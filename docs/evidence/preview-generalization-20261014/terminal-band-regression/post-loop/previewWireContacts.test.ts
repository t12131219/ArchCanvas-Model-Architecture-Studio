import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const preview = fileURLToPath(new URL('../public/preview/yworks_edge_router_lab/', import.meta.url));
const context = vm.createContext({});
for (const name of ['router.js', 'physical-ports.js', 'junction-markers.js', 'route-labels.js',
  'source-contracts.js', 'semantic-constraints.js', 'graph-engine.js', 'recursive-graph.js'])
  vm.runInContext(fs.readFileSync(path.join(preview, name), 'utf8'), context, { filename: name });
const R = context.EdgeRouterLabRouting, C = context.SummaryConstraints, E = context.SummaryEngine, F = context.SummaryRecursive;
type Point = { x: number; y: number };
const points = (coordinates: number[][]): Point[] => coordinates.map(([x, y]) => ({ x, y }));
const plain = (value: any) => JSON.parse(JSON.stringify(value));
const contactPoints = (a: Point[], b: Point[]) => plain(R.wireContacts(a, b).map((entry: any) => entry.point));

test('one physical internal corner contact is counted once for an unordered pair of routes', () => {
  const a = points([[0, 0], [10, 0], [10, 10]]), b = points([[10, -10], [10, 0], [20, 0]]);
  assert.deepEqual(contactPoints(a, b), [{ x: 10, y: 0 }]);
  for (const first of [a, a.slice().reverse()]) for (const second of [b, b.slice().reverse()]) {
    assert.deepEqual(contactPoints(first, second), [{ x: 10, y: 0 }]);
    assert.deepEqual(contactPoints(second, first), [{ x: 10, y: 0 }]);
  }
});

test('subdividing a route at crossings does not inflate or erase the number of physical contacts', () => {
  const a = points([[0, 0], [40, 0]]), divided = points([[0, 0], [10, 0], [30, 0], [40, 0]]);
  const b = points([[10, -10], [10, 10], [30, 10], [30, -10]]);
  const dividedB = points([[10, -10], [10, 0], [10, 10], [30, 10], [30, 0], [30, -10]]);
  for (const first of [a, divided]) for (const second of [b, dividedB])
    assert.deepEqual(contactPoints(first, second), [{ x: 10, y: 0 }, { x: 30, y: 0 }]);
  assert.deepEqual(plain(R.wireContacts(a, b).map((entry: any) => entry.kind)), ['crossing', 'crossing']);
});

test('rotations, reflections, translation and scale preserve independent contact counts', () => {
  const a = points([[0, 0], [20, 0], [20, 20], [40, 20]]);
  const b = points([[10, -10], [10, 10], [30, 10], [30, 30]]);
  const expected = R.wireContacts(a, b).length;
  assert.equal(expected, 3);
  const cornerA = points([[0, 0], [10, 0], [10, 10]]), cornerB = points([[10, -10], [10, 0], [20, 0]]);
  for (const scale of [.1, 1, 100]) for (const reflection of [-1, 1]) for (const turn of [0, 1, 2, 3]) {
    const transform = ({ x, y }: Point): Point => {
      x *= reflection;
      for (let i = 0; i < turn; i++) [x, y] = [-y, x];
      return { x: x * scale + 371, y: y * scale - 193 };
    };
    assert.equal(R.wireContacts(a.map(transform), b.map(transform)).length, expected,
      JSON.stringify({ scale, reflection, turn }));
    assert.equal(R.wireContacts(cornerA.map(transform), cornerB.map(transform)).length, 1);
  }
});

test('octilinear crossings and coincident diagonal corners are measured geometrically', () => {
  assert.deepEqual(plain(R.wireContacts(points([[0, 0], [20, 20]]), points([[0, 20], [20, 0]]))),
    [{ point: { x: 10, y: 10 }, kind: 'crossing' }]);
  const a = points([[0, 0], [10, 10], [20, 0]]), b = points([[0, 20], [10, 10], [20, 20]]);
  assert.deepEqual(contactPoints(a, b), [{ x: 10, y: 10 }]);
  const collinear = points([[0, 0], [10, 10], [10, 20]]), other = points([[10, 0], [10, 10], [20, 20]]);
  assert.deepEqual(contactPoints(collinear, other), [{ x: 10, y: 10 }]);
});

test('actual terminal coincidences are excluded while terminal-to-interior contacts remain visible', () => {
  assert.deepEqual(contactPoints(points([[0, 0], [10, 0]]), points([[10, 0], [10, 10]])), []);
  assert.deepEqual(contactPoints(points([[0, 0], [10, 0]]), points([[10, -10], [10, 10]])), [{ x: 10, y: 0 }]);
  assert.deepEqual(contactPoints(points([[0, 0], [10, 0], [10, 10]]), points([[10, 0], [20, 0]])), [{ x: 10, y: 0 }]);
  assert.deepEqual(contactPoints(points([[0, 0], [0, 0], [10, 0]]), points([[0, 1], [10, 1]])), []);
  const first = points([[0, 0], [20, 0]]), second = points([[10, 0], [30, 0]]);
  assert.ok(R.overlap(first[0], first[1], second[0], second[1]) > 0);
  assert.deepEqual(contactPoints(first, second), [], 'positive shared runs remain the responsibility of overlap validation');
});

