#!/usr/bin/env node
/** Exact candidate/call counts in copied instrumentation, never a timing run. */
import assert from 'node:assert/strict';
import { cpSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { pathToFileURL } from 'node:url';

const report = JSON.parse(readFileSync(process.argv[2]));
const architecture = JSON.parse(readFileSync(process.argv[3]));
const output = process.argv[4];
const directory = join(mkdtempSync(join(tmpdir(), 'archcanvas-core-trace-')), 'core');
cpSync(report.coreSnapshotDirectory, directory, { recursive: true });
const helper = "function count(name: string) { const counts = (globalThis as any).__ARCHCANVAS_CORE_COUNTS__; counts[name] = (counts[name] ?? 0) + 1; }\n";
function instrument(file, replacements) {
  let source = readFileSync(join(directory, file), 'utf8');
  for (const [before, after] of replacements) source = source.replaceAll(before, after);
  writeFileSync(join(directory, file), helper + source);
}
instrument('document.ts', [
  ["import { buildScene } from './scene.ts';", "import { buildScene as actualBuildScene } from './scene.ts'; function buildScene(document: CanvasDocument) { count('buildSceneCallsInsideDocument'); return actualBuildScene(document); }"],
  ['structuredClone(v)', "(count('structuredCloneCalls'), structuredClone(v))"],
  ['function subtreePinned(document: CanvasDocument, id: string): boolean {', "function subtreePinned(document: CanvasDocument, id: string): boolean { count('pinnedNodeIndexRebuilds');"],
]);
instrument('validate.ts', [
  ['export function validateArchitecture(value: unknown): Architecture {', "export function validateArchitecture(value: unknown): Architecture { count('validateArchitectureCalls');"],
  ['export function validateDocument(value: unknown): CanvasDocument {', "export function validateDocument(value: unknown): CanvasDocument { count('validateDocumentCalls');"],
]);
instrument('scene.ts', [
  ['export function buildScene(document: CanvasDocument): Scene {', "export function buildScene(document: CanvasDocument): Scene { count('buildSceneCalls');"],
  ['primaryIds.filter(id => ranks.get(id) === level)', "primaryIds.filter(id => (count('levelCandidates'), ranks.get(id) === level))"],
  ['links.filter(([, target]) => target === id)', "links.filter(([, target]) => (count('predecessorCandidates'), target === id))"],
  ["projected.filter(({ s, t }) => (direction === 'out' ? s : t) === id)", "projected.filter(({ s, t }) => (count('projectedPortCandidates'), (direction === 'out' ? s : t) === id))"],
  ['architecture.edges.filter(e => canonicalEdgeIds.includes(e.id))', "architecture.edges.filter(e => (count('canonicalEdgeCandidates'), canonicalEdgeIds.includes(e.id)))"],
  ['projected.slice(0, index).filter(p => p.s === s && p.t === t && p.e.tensorId === e.tensorId && p.e.role === e.role)', "projected.slice(0, index).filter(p => (count('parallelCandidates'), p.s === s && p.t === t && p.e.tensorId === e.tensorId && p.e.role === e.role))"],
  ["for (const item of projected) for (const direction of ['in', 'out'] as const) {", "for (const item of projected) for (const direction of ['in', 'out'] as const) { count('projectedPortIndexInsertions');"],
]);
globalThis.__ARCHCANVAS_CORE_COUNTS__ = {};
const core = await import(pathToFileURL(join(directory, 'index.ts')).href);
const initial = core.createDocument(architecture), history = core.createHistory(initial);
const target = architecture.nodes.find(node => node.label === 'network' && node.children.length === 300);
const phases = {};
function trace(name, operation) {
  globalThis.__ARCHCANVAS_CORE_COUNTS__ = {};
  const value = operation(); phases[name] = { ...globalThis.__ARCHCANVAS_CORE_COUNTS__ }; return value;
}
const expanded = trace('reduceHistoryExpand', () => core.reduceHistory(history, { type: 'apply', operations: [{ type: 'expand', id: target.id, expanded: true }] }));
const expandedScene = trace('buildExpandedScene', () => core.buildScene(expanded.document));
trace('reduceHistoryCollapse', () => core.reduceHistory(expanded, { type: 'apply', operations: [{ type: 'expand', id: target.id, expanded: false }] }));
assert.equal(expandedScene.nodes.length, 304); assert.equal(expandedScene.edges.length, 302);
writeFileSync(output, JSON.stringify({ schemaVersion: 1, scope: 'Exact call/candidate trace from copied instrumented code; no timing/browser claim', referenceCodeDigests: report.copiedCodeDigests, instrumentedDirectory: directory, sourceDigest: architecture.sourceDigest, irDigest: architecture.irDigest, phases }, null, 2) + '\n');
console.log(JSON.stringify(phases, null, 2));

