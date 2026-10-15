import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { createSourceAuthoringCache } from '../src/sourceAuthoringCache.ts';
import { AUTHORING_WORKSPACE_CACHE } from '../src/authoringWorkspaceCache.ts';
import { blankDraft, changeDraft, draftHistory } from '../src/authoring.ts';
import { createDocument, createHistory } from '../src/core/index.ts';
import type { Architecture, CanvasDocument } from '../src/core/types.ts';
import type { AuthoringWorkspace } from '../src/sourceAuthoringSession.ts';
import { parseAuthoringWorkspace } from '../src/sourceAuthoringSession.ts';

function fixture(identity = 'first') {
  const architecture: Architecture = { schemaVersion: 1, id: identity, label: identity, entry: 'model:Model', sourceDigest: `source-${identity}`, irDigest: `ir-${identity}`,
    nodes: [], edges: [], diagnostics: [], sources: [{ path: 'model.py', content: `# ${identity}`, digest: `file-${identity}` }] };
  const document = createDocument(architecture), draft = blankDraft(`draft-${identity}`);
  draft.sourceProvenance = { schemaVersion: 1, digest: 'provenance', documentId: document.id, visualRevision: document.revision,
    sourceDigest: document.sourceBindingDigest, irDigest: architecture.irDigest, architecture, canvas: document,
    modules: [], nodeRefs: {}, edgeRefs: {}, originalGraph: { nodes: [], edges: [] } };
  const history = changeDraft(draftHistory(draft), value => { value.title = 'unsaved model edit'; });
  const workspace: AuthoringWorkspace = { draft: history.draft, history, storageRevision: 6, savedRevision: 0,
    camera: { x: 30, y: -21, zoom: .7 }, selection: [], tool: 'pan', sourceHistory: { past: 2, future: 1 } };
  return { document, workspace: parseAuthoringWorkspace(workspace)! };
}
const noLegacy = { getItem: () => null };

test('original-source workspaces remain isolated by document, source and IR identity, with unsaved history intact', async () => {
  const a = fixture(), b = fixture('second'), values = new Map<string, unknown>();
  const cache = createSourceAuthoringCache(async key => values.get(key), async (key, value) => { values.set(key, structuredClone(value)); }, noLegacy);
  await cache.write(a.workspace); await cache.write(b.workspace);
  assert.deepEqual(await cache.read(a.document), a.workspace); assert.deepEqual(await cache.read(b.document), b.workspace);
  const normalized = { ...a.document, architecture: Object.fromEntries(Object.entries(a.document.architecture).reverse()) as Architecture };
  assert.deepEqual(await cache.read(normalized), a.workspace, 'HTTP key normalization does not change source facts');
  assert.equal(await cache.read({ ...a.document, sourceBindingDigest: 'changed-source' }), null);
  const revised = structuredClone(a.document); revised.architecture.irDigest = 'changed-ir';
  assert.equal(await cache.read(revised), null); assert.equal(values.size, 2);
});

test('a damaged or mismatched exact-key source record is rejected instead of silently replacing unsaved edits', async () => {
  const { document, workspace } = fixture(), values = new Map<string, unknown>();
  const cache = createSourceAuthoringCache(async key => values.get(key), async (key, value) => { values.set(key, structuredClone(value)); }, noLegacy);
  await cache.write(workspace);
  const key = [...values.keys()][0], original = values.get(key);
  for (const change of [
    (value: any) => { value.workspace.draft.sourceProvenance.sourceDigest = 'stale'; },
    (value: any) => { value.workspace.draft.sourceProvenance.architecture.sources[0].content = 'changed bytes'; },
    (value: any) => { value.workspace.history.past[0].id = 'draft-foreign'; },
    (value: any) => { value.workspace.storageRevision = -1; },
  ]) {
    const damaged = structuredClone(original); change(damaged); values.set(key, damaged);
    await assert.rejects(() => cache.read(document), /不一致/);
    assert.deepEqual(values.get(key), damaged, 'rejected browser records are preserved');
  }
});

