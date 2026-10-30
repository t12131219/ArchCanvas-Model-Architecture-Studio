import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { webcrypto } from 'node:crypto';
import vm from 'node:vm';

const project=fileURLToPath(new URL('../../',import.meta.url));
const fixtureRun=await promisify(execFile)('python3',['-I','-S','-B','-c',`
import json,sys,tempfile
sys.path.insert(0,sys.argv[1]+'/src')
from archcanvas_preview import analyze
from archcanvas_adapters import AdapterRegistry,scaffold_adapter_files
from archcanvas_adapters.handoff import starter_rules
files={'unseen.py':'from torch import nn\\nraise RuntimeError("STATIC_ONLY")\\nclass Unknown(nn.Module):\\n def forward(self, values):\\n  return [item.secret() for item in values if item is not None]\\n'}
bundle=analyze(files,'unseen:Unknown',semantic_mode='summary')
with tempfile.TemporaryDirectory() as directory:
 registry=AdapterRegistry(directory)
 for rule in starter_rules().values():
  registry.register_files(scaffold_adapter_files(files,'unseen:Unknown',rules=[rule]),files)
 print(json.dumps(registry.preview(bundle,files)))
`,project],{encoding:'utf8',maxBuffer:2_000_000});
const fixture=JSON.parse(fixtureRun.stdout);
const context=vm.createContext({performance,TextEncoder,TextDecoder,crypto:webcrypto});
const load=(path:string)=>vm.runInContext(readFileSync(new URL('../public/preview/'+path,import.meta.url),'utf8'),context,{filename:path});
for(const name of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph','source-adapter'])load('yworks_edge_router_lab/'+name+'.js');
for(const {path}of JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json',import.meta.url),'utf8')).files)load(path);
for(const name of ['studio-semantic','studio-documents','studio-authoring'])load('yworks_edge_router_lab/'+name+'.js');
vm.runInContext('globalThis.window=globalThis',context);load('yworks_edge_router_lab/studio-presentation.js');
const N=context.ArchCanvasSemanticView,A=context.SemanticAuthoring,W=context.ArchCanvasSummaryAuthoring,D=context.ArchCanvasSummaryDocuments;
const options={refineCrossings:false,refinePlacement:false,refineChannels:false,refineFlow:false,budgetMs:1000};
const copy=(v:any)=>JSON.parse(JSON.stringify(v));

test('verified unknown views survive browser digest validation and native expansion',async()=>{
 await context.SummarySourceAdapter.verify(fixture);
 const ir=fixture.ir.semantic_ir,card=ir.nodes.find((n:any)=>n.inspection_only);
 assert.ok(card,'a real new inspection element must enter native IR');
 let result=N.prepare({task:'generic-build',ir,binding:fixture,options});
 result=N.prepare({task:'frontier',graph:result.graph,transition:{type:'all',expanded:true},options});
 assert.equal(N.accepts(result.graph,result.validation),true);
 assert.ok(result.graph.nodes.some((n:any)=>n.id===card.id));
 assert.equal(result.graph.generic.ir.coverage.complete,false);
 const sourceEdges=result.graph.edges.filter((e:any)=>e.binding.kind==='source-inspection');
 assert.ok(sourceEdges.length,'arbitrary user expressions must retain inspection arrows after real expansion');
 for(const edge of sourceEdges){
  const appearance=context.ArchCanvasStudioPresentation.edgeAppearance(result.graph,edge);
  assert.equal(appearance.sourceRelation,true);assert.equal(appearance.stroke,'#776095');
 }
 const ordinary=result.graph.edges.find((e:any)=>e.binding.kind!=='source-inspection');
 if(ordinary)assert.equal(context.ArchCanvasStudioPresentation.isSourceDependency(result.graph,ordinary),false);
});

test('source inspection retains edit/save compatibility without acquiring tensor ports',async()=>{
 const ir=fixture.ir.semantic_ir,graph=N.prepare({task:'generic-build',ir,options}).graph;
 const {record,parsed}=await W.begin(graph);
 A.validate(parsed.authoring);
 const card=parsed.authoring.nodes.find((n:any)=>n.inspection_only),other=parsed.authoring.nodes.find((n:any)=>!n.inspection_only&&n.kind==='interface');
 assert.ok(card);assert.ok(other);
 assert.deepEqual(copy(A.ports(parsed.authoring,card.id)),{inputs:[],outputs:[]});
 assert.throws(()=>A.connect(copy(parsed.authoring),{node:card.id,port:'out'},{node:other.id,port:'in'}),/源码检查卡片/);
 const restored=await D.restore(copy(record));
 assert.ok(restored.parsed.ir.nodes.some((n:any)=>n.id===card.id));
 assert.deepEqual(copy(restored.parsed.ir),copy(parsed.ir));
});

test('actual source registration uses native worker without synchronous legacy depth routing',async()=>{
 const source=readFileSync(new URL('../public/preview/yworks_edge_router_lab/app.js',import.meta.url),'utf8');
 const callback=source.slice(source.indexOf('  async function registerSource('),source.indexOf('  async function installSource('));
 const importedPackages=new Map(),importedSources=new Map(),catalog={cases:[]};
 let workerBuilds=0;
 const environment={A:{verify:(b:any)=>context.SummarySourceAdapter.verify(b),sources:()=>{throw Error('Legacy routing must not run for a native source import');}},
   N,E:context.SummaryEngine,F:context.SummaryRecursive,G:context.SummaryNativeSemantic,
   runGraphTask:async(message:any)=>{workerBuilds++;return N.prepare({...message,options});},
   importedPackages,importedSources,catalog};
 const register=new Function(...Object.keys(environment),callback+';return registerSource;')(...Object.values(environment));
 const item=await register(fixture);
 assert.equal(workerBuilds,1);
 assert.equal(importedPackages.get(item.id),fixture);
 const graph=importedSources.get(item.id).overview;
 assert.ok(graph.generic.ir.nodes.some((n:any)=>n.inspection_only));
 assert.deepEqual(copy(graph.generic.ir),copy(fixture.ir.semantic_ir));
});

test('configured CPU-failure source bundle survives default fanout optimisation and native registration',async()=>{
 const {stdout}=await promisify(execFile)('python3',['-I','-S','-B','-c',`
import json,sys,tempfile
from pathlib import Path
sys.path.insert(0,sys.argv[1]+'/src')
from archcanvas_preview import analyze
from archcanvas_adapters import AdapterRegistry,scaffold_adapter_files
from archcanvas_adapters.handoff import starter_rules
files={'model.py':Path(sys.argv[1]+'/fixtures/agent_views/model.py').read_text()}
config={'input_dim':8,'output_dim':4,'degree':3}
bundle=analyze(files,'model:ChebyKANLinear',config,semantic_mode='summary')
with tempfile.TemporaryDirectory() as directory:
 registry=AdapterRegistry(directory)
 registry.register_files(scaffold_adapter_files(files,'model:ChebyKANLinear',config=config,rules=[starter_rules()['attribute-call']]),files)
 print(json.dumps(registry.preview(bundle,files)))
`,project],{encoding:'utf8',maxBuffer:2_000_000});
 const configured=JSON.parse(stdout);
 await context.SummarySourceAdapter.verify(configured);
 const result=N.prepare({task:'generic-build',ir:configured.ir.semantic_ir,binding:configured,options:{}});
 assert.equal(result.validation.source.ok,true,result.validation.source.violations.join('; '));
 assert.equal(N.accepts(result.graph,result.validation),true);
 assert.deepEqual(copy(result.graph.generic.ir),copy(configured.ir.semantic_ir));
 const errors=result.graph.edges.flatMap((e:any)=>context.SummaryPhysicalPorts.errors(result.graph,e).map((v:string)=>e.id+': '+v));
 assert.deepEqual(copy(errors),[],'the complete proposed fanout must preserve distinct physical operand slots');
 assert.equal(result.graph.generic.ir.nodes.filter((n:any)=>n.inspection_only).length,6);
 const original=copy(configured.ir.semantic_ir);
 let expanded=N.prepare({task:'frontier',graph:result.graph,transition:{type:'all',expanded:true},options:{}});
 const continuous=(graph:any)=>{
  const call=graph.nodes.find((n:any)=>n.semantic.function_target==='torch.acos'&&!n.semantic.inspection_only);
  assert.ok(call,'the original opaque call remains the computational endpoint');
  assert.equal(call.expanded,false);assert.equal(call.label,'torch.acos');
  assert.equal(graph.nodes.some((n:any)=>n.semantic.inspection_only),false,'callable spelling does not belong on the tensor canvas');
  assert.equal(graph.edges.some((e:any)=>e.binding.kind==='source-inspection'),false);
  assert.deepEqual(copy(context.SummaryNativeSemantic.children(graph,call.id)),[],'fully expanded calls have no redundant syntax toggle');
  const details=context.SummaryNativeSemantic.nodeEvidence(graph,call.id);
  assert.match(details,/Source syntax details/);assert.match(details,/torch.acos/);assert.match(details,/Source expression:\ntorch(?:\n|$)/);
  assert.ok(!N.hierarchy(graph).some((n:any)=>n.id.includes('/rule-')),'detail-only syntax cannot reappear through the layer tree');
  const receipts=graph.generic.receipts;
  for(const card of original.nodes.filter((n:any)=>n.inspection_only))assert.ok(receipts.node_accounting.attached.includes(card.id));
  for(const edge of original.edges.filter((e:any)=>e.kind==='source-inspection'))assert.ok(receipts.edge_accounting.attached.includes(edge.id));
  const input=graph.edges.find((e:any)=>e.target===call.id&&e.binding.kind==='data');
  const output=graph.edges.find((e:any)=>e.source===call.id&&e.binding.kind!=='source-inspection');
  assert.ok(input&&output,'tensor data must enter and leave the same visible computational leaf');
  const upstream=(id:string):any=>{const n=graph.nodes.find((n:any)=>n.id===id);return n.semantic.kind==='value-alias'?upstream(graph.edges.find((e:any)=>e.target===id&&e.binding.kind!=='source-inspection').source):n;};
  const downstream=(id:string):any=>{const n=graph.nodes.find((n:any)=>n.id===id);return n.semantic.kind==='value-alias'?downstream(graph.edges.find((e:any)=>e.source===id&&e.binding.kind!=='source-inspection').target):n;};
  assert.equal(upstream(input.source).label,'tanh');assert.equal(downstream(output.target).label,'mult');
  assert.equal(input.relationStyle,'data');assert.equal(output.relationStyle,'data');
  assert.ok(context.EdgeRouterLabRouting.dist(input.route.at(-1),context.SummaryPhysicalPorts.point(call,context.SummaryPhysicalPorts.active(input,'target')))<1e-5);
  assert.ok(context.EdgeRouterLabRouting.dist(output.route[0],context.SummaryPhysicalPorts.point(call,context.SummaryPhysicalPorts.active(output,'source')))<1e-5);
  assert.deepEqual(copy(graph.generic.ir),original,'attaching source evidence cannot rewrite canonical tensor dependencies');
 };
 continuous(expanded.graph);
 const check=expanded.validation;assert.equal(N.accepts(expanded.graph,check),true);
 const edit=await W.begin(expanded.graph);
 assert.deepEqual(copy(edit.parsed.ir),original);
 assert.ok(!edit.parsed.authoring.nodes.some((n:any)=>n.inspection_group_for),'a presentation frame must never become an authoring module');
 assert.equal(N.accepts(edit.initialGraph,context.SummaryEngine.validateView(edit.initialGraph)),true);
 const document=context.SummaryNativeSemantic.document(expanded.graph),parsed=context.SummaryNativeSemantic.read(document);
 const reopened=N.prepare({task:'generic-build',...parsed,extra:{layouts:parsed.layouts},nativeLayout:parsed.nativeLayout,options:{}});
 continuous(reopened.graph);
 const collapsed=N.prepare({task:'frontier',graph:expanded.graph,transition:{type:'all',expanded:false},options:{}});
 const reexpanded=N.prepare({task:'frontier',graph:collapsed.graph,transition:{type:'all',expanded:true},options:{}});
 continuous(reexpanded.graph);
 const moved=context.SummaryNativeSemantic.cloneGeometry(reexpanded.graph),moving=moved.nodes.find((n:any)=>n.semantic.function_target==='torch.acos');
 context.SummaryEngine.move(moved,moving.id,0,8);
 continuous(moved);
 const old=context.SummaryNativeSemantic.read({...document,renderer:'native-semantic/21'});
 assert.equal(old.nativeLayout,null,'old disconnected inspection layouts are migrated instead of replayed');
 const compatible=context.SummaryNativeSemantic.read({...document,renderer:'native-semantic/22'});
 assert.deepEqual(copy(compatible.nativeLayout),copy(document.nativeLayout),'compatible saved source layouts must not be discarded by the new context menu version');
});


test('callable syntax attachment is name independent and never hides computational dependencies',()=>{
 const ir:any={schema:'archcanvas-source-semantic/2',nodes:[
  {id:'root',kind:'composite',label:'Arbitrary model'},
  {id:'call',parent:'root',kind:'opaque',label:'result',function_target:'foreign_namespace.hidden_function'},
  {id:'callable',parent:'call',kind:'opaque',inspection_only:true,sourceKind:'SourceExpression',label:'foreign_namespace.hidden_function',sourceParameters:{sourceRulePath:['func']}},
  {id:'receiver',parent:'callable',kind:'opaque',inspection_only:true,sourceKind:'SourceExpression',label:'foreign_namespace',sourceParameters:{sourceRulePath:['func','value']}}
 ],edges:[{id:'syntax',source:'receiver',target:'callable',kind:'source-inspection',syntaxOnly:true}]};
 const before=JSON.stringify(ir),state={view:'source',mode:'source',open:['root','call','callable']};
 const cut=context.SummaryNativeSemantic.project(ir,state);
 assert.deepEqual(copy(cut.nodes.map((n:any)=>n.id)),['root','call']);
 assert.deepEqual(copy(cut.edge_accounting.attached),['syntax']);
 assert.deepEqual(copy(cut.node_accounting.attached),['callable','receiver']);
 assert.equal(JSON.stringify(ir),before);
 const tensor=copy(ir);tensor.edges.push({id:'real-data',source:'receiver',target:'call',kind:'data'});
 const retained=context.SummaryNativeSemantic.project(tensor,state);
 assert.ok(retained.nodes.some((n:any)=>n.id==='receiver'),'any real dependency vetoes syntax attachment');
 assert.ok(retained.edges.some((e:any)=>e.id==='real-data'),'source data cannot become a detail annotation');
});

test('resource docking is a general geometry policy and retains mutable/effectful reads',()=>{
 const nodes:any[]=[{id:'model',kind:'composite',label:'Unknown model'},...Array.from({length:9},(_,i)=>({id:'op'+i,parent:'model',kind:'compute',label:'op'+i})),{id:'read',parent:'model',kind:'state',label:'unseen_size'},{id:'mutable',parent:'model',kind:'state',label:'writeable',mutable:true}];
 const edges:any[]=[...Array.from({length:8},(_,i)=>({id:'link'+i,source:'op'+i,target:'op'+(i+1),kind:'data'})),{id:'use',source:'read',target:'op7',kind:'data'},{id:'mutable-use',source:'mutable',target:'op7',kind:'data'}];
 const before=JSON.stringify({nodes,edges}),idx=context.SemanticEngine.index({nodes});
 const positions=context.SemanticLayout.layout(idx,['model'],new Set(nodes.map(n=>n.id)),edges,{}, {nodeSize:()=>({w:112,h:44}),inputPlacement:'consumer',resourcePlacement:'consumer'});
 assert.ok(positions.get('read').y>positions.get('op0').y,'a predecessor-free read is drawn near its first consumer');
 assert.ok(positions.get('read').y<positions.get('op7').y);
 assert.equal(positions.get('mutable').y,positions.get('op0').y,'mutable state retains conservative source arrangement');
 assert.equal(JSON.stringify({nodes,edges}),before,'layout may not mutate source facts');
});

test('selected semantic leaves lower to local source atoms and restore independently',async()=>{
 const catalog=JSON.parse(readFileSync(new URL('../public/preview/data/semantic/studio-catalog.json',import.meta.url),'utf8'));
 const model=catalog.models.find((m:any)=>/transformer/i.test(m.title||m.id))||catalog.models[0];
 const ir=JSON.parse(readFileSync(new URL('../public/preview/data/semantic/'+model.ir.path,import.meta.url),'utf8'));
 let result=N.prepare({task:'generic-build',ir,options});
 const G=context.SummaryNativeSemantic;
 const candidates=result.graph.nodes.filter((n:any)=>!n.modelHeading&&!G.children(result.graph,n.id).length&&G.atomicTargets(result.graph,[n.id]).length);
 assert.ok(candidates.length,'semantic leaves with attached configuration/resources must allow atomic inspection');
 const selected=candidates.slice(0,2).map((n:any)=>n.id),before=copy(result.graph),canonical=JSON.stringify(result.graph.generic.ir);
 result=N.prepare({task:'frontier',graph:result.graph,transition:{type:'atomic',ids:selected,expanded:true},options:{...options,budgetMs:16000}});
 assert.equal(result.validation.source.ok,true,result.validation.source.violations.join('; '));
 assert.equal(result.graph.generic.state.paperCanonical===true,false,'local source expansion must not expand the whole model');
 assert.equal(result.graph.generic.state.atomicCuts.length,selected.length);
 assert.equal(result.validation.layout.ok,true,result.validation.layout.violations.join('; '));
 assert.ok(result.validation.edges.every(([,v]:any)=>v.ok),'local atomic expansion must keep strictly valid routes');
 assert.ok(result.graph.edges.every((e:any)=>e.binding.kind!=='parameter-read'),'local atomic scopes must not restore weight arrows');
 const touched=new Set(result.graph.generic.state.atomicCuts.flatMap((c:any)=>c.members));
 for(const n of before.nodes.filter((n:any)=>!selected.includes(n.id)&&!touched.has(n.id)))assert.ok(result.graph.nodes.some((v:any)=>v.id===n.id),'unselected semantic siblings remain visible');
 assert.equal(JSON.stringify(result.graph.generic.ir),canonical);
 const first=result.graph.generic.state.atomicCuts[0];
 const firstVisible=result.graph.nodes.find((n:any)=>first.members.includes(n.id));
 const partial=N.prepare({task:'frontier',graph:result.graph,transition:{type:'atomic',ids:[firstVisible.id],expanded:false},options});
 assert.equal(partial.graph.generic.state.atomicCuts.length,selected.length-1);
 assert.ok(partial.graph.nodes.some((n:any)=>n.id===first.id),'one scope can restore without closing the other');
 assert.equal(JSON.stringify(partial.graph.generic.ir),canonical);
 const edit=await W.begin(result.graph);
 assert.equal(JSON.stringify(edit.parsed.ir),canonical,'local source inspection does not change edit authority');
 const members=result.graph.generic.state.atomicCuts.flatMap((c:any)=>c.members);
 assert.ok(members.some((id:string)=>result.graph.nodes.some((n:any)=>n.id===id)&&!before.nodes.some((n:any)=>n.id===id)));
 const record=G.document(result.graph),parsed=G.read(record);
 assert.equal(G.read({...record,renderer:'native-semantic/23'}).nativeLayout,null,'old partial atomic layouts are rebuilt to the complete source form');
 const reopened=N.prepare({task:'generic-build',...parsed,options});
 assert.deepEqual(copy(reopened.graph.nodes.map((n:any)=>n.id)),copy(result.graph.nodes.map((n:any)=>n.id)));
 const restored=N.prepare({task:'frontier',graph:result.graph,transition:{type:'atomic',ids:result.graph.nodes.filter((n:any)=>members.includes(n.id)).map((n:any)=>n.id),expanded:false},options});
 assert.equal(restored.validation.source.ok,true,restored.validation.source.violations.join('; '));
 assert.deepEqual(copy(restored.graph.nodes.map((n:any)=>n.id)),copy(before.nodes.map((n:any)=>n.id)));
});

test('local atomic module uses the same source units and containers as expand all',()=>{
 const catalog=JSON.parse(readFileSync(new URL('../public/preview/data/semantic/studio-catalog.json',import.meta.url),'utf8'));
 const model=catalog.models.find((m:any)=>/transformer/i.test(m.title||m.id));
 const ir=JSON.parse(readFileSync(new URL('../public/preview/data/semantic/'+model.ir.path,import.meta.url),'utf8'));
 const G=context.SummaryNativeSemantic,base=G.build(ir),raw=new Map(ir.nodes.map((n:any)=>[n.id,n]));
 const within=(id:string,owner:string)=>{while(id){if(id===owner)return true;id=(raw.get(id) as any)?.parent;}return false;};
 const target=base.nodes.find((n:any)=>n.semantic.kind==='composite'&&!n.modelHeading&&ir.nodes.filter((v:any)=>within(v.id,n.id)).length>10&&ir.nodes.filter((v:any)=>within(v.id,n.id)).length<60);
 assert.ok(target);
 const local=G.operate(base,{kind:'atomic',ids:[target.id],open:true}),all=G.operate(base,{kind:'all',open:true});
 const expected=all.nodes.filter((n:any)=>within(n.id,target.id)),actual=local.nodes.filter((n:any)=>within(n.id,target.id));
 assert.deepEqual(copy(actual.map((n:any)=>n.id).sort()),copy(expected.map((n:any)=>n.id).sort()));
 for(const n of expected){const a=actual.find((v:any)=>v.id===n.id);assert.equal(a.expanded,n.expanded,n.id);assert.equal(a.label,n.label,n.id);assert.deepEqual(copy(a.semantic.paper),copy(n.semantic.paper),n.id);}
 const ids=new Set(expected.map((n:any)=>n.id));
 const signature=(g:any)=>g.edges.filter((e:any)=>ids.has(e.source)&&ids.has(e.target)).map((e:any)=>[e.id,e.source,e.target,e.binding.kind]).sort((a:any,b:any)=>a[0].localeCompare(b[0]));
 assert.deepEqual(copy(signature(local)),copy(signature(all)),'internal source wires match expand all rather than publication bundles');
 assert.equal(JSON.stringify(local.generic.ir),JSON.stringify(base.generic.ir));
});
