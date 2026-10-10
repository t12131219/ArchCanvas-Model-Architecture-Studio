import { sameSourceSemantics } from '../src/sourcePresentation.ts';
import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';
import { blankDraft, changeDraft, draftHistory, travelDraft, addDraftNode, draftModuleSize, nextDraftPosition } from '../src/authoring.ts';
import type { AuthoredDraft, DraftCatalog, DraftHistory } from '../src/authoring.ts';
import { applyVisualBatch, buildScene, createDocument, createHistory } from '../src/core/index.ts';
import type { Architecture, CanvasDocument } from '../src/core/types.ts';
import { createGeneratedCanvas } from '../src/generatedCanvas.ts';
import * as generatedWorkspaceHelpers from '../src/generatedWorkspace.ts';
import { sameGeneratedDraft, resumeGeneratedWorkspace, readGeneratedWorkspace, writeGeneratedWorkspace, authoringViewSelection } from '../src/generatedWorkspace.ts';
import type { GeneratedWorkspaceBinding } from '../src/generatedWorkspace.ts';
import { customModuleCatalog, readCustomModuleDefinition } from '../src/customModules.ts';
import type { CustomModuleDefinition, CustomModulePreview } from '../src/customModules.ts';
import type { GeneratedDraft } from '../src/api.ts';
import { sourceAuthoringKey, followSourceView, resumeSourceAuthoring, parseAuthoringWorkspace } from '../src/sourceAuthoringSession.ts';
import type { AuthoringWorkspace, SourceAuthoringView } from '../src/sourceAuthoringSession.ts';

const studio = fileURLToPath(new URL('../', import.meta.url)), project = fileURLToPath(new URL('../../', import.meta.url));
const temporary = mkdtempSync(`${studio}.editor-workflow-independent-`);
after(() => rmSync(temporary, { recursive: true, force: true }));
async function backend(expression: string, value: unknown = null): Promise<any> {
  return new Promise((resolveResult, reject) => {
    const child = execFile(`${project}.venv/bin/python`, ['-I', '-S', '-B', '-c',
    `import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_authoring import generate_model,module_catalog,preview_custom_module,import_source_draft;from archcanvas_python import analyze_source;v=json.load(sys.stdin);${expression}`, project],
      { maxBuffer: 6_000_000 }, (error, stdout) => { if (error) reject(error); else try { resolveResult(JSON.parse(stdout)); } catch (reason) { reject(reason); } });
    child.stdin!.end(JSON.stringify(value));
  });
}
function connectedDraft() {
  const draft = blankDraft('draft-editor-independent');
  draft.title = '独立连续工作流';
  draft.nodes = [
    { id: 'input', kind: 'Input', label: '输入', parameters: { shape: [2, 4], dtype: 'float32' }, position: { x: -530, y: -260 } },
    { id: 'linear', kind: 'Linear', label: '我的投影', parameters: { in_features: 4, out_features: 4, bias: true }, position: { x: -160, y: 40 } },
    { id: 'output', kind: 'Output', label: '输出', parameters: {}, position: { x: 230, y: 350 } },
  ];
  draft.edges = [{ id: 'in', source: { nodeId: 'input', portId: 'output' }, target: { nodeId: 'linear', portId: 'input' } },
    { id: 'out', source: { nodeId: 'linear', portId: 'output' }, target: { nodeId: 'output', portId: 'input' } }];
  return draft;
}
const sourceDraft = connectedDraft();
const generated = await backend('print(json.dumps(generate_model(v)))', sourceDraft) as GeneratedDraft;
const catalog = await backend('print(json.dumps(module_catalog()))') as DraftCatalog;
const customSource = 'from torch import nn\nclass Fusion(nn.Module):\n def __init__(self,width=4):\n  super().__init__();self.project=nn.Linear(width,width)\n def forward(self,features,*,memory):\n  value=self.project(features)\n  return {"pair":(value,memory),"sum":value+memory}\n';
const customPreview = await backend('print(json.dumps(preview_custom_module(v)))',
  { source: customSource, entry: 'Fusion', label: '我的融合', constructorValues: { width: 4 } }) as CustomModulePreview;
const view: SourceAuthoringView = { selection: [], camera: { x: -72, y: 216, zoom: .61 }, viewport: { width: 723, height: 644 }, tool: 'pan', sourceHistory: { past: 2, future: 1 } };

