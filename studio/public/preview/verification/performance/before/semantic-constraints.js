/* Geometry contracts derived from recorded source projections, not new tensor facts. */
(function(root){
  'use strict';
  const EPS=1e-5,R=root.EdgeRouterLabRouting;
  const S=root.SummarySourceContracts || (typeof require==='function'?require('./source-contracts.js'):null);
  const P=root.SummaryPhysicalPorts || (typeof require==='function'?require('./physical-ports.js'):null);
  const inside=(p,n)=>p.x>n.x+EPS&&p.x<n.x+n.w-EPS&&p.y>n.y+EPS&&p.y<n.y+n.h-EPS;
  const pointIn=(p,n)=>p.x>=n.x-EPS&&p.x<=n.x+n.w+EPS&&p.y>=n.y-EPS&&p.y<=n.y+n.h+EPS;
  function ancestors(graph,id){const map=new Map(graph.nodes.map(n=>[n.id,n])),ids=[];let n=map.get(id),seen=new Set();while(n&&!seen.has(n.id)){seen.add(n.id);if(n.expanded)ids.push(n.id);n=map.get(n.parent);}return ids;}
  function crossings(points,n){
    const events=[];
    for(let i=1;i<points.length;i++){
      const a=points[i-1],b=points[i],dx=b.x-a.x,dy=b.y-a.y;
      for(const [side,axis,value,low,high]of [['left','x',n.x,n.y,n.y+n.h],['right','x',n.x+n.w,n.y,n.y+n.h],['top','y',n.y,n.x,n.x+n.w],['bottom','y',n.y+n.h,n.x,n.x+n.w]]){
        const delta=axis==='x'?dx:dy;if(Math.abs(delta)<EPS)continue;
        const t=(value-a[axis])/delta;if(t<-EPS||t>1+EPS)continue;
        const p={x:a.x+dx*t,y:a.y+dy*t},along=axis==='x'?p.y:p.x;
        if(along<low-EPS||along>high+EPS)continue;
        const u=Math.max(0,Math.min(1,t)),order=i-1+u;
        if(events.some(e=>Math.abs(e.order-order)<EPS))continue;
        // A border contact on an endpoint is a legitimate named interface.
        // Interior bends touching a border are not silently promoted to gates.
        const before=t>EPS?{x:p.x-dx/Math.hypot(dx,dy)*.02,y:p.y-dy/Math.hypot(dx,dy)*.02}:points[i-2];
        const after=t<1-EPS?{x:p.x+dx/Math.hypot(dx,dy)*.02,y:p.y+dy/Math.hypot(dx,dy)*.02}:points[i+1];
        if(order>EPS&&order<points.length-1-EPS&&(!before||!after||inside(before,n)===inside(after,n)))continue;
        events.push({frame:n.id,side,fraction:(along-low)/(high-low),order,direction:inside(after||b,n)?'enter':'exit'});
      }
    }
    return events.sort((a,b)=>a.order-b.order);
  }
  function wireIdentity(edge){
    const b=edge.binding||{};
    if(b.wire_identity)return JSON.stringify(b.wire_identity);
    if(b.endpoint_binding?.canonical)return JSON.stringify([b.endpoint_binding.canonical.src,b.endpoint_binding.canonical.src_port]);
    if(b.canonical_src)return b.canonical_src;
    if(b.semantic_src)return JSON.stringify([b.semantic_src,b.semantic_src_port||'out']);
    // Trace collections/forks are explicit visual buses, not implicit sums.
    if(['fork_bus','collection_bus'].includes(b.representation))return 'bus:'+JSON.stringify(b.semantic_trace||[]);
    return b.src||edge.id;
  }
  function initialize(graph){
    for(const n of graph.nodes)if(n.junction&&!n.parent){const owners=graph.nodes.filter(v=>v.expanded&&inside({x:n.x,y:n.y},v));if(owners.length)n.parent=owners.sort((a,b)=>a.w*a.h-b.w*b.h)[0].id;}
    for(const e of graph.edges){if(e.contract)continue;
      const relation=new Set([...ancestors(graph,e.source),...ancestors(graph,e.target)]);
      const gates=graph.nodes.filter(n=>n.expanded).flatMap(n=>crossings(e.route,n)).filter(g=>relation.has(g.frame)&&(!e.draft||g.frame===e.source&&e.fixedSource||g.frame===e.target&&e.fixedTarget));
      e.contract={version:1,gates,wire:wireIdentity(e),bus:['fork_bus','collection_bus'].includes(e.binding?.representation),
        source:e.source,target:e.target,originalSourcePort:e.fixedSource,originalTargetPort:e.fixedTarget,
        minimumTerminal:Math.min(9,R.dist(e.route.at(-1)||{},e.route.at(-2)||{})),
        enforcePortApproach:!!(graph.irSha256||graph.caseId==='routing-lab'||e.draft)};
    }
    // The source identity licenses sharing; geometry only records where the
    // existing fan-out splits. The longest common initial segment retains
    // nested forks (residual first, Q/K/V later) without inventing a sum.
    for(const e of graph.edges)if(e.contract.sharedStem===undefined){
      if(e.portPolicy){e.contract.sharedStem=e.portPolicy.source.sharedStem||null;continue;}
      let length=0;const a=e.route[0],b=e.route[1];
      if(a&&b)for(const v of graph.edges)if(v!==e&&v.source===e.source&&v.contract.wire===e.contract.wire&&R.dist(a,v.route[0])<EPS){
        const c=v.route[1];if(c)length=Math.max(length,R.overlap(a,b,a,c));
      }
      e.contract.sharedStem=length>EPS?{side:e.fixedSource?.side,length,axis:Math.abs(a.x-b.x)<EPS?'y':'x',coordinate:Math.abs(a.x-b.x)<EPS?a.y+Math.sign(b.y-a.y)*length:a.x+Math.sign(b.x-a.x)*length}:null;
    }
    return graph;
  }
  function gatePoint(n,g){return R.port(n,g.side,g.fraction);}
  function validateJunctions(graph){const J=root.SummaryJunctionMarkers,violations=[];
    for(const marker of graph.junctionMarkers||[])if(J&&!marker.edges.some(id=>graph.edges.find(e=>e.id===id)?.draft)&&!J.point(graph,marker))
      violations.push('source tensor fork disconnected '+marker.id);
    return {ok:!violations.length,violations};
  }
  function sharedStemPoint(graph,e){const stem=e.portPolicy?.source.sharedStem||e.contract?.sharedStem;if(!stem)return null;
    const owner=graph.nodes.find(n=>n.id===e.source),f=P.active(e,'source');if(!owner||!f||f.side!==stem.side)return null;
    const p=P.point(owner,f),frame=graph.nodes.find(n=>n.id===stem.owner),delta=frame?frame[stem.axis]-(frame.base?.[stem.axis==='x'?0:1]??frame[stem.axis]):0;
    const q=stem.axis==='y'?{x:p.x,y:stem.coordinate+delta}:{x:stem.coordinate+delta,y:p.y};
    // The source licenses a shared fork, not an absolute pixel coordinate.
    // Shorten its common first ray before any painted frame wall. All peers
    // use this same source slot and frame band, so the branch stays shared.
    const peers=graph.edges.filter(v=>v.source===e.source&&v.contract?.wire===e.contract?.wire),axis=stem.axis,along=axis==='x'?'y':'x';
    const sign=Math.sign(q[axis]-p[axis]);let length=Math.abs(q[axis]-p[axis]);
    for(const frame of graph.nodes.filter(n=>n.expanded)){const clearance=borderClearance(e,frame);
      for(const gate of activeGates(graph,e).filter(g=>g.frame===frame.id&&(['left','right'].includes(g.side)?'x':'y')===axis)){
        const wall=gatePoint(frame,gate)[axis],distance=(wall-p[axis])*sign;
        if(distance>0&&Math.abs(length-distance)<clearance+.25)length=distance+clearance+.25;
      }
    }
    for(const frame of graph.nodes.filter(n=>n.expanded)){
      const gates=peers.flatMap(v=>activeGates(graph,v).filter(g=>g.frame===frame.id));
      for(const wall of walls(frame,gates,borderClearance(e,frame))){
        if(p[along]<=wall[along]+EPS||p[along]>=wall[along]+wall[along==='x'?'w':'h']-EPS)continue;
        const entry=sign>0?wall[axis]:wall[axis]+wall[axis==='x'?'w':'h'];
        const distance=(entry-p[axis])*sign;
        if(distance>9&&distance<length)length=distance-.25;
      }
    }
    return {...q,[axis]:p[axis]+sign*length};}
  function activeGates(graph,e){return (e.contract?.gates||[]).map(g=>{
    const anchor=['source','target'].find(s=>e.portPolicy?.[s]?.gates?.some(a=>a.frame===g.frame&&a.side===g.side&&a.anchor===s&&a.direction===g.direction&&Math.abs(a.fraction-g.fraction)<EPS));
    if(anchor){const f=P.active(e,anchor),owner=graph.nodes.find(n=>n.id===e[anchor]),frame=graph.nodes.find(n=>n.id===g.frame);
      if(f&&(['top','bottom'].includes(f.side)===['top','bottom'].includes(g.side))&&owner&&frame){const p=P.point(owner,f),vertical=g.side==='left'||g.side==='right';
        const fraction=(p[vertical?'y':'x']-frame[vertical?'y':'x'])/frame[vertical?'h':'w'];
        if(fraction>0&&fraction<1)return {...g,fraction};}}
    const side=g.frame===e.source?'source':g.frame===e.target?'target':null,f=side&&P.active(e,side);
    return side&&e['physical'+side[0].toUpperCase()+side.slice(1)]&&f.side===g.side?{...g,fraction:f.fraction}:g;
  }).map(g=>{const n=graph.nodes.find(n=>n.id===g.frame);if(!n)return g;
    const size=['left','right'].includes(g.side)?n.h:n.w,pad=(borderClearance(e,n)+1)/size;
    return {...g,fraction:Math.max(pad,Math.min(1-pad,g.fraction))};
  });}
  function borderClearance(e,n){
    // Include the painted shaft and frame strokes, plus a visible air gap.
    const widths=[...n.html?.matchAll(/stroke-width="([\d.]+)"/g)||[]].map(m=>+m[1]);
    return (e.width||2.2)/2+Math.max(2,...widths)/2+2;
  }
  function borderContacts(e,n,points){const hits=[],clearance=borderClearance(e,n);
    for(const side of ['left','right','top','bottom']){
      const vertical=side==='left'||side==='right',axis=vertical?'x':'y',along=vertical?'y':'x';
      const value=n[axis]+(['right','bottom'].includes(side)?n[vertical?'w':'h']:0),low=n[along],high=low+n[vertical?'h':'w'];
      for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i];
        const distance=Math.max(Math.abs(a[axis]-value),Math.abs(b[axis]-value));
        const length=Math.min(high,Math.max(a[along],b[along]))-Math.max(low,Math.min(a[along],b[along]));
        // Perpendicular interface crossings are permitted; travel beside a
        // stroke must keep the whole painted wire outside the clearance band.
        if(length>EPS&&distance<clearance-EPS&&Math.abs(a[axis]-b[axis])<EPS)
          hits.push({frame:n.id,side,segment:i-1,distance,clearance,length});
      }
    }return hits;
  }
  function walls(n,gates,padding=2){
    const result=[],thickness=padding*2;
    for(const side of ['left','right','top','bottom']){
      const vertical=side==='left'||side==='right',low=vertical?n.y:n.x,high=low+(vertical?n.h:n.w),coordinate=side==='left'?n.x:side==='right'?n.x+n.w:side==='top'?n.y:n.y+n.h;
      const gaps=gates.filter(g=>g.side===side).map(g=>{const p=gatePoint(n,g),along=vertical?p.y:p.x;return[along-3,along+3];}).sort((a,b)=>a[0]-b[0]);let cursor=low-padding;
      for(const [a,b]of [...gaps,[high+padding,high+padding]]){const end=Math.min(a,high+padding);if(end>cursor+EPS)result.push(vertical?{x:coordinate-padding,y:cursor,w:thickness,h:end-cursor,id:'wall:'+n.id}:{x:cursor,y:coordinate-padding,w:end-cursor,h:thickness,id:'wall:'+n.id});cursor=Math.max(cursor,b);}
    }
    return result;
  }
  function constraints(graph,e,opts){
    initialize(graph);
    const frames=graph.nodes.filter(n=>n.expanded),related=new Set([...ancestors(graph,e.source),...ancestors(graph,e.target)]),extra=[];
    for(const n of frames){
      const gates=e.draft?[]:activeGates(graph,e).filter(g=>g.frame===n.id);
      // Draft edges require explicit interfaces when they cross a container.
      if(e.draft&&related.has(n.id)){
        for(const [id,f]of [[e.source,e.fixedSource],[e.target,e.fixedTarget]])if(id===n.id&&f)gates.push({frame:n.id,side:f.side,fraction:f.fraction});
      }
      if(!related.has(n.id)){extra.push({...R.expand(n,borderClearance(e,n)),id:'unrelated:'+n.id});continue;}
      extra.push(...walls(n,gates,borderClearance(e,n)));
    }
    for(const n of graph.nodes)if(n.expanded)for(const box of n.labelObstacles||[])
      extra.push({x:n.x+box.x,y:n.y+box.y,w:box.w,h:box.h,id:'label:'+n.id});
    return {...opts,extraObstacles:extra};
  }
  function validate(graph,e,points){
    const violations=S?[...S.nodeErrors(graph),...S.edgeErrors(graph,e,points)]:[];
    if(!e.contract)violations.push('missing routing/source contract');
    if(!e.contract)return {ok:false,violations};
    if(points.length<2||points.some(p=>!Number.isFinite(p.x)||!Number.isFinite(p.y)))violations.push('invalid route geometry');
    const related=new Set([...ancestors(graph,e.source),...ancestors(graph,e.target)]);
    if(!e.draft&&(e.source!==e.contract.source||e.target!==e.contract.target))violations.push('producer/consumer changed without a declared draft');
    for(let i=1;i<points.length;i++){
      const a=points[i-1],b=points[i];
      if(e.style!=='octilinear'&&Math.abs(a.x-b.x)>EPS&&Math.abs(a.y-b.y)>EPS)violations.push('nonorthogonal canonical route');
      if(i>1){const p=points[i-2],ux=a.x-p.x,uy=a.y-p.y,vx=b.x-a.x,vy=b.y-a.y;if(Math.abs(ux*vy-uy*vx)<EPS&&ux*vx+uy*vy<0)violations.push('retraced terminal');}
    }
    const clean=R.simplify(points),normals={left:[-1,0],right:[1,0],top:[0,-1],bottom:[0,1]};
    const stem=sharedStemPoint(graph,e),recordedStem=e.portPolicy?.source.sharedStem||e.contract.sharedStem;
    if(stem&&clean.length>1&&(recordedStem.axis==='y'?
        Math.abs(clean[0].x-clean[1].x)>EPS||Math.min(clean[0].y,clean[1].y)>stem.y+EPS||Math.max(clean[0].y,clean[1].y)<stem.y-EPS:
        Math.abs(clean[0].y-clean[1].y)>EPS||Math.min(clean[0].x,clean[1].x)>stem.x+EPS||Math.max(clean[0].x,clean[1].x)<stem.x-EPS))violations.push('shared tensor stem disconnected before recorded fork');
    for(const [which,a,b]of [['source',clean[0],clean[1]],['target',clean.at(-1),clean.at(-2)]]){
      const f=P.active(e,which),n=normals[f?.side];
      if((e.contract.enforcePortApproach??!!graph.irSha256)&&a&&b&&n&&((b.x-a.x)*n[0]+(b.y-a.y)*n[1])*(f.inward?-1:1)<=EPS)violations.push('wrong '+which+' port approach');
    }
    if(e.style!=='octilinear'&&e.arrow!=='none'&&clean.length>=2&&R.dist(clean.at(-1),clean.at(-2))+EPS<(e.contract.minimumTerminal||0))violations.push('insufficient arrow terminal');
    for(const n of graph.nodes){
      if(n.junction)continue;
      if(!n.expanded){
        for(let i=1;i<points.length;i++)if(n.id!==e.source&&n.id!==e.target&&R.intersectsRect(points[i-1],points[i],n))violations.push('unrelated leaf '+n.id);
        if(e.contract.enforcePortApproach&&(n.id===e.source||n.id===e.target)&&points.slice(1).some((p,i)=>R.intersectsRect(points[i],p,n)))violations.push('route enters endpoint body '+n.id);
        continue;
      }
      if(!related.has(n.id)&&points.slice(1).some((p,i)=>R.intersectsRect(points[i],p,n)))violations.push('unrelated container '+n.id);
      const actual=crossings(points,n),allowed=activeGates(graph,e).filter(g=>g.frame===n.id);
      for(const g of actual)if(!allowed.some(v=>v.side===g.side&&v.direction===g.direction&&R.dist(gatePoint(n,g),gatePoint(n,v))<3.01))violations.push('undeclared boundary '+n.id);
      for(const hit of borderContacts(e,n,points))violations.push('border stroke clearance '+n.id+':'+hit.side);
    }
    // A route may remove an unnecessary exit/re-entry detour in the original
    // SVG. Its remaining crossings must still follow the recorded order; a
    // repeated gate is not a license to bounce across a container indefinitely.
    const actual=graph.nodes.filter(n=>n.expanded).flatMap(n=>crossings(points,n)).sort((a,b)=>a.order-b.order);
    const allowed=activeGates(graph,e).sort((a,b)=>a.order-b.order);let cursor=0;
    for(const g of actual){let found=false;while(cursor<allowed.length){const v=allowed[cursor++],n=graph.nodes.find(n=>n.id===g.frame);if(v.frame===g.frame&&v.side===g.side&&v.direction===g.direction&&R.dist(gatePoint(n,g),gatePoint(n,v))<3.01){found=true;break;}}if(!found){violations.push('boundary crossing order changed');break;}}
    return {ok:violations.length===0,violations:[...new Set(violations)]};
  }
  const api={borderClearance,borderContacts,initialize,ancestors,crossings,wireIdentity,walls,gatePoint,sharedStemPoint,activeGates,constraints,validate,validateJunctions,inside,pointIn,validateSource:S?.validateGraph};
  root.SummaryConstraints=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
