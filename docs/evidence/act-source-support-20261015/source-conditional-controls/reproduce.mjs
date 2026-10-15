import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const repo = fileURLToPath(new URL('../../../../', import.meta.url));
const engine = repo + 'studio/public/preview/yworks_edge_router_lab/';
const scripts = ['router.js', 'physical-ports.js', 'junction-markers.js', 'route-labels.js', 'source-contracts.js', 'semantic-constraints.js', 'graph-engine.js', 'recursive-graph.js', 'source-controls.js', 'frontier-task.js', 'source-adapter.js'];
const context = vm.createContext({ performance, TextEncoder, TextDecoder }); context.self = context;
const sha = value => createHash('sha256').update(value).digest('hex');
for (const file of scripts) vm.runInContext(readFileSync(engine + file, 'utf8'), context, { filename: file });
const { SummarySourceAdapter: A, SummaryRecursive: F, SummaryEngine: E, SummaryFrontierTask: T, SummarySourceControls: S } = context;
const sourceFile = new URL('../final-arrow-support/ACTPolicy-preview.json', import.meta.url);
const bundle = JSON.parse(readFileSync(sourceFile, 'utf8'));
const graph = F.build(F.create(A.sources(bundle)));
const detail = graph.recursive.authority.detail;
const conditional = detail.nodes.find(n => n.semantic?.sourceKind === 'SourceConditional' && n.semantic.label === 'if actions is not None');
assert.ok(conditional);
let cursor = conditional; const ancestors = [];
while (cursor) { ancestors.unshift(cursor.id); cursor = detail.nodes.find(n => n.id === cursor.parent); }
const branches = detail.nodes.filter(n => n.parent === conditional.id && n.semantic?.sourceKind === 'SourceBranch');
const training = branches.find(n => n.semantic.label !== 'else');
const frontiers = [['condition-expanded', ancestors], ['training-expanded', [...ancestors, training.id]], ['both-branches-expanded', [...ancestors, ...branches.map(n => n.id)]]];
const results = [];
for (const [name, ids] of frontiers) {
  const result = T.run(E.clone(graph), { type: 'expand', ids, expanded: true }, {});
  const canonical = () => JSON.stringify([result.graph.nodes, result.graph.edges, result.graph.semanticBaseline, result.graph.recursive]);
  const before = sha(canonical()); const value = S.refresh(result.graph); const after = sha(canonical());
  assert.equal(before, after);
  assert.ok(result.validation.source.ok && result.validation.layout.ok && result.validation.edges.every(([, check]) => check.ok));
  const controls = value.controls.filter(control => control.owner === conditional.id);
  assert.equal(controls.length, 2); assert.equal(value.diagnostics.length, 0);
  assert.ok(controls.every(control => control.geometryValidated && branches.some(branch => branch.id === control.target)));
  assert.equal(result.graph.edges.some(edge => edge.id.startsWith('source-control:')), false);
  results.push({ name, ids, nodes: result.graph.nodes.length, edges: result.graph.edges.length, timing: result.timing, canonicalBefore: before, canonicalAfter: after,
    validation: { source: result.validation.source.ok, layout: result.validation.layout.ok, edgeCount: result.validation.edges.length, invalidEdges: result.validation.edges.filter(([, check]) => !check.ok) },
    controls: value.controls, decisions: value.decisions, diagnostics: value.diagnostics });
}
writeFileSync(new URL('act-frontiers.json', import.meta.url), JSON.stringify({ source: fileURLToPath(sourceFile).slice(repo.length), sourceSha256: sha(readFileSync(sourceFile)), engine: Object.fromEntries(scripts.map(file => [file, sha(readFileSync(engine + file))])), results }, null, 2) + '\n');
console.log(JSON.stringify(results.map(({ name, nodes, edges, controls, diagnostics, validation }) => ({ name, nodes, edges, controls: controls.length, diagnostics: diagnostics.length, validation })), null, 2));
