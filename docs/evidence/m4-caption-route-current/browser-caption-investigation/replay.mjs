import {readFileSync,writeFileSync} from 'node:fs';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../../../..');
const baseline=await import(pathToFileURL(path.join(here,'snapshots/baseline/core/index.ts')));
const current=await import(pathToFileURL(path.join(here,'snapshots/current/core/index.ts')));
const envelope=JSON.parse(readFileSync(path.join(root,'docs/evidence/m4-caption-route-current/browser/pre-ui/saved-transformer-envelope.json'))),document=envelope.document;
const encoder='repeat:instance:model.Transformer.encoder',decoder='call:instance:model.Transformer.decoder';
function memory(scene){const edge=scene.edges.find(e=>e.id==='edge:44'),a=scene.nodes.find(n=>n.id===encoder),b=scene.nodes.find(n=>n.id===decoder);return {edge,encoder:{x:a.x,y:a.y,width:a.width,height:a.height},decoder:{x:b.x,y:b.y,width:b.width,height:b.height},verticalDifference:Math.abs(a.y-b.y),guides:(scene.captionGuides??[]).filter(g=>g.sceneEdgeId===edge.id),diagnostics:scene.diagnostics.filter(d=>d.edgeId===edge.id),sourceDigest:scene.sourceDigest,irDigest:scene.irDigest,sourceFacts:scene.sourceFacts};}
const records=[];
for(const [axis,deltas]of [['dy',[-24,-16,-15,-14,0,14,15,16,24]],['dx',[-24,24]]])for(const delta of deltas){
 const operations=[{type:'move',ids:[encoder],dx:axis==='dx'?delta:0,dy:axis==='dy'?delta:0}],before=JSON.stringify(document),edited=current.applyVisualBatch(document,operations);
 const old=baseline.buildScene(edited),next=current.buildScene(edited),again=current.buildScene(edited),detail=current.buildExportScene(edited,{nodeId:document.expandedIds[0]});
 records.push({name:`encoder-${axis}-${delta}`,operations,inputUnchanged:JSON.stringify(document)===before,architectureExact:JSON.stringify(edited.architecture)===JSON.stringify(document.architecture),deterministic:JSON.stringify(next)===JSON.stringify(again),baseline:memory(old),current:memory(next),detailMemory:memory(detail)});
 if(axis==='dy'&&delta===24){writeFileSync(path.join(here,'encoder-down-current.scene.json'),JSON.stringify(next,null,2)+'\n');writeFileSync(path.join(here,'encoder-down-current.svg'),current.renderSvg(next));writeFileSync(path.join(here,'encoder-down-baseline.scene.json'),JSON.stringify(old,null,2)+'\n');writeFileSync(path.join(here,'encoder-down-baseline.svg'),baseline.renderSvg(old));writeFileSync(path.join(here,'encoder-down-draft-document.json'),JSON.stringify(edited,null,2)+'\n');}
}
const explicit=structuredClone(document);for(const edge of explicit.architecture.edges.filter(e=>e.role==='memory'))edge.label='memory';
// Static counterfactual copied IR only; no original CanvasDocument/source bytes are changed.
const counterfactual=current.applyVisualBatch(explicit,[{type:'move',ids:[encoder],dx:0,dy:24}]);
const cf=current.buildScene(counterfactual);writeFileSync(path.join(here,'explicit-label-counterfactual.scene.json'),JSON.stringify(cf,null,2)+'\n');
const report={schema:'archcanvas-memory-label-threshold-replay/1',node:{executable:process.execPath,version:process.version},documentId:document.id,canonicalEdge:document.architecture.edges.find(e=>e.id==='edge:44'),records,explicitLabelCounterfactual:memory(cf),limits:['All moves occur in detached in-memory document copies','No source model executed','Counterfactual explicit labels alter only a copied static IR; not an authorized production semantic operation','No source/build/service/save/history mutation','Finite threshold matrix does not certify general caption stability']};
writeFileSync(path.join(here,'replay.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(records.map(r=>({name:r.name,gap:r.current.verticalDifference,old:r.baseline.edge.label,current:r.current.edge.label,guides:r.current.guides.length,detail:r.detailMemory.edge.label}))));
