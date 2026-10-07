import test from 'node:test';
import assert from 'node:assert/strict';
import { validateInputObservation } from '../scripts/validate_input_observation.mjs';

// Hand-authored browser facts; no Studio/observer serializer or matcher import.
const ids = ['node:A', 'node:P'];
function scene(at, revision, x = 10, y = 10, scale = 1, tx = 100, ty = 40) {
  const m = { a: scale, b: 0, c: 0, d: scale, e: tx, f: ty };
  return { at, documentId: 'canvas-hand-authored', revision, camera: { cssTransform: 'hand-authored-fixture', matrix: m },
    viewport: { x: 0, y: 0, width: 500, height: 400 }, frameRect: { x: 10, y: 70, width: 500, height: 400 },
    sourceDigest: 'a'.repeat(64), irDigest: 'b'.repeat(64), visibleIds: ids, expandedIds: [], pinnedIds: ['node:P'],
    objects: Object.fromEntries(ids.map((id, i) => {
      const canvas = { x: i ? 60 : x, y: i ? 60 : y, width: 20, height: 20 };
      return [id, { canvas, screen: { x: canvas.x * scale + tx, y: canvas.y * scale + ty, width: 20 * scale, height: 20 * scale },
        screenMatrix: m, intersectsViewport: true, label: id, canonicalId: id }];
    })) };
}
function input(id, type, at, x, y, targetToken, kind = 'node') {
  return { id, type, eventAt: at, capturedAt: at + .05, trusted: true, trialId: 'trial-1',
    target: { token: targetToken, nodeId: kind === 'node' ? 'node:A' : null, kind, action: null },
    pointerId: 1, pointerType: 'mouse', button: 0, buttons: type === 'pointerup' ? 0 : 1, x, y,
    key: null, code: null, ctrl: false, meta: false, shift: false, spaceHeld: false, deltaX: null, deltaY: null, deltaMode: null };
}
function fixture() {
  const before = scene(10.1, 3), after = scene(50, 4, 42, 30);
  return { schemaVersion: 1, protocol: 'archcanvas-input-observation/1', label: 'independent authored drag',
    measurement: { mode: 'full', runtimeAccess: 'DOM-only', coordinateSpace: 'iframe-client-css-pixels', latency: 'matched-discrete-event-timing-only',
      continuousInput: 'observed-geometry-proxy-not-paint', frames: 'raf-callback-cadence-not-presented-frames', durationThresholdMs: 16, durationQuantizationMs: 8 },
    environment: { timeOrigin: 1_000_000, isIframe: true, viewport: { width: 500, height: 400, devicePixelRatio: 1 }, scripts: ['http://localhost/assets/frozen.js'],
      supported: { eventTimingObserved: true, longTasksObserved: true } }, startedAt: 0, stoppedAt: 100,
    bindingAtStart: scene(1, 3), trials: [{ id: 'trial-1', spec: { operation: 'drag', targetIds: ['node:A'], anchorIds: [], pinnedIds: ['node:P'] },
      armedAt: 2, status: 'finished', before, after, firstEventId: 'input-1', lastEventId: 'input-3', finishedAt: 51 }],
    events: [input('input-1', 'pointerdown', 10, 110, 50, 't1'), input('input-2', 'pointermove', 20, 126, 60, 't2', 'viewport'), input('input-3', 'pointerup', 40, 142, 70, 't2', 'viewport')],
    frames: [{ at: 5, observedAt: 5.2, trialId: null, geometry: null }, { at: 21, observedAt: 21.2, trialId: 'trial-1', geometry: scene(21.1, 4, 26, 20) },
      { at: 45, observedAt: 45.2, trialId: 'trial-1', geometry: scene(45.1, 4, 42, 30) }, { at: 80, observedAt: 80.2, trialId: null, geometry: null }],
    eventTiming: [{ name: 'pointerdown', startAt: 10, durationMs: 64, processingStart: 10.15, processingEnd: 11, interactionId: 7, targetToken: 't1', targetNodeId: 'node:A' },
      { name: 'pointerup', startAt: 40, durationMs: 32, processingStart: 40.15, processingEnd: 41, interactionId: 7, targetToken: 't2', targetNodeId: null }],
    longTasks: [{ at: 20, durationMs: 60, name: 'self', attribution: [] }], visibility: [{ at: 0, state: 'visible', hasFocus: true, topHasFocus: true }],
    overhead: { sceneReads: [{ at: 10, durationMs: .6, full: true }], inputCallbacks: [{ at: 10, durationMs: .8 }], frameCallbacks: [{ at: 21, durationMs: .4 }], performanceCallbacks: [] },
    buffers: {}, errors: [] };
}

