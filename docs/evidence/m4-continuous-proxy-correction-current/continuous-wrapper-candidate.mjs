#!/usr/bin/env node
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { validateInputObservation } from './implementation-candidate.mjs';

// Validate the responsive observer's received-event ledger before accepting
// its DOM proxies. This checker neither imports nor runs the observer.
export function validateContinuousObservation(r) {
  const fail = message => { throw new Error(message); };
  const integer = v => Number.isInteger(v) && v >= 0;
  const finite = v => typeof v === 'number' && Number.isFinite(v);
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const d = r?.inputDenominator, stop = r?.stopProtocol;
  const counters = ['observed', 'trusted', 'untrusted', 'retained', 'dropped', 'failed', 'coalescedPointerSamples'];
  if (r?.extension !== 'archcanvas-responsive-continuous-ledger/1' || !d || !stop || !r.bindingAtEnd ||
    !Array.isArray(r.events) || !d.byType || typeof d.byType !== 'object' || Array.isArray(d.byType)) fail('Missing responsive continuous ledger');
  const accounting = b => b && counters.every(k => integer(b[k])) &&
    b.observed === b.trusted + b.untrusted && b.observed === b.retained + b.dropped + b.failed;
  if (!accounting(d) || d.retained !== r.events.length) fail('Received input accounting disagrees');
  const types = Object.entries(d.byType);
  for (const k of counters) if (types.reduce((n, [, b]) => n + (b?.[k] ?? NaN), 0) !== d[k]) fail('Input type totals disagree: ' + k);
  for (const [type, b] of types) {
    if (!accounting(b)) fail('Invalid per-type input ledger');
    const events = r.events.filter(e => e.type === type);
    if (events.length !== b.retained || events.filter(e => e.trusted).length > b.trusted ||
      events.filter(e => !e.trusted).length > b.untrusted) fail('Retained input type disagrees');
    if (!d.dropped && !d.failed && events.reduce((n, e) => n + (e.coalesced?.length ?? 0), 0) !== b.coalescedPointerSamples)
      fail('Coalesced samples disagree');
  }
  if (r.events.some(e => !Object.hasOwn(d.byType, e.type))) fail('Retained input missing from type ledger');
  const eventBuffer = r.buffers?.events;
  if ((!eventBuffer && (d.retained || d.dropped)) || eventBuffer &&
    (eventBuffer.seen !== d.retained + d.dropped || eventBuffer.dropped !== d.dropped)) fail('Event buffer ledger disagrees');
  const rawEventCompleteness = d.dropped === 0 && d.failed === 0;
  if (d.rawEventCompleteness !== rawEventCompleteness) fail('Raw event completeness overclaimed');
  if (!integer(stop.requestedDrainMs) || stop.requestedDrainMs > 5000 || !finite(stop.captureEndedAt) || !finite(stop.drainEndedAt) ||
    stop.captureEndedAt < r.startedAt || stop.drainEndedAt < stop.captureEndedAt || r.stoppedAt < stop.drainEndedAt ||
    stop.unformedEntriesGuaranteed !== false) fail('Invalid stop/drain protocol');
  if (r.events.some(e => e.capturedAt > stop.captureEndedAt)) fail('Post-capture input included');
  for (const e of r.eventTiming ?? []) if (e.membership !== 'capture' || e.startAt < r.startedAt || e.startAt > stop.captureEndedAt ||
    !finite(e.deliveredAt) || e.deliveredAt < e.startAt || !['capture', 'drain'].includes(e.deliveryPhase)) fail('Native timing capture membership disagrees');
  for (const e of r.postCaptureTiming ?? []) if (e.membership !== 'after-capture' || e.startAt <= stop.captureEndedAt)
    fail('Post-capture native timing membership disagrees');

  const base = validateInputObservation(r);
  const full = [r.bindingAtStart, r.bindingAtEnd, ...r.trials.flatMap(t => [t.before, t.after]).filter(Boolean)];
  const start = r.bindingAtStart, end = r.bindingAtEnd;
  for (const g of full) {
    if (g.documentId !== start.documentId || g.sourceDigest !== start.sourceDigest || g.irDigest !== start.irDigest)
      fail('Full-boundary document/source/IR binding disagrees');
    const c = g.coverage, objects = Object.values(g.objects).filter(Boolean);
    if (!c || c.renderedCanonicalBodies !== g.visibleIds.length || c.measuredBodies !== objects.length ||
      c.viewportIntersectingBodies !== objects.filter(o => o.intersectsViewport).length ||
      c.fullyInsideBodies !== objects.filter(o => o.fullyInsideViewport).length) fail('Full-boundary body coverage disagrees');
    for (const o of objects) {
      const v = g.viewport, b = o.screen;
      const inside = b.x >= v.x && b.y >= v.y && b.x + b.width <= v.x + v.width && b.y + b.height <= v.y + v.height;
      if (o.fullyInsideViewport !== inside) fail('Fully-inside body coverage disagrees');
    }
  }
  const protectedPins = start.pinnedIds.map(id => ({ id,
    measured: !!start.objects[id] && !!end.objects[id],
    canvasExact: start.objects[id] && end.objects[id] ? same(start.objects[id].canvas, end.objects[id].canvas) : null,
    before: start.objects[id] ?? null, after: end.objects[id] ?? null }));
  return { schema: 'archcanvas-continuous-engineering-validation/2', base,
    inputDenominator: d, rawEventCompleteness, continuousProxyDefinition: base.continuousProxyDefinition,
    continuousCaptureComplete: base.continuousInputSummary.completeCapture,
    captureDurationMs: stop.captureEndedAt - r.startedAt, drainDurationMs: stop.drainEndedAt - stop.captureEndedAt,
    bindingContinuity: { document: true, source: true, ir: true,
      visibleIds: same(start.visibleIds, end.visibleIds), expandedIds: same(start.expandedIds, end.expandedIds),
      pinnedIds: same(start.pinnedIds, end.pinnedIds), protectedPins },
    viewportCoverage: { atStart: start.coverage, atEnd: end.coverage },
    presentedFps: null, continuousInputToPaintMs: null, performanceGatePassed: false,
    limitation: 'Received declared-type event accounting and DOM state observations only; no causal input response, presented paint, legibility, fixed-environment comparison or human certification.' };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  console.log(JSON.stringify(validateContinuousObservation(JSON.parse(await readFile(process.argv[2], 'utf8'))), null, 2));
}