/** Extract current functions, so callback tests fail if the actual product loses a guard or state transfer. */
function callbacks(file: string, component: string, names: string[], environment: Record<string, unknown>) {
  const input = readFileSync(`${studio}src/${file}`, 'utf8'), ast = ts.createSourceFile(file, input, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const declaration = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === component);
  assert.ok(declaration && ts.isFunctionDeclaration(declaration) && declaration.body);
  const code = names.map(name => {
    const member = declaration.body!.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === name);
    assert.ok(member, `actual ${file} callback ${name}`); return member.getText(ast);
  }).join('\n');
  const js = ts.transpileModule(code, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  return new Function(...Object.keys(environment), `${js}; return {${names.join(',')}};`)(...Object.values(environment)) as Record<string, (...args: any[]) => any>;
}
function browseHarness(draft: AuthoredDraft, options: { baseline?: AuthoredDraft; generate?: (value: AuthoredDraft) => Promise<GeneratedDraft>; open?: (value: GeneratedDraft) => Promise<void> } = {}) {
  const currentRef = { current: draftHistory(draft) }, retained: AuthoringWorkspace[] = [], reused: AuthoringWorkspace[] = [], opened: GeneratedDraft[] = [], errors: string[] = [];
  const busyStates: boolean[] = [], operations: Array<string | null> = [], generatedInputs: AuthoredDraft[] = [], flight = { current: false };
  const env = { busy: false, portEditing: false, invalidFieldsRef: { current: [] }, currentRef, storageRevision: 4, savedRevision: 2,
    selectedIds: ['linear'], camera: { ...view.camera }, cameraViewport: { current: view.viewport }, tool: view.tool, initial: { sourceHistory: view.sourceHistory },
    browseBaseline: options.baseline, onReuseView: (workspace: AuthoringWorkspace) => { reused.push(workspace); }, sameGeneratedDraft, sameSourceSemantics,
    // Aliases cover the product's synchronous lock without replacing the actual callback.
    browsing: flight, browseInFlight: flight, browseFlight: flight,
    cancel: () => {}, clearError: () => {}, setBusy: (value: boolean) => { busyStates.push(value); }, setBusyOperation: (value: string | null) => { operations.push(value); },
    api: { generateDraft: async (value: AuthoredDraft) => { generatedInputs.push(value); return options.generate ? options.generate(value) : generated; } },
    reprojectSourceDraft: async (value: AuthoredDraft) => value,
    viewStateRef: { current: (workspace: AuthoringWorkspace) => { retained.push(workspace); } },
    onOpen: async (value: GeneratedDraft) => { opened.push(value); await options.open?.(value); },
    reportError: (reason: unknown, prefix = '') => { errors.push(prefix + String(reason)); },
  };
  const actual = callbacks('AuthoringStudio.tsx', 'AuthoringStudio', ['browse'], env);
  return { browse: actual.browse, currentRef, retained, reused, opened, errors, busyStates, operations, generatedInputs, flight };
}

function generatedAppHarness(workspace: AuthoringWorkspace, existing?: CanvasDocument, stored?: Map<string, string>) {
  const authoringSessions = { current: new Map([['blank', workspace]]) }, authoringSessionKey = { current: 'blank' as string | null };
  const generatedWorkspaces = { current: new Map<string, GeneratedWorkspaceBinding>() }, values = stored ?? new Map<string, string>();
  const historyRef = { current: existing ? createHistory(existing) : null as ReturnType<typeof createHistory> | null };
  const cameraRef = { current: { ...view.camera } }, opened: AuthoringWorkspace[] = [], baselines: Array<AuthoredDraft | undefined> = [], failures: string[] = [];
  const selection = { kind: 'node', ids: [] as string[] }, registered: Architecture[] = [];
  const localStorage = { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => { values.set(key, value); } };
  const env = { ...generatedWorkspaceHelpers, historyRef, cameraRef, authoringSessions, authoringSessionKey, generatedWorkspaces,
    localStorage, selection, sourceAuthoringKey, followSourceView, resumeSourceAuthoring, buildScene, createGeneratedCanvas, createHistory, blankDraft,
    loadSequence: { current: 0 }, cameraOwner: { current: null }, cameraIntent: { current: 0 }, tool: 'pan', busy: false, portEditing: false, activeRecovery: null,
    cancelGesture: () => {}, readCameraViewport: () => view.viewport, openArchitecture: async () => {},
    api: { register: async (architecture: Architecture) => { registered.push(architecture); return { id: 'managed-generated', architecture }; },
      importSourceDraft: async () => { throw new Error('A generated view must resume the original draft, not import a new one'); },
      sourceDraftFrontier: async () => { throw new Error('A plain authored atom has no source frontier to rebase'); } },
    setFailure: (value: string) => failures.push(value), setBusy: () => {},
    setHistory: (history: ReturnType<typeof createHistory>) => { historyRef.current = history; },
    setSelection: (next: { kind: string; ids: string[] }) => { selection.kind = next.kind; selection.ids = next.ids; },
    setBrowseBaseline: (draft: AuthoredDraft | undefined) => { baselines.push(draft); },
    setAuthoringWorkspace: (current: AuthoringWorkspace) => { opened.push(current); }, setAuthoringOpen: () => {},
    setProjectId: () => {}, setExampleId: () => {}, setTool: () => {}, setNotice: () => {},
    commitCamera: (camera: typeof view.camera) => { cameraRef.current = { ...camera }; },
    initializeCamera: () => { throw new Error('The current editor camera must be retained'); },
  };
  const actual = callbacks('App.tsx', 'App', ['sourceDraftKey', 'cacheGeneratedWorkspace', 'retainAuthoringWorkspace', 'openBlankAuthoring', 'openGeneratedModel', 'continueModelAuthoring'], env);
  return { actual, authoringSessions, authoringSessionKey, generatedWorkspaces, historyRef, cameraRef, selection, opened, baselines, failures, registered, values };
}

test('actual new-blank entry always starts empty despite a cached source draft, and keeps previous workspaces intact', () => {
  const previous: AuthoringWorkspace = { draft: sourceDraft, history: draftHistory(sourceDraft), camera: view.camera, selection: ['linear'] };
  const h = generatedAppHarness(previous);
  h.values.set('archcanvas.authored-workspace.v1', JSON.stringify(previous));
  const previousBytes = JSON.stringify(previous);
  h.actual.openBlankAuthoring();
  const first = h.opened.at(-1)!, firstKey = h.authoringSessionKey.current;
  assert.ok(first && firstKey); assert.deepEqual(first.draft.nodes, []); assert.deepEqual(first.draft.edges, []);
  assert.equal(first.draft.sourceProvenance, undefined); assert.equal(first.savedRevision, -1);
  assert.equal(h.baselines.at(-1), undefined); assert.equal(h.authoringSessions.current.get(firstKey), first);
  h.actual.openBlankAuthoring();
  const second = h.opened.at(-1)!;
  assert.notEqual(second.draft.id, first.draft.id); assert.notEqual(h.authoringSessionKey.current, firstKey);
  assert.equal(h.authoringSessions.current.get(firstKey), first);
  assert.equal(JSON.stringify(h.authoringSessions.current.get('blank')), previousBytes);
  assert.equal(h.values.get('archcanvas.authored-workspace.v1'), previousBytes);
});

