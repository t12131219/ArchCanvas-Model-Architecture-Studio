import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';
import vm from 'node:vm';
import { isPreviewSourceDependency } from '../src/previewPresentation.ts';

const project = fileURLToPath(new URL('../../', import.meta.url));
const context = vm.createContext({ performance, TextEncoder, TextDecoder });
for (const file of ['router.js', 'physical-ports.js', 'junction-markers.js', 'route-labels.js',
  'source-contracts.js', 'semantic-constraints.js', 'graph-engine.js', 'recursive-graph.js', 'source-adapter.js']) {
  vm.runInContext(readFileSync(path.join(project, 'studio/public/preview/yworks_edge_router_lab', file), 'utf8'), context, { filename: file });
}
const F = context.SummaryRecursive, E = context.SummaryEngine, S = context.SummarySourceAdapter;
const plain = (value: any) => JSON.parse(JSON.stringify(value));

// This syntax is opaque to the old inspector. The independent rule adds its
// actual iterable and argument, reusing the existing comprehension/call cards.
const source = `from torch import nn
class CopperSprig(nn.Module):
 def __init__(self):
  super().__init__(); self.parts=nn.ModuleList([nn.Identity()])
 def forward(self,x):
  values=[part(x) for part in self.parts]
  return values
`;
const rule = {
  schema: 'archcanvas-source-rule/1', name: 'Comprehension call inputs',
  match: { type: 'ListComp', fields: {
    elt: { type: 'Call', fields: { args: [{ type: 'Name' }] } },
    generators: [{ type: 'comprehension', fields: { is_async: 0 } }],
  } },
  nodes: [
    { key: 'region', at: [], parent: null, kind: 'SourceLoop' },
    { key: 'iterator', at: ['generators', 0, 'iter'], parent: 'region', kind: 'SourceExpression' },
    { key: 'input', at: ['elt', 'args', 0], parent: 'region', kind: 'SourceExpression' },
    { key: 'operation', at: ['elt'], parent: 'region', kind: 'SourceCall' },
  ],
  relations: [
    { source: 'iterator', target: 'operation', proof: 'comprehension-iteration' },
    { source: 'input', target: 'operation', proof: 'expression-input' },
  ],
};
let fixturePromise: Promise<any>;
function fixture() {
  return fixturePromise ??= promisify(execFile)('python3', ['-I', '-S', '-B', '-c', `
import sys,json
sys.path.insert(0,sys.argv[1]+"/src")
from archcanvas_preview import analyze
from archcanvas_adapters import scaffold_adapter_files,validate_adapter_files,apply_preview_adapters
files={"foreign.py":sys.argv[2]}
raw=analyze(files,"foreign:CopperSprig")
definition=validate_adapter_files(scaffold_adapter_files(files,"foreign:CopperSprig",rules=[json.loads(sys.argv[3])]),files)
adapted=apply_preview_adapters(raw,files,[definition])
print(json.dumps({"raw":raw,"definition":definition,"bundle":adapted}))
`, project, source, JSON.stringify(rule)], { encoding: 'utf8', maxBuffer: 2_000_000, timeout: 15_000 })
    .then(({ stdout }) => JSON.parse(stdout));
}
function checked(graph: any) {
  assert.ok(graph, 'a recursive expansion produced a scene');
  assert.equal(F.route(graph).failed, 0);
  const result = E.validateView(graph);
  assert.equal(result.source.ok, true, result.source.violations.join('; '));
  assert.equal(result.layout.ok, true, result.layout.violations.join('; '));
  assert.deepEqual(plain(result.edges.filter(([, edge]: any) => !edge.ok)), []);
  assert.deepEqual(plain(result.routing.contacts), []);
  assert.deepEqual(plain(result.routing.constrained), []);
  return graph;
}
function expanded(bundle: any) {
  return checked(F.all(checked(F.build(F.create(S.sources(bundle)))), true));
}
function originalFactsRemain(raw: any, graph: any) {
  const detail = graph.recursive.authority.detail;
  for (const node of raw.ir.nodes) assert.deepEqual(plain(detail.nodes.find((item: any) => item.id === node.id)?.semantic), node);
  for (const edge of raw.ir.edges) {
    const binding = detail.edges.find((item: any) => item.id === edge.id)?.binding;
    assert.ok(binding, `the original edge survives: ${edge.id}`);
    assert.equal(binding.canonical_src, `${edge.source}:${edge.sourcePort}`);
    assert.equal(binding.canonical_dst, `${edge.target}:${edge.targetPort}`);
    assert.deepEqual(plain(binding.source_evidence), edge.source_evidence);
  }
}
const geometry = (graph: any) => plain(graph.nodes.map((node: any) => ({ id: node.id, x: node.x, y: node.y, w: node.w, h: node.h, expanded: node.expanded })));

