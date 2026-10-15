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
const R = context.EdgeRouterLabRouting;
const plain = (value: any) => JSON.parse(JSON.stringify(value));
const node = (id: string, x: number, y: number, w: number, h: number, parent: string | null = null, expanded = false) =>
  ({ id, x, y, w, h, parent, expanded, routingObstacle: !expanded, base: [x, y], labelObstacles: [] as any[], html: '' });
function edge(source: string, target: string, sourceSide: string, targetSide: string, points: number[][]): any {
  return { id: 'value', source, target, arrow: 'target', style: 'orthogonal',
    fixedSource: { side: sourceSide, fraction: .5, inward: false }, fixedTarget: { side: targetSide, fraction: .5, inward: false },
    route: points.map(([x, y]) => ({ x, y })), waypoints: [] as any[], binding: { wire_identity: [source, 'out'], src: source + ':out', dst: target + ':in' },
    portPolicy: Object.fromEntries(['source', 'target'].map(side => [side,
      { mode: 'fixed', shape: 'rectangle', spacing: 12, gates: [], sharedStem: null }])) };
}
function graph(nodes: any[], edges: any[]) {
  const value = C.initialize({ nodes, edges, canvas: [1100, 900], junctionMarkers: [], routeLabels: [], attachments: [] });
  for (const edge of edges) { edge.contract.enforcePortApproach = true; edge.contract.minimumTerminal = 9; }
  return value;
}

test('expanded headings are geometric obstacles for original routes and repaired routes', () => {
  const owner = node('owner', 200, 100, 600, 400, null, true);
  owner.labelObstacles = [{ x: 10, y: 6, w: 300, h: 28 }];
  const value = edge('producer', 'consumer', 'top', 'top', [[250, 200], [250, 115], [680, 115], [680, 200]]);
  const g = graph([owner, node('producer', 220, 200, 60, 30, 'owner'), node('consumer', 650, 200, 60, 30, 'owner')], [value]);
  const original = JSON.stringify(value.binding);
  assert.ok(C.validate(g, value, value.route).violations.includes('route enters expanded heading owner'));
  assert.equal(F.route(g).failed, 0);
  assert.equal(C.validate(g, value, value.route).ok, true);
  assert.equal(JSON.stringify(value.binding), original);
});

test('invalid containment rejects routing immediately without changing nodes or evidence', () => {
  const source = graph([node('owner', 100, 100, 500, 400, null, true), node('child', 200, 200, 80, 40, 'owner')], []);
  const g = F.build(F.create({ detailed: source })), child = g.nodes.find((n: any) => n.id === 'child');
  child.x = g.nodes.find((n: any) => n.id === 'owner').x - 200;
  const before = JSON.stringify(g); let searches = 0; const batch = E.routeBatch;
  E.routeBatch = (...args: any[]) => { searches++; return batch(...args); };
  try {
    const result = F.route(g);
    assert.ok(result.failed > 0); assert.match(result.reason, /cannot repair invalid source layout/);
    assert.equal(searches, 0); assert.equal(JSON.stringify(g), before);
  } finally { E.routeBatch = batch; }
});

test('a local parallel detour preserves the licensed gate ray while clearing a nearby frame', () => {
  const value = edge('producer', 'consumer', 'left', 'right', [[600, 715], [408, 715], [408, 215], [360, 215]]);
  const g = graph([node('owner', 100, 100, 800, 500, null, true), node('neighbor', 200, 300, 200, 200, 'owner', true),
    node('producer', 600, 700, 60, 30), node('consumer', 300, 200, 60, 30, 'owner')], [value]);
  const authority = JSON.stringify([value.binding, value.fixedSource, value.fixedTarget, value.contract.gates]);
  assert.equal(C.validate(g, value, value.route).ok, true);
  assert.ok(C.laneContacts(g, value, value.route).length);
  let searches = 0; const batch = E.routeBatch;
  E.routeBatch = (...args: any[]) => { searches++; return batch(...args); };
  try { assert.equal(F.route(g).failed, 0); } finally { E.routeBatch = batch; }
  assert.equal(searches, 0);
  assert.equal(C.validate(g, value, value.route).ok, true);
  assert.deepEqual(plain(C.laneContacts(g, value, value.route)), []);
  assert.equal(JSON.stringify([value.binding, value.fixedSource, value.fixedTarget, value.contract.gates]), authority);
  assert.ok(C.crossings(value.route, g.nodes[0]).some((gate: any) => gate.side === 'bottom' && gate.direction === 'enter'
    && Math.abs(gate.fraction - .385) < 1e-5));
});