test('new-blank from the editor hands off the exact unsaved draft and history before creating a separate session', () => {
  const history = changeDraft(draftHistory(sourceDraft), draft => { draft.nodes[1].label = '未保存的修改'; });
  const snapshots: AuthoringWorkspace[] = [];
  const currentRef = { current: history };
  const env = { busy: false, portEditing: false, cancel: () => {}, onNewBlank: (workspace: AuthoringWorkspace) => snapshots.push(workspace), currentRef,
    storageRevision: 4, savedRevision: 0, selectedIds: ['linear'], camera: view.camera,
    cameraViewport: { current: view.viewport }, tool: 'pan', initial: { sourceHistory: view.sourceHistory, viewBaseline: sourceDraft } };
  callbacks('AuthoringStudio.tsx', 'AuthoringStudio', ['startBlankDraft'], env).startBlankDraft();
  assert.equal(snapshots.length, 1); assert.equal(snapshots[0].draft, history.draft); assert.equal(snapshots[0].history, history);
  assert.deepEqual(snapshots[0].selection, ['linear']); assert.deepEqual(snapshots[0].camera, view.camera);
  assert.equal(snapshots[0].viewBaseline, sourceDraft); assert.equal(currentRef.current, history);
});

test('actual App opens generated work, resumes the original semantic history on repeated returns, and recovers it after reload', async () => {
  let history = changeDraft(draftHistory(sourceDraft), draft => { draft.title = '保留的草稿'; });
  history = changeDraft(history, draft => { draft.nodes[1].label = 'future label'; }); history = travelDraft(history, 'undo');
  const workspace: AuthoringWorkspace = { draft: history.draft, history, storageRevision: 3, savedRevision: 0, selection: ['linear'], camera: view.camera, viewport: view.viewport, tool: 'pan' };
  const h = generatedAppHarness(workspace);
  await h.actual.openGeneratedModel({ ...generated, draft: history.draft, presentationDraft: history.draft });
  assert.ok(h.historyRef.current); const document = h.historyRef.current.document, binding = h.generatedWorkspaces.current.get(sourceAuthoringKey(document))!;
  assert.deepEqual(h.selection.ids, [binding.nodeBindings.linear]); assert.deepEqual(h.cameraRef.current, view.camera);
  const viewHistoryBytes = JSON.stringify(h.historyRef.current);
  await h.actual.continueModelAuthoring(); await h.actual.continueModelAuthoring();
  assert.equal(h.opened.length, 2); assert.equal(h.opened[0].draft.id, sourceDraft.id); assert.equal(h.opened[0].history, history);
  assert.equal(h.opened[1].history, history); assert.equal(h.opened[1].history!.future.length, 1); assert.equal(h.registered.length, 1);
  assert.equal(JSON.stringify(h.historyRef.current), viewHistoryBytes); assert.deepEqual(h.baselines.at(-1), history.draft);
  h.historyRef.current = { ...h.historyRef.current, document: applyVisualBatch(document, [{ type: 'move', ids: [binding.nodeBindings.linear], dx: 48, dy: -32, scope: 'current-frontier' }]) };
  await h.actual.continueModelAuthoring(); const moved = h.opened.at(-1)!;
  assert.equal(moved.history!.past.length, history.past.length + 1); assert.deepEqual(moved.selection, ['linear']);
  assert.deepEqual(moved.draft.nodes.find(node => node.id === 'linear')!.position, { x: sourceDraft.nodes[1].position.x + 48, y: sourceDraft.nodes[1].position.y - 32 });
  h.actual.retainAuthoringWorkspace(moved);
  const afterReload = generatedAppHarness({ ...workspace, draft: blankDraft('draft-unused') }, h.historyRef.current.document, h.values);
  afterReload.authoringSessions.current.clear(); afterReload.selection.ids = [binding.nodeBindings.linear];
  await afterReload.actual.continueModelAuthoring();
  assert.equal(afterReload.opened.length, 1); assert.equal(afterReload.opened[0].draft.id, sourceDraft.id);
  assert.deepEqual(afterReload.opened[0].history, moved.history); assert.deepEqual(afterReload.opened[0].camera, view.camera);
  assert.equal(afterReload.failures.filter(Boolean).length, 0); assert.equal(afterReload.registered.length, 0);
});

test('actual edit→view with an unchanged baseline reuses the current view and preserves both stacks and the camera', async () => {
  const h = browseHarness(structuredClone(sourceDraft), { baseline: sourceDraft });
  h.currentRef.current = changeDraft(h.currentRef.current, draft => { draft.title = 'temporary'; });
  h.currentRef.current = travelDraft(h.currentRef.current, 'undo');
  const bytes = JSON.stringify(h.currentRef.current);
  await h.browse();
  assert.equal(h.generatedInputs.length, 0); assert.equal(h.opened.length, 0); assert.equal(h.reused.length, 1);
  assert.equal(h.reused[0].history, h.currentRef.current); assert.equal(h.reused[0].history!.future.length, 1);
  assert.deepEqual(h.reused[0].camera, view.camera); assert.deepEqual(h.reused[0].selection, ['linear']); assert.equal(h.reused[0].tool, 'pan');
  assert.equal(JSON.stringify(h.currentRef.current), bytes);
});

