import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { performance } from 'node:perf_hooks';
import { previewHierarchy } from '../src/previewHierarchy.ts';
import { previewSelectionNodeIds } from '../src/previewInterop.ts';
import { previewPanelDocument } from '../src/previewPanelDocument.ts';

const root = fileURLToPath(new URL('../../', import.meta.url));
const context = vm.createContext({ performance });
for (const name of ['router', 'physical-ports', 'junction-markers', 'route-labels', 'source-contracts', 'semantic-constraints', 'graph-engine', 'recursive-graph']) {
  vm.runInContext(readFileSync(new URL(`../public/preview/yworks_edge_router_lab/${name}.js`, import.meta.url), 'utf8'), context);
}
const manifest = JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json', import.meta.url), 'utf8'));
for (const { path } of manifest.files) vm.runInContext(readFileSync(new URL(`../public/preview/${path}`, import.meta.url), 'utf8'), context, { filename: path });
vm.runInContext(readFileSync(new URL('../public/preview/yworks_edge_router_lab/studio-semantic.js', import.meta.url), 'utf8'), context);
const N = context.ArchCanvasSemanticView, G = context.SummaryNativeSemantic, E = context.SummaryEngine;
const copy = (v: any) => JSON.parse(JSON.stringify(v));
const source = `from torch import nn
class FFN(nn.Module):
 def __init__(self):
  super().__init__()
  self.up=nn.Linear(4,8)
  self.relu=nn.ReLU()
  self.down=nn.Linear(8,4)
 def forward(self,x):
  return self.down(self.relu(self.up(x)))
class Cell(nn.Module):
 def __init__(self):
  super().__init__()
  self.ffn=FFN()
  self.norm=nn.LayerNorm(4)
 def forward(self,x):
  return self.norm(x+self.ffn(x))
class Model(nn.Module):
 def __init__(self):
  super().__init__()
  self.cell=Cell()
  self.drop=nn.Dropout(0.15)
 def forward(self,x):
  return self.drop(self.cell(x))
`;
async function analyzeFiles(files: Record<string, string>, entry: string) {
  const { stdout } = await promisify(execFile)('python3', ['-I', '-S', '-B', '-c', 'import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_preview import analyze;print(json.dumps(analyze(json.loads(sys.argv[2]),sys.argv[3],semantic_mode="summary")))', root, JSON.stringify(files), entry], { encoding: 'utf8', maxBuffer: 8_000_000 });
  return JSON.parse(stdout);
}
const analyze = (text = source) => analyzeFiles({ 'net.py': text }, 'net:Model');
const bundle = await analyze();
// Keep real routing enabled; only disable optional aesthetic sweeps in the unit suite.
const options = { refineCrossings: false, refinePlacement: false, refineChannels: false, refineFlow: false };
function prepare(graph?: any, transition?: any) {
  const result = N.prepare(graph ? { task: 'frontier', graph, transition, options } : { task: 'generic-build', ir: bundle.ir.semantic_ir, binding: bundle, options });
  assert.equal(result.validation.source.ok, true, result.validation.source.violations.join('; '));
  assert.equal(result.validation.layout.ok, true, result.validation.layout.violations.join('; '));
  assert.deepEqual(copy(result.validation.edges.filter(([, v]: any) => !v.ok)), []);
  for (const [ledger, canonical] of [[result.graph.generic.receipts.node_accounting, bundle.ir.semantic_ir.nodes], [result.graph.generic.receipts.edge_accounting, bundle.ir.semantic_ir.edges]]) {
    const ids = Object.values(ledger).flat() as string[];
    assert.equal(ids.length, canonical.length); assert.equal(new Set(ids).size, canonical.length);
    assert.deepEqual([...ids].sort(), canonical.map((n: any) => n.id).sort());
  }
  return result.graph;
}

test('old parameter-arrow layouts migrate with provenance while unaffected layouts remain compatible', () => {
  const graph=prepare(),document=G.document(graph),parsed=G.read({...document,renderer:'native-semantic/18'});
  assert.equal(parsed.nativeLayout,null);
  assert.deepEqual(copy(parsed.migration.previousNativeLayout),copy(document.nativeLayout));
  for(const renderer of ['native-semantic/18','native-semantic/22','native-semantic/23','native-semantic/24']){
    assert.equal(G.requiresUpgrade(renderer,document.ir,document.state),true);
    assert.equal(G.read({...document,renderer}).nativeLayout,null);
  }
  const ir={schema:'archcanvas-source-semantic/2',nodes:[{id:'root',kind:'composite',label:'Untouched'},{id:'op',parent:'root',kind:'compute',label:'Op'}],edges:[]};
  const untouched=G.document(G.build(ir,{view:'source',mode:'source',open:['root']}));
  assert.deepEqual(copy(G.read({...untouched,renderer:'native-semantic/24'}).nativeLayout),copy(untouched.nativeLayout));
});

