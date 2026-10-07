import { writeFileSync } from 'node:fs';
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';
const here=path.dirname(fileURLToPath(import.meta.url));
const {placeEdgeLabels}=await import(pathToFileURL(path.join(here,'../snapshots/continuation-review/attempt-1/core/edgeLabelPlacement.ts')));
const node=(id,x,y,width,height)=>({id,x,y,width,height,headerHeight:height,expanded:false,expandable:false,ports:[]});
const edge=(id,path,label,x,y,width=1.5)=>({id,path,label,labelX:x,labelY:y,sourceId:'a',targetId:'b',source:{nodeId:'a',portId:'out'},target:{nodeId:'b',portId:'in'},canonicalEdgeIds:[id],tensorId:id,role:'data',stroke:'#000',width,dashed:false});
const cases=[];
for(const dx of [.1,.3,.4,.55,.75,.8,1,1.14,1.15,1.16,1.5]){
 const input={nodes:[node('a',0,0,100,60),node('b',102,0,100,60)],edges:[edge('own','M 100 30 H 102','q',90,73),edge('foreign',`M ${101+dx} 31 V 60`,'',0,0)]};
 const before=JSON.stringify(input),result=placeEdgeLabels(input.nodes,input.edges);
 cases.push({name:`foreign-stroke-distance-${dx}`,input,immutable:JSON.stringify(input)===before,placements:[...result.placements],guides:result.guides,diagnostics:result.diagnostics});
}
writeFileSync(path.join(here,'foreign-stroke-probe.json'),JSON.stringify({cases},null,2)+'\n');
console.log(JSON.stringify(cases.map(c=>({name:c.name,guides:c.guides,placements:c.placements,diagnosticCount:c.diagnostics.length}))));
