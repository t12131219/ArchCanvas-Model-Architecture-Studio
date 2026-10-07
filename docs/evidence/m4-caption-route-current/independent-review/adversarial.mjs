import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath,pathToFileURL } from 'node:url';
import path from 'node:path';
const here=path.dirname(fileURLToPath(import.meta.url)), tag=process.argv[2]??'attempt-1';
const { placeEdgeLabels }=await import(pathToFileURL(path.join(here,`snapshots/${tag}/core/edgeLabelPlacement.ts`)));
const source=JSON.parse(readFileSync(path.join(here,'../../m4-visual-next-current/review/fresh-source-core/transformer-level0-paper-180.scene.json'),'utf8'));
const memory=source.edges.find(e=>e.label==='memory');
const endpointNodes=source.nodes.filter(n=>[memory.sourceId,memory.targetId].includes(n.id));
const extra=(id,route,label,x,y)=>({...memory,id,sourceId:'synthetic-source',targetId:'synthetic-target',canonicalEdgeIds:[id],tensorId:'synthetic:'+id,path:route,label,labelX:x,labelY:y});
const cases=[];
function capture(name,nodes,edges,bodies=[]){
  const before=JSON.stringify({nodes,edges,bodies}); const a=placeEdgeLabels(nodes,edges,bodies); const b=placeEdgeLabels(nodes,edges,bodies);
  const project=r=>({placements:[...r.placements],guides:r.guides,diagnostics:r.diagnostics});
  const scene={bounds:{x:-1000,y:-1000,width:5000,height:5000},nodes,edges:edges.map(e=>({...e,...(a.placements.get(e.id)?{labelX:a.placements.get(e.id).x,labelY:a.placements.get(e.id).y}: {})})),captionGuides:a.guides,annotations:bodies,diagnostics:a.diagnostics};
  cases.push({name,input:{nodes,edges,bodies},scene,immutable:before===JSON.stringify({nodes,edges,bodies}),deterministic:JSON.stringify(project(a))===JSON.stringify(project(b))});
}
capture('migrating-later-caption-guide-stroke-boundary',endpointNodes,[memory,extra('later-caption','M 300 453.5 H 315','q',300.8,438.5),extra('initial-caption-blocker','M 290 432 H 315','',0,0)]);
capture('migrating-caption-interior-stroke-boundary',endpointNodes,[memory,extra('later-caption','M 300 469.5 H 315','q',300.8,438.5),extra('initial-caption-blocker','M 290 432 H 315','',0,0)]);
for(const shift of [-.39,-.3,-.2,-.1,0,.1,.2,.3,.39,.4,.41]){
  capture(`reservation-boundary-${shift}`,endpointNodes,[memory,extra('later-caption','M 300 469.5 H 315','q',298.5+shift+2,438.5),extra('initial-caption-blocker','M 290 432 H 315','',0,0)]);
}
capture('clear-source-memory',source.nodes,source.edges,source.annotations);
capture('expanded-header-and-repeat',endpointNodes.map((n,i)=>i?{...n,expanded:true,headerHeight:46}:n),[memory]);
capture('all-space-blocked',endpointNodes,[memory],[{id:'blocking-note',x:210,y:350,width:200,height:220}]);
capture('distant-caption-no-association',[],[extra('distant','M 10 10 H 100','caption',500,500)]);
capture('shared-route-cannot-license-guide-contact',endpointNodes,[memory,{...memory,id:'shared',label:'',labelX:0,labelY:0}]);
capture('guide-name-collision',endpointNodes,[memory,{...extra('caption-guide:'+memory.id,'M 1000 1000 H 1100','',0,0)}]);
capture('129-caption-precap',[],Array.from({length:129},(_,i)=>extra('cap:'+i,`M ${i*100} 100 H ${i*100+50}`,'q',i*100,90)));
capture('80-caption-checkcap',[],Array.from({length:80},(_,i)=>extra('cap:'+i,`M ${i*100} 100 H ${i*100+50}`,'longer caption',i*100,100)));
const out=path.join(here,tag);mkdirSync(out,{recursive:true});
writeFileSync(path.join(out,'caption-adversarial.json'),JSON.stringify({tag,cases},null,2)+'\n');
console.log(JSON.stringify({tag,cases:cases.length,immutable:cases.every(c=>c.immutable),deterministic:cases.every(c=>c.deterministic),first:cases[0].scene.captionGuides,firstPlacements:cases[0].scene.edges.map(e=>({id:e.id,x:e.labelX,y:e.labelY}))}));
