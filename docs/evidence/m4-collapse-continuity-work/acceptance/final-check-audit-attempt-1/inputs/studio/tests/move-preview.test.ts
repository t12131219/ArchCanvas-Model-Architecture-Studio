import test from 'node:test';
import assert from 'node:assert/strict';
import { applyVisualBatch, buildScene, createDocument, createHistory, reduceHistory, renderSvg, RevisionConflict, validateDocument } from '../src/core/index.ts';
import { prepareMovePreview, previewMoveScene } from '../src/core/movePreview.ts';
import type { MovePreviewSession } from '../src/core/movePreview.ts';
import type { Architecture, ArchitectureNode, CanvasDocument } from '../src/core/index.ts';

// Independent hierarchy/routing facts, not captured scene or preview output.
function architecture(): Architecture {
  const node = (id: string, category: string, parentId?: string, children: string[] = []): ArchitectureNode => ({
    id, label: id, kind: category, category, parentId, children, parameters: {}, evidence: 'source',
    ports: [{ id: 'in', name: 'input', direction: 'in', role: 'data', ordinal: 0 }, { id: 'out', name: 'output', direction: 'out', role: 'data', ordinal: 0 }],
  });
  return {
    schemaVersion: 1, id: 'architecture:preview-oracle', label: 'Source-bound move oracle', entry: 'model:Model',
    sourceDigest: 'preview-source', irDigest: 'preview-ir', sources: [], diagnostics: [],
    nodes: [node('root', 'container', undefined, ['input', 'container', 'output']), node('input', 'input', 'root'),
      node('container', 'container', 'root', ['linear', 'activation']), node('linear', 'linear', 'container'),
      node('activation', 'activation', 'container'), node('output', 'output', 'root')],
    edges: [
      { id: 'entry', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'linear', portId: 'in' }, tensorId: 'input-tensor', role: 'data' },
      { id: 'internal', source: { nodeId: 'linear', portId: 'out' }, target: { nodeId: 'activation', portId: 'in' }, tensorId: 'linear-tensor', role: 'data' },
      { id: 'exit', source: { nodeId: 'activation', portId: 'out' }, target: { nodeId: 'output', portId: 'in' }, tensorId: 'activation-tensor', role: 'data' },
      { id: 'bypass', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'activation', portId: 'in' }, tensorId: 'input-tensor', role: 'residual' },
    ],
  };
}
function expanded(): CanvasDocument { return applyVisualBatch(createDocument(architecture()), [{ type: 'expand', id: 'container', expanded: true }]); }
function equivalent(document: CanvasDocument, ids: string[], dx: number, dy: number) {
  const original = JSON.stringify(document), session = prepareMovePreview(document, ids);
  const preview = previewMoveScene(session, dx, dy), committed = buildScene(applyVisualBatch(document, [{ type: 'move', ids, dx, dy }]));
  assert.deepEqual(preview, committed);
  assert.equal(renderSvg(preview, { interactive: true }), renderSvg(committed, { interactive: true }));
  assert.equal(JSON.stringify(document), original);
  return preview;
}

test('preview equals complete guarded scene/SVG for container resizing, negative/manual geometry and repeated frames', () => {
  let document = expanded();
  document = applyVisualBatch(document, [
    { type: 'move', ids: ['linear'], dx: 11, dy: -9 },
    { type: 'alias', id: 'activation', label: '长名称保留手动位置与完整对象关系' },
    { type: 'nodeStyle', id: 'linear', style: { fill: '#abcdef' } },
    { type: 'edgeStyle', id: 'bypass', style: { width: 3, dashed: true } },
    { type: 'annotation', annotation: { id: 'note', text: 'An unchanged explanatory note', x: -20, y: 100 } },
  ]);
  for (const ids of [['linear'], ['activation'], ['container'], ['root'], ['linear', 'output']]) {
    for (const [dx, dy] of [[0, 0], [48, 120], [-360, -140], [12.25, 3.75]]) equivalent(document, ids, dx, dy);
  }
  const session = prepareMovePreview(document, ['linear']);
  assert.deepEqual(previewMoveScene(session, 12, 8), previewMoveScene(session, 12, 8));
  previewMoveScene(session, -24, 40);
  assert.deepEqual(previewMoveScene(session, 12, 8), previewMoveScene(session, 12, 8));
});

