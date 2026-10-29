// Check the current native catalog without executing any model source.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
const root=path.resolve(process.argv[2]||fileURLToPath(new URL('..',import.meta.url))),output=process.argv[3];
if(!output)throw Error('An explicit evidence JSON path is required');
const base=path.join(root,'studio/public/preview'),context=vm.createContext({performance,TextEncoder});
const load=p=>vm.runInContext(fs.readFileSync(path.join(process.env.ARCHCANVAS_AUDIT_ASSETS||base,p),'utf8'),context,{filename:p});
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])load('yworks_edge_router_lab/'+n+'.js');
for(const row of JSON.parse(fs.readFileSync(path.join(root,'docs/summary-native-view-manifest-20261028.json'))).files)load(row.path);
load('yworks_edge_router_lab/studio-semantic.js');
const N=context.ArchCanvasSemanticView,G=context.SummaryNativeSemantic,P=context.SummaryPhysicalPorts,R=context.EdgeRouterLabRouting;
const options={firstLegal:true,refineCrossings:false,refinePlacement:false,refineChannels:false,refineFlow:false};
const catalog=JSON.parse(fs.readFileSync(path.join(base,'data/semantic/studio-catalog.json'))),rows=[];
const bundles=process.argv[4]==='--bundles-only';
const models=bundles?process.argv.slice(5).map(p=>{const bundle=JSON.parse(fs.readFileSync(p));return {id:bundle.id,title:bundle.entry,ir:bundle.ir.semantic_ir};}):catalog.models;
const report={schema:'archcanvas-native-connection-audit/1',renderer:G.VERSION,modelExecution:false,scope:bundles?'Recorded supplemental source-inspection bundles; F0, F1, source depth 1 and bounded full/nested expansion':'43 catalog configurations; F0, F1, source depth 1; full source expansion for IR <= 300 nodes; sampled nested source expansion for larger IR',rows};
const flush=()=>fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
function check(model,view,result){
 const graph=result.graph,ports=P.context(graph),by=new Map(graph.nodes.map(n=>[n.id,n])),errors=[];
 for(const e of graph.edges){
  if(!by.has(e.source)||!by.has(e.target)){errors.push(e.id+': missing endpoint');continue;}
  errors.push(...P.errors(graph,e,e.route,ports).map(v=>e.id+': '+v));
  const displayed=context.SummaryEngine.displayed(graph,e);
  for(const [side,index]of [['source',0],['target',-1]])if(!displayed.length||R.dist(displayed.at(index),P.point(by.get(e[side]),P.active(e,side)))>1e-5)errors.push(e.id+': displayed '+side+' detached');
  if(e.binding?.kind==='source-inspection'&&e.binding.syntaxOnly&&by.get(e.target).expanded){
   const next=graph.edges.filter(v=>v.source===e.target&&v.binding?.kind==='source-inspection'&&v.binding.syntaxOnly);
   const incoming=graph.edges.filter(v=>v.target===e.target&&v.binding?.kind==='source-inspection'&&v.binding.syntaxOnly);
   if(incoming.length===1&&next.length===1&&by.get(e.source).parent===e.target&&by.get(e.target).parent===next[0].target&&R.dist(e.route.at(-1),next[0].route[0])>1e-5)errors.push(e.id+': disconnected nested inspection interface');
  }
 }
 const row={id:model.id,title:model.title,view,nodes:graph.nodes.length,edges:graph.edges.length,sourceValid:result.validation.source.ok,layoutValid:result.validation.layout.ok,sourceErrors:result.validation.source.violations,layoutErrors:result.validation.layout.violations,endpointErrors:errors,inspectionEdges:graph.edges.filter(e=>e.binding?.kind==='source-inspection').length,pending:graph.nativeRouting?.pending||0,failed:graph.nativeRouting?.failed||0,strictRouting:result.validation.edges.every(([,v])=>v.ok)};
 row.routeMs=result.timing?.routeMs;row.routeErrors=result.validation.edges.filter(([,v])=>!v.ok);rows.push(row);flush();console.log(JSON.stringify({id:row.id,view,nodes:row.nodes,errors:errors.length,pending:row.pending,failed:row.failed}));
}
for(const model of models){
 try{
  const ir=bundles?model.ir:JSON.parse(fs.readFileSync(path.join(base,'data/semantic',model.ir.path))),rootModule=ir.nodes.find(n=>n.kind==='composite'&&!n.parent);
  let result=N.prepare({task:'generic-build',ir,state:N.state('overview'),options});check(model,'F0',result);
  result=N.prepare({task:'frontier',graph:result.graph,transition:{type:'preset',preset:'detail'},options});check(model,'F1',result);
  if(rootModule){result=N.prepare({task:'frontier',graph:result.graph,transition:{type:'module',request:{ids:[rootModule.id],level:'source',depth:1,replaceDescendants:true}},options});check(model,'source-depth-1',result);}
  if(ir.nodes.length<=300){result=N.prepare({task:'frontier',graph:result.graph,transition:{type:'all',expanded:true},options});check(model,'all-source',result);}
  else {
   const module=ir.nodes.find(n=>n.label==='self.encode')||ir.nodes.find(n=>n.kind==='composite'&&n.parent);
   if(module){result=N.prepare({task:'frontier',graph:result.graph,transition:{type:'module',request:{ids:[module.id],level:'source',depth:2,replaceDescendants:true}},options});check(model,'sampled-nested-source-depth-2',result);}
  }
 }catch(error){rows.push({id:model.id,title:model.title,error:error.stack});flush();console.log(JSON.stringify({id:model.id,error:error.message}));}
}
report.summary={configurations:models.length,views:rows.length,errors:rows.filter(r=>r.error||r.endpointErrors?.length||!r.sourceValid||!r.layoutValid||r.pending||r.failed||!r.strictRouting).length,viewsWithPendingRoutes:rows.filter(r=>r.pending).length,viewsWithFailedRoutes:rows.filter(r=>r.failed).length};
report.status=report.summary.errors?'failed':'passed-strict-routing-audit';flush();console.log(JSON.stringify(report.summary));
if(report.summary.errors)process.exitCode=1;
