import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
import { loadSummaryPreviewCases } from '../src/summaryCatalog.ts';

const root = new URL('../public/preview/', import.meta.url);
const catalog = JSON.parse(readFileSync(new URL('data/summary-cases.json', root), 'utf8'));
const context = vm.createContext({ performance });
context.self = context; context.window = context;
context.importScripts = (...files: string[]) => files.forEach(file => vm.runInContext(readFileSync(new URL('yworks_edge_router_lab/' + file, root), 'utf8'), context));
vm.runInContext(readFileSync(new URL('yworks_edge_router_lab/routing-worker.js', root), 'utf8'), context);
const C = context.SummaryConstraints, F = context.SummaryRecursive, T = context.SummaryFrontierTask;

test('current Summary directory loads independently of retired Studio examples and all new assets match their receipt', async t => {
  t.mock.method(globalThis, 'fetch', async (url: string) => {
    assert.equal(url, '/preview/data/summary-cases.json');
    return new Response(readFileSync(new URL('data/summary-cases.json', root)));
  });
  assert.deepEqual(await loadSummaryPreviewCases(), catalog.cases);
  const manifest = JSON.parse(readFileSync(new URL('../../docs/summary-current-cases-manifest-20261028.json', import.meta.url), 'utf8'));
  assert.equal(catalog.cases.length, 3);
  for (const record of manifest.files) {
    const data = readFileSync(new URL(record.path, root));
    assert.equal(data.length, record.bytes);
    assert.equal(createHash('sha256').update(data).digest('hex'), record.sha256);
  }
});

for (const item of catalog.cases) test(`${item.title}: real worker projection, detail expansion and return preserve the full case authority`, () => {
  const descriptors = item.routeTemplates ? [...item.views, ...item.routeTemplates] : item.sourceAtomic ? [...item.views,
    ...['overview', 'modules', 'detailed'].map(key => ({ key, asset: `data/cases/01093cc06a87b35a-${key}.js`, dataKey: `01093cc06a87b35a:${key}` }))] : item.views;
  const sources: Record<string, unknown> = {};
  for (const descriptor of descriptors) {
    vm.runInContext(readFileSync(new URL(descriptor.asset, root), 'utf8'), context);
    sources[descriptor.key] = C.initialize(context.SummaryCaseData[descriptor.dataKey ?? `${item.id}:${descriptor.key}`]);
  }
  const document = F.create(sources), authority = JSON.stringify(document.authority);
  assert.equal(document.authority.detail.nodes.length, item.views.at(-1).nodes);
  const initial = T.run(F.build(document), null, {});
  function valid(result: any) {
    assert.equal(result.ok, true, result.error); assert.equal(result.failed, 0);
    assert.equal(result.validation.source.ok, true); assert.equal(result.validation.layout.ok, true);
    assert.equal(JSON.stringify(result.graph.recursive.authority), authority);
  }
  valid(initial);
  const parents = new Map(document.authority.detail.nodes.map((node: any) => [node.id, node.parent]));
  const depth = (id: string) => { let n = 0; while (parents.get(id)) { id = parents.get(id) as string; n++; } return n; };
  const base = Math.min(...document.authority.mandatory.map(depth));
  const ids = F.containers(document.authority).filter((id: string) => depth(id) <= base + 1);
  const detail = T.run(initial.graph, { type: 'expand', ids, expanded: true }, {}); valid(detail);
  assert.ok(detail.graph.nodes.length >= initial.graph.nodes.length);
  const folded = T.run(detail.graph, { type: 'expand', ids: ids.filter((id: string) => !document.authority.mandatory.includes(id)), expanded: false }, {}); valid(folded);
});

for (const item of catalog.cases) test(`${item.title}: module cuts retain all registered source identities and independent siblings`, () => {
  const descriptors = item.routeTemplates ? [...item.views, ...item.routeTemplates] : item.sourceAtomic ? [...item.views,
    ...['overview', 'modules', 'detailed'].map(key => ({ key, asset: `data/cases/01093cc06a87b35a-${key}.js`, dataKey: `01093cc06a87b35a:${key}` }))] : item.views;
  const sources: Record<string, unknown> = {};
  for (const d of descriptors) { vm.runInContext(readFileSync(new URL(d.asset, root), 'utf8'), context); sources[d.key] = C.initialize(context.SummaryCaseData[d.dataKey ?? `${item.id}:${d.key}`]); }
  const graph=F.build(F.create(sources)), authority=JSON.stringify(graph.recursive.authority), modules=T.modules(graph);
  const target=modules.find((m:any)=>m.parent&&!graph.recursive.authority.mandatory.includes(m.id))??modules[0];assert.ok(target);
  for(const request of [{ids:[target.id],level:'f0'},{ids:[target.id],level:'f1'},{ids:[target.id],level:'source',depth:1},{ids:[target.id],level:'source'}]){
    const next=T.moduleCut(graph,request);
    assert.equal(JSON.stringify(next.recursive.authority),authority);
    assert.deepEqual(Array.from(F.nodeErrors(next)),[]);
    for(const edge of next.edges)assert.deepEqual(Array.from(F.edgeErrors(next,edge,edge.route,{skipPhysical:true})),[]);
    assert.equal(T.inspector(next,[]).moduleCuts.length,1);
    const returned=T.moduleCut(next,{ids:[target.id],reset:true});
    assert.deepEqual(Array.from(returned.nodes.map((n:any)=>n.id)),Array.from(graph.nodes.map((n:any)=>n.id)));
  }
  const source=new Map(graph.recursive.authority.detail.nodes.map((n:any)=>[n.id,n]));
  const within=(id:string,owner:string)=>{while(id){if(id===owner)return true;id=(source.get(id)as any)?.parent;}return false;};
  for(const module of modules){
    const next=T.moduleCut(graph,{ids:[module.id],level:'source'}),visible=new Set(next.nodes.map((n:any)=>n.id));
    for(const n of graph.recursive.authority.detail.nodes.filter((n:any)=>within(n.id,module.id)))assert.ok(visible.has(n.id),`${module.label}: ${n.id}`);
  }
  // Exercise the actual strict router as well as the semantic-only projections.
  const routed=T.run(graph,{type:'module',request:{ids:[target.id],level:'f1'}},{});
  assert.equal(routed.validation.source.ok,true);assert.equal(routed.validation.layout.ok,true);assert.equal(routed.failed,0);
  let manual=T.moduleCut(graph,{ids:[target.id],level:'source'});
  const child=modules.find((m:any)=>m.id!==target.id&&within(m.id,target.id));
  const sibling=modules.find((m:any)=>!within(m.id,target.id)&&!within(target.id,m.id));
  if(child&&sibling){manual=F.toggle(manual,child.id,false);const changed=T.moduleCut(manual,{ids:[sibling.id],level:'f0'});assert.equal(F.opened(changed.recursive,child.id),false);}
});