test('a short contact at a frame corner moves its elbow without moving the lane under a distant heading', () => {
  const owner = node('owner', 100, 100, 900, 500, null, true);
  owner.labelObstacles = [{ x: 650, y: 50, w: 100, h: 20 }];
  const value = edge('producer', 'consumer', 'right', 'right', [[760, 465], [800, 465], [800, 170], [498, 170], [498, 120], [360, 120]]);
  const g = graph([owner, node('neighbor', 200, 180, 300, 200, 'owner', true),
    node('producer', 700, 450, 60, 30, 'owner'), node('consumer', 300, 105, 60, 30, 'owner')], [value]);
  const authority = JSON.stringify([value.binding, value.fixedSource, value.fixedTarget, value.contract]);
  assert.equal(C.validate(g, value, value.route).ok, true);
  assert.equal(C.laneContacts(g, value, value.route)[0].length, 2);
  assert.equal(F.route(g).failed, 0);
  assert.equal(C.validate(g, value, value.route).ok, true);
  assert.deepEqual(plain(C.laneContacts(g, value, value.route)), []);
  assert.ok(value.route.some((p: any) => p.x === 800 && p.y === 170), 'the distant lane remains below the heading');
  assert.equal(JSON.stringify([value.binding, value.fixedSource, value.fixedTarget, value.contract]), authority);
});

test('bounded orthogonal shortcuts remove an unnecessary short step and retain a manual knot', () => {
  for (const preserve of [false, true]) {
    const value = edge('producer', 'consumer', 'right', 'left', [[60, 215], [200, 215], [200, 150], [192, 150], [192, 65], [300, 65]]);
    if (preserve) value.waypoints = [{ x: 200, y: 150 }, { x: 192, y: 150 }];
    const g = graph([node('producer', 0, 200, 60, 30), node('consumer', 300, 50, 60, 30)], [value]);
    const authority = JSON.stringify([value.binding, value.fixedSource, value.fixedTarget, value.waypoints]);
    assert.equal(F.route(g, { preserve }).failed, 0);
    assert.equal(C.validate(g, value, value.route).ok, true);
    assert.equal(value.route.length, preserve ? 6 : 4);
    assert.equal(JSON.stringify([value.binding, value.fixedSource, value.fixedTarget, value.waypoints]), authority);
    const before = JSON.stringify(value.route); F.route(g, { preserve });
    assert.equal(JSON.stringify(value.route), before, 'cleanup is stable when the same frontier is reopened');
  }
});

test('optional shortening does not add unrelated crossings or crowd a parallel lane', () => {
  const value = edge('producer', 'consumer', 'right', 'left', [[60, 215], [200, 215], [200, 150], [192, 150], [192, 65], [300, 65]]);
  const peer = { ...edge('peer-producer', 'peer-consumer', 'left', 'left', [[400, 100], [195, 100], [195, 90], [205, 90], [205, 400], [400, 400]]), id: 'peer-value' };
  peer.waypoints = [{ x: 195, y: 100 }, { x: 195, y: 90 }, { x: 205, y: 90 }];
  const g = graph([node('producer', 0, 200, 60, 30), node('consumer', 300, 50, 60, 30),
    node('peer-producer', 400, 85, 60, 30), node('peer-consumer', 400, 385, 60, 30)], [value, peer]);
  const crossings = () => value.route.slice(1).reduce((sum: number, p: any, i: number) => sum + peer.route.slice(1)
    .filter((q: any, j: number) => R.crossing(value.route[i], p, peer.route[j], q)).length, 0);
  const before = crossings(), originalPeer = JSON.stringify(peer.route);
  assert.equal(F.route(g, { preserve: true }).failed, 0);
  assert.ok(crossings() <= before, 'a shorter route must retain or improve unrelated crossing count');
  assert.ok(value.route.every((p: any) => p.x !== 200 || p.y >= 150), 'shortening does not extend the crowded parallel lane');
  assert.equal(JSON.stringify(peer.route), originalPeer);
});

