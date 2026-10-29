import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { webcrypto } from 'node:crypto';
const base=new URL('../public/preview/',import.meta.url),ctx=vm.createContext({performance,TextEncoder,crypto:webcrypto});
const load=(path:string)=>vm.runInContext(readFileSync(new URL(path,base),'utf8'),ctx,{filename:path});
for(const n of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])load(`yworks_edge_router_lab/${n}.js`);
for(const row of JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json',import.meta.url),'utf8')).files)load(row.path);
for(const n of ['studio-semantic','studio-documents','studio-authoring'])load(`yworks_edge_router_lab/${n}.js`);
const G=ctx.SummaryNativeSemantic,N=ctx.ArchCanvasSemanticView,R=ctx.SummarySourceRuntime;
const copy=(v:any)=>v===undefined?undefined:JSON.parse(JSON.stringify(v));
const equal=(a:any,b:any,message='objects differ')=>assert.ok(G.stable(a)===G.stable(b),message);
const catalog=JSON.parse(readFileSync(new URL('data/semantic/studio-catalog.json',base),'utf8'));
const read=(id:string)=>JSON.parse(readFileSync(new URL('data/semantic/'+catalog.models.find((m:any)=>m.id===id||m.title===id).ir.path,base),'utf8'));
const ir=read('0216717d966327f4'),state=N.state('overview');
const encode=ir.nodes.find((n:any)=>n.label==='self.encode').id,decode=ir.nodes.find((n:any)=>n.label==='self.decode').id;
const build=(cuts:any[],value=ir,extra={})=>G.build(value,{...state,...extra,moduleCuts:cuts});
const plain=G.build(ir,state),canonical=new Map(ir.nodes.map((n:any)=>[n.id,n]));
function inside(id:string,owner:string){while(id){if(id===owner)return true;id=(canonical.get(id)as any)?.parent;}return false;}
function check(graph:any,value=ir){
 const cut=G.expected(graph),valid=G.validate(graph,true);assert.equal(valid.ok,true,valid.violations.join('; '));equal(copy(graph.generic.ir),value);
 for(const [ledger,all]of [[cut.node_accounting,value.nodes],[cut.edge_accounting,value.edges]]){
  const ids=Object.values(ledger).flat()as string[];assert.equal(ids.length,all.length);assert.equal(new Set(ids).size,all.length);equal(ids.slice().sort(),all.map((n:any)=>n.id).sort());
 }
 const ids=new Set(graph.nodes.map((n:any)=>n.id));for(const e of graph.edges){assert.ok(ids.has(e.source));assert.ok(ids.has(e.target));}return graph;
}
test('all intermediate cuts coexist with an unchanged sibling and exact outer dependencies',()=>{
 const before=plain.nodes.filter((n:any)=>inside(n.id,decode));
 const rawEdges=new Map(ir.edges.map((e:any)=>[e.id,e]));
 const provenance=(e:any):string[]=>[e.id,...(e.originals||[]),...(e.bundle_members||[]).flatMap(provenance)];
 const outer=G.expected(plain).edges.filter((e:any)=>provenance(e).every(id=>{const raw=rawEdges.get(id)as any;return !raw||!inside(raw.source,encode)&&!inside(raw.target,encode);}));
 for(const level of R.levels.filter((v:string)=>v!=='source')){
  const graph=check(build([{id:encode,level}]));equal(copy(graph.nodes.filter((n:any)=>inside(n.id,decode)).map((n:any)=>[n.id,n.expanded,n.semantic])),copy(before.map((n:any)=>[n.id,n.expanded,n.semantic])),level);
  const edges=new Map(G.expected(graph).edges.map((e:any)=>[e.id,e]));for(const e of outer)equal(copy(edges.get(e.id)),copy(e),level+' '+e.id);
 }
});
test('source depths reach every real encoder unit while decoder stays at F0',()=>{
 const scope=ir.nodes.filter((n:any)=>inside(n.id,encode)),max=R.moduleIndex(ir).find((n:any)=>n.id===encode).maxDepth;let previous=0;
 for(const depth of [0,1,2,max]){const graph=check(build([{id:encode,level:'source',depth}])),shown=graph.nodes.filter((n:any)=>inside(n.id,encode));assert.ok(shown.length>=previous);previous=shown.length;if(depth===max)equal(shown.map((n:any)=>n.id).sort(),scope.map((n:any)=>n.id).sort());}
 assert.ok(scope.length>1000);
});
test('nested overrides use specificity and whole-model atoms reach all 3371 original facts and exact operands',()=>{
 const child=ir.nodes.find((n:any)=>n.label==='self_attn'&&inside(n.id,encode)).id,cuts=[{id:encode,level:'source'},{id:child,level:'f0'},{id:decode,level:'f1'}];
 const graph=check(build(cuts));assert.ok(graph.nodes.filter((n:any)=>inside(n.id,child)).length<ir.nodes.filter((n:any)=>inside(n.id,child)).length);
 equal(copy(G.layoutSnapshot(check(build(cuts.slice().reverse())))),copy(G.layoutSnapshot(graph)));
 const all=check(build([{id:ir.nodes.find((n:any)=>!n.parent).id,level:'source'}]));assert.equal(all.nodes.length,ir.nodes.length);assert.equal(all.edges.length,ir.edges.length);
 for(const e of G.expected(all).edges){const raw=ir.edges.find((v:any)=>v.id===e.id);for(const key of ['source','target','source_port','target_port','kind','condition','evidence'])equal(copy(e[key]??null),copy(raw[key]??null));}
});
test('module commands, reset, preset and back keep independent history and reject forged scopes',()=>{
 const small=read('MultilayerPerceptron · mlp'),graph=G.build(small,state),target=small.nodes.find((n:any)=>n.kind==='composite').id;
 const command=(request:any)=>N.prepare({task:'frontier',graph,transition:{type:'module',request},options:{budgetMs:0,refineCrossings:false,refinePlacement:false,refineChannels:false,refineFlow:false}}).graph;
 const before=JSON.stringify(graph),next=check(command({ids:[target],level:'source'}),small);assert.ok(JSON.stringify(graph)===before,'prior graph mutated');assert.equal(N.inspector(next).canBack,true);
 const back=G.operate(next,{kind:'back'});equal(copy(G.layoutSnapshot(back).nodes),copy(G.layoutSnapshot(graph).nodes));
 for(const op of [{kind:'frontier',action:'overview'},{kind:'all',open:true}])assert.equal(G.operate(next,op).generic.state.moduleCuts,undefined);
 for(const request of [{ids:['forged'],level:'source'},{ids:[target],level:'fake'},{ids:[target],level:'source',depth:-1},{ids:[target],level:'source',depth:NaN}])assert.throws(()=>command(request));
 for(const cuts of [[{id:target,level:'source',members:['forged']}],[{id:target,level:'source',open:'forged'}],[{id:target,level:'source'},{id:target,level:'f0'}]])assert.throws(()=>build(cuts,small));
});
test('JSON reopen recompiles mixed receipts; altered bindings and accounting refuse',()=>{
 const graph=check(build([{id:encode,level:'source',depth:2},{id:decode,level:'f1'}])),doc=copy(G.document(graph)),read=G.read(doc),restored=check(G.build(read.ir,read.state,{...read}));equal(copy(G.expected(restored).publication.mixed),copy(G.expected(graph).publication.mixed));
 const forged=copy(graph);forged.edges[0].binding.target_port='forged';assert.equal(G.validate(forged,true).ok,false);forged.generic.receipts.node_accounting.visible.pop();assert.equal(G.validate(forged,true).ok,false);
});
test('scoped toggles preserve mixed siblings through collapse and reopen',()=>{
 const graph=check(build([{id:encode,level:'f1'},{id:decode,level:'f0'}])),target=graph.nodes.find((n:any)=>n.expanded&&inside(n.id,encode)&&n.id!==encode);assert.ok(target);
 const collapsed=check(G.operate(graph,{kind:'toggle',id:target.id,force:false}));assert.ok(collapsed.nodes.length<graph.nodes.length);
 const reopened=check(G.operate(collapsed,{kind:'toggle',id:target.id,force:true}));equal(reopened.nodes.map((n:any)=>[n.id,n.expanded]),graph.nodes.map((n:any)=>[n.id,n.expanded]));
});
for(const model of catalog.models)test(`all-case canonical and intermediate accounting: ${model.title}`,()=>{
 const value=read(model.id),roots=value.nodes.filter((n:any)=>!n.parent&&n.kind==='composite'&&n.id!=='runtime-observations');
 const root=roots[0];assert.ok(root);
 const modes=value.runtime?.runs?.length?['source','merged','runtime']:['source'];
 for(const mode of modes)for(const level of ['f0','f1','overview','modules','stages','semantic','roles','detailed','source'])check(build([{id:root.id,level,...(level==='source'?{depth:2}:{})}],value,{mode}),value);
});

for(const model of catalog.models)test(`every registered source module can reach its own atoms: ${model.title}`,()=>{
 const value=read(model.id),by=new Map(value.nodes.map((n:any)=>[n.id,n])),children=new Map<string,string[]>();
 for(const n of value.nodes){const list=children.get(n.parent)||[];list.push(n.id);children.set(n.parent,list);}
 for(const module of R.moduleIndex(value)){
  let at=module.id,observed=false;while(at){if(at==='runtime-observations'||at.startsWith('runtime:'))observed=true;at=(by.get(at)as any)?.parent;}
  const scope=new Set<string>(),walk=(id:string)=>{scope.add(id);for(const c of children.get(id)||[])walk(c);};walk(module.id);
  const cut=G.project(value,{...state,mode:observed?'runtime':'source',moduleCuts:[{id:module.id,level:'source'}]});
  const shown=new Set(cut.nodes.map((n:any)=>n.id));
  // Runtime attachments can live below a source root in the canonical IR;
  // source mode intentionally excludes them. Their own scopes use runtime.
  const active=(id:string)=>{while(id){if(id==='runtime-observations'||id.startsWith('runtime:'))return observed;id=(by.get(id)as any)?.parent;}return true;};
  for(const id of [...scope].filter(active))assert.ok(shown.has(id),`${model.title}: ${module.label} failed to expose ${id}`);
  for(const [ledger,all]of [[cut.node_accounting,value.nodes],[cut.edge_accounting,value.edges]]){
   const ids=Object.values(ledger).flat()as string[];assert.equal(new Set(ids).size,all.length);assert.equal(ids.length,all.length);
  }
  const rawEdges=new Map(value.edges.map((e:any)=>[e.id,e]));
  for(const edge of cut.edges.filter((e:any)=>scope.has(e.canonical_source??e.source)&&scope.has(e.canonical_target??e.target))){
   const raw=rawEdges.get(edge.id)as any;if(raw){assert.equal(edge.source,raw.source);assert.equal(edge.target,raw.target);assert.equal(edge.source_port,raw.source_port);assert.equal(edge.target_port,raw.target_port);}
  }
 }
});

test('visual drafts survive latent endpoints, module changes and portable JSON without rewriting IR',()=>{
 const value=read('MultilayerPerceptron · mlp'),root=value.nodes.find((n:any)=>!n.parent).id;
 const graph=build([{id:root,level:'source'}],value),edge=graph.edges.find((e:any)=>e.source!==root&&e.target!==root);assert.ok(edge);
 const draft={...copy(edge),id:'visual-only-test',draft:true};delete draft.binding;delete draft.contract;graph.edges.push(draft);
 const hidden=G.operate(graph,{kind:'state',patch:{moduleCuts:[{id:root,level:'source',depth:0}]}});
 assert.equal(hidden.sourceDraftEdges.length,1);assert.equal(hidden.edges.some((e:any)=>e.id===draft.id),false);equal(hidden.generic.ir,value);
 const doc=copy(G.document(hidden)),saved=G.read(doc),restored=G.build(saved.ir,saved.state,saved);G.restore(restored,saved.nativeLayout);
 assert.equal(restored.sourceDraftEdges.length,1);
 const shown=G.operate(restored,{kind:'state',patch:{moduleCuts:[{id:root,level:'source'}]}});
 assert.ok(shown.edges.some((e:any)=>e.id===draft.id&&e.draft));assert.equal(shown.sourceDraftEdges.length,0);check(shown,value);
 const released=shown.edges.find((e:any)=>e.id===edge.id);released.draft=true;delete released.contract;released.stroke='#12ab34';
 const reapplied=G.operate(shown,{kind:'state',patch:{moduleCuts:[{id:root,level:'source'}]}});
 assert.equal(reapplied.edges.find((e:any)=>e.id===edge.id).draft,true);assert.equal(reapplied.edges.find((e:any)=>e.id===edge.id).stroke,'#12ab34');check(reapplied,value);
 // A visual deletion remains a visual operation; it cannot erase IR facts.
 shown.edges=shown.edges.filter((e:any)=>e.id!==edge.id);shown.sourceDraftOperations.push({kind:'remove-connection',id:edge.id,binding:copy(edge.binding)});
 const again=G.operate(shown,{kind:'state',patch:{moduleCuts:[{id:root,level:'source'}]}});assert.ok(!again.edges.some((e:any)=>e.id===edge.id));check(again,value);
});

test('authoring copy and edits retain live module depths, drop stale openings and remove erased scopes',async()=>{
 const W=ctx.ArchCanvasSummaryAuthoring,value=read('MultilayerPerceptron · mlp'),root=value.nodes.find((n:any)=>!n.parent).id;
 const before=build([{id:root,level:'source',depth:1,open:[root]}],value),saved=JSON.stringify(before);
 const begun=await W.begin(before),authored=W.attach(G.build(begun.parsed.ir,begun.parsed.state,{authoring:begun.parsed.authoring}),begun.record);
 assert.equal(authored.generic.state.moduleCuts[0].depth,1);assert.equal(authored.generic.state.moduleCuts[0].open,undefined);
 const changed=await W.apply(authored,{action:'edit',id:root,fields:{label:'Edited model'}});
 assert.equal(changed.parsed.state.moduleCuts[0].id,root);assert.equal(changed.parsed.state.moduleCuts[0].depth,1);
 assert.equal(changed.parsed.ir.authoring.edited,true);assert.equal(changed.parsed.ir.semantic_contracts.length,0);
 const erased=await W.apply(authored,{action:'erase',ids:[root]});assert.ok(!erased.parsed.state.moduleCuts?.length);
 assert.equal(JSON.stringify(before),saved);check(before,value);
});

test('source and CPU module overrides remain dormant in the other evidence mode and reject invented scopes',()=>{
 const value=read('BranchMLP'),source=value.nodes.find((n:any)=>!n.parent&&n.id!=='runtime-observations').id;
 const runtime=value.nodes.find((n:any)=>n.id==='runtime-observations').id;
 const cuts=[{id:source,level:'source'},{id:runtime,level:'source'}];
 for(const mode of ['source','runtime','merged']){
  const graph=check(build(cuts,value,{mode}),value),shown=graph.nodes.map((n:any)=>n.id),scopes=G.expected(graph).publication.mixed.scopes;
  assert.equal(graph.generic.state.moduleCuts.length,2);
  if(mode==='source'){assert.ok(!shown.includes(runtime));assert.ok(!scopes.some((s:any)=>s.id===runtime));}
  if(mode==='runtime'){assert.ok(!shown.includes(source));assert.ok(!scopes.some((s:any)=>s.id===source));}
 }
 assert.throws(()=>build([{id:'invented',level:'source'}],value,{mode:'merged'}));
 // Every bridge composite is sourced from an independently matched CPU call.
 const active=R.fullyExpandedIR(value,{mode:'merged'}),bridge=active.nodes.find((n:any)=>n.source_runtime);
 if(bridge){const graph=check(build([{id:bridge.id,level:'source'}],value,{mode:'merged'}),value);assert.ok(graph.nodes.some((n:any)=>n.id===bridge.id));}
});

for(const model of catalog.models)test(`all-case mixed worker preparation and route status: ${model.title}`,()=>{
 const value=read(model.id),modules=R.moduleIndex(value).filter((n:any)=>n.id!=='runtime-observations'&&!n.id.startsWith('runtime:'));
 const roots=value.nodes.filter((n:any)=>!n.parent&&n.kind==='composite'&&n.id!=='runtime-observations'),root=roots[0];
 const parents=new Map(value.nodes.map((n:any)=>[n.id,n.parent]));
 const within=(id:string,owner:string)=>{while(id){if(id===owner)return true;id=parents.get(id)as string;}return false;};
 const child=modules.find((n:any)=>n.id!==root.id),sibling=child&&modules.find((n:any)=>!within(n.id,child.id)&&!within(child.id,n.id));
 const cuts=[{id:root.id,level:'f0'},...(child?[{id:child.id,level:'source',depth:2}]:[]),...(sibling?[{id:sibling.id,level:'f1'}]:[])];
 const graph=build(cuts,value),result=N.prepare({task:'generic-route',graph,options:{budgetMs:30,refineCrossings:false,refinePlacement:false,refineChannels:false,refineFlow:false}});
 assert.equal(N.accepts(result.graph,result.validation),true,model.title);check(result.graph,value);
 const route=N.inspector(result.graph).routing;
 assert.equal(route.complete,!route.pending&&!route.failed);
 assert.equal(route.pending,result.graph.edges.filter((e:any)=>e.pendingRouting).length);
});

for(const model of catalog.models.filter((m:any)=>{const value=read(m.id);return !!value.runtime?.runs?.length;}))test(`recorded mixed scopes reopen in all evidence modes: ${model.title}`,()=>{
 const value=read(model.id),source=value.nodes.find((n:any)=>!n.parent&&n.id!=='runtime-observations').id;
 for(const mode of ['source','runtime','merged']){
  const scopes=[{id:source,level:'source',depth:2},...(mode==='runtime'?[{id:'runtime-observations',level:'source',depth:2}]:[])];
  const graph=build(scopes,value,{mode}),document=copy(G.document(graph)),saved=G.read(document);
  const restored=G.build(saved.ir,saved.state,saved);
  equal(copy(G.expected(restored).publication.mixed),copy(G.expected(graph).publication.mixed),model.title+' '+mode);
  G.restore(restored,saved.nativeLayout);check(restored,value);
  equal(copy(G.layoutSnapshot(restored)),copy(G.layoutSnapshot(graph)),model.title+' '+mode);
 }
});

test('explicit subtree depth replaces descendant overrides and preserves sibling cuts, source and prior history',()=>{
 const child=ir.nodes.find((n:any)=>n.label==='self_attn'&&inside(n.id,encode)).id;
 const graph=build([{id:encode,level:'source',depth:2},{id:child,level:'f0'},{id:decode,level:'f1'}]);
 const before=JSON.stringify(graph),options={budgetMs:0,refineCrossings:false,refinePlacement:false,refineChannels:false,refineFlow:false};
 const apply=(request:any)=>N.prepare({task:'frontier',graph,transition:{type:'module',request},options}).graph;
 const old=apply({ids:[encode],level:'source',depth:0});assert.ok(old.generic.state.moduleCuts.some((c:any)=>c.id===child),'existing callers retain specific overrides');
 for(const request of [{ids:[encode],level:'source',depth:0},{ids:[encode],level:'source',depth:2},{ids:[encode],level:'f1'},{ids:[encode],reset:true}]){
  const next=check(apply({...request,replaceDescendants:true}));
  assert.ok(!next.generic.state.moduleCuts.some((c:any)=>c.id===child));
  equal(copy(next.generic.state.moduleCuts.find((c:any)=>c.id===decode)),{id:decode,level:'f1'});
  if(request.depth===0)assert.equal(next.nodes.filter((n:any)=>inside(n.id,encode)).length,1);
  assert.equal(JSON.stringify(graph),before,'command mutated the preceding graph');
 }
 assert.throws(()=>apply({ids:[encode],level:'source',replaceDescendants:'yes'}),/范围/);
});