test('authored drag separates native discrete interactions, DOM proxy and callback cadence', () => {
  const result = validateInputObservation(fixture()), t = result.trials[0];
  assert.equal(t.operationSucceeded, true);
  assert.deepEqual(t.changes['node:A'].canvas, { x: 32, y: 20, distancePx: Math.hypot(32, 20) });
  assert.equal(t.protectedObjects[0].canvas.distancePx, 0);
  assert.equal(result.latency.matchedDiscreteInputs, 2);
  assert.equal(result.latency.matchedInteractions, 1);
  assert.equal(result.latency.matchedInteractionP95Ms, 64);
  assert.equal(t.continuousProxies.length, 1);
  assert.ok(Math.abs(t.continuousProxies[0].inputToObservedChangeProxyMs - 1.2) < .0001);
  assert.equal(t.continuousProxies[0].presentedPaintCertified, false);
  assert.equal(result.presentedDragPaintCertified, false);
  assert.equal(result.humanCertified, false);
  assert.equal(result.observerSelfCost.inputCallbacks.p95Ms, .8);
  assert.equal(result.selfCostCategoriesOverlap, true);
});

test('missing and ambiguous native entries remain null; no zero-latency claim', () => {
  const missing = fixture(); missing.eventTiming = [];
  const m = validateInputObservation(missing);
  assert.equal(m.latency.matchedInteractionP95Ms, null);
  assert.equal(m.latency.matchedDiscreteInputs, 0);
  const ambiguous = fixture(); ambiguous.eventTiming.push(structuredClone(ambiguous.eventTiming[0]));
  const a = validateInputObservation(ambiguous);
  assert.equal(a.latency.matches[0].nativeDurationMs, null);
  assert.equal(a.latency.matches[0].missingReason, 'ambiguous');
  assert.equal(a.latency.matchedInteractionP95Ms, 32);
});

test('two raw inputs competing for one native entry stay ambiguous on both sides', () => {
  const r = fixture();
  r.events.splice(1, 0, input('input-4', 'pointerdown', 14, 110, 50, 't1'));
  const result = validateInputObservation(r);
  for (const id of ['input-1', 'input-4']) {
    const m = result.latency.matches.find(m => m.inputId === id);
    assert.equal(m.nativeDurationMs, null);
    assert.equal(m.missingReason, 'ambiguous');
    assert.equal(m.inputCandidateCount, 1);
    assert.equal(m.candidateEntryInputCounts[0].inputs, 2);
  }
  assert.equal(result.latency.matchedDiscreteInputs, 1);
  assert.equal(result.latency.matchedInteractionP95Ms, 32);
});

test('an unassigned competing input cannot lend its native entry to a requested trial', () => {
  const r = fixture(), outside = input('input-4', 'pointerdown', 14, 110, 50, 't1');
  outside.trialId = null; r.events.splice(1, 0, outside);
  const result = validateInputObservation(r);
  assert.equal(result.latency.matches.find(m => m.inputId === 'input-1').nativeDurationMs, null);
  assert.equal(result.latency.matches.find(m => m.inputId === 'input-1').missingReason, 'ambiguous');
});

