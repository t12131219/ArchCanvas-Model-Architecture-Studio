import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const base=new URL('../public/preview/',import.meta.url),context=vm.createContext({performance});
function script(path:string){vm.runInContext(readFileSync(new URL(path,base),'utf8'),context,{filename:path});}
for(const name of ['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph'])script('yworks_edge_router_lab/'+name+'.js');
for(const row of JSON.parse(readFileSync(new URL('../../docs/summary-native-view-manifest-20261028.json',import.meta.url),'utf8')).files)script(row.path);
for(const name of ['studio-adaptive','studio-semantic'])script('yworks_edge_router_lab/'+name+'.js');
const N=context.ArchCanvasSemanticView,G=context.SummaryNativeSemantic,V=context.ArchCanvasAdaptiveView,A=context.SemanticAdaptiveFrontier;
const copy=(v:any)=>JSON.parse(JSON.stringify(v)),options={budgetMs:4000,refineCrossings:false,refinePlacement:false,refineChannels:false,refineFlow:false};
const catalog=JSON.parse(readFileSync(new URL('data/semantic/studio-catalog.json',base),'utf8'));
const irFor=(title:string)=>JSON.parse(readFileSync(new URL('data/semantic/'+catalog.models.find((m:any)=>m.title===title).ir.path,base),'utf8'));
const ir=irFor('SameSource'),state={paperMedium:'canvas',paperAuto:true,paperGranularity:'roles'};
function check(result:any){
 assert.equal(result.ok,true);assert.equal(result.validation.source.ok,true);assert.equal(N.accepts(result.graph,result.validation),true);
 const graph=result.graph;
 for(const [ledger,all]of [[graph.generic.receipts.node_accounting,graph.generic.ir.nodes],[graph.generic.receipts.edge_accounting,graph.generic.ir.edges]]){
  const ids=Object.values(ledger).flat() as string[];assert.equal(new Set(ids).size,ids.length);assert.deepEqual(ids.slice().sort(),copy(all.map((n:any)=>n.id)).sort());
 }
 return result;
}
const build=(value=ir,extra:any={})=>check(N.prepare({task:'generic-build',ir:value,state,options,...extra}));
const patch=(result:any,value:any,opts=options)=>check(N.prepare({task:'frontier',graph:result.graph,transition:{type:'semantic',patch:value},options:opts}));
const baseline=build(),automatic=patch(baseline,{paperAdaptive:true,paperAdaptivePolicy:'structure'});

test('native measured Summary selection gains exact relationships without changing canonical facts or original requests',()=>{
 const report=automatic.graph.nativeAdaptive;
 assert.equal(baseline.graph.nodes.length,11);assert.equal(automatic.graph.nodes.length,17);
 assert.ok(report.attempts.some((a:any)=>a.accepted&&a.gain>0&&a.opportunity.kind==='roles'));
 assert.ok(report.attempts.length<=3);assert.ok(report.preflights.length<=36);
 assert.deepEqual(copy(automatic.graph.generic.ir),ir);
 assert.deepEqual(copy(automatic.graph.generic.state.nativeAdaptiveBase),{paperRoleDetails:[],paperRolePaths:[],paperExpressionDetails:[]});
 assert.equal(report.selected.route_failures,0);assert.equal(report.selected.unplaced_labels,0);
 const before=A.evidence(ir,V.measured(baseline)),after=A.evidence(ir,V.measured(automatic));
 for(const id of before.goals.keys())assert.ok(after.goals.has(id),id);
 for(const id of before.boundaries)assert.ok(after.boundaries.has(id),id);
 assert.ok(after.goals.size>before.goals.size);
 assert.deepEqual(copy(A.metrics(V.measured(automatic))),copy(report.selected));
});

test('disabled requests, print, manual/source units and other granularities never enter automatic selection',()=>{
 assert.equal(baseline.graph.nativeAdaptive,undefined);
 for(const extra of [{paperAdaptive:false},{paperAuto:false},{paperMedium:'print'},{paperGranularity:'modules'},{paperCanonical:true,paperAuto:false}]){
  const result=build(ir,{state:{...state,paperAdaptive:true,...extra}});assert.equal(result.graph.nativeAdaptive,undefined);
 }
 const returned=patch(automatic,{paperAdaptive:false});
 assert.deepEqual(copy(G.layoutSnapshot(returned.graph).nodes),copy(G.layoutSnapshot(baseline.graph).nodes));
 assert.deepEqual(copy(G.layoutSnapshot(returned.graph).edges),copy(G.layoutSnapshot(baseline.graph).edges));
 assert.equal(returned.graph.generic.state.nativeAdaptiveBase,null);
});

