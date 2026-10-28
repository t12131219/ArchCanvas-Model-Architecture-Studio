import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const app=readFileSync(new URL('../public/preview/yworks_edge_router_lab/app.js',import.meta.url),'utf8');
const fn=app.slice(app.indexOf('  async function arrangeSelection('),app.indexOf('  async function studioVisual('));
const base=[{id:'a',x:100,y:50,w:80,h:30,parent:'root'},{id:'b',x:300,y:150,w:120,h:50,parent:'root'},{id:'c',x:500,y:350,w:100,h:40,parent:'root'}];
function harness(nodes=base,pinned:string[]=[],reject=false){
  const operations:any[]=[];const notices:string[]=[];
  const c=vm.createContext({graph:{canvas:[2000,2000]},window:{ArchCanvasStudioPresentation:{state:()=>({nodes:Object.fromEntries(pinned.map(id=>[id,{pinned:true}]))})}},selectedLayoutNodes:()=>nodes,studioVisual:async(message:any)=>{if(reject)throw new Error('位置受到节点、容器或连接约束。');operations.push(...message.operations);},toast:(message:string)=>notices.push(message)});
  vm.runInContext(fn,c);return{run:(kind:string)=>c.arrangeSelection({kind}),operations,notices};
}
const examples=[['left','x',[100,100,100]],['hcenter','x',[310,290,300]],['right','x',[520,480,500]],['top','y',[50,50,50]],['vcenter','y',[205,195,200]],['bottom','y',[360,340,350]],['distribute-x','x',[100,280,500]],['distribute-y','y',[50,190,350]]] as const;
for(const[kind,axis,expected]of examples)test(`actual ${kind} action produces independently calculated coordinates`,async()=>{
  const h=harness();await h.run(kind);
  const results=base.map(n=>h.operations.find(op=>op.id===n.id)?.position[axis]??n[axis]);
  assert.deepEqual(results,expected);assert.ok(h.operations.every(op=>op.exact&&op.scope==='all-frontiers'));assert.equal(h.notices.length,1);
});
test('fixed anchor is retained and conflicting anchors, locked distribution and different scopes are rejected',async()=>{
  const h=harness(base,['b']);await h.run('left');assert.ok(h.operations.every(op=>op.id!=='b'));assert.ok(h.operations.every(op=>op.position.x===300));
  await assert.rejects(harness(base,['a','b']).run('left'),/基准不同/);
  await assert.rejects(harness(base,['b']).run('distribute-y'),/解锁/);
  await assert.rejects(harness(base.map(n=>({...n,parent:n.id==='a'?'other':'root'}))).run('top'),/同一容器/);
  await assert.rejects(harness(base.slice(0,2)).run('distribute-x'),/至少 3/);
});
test('no-op and rejected geometry have distinct actionable feedback',async()=>{
  const aligned=harness(base.map(n=>({...n,x:100})));await aligned.run('left');assert.equal(aligned.operations.length,0);assert.match(aligned.notices[0],/无需调整/);
  const rejected=harness(base,[],true);await assert.rejects(rejected.run('left'),/未应用排列.*原位置已保留/);assert.equal(rejected.operations.length,0);assert.deepEqual(rejected.notices,[]);
});
