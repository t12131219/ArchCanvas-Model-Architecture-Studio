  function localBlockerPortCandidate(graph,e,context,options={}){
    // This inexpensive side-channel candidate never crosses a new interface.
    // Explicit/manual knots retain the complete normal routing path.
    if(options.preserve&&(e.waypoints||[]).length)return null;
    const P=root.SummaryPhysicalPorts,spacing=Math.max(10,options.edgeSpacing||0),normals={left:[-1,0],right:[1,0],top:[0,-1],bottom:[0,1]},related=new Set([...C.ancestors(graph,e.source),...C.ancestors(graph,e.target)]);
    const labels=graph.nodes.filter(n=>n.expanded||n.glyphPresentation).flatMap(n=>(n.labelObstacles||[]).map(b=>({x:n.x+b.x,y:n.y+b.y,w:b.w,h:b.h}))),prior=graph.edges.filter(v=>v!==e&&v.contract?.wire!==e.contract?.wire).map(v=>Object.assign(v.route.slice(),{wire:v.contract?.wire}));
    const requested=options.portOverrides?.[e.id],ports=side=>requested?.[side]?(P.permitted(graph,e,side,requested[side])?[requested[side]]:[]):[e[side==='source'?'fixedSource':'fixedTarget'],P.active(e,side),...P.candidates(graph,e,side,options.sides||'any')].filter((p,i,a)=>p&&P.permitted(graph,e,side,p)&&a.findIndex(v=>JSON.stringify(v)===JSON.stringify(p))===i).slice(0,6);
    const settings={bendCost:options.bendCost??40,crossingCost:options.crossingCost??180,overlapCost:options.overlapCost??2,edgeSpacing:spacing},same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),sources=ports('source'),targets=ports('target');
    // Preserve the recorded port pair first, then the settled physical pair.
    // Alternate licensed ports consume only the remaining bounded budget.
    for(const priority of [0,1,2]){const candidates=new Map();
    for(const source of sources)for(const target of targets){
      const portPriority=same(source,e.fixedSource)&&same(target,e.fixedTarget)?0:same(source,P.active(e,'source'))&&same(target,P.active(e,'target'))?1:2;if(portPriority!==priority)continue;
      const projected={...e,physicalSource:source,physicalTarget:target};
      // Frame transit retains the existing gate-aware candidate/router. This
      // local pass covers a sibling blocker between two endpoint interfaces.
      if(C.activeGates(graph,projected).some(g=>g.frame!==e.source&&g.frame!==e.target))continue;
      const s=E.endpoint(graph,projected,'source'),t=E.endpoint(graph,projected,'target'),ns=normals[source.side],nt=normals[target.side],stub=Math.max(14,e.contract?.minimumTerminal||0),a=C.sharedStemPoint(graph,projected,{...context,boundaryLanes:true})||{x:s.x+ns[0]*stub*(source.inward?-1:1),y:s.y+ns[1]*stub*(source.inward?-1:1)},b={x:t.x+nt[0]*stub*(target.inward?-1:1),y:t.y+nt[1]*stub*(target.inward?-1:1)};
      const trials=[[a,b],[a,{x:a.x,y:b.y},b],[a,{x:b.x,y:a.y},b]],mid={x:(a.x+b.x)/2,y:(a.y+b.y)/2};
      const blockers=graph.nodes.filter(n=>n.expanded&&!related.has(n.id)&&trials.some(ps=>ps.slice(1).some((p,i)=>R.intersectsRect(ps[i],p,n)))).sort((u,v)=>R.dist({x:u.x+u.w/2,y:u.y+u.h/2},mid)-R.dist({x:v.x+v.w/2,y:v.y+v.h/2},mid)||u.id.localeCompare(v.id)).slice(0,4);
      for(const blocker of blockers){const pads=C.laneClearances(graph,projected,blocker,context);
        for(const side of ['left','right','top','bottom'])for(let lane=0;lane<3;lane++){
          const vertical=side==='left'||side==='right',axis=vertical?'x':'y',size=vertical?'w':'h',sign=side==='right'||side==='bottom'?1:-1,coordinate=blocker[axis]+(sign>0?blocker[size]:0)+sign*(Math.max(12,pads[side].outside)+lane*spacing);
          const points=R.simplify(vertical?[s,a,{x:coordinate,y:a.y},{x:coordinate,y:b.y},b,t]:[s,a,{x:a.x,y:coordinate},{x:b.x,y:coordinate},b,t]);
          if(points.length>24||points.slice(1).some((p,i)=>Math.abs(p.x-points[i].x)>EPS&&Math.abs(p.y-points[i].y)>EPS))continue;
          const cost=R.routeCost(points,prior,settings);if(!Number.isFinite(cost))continue;
          const key=JSON.stringify([points,source,target]),entry={points,source,target,projected,cost};if(!candidates.has(key))candidates.set(key,entry);
        }
      }
    }
    // One graph edge receives at most 128 complete validations. Invalid
    // candidates leave every route, port, source record and gate unchanged.
    const limited=[...candidates.values()].sort((a,b)=>a.cost-b.cost||a.points.length-b.points.length).slice(0,priority===1?32:48);
    for(const candidate of limited){
      const {points,projected}=candidate;
      if(points.some(p=>p.x<1||p.y<1||p.x>(graph.canvas?.[0]||Infinity)-1||p.y>(graph.canvas?.[1]||Infinity)-1)||labels.some(box=>points.slice(1).some((p,i)=>R.intersectsRect(points[i],p,box))))continue;
      if(C.validate(graph,projected,points,context).ok&&!C.laneContacts(graph,projected,points,context).length&&!E.overlapsWire(graph,projected,points)&&C.validateJunctions({...graph,edges:graph.edges.map(v=>v===e?{...projected,route:points}:v)}).ok)return {points,source:candidate.source,target:candidate.target};
    }}return null;
  }
