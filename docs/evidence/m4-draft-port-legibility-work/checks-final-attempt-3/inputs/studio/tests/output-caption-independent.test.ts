import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { applyVisualBatch, buildScene, createDocument, createHistory, reduceHistory, renderSvg } from '../src/core/index.ts';
import type { Architecture, ArchitectureNode, CanvasDocument, OutputPathSegment, Scene } from '../src/core/index.ts';

// These examples and expected captions were handwritten before the bounded
// scene repair. No expected return key is inferred from a rendered subtitle.
const realKey = 'n_192b289eb9894cdf852dee0442427de7';
const realId = 'output:model.AuthoredModel:0';
const rawUrl = new URL('../../docs/evidence/m4-authoring-interaction-work/output-caption/attempt-1/before/docs/evidence/m4-collapse-continuity-work/authoring-browser-attempt-1/managed-saved-envelope.json', import.meta.url);
function sealedDocument(): CanvasDocument {
  const bytes = readFileSync(rawUrl);
  assert.equal(createHash('sha256').update(bytes).digest('hex'), 'aa70556487db07545573133b0100324d2b77a2c6bff4a4075ffff8039d1a9ed8');
  return JSON.parse(bytes.toString()).document;
}
function output(id: string, outputPath: OutputPathSegment[]): ArchitectureNode {
  return { id, label: 'output', kind: 'Output', category: 'output', children: [], ports: [], parameters: {}, evidence: 'source', outputPath };
}
function handwrittenArchitecture(nodes: ArchitectureNode[]): Architecture {
  return { schemaVersion: 1, id: 'caption-handwritten', label: 'Caption examples', sourceDigest: 'unchanged-source', irDigest: 'unchanged-ir',
    entry: 'model:CaptionExamples', nodes, edges: [], diagnostics: [], sources: [
      { path: 'model.py', content: 'class CaptionExamples:\n    def forward(self, x):\n        return {"forecast": [x, x], "state": {"hidden": x}}\n', digest: 'unchanged-file-digest' },
    ] };
}
function decodeXml(value: string): string {
  return value.replace(/&(amp|lt|gt|quot|apos);/g, (_, name: string) => ({ amp: '&', lt: '<', gt: '>', quot: '"', apos: "'" }[name]!));
}
function metadata(svg: string): { sourceFacts: Scene['sourceFacts']; sourceDigest: string; irDigest: string } {
  const text = /<metadata>([\s\S]*?)<\/metadata>/.exec(svg)?.[1];
  assert.ok(text, 'SVG retains machine-readable source metadata');
  return JSON.parse(decodeXml(text));
}
function visibleText(svg: string): string {
  return [...svg.matchAll(/<text\b[^>]*>([\s\S]*?)<\/text>/g)].map(match => decodeXml(match[1].replace(/<[^>]+>/g, ''))).join('\n');
}

test('sealed generated architecture uses the actual Output alias while exact return evidence survives in scene and SVG', () => {
  const d = sealedDocument(), before = structuredClone(d);
  assert.equal(d.displayAliases[realId], '输出');
  assert.deepEqual(d.architecture.nodes.find(n => n.id === realId)?.outputPath, [{ kind: 'key', key: realKey }]);
  const scene = buildScene(d), node = scene.nodes.find(n => n.id === realId)!;
  assert.equal(node.label, '输出');
  assert.equal(node.subtitle, 'model output');
  assert.deepEqual(node.sourceFact?.outputPath, [{ kind: 'key', key: realKey }]);
  assert.equal(node.sourceFact?.sourceLabel, 'output');
  const svg = renderSvg(scene), exported = metadata(svg);
  assert.ok(visibleText(svg).includes('model output'));
  assert.ok(!visibleText(svg).includes(realKey));
  assert.ok(svg.includes(`return[&quot;${realKey}&quot;]`), 'hover/title preserves the real output path');
  assert.deepEqual(exported.sourceFacts.find(n => n.id === realId)?.outputPath, [{ kind: 'key', key: realKey }]);
  assert.equal(exported.sourceDigest, before.architecture.sourceDigest);
  assert.equal(exported.irDigest, before.architecture.irDigest);
  assert.deepEqual(d, before, 'projection and export never mutate source or document');
});

test('a legitimate n_ user return key without a display alias is never classified as machine-generated', () => {
  const d = sealedDocument();
  delete d.displayAliases[realId];
  const before = structuredClone(d), scene = buildScene(d);
  assert.equal(scene.nodes.find(n => n.id === realId)?.label, 'output');
  assert.equal(scene.nodes.find(n => n.id === realId)?.subtitle, 'return.n_192b289eb9894cdf852dee0442427de7');
  assert.deepEqual(scene.sourceFacts.find(n => n.id === realId)?.outputPath, [{ kind: 'key', key: realKey }]);
  assert.deepEqual(d, before);
});