test('a wrong-target drag remains outside its armed requested trial', () => {
  const r = fixture(), t = r.trials[0];
  t.status = 'no-input'; t.before = null; t.firstEventId = null; t.lastEventId = null;
  r.events.forEach(e => { e.trialId = null; });
  r.events[0].target.nodeId = 'parent-of-requested-node';
  r.frames.forEach(f => { f.trialId = null; f.geometry = null; });
  const result = validateInputObservation(r).trials[0];
  assert.equal(result.observed, false);
  assert.equal(result.operationSucceeded, false);
  assert.equal(result.missingReason, 'requested-target-not-hit');
  assert.equal(result.outsideRequestedTrialInputCount, 3);
  assert.equal(result.outsideRequestedTrialStarts[0].requestedTargetMatched, false);
  assert.equal(result.outsideRequestedTrialStarts[0].targetNodeId, 'parent-of-requested-node');
});

test('untrusted input cannot start a native trial, and a wrong object cannot borrow its latency', () => {
  const synthetic = fixture(); synthetic.events[0].trusted = false;
  assert.throws(() => validateInputObservation(synthetic), /synthetic/);
  const wrongTarget = fixture(); wrongTarget.events[0].target.nodeId = 'other';
  assert.throws(() => validateInputObservation(wrongTarget), /different control\/target/);
  const differentToken = fixture(); differentToken.eventTiming[0].targetToken = 'some-other-element';
  assert.equal(validateInputObservation(differentToken).latency.matches[0].nativeDurationMs, null);
});

test('wrong screen coordinate space, source drift and invented wheel Event Timing are rejected', () => {
  const badScreen = fixture(); badScreen.trials[0].after.objects['node:A'].screen.x += 1;
  assert.throws(() => validateInputObservation(badScreen), /transform/);
  const drift = fixture(); drift.trials[0].after.sourceDigest = 'c'.repeat(64);
  assert.throws(() => validateInputObservation(drift), /Source\/IR changed/);
  const wheel = fixture(); wheel.eventTiming[0].name = 'wheel';
  assert.throws(() => validateInputObservation(wheel), /Event Timing/);
});

test('missing/offscreen pin coverage stays unmeasured instead of being reported as zero screen movement', () => {
  const hidden = fixture(); hidden.trials[0].after.objects['node:P'] = null;
  const h = validateInputObservation(hidden).trials[0].protectedObjects[0];
  assert.equal(h.canvas, null); assert.equal(h.screen, null); assert.equal(h.screenMeasured, false);
  const offscreen = fixture();
  for (const s of [offscreen.trials[0].before, offscreen.trials[0].after]) {
    const p = s.objects['node:P']; p.canvas.x = 1000; p.screen.x = 1100; p.intersectsViewport = false;
  }
  const o = validateInputObservation(offscreen).trials[0].protectedObjects[0];
  assert.equal(o.canvas.distancePx, 0); assert.equal(o.screenMeasured, false);
});

test('missing pointerup/cancel and multiple revisions cannot certify a committed drag', () => {
  for (const mutate of [r => { r.events[2].type = 'pointercancel'; }, r => { r.trials[0].after.revision = 5; }, r => { r.events[2].pointerId = 2; }]) {
    const r = fixture(); mutate(r); assert.equal(validateInputObservation(r).trials[0].operationSucceeded, false);
  }
});

test('camera-only zoom records canvas continuity without inventing a document revision', () => {
  const r = fixture(), t = r.trials[0];
  t.spec.operation = 'zoom'; t.after = scene(50, 3, 10, 10, 1.2); r.events[0].target.action = 'zoom';
  r.frames[1].geometry = scene(21.1, 3, 10, 10, 1.2); r.frames[2].geometry = scene(45.1, 3, 10, 10, 1.2);
  const out = validateInputObservation(r).trials[0];
  assert.equal(out.operationSucceeded, true); assert.equal(out.revisionDelta, 0); assert.equal(out.changes['node:A'].canvas.distancePx, 0);
  t.after.revision = 4; assert.equal(validateInputObservation(r).trials[0].operationSucceeded, false);
});

test('a no-op undo with a new revision does not establish restored geometry', () => {
  const r = fixture(); r.trials[0].spec.operation = 'undo'; r.events[0].target.action = 'undo'; r.trials[0].after = scene(50, 4);
  assert.equal(validateInputObservation(r).trials[0].operationSucceeded, false);
  r.trials[0].after = scene(50, 4, -22, -10);
  assert.equal(validateInputObservation(r).trials[0].operationSucceeded, true);
});

