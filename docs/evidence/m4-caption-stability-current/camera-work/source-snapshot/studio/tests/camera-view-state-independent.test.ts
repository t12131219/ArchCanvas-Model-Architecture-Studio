import test from 'node:test';
import assert from 'node:assert/strict';
import { cameraAtPanInput, beginCameraPan } from '../src/cameraGesture.ts';
import { createDocument, createHistory, reduceHistory } from '../src/core/index.ts';
import { canApplyCameraViewTicket, cameraViewStorageKey, captureCameraView, readCameraView,
  restoreCameraView, sameCameraViewDocument, writeCameraView } from '../src/cameraViewState.ts';
import type { CameraViewIdentity, CameraViewStorage } from '../src/cameraViewState.ts';
import type { Architecture } from '../src/core/types.ts';

const identity: CameraViewIdentity = { documentId: 'canvas-a', sourceBindingDigest: 'a'.repeat(64),
  irDigest: 'b'.repeat(64), visualRevision: 20 };
const viewport = { width: 672, height: 641 };
const camera = { x: -12, y: -82.5, zoom: 1 };

function storage(): CameraViewStorage & { values: Map<string, string> } {
  const values = new Map<string, string>();
  return { values, getItem: key => values.get(key) ?? null, setItem: (key, value) => { values.set(key, value); } };
}
function cloned<T>(value: T): T { return JSON.parse(JSON.stringify(value)); }

test('same-viewport reload preserves exact camera and independently calculated world centre', () => {
  const state = captureCameraView(identity, camera, viewport)!;
  assert.deepEqual(state.worldCenter, { x: 348, y: 403 });
  assert.deepEqual(state.capturedViewport, { width: 672, height: 641 });
  assert.deepEqual(restoreCameraView(state, identity, viewport), camera);
  const store = storage();
  assert.equal(writeCameraView(store, identity, camera, viewport), true);
  assert.deepEqual(readCameraView(store, identity, viewport), camera);
  assert.equal(store.values.size, 1);
});

test('a resized reopened viewport preserves world centre and zoom through new pixel translation', () => {
  const state = captureCameraView(identity, { x: 120, y: -80, zoom: .5 }, { width: 800, height: 600 })!;
  assert.deepEqual(state.worldCenter, { x: 560, y: 760 });
  assert.deepEqual(restoreCameraView(state, identity, { width: 1200, height: 900 }), { x: 320, y: 70, zoom: .5 });
  // Independent centre equation; neither capture nor projection is used as oracle.
  const next = restoreCameraView(state, identity, { width: 1200, height: 900 })!;
  assert.equal((600 - next.x) / next.zoom, 560);
  assert.equal((450 - next.y) / next.zoom, 760);
});

test('source/IR/document identities and visual revisions prevent stale or cross-model reuse', () => {
  const state = captureCameraView(identity, camera, viewport)!;
  for (const other of [
    { ...identity, documentId: 'canvas-b' },
    { ...identity, sourceBindingDigest: 'c'.repeat(64) },
    { ...identity, irDigest: 'd'.repeat(64) },
    { ...identity, visualRevision: 19 },
    { ...identity, visualRevision: 21 },
  ]) assert.equal(restoreCameraView(state, other, viewport), null);
  assert.equal(sameCameraViewDocument(identity, { ...identity, visualRevision: 21 }), true);
  assert.equal(sameCameraViewDocument(identity, { ...identity, sourceBindingDigest: 'c'.repeat(64) }), false);
});

test('per-document source/IR keys isolate values without adding revision to the key', () => {
  const store = storage();
  assert.equal(writeCameraView(store, identity, camera, viewport), true);
  const other = { ...identity, documentId: 'canvas-b' };
  assert.equal(writeCameraView(store, other, { x: 32, y: 48, zoom: .75 }, viewport), true);
  assert.equal(store.values.size, 2);
  assert.deepEqual(readCameraView(store, identity, viewport), camera);
  assert.deepEqual(readCameraView(store, other, viewport), { x: 32, y: 48, zoom: .75 });
  assert.equal(cameraViewStorageKey(identity), cameraViewStorageKey({ ...identity, visualRevision: 21 }));
  assert.notEqual(cameraViewStorageKey(identity), cameraViewStorageKey({ ...identity, irDigest: 'f'.repeat(64) }));
});

test('invalid stored versions, centres, scales, viewport and identity are refused rather than coerced', () => {
  const state = captureCameraView(identity, camera, viewport)!;
  const cases: unknown[] = [null, [], 'state', { ...state, schemaVersion: 2 },
    { ...state, zoom: 0 }, { ...state, zoom: -1 }, { ...state, zoom: 3.01 },
    { ...state, zoom: Infinity }, { ...state, zoom: NaN }, { ...state, zoom: '1' },
    { ...state, worldCenter: { x: 1e10, y: 0 } }, { ...state, worldCenter: { x: 0, y: NaN } },
    { ...state, capturedViewport: { width: 0, height: 641 } },
    { ...state, capturedViewport: { width: 96, height: 641 } },
    { ...state, capturedViewport: { width: 672, height: Infinity } },
    { ...state, identity: { ...identity, visualRevision: -1 } },
    { ...state, identity: { ...identity, visualRevision: 1.5 } },
    { ...state, identity: { ...identity, sourceBindingDigest: 'wrong' } }];
  for (const value of cases) assert.equal(restoreCameraView(value, identity, viewport), null);
  for (const next of [{ width: 0, height: 0 }, { width: 96, height: 92 }, { width: NaN, height: 641 },
    { width: 1e6, height: 641 }]) assert.equal(restoreCameraView(state, identity, next), null);
});

