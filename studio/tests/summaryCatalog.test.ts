import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { webcrypto, createHash } from 'node:crypto';
import vm from 'node:vm';
import { loadSummaryCatalog, loadSummaryCatalogModel, parseSummaryCatalog, summaryCatalogBlockReason, SUMMARY_CATALOG_LIMITS } from '../src/summaryCatalog.ts';

const root = new URL('../public/preview/', import.meta.url);
const catalog = parseSummaryCatalog(JSON.parse(readFileSync(new URL('data/semantic/studio-catalog.json',root),'utf8')));
const json = (value: unknown) => JSON.parse(JSON.stringify(value));
const context = vm.createContext({ performance, TextEncoder, crypto: webcrypto });
function script(path: string) { vm.runInContext(readFileSync(new URL(path,root),'utf8'),context,{filename:path}); }
for (const name of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph']) script('yworks_edge_router_lab/'+name+'.js');
for (const {path} of JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json',import.meta.url),'utf8')).files) script(path);
for (const name of ['studio-semantic','studio-documents']) script('yworks_edge_router_lab/'+name+'.js');
const D=context.ArchCanvasSummaryDocuments, N=context.ArchCanvasSemanticView, E=context.SemanticEngine;
const hash=(value: Uint8Array|string)=>createHash('sha256').update(value).digest('hex');
const fileFetch = async (url: string|URL|Request, options?: RequestInit) => {
  options?.signal?.throwIfAborted();
  assert.ok(typeof url==='string' && url.startsWith('/preview/data/semantic/'));
  const data=readFileSync(new URL(url.slice('/preview/'.length),root));
  return new Response(data,{headers:{'Content-Length':String(data.length)}});
};

test('complete catalog assets are portable formal files, pinned independently of source paths', async t=>{
  const calls: string[]=[];
  t.mock.method(globalThis,'fetch',async (url: string, options?: RequestInit)=>{calls.push(url);return fileFetch(url,options);});
  assert.deepEqual(await loadSummaryCatalog(),catalog);
  assert.equal(calls.length,1,'catalog metadata must not eagerly load model IR');
  assert.equal(catalog.models.length,43);
  assert.equal(catalog.models.filter(m=>!summaryCatalogBlockReason(m)).length,43);
  const manifest=JSON.parse(readFileSync(new URL('../../docs/summary-catalog-assets-manifest-20261028.json',import.meta.url),'utf8'));
  assert.equal(manifest.files.length,45);
  for(const asset of manifest.files){
    const data=readFileSync(new URL(asset.path,root));assert.equal(data.length,asset.bytes);assert.equal(hash(data),asset.sha256);
  }
  for(const model of catalog.models){
    const ir=JSON.parse(readFileSync(new URL('data/semantic/'+model.ir.path,root),'utf8'));
    assert.equal(ir.ir_digest,model.digest);assert.equal(ir.nodes.length,model.nodes);assert.equal(ir.edges.length,model.edges);E.validate(ir);
  }
});

for(const model of catalog.models.filter(m=>!summaryCatalogBlockReason(m)))test(`catalog ${model.title} opens with complete native accounting and portable document restore`,async t=>{
  t.mock.method(globalThis,'fetch',fileFetch);
  const payload=await loadSummaryCatalogModel(model), before=JSON.stringify(payload), document=await D.read(payload);
  const result=N.prepare({task:'generic-build',ir:document.parsed.ir,options:{budgetMs:50,refineCrossings:false,refinePlacement:false,refineChannels:false,refineFlow:false}});
  assert.equal(N.accepts(result.graph,result.validation),true);assert.equal(JSON.stringify(payload),before);
  assert.equal(result.graph.generic.ir.nodes.length,model.nodes);assert.equal(result.graph.generic.ir.edges.length,model.edges);
  assert.equal(result.graph.generic.ir.ir_digest,model.digest);assert.deepEqual(json(result.graph.generic.ir),json(document.parsed.ir));
  assert.deepEqual(json((await D.restore(json(document.record))).parsed.ir),json(document.parsed.ir));
  assert.equal(D.attach(result.graph,document.record).sourceAdapter,undefined);
  assert.equal(result.graph.importedDocument.sourceVerified,false);assert.equal(result.graph.importedDocument.modelExecuted,false);
  assert.equal(result.graph.nativeRouting.complete,result.graph.nativeRouting.pending===0&&result.graph.nativeRouting.failed===0);
});

test('entries beyond the explicit catalog budgets refuse before fetching',async t=>{
  let calls=0;t.mock.method(globalThis,'fetch',async()=>{calls++;throw Error('must not fetch');});
  for(const patch of [{nodes:4001},{edges:5001},{ir:{...catalog.models[0].ir,bytes:16000001}}])await assert.rejects(()=>loadSummaryCatalogModel({...catalog.models[0],...patch}),/预算/);
  assert.equal(calls,0);
});

test('catalog rejects traversal, external URLs, duplicate identities and altered budgets',()=>{
  for(const change of [
    (v:any)=>v.models[0].ir.path='../secrets.json',
    (v:any)=>v.models[0].ir.path='https://example.invalid/x.json',
    (v:any)=>v.models[0].ir.path='%2e%2e/secrets.json',
    (v:any)=>v.models.push(v.models[0]),
    (v:any)=>v.models[0].nodes=-1,
    (v:any)=>v.models[0].ir.sha256='forged',
    (v:any)=>v.limits.nodes=1000000,
  ]){const bad=json(catalog);bad.limits={...SUMMARY_CATALOG_LIMITS};change(bad);assert.throws(()=>parseSummaryCatalog(bad));}
});

test('asset byte tampering, mismatched semantic identity and streaming size overflow fail closed',async t=>{
  const model=catalog.models.find(m=>!summaryCatalogBlockReason(m))!;
  const bytes=readFileSync(new URL('data/semantic/'+model.ir.path,root));
  const altered=Buffer.from(bytes);altered[altered.length-1]^=1;
  const mock=t.mock.method(globalThis,'fetch',async()=>new Response(altered));
  await assert.rejects(()=>loadSummaryCatalogModel(model),/摘要/);
  mock.mock.mockImplementation(fileFetch);
  await assert.rejects(()=>loadSummaryCatalogModel({...model,digest:'a'.repeat(64)}),/身份或计数/);
  mock.mock.mockImplementation(async()=>new Response(new ReadableStream({start(c){c.enqueue(new Uint8Array(model.ir.bytes));c.enqueue(new Uint8Array(1));c.close();}})));
  await assert.rejects(()=>loadSummaryCatalogModel(model),/读取预算/);
});

test('presentation state is preserved and must bind to the exact IR; cancellation never imports',async t=>{
  const model=catalog.models.find(m=>!summaryCatalogBlockReason(m))!;
  const state={view:'publication',mode:'source',paperGranularity:'stages',open:[]};
  const profile={schema:'semantic-presentation/1',ir_digest:model.digest,revision:'reviewed-state',default_state:state};
  let encoded=JSON.stringify(profile);
  const presentation=()=>({path:'presentations/test.json',bytes:Buffer.byteLength(encoded),sha256:hash(encoded)});
  const mock=t.mock.method(globalThis,'fetch',async(url: string, options?: RequestInit)=>url.endsWith('/test.json')?new Response(encoded):fileFetch(url,options));
  const document=await loadSummaryCatalogModel({...model,presentation:presentation()});
  assert.deepEqual(document.state,state);assert.equal((await D.read(document)).parsed.state.paperGranularity,'stages');
  profile.ir_digest='b'.repeat(64);encoded=JSON.stringify(profile);
  await assert.rejects(()=>loadSummaryCatalogModel({...model,presentation:presentation()}),/展示配置/);
  const abort=new AbortController();abort.abort();mock.mock.mockImplementation(fileFetch);
  await assert.rejects(()=>loadSummaryCatalogModel(model,abort.signal),{name:'AbortError'});
});
