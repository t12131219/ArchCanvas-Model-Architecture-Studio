import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const base=new URL('../public/preview/yworks_edge_router_lab/',import.meta.url);
const ctx=vm.createContext({});
vm.runInContext(readFileSync(new URL('studio-shared-source.js',base),'utf8'),ctx);
const pool=()=>ctx.ArchCanvasSharedSource.pool();
const json=(v:any)=>JSON.parse(JSON.stringify(v));
const source=()=>({schema:'archcanvas-source-semantic/2',ir_digest:'claimed',nodes:[{id:'a',source_evidence:['file.py:4'],label:'A'}],edges:[],runtime:{runs:[{events:[{source_stack:[{file:'file.py',line:4}]}]}]},unknown:{complete:true}});

test('host snapshot shares complete equal source across graph, adapter and native documents while isolating all mutable presentation',()=>{
 const p=pool(),ir=source();
 const input={graph:{generic:{ir,state:{mode:'source'},authoring:{baseline:json(ir)}},nodes:[{id:'a',x:3}],studioCamera:{x:1,y:2,w:3,h:4}},adapter:{ir:{semantic_ir:json(ir)}},nativeDocument:{document:{baseline:json(ir)}}};
 const before=JSON.stringify(input),a=p.copy(input),b=p.copy(input);
 assert.deepEqual(json(a),json(input));assert.equal(JSON.stringify(input),before);
 assert.equal(a.graph.generic.ir,a.adapter.ir.semantic_ir);assert.equal(a.graph.generic.ir,a.nativeDocument.document.baseline);
 assert.equal(a.graph.generic.ir,a.graph.generic.authoring.baseline);assert.equal(a.graph.generic.ir,b.graph.generic.ir);
 const received=structuredClone(a);assert.equal(received.graph.generic.ir,received.nativeDocument.document.baseline);
 assert.notEqual(a.graph.nodes,b.graph.nodes);assert.notEqual(a.graph.generic.state,b.graph.generic.state);
 a.graph.nodes[0].x=99;a.graph.generic.state.mode='runtime';a.graph.studioCamera.x=70;
 assert.equal(b.graph.nodes[0].x,3);assert.equal(input.graph.nodes[0].x,3);assert.equal(b.graph.studioCamera.x,1);
 assert.equal(b.graph.generic.state.mode,'source');assert.equal(Object.isFrozen(a.graph.generic.ir.runtime.runs[0].events[0]),true);
 assert.throws(()=>{a.graph.generic.ir.nodes[0].label='changed';},TypeError);
});

test('snapshot sharing compares every source field and never equates altered source-stack, unknown metadata or order under the same digest',()=>{
 const p=pool(),ir=source(),canonical=p.copy({ir}).ir;
 for(const edit of [(v:any)=>v.runtime.runs[0].events[0].source_stack[0].line=5,(v:any)=>v.unknown.complete=false,(v:any)=>v.nodes[0].source_evidence.push('other'),(v:any)=>v.nodes.push({id:'b'}),(v:any)=>delete v.unknown]){
  const changed=json(ir);edit(changed);const result=p.copy({original:ir,changed});
  assert.equal(result.original,canonical);assert.notEqual(result.changed,canonical);assert.deepEqual(json(result.changed),changed);
 }
 assert.deepEqual(json(canonical),ir);
});

test('a workspace with many distinct module fragments still shares the complete original within its one snapshot across session-pool eviction',()=>{
 const p=pool(),ir=source(),input={graph:{ir},library:Array.from({length:9},(_,index)=>({...source(),ir_digest:'fragment-'+index,title:'Module '+index})),original:json(ir)};
 const output=p.copy(input);assert.equal(output.graph.ir,output.original);assert.deepEqual(json(output),input);
 assert.equal(new Set(output.library).size,9);assert.notEqual(output.library[0],output.graph.ir);
 const changed=source();changed.nodes[0].label='same digest, different source';
 const result=p.copy({a:ir,b:changed,c:json(ir)});assert.equal(result.a,result.c);assert.notEqual(result.a,result.b);
});

