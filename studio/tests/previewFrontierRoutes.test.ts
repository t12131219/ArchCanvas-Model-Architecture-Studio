import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';

// Use the shipped engine and source-grounded catalog; no model code executes.
const preview = fileURLToPath(new URL('../public/preview/', import.meta.url));
const context = vm.createContext({});
for (const file of ['router.js', 'physical-ports.js', 'junction-markers.js', 'route-labels.js',
  'source-contracts.js', 'semantic-constraints.js', 'graph-engine.js', 'recursive-graph.js']) {
  vm.runInContext(readFileSync(path.join(preview, 'yworks_edge_router_lab', file), 'utf8'), context, { filename: file });
}
const E = context.SummaryEngine, F = context.SummaryRecursive, C = context.SummaryConstraints;
const catalog = JSON.parse(readFileSync(path.join(preview, 'data/catalog.json'), 'utf8'));
const transformer = catalog.cases.find((item: any) => item.id === '01093cc06a87b35a');
const plain = (value: any) => JSON.parse(JSON.stringify(value));
const routed = new Map<string, any>();

function fixture(...open: string[]) {
  const key = open.join('|');
  if (routed.has(key)) return E.clone(routed.get(key));
  const sources = Object.fromEntries(transformer.views.filter((view: any) => view.json).map((view: any) =>
    [view.key, C.initialize(JSON.parse(readFileSync(path.join(preview, view.json), 'utf8')))]));
  const doc = F.create(sources);
  for (const id of open) {
    let node = doc.authority.detail.nodes.find((node: any) => node.id === id);
    assert.ok(node && F.children(doc.authority, id).length, `${id} must be an actual expandable container`);
    while (node) {
      if (F.children(doc.authority, node.id).length && !doc.state.open.includes(node.id)) doc.state.open.push(node.id);
      node = doc.authority.detail.nodes.find((parent: any) => parent.id === node.parent);
    }
  }
  const graph = F.build(doc);
  assert.equal(F.route(graph).failed, 0);
  const checked = E.validateView(graph);
  assert.equal(checked.source.ok, true, checked.source.violations.join('; '));
  assert.equal(checked.layout.ok, true, checked.layout.violations.join('; '));
  assert.ok(checked.edges.every(([, result]: any) => result.ok), JSON.stringify(checked.edges));
  assert.equal(checked.routing.contacts.length, 0, 'mixed frontiers must reserve clear frame lanes');
  routed.set(key, E.clone(graph));
  return graph;
}

test('partial Decoder expansion retains one clear Memory bus below K/V', () => {
    const graph = fixture('dec.cross'), frame = graph.nodes.find((node: any) => node.id === 'dec.cross');
    const branches = graph.edges.filter((edge: any) => edge.source === 'enc.memory.value'
      && ['dec.cross.k', 'dec.cross.v'].includes(edge.target));
    assert.equal(branches.length, 2);
    assert.equal(branches[0].contract.wire, branches[1].contract.wire);
    const bus = branches[0].route[1];
    for (const edge of branches) {
      const operand = graph.nodes.find((node: any) => node.id === edge.target);
      assert.equal(edge.route.length, 4, 'Memory needs a trunk, shared horizontal bus and one arrow terminal');
      assert.deepEqual(plain(edge.route.slice(0, 2)), plain(branches[0].route.slice(0, 2)));
      assert.ok(bus.y > operand.y + operand.h && bus.y < frame.y + frame.h,
        'the K/V bus belongs below the operands, away from the container title');
      assert.equal(edge.route.at(-1).x, operand.x + operand.w / 2);
      assert.equal(edge.route.at(-1).y, operand.y + operand.h);
      for (const gate of C.activeGates(graph, edge)) {
        assert.equal(gate.side, 'left');
        const owner = graph.nodes.find((node: any) => node.id === gate.frame);
        assert.ok(Math.abs(C.gatePoint(owner, gate).y - bus.y) < 1e-5,
          'nested Decoder and cross-attention gates must share the consumer bus');
      }
      const raw = graph.recursive.authority.detail.edges.find((raw: any) => raw.id === edge.projection.original);
      assert.deepEqual(plain(edge.binding), plain(raw.binding));
    }
    assert.ok(graph.junctionMarkers.some((marker: any) => marker.owner === 'enc.memory.value'
      && marker.edges.every((id: string) => branches.some((edge: any) => edge.id === id))
      && E.junctionPoint(graph, marker)), 'the shared value keeps its actual source-authorized fork');
    assert.equal(F.toggle(graph, 'dec.cross.sdpa', true), null,
      'the source represents cross-attention SDPA as a leaf, so it cannot add another expansion depth');
});

