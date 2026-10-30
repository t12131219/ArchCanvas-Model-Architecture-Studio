// Static native-frontier benchmark; never imports or executes model Python.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('..',import.meta.url)),base=path.join(root,'studio/public/preview'),ctx=vm.createContext({performance,TextEncoder});
const load=p=>vm.runInContext(fs.readFileSync(path.join(base,p),'utf8'),ctx,{filename:p});
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])load('yworks_edge_router_lab/'+n+'.js');
for(const {path:p}of JSON.parse(fs.readFileSync(path.join(root,'docs/summary-native-view-manifest-20261028.json'))).files)load(p);
load('yworks_edge_router_lab/studio-semantic.js');
const G=ctx.SummaryNativeSemantic,N=ctx.ArchCanvasSemanticView,stats={};
for(const [name,obj,keys]of [['layout',ctx.SemanticLayout,['layout']],['projection',ctx.SummarySourceRuntime,['project']],['publication',ctx.SemanticPublication,['project','projectCanonical']],['engine',ctx.SemanticEngine,['project']]])for(const key of keys){const fn=obj[key];obj[key]=function(...args){const start=performance.now();try{return fn.apply(this,args);}finally{const row=stats[name+'.'+key]??={calls:0,ms:0};row.calls++;row.ms+=performance.now()-start;}};}
const catalog=JSON.parse(fs.readFileSync(path.join(base,'data/semantic/studio-catalog.json'))),models=catalog.models.filter(m=>m.title==='Transformer · 语义架构'||m.title==='MultilayerPerceptron · mlp');
const report={renderer:G.VERSION,modelExecution:false,rows:[]};
for(const model of models){
 const ir=JSON.parse(fs.readFileSync(path.join(base,'data/semantic',model.ir.path))),options={refineCrossings:false,refinePlacement:false,refineChannels:false,refineFlow:false},original=JSON.stringify(ir);
 let graph;
 const run=(label,transition)=>{for(const key of Object.keys(stats))delete stats[key];const start=performance.now();const result=N.prepare(graph?{task:'frontier',graph,transition,options}:{task:'generic-build',ir,state:G.initial(ir),options});graph=result.graph;const row={model:model.title,label,ms:Math.round(performance.now()-start),timing:result.timing,nodes:graph.nodes.length,edges:graph.edges.length,pending:result.pending,failed:result.failed,valid:N.accepts(graph,result.validation),phases:JSON.parse(JSON.stringify(stats))};report.rows.push(row);console.log(JSON.stringify(row));if(!row.valid||JSON.stringify(graph.generic.ir)!==original)throw Error('Frontier validity/source changed');};
 run('initial');
 const target=graph.nodes.find(n=>n.expanded&&!n.modelHeading&&G.children(graph,n.id).length>=3&&G.children(graph,n.id).length<=15);
 if(target)for(let i=0;i<3;i++){run('collapse-'+i,{type:'toggle',id:target.id,expanded:false});run('expand-'+i,{type:'toggle',id:target.id,expanded:true});}
}
if(process.argv[2])fs.writeFileSync(process.argv[2],JSON.stringify(report,null,2)+'\n');
