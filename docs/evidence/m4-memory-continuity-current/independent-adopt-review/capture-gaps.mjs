import {readFileSync,writeFileSync,mkdirSync,existsSync,readdirSync} from 'node:fs';
import {createHash} from 'node:crypto';import {fileURLToPath} from 'node:url';import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../../..');
const owner=path.join(root,'docs/evidence/m4-memory-continuity-current/independent-adopt-review'),out=path.join(owner,'gap-capture-attempt-1');
if(existsSync(out))throw new Error('Evidence must not be overwritten');
const bind=rel=>{const bytes=readFileSync(path.join(root,rel));return{path:rel,bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')}};
const sourceRel='docs/evidence/m4-caption-stability-current/independent-review/source-envelope.json';
const envelope=JSON.parse(readFileSync(path.join(root,sourceRel),'utf8')),frozen=envelope.document;
const coreCurrent=readdirSync(path.join(root,'studio/src/core')).filter(p=>p.endsWith('.ts')).sort().map(p=>`studio/src/core/${p}`);
const corePrior=readdirSync(path.join(root,'docs/evidence/m4-memory-continuity-current/before-change/inputs/studio/src/core')).filter(p=>p.endsWith('.ts')).sort().map(p=>`docs/evidence/m4-memory-continuity-current/before-change/inputs/studio/src/core/${p}`);
const inputBindings=[...coreCurrent,...corePrior,sourceRel,'docs/evidence/m4-memory-continuity-current/independent-adopt-review/capture-gaps.mjs'].map(bind);
const {buildExportScene,applyVisualBatch}=await import(path.join(root,'studio/src/core/index.ts'));
const {buildExportScene:beforeScene}=await import(path.join(root,'docs/evidence/m4-memory-continuity-current/before-change/inputs/studio/src/core/exportScene.ts'));
const savedBytes=JSON.stringify(frozen),rows=[];
mkdirSync(out);writeFileSync(path.join(out,'source-envelope.json'),readFileSync(path.join(root,sourceRel)));
const save=(name,value)=>{const p=path.join(out,name);writeFileSync(p,JSON.stringify(value,null,2)+'\n');return bind(path.relative(root,p))};
const moves=[22.99,23,23.01,34.99,35,35.01,41.99,42,42.01];
for(const dx of moves)for(const preset of ['paper','monochrome']){
 const id='repeat:instance:model.Transformer.encoder',dy=15;
 const document=applyVisualBatch(frozen,[{type:'move',ids:[id],dx,dy},{type:'page',page:{preset,widthMm:180}}]);
 for(const e of document.architecture.edges.filter(e=>e.role==='memory'))delete e.label;
 const expected=structuredClone(frozen.architecture);for(const e of expected.edges.filter(e=>e.role==='memory'))delete e.label;
 const architectureExact=JSON.stringify(document.architecture)===JSON.stringify(expected),stem=`source-dx${String(dx).replace('.','p')}-dy15-${preset}-180`,bytes=JSON.stringify(document);
 const documentBinding=save(`${stem}.document.json`,document);
 const movementExpected={...frozen.layout[id],x:frozen.layout[id].x+dx,y:frozen.layout[id].y+dy};
 const movedOnlyExpectedNode=JSON.stringify(document.layout[id])===JSON.stringify(movementExpected)&&Object.keys(frozen.layout).filter(n=>n!==id).every(n=>JSON.stringify(document.layout[n])===JSON.stringify(frozen.layout[n]));
 for(const scope of ['whole','detail']){
  const options=scope==='whole'?{widthMm:180}:{nodeId:document.expandedIds[0],widthMm:180};const old=beforeScene(document,options),current=buildExportScene(document,options);
  rows.push({key:`${stem}-${scope}`,originalKey:'Transformer source-envelope',caption:'default',endpoint:'source',dx,dy,preset,widthMm:180,scope,options,
   originalInput:bind(sourceRel),documentBinding,beforeBinding:save(`${stem}-${scope}.before.json`,old),currentBinding:save(`${stem}-${scope}.current.json`,current),
   inputUnchanged:JSON.stringify(document)===bytes,detachedDeterministic:JSON.stringify(buildExportScene(structuredClone(document),options))===JSON.stringify(current),architectureExact,movedOnlyExpectedNode,
   currentMemoryPath:current.edges.find(e=>e.id==='edge:44').path,priorMemoryPath:old.edges.find(e=>e.id==='edge:44').path});
 }
}
const inputAfter=inputBindings.map(b=>bind(b.path)),exact=inputAfter.every((r,i)=>JSON.stringify(r)===JSON.stringify(inputBindings[i]));
save('capture.json',{schema:'archcanvas-independent-real-repeat-gap-memory-capture/1',createdUtc:new Date().toISOString(),inputBindings,inputAfter,inputsUnchanged:exact,baseDocumentUnchanged:JSON.stringify(frozen)===savedBytes,rows,
 scope:'36 actual source-backed Transformer Encoder15dy+9dx gap-boundary typedmove cases×paper/mono×whole/rootdetail,180mm defaultcaption. Current versus immediate-before formalcore. No model/browser/product/gold mutation.'});
if(!exact)throw new Error('Input changed during capture');console.log(JSON.stringify({cases:rows.length,inputs:inputBindings.length,inputsUnchanged:exact,baseDocumentUnchanged:JSON.stringify(frozen)===savedBytes,
 architectureExact:rows.filter(r=>r.architectureExact).length,movedOnlyExpectedNode:rows.filter(r=>r.movedOnlyExpectedNode).length,changedMemoryPaths:rows.filter(r=>r.currentMemoryPath!==r.priorMemoryPath).length}));
