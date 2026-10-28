import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const base=new URL('../public/preview/',import.meta.url),ctx=vm.createContext({performance});ctx.window=ctx;ctx.self=ctx;
const load=(path:string)=>vm.runInContext(readFileSync(new URL(path,base),'utf8'),ctx,{filename:path});
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph','frontier-task'])load('yworks_edge_router_lab/'+n+'.js');
const C=ctx.SummaryConstraints,F=ctx.SummaryRecursive,T=ctx.SummaryFrontierTask;
const entry=JSON.parse(readFileSync(new URL('data/summary-cases.json',base),'utf8')).cases.find((c:any)=>c.id==='01093cc06a87b35c');
const sources:any={};for(const v of [...entry.views,...entry.routeTemplates]){load(v.asset);sources[v.key]=C.initialize(ctx.SummaryCaseData[entry.id+':'+v.key]);}
test('external Memory fan-out keeps nested consumer lanes instead of clamping to title corners',()=>{
 let graph=F.build(F.create(sources));graph=T.moduleCut(graph,{ids:['runtime:call9'],level:'source'});graph=T.moduleCut(graph,{ids:['runtime:call51'],level:'source'});
 for(const id of ['trace-edge-0171','trace-edge-0180']){
  const edge=graph.edges.find((e:any)=>e.id===id),raw=sources['source-atomic'].edges.find((e:any)=>e.id===id);
  assert.equal(JSON.stringify(edge.binding),JSON.stringify(raw.binding));
  const gates=edge.contract.gates.filter((g:any)=>g.frame!==edge.target),ys=gates.map((g:any)=>C.gatePoint(graph.nodes.find((n:any)=>n.id===g.frame),g).y);
  const shared=ys.slice(0,3);assert.ok(Math.max(...shared)-Math.min(...shared)<.01,'shared parent K/V gates must retain their common consumer lane');
  for(const gate of gates){const n=graph.nodes.find((n:any)=>n.id===gate.frame);assert.ok(gate.fraction*n.h>80,'Memory may not be anchored above the receiving frame');}
 }
});
test('registered F0 resets mixed overrides in one transition and restores its exact source skeleton',()=>{
 let graph=F.build(F.create(sources));graph=T.moduleCut(graph,{ids:['runtime:call9'],level:'source'});graph=T.moduleCut(graph,{ids:['runtime:call51'],level:'f1'});
 const result=T.run(graph,{type:'preset',preset:'overview'}),expected=F.visible(F.create(sources));
 assert.equal(result.failed,0);assert.equal(result.validation.source.ok,true);assert.equal(result.validation.layout.ok,true);
 assert.equal(result.validation.edges.every(([,v]:any)=>v.ok),true);
 assert.equal(result.graph.recursive.state.moduleCuts,undefined);
 assert.deepEqual([...result.graph.nodes.map((n:any)=>n.id)].sort(),[...expected].sort());
 assert.ok(graph.recursive.state.moduleCuts.length>0,'prior mixed history must remain intact');
});
