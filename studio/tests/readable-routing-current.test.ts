import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { applyVisualBatch, buildScene, createDocument } from '../src/core/index.ts';
import { refineReadableRoutes } from '../src/core/readableRouting.ts';
import type { Architecture, CanvasDocument, Scene, SceneNode } from '../src/core/types.ts';
import type { RouteRequest, RouteResult, RoutePoint } from '../src/core/orthogonalRouter.ts';

// Current-product oracle. It parses only the public orthogonal paths and keeps
// canonical identities outside the route implementation under test.
const architecture = JSON.parse(readFileSync(new URL('../../docs/evidence/unified-editor-review-v1/routing-audit/residual_cnn/architecture.json', import.meta.url), 'utf8')) as Architecture;
const EPS = .051;
const close = (a: number, b: number) => Math.abs(a - b) < EPS;
function points(path: string): RoutePoint[] {
  let x = 0, y = 0; const result: RoutePoint[] = [];
  for (const [, op, a, b] of path.matchAll(/([MHV])\s*(-?[\d.]+)(?:\s+(-?[\d.]+))?/g)) {
    if (op === 'M') { x = +a; y = +b; } else if (op === 'H') x = +a; else y = +a;
    if (!result.length || !close(x, result.at(-1)!.x) || !close(y, result.at(-1)!.y)) result.push({ x, y });
  }
  return result;
}
function segments(path: string) { const p = points(path); return p.slice(1).map((b, i) => ({ a: p[i], b, vertical: close(p[i].x, b.x) })); }
function pair(first: string, second: string) {
  const crossings = new Set<string>(), contacts = new Set<string>(); let overlap = 0;
  for (const a of segments(first)) for (const b of segments(second)) {
    if (a.vertical === b.vertical) {
      const firstAxis = a.vertical ? a.a.x : a.a.y, secondAxis = b.vertical ? b.a.x : b.a.y;
      if (!close(firstAxis, secondAxis)) continue;
      const axis = a.vertical ? 'y' : 'x';
      const low = Math.max(Math.min(a.a[axis], a.b[axis]), Math.min(b.a[axis], b.b[axis]));
      const high = Math.min(Math.max(a.a[axis], a.b[axis]), Math.max(b.a[axis], b.b[axis]));
      if (high > low + EPS) overlap += high - low; else if (high >= low - EPS) contacts.add(`${a.vertical ? firstAxis : low},${a.vertical ? low : firstAxis}`);
    } else {
      const vertical = a.vertical ? a : b, horizontal = a.vertical ? b : a, x = vertical.a.x, y = horizontal.a.y;
      if (x < Math.min(horizontal.a.x, horizontal.b.x) - EPS || x > Math.max(horizontal.a.x, horizontal.b.x) + EPS || y < Math.min(vertical.a.y, vertical.b.y) - EPS || y > Math.max(vertical.a.y, vertical.b.y) + EPS) continue;
      const strict = x > Math.min(horizontal.a.x, horizontal.b.x) + EPS && x < Math.max(horizontal.a.x, horizontal.b.x) - EPS && y > Math.min(vertical.a.y, vertical.b.y) + EPS && y < Math.max(vertical.a.y, vertical.b.y) - EPS;
      (strict ? crossings : contacts).add(`${x},${y}`);
    }
  }
  return { crossings, contacts, overlap };
}
function sceneAtLevel(): CanvasDocument {
  let document = createDocument(architecture);
  const byId = new Map(architecture.nodes.map(node => [node.id, node]));
  const depth = (id: string): number => { const parent = byId.get(id)?.parentId; return parent ? depth(parent) + 1 : 0; };
  const operations = architecture.nodes.filter(node => node.children.length && node.parentId && depth(node.id) <= 2).map(node => ({ type: 'expand' as const, id: node.id, expanded: true }));
  return applyVisualBatch(document, operations);
}
function requests(scene: Scene): { requests: RouteRequest[]; baseline: RouteResult[] } {
  const result = scene.edges.map(edge => { const path = points(edge.path); return {
    request: { sourceId: edge.sourceId, targetId: edge.targetId, start: path[0], end: path.at(-1)!, preferredPath: edge.path, tensorId: edge.tensorId, canonicalSource: edge.source, canonicalTarget: edge.target, canonicalEdgeIds: edge.canonicalEdgeIds, role: edge.role, appearance: { stroke: edge.stroke, width: edge.width, dashed: edge.dashed, dashPattern: edge.dashPattern } },
    baseline: { path: edge.path, points: path, changed: false, blockedBy: [] },
  }; });
  return { requests: result.map(item => item.request), baseline: result.map(item => item.baseline) };
}
function translatePath(path: string, dx: number, dy: number) {
  return path.replace(/([MHV])\s*(-?[\d.]+)(?:\s+(-?[\d.]+))?/g, (_, op, a, b) => op === 'M' ? `M ${+a + dx} ${+b + dy}` : `${op} ${+a + (op === 'H' ? dx : dy)}`);
}
function mirroredPath(path: string, axis: number) {
  const p = points(path).map(point => ({ x: axis - point.x, y: point.y }));
  return p.map((point, index) => index === 0 ? `M ${point.x} ${point.y}` : p[index - 1].x === point.x ? `V ${point.y}` : `H ${point.x}`).join(' ');
}
function assertPorts(scene: Scene, document: CanvasDocument) {
  const canonical = new Map(document.architecture.edges.map(edge => [edge.id, edge]));
  for (const edge of scene.edges) {
    const pointsForEdge = points(edge.path);
    for (const [nodeId, direction, endpoint] of [[edge.sourceId, 'out', pointsForEdge[0]], [edge.targetId, 'in', pointsForEdge.at(-1)!]] as const) {
      assert.ok(scene.nodes.find(node => node.id === nodeId)?.ports.some(port => port.direction === direction && edge.canonicalEdgeIds.every(id => port.canonicalEdgeIds.includes(id)) && close(port.x, endpoint.x) && close(port.y, endpoint.y)), `${edge.id} endpoint lost its canonical ${direction} port`);
    }
    const fact = canonical.get(edge.id);
    assert.deepEqual(edge.source, fact?.source); assert.deepEqual(edge.target, fact?.target); assert.equal(edge.tensorId, fact?.tensorId); assert.equal(edge.role, fact?.role);
  }
}
function assertNoNewPeers(before: Scene, after: Scene) {
  const beforeById = new Map(before.edges.map(edge => [edge.id, edge])), afterById = new Map(after.edges.map(edge => [edge.id, edge])), ids = [...beforeById.keys()];
  for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
    const first = ids[i], second = ids[j], old = pair(beforeById.get(first)!.path, beforeById.get(second)!.path), next = pair(afterById.get(first)!.path, afterById.get(second)!.path);
    for (const key of ['crossings', 'contacts'] as const) for (const point of next[key]) assert.ok(old[key].has(point), `new peer ${key} ${first}/${second} at ${point}`);
    assert.ok(next.overlap <= old.overlap + EPS, `new peer overlap ${first}/${second}: ${old.overlap} -> ${next.overlap}`);
  }
}
test('current residual frontier reserves an outside ancestor corridor after right move', () => {
  const document = sceneAtLevel(), before = buildScene(document), byId = new Map(architecture.nodes.map(node => [node.id, node]));
  const moved = architecture.nodes.find(node => {
    const parent = node.parentId ? byId.get(node.parentId) : undefined;
    const repeat = parent?.parentId ? byId.get(parent.parentId) : undefined;
    return node.kind === 'Conv2d' && parent?.kind === 'Module' && repeat?.kind === 'Repeat';
  })!;
  const movedDocument = applyVisualBatch(document, [{ type: 'move', ids: [moved.id], dx: 24, dy: 0, scope: 'current-frontier' }]);
  const after = buildScene(movedDocument); assertNoNewPeers(before, after); assertPorts(after, movedDocument);
  const stemId = architecture.nodes.find(node => node.label === 'stem')!.id;
  const addId = architecture.nodes.find(node => {
    const parent = node.parentId ? byId.get(node.parentId) : undefined;
    const repeat = parent?.parentId ? byId.get(parent.parentId) : undefined;
    return node.kind === 'Add' && parent?.kind === 'Module' && repeat?.kind === 'Repeat';
  })!.id;
  const residual = after.edges.find(edge => edge.role === 'residual' && edge.source.nodeId === stemId && edge.target.nodeId === addId)!;
  const dataFromStem = after.edges.find(edge => edge.role === 'data' && edge.source.nodeId === stemId && edge.target.nodeId !== addId)!;
  const dataIntoAdd = after.edges.find(edge => edge.role === 'data' && edge.target.nodeId === addId)!;
  const edgePairs = [[dataFromStem, residual] as const, [dataIntoAdd, residual] as const];
  assert.equal(edgePairs.length, 2); for (const [edge, peer] of edgePairs) { const metric = pair(edge.path, peer.path); assert.equal(metric.crossings.size, 0); assert.equal(metric.overlap, 0); }
  assert.equal(after.diagnostics.some(diagnostic => diagnostic.code === 'layout-route-blocked'), false);
  assert.deepEqual([...after.hiddenEdges, ...after.edges.flatMap(edge => edge.canonicalEdgeIds)].sort(), architecture.edges.map(edge => edge.id).sort());
});
test('current readable routes keep ports and peer geometry under translation and horizontal mirror', () => {
  const document = sceneAtLevel(), scene = buildScene(document), input = requests(scene);
  const shiftedNodes = scene.nodes.map(node => ({ ...node, x: node.x + 1000, y: node.y + 300, ports: node.ports.map(port => ({ ...port, x: port.x + 1000, y: port.y + 300 })) }));
  const shiftedRequests = input.requests.map(request => ({ ...request, start: { x: request.start.x + 1000, y: request.start.y + 300 }, end: { x: request.end.x + 1000, y: request.end.y + 300 }, preferredPath: translatePath(request.preferredPath, 1000, 300) }));
  const shiftedBaseline = input.baseline.map(result => ({ ...result, path: translatePath(result.path, 1000, 300), points: result.points.map(point => ({ x: point.x + 1000, y: point.y + 300 })) }));
  const shifted = refineReadableRoutes(shiftedNodes, shiftedRequests, shiftedBaseline);
  for (const [index, result] of shifted.entries()) { assert.deepEqual(result.points[0], shiftedRequests[index].start); assert.deepEqual(result.points.at(-1), shiftedRequests[index].end); }
  const axis = 1600, mirroredNodes = scene.nodes.map(node => ({ ...node, x: axis - node.x - node.width, ports: node.ports.map(port => ({ ...port, x: axis - port.x })) }));
  const mirroredRequests = input.requests.map(request => ({ ...request, start: { x: axis - request.start.x, y: request.start.y }, end: { x: axis - request.end.x, y: request.end.y }, preferredPath: mirroredPath(request.preferredPath, axis) }));
  const mirroredBaseline = input.baseline.map(result => ({ ...result, path: mirroredPath(result.path, axis), points: result.points.map(point => ({ x: axis - point.x, y: point.y })) }));
  const mirrored = refineReadableRoutes(mirroredNodes, mirroredRequests, mirroredBaseline);
  for (const [index, result] of mirrored.entries()) { assert.deepEqual(result.points[0], mirroredRequests[index].start); assert.deepEqual(result.points.at(-1), mirroredRequests[index].end); }
});

