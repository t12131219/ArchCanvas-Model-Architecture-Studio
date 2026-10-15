import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';

const preview = fileURLToPath(new URL('../public/preview/', import.meta.url));
const context = vm.createContext({});
for (const file of ['router.js', 'physical-ports.js', 'junction-markers.js', 'route-labels.js',
  'source-contracts.js', 'semantic-constraints.js', 'graph-engine.js', 'recursive-graph.js']) {
  vm.runInContext(readFileSync(path.join(preview, 'yworks_edge_router_lab', file), 'utf8'), context, { filename: file });
}
const E = context.SummaryEngine, F = context.SummaryRecursive, C = context.SummaryConstraints;
const catalog = JSON.parse(readFileSync(path.join(preview, 'data/catalog.json'), 'utf8'));
const plain = (value: any) => JSON.parse(JSON.stringify(value));

function fixture(id: string) {
  const item = catalog.cases.find((item: any) => item.id === id);
  assert.ok(item);
  const sources = Object.fromEntries(item.views.filter((view: any) => view.json).map((view: any) =>
    [view.key, C.initialize(JSON.parse(readFileSync(path.join(preview, view.json), 'utf8')))]));
  return F.build(F.create(sources));
}
function checked(graph: any) {
  assert.equal(F.route(graph).failed, 0);
  const check = E.validateView(graph);
  assert.equal(check.source.ok, true, check.source.violations.join('; '));
  assert.equal(check.layout.ok, true, check.layout.violations.join('; '));
  assert.deepEqual(plain(check.edges.filter(([, result]: any) => !result.ok)), []);
  assert.deepEqual(plain(check.routing.contacts), []);
  assert.deepEqual(plain(check.routing.constrained), []);
  for (const edge of graph.edges) for (const gate of C.activeGates(graph, edge)) {
    if (gate.frame === edge.source || gate.frame === edge.target) continue; // Named endpoint interface, checked by physical-port validation.
    if (C.ancestors(graph, edge.source).includes(gate.frame) && C.ancestors(graph, edge.target).includes(gate.frame)) continue; // Recorded optional escape/reentry detour.
    const frame = graph.nodes.find((node: any) => node.id === gate.frame);
    assert.ok(C.crossings(edge.route, frame).some((crossing: any) => crossing.side === gate.side
      && crossing.direction === gate.direction), `${edge.id} must retain the licensed ${gate.frame}/${gate.side} crossing`);
  }
  return graph;
}

for (const id of ['3ea7a49a16ba458d', '654be40c8d6a5cc2', '0342f4170c15ba8e', '8ed3fd7a969716dc', '39ca17212a8004c5']) {
  test(`exact ${catalog.cases.find((item: any) => item.id === id).title} frontier retains identities and restores clear routes`, () => {
    const initial = checked(fixture(id)), authority = JSON.stringify(initial.recursive.authority);
    const full = checked(F.all(initial, true)), geometry = JSON.stringify(full.nodes), routes = JSON.stringify(full.edges.map((edge: any) => [edge.id, edge.route]));
    assert.equal(JSON.stringify(full.recursive.authority), authority);
    const reopened = checked(F.all(checked(F.all(full, false)), true));
    assert.equal(JSON.stringify(reopened.nodes), geometry);
    assert.equal(JSON.stringify(reopened.edges.map((edge: any) => [edge.id, edge.route])), routes);
    for (const edge of reopened.edges) {
      const raw = reopened.recursive.authority.detail.edges.find((raw: any) => raw.id === edge.projection.original);
      assert.deepEqual(plain(edge.binding), plain(raw.binding));
    }
    const damaged = E.clone(reopened), edge = damaged.edges.find((edge: any) => edge.contract.gates.length);
    assert.ok(edge);
    edge.contract.gates[0].side = edge.contract.gates[0].side === 'left' ? 'right' : 'left';
    assert.equal(C.validateSource(damaged).ok, false, 'readable lanes do not license a different source interface');
  });
}

