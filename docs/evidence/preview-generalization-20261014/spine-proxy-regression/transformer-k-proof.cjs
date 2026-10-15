const fs=require('fs'),vm=require('vm'),path=require('path'),crypto=require('crypto'),assert=require('assert');
const project=path.resolve(__dirname,'../../../..');
const preview=path.join(project,'studio/public/preview');
const receipt=JSON.parse(fs.readFileSync(path.join(__dirname,'runtime-receipt.json')));const runtime=process.argv[2]||null;
const context=vm.createContext({}),hashes={};
for(const name of ['router.js','physical-ports.js','junction-markers.js','route-labels.js','source-contracts.js','semantic-constraints.js','graph-engine.js','recursive-graph.js']){
 const filename=runtime?path.join(runtime,name):name==='recursive-graph.js'?path.join(__dirname,receipt.variantOverlay):path.join(project,receipt.baseRuntimeFiles[name]);const bytes=fs.readFileSync(filename);hashes[name]=crypto.createHash('sha256').update(bytes).digest('hex');assert.strictEqual(hashes[name],receipt.variantRuntimeHashes[name]);vm.runInContext(bytes.toString(),context,{filename:name});
}
const C=context.SummaryConstraints,E=context.SummaryEngine,F=context.SummaryRecursive;
const item=JSON.parse(fs.readFileSync(path.join(preview,'data/catalog.json'))).cases.find(c=>c.id==='01093cc06a87b35a');
const inputs={},results=[];
for(const id of ['enc.self','dec.self']){
 const sources=Object.fromEntries(item.views.filter(v=>v.json).map(v=>{const bytes=fs.readFileSync(path.join(preview,v.json));inputs[v.json]=crypto.createHash('sha256').update(bytes).digest('hex');return[v.key,C.initialize(JSON.parse(bytes))];}));
 const graph=F.toggle(F.build(F.create(sources)),id,true),authority=JSON.stringify(graph.recursive.authority);
 const baseline=JSON.stringify(graph.edges.map(e=>[e.id,e.source,e.target,e.binding,e.fixedSource,e.fixedTarget,e.contract]));
 const routed=F.route(graph),checked=E.validateView(graph),edge=graph.edges.find(e=>e.target===id+'.k');
 const source=E.endpoint(graph,edge,'source'),target=E.endpoint(graph,edge,'target'),gates=C.activeGates(graph,edge).map(g=>({...g,point:C.gatePoint(graph.nodes.find(n=>n.id===g.frame),g)}));
 assert.strictEqual(routed.failed,0);assert(checked.source.ok&&checked.layout.ok&&checked.edges.every(([,c])=>c.ok));
 assert.strictEqual(edge.route.length,2);assert(Math.abs(source.x-target.x)<1e-5);assert(gates.length>=2);assert(gates.every(g=>Math.abs(g.point.x-source.x)<1e-5));
 assert.strictEqual(JSON.stringify(graph.recursive.authority),authority);assert.strictEqual(JSON.stringify(graph.edges.map(e=>[e.id,e.source,e.target,e.binding,e.fixedSource,e.fixedTarget,e.contract])),baseline);
 results.push({id,edge:edge.id,source:edge.source,target:edge.target,sourcePoint:source,targetPoint:target,route:edge.route,gates,failed:routed.failed,validation:checked,authorityUnchanged:true,sourceFieldsUnchanged:true});
}
const result={hashes,inputs,results};fs.writeFileSync(process.argv[3]||'/tmp/archcanvas-spine-proxy-transformer-k-reproduced.json',JSON.stringify(result,null,2));console.log(JSON.stringify({hashes,results:results.map(r=>({id:r.id,route:r.route,gates:r.gates,failed:r.failed,authorityUnchanged:true,sourceFieldsUnchanged:true}))},null,2));
