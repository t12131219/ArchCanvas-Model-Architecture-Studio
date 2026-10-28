import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const base=new URL('../public/preview/',import.meta.url),ctx=vm.createContext({performance});
const load=(p:string)=>vm.runInContext(readFileSync(new URL(p,base),'utf8'),ctx,{filename:p});
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])load(`yworks_edge_router_lab/${n}.js`);
for(const row of JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json',import.meta.url),'utf8')).files)load(row.path);
load('yworks_edge_router_lab/studio-semantic.js');
const G=ctx.SummaryNativeSemantic,N=ctx.ArchCanvasSemanticView;
const catalog=JSON.parse(readFileSync(new URL('data/semantic/studio-catalog.json',base),'utf8'));
const ir=JSON.parse(readFileSync(new URL('data/semantic/'+catalog.models.find((m:any)=>m.id==='0216717d966327f4').ir.path,base),'utf8'));
test('dense source frontiers wrap without dropping any source node, operand or owner',()=>{
 const root=ir.nodes.find((n:any)=>!n.parent),graph=G.build(ir,{...N.state('overview'),moduleCuts:[{id:root.id,level:'source'}]});
 assert.equal(graph.nodes.length,3371);assert.equal(graph.edges.length,3663);
 assert.ok(Math.max(...graph.canvas)/Math.min(...graph.canvas)<4,'full source canvas must not degenerate into a 68:1 strip');
 assert.equal(G.validate(graph,true).ok,true);
 const by=new Map(graph.nodes.map((n:any)=>[n.id,n]));
 for(const n of ir.nodes){const shown=by.get(n.id)as any;assert.equal(shown.parent,n.parent);if(n.parent){const p=by.get(n.parent)as any;assert.ok(shown.x>=p.x&&shown.y>=p.y&&shown.x+shown.w<=p.x+p.w+.01&&shown.y+shown.h<=p.y+p.h+.01,n.id+' escaped frame');}}
 const raw=new Map(ir.edges.map((e:any)=>[e.id,e]));for(const e of graph.edges)for(const k of ['source','target','source_port','target_port'])assert.equal(e.binding[k],(raw.get(e.id)as any)[k]);
 for(const version of ['native-semantic/16','native-semantic/17']){const doc=G.document(graph);doc.renderer=version;const restored=G.read(doc);
 assert.equal(restored.nativeLayout,null);assert.ok(restored.migration.previousNativeLayout);}
});
test('v16 publication-only mixed layouts preserve manual geometry',()=>{
 const root=ir.nodes.find((n:any)=>!n.parent),graph=G.build(ir,{...N.state('overview'),moduleCuts:[{id:root.id,level:'f0'}]});
 graph.nodes[0].x+=17;const doc=G.document(graph);doc.renderer='native-semantic/16';
 assert.equal(G.stable(G.read(doc).nativeLayout),G.stable(doc.nativeLayout));
});
test('spatial candidate filtering preserves exhaustive source, body, caption and boundary validation',()=>{
 const root=ir.nodes.find((n:any)=>!n.parent),graph=G.build(ir,{...N.state('overview'),moduleCuts:[{id:root.id,level:'source'}]}),C=ctx.SummaryConstraints;
 const indexed=C.validationContext(graph),exhaustive={...indexed,spatialNodes:null};
 for(let i=0;i<graph.edges.length;i+=11){const e=graph.edges[i];for(const points of [e.route,[e.route[0],{x:e.route[0].x+9,y:e.route[0].y},{x:e.route.at(-1).x+9,y:e.route.at(-1).y},e.route.at(-1)]]){
  const normalize=(v:any)=>JSON.stringify([...v].map((x:any)=>typeof x==='string'?x:JSON.stringify(x)).sort());
  assert.equal(normalize(C.validate(graph,e,points,indexed).violations),normalize(C.validate(graph,e,points,exhaustive).violations),e.id+' exact validation');
  assert.equal(normalize(C.laneContacts(graph,e,points,indexed)),normalize(C.laneContacts(graph,e,points,exhaustive)),e.id+' lanes');
 }}
});
test('collinear lane index matches exhaustive overlap detection including epsilon-neighbour buckets',()=>{
 const R=ctx.EdgeRouterLabRouting,E=ctx.SummaryEngine;
 const edges=Array.from({length:180},(_,i)=>({id:String(i),route:[{x:i%9,y:(i%7)*10+(i%3)*.0000004},{x:i%9+30,y:(i%7)*10+(i%3)*.0000004}],contract:{wire:i%8===0?'shared':String(i)}}));
 edges.push(...Array.from({length:40},(_,i)=>({id:'v'+i,route:[{x:i%4+.0000004,y:i},{x:i%4+.0000004,y:i+10}],contract:{wire:'v'+i}})));
 const graph={nodes:[],edges},expected=[];for(let i=0;i<edges.length;i++)for(let j=i+1;j<edges.length;j++){const a=edges[i],b=edges[j];if(a.contract.wire!==b.contract.wire&&R.overlap(...a.route,...b.route)>1e-5)expected.push([a.id,b.id]);}
 const normalize=(v:any)=>JSON.stringify(v.map((x:any)=>x.join('/')).sort());assert.equal(normalize(E.layoutConflicts(graph).wires),normalize(expected));
});
test('candidate peer bounds preserve route choice, crossing cost and overlap rejection',()=>{
 const R=ctx.EdgeRouterLabRouting,nodes=[{id:'s',x:30,y:30,w:40,h:40},{id:'t',x:300,y:200,w:40,h:40}],edge={source:'s',target:'t',fixedSource:{side:'right',fraction:.5},fixedTarget:{side:'left',fraction:.5}};
 const peers=Array.from({length:180},(_,i)=>Object.assign([{x:1000+i*10,y:20},{x:1000+i*10,y:400}],{wire:'far'+i}));
 peers.push(Object.assign([{x:160,y:0},{x:160,y:300}],{wire:'near'}));
 peers.push(Object.assign([{x:70,y:50+.0000004},{x:140,y:50+.0000004}],{wire:'near-epsilon'}));
 for(const quickCandidatesOnly of [true,false])for(const crossingCost of [0,450]){
  const options={width:400,height:400,edgeSpacing:12,crossingCost,quickCandidatesOnly,maxSearchVertices:20000};
  const original=R.routeEdge(edge,nodes,peers,{...options,spatialPrior:false}),indexed=R.routeEdge(edge,nodes,peers,{...options,spatialPrior:true});
  assert.equal(G.stable(indexed),G.stable(original));
 }
});
test('folded source corridor candidates escape a blocked parameter column without a visibility search',()=>{
 const R=ctx.EdgeRouterLabRouting,nodes=[{id:'s',x:180,y:310,w:60,h:40},{id:'t',x:180,y:70,w:60,h:40},{id:'parameter',x:150,y:170,w:120,h:60}];
 const edge={source:'s',target:'t',fixedSource:{side:'top',fraction:.5},fixedTarget:{side:'bottom',fraction:.5}},options={width:500,height:500,margin:6,stub:18,minimumTerminal:9,firstLegal:true,quickCandidatesOnly:true,maxSearchVertices:1};
 const result=R.routeEdge(edge,nodes,[],options);assert.equal(result.ok,true);assert.equal(result.expanded,0);
 for(let i=1;i<result.points.length;i++)assert.equal(R.intersectsRect(result.points[i-1],result.points[i],R.expand(nodes[2],6)),false);
 assert.ok(result.points.some((p:any)=>p.x<150||p.x>270),'must leave the blocked operand column');
 const expired=R.routeEdge(edge,nodes,[],{...options,quickCandidatesOnly:false,deadline:-1});assert.equal(expired.ok,false,'expired full search must remain incomplete');
});
test('returning to an original port cannot collide with a peer which moved while the slot was vacant',()=>{
 const P=ctx.SummaryPhysicalPorts,nodes=[{id:'a',x:0,y:0,w:100,h:80},{id:'b',x:200,y:0,w:100,h:80},{id:'sink',x:100,y:200,w:100,h:80}];
 const make=(id:string,source:string,fraction:number):any=>({id,source,target:'sink',fixedSource:{side:'bottom',fraction:.5},fixedTarget:{side:'top',fraction},portPolicy:{target:{mode:'free',spacing:6,shape:'rectangle'}},projection:{presentationSlots:{target:id}}});
 const a=make('a','a',.3),b=make('b','b',.5),graph={nodes,edges:[a,b]};
 assert.equal(P.permitted(graph,b,'target',b.fixedTarget),true);
 a.physicalTarget={side:'top',fraction:.5};b.physicalTarget={side:'top',fraction:.8};
 assert.equal(P.permitted(graph,b,'target',b.fixedTarget),false);
 assert.equal(P.candidates(graph,b,'target').some((p:any)=>p.side==='top'&&p.fraction===.5),false);
 assert.equal(P.permitted(graph,b,'target',b.physicalTarget),true);
});
test('cached frame broad phase preserves the exact painted-border predicate',()=>{
 const root=ir.nodes.find((n:any)=>!n.parent),graph=G.build(ir,{...N.state('overview'),moduleCuts:[{id:root.id,level:'source'}]}),C=ctx.SummaryConstraints,context=C.validationContext(graph);
 for(let i=0;i<graph.edges.length;i+=37){const e=graph.edges[i],constraints=G.constraints(graph,e,G.routeOptions(),context,C),by=new Map(graph.nodes.map((n:any)=>[n.id,n])),ids=new Set<string>();
  for(const id of [e.source,e.target]){let n=by.get(id)as any;while(n){if(n.expanded&&!n.modelHeading)ids.add(n.id);n=by.get(n.parent);}}
  for(const id of ids){const n=by.get(id)as any,p=C.borderClearance(e,n);for(const d of [-p-1,-p+.000001,0,p-.000001,p+1])for(const [a,b]of [[{x:n.x+d,y:n.y+3},{x:n.x+d,y:n.y+n.h-3}],[{x:n.x+3,y:n.y+d},{x:n.x+n.w-3,y:n.y+d}]])
   assert.equal(constraints.segmentAllowed(a,b),![...ids].some(id=>C.borderContacts(e,by.get(id),[a,b]).length),e.id+' border '+id);
  }
 }
});
test('translated route proposals recheck target obstacles and occupied wire identities',()=>{
 const P=ctx.SummaryPhysicalPorts,C=ctx.SummaryConstraints,E=ctx.SummaryEngine;
 const graph:any={nodes:[{id:'a',label:'value',x:20,y:20,w:40,h:40},{id:'b',label:'sink',x:20,y:180,w:40,h:40},{id:'c',label:'value',x:220,y:20,w:40,h:40},{id:'d',label:'sink',x:220,y:180,w:40,h:40}],edges:[],canvas:[400,300],nativeRouting:{complete:false}};
 const make=(id:string,source:string,target:string,offset:number)=>({id,source,target,route:[{x:40+offset,y:60},{x:40+offset,y:180}],fixedSource:{side:'bottom',fraction:.5},fixedTarget:{side:'top',fraction:.5},portPolicy:{source:{mode:'fixed'},target:{mode:'fixed'}},binding:{kind:'data',source_port:'out',target_port:'in'},contract:{wire:id,source,target,minimumTerminal:9,gates:[]},failed:false});
 const first=make('first','a','b',0),second=make('second','c','d',200);graph.edges=[first,second];C.initialize(graph);let context=C.validationContext(graph),cache=G.routePatternCache(graph);
 assert.equal(cache.reuse(second,[],context,G.routeOptions())?.ok,true);assert.equal(G.stable(second.route),G.stable([{x:240,y:60},{x:240,y:180}]));
 const peer=Object.assign([{x:240,y:90},{x:240,y:150}],{wire:'different'});assert.equal(cache.reuse(second,[peer],context,G.routeOptions()),null);
 graph.nodes.push({id:'block',label:'obstacle',x:225,y:100,w:30,h:30});context=C.validationContext(graph);cache=G.routePatternCache(graph);assert.equal(cache.reuse(second,[],context,G.routeOptions()),null);
});

test('compact source search keeps every obstacle and falls back to full lanes',()=>{
 const R=ctx.EdgeRouterLabRouting,nodes=[{id:'s',x:60,y:650,w:50,h:40},{id:'t',x:650,y:60,w:50,h:40},
  ...Array.from({length:8},(_,i)=>({id:'wall'+i,x:150+i*60,y:i%2?1:230,w:22,h:510}))];
 const edge={source:'s',target:'t',fixedSource:{side:'right',fraction:.5},fixedTarget:{side:'bottom',fraction:.5}},before=G.stable([edge,nodes]);
 for(const compactCoordinates of [1,8,64]){
  const result=R.routeEdge(edge,nodes,[],{width:850,height:850,margin:3,stub:12,firstLegal:true,compactCoordinates,maxSearchVertices:100000});
  assert.equal(result.ok,true,'compact/fallback maze '+compactCoordinates);
  for(let i=1;i<result.points.length;i++)for(const n of nodes.slice(2))assert.equal(R.intersectsRect(result.points[i-1],result.points[i],R.expand(n,3)),false);
 }
 assert.equal(G.stable([edge,nodes]),before,'candidate search must not mutate source or obstacles');
});
