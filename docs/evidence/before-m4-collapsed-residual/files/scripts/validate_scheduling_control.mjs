#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { dirname, isAbsolute, relative, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Offline checker. No control/observer, Studio or browser imports.
const TARGET_TYPES = new Set(['pointerdown', 'pointerup', 'click']);
const BUFFER_NAMES = ['frames', 'eventTiming', 'inputs', 'rafCallbackCosts', 'inputCallbackCosts', 'performanceCallbackCosts', 'environmentChanges'];
const MATCH_TOLERANCE_MS = 8;
const EPSILON_MS = .001;
const numeric = value => typeof value === 'number' && Number.isFinite(value);
const nonnegative = value => numeric(value) && value >= 0;
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const fail = message => { throw new Error(message); };
const rounded = value => Math.round(value * 1e6) / 1e6;
const sha = bytes => createHash('sha256').update(bytes).digest('hex');

function distribution(values) {
  if (!values.length) return { samples: 0, minMs: null, meanMs: null, p50Ms: null, p95Ms: null, p99Ms: null, maxMs: null, sumMs: null };
  const sorted = [...values].sort((a, b) => a - b);
  const quantile = p => rounded(sorted[Math.ceil(sorted.length * p) - 1]);
  const sum = values.reduce((a, b) => a + b, 0);
  return { samples: values.length, minMs: rounded(sorted[0]), meanMs: rounded(sum / values.length),
    p50Ms: quantile(.5), p95Ms: quantile(.95), p99Ms: quantile(.99), maxMs: rounded(sorted.at(-1)), sumMs: rounded(sum) };
}

