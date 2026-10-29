import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
const base=new URL('../public/preview/yworks_edge_router_lab/',import.meta.url);
const app=readFileSync(new URL('app.js',base),'utf8');
function named(source:string,name:string){
 const ast=ts.createSourceFile('app.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);let fn:ts.FunctionDeclaration|undefined;
 function visit(n:ts.Node){if(ts.isFunctionDeclaration(n)&&n.name?.text===name)fn=n;ts.forEachChild(n,visit);}visit(ast);assert.ok(fn,name);
 return ts.transpile(fn.getText(ast),{target:ts.ScriptTarget.ES2022});
}
test('busy notifications avoid full host snapshots; explicit reads, idle state and origin validation keep their contract',async()=>{
 let listener:any,busy=false,dragging=false,cancellable=false,builds=0;const messages:any[]=[],parent={postMessage:(v:any)=>messages.push(structuredClone(v))};
 const root:any={parent,location:{origin:'http://localhost:8790',search:''},addEventListener(_:string,fn:any){listener=fn;}};
 const c=vm.createContext({window:root,document:{},URLSearchParams});vm.runInContext(readFileSync(new URL('studio-bridge.js',base),'utf8'),c);
 const link=root.ArchCanvasPreviewBridge.create({started:async()=>{},isBusy:()=>busy,interaction:()=>({caseId:'model',busy,dragging,canCancel:cancellable}),state:()=>{builds++;return {document:{graph:{nodes:[{id:'a',x:1}],source:'complete'}}};}});
 link.ready();assert.equal(builds,1);messages.length=0;busy=true;dragging=true;link.state();dragging=false;cancellable=true;link.state();
 assert.equal(builds,1);assert.deepEqual(messages.map(v=>v.type),['archcanvas:preview:interaction','archcanvas:preview:interaction']);assert.ok(messages.every(v=>!('document' in v)&&!('graph' in v)));assert.equal(messages[1].canCancel,true);
 const send=(origin:string)=>listener({source:parent,origin,data:{type:'archcanvas:preview:snapshot',requestId:'read'}});
 send(root.location.origin);for(let i=0;i<6;i++)await Promise.resolve();assert.equal(builds,2);assert.equal(messages.at(-1).document.graph.source,'complete');
 send('https://foreign.invalid');for(let i=0;i<6;i++)await Promise.resolve();assert.equal(builds,2);
 busy=false;link.interaction();assert.equal(builds,2);link.state();assert.equal(builds,3);assert.equal(messages.at(-1).type,'archcanvas:preview:state');
});
test('actual pointer capture and selection feedback avoid scene, inspector and source traversal',()=>{
 let captures=0,status=0,handles=0;const attrs:any={};
 const c=vm.createContext({performance,busy:false,drag:null,svg:{classList:{toggle(){}},setPointerCapture(){captures++;},setAttribute(k:string,v:string){attrs[k]=v;}},point:()=>({x:1,y:2}),studioBridge:{state(){status++;}},graph:{get nodes(){throw Error('full graph traversal before feedback');}},refreshHandles(){handles++;},stageScale:()=>1});
 vm.runInContext(named(app,'begin')+named(app,'render'),c);c.begin({button:0,pointerId:7,stopPropagation(){},preventDefault(){}},{kind:'node',node:{id:'a'}});c.render({presentationOnly:true});
 assert.equal(captures,1);assert.equal(status,1);assert.equal(handles,1);assert.equal(c.drag.saved,false);assert.ok(Number(attrs['data-render-ms'])>=0);
});
test('expired autosave cannot serialize a live preview or a pending routing transaction',()=>{
 let workspaces=0,cleared=0,deferred=0;const c=vm.createContext({clearTimeout(){cleared++;},persist(){deferred++;},persistTimer:1,graph:{nodes:[]},current:{id:'case'},busy:false,drag:{kind:'node'},persistWorkspace(){workspaces++;throw Error('workspace serialized during gesture');}});
 vm.runInContext(named(app,'flushPersist'),c);c.flushPersist();assert.equal(workspaces,0);assert.equal(c.persistTimer,0);c.drag=null;c.busy=true;c.flushPersist();assert.equal(workspaces,0);assert.equal(cleared,2);assert.equal(deferred,2);
});
test('host status keeps committed graph, source and selection intact; cancellation stays live and foreign case status is ignored',()=>{
 const source=readFileSync(new URL('../src/App.tsx',import.meta.url),'utf8'),graph={nodes:[{id:'a',x:1}]},snapshot:any={caseId:'model',graph,semanticView:{canonical:true},selectedNodes:['a']},states:any[]=[],cancel:any[]=[];
 const c=vm.createContext({previewSnapshot:{current:snapshot},setPreviewBusy:(v:any)=>states.push(v),setPreviewCanCancel:(v:any)=>cancel.push(v)});vm.runInContext(named(source,'receivePreviewInteraction'),c);
 c.receivePreviewInteraction({caseId:'other',busy:true});assert.equal(states.length,0);
 c.receivePreviewInteraction({caseId:'model',busy:true,dragging:true,canCancel:false,graph:{nodes:[]},selectedNodes:['forged']});assert.equal(snapshot.graph,graph);assert.deepEqual(snapshot.selectedNodes,['a']);assert.deepEqual(snapshot.semanticView,{canonical:true});assert.equal(snapshot.dragging,true);
 c.receivePreviewInteraction({caseId:'model',busy:true,dragging:false,canCancel:true});assert.equal(snapshot.canCancel,true);assert.equal(snapshot.dragging,false);assert.deepEqual(cancel,[false,true]);
});
test('dragging hides stale source controls without inspecting the graph, then restores the validated layer',()=>{
 const attrs=new Map<string,string>([['data-source-control-signature','valid|#8a6a46']]),layer={setAttribute:(k:string,v:string)=>attrs.set(k,v),removeAttribute:(k:string)=>attrs.delete(k),getAttribute:(k:string)=>attrs.get(k)};
 const c=vm.createContext({ensure:()=>({signature:'valid',controls:[],decisions:[],diagnostics:[]})});vm.runInContext(named(readFileSync(new URL('source-controls.js',base),'utf8'),'render'),c);
 c.render(new Proxy({},{get(){throw Error('source serialization on pointer movement');}}),{querySelector:()=>layer},{interactive:true});assert.equal(attrs.get('display'),'none');c.render({}, {querySelector:()=>layer});assert.equal(attrs.has('display'),false);
});

test('host binding reuse avoids source walks for status-only updates and invalidates on graph, source and architecture generations',()=>{
 const source=readFileSync(new URL('../src/App.tsx',import.meta.url),'utf8'),architecture={},evidence={},graph={},bindings=new Map([['canonical','formal']]);let signatures=0,rebuilds=0;
 const c=vm.createContext({historyRef:{current:{document:{architecture}}},previewSnapshot:{current:{graph}},previewSource:{current:evidence},previewNodeBindings:{current:{architecture,source:evidence,graph,signature:'same',bindings}},previewMappingSignature:()=>{signatures++;return 'same';},previewUniqueNodeBindings:()=>{rebuilds++;return new Map();}});
 vm.runInContext(named(source,'currentPreviewNodeBindings'),c);assert.equal(c.currentPreviewNodeBindings(),bindings);assert.equal(signatures,0);
 c.previewSnapshot.current.graph={};assert.equal(c.currentPreviewNodeBindings(),bindings);assert.equal(signatures,1);assert.equal(rebuilds,0);assert.equal(c.previewNodeBindings.current.graph,c.previewSnapshot.current.graph);
 c.currentPreviewNodeBindings();assert.equal(signatures,1);
 c.previewSource.current={};c.currentPreviewNodeBindings();assert.equal(rebuilds,1);
 c.historyRef.current.document.architecture={};c.currentPreviewNodeBindings();assert.equal(rebuilds,2);
});

test('first-feedback timing ignores pointer events that do not change the preview position',()=>{
 const ast=ts.createSourceFile('app.js',app,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);let listener:ts.Expression|undefined;
 function visit(n:ts.Node){if(ts.isCallExpression(n)&&n.expression.getText(ast)==='svg.addEventListener'&&n.arguments[0]?.getText(ast)==="'pointermove'")listener=n.arguments[1];ts.forEachChild(n,visit);}visit(ast);assert.ok(listener);
 let queued:any;const attrs=new Map<string,string>();const c=vm.createContext({drag:{kind:'node',last:{x:1,y:1}},dragFrame:0,dragPoint:null,performance:{now:()=>20},point:(e:any)=>e.p,requestAnimationFrame:(fn:any)=>{queued=fn;return 1;},svg:{setAttribute:(k:string,v:string)=>attrs.set(k,v)}});
 c.processDragPoint=(p:any)=>{if(p.x!==c.drag.last.x||p.y!==c.drag.last.y)c.drag.last=p;};vm.runInContext('globalThis.move='+listener.getText(ast),c);
 c.move({p:{x:1,y:1},timeStamp:10});queued();assert.equal(attrs.has('data-drag-first-input-to-dom-ms'),false);
 c.move({p:{x:2,y:1},timeStamp:11});queued();assert.equal(attrs.get('data-drag-first-input-to-dom-ms'),'9.00');assert.equal(attrs.get('data-drag-max-input-to-dom-ms'),'9.00');
 c.move({p:{x:3,y:1},timeStamp:12});queued();assert.equal(attrs.get('data-drag-first-input-to-dom-ms'),'9.00');assert.equal(attrs.get('data-drag-input-to-dom-ms'),'8.00');
});
