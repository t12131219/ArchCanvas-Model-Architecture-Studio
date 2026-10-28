import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { webcrypto } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const context = vm.createContext({ performance, TextEncoder, crypto: webcrypto });
const script = (path: string) => vm.runInContext(readFileSync(new URL('../public/preview/' + path, import.meta.url), 'utf8'), context, { filename: path });
for (const name of ['router', 'physical-ports', 'junction-markers', 'route-labels', 'source-contracts', 'semantic-constraints', 'graph-engine', 'recursive-graph']) script('yworks_edge_router_lab/' + name + '.js');
const manifest = JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json', import.meta.url), 'utf8'));
for (const { path } of manifest.files) script(path);
for (const name of ['studio-semantic', 'studio-documents']) script('yworks_edge_router_lab/' + name + '.js');
const D = context.ArchCanvasSummaryDocuments, N = context.ArchCanvasSemanticView, G = context.SummaryNativeSemantic, E = context.SummaryEngine, A = context.SemanticAuthoring;
const copy = (value: any) => JSON.parse(JSON.stringify(value));
const project = fileURLToPath(new URL('../../', import.meta.url));
const source = 'from torch import nn\nclass Model(nn.Module):\n def forward(self,x):\n  return x+x\n';
const { stdout } = await promisify(execFile)('python3', ['-I', '-S', '-B', '-c', 'import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_preview import analyze;print(json.dumps(analyze({"net.py":sys.argv[2]},"net:Model",semantic_mode="summary")["ir"]["semantic_ir"]))', project, source], { encoding: 'utf8' });
const ir = JSON.parse(stdout);
const options = { refineCrossings: false, refinePlacement: false, refineChannels: false, refineFlow: false };
function build(parsed: any) {
  const result = N.prepare({ task: 'generic-build', ir: parsed.ir, state: parsed.state, extra: { authoring: parsed.authoring, migration: parsed.migration, layouts: parsed.layouts }, nativeLayout: parsed.nativeLayout, options });
  assert.equal(N.accepts(result.graph, result.validation), true);
  return result.graph;
}
const native = G.document(build({ ir }));
const formats = [copy(ir), copy(native), { schema: 'semantic-canvas/1', ir: copy(ir), state: copy(native.state), geometry: { old: true } }, { schema: 'archcanvas-architecture-document/1', ir: copy(ir), state: copy(native.state) }, copy(A.fromIR(ir))];

for (const value of formats) test(`Summary imports ${value.schema} through its original reader and preserves portable evidence`, async () => {
  const before = JSON.stringify(value), document = await D.read(value), graph = D.attach(build(document.parsed), document.record);
  assert.equal(JSON.stringify(value), before);
  assert.deepEqual(copy(document.record.document), value);
  assert.deepEqual(copy(document.parsed.ir), ir);
  assert.equal(D.matches(graph, document.parsed), true);
  assert.equal(graph.sourceAdapter, undefined);
  assert.equal(graph.importedDocument.sourceVerified, false);
  assert.equal(graph.importedDocument.modelExecuted, false);
  assert.equal(graph.caseId, document.record.id);
  assert.deepEqual(copy(await D.restore(copy(document.record))), copy(document));
  for (const transition of [{ type: 'preset', preset: 'detail' }, { type: 'all', expanded: true }, { type: 'preset', preset: 'overview' }]) {
    const next = N.prepare({ task: 'frontier', graph, transition, options });
    assert.equal(N.accepts(next.graph, next.validation), true);
    assert.deepEqual(copy(next.graph.generic.ir), ir);
    assert.deepEqual(copy(next.graph.importedDocument), copy(graph.importedDocument));
  }
});

test('native layout restores exactly; legacy geometry stays in provenance and authoring model is preserved', async () => {
  const document = await D.read(copy(native)), graph = build(document.parsed);
  assert.deepEqual(copy(G.layoutSnapshot(graph).nodes), copy(native.nativeLayout.nodes));
  const legacy = await D.read(copy(formats[2]));
  assert.deepEqual(copy(legacy.parsed.migration.original.geometry), { old: true });
  assert.equal(legacy.parsed.nativeLayout, undefined);
  const authored = await D.read(copy(formats[4]));
  assert.deepEqual(copy(build(authored.parsed).generic.authoring), formats[4]);
  const empty = await D.read(copy(A.empty('空白草稿')));
  assert.equal(N.accepts(build(empty.parsed), E.validateView(build(empty.parsed))), true);
});

test('restored documents reject changed content, source authority and authoring state', async () => {
  const { record, parsed } = await D.read(copy(formats[4]));
  const changed = copy(record); changed.document.title += ' changed';
  await assert.rejects(() => D.restore(changed), /身份与内容/);
  const graph = copy(D.attach(build(parsed), record));
  graph.sourceAdapter = { sourceSha256: 'forged' };
  D.attach(graph, record); assert.equal(graph.sourceAdapter, undefined);
  graph.generic.ir.nodes[0].label += ' forged'; assert.equal(D.matches(graph, parsed), false);
  const altered = copy(build(parsed)); altered.generic.authoring.title = 'forged'; assert.equal(D.matches(altered, parsed), false);
});

test('edited imported documents accept generated glyphs and reject executable SVG or attachment payloads', async () => {
  const { parsed } = await D.read(copy(native)), graph = copy(build(parsed));
  assert.equal(D.checkRendering(graph), true);
  for (const patch of [
    (v: any) => v.nodes[0].html += '<svg onload="window.injected=true"/>',
    (v: any) => v.definitions = '<script>window.injected=true</script>',
    (v: any) => v.extras = '<image href="https://example.invalid/pixel"/>',
    (v: any) => v.attachments = [{ html: '<foreignObject/>' }],
    (v: any) => v.routeLabels = [{ html: '<text onclick="window.injected=true"/>' }],
  ]) { const forged = copy(graph); patch(forged); assert.throws(() => D.checkRendering(forged), /原生文档/); }
});

test('malformed identity, hierarchy, endpoints and bounded resource violations reject before import', async () => {
  await assert.rejects(() => D.read({ schema: 'unknown' }), /不支持/);
  for (const change of [
    (v: any) => v.nodes.push(copy(v.nodes[0])),
    (v: any) => v.nodes[0].parent = 'missing',
    (v: any) => v.nodes[0].parent = v.nodes[0].id,
    (v: any) => v.edges[0].target = 'missing',
    (v: any) => v.nodes = Array.from({ length: 4001 }, (_, i) => ({ id: String(i) })),
  ]) { const bad = copy(ir); change(bad); await assert.rejects(() => D.read(bad)); }
  const deep = copy(ir); let nested = deep; for (let i = 0; i < 130; i++) nested = nested.extra = {};
  await assert.rejects(() => D.read(deep), /结构预算/);
  const cyclic = copy(ir); cyclic.extra = cyclic; await assert.rejects(() => D.read(cyclic), /循环/);
  const huge = copy(ir); huge.extra = 'x'.repeat(D.limits.bytes); await assert.rejects(() => D.read(huge), /64 MB/);
});
