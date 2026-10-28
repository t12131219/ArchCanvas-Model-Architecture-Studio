/* Reproducible, read-only semantic audit. No Python model is executed. */
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const project=path.resolve(__dirname,'../..'),base=path.join(project,'studio/public/preview'),ctx=vm.createContext({performance});
const load=p=>vm.runInContext(fs.readFileSync(path.join(base,p),'utf8'),ctx,{filename:p});
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])load(`yworks_edge_router_lab/${n}.js`);
for(const row of JSON.parse(fs.readFileSync(path.join(project,'docs/summary-native-view-manifest-20261028.json'))).files)load(row.path);
load('yworks_edge_router_lab/studio-semantic.js');
const G=ctx.SummaryNativeSemantic,N=ctx.ArchCanvasSemanticView,S=ctx.SummarySourceRuntime;
const catalog=JSON.parse(fs.readFileSync(path.join(base,'data/semantic/studio-catalog.json'))),rows=[];
const output=path.resolve(process.argv[2]||path.join(project,'docs/evidence/summary-all-cases-progressive-20261028/semantic-audit.json'));
function check(ir,state){
 const cut=G.project(ir,state),visible=new Set(cut.nodes.map(n=>n.id));
 for(const [key,raw]of [['node_accounting',ir.nodes],['edge_accounting',ir.edges]]){const ids=Object.values(cut[key]).flat();assert.equal(ids.length,new Set(ids).size,key+' duplicates');assert.equal(G.stable([...ids].sort()),G.stable(raw.map(n=>n.id).sort()),key+' exact inventory');}
 for(const n of cut.nodes){assert.ok(cut.positions.has(n.id),n.id+' missing position');if(n.parent)assert.ok(visible.has(n.parent),n.id+' missing owner');}
 for(const e of cut.edges){assert.ok(visible.has(e.source)&&visible.has(e.target),e.id+' missing endpoint');}
 return cut;
}
for(const model of catalog.models){
 const ir=JSON.parse(fs.readFileSync(path.join(base,'data/semantic',model.ir.path))),unchanged=G.stable(ir),state=N.state('overview'),root=ir.nodes.find(n=>!n.parent&&n.kind==='composite'&&n.id!=='runtime-observations');
 const mods=S.moduleIndex(ir).filter(n=>n.id!==root.id&&!n.id.includes('runtime')&&!n.id.startsWith('R/')).sort((a,b)=>b.count-a.count),a=mods[0]||{id:root.id},b=mods.find(n=>n.id!==a.id&&!n.id.startsWith(a.id+'/')&&!a.id.startsWith(n.id+'/'));
 const baseline=check(ir,state),stages=[];
 const within=(id,owner,idx)=>{const seen=new Set();while(id&&!seen.has(id)){if(id===owner)return true;seen.add(id);id=idx.nodes.get(id)?.parent;}return false;};
 for(const level of S.levels){const depths=level==='source'?[0,1,2,3,4,undefined]:[undefined];for(const depth of depths){
  const cuts=[{id:a.id,level,...(depth===undefined?{}:{depth})}];if(b)cuts.push({id:b.id,level:'f0'});
  const cut=check(ir,{...state,moduleCuts:cuts});
  if(b){const expected=check(ir,{...state,moduleCuts:[{id:b.id,level:'f0'}]});const keys=c=>c.nodes.filter(n=>within(n.id,b.id,c.idx)).map(n=>[n.id,n.parent,!!c.positions.get(n.id)?.expanded]).sort();assert.equal(G.stable(keys(cut)),G.stable(keys(expected)),'sibling F0 must survive '+level);}
  stages.push({level,depth:depth??'all',nodes:cut.nodes.length,edges:cut.edges.length});
 }}
 const finalState={...state,moduleCuts:[{id:root.id,level:'source'}]},full=check(ir,finalState),graph=G.build(ir,finalState);assert.equal(G.validate(graph,true).ok,true,'source bindings and owners');
 const raw=new Map(ir.edges.map(e=>[e.id,e]));let exactOperands=0;
 for(const e of graph.edges){const original=raw.get(e.id);if(original&&!e.binding.bundle_members&&!e.binding.runtime_bridge){for(const k of ['source','target','source_port','target_port'])assert.equal(e.binding[k],original[k],e.id+' '+k);exactOperands++;}}
 assert.equal(G.stable(ir),unchanged,'audit must not mutate imported source IR');
 rows.push({id:model.id,title:model.title,rawNodes:ir.nodes.length,rawEdges:ir.edges.length,root:root.id,moduleA:a.id,moduleB:b?.id,baseline:{nodes:baseline.nodes.length,edges:baseline.edges.length},stages,source:{nodes:full.nodes.length,edges:full.edges.length,canvas:graph.canvas,exactOperands,valid:true},sourceUnchanged:true});
 fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify({schema:'summary-all-cases-audit/1',scope:'Imported canonical IR, not independently executed Python',models:rows},null,2));console.log(model.title,full.nodes.length,full.edges.length,'PASS');
}
console.log('PASS',rows.length,'models',rows.reduce((n,m)=>n+m.stages.length,0),'mixed stages');
