import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import {previewHierarchy} from '../src/previewHierarchy.ts';
import {previewPanelDocument,previewMappingSignature,previewMappingCoverage} from '../src/previewPanelDocument.ts';
import {previewUniqueNodeBindings,previewSelectionNodeIds,previewDetailGraph} from '../src/previewInterop.ts';

const base=new URL('../public/preview/',import.meta.url),ctx=vm.createContext({performance});
const script=(path:string)=>vm.runInContext(readFileSync(new URL(path,base),'utf8'),ctx,{filename:path});
for(const name of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])script('yworks_edge_router_lab/'+name+'.js');
for(const row of JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json',import.meta.url),'utf8')).files)script(row.path);
script('yworks_edge_router_lab/studio-semantic.js');
const N=ctx.ArchCanvasSemanticView,G=ctx.SummaryNativeSemantic,E=ctx.SummaryEngine,copy=(v:any)=>JSON.parse(JSON.stringify(v));
const fixture=JSON.parse(readFileSync(new URL('fixtures/preview-formal-ast.json',import.meta.url),'utf8'));
fixture.bundle=JSON.parse((await promisify(execFile)('python3',['-I','-S','-B','-c','import sys,json;sys.path.insert(0,sys.argv[1]);from archcanvas_preview import analyze;v=json.loads(sys.argv[2]);print(json.dumps(analyze(v["files"],v["entry"],semantic_mode="summary")))',fileURLToPath(new URL('../../src/',import.meta.url)),JSON.stringify(fixture.inputs)],{encoding:'utf8',maxBuffer:8_000_000,timeout:30_000})).stdout);
const catalog=JSON.parse(readFileSync(new URL('data/semantic/studio-catalog.json',base),'utf8'));
const irFor=(model:any)=>JSON.parse(readFileSync(new URL('data/semantic/'+model.ir.path,base),'utf8'));
function build(ir:any){return N.decorate(G.build(ir,N.state('overview')));}
function expandedHierarchy(graph:any){return {...graph,semanticHierarchy:{nodes:N.nodes(graph)}};}
function matching(snapshot:any,architecture:any,source:any){return {signature:previewMappingSignature(snapshot),coverage:previewMappingCoverage(snapshot,architecture,source),bindings:[...previewUniqueNodeBindings(architecture,snapshot.graph,source)]};}

test('all 43 canonical models retain identical Studio hierarchy and opaque panel documents with compact navigation rows',()=>{
 for(const model of catalog.models){
  const ir=irFor(model),before=JSON.stringify(ir),graph=build(ir),reference=expandedHierarchy(graph);
  assert.deepEqual(previewHierarchy({graph}),previewHierarchy({graph:reference}),model.title);
  assert.deepEqual(previewPanelDocument({graph}),previewPanelDocument({graph:reference}),model.title);
  assert.equal(JSON.stringify(ir),before);assert.deepEqual(copy(graph.generic.ir),ir);
  assert.deepEqual(graph.semanticHierarchy.nodes.map((n:any)=>n.id),N.nodes(graph).map((n:any)=>n.id));
  assert.ok(graph.semanticHierarchy.nodes.every((n:any)=>!n.html&&!n.semantic?.paper&&!n.semantic?.semantic_contracts));
 }
});

test('multifile shared calls preserve exact formal bindings, evidence spans and ambiguity after compaction',()=>{
 const {bundle,architecture}=fixture,graph=build(bundle.ir.semantic_ir),reference=expandedHierarchy(graph);
 const compact=matching({graph},architecture,bundle),full=matching({graph:reference},architecture,bundle);
 assert.deepEqual(compact,full);assert.ok(compact.bindings.length>0);
 assert.deepEqual(previewPanelDocument({graph},bundle),previewPanelDocument({graph:reference},bundle));
 for(const node of previewDetailGraph(graph).nodes){
  const previous=reference.semanticHierarchy.nodes.find((n:any)=>n.id===node.id);
  assert.deepEqual(previewSelectionNodeIds(architecture,{nodeId:node.id,node},bundle),previewSelectionNodeIds(architecture,{nodeId:node.id,node:previous},bundle));
 }
 assert.deepEqual(copy(graph.generic.ir),bundle.ir.semantic_ir);
});

test('host projection retains explicit aggregate exclusions and source branch/call-site identity fields',()=>{
 const graph=build(fixture.bundle.ir.semantic_ir),raw=G.expected(graph).idx.nodes.values().next().value;
 // Use the native projection boundary with counterexamples carrying matching
 // display IDs: aggregate exclusions must survive even exact ID matching.
 const expected=G.expected;G.expected=()=>({idx:{nodes:new Map([[raw.id,{...raw,presentation_only:false,canonical_members:['first','second'],source_evidence:['proof'],sourceStructure:true,sourceKind:'SourceBranch',instance:'instance:branch',moduleType:'Linear',expression:'self.branch(x)',sourceParameters:{condition:'flag',callSites:[{file:'net/model.py',line:3,endLine:3,expression:'self.branch(x)'}],huge:{payload:'unused'}}}]])}});
 try{
  const row=N.hierarchy(graph)[0];assert.deepEqual(copy(row.semantic.canonical_members),['first','second']);
  assert.equal(row.semantic.sourceParameters.condition,'flag');assert.equal(row.semantic.sourceParameters.callSites[0].file,'net/model.py');
  assert.equal(row.semantic.sourceParameters.huge,undefined);assert.equal(row.semantic.expression,'self.branch(x)');
  const architecture={...fixture.architecture,nodes:[{...fixture.architecture.nodes[0],id:row.id}]};
  assert.deepEqual(previewSelectionNodeIds(architecture,{nodeId:row.id,node:row}),[]);
 }finally{G.expected=expected;}
});

test('3371-node Transformer host hierarchy shrinks without truncation and thirty snapshots share immutable facts',()=>{
 const model=catalog.models.find((m:any)=>m.title==='Transformer · 语义架构'),ir=irFor(model),graph=build(ir);
 const referenceBytes=Buffer.byteLength(JSON.stringify(N.nodes(graph))),compactBytes=Buffer.byteLength(JSON.stringify(graph.semanticHierarchy.nodes));
 assert.equal(graph.generic.ir.nodes.length,3371);assert.equal(graph.generic.ir.edges.length,3663);
 assert.ok(compactBytes<referenceBytes*.15,JSON.stringify({referenceBytes,compactBytes}));
 const snapshots=Array.from({length:30},()=>N.snapshot(graph));
 assert.equal(new Set(snapshots.map((g:any)=>g.generic.ir)).size,1);
 assert.equal(new Set(snapshots.map((g:any)=>g.generic.receipts)).size,1);
 assert.equal(new Set(snapshots.map((g:any)=>g.nodes)).size,30);
 snapshots[0].nodes[0].x+=100;assert.notEqual(snapshots[0].nodes[0].x,snapshots[1].nodes[0].x);
 assert.deepEqual(copy(snapshots[1].generic.ir),ir);
});

test('native snapshots isolate geometry, routes, overlays, drafts and layouts while shared source fields reject mutation',()=>{
 const graph=build(fixture.bundle.ir.semantic_ir);graph.studioPresentation={nodes:{sample:{alias:'before'}}};
 graph.sourceDraftOperations=[{id:'draft',route:[{x:10,y:20}]}];graph.generic.layouts=[{nodes:[{id:'sample',x:1}]}];
 const snapshot=N.snapshot(graph),saved=JSON.stringify(snapshot);
 for(const field of ['ir','state','receipts','navigation']){assert.equal(snapshot.generic[field],graph.generic[field]);assert.equal(Object.isFrozen(graph.generic[field]),true);}
 assert.throws(()=>{snapshot.generic.ir.nodes[0].label='forged';},TypeError);
 graph.nodes[0].x+=100;graph.edges[0].route[0].x+=100;graph.studioPresentation.nodes.sample.alias='after';
 graph.sourceDraftOperations[0].route[0].x=100;graph.generic.layouts[0].nodes[0].x=100;
 assert.equal(JSON.stringify(snapshot),saved);
 const forged=copy(snapshot);forged.edges[0].binding.target_port='invented';
 assert.equal(E.validateView(forged).source.ok,false,'sharing does not create serialized trust');
 const next=build({...copy(graph.generic.ir),title:'another source generation'}),nextSnapshot=N.snapshot(next);
 assert.notEqual(snapshot.generic.ir,nextSnapshot.generic.ir);assert.equal(snapshot.generic.ir.title,fixture.bundle.ir.semantic_ir.title);
});

test('legacy snapshots retain independent mutable source objects',()=>{
 const graph={nodes:[{id:'legacy',semantic:{label:'original'}}],recursive:{authority:{detail:{nodes:[{id:'legacy'}]}}}};
 const snapshot=N.snapshot(graph);graph.nodes[0].semantic.label='edited';graph.recursive.authority.detail.nodes[0].id='other';
 assert.equal(snapshot.nodes[0].semantic.label,'original');assert.equal(snapshot.recursive.authority.detail.nodes[0].id,'legacy');
});

test('actual native save, undo and redo handlers use isolated shared-evidence snapshots with the existing history cap',()=>{
 const app=readFileSync(new URL('yworks_edge_router_lab/app.js',base),'utf8'),buttons:any={},graph=build(fixture.bundle.ir.semantic_ir);
 const env=vm.createContext({graph,history:[],future:['old'],camera:{x:1,y:2,w:800,h:600},busy:false,drag:null,N,E,
  selectedNodes:new Set(),selectedEdges:new Set(),selectedAnnotation:null,connection:null,dirty:false,ghost:[],render(){},persist(){},cameraUpdate(){},studioBridge:{state(){}},$:(id:string)=>buttons[id]||(buttons[id]={})});
 vm.runInContext(app.slice(app.indexOf('  function save(){'),app.indexOf('  function flushPersist(){')),env);
 vm.runInContext(app.slice(app.indexOf("  $('undo').onclick="),app.indexOf("  $('reset').onclick=")),env);
 for(let i=0;i<35;i++){env.save();env.graph.nodes[0].x+=1;}
 assert.equal(env.history.length,30);assert.equal(env.future.length,0);
 const saved=env.history.at(-1),x=env.graph.nodes[0].x;
 assert.equal(saved.generic.ir,env.graph.generic.ir);assert.equal(saved.nodes[0].x,x-1);
 buttons.undo.onclick();assert.equal(env.graph.nodes[0].x,x-1);assert.equal(env.future.length,1);
 buttons.redo.onclick();assert.equal(env.graph.nodes[0].x,x);assert.equal(env.future.length,0);
});

test('hierarchy references resolve only an exact canonical ID and cannot substitute a label, ordinal or foreign reference',()=>{
 const canonical={id:'exact:id',kind:'linear',expression:'self.first(x)'},graph:any={nodes:[],generic:{ir:{nodes:[canonical,{id:'other:id',kind:'linear',label:'Same label'}]}},semanticHierarchy:{nodes:[
  {id:'missing:id',label:'Same label',x:0,y:0,semanticRef:true},
  {id:'exact:id',x:0,y:0,semanticRef:'other:id'},
  {id:'exact:id',x:0,y:0,semanticRef:true},
  {id:'summary:id',x:0,y:0,semantic:{id:'summary:id',presentation_only:true,canonical_members:['exact:id','other:id']}},
 ]}},before=JSON.stringify(graph),detail=previewDetailGraph(graph);
 assert.equal(detail.nodes[0].semantic,undefined);assert.equal(detail.nodes[1].semantic,undefined);
 assert.equal(detail.nodes[2].semantic,canonical);assert.equal(detail.nodes[3].semantic.presentation_only,true);
 assert.equal(JSON.stringify(graph),before);
});

test('thirty actual Studio visual transactions share canonical facts while independently restoring every overlay',async()=>{
 vm.runInContext('globalThis.window=globalThis;',ctx);script('yworks_edge_router_lab/studio-presentation.js');
 const app=readFileSync(new URL('yworks_edge_router_lab/app.js',base),'utf8');
 const a=app.indexOf('  async function studioVisual('),b=app.indexOf('  function studioSvg(',a);
 const initial=N.decorate(G.prepare({task:'generic-build',ir:fixture.bundle.ir.semantic_ir,options:{budgetMs:2000,refineCrossings:false,refinePlacement:false,refineChannels:false,refineFlow:false}}).graph);
 const env=vm.createContext({graph:initial,N,E,G,performance,window:{ArchCanvasStudioPresentation:ctx.ArchCanvasStudioPresentation},busy:false,drag:null,camera:{x:1,y:2,w:800,h:600},history:[],future:[],dirty:false,
  studioBridge:{state(){}},render(){},persist(){},syncUnifiedState(){}});
 vm.runInContext(app.slice(a,b)+';globalThis.visual=studioVisual;',env);
 const id=initial.nodes[0].id,geometry=JSON.stringify(initial.nodes),original=JSON.stringify(initial.generic.ir);
 for(let i=0;i<30;i++)await env.visual({operations:[{type:'alias',id,label:'Revision '+i}]});
 assert.equal(env.history.length,30);assert.equal(new Set([...env.history,env.graph].map((g:any)=>g.generic.ir)).size,1);
 assert.equal(new Set([...env.history,env.graph].map((g:any)=>g.nodes)).size,31);
 assert.equal(JSON.stringify(env.graph.nodes),geometry);assert.equal(JSON.stringify(env.graph.generic.ir),original);
 assert.equal(env.graph.studioPresentation.nodes[id].alias,'Revision 29');
 assert.equal(env.history[1].studioPresentation.nodes[id].alias,'Revision 0');
 assert.equal(env.history[29].studioPresentation.nodes[id].alias,'Revision 28');
 env.graph.studioPresentation.nodes[id].alias='changed';assert.equal(env.history[29].studioPresentation.nodes[id].alias,'Revision 28');
});


test('restored native decoration preserves saved revision and exact graph bytes while new semantic transitions advance it',()=>{
 const graph=build(fixture.bundle.ir.semantic_ir);graph.semanticRevision=17;
 const stored=JSON.parse(JSON.stringify(graph)),before=JSON.stringify(stored);
 N.decorate(stored,null);assert.equal(stored.semanticRevision,17);assert.equal(JSON.stringify(stored),before);
 const next=build(fixture.bundle.ir.semantic_ir);N.decorate(next,stored);assert.equal(next.semanticRevision,18);
});
