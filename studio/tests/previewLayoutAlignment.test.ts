import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const directory = fileURLToPath(new URL('../public/preview/yworks_edge_router_lab/', import.meta.url));
const context = vm.createContext({});
for (const file of ['router.js', 'physical-ports.js', 'junction-markers.js', 'route-labels.js',
  'source-contracts.js', 'semantic-constraints.js', 'graph-engine.js', 'recursive-graph.js'])
  vm.runInContext(readFileSync(path.join(directory, file), 'utf8'), context, { filename: file });
const F = context.SummaryRecursive;
const clone = (value: any) => JSON.parse(JSON.stringify(value));
const node = (id: string, x: number, y: number, w: number, h: number, parent?: string, expanded = false) =>
  ({ id, label: id, x, y, w, h, base: [x, y], parent, expanded, routingObstacle: !expanded, labelObstacles: [], html: '' });
const graph = (nodes: any[], edges: any[] = []) => ({ nodes, edges, canvas: [3000, 3000],
  attachments: [], routeLabels: [], junctionMarkers: [], extras: '' });
const find = (g: any, id: string) => g.nodes.find((n: any) => n.id === id);
const center = (g: any, id: string) => { const n = find(g, id); return n.x + n.w / 2; };

function columnFixture(differentCenter = false, parallel = false) {
  const overview = [node('root', 50, 50, 1400, 1200, undefined, true),
    node('wide', 100, 150, 200, 100, 'root'), node('leaf', 100, 350, differentCenter ? 100 : 200, 100, 'root'),
    node('folded', 100, 550, 200, 100, 'root')];
  if (parallel) overview.push(node('right-a', 1050, 150, 200, 100, 'root'), node('right-b', 1050, 350, 200, 100, 'root'));
  const detailed = clone(overview);
  Object.assign(detailed.find((n: any) => n.id === 'wide'), { expanded: true, w: 700, h: 300 });
  Object.assign(detailed.find((n: any) => n.id === 'folded'), { expanded: true, w: 500, h: 300 });
  detailed.push(node('wide/child', 150, 250, 600, 80, 'wide'), node('folded/child', 150, 650, 300, 80, 'folded'));
  return F.build(F.create({ overview: graph(overview), detailed: graph(detailed) }));
}

test('mixed width changes retain an explicit source center column and keep separate columns distinct', () => {
  const initial = columnFixture(false, true), authority = JSON.stringify(initial.recursive.authority);
  const mixed = F.toggle(initial, 'wide', true);
  assert.equal(center(mixed, 'wide'), center(mixed, 'leaf'));
  assert.equal(center(mixed, 'wide'), center(mixed, 'folded'));
  assert.equal(center(mixed, 'right-a'), center(mixed, 'right-b'));
  assert.ok(find(mixed, 'right-a').x >= find(mixed, 'wide').x + find(mixed, 'wide').w + 18);
  assert.equal(JSON.stringify(mixed.recursive.authority), authority);
  const leftAligned = F.toggle(columnFixture(true), 'wide', true);
  assert.notEqual(center(leftAligned, 'wide'), center(leftAligned, 'leaf'), 'different original centers do not imply a common axis');
});

test('manual local offsets remain final deltas and mixed collapse/reopen restores the complete geometry', () => {
  const mixed = F.toggle(columnFixture(), 'wide', true), doc = mixed.recursive;
  const relative = (g: any) => ({ x: find(g, 'leaf').x - find(g, 'root').x, y: find(g, 'leaf').y - find(g, 'root').y });
  const before = relative(mixed);
  doc.state.layouts.root = { leaf: { x: 37, y: -11 } }; doc.state.frontiers = {};
  const moved = F.build(doc), after = relative(moved);
  assert.deepEqual({ x: after.x - before.x, y: after.y - before.y }, { x: 37, y: -11 });
  assert.deepEqual(clone(doc.state.layouts.root), { leaf: { x: 37, y: -11 } });
  const geometry = JSON.stringify(moved.nodes);
  assert.equal(JSON.stringify(F.toggle(F.toggle(moved, 'wide', false), 'wide', true).nodes), geometry);
});