test('actual edit→view generates the latest modified snapshot and retains its workspace before opening it', async () => {
  const changed = structuredClone(sourceDraft); changed.nodes[1].parameters.out_features = 7;
  const h = browseHarness(changed, { baseline: sourceDraft, open: async value => {
    assert.equal(h.retained.length, 1, 'retain current semantic history before opening the new view');
    assert.equal(value.presentationDraft, changed); assert.equal(h.retained[0].draft, changed);
  } });
  const bytes = JSON.stringify(changed); await h.browse();
  assert.deepEqual(h.generatedInputs, [changed]); assert.equal(h.opened.length, 1); assert.equal(h.reused.length, 0);
  assert.deepEqual(h.operations, ['generate', 'open', null]); assert.deepEqual(h.busyStates, [true, false]);
  assert.equal(JSON.stringify(changed), bytes); assert.equal(h.currentRef.current.past.length, 0);
});

test('real normalized generation response accepts a separate JSON-roundtripped authored presentation, but refuses stale values', async () => {
  const response = await backend('print(json.dumps(generate_model(v),sort_keys=True))', sourceDraft) as GeneratedDraft;
  const presentation = JSON.parse(JSON.stringify(sourceDraft)) as AuthoredDraft;
  assert.notEqual(presentation, response.draft);
  assert.ok(sameGeneratedDraft(presentation, response.draft));
  const retained = createGeneratedCanvas(response.architecture, response.draft, response, presentation);
  const scene = buildScene(retained.document);
  assert.equal(scene.nodes.find(node => node.id === retained.nodeBindings.linear)!.label, '我的投影');
  assert.deepEqual(scene.nodes.filter(node => retained.nodeBindings.linear === node.id).map(node => ({ x: node.x, y: node.y })), [{ x: -160, y: 40 }]);
  for (const alter of [(draft: AuthoredDraft) => { draft.nodes[1].parameters.out_features = 12; },
    (draft: AuthoredDraft) => { draft.edges[0].target.portId = 'other'; },
    (draft: AuthoredDraft) => { draft.id = 'different-draft'; }]) {
    const changed = structuredClone(presentation); alter(changed);
    assert.throws(() => createGeneratedCanvas(response.architecture, response.draft, response, changed), /来源不一致/);
  }
});

test('actual failed generation or opening preserves edited bytes/history and reports that the editor was retained', async () => {
  for (const failing of ['generate', 'open']) {
    const changed = structuredClone(sourceDraft); changed.title += ` ${failing}`;
    const fail = async () => { throw new Error(`controlled ${failing} failure`); };
    const h = browseHarness(changed, { baseline: sourceDraft, ...(failing === 'generate' ? { generate: fail } : { open: fail }) });
    const bytes = JSON.stringify(h.currentRef.current); await h.browse();
    assert.equal(h.reused.length, 0); assert.equal(JSON.stringify(h.currentRef.current), bytes);
    assert.match(h.errors.at(-1)!, /无法切换到视图，编辑已保留/); assert.match(h.errors.at(-1)!, new RegExp(failing));
    assert.equal(h.busyStates.at(-1), false); assert.equal(h.operations.at(-1), null); assert.equal(h.flight.current, false);
  }
});

test('actual stale async generation cannot open a newer draft, and synchronous repeated mode clicks generate once', async () => {
  let finish!: (value: GeneratedDraft) => void;
  const h = browseHarness(sourceDraft, { generate: () => new Promise(resolveResult => { finish = resolveResult; }) });
  const first = h.browse(), repeated = h.browse();
  assert.equal(h.generatedInputs.length, 1, 'busy render state alone cannot guard two synchronous mode clicks');
  h.currentRef.current = changeDraft(h.currentRef.current, draft => { draft.title = 'changed while pending'; });
  finish(generated); await Promise.all([first, repeated]);
  assert.equal(h.opened.length, 0); assert.equal(h.retained.length, 0); assert.equal(h.currentRef.current.draft.title, 'changed while pending');
  assert.equal(h.flight.current, false);
});

test('view baseline equivalence ignores only revision and detects connections, presentation and custom definitions', () => {
  const revised = structuredClone(sourceDraft); revised.revision += 9; assert.equal(sameGeneratedDraft(sourceDraft, revised), true);
  for (const mutate of [
    (draft: AuthoredDraft) => { draft.nodes[1].parameters.out_features = 8; },
    (draft: AuthoredDraft) => { draft.nodes[1].position.x -= 22; },
    (draft: AuthoredDraft) => { draft.edges[0].target.portId = 'other'; },
    (draft: AuthoredDraft) => { draft.customModules = [customPreview.definition]; },
  ]) { const changed = structuredClone(sourceDraft); mutate(changed); assert.equal(sameGeneratedDraft(sourceDraft, changed), false); }
});

