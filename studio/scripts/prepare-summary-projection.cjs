/* Reproduce a routed evidence document without running or editing Python.
 * Native: node ... <model-id> <output.json> '[{"id":"...","level":"source"}]'
 * Registered: the last argument is an array of frontier-task transitions.
 * The resulting JSON is opened with Studio's normal document import dialog.
 */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const [id,output,requests]=process.argv.slice(2);
if(!id||!output)throw Error('Expected model-id output.json [cuts-or-transitions-json]');
const project=path.resolve(__dirname,'../..'),base=path.join(project,'studio/public/preview'),ctx=vm.createContext({performance});ctx.window=ctx;ctx.self=ctx;
const load=p=>vm.runInContext(fs.readFileSync(path.join(base,p),'utf8'),ctx,{filename:p});
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph','frontier-task'])load(`yworks_edge_router_lab/${n}.js`);
for(const row of JSON.parse(fs.readFileSync(path.join(project,'docs/summary-native-view-manifest-20261028.json'))).files)load(row.path);
load('yworks_edge_router_lab/studio-semantic.js');
const catalog=JSON.parse(fs.readFileSync(path.join(base,'data/semantic/studio-catalog.json'))),model=catalog.models.find(m=>m.id===id),steps=[];
const save=(document,suffix='')=>{const file=path.resolve(suffix?output.replace(/\.json$/,'')+suffix+'.json':output);fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(document));};
function verify(result){assert.ok(result.validation.source.ok&&result.validation.layout.ok,'source/layout validation');assert.ok(result.validation.edges.every(([,v])=>v.ok),'every dependency must have a legal route');}
if(model){
 const G=ctx.SummaryNativeSemantic,N=ctx.ArchCanvasSemanticView,ir=JSON.parse(fs.readFileSync(path.join(base,'data/semantic',model.ir.path)));
 const cuts=requests?JSON.parse(requests):[{id:ir.nodes.find(n=>!n.parent&&n.kind==='composite').id,level:'source'}];
 let graph=G.build(ir,{...N.state('overview'),moduleCuts:cuts}),complete=false;
 for(let pass=0;pass<60;pass++){
  const started=performance.now(),result=N.prepare({task:'generic-route',graph,options:{budgetMs:8000}});graph=result.graph;
  const row={pass,ms:performance.now()-started,nodes:graph.nodes.length,edges:graph.edges.length,routing:graph.nativeRouting,invalid:result.validation.edges.filter(([,v])=>!v.ok).length};steps.push(row);console.log(JSON.stringify(row));save(G.document(graph));
  if(graph.nativeRouting.complete){verify(result);complete=true;break;}
 }
 assert.ok(complete,'routing remains incomplete; saved document is a diagnostic, not a passing result');
}else{
 const entry=JSON.parse(fs.readFileSync(path.join(base,'data/summary-cases.json'))).cases.find(c=>c.id===id);assert.ok(entry,'unknown model');
 const templates=entry.routeTemplates||(entry.sourceAtomic?['overview','modules','detailed'].map(key=>({key,asset:'data/cases/01093cc06a87b35a-'+key+'.js',dataKey:'01093cc06a87b35a:'+key})):[]);
 const sources={};for(const v of [...entry.views,...templates]){load(v.asset);sources[v.key]=ctx.SummaryConstraints.initialize(ctx.SummaryCaseData[v.dataKey||id+':'+v.key]);}
 const F=ctx.SummaryRecursive,T=ctx.SummaryFrontierTask;let graph=F.build(F.create(sources));
 const transitions=requests?JSON.parse(requests):[{type:'preset',preset:'overview'}];
 for(const [step,transition]of transitions.entries()){
  const started=performance.now(),result=T.run(graph,transition);verify(result);graph=result.graph;
  const row={step,transition,ms:performance.now()-started,nodes:graph.nodes.length,edges:graph.edges.length,invalid:0};steps.push(row);console.log(JSON.stringify(row));
  const document={schema:'summary-merge-recursive/1',caseId:id,graph,dirty:false,frontierPreset:'custom'};save(document,'-step-'+step);save(document);
 }
}
fs.writeFileSync(path.resolve(output)+'.routing.json',JSON.stringify({model:id,executesPython:false,steps},null,2));
