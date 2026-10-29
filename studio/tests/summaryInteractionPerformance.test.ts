import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const base=new URL('../public/preview/',import.meta.url),ctx=vm.createContext({performance,TextEncoder});
const load=(p:string)=>vm.runInContext(readFileSync(new URL(p,base),'utf8'),ctx,{filename:p});
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])load(`yworks_edge_router_lab/${n}.js`);
for(const row of JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json',import.meta.url),'utf8')).files)load(row.path);
load('yworks_edge_router_lab/studio-semantic.js');
const G=ctx.SummaryNativeSemantic,N=ctx.ArchCanvasSemanticView,E=ctx.SummaryEngine;
const catalog=JSON.parse(readFileSync(new URL('data/semantic/studio-catalog.json',base),'utf8'));
const plain=(v:any)=>JSON.parse(JSON.stringify(v));
function strict(graph:any){const v=E.validateView(graph);assert.equal(v.source.ok,true,JSON.stringify(v.source));assert.equal(v.layout.ok,true,JSON.stringify(v.layout));assert.deepEqual(plain(v.edges.filter(([,check]:any)=>!check.ok)),[]);}
for(const id of ['d6df94c94e8a5888','0216717d966327f4'])test(`interactive routes preserve source, valid geometry and reversible history: ${id}`,()=>{
 const m=catalog.models.find((m:any)=>m.id===id),ir=JSON.parse(readFileSync(new URL('data/semantic/'+m.ir.path,base),'utf8'));
 const state=m.presentation?JSON.parse(readFileSync(new URL('data/semantic/'+m.presentation.path,base),'utf8')).default_state:N.state('overview');
 const original=N.prepare({task:'generic-build',ir,state,options:{}}).graph;strict(original);
 const before=JSON.stringify(original),snapshot=N.snapshot(original),target=original.nodes.find((n:any)=>n.expanded&&n.parent&&G.children(original,n.id).length);
 const collapsed=N.prepare({task:'frontier',graph:original,transition:{type:'toggle',id:target.id,expanded:false}}).graph;
 strict(collapsed);assert.ok(collapsed.nodes.length<original.nodes.length);assert.ok(collapsed.nativeRouteReuse.reused>0);
 assert.equal(collapsed.generic.ir,original.generic.ir);assert.equal(JSON.stringify(original),before);
 const reopened=N.prepare({task:'frontier',graph:collapsed,transition:{type:'toggle',id:target.id,expanded:true}}).graph;strict(reopened);
 assert.deepEqual(plain(G.layoutSnapshot(reopened).nodes),plain(G.layoutSnapshot(original).nodes));
 assert.deepEqual(plain(G.layoutSnapshot(reopened).edges),plain(G.layoutSnapshot(original).edges));
 const leaf=reopened.nodes.find((n:any)=>!n.expanded&&!n.modelHeading&&n.parent),moved=G.cloneGeometry(reopened),authority=JSON.stringify(moved.edges.map((e:any)=>e.binding));
 assert.ok(E.move(moved,leaf.id,8,0).has(leaf.id),JSON.stringify(moved.lastMove));assert.equal(moved.nodes.find((n:any)=>n.id===leaf.id).x,leaf.x+8);strict(moved);
 assert.equal(JSON.stringify(moved.edges.map((e:any)=>e.binding)),authority);assert.deepEqual(plain(moved.generic.ir),ir);
 assert.equal(JSON.stringify(snapshot),before,'undo snapshot stays independent');
 const blocked=G.cloneGeometry(reopened),geometry=JSON.stringify([blocked.nodes,blocked.edges]),sibling=blocked.nodes.find((n:any)=>n.id!==leaf.id&&n.parent===leaf.parent&&!n.junction);
 assert.ok(sibling);assert.equal(E.move(blocked,leaf.id,sibling.x-leaf.x,sibling.y-leaf.y).size,0);assert.equal(JSON.stringify([blocked.nodes,blocked.edges]),geometry,'invalid move rolls back routes and nodes');
 const forged=plain(collapsed);forged.generic.ir.nodes[0].label='forged under same digest';
 assert.equal(G.validate(forged,true).ok,false);
 if(id==='d6df94c94e8a5888'){
  let projections=0;const project=G.engine.project;
  try{G.engine.project=(...args:any[])=>{projections++;return project(...args);};N.inspector(collapsed,[]);strict(collapsed);assert.equal(projections,0,'committed frontier metadata must not invalidate its semantic projection');}
  finally{G.engine.project=project;}
  for(const alter of [
   (g:any)=>{g.nodes[1].parent='forged-owner';},
   (g:any)=>{g.nodes[1].expanded=!g.nodes[1].expanded;},
   (g:any)=>{g.nodes[0].modelHeading=!g.nodes[0].modelHeading;},
   (g:any)=>{g.nodes[1].semantic={...g.nodes[1].semantic,label:'forged'};},
   (g:any)=>{g.generic.receipts=plain(g.generic.receipts);g.generic.receipts.node_accounting.visible.pop();},
   (g:any)=>{g.edges[0].binding={...g.edges[0].binding,target_port:'forged'};},
   (g:any)=>{g.edges[0].contract.wire='forged';},
   (g:any)=>{g.edges.pop();}
  ]){const candidate=G.cloneGeometry(collapsed);alter(candidate);assert.equal(E.validateView(candidate).source.ok,false,'geometry certificates cannot license modified source/topology');}
  const candidate=G.cloneGeometry(collapsed),C=ctx.SummaryConstraints,context=C.validationContext(candidate),edge=candidate.edges[0];
  edge.contract.wire='changed within synchronous context';
  assert.equal(C.validate(candidate,edge,edge.route,context).ok,false,'live contract mutation cannot reuse a semantic edge certificate');
 }
});
