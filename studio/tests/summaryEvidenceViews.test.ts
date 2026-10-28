import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {webcrypto} from 'node:crypto';
import vm from 'node:vm';

const base=new URL('../public/preview/',import.meta.url),context=vm.createContext({performance,TextEncoder,crypto:webcrypto});
function script(path:string){vm.runInContext(readFileSync(new URL(path,base),'utf8'),context,{filename:path});}
for(const name of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])script('yworks_edge_router_lab/'+name+'.js');
for(const row of JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json',import.meta.url),'utf8')).files)script(row.path);
for(const name of ['studio-semantic','studio-documents'])script('yworks_edge_router_lab/'+name+'.js');
const N=context.ArchCanvasSemanticView,G=context.SummaryNativeSemantic,D=context.ArchCanvasSummaryDocuments;
const copy=(v:any)=>JSON.parse(JSON.stringify(v)),options={budgetMs:30,refineCrossings:false,refinePlacement:false,refineChannels:false,refineFlow:false};
const catalog=JSON.parse(readFileSync(new URL('data/semantic/studio-catalog.json',base),'utf8'));
const models=catalog.models.filter((m:any)=>m.nodes<=480).map((m:any)=>({model:m,ir:JSON.parse(readFileSync(new URL('data/semantic/'+m.ir.path,base),'utf8'))}));
const recorded=models.filter((m:any)=>m.ir.runtime?.runs?.length);
function check(result:any,ir:any){
 assert.equal(result.ok,true);assert.equal(N.accepts(result.graph,result.validation),true);assert.equal(result.validation.source.ok,true);
 assert.deepEqual(copy(result.graph.generic.ir),ir);
 for(const [ledger,all] of [[result.graph.generic.receipts.node_accounting,ir.nodes],[result.graph.generic.receipts.edge_accounting,ir.edges]]){
  const ids=Object.values(ledger).flat() as string[];assert.equal(ids.length,all.length);assert.equal(new Set(ids).size,all.length);assert.deepEqual(ids.slice().sort(),all.map((v:any)=>v.id).sort());
 }
 return result.graph;
}
const build=(ir:any)=>check(N.prepare({task:'generic-build',ir,options}),ir);
const transition=(graph:any,patch:any)=>check(N.prepare({task:'frontier',graph,transition:{type:'semantic',patch},options}),copy(graph.generic.ir));

for(const {model,ir} of recorded)test(`source/CPU/merged views retain all facts and accounting for ${model.title}`,async()=>{
 let graph=build(ir);const initial=G.layoutSnapshot(graph),sourceCamera={x:10,y:20,w:900,h:600};
 assert.equal(N.inspector(graph).mode,'source');assert.deepEqual(copy(N.inspector(graph).availableModes),['source','runtime','merged']);
 const runtime=transition(graph,{mode:'runtime',paperFocus:null,paperRelation:null});
 assert.equal(runtime.generic.state.mode,'runtime');assert.ok(runtime.nodes.some((n:any)=>n.id==='runtime-observations'||n.id.startsWith('runtime:')));
 assert.equal(N.restoreCamera(graph,runtime,sourceCamera),null);
 graph=transition(runtime,{mode:'merged',paperFocus:null,paperRelation:null});
 const evidence=N.inspector(graph).runtimeEvidence;assert.equal(evidence.runs.length,ir.runtime.runs.length);assert.equal(evidence.executesModel,false);
 for(let i=0;i<ir.runtime.runs.length;i++){
  graph=transition(graph,{runtimeInlineRun:i,paperFocus:null});assert.equal(N.inspector(graph).runtimeEvidence.selectedRun,i);
  const detail=check(N.prepare({task:'frontier',graph,transition:{type:'preset',preset:'detail'},options}),ir);
  assert.equal(detail.generic.state.mode,'merged');assert.equal(N.inspector(detail).runtimeEvidence.selectedRun,i);
 }
 const saved=G.document(graph),read=G.read(copy(saved)),restored=check(N.prepare({task:'generic-build',...read,options}),ir);
 assert.deepEqual(copy(G.layoutSnapshot(restored)),copy(G.layoutSnapshot(graph)));assert.equal(restored.generic.state.mode,'merged');
 const record=await D.read(saved);assert.deepEqual(copy((await D.restore(copy(record.record))).parsed.ir),ir);
 const returned=transition(runtime,{mode:'source',paperFocus:null,paperRelation:null});
 assert.deepEqual(copy(N.restoreCamera(runtime,returned,{x:200,y:100,w:400,h:250})),sourceCamera);
 assert.deepEqual(copy(G.layoutSnapshot(returned).nodes),copy(initial.nodes));
});

test('mode and run validation refuses before altering facts, geometry, saved layouts or source authority',()=>{
 const ir=recorded[0].ir,graph=build(ir),before=JSON.stringify(graph);
 for(const patch of [{mode:'gpu'},{mode:null},{runtimeInlineRun:0},{mode:'merged',runtimeInlineRun:-1},{mode:'merged',runtimeInlineRun:999},{mode:'merged',runtimeInlineRun:.5},{mode:'merged',runtimeInlineRun:'0'},{mode:'merged',runtimeInlineRun:null},{mode:'merged',runtimeInlineRun:NaN},{runtime:{model_executed:true}}]){
  assert.throws(()=>transition(graph,patch));assert.equal(JSON.stringify(graph),before);
 }
 const plain=models.find((m:any)=>!m.ir.runtime?.runs?.length).ir,source=build(plain),snapshot=JSON.stringify(source);
 assert.throws(()=>transition(source,{mode:'runtime'}),/没有 CPU/);assert.equal(JSON.stringify(source),snapshot);
 const merged=transition(source,{mode:'merged'});assert.equal(N.inspector(merged).runtimeEvidence.runs.length,0);
 assert.deepEqual(copy(merged.generic.ir),plain);
});

test('forged or incomplete runtime supplementation stays unbound and retains canonical unknowns',()=>{
 const ir=copy(recorded[0].ir),opaque=ir.nodes.find((n:any)=>n.kind==='opaque');
 ir.source_runtime_index={schema:'source-runtime-integration/1',receipt_digest:ir.runtime.trace_digest,regions:[{run:0,source:opaque?.id||ir.nodes[0].id,call:'runtime:0:forged',events:['runtime:0:invented']}],unplaced:[]};
 for(const mutate of [(v:any)=>{},(v:any)=>v.runtime.source_unchanged=false,(v:any)=>v.runtime.runs[0].truncated=true,(v:any)=>v.runtime.runs[0].replay.matched=false]){
  const value=copy(ir);mutate(value);const graph=transition(build(value),{mode:'merged'}),view=N.inspector(graph);
  assert.equal(view.runtimeEvidence.integratedRegions,0);assert.deepEqual(copy(graph.generic.ir),value);
  assert.equal(graph.sourceAdapter,undefined);assert.equal(graph.sourceProfile?.modelExecuted,undefined);
 }
});

test('malformed run metadata cannot create selectable supplementation or execution authority',()=>{
 const graph=build(recorded[0].ir);
 for(const runs of [{length:2},'forged',[null],[false]]){
  const value=copy(graph);value.generic.ir.runtime.runs=runs;
  const before=JSON.stringify(value);
  assert.throws(()=>transition(value,{mode:'merged',runtimeInlineRun:0}),/样例不存在/);
  assert.equal(JSON.stringify(value),before);
 }
});

test('latent hierarchy focus crosses source/CPU views by exact identity and returns to the previous evidence cut',()=>{
 const ir=recorded[0].ir,source=build(ir);
 const target=ir.nodes.find((n:any)=>n.id.startsWith('runtime:')&&n.kind==='compute');assert.ok(target);
 const cpu=check(N.prepare({task:'frontier',graph:source,transition:{type:'focus',id:target.id},options}),ir);
 assert.equal(cpu.generic.state.mode,'runtime');assert.ok(cpu.nodes.some((n:any)=>n.id===target.id));assert.equal(N.inspector(cpu).canBack,true);
 const returned=check(N.prepare({task:'frontier',graph:cpu,transition:{type:'back'},options}),ir);
 assert.equal(returned.generic.state.mode,'source');
 const staticNode=ir.nodes.find((n:any)=>!n.id.startsWith('runtime:')&&n.id!=='runtime-observations'&&n.kind==='compute');assert.ok(staticNode);
 const focused=check(N.prepare({task:'frontier',graph:cpu,transition:{type:'focus',id:staticNode.id},options}),ir);
 assert.equal(focused.generic.state.mode,'source');assert.ok(focused.nodes.some((n:any)=>n.id===staticNode.id));
 const back=check(N.prepare({task:'frontier',graph:focused,transition:{type:'back'},options}),ir);assert.equal(back.generic.state.mode,'runtime');assert.ok(back.nodes.some((n:any)=>n.id===target.id));
});