const node = (id: string, x: number, y: number, w: number, h: number) =>
  ({ id, x, y, w, h, parent: null, expanded: false, routingObstacle: true, base: [x, y], labelObstacles: [], html: '' });
const edge = (id: string, source: string, target: string, sourceSide: string, targetSide: string, route: number[][]): any =>
  ({ id, source, target, arrow: 'target', style: 'orthogonal', route: points(route), waypoints: [],
    fixedSource: { side: sourceSide, fraction: .5, inward: false }, fixedTarget: { side: targetSide, fraction: .5, inward: false },
    binding: { wire_identity: [source, 'out'], src: source + ':out', dst: target + ':in' },
    portPolicy: Object.fromEntries(['source', 'target'].map(side => [side,
      { mode: 'fixed', shape: 'rectangle', spacing: 12, gates: [], sharedStem: null }])) });
function synthetic(shared = false) {
  const a = edge('candidate', 'source', 'target', 'right', 'left',
    [[10, 40], [20, 40], [20, 50], [20, 60], [25, 60], [25, 80], [50, 80], [60, 80], [60, 40], [70, 40]]);
  const b = shared ? edge('peer', 'source', 'peer-target', 'right', 'left',
    [[10, 40], [30, 40], [30, 20], [50, 20], [50, 50], [80, 50]])
    : edge('peer', 'peer-source', 'peer-target', 'bottom', 'left', [[50, 20], [50, 50], [80, 50]]);
  const graph = C.initialize({ nodes: [node('source', 0, 35, 10, 10), node('target', 70, 36, 10, 8),
    node('peer-source', 45, 10, 10, 10), node('peer-target', 80, 45, 20, 10), node('local-blocker', 18, 65, 4, 10),
    node('upper-blocker', 24, 42, 2, 4), node('straight-blocker', 40, 35, 5, 10), node('middle-blocker', 35, 55, 5, 10)],
    edges: [a, b], canvas: [200, 150], junctionMarkers: shared
      ? [{ id: 'source-fork', owner: 'source', original: [20, 40], edges: ['candidate', 'peer'], fragments: [] }] : [],
    attachments: [], routeLabels: [] });
  for (const value of graph.edges) { value.contract.enforcePortApproach = true; value.contract.minimumTerminal = 9; }
  return graph;
}
function assertValid(graph: any) {
  const result = E.validateView(graph);
  assert.equal(result.source.ok, true, JSON.stringify(result.source));
  assert.equal(result.layout.ok, true, JSON.stringify(result.layout));
  assert.deepEqual(plain(result.edges.filter(([, check]: any) => !check.ok)), []);
}
function sourceFields(graph: any) {
  return JSON.stringify(graph.edges.map((value: any) => [value.id, value.source, value.target, value.binding,
    value.fixedSource, value.fixedTarget, value.portPolicy, value.contract, value.waypoints]));
}

test('real frontier cleanup rejects a shortcut that adds an unregistered corner contact despite unchanged strict crossings', () => {
  for (const preserve of [false, true]) {
    const graph = synthetic();
    if (preserve) graph.edges[0].waypoints = points([[20, 50], [60, 80]]);
    assertValid(graph);
    const before = R.wireContacts(graph.edges[0].route, graph.edges[1].route).length;
    const authority = sourceFields(graph), peer = JSON.stringify(graph.edges[1]);
    const result = F.route(graph, { preserve });
    assert.equal(result.failed, 0); assertValid(graph);
    assert.ok(R.wireContacts(graph.edges[0].route, graph.edges[1].route).length <= before);
    assert.equal(JSON.stringify(graph.edges[1]), peer);
    assert.equal(sourceFields(graph), authority, 'source bindings, contracts, ports and explicit knots remain exact');
    const settled = JSON.stringify(graph.edges);
    assert.equal(F.route(graph, { preserve }).failed, 0);
    assert.equal(JSON.stringify(graph.edges), settled, 'the same cleanup frontier is stable');
  }
});

test('source-authorized fan-out remains a shared wire, allowing a harmless shared contact during cleanup', () => {
  const graph = synthetic(true); assertValid(graph);
  assert.equal(graph.edges[0].contract.wire, graph.edges[1].contract.wire);
  const authority = sourceFields(graph), before = graph.edges[0].route.length;
  assert.equal(F.route(graph).failed, 0); assertValid(graph);
  assert.ok(graph.edges[0].route.length < before, 'the independent-contact guard does not block the authorized shared wire');
  assert.equal(sourceFields(graph), authority);
  assert.ok(E.junctionPoint(graph, graph.junctionMarkers[0]), 'the registered source fork stays on both paths');
});

test('only a complete source-recorded shared presentation is licensed; partial coincident paths remain independent', () => {
  const graph = synthetic(), a = graph.edges[0], b = plain(a);
  b.id = 'other-value'; b.contract.wire = '["source","other"]';
  a.projection = { visual: 'recorded-overview' }; b.projection = { visual: 'recorded-overview' };
  graph.recursive = { authority: { variants: [{ nodes: graph.nodes.map((n: any) => ({ id: n.id })),
    edges: [{ id: 'recorded-overview', source: a.source, target: a.target }] }] } };
  assert.equal(E.sharesPresentation(graph, a, b), true);
  b.route[2].y += 1;
  assert.equal(E.sharesPresentation(graph, a, b), false);
  b.route = plain(a.route); b.draft = true;
  assert.equal(E.sharesPresentation(graph, a, b), false);
});
