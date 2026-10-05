import assert from 'node:assert/strict';
import test from 'node:test';
import { validateSchedulingControl } from '../scripts/validate_scheduling_control.mjs';

// Synthetic diagnostic fixtures only; never researcher/measurement evidence.
const binding = path => ({ path, bytes: 1, sha256: 'a'.repeat(64) });
function fixture() {
  return { schema: 'archcanvas-scheduling-control/1', startedAt: 100, stoppedAt: 2100, timeOrigin: 100000,
    capturedAt: '2026-10-04T00:00:00.000Z', userAgent: 'synthetic-test-agent', viewport: { width: 800, height: 600, dpr: 1 },
    hardwareConcurrency: 1, stopReason: 'test', eventTimingSupported: true, durationThresholdMs: 16, truncated: {}, limitations: [],
    context: { schema: 'archcanvas-measurement-context/1', formalStudioUnmodified: true,
      productionAssets: [binding('studio/dist/test.js')], probeSources: [binding('scripts/m4_input_support/control.mjs')] },
    beginEnvironment: { at: 100, visibility: 'visible', focused: true }, endEnvironment: { at: 2100, visibility: 'visible', focused: true },
    environmentChanges: [], frames: [110, 120, 1110, 1120], rafCallbackCosts: [0, 0, .1, 0],
    inputs: [{ type: 'click', at: 150, capturedAt: 151, trusted: true, targetId: 'target' }], inputCallbackCosts: [.1],
    eventTiming: [{ name: 'click', startTime: 150, duration: 32, processingStart: 151, processingEnd: 152, interactionId: 1, targetId: 'target' }],
    performanceCallbackCosts: [.1] };
}

test('full-window callback rate and interval cadence use distinct explicit denominators', () => {
  const v = validateSchedulingControl(fixture());
  assert.deepEqual(v.frameCadence.intervalDistribution, { samples: 3, minMs: 10, meanMs: 336.666667, p50Ms: 10, p95Ms: 990, p99Ms: 990, maxMs: 990, sumMs: 1010 });
  assert.equal(v.frameCadence.callbackRateOverExactSessionWindowHz, 2);
  assert.equal(v.frameCadence.intervalCadenceHz, 2.970297);
  assert.deepEqual(v.frameCadence.oneSecondWindows.map(w => w.callbacks), [2, 2]);
  assert.deepEqual(v.frameCadence.intervalBins, { lte20Ms: 2, gt20Lte50Ms: 0, gt50Lte100Ms: 0, gt100Lte500Ms: 0, gt500Ms: 1 });
  assert.equal(v.frameCadence.presentedFrameRateHz, null);
  assert.equal(v.frameCadence.estimatedMissedPresentedFrames, null);
});

test('start-button PO entries without captured inputs never inflate target matches', () => {
  const r = fixture();
  r.eventTiming.unshift({ name: 'click', startTime: 99, duration: 1000, processingStart: 99, processingEnd: 101, interactionId: 2, targetId: 'start' });
  const v = validateSchedulingControl(r).eventTiming;
  assert.equal(v.eligibleCapturedTrustedTargetInputs, 1);
  assert.equal(v.matchedTargetInputs, 1);
  assert.equal(v.excludedStartDiscreteNativeEntries, 1);
  assert.equal(v.capturedStartInputs, 0);
  assert.equal(v.matches[0].nativeDurationMs, 32);
});

test('unsupported or below-threshold absence stays null, never zero latency', () => {
  for (const supported of [true, false]) {
    const r = fixture(); r.eventTimingSupported = supported; r.eventTiming = [];
    const v = validateSchedulingControl(r).eventTiming;
    assert.equal(v.matchedTargetInputs, 0);
    assert.equal(v.matches[0].nativeDurationMs, null);
    assert.equal(v.matches[0].interactionId, null);
    assert.equal(v.matchedInteractionDurationDistribution.p95Ms, null);
    assert.equal(v.allCapturedEligibleInputsMatched, false);
  }
});

test('multiple candidate native entries remain ambiguous even when one is closer', () => {
  const r = fixture(); r.eventTiming.push({ ...r.eventTiming[0], startTime: 151, processingStart: 151, processingEnd: 152, duration: 40 });
  const v = validateSchedulingControl(r).eventTiming;
  assert.equal(v.matches[0].nativeDurationMs, null);
  assert.match(v.matches[0].missingReason, /ambiguous/);
});

