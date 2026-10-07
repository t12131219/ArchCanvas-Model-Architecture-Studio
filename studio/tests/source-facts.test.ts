import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';
import { applyVisualBatch, buildExportScene, buildScene, createDocument, instanceCalls, outputPathText, renderSvg, sourceNodeFacts, validateDocument } from '../src/core/index.ts';
import { textWidth } from '../src/core/typography.ts';
import type { Architecture, CanvasDocument } from '../src/core/index.ts';

const project = fileURLToPath(new URL('../../', import.meta.url));
async function model(name: string): Promise<Architecture> {
  const local = `${project}.venv/bin/python`;
  const { stdout } = await promisify(execFile)(existsSync(local) ? local : 'python3', ['-I', '-S', '-B', '-c',
    'import sys,json; from pathlib import Path; root=Path(sys.argv[1]);sys.path.insert(0,str(root/"src"));from archcanvas_python import analyze_project;print(json.dumps(analyze_project(root/"fixtures/holdout_families",sys.argv[2])))',
    project, `model:${name}`], { encoding: 'utf8', maxBuffer: 2_000_000 });
  return JSON.parse(stdout);
}
function metadata(svg: string) {
  return JSON.parse(svg.match(/<metadata>(.*?)<\/metadata>/s)![1].replace(/&(quot|apos|lt|gt|amp);/g,
    (_, entity) => ({ quot: '"', apos: "'", lt: '<', gt: '>', amp: '&' }[entity as string]!)));
}

test('real Temporal shared projection keeps two distinct calls and four authored paths after edits and reopen', async () => {
  const architecture = await model('TemporalForecaster');
  const projection = architecture.nodes.filter(node => node.kind === 'Linear');
  assert.equal(projection.length, 2);
  assert.equal(projection[0].instanceId, projection[1].instanceId);
  assert.notEqual(projection[0].callId, projection[1].callId);
  assert.deepEqual(instanceCalls(architecture, projection[0]).map(node => node.id), projection.map(node => node.id));
  const facts = sourceNodeFacts(architecture);
  assert.deepEqual(facts.filter(fact => fact.kind === 'Linear').map(fact => fact.callCount), [2, 2]);
  assert.deepEqual(facts.filter(fact => fact.kind === 'Output').map(fact => outputPathText(fact.outputPath!)),
    ['return["forecast"][0]', 'return["forecast"][1]', 'return["state"]["hidden"]', 'return["state"]["cell"]']);
  const edited = applyVisualBatch(createDocument(architecture), [
    { type: 'alias', id: projection[0].id, label: 'Published estimate' },
    { type: 'nodeStyle', id: projection[1].id, style: { fill: '#123456' } },
    { type: 'move', ids: [projection[0].id], dx: 17, dy: 11 }, { type: 'pin', ids: [projection[1].id], pinned: true },
  ]);
  const reopened = validateDocument(JSON.parse(JSON.stringify(edited))) as CanvasDocument;
  const scene = buildScene(reopened), exported = buildExportScene(reopened), svg = renderSvg(exported), receipt = metadata(svg);
  assert.deepEqual(scene.sourceFacts, facts); assert.deepEqual(exported.sourceFacts, facts);
  assert.deepEqual(receipt.sourceFacts, facts);
  assert.equal(receipt.sourceFactScope, 'whole-source-architecture');
  assert.equal(receipt.sourceDigest, architecture.sourceDigest); assert.equal(receipt.irDigest, architecture.irDigest);
  assert.equal(receipt.documentId, edited.id); assert.equal(receipt.revision, edited.revision);
  assert.equal(scene.nodes.find(node => node.id === projection[0].id)!.label, 'Published estimate');
  assert.equal(scene.nodes.find(node => node.id === projection[0].id)!.subtitle, 'shared instance · 2 calls');
  assert.ok(svg.includes('return.forecast[0]')); assert.ok(svg.includes('return.state.hidden'));
  assert.deepEqual(receipt.renderedBindings.map((binding: { sceneEdgeId: string; canonicalEdgeIds: string[] }) => [binding.sceneEdgeId, binding.canonicalEdgeIds]),
    scene.edges.map(edge => [edge.id, edge.canonicalEdgeIds]));
  assert.deepEqual(reopened.architecture, architecture);
});

