import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { blankDraft, changeDraft, draftHistory, travelDraft } from '../src/authoring.ts';
import type { AuthoringWorkspace } from '../src/sourceAuthoringSession.ts';
import { parseAuthoringWorkspace } from '../src/sourceAuthoringSession.ts';
import { AUTHORING_CACHE_ERROR, AUTHORING_WORKSPACE_CACHE, createAuthoringWorkspaceWriter, restoreCachedAuthoringWorkspace } from '../src/authoringWorkspaceCache.ts';

const tick = () => new Promise(resolve => setImmediate(resolve));
function workspace(): AuthoringWorkspace {
  const initial = blankDraft('draft-recoverable');
  initial.nodes.push({ id: 'input', kind: 'Input', label: 'x', parameters: { shape: [1, 4] }, position: { x: 10, y: 20 } });
  let history = changeDraft(draftHistory(initial), draft => { draft.title = 'first edit'; });
  history = changeDraft(history, draft => { draft.title = 'second edit'; });
  history = travelDraft(history, 'undo');
  return { draft: history.draft, history, storageRevision: 7, savedRevision: 0, selection: ['input'],
    camera: { x: -42, y: 211, zoom: .55 }, viewport: { width: 883, height: 701 }, tool: 'pan',
    sourceHistory: { past: 4, future: 2 }, viewBaseline: structuredClone(initial) };
}
function storage(value: unknown = null) {
  let bytes = value === null ? null : JSON.stringify(value), removed = 0, reads = 0;
  return { getItem(key: string) { assert.equal(key, AUTHORING_WORKSPACE_CACHE); reads++; return bytes; },
    removeItem(key: string) { assert.equal(key, AUTHORING_WORKSPACE_CACHE); bytes = null; removed++; },
    get removed() { return removed; }, get reads() { return reads; } };
}

test('explicit authoring sessions take precedence without reading browser storage or creating a fallback', async () => {
  const explicit = workspace(), legacy = storage();
  const result = await restoreCachedAuthoringWorkspace(() => { throw Error('unexpected blank'); }, explicit,
    async () => { throw Error('unexpected database read'); }, legacy);
  assert.equal(result.workspace, explicit); assert.equal(result.writable, true); assert.equal(legacy.reads, 0);
});

test('IndexedDB recovery preserves unsaved edits, both history stacks, selection, camera and separate source-history counts', async () => {
  const original = workspace(), legacy = storage({ draft: blankDraft('stale') });
  const result = await restoreCachedAuthoringWorkspace(() => { throw Error('unexpected blank'); }, undefined,
    async key => { assert.equal(key, AUTHORING_WORKSPACE_CACHE); return structuredClone(original); }, legacy);
  assert.deepEqual(result.workspace, original); assert.equal(legacy.reads, 0);
  assert.equal(travelDraft(result.workspace.history!, 'redo').draft.title, 'second edit');
  assert.equal(travelDraft(result.workspace.history!, 'undo').draft.title, original.history!.past[0].title);
  assert.equal(result.workspace.savedRevision, 0, 'browser recovery is not an explicit server save');
  for (const sourceHistory of [{ past: -1, future: 0 }, { past: 0, future: NaN }, 'forged']) {
    assert.equal(parseAuthoringWorkspace({ ...original, sourceHistory }), null);
  }
});

test('missing or damaged async cache migrates legacy state only after its replacement transaction commits', async () => {
  const original = workspace(), legacy = storage(original);
  const recovered = await restoreCachedAuthoringWorkspace(() => { throw Error('unexpected blank'); }, undefined, async () => ({ broken: true }), legacy);
  assert.deepEqual(recovered.workspace, original); assert.equal(legacy.removed, 0);
  let finish!: () => void, committed: unknown;
  const writer = createAuthoringWorkspaceWriter(async (_key, value) => {
    await new Promise<void>(resolve => { finish = resolve; }); committed = structuredClone(value);
  }, legacy);
  const saving = writer(recovered.workspace); assert.equal(legacy.removed, 0);
  finish(); await saving;
  assert.deepEqual(committed, original); assert.equal(legacy.removed, 1);
});

test('failed reads retain a usable legacy copy, but never overwrite an unread database with a blank fallback', async () => {
  const initial = workspace(), blank = { draft: blankDraft('fallback') };
  const read = async () => { throw Error('database unavailable'); };
  const recovered = await restoreCachedAuthoringWorkspace(() => blank, undefined, read, storage(initial));
  assert.deepEqual(recovered.workspace, initial); assert.equal(recovered.writable, true); assert.equal(recovered.warning, AUTHORING_CACHE_ERROR);
  const failed = await restoreCachedAuthoringWorkspace(() => blank, undefined, read, storage());
  assert.equal(failed.workspace, blank); assert.equal(failed.writable, false); assert.equal(failed.warning, AUTHORING_CACHE_ERROR);
  const missing = await restoreCachedAuthoringWorkspace(() => blank, undefined, async () => undefined, storage());
  assert.equal(missing.workspace, blank); assert.equal(missing.writable, true); assert.equal(missing.warning, undefined);
});

