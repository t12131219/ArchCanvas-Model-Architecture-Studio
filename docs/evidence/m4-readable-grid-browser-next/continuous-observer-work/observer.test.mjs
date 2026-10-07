import test from 'node:test';
import assert from 'node:assert/strict';
import { createInputObserver } from './observer.mjs';
import { validateContinuousObservation } from './validate.mjs';

// Hand-authored public surface, no product state, DOM dispatch or serializer.
function surface({tool='select',kind='viewport',control=false,editing=false}={}){
  let at=10,revision=5;const listeners=new Map(),raf=new Map(),timers=[];let seq=0;
  const viewportRect={x:230,y:100,width:3300,height:1800};
  const camera={a:1,b:0,c:0,d:1,e:230,f:100};
  class Element{
    constructor(attrs={}){this.attrs=attrs;}
    getAttribute(k){return this.attrs[k]??null;}
    closest(s){
      if(s==='.canvas-viewport')return viewport;
      if(s==='button')return control?new Element({'aria-label':'适合画布 F'}):null;
      if(s==='input,textarea,select,[contenteditable]')return editing?this:null;
      if(s==='[data-canonical-id]'&&kind==='node')return groups[0];
      if(s==='[data-expand-id]'&&kind==='toggle')return new Element({'data-expand-id':'node:A'});
      return null;
    }
  }
  const viewport=new Element({'data-canvas-tool':tool});viewport.getBoundingClientRect=()=>viewportRect;
  const hand=new Element({'aria-pressed':String(tool==='pan')});
  const groups=['node:A','node:P'].map((id,i)=>{
    const g=new Element({'data-node-id':id,'data-canonical-id':id,'aria-label':id});
    const body={x:{baseVal:{value:40+i*100}},y:{baseVal:{value:30}},width:{baseVal:{value:60}},height:{baseVal:{value:30}},getScreenCTM:()=>camera};
    g.querySelector=()=>body;g.body=body;return g;
  });
  const metadata={sourceDigest:'a'.repeat(64),irDigest:'b'.repeat(64),sourceFacts:groups.map((g,i)=>({id:g.getAttribute('data-node-id'),category:i?'input':'linear'}))};
  const svg=new Element({'data-document-id':'canvas-independent-responsive','data-revision':String(revision)});
  svg.outerHTML='<svg data-document-id="canvas-independent-responsive"/>';
  svg.querySelector=s=>s==='metadata'?{textContent:JSON.stringify(metadata)}:groups.find(g=>s.includes('"'+g.getAttribute('data-node-id')+'"'))??null;
  svg.querySelectorAll=()=>groups;
  const host={querySelector:()=>svg,dataset:{expandedIds:'[]',pinnedIds:'["node:P"]'}};
  const doc={querySelector:s=>s==='.publication-scene'?host:s==='.paper'?{}:s==='.canvas-viewport'?viewport:s==='.canvas-toolbar button[aria-label="平移画布"]'?hand:null,
    querySelectorAll:()=>[],visibilityState:'visible',hasFocus:()=>true,scripts:[],fonts:Object.assign([],{status:'loaded'}),addEventListener(){},removeEventListener(){}};
  const performanceObservers=[];
  class Observer{static supportedEntryTypes=['event','longtask'];constructor(callback){this.callback=callback;this.queue=[];performanceObservers.push(this);}observe(options){this.type=options.type??options.entryTypes[0];}takeRecords(){return this.queue.splice(0);}disconnect(){}deliver(entries){this.callback({getEntries:()=>entries});}}
  const w={document:doc,Element,performance:{now:()=>at++,timeOrigin:1000000},DOMMatrixReadOnly:class{constructor(){Object.assign(this,camera);}},
    DOMPoint:class{constructor(x,y){this.x=x;this.y=y;}matrixTransform(m){return{x:m.a*this.x+m.c*this.y+m.e,y:m.b*this.x+m.d*this.y+m.f};}},
    getComputedStyle:()=>({transform:`matrix(${camera.a},0,0,${camera.d},${camera.e},${camera.f})`}),
    requestAnimationFrame:callback=>{raf.set(++seq,callback);return seq;},cancelAnimationFrame:id=>raf.delete(id),
    setTimeout:(callback,ms)=>{timers.push({callback,ms});},location:{href:'http://127.0.0.1:42940/'},navigator:{userAgent:'independent-fake-surface'},innerWidth:3600,innerHeight:2100,devicePixelRatio:1,frameElement:null,CSS:{escape:s=>s},PerformanceObserver:Observer,
    addEventListener(type,callback){const set=listeners.get(type)??new Set();set.add(callback);listeners.set(type,set);},removeEventListener(type,callback){listeners.get(type)?.delete(callback);}};
  w.parent=w;
  return{w,camera,svg,groups,metadata,performanceObservers,timers,
    emit(type,extra={}){const e={type,target:new Element(),isTrusted:true,timeStamp:at,pointerId:1,pointerType:'mouse',button:0,buttons:type==='pointerup'?0:1,clientX:320,clientY:180,deltaX:0,deltaY:1,deltaMode:0,...extra};for(const fn of [...listeners.get(type)??[]])fn(e);},
    frame(){at+=16;const callbacks=[...raf.values()];raf.clear();for(const callback of callbacks)callback(at);},
    finishDrain(){for(const t of timers.splice(0)){at+=t.ms;t.callback();}},
    setRevision(v){revision=v;svg.attrs['data-revision']=String(v);}};
}
async function stop(o,f){const p=o.stop();f.finishDrain();return await p;}

