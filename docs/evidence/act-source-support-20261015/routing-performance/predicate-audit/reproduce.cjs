const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const base=path.resolve(__dirname, '../../../../..');
const baseline=base+'/docs/evidence/act-source-support-20261015/routing-performance/before/router.js';
const current=base+'/studio/public/preview/yworks_edge_router_lab/router.js';
function load(file){const context=vm.createContext({});const code=fs.readFileSync(file,'utf8').replace('const api = { routeEdge,','const api = { wireContact,inside,routeEdge,');vm.runInContext(code,context);return context.EdgeRouterLabRouting;}
const old=load(baseline),next=load(current);let state=20261015;const random=()=>((state=(Math.imul(state,1664525)+1013904223)>>>0)/4294967296),EPS=1e-6;
let wireChecks=0,rectangleChecks=0,wireMismatch=0,rectangleMismatch=0,examples=[];
function wire(a,b,c,d){wireChecks++;const x=old.wireContact(a,b,c,d),y=next.wireContact(a,b,c,d);if(x!==y){wireMismatch++;if(examples.length<8)examples.push({a,b,c,d,before:x,after:y});}}
const move=(p,turn,scale,ox,oy)=>{for(let i=0;i<turn;i++)p={x:-p.y,y:p.x};return{x:p.x*scale+ox,y:p.y*scale+oy};};
for(const scale of [.001,.01,.1,1,10,1000])for(let turn=0;turn<4;turn++)for(const ox of [0,100]){
 const cv=p=>move(p,turn,scale,ox,-ox);
 for(const off of [0,EPS/2,EPS,EPS*2,EPS*10,.001])wire(cv({x:.25,y:off}),cv({x:.75,y:off}),cv({x:0,y:0}),cv({x:1,y:0}));
}
for(let i=0;i<30000;i++){
 const scale=10**(random()*7-4),turn=i%4,ox=(random()-.5)*1000,oy=(random()-.5)*1000;
 const cv=p=>move(p,turn,scale,ox,oy);let a,b,c,d;
 if(i%3===0){const length=.1+random()*10,offset=(random()-.5)*EPS*50/scale;a={x:length*.2,y:offset};b={x:length*.8,y:offset};c={x:0,y:0};d={x:length,y:0};}
 else{a={x:random()*10,y:random()*10};b=i%2?{x:a.x,y:random()*10}:{x:random()*10,y:a.y};c={x:random()*10,y:random()*10};d=i%2?{x:random()*10,y:c.y}:{x:c.x,y:random()*10};}
 wire(cv(a),cv(b),cv(c),cv(d));
 const r={x:(random()-.5)*200,y:(random()-.5)*200,w:random()*10+.00001,h:random()*10+.00001};
 const horizontal=i%2===0,axis=horizontal?'y':'x',extent=horizontal?'h':'w';
 const fixed=[r[axis]-EPS*2,r[axis],r[axis]+EPS,r[axis]+r[extent]/2,r[axis]+r[extent]-EPS,r[axis]+r[extent],r[axis]+r[extent]+EPS*2][i%7];
 const p=horizontal?{x:r.x-r.w,y:fixed}:{x:fixed,y:r.y-r.h},q=horizontal?{x:r.x+2*r.w,y:fixed}:{x:fixed,y:r.y+2*r.h};
 const candidates=fixed>=r[axis]&&fixed<=r[axis]+r[extent]?[r]:[];
 rectangleChecks++;if(old.intersectsRect(p,q,r)!==candidates.some(x=>old.intersectsRect(p,q,x)))rectangleMismatch++;
 // Grid-point inside uses the same row predicate.
 const point={x:r.x+r.w/2,y:fixed},rows=fixed>=r.y&&fixed<=r.y+r.h?[r]:[];
 rectangleChecks++;if(old.inside(point,r)!==rows.some(x=>old.inside(point,x)))rectangleMismatch++;
}
const out={schema:'router-predicate-differential/1',seed:20261015,wireChecks,rectangleChecks,wireMismatch,rectangleMismatch,examples,scope:'Only line-contact predicate and row/column obstacle broad-phase; not a route matrix.',beforeFile:baseline,afterFile:current};
console.log(JSON.stringify(out,null,2));if(wireMismatch||rectangleMismatch)process.exitCode=1;