for (const id of ['3ea7a49a16ba458d', '654be40c8d6a5cc2', '0342f4170c15ba8e', '8ed3fd7a969716dc', '6740cec116c53470']) {
  test(`nested mixed ${catalog.cases.find((item: any) => item.id === id).title} frontier preserves geometry and gates`, () => {
    let graph = checked(fixture(id));
    const authority = JSON.stringify(graph.recursive.authority), nodes = graph.recursive.authority.detail.nodes;
    const depth = (id: string) => { let node = nodes.find((node: any) => node.id === id), depth = 0; while (node?.parent) { depth++; node = nodes.find((parent: any) => parent.id === node.parent); } return depth; };
    const target = F.containers(graph.recursive.authority).filter((id: string) => !graph.recursive.authority.mandatory.includes(id)).sort((a: string, b: string) => depth(b) - depth(a) || a.localeCompare(b))[0];
    let node = nodes.find((node: any) => node.id === target), chain: string[] = [];
    while (node) { if (F.children(graph.recursive.authority, node.id).length && !graph.recursive.authority.mandatory.includes(node.id)) chain.unshift(node.id); node = nodes.find((parent: any) => parent.id === node.parent); }
    for (const id of chain) graph = checked(F.toggle(graph, id, true));
    assert.equal(JSON.stringify(graph.recursive.authority), authority);
    assert.ok(graph.nodes.some((node: any) => node.parent === target));
    const before = JSON.stringify([graph.nodes, graph.edges.map((edge: any) => edge.route)]);
    graph = checked(F.toggle(checked(F.toggle(graph, chain[0], false)), chain[0], true));
    assert.equal(JSON.stringify([graph.nodes, graph.edges.map((edge: any) => edge.route)]), before);
  });
}

test('gate corner lanes use the same source-safe rule in all four orientations', () => {
  const node = (id: string, x: number, y: number, w: number, h: number, parent: string | null, expanded: boolean) =>
    ({ id, x, y, w, h, base: [x, y], parent, expanded, routingObstacle: !expanded, labelObstacles: [], html: '' });
  for (let turns = 0; turns < 4; turns++) {
    const nodes: any[] = [node('owner', 0, 0, 600, 550, null, true), node('block', 100, 100, 300, 300, 'owner', true),
      node('operand', 200, 300, 100, 50, 'block', false), node('producer', 450, 450, 60, 30, 'owner', false)];
    const edge: any = { id: 'value', source: 'producer', target: 'operand', arrow: 'target', style: 'orthogonal',
      fixedSource: { side: 'left', fraction: .5, inward: false }, fixedTarget: { side: 'right', fraction: .5, inward: false },
      route: [{ x: 450, y: 465 }, { x: 394, y: 465 }, { x: 394, y: 325 }, { x: 300, y: 325 }],
      binding: { src: 'producer:out', dst: 'operand:in', wire_identity: ['producer', 'out'] },
      portPolicy: Object.fromEntries(['source', 'target'].map(side => [side, { mode: 'fixed', shape: 'rectangle', spacing: 12, gates: [], sharedStem: null }])) };
    const rotate = (point: any) => ({ x: 650 - point.y, y: point.x });
    const sides: Record<string, string> = { left: 'top', top: 'right', right: 'bottom', bottom: 'left' };
    for (let turn = 0; turn < turns; turn++) {
      const ports = Object.fromEntries(['source', 'target'].map(side => [side, rotate(context.SummaryPhysicalPorts.point(nodes.find(node => node.id === edge[side]), edge[side === 'source' ? 'fixedSource' : 'fixedTarget']))]));
      for (const node of nodes) {
        const a = rotate(node), b = rotate({ x: node.x + node.w, y: node.y + node.h });
        Object.assign(node, { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), w: Math.abs(a.x - b.x), h: Math.abs(a.y - b.y) });
        node.base = [node.x, node.y];
      }
      for (const side of ['source', 'target']) {
        const fixed = edge[side === 'source' ? 'fixedSource' : 'fixedTarget'], node = nodes.find(node => node.id === edge[side]), next = sides[fixed.side];
        const axis = ['left', 'right'].includes(next) ? 'y' : 'x', size = axis === 'x' ? 'w' : 'h';
        fixed.side = next; fixed.fraction = (ports[side][axis] - node[axis]) / node[size];
      }
      edge.route = edge.route.map(rotate);
    }
    const source = C.initialize({ nodes, edges: [edge], canvas: [750, 750], junctionMarkers: [], routeLabels: [], attachments: [] });
    source.edges[0].contract.enforcePortApproach = true;
    const initial = F.build(F.create({ detailed: source })), authority = JSON.stringify(initial.recursive.authority);
    const full = checked(F.toggle(initial, 'block', true));
    assert.equal(JSON.stringify(full.recursive.authority), authority);
    const gate = C.activeGates(full, full.edges[0]).find((gate: any) => gate.frame === 'block');
    const original = source.edges[0].contract.gates.find((gate: any) => gate.frame === 'block');
    assert.equal(gate.side, original.side); assert.equal(gate.direction, original.direction);
    assert.ok(gate.fraction > .03 && gate.fraction < .97, 'a gate near a corner moves along its licensed side');
  }
});

