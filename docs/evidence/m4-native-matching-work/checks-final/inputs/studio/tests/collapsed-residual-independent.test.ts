import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import type { CanvasDocument, Scene } from '../src/core/types.ts';
import type { RouteRequest } from '../src/core/orthogonalRouter.ts';
// Product calls produce observations only. The literal paths, geometry,
// candidate graph and protected metrics below belong to the separate oracle.
import { buildScene, buildExportScene, renderSvg } from '../src/core/index.ts';
import { createOrthogonalRouter } from '../src/core/orthogonalRouter.ts';
import { assertEndpoints, assertRefinement, assertSvg, intrusions, pair, penetrates, points, stats } from '../../docs/evidence/m4-collapsed-residual-work/acceptance/oracle.ts';
import { addProtectedRoute, genericDocument, literalNode, literalPort, literalRoutingCase } from '../../docs/evidence/m4-collapsed-residual-work/acceptance/fixtures.ts';

const root=new URL('../../',import.meta.url), evidence=new URL('../../docs/evidence/m4-collapsed-residual-work/acceptance/baseline/',import.meta.url);
type Binding={path:string;bytes:number;sha256:string};
type FrozenRecord={key:string;files:Record<string,{source:Binding;copy:Binding}>};
const capture=JSON.parse(readFileSync(new URL('capture.json',evidence),'utf8')) as {records:FrozenRecord[];inputsBefore:Binding[];inputsAfter:Binding[];inputsUnchanged:boolean;literalCnn:{oldPath:string;oldLength:number;oldBends:number;candidatePath:string;candidateLength:number;candidateBends:number}};
const serialized=<T>(value:T):T=>JSON.parse(JSON.stringify(value));
const digest=(bytes:Buffer)=>createHash('sha256').update(bytes).digest('hex');
const file=(record:FrozenRecord,key:string)=>readFileSync(new URL(record.files[key].copy.path,root));
const beforeFor=(record:FrozenRecord)=>JSON.parse(file(record,'scene.json').toString()) as Scene;
const canvasFor=(record:FrozenRecord)=>JSON.parse(file(record,'canvas.json').toString()) as CanvasDocument;
const cnn=capture.records.find(record=>record.key==='residual_cnn-level0-paper-180')!;
function observe(fixture:ReturnType<typeof literalRoutingCase>) {
  const untouched=JSON.stringify(fixture), routes=createOrthogonalRouter(fixture.scene.nodes).batch(fixture.requests as RouteRequest[]);
  assert.equal(JSON.stringify(fixture),untouched,'router mutated literal nodes/ports/requests');
  const after=structuredClone(fixture.scene);
  after.edges.forEach((edge,index)=>{edge.path=routes[index].path;});
  assert.deepEqual(routes,createOrthogonalRouter(fixture.scene.nodes).batch(fixture.requests as RouteRequest[]),'nondeterministic batch');
  return after;
}
function coverage(document:CanvasDocument,scene:Scene) {
  assert.deepEqual([...scene.hiddenEdges,...scene.edges.flatMap(edge=>edge.canonicalEdgeIds)].sort(),document.architecture.edges.map(edge=>edge.id).sort(),'canonical edges lost, duplicated or hidden');
}

test('independent residual baseline freezes all nine authored frontiers and actual public route bytes',()=>{
  assert.equal(capture.records.length,9);assert.equal(capture.inputsUnchanged,true);assert.deepEqual(capture.inputsBefore,capture.inputsAfter);
  for(const record of capture.records)for(const value of Object.values(record.files)) {
    const copy=readFileSync(new URL(value.copy.path,root)), original=readFileSync(new URL(value.source.path,root));
    assert.equal(copy.length,value.copy.bytes);assert.equal(digest(copy),value.copy.sha256);assert.deepEqual(copy,original);
  }
  const edge=beforeFor(cnn).edges.find(edge=>edge.id==='edge:9')!;
  assert.equal(edge.path,'M 209.3 316 V 329 H 326 V 341 H 209.3 V 354');
  assert.ok(Math.abs(stats(edge.path).length-271.4)<1e-9);assert.equal(stats(edge.path).bends,4);
  assert.equal(capture.literalCnn.candidatePath,'M 209.3 316 V 354');
  assert.deepEqual(stats(capture.literalCnn.candidatePath),{length:38,bends:0});
  const literal=beforeFor(cnn);literal.edges.find(edge=>edge.id==='edge:9')!.path=capture.literalCnn.candidatePath;
  assertRefinement(beforeFor(cnn),literal);assert.deepEqual(intrusions(literal),[]);
});

