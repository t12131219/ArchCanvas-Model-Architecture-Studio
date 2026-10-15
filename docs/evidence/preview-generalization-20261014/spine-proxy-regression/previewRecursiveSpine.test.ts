import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';

const directory = fileURLToPath(new URL('../public/preview/yworks_edge_router_lab/', import.meta.url));
const context = vm.createContext({});
for (const name of ['router.js', 'physical-ports.js', 'junction-markers.js', 'route-labels.js',
  'source-contracts.js', 'semantic-constraints.js', 'graph-engine.js', 'recursive-graph.js'])
  vm.runInContext(readFileSync(path.join(directory, name), 'utf8'), context, { filename: name });
const C = context.SummaryConstraints, E = context.SummaryEngine, F = context.SummaryRecursive;
const plain = (value: any) => JSON.parse(JSON.stringify(value));

function fixture(mirrorX: boolean, mirrorY: boolean, shared: boolean | 'independent' | 'proxy' | 'single-layer' = true) {
  const node = (id: string, x: number, y: number, w: number, h: number, parent: string | null = null, expanded = false) =>
    ({ id, label: id, x, y, w, h, parent, expanded, routingObstacle: !expanded, base: [x, y], labelObstacles: [], html: '' });
  const nodes = [node('owner', 200, 50, 600, 800, null, true),
    node('foldable', 300, 100, 400, 150, 'owner', true), node('foldable/value', 470, 150, 60, 40, 'foldable'),
    node('frame', 300, 350, 400, 400, 'owner', true), node('left', 330, 650, 60, 60, 'frame'),
    node('center', 470, 650, 60, 60, 'frame'), node('right', 610, 650, 60, 60, 'frame'),
    node('producer', 470, shared === 'single-layer' ? 780 : 950, 60, 60, shared === 'single-layer' ? 'owner' : null)];
  const point = (x: number, y: number) => ({ x: mirrorX ? 1000 - x : x, y: mirrorY ? 1200 - y : y });
  const edges = (shared ? ['left', 'center', 'right'] : ['center']).map((target, i) => {
    const x = nodes.find(n => n.id === target)!.x + 30;
    const field = shared === 'independent' ? `slot-${i}` : 'out';
    return { id: `branch-${i}`, source: shared === 'proxy' ? 'frame' : 'producer', target, arrow: 'target', style: 'orthogonal',
      fixedSource: { side: shared === 'proxy' ? (mirrorY ? 'top' : 'bottom') : (mirrorY ? 'bottom' : 'top'), fraction: .5, inward: shared === 'proxy' },
      fixedTarget: { side: mirrorY ? 'top' : 'bottom', fraction: .5, inward: false },
      route: [point(500, shared === 'proxy' ? 750 : shared === 'single-layer' ? 780 : 950), point(500, 725), point(x, 725), point(x, 710)], waypoints: [],
      binding: { wire_identity: [shared === 'proxy' ? 'frame' : 'producer', field], src: (shared === 'proxy' ? 'frame' : 'producer') + ':' + field, dst: target + ':in' },
      portPolicy: Object.fromEntries(['source', 'target'].map(side => [side,
        { mode: shared === 'independent' && side === 'source' ? 'perimeter' : 'fixed',
          shape: 'rectangle', spacing: 12, gates: [], sharedStem: null }])) };
  });
  for (const n of nodes) {
    if (mirrorX) n.x = 1000 - n.x - n.w;
    if (mirrorY) n.y = 1200 - n.y - n.h;
    n.base = [n.x, n.y];
  }
  const source = C.initialize({ nodes, edges, canvas: [1200, 1200], attachments: [], routeLabels: [], junctionMarkers: [] });
  return F.toggle(F.build(F.create({ detailed: source })), 'frame', true);
}

for (const mirrorX of [false, true]) for (const mirrorY of [false, true])
  test(`asymmetric nested frame padding preserves the source operand spine under reflections ${mirrorX}/${mirrorY}`, () => {
    const g = fixture(mirrorX, mirrorY), authority = JSON.stringify(g.recursive.authority);
    assert.equal(F.route(g).failed, 0);
    const middle = g.edges.find((e: any) => e.target === 'center'), source = E.endpoint(g, middle, 'source');
    assert.equal(middle.route.length, 2, 'source-aligned input stays straight through both nested boundaries');
    for (const e of g.edges) {
      const gates = C.activeGates(g, e);
      assert.equal(gates.length, 2);
      assert.ok(e.route.length <= 4, 'a shared branch needs only its real fork');
      for (const gate of gates) {
        const frame = g.nodes.find((n: any) => n.id === gate.frame);
        assert.ok(Math.abs(C.gatePoint(frame, gate).x - source.x) < 1e-5);
      }
      assert.equal(C.validate(g, e, e.route).ok, true);
    }
    assert.equal(E.validateView(g).layout.ok, true);
    assert.equal(JSON.stringify(g.recursive.authority), authority);
    const saved = JSON.stringify(g.nodes);
    assert.equal(JSON.stringify(F.toggle(F.toggle(g, 'frame', false), 'frame', true).nodes), saved);
  });

