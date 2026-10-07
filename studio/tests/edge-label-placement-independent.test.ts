import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
// Only the source-bound M4 capture is frozen here. Current public caption,
// source/port and export invariants also run in atomic-frontier-routing.test.ts.
import { buildScene, buildExportScene, createDocument, createHistory, reduceHistory, renderSvg } from './historical-routing-core.ts';
import type { Architecture, CanvasDocument, Scene, SceneNode } from '../src/core/types.ts';
import { placeEdgeLabels } from '../src/core/edgeLabelPlacement.ts';
import { layoutWarnings } from '../src/layoutWarnings.ts';

const before = new URL('../../docs/evidence/m4-visual-next-current/review/label-before/files/docs/evidence/m4-visual-next-current/review/fresh-source-core/', import.meta.url);
const document = () => JSON.parse(readFileSync(new URL('transformer-level0-paper-180.canvas.json', before), 'utf8')) as CanvasDocument;
const original = () => JSON.parse(readFileSync(new URL('transformer-level0-paper-180.scene.json', before), 'utf8')) as Scene;

// Independent nominal envelope for the SVG's 9-unit plain edge text. The
// production text-placement/outline/intersection helpers are not imported.
function labelBody(label: string, x: number, y: number) {
  return { x: x - 2, y: y - 11, width: [...label].length * 9 + 4, height: 16 };
}
function intersections(body: { x: number; y: number; width: number; height: number }, nodes: SceneNode[]) {
  return nodes.flatMap(node => {
    const rectangles = node.expanded
      ? [{ x: node.x, y: node.y, width: node.width, height: node.headerHeight }]
      : [0, ...(node.repeat ? [3.5, 7] : [])].map(offset => ({ x: node.x + offset, y: node.y + offset, width: node.width, height: node.height }));
    return rectangles.some(other => Math.min(body.x + body.width, other.x + other.width) > Math.max(body.x, other.x)
      && Math.min(body.y + body.height, other.y + other.height) > Math.max(body.y, other.y)) ? [node.id] : [];
  });
}

test('formal Transformer memory caption clears both repeat plates and target card with all model facts fixed', () => {
  const input = document(), inputBytes = JSON.stringify(input), scene = buildScene(input), prior = original();
  const memory = scene.edges.find(edge => edge.role === 'memory' && edge.label)!;
  const oldMemory = prior.edges.find(edge => edge.id === memory.id)!;
  assert.ok(intersections(labelBody(oldMemory.label, oldMemory.labelX, oldMemory.labelY), prior.nodes).length >= 2, 'source-bound pre-fix counterexample must remain present');
  assert.deepEqual(intersections(labelBody(memory.label, memory.labelX, memory.labelY), scene.nodes), [], 'memory caption must not enter a repeat plate, header or target card');
  assert.notDeepEqual([memory.labelX, memory.labelY], [oldMemory.labelX, oldMemory.labelY]);
  assert.deepEqual(JSON.parse(JSON.stringify(scene.nodes)), prior.nodes);
  const withoutPositions = (edges: Scene['edges']) => edges.map(({ labelX: _x, labelY: _y, ...edge }) => edge);
  assert.deepEqual(JSON.parse(JSON.stringify(withoutPositions(scene.edges))), withoutPositions(prior.edges));
  assert.deepEqual(scene.sourceFacts, prior.sourceFacts); assert.deepEqual(scene.hiddenEdges, prior.hiddenEdges);
  assert.equal(scene.sourceDigest, prior.sourceDigest); assert.equal(scene.irDigest, prior.irDigest);
  assert.equal(JSON.stringify(input), inputBytes, 'derived caption placement cannot write layout/model/aliases');
  assert.deepEqual(scene, buildScene(input));
  assert.match(renderSvg(scene), new RegExp(`x="${memory.labelX}" y="${memory.labelY}" font-size="9"`));
});