test('bounded-buffer loss and unsupported native timing remain explicit', () => {
  const r = fixture(); r.buffers.events = { limit: 3, dropped: 1 };
  assert.equal(validateInputObservation(r).completeBuffers, false);
  r.buffers.events.limit = 4; assert.throws(() => validateInputObservation(r), /Buffer accounting/);
  const unsupported = fixture(); unsupported.environment.supported.eventTimingObserved = false; unsupported.eventTiming = [];
  assert.equal(validateInputObservation(unsupported).latency.supported, false);
  unsupported.eventTiming = fixture().eventTiming;
  assert.throws(() => validateInputObservation(unsupported), /Unsupported observer/);
});

test('raf-only control contains no full observer/trial/native data', () => {
  const r = fixture(); r.measurement.mode = 'raf-only'; r.trials = []; r.events = []; r.eventTiming = []; r.longTasks = [];
  r.environment.supported = { eventTimingObserved: false, longTasksObserved: false };
  r.frames.forEach(f => { f.trialId = null; f.geometry = null; });
  const out = validateInputObservation(r);
  assert.equal(out.latency.matchedInteractionP95Ms, null); assert.equal(out.trials.length, 0); assert.equal(out.idleCadence.intervals, 3);
  r.events = fixture().events; assert.throws(() => validateInputObservation(r), /raf-only/);
});

// Version2 facts are authored independently of the observer and Studio helper.
// SVG equality is a public visual boundary, never hidden Canvas/history proof.
function publicFacts(r) {
  r.schemaVersion = 2; r.protocol = 'archcanvas-input-observation/2';
  Object.assign(r.measurement, { coordinateSpace: 'window-client-css-pixels',
    panTrigger: 'public-tool-space-middle/1', panTerminal: 'same-pointer-up-and-viewport-relative-camera/1',
    documentContinuity: 'public-svg-and-frontier-not-hidden-document/1' });
  const geometry = [r.bindingAtStart, ...r.trials.flatMap(t => [t.before, t.after]), ...r.frames.flatMap(f => f.geometry ? [f.geometry] : [])];
  for (const g of geometry) if (g) Object.assign(g, { canvasTool: 'pan', handToolPressed: true,
    svgMarkup: '<svg data-document-id="canvas-hand-authored"><g data-node-id="node:A" fill="#abc"/><g data-node-id="node:P"/></svg>',
    selectionMarkup: ['<div class="selection-outline" data-test-identity="node:A"></div>'] });
  for (const e of r.events) {
    Object.assign(e.target, { inCanvas: true, editingTarget: false, canvasControl: false, canvasTool: 'pan', handToolPressed: true });
    e.viewport = { x: 0, y: 0, width: 500, height: 400 };
  }
  return r;
}
function handPanFixture() {
  const r = fixture();
  r.trials[0].spec.operation = 'pan';
  r.trials[0].after = scene(50, 3, 10, 10, 1, 132, 60);
  r.frames[1].geometry = scene(21.1, 3, 10, 10, 1, 116, 50);
  r.frames[2].geometry = scene(45.1, 3, 10, 10, 1, 132, 60);
  return publicFacts(r);
}
function setPublicTool(r, tool, pressed) {
  for (const g of [r.bindingAtStart, ...r.trials.flatMap(t => [t.before, t.after]), ...r.frames.flatMap(f => f.geometry ? [f.geometry] : [])]) {
    if (g) { g.canvasTool = tool; g.handToolPressed = pressed; }
  }
  for (const e of r.events) { e.target.canvasTool = tool; e.target.handToolPressed = pressed; }
}

