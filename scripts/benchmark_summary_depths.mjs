import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(process.argv[2]||fileURLToPath(new URL('..',import.meta.url))),out=process.argv[3];
const base=path.join(root,'studio/public/preview'),ctx=vm.createContext({performance,TextEncoder});
const override=process.env.SUMMARY_BENCH_ASSET_OVERRIDE;
const load=p=>{const alternate=override&&path.join(override,path.basename(p));return vm.runInContext(fs.readFileSync(alternate&&fs.existsSync(alternate)?alternate:path.join(base,p),'utf8'),ctx,{filename:p});};
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])load('yworks_edge_router_lab/'+n+'.js');
for(const row of JSON.parse(fs.readFileSync(path.join(root,'docs/summary-native-view-manifest-20261028.json'))).files)load(row.path);
for(const n of ['studio-shared-source','studio-semantic'])load('yworks_edge_router_lab/'+n+'.js');
const G=ctx.SummaryNativeSemantic,N=ctx.ArchCanvasSemanticView,E=ctx.SummaryEngine,rows=[];
function time(name,fn){const t=performance.now(),value=fn();const row={name,ms:+(performance.now()-t).toFixed(2)};rows.push(row);console.log(JSON.stringify(row));return value;}
const catalog=JSON.parse(fs.readFileSync(path.join(base,'data/semantic/studio-catalog.json')));
const id=process.argv[4]||'0216717d966327f4',m=catalog.models.find(m=>m.id===id),ir=JSON.parse(fs.readFileSync(path.join(base,'data/semantic',m.ir.path)));
const strict=v=>v.source.ok&&v.layout.ok&&v.edges.every(([,c])=>c.ok);
const flush=()=>{if(out)fs.writeFileSync(out,JSON.stringify({rows},null,2)+'\n');};
const state=m.presentation?JSON.parse(fs.readFileSync(path.join(base,'data/semantic',m.presentation.path))).default_state:N.state('overview');
let result=time('initial',()=>N.prepare({task:'generic-build',ir,state,options:{}})),graph=result.graph;
const module=ir.nodes.find(n=>n.label===(process.argv[6]||'self.encode'))||ir.nodes.find(n=>n.kind==='composite'&&!n.parent);
for(const level of (process.argv[5]||'0,1,3,5,7,all').split(',')){
 result=time('depth:'+level,()=>N.prepare({task:'frontier',graph,transition:{type:'module',request:{ids:[module.id],level:['f0','f1'].includes(level)?level:'source',...(['all','f0','f1'].includes(level)?{}:{depth:Number(level)}),replaceDescendants:true}},options:{}}));graph=result.graph;
 Object.assign(rows.at(-1),{nodes:graph.nodes.length,edges:graph.edges.length,accepted:N.accepts(graph,result.validation),sourceValid:result.validation.source.ok,layoutValid:result.validation.layout.ok,strict:strict(result.validation),pending:graph.nativeRouting?.pending,failed:graph.nativeRouting?.failed,timing:result.timing});flush();
 for(const name of ['validate','inspector','snapshot','stats','host-copy']){const v=time(level+':'+name,()=>name==='validate'?E.validateView(graph):name==='inspector'?N.inspector(graph,[]):name==='snapshot'?N.snapshot(graph):name==='stats'?ctx.EdgeRouterLabRouting.stats(graph.edges):ctx.ArchCanvasSharedSource.pool().copy({graph,semanticView:N.inspector(graph,[])}));if(name==='validate')rows.at(-1).strict=strict(v);flush();}
 const leaf=graph.nodes.find(n=>!n.expanded&&!n.modelHeading&&n.parent),moved=G.cloneGeometry(graph);
 if(leaf){time(level+':move',()=>E.move(moved,leaf.id,8,0));Object.assign(rows.at(-1),{blocked:moved.lastMove?.blocked,reason:moved.lastMove?.reason,dx:moved.nodes.find(n=>n.id===leaf.id).x-leaf.x});flush();}
}
