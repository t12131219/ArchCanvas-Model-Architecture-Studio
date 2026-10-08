import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { applyVisualBatch, buildScene, createHistory, reduceHistory } from '../src/core/index.ts';
import { routeLaneConflicts, sharedRoutePresentation } from '../src/core/routeLaneConflicts.ts';
import { refineReadableRoutes, READABLE_COMPONENT_BUDGET } from '../src/core/readableRouting.ts';
import type { CanvasDocument, Scene, SceneEdge } from '../src/core/types.ts';
import type { RoutePoint } from '../src/core/orthogonalRouter.ts';

// Independent public-path oracle. It does not call the router's pair metric or
// lane classifier, and counts collinear occupancy regardless of edge role.
function points(path: string): RoutePoint[] {
  let x = 0, y = 0; const result: RoutePoint[] = [];
  for (const [, op, a, b] of path.matchAll(/([MHV])\s*(-?[\d.]+)(?:\s+(-?[\d.]+))?/g)) {
    if (op === 'M') { x = +a; y = +b; } else if (op === 'H') x = +a; else y = +a;
    result.push({ x, y });
  }
  return result;
}
function pair(first: string, second: string) {
  const a = points(first), b = points(second), crossings = new Set<string>(); let overlap = 0;
  for (let i = 1; i < a.length; i++) for (let j = 1; j < b.length; j++) {
    const p = a[i - 1], q = a[i], r = b[j - 1], s = b[j], vertical = p.x === q.x, otherVertical = r.x === s.x;
    if (vertical === otherVertical) {
      if (vertical ? p.x !== r.x : p.y !== r.y) continue;
      const axis = vertical ? 'y' : 'x';
      overlap += Math.max(0, Math.min(Math.max(p[axis], q[axis]), Math.max(r[axis], s[axis])) - Math.max(Math.min(p[axis], q[axis]), Math.min(r[axis], s[axis])));
    } else {
      const [v, w, h, k] = vertical ? [p, q, r, s] : [r, s, p, q];
      if (v.x > Math.min(h.x, k.x) && v.x < Math.max(h.x, k.x) && h.y > Math.min(v.y, w.y) && h.y < Math.max(v.y, w.y)) crossings.add(`${v.x},${h.y}`);
    }
  }
  return { overlap, crossings };
}
const lane = (id: string, path: string, extra: Partial<SceneEdge> = {}): SceneEdge => ({ id, sourceId: 'origin', targetId: id,
  source: { nodeId: 'canonical-origin', portId: 'out' }, target: { nodeId: id, portId: 'in' }, canonicalEdgeIds: [id],
  tensorId: 'tensor', role: 'data', path, stroke: '#335577', width: 1.5, dashed: false, label: '', labelX: 0, labelY: 0, ...extra });

test('a genuine source/style fan-out is drawn once with a literal junction and complete canonical paths retained', () => {
  const edges = [lane('a', 'M 0 0 V 20 H 30 V 70 H 80'), lane('b', 'M 0 0 V 20 H 30 V 100 H 80')], bytes = JSON.stringify(edges);
  assert.equal(pair(edges[0].path, edges[1].path).overlap, 100, 'fixture really contains an overdrawn trunk');
  assert.deepEqual(routeLaneConflicts(edges), []);
  const presentation = sharedRoutePresentation(edges);
  assert.equal(presentation.paths.get('a'), edges[0].path);
  assert.equal(presentation.paths.get('b'), 'M 30 70 V 100 H 80');
  assert.equal(presentation.prefixLengths.get('b'), 100);
  assert.deepEqual(presentation.junctions, [{ x: 30, y: 70, edgeIds: ['a', 'b'], stroke: '#335577', width: 1.5 }]);
  assert.equal(pair(presentation.paths.get('a')!, presentation.paths.get('b')!).overlap, 0);
  assert.equal(JSON.stringify(edges), bytes);
});

test('tensor labels alone, distinct canonical ports, role/style changes and later rejoining never hide an ambiguous lane', () => {
  const first = lane('a', 'M 0 0 V 20 H 30 V 70 H 80');
  for (const extra of [{ source: { nodeId: 'other', portId: 'out' } }, { source: { nodeId: 'canonical-origin', portId: 'other' } },
    { role: 'residual' as const }, { stroke: '#775533' }, { dashed: true }, { width: 2 }]) {
    const second = lane('b', 'M 0 0 V 20 H 30 V 100 H 80', extra);
    assert.equal(routeLaneConflicts([first, second]).length, 1);
    assert.equal(sharedRoutePresentation([first, second]).paths.get('b'), second.path);
  }
  const later = lane('c', 'M 0 0 V 10 H 30 V 100 H 80');
  assert.ok(routeLaneConflicts([first, later])[0].length > 0, 'a later reunion is not a shared prefix');
  assert.ok(routeLaneConflicts([first, lane('duplicate', first.path)])[0].length > 0, 'fully coincident routes have no discernible branch');
});

