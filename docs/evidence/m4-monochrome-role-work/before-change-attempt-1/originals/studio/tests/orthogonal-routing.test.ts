import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { applyVisualBatch, buildExportScene, buildScene, createHistory, reduceHistory, renderSvg } from '../src/core/index.ts';
import { prepareMovePreview, previewMoveScene } from '../src/core/movePreview.ts';
import { createOrthogonalRouter } from '../src/core/orthogonalRouter.ts';
import type { CanvasDocument, Scene, SceneNode } from '../src/core/types.ts';

type Point = [number, number];
// Deliberately independent of the product router's parser/intersection helpers.
function pathPoints(path: string): Point[] {
  let x = 0, y = 0;
  return [...path.matchAll(/([MLHV])\s*(-?[\d.]+)(?:\s+(-?[\d.]+))?/g)].map(([, command, first, second]) => {
    if (command === 'M' || command === 'L') { x = Number(first); y = Number(second); }
    else if (command === 'H') x = Number(first); else y = Number(first);
    return [x, y];
  });
}
function intrusions(scene: Scene, includeEndpointBodies = false): { edge: string; node: string }[] {
  const nodes = new Map(scene.nodes.map(node => [node.id, node])), result: { edge: string; node: string }[] = [];
  function parents(id: string) { const ids = new Set<string>(); let parent = nodes.get(id)?.parentId;
    while (parent) { ids.add(parent); parent = nodes.get(parent)?.parentId; } return ids; }
  for (const edge of scene.edges) {
    const excluded = new Set([...(includeEndpointBodies ? [] : [edge.sourceId, edge.targetId]), ...parents(edge.sourceId), ...parents(edge.targetId)]);
    const points = pathPoints(edge.path);
    for (const node of scene.nodes) {
      if (excluded.has(node.id)) continue;
      for (let index = 1; index < points.length; index++) {
        const [ax, ay] = points[index - 1], [bx, by] = points[index], margin = .25;
        const left = node.x + margin, right = node.x + node.width - margin, top = node.y + margin, bottom = node.y + node.height - margin;
        const hit = ax === bx ? ax > left && ax < right && Math.max(Math.min(ay, by), top) < Math.min(Math.max(ay, by), bottom)
          : ay === by && ay > top && ay < bottom && Math.max(Math.min(ax, bx), left) < Math.min(Math.max(ax, bx), right);
        if (hit) { result.push({ edge: edge.id, node: node.id }); break; }
      }
    }
  }
  return result;
}
function endpoints(scene: Scene) {
  for (const edge of scene.edges) {
    const points = pathPoints(edge.path);
    for (const [id, direction, endpoint] of [[edge.sourceId, 'out', points[0]], [edge.targetId, 'in', points.at(-1)!]] as const) {
      const ports = scene.nodes.find(node => node.id === id)!.ports.filter(port => port.direction === direction && port.canonicalEdgeIds.some(edgeId => edge.canonicalEdgeIds.includes(edgeId)));
      assert.ok(ports.some(port => Math.abs(port.x - endpoint[0]) <= .15 && Math.abs(port.y - endpoint[1]) <= .15), `${edge.id} detached ${direction} endpoint`);
    }
    for (let index = 1; index < points.length; index++) assert.ok(points[index - 1][0] === points[index][0] || points[index - 1][1] === points[index][1]);
    for (const [x, y] of points) assert.ok(x >= scene.bounds.x && y >= scene.bounds.y && x <= scene.bounds.x + scene.bounds.width && y <= scene.bounds.y + scene.bounds.height, `${edge.id} path clipped by Scene bounds`);
  }
}
function node(id: string, x: number, y: number, width = 20, height = 20, parentId?: string): SceneNode {
  return { id, x, y, width, height, parentId, localX: x, localY: y, label: id, subtitle: '', headerHeight: 20,
    kind: 'Linear', category: 'linear', fill: '#ffffff', stroke: '#000000', glyph: 'operator', expanded: false,
    expandable: false, pinned: false, evidence: 'source', ports: [] };
}
function gold(caseId: string): CanvasDocument {
  return JSON.parse(readFileSync(new URL(`../../docs/evidence/browser-visual-matrix-boundary-final/captures/${caseId}/canvas.json`, import.meta.url), 'utf8')) as CanvasDocument;
}
const frontierCases = [
  'mlp-level0-paper-180', 'mlp-level1-paper-180', 'residual_cnn-level0-paper-180', 'residual_cnn-level1-paper-180', 'residual_cnn-level2-paper-180',
  'transformer-level0-paper-180', 'transformer-level1-paper-180', 'transformer-level2-paper-180', 'transformer-level3-paper-180',
];

