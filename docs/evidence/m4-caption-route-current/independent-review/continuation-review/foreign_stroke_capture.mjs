import { writeFileSync } from 'node:fs';
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';
const here=path.dirname(fileURLToPath(import.meta.url)),tag=process.argv[2];
if(!tag)throw new Error('explicit immutable snapshot tag required');
const {placeEdgeLabels}=await import(pathToFileURL(path.join(here,`../snapshots/${tag}/core/edgeLabelPlacement.ts`)));
const node=(id,x,y,width,height)=>({id,x,y,width,height,headerHeight:height,expanded:false,expandable:false,ports:[]});
const edge=(id,path,label,x,y,width=1.5)=>({id,path,label,labelX:x,labelY:y,sourceId:'a',targetId:'b',source:{nodeId:'a',portId:'out'},target:{nodeId:'b',portId:'in'},canonicalEdgeIds:[id],tensorId:id,role:'data',stroke:'#000',width,dashed:false});
const cases=[];
for(const [dx,width] of [[.1,1.5],[.3,1.5],[.4,1.5],[.55,1.5],[.75,1.5],[.8,1.5],[1,1.5],[1.14,1.5],[1.15,1.5],[1.16,1.5],[1.5,1.5],[1.2,3],[2.1,3],[6.4,12]]){
 const input={nodes:[node('a',0,0,100,60),node('b',102,0,100,60)],edges:[edge('own','M 100 30 H 102','q',90,73),edge('foreign',`M ${101+dx} 31 V 60`,'',0,0,width)]};
 const before=JSON.stringify(input),a=placeEdgeLabels(input.nodes,input.edges),b=placeEdgeLabels(input.nodes,input.edges);
 const project=r=>({placements:[...r.placements],guides:r.guides,diagnostics:r.diagnostics});
 const scene={nodes:input.nodes,edges:input.edges.map(e=>({...e,...(a.placements.get(e.id)?{labelX:a.placements.get(e.id).x,labelY:a.placements.get(e.id).y}:{})})),captionGuides:a.guides,diagnostics:a.diagnostics,bounds:{x:-100,y:-100,width:1000,height:1000}};
 cases.push({name:`foreign-stroke-distance-${dx}-width-${width}`,input,immutable:JSON.stringify(input)===before,deterministic:JSON.stringify(project(a))===JSON.stringify(project(b)),scene});
}
const invalid=[];
for(const width of [NaN,Infinity,-Infinity,-1]){
 const nodes=[node('a',0,0,100,60),node('b',102,0,100,60)],edges=[edge('own','M 100 30 H 102','q',90,73),edge('foreign','M 101.55 31 V 60','',0,0,width)];
 const result=placeEdgeLabels(nodes,edges);
 invalid.push({width:String(width),inputWidthPreserved:Object.is(edges[1].width,width),placements:[...result.placements],guides:result.guides,diagnostics:result.diagnostics,
  honest:result.guides.length===0&&result.placements.get('own')?.x===90&&result.placements.get('own')?.y===73&&result.diagnostics.some(d=>d.edgeId==='own'&&d.code==='layout-edge-label-association'&&d.message.includes('stroke width'))});
}
writeFileSync(path.join(here,'..',tag,'foreign-stroke-capture.json'),JSON.stringify({tag,cases,invalid},null,2)+'\n');
console.log(JSON.stringify({tag,cases:cases.length,immutable:cases.every(c=>c.immutable),deterministic:cases.every(c=>c.deterministic),invalidCases:invalid.length,allInvalidHonest:invalid.every(c=>c.honest&&c.inputWidthPreserved)}));
