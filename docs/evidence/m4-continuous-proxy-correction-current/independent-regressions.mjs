// Independent hand-authored browser facts. No observer, product scene,
// signature helper, or implementation-generated expected values are imported.
import test from 'node:test';
import assert from 'node:assert/strict';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const validatorUrl = process.env.ARCHCANVAS_PROXY_VALIDATOR
  ? pathToFileURL(resolve(process.env.ARCHCANVAS_PROXY_VALIDATOR)).href
  : new URL('../../../scripts/validate_input_observation.mjs', import.meta.url).href;
const { validateInputObservation: validate } = await import(validatorUrl);
const wrapperUrl = process.env.ARCHCANVAS_PROXY_WRAPPER
  ? pathToFileURL(resolve(process.env.ARCHCANVAS_PROXY_WRAPPER)).href : null;
const wrap = wrapperUrl ? (await import(wrapperUrl)).validateContinuousObservation : null;
const A = 'node:A', P = 'node:P', U = 'node:U';
const source = 'a'.repeat(64), ir = 'b'.repeat(64);
const viewport = { x: 0, y: 0, width: 500, height: 400 };
const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-9, `${actual} != ${expected}`);

// Three literal bodies with known affine screen coordinates. The only fixture
// transforms are positive uniform scales and translations; no production math.
function scene(at, revision = 3, { ax = 10, ay = 10, ux = 200, scale = 1, tx = 100, ty = 40, full = true } = {}) {
  const matrix = { a: scale, b: 0, c: 0, d: scale, e: tx, f: ty };
  const objects = {};
  for (const [id, x, y] of [[A, ax, ay], [P, 60, 60], [U, ux, 150]]) {
    const screen = { x: x * scale + tx, y: y * scale + ty, width: 20 * scale, height: 20 * scale };
    objects[id] = { canvas: { x, y, width: 20, height: 20 }, screen, screenMatrix: { ...matrix }, label: id, canonicalId: id,
      intersectsViewport: screen.x < 500 && screen.x + screen.width > 0 && screen.y < 400 && screen.y + screen.height > 0,
      fullyInsideViewport: screen.x >= 0 && screen.y >= 0 && screen.x + screen.width <= 500 && screen.y + screen.height <= 400 };
  }
  if (!full) delete objects[U];
  const g = { at, documentId: 'canvas-independent-three-bodies', revision, camera: { matrix, cssTransform: 'literal-fixture' },
    viewport: { ...viewport }, frameRect: null, objects, canvasTool: 'select', handToolPressed: false };
  if (full) Object.assign(g, { sourceDigest: source, irDigest: ir, visibleIds: [A, P, U], expandedIds: [], pinnedIds: [P],
    svgMarkup: `<svg data-literal-a="${ax},${ay}" data-literal-u="${ux}"/>`, selectionMarkup: [] });
  return g;
}
function input(id, type, at, { trialId = 'trial-1', trusted = true, kind = type === 'pointerdown' ? 'node' : 'viewport' } = {}) {
  return { id, type, eventAt: at, capturedAt: at + .05, trusted, trialId,
    target: { token: type === 'pointerdown' ? 'control-A' : 'viewport-control', nodeId: kind === 'node' ? A : null,
      kind, action: null, canvasTool: 'select', handToolPressed: false, inCanvas: true, editingTarget: false, canvasControl: false },
    viewport: { ...viewport }, pointerId: 1, pointerType: 'mouse', button: 0, buttons: type === 'pointerup' ? 0 : 1,
    x: type === 'pointerdown' ? 110 : type === 'pointerup' ? 142 : 126, y: type === 'pointerdown' ? 50 : type === 'pointerup' ? 70 : 60,
    key: null, code: null, ctrl: false, meta: false, shift: false, spaceHeld: false, deltaX: null, deltaY: null, deltaMode: null };
}
function fixture(version = 2) {
  return { schemaVersion: version, protocol: `archcanvas-input-observation/${version}`, label: 'independent partial frame counterexample',
    measurement: { mode: 'full', runtimeAccess: 'DOM-only', coordinateSpace: version === 2 ? 'window-client-css-pixels' : 'iframe-client-css-pixels',
      latency: 'matched-discrete-event-timing-only', continuousInput: 'observed-geometry-proxy-not-paint',
      frames: 'raf-callback-cadence-not-presented-frames', durationThresholdMs: 16, durationQuantizationMs: 8,
      ...(version === 2 ? { panTrigger: 'public-tool-space-middle/1', panTerminal: 'same-pointer-up-and-viewport-relative-camera/1',
        documentContinuity: 'public-svg-and-frontier-not-hidden-document/1' } : {}) },
    environment: { timeOrigin: 1_000_000, isIframe: false, viewport: { width: 500, height: 400, devicePixelRatio: 1 },
      scripts: ['http://localhost/independent.js'], supported: { eventTimingObserved: true, longTasksObserved: true } },
    startedAt: 0, stoppedAt: 100, bindingAtStart: scene(1),
    trials: [{ id: 'trial-1', spec: { operation: 'drag', targetIds: [A], anchorIds: [], pinnedIds: [P] },
      armedAt: 2, status: 'finished', before: scene(10.1), after: scene(50, 4, { ax: 42, ay: 30 }),
      firstEventId: 'down', lastEventId: 'up', finishedAt: 51 }],
    events: [input('down', 'pointerdown', 10), input('move', 'pointermove', 20), input('up', 'pointerup', 40)],
    frames: [{ at: 5, observedAt: 5.2, trialId: null, geometry: null },
      { at: 21, observedAt: 21.2, trialId: 'trial-1', geometry: scene(21.1, 3, { full: false }) },
      { at: 45, observedAt: 45.2, trialId: 'trial-1', geometry: scene(45.1, 4, { ax: 26, ay: 20, full: false }) },
      { at: 80, observedAt: 80.2, trialId: null, geometry: null }],
    eventTiming: [{ name: 'pointerdown', startAt: 10, durationMs: 64, processingStart: 10.15, processingEnd: 11,
      interactionId: 7, targetToken: 'control-A', targetNodeId: A },
      { name: 'pointerup', startAt: 40, durationMs: 32, processingStart: 40.15, processingEnd: 41,
        interactionId: 7, targetToken: 'viewport-control', targetNodeId: null }],
    longTasks: [], visibility: [{ at: 0, state: 'visible', hasFocus: true, topHasFocus: true }],
    overhead: { sceneReads: [], inputCallbacks: [], frameCallbacks: [], performanceCallbacks: [] }, buffers: {}, errors: [] };
}
const trial = r => validate(r).trials[0];
const proxy = t => t.continuousProxies[0];
const unchangedFrames = r => { r.frames[2].geometry = scene(45.1, 3, { full: false }); };
function wheelFixture(version, empty = false) {
  const r = fixture(version), t = r.trials[0];
  t.spec = { operation: 'zoom', targetIds: [], anchorIds: empty ? [] : [A], pinnedIds: empty ? [] : [P] };
  t.after = scene(50, 3, { scale: 2 });
  const e = input('wheel', 'wheel', 20); Object.assign(e, { deltaX: 0, deltaY: -120, deltaMode: 0 });
  r.events = [e]; t.firstEventId = t.lastEventId = 'wheel'; r.eventTiming = [];
  r.frames[2].geometry = scene(45.1, 3, { scale: 2, full: false });
  if (empty) for (const f of r.frames) if (f.geometry) f.geometry.objects = {};
  return r;
}

