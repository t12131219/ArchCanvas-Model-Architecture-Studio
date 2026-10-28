import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
const native = readFileSync(new URL('../public/preview/yworks_edge_router_lab/app.js', import.meta.url), 'utf8');
const cancel = native.slice(native.indexOf('  function cancelActiveGesture(){'), native.indexOf("  svg.addEventListener('pointercancel'"));

function gestureHarness(kind: string, saved = false) {
  const originalGraph = { id: 'original' }, originalHistory = ['original'], originalFuture = ['redo'];
  const active = { kind, saved, pointerId: 7, initial: ['before-selection'], camera: { x: -12, y: 18, w: 700, h: 400 }, before: originalGraph, history: originalHistory, future: originalFuture, dirty: false };
  const releases: number[] = [], frames: number[] = [], renders: unknown[] = [];
  const env = vm.createContext({ drag: active, dragFrame: 33, dragPoint: { x: 9, y: 9 }, connection: {}, camera: { x: 100, y: 100, w: 700, h: 400 }, selectedNodes: new Set(['transient']), graph: { id: 'transient' }, history: ['transient'], future: [], dirty: true,
    cancelAnimationFrame: (id: number) => frames.push(id), cameraUpdate() {}, render: (value: unknown) => renders.push(value), studioBridge: { state() {} },
    svg: { hasPointerCapture: () => true, releasePointerCapture: (id: number) => { assert.equal(env.drag, null); releases.push(id); }, classList: { remove() {} } }, $: () => ({ replaceChildren() {} }),
  });
  vm.runInContext(native.slice(native.indexOf('  function restoreGesture('), native.indexOf('  function unchangedGesture(')) + cancel, env);
  return { env, run: () => vm.runInContext('cancelActiveGesture()', env), active, originalGraph, originalHistory, originalFuture, frames, releases, renders };
}

test('native cancellation restores a mutated graph and both histories before releasing capture, and repeated cancellation cannot commit it', () => {
  const h = gestureHarness('node', true); h.run();
  assert.equal(h.env.graph, h.originalGraph); assert.equal(h.env.history, h.originalHistory); assert.equal(h.env.future, h.originalFuture); assert.equal(h.env.dirty, false);
  assert.equal(h.env.drag, null); assert.equal(h.env.dragFrame, 0); assert.equal(h.env.dragPoint, null); assert.equal(h.env.connection, null);
  assert.deepEqual(h.frames, [33]); assert.deepEqual(h.releases, [7]); assert.deepEqual(JSON.parse(JSON.stringify(h.renders)), [{ presentationOnly: false }]);
  h.run(); assert.deepEqual(h.releases, [7]); assert.equal(h.env.history, h.originalHistory);
});

test('native pan rollback restores camera and marquee rollback restores prior selection without adding graph history', () => {
  const pan = gestureHarness('pan'); const history = pan.env.history; pan.run();
  assert.deepEqual(JSON.parse(JSON.stringify(pan.env.camera)), pan.active.camera); assert.equal(pan.env.history, history);
  const box = gestureHarness('marquee'); box.run(); assert.deepEqual(Array.from(box.env.selectedNodes), ['before-selection']);
});

function appCallback(name: string, environment: Record<string, unknown>) {
  const source = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8'), ast = ts.createSourceFile('App.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const app = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'App') as ts.FunctionDeclaration;
  const body = app.body!.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === name)!;
  const code = ts.transpileModule(body.getText(ast), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  return new Function(...Object.keys(environment), `${code};return ${name};`)(...Object.values(environment));
}

