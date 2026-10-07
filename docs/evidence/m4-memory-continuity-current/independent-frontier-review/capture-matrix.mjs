import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../../..');
const owner=path.join(root,'docs/evidence/m4-memory-continuity-current/independent-frontier-review');
const attempt=process.argv[2];if(!/^capture-attempt-[1-9][0-9]*$/.test(attempt??''))throw new Error('Append-only capture-attempt-N required');
const out=path.join(owner,attempt);if(existsSync(out))throw new Error('Evidence must not be overwritten');
const bind=rel=>{const bytes=readFileSync(path.join(root,rel));return{path:rel,bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')}};
const captureRel='docs/evidence/m4-collapsed-residual-work/acceptance/baseline/capture.json';
const originalCapture=JSON.parse(readFileSync(path.join(root,captureRel),'utf8'));
const coreCurrent=readdirSync(path.join(root,'studio/src/core')).filter(p=>p.endsWith('.ts')).sort().map(p=>`studio/src/core/${p}`);
const corePrior=readdirSync(path.join(root,'docs/evidence/m4-memory-continuity-current/before-change/inputs/studio/src/core')).filter(p=>p.endsWith('.ts')).sort().map(p=>`docs/evidence/m4-memory-continuity-current/before-change/inputs/studio/src/core/${p}`);
const inputBindings=[...coreCurrent,...corePrior,captureRel,'docs/evidence/m4-memory-continuity-current/independent-frontier-review/capture-matrix.mjs',
 ...originalCapture.records.flatMap(r=>[r.files['actual-canvas.json'].source.path,r.files['actual-canvas.json'].copy.path])].map(bind);
const sourceReadback=originalCapture.records.map(r=>({key:r.key,copyExpected:r.files['actual-canvas.json'].copy,copyActual:bind(r.files['actual-canvas.json'].copy.path),
 sourceExpected:r.files['actual-canvas.json'].source,sourceActual:bind(r.files['actual-canvas.json'].source.path)}));
for(const r of sourceReadback)for(const part of ['copy','source'])if(r[`${part}Expected`].bytes!==r[`${part}Actual`].bytes||r[`${part}Expected`].sha256!==r[`${part}Actual`].sha256)throw new Error(`Frozen original input changed: ${r.key} ${part}`);
const {buildExportScene}=await import(path.join(root,'studio/src/core/exportScene.ts'));
const {buildExportScene:beforeScene}=await import(path.join(root,'docs/evidence/m4-memory-continuity-current/before-change/inputs/studio/src/core/exportScene.ts'));
mkdirSync(out);const rows=[];
const save=(name,value)=>{const p=path.join(out,name);writeFileSync(p,JSON.stringify(value,null,2)+'\n');return bind(path.relative(root,p))};
for(const record of originalCapture.records){
 const frozen=JSON.parse(readFileSync(path.join(root,record.files['actual-canvas.json'].copy.path),'utf8'));
 for(const caption of ['default','empty','custom'])for(const preset of ['paper','monochrome'])for(const widthMm of [85,180]){
  const document=structuredClone(frozen);document.pageSpec={...document.pageSpec,preset,widthMm};
  for(const edge of document.architecture.edges.filter(e=>e.role==='memory')){if(caption==='default')delete edge.label;else edge.label=caption==='empty'?'':'独立 memory 说明'}
  const bytes=JSON.stringify(document),stem=`${record.fixture}-L${record.level}-${caption}-${preset}-${widthMm}`;
  const documentBinding=save(`${stem}.document.json`,document);
  for(const scope of ['whole','detail']){
   const options=scope==='whole'?{widthMm}:{nodeId:document.expandedIds[0],widthMm};
   const old=beforeScene(document,options),current=buildExportScene(document,options);
   rows.push({key:`${stem}-${scope}`,originalKey:record.key,caption,preset,widthMm,scope,options,
    originalInput:record.files['actual-canvas.json'].copy,documentBinding,
    beforeBinding:save(`${stem}-${scope}.before.json`,old),currentBinding:save(`${stem}-${scope}.current.json`,current),
    inputUnchanged:JSON.stringify(document)===bytes,detachedDeterministic:JSON.stringify(buildExportScene(structuredClone(document),options))===JSON.stringify(current)});
  }
 }
}
const inputAfter=inputBindings.map(b=>bind(b.path));
const exact=inputAfter.every((r,i)=>JSON.stringify(r)===JSON.stringify(inputBindings[i]));
save('capture.json',{schema:'archcanvas-independent-nine-frontier-memory-capture/1',createdUtc:new Date().toISOString(),sourceReadback,inputBindings,inputAfter,inputsUnchanged:exact,rows,
 scope:'Nine frozen source-backed actual CanvasDocuments regenerated using immediate-before and current formal core, 216 whole/detail presentation cases. No model execution, browser operations or product/gold/history mutation.'});
if(!exact)throw new Error('Input changed during capture; preserve attempt and recapture');
console.log(JSON.stringify({cases:rows.length,documents:originalCapture.records.length,inputs:inputBindings.length,inputsUnchanged:exact,unchangedDocuments:rows.filter(r=>r.inputUnchanged).length,deterministic:rows.filter(r=>r.detachedDeterministic).length}));