test('generated workspace resumes exact draft/history, maps selection and reflects subsequent view movement without source mutation', () => {
  const result = createGeneratedCanvas(generated.architecture, sourceDraft, generated), document = result.document;
  const history = changeDraft(draftHistory(sourceDraft), draft => { draft.title = 'earlier title'; });
  const workspace = { draft: history.draft, history, camera: view.camera, selection: ['linear'], storageRevision: 4, savedRevision: 1 };
  const binding: GeneratedWorkspaceBinding = { workspaceKey: 'blank', documentId: document.id, sourceDigest: document.sourceBindingDigest,
    irDigest: document.architecture.irDigest, draft: history.draft, nodeBindings: result.nodeBindings, visualRevision: document.revision };
  const bytes = JSON.stringify({ document, workspace, binding });
  const canonical = result.nodeBindings.linear;
  const same = resumeGeneratedWorkspace(workspace, document, binding, { ...view, selection: [canonical] });
  assert.equal(same.history, history); assert.deepEqual(same.selection, ['linear']); assert.deepEqual(same.camera, view.camera);
  const moved = applyVisualBatch(document, [{ type: 'move', ids: [canonical], dx: -24, dy: 32, scope: 'current-frontier' }, { type: 'alias', id: canonical, label: '视图中的名称' }]);
  const resumed = resumeGeneratedWorkspace(workspace, moved, binding, { ...view, selection: [canonical] });
  assert.equal(resumed.history!.past.length, history.past.length + 1); assert.equal(resumed.history!.future.length, 0);
  assert.deepEqual(resumed.draft.nodes.find(node => node.id === 'linear')!.position, { x: sourceDraft.nodes[1].position.x - 24, y: sourceDraft.nodes[1].position.y + 32 });
  assert.equal(resumed.draft.nodes.find(node => node.id === 'linear')!.label, '视图中的名称');
  assert.equal(travelDraft(resumed.history!, 'undo').draft.nodes.find(node => node.id === 'linear')!.label, '我的投影');
  assert.equal(JSON.stringify({ document, workspace, binding }), bytes); assert.deepEqual(moved.architecture, document.architecture);
});

test('generated workspace rejects a changed document/source/IR binding before modifying retained authoring history', () => {
  const result = createGeneratedCanvas(generated.architecture, sourceDraft, generated), document = result.document;
  const workspace = { draft: sourceDraft, history: draftHistory(sourceDraft) }, bytes = JSON.stringify(workspace);
  const binding: GeneratedWorkspaceBinding = { workspaceKey: 'blank', documentId: document.id, sourceDigest: document.sourceBindingDigest,
    irDigest: document.architecture.irDigest, draft: sourceDraft, nodeBindings: result.nodeBindings, visualRevision: document.revision };
  for (const mutate of [(doc: CanvasDocument) => { doc.id += '-other'; }, (doc: CanvasDocument) => { doc.sourceBindingDigest = 'other'; },
    (doc: CanvasDocument) => { doc.architecture.irDigest = 'other'; }]) {
    const changed = structuredClone(document); mutate(changed);
    assert.throws(() => resumeGeneratedWorkspace(workspace, changed, binding, view), /绑定已变化/); assert.equal(JSON.stringify(workspace), bytes);
  }
});

test('blank-authored visual styles persist through view→edit, browser recovery and a fresh static generation', async () => {
  const result = createGeneratedCanvas(generated.architecture, sourceDraft, generated), document = result.document, canonical = result.nodeBindings.linear;
  assert.equal(sourceDraft.nodes[1].presentation, undefined, 'this is an authored atom, not a source-projection card');
  const styled = applyVisualBatch(document, [{ type: 'nodeStyle', id: canonical, style: { fill: '#163f6b', stroke: '#f0c864' } }]);
  const history = draftHistory(sourceDraft), workspace: AuthoringWorkspace = { draft: history.draft, history, storageRevision: 0, savedRevision: -1 };
  const binding: GeneratedWorkspaceBinding = { workspaceKey: 'blank', documentId: document.id, sourceDigest: document.sourceBindingDigest,
    irDigest: document.architecture.irDigest, draft: sourceDraft, nodeBindings: result.nodeBindings, visualRevision: document.revision };
  const resumed = resumeGeneratedWorkspace(workspace, styled, binding, view), node = resumed.draft.nodes.find(item => item.id === 'linear')!;
  assert.equal(node.visual?.fill, '#163f6b'); assert.equal(node.visual?.stroke, '#f0c864'); assert.equal(node.presentation, undefined);
  const recovered = parseAuthoringWorkspace(JSON.parse(JSON.stringify(resumed)))!; assert.ok(recovered);
  assert.deepEqual(recovered.draft.nodes.find(item => item.id === 'linear')!.visual, node.visual);
  const fresh = await backend('print(json.dumps(generate_model(v)))', recovered.draft) as GeneratedDraft;
  const current = createGeneratedCanvas(fresh.architecture, recovered.draft, fresh), scene = buildScene(current.document);
  const visible = scene.nodes.find(item => item.id === current.nodeBindings.linear)!;
  assert.equal(visible.fill, '#163f6b'); assert.equal(visible.stroke, '#f0c864');
  assert.deepEqual({ width: visible.width, height: visible.height }, { width: node.visual!.width, height: node.visual!.height });
  assert.deepEqual(fresh.draft.nodes.find(item => item.id === 'linear')!.visual, node.visual);
  assert.equal(travelDraft(recovered.history!, 'undo').draft.nodes.find(item => item.id === 'linear')!.visual, undefined);
});