test('painted free lanes separate in all orientations while manual knots and shared values remain intact', () => {
  for (let turns = 0; turns < 4; turns++) for (const protection of ['free', 'manual', 'same-wire']) {
    const value = edge('producer', 'consumer', 'right', 'left', [[60, 65], [200, 65], [200, 215], [300, 215]]);
    const peer = { ...edge('peer-producer', 'peer-consumer', 'right', 'left', [[60, 95], [201, 95], [201, 185], [300, 185]]), id: 'peer-value' };
    if (protection === 'manual') value.waypoints = [{ x: 200, y: 150 }];
    if (protection === 'same-wire') peer.binding.wire_identity = value.binding.wire_identity;
    const nodes = [node('producer', 0, 50, 60, 30), node('consumer', 300, 200, 60, 30),
      node('peer-producer', 0, 80, 60, 30), node('peer-consumer', 300, 170, 60, 30)];
    const rotate = (p: any) => { let x = p.x, y = p.y; for (let t = 0; t < turns; t++) [x, y] = [-y, x]; return { x: x + 700, y: y + 700 }; };
    const sides = ['right', 'bottom', 'left', 'top'];
    for (const n of nodes) {
      const corners = [[n.x, n.y], [n.x + n.w, n.y], [n.x, n.y + n.h], [n.x + n.w, n.y + n.h]].map(([x, y]) => rotate({ x, y }));
      n.x = Math.min(...corners.map(p => p.x)); n.y = Math.min(...corners.map(p => p.y));
      n.w = Math.max(...corners.map(p => p.x)) - n.x; n.h = Math.max(...corners.map(p => p.y)) - n.y; n.base = [n.x, n.y];
    }
    for (const e of [value, peer]) { e.route = e.route.map(rotate); e.waypoints = e.waypoints.map(rotate); e.fixedSource.side = sides[turns]; e.fixedTarget.side = sides[(turns + 2) % 4]; }
    const g = graph(nodes, [value, peer]); g.canvas = [2000, 2000];
    const authority = JSON.stringify(g.edges.map((e: any) => [e.binding, e.fixedSource, e.fixedTarget, e.waypoints])), before = JSON.stringify(g.edges.map((e: any) => e.route));
    assert.equal(F.route(g, { preserve: true }).failed, 0);
    assert.equal(JSON.stringify(g.edges.map((e: any) => [e.binding, e.fixedSource, e.fixedTarget, e.waypoints])), authority);
    if (protection === 'same-wire') assert.equal(JSON.stringify(g.edges.map((e: any) => e.route)), before);
    else {
      const axis = turns % 2 ? 'y' : 'x';
      assert.ok(Math.abs(value.route[1][axis] - peer.route[1][axis]) >= 10);
      if (protection === 'manual') assert.ok(value.route.slice(1).some((p: any, i: number) => R.dist(value.route[i], value.waypoints[0]) + R.dist(value.waypoints[0], p) <= R.dist(value.route[i], p) + 1e-5));
    }
    const final = JSON.stringify(g.edges.map((e: any) => e.route)), restored = E.clone(g); F.route(restored, { preserve: true });
    assert.equal(JSON.stringify(restored.edges.map((e: any) => e.route)), final);
  }
});

test('a local blocker channel keeps original ports, source fields and ordered manual knots', () => {
  for (const preserve of [false, true]) {
    const points = preserve ? [[260, 415], [280, 415], [280, 620], [630, 620], [630, 415], [650, 415]]
      : [[260, 415], [650, 415]];
    const value = edge('producer', 'consumer', 'right', 'left', points);
    if (preserve) value.waypoints = [{ x: 280, y: 620 }, { x: 630, y: 620 }];
    const g = graph([node('owner', 100, 100, 900, 600, null, true), node('blocker', 350, 300, 200, 300, 'owner', true),
      node('producer', 200, 400, 60, 30, 'owner'), node('consumer', 650, 400, 60, 30, 'owner')], [value]);
    const sourceFields = JSON.stringify([value.binding, value.contract, value.fixedSource, value.fixedTarget, value.waypoints]);
    let searches = 0; const batch = E.routeBatch; E.routeBatch = (...args: any[]) => { searches++; return batch(...args); };
    try { assert.equal(F.route(g, { preserve }).failed, 0); } finally { E.routeBatch = batch; }
    assert.equal(searches, 0, 'local geometric candidates do not invoke the visibility graph');
    assert.equal(C.validate(g, value, value.route).ok, true);
    assert.equal(JSON.stringify([value.binding, value.contract, value.fixedSource, value.fixedTarget, value.waypoints]), sourceFields);
    if (preserve) for (const knot of value.waypoints) assert.ok(value.route.some((p: any) => R.dist(p, knot) < 1e-5));
    const authority = F.create({ detailed: g }), recursive = F.all(F.build(authority), true), projected = recursive.edges[0];
    projected.fixedTarget.side = 'top';
    assert.equal(C.validateSource(recursive).ok, false, 'a clear local channel cannot authorize a changed fixed source interface');
  }
});

