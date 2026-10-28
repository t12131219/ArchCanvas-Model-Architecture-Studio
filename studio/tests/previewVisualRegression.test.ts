import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
const execute = promisify(execFile);
import { fileURLToPath } from 'node:url';

const project = fileURLToPath(new URL('../../', import.meta.url));
const context = vm.createContext({ TextEncoder, TextDecoder });
for (const name of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph','source-adapter','source-controls','frontier-task'])
  vm.runInContext(readFileSync(new URL(`../public/preview/yworks_edge_router_lab/${name}.js`,import.meta.url),'utf8'),context);
const A=context.SummarySourceAdapter,F=context.SummaryRecursive,E=context.SummaryEngine,T=context.SummaryFrontierTask;
const plain=(v:any)=>JSON.parse(JSON.stringify(v));
async function analyze(source:string,entry:string) {
  return JSON.parse((await execute('python3',['-I','-S','-B','-c','import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_preview.analyze import analyze;print(json.dumps(analyze({"fixture.py":sys.argv[2]},sys.argv[3])))',project,source,entry],{encoding:'utf8',maxBuffer:4_000_000})).stdout);
}
function valid(g:any) {
  const v=E.validateView(g);
  assert.equal(v.source.ok,true,v.source.violations.join('; '));
  assert.equal(v.layout.ok,true,v.layout.violations.join('; '));
  assert.deepEqual(plain(v.edges.filter(([,v]:any)=>!v.ok)),[]);
  return g;
}
test('conditional alternatives keep independent display terminals in initial, mixed and full frontiers, including renamed/reordered holdouts',async()=>{
  const original=readFileSync(new URL('../../docs/evidence/visual-audit-20261017/inputs/transformed_mlp.py',import.meta.url),'utf8');
  const variants=[original,original.replaceAll('Wrapper','Envelope').replaceAll('MLP','Block').replaceAll('flag','choice').replace('a=self.left(x)\n        b=self.right(x)','b=self.right(x)\n        a=self.left(x)'),
    original.replaceAll('Wrapper','Triple').replace('self.fallback=nn.Identity()','self.fallback=nn.Identity()\n        self.third=MLP()').replace('c=a+b','c=a+b+self.third(x)')];
  for(const [i,source]of variants.entries()) {
    const bundle=await analyze(source,'fixture:'+['Wrapper','Envelope','Triple'][i]),before=JSON.stringify(bundle),sources=A.sources(bundle);
    let graph=valid(T.run(F.build(F.create(sources)),null,{}).graph);
    const region=graph.nodes.find((n:any)=>n.semantic?.sourceStructure===true||n.label==='待解析 · Module');assert.ok(region);
    graph=valid(T.run(graph,{type:'expand',ids:[region.id],expanded:true},{}).graph);
    graph=valid(T.run(graph,{type:'all',expanded:true},{}).graph);
    for(const e of graph.edges)for(const f of graph.edges)if(e!==f&&e.target===f.target&&e.contract.wire!==f.contract.wire)
      assert.ok(Math.hypot(e.route.at(-1).x-f.route.at(-1).x,e.route.at(-1).y-f.route.at(-1).y)>=9,'independent values never collapse onto a shared arrow terminal');
    F.remember(graph);const bindings=JSON.stringify(graph.edges.map((e:any)=>[e.id,e.source,e.target,e.binding]));
    const folded=valid(T.run(E.clone(graph),{type:'expand',ids:[region.id],expanded:false},{}).graph);
    const restored=valid(T.run(folded,{type:'expand',ids:[region.id],expanded:true},{}).graph);
    assert.equal(JSON.stringify(restored.edges.map((e:any)=>[e.id,e.source,e.target,e.binding])),bindings);
    assert.equal(JSON.stringify(bundle),before,'source corpus, IR and evidence remain unchanged');
  }
});
