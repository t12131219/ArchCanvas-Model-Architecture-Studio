// Recompute semantic projections from the formal checkout, then compare with
// read-only browser DOM evidence. This does not certify physical route layout.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../..');
const base = path.join(root, 'studio/public/preview');
const ctx = vm.createContext({ performance });
const load = p => vm.runInContext(fs.readFileSync(path.join(base, p), 'utf8'), ctx, { filename: p });
for (const n of ['router', 'physical-ports', 'junction-markers', 'route-labels', 'source-contracts', 'semantic-constraints', 'graph-engine', 'recursive-graph']) load('yworks_edge_router_lab/' + n + '.js');
for (const row of JSON.parse(fs.readFileSync(path.join(root, 'docs/summary-native-view-manifest-20261028.json'))).files) load(row.path);
load('yworks_edge_router_lab/studio-semantic.js');
const catalog = JSON.parse(fs.readFileSync(path.join(base, 'data/semantic/studio-catalog.json')));
const entry = catalog.models.find(m => m.id === '0216717d966327f4');
const ir = JSON.parse(fs.readFileSync(path.join(base, 'data/semantic', entry.ir.path)));
const G = ctx.SummaryNativeSemantic, N = ctx.ArchCanvasSemanticView;
const model = ir.nodes.find(n => !n.parent).id;
const encode = ir.nodes.find(n => n.label === 'self.encode').id;
const decode = ir.nodes.find(n => n.label === 'self.decode').id;
const attention = ir.nodes.find(n => n.label === 'self_attn' && n.id.startsWith(encode + '/')).id;
const cut = (id, level, depth) => ({ id, level, ...(depth === undefined ? {} : { depth }) });
const enc = (level, depth) => cut(encode, level, depth);
const att = (level, depth) => [enc('f1'), cut(attention, level, depth)];
const both = depth => [enc('source'), cut(decode, 'source', depth)];
const cases = {
  '01-global-f0': [],
  '02-encoder-f1-decoder-f0': [enc('f1')],
  '03-attention-roles': att('roles'),
  '04-attention-detailed': att('detailed'),
  '05-attention-source-depth2': att('source', 2),
  '06-attention-all-atoms': att('source'),
  '06b-attention-after-route-continuation': att('source'),
  '06c-attention-source-readable': att('source'),
  '06d-attention-scaled-dot-source-detail': att('source'),
  '07-encoder-source-depth2': [enc('source', 2)],
  '08-encoder-source-depth6': [enc('source', 6)],
  '09-encoder-all-atoms-decoder-f0': [enc('source')],
  '10-encoder-all-decoder-depth6': both(6),
  '11-encoder-all-decoder-depth8': both(8),
  '12-both-all-atoms': both(),
  '13-root-all-atoms': [cut(model, 'source'), ...both()],
  '13a-root-after-route-continuation': [cut(model, 'source'), ...both()],
  '13b-root-source-readable': [cut(model, 'source'), ...both()],
  '13c-decoder-cross-attention-source': [cut(model, 'source'), ...both()],
};
const exact = (a, b) => JSON.stringify([...a].sort()) === JSON.stringify([...b].sort());
// This browser started from a saved F1 view. F0 resets module cuts while
// preserving these original Summary presentation preferences (frontier()).
const baselineState = () => ({ ...N.state('overview'), paperRolePathStages: true, paperRoleSourceFrames: true });
const canonicalEdges = new Map(ir.edges.map(e => [e.id, e]));
const parent = new Map(ir.nodes.map(n => [n.id, n.parent]));
const within = (id, owner) => { while (id) { if (id === owner) return true; id = parent.get(id); } return false; };
const rows = [];
const projectionCache = new Map();
const projectCached = (cuts, mode) => {
  const key = JSON.stringify({ cuts, mode });
  if (!projectionCache.has(key)) projectionCache.set(key, G.project(ir, { ...baselineState(), mode, moduleCuts: cuts }));
  return projectionCache.get(key);
};
for (const [name, cuts] of Object.entries(cases)) {
  const file = path.join(__dirname, name + '.json');
  if (!fs.existsSync(file)) continue;
  const browser = JSON.parse(fs.readFileSync(file));
  const before = JSON.stringify(ir);
  const projected = projectCached(cuts, browser.evidenceMode || 'merged');
  const nodeIDs = projected.nodes.map(n => n.id);
  assert.ok(exact(browser.ids, nodeIDs), name + ': rendered IDs differ from semantic projection ' + JSON.stringify({missing:nodeIDs.filter(id=>!browser.ids.includes(id)),extra:browser.ids.filter(id=>!nodeIDs.includes(id)),attention}));
  assert.equal(browser.edges, projected.edges.length, name + ': edge count');
  assert.equal(browser.source, 'true', name + ': browser source constraint');
  assert.equal(JSON.stringify(ir), before, name + ': projection mutated source IR');
  for (const [ledger, all] of [[projected.node_accounting, ir.nodes], [projected.edge_accounting, ir.edges]]) {
    const ids = Object.values(ledger).flat();
    assert.equal(ids.length, all.length, name + ': accounting count');
    assert.equal(new Set(ids).size, all.length, name + ': accounting duplicate');
    assert.ok(exact(ids, all.map(n => n.id)), name + ': accounting coverage');
  }
  if (!cuts.some(c => c.id === decode || c.id === model)) {
    const baseline = projectCached([], browser.evidenceMode || 'merged');
    assert.ok(exact(browser.ids.filter(id => within(id, decode)), baseline.nodes.map(n => n.id).filter(id => within(id, decode))), name + ': decoder did not stay F0');
  }
  let checkedExactBindings = 0;
  if (name.startsWith('13')) {
    assert.ok(exact(browser.ids, ir.nodes.map(n => n.id)), 'full root must expose every original source node');
    assert.ok(exact(browser.edgeBindings.map(e => e.id), ir.edges.map(e => e.id)), 'full root must expose every original dependency');
    for (const e of browser.edgeBindings) {
      const raw = canonicalEdges.get(e.id);
      for (const key of ['source', 'target']) assert.equal(e[key], raw[key], e.id + ':' + key);
      for (const key of ['source_port', 'target_port', 'kind', 'evidence']) assert.equal(e.binding[key], raw[key], e.id + ':' + key);
      checkedExactBindings++;
    }
  }
  rows.push({ name, nodes: browser.nodes, edges: browser.edges, sourceValid: true, nodeAndEdgeAccounting: true, decoderF0Unchanged: !cuts.some(c => c.id === decode || c.id === model) ? true : null, checkedExactBindings, layoutValid: browser.layout === 'true', invalidRoutes: browser.invalid.length, routing: browser.routing || null });
}
const result = { model: 'Transformer', originalNodes: ir.nodes.length, originalEdges: ir.edges.length, renderer: G.VERSION, note: 'Source validation is against the imported canonical IR; Python source parsing and model execution were not run in this test.', rows };
fs.writeFileSync(path.join(__dirname, 'source-verification.json'), JSON.stringify(result, null, 2));
console.log(JSON.stringify(result, null, 2));