test('fit scales below .15 remain valid while unsafe captures are rejected', () => {
  const fitted = { x: 20, y: 30, zoom: .017 };
  const state = captureCameraView(identity, fitted, viewport)!;
  const restored = restoreCameraView(state, identity, viewport)!;
  assert.ok(Math.abs(restored.x - fitted.x) < 1e-9 && Math.abs(restored.y - fitted.y) < 1e-9);
  assert.equal(restored.zoom, fitted.zoom);
  for (const invalid of [{ ...camera, zoom: 0 }, { ...camera, zoom: 1e-9 }, { ...camera, x: Infinity },
    { ...camera, y: 1e10 }]) assert.equal(captureCameraView(identity, invalid, viewport), null);
  assert.equal(cameraViewStorageKey({ ...identity, documentId: '' }), null);
  assert.equal(cameraViewStorageKey({ ...identity, documentId: 'a'.repeat(1025) }), null);
});

test('malformed, absent, oversized, disabled and quota-failed storage leave a graceful fallback', () => {
  const store = storage(), key = cameraViewStorageKey(identity)!;
  for (const raw of ['{', 'null', '"camera"', 'x'.repeat(16385), JSON.stringify({ schemaVersion: 9 })]) {
    store.setItem(key, raw); assert.equal(readCameraView(store, identity, viewport), null);
  }
  const failure: CameraViewStorage = { getItem: () => { throw new Error('SecurityError'); },
    setItem: () => { throw new Error('QuotaExceededError'); } };
  assert.equal(readCameraView(failure, identity, viewport), null);
  assert.equal(writeCameraView(failure, identity, camera, viewport), false);
  assert.equal(readCameraView(null, identity, viewport), null);
  assert.equal(writeCameraView(null, identity, camera, viewport), false);
});

test('delayed restore cannot supersede explicit fit, zoom, focus, pan or a newer document load', () => {
  const ticket = { identity, loadSequence: 4, intentSequence: 10 };
  assert.equal(canApplyCameraViewTicket(ticket, identity, 4, 10), true);
  for (const action of ['fit', 'zoom', 'focus', 'pan', 'reset']) {
    assert.equal(canApplyCameraViewTicket(ticket, identity, 4, 11), false, action);
  }
  assert.equal(canApplyCameraViewTicket(ticket, identity, 5, 10), false);
  assert.equal(canApplyCameraViewTicket(ticket, { ...identity, documentId: 'canvas-b' }, 4, 10), false);
  assert.equal(canApplyCameraViewTicket(ticket, { ...identity, irDigest: 'c'.repeat(64) }, 4, 10), false);
  assert.equal(canApplyCameraViewTicket(ticket, { ...identity, visualRevision: 21 }, 4, 10), false);
  assert.equal(canApplyCameraViewTicket(ticket, null, 4, 10), false);
});

test('terminal pan is saved and cancellation can restore the prior camera without retaining the preview', () => {
  const store = storage(); writeCameraView(store, identity, camera, viewport);
  const pan = beginCameraPan(camera, { pointerId: 3, clientX: 200, clientY: 180, viewportX: 20, viewportY: 40 });
  const intermediate = cameraAtPanInput(pan, { pointerId: 3, clientX: 245, clientY: 220, viewportX: 20, viewportY: 40 })!;
  assert.deepEqual(intermediate, { x: 33, y: -42.5, zoom: 1 });
  assert.deepEqual(readCameraView(store, identity, viewport), camera);
  writeCameraView(store, identity, intermediate, viewport);
  assert.deepEqual(readCameraView(store, identity, viewport), intermediate);
  writeCameraView(store, identity, pan.camera, viewport);
  assert.deepEqual(readCameraView(store, identity, viewport), camera);
});

test('capture/restore/tickets mutate no input and store revisions without touching Canvas/history', () => {
  const architecture: Architecture = { schemaVersion: 1, id: 'a', label: 'A', sourceDigest: identity.sourceBindingDigest,
    irDigest: identity.irDigest, entry: 'model:A', nodes: [], edges: [], diagnostics: [], sources: [] };
  const document = createDocument(architecture), history = createHistory(document);
  const before = cloned({ identity, camera, viewport, document, history });
  const owner = { ...identity, documentId: document.id, visualRevision: document.revision };
  const store = storage();
  captureCameraView(identity, camera, viewport); writeCameraView(store, owner, camera, viewport);
  const next = reduceHistory(history, { type: 'apply', baseRevision: 0, operations: [{ type: 'page', page: { background: '#fff' } }] });
  writeCameraView(store, { ...owner, visualRevision: next.document.revision }, camera, viewport);
  assert.equal(readCameraView(store, owner, viewport), null);
  assert.deepEqual(readCameraView(store, { ...owner, visualRevision: next.document.revision }, viewport), camera);
  assert.deepEqual({ identity, camera, viewport, document, history }, before);
  assert.ok(!Object.hasOwn(document, 'camera') && !Object.hasOwn(document, 'worldCenter'));
});

test('a deliberately adopted reconciled identity can retain view while old source state remains isolated', () => {
  const store = storage(); writeCameraView(store, identity, camera, viewport);
  const reconciled = { ...identity, sourceBindingDigest: 'c'.repeat(64), irDigest: 'd'.repeat(64), visualRevision: 0 };
  assert.equal(readCameraView(store, reconciled, viewport), null);
  assert.equal(writeCameraView(store, reconciled, camera, viewport), true);
  assert.deepEqual(readCameraView(store, reconciled, viewport), camera);
  assert.deepEqual(readCameraView(store, identity, viewport), camera);
  assert.equal(store.values.size, 2);
});
