import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildScene, renderSvg, createDocument, createHistory } from '../src/core/index.ts';
import { sourceNodeFacts } from '../src/core/nodeFacts.ts';
import { isPreviewPanelDocument, previewMappingCoverage, previewNeedsPanelDocument, previewPanelDocument, projectPreviewHistory } from '../src/previewPanelDocument.ts';
import { previewSelectionNodeIds, previewUniqueNodeBindings, previewCanvasOperations, previewExpansionOperations } from '../src/previewInterop.ts';
import { previewDocumentSyncOperations } from '../src/previewPresentation.ts';
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

function registeredCase(id: string) {
  const base = new URL('../public/preview/', import.meta.url);
  const catalog = JSON.parse(readFileSync(new URL('data/catalog.json', base), 'utf8'));
  const index = JSON.parse(readFileSync(new URL('data/catalog-sources.json', base), 'utf8')).cases;
  const entry = catalog.cases.find((item: { id: string }) => item.id === id), descriptor = index[id];
  const view = entry.views.filter((item: { json?: string }) => item.json).sort((a: { nodes: number }, b: { nodes: number }) => b.nodes - a.nodes)[0];
  const graph = JSON.parse(readFileSync(new URL(view.json, base), 'utf8'));
  const raw = descriptor.evidence ? JSON.parse(readFileSync(new URL(descriptor.evidence, base), 'utf8')) : {};
  const evidence: NonNullable<RawPreviewSource['evidence']> = {};
  for (const [key, item] of Object.entries(raw.symbols ?? raw) as [string, any][]) {
    if (!item || typeof item !== 'object' || !(item.line ?? item.start)) continue;
    const path = item.file ?? item.path ?? item.source ?? raw.origin;
    const source = descriptor.files.find((file: { path: string; originalPath?: string }) => [file.path, file.originalPath].filter(Boolean).some(alias => path === alias || path?.endsWith('/' + alias)));
    evidence[item.evidence_id ?? key] = { file: source?.path ?? path, line: item.line ?? item.start,
      endLine: item.endLine ?? item.end ?? item.line ?? item.start, expression: item.expression ?? item.snippet ?? '' };
  }
  const source: RawPreviewSource = { schema: 'archcanvas-preview-source/1', caseId: id, entry: 'reviewed:Model',
    files: Object.fromEntries(descriptor.files.map((file: { path: string; asset: string }) => [file.path, readFileSync(new URL(file.asset, base), 'utf8')])), evidence };
  return { snapshot: { caseId: id, graph } as PreviewSnapshot, source };
}

test('actual notebook AlexNet and module diagrams retain all display actions when their formal parser coverage differs', () => {
  for (const id of ['771109e666204fb7', '25a45edcfd7a974c']) {
    const { snapshot, source } = registeredCase(id), before = previewPanelDocument(snapshot, source);
    assert.ok(before.architecture.sources.length > 0); assert.ok(before.architecture.sources.every(file => file.path.endsWith('.py')));
    assert.ok(before.architecture.nodes.some(node => node.source), 'registered reviewed source evidence remains inspectable');
    const partial = { ...before.architecture, nodes: [] };
    const coverage = previewMappingCoverage(snapshot, partial, source);
    assert.equal(coverage.mapped, 0); assert.equal(coverage.unmapped.length, coverage.total);
    assert.equal(previewNeedsPanelDocument(snapshot, partial, source), true);
    assert.equal(previewNeedsPanelDocument(snapshot, before.architecture, source), false);
    const after = structuredClone(before), target = before.architecture.nodes.find(node => node.children.length)!;
    after.displayAliases[target.id] = 'Reviewed display'; after.nodeStyleOverrides[target.id] = { fill: '#deeee6', stroke: '#123456', glyph: 'opaque' };
    after.pinnedObjects = [target.id]; after.layout[target.id].x += 20;
    const edge = after.architecture.edges[0]; if (edge) after.edgeStyleOverrides[edge.id] = { stroke: '#654321', dashed: true, width: 3 };
    const operations = previewDocumentSyncOperations(before, after, snapshot.graph, source);
    const paint = operations.find(operation => operation.type === 'syncPresentation')!;
    assert.deepEqual((paint.nodes as Record<string, unknown>)[target.id], { alias: 'Reviewed display', fill: '#deeee6', stroke: '#123456', glyph: 'opaque', pinned: true });
    assert.ok(operations.some(operation => operation.type === 'nodeLayout' && operation.id === target.id));
    if (edge) assert.deepEqual((paint.edges as Record<string, unknown>)[edge.id], { stroke: '#654321', dashed: true, width: 3 });
    assert.deepEqual(after.architecture, before.architecture); assert.ok(after.architecture.nodes.every(node => node.evidence === 'opaque'));
    assert.equal(after.sourceBindingDigest, `preview-only:${id}`);
  }
});

test('mapping coverage treats reviewed aggregates sharing one formal source object as visual-only objects', () => {
  const graph = { nodes: [{ id: 'reviewed-first', x: 0, y: 0, semantic: { id: 'reviewed-first', kind: 'linear', source_evidence: ['call'] } },
    { id: 'reviewed-second', x: 250, y: 0, semantic: { id: 'reviewed-second', kind: 'linear', source_evidence: ['call'] } },
    { id: 'junction', x: 100, y: 0, junction: true }], edges: [] };
  const source: RawPreviewSource = { schema: 'archcanvas-preview-source/1', caseId: 'aggregate', entry: 'model:Model', files: { 'model.py': 'self.linear(x)' },
    evidence: { call: { file: 'model.py', line: 1, endLine: 1, expression: 'self.linear(x)' } } };
  const projected = previewPanelDocument({ caseId: 'aggregate', graph }, source);
  const formal = { ...projected.architecture, nodes: [{ ...projected.architecture.nodes[0], id: 'formal-call', kind: 'Linear', category: 'linear' }] };
  const coverage = previewMappingCoverage({ graph }, formal, source);
  assert.equal(coverage.total, 2); assert.equal(coverage.mapped, 0); assert.deepEqual(coverage.shared, ['reviewed-first', 'reviewed-second']);
  assert.equal(previewNeedsPanelDocument({ graph }, formal, source), true);
  const document = createDocument(formal);
  document.displayAliases['formal-call'] = '正式部件名'; document.nodeStyleOverrides['formal-call'] = { fill: '#112233' };
  document.pinnedObjects = ['formal-call'];
  const visual = { ...graph, studioPresentation: { nodes: {
    'reviewed-first': { alias: '第一展示名', fill: '#334455' }, 'reviewed-second': { alias: '第二展示名', fill: '#556677' },
  } } };
  assert.equal(previewUniqueNodeBindings(formal, visual, source).size, 0);
  assert.deepEqual(previewCanvasOperations(document, visual, source), []);
  assert.deepEqual(previewExpansionOperations(document, visual, source), []);
  const synchronized = previewDocumentSyncOperations(undefined, document, visual, source);
  assert.deepEqual(synchronized.flatMap(operation => Object.keys((operation.nodes ?? {}) as Record<string, unknown>)), [], 'formal presentation never chooses the first shared display object');
  const after = projectPreviewHistory(createHistory(document), visual, source).document;
  assert.deepEqual(after.layout, document.layout); assert.deepEqual(after.architecture, formal);
  assert.deepEqual(after.displayAliases, document.displayAliases); assert.deepEqual(after.nodeStyleOverrides, document.nodeStyleOverrides);
  assert.deepEqual(after.pinnedObjects, document.pinnedObjects, 'inspection painting cannot overwrite a formal object through shared evidence');
});
