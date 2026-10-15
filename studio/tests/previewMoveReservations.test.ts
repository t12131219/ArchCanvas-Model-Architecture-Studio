import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const preview = fileURLToPath(new URL('../public/preview/', import.meta.url));
const context = vm.createContext({});
for (const name of ['router.js', 'physical-ports.js', 'junction-markers.js', 'route-labels.js',
  'source-contracts.js', 'semantic-constraints.js', 'graph-engine.js'])
  vm.runInContext(fs.readFileSync(path.join(preview, 'yworks_edge_router_lab', name), 'utf8'), context, { filename: name });
const C = context.SummaryConstraints, E = context.SummaryEngine, J = context.SummaryJunctionMarkers;
const plain = (value: any) => JSON.parse(JSON.stringify(value));
const node = (id: string, x: number, y: number, w: number, h: number, parent: string | null = null, expanded = false) =>
  ({ id, x, y, w, h, base: [x, y], parent, expanded, routingObstacle: !expanded, labelObstacles: [], html: '' });
const edge = (id: string, source: string, target: string, targetSide: string, points: number[][]): any =>
  ({ id, source, target, arrow: 'target', style: 'orthogonal', route: points.map(([x, y]) => ({ x, y })), waypoints: [],
    fixedSource: { side: 'right', fraction: .5, inward: false }, fixedTarget: { side: targetSide, fraction: .5, inward: false },
    binding: { wire_identity: [source, 'out'], src: source + ':out', dst: target + ':in' },
    portPolicy: Object.fromEntries(['source', 'target'].map(side => [side,
      { mode: 'fixed', shape: 'rectangle', spacing: 12, gates: [], sharedStem: null }])) });
function synthetic() {
  const values = [edge('first', 'producer', 'first-target', 'left', [[140, 220], [190, 220], [190, 200], [300, 200]]),
    edge('pending', 'other-producer', 'second-target', 'left', [[140, 100], [240, 100], [240, 220], [280, 220], [280, 300], [300, 300]]),
    edge('valid-peer', 'peer-producer', 'peer-target', 'right', [[80, 50], [210, 50], [210, 220], [200, 220], [200, 350], [60, 350]])];
  const graph = C.initialize({ nodes: [node('group', 260, 100, 240, 400, null, true),
    node('producer', 100, 205, 40, 30), node('other-producer', 100, 85, 40, 30),
    node('first-target', 300, 185, 40, 30, 'group'), node('second-target', 300, 285, 40, 30, 'group'),
    node('peer-producer', 50, 40, 30, 20), node('peer-target', 30, 340, 30, 20)],
    edges: values, canvas: [900, 800], junctionMarkers: [], routeLabels: [], attachments: [] });
  for (const value of values) { value.contract.enforcePortApproach = true; value.contract.minimumTerminal = 9; }
  return graph;
}
function assertValid(graph: any) {
  const check = E.validateView(graph);
  assert.equal(check.source.ok, true, JSON.stringify(check.source));
  assert.equal(check.layout.ok, true, JSON.stringify(check.layout));
  assert.deepEqual(plain(check.edges.filter(([, result]: any) => !result.ok)), []);
}

test('a group move repairs provisional target paths while reserving a third independent valid wire', () => {
  for (const reverse of [false, true]) {
    const graph = synthetic(); if (reverse) graph.edges.reverse(); assertValid(graph);
    const peer = graph.edges.find((value: any) => value.id === 'valid-peer'), beforePeer = JSON.stringify(peer);
    const authority = JSON.stringify(graph.edges.map((value: any) => [value.id, value.binding, value.fixedSource, value.fixedTarget]));
    assert.ok(E.move(graph, 'group', 0, 20).has('group'), JSON.stringify(graph.lastMove));
    assertValid(graph);
    assert.equal(JSON.stringify(peer), beforePeer, 'the valid unrelated peer retains its complete route and metadata');
    assert.equal(JSON.stringify(graph.edges.map((value: any) => [value.id, value.binding, value.fixedSource, value.fixedTarget])), authority);
    for (const value of graph.edges) assert.equal(E.overlapsWire(graph, value, value.route), false);
  }
});

test('a valid independent wire cannot be ignored when a moved mandatory shared ray would overlap it', () => {
  const graph = synthetic(), first = graph.edges.find((value: any) => value.id === 'first');
  first.portPolicy.source.sharedStem = { side: 'right', axis: 'x', length: 50, coordinate: 190, owner: 'producer' };
  first.contract.sharedStem = plain(first.portPolicy.source.sharedStem);
  assertValid(graph);
  const control = E.clone(graph);
  control.edges = control.edges.filter((value: any) => value.id !== 'valid-peer');
  control.nodes = control.nodes.filter((value: any) => !['peer-producer', 'peer-target'].includes(value.id));
  C.initialize(control); assertValid(control);
  assert.ok(E.move(control, 'producer', 15, 0).has('producer'), JSON.stringify(control.lastMove));
  assertValid(control);
  const nodes = JSON.stringify(graph.nodes), edges = JSON.stringify(graph.edges);
  assert.equal(E.move(graph, 'producer', 15, 0).size, 0);
  assert.equal(graph.lastMove.blocked, true);
  assert.equal(JSON.stringify(graph.nodes), nodes, 'a rejected move restores every node');
  assert.equal(JSON.stringify(graph.edges), edges, 'a rejected move restores source fields, ports, knots and routes');
  assertValid(graph);
});

test('repairing original compact headings during a norm move preserves the registered residual junction and undo snapshot', () => {
  const catalog = JSON.parse(fs.readFileSync(path.join(preview, 'data/catalog.json'), 'utf8'));
  const item = catalog.cases.find((value: any) => value.title === 'Transformer · compact'
    && value.collection === 'transformer_programmatic_guide' && !value.historical);
  const graph = C.initialize(JSON.parse(fs.readFileSync(path.join(preview, item.views.find((value: any) => value.key === 'modules').json), 'utf8')));
  const marker = graph.junctionMarkers.find((value: any) => value.owner === 'enc.norm1');
  const undo = E.clone(graph), oldJunction = E.junctionPoint(undo, marker), baseline = JSON.stringify(graph.semanticBaseline);
  assert.ok(E.validateView(graph).edges.some(([, check]: any) => check.violations.some((message: string) => message.includes('expanded heading'))));
  assert.ok(E.move(graph, 'enc.norm1', 10, 0).has('enc.norm1'), JSON.stringify(graph.lastMove));
  assertValid(graph);
  const junction = E.junctionPoint(graph, marker); assert.ok(junction);
  for (const id of marker.edges) assert.ok(J.contains(graph.edges.find((value: any) => value.id === id).route, junction));
  assert.ok(J.rays(marker.edges.map((id: string) => graph.edges.find((value: any) => value.id === id).route), junction).size >= 3);
  assert.equal(JSON.stringify(graph.semanticBaseline), baseline);
  assert.deepEqual(plain(E.junctionPoint(undo, marker)), plain(oldJunction));
});