test('JSON reopen restores effective native cut, camera-independent geometry and requests without trusting a saved receipt',()=>{
 const document=copy(G.document(automatic.graph));document.nativeAdaptive={requested:true,accepted:true,forged:true};
 const read=G.read(document),reopened=check(N.prepare({task:'generic-build',...read,options}));
 assert.deepEqual(copy(G.layoutSnapshot(reopened.graph)),copy(G.layoutSnapshot(automatic.graph)));
 assert.deepEqual(copy(reopened.graph.generic.ir),ir);assert.equal(reopened.graph.nativeAdaptive.restored,true);
 assert.equal(reopened.graph.nativeAdaptive.forged,undefined);
 const disabled=patch(reopened,{paperAdaptive:false});assert.equal(disabled.graph.nodes.length,11);
 const reenabled=patch(disabled,{paperAdaptive:true,paperAdaptivePolicy:'structure'});
 assert.deepEqual(copy(reenabled.graph.nodes),copy(automatic.graph.nodes));
 assert.deepEqual(copy(reenabled.graph.edges),copy(automatic.graph.edges));
 const forged=copy(document);forged.nativeLayout.edges[0].binding.target_port='forged';
 assert.throws(()=>N.prepare({task:'generic-build',...G.read(forged),options}));
});

test('manual role edits materialize selected automatic details and disable replanning',()=>{
 const roles=automatic.graph.generic.state.paperRoleDetails;assert.ok(roles.length);
 const manual=patch(automatic,{paperRolePaths:[]});
 assert.equal(manual.graph.generic.state.paperAdaptive,false);assert.equal(manual.graph.generic.state.nativeAdaptiveBase,null);
 assert.deepEqual(copy(manual.graph.generic.state.paperRoleDetails),copy(roles));assert.equal(manual.graph.nodes.length,17);
 const collapsed=patch(automatic,{paperRoleDetails:[],paperRolePaths:[]});assert.equal(collapsed.graph.nodes.length,11);assert.equal(collapsed.graph.generic.state.paperAdaptive,false);
});

test('policy changes replan from original requests; F0/F1 and manual expansion cannot reuse stale automatic bases',()=>{
 const changed=patch(automatic,{paperAdaptivePolicy:'detail'});assert.equal(changed.graph.nativeAdaptive.policy,'detail');
 assert.ok(changed.graph.nativeAdaptive.attempts.length>0);
 const f0=check(N.prepare({task:'frontier',graph:automatic.graph,transition:{type:'preset',preset:'overview'},options}));
 assert.equal(f0.graph.generic.state.paperAdaptive,false);assert.equal(f0.graph.generic.state.nativeAdaptiveBase,undefined);
 const f1=check(N.prepare({task:'frontier',graph:f0.graph,transition:{type:'preset',preset:'detail'},options}));
 assert.equal(f1.graph.generic.state.nativeAdaptiveBase,undefined);
 const source=check(N.prepare({task:'frontier',graph:automatic.graph,transition:{type:'all',expanded:true},options}));
 assert.equal(source.graph.generic.state.paperAdaptive,false);assert.equal(source.graph.nodes.length,ir.nodes.length);
});

test('missing actual operand paths reject claimed gain even when original semantic receipts remain',()=>{
 const before=V.measured(baseline),complete=V.measured(automatic),proof=context.SemanticExpressionGoals.canonicalPaths(ir,complete.prepared.routes);
 const gained=[...A.evidence(ir,complete).goals.values()].filter((g:any)=>!A.evidence(ir,before).goals.has(g.id));assert.ok(gained.length);
 const target=gained[0].node,incoming=ir.edges.filter((e:any)=>e.target===target&&['data','alias','interface-binding'].includes(e.kind));assert.ok(incoming.some((e:any)=>proof.exact(e.id)));
 const broken=copy(automatic.graph);for(const edge of broken.edges)if(incoming.some((e:any)=>edge.binding.id===e.id||edge.binding.originals?.includes(e.id)))edge.pendingRouting=true;
 const measured=V.measured({...automatic,graph:broken});assert.ok(A.evidence(ir,measured).goals.size<A.evidence(ir,complete).goals.size);
 assert.equal(A.assess(ir,before,measured).accepted,false);
});

