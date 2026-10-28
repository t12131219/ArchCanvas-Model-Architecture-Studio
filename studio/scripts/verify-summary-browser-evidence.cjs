/* Match screenshots' DOM inventory to a fresh projection of canonical IR. */
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const project=path.resolve(__dirname,'../..'),base=path.join(project,'studio/public/preview'),dir=path.resolve(process.argv[2]||path.join(project,'docs/evidence/summary-all-cases-progressive-20261028')),ctx=vm.createContext({performance});
const load=p=>vm.runInContext(fs.readFileSync(path.join(base,p),'utf8'),ctx,{filename:p});
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])load(`yworks_edge_router_lab/${n}.js`);
for(const row of JSON.parse(fs.readFileSync(path.join(project,'docs/summary-native-view-manifest-20261028.json'))).files)load(row.path);
load('yworks_edge_router_lab/studio-semantic.js');
const G=ctx.SummaryNativeSemantic,N=ctx.ArchCanvasSemanticView,catalog=JSON.parse(fs.readFileSync(path.join(base,'data/semantic/studio-catalog.json'))),results=[];
const unique=new Map(JSON.parse(fs.readFileSync(path.join(dir,'browser-index.json'))).map(r=>[r.file,r]));
// Presentation coordinates and the currently rendered endpoint are mutable;
// operands, source identities and trace evidence must compare exactly.
function canonicalBinding(binding){const b=JSON.parse(JSON.stringify(binding||{}));for(const k of ['points','explicit_sides','port_authority'])delete b[k];if(b.endpoint_binding){for(const k of ['src','dst'])delete b[k];for(const k of ['rendered_src','rendered_dst'])delete b.endpoint_binding[k];}return G.stable(b);}
function complete(row,data){assert.equal(data.source,'true',row.file+' source validation');assert.equal(data.layout,'true',row.file+' layout validation');assert.equal(data.invalid,0,row.file+' unfinished or invalid routes');}
for(const row of unique.values()){
 const model=catalog.models.find(m=>m.id===row.model.id);if(!model)continue;
 const data=JSON.parse(fs.readFileSync(path.join(dir,row.file+'.json'))),ir=JSON.parse(fs.readFileSync(path.join(base,'data/semantic',model.ir.path))),state={...N.state('overview')},a=data.meta.a,b=data.meta.b;
 complete(row,data);
 if(data.meta.state)Object.assign(state,data.meta.state);
 else if(row.stage==='02-module-f1')state.moduleCuts=[{id:a,level:'f1'}];
 else if(row.stage==='03-module-detailed')state.moduleCuts=[{id:a,level:'detailed'}];
 else if(row.stage==='04-module-source-depth1')state.moduleCuts=[{id:a,level:'source',depth:1}];
 else if(row.stage==='04b-sibling-semantic')state.moduleCuts=[{id:a,level:'source',depth:1},{id:b,level:'semantic'}];
 else if(row.stage.startsWith('05'))state.moduleCuts=[{id:data.meta.root,level:'source'}];
 else if(row.stage!=='01-f0')continue;
 const cut=G.project(ir,state);assert.equal(data.mode,'source',row.file+' mode');
 assert.equal(G.stable([...data.ids].sort()),G.stable(cut.nodes.map(n=>n.id).sort()),row.file+' DOM node inventory');
 const by=new Map(cut.edges.map(e=>[e.id,e]));assert.equal(data.edgeBindings.length,by.size,row.file+' edge count');
 for(const edge of data.edgeBindings){assert.ok(by.has(edge.id),row.file+' unknown edge');assert.equal(G.stable(edge.binding),G.stable(by.get(edge.id)),row.file+' exact operands '+edge.id);}
 assert.ok(fs.statSync(path.join(dir,row.file+'.png')).size>1000,'screenshot missing');results.push({file:row.file,model:row.model,stage:row.stage,nodes:data.nodes,edges:data.edges,semanticMatch:true,source:data.source,layout:data.layout,invalid:data.invalid});
}
const nativeCount=results.length,nativeModels=new Set(results.map(r=>r.model.id)).size;
ctx.window=ctx;const F=ctx.SummaryRecursive,C=ctx.SummaryConstraints,registered=JSON.parse(fs.readFileSync(path.join(base,'data/summary-cases.json'))).cases;
for(const model of registered){
 const descriptors=model.routeTemplates?[...model.views,...model.routeTemplates]:model.sourceAtomic?[...model.views,...['overview','modules','detailed'].map(key=>({key,asset:'data/cases/01093cc06a87b35a-'+key+'.js',dataKey:'01093cc06a87b35a:'+key}))]:model.views;
 const sources={};for(const v of descriptors){load(v.asset);sources[v.key]=C.initialize(ctx.SummaryCaseData[v.dataKey||model.id+':'+v.key]);}
 for(const row of unique.values()){
  if(row.model.id!==model.id||row.kind==='authoring-ui')continue;
  const data=JSON.parse(fs.readFileSync(path.join(dir,row.file+'.json'))),ids=new Set(data.ids),doc=F.create(sources),all=doc.authority.detail.nodes;
  complete(row,data);
  // Reconstruct visibility from the DOM, then require the complete licensed
  // child set and exact canonical bindings. A screenshot cannot omit one
  // branch or invent a source identity and still match this projection.
  doc.state.open=F.containers(doc.authority).filter(id=>all.some(n=>n.parent===id&&ids.has(n.id)));
  doc.state.folded=F.containers(doc.authority).filter(id=>!doc.state.open.includes(id));doc.state.moduleCuts=[{id:all.find(n=>!n.parent).id,level:'source'}];
  const graph=F.build(doc);assert.equal(G.stable([...ids].sort()),G.stable(graph.nodes.map(n=>n.id).sort()),row.file+' registered hierarchy');
  const by=new Map(graph.edges.map(e=>[e.id,e]));assert.equal(data.edgeBindings.length,by.size,row.file+' registered dependencies');
  for(const edge of data.edgeBindings){assert.ok(by.has(edge.id),row.file+' unregistered edge');assert.equal(canonicalBinding(edge.binding),canonicalBinding(by.get(edge.id).binding),row.file+' canonical registered binding '+edge.id);}
  assert.ok(fs.statSync(path.join(dir,row.file+'.png')).size>1000,'screenshot missing');results.push({file:row.file,model:row.model,stage:row.stage,nodes:data.nodes,edges:data.edges,semanticMatch:true,source:data.source,layout:data.layout,invalid:data.invalid,registered:true});
 }
}
fs.writeFileSync(path.join(dir,'browser-verification.json'),JSON.stringify({schema:'summary-browser-evidence-verification/2',checked:results.length,models:new Set(results.map(r=>r.model.id)).size,nativeCount,nativeModels,results},null,2));console.log('PASS',results.length,'screenshots from',new Set(results.map(r=>r.model.id)).size,'models;',nativeCount,'native screenshots from',nativeModels,'native models');
