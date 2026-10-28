/* Shared visual graph operations. Imported canonical evidence is preserved. */
(function(root) {
  'use strict';
  const R = root.EdgeRouterLabRouting;
  const C = root.SummaryConstraints || (typeof require==='function'?require('./semantic-constraints.js'):null);
  const P = root.SummaryPhysicalPorts || (typeof require==='function'?require('./physical-ports.js'):null);
  const J = root.SummaryJunctionMarkers || (typeof require==='function'?require('./junction-markers.js'):null);
  const L = root.SummaryRouteLabels || (typeof require==='function'?require('./route-labels.js'):null);
  const clone = value => JSON.parse(JSON.stringify(value));
  const stable=v=>JSON.stringify(v&&typeof v==='object'?Array.isArray(v)?v.map(x=>JSON.parse(stable(x))):Object.fromEntries(Object.keys(v).sort().map(k=>[k,JSON.parse(stable(v[k]))])):v??null);
  function canonicalBinding(binding){const b=clone(binding||{});for(const k of ['points','explicit_sides','port_authority'])delete b[k];if(b.endpoint_binding){for(const k of ['src','dst'])delete b[k];for(const k of ['rendered_src','rendered_dst'])delete b.endpoint_binding[k];}return stable(b);}
  function upgradePresentation(graph,original){
    const changed=original.nodes.filter(n=>n.glyphPresentation&&!graph.nodes.find(v=>v.id===n.id)?.glyphPresentation);
    if(changed.length){
      // A geometry migration cannot bless a damaged source record. Validate
      // the old receipt first, then compare exact source identities with the
      // regenerated graph. Manual positions and visual drafts are retained.
      const receipt=graph.semanticBaseline,compatible=receipt&&C.validateSource(graph).ok&&
        graph.irSha256===original.irSha256&&graph.nodes.length===original.nodes.length&&
        original.nodes.every(n=>{const old=graph.nodes.find(v=>v.id===n.id);return old&&old.parent===n.parent&&stable(old.semantic)===stable(n.semantic);})&&
        graph.edges.every(e=>{const source=original.edges.find(v=>v.id===e.id);return e.draft&&!source||source&&canonicalBinding(e.binding)===canonicalBinding(source.binding);});
      if(!compatible){graph.semanticBaseline=clone(original.semanticBaseline);return graph;}
      const resized=new Set(changed.map(n=>n.id));
      for(const source of changed){const n=graph.nodes.find(v=>v.id===source.id),slot=source.glyphPresentation.slot_bbox;
        n.x+=source.x-slot[0];n.y+=source.y-slot[1];n.w=source.w;n.h=source.h;n.base=clone(source.base);n.fill=source.fill;
        n.glyphPresentation=clone(source.glyphPresentation);
      }
      for(const e of graph.edges){const source=original.edges.find(v=>v.id===e.id);if(!source)continue;
        e.binding=clone(source.binding);e.portPolicy=clone(source.portPolicy);e.contract=clone(source.contract);
        for(const side of ['source','target']){const k=side[0].toUpperCase()+side.slice(1),old=e['physical'+k];e['fixed'+k]=clone(source['fixed'+k]);
          if(resized.has(e[side])||old&&!P.permitted(graph,e,side,old))delete e['physical'+k];
          if(!e.draft){const i=side==='source'?0:e.route.length-1;e.route[i]=endpoint(graph,e,side);}
        }
      }
      for(const op of graph.sourceDraftOperations||[]){const source=original.edges.find(e=>e.id===op.id);if(source&&canonicalBinding(op.binding)===canonicalBinding(source.binding))op.binding=clone(source.binding);}
      graph.glyphMigration={schema:1,nodes:changed.map(n=>n.id),preserved:'manual displacement, canonical semantics, draft operations, waypoints and caption anchors'};
    }
    // Old SVG dots were accidentally nested under the last emitted glyph.
    // Remove only the registered fragments, preserving hand-placed geometry.
    const oldLabels=new Map((graph.routeLabels||[]).map(a=>[a.id,a]));
    graph.routeLabels=(original.routeLabels||[]).map(source=>changed.length?{...clone(source),...(oldLabels.get(source.id)?.anchor?{anchor:clone(oldLabels.get(source.id).anchor)}:{})}:oldLabels.get(source.id)||clone(source));
    graph.routeLabels.push(...[...oldLabels.values()].filter(a=>!(original.routeLabels||[]).some(v=>v.id===a.id)));
    graph.attachments=clone(original.attachments||[]);
    // Source glyph markup is regenerated only for additive metadata migrations;
    // node coordinates, paths and manual caption anchors stay in this draft.
    for(const n of graph.nodes){const source=original.nodes.find(v=>v.id===n.id);if(source){n.html=source.html;n.labelObstacles=clone(source.labelObstacles||[]);}}
    graph.extras=original.extras||'';
    graph.junctionMarkers=clone(original.junctionMarkers||[]);
    for(const marker of graph.junctionMarkers)for(const fragment of marker.fragments||[]){
      const owner=graph.nodes.find(n=>n.id===fragment.owner);
      if(owner){owner.html=owner.html.replace(fragment.html,'');if(fragment.legacyHtml)owner.html=owner.html.replace(fragment.legacyHtml,'');}
      else if(fragment.owner===null){graph.extras=(graph.extras||'').replace(fragment.html,'');if(fragment.legacyHtml)graph.extras=graph.extras.replace(fragment.legacyHtml,'');}
    }
    for(const e of graph.edges){const source=original.edges.find(v=>v.id===e.id);if(!source)continue;
      if(source.portPolicy&&!e.portPolicy)e.portPolicy=clone(source.portPolicy);
      else if(source.portPolicy&&e.portPolicy)for(const side of ['source','target']){
        const expected=clone(source.portPolicy[side]),old=clone(e.portPolicy[side]);
        for(const k of ['gates','sharedStem']){delete expected[k];delete old[k];}
        if(old.shape==='circle'&&expected.shape==='rectangle'&&graph.junctionMarkers.some(m=>m.fragments.some(f=>f.owner===e[side]))){
          old.shape='rectangle';const registered=clone(expected);
          if(JSON.stringify(registered)===JSON.stringify(old))e.portPolicy[side].shape='rectangle';
        }
        if(JSON.stringify(expected)===JSON.stringify(old)){
          const oldGates=e.portPolicy[side].gates;
          if(!oldGates||oldGates.every(g=>g.fraction===undefined)&&oldGates.every(g=>(source.portPolicy[side].gates||[]).some(n=>n.frame===g.frame&&n.side===g.side&&n.anchor===g.anchor)))
            e.portPolicy[side].gates=clone(source.portPolicy[side].gates||[]);
          if(e.portPolicy[side].sharedStem===undefined)e.portPolicy[side].sharedStem=clone(source.portPolicy[side].sharedStem??null);
        }
      }
      // An additive source-authority receipt is safe to migrate only when
      // every prior binding field still equals the registered source record.
      if(source.binding?.port_authority&&!e.binding?.port_authority){
        const expected=clone(source.binding);delete expected.port_authority;
        if(JSON.stringify(expected)===JSON.stringify(e.binding))e.binding.port_authority=clone(source.binding.port_authority);
      }
    }
    if(original.semanticBaseline)graph.semanticBaseline=clone(original.semanticBaseline);else delete graph.semanticBaseline;
    if(changed.length){
      C.initialize(graph);
      const targets=graph.edges.filter(e=>!C.validate(graph,e,e.route).ok).map(e=>e.id);
      if(targets.length)routeBatch(graph,targets,{margin:6,stub:16,bendCost:40,crossingCost:180,overlapCost:2,edgeSpacing:12,sides:'any',style:'orthogonal'});
    }
    return graph;
  }
  function port(n, fixed) {
    const p = R.port(n, fixed.side, fixed.fraction);
    return fixed.offset ? {...p,x:n.x+fixed.offset.x,y:n.y+fixed.offset.y} : p;
  }
  function endpoint(graph,edge,side) {
    const n=graph.nodes.find(n=>n.id===edge[side]);
    const other=graph.nodes.find(n=>n.id===edge[side==='source'?'target':'source']);
    const fixed=P.active(edge,side);
    return fixed?port(n,fixed):R.port(n,R.candidateSides(n,other)[0]);
  }
  function descendants(graph,id) {
    const result=new Set([id]);let changed=true;
    while(changed){changed=false;for(const n of graph.nodes)if(result.has(n.parent)&&!result.has(n.id)){result.add(n.id);changed=true;}}
    return result;
  }
  const normals={left:[-1,0],right:[1,0],top:[0,-1],bottom:[0,1]};
  function footprint(n){
    if(!n.glyphPresentation)return n;
    const labels=(n.labelObstacles||[]).map(b=>({x:n.x+b.x,y:n.y+b.y,w:b.w,h:b.h})),parts=[n,...labels];
    const x=Math.min(...parts.map(b=>b.x)),y=Math.min(...parts.map(b=>b.y));
    return {x,y,w:Math.max(...parts.map(b=>b.x+b.w))-x,h:Math.max(...parts.map(b=>b.y+b.h))-y};
  }
  function attachmentTransform(graph,a){
    const n=graph.nodes.find(n=>n.id===a.owner);
    const p=a.presentation,base=p?.base||n?.base;
    return n?{x:n.x-base[0]+(n.w-(p?.size[0]??n.w))*(p?.horizontal||0),y:n.y-base[1]+(n.h-(p?.size[1]??n.h))*(p?.vertical||0)}:{x:0,y:0};
  }
  function sharesPresentation(graph,a,b){
    if(!graph.recursive||a.draft||b.draft||!a.projection?.visual||a.projection.visual!==b.projection?.visual||a.source!==b.source||a.target!==b.target)return false;
    // An exact recorded overview can depict a tuple/collection or authored
    // alternatives with one summary arrow. This licenses only that complete
    // coincident projection, never a partial overlap between distinct inputs.
    if(a.route.length!==b.route.length||a.route.some((p,i)=>R.dist(p,b.route[i])>1e-5))return false;
    const visible=new Set(graph.nodes.map(n=>n.id));
    return graph.recursive.authority.variants.some(v=>v.nodes.length===visible.size&&v.nodes.every(n=>visible.has(n.id))&&v.edges.some(e=>e.id===a.projection.visual&&e.source===a.source&&e.target===a.target));
  }
  function overlapsWire(graph,e,points){
    return graph.edges.some(other=>other!==e&&other.contract?.wire!==e.contract?.wire&&!sharesPresentation(graph,{...e,route:points},other)&&
      points.slice(1).some((b,i)=>other.route.slice(1).some((d,j)=>R.overlap(points[i],b,other.route[j],d)>1e-5)));
  }
  function layoutConflicts(graph){
    const nodes=[],wires=[];
    for(const [i,a] of graph.nodes.entries())for(const b of graph.nodes.slice(i+1)){
      if(a.junction||b.junction||a.parent!==b.parent)continue;
      if(Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x)>1e-5&&Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y)>1e-5)nodes.push([a.id,b.id]);
    }
    for(const [i,a] of graph.edges.entries())for(const b of graph.edges.slice(i+1)){
      if(a.contract?.wire===b.contract?.wire||sharesPresentation(graph,a,b))continue;
      if(a.route.slice(1).some((p,j)=>b.route.slice(1).some((q,k)=>R.overlap(a.route[j],p,b.route[k],q)>1e-5)))wires.push([a.id,b.id]);
    }
    return {nodes,wires};
  }
  function validateView(graph){
    C.initialize(graph);const context=C.validationContext(graph),conflicts=layoutConflicts(graph);
    const junctions=C.validateJunctions(graph);
    const violations=[...conflicts.nodes.map(ids=>'sibling glyph overlap '+ids.join(' / ')),...conflicts.wires.map(ids=>'unrelated tensor lane overlap '+ids.join(' / ')),...junctions.violations];
    const affected=new Map();for(const ids of conflicts.wires)for(const id of ids){const errors=affected.get(id)||[];errors.push('unrelated tensor lane overlap '+ids.join(' / '));affected.set(id,errors);}
    const constrained=graph.edges.filter(e=>e.boundaryLane?.constrainedAt===C.geometryKey(graph)).map(e=>e.id);
    return {source:C.validateSource(graph),layout:{ok:!violations.length,violations,...conflicts,junctions},routing:{constrained,contacts:graph.edges.flatMap(e=>C.laneContacts(graph,e,e.route,context).map(hit=>({edge:e.id,...hit})))},edges:graph.edges.map(e=>{const check=C.validate(graph,e,e.route,context),extra=affected.get(e.id)||[];return [e.id,{ok:check.ok&&!extra.length,violations:[...check.violations,...extra]}];})};
  }
  function repairCandidates(graph,e,old){
    const s=endpoint(graph,e,'source'),t=endpoint(graph,e,'target'),out=[];
    const add=ps=>out.push(R.simplify(ps));
    add([s,t]);
    if(old.length>2){
      const ps=clone(old);ps[0]=s;ps[ps.length-1]=t;
      if(Math.abs(old[0].x-old[1].x)<1e-5)ps[1].x=s.x;else ps[1].y=s.y;
      if(Math.abs(old.at(-1).x-old.at(-2).x)<1e-5)ps[ps.length-2].x=t.x;else ps[ps.length-2].y=t.y;
      add(ps);
    }
    const ns=normals[s.side],nt=normals[t.side],ss=P.active(e,'source')?.inward?-1:1,ts=P.active(e,'target')?.inward?-1:1;
    // Short Q/K/V gaps need a balanced dogleg, not two fixed 28px stubs
    // that extend past each other and retrace the same lane.
    if(ns[1]&&nt[1]){const y=(s.y+t.y)/2;add([s,{x:s.x,y},{x:t.x,y},t]);}
    if(ns[0]&&nt[0]){const x=(s.x+t.x)/2;add([s,{x,y:s.y},{x,y:t.y},t]);}
    for(const stub of [4,6,9,10,16,24]){
      const terminal=Math.max(9,stub);
      const a={x:s.x+ns[0]*ss*stub,y:s.y+ns[1]*ss*stub},b={x:t.x+nt[0]*ts*terminal,y:t.y+nt[1]*ts*terminal};
      add([s,a,{x:b.x,y:a.y},b,t]);add([s,a,{x:a.x,y:b.y},b,t]);
    }
    return out.sort((a,b)=>(a.length-b.length)*40+a.slice(1).reduce((v,p,i)=>v+R.dist(a[i],p),0)-b.slice(1).reduce((v,p,i)=>v+R.dist(b[i],p),0));
  }
  function move(graph,id,dx,dy,options={}) {
    C.initialize(graph);
    const ids=descendants(graph,id);
    const moving=graph.nodes.filter(n=>ids.has(n.id)),selected=moving.find(n=>n.id===id);
    if(!selected)return new Set();
    const owner=graph.nodes.find(n=>n.id===selected.parent);
    if(owner){const pad=2;for(const glyph of moving){const n=footprint(glyph);dx=Math.max(owner.x+pad-n.x,Math.min(owner.x+owner.w-pad-n.x-n.w,dx));dy=Math.max(owner.y+pad-n.y,Math.min(owner.y+owner.h-pad-n.y-n.h,dy));}}
    const siblings=graph.nodes.filter(n=>!ids.has(n.id)&&n.parent===moving.find(n=>n.id===id)?.parent&&!n.junction);
    const wouldOverlap=(node,other)=>{const n=footprint(node),b=footprint(other);return Math.min(n.x+dx+n.w,b.x+b.w)-Math.max(n.x+dx,b.x)>1e-5&&Math.min(n.y+dy+n.h,b.y+b.h)-Math.max(n.y+dy,b.y)>1e-5;};
    graph.lastMove={blocked:false,rerouted:0};
    if(siblings.some(b=>wouldOverlap(selected,b))){graph.lastMove.blocked=true;return new Set();}
    const savedNodes=moving.map(n=>[n,n.x,n.y]),savedEdges=graph.edges.map(e=>[e,clone(e)]);
    const rollback=reason=>{for(const [n,x,y]of savedNodes){n.x=x;n.y=y;}for(const [e,old]of savedEdges){for(const k of Object.keys(e))delete e[k];Object.assign(e,old);}graph.lastMove={blocked:true,reason};return new Set();};
    for(const n of graph.nodes)if(ids.has(n.id)){n.x+=dx;n.y+=dy;}
    const context=C.validationContext(graph);
    const affected=[];
    for(const e of graph.edges){
      if(ids.has(e.source)&&ids.has(e.target)){e.route=e.route.map(p=>({x:p.x+dx,y:p.y+dy}));e.waypoints=(e.waypoints||[]).map(p=>({x:p.x+dx,y:p.y+dy}));}
      else{
        if(ids.has(e.source))e.route[0]=endpoint(graph,e,'source');
        if(ids.has(e.target))e.route[e.route.length-1]=endpoint(graph,e,'target');
      }
      if(ids.has(e.source)||ids.has(e.target)||!C.validate(graph,e,e.route,context).ok||C.needsLaneRepair(graph,e,context))affected.push(e);
    }
    const opts={margin:6,stub:16,bendCost:40,crossingCost:180,overlapCost:2,edgeSpacing:12,sides:'any',preserve:true,...options};
    const settled=new Set();let reserved=graph.edges;
    // Moving one endpoint temporarily makes an affected sibling's old path
    // diagonal or leaves its gate behind. That pending path cannot reserve
    // a lane before its own repair. Valid and already settled peers remain
    // obstacles; the complete graph is checked again before committing.
    const legal=(e,ps)=>C.validate(graph,e,ps,context).ok&&!overlapsWire({...graph,edges:reserved},e,ps);
    for(const e of affected){
      reserved=graph.edges.filter(v=>v===e||!affected.includes(v)||settled.has(v)||C.validate(graph,v,v.route,context).ok);
      const incident=ids.has(e.source)!==ids.has(e.target);
      if(incident&&e.portPolicy&&!e.contract.bus){
        // Reconsider legal but long routes too: dragging a PE across an Add
        // must change its physical side without changing the PE input field.
        const prior=reserved.filter(v=>v!==e).map(v=>Object.assign(v.route.slice(),{wire:v.contract.wire}));
        const old=savedEdges.find(([v])=>v===e)[1].route;
        const shared=(e.portPolicy?.source.sharedStem||e.contract.sharedStem)&&repairCandidates(graph,e,old).find(ps=>legal(e,ps)&&!C.laneContacts(graph,e,ps,context).length);
        if(shared){e.route=shared;settled.add(e);graph.lastMove.rerouted++;continue;}
        const result=routeOne(graph,e,prior,{...opts,style:e.style,preserve:false},context);
        if(result.ok&&legal(e,e.route)){settled.add(e);graph.lastMove.rerouted++;continue;}
      }
      if(legal(e,e.route)&&!C.needsLaneRepair(graph,e,context)){e.failed=false;delete e.reason;settled.add(e);continue;}
      if(e.contract.bus)return rollback('explicit branch skeleton cannot be disconnected');
      const old=savedEdges.find(([v])=>v===e)[1].route;
      const candidate=repairCandidates(graph,e,old).find(ps=>legal(e,ps)&&!C.laneContacts(graph,e,ps,context).length);
      if(candidate)e.route=candidate;
      else{
        const prior=reserved.filter(v=>v!==e).map(v=>Object.assign(v.route.slice(),{wire:v.contract.wire}));
        const result=routeOne(graph,e,prior,{...opts,style:e.style},context);
        if(!result.ok||!legal(e,e.route))return rollback(e.id+': '+(result.reason||'no legal local corridor'));
      }
      e.failed=false;delete e.reason;settled.add(e);graph.lastMove.rerouted++;
    }
    // Later repairs must not invalidate an earlier wire, gate or terminal.
    reserved=graph.edges;
    if(affected.some(e=>!legal(e,e.route)))return rollback('local routes conflict');
    const complete=validateView(graph);
    if(!complete.source.ok||!complete.layout.ok||complete.edges.some(([edgeId,check])=>!check.ok&&!graph.edges.find(e=>e.id===edgeId)?.draft))
      return rollback(!complete.layout.junctions.ok?'source tensor fork disconnected':'complete moved graph is invalid');
    return ids;
  }
  // Pointer motion updates only presentation geometry. The authoritative
  // move() runs on the pre-drag graph when the gesture ends, in a worker.
  function movePreview(graph,id,dx,dy) {
    const ids=descendants(graph,id),selected=graph.nodes.find(n=>n.id===id);
    if(!selected||(!dx&&!dy))return ids;
    const moving=graph.nodes.filter(n=>ids.has(n.id));
    const bounds=footprint(selected);
    if(graph.canvas){dx=Math.max(3-bounds.x,Math.min(graph.canvas[0]-3-bounds.x-bounds.w,dx));dy=Math.max(3-bounds.y,Math.min(graph.canvas[1]-3-bounds.y-bounds.h,dy));}
    const owner=graph.nodes.find(n=>n.id===selected.parent);
    if(owner){const pad=2;
      dx=Math.max(owner.x+pad-bounds.x,Math.min(owner.x+owner.w-pad-bounds.x-bounds.w,dx));
      dy=Math.max(owner.y+pad-bounds.y,Math.min(owner.y+owner.h-pad-bounds.y-bounds.h,dy));
    }
    const siblings=graph.nodes.filter(n=>!ids.has(n.id)&&n.parent===selected.parent&&!n.junction);
    const overlap=node=>{const b=footprint(node);return Math.min(bounds.x+dx+bounds.w,b.x+b.w)-Math.max(bounds.x+dx,b.x)>1e-5&&
      Math.min(bounds.y+dy+bounds.h,b.y+b.h)-Math.max(bounds.y+dy,b.y)>1e-5;};
    if(siblings.some(overlap)){graph.lastMove={blocked:true,reason:'node overlap'};return new Set();}
    for(const n of moving){n.x+=dx;n.y+=dy;}
    for(const e of graph.edges){const s=ids.has(e.source),t=ids.has(e.target);
      if(s&&t){e.route=(e.route||[]).map(p=>({x:p.x+dx,y:p.y+dy}));e.waypoints=(e.waypoints||[]).map(p=>({x:p.x+dx,y:p.y+dy}));}
      else{if(s&&e.route?.length)e.route[0]=endpoint(graph,e,'source');if(t&&e.route?.length)e.route[e.route.length-1]=endpoint(graph,e,'target');}
    }
    graph.lastMove={blocked:false,preview:true};return ids;
  }
  function reconnect(graph,edge,side,nodeId,fixed) {
    delete edge[side==='source'?'physicalSource':'physicalTarget'];
    edge[side]=nodeId;edge[side==='source'?'fixedSource':'fixedTarget']=fixed;
    edge.route[side==='source'?0:edge.route.length-1]=endpoint(graph,edge,side);
    edge.draft=true;
    delete edge.contract;C.initialize(graph);
  }
  function crop(points,startArrow,endArrow) {
    // Keep the canonical route all the way to its physical port. The original
    // SVG uses a user-space marker whose refX is the path endpoint; shortening
    // the wire first creates a visible spur/gap at a turn.
    return R.simplify(points);
  }
  function arrow(tip,from,open=false) {
    const len=R.dist(tip,from);if(len<1e-6)return '';
    const ux=(tip.x-from.x)/len,uy=(tip.y-from.y)/len;
    // Match markerWidth=10, markerHeight=8, refX=9, refY=4 from the
    // recorded source SVG: the tip is exactly the route endpoint.
    const bx=tip.x-ux*9,by=tip.y-uy*9;
    return `M ${bx-uy*4} ${by+ux*4} L ${tip.x} ${tip.y} L ${bx+uy*4} ${by-ux*4}${open?'':' Z'}`;
  }
  function displayed(graph,e) {
    const points=R.simplify(e.route);
    if(e.style!=='octilinear'||points.length<2)return points;
    const result=R.chamfer(points,graph.nodes,18);
    return C.validate(graph,e,result).ok?result:points;
  }
  function curvePoints(points,radius){
    const out=[points[0]];
    for(let i=1;i<points.length-1;i++){
      const a=points[i-1],b=points[i],c=points[i+1],da=R.dist(a,b),dc=R.dist(b,c),r=Math.min(radius,da/3,dc/3);
      const p={x:b.x+(a.x-b.x)/da*r,y:b.y+(a.y-b.y)/da*r},q={x:b.x+(c.x-b.x)/dc*r,y:b.y+(c.y-b.y)/dc*r};out.push(p);
      // Sample each bounded quadratic at sub-pixel spacing for the same wall,
      // leaf and gate checks used by the orthogonal canonical route.
      const steps=Math.max(16,Math.ceil(r*4));
      for(let j=1;j<=steps;j++){const t=j/steps,u=1-t;out.push({x:u*u*p.x+2*u*t*b.x+t*t*q.x,y:u*u*p.y+2*u*t*b.y+t*t*q.y});}
    }
    out.push(points.at(-1));return R.simplify(out);
  }
  function curveRadius(graph,e,points){
    if(!graph||!e)return 12;
    for(const radius of [12,6,3,1]){
      const sample=curvePoints(points,radius);
      if(!C.validate(graph,{...e,style:'octilinear'},sample).ok)continue;
      const obstacles=C.constraints(graph,e,{margin:0}).extraObstacles;
      if(!sample.slice(1).some((p,i)=>obstacles.some(n=>R.intersectsRect(sample[i],p,n))))return radius;
    }
    return 0;
  }
  const path=(points,style,graph,e)=>style==='curved'?R.roundedPath(points,curveRadius(graph,e,points)):R.polylinePath(points);
  function adaptiveOptions(graph,e,options) {
    if(graph.caseId==='routing-lab')return {...options,width:graph.canvas[0],height:graph.canvas[1]};
    const s=graph.nodes.find(n=>n.id===e.source),t=graph.nodes.find(n=>n.id===e.target);
    let gap=Infinity;
    for(const a of [s,t])for(const b of graph.nodes){
      if(a===b||b.routingObstacle===false&&!b.expanded||a.expanded||a.junction)continue;
      const gx=Math.max(a.x,b.x)-Math.min(a.x+a.w,b.x+b.w),gy=Math.max(a.y,b.y)-Math.min(a.y+a.h,b.y+b.h);
      if(gx>=0&&gy<=0)gap=Math.min(gap,gx);if(gy>=0&&gx<=0)gap=Math.min(gap,gy);
    }
    const margin=Math.max(.1,Math.min(options.margin,Number.isFinite(gap)?gap*.24:options.margin));
    let stub=Math.max(margin+1,e.contract?.minimumTerminal||0,Math.min(24,Number.isFinite(gap)?gap*.4:24));
    // Keep an outward terminal stub inside the searchable canvas. A fixed
    // left/right port near the canvas edge otherwise lands exactly on the
    // visibility boundary and makes a valid gate route appear impossible.
    const boundary={x:1,y:1,w:graph.canvas[0]-2,h:graph.canvas[1]-2};
    for(const side of ['source','target']){
      const f=P.active(e,side),n=graph.nodes.find(v=>v.id===e[side]);
      if(!f||!n)continue;
      const p=P.point(n,f),normal=normals[f.side],direction=f.inward?-1:1;
      if(direction<0)continue;
      const distance=normal[0]<0?p.x-boundary.x:normal[0]>0?boundary.x+boundary.w-p.x:normal[1]<0?p.y-boundary.y:boundary.y+boundary.h-p.y;
      if(Number.isFinite(distance))stub=Math.min(stub,Math.max(1,distance-1));
    }
    return {...options,margin,stub,stubPadding:1,width:graph.canvas[0],height:graph.canvas[1]};
  }
  function conflicts(graph,e,options) {
    C.initialize(graph);
    if(!C.validate(graph,e,e.route).ok)return true;
    if(e.style!==options.style||e.route.length<2||e.draft)return true;
    const opts=adaptiveOptions(graph,e,options);
    for(let i=1;i<e.route.length;i++)for(const n of graph.nodes){
      if(n.routingObstacle===false||i===1&&n.id===e.source||i===e.route.length-1&&n.id===e.target)continue;
      if(R.intersectsRect(e.route[i-1],e.route[i],R.expand(n,opts.margin)))return true;
    }
    if(options.edgeSpacing>0)for(const other of graph.edges){
      if(other===e)continue;
      if(other.contract?.wire===e.contract?.wire)continue;
      const same=(a,b)=>R.dist(a,b)<1e-6;
      for(let i=1;i<e.route.length;i++)for(let j=1;j<other.route.length;j++){
        if(R.overlap(e.route[i-1],e.route[i],other.route[j-1],other.route[j])<=1e-6)continue;
        const terminals=[e.route[0],e.route.at(-1)].filter(p=>same(p,other.route[0])||same(p,other.route.at(-1)));
        if(!terminals.some(p=>(i===1&&same(p,e.route[0])||i===e.route.length-1&&same(p,e.route.at(-1)))&&
          (j===1&&same(p,other.route[0])||j===other.route.length-1&&same(p,other.route.at(-1)))))return true;
      }
    }
    return false;
  }
  function routeOne(graph,e,prior,options,context) {
    if(!context){C.initialize(graph);context=C.validationContext(graph);}
    if(e.contract.bus){const check=C.validate(graph,e,e.route,context);if(check.ok){e.failed=false;if(C.laneContacts(graph,e,e.route,context).length)e.boundaryLane={constrainedAt:C.geometryKey(graph),reason:'explicit source bus skeleton retained'};return{ok:true,retained:true,points:e.route};}e.failed=true;e.reason='汇流骨架离开所属范围，请恢复原图或移动所属容器。';return{ok:false,reason:e.reason};}
    const fraction=id=>{const siblings=graph.edges.filter(v=>v.source===id||v.target===id);return .2+.6*(siblings.indexOf(e)+1)/(siblings.length+1);};
    const compatible=prior.filter(p=>!p.wire||p.wire!==e.contract.wire);
    const tangled=options.crossingCost>0&&compatible.some(path=>path.slice(1).some((b,j)=>e.route.slice(1).some((d,i)=>R.crossing(path[j],b,e.route[i],d))));
    if(!options.optimizeReadability&&!C.needsLaneRepair(graph,e,context)&&(options.optimizeCrossings===false||!tangled)&&(e.portPolicy?.source.sharedStem||e.contract.sharedStem)&&C.validate(graph,e,e.route,context).ok&&
        !compatible.some(path=>path.slice(1).some((b,j)=>e.route.slice(1).some((d,i)=>R.overlap(path[j],b,e.route[i],d)>1e-5)))){
      e.failed=false;e.style=options.style;delete e.reason;return {ok:true,retained:true,points:e.route,reason:'source-backed shared tensor stem retained'};
    }
    const opts={...adaptiveOptions(graph,e,options),sourceFraction:fraction(e.source),targetFraction:fraction(e.target),minimumTerminal:e.contract.minimumTerminal};
    if(options.boundaryLanes!==false)opts.maxSearchVertices=20000;
    const projected=(s,t)=>({...e,physicalSource:s,physicalTarget:t});
    const flexible=!!e.portPolicy&&!e.draft;
    const requestedPorts=options.portOverrides?.[e.id];
    const extra=flexible?{
      sourceCandidates:requestedPorts?.source?[requestedPorts.source]:P.candidates(graph,e,'source',options.sides),targetCandidates:requestedPorts?.target?[requestedPorts.target]:P.candidates(graph,e,'target',options.sides),
      obstaclesForPorts:(s,t)=>C.constraints(graph,projected(s,t),opts,context).extraObstacles,
      acceptCandidate:(ps,s,t)=>C.validate(graph,projected(s,t),ps,context).ok&&(options.boundaryLanes===false||!C.laneContacts(graph,projected(s,t),ps,context).length)
    }:{acceptCandidate:ps=>C.validate(graph,e,ps,context).ok&&(options.boundaryLanes===false||!C.laneContacts(graph,e,ps,context).length)};
    const stem=C.sharedStemPoint(graph,e,{...context,boundaryLanes:options.boundaryLanes!==false}),originalWaypoints=options.preserve?(e.waypoints||[]):[];
    if(stem)opts.stub=Math.min(opts.stub,Math.max(opts.margin+1,R.dist(endpoint(graph,e,'source'),stem)-1));
    const waypoints=originalWaypoints.slice();
    if(stem){const source=endpoint(graph,e,'source'),length=R.dist(source,stem);let index=0;
      // A common tensor ray can pass several gates before it branches. Keep
      // those gates before the fork, rather than going to the fork first and
      // forcing a reversal back across a wall on a fully expanded frontier.
      while(index<waypoints.length&&Math.abs(R.dist(source,waypoints[index])+R.dist(waypoints[index],stem)-length)<1e-5)index++;
      if(!waypoints.some(p=>R.dist(p,stem)<1e-5))waypoints.splice(index,0,stem);
    }
    const result=R.routeEdge({...e,fixedSource:P.active(e,'source'),fixedTarget:P.active(e,'target'),waypoints},graph.nodes,compatible,{...C.constraints(graph,e,opts,context),...extra,preserve:!!stem||options.preserve});
    if(!result.ok&&options.boundaryLanes!==false){
      // Aesthetic lane width cannot make a previously legal narrow source
      // interface immovable. Retry the painted-stroke safety constraint and
      // record the constrained geometry; moving or unfolding retries it.
      const safeRecorded=C.validate(graph,e,e.route,context).ok&&!compatible.some(path=>path.slice(1).some((b,j)=>e.route.slice(1).some((d,i)=>R.overlap(path[j],b,e.route[i],d)>1e-5)));
      const fallback=safeRecorded?{ok:true,retained:true,points:e.route}:routeOne(graph,e,prior,{...options,boundaryLanes:false},context);
      if(fallback.ok){e.failed=false;delete e.reason;e.boundaryLane=C.laneContacts(graph,e,e.route,context).length?{constrainedAt:context.geometryKey,reason:'preferred lane unavailable within local search; stroke-safe source route retained'}:{clear:true};}
      return fallback;
    }
    if(!result.ok&&!e.draft&&e.route.length>1&&C.validate(graph,e,e.route,context).ok){
      const overlaps=options.edgeSpacing>0&&compatible.some(path=>path.slice(1).some((b,j)=>e.route.slice(1).some((d,i)=>R.overlap(path[j],b,e.route[i],d)>1e-5)));
      if(!overlaps){e.failed=false;return{ok:true,retained:true,points:e.route,reason:'recorded legal corridor retained'};}
    }
    if(result.ok){e.route=result.points;e.sourcePort=result.sourcePort;e.targetPort=result.targetPort;if(flexible){e.physicalSource=result.physicalSource;e.physicalTarget=result.physicalTarget;}e.style=options.style;e.failed=false;delete e.reason;if(options.boundaryLanes!==false)e.boundaryLane={clear:true};}
    else {e.failed=true;e.reason=result.reason;}
    return result;
  }
  function routeBatch(graph,ids,options) {
    C.initialize(graph);
    const context=C.validationContext(graph);
    const before=graph.edges.map(e=>[e,clone(e)]);
    const marked=e=>Object.assign(e.route.slice(),{wire:e.contract.wire}),set=new Set(ids),prior=graph.edges.filter(e=>!set.has(e.id)||e.contract.bus).map(marked);
    let routed=0,failed=0,retained=0;
    const conflicted=new Set(graph.edges.filter(e=>overlapsWire(graph,e,e.route)).map(e=>e.id)),done=new Set();
    const queue=graph.edges.filter(e=>set.has(e.id));
    if(options.groupByWire)queue.sort((a,b)=>String(a.contract?.wire||'').localeCompare(String(b.contract?.wire||''))||String(a.source).localeCompare(String(b.source))||String(a.id).localeCompare(String(b.id)));
    for(const e of queue){
      // Reserve registered legal corridors, but never reserve an invalid
      // projection merely because it happens not to overlap another wire.
      // Invalid siblings are provisional until routed; pinning their old
      // geometry can strand a branch in the same batch.
      const occupied=e.portPolicy?graph.edges.filter(v=>v!==e&&(!set.has(v.id)||done.has(v.id)||v.contract?.bus||(!conflicted.has(v.id)&&C.validate(graph,v,v.route,context).ok))).map(marked):prior;
      const r=routeOne(graph,e,occupied,options,context);if(r.ok){if(r.retained)retained++;else routed++;}else failed++;done.add(e.id);if(!e.contract.bus)prior.push(marked(e));}
    const junctionCheck=C.validateJunctions(graph);
    if(!junctionCheck.ok){
      // Validate shared topology after all branches have moved, not while
      // half of a fan-out still contains its previous coordinates.
      for(const [e,saved]of before){for(const k of Object.keys(e))delete e[k];Object.assign(e,saved);}
      return {graph,routed:0,failed:ids.length,retained:0,reason:junctionCheck.violations.join('; ')};
    }
    // Apply the same bounded readability pass used by recursive frontiers
    // after an explicit Apply/layout request. It only changes legal route
    // geometry, keeps source bindings and manual knots intact, and is gated
    // by the caller so low-level routing tests can still exercise the raw
    // visibility router in isolation.
    if(options.optimizeReadability&&graph.recursive&&root.SummaryRecursive?.polish){
      root.SummaryRecursive.polish(graph,{...options,edgeIds:options.edgeIds||undefined});
    }
    return {graph,routed,failed,retained};
  }
  function labelPath(graph,a){const e=graph.edges.find(v=>v.id===a.edge);if(!e)return [];
    const ps=displayed(graph,e);return e.style==='curved'?curvePoints(ps,curveRadius(graph,e,ps)):ps;
  }
  function routeLabelPlacements(graph,fast=false){const out=new Map(),occupied=[];for(const a of graph.routeLabels||[]){
    const e=graph.edges.find(e=>e.id===a.edge),points=fast?(e?.route||[]):labelPath(graph,a);
    const placed=L.place(graph,a,points,occupied,fast);if(placed){out.set(a.id,placed);occupied.push(placed.box);}
  }return out;}
  function snapRouteLabel(graph,a,p){return L.snap(a,labelPath(graph,a),p);}
  const api={labelPath,routeLabelPlacements,snapRouteLabel,clone,upgradePresentation,port,endpoint,descendants,move,movePreview,reconnect,crop,arrow,path,curvePoints,curveRadius,displayed,adaptiveOptions,conflicts,overlapsWire,sharesPresentation,layoutConflicts,validateView,routeOne,routeBatch,attachmentTransform,junctionPoint:J.point};
  root.SummaryEngine=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