test('F1 uses certified roles and stages, preserves every native fact and restores F0 geometry', () => {
  const original = JSON.stringify(bundle.ir.semantic_ir), f0 = prepare();
  const layout = copy(G.layoutSnapshot(f0));
  const f1 = prepare(f0, { type: 'preset', preset: 'detail' });
  assert.ok(f1.nodes.length > f0.nodes.length);
  const recipe = f1.generic.state.paperFrontierRecipe;
  assert.equal(recipe.schema, 'certified-detail-frontier/1');
  assert.ok(recipe.role_paths.length + recipe.stage_requests.length > 0, 'a source-depth preset cannot satisfy certified refinement');
  for (const path of recipe.role_paths) assert.ok(G.expected(f1).architecture.semantic_contracts.some((c: any) => c.id === path.certificate && c.node === path.node));
  assert.equal(JSON.stringify(f1.generic.ir), original);
  assert.equal(f1.frontierPreset, 'detail');
  const returned = prepare(f1, { type: 'preset', preset: 'overview' });
  assert.deepEqual(copy(G.layoutSnapshot(returned).nodes), layout.nodes);
  assert.equal(returned.frontierPreset, 'overview');
  assert.equal(JSON.stringify(returned.generic.ir), original);
});

test('local source expansion keeps the selected node screen position and zoom', () => {
  const camera={x:10,y:20,w:800,h:500};
  const before={nodes:[{id:'leaf',x:100,y:200,w:160,h:60}]};
  const next={nodes:[{id:'leaf',x:400,y:600,w:180,h:80}],generic:{state:{}}};
  assert.deepEqual(copy(N.localCamera(before,next,camera,['leaf'])),{x:320,y:430,w:800,h:500});
  assert.deepEqual(camera,{x:10,y:20,w:800,h:500});
});

test('native cut cameras restore independently and reject invalid saved viewports', () => {
  const f0 = prepare(), f1 = prepare(f0, { type: 'preset', preset: 'detail' });
  const overviewCamera = { x: 31, y: -20, w: 800, h: 500 };
  assert.equal(N.restoreCamera(f0, f1, overviewCamera), null);
  const returned = prepare(f1, { type: 'preset', preset: 'overview' });
  const detailCamera = { x: 300, y: 20, w: 400, h: 250 };
  assert.deepEqual(copy(N.restoreCamera(f1, returned, detailCamera)), overviewCamera);
  const detail = prepare(returned, { type: 'preset', preset: 'detail' });
  assert.deepEqual(copy(N.restoreCamera(returned, detail, overviewCamera)), detailCamera);
  for (const value of [null, {}, { ...overviewCamera, w: 0 }, { ...overviewCamera, x: NaN }, { ...overviewCamera, h: Infinity }]) assert.ok(!N.validCamera(value));
});

test('source-unit expansion and native JSON roundtrip retain every original node, operand and route', () => {
  const graph = prepare(prepare(), { type: 'all', expanded: true });
  assert.equal(graph.generic.state.paperCanonical, true);
  assert.equal(graph.nodes.length, bundle.ir.semantic_ir.nodes.length);
  assert.equal(graph.edges.length + graph.generic.receipts.edge_accounting.attached.length, bundle.ir.semantic_ir.edges.length);
  assert.ok(graph.edges.every((e:any)=>e.binding.kind!=='parameter-read'));
  const saved = G.document(graph), read = G.read(copy(saved));
  const restored = N.prepare({ task: 'generic-build', ...read, options }).graph;
  assert.deepEqual(copy(G.layoutSnapshot(restored)), copy(G.layoutSnapshot(graph)));
  assert.equal(G.stable(restored.generic.ir), G.stable(bundle.ir.semantic_ir));
});

