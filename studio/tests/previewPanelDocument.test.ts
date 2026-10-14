import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildScene, renderSvg } from '../src/core/index.ts';
import { sourceNodeFacts } from '../src/core/nodeFacts.ts';
import { isPreviewPanelDocument, previewPanelDocument } from '../src/previewPanelDocument.ts';
import { previewSelectionNodeIds } from '../src/previewInterop.ts';
import type { RawPreviewSource } from '../src/previewInterop.ts';
import type { PreviewSnapshot } from '../src/PreviewStudio.tsx';

test('routing-only and unknown catalog node kinds have usable panels without declaring model source facts', () => {
  const snapshot: PreviewSnapshot = { caseId: 'routing-lab', caseInfo: { title: 'Edge Router · 避障实验' }, graph: {
    nodes: ['module', 'explanatory_softmax', 'constructor', '__proto__'].map((kind, i) => ({ id: `node-${i}`, label: `Sandbox ${i}`, x: i * 250, y: 50,
      expanded: false, semantic: { id: `node-${i}`, kind, shape: '[B,512]', param_identity: 'model.weight', certainty: 'runtime' } })),
    edges: [{ id: 'route', source: 'node-0', target: 'node-1' }],
  } };
  const document = previewPanelDocument(snapshot), scene = buildScene(document);
  assert.equal(isPreviewPanelDocument(document), true); assert.equal(document.title, 'Edge Router · 避障实验');
  assert.equal(document.architecture.sources.length, 0); assert.equal(document.architecture.entry, '');
  assert.ok(document.architecture.nodes.every(node => node.evidence === 'opaque' && Object.keys(node.parameters).length === 0));
  assert.deepEqual(document.architecture.nodes.map(node => node.category), ['module', 'opaque', 'opaque', 'opaque']);
  assert.equal(scene.nodes.length, 4); assert.ok(renderSvg(scene).includes('Sandbox'));
  const facts = sourceNodeFacts(document.architecture);
  assert.ok(facts.every(fact => fact.evidence === 'opaque' && !fact.source && !fact.instanceId && !fact.callId && !fact.outputPath));
  assert.ok(document.architecture.nodes.every(node => node.ports.every(port => port.role === 'display')));
});

test('historical library source spans appear as opaque inspection evidence while shape, parameter and call claims remain excluded', () => {
  const graph = JSON.parse(readFileSync(new URL('../public/preview/data/cases/25a45edcfd7a974c-overview.json', import.meta.url), 'utf8'));
  const raw: RawPreviewSource = { schema: 'archcanvas-preview-source/1', caseId: '25a45edcfd7a974c', entry: 'glow_modules.model:ActNorm', files: {
    'glow-modules/model.py': '# preserved source text\n',
  }, evidence: { E001: { file: 'glow-modules/model.py', line: 12, endLine: 18, expression: 'def __init__(self): ...' },
    E002: { file: 'glow-modules/model.py', line: 42, endLine: 58, expression: 'def forward(self, x): ...' } } };
  const before = JSON.stringify(graph), document = previewPanelDocument({ caseId: raw.caseId, graph }, raw);
  assert.equal(JSON.stringify(graph), before);
  assert.doesNotThrow(() => buildScene(document));
  const root = document.architecture.nodes.find(node => node.id === 'glow_actnorm.root')!;
  assert.equal(root.kind, 'group'); assert.equal(root.category, 'container'); assert.equal(root.evidence, 'opaque');
  assert.equal(root.source?.path, 'glow-modules/model.py'); assert.equal(root.source?.line, 12);
  assert.equal(document.architecture.sources[0].digest, 'preview-only');
  const facts = sourceNodeFacts(document.architecture), fact = facts.find(item => item.id === root.id)!;
  assert.equal(fact.source?.expression, 'def __init__(self): ...'); assert.equal(fact.evidence, 'opaque');
  assert.equal(fact.instanceId, undefined); assert.equal(fact.repeat, undefined);
  assert.deepEqual(previewSelectionNodeIds(document.architecture, { nodeId: 'glow_actnorm.root' }, raw), ['glow_actnorm.root']);
  assert.equal(document.architecture.nodes.find(node => node.id === 'glow_actnorm.x')?.parameters.shape, undefined);
});

test('panel geometry uses the preview parent frame and cannot mutate formal source bindings', () => {
  const graph = { nodes: [{ id: 'root', label: 'Root', x: 200, y: 100, expanded: true, semantic: { id: 'root', kind: 'group' } },
    { id: 'child', label: 'Child', parent: 'root', x: 260, y: 180, semantic: { id: 'child', kind: 'linear' } }], edges: [] };
  const document = previewPanelDocument({ caseId: 'nested', graph });
  assert.deepEqual(document.layout.child, { x: 60, y: 80 }); assert.deepEqual(document.expandedIds, ['root']);
  assert.equal(document.sourceBindingDigest, 'preview-only:nested'); assert.equal(document.architecture.sourceDigest, document.sourceBindingDigest);
  assert.equal(document.architecture.nodes[1].evidence, 'opaque');
});