test('trusted pointer/wheel ledger retains every observed input and coalesced denominator',async()=>{
  const f=surface();const o=createInputObserver(f.w,{drainMs:2000});o.start();
  f.emit('pointerdown');f.emit('pointermove',{getCoalescedEvents:()=>[{timeStamp:50,clientX:323,clientY:184},{timeStamp:51,clientX:327,clientY:185}]});f.emit('pointerup');f.emit('wheel');f.emit('click',{isTrusted:false});
  const r=await stop(o,f);assert.equal(r.inputDenominator.observed,5);assert.equal(r.inputDenominator.trusted,4);assert.equal(r.inputDenominator.untrusted,1);assert.equal(r.inputDenominator.retained,5);assert.equal(r.inputDenominator.coalescedPointerSamples,2);assert.equal(r.inputDenominator.rawEventCompleteness,true);
  assert.equal(r.inputDenominator.byType.pointermove.observed,1);assert.ok(r.events.every(e=>Number.isFinite(e.rawTimeStamp)));
  const a=validateContinuousObservation(r);assert.equal(a.performanceGatePassed,false);assert.equal(a.presentedFps,null);assert.equal(a.continuousInputToPaintMs,null);assert.equal(a.viewportCoverage.atStart.fullyInsideBodies,2);assert.equal(a.bindingContinuity.protectedPins[0].canvasExact,true);
});

test('overflow preserves total denominator and never claims complete raw events',async()=>{
  const f=surface();const o=createInputObserver(f.w,{eventLimit:2,drainMs:0});o.start();for(let i=0;i<5;i++)f.emit('wheel');
  const r=await stop(o,f);assert.equal(r.events.length,2);assert.equal(r.inputDenominator.observed,5);assert.equal(r.inputDenominator.dropped,3);assert.equal(r.inputDenominator.byType.wheel.dropped,3);assert.equal(r.inputDenominator.rawEventCompleteness,false);assert.equal(r.buffers.events.seen,5);assert.equal(validateContinuousObservation(r).rawEventCompleteness,false);
  const bad=structuredClone(r);bad.inputDenominator.rawEventCompleteness=true;assert.throws(()=>validateContinuousObservation(bad),/overclaimed/);
});