test('ordered writer coalesces pointer updates and commits the latest full workspace after a failed earlier transaction', async () => {
  const original = workspace(), legacy = storage(original), written: AuthoringWorkspace[] = [];
  const finishes: Array<{ resolve: () => void; reject: (reason: unknown) => void }> = [];
  const writer = createAuthoringWorkspaceWriter(async (_key, value) => {
    written.push(structuredClone(value));
    await new Promise<void>((resolve, reject) => { finishes.push({ resolve, reject }); });
  }, legacy);
  let settled = false;
  const first = writer(original); const failedFirst = assert.rejects(first, /quota/);
  const queued: Promise<void>[] = [];
  for (let x = 0; x < 50; x++) queued.push(writer({ ...original, camera: { ...original.camera!, x } }));
  const all = Promise.all(queued).then(() => { settled = true; });
  assert.equal(written.length, 1); assert.equal(settled, false);
  finishes[0].reject(Error('quota')); await failedFirst; await tick();
  assert.equal(legacy.removed, 0); assert.equal(written.length, 2, 'one pending complete snapshot replaces fifty queued camera writes');
  assert.equal(written[1].camera!.x, 49); assert.deepEqual(written[1].history, original.history); assert.equal(settled, false);
  finishes[1].resolve(); await all;
  assert.equal(legacy.removed, 1); assert.equal(settled, true); assert.equal(original.savedRevision, 0);
});

const source = readFileSync(new URL('../src/AuthoringStudio.tsx', import.meta.url), 'utf8');
const ast = ts.createSourceFile('AuthoringStudio.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const component = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'AuthoringStudio');
assert.ok(component && ts.isFunctionDeclaration(component) && component.body);
const componentBody = component.body;
function effect(needle: string, env: Record<string, unknown>) {
  const statement = componentBody.statements.find(node => ts.isExpressionStatement(node) && ts.isCallExpression(node.expression) &&
    node.expression.expression.getText(ast) === 'useEffect' && node.getText(ast).includes(needle));
  assert.ok(statement, `actual effect: ${needle}`);
  let cleanup: (() => void) | undefined;
  const code = ts.transpileModule(statement.getText(ast), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  new Function(...Object.keys(env), 'useEffect', code)(...Object.values(env), (body: () => (() => void) | undefined) => { cleanup = body(); });
  return () => cleanup?.();
}

test('actual hydration effect ignores delayed completion after unmount and does not start for an explicit initial session', async () => {
  let finish!: (value: unknown) => void, reads = 0, restored = 0, ready = 0;
  const initial = workspace();
  const env = { initialWorkspace: undefined, initial, restoreCachedAuthoringWorkspace: () => {
    reads++; return new Promise(resolve => { finish = resolve; });
  }, restoreWorkspace: () => { restored++; }, setError: () => {}, setCacheWritable: () => {}, setCacheReady: () => { ready++; } };
  const cleanup = effect('restoreCachedAuthoringWorkspace', env);
  cleanup(); finish({ workspace: initial, writable: true }); await tick();
  assert.equal(restored, 0); assert.equal(ready, 0);
  effect('restoreCachedAuthoringWorkspace', { ...env, initialWorkspace: initial }); assert.equal(reads, 1);
  effect('restoreCachedAuthoringWorkspace', env); finish({ workspace: initial, writable: true }); await tick();
  assert.equal(restored, 1); assert.equal(ready, 1);
});

test('actual hydration callback installs the restored history, view and revisions together', () => {
  const declaration = component!.body!.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'restoreWorkspace');
  assert.ok(declaration);
  const result: Record<string, unknown> = {}, currentRef = { current: null as unknown }, cameraViewport = { current: null as unknown }, fitSourceOnEntry = { current: true };
  const env: Record<string, unknown> = { currentRef, cameraViewport, fitSourceOnEntry, draftHistory };
  for (const name of ['Initial', 'History', 'StorageRevision', 'SavedRevision', 'Selection', 'Camera', 'Tool']) env[`set${name}`] = (value: unknown) => { result[name] = value; };
  const code = ts.transpileModule(declaration.getText(ast), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  const restore = new Function(...Object.keys(env), `${code}; return restoreWorkspace;`)(...Object.values(env)) as (value: AuthoringWorkspace) => void;
  const saved = workspace(); restore(saved);
  assert.equal(currentRef.current, saved.history); assert.equal(result.History, saved.history); assert.equal(result.Initial, saved);
  assert.deepEqual(result.Selection, { node: 'input', nodes: ['input'] }); assert.deepEqual(result.Camera, saved.camera);
  assert.equal(result.Tool, 'pan'); assert.equal(result.StorageRevision, 7); assert.equal(result.SavedRevision, 0);
  assert.deepEqual(cameraViewport.current, saved.viewport); assert.equal(fitSourceOnEntry.current, false);
});

test('actual persistence effect waits for hydration, reports failures, and never changes explicit-save state', async () => {
  const saved = workspace(), calls: AuthoringWorkspace[] = [], errors: string[] = [];
  const env = { cacheReady: false, cacheWritable: true, cacheWriter: { current: async (value: AuthoringWorkspace) => { calls.push(value); throw Error('quota'); } },
    history: saved.history, storageRevision: 7, savedRevision: 0, selectedIds: saved.selection, camera: saved.camera,
    cameraViewport: { current: saved.viewport }, tool: saved.tool, initial: saved, AUTHORING_CACHE_ERROR, setError: (value: string) => errors.push(value) };
  effect('cacheWriter.current!', env); assert.equal(calls.length, 0);
  effect('cacheWriter.current!', { ...env, cacheReady: true, cacheWritable: false }); assert.equal(calls.length, 0);
  effect('cacheWriter.current!', { ...env, cacheReady: true }); await tick();
  assert.deepEqual(calls[0], saved); assert.deepEqual(errors, [AUTHORING_CACHE_ERROR]); assert.equal(env.savedRevision, 0);
  const cleanup = effect('cacheWriter.current!', { ...env, cacheReady: true }); cleanup(); await tick(); assert.equal(errors.length, 1);
});