test('one native entry competing with two raw inputs does not greedily match either', () => {
  const r = fixture(); r.inputs.push({ ...r.inputs[0], at: 155, capturedAt: 155 }); r.inputCallbackCosts.push(0);
  const v = validateSchedulingControl(r).eventTiming;
  assert.equal(v.matchedTargetInputs, 0);
  assert.ok(v.matches.every(m => m.nativeEntryIndex === null && m.nativeDurationMs === null && /competing/.test(m.missingReason)));
});

test('wrong target, event name, distant timestamp, zero interaction, and untrusted input cannot match', () => {
  for (const change of [{ targetId: 'start' }, { name: 'pointerup' }, { startTime: 170, processingStart: 170, processingEnd: 171 }, { interactionId: 0 }]) {
    const r = fixture(); Object.assign(r.eventTiming[0], change);
    assert.equal(validateSchedulingControl(r).eventTiming.matches[0].nativeDurationMs, null);
  }
  const r = fixture(); r.inputs[0].trusted = false;
  assert.equal(validateSchedulingControl(r).eventTiming.eligibleCapturedTrustedTargetInputs, 0);
});

test('positive interaction id groups matched pointer and click records as one observed subset', () => {
  const r = fixture();
  r.inputs = ['pointerdown', 'pointerup', 'click'].map(type => ({ type, at: 150, capturedAt: 151, trusted: true, targetId: 'target' }));
  r.eventTiming = r.inputs.map((input, i) => ({ name: input.type, startTime: 150, duration: 32 + i * 8, processingStart: 151, processingEnd: 152, interactionId: 3, targetId: 'target' }));
  r.inputCallbackCosts = [0, 0, 0];
  const v = validateSchedulingControl(r).eventTiming;
  assert.equal(v.matchedTargetInputs, 3);
  assert.deepEqual(v.matchedInteractions, [{ interactionId: 3, maxMatchedDurationMs: 48 }]);
  assert.equal(v.overallPageInpMs, null);
});

test('document visible/focused and a failed external request never certify host presentation', () => {
  const visibilityObservation = { schema: 'archcanvas-cua-visibility-observation/1', capturedAt: '2026-10-04T00:01:00Z',
    browserId: '2', attemptedSet: true, before: false, reportedAfter: false, controlReceipts: ['synthetic.json'] };
  const v = validateSchedulingControl(fixture(), { visibilityObservation });
  assert.equal(v.environment.beginDocument.visibility, 'visible');
  assert.equal(v.environment.externalVisibility.capabilityReportedAfter, false);
  assert.equal(v.environment.hostPresentation, 'unconfirmed');
  assert.equal(v.hostPresentationCertified, false);
  assert.equal(v.environment.resolvedFontEnvironment, null);
  assert.equal(validateSchedulingControl(fixture()).environment.externalVisibility, null);
});

test('partial end window is labelled and empty rAF/cost statistics remain unknown', () => {
  const r = fixture(); r.stoppedAt = 2350; r.endEnvironment.at = 2350;
  let v = validateSchedulingControl(r);
  assert.equal(v.frameCadence.oneSecondWindows.at(-1).durationMs, 250);
  assert.equal(v.frameCadence.oneSecondWindows.at(-1).completeOneSecondWindow, false);
  r.frames = []; r.rafCallbackCosts = []; r.performanceCallbackCosts = [];
  v = validateSchedulingControl(r);
  assert.equal(v.frameCadence.intervalDistribution.p95Ms, null);
  assert.equal(v.frameCadence.intervalCadenceHz, null);
  assert.equal(v.callbackSelfCost.categories.performanceCallbackCosts.p95Ms, null);
  assert.equal(v.callbackSelfCost.wholeObserverOverheadMs, null);
});

test('truncated native buffer suppresses uniqueness and does not invent a match', () => {
  const r = fixture();
  r.eventTiming = Array.from({ length: 10000 }, (_, index) => ({ ...r.eventTiming[0], targetId: index === 0 ? 'target' : 'other' }));
  r.truncated.eventTiming = true;
  const v = validateSchedulingControl(r);
  assert.equal(v.completeBuffers, false);
  assert.equal(v.eventTiming.matches[0].nativeDurationMs, null);
  assert.equal(v.eventTiming.matches[0].missingReason, 'event-timing-buffer-truncated');
});

test('inconsistent raw clocks, buffers and native processing order are rejected', () => {
  for (const mutation of [r => { r.frames[1] = r.frames[0]; }, r => { r.inputCallbackCosts = []; },
    r => { r.eventTiming[0].processingEnd = 140; }, r => { r.inputs[0].capturedAt = 99; },
    r => { r.truncated.inputs = true; }, r => { r.rafCallbackCosts[0] = -1; }]) {
    const r = fixture(); mutation(r); assert.throws(() => validateSchedulingControl(r));
  }
});
