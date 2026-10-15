import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

// Exercise the actual application loader and migration, rather than supplying
// the engine with receipts that the application itself previously discarded.
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const assets = path.join(root, 'studio/public/preview/yworks_edge_router_lab');
const context = vm.createContext({ TextEncoder, TextDecoder, console });
for (const name of ['router.js', 'physical-ports.js', 'junction-markers.js', 'route-labels.js',
  'source-contracts.js', 'semantic-constraints.js', 'graph-engine.js', 'recursive-graph.js', 'source-adapter.js']) {
  vm.runInContext(fs.readFileSync(path.join(assets, name), 'utf8'), context, { filename: name });
}
const F = context.SummaryRecursive, E = context.SummaryEngine, A = context.SummarySourceAdapter;
const bundle = JSON.parse(fs.readFileSync(path.join(root, 'docs/evidence/agent-source-rules-20261015/act-detrvae.bundle.json')));
const generated = A.sources(bundle), keys = Object.keys(generated);
assert.ok(keys.length > 2, 'nested imported source must supply intermediate folded receipts');
context.importedSources = new Map([[bundle.id, generated]]);
const calls = [];
context.asset = async (descriptor, item) => { calls.push([item.id, descriptor.key]); return generated[descriptor.key]; };
context.lab = () => ({ builtin: true });
const app = fs.readFileSync(path.join(assets, 'app.js'), 'utf8');
const start = app.indexOf('  async function caseSources('), end = app.indexOf('  async function openCase(', start);
assert.ok(start >= 0 && end > start, 'the shared application loader must be present');
vm.runInContext(app.slice(start, end) + '\nglobalThis.readCaseSources=caseSources;', context, { filename: 'app.js:caseSources' });
const item = { id: bundle.id, views: [{ key: 'overview' }, { key: 'detailed' }] };
const loaded = await context.readCaseSources(item);
assert.deepEqual(Object.keys(loaded), keys);
assert.equal(calls.length, 0, 'imported receipts must not be truncated to the two menu entries');
assert.match(app.slice(end, app.indexOf('  function ', end)), /await caseSources\(c,builtin\)/);
assert.match(app.slice(app.indexOf('  async function studioLoad(')), /await caseSources\(c,!!c\.views\[0\]\?\.builtin\)/);
assert.equal((await context.readCaseSources({ ...item, id: 'catalog-only' })).detailed, generated.detailed);
assert.deepEqual(calls, [['catalog-only', 'overview'], ['catalog-only', 'detailed']]);
assert.equal((await context.readCaseSources({ id: 'sandbox', views: [] }, true)).overview.builtin, true);
console.log('PASS application loader retains all source depth receipts with a two-entry menu');

const fresh = F.create(loaded);
// Model the previous application state: the authority and cached frontier were
// made from just the menu views, before the source presentation migration.
let old = F.build(F.create({ overview: generated.overview, detailed: generated.detailed }));
old.sourceAdapter.presentationVersion--;
old.recursive.authority.detail.sourceAdapter.presentationVersion--;
const state = old.recursive.state;
const branch = bundle.ir.nodes.find(node => node.label === 'for layer in self.layers');
assert.ok(branch);
const byId = new Map(bundle.ir.nodes.map(node => [node.id, node]));
let current = branch;
while (current) { if (!state.open.includes(current.id)) state.open.push(current.id); current = byId.get(current.parent); }
state.layouts['preserved-user-layout'] = { x: 17, y: -9 };
state.studioPresentation = { nodes: { [branch.id]: { alias: 'Retained reviewed name' } } };
const preserved = JSON.stringify({ open: state.open, folded: state.folded, layouts: state.layouts, presentation: state.studioPresentation });
state.frontiers.badLegacyReceipt = { nodes: [], edges: [], sentinel: true };
old.recursive.authority = E.clone(fresh.authority);
const upgraded = F.upgrade(old);
assert.notEqual(upgraded, old, 'old source renderer must rebuild its projected geometry');
assert.equal(JSON.stringify({ open: upgraded.recursive.state.open, folded: upgraded.recursive.state.folded,
  layouts: upgraded.recursive.state.layouts, presentation: upgraded.recursive.state.studioPresentation }), preserved);
assert.equal(Object.keys(upgraded.recursive.state.frontiers).length, 0);
assert.equal(upgraded.recursive.authority.variants.length, keys.length);
assert.equal(upgraded.sourceAdapter.presentationVersion, generated.detailed.sourceAdapter.presentationVersion);
assert.equal(upgraded.nodes.find(node => node.id === branch.id)?.expanded, true);
const routeOptions = { margin: 6, stub: 28, bendCost: 40, crossingCost: 450, overlapCost: 2,
  edgeSpacing: 12, preserve: false, sides: 'any', grid: 0, style: 'orthogonal' };
const before = JSON.stringify(upgraded.recursive.authority);
const routed = F.route(upgraded, routeOptions), checked = E.validateView(upgraded);
assert.equal(routed.failed, 0);
assert.equal(checked.source.ok, true, checked.source.violations.join('; '));
assert.equal(checked.layout.ok, true, checked.layout.violations.join('; '));
assert.deepEqual(JSON.parse(JSON.stringify(checked.edges.filter(([, value]) => !value.ok))), []);
assert.equal(JSON.stringify(upgraded.recursive.authority), before, 'routing must preserve all canonical authority');
assert.equal(F.upgrade(upgraded), upgraded, 'new source geometry must not rebuild again');
console.log('PASS old depth-truncated frontiers migrate, retain edits and expand with strict lane validation');

const canvasIndex = process.argv.indexOf('--browser-canvas');
if (canvasIndex >= 0) {
  const exported = JSON.parse(fs.readFileSync(process.argv[canvasIndex + 1]));
  const graph = exported.graph;
  graph.recursive.authority = E.clone(fresh.authority);
  const migrated = F.upgrade(graph);
  assert.notEqual(migrated, graph);
  const target = migrated.nodes.find(node => node.id === branch.id);
  assert.ok(target && !target.expanded);
  const expanded = F.toggle(migrated, target.id, true);
  const result = F.route(expanded, routeOptions), validation = E.validateView(expanded);
  assert.equal(result.failed, 0);
  assert.equal(validation.source.ok, true);
  assert.equal(validation.layout.ok, true, validation.layout.violations.join('; '));
  assert.deepEqual(JSON.parse(JSON.stringify(validation.edges.filter(([, value]) => !value.ok))), []);
  console.log('PASS actual exported browser frontier migrates and opens the previously refused nested loop');
}
