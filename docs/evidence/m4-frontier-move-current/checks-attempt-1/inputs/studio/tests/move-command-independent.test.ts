import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import type { PointerEvent } from 'react';
import { parseMoveCommand } from '../src/moveCommand.ts';
import { applyVisualBatch, buildScene, createDocument, createHistory, reduceHistory, renderSvg, ValidationError } from '../src/core/index.ts';
import type { Architecture, ArchitectureNode, CanvasDocument, HistoryState, MoveScope, VisualOperation } from '../src/core/types.ts';
import { prepareMovePreview, previewMoveScene } from '../src/core/movePreview.ts';
import { planLayoutRecovery } from '../src/core/layoutRecovery.ts';

const all: MoveScope = 'all-frontiers', local: MoveScope = 'current-frontier';
const compactKey = 'visible-frontier/1:["root"]';
const deepKey = 'visible-frontier/1:["network","root"]';

test('independent command directions use signed world distances and retain input selection', () => {
  const ids = ['output', 'input', 'output'];
  for (const [direction, dx, dy] of [['上',0,-24],['下',0,24],['左',-24,0],['右',24,0]] as const) {
    assert.deepEqual(parseMoveCommand(`向${direction}移动 24 画布单位`, ids),
      { status: 'ready', operation: { type: 'move', ids: ['output','input'], dx, dy, scope: all } });
  }
  assert.deepEqual(ids, ['output','input','output']);
});

test('decimal distances, bounded target wording, punctuation and whitespace have literal results', () => {
  for (const text of ['向右移动 12.25', ' 往右移12.25单位。 ', '将选中节点向右移动12.25！', '让所选对象，右移 12.25 画布单位']) {
    assert.deepEqual(parseMoveCommand(text, ['output'], local),
      { status: 'ready', operation: { type: 'move', ids: ['output'], dx:12.25, dy:0, scope:local } });
  }
  assert.deepEqual(parseMoveCommand('向右移动 4.', ['output'], local),
    { status:'ready',operation:{type:'move',ids:['output'],dx:4,dy:0,scope:local} });
});

test('explicit scope prefixes override either default and an omitted prefix uses the selected default', () => {
  for (const prefix of ['仅当前视图','只在当前视图','在当前视图','当前视图']) for (const fallback of [all,local]) {
    assert.deepEqual(parseMoveCommand(`${prefix}，向下移动 1.5`, ['output'], fallback),
      { status:'ready',operation:{type:'move',ids:['output'],dx:0,dy:1.5,scope:local} });
  }
  for (const prefix of ['所有视图','全部视图','在所有视图']) for (const fallback of [all,local]) {
    assert.deepEqual(parseMoveCommand(`${prefix} 向左移动 2.75`, ['output'], fallback),
      { status:'ready',operation:{type:'move',ids:['output'],dx:-2.75,dy:0,scope:all} });
  }
  assert.deepEqual(parseMoveCommand('向右移动 4', ['output'], local),
    {status:'ready',operation:{type:'move',ids:['output'],dx:4,dy:0,scope:local}});
});

test('empty selection, zero and nonfinite distances never emit a partial operation', () => {
  for (const [text, ids] of [['向右移动 4', []],['向右移动 0', ['output']],['向下移动 0.0', ['output']],
    [`向左移动 ${'9'.repeat(400)}`, ['output']]] as const) {
    const result=parseMoveCommand(text, ids);
    assert.equal(result.status, 'invalid');
    assert.equal('operation' in result, false);
  }
  assert.throws(() => parseMoveCommand('向右移动 4', ['output'], 'unknown' as never), ValidationError);
});

test('malformed attempted moves reject signed/exponent/partial/compound/CSS distances completely', () => {
  for (const text of ['向右移动 -4','向右移动 +4','向右移动 .5','向右移动 4.5.6','向右移动 4..','向右移动 1e3',
    '向右移动 NaN','向右移动 Infinity','向右移动 4px','向右移动 4 CSSpx','向右移动',
    '向右移动 4，然后向下移动 8','仅当前视图向下移动 16 并设为蓝色','向右移动4;向下移动8']) {
    const result=parseMoveCommand(text,['output']);
    assert.equal(result.status,'invalid',text);
    assert.equal('operation' in result,false,text);
  }
});