for (const version of [1, 2]) {
  const label = `v${version}`;
  test(`${label}: smaller unchanged frame object set invents no visual change`, () => {
    const r = fixture(version); unchangedFrames(r); const t = trial(r);
    assert.equal(proxy(t).inputToObservedChangeProxyMs, null);
    assert.equal(proxy(t).missingReason, 'no-later-observed-change');
    assert.deepEqual(t.continuousObjectIds, [A, P]);
    assert.deepEqual(t.continuousCoverage, { eligibleInputs: 1, measuredInputs: 0, unmeasuredInputs: 1, measuredSubsetP95Ms: null });
  });
  test(`${label}: delayed actual frame is chosen instead of first partial frame`, () => {
    const r = fixture(version), result = validate(r), t = result.trials[0];
    near(proxy(t).inputToObservedChangeProxyMs, 25.2);
    near(proxy(t).observedAt, 45.2);
    assert.deepEqual(proxy(t).changeKinds, ['revision', 'objects']);
    assert.equal(t.operationSucceeded, true); assert.equal(t.continuousCoverageComplete, true);
    assert.equal(proxy(t).causalInputIdentified, false); assert.equal(proxy(t).presentedPaintCertified, false);
    assert.equal(result.latency.matchedDiscreteInputs, 2); assert.equal(result.latency.matchedInteractions, 1);
    assert.equal(result.latency.matchedInteractionP95Ms, 64);
    assert.equal(result.humanCertified, false); assert.equal(result.presentedDragPaintCertified, false);
  });
  test(`${label}: object/property insertion order has no timing meaning`, () => {
    const r = fixture(version), g = r.frames[1].geometry;
    g.objects = { [P]: g.objects[P], [A]: g.objects[A] };
    g.camera.matrix = { f: 40, e: 100, d: 1, c: 0, b: 0, a: 1 };
    g.objects[A].canvas = { height: 20, width: 20, y: 10, x: 10 };
    g.objects[P].screen = { height: 20, width: 20, y: 100, x: 160 };
    near(proxy(trial(r)).inputToObservedChangeProxyMs, 25.2);
  });
  test(`${label}: every declared role requires an own object property`, () => {
    for (const id of [A, P, U]) {
      const r = fixture(version); r.trials[0].spec.anchorIds = [U];
      for (const f of r.frames) if (f.geometry) f.geometry.objects[U] = scene(1).objects[U];
      delete r.frames[1].geometry.objects[id];
      assert.throws(() => validate(r), /coverage missing/i);
    }
  });
  test(`${label}: null frame target or pin gap makes continuous evidence unmeasured`, () => {
    for (const id of [A, P]) {
      const r = fixture(version); r.frames[1].geometry.objects[id] = null; const t = trial(r);
      assert.equal(proxy(t).inputToObservedChangeProxyMs, null);
      assert.equal(proxy(t).missingReason, 'required-object-unavailable');
      assert.equal(t.continuousCoverageComplete, false); assert.equal(t.continuousObservationScope.objectCoverage, false);
      assert.equal(t.continuousCoverage.measuredInputs, 0);
    }
  });
  test(`${label}: unavailable requested drag target at either boundary is rejected`, () => {
    for (const where of ['before', 'after']) {
      const r = fixture(version); r.trials[0][where].objects[A] = null;
      assert.throws(() => validate(r), /Drag target geometry unavailable/);
    }
  });
  test(`${label}: null boundary pin is not measured as zero displacement`, () => {
    const r = fixture(version); r.trials[0].after.objects[P] = null; const t = trial(r);
    assert.equal(t.protectedObjects[0].canvas, null); assert.equal(t.protectedObjects[0].screen, null);
    assert.equal(t.protectedObjects[0].screenMeasured, false);
    assert.equal(proxy(t).inputToObservedChangeProxyMs, null); assert.equal(t.continuousCoverageComplete, false);
  });
  test(`${label}: wrong frame document or canonical binding is rejected`, () => {
    const doc = fixture(version); doc.frames[1].geometry.documentId = 'different-document';
    assert.throws(() => validate(doc), /bound window/);
    const canonical = fixture(version); canonical.frames[1].geometry.objects[A].canonicalId = 'wrong-canonical';
    assert.throws(() => validate(canonical), /canonical object identity/);
  });
  test(`${label}: available source/IR drift is rejected without inventing frame digests`, () => {
    for (const key of ['sourceDigest', 'irDigest']) {
      const boundary = fixture(version); boundary.trials[0].after[key] = 'c'.repeat(64);
      assert.throws(() => validate(boundary), /Source\/IR changed/);
      const frame = fixture(version); frame.frames[1].geometry[key] = 'c'.repeat(64);
      assert.throws(() => validate(frame), /available frame binding/);
    }
    const plain = fixture(version), before = JSON.stringify(plain); const t = trial(plain);
    assert.equal(t.continuousObservationScope.sourceIr, 'before-after-boundaries');
    assert.equal(t.continuousObservationScope.framesWithSourceDigest, 0);
    assert.equal(t.continuousObservationScope.framesWithIrDigest, 0);
    assert.equal(JSON.stringify(plain), before, 'validator does not mutate/invent raw fields');
  });
  test(`${label}: input/frame truncation or observer error suppresses first-change proxies`, () => {
    for (const cause of ['events', 'frames', 'error']) {
      const r = fixture(version);
      if (cause === 'error') r.errors.push({ at: 22, phase: 'frame', error: 'literal received capture failure' });
      else r.buffers[cause] = { limit: r[cause].length, dropped: 1 };
      const result = validate(r), t = result.trials[0];
      assert.equal(proxy(t).inputToObservedChangeProxyMs, null);
      assert.equal(proxy(t).missingReason, 'incomplete-capture');
      assert.equal(t.continuousCoverageComplete, false); assert.equal(result.continuousInputSummary.completeCapture, false);
    }
  });
  test(`${label}: wheel camera change preserves world geometry and stays a DOM proxy`, () => {
    const r = wheelFixture(version), result = validate(r), t = result.trials[0];
    near(proxy(t).inputToObservedChangeProxyMs, 25.2);
    assert.equal(t.operationSucceeded, true); assert.equal(t.revisionDelta, 0);
    assert.equal(t.cameraChanged, true); assert.equal(t.scaleChanged, true);
    assert.equal(t.changes[A].canvas.distancePx, 0); assert.equal(t.changes[P].canvas.distancePx, 0);
    assert.deepEqual(proxy(t).changeKinds, ['camera', 'objects']);
    assert.equal(result.latency.matchedDiscreteInputs, 0); assert.equal(proxy(t).presentedPaintCertified, false);
  });
  test(`${label}: revision-only match cannot be labelled body movement`, () => {
    const r = fixture(version); r.frames[2].geometry = scene(45.1, 4, { full: false }); r.trials[0].after = scene(50, 4);
    const t = trial(r); near(proxy(t).inputToObservedChangeProxyMs, 25.2);
    assert.deepEqual(proxy(t).changeKinds, ['revision']); assert.equal(t.changes[A].canvas.distancePx, 0);
    assert.equal(t.operationSucceeded, false);
  });
  test(`${label}: unrelated full-boundary change is retained without subset proxy invention`, () => {
    const r = fixture(version); unchangedFrames(r);
    r.trials[0].spec.operation = 'undo'; r.events[0].target.action = 'undo';
    r.trials[0].after = scene(50, 4, { ux: 210 });
    const t = trial(r);
    assert.equal(proxy(t).inputToObservedChangeProxyMs, null);
    assert.equal(t.operationSucceeded, true, 'whole-boundary undo shape comparison still sees unrelated U');
    assert.equal(r.trials[0].after.objects[U].canvas.x - r.trials[0].before.objects[U].canvas.x, 10);
    assert.equal(t.changes[A].canvas.distancePx, 0);
    if (version === 2) assert.equal(t.publicDocumentContinuity.matched, false);
  });
  test(`${label}: successful target drag does not certify unrelated-body invariance`, () => {
    const r = fixture(version); r.trials[0].after = scene(50, 4, { ax: 42, ay: 30, ux: 210 }); const t = trial(r);
    near(proxy(t).inputToObservedChangeProxyMs, 25.2); assert.equal(t.operationSucceeded, true);
    assert.equal(t.changes[A].canvas.x, 32);
    assert.equal(r.trials[0].after.objects[U].canvas.x - r.trials[0].before.objects[U].canvas.x, 10);
    assert.deepEqual(t.continuousObjectIds, [A, P]);
  });
  test(`${label}: no-input wrong-tool attempt cannot borrow outside movement`, () => {
    const r = fixture(version), t = r.trials[0]; t.status = 'no-input'; t.before = null;
    for (const e of r.events) { e.trialId = null; e.target.canvasTool = 'pan'; e.target.handToolPressed = true; }
    for (const f of r.frames) { f.trialId = null; f.geometry = null; }
    t.after = scene(50, 3, { tx: 132, ty: 60 }); t.after.canvasTool = 'pan'; t.after.handToolPressed = true;
    const result = validate(r), out = result.trials[0];
    assert.equal(out.operationSucceeded, false); assert.equal(out.observed, false);
    assert.equal((out.continuousProxies ?? []).length, 0);
    assert.equal(result.continuousInputSummary.assignedEligibleInputs, 0);
    assert.equal(result.continuousInputSummary.retainedOutsideTrialInputs, 1);
  });
  test(`${label}: shared frame, missing response and outside inputs keep separate denominators`, () => {
    const r = fixture(version), late = input('late-wheel', 'wheel', 46); Object.assign(late, { deltaX: 0, deltaY: 10, deltaMode: 0 });
    r.events = [r.events[0], input('outside', 'pointermove', 15, { trialId: null }), r.events[1],
      input('move-2', 'pointermove', 30), r.events[2], late]; r.trials[0].lastEventId = 'late-wheel';
    const result = validate(r), t = result.trials[0], [first, second, missing] = t.continuousProxies;
    near(first.inputToObservedChangeProxyMs, 25.2); near(second.inputToObservedChangeProxyMs, 15.2);
    assert.equal(first.observedAt, second.observedAt); assert.equal(missing.inputToObservedChangeProxyMs, null);
    assert.equal(missing.missingReason, 'no-later-observed-change');
    assert.equal(t.continuousCoverage.eligibleInputs, 3); assert.equal(t.continuousCoverage.measuredInputs, 2);
    assert.equal(t.continuousCoverage.unmeasuredInputs, 1); near(t.continuousCoverage.measuredSubsetP95Ms, 25.2);
    assert.equal(result.continuousInputSummary.retainedTrustedContinuousInputs, 4);
    assert.equal(result.continuousInputSummary.assignedEligibleInputs, 3);
    assert.equal(result.continuousInputSummary.retainedOutsideTrialInputs, 1);
    assert.equal(first.causalInputIdentified, false);
  });
  test(`${label}: empty declared set reports only camera/revision coverage`, () => {
    const t = trial(wheelFixture(version, true)); near(proxy(t).inputToObservedChangeProxyMs, 25.2);
    assert.deepEqual(t.continuousObjectIds, []); assert.equal(t.continuousObservationScope.state, 'camera-revision-only');
    assert.equal(t.continuousObservationScope.objectCoverage, false); assert.deepEqual(proxy(t).changeKinds, ['camera']);
  });
  test(`${label}: untrusted continuous inputs cannot enter the measured subset`, () => {
    const r = fixture(version); r.events[1].trusted = false; const result = validate(r), t = result.trials[0];
    assert.equal(t.continuousProxies.length, 0); assert.equal(t.continuousCoverage.eligibleInputs, 0);
    assert.equal(result.continuousInputSummary.retainedTrustedContinuousInputs, 0);
  });
  test(`${label}: missing terminal input cannot become successful because a proxy exists`, () => {
    const r = fixture(version); r.events.pop(); r.trials[0].lastEventId = 'move'; r.eventTiming.pop();
    const t = trial(r); near(proxy(t).inputToObservedChangeProxyMs, 25.2); assert.equal(t.operationSucceeded, false);
  });
}