test('an exterior detour keeps fixed ports, licensed gates and source fields intact', () => {
  const node = (id: string, x: number, y: number, w: number, h: number, parent: string | null, expanded = false) =>
    ({ id, x, y, w, h, base: [x, y], parent, expanded, routingObstacle: !expanded, labelObstacles: [], html: '' });
  const owner: any = node('owner', 200, 100, 500, 400, null, true);
  owner.labelObstacles = [{ x: 10, y: 6, w: 300, h: 28 }];
  const nodes = [owner, node('producer', 0, 200, 60, 30, null), node('consumer', 400, 300, 100, 50, 'owner')];
  const edge: any = { id: 'value', source: 'producer', target: 'consumer', arrow: 'target', style: 'orthogonal',
    fixedSource: { side: 'left', fraction: .5, inward: false }, fixedTarget: { side: 'right', fraction: .5, inward: false },
    route: [{ x: 0, y: 215 }, { x: 714, y: 215 }, { x: 714, y: 325 }, { x: 500, y: 325 }],
    binding: { src: 'producer:tuple:field[1]', dst: 'consumer:operand[0]', wire_identity: ['producer', 'tuple:field[1]'] },
    portPolicy: Object.fromEntries(['source', 'target'].map(side => [side,
      { mode: 'fixed', shape: 'rectangle', spacing: 12, gates: [], sharedStem: null }])) };
  const graph: any = C.initialize({ nodes, edges: [edge], canvas: [800, 600], junctionMarkers: [], routeLabels: [], attachments: [] });
  edge.contract.enforcePortApproach = true;
  const evidence = JSON.stringify([edge.binding, edge.fixedSource, edge.fixedTarget, edge.contract.gates]);
  let searches = 0; const routeBatch = E.routeBatch;
  E.routeBatch = (...args: any[]) => { searches++; return routeBatch(...args); };
  try {
    assert.equal(F.route(graph, { sides: 'any' }).failed, 0);
  } finally { E.routeBatch = routeBatch; }
  assert.equal(searches, 0, 'the bounded exterior candidate must settle this licensed detour before visibility search');
  assert.equal(C.validate(graph, edge, edge.route).ok, true);
  assert.deepEqual(plain(C.laneContacts(graph, edge, edge.route)), []);
  assert.equal(JSON.stringify([edge.binding, edge.fixedSource, edge.fixedTarget, edge.contract.gates]), evidence);
  assert.equal(edge.physicalSource.side, 'left'); assert.equal(edge.physicalTarget.side, 'right');
  assert.ok(edge.route.some((point: any) => point.x < 0));
  assert.ok(C.crossings(edge.route, owner).some((crossing: any) => crossing.side === 'right' && crossing.direction === 'enter'));
  const R = context.EdgeRouterLabRouting;
  assert.ok(!edge.route.slice(1).some((point: any, index: number) => R.intersectsRect(edge.route[index], point,
    { x: 210, y: 106, w: 300, h: 28 })), 'the detour must keep the expanded title readable');
});

