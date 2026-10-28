import test from 'node:test';
import assert from 'node:assert/strict';
import { rememberPreviewSave, matchesPreviewSave } from '../src/previewSaveState.ts';
const document={id:'fixture',sourceBindingDigest:'source',architecture:{irDigest:'ir'}};
const graph={nodes:[{id:'a',x:170,y:200}],edges:[],sourceDraftOperations:[]};
function store(){const values=new Map<string,string>();return{getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value);}};}
test('saved preview marker survives reload while edits, alternate sources, and other documents remain dirty',async()=>{
  const storage=store();assert.equal(await matchesPreviewSave(storage,document,graph),false);
  await rememberPreviewSave(storage,document,graph);
  assert.equal(await matchesPreviewSave(storage,document,JSON.parse(JSON.stringify(graph))),true);
  for(const changed of [{...graph,nodes:[{id:'a',x:171,y:200}]},{...graph,sourceDraftOperations:[{kind:'remove-connection'}]},{...graph,edges:[{id:'new'}]}])assert.equal(await matchesPreviewSave(storage,document,changed),false);
  assert.equal(await matchesPreviewSave(storage,{...document,id:'other'},graph),false);
  assert.equal(await matchesPreviewSave(storage,{...document,sourceBindingDigest:'new'},graph),false);
  assert.equal(await matchesPreviewSave(storage,{...document,architecture:{irDigest:'new'}},graph),false);
});
test('unavailable or corrupt optional markers do not block saving or hide unsaved state',async()=>{
  const storage={getItem:()=>'{bad',setItem(){throw new Error('quota');}};
  await assert.doesNotReject(rememberPreviewSave(storage,document,graph));assert.equal(await matchesPreviewSave(storage,document,graph),false);
});
