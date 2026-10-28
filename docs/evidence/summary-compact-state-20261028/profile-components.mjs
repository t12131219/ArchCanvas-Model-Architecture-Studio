import fs from 'node:fs';import vm from 'node:vm';import {webcrypto} from 'node:crypto';
const root='/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio',base=root+'/studio/public/preview/',ctx=vm.createContext({performance,TextEncoder,crypto:webcrypto});
const script=p=>vm.runInContext(fs.readFileSync(base+p,'utf8'),ctx,{filename:p});
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])script('yworks_edge_router_lab/'+n+'.js');
for(const row of JSON.parse(fs.readFileSync(root+'/docs/summary-native-view-manifest-20261028.json')).files)script(row.path);script('yworks_edge_router_lab/studio-semantic.js');
const catalog=JSON.parse(fs.readFileSync(base+'data/semantic/studio-catalog.json'));const bytes=v=>v===undefined?0:Buffer.byteLength(JSON.stringify(v));
for(const m of catalog.models.filter(m=>m.nodes>480||m.edges>3600)){
 const ir=JSON.parse(fs.readFileSync(base+'data/semantic/'+m.ir.path)),start=performance.now();const result=ctx.ArchCanvasSemanticView.prepare({task:'generic-build',ir,options:{budgetMs:300,refineCrossings:false,refinePlacement:false,refineChannels:false,refineFlow:false}}),g=result.graph;
 const top=Object.entries(g).map(([k,v])=>({key:k,bytes:bytes(v)})).sort((a,b)=>b.bytes-a.bytes),generic=Object.entries(g.generic).map(([k,v])=>({key:k,bytes:bytes(v)})).sort((a,b)=>b.bytes-a.bytes);
 console.log(JSON.stringify({title:m.title,ms:performance.now()-start,canonical:[ir.nodes.length,ir.edges.length],visible:[g.nodes.length,g.edges.length],top:top.slice(0,8),generic,nativeDocumentBytes:bytes(ctx.SummaryNativeSemantic.document(g)),cloneGeometryMs:(()=>{const t=performance.now();ctx.SummaryNativeSemantic.cloneGeometry(g);return performance.now()-t;})()}));
}