function node(id: string, x: number, y: number, width: number, height: number, expanded = false): SceneNode {
  return { id, x, y, width, height, localX: x, localY: y, label: id, subtitle: '', headerHeight: 30,
    kind: 'Block', category: 'module', fill: '#fff', stroke: '#000', glyph: 'module', expanded,
    expandable: expanded, pinned: false, evidence: 'source', ports: [] };
}
function edge(id: string, label: string, x: number, y: number, route = 'M 10 80 H 90'): Scene['edges'][number] {
  return { id, label, labelX: x, labelY: y, path: route, sourceId: 'left', targetId: 'right',
    source: { nodeId: 'left', portId: 'out' }, target: { nodeId: 'right', portId: 'in' }, canonicalEdgeIds: [id],
    tensorId: id, role: 'memory', stroke: '#000', width: 1.5, dashed: false };
}

test('general placement leaves a safe caption unchanged in expanded content and ignores empty captions', () => {
  const nodes = [node('frame', 0, 0, 250, 250, true), node('left', 0, 160, 40, 40), node('right', 190, 160, 40, 40)];
  const edges = [edge('safe', '上下文', 60, 105), edge('empty', '', 2, 2)];
  const beforeBytes = JSON.stringify({ nodes, edges }), result = placeEdgeLabels(nodes, edges);
  assert.deepEqual(result.placements.get('safe'), { x: 60, y: 105 });
  assert.equal(result.placements.has('empty'), false); assert.deepEqual(result.diagnostics, []);
  assert.equal(JSON.stringify({ nodes, edges }), beforeBytes);
});

test('independent repeat/header/note blockers relocate captions without changing paths or card coordinates', () => {
  const repeated = { ...node('repeated', 0, 40, 30, 30), repeat: { count: 3, sharing: 'independent' as const } };
  const nodes = [repeated, node('header', 50, 20, 90, 100, true)];
  const edges = [edge('caption', '投影', 33, 60, 'M 25 95 H 90')];
  const notes = [{ id: 'note', x: 33, y: 65, width: 45, height: 30 }];
  const snapshot = JSON.stringify({ nodes, edges, notes });
  const result = placeEdgeLabels(nodes, edges, notes), position = result.placements.get('caption')!;
  assert.notDeepEqual(position, { x: 33, y: 60 });
  const body = labelBody('投影', position.x, position.y);
  assert.deepEqual(intersections(body, nodes), []);
  assert.ok(body.x + body.width <= 33 || body.x >= 78 || body.y + body.height <= 65 || body.y >= 95);
  assert.deepEqual(result.diagnostics, []); assert.equal(JSON.stringify({ nodes, edges, notes }), snapshot);
});

test('two distinct captions keep separate nominal envelopes and avoid an unrelated route', () => {
  const nodes: SceneNode[] = [], edges = [edge('first', 'memory', 45, 65), edge('second', 'mask', 45, 65),
    edge('crossing', '', 0, 0, 'M 30 64 H 130')];
  const result = placeEdgeLabels(nodes, edges), first = result.placements.get('first')!, second = result.placements.get('second')!;
  const a = labelBody('memory', first.x, first.y), b = labelBody('mask', second.x, second.y);
  assert.ok(a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y);
  for (const body of [a, b]) assert.ok(body.y >= 64 || body.y + body.height <= 64 || body.x + body.width <= 30 || body.x >= 130);
  assert.deepEqual(result.diagnostics, []); assert.deepEqual(result, placeEdgeLabels(nodes, edges));
});