test('truncated hidden captions, out-of-bounds glyph text and real lane conflicts cannot be promoted to measured gain',()=>{
 const before=V.measured(baseline),complete=V.measured(automatic),node=automatic.graph.nodes.find((n:any)=>!n.expanded&&!n.modelHeading);
 const hidden=copy(automatic.graph);hidden.nodes.find((n:any)=>n.id===node.id).semantic.paper.captions.push('never printed');
 const measured=V.measured({...automatic,graph:hidden});assert.ok(!measured.graph.nodes.find((n:any)=>n.id===node.id).paper.captions.includes('never printed'));
 const clipped=copy(automatic.graph);clipped.nodes.find((n:any)=>n.id===node.id).html+='<text x="90000" y="20" font-size="12">clipped</text>';
 const invalid=V.measured({...automatic,graph:clipped});assert.ok(invalid.prepared.quality.unplaced_port_labels.length>0);assert.equal(A.assess(ir,before,invalid).accepted,false);
 const crossed=copy(automatic.graph);crossed.edges[1].route=copy(crossed.edges[0].route);
 const conflict=V.measured({...automatic,graph:crossed});assert.ok(conflict.prepared.quality.route_failures.length>0||conflict.prepared.quality.line_geometry.overlapping_paths.length>0);
 assert.equal(A.assess(ir,before,conflict).accepted,false);assert.equal(complete.prepared.quality.issues.length,0);
});

test('routing budget exhaustion keeps candidates rejected and source evidence complete',()=>{
 const pending=build(ir,{options:{...options,budgetMs:0}}),result=patch(pending,{paperAdaptive:true}, {...options,budgetMs:0});
 assert.ok(result.graph.nativeRouting.pending>0);assert.ok(result.graph.nativeAdaptive.attempts.every((a:any)=>!a.accepted));
 assert.deepEqual(copy(result.graph.generic.ir),ir);
});

test('unknown, broken and control cases retain complete accounting and original boundaries',()=>{
 for(const title of ['UnknownFusion','BrokenCell','ConditionalResidual','LoopWithBoundary']){
  const value=irFor(title),before=build(value),after=patch(before,{paperAdaptive:true,paperAdaptivePolicy:'structure'});
  assert.deepEqual(copy(after.graph.generic.ir),value);
  const old=A.evidence(value,V.measured(before)),current=A.evidence(value,V.measured(after));
  for(const id of old.boundaries)assert.ok(current.boundaries.has(id),title+' '+id);
  assert.ok(after.graph.nativeAdaptive.attempts.length<=3);
 }
});

test('invalid automatic flags and externally supplied private bases refuse without mutating the current graph',()=>{
 const before=JSON.stringify(automatic.graph);
 for(const value of [{paperAdaptive:'true'},{paperAdaptive:null},{paperAdaptivePolicy:'family'},{nativeAdaptiveBase:{paperRoleDetails:['forged']}}]){
  assert.throws(()=>patch(automatic,value));assert.equal(JSON.stringify(automatic.graph),before);
 }
});

test('Studio alias overlays participate in printed evidence and cannot fulfill the hidden original title',()=>{
 const graph=copy(automatic.graph),target=graph.nodes.find((n:any)=>!n.expanded&&!n.modelHeading),alias='一个被用户修改且很长的显示名称';
 graph.studioPresentation={version:1,nodes:{[target.id]:{alias}},edges:{},annotations:{},legend:[],page:{}};
 const result=V.measured({...automatic,graph}),printed=result.graph.nodes.find((n:any)=>n.id===target.id);
 assert.equal(printed.paper.lines[0],alias);assert.ok(result.prepared.quality.min_canvas_font_px<12);
 const changed=patch({...automatic,graph},{paperAdaptivePolicy:'detail'});
 assert.equal(changed.graph.studioPresentation.nodes[target.id].alias,alias);
 assert.ok(changed.graph.nativeAdaptive.attempts.every((attempt:any)=>!attempt.accepted));
});


test('edited-wrapper restoration discards supplied adaptive receipts after native validation',()=>{
 const graph=copy(automatic.graph);graph.nativeAdaptive={accepted:true,forged:true,attempts:[{accepted:true,gain:999}]};
 assert.equal(context.SummaryEngine.validateView(graph).source.ok,true);V.restored(graph);
 assert.equal(graph.nativeAdaptive.restored,true);assert.equal(graph.nativeAdaptive.forged,undefined);assert.equal(graph.nativeAdaptive.attempts,undefined);
 assert.deepEqual(copy(graph.nativeAdaptive.selected),copy(A.metrics(V.measured({...automatic,graph}))));
 const app=readFileSync(new URL('../public/preview/yworks_edge_router_lab/app.js',import.meta.url),'utf8');
 assert.match(app,/N\.accepts\(nextGraph,validation\)[^}]+ArchCanvasAdaptiveView\?\.restored\(nextGraph\)/);
});
