import{readFileSync,writeFileSync}from'node:fs';import{buildScene,buildExportScene,renderSvg}from'../../../../studio/src/core/index.ts';
import{fileURLToPath}from'node:url';import path from'node:path';const here=path.dirname(fileURLToPath(import.meta.url));
for(const[identifier,label,nodeId]of[['ea42cd05c8a344348ed5751da24276ec','whole',undefined],['a0a6f9b4d5b74acfa9c9b032175c14ca','detail','call:instance:model.Transformer']]){
 const input=readFileSync(path.join(here,'exports',identifier,'document.json')),payload=JSON.parse(input),doc=payload.document??payload,before=JSON.stringify(doc);const scene=buildExportScene(doc,nodeId?{nodeId}:{});if(before!==JSON.stringify(doc))throw Error('capture mutated document');writeFileSync(path.join(here,label+'.scene.json'),JSON.stringify(scene,null,2)+'\n');writeFileSync(path.join(here,label+'.raw.svg'),renderSvg(scene));
}
const mono=JSON.parse(readFileSync(path.join(here,'exports/ea42cd05c8a344348ed5751da24276ec/document.json')));const doc=mono.document??mono;doc.pageSpec.preset='monochrome';const scene=buildScene(doc);writeFileSync(path.join(here,'monochrome-replay.scene.json'),JSON.stringify(scene,null,2)+'\n');
