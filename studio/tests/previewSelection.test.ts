import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
const directory = new URL('../public/preview/yworks_edge_router_lab/', import.meta.url);
const context = vm.createContext({});
vm.runInContext(readFileSync(new URL('studio-selection.js', directory), 'utf8'), context);
const S = context.ArchCanvasStudioSelection;
const plain = (value: unknown) => JSON.parse(JSON.stringify(value));
const nodes = [
  { id:'frame',x:0,y:0,w:400,h:500,expanded:true },
  { id:'a',x:20,y:40,w:80,h:40,parent:'frame' },
  { id:'b',x:170,y:130,w:100,h:40,parent:'frame' },
  { id:'j',x:100,y:100,w:8,h:8,parent:'frame',junction:true },
  { id:'other',x:450,y:50,w:80,h:40 },
];
test('selection replacement, additive click and toggling retain insertion order without duplicates',()=>{
  const before=new Set(['a','b']);
  assert.deepEqual([...S.update(before,['b','other'],'add')],['a','b','other']);
  assert.deepEqual([...S.update(before,['b','other'],'toggle')],['a','other']);
  assert.deepEqual([...S.update(before,['other','other'])],['other']);
  assert.deepEqual([...before],['a','b']);
  assert.throws(()=>S.update(before,[],'surprise'),/选择方式/);
});
test('marquee works in all directions, requires full containment and excludes junctions and expanded scopes',()=>{
  const original=JSON.stringify(nodes);
  for(const [a,b]of [[{x:10,y:30},{x:300,y:200}],[{x:300,y:200},{x:10,y:30}],[{x:10,y:200},{x:300,y:30}],[{x:300,y:30},{x:10,y:200}]])assert.deepEqual(plain(S.inBox(nodes,a,b)),['a','b']);
  assert.deepEqual(plain(S.inBox(nodes,{x:10,y:30},{x:230,y:150})),['a']);
  assert.deepEqual(plain(S.inBox(nodes,{x:0,y:0},{x:400,y:500})),['a','b']);
  assert.equal(JSON.stringify(nodes),original);
});
test('scope commands select exact siblings, exclude hidden facts and keep parent-child scopes out of select all',()=>{
  assert.deepEqual(plain(S.targets(nodes,new Set(['a']),'siblings')),['a','b']);
  assert.deepEqual(plain(S.targets(nodes,new Set(['other']),'siblings')),['frame','other']);
  assert.deepEqual(plain(S.targets(nodes,new Set(),'all')),['a','b','other']);
  assert.throws(()=>S.targets(nodes,new Set(),'siblings'),/先选择/);
});
// Exercise the actual canvas event handler, rather than a second implementation.
const app=readFileSync(new URL('app.js',directory),'utf8');
const handler=app.slice(app.indexOf('  function nodeDown('),app.indexOf('  function edgeDown('));
for(const modifier of ['shiftKey','ctrlKey','metaKey'])test(`canvas ${modifier} toggles selection without beginning a drag or changing history`,()=>{
  const c=vm.createContext({window:{ArchCanvasStudioSelection:S},busy:false,tool:'select',selectedAnnotation:'note',selectedNodes:new Set(['a']),selectedEdges:new Set(['edge']),render(){},begin(){throw new Error('unexpected drag');}});
  vm.runInContext(handler,c);
  c.nodeDown({button:0,[modifier]:true,stopPropagation(){}},{id:'b'});
  assert.deepEqual([...c.selectedNodes],['a','b']);assert.equal(c.selectedEdges.size,0);assert.equal(c.selectedAnnotation,null);
  c.nodeDown({button:0,[modifier]:true,stopPropagation(){}},{id:'a'});
  assert.deepEqual([...c.selectedNodes],['b']);
});
test('dragging an existing multi selection preserves it and checks pinned members before starting',()=>{
  const started:any[]=[];let pinned=false;
  const c=vm.createContext({window:{ArchCanvasStudioSelection:S,ArchCanvasStudioPresentation:{state:()=>({nodes:pinned?{b:{pinned:true}}:{}})}},graph:{},busy:false,tool:'select',selectedAnnotation:null,selectedNodes:new Set(['a','b']),selectedEdges:new Set(),begin(_ev:any,item:any){started.push(item);},toast(){},render(){}});
  vm.runInContext(handler,c);
  c.nodeDown({button:0,stopPropagation(){}},{id:'a'});
  assert.deepEqual(plain(started[0]),{kind:'group',ids:['a','b'],clicked:'a'});assert.deepEqual([...c.selectedNodes],['a','b']);
  pinned=true;c.nodeDown({button:0,stopPropagation(){}},{id:'a'});assert.equal(started.length,1);
});

test('a plain click on a selected group member returns to a single selection without a visual edit',async()=>{
  const ast=ts.createSourceFile('app.js',app,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
  let listener:ts.Expression|undefined;
  function visit(n:ts.Node){if(ts.isCallExpression(n)&&n.expression.getText(ast)==='svg.addEventListener'&&n.arguments[0]?.getText(ast)==="'pointerup'")listener=n.arguments[1];ts.forEachChild(n,visit);}
  visit(ast);assert.ok(listener);
  const c=vm.createContext({drag:{kind:'group',ids:['a','b'],clicked:'a',start:{x:10,y:20}},dragFrame:0,dragPoint:null,
    selectedNodes:new Set(['a','b']),point:()=>({x:10,y:20}),hitNode:()=>null,processDragPoint(){},
    svg:{hasPointerCapture:()=>false},$:()=>({replaceChildren(){}}),render(){},studioBridge:{state(){}},
    studioVisual(){throw new Error('selection click must not create an edit');},toast(){}});
  await vm.runInContext(`(${listener.getText(ast)})({pointerId:1})`,c);
  assert.deepEqual([...c.selectedNodes],['a']);assert.equal(c.drag,null);
});