test('non-source snapshot keeps JSON field/array semantics and prototype-like keys without mutating its input',()=>{
 const p=pool(),input=JSON.parse('{"__proto__":{"x":1},"constructor":{"y":2}}');
 input.other=undefined;input.list=[undefined,NaN,Infinity];const output=p.copy(input);
 assert.deepEqual(json(output),json(input));assert.ok(Object.hasOwn(output,'__proto__'));assert.equal(({} as any).x,undefined);
 assert.equal(Object.hasOwn(output,'other'),false);assert.deepEqual(json(output.list),[null,null,null]);
 const cyclic:any={};cyclic.self=cyclic;assert.throws(()=>p.copy(cyclic),/cyclic/);
 assert.throws(()=>p.copy({value:1n}),/BigInt/);
 const metadata={schema:'archcanvas-source-semantic/2',documentSha256:'display-only',sourceVerified:false};
 const a=p.copy(metadata),b=p.copy(metadata);assert.notEqual(a,b);assert.equal(Object.isFrozen(a),false);
 a.sourceVerified=true;assert.equal(b.sourceVerified,false);assert.equal(metadata.sourceVerified,false);
});

test('actual Studio document builder shares the original source and preserves camera, source identity and independently editable geometry',()=>{
 const app=readFileSync(new URL('app.js',base),'utf8'),code=app.slice(app.indexOf('  function studioDocument('),app.indexOf('  function studioState('));
 const ir=source(),hostSource=pool(),graph={generic:{ir,state:{mode:'source'}},nodes:[{id:'a',x:3}],sourceAdapter:{sourceSha256:'source',irSha256:'ir'},semanticRevision:7};
 const environment=vm.createContext({graph,hostSource,workerChannel:{isPending:()=>false},current:{id:'case',title:'Model'},view:{key:'overview'},frontierPreset:'overview',N:{inspector:()=>({})},window:{},camera:{x:1,y:2,w:3,h:4},interactionMode:'compat',tool:'select',canvasGridVisible:true,dirty:true,busy:false,drag:null,history:[],future:[],selectedNodes:new Set(),selectedEdges:new Set(),importedPackages:new Map([['case',{ir:{semantic_ir:json(ir)}}]]),importedDocuments:new Map([['case',{record:{document:json(ir)}}]]),catalogSources:null,$:()=>({checked:false}),studioSelection:()=>({})});
 vm.runInContext(code,environment);const a=environment.studioDocument(),b=environment.studioDocument();
 assert.equal(a.graph.generic.ir,a.adapter.ir.semantic_ir);assert.equal(a.graph.generic.ir,a.nativeDocument.document);
 assert.equal(a.graph.generic.ir,b.graph.generic.ir);assert.equal(a.snapshotRevision,7);
 assert.deepEqual(json(a.sourceIdentity),{caseId:'case',sourceSha256:'source',irSha256:'ir'});
 assert.deepEqual(json(a.graph.studioCamera),{x:1,y:2,w:3,h:4});a.graph.nodes[0].x=90;
 assert.equal(b.graph.nodes[0].x,3);assert.equal(graph.nodes[0].x,3);
});

test('actual explicit save persists an independent native snapshot without building or serializing a host document',async()=>{
 const app=readFileSync(new URL('app.js',base),'utf8'),start=app.indexOf('save:async()=>{if(busy||drag)'),end=app.indexOf(',export:format',start);
 assert.ok(start>0&&end>start);const writes:any[]=[];let flushed=0,workspace=0;
 const graph={generic:{ir:source()},nodes:[{id:'a',x:3}]};
 const context=vm.createContext({busy:false,drag:null,graph,current:{id:'case'},camera:{x:1,y:2,w:3,h:4},dirty:true,frontierPreset:'detail',flushPersist:()=>{flushed++;},persistWorkspace:async()=>{workspace++;},N:{snapshot:pool().copy},key:()=> 'case:unified',window:{SummaryRecursiveStorage:{put:async(key:any,value:any)=>{writes.push([key,value]);}}}});
 vm.runInContext('globalThis.save=({'+app.slice(start,end)+'}).save;',context);await context.save();
 assert.equal(flushed,1);assert.equal(workspace,1);assert.equal(writes.length,1);
 const payload=writes[0][1];assert.equal(payload.version,5);assert.equal(payload.graph.generic.ir,graph.generic.ir);
 assert.deepEqual(json(payload.graph.studioCamera),{x:1,y:2,w:3,h:4});graph.nodes[0].x=90;assert.equal(payload.graph.nodes[0].x,3);
 context.busy=true;await assert.rejects(()=>context.save(),/完成当前图操作/);assert.equal(writes.length,1);
});
