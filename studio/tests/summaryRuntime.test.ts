import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { t, uiMessage } from '../src/i18n.ts';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

function callback(file: string, name: string, env: Record<string, unknown>) {
  const source = readFileSync(new URL(file, import.meta.url), 'utf8'), ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  let found: ts.FunctionDeclaration | undefined;
  function visit(node: ts.Node) { if (ts.isFunctionDeclaration(node) && node.name?.text === name) found = node; ts.forEachChild(node, visit); }
  visit(ast); assert.ok(found, `actual ${name}`);
  const code = ts.transpileModule(found.getText(ast), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  return new Function(...Object.keys(env), code + `; return ${name};`)(...Object.values(env)) as (...args: any[]) => Promise<any>;
}
const savedReceipt = { status: 'passed', runtimeVerified: true, source_files: { 'model.py': 'frozen source' }, binding: { entry: 'model:Model', source_manifest_sha256: 'digest' } };
function appEnvironment() {
  const sent: any[] = [], loadSequence = { current: 3 }, previewCase = { current: 'case' };
  const result = { receipt: savedReceipt, document: { schema: 'archcanvas-source-semantic/2' } };
  return { sent, result, loadSequence, previewCase, readyPreview: () => true, previewLayoutDisabled: false,
    previewSnapshot: { current: { graph: { generic: { ir: { runtime: savedReceipt } } } } },
    api: { observeSummary: async (value: unknown) => { sent.push(value); return result; } },
  };
}
test('actual CPU entry reuses complete receipt source text and explicit profile without creating a source transaction', async () => {
  const env = appEnvironment(), spec = { schema: 'semantic-inputs/1', cases: [] };
  const run = callback('../src/App.tsx', 'runSummaryObservation', env);
  assert.equal(await run(spec, () => {}), env.result);
  assert.deepEqual(env.sent, [{ files: savedReceipt.source_files, entry: 'model:Model', inputSpec: spec, sourceSha256: 'digest' }]);
});
test('actual CPU entry rejects a late observation after A to B to A rather than applying by case name alone', async () => {
  const env = appEnvironment(); let finish!: (value: unknown) => void;
  env.api.observeSummary = async () => new Promise(resolve => { finish = resolve; }) as any;
  const pending = callback('../src/App.tsx', 'runSummaryObservation', env)({}, () => {});
  env.loadSequence.current += 2; finish(env.result);
  await assert.rejects(pending, /模型已切换/);
});
test('actual CPU entry refuses to start after an asynchronous source response loses model ownership', async () => {
  const env: any = appEnvironment(); env.previewSnapshot.current = { graph: {} };
  env.previewEngine = { current: { source: async () => { env.loadSequence.current++; return {}; } } };
  env.sourceFromResult = () => ({ schema: 'summary-source-adapter/1', sourceSha256: 'exact' });
  env.bundlePreviewRequest = () => ({ files: { 'model.py': 'bytes' }, entry: 'model:Model' });
  await assert.rejects(callback('../src/App.tsx', 'runSummaryObservation', env)({}, () => {}), /未开始 CPU/);
  assert.equal(env.sent.length, 0);
});
test('actual API polls with the current session, exposes targeted cancellation and returns observation receipts independently of transactions', async () => {
  const writes: any[] = [], reads: any[] = [], result = { receipt: { status: 'failed', reason: 'cancelled' }, document: null };
  let cancel!: () => Promise<void>;
  const run = callback('../src/api.ts', 'observeSummary', {
    mutation: async (path: string, value: unknown) => { writes.push([path, value]); return { id: 'own-job', status: 'running' }; },
    request: async (path: string, options: unknown) => { reads.push([path, options]); return { id: 'own-job', status: 'complete', result }; },
    session: Promise.resolve('session-token'), setTimeout: (fn: () => void) => fn(),
  });
  assert.equal(await run({ files: {}, entry: 'model:Model', inputSpec: {} }, (stop: () => Promise<void>) => { cancel = stop; }), result);
  await cancel(); assert.equal(writes[1][0], '/preview/runtime-jobs/own-job/cancel');
  assert.deepEqual(reads, [['/preview/runtime-jobs/own-job', { headers: { 'X-ArchCanvas-Session': 'session-token' } }]]);
});
test('actual panel run honors cancellation requested before job creation and ignores results after unmount', async () => {
  const stopRequested = { current: false }, alive = { current: true }, cancel = { current: null }, results: unknown[] = [], errors: unknown[] = [];
  let registered!: (stop: () => Promise<void>) => void, finish!: (value: unknown) => void, stopped = 0;
  const run = callback('../src/SummaryRuntimePanel.tsx', 'run', {
    stopRequested, alive, cancel, draft: '{}', setError: (e: unknown) => errors.push(e), setPending() {}, setResult: (r: unknown) => results.push(r),
    onRun: async (_spec: unknown, onStart: typeof registered) => { registered = onStart; return new Promise(resolve => { finish = resolve; }); },
  });
  const pending = run(); stopRequested.current = true; registered(async () => { stopped++; });
  alive.current = false; finish({ receipt: savedReceipt }); await pending;
  assert.equal(stopped, 1); assert.deepEqual(results, [null]); assert.deepEqual(errors, ['']);
});
test('retained Studio fold shows explicit profile and actual unavailable environment without offering automatic execution', () => {
  const source = readFileSync(new URL('../src/SummaryRuntimePanel.tsx', import.meta.url), 'utf8');
  const code = ts.transpileModule(source.replace(/^import .*;$/gm, '').replace('export function SummaryRuntimePanel', 'function SummaryRuntimePanel'), { compilerOptions: { target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React } }).outputText;
  const Panel = new Function('React', 'useState', 'useRef', 'useEffect', 't', 'uiMessage', code + ';return SummaryRuntimePanel;')(React, React.useState, React.useRef, () => {}, t, uiMessage);
  const html = renderToStaticMarkup(React.createElement(Panel, { available: false, reason: 'isolation unavailable', hasSource: true, disabled: false, onRun() { throw Error('render must not execute'); }, onSaveEvidence() {} }));
  assert.match(html, /源码与运行证据/); assert.match(html, /添加运行证据/); assert.match(html, /isolation unavailable/); assert.doesNotMatch(html, /textarea|>运行探针<|Summary 证据视图/);
});