test('content spine alignment keeps descendant manual offsets as final deltas', () => {
  const g = fixture(false, false), before = g.nodes.find((n: any) => n.id === 'center');
  const authority = JSON.stringify(g.recursive.authority);
  g.recursive.state.layouts.frame = { center: { x: 17, y: -3 } }; g.recursive.state.frontiers = {};
  const moved = F.build(g.recursive), after = moved.nodes.find((n: any) => n.id === 'center');
  assert.equal(after.x - before.x, 17);
  assert.equal(after.y - before.y, -3);
  assert.deepEqual(plain(moved.recursive.state.layouts.frame), { center: { x: 17, y: -3 } });
  assert.equal(JSON.stringify(moved.recursive.authority), authority);
});

test('a single centered boundary wire preserves outline alignment instead of authorizing a shared content axis', () => {
  for (const mirrorX of [false, true]) for (const mirrorY of [false, true]) {
    const g = fixture(mirrorX, mirrorY, false), authority = JSON.stringify(g.recursive.authority);
    const center = (id: string) => { const n = g.nodes.find((n: any) => n.id === id); return n.x + n.w / 2; };
    assert.equal(center('frame'), center('foldable'), 'source-aligned outlines retain their column for a single wire');
    assert.equal(F.route(g).failed, 0);
    assert.equal(E.validateView(g).layout.ok, true);
    assert.equal(JSON.stringify(g.recursive.authority), authority);
  }
});

test('distinct tuple output slots preserve outline alignment and keep their complete value identities', () => {
  for (const mirrorX of [false, true]) for (const mirrorY of [false, true]) {
    const g = fixture(mirrorX, mirrorY, 'independent'), authority = JSON.stringify(g.recursive.authority);
    const center = (id: string) => { const n = g.nodes.find((n: any) => n.id === id); return n.x + n.w / 2; };
    assert.equal(center('frame'), center('foldable'), 'different fields cannot license a shared content spine');
    assert.equal(new Set(g.edges.map((e: any) => C.wireIdentity(e, g))).size, 3);
    assert.equal(C.validateSource(g).ok, true);
    assert.equal(JSON.stringify(g.recursive.authority), authority);
    assert.deepEqual(plain(g.edges.map((e: any) => e.binding.wire_identity)),
      [['producer', 'slot-0'], ['producer', 'slot-1'], ['producer', 'slot-2']]);
  }
});


test('a container input proxy fan-out cannot move its own outline away from the source column', () => {
  for (const mirrorX of [false, true]) for (const mirrorY of [false, true]) {
    const graph = fixture(mirrorX, mirrorY, 'proxy'), authority = JSON.stringify(graph.recursive.authority);
    const center = (id: string) => { const n = graph.nodes.find((n: any) => n.id === id); return n.x + n.w / 2; };
    assert.equal(new Set(graph.edges.map((e: any) => e.source)).size, 1);
    assert.equal(graph.edges[0].source, 'frame');
    assert.equal(center('frame'), center('foldable'), 'the frame input proxy preserves the recorded outline column');
    assert.equal(F.route(graph).failed, 0);
    assert.equal(E.validateView(graph).layout.ok, true);
    assert.equal(JSON.stringify(graph.recursive.authority), authority);
  }
});

test('a genuine producer within the parent still licenses a shared content axis through one boundary', () => {
  for (const mirrorX of [false, true]) for (const mirrorY of [false, true]) {
    const graph = fixture(mirrorX, mirrorY, 'single-layer'), authority = JSON.stringify(graph.recursive.authority);
    assert.equal(F.route(graph).failed, 0);
    const middle = graph.edges.find((e: any) => e.target === 'center');
    assert.equal(middle.route.length, 2);
    for (const edge of graph.edges) {
      assert.equal(C.activeGates(graph, edge).length, 1, 'a single real boundary is sufficient');
      assert.equal(C.validate(graph, edge, edge.route).ok, true);
    }
    assert.equal(E.validateView(graph).layout.ok, true);
    assert.equal(JSON.stringify(graph.recursive.authority), authority);
  }
});