test('a mixed expanded parent reserves space for distinct source-backed boundary wires', () => {
  const nodes = [node('owner', 100, 100, 550, 600, null, true), node('module', 116, 180, 500, 400, 'owner', true),
    node('nested', 150, 450, 100, 80, 'module', true), node('nested-leaf', 170, 470, 40, 30, 'nested')];
  const edges: any[] = [];
  for (let i = 0; i < 3; i++) {
    const y = 250 + i * 60; nodes.push(node('producer-' + i, 400, y, 60, 30, 'module'), node('consumer-' + i, 800, y, 60, 30));
    edges.push({ ...edge('producer-' + i, 'consumer-' + i, 'right', 'left', [[460, y + 15], [800, y + 15]]), id: 'value-' + i });
  }
  const detailed = graph(nodes, edges), doc = F.create({ detailed }), initial = F.build(doc), mixed = F.toggle(initial, 'module', true);
  const owner = mixed.nodes.find((n: any) => n.id === 'owner'), module = mixed.nodes.find((n: any) => n.id === 'module');
  assert.ok(owner.x + owner.w - module.x - module.w >= 44, 'three distinct boundary values reserve two painted lanes plus 20px spacing');
  const full = F.all(mixed, true);
  assert.deepEqual(plain(full.nodes.map((n: any) => [n.id, n.x, n.y, n.w, n.h])), plain(detailed.nodes.map((n: any) => [n.id, n.x, n.y, n.w, n.h])), 'registered full source geometry remains exact');
});

test('optional cleanup has a graph budget and a cloned frontier does not continue after exhaustion', () => {
  const nodes: any[] = [], edges: any[] = [];
  for (let i = 0; i < 140; i++) {
    const y = i * 300, source = 'producer-' + i, target = 'consumer-' + i;
    nodes.push(node(source, 0, y + 200, 60, 30), node(target, 300, y + 50, 60, 30));
    edges.push({ ...edge(source, target, 'right', 'left', [[60, y + 215], [200, y + 215], [200, y + 150], [192, y + 150], [192, y + 65], [300, y + 65]]), id: 'value-' + i });
  }
  nodes.push(node('unrelated-peer', 1000, 100, 40, 40));
  const g = graph(nodes, edges), validate = C.validate; let calls = 0;
  C.validate = (...args: any[]) => { calls++; return validate(...args); };
  try {
    assert.equal(F.route(g).failed, 0);
    const firstCalls = calls, remaining = g.edges.filter((e: any) => e.route.length === 6).length;
    assert.ok(remaining > 0 && remaining < edges.length, 'one frontier stops optional work before all tiny steps are polished');
    const clone = E.clone(g), before = JSON.stringify(clone.edges.map((e: any) => e.route)); calls = 0;
    assert.equal(F.route(clone).failed, 0);
    assert.equal(JSON.stringify(clone.edges.map((e: any) => e.route)), before);
    assert.ok(firstCalls - calls <= 256, 'optional geometric validation is bounded across the whole graph');
    clone.nodes.find((n: any) => n.id === 'unrelated-peer').x++;
    assert.equal(F.route(clone).failed, 0);
    assert.ok(clone.edges.filter((e: any) => e.route.length === 6).length < remaining, 'changing peer geometry invalidates optional cleanup receipt');
  } finally { C.validate = validate; }
});