test('source-grounded overview mask gains eight-unit body clearance without changing any peer pair or port', () => {
  const frozen = JSON.parse(readFileSync(new URL('../../docs/evidence/unified-editor-review-v2/routing-before/transformer-level0-base.canvas.json', import.meta.url), 'utf8')) as CanvasDocument;
  const before = JSON.parse(readFileSync(new URL('../../docs/evidence/unified-editor-review-v2/routing-before/transformer-level0-base.scene.json', import.meta.url), 'utf8')) as Scene;
  const bytes = JSON.stringify(frozen), after = buildScene(frozen);
  const sourceId = frozen.architecture.nodes.find(node => node.label === 'target_mask' && node.category === 'input')!.id;
  const edge = after.edges.find(edge => edge.role === 'mask' && edge.sourceId === sourceId)!;
  const original = before.edges.find(item => item.id === edge.id)!;
  const route = points(edge.path), oldRoute = points(original.path), source = after.nodes.find(node => node.id === sourceId)!;
  assert.equal(source.y - oldRoute[1].y, 6, 'the preserved before evidence must exercise the observed six-unit lane');
  assert.ok(source.y - route[1].y >= 8 - EPS, 'source mask lane must clear the body by eight world units');
  for (const node of after.nodes.filter(node => !node.expanded)) {
    for (let index = 1; index < route.length; index++) {
      if (node.id === edge.sourceId && index === 1 || node.id === edge.targetId && index === route.length - 1) continue;
      const a = route[index - 1], b = route[index], vertical = a.x === b.x;
      const overlap = vertical
        ? Math.min(Math.max(a.y, b.y), node.y + node.height) - Math.max(Math.min(a.y, b.y), node.y)
        : Math.min(Math.max(a.x, b.x), node.x + node.width) - Math.max(Math.min(a.x, b.x), node.x);
      if (overlap <= 8) continue;
      const distance = vertical ? Math.min(Math.abs(a.x - node.x), Math.abs(a.x - node.x - node.width))
        : Math.min(Math.abs(a.y - node.y), Math.abs(a.y - node.y - node.height));
      assert.ok(distance >= 8 - EPS, `mask lane runs too close to ${node.label}`);
    }
  }
  assertNoNewPeers(before, after); assertPorts(after, frozen);
  assert.deepEqual([...after.hiddenEdges, ...after.edges.flatMap(edge => edge.canonicalEdgeIds)].sort(), frozen.architecture.edges.map(edge => edge.id).sort());
  assert.equal(JSON.stringify(frozen), bytes);
  const input = requests(before), mirrorAxis = 1800;
  for (const mirrored of [false, true]) {
    const transform = (point: RoutePoint) => ({ x: mirrored ? mirrorAxis - point.x : point.x + 1000, y: point.y - 700 });
    const transformedPath = (value: string) => {
      const route = points(value).map(transform);
      return route.map((point, index) => !index ? `M ${point.x} ${point.y}` : route[index - 1].x === point.x ? `V ${point.y}` : `H ${point.x}`).join(' ');
    };
    const nodes = before.nodes.map(node => ({ ...node,
      x: mirrored ? mirrorAxis - node.x - node.width : node.x + 1000, y: node.y - 700,
      ports: node.ports.map(port => ({ ...port, ...transform(port) })),
    }));
    const request = input.requests.map(request => ({ ...request, start: transform(request.start), end: transform(request.end), preferredPath: transformedPath(request.preferredPath) }));
    const baseline = input.baseline.map(result => ({ ...result, path: transformedPath(result.path), points: result.points.map(transform) }));
    const result = refineReadableRoutes(nodes, request, baseline);
    const observed = result[input.requests.findIndex(request => request.sourceId === sourceId && request.role === 'mask')];
    const movedSource = nodes.find(node => node.id === sourceId)!;
    assert.ok(movedSource.y - observed.points[1].y >= 8 - EPS, 'translated/mirrored mask must retain the clearance improvement');
    const firstScene = { ...before, nodes, edges: before.edges.map(edge => ({ ...edge, path: transformedPath(edge.path) })) };
    const nextScene = { ...firstScene, edges: firstScene.edges.map((edge, index) => ({ ...edge, path: result[index].path })) };
    assertNoNewPeers(firstScene, nextScene); assertPorts(nextScene, frozen);
  }
});
