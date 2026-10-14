// Recheck the captured before/after frontier without regenerating the catalog.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..');
require(root+'/yworks_edge_router_lab/router.js');
const E=require(root+'/yworks_edge_router_lab/graph-engine.js'),C=globalThis.SummaryConstraints;
const before=JSON.parse(fs.readFileSync(__dirname+'/transformer-before.json'));
const after=JSON.parse(fs.readFileSync(__dirname+'/transformer-after.json'));
const identities=g=>({ir:g.irSha256,authority:g.recursive.authority,open:g.recursive.state.open,
  nodes:g.nodes.map(n=>[n.id,n.x,n.y,n.w,n.h,n.semantic]),
  bindings:g.edges.map(e=>[e.id,e.source,e.target,e.binding])});
assert.deepEqual(identities(before),identities(after));
const edge=(g,id)=>g.edges.find(e=>e.id===id),node=(g,id)=>g.nodes.find(n=>n.id===id);
const metrics=g=>({
  residualBelowAttention:edge(g,'binding-005-4').route[1].y-node(g,'enc.self').y-node(g,'enc.self').h,
  residualBesideAttention:node(g,'enc.self').x-edge(g,'binding-005-4').route[2].x,
  memoryAboveEncoder:node(g,'enc.layer_i').y-edge(g,'encoder-memory-to-cross-39').route[1].y
});
const checked=E.validateView(after);
assert.ok(checked.source.ok&&checked.layout.ok&&checked.edges.every(([,v])=>v.ok));
for(const id of ['binding-005-4','encoder-memory-to-cross-39'])assert.deepEqual(C.laneContacts(after,edge(after,id)),[]);
const report={case:after.caseId,frontier:'enc.self and enc.ffn expanded; other optional modules folded',
  nodes:after.nodes.length,edges:after.edges.length,sourceAndBindingsUnchanged:true,
  coordinateUnits:'canvas world units',before:metrics(before),after:metrics(after),
  validation:{source:checked.source.ok,layout:checked.layout.ok,edges:checked.edges.every(([,v])=>v.ok)},
  routing:checked.routing};
fs.writeFileSync(__dirname+'/comparison.json',JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