test('folded normalization fans out without a reversed elbow or a constrained border route', () => {
  const graph = fixture('dec.cross');
  const edge = graph.edges.find((edge: any) => edge.source === 'dec.norm1' && edge.target === 'dec.cross.q');
  assert.equal(edge.route.length, 4);
  assert.equal(edge.route[0].x, edge.route[1].x);
  assert.equal(edge.route[1].y, edge.route[2].y);
  assert.equal(edge.route[2].x, edge.route[3].x);
  assert.ok(edge.route[0].y > edge.route[1].y && edge.route[2].y > edge.route[3].y,
    'Q receives a monotone upward arrow from the folded normalization');
  const checking = C.validationContext(graph);
  const stem = C.sharedStemPoint(graph, edge, checking);
  const preferred = C.sharedStemPoint(graph, edge, { ...checking, boundaryLanes: true });
  assert.deepEqual(plain(stem), plain(preferred), 'stroke validation and lane routing must agree on the fork');
  assert.equal(F.route(graph).routed, 0, 'a second pass must preserve the complete legal frontier');
});

test('deep mixed attention keeps Encoder residuals clear of both child and enclosing frames', () => {
  const graph = fixture('dec.cross', 'dec.norm1', 'enc.self.sdpa');
  assert.ok(graph.nodes.some((node: any) => node.id === 'enc.self.sdpa.qkt'));
  const residual = graph.edges.find((edge: any) => edge.id === 'binding-005-4');
  const self = graph.nodes.find((node: any) => node.id === 'enc.self');
  const parent = graph.nodes.find((node: any) => node.id === self.parent);
  assert.ok(parent.y + parent.h - self.y - self.h >= 32,
    'nested frame lanes need usable space between their preferred clearances');
  assert.equal(C.laneContacts(graph, residual).length, 0);
  assert.equal(residual.route.length, 5, 'the residual branches once after the recorded parent entry');
  assert.ok(residual.route[1].y - self.y - self.h >= 12 - 1e-5);
  assert.ok(self.x - residual.route[2].x >= 12 - 1e-5);
  assert.equal(F.route(graph).routed, 0);
});

test('sequential Decoder expansions keep perpendicular residual gates on clear orthogonal lanes', () => {
  let graph = fixture();
  for (const id of ['dec.cross', 'dec.ffn', 'dec.norm2', 'dec.self', 'dec.self.sdpa', 'dec.norm1']) {
    assert.ok(F.children(graph.recursive.authority, id).length, `${id} is a real container`);
    graph = F.toggle(graph, id, true);
    assert.equal(F.route(graph).failed, 0, id);
    const checked = E.validateView(graph);
    assert.equal(checked.source.ok, true, id);
    assert.equal(checked.layout.ok, true, id + ': ' + checked.layout.violations.join('; '));
    assert.ok(checked.edges.every(([, result]: any) => result.ok), id);
    assert.equal(checked.routing.contacts.length, 0, id + ': ' + JSON.stringify(checked.routing.contacts));
    assert.equal(checked.routing.constrained.length, 0, id);
  }
  for (const id of ['binding-012-11', 'binding-075-74']) {
    const residual = graph.edges.find((edge: any) => edge.id === id);
    assert.equal(residual.route.length, 5, 'a clear residual needs one horizontal turn between recorded gates');
    assert.deepEqual(plain(residual.binding), plain(graph.recursive.authority.detail.edges
      .find((edge: any) => edge.id === residual.projection.original).binding));
  }
});

