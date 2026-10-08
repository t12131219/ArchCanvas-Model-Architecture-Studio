import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import type { PointerEvent } from 'react';
import { cameraViewportSize, resizeCameraViewport } from '../src/cameraViewport.ts';
import type { CameraViewport } from '../src/cameraViewport.ts';
import { beginCameraPan, cameraAtPanInput } from '../src/cameraGesture.ts';
import type { CameraPan, CameraState } from '../src/cameraGesture.ts';
import { fitCameraToBounds, viewportToWorld } from '../src/cameraProjection.ts';
import { canApplyCameraViewTicket, readCameraView, sameCameraViewDocument, writeCameraView } from '../src/cameraViewState.ts';
import type { CameraViewIdentity, CameraViewStorage } from '../src/cameraViewState.ts';
import type { CameraViewTicket } from '../src/cameraViewState.ts';
import { buildScene, createDocument, createHistory, reduceHistory } from '../src/core/index.ts';
import { prepareMovePreview } from '../src/core/movePreview.ts';
import type { CanvasDocument, HistoryState, VisualOperation } from '../src/core/types.ts';

const small = { width: 672, height: 711 }, large = { width: 883, height: 786 };
const baseline = { x: -14, y: -49.5, zoom: 1 };
function center(view: CameraState, size: CameraViewport) {
  // Independent equation: no product projection/resize helper supplies oracle.
  return { x: (size.width / 2 - view.x) / view.zoom, y: (size.height / 2 - view.y) / view.zoom };
}
function close(actual: number, expected: number) { assert.ok(Math.abs(actual - expected) < 1e-8, `${actual} != ${expected}`); }

test('the observed large-to-small live resize keeps world centre 350,405 in its first coordinated result', () => {
  const next = resizeCameraViewport({ x: 91.5, y: -12, zoom: 1 }, large, small)!;
  assert.deepEqual(next, baseline);
  assert.deepEqual(center(next, small), { x: 350, y: 405 });
  assert.deepEqual(resizeCameraViewport(next, small, large), { x: 91.5, y: -12, zoom: 1 });
});

test('fractional, negative and small-fit cameras preserve centre and zoom across anisotropic size chains', () => {
  for (const view of [baseline, { x: -1204.25, y: 380.75, zoom: .017 }, { x: .125, y: -.375, zoom: 3 }]) {
    const sizes = [small, { width: 4096.5, height: 160.25 }, { width: 80, height: 70 }, large, small];
    const expected = center(view, small);
    let current = view;
    for (let index = 1; index < sizes.length; index++) {
      current = resizeCameraViewport(current, sizes[index - 1], sizes[index])!;
      const observed = center(current, sizes[index]);
      close(observed.x, expected.x); close(observed.y, expected.y);
      assert.equal(current.zoom, view.zoom);
    }
    close(current.x, view.x); close(current.y, view.y);
  }
});

test('same-size deliveries are no-ops and invalid or hidden dimensions cannot establish a frame', () => {
  assert.equal(resizeCameraViewport(baseline, small, { ...small }), baseline);
  for (const size of [null, undefined, { width: 0, height: 711 }, { width: 672, height: -1 },
    { width: NaN, height: 711 }, { width: 672, height: Infinity }, { width: 100001, height: 711 }]) {
    assert.equal(cameraViewportSize(size), null);
    if (size) {
      assert.equal(resizeCameraViewport(baseline, small, size), null);
      assert.equal(resizeCameraViewport(baseline, size, small), null);
    }
  }
  for (const view of [{ ...baseline, x: Infinity }, { ...baseline, y: NaN }, { ...baseline, zoom: 0 },
    { ...baseline, zoom: -1 }, { ...baseline, zoom: Infinity }]) assert.equal(resizeCameraViewport(view, small, large), null);
  const before = JSON.stringify({ baseline, small, large });
  resizeCameraViewport(baseline, small, large);
  assert.equal(JSON.stringify({ baseline, small, large }), before);
});

type Gesture = { type: 'pan' | 'move' | 'box'; pointerId: number; x: number; y: number; camera: CameraState;
  pan?: CameraPan; ids: string[]; dx: number; dy: number; document?: CanvasDocument; preview?: ReturnType<typeof prepareMovePreview> };