test('Skip repeat is independent; expanding and detail export retain identities and external boundaries', async () => {
  const architecture = await model('SkipSegmentation');
  const repeat = architecture.nodes.find(node => node.repeat)!;
  assert.deepEqual(repeat.repeat, { count: 2, sharing: 'independent' });
  const children = repeat.children.map(id => architecture.nodes.find(node => node.id === id)!);
  assert.equal(new Set(children.map(node => node.instanceId)).size, 2);
  const document = applyVisualBatch(createDocument(architecture), [{ type: 'expand', id: repeat.id, expanded: true }]);
  const full = buildScene(document), detail = buildExportScene(document, { nodeId: repeat.id });
  assert.equal(full.nodes.find(node => node.id === repeat.id)!.subtitle, '2 × independent instances');
  assert.ok(renderSvg(full).includes('2× · independent'));
  assert.deepEqual(detail.sourceFacts, sourceNodeFacts(architecture));
  const receipt = metadata(renderSvg(detail));
  for (const boundary of detail.nodes.filter(node => node.boundary)) {
    assert.equal(boundary.sourceFact!.id, boundary.canonicalNodeId);
    assert.ok(receipt.renderedNodes.some((node: { sceneNodeId: string; canonicalNodeId: string; boundary: boolean }) =>
      node.sceneNodeId === boundary.id && node.canonicalNodeId === boundary.canonicalNodeId && node.boundary));
  }
  const supported = receipt.sourceFacts.find((fact: { kind: string }) => fact.kind === 'ConvTranspose2d');
  assert.ok(supported, 'the expanded formal catalog must retain this operator in source facts');
  assert.equal(supported.evidence, 'contract');
});

test('GNN names and arbitrary visual aliases do not turn unknown regions into known attention', async () => {
  const architecture = await model('GraphForecast');
  const unknown = architecture.nodes.find(node => node.kind === 'GraphAttentionKernel')!;
  assert.equal(unknown.evidence, 'opaque');
  const document = applyVisualBatch(createDocument(architecture), [
    { type: 'alias', id: unknown.id, label: 'Self Attention' }, { type: 'nodeStyle', id: unknown.id, style: { glyph: 'attention' } },
  ]);
  const scene = buildScene(document), visible = scene.nodes.find(node => node.id === unknown.id)!;
  assert.equal(visible.evidence, 'opaque'); assert.equal(visible.subtitle, 'unresolved · opaque boundary');
  const svg = renderSvg(scene), fact = metadata(svg).sourceFacts.find((node: { id: string }) => node.id === unknown.id);
  assert.equal(fact.kind, 'GraphAttentionKernel'); assert.equal(fact.evidence, 'opaque');
  assert.equal(fact.sourceLabel, 'message'); assert.ok(svg.includes('stroke-dasharray="5 3"'));
  assert.equal(architecture.nodes.some(node => node.kind === 'MultiheadAttention'), false);
});

test('same label and duplicated call identity cannot invent distinct shared calls; facts detach from Canvas', async () => {
  const architecture = await model('TemporalForecaster');
  const nodes = architecture.nodes.filter(node => node.kind === 'Linear');
  const notShared = structuredClone(architecture);
  notShared.nodes.find(node => node.id === nodes[1].id)!.instanceId = 'independent-instance';
  assert.equal(instanceCalls(notShared, nodes[0]).length, 1);
  assert.equal(sourceNodeFacts(notShared).find(fact => fact.id === nodes[0].id)!.callCount, 1);
  const duplicate = structuredClone(architecture);
  duplicate.nodes.find(node => node.id === nodes[1].id)!.callId = nodes[0].callId;
  assert.equal(instanceCalls(duplicate, nodes[0]).length, 1);
  assert.equal(sourceNodeFacts(duplicate).find(fact => fact.id === nodes[0].id)!.callCount, 1);
  const document = createDocument(architecture), before = JSON.stringify(document), scene = buildScene(document);
  scene.sourceFacts.find(fact => fact.outputPath)!.outputPath![0] = { kind: 'key', key: 'changed-scene-only' };
  scene.sourceFacts.find(fact => fact.source)!.source!.expression = 'changed scene expression';
  assert.equal(JSON.stringify(document), before);
});

test('long authored output keys stay exact in metadata while subtitles fit the existing node width', async () => {
  const architecture = await model('TemporalForecaster');
  const output = architecture.nodes.find(node => node.kind === 'Output')!;
  const key = '<&"long slot>'.repeat(25);
  output.outputPath = [{ kind: 'key', key }];
  const scene = buildScene(createDocument(architecture)), node = scene.nodes.find(node => node.id === output.id)!;
  const svg = renderSvg(scene);
  // The main node group carries more attributes, so locate by its exact id and direct body text.
  const fragment = svg.slice(svg.indexOf(`data-node-id="${output.id}"`), svg.indexOf(`data-node-id="${output.id}"`) + 8000);
  const subtitle = fragment.match(/font-size="10">([^<]*)<\/text>/)![1].replace(/&(quot|apos|lt|gt|amp);/g,
    (_, entity) => ({ quot: '"', apos: "'", lt: '<', gt: '>', amp: '&' }[entity as string]!));
  assert.ok(subtitle.endsWith('…')); assert.ok(textWidth(subtitle, 10) <= node.width - 62);
  assert.deepEqual(metadata(svg).sourceFacts.find((fact: { id: string }) => fact.id === output.id).outputPath, [{ kind: 'key', key }]);
  assert.equal(scene.nodes.find(node => node.id === output.id)!.width, 194);
});
