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
for(const name of ['studio-shared-source','studio-worker-transport','studio-adaptive','studio-semantic'])script('yworks_edge_router_lab/'+name+'.js');
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

test('thirty actual semantic cut changes share one full immutable source IR across independent native states and history',async t=>{
 const {channel}=actual();t.after(()=>channel.reset());let graph=build();const history=[];
 for(let i=0;i<30;i++){
  graph=valid(await channel.run({task:'frontier',graph,transition:{type:'semantic',patch:{paperGranularity:i%2?'modules':'roles'}},options}));
  history.push(N.snapshot(graph));
 }
 assert.equal(new Set(history.map(g=>g.generic.ir)).size,1);assert.equal(new Set(history.map(g=>g.generic.state)).size,30);
 assert.equal(new Set(history.map(g=>g.nodes)).size,30);assert.deepEqual(plain(history[0].generic.ir),ir);
 const before=JSON.stringify(history[0]),isolated=N.snapshot(history[29]);isolated.nodes[0].x+=7;assert.equal(JSON.stringify(history[0]),before);
 for(const saved of history.slice().reverse()){
  const restored=valid(await channel.run({task:'validate',graph:saved}));assert.equal(restored.generic.ir,saved.generic.ir);
  assert.deepEqual(plain(restored.nodes),plain(saved.nodes));assert.deepEqual(plain(restored.generic.state),plain(saved.generic.state));
 }
});

test('full source comparison never deduplicates changed fields under the same claimed digest',()=>{
 const pool=context.ArchCanvasSharedSource.pool(),source=structuredClone(ir),canonical=pool.intern(source);
 assert.equal(pool.intern(structuredClone(source)),canonical);assert.equal(Object.isFrozen(canonical.nodes[0]),true);
 for(const edit of [(v:any)=>v.nodes[0].label='different',(v:any)=>v.edges[0].target_port='different',(v:any)=>v.extra={proof:'new'},(v:any)=>v.nodes.reverse(),(v:any)=>v.nodes[0].source_evidence=['other']]){
  const next=structuredClone(source);edit(next);assert.notEqual(pool.intern(next),canonical);assert.deepEqual(plain(canonical),ir);
 }
 assert.throws(()=>{canonical.nodes[0].label='mutable';},TypeError);
});

test('source pooling compares complete recorded CPU evidence and unknown metadata, including array order and property presence',()=>{
 const pool=context.ArchCanvasSharedSource.pool(),source={schema:'test',ir_digest:'same',runtime:{runs:[{case:'a',events:[{source_stack:[{file:'model.py',line:3}]}]}]},unknown:{a:null}};
 const a=pool.intern(source);assert.equal(pool.intern(structuredClone(source)),a);
 for(const edit of [(v:any)=>v.runtime.runs[0].events[0].source_stack[0].line=4,(v:any)=>delete v.unknown.a,(v:any)=>v.unknown.a=undefined,(v:any)=>v.runtime.runs.push({case:'b',events:[]})]){
  const changed=structuredClone(source);edit(changed);assert.notEqual(pool.intern(changed),a);
 }
});

test('source pool bounds strong retention to four complete sources while older history remains immutable and usable',()=>{
 const pool=context.ArchCanvasSharedSource.pool(),original=pool.intern(structuredClone(ir));
 for(let i=0;i<5;i++)pool.intern({...structuredClone(ir),title:'source '+i});
 const restored=pool.intern(structuredClone(ir));assert.notEqual(restored,original);assert.deepEqual(plain(restored),plain(original));
 assert.equal(pool.intern(structuredClone(ir)),restored);assert.equal(Object.isFrozen(original),true);
});

test('transport canonicalizes before caching, preserving same-cut shell reuse in both directions',()=>{
 const a=T.endpoint('a'),b=T.endpoint('b');let graph=build();const source=graph.generic.ir;
 const first=a.pack({graph});graph=b.unpack(structuredClone(first)).graph;const reply=b.pack({graph});assert.equal(reply.graph.core,undefined);
 graph=a.unpack(structuredClone(reply)).graph;assert.equal(graph.generic.ir,source);
 graph=structuredClone(graph);graph.generic.state={...graph.generic.state,paperGranularity:'roles'};
 const changed=b.unpack(structuredClone(a.pack({graph}))).graph;const back=a.unpack(structuredClone(b.pack({graph:changed}))).graph;
 assert.equal(back.generic.ir,source);assert.equal(a.pack({graph:back}).graph.core,undefined);
});

test('actual autosave snapshot avoids full IR JSON cloning and isolates mutable geometry until IndexedDB captures it',()=>{
 const app=readFileSync(new URL('yworks_edge_router_lab/app.js',base),'utf8');
 const start=app.indexOf('  function flushPersist()'),end=app.indexOf('  function persist()',start),writes:any[]=[],sessions=new Map();
 const graph=build(),ctx=vm.createContext({persistWorkspace:async()=>{},toast:()=>{},clearTimeout:()=>{},persistTimer:0,graph,original:graph,current:{id:'test'},busy:false,drag:null,G:context.SummaryNativeSemantic,F:{},camera:{x:0,y:0,w:900,h:600},E,N,history:[],future:[],dirty:true,frontierPreset:'overview',sessions,key:()=> 'test:unified',window:{SummaryRecursiveStorage:{put:async(k:any,v:any)=>{writes.push([k,v]);}}},svg:{setAttribute:()=>{}},$:()=>({}),studioBridge:null});
 vm.runInContext(app.slice(start,end)+';flushPersist();',ctx);assert.equal(writes.length,1);
 const payload=writes[0][1],session=sessions.get('test:unified');assert.equal(payload.version,5);assert.equal(payload.graph.generic.ir,graph.generic.ir);
 assert.equal(session.graph.generic.ir,graph.generic.ir);assert.notEqual(session.graph.nodes,payload.graph.nodes);
 const saved=JSON.stringify(payload);graph.nodes[0].x+=100;session.graph.nodes[0].y+=100;
 assert.equal(JSON.stringify(payload),saved);assert.deepEqual(plain(structuredClone(payload).graph.generic.ir),ir);
});
