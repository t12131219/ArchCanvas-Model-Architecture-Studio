import {readFileSync,writeFileSync,mkdirSync,existsSync,readdirSync} from 'node:fs';
import {createHash} from 'node:crypto';import {fileURLToPath} from 'node:url';import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../../..'),stage='docs/evidence/m4-memory-continuity-current';
const owner=path.join(root,stage,'independent-browser-export-review'),out=path.join(owner,'expectations-attempt-1');
if(existsSync(out))throw new Error('Do not overwrite evidence');
const bind=rel=>{const b=readFileSync(path.join(root,rel));return{path:rel,bytes:b.length,sha256:createHash('sha256').update(b).digest('hex')}};
const core=readdirSync(path.join(root,'studio/src/core')).filter(p=>p.endsWith('.ts')).sort().map(p=>`studio/src/core/${p}`);
const browserFiles=readdirSync(path.join(root,stage,'browser')).sort().map(p=>`${stage}/browser/${p}`);
const exports=readdirSync(path.join(root,stage,'actual-export-work')).flatMap(p=>p.endsWith('.json')?[`${stage}/actual-export-work/${p}`]:readdirSync(path.join(root,stage,'actual-export-work',p)).sort().map(f=>`${stage}/actual-export-work/${p}/${f}`));
const inputBindings=[...core,...browserFiles,...exports,'scripts/export_canvas.mjs','src/archcanvas_publication/exporter.py',`${stage}/independent-browser-export-review/capture-expectations.mjs`].map(bind);
const saved=JSON.parse(readFileSync(path.join(root,stage,'actual-export-work/saved-rev47-envelope.json'),'utf8'));
const {buildScene,buildExportScene,renderSvg,applyVisualBatch,publicationPreflight}=await import(path.join(root,'studio/src/core/index.ts'));
mkdirSync(out);const save=(name,value)=>{const p=path.join(out,name);writeFileSync(p,typeof value==='string'?value:JSON.stringify(value,null,2)+'\n');return bind(path.relative(root,p))};
const rows=[];
for(const p of browserFiles.filter(p=>p.endsWith('.json')&&!p.includes('/15-'))){
 const captured=JSON.parse(readFileSync(path.join(root,p),'utf8')),num=Number(path.basename(p).slice(0,2));
 const revisions={1:39,2:40,3:41,4:42,5:43,6:44,7:45,8:46,9:47,10:47,11:47,12:47,13:47,14:47,16:47};
 const displacement={2:[0,16],4:[0,-16],6:[-24,0],8:[24,0]}[num]??[0,0];
 let document=structuredClone(saved.document);document.revision=displacement.some(v=>v!==0)?revisions[num]-1:revisions[num];
 if(displacement.some(v=>v!==0))document=applyVisualBatch(document,[{type:'move',ids:['repeat:instance:model.Transformer.encoder'],dx:displacement[0],dy:displacement[1]}]);
 const current=buildScene(document),stem=path.basename(p,'.json');
 rows.push({number:num,browserBinding:bind(p),expectedRevision:revisions[num],displacement,documentBinding:save(`${stem}.document.json`,document),
  sceneBinding:save(`${stem}.scene.json`,current),interactiveSvgBinding:save(`${stem}.interactive.svg`,renderSvg(current,{interactive:true}))});
}
const publication=buildExportScene(saved.document,{widthMm:180});
const publicationSceneBinding=save('saved47.publication.scene.json',publication),publicationSvgBinding=save('saved47.publication.svg',renderSvg(publication));
const preflight=publicationPreflight(publication);
const inputAfter=inputBindings.map(b=>bind(b.path)),exact=inputAfter.every((b,i)=>JSON.stringify(b)===JSON.stringify(inputBindings[i]));
save('capture.json',{schema:'archcanvas-independent-browser-export-expectations/1',createdUtc:new Date().toISOString(),inputBindings,inputAfter,inputsUnchanged:exact,rows,
 publicationSceneBinding,publicationSvgBinding,preflight,storageRevision:saved.revision,canvasRevision:saved.document.revision,
 scope:'Current-core expectations reconstructed from actual saved47document plus recorded literal four moves/revision identities. Full interactive/publicationSVG rendered to new review files only; actual browser/export evidence preserved, no model/source/browser mutation. Intermediate whole-document bytes are not captured by browser DOM.'});
if(!exact)throw new Error('Inputs changed while generating expectations');console.log(JSON.stringify({browserScenes:rows.length,inputs:inputBindings.length,inputsUnchanged:exact,canvasRevision:saved.document.revision,storageRevision:saved.revision,publicationSvgSha:publicationSvgBinding.sha256}));
