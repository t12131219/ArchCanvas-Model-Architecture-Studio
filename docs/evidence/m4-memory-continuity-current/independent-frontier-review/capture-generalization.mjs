import {readFileSync,writeFileSync,mkdirSync,existsSync,readdirSync} from 'node:fs';
import {createHash} from 'node:crypto';import {fileURLToPath} from 'node:url';import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../../..');
const owner=path.join(root,'docs/evidence/m4-memory-continuity-current/independent-frontier-review'),out=path.join(owner,'generalization-capture-attempt-1');
if(existsSync(out))throw new Error('Do not overwrite evidence');
const bind=rel=>{const bytes=readFileSync(path.join(root,rel));return{path:rel,bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')}};
const models=['GraphForecast','SkipSegmentation','TemporalForecaster'];
const reportRel='docs/evidence/source-facts/report.json',sourceReport=JSON.parse(readFileSync(path.join(root,reportRel),'utf8'));
const coreCurrent=readdirSync(path.join(root,'studio/src/core')).filter(p=>p.endsWith('.ts')).sort().map(p=>`studio/src/core/${p}`);
const corePrior=readdirSync(path.join(root,'docs/evidence/m4-memory-continuity-current/before-change/inputs/studio/src/core')).filter(p=>p.endsWith('.ts')).sort().map(p=>`docs/evidence/m4-memory-continuity-current/before-change/inputs/studio/src/core/${p}`);
const inputBindings=[...coreCurrent,...corePrior,reportRel,'docs/evidence/m4-memory-continuity-current/independent-frontier-review/capture-generalization.mjs',...models.flatMap(m=>['canvas.json','architecture.json','saved-envelope.json'].map(f=>`docs/evidence/source-facts/${m}/${f}`))].map(bind);
const {buildExportScene}=await import(path.join(root,'studio/src/core/exportScene.ts'));
const {buildExportScene:beforeScene}=await import(path.join(root,'docs/evidence/m4-memory-continuity-current/before-change/inputs/studio/src/core/exportScene.ts'));
mkdirSync(out);const rows=[],originalSourceChecks=[];
const save=(name,value)=>{const p=path.join(out,name);writeFileSync(p,JSON.stringify(value,null,2)+'\n');return bind(path.relative(root,p))};
for(const model of models){
 const canvasRel=`docs/evidence/source-facts/${model}/canvas.json`,frozen=JSON.parse(readFileSync(path.join(root,canvasRel),'utf8'));
 const architecture=JSON.parse(readFileSync(path.join(root,`docs/evidence/source-facts/${model}/architecture.json`),'utf8'));
 const envelope=JSON.parse(readFileSync(path.join(root,`docs/evidence/source-facts/${model}/saved-envelope.json`),'utf8'));
 const report=sourceReport.checks.find(r=>r.entry===`model:${model}`);
 originalSourceChecks.push({model,canvasArchitectureExact:JSON.stringify(frozen.architecture)===JSON.stringify(architecture),savedDocumentExact:JSON.stringify(envelope.document)===JSON.stringify(frozen),
  sourceDigestExact:frozen.architecture.sourceDigest===report.sourceDigest,irDigestExact:frozen.architecture.irDigest===report.irDigest,documentIdExact:frozen.id===report.documentId,revisionExact:frozen.revision===report.visualRevision});
 for(const preset of ['paper','monochrome'])for(const widthMm of [85,180]){
  const document=structuredClone(frozen);document.pageSpec={...document.pageSpec,preset,widthMm};
  for(const edge of document.architecture.edges.filter(e=>e.role==='memory'))delete edge.label;
  const bytes=JSON.stringify(document),stem=`${model}-default-${preset}-${widthMm}`,documentBinding=save(`${stem}.document.json`,document);
  for(const scope of ['whole','detail']){
   const options=scope==='whole'?{widthMm}:{nodeId:document.expandedIds[0],widthMm};const old=beforeScene(document,options),current=buildExportScene(document,options);
   rows.push({key:`${stem}-${scope}`,originalKey:model,caption:'default',preset,widthMm,scope,options,originalInput:bind(canvasRel),documentBinding,
    beforeBinding:save(`${stem}-${scope}.before.json`,old),currentBinding:save(`${stem}-${scope}.current.json`,current),inputUnchanged:JSON.stringify(document)===bytes,
    detachedDeterministic:JSON.stringify(buildExportScene(structuredClone(document),options))===JSON.stringify(current)});
  }
 }
}
const inputAfter=inputBindings.map(b=>bind(b.path)),exact=inputAfter.every((r,i)=>JSON.stringify(r)===JSON.stringify(inputBindings[i]));
save('capture.json',{schema:'archcanvas-independent-opaque-shared-generalization-memory-capture/1',createdUtc:new Date().toISOString(),inputBindings,inputAfter,inputsUnchanged:exact,rows,originalSourceChecks,
 scope:'24 whole/detail presentation cases over three historical static source-grounded documents, opaque/shared/repeat preservation against immediate-before/current formal core. No model execution, browser operations or product/gold mutation.'});
if(!exact)throw new Error('Input changed during capture');
console.log(JSON.stringify({cases:rows.length,models:models.length,inputs:inputBindings.length,inputsUnchanged:exact,originalSourceChecks}));