function helperFixture(side: string, gates: 'valid' | 'missing' | 'multiple' = 'valid', contained = false) {
  const opposite: Record<string, string> = { right: 'left', left: 'right', top: 'bottom', bottom: 'top' };
  const initial: Record<string, number[]> = { right: [100, 600], left: [1100, 600], top: [600, 1100], bottom: [600, 100] };
  const final: Record<string, number[]> = { right: [1012, 600], left: [288, 600], top: [600, 328], bottom: [600, 1012] };
  const [hx, hy] = contained ? [700, 600] : initial[side], [fx, fy] = final[side];
  const overview = [node('owner', 500, 500, 400, 600, undefined, true), node('consumer', 600, 650, 100, 60, 'owner'),
    node('spare', 600, 850, 100, 60, 'owner'), node('helper', hx, hy, 100, 60, contained ? 'owner' : undefined)];
  const detailed = clone(overview);
  for (const id of ['consumer', 'spare']) Object.assign(detailed.find((n: any) => n.id === id), { expanded: true, w: 250, h: 160 });
  detailed.push(node('consumer/value', 650, 720, 100, 40, 'consumer'), node('spare/value', 650, 920, 100, 40, 'spare'));
  if (!contained) Object.assign(detailed.find((n: any) => n.id === 'helper'), { x: fx, y: fy, base: [fx, fy] });
  const edge = (id: string, incoming: boolean) => ({ id, source: incoming ? 'consumer/value' : 'helper',
    target: incoming ? 'helper' : 'consumer/value', arrow: 'target', style: 'orthogonal',
    fixedSource: { side: incoming ? side : opposite[side], fraction: .5, inward: false },
    fixedTarget: { side: incoming ? opposite[side] : side, fraction: .5, inward: false },
    portPolicy: Object.fromEntries(['source', 'target'].map(which => [which,
      { mode: 'fixed', shape: 'rectangle', spacing: 12, gates: [], sharedStem: null }])),
    route: [{ x: fx, y: fy + 30 }, { x: 700, y: 740 }],
    binding: { src: incoming ? 'consumer/value:shape' : 'helper:sample', role: incoming ? 'shape_dependency' : 'random_sample' },
    contract: { version: 1, source: incoming ? 'consumer/value' : 'helper', target: incoming ? 'helper' : 'consumer/value',
      gates: gates === 'missing' ? [] : Array.from({ length: gates === 'multiple' ? 2 : 1 }, (_, i) =>
        ({ frame: 'owner', side, fraction: .5 + i * .1, order: 1 + i, direction: incoming ? 'exit' : 'enter' })),
      wire: id, sharedStem: null, enforcePortApproach: true, minimumTerminal: 9 } });
  const edges = [edge('sample', false), edge('shape', true)];
  const initialGraph = F.build(F.create({ overview: graph(overview, clone(edges)), detailed: graph(detailed, clone(edges)) }));
  return { initial: initialGraph, mixed: F.toggle(initialGraph, 'consumer', true) };
}

function isOnSide(g: any, side: string) {
  const h = find(g, 'helper'), o = find(g, 'owner');
  return side === 'right' ? h.x >= o.x + o.w + 112 : side === 'left' ? h.x + h.w <= o.x - 112
    : side === 'bottom' ? h.y >= o.y + o.h + 112 : h.y + h.h <= o.y - 112;
}

for (const side of ['left', 'right', 'top', 'bottom']) test(`one leaf helper follows its explicit ${side} interfaces without dropping incoming shape evidence`, () => {
  const { initial, mixed } = helperFixture(side), authority = JSON.stringify(initial.recursive.authority);
  assert.ok(isOnSide(mixed, side));
  assert.equal(mixed.edges.length, 2);
  assert.equal(JSON.stringify(mixed.recursive.authority), authority);
  for (const edge of mixed.edges) {
    const raw = mixed.recursive.authority.detail.edges.find((e: any) => e.id === edge.projection.original);
    assert.deepEqual(clone(edge.binding), clone(raw.binding));
    assert.ok(edge.contract.gates.every((g: any) => g.side === side));
  }
  const nodes = JSON.stringify(mixed.nodes);
  assert.equal(JSON.stringify(F.toggle(F.toggle(mixed, 'consumer', false), 'consumer', true).nodes), nodes);
});

test('missing or ambiguous helper interfaces and contained leaves do not authorize relocation', () => {
  for (const gates of ['missing', 'multiple'] as const) assert.equal(isOnSide(helperFixture('right', gates).mixed, 'right'), false);
  const contained = helperFixture('right', 'valid', true).mixed, helper = find(contained, 'helper'), owner = find(contained, 'owner');
  assert.equal(helper.parent, 'owner');
  assert.ok(helper.x >= owner.x && helper.x + helper.w <= owner.x + owner.w);
});

test('helper placement reserves root envelopes after manual offsets and retains exact registered frontiers', () => {
  const { initial, mixed } = helperFixture('right'), doc = mixed.recursive, before = clone(find(mixed, 'helper'));
  doc.state.layouts.$root = { helper: { x: 37, y: -11 } }; doc.state.frontiers = {};
  const moved = F.build(doc);
  assert.equal(find(moved, 'helper').x - before.x, 37); assert.equal(find(moved, 'helper').y - before.y, -11);
  const clean = helperFixture('right'), cleanDoc = clean.mixed.recursive;
  for (const variant of cleanDoc.authority.variants) variant.nodes.push(node('blocker', 2000, 2000, 100, 60));
  cleanDoc.authority.detail.nodes.push(node('blocker', 2000, 2000, 100, 60));
  cleanDoc.state.frontiers = {};
  const withBlocker = F.build(cleanDoc), blocker = find(withBlocker, 'blocker'), proposed = find(withBlocker, 'helper');
  cleanDoc.state.layouts.$root = { blocker: { x: proposed.x - blocker.x, y: proposed.y - blocker.y } }; cleanDoc.state.frontiers = {};
  assert.equal(isOnSide(F.build(cleanDoc), 'right'), false, 'a shifted root can occupy the candidate helper envelope');
  const exactInitial = JSON.stringify(initial.nodes), full = F.all(helperFixture('right').initial, true), exactFull = JSON.stringify(full.nodes);
  assert.equal(JSON.stringify(F.all(F.all(full, false), true).nodes), exactFull);
  const fresh = helperFixture('right').initial;
  assert.equal(JSON.stringify(fresh.nodes), exactInitial, 'registered overview remains source geometry');
  assert.equal(find(full, 'helper').x, 1012, 'registered full view keeps its original helper position');
});
