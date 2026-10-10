import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { applyVisualBatch, buildExportScene, buildScene, createDocument, createHistory, reduceHistory, renderSvg } from '../src/core/index.ts';
import type { Architecture, ArchitectureNode, CanvasDocument } from '../src/core/types.ts';
import { layoutWarnings } from '../src/layoutWarnings.ts';
import { planLayoutRecovery } from '../src/core/layoutRecovery.ts';
import { prepareMovePreview, previewMoveScene } from '../src/core/movePreview.ts';
import { createOrthogonalRouter } from '../src/core/orthogonalRouter.ts';

const editor = { presentation: 'editor' } as const;
function hierarchy(): CanvasDocument {
  const node = (id: string, parentId?: string, children: string[] = []): ArchitectureNode => ({
    id, label: id, kind: children.length ? 'Module' : 'Linear', category: children.length ? 'container' : 'linear',
    parentId, children, parameters: {}, evidence: 'source', ports: [
      { id: 'in', name: 'input', direction: 'in', role: 'data', ordinal: 0 },
      { id: 'out', name: 'output', direction: 'out', role: 'data', ordinal: 0 },
    ],
  });
  const architecture: Architecture = {
    schemaVersion: 1, id: 'free-root', label: 'Model', entry: 'model:Model', sourceDigest: 'source', irDigest: 'ir', sources: [], diagnostics: [],
    nodes: [node('root', undefined, ['input', 'group', 'output', 'spare']), node('input', 'root'),
      node('group', 'root', ['first', 'second']), node('first', 'group'), node('second', 'group'), node('output', 'root'), node('spare', 'root')],
    edges: [
      { id: 'enter', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'first', portId: 'in' }, tensorId: 'input', role: 'data' },
      { id: 'inside', source: { nodeId: 'first', portId: 'out' }, target: { nodeId: 'second', portId: 'in' }, tensorId: 'middle', role: 'data' },
      { id: 'leave', source: { nodeId: 'second', portId: 'out' }, target: { nodeId: 'output', portId: 'in' }, tensorId: 'result', role: 'data' },
    ],
  };
  const document = createDocument(architecture);
  document.layout = { root: { x: 50, y: 92 }, input: { x: -200, y: -100 }, group: { x: -200, y: 80 },
    first: { x: 30, y: 70 }, second: { x: 30, y: 180 }, output: { x: 180, y: 620 }, spare: { x: 320, y: -100 } };
  return document;
}

test('Transformer overview no longer reports its hidden root boundary or title while preserving publication checks', () => {
  const fixture = JSON.parse(readFileSync(new URL('../../docs/evidence/unified-editor-review-v2/routing-before/transformer-level3-base.canvas.json', import.meta.url), 'utf8')) as CanvasDocument;
  const document = applyVisualBatch(createDocument(fixture.architecture), [
    { type: 'move', ids: ['input:model.Transformer:memory_mask'], dx: -150, dy: -62 },
    { type: 'move', ids: ['repeat:instance:model.Transformer.encoder'], dx: -150, dy: 0 },
  ]);
  const before = JSON.stringify(document), publication = buildExportScene(document), scene = buildScene(document, editor);
  assert.deepEqual(layoutWarnings(publication), [
    '“memory_mask”超出了“Transformer”的边界。移回容器内，或预览位置修复。',
    '“encoder”超出了“Transformer”的边界。移回容器内，或预览位置修复。',
    '“memory_mask”进入了“Transformer”的标题区。向下移动该对象可恢复留白。',
  ]);
  assert.deepEqual(layoutWarnings(scene), []);
  assert.deepEqual(scene.nodes.map(node => [node.id, node.x, node.y]), publication.nodes.map(node => [node.id, node.x, node.y]));
  assert.deepEqual(scene.edges.map(edge => [edge.id, edge.canonicalEdgeIds, edge.source, edge.target, edge.tensorId]),
    publication.edges.map(edge => [edge.id, edge.canonicalEdgeIds, edge.source, edge.target, edge.tensorId]));
  assert.deepEqual(scene.sourceFacts, publication.sourceFacts);
  assert.equal(JSON.stringify(document), before);
  assert.deepEqual(buildExportScene(document), publication);
  assert.doesNotMatch(renderSvg(scene, { presentation: 'editor' }).split('</metadata>')[1], /data-node-id="call:instance:model.Transformer" data-canonical-id=/);
});

