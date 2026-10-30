import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';
import {Worker} from 'node:worker_threads';

const base=new URL('../public/preview/',import.meta.url),engine=fileURLToPath(new URL('yworks_edge_router_lab/',base));
const context=vm.createContext({performance});
const script=(name:string)=>vm.runInContext(readFileSync(new URL(name,base),'utf8'),context,{filename:name});
for(const name of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph','source-controls'])script('yworks_edge_router_lab/'+name+'.js');
for(const row of JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json',import.meta.url),'utf8')).files)script(row.path);
for(const name of ['studio-worker-transport','studio-adaptive','studio-semantic'])script('yworks_edge_router_lab/'+name+'.js');
const T=context.ArchCanvasNativeWorkerTransport,N=context.ArchCanvasSemanticView,E=context.SummaryEngine;
const catalog=JSON.parse(readFileSync(new URL('data/semantic/studio-catalog.json',base),'utf8'));
const ir=JSON.parse(readFileSync(new URL('data/semantic/'+catalog.models.find((m:any)=>m.title==='SameSource').ir.path,base),'utf8'));
const options={budgetMs:4000,refineCrossings:false,refinePlacement:false,refineChannels:false,refineFlow:false};
const plain=(v:any)=>JSON.parse(JSON.stringify(v));
const build=()=>N.prepare({task:'generic-build',ir:structuredClone(ir),state:N.state('overview'),options}).graph;
function fake(){
 const workers:any[]=[];
 const channel=T.client(()=>{const worker:any={sent:[],terminated:false,postMessage(value:any){this.sent.push(structuredClone(value));},terminate(){this.terminated=true;}};workers.push(worker);return worker;});
 return {channel,workers};
}
function actual(){
 const workers:any[]=[],sent:any[]=[],received:any[]=[];
 const channel=T.client(()=>{
  const worker=new Worker(`const {parentPort,workerData}=require('node:worker_threads');const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');globalThis.self=globalThis;globalThis.importScripts=(...files)=>files.forEach(file=>vm.runInThisContext(fs.readFileSync(path.join(workerData,file),'utf8'),{filename:file}));globalThis.postMessage=value=>parentPort.postMessage(value);importScripts('routing-worker.js');parentPort.on('message',data=>self.onmessage({data}));`,{eval:true,workerData:engine});
  const proxy:any={postMessage(value:any){sent.push(structuredClone(value));worker.postMessage(value);},terminate(){void worker.terminate();}};
  worker.on('message',data=>{received.push(structuredClone(data));proxy.onmessage?.({data});});worker.on('error',error=>proxy.onerror?.(error));workers.push(proxy);return proxy;
 });
 return {channel,workers,sent,received};
}
function valid(result:any){assert.equal(result.ok,true,result.error);assert.equal(result.validation.source.ok,true);assert.equal(result.validation.layout.ok,true);assert.ok(result.validation.edges.every(([,v]:any)=>v.ok));return result.graph;}

test('structured clone channel returns geometry with the original immutable canonical facts and exact bindings',async t=>{
 const {channel,sent,received}=actual();t.after(()=>channel.reset());
 const graph=build(),before=JSON.stringify(graph),result=await channel.run({task:'validate',graph});
 const next=valid(result);assert.equal(JSON.stringify(graph),before);const expected=structuredClone(graph);context.SummarySourceControls.refresh(expected);assert.deepEqual(plain(next),plain(expected));
 assert.equal(next.generic.ir,graph.generic.ir);assert.equal(next.edges[0].binding,graph.edges[0].binding);
 assert.ok(sent[0].graph.core);assert.equal(received[0].graph.core,undefined,'return reuses the core just received by Worker');
 const snapshot=N.snapshot(next);snapshot.nodes[0].x+=5;assert.notEqual(snapshot.nodes[0].x,next.nodes[0].x);
 assert.throws(()=>{next.generic.ir.title='forged';},TypeError);
});

test('thirty actual Worker validations transmit the core once and retain every geometry snapshot independently',async t=>{
 const {channel,sent,received}=actual();t.after(()=>channel.reset());let graph=build();const history=[];
 for(let i=0;i<30;i++){graph=valid(await channel.run({task:'validate',graph}));history.push(N.snapshot(graph));}
 assert.equal(sent.filter(v=>v.graph?.core).length,1);assert.equal(received.filter(v=>v.graph?.core).length,0);
 assert.equal(new Set(history.map(g=>g.generic.ir)).size,1);assert.equal(new Set(history.map(g=>g.nodes)).size,30);
 assert.deepEqual(plain(history[29].generic.ir),ir);assert.deepEqual(plain(history[0].edges),plain(history[29].edges));
});

test('actual frontier transitions and undo across more than four cores restore their own source and cut',async t=>{
 const {channel}=actual();t.after(()=>channel.reset());const history=[];let graph=build();
 for(let i=0;i<7;i++){
  const patch={paperGranularity:i%2===0?'roles':'modules'};
  graph=valid(await channel.run({task:'frontier',graph,transition:{type:'semantic',patch},options}));history.push(N.snapshot(graph));
 }
 for(const saved of history.slice().reverse()){
  const next=valid(await channel.run({task:'validate',graph:saved}));
  assert.deepEqual(plain(next.generic.state),plain(saved.generic.state));assert.deepEqual(plain(next.generic.ir),ir);
  assert.deepEqual(plain(next.nodes),plain(saved.nodes));assert.deepEqual(plain(next.edges),plain(saved.edges));
 }
});

test('actual transport never certifies forged binding, source facts or a missing operand',async t=>{
 const {channel}=actual();t.after(()=>channel.reset());const graph=valid(await channel.run({task:'validate',graph:build()}));
 for(const alter of [(g:any)=>g.edges[0].binding.target_port='invented',(g:any)=>g.generic.ir.nodes[0].label='forged',(g:any)=>g.edges.splice(0,1)]){
  const forged=structuredClone(graph);alter(forged);const result=await channel.run({task:'validate',graph:forged});
  assert.ok(!result.ok||!N.accepts(result.graph,result.validation),'wire core must not carry trusted certification');
 }
 valid(await channel.run({task:'validate',graph}));
});

test('actual generic-build installs a Worker-origin core, then geometry validation sends no duplicate core',async t=>{
 const {channel,sent,received}=actual();t.after(()=>channel.reset());
 const graph=valid(await channel.run({task:'generic-build',ir,state:N.state('overview'),options}));
 assert.ok(received[0].graph.core);assert.deepEqual(plain(graph.generic.ir),ir);
 valid(await channel.run({task:'validate',graph}));assert.equal(sent[1].graph.core,undefined);assert.equal(received[1].graph.core,undefined);
});

test('actual legacy validation retains the uncompressed graph contract',async t=>{
 const {channel,sent,received}=actual();t.after(()=>channel.reset());
 const graph={nodes:[],edges:[]};const result=await channel.run({task:'validate',graph});
 assert.equal(sent[0].graph.nativeGeometryTransport,undefined);assert.equal(received[0].graph.nativeGeometryTransport,undefined);
 assert.equal(result.ok,true);assert.deepEqual(result.graph.nodes,[]);
});

test('send failure drains all pending calls, resets semantic cache and ignores late callbacks from the old Worker',async()=>{
 const {channel,workers}=fake(),graph=build();const pending=channel.run({task:'validate',graph}),old=workers[0];
 old.postMessage=()=>{throw Error('DataCloneError');};const failed=channel.run({task:'validate',graph});
 assert.equal(await pending,null);assert.equal(await failed,null);assert.equal(old.terminated,true);
 const retry=channel.run({task:'validate',graph}),fresh=workers[1],message=fresh.sent[0];assert.ok(message.graph.core);
 old.onerror();old.onmessage({data:{requestId:message.requestId,ok:false,error:'stale'}});assert.equal(fresh.terminated,false);
 fresh.onmessage({data:{requestId:message.requestId,ok:true}});assert.equal((await retry).ok,true);channel.reset();
});

test('error and messageerror both drain requests and the next generation sends complete facts',async()=>{
 for(const event of ['onerror','onmessageerror']){
  const {channel,workers}=fake(),graph=build(),pending=channel.run({task:'validate',graph});workers[0][event]();assert.equal(await pending,null);
  const retry=channel.run({task:'validate',graph}),worker=workers[1];assert.ok(worker.sent[0].graph.core);assert.notEqual(worker.sent[0].graph.id,workers[0].sent[0].graph.id);
  worker.onmessage({data:{requestId:worker.sent[0].requestId,ok:true}});assert.equal((await retry).ok,true);channel.reset();
 }
});

test('missing reply core and explicit Worker cache misses discard the channel instead of borrowing an old IR',async()=>{
 for(const response of [{graph:{nativeGeometryTransport:1,id:'expired',shell:{generic:{},nodes:[],edges:[]}}},{nativeTransportError:true,error:'expired'}]){
  const {channel,workers}=fake(),pending=channel.run({task:'validate',graph:build()}),worker=workers[0];
  worker.onmessage({data:{requestId:worker.sent[0].requestId,...response}});assert.equal(await pending,null);assert.equal(worker.terminated,true);
  const retry=channel.run({task:'validate',graph:build()});assert.ok(workers[1].sent[0].graph.core);channel.reset();assert.equal(await retry,null);
 }
});

test('out-of-order and unrelated replies resolve only their exact pending request',async()=>{
 const {channel,workers}=fake(),a=channel.run({task:'validate',graph:build()}),b=channel.run({task:'validate',graph:build()}),worker=workers[0];
 worker.onmessage({data:{requestId:99999,ok:true}});
 worker.onmessage({data:{requestId:worker.sent[1].requestId,ok:false,error:'semantic refusal'}});assert.equal((await b).error,'semantic refusal');assert.equal(worker.terminated,false);
 worker.onmessage({data:{requestId:worker.sent[0].requestId,ok:true}});assert.equal((await a).ok,true);channel.reset();
});

test('unavailable Worker lets the caller use its independent validated fallback',async()=>{
 for(const factory of [()=>null,()=>{throw Error('unavailable');}])assert.equal(await T.client(factory).run({task:'validate',graph:build()}),null);
 const app=readFileSync(new URL('yworks_edge_router_lab/app.js',base),'utf8');
 const start=app.indexOf('  async function runGraphTask('),end=app.indexOf('  async function runRouting(',start);
 const fallback=vm.createContext({workerChannel:{run:async()=>null},N,E,setTimeout,window:{SummarySourceControls:context.SummarySourceControls},message:{task:'validate',graph:build()}});
 vm.runInContext(app.slice(start,end)+';globalThis.run=runGraphTask;',fallback);
 const input=fallback.message.graph,before=JSON.stringify(input),result=await fallback.run(fallback.message);valid(result);
 assert.notEqual(result.graph,input);assert.equal(JSON.stringify(input),before);assert.deepEqual(plain(result.graph.generic.ir),ir);
});

test('bounded native cache evicts old references explicitly and replaced source objects force a new full core',()=>{
 const a=T.endpoint('left'),b=T.endpoint('right'),graph=build();const first=structuredClone(a.pack({graph}));b.unpack(structuredClone(first));
 assert.equal(a.pack({graph}).graph.core,undefined);
 const replacement=N.snapshot(graph);replacement.generic.ir=structuredClone(graph.generic.ir);const changed=structuredClone(a.pack({graph:replacement}));assert.ok(changed.graph.core);assert.notEqual(changed.graph.id,first.graph.id);
 for(let i=0;i<6;i++)b.unpack(structuredClone(a.pack({graph:build()})));
 const expired=structuredClone(first);delete expired.graph.core;assert.throws(()=>b.unpack(expired),/缓存已过期/);
});

test('explicit cancellation terminates only the pending generation and ignores late replies without requesting fallback',async()=>{
 const {channel,workers}=fake();assert.equal(channel.isPending(),false);assert.equal(channel.cancel(),false);
 const graph=build(),before=JSON.stringify(graph),pending=channel.run({task:'validate',graph}),old=workers[0];
 assert.equal(channel.isPending(),true);assert.equal(channel.cancel(),true);assert.equal(channel.isPending(),false);
 assert.deepEqual(plain(await pending),{cancelled:true});assert.equal(old.terminated,true);
 const retry=channel.run({task:'validate',graph}),next=workers[1];assert.ok(next.sent[0].graph.core);
 old.onmessage({data:{requestId:next.sent[0].requestId,ok:false,error:'late abandoned result'}});
 assert.equal(channel.isPending(),true);
 next.onmessage({data:{requestId:next.sent[0].requestId,ok:true}});assert.equal((await retry).ok,true);
 assert.equal(channel.isPending(),false);assert.equal(JSON.stringify(graph),before);channel.reset();
});

test('cancelled graph task rejects before any main-thread fallback and frontier keeps graph/history/selection/camera',async()=>{
 const app=readFileSync(new URL('yworks_edge_router_lab/app.js',base),'utf8');
 const start=app.indexOf('  async function runGraphTask('),end=app.indexOf('  async function runRouting(',start);
 let fallbackCalls=0;const graph=build(),selected=new Set([graph.nodes[0].id]),camera={x:7,y:9,w:800,h:600};
 const scope=vm.createContext({workerChannel:{run:async()=>({cancelled:true})},N:{prepare(){fallbackCalls++;throw Error('unexpected fallback');}},E,setTimeout,
  graph,busy:false,drag:null,camera,selectedNodes:selected,selectedEdges:new Set(),history:[],future:[{redo:true}],performance,
  render(){},options:()=>({}),$(){return {};},studioBridge:{state(){}},toast(){},persist(){throw Error('cancel must not persist');}});
 vm.runInContext(app.slice(start,end)+';globalThis.run=runGraphTask;',scope);
 await assert.rejects(()=>scope.run({task:'generic-build',ir}),{name:'AbortError'});assert.equal(fallbackCalls,0);
 const a=app.indexOf('  async function changeFrontier('),b=app.indexOf('  let nodeMenu=',a);
 vm.runInContext(app.slice(a,b)+';globalThis.change=changeFrontier;',scope);
 await assert.rejects(()=>scope.change({type:'preset',preset:'detail'},true),{name:'AbortError'});
 assert.equal(scope.graph,graph);assert.equal(scope.history.length,0);assert.equal(scope.future.length,1);assert.equal(scope.selectedNodes,selected);
 assert.deepEqual(plain(scope.camera),camera);assert.equal(scope.busy,false);assert.equal(fallbackCalls,0);
});

test('pending observer advertises cancellation only for actual pending Worker requests',async()=>{
 const events:boolean[]=[],workers:any[]=[];
 const channel=T.client(()=>{const w:any={postMessage(){},terminate(){}};workers.push(w);return w;},(pending:boolean)=>events.push(pending));
 const a=channel.run({task:'validate',graph:build()});assert.equal(channel.isPending(),true);channel.cancel();await a;
 const b=channel.run({task:'validate',graph:build()});workers[1].onerror();assert.equal(await b,null);
 assert.deepEqual(events,[true,false,true,false]);assert.equal(channel.isPending(),false);
});

test('actual Apply worker task validates a bounded batch, keeps source transport shared and resumes the remaining scope',async t=>{
 const {channel,sent}=actual();t.after(()=>channel.reset());const graph=valid(await channel.run({task:'validate',graph:build()}));
 const ids=graph.edges.map((e:any)=>e.id),geometry=JSON.stringify(graph.nodes),bindings=JSON.stringify(graph.edges.map((e:any)=>e.binding));
 const options={margin:6,stub:28,bendCost:40,crossingCost:450,overlapCost:2,edgeSpacing:12,sides:'any',style:'orthogonal',optimizeReadability:true,budgetMs:0};
 const first=await channel.run({task:'optimize',graph,ids,options}),retained=valid(first);assert.deepEqual(plain(first.optimization.pendingIds),plain(ids));assert.equal(JSON.stringify(retained.nodes),geometry);assert.equal(JSON.stringify(retained.edges.map((e:any)=>e.binding)),bindings);assert.equal(retained.generic.ir,graph.generic.ir);
 assert.equal(sent.at(-1).graph.core,undefined,'Apply must not resend the already verified source corpus');
 const next=await channel.run({task:'optimize',graph:retained,ids,options:{...options,budgetMs:100}});valid(next);assert.equal(JSON.stringify(next.graph.nodes),geometry);assert.equal(next.optimization.checked+next.optimization.pendingIds.length,ids.length);
});
