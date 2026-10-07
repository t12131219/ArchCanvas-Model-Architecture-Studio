import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
const here=path.dirname(fileURLToPath(import.meta.url)),tag=process.argv[2];
if(!['before','label-only','after','after-peer-fix'].includes(tag))throw new Error('Select a frozen before/label-only/after/after-peer-fix core.');
const core=await import(pathToFileURL(path.join(here,`snapshots/${tag}/core/index.ts`)));
const placement=await import(pathToFileURL(path.join(here,`snapshots/${tag}/core/edgeLabelPlacement.ts`)));
const envelope=JSON.parse(readFileSync(path.join(here,'source-envelope.json'))),source=envelope.document;
const unchanged=JSON.stringify(source),rootId=source.expandedIds[0],encoder='repeat:instance:model.Transformer.encoder';
const moves=[{name:'baseline',dx:0,dy:0},...[-48,-24,-16,-15,-14,14,15,16,24,48].map(dy=>({name:`dy${dy}`,dx:0,dy})),...[-48,-24,24,48].map(dx=>({name:`dx${dx}`,dx,dy:0}))];
const out=path.join(here,tag);mkdirSync(out,{recursive:false});
const sha=x=>createHash('sha256').update(x).digest('hex');
const write=(name,x)=>{const raw=JSON.stringify(x,null,2)+'\n';writeFileSync(path.join(out,name),raw);return {path:`${tag}/${name}`,bytes:Buffer.byteLength(raw),sha256:sha(raw)};};
const documentRecords=[],sceneRecords=[];
for(const mode of ['default','empty','custom']){
 const base=structuredClone(source);
 if(mode!=='default')for(const edge of base.architecture.edges.filter(e=>e.role==='memory'))edge.label=mode==='empty'?'':'memory context';
 for(const move of moves){
  const history=core.createHistory(base),prior=JSON.stringify(history);
  const applied=core.reduceHistory(history,{type:'apply',operations:[{type:'move',ids:[encoder],dx:move.dx,dy:move.dy}]});
  const undo=core.reduceHistory(applied,{type:'undo'}),redo=core.reduceHistory(undo,{type:'redo'});
  const docName=`${mode}-${move.name}.documents.json`;
  const doc=write(docName,{mode,move,sourceRevision:source.revision,base,historyBefore:history,applied,undo,redo,historyInputUnchanged:JSON.stringify(history)===prior});
  documentRecords.push({mode,move,binding:doc});
  for(const preset of ['paper','monochrome'])for(const widthMm of [85,180])for(const scope of ['whole','detail']){
   const document=structuredClone(applied.document);document.pageSpec={...document.pageSpec,preset,widthMm};
   const start=JSON.stringify(document),options=scope==='detail'?{nodeId:rootId,widthMm}:{widthMm};
   const scene=core.buildExportScene(document,options),repeat=core.buildExportScene(document,options),svg=core.renderSvg(scene);
   const stem=`${mode}-${move.name}-${preset}-${widthMm}-${scope}`;
   const sceneBinding=write(`${stem}.scene.json`,scene);writeFileSync(path.join(out,`${stem}.svg`),svg);
   sceneRecords.push({stem,mode,move,preset,widthMm,scope,sceneBinding,svgBinding:{path:`${tag}/${stem}.svg`,bytes:Buffer.byteLength(svg),sha256:sha(svg)},
    inputDocumentBinding:doc,documentUnchanged:JSON.stringify(document)===start,deterministic:JSON.stringify(scene)===JSON.stringify(repeat)});
  }
 }
}
const edge={id:'synthetic-memory',path:'M 0 0 H 100',label:'memory',labelX:40,labelY:30,width:1.5,stroke:'#123456'};
const node=i=>({id:`distant${i}`,x:10000+i*20,y:10000,width:10,height:10,headerHeight:5,expanded:false});
const budgetCases=[
 {name:'nodes1025',nodes:Array.from({length:1025},(_,i)=>node(i)),edges:[edge],bodies:[]},
 {name:'routes513',nodes:[],edges:[edge,...Array.from({length:512},(_,i)=>({...edge,id:`route${i}`,label:'',path:`M 0 ${10000+i} H 100`}))],bodies:[]},
 {name:'labels129',nodes:[],edges:Array.from({length:129},(_,i)=>({...edge,id:`label${i}`})),bodies:[]},
 {name:'bodies1025',nodes:[],edges:[edge],bodies:Array.from({length:1025},(_,i)=>node(i))},
 {name:'characters262145',nodes:[],edges:[{...edge,path:edge.path+' '.repeat(262145)}],bodies:[]},
 {name:'points4097',nodes:[],edges:[{...edge,path:'M 0 0 '+'H 100 '.repeat(4097)}],bodies:[]},
 {name:'impossible-local',nodes:[{id:'cover',x:-200,y:-200,width:500,height:500,headerHeight:5,expanded:false}],edges:[edge],bodies:[]},
];
const budgetRecords=budgetCases.map(input=>{const before=JSON.stringify(input),value=placement.placeEdgeLabels(input.nodes,input.edges,input.bodies);return {input,unchanged:JSON.stringify(input)===before,placements:[...value.placements],diagnostics:value.diagnostics,guides:value.guides};});
write('budget-records.json',budgetRecords);
write('capture.json',{schema:'archcanvas-caption-stability-output-capture/1',tag,node:{executable:process.execPath,version:process.version},
 sourceInputUnchanged:JSON.stringify(source)===unchanged,sourceDocumentId:source.id,sourceRevision:source.revision,sourceDigest:source.sourceBindingDigest,
 documentRecords,sceneRecords,limits:['Detached copies and static facts only; no source/runtime model execution, native browser gestures, physical font or performance approval.',
 '45 label/move inputs x8 presentation scopes are360 scene cases of one source-backed Transformer; not360 models or users.']});
console.log(JSON.stringify({tag,documents:documentRecords.length,scenes:sceneRecords.length,budgetCases:budgetRecords.length,sourceInputUnchanged:JSON.stringify(source)===unchanged}));
