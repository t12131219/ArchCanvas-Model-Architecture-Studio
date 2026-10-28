import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { parseMoveCommand } from '../src/moveCommand.ts';
import { applyVisualBatch, buildScene, createDocument, createHistory, reduceHistory, renderSvg, ValidationError } from '../src/core/index.ts';
import type { Architecture, ArchitectureNode, CanvasDocument, HistoryState, MoveScope, VisualOperation } from '../src/core/types.ts';

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
  for (const prefix of ['仅当前视图','只在当前视图','在当前视图','当前视图']) {
    for (let i = 0; i < 2; i += 1) {
      const fallback: MoveScope = i === 0 ? all : local;
      assert.deepEqual(parseMoveCommand(`${prefix}，向下移动 1.5`, ['output'], fallback),
        { status:'ready',operation:{type:'move',ids:['output'],dx:0,dy:1.5,scope:local} });
    }
  }
  for (const prefix of ['所有视图','全部视图','在所有视图']) {
    for (let i = 0; i < 2; i += 1) {
      const fallback: MoveScope = i === 0 ? all : local;
      assert.deepEqual(parseMoveCommand(`${prefix} 向左移动 2.75`, ['output'], fallback),
        { status:'ready',operation:{type:'move',ids:['output'],dx:-2.75,dy:0,scope:all} });
    }
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

function appHarness(scope:MoveScope=all, ids:string[]=['output'], commandText='') {
  const source=readFileSync(new URL('../src/App.tsx',import.meta.url),'utf8');
  const ast=ts.createSourceFile('App.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
  const app=ast.statements.find(item=>ts.isFunctionDeclaration(item)&&item.name?.text==='App');
  assert.ok(app&&ts.isFunctionDeclaration(app)&&app.body);
  const names=['chooseMoveScope','apply','arrangePreview','runCommand'];
  const snippets=names.map(name=>{
    const statement=app.body!.statements.find(item=>ts.isFunctionDeclaration(item)?item.name?.text===name:
      ts.isVariableStatement(item)&&item.declarationList.declarations.some(d=>ts.isIdentifier(d.name)&&d.name.text===name));
    assert.ok(statement,`Actual App callback ${name}`);return statement.getText(ast);
  });
  const historyRef={current:createHistory(literalDocument())}, current=historyRef.current.document;
  const operations:VisualOperation[][]=[],notices:string[]=[],failures:string[]=[],commands:string[]=[],scopeChanges:MoveScope[]=[],arrangementCalls:unknown[][]=[];
  const environment={historyRef,current,layoutMoveScope:scope,selection:{kind:'node',ids},command:commandText,
    selectedNode:current.architecture.nodes.find(n=>n.id===ids[0]),
    setActionFeedback:()=>{},setFailure:(value:string)=>failures.push(value),setNotice:(value:string)=>notices.push(value),
    setCommand:(value:string)=>commands.push(value),setLayoutMoveScope:(value:MoveScope)=>scopeChanges.push(value),
    setHistory:(value:HistoryState)=>assert.equal(value,historyRef.current),
    useCallback:<T>(callback:T)=>callback,cancelGesture:()=>{},mapPreviewOperations:(value:VisualOperation[])=>value,
    readyPreview:()=>true,previewLayoutDisabled:false,previewCanAlign:true,
    previewEngine:{current:{visual:async()=>{},command:(...args:unknown[])=>arrangementCalls.push(args)}},
    reduceHistory:(previous:HistoryState,action:Parameters<typeof reduceHistory>[1])=>{
      if(action.type==='apply')operations.push(action.operations);return reduceHistory(previous,action);},
    parseMoveCommand,studioTelemetry:{beginInteraction:()=>1,endInteraction:()=>{}},
  };
  const compiled=ts.transpileModule(snippets.join('\n'),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText;
  const callbacks=new Function(...Object.keys(environment),`${compiled}\nreturn {${names.join(',')}};`)(...Object.values(environment)) as {
    chooseMoveScope:(scope:MoveScope)=>void;apply:(ops:VisualOperation[])=>void;arrangePreview:(kind:string)=>void;runCommand:()=>void;
  };
  return {...callbacks,current,historyRef,operations,notices,failures,commands,scopeChanges,arrangementCalls};
}

test('actual App alignment forwards selected scope to the recursive preview without mutating formal source caches', () => {
  for(const scope of [all,local]) {
    const h=appHarness(scope,['input','output']),oldCompact=JSON.stringify(h.current.layoutByFrontier[compactKey]);
    h.arrangePreview('left');
    assert.deepEqual(h.arrangementCalls,[['arrange-selection',{kind:'left',scope}]]);
    assert.deepEqual(h.operations,[]);
    assert.equal(JSON.stringify(h.historyRef.current.document.layoutByFrontier[compactKey]),oldCompact);
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
