import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { webcrypto } from 'node:crypto';
import vm from 'node:vm';

const context = vm.createContext({ performance, TextEncoder, crypto: webcrypto });
function load(path: string) { vm.runInContext(readFileSync(new URL('../public/preview/' + path, import.meta.url), 'utf8'), context, { filename: path }); }
for (const name of ['router', 'physical-ports', 'junction-markers', 'route-labels', 'source-contracts', 'semantic-constraints', 'graph-engine', 'recursive-graph']) load('yworks_edge_router_lab/' + name + '.js');
for (const { path } of JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json', import.meta.url), 'utf8')).files) load(path);
for (const name of ['studio-semantic', 'studio-documents', 'studio-authoring']) load('yworks_edge_router_lab/' + name + '.js');
const W = context.ArchCanvasSummaryAuthoring, D = context.ArchCanvasSummaryDocuments, A = context.SemanticAuthoring, N = context.ArchCanvasSemanticView;
const presets = JSON.parse(readFileSync(new URL('../public/preview/data/semantic/authoring-presets.json', import.meta.url), 'utf8')).modules;
const copy = (value: any) => JSON.parse(JSON.stringify(value));
const options = { refineCrossings: false, refinePlacement: false, refineChannels: false, refineFlow: false, budgetMs: 1000 };
function graph(result: any) {
  const { parsed, record } = result;
  const built = N.prepare({ task: 'generic-build', ir: parsed.ir, state: parsed.state, extra: { authoring: parsed.authoring }, options });
  assert.equal(N.accepts(built.graph, built.validation), true);
  return W.attach(built.graph, record);
}
const blank = async () => graph(await W.begin(null, { blank: true }));
async function edit(g: any, op: any) { return graph(await W.apply(g, op, presets)); }

test('blank authoring has an explicit independent identity and never acquires source authority', async () => {
  const g = await blank(), record = W.record(g), restored = await D.restore(record);
  assert.match(record.id, /^summary-authoring-/); assert.equal(record.document.schema, 'semantic-authoring/1');
  assert.equal(record.origin, null); assert.equal(g.sourceAdapter, undefined);
  assert.equal(g.importedDocument.sourceVerified, false); assert.equal(g.sourceProfile.modelExecuted, false);
  assert.equal(D.matches(g, restored.parsed), true); assert.equal(D.checkRendering(g), true);
});

test('precise connections refuse occupied inputs, explicitly replace, rewire and leave failed transactions intact', async () => {
  let g = await blank();
  for (const [role, label] of [['input', 'first'], ['input', 'second'], ['output', 'last']]) g = await edit(g, { action: 'interface', role, label });
  const [first, second, last] = g.generic.authoring.nodes.map((n: any) => n.id), base = copy(g);
  const panel = structuredClone(W.inspector(g));
  assert.equal(Object.hasOwn(panel.nodes[0], 'constructor'), false);
  assert.ok([first, second, last].every((id: string) => g.nodes.some((n: any) => n.id === id)), 'root enclosure stays open after rebuilding edits');
  g = await edit(g, { action: 'connect', source: { node: first, port: 'out' }, target: { node: last, port: 'in' } });
  const before = JSON.stringify(g);
  await assert.rejects(W.apply(g, { action: 'connect', source: { node: second, port: 'out' }, target: { node: last, port: 'in' } }), /已有连接/);
  await assert.rejects(W.apply(g, { action: 'connect', source: { node: second, port: 'invented' }, target: { node: last, port: 'in' }, replace: true }), /端口槽位/);
  assert.equal(JSON.stringify(g), before);
  g = await edit(g, { action: 'connect', source: { node: second, port: 'out' }, target: { node: last, port: 'in' }, replace: true });
  assert.equal(g.generic.authoring.edges.length, 1); assert.equal(g.generic.authoring.edges[0].source, second);
  g = await edit(g, { action: 'rewire', id: g.generic.authoring.edges[0].id, source: { node: first, port: 'out' }, target: { node: last, port: 'in' } });
  assert.equal(g.generic.authoring.edges[0].source, first);
  g = await edit(g, { action: 'remove-edge', id: g.generic.authoring.edges[0].id });
  assert.equal(g.generic.authoring.edges.length, 0); assert.equal(g.caseId, base.caseId);
});

test('groups, nested scope, reusable templates and duplicates preserve remapped subtree and exact slot facts', async () => {
  let g = await blank();
  g = await edit(g, { action: 'add', preset: 0 });
  const original = copy(g.generic.authoring), root = original.nodes.find((n: any) => !n.parent).id;
  g = await edit(g, { action: 'library', ids: [root], title: 'Reusable' });
  g = await edit(g, { action: 'add', library: 0 });
  assert.equal(g.generic.authoring.nodes.length, original.nodes.length * 2);
  assert.equal(new Set(g.generic.authoring.nodes.map((n: any) => n.id)).size, original.nodes.length * 2);
  const roots = g.generic.authoring.nodes.filter((n: any) => !n.parent).map((n: any) => n.id);
  g = await edit(g, { action: 'group', ids: roots, title: 'Grouped' });
  const groupId = g.generic.authoring.nodes.find((n: any) => n.label === 'Grouped').id;
  assert.ok(roots.every((id: string) => g.generic.authoring.nodes.find((n: any) => n.id === id).parent === groupId));
  g = await edit(g, { action: 'scope', id: groupId });
  g = await edit(g, { action: 'interface', role: 'input', label: 'nested' });
  assert.equal(g.generic.authoring.nodes.find((n: any) => n.label === 'nested').parent, groupId);
  const before = JSON.stringify(g);
  await assert.rejects(W.apply(g, { action: 'group', ids: [groupId, roots[0]], title: 'Wrong' }), /同一级/);
  assert.equal(JSON.stringify(g), before);
  g = await edit(g, { action: 'erase', ids: [groupId] });
  assert.equal(g.generic.authoring.nodes.length, 0); assert.equal(g.generic.authoring.edges.length, 0); assert.equal(g.generic.authoring.editorScope, null);
});

test('editing a sourced node detaches stale certificates and keeps original constructor evidence as provenance', async () => {
  const ir = copy(presets[0].ir), source = N.prepare({ task: 'generic-build', ir, options }).graph;
  source.caseId = 'verified-parent'; source.sourceAdapter = { sourceSha256: 'original-bytes' };
  let g = graph(await W.begin(source)), doc = g.generic.authoring;
  const target = doc.nodes.find((n: any) => n.constructor), id = target.id;
  const baseline = copy(doc.baseline);
  g = await edit(g, { action: 'edit', id, fields: { label: 'Edited Linear', constructor: { args: [7, 9], kwargs: {} } } });
  assert.deepEqual(copy(g.generic.authoring.baseline), baseline);
  assert.deepEqual(copy(g.generic.ir.semantic_contracts), []);
  assert.equal(g.generic.ir.runtime.model_executed, false);
  assert.equal(g.generic.ir.coverage.status, 'not-verified');
  assert.equal(g.generic.ir.nodes.find((n: any) => n.id === id).evidence_status, 'user-authored');
  assert.equal(W.record(g).origin.sourceSha256, 'original-bytes'); assert.equal(g.sourceAdapter, undefined);
});

test('portable authoring requires digest, sourceIR and regenerated glyphs to agree independently', async () => {
  let g = await blank(); g = await edit(g, { action: 'add', preset: 12 });
  const record = W.record(g), restored = await D.restore(copy(record));
  assert.equal(D.matches(g, restored.parsed), true); assert.equal(D.checkRendering(g), true);
  const changed = copy(record); changed.document.title = 'forged';
  await assert.rejects(D.restore(changed), /摘要/);
  const forged = copy(g); forged.generic.ir.nodes[0].label += ' forged';
  assert.equal(D.matches(forged, restored.parsed), false);
  forged.nodes[0].html += '<script>1</script>';
  assert.throws(() => D.checkRendering(forged), /图元/);
  const ordinary = await D.read(copy(record.document)), readOnly = copy(g);
  D.attach(readOnly, ordinary.record); assert.equal(readOnly.authoringWorkspace, undefined);
  await assert.rejects(W.apply(readOnly, { action: 'interface', role: 'input', label: 'x' }), /编辑副本/);
});

test('every shipped source preset can enter the native editing authority without the prototype runtime', async () => {
  assert.equal(presets.length, 16); assert.equal(presets.reduce((sum: number, m: any) => sum + m.ir.nodes.length, 0), 113);
  for (let preset = 0; preset < presets.length; preset++) {
    const g = await edit(await blank(), { action: 'add', preset });
    assert.equal(g.generic.authoring.nodes.length, presets[preset].ir.nodes.length, presets[preset].title);
    assert.equal(D.checkRendering(g), true); assert.equal(g.generic.ir.runtime.model_executed, false);
  }
});