test('the legacy global source draft migrates only to an exact matching source key', async () => {
  const { document, workspace } = fixture(), other = fixture('other'), values = new Map<string, unknown>([[AUTHORING_WORKSPACE_CACHE, workspace]]);
  const cache = createSourceAuthoringCache(async key => values.get(key), async (key, value) => { values.set(key, structuredClone(value)); }, noLegacy);
  assert.equal(await cache.read(other.document), null); assert.equal(values.size, 1);
  assert.deepEqual(await cache.read(document), workspace); assert.equal(values.size, 2);
  values.delete(AUTHORING_WORKSPACE_CACHE);
  assert.deepEqual(await cache.read(document), workspace, 'per-source recovery no longer depends on the global last-opened draft');
  const legacy = createSourceAuthoringCache(async () => undefined, async () => {}, { getItem: () => JSON.stringify(workspace) });
  assert.deepEqual(await legacy.read(document), workspace);
  const unavailable = createSourceAuthoringCache(async () => { throw Error('database unavailable'); }, async () => { throw Error('database unavailable'); },
    { getItem: () => JSON.stringify(workspace) });
  assert.deepEqual(await unavailable.read(document), workspace, 'an exact readable legacy source draft survives a failed migration');
  await assert.rejects(() => unavailable.read(other.document), /database unavailable/, 'an unread per-source database is never replaced by a fresh import');
});

test('source-cache writes coalesce pointer snapshots independently for each model and recover after a rejected write', async () => {
  const a = fixture(), b = fixture('second'), pending: Array<{ resolve: () => void; reject: (reason: unknown) => void }> = [];
  const written: Array<{ key: string; value: unknown }> = [];
  const cache = createSourceAuthoringCache(async () => undefined, async (key, value) => {
    written.push({ key, value: structuredClone(value) });
    await new Promise<void>((resolve, reject) => { pending.push({ resolve, reject }); });
  }, noLegacy);
  const first = cache.write(a.workspace), rejected = assert.rejects(first, /quota/);
  const queued = Array.from({ length: 40 }, (_, x) => cache.write({ ...a.workspace, camera: { ...a.workspace.camera!, x } }));
  const separate = cache.write(b.workspace);
  assert.equal(written.length, 2, 'one active transaction per source generation');
  pending[0].reject(Error('quota')); pending[1].resolve(); await rejected; await separate;
  assert.equal(written.length, 3); assert.equal((written[2].value as { workspace: AuthoringWorkspace }).workspace.camera!.x, 39);
  pending[2].resolve(); await Promise.all(queued);
  assert.equal(a.workspace.savedRevision, 0, 'browser recovery never marks the server draft saved');
});

test('actual source-session opening rejects delayed or failed cache reads without importing and overwriting a draft', async () => {
  const input = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8');
  const ast = ts.createSourceFile('App.tsx', input, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const app = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'App');
  assert.ok(app && ts.isFunctionDeclaration(app) && app.body);
  const declaration = app.body.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'continueModelAuthoring'); assert.ok(declaration);
  const code = ts.transpileModule(declaration.getText(ast), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  for (const stale of [true, false]) {
    const { document, workspace } = fixture(), historyRef = { current: createHistory(document) }, loadSequence = { current: 4 }, failures: string[] = [];
    const authoringSessions = { current: new Map<string, AuthoringWorkspace>() };
    let finish!: (value: unknown) => void, fail!: (reason: unknown) => void;
    const env = { cancelGesture() {}, historyRef, busy: false, activeRecovery: null, loadSequence, sourceDraftKey: () => 'source-key',
      generatedWorkspaces: { current: new Map() }, readPersistentGeneratedWorkspace: async () => null, authoringSessions,
      readSourceAuthoringWorkspace: () => new Promise((resolve, reject) => { finish = resolve; fail = reject; }),
      setFailure: (value: string) => { failures.push(value); }, api: { importSourceDraft: () => { throw Error('must not overwrite source edits'); } },
      setAuthoringOpen: () => { throw Error('stale or unread cache opened editor'); } };
    const open = new Function(...Object.keys(env), `${code};return continueModelAuthoring;`)(...Object.values(env)) as () => Promise<void>;
    const opening = open(); await Promise.resolve();
    if (stale) { loadSequence.current++; finish(workspace); } else fail(Error('unreadable browser database'));
    await opening; assert.equal(authoringSessions.current.size, 0);
    assert.equal(failures.length, stale ? 0 : 1);
  }
});