test('generated view cache roundtrips both authoring history stacks and accepts only this exact saved model binding', () => {
  const result = createGeneratedCanvas(generated.architecture, sourceDraft, generated), document = result.document;
  let history = changeDraft(draftHistory(sourceDraft), draft => { draft.title = 'saved editor'; });
  history = changeDraft(history, draft => { draft.nodes[1].label = 'future'; }); history = travelDraft(history, 'undo');
  const workspace: AuthoringWorkspace = { draft: history.draft, history, storageRevision: 4, savedRevision: 0, selection: ['linear'],
    camera: view.camera, viewport: view.viewport, tool: 'pan', viewBaseline: history.draft };
  const binding: GeneratedWorkspaceBinding = { workspaceKey: 'blank', documentId: document.id, sourceDigest: document.sourceBindingDigest,
    irDigest: document.architecture.irDigest, draft: history.draft, nodeBindings: result.nodeBindings, visualRevision: document.revision };
  const values = new Map<string, string>(), storage = { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => { values.set(key, value); } };
  writeGeneratedWorkspace(storage, workspace, binding);
  const recovered = readGeneratedWorkspace(storage, document)!; assert.ok(recovered);
  assert.deepEqual(recovered.binding, binding); assert.deepEqual(recovered.workspace.history, history); assert.deepEqual(recovered.workspace.camera, view.camera);
  assert.equal(recovered.workspace.history!.future.length, 1); assert.deepEqual(authoringViewSelection(recovered.workspace, binding), [result.nodeBindings.linear]);
  const key = [...values.keys()][0], pristine = values.get(key)!;
  for (const mutate of [
    (raw: any) => { raw.binding.sourceDigest = 'changed'; },
    (raw: any) => { raw.binding.nodeBindings.linear = 'missing'; },
    (raw: any) => { raw.binding.nodeBindings.output = raw.binding.nodeBindings.linear; },
    (raw: any) => { raw.workspace.history.past[0].id = 'draft-other'; },
    (raw: any) => { raw.workspace.camera.zoom = 0; },
  ]) {
    const raw = JSON.parse(pristine); mutate(raw); values.set(key, JSON.stringify(raw));
    assert.equal(readGeneratedWorkspace(storage, document), null, 'damaged cache is not reattached to a view');
  }
  values.set(key, pristine); const changed = structuredClone(document); changed.architecture.irDigest = 'other';
  assert.equal(readGeneratedWorkspace(storage, changed), null); assert.deepEqual(history.draft, workspace.draft);
});

test('generated source view translates changed generated geometry back to the original source frontier before edit resumes', async () => {
  const source = 'from torch import nn\nclass Pair(nn.Module):\n def __init__(self):\n  super().__init__();self.fc=nn.Linear(4,4);self.act=nn.GELU()\n def forward(self,x): return self.act(self.fc(x))\n';
  const architecture = await backend('print(json.dumps(analyze_source(v,"model:Pair")))', source) as Architecture;
  const sourceDocument = createDocument(architecture), imported = await backend('print(json.dumps(import_source_draft(v[0],v[1])))', [sourceDocument, buildScene(sourceDocument)]) as { draft: AuthoredDraft; sceneNodeBindings: Record<string, string> };
  const generatedResult = await backend('print(json.dumps(generate_model(v)))', imported.draft) as GeneratedDraft;
  const generatedCanvas = createGeneratedCanvas(generatedResult.architecture, imported.draft, generatedResult, generatedResult.presentationDraft),
    generatedDocument = generatedCanvas.document, draftNode = imported.draft.nodes.find(node => imported.draft.sourceProvenance!.nodeRefs[node.id]?.kind === 'Linear')!;
  const canonical = generatedCanvas.nodeBindings[draftNode.id];
  const moved = applyVisualBatch(generatedDocument, [{ type: 'move', ids: [canonical], dx: 37, dy: -19, scope: 'current-frontier' }, { type: 'alias', id: canonical, label: 'view alias' }]);
  const binding: GeneratedWorkspaceBinding = { workspaceKey: 'source', documentId: generatedDocument.id, sourceDigest: generatedDocument.sourceBindingDigest,
    irDigest: generatedDocument.architecture.irDigest, draft: imported.draft, nodeBindings: generatedCanvas.nodeBindings, visualRevision: generatedDocument.revision };
  const workspace: AuthoringWorkspace = { draft: imported.draft, history: draftHistory(imported.draft), viewBaseline: structuredClone(imported.draft) };
  const translated = generatedWorkspaceHelpers.generatedSourceView(workspace, moved, binding);
  assert.ok(translated); assert.equal(translated!.sourceBindingDigest, sourceDocument.sourceBindingDigest); assert.equal(translated!.architecture.irDigest, sourceDocument.architecture.irDigest);
  const sourceId = imported.draft.sourceProvenance!.nodeRefs[draftNode.id].nodeId, generatedNode = buildScene(moved).nodes.find(node => node.id === canonical)!;
  const generatedParent = generatedNode.parentId ? buildScene(moved).nodes.find(node => node.id === generatedNode.parentId) : undefined;
  assert.equal(translated!.displayAliases[sourceId], 'view alias'); assert.equal(translated!.layout[sourceId].x, generatedNode.x - (generatedParent?.x ?? 0)); assert.equal(translated!.layout[sourceId].y, generatedNode.y - (generatedParent?.y ?? 0));
  for (const [draftId, ref] of Object.entries(imported.draft.sourceProvenance!.nodeRefs)) {
    const target = binding.nodeBindings[draftId]; if (!target) continue;
    assert.equal(translated!.expandedIds.includes(ref.nodeId), moved.expandedIds.includes(target), `expanded frontier maps ${draftId}`);
  }
  assert.notEqual(translated!.id, moved.id); assert.deepEqual(workspace.draft, imported.draft);
});

