import test from 'node:test';
import assert from 'node:assert/strict';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import {createDocument,applyVisualBatch,buildScene,createHistory,reduceHistory} from '../src/core/index.ts';
import type {Architecture,ArchitectureNode,CanvasDocument,SceneNode} from '../src/core/index.ts';
function parallel(): Architecture {
 const node=(id:string,parentId?:string,children:string[]=[],category='linear'):ArchitectureNode=>({id,label:id,kind:category,category,parentId,children,ports:[{id:'in',name:'input',direction:'in',role:'data',ordinal:0},{id:'out',name:'output',direction:'out',role:'data',ordinal:0}],parameters:{},evidence:'source'});
 return {schemaVersion:1,id:'architecture:parallel-oracle',label:'Two independent branches',entry:'test:Model',sourceDigest:'manual-source-facts',irDigest:'manual-ir-facts',sources:[],diagnostics:[],nodes:[node('root',undefined,['input','tall','short','output'],'container'),node('input','root',[],'input'),node('tall','root',['first','second'],'container'),node('first','tall'),node('second','tall'),node('short','root',['small'],'container'),node('small','short'),node('output','root',[],'output')],edges:[['input','first'],['first','second'],['input','small'],['second','output'],['small','output']].map(([s,t],i)=>({id:'edge'+i,source:{nodeId:s,portId:'out'},target:{nodeId:t,portId:'in'},tensorId:s+'-tensor',role:'data'}))};
}
const expand=(d:CanvasDocument,id:string,on=true)=>applyVisualBatch(d,[{type:'expand',id,expanded:on}]);
const at=(d:CanvasDocument,id:string)=>buildScene(d).nodes.find(n=>n.id===id)!;
const pos=(n:SceneNode)=>({x:n.x,y:n.y,width:n.width,height:n.height});
const overlap=(a:SceneNode,b:SceneNode)=>a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+b.height&&a.y+a.height>b.y;
const noSiblingOverlap=(d:CanvasDocument)=>{const s=buildScene(d);for(let i=0;i<s.nodes.length;i++)for(let j=i+1;j<s.nodes.length;j++)if(s.nodes[i].parentId===s.nodes[j].parentId)assert.equal(overlap(s.nodes[i],s.nodes[j]),false,`${s.nodes[i].id} overlaps ${s.nodes[j].id}`);};
const project=fileURLToPath(new URL('../../',import.meta.url));
async function model(fixture:string,entry:string):Promise<Architecture> {
 const code='import sys,json;from pathlib import Path;root=Path(sys.argv[1]);sys.path.insert(0,str(root/"src"));from archcanvas_python import analyze_project;print(json.dumps(analyze_project(root/"fixtures"/sys.argv[2],sys.argv[3])))';
 const {stdout}=await promisify(execFile)('python3',['-I','-S','-B','-c',code,project,fixture,entry],{encoding:'utf8',maxBuffer:2_000_000});
 return JSON.parse(stdout);
}
const actual=async()=>({architecture:await model('transformer','model:Transformer'),expandedIds:[
 'call:instance:model.Transformer','repeat:instance:model.Transformer.encoder','call:instance:model.Transformer.decoder',
 'call:instance:model.Transformer.encoder.0','call:instance:model.Transformer.encoder.1','call:instance:model.Transformer.decoder.feedforward',
]});

test('parallel growth fitting below an existing taller branch does not shift output again',()=>{
 let d=createDocument(parallel()); const tallAnchor=at(d,'tall');
 d=expand(d,'tall'); assert.equal(at(d,'tall').x,tallAnchor.x);assert.equal(at(d,'tall').y,tallAnchor.y);
 const output=pos(at(d,'output')),shortAnchor=at(d,'short');
 assert.equal(output.y-at(d,'tall').y-at(d,'tall').height,38);
 d=expand(d,'short'); assert.deepEqual(pos(at(d,'output')),output);
 assert.equal(at(d,'short').x,shortAnchor.x);assert.equal(at(d,'short').y,shortAnchor.y); noSiblingOverlap(d);
});

test('horizontal free space absorbs width growth; adjacent sibling spacing and authored gap are preserved',()=>{
 let d=createDocument(parallel());d=applyVisualBatch(d,[{type:'move',ids:['short'],dx:100,dy:0}]);
 const before=pos(at(d,'short'));d=expand(d,'tall');assert.deepEqual(pos(at(d,'short')),before);noSiblingOverlap(d);
 let tight=createDocument(parallel());const beforeGap=at(tight,'short').x-at(tight,'tall').x-at(tight,'tall').width;
 tight=expand(tight,'tall');assert.equal(at(tight,'short').x-at(tight,'tall').x-at(tight,'tall').width,beforeGap);noSiblingOverlap(tight);
});

test('manual distant output absorbs growth; downstream relative offsets and explicit user movement survive frontier restore',()=>{
 let d=createDocument(parallel()); d=applyVisualBatch(d,[{type:'move',ids:['output'],dx:0,dy:500}]);
 const before=pos(at(d,'output')); d=expand(d,'tall');d=expand(d,'short');assert.deepEqual(pos(at(d,'output')),before);
 const prior=structuredClone(d.layout.output);d=expand(d,'short',false);d=applyVisualBatch(d,[{type:'move',ids:['output'],dx:13,dy:17}]);d=expand(d,'short');
 assert.equal(d.layout.output.x,prior.x+13);assert.equal(d.layout.output.y,prior.y+17);noSiblingOverlap(d);
});