test('independent route parser and protected pair oracle expose split-vertex crossings and interval union',()=>{
  for(const bad of ['M 0 0 L 10 10','M 0 0 V','M 0 0 V NaN','M 0 0 H 1 junk','M 0 0 H 1 M 1 1 V 2','m 0 0 v 1','M 0 0 H 1e999'])assert.throws(()=>points(bad));
  const unsplit=pair('M 0 75 H 100','M 60 65 V 85'),split=pair('M 0 75 H 60 H 100','M 60 65 V 75 V 85');
  assert.deepEqual(split,unsplit);assert.equal(split.crossings.length,1);
  assert.equal(pair('M 50 50 V 75 H 70 V 100','M -20 75 H 50 V 80 H -20').crossings.length,1,'actual bend contact must not vanish behind strict segment interiors');
  assert.equal(pair('M 0 0 H 20 H 0 H 20','M 5 0 H 15').overlapLength,10,'retrace cannot double-count or conceal overlap');
  assert.equal(pair('M 0 0 H 10','M 10 -10 V 10').crossings.length,0,'whole-edge endpoint touch is not a strict crossing');
});

test('independent oracle rejects coherent branch, role/style, port, body/header and backplate corruptions',()=>{
  const before=beforeFor(cnn);
  const rejects=(change:(scene:Scene)=>void)=>{const after=structuredClone(before);change(after);assert.throws(()=>assertRefinement(before,after,renderSvg(after)));};
  rejects(scene=>{scene.edges.find(edge=>edge.id==='edge:9')!.role='data';});
  rejects(scene=>{scene.edges.find(edge=>edge.id==='edge:9')!.stroke='#000000';});
  rejects(scene=>{const edge=scene.edges.find(edge=>edge.id==='edge:9')!;edge.canonicalEdgeIds.push('edge:2');});
  rejects(scene=>{const removed=scene.edges.pop()!;scene.hiddenEdges.push(...removed.canonicalEdgeIds);});
  rejects(scene=>{scene.edges.find(edge=>edge.id==='edge:9')!.target.portId='invented-proxy-port';});
  rejects(scene=>{const edge=scene.edges.find(edge=>edge.id==='edge:9')!;const port=scene.nodes.find(node=>node.id===edge.targetId)!.ports.find(port=>port.canonicalEdgeIds.includes(edge.id))!;port.x+=4;edge.path='M 209.3 316 V 329 H 213.3 V 354';});
  rejects(scene=>{scene.edges.find(edge=>edge.id==='edge:9')!.path='M 209.3 316 V 280 H 350 V 354 H 209.3';});
  const published=renderSvg(before).replace('data-edge-id="edge:9"','data-edge-id="concealed"');assert.throws(()=>assertSvg(before,published));
  const repeat=literalNode('independent-stack',30,60,18,15,{repeat:{count:3,sharing:'shared'}});
  assert.equal(penetrates('M 50 50 V 100',repeat),false,'front card is clear in the backplate counterexample');
  const f=literalRoutingCase();f.scene.nodes.push(repeat);const bad=structuredClone(f.scene);bad.edges[0].path='M 50 50 V 100';
  assert.ok(intrusions(bad).some(hit=>hit.includes('backplate')));assert.throws(()=>assertRefinement(f.scene,bad),/new intrusion/);
});

test('CNN collapsed proxy residual becomes the independent 38-unit straight route without merging its data lane',()=>{
  const document=canvasFor(cnn), original=JSON.stringify(document), scene=serialized(buildScene(document));
  assertRefinement(beforeFor(cnn),scene,renderSvg(scene));coverage(document,scene);
  const edge=scene.edges.find(edge=>edge.id==='edge:9')!;
  assert.deepEqual(stats(edge.path),{length:38,bends:0});assert.deepEqual(points(edge.path),[{x:209.3,y:316},{x:209.3,y:354}]);
  assert.equal(edge.role,'residual');assert.deepEqual(edge.canonicalEdgeIds,['edge:9']);
  const ordinary=scene.edges.find(edge=>edge.canonicalEdgeIds.includes('edge:2'))!;
  assert.equal(ordinary.tensorId,edge.tensorId);assert.equal(ordinary.role,'data');assert.notEqual(ordinary.path,edge.path);
  assert.equal(JSON.stringify(document),original);assert.equal(renderSvg(buildExportScene(document)),renderSvg(scene));
});