function responsiveFixture({ failed = 0 } = {}) {
  const r = fixture(2);
  r.extension = 'archcanvas-responsive-continuous-ledger/1';
  r.bindingAtEnd = scene(55, 4, { ax: 42, ay: 30 });
  r.stopProtocol = { requestedDrainMs: 20, captureEndedAt: 60, drainEndedAt: 80, unformedEntriesGuaranteed: false };
  r.postCaptureTiming = []; r.excludedBeforeCaptureTiming = [];
  const row = (retained, failures = 0) => ({ observed: retained + failures, trusted: retained + failures, untrusted: 0,
    retained, dropped: 0, failed: failures, coalescedPointerSamples: 0 });
  r.inputDenominator = { ...row(3, failed), rawEventCompleteness: failed === 0,
    byType: { pointerdown: row(1), pointermove: row(1, failed), pointerup: row(1) } };
  r.buffers.events = { limit: 3, seen: 3, dropped: 0 };
  r.buffers.frames = { limit: 4, seen: 4, dropped: 0 };
  for (const e of r.eventTiming) Object.assign(e, { membership: 'capture', deliveredAt: 75, deliveryPhase: 'drain' });
  const full = [r.bindingAtStart, r.bindingAtEnd, r.trials[0].before, r.trials[0].after];
  for (const g of full) g.coverage = { renderedCanonicalBodies: 3, measuredBodies: 3, viewportIntersectingBodies: 3, fullyInsideBodies: 3 };
  return r;
}
test('responsive base: self-consistent failed received input suppresses continuous proxies', () => {
  const result = validate(responsiveFixture({ failed: 1 })), t = result.trials[0];
  assert.equal(proxy(t).inputToObservedChangeProxyMs, null); assert.equal(proxy(t).missingReason, 'incomplete-capture');
  assert.equal(result.continuousInputSummary.completeCapture, false);
});
test('responsive wrapper: valid complete ledger preserves literal proxy and limits', { skip: !wrap }, () => {
  const result = wrap(responsiveFixture()); near(proxy(result.base.trials[0]).inputToObservedChangeProxyMs, 25.2);
  assert.equal(result.rawEventCompleteness, true); assert.equal(result.continuousCaptureComplete, true);
  assert.equal(result.presentedFps, null); assert.equal(result.continuousInputToPaintMs, null);
  assert.equal(result.performanceGatePassed, false); assert.equal(result.bindingContinuity.protectedPins[0].canvasExact, true);
});
test('responsive wrapper: failed input remains incomplete despite retained rows matching', { skip: !wrap }, () => {
  const result = wrap(responsiveFixture({ failed: 1 })); assert.equal(result.rawEventCompleteness, false);
  assert.equal(result.continuousCaptureComplete, false); assert.equal(proxy(result.base.trials[0]).inputToObservedChangeProxyMs, null);
});
test('responsive wrapper: false completeness and type/buffer totals are rejected', { skip: !wrap }, () => {
  const overclaim = responsiveFixture({ failed: 1 }); overclaim.inputDenominator.rawEventCompleteness = true;
  assert.throws(() => wrap(overclaim), /completeness overclaimed/);
  const type = responsiveFixture(); type.inputDenominator.byType.pointermove.trusted = 2;
  assert.throws(() => wrap(type), /type totals|per-type/);
  const seen = responsiveFixture(); seen.buffers.events.seen = 4;
  assert.throws(() => wrap(seen), /buffer ledger/);
});
test('responsive wrapper: missing session-end pin has null invariance, not false zero', { skip: !wrap }, () => {
  const r = responsiveFixture(); r.bindingAtEnd.objects[P] = null;
  r.bindingAtEnd.coverage = { renderedCanonicalBodies: 3, measuredBodies: 2, viewportIntersectingBodies: 2, fullyInsideBodies: 2 };
  const p = wrap(r).bindingContinuity.protectedPins[0]; assert.equal(p.measured, false); assert.equal(p.canvasExact, null);
});
test('responsive wrapper: source and geometry coverage claims remain independently bound', { skip: !wrap }, () => {
  const drift = responsiveFixture(); drift.bindingAtEnd.sourceDigest = 'c'.repeat(64);
  assert.throws(() => wrap(drift), /document\/source\/IR binding/);
  const coverage = responsiveFixture(); coverage.bindingAtEnd.coverage.fullyInsideBodies = 2;
  assert.throws(() => wrap(coverage), /body coverage/);
});
