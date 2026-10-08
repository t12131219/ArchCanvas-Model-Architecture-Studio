import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import ts from 'typescript';
import { applyVisualBatch, buildScene, createDocument, createHistory, reduceHistory } from '../src/core/index.ts';
import { blankDraft, changeDraft, draftHistory, removeDraftNode, travelDraft } from '../src/authoring.ts';
import { authoringCameraAtViewport, followSourceView, parseAuthoringWorkspace, reopenAuthoringWorkspace, resumeSourceAuthoring, sourceAuthoringKey } from '../src/sourceAuthoringSession.ts';
import type { AuthoringWorkspace, SourceAuthoringView } from '../src/sourceAuthoringSession.ts';
import type { AuthoredDraft } from '../src/authoring.ts';
import type { ImportedSourceDraft } from '../src/api.ts';
import type { CanvasDocument, Scene } from '../src/core/types.ts';
import { resumeGeneratedWorkspace, readGeneratedWorkspace, writeGeneratedWorkspace } from '../src/generatedWorkspace.ts';
import type { GeneratedWorkspaceBinding } from '../src/generatedWorkspace.ts';

const run = promisify(execFile), project = fileURLToPath(new URL('../../', import.meta.url));
async function python(expression: string, value?: unknown) {
  const result = await run(`${project}.venv/bin/python`, ['-I', '-S', '-B', '-c',
    `import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_authoring import import_source_draft,rebase_source_frontier;from archcanvas_python import analyze_source;v=json.loads(sys.argv[2]);${expression}`, project, JSON.stringify(value ?? null)]);
  return JSON.parse(result.stdout);
}
async function fixture() {
  const architecture = await python('print(json.dumps(analyze_source(v,"model:Pair")))',
    'from torch import nn\nclass Pair(nn.Module):\n def __init__(self):\n  super().__init__(); self.fc=nn.Linear(4,4); self.act=nn.GELU()\n def forward(self,x): return self.act(self.fc(x))\n');
  const document = createDocument(architecture);
  const imported = await importSource(document);
  return { document, imported };
}
const importSource = (document: CanvasDocument) => python('print(json.dumps(import_source_draft(v[0],v[1])))', [document, buildScene(document)]) as Promise<ImportedSourceDraft>;
const rebaseSource = (draft: AuthoredDraft, document: CanvasDocument, scene: Scene) => python('print(json.dumps(rebase_source_frontier(v[0],v[1],v[2])))', [draft, document, scene]) as Promise<ImportedSourceDraft>;
const view: SourceAuthoringView = { selection: [], camera: { x: -44, y: 121, zoom: .5 }, viewport: { width: 672, height: 711 }, tool: 'pan', sourceHistory: { past: 3, future: 1 } };
function find(draft: AuthoredDraft, kind: string) { return draft.nodes.find(node => draft.sourceProvenance!.nodeRefs[node.id]?.kind === kind)!; }
function extract(file: string, component: string, names: string[]) {
  const source = readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8');
  const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const declaration = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === component);
  assert.ok(declaration && ts.isFunctionDeclaration(declaration) && declaration.body);
  return names.map(name => { const statement = declaration.body!.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === name);
    assert.ok(statement, `${file} actual callback ${name}`); return statement.getText(ast); }).join('\n');
}