test('real custom-module preview retains named keyword input and three distinct nested output boundaries in the frontend reader', () => {
  const definition = readCustomModuleDefinition(customPreview.definition), module = customModuleCatalog(definition);
  assert.deepEqual(module.ports.map(port => [port.id, port.name, port.direction]), customPreview.module.ports.map(port => [port.id, port.name, port.direction]));
  assert.deepEqual(definition.inputs.map(port => port.id), ['features', 'memory']);
  assert.deepEqual(definition.outputs.map(port => port.path), [[{ kind: 'key', key: 'pair' }, { kind: 'index', index: 0 }],
    [{ kind: 'key', key: 'pair' }, { kind: 'index', index: 1 }], [{ kind: 'key', key: 'sum' }]]);
  assert.equal(customPreview.verification.modelExecution, 'not_run'); assert.equal(customPreview.verification.shapeInference, 'unknown');
  definition.inputs[0].id = 'mutated'; assert.equal(customPreview.definition.inputs[0].id, 'features', 'reader returns independent definition bytes');
});

test('malformed custom source/class/constructor/port/output contracts cannot enter restored draft state', () => {
  const valid = structuredClone(sourceDraft); valid.customModules = [customPreview.definition];
  assert.ok(parseAuthoringWorkspace({ draft: valid, storageRevision: 0, savedRevision: -1 }), 'valid full contract restores before malformed variants are tested');
  const corruptions: Array<(definition: CustomModuleDefinition) => void> = [
    definition => { definition.source = ''; }, definition => { definition.entry = 'not.a.class'; },
    definition => { definition.constructorValues = [] as unknown as Record<string, unknown>; },
    definition => { definition.inputs[0].positionalOnly = 'false' as unknown as boolean; },
    definition => { definition.outputs[0].id = definition.inputs[0].id; },
    definition => { definition.outputs[0].path = [{ kind: 'index', index: -1 }]; },
    definition => { definition.outputs = []; }, definition => { definition.digest = 'unbound'; },
  ];
  for (const mutate of corruptions) {
    const invalid = structuredClone(customPreview.definition); mutate(invalid); assert.throws(() => readCustomModuleDefinition(invalid), /自定义模块/);
    const draft = structuredClone(sourceDraft); draft.customModules = [invalid]; assert.equal(parseAuthoringWorkspace({ draft, storageRevision: 0, savedRevision: -1 }), null);
  }
});

test('actual custom-module insertion registers once, supports repeated instances and persists definitions plus undo', () => {
  const currentRef = { current: draftHistory(sourceDraft) }, selected: string[] = [], notices: string[] = [];
  const env = { busy: false, portEditing: false, catalog, currentRef, svgRef: { current: null }, draftModuleSize, nextDraftPosition, addDraftNode,
    crypto, point: (x: number, y: number) => ({ x, y }),
    apply: (update: Parameters<typeof changeDraft>[1]) => { currentRef.current = changeDraft(currentRef.current, update); return currentRef.current.draft; },
    setSelection: (value: { node: string }) => { selected.push(value.node); }, setPaletteView: () => {}, setPaletteCategory: () => {}, setSearch: () => {}, setCustomModuleOpen: () => {},
    setNotice: (value: string) => { notices.push(value); },
  };
  const h = callbacks('AuthoringStudio.tsx', 'AuthoringStudio', ['insertCustomModule'], env);
  h.insertCustomModule(customPreview); h.insertCustomModule(customPreview);
  assert.equal(currentRef.current.draft.customModules!.length, 1); assert.equal(currentRef.current.past.length, 2);
  assert.equal(new Set(selected).size, 2); assert.equal(currentRef.current.draft.nodes.filter(node => node.kind === customPreview.definition.kind).length, 2);
  assert.match(notices.at(-1)!, /输出形状未推测/);
  const restored = parseAuthoringWorkspace(JSON.parse(JSON.stringify({ draft: currentRef.current.draft, history: currentRef.current, storageRevision: 0, savedRevision: -1, camera: view.camera, tool: 'pan' })))!;
  assert.ok(restored); assert.deepEqual(restored.draft.customModules, [customPreview.definition]);
  assert.equal(travelDraft(restored.history!, 'undo').draft.nodes.filter(node => node.kind === customPreview.definition.kind).length, 1);
});

test('actual custom preview callback rejects malformed JSON, preserves a bounded static result, and prevents parallel requests', async () => {
  let finish!: (value: CustomModulePreview) => void, calls = 0, preview: CustomModulePreview | null = null;
  const errors: string[] = [], flight = { current: false };
  const env = { inFlight: flight, source: customSource, entry: 'Fusion', label: '我的融合', constructorText: '{"width":4}',
    setBusy: () => {}, setError: (value: string) => errors.push(value), setPreview: (value: CustomModulePreview | null) => { preview = value; }, readCustomModuleDefinition,
    api: { previewCustomModule: async () => { calls++; return new Promise<CustomModulePreview>(resolveResult => { finish = resolveResult; }); } } };
  const h = callbacks('CustomModuleDialog.tsx', 'CustomModuleDialog', ['inspect'], env);
  const first = h.inspect(), repeated = h.inspect(); assert.equal(calls, 1); finish(customPreview); await Promise.all([first, repeated]);
  assert.equal(preview, customPreview); assert.equal(flight.current, false); assert.equal(errors.at(-1), '');
  const bad = callbacks('CustomModuleDialog.tsx', 'CustomModuleDialog', ['inspect'], { ...env, constructorText: '[4]' });
  await bad.inspect(); assert.equal(calls, 1); assert.equal(preview, null); assert.match(errors.at(-1)!, /JSON 对象/);
});