test('pinned output and pinned descendant protect anchors while the existing warning reports unresolved overlap',()=>{
 let d=createDocument(parallel());d=applyVisualBatch(d,[{type:'pin',ids:['output'],pinned:true}]); const output=pos(at(d,'output')),tall=pos(at(d,'tall'));
 d=expand(d,'tall');assert.deepEqual(pos(at(d,'output')),output);assert.equal(at(d,'tall').x,tall.x);assert.equal(at(d,'tall').y,tall.y);
 assert.ok(buildScene(d).diagnostics.some(x=>x.message.startsWith('Pinned object')));
 let descendant=expand(createDocument(parallel()),'short');descendant=applyVisualBatch(descendant,[{type:'pin',ids:['small'],pinned:true}]);const small=pos(at(descendant,'small'));
 descendant=expand(descendant,'tall');assert.deepEqual(pos(at(descendant,'small')),small);
});

test('exact collapse/reexpand frontier snapshots and undo/redo remain stable after repeated parallel expansion',()=>{
 let d=expand(expand(createDocument(parallel()),'tall'),'short'); const layout=structuredClone(d.layout),semantic=JSON.stringify(d.architecture);
 for(let i=0;i<3;i++){d=expand(d,'short',false);d=expand(d,'tall',false);d=expand(d,'tall');d=expand(d,'short');assert.deepEqual(d.layout,layout);}
 const h=createHistory(expand(d,'short',false)),applied=reduceHistory(h,{type:'apply',operations:[{type:'expand',id:'short',expanded:true}]});
 assert.equal(applied.past.length,1);assert.deepEqual(applied.document.layout,layout);
 const undone=reduceHistory(applied,{type:'undo'}),redone=reduceHistory(undone,{type:'redo'});assert.deepEqual(undone.document.layout,h.document.layout);assert.deepEqual(redone.document.layout,layout);assert.equal(JSON.stringify(redone.document.architecture),semantic);
});

test('real Transformer depth-two UI frontier uses existing space without cumulative independent branch height',async()=>{
 const source=await actual();let d=createDocument(source.architecture);const operations=source.expandedIds.slice(1);
 for(const id of operations){const anchor=pos(at(d,id));d=expand(d,id);assert.equal(at(d,id).x,anchor.x);assert.equal(at(d,id).y,anchor.y);noSiblingOverlap(d);}
 const encoder=at(d,'repeat:instance:model.Transformer.encoder'),decoder=at(d,'call:instance:model.Transformer.decoder'),projection=at(d,'call:instance:model.Transformer.output_projection');
 assert.equal(projection.y-Math.max(encoder.y+encoder.height,decoder.y+decoder.height),38);
 assert.equal(projection.localY,1994);assert.equal(buildScene(d).bounds.height,2382);
 assert.deepEqual(d.architecture,source.architecture);
});

test('real Transformer depth-three and cached frontiers retain manual feedforward positions and no sibling intersections',async()=>{
 const source=await actual();let d=createDocument(source.architecture);for(const id of source.expandedIds.slice(1))d=expand(d,id);
 for(const id of ['call:instance:model.Transformer.encoder.0.feedforward','call:instance:model.Transformer.encoder.1.feedforward']){d=expand(d,id);noSiblingOverlap(d);}
 const projection=at(d,'call:instance:model.Transformer.output_projection'),encoder=at(d,'repeat:instance:model.Transformer.encoder');
 assert.equal(projection.y-encoder.y-encoder.height,38);
 const id='call:instance:model.Transformer.encoder.0.feedforward.activation';d=applyVisualBatch(d,[{type:'move',ids:[id],dx:5,dy:7}]);const manual=structuredClone(d.layout[id]);
 d=expand(d,'call:instance:model.Transformer.encoder.0.feedforward',false);d=expand(d,'call:instance:model.Transformer.encoder.0.feedforward');assert.deepEqual(d.layout[id],manual);
});

test('real Residual CNN grows both repeats and keeps downstream pool/flatten/classifier clear',async()=>{
 const a=await model('residual_cnn','model:ResidualCNN');
 let d=createDocument(a); for(const node of a.nodes.filter(n=>n.children.length&&n.parentId)){d=expand(d,node.id);noSiblingOverlap(d);}
 const repeat=at(d,'repeat:instance:model.ResidualCNN.blocks'),pool=at(d,'call:instance:model.ResidualCNN.pool');
 assert.equal(pool.y-repeat.y-repeat.height,38);
 const layout=structuredClone(d.layout);for(const node of [...a.nodes].reverse().filter(n=>n.children.length&&n.parentId))d=expand(d,node.id,false);
 for(const node of a.nodes.filter(n=>n.children.length&&n.parentId))d=expand(d,node.id);assert.deepEqual(d.layout,layout);noSiblingOverlap(d);
});
