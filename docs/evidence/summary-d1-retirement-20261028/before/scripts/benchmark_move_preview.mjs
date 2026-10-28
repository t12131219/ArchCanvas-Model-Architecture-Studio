#!/usr/bin/env node
/** Controlled CPU-only old/new drag frame paths from one standalone core copy. */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { cpSync, mkdtempSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { cpus, platform, arch, tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const args = new Map();
for (let i = 2; i < process.argv.length; i += 2) args.set(process.argv[i], process.argv[i + 1]);
const project = resolve(dirname(fileURLToPath(import.meta.url)), '..');
if (!args.get('--architecture')) throw new Error('--architecture must name the static source-backed DenseStress300 JSON');
const samples = Number(args.get('--samples') ?? 60), warmup = Number(args.get('--warmup') ?? 10);
assert.ok(Number.isInteger(samples) && samples >= 30 && samples <= 200 && Number.isInteger(warmup) && warmup >= 1);
const output = resolve(args.get('--output') ?? join(project, 'docs/evidence/m4-drag-core-performance.json'));
const directory = join(mkdtempSync(join(tmpdir(), 'archcanvas-drag-core-')), 'core');
cpSync(join(project, 'studio/src/core'), directory, { recursive: true });
const hash = value => createHash('sha256').update(value).digest('hex');
const codeDigests = () => Object.fromEntries(readdirSync(directory).filter(name => name.endsWith('.ts')).sort().map(name => [name, hash(readFileSync(join(directory, name)))]));
const digests = codeDigests(), architecturePath = resolve(args.get('--architecture'));
const architectureBytes = readFileSync(architecturePath), architecture = JSON.parse(architectureBytes);
for (const source of architecture.sources) {
  assert.equal(hash(source.content), source.digest);
  assert.equal(hash(readFileSync(join(project, 'fixtures/stress_300', source.path))), source.digest);
}
const core = await import(pathToFileURL(join(directory, 'index.ts')).href);
const preview = await import(pathToFileURL(join(directory, 'movePreview.ts')).href);
const network = architecture.nodes.find(node => node.label === 'network' && node.children.length === 300);
assert.ok(network, 'A real recovered 300-layer network is required');
const initial = core.applyVisualBatch(core.createDocument(architecture), [{ type: 'expand', id: network.id, expanded: true }]);
const history = core.createHistory(initial), initialBytes = JSON.stringify(initial), historyBytes = JSON.stringify(history);
const targetId = network.children[149], phases = {};
const measure = (name, operation, record) => {
  const start = process.hrtime.bigint(), value = operation(), elapsed = Number(process.hrtime.bigint() - start) / 1e6;
  if (record) (phases[name] ??= []).push(elapsed);
  return value;
};
let receipt;
for (let trial = 0; trial < warmup + samples; trial++) {
  const record = trial >= warmup, ids = [targetId], dx = (trial % 11 - 5) * 4, dy = (trial % 7 - 3) * 4;
  const operation = { type: 'move', ids, dx, dy };
  const session = measure('prepareOncePerGesture', () => preview.prepareMovePreview(initial, ids), record);
  let beforeScene, afterScene, beforeSvg, afterSvg;
  // Alternate order to reduce a systematic cold-cache/GC ordering bias.
  const before = () => { beforeScene = measure('beforeGuardedFrameScene', () => core.buildScene(core.applyVisualBatch(initial, [operation])), record); beforeSvg = measure('beforeRenderSvg', () => core.renderSvg(beforeScene, { interactive: true }), record); };
  const after = () => { afterScene = measure('afterPreparedFrameScene', () => preview.previewMoveScene(session, dx, dy), record); afterSvg = measure('afterRenderSvg', () => core.renderSvg(afterScene, { interactive: true }), record); };
  if (trial % 2) { after(); before(); } else { before(); after(); }
  assert.deepEqual(afterScene, beforeScene, 'Entire scene matches guarded original frame path');
  assert.equal(afterSvg, beforeSvg, 'Entire interactive SVG bytes match guarded original frame path');
  assert.equal(afterScene.nodes.length, 304); assert.equal(afterScene.edges.length, 302);
  const committed = measure('guardedCommitHistory', () => core.reduceHistory(history, { type: 'apply', operations: [operation], baseRevision: session.baseRevision }), record);
  assert.deepEqual(core.buildScene(committed.document), afterScene);
  assert.equal(committed.past.length, 1);
  const undo = core.reduceHistory(committed, { type: 'undo' }), redo = core.reduceHistory(undo, { type: 'redo' });
  assert.deepEqual(undo.document.layout, initial.layout); assert.deepEqual(redo.document.layout, committed.document.layout);
  assert.equal(JSON.stringify(initial), initialBytes); assert.equal(JSON.stringify(history), historyBytes);
  assert.deepEqual(committed.document.architecture, architecture);
  receipt = { sceneSha256: hash(JSON.stringify(afterScene)), svgSha256: hash(afterSvg) };
}

// Exact calls are counted separately in a second copied core, never in timings.
const traced = join(mkdtempSync(join(tmpdir(), 'archcanvas-drag-trace-')), 'core');
cpSync(directory, traced, { recursive: true });
const helper = "function count(name: string) { const counts = (globalThis as any).__ARCHCANVAS_MOVE_COUNTS__; counts[name] = (counts[name] ?? 0) + 1; }\n";
function instrument(file, replacements) {
  let source = readFileSync(join(traced, file), 'utf8');
  for (const [before, after] of replacements) { assert.ok(source.includes(before), file + ': missing instrumentation target'); source = source.replaceAll(before, after); }
  writeFileSync(join(traced, file), helper + source);
}
instrument('document.ts', [['structuredClone(v)', "(count('structuredClone'), structuredClone(v))"]]);
instrument('movePreview.ts', [['const snapshot = structuredClone(document);', "count('structuredClone'); const snapshot = structuredClone(document);"]]);
instrument('validate.ts', [
  ['export function validateArchitecture(value: unknown): Architecture {', "export function validateArchitecture(value: unknown): Architecture { count('validateArchitecture');"],
  ['export function validateDocument(value: unknown): CanvasDocument {', "export function validateDocument(value: unknown): CanvasDocument { count('validateDocument');"],
]);
instrument('scene.ts', [['export function buildScene(document: CanvasDocument): Scene {', "export function buildScene(document: CanvasDocument): Scene { count('buildScene');"]]);
globalThis.__ARCHCANVAS_MOVE_COUNTS__ = {};
const tracedCore = await import(pathToFileURL(join(traced, 'index.ts')).href), tracedPreview = await import(pathToFileURL(join(traced, 'movePreview.ts')).href);
const tracedDocument = tracedCore.applyVisualBatch(tracedCore.createDocument(architecture), [{ type: 'expand', id: network.id, expanded: true }]);
const tracedHistory = tracedCore.createHistory(tracedDocument), calls = {};
const trace = (name, operation) => { globalThis.__ARCHCANVAS_MOVE_COUNTS__ = {}; const value = operation(); calls[name] = { ...globalThis.__ARCHCANVAS_MOVE_COUNTS__ }; return value; };
const operation = { type: 'move', ids: [targetId], dx: 24, dy: 16 };
trace('beforeEachFrame', () => tracedCore.buildScene(tracedCore.applyVisualBatch(tracedDocument, [operation])));
const tracedSession = trace('afterOncePerGesture', () => tracedPreview.prepareMovePreview(tracedDocument, operation.ids));
trace('afterEachFrame', () => tracedPreview.previewMoveScene(tracedSession, operation.dx, operation.dy));
trace('commitIncludingAppScene', () => tracedCore.buildScene(tracedCore.reduceHistory(tracedHistory, { type: 'apply', operations: [operation], baseRevision: tracedSession.baseRevision }).document));
assert.equal(calls.beforeEachFrame.validateDocument, 2); assert.equal(calls.beforeEachFrame.structuredClone, 1); assert.equal(calls.beforeEachFrame.buildScene, 2);
assert.deepEqual(calls.afterEachFrame, { buildScene: 1 });
assert.equal(calls.commitIncludingAppScene.validateDocument, 2); assert.equal(calls.commitIncludingAppScene.structuredClone, 2);
const percentile = (values, p) => [...values].sort((a, b) => a - b)[Math.ceil(values.length * p) - 1];
const summarized = Object.fromEntries(Object.entries(phases).map(([name, values]) => [name, { samples: values, p50Ms: percentile(values, .5), p95Ms: percentile(values, .95), maxMs: Math.max(...values) }]));
assert.deepEqual(codeDigests(), digests);
writeFileSync(output, JSON.stringify({
  schemaVersion: 1, scope: 'CPU-only source-backed 300-layer drag frame paths; no browser latency, paint, INP, FPS or Event Timing claim',
  timer: 'process.hrtime.bigint monotonic nanoseconds', samples, warmup,
  experiment: 'Alternating before/after order, identical copied core/buildScene/serializer, every complete scene and interactive SVG compared outside timers',
  environment: { node: process.version, platform: platform(), arch: arch(), cpu: cpus()[0]?.model },
  fixture: { entry: architecture.entry, sourceDigest: architecture.sourceDigest, irDigest: architecture.irDigest, architectureFile: architecturePath, architectureSha256: hash(architectureBytes), currentSourceBytesMatched: true, sources: architecture.sources.map(source => ({ path: source.path, sha256: source.digest })) },
  targetId, coreSnapshotDirectory: directory, copiedCodeDigests: digests, scriptSha256: hash(readFileSync(fileURLToPath(import.meta.url))),
  appImplementationSha256: hash(readFileSync(join(project, 'studio/src/App.tsx'))),
  semanticChecks: { sceneAndSvgEqualEveryTrial: true, committedSceneMatchesPreview: true, inputAndHistoryUnmutated: true, architectureUnmutated: true, commitFullyGuarded: true, undoRedo: true, visibleNodes: 304, projectedEdges: 302 },
  calls: { instrumentedDirectory: traced, phases: calls }, receipt, phases: summarized,
  limitations: ['Snapshot preparation is additional once-per-gesture work.', 'All scene layout/projection/routing and SVG serialization still run each frame.', 'CPU equivalence does not certify DOM rendering or native browser performance.'],
}, null, 2) + '\n');
console.log(JSON.stringify({ output, phases: Object.fromEntries(Object.entries(summarized).map(([name, phase]) => [name, { p50Ms: phase.p50Ms, p95Ms: phase.p95Ms }])), calls }, null, 2));