test('the registered full view retains source glyph positions and repairs cramped residual paths', () => {
  const graph = F.all(fixture('dec.cross'), true);
  const source = graph.recursive.authority.detail;
  const bounds = (nodes: any[]) => nodes.map((node: any) => [node.id, node.x, node.y, node.w, node.h]);
  assert.deepEqual(plain(bounds(graph.nodes)), plain(bounds(source.nodes)));
  assert.equal(C.validateSource(graph).ok, true);
  assert.equal(F.route(graph).failed, 0);
  const checked = E.validateView(graph);
  assert.equal(checked.layout.ok, true);
  assert.equal(checked.routing.contacts.length, 0);
  assert.equal(checked.routing.constrained.length, 0);
  for (const id of ['binding-005-4', 'binding-012-11']) {
    const edge = graph.edges.find((edge: any) => edge.id === id);
    assert.equal(edge.route.length, 5);
    assert.deepEqual(plain(edge.binding), plain(source.edges.find((edge: any) => edge.id === id).binding));
    assert.equal(C.laneContacts(graph, edge).length, 0,
      'the original 10px residual lane must move to the legal 11px parent/child corridor');
  }
});

test('closing and reopening a branch restores its geometry and retained descendant choices', () => {
  let graph = F.toggle(fixture('dec.cross'), 'enc.self', true);
  assert.equal(F.route(graph).failed, 0);
  graph = F.toggle(graph, 'enc.self.sdpa', true);
  assert.equal(F.route(graph).failed, 0);
  assert.ok(graph.nodes.some((node: any) => node.id === 'enc.self.sdpa.qkt'));
  const nodes = plain(graph.nodes), routes = plain(graph.edges.map((edge: any) => [edge.id, edge.route]));
  const authority = JSON.stringify(graph.recursive.authority);
  graph = F.toggle(graph, 'enc.self', false);
  assert.ok(!graph.nodes.some((node: any) => node.id === 'enc.self.sdpa'));
  assert.equal(F.opened(graph.recursive, 'enc.self.sdpa'), true);
  graph = F.toggle(graph, 'enc.self', true);
  assert.ok(graph.nodes.some((node: any) => node.id === 'enc.self.sdpa.qkt'));
  assert.deepEqual(plain(graph.nodes), nodes);
  assert.deepEqual(plain(graph.edges.map((edge: any) => [edge.id, edge.route])), routes);
  assert.equal(JSON.stringify(graph.recursive.authority), authority);
  assert.equal(F.route(graph).routed, 0);
});

test('older cached frontiers rebuild the bad gates while retaining local edits and source identities', () => {
  const graph = fixture('dec.cross');
  const doc = graph.recursive, authority = JSON.stringify(doc.authority);
  doc.presentationVersion = 13;
  doc.state.layouts['dec.cross'] = { 'dec.cross.k': { x: 2, y: 0 } };
  const choices = plain(doc.state.open), offsets = plain(doc.state.layouts);
  doc.state.captionAnchors = { sample: { mode: 'ratio', ratio: 0.4, gap: 12 } };
  F.remember(graph);
  const updated = F.upgrade(graph);
  assert.equal(updated.recursive.presentationVersion, 18);
  assert.deepEqual(plain(updated.recursive.state.open), choices);
  assert.deepEqual(plain(updated.recursive.state.layouts), offsets);
  assert.deepEqual(plain(updated.recursive.state.captionAnchors.sample), { mode: 'ratio', ratio: 0.4, gap: 12 });
  assert.equal(JSON.stringify(updated.recursive.authority), authority);
  assert.equal(C.validateSource(updated).ok, true);
  const damaged = E.clone(updated);
  damaged.edges.find((edge: any) => edge.source === 'enc.memory.value').binding = { forged: true };
  assert.equal(C.validateSource(damaged).ok, false, 'visual route repair must not weaken source receipts');
});
