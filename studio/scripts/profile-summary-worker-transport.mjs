// Diagnostic packet costs only. Does not authorize opening over-budget models.
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const root=new URL('../../',import.meta.url),base=new URL('studio/public/preview/',root),ctx=vm.createContext({performance});
const script=p=>vm.runInContext(fs.readFileSync(new URL(p,base),'utf8'),ctx,{filename:p});
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])script('yworks_edge_router_lab/'+n+'.js');
for(const row of JSON.parse(fs.readFileSync(new URL('docs/summary-native-view-manifest-20261028.json',root))).files)script(row.path);
for(const n of ['studio-worker-transport','studio-adaptive','studio-semantic'])script('yworks_edge_router_lab/'+n+'.js');
const catalog=JSON.parse(fs.readFileSync(new URL('data/semantic/studio-catalog.json',base))),bytes=v=>Buffer.byteLength(JSON.stringify(v)),rows=[];
for(const model of catalog.models.filter(m=>m.nodes>480||m.edges>3600)){
 const ir=JSON.parse(fs.readFileSync(new URL('data/semantic/'+model.ir.path,base))),started=performance.now();
 const result=ctx.ArchCanvasSemanticView.prepare({task:'generic-build',ir,options:{budgetMs:300,refineCrossings:false,refinePlacement:false,refineChannels:false,refineFlow:false}}),graph=result.graph;
 const a=ctx.ArchCanvasNativeWorkerTransport.endpoint('profile-main'),b=ctx.ArchCanvasNativeWorkerTransport.endpoint('profile-worker');
 const full=a.pack({graph}),received=b.unpack(structuredClone(full)).graph,reply=b.pack({graph:received}),restored=a.unpack(structuredClone(reply)).graph;
 const repeat=a.pack({graph:restored});assert.ok(full.graph.core);assert.equal(reply.graph.core,undefined);assert.equal(repeat.graph.core,undefined);
 assert.equal(restored.generic.ir,graph.generic.ir);assert.deepEqual(JSON.parse(JSON.stringify(restored)),JSON.parse(JSON.stringify(graph)));
 const history=Array.from({length:30},()=>ctx.ArchCanvasSemanticView.snapshot(restored));assert.equal(new Set(history.map(g=>g.generic.ir)).size,1);assert.equal(new Set(history.map(g=>g.nodes)).size,30);
 const sizes={uncompressed:bytes({graph}),initialPacket:bytes(full),geometryPacket:bytes(repeat),geometryReply:bytes(reply)};
 rows.push({id:model.id,title:model.title,canonical:[ir.nodes.length,ir.edges.length],visible:[graph.nodes.length,graph.edges.length],...sizes,savedPerGeometryMessage:sizes.uncompressed-sizes.geometryPacket,reduction:1-sizes.geometryPacket/sizes.uncompressed,thirtySnapshotsSharedCore:true,exactRoundTrip:true,ms:performance.now()-started,routing:{failed:result.failed,pending:result.pending},scope:'F0 diagnostic with 300ms native routing budget; not routing-completion, persistent-storage, stress or cancellation acceptance'});
 globalThis.gc?.();
}
const output=process.argv[process.argv.indexOf('--output')+1];const report={ok:true,scope:'diagnostic-only-not-enabled',limitsUnchanged:{nodes:480,edges:3600,bytes:16000000},models:rows};
if(process.argv.includes('--output'))fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
