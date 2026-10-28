import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
import {rememberPreviewSave,matchesPreviewSave} from '../src/previewSaveState.ts';

const app=readFileSync(new URL('../src/App.tsx',import.meta.url),'utf8');
const ast=ts.createSourceFile('App.tsx',app,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
let fallback:ts.ArrowFunction|undefined;
function find(node:ts.Node){
 if(ts.isArrowFunction(node)&&node.body.getText(ast).includes('if (!active.previewCaseId) throw error;')&&node.body.getText(ast).startsWith('{\n            if (!active.previewCaseId)'))fallback=node;
 ts.forEachChild(node,find);
}
find(ast);assert.ok(fallback,'actual missing-document recovery callback');
const code=ts.transpile('globalThis.recover='+fallback.getText(ast),{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None});
const document={id:'preview-fixture',revision:0,sourceBindingDigest:'preview-only:case',architecture:{irDigest:'source'}};
const snapshot={caseId:'case',dirty:true,graph:{generic:{ir:{id:'source'}},nodes:[{id:'a',x:10}]}};

async function run(saved:boolean,changeWhileChecking=false,projectWhileChecking=false){
 const values=new Map<string,string>(),store={getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value);}};
 if(saved)await rememberPreviewSave(store,document,snapshot.graph);
 const state={previewDirty:true,savedRevision:-1,notice:'',received:false};
 const environment:any={active:{previewCaseId:'case'},previewEngine:{current:{snapshot:async()=>snapshot}},alive:true,sequence:1,loadSequence:{current:1},initialModelLoading:{current:true},previewCase:{current:'old'},previewSnapshot:{current:null},historyRef:{current:null},savedPreviewGraph:{current:null},localStorage:store,
  receivePreviewState:async(value:any)=>{state.received=true;environment.loadSequence.current++;environment.previewSnapshot.current=value;environment.historyRef.current={document};},
  matchesPreviewSave:async(...args:Parameters<typeof matchesPreviewSave>)=>{const result=await matchesPreviewSave(...args);if(projectWhileChecking)environment.historyRef.current={document:{...document,revision:1}};if(changeWhileChecking){environment.loadSequence.current++;environment.historyRef.current={document:{...document,id:'new-model'}};environment.previewSnapshot.current={caseId:'new-model'};}return result;},
  setPreviewDirty:(value:boolean)=>{state.previewDirty=value;},setSavedVisualRevision:(value:number)=>{state.savedRevision=value;},setNotice:(value:string)=>{state.notice=value;}};
 const context=vm.createContext(environment);vm.runInContext(code,context);await context.recover(Error('formal document absent'));
 return {state,environment};
}

test('actual browser-only recovery reads the saved marker after adopting its preview document and restores the saved UI state',async()=>{
 const {state,environment}=await run(true);assert.equal(state.received,true);assert.equal(state.previewDirty,false);assert.equal(state.savedRevision,0);
 assert.equal(environment.savedPreviewGraph.current,JSON.stringify(snapshot.graph));assert.match(state.notice,/浏览器重开/);
});

test('browser-only recovery keeps an unmarked graph dirty and cannot mark another model saved after asynchronous identity changes',async()=>{
 const unmarked=await run(false);assert.equal(unmarked.state.previewDirty,true);assert.equal(unmarked.state.savedRevision,-1);assert.equal(unmarked.environment.savedPreviewGraph.current,null);
 const raced=await run(true,true);assert.equal(raced.state.previewDirty,true);assert.equal(raced.state.savedRevision,-1);assert.equal(raced.environment.savedPreviewGraph.current,null);assert.equal(raced.state.notice,'');
});


test('same-case panel projection during saved-marker hashing keeps the verified native graph saved at the latest mirror revision',async()=>{
 const {state,environment}=await run(true,false,true);assert.equal(state.previewDirty,false);assert.equal(state.savedRevision,1);assert.equal(environment.savedPreviewGraph.current,JSON.stringify(snapshot.graph));
});
