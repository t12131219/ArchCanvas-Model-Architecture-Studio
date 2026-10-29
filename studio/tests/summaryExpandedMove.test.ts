import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { webcrypto } from 'node:crypto';

const base = new URL('../public/preview/', import.meta.url);
const ctx = vm.createContext({ performance, TextEncoder, crypto: webcrypto });
const load = (path: string) => vm.runInContext(readFileSync(new URL(path, base), 'utf8'), ctx, { filename: path });
for (const name of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph']) load(`yworks_edge_router_lab/${name}.js`);
for (const { path } of JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json', import.meta.url), 'utf8')).files) load(path);
for (const name of ['studio-semantic','studio-documents','studio-authoring']) load(`yworks_edge_router_lab/${name}.js`);
const G = ctx.SummaryNativeSemantic, N = ctx.ArchCanvasSemanticView, E = ctx.SummaryEngine, W = ctx.ArchCanvasSummaryAuthoring;
const options = { budgetMs: 0, moveBudgetMs: 2000, refineCrossings: false, refinePlacement: false, refineChannels: false, refineFlow: false };

test('fully expanded Transformer edit copy moves without requiring unrelated pending routes to become complete', async () => {
  const ir = JSON.parse(readFileSync(new URL('data/semantic/0216717d966327f4.json', base), 'utf8'));
  const root = ir.nodes.find((n: any) => !n.parent).id;
  const result = N.prepare({ task: 'generic-build', ir, state: { ...N.state('overview'), moduleCuts: [{id: root, level:'source'}] }, options });
  assert.equal(N.accepts(result.graph, result.validation), true);
  assert.equal(result.graph.nodes.length, 3371);
  assert.ok(result.graph.edges.some((e: any) => e.failed || e.pendingRouting));
  const begun = await W.begin(result.graph), graph = begun.initialGraph;
  const original = JSON.stringify(graph), facts = JSON.stringify(graph.generic.ir), bindings = JSON.stringify(graph.edges.map((e: any) => e.binding));
  // A whole subtree translates its internal routes; no cosmetic full-graph
  // reroute is needed for a legal root movement with unrelated pending lanes.
  const moved = G.cloneGeometry(graph), target = moved.nodes.find((n: any) => n.id === root), x = target.x;
  assert.ok(E.move(moved, root, 8, 0, options).has(root), JSON.stringify(moved.lastMove));
  const checked = E.validateView(moved);
  assert.equal(E.acceptsView(moved, checked), true);
  assert.equal(target.x, x + 8);
  assert.equal(JSON.stringify(moved.generic.ir), facts);
  assert.equal(JSON.stringify(moved.edges.map((e: any) => e.binding)), bindings);
  assert.equal(JSON.stringify(graph), original, 'undo snapshot stays independent');
  assert.ok(moved.edges.some((e: any) => e.failed || e.pendingRouting), 'a move cannot claim pending routing completed');
  for (const expanded of [false, true]) {
    const local = G.cloneGeometry(graph);
    const node = local.nodes.find((n: any) => {
      if (!!n.expanded !== expanded || n.junction || !n.parent) return false;
      const parent = local.nodes.find((p: any) => p.id === n.parent);
      return parent && parent.x + parent.w - n.x - n.w > 12 && !local.nodes.some((p: any) => p.id !== n.id && p.parent === n.parent && p.x < n.x+n.w+8 && p.x+p.w > n.x+8 && p.y < n.y+n.h && p.y+p.h > n.y);
    });
    assert.ok(node, 'a legal local corridor exists');
    const before = node.x;
    assert.ok(E.move(local, node.id, 8, 0, options).has(node.id), `${node.id}: ${JSON.stringify(local.lastMove)}`);
    assert.equal(node.x, before + 8);
    assert.equal(E.acceptsView(local, E.validateView(local)), true);
    assert.equal(JSON.stringify(local.generic.ir), facts);
  }
  const forged = JSON.parse(JSON.stringify(moved));
  forged.edges[0].binding.target_port = 'forged';
  assert.equal(E.acceptsView(forged, E.validateView(forged)), false, 'pending paths cannot license changed source slots');
  const overlap = G.cloneGeometry(moved);
  const siblings = overlap.nodes.filter((n:any)=>!n.expanded&&!n.junction&&n.parent===overlap.nodes.find((n:any)=>!n.expanded&&!n.junction&&n.parent)?.parent);
  assert.ok(siblings.length > 1);
  siblings[1].x = siblings[0].x; siblings[1].y = siblings[0].y;
  assert.equal(E.acceptsView(overlap, E.validateView(overlap)), false, 'node collisions still reject');
});
