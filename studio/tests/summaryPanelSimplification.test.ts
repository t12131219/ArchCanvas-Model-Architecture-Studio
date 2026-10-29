import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import ts from 'typescript';
import React from 'react';
import { parseSummaryCatalog, summaryPrograms, summaryConfiguration } from '../src/summaryCatalog.ts';

function component(file:string, states:Record<number,unknown>={}) {
 const source=readFileSync(new URL('../src/'+file,import.meta.url),'utf8');
 const exports:any={};let slot=0;
 const hooks={...React,useEffect(){},useState(initial:unknown){const i=slot++;return [i in states?states[i]:initial,()=>{}];},useRef:(value:unknown)=>({current:value})};
 const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React}}).outputText;
 new Function('require','exports','React',code)(()=>hooks,exports,React);return exports;
}
function elements(node:any):any[] {return !node||typeof node!=='object'?[]:[node,...React.Children.toArray(node.props?.children).flatMap(elements)];}
function text(node:any):string {return typeof node==='string'||typeof node==='number'?String(node):React.Children.toArray(node?.props?.children).map(text).join('');}
const modules=[{id:'root',label:'Model',parent:null,count:20,maxDepth:6},{id:'child',label:'Child',parent:'root',count:10,maxDepth:3}];
test('module panel buttons address the selected subtree and expose one collapsed set of presets',()=>{
 const {SummaryViewPanel,summaryModuleDepth}=component('SummaryViewPanel.tsx',{0:'child'}),commands:any[]=[],focused:any[]=[];
 const view={modules,moduleCuts:[{id:'child',level:'source',depth:1}]};
 const tree=SummaryViewPanel({snapshot:{semanticView:view,graph:{nodes:[],edges:[]}},disabled:false,onCommand:(v:any)=>commands.push(v),onFocus:(v:any)=>focused.push(v)}),all=elements(tree);
 for(const label of ['展开一层','收起一层','应用深度','全部展开','收起模块','架构概览','模块详图','恢复目标模块默认展开']){
  const button=all.find(e=>e.type==='button'&&text(e)===label);assert.ok(button,label);button.props.onClick();
  const request=commands.at(-1).moduleCut;assert.deepEqual(request.ids,['child']);assert.equal(request.replaceDescendants,true);
 }
 assert.equal(commands[0].moduleCut.depth,2);assert.equal(commands[1].moduleCut.depth,0);assert.equal(commands[3].moduleCut.depth,undefined);assert.equal(commands[4].moduleCut.depth,0);
 all.find(e=>e.type==='button'&&text(e)==='定位目标模块').props.onClick();assert.deepEqual(focused,['child']);
 const presets=all.find(e=>e.type==='details'&&e.props.className==='summary-expansion-presets');assert.equal(presets.props.open,undefined);
 assert.equal(all.filter(e=>e.type==='select').length,1,'no competing view dropdown');assert.doesNotMatch(text(tree),/F0|F1|CPU 精确源码|语义视图/);
 assert.equal(summaryModuleDepth(view,modules[1],[]),1);
 assert.equal(summaryModuleDepth({modules},modules[0],[{id:'root',expanded:true},{id:'child',parent:'root',expanded:true}]),2);
});
test('runtime evidence switches annotate the current graph without replacing module depths or opening another model',()=>{
 const {SummaryRuntimePanel}=component('SummaryRuntimePanel.tsx'),commands:any[]=[];
 const tree=SummaryRuntimePanel({available:false,hasSource:false,disabled:false,onRun(){throw Error('must not run');},onCommand:(v:any)=>commands.push(v),onSaveEvidence(){},snapshot:{semanticView:{mode:'source',runtimeEvidence:{runs:[{index:0,case:'sample',mode:'eval',status:'passed'}],selectedRun:0,integratedRegions:2}}}}),all=elements(tree);
 all.find(e=>e.props['aria-label']==='显示已匹配运行证据').props.onChange({target:{checked:true}});
 all.find(e=>e.props['aria-label']==='Summary 观察记录').props.onChange({target:{value:'0'}});
 assert.deepEqual(commands,[{patch:{mode:'merged',paperFocus:null,paperRelation:null}},{patch:{mode:'merged',runtimeInlineRun:0,paperFocus:null}}]);
 assert.equal(tree.props.open,undefined);assert.equal(all.some(e=>e.type==='textarea'),false);assert.doesNotMatch(text(tree),/CPU 精确源码|打开本次观察结果|证据视图/);
});
test('a new observation has a complete save path without replacing the active graph',()=>{
 const document={schema:'archcanvas-source-semantic/2',nodes:[],runtime:{runs:[{id:'specific-input'}]}};
 const {SummaryRuntimePanel}=component('SummaryRuntimePanel.tsx',{4:{document,receipt:{status:'passed'}}}),saved:any[]=[];
 const tree=SummaryRuntimePanel({available:false,hasSource:false,disabled:false,onSaveEvidence:(value:any)=>saved.push(value)});
 elements(tree).find(e=>e.type==='button'&&text(e)==='保存本次观察证据').props.onClick();assert.deepEqual(saved,[document]);assert.match(text(tree),/尚未附加到当前图/);
});
test('model entries group by source identity, retaining constructor variants and their own observation coverage',()=>{
 const catalog=parseSummaryCatalog(JSON.parse(readFileSync(new URL('../public/preview/data/semantic/studio-catalog.json',import.meta.url),'utf8')));
 const programs=summaryPrograms(catalog.models);assert.equal(catalog.models.length,43);assert.equal(programs.length,42);
 for(const model of catalog.models){
  const ir=JSON.parse(readFileSync(new URL('../public/preview/data/semantic/'+model.ir.path,import.meta.url),'utf8')),entry=ir.entry;
  const source=ir.sources.find((s:any)=>s.path===entry.file);
  if(!source){assert.equal(model.program,undefined);assert.ok(programs.some(p=>p.id===model.id));continue;}
  const expected=createHash('sha256').update(JSON.stringify([source.unit_sha256||source.sha256,entry.class,entry.cell??null])).digest('hex');
  assert.equal(model.program?.id,expected);assert.deepEqual(model.program?.constructor,entry.constructor??{});assert.equal(model.program?.observations,ir.runtime?.runs?.length??0);
 }
 const transformer=programs.find(p=>p.models.length===2)!;assert.equal(transformer.title,'Transformer');assert.notEqual(summaryConfiguration(transformer.models[0]),summaryConfiguration(transformer.models[1]));
 const [first]=catalog.models;assert.equal(summaryPrograms([first,{...first,id:'other',program:{...first.program!,id:'a'.repeat(64)}}]).length,2,'same title cannot merge different sources');
});
test('host retains object legend page editing panels and removes redundant Summary view shells',()=>{
 const app=readFileSync(new URL('../src/App.tsx',import.meta.url),'utf8');
 assert.doesNotMatch(app,/className="semantic-frontier"|className="summary-interaction"|onOpenPreview=|openSummaryObservation/);
 for(const name of ['对象','图例','页面','Summary'])assert.ok(app.includes(name));
 assert.ok(app.includes('<SummarySemanticPanel embedded'));assert.ok(app.includes('onSaveEvidence='));
 const library=readFileSync(new URL('../src/SummaryCatalogPanel.tsx',import.meta.url),'utf8');assert.doesNotMatch(library,/loadSummaryPreviewCases|summary-preview-cases/);
});