test('selected parent and child move exactly once; pinned descendants protect ancestor subtree', () => {
  let document = expanded();
  const before = buildScene(document).nodes.find(node => node.id === 'linear')!;
  const after = equivalent(document, ['container', 'linear', 'linear'], 24, 32).nodes.find(node => node.id === 'linear')!;
  assert.equal(after.x - before.x, 24); assert.equal(after.y - before.y, 32);
  document = applyVisualBatch(document, [{ type: 'pin', ids: ['linear'], pinned: true }]);
  const pinned = buildScene(document).nodes.find(node => node.id === 'linear');
  assert.deepEqual(equivalent(document, ['container', 'linear'], 80, 56).nodes.find(node => node.id === 'linear'), pinned);
  // The guarded move intentionally treats even a blocked selected ancestor as coverage.
  equivalent(document, ['container', 'activation'], 24, 32);
  equivalent(document, ['activation'], 24, 32);
});

test('sparse visible layout materializes once and hidden layout uses the established source contract', () => {
  const document = expanded(); document.layout = {};
  equivalent(document, ['linear'], 20, 12);
  const hidden = createDocument(architecture());
  assert.throws(() => prepareMovePreview(hidden, ['linear']), /hidden and has no established layout/);
  assert.throws(() => applyVisualBatch(hidden, [{ type: 'move', ids: ['linear'], dx: 4, dy: 4 }]), /hidden and has no established layout/);
  hidden.layout.linear = { x: 15, y: 25 };
  equivalent(hidden, ['linear'], 4, 4);
  equivalent(hidden, ['container'], 4, 4);
});

test('preview leaves history/frontiers/source untouched, commit updates snapshots and supports one undo/redo', () => {
  let document = expanded();
  document = applyVisualBatch(document, [{ type: 'expand', id: 'container', expanded: false }, { type: 'expand', id: 'container', expanded: true }]);
  let history = createHistory(document);
  const bytes = JSON.stringify(history), session = prepareMovePreview(history.document, ['linear']);
  for (let i = 1; i <= 10; i++) previewMoveScene(session, i * 4, i * 8);
  assert.equal(JSON.stringify(history), bytes);
  const move = { type: 'move' as const, ids: ['linear'], dx: 40, dy: 80 };
  const next = reduceHistory(history, { type: 'apply', operations: [move], baseRevision: session.baseRevision });
  assert.equal(next.past.length, 1); assert.equal(next.document.revision, history.document.revision + 1);
  for (const [frontier, layout] of Object.entries(document.layoutByFrontier)) if (layout.linear) {
    assert.equal(next.document.layoutByFrontier[frontier].linear.x, layout.linear.x + 40);
    assert.equal(next.document.layoutByFrontier[frontier].linear.y, layout.linear.y + 80);
  }
  assert.deepEqual(next.document.architecture, document.architecture);
  const undone = reduceHistory(next, { type: 'undo' });
  assert.deepEqual(undone.document.layout, document.layout);
  const redone = reduceHistory(undone, { type: 'redo' });
  assert.deepEqual(redone.document.layout, next.document.layout);
  assert.throws(() => reduceHistory(next, { type: 'apply', operations: [move], baseRevision: session.baseRevision }), RevisionConflict);
  validateDocument(next.document);
});

test('prepared snapshot isolates later caller mutation and returned scene cannot corrupt frozen semantic references', () => {
  const document = expanded(), session = prepareMovePreview(document, ['linear']);
  const scene = previewMoveScene(session, 16, 8), expected = structuredClone(scene);
  document.layout.linear.x += 400;
  document.architecture.nodes.find(node => node.id === 'linear')!.parameters.newValue = 123;
  document.pageSpec.background = '#000000';
  assert.deepEqual(previewMoveScene(session, 16, 8), expected);
  assert.throws(() => { scene.pageSpec.background = '#000000'; }, TypeError);
  assert.throws(() => { scene.edges[0].source.portId = 'other'; }, TypeError);
  scene.nodes[0].x += 20;
  assert.deepEqual(previewMoveScene(session, 16, 8), expected);
});

test('preview rejects forged sessions, invalid selection/coordinates and corrupted document before showing geometry', () => {
  const document = expanded();
  assert.throws(() => prepareMovePreview(document, ['unknown']), /unknown object/);
  assert.throws(() => prepareMovePreview(document, 'linear' as never), /expected array/);
  const session = prepareMovePreview(document, ['linear']);
  assert.throws(() => previewMoveScene(session, Infinity, 2), /finite/);
  assert.throws(() => previewMoveScene(session, 2, NaN), /finite/);
  assert.throws(() => previewMoveScene({ ...session } as MovePreviewSession, 2, 2), /unknown gesture snapshot/);
  document.layout.linear.x = NaN;
  assert.throws(() => prepareMovePreview(document, ['linear']), /finite/);
});
