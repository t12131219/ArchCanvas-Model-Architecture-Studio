// Independent math and callback review. No product writes or model execution.
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import ts from '../../../../studio/node_modules/typescript/lib/typescript.js';
import { cameraViewportSize, resizeCameraViewport } from '../../../../studio/src/cameraViewport.ts';
import { beginCameraPan, cameraAtPanInput } from '../../../../studio/src/cameraGesture.ts';
import { canApplyCameraViewTicket, sameCameraViewDocument, readCameraView, writeCameraView } from '../../../../studio/src/cameraViewState.ts';
import { viewportToWorld, fitCameraToBounds } from '../../../../studio/src/cameraProjection.ts';

const root = new URL('../../../../', import.meta.url), here = new URL('./', import.meta.url);
const output = new URL('attempt-2/', here);
if (existsSync(output)) throw new Error('Append-only evidence; choose a new attempt');
mkdirSync(output);
const binding = path => {
  const data = readFileSync(new URL(path, root));
  return { path, bytes: data.length, sha256: createHash('sha256').update(data).digest('hex') };
};
const inputPaths = ['studio/src/App.tsx', 'studio/src/cameraViewport.ts', 'studio/src/cameraGesture.ts',
  'studio/src/cameraProjection.ts', 'studio/src/cameraViewState.ts', 'studio/tests/camera-viewport-resize-independent.test.ts',
  'studio/tests/camera-view-state-independent.test.ts'];
const inputs = inputPaths.map(binding), appText = readFileSync(new URL('studio/src/App.tsx', root), 'utf8');
if (inputs[0].sha256 !== '385e2b3a153b1895969aec4f3a34b16d151d7cbfc4169aa78fced48fd0422a49' ||
    inputs[1].sha256 !== '8f9b3ae654e98da4af1f4750ec6eea41534d42deb271353e44f97563f4234115') throw new Error('Stable author hashes changed');
