import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { webcrypto } from 'node:crypto';
import { bundlePreviewRequest } from '../src/previewInterop.ts';

const project = fileURLToPath(new URL('../../', import.meta.url));
const context = vm.createContext({ TextEncoder, TextDecoder, crypto: webcrypto });
for (const name of ['router', 'physical-ports', 'junction-markers', 'route-labels', 'source-contracts', 'semantic-constraints', 'graph-engine', 'recursive-graph', 'source-adapter']) {
  vm.runInContext(readFileSync(new URL(`../public/preview/yworks_edge_router_lab/${name}.js`, import.meta.url), 'utf8'), context, { filename: name + '.js' });
}
const S = context.SummarySourceAdapter, F = context.SummaryRecursive, E = context.SummaryEngine;
const plain = (value: any) => JSON.parse(JSON.stringify(value));
async function analyze(source: string, config: Record<string, unknown> = {}) {
  const { stdout } = await promisify(execFile)('python3', ['-I', '-S', '-B', '-c',
    'import sys,json,tempfile;from pathlib import Path;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_preview import analyze;from archcanvas_adapters import AdapterRegistry;files={"net.py":sys.argv[2]};bundle=analyze(files,"net:Model",json.loads(sys.argv[3]),semantic_mode="summary");t=tempfile.TemporaryDirectory();print(json.dumps(AdapterRegistry(Path(t.name)).preview(bundle,files)))',
    project, source, JSON.stringify(config)], { encoding: 'utf8', maxBuffer: 8_000_000 });
  return JSON.parse(stdout);
}
function checked(graph: any) {
  assert.equal(F.route(graph).failed, 0);
  const result = E.validateView(graph);
  assert.equal(result.source.ok, true, result.source.violations.join('; '));
  assert.equal(result.layout.ok, true, result.layout.violations.join('; '));
  assert.deepEqual(plain(result.edges.filter(([, value]: any) => !value.ok)), []);
  return graph;
}
const sources = {
  residual: 'from torch import nn\nclass Model(nn.Module):\n def __init__(self):\n  super().__init__();self.fc=nn.Linear(4,4)\n def forward(self,x):\n  return x+self.fc(x)\n',
  loop: 'from torch import nn\nclass Model(nn.Module):\n def forward(self,x):\n  for i in range(3):\n   x=x.relu()\n  return x\n',
  branch: 'from torch import nn\nclass Model(nn.Module):\n def forward(self,x,flag):\n  if flag:\n   y=x.relu()\n  else:\n   y=x.sigmoid()\n  return y\n',
  opaque: 'from torch import nn\nfrom external import mystery\nclass Model(nn.Module):\n def forward(self,x):\n  return mystery(x)\n',
};
for (const [name, source] of Object.entries(sources)) test(`native Summary ${name} verifies and opens on the single recursive authority`, async () => {
  const bundle = await analyze(source), before = JSON.stringify(bundle);
  await S.verify(bundle);
  const views = S.sources(bundle);
  let graph = checked(F.build(F.create(views)));
  const overview = JSON.stringify(graph.nodes.map((node: any) => [node.id, node.x, node.y, node.expanded]));
  graph = checked(F.all(graph, true));
  assert.equal(graph.nodes.length, bundle.ir.nodes.length, 'the full source graph must remain expandable');
  assert.equal(graph.edges.length, bundle.ir.edges.length, 'no loop backedge or conditional edge may disappear');
  for (const edge of graph.edges) {
    const raw = bundle.ir.edges.find((item: any) => item.id === edge.projection.original);
    assert.equal(edge.binding.canonical_src, `${raw.source}:${raw.sourcePort}`);
    assert.equal(edge.binding.canonical_dst, `${raw.target}:${raw.targetPort}`);
  }
  graph = checked(F.all(graph, false));
  assert.equal(JSON.stringify(graph.nodes.map((node: any) => [node.id, node.x, node.y, node.expanded])), overview);
  assert.equal(JSON.stringify(bundle), before, 'all frontier and route edits preserve the source facts');
});

test('float literals, unicode spans and saved constructor config survive the browser digest gate', async () => {
  const bundle = await analyze(sources.residual.replace('nn.Linear(4,4)', 'nn.Dropout(1.0)').replaceAll('x', '特征'), { width: 8, probability: 1.0, semanticMode: 'a constructor argument' });
  await S.verify(bundle);
  const request = bundlePreviewRequest(bundle);
  assert.equal(request.semanticMode, 'summary');
  assert.deepEqual(request.config, { width: 8, probability: 1, semanticMode: 'a constructor argument' });
  assert.ok(Object.values(bundle.evidence).some((span: any) => span.expression.includes('特征')));
});

test('forged native projection and native IR digests are rejected before graph installation', async () => {
  const bundle = await analyze(sources.residual);
  const forged = structuredClone(bundle); forged.ir.nodes[1].semantic.label = 'forged'; forged.canonicalIR = JSON.stringify(forged.ir);
  assert.throws(() => S.validate(forged), /节点投影不一致/);
  const changed = structuredClone(bundle); changed.ir.semantic_ir.ir_digest = '0'.repeat(64);
  changed.canonicalIR = JSON.stringify(changed.ir);
  const bytes = await webcrypto.subtle.digest('SHA-256', new TextEncoder().encode(changed.canonicalIR));
  changed.irSha256 = Buffer.from(bytes).toString('hex');
  await assert.rejects(() => S.verify(changed), /语义 IR SHA256/);
});

test('native IR downloads preserve Python floats, large integers and their original digest', async () => {
  const bundle = await analyze(sources.residual.replace('nn.Linear(4,4)', 'nn.Linear(9007199254740993,4)').replace('return x+self.fc(x)', 'return self.fc(x) * 1.0'));
  await S.verify(bundle);
  // Simulate JSON/IndexedDB transport through JavaScript before downloading.
  const exported = S.semanticDocument(JSON.parse(JSON.stringify(bundle)));
  assert.match(exported, /9007199254740993/);
  assert.match(exported, /1\.0/);
  const { stdout } = await promisify(execFile)('python3', ['-I', '-S', '-B', '-c',
    'import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_summary_semantic.schema import validate_ir;ir=json.loads(sys.argv[2]);result=validate_ir(ir);assert result["ok"],result;print(ir["ir_digest"])', project, exported], { encoding: 'utf8' });
  assert.equal(stdout.trim(), bundle.ir.semantic_ir.ir_digest);
});