for(const record of capture.records)test(`all protected branches/cards/ports and pair-local safety survive: ${record.key}`,()=>{
  const document=canvasFor(record), original=JSON.stringify(document), before=beforeFor(record), scene=serialized(buildScene(document));
  assertRefinement(before,scene,renderSvg(scene));coverage(document,scene);
  for(const edge of scene.edges) {
    const old=before.edges.find(item=>item.id===edge.id)!;if(edge.path===old.path)continue;
    const owner=scene.nodes.find(node=>node.id===edge.targetId)!;
    assert.equal(edge.role,'residual','unrelated role changed under a residual-only repair');
    assert.equal(owner.expanded,false);assert.notEqual(edge.target.nodeId,owner.id,'actual target is visible, not collapsed proxy');
    assert.ok(stats(edge.path).length<stats(old.path).length);assert.ok(stats(edge.path).bends<=stats(old.path).bends);
  }
  assert.deepEqual(scene,serialized(buildScene(document)));assert.equal(renderSvg(buildExportScene(document)),renderSvg(scene));
  assert.equal(JSON.stringify(document),original);assert.equal(renderSvg(scene),renderSvg(buildScene(document)));
});

test('renamed generic graphs shorten collapsed module and repeat proxies while preserving manual pins and exposed repeat ports',()=>{
  for(const [prefix,repeat,sourceRepeat,pinned] of [['orbital-flow',false,false,false],['renamed-repeat',true,false,true],['shared-source',true,true,true]] as const) {
    const document=genericDocument(prefix,{repeat,sourceRepeat,pinned}), original=JSON.stringify(document), scene=buildScene(document);
    const skip=scene.edges.find(edge=>edge.id===`${prefix}/skip`)!;
    assert.deepEqual(stats(skip.path),{length:sourceRepeat?31:38,bends:0});
    assert.deepEqual(points(skip.path),[{x:209.3,y:sourceRepeat?223:216},{x:209.3,y:254}]);
    assert.equal(scene.nodes.find(node=>node.id===`${prefix}/feed`)!.localX,30);
    assert.equal(scene.nodes.find(node=>node.id===`${prefix}/cell`)!.localY,162);
    assert.equal(scene.nodes.find(node=>node.id===`${prefix}/cell`)!.pinned,pinned);
    coverage(document,scene);assertEndpoints(scene);assertSvg(scene,renderSvg(scene));assert.deepEqual(intrusions(scene),[]);
    assertSvg(scene,renderSvg(scene,{interactive:true}));
    assert.equal(renderSvg(buildExportScene(document)),renderSvg(scene));assert.equal(JSON.stringify(document),original);
  }
});

test('single-route collapsed proxy optimization works without pressure or model-name assumptions',()=>{
  const fixture=literalRoutingCase({repeat:true,pinned:true}), after=observe(fixture);
  assert.equal(after.edges[0].path,fixture.literalExpected);assert.deepEqual(stats(after.edges[0].path),{length:50,bends:0});
  assertRefinement(fixture.scene,after,renderSvg(after));
});

test('clear manually misaligned proxy endpoints attain the independent Manhattan minimum with two turns',()=>{
  const fixture=literalRoutingCase({misaligned:true,pinned:true}),after=observe(fixture);
  assert.deepEqual(stats(after.edges[0].path),{length:70,bends:2});
  assertRefinement(fixture.scene,after,renderSvg(after));
});

test('expanded targets, actual visible targets, upward residuals and memory/mask roles retain the original outside route',()=>{
  for(const options of [{targetExpanded:true},{targetProxy:false},{upward:true},{role:'memory' as const},{role:'mask' as const}]) {
    const fixture=literalRoutingCase(options),after=observe(fixture);assert.equal(after.edges[0].path,fixture.scene.edges[0].path,JSON.stringify(options));
    assertRefinement(fixture.scene,after);
  }
  const expanded=genericDocument('visible-merge',{expanded:true}),scene=buildScene(expanded);
  const skip=scene.edges.find(edge=>edge.id==='visible-merge/skip')!;
  assert.equal(skip.targetId,skip.target.nodeId);assert.ok(stats(skip.path).bends>=4,'cannot shortcut visible intermediate operators/header');
  assertEndpoints(scene);assertSvg(scene,renderSvg(scene));assert.deepEqual(intrusions(scene),[]);
});

