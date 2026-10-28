import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const base=new URL('../public/preview/',import.meta.url),ctx=vm.createContext({performance});
const load=(path:string)=>vm.runInContext(readFileSync(new URL(path,base),'utf8'),ctx,{filename:path});
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])load(`yworks_edge_router_lab/${n}.js`);
for(const row of JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json',import.meta.url),'utf8')).files)load(row.path);
load('yworks_edge_router_lab/studio-semantic.js');
const G=ctx.SummaryNativeSemantic,F=ctx.SemanticCompositionLayout,N=ctx.ArchCanvasSemanticView;
const catalog=JSON.parse(readFileSync(new URL('data/semantic/studio-catalog.json',base),'utf8'));
const read=(model:any)=>JSON.parse(readFileSync(new URL('data/semantic/'+model.ir.path,base),'utf8'));
const signature=(cut:any)=>({nodes:cut.nodes.map((n:any)=>[n.id,n.parent,n.paper,n.contract_stage,n.role_path_stage,cut.positions.get(n.id).expanded]).sort(),
 edges:cut.edges.map((e:any)=>[e.id,e.source,e.target,e.source_port,e.target_port,e.kind,e.condition,e.originals,e.bundle_members,e.design_route]).sort()});
const equal=(a:any,b:any,label:string)=>assert.equal(G.stable(a),G.stable(b),label);
for(const model of catalog.models)test(`presentation matches original whole-model frontier: ${model.title}`,()=>{
 const ir=read(model),root=ir.nodes.find((n:any)=>!n.parent&&n.kind==='composite'&&n.id!=='runtime-observations');
 for(const level of ['f0','f1']){
  let state=F.frontier({mode:'source'},level==='f0'?'overview':'detail');if(level==='f1')state=F.certifiedDetails(ir,state,{semanticOnly:true});
  const expected=G.project(ir,state),actual=G.project(ir,{...N.state('overview'),moduleCuts:[{id:root.id,level}]});
  equal(signature(actual),signature(expected),model.title+' '+level+' presentation');
 }
});
const model=catalog.models.find((m:any)=>m.id==='0216717d966327f4'),ir=read(model),encode='model/470:4:composite:1/445:4:composite:1',decode='model/470:4:composite:1/453:4:composite:1';
test('Transformer sibling F1 cuts preserve five Add & Norm stages, attention paths and exact original layout',()=>{
 const state=F.certifiedDetails(ir,N.state('detail'),{semanticOnly:true}),original=G.build(ir,state);
 const mixed=G.build(ir,{...N.state('overview'),moduleCuts:[{id:encode,level:'f1'},{id:decode,level:'f1'}]});
 equal(signature(G.expected(mixed)),signature(G.expected(original)),'same-level sibling structure');
 const geometry=(g:any)=>g.nodes.map((n:any)=>[n.id,n.parent,n.x,n.y,n.w,n.h,n.expanded,n.fill]).sort();
 equal(geometry(mixed),geometry(original),'same-level sibling geometry');
 assert.equal(mixed.nodes.filter((n:any)=>n.semantic.contract_stage).length,5);
 assert.equal(mixed.nodes.filter((n:any)=>n.semantic.semantic_type==='multihead-attention'&&n.expanded).length,3);
 for(const stage of mixed.nodes.filter((n:any)=>n.semantic.contract_stage)){
  assert.equal(stage.expanded,true);
  for(const id of stage.semantic.canonical_members)assert.equal(G.expected(mixed).idx.nodes.get(id).parent,stage.id);
 }
});
test('mixed F1/F0 retains complete local stages and does not route through removed groups',()=>{
 const graph=G.build(ir,{...N.state('overview'),moduleCuts:[{id:encode,level:'f1'},{id:decode,level:'f0'}]}),cut=G.expected(graph);
 assert.equal(graph.nodes.filter((n:any)=>n.semantic.contract_stage).length,5);
 assert.equal(graph.nodes.filter((n:any)=>n.semantic.contract_stage&&n.expanded).length,2);
 assert.equal(graph.nodes.filter((n:any)=>n.semantic.semantic_type==='multihead-attention'&&n.expanded).length,1);
 const ids=new Set(graph.nodes.map((n:any)=>n.id));for(const edge of cut.edges){assert.ok(ids.has(edge.source));assert.ok(ids.has(edge.target));}
 let result=N.prepare({task:'generic-route',graph,options:{budgetMs:8000}});
 for(let pass=0;pass<2&&!N.inspector(result.graph).routing.complete;pass++)result=N.prepare({task:'generic-route',graph:result.graph,options:{budgetMs:8000}});
 assert.equal(N.accepts(result.graph,result.validation),true);
 assert.equal(N.inspector(result.graph).routing.complete,true,'small mixed view must finish routing');
});
test('v15 saved mixed graphs and portable documents rebuild without reusing broken geometry',()=>{
 const graph=G.build(ir,{...N.state('overview'),moduleCuts:[{id:encode,level:'f1'},{id:decode,level:'f0'}]});
 graph.generic.version='native-semantic/15';const state=G.stable(graph.generic.state),facts=G.stable(graph.generic.ir);
 // Reproduce the damaged saved drawing: the old filter removed every group
 // carrying a cut inventory, leaving children with absent presentation parents.
 graph.nodes=graph.nodes.filter((n:any)=>!n.semantic.boundary_ports);
 const upgraded=G.operate(graph,{kind:'upgrade'});
 assert.equal(upgraded.generic.version,G.VERSION);assert.equal(G.stable(upgraded.generic.state),state);assert.equal(G.stable(upgraded.generic.ir),facts);
 assert.equal(upgraded.generic.migration.previousRenderer,'native-semantic/15');assert.ok(upgraded.generic.migration.previousNativeLayout);
 assert.equal(upgraded.nodes.filter((n:any)=>n.semantic.contract_stage).length,5);
 const doc=G.document(graph),parsed=G.read(doc);assert.equal(parsed.nativeLayout,null);assert.deepEqual(Array.from(parsed.layouts),[]);
 const small=G.build(read(catalog.models.find((m:any)=>m.title==='MultilayerPerceptron · mlp')),N.state('overview'));
 const unchanged=G.document(small);unchanged.renderer='native-semantic/15';
 equal(G.read(unchanged).nativeLayout,unchanged.nativeLayout,'unaffected v15 custom positions remain portable');
});
