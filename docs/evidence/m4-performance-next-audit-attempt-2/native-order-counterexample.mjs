#!/usr/bin/env node
/** Read-only audit reproduction; does not edit the product or original receipts. */
import { readFile } from 'node:fs/promises';
import { joinNativeTrials, summarizeNativeTrials } from '../../../studio/src/nativePerformance.ts';
import { validateNativePerformance } from '../../../scripts/validate_native_performance.mjs';
const original = JSON.parse(await readFile(new URL('../m4-native-performance-stress-smoke.json', import.meta.url), 'utf8'));
const template = original.trials[0];
const event = { ...template.nativeEventTiming, startAt: 3, processingStart: 4, processingEnd: 5 };
const trialBase = { ...template, trusted: true, error: null };
const trials = [{ ...trialBase, eventAt: 0, capturedAt: 0 }, { ...trialBase, eventAt: 6, capturedAt: 6 }];
const joined = joinNativeTrials(trials, [event]);
const report = { ...original, trials: joined, snapshot: { ...original.snapshot, eventTiming: [event] }, summary: summarizeNativeTrials(joined) };
console.log(JSON.stringify({
  protocol: 'archcanvas-native-order-ambiguity-counterexample/1',
  scope: 'Synthetic audit-only receipt; not a measured browser sample and never counted as human or performance evidence.',
  independentExpectedMatching: [null, null],
  independentReason: 'The sole entry at 3 ms can explain both same-target/same-type trials at 0 ms and 6 ms within the 8 ms match window. Neither pair is bilateral unique.',
  actualProductMatching: joined.map(t => ({ eventAt: t.eventAt, matched: t.nativeEventTiming !== null, duration: t.nativeInputToNextPaintMs })),
  actualIndependentValidatorResult: validateNativePerformance(report),
  orderBiasReproduced: joined[0].nativeEventTiming !== null && joined[1].nativeEventTiming === null,
}, null, 2));
