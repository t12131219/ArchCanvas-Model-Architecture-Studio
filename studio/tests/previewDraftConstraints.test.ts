import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';

// Execute only the formal vendored browser engine, without a prototype server
// or importing model source. The real catalog supplies source-owned receipts.
const preview = fileURLToPath(new URL('../public/preview/', import.meta.url));
const context = vm.createContext({});
for (const file of ['router.js', 'physical-ports.js', 'junction-markers.js', 'route-labels.js',
  'source-contracts.js', 'semantic-constraints.js', 'graph-engine.js', 'recursive-graph.js']) {
  vm.runInContext(readFileSync(path.join(preview, 'yworks_edge_router_lab', file), 'utf8'), context, { filename: file });
}
const E = context.SummaryEngine, F = context.SummaryRecursive, C = context.SummaryConstraints;
const catalog = JSON.parse(readFileSync(path.join(preview, 'data/catalog.json'), 'utf8'));
const model = catalog.cases.find((item: any) => item.id === 'e40ad1504991acea');
function fixture() {
  const sources = Object.fromEntries(model.views.filter((view: any) => view.json).map((view: any) =>
    [view.key, C.initialize(JSON.parse(readFileSync(path.join(preview, view.json), 'utf8')))]));
  const graph = F.build(F.create(sources));
  assert.equal(C.validateSource(graph).ok, true);
  return graph;
}
function sourceEdge(graph: any) {
  return graph.edges.find((edge: any) => !graph.junctionMarkers.some((marker: any) => marker.edges.includes(edge.id))
    && (edge.projection.originals ?? [edge.projection.original]).length === 1);
}
function sourceRemoval(graph: any, edge: any) {
  const id = edge.projection.original;
  const raw = graph.recursive.authority.detail.edges.find((item: any) => item.id === id);
  return { kind: 'remove-connection', id, binding: E.clone(raw.binding) };
}

test('recursive visual reconnect retains exact source binding while changing its visible endpoint', () => {
  const graph = fixture(), edge = sourceEdge(graph), binding = JSON.stringify(edge.binding), projection = JSON.stringify(edge.projection);
  const target = graph.nodes.find((node: any) => node.id !== edge.target && node.id !== edge.source && !node.expanded);
  E.reconnect(graph, edge, 'target', target.id, { side: 'left', fraction: 0.5 });
  assert.equal(edge.draft, true); assert.equal(edge.target, target.id);
  assert.equal(JSON.stringify(edge.binding), binding); assert.equal(JSON.stringify(edge.projection), projection);
  assert.equal(C.validateSource(graph).ok, true);
});

test('draft flags cannot bless forged bindings, changed projections, identities, or missing source receipts', () => {
  const damages = [
    (_graph: any, edge: any) => { edge.binding = { forged: true }; },
    (_graph: any, edge: any) => { edge.projection.original = 'forged'; },
    (_graph: any, edge: any) => { edge.projection.originals = ['forged']; },
    (_graph: any, edge: any) => { edge.id = 'forged'; },
    (graph: any, edge: any) => { delete graph.recursiveReceipt.edges[edge.id]; },
  ];
  for (const draft of [false, true]) for (const damage of damages) {
    const graph = fixture(), edge = sourceEdge(graph); edge.draft = draft; damage(graph, edge);
    assert.equal(C.validateSource(graph).ok, false);
  }
});

test('a registered source edge cannot erase its projection and reuse a deletion audit to forge its binding', () => {
  const graph = fixture(), edge = sourceEdge(graph);
  graph.sourceDraftOperations = [sourceRemoval(graph, edge)];
  edge.draft = true; delete edge.projection; edge.binding = { forged: true };
  assert.equal(C.validateSource(graph).ok, false);
});

test('visual source deletion requires the exact original id and binding in its audit', () => {
  const graph = fixture(), edge = sourceEdge(graph), removal = sourceRemoval(graph, edge);
  graph.edges = graph.edges.filter((item: any) => item !== edge);
  assert.equal(C.validateSource(graph).ok, false);
  graph.sourceDraftOperations = [{ ...removal, binding: { forged: true } }];
  assert.equal(C.validateSource(graph).ok, false);
  graph.sourceDraftOperations = [removal];
  assert.equal(C.validateSource(graph).ok, true);
});

test('a new visual draft remains separate from audited source edges and survives branch rebuilding', () => {
  const graph = fixture(), edge = sourceEdge(graph), authority = JSON.stringify(graph.recursive.authority);
  graph.edges.push({ id: 'visual-new', source: edge.source, target: edge.target, draft: true,
    binding: { evidence: 'visual edit draft; no source model writeback' },
    fixedSource: { side: 'right', fraction: 0.5 }, fixedTarget: { side: 'left', fraction: 0.5 },
    route: E.clone(edge.route), waypoints: [], arrow: 'target', style: 'orthogonal' });
  C.initialize(graph); assert.equal(C.validateSource(graph).ok, true);
  const rebuilt = F.toggle(graph, 'highway.layer0', true);
  assert.equal(C.validateSource(rebuilt).ok, true);
  assert.equal(rebuilt.edges.filter((item: any) => item.id === 'visual-new').length, 1);
  const expanded = F.all(rebuilt, true);
  assert.equal(C.validateSource(expanded).ok, true);
  assert.equal(expanded.edges.filter((item: any) => item.id === 'visual-new').length, 1);
  assert.equal(JSON.stringify(expanded.recursive.authority), authority, 'a new visual arrow must preserve all original source nodes and edges');
});

test('reconnected audited drafts survive expansion and JSON restoration with their source projection', () => {
  const graph = fixture(), edge = sourceEdge(graph), binding = JSON.stringify(edge.binding), projection = JSON.stringify(edge.projection), authority = JSON.stringify(graph.recursive.authority);
  const target = graph.nodes.find((node: any) => node.id !== edge.target && node.id !== edge.source && !node.expanded);
  E.reconnect(graph, edge, 'target', target.id, { side: 'left', fraction: 0.5 });
  const rebuilt = F.toggle(graph, 'highway.layer0', true), restored = E.clone(rebuilt);
  assert.equal(C.validateSource(restored).ok, true);
  const saved = restored.edges.find((item: any) => item.id === edge.id);
  assert.equal(JSON.stringify(saved.binding), binding); assert.equal(JSON.stringify(saved.projection), projection);
  assert.equal(saved.draft, true);
  const expanded = F.all(restored, true);
  assert.equal(C.validateSource(expanded).ok, true);
  assert.equal(JSON.stringify(expanded.edges.find((item: any) => item.id === edge.id).binding), binding);
  assert.equal(JSON.stringify(expanded.recursive.authority), authority);
});