test('a verified v2 rule exposes new source internals and arrowed syntax dependencies in the recursive scene', async () => {
  const { raw, definition, bundle } = await fixture(), original = JSON.stringify(bundle);
  assert.equal(definition.schema, 'archcanvas-source-adapter/2');
  assert.equal(definition.generationContract, null);
  assert.equal(bundle.sourceSha256, raw.sourceSha256);
  assert.equal(bundle.sourceRuleApplications.length, 1);
  const added = bundle.ir.nodes.filter((node: any) => !raw.ir.nodes.some((item: any) => item.id === node.id));
  assert.deepEqual(added.map((node: any) => node.expression).sort(), ['self.parts', 'x']);
  assert.equal(raw.ir.nodes.some((node: any) => node.expression === 'self.parts'), false);
  const proofEdges = bundle.ir.edges.filter((edge: any) => edge.sourceRuleId);
  assert.equal(proofEdges.length, 2);
  const call = raw.ir.nodes.find((node: any) => node.expression === 'part(x)');
  assert.ok(call);
  assert.ok(proofEdges.every((edge: any) => edge.target === call.id));

  const graph = expanded(bundle);
  for (const fact of added) {
    const visible = graph.nodes.find((node: any) => node.id === fact.id);
    assert.ok(visible, `a new internal node is visible: ${fact.expression}`);
    assert.deepEqual(plain(visible.semantic), fact);
    assert.equal(visible.semantic.sourceStructure, true);
    assert.equal(visible.semantic.generationContract, null);
  }
  for (const fact of proofEdges) {
    const edge = graph.edges.find((item: any) => item.projection?.original === fact.id);
    assert.ok(edge, `a proven source dependency is displayed: ${fact.id}`);
    assert.equal(edge.source, fact.source); assert.equal(edge.target, fact.target);
    assert.equal(edge.arrow, 'target'); assert.equal(edge.dashed, true);
    assert.equal(edge.syntaxOnly, true); assert.equal(edge.draft, false);
    assert.equal(isPreviewSourceDependency(graph, edge), true);
    assert.equal(edge.binding.canonical_src, `${fact.source}:${fact.sourcePort}`);
    assert.equal(edge.binding.canonical_dst, `${fact.target}:${fact.targetPort}`);
    assert.deepEqual(plain(edge.binding.source_evidence), fact.source_evidence);
    assert.ok(edge.route.length >= 2);
  }
  originalFactsRemain(raw, graph);
  for (const fact of raw.ir.nodes) assert.deepEqual(bundle.ir.nodes.find((node: any) => node.id === fact.id), fact);
  for (const fact of raw.ir.edges) assert.deepEqual(bundle.ir.edges.find((edge: any) => edge.id === fact.id), fact);
  assert.equal(JSON.stringify(bundle), original, 'scene construction does not alter the trusted bundle');
});

test('rule internals retain a manual move, expansion state and canonical facts through collapse and JSON reopen', async () => {
  const { raw, bundle } = await fixture();
  let graph = expanded(bundle);
  const boundaryId = bundle.sourceRuleApplications[0].boundary;
  const target = bundle.ir.nodes.find((node: any) => node.sourceRuleId && node.expression === 'self.parts');
  assert.ok(target);
  const before = E.clone(graph), initial = before.nodes.find((node: any) => node.id === target.id);
  assert.ok(E.move(graph, target.id, 12, 0).has(target.id), JSON.stringify(graph.lastMove));
  F.captureMove(before, graph, target.id); graph = checked(graph);
  const moved = graph.nodes.find((node: any) => node.id === target.id);
  assert.equal(moved.x, initial.x + 12); assert.equal(moved.y, initial.y);
  const local = plain(graph.recursive.state.layouts[target.parent][target.id]);
  assert.deepEqual(local, { x: 12, y: 0 });
  const positions = geometry(graph), authority = JSON.stringify(graph.recursive.authority);

  graph = checked(F.toggle(graph, boundaryId, false));
  assert.equal(graph.nodes.some((node: any) => node.id === target.id), false);
  assert.equal(graph.nodes.find((node: any) => node.id === boundaryId).expanded, false);
  originalFactsRemain(raw, graph);
  // The edit JSON retains complete authority and hidden layouts instead of
  // reconstructing a guessed module from a preset name on reopen.
  const stored = JSON.stringify(graph);
  graph = checked(F.build(JSON.parse(stored).recursive));
  assert.equal(graph.nodes.some((node: any) => node.id === target.id), false);
  graph = checked(F.toggle(graph, boundaryId, true));
  assert.deepEqual(geometry(graph), positions);
  assert.deepEqual(plain(graph.recursive.state.layouts[target.parent][target.id]), local);
  assert.equal(JSON.stringify(graph.recursive.authority), authority);
  originalFactsRemain(raw, graph);
  assert.equal(graph.irSha256, bundle.irSha256);
  assert.equal(graph.sourceAdapter.sourceSha256, bundle.sourceSha256);
  const proofIds = new Set(bundle.ir.edges.filter((edge: any) => edge.sourceRuleId).map((edge: any) => edge.id));
  assert.equal(graph.edges.filter((edge: any) => proofIds.has(edge.projection?.original)).length, 2);

  const forged = E.clone(graph), edge = forged.edges.find((item: any) => proofIds.has(item.projection?.original));
  edge.binding.canonical_src = 'fabricated:tensor';
  assert.equal(E.validateView(forged).source.ok, false, 'JSON reopen cannot grant new canonical source bindings');
});
