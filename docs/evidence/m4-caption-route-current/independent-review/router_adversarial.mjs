import { writeFileSync,mkdirSync } from 'node:fs';
import { fileURLToPath,pathToFileURL } from 'node:url';
import path from 'node:path';
const here=path.dirname(fileURLToPath(import.meta.url)),tag=process.argv[2]??'attempt-1';
const baseline=await import(pathToFileURL(path.join(here,'snapshots/baseline/core/orthogonalRouter.ts')));
const candidate=await import(pathToFileURL(path.join(here,`snapshots/${tag}/core/orthogonalRouter.ts`)));
const node=(id,x,y,width=20,height=20,extras={})=>({id,x,y,width,height,headerHeight:height,expanded:false,expandable:false,ports:[],...extras});
const baseNodes=[node('source',0,40),node('target',200,40)];
const request=(id,route,extras={})=>({sourceId:'source',targetId:'target',start:{x:20,y:50},end:{x:200,y:50},preferredPath:route,tensorId:id,role:'data',...extras});
const main='M 20 50 H 26 V 100 H 194 V 50 H 200';
const records=[];
function capture(name,nodes,requests){
 const before=JSON.stringify({nodes,requests}); const old=baseline.createOrthogonalRouter(nodes).batch(requests);
 const next=candidate.createOrthogonalRouter(nodes).batch(requests),repeat=candidate.createOrthogonalRouter(nodes).batch(requests);
 records.push({name,nodes,requests,old,next,immutable:before===JSON.stringify({nodes,requests}),deterministic:JSON.stringify(next)===JSON.stringify(repeat)});
}
capture('clear-detour',baseNodes,[request('t',main)]);
capture('unrelated-card-clearance', [...baseNodes,node('obstacle',90,40)], [request('t',main)]);
capture('repeat-backplates', [...baseNodes,node('repeat',90,40,20,20,{repeat:{count:3,sharing:'independent'}})], [request('t',main)]);
capture('expanded-ancestor-header', [...baseNodes.map(n=>({...n,parentId:'group'})),node('group',-10,-10,240,130,{expanded:true,headerHeight:30})], [request('t',main)]);
capture('preserve-source-short-lead',baseNodes,[request('t','M 20 50 H 23 V 100 H 197 V 50 H 200')]);
capture('original-u-turn-retained',baseNodes,[request('t','M 20 50 H 30 V 100 H 194 H 180 V 50 H 200')]);
capture('same-coordinate-subpath',baseNodes,[request('t','M 20 50 H 26 V 80 H 90 V 100 H 194 V 50 H 200')]);
for(const y of [30,49.995,50,50.005,60,80,100,100.005,120]){
 const peerNodes=[node('peerSource',60,y-20),node('peerTarget',60,150)];
 const peer={sourceId:'peerSource',targetId:'peerTarget',start:{x:70,y},end:{x:70,y:150},preferredPath:`M 70 ${y} V 150`,tensorId:'peer',role:'data'};
 for(const same of [false,true]) capture(`peer-contact-y${y}-${same?'same':'different'}-tensor`,[...baseNodes,...peerNodes],[request(same?'peer':'main',main),peer]);
}
for(const inset of [0,.005,.02,1,3,6]){
 const obstacles=[node('obstacle',90,50+inset,20,20)];
 capture(`close-body-clearance-${inset}`,[...baseNodes,...obstacles],[request('t',main)]);
}
for(const y of [70,90,130]) for(const side of ['above','below']){
 const h=side==='above'?-y:y;
 const poly=`M 20 50 H 26 V ${50+h} H 80 V ${50+h+20} H 140 V ${50+h} H 194 V 50 H 200`;
 capture(`multi-splice-${side}-${y}`,baseNodes,[request('t',poly)]);
}
capture('over-node-cap',[...baseNodes,...Array.from({length:1023},(_,i)=>node('far:'+i,10000+i*30,10000))],[request('t',main)]);
capture('over-route-cap',baseNodes,Array.from({length:513},(_,i)=>request('shared',main)));
const longRoute='M 20 50 H 26 '+Array.from({length:34},(_,i)=>`V ${100+i*20} H ${i%2?40:30}`).join(' ')+' V 900 H 194 V 50 H 200';
capture('over-points-per-route',baseNodes,[request('t',longRoute)]);
capture('over-total-point-cap',baseNodes,Array.from({length:450},(_,i)=>request('shared',`M 20 50 H 26 V ${100+i*10} H 80 V ${120+i*10} H 140 V ${100+i*10} H 194 V 50 H 200`)));
const out=path.join(here,tag);mkdirSync(out,{recursive:true});writeFileSync(path.join(out,'router-adversarial.json'),JSON.stringify({tag,records},null,2)+'\n');
console.log(JSON.stringify({tag,cases:records.length,immutable:records.every(c=>c.immutable),deterministic:records.every(c=>c.deterministic),changedRoutes:records.reduce((s,c)=>s+c.next.filter((r,i)=>r.path!==c.old[i].path).length,0)}));