test('nested slots, scalar keys, a UUID-looking user key and whole return retain handwritten unaliased captions', () => {
  const d = createDocument(handwrittenArchitecture([
    output('forecast-1', [{ kind: 'key', key: 'forecast' }, { kind: 'index', index: 1 }]),
    output('scalar-keys', [{ kind: 'key', key: 'a.b' }, { kind: 'index', index: 2 }, { kind: 'key', key: false }, { kind: 'key', key: null }, { kind: 'key', key: '输出' }]),
    output('uuid-key', [{ kind: 'key', key: '550e8400-e29b-41d4-a716-446655440000' }]),
    output('whole-return', []),
  ]));
  const before = structuredClone(d), scene = buildScene(d);
  assert.deepEqual(scene.nodes.map(n => [n.id, n.subtitle]), [
    ['forecast-1', 'return.forecast[1]'],
    ['scalar-keys', 'return["a.b"][2][false][null]["输出"]'],
    ['uuid-key', 'return["550e8400-e29b-41d4-a716-446655440000"]'],
    ['whole-return', 'return'],
  ]);
  assert.deepEqual(d, before);
});

test('different long aliases on multiple outputs retain distinct labels and their independent actual nested paths', () => {
  const d = createDocument(handwrittenArchitecture([
    output('forecast', [{ kind: 'key', key: 'forecast' }, { kind: 'index', index: 1 }]),
    output('hidden', [{ kind: 'key', key: 'state' }, { kind: 'key', key: 'hidden' }]),
  ]));
  d.displayAliases.forecast = 'Future observations after temporal projection with a long explanatory caption';
  d.displayAliases.hidden = 'Hidden memory carried into the next iteration with a different long caption';
  const before = structuredClone(d), scene = buildScene(d), exported = metadata(renderSvg(scene));
  assert.deepEqual(scene.nodes.map(n => [n.id, n.label, n.subtitle]), [
    ['forecast', 'Future observations after temporal projection with a long explanatory caption', 'model output'],
    ['hidden', 'Hidden memory carried into the next iteration with a different long caption', 'model output'],
  ]);
  assert.deepEqual(exported.sourceFacts.map(n => [n.id, n.outputPath]), [
    ['forecast', [{ kind: 'key', key: 'forecast' }, { kind: 'index', index: 1 }]],
    ['hidden', [{ kind: 'key', key: 'state' }, { kind: 'key', key: 'hidden' }]],
  ]);
  assert.deepEqual(d, before);
});

test('non-output aliases, an Output without a declared path and opaque evidence preserve their existing meaning', () => {
  const linear: ArchitectureNode = { id: 'linear', label: 'projection', kind: 'Linear', category: 'module', children: [], ports: [],
    parameters: { in_features: 16, out_features: 8 }, evidence: 'contract' };
  const legacy: ArchitectureNode = { id: 'legacy-output', label: 'output', kind: 'Output', category: 'output', children: [], ports: [], parameters: {}, evidence: 'source' };
  const unresolved = output('unresolved', [{ kind: 'key', key: 'opaque' }]); unresolved.evidence = 'opaque';
  const d = createDocument(handwrittenArchitecture([linear, legacy, unresolved]));
  d.displayAliases = { linear: 'Named projection', 'legacy-output': 'Named old output', unresolved: 'Named unknown output' };
  assert.deepEqual(buildScene(d).nodes.map(n => [n.id, n.subtitle]), [
    ['linear', '16 → 8'], ['legacy-output', 'Output'], ['unresolved', 'unresolved · opaque boundary'],
  ]);
});

test('explicit alias uses existing visual history and undo restores the real return caption without touching canonical facts', () => {
  const d = sealedDocument(); delete d.displayAliases[realId];
  const architecture = structuredClone(d.architecture);
  let history = createHistory(d);
  history = reduceHistory(history, { type: 'apply', operations: [{ type: 'alias', id: realId, label: 'Predictions' }] });
  assert.equal(buildScene(history.document).nodes.find(n => n.id === realId)?.subtitle, 'model output');
  assert.deepEqual(history.document.architecture, architecture);
  history = reduceHistory(history, { type: 'undo' });
  assert.equal(buildScene(history.document).nodes.find(n => n.id === realId)?.subtitle, 'return.n_192b289eb9894cdf852dee0442427de7');
  assert.deepEqual(history.document.architecture, architecture);
  history = reduceHistory(history, { type: 'redo' });
  assert.equal(buildScene(history.document).nodes.find(n => n.id === realId)?.label, 'Predictions');
  assert.equal(buildScene(history.document).nodes.find(n => n.id === realId)?.subtitle, 'model output');
  assert.deepEqual(history.document.architecture, architecture);
  const sameName = applyVisualBatch(d, [{ type: 'alias', id: realId, label: 'output' }]);
  assert.equal(buildScene(sameName).nodes.find(n => n.id === realId)?.subtitle, 'model output', 'explicit alias is a presentation choice even when it matches the source label');
});