test('v2 hand-left pan matches actual terminal camera and unchanged public document', () => {
  const r = handPanFixture(), out = validateInputObservation(r), t = out.trials[0];
  assert.equal(out.inputProtocol, 'archcanvas-input-observation/2');
  assert.equal(t.operationSucceeded, true);
  assert.equal(t.panTerminal.status, 'matched');
  assert.deepEqual(t.panTerminal.deltaCssPx, { x: 32, y: 20 });
  assert.deepEqual(t.panTerminal.expectedCamera, { a: 1, b: 0, c: 0, d: 1, e: 132, f: 60 });
  assert.equal(t.publicDocumentContinuity.matched, true);
  assert.equal(t.publicDocumentContinuity.hiddenCanvasCertified, false);
  assert.equal(t.publicDocumentContinuity.historyCertified, false);
  assert.equal(t.panTerminal.presentedPaintCertified, false);
});

test('v2 pan does not require an intermediate move or scheduled RAF to reach pointerup', () => {
  const r = handPanFixture(); r.events.splice(1, 1);
  const out = validateInputObservation(r).trials[0];
  assert.equal(out.trustedPointerMoves, 0);
  assert.equal(out.panTerminal.status, 'matched');
  assert.equal(out.operationSucceeded, true);
});

test('v2 rejects select-mode ordinary left drag and inconsistent toolbar state as pan', () => {
  for (const [tool, pressed] of [['select', false], ['pan', false], ['select', true]]) {
    const r = handPanFixture(); setPublicTool(r, tool, pressed);
    assert.throws(() => validateInputObservation(r), /Pan lacks its actual input trigger/);
  }
  const wrongButton = handPanFixture(); wrongButton.events[0].button = 2; wrongButton.events[0].spaceHeld = true;
  assert.throws(() => validateInputObservation(wrongButton), /Pan lacks its actual input trigger/);
});

test('v2 explicit Space-left and middle remain valid without hand tool', () => {
  for (const mutate of [r => { r.events[0].spaceHeld = true; }, r => { r.events[0].button = 1; }]) {
    const r = handPanFixture(); setPublicTool(r, 'select', false); mutate(r);
    assert.equal(validateInputObservation(r).trials[0].operationSucceeded, true);
  }
});

test('v2 hand pan can start over expand/port glyphs but never an HTML canvas control', () => {
  for (const kind of ['toggle', 'port', 'node', 'viewport']) {
    const r = handPanFixture(); r.events[0].target.kind = kind;
    assert.equal(validateInputObservation(r).trials[0].operationSucceeded, true);
  }
  for (const key of ['canvasControl', 'editingTarget']) {
    const r = handPanFixture(); r.events[0].target[key] = true;
    assert.throws(() => validateInputObservation(r), /Pan lacks its actual input trigger/);
  }
  const outside = handPanFixture(); outside.events[0].target.inCanvas = false;
  assert.throws(() => validateInputObservation(outside), /Pan lacks its actual input trigger/);
});

test('v2 wrong-mode pan stays no-input rather than borrowing an object drag', () => {
  const r = handPanFixture(), t = r.trials[0]; setPublicTool(r, 'select', false);
  t.status = 'no-input'; t.before = null; t.firstEventId = null; t.lastEventId = null;
  r.events.forEach(e => { e.trialId = null; }); r.frames.forEach(f => { f.trialId = null; f.geometry = null; });
  const out = validateInputObservation(r).trials[0];
  assert.equal(out.observed, false); assert.equal(out.operationSucceeded, false);
  assert.equal(out.missingReason, 'left-pointer-without-active-pan-trigger');
});

test('v2 armed object drag cannot borrow a hand-mode native input', () => {
  const r = publicFacts(fixture());
  assert.throws(() => validateInputObservation(r), /Object drag began in pan mode/);
});

test('v2 stale last-RAF camera fails even though a nonzero pan was observed', () => {
  const r = handPanFixture(); r.trials[0].after = scene(50, 3, 10, 10, 1, 116, 50); publicFacts(r);
  const out = validateInputObservation(r).trials[0];
  assert.equal(out.cameraChanged, true);
  assert.equal(out.panTerminal.status, 'mismatch');
  assert.equal(out.operationSucceeded, false);
});

