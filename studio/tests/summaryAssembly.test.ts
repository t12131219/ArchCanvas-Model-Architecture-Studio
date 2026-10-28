import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { webcrypto, createHash } from 'node:crypto';
import vm from 'node:vm';

const context = vm.createContext({ performance, TextEncoder, crypto: webcrypto });
const copy = (value: any) => JSON.parse(JSON.stringify(value));
function load(path: string) { vm.runInContext(readFileSync(new URL('../public/preview/' + path, import.meta.url), 'utf8'), context, { filename: path }); }
for (const name of ['router', 'physical-ports', 'junction-markers', 'route-labels', 'source-contracts', 'semantic-constraints', 'graph-engine', 'recursive-graph']) load('yworks_edge_router_lab/' + name + '.js');
for (const { path } of JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json', import.meta.url), 'utf8')).files) load(path);
for (const name of ['studio-semantic', 'studio-documents', 'studio-authoring']) load('yworks_edge_router_lab/' + name + '.js');
const W = context.ArchCanvasSummaryAuthoring, D = context.ArchCanvasSummaryDocuments, N = context.ArchCanvasSemanticView;
const presets = JSON.parse(readFileSync(new URL('../public/preview/data/semantic/authoring-presets.json', import.meta.url), 'utf8')).modules;
const options = { refineCrossings: false, refinePlacement: false, refineChannels: false, refineFlow: false, budgetMs: 1000 };
function build(result: any) {
  const { parsed, record } = result, built = N.prepare({ task: 'generic-build', ir: parsed.ir, state: parsed.state, extra: { authoring: parsed.authoring }, options });
  assert.equal(N.accepts(built.graph, built.validation), true);
  return W.attach(built.graph, record);
}
async function edited() {
  const graph = build(await W.begin(null, { blank: true }));
  return build(await W.apply(graph, { action: 'add', preset: presets.findIndex((p: any) => p.title === 'Residual') }, presets));
}
async function analyze(ir: any): Promise<any> {
  const project = fileURLToPath(new URL('../../', import.meta.url));
  return new Promise((resolve, reject) => {
    const child = execFile('python3', ['-I', '-S', '-B', '-c', 'import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_preview.assembly_bridge import certify_declared_assembly;print(json.dumps(certify_declared_assembly(json.load(sys.stdin))))', project], { maxBuffer: 32_000_000 }, (error, stdout) => error ? reject(error) : resolve(JSON.parse(stdout)));
    child.stdin!.end(JSON.stringify(ir));
  });
}
const request = (graph: any, result: any) => ({ action: 'certify', workspaceId: graph.authoringWorkspace.id, baseDocumentSha256: graph.authoringWorkspace.documentSha256, result });
function rehash(result: any, change: (ir: any) => void) { const next = copy(result), ir = JSON.parse(next.irText); change(ir); next.irText = JSON.stringify(ir); next.resultSha256 = createHash('sha256').update(next.irText).digest('hex'); return next; }

test('real Summary assembly contracts preserve every declared fact and survive strict portable restore and native cuts', async () => {
  const before = await edited(), result = await analyze(before.generic.ir);
  const graph = build(await W.apply(before, request(before, result)));
  assert.ok(graph.generic.ir.semantic_contracts.length > 0);
  assert.deepEqual(copy(graph.generic.ir.nodes), copy(before.generic.ir.nodes));
  assert.deepEqual(copy(graph.generic.ir.edges), copy(before.generic.ir.edges));
  assert.deepEqual(copy(graph.generic.authoring), copy(before.generic.authoring));
  assert.equal(graph.sourceAdapter, undefined); assert.equal(graph.sourceProfile.modelExecuted, false);
  assert.equal(W.inspector(graph).localAnalysis.sourceTransactionBinding, false);
  const restored = await D.restore(copy(W.record(graph)));
  assert.equal(D.matches(graph, restored.parsed), true); assert.equal(D.checkRendering(graph), true);
  for (const preset of ['overview', 'detail']) {
    const next = N.prepare({ task: 'generic-route', graph, transition: { type: 'preset', preset }, options });
    assert.equal(N.accepts(next.graph, next.validation), true);
    assert.deepEqual(copy(next.graph.generic.ir), copy(graph.generic.ir));
  }
});

test('any subsequent declaration edit invalidates local analysis while preserving the prior history snapshot', async () => {
  const before = await edited(), result = await analyze(before.generic.ir), graph = build(await W.apply(before, request(before, result)));
  const saved = JSON.stringify(graph), next = build(await W.apply(graph, { action: 'edit', id: graph.generic.authoring.nodes[0].id, fields: { label: 'changed declaration' } }));
  assert.equal(W.inspector(next).localAnalysis, null); assert.equal(next.generic.ir.semantic_contracts.length, 0);
  assert.equal(next.generic.ir.authoring.local_contracts_recomputed, undefined);
  assert.equal(JSON.stringify(graph), saved);
  assert.equal(D.matches(graph, (await D.restore(copy(W.record(graph)))).parsed), true);
});

test('stale, fact-changing, unbounded-scope and corrupt local results refuse without changing the committed graph', async () => {
  const graph = await edited(), result = await analyze(graph.generic.ir), saved = JSON.stringify(graph), op = request(graph, result);
  await assert.rejects(W.apply(graph, { ...op, workspaceId: 'other' }), /已变化/);
  await assert.rejects(W.apply(graph, { ...op, baseDocumentSha256: 'old' }), /已变化/);
  for (const invalid of [
    { ...result, irText: result.irText + ' ' },
    rehash(result, ir => ir.nodes[0].label = 'forged canonical node'),
    rehash(result, ir => ir.semantic_contracts[0].scope = 'verified entire Python program'),
    rehash(result, ir => { let nested: any = {}; const top = nested; for (let i = 0; i < 140; i++) nested = nested.next = {}; ir.semantic_contracts[0].proof = [top]; }),
    { ...result, analysis: { ...result.analysis, sourceTransactionBinding: true } },
  ]) await assert.rejects(W.apply(graph, request(graph, invalid)), /局部|预算/);
  assert.equal(JSON.stringify(graph), saved);
});