export function validateSchedulingControl(receipt, { visibilityObservation = null } = {}) {
  if (!object(receipt) || receipt.schema !== 'archcanvas-scheduling-control/1') fail('Unsupported scheduling-control schema');
  const r = receipt;
  if (!nonnegative(r.startedAt) || !nonnegative(r.stoppedAt) || r.stoppedAt <= r.startedAt || !nonnegative(r.timeOrigin) ||
    typeof r.capturedAt !== 'string' || !numeric(Date.parse(r.capturedAt)) || typeof r.userAgent !== 'string' || !r.userAgent ||
    !object(r.viewport) || !['width', 'height', 'dpr'].every(k => numeric(r.viewport[k]) && r.viewport[k] > 0) ||
    !Number.isInteger(r.hardwareConcurrency) || r.hardwareConcurrency < 1 || typeof r.stopReason !== 'string' ||
    typeof r.eventTimingSupported !== 'boolean' || r.durationThresholdMs !== 16 || !object(r.truncated) ||
    !Array.isArray(r.limitations) || !r.limitations.every(v => typeof v === 'string')) fail('Invalid clock/environment contract');
  for (const key of BUFFER_NAMES) if (!Array.isArray(r[key]) || r[key].length > 10000) fail(`Invalid raw buffer: ${key}`);
  for (const [key, value] of Object.entries(r.truncated)) {
    if (!BUFFER_NAMES.includes(key) || typeof value !== 'boolean' || value && r[key].length !== 10000) fail('Invalid truncation accounting');
  }
  const truncatedBuffers = BUFFER_NAMES.filter(key => r.truncated[key] === true);
  const context = r.context;
  if (!object(context) || context.schema !== 'archcanvas-measurement-context/1' || typeof context.formalStudioUnmodified !== 'boolean') fail('Invalid context');
  for (const name of ['productionAssets', 'probeSources']) {
    if (!Array.isArray(context[name]) || !context[name].length) fail(`Missing context ${name}`);
    const paths = new Set();
    for (const entry of context[name]) {
      if (!object(entry) || typeof entry.path !== 'string' || !entry.path || isAbsolute(entry.path) || entry.path.split(/[\\/]/).includes('..') ||
        paths.has(entry.path) || !Number.isInteger(entry.bytes) || entry.bytes < 0 || typeof entry.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(entry.sha256)) fail('Invalid context file binding');
      paths.add(entry.path);
    }
  }
  const environmentFlag = flag => {
    if (!object(flag) || !nonnegative(flag.at) || flag.at < r.startedAt - EPSILON_MS || flag.at > r.stoppedAt + 8 ||
      !['visible', 'hidden'].includes(flag.visibility) || typeof flag.focused !== 'boolean') fail('Invalid document visibility/focus observation');
  };
  environmentFlag(r.beginEnvironment); environmentFlag(r.endEnvironment);
  let previousEnvironmentAt = r.beginEnvironment.at;
  for (const flag of r.environmentChanges) {
    environmentFlag(flag);
    if (flag.at < previousEnvironmentAt || flag.at > r.endEnvironment.at) fail('Unordered document environment changes');
    previousEnvironmentAt = flag.at;
  }
  if (r.endEnvironment.at < previousEnvironmentAt) fail('End environment precedes changes');
  let previousFrame = -Infinity;
  for (const at of r.frames) {
    // A rAF timestamp is a browser animation clock; it may slightly precede
    // performance.now() at session start. Exact-window exclusions are explicit.
    if (!nonnegative(at) || at <= previousFrame || at < r.startedAt - 8 || at > r.stoppedAt + 8) fail('Invalid or unordered rAF timestamp');
    previousFrame = at;
  }
  let previousInputAt = -Infinity, previousCapturedAt = -Infinity;
  for (const input of r.inputs) {
    if (!object(input) || !TARGET_TYPES.has(input.type) || !nonnegative(input.at) || !nonnegative(input.capturedAt) ||
      input.at < previousInputAt || input.capturedAt < previousCapturedAt || input.at > input.capturedAt + 8 ||
      input.capturedAt < r.startedAt || input.capturedAt > r.stoppedAt || typeof input.trusted !== 'boolean' ||
      !(input.targetId === null || typeof input.targetId === 'string')) fail('Invalid captured raw input');
    previousInputAt = input.at; previousCapturedAt = input.capturedAt;
  }
  for (const entry of r.eventTiming) {
    // PO delivery can contain entries that began before the start handler
    // installed the observer in that same task. Do not invent captured inputs.
    if (!object(entry) || typeof entry.name !== 'string' || !entry.name ||
      !['startTime', 'duration', 'processingStart', 'processingEnd'].every(k => nonnegative(entry[k])) ||
      entry.processingStart + EPSILON_MS < entry.startTime || entry.processingEnd + EPSILON_MS < entry.processingStart ||
      entry.startTime > r.stoppedAt + 8 || entry.processingEnd > r.stoppedAt + 8 || !Number.isInteger(entry.interactionId) || entry.interactionId < 0 ||
      !(entry.targetId === null || typeof entry.targetId === 'string')) fail('Invalid native EventTiming entry');
  }
  if (!r.eventTimingSupported && r.eventTiming.length) fail('Unsupported observer contains native entries');
  for (const key of ['rafCallbackCosts', 'inputCallbackCosts', 'performanceCallbackCosts']) if (!r[key].every(nonnegative)) fail(`Invalid callback costs: ${key}`);
  if (r.rafCallbackCosts.length !== r.frames.length || r.inputCallbackCosts.length !== r.inputs.length) fail('Callback cost/input/frame sample counts disagree');

  const intervals = r.frames.slice(1).map((at, index) => at - r.frames[index]);
  const intervalBins = { lte20Ms: 0, gt20Lte50Ms: 0, gt50Lte100Ms: 0, gt100Lte500Ms: 0, gt500Ms: 0 };
  for (const value of intervals) {
    const key = value <= 20 ? 'lte20Ms' : value <= 50 ? 'gt20Lte50Ms' : value <= 100 ? 'gt50Lte100Ms' : value <= 500 ? 'gt100Lte500Ms' : 'gt500Ms';
    intervalBins[key]++;
  }
  const windowDuration = r.stoppedAt - r.startedAt;
  if (windowDuration > 3_600_000) fail('Control window exceeds offline summary bound');
  const secondWindows = [];
  for (let index = 0; r.startedAt + index * 1000 < r.stoppedAt; index++) {
    const startAt = r.startedAt + index * 1000, endAt = Math.min(startAt + 1000, r.stoppedAt);
    secondWindows.push({ index, startAt, endAt, durationMs: rounded(endAt - startAt),
      completeOneSecondWindow: endAt === startAt + 1000,
      callbacks: r.frames.filter(at => at >= startAt && at < endAt).length });
  }
  const exactWindowFrames = r.frames.filter(at => at >= r.startedAt && at < r.stoppedAt);

  const eligibleInputs = r.inputs.map((input, index) => ({ input, index })).filter(({ input }) => input.trusted && input.targetId === 'target');
  const candidates = eligibleInputs.map(({ input }) => r.eventTiming.flatMap((entry, index) =>
    entry.interactionId > 0 && entry.targetId === 'target' && entry.name === input.type && Math.abs(entry.startTime - input.at) <= MATCH_TOLERANCE_MS ? [index] : []));
  const candidateUses = new Map();
  for (const indexes of candidates) for (const index of indexes) candidateUses.set(index, (candidateUses.get(index) ?? 0) + 1);
  const matches = eligibleInputs.map(({ input, index }, position) => {
    const available = candidates[position];
    const nativeIndex = available.length === 1 && candidateUses.get(available[0]) === 1 && !r.truncated.inputs && !r.truncated.eventTiming ? available[0] : null;
    const entry = nativeIndex === null ? null : r.eventTiming[nativeIndex];
    const missingReason = entry ? null : r.truncated.inputs ? 'raw-input-buffer-truncated' : r.truncated.eventTiming ? 'event-timing-buffer-truncated' :
      available.length > 1 || available.some(i => candidateUses.get(i) > 1) ? 'ambiguous-candidate-or-competing-raw-input' :
        'unavailable-below-threshold-detached-or-unobserved';
    return { rawInputIndex: index, type: input.type, targetId: input.targetId, trusted: true, inputAt: input.at, capturedAt: input.capturedAt,
      inputCaptureDelayMs: rounded(input.capturedAt - input.at), candidateNativeEntryIndexes: available,
      nativeEntryIndex: nativeIndex, nativeDurationMs: entry?.duration ?? null, interactionId: entry?.interactionId ?? null,
      nativeInputQueueMs: entry ? rounded(entry.processingStart - entry.startTime) : null,
      nativeProcessingMs: entry ? rounded(entry.processingEnd - entry.processingStart) : null, missingReason };
  });
  const interactions = new Map();
  for (const match of matches) if (match.interactionId !== null) interactions.set(match.interactionId, Math.max(interactions.get(match.interactionId) ?? 0, match.nativeDurationMs));
  const matchedIndexes = new Set(matches.flatMap(match => match.nativeEntryIndex === null ? [] : [match.nativeEntryIndex]));
  let externalVisibility = null;
  if (visibilityObservation !== null) {
    const v = visibilityObservation;
    if (!object(v) || v.schema !== 'archcanvas-cua-visibility-observation/1' || typeof v.capturedAt !== 'string' || !numeric(Date.parse(v.capturedAt)) ||
      typeof v.browserId !== 'string' || typeof v.attemptedSet !== 'boolean' || typeof v.before !== 'boolean' || typeof v.reportedAfter !== 'boolean' ||
      !Array.isArray(v.controlReceipts) || !v.controlReceipts.every(x => typeof x === 'string')) fail('Invalid external visibility observation');
    externalVisibility = { capturedAt: v.capturedAt, browserId: v.browserId, attemptedSet: v.attemptedSet,
      capabilityBefore: v.before, capabilityReportedAfter: v.reportedAfter, controlReceipts: v.controlReceipts,
      hostPresentation: 'unconfirmed', continuousSynchronizedTrace: false, scope: 'External capability result; not a calibrated or continuous host-presentation observation' };
  }
  const callbackCosts = Object.fromEntries(['rafCallbackCosts', 'inputCallbackCosts', 'performanceCallbackCosts'].map(key => [key,
    { ...distribution(r[key]), completeCapturedBuffer: !r.truncated[key] }]));
  return { schema: 'archcanvas-scheduling-control-validation/1', status: 'validated-offline-scheduling-control',
    humanCertified: false, studioPerformanceCertified: false, presentedFrameRateCertified: false, hostPresentationCertified: false,
    completeBuffers: truncatedBuffers.length === 0, truncatedBuffers, quantiles: 'nearest rank; no interpolation; milliseconds rounded to six decimals',
    environment: { timeOrigin: r.timeOrigin, capturedAt: r.capturedAt, userAgent: r.userAgent, viewport: r.viewport,
      hardwareConcurrency: r.hardwareConcurrency, beginDocument: r.beginEnvironment, documentChanges: r.environmentChanges,
      endDocument: r.endEnvironment, externalVisibility, hostPresentation: 'unconfirmed', resolvedFontEnvironment: null },
    receiptContext: context,
    frameCadence: { frameTimestampCount: r.frames.length, intervalDistribution: distribution(intervals), intervalBins,
      observationWindowMs: rounded(windowDuration), firstFrameDelayFromStartMs: r.frames.length ? rounded(r.frames[0] - r.startedAt) : null,
      lastFrameToStopMs: r.frames.length ? rounded(r.stoppedAt - r.frames.at(-1)) : null,
      callbackRateOverExactSessionWindowHz: !r.truncated.frames ? rounded(exactWindowFrames.length * 1000 / windowDuration) : null,
      intervalCadenceHz: !r.truncated.frames && intervals.length ? rounded(intervals.length * 1000 / (r.frames.at(-1) - r.frames[0])) : null,
      outsideExactSessionWindowCount: r.frames.length - exactWindowFrames.length, oneSecondWindows: secondWindows,
      gapsOver100Ms: intervals.flatMap((durationMs, index) => durationMs > 100 ? [{ frameIndexBefore: index, frameIndexAfter: index + 1,
        startAt: r.frames[index], endAt: r.frames[index + 1], durationMs: rounded(durationMs) }] : []),
      presentedFrameRateHz: null, estimatedMissedPresentedFrames: null, scope: 'Raw rAF callback timestamps; mixed scheduling cadence across the observed window, not displayed frames' },
    eventTiming: { supported: r.eventTimingSupported, durationThresholdMs: r.durationThresholdMs, durationQuantizationExpectedMs: 8,
      rawNativeEntries: r.eventTiming.length, entriesOnExpected8MsGrid: r.eventTiming.filter(e => Math.abs(e.duration / 8 - Math.round(e.duration / 8)) < EPSILON_MS).length,
      rawInputCount: r.inputs.length, eligibleCapturedTrustedTargetInputs: matches.length, matchedTargetInputs: matchedIndexes.size,
      excludedRawInputs: r.inputs.length - matches.length,
      excludedStartDiscreteNativeEntries: r.eventTiming.filter(e => e.targetId === 'start' && TARGET_TYPES.has(e.name)).length,
      capturedStartInputs: r.inputs.filter(e => e.targetId === 'start').length,
      nativeEntriesNotMatchedToEligibleTargetInput: r.eventTiming.length - matchedIndexes.size,
      matching: { targetId: 'target', types: [...TARGET_TYPES], trustedRawOnly: true, timeToleranceMs: MATCH_TOLERANCE_MS,
        rule: 'Same type/target/time; exactly one candidate and exactly one competing captured raw input. No greedy assignment; truncated raw/native buffers suppress matches.' },
      matches, matchedInteractions: [...interactions].map(([interactionId, maxMatchedDurationMs]) => ({ interactionId, maxMatchedDurationMs })),
      matchedInteractionDurationDistribution: distribution([...interactions.values()]),
      allCapturedEligibleInputsMatched: !r.truncated.inputs && !r.truncated.eventTiming && matches.length > 0 && matches.every(m => m.nativeEntryIndex !== null),
      overallPageInpMs: null, continuousInputToPaintMs: null, scope: 'Only uniquely matched captured trusted target subset; start-button PO records do not create raw inputs, and missing entries are unknown' },
    callbackSelfCost: { categories: callbackCosts,
      costScope: 'rAF/input samples end before their cost append; rAF excludes rescheduling. PO samples measure the consume loop. Browser delivery, target click handler, timer, rendering, and other work are excluded.',
      performanceCallbackSamplesAreNotEntryCount: true, zeroSamplesMayReflectClockResolution: true,
      wholeObserverOverheadMs: null, schedulingCauseEstablished: false },
    limitations: ['Agent-operated simple page, not a human task or Studio benchmark.',
      'rAF timestamps measure callbacks, not presented frames, sustained FPS, dropped frames or continuous input paint latency.',
      'The two control windows do not establish that viewport changes or a visibility request caused the scheduling pattern.',
      'Document visible/focused and an external capability return do not certify host presentation.',
      'EventTiming duration is rounded; missing, competing, unsupported or truncated matches remain null.',
      'Tiny measured callback sections do not establish total CPU cost or a scheduling cause.',
      'Context hashes bind declared files; a declaration of unchanged production is not a historical execution proof.'] };
}

