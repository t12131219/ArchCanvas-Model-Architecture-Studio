// F0 packet diagnostic only: does not open or authorize large catalog models.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {serialize} from 'node:v8';
const root=new URL('file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/'),base=new URL('studio/public/preview/',root),ctx=vm.createContext({performance});
const script=p=>vm.runInContext(fs.readFileSync(new URL(p,base),'utf8'),ctx,{filename:p});
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])script('yworks_edge_router_lab/'+n+'.js');
for(const row of JSON.parse(fs.readFileSync(new URL('docs/summary-native-view-manifest-20261028.json',root))).files)script(row.path);
for(const n of ['studio-shared-source','studio-worker-transport','studio-adaptive','studio-semantic'])script('yworks_edge_router_lab/'+n+'.js');

const catalog=JSON.parse(fs.readFileSync(new URL('data/semantic/studio-catalog.json',base)));
const N=ctx.ArchCanvasSemanticView,G=ctx.SummaryNativeSemantic,E=ctx.SummaryEngine;
for(const model of catalog.models.filter(m=>m.nodes>480||m.edges>3600)){
 const ir=JSON.parse(fs.readFileSync(new URL('data/semantic/'+model.ir.path,base)));let result,graph;
 for(const cut of ['overview','detail']){
  const started=performance.now();result=N.prepare(cut==='overview'?{task:'generic-build',ir,options:{}}:{task:'frontier',graph,transition:{type:'preset',preset:'detail'},options:{}});graph=result.graph;
  console.log(JSON.stringify({model:model.title,cut,ms:performance.now()-started,visible:[graph.nodes.length,graph.edges.length],routing:graph.nativeRouting,accepted:N.accepts(graph,result.validation),source:result.validation.source.ok,nodeConflicts:result.validation.layout.nodes,failed:graph.edges.filter(e=>e.failed&&!e.pendingRouting).slice(0,8).map(e=>[e.id,e.reason]),rss:process.memoryUsage().rss}));
  for(let i=0;i<4&&graph.nativeRouting.pending;i++){
   const start=performance.now();result=N.prepare({task:'generic-route',graph,options:{}});graph=result.graph;
   console.log(JSON.stringify({model:model.title,cut,continuation:i,ms:performance.now()-start,routing:graph.nativeRouting,accepted:N.accepts(graph,result.validation),rss:process.memoryUsage().rss}));
  }
 }
 globalThis.gc?.();
}