test('semantic granularity, frame and read policies preserve complete canonical accounting', () => {
  let graph = prepare(); const raw = JSON.stringify(graph.generic.ir);
  for (const paperGranularity of ['modules', 'stages', 'semantic', 'roles', 'detailed', 'overview']) {
    graph = prepare(graph, { type: 'semantic', patch: { paperGranularity } });
    assert.equal(graph.frontierPreset, 'custom');
    assert.equal(JSON.stringify(graph.generic.ir), raw);
  }
  for (const patch of [{ paperFrameView: 'source' }, { paperReadSummary: 'boundary' }, { paperSequenceView: 'summary' }]) graph = prepare(graph, { type: 'semantic', patch });
  assert.equal(graph.generic.state.paperFrameView, 'source');
});

test('role-path requests must name an existing certificate and exact role; forgery rejects', () => {
  const graph = prepare(prepare(), { type: 'preset', preset: 'detail' });
  const role = N.inspector(graph).roleOptions[0]; assert.ok(role);
  const request = { node: role.node, certificate: role.certificate, role: role.role };
  prepare(graph, { type: 'semantic', patch: { paperRolePaths: [request] } });
  assert.throws(() => prepare(graph, { type: 'semantic', patch: { paperRolePaths: [{ ...request, certificate: 'forged' }] } }), /认证契约/);
  assert.throws(() => prepare(graph, { type: 'semantic', patch: { paperRolePaths: [{ ...request, role: ['nonexistent'] }] } }), /认证契约/);
  assert.throws(() => prepare(graph, { type: 'semantic', patch: { mode: 'runtime' } }), /没有 CPU/);
  assert.throws(() => prepare(graph, { type: 'semantic', patch: { paperGranularity: 'fake' } }), /无效/);
  assert.throws(() => prepare(graph, { type: 'semantic', patch: { paperRepresentative: true, paperFocus: role.node, paperRepresentativeGroup: 999 } }), /已证明/);
  const details = N.inspector(graph, [graph.nodes[0].id]).selectionDetails;
  assert.equal(details.length, 1);
  assert.ok(details[0].evidence.length > 0);
});

test('native navigation feeds Studio hierarchy and panel projection without inventing formal bindings', () => {
  const graph = prepare(), snapshot = { graph, semanticView: N.inspector(graph) };
  const hierarchy = previewHierarchy(snapshot)!;
  assert.ok(hierarchy.nodes.length > graph.nodes.length, 'latent source children stay navigable');
  for (const raw of graph.nodes) assert.ok(hierarchy.nodes.some(node => node.id === raw.id));
  const document = previewPanelDocument(snapshot, bundle);
  assert.ok(document.sourceBindingDigest.startsWith('preview-only:'));
  assert.equal(document.architecture.nodes.length, hierarchy.nodes.length);
  const synthetic = { id: 'summary', presentation_only: true, canonical_members: ['a', 'b'] };
  assert.deepEqual(previewSelectionNodeIds({ ...document.architecture, nodes: [{ ...document.architecture.nodes[0], id: 'summary' }] }, { nodeId: synthetic.id, node: synthetic }), []);
});

test('visual overlays survive semantic projection and saved native layout rejects binding/receipt tampering', () => {
  const graph = prepare(); graph.studioPresentation = { version: 1, nodes: { [graph.nodes[1].id]: { alias: '保留名称' } }, edges: {}, annotations: {}, legend: [], page: {} };
  const next = prepare(graph, { type: 'preset', preset: 'detail' });
  assert.deepEqual(copy(next.studioPresentation), graph.studioPresentation);
  const restored = copy(next); assert.equal(E.validateView(restored).source.ok, true);
  assert.equal(Object.isFrozen(restored.edges[0].binding), true);
  restored.edges[0].binding = { ...restored.edges[0].binding, target_port: 'forged' };
  assert.equal(E.validateView(restored).source.ok, false);
  const forged = copy(next);forged.generic.receipts.node_accounting.visible.pop();
  assert.equal(E.validateView(forged).source.ok, false);
});

test('an exhausted routing budget stays explicit, saves as incomplete and can continue without changing source', () => {
  const result = N.prepare({task:'generic-build',ir:bundle.ir.semantic_ir,binding:bundle,options:{...options,budgetMs:0}});
  assert.ok(result.pending > 0);
  assert.equal(result.graph.nativeRouting.complete, false);
  assert.equal(N.accepts(result.graph, result.validation), true);
  const restored = copy(result.graph), before = JSON.stringify(restored.generic.ir);
  const continued = N.prepare({task:'generic-route',graph:restored,options});
  assert.equal(continued.pending, 0);
  assert.equal(continued.failed, 0);
  assert.equal(continued.validation.layout.ok, true);
  assert.equal(JSON.stringify(continued.graph.generic.ir), before);
  const forged = copy(result.graph); forged.edges[0].binding.target_port = 'forged';
  assert.equal(N.accepts(forged, E.validateView(forged)), false);
});

