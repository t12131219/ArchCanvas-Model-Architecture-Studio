import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
// Frozen independent v2 oracle; exact matching/terminal rules are unchanged.
import { validateInputObservation } from './inputs/06-validate_input_observation.mjs';

export function validateContinuousObservation(r) {
  const base=validateInputObservation(r);
  const fail=message=>{throw new Error(message);};
  const integer=v=>Number.isInteger(v)&&v>=0;
  const d=r.inputDenominator, stop=r.stopProtocol;
  if(r.extension!=='archcanvas-responsive-continuous-ledger/1'||!d||!stop||!r.bindingAtEnd)fail('Missing continuous extension');
  if(![d.observed,d.trusted,d.untrusted,d.retained,d.dropped,d.failed,d.coalescedPointerSamples].every(integer)||
     d.observed!==d.trusted+d.untrusted||d.observed!==d.retained+d.dropped+d.failed||d.retained!==r.events.length)fail('Total input ledger disagrees');
  const types=Object.entries(d.byType??{});
  if(types.reduce((n,[,b])=>n+b.observed,0)!==d.observed)fail('Input type total disagrees');
  const counters=['observed','trusted','untrusted','retained','dropped','failed','coalescedPointerSamples'];
  for(const key of counters)if(types.reduce((n,[,b])=>n+b[key],0)!==d[key])fail('Input type counters disagree: '+key);
  for(const [type,b]of types){
    if(!counters.every(k=>integer(b[k]))||b.observed!==b.trusted+b.untrusted||b.observed!==b.retained+b.dropped+b.failed)fail('Invalid input type ledger');
    const events=r.events.filter(e=>e.type===type);
    if(events.length!==b.retained||events.filter(e=>e.trusted).length>b.trusted||events.filter(e=>!e.trusted).length>b.untrusted)fail('Retained input type disagrees');
    if(!d.dropped&&!d.failed&&events.reduce((n,e)=>n+(e.coalesced?.length??0),0)!==b.coalescedPointerSamples)fail('Coalesced input denominator disagrees');
  }
  if(r.events.length&&!r.buffers.events||r.buffers.events&&(r.buffers.events.seen!==d.retained+d.dropped||r.buffers.events.dropped!==d.dropped))fail('Event buffer ledger disagrees');
  const complete=d.dropped===0&&d.failed===0;
  if(d.rawEventCompleteness!==complete)fail('Raw event completeness overclaimed');
  if(!Number.isInteger(stop.requestedDrainMs)||stop.requestedDrainMs<0||stop.requestedDrainMs>5000||
     !Number.isFinite(stop.captureEndedAt)||!Number.isFinite(stop.drainEndedAt)||
     stop.captureEndedAt<r.startedAt||stop.drainEndedAt<stop.captureEndedAt||r.stoppedAt<stop.drainEndedAt||stop.unformedEntriesGuaranteed!==false)fail('Stop protocol disagrees');
  if(r.events.some(e=>e.capturedAt>stop.captureEndedAt))fail('Post-capture event included');
  for(const e of r.eventTiming)if(e.membership!=='capture'||e.startAt<r.startedAt||e.startAt>stop.captureEndedAt||
      !Number.isFinite(e.deliveredAt)||e.deliveredAt<e.startAt||!['capture','drain'].includes(e.deliveryPhase))fail('Capture timing membership disagrees');
  for(const e of r.postCaptureTiming??[])if(e.membership!=='after-capture'||e.startAt<=stop.captureEndedAt)fail('Post-capture timing membership disagrees');
  const full=[r.bindingAtStart,r.bindingAtEnd,...r.trials.flatMap(t=>[t.before,t.after]).filter(Boolean)];
  for(const g of full){
    const coverage=g.coverage;
    if(!coverage||coverage.renderedCanonicalBodies!==g.visibleIds.length)fail('Missing viewport body coverage');
    const objects=Object.entries(g.objects).filter(([,o])=>o);
    const intersects=objects.filter(([,o])=>o.intersectsViewport).length;
    const fully=objects.filter(([,o])=>o.fullyInsideViewport).length;
    if(coverage.measuredBodies!==objects.length||coverage.viewportIntersectingBodies!==intersects||coverage.fullyInsideBodies!==fully)fail('Viewport body counts disagree');
    for(const [,o]of objects){const v=g.viewport,b=o.screen;const expected=b.x>=v.x&&b.y>=v.y&&b.x+b.width<=v.x+v.width&&b.y+b.height<=v.y+v.height;if(o.fullyInsideViewport!==expected)fail('Fully-inside viewport overclaimed');}
  }
  const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),a=r.bindingAtStart,b=r.bindingAtEnd;
  const protectedPins=a.pinnedIds.map(id=>({id,before:a.objects[id]??null,after:b.objects[id]??null,
    measured:!!a.objects[id]&&!!b.objects[id],canvasExact:!!a.objects[id]&&!!b.objects[id]&&same(a.objects[id].canvas,b.objects[id].canvas)}));
  return {schema:'archcanvas-continuous-engineering-validation/1',base,inputDenominator:d,captureDurationMs:stop.captureEndedAt-r.startedAt,
    drainDurationMs:stop.drainEndedAt-stop.captureEndedAt,rawEventCompleteness:complete,
    bindingContinuity:{document:a.documentId===b.documentId,source:a.sourceDigest===b.sourceDigest,ir:a.irDigest===b.irDigest,
      visibleIds:same(a.visibleIds,b.visibleIds),expandedIds:same(a.expandedIds,b.expandedIds),pinnedIds:same(a.pinnedIds,b.pinnedIds),protectedPins},
    viewportCoverage:{atStart:a.coverage,atEnd:b.coverage},presentedFps:null,continuousInputToPaintMs:null,performanceGatePassed:false,
    limitation:'Native raw event ledger and DOM/rAF proxies only; completeness does not certify missing native timing, paint, legibility, occlusion, fixed environment or human usability.'};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)console.log(JSON.stringify(validateContinuousObservation(JSON.parse(await readFile(process.argv[2],'utf8'))),null,2));
