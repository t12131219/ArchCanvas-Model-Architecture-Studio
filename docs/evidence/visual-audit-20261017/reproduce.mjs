// Pure engine diagnosis; does not control a browser or execute model source.
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,'../../..');
const runtime=path.join(root,'studio/public/preview/yworks_edge_router_lab');
const ctx=vm.createContext({TextEncoder,TextDecoder});
for(const name of ['router.js','physical-ports.js','junction-markers.js','route-labels.js','source-contracts.js','semantic-constraints.js','graph-engine.js','recursive-graph.js','source-adapter.js','source-controls.js','frontier-task.js'])vm.runInContext(fs.readFileSync(path.join(runtime,name),'utf8'),ctx,{filename:name});
const C=ctx.SummaryConstraints,F=ctx.SummaryRecursive,E=ctx.SummaryEngine,T=ctx.SummaryFrontierTask;
const results={};
for(const name of ['seeded','transformed']){
 const bundle=JSON.parse(fs.readFileSync(path.join(here,name+'-bundle.json')));
 const sources=ctx.SummarySourceAdapter.sources(bundle);
 const g=F.build(F.create(sources));
 const states={};
 for(const [state,transition] of [['initial',null],['expanded',{type:'all',expanded:true}]]){
  try{const r=T.run(E.clone(g),transition,{});states[state]={ok:true,nodes:r.graph.nodes.length,edges:r.graph.edges.length};
   if(name==='seeded'&&state==='expanded'){
    const before=r.graph.edges.find(e=>e.id==='edge-4'),beforePoints=E.clone(before.route);
    E.routeBatch(r.graph,r.graph.edges.map(e=>e.id),{style:'orthogonal',sides:'any',margin:6,avoidCrossings:true,optimizeReadability:true});
    const after=r.graph.edges.find(e=>e.id==='edge-4');
    states.unary={before:beforePoints,after:after.route};
   }
  }catch(error){states[state]={ok:false,error:String(error)};}
 }
 results[name]=states;
}
// Match the app's complete authority inputs for each catalog case, rather than
// conflating a historical detailed-only stress probe with user-facing loading.
const catalog=JSON.parse(fs.readFileSync(path.join(root,'studio/public/preview/data/catalog.json'))).cases;
const cases=[];
for(const c of catalog){
 if(c.views.some(v=>v.builtin))continue;
 try{
  const sources=Object.fromEntries(c.views.map(v=>[v.key,C.initialize(JSON.parse(fs.readFileSync(path.join(root,'studio/public/preview',v.asset.replace(/\.js$/,'.json')))))]));
  const g=F.build(F.create(sources));
  let r=T.run(g,null,{});
  const start=Date.now();r=T.run(r.graph,{type:'all',expanded:true},{});
  cases.push({id:c.id,title:c.title,historical:!!c.historical,ok:true,nodes:r.graph.nodes.length,edges:r.graph.edges.length,ms:Date.now()-start});
 }catch(error){cases.push({id:c.id,title:c.title,historical:!!c.historical,ok:false,error:String(error)});}
}
results.catalog={total:cases.length,current:cases.filter(x=>!x.historical).length,currentFailed:cases.filter(x=>!x.historical&&!x.ok).length,historical:cases.filter(x=>x.historical).length,historicalFailed:cases.filter(x=>x.historical&&!x.ok).length,cases};
fs.writeFileSync(path.join(here,'repro-results.json'),JSON.stringify(results,null,2)+'\n');
console.log(JSON.stringify({seeded:results.seeded,transformed:results.transformed,catalog:{...results.catalog,cases:undefined}},null,2));
// Diagnoses are recorded as facts, not a test suite claiming these bugs pass.
