// Standalone benchmark for the vendored Apply/layout engine; no prototype runtime.
import fs from 'node:fs';import path from 'node:path';import vm from 'node:vm';import {fileURLToPath} from 'node:url';
const root=path.resolve(process.argv[2]||fileURLToPath(new URL('..',import.meta.url))),mode=process.argv[3]||'optimized',cold=process.argv[4]==='cold',output=process.argv[5];
const base=path.join(root,'studio/public/preview'),ctx=vm.createContext({performance,TextEncoder});
function load(p){vm.runInContext(fs.readFileSync(path.join(base,p),'utf8'),ctx,{filename:p});}
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph','source-controls'])load('yworks_edge_router_lab/'+n+'.js');
for(const r of JSON.parse(fs.readFileSync(path.join(root,'docs/summary-native-view-manifest-20261028.json'))).files)load(r.path);load('yworks_edge_router_lab/studio-semantic.js');
const N=ctx.ArchCanvasSemanticView,E=ctx.SummaryEngine,models=JSON.parse(fs.readFileSync(path.join(base,'data/semantic/studio-catalog.json'))).models,m=models.find(m=>m.id==='0216717d966327f4');
const ir=JSON.parse(fs.readFileSync(path.join(base,'data/semantic',m.ir.path))),state=JSON.parse(fs.readFileSync(path.join(base,'data/semantic',m.presentation.path))).default_state;
let graph=N.prepare({task:'generic-build',ir,state,options:{}}).graph;if(cold)graph=JSON.parse(JSON.stringify(graph));
const ids=graph.edges.map(e=>e.id),beforeNodes=JSON.stringify(graph.nodes),beforeBindings=JSON.stringify(graph.edges.map(e=>e.binding)),rows=[];
const options={margin:6,stub:28,bendCost:40,crossingCost:450,overlapCost:2,edgeSpacing:12,preserve:false,sides:'any',grid:0,style:'orthogonal',optimizeReadability:true};
console.log(JSON.stringify({phase:'start',mode,cold,nodes:graph.nodes.length,edges:graph.edges.length}));
for(let batch=1;batch<=5;batch++){
 const start=performance.now(),r=mode==='baseline'?E.routeBatch(graph,ids,options):E.optimizeRoutes(graph,ids,options);graph=r.graph;
 const row={batch,ms:performance.now()-start,routed:r.routed,retained:r.retained,failed:r.failed,pending:r.optimization?.pendingIds.length||0,checked:r.optimization?.checked,timing:r.optimization?.timing};rows.push(row);console.log(JSON.stringify(row));
 const v=r.validation||E.validateView(graph);if(!v.source.ok||!v.layout.ok||v.edges.some(([,c])=>!c.ok))throw Error('invalid graph');
 if(JSON.stringify(graph.nodes)!==beforeNodes||JSON.stringify(graph.edges.map(e=>e.binding))!==beforeBindings)throw Error('geometry/source changed');
 if(!row.pending)break;
}
if(output)fs.writeFileSync(output,JSON.stringify({mode,cold,nodes:graph.nodes.length,edges:graph.edges.length,valid:true,rows},null,2)+'\n');