test('clear preferred orthogonal paths remain byte-identical and endpoint data stays immutable', () => {
  const nodes = [node('a', 0, 0), node('b', 100, 100), node('c', 500, 50)], before = JSON.stringify(nodes);
  const route = createOrthogonalRouter(nodes), preferredPath = 'M 10 20 V 60 H 110 V 100';
  assert.deepEqual(route({ sourceId: 'a', targetId: 'b', start: { x: 10, y: 20 }, end: { x: 110, y: 100 }, preferredPath }),
    { path: preferredPath, points: [{ x: 10, y: 20 }, { x: 10, y: 60 }, { x: 110, y: 60 }, { x: 110, y: 100 }], changed: false, blockedBy: [] });
  assert.equal(JSON.stringify(nodes), before);
});

test('independent broken-path counterexample detects unrelated intrusion and repaired route keeps endpoints', () => {
  const nodes = [node('a', 0, 0), node('b', 100, 100), node('c', 50, 40, 40, 40)];
  const request = { sourceId: 'a', targetId: 'b', start: { x: 10, y: 20 }, end: { x: 110, y: 100 }, preferredPath: 'M 10 20 V 60 H 110 V 100' };
  const fake = { nodes, edges: [{ id: 'crossing', sourceId: 'a', targetId: 'b', path: request.preferredPath }] } as unknown as Scene;
  assert.deepEqual(intrusions(fake), [{ edge: 'crossing', node: 'c' }]);
  const result = createOrthogonalRouter(nodes)(request);
  assert.equal(result.changed, true); assert.deepEqual(result.blockedBy, []);
  fake.edges[0].path = result.path; assert.deepEqual(intrusions(fake), []);
  assert.deepEqual(pathPoints(result.path)[0], [10, 20]); assert.deepEqual(pathPoints(result.path).at(-1), [110, 100]);
});

test('ancestor frame passage is valid; unrelated frame interiors remain obstacles', () => {
  const route = createOrthogonalRouter([node('frame', -10, -10, 140, 140), node('a', 0, 0, 20, 20, 'frame'), node('b', 100, 100, 20, 20, 'frame')]);
  assert.equal(route({ sourceId: 'a', targetId: 'b', start: { x: 10, y: 20 }, end: { x: 110, y: 100 }, preferredPath: 'M 10 20 V 60 H 110 V 100' }).changed, false);
});

test('preferred route re-entry into an endpoint body is repaired, not mistaken for a clear unrelated-body path', () => {
  const nodes = [node('a', 0, 0), node('b', 100, 100)];
  const request = { sourceId: 'a', targetId: 'b', start: { x: 10, y: 20 }, end: { x: 110, y: 100 }, preferredPath: 'M 10 20 V 10 H 110 V 100' };
  const scene = { nodes, edges: [{ id: 'reentry', sourceId: 'a', targetId: 'b', path: request.preferredPath }] } as unknown as Scene;
  assert.deepEqual(intrusions(scene), []); assert.deepEqual(intrusions(scene, true), [{ edge: 'reentry', node: 'a' }]);
  const result = createOrthogonalRouter(nodes)(request); assert.equal(result.changed, true);
  scene.edges[0].path = result.path; assert.deepEqual(intrusions(scene, true), []);
});

test('overlap covering an endpoint is reported explicitly rather than invented as a clear route', () => {
  const route = createOrthogonalRouter([node('a', 0, 0), node('b', 100, 100), node('covering', 0, 15, 20, 30)]);
  const result = route({ sourceId: 'a', targetId: 'b', start: { x: 10, y: 20 }, end: { x: 110, y: 100 }, preferredPath: 'M 10 20 V 60 H 110 V 100' });
  assert.equal(result.changed, false); assert.deepEqual(result.blockedBy, ['covering']); assert.deepEqual(route.overlaps, [{ first: 'a', second: 'covering' }]);
});

test('blocked ancestor headers retain arbitrary canonical IDs without synthetic suffix decoding', () => {
  const frame = { ...node('container#header', -10, -10, 140, 140), expanded: true, expandable: true };
  const route = createOrthogonalRouter([frame, node('a', 0, 0, 20, 20, frame.id), node('b', 100, 100, 20, 20, frame.id)]);
  const preferredPath = 'M 10 0 V -5 H 110 V 100';
  const result = route({ sourceId: 'a', targetId: 'b', start: { x: 10, y: 0 }, end: { x: 110, y: 100 }, preferredPath });
  assert.deepEqual(result.blockedBy, [frame.id]); assert.equal(result.path, preferredPath);
  assert.deepEqual(route.headerOverlaps, [{ node: 'a', ancestor: frame.id }]);
});