test('alias/color text and an empty command are not inferred as a movement', () => {
  for (const text of ['', '   ', '设为蓝色', '命名为“向右移动 24”', '将选中对象改名为向下移动 16',
    '显示名设为仅当前视图向左移动 8', '把“向右移动”作为标题', '展开这个对象']) {
    assert.deepEqual(parseMoveCommand(text,['output']),{status:'none'},text);
  }
});

function literalDocument(): CanvasDocument {
  const node=(id:string,parentId?:string,children:string[]=[]):ArchitectureNode => ({
    id,label:id,kind:children.length?'Module':'Linear',category:children.length?'container':'linear',
    ...(parentId?{parentId}:{}),children,ports:[],parameters:{},evidence:'source',
  });
  const architecture:Architecture={schemaVersion:1,id:'ui-move-scope-literal',label:'Literal',entry:'Model',
    sourceDigest:'literal-source',irDigest:'literal-ir',sources:[],diagnostics:[],edges:[],
    nodes:[node('root',undefined,['input','network','output']),node('input','root'),
      node('network','root',['leaf']),node('leaf','network'),node('output','root')]};
  const document=createDocument(architecture);
  document.expandedIds=['root','network'];
  document.layout={root:{x:50,y:92},input:{x:32,y:20},network:{x:32,y:80},leaf:{x:24,y:80},output:{x:36,y:30254}};
  document.layoutByFrontier={
    [compactKey]:{root:{x:900,y:800},input:{x:320,y:200},network:{x:16,y:64},output:{x:36,y:262}},
    [deepKey]:{root:{x:50,y:92},input:{x:32,y:20},network:{x:32,y:80},leaf:{x:24,y:80},output:{x:36,y:30254}},
  };
  return document;
}

type Pointer=PointerEvent<HTMLDivElement>;
type Gesture={type:'pan'|'move'|'box';pointerId:number;x:number;y:number;camera:{x:number;y:number;zoom:number};
  ids:string[];dx:number;dy:number;document?:CanvasDocument;preview?:ReturnType<typeof prepareMovePreview>;moveScope?:MoveScope;pan?:unknown};