test('hidden root headers cease to be routing obstacles, while physical frames retain their headers', () => {
  const scene = buildScene(hierarchy(), editor), base = scene.nodes.find(node => node.id === 'input')!;
  const root = { ...scene.nodes.find(node => node.id === 'root')!, x: 0, y: 0, width: 400, height: 200, headerHeight: 100 };
  const source = { ...base, id: 'source', parentId: root.id, x: 30, y: 20, width: 50, height: 30 };
  const target = { ...base, id: 'target', parentId: root.id, x: 250, y: 20, width: 50, height: 30 };
  const request = { sourceId: source.id, targetId: target.id, tensorId: 'tensor', role: 'data' as const,
    start: { x: 80, y: 35 }, end: { x: 250, y: 35 }, preferredPath: 'M 80 35 H 250' };
  const physical = createOrthogonalRouter([root, source, target]);
  assert.equal(physical.headerOverlaps.length, 2);
  assert.ok(physical(request).blockedBy.includes(root.id));
  const logical = createOrthogonalRouter([root, source, target], new Set([root.id]));
  assert.deepEqual(logical.headerOverlaps, []);
  assert.deepEqual(logical(request).blockedBy, []);
  assert.equal(logical(request).path, request.preferredPath);
});

test('negative world positions survive nested and root collapse, undo, redo and JSON reopen', () => {
  let document = hierarchy();
  document.displayAliases.input = 'Custom input';
  document.nodeStyleOverrides.input = { fill: '#abcdef' };
  document.pinnedObjects = ['spare'];
  const initial = buildScene(document, editor), facts = JSON.parse(JSON.stringify(document.architecture));
  const locations = (value: CanvasDocument) => buildScene(value, editor).nodes.map(node => [node.id, node.x, node.y, node.width, node.height]);
  let history = createHistory(document);
  const toggle = (id: string, expanded: boolean) => { history = reduceHistory(history, { type: 'apply', operations: [{ type: 'expand', id, expanded }] }); };
  toggle('group', true); toggle('group', false);
  assert.deepEqual(locations(history.document), locations(document));
  assert.deepEqual(buildScene(history.document, editor).edges, initial.edges);
  toggle('root', false);
  assert.deepEqual(buildScene(history.document, editor).nodes.map(node => node.id), ['root']);
  assert.match(renderSvg(buildScene(history.document, editor), { presentation: 'editor' }), /data-node-id="root" data-canonical-id=/);
  toggle('root', true);
  assert.deepEqual(locations(history.document), locations(document));
  history = reduceHistory(reduceHistory(history, { type: 'undo' }), { type: 'redo' });
  document = JSON.parse(JSON.stringify(history.document));
  assert.deepEqual(locations(document), initial.nodes.map(node => [node.id, node.x, node.y, node.width, node.height]));
  assert.deepEqual(document.architecture, facts);
  assert.equal(document.displayAliases.input, 'Custom input');
  assert.equal(document.nodeStyleOverrides.input.fill, '#abcdef');
  assert.deepEqual(document.pinnedObjects, ['spare']);
});

test('visible nested containers still report escaped children and header intrusion', () => {
  const document = applyVisualBatch(hierarchy(), [{ type: 'expand', id: 'group', expanded: true }]);
  document.layout.first = { x: -10, y: 0 };
  const scene = buildScene(document, editor);
  assert.ok(scene.diagnostics.some(item => item.code === 'layout-outside-parent' && item.objectIds?.[0] === 'first' && item.objectIds[1] === 'group'));
  assert.ok(scene.diagnostics.some(item => item.code === 'layout-header-overlap' && item.objectIds?.[0] === 'first' && item.objectIds[1] === 'group'));
  assert.ok(!scene.diagnostics.some(item => item.code && item.objectIds?.includes('root')));
});

test('editor drag preview matches commit and recovery does not clamp objects into the hidden root', () => {
  const document = hierarchy(), id = 'input';
  const session = prepareMovePreview(document, [id], 'current-frontier');
  const preview = previewMoveScene(session, -24, -32, editor);
  const committed = applyVisualBatch(document, [{ type: 'move', ids: [id], dx: -24, dy: -32, scope: 'current-frontier' }]);
  assert.deepEqual(preview, buildScene(committed, editor));
  assert.equal(planLayoutRecovery(committed, id, 'current-frontier', editor).status, 'unneeded');
  document.layout.spare = { ...document.layout.input };
  const plan = planLayoutRecovery(document, id, 'current-frontier', editor);
  assert.equal(plan.status, 'ready');
  if (plan.status !== 'ready') return;
  const moved = plan.scene.nodes.find(node => node.id === id)!, root = plan.scene.nodes.find(node => node.id === 'root')!;
  assert.ok(moved.x < root.x && moved.y < root.y, 'real overlap can be repaired in the free negative canvas');
  assert.deepEqual(plan.scene, buildScene(applyVisualBatch(document, [plan.operation]), editor));
  assert.ok(!plan.scene.diagnostics.some(item => item.code === 'layout-overlap' && item.objectIds?.includes(id)));
});
