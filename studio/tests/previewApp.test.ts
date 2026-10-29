import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { previewPanelDocument, projectPreviewHistory } from '../src/previewPanelDocument.ts';
import { previewUniqueNodeBindings } from '../src/previewInterop.ts';

function callback(name: string, environment: Record<string, unknown>) {
  const source = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8');
  const ast = ts.createSourceFile('App.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const app = ast.statements.find(item => ts.isFunctionDeclaration(item) && item.name?.text === 'App');
  assert.ok(app && ts.isFunctionDeclaration(app) && app.body);
  const declaration = app.body.statements.find(item => ts.isFunctionDeclaration(item) ? item.name?.text === name :
    ts.isVariableStatement(item) && item.declarationList.declarations.some(d => ts.isIdentifier(d.name) && d.name.text === name));
  assert.ok(declaration, `actual App callback ${name}`);
  const code = ts.transpileModule(declaration.getText(ast), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  return new Function(...Object.keys(environment), `${code}; return ${name};`)(...Object.values(environment)) as () => Promise<void>;
}

test('all Summary document formats enter the native bridge instead of the formal architecture parser', async () => {
  const loaded: unknown[] = [];
  const importJson = callback('importCanvasJson', {
    previewEngine: { current: { load: async (value: unknown) => loaded.push(value) } },
    openArchitecture() { throw Error('Summary document must use its own reader'); },
    validateArchitecture() { throw Error('not a formal architecture'); }, setExampleId() {}, setImportOpen() {},
  }) as unknown as (text: string) => Promise<void>;
  for (const schema of ['archcanvas-native-semantic/1', 'semantic-canvas/1', 'archcanvas-architecture-document/1', 'semantic-authoring/1', 'archcanvas-source-semantic/2']) await importJson(JSON.stringify({ schema }));
  assert.equal(loaded.length, 5);
});

test('imported Summary evidence opens Studio panels without requesting or binding Python source', async () => {
  const historyRef = { current: null as any }, previewSource = { current: { old: true } as any }, notices: string[] = [];
  const env = {
    previewSnapshot: { current: null }, synchronizePreviewNodeSelection() {}, setPreviewTool() {}, setPortEditing() {}, setGrid() {}, setPreviewBusy() {}, setPreviewCanCancel() {},
    setPreviewDirty() {}, setPreviewUndo() {}, setPreviewRedo() {}, setPreviewVersion() {}, setSelection() {}, savedPreviewGraph: { current: null },
    initialModelLoading: { current: false }, previewLoading: { current: false }, previewCase: { current: 'old' }, previewSource,
    previewSequence: { current: 0 }, loadSequence: { current: 0 }, previewBoundSource: { current: 'old' },
    historyRef, previewPanelDocument: () => ({ sourceBindingDigest: 'preview-only:doc' }), createHistory: (document: any) => ({ document }),
    setHistory() {}, setBusy() {}, setPreviewConnecting() {}, setExampleId() {}, setProjectId() {}, setNotice: (text: string) => notices.push(text),
    previewEngine: { current: { source() { throw Error('must not request source for imported IR'); } } },
  };
  await (callback('receivePreviewState', env) as unknown as (snapshot: any) => Promise<void>)({ caseId: 'doc', importedDocument: { sourceVerified: false }, graph: { caseId: 'doc' } });
  assert.equal(previewSource.current, undefined);
  assert.equal(historyRef.current.document.sourceBindingDigest, 'preview-only:doc');
  assert.match(notices[0], /文档证据未绑定 Python/);
});

test('a saved imported preview restores only the matching preview-only identity and never promotes source evidence', async () => {
  const snapshot = { caseId: 'doc', importedDocument: {}, graph: {} }, previewSource = { current: {} as any };
  const env = { previewEngine: { current: { snapshot: async () => snapshot, source() { throw Error('unverified document has no Python source'); } } },
    loadSequence: { current: 3 }, previewSource, previewCase: { current: '' }, previewSnapshot: { current: null }, previewBoundSource: { current: 'old' },
    matchesPreviewSave: async () => true, localStorage: {}, savedPreviewGraph: { current: null }, setPreviewConnecting() {},
  };
  const restore = callback('restoreMatchingPreview', env) as unknown as (document: any, id: string, sequence: number) => Promise<any>;
  assert.equal(await restore({ sourceBindingDigest: 'preview-only:doc' }, 'doc', 3), snapshot);
  assert.equal(previewSource.current, undefined);
  assert.equal(await restore({ sourceBindingDigest: 'source-bound' }, 'doc', 3), null);
  assert.equal(await restore({ sourceBindingDigest: 'preview-only:other' }, 'doc', 3), null);
});

function importHarness(formalSupported = true) {
  const calls: string[] = [], notices: string[] = [], failures: string[] = [];
  const snapshot = { caseId: 'new-case', graph: { nodes: [{ id: 'input' }], edges: [] } };
  const historyRef = { current: null as any }, loadSequence = { current: 0 }, previewLoading = { current: false };
  const environment = {
    busy: false, previewConnecting: false, previewBusy: false,
    cancelGesture() {}, loadSequence, previewSequence: { current: 0 }, previewLoading, filename: 'new.py', sourceText: 'model bytes', entry: 'new:Model',
    previewSource: { current: undefined }, previewCase: { current: '' }, previewSnapshot: { current: null }, previewBoundSource: { current: '' }, historyRef,
    api: { previewAnalyze: async () => { calls.push('preview-parse'); return { id: 'new-case' }; },
      previewEditSource: async () => { calls.push('editor-parse'); if (!formalSupported) throw new Error('unsupported editor syntax'); return { sourceDigest: 'source', irDigest: 'ir' }; } },
    previewEngine: { current: { load: async () => { calls.push('preview-load'); }, snapshot: async () => snapshot } },
    openArchitecture: async () => { calls.push('open-formal'); },
    previewPanelDocument: () => ({ sourceBindingDigest: 'preview-only:new-case' }), createHistory: (document: unknown) => ({ document }),
    previewNeedsPanelDocument: () => false,
    receivePreviewState: async () => { calls.push('sync'); }, setHistory() {}, setProjectId() {}, setStorageRevision() {}, setSavedVisualRevision() {},
    setBusy() {}, setPreviewConnecting() {}, setFailure: (value: string) => failures.push(value), setNotice: (value: string) => notices.push(value), setExampleId() {}, setImportOpen() {},
  };
  return { environment, calls, notices, failures, historyRef, loadSequence, previewLoading };
}

test('actual single-file import opens recursive preview before the editor contract and retains unsupported preview source', async () => {
  for (const supported of [true, false]) {
    const h = importHarness(supported); await callback('importSource', h.environment)();
    assert.deepEqual(h.calls.slice(0, 3), ['preview-parse', 'preview-load', 'editor-parse']);
    assert.equal(h.calls.includes('open-formal'), supported); assert.equal(h.calls.at(-1), 'sync');
    assert.equal(h.previewLoading.current, false); assert.equal(h.failures.at(-1), '');
    if (!supported) { assert.match(h.historyRef.current.document.sourceBindingDigest, /^preview-only:/); assert.match(h.notices.at(-1)!, /编辑契约/); }
  }
});

test('actual slow source import cannot load its preview after a different model takes ownership', async () => {
  const h = importHarness(); let finish!: (value: { id: string }) => void;
  h.environment.api.previewAnalyze = () => new Promise(resolve => { finish = resolve; });
  const pending = callback('importSource', h.environment)();
  h.loadSequence.current++; finish({ id: 'old-case' }); await pending;
  assert.deepEqual(h.calls, []); assert.equal(h.historyRef.current, null);
});

test('source import while the current graph is loading or busy preserves its generation and source', async () => {
  for (const state of ['busy', 'previewConnecting', 'previewBusy']) {
    const h = importHarness(); Object.assign(h.environment, { [state]: true });
    await callback('importSource', h.environment)();
    assert.deepEqual(h.calls, []); assert.equal(h.loadSequence.current, 0);
    assert.equal(h.historyRef.current, null); assert.equal(h.previewLoading.current, false);
    assert.match(h.failures.at(-1)!, /等待当前模型载入或图操作完成/);
  }
});

test('actual edit entry awaits the latest preview snapshot and never opens an editor after a stale model response', async () => {
  const calls: string[] = [], sequence = { current: 4 };
  let finish!: (value: object) => void;
  const env = { enteringAuthoring: { current: false }, busy: false, activeRecovery: null, historyRef: { current: {} }, loadSequence: sequence,
    previewSnapshot: {current:null},setBusy() {},setNotice() {},
    previewEngine: { current: { snapshot: () => new Promise(resolve => { finish = resolve; }) } },
    receivePreviewState: async () => { calls.push('sync'); }, continueModelAuthoring: async () => { calls.push('edit'); }, readyPreview: () => true, setFailure() {} };
  const edit = callback('editCurrentPreview', env), pending = edit(); await edit();
  finish({ graph: {} }); await pending; assert.deepEqual(calls, ['sync', 'edit']);
  const stale = edit(); sequence.current++; finish({ graph: {} }); await stale;
  assert.deepEqual(calls, ['sync', 'edit']); assert.equal(env.enteringAuthoring.current, false);
});

test('actual save freezes the synchronized preview revision and records a stable saved-graph baseline', async () => {
  const historyRef = { current: { document: { id: 'doc', revision: 2, sourceBindingDigest: 'source' } } };
  const snapshot = { graph: { nodes: [{ id: 'moved', x: 128 }] } }, savedPreviewGraph = { current: null as string | null };
  const sent: any[] = [], revisions: number[] = [];
  const env = { rememberPreviewSave: async () => {}, localStorage: {}, activeRecovery: null, historyRef, saving: { current: false }, loadSequence: { current: 1 }, storageRevision: 3, savedPreviewGraph,
    useCallback: (value: unknown) => value,
    previewEngine: { current: { save: async () => {}, snapshot: async () => snapshot } },
    receivePreviewState: async () => { historyRef.current = { document: { ...historyRef.current.document, revision: 9 } }; },
    readyPreview: () => true,
    api: { save: async (...args: unknown[]) => { sent.push(args); return { revision: 4 }; } },
    updateDocumentUrl: (id: string) => { assert.equal(id, 'doc'); },
    setBusy() {}, setNotice() {}, setFailure() {}, setStorageRevision() {}, setPreviewDirty() {}, setSavedVisualRevision: (value: number) => revisions.push(value) };
  await callback('save', env)();
  assert.equal(sent[0][0].revision, 9); assert.equal(sent[0][2].document.revision, 9);
  assert.equal(sent[0][1], 3); assert.deepEqual(revisions, [9]); assert.equal(savedPreviewGraph.current, JSON.stringify(snapshot.graph));
});

test('successful preview-only save clears prior rejected-import feedback without calling formal source persistence', async () => {
  const calls: string[] = [], failures: string[] = [], notices: string[] = [], snapshot = { graph: { caseId: 'doc' } };
  const env = {
    useCallback: (fn: unknown) => fn, storageRevision: 0, activeRecovery: null, saving: { current: false }, readyPreview: () => true,
    historyRef: { current: { document: { sourceBindingDigest: 'preview-only:doc', revision: 4 } } }, savedPreviewGraph: { current: '' },
    previewEngine: { current: { save: async () => calls.push('child-save'), snapshot: async () => snapshot } },
    receivePreviewState: async () => calls.push('snapshot'), rememberPreviewSave: async () => calls.push('marker'), localStorage: {},
    setPreviewDirty() {}, setSavedVisualRevision() {}, setNotice: (value: string) => notices.push(value), setFailure: (value: string) => failures.push(value),
    api: { save() { throw Error('a preview-only graph is not a formal source document'); } },
  };
  await callback('save', env)();
  assert.deepEqual(calls, ['child-save', 'snapshot', 'marker']);
  assert.deepEqual(failures, ['']); assert.match(notices[0], /已保存到浏览器/);
});

test('actual hierarchy focus keeps unmatched catalog aggregates explicit and sends only a mapped node ID', () => {
  const calls: unknown[] = [], notices: string[] = [];
  const focus = callback('focusPreviewNode', {
    previewNodeId: (id: string) => id === 'matched' ? 'preview-node' : undefined,
    previewEngine: { current: { focus: (message: unknown) => calls.push(message) } },
    setNotice: (message: string) => notices.push(message),
  }) as unknown as (id: string) => void;
  focus('encoder'); assert.deepEqual(calls, []); assert.match(notices[0], /没有直接对应图元/);
  focus('matched'); assert.deepEqual(calls, [{ nodeId: 'preview-node' }]);
});

test('actual catalog binding keeps every reviewed display object editable and opens formal source only for model authoring', async () => {
  for (const openEditor of [false, true]) {
    const calls: string[] = [], historyRef = { current: null as any };
    const source = { schema: 'archcanvas-preview-source/1', caseId: 'catalog', files: { 'model.py': 'original bytes' }, entry: 'model:Model' };
    const env = { sourceFromResult: () => source, previewSource: { current: undefined },
      rawPreviewSourceRequest: () => ({ files: source.files, entry: source.entry }), bundlePreviewRequest() {},
      previewSequence: { current: 0 }, previewCase: { current: 'catalog' }, previewSnapshot: { current: { caseId: 'catalog', graph: {} } },
      previewBoundSource: { current: '' }, historyRef,
      api: { previewEditSource: async () => { calls.push('formal-parse'); return { sourceDigest: 'source', irDigest: 'ir' }; } },
      previewNeedsPanelDocument: () => true, previewPanelDocument: () => ({ sourceBindingDigest: 'preview-only:catalog' }),
      createHistory: (document: unknown) => ({ document }), setHistory() {}, setProjectId() {}, setStorageRevision() {}, setSavedVisualRevision() {},
      setPreviewConnecting() {}, setExampleId() {}, setNotice() {},
      openArchitecture: async () => { calls.push('formal-open'); historyRef.current = { document: {} }; }, receivePreviewState: async () => { calls.push('visual-sync'); },
      continueModelAuthoring: async () => { calls.push('model-edit'); },
    };
    const bind = callback('bindPreviewSource', env) as unknown as (result: unknown, edit: boolean) => Promise<void>;
    await bind({}, openEditor);
    assert.deepEqual(calls, openEditor ? ['formal-parse', 'formal-open', 'visual-sync', 'model-edit'] : ['formal-parse', 'visual-sync']);
    if (!openEditor) assert.equal(historyRef.current.document.sourceBindingDigest, 'preview-only:catalog');
  }
});

test('actual unsupported catalog source retains read-only text and a safe display projection without an old mapping error', async () => {
  const notices: string[] = [], historyRef = { current: null as any }, source = { schema: 'archcanvas-preview-source/1' };
  const env = { sourceFromResult: () => source, previewSource: { current: undefined },
    rawPreviewSourceRequest: () => { throw new Error('unsupported entry'); }, bundlePreviewRequest() {},
    previewSequence: { current: 0 }, previewCase: { current: 'catalog' }, previewSnapshot: { current: { graph: {} } }, previewBoundSource: { current: '' }, historyRef,
    previewPanelDocument: (_snapshot: unknown, actual: unknown) => ({ sourceBindingDigest: 'preview-only:catalog', actual }),
    createHistory: (document: unknown) => ({ document }), setHistory() {}, setProjectId() {}, setStorageRevision() {}, setSavedVisualRevision() {},
    setPreviewConnecting() {}, setSourceOpen() {}, receivePreviewState: async () => {}, setNotice: (notice: string) => notices.push(notice),
  };
  const bind = callback('bindPreviewSource', env) as unknown as (result: unknown, edit: boolean) => Promise<void>;
  await bind({}, false);
  assert.equal(historyRef.current.document.actual, source); assert.match(notices[0], /只读查看/);
  await assert.rejects(() => bind({}, true), /unsupported entry/);
});

test('additional preview inspection objects preserve a byte-matched formal document and managed ownership', async () => {
  const architecture = { sourceDigest: 'source', irDigest: 'ir' }, original = { document: { id: 'formal', sourceBindingDigest: 'source', architecture, revision: 6 } };
  const historyRef = { current: original }, source = { schema: 'summary-source-adapter/1', id: 'formal-case' }, projected: unknown[] = [];
  const environment = {
    previewSnapshot: { current: null }, synchronizePreviewNodeSelection() {}, setPreviewTool() {}, setPortEditing() {}, setGrid() {}, setPreviewBusy() {}, setPreviewCanCancel() {},
    setPreviewDirty() {}, setPreviewUndo() {}, setPreviewRedo() {}, setPreviewVersion() {}, setSelection() {}, savedPreviewGraph: { current: null },
    initialModelLoading: { current: false }, previewLoading: { current: false }, previewCase: { current: 'formal-case' }, previewSource: { current: source },
    synchronizingPreview: { current: false }, historyRef, graphFromSnapshot: (snapshot: any) => snapshot.graph,
    currentPreviewSourceMatches: (actual: unknown) => actual === architecture, currentPreviewNodeBindings: () => new Map(),
    previewPanelDocument: () => { throw Error('inspection cannot revoke formal ownership'); },
    setProjectId: () => { throw Error('inspection cannot detach its managed project'); },
    projectPreviewHistory: (before: unknown) => { projected.push(before); return before; },
  };
  const receive = callback('receivePreviewState', environment) as unknown as (snapshot: unknown) => Promise<void>;
  await receive({ caseId: 'formal-case', graph: { nodes: [{ id: 'formal-node' }, { id: 'opaque-inspection-only' }], edges: [] } });
  assert.equal(historyRef.current, original); assert.deepEqual(projected, [original]);
  environment.currentPreviewSourceMatches = () => false;
  const rejectForeignSource = callback('receivePreviewState', environment) as unknown as (snapshot: unknown) => Promise<void>;
  await rejectForeignSource({ caseId: 'formal-case', graph: { nodes: [], edges: [] } });
  assert.deepEqual(projected, [original], 'a different source cannot borrow the formal generation');
});

test('inspection-only visual operations use preview IDs and ignore errors from a superseded source generation', async () => {
  const sent: unknown[] = [], failures: string[] = [], loadSequence = { current: 3 };
  let reject!: (reason: Error) => void;
  const apply = callback('applyInspectionVisual', {
    readyPreview: () => true, previewLayoutDisabled: false, loadSequence,
    previewEngine: { current: { visual: (operations: unknown) => { sent.push(operations); return new Promise((_resolve, fail) => { reject = fail; }); } } },
    setFailure: (message: string) => { failures.push(message); },
  }) as unknown as (operations: unknown[]) => Promise<void>;
  const operations = [{ type: 'alias', id: 'inspection-only', label: '检查部件' }, { type: 'expand', id: 'inspection-only', expanded: true }];
  const pending = apply(operations); assert.deepEqual(sent, [operations]);
  loadSequence.current++; reject(Error('old source failed')); await pending;
  assert.deepEqual(failures, [], 'late visual failures cannot overwrite another model status');
});

test('formal selection excludes shared inspection evidence and retains its raw preview selection', () => {
  const selected: unknown[] = [], raw: unknown[] = [];
  const select = callback('receivePreviewSelection', {
    previewCase: { current: 'case' }, synchronizePreviewNodeSelection: (value: unknown) => { raw.push(value); },
    historyRef: { current: { document: { architecture: {} } } }, graphFromSnapshot: () => ({ nodes: [] }),
    currentPreviewNodeBindings: () => new Map([['unique-display', 'unique-formal']]),
    setSelection: (value: unknown) => { selected.push(value); }, setPanel() {},
  }) as unknown as (message: unknown) => void;
  select({ caseId: 'case', nodeIds: ['shared-display'] });
  select({ caseId: 'case', nodeIds: ['unique-display'] });
  assert.deepEqual(raw, [['shared-display'], ['unique-display']]);
  assert.deepEqual(selected, [{ kind: 'node', ids: [] }, { kind: 'node', ids: ['unique-formal'] }]);
});

test('a delayed IndexedDB recovery cannot install its authoring workspace after the current model changes', async () => {
  for (const changeGeneration of [false, true]) {
    const frozen = { id: 'formal', sourceBindingDigest: 'source' }, historyRef = { current: { document: frozen } }, loadSequence = { current: 8 };
    const generatedWorkspaces = { current: new Map() }, authoringSessions = { current: new Map() };
    let finish!: (value: unknown) => void;
    const open = callback('continueModelAuthoring', {
      cancelGesture() {}, historyRef, busy: false, activeRecovery: null, loadSequence, sourceDraftKey: () => 'formal-key',
      generatedWorkspaces, authoringSessions, readPersistentGeneratedWorkspace: () => new Promise(resolve => { finish = resolve; }),
      setAuthoringOpen: () => { throw Error('stale cache opened an editor'); },
    });
    const pending = open();
    if (changeGeneration) loadSequence.current++;
    else historyRef.current = { document: { ...frozen } };
    finish({ binding: { workspaceKey: 'old' }, workspace: {} }); await pending;
    assert.equal(generatedWorkspaces.current.size, 0); assert.equal(authoringSessions.current.size, 0);
  }
});

test('source panel opening reuses the existing exact formal binding instead of reparsing and discarding a generated document', async () => {
  const source = { schema: 'summary-source-adapter/1' }, architecture = { sourceDigest: 'generated-source', irDigest: 'generated-ir' };
  const original = { document: { id: 'generated-document', sourceBindingDigest: 'generated-source', architecture } }, historyRef = { current: original };
  const previewBoundSource = { current: '' }, calls: string[] = [];
  const bind = callback('bindPreviewSource', {
    sourceFromResult: () => source, previewSource: { current: undefined }, previewSequence: { current: 0 }, previewCase: { current: 'case' },
    previewSnapshot: { current: {} }, historyRef, previewBoundSource, setPreviewConnecting() {},
    previewSourceMatchesArchitecture: (actualSource: unknown, actualArchitecture: unknown) => actualSource === source && actualArchitecture === architecture,
    receivePreviewState: async () => { calls.push('sync'); }, continueModelAuthoring: async () => { calls.push('edit'); },
    api: { previewEditSource: () => { throw Error('must retain exact generation'); } },
  }) as unknown as (result: unknown, edit: boolean) => Promise<void>;
  await bind({}, true);
  assert.equal(historyRef.current, original); assert.equal(previewBoundSource.current, 'generated-source:generated-ir'); assert.deepEqual(calls, ['sync', 'edit']);
});

test('actual hierarchy expansion delegates one preview transaction without repeating the formal layout and ignores a stale rejection', async () => {
  const previous = { document: { revision: 1, architecture: {} }, past: [], future: [] };
  const historyRef = { current: previous }, loadSequence = { current: 1 }, sent: unknown[] = [], failures: string[] = [];
  let fail!: (error: Error) => void;
  const apply = callback('apply', {
    useCallback: (value: unknown) => value, cancelGesture() {}, historyRef, loadSequence,
    studioTelemetry: { beginInteraction() {}, endInteraction() {} }, readyPreview: () => true,
    mapPreviewOperations: () => [{ type: 'expand', id: 'preview-attention', expanded: true }],
    reduceHistory() { throw new Error('must not run a second layout engine'); },
    previewEngine: { current: { visual: (operations: unknown) => { sent.push(operations); return new Promise((_resolve, reject) => { fail = reject; }); } } },
    setHistory() { throw new Error('must await authoritative snapshot'); }, setNotice() {}, setFailure: (message: string) => failures.push(message),
  }) as unknown as (operations: unknown[]) => void;
  apply([{ type: 'expand', id: 'formal-attention', expanded: true }]);
  assert.deepEqual(sent, [[{ type: 'expand', id: 'preview-attention', expanded: true }]]);
  assert.equal(historyRef.current, previous);
  loadSequence.current++; fail(new Error('old model rejected')); await Promise.resolve();
  assert.deepEqual(failures, [''], 'a late error from a superseded source generation cannot replace the current status');
});

test('actual preview source check caches an immutable generation and rechecks either source or architecture replacement', () => {
  const architecture = { entry: 'model:Model', sources: [{ path: 'model.py', content: 'original' }] };
  const original = { files: { 'model.py': 'original' } }, replacement = { files: { 'model.py': 'changed' } };
  const previewSource = { current: original }, previewSourceMatch = { current: null as unknown }, calls: unknown[] = [];
  const matches = callback('currentPreviewSourceMatches', {
    previewSource, previewSourceMatch,
    previewSourceMatchesArchitecture: (source: typeof original, actual: typeof architecture) => {
      calls.push([source, actual]); return source.files['model.py'] === actual.sources[0].content;
    },
  }) as unknown as (target: typeof architecture) => boolean;
  assert.equal(matches(architecture), true); assert.equal(matches(architecture), true); assert.equal(calls.length, 1);
  previewSource.current = replacement;
  assert.equal(matches(architecture), false); assert.equal(calls.length, 2, 'a newly imported source cannot inherit an old byte-match result');
  const changedArchitecture = { ...architecture, sources: [{ path: 'model.py', content: 'changed' }] };
  assert.equal(matches(changedArchitecture), true); assert.equal(calls.length, 3, 'a formal source edit rechecks its new architecture');
});

test('actual mixed expansion and paint batch remains one engine transaction and preserves parent history on rejection', async () => {
  const previous = { document: { revision: 3 }, past: [], future: [] }, historyRef = { current: previous }, calls: unknown[] = [], failures: string[] = [];
  let reject!: (error: Error) => void;
  const operations = [{ type: 'expand', id: 'branch-left', expanded: true }, { type: 'expand', id: 'branch-right', expanded: false }, { type: 'alias', id: 'child', label: 'Display' }];
  const apply = callback('apply', {
    useCallback: (value: unknown) => value, cancelGesture() {}, historyRef, loadSequence: { current: 5 },
    studioTelemetry: { beginInteraction() {}, endInteraction() {} }, readyPreview: () => true, mapPreviewOperations: (batch: unknown[]) => batch,
    reduceHistory() { throw Error('mixed expansion must not invoke a second layout'); },
    previewEngine: { current: { visual: (batch: unknown[]) => { calls.push(batch); return new Promise((_done, fail) => { reject = fail; }); } } },
    setHistory() { throw Error('must not publish before transaction succeeds'); }, setNotice() {}, setFailure: (message: string) => failures.push(message),
  }) as unknown as (operations: unknown[]) => void;
  apply(operations); assert.deepEqual(calls, [operations]); assert.equal(historyRef.current, previous);
  reject(Error('layout rejected')); await Promise.resolve();
  assert.equal(historyRef.current, previous); assert.match(failures.at(-1)!, /layout rejected/);
});

test('actual catalog source request rejects an old A response after an A to B to A switch and keeps busy snapshots on the old case', async () => {
  const previewCase = { current: 'seed' }, previewSequence = { current: 0 }, loadSequence = { current: 0 }, historyRef = { current: { document: { id: 'seed', sourceBindingDigest: 'preview-only:seed' } } as any };
  const deferred: { resolve: (result: unknown) => void }[] = [], bound: unknown[] = [], history: unknown[] = [];
  const environment = {
    previewSnapshot: { current: null }, synchronizePreviewNodeSelection() {}, setPreviewTool() {}, setPortEditing() {}, setGrid() {}, setPreviewBusy() {}, setPreviewCanCancel() {},
    setPreviewDirty() {}, setPreviewUndo() {}, setPreviewRedo() {}, setPreviewVersion() {}, setSelection() {}, savedPreviewGraph: { current: null },
    initialModelLoading: { current: false }, previewLoading: { current: false }, previewCase, previewSequence, loadSequence, previewBoundSource: { current: '' }, previewSource: { current: undefined },
    setBusy() {}, setPreviewConnecting() {}, previewPanelDocument: (snapshot: any) => ({ id: snapshot.caseId, sourceBindingDigest: `preview-only:${snapshot.caseId}` }),
    createHistory: (document: unknown) => ({ document, past: [], future: [] }), historyRef, setHistory: (next: unknown) => history.push(next), setExampleId() {}, setProjectId() {}, setNotice() {},
    previewEngine: { current: { source: () => new Promise(resolve => { deferred.push({ resolve }); }) } },
    bindPreviewSource: async (result: unknown) => { bound.push(result); }, synchronizingPreview: { current: false },
    graphFromSnapshot: (snapshot: any) => snapshot.graph, previewGraphEdges: () => [],
    enteringAuthoring: { current: false }, authoringOpen: false, previewCoverage: { current: null },
    projectPreviewHistory: (before: unknown) => before,
  };
  const receive = callback('receivePreviewState', environment) as unknown as (snapshot: any) => Promise<void>;
  const a1 = receive({ caseId: 'A', graph: { caseId: 'A', nodes: [] } });
  const b = receive({ caseId: 'B', graph: { caseId: 'B', nodes: [] } });
  const a2 = receive({ caseId: 'A', graph: { caseId: 'A', nodes: [] } });
  deferred[0].resolve({ version: 'old-A' }); deferred[1].resolve({ version: 'B' }); await Promise.all([a1, b]);
  assert.deepEqual(bound, [], 'same case ID cannot bypass the source generation guard');
  deferred[2].resolve({ version: 'new-A' }); await a2;
  assert.deepEqual(bound, [{ version: 'new-A' }]); assert.equal(historyRef.current.document.id, 'A');
  const before = historyRef.current, count = history.length;
  await receive({ caseId: 'A', busy: true, graph: { caseId: 'A', nodes: [] } });
  assert.equal(historyRef.current, before); assert.equal(history.length, count, 'an old-case busy snapshot during loading must not create a new source document');
  await receive({ caseId: 'B', busy: true, graph: { caseId: 'B', nodes: [] } });
  assert.equal(previewCase.current, 'A'); assert.equal(deferred.length, 3);
  assert.equal(historyRef.current, before, 'a busy candidate cannot claim a new model before commit');
});


test('saved native graph keeps a derived panel projection saved while real alias or geometry edits remain dirty', async () => {
  for (const edit of ['none', 'alias', 'geometry', 'formal']) {
    const savedGraph = { caseId: 'case', nodes: [{ id: 'a', label: 'A', kind: 'linear', x: 10, y: 20, w: 120, h: 60 }], edges: [],
      studioPresentation: { nodes: { a: { alias: 'Saved alias' } } } };
    const graph = structuredClone(savedGraph);
    if (edit === 'alias') graph.studioPresentation.nodes.a.alias = 'New alias';
    if (edit === 'geometry') graph.nodes[0].x = 80;
    const document = previewPanelDocument({ caseId: 'case', graph: savedGraph });
    if (edit === 'formal') { document.sourceBindingDigest = 'formal-source'; document.architecture.sourceDigest = 'formal-source'; }
    const historyRef = { current: { document, past: [], future: [] } as any };
    let dirty = false, savedRevision = document.revision;
    const environment = {
      previewSnapshot: { current: null }, synchronizePreviewNodeSelection() {}, setPreviewTool() {}, setPortEditing() {}, setGrid() {}, setPreviewBusy() {}, setPreviewCanCancel() {},
      savedPreviewGraph: { current: JSON.stringify(savedGraph) }, setPreviewDirty: (value: boolean) => { dirty = value; },
      setSavedVisualRevision: (value: number) => { savedRevision = value; }, setPreviewUndo() {}, setPreviewRedo() {}, setPreviewVersion() {}, setSelection() {},
      initialModelLoading: { current: false }, previewLoading: { current: false }, previewCase: { current: 'case' },
      synchronizingPreview: { current: false }, previewSource: { current: { schema: 'fixture', caseId: 'case' } }, historyRef,
      currentPreviewSourceMatches: () => true, graphFromSnapshot: (value: any) => value.graph,
      currentPreviewNodeBindings: () => previewUniqueNodeBindings(historyRef.current.document.architecture, graph),
      projectPreviewHistory, setHistory() {},
    };
    await (callback('receivePreviewState', environment) as unknown as (snapshot: any) => Promise<void>)({ caseId: 'case', dirty: true, graph });
    assert.equal(historyRef.current.document.displayAliases.a, graph.studioPresentation.nodes.a.alias);
    assert.ok(historyRef.current.document.revision > document.revision, 'actual panel projection changed its revision');
    assert.equal(dirty || savedRevision !== historyRef.current.document.revision, edit !== 'none', edit);
    if (edit === 'formal') assert.equal(savedRevision, document.revision, 'formal document edits retain their own save contract');
  }
});
