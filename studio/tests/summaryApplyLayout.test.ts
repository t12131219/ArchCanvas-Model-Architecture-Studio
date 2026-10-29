import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';import vm from 'node:vm';import ts from 'typescript';
const base=new URL('../public/preview/',import.meta.url),c=vm.createContext({performance,TextEncoder});
const load=(p:string)=>vm.runInContext(readFileSync(new URL(p,base),'utf8'),c,{filename:p});
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph','source-controls'])load('yworks_edge_router_lab/'+n+'.js');
for(const r of JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json',import.meta.url),'utf8')).files)load(r.path);load('yworks_edge_router_lab/studio-semantic.js');
const E=c.SummaryEngine,N=c.ArchCanvasSemanticView,G=c.SummaryNativeSemantic,plain=(v:any)=>JSON.parse(JSON.stringify(v));
const catalog=JSON.parse(readFileSync(new URL('data/semantic/studio-catalog.json',base),'utf8'));
function build(id:string){const m=catalog.models.find((m:any)=>m.id===id),ir=JSON.parse(readFileSync(new URL('data/semantic/'+m.ir.path,base),'utf8')),state=m.presentation?JSON.parse(readFileSync(new URL('data/semantic/'+m.presentation.path,base),'utf8')).default_state:N.state('overview');return N.prepare({task:'generic-build',ir,state,options:{}}).graph;}
const opts={margin:6,stub:28,bendCost:40,crossingCost:450,overlapCost:2,edgeSpacing:12,preserve:false,sides:'any',grid:0,style:'orthogonal',optimizeReadability:true};
function strict(g:any){const v=E.validateView(g);assert.equal(v.source.ok,true,JSON.stringify(v.source));assert.equal(v.layout.ok,true,JSON.stringify(v.layout));assert.deepEqual(plain(v.edges.filter(([,v]:any)=>!v.ok)),[]);}
for(const id of ['d6df94c94e8a5888','0216717d966327f4'])test('Apply batches preserve canonical facts, positions, independent undo and strict geometry: '+id,()=>{
 const graph=build(id),before=N.snapshot(graph),source=JSON.stringify(graph.generic.ir),geometry=JSON.stringify(graph.nodes),bindings=JSON.stringify(graph.edges.map((e:any)=>e.binding));strict(graph);
 const ids=graph.edges.map((e:any)=>e.id),r=E.optimizeRoutes(graph,ids,{...opts,budgetMs:80});assert.equal(r.ok,true);strict(r.graph);
 assert.equal(JSON.stringify(graph.nodes),geometry);assert.equal(JSON.stringify(graph.generic.ir),source);assert.equal(JSON.stringify(graph.edges.map((e:any)=>e.binding)),bindings);
 assert.equal(JSON.stringify(before.nodes),geometry);assert.notEqual(graph.edges,before.edges);assert.equal(graph.generic.ir,before.generic.ir);strict(before);
 assert.equal(r.optimization.checked+r.optimization.pendingIds.length,ids.length);assert.ok(r.optimization.checked>0);
 const oldPending=new Set(r.optimization.pendingIds);if(oldPending.size){const next=E.optimizeRoutes(graph,ids,{...opts,budgetMs:80});assert.ok(next.optimization.checked<=oldPending.size,'continue must not redo already completed edges');assert.equal(next.optimization.checked+next.optimization.pendingIds.length,oldPending.size);strict(graph);}
});
test('zero search budget retains all routes and defers exactly the selected scope; settings or geometry changes invalidate continuation',()=>{
 const graph=build('d6df94c94e8a5888'),ids=graph.edges.slice(0,3).map((e:any)=>e.id),before=JSON.stringify(graph.edges);const r=E.optimizeRoutes(graph,ids,{...opts,budgetMs:0});assert.deepEqual(plain(r.optimization.pendingIds),plain(ids));assert.equal(r.optimization.checked,0);assert.equal(JSON.stringify(graph.edges),before);
 // A malicious scheduling receipt is not a validation certificate.
 const forged=G.cloneGeometry(graph);forged.edges[0].binding={...forged.edges[0].binding,target_port:'invented'};assert.throws(()=>E.optimizeRoutes(forged,ids,opts),/源码语义/);
 const all=graph.edges.map((e:any)=>e.id),next=E.optimizeRoutes(graph,all,{...opts,budgetMs:0});assert.equal(next.optimization.pendingIds.length,all.length,'scope change must not resume only three old IDs');
});
test('never and empty scopes do not reroute; manual knots and unselected edge geometry survive selected optimization',()=>{
 const g=build('d6df94c94e8a5888'),ids=g.edges.map((e:any)=>e.id),before=JSON.stringify(g.edges);assert.equal(E.optimizeRoutes(g,ids,{...opts,policy:'never'}).unchanged,true);assert.equal(E.optimizeRoutes(g,[],opts).unchanged,true);assert.equal(JSON.stringify(g.edges),before);
 const e=g.edges.find((e:any)=>e.route.length>2);assert.ok(e);e.waypoints=[{...e.route[1]}];const knot=JSON.stringify(e.waypoints),peers=JSON.stringify(g.edges.filter((v:any)=>v!==e));
 E.optimizeRoutes(g,[e.id],{...opts,preserve:true,budgetMs:200});strict(g);assert.equal(JSON.stringify(e.waypoints),knot);assert.equal(JSON.stringify(g.edges.filter((v:any)=>v!==e)),peers);
});
const app=readFileSync(new URL('yworks_edge_router_lab/app.js',base),'utf8'),apply=app.slice(app.indexOf('  async function apply(){'),app.indexOf('  function download(',app.indexOf('  async function apply(){')));
for(const cancelled of [false,true])test('actual Apply handler delegates source preflight to Worker and preserves history on cancellation: '+cancelled,async()=>{
 const graph={nodes:[{id:'a',x:1,y:2,w:3,h:4}],edges:[{id:'edge',source:'a',target:'a',route:[]}]},jobs:any[]=[];let saves=0,persists=0,states=0;const validation={source:{ok:true},layout:{ok:true},edges:[]};
 const env=vm.createContext({graph,busy:false,drag:null,selectedEdges:new Set(),selectedNodes:new Set(),dirty:false,performance,requestAnimationFrame:(fn:any)=>fn(0),options:()=>opts,studioBridge:{state(){states++;}},$:(id:string)=>({value:id==='scope'?'all':'always'}),C:{validateSource(){throw Error('source check blocked UI');}},toast(){},render(){},persist(){persists++;},save(){saves++;},E:{clone:plain},svg:{setAttribute(){}},runGraphTask:async(msg:any)=>{jobs.push(msg);if(cancelled)throw new Error('操作已取消');return {ok:true,graph:plain(graph),validation,routed:1,retained:0,optimization:{checked:1,pendingIds:[],ms:1}};}});
 vm.runInContext(apply,env);await env.apply();assert.equal(jobs.length,1);assert.equal(jobs[0].task,'optimize');assert.deepEqual(plain(jobs[0].ids),['edge']);assert.equal(env.busy,false);assert.equal(saves,cancelled?0:1);assert.equal(persists,cancelled?0:1);assert.ok(states>=2);if(cancelled)assert.equal(env.graph,graph);
});
test('bridge emits exactly one complete document after Apply while keeping busy and cancellation status live',async()=>{
 let listener:any,busy=false,builds=0,bridge:any;const messages:any[]=[],parent={postMessage:(v:any)=>messages.push(v)},root:any={parent,location:{origin:'http://localhost:8790',search:''},addEventListener(_:string,fn:any){listener=fn;}};
 const env=vm.createContext({window:root,document:{},URLSearchParams});vm.runInContext(readFileSync(new URL('yworks_edge_router_lab/studio-bridge.js',base),'utf8'),env);
 bridge=root.ArchCanvasPreviewBridge.create({started:async()=>{},isBusy:()=>busy,state:()=>{builds++;return {document:{graph:{nodes:[]}}};},interaction:()=>({caseId:'test',busy,canCancel:busy}),command:async()=>{busy=true;bridge.state();busy=false;bridge.state();}});bridge.ready();messages.length=0;builds=0;
 listener({source:parent,origin:root.location.origin,data:{type:'archcanvas:preview:apply-layout',requestId:'apply'}});for(let i=0;i<12;i++)await Promise.resolve();assert.equal(builds,1);assert.equal(messages.filter(v=>v.document).length,1);assert.equal(messages.at(-1).type,'archcanvas:preview:applied');assert.ok(messages.some(v=>v.type.endsWith(':interaction')&&v.canCancel));
});