test('bounded local placement reports an impossible caption instead of hiding it or moving model objects', () => {
  const nodes = [node('solid', -300, -300, 800, 800)], edges = [edge('crowded', '共享张量', 30, 30)];
  const beforeBytes = JSON.stringify({ nodes, edges }), result = placeEdgeLabels(nodes, edges);
  assert.deepEqual(result.placements.get('crowded'), { x: 30, y: 30 });
  assert.equal(result.diagnostics.length, 1); assert.equal(result.diagnostics[0].code, 'layout-edge-label-blocked');
  assert.equal(result.diagnostics[0].edgeId, 'crowded'); assert.deepEqual(result.diagnostics[0].objectIds, ['solid']);
  const scene = original(); scene.nodes = nodes; scene.edges = edges; scene.diagnostics = result.diagnostics;
  assert.deepEqual(layoutWarnings(scene), ['“对象” → “对象”连线标签缺少足够留白。移动附近对象，或增大间距。']);
  assert.equal(edges[0].label, '共享张量'); assert.equal(JSON.stringify({ nodes, edges }), beforeBytes);
});

test('whole and detail export use the same caption safety after projection while visual history retains canonical facts', () => {
  const input = document(), beforeBytes = JSON.stringify(input);
  assert.deepEqual(buildExportScene(input), buildScene(input));
  const detail = buildExportScene(input, { nodeId: input.expandedIds[0] });
  for (const caption of detail.edges.filter(item => item.label)) {
    const body = labelBody(caption.label, caption.labelX, caption.labelY);
    assert.deepEqual(intersections(body, detail.nodes), []);
    assert.ok(body.x >= detail.bounds.x && body.x + body.width <= detail.bounds.x + detail.bounds.width);
    assert.ok(body.y >= detail.bounds.y && body.y + body.height <= detail.bounds.y + detail.bounds.height);
  }
  const history = reduceHistory(createHistory(input), { type: 'apply', baseRevision: input.revision,
    operations: [{ type: 'move', ids: ['repeat:instance:model.Transformer.encoder'], dx: -20, dy: 15 }] });
  const moved = buildScene(history.document), undo = reduceHistory(history, { type: 'undo' }), redo = reduceHistory(undo, { type: 'redo' });
  assert.deepEqual(undo.document.layout, input.layout); assert.deepEqual(redo.document.layout, history.document.layout);
  assert.deepEqual(history.document.architecture, input.architecture); assert.deepEqual(moved.sourceFacts, buildScene(input).sourceFacts);
  assert.equal(JSON.stringify(input), beforeBytes);
});

test('long source-declared captions remain complete and inside overview/detail bounds even when local placement is blocked', () => {
  const architecture: Architecture = { schemaVersion: 1, id: 'caption-bounds', entry: 'oracle:CaptionBounds', label: 'Caption bounds',
    sourceDigest: 'independent-caption-source', irDigest: 'independent-caption-ir', sources: [], diagnostics: [],
    nodes: [
      { id: 'root', label: 'Root', kind: 'Block', category: 'container', children: ['left', 'right'], parameters: {}, ports: [], evidence: 'source' },
      ...['left', 'right'].map(id => ({ id, parentId: 'root', label: id, kind: 'Linear', category: 'linear', children: [], parameters: {}, evidence: 'source' as const,
        ports: [{ id: 'in', name: 'in', direction: 'in' as const, role: 'data' as const, ordinal: 0 }, { id: 'out', name: 'out', direction: 'out' as const, role: 'data' as const, ordinal: 0 }] })),
    ], edges: [{ id: 'declared-caption', source: { nodeId: 'left', portId: 'out' }, target: { nodeId: 'right', portId: 'in' },
      role: 'data', tensorId: 'unchanged-tensor', label: '跨模块共享张量'.repeat(25) }] };
  const input = createDocument(architecture), beforeBytes = JSON.stringify(input);
  for (const scene of [buildScene(input), buildExportScene(input, { nodeId: 'root' })]) {
    const caption = scene.edges[0], body = labelBody(caption.label, caption.labelX, caption.labelY);
    assert.equal(caption.label, architecture.edges[0].label);
    assert.ok(body.x >= scene.bounds.x && body.x + body.width <= scene.bounds.x + scene.bounds.width);
    assert.ok(body.y >= scene.bounds.y && body.y + body.height <= scene.bounds.y + scene.bounds.height);
  }
  assert.equal(JSON.stringify(input), beforeBytes);
});