test('native physical port overrides reroute the selected endpoint without changing the operand binding', () => {
  const graph = prepare(prepare(), {type:'all',expanded:true});
  const target = graph.nodes.filter((n: any) => n.semantic.label === 'return').at(-1);
  const edge = graph.edges.find((e: any) => e.target === target.id), binding = copy(edge.binding);
  const physical = {side:'left',fraction:.5};
  edge.physicalTarget = physical; edge.pendingRouting = true;
  const result = N.prepare({task:'generic-route',graph,options:{portOverrides:{[edge.id]:{target:physical}}}});
  assert.equal(result.failed, 0);
  assert.deepEqual(copy(result.graph.edges.find((e: any) => e.id === edge.id).physicalTarget), physical);
  assert.deepEqual(copy(edge.binding), binding);
});

test('conditional, iteration and opaque regions retain all unknown boundaries in every semantic cut', async () => {
  const value = await analyze('from torch import nn\nfrom external import mystery\nclass Model(nn.Module):\n def forward(self,x,flag):\n  if flag:\n   y=mystery(x)\n  else:\n   y=x.relu()\n  for i in range(3):\n   y=y.relu()\n  return y\n');
  let graph = N.prepare({ task: 'generic-build', ir: value.ir.semantic_ir, binding: value, options }).graph;
  const before = JSON.stringify(graph.generic.ir);
  graph = N.prepare({ task: 'frontier', graph, transition: { type: 'preset', preset: 'detail' }, options }).graph;
  assert.equal(JSON.stringify(graph.generic.ir), before);
  const cut = G.expected(graph), ledger = Object.values(cut.node_accounting).flat();
  for (const node of graph.generic.ir.nodes.filter((n: any) => n.kind === 'opaque' || n.condition || n.iteration_contract)) assert.ok(ledger.includes(node.id));
  assert.equal(E.validateView(graph).source.ok, true);
});

for (const [fixture, model] of [['mlp', 'MLP'], ['residual_cnn', 'ResidualCNN'], ['transformer', 'Transformer'], ['holdout_vit', 'PatchVisionEncoder'], ['holdout_families', 'TemporalForecaster']]) {
  test(`formal ${fixture} source keeps complete native accounting through F0, F1 and source-unit cuts`, async (t) => {
    const folder = new URL(`../../fixtures/${fixture}/`, import.meta.url);
    const files = Object.fromEntries(readdirSync(folder).filter(name => name.endsWith('.py')).map(name => [name, readFileSync(new URL(name, folder), 'utf8')]));
    const value = await analyzeFiles(files, `model:${model}`), ir = value.ir.semantic_ir;
    // A route-validity regression gets its own finite budget; budget exhaustion
    // and continuation are exercised separately above, including budgetMs: 0.
    const fixtureOptions = { ...options, budgetMs: 30_000 };
    let graph: any;
    for (const transition of [null, { type: 'preset', preset: 'detail' }, { type: 'all', expanded: true }]) {
      let result: any = N.prepare(graph ? { task: 'frontier', graph, transition, options: fixtureOptions } : { task: 'generic-build', ir, binding: value, options: fixtureOptions });
      for (let attempt=0; attempt<1 && result.failed; attempt++) result = N.prepare({task:'generic-route',graph:result.graph,options:fixtureOptions});
      graph = result.graph;
      assert.equal(result.validation.source.ok, true, result.validation.source.violations.join('; '));
      assert.equal(N.accepts(graph, result.validation), true, JSON.stringify(result.validation));
      assert.equal(graph.nativeRouting.complete, result.pending === 0 && result.failed === 0);
      t.diagnostic(JSON.stringify({fixture,cut:transition?.type==='all'?'source-unit':transition?.preset||'overview',nodes:graph.nodes.length,edges:graph.edges.length,pending:result.pending,failed:result.failed,invalid:result.validation.edges.filter(([,v]:any)=>!v.ok).map(([id]:any)=>id)}));
      assert.equal(JSON.stringify(graph.generic.ir), JSON.stringify(ir));
      for (const [ledger, objects] of [[graph.generic.receipts.node_accounting, ir.nodes], [graph.generic.receipts.edge_accounting, ir.edges]]) {
        const ids = Object.values(ledger).flat() as string[];
        assert.deepEqual([...ids].sort(), objects.map((n: any) => n.id).sort());
        assert.equal(new Set(ids).size, ids.length);
      }
      assert.equal(result.pending, 0); assert.equal(result.failed, 0);
      assert.equal(result.validation.layout.ok, true);
      assert.deepEqual(copy(result.validation.edges.filter(([, v]: any) => !v.ok)), []);
    }
  });
}

