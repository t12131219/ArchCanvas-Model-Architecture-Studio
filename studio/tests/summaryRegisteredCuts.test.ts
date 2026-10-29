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

test('registered subtree replacement clears nested overrides without affecting sibling cuts or preceding graph',()=>{
 let graph=F.build(F.create(sources));const available=T.modules(graph),by=new Map(graph.recursive.authority.detail.nodes.map((n:any)=>[n.id,n]));
 const inside=(id:string,owner:string)=>{while(id){if(id===owner)return true;id=(by.get(id)as any)?.parent;}return false;};
 const owner=available.find((m:any)=>available.some((n:any)=>n.id!==m.id&&inside(n.id,m.id))&&available.some((n:any)=>!inside(n.id,m.id)&&!inside(m.id,n.id)));
 assert.ok(owner);const child=available.find((n:any)=>n.id!==owner.id&&inside(n.id,owner.id)),sibling=available.find((n:any)=>!inside(n.id,owner.id)&&!inside(owner.id,n.id));
 graph=T.moduleCut(graph,{ids:[owner.id],level:'source',depth:1});graph=T.moduleCut(graph,{ids:[child.id],level:'source'});graph=T.moduleCut(graph,{ids:[sibling.id],level:'f1'});
 const before=JSON.stringify(graph),collapsed=T.moduleCut(graph,{ids:[owner.id],level:'source',depth:0,replaceDescendants:true});
 assert.equal(collapsed.recursive.state.moduleCuts.some((c:any)=>c.id===child.id),false);
 assert.equal(collapsed.recursive.state.moduleCuts.find((c:any)=>c.id===sibling.id).level,'f1');
 assert.equal(collapsed.nodes.filter((n:any)=>inside(n.id,owner.id)).length,1);
 assert.equal(JSON.stringify(graph),before);
 const reset=T.moduleCut(graph,{ids:[owner.id],reset:true,replaceDescendants:true});assert.equal(reset.recursive.state.moduleCuts.length,1);
 assert.equal(reset.recursive.state.moduleCuts[0].id,sibling.id);
});