test('missing, unresolved, mixed or inconsistent canonical/proxy-port evidence never licenses shortcutting',()=>{
  const changes=[
    (f:ReturnType<typeof literalRoutingCase>)=>{delete (f.requests[0] as Partial<RouteRequest>).canonicalTarget;},
    (f:ReturnType<typeof literalRoutingCase>)=>{f.requests[0].canonicalTarget.nodeId='unrelated-hidden-node';},
    (f:ReturnType<typeof literalRoutingCase>)=>{f.requests[0].canonicalTarget.portId='wrong-input';},
    (f:ReturnType<typeof literalRoutingCase>)=>{f.scene.nodes.find(node=>node.id===f.targetId)!.ports[0].proxy=false;},
    (f:ReturnType<typeof literalRoutingCase>)=>{f.scene.nodes.find(node=>node.id===f.targetId)!.ports[0].canonicalBindings=[];},
    (f:ReturnType<typeof literalRoutingCase>)=>{f.scene.nodes.find(node=>node.id===f.targetId)!.ports[0].canonicalBindings.push({nodeId:'mixed-target',portId:'other'});},
    (f:ReturnType<typeof literalRoutingCase>)=>{f.requests[0].canonicalEdgeIds.push('unproven-branch');},
  ];
  for(const change of changes) {const fixture=literalRoutingCase();change(fixture);assert.equal(observe(fixture).edges[0].path,fixture.scene.edges[0].path);}
});

test('unrelated body, ancestor header and repeat backplate blocking all retain safe old route and immutable anchors',()=>{
  const body=literalRoutingCase();body.scene.nodes.push(literalNode('blocking-body',45,65,10,20));
  const plates=literalRoutingCase();plates.scene.nodes.push(literalNode('blocking-stack',30,60,18,15,{repeat:{count:2,sharing:'independent'},pinned:true}));
  const header=literalRoutingCase();header.scene.nodes.find(node=>node.id===header.sourceId)!.parentId=undefined;
  header.scene.nodes.find(node=>node.id==='shell')!.y=70;header.scene.nodes.find(node=>node.id==='shell')!.height=150;
  header.scene.nodes.find(node=>node.id==='shell')!.width=140;
  for(const fixture of [body,plates,header]) {
    const after=observe(fixture);assert.ok(stats(after.edges[0].path).bends>0);assertRefinement(fixture.scene,after,renderSvg(after));
    const candidate=structuredClone(fixture.scene);candidate.edges[0].path='M 50 50 V 100';assert.throws(()=>assertRefinement(fixture.scene,candidate),/intrusion/);
  }
});

test('every other edge is protected even when sharing tensor but differing in role/style: crossing and overlap',()=>{
  for(const shape of ['horizontal','overlap'] as const)for(const same of [false,true])for(const role of ['data','memory','mask','residual'] as const) {
    const fixture=addProtectedRoute(literalRoutingCase(),shape,same,role),after=observe(fixture);
    assertRefinement(fixture.scene,after,renderSvg(after));assert.ok(stats(after.edges[0].path).bends>0,'short aligned lane introduces protected interference');
    const bad=structuredClone(fixture.scene);bad.edges[0].path='M 50 50 V 100';
    if(shape==='overlap')assert.ok(pair(bad.edges[0].path,bad.edges[1].path).overlapLength>0,'literal negative control has genuine positive interval overlap');
    assert.throws(()=>assertRefinement(fixture.scene,bad),shape==='horizontal'?/protected crossing/:/protected (crossing|overlap)/);
  }
});

test('misaligned short staircases cannot conceal crossings on another edge intermediate vertex, including same-tensor different styles',()=>{
  for(const shape of ['split-vertical','bend-vertex'] as const)for(const same of [false,true])for(const role of ['data','memory','mask','residual'] as const) {
    const fixture=addProtectedRoute(literalRoutingCase({misaligned:true}),shape,same,role);
    assert.deepEqual(pair(fixture.scene.edges[0].path,fixture.scene.edges[1].path).crossings,[]);
    const bad=structuredClone(fixture.scene);bad.edges[0].path='M 50 50 V 75 H 70 V 100';
    assert.equal(pair(bad.edges[0].path,bad.edges[1].path).crossings.length,1);
    assert.throws(()=>assertRefinement(fixture.scene,bad),/protected crossing/);
    assertRefinement(fixture.scene,observe(fixture));
  }
});

