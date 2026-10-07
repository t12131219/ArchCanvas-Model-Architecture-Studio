#!/usr/bin/env node
/** Audit-only frozen before version; no current source/build or browser mutation. */
import { readFile } from 'node:fs/promises';
import { joinNativeTrials, summarizeNativeTrials } from './before/studio/src/nativePerformance.ts';
import { validateNativePerformance } from './before/scripts/validate_native_performance.mjs';
const original = JSON.parse(await readFile(new URL('../m4-native-performance-stress-smoke.json', import.meta.url), 'utf8'));
const template = original.trials[0];
const event = { ...template.nativeEventTiming, startAt: 3, processingStart: 4, processingEnd: 5 };
const trialBase = { ...template, trusted: true, error: null };
const trials = [{ ...trialBase, eventAt: 0, capturedAt: 0 }, { ...trialBase, eventAt: 6, capturedAt: 6 }];
const joined = joinNativeTrials(trials, [event]);
const report = { ...original, trials: joined, snapshot: { ...original.snapshot, eventTiming: [event] }, summary: summarizeNativeTrials(joined) };
console.log(JSON.stringify({
  protocol: 'archcanvas-native-matching-frozen-before-reproduction/1',
  scope: 'Synthetic counterexample using frozen before source. Not a browser receipt.',
  independentExpectedMatching: [null, null],
  independentReason: 'The sole entry at 3 ms fits two same-target trials at 0 ms and 6 ms within ±8 ms; neither is bilateral unique.',
  actualProductMatching: joined.map(t => ({ eventAt: t.eventAt, matched: t.nativeEventTiming !== null, duration: t.nativeInputToNextPaintMs })),
  actualValidator: validateNativePerformance(report),
}, null, 2));