// Execute the actual App callback AST, not duplicated callback logic or JSX regex.
// State setters, viewport/capture and rAF are controlled infrastructure. React is
// not mounted; this does not certify native effects, first paint or pixel output.
function appHarness(scope:MoveScope=all, ids:string[]=['output'], commandText='') {
  const source=readFileSync(new URL('../src/App.tsx',import.meta.url),'utf8');
  const ast=ts.createSourceFile('App.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
  const app=ast.statements.find(item=>ts.isFunctionDeclaration(item)&&item.name?.text==='App');
  assert.ok(app&&ts.isFunctionDeclaration(app)&&app.body);
  const names=['cancelGesture','chooseMoveScope','apply','panInput','pointerDown','pointerMove','pointerUp',
    'align','runCommand','previewPositionRecovery','applyPositionRecovery'];
  const snippets=names.map(name=>{
    const statement=app.body!.statements.find(item=>ts.isFunctionDeclaration(item)?item.name?.text===name:
      ts.isVariableStatement(item)&&item.declarationList.declarations.some(d=>ts.isIdentifier(d.name)&&d.name.text===name));
    assert.ok(statement,`Actual App callback ${name}`);return statement.getText(ast);
  });
  const historyRef={current:createHistory(literalDocument())};
  const current=historyRef.current.document,scene=buildScene(current);
  const gesture={current:null as Gesture|null},portGesture={current:null as {pointerId:number}|null},frame={current:0};
  const cameraRef={current:{x:10,y:20,zoom:.5}};
  const pending=new Map<number,FrameRequestCallback>(),captured=new Set<number>();
  const operations:VisualOperation[][]=[],notices:string[]=[],failures:string[]=[],commands:string[]=[],scopeChanges:MoveScope[]=[];
  const previewCalls:MoveScope[]=[],recoveryCalls:MoveScope[]=[],events:string[]=[];
  let nextFrame=0,preview:unknown=null,recovery:unknown=null;
  const element={getBoundingClientRect:()=>({left:20,top:40,width:640,height:600}),
    setPointerCapture:(id:number)=>{captured.add(id);events.push('capture');},hasPointerCapture:(id:number)=>captured.has(id),
    releasePointerCapture:(id:number)=>{captured.delete(id);events.push('release');}};
  const environment={historyRef,current,scene,cameraRef,gesture,portGesture,frame,viewportRef:{current:element},
    portRequest:{current:0},space:{current:false},tool:'select',busy:false,inputSpec:null,
    layoutMoveScope:scope,selection:{kind:'node',ids},command:commandText,activeRecovery:null,
    selectedNode:current.architecture.nodes.find(n=>n.id===ids[0]),selectedSceneNode:scene.nodes.find(n=>n.id===ids[0]),
    editingTarget:()=>false,claimGestureCamera:()=>{events.push('claim');},
    synchronizeCameraViewport:()=>{events.push('synchronize');},
    setPreview:(value:unknown)=>{preview=typeof value==='function'?(value as (p:unknown)=>unknown)(preview):value;},
    setRecoveryPreview:(value:unknown)=>{recovery=value;},setBox:()=>{},setPortDraft:()=>{},setIsPanning:()=>{},
    setSelection:()=>{},setPanel:()=>{},setFailure:(value:string)=>{failures.push(value);},setNotice:(value:string)=>{notices.push(value);},
    setCommand:(value:string)=>{commands.push(value);},setLayoutMoveScope:(value:MoveScope)=>{scopeChanges.push(value);},
    setHistory:(value:HistoryState)=>{assert.equal(value,historyRef.current);},
    useCallback:<T>(callback:T)=>callback,
    prepareMovePreview:(document:CanvasDocument,selection:readonly string[],value?:MoveScope)=>{
      previewCalls.push(value??all);return prepareMovePreview(document,selection,value);},
    planLayoutRecovery:(document:CanvasDocument,id:string,value?:MoveScope)=>{
      recoveryCalls.push(value??all);return planLayoutRecovery(document,id,value);},
    reduceHistory:(previous:HistoryState,action:Parameters<typeof reduceHistory>[1])=>{
      if(action.type==='apply')operations.push(action.operations);return reduceHistory(previous,action);},
    parseMoveCommand,studioTelemetry:{beginInteraction:()=>1,endInteraction:()=>{}},
    requestAnimationFrame:(callback:FrameRequestCallback)=>{const id=++nextFrame;pending.set(id,callback);return id;},
    cancelAnimationFrame:(id:number)=>{pending.delete(id);},
  };
  const compiled=ts.transpileModule(snippets.join('\n'),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText;
  const callbacks=new Function(...Object.keys(environment),`${compiled}\nreturn {${names.join(',')},
    replaceRenderScope(value) { layoutMoveScope=value; }, replaceActiveRecovery(value) { activeRecovery=value; }};`)(...Object.values(environment)) as {
    cancelGesture:()=>void;chooseMoveScope:(scope:MoveScope)=>void;apply:(ops:VisualOperation[])=>void;
    pointerDown:(event:Pointer)=>void;pointerMove:(event:Pointer)=>void;pointerUp:(event:Pointer)=>void;
    align:()=>void;runCommand:()=>void;previewPositionRecovery:()=>void;applyPositionRecovery:()=>void;
    replaceRenderScope:(value:MoveScope)=>void;replaceActiveRecovery:(value:unknown)=>void;
  };
  const event=(x:number,y:number,nodeId?:string,pointerId=7)=>({pointerId,clientX:x+20,clientY:y+40,button:0,shiftKey:false,
    currentTarget:element,preventDefault(){},target:{closest:(selector:string)=>selector==='[data-node-id]'&&nodeId?{getAttribute:()=>nodeId}:null}}) as unknown as Pointer;
  return {...callbacks,current,scene,historyRef,gesture,portGesture,frame,cameraRef,pending,captured,operations,
    notices,failures,commands,scopeChanges,previewCalls,recoveryCalls,events,event,
    getPreview:()=>preview as {session:ReturnType<typeof prepareMovePreview>;dx:number;dy:number}|null,
    getRecovery:()=>recovery as {document:CanvasDocument;plan:ReturnType<typeof planLayoutRecovery>}|null,
    runFrames:()=>{const work=[...pending];pending.clear();for(const [,callback] of work)callback(0);}};
}

test('actual App drag captures scope at down and commits that scope after a different render scope', () => {
  for(const scope of [all,local]) {
    const h=appHarness(scope),oldCompact=JSON.stringify(h.current.layoutByFrontier[compactKey]);
    h.pointerDown(h.event(100,100,'output'));
    assert.deepEqual(h.previewCalls,[scope]);
    assert.equal(h.gesture.current?.moveScope,scope);
    assert.equal(h.gesture.current?.preview?.scope,scope);
    h.replaceRenderScope(scope===all?local:all);
    h.pointerMove(h.event(112,104));h.runFrames();
    const value=h.getPreview();assert.ok(value);
    const preview=previewMoveScene(value.session,value.dx,value.dy);
    h.pointerUp(h.event(112,104));
    assert.deepEqual(h.operations,[[{type:'move',ids:['output'],dx:24,dy:8,scope}]]);
    assert.deepEqual(preview,buildScene(h.historyRef.current.document));
    assert.equal(renderSvg(preview,{interactive:true}),renderSvg(buildScene(h.historyRef.current.document),{interactive:true}));
    assert.equal(h.historyRef.current.past.length,1);
    assert.deepEqual(h.current.layout.output,{x:36,y:30254});
    assert.deepEqual(h.historyRef.current.document.layout.output,{x:60,y:30262});
    assert.equal(JSON.stringify(h.historyRef.current.document.layoutByFrontier[compactKey])===oldCompact,scope===local);
  }
});

test('actual App ignores unrelated pointer-up and stale-document move without committing history', () => {
  const h=appHarness(local);h.pointerDown(h.event(100,100,'output'));
  h.pointerUp(h.event(112,104,undefined,8));assert.equal(h.operations.length,0);assert.ok(h.gesture.current);
  h.historyRef.current=createHistory(applyVisualBatch(h.current,[{type:'alias',id:'output',label:'changed'}]));
  h.pointerUp(h.event(112,104));assert.equal(h.operations.length,0);assert.equal(h.historyRef.current.past.length,0);
});

test('actual App scope selection cancels gesture, frame and recovery before a late terminal input', () => {
  const h=appHarness(local);h.pointerDown(h.event(100,100,'output'));h.pointerMove(h.event(112,104));
  assert.equal(h.pending.size,1);assert.ok(h.captured.has(7));
  h.chooseMoveScope(all);
  assert.deepEqual(h.scopeChanges,[all]);assert.equal(h.gesture.current,null);assert.equal(h.pending.size,0);
  assert.equal(h.getPreview(),null);assert.equal(h.getRecovery(),null);assert.equal(h.captured.size,0);
  h.runFrames();h.pointerUp(h.event(112,104));assert.equal(h.operations.length,0);assert.equal(h.historyRef.current.past.length,0);
});

test('actual App alignment uses the selected scope and preserves the unrelated compact cache for current scope', () => {
  for(const scope of [all,local]) {
    const h=appHarness(scope,['input','output']),oldCompact=JSON.stringify(h.current.layoutByFrontier[compactKey]);
    h.align();
    assert.deepEqual(h.operations,[[{type:'move',ids:['input'],dx:0,dy:0,scope},{type:'move',ids:['output'],dx:-4,dy:0,scope}]]);
    assert.equal(h.historyRef.current.document.layout.output.x,32);
    assert.equal(JSON.stringify(h.historyRef.current.document.layoutByFrontier[compactKey])===oldCompact,scope===local);
  }
});

test('actual App language dispatch applies exact local world delta and preserves alias source facts', () => {
  const h=appHarness(all,['output'],'仅当前视图向上移动 28590 画布单位');
  const oldCompact=JSON.stringify(h.current.layoutByFrontier[compactKey]);h.runCommand();
  assert.deepEqual(h.operations,[[{type:'move',ids:['output'],dx:0,dy:-28590,scope:local}]]);
  assert.deepEqual(h.historyRef.current.document.layout.output,{x:36,y:1664});
  assert.equal(JSON.stringify(h.historyRef.current.document.layoutByFrontier[compactKey]),oldCompact);
  assert.deepEqual(h.historyRef.current.document.architecture,h.current.architecture);assert.deepEqual(h.commands,['']);
});

test('actual App refuses partial compound movement and leaves alias/color dispatch intact', () => {
  const invalid=appHarness(local,['output'],'向右移动 24 并设为蓝色');invalid.runCommand();
  assert.equal(invalid.operations.length,0);assert.equal(invalid.failures.length,1);assert.equal(invalid.commands.length,0);
  const alias=appHarness(local,['output'],'命名为“向右移动 24”');alias.runCommand();
  assert.deepEqual(alias.operations,[[{type:'alias',id:'output',label:'向右移动 24'}]]);
  assert.deepEqual(alias.historyRef.current.document.layout.output,{x:36,y:30254});
});

test('actual App recovery forwards current scope and applies the exact proposed operation', () => {
  const h=appHarness(local,['input']);h.previewPositionRecovery();assert.deepEqual(h.recoveryCalls,[local]);
  const value=h.getRecovery();assert.ok(value);assert.equal(value.plan.status,'ready');
  if(value.plan.status!=='ready')throw new Error('Literal header conflict must have a ready proposal');
  assert.equal(value.plan.operation.scope,local);
  const oldCompact=JSON.stringify(h.current.layoutByFrontier[compactKey]);
  h.replaceActiveRecovery(value);h.applyPositionRecovery();
  assert.deepEqual(h.operations,[[value.plan.operation]]);assert.equal(h.historyRef.current.past.length,1);
  assert.deepEqual(buildScene(h.historyRef.current.document),value.plan.scene);
  assert.equal(JSON.stringify(h.historyRef.current.document.layoutByFrontier[compactKey]),oldCompact);
});

test('scope-specific caches retain the operated-container, ancestor and pinned-subtree toggle rules', () => {
  const input=literalDocument();input.pinnedObjects=['input'];
  const moved=applyVisualBatch(input,[{type:'move',ids:['output'],dx:0,dy:-28590,scope:local}]);
  const collapsed=applyVisualBatch(moved,[{type:'expand',id:'network',expanded:false}]);
  assert.deepEqual(collapsed.layout.root,{x:50,y:92});
  assert.deepEqual(collapsed.layout.network,{x:32,y:80});
  assert.deepEqual(collapsed.layout.input,{x:32,y:20});
  assert.deepEqual(collapsed.layout.output,{x:36,y:262});
  const reopened=applyVisualBatch(collapsed,[{type:'expand',id:'network',expanded:true}]);
  assert.deepEqual(reopened.layout.output,{x:36,y:1664});
  assert.deepEqual(reopened.layout.root,{x:50,y:92});assert.deepEqual(reopened.layout.network,{x:32,y:80});
  assert.deepEqual(reopened.layout.input,{x:32,y:20});
  // Distinct neighbor placements are restored; anchored positions do not become
  // independently restorable merely because the movement scope is local.
  assert.notDeepEqual(collapsed.layout.root,input.layoutByFrontier[compactKey].root);
});
