#!/usr/bin/env node
/** CPU-only core benchmark; never substitutes for browser paint/Event Timing. */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { cpSync, mkdtempSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { cpus, platform, arch, tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const args = new Map();
for (let index = 2; index < process.argv.length; index += 2) args.set(process.argv[index], process.argv[index + 1]);
const project = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const architectureFile = args.get('--architecture');
if (!architectureFile) throw new Error('--architecture must name an analyzed formal fixture JSON');
const samples = Number(args.get('--samples') ?? 30), warmup = Number(args.get('--warmup') ?? 5);
if (!Number.isInteger(samples) || samples < 20 || samples > 100 || !Number.isInteger(warmup) || warmup < 1) throw new Error('Use >=20 samples and >=1 warm-up');
const output = resolve(args.get('--output') ?? 'docs/evidence/m4-core-performance.json');
const snapshotDirectory = mkdtempSync(join(tmpdir(), 'archcanvas-core-benchmark-'));
const coreDirectory = join(snapshotDirectory, 'core');
const sourceCodeDirectory = resolve(args.get('--core-directory') ?? join(project, 'studio/src/core'));
cpSync(sourceCodeDirectory, coreDirectory, { recursive: true });
const hash = value => createHash('sha256').update(value).digest('hex');
function codeDigests(directory) {
  return Object.fromEntries(readdirSync(directory).filter(name => name.endsWith('.ts')).sort().map(name => [name, hash(readFileSync(join(directory, name)))]));
}
const copiedCodeDigests = codeDigests(coreDirectory);
assert.deepEqual(copiedCodeDigests, codeDigests(sourceCodeDirectory));
const architectureBytes = readFileSync(resolve(architectureFile));
const architecture = JSON.parse(architectureBytes);
for (const source of architecture.sources) assert.equal(hash(source.content), source.digest, `Source content digest: ${source.path}`);
const formalSourceRoot = resolve(args.get('--source-root') ?? join(project, 'fixtures/stress_300'));
for (const source of architecture.sources) assert.equal(hash(readFileSync(join(formalSourceRoot, source.path))), source.digest, `Current formal source bytes: ${source.path}`);
const core = await import(pathToFileURL(join(coreDirectory, 'index.ts')).href);
const referenceFile = args.get('--reference');
const referenceReport = referenceFile ? JSON.parse(readFileSync(resolve(referenceFile))) : null;
const reference = referenceReport ? await import(pathToFileURL(join(referenceReport.coreSnapshotDirectory, 'index.ts')).href) : null;
const target = architecture.nodes.find(node => node.label === 'network' && node.children.length === 300);
assert.ok(target, 'Expected source-backed 300-layer network');
const initial = core.createDocument(architecture);
const originalArchitecture = JSON.stringify(architecture);
const phaseSamples = {};
function measure(phase, operation, record) {
  const started = process.hrtime.bigint();
  const result = operation();
  const elapsedMs = Number(process.hrtime.bigint() - started) / 1e6;
  if (record) (phaseSamples[phase] ??= []).push(elapsedMs);
  return result;
}
let receipt;
for (let iteration = 0; iteration < warmup + samples; iteration++) {
  const record = iteration >= warmup;
  const history = core.createHistory(initial);
  const beforeBytes = JSON.stringify(history);
  const expanded = measure('reduceHistoryExpand', () => core.reduceHistory(history, { type: 'apply', operations: [{ type: 'expand', id: target.id, expanded: true }] }), record);
  const expandedScene = measure('buildExpandedScene', () => core.buildScene(expanded.document), record);
  const expandedSvg = measure('renderExpandedSvg', () => core.renderSvg(expandedScene, { interactive: true }), record);
  const collapsed = measure('reduceHistoryCollapse', () => core.reduceHistory(expanded, { type: 'apply', operations: [{ type: 'expand', id: target.id, expanded: false }] }), record);
  const collapsedScene = measure('buildCollapsedScene', () => core.buildScene(collapsed.document), record);
  const collapsedSvg = measure('renderCollapsedSvg', () => core.renderSvg(collapsedScene, { interactive: true }), record);
  measure('cloneExpandedDocument', () => structuredClone(expanded.document), record);
  measure('validateExpandedDocument', () => core.validateDocument(expanded.document), record);
  const undone = measure('undo', () => core.reduceHistory(collapsed, { type: 'undo' }), record);
  const redone = measure('redo', () => core.reduceHistory(undone, { type: 'redo' }), record);
  assert.equal(JSON.stringify(history), beforeBytes, 'No input history mutation');
  assert.equal(JSON.stringify(expanded.document.architecture), originalArchitecture, 'No source/semantic mutation');
  assert.equal(expandedScene.nodes.length, 304);
  assert.equal(expandedScene.edges.length, 302);
  assert.equal(collapsedScene.nodes.length, 4);
  assert.deepEqual(undone.document.expandedIds, expanded.document.expandedIds);
  assert.deepEqual(redone.document.layout, collapsed.document.layout);
  assert.equal(redone.document.revision, collapsed.document.revision + 2);
  if (reference) {
    const baselineHistory = reference.createHistory(reference.createDocument(architecture));
    const baselineExpanded = reference.reduceHistory(baselineHistory, { type: 'apply', operations: [{ type: 'expand', id: target.id, expanded: true }] });
    const baselineCollapsed = reference.reduceHistory(baselineExpanded, { type: 'apply', operations: [{ type: 'expand', id: target.id, expanded: false }] });
    assert.deepEqual(expanded, baselineExpanded, 'Expanded document/history matches baseline');
    assert.deepEqual(collapsed, baselineCollapsed, 'Collapsed document/history matches baseline');
    assert.deepEqual(expandedScene, reference.buildScene(baselineExpanded.document), 'Expanded scene matches baseline');
    assert.deepEqual(collapsedScene, reference.buildScene(baselineCollapsed.document), 'Collapsed scene matches baseline');
    assert.equal(expandedSvg, reference.renderSvg(reference.buildScene(baselineExpanded.document), { interactive: true }), 'Expanded SVG bytes match baseline');
    assert.equal(collapsedSvg, reference.renderSvg(reference.buildScene(baselineCollapsed.document), { interactive: true }), 'Collapsed SVG bytes match baseline');
  }
  receipt = { expandedSceneSha256: hash(JSON.stringify(expandedScene)), collapsedSceneSha256: hash(JSON.stringify(collapsedScene)), expandedSvgSha256: hash(expandedSvg), collapsedSvgSha256: hash(collapsedSvg) };
}
const percentile = (values, p) => [...values].sort((a, b) => a - b)[Math.ceil(values.length * p) - 1];
const phases = Object.fromEntries(Object.entries(phaseSamples).map(([name, values]) => [name, { samples: values, p50Ms: percentile(values, .5), p95Ms: percentile(values, .95), maxMs: Math.max(...values) }]));
assert.deepEqual(codeDigests(coreDirectory), copiedCodeDigests);
writeFileSync(output, JSON.stringify({ schemaVersion: 1, scope: 'CPU-only formal TypeScript core; no browser latency, paint, FPS or Event Timing claim', timer: 'process.hrtime.bigint monotonic nanoseconds', samples, warmup, fixture: { entry: architecture.entry, sourceDigest: architecture.sourceDigest, irDigest: architecture.irDigest, architectureFile: resolve(architectureFile), formalSourceRoot, currentSourceBytesMatched: true, architectureSha256: hash(architectureBytes), sources: architecture.sources.map(source => ({ path: source.path, sha256: source.digest })) }, environment: { node: process.version, platform: platform(), arch: arch(), cpu: cpus()[0]?.model }, targetId: target.id, coreSnapshotDirectory: coreDirectory, copiedCodeDigests, scriptSha256: hash(readFileSync(fileURLToPath(import.meta.url))), referenceReport: referenceFile ? resolve(referenceFile) : null, referenceBytesMatched: !!reference, semanticChecks: { inputUnmutated: true, architectureUnmutated: true, undoRedo: true, expandedNodes: 304, expandedEdges: 302, collapsedNodes: 4 }, receipt, phases }, null, 2) + '\n');
console.log(JSON.stringify({ output, coreSnapshotDirectory: coreDirectory, phases: Object.fromEntries(Object.entries(phases).map(([name, phase]) => [name, { p50Ms: phase.p50Ms, p95Ms: phase.p95Ms }])) }, null, 2));
