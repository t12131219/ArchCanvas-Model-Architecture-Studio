/* Geometry transactions for exact-value fan-outs and unordered sibling rows. */
(function(root){
 'use strict';
 const R=root.EdgeRouterLabRouting,EPS=1e-5;
 const key=e=>JSON.stringify([e.source,e.contract?.wire,e.projection?.presentationSlots?.source||e.binding?.source_port]);
 function eligible(e,by){const b=e.binding||{},n=by.get(e.source)?.semantic||{};
  return e.style==='orthogonal'&&typeof e.contract?.wire==='string'&&!e.draft&&!e.failed&&!e.pendingRouting&&!e.contract?.bus&&!e.waypoints?.length&&!b.bundle_members&&
   ['data','alias','interface-binding'].includes(b.kind)&&!b.iteration&&!b.condition&&!b.conditions&&!b.guard&&!b.branch&&
   !['opaque','state','buffer'].includes(n.kind)&&!n.mutable&&!n.condition&&!n.guard&&b.evidence_status!=='conflict'&&
   !['opaque','conflict','unresolved'].includes(b.evidence)&&e.portPolicy?.source.mode==='free'&&e.portPolicy?.target.mode==='free';
 }
 function groups(graph){const by=new Map(graph.nodes.map(n=>[n.id,n])),rows=new Map();
  for(const e of graph.edges)if(eligible(e,by)){const k=key(e);if(!rows.has(k))rows.set(k,[]);rows.get(k).push(e);}
  return [...rows.values()].filter(es=>es.length>1&&es.length<=12);
 }
 // Count the painted union per exact value, rather than counting a common
 // segment once for every consumer. Distinct values always count separately.
 function ink(edges){const bands=new Map();let total=0;
  for(const e of edges)for(let i=1;i<e.route.length;i++){const a=e.route[i-1],b=e.route[i],vertical=Math.abs(a.x-b.x)<EPS,k=JSON.stringify([key(e),vertical,vertical?a.x:a.y]),v=vertical?'y':'x';
   if(!bands.has(k))bands.set(k,[]);bands.get(k).push([Math.min(a[v],b[v]),Math.max(a[v],b[v])]);}
  for(const spans of bands.values()){spans.sort((a,b)=>a[0]-b[0]);let end=-Infinity;for(const [a,b]of spans){total+=Math.max(0,b-Math.max(a,end));end=Math.max(end,b);}}
  return total;
 }
 // Border readability is measured on actual painted value lanes too. A
 // shared prefix is one stroke, even when several consumers retain its path.
 function borders(graph,route){return root.SummaryNativeSemantic.borderProximity(graph,route,graph.nodes.filter(n=>!n.modelHeading&&!n.junction));}
 function borderInk(graph){
  const bands=new Map();for(const e of graph.edges)for(let i=1;i<e.route.length;i++){const a=e.route[i-1],b=e.route[i],v=Math.abs(a.x-b.x)<EPS,k=JSON.stringify([key(e),v,v?a.x:a.y]),axis=v?'y':'x';if(!bands.has(k))bands.set(k,[]);bands.get(k).push([Math.min(a[axis],b[axis]),Math.max(a[axis],b[axis])]);}
  let total=0;for(const [k,spans]of bands){const [,v,c]=JSON.parse(k);spans.sort((a,b)=>a[0]-b[0]);let start=null,end=-Infinity;const measure=()=>{if(start!==null)total+=borders(graph,v?[{x:c,y:start},{x:c,y:end}]:[{x:start,y:c},{x:end,y:c}]).cost;};for(const [a,b]of spans){if(a>end+EPS){measure();start=a;end=b;}else end=Math.max(end,b);}measure();}return total;
 }
 function prefix(a,b){if(!a.length||!b.length||R.dist(a[0],b[0])>EPS)return [];
  let i=1,j=1,p={...a[0]},out=[p];
  while(i<a.length&&j<b.length){const x=a[i],y=b[j],dx=[Math.sign(x.x-p.x),Math.sign(x.y-p.y)],dy=[Math.sign(y.x-p.x),Math.sign(y.y-p.y)];
   if(dx[0]!==dy[0]||dx[1]!==dy[1])break;
   const step=Math.min(R.dist(p,x),R.dist(p,y));if(step<EPS)break;
   p={x:p.x+dx[0]*step,y:p.y+dx[1]*step};out.push(p);if(R.dist(p,x)<EPS)i++;if(R.dist(p,y)<EPS)j++;
  }return R.simplify(out);
 }
 // Dots are derived from actual common prefixes, never persisted as new IR
 // vertices or used as a reason to reject otherwise legal manual movement.
 function markers(graph){if(!graph.generic||graph.edges.length>300)return [];
  const J=root.SummaryJunctionMarkers,result=new Map();
  for(const es of groups(graph))for(let i=0;i<es.length;i++)for(const b of es.slice(i+1)){const a=es[i],shared=prefix(a.route,b.route),p=shared.at(-1);
   if(shared.length<2||R.dist(shared[0],p)<9||J.rays([a.route,b.route],p).size<3)continue;
   const id='value-fork:'+key(a)+':'+p.x+':'+p.y,prior=result.get(id),edges=[...new Set([...(prior?.edges||[]),a.id,b.id])];
   result.set(id,{id,point:p,owner:a.source,edges,wire:a.contract.wire,radius:2.7,fill:a.stroke||'#263b4b'});
  }return [...result.values()];
 }
 function fanouts(graph,options={},budgetMs=600){
  if(graph.nodes.length>300||graph.edges.length>300||options.policy==='never'||options.style&&options.style!=='orthogonal')return;
  const C=root.SummaryConstraints,P=root.SummaryPhysicalPorts,N=root.SummaryEngine,started=performance.now(),context=C.validationContext(graph),by=new Map(graph.nodes.map(n=>[n.id,n])),before=R.stats(graph.edges),inkBefore=ink(graph.edges);let accepted=0,attempted=0;
  for(const es of groups(graph)){
   if(options.flowEdges&&!es.some(e=>options.flowEdges.has(e.id)))continue;
   // Try a whole fan-out as a transaction first. Changing one branch alone
   // can temporarily duplicate the old trunk and hide a better shared tree.
   const snapshot=es.map(e=>({route:e.route,physicalSource:e.physicalSource,physicalTarget:e.physicalTarget}));
   const baseStats=R.stats(graph.edges),baseInk=ink(graph.edges);let bestTree=null,bestTreeCost=baseInk+40*baseStats.bends+450*baseStats.crossings;
   for(const anchor of es){
    if(options.flowEdges&&es.some(e=>!options.flowEdges.has(e.id)))break;
    if(performance.now()-started>=budgetMs)break;
    const source=P.active(anchor,'source');
    for(let i=1;i<anchor.route.length;i++){
     if(performance.now()-started>=budgetMs)break;
     const a=anchor.route[i-1],b=anchor.route[i],vertical=Math.abs(a.x-b.x)<EPS,axis=vertical?'y':'x';
     const splits=[b,...es.flatMap(e=>P.candidates(graph,e,'target',options.sides).map(port=>{const t=P.point(by.get(e.target),port);return vertical?{x:a.x,y:t.y+R.SIDE[port.side][1]*24}:{x:t.x+R.SIDE[port.side][0]*24,y:a.y};}))];
     for(const q of splits){
      if(performance.now()-started>=budgetMs)break;
      if(q[axis]<Math.min(a[axis],b[axis])-EPS||q[axis]>Math.max(a[axis],b[axis])+EPS)continue;
      const trunk=R.simplify([...anchor.route.slice(0,i),q]);if(R.dist(trunk[0],q)<9)continue;
      const rows=[];let valid=true;
      for(const e of es){
       if(e===anchor){rows.push({route:e.route,physicalSource:source,physicalTarget:P.active(e,'target')});continue;}
       if(!P.permitted(graph,e,'source',source)){valid=false;break;}
       let choice=null,cost=Infinity;
       for(const target of P.candidates(graph,e,'target',options.sides)){
        const t=P.point(by.get(e.target),target);
        for(const turn of [{x:q.x,y:t.y},{x:t.x,y:q.y}]){
         const route=R.simplify([...trunk,turn,t]),stats=R.stats([{route}]);if(stats.length+40*stats.bends>=cost)continue;
         const candidate={...e,route,physicalSource:source,physicalTarget:target};attempted++;
         if(!C.validate(graph,candidate,route,context).ok||N.overlapsWire(graph,candidate,route))continue;
         choice={route,physicalSource:source,physicalTarget:target};cost=stats.length+40*stats.bends;
        }
       }if(!choice){valid=false;break;}rows.push(choice);
      }
      if(!valid)continue;
      es.forEach((e,j)=>Object.assign(e,rows[j]));
      const stats=R.stats(graph.edges),painted=ink(graph.edges),cost=painted+40*stats.bends+450*stats.crossings;
      if(painted<baseInk-EPS&&stats.length<=baseStats.length*1.04&&stats.bends<=baseStats.bends+1&&stats.crossings<=baseStats.crossings&&cost<bestTreeCost-EPS){bestTree=rows;bestTreeCost=cost;}
      es.forEach((e,j)=>Object.assign(e,snapshot[j]));
     }
    }
   }
   if(bestTree){es.forEach((e,j)=>Object.assign(e,bestTree[j]));accepted++;}
   for(const e of es){
    if(options.flowEdges&&!options.flowEdges.has(e.id))continue;
    if(performance.now()-started>=budgetMs)break;
    const saved={route:e.route,physicalSource:e.physicalSource,physicalTarget:e.physicalTarget},base=R.stats(graph.edges),baseInk=ink(graph.edges);let best=null,bestScore=baseInk+40*base.bends+450*base.crossings;
    const target=by.get(e.target),ports=P.candidates(graph,e,'target',options.sides),oldLength=R.stats([{route:saved.route}]).length;
    for(const anchor of es.filter(a=>a!==e)){
     const source=P.active(anchor,'source');if(!P.permitted(graph,e,'source',source))continue;
     for(const tPort of ports){const t=P.point(target,tPort),normal=R.SIDE[tPort.side],stub=24;
      for(let i=1;i<anchor.route.length;i++){
       if(performance.now()-started>=budgetMs)break;
       const a=anchor.route[i-1],b=anchor.route[i],vertical=Math.abs(a.x-b.x)<EPS,axis=vertical?'y':'x';
       const projected=vertical?{x:a.x,y:t.y+normal[1]*stub}:{x:t.x+normal[0]*stub,y:a.y};
       const points=[b,projected].filter(p=>p[axis]>=Math.min(a[axis],b[axis])-EPS&&p[axis]<=Math.max(a[axis],b[axis])+EPS);
       for(const q of points)for(const bend of [{x:q.x,y:t.y},{x:t.x,y:q.y}]){
        const route=R.simplify([...anchor.route.slice(0,i),q,bend,t]);if(prefix(route,anchor.route).length<2)continue;
        e.route=route;e.physicalSource=source;e.physicalTarget=tPort;
        const candidateInk=ink(graph.edges),local=R.stats([e]);
        if(candidateInk>=baseInk-EPS||local.length>oldLength+base.length*.04||local.bends>saved.route.length)continue;
        attempted++;
        if(!C.validate(graph,e,route,context).ok||N.overlapsWire(graph,e,route))continue;
        const stats=R.stats(graph.edges),cost=candidateInk+40*stats.bends+450*stats.crossings;
        if(stats.crossings>base.crossings||stats.length>base.length*1.04||stats.bends>base.bends+1||cost>=bestScore-EPS)continue;
        best={route,physicalSource:source,physicalTarget:tPort};bestScore=cost;
       }
      }
     }
    }
    Object.assign(e,best||saved);if(best)accepted++;
   }
   if(performance.now()-started>=budgetMs)break;
  }
  graph.nativeFanoutRefinement={accepted,attempted,before,after:R.stats(graph.edges),inkBefore,inkAfter:ink(graph.edges),forks:markers(graph).length,ms:performance.now()-started};
 }
 // Remove local doglegs without replacing a whole cross-frame corridor.
 // Exact fan-outs are one transaction: shortening just one branch can
 // temporarily duplicate the trunk that its sibling still follows.
 function shortcuts(graph,options={},budgetMs=400){
  if(graph.nodes.length>300||graph.edges.length>300||options.policy==='never'||options.style&&options.style!=='orthogonal')return;
  const C=root.SummaryConstraints,N=root.SummaryEngine,context=C.validationContext(graph),started=performance.now(),before=R.stats(graph.edges),inkBefore=ink(graph.edges);let accepted=0,attempted=0;
  const safe=e=>e.style==='orthogonal'&&!e.draft&&!e.failed&&!e.pendingRouting&&!e.contract?.bus&&!e.waypoints?.length&&(!options.flowEdges||options.flowEdges.has(e.id));
  const shared=groups(graph),seen=new Set(shared.flat()),batches=[...shared.map(es=>es.filter(safe)),...graph.edges.filter(e=>!seen.has(e)&&safe(e)).map(e=>[e])].filter(es=>es.length).sort((a,b)=>Math.max(...b.map(e=>e.route.length))-Math.max(...a.map(e=>e.route.length)));
  const crosses=(e,route)=>graph.edges.filter(v=>v!==e).reduce((sum,v)=>sum+route.slice(1).reduce((s,p,i)=>s+v.route.slice(1).filter((q,j)=>R.crossing(route[i],p,v.route[j],q)).length,0),0);
  for(const es of batches){
   if(performance.now()-started>=budgetMs)break;
   const saved=es.map(e=>e.route),base=R.stats(graph.edges),oldInk=ink(graph.edges);let changed=false;
   for(const e of es){
    // Two passes can simplify a long route at both ends. Ports and middle
    // boundary transitions stay registered and every complete path is checked.
    for(let pass=0;pass<2;pass++){
     if(performance.now()-started>=budgetMs)break;
     const route=e.route,stats=R.stats([e]),crossings=crosses(e,route);let best=null,bestCost=stats.length+40*stats.bends;
     for(let span=route.length-1;span>=2;span--)for(let i=0;i+span<route.length;i++){
      if(performance.now()-started>=budgetMs)break;
      const j=i+span,a=route[i],b=route[j];
      for(const turn of [{x:a.x,y:b.y},{x:b.x,y:a.y}]){
       const ps=R.simplify([...route.slice(0,i+1),turn,...route.slice(j)]),s=R.stats([{route:ps}]),cost=s.length+40*s.bends;
       if(cost>=bestCost-EPS||s.length>stats.length+EPS||s.bends>stats.bends)continue;
       attempted++;
       if(!C.validate(graph,e,ps,context).ok||N.overlapsWire(graph,e,ps)||crosses(e,ps)>crossings)continue;
       best=ps;bestCost=cost;
      }
     }
     if(!best)break;e.route=best;changed=true;
    }
   }
   const after=R.stats(graph.edges),painted=ink(graph.edges);
   if(changed&&after.length<=base.length+EPS&&after.bends<=base.bends&&after.crossings<=base.crossings&&painted<=oldInk+EPS&&es.every(e=>C.validate(graph,e,e.route,context).ok&&!N.overlapsWire(graph,e,e.route))){accepted++;}
   else es.forEach((e,i)=>{e.route=saved[i];});
  }
  graph.nativeShortcutRefinement={accepted,attempted,before,after:R.stats(graph.edges),inkBefore,inkAfter:ink(graph.edges),ms:performance.now()-started};
 }
 // Separate long, almost coincident unrelated lanes. Exact overlap was
 // already illegal, but a 1px gap could previously pass as perfectly clear.
 function proximity(edges,gap=12){let cost=0;
  for(let i=0;i<edges.length;i++)for(const b of edges.slice(i+1)){
   const a=edges[i];if(key(a)===key(b)||a.style!=='orthogonal'||b.style!=='orthogonal')continue;
   for(let j=1;j<a.route.length;j++)for(let k=1;k<b.route.length;k++){
    const p=a.route[j-1],q=a.route[j],r=b.route[k-1],s=b.route[k],v=Math.abs(p.x-q.x)<EPS;if(v!==(Math.abs(r.x-s.x)<EPS))continue;
    const along=v?'y':'x',across=v?'x':'y',length=Math.min(Math.max(p[along],q[along]),Math.max(r[along],s[along]))-Math.max(Math.min(p[along],q[along]),Math.min(r[along],s[along])),distance=Math.abs(p[across]-r[across]);
    if(length>=40&&distance<gap)cost+=length*(gap-distance)/gap;
   }
  }return cost;
 }
 function separate(graph,options={},budgetMs=300){
  if(graph.nodes.length>300||graph.edges.length>300||options.policy==='never'||options.edgeSpacing===0||options.style&&options.style!=='orthogonal')return;
  const C=root.SummaryConstraints,N=root.SummaryEngine,context=C.validationContext(graph),started=performance.now(),before=R.stats(graph.edges),gap=Math.max(9,Math.min(24,options.edgeSpacing||12)),nearBefore=proximity(graph.edges,gap);let accepted=0,attempted=0;
  const safe=e=>e.style==='orthogonal'&&!e.draft&&!e.failed&&!e.pendingRouting&&!e.contract?.bus&&!e.waypoints?.length&&(!options.flowEdges||options.flowEdges.has(e.id));
  const shared=groups(graph),seen=new Set(shared.flat()),batches=[...shared.map(es=>es.filter(safe)),...graph.edges.filter(e=>!seen.has(e)&&safe(e)).map(e=>[e])].filter(es=>es.length);
  const weights=new Map();for(let i=0;i<graph.edges.length;i++)for(const b of graph.edges.slice(i+1)){const a=graph.edges[i],value=proximity([a,b],gap);weights.set(a,(weights.get(a)||0)+value);weights.set(b,(weights.get(b)||0)+value);}
  if(options.borderClearance)for(const e of graph.edges)weights.set(e,(weights.get(e)||0)+borders(graph,e.route).cost);
  batches.sort((a,b)=>b.reduce((n,e)=>n+(weights.get(e)||0),0)-a.reduce((n,e)=>n+(weights.get(e)||0),0));
  for(const es of batches){
   if(performance.now()-started>=budgetMs)break;
   const border=ps=>options.borderClearance?borders(graph,ps):{cost:0,xs:[],ys:[]},saved=es.map(e=>e.route),base=R.stats(graph.edges),oldInk=ink(graph.edges),oldNear=proximity(graph.edges,gap),oldBorder=es.reduce((v,e)=>v+border(e.route).cost,0);let best=null,bestCost=base.length+40*base.bends+oldNear+oldBorder;
   for(const anchor of es)for(let i=1;i<anchor.route.length-2;i++){
    if(performance.now()-started>=budgetMs)break;
    const a=anchor.route[i],b=anchor.route[i+1],v=Math.abs(a.x-b.x)<EPS,axis=v?'x':'y',along=v?'y':'x',lanes=new Set();
    for(const other of graph.edges)if(key(other)!==key(anchor)&&other.style==='orthogonal')for(let j=1;j<other.route.length;j++){
     const p=other.route[j-1],q=other.route[j];if(v!==(Math.abs(p.x-q.x)<EPS)||Math.abs(a[axis]-p[axis])>=gap)continue;
     const overlap=Math.min(Math.max(a[along],b[along]),Math.max(p[along],q[along]))-Math.max(Math.min(a[along],b[along]),Math.min(p[along],q[along]));
     if(overlap>=40){lanes.add(p[axis]-gap);lanes.add(p[axis]+gap);}
    }
    const boundary=border([a,b]);for(const lane of v?boundary.xs:boundary.ys)lanes.add(lane);
    for(const lane of lanes){
     if(performance.now()-started>=budgetMs)break;
     // Move matching common segments together; their individual terminals
     // and every unrelated route remain fixed.
     const routes=saved.map(ps=>{const out=ps.map(p=>({...p}));for(let j=1;j<ps.length-2;j++)if(Math.abs(ps[j][axis]-a[axis])<EPS&&Math.abs(ps[j+1][axis]-a[axis])<EPS&&Math.min(Math.max(ps[j][along],ps[j+1][along]),Math.max(a[along],b[along]))-Math.max(Math.min(ps[j][along],ps[j+1][along]),Math.min(a[along],b[along]))>EPS){out[j][axis]=lane;out[j+1][axis]=lane;}return R.simplify(out);});
     if(routes.some((ps,j)=>ps.length<2||R.dist(ps[0],ps[1])+EPS<Math.min(9,R.dist(saved[j][0],saved[j][1]))||R.dist(ps.at(-1),ps.at(-2))+EPS<Math.min(9,R.dist(saved[j].at(-1),saved[j].at(-2)))))continue;
     es.forEach((e,j)=>{e.route=routes[j];});attempted++;
     const after=R.stats(graph.edges),near=proximity(graph.edges,gap),candidateBorder=es.reduce((v,e)=>v+border(e.route).cost,0),cost=after.length+40*after.bends+near+candidateBorder;
     if(near<=oldNear+EPS&&candidateBorder<=oldBorder+EPS&&(near<oldNear-EPS||candidateBorder<oldBorder-EPS)&&cost<bestCost-EPS&&after.length<=base.length*1.03&&after.bends<=base.bends&&after.crossings<=base.crossings&&ink(graph.edges)<=oldInk*1.03&&es.every(e=>C.validate(graph,e,e.route,context).ok&&!N.overlapsWire(graph,e,e.route))){best=routes;bestCost=cost;}
     es.forEach((e,j)=>{e.route=saved[j];});
    }
   }
   if(best){es.forEach((e,j)=>{e.route=best[j];});accepted++;}
  }
  graph[options.borderClearance?'nativeBorderRefinement':'nativeSeparationRefinement']={accepted,attempted,before,after:R.stats(graph.edges),nearBefore,nearAfter:proximity(graph.edges,gap),ms:performance.now()-started};
 }
 // Route an unordered parallel row and its immediate feeders together. Reserve
 // the consumer's facing side in geometric order, and the opposite face of
 // each producer for its inputs. Operand identities never change with x order.
 function convergence(graph,options={},budgetMs=700){
  if(graph.nodes.length>300||graph.edges.length>300||options.sides==='lr'||options.policy==='never'||options.style&&options.style!=='orthogonal')return;
  const G=root.SummaryNativeSemantic,C=root.SummaryConstraints,P=root.SummaryPhysicalPorts,N=root.SummaryEngine,started=performance.now(),before=R.stats(graph.edges),records=[];let attempted=0;
  const by=new Map(graph.nodes.map(n=>[n.id,n])),safe=n=>n&&!n.expanded&&!n.junction&&!['opaque','state','buffer','control','parameter','interface'].includes(n.semantic?.kind)&&!n.semantic?.mutable&&!n.semantic?.condition&&!n.semantic?.invocation_binding;
  const score=g=>{const s=R.stats(g.edges);return ink(g.edges)+40*s.bends+450*s.crossings+proximity(g.edges)+borderInk(g)*.5;};
  const complexity=n=>{const row=graph.edges.filter(e=>e.target===n.id&&safe(by.get(e.source))).map(e=>e.source);return new Set(graph.edges.filter(e=>row.includes(e.target)).map(key)).size;};
  for(const sink of graph.nodes.filter(safe).sort((a,b)=>complexity(b)-complexity(a))){
   if(performance.now()-started>=budgetMs)break;
   const ins=graph.edges.filter(e=>e.target===sink.id&&eligible(e,by)&&safe(by.get(e.source))&&by.get(e.source).parent===sink.parent),rows=new Map();
   for(const e of ins){const n=by.get(e.source),k=Math.round(n.y);if(!rows.has(k))rows.set(k,[]);rows.get(k).push(e);}
   for(const es of rows.values()){
    if(es.length<2||es.length>4||new Set(es.map(e=>e.source)).size!==es.length)continue;
    es.sort((a,b)=>by.get(a.source).x-by.get(b.source).x);const ids=new Set(es.map(e=>e.source)),up=es.every(e=>by.get(e.source).y>=sink.y+sink.h+18),down=es.every(e=>by.get(e.source).y+by.get(e.source).h<=sink.y-18);
    if(!up&&!down||graph.edges.some(e=>ids.has(e.source)&&ids.has(e.target)))continue;
    const affected=graph.edges.filter(e=>ids.has(e.source)||ids.has(e.target)||e.target===sink.id),feeders=affected.filter(e=>!es.includes(e));
    if(affected.some(e=>!eligible(e,by)||options.flowEdges&&!options.flowEdges.has(e.id))||feeders.some(e=>ids.has(e.source)))continue;
    const row=es.map(e=>by.get(e.source)),proposals=[...(options.reorderRows===false?[]:rowCandidates(graph)).filter(p=>p.from.length===row.length&&p.from.every(id=>ids.has(id))).map(p=>p.order),row.map(n=>n.id)];
    const base=R.stats(graph.edges),baseInk=ink(graph.edges),baseNear=proximity(graph.edges),baseBorder=borderInk(graph);let best=null,bestCost=score(graph);
    for(const order of proposals){
     if(performance.now()-started>=budgetMs)break;
     const cg=G.cloneGeometry(graph),nodes=new Map(cg.nodes.map(n=>[n.id,n])),edges=new Map(cg.edges.map(e=>[e.id,e])),group=affected.map(e=>edges.get(e.id)),saved=new Map(group.map(e=>[e.id,e.route]));let x=row[0].x;
     for(const [i,id]of order.entries()){nodes.get(id).x=x;x+=nodes.get(id).w+(i<row.length-1?row[i+1].x-row[i].x-row[i].w:0);}
     const ctx=C.validationContext(cg);let ok=true;
     for(const e of group)e.route=[];
     for(const [i,id]of order.entries()){const e=edges.get(es.find(v=>v.source===id).id),source=nodes.get(id),target=nodes.get(sink.id),a={side:up?'top':'bottom',fraction:.5},b={side:up?'bottom':'top',fraction:(i+1)/(order.length+1)},s=P.point(source,a),t=P.point(target,b),y=(s.y+t.y)/2;
      Object.assign(e,{physicalSource:a,physicalTarget:b,route:R.simplify([s,{x:s.x,y},{x:t.x,y},t])});
     }
     // Joint port assignment precedes validation, so old occupied fractions
     // cannot incorrectly veto a new, mutually spaced allocation.
     if(es.some(v=>{const e=edges.get(v.id);return !C.validate(cg,e,e.route,ctx).ok||N.overlapsWire(cg,e,e.route);}))continue;
     for(const old of feeders){
      if(performance.now()-started>=budgetMs){ok=false;break;}
      const e=edges.get(old.id),target=nodes.get(e.target),lateral=e.target===sink.id,targetPorts=lateral?[...['right','left'].map(side=>({side,fraction:.5})),{side:up?'top':'bottom',fraction:.25},{side:up?'top':'bottom',fraction:.75}].filter(p=>options.sides!=='tb'||['top','bottom'].includes(p.side)):[{side:up?'bottom':'top',fraction:.5}],peers=cg.edges.filter(v=>v!==e&&key(v)===key(e)&&v.route.length),sources=peers.length?[P.active(peers[0],'source')]:P.candidates(cg,e,'source',options.sides);let choice=null,cost=Infinity;
      for(const targetPort of targetPorts)for(const a of sources){const t=P.point(target,targetPort);const s=P.point(nodes.get(e.source),a),sideLanes=[Math.min(...row.map(n=>n.x))-14,Math.max(...row.map(n=>n.x+n.w))+14],lanes=[t.y+(up?1:-1)*18,t.y+(up?1:-1)*30],paths=[[s,{x:s.x,y:t.y},t],[s,{x:t.x,y:s.y},t],...lanes.map(y=>[s,{x:s.x,y},{x:t.x,y},t])];
       for(const original of [saved.get(e.id),...peers.map(v=>v.route)])for(let cut=1;cut<original.length;cut++){const prefix=original.slice(0,cut+1);if(R.dist(prefix[0],s)>EPS)continue;for(const y of lanes)paths.push([...prefix,{x:prefix.at(-1).x,y},{x:t.x,y},t]);if(lateral)for(const x of sideLanes){const normal=R.SIDE[targetPort.side],stub={x:t.x+normal[0]*18,y:t.y+normal[1]*18};paths.push([...prefix,{x,y:prefix.at(-1).y},{x,y:stub.y},stub,t]);}}
       for(const ps of paths){const route=R.simplify(ps),st=R.stats([{route}]),cross=cg.edges.filter(v=>v!==e).reduce((v,b)=>v+route.slice(1).reduce((v,p,i)=>v+b.route.slice(1).filter((q,j)=>R.crossing(route[i],p,b.route[j],q)).length,0),0),value=st.length+40*st.bends+450*cross;
        if(value>=cost)continue;const candidate={...e,physicalSource:a,physicalTarget:targetPort};attempted++;
        if(!C.validate(cg,candidate,route,ctx).ok||N.overlapsWire(cg,e,route))continue;
        choice={route,physicalSource:a,physicalTarget:targetPort};cost=value;
       }
      }
      if(!choice){ok=false;break;}Object.assign(e,choice);
     }
     if(!ok)continue;
     const st=R.stats(cg.edges),value=score(cg),border=borderInk(cg),check=N.validateView(cg);
     if(check.source.ok&&check.layout.ok&&check.edges.every(([,v])=>v.ok)&&st.crossings<=base.crossings&&st.bends<=base.bends&&st.length<=base.length*1.01&&ink(cg.edges)<=baseInk*1.01&&proximity(cg.edges)<=baseNear+EPS&&border<=baseBorder+EPS&&value<bestCost-EPS){best=cg;bestCost=value;}
    }
    if(best){Object.assign(graph,{nodes:best.nodes,edges:best.edges});records.push({consumer:sink.id,members:[...ids],before:base,after:R.stats(graph.edges)});}
   }
  }
  graph.nativeConvergenceRefinement={attempted,accepted:records.length,records,before,after:R.stats(graph.edges),ms:performance.now()-started};
 }
 // Internal lane shifts cannot clear a long terminal ray: its x/y is tied to
 // a physical slot. Slide that presentation slot along the same face instead.
 // The registered operand/value and canonical port remain immutable.
 function terminals(graph,options={},budgetMs=200){
  if(graph.nodes.length>300||graph.edges.length>300||options.policy==='never'||options.edgeSpacing===0||options.style&&options.style!=='orthogonal')return;
  const P=root.SummaryPhysicalPorts,C=root.SummaryConstraints,N=root.SummaryEngine,started=performance.now(),ctx=C.validationContext(graph),by=new Map(graph.nodes.map(n=>[n.id,n])),gap=Math.max(9,Math.min(24,options.edgeSpacing||12)),before=R.stats(graph.edges),nearBefore=proximity(graph.edges,gap),borderBefore=borderInk(graph);let accepted=0,attempted=0;
  const queue=graph.edges.filter(e=>e.style==='orthogonal'&&!e.draft&&!e.failed&&!e.pendingRouting&&!e.contract?.bus&&!e.waypoints?.length&&e.route.length>=4&&(!options.flowEdges||options.flowEdges.has(e.id))).map(e=>({e,cost:borders(graph,e.route).cost+graph.edges.filter(v=>v!==e).reduce((n,v)=>n+proximity([e,v],gap),0)})).filter(v=>v.cost>EPS).sort((a,b)=>b.cost-a.cost);
  for(const {e}of queue){
   if(performance.now()-started>=budgetMs)break;
   const saved={route:e.route,physicalSource:e.physicalSource,physicalTarget:e.physicalTarget},base=R.stats(graph.edges),oldInk=ink(graph.edges),near=proximity(graph.edges,gap),border=borderInk(graph);let best=null,bestCost=base.length+40*base.bends+near+border;
   for(const which of ['target','source']){
    if(e.portPolicy?.[which].mode!=='free')continue;
    const node=by.get(e[which]),port=P.active(e,which),vertical=['top','bottom'].includes(port.side),size=vertical?node.w:node.h;
    if(node.junction||node.expanded||port.inward||port.offset||options.sides==='lr'&&vertical||options.sides==='tb'&&!vertical)continue;
    for(const delta of [-gap,gap,-2*gap,2*gap]){
     if(performance.now()-started>=budgetMs)break;
     Object.assign(e,saved);const candidate={...port,fraction:port.fraction+delta/size};if(!P.permitted(graph,e,which,candidate))continue;
     const route=saved.route.map(p=>({...p})),end=which==='source'?0:route.length-1,next=which==='source'?1:route.length-2,axis=vertical?'x':'y';
     route[end][axis]+=delta;route[next][axis]+=delta;e.route=R.simplify(route);e[which==='source'?'physicalSource':'physicalTarget']=candidate;attempted++;
     if(!C.validate(graph,e,e.route,ctx).ok||N.overlapsWire(graph,e,e.route))continue;
     const s=R.stats(graph.edges),n=proximity(graph.edges,gap),b=borderInk(graph),cost=s.length+40*s.bends+n+b;
     if(n<=near+EPS&&b<=border+EPS&&(n<near-EPS||b<border-EPS)&&s.crossings<=base.crossings&&s.bends<=base.bends&&s.length<=base.length*1.03&&ink(graph.edges)<=oldInk*1.03&&cost<bestCost-EPS){best={route:e.route,physicalSource:e.physicalSource,physicalTarget:e.physicalTarget};bestCost=cost;}
    }
   }
   Object.assign(e,best||saved);if(best)accepted++;
  }
  graph.nativeTerminalRefinement={accepted,attempted,before,after:R.stats(graph.edges),nearBefore,nearAfter:proximity(graph.edges,gap),borderBefore,borderAfter:borderInk(graph),ms:performance.now()-started};
 }
 function rowCandidates(graph){const by=new Map(graph.nodes.map(n=>[n.id,n])),children=new Map(),out=[];
  for(const n of graph.nodes){if(!children.has(n.parent))children.set(n.parent,[]);children.get(n.parent).push(n);}
  const safe=n=>{const s=n.semantic||{};return !['opaque','control','state','buffer','parameter','interface'].includes(s.kind)&&!s.mutable&&!s.identity_display&&!s.observed_calls&&!s.invocation_binding&&!s.condition&&!s.conditions&&!s.guard&&
   !['serial-repeat','repeat-instance','serial-remainder','loop-template','iteration-region','conditional-collection','branch-region'].includes(s.semantic_type)&&(children.get(n.id)||[]).every(safe);};
  for(const [parent,kids]of children){if(!parent||!by.get(parent)?.expanded)continue;
   const ids=new Set(kids.map(n=>n.id)),owner=id=>{while(id&&!ids.has(id))id=by.get(id)?.parent;return id;},adj=new Map(kids.map(n=>[n.id,new Set()]));let guarded=false;
   for(const e of graph.edges){const a=owner(e.source),b=owner(e.target),members=e.binding?.bundle_members||[e.binding||{}];
    if((a||b)&&members.some(m=>m.iteration||['state-write','effect'].includes(m.kind))){guarded=true;break;}
    if(a&&b&&a!==b)adj.get(a).add(b);
   }if(guarded)continue;
   const reaches=(a,b,seen=new Set())=>{if(a===b)return true;if(seen.has(a))return false;seen.add(a);return [...adj.get(a)].some(c=>reaches(c,b,seen));};
   const rows=new Map();for(const n of kids.filter(safe)){const k=Math.round(n.y);if(!rows.has(k))rows.set(k,[]);rows.get(k).push(n);}
   for(const row of rows.values()){
    if(row.length<2||row.length>4||row.some(a=>row.some(b=>a!==b&&(reaches(a.id,b.id)||reaches(b.id,a.id)))))continue;
    row.sort((a,b)=>a.x-b.x);if(row.some((n,i)=>i&&n.x<row[i-1].x+row[i-1].w+12))continue;
    const edgeRows=graph.edges.map(e=>({e,a:owner(e.source),b:owner(e.target)})).filter(({e})=>['data','alias','interface-binding'].includes(e.binding?.kind));
    const gaps=row.slice(1).map((n,i)=>n.x-row[i].x-row[i].w),perms=xs=>xs.length<2?[xs]:xs.flatMap(n=>perms(xs.filter(v=>v!==n)).map(p=>[n,...p]));
    const proposal=order=>{let x=row[0].x;const positions=new Map();for(const [i,n]of order.entries()){positions.set(n.id,x);x+=n.w+(gaps[i]||0);}return positions;};
    const cost=positions=>{let sum=0;const center=id=>positions.has(id)?positions.get(id)+by.get(id).w/2:by.get(id).x+by.get(id).w/2;
     for(const {e,a,b}of edgeRows){if(positions.has(b)&&!positions.has(a))sum+=2*Math.abs(center(b)-(a?center(a):by.get(e.source).x+by.get(e.source).w/2));if(positions.has(a)&&!positions.has(b))sum+=Math.abs(center(a)-(b?center(b):by.get(e.target).x+by.get(e.target).w/2));}
     const common=new Map();for(const {e,b}of edgeRows)if(positions.has(b)&&!positions.has(owner(e.source))){const k=key(e);if(!common.has(k))common.set(k,new Set());common.get(k).add(b);}
     // Keep consumers of one exact input contiguous when their other costs
     // tie. This is independent of role names and of source declaration order.
     for(const ids of common.values())if(ids.size>1){const xs=[...ids].map(center),lo=Math.min(...xs),hi=Math.max(...xs);for(const n of row)if(!ids.has(n.id)&&center(n.id)>lo&&center(n.id)<hi)sum+=2*(n.w+32);}
     return sum;};
    const baseline=cost(proposal(row)),trials=perms(row).map(order=>({parent,order:order.map(n=>n.id),positions:proposal(order)})).map(p=>({...p,cost:cost(p.positions)})).filter(p=>p.cost<baseline-EPS).sort((a,b)=>a.cost-b.cost).slice(0,2);
    out.push(...trials.map(p=>({...p,from:row.map(n=>n.id),gain:baseline-p.cost})));
   }
  }return out.sort((a,b)=>b.gain-a.gain);
 }
 function reorder(graph,options={},budgetMs=2200){
  if(graph.nodes.length>300||graph.edges.length>300||options.policy==='never'||options.style&&options.style!=='orthogonal')return;
  const G=root.SummaryNativeSemantic,C=root.SummaryConstraints,N=root.SummaryEngine,started=performance.now(),before=R.stats(graph.edges),records=[],trials=[],done=new Set();let attempted=0;
  for(const proposal of rowCandidates(graph)){
   if(performance.now()-started>=budgetMs)break;
   if(done.has(proposal.parent+':'+proposal.from.join('|')))continue;
   const candidate=G.cloneGeometry(graph),oldX=new Map(graph.nodes.map(n=>[n.id,n.x])),by=new Map(candidate.nodes.map(n=>[n.id,n])),moved=new Set(),shift=(id,dx)=>{const n=by.get(id);n.x+=dx;moved.add(id);for(const c of candidate.nodes)if(c.parent===id)shift(c.id,dx);};
   for(const [id,x]of proposal.positions)if(Math.abs(by.get(id).x-x)>EPS)shift(id,x-by.get(id).x);
   const context=C.validationContext(candidate),affected=new Set();
   for(const e of candidate.edges){
    const dx=by.get(e.source).x-oldX.get(e.source),tx=by.get(e.target).x-oldX.get(e.target);
    if(dx||tx){
     const ps=e.route.map(p=>({...p}));
     if(Math.abs(dx-tx)<EPS)for(const p of ps)p.x+=dx;
     else {
      // Transfer the terminal ray with its module. A vertical ray needs its
      // elbow translated too; a horizontal ray only needs its endpoint.
      // Shared evidence and already legal intermediate channels stay intact.
      if(ps.length>2){if(Math.abs(ps[0].x-ps[1].x)<EPS)ps[1].x+=dx;if(Math.abs(ps.at(-1).x-ps.at(-2).x)<EPS)ps.at(-2).x+=tx;}
      ps[0].x+=dx;ps.at(-1).x+=tx;
     }
     e.route=R.simplify(ps);
    }
   }
   for(const e of candidate.edges)if(moved.has(e.source)&&!moved.has(e.target)||!C.validate(candidate,e,e.route,context).ok||N.overlapsWire(candidate,e,e.route)){affected.add(e.id);e.pendingRouting=true;}
   attempted++;
   candidate.nativeRouting={pending:affected.size,failed:0,complete:false};
   G.route(candidate,{...options,refinePlacement:false,refineCrossings:false,refineChannels:false,refineFlow:false,preferCurrentPorts:false,budgetMs:Math.min(1200,Math.max(0,budgetMs-(performance.now()-started)))});
   if(candidate.edges.some(e=>e.failed||e.pendingRouting)){trials.push({from:proposal.from,to:proposal.order,pending:candidate.edges.filter(e=>e.pendingRouting).length,failed:candidate.edges.filter(e=>e.failed&&!e.pendingRouting).length});continue;}
   fanouts(candidate,options,Math.min(160,Math.max(0,budgetMs-(performance.now()-started))));
   const old=R.stats(graph.edges),after=R.stats(candidate.edges),oldInk=ink(graph.edges),afterInk=ink(candidate.edges),check=N.validateView(candidate);
   trials.push({from:proposal.from,to:proposal.order,before:old,after,inkBefore:oldInk,inkAfter:afterInk,valid:check.source.ok&&check.layout.ok&&check.edges.every(([,v])=>v.ok)});
   if(check.source.ok&&check.layout.ok&&check.edges.every(([,v])=>v.ok)&&after.crossings<=old.crossings&&after.bends<=old.bends&&after.length<=old.length+EPS&&afterInk<=oldInk+EPS&&(after.crossings<old.crossings||after.bends<old.bends||afterInk<oldInk-EPS)){
    Object.assign(graph,{nodes:candidate.nodes,edges:candidate.edges});done.add(proposal.parent+':'+proposal.from.join('|'));records.push({parent:proposal.parent,from:proposal.from,to:proposal.order,affected:affected.size,before:old,after});
   }
  }
  graph.nativeSiblingRefinement={attempted,accepted:records.length,records,trials,before,after:R.stats(graph.edges),ms:performance.now()-started};
 }
 const api={groups,ink,borders,borderInk,prefix,markers,fanouts,shortcuts,proximity,separate,convergence,terminals,rowCandidates,reorder};root.SummaryFlowOptimizer=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
