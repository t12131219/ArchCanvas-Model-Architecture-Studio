import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const runtime = process.env.ARCHCANVAS_PREVIEW_TEST_RUNTIME ||
  fileURLToPath(new URL('../public/preview/yworks_edge_router_lab/', import.meta.url));
const context = vm.createContext({ performance });
for (const name of ['router.js', 'physical-ports.js', 'junction-markers.js', 'route-labels.js',
  'source-contracts.js', 'semantic-constraints.js', 'graph-engine.js', 'recursive-graph.js'])
  vm.runInContext(fs.readFileSync(path.join(runtime, name), 'utf8'), context, { filename: name });
const C = context.SummaryConstraints, E = context.SummaryEngine, F = context.SummaryRecursive, R = context.EdgeRouterLabRouting;
type Point = { x: number; y: number };
const points = (values: number[][]): Point[] => values.map(([x, y]) => ({ x, y }));
const plain = (value: any) => JSON.parse(JSON.stringify(value));
const node = (id: string, x: number, y: number, w: number, h: number, parent: string | null = null, expanded = false) =>
  ({ id, x, y, w, h, parent, expanded, routingObstacle: true, base: [x, y], labelObstacles: [], html: '' });
function fixture(mirrorX = false, mirrorY = false, turn = false) {
  const transform = ({ x, y }: Point) => {
    if (mirrorX) x = -x; if (mirrorY) y = -y; if (turn) [x, y] = [-y, x];
    return { x: x + 500, y: y + 500 };
  };
  const nodes = [node('alpha', 50, 300, 50, 30), node('beta', 50, 200, 50, 30, 'scope'),
    node('collector', 50, 0, 50, 60), node('scope', 40, 190, 70, 50, null, true)].map(n => {
    const corners = [transform({ x: n.x, y: n.y }), transform({ x: n.x + n.w, y: n.y + n.h })];
    const x = Math.min(...corners.map(p => p.x)), y = Math.min(...corners.map(p => p.y));
    return { ...n, x, y, w: Math.max(...corners.map(p => p.x)) - x, h: Math.max(...corners.map(p => p.y)) - y, base: [x, y] };
  });
  const side = (original: string) => {
    const normals: Record<string, Point> = { left: { x: -1, y: 0 }, right: { x: 1, y: 0 }, top: { x: 0, y: -1 }, bottom: { x: 0, y: 1 } };
    const zero = transform({ x: 0, y: 0 }), vector = transform(normals[original]);
    return vector.x < zero.x ? 'left' : vector.x > zero.x ? 'right' : vector.y < zero.y ? 'top' : 'bottom';
  };
  const port = (owner: string, originalSide: string, point: Point) => {
    const n = nodes.find(n => n.id === owner)!, s = side(originalSide);
    return { side: s, fraction: ['left', 'right'].includes(s) ? (point.y - n.y) / n.h : (point.x - n.x) / n.w, inward: false };
  };
  const edge = (id: string, source: string, slot: number, raw: number[][]): any => {
    const route = points(raw).map(transform);
    return { id, source, target: 'collector', arrow: 'target', style: 'orthogonal', route, waypoints: [],
      fixedSource: port(source, 'left', route[0]), fixedTarget: port('collector', 'left', route.at(-1)!),
      binding: { wire_identity: [source, 'value'], src: source + ':value', dst: 'collector:slot[' + slot + ']' },
      portPolicy: Object.fromEntries(['source', 'target'].map(which => [which,
        { mode: 'fixed', shape: 'rectangle', spacing: 12, gates: [], sharedStem: null }])) };
  };
  const candidate = edge('second-slot', 'beta', 1, [[50, 215], [46, 215], [46, 56], [40, 56], [40, 42], [50, 42]]);
  const peer = edge('first-slot', 'alpha', 0, [[50, 315], [34, 315], [34, 30], [50, 30]]);
  peer.waypoints = points([[34, 200], [34, 100]]).map(transform);
  const graph = C.initialize({ nodes, edges: [candidate, peer], canvas: [1000, 1000], junctionMarkers: [], attachments: [], routeLabels: [] });
  for (const e of graph.edges) { e.contract.enforcePortApproach = true; e.contract.minimumTerminal = 9; }
  const gatePoint = transform({ x: 46, y: 190 }), gatePort = port('scope', 'top', gatePoint);
  const gate = { frame: 'scope', side: gatePort.side, fraction: gatePort.fraction, direction: 'exit', order: 0 };
  candidate.contract.gates = [gate]; candidate.portPolicy.source.gates = plain([gate]);
  return { graph, candidate, peer, transform };
}
function authority(graph: any) {
  return JSON.stringify(graph.edges.map((e: any) => [e.id, e.source, e.target, e.binding, e.contract,
    e.fixedSource, e.fixedTarget, e.portPolicy, e.waypoints]));
}
function assertValid(graph: any) {
  const result = E.validateView(graph);
  assert.equal(result.source.ok, true, JSON.stringify(result.source));
  assert.equal(result.layout.ok, true, JSON.stringify(result.layout));
  assert.deepEqual(plain(result.edges.filter(([, check]: any) => !check.ok)), []);
}
function closeLength(a: any, b: any) {
  let total = 0;
  for (let i = 2; i < a.route.length - 1; i++) for (let j = 2; j < b.route.length - 1; j++) {
    const p = a.route[i - 1], q = a.route[i], u = b.route[j - 1], v = b.route[j];
    const vertical = Math.abs(p.x - q.x) < 1e-5, horizontal = Math.abs(p.y - q.y) < 1e-5;
    if ((!vertical && !horizontal) || (vertical ? Math.abs(u.x - v.x) >= 1e-5 : Math.abs(u.y - v.y) >= 1e-5)) continue;
    const axis = vertical ? 'x' : 'y', along = vertical ? 'y' : 'x';
    if (Math.abs(p[axis] - u[axis]) >= 10 - 1e-5) continue;
    total += Math.max(0, Math.min(Math.max(p[along], q[along]), Math.max(u[along], v[along]))
      - Math.max(Math.min(p[along], q[along]), Math.min(u[along], v[along])));
  }
  return total;
}
const length = (e: any) => e.route.slice(1).reduce((sum: number, p: Point, i: number) => sum + R.dist(e.route[i], p), 0);