/** Compile real TSX dependencies; plain TS helpers still run from the formal project. */
function compileComponent(file: string, input?: string, suffix = ''): string {
  const path = resolve(`${studio}src`, file), target = `${temporary}/${file.replaceAll('/', '-').replace(/\.tsx$/, '')}${suffix}.mjs`;
  if (existsSync(target)) return target;
  const output = ts.transpileModule(input ?? readFileSync(path, 'utf8'), { fileName: path,
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
  writeFileSync(target, ''); // Bound recursive imports to one temporary module per dependency.
  const resolved = output.replace(/import ['"][^'"]+\.css['"];?/g, '')
    .replace(/(['"])(\.[^'"]+)\1/g, (_match, _quote, specifier: string) => {
      const base = resolve(dirname(path), specifier), tsx = `${base}.tsx`, tsFile = `${base}.ts`;
      const dependency = existsSync(tsx) ? compileComponent(tsx.slice(`${studio}src/`.length)) : existsSync(tsFile) ? tsFile : existsSync(base) && statSync(base).isFile() ? base : `${base}/index.ts`;
      return `'${pathToFileURL(dependency).href}'`;
    });
  writeFileSync(target, resolved); return target;
}
function authoringInput() {
  const input = readFileSync(`${studio}src/AuthoringStudio.tsx`, 'utf8');
  const configured = input.replace('useState<DraftCatalog | null>(null)', `useState<DraftCatalog | null>(${JSON.stringify(catalog)})`);
  assert.notEqual(input, configured, 'SSR must use the actual active runtime catalog'); return configured;
}

test('actual editor top actions expose edit/view mode and custom-source launcher, with floating legend outside world SVG', async () => {
  const { AuthoringStudio } = await import(pathToFileURL(compileComponent('AuthoringStudio.tsx', authoringInput(), '-loaded')).href);
  const html = renderToStaticMarkup(createElement(AuthoringStudio, { initialWorkspace: { draft: sourceDraft }, onClose: () => {}, onOpen: async () => {} }));
  const header = html.slice(0, html.indexOf('</header>'));
  assert.match(header, /aria-label="工作区模式"/); assert.match(header, /aria-pressed="false"[^>]*>视图/); assert.match(header, /aria-pressed="true"[^>]*>编辑/);
  assert.match(html, /源码自定义模块/); assert.match(html, /class="workspace-caption"><b>独立连续工作流/);
  const legend = html.indexOf('aria-label="悬浮图例"'), canvas = html.indexOf('aria-label="模型搭建画布"');
  assert.ok(legend > 0); assert.ok(canvas > 0); assert.ok(html.lastIndexOf('</svg>', legend) > canvas, 'legend is a viewport sibling after the complete transformed canvas');
  assert.match(html.slice(legend), /aria-label="收起悬浮图例"/); assert.match(html.slice(legend), /数据流/);
});

test('actual source-view top actions expose the same mode switch and keep root/title/legend out of the editor world', async () => {
  const document = createGeneratedCanvas(generated.architecture, sourceDraft, generated).document;
  const input = readFileSync(`${studio}src/App.tsx`, 'utf8');
  const configured = input.replace('useState<HistoryState | null>(null)', `useState<HistoryState | null>(${JSON.stringify(createHistory(document))})`);
  assert.notEqual(input, configured);
  const { default: App } = await import(pathToFileURL(compileComponent('App.tsx', configured, '-loaded')).href);
  const html = renderToStaticMarkup(createElement(App));
  const header = html.slice(0, html.indexOf('</header>'));
  assert.match(header, /aria-pressed="true"[^>]*>视图/); assert.match(header, /aria-pressed="false"[^>]*>编辑/);
  assert.match(html, /class="workspace-caption"/); assert.match(html, /aria-label="悬浮图例"/);
  const scene = html.slice(html.indexOf('class="paper infinite-scene"'), html.indexOf('aria-label="悬浮图例"'));
  assert.doesNotMatch(scene, /class="legend"|data-scene-node="module:model.AuthoredModel"/);
});

test('actual custom-source modal renders class/source/constructor fields and named multi-output preview without a shape claim', async () => {
  const input = readFileSync(`${studio}src/CustomModuleDialog.tsx`, 'utf8');
  const configured = input.replace('useState<CustomModulePreview | null>(null)', `useState<CustomModulePreview | null>(${JSON.stringify(customPreview)})`);
  assert.notEqual(input, configured);
  const { CustomModuleDialog } = await import(pathToFileURL(compileComponent('CustomModuleDialog.tsx', configured, '-preview')).href);
  const html = renderToStaticMarkup(createElement(CustomModuleDialog, { onClose: () => {}, onInsert: () => {} }));
  assert.match(html, /role="dialog" aria-modal="true"/);
  for (const label of ['自定义模块类名', '自定义模块显示名称', '自定义模块 Python 源码', '自定义模块构造参数']) assert.ok(html.includes(`aria-label="${label}"`));
  for (const port of customPreview.module.ports) assert.ok(html.includes(`${port.direction === 'in' ? '输入' : '输出'} ${port.name.replaceAll("'", '&#x27;')}`));
  assert.match(html, /未执行模型；输出形状保留为未知/); assert.match(html, /静态结构 · /);
  assert.match(html, /<button class="primary">添加到模型/);
});
