#!/usr/bin/env node
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

// Independent receipt checker: no Studio geometry or matching implementation import.
export function validateNativePerformance(report) {
  const fail = message => { throw new Error(message); };
  const finite = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
  const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
  const p95 = values => values.length ? [...values].sort((a, b) => a - b)[Math.ceil(values.length * .95) - 1] : null;
  const delta = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const point = value => value && [value.x, value.y].every(item => typeof item === 'number' && Number.isFinite(item));
  const scene = value => {
    if (!value || !value.documentId || !Number.isInteger(value.revision) || value.revision < 0 || !hash(value.sourceDigest) || !hash(value.irDigest) ||
      !Array.isArray(value.visibleIds) || new Set(value.visibleIds).size !== value.visibleIds.length || !Array.isArray(value.expandedIds) || !Array.isArray(value.pinnedIds) || !value.anchors) fail('Invalid source-bound scene');
    for (const [id, anchor] of Object.entries(value.anchors)) if (!value.visibleIds.includes(id) || !point(anchor.screen) || !point(anchor.canvas)) fail('Invalid screen/canvas geometry');
  };
  if (report.schemaVersion !== 1 || report.protocol !== 'archcanvas-native-performance/1' ||
    report.measurement?.latency !== 'native-event-timing-to-next-paint' || report.measurement?.geometryBoundary !== 'two-animation-frames-after-input' ||
    report.measurement?.durationThresholdMs !== 16 || report.measurement?.durationQuantizationMs !== 8 || !Array.isArray(report.trials) || !Array.isArray(report.snapshot?.eventTiming)) fail('Unsupported native performance receipt');
  scene(report.bindingAtStart);
  const used = new Set(); const durations = [], anchors = [], pins = [];
  let validCount = 0, missingPins = 0, previousAt = -Infinity;
  for (const trial of report.trials) {
    scene(trial.before); if (trial.after) scene(trial.after);
    if (!['click', 'pointerdown'].includes(trial.eventName) || !['expand', 'collapse'].includes(trial.operation) ||
      typeof trial.trusted !== 'boolean' || !finite(trial.eventAt) || !finite(trial.capturedAt) || trial.eventAt < previousAt ||
      !trial.before.visibleIds.includes(trial.targetId)) fail('Invalid or unordered input trial');
    previousAt = trial.eventAt;
    const after = trial.after;
    const valid = !!after && after.documentId === trial.before.documentId && after.sourceDigest === trial.before.sourceDigest &&
      after.irDigest === trial.before.irDigest && after.revision === trial.before.revision + 1;
    if (trial.bindingValid !== valid) fail('Source/revision binding claim disagrees');
    const targetChanged = valid && trial.before.expandedIds.includes(trial.targetId) === (trial.operation === 'collapse') && after.expandedIds.includes(trial.targetId) === (trial.operation === 'expand');
    if (trial.targetChanged !== targetChanged) fail('Target expansion state claim disagrees');
    if (valid && targetChanged && !trial.error) {
      if (trial.operation === 'expand' && after.visibleIds.length <= trial.before.visibleIds.length ||
        trial.operation === 'collapse' && after.visibleIds.length >= trial.before.visibleIds.length) fail('Toggle did not change visible frontier');
      validCount++;
    }
    const candidates = report.snapshot.eventTiming.map((event, index) => ({ event, index })).filter(({ event, index }) =>
      !used.has(index) && trial.trusted && event.name === trial.eventName && event.targetCanonicalNodeId === trial.targetId && event.interactionId > 0 &&
      Math.abs(event.startAt - trial.eventAt) <= 8 && event.processingStart >= event.startAt && event.processingEnd >= event.processingStart && finite(event.durationMs));
    const matched = candidates.length === 1 ? candidates[0] : null;
    if (matched) used.add(matched.index);
    if (JSON.stringify(trial.nativeEventTiming) !== JSON.stringify(matched?.event ?? null) || trial.nativeInputToNextPaintMs !== (matched?.event.durationMs ?? null)) fail('Native event missing, ambiguous or incorrectly matched');
    const a = trial.before.anchors[trial.targetId], b = after?.anchors[trial.targetId];
    const expectedAnchor = targetChanged && a && b ? delta(a.screen, b.screen) : null;
    if (trial.anchorScreenDisplacementPx !== expectedAnchor) fail('Screen anchor summary disagrees');
    if (valid && targetChanged && !trial.error) {
      if (matched) durations.push(matched.event.durationMs);
      if (expectedAnchor !== null) anchors.push(expectedAnchor);
    }
    if (!Array.isArray(trial.pins) || trial.pins.length !== trial.before.pinnedIds.length) fail('Pin coverage missing');
    trial.before.pinnedIds.forEach((id, index) => {
      const pin = trial.pins[index], before = trial.before.anchors[id], next = after?.anchors[id];
      const measured = !!before && !!next;
      if (pin.id !== id || pin.measured !== measured || pin.canvasDisplacementPx !== (measured ? delta(before.canvas, next.canvas) : null) ||
        pin.screenDisplacementPx !== (measured ? delta(before.screen, next.screen) : null)) fail('Pin coordinate spaces or coverage disagree');
      if (valid && targetChanged && !trial.error) measured ? pins.push(pin.canvasDisplacementPx) : missingPins++;
    });
  }
  const expectedSummary = { capturedTrials: report.trials.length, validSceneTrials: validCount, matchedNativeTrials: durations.length,
    nativeInputToNextPaintP95Ms: p95(durations), anchorScreenMaxPx: anchors.length ? Math.max(...anchors) : null,
    measuredPinCount: pins.length, pinCanvasMaxPx: pins.length ? Math.max(...pins) : null,
    unmeasuredPinCount: missingPins, certification: 'pending-fixed-environment-and-review' };
  if (JSON.stringify(report.summary) !== JSON.stringify(expectedSummary)) fail('Native summary disagrees with raw trials');
  const frames = report.frames;
  if (!frames || !Array.isArray(frames.intervals) || !frames.intervals.every(finite) || frames.frameCount !== (frames.intervals.length ? frames.intervals.length + 1 : frames.firstFrameAt === null ? 0 : 1) ||
    frames.intervalP95Ms !== p95(frames.intervals) || frames.fps !== (frames.frameCount > 1 ? (frames.frameCount - 1) * 1000 / (frames.lastFrameAt - frames.firstFrameAt) : null)) fail('Frame summary disagrees');
  return { status: 'validated-engineering-receipt', ...expectedSummary, fps: frames.fps,
    limitation: 'Validation checks receipt consistency, not hardware/font lock, human participation or publication quality.' };
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  console.log(JSON.stringify(validateNativePerformance(JSON.parse(await readFile(process.argv[2], 'utf8'))), null, 2));
}