test('counter oracle rejects forged type and coalesced denominators',async()=>{
  const f=surface(),o=createInputObserver(f.w,{drainMs:0});o.start();f.emit('pointermove');const r=await stop(o,f);
  const bad=structuredClone(r);bad.inputDenominator.byType.pointermove.trusted=0;assert.throws(()=>validateContinuousObservation(bad),/counters|ledger/);
  const forged=structuredClone(r);forged.inputDenominator.coalescedPointerSamples=3;forged.inputDenominator.byType.pointermove.coalescedPointerSamples=3;assert.throws(()=>validateContinuousObservation(forged),/Coalesced/);
});

test('wrong target/untrusted gesture cannot start requested drag; raw attempts remain retained',async()=>{
  const f=surface({kind:'node'}),o=createInputObserver(f.w,{drainMs:0});o.start();o.arm({operation:'drag',targetIds:['different:node']});f.emit('pointerdown');f.emit('pointerup');const t=o.finishTrial();assert.equal(t.status,'no-input');assert.equal((await stop(o,f)).events.length,2);
  const g=surface({kind:'node'}),p=createInputObserver(g.w,{drainMs:0});p.start();p.arm({operation:'drag',targetIds:['node:A']});g.emit('pointerdown',{isTrusted:false});assert.equal(p.finishTrial().status,'no-input');assert.equal((await stop(p,g)).inputDenominator.untrusted,1);
});

test('hand tool retains pan priority and will not classify it as selected object drag',async()=>{
  const f=surface({tool:'pan',kind:'node'}),o=createInputObserver(f.w,{drainMs:0});o.start();o.arm({operation:'drag',targetIds:['node:A']});f.emit('pointerdown');assert.equal(o.finishTrial().status,'no-input');await stop(o,f);
  const g=surface({tool:'pan',kind:'node'}),p=createInputObserver(g.w,{drainMs:0});p.start();p.arm({operation:'pan'});g.emit('pointerdown');g.camera.e+=24;g.frame();g.emit('pointerup',{clientX:344});assert.equal(p.finishTrial().status,'finished');const r=await stop(p,g);const a=validateContinuousObservation(r);assert.equal(a.base.trials[0].operationSucceeded,true);assert.equal(a.bindingContinuity.protectedPins[0].canvasExact,true);
});

test('capture ends before drain: later events excluded but delivered capture timing retained',async()=>{
  const f=surface(),o=createInputObserver(f.w,{drainMs:2000});o.start();f.emit('pointerdown');const eventAt=f.w.performance.now()-3;
  const promise=o.stop();f.emit('wheel');const po=f.performanceObservers.find(p=>p.type==='event');
  const ended=f.w.performance.now();po.deliver([{name:'pointerdown',entryType:'event',startTime:eventAt,duration:32,processingStart:eventAt+1,processingEnd:eventAt+2,interactionId:1,target:null},{name:'click',entryType:'event',startTime:ended+5,duration:32,processingStart:ended+6,processingEnd:ended+7,interactionId:2,target:null}]);
  f.finishDrain();const r=await promise;assert.equal(r.inputDenominator.observed,1);assert.equal(r.eventTiming.length,1);assert.equal(r.eventTiming[0].deliveryPhase,'drain');assert.equal(r.postCaptureTiming.length,1);assert.equal(r.stopProtocol.unformedEntriesGuaranteed,false);assert.ok(r.stopProtocol.drainEndedAt-r.stopProtocol.captureEndedAt>=2000);
});

test('fully-inside counts are geometric and forged viewport membership is refused',async()=>{
  const f=surface(),o=createInputObserver(f.w,{drainMs:0});o.start();const r=await stop(o,f);const bad=structuredClone(r);bad.bindingAtStart.objects['node:A'].fullyInsideViewport=false;assert.throws(()=>validateContinuousObservation(bad),/counts|overclaimed/);
});
