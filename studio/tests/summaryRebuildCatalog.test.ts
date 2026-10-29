import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { webcrypto } from 'node:crypto';
import vm from 'node:vm';
const root = new URL('../public/preview/', import.meta.url);
const context = vm.createContext({ performance, TextEncoder, crypto: webcrypto });
function load(path: string) { vm.runInContext(readFileSync(new URL(path, root), 'utf8'), context, {filename:path}); }
for (const name of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph']) load('yworks_edge_router_lab/'+name+'.js');
for (const {path} of JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json', import.meta.url),'utf8')).files) load(path);
for (const name of ['studio-semantic','studio-documents','studio-authoring']) load('yworks_edge_router_lab/'+name+'.js');
const A=context.SemanticAuthoring, W=context.ArchCanvasSummaryAuthoring, D=context.ArchCanvasSummaryDocuments, N=context.ArchCanvasSemanticView;
const copy=(v:any)=>JSON.parse(JSON.stringify(v));
const catalog=JSON.parse(readFileSync(new URL('data/semantic/studio-catalog.json',root),'utf8'));
const reports:any[]=[];
const options={budgetMs:0,refineCrossings:false,refinePlacement:false,refineChannels:false,refineFlow:false};
for (const item of catalog.models) test(`${item.title} (${item.id}): zero-node module and atomic reconstruction`,async()=>{
 const ir=JSON.parse(readFileSync(new URL('data/semantic/'+item.ir.path,root),'utf8'));
 const report:any={id:item.id,title:item.title,nodes:ir.nodes.length,edges:ir.edges.length};
 for(const atomic of [false,true]) {
  const plan=A.recipe(ir,{atomic}),doc=A.empty(ir.title);
  doc.recipe={parents:plan.parents,baseline:copy(ir)};
  assert.equal(doc.nodes.length,0); assert.equal(doc.edges.length,0);
  // Children deliberately precede containers: identity restoration cannot rely on insertion order.
  for(const part of [...plan.parts].reverse()) A.add(doc,part,{keepIdentity:true});
  for(const edge of plan.connections) A.restoreConnection(doc,edge);
  assert.equal(A.validate(doc),true);
  assert.deepEqual(copy(A.sourceIR(doc)),ir,'source facts, identities, hierarchy and operand slots survive');
  report[atomic?'atomic':'modules']={parts:plan.parts.length,exact:true};
  if(!atomic) {
   const workspace=await D.workspace(doc),restored=await D.restore(copy(workspace.record));
   assert.deepEqual(copy(restored.parsed.ir),ir,'portable authored document restores exactly');
   const built=N.prepare({task:'generic-build',ir:restored.parsed.ir,state:restored.parsed.state,extra:{authoring:restored.parsed.authoring},options});
   assert.equal(N.accepts(built.graph,built.validation),true,JSON.stringify(built.validation).slice(0,1500));
   assert.equal(W.inspector(W.attach(built.graph,restored.record)).recipe.exact,true);
   report.nativeAccepted=true;
   report.pendingRoutes=built.graph.edges.filter((e:any)=>e.failed||e.pendingRouting).length;
  }
 }
 reports.push(report);
});
test('catalog reconstruction coverage is complete',()=>{
 assert.equal(catalog.models.length,43);
 assert.equal(reports.length,catalog.models.length);
 if(process.env.ARCHCANVAS_REBUILD_REPORT)writeFileSync(process.env.ARCHCANVAS_REBUILD_REPORT,JSON.stringify({schema:'archcanvas-rebuild-audit/1',scope:'Exact structural reconstruction, portable save/restore and native view acceptance; not Python generation or execution equivalence.',models:reports},null,2)+'\n');
});
