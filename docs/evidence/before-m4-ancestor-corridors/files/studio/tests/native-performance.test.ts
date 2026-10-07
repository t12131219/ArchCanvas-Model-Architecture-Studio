import test from 'node:test';
import assert from 'node:assert/strict';
import { joinNativeTrials, summarizeNativeTrials } from '../src/nativePerformance.ts';
import type { NativeScene, NativeTrial } from '../src/nativePerformance.ts';
import type { EventTimingSample } from '../src/perf.ts';
// @ts-expect-error Independent Node receipt verifier has no browser dependency or declarations.
import { validateNativePerformance } from '../../scripts/validate_native_performance.mjs';

function scene(revision: number): NativeScene {
  return { documentId: 'sample', revision, sourceDigest: 'a'.repeat(64), irDigest: 'b'.repeat(64),
    visibleIds: ['target', 'pin'], expandedIds: revision > 1 ? ['target'] : [], pinnedIds: ['pin'], anchors: {
      target: { canvas: { x: 10, y: 20 }, screen: { x: 100, y: 200 } },
      pin: { canvas: { x: 100, y: 20 }, screen: { x: 200, y: 200 } },
    } };
}
function trial(overrides: Partial<NativeTrial> = {}): NativeTrial {
  return { eventName: 'click', eventAt: 100, capturedAt: 110, trusted: true, targetId: 'target', operation: 'expand',
    before: scene(1), after: scene(2), error: null, ...overrides };
}
function entry(overrides: Partial<EventTimingSample> = {}): EventTimingSample {
  return { name: 'click', targetCanonicalNodeId: 'target', startAt: 100, processingStart: 110, processingEnd: 120, durationMs: 32, interactionId: 7, ...overrides };
}

test('native timing remains independent of geometry and handler proxy; pin spaces differ', () => {
  const item = trial();
  item.after!.anchors.target.screen.x += 6;
  item.after!.anchors.pin.screen.x += 6; // camera/viewport shift is not a canvas mutation
  const joined = joinNativeTrials([item], [entry()]);
  assert.equal(joined[0].nativeInputToNextPaintMs, 32);
  assert.equal(joined[0].anchorScreenDisplacementPx, 6);
  assert.equal(joined[0].pins[0].canvasDisplacementPx, 0);
  assert.equal(joined[0].pins[0].screenDisplacementPx, 6);
  assert.equal(summarizeNativeTrials(joined).certification, 'pending-fixed-environment-and-review');
});

test('untrusted, unmatched, ambiguous and reused native entries cannot yield passing zero latency', () => {
  for (const entries of [[], [entry({ name: 'pointerdown' })], [entry({ startAt: 200 })],
    [entry({ interactionId: 0 })], [entry({ targetCanonicalNodeId: 'other' })], [entry({ targetCanonicalNodeId: null })], [entry(), entry()], [entry({ processingEnd: 90 })]]) {
    const joined = joinNativeTrials([trial()], entries);
    assert.equal(joined[0].nativeInputToNextPaintMs, null);
    assert.equal(summarizeNativeTrials(joined).nativeInputToNextPaintP95Ms, null);
  }
  assert.equal(joinNativeTrials([trial({ trusted: false })], [entry()])[0].nativeInputToNextPaintMs, null);
  const reused = joinNativeTrials([trial(), trial()], [entry()]);
  assert.equal(reused.filter(item => item.nativeInputToNextPaintMs !== null).length, 1);
});

test('stale source or concurrent revisions invalidate spatial and summary evidence; missing pins stay unmeasured', () => {
  for (const alteration of [ { revision: 4 }, { sourceDigest: 'c'.repeat(64) }, { irDigest: 'c'.repeat(64) }, { documentId: 'other' } ]) {
    const joined = joinNativeTrials([trial({ after: { ...scene(2), ...alteration } })], [entry()]);
    assert.equal(joined[0].bindingValid, false);
    assert.equal(joined[0].anchorScreenDisplacementPx, null);
    assert.equal(summarizeNativeTrials(joined).validSceneTrials, 0);
    assert.equal(summarizeNativeTrials(joined).nativeInputToNextPaintP95Ms, null);
  }
  const item = trial(); delete item.after!.anchors.pin;
  const summary = summarizeNativeTrials(joinNativeTrials([item], [entry()]));
  assert.equal(summary.measuredPinCount, 0); assert.equal(summary.unmeasuredPinCount, 1);
  assert.equal(summary.pinCanvasMaxPx, null);
});

test('independent native receipt checker rejects forged zero latency, anchor drift and stale source', () => {
  const item = trial(); item.after!.visibleIds.push('child');
  const trials = joinNativeTrials([item], [entry()]);
  const receipt = { schemaVersion: 1, protocol: 'archcanvas-native-performance/1',
    measurement: { latency: 'native-event-timing-to-next-paint', geometryBoundary: 'two-animation-frames-after-input', durationThresholdMs: 16, durationQuantizationMs: 8 },
    bindingAtStart: item.before, trials, summary: summarizeNativeTrials(trials), snapshot: { eventTiming: [entry()] },
    frames: { frameCount: 3, firstFrameAt: 10, lastFrameAt: 50, intervals: [20, 20], intervalP95Ms: 20, fps: 50 } };
  assert.equal(validateNativePerformance(receipt).status, 'validated-engineering-receipt');
  const forgedLatency = structuredClone(receipt); forgedLatency.trials[0].nativeInputToNextPaintMs = 0;
  assert.throws(() => validateNativePerformance(forgedLatency), /incorrectly matched/);
  const shiftedAnchor = structuredClone(receipt); shiftedAnchor.trials[0].after!.anchors.target.screen.x += 10;
  assert.throws(() => validateNativePerformance(shiftedAnchor), /Screen anchor/);
  const stale = structuredClone(receipt); stale.trials[0].after!.sourceDigest = 'c'.repeat(64);
  assert.throws(() => validateNativePerformance(stale), /binding claim/);
  const wrongPinSpace = structuredClone(receipt); wrongPinSpace.trials[0].after!.anchors.pin.canvas.x += 10;
  assert.throws(() => validateNativePerformance(wrongPinSpace), /Pin coordinate/);
  const missingFrames = structuredClone(receipt); missingFrames.frames.intervals.pop();
  assert.throws(() => validateNativePerformance(missingFrames), /Frame summary/);
  const wrongTarget = structuredClone(receipt); wrongTarget.trials[0].after!.expandedIds = ['other'];
  assert.throws(() => validateNativePerformance(wrongTarget), /Target expansion/);
  const joinedWrongTarget = joinNativeTrials([trial({ after: { ...scene(2), expandedIds: ['other'] } })], [entry()]);
  assert.equal(summarizeNativeTrials(joinedWrongTarget).validSceneTrials, 0);
  assert.equal(joinedWrongTarget[0].anchorScreenDisplacementPx, null);
});
