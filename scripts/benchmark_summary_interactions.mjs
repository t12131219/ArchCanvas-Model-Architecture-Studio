import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(process.argv[2]||fileURLToPath(new URL('..',import.meta.url))),out=process.argv[3];
const base=path.join(root,'studio/public/preview'),ctx=vm.createContext({performance,TextEncoder});
const load=p=>vm.runInContext(fs.readFileSync(path.join(base,p),'utf8'),ctx,{filename:p});
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])load('yworks_edge_router_lab/'+n+'.js');
for(const row of JSON.parse(fs.readFileSync(path.join(root,'docs/summary-native-view-manifest-20261028.json'))).files)load(row.path);
for(const n of ['studio-shared-source','studio-semantic'])load('yworks_edge_router_lab/'+n+'.js');
const G=ctx.SummaryNativeSemantic,N=ctx.ArchCanvasSemanticView,E=ctx.SummaryEngine,rows=[];
function time(name,fn){const t=performance.now(),value=fn();const row={name,ms:+(performance.now()-t).toFixed(2)};rows.push(row);console.log(JSON.stringify(row));return value;}
const catalog=JSON.parse(fs.readFileSync(path.join(base,'data/semantic/studio-catalog.json')));
for(const id of (process.argv[4]||'d6df94c94e8a5888,0216717d966327f4').split(',')){
 const m=catalog.models.find(m=>m.id===id),ir=JSON.parse(fs.readFileSync(path.join(base,'data/semantic',m.ir.path))),state=m.presentation?JSON.parse(fs.readFileSync(path.join(base,'data/semantic',m.presentation.path))).default_state:N.state('overview');
 let r=time(id+':initial',()=>N.prepare({task:'generic-build',ir,state,options:{}})),graph=r.graph;
 rows.at(-1).valid=N.accepts(graph,r.validation);rows.at(-1).nodes=graph.nodes.length;
 const target=graph.nodes.find(n=>n.expanded&&n.parent&&G.children(graph,n.id).length)||graph.nodes.find(n=>n.expanded);
 if(target){
  for(const expanded of [false,true]){r=time(id+':toggle:'+expanded,()=>N.prepare({task:'frontier',graph,transition:{type:'toggle',id:target.id,expanded},options:{}}));graph=r.graph;Object.assign(rows.at(-1),{nodes:graph.nodes.length,valid:N.accepts(graph,r.validation),strict:r.validation.source.ok&&r.validation.layout.ok&&r.validation.edges.every(([,v])=>v.ok),pending:graph.nativeRouting?.pending,failed:graph.nativeRouting?.failed,timing:r.timing,reuse:graph.nativeRouteReuse});console.log(JSON.stringify(r.timing));}
 }
 const leaf=graph.nodes.find(n=>!n.expanded&&!n.modelHeading&&n.parent);
 if(leaf){const moved=G.cloneGeometry(graph);time(id+':move',()=>E.move(moved,leaf.id,8,0,{}));Object.assign(rows.at(-1),{blocked:moved.lastMove?.blocked,dx:moved.nodes.find(n=>n.id===leaf.id).x-leaf.x});const check=time(id+':move-validation',()=>E.validateView(moved));rows.at(-1).strict=check.source.ok&&check.layout.ok&&check.edges.every(([,v])=>v.ok);}
 for(const name of ['inspector','remember','snapshot'])time(id+':'+name,()=>name==='inspector'?N.inspector(graph,[]):name==='remember'?G.remember(graph):N.snapshot(graph));
 const pool=ctx.ArchCanvasSharedSource.pool();time(id+':host-copy',()=>pool.copy({graph,semanticView:N.inspector(graph,[])}));
 time(id+':serialized-bytes',()=>JSON.stringify(graph));rows.at(-1).bytes=JSON.stringify(graph).length;
 if(process.argv[5]==='levels'){
  const module=ir.nodes.find(n=>n.label==='self.encode')||ir.nodes.find(n=>n.kind==='composite'&&!n.parent);
  for(const depth of [0,1,2,3]){
   r=time(id+':source-depth:'+depth,()=>N.prepare({task:'frontier',graph,transition:{type:'module',request:{ids:[module.id],level:'source',depth,replaceDescendants:true}},options:{}}));graph=r.graph;
   Object.assign(rows.at(-1),{nodes:graph.nodes.length,strict:r.validation.source.ok&&r.validation.layout.ok&&r.validation.edges.every(([,v])=>v.ok),pending:graph.nativeRouting?.pending,failed:graph.nativeRouting?.failed,timing:r.timing,reuse:graph.nativeRouteReuse});console.log(JSON.stringify(rows.at(-1)));
  }
 }
}
if(out)fs.writeFileSync(out,JSON.stringify({rows},null,2)+'\n');
