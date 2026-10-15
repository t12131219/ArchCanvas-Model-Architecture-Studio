import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';

const preview = fileURLToPath(new URL('../public/preview/', import.meta.url));
const enginePath = path.join(preview, 'yworks_edge_router_lab');
const plain = (value: any) => JSON.parse(JSON.stringify(value));
let response: any;
const context = vm.createContext({ performance, postMessage: (value: any) => { response = plain(value); } });
context.self = context;
context.importScripts = (...files: string[]) => files.forEach(file => vm.runInContext(readFileSync(path.join(enginePath, file), 'utf8'), context, { filename: file }));
vm.runInContext(readFileSync(path.join(enginePath, 'routing-worker.js'), 'utf8'), context);
const E = context.SummaryEngine, C = context.SummaryConstraints, F = context.SummaryRecursive, task = context.SummaryFrontierTask;
const catalog = JSON.parse(readFileSync(path.join(preview, 'data/catalog.json'), 'utf8'));
const transformer = catalog.cases.find((item: any) => item.id === '01093cc06a87b35a');
function fixture() {
  const sources = Object.fromEntries(transformer.views.filter((view: any) => view.json).map((view: any) =>
    [view.key, C.initialize(JSON.parse(readFileSync(path.join(preview, view.json), 'utf8')))]));
  return F.build(F.create(sources));
}
function execute(graph: any, transition: any) { return task.run(E.clone(graph), transition, {}); }
function valid(result: any) {
  assert.equal(result.ok, true);
  assert.equal(result.failed, 0);
  assert.equal(result.validation.source.ok, true);
  assert.equal(result.validation.layout.ok, true);
  assert.ok(result.validation.edges.every(([, check]: any) => check.ok));
}

test('worker and fallback share the same validated frontier transaction; input authority stays intact', () => {
  const original = fixture(), before = JSON.stringify(original), transition = { type: 'expand', ids: ['dec.cross'], expanded: true };
  const fallback = execute(original, transition); valid(fallback);
  context.self.onmessage({ data: { requestId: 41, task: 'frontier', graph: E.clone(original), transition, options: {} } });
  assert.equal(response.requestId, 41); valid(response);
  assert.deepEqual(plain(fallback.graph), response.graph);
  assert.equal(JSON.stringify(original), before, 'worker copies must not mutate the committed graph or undo snapshot');
  assert.deepEqual(plain(fallback.graph.recursive.authority), plain(original.recursive.authority));
  assert.ok(fallback.timing.total >= fallback.timing.route);
});

test('frontier task preserves descendants across collapse, recognizes no-ops and supports full expansion', () => {
  const original = fixture();
  const expanded = execute(original, { type: 'expand', ids: ['dec.self', 'dec.self.sdpa'], expanded: true }); valid(expanded);
  const graph = expanded.graph;
  const same = execute(graph, { type: 'toggle', id: 'dec.self', expanded: true });
  assert.equal(same.unchanged, true);
  assert.deepEqual(plain(same.graph), plain(graph));
  const closed = execute(graph, { type: 'toggle', id: 'dec.self', expanded: false }); valid(closed);
  assert.equal(F.opened(closed.graph.recursive, 'dec.self.sdpa'), true);
  const reopened = execute(closed.graph, { type: 'toggle', id: 'dec.self', expanded: true }); valid(reopened);
  assert.deepEqual(plain(reopened.graph.nodes), plain(graph.nodes));
  assert.deepEqual(plain(reopened.graph.edges.map((edge: any) => edge.route)), plain(graph.edges.map((edge: any) => edge.route)));
  const all = execute(reopened.graph, { type: 'all', expanded: true }); valid(all);
  assert.equal(all.graph.nodes.length, all.graph.recursive.authority.detail.nodes.length);
  assert.equal(execute(all.graph, { type: 'all', expanded: true }).unchanged, true);
  const folded = execute(all.graph, { type: 'all', expanded: false }); valid(folded);
  assert.equal(execute(folded.graph, { type: 'all', expanded: false }).unchanged, true);
  assert.deepEqual(plain(folded.graph.recursive.authority), plain(original.recursive.authority));
});

test('invalid requests and forged bindings reject a transaction without touching its input snapshot', () => {
  const graph = fixture(), before = JSON.stringify(graph);
  assert.throws(() => execute(graph, { type: 'expand', ids: ['missing'], expanded: true }), /不存在/);
  assert.throws(() => execute(graph, { type: 'unknown' }), /不支持/);
  const forged = E.clone(graph);
  forged.edges[0].binding = { forged: true };
  assert.throws(() => execute(forged, undefined), /binding|source|receipt|源码/);
  assert.equal(JSON.stringify(graph), before);
});
