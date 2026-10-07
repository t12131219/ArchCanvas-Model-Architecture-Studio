import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
// An explicit, separate three-point horizontal gap frontier. Product imports
// only capture outputs; audit_gap.py supplies the independent literal oracle.
const here=path.dirname(fileURLToPath(import.meta.url)),tag=process.argv[2],suite=process.argv[3]??'port-gap';
if(!['before','label-only','after'].includes(tag))throw new Error('Select a frozen core.');
if(!['port-gap','side-gap'].includes(suite))throw new Error('Select port-gap or side-gap.');
const core=await import(pathToFileURL(path.join(here,`snapshots/${tag}/core/index.ts`)));
const source=JSON.parse(readFileSync(path.join(here,'source-envelope.json'))).document;
const unchanged=JSON.stringify(source),rootId=source.expandedIds[0],encoder='repeat:instance:model.Transformer.encoder';
const moves=(suite==='port-gap'?[34,35,36]:[41,42,43]).map(dx=>({name:`dx${dx}`,dx,dy:0}));
const directory=`${suite==='port-gap'?'gap':'side-gap'}-${tag}`,out=path.join(here,directory);mkdirSync(out,{recursive:false});
const sha=x=>createHash('sha256').update(x).digest('hex');
const write=(name,value)=>{const raw=JSON.stringify(value,null,2)+'\n';writeFileSync(path.join(out,name),raw);return {path:`${directory}/${name}`,bytes:Buffer.byteLength(raw),sha256:sha(raw)};};
const documentRecords=[],sceneRecords=[];
for(const mode of ['default','empty','custom']){
 const base=structuredClone(source);
 if(mode!=='default')for(const edge of base.architecture.edges.filter(e=>e.role==='memory'))edge.label=mode==='empty'?'':'memory context';
 for(const move of moves){
  const history=core.createHistory(base),prior=JSON.stringify(history);
  const applied=core.reduceHistory(history,{type:'apply',operations:[{type:'move',ids:[encoder],dx:move.dx,dy:0}]});
  const undo=core.reduceHistory(applied,{type:'undo'}),redo=core.reduceHistory(undo,{type:'redo'});
  const documentBinding=write(`${mode}-${move.name}.documents.json`,{mode,move,base,historyBefore:history,applied,undo,redo,historyInputUnchanged:JSON.stringify(history)===prior});
  documentRecords.push({mode,move,binding:documentBinding});
  for(const preset of ['paper','monochrome'])for(const widthMm of [85,180])for(const scope of ['whole','detail']){
   const document=structuredClone(applied.document);document.pageSpec={...document.pageSpec,preset,widthMm};
   const start=JSON.stringify(document),options=scope==='detail'?{nodeId:rootId,widthMm}:{widthMm};
   const scene=core.buildExportScene(document,options),repeat=core.buildExportScene(document,options),svg=core.renderSvg(scene);
   const stem=`${mode}-${move.name}-${preset}-${widthMm}-${scope}`,sceneBinding=write(`${stem}.scene.json`,scene);
   writeFileSync(path.join(out,`${stem}.svg`),svg);
   sceneRecords.push({stem,mode,move,preset,widthMm,scope,sceneBinding,svgBinding:{path:`${directory}/${stem}.svg`,bytes:Buffer.byteLength(svg),sha256:sha(svg)},documentBinding,
    documentUnchanged:JSON.stringify(document)===start,deterministic:JSON.stringify(scene)===JSON.stringify(repeat)});
  }
 }
}
write('capture.json',{schema:'archcanvas-horizontal-gap-output-capture/1',tag,suite,node:{executable:process.execPath,version:process.version},
 sourceInputUnchanged:JSON.stringify(source)===unchanged,sourceDocumentId:source.id,sourceRevision:source.revision,documentRecords,sceneRecords,
 scope:suite==='port-gap'?'Encoder moves +34/+35/+36 close the original 35-world-unit projected-port gap to +1/0/-1.':'Encoder moves +41/+42/+43 close the original 42-world-unit front-card gap to +1/0/-1; the Repeat back plates extend seven units farther.',
 limits:'Nine detached inputs, 72 presentation scenes of the same Transformer. No source/runtime model execution or browser inputs.'});
console.log(JSON.stringify({tag,suite,documents:documentRecords.length,scenes:sceneRecords.length,sourceInputUnchanged:JSON.stringify(source)===unchanged}));