test('all nine historical source-bound golden frontiers rerender without unrelated-body intrusions', () => {
  for (const caseId of frontierCases) {
    const document = gold(caseId), original = JSON.stringify(document), scene = buildScene(document);
    assert.deepEqual(intrusions(scene, true), [], caseId); endpoints(scene);
    assert.ok(!scene.diagnostics.some(diagnostic => diagnostic.message.includes('routing conflict')), caseId);
    assert.equal(JSON.stringify(document), original);
    assert.deepEqual(scene.sourceFacts.map(fact => fact.id).sort(), document.architecture.nodes.map(node => node.id).sort());
  }
});

test('detail boundary stubs reuse obstacle routing across all visible expanded golden containers', () => {
  for (const caseId of frontierCases) {
    const document = gold(caseId);
    for (const node of buildScene(document).nodes.filter(node => node.expanded && node.expandable)) {
      const scene = buildExportScene(document, { nodeId: node.id });
      assert.deepEqual(intrusions(scene, true), [], `${caseId}:${node.id}`); endpoints(scene);
      assert.ok(!scene.diagnostics.some(diagnostic => diagnostic.message.includes('Detail edge') && diagnostic.message.includes('routing conflict')), `${caseId}:${node.id}`);
      const ids = [...scene.exportScope!.internalEdgeIds, ...scene.exportScope!.boundaryEdges.map(edge => edge.edgeId), ...scene.exportScope!.omittedEdgeIds];
      assert.deepEqual(ids.sort(), document.architecture.edges.map(edge => edge.id).sort());
    }
  }
});

test('four-direction moves preserve semantic identity, history, exact preview/guarded Scene and routed SVG', () => {
  const document = gold('mlp-level1-paper-180'), id = 'call:instance:model.MLP.network.0';
  for (const [dx, dy] of [[-180, 0], [180, 0], [0, -80], [0, 25]]) {
    const session = prepareMovePreview(document, [id]), preview = previewMoveScene(session, dx, dy);
    const history = reduceHistory(createHistory(document), { type: 'apply', baseRevision: document.revision, operations: [{ type: 'move', ids: [id], dx, dy }] });
    const committed = buildScene(history.document);
    assert.deepEqual(preview, committed); assert.equal(renderSvg(preview), renderSvg(committed)); endpoints(committed);
    assert.deepEqual(history.document.architecture, document.architecture);
    const undo = reduceHistory(history, { type: 'undo' }), redo = reduceHistory(undo, { type: 'redo' });
    assert.deepEqual(undo.document.layout, document.layout); assert.deepEqual(redo.document.layout, history.document.layout);
  }
});

test('intentional overlapping manual objects keep anchors and publish explicit overlap/routing diagnostics', () => {
  const document = gold('mlp-level1-paper-180');
  const moved = applyVisualBatch(document, [{ type: 'move', ids: ['call:instance:model.MLP.network.0'], dx: 0, dy: 80 }]);
  const scene = buildScene(moved);
  assert.equal(moved.layout['call:instance:model.MLP.network.0'].y, document.layout['call:instance:model.MLP.network.0'].y + 80);
  assert.ok(scene.diagnostics.some(diagnostic => diagnostic.message.includes('overlap') && diagnostic.message.includes('manual anchors')));
  assert.ok(scene.diagnostics.some(diagnostic => diagnostic.message.includes('routing conflict')));
  assert.ok(scene.diagnostics.some(diagnostic => diagnostic.code === 'layout-overlap'));
  const blocked = scene.diagnostics.filter(diagnostic => diagnostic.code === 'layout-route-blocked');
  assert.ok(blocked.length > 0);
  for (const diagnostic of blocked) {
    assert.ok(scene.edges.some(edge => edge.id === diagnostic.edgeId));
    assert.ok(diagnostic.objectIds?.length);
    assert.ok(diagnostic.objectIds!.every(id => scene.nodes.some(node => node.id === id)));
  }
  assert.ok(intrusions(scene, true).length > 0); // Honest endpoint-body conflict, not a false clear-route claim.
});

test('manual upward move into expanded ancestor header keeps the coordinate and reports the conflict', () => {
  const document = gold('mlp-level1-paper-180'), id = 'call:instance:model.MLP.network.0';
  const moved = applyVisualBatch(document, [{ type: 'move', ids: [id], dx: 0, dy: -32 }]);
  assert.equal(moved.layout[id].y, document.layout[id].y - 32);
  const scene = buildScene(moved);
  const header = scene.diagnostics.find(diagnostic => diagnostic.code === 'layout-header-overlap' && diagnostic.objectIds?.[0] === id);
  assert.ok(header); assert.equal(header.objectIds![1], scene.nodes.find(node => node.id === id)!.parentId);
  assert.ok(header.message.includes(id) && header.message.includes('header of its expanded ancestor'));
});
