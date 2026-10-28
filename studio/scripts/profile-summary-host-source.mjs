// F0 packet diagnostic only: does not open or authorize large catalog models.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {serialize} from 'node:v8';
const root=new URL('../../',import.meta.url),base=new URL('studio/public/preview/',root),ctx=vm.createContext({performance});
const script=p=>vm.runInContext(fs.readFileSync(new URL(p,base),'utf8'),ctx,{filename:p});
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])script('yworks_edge_router_lab/'+n+'.js');
for(const row of JSON.parse(fs.readFileSync(new URL('docs/summary-native-view-manifest-20261028.json',root))).files)script(row.path);
for(const n of ['studio-shared-source','studio-worker-transport','studio-adaptive','studio-semantic'])script('yworks_edge_router_lab/'+n+'.js');
const rows=[],catalog=JSON.parse(fs.readFileSync(new URL('data/semantic/studio-catalog.json',base)));
const app=fs.readFileSync(new URL('yworks_edge_router_lab/app.js',base),'utf8');
const beforeApp=fs.readFileSync(new URL('docs/evidence/summary-host-source-20261028/before/studio/public/preview/yworks_edge_router_lab/app.js',root),'utf8');
const builder=text=>text.slice(text.indexOf('  function studioDocument('),text.indexOf('  function studioState('));
function sources(value){const unique=new Set();let occurrences=0;function walk(v){if(!v||typeof v!=='object')return;if(v.schema==='archcanvas-source-semantic/2'){occurrences++;unique.add(v);return;}for(const item of Object.values(v))walk(item);}walk(value);return {occurrences,uniqueSources:unique.size};}
for(const model of catalog.models.filter(m=>m.nodes>480||m.edges>3600)){
 const ir=JSON.parse(fs.readFileSync(new URL('data/semantic/'+model.ir.path,base))),result=ctx.ArchCanvasSemanticView.prepare({task:'generic-build',ir,options:{budgetMs:300,refineCrossings:false,refinePlacement:false,refineChannels:false,refineFlow:false}}),graph=result.graph;
 const environment=vm.createContext({graph,hostSource:ctx.ArchCanvasSharedSource.pool(),current:{id:model.id,title:model.title},view:{key:'overview'},frontierPreset:'overview',N:ctx.ArchCanvasSemanticView,E:ctx.SummaryEngine,window:{},camera:{x:0,y:0,w:1000,h:700},interactionMode:'compat',tool:'select',canvasGridVisible:true,dirty:false,busy:false,drag:null,history:[],future:[],selectedNodes:new Set(),selectedEdges:new Set(),importedPackages:new Map(),importedDocuments:new Map([[model.id,{record:{schema:'archcanvas-summary-import/1',document:ir}}]]),catalogSources:null,$:()=>({checked:false}),studioSelection:()=>({})});
 vm.runInContext(builder(beforeApp),environment);let started=performance.now();const before=environment.studioDocument(),beforeMs=performance.now()-started;
 vm.runInContext(builder(app),environment);started=performance.now();const after=environment.studioDocument(),afterMs=performance.now()-started;
 assert.deepEqual(JSON.parse(JSON.stringify(after)),JSON.parse(JSON.stringify(before)));assert.equal(after.graph.generic.ir,after.nativeDocument.document);
 const clone=structuredClone(after);assert.equal(clone.graph.generic.ir,clone.nativeDocument.document);assert.notEqual(clone.graph.nodes,after.graph.nodes);
 const beforeBytes=serialize(before).byteLength,afterBytes=serialize(after).byteLength;
 assert.ok(afterBytes<beforeBytes);rows.push({id:model.id,title:model.title,canonical:[ir.nodes.length,ir.edges.length],visible:[graph.nodes.length,graph.edges.length],before:sources(before),after:sources(after),sourceJSONBytes:Buffer.byteLength(JSON.stringify(ir)),beforeSerializedReferenceBytes:beforeBytes,afterSerializedReferenceBytes:afterBytes,reduction:1-afterBytes/beforeBytes,beforeMs,afterMs,completeJSONEqual:true,structuredClonePreservesSharing:true,routing:{failed:result.failed,pending:result.pending},scope:'Actual host builder before/after on complete IR, 300ms F0 route budget. V8 serialization measures reference representation, not browser IPC byte counts, RSS or routing-completion acceptance.'});
 globalThis.gc?.();
}
const report={ok:true,scope:'diagnostic-only-not-enabled; portable JSON content/size unchanged; each message still carries full source',limitsUnchanged:{nodes:480,edges:3600,bytes:16000000},models:rows};
const index=process.argv.indexOf('--output');if(index>=0)fs.writeFileSync(process.argv[index+1],JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