test('retraced protected segments cannot inflate old pair overlap and license a larger same-tensor residual overlap',()=>{
  const fixture=literalRoutingCase(),edgeId='protected/retraced',sourceId='protected/source',targetId='protected/target';
  const start={x:-10,y:60},end={x:50,y:80},path='M -10 60 H 55 H 50 H 55 H 50 V 80';
  const source=literalNode(sourceId,-30,50,20,20,{parentId:'shell'}),target=literalNode(targetId,20,80,30,20,{parentId:'shell'});
  source.ports=[literalPort(sourceId,sourceId,'out',edgeId,'out',start.x,start.y)];
  target.ports=[literalPort(targetId,targetId,'in',edgeId,'in',end.x,end.y)];
  fixture.scene.nodes.push(source,target);
  const appearance={stroke:'#115588',width:2,dashed:false};
  const protectedEdge={id:edgeId,sourceId,targetId,source:{nodeId:sourceId,portId:'out'},target:{nodeId:targetId,portId:'in'},
    canonicalEdgeIds:[edgeId],tensorId:fixture.requests[0].tensorId,role:'data' as const,path,...appearance,label:'',labelX:0,labelY:0};
  fixture.scene.edges.push(protectedEdge);
  fixture.requests.push({sourceId,targetId,start,end,preferredPath:path,tensorId:protectedEdge.tensorId,role:'data',appearance,
    canonicalSource:{...protectedEdge.source},canonicalTarget:{...protectedEdge.target},canonicalEdgeIds:[edgeId],displaySide:'bottom'});
  // The old horizontal overlap is the union [50,55], despite four traversals.
  // The tempting straight route overlaps the independent vertical interval
  // [60,80]. Both share one interior crossing, so only overlap detects harm.
  const oldPair=pair(fixture.scene.edges[0].path,path);
  assert.deepEqual(oldPair,{crossings:['50/60'],overlapLength:5});
  const bad=structuredClone(fixture.scene);bad.edges[0].path='M 50 50 V 100';
  assert.deepEqual(pair(bad.edges[0].path,path),{crossings:['50/60'],overlapLength:20});
  assert.deepEqual(intrusions(fixture.scene),[]);assert.deepEqual(intrusions(bad),[]);
  assert.throws(()=>assertRefinement(fixture.scene,bad),/new protected overlap/);
  const after=observe(fixture),currentPair=pair(after.edges[0].path,after.edges[1].path);
  assertRefinement(fixture.scene,after,renderSvg(after));
  assert.deepEqual(after.edges[1],protectedEdge,'clear protected data route/branch/style must remain unchanged');
  assert.ok(currentPair.overlapLength<=oldPair.overlapLength,'old retraces cannot conceal a larger physical overlap');
  assert.ok(currentPair.crossings.length<=oldPair.crossings.length);
});

test('effective style overrides retain separate canonical residual branches and never merge them with the same-tensor data lane',()=>{
  const document=genericDocument('style-split');
  const extra=structuredClone(document.architecture.edges[1]);extra.id='style-split/alternate';document.architecture.edges.push(extra);
  document.edgeStyleOverrides[extra.id]={stroke:'#123456',width:2,dashed:true};
  const original=JSON.stringify(document),scene=buildScene(document),skip=scene.edges.filter(edge=>edge.role==='residual');
  assert.equal(skip.length,2);assert.equal(scene.edges.filter(edge=>edge.role==='data').length,1);coverage(document,scene);
  assert.ok(skip.some(edge=>edge.canonicalEdgeIds.length===1&&edge.canonicalEdgeIds[0]===extra.id&&edge.stroke==='#123456'&&edge.width===2&&edge.dashed));
  assertEndpoints(scene);assertSvg(scene,renderSvg(scene));assert.deepEqual(intrusions(scene),[]);
  assert.equal(renderSvg(buildExportScene(document)),renderSvg(scene));assert.equal(JSON.stringify(document),original);
});

test('bounded-work fallback preserves the old route instead of advertising an unchecked shortcut',()=>{
  const fixture=literalRoutingCase();
  for(let i=0;i<1025;i++)fixture.scene.nodes.push(literalNode(`isolated-budget-${i}`,10000+i*30,10000,20,20));
  const after=observe(fixture);assert.equal(after.edges[0].path,fixture.scene.edges[0].path);
});