const ast = ts.createSourceFile('App.tsx', appText, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const app = ast.statements.find(s => ts.isFunctionDeclaration(s) && s.name?.text === 'App');
const names = ['readCameraViewport', 'persistCamera', 'claimCamera', 'claimGestureCamera', 'commitCamera', 'synchronizeCameraViewport',
  'cancelGesture', 'initializeCamera', 'panInput', 'pointerDown', 'pointerMove', 'pointerUp', 'pointerCancelled', 'candidatePorts'];
const statement = name => app.body.statements.find(s => ts.isFunctionDeclaration(s) ? s.name?.text === name :
  ts.isVariableStatement(s) && s.declarationList.declarations.some(d => ts.isIdentifier(d.name) && d.name.text === name));
const snippets = names.map(name => {
  const s = statement(name); if (!s) throw new Error(`Missing actual callback ${name}`); return s.getText(ast);
});
const identityHelper = ast.statements.find(s => ts.isFunctionDeclaration(s) && s.name?.text === 'cameraViewIdentity');
const observer = app.body.statements.find(s => ts.isExpressionStatement(s) && ts.isCallExpression(s.expression) &&
  ts.isIdentifier(s.expression.expression) && s.expression.expression.text === 'useLayoutEffect');
const executable = ts.transpileModule(`${identityHelper.getText(ast)}\n${snippets.join('\n')}\nfunction install() { ${observer.getText(ast)} }`,
  { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
const checks = [], observations = [];
const check = (name, passed, details) => checks.push({ name, passed: !!passed, ...(details === undefined ? {} : { details }) });
const near = (a, b) => Math.abs(a - b) <= 1e-7 * Math.max(1, Math.abs(b));
const sameView = (a, b) => a && b && near(a.x, b.x) && near(a.y, b.y) && a.zoom === b.zoom;
const center = (v, s) => ({ x: (s.width / 2 - v.x) / v.zoom, y: (s.height / 2 - v.y) / v.zoom });
const small = { width: 672, height: 711 }, large = { width: 883, height: 786 }, base = { x: -14, y: -49.5, zoom: 1 };
const expectedResize = (v, a, b) => ({ x: b.width / 2 - (a.width / 2 - v.x), y: b.height / 2 - (a.height / 2 - v.y), zoom: v.zoom });

function harness(tool = 'pan', portPrepared = false) {
  const document = { id: 'independent-viewport-review', revision: 31, sourceBindingDigest: 'a'.repeat(64), architecture: { irDigest: 'b'.repeat(64) } };
  const identity = { documentId: document.id, visualRevision: document.revision, sourceBindingDigest: document.sourceBindingDigest, irDigest: document.architecture.irDigest };
  const refs = { historyRef: { current: { document } }, cameraRef: { current: { ...base } }, cameraOwner: { current: identity },
    cameraViewport: { current: { ...small } }, cameraIntent: { current: 20 }, loadSequence: { current: 8 },
    gesture: { current: null }, portGesture: { current: null }, portRequest: { current: 5 },
    frame: { current: 0 }, cameraInitializationFrame: { current: 0 }, pendingCameraInitialization: { current: null }, viewportRef: { current: null } };
  let rectangle = { ...small, left: 20, top: 40 }, nextFrame = 0;
  const frames = new Map(), captures = new Set(), values = new Map(), writes = [], renders = [], proposals = [], releases = [],
    observers = [], cleanups = [], flushes = [], visualOperations = [];
  const storage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => { values.set(key, value); writes.push(JSON.parse(value)); } };
  let callbacks;
  const element = { getBoundingClientRect: () => ({ ...rectangle }), hasPointerCapture: id => captures.has(id),
    setPointerCapture: id => captures.add(id), releasePointerCapture: id => {
      releases.push({ id, gestureCleared: refs.gesture.current === null, portCleared: refs.portGesture.current === null,
        requestAtRelease: refs.portRequest.current }); captures.delete(id);
      callbacks.pointerCancelled({ pointerId: id });
    } };
  refs.viewportRef.current = element;
  const scene = { bounds: { x: 0, y: 0, width: 600, height: 600 }, nodes: [
    { id: 'producer', expanded: false, x: 80, y: 140, width: 40, height: 60, ports: [
      { id: 'producer:out', direction: 'out', canonicalPortId: 'out', canonicalNodeId: 'producer', x: 100, y: 200 } ] },
    { id: 'consumer', expanded: false, x: 180, y: 240, width: 40, height: 60, ports: [
      { id: 'consumer:in', direction: 'in', canonicalPortId: 'in', canonicalNodeId: 'consumer', proxy: false, x: 200, y: 240 } ] } ] };
  class Observer {
    constructor(callback) { this.record = { callback, disconnected: false, target: null }; observers.push(this.record); }
    observe(target) { this.record.target = target; }
    disconnect() { this.record.disconnected = true; }
  }
  let resolveOptions;
  const optionsPromise = new Promise(resolve => { resolveOptions = resolve; });
  const env = { ...refs, current: document, scene, tool, space: { current: false }, selection: { kind: 'node', ids: [] },
    activeRecovery: null, busy: false, inputSpec: portPrepared ? {} : null, authoringOpen: false, ResizeObserver: Observer,
    useCallback: callback => callback, useLayoutEffect: callback => { const cleanup = callback(); if (cleanup) cleanups.push(cleanup); },
    flushSync: callback => { flushes.push('enter'); callback(); flushes.push('exit'); },
    window: { addEventListener() {}, removeEventListener() {} },
    setCamera: view => renders.push({ ...view }), setIsPanning() {}, setPreview() {}, setRecoveryPreview() {}, setBox() {}, setPortDraft() {},
    setSelection() {}, setPanel() {}, setFailure() {}, setConnectionProposal: value => proposals.push(value),
    editingTarget: () => false, inspectRebind: () => optionsPromise,
    prepareMovePreview: () => ({}), apply: (...args) => visualOperations.push(args),
    cameraSessionStorage: () => storage, cameraViewportSize, resizeCameraViewport, beginCameraPan, cameraAtPanInput,
    viewportToWorld, fitCameraToBounds, readCameraView, writeCameraView, sameCameraViewDocument, canApplyCameraViewTicket,
    buildScene: () => scene,
    requestAnimationFrame: callback => { const id = ++nextFrame; frames.set(id, callback); return id; },
    cancelAnimationFrame: id => frames.delete(id) };
  callbacks = new Function(...Object.keys(env), `${executable}\nreturn { ${names.join(',')}, install };`)(...Object.values(env));
  const event = (x, y, target = null) => ({ pointerId: 7, clientX: x + rectangle.left, clientY: y + rectangle.top, currentTarget: element,
    target: { closest: selector => selector === '[data-node-id]' && target === 'producer' ? { getAttribute: () => 'producer' } :
      selector === '[data-port-id]' && target === 'consumer:in' ? { getAttribute: () => 'consumer:in' } : null },
    button: 0, shiftKey: false, preventDefault() {} });
  const runFrame = () => { const q = [...frames]; frames.clear(); for (const [, callback] of q) callback(0); };
  return { ...callbacks, ...refs, document, identity, scene, element, storage, writes, values, renders, proposals, releases,
    frames, captures, observers, cleanups, flushes, visualOperations, optionsPromise, resolveOptions, event, runFrame,
    resize: (size, origin = { left: rectangle.left, top: rectangle.top }) => { rectangle = { ...size, ...origin }; } };
}

// Product helper is the subject; the oracle is the world-centre equation.
const sizes = [small, large, { width: 80, height: 70 }, { width: 100000, height: 100000 },
  { width: 97.125, height: 93.5 }, { width: 4096.25, height: 160.5 }];
for (const zoom of [1e-6, .017, .75, 1, 3]) for (const x of [-1e6, -14, .125, 900000]) for (const y of [-990000, -49.5, .5, 33])
  for (const a of sizes) for (const b of sizes) {
    const view = { x, y, zoom }, result = resizeCameraViewport(view, a, b), expected = expectedResize(view, a, b);
    const oldCenter = center(view, a), newCenter = center(result, b);
    check(`independent resize equation ${zoom}/${x}/${y}/${a.width}/${a.height}/${b.width}/${b.height}`,
      sameView(result, expected) && near(oldCenter.x, newCenter.x) && near(oldCenter.y, newCenter.y));
  }
for (const invalid of [null, undefined, { width: 0, height: 1 }, { width: -1, height: 711 },
  { width: NaN, height: 711 }, { width: Infinity, height: 711 }, { width: 100000.1, height: 711 }])
  check('invalid hidden dimension fails closed ' + String(invalid?.width), cameraViewportSize(invalid) === null);

{
  const h = harness(); h.resize(large); h.persistCamera();
  check('pending resize persists established small mapping', h.writes.at(-1).capturedViewport.width === 672 &&
    h.writes.at(-1).worldCenter.x === 350 && h.writes.at(-1).worldCenter.y === 405);
  h.synchronizeCameraViewport();
  check('idle immediately coordinates new mapping without intent', sameView(h.cameraRef.current, expectedResize(base, small, large)) && h.cameraIntent.current === 20);
  check('synchronized persistence uses large frame and same world centre', h.writes.at(-1).capturedViewport.width === 883 &&
    h.writes.at(-1).worldCenter.x === 350 && h.writes.at(-1).worldCenter.y === 405);
}
for (const type of ['pan', 'move', 'box', 'port']) {
  const h = harness();
  if (type === 'port') h.portGesture.current = { pointerId: 7 };
  else h.gesture.current = { type, pointerId: 7, camera: { ...base } };
  h.captures.add(7); h.resize(large); h.synchronizeCameraViewport();
  check(type + ' resize held before cancel', sameView(h.cameraRef.current, base) && h.cameraViewport.current.width === 672 && h.renders.length === 0);
  h.cancelGesture();
  check(type + ' cancel coordinates exactly once', sameView(h.cameraRef.current, expectedResize(base, small, large)) && h.renders.length === 1 && h.portRequest.current === 6);
  check(type + ' synchronous lostcapture sees cleared ownership', h.releases.length === 1 && h.releases[0].gestureCleared && h.releases[0].portCleared && h.portRequest.current === 6);
}
{
  const h = harness(); h.pointerDown(h.event(200, 180)); h.pointerMove(h.event(216, 188));
  h.resize(large, { left: 31, top: 25 }); h.synchronizeCameraViewport(); h.pointerUp(h.event(232, 196));
  const finalAtOldFrame = { x: 18, y: -33.5, zoom: 1 };
  check('pan pointerup samples unsent terminal and then compensates size', sameView(h.cameraRef.current, expectedResize(finalAtOldFrame, small, large)));
  check('pan lostcapture cannot rollback terminal or run pending preview', h.frames.size === 0 && h.releases.at(-1).gestureCleared && h.cameraViewport.current.width === 883);
  h.runFrame();
  check('stale pending pan preview remains absent', sameView(h.cameraRef.current, expectedResize(finalAtOldFrame, small, large)));
}

for (const invalidate of ['none', 'load', 'request', 'document']) {
  const h = harness(); let resolve;
  const promise = new Promise(r => { resolve = r; });
  h.portGesture.current = { pointerId: 7, request: 5, sequence: 8, document: h.document,
    port: { canonicalNodeId: 'consumer', canonicalPortId: 'in' }, promise };
  h.captures.add(7); h.resize(large); h.synchronizeCameraViewport();
  // Native terminal coordinates still use the original camera. The actual
  // producer port is world100,200, hence viewport86,150.5 in the old frame.
  h.pointerUp(h.event(86, 150.5));
  check('port ' + invalidate + ' clears before release without invalidating own request', h.releases[0].portCleared && h.portRequest.current === 5 && h.portGesture.current === null);
  if (invalidate === 'load') h.loadSequence.current++;
  if (invalidate === 'request') h.portRequest.current++;
  if (invalidate === 'document') h.historyRef.current = { document: { ...h.document } };
  resolve({ candidates: [{ binding: { nodeId: 'producer', portId: 'out' } }], blockers: [] });
  await promise; await Promise.resolve(); await Promise.resolve();
  check('port ' + invalidate + ' pending result ownership', invalidate === 'none' ?
    h.proposals.length === 1 && h.proposals[0].candidate.binding.nodeId === 'producer' : h.proposals.length === 0);
  check('port ' + invalidate + ' queued resize exactly once after terminal', sameView(h.cameraRef.current, expectedResize(base, small, large)) && h.cameraViewport.current.width === 883);
}
{
  const h = harness(); h.install(); const old = h.observers[0];
  h.viewportRef.current = null; h.cleanups[0](); h.install();
  h.resize(large); old.callback();
  check('authoring hidden/disconnected old observer cannot update state', sameView(h.cameraRef.current, base) && h.flushes.length === 0);
  h.viewportRef.current = { ...h.element }; h.install();
  check('authoring return owner coordinates new element before effect completes', sameView(h.cameraRef.current, expectedResize(base, small, large)) && h.observers.length === 2);
  h.resize(small); old.callback();
  check('replaced old observer remains rejected', sameView(h.cameraRef.current, expectedResize(base, small, large)));
  h.observers[1].callback();
  check('new observer owns replacement element', sameView(h.cameraRef.current, base));
}
for (const change of ['load', 'intent', 'document', 'revision']) {
  const h = harness(); h.initializeCamera(h.document, 8); h.resize(large);
  if (change === 'load') h.loadSequence.current++;
  if (change === 'intent') h.commitCamera({ x: 120, y: -80, zoom: .75 });
  if (change === 'document') h.historyRef.current = { document: { ...h.document, id: 'other' } };
  if (change === 'revision') h.historyRef.current = { document: { ...h.document, revision: 32 } };
  const previous = { ...h.cameraRef.current }; h.runFrame();
  check('stale initializer rejects ' + change, sameView(h.cameraRef.current, previous) && h.frames.size === 0);
}
{
  const h = harness(); h.initializeCamera(h.document, 8); h.gesture.current = { type: 'move', pointerId: 7, camera: base };
  h.runFrame(); h.runFrame();
  check('active gesture retains pending initialization without busy rAF loop', h.cameraOwner.current === null && h.frames.size === 0 && h.pendingCameraInitialization.current !== null);
  h.gesture.current = null; h.synchronizeCameraViewport(); h.runFrame();
  check('released gesture permits pending initializer once', h.cameraOwner.current !== null && h.frames.size === 0);
}
{
  const h = harness(); writeCameraView(h.storage, h.identity, base, small); h.initializeCamera(h.document, 8); h.viewportRef.current = null;
  for (let i = 0; i < 4; i++) h.runFrame();
  const beforeReturn = { frames: h.frames.size, ownerNull: h.cameraOwner.current === null, pending: h.pendingCameraInitialization.current !== null };
  h.viewportRef.current = h.element; h.install();
  h.resize(large); h.observers[0].callback();
  check('visible observer does not duplicate resumed initialization request', h.frames.size === 1);
  h.runFrame();
  const record = { id: 'initialization-while-viewport-hidden', status: 'bounded-counterexample-fixed-in-current-callbacks',
    afterFourMissingViewportFrames: beforeReturn,
    ownerAfterVisibleFrame: h.cameraOwner.current,
    finalCamera: h.cameraRef.current,
    reason: 'Initializer stops bounded retries while hidden but retains its ticket. Returning viewport effect requests one new frame, using the latest usable dimensions.' };
  observations.push(record);
  check('hidden initializer retains bounded request then resumes exactly once', beforeReturn.frames === 0 && beforeReturn.ownerNull && beforeReturn.pending &&
    h.frames.size === 0 && h.cameraOwner.current !== null && h.pendingCameraInitialization.current === null &&
    sameView(h.cameraRef.current, expectedResize(base, small, large)));
}
for (const type of ['move', 'box', 'port', 'pan']) {
  const h = harness(type === 'pan' ? 'pan' : 'select', type === 'port');
  writeCameraView(h.storage, h.identity, { x: 120, y: 300, zoom: .5 }, small);
  h.initializeCamera(h.document, 8); h.cameraViewport.current = null;
  h.pointerDown(h.event(200, 180, type === 'move' ? 'producer' : type === 'port' ? 'consumer:in' : null));
  check(type + ' early native callback owns shown mapping before initialization', h.cameraOwner.current?.documentId === h.document.id &&
    h.cameraIntent.current === 21 && h.pendingCameraInitialization.current === null && h.frames.size === 0 && h.cameraViewport.current?.width === 672);
  h.resize(large); h.runFrame();
  check(type + ' early input rejects delayed restored camera', sameView(h.cameraRef.current, base));
  // A move changes the visual revision on commit. The mapping ownership is
  // semantic-document based, so the subsequent current-revision persistence
  // is valid without letting the old initialization ticket apply.
  if (type === 'move') h.document.revision++;
  h.cancelGesture();
  check(type + ' early cancel still coordinates latest size', sameView(h.cameraRef.current, expectedResize(base, small, large)) && h.frames.size === 0);
  if (type === 'port') {
    h.resolveOptions({ candidates: [], blockers: [] }); await h.optionsPromise; await Promise.resolve();
    check('early cancelled port pending options cannot show proposal', h.proposals.length === 0);
  }
}
const inputReadback = inputPaths.map(binding);
check('seven reviewed source/test bindings unchanged during audit', JSON.stringify(inputs) === JSON.stringify(inputReadback));
const report = { schema: 'archcanvas-independent-viewport-callback-review/1', createdUtc: new Date().toISOString(),
  passed: checks.filter(x => x.passed).length, total: checks.length, checks, failedChecks: checks.filter(x => !x.passed),
  observations, inputBindings: inputs,
  scope: 'Independently derived world-centre equation and actual extracted App callbacks with synchronous lostcapture and controlled rAF/promise schedules. React is not mounted, ResizeObserver delivery is mocked, and setCamera/flushSync do not prove browser paint. No model execution, document write, browser input or publication/performance/human gate certification. Recorded known counterexample is an observation, not a successful feature test.' };
writeFileSync(new URL('report.json', output), JSON.stringify(report, null, 2) + '\n');
const self = readFileSync(new URL('review_callbacks.mjs', here));
writeFileSync(new URL('script-copy.mjs', output), self);
console.log(JSON.stringify({ passed: report.passed, total: report.total, observations }));
if (report.passed !== report.total) process.exitCode = 1;
