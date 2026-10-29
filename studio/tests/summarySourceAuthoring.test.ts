import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { webcrypto } from 'node:crypto';
import vm from 'node:vm';
const context = vm.createContext({performance,TextEncoder,crypto:webcrypto});
function load(path: string) { vm.runInContext(readFileSync(new URL('../public/preview/'+path,import.meta.url),'utf8'),context,{filename:path}); }
for(const name of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])load('yworks_edge_router_lab/'+name+'.js');
for(const {path}of JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json',import.meta.url),'utf8')).files)load(path);
for(const name of ['studio-semantic','studio-documents','studio-authoring'])load('yworks_edge_router_lab/'+name+'.js');
const W=context.ArchCanvasSummaryAuthoring,N=context.ArchCanvasSemanticView,A=context.SemanticAuthoring,D=context.ArchCanvasSummaryDocuments;
const copy=(value:any)=>JSON.parse(JSON.stringify(value));
const options={refineCrossings:false,refinePlacement:false,refineChannels:false,refineFlow:false,budgetMs:1000};
const source='from torch import nn\nclass Block(nn.Module):\n def __init__(self,width=4):\n  super().__init__()\n  self.linear=nn.Linear(width,width)\n def forward(self,x,skip):\n  return self.linear(x)+skip\n';
const project=fileURLToPath(new URL('../../',import.meta.url));
const {stdout}=await promisify(execFile)('python3',['-I','-S','-B','-c','import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_preview.authoring_bridge import compile_source_module;print(json.dumps([compile_source_module(sys.argv[2],"Block",{"width":7}),compile_source_module(sys.argv[2],"Block",{"width":16}),compile_source_module(sys.argv[2].replace("def forward(self,x,skip):","def forward(self,x):").replace("self.linear(x)+skip","self.linear(x)"),"Block",{"width":16})]))',project,source],{encoding:'utf8'});
const [original,changed,incompatible]=JSON.parse(stdout);
function build(result:any){const {record,parsed}=result,built=N.prepare({task:'generic-build',ir:parsed.ir,state:parsed.state,extra:{authoring:parsed.authoring},options});assert.equal(N.accepts(built.graph,built.validation),true);return W.attach(built.graph,record);}
async function blank(){return build(await W.begin(null,{blank:true}));}
async function edit(graph:any,op:any){return build(await W.apply(graph,op,[]));}

test('source modules reparse constructor facts and replace while preserving exact external slot connections',async()=>{
 let graph=await blank();graph=await edit(graph,{action:'interface',role:'input',label:'external'});const external=graph.generic.authoring.nodes[0].id;
 graph=await edit(graph,{action:'add-source',module:original});const root=graph.generic.authoring.nodes.find((n:any)=>n.kind==='composite').id;
 const port=A.ports(graph.generic.authoring,root).inputs.find((p:any)=>p.label==='skip');assert.ok(port);
 graph=await edit(graph,{action:'connect',source:{node:external,port:'out'},target:{node:port.node,port:port.port}});
 const edge=copy(graph.generic.authoring.edges.find((e:any)=>e.source===external));
 const stable=JSON.stringify(graph);
 await assert.rejects(W.apply(graph,{action:'replace-module',id:root,module:incompatible}),/已连接输入/);assert.equal(JSON.stringify(graph),stable);
 graph=await edit(graph,{action:'replace-module',id:root,module:changed});const replacement=graph.generic.authoring.nodes.find((n:any)=>n.kind==='composite').id;
 assert.notEqual(replacement,root);const next=A.ports(graph.generic.authoring,replacement).inputs.find((p:any)=>p.label==='skip');
 const nextEdge=graph.generic.authoring.edges.find((e:any)=>e.id===edge.id);assert.equal(nextEdge.source,external);assert.equal(nextEdge.target,next.node);assert.equal(nextEdge.target_port,next.port);
 assert.equal(graph.generic.authoring.modules[replacement].constructor.width,16);assert.equal(graph.generic.authoring.modules[replacement].source,source);
 assert.ok(graph.generic.authoring.nodes.some((n:any)=>JSON.stringify(n.constructor?.args)==='[16,16]'));
 assert.equal(graph.generic.ir.runtime.model_executed,false);
 const restored=await D.restore(copy(W.record(graph)));assert.equal(D.matches(graph,restored.parsed),true);
 assert.equal(structuredClone(W.inspector(graph)).nodes.find((n:any)=>n.id===replacement).module.constructor.width,16);
});

test('late source responses cannot modify a different workspace or a changed revision of the same draft',async()=>{
 let graph=await blank();const old=copy(graph.authoringWorkspace);graph=await edit(graph,{action:'interface',role:'input',label:'new'});
 const before=JSON.stringify(graph);
 await assert.rejects(W.apply(graph,{action:'add-source',module:original,workspaceId:old.id,baseDocumentSha256:old.documentSha256}),/已变化/);
 await assert.rejects(W.apply(graph,{action:'add-source',module:original,workspaceId:'different'}),/已变化/);
 assert.equal(JSON.stringify(graph),before);
});

for(const atomic of [false,true])test(`reference recipe exactly reconstructs original identities, operand slots and IR (${atomic?'atomic':'modules'})`,async()=>{
 const sourceGraph=N.prepare({task:'generic-build',ir:original.ir,options}).graph;sourceGraph.caseId='original';
 let graph=build(await W.begin(sourceGraph));graph=await edit(graph,{action:'recipe-start',atomic});
 assert.equal(graph.generic.authoring.nodes.length,0);const count=W.inspector(graph).recipe.parts.length;assert.ok(count>1);
 // Reverse insertion order forces original parent restoration rather than
 // relying on a convenient topological sequence.
 for(let part=count-1;part>=0;part--)graph=await edit(graph,{action:'recipe-add',part});
 assert.ok(W.inspector(graph).recipe.readyConnections>0);graph=await edit(graph,{action:'recipe-wires'});
 assert.equal(W.inspector(graph).recipe.exact,true);assert.deepEqual(copy(graph.generic.ir),original.ir);
 assert.equal(D.matches(graph,(await D.restore(copy(W.record(graph)))).parsed),true);
});

test('named blank models accept arbitrary custom source, retain source names and restore renamed drafts',async()=>{
 const custom='from torch import nn\nraise RuntimeError("AST_ONLY_SENTINEL")\nclass CustomPair(nn.Module):\n def __init__(self,width=5):\n  super().__init__()\n  self.shared=nn.Linear(width,width)\n def forward(self,x,skip):\n  first=self.shared(x)\n  second=self.shared(skip)\n  return first,second\n';
 const {stdout}=await promisify(execFile)('python3',['-I','-S','-B','-c','import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_preview.authoring_bridge import compile_source_module;print(json.dumps(compile_source_module(sys.argv[2],"CustomPair",{"width":13})))',project,custom],{encoding:'utf8'});
 const module=JSON.parse(stdout);
 assert.equal(module.source,custom);assert.equal(module.entry,'CustomPair');
 assert.equal(module.constructor.width,13);assert.equal(module.ir.runtime.model_executed,false,'top-level raise must never execute');
 let graph=build(await W.begin(null,{blank:true,title:'  MyVisionEncoder  '}));
 assert.equal(graph.generic.authoring.title,'MyVisionEncoder');
 graph=await edit(graph,{action:'add-source',module});
 const root=graph.generic.authoring.nodes.find((n:any)=>!n.parent);assert.equal(root.label,'CustomPair');
 assert.equal(graph.generic.authoring.modules[root.id].source,custom);
 assert.equal(A.ports(graph.generic.authoring,root.id).inputs.length,2);
 assert.equal(A.ports(graph.generic.authoring,root.id).outputs.length,1,'a Python tuple is one structured return value');
 const tuple=graph.generic.authoring.nodes.find((n:any)=>n.operator==='structure'&&n.structure_kind==='tuple');assert.ok(tuple);
 assert.deepEqual(copy(graph.generic.authoring.edges.filter((e:any)=>e.target===tuple.id).map((e:any)=>e.target_port).sort()),['0','1']);
 const nodes=copy(graph.generic.authoring.nodes),edges=copy(graph.generic.authoring.edges);
 graph=await edit(graph,{action:'title',title:'我的 VisionEncoder'});
 assert.deepEqual(copy(graph.generic.authoring.nodes),nodes);assert.deepEqual(copy(graph.generic.authoring.edges),edges);
 assert.equal(graph.generic.ir.nodes.find((n:any)=>!n.parent).label,'我的 VisionEncoder');
 assert.equal(graph.generic.authoring.nodes.find((n:any)=>n.id===root.id).label,'CustomPair');
 const restored=await D.restore(copy(W.record(graph)));
 assert.equal(restored.record.document.title,'我的 VisionEncoder');assert.equal(D.matches(graph,restored.parsed),true);
 for(const title of ['', 'x'.repeat(241),'Bad\nName'])await assert.rejects(W.apply(graph,{action:'title',title}),/名称/);
 assert.equal(graph.generic.authoring.title,'我的 VisionEncoder','failed operations retain the draft');
});

test('complete-model import prepares a fresh source-bound document and recipe rebuilding retains the executable binding', async()=>{
 const before=await blank(),saved=JSON.stringify(before);
 const prepared=await W.fromSource(original,'ImportedModel');
 assert.equal(JSON.stringify(before),saved,'preparation never changes the previous workspace');
 let graph=build(prepared);
 assert.equal(graph.generic.authoring.title,'ImportedModel');
 assert.equal(graph.generic.authoring.codeReference.source,source);
 assert.deepEqual(copy(graph.generic.ir.nodes),original.ir.nodes);
 graph=await edit(graph,{action:'recipe-start',atomic:true});
 assert.equal(graph.generic.authoring.nodes.length,0);
 assert.equal(graph.generic.authoring.codeReference.entry,'Block');
 const count=W.inspector(graph).recipe.parts.length;
 for(let part=count-1;part>=0;part--)graph=await edit(graph,{action:'recipe-add',part});
 graph=await edit(graph,{action:'recipe-wires'});
 const restored=await D.restore(copy(W.record(graph)));
 assert.equal(W.inspector(graph).recipe.exact,true);
 assert.equal(restored.parsed.authoring.codeReference.source,source);
 await assert.rejects(W.fromSource({...original,ir:{...original.ir,nodes:[]}},'Invalid'));
 assert.equal(JSON.stringify(before),saved);
});
