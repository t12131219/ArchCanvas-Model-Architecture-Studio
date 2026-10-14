import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

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

function importHarness(formalSupported = true) {
  const calls: string[] = [], notices: string[] = [], failures: string[] = [];
  const snapshot = { caseId: 'new-case', graph: { nodes: [{ id: 'input' }], edges: [] } };
  const historyRef = { current: null as any }, loadSequence = { current: 0 }, previewLoading = { current: false };
  const environment = {
    cancelGesture() {}, loadSequence, previewSequence: { current: 0 }, previewLoading, filename: 'new.py', sourceText: 'model bytes', entry: 'new:Model',
    previewSource: { current: undefined }, previewCase: { current: '' }, previewSnapshot: { current: null }, previewBoundSource: { current: '' }, historyRef,
    api: { previewAnalyze: async () => { calls.push('preview-parse'); return { id: 'new-case' }; },
      previewEditSource: async () => { calls.push('editor-parse'); if (!formalSupported) throw new Error('unsupported editor syntax'); return { sourceDigest: 'source', irDigest: 'ir' }; } },
    previewEngine: { current: { load: async () => { calls.push('preview-load'); }, snapshot: async () => snapshot } },
    openArchitecture: async () => { calls.push('open-formal'); },
    previewPanelDocument: () => ({ sourceBindingDigest: 'preview-only:new-case' }), createHistory: (document: unknown) => ({ document }),
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

test('actual edit entry awaits the latest preview snapshot and never opens an editor after a stale model response', async () => {
  const calls: string[] = [], sequence = { current: 4 };
  let finish!: (value: object) => void;
  const env = { enteringAuthoring: { current: false }, busy: false, activeRecovery: null, historyRef: { current: {} }, loadSequence: sequence,
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
  const env = { activeRecovery: null, historyRef, saving: { current: false }, loadSequence: { current: 1 }, storageRevision: 3, savedPreviewGraph,
    useCallback: (value: unknown) => value,
    previewEngine: { current: { save: async () => {}, snapshot: async () => snapshot } },
    receivePreviewState: async () => { historyRef.current = { document: { ...historyRef.current.document, revision: 9 } }; },
    readyPreview: () => true,
    api: { save: async (...args: unknown[]) => { sent.push(args); return { revision: 4 }; } },
    setBusy() {}, setNotice() {}, setFailure() {}, setStorageRevision() {}, setPreviewDirty() {}, setSavedVisualRevision: (value: number) => revisions.push(value) };
  await callback('save', env)();
  assert.equal(sent[0][0].revision, 9); assert.equal(sent[0][2].document.revision, 9);
  assert.equal(sent[0][1], 3); assert.deepEqual(revisions, [9]); assert.equal(savedPreviewGraph.current, JSON.stringify(snapshot.graph));
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