for (const mirrorX of [false, true]) for (const mirrorY of [false, true]) for (const turn of [false, true]) {
  test(`neighboring value slots shorten a crowded terminal band with fixed ports and source gate (${mirrorX}, ${mirrorY}, ${turn})`, () => {
    const { graph, candidate, peer } = fixture(mirrorX, mirrorY, turn);
    assertValid(graph); assert.equal(closeLength(candidate, peer), 14);
    const source = authority(graph), beforeLength = length(candidate), beforePoints = candidate.route.length, peerRoute = JSON.stringify(peer.route);
    assert.equal(F.route(graph, { preserve: true }).failed, 0); assertValid(graph);
    assert.ok(closeLength(candidate, peer) <= 2 + 1e-5, 'the adjacent fixed slot licenses a shorter free band');
    assert.equal(candidate.route.length, beforePoints, 'no extra bend is created');
    assert.equal(length(candidate), beforeLength, 'the shorter band does not lengthen the path');
    assert.equal(JSON.stringify(peer.route), peerRoute, 'the manually positioned peer stays exact');
    assert.equal(authority(graph), source, 'independent slot values, fixed ports, ordered knots and the source gate stay exact');
    assert.equal(R.wireContacts(candidate.route, peer.route).length, 0);
    const end = candidate.route.at(-1), previous = candidate.route.at(-2);
    assert.ok(R.dist(end, previous) >= candidate.contract.minimumTerminal);
    const settled = JSON.stringify(graph.edges), clone = E.clone(graph);
    assert.equal(F.route(clone, { preserve: true }).failed, 0);
    assert.equal(JSON.stringify(clone.edges), settled, 'a cloned settled frontier retains the same lanes');
  });
}

test('an explicit ordered knot on the short terminal band prevents automatic sliding', () => {
  const { graph, candidate, transform } = fixture();
  candidate.waypoints = points([[46, 56], [40, 56]]).map(transform);
  assertValid(graph); const source = authority(graph);
  assert.equal(F.route(graph, { preserve: true }).failed, 0); assertValid(graph);
  assert.equal(authority(graph), source);
  for (const point of candidate.waypoints) assert.ok(candidate.route.some((p: Point) => R.dist(p, point) < 1e-5));
});
