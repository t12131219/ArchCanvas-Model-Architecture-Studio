// Public routing engine graph fixtures, independent of source parsing.
import fs from 'node:fs';import vm from 'node:vm';import path from 'node:path';import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url)),runtime=path.resolve(here,'../../../studio/public/preview/yworks_edge_router_lab');
const ctx=vm.createContext({TextEncoder,TextDecoder});for(const name of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph','source-controls','frontier-task'])vm.runInContext(fs.readFileSync(path.join(runtime,name+'.js'),'utf8'),ctx);
const E=ctx.SummaryEngine,C=ctx.SummaryConstraints,F=ctx.SummaryRecursive,T=ctx.SummaryFrontierTask;
const results=[];
for(const [name,pairs]of Object.entries({cycle:[[0,1],[1,2],[2,3],[3,0]],self_loop:[[0,0],[0,1],[1,2]],parallel_reverse:[[0,1],[0,1],[1,0],[2,3]],disconnected:[[0,1],[2,3],[4,5]]})){
 const nodes=Array.from({length:6},(_,i)=>{const x=90+(i%3)*280,y=90+Math.floor(i/3)*250,w=170,h=i===4?100:70,label=['Very long branch name','多语言模块 — 宽字符','Return / Rücklauf','Stage\nTwo','Independent component','Isolated'][i];return {id:'n'+i,x,y,w,h,base:[x,y],parent:null,expanded:false,routingObstacle:true,label,semantic:{kind:'independent generated topology'},html:`<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="#e7f1ee" stroke="#26786c"/><text x="${x+8}" y="${y+30}" font-size="12">${label}</text>`};});
 const edges=pairs.map(([s,t],i)=>({id:'edge-'+i,source:'n'+s,target:'n'+t,route:[],waypoints:[],arrow:'target',style:'orthogonal',binding:{representation:'generated-topology',src:'n'+s+':out',dst:'n'+t+':in'+i},draft:false}));
 const graph={nodes,edges,canvas:[1000,600],caseId:'generated-'+name,viewKey:'overview',definitions:'',extras:'',sourceFacts:[],sourceProfile:{},irSha256:null};
 for(const e of edges)e.route=[E.endpoint(graph,e,'source'),E.endpoint(graph,e,'target')];
 const before=JSON.stringify(edges.map(e=>[e.source,e.target,e.binding]));
 try{const routed=E.routeBatch(graph,edges.map(e=>e.id),{margin:6,stub:20,bendCost:40,crossingCost:450,overlapCost:2,edgeSpacing:12,sides:'any',style:'orthogonal'}),v=E.validateView(graph);
  const errors=[...v.source.violations,...v.layout.violations,...v.edges.filter(([,v])=>!v.ok).map(([id,v])=>id+': '+v.violations.join(';'))];
  results.push({name,pairs,nodes:nodes.length,edges:edges.length,ok:!routed.failed&&!errors.length,failed:routed.failed,errors,bindingsUnchanged:before===JSON.stringify(edges.map(e=>[e.source,e.target,e.binding])),routes:edges.map(e=>({id:e.id,route:e.route,reason:e.reason}))});
  fs.writeFileSync(path.join(here,'scenes','topology-'+name+'.json'),JSON.stringify(graph));
 }catch(error){results.push({name,ok:false,error:String(error)});}
}
fs.writeFileSync(path.join(here,'topologies.json'),JSON.stringify(results,null,2));console.log(results.map(r=>({name:r.name,ok:r.ok,errors:r.errors,failed:r.failed})));
