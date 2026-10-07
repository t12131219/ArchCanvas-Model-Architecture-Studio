import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../../..');
const owner=path.join(root,'docs/evidence/m4-memory-continuity-current/independent-guard-review');
const attempt=process.argv[2];if(!/^ports-attempt-[1-9][0-9]*$/.test(attempt??''))throw new Error('append-only ports-attempt-N required');
const out=path.join(owner,attempt);if(existsSync(out))throw new Error('Evidence must not be overwritten');
const bind=rel=>{const bytes=readFileSync(path.join(root,rel));return{path:rel,bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')}};
const currentCore=readdirSync(path.join(root,'studio/src/core')).filter(p=>p.endsWith('.ts')).sort().map(p=>`studio/src/core/${p}`);
const oldCore=readdirSync(path.join(root,'docs/evidence/m4-memory-continuity-current/before-change/inputs/studio/src/core')).filter(p=>p.endsWith('.ts')).sort().map(p=>`docs/evidence/m4-memory-continuity-current/before-change/inputs/studio/src/core/${p}`);
const bindings=[...currentCore,...oldCore,'docs/evidence/m4-memory-continuity-current/independent-guard-review/port-integration-capture.mjs'].map(bind);
const {buildScene}=await import(path.join(root,'studio/src/core/scene.ts'));
const {buildScene:beforeScene}=await import(path.join(root,'docs/evidence/m4-memory-continuity-current/before-change/inputs/studio/src/core/scene.ts'));
const {buildExportScene}=await import(path.join(root,'studio/src/core/exportScene.ts'));
const {buildExportScene:beforeExport}=await import(path.join(root,'docs/evidence/m4-memory-continuity-current/before-change/inputs/studio/src/core/exportScene.ts'));
const ports=[{id:'in',name:'in',direction:'in',role:'data',ordinal:0},{id:'out',name:'out',direction:'out',role:'data',ordinal:0},{id:'alt',name:'alt',direction:'out',role:'data',ordinal:1}];
const n=(id,extra={})=>({id,label:id,kind:'Linear',category:'linear',children:[],ports:structuredClone(ports),parameters:{},evidence:'source',...extra});
const e=(id,s,t,extra={})=>({id,source:{nodeId:s,portId:'out'},target:{nodeId:t,portId:'in'},tensorId:'same-name',role:'memory',...extra});
function doc(){return{schemaVersion:1,id:'literal-port',title:'Literal',revision:0,sourceBindingDigest:'not-executed',architecture:{schemaVersion:1,id:'independent-multiple-consumer',entry:'literal:Independent',label:'Literal',sourceDigest:'not-executed',irDigest:'literal-independent',diagnostics:[],sources:[],nodes:[
  n('a'),n('b',{children:['b1','b2']}),n('b1',{parentId:'b'}),n('b2',{parentId:'b'}),n('c',{children:['c1']}),n('c1',{parentId:'c'}),n('d'),n('e')],edges:[
  e('accepted-first','a','b1'),e('retained-expanded','a','c1'),e('retained-style','a','d'),e('accepted-later','a','b2'),e('data-consumer','a','d',{role:'data'}),e('distinct-binding-equal-name','a','e',{source:{nodeId:'a',portId:'alt'}})]},
  displayAliases:{},nodeStyleOverrides:{},edgeStyleOverrides:{'retained-style':{dashed:true,width:2.25}},legendItems:[],annotations:[],pageSpec:{widthMm:180,background:'#fff',preset:'paper'},
  expandedIds:['c'],layout:{a:{x:0,y:0,width:200,height:100},b:{x:300,y:10,width:200,height:100},c:{x:600,y:500,width:280,height:220},c1:{x:50,y:60,width:180,height:100},d:{x:600,y:900,width:200,height:100},e:{x:900,y:1200,width:200,height:100}},layoutByFrontier:{},pinnedObjects:[]}}
const rows=[],checks=[];const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
function check(caseName,name,actual,expected=true){checks.push({case:caseName,name,actual,expected,passed:same(actual,expected)})}
function parser(value){const t=value.match(/[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?/g),p=[];let i=0;while(i<t.length){const c=t[i++];if(c==='M'||c==='L')p.push([+t[i++],+t[i++]]);else if(c==='H')p.push([+t[i++],p.at(-1)[1]]);else if(c==='V')p.push([p.at(-1)[0],+t[i++]]);else throw new Error(c)}return p}
function verify(name,document,expectedAdopted,options){
  const build=options?d=>buildExportScene(d,options):buildScene,previous=options?d=>beforeExport(d,options):beforeScene;
  const bytes=JSON.stringify(document),old=previous(document),scene=build(document),changed=scene.edges.filter(edge=>edge.path!==old.edges.find(o=>o.id===edge.id)?.path).map(e=>e.id);
  check(name,'chosen-memory-route-ids',changed,expectedAdopted);
  check(name,'input-immutable',JSON.stringify(document),bytes);
  check(name,'detached-rebuild-deterministic',build(structuredClone(document)),scene);
  for(const field of ['sourceDigest','irDigest','sourceFacts','hiddenEdges','pageSpec','documentId','revision','title','legend','annotations'])check(name,`protected-${field}`,scene[field],old[field]);
  const allIds=scene.edges.flatMap(edge=>edge.canonicalEdgeIds).sort();check(name,'represented-edge-coverage-exact',allIds,old.edges.flatMap(edge=>edge.canonicalEdgeIds).sort());
  for(const edge of scene.edges){
    const prior=old.edges.find(o=>o.id===edge.id),{path:_p,labelX:_x,labelY:_y,...facts}=edge,{path:_op,labelX:_ox,labelY:_oy,...oldFacts}=prior;
    check(name,`edge-${edge.id}-canonical-style`,facts,oldFacts);
    if(!expectedAdopted.includes(edge.id))check(name,`edge-${edge.id}-retained-path`,edge.path,prior.path);
    const points=parser(edge.path);
    for(const direction of ['out','in']){
      const owner=scene.nodes.find(n=>n.id===(direction==='out'?edge.sourceId:edge.targetId)),point=direction==='out'?points[0]:points.at(-1);
      const matching=owner.ports.filter(p=>p.direction===direction&&edge.canonicalEdgeIds.every(id=>p.canonicalEdgeIds.includes(id))&&Math.abs(p.x-point[0])<=.050000001&&Math.abs(p.y-point[1])<=.050000001);
      check(name,`edge-${edge.id}-${direction}-exact-one-public-port`,matching.length,1);
    }
  }
  for(const node of scene.nodes){
    const prior=old.nodes.find(n=>n.id===node.id),{ports:_p,...rest}=node,{ports:_op,...oldRest}=prior;check(name,`node-${node.id}-geometry-facts`,rest,oldRest);
    for(const p of node.ports){
      check(name,`port-${node.id}-${p.id}-nonempty`,p.canonicalEdgeIds.length>0);
      const direction=p.direction==='out'?'source':'target';
      const consuming=scene.edges.filter(edge=>(direction==='source'?edge.sourceId:edge.targetId)===node.id&&edge.canonicalEdgeIds.some(id=>p.canonicalEdgeIds.includes(id)));
      check(name,`port-${node.id}-${p.id}-only-actual-consumers`,p.canonicalEdgeIds.every(id=>consuming.some(e=>e.canonicalEdgeIds.includes(id))));
      const ordered=document.architecture.edges.filter(e=>p.canonicalEdgeIds.includes(e.id)).map(e=>e[direction]);check(name,`port-${node.id}-${p.id}-architecture-order-bindings`,p.canonicalBindings,ordered);
    }
    const adoptedIds=scene.edges.filter(e=>expectedAdopted.includes(e.id)).flatMap(e=>e.canonicalEdgeIds);
    const retainedOld=prior.ports.filter(p=>!p.canonicalEdgeIds.some(id=>adoptedIds.includes(id)));
    for(const p of retainedOld)check(name,`port-${node.id}-${p.id}-retained-exact`,node.ports.find(q=>q.id===p.id),p);
    for(const p of prior.ports.filter(p=>p.canonicalEdgeIds.some(id=>adoptedIds.includes(id)))){
      const remaining=p.canonicalEdgeIds.filter(id=>!adoptedIds.includes(id));
      if(!remaining.length)continue;
      const expected={...p,canonicalEdgeIds:remaining,canonicalBindings:document.architecture.edges.filter(e=>remaining.includes(e.id)).map(e=>p.direction==='out'?e.source:e.target)};
      check(name,`port-${node.id}-${p.id}-remaining-consumer-exact`,node.ports.find(q=>q.id===p.id),expected);
    }
  }
  if(expectedAdopted.length){
    const source=scene.nodes.find(n=>n.id==='a'),accepted=scene.edges.find(e=>e.id==='accepted-first'),side=source.ports.find(p=>p.direction==='out'&&p.canonicalEdgeIds.includes('accepted-first'));
    const target=scene.nodes.find(n=>n.id===accepted.targetId),expectedX=Math.round((source.x+source.width)*100)/100,expectedY=Math.round((source.y+source.height*.55)*100)/100;
    check(name,'accepted-side-source-coordinate',side&&[Math.round(side.x*100)/100,Math.round(side.y*100)/100],[expectedX,expectedY]);
    check(name,'accepted-side-source-coverage',side?.canonicalEdgeIds,accepted.canonicalEdgeIds);
    check(name,'retained-bottom-consumers-covered',source.ports.some(p=>p.canonicalEdgeIds.includes('retained-expanded')&&p.canonicalEdgeIds.includes('retained-style')));
    for(const id of ['data-consumer','distinct-binding-equal-name'])check(name,`${id}-port-exact`,source.ports.find(p=>p.canonicalEdgeIds.includes(id)),old.nodes.find(n=>n.id==='a').ports.find(p=>p.canonicalEdgeIds.includes(id)));
    const targetX=Math.round(target.x*100)/100,targetY=Math.round((target.y+target.height*.55)*100)/100,lane=Math.round((expectedX+targetX)*50)/100;
    const expectedPath=expectedY===targetY?`M ${expectedX} ${expectedY} H ${targetX}`:`M ${expectedX} ${expectedY} H ${lane} V ${targetY} H ${targetX}`;
    check(name,'adopted-exact-HVH',accepted.path,expectedPath);
  }
  rows.push({name,document,old,scene,expectedAdopted,changed,options:options??{}});
}
for(const preset of ['paper','monochrome'])for(const width of [85,180])for(const dy of [10,15,16,24]){const document=doc();document.pageSpec={...document.pageSpec,preset,widthMm:width};document.layout.b.y=dy;verify(`bundled-${preset}-${width}-dy${dy}`,document,['accepted-first'])}
for(const dy of [15,16,24]){const document=doc();document.layout.b.y=dy;document.edgeStyleOverrides['accepted-later']={dashed:true,width:2.25};verify(`style-split-retains-dy${dy}`,document,[])}
for(const dy of [15,24]){
  const document=doc();document.layout.b.y=dy;document.expandedIds.push('b');document.layout.b1={x:60,y:70,width:200,height:100};document.layout.b2={x:60,y:230,width:200,height:100};
  verify(`expanded-parent-collapsed-effective-leaf-adopts-dy${dy}`,document,['accepted-first']);
  document.architecture.nodes.find(n=>n.id==='b1').children=['b1a'];document.architecture.nodes.push(n('b1a',{parentId:'b1'}));document.expandedIds.push('b1');document.layout.b1a={x:40,y:60,width:200,height:100};
  verify(`true-expanded-effective-endpoint-retains-dy${dy}`,document,[]);
}
function mixedProxyDocument(){
  const document=doc();for(const node of document.architecture.nodes.filter(n=>!n.parentId))node.parentId='owner';
  document.architecture.nodes.unshift(n('owner',{category:'container',kind:'Block',children:document.architecture.nodes.filter(n=>n.parentId==='owner').map(n=>n.id),ports:[]}));
  document.architecture.nodes.find(n=>n.id==='a').children=['a1','a2'];document.architecture.nodes.push(n('a1',{parentId:'a'}),n('a2',{parentId:'a'}));
  document.architecture.nodes.find(n=>n.id==='c').children=['c1','c2'];document.architecture.nodes.push(n('c2',{parentId:'c'}));
  document.expandedIds=['owner'];document.layout.owner={x:0,y:0,width:1400,height:1700};document.layout.a.y=150;document.layout.b.y=165;
  for(const edge of document.architecture.edges)edge.source.nodeId='a1';
  document.architecture.edges.splice(5,0,e('retained-later-binding','a2','c2'));return document;
}
for(const preset of ['paper','monochrome'])for(const width of [85,180]){
  const document=mixedProxyDocument();document.pageSpec={...document.pageSpec,preset,widthMm:width};
  verify(`mixed-proxy-whole-${preset}-${width}`,document,['accepted-first']);
  verify(`mixed-proxy-detail-${preset}-${width}`,document,['accepted-first'],{nodeId:'owner',widthMm:width});
}
mkdirSync(out);writeFileSync(path.join(out,'capture.json'),JSON.stringify({bindings,rows},null,2)+'\n');
const report={schema:'archcanvas-independent-memory-display-port-integration/1',createdUtc:new Date().toISOString(),bindings,cases:rows.length,relations:checks.length,passed:checks.filter(c=>c.passed).length,failures:checks.filter(c=>!c.passed),checks,
  scope:'Literal imported public whole/detail Scene builds against hash-bound same-document prior core. Canonical coverage, retained ports/paths, detached determinism and bounded exact adopted geometry. Not source-backed model accuracy, browser pixels, overall routing, fonts/arrowheads, physical publication, presented performance or human tasks.'};
writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2)+'\n');
for(const b of bindings)if(!same(bind(b.path),b))throw new Error(`Input changed during capture: ${b.path}`);
writeFileSync(path.join(out,'bindings-exact.json'),JSON.stringify({exact:true,bindings},null,2)+'\n');console.log(JSON.stringify({cases:report.cases,relations:report.relations,passed:report.passed,failures:report.failures}));