function appHarness(document: CanvasDocument, imported: ImportedSourceDraft) {
  const historyRef = { current: createHistory(document) }, cameraRef = { current: { ...view.camera } }, loadSequence = { current: 2 };
  const authoringSessions = { current: new Map<string, AuthoringWorkspace>() }, authoringSessionKey = { current: null as string | null };
  const generatedWorkspaces = { current: new Map<string, GeneratedWorkspaceBinding>() }, baselines: Array<AuthoredDraft | undefined> = [];
  const cache = new Map<string, string>(), localStorage = { getItem: (key: string) => cache.get(key) ?? null, setItem: (key: string, value: string) => { cache.set(key, value); } };
  const opened: AuthoringWorkspace[] = [], failures: string[] = [], busyStates: boolean[] = [], apiCalls: string[] = [];
  const env = { historyRef, cameraRef, loadSequence, authoringSessions, authoringSessionKey, generatedWorkspaces, resumeGeneratedWorkspace, readGeneratedWorkspace, writeGeneratedWorkspace, localStorage, selection: { kind: 'node', ids: [] as string[] }, tool: 'select', busy: false,
    activeRecovery: null, cancelGesture: () => {}, readCameraViewport: () => view.viewport, sourceAuthoringKey, followSourceView, resumeSourceAuthoring, buildScene,
    api: { importSourceDraft: async () => { apiCalls.push('import'); return imported; }, sourceDraftFrontier: async (draft: AuthoredDraft, doc: CanvasDocument, scene: Scene) => { apiCalls.push('rebase'); return rebaseSource(draft, doc, scene); } },
    setFailure: (value: string) => { failures.push(value); }, setBusy: (value: boolean) => { busyStates.push(value); },
    setBrowseBaseline: (draft: AuthoredDraft | undefined) => { baselines.push(draft); },
    setAuthoringWorkspace: (workspace: AuthoringWorkspace) => { opened.push(workspace); }, setAuthoringOpen: () => {} };
  const code = ts.transpileModule(extract('App.tsx', 'App', ['sourceDraftKey', 'cacheGeneratedWorkspace', 'retainAuthoringWorkspace', 'continueModelAuthoring']),
    { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  const callbacks = new Function(...Object.keys(env), `${code};return {continueModelAuthoring,retainAuthoringWorkspace,steer(ids,nextTool){selection={kind:'node',ids};tool=nextTool}};`)(...Object.values(env)) as {
      continueModelAuthoring: () => Promise<void>; retainAuthoringWorkspace: (workspace: AuthoringWorkspace) => void; steer: (ids: string[], tool: string) => void };
  return { ...callbacks, historyRef, cameraRef, authoringSessions, generatedWorkspaces, baselines, opened, failures, busyStates, apiCalls };
}

test('actual App callbacks retain draft undo/redo and follow same-revision camera, selection and tool on multiple returns', async () => {
  const { document, imported } = await fixture(), h = appHarness(document, imported);
  const sourceHistoryBefore = JSON.stringify(h.historyRef.current);
  await h.continueModelAuthoring(); assert.equal(h.apiCalls.length, 1);
  const first = h.opened.at(-1)!, fc = find(first.draft, 'Linear');
  const history = changeDraft(draftHistory(first.draft), draft => { draft.nodes.find(node => node.id === fc.id)!.parameters.out_features = 7; });
  h.retainAuthoringWorkspace({ ...first, draft: history.draft, history });
  h.cameraRef.current = { x: 189.115, y: 143.5, zoom: .538 }; h.steer([first.draft.sourceProvenance!.nodeRefs[fc.id].nodeId], 'pan');
  await h.continueModelAuthoring();
  const second = h.opened.at(-1)!;
  assert.equal(second.history, history); assert.deepEqual(second.selection, [fc.id]); assert.deepEqual(second.camera, h.cameraRef.current);
  assert.deepEqual(second.viewport, view.viewport); assert.equal(second.tool, 'pan'); assert.equal(second.draft.nodes.find(node => node.id === fc.id)!.parameters.out_features, 7);
  h.retainAuthoringWorkspace(second); h.steer([], 'select'); h.cameraRef.current = { x: -241, y: 411, zoom: 1.2 };
  await h.continueModelAuthoring(); assert.deepEqual(h.opened.at(-1)!.selection, []); assert.equal(h.opened.at(-1)!.history, history);
  assert.deepEqual(h.opened.at(-1)!.camera, h.cameraRef.current); assert.equal(h.apiCalls.length, 1);
  assert.equal(JSON.stringify(h.historyRef.current), sourceHistoryBefore, 'source canvas history is never replaced by semantic draft snapshots');
});

test('real source rebase preserves parameters, added nodes and edges, deletion tombstones and both history stacks', async () => {
  const { document, imported } = await fixture(), fc = find(imported.draft, 'Linear'), act = find(imported.draft, 'GELU');
  let history = changeDraft(draftHistory(imported.draft), draft => { draft.nodes.find(node => node.id === fc.id)!.parameters.out_features = 7;
    draft.nodes.find(node => node.id === fc.id)!.position.x += 23; draft.nodes.push({ id: 'extra', kind: 'Identity', label: '新增模块', parameters: {}, position: { x: -900, y: 42 } });
    const incoming = draft.edges.find(edge => edge.target.nodeId === fc.id)!;
    draft.edges.push({ id: 'extra_edge', source: { ...incoming.source }, target: { nodeId: 'extra', portId: 'input' } }); });
  history = changeDraft(history, draft => removeDraftNode(draft, act.id));
  history = changeDraft(history, draft => { draft.nodes.find(node => node.id === fc.id)!.label = 'future label'; });
  history = travelDraft(history, 'undo');
  const workspace: AuthoringWorkspace = { draft: history.draft, history, storageRevision: 3, savedRevision: 2, camera: view.camera }, before = JSON.stringify(workspace);
  const canonical = imported.draft.sourceProvenance!.nodeRefs[fc.id].nodeId;
  const changed = applyVisualBatch(document, [{ type: 'move', ids: [canonical], dx: 49, dy: -17, scope: 'current-frontier' }, { type: 'alias', id: canonical, label: 'source label' }]);
  const rebased = await resumeSourceAuthoring(workspace, changed, { ...view, selection: [canonical] }, rebaseSource);
  assert.equal(JSON.stringify(workspace), before); assert.equal(rebased.history!.past.length, history.past.length); assert.equal(rebased.history!.future.length, 1);
  assert.equal(rebased.draft.nodes.find(node => node.id === fc.id)!.parameters.out_features, 7);
  const expected = rebased.draft.sourceProvenance!.originalGraph.nodes.find(node => node.id === fc.id)!.position;
  assert.deepEqual(rebased.draft.nodes.find(node => node.id === fc.id)!.position, { x: expected.x + 23, y: expected.y });
  assert.equal(rebased.draft.nodes.find(node => node.id === fc.id)!.label, 'source label');
  assert.ok(!rebased.draft.nodes.some(node => node.id === act.id)); assert.ok(rebased.draft.sourceCache!.removedNodeIds.includes(act.id));
  assert.deepEqual(rebased.draft.nodes.find(node => node.id === 'extra'), history.draft.nodes.find(node => node.id === 'extra'));
  assert.deepEqual(rebased.draft.edges.find(edge => edge.id === 'extra_edge'), history.draft.edges.find(edge => edge.id === 'extra_edge'));
  assert.equal(rebased.draft.revision, history.draft.revision + 1); assert.equal(rebased.savedRevision, 2, 'rebase remains visibly unsaved');
  for (const snapshot of [rebased.draft, ...rebased.history!.past, ...rebased.history!.future]) assert.equal(snapshot.sourceProvenance!.visualRevision, changed.revision);
  const undone = travelDraft(rebased.history!, 'undo'); assert.ok(undone.draft.nodes.some(node => node.id === act.id), 'deletion undo still restores the operator');
  const redone = travelDraft(rebased.history!, 'redo'); assert.equal(redone.draft.nodes.find(node => node.id === fc.id)!.label, 'future label');
  assert.ok(!redone.draft.nodes.some(node => node.id === act.id));
});

test('actual App visual-revision return reprojects complete history and preserves source history byte-for-byte', async () => {
  const { document, imported } = await fixture(), h = appHarness(document, imported);
  await h.continueModelAuthoring(); const first = h.opened.at(-1)!;
  const history = changeDraft(draftHistory(first.draft), draft => { draft.title = 'edited title'; });
  h.retainAuthoringWorkspace({ ...first, draft: history.draft, history });
  h.historyRef.current = reduceHistory(h.historyRef.current, { type: 'apply', operations: [{ type: 'alias', id: document.architecture.nodes.find(node => node.kind === 'Linear')!.id, label: 'source revised' }] });
  const before = JSON.stringify(h.historyRef.current); await h.continueModelAuthoring();
  const resumed = h.opened.at(-1)!; assert.equal(resumed.history!.past.length, 1); assert.equal(resumed.draft.title, 'edited title');
  assert.equal(resumed.draft.sourceProvenance!.visualRevision, h.historyRef.current.document.revision); assert.equal(JSON.stringify(h.historyRef.current), before);
  assert.deepEqual(resumed.sourceHistory, { past: 1, future: 0 }); assert.deepEqual(h.apiCalls, ['import', 'rebase', 'rebase', 'rebase'], 'draft, undo snapshot and no-change view baseline are each rebased');
});

test('changed source/IR or an invalid history rebase is rejected atomically before replacing a retained session', async () => {
  const { document, imported } = await fixture(); const history = changeDraft(draftHistory(imported.draft), draft => { draft.title = 'keep'; });
  const workspace = { draft: history.draft, history }, bytes = JSON.stringify(workspace);
  const changed = structuredClone(document); changed.architecture.irDigest = 'changed';
  await assert.rejects(resumeSourceAuthoring(workspace, changed, view, rebaseSource), /摘要/); assert.equal(JSON.stringify(workspace), bytes);
  const revised = { ...document, revision: document.revision + 1 }; let count = 0;
  await assert.rejects(resumeSourceAuthoring(workspace, revised, view, async (draft, doc, scene) => { if (++count === 2) throw new Error('snapshot failure'); return rebaseSource(draft, doc, scene); }), /snapshot failure/);
  assert.equal(JSON.stringify(workspace), bytes);
  const h = appHarness(document, imported); await h.continueModelAuthoring(); h.historyRef.current.document = changed;
  await h.continueModelAuthoring(); assert.equal(h.opened.length, 1); assert.match(h.failures.at(-1)!, /摘要/); assert.deepEqual(h.apiCalls, ['import']);
});

test('saved/reopened draft retains view and undo, browser recovery restores both stacks and rejects cross-source history', async () => {
  const { imported } = await fixture(); const original = imported.draft;
  const edited = changeDraft(draftHistory(original), draft => { draft.title = 'unsaved title'; });
  const workspace: AuthoringWorkspace = { draft: edited.draft, history: edited, storageRevision: 1, savedRevision: 0, camera: view.camera,
    viewport: view.viewport, selection: [original.nodes[0].id], tool: 'pan' };
  const saved = reopenAuthoringWorkspace(workspace, original, 2);
  assert.equal(saved.history!.past.length, 2); assert.equal(saved.draft.title, original.title); assert.equal(saved.savedRevision, saved.draft.revision);
  assert.deepEqual(saved.camera, view.camera); assert.deepEqual(saved.selection, workspace.selection); assert.equal(saved.tool, 'pan');
  assert.equal(travelDraft(saved.history!, 'undo').draft.title, 'unsaved title');
  const reloaded = parseAuthoringWorkspace(JSON.parse(JSON.stringify(saved)))!; assert.deepEqual(reloaded, { ...saved, viewBaseline: undefined });
  const corrupt = structuredClone(saved); corrupt.history!.past[0].sourceProvenance!.sourceDigest = 'changed'; assert.equal(parseAuthoringWorkspace(corrupt), null);
  const noChange = reopenAuthoringWorkspace(saved, original, 2); assert.equal(noChange.history, saved.history);
});

test('source→draft viewport change preserves world centre and close-up zoom without changing canvas geometry', () => {
  const source = { width: 672, height: 711 }, draft = { width: 817, height: 701 }, camera = { x: 189.115, y: 143.5, zoom: .538 };
  const translated = authoringCameraAtViewport(camera, source, draft);
  const centre = (c: typeof camera, v: typeof source) => ({ x: (v.width / 2 - c.x) / c.zoom, y: (v.height / 2 - c.y) / c.zoom });
  assert.deepEqual(centre(translated, draft), centre(camera, source)); assert.equal(translated.zoom, camera.zoom);
  assert.deepEqual(authoringCameraAtViewport(translated, draft, source), camera);
});

test('actual AuthoringStudio reopen callback keeps camera/selection and undo; save commits only matching current bytes', async () => {
  const { imported } = await fixture(), original = imported.draft;
  const history = changeDraft(draftHistory(original), draft => { draft.title = 'edited'; });
  const currentRef = { current: history }, messages: string[] = [], selectedIds = [history.draft.nodes[0].id];
  const changed: { history?: typeof history; saved?: number; storage?: number; selection?: unknown } = {};
  const env = { busy: false, currentRef, history, storageRevision: 1, savedRevision: 0, selectedIds, camera: view.camera, tool: 'pan',
    cancel: () => {}, setBusy: () => {}, setBusyOperation: () => {}, setStorageRevision: (v: number) => { changed.storage = v; },
    setSavedRevision: (v: number) => { changed.saved = v; }, setHistory: (v: typeof history) => { changed.history = v; },
    setSelection: (v: unknown) => { changed.selection = v; }, setGenerated: () => {}, clearError: () => {}, reportError: (reason: unknown) => { throw reason; },
    setNotice: (v: string) => messages.push(v), reopenAuthoringWorkspace,
    saving: { current: false }, invalidFieldsRef: { current: [] },
    api: { draft: async () => ({ draft: original, revision: 2 }), saveDraft: async () => ({ draft: currentRef.current.draft, revision: 3 }) } };
  const code = ts.transpileModule(extract('AuthoringStudio.tsx', 'AuthoringStudio', ['reopen', 'save']), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  const callbacks = new Function(...Object.keys(env), `${code};return {reopen,save}`)(...Object.values(env)) as { reopen: () => Promise<void>; save: () => Promise<void> };
  await callbacks.reopen(); assert.equal(currentRef.current.past.length, 2); assert.equal(currentRef.current.draft.title, original.title);
  assert.deepEqual(changed.selection, { node: selectedIds[0], nodes: selectedIds }); assert.match(messages.at(-1)!, /撤销记录保留/);
  await callbacks.save(); assert.equal(changed.storage, 3); assert.equal(changed.saved, currentRef.current.draft.revision);
  assert.equal(travelDraft(currentRef.current, 'undo').draft.title, 'edited');
});