type Pointer = PointerEvent<HTMLDivElement>;

// Execute real App callbacks and its real observer effect, rather than a copied
// implementation. This harness does not mount React or certify browser paint.
function appHarness(tool: 'pan' | 'select' = 'pan', observerAvailable = true) {
  const source = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8');
  const ast = ts.createSourceFile('App.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const app = ast.statements.find(item => ts.isFunctionDeclaration(item) && item.name?.text === 'App');
  assert.ok(app && ts.isFunctionDeclaration(app) && app.body);
  const names = ['readCameraViewport', 'persistCamera', 'claimCamera', 'claimGestureCamera', 'commitCamera', 'synchronizeCameraViewport',
    'cancelGesture', 'initializeCamera', 'apply', 'panInput', 'pointerDown', 'pointerMove', 'pointerUp'];
  const snippets = names.map(name => {
    const statement = app.body!.statements.find(item => ts.isFunctionDeclaration(item) ? item.name?.text === name :
      ts.isVariableStatement(item) && item.declarationList.declarations.some(d => ts.isIdentifier(d.name) && d.name.text === name));
    assert.ok(statement, `actual App callback ${name}`); return statement.getText(ast);
  });
  const identityHelper = ast.statements.find(item => ts.isFunctionDeclaration(item) && item.name?.text === 'cameraViewIdentity');
  assert.ok(identityHelper);
  const effect = app.body.statements.find(item => ts.isExpressionStatement(item) && ts.isCallExpression(item.expression) &&
    ts.isIdentifier(item.expression.expression) && item.expression.expression.text === 'useLayoutEffect');
  assert.ok(effect, 'actual viewport useLayoutEffect');
  const document = createDocument({ schemaVersion: 1, id: 'resize-source', label: 'Resize source', entry: 'Model',
    sourceDigest: 'a'.repeat(64), irDigest: 'b'.repeat(64), sources: [], diagnostics: [], edges: [],
    nodes: [{ id: 'leaf', label: 'Linear', kind: 'Linear', category: 'linear', children: [], ports: [], parameters: {}, evidence: 'source' }] });
  const historyRef = { current: createHistory(document) }, cameraRef = { current: { ...baseline } };
  const owner: CameraViewIdentity = { documentId: document.id, sourceBindingDigest: document.sourceBindingDigest,
    irDigest: document.architecture.irDigest, visualRevision: document.revision };
  const cameraOwner = { current: owner as CameraViewIdentity | null }, cameraViewport = { current: { ...small } as CameraViewport | null };
  const gesture = { current: null as Gesture | null }, portGesture = { current: null as { pointerId: number } | null };
  const cameraIntent = { current: 10 }, loadSequence = { current: 4 }, cameraInitializationFrame = { current: 0 }, frame = { current: 0 };
  const pendingCameraInitialization = { current: null as { ticket: CameraViewTicket; restore: boolean } | null };
  const values = new Map<string, string>(), accesses: string[] = [], rendered: CameraState[] = [], selected: { kind: string; ids: string[] }[] = [];
  const storage: CameraViewStorage = { getItem: key => { accesses.push('read'); return values.get(key) ?? null; },
    setItem: (key, value) => { accesses.push('write'); values.set(key, value); } };
  let dimensions: CameraViewport = { ...small }, nextFrame = 0;
  const pending = new Map<number, FrameRequestCallback>(), captured = new Set<number>();
  const element = { getBoundingClientRect: () => ({ ...dimensions, left: 20, top: 40 }),
    hasPointerCapture: (id: number) => captured.has(id), setPointerCapture: (id: number) => { captured.add(id); },
    releasePointerCapture: (id: number) => { captured.delete(id); } };
  const viewportRef = { current: element as typeof element | null };
  const observers: { callback: () => void; target: unknown; disconnected: boolean }[] = [];
  const fallback = new Map<string, () => void>(), operations: VisualOperation[][] = [];
  const cleanups: (() => void)[] = [], flushes: string[] = [];
  class Observer {
    record: typeof observers[number];
    constructor(callback: () => void) { this.record = { callback, target: null, disconnected: false }; observers.push(this.record); }
    observe(target: unknown) { this.record.target = target; }
    disconnect() { this.record.disconnected = true; }
  }
  const scene = buildScene(historyRef.current.document);
  const implicitRoots = new Set<string>();
  const environment = { historyRef, implicitRoots, cameraRef, cameraOwner, cameraViewport, cameraIntent, loadSequence, cameraInitializationFrame, pendingCameraInitialization, frame,
    gesture, portGesture, portRequest: { current: 0 }, viewportRef, scene, current: historyRef.current.document, tool,
    activeRecovery: null, layoutMoveScope: 'all-frontiers', space: { current: false }, busy: false, inputSpec: null, selection: { kind: 'node', ids: [] },
    editingTarget: () => false, setPreview: () => {}, setRecoveryPreview: () => {}, setBox: () => {}, setPortDraft: () => {},
    setIsPanning: () => {}, setPanel: () => {}, setFailure: () => {}, setNotice: () => {},
    setCamera: (view: CameraState) => { rendered.push({ ...view }); },
    setHistory: (value: HistoryState) => { assert.equal(value, historyRef.current); },
    setSelection: (value: { kind: string; ids: string[] }) => { selected.push(value); },
    useCallback: <T>(callback: T) => callback,
    useLayoutEffect: (callback: () => (() => void) | undefined) => { const cleanup = callback(); if (cleanup) cleanups.push(cleanup); },
    flushSync: (callback: () => void) => { flushes.push('enter'); callback(); flushes.push('exit'); },
    ResizeObserver: observerAvailable ? Observer : undefined,
    window: { addEventListener: (name: string, callback: () => void) => { fallback.set(name, callback); },
      removeEventListener: (name: string, callback: () => void) => { if (fallback.get(name) === callback) fallback.delete(name); } },
    authoringOpen: false, cameraSessionStorage: () => storage,
    canApplyCameraViewTicket, readCameraView, writeCameraView, sameCameraViewDocument, cameraViewportSize, resizeCameraViewport,
    beginCameraPan, cameraAtPanInput, fitCameraToBounds, viewportToWorld, buildScene, prepareMovePreview,
    reduceHistory: (prior: HistoryState, action: Parameters<typeof reduceHistory>[1]) => {
      if (action.type === 'apply') operations.push(action.operations); return reduceHistory(prior, action);
    },
    studioTelemetry: { beginInteraction: () => 1, endInteraction: () => {} },
    requestAnimationFrame: (callback: FrameRequestCallback) => { const id = ++nextFrame; pending.set(id, callback); return id; },
    cancelAnimationFrame: (id: number) => { pending.delete(id); },
  };
  const executable = ts.transpileModule(`${identityHelper.getText(ast)}\n${snippets.join('\n')}\nfunction installObserver() { ${effect.getText(ast)} }`,
    { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  const callbacks = new Function(...Object.keys(environment), `${executable}\nreturn { ${names.join(',')}, installObserver };`)(...Object.values(environment)) as {
    persistCamera: () => void; claimCamera: () => void; commitCamera: (view: CameraState) => void;
    synchronizeCameraViewport: () => void; cancelGesture: () => void; initializeCamera: (doc: CanvasDocument, sequence: number) => void;
    pointerDown: (event: Pointer) => void; pointerMove: (event: Pointer) => void; pointerUp: (event: Pointer) => void;
    installObserver: () => void;
  };
  const event = (x: number, y: number, nodeId?: string) => ({ pointerId: 7, clientX: x + 20, clientY: y + 40,
    button: 0, shiftKey: false, currentTarget: element, preventDefault() {}, target: { closest: (selector: string) =>
      selector === '[data-node-id]' && nodeId ? { getAttribute: () => nodeId } : null } }) as unknown as Pointer;
  return { ...callbacks, owner, document, historyRef, cameraRef, cameraOwner, cameraViewport, cameraIntent, loadSequence,
    gesture, portGesture, cameraInitializationFrame, pendingCameraInitialization, frame, values, accesses, storage, rendered, selected, observers, cleanups,
    viewportRef, element, pending, operations, captured, flushes, fallback, event,
    resize: (size: CameraViewport) => { dimensions = { ...size }; },
    runFrames: () => { const work = [...pending]; pending.clear(); for (const [, callback] of work) callback(0); } };
}

test('actual App idle resize commits the latest centre synchronously without a new intent or history entry', () => {
  const h = appHarness(), original = JSON.stringify(h.historyRef.current), intent = h.cameraIntent.current;
  h.resize(large); h.synchronizeCameraViewport();
  assert.deepEqual(h.cameraRef.current, { x: 91.5, y: -12, zoom: 1 });
  assert.deepEqual(h.cameraViewport.current, large);
  assert.deepEqual(readCameraView(h.storage, h.owner, small), baseline);
  assert.equal(h.pending.size, 0); assert.equal(h.cameraIntent.current, intent);
  h.resize(small); h.synchronizeCameraViewport();
  assert.deepEqual(h.cameraRef.current, baseline); assert.equal(h.rendered.length, 2);
  h.synchronizeCameraViewport(); assert.equal(h.rendered.length, 2);
  assert.equal(JSON.stringify(h.historyRef.current), original);
});

test('actual persistence before observer delivery uses the camera anchor instead of a newly resized DOM', () => {
  const h = appHarness(); h.resize(large); h.persistCamera();
  const state = JSON.parse([...h.values.values()][0]);
  assert.deepEqual(state.worldCenter, { x: 350, y: 405 }); assert.deepEqual(state.capturedViewport, small);
  h.synchronizeCameraViewport();
  const updated = JSON.parse([...h.values.values()][0]);
  assert.deepEqual(updated.worldCenter, state.worldCenter); assert.deepEqual(updated.capturedViewport, large);
});

test('actual pan, move, box and port ownership defer resize until their mapping is released', () => {
  for (const type of ['pan', 'move', 'box', 'port'] as const) {
    const h = appHarness();
    if (type === 'port') h.portGesture.current = { pointerId: 7 };
    else h.gesture.current = { type, pointerId: 7, x: 200, y: 180, camera: baseline, ids: [], dx: 0, dy: 0 };
    h.resize(large); h.synchronizeCameraViewport();
    assert.deepEqual(h.cameraRef.current, baseline); assert.deepEqual(h.cameraViewport.current, small);
    assert.equal(h.rendered.length, 0); assert.equal(h.values.size, 0);
    h.cancelGesture();
    assert.deepEqual(h.cameraRef.current, { x: 91.5, y: -12, zoom: 1 });
    assert.deepEqual(h.cameraViewport.current, large);
  }
});

test('actual terminal pan includes the unsampled pointerup delta then applies the queued resize exactly once', () => {
  const h = appHarness(); h.pointerDown(h.event(200, 180));
  h.pointerMove(h.event(216, 188)); assert.equal(h.pending.size, 1);
  h.resize(large); h.synchronizeCameraViewport();
  h.pointerUp(h.event(232, 196));
  assert.deepEqual(h.cameraRef.current, { x: 123.5, y: 4, zoom: 1 });
  assert.deepEqual(center(h.cameraRef.current, large), { x: 318, y: 389 });
  assert.deepEqual(readCameraView(h.storage, h.owner, small), { x: 18, y: -33.5, zoom: 1 });
  assert.equal(h.pending.size, 0); assert.equal(h.gesture.current, null); assert.equal(h.captured.size, 0);
  h.runFrames(); h.synchronizeCameraViewport();
  assert.deepEqual(h.cameraRef.current, { x: 123.5, y: 4, zoom: 1 });
  assert.equal(h.historyRef.current.past.length, 0); assert.deepEqual(h.operations, []);
});

test('actual cancel after a resized pan preview restores the original world centre and never retains that preview', () => {
  const h = appHarness(); h.pointerDown(h.event(200, 180)); h.pointerMove(h.event(240, 204)); h.runFrames();
  assert.deepEqual(h.cameraRef.current, { x: 26, y: -25.5, zoom: 1 });
  h.resize(large); h.synchronizeCameraViewport(); h.cancelGesture();
  assert.deepEqual(h.cameraRef.current, { x: 91.5, y: -12, zoom: 1 });
  assert.deepEqual(center(h.cameraRef.current, large), { x: 350, y: 405 });
  assert.deepEqual(readCameraView(h.storage, h.owner, small), baseline);
  assert.equal(h.pending.size, 0); assert.equal(h.captured.size, 0);
});

test('actual resized object drag keeps its typed delta and one undo entry independent of transient camera coordination', () => {
  const h = appHarness('select'), before = buildScene(h.historyRef.current.document).nodes.find(node => node.id === 'leaf')!;
  h.pointerDown(h.event(200, 180, 'leaf')); h.pointerMove(h.event(216, 188));
  h.resize(large); h.synchronizeCameraViewport(); h.pointerUp(h.event(232, 196));
  assert.deepEqual(h.operations, [[{ type: 'move', ids: ['leaf'], dx: 32, dy: 16, scope: 'all-frontiers' }]]);
  const after = buildScene(h.historyRef.current.document).nodes.find(node => node.id === 'leaf')!;
  assert.equal(after.x - before.x, 32); assert.equal(after.y - before.y, 16);
  assert.equal(h.historyRef.current.past.length, 1); assert.equal(h.pending.size, 0);
  assert.deepEqual(center(h.cameraRef.current, large), { x: 350, y: 405 });
  const undone = reduceHistory(h.historyRef.current, { type: 'undo' });
  assert.deepEqual(undone.document.layout, h.document.layout);
  assert.ok(!Object.hasOwn(h.historyRef.current.document, 'camera') && !Object.hasOwn(h.historyRef.current.document, 'worldCenter'));
});

test('actual box terminal selection uses the old frozen camera before viewport coordination', () => {
  const h = appHarness('select'); h.pointerDown(h.event(0, 0));
  h.resize(large); h.synchronizeCameraViewport(); h.pointerUp(h.event(650, 700));
  assert.deepEqual(h.selected.at(-1), { kind: 'node', ids: ['leaf'] });
  assert.deepEqual(center(h.cameraRef.current, large), { x: 350, y: 405 });
  assert.equal(h.historyRef.current.past.length, 0);
});

test('an explicit current-size camera commit wins without a second old-size correction', () => {
  const h = appHarness(); h.resize(large);
  const explicit = { x: 160, y: -70, zoom: .75 };
  h.commitCamera(explicit); h.synchronizeCameraViewport();
  assert.deepEqual(h.cameraRef.current, explicit); assert.deepEqual(h.cameraViewport.current, large);
  assert.equal(h.rendered.length, 1); assert.equal(h.cameraIntent.current, 11);
  h.resize(small); h.synchronizeCameraViewport();
  assert.deepEqual(h.cameraRef.current, { x: 54.5, y: -107.5, zoom: .75 });
  assert.deepEqual(center(h.cameraRef.current, small), center(explicit, large));
});

test('initialization ignores unowned resize and restores at its latest viewport; active drag defers it', () => {
  const h = appHarness(); writeCameraView(h.storage, h.owner, baseline, small);
  h.initializeCamera(h.document, 4); h.resize(large); h.synchronizeCameraViewport();
  assert.deepEqual(h.cameraRef.current, baseline);
  h.gesture.current = { type: 'move', pointerId: 7, x: 200, y: 180, camera: baseline, ids: [], dx: 0, dy: 0 };
  h.runFrames(); assert.equal(h.cameraOwner.current, null); assert.equal(h.pending.size, 0);
  assert.ok(h.pendingCameraInitialization.current);
  h.gesture.current = null; h.synchronizeCameraViewport(); h.runFrames();
  assert.deepEqual(h.cameraRef.current, { x: 91.5, y: -12, zoom: 1 });
  assert.deepEqual(h.cameraViewport.current, large); assert.equal(h.pending.size, 0);
});

test('an early actual spatial gesture owns its displayed mapping and invalidates a delayed restore even after document commit', () => {
  for (const nodeId of ['leaf', undefined]) {
    const h = appHarness('select');
    writeCameraView(h.storage, h.owner, { x: 300, y: 400, zoom: .5 }, small);
    h.initializeCamera(h.document, 4);
    h.pointerDown(h.event(200, 180, nodeId));
    assert.deepEqual(h.cameraOwner.current, h.owner); assert.equal(h.cameraIntent.current, 11);
    assert.deepEqual(h.cameraViewport.current, small);
    h.resize(large); h.runFrames();
    assert.deepEqual(h.cameraRef.current, baseline, 'old initialization cannot overwrite the active pointer view');
    h.pointerUp(h.event(232, 196)); h.runFrames();
    assert.deepEqual(h.cameraRef.current, { x: 91.5, y: -12, zoom: 1 });
    assert.deepEqual(center(h.cameraRef.current, large), { x: 350, y: 405 });
    const identity = { ...h.owner, visualRevision: h.historyRef.current.document.revision };
    h.persistCamera(); assert.deepEqual(readCameraView(h.storage, identity, small), baseline);
    assert.equal(h.cameraInitializationFrame.current, 0); assert.equal(h.pending.size, 0);
  }
});

test('an early actual pan establishes its own viewport anchor before a resized terminal sample', () => {
  const h = appHarness(); h.initializeCamera(h.document, 4); h.cameraViewport.current = null;
  h.pointerDown(h.event(200, 180));
  assert.deepEqual(h.cameraViewport.current, small);
  h.resize(large); h.runFrames(); h.pointerUp(h.event(232, 196));
  assert.deepEqual(h.cameraRef.current, { x: 123.5, y: 4, zoom: 1 });
  assert.deepEqual(center(h.cameraRef.current, large), { x: 318, y: 389 });
  assert.equal(h.pending.size, 0); assert.equal(h.cameraIntent.current, 12);
});

test('a later document, revision, load or explicit intent rejects pending initialization and old ownership', () => {
  for (const invalidate of [
    (h: ReturnType<typeof appHarness>) => { h.loadSequence.current++; h.cameraOwner.current = null; },
    (h: ReturnType<typeof appHarness>) => { h.historyRef.current = createHistory({ ...h.document, id: 'other' }); },
    (h: ReturnType<typeof appHarness>) => { h.historyRef.current = createHistory({ ...h.document, revision: 1 }); },
    (h: ReturnType<typeof appHarness>) => { h.historyRef.current = createHistory({ ...h.document, sourceBindingDigest: 'c'.repeat(64),
      architecture: { ...h.document.architecture, sourceDigest: 'c'.repeat(64) } }); },
  ]) {
    const h = appHarness(); h.initializeCamera(h.document, 4); invalidate(h); h.resize(large);
    h.synchronizeCameraViewport(); h.runFrames();
    assert.deepEqual(h.cameraRef.current, baseline); assert.equal(h.values.size, 0); assert.equal(h.pending.size, 0);
  }
  const h = appHarness(); h.initializeCamera(h.document, 4); h.resize(large);
  h.commitCamera({ x: 55, y: 60, zoom: .5 }); h.runFrames(); h.synchronizeCameraViewport();
  assert.deepEqual(h.cameraRef.current, { x: 55, y: 60, zoom: .5 });
  assert.deepEqual(h.cameraViewport.current, large);
});

test('the actual observer effect commits in its delivery and rejects disconnected or replaced elements', () => {
  const h = appHarness(); h.installObserver(); assert.equal(h.observers.length, 1);
  const observer = h.observers[0]; assert.equal(observer.target, h.element);
  h.resize(large); observer.callback();
  assert.deepEqual(h.cameraRef.current, { x: 91.5, y: -12, zoom: 1 });
  assert.deepEqual(h.flushes, ['enter', 'exit']); assert.equal(h.pending.size, 0);
  h.viewportRef.current = { ...h.element }; h.resize(small); observer.callback();
  assert.deepEqual(h.cameraRef.current, { x: 91.5, y: -12, zoom: 1 });
  assert.equal(h.flushes.length, 2);
  h.viewportRef.current = h.element; h.cleanups[0](); observer.callback();
  assert.equal(observer.disconnected, true); assert.equal(h.flushes.length, 2);
  h.installObserver();
  assert.deepEqual(h.cameraRef.current, baseline); assert.equal(h.observers.length, 2);
});

test('the real window fallback follows the same mapping and unregisters after cleanup', () => {
  const h = appHarness('pan', false); h.installObserver();
  assert.equal(h.observers.length, 0); assert.equal(h.fallback.size, 1);
  h.resize(large); h.fallback.get('resize')!();
  assert.deepEqual(h.cameraRef.current, { x: 91.5, y: -12, zoom: 1 });
  h.cleanups[0](); assert.equal(h.fallback.size, 0);
});

test('the actual observer remount resumes a bounded exhausted hidden initialization at the now-visible dimensions', () => {
  const h = appHarness(); writeCameraView(h.storage, h.owner, baseline, small);
  h.viewportRef.current = null; h.initializeCamera(h.document, 4); h.installObserver();
  for (let index = 0; index < 4; index++) h.runFrames();
  assert.equal(h.pending.size, 0); assert.equal(h.cameraOwner.current, null);
  assert.ok(h.pendingCameraInitialization.current); assert.equal(h.observers.length, 0);
  h.runFrames(); assert.equal(h.pending.size, 0, 'hidden viewport is not retried indefinitely');
  h.viewportRef.current = h.element; h.resize(large); h.installObserver();
  assert.equal(h.observers.length, 1); assert.equal(h.pending.size, 1);
  h.observers[0].callback(); assert.equal(h.pending.size, 1, 'initial observer delivery does not queue a duplicate');
  h.runFrames();
  assert.deepEqual(h.cameraRef.current, { x: 91.5, y: -12, zoom: 1 });
  assert.deepEqual(h.cameraViewport.current, large); assert.equal(h.pendingCameraInitialization.current, null);
  assert.deepEqual(readCameraView(h.storage, h.owner, small), baseline);
});

test('the actual observer revives an exhausted tiny viewport only when dimensions become usable', () => {
  const h = appHarness(); writeCameraView(h.storage, h.owner, baseline, small);
  h.resize({ width: 80, height: 70 }); h.installObserver(); h.initializeCamera(h.document, 4);
  for (let index = 0; index < 4; index++) h.runFrames();
  assert.equal(h.pending.size, 0); assert.equal(h.cameraOwner.current, null);
  h.observers[0].callback(); assert.equal(h.pending.size, 0);
  h.resize(large); h.observers[0].callback(); assert.equal(h.pending.size, 1);
  h.runFrames(); assert.deepEqual(h.cameraRef.current, { x: 91.5, y: -12, zoom: 1 });
  assert.equal(h.pendingCameraInitialization.current, null);
});

test('a stale load/intent/revision cannot revive after hidden exhaustion, and an owned remount keeps explicit intent', () => {
  for (const invalidate of [
    (h: ReturnType<typeof appHarness>) => { h.cameraIntent.current++; },
    (h: ReturnType<typeof appHarness>) => { h.loadSequence.current++; },
    (h: ReturnType<typeof appHarness>) => { h.historyRef.current = createHistory({ ...h.document, revision: 1 }); },
  ]) {
    const h = appHarness(); h.viewportRef.current = null; h.initializeCamera(h.document, 4);
    for (let index = 0; index < 4; index++) h.runFrames();
    invalidate(h); h.viewportRef.current = h.element; h.resize(large); h.installObserver(); h.runFrames();
    assert.equal(h.pending.size, 0); assert.equal(h.pendingCameraInitialization.current, null);
    assert.deepEqual(h.cameraRef.current, baseline); assert.equal(h.values.size, 0);
  }
  const h = appHarness(); h.viewportRef.current = null; h.initializeCamera(h.document, 4);
  for (let index = 0; index < 4; index++) h.runFrames();
  h.viewportRef.current = h.element; h.resize(large);
  h.commitCamera({ x: 120, y: 60, zoom: .8 });
  assert.equal(h.pendingCameraInitialization.current, null);
  h.installObserver(); h.runFrames();
  assert.deepEqual(h.cameraRef.current, { x: 120, y: 60, zoom: .8 });
  assert.equal(h.pending.size, 0); assert.equal(h.cameraIntent.current, 11);
});

test('hidden dimensions are ignored; a tiny visible viewport can return without contaminating stored centre', () => {
  const h = appHarness(); h.persistCamera();
  const original = [...h.values.values()][0];
  h.resize({ width: 0, height: 0 }); h.synchronizeCameraViewport();
  assert.deepEqual(h.cameraRef.current, baseline); assert.deepEqual(h.cameraViewport.current, small);
  h.resize({ width: 80, height: 70 }); h.synchronizeCameraViewport();
  assert.deepEqual(center(h.cameraRef.current, { width: 80, height: 70 }), { x: 350, y: 405 });
  assert.equal([...h.values.values()][0], original, 'session storage refuses undersized captures');
  h.resize(small); h.synchronizeCameraViewport();
  assert.deepEqual(h.cameraRef.current, baseline); assert.deepEqual(readCameraView(h.storage, h.owner, small), baseline);
});