test('recursive routing preserves actual manual knots in their declared order', () => {
  const nodes = [{ id: 'producer', x: 0, y: 100, w: 60, h: 30 }, { id: 'consumer', x: 300, y: 100, w: 60, h: 30 }]
    .map(node => ({ ...node, parent: null, expanded: false, base: [node.x, node.y], routingObstacle: true, labelObstacles: [], html: '' }));
  const edge: any = { id: 'manual-value', source: 'producer', target: 'consumer', arrow: 'target', style: 'orthogonal',
    fixedSource: { side: 'right', fraction: .5, inward: false }, fixedTarget: { side: 'left', fraction: .5, inward: false },
    route: [{ x: 60, y: 115 }, { x: 300, y: 115 }], waypoints: [{ x: 120, y: 40 }, { x: 240, y: 40 }],
    binding: { src: 'producer:out', dst: 'consumer:in', wire_identity: ['producer', 'out'] },
    portPolicy: Object.fromEntries(['source', 'target'].map(side => [side,
      { mode: 'fixed', shape: 'rectangle', spacing: 12, gates: [], sharedStem: null }])) };
  const graph: any = C.initialize({ nodes, edges: [edge], canvas: [500, 250], junctionMarkers: [], routeLabels: [], attachments: [] });
  edge.contract.enforcePortApproach = true;
  const evidence = JSON.stringify([edge.binding, edge.fixedSource, edge.fixedTarget, edge.waypoints]);
  assert.equal(F.route(graph, { preserve: true }).failed, 0);
  assert.equal(C.validate(graph, edge, edge.route).ok, true);
  assert.equal(JSON.stringify([edge.binding, edge.fixedSource, edge.fixedTarget, edge.waypoints]), evidence);
  const R = context.EdgeRouterLabRouting;
  let order = -1;
  for (const waypoint of edge.waypoints) {
    const found = edge.route.slice(1).findIndex((point: any, index: number) => index >= order
      && R.dist(edge.route[index], waypoint) + R.dist(waypoint, point) <= R.dist(edge.route[index], point) + 1e-5);
    assert.ok(found >= order && found >= 0, 'each retained knot occurs along the route in source-to-target order');
    order = found;
  }
  assert.ok(edge.route.some((point: any) => point.y === 40));
});

test('provably conflicting fixed target rays fail before search without rejecting shared values or separate slots', () => {
  const fixture = (shared: boolean, separateSlots: boolean) => {
    const nodes = [{ id: 'first', x: 0, y: 100, w: 60, h: 30 }, { id: 'second', x: 0, y: 200, w: 60, h: 30 },
      { id: 'consumer', x: 300, y: 100, w: 60, h: 60 }].map(node =>
      ({ ...node, parent: null, expanded: false, base: [node.x, node.y], routingObstacle: true, labelObstacles: [], html: '' }));
    const edges = ['first', 'second'].map((source, index) => {
      const y = index && separateSlots ? 145 : 115;
      return { id: 'input-' + index, source, target: 'consumer', arrow: 'target', style: 'orthogonal',
        fixedSource: { side: 'right', fraction: .5, inward: false }, fixedTarget: { side: 'left', fraction: (y - 100) / 60, inward: false },
        route: index ? [{ x: 60, y: 215 }, { x: 180, y: 215 }, { x: 180, y }, { x: 300, y }] : [{ x: 60, y: 115 }, { x: 300, y: 115 }],
        binding: { src: source + ':out', dst: 'consumer:in', wire_identity: [shared ? 'shared-value' : source, 'out'] },
        portPolicy: Object.fromEntries(['source', 'target'].map(side => [side,
          { mode: 'fixed', shape: 'rectangle', spacing: 12, gates: [], sharedStem: null }])) };
    });
    const graph = C.initialize({ nodes, edges, canvas: [500, 350], junctionMarkers: [], routeLabels: [], attachments: [] });
    for (const edge of graph.edges) { edge.contract.enforcePortApproach = true; edge.contract.minimumTerminal = 9; }
    return graph;
  };
  const conflict = fixture(false, false), before = JSON.stringify(conflict);
  let searches = 0; const batch = E.routeBatch;
  E.routeBatch = (...args: any[]) => { searches++; return batch(...args); };
  try {
    const result = F.route(conflict);
    assert.equal(result.failed, 1); assert.equal(result.routed, 0);
    assert.match(result.reason, /fixed target interface/);
    assert.equal(searches, 0, 'a mathematical endpoint conflict must never start visibility search');
    assert.equal(JSON.stringify(conflict), before, 'rejecting an impossible request retains every geometry and source field');
    for (const graph of [fixture(true, false), fixture(false, true)]) {
      assert.equal(F.route(graph).failed, 0);
      assert.equal(E.validateView(graph).layout.ok, true);
    }
  } finally { E.routeBatch = batch; }
});