test('weight reads attach to consumer details without hiding masks, buffer values, control or tensor operands', () => {
  const ir:any={schema:'archcanvas-source-semantic/2',nodes:[
    {id:'root',kind:'composite',label:'Unseen'},
    {id:'weights',parent:'root',kind:'parameter',label:'arbitrary weight'},
    {id:'buffer',parent:'root',kind:'buffer',label:'persistent tensor'},
    {id:'mask',parent:'root',kind:'interface',role:'input',label:'mask'},
    {id:'input',parent:'root',kind:'interface',role:'input',label:'value'},
    {id:'guard',parent:'root',kind:'control',operator:'if',label:'guard'},
    {id:'op',parent:'root',kind:'compute',operator:'unknown',label:'Unseen operation'}
  ],edges:[
    {id:'weight-use',source:'weights',target:'op',kind:'parameter-read',evidence:'framework-contract'},
    {id:'tensor-operand',source:'weights',target:'op',kind:'data',target_port:'arg:1'},
    {id:'buffer-use',source:'buffer',target:'op',kind:'data'},
    {id:'mask-use',source:'mask',target:'op',kind:'interface-binding',target_port:'mask'},
    {id:'value-use',source:'input',target:'op',kind:'data',target_port:'arg:0'},
    {id:'control-use',source:'guard',target:'op',kind:'control'}
  ]};
  for(const edge of ir.edges){edge.source_port??='out';edge.target_port??='in';}
  const original=JSON.stringify(ir),state={view:'source',mode:'source',open:['root']};
  const cut=G.project(ir,state),reference=context.SemanticEngine.project(ir,state,null,{semanticOnly:true});
  assert.deepEqual(copy(cut.edges),copy(reference.edges.filter((e:any)=>e.kind!=='parameter-read')));
  assert.deepEqual(copy(cut.edge_accounting.attached),['weight-use']);
  assert.deepEqual(copy(cut.annotations.get('op')[0].edge),ir.edges[0]);
  assert.equal(cut.annotations.get('op')[0].resource.id,'weights');
  assert.match(G.nodeEvidence(G.build(ir,state),'op'),/Parameter dependencies/);
  assert.equal(JSON.stringify(ir),original);
});

test('all catalog configurations attach parameter arrows at overview, detail and full source cuts', t => {
  const catalog=JSON.parse(readFileSync(new URL('../public/preview/data/semantic/studio-catalog.json',import.meta.url),'utf8'));
  let views=0,parameterReads=0;
  for(const model of catalog.models){
    const ir=JSON.parse(readFileSync(new URL('../public/preview/data/semantic/'+model.ir.path,import.meta.url),'utf8')),original=JSON.stringify(ir);
    const full=context.SemanticPublication.fullyExpanded(ir,{mode:'source'},context.SemanticEngine);
    for(const [name,state]of [['F0',N.state('overview')],['F1',G.initial(ir)],['source',full]]){
      const cut=G.project(ir,state),members=(e:any):any[]=>e.bundle_members?.flatMap(members)||[e];
      assert.ok(cut.edges.flatMap(members).every((e:any)=>e.kind!=='parameter-read'),model.id+': '+name);
      const counted=Object.values(cut.edge_accounting).flat() as string[];
      assert.equal(counted.length,ir.edges.length,model.id+': complete ledger');
      assert.equal(new Set(counted).size,ir.edges.length,model.id+': no duplicate accounting');
      assert.deepEqual([...counted].sort(),ir.edges.map((e:any)=>e.id).sort());
      for(const edge of ir.edges.filter((e:any)=>e.kind==='parameter-read')){
        if(cut.edge_accounting.excluded.includes(edge.id))continue;
        assert.ok(cut.edge_accounting.attached.includes(edge.id),model.id+': '+edge.id);
        assert.ok([...cut.annotations.values()].flat().some((note:any)=>note.annotation_kind==='parameter-dependency'&&JSON.stringify(note.edge)===JSON.stringify(edge)),model.id+': exact parameter evidence');
        parameterReads++;
      }
      views++;
    }
    assert.equal(JSON.stringify(ir),original);
  }
  t.diagnostic(JSON.stringify({configurations:catalog.models.length,views,parameterReads,modelExecution:false}));
});

