// Offline, non-executing regression diagnosis. Browser evidence is separate.
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../../..'),pub=path.join(root,'studio/public/preview'),runtime=path.join(pub,'yworks_edge_router_lab');
const ctx=vm.createContext({TextEncoder,TextDecoder}),baseline=process.env.AUDIT_BASELINE==='1',output=baseline?path.join(here,'controlled-before'):here;
fs.mkdirSync(path.join(output,'scenes'),{recursive:true});
const assets=['router','physical-ports','junction-markers','route-labels','source-contracts','semantic-constraints','graph-engine','recursive-graph','source-adapter','source-controls','frontier-task'];
const assetPath=n=>baseline&&fs.existsSync(path.join(here,'../visual-fixes-20261017/before',n+'.js'))?path.join(here,'../visual-fixes-20261017/before',n+'.js'):path.join(runtime,n+'.js');
for(const n of assets)vm.runInContext(fs.readFileSync(assetPath(n),'utf8'),ctx,{filename:n});
const C=ctx.SummaryConstraints,F=ctx.SummaryRecursive,E=ctx.SummaryEngine,T=ctx.SummaryFrontierTask,R=ctx.EdgeRouterLabRouting;
const hash=v=>crypto.createHash('sha256').update(typeof v==='string'?v:JSON.stringify(v)).digest('hex');
const clean=v=>JSON.parse(JSON.stringify(v));
const round=x=>Math.round(x*100)/100;
function metrics(g){
 let length=0,bends=0,micro=0,hairpins=0,crossings=0;
 const segments=[];
 for(const e of g.edges){const ps=R.simplify(e.route);bends+=Math.max(0,ps.length-2);
  ps.slice(1).forEach((b,i)=>{const a=ps[i],l=Math.hypot(b.x-a.x,b.y-a.y);length+=l;if(l>0&&l<3)micro++;segments.push({a,b,e});});
  ps.slice(0,-3).forEach((a,i)=>{const b=ps[i+1],c=ps[i+2],d=ps[i+3];if(Math.abs(a.y-b.y)<1e-5&&Math.abs(c.y-d.y)<1e-5&&(b.x-a.x)*(d.x-c.x)<0&&Math.abs(b.y-c.y)<10)hairpins++;
   if(Math.abs(a.x-b.x)<1e-5&&Math.abs(c.x-d.x)<1e-5&&(b.y-a.y)*(d.y-c.y)<0&&Math.abs(b.x-c.x)<10)hairpins++;});
 }
 for(let i=0;i<segments.length;i++)for(let j=i+1;j<segments.length;j++){
  const a=segments[i],b=segments[j];if(a.e===b.e||a.e.contract?.wire===b.e.contract?.wire)continue;
  const h=Math.abs(a.a.y-a.b.y)<1e-5?a:b,v=h===a?b:a;
  if(Math.abs(h.a.y-h.b.y)>1e-5||Math.abs(v.a.x-v.b.x)>1e-5)continue;
  if(v.a.x>Math.min(h.a.x,h.b.x)+.01&&v.a.x<Math.max(h.a.x,h.b.x)-.01&&h.a.y>Math.min(v.a.y,v.b.y)+.01&&h.a.y<Math.max(v.a.y,v.b.y)-.01)crossings++;
 }
 const leaves=g.nodes.filter(n=>!n.expanded&&!n.junction),bounds=g.nodes.length?{x:Math.min(...g.nodes.map(n=>n.x)),y:Math.min(...g.nodes.map(n=>n.y)),r:Math.max(...g.nodes.map(n=>n.x+n.w)),b:Math.max(...g.nodes.map(n=>n.y+n.h))}:{x:0,y:0,r:1,b:1};
 return {nodes:g.nodes.length,edges:g.edges.length,containers:g.nodes.filter(n=>n.expanded).length,length:round(length),bends,crossings,microSegmentsBelow3:micro,hairpinsBelow10:hairpins,width:round(bounds.r-bounds.x),height:round(bounds.b-bounds.y),leafAreaRatio:round(leaves.reduce((a,n)=>a+n.w*n.h,0)/((bounds.r-bounds.x)*(bounds.b-bounds.y)))};
}
function binding(g){return g.edges.map(e=>[e.id,e.source,e.target,e.binding]);}
function scene(g){return {canvas:g.canvas,definitions:g.definitions,extras:g.extras,nodes:g.nodes,edges:g.edges,routeLabels:g.routeLabels,attachments:g.attachments,sourceControls:g.sourceControls,junctionMarkers:g.junctionMarkers};}
function diagnose(c,sources){
 const immutable=hash(sources),row={id:c.id,title:c.title,historical:!!c.historical,states:[]};
 const base=F.build(F.create(sources));
 const run=(name,g,transition)=>{const start=Date.now();try{const r=T.run(E.clone(g),transition,{}),out=r.graph;
   const v=E.validateView(out),state={name,ok:v.source.ok&&v.layout.ok&&v.edges.every(([,v])=>v.ok),ms:Date.now()-start,metrics:metrics(out),controls:out.sourceControls?.diagnostics||[],validation:{source:v.source,layout:v.layout.violations,edges:v.edges.filter(([,v])=>!v.ok)}};
   row.states.push(state);fs.writeFileSync(path.join(output,'scenes',c.id+'--'+name+'.json'),JSON.stringify(scene(out)));return out;
  }catch(error){row.states.push({name,ok:false,ms:Date.now()-start,error:String(error)});return null;}};
 const initial=run('initial',base,null);
 // States are independent: one failed projection must not suppress other coverage.
 const full=run('full',initial||base,{type:'all',expanded:true});
 const ids=F.containers(base.recursive.authority).filter(id=>!base.recursive.authority.mandatory.includes(id));
 run('mixed',initial||base,{type:'expand',ids:ids.filter((_,i)=>i%2===0),expanded:true});
 const detail=base.recursive.authority.detail,byId=new Map(detail.nodes.map(n=>[n.id,n]));
 const depth=id=>{let d=0,n=byId.get(id);while(n?.parent&&d<100){d++;n=byId.get(n.parent);}return d;};
 const deepest=ids.toSorted((a,b)=>depth(b)-depth(a))[0],chain=[];let n=byId.get(deepest);while(n){if(ids.includes(n.id))chain.unshift(n.id);n=byId.get(n.parent);}
 run('deep',initial||base,{type:'expand',ids:chain,expanded:true});
 if(full){F.remember(full);const expected=JSON.stringify(binding(full));let restored=full;
  for(let i=1;i<=2;i++){const folded=run('fold'+i,restored,{type:'all',expanded:false});restored=folded&&run('reopen'+i,folded,{type:'all',expanded:true});if(!restored)break;row.states.at(-1).bindingsRestored=JSON.stringify(binding(restored))===expected;}
 }
 row.sourceUnchanged=immutable===hash(sources);row.ok=row.sourceUnchanged&&row.states.every(s=>s.ok&&s.bindingsRestored!==false);return row;
}
const catalog=JSON.parse(fs.readFileSync(path.join(pub,'data/catalog.json'))).cases,rows=[];
// Extract the pure builtin factory verbatim; no browser/app code is executed.
const app=fs.readFileSync(path.join(runtime,'app.js'),'utf8'),lab=app.slice(app.indexOf('  function lab(){'),app.indexOf('  function renderCatalog(){'));
vm.runInContext('const R=EdgeRouterLabRouting,E=SummaryEngine;'+lab+';this.auditLab=lab;',ctx);
let extra=[];if(fs.existsSync(path.join(here,'inputs/index.json')))extra=JSON.parse(fs.readFileSync(path.join(here,'inputs/index.json')));
const selected=[...catalog,...extra].filter(c=>!process.env.AUDIT_FILTER||c.id.includes(process.env.AUDIT_FILTER));
for(const [i,c]of selected.entries()){
 try{const sources=c.bundle?ctx.SummarySourceAdapter.sources(JSON.parse(fs.readFileSync(path.join(here,c.bundle)))):c.views.some(v=>v.builtin)?{overview:ctx.auditLab()}:Object.fromEntries(c.views.map(v=>[v.key,C.initialize(JSON.parse(fs.readFileSync(path.join(pub,v.json||v.asset.replace(/\.js$/,'.json')))))]));rows.push(diagnose(c,sources));}
 catch(error){rows.push({id:c.id,title:c.title,historical:!!c.historical,ok:false,error:String(error),states:[]});}
 fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({controlledBefore:baseline,assets:assets.map(n=>({name:n,path:assetPath(n),sha256:hash(fs.readFileSync(assetPath(n),'utf8'))})),cases:rows},null,2));
 console.log(`${i+1}/${selected.length} ${c.id} ${rows.at(-1).ok?'PASS':'FAIL'} ${rows.at(-1).states.filter(s=>!s.ok).map(s=>s.name).join(',')}`);
}
