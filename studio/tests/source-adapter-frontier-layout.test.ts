import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';

const project = fileURLToPath(new URL('../../', import.meta.url));
const preview = path.join(project, 'studio/public/preview');
const context = vm.createContext({ TextEncoder, TextDecoder });
for (const file of ['router.js', 'physical-ports.js', 'junction-markers.js', 'route-labels.js',
  'source-contracts.js', 'semantic-constraints.js', 'graph-engine.js', 'recursive-graph.js', 'source-adapter.js']) {
  vm.runInContext(readFileSync(path.join(preview, 'yworks_edge_router_lab', file), 'utf8'), context, { filename: file });
}
const F = context.SummaryRecursive, E = context.SummaryEngine, S = context.SummarySourceAdapter;
const plain = (value: any) => JSON.parse(JSON.stringify(value));
const source = 'from torch import nn\nclass Lantern(nn.Module):\n def forward(self,x,flag):\n  if flag:\n'
  + Array.from({ length: 36 }, (_, i) => `   y${i}=x.${i % 2 ? 'relu' : 'sigmoid'}()\n`).join('')
  + '   return y35\n  else:\n   return x\n';
let bundlePromise: Promise<any>;
function bundle() {
  return bundlePromise ??= promisify(execFile)('python3', ['-I', '-S', '-B', '-c',
    'import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_preview.analyze import analyze;print(json.dumps(analyze({"lantern.py":sys.argv[2]},"lantern:Lantern")))',
    project, source], { encoding: 'utf8', maxBuffer: 2_000_000 }).then(({ stdout }) => JSON.parse(stdout));
}
function checked(graph: any) {
  assert.equal(F.route(graph).failed, 0);
  const check = E.validateView(graph);
  assert.equal(check.source.ok, true, check.source.violations.join('; '));
  assert.equal(check.layout.ok, true, check.layout.violations.join('; '));
  assert.deepEqual(plain(check.edges.filter(([, result]: any) => !result.ok)), []);
  assert.deepEqual(plain(check.routing.contacts), []);
  assert.deepEqual(plain(check.routing.constrained), []);
  return graph;
}
function mixed(sources: any) {
  let graph = checked(F.build(F.create(sources)));
  for (const label of ['待解析 · Module', 'if flag']) {
    const node = graph.nodes.find((n: any) => n.label === label && !n.expanded);
    assert.ok(node); graph = checked(F.toggle(graph, node.id, true));
  }
  return graph;
}

test('nested source frames release hidden descendant width and preserve evidence and canonical edges', async () => {
  const raw = await bundle(), before = JSON.stringify(raw), sources = S.sources(raw);
  const graph = mixed(sources), condition = graph.nodes.find((n: any) => n.label === 'if flag' && n.expanded);
  assert.ok(condition.w < 900, `two folded arms reserve only their actual width: ${condition.w}`);
  for (const node of sources.detailed.nodes) {
    if (node.parent) assert.ok(Object.values(sources).some((view: any) => view.nodes.some((n: any) => n.id === node.id && !n.expanded)),
      `every non-root source object has a folded receipt: ${node.id}`);
    assert.deepEqual(plain(node.semantic), raw.ir.nodes.find((n: any) => n.id === node.id));
  }
  for (const edge of sources.detailed.edges) {
    const original = raw.ir.edges.find((e: any) => e.id === edge.id);
    assert.equal(edge.binding.canonical_src, `${original.source}:${original.sourcePort}`);
    assert.equal(edge.binding.canonical_dst, `${original.target}:${original.targetPort}`);
  }
  assert.equal(JSON.stringify(raw), before);
});

test('many independent statements wrap inside their existing dependency rank without invented sequence edges', async () => {
  const raw = await bundle(), graph = checked(F.all(mixed(S.sources(raw)), true));
  const statements = graph.nodes.filter((n: any) => /^x\.(relu|sigmoid)$/.test(n.label));
  assert.equal(statements.length, 36);
  const parent = graph.nodes.find((n: any) => n.id === statements[0].parent);
  assert.ok(parent.w < 1400, `independent statements must not create a horizontal strip: ${parent.w}`);
  const rows = new Map<number, number>();
  for (const n of statements) rows.set(n.y, (rows.get(n.y) || 0) + 1);
  assert.ok(rows.size >= 9); assert.ok([...rows.values()].every(count => count <= 4));
  assert.equal(graph.edges.length, raw.ir.edges.length);
});

test('mixed source frontier and manual layout restore exactly after collapse and reopen', async () => {
  let graph = mixed(S.sources(await bundle()));
  const branch = graph.nodes.find((n: any) => n.label === 'else');
  const owner = branch.parent; const local = graph.recursive.state.layouts[owner] ||= {};
  local[branch.id] = { x: 28, y: 18 };
  delete graph.recursive.state.frontiers[F.signature(graph.recursive)];
  graph = checked(F.build(graph.recursive));
  const before = JSON.stringify([graph.nodes, graph.edges.map((e: any) => [e.id, e.route])]);
  const outer = graph.nodes.find((n: any) => n.label === '待解析 · Module');
  graph = checked(F.toggle(checked(F.toggle(graph, outer.id, false)), outer.id, true));
  assert.equal(JSON.stringify([graph.nodes, graph.edges.map((e: any) => [e.id, e.route])]), before);
  assert.deepEqual(plain(graph.recursive.state.layouts[owner][branch.id]), { x: 28, y: 18 });
});

test('detailed-only source fallback cards keep readable captions rather than internal identity text', async () => {
  const raw = await bundle(), sources = S.sources(raw);
  const graph = checked(F.build(F.create({ detailed: sources.detailed })));
  const folded = graph.nodes.filter((n: any) => n.recursiveVariant?.synthetic);
  assert.ok(folded.length);
  for (const node of folded) {
    assert.ok(node.foldedPresentation);
    assert.ok(node.html.includes(node.foldedPresentation.detail));
    assert.equal(node.html.includes(node.id), false, 'source identity remains metadata, not a subtitle');
    assert.deepEqual(plain(node.semantic), raw.ir.nodes.find((n: any) => n.id === node.id));
  }
});
