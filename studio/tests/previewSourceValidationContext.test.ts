import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const preview = fileURLToPath(new URL('../public/preview/', import.meta.url));
function runtime(cache = true) {
  const context = vm.createContext({});
  for (const file of ['router.js', 'physical-ports.js', 'junction-markers.js', 'route-labels.js',
    'source-contracts.js', 'semantic-constraints.js', 'graph-engine.js', 'recursive-graph.js']) {
    vm.runInContext(readFileSync(path.join(preview, 'yworks_edge_router_lab', file), 'utf8'), context, { filename: file });
  }
  if (!cache) {
    const create = context.SummaryConstraints.validationContext;
    context.SummaryConstraints.validationContext = (graph: any) => {
      const context = create(graph); delete context.sourceEdgeErrors; return context;
    };
  }
  return { F: context.SummaryRecursive, E: context.SummaryEngine, C: context.SummaryConstraints,
    P: context.SummaryPhysicalPorts, S: context.SummarySourceContracts };
}
const plain = (value: any) => JSON.parse(JSON.stringify(value));
const catalog = JSON.parse(readFileSync(path.join(preview, 'data/catalog.json'), 'utf8'));
function fixture(engine: ReturnType<typeof runtime>, id: string) {
  const item = catalog.cases.find((item: any) => item.id === id);
  return engine.F.build(engine.F.create(Object.fromEntries(item.views.filter((view: any) => view.json)
    .map((view: any) => [view.key, engine.C.initialize(JSON.parse(readFileSync(path.join(preview, view.json), 'utf8')))]))));
}

test('source checks reuse only source invariants while every candidate rechecks physical ports', () => {
  const r = runtime(), graph = fixture(r, '0342f4170c15ba8e');
  assert.equal(r.F.route(graph).failed, 0);
  const edge = graph.edges[0], context = r.C.validationContext(graph), edgeErrors = r.S.edgeErrors, physicalErrors = r.P.errors;
  let sourceChecks = 0, physicalChecks = 0;
  r.S.edgeErrors = (...args: any[]) => { sourceChecks++; return edgeErrors(...args); };
  r.P.errors = (...args: any[]) => { physicalChecks++; return physicalErrors(...args); };
  const reference = plain(r.C.validate(graph, edge, edge.route)); sourceChecks = physicalChecks = 0;
  for (let i = 0; i < 12; i++) assert.deepEqual(plain(r.C.validate(graph, edge, edge.route, context)), reference);
  assert.equal(sourceChecks, 1); assert.equal(physicalChecks, 12);
  edge.binding = { ...edge.binding, canonical_src: 'fabricated-value' };
  assert.equal(r.C.validate(graph, edge, edge.route, context).ok, false);
  assert.equal(sourceChecks, 2, 'an in-place source edit invalidates its source result');
});

test('candidate endpoints and contract edits cannot inherit a valid source result', () => {
  const r = runtime(), graph = fixture(r, '0342f4170c15ba8e'); r.F.route(graph);
  const edge = graph.edges.find((edge: any) => edge.contract.gates.length) ?? graph.edges[0];
  const context = r.C.validationContext(graph);
  assert.equal(r.C.validate(graph, edge, edge.route, context).ok, true);
  const badEndpoint = plain(edge.route); badEndpoint[0].x += 1;
  assert.equal(r.C.validate(graph, edge, badEndpoint, context).ok, false);
  const originalPort = edge.physicalSource;
  edge.physicalSource = { ...edge.fixedSource, fraction: -1 };
  assert.equal(r.C.validate(graph, edge, edge.route, context).ok, false);
  edge.physicalSource = originalPort;
  const originalContract = plain(edge.contract); edge.contract.wire = 'fabricated-wire';
  assert.equal(r.C.validate(graph, edge, edge.route, context).ok, false);
  edge.contract = originalContract;
  const clone = plain(graph); clone.edges.find((e: any) => e.id === edge.id).binding.src = 'fabricated-producer';
  const cloneEdge = clone.edges.find((e: any) => e.id === edge.id);
  assert.equal(r.C.validate(clone, cloneEdge, cloneEdge.route, context).ok, false, 'contexts are graph local');
  const otherContext = r.C.validationContext(graph);
  assert.notEqual(context.sourceEdgeErrors, otherContext.sourceEdgeErrors);
  const noGates = plain(graph), gated = noGates.edges.find((e: any) => e.contract.gates.length);
  if (gated) {
    for (const variant of noGates.recursive.authority.variants) for (const edge of variant.edges) edge.contract.gates = [];
    const checked = r.C.validate(noGates, gated, gated.route, r.C.validationContext(noGates));
    assert.equal(checked.ok, false, 'a new transaction must re-read changed source gate licences');
    assert.match(checked.violations.join(';'), /no source interface/);
  }
});

for (const id of ['3ea7a49a16ba458d', '0342f4170c15ba8e', '87dbdc94e0f6462f']) {
  test(`cached and uncached ${catalog.cases.find((item: any) => item.id === id).title} routing is identical`, () => {
    const cached = runtime(), uncached = runtime(false);
    let a = fixture(cached, id), b = fixture(uncached, id);
    for (const expanded of [false, true, false, true]) {
      a = cached.F.all(a, expanded); b = uncached.F.all(b, expanded);
      assert.equal(cached.F.route(a).failed, 0); assert.equal(uncached.F.route(b).failed, 0);
      assert.deepEqual(plain(a.nodes), plain(b.nodes)); assert.deepEqual(plain(a.edges), plain(b.edges));
      const ca = cached.E.validateView(a), cb = uncached.E.validateView(b);
      assert.equal(ca.source.ok, true); assert.equal(ca.layout.ok, true);
      assert.deepEqual(plain(ca), plain(cb));
    }
  });
}