const evidence = new URL('../../docs/evidence/unified-editor-review-v2/routing-after/', import.meta.url);
function load(name: string) { return JSON.parse(readFileSync(new URL(`${name}.canvas.json`, evidence), 'utf8')) as CanvasDocument; }
function assertFacts(scene: Scene, document: CanvasDocument) {
  for (const edge of scene.edges) {
    const route = points(edge.path);
    for (const [id, direction, endpoint] of [[edge.sourceId, 'out', route[0]], [edge.targetId, 'in', route.at(-1)!]] as const)
      assert.ok(scene.nodes.find(node => node.id === id)?.ports.some(port => port.direction === direction &&
        edge.canonicalEdgeIds.every(edgeId => port.canonicalEdgeIds.includes(edgeId)) && Math.abs(port.x - endpoint.x) < .051 && Math.abs(port.y - endpoint.y) < .051));
    const fact = document.architecture.edges.find(item => item.id === edge.id)!;
    assert.deepEqual(edge.source, fact.source); assert.deepEqual(edge.target, fact.target);
    assert.equal(edge.role, fact.role); assert.equal(edge.tensorId, fact.tensorId);
  }
  assert.deepEqual([...scene.hiddenEdges, ...scene.edges.flatMap(edge => edge.canonicalEdgeIds)].sort(), document.architecture.edges.map(edge => edge.id).sort());
}
function assertNoDistinctOverlays(scene: Scene) {
  for (let i = 0; i < scene.edges.length; i++) for (let j = i + 1; j < scene.edges.length; j++) {
    const a = scene.edges[i], b = scene.edges[j];
    if (a.source.nodeId === b.source.nodeId && a.source.portId === b.source.portId && a.tensorId === b.tensorId && a.role === b.role && a.stroke === b.stroke && a.width === b.width && a.dashed === b.dashed) continue;
    assert.equal(pair(a.path, b.path).overlap, 0, `ambiguous lane ${a.id}/${b.id}`);
  }
  assert.deepEqual(routeLaneConflicts(scene.edges), []);
}

test('the image failure has genuine differently typed overlays; all 41 saved hierarchical/movement scenes now separate them without rewriting facts or anchors', () => {
  const old = JSON.parse(readFileSync(new URL('transformer-level2-base.scene.json', evidence), 'utf8')) as Scene;
  const oldData = old.edges.find(edge => edge.id === 'edge:8')!, oldResidual = old.edges.find(edge => edge.id === 'edge:13')!;
  assert.ok(pair(oldData.path, oldResidual.path).overlap > 200, 'frozen before really exercises the reported image overlap');
  const files = readdirSync(evidence).filter(name => name.endsWith('.canvas.json'));
  assert.equal(files.length, 41);
  for (const file of files) {
    const document = JSON.parse(readFileSync(new URL(file, evidence), 'utf8')) as CanvasDocument, bytes = JSON.stringify(document), scene = buildScene(document);
    assertNoDistinctOverlays(scene); assertFacts(scene, document); assert.equal(JSON.stringify(document), bytes, file);
  }
});

test('deep frontier four-direction movement, persistence and history retain the separated routes and stable visual slots', () => {
  const document = load('transformer-level3-base'), initial = buildScene(document);
  const selected = initial.nodes.find(node => !node.expanded && node.category === 'attention')!;
  const sourceSlots = initial.nodes.find(node => node.label === 'source embedding')!.ports;
  for (const [dx, dy] of [[-24, 0], [24, 0], [0, -24], [0, 24]]) {
    const operation = { type: 'move' as const, ids: [selected.id], dx, dy, scope: 'current-frontier' as const };
    const moved = applyVisualBatch(document, [operation]), scene = buildScene(moved);
    assertNoDistinctOverlays(scene); assertFacts(scene, moved);
    assert.deepEqual(scene.nodes.find(node => node.label === 'source embedding')!.ports, sourceSlots, 'moving the opposite card cannot swap source slots');
    assert.deepEqual(buildScene(JSON.parse(JSON.stringify(moved))), scene);
    const history = reduceHistory(createHistory(document), { type: 'apply', operations: [operation] });
    const undone = reduceHistory(history, { type: 'undo' }), redone = reduceHistory(undone, { type: 'redo' });
    assert.deepEqual(buildScene(undone.document).edges, initial.edges); assert.deepEqual(buildScene(redone.document).edges, scene.edges);
    assert.deepEqual(moved.architecture, document.architecture);
  }
});

test('route work caps are deterministic and oversized batches retain complete canonical endpoint geometry', () => {
  assert.equal(Object.isFrozen(READABLE_COMPONENT_BUDGET), true);
  const document = load('transformer-level3-base'), scene = buildScene(document), edge = scene.edges[0], route = points(edge.path);
  const request = { sourceId: edge.sourceId, targetId: edge.targetId, start: route[0], end: route.at(-1)!, preferredPath: edge.path };
  const baseline = { path: edge.path, points: route, changed: false, blockedBy: [] };
  const tooMany = Array.from({ length: 513 }, () => request), paths = Array.from({ length: 513 }, () => baseline);
  assert.deepEqual(refineReadableRoutes(scene.nodes, tooMany, paths), paths);
});
