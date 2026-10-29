import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const base=new URL('../public/preview/',import.meta.url),ctx=vm.createContext({performance});
for(const file of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine'])vm.runInContext(readFileSync(new URL(`yworks_edge_router_lab/${file}.js`,base),'utf8'),ctx);
vm.runInContext(readFileSync(new URL('semantic_studio/geometry-index.js',base),'utf8'),ctx);
const R=ctx.EdgeRouterLabRouting,C=ctx.SummaryConstraints,P=ctx.SummaryPhysicalPorts;
const plain=(v:any)=>JSON.parse(JSON.stringify(v));
let seed=81723;
const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/2**32;};

// Frozen mathematical oracle, independent of the new boolean hot path.
function borderOracle(n:any,a:any,b:any,pad:number){
 const epsilon=1e-5;
 for(const side of ['left','right','top','bottom']){
  const vertical=side==='left'||side==='right',axis=vertical?'x':'y',along=vertical?'y':'x';
  const value=n[axis]+(['right','bottom'].includes(side)?n[vertical?'w':'h']:0),low=n[along],high=low+n[vertical?'h':'w'];
  const distance=Math.max(Math.abs(a[axis]-value),Math.abs(b[axis]-value));
  const length=Math.min(high,Math.max(a[along],b[along]))-Math.max(low,Math.min(a[along],b[along]));
  if(length>epsilon&&distance<pad-epsilon&&Math.abs(a[axis]-b[axis])<epsilon)return true;
 }
 return false;
}
test('boolean border predicate equals original stroke math for near-axis, short and ordinary segments',()=>{
 for(let i=0;i<10000;i++){
  const n={x:random()*1000-500,y:random()*1000-500,w:10+random()*300,h:10+random()*300},pad=random()*20;
  const a={x:n.x+(random()-.1)*n.w,y:n.y+(random()-.1)*n.h},b={x:a.x+(random()-.5)*500,y:a.y+(random()-.5)*500};
  if(i%3===0)b.x=a.x+(i%5)*3e-6;
  if(i%3===1)b.y=a.y+(i%5)*3e-6;
  assert.equal(C.segmentBorderContact(a,b,n,pad),borderOracle(n,a,b,pad));
 }
});

function graph(){
 const nodes=Array.from({length:144},(_,i)=>({id:'n'+i,x:(i%12)*200+50,y:Math.floor(i/12)*120+50,w:90,h:40,parent:null,expanded:false,html:'',routingObstacle:true}));
 const edges=nodes.slice(1).map((n,i)=>({id:'e'+i,source:nodes[i].id,target:n.id,fixedSource:{side:'right',fraction:.5},fixedTarget:{side:'left',fraction:.5},portPolicy:{source:{mode:'free',spacing:6},target:{mode:'free',spacing:6}},route:[{x:nodes[i].x+90,y:nodes[i].y+20},{x:n.x,y:n.y+20}],style:'orthogonal',arrow:'target'}));
 return C.initialize({nodes,edges,canvas:[2600,1800]});
}
test('spatial validation retains every exact violation of a full node scan',()=>{
 const g=graph(),indexed=C.validationContext(g),linear={...indexed,spatialNodes:null,spatialIndex:null};
 assert.ok(indexed.spatialIndex);
 // Include a caption outside its owner and an expanded frame crossing.
 g.nodes[25].expanded=true;g.nodes[25].labelObstacles=[{x:-20,y:-50,w:180,h:30}];
 const current=C.validationContext(g),full={...current,spatialNodes:null,spatialIndex:null};
 for(const e of g.edges)for(const points of [e.route,[e.route[0],{x:e.route[0].x,y:e.route.at(-1).y},e.route.at(-1)],
  [{x:0,y:0},{x:2600,y:1800}]]){
  assert.deepEqual(plain(C.validate(g,e,points,current).violations).sort(),plain(C.validate(g,e,points,full).violations).sort());
 }
 assert.equal(C.validate(g,g.edges[0],g.edges[0].route,indexed).ok,C.validate(g,g.edges[0],g.edges[0].route,linear).ok);
});

test('incident port index matches scans and reads peers at their current physical slots',()=>{
 const g=graph(),context=P.context(g);
 for(const e of g.edges){e.physicalSource={side:'right',fraction:.6};e.physicalTarget={side:'left',fraction:.4};}
 for(const e of g.edges){
  assert.deepEqual(plain(P.errors(g,e,e.route,context)),plain(P.errors(g,e,e.route)));
  for(const side of ['source','target'])assert.deepEqual(plain(P.candidates(g,e,side,'any',context)),plain(P.candidates(g,e,side)));
 }
 const peer={...g.edges[0],id:'peer',binding:{src:'different value'},physicalSource:{side:'right',fraction:.7}};g.edges.push(peer);
 const fresh=P.context(g),edge=g.edges[0];edge.physicalSource={side:'right',fraction:.7};
 assert.equal(P.permitted(g,edge,'source',edge.physicalSource,fresh),false);
 peer.physicalSource={side:'bottom',fraction:.5};
 assert.equal(P.permitted(g,edge,'source',edge.physicalSource,fresh),P.permitted(g,edge,'source',edge.physicalSource));
 assert.equal(P.permitted(g,edge,'source',edge.physicalSource,fresh),true);
});

test('indexed crossing statistics exactly match the quadratic pair oracle',()=>{
 const edges=Array.from({length:200},(_,i)=>({route:Array.from({length:2+i%5},()=>({x:Math.round(random()*1000)/10,y:Math.round(random()*1000)/10}))}));
 let crossings=0,length=0,bends=0;
 for(const e of edges){bends+=e.route.length-2;for(let i=1;i<e.route.length;i++)length+=R.dist(e.route[i-1],e.route[i]);}
 for(let i=0;i<edges.length;i++)for(let j=i+1;j<edges.length;j++)for(let u=1;u<edges[i].route.length;u++)for(let v=1;v<edges[j].route.length;v++)if(R.crossing(edges[i].route[u-1],edges[i].route[u],edges[j].route[v-1],edges[j].route[v]))crossings++;
 assert.deepEqual(plain(R.stats(edges)),{length:Math.round(length),bends,crossings});
});

test('indexed routing matches full obstacle scans and does not reuse geometry across edits',()=>{
 const g=graph(),edge={...g.edges[0],route:[],contract:null},options={width:2600,height:1800,margin:3,firstLegal:true};
 const index=ctx.SemanticGeometryIndex;
 for(const dx of [0,110,-70]){
  g.nodes[30].x+=dx;
  const fast=R.routeEdge(edge,g.nodes,[],options);ctx.SemanticGeometryIndex=null;
  let slow;try{slow=R.routeEdge(edge,g.nodes,[],options);}finally{ctx.SemanticGeometryIndex=index;}
  assert.deepEqual(plain(fast),plain(slow));
 }
});
