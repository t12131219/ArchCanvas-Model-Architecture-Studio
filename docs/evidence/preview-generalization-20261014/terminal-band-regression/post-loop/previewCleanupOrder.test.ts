import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const preview = fileURLToPath(new URL('../public/preview/', import.meta.url));
const runtime = process.env.ARCHCANVAS_PREVIEW_TEST_RUNTIME || path.join(preview, 'yworks_edge_router_lab');
const context = vm.createContext({});
for (const name of ['router.js', 'physical-ports.js', 'junction-markers.js', 'route-labels.js',
  'source-contracts.js', 'semantic-constraints.js', 'graph-engine.js', 'recursive-graph.js'])
  vm.runInContext(fs.readFileSync(path.join(runtime, name), 'utf8'), context, { filename: name });
const C = context.SummaryConstraints, E = context.SummaryEngine, F = context.SummaryRecursive;
const plain = (value: any) => JSON.parse(JSON.stringify(value));

function loadCase(title: string) {
  const catalog = JSON.parse(fs.readFileSync(path.join(preview, 'data/catalog.json'), 'utf8'));
  const item = catalog.cases.find((item: any) => !item.historical && item.title === title
    && item.collection === 'module_programmatic_guide');
  assert.ok(item, 'the original source-backed regression case remains registered');
  const sources = Object.fromEntries(item.views.filter((view: any) => view.json).map((view: any) => [view.key,
    C.initialize(JSON.parse(fs.readFileSync(path.join(preview, view.json), 'utf8')))]));
  return F.build(F.create(sources));
}
function sourceFields(graph: any) {
  return JSON.stringify(graph.edges.map((edge: any) => [edge.id, edge.source, edge.target, edge.binding,
    edge.fixedSource, edge.fixedTarget, edge.portPolicy, edge.contract, edge.waypoints]));
}
function assertValid(graph: any) {
  const checked = E.validateView(graph);
  assert.equal(checked.source.ok, true, JSON.stringify(checked.source));
  assert.equal(checked.layout.ok, true, JSON.stringify(checked.layout));
  assert.deepEqual(plain(checked.edges.filter(([, check]: any) => !check.ok)), []);
}

test('terminal follow-up waits for the original full cleanup to simplify shared LSTM output routes', () => {
  const graph = loadCase('layernorm lstm cell'), authority = JSON.stringify(graph.recursive.authority);
  const source = sourceFields(graph);
  assert.equal(F.route(graph).failed, 0); assertValid(graph);
  // Both source-recorded outputs need one long detour around the body. The
  // original cleanup removes its short intermediate bands before terminal
  // sliding; sliding those bands first stranded two extra bends on each.
  for (const [id, maximumPoints] of [['route-0036-35', 7], ['route-0037-36', 8]] as const) {
    const edge = graph.edges.find((edge: any) => edge.id === id);
    assert.ok(edge, 'the original output binding is preserved');
    assert.ok(edge.route.length <= maximumPoints, `${id}: ${JSON.stringify(edge.route)}`);
  }
  assert.equal(JSON.stringify(graph.recursive.authority), authority);
  assert.equal(sourceFields(graph), source, 'the cleanup keeps source evidence, fixed ports, gates and manual knots exact');
  const nodes = JSON.stringify(graph.nodes), routes = JSON.stringify(graph.edges);
  const reopened = F.all(F.all(E.clone(graph), true), false);
  assert.equal(F.route(reopened).failed, 0); assertValid(reopened);
  assert.equal(JSON.stringify(reopened.nodes), nodes, 'folding restores the exact initial geometry');
  assert.equal(JSON.stringify(reopened.edges), routes, 'folding restores the simplified output paths');
  assert.equal(JSON.stringify(reopened.recursive.authority), authority);
});