async function currentBindings(context, root) {
  const entries = [];
  for (const category of ['productionAssets', 'probeSources']) for (const declared of context[category]) {
    let current = null, error = null;
    try { const raw = await readFile(resolve(root, declared.path)); current = { sha256: sha(raw), bytes: raw.length }; }
    catch (e) { error = e.code ?? String(e); }
    entries.push({ category, path: declared.path, declared: { sha256: declared.sha256, bytes: declared.bytes }, current,
      matchesCurrentFile: current !== null && current.sha256 === declared.sha256 && current.bytes === declared.bytes, error });
  }
  const source = path => entries.find(e => e.path === path)?.matchesCurrentFile ?? null;
  return { allDeclaredFilesMatchCurrent: entries.every(e => e.matchesCurrentFile),
    productionAssetsMatchCurrent: entries.filter(e => e.category === 'productionAssets').every(e => e.matchesCurrentFile),
    controlModuleMatchesCurrent: source('scripts/m4_input_support/control.mjs'), controlPageMatchesCurrent: source('scripts/m4_input_support/control.html'),
    harnessMatchesCurrent: source('scripts/m4_input_harness.py'), entries,
    scope: 'Current bytes compared with receipt declarations; control.mjs does not import the separate Studio input observer listed in context' };
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    const [receiptPath, ...options] = process.argv.slice(2);
    if (!receiptPath) fail('Usage: node scripts/validate_scheduling_control.mjs RECEIPT [--visibility RECEIPT] [--root FORMAL_ROOT]');
    let visibilityPath = null, root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
    for (let index = 0; index < options.length; index += 2) {
      if (!options[index + 1]) fail('Option requires a value');
      if (options[index] === '--visibility' && visibilityPath === null) visibilityPath = options[index + 1];
      else if (options[index] === '--root') root = resolve(options[index + 1]);
      else fail(`Unknown or duplicate option: ${options[index]}`);
    }
    const raw = await readFile(receiptPath), visibilityRaw = visibilityPath === null ? null : await readFile(visibilityPath);
    const report = validateSchedulingControl(JSON.parse(raw), { visibilityObservation: visibilityRaw === null ? null : JSON.parse(visibilityRaw) });
    report.inputBinding = { path: relative(root, resolve(receiptPath)), sha256: sha(raw), bytes: raw.length };
    report.visibilityInputBinding = visibilityRaw === null ? null : { path: relative(root, resolve(visibilityPath)), sha256: sha(visibilityRaw), bytes: visibilityRaw.length };
    const validatorRaw = await readFile(fileURLToPath(import.meta.url));
    report.validatorBinding = { path: relative(root, fileURLToPath(import.meta.url)), sha256: sha(validatorRaw), bytes: validatorRaw.length };
    report.validationRuntime = { validatedAt: new Date().toISOString(), node: process.version, executablePath: process.execPath };
    report.contextCurrentFileComparison = await currentBindings(report.receiptContext, root);
    console.log(JSON.stringify(report, null, 2));
  } catch (error) { console.error(error.message); process.exitCode = 1; }
}
