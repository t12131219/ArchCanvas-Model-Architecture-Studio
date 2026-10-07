import { readFileSync,writeFileSync } from 'node:fs';
import { fileURLToPath,pathToFileURL } from 'node:url';import path from 'node:path';
const here=path.dirname(fileURLToPath(import.meta.url));const tag=process.argv[2]??'attempt-2';
const {placeEdgeLabels}=await import(pathToFileURL(path.join(here,`snapshots/${tag}/core/edgeLabelPlacement.ts`)));
const old=JSON.parse(readFileSync(path.join(here,'../../m4-visual-next-current/review/fresh-source-core/transformer-level0-paper-180.scene.json'),'utf8'));
const memory=old.edges.find(e=>e.label==='memory'); const endpointNodes=old.nodes.filter(n=>[memory.sourceId,memory.targetId].includes(n.id));
const node=(id,x,y,width,height)=>({id,x,y,width,height,headerHeight:height,expanded:false,expandable:false,ports:[]});
const edge=(id,route,label,x,y,sourceId,targetId)=>({...memory,id,path:route,label,labelX:x,labelY:y,sourceId,targetId,canonicalEdgeIds:[id],tensorId:id});
const cases=[];
function capture(name,nodes,edges){const a=placeEdgeLabels(nodes,edges);cases.push({name,nodes,edges,placements:[...a.placements],guides:a.guides,diagnostics:a.diagnostics});}
for(const delta of [.4,.55,.8,1,1.14,1.15,1.16]){
 const x=298.5+delta;
 capture(`guide-unrelated-route-stroke-${delta}`,[...endpointNodes,node('peerSource',x-97,318,194,62),node('peerTarget',x-97,500,194,62)],[memory,edge('peer',`M ${x} 380 V 500`,'',0,0,'peerSource','peerTarget')]);
}
capture('parallel-guide-strokes',[node('a',0,0,100,60),node('b',102,0,100,60),node('c',101.42,35,.04,10)],
 [edge('first','M 100 30 H 102','q',90,73,'a','b'),edge('second','M 101.46 40 H 102','q',90.61,97,'c','b')]);
writeFileSync(path.join(here,tag,'stroke-probe.json'),JSON.stringify({tag,cases},null,2)+'\n');console.log(JSON.stringify(cases.map(c=>({name:c.name,guides:c.guides,placements:c.placements}))));