test('v2 terminal delta removes event-time viewport-origin drift', () => {
  const r = handPanFixture();
  r.events[2].viewport.x = -30; r.events[2].x -= 30;
  const out = validateInputObservation(r).trials[0];
  assert.deepEqual(out.panTerminal.deltaCssPx, { x: 32, y: 20 });
  assert.equal(out.operationSucceeded, true);
  r.events[2].x += 30;
  assert.equal(validateInputObservation(r).trials[0].panTerminal.status, 'mismatch');
});

test('v2 same-revision alias/style/binding/frontier/selection mutations fail public continuity', () => {
  const mutations = [
    r => { r.trials[0].after.svgMarkup += '<g fill="#bad"/>'; },
    r => { r.trials[0].after.expandedIds = ['node:A']; },
    r => { r.trials[0].after.pinnedIds = []; },
    r => { r.trials[0].after.visibleIds = ['node:A']; delete r.trials[0].after.objects['node:P']; r.trials[0].spec.pinnedIds = []; },
    r => { r.trials[0].after.selectionMarkup = []; },
    r => { r.trials[0].after.revision = 4; },
  ];
  for (const mutate of mutations) {
    const r = handPanFixture(); mutate(r);
    const out = validateInputObservation(r).trials[0];
    assert.equal(out.publicDocumentContinuity.matched, false); assert.equal(out.operationSucceeded, false);
  }
});

test('v2 cancelled/lost-capture/blur/Escape pan cannot become a successful terminal gesture', () => {
  for (const type of ['pointercancel', 'lostpointercapture', 'blur', 'keydown']) {
    const r = handPanFixture(), interrupt = input('input-4', type, 30, 130, 65, 't2', 'viewport');
    Object.assign(interrupt.target, { inCanvas: true, editingTarget: false, canvasControl: false, canvasTool: 'pan', handToolPressed: true });
    interrupt.viewport = { x: 0, y: 0, width: 500, height: 400 };
    if (type === 'keydown') interrupt.key = 'Escape';
    r.events.splice(2, 0, interrupt);
    const out = validateInputObservation(r).trials[0];
    assert.equal(out.cancelled, true); assert.equal(out.operationSucceeded, false);
  }
});

test('v2 a normal lostcapture after release does not retroactively cancel successful pan', () => {
  const r = handPanFixture(), release = input('input-4', 'lostpointercapture', 41, 142, 70, 't2', 'viewport');
  Object.assign(release.target, { inCanvas: true, editingTarget: false, canvasControl: false, canvasTool: 'pan', handToolPressed: true });
  release.viewport = { x: 0, y: 0, width: 500, height: 400 };
  r.events.push(release); r.trials[0].lastEventId = release.id;
  assert.equal(validateInputObservation(r).trials[0].cancelled, false);
  assert.equal(validateInputObservation(r).trials[0].operationSucceeded, true);
});

test('v2 missing, different-pointer, duplicate or truncated terminal evidence remains unmeasured', () => {
  for (const mutate of [
    r => { r.events[2].type = 'pointercancel'; },
    r => { r.events[2].pointerId = 2; },
    r => { const extra = structuredClone(r.events[2]); extra.id = 'input-4'; extra.eventAt = 41; extra.capturedAt = 41.05; r.events.push(extra); r.trials[0].lastEventId = extra.id; },
    r => { r.buffers.events = { limit: 3, dropped: 1 }; },
    r => { r.trials[0].after.at = 30; },
  ]) {
    const r = handPanFixture(); mutate(r);
    const out = validateInputObservation(r).trials[0];
    assert.equal(out.panTerminal.status, 'unmeasured'); assert.equal(out.operationSucceeded, false);
  }
});

test('v1 Space pan remains readable without inventing v2 tool/terminal evidence', () => {
  const r = fixture(); r.trials[0].spec.operation = 'pan'; r.events[0].spaceHeld = true;
  r.trials[0].after = scene(50, 3, 10, 10, 1, 132, 60);
  const out = validateInputObservation(r).trials[0];
  assert.equal(out.operationSucceeded, true);
  assert.equal(out.panTerminal.status, 'unmeasured'); assert.equal(out.panTerminal.reason, 'unavailable-in-v1');
  assert.equal(out.publicDocumentContinuity.matched, null);
});