test('retained port panel forwards exact child identity or formal evidence mapping and ignores an old model failure', async () => {
  const calls: unknown[] = [], notices: string[] = [], failures: string[] = [], loadSequence = { current: 3 };
  let reject!: (reason: Error) => void;
  const run = appCallback('optimizeAutomaticPorts', { readyPreview: () => true, graphFromSnapshot: () => ({ nodes: [{ id: 'native/raw' }] }), previewNodeId: (id: string) => id === 'formal-source' ? 'native/from-evidence' : undefined,
    loadSequence, previewEngine: { current: { visual: (ops: unknown) => { calls.push(ops); return calls.length === 3 ? new Promise((_yes, no) => { reject = no; }) : Promise.resolve(); } } },
    setNotice: (value: string) => notices.push(value), setFailure: (value: string) => failures.push(value) });
  run('native/raw', true); run('formal-source'); await Promise.resolve(); await Promise.resolve();
  assert.deepEqual(calls, [[{ type: 'portLayout', ownerId: 'native/raw', nodeId: 'native/raw', layout: null }], [{ type: 'portLayout', ownerId: 'native/from-evidence', nodeId: 'native/from-evidence', layout: null }]]);
  assert.equal(notices.length, 2);
  run('native/raw', true); loadSequence.current++; reject(Error('old model')); await Promise.resolve(); await Promise.resolve(); assert.deepEqual(failures, ['', '']);
  run('unmapped'); assert.match(failures.at(-1)!, /唯一对应/); assert.equal(calls.length, 3);
});

test('retained layout panel delegates to Summary without building or writing a formal layout', () => {
  const calls: unknown[] = [];
  const run = appCallback('repairSummaryLayout', { readyPreview: () => true, cancelGesture: () => calls.push('cancel'), previewEngine: { current: { command: (command: string) => calls.push(command) } } });
  run(); assert.deepEqual(calls, ['cancel', 'apply-layout']);
});

test('same-origin bridge accepts cancellation while a native gesture is busy but rejects another mutation', async () => {
  let listener!: (event: unknown) => void; const messages: any[] = [], calls: string[] = [];
  const parent = { postMessage: (message: unknown) => messages.push(message) };
  const root = { parent, location: { origin: 'http://localhost:1234', search: '' }, addEventListener: (_: string, fn: typeof listener) => { listener = fn; } };
  const env = vm.createContext({ window: root, URLSearchParams, document: {} });
  vm.runInContext(readFileSync(new URL('../public/preview/yworks_edge_router_lab/studio-bridge.js', import.meta.url), 'utf8'), env);
  (root as any).ArchCanvasPreviewBridge.create({ started: async () => {}, isBusy: () => true, state: () => ({}), command: async (command: string) => calls.push(command) });
  for (const command of ['cancel-gesture', 'fit']) listener({ source: parent, origin: root.location.origin, data: { type: 'archcanvas:preview:' + command, requestId: command } });
  for (let i = 0; i < 8; i++) await Promise.resolve();
  assert.deepEqual(calls, ['cancel-gesture']); assert.ok(messages.some(m => m.type.endsWith(':applied') && m.requestId === 'cancel-gesture')); assert.ok(messages.some(m => m.type.endsWith(':error') && m.requestId === 'fit'));
});


test('startup progress and cancellation remain available before readiness without waiting on the unfinished startup promise',async()=>{
 let listener!:(event:unknown)=>void;const messages:any[]=[],calls:string[]=[];
 const parent={postMessage:(message:unknown)=>messages.push(message)};
 const root={parent,location:{origin:'http://localhost:1234',search:''},addEventListener:(_:string,fn:typeof listener)=>{listener=fn;}};
 const env=vm.createContext({window:root,URLSearchParams,document:{}});
 vm.runInContext(readFileSync(new URL('../public/preview/yworks_edge_router_lab/studio-bridge.js',import.meta.url),'utf8'),env);
 const bridge=(root as any).ArchCanvasPreviewBridge.create({started:()=>new Promise(()=>{}),isBusy:()=>true,command:async(command:string)=>calls.push(command)});
 bridge.progress({canCancel:true,message:'正在恢复'});assert.equal(messages[0].type,'archcanvas:preview:progress');assert.equal(messages[0].canCancel,true);
 listener({source:parent,origin:root.location.origin,data:{type:'archcanvas:preview:cancel-operation',requestId:'cancel'}});
 for(let i=0;i<6;i++)await Promise.resolve();assert.deepEqual(calls,['cancel-operation']);assert.ok(messages.some(v=>v.type.endsWith(':applied')&&v.requestId==='cancel'));
 listener({source:parent,origin:'https://other.invalid',data:{type:'archcanvas:preview:cancel-operation',requestId:'foreign'}});
 for(let i=0;i<6;i++)await Promise.resolve();assert.deepEqual(calls,['cancel-operation']);
});