test('revisiting a complete source/state cut skips projection and layout while owning fresh mutable geometry', () => {
  const ir:any={schema:'archcanvas-source-semantic/2',title:'cache-isolation',nodes:[
    {id:'cache-root',kind:'composite',label:'Cache root'},
    {id:'cache-op',parent:'cache-root',kind:'compute',label:'Original label'}
  ],edges:[]},state={view:'source',mode:'source',open:['cache-root']};
  const first=G.build(ir,state),positions=copy(first.nodes.map((n:any)=>[n.id,n.x,n.y,n.w,n.h]));
  const runtime=context.SummarySourceRuntime,layout=context.SemanticLayout,project=runtime.project,arrange=layout.layout;
  let projects=0,layouts=0;runtime.project=(...args:any[])=>{projects++;return project(...args);};layout.layout=(...args:any[])=>{layouts++;return arrange(...args);};
  try{
    first.nodes[0].x+=50;first.generic.layouts.push({key:'private',layout:{}});
    const second=G.build(copy(ir),copy(state),{migration:{private:'new'}});
    assert.equal(projects,0);assert.equal(layouts,0);
    assert.deepEqual(copy(second.nodes.map((n:any)=>[n.id,n.x,n.y,n.w,n.h])),positions);
    assert.notEqual(first.nodes,second.nodes);assert.notEqual(first.nodes[0],second.nodes[0]);
    assert.deepEqual(copy(second.generic.layouts),[]);
    assert.deepEqual(copy(second.generic.migration),{private:'new'});
    assert.equal(G.validate(second,true).ok,true);
    const altered=copy(ir);altered.nodes[1].label='Changed source, same claimed digest';altered.ir_digest='claimed';
    const changed=G.build(altered,state);
    assert.ok(projects>0&&layouts>0,'a saved digest cannot authorize reuse across changed source facts');
    assert.equal(changed.nodes.find((n:any)=>n.id==='cache-op').semantic.label,altered.nodes[1].label);
    const closed=G.build(ir,{...state,open:[]});assert.equal(closed.nodes.length,1);
  }finally{runtime.project=project;layout.layout=arrange;}
});

test('multi-selection atomic expansion compiles its complete source form once and preserves independent ranges', () => {
  const catalog=JSON.parse(readFileSync(new URL('../public/preview/data/semantic/studio-catalog.json',import.meta.url),'utf8'));
  const model=catalog.models.find((m:any)=>m.title==='Transformer · 语义架构');
  const ir=JSON.parse(readFileSync(new URL('../public/preview/data/semantic/'+model.ir.path,import.meta.url),'utf8'));
  ir.title='independent atomic projection cache check';
  const base=G.build(ir),targets=base.nodes.filter((n:any)=>!n.modelHeading&&!G.children(base,n.id).length&&G.atomicTargets(base,[n.id]).length).slice(0,2).map((n:any)=>n.id);
  assert.equal(targets.length,2);
  const P=context.SemanticPublication,project=P.projectCanonical;let calls=0;
  P.projectCanonical=(...args:any[])=>{calls++;return project(...args);};
  try{
    const result=G.operate(base,{kind:'atomic',ids:targets,open:true});
    assert.equal(calls,1,'independent atomic selections share one canonical projection');
    assert.equal(result.generic.state.atomicCuts.length,2);
    assert.equal(G.validate(result,true).ok,true);
    assert.equal(JSON.stringify(result.generic.ir),JSON.stringify(base.generic.ir));
    assert.ok(result.edges.every((e:any)=>e.binding.kind!=='parameter-read'));
    const separate=G.operate(base,{kind:'atomic',ids:[targets[1]],open:true});
    assert.equal(calls,1,'another scope reuses the immutable complete source analysis');
    assert.equal(separate.generic.state.atomicCuts.length,1);
    assert.equal(result.generic.state.atomicCuts.length,2,'cached analysis does not merge independent view state');
    assert.equal(G.validate(separate,true).ok,true);
  }finally{P.projectCanonical=project;}
});
