import { readFileSync, writeFileSync, mkdirSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { resolve, relative } from 'node:path';
import { applyVisualBatch, createDocument, buildScene, buildExportScene, renderSvg } from '../../../../studio/src/core/index.ts';

// Independent assertion oracle: own public SVG-path parser, segment geometry,
// canonical source matching and obstacle/clearance checks. Product code is
// used solely to produce the observations; no historical routing is imported.
const dir = fileURLToPath(new URL('.', import.meta.url));
const project = resolve(dir, '../../../../');
const EPS = .051;
const near = (a,b) => Math.abs(a-b)<EPS;
const sha = raw => createHash('sha256').update(raw).digest('hex');
export function parse(path) {
  const out=[]; let x=0,y=0, tail=path;
  const first=/^M\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)/.exec(tail);
  if (!first) throw Error(`invalid start ${path}`);
  x=+first[1]; y=+first[2]; out.push({x,y}); tail=tail.slice(first[0].length);
  while(tail.trim()) {
    const m=/^\s*([HV])\s+(-?\d+(?:\.\d+)?)/.exec(tail);
    if(!m) throw Error(`unparsed path tail ${tail}`);
    if(m[1]==='H')x=+m[2];else y=+m[2];
    out.push({x,y});tail=tail.slice(m[0].length);
  }
  return out.filter((p,i)=>!i||!near(p.x,out[i-1].x)||!near(p.y,out[i-1].y));
}
const segments=p=>p.slice(1).map((b,i)=>({a:p[i],b,v:near(p[i].x,b.x),len:Math.abs(p[i].x-b.x)+Math.abs(p[i].y-b.y),index:i}));
const merged=spans=> {
  const sorted=spans.sort((a,b)=>a[0]-b[0]),out=[];
  for(const [a,b] of sorted){if(!out.length||a>out.at(-1)[1]+EPS)out.push([a,b]);else out.at(-1)[1]=Math.max(out.at(-1)[1],b);}
  return out.reduce((s,[a,b])=>s+b-a,0);
};
export function pair(first,second) {
  const crossings=new Map(),contacts=new Map(),overlap=new Map();
  for(const a of segments(first))for(const b of segments(second)){
    if(a.v===b.v){
      if(!near(a.v?a.a.x:a.a.y,a.v?b.a.x:b.a.y))continue;
      const low=Math.max(a.v?Math.min(a.a.y,a.b.y):Math.min(a.a.x,a.b.x),a.v?Math.min(b.a.y,b.b.y):Math.min(b.a.x,b.b.x));
      const high=Math.min(a.v?Math.max(a.a.y,a.b.y):Math.max(a.a.x,a.b.x),a.v?Math.max(b.a.y,b.b.y):Math.max(b.a.x,b.b.x));
      if(high>low+EPS){const key=`${a.v?'v':'h'}:${a.v?a.a.x:a.a.y}`;const xs=overlap.get(key)||[];xs.push([low,high]);overlap.set(key,xs);}
    }else{
      const v=a.v?a:b,h=a.v?b:a;
      const x=v.a.x,y=h.a.y;
      if(x>=Math.min(h.a.x,h.b.x)-EPS&&x<=Math.max(h.a.x,h.b.x)+EPS&&y>=Math.min(v.a.y,v.b.y)-EPS&&y<=Math.max(v.a.y,v.b.y)+EPS){
        const strict=x>Math.min(h.a.x,h.b.x)+EPS&&x<Math.max(h.a.x,h.b.x)-EPS&&y>Math.min(v.a.y,v.b.y)+EPS&&y<Math.max(v.a.y,v.b.y)-EPS;
        (strict?crossings:contacts).set(`${x},${y}`,{x,y});
      }
    }
  }
  return {crossings:[...crossings.values()],contacts:[...contacts.values()],overlaps:[...overlap].map(([axis,spans])=>({axis,spans,length:merged(spans)})),overlapLength:[...overlap.values()].reduce((s,xs)=>s+merged(xs),0)};
}
const enters=(s,r)=>s.v?s.a.x>r.x+EPS&&s.a.x<r.x+r.width-EPS&&Math.max(Math.min(s.a.y,s.b.y),r.y+EPS)<Math.min(Math.max(s.a.y,s.b.y),r.y+r.height-EPS):s.a.y>r.y+EPS&&s.a.y<r.y+r.height-EPS&&Math.max(Math.min(s.a.x,s.b.x),r.x+EPS)<Math.min(Math.max(s.a.x,s.b.x),r.x+r.width-EPS);
function analyze(scene,doc){
 const nodes=new Map(scene.nodes.map(n=>[n.id,n])),canon=new Map(doc.architecture.edges.map(e=>[e.id,e])),arch=new Map(doc.architecture.nodes.map(n=>[n.id,n]));
 const ancestors=id=>{const out=new Set();let p=arch.get(id)?.parentId;while(p&&!out.has(p)){out.add(p);p=arch.get(p)?.parentId;}return out;};
 const facts=scene.sourceFacts.every(f=>{const n=arch.get(f.id);return n&&f.sourceLabel===n.label&&f.kind===n.kind&&JSON.stringify(f.source)===JSON.stringify(n.source)&&f.instanceId===n.instanceId&&f.callId===n.callId;});
 const coverage=[...scene.hiddenEdges,...scene.edges.flatMap(e=>e.canonicalEdgeIds)].sort();
 const identityErrors=[],intrusions=[],borderNear=[],routes=[];
 for(const e of scene.edges){
  const p=parse(e.path),ss=segments(p),own=new Set([...ancestors(e.sourceId),...ancestors(e.targetId)]),c=canon.get(e.id);
  if(JSON.stringify(e.source)!==JSON.stringify(c?.source)||JSON.stringify(e.target)!==JSON.stringify(c?.target)||e.role!==c?.role||e.tensorId!==c?.tensorId)identityErrors.push(e.id);
  for(const [id,direction,point] of [[e.sourceId,'out',p[0]],[e.targetId,'in',p.at(-1)]]){
   const ports=nodes.get(id)?.ports.filter(port=>port.direction===direction&&near(port.x,point.x)&&near(port.y,point.y)&&e.canonicalEdgeIds.every(id=>port.canonicalEdgeIds.includes(id)));
   if(!ports?.length)identityErrors.push(`${e.id}/${direction}/attachment`);
  }
  for(const n of scene.nodes){
   const offsets=n.repeat&&!n.expanded?[0,3.5,7]:[0];
   for(const offset of offsets){
    const r={x:n.x+offset,y:n.y+offset,width:n.width,height:own.has(n.id)&&n.expanded?n.headerHeight:n.height};
    for(const s of ss)if(enters(s,r))intrusions.push({edge:e.id,node:n.id,offset,segment:s.index,from:s.a,to:s.b});
   }
   // Do not count the short attached terminal segment as a border lane.
   for(const s of ss){
    if((n.id===e.sourceId&&s.index===0)||(n.id===e.targetId&&s.index===ss.length-1))continue;
    const overlap=s.v?Math.min(Math.max(s.a.y,s.b.y),n.y+n.height)-Math.max(Math.min(s.a.y,s.b.y),n.y):Math.min(Math.max(s.a.x,s.b.x),n.x+n.width)-Math.max(Math.min(s.a.x,s.b.x),n.x);
    const distance=s.v?Math.min(Math.abs(s.a.x-n.x),Math.abs(s.a.x-n.x-n.width)):Math.min(Math.abs(s.a.y-n.y),Math.abs(s.a.y-n.y-n.height));
    if(overlap>8&&distance<8-EPS)borderNear.push({edge:e.id,node:n.id,segment:s.index,distance,parallelLength:overlap,from:s.a,to:s.b,ancestor:own.has(n.id)});
   }
  }
  const length=ss.reduce((s,x)=>s+x.len,0),direct=Math.abs(p[0].x-p.at(-1).x)+Math.abs(p[0].y-p.at(-1).y);
  routes.push({edge:e.id,role:e.role,path:e.path,length,direct,detour:length-direct,ratio:direct?length/direct:Infinity,bends:Math.max(0,p.length-2),blocked:scene.diagnostics.filter(d=>d.edgeId===e.id&&d.code==='layout-route-blocked')});
 }
 const pairs=[];
 for(let i=0;i<scene.edges.length;i++)for(let j=i+1;j<scene.edges.length;j++){
  const a=scene.edges[i],b=scene.edges[j],m=pair(parse(a.path),parse(b.path));
  if(m.crossings.length||m.overlapLength>EPS)pairs.push({first:a.id,second:b.id,sameTensor:a.tensorId===b.tensorId,sameCanonicalSource:JSON.stringify(a.source)===JSON.stringify(b.source),...m});
 }
 // Independent coarse-arrow check: a drawn parent/child pair with identical
 // opposite endpoint, exact port, tensor and role should not coexist unless
 // the coarse endpoint is opaque.
 const ambiguities=[];
 for(const a of scene.edges)for(const b of scene.edges){if(a.id===b.id||a.role!==b.role||a.tensorId!==b.tensorId)continue;
  if(JSON.stringify(a.source)===JSON.stringify(b.source)&&ancestors(b.targetId).has(a.targetId)&&nodes.get(a.targetId)?.expanded&&arch.get(a.targetId)?.evidence!=='opaque')ambiguities.push({coarse:a.id,detailed:b.id,side:'target'});
  if(JSON.stringify(a.target)===JSON.stringify(b.target)&&ancestors(b.sourceId).has(a.sourceId)&&nodes.get(a.sourceId)?.expanded&&arch.get(a.sourceId)?.evidence!=='opaque')ambiguities.push({coarse:a.id,detailed:b.id,side:'source'});
 }
 return {nodes:scene.nodes.length,edges:scene.edges.length,hidden:scene.hiddenEdges.length,canonicalCoverage:JSON.stringify(coverage)===JSON.stringify(doc.architecture.edges.map(e=>e.id).sort()),sourceFactsMatch:facts,sourceDigestMatch:scene.sourceDigest===doc.architecture.sourceDigest,irDigestMatch:scene.irDigest===doc.architecture.irDigest,identityErrors,ambiguities,intrusions,borderNear,pairs,routes:routes.sort((a,b)=>b.detour-a.detour),summary:{crossingPairs:pairs.filter(p=>p.crossings.length).length,distinctTensorCrossingPairs:pairs.filter(p=>p.crossings.length&&!p.sameTensor).length,overlapPairs:pairs.filter(p=>p.overlapLength>EPS).length,distinctTensorOverlapPairs:pairs.filter(p=>p.overlapLength>EPS&&!p.sameTensor).length,overlapLength:pairs.reduce((s,p)=>s+p.overlapLength,0),intrusions:intrusions.length,borderNear:borderNear.length,maxDetour:Math.max(...routes.map(r=>r.detour)),maxRatio:Math.max(...routes.filter(r=>r.direct>0).map(r=>r.ratio))},diagnostics:scene.diagnostics};
}
const records=[];
for(const [name,levels] of [['mlp',1],['residual_cnn',2],['transformer',3]]){
 const architecture=JSON.parse(readFileSync(resolve(dir,name,'architecture.json'),'utf8')),byId=new Map(architecture.nodes.map(n=>[n.id,n]));
 const depth=n=>n.parentId?1+depth(byId.get(n.parentId)):0;
 for(let level=0;level<=levels;level++){
  let doc=createDocument(architecture);doc=applyVisualBatch(doc,architecture.nodes.filter(n=>n.children.length&&depth(n)<=level&&n.parentId).map(n=>({type:'expand',id:n.id,expanded:true})));
  const base=buildScene(doc),atomic=base.nodes.filter(n=>!n.expandable&&!['input','output'].includes(n.category));
  const movable=atomic.find(n=>n.category==='attention')||atomic[Math.floor(atomic.length/2)];
  for(const [suffix,dx,dy] of [['base',0,0],['left',-24,0],['right',24,0],['up',0,-24],['down',0,24]]){
   if(suffix!=='base'&&!movable)continue;
   const actual=suffix==='base'?doc:applyVisualBatch(doc,[{type:'move',ids:[movable.id],dx,dy,scope:'current-frontier'}]);
   const bytes=JSON.stringify(actual),scene=buildScene(actual),svg=renderSvg(buildExportScene(actual));
   const caseId=`${name}-level${level}-${suffix}`;
   const result=analyze(scene,actual);result.svgMatchesScene=svg===renderSvg(scene);result.documentUnchanged=bytes===JSON.stringify(actual);result.movement=suffix==='base'?null:{id:movable.id,dx,dy};
   writeFileSync(resolve(dir,`${caseId}.canvas.json`),JSON.stringify(actual,null,2)+'\n');writeFileSync(resolve(dir,`${caseId}.scene.json`),JSON.stringify(scene,null,2)+'\n');writeFileSync(resolve(dir,`${caseId}.svg`),svg);writeFileSync(resolve(dir,`${caseId}.audit.json`),JSON.stringify(result,null,2)+'\n');
   records.push({caseId,...result.summary,canonicalCoverage:result.canonicalCoverage,sourceFactsMatch:result.sourceFactsMatch,identityErrors:result.identityErrors.length,ambiguities:result.ambiguities.length,documentUnchanged:result.documentUnchanged,svgMatchesScene:result.svgMatchesScene});
  }
 }
}
const paths=['studio/src/core/atomicFrontier.ts','studio/src/core/memoryContinuity.ts','studio/src/core/readableRouting.ts','studio/src/core/orthogonalRouter.ts','studio/src/core/scene.ts','studio/src/core/exportScene.ts','studio/src/core/svg.ts','studio/src/core/document.ts','studio/src/core/nodeVisualOutline.ts','studio/tests/atomic-frontier-routing.test.ts','studio/tests/readable-routing-current.test.ts',...['mlp/model.py','residual_cnn/model.py','residual_cnn/blocks.py','transformer/model.py','transformer/blocks.py'].map(p=>'fixtures/'+p)];
const bindings=paths.map(path=>{const raw=readFileSync(resolve(project,path));return{path,bytes:raw.length,sha256:sha(raw)};});
const report={schema:'archcanvas.independent-current-routing-audit/1',generatedAt:new Date().toISOString(),operator:'AI',scope:'Current source analysis and current product routing only; 9 base frontiers and 36 single-node cardinal moves. No historical route implementation, no human/publication/performance acceptance.',bindings,records};
writeFileSync(resolve(dir,'report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(records,null,2));
