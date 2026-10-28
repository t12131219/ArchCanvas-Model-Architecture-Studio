/* Compound-graph layout and obstacle-aware orthogonal routing. Node labels and
 * model family names never determine topology or create connections. */
(function(root){
  'use strict';
  const Geometry=root.SemanticGeometryIndex||(typeof require==='function'?require('./geometry-index.js'):null),routingScopes=new WeakMap();
  function withRoutingIndex(positions,run){
    const previous=routingScopes.get(positions),idx=positions.context?.idx,ancestors=new Map(),incident=new Map(),covering=new Map();
    for(const id of positions.keys()){
      const chain=new Set([id]);let parent=idx?.nodes.get(id)?.parent;while(parent){chain.add(parent);parent=idx.nodes.get(parent)?.parent;}ancestors.set(id,chain);
      const p=positions.get(id),covers=[];
      for(const at of [...chain].slice(1)){const q=positions.get(at);if(!q)continue;const top=positions.context?.protectFrameTitles!==true&&q.expanded&&q.header?Math.min(q.h,q.header-10):0;
        if(p.x>=q.x-8&&p.x+p.w<=q.x+q.w+8&&p.y>=q.y+top-(top?0:8)&&p.y+p.h<=q.y+q.h+8)covers.push(at);
      }covering.set(id,covers);
    }
    for(const edge of positions.context?.edges||[])for(const source of [true,false]){const id=source?edge.source:edge.target;if(!incident.has(id))incident.set(id,[]);incident.get(id).push({edge,source});}
    routingScopes.set(positions,{ancestors,incident,covering,reserved:null,count:0,segments:null});
    try{return run();}finally{if(previous)routingScopes.set(positions,previous);else routingScopes.delete(positions);}
  }
  function components(ids,adj){
    let sequence=0;const stack=[],active=new Set(),number=new Map(),low=new Map(),result=[];
    function visit(id){number.set(id,sequence);low.set(id,sequence++);stack.push(id);active.add(id);
      for(const to of adj.get(id)||[])if(!number.has(to)){visit(to);low.set(id,Math.min(low.get(id),low.get(to)));}else if(active.has(to))low.set(id,Math.min(low.get(id),number.get(to)));
      if(low.get(id)===number.get(id)){const group=[];let item;do{item=stack.pop();active.delete(item);group.push(item);}while(item!==id);result.push(group);}
    }
    for(const id of ids)if(!number.has(id))visit(id);return result;
  }
  // A side entry is only a drawing preference: external values remain data,
  // with distinct uses, operand slots and conditions. No role is inferred.
  function contextEntries(idx,visible,edges,side='left'){
    const ancestors=id=>{const result=[];while(id!=null){result.push(id);id=idx.nodes.get(id)?.parent;}return result;};
    const ordinary=edge=>(edge.bundle_members||[edge]).every(m=>['data','alias','interface-binding'].includes(m.kind)&&!m.condition);
    const counts=new Map(),result=[];
    for(const e of edges){
      const owner=idx.nodes.get(e.target)?.parent,inside=id=>ancestors(id).includes(owner);
      if(!owner||!visible.has(owner)||inside(e.source)||ancestors(e.target).includes(e.source)||e.design_route||!ordinary(e))continue;
      const internal=edges.filter(other=>other.target===e.target&&other.source!==e.source&&inside(other.source)&&other.source!==owner&&ordinary(other)&&!other.design_route);
      if(!internal.length)continue;
      const index=counts.get(owner)||0;counts.set(owner,index+1);
      result.push({edge:e.id,owner,index,side:side==='left'?'left':'right',internal_inputs:internal.map(other=>other.id),
        scope:'visible dependency geometry; no auxiliary-input or execution assertion'});
    }
    return result;
  }
  // Follow an expanded region's actual exit with its existing downstream
  // nodes. Horizontal drawing alignment only; ranks, ownership and all
  // dependencies remain unchanged. Multiple source regions keep DAG layout.
  function regionFollowers(idx,nodes,edges,original){
    const positions=new Map([...original].map(([id,p])=>[id,{...p}])),records=[],moved=new Set();
    positions.context={...original.context,routeCache:new Map(),reserved:[]};
    const owner=(id,parent)=>{while(id&&idx.nodes.get(id)?.parent!==parent)id=idx.nodes.get(id)?.parent;return id;};
    const ordinary=e=>!e.design_route&&!e.layout_after&&(e.bundle_members||[e]).every(m=>['data','alias','interface-binding'].includes(m.kind)&&!m.condition);
    const overlap=(a,b)=>a.x<b.x+b.w+8&&a.x+a.w+8>b.x&&a.y<b.y+b.h+8&&a.y+a.h+8>b.y;
    for(const n of nodes.slice().sort((a,b)=>positions.get(a.id).y-positions.get(b.id).y)){
      const p=positions.get(n.id),parent=positions.get(n.parent);
      if(p.expanded||p.cyclic||!parent?.expanded||!['compute','composite','interface','opaque'].includes(n.kind)||
        n.condition||n.mutable||n.identity_display||n.observed_calls)continue;
      const incoming=edges.filter(e=>e.target===n.id),incident=edges.filter(e=>e.source===n.id||e.target===n.id);
      if(!incoming.length||incident.some(e=>!ordinary(e)))continue;
      const regions=[...new Set(incoming.map(e=>owner(e.source,n.parent)))];
      if(regions.length!==1||!regions[0]||regions[0]===n.id)continue;
      const source=positions.get(regions[0]);
      if(!source||source.cyclic||(!source.expanded&&!moved.has(regions[0]))||p.y<source.y+source.h)continue;
      const center=incoming.reduce((sum,e)=>{const at=positions.get(e.source);return sum+at.x+at.w/2;},0)/incoming.length;
      const lanes=positions.context.contextLanes.filter(c=>c.owner===n.parent&&c.selected!==false);
      const left=parent.x+16+(parent.design_gutter||0)+(lanes.some(c=>c.side==='left')?(parent.context_gutter||0):0);
      const right=parent.x+parent.w-16-(lanes.some(c=>c.side==='right')?(parent.context_gutter||0):0)-p.w;
      if(right<left)continue;
      const x=Math.max(left,Math.min(right,center-p.w/2));
      if(Math.abs(x-p.x)<1||nodes.some(k=>k.parent===n.parent&&k.id!==n.id&&overlap({...p,x},positions.get(k.id))))continue;
      records.push({node:n.id,parent:n.parent,source_region:regions[0],before:{x:p.x,y:p.y},after:{x,y:p.y},
        inputs:incoming.map(e=>({edge:e.id,source:e.source,target:e.target,source_port:e.source_port,target_port:e.target_port})),
        scope:'Existing region exit and downstream terminals; horizontal drawing alignment only, no sequencing or equivalence assertion.'});
      p.x=x;moved.add(n.id);
    }
    return {positions,records};
  }
  // Only an existing, unguarded side entry may face its receiving region.
  // Ancestor boundaries and semantic state/bypass terminals keep their policy.
  function contextSourceSide(edge,positions){
    const ctx=positions.context,from=positions.get(edge.source),owner=positions.get(edge.context_lane?.owner);
    if(!ctx?.contextSourceFacing||!owner?.context_gutter||!from||edge.design_route||
      !(edge.bundle_members||[edge]).every(m=>['data','alias','interface-binding'].includes(m.kind)&&!m.condition))return null;
    const ancestors=id=>{const seen=new Set();while(id!=null){seen.add(id);id=ctx.idx.nodes.get(id)?.parent;}return seen;};
    if(ancestors(edge.target).has(edge.source)||ancestors(edge.source).has(edge.target))return null;
    if(from.x+from.w<=owner.x)return 'right';
    if(from.x>=owner.x+owner.w)return 'left';
    return null;
  }
  // A value from a horizontally separate scope can face its receiving frame.
  // This is a geometric entry proposal, independent of operator/family names.
  // Ancestor interfaces and established semantic/context channels keep their
  // own policies; conditional and state dependencies are not reclassified.
  function crossScopeEntries(positions){
    const context=positions.context,idx=context?.idx,result=[];
    if(!idx)return result;
    const ancestry=id=>{const seen=new Set();while(id!=null&&!seen.has(id)){seen.add(id);id=idx.nodes.get(id)?.parent;}return seen;};
    for(const e of context.edges||[]){
      if(e.design_route||e.context_lane||e.layout_after||e.condition||e.iteration||context.feedback?.has(e.id)||
        !(e.bundle_members||[e]).every(m=>['data','alias','interface-binding'].includes(m.kind)&&!m.condition&&!m.iteration&&!m.design_route&&!m.context_lane&&!m.layout_after))continue;
      const a=positions.get(e.source),b=positions.get(e.target),owner=idx.nodes.get(e.target)?.parent,p=positions.get(owner);
      if(!a||!b||!p?.expanded||ancestry(e.source).has(owner)||ancestry(e.source).has(e.target)||ancestry(e.target).has(e.source))continue;
      const side=a.x+a.w<=p.x?'left':a.x>=p.x+p.w?'right':null;
      if(side)result.push({edge:e.id,owner,source_side:side==='left'?'right':'left',target_side:side,
        scope:'Visible cross-scope geometry only; source identity and exact operand slots retained, no input-role or scheduling assertion.'});
    }
    return result;
  }
  // Stage an existing fixed call input beside its single closed consumer.
  // Literal evidence comes from the invocation compiler, not an input name.
  // Only this input's position changes; containment and conditional structure
  // remain intact. The renderer must measure actual paths before accepting it.
  function consumerArguments(positions,literals,preference='left'){
    const ctx=positions.context,idx=ctx?.idx,records=[];
    const result=new Map([...positions].map(([id,p])=>[id,{...p}]));
    result.context={...ctx,routeCache:new Map(),reserved:[]};
    if(!idx)return {positions:result,records};
    const ancestors=id=>{const seen=new Set();while(id!=null&&!seen.has(id)){seen.add(id);id=idx.nodes.get(id)?.parent;}return seen;};

    const overlap=(a,b)=>a.x<b.x+b.w+12&&a.x+a.w+12>b.x&&a.y<b.y+b.h+12&&a.y+a.h+12>b.y;
    const ordinary=e=>!e.design_route&&!e.context_lane&&!e.layout_after&&!e.iteration&&!e.condition&&!ctx.feedback?.has(e.id)&&
      (e.bundle_members||[e]).every(m=>['data','alias','interface-binding','control'].includes(m.kind)&&!m.design_route&&!m.context_lane&&!m.layout_after&&!m.iteration&&!m.condition);
    for(const [id,p]of result){
      if(!literals.has(id))continue;
      const n=idx.nodes.get(id),parent=result.get(n?.parent),uses=(ctx.edges||[]).filter(e=>e.source===id),targets=[...new Set(uses.map(e=>e.target))];
      if(n?.kind!=='interface'||n.role!=='input'||p.expanded||p.cyclic||!parent?.expanded||targets.length!==1||uses.some(e=>!ordinary(e))||
        (ctx.edges||[]).some(e=>e.target===id)||ctx.fixedInputs?.some(r=>r.nodes.includes(id))||ctx.inputDocks?.some(r=>r.node===id))continue;
      const target=targets[0],b=result.get(target);
      if(!b||b.expanded||b.cyclic||idx.nodes.get(target)?.parent!==n.parent)continue;
      const lanes=(ctx.contextLanes||[]).filter(c=>c.owner===n.parent&&c.selected!==false);
      const left=parent.x+16+(parent.design_gutter||0)+(lanes.some(c=>c.side==='left')?(parent.context_gutter||0):0);
      const right=parent.x+parent.w-16-(lanes.some(c=>c.side==='right')?(parent.context_gutter||0):0);
      const sides=preference==='right'?['right','left']:['left','right'],parents=ancestors(id);
      const candidate=sides.map(side=>({side,x:side==='left'?b.x-p.w-20:b.x+b.w+20,y:b.y+(b.h-p.h)/2})).find(c=>
        c.x>=left&&c.x+p.w<=right&&c.y>=parent.y+(parent.header||0)+8&&c.y+p.h<=parent.y+parent.h-16&&
        [...result].every(([other,box])=>other===id||parents.has(other)||!overlap({...p,...c},box)));
      if(!candidate||Math.abs(p.x-candidate.x)+Math.abs(p.y-candidate.y)<1)continue;
      records.push({node:id,parent:n.parent,target,side:candidate.side,before:{x:p.x,y:p.y},after:{x:candidate.x,y:candidate.y},
        edges:uses.map(e=>({edge:e.id,source_port:e.source_port,target_port:e.target_port,kind:e.kind})),
        scope:'Existing invocation-bound literal beside one closed consumer. Canonical value, source ownership, conditions and operand slots retained; no branch pruning, scheduling, purity or input-role inference.'});
      Object.assign(p,{x:candidate.x,y:candidate.y});
    }
    return {positions:result,records};
  }
  // Independent visible operands may share a row even when their producers
  // enter at different heights. This is correspondence, not equal operations
  // or concurrent execution. Keep every existing consumer slot and boundary.
  // A helper's input declaration supplies a stable reading order. Neither
  // port spelling nor the order of projected edges is an ordering contract.
  function declaredOperandOrder(uses,idx,canonicalEdges){
    if(uses.length<2||uses.length>6)return null;
    const rows=[];
    for(const e of uses){
      const n=idx.nodes.get(e.canonical_target),binding=canonicalEdges.find(b=>b.id===e.id),loc=n?.source?.[0];
      if(e.kind!=='interface-binding'||e.evidence!=='source-dependency'||e.bundle_members||e.condition||e.iteration||
        !binding||binding.kind!=='interface-binding'||binding.evidence!=='source-dependency'||binding.condition||binding.iteration||binding.design_route||binding.layout_after||
        binding.source!==e.canonical_source||binding.target!==e.canonical_target||binding.target_port!==e.target_port||
        n?.kind!=='interface'||n.role!=='input'||n.parent!==e.target||n.slot!==e.target_port||
        n.evidence_status!=='static-only'||n.runtime_evidence?.length||n.condition||n.source?.length!==1||
        !loc?.file||!loc.symbol||!Number.isInteger(loc.line)||loc.line<1||!Number.isInteger(loc.column)||loc.column<0)return null;
      rows.push({node:e.source,edge:e.id,input:n.id,owner:n.parent,slot:n.slot,source:{...loc}});
    }
    if(new Set(rows.map(r=>r.owner)).size!==1||new Set(rows.map(r=>r.input)).size!==rows.length||
      new Set(rows.map(r=>JSON.stringify([r.source.file,r.source.symbol]))).size!==1||
      new Set(rows.map(r=>JSON.stringify([r.source.line,r.source.column]))).size!==rows.length)return null;
    rows.sort((a,b)=>a.source.line-b.source.line||a.source.column-b.source.column);
    return {rule_version:'declared-operand-order/1',owner:rows[0].owner,inputs:rows,
      scope:'Source parameter declaration order is a visual preference, not an assertion of execution order or interchangeable operands.'};
  }
  function operandRows(positions,order='existing',canonicalEdges=[],{sink:onlySink}={}){
    const ctx=positions.context,idx=ctx?.idx,records=[],result=new Map([...positions].map(([id,p])=>[id,{...p}]));
    result.context={...ctx,routeCache:new Map(),reserved:[]};
    if(!idx)return {positions:result,records};
    const guarded=n=>!n||!['compute','composite'].includes(n.kind)||n.condition||n.mutable||n.identity_display||n.observed_calls||n.runtime_evidence?.length||n.evidence_status==='runtime-only'||n.repeat_contract||n.iteration||
      ['conditional-region','conditional-collection','loop-template','iteration-region','serial-repeat','repeat-instance','serial-remainder','observed-variant'].includes(n.semantic_type);
    const ordinary=e=>!e.condition&&!e.iteration&&!e.design_route&&!e.layout_after&&!ctx.feedback?.has(e.id)&&
      (e.bundle_members||[e]).every(m=>['data','alias','interface-binding','parameter-read'].includes(m.kind)&&!m.condition&&!m.iteration&&!m.design_route&&!m.layout_after);
    const ancestors=id=>{const seen=new Set();while(id!=null&&!seen.has(id)){seen.add(id);id=idx.nodes.get(id)?.parent;}return seen;};
    const protectedAncestor=id=>[...ancestors(idx.nodes.get(id)?.parent)].some(at=>{const n=idx.nodes.get(at);return !n||['opaque','control'].includes(n.kind)||n.condition||n.mutable||n.identity_display||n.observed_calls||n.runtime_evidence?.length||n.evidence_status==='runtime-only'||n.iteration||
      ['conditional-region','conditional-collection','loop-template','iteration-region','observed-variant'].includes(n.semantic_type);});
    const protectedContents=id=>{const todo=[id],seen=new Set();for(let i=0;i<todo.length;i++){
      const at=todo[i];if(seen.has(at))return true;seen.add(at);const n=idx.nodes.get(at);
      if(!n||['opaque','control'].includes(n.kind)||n.condition||n.mutable||n.identity_display||n.observed_calls||n.runtime_evidence?.length||n.evidence_status==='runtime-only'||n.repeat_contract||n.iteration||
        ['conditional-region','conditional-collection','loop-template','iteration-region','serial-repeat','repeat-instance','serial-remainder','observed-variant'].includes(n.semantic_type))return true;
      todo.push(...idx.children.get(at)||[]);
    }return canonicalEdges.some(e=>(seen.has(e.source)||seen.has(e.target))&&(e.condition||e.iteration||e.design_route||e.layout_after||
      !['data','alias','interface-binding','parameter-read','buffer-read','state-read'].includes(e.kind)));};
    const claimed=new Set(),overlap=(a,b)=>a.x<b.x+b.w+12&&a.x+a.w+12>b.x&&a.y<b.y+b.h+12&&a.y+a.h+12>b.y;
    for(const [sink,s]of result){
      if(onlySink!==undefined&&sink!==onlySink)continue;
      const target=idx.nodes.get(sink),parent=result.get(target?.parent);
      if(guarded(target)||protectedAncestor(sink)||s.expanded||s.cyclic||!parent?.expanded)continue;
      const incoming=(ctx.edges||[]).filter(e=>e.target===sink),ids=[...new Set(incoming.map(e=>e.source))].filter(id=>{
        const n=idx.nodes.get(id),p=result.get(id),uses=(ctx.edges||[]).filter(e=>e.source===id),incident=(ctx.edges||[]).filter(e=>e.source===id||e.target===id);
        return p&&!p.expanded&&!p.cyclic&&!claimed.has(id)&&n?.parent===target.parent&&!guarded(n)&&!protectedContents(id)&&
          uses.length===1&&uses[0].target===sink&&incident.every(ordinary)&&!uses[0].bundle_members;
      });
      if(ids.length<2||ids.length>6)continue;
      const uses=ids.map(id=>incoming.find(e=>e.source===id));
      if(uses.some(e=>!e.target_port)||new Set(uses.map(e=>e.target_port)).size!==uses.length)continue;
      const declaration=order==='declared'?declaredOperandOrder(uses,idx,canonicalEdges):null;
      if(order==='declared'&&!declaration)continue;
      const byX=ids.slice().sort((a,b)=>result.get(a).x-result.get(b).x),centers=byX.map(id=>{const p=result.get(id);return p.x+p.w/2;});
      const ordered=declaration?declaration.inputs.map(r=>r.node):order==='operands'?ids:byX,y=Math.max(...ids.map(id=>result.get(id).y));
      const candidates=ordered.map((id,i)=>({...result.get(id),x:centers[i]-result.get(id).w/2,y}));
      if(candidates.every(p=>p.x===result.get(p.id).x&&p.y===result.get(p.id).y))continue;
      const lanes=(ctx.contextLanes||[]).filter(c=>c.owner===target.parent&&c.selected!==false),left=parent.x+16+(parent.design_gutter||0)+(lanes.some(c=>c.side==='left')?(parent.context_gutter||0):0),
        right=parent.x+parent.w-16-(lanes.some(c=>c.side==='right')?(parent.context_gutter||0):0);
      if(candidates.some((p,i)=>p.x<left||p.x+p.w>right||p.y<parent.y+(parent.header||0)+8||p.y+p.h+20>s.y||
        candidates.some((q,j)=>i!==j&&overlap(p,q))||[...result].some(([other,box])=>!ids.includes(other)&&!ancestors(p.id).has(other)&&overlap(p,box))))continue;
      records.push({parent:target.parent,sink,order,...(declaration?{declaration}:{}),nodes:ordered.map((id,i)=>({node:id,before:{x:result.get(id).x,y:result.get(id).y},after:{x:candidates[i].x,y},
        edge:uses.find(e=>e.source===id).id,target_port:uses.find(e=>e.source===id).target_port})),
        scope:'Independent closed visible operands share a measured row; canonical slots and source ownership retained. No operation equivalence, purity or concurrent execution asserted.'});
      candidates.forEach(p=>{Object.assign(result.get(p.id),{x:p.x,y:p.y});claimed.add(p.id);});
    }
    return {positions:result,records};
  }
  // Delete only globally empty horizontal bands. Protect every body/title,
  // label, terminal and horizontal wire; a common monotone map then shortens
  // vertical wires without changing their order or physical correspondence.
  function emptyBands(positions,routes,windows,labels=[],minimum=16){
    const forbidden=[...positions.values()].map(p=>[p.y-8,p.y+(p.expanded?p.header:p.h)+8]);
    for(const p of labels)forbidden.push([p.y-8,p.y+p.h+8]);
    for(const e of routes){
      const ps=e.route.points;
      for(const p of [ps[0],ps.at(-1)])forbidden.push([p.y-8,p.y+8]);
      for(let i=1;i<ps.length;i++)if(ps[i-1].y===ps[i].y)forbidden.push([ps[i].y-8,ps[i].y+8]);
    }
    const bands=[];
    for(const {top,bottom}of windows){
      let free=[[top,bottom]];
      for(const [a,b]of forbidden)free=free.flatMap(([l,h])=>b<=l||a>=h?[[l,h]]:
        [[l,Math.min(a,h)],[Math.max(l,b),h]].filter(([x,y])=>y>x));
      bands.push(...free.filter(([a,b])=>b-a>=Math.max(1,minimum)));
    }
    const merged=[];
    for(const [top,bottom]of bands.sort((a,b)=>a[0]-b[0])){
      if(merged.length&&top<=merged.at(-1).bottom)merged.at(-1).bottom=Math.max(bottom,merged.at(-1).bottom);
      else merged.push({top,bottom});
    }
    return merged;
  }
  // Equal projected neighbor centers leave physical terminal order ambiguous.
  // Keep nearer neighbors together before using edge IDs to break the tie;
  // this orders drawing terminals, never canonical operands or executions.
  function neighborOrder(items,positions,node,side,near=false){
    const p=positions.get(node),horizontal=side==='top'||side==='bottom';
    const other=item=>item.source?item.edge.target:item.edge.source;
    const coordinate=item=>{const o=positions.get(other(item));return horizontal?o.x+o.w/2:o.y+o.h/2;};
    const distance=item=>{const o=positions.get(other(item));return horizontal?Math.abs(o.y+o.h/2-p.y-p.h/2):Math.abs(o.x+o.w/2-p.x-p.w/2);};
    return items.slice().sort((a,b)=>coordinate(a)-coordinate(b)||
      (near?distance(a)-distance(b)||String(other(a)).localeCompare(String(other(b))):0)||
      a.edge.id.localeCompare(b.edge.id)||Number(a.source)-Number(b.source));
  }
  function coincidentPorts(positions,routes){
    const sides=new Map(),records=[];
    for(const edge of routes)for(const source of [true,false]){
      const node=source?edge.source:edge.target,side=source?edge.route.source_side:edge.route.target_side,key=JSON.stringify([node,side]);
      if(!sides.has(key))sides.set(key,[]);sides.get(key).push({edge,source});
    }
    const key=i=>JSON.stringify([i.edge.id,i.source]);
    for(const [at,items]of sides){
      const [node,side]=JSON.parse(at),p=positions.get(node);
      if(!p||p.expanded||p.cyclic||items.length<2||items.some(i=>!i.edge.route.ok||i.edge.design_route||i.edge.context_lane||i.edge.iteration||i.edge.layout_after||positions.context.feedback?.has(i.edge.id)||
        !(i.edge.bundle_members||[i.edge]).every(e=>['data','alias','interface-binding'].includes(e.kind)&&!e.design_route&&!e.context_lane&&!e.iteration&&!e.layout_after)))continue;
      const before=neighborOrder(items,positions,node,side),after=neighborOrder(items,positions,node,side,true);
      if(before.every((i,n)=>key(i)===key(after[n])))continue;
      // Earlier accepted policies can own physical terminals. Only refine an
      // actual neighbor-order tie, never silently replace a different order.
      const coordinate=i=>{const pt=i.source?i.edge.route.points[0]:i.edge.route.points.at(-1);return side==='top'||side==='bottom'?pt.x:pt.y;};
      const actual=items.slice().sort((a,b)=>coordinate(a)-coordinate(b));
      if(!before.every((i,n)=>key(i)===key(actual[n])))continue;
      const describe=i=>{const other=i.source?i.edge.target:i.edge.source,o=positions.get(other),horizontal=side==='top'||side==='bottom';
        return {edge:i.edge.id,source:i.source,other,coordinate:horizontal?o.x+o.w/2:o.y+o.h/2,distance:horizontal?Math.abs(o.y+o.h/2-p.y-p.h/2):Math.abs(o.x+o.w/2-p.x-p.w/2)};};
      records.push({node,side,before:before.map(describe),after:after.map(describe),
        scope:'Coincident neighbor coordinates only; nearer endpoints stay together. Distinct uses, conditions, canonical values and operand slots retained; no scheduling or value-equivalence claim.'});
    }
    return records;
  }
  // Coordinate uses of one already resolved output value. Every edge and
  // physical terminal survives; the common stem is drawing geometry only.
  function fanoutInk(routes){
    const lines=new Map();
    for(const e of routes)for(let i=1;i<e.route.points.length;i++){
      const a=e.route.points[i-1],b=e.route.points[i],vertical=a.x===b.x;
      const key=JSON.stringify([e.source,e.resolved_source,e.source_port,vertical,vertical?a.x:a.y]);
      if(!lines.has(key))lines.set(key,[]);
      lines.get(key).push(vertical?[Math.min(a.y,b.y),Math.max(a.y,b.y)]:[Math.min(a.x,b.x),Math.max(a.x,b.x)]);
    }
    let length=0;for(const ranges of lines.values()){
      let end=-Infinity;for(const [a,b]of ranges.sort((a,b)=>a[0]-b[0])){length+=Math.max(0,b-Math.max(a,end));end=Math.max(end,b);}
    }return length;
  }
  function fanoutJunctions(routes){
    const points=new Map(routes.flatMap(e=>e.route.points.map(p=>[JSON.stringify(p),p]))),result=[];
    for(const p of points.values()){
      const directions=new Set();
      for(const e of routes)for(let i=1;i<e.route.points.length;i++){
        const a=e.route.points[i-1],b=e.route.points[i];
        if(a.x===b.x&&p.x===a.x&&p.y>=Math.min(a.y,b.y)&&p.y<=Math.max(a.y,b.y)){
          if(Math.min(a.y,b.y)<p.y)directions.add('up');if(Math.max(a.y,b.y)>p.y)directions.add('down');
        }
        if(a.y===b.y&&p.y===a.y&&p.x>=Math.min(a.x,b.x)&&p.x<=Math.max(a.x,b.x)){
          if(Math.min(a.x,b.x)<p.x)directions.add('left');if(Math.max(a.x,b.x)>p.x)directions.add('right');
        }
      }
      if(directions.size>=3)result.push({...p});
    }return result.sort((a,b)=>a.y-b.y||a.x-b.x);
  }
  function sharedFanouts(positions,routes,{forkOffsets=new Map()}={}){
    const ctx=positions.context,groups=new Map(),records=[];
    const ordinary=e=>e.route.ok&&!e.bundle_members&&!e.design_route&&!e.context_lane&&!e.condition&&!e.iteration&&!e.layout_after&&
      !ctx.feedback?.has(e.id)&&['data','alias','interface-binding'].includes(e.kind)&&e.resolved_source&&e.source_port&&
      !e.paper_labels?.length&&e.route.source_side==='bottom'&&e.route.target_side==='top';
    for(const e of routes)if(ordinary(e)){
      const p=positions.get(e.source),n=ctx.idx.nodes.get(e.source);
      if(!p||p.expanded||p.cyclic||!n||n.mutable||n.condition||n.evidence_status==='runtime-only'||
        ['parameter','buffer','state','control'].includes(n.kind))continue;
      const key=JSON.stringify([e.source,e.resolved_source,e.source_port]);
      if(!groups.has(key))groups.set(key,[]);groups.get(key).push(e);
    }
    for(const edges of groups.values()){
      if(edges.length<2||edges.length>6||new Set(edges.map(e=>e.target)).size!==edges.length)continue;
      const starts=edges.map(e=>e.route.points[0]),ends=edges.map(e=>e.route.points.at(-1));
      // Round operations can have different boundary ordinates on one row.
      // Rank eligibility uses actual node tops; every curved terminal stays.
      if(new Set(starts.map(p=>p.y)).size!==1||new Set(edges.map(e=>positions.get(e.target).y)).size!==1)continue;
      const join=starts[0].y+16,fork=Math.min(...ends.map(p=>p.y))-16-(forkOffsets.get(edges[0].source)||0);
      if(fork-join<32)continue;
      const hub=starts.map(p=>p.x).sort((a,b)=>a-b)[Math.floor(starts.length/2)];
      const fresh=edges.map(e=>{
        const s=e.route.points[0],t=e.route.points.at(-1),raw=[s,{x:s.x,y:join},{x:hub,y:join},{x:hub,y:fork},{x:t.x,y:fork},t];
        const points=raw.filter((p,i)=>!i||p.x!==raw[i-1].x||p.y!==raw[i-1].y);
        for(let i=1;i<points.length-1;)if(points[i-1].x===points[i].x&&points[i].x===points[i+1].x||points[i-1].y===points[i].y&&points[i].y===points[i+1].y)points.splice(i,1);else i++;
        return {...e,route:{...e.route,points}};
      });
      // Reuse the router's actual title/body and endpoint obstacle policy.
      if(fresh.some(e=>{const boxes=routeObstacles(e,positions);return e.route.points.some((b,i,ps)=>i&&blocked(ps[i-1],b,boxes));}))continue;
      const junctions=fanoutJunctions(fresh);
      if(!junctions.length)continue;
      records.push({source:edges[0].source,resolved_source:edges[0].resolved_source,source_port:edges[0].source_port,
        edges:edges.map(e=>e.id),hub,join,fork,junctions,routes:fresh,
        terminal_detour_budget:2*starts.reduce((sum,p)=>sum+Math.abs(p.x-hub),0),
        ink_before:fanoutInk(edges),ink_candidate:fanoutInk(fresh),
        scope:'Repeated uses of one resolved output, with distinct original terminals and operand slots. Shared drawing paths do not merge computations, parameters or invocations.'});
    }return records;
  }
  // Architecture views can run upward or enter another region from the side.
  // Build shared drawing trunks from exact output identity and actual ports;
  // no module role, label or source class participates in eligibility.
  function architectureFanouts(positions,routes){
    const ctx=positions.context,groups=new Map(),records=[],opposite={top:'bottom',bottom:'top',left:'right',right:'left'};
    for(const e of routes){
      const side=e.route?.source_side,p=positions.get(e.source),n=ctx.idx.nodes.get(e.source);
      if(!e.route?.ok||!opposite[side]||e.route.target_side!==opposite[side]||e.bundle_members||e.design_route||e.context_lane||
        e.condition||e.iteration||e.layout_after||ctx.feedback?.has(e.id)||!['data','alias','interface-binding'].includes(e.kind)||
        !e.resolved_source||!e.source_port||e.paper_labels?.length||!p||p.expanded||p.cyclic||!n||n.mutable||n.condition||
        n.evidence_status==='runtime-only'||['parameter','buffer','state','control','opaque'].includes(n.kind))continue;
      const vertical=side==='top'||side==='bottom',end=e.route.points.at(-1);
      // Vertical consumers share a measured terminal row. Side-facing users
      // may lie at different heights; their common trunk uses the open gap.
      const key=JSON.stringify([e.source,e.resolved_source,e.source_port,side,vertical?end.y:null]);
      if(!groups.has(key))groups.set(key,[]);groups.get(key).push(e);
    }
    for(const edges of groups.values()){
      if(edges.length<2||edges.length>6)continue;
      const side=edges[0].route.source_side,vertical=side==='top'||side==='bottom',axis=vertical?'y':'x',tangent=vertical?'x':'y',sign=['bottom','right'].includes(side)?1:-1;
      const starts=edges.map(e=>e.route.points[0]),ends=edges.map(e=>e.route.points.at(-1));
      if(new Set(starts.map(p=>p[axis])).size!==1)continue;
      const begin=starts[0][axis]+sign*16,limit=sign*Math.min(...ends.map(p=>sign*p[axis]))-sign*16;
      if(sign*(limit-begin)<32)continue;
      const hub=starts.map(p=>p[tangent]).sort((a,b)=>a-b)[Math.floor(starts.length/2)],at=(a,b)=>({[axis]:a,[tangent]:b});
      // Keep each consumer's existing local detour. A cross-region trunk
      // must not draw straight through a sibling operation on the target row.
      const pivots=vertical?[]:edges.map(e=>{
        const i=e.route.points.findIndex((p,i,ps)=>i&&p[axis]===ps[i-1][axis]&&
          Math.abs(p[tangent]-ps[i-1][tangent])>=16&&sign*(p[axis]-begin)>=0&&sign*(limit-p[axis])>=0);
        return i<1?e.route.points.length-1:i;
      });
      const rails=vertical?[limit]:[...edges.map((e,i)=>e.route.points[pivots[i]][axis]).filter(x=>sign*(x-begin)>=0&&sign*(limit-x)>=0),begin+sign*16,begin+(limit-begin)*.5,limit];
      for(const rail of [...new Set(rails)]){
        if(!vertical&&edges.some((e,i)=>sign*((e.route.points[pivots[i]+1]||e.route.points.at(-1))[axis]-rail)<16))continue;
        const fresh=edges.map((e,i)=>{
          const s=e.route.points[0],t=e.route.points.at(-1),pivot=vertical?t:e.route.points[pivots[i]],
            tail=vertical||pivots[i]===e.route.points.length-1?[t]:e.route.points.slice(pivots[i]+1),raw=[s,at(begin,s[tangent]),at(begin,hub),at(rail,hub),at(rail,pivot[tangent]),...tail];
          return {...e,route:{...e.route,points:simplify(raw)}};
        });
        if(fresh.some(e=>{const boxes=routeObstacles(e,positions);return e.route.points.some((b,i,ps)=>i&&blocked(ps[i-1],b,boxes));}))continue;
        const junctions=fanoutJunctions(fresh);if(!junctions.length)continue;
        records.push({source:edges[0].source,resolved_source:edges[0].resolved_source,source_port:edges[0].source_port,
          edges:edges.map(e=>e.id),method:vertical?'vertical-output-trunk':'side-output-trunk',side,hub,join:begin,fork:rail,junctions,routes:fresh,
          terminal_detour_budget:2*starts.reduce((sum,p)=>sum+Math.abs(p[tangent]-hub),0),
          ink_before:fanoutInk(edges),ink_candidate:fanoutInk(fresh),
          scope:'Exact uses of one resolved output share drawing ink only. Every original edge, source and consumer terminal, operand slot and source-call identity stays distinct.'});
      }
    }
    return records.sort((a,b)=>(b.ink_before-b.ink_candidate)-(a.ink_before-a.ink_candidate)||a.source.localeCompare(b.source)||a.fork-b.fork);
  }
  // Swap two existing source terminals when their outward leads cross. Only
  // the first normal segment and following tangent segment change; all later
  // bends and every consumer terminal remain fixed. No values are merged.
  function sourcePortSwaps(positions,routes){
    const ctx=positions.context,result=[];
    const ordinary=e=>!e.condition&&!e.iteration&&!e.design_route&&!e.context_lane&&!e.layout_after&&
      ['data','alias','interface-binding'].includes(e.kind);
    const eligible=e=>e.route.ok&&!ctx.feedback?.has(e.id)&&
      (e.bundle_members?e.bundle_members.length>0&&ordinary({...e,kind:'data'})&&e.bundle_members.every(ordinary):ordinary(e));
    const leads=[];
    for(const e of routes){
      const p=positions.get(e.source),ps=e.route?.points,side=e.route?.source_side;
      if(!eligible(e)||!p||p.expanded||p.cyclic||p.symbol||!['top','bottom','left','right'].includes(side)||ps.length<4)continue;
      const axis=['top','bottom'].includes(side)?'y':'x',tangent=axis==='y'?'x':'y',sign=['bottom','right'].includes(side)?1:-1;
      if(ps[0][tangent]!==ps[1][tangent]||ps[1][axis]!==ps[2][axis]||
        (ps[1][axis]-ps[0][axis])*sign<4||ps[1][tangent]===ps[2][tangent])continue;
      leads.push({e,axis,tangent,side});
    }
    for(let i=0;i<leads.length;i++)for(let j=i+1;j<leads.length;j++){
      const a=leads[i],b=leads[j],pa=a.e.route.points,pb=b.e.route.points;
      if(a.e.source!==b.e.source||a.side!==b.side||pa[0][a.axis]!==pb[0][a.axis]||pa[0][a.tangent]===pb[0][a.tangent])continue;
      // Only a strict crossing between one normal lead and the other's
      // first tangent is eligible, not a distant crossing or touching bend.
      const crosses=(normal,tan)=>Math.min(tan[1][a.tangent],tan[2][a.tangent])<normal[0][a.tangent]&&
        normal[0][a.tangent]<Math.max(tan[1][a.tangent],tan[2][a.tangent])&&
        Math.min(normal[0][a.axis],normal[1][a.axis])<tan[1][a.axis]&&
        tan[1][a.axis]<Math.max(normal[0][a.axis],normal[1][a.axis]);
      if(!crosses(pa,pb)&&!crosses(pb,pa))continue;
      const fresh=[a,b].map((r,k)=>{
        const ps=r.e.route.points.map(p=>({...p})),other=k?pa:pb;
        ps[0][a.tangent]=other[0][a.tangent];ps[1][a.tangent]=other[0][a.tangent];
        return {...r.e,route:{...r.e.route,points:ps}};
      });
      if(fresh.some(e=>{const ps=e.route.points,boxes=routeObstacles(e,positions);return ps[1][a.tangent]===ps[2][a.tangent]||
        ps.slice(0,3).some((p,i,lead)=>i&&blocked(lead[i-1],p,boxes));}))continue;
      result.push({source:a.e.source,side:a.side,edges:[a.e.id,b.e.id],routes:fresh,
        before:[pa[0],pb[0]],after:fresh.map(e=>e.route.points[0]),
        scope:'Permutation of existing geometric source terminals; canonical source/target slots, bundled uses and all bends after the first tangent remain. No value equivalence, source role or execution assertion.'});
    }
    return result;
  }
  // Parallel labelled wires need clearance where their visible branches meet,
  // not in every helper in the figure. Use the drawing hierarchy after frame
  // ownership; source nesting may no longer be the visible containment tree.
  function labelClearances(idx,edges){
    const pairs=new Map(),regions=new Map();
    for(const e of edges){const key=JSON.stringify([e.source,e.target]);if(!pairs.has(key))pairs.set(key,[]);pairs.get(key).push(e);}
    const parents=id=>{const result=[];let at=idx.nodes.get(id)?.parent??null;while(at!==null){result.push(at);at=idx.nodes.get(at)?.parent??null;}result.push(null);return result;};
    for(const group of pairs.values()){
      if(group.length<2||!group.some(e=>e.condition||e.bundle_members))continue;
      const edge=group[0],a=parents(edge.source),b=new Set(parents(edge.target)),parent=a.find(id=>b.has(id));
      if(!regions.has(parent))regions.set(parent,{parent,gap_y:0,pairs:[]});
      const record=regions.get(parent),gap=32+28*group.length;
      record.gap_y=Math.max(record.gap_y,gap);record.pairs.push({source:edge.source,target:edge.target,edges:group.map(e=>e.id),gap_y:gap});
    }
    return [...regions.values()];
  }
  function layout(idx,roots,visible,edges,offsets={},options={}){
    const positions=new Map(),feedback=new Set(),compoundAlignments=[],branchColumns=[],rankClearances=[],inputDocks=[],fixedInputs=[],sourceForkWidths=[],moduleColumns=[],localPathRows=[];
    const laneOwners=new Map(),contextOwners=new Map(),contextLanes=[];
    const ancestry=id=>{const result=[];while(id!=null){result.push(id);id=idx.nodes.get(id)?.parent;}return result;};
    const laneKinds=['bypass','state-interface','iteration-feedback'];
    if(options.semanticLanes)for(const e of edges)if(laneKinds.includes(e.design_route?.kind)){
      const targetAnc=new Set(ancestry(e.target)),owner=ancestry(e.source).slice(1).find(id=>targetAnc.has(id));
      if(owner){e.design_route.owner=owner;laneOwners.set(owner,(laneOwners.get(owner)||0)+1);}
    }
    if(options.contextLanes)for(const entry of contextEntries(idx,visible,edges,options.contextLanes)){
      if(Array.isArray(options.contextEdges)&&!options.contextEdges.includes(entry.edge)){contextLanes.push({...entry,selected:false});continue;}
      entry.index=contextOwners.get(entry.owner)||0;
      const e=edges.find(e=>e.id===entry.edge);e.context_lane={...entry};delete e.context_lane.edge;
      contextOwners.set(entry.owner,(contextOwners.get(entry.owner)||0)+1);contextLanes.push(entry);
    }
    const gapX=options.gapX??40,gapY=options.gapY??76;
    const guarded=n=>!n||n.condition||n.mutable||n.identity_display||n.observed_calls||n.iteration||n.runtime_evidence?.length||n.evidence_status==='runtime-only'||
      ['opaque','control','state','buffer'].includes(n.kind)||['conditional-region','conditional-collection','loop-template','iteration-region','observed-variant'].includes(n.semantic_type);
    // Pack only an actual short leaf path into the width already available in
    // its parent. A topological ordering alone cannot establish a serial path.
    // This is geometry: all operands, owners and calls stay in the same cut.
    function packLocalPath(id){
      if(!options.localPathRows)return;
      const p=positions.get(id),n=idx.nodes.get(id),kids=(idx.children.get(id)||[]).filter(c=>visible.has(c));
      if(guarded(n)||kids.length<2||kids.length>6||kids.some(c=>guarded(idx.nodes.get(c))||idx.nodes.get(c).kind!=='compute'||positions.get(c).expanded))return;
      const inside=new Set(kids),links=new Map(kids.map(c=>[c,new Set()])),pred=new Map(kids.map(c=>[c,new Set()]));
      for(const e of edges){if(!inside.has(e.source)&&!inside.has(e.target))continue;
        if(e.layout_after||e.design_route&&e.design_route.kind!=='bypass'||(e.bundle_members||[e]).some(m=>!['data','alias','interface-binding'].includes(m.kind)||m.condition||m.iteration))return;
        if(inside.has(e.source)&&inside.has(e.target)){links.get(e.source).add(e.target);pred.get(e.target).add(e.source);}}
      const starts=kids.filter(c=>!pred.get(c).size);if(starts.length!==1||kids.some(c=>links.get(c).size>1||pred.get(c).size>1))return;
      const ordered=[],seen=new Set();let at=starts[0];while(at&&!seen.has(at)){seen.add(at);ordered.push(at);at=[...links.get(at)][0];}
      if(ordered.length!==kids.length||at)return;
      const pad=options.framePaddingFor?.(n)??options.framePadding??32,gap=options.localPathGap??28,available=p.w-pad*2,rows=[];
      for(const child of ordered){const w=positions.get(child).w;if(w>available)return;const row=rows.at(-1);
        if(!row||row.w+gap+w>available)rows.push({ids:[child],w});else{row.ids.push(child);row.w+=gap+w;}}
      if(rows.length>=kids.length)return;
      const height=p.header+rows.reduce((h,r)=>h+Math.max(...r.ids.map(c=>positions.get(c).h)),0)+(rows.length-1)*gap+pad;
      if(height>=p.h)return;
      const before=p.h;let y=p.header;
      for(const [i,row]of rows.entries()){const h=Math.max(...row.ids.map(c=>positions.get(c).h));let x=(p.w-row.w)/2;
        for(const child of i%2?row.ids.slice().reverse():row.ids){const c=positions.get(child);c.x=x;c.y=y+(h-c.h)/2;c.arrangement='local-path-row';x+=c.w+gap;}y+=h+gap;}
      if(options.direction==='up')for(const child of kids){const c=positions.get(child);c.y=p.header+height-pad-c.y-c.h;}
      p.h=height;localPathRows.push({parent:id,ordered,rows:rows.map(r=>r.ids),before,after:height});
    }
    function size(n){
      if(options.nodeSize)return options.nodeSize(n);
      if(n.kind==='compute'&&(['add','mult','mul'].includes(n.operator)||/^aten\.(add|mul)\./.test(n.operator||'')))return {w:64,h:64,symbol:n.operator==='add'||n.operator.startsWith('aten.add.')?'+':'×'};
      if(n.kind==='interface')return {w:130,h:42};
      if(n.kind==='value-alias')return {w:156,h:52};
      if(['parameter','buffer','state'].includes(n.kind))return {w:176,h:58};
      return {w:n.kind==='composite'?244:220,h:74};
    }
    function arrange(kids,parent){
      const gapY=Math.max(options.gapY??76,options.gapYForParent?.(parent)??0);
      const rankColumns=options.rankColumnsFor?.(idx.nodes.get(parent))??options.rankColumns;
      const kidSet=new Set(kids),owners=new Map(),owner=id=>{const key=id;if(owners.has(key))return owners.get(key);while(id!=null&&!kidSet.has(id)){if(id===parent){id=null;break;}id=idx.nodes.get(id)?.parent;}owners.set(key,id);return id;};
      const adj=new Map(kids.map(id=>[id,new Set()])),pred=new Map(kids.map(id=>[id,new Set()]));
      for(const e of edges){const a=owner(e.source),b=owner(e.target);if(a&&b&&a!==b){
        // Only explicitly proved normal-completion backedges may be separated
        // from forward ranking. Other SCCs retain their ordinary cycle layout.
        if(e.design_route?.kind==='iteration-feedback'){feedback.add(e.id);continue;}
        adj.get(a).add(b);pred.get(b).add(a);}}
      // A relation may request a reading order without inventing a data edge.
      // For example, a loop result follows the source body template although
      // zero iterations can bypass that body. Existing dependencies win.
      for(const e of edges)if(e.layout_after){
        const a=owner(e.layout_after),b=owner(e.target);
        if(!a||!b||a===b)continue;
        const todo=[b],seen=new Set();for(let i=0;i<todo.length;i++){const at=todo[i];if(seen.has(at))continue;seen.add(at);todo.push(...adj.get(at)||[]);}
        if(!seen.has(a)){adj.get(a).add(b);pred.get(b).add(a);}
      }
      const scc=components(kids,adj),unit=new Map();scc.forEach((group,i)=>group.forEach(id=>unit.set(id,i)));
      // Relocate an existing external terminal beside its actual consumers.
      // No copied values, role inference, containment or ranking edges arise.
      // This is only a candidate; the publication renderer measures real routes.
      function finish(box,band=null){
        if(!options.inputDocks||!scc.every(g=>g.length===1))return box;
        const guarded=id=>{const n=idx.nodes.get(id);return !n||['opaque','control','state','buffer','parameter'].includes(n.kind)||n.condition||n.mutable||n.identity_display||n.observed_calls||n.evidence_status==='runtime-only'||
          ['conditional-region','conditional-collection','loop-template','iteration-region','observed-variant'].includes(n.semantic_type);};
        const regions=kids.filter(id=>positions.get(id).expanded&&!guarded(id));
        if(!regions.length)return box;
        // A visible conditional/unknown boundary is a valid wire endpoint.
        // Do not traverse its interior or a guarded ancestor. The source
        // stays outside the receiving region with every guarded use intact.
        const endpoint=id=>{const n=idx.nodes.get(id);return n&&!n.mutable&&!n.identity_display&&!n.observed_calls&&n.evidence_status!=='runtime-only'&&
          (['opaque','control'].includes(n.kind)||n.condition||['conditional-region','conditional-collection'].includes(n.semantic_type));};
        const relative=target=>{let id=target,x=0,y=0;while(id!=null&&!kidSet.has(id)){const p=positions.get(id);if(!p||guarded(id)&&!(id===target&&endpoint(id)))return null;x+=p.x;y+=p.y;id=idx.nodes.get(id)?.parent;}
          return regions.includes(id)?{region:id,x:x+positions.get(id).x,y:y+positions.get(id).y}:null;};
        const ordinary=e=>!e.design_route&&!e.layout_after&&(e.bundle_members||[e]).every(m=>['data','alias','interface-binding'].includes(m.kind)&&!m.iteration);
        const inputs=kids.filter(id=>{const n=idx.nodes.get(id);return n.kind==='interface'&&n.role==='input'&&!guarded(id)&&!pred.get(id).size;});
        let remaining=inputs.length;
        const overlap=(a,b)=>a.x<b.x+b.w+gapX&&a.x+a.w+gapX>b.x&&a.y<b.y+b.h+gapY/2&&a.y+a.h+gapY/2>b.y;
        const median=xs=>{xs.sort((a,b)=>a-b);return xs[Math.floor(xs.length/2)];};
        // Keep two entry anchors where available; prioritize the terminals
        // with most distinct visible uses rather than source declaration order.
        const ordered=inputs.slice().sort((a,b)=>edges.filter(e=>e.source===b).length-edges.filter(e=>e.source===a).length);
        for(const id of ordered){
          if(remaining<=Math.min(2,inputs.length-1)||inputDocks.filter(r=>r.parent===parent).length>=4)break;
          const uses=edges.filter(e=>e.source===id),p=positions.get(id);
          if(uses.length<2||uses.some(e=>!ordinary(e))||edges.some(e=>e.target===id))continue;
          const targets=uses.map(e=>{const at=relative(e.target),t=positions.get(e.target);return at?{...at,x:at.x+t.w/2,y:at.y+t.h/2}:null;});
          if(targets.some(t=>!t))continue;
          const top=median(targets.map(t=>t.y))-p.h/2;
          if(top-p.y<3*gapY)continue;
          const cost=a=>targets.reduce((sum,t)=>sum+Math.abs(a.x+a.w/2-t.x)+Math.abs(a.y+a.h/2-t.y),0),before=cost(p);
          const bounds=targets.map(t=>positions.get(t.region)),left=Math.min(...bounds.map(p=>p.x)),right=Math.max(...bounds.map(p=>p.x+p.w));
          const trials=[{side:'left',x:left-gapX-p.w},{side:'right',x:right+gapX}].map(a=>({...a,y:top,w:p.w,h:p.h}));
          const candidate=trials.filter(a=>kids.every(other=>other===id||!overlap(a,positions.get(other)))).sort((a,b)=>cost(a)-cost(b))[0];
          if(!candidate||cost(candidate)>before*.85)continue;
          const record={parent,node:id,side:candidate.side,edges:uses.map(e=>({edge:e.id,target:e.target,source_port:e.source_port,target_port:e.target_port})),regions:[...new Set(targets.map(t=>t.region))],
            conditional_uses:uses.flatMap(e=>(e.bundle_members||[e]).filter(m=>m.condition).map(m=>({edge:m.id,condition:JSON.parse(JSON.stringify(m.condition))}))),
            initial:{x:p.x,y:p.y},candidate:{x:candidate.x,y:candidate.y},estimated_before:before,estimated_after:cost(candidate),
            scope:'One existing source terminal outside receiving regions; exact uses, conditions and source ownership retained. Visible boundaries may receive wires; guarded ancestors are not traversed. Geometry only, no branch pruning, scheduling or input-role assertion.'};
          Object.assign(p,{x:candidate.x,y:candidate.y,arrangement:'input-dock'});inputDocks.push(record);remaining--;
          if(band){band.inputs=band.inputs.filter(other=>other!==id);(band.docked_inputs||=[]).push(id);}
        }
        const moved=inputDocks.filter(r=>r.parent===parent);if(!moved.length)return box;
        const shift=Math.max(0,-Math.min(...kids.map(id=>positions.get(id).x)));
        if(shift)for(const id of kids)positions.get(id).x+=shift;
        for(const record of moved)record.translation_x=shift;
        return {w:Math.max(...kids.map(id=>{const p=positions.get(id);return p.x+p.w;})),h:Math.max(...kids.map(id=>{const p=positions.get(id);return p.y+p.h;}))};
      }
      const ca=scc.map(()=>new Set()),degree=scc.map(()=>0),rank=scc.map(()=>0);
      for(const [a,targets]of adj)for(const b of targets){const x=unit.get(a),y=unit.get(b);if(x!==y&&!ca[x].has(y)){ca[x].add(y);degree[y]++;}}
      const queue=scc.map((_,i)=>i).filter(i=>!degree[i]);
      for(let i=0;i<queue.length;i++)for(const b of ca[queue[i]]){rank[b]=Math.max(rank[b],rank[queue[i]]+1);if(!--degree[b])queue.push(b);}
      // Move slack computations toward their first consumer in the condensed
      // DAG. Inputs, interfaces and SCCs keep their original ranks. Reverse
      // topological order preserves every inter-component dependency; this is
      // a drawing choice, not a claim about execution scheduling or fusion.
      if(options.rankStrategy==='consumer')for(const u of queue.slice().reverse()){
        if(scc[u].length!==1||!ca[u].size||scc[u].some(id=>!pred.get(id).size||idx.nodes.get(id)?.kind==='interface'))continue;
        rank[u]=Math.min(...[...ca[u]].map(v=>rank[v]-1));
      }
      // External inputs may enter next to their first consumer. This shortens
      // long context/state/control wires without copying a value or scheduling
      // a call. Edges, slots and SCC membership are unchanged.
      if(options.inputPlacement==='consumer')for(const u of queue){
        if(scc[u].length!==1||!ca[u].size)continue;
        const id=scc[u][0],n=idx.nodes.get(id);
        if(pred.get(id).size||n?.kind!=='interface'||n.role!=='input')continue;
        rank[u]=Math.min(...[...ca[u]].map(v=>rank[v]-1));
      }
      for(const e of edges){const a=owner(e.source),b=owner(e.target);if(a&&b&&a!==b&&unit.get(a)===unit.get(b))feedback.add(e.id);}
      // SCCs are explicitly kept as cycles; they cannot be topologically sorted
      // into a fictional feed-forward chain. Arrange their members side by side.
      const rows=new Map();for(const id of kids){const r=rank[unit.get(id)];if(!rows.has(r))rows.set(r,[]);rows.get(r).push(id);}
      if(options.alignForks)for(const row of rows.values()){
        const candidates=row.filter(id=>idx.nodes.get(id)?.kind==='compute'&&!positions.get(id).symbol);
        for(const id of candidates){const peers=candidates.filter(other=>[...pred.get(id)].some(p=>pred.get(other).has(p)));if(peers.length>1){const w=Math.max(...peers.map(id=>positions.get(id).w));for(const peer of peers)positions.get(peer).w=w;}}
      }
      // An outer input has no predecessor in this container's condensed DAG.
      // Use its exact visible output slot to recover only the drawing fork.
      // Width padding does not imply common operations, shapes or execution.
      if(options.sourceForkWidths&&!Object.keys(offsets).length)for(const row of rows.values()){
        const guarded=id=>{const seen=new Set();while(id!=null){const n=idx.nodes.get(id);
          if(!n||seen.has(id)||['opaque','control','state','buffer','parameter'].includes(n.kind)||n.condition||n.mutable||n.iteration||
            n.identity_display||n.observed_calls||n.runtime_evidence?.length||n.evidence_status==='runtime-only'||
            ['conditional-region','conditional-collection','loop-template','iteration-region','observed-variant'].includes(n.semantic_type))return true;
          seen.add(id);id=n.parent;}return false;};
        const candidates=new Set(row.filter(id=>idx.nodes.get(id)?.kind==='compute'&&!positions.get(id).symbol&&
          !positions.get(id).expanded&&scc[unit.get(id)].length===1&&!guarded(id)));
        const groups=new Map(),claimedWidths=new Set();
        for(const e of edges)if(candidates.has(e.target)&&owner(e.source)===null&&e.resolved_source===e.source&&
          typeof e.source_port==='string'&&e.source_port.length&&!e.bundle_members&&!e.design_route&&!e.context_lane&&!e.layout_after&&
          !e.condition&&!e.iteration&&['source-dependency','static-source'].includes(e.evidence)&&
          typeof e.target_port==='string'&&e.target_port.length&&(!e.canonical_target||e.canonical_target===e.target)&&
          ['data','alias','interface-binding'].includes(e.kind)&&!guarded(e.source)){
          const key=JSON.stringify([e.source,e.source_port]);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(e);
        }
        for(const group of groups.values()){
          const ids=[...new Set(group.map(e=>e.target))];
          // Never add padding to a wrapped row or a very unequal pair. The
          // normal layout remains available without an extra routing trial.
          if(ids.length<2||ids.length>3||ids.some(id=>claimedWidths.has(id))||rankColumns&&row.length>rankColumns)continue;
          const before=ids.map(id=>({node:id,width:positions.get(id).w})),width=Math.max(...before.map(n=>n.width));
          if(width>Math.min(...before.map(n=>n.width))*1.2||before.every(n=>n.width===width))continue;
          for(const id of ids){positions.get(id).w=width;claimedWidths.add(id);}
          sourceForkWidths.push({parent,source:group[0].source,source_port:group[0].source_port,
            uses:group.map(e=>({edge:e.id,target:e.target,target_port:e.target_port})),before,width,
            max_width_ratio:1.2,scope:'Small equal-width padding for same-rank consumers of one exact external output slot. No computation, shape, purity, parameter sharing or execution claim.'});
        }
      }
      const sorted=[...rows.keys()].sort((a,b)=>a-b),order=new Map();
      // Reserve label space at the receiving rank, not in every rank of its
      // frame. Same-rank/SCC pairs have no unique vertical channel and keep
      // the conservative parent-wide spacing.
      const requests=options.rankLabelClearances?.find(r=>r.parent===parent),rankGaps=new Map();
      let rankRecord=null;
      if(requests){
        const pairs=requests.pairs.map(pair=>{const a=owner(pair.source),b=owner(pair.target),from=a?rank[unit.get(a)]:null,to=b?rank[unit.get(b)]:null;
          const before=from!==null&&to!==null&&from!==to?sorted[sorted.indexOf(Math.max(from,to))-1]:null;
          return {...pair,source_child:a,target_child:b,source_rank:from,target_rank:to,after_rank:before};});
        const fallback=pairs.some(p=>p.after_rank===null);
        for(const r of sorted)rankGaps.set(r,fallback?gapY:options.rankBaseGapY??options.gapY??76);
        if(!fallback)for(const p of pairs)rankGaps.set(p.after_rank,Math.max(rankGaps.get(p.after_rank),p.gap_y));
        rankRecord={parent,mode:fallback?'parent':'rank',reason:fallback?'A same-rank or unranked pair has no unique vertical channel.':null,pairs,ranks:[],applied:true};
        rankClearances.push(rankRecord);
      }
      // Wrapped cells within a rank retain their existing clearance. Only
      // the gaps between distinct dependency ranks are candidates here.
      const rowGapY=gapY;
      const gapAfter=r=>rankGaps.get(r)??gapY;
      for(const row of rows.values())row.forEach((id,i)=>order.set(id,i));
      for(let pass=0;pass<6;pass++)for(const r of pass%2?sorted.slice().reverse():sorted){
        const row=rows.get(r),neighbors=pass%2?adj:pred;
        const score=id=>{const ns=[...neighbors.get(id)].filter(n=>rank[unit.get(n)]!==r);return ns.length?ns.reduce((s,n)=>s+order.get(n),0)/ns.length:order.get(id);};
        const scores=new Map(row.map(id=>[id,score(id)]));row.sort((a,b)=>scores.get(a)-scores.get(b)||order.get(a)-order.get(b));row.forEach((id,i)=>order.set(id,i));
      }
      // Put newly entering interfaces at the edge of the rank so their wires
      // can reach a context/state gutter without traversing another operation.
      if(options.inputPlacement==='consumer')for(const row of rows.values())row.sort((a,b)=>{
        const input=id=>idx.nodes.get(id)?.kind==='interface'&&idx.nodes.get(id)?.role==='input';
        return Number(input(b))-Number(input(a));
      });
      // Trace independent local chains into a common consumer. Columns are
      // dependency paths, not semantic names or execution-parallel branches.
      const branchGroups=[],claimed=new Set();
      if(options.branchColumns)for(const sink of kids){
        // An expanded source container is still one geometric child here.
        // Its visible internals and exact cut edges remain intact; excluding
        // it would wrap independent paths among unrelated context inputs.
        // The renderer still measures the whole candidate before selecting it.
        const safe=id=>{const n=idx.nodes.get(id);return scc[unit.get(id)].length===1&&
          ['compute','composite'].includes(n.kind)&&!n.condition&&!n.mutable&&!n.identity_display&&!n.observed_calls&&
          !['conditional-region','conditional-collection','loop-template','iteration-region','serial-repeat','repeat-instance','serial-remainder'].includes(n.semantic_type);};
        if(!safe(sink))continue;
        const chains=[];
        for(const tip of pred.get(sink)){
          const path=[];let at=tip,next=sink;
          while(safe(at)&&adj.get(at).size===1&&adj.get(at).has(next)&&!claimed.has(at)){
            const uses=edges.filter(e=>owner(e.source)===at&&owner(e.target)===next);
            if(!uses.length||uses.some(e=>e.design_route||e.layout_after||(e.bundle_members||[e]).some(m=>!['data','alias','interface-binding'].includes(m.kind)||m.condition)))break;
            path.unshift(at);if(pred.get(at).size!==1)break;next=at;at=[...pred.get(at)][0];
          }
          if(path.length>=2)chains.push({nodes:path,edges:edges.filter(e=>path.includes(owner(e.source))&&(path.includes(owner(e.target))||owner(e.target)===sink)).map(e=>e.id),
            ports:edges.filter(e=>owner(e.source)===tip&&owner(e.target)===sink).map(e=>({edge:e.id,port:e.target_port}))});
        }
        if(chains.length<2||chains.length>6)continue;
        // Rank equality is a local placement prerequisite, not stage or
        // operator equivalence. Unequal chains retain ordinary DAG geometry.
        const levels=chains[0].nodes.map(id=>rank[unit.get(id)]);
        if(chains.some(c=>c.nodes.length!==levels.length||c.nodes.some((id,i)=>rank[unit.get(id)]!==levels[i])))continue;
        chains.sort((a,b)=>edges.findIndex(e=>e.id===a.ports[0].edge)-edges.findIndex(e=>e.id===b.ports[0].edge));
        const group={parent,sink,chains,widths:chains.map(c=>Math.max(...c.nodes.map(id=>positions.get(id).w))),ranks:levels,
          scope:'visible serial paths into distinct consumer operands; scheduling and stage equivalence not asserted'};
        branchGroups.push(group);for(const c of chains)for(const id of c.nodes)claimed.add(id);branchColumns.push(group);
      }
      if(options.regularModuleColumns&&scc.every(g=>g.length===1)){
        const candidates=sorted.filter(r=>rows.get(r).length===1).map(r=>rows.get(r)[0]).filter(id=>{
          const n=idx.nodes.get(id);return positions.get(id).expanded&&!guarded(n)&&n.kind==='composite'&&
            (n.semantic_contracts?.length||n.contract_stage||n.semantic_type==='source-module');});
        const flow=new Map(kids.map(id=>[id,new Set()]));
        for(const e of edges){const a=owner(e.source),b=owner(e.target);if(a&&b&&a!==b&&!e.layout_after&&(!e.design_route||e.design_route.kind==='bypass')&&
          (e.bundle_members||[e]).every(m=>['data','alias','interface-binding'].includes(m.kind)&&!m.condition&&!m.iteration))flow.get(a).add(b);}
        const reaches=(a,b)=>{const todo=[a],seen=new Set();for(let i=0;i<todo.length;i++){const at=todo[i];if(at===b)return true;if(seen.has(at))continue;seen.add(at);todo.push(...flow.get(at));}return false;};
        if(candidates.length>1&&candidates.every((a,i)=>candidates.slice(i+1).every(b=>reaches(a,b)!==reaches(b,a)))){
          const width=Math.max(...candidates.map(id=>positions.get(id).w));
          for(const id of candidates){const p=positions.get(id),extra=width-p.w;
            for(const child of idx.children.get(id)||[])if(positions.has(child))positions.get(child).x+=extra/2;
            p.w=width;packLocalPath(id);}
          moduleColumns.push({parent,members:candidates,width});
        }
      }
      const grids=sorted.map(r=>{const ids=rows.get(r),cols=Math.min(rankColumns||ids.length,ids.length),widths=Array(cols).fill(0),heights=Array(Math.ceil(ids.length/cols)).fill(0);
        ids.forEach((id,i)=>{const p=positions.get(id);widths[i%cols]=Math.max(widths[i%cols],p.w);heights[Math.floor(i/cols)]=Math.max(heights[Math.floor(i/cols)],p.h);});
        return {cols,widths,heights,w:widths.reduce((s,w)=>s+w,0)+(cols-1)*gapX,h:heights.reduce((s,h)=>s+h,0)+(heights.length-1)*rowGapY};});
      if(branchGroups.length)for(const [i,r]of sorted.entries()){
        const groups=branchGroups.filter(g=>g.ranks.includes(r));if(!groups.length)continue;
        const assigned=new Set(groups.flatMap(g=>g.chains.flatMap(c=>c.nodes.filter(id=>rank[unit.get(id)]===r))));
        const rest=rows.get(r).filter(id=>!assigned.has(id)),bands=[];
        if(rest.length){
          const cols=Math.min(rankColumns||rest.length,rest.length),widths=Array(cols).fill(0),heights=Array(Math.ceil(rest.length/cols)).fill(0);
          rest.forEach((id,j)=>{const p=positions.get(id);widths[j%cols]=Math.max(widths[j%cols],p.w);heights[Math.floor(j/cols)]=Math.max(heights[Math.floor(j/cols)],p.h);});
          bands.push({w:widths.reduce((a,b)=>a+b,0)+(cols-1)*gapX,h:heights.reduce((a,b)=>a+b,0)+(heights.length-1)*rowGapY,
            cells:rest.map((id,j)=>({id,x:widths.slice(0,j%cols).reduce((a,b)=>a+b+gapX,0)+(widths[j%cols]-positions.get(id).w)/2,y:heights.slice(0,Math.floor(j/cols)).reduce((a,b)=>a+b+rowGapY,0)}))});
        }
        for(const g of groups){const step=g.ranks.indexOf(r),ids=g.chains.map(c=>c.nodes[step]);
          bands.push({w:g.widths.reduce((a,b)=>a+b,0)+(ids.length-1)*gapX,h:Math.max(...ids.map(id=>positions.get(id).h)),
            cells:ids.map((id,j)=>({id,x:g.widths.slice(0,j).reduce((a,b)=>a+b+gapX,0)+(g.widths[j]-positions.get(id).w)/2,y:0}))});
        }
        const w=Math.max(...bands.map(b=>b.w)),cells=[];let y=0;
        for(const band of bands){cells.push(...band.cells.map(c=>({...c,x:c.x+(w-band.w)/2,y:c.y+y})));y+=band.h+rowGapY;}
        grids[i]={...grids[i],w,h:y-rowGapY,cells};
      }
      const rowWidths=grids.map(g=>g.w);
      const width=Math.max(0,...rowWidths),rowTops=new Map();let y=0;
      sorted.forEach((r,i)=>{const row=rows.get(r),grid=grids[i],left=(width-rowWidths[i])/2;
        rowTops.set(r,y);
        if(rankRecord)rankRecord.ranks.push({rank:r,nodes:row.slice(),top:y,height:grid.h,gap_after:i<sorted.length-1?gapAfter(r):0});
        if(grid.cells){for(const c of grid.cells){const p=positions.get(c.id);p.x=left+c.x;p.y=y+c.y;p.cyclic=scc[unit.get(c.id)].length>1;}}else row.forEach((id,j)=>{const p=positions.get(id),col=j%grid.cols,gr=Math.floor(j/grid.cols);p.x=left+grid.widths.slice(0,col).reduce((s,w)=>s+w+gapX,0)+(grid.widths[col]-p.w)/2;p.y=y+grid.heights.slice(0,gr).reduce((s,h)=>s+h+rowGapY,0);p.cyclic=scc[unit.get(id)].length>1;});
        y+=grid.h+(i<sorted.length-1?gapAfter(r):0);
      });
      const vertical={w:width,h:Math.max(0,y)};
      // An edge into a late internal stage does not require the whole target
      // frame to start below its producer's frame. Use actual visible ports
      // to align independently entered compound flows in adjacent columns.
      // Source ownership, endpoints and the full compound hierarchy survive.
      if(options.compoundPorts&&!moduleColumns.some(r=>r.parent===parent)&&scc.every(group=>group.length===1)&&kids.filter(id=>positions.get(id).expanded).length>1){
        const relative=(id,ancestor)=>{let y=0,at=id;while(at&&at!==ancestor){y+=positions.get(at)?.y||0;at=idx.nodes.get(at)?.parent;}return at===ancestor?y:null;};
        const weights=new Map(kids.map(id=>[id,new Map()])),entryBindings=[];let late=false;
        const reaches=(from,to)=>{const todo=[from],seen=new Set();for(let i=0;i<todo.length;i++){const at=todo[i];if(at===to)return true;if(seen.has(at))continue;seen.add(at);todo.push(...adj.get(at)||[]);}return false;};
        for(const e of edges){const a=owner(e.source),b=owner(e.target);if(!a||!b||a===b||e.design_route?.kind==='iteration-feedback')continue;
          const pa=positions.get(a),pb=positions.get(b),sy=relative(e.source,a),ty=relative(e.target,b);
          const flows=e.bundle_members||[e],data=flows.every(e=>['data','alias','interface-binding'].includes(e.kind)&&!e.condition);
          // The target needs a distinct, independently sourced entry. Merely
          // nesting a serial operation deeply inside a helper is insufficient.
          const independent=edges.find(other=>{const from=owner(other.source);if(!from||from===a||from===b||owner(other.target)!==b||reaches(a,from))return false;
            const uses=other.bundle_members||[other],entry=relative(other.target,b);
            return uses.every(e=>['data','alias','interface-binding'].includes(e.kind)&&!e.condition)&&entry!==null&&entry<=ty+gapY;
          });
          const internal=data&&pa.expanded&&pb.expanded&&sy!==null&&ty!==null&&e.target!==b&&independent;
          // An independently entered region need not start below the producer
          // of its later context input. This optional drawing convention keeps
          // the cross-region arrow (possibly upward); it does not assert time.
          const guarded=id=>{const n=idx.nodes.get(id);return ['opaque','control'].includes(n.kind)||n.condition||n.mutable||n.identity_display||n.observed_calls||
            ['conditional-region','conditional-collection','loop-template','iteration-region','observed-variant'].includes(n.semantic_type);};
          const entry=internal&&options.compoundStarts&&!e.design_route&&![a,b,e.source,e.target].some(guarded);
          const distance=entry?0:internal?sy+positions.get(e.source).h-ty+gapY:pa.h+gapY;
          if(entry)entryBindings.push({edge:e.id,source_frame:a,target_frame:b,source:e.source,target:e.target,independent_entry:independent.id});
          if(internal&&ty>pb.header+gapY)late=true;
          weights.get(a).set(b,Math.max(weights.get(a).get(b)??-Infinity,distance));
        }
        // Reading-order constraints and any unmodeled dependency retain the
        // conservative full-frame distance. No control boundary is crossed.
        for(const [a,targets]of adj)for(const b of targets)if(!weights.get(a).has(b))weights.get(a).set(b,positions.get(a).h+gapY);
        if(late){
          // A wrapped row of entry interfaces must not push an entire expanded
          // column sideways. Reserve their existing rows above the regions.
          // This is only a geometry candidate: no interface is copied and no
          // dependency, condition, state or execution order is changed.
          const inputs=kids.filter(id=>!pred.get(id).size&&idx.nodes.get(id)?.kind==='interface'&&idx.nodes.get(id)?.role==='input');
          const band=options.compoundInputBand&&options.compoundStarts&&entryBindings.length&&inputs.length>1?
            {inputs,regions:kids.filter(id=>!inputs.includes(id)),gap_y:gapY}:null;
          const floor=band?Math.max(...inputs.map(id=>positions.get(id).y+positions.get(id).h))+gapY:0;
          const tops=new Map(kids.map(id=>[id,band?(inputs.includes(id)?positions.get(id).y:floor):!pred.get(id).size&&idx.nodes.get(id)?.kind==='interface'?positions.get(id).y:0]));
          for(const u of queue){const a=scc[u][0];for(const [b,distance]of weights.get(a))tops.set(b,Math.max(tops.get(b),tops.get(a)+distance));}
          const placed=[],candidate=new Map(),ordinal=new Map(queue.map((u,i)=>[scc[u][0],i]));
          for(const id of kids.slice().sort((a,b)=>tops.get(a)-tops.get(b)||ordinal.get(a)-ordinal.get(b))){
            const p=positions.get(id),top=tops.get(id),overlap=placed.filter(q=>top<q.y+q.h+gapY/2&&top+p.h+gapY/2>q.y);
            const xs=[0,...overlap.map(q=>q.x+q.w+gapX)].sort((a,b)=>a-b);
            if(options.followOutputSources&&!p.expanded&&pred.get(id).size){
              const sources=edges.filter(e=>owner(e.target)===id&&candidate.has(owner(e.source))&&(e.bundle_members||[e]).every(m=>['data','alias','interface-binding'].includes(m.kind)&&!m.condition));
              const centers=sources.map(e=>{const source=owner(e.source);let dx=0,at=e.source;while(at&&at!==source){dx+=positions.get(at).x;at=idx.nodes.get(at)?.parent;}
                return candidate.get(source).x+dx+positions.get(e.source).w/2;});
              if(centers.length)xs.unshift(Math.max(0,centers.reduce((a,b)=>a+b,0)/centers.length-p.w/2));
            }
            const x=xs.find(x=>overlap.every(q=>x+p.w+gapX<=q.x||x>=q.x+q.w+gapX));
            const box={id,x,y:top,w:p.w,h:p.h};candidate.set(id,box);placed.push(box);
          }
          if(band){
            // Use the regions' available width instead of the global rank's
            // column count. Order entries by their actual consumer positions;
            // shared inputs keep one terminal and all of their distinct uses.
            const available=Math.max(...band.regions.map(id=>{const p=candidate.get(id);return p.x+p.w;}),...inputs.map(id=>positions.get(id).w));
            const relativeX=(id,ancestor)=>{let x=0;while(id&&id!==ancestor){x+=positions.get(id).x;id=idx.nodes.get(id)?.parent;}return x;};
            const desired=id=>{const uses=edges.filter(e=>owner(e.source)===id&&band.regions.includes(owner(e.target)));
              return uses.length?uses.reduce((sum,e)=>sum+candidate.get(owner(e.target)).x+relativeX(e.target,owner(e.target))+positions.get(e.target).w/2,0)/uses.length:0;};
            const ordered=inputs.map((id,i)=>({id,i,w:positions.get(id).w,h:positions.get(id).h,desired:desired(id)})).sort((a,b)=>a.desired-b.desired||a.i-b.i);
            const rows=[];let row=[],used=0;
            for(const cell of ordered){if(row.length&&used+gapX+cell.w>available){rows.push(row);row=[];used=0;}row.push(cell);used+=(row.length>1?gapX:0)+cell.w;}
            if(row.length)rows.push(row);let top=0;
            for(const cells of rows){
              let right=-gapX;for(const cell of cells){cell.x=Math.max(right+gapX,Math.min(available-cell.w,cell.desired-cell.w/2));right=cell.x+cell.w;}
              let left=available+gapX;for(const cell of cells.slice().reverse()){cell.x=Math.min(cell.x,left-gapX-cell.w);left=cell.x;}
              for(const cell of cells)Object.assign(candidate.get(cell.id),{x:cell.x,y:top});
              top+=Math.max(...cells.map(c=>c.h))+gapY;
            }
            const shift=top-floor;for(const id of band.regions)candidate.get(id).y+=shift;
          }
          // In upward flow, align independent regions at their output side.
          // Keep each natural height and move only exclusive external inputs
          // with its entry. Shared/context/control inputs are never duplicated.
          if(band&&options.compoundOutputAlignment&&options.direction==='up'){
            const entries=new Map();
            for(const input of inputs){
              const n=idx.nodes.get(input),uses=edges.filter(e=>e.source===input),targets=new Set(uses.map(e=>owner(e.target)));
              if(guarded(input)||n.invocation_binding||targets.size!==1||!uses.length||uses.some(e=>e.design_route||e.layout_after||(e.bundle_members||[e]).some(m=>!['data','alias','interface-binding'].includes(m.kind)||m.condition||m.iteration)))continue;
              const target=[...targets][0];if(!candidate.has(target)||!positions.get(target).expanded||guarded(target))continue;
              if(!entries.has(target))entries.set(target,[]);entries.get(target).push(input);
            }
            const streams=[...entries.keys()];
            if(streams.length>1&&streams.length<=6){
              const bottom=Math.max(...streams.map(id=>candidate.get(id).y+candidate.get(id).h)),saved=new Map();
              for(const stream of streams){const p=candidate.get(stream),dy=bottom-p.y-p.h;
                for(const id of [stream,...entries.get(stream)]){const q=candidate.get(id);saved.set(id,q.y);q.y+=dy;}}
              const boxes=[...candidate.values()],overlap=boxes.some((a,i)=>boxes.slice(i+1).some(b=>a.x<b.x+b.w&&b.x<a.x+a.w&&a.y<b.y+b.h&&b.y<a.y+a.h));
              if(overlap)for(const [id,y]of saved)candidate.get(id).y=y;
              else band.output_alignment=streams.map(id=>({region:id,inputs:entries.get(id),shift:candidate.get(id).y-saved.get(id)}));
            }
          }
          const box={w:Math.max(...placed.map(p=>p.x+p.w)),h:Math.max(...placed.map(p=>p.y+p.h))};
          const score=b=>Math.max(b.w/1.6,b.h);
          const accepted=box.h<vertical.h*.9&&score(box)<score(vertical)*.9&&box.w*box.h<=vertical.w*vertical.h*2;
          compoundAlignments.push({parent,before:vertical,candidate:box,accepted,...(options.compoundStarts?{mode:'entries',entry_bindings:entryBindings}:{}),...(band?{input_band:band}:{}),scope:'visible endpoint geometry; no execution-order assertion'});
          if(accepted){
            if(rankRecord){rankRecord.applied=false;rankRecord.reason='Compound port alignment uses its existing clearance policy.';}
            for(const [id,p]of candidate){Object.assign(positions.get(id),{x:p.x,y:p.y,arrangement:'compound-port-alignment'});}
            return finish(box,band);
          }
        }
      }
      // Fold a long, narrow acyclic rank sequence into a reading path. Nodes
      // within one rank stay parallel; skip edges keep their exact endpoints.
      // Broad branching and SCC feedback retain the ordinary layered layout.
      // Layout carries no claim that adjacent cells have a dependency.
      const prefix=options.foldBoundaryRanks&&rows.get(sorted[0])?.length>1?1:0;
      const suffix=options.foldBoundaryRanks&&rows.get(sorted.at(-1))?.length>1?1:0;
      const foldedRanks=sorted.slice(prefix,sorted.length-suffix||undefined);
      const bypassFlow=options.semanticLanes&&edges.some(e=>laneKinds.includes(e.design_route?.kind)&&owner(e.target));
      if(options.foldSerial&&!moduleColumns.some(r=>r.parent===parent)&&!bypassFlow&&sorted.length>=(options.foldMinRanks??5)&&scc.every(group=>group.length===1)&&foldedRanks.every(r=>rows.get(r).length<=(options.foldMaxParallel??2)&&rows.get(r).length<=(rankColumns||Infinity))){
        const foldGapX=options.foldGapX??gapY;
        const cells=foldedRanks.map(r=>({ids:rows.get(r),w:rowWidths[sorted.indexOf(r)],h:Math.max(...rows.get(r).map(id=>positions.get(id).h))}));
        const topH=prefix?grids[0].h+gapY:0,bottomH=suffix?grids.at(-1).h+gapY:0;
        const score=box=>Math.max(box.w/1.5,box.h)+Math.max(0,box.w-(options.maxWidth||Infinity))*4;let best=null;
        for(let cols=2;cols<cells.length&&cols<=(options.foldMaxColumns??Infinity);cols++){
          const widths=Array(cols).fill(0),heights=Array(Math.ceil(cells.length/cols)).fill(0),grid=[];
          cells.forEach((cell,i)=>{const row=Math.floor(i/cols),col=row%2?cols-1-i%cols:i%cols;widths[col]=Math.max(widths[col],cell.w);heights[row]=Math.max(heights[row],cell.h);grid.push({cell,row,col});});
          const innerW=widths.reduce((s,w)=>s+w,0)+foldGapX*(cols-1);
          const box={w:Math.max(innerW,prefix?rowWidths[0]:0,suffix?rowWidths.at(-1):0),h:topH+bottomH+heights.reduce((s,h)=>s+h,0)+gapY*(heights.length-1)};
          if(score(box)<score(vertical)*(options.foldGain??.8)&&(!best||score(box)<score(best.box)))best={box,widths,heights,grid};
        }
        if(best){if(rankRecord){rankRecord.applied=false;rankRecord.reason='Folded rank columns use their existing clearance policy.';}for(const [rank,{cell,row,col}]of best.grid.entries()){
          const innerW=best.widths.reduce((s,w)=>s+w,0)+foldGapX*(best.widths.length-1);
          let x=(best.box.w-innerW)/2+best.widths.slice(0,col).reduce((s,w)=>s+w+foldGapX,0)+(best.widths[col]-cell.w)/2;
          const y=topH+best.heights.slice(0,row).reduce((s,h)=>s+h+gapY,0)+(best.heights[row]-cell.h)/2;
          for(const id of cell.ids){const p=positions.get(id);p.x=x;p.y=y;p.topological_rank=rank+prefix;p.arrangement='folded-ranks';x+=p.w+gapX;}
        }
          // Wide input/output ranks occupy their own bands; they do not force
          // every column of the computation path to inherit their full width.
          for(const i of [...(prefix?[0]:[]),...(suffix?[sorted.length-1]:[])])for(const id of rows.get(sorted[i])){
            const p=positions.get(id),oldTop=rowTops.get(sorted[i]);p.x+=(best.box.w-width)/2;p.y=p.y-oldTop+(i===0?0:best.box.h-grids[i].h);p.topological_rank=i;p.arrangement='boundary-band';
          }
          return finish(best.box);}
      }
      return finish(vertical);
    }
    function place(id){const n=idx.nodes.get(id),kids=(idx.children.get(id)||[]).filter(c=>visible.has(c)),p={id,x:0,y:0,...size(n),expanded:!!kids.length};positions.set(id,p);
      if(kids.length){
        kids.forEach(place);
        const fixed=kids.filter(c=>options.fixedInputIds?.has(c)&&!edges.some(e=>e.target===c)),body=kids.filter(c=>!fixed.includes(c));
        const box=body.length?arrange(body,id):{w:0,h:0},pad=options.framePaddingFor?.(n)??options.framePadding??32;
        let title=typeof options.frameHeader==='function'?options.frameHeader(n):options.frameHeader??74;
        const titleWidth=Math.max(212,p.w),railGap=28,railRows=[];let row=[],used=0;
        // These are the original canonical terminals, moved beside the source
        // title. Their data/control/effect edges remain real routed edges.
        for(const child of fixed){const at=positions.get(child);if(row.length&&used+railGap+at.w>480){railRows.push(row);row=[];used=0;}row.push(child);used+=(row.length>1?railGap:0)+at.w;}
        if(row.length)railRows.push(row);
        const railHeight=railRows.reduce((h,row)=>h+Math.max(...row.map(c=>positions.get(c).h)),0)+Math.max(0,railRows.length-1)*28;
        // Leave room for the normal 16px terminal stub and 8px obstacle pad,
        // including between rows and above the first body node.
        if(fixed.length)title=options.compactArgumentBand?title+railHeight+24:Math.max(title,railHeight+32);
        const header=title+(options.headerClearance??20),gutter=laneOwners.has(id)?28+Math.min(3,laneOwners.get(id))*20:0;
        p.header=header;p.protected_header_height=title-10;p.design_gutter=gutter;
        const railWidth=Math.max(0,...railRows.map(row=>row.reduce((w,c)=>w+positions.get(c).w,0)+(row.length-1)*railGap));
        p.w=Math.max(options.frameMinWidthFor?.(n)||0,options.nodeSize?212:300,box.w+pad*2+gutter+(contextOwners.has(id)?32+contextOwners.get(id)*16:0),fixed.length?(options.compactArgumentBand?railWidth+pad*2:titleWidth+pad+railWidth+pad):0);
        if(contextOwners.has(id))p.context_gutter=32+contextOwners.get(id)*16;
        p.h=box.h+header+pad;
        for(const child of body){const c=positions.get(child);c.x+=(options.frameCenterBodyFor?.(n)?Math.max(0,(p.w-box.w-pad*2-gutter)/2):0)+pad+gutter+(options.contextLanes==='left'?(p.context_gutter||0):0);c.y=header+(options.direction==='up'?box.h-c.y-c.h:c.y);}
        if(fixed.length){
          p.protected_header_width=titleWidth;
          let top=options.compactArgumentBand?title-railHeight-12:10;for(const row of railRows){let left=options.compactArgumentBand?(p.w-row.reduce((sum,c)=>sum+positions.get(c).w,0)-(row.length-1)*railGap)/2:titleWidth+pad;for(const child of row){const at=positions.get(child);Object.assign(at,{x:left,y:top,arrangement:'fixed-call-argument'});left+=at.w+railGap;}top+=Math.max(...row.map(c=>positions.get(c).h))+28;}
          fixedInputs.push({parent:id,nodes:fixed,title_width:titleWidth,scope:'Existing invocation-bound literal terminals; identity, containment and all dependencies retained. Geometry only.'});
        }
      }
    }
    roots.filter(id=>visible.has(id)).forEach(place);
    const rootBox=arrange(roots.filter(id=>visible.has(id)),null);
    if(options.direction==='up')for(const id of roots.filter(id=>visible.has(id))){const p=positions.get(id);p.y=rootBox.h-p.y-p.h;}
    function absolute(id,dx,dy){const p=positions.get(id),off=offsets[id]||{x:0,y:0};p.x+=dx+off.x;p.y+=dy+off.y;for(const c of idx.children.get(id)||[])if(positions.has(c))absolute(c,p.x,p.y);}
    for(const id of roots)if(positions.has(id))absolute(id,32,30);
    positions.context={protectFrameTitles:options.protectFrameTitles===true,preserveContextEdges:options.contextEdges,contextSourceFacing:options.contextSourceFacing,idx,edges,feedback,compoundAlignments,contextLanes,branchColumns,rankClearances,inputDocks,fixedInputs,sourceForkWidths,moduleColumns,localPathRows,
      entryBandRouting:compoundAlignments.some(r=>entryBandGeometry(r,positions))};return positions;
  }
  function branchGeometry(group,positions){
    const paths=group.chains.map(c=>c.nodes.map(id=>positions.get(id)));
    if(paths.some(ps=>ps.some(p=>!p)))return false;
    const close=(a,b)=>Math.abs(a-b)<1e-6;
    if(!paths.every(ps=>ps.every((p,i)=>close(p.x+p.w/2,ps[0].x+ps[0].w/2)&&(!i||p.y>=ps[i-1].y+ps[i-1].h))))return false;
    if(!paths.every(ps=>ps.every((p,i)=>close(p.y,paths[0][i].y))))return false;
    if(!paths.every((ps,i)=>!i||Math.min(...ps.map(p=>p.x))>=Math.max(...paths[i-1].map(p=>p.x+p.w))))return false;
    const sink=positions.get(group.sink);return !!sink&&paths.every(ps=>sink.y>=ps.at(-1).y+ps.at(-1).h);
  }
  function inputDockGeometry(record,positions){
    const p=positions.get(record.node),parent=positions.get(record.parent),idx=positions.context.idx;
    if(!p||!parent||idx.nodes.get(record.node)?.parent!==record.parent||p.y<parent.y+parent.header||p.x<parent.x||p.x+p.w>parent.x+parent.w||p.y+p.h>parent.y+parent.h)return false;
    const regions=record.regions.map(id=>positions.get(id));if(regions.some(p=>!p))return false;
    if(record.side==='left'?!regions.every(r=>p.x+p.w<=r.x):!regions.every(r=>p.x>=r.x+r.w))return false;
    return (idx.children.get(record.parent)||[]).filter(id=>id!==record.node&&positions.has(id)).every(id=>{
      const q=positions.get(id);return p.x+p.w<=q.x||q.x+q.w<=p.x||p.y+p.h<=q.y||q.y+q.h<=p.y;
    });
  }
  function entryGeometry(record,positions){
    return record.accepted&&record.entry_bindings?.length>0&&record.entry_bindings.every(binding=>{
      const a=positions.get(binding.source_frame),b=positions.get(binding.target_frame);
      return a&&b&&(a.x+a.w<=b.x||b.x+b.w<=a.x)&&a.y<b.y+b.h&&b.y<a.y+a.h;
    });
  }
  function entryBandGeometry(record,positions){
    const band=record.input_band;
    if(!band||!entryGeometry(record,positions)||band.inputs.length<2||!band.regions.length)return false;
    if(![...band.inputs,...band.regions].every(id=>positions.has(id)))return false;
    const floor=Math.max(...band.inputs.map(id=>{const p=positions.get(id);return p.y+p.h;}))+band.gap_y;
    return band.regions.every(id=>positions.get(id).y>=floor);
  }
  const point=(x,y)=>({x,y});
  function simplify(points){const out=[];for(const p of points){if(out.length&&out.at(-1).x===p.x&&out.at(-1).y===p.y)continue;while(out.length>1&&((out.at(-2).x===out.at(-1).x&&out.at(-1).x===p.x)||(out.at(-2).y===out.at(-1).y&&out.at(-1).y===p.y)))out.pop();out.push(p);}return out;}
  function blocked(a,b,boxes){return boxes.some(r=>{
    if(r.circle){const radius=r.w/2,cx=r.x+radius,cy=r.y+radius,d=a.x===b.x?Math.abs(a.x-cx):Math.abs(a.y-cy);if(d>=radius-1e-8)return false;const half=Math.sqrt(radius*radius-d*d);return a.x===b.x?Math.max(a.y,b.y)>cy-half+1e-8&&Math.min(a.y,b.y)<cy+half-1e-8:Math.max(a.x,b.x)>cx-half+1e-8&&Math.min(a.x,b.x)<cx+half-1e-8;}
    return a.x===b.x?a.x>r.x&&a.x<r.x+r.w&&Math.max(a.y,b.y)>r.y&&Math.min(a.y,b.y)<r.y+r.h:a.y>r.y&&a.y<r.y+r.h&&Math.max(a.x,b.x)>r.x&&Math.min(a.x,b.x)<r.x+r.w;
  });}
  // A source owner is evidence provenance, not necessarily the smallest
  // drawing boundary around a certified branch. This proposal keeps the
  // original owner and derives a separate, reversible geometric scope.
  function containedBranchBoundary(idx,positions,edges,representatives,id){
    const p=positions.get(id),owner=idx.nodes.get(id);
    if(!p||p.expanded||owner?.kind!=='composite'||owner.presentation_only)return null;
    const members=Object.keys(representatives).filter(key=>representatives[key]===id),inside=new Set(members);
    if(members.length<2||members.length>256)return null;
    const protectedNode=n=>!n||n.kind==='opaque'||n.mutable||n.identity_display||n.observed_calls||n.runtime_evidence?.length||
      n.evidence_status==='runtime-only'||n.iteration||n.repeat_contract||n.kind==='buffer';
    if(protectedNode(owner)||members.some(key=>protectedNode(idx.nodes.get(key))))return null;
    const incident=edges.filter(e=>inside.has(e.source)||inside.has(e.target));
    if(incident.some(e=>e.iteration||!['data','alias','interface-binding','parameter-read','control'].includes(e.kind)))return null;
    const cuts=incident.filter(e=>inside.has(e.source)!==inside.has(e.target));
    // Control must remain wholly inside the closed boundary. This is a
    // containment proof, not permission to select or erase either branch.
    if(cuts.some(e=>e.kind==='control'||e.condition))return null;
    const conditions=members.filter(key=>idx.nodes.get(key).condition).map(key=>({node:key,condition:idx.nodes.get(key).condition}));
    if(conditions.some(r=>!inside.has(r.condition.branch)||idx.nodes.get(r.condition.branch)?.kind!=='control')||
      incident.some(e=>e.condition&&(!inside.has(e.condition.branch)||idx.nodes.get(e.condition.branch)?.kind!=='control')))return null;
    const phis=members.filter(key=>idx.nodes.get(key).operator==='phi').map(key=>({node:key,inputs:incident.filter(e=>e.target===key)}));
    if(!phis.length||phis.some(r=>!r.inputs.length||r.inputs.length>2||r.inputs.some(e=>e.kind!=='data'||!e.condition||!inside.has(e.source)||
      !inside.has(e.condition.branch)||idx.nodes.get(e.condition.branch)?.operator!=='if'||e.target_port!==e.condition.outcome)||
      r.inputs.some(e=>e.condition.branch!==r.inputs[0].condition.branch)||
      new Set(r.inputs.map(e=>e.condition.outcome)).size!==r.inputs.length||r.inputs.some(e=>!['true','false'].includes(e.condition.outcome))))return null;
    for(const control of new Set(phis.map(r=>r.inputs[0].condition.branch))){
      const branches=incident.filter(e=>e.source===control&&e.kind==='control');
      if(branches.length!==2||new Set(branches.map(e=>e.target_port)).size!==2||branches.some(e=>
        !inside.has(e.target)||!['true','false'].includes(e.target_port)||idx.nodes.get(e.target)?.condition?.branch!==control||
        idx.nodes.get(e.target)?.condition?.outcome!==e.target_port))return null;
    }
    return {boundary:id,members,conditions,phis,control_edges:incident.filter(e=>e.kind==='control'),cuts,
      scope:'Closed drawing boundary retains all conditional alternatives and exact cuts; no branch selection, value substitution or execution claim.'};
  }
  function localBypassScope(g,e,{contained=true}={}){
    if(e.design_route?.kind!=='bypass'||e.bundle_members||e.condition||e.iteration||e.context_lane||e.kind!=='data')return null;
    const c=g.architecture?.semantic_contracts?.find(c=>c.id===e.design_route.certificate),r=c?.roles;
    if(!r?.branch_path?.length||r.branch_path.length>64||e.resolved_source!==r.skip||e.source_port!==r.skip_slot||e.canonical_target!==r.add)return null;
    const source=g.idx.nodes.get(e.source),target=g.idx.nodes.get(e.target);
    if(!(e.source===r.skip||source?.contract_stage?.roles.normalization===r.skip&&e.source_port==='out')||
      !(e.target===r.add||target?.contract_stage?.roles.add===r.add&&target.contract_stage.certificate===c.id))return null;
    const chain=id=>{const result=[];while(id&&!result.includes(id)){result.push(id);id=g.idx.nodes.get(id)?.parent;}return result;};
    const ends=new Set([...chain(e.source),...chain(e.target)]),mapping=[],boundaries=new Map();
    for(const id of r.branch_path){
      const n=g.idx.nodes.get(id),rep=g.representatives[id];
      if(!n||['opaque','state','buffer'].includes(n.kind)||n.mutable||!g.positions.has(rep))return null;
      if(n.kind==='control'||n.condition||n.operator==='phi'){
        if(!contained)return null;
        if(!boundaries.has(rep))boundaries.set(rep,containedBranchBoundary(g.idx,g.positions,g.architecture.edges||[],g.representatives,rep));
        if(!boundaries.get(rep)||n.operator==='phi'&&boundaries.get(rep).phis.find(r=>r.node===id)?.inputs.length!==2)return null;
      }
      if(rep===e.source)return null;
      mapping.push({canonical:id,visible:rep});
    }
    // The final branch operation can be inside the exact Add/Norm stage.
    // Other computations must remain outside both endpoints' ancestry.
    const frontier=[...new Set(mapping.filter(m=>m.visible!==e.target).map(m=>{
      let outer=m.visible;
      for(const id of chain(m.visible)){if(ends.has(id))break;if(g.positions.has(id))outer=id;}
      return outer;
    }))];
    if(!frontier.length||frontier.some(id=>ends.has(id)))return null;
    const ps=frontier.map(id=>g.positions.get(id)),a=g.positions.get(e.source),b=g.positions.get(e.target);
    if(!a||!b||ps.some(p=>p.y<a.y+a.h||p.y+p.h>b.y))return null;
    return {edge:e.id,certificate:c.id,source:e.source,target:e.target,skip:r.skip,skip_slot:r.skip_slot,add:r.add,
      owner:e.design_route.owner,mapping,frontier,side:'left',...(boundaries.size?{contained_boundaries:[...boundaries.values()]}:{})};
  }
  function localBypassGeometry(scope,e,positions){
    const ps=scope?.frontier?.map(id=>positions.get(id)),p=e?.route?.points;
    if(!ps?.length||ps.some(v=>!v)||!e.route.ok||e.id!==scope.edge||e.source!==scope.source||e.target!==scope.target||
      e.design_route?.kind!=='bypass'||e.design_route.certificate!==scope.certificate||e.design_route.owner!==scope.owner||
      e.resolved_source!==scope.skip||e.source_port!==scope.skip_slot||e.canonical_target!==scope.add||
      e.route.source_side!=='left'||e.route.target_side!=='left'||p.length!==4)return false;
    const needsContainment=scope.mapping?.filter(m=>{const n=positions.context?.idx?.nodes.get(m.canonical);return n&&(n.kind==='control'||n.condition||n.operator==='phi');})||[];
    if(needsContainment.length||scope.contained_boundaries?.length){
      const facts=positions.context?.localBypassFacts,idx=positions.context?.idx;
      if(!facts||!idx||!scope.contained_boundaries?.length||scope.mapping.some(m=>facts.representatives[m.canonical]!==m.visible)||
        needsContainment.some(m=>!scope.contained_boundaries.some(r=>r.boundary===m.visible&&
          (idx.nodes.get(m.canonical).operator!=='phi'||r.phis.some(p=>p.node===m.canonical&&p.inputs.length===2))))||
        scope.contained_boundaries.some(r=>JSON.stringify(r)!==JSON.stringify(containedBranchBoundary(idx,positions,facts.edges,facts.representatives,r.boundary))))return false;
    }
    const left=Math.min(...ps.map(p=>p.x)),top=Math.min(...ps.map(p=>p.y)),bottom=Math.max(...ps.map(p=>p.y+p.h));
    return p[0].y===p[1].y&&p[1].x===p[2].x&&p[2].y===p[3].y&&p[0].x>p[1].x&&p[3].x>p[2].x&&
      p[1].x>=left-52&&p[1].x<=left-16&&p[1].y<=top&&p[2].y>=bottom;
  }
  function routeObstacles(e,positions){
    const a=positions.get(e.source),b=positions.get(e.target),context=positions.context,idx=context?.idx;
    const scope=routingScopes.get(positions),ancestors=id=>{if(scope?.ancestors.has(id))return scope.ancestors.get(id);const set=new Set([id]);while(idx?.nodes.get(id)?.parent){id=idx.nodes.get(id).parent;set.add(id);}return set;};
    const sourceAnc=ancestors(e.source),targetAnc=ancestors(e.target),boxes=[],protectTitles=context?.protectFrameTitles===true;
    const bodyBox=(p,pad=0)=>{
      const top=!protectTitles&&p.expanded&&p.header?Math.min(p.h,p.header-10):0;
      return {x:p.x-pad,y:p.y+top-(top?0:pad),w:p.w+2*pad,h:p.h-top+(top?pad:2*pad),circle:!!p.symbol};
    };
    if(protectTitles)for(const [id,p]of positions)if(p.expanded&&p.header&&(sourceAnc.has(id)||targetAnc.has(id)))boxes.push({x:p.x,y:p.y,w:p.protected_header_width??p.w,h:p.protected_header_height??p.header-10});
    for(const [id,p]of positions){
      if(sourceAnc.has(id)||targetAnc.has(id))continue;
      if(scope){if(!scope.covering.get(id).some(parent=>!sourceAnc.has(parent)&&!targetAnc.has(parent)))boxes.push(bodyBox(p,8));continue;}
      let parent=idx?.nodes.get(id)?.parent,covered=false;
      while(parent){if(positions.has(parent)&&!sourceAnc.has(parent)&&!targetAnc.has(parent)){
        const box=bodyBox(positions.get(parent),8);
        if(p.x>=box.x&&p.x+p.w<=box.x+box.w&&p.y>=box.y&&p.y+p.h<=box.y+box.h){covered=true;break;}
      }parent=idx?.nodes.get(parent)?.parent;}
      if(!covered)boxes.push(bodyBox(p,8));
    }
    if(!(e.source!==e.target&&a.expanded&&targetAnc.has(e.source)))boxes.push(bodyBox(a));
    if(!(e.source!==e.target&&b.expanded&&sourceAnc.has(e.target)))boxes.push(bodyBox(b));
    return boxes;
  }
  function allowsPhysicalSides(e,positions){
    // Only physical geometry is free. Certified lanes, control entry, compound
    // boundaries and explicitly routed relations keep their existing policy.
    return e.source!==e.target&&['data','alias','interface-binding','parameter-read'].includes(e.kind)&&
      !e.design_route&&!e.context_lane&&!e.layout_after&&!e.iteration&&!e.condition&&!e.bundle_members&&
      !positions.get(e.source)?.expanded&&!positions.get(e.target)?.expanded&&
      !positions.context?.crossScopePorts?.some(c=>c.edge===e.id);
  }
  function route(e,positions,{terminalsOnly=false}={}){
    const a=positions.get(e.source),b=positions.get(e.target);if(!a||!b)return {points:[],ok:false,reason:'missing-endpoint'};
    const context=positions.context,idx=context?.idx;
    const scope=routingScopes.get(positions),ancestors=id=>{if(scope?.ancestors.has(id))return scope.ancestors.get(id);const set=new Set([id]);while(idx?.nodes.get(id)?.parent){id=idx.nodes.get(id).parent;set.add(id);}return set;};
    const sourceAnc=ancestors(e.source),targetAnc=ancestors(e.target);
    const vertical=b.y>=a.y+a.h,up=a.y>=b.y+b.h,side=!vertical&&!up;
    let ss,ts;
    if(side){ss=b.x>=a.x?'right':'left';ts=ss==='right'?'left':'right';}
    else {ss=vertical?'bottom':'top';ts=vertical?'top':'bottom';}
    // When the endpoint is an expanded ancestor, attach to its *inner* boundary.
    // It is legal to cross ancestors; unrelated containers remain obstacles.
    const startInward=e.source!==e.target&&a.expanded&&targetAnc.has(e.source),endInward=e.source!==e.target&&b.expanded&&sourceAnc.has(e.target);
    const headerControl=e.kind==='control'&&context?.ancestorPorts==='header';
    if(startInward)ss=headerControl?'top':'bottom';if(endInward)ts=headerControl?'top':'bottom';
    if(headerControl&&(startInward||endInward))ss=ts='top';
    const laneOwner=positions.get(e.design_route?.owner);
    const semanticBypass=['bypass','state-interface','iteration-feedback'].includes(e.design_route?.kind)&&laneOwner?.design_gutter;
    if(semanticBypass)ss=ts='left';
    const contextOwner=positions.get(e.context_lane?.owner),contextLane=!!contextOwner?.context_gutter;
    if(contextLane){ts=e.context_lane.side;ss=contextSourceSide(e,positions)||ss;}
    const crossScope=context?.crossScopePorts?.find(c=>c.edge===e.id);
    if(crossScope){ss=crossScope.source_side;ts=crossScope.target_side;}
    const physicalSides=context?.physicalPortSides?.[e.id];
    if(physicalSides&&allowsPhysicalSides(e,positions)){ss=physicalSides[0];ts=physicalSides[1];}
    function sideFor(edge,isSource){
      const from=positions.get(edge.source),to=positions.get(edge.target);if(!from||!to)return null;
      const down=to.y>=from.y+from.h,up=from.y>=to.y+to.h;
      let sourceSide,targetSide;
      if(!down&&!up){sourceSide=to.x>=from.x?'right':'left';targetSide=sourceSide==='right'?'left':'right';}
      else{sourceSide=down?'bottom':'top';targetSide=down?'top':'bottom';}
      const header=edge.kind==='control'&&context?.ancestorPorts==='header';
      if(edge.source!==edge.target&&from.expanded&&ancestors(edge.target).has(edge.source))sourceSide=header?'top':'bottom';
      if(edge.source!==edge.target&&to.expanded&&ancestors(edge.source).has(edge.target))targetSide=header?'top':'bottom';
      if(header&&edge.source!==edge.target&&(from.expanded&&ancestors(edge.target).has(edge.source)||to.expanded&&ancestors(edge.source).has(edge.target)))sourceSide=targetSide='top';
      if(['bypass','state-interface','iteration-feedback'].includes(edge.design_route?.kind)&&positions.get(edge.design_route.owner)?.design_gutter)sourceSide=targetSide='left';
      if(edge.context_lane&&positions.get(edge.context_lane.owner)?.context_gutter){
        targetSide=edge.context_lane.side;sourceSide=contextSourceSide(edge,positions)||sourceSide;
      }
      const crossScope=context?.crossScopePorts?.find(c=>c.edge===edge.id);
      if(crossScope){sourceSide=crossScope.source_side;targetSide=crossScope.target_side;}
      const physicalSides=context?.physicalPortSides?.[edge.id];
      if(physicalSides&&allowsPhysicalSides(edge,positions)){sourceSide=physicalSides[0];targetSide=physicalSides[1];}
      return isSource?sourceSide:targetSide;
    }
    function port(id,other,isSource,which){
      const p=positions.get(id),siblings=[];
      // Folded paths can enter and leave through the same side. Allocate all
      // incident terminals together so the outgoing stub cannot retrace an
      // incoming arrow at the very same physical point.
      if(scope){for(const item of scope.incident.get(id)||[])if(sideFor(item.edge,item.source)===which)siblings.push(item);}
      else for(const edge of context?.edges||[e])for(const source of [true,false])if((source?edge.source:edge.target)===id&&sideFor(edge,source)===which)siblings.push({edge,source});
      const near=context?.coincidentPorts?.some(c=>c.node===id&&c.side===which);
      if(context?.portOrder==='neighbors'||near){
        // Physical order follows the opposite endpoint on this side. It does
        // not change a canonical operand slot or merge repeated uses. Match
        // parallel-edge ties at both ends to avoid an artificial braid.
        siblings.splice(0,siblings.length,...neighborOrder(siblings,positions,id,which,near));
      }
      // Every canonical boundary edge receives a distinct physical terminal.
      const i=siblings.findIndex(x=>x.edge.id===e.id&&x.source===isSource),fraction=(Math.max(0,i)+1)/(siblings.length+1);
      if(which==='top'||which==='bottom'){
        const x=p.x+16+(p.w-32)*fraction,delta=p.symbol?p.w/2-Math.sqrt((p.w/2)**2-(x-p.x-p.w/2)**2):0;
        // A control dependency of an open scope belongs to its header. Its
        // inward stub enters the body without traversing all enclosed stages.
        const header=headerControl&&which==='top'&&(isSource?startInward:endInward);
        return point(x,header?p.y+p.header-10:which==='top'?p.y+delta:p.y+p.h-delta);
      }
      const y=p.y+14+(p.h-28)*fraction,delta=p.symbol?p.w/2-Math.sqrt((p.w/2)**2-(y-p.y-p.h/2)**2):0;
      return point(which==='left'?p.x+delta:p.x+p.w-delta,y);
    }
    const s=port(e.source,e.target,true,ss),t=port(e.target,e.source,false,ts),normals={top:[0,-1],bottom:[0,1],left:[-1,0],right:[1,0]};
    if(terminalsOnly)return {points:[s,t],source_side:ss,target_side:ts};
    const sn=normals[ss],tn=normals[ts],stub=headerControl&&(startInward||endInward)?1:(context?.stubLength??16);
    const start=point(s.x+sn[0]*stub*(startInward?-1:1),s.y+sn[1]*stub*(startInward?-1:1));
    const end=point(t.x+tn[0]*stub*(endInward?-1:1),t.y+tn[1]*stub*(endInward?-1:1));
    // Expanded titles remain pass-through; real nodes, unrelated bodies
    // and endpoint interiors use the same obstacle policy as shared fanouts.
    const boxes=routeObstacles(e,positions);
    const obstacleIndex=boxes.length>64?Geometry.boxes(boxes):null;
    const routeBlocked=(a,b)=>blocked(a,b,obstacleIndex?obstacleIndex.query({x:Math.min(a.x,b.x),y:Math.min(a.y,b.y),w:Math.abs(a.x-b.x),h:Math.abs(a.y-b.y)}):boxes);
    const middle=(start.y+end.y)/2;
    const candidates=[
      [start,point(start.x,end.y),end],
      [start,point(end.x,start.y),end],
      [start,point(start.x,middle),point(end.x,middle),end]
    ];
    // A visibility search can exhaust its budget before finding a nearby
    // parallel rail. During contact repair, also try shifting one interior
    // segment of the existing valid route. Terminals stay fixed; all trial
    // segments still face the same obstacle and congestion checks below.
    const repair=context?.repairRoute?.points,repairCandidates=[];
    if(repair?.length>3&&repair[0].x===s.x&&repair[0].y===s.y&&repair.at(-1).x===t.x&&repair.at(-1).y===t.y){
      // A broad shift can cross several nearby wires even when a narrow
      // parallel corridor is clear. Try sub-grid spacing too; these remain
      // subject to full obstacle, terminal and final figure quality checks.
      for(let i=1;i<repair.length-2;i++)for(const delta of [-12,12,-24,24,-8,8,-4,4]){
        const a=repair[i],b=repair[i+1],vertical=a.x===b.x,horizontal=a.y===b.y;
        if(!vertical&&!horizontal)continue;
        const trial=repair.map(p=>({...p}));
        if(vertical){trial[i].x+=delta;trial[i+1].x+=delta;}else{trial[i].y+=delta;trial[i+1].y+=delta;}
        if(trial.some((p,j)=>j&&p.x!==trial[j-1].x&&p.y!==trial[j-1].y))continue;
        candidates.push(trial);repairCandidates.push(trial);
      }
    }
    const laneCandidates=semanticBypass?[16,36,56].filter(x=>x<laneOwner.design_gutter).flatMap(dx=>{
      const x=laneOwner.x+dx,leave=a.y+a.h+16,enter=b.y-16;
      const corridors=[...new Set([start.y,end.y,a.y-16,leave,enter,b.y+b.h+16,...boxes.flatMap(r=>[r.y-2,r.y+r.h+2])])];
      const nearest=y=>corridors.slice().sort((a,b)=>Math.abs(a-y)-Math.abs(b-y)).slice(0,6);
      return [[start,point(x,start.y),point(x,end.y),end],
        [start,point(start.x,leave),point(x,leave),point(x,enter),point(end.x,enter),end],
        ...nearest(start.y).flatMap(leave=>nearest(end.y).filter(enter=>enter!==leave).map(enter=>
          [start,point(start.x,leave),point(x,leave),point(x,enter),point(end.x,enter),end]))];
    }):[];
    if(contextLane){
      const x=e.context_lane.side==='left'?contextOwner.x+(contextOwner.design_gutter||0)+16+e.context_lane.index*16:contextOwner.x+contextOwner.w-16-e.context_lane.index*16;
      laneCandidates.push([start,point(x,start.y),point(x,end.y),end]);
      const corridors=[...new Set([start.y,a.y+a.h+16,...boxes.flatMap(r=>[r.y-2,r.y+r.h+2])])];
      for(const y of corridors)laneCandidates.push([start,point(start.x,y),point(x,y),point(x,end.y),end]);
      // An entry above a region cannot descend through that region's title
      // to reach its internal gutter. Approach around an ancestor boundary,
      // then enter the gutter below the title. Every segment still passes the
      // same actual obstacle and congestion checks as an ordinary route.
      if(context.entryBandRouting){
        const escapes=[...new Set([...targetAnc].map(id=>positions.get(id)).filter(p=>p?.expanded)
          .map(p=>e.context_lane.side==='left'?p.x-16:p.x+p.w+16))];
        const entries=[...new Set([contextOwner.y+contextOwner.header+8,b.y-16,...boxes.flatMap(r=>[r.y-2,r.y+r.h+2])])]
          .filter(y=>y!==end.y).sort((a,b)=>Math.abs(a-end.y)-Math.abs(b-end.y)).slice(0,8);
        const leaves=[...new Set([start.y,a.y+a.h+16,...boxes.map(r=>r.y+r.h+2)])]
          .filter(y=>y>=start.y).sort((a,b)=>a-b).slice(0,6);
        for(const outside of escapes)for(const leave of leaves)for(const enter of entries)
          laneCandidates.push([start,point(start.x,leave),point(outside,leave),point(outside,enter),point(x,enter),point(x,end.y),end]);
      }
    }
    const reserved=context?.reserved||[];
    // Normalize the fixed reservation snapshot once. Keep its original order
    // so fractional overlap penalties are accumulated in exactly the same
    // sequence as before, including zero-length reserved segments.
    let reservationIndex=null;
    if(scope){
      if(scope.reserved!==reserved||scope.count>reserved.length){scope.reserved=reserved;scope.count=0;scope.segments=Geometry.segments();}
      for(;scope.count<reserved.length;scope.count++)scope.segments.add(...reserved[scope.count]);reservationIndex=scope.segments;
    }
    const reservationBounds=reservationIndex?null:reserved.map(([c,d])=>({vertical:c.x===d.x,x:c.x,y:c.y,
      left:Math.min(c.x,d.x),right:Math.max(c.x,d.x),top:Math.min(c.y,d.y),bottom:Math.max(c.y,d.y)}));
    if(reserved.length)for(const delta of [-12,12,-24,24,-40,40]){
      candidates.push([start,point(start.x,middle+delta),point(end.x,middle+delta),end]);
      const x=(start.x+end.x)/2+delta;candidates.push([start,point(x,start.y),point(x,end.y),end]);
    }
    const clear=ps=>ps.every((p,i)=>!i||!routeBlocked(ps[i-1],p));
    const contextLow=contextLane?(e.context_lane.side==='left'?contextOwner.x+(contextOwner.design_gutter||0):contextOwner.x+contextOwner.w-contextOwner.context_gutter):null;
    const contextHigh=contextLane?(e.context_lane.side==='left'?contextLow+contextOwner.context_gutter:contextOwner.x+contextOwner.w):null;
    const inContext=ps=>contextLane&&ps.some((p,i)=>i&&p.x===ps[i-1].x&&p.y!==ps[i-1].y&&p.x>contextLow&&p.x<contextHigh);
    const verticalReservations=new Map(),horizontalReservations=new Map();
    function congestion(a,b){let penalty=0;
      const vertical=a.x===b.x,left=Math.min(a.x,b.x),right=Math.max(a.x,b.x),top=Math.min(a.y,b.y),bottom=Math.max(a.y,b.y);
      // The reservation snapshot is immutable for this route. A fixed rail
      // can only meet parallel segments on that rail or perpendicular spans
      // covering its coordinate. Preserve the original accumulation order,
      // inclusive endpoints, zero-length segments and all penalty arithmetic.
      const rails=vertical?verticalReservations:horizontalReservations,coordinate=vertical?a.x:a.y;
      let relevant=reservationIndex?reservationIndex.query(a,b):rails.get(coordinate);
      if(!relevant){relevant=reservationBounds.filter(r=>vertical?
        r.vertical?r.x===coordinate:r.left<=coordinate&&coordinate<=r.right:
        r.vertical?r.top<=coordinate&&coordinate<=r.bottom:r.y===coordinate);rails.set(coordinate,relevant);}
      for(const r of relevant){
      if(vertical===r.vertical){
        if(vertical?a.x!==r.x:a.y!==r.y)continue;
        const overlap=vertical?Math.min(bottom,r.bottom)-Math.max(top,r.top):Math.min(right,r.right)-Math.max(left,r.left);
        penalty+=Math.max(0,overlap)*24;
      }else{
        const vx=vertical?a.x:r.x,hy=vertical?r.y:a.y,hleft=vertical?r.left:left,hright=vertical?r.right:right,vtop=vertical?top:r.top,vbottom=vertical?bottom:r.bottom;
        if(vx>hleft&&vx<hright&&hy>vtop&&hy<vbottom)penalty+=context?.crossingCost??18;
        else if(context?.contactCost&&vx>=hleft&&vx<=hright&&hy>=vtop&&hy<=vbottom)penalty+=context.contactCost;
      }
    }return penalty;}
    // Candidate arrays and the obstacle/reservation snapshot do not change
    // during one route. Reuse scores without changing comparison or tie order.
    const lengths=new WeakMap();
    const length=ps=>{if(!lengths.has(ps))lengths.set(ps,ps.reduce((s,p,i)=>s+(i?Math.abs(p.x-ps[i-1].x)+Math.abs(p.y-ps[i-1].y)+congestion(ps[i-1],p):0),0)+ps.length*12);return lengths.get(ps);};
    if(context?.localBypassTrial?.edge===e.id){
      const trial=context.localBypassTrial,points=simplify([s,start,point(trial.x,start.y),point(trial.x,end.y),end,t]);
      const result={points,ok:clear(points),reason:null,feedback:false,source_side:ss,target_side:ts};
      result.ok=result.ok&&localBypassGeometry(trial.scope,{...e,route:result},positions);
      if(!result.ok)result.reason='local-bypass-not-clear-or-not-realized';
      return result;
    }
    // During an explicitly requested repair, compare the shifted rails with
    // the ordinary lane candidates. The normal router keeps its historical
    // lane preference; a repair must be allowed to choose a slightly longer
    // rail when it removes a false junction.
    const routeCandidates=repair?[...repairCandidates,...laneCandidates,...candidates]:laneCandidates;
    let best=(repair?repairCandidates.filter(clear).sort((a,b)=>length(a)-length(b))[0]:null)||routeCandidates.filter(clear).sort((a,b)=>length(a)-length(b))[0]||candidates.filter(clear).sort((a,b)=>length(a)-length(b))[0];
    const crowded=best&&best.some((p,i)=>i&&congestion(best[i-1],p)>100);
    if(!best||crowded){
      // Keep an already selected, feasible side-entry relation during congestion
      // search, independently of the optional entry-band arrangement. Unselected
      // proposals remain soft preferences. Search both
      // direction and gutter-visit state, so an ordinary shortcut cannot win
      // by abandoning the relation and an alternative gutter route can compete.
      const preserveContext=inContext(best||[])&&(context?.entryBandRouting||Array.isArray(context?.preserveContextEdges)&&context.preserveContextEdges.includes(e.id));
      const contextRail=preserveContext?(e.context_lane.side==='left'?contextLow+16+e.context_lane.index*16:contextHigh-16-e.context_lane.index*16):null;
      // Compressed visibility grid; obstacles contribute only their boundaries.
      // First try the endpoint corridor, then expand to include all obstacles.
      for(const margin of [160,Infinity]){
        const local=boxes.filter(r=>r.x+r.w>=Math.min(start.x,end.x)-margin&&r.x<=Math.max(start.x,end.x)+margin&&r.y+r.h>=Math.min(start.y,end.y)-margin&&r.y<=Math.max(start.y,end.y)+margin);
        const nearby=reserved.filter(([a,b])=>Math.max(a.x,b.x)>=Math.min(start.x,end.x)-margin&&Math.min(a.x,b.x)<=Math.max(start.x,end.x)+margin&&Math.max(a.y,b.y)>=Math.min(start.y,end.y)-margin&&Math.min(a.y,b.y)<=Math.max(start.y,end.y)+margin);
        const xs=[...new Set([start.x,end.x,...(preserveContext?[contextRail]:[]),...local.flatMap(r=>[r.x-2,r.x+r.w+2]),...nearby.flatMap(([a,b])=>a.x===b.x?[a.x-12,a.x+12]:[])])].sort((a,b)=>a-b);
        const ys=[...new Set([start.y,end.y,...local.flatMap(r=>[r.y-2,r.y+r.h+2]),...nearby.flatMap(([a,b])=>a.y===b.y?[a.y-12,a.y+12]:[])])].sort((a,b)=>a-b);
        const sx=xs.indexOf(start.x),sy=ys.indexOf(start.y),tx=xs.indexOf(end.x),ty=ys.indexOf(end.y);
        // Both direction states may visit the same undirected adjacent grid
        // segment. Only its obstacle/penalty result is shared; search costs,
        // turn penalties, heap order and the visit budget remain unchanged.
        // This cache belongs to this grid and route, never to another trial.
        const segments=new Map();
        // Numeric identities encode the exact same (cell,direction,lane)
        // state. Heap insertion/tie order and the visit budget stay intact.
        const key=(x,y,d,lane=false)=>((y*xs.length+x)*3+(d==='h'?0:d==='v'?1:2))*2+Number(!!lane),cost=new Map(),prev=new Map(),heap=[];
        function push(item){heap.push(item);let i=heap.length-1;while(i){const p=(i-1)>>1;if(heap[p].f<=item.f)break;heap[i]=heap[p];i=p;}heap[i]=item;}
        function pop(){const top=heap[0],last=heap.pop();if(heap.length){let i=0;while(i*2+1<heap.length){let j=i*2+1;if(j+1<heap.length&&heap[j+1].f<heap[j].f)j++;if(heap[j].f>=last.f)break;heap[i]=heap[j];i=j;}heap[i]=last;}return top;}
        const initial=key(sx,sy,'s');cost.set(initial,0);push({x:sx,y:sy,d:'s',g:0,f:0,k:initial});let final=null,visits=0;
        while(heap.length&&visits++<24000){const cur=pop();if(cur.g!==cost.get(cur.k))continue;
          if(cur.x===tx&&cur.y===ty&&(!preserveContext||cur.lane)){final=cur.k;break;}
          for(let direction=0;direction<4;direction++){
            const dx=direction===0?-1:direction===1?1:0,dy=direction===2?-1:direction===3?1:0,d=direction<2?'h':'v';
            const x=cur.x+dx,y=cur.y+dy;if(x<0||y<0||x>=xs.length||y>=ys.length)continue;
            const p=point(xs[x],ys[y]),from=point(xs[cur.x],ys[cur.y]);
            const segmentKey=(Math.min(y,cur.y)*xs.length+Math.min(x,cur.x))*2+(d==='v'?1:0);
            let segment=segments.get(segmentKey);
            if(!segment){const hit=routeBlocked(from,p);segment={blocked:hit,penalty:hit?0:congestion(from,p)};segments.set(segmentKey,segment);}
            if(segment.blocked)continue;
            const lane=preserveContext&&(cur.lane||d==='v'&&p.x>contextLow&&p.x<contextHigh);
            const g=cur.g+Math.abs(p.x-from.x)+Math.abs(p.y-from.y)+segment.penalty+(cur.d!==d&&cur.d!=='s'?24:0),k=key(x,y,d,lane);
            if(g>=(cost.get(k)??Infinity))continue;cost.set(k,g);prev.set(k,cur.k);
            push({x,y,d,lane,g,k,f:g+Math.abs(p.x-end.x)+Math.abs(p.y-end.y)});
          }
        }
        if(final!==null){const found=[];for(let k=final;k!==undefined;k=prev.get(k)){const cell=Math.floor(k/6),x=cell%xs.length,y=Math.floor(cell/xs.length);found.push(point(xs[x],ys[y]));}found.reverse();
          if((!semanticBypass||!best||found.some(p=>p.x>laneOwner.x&&p.x<laneOwner.x+laneOwner.design_gutter))&&
            (!preserveContext||inContext(found))&&(!best||length(found)<length(best)))best=found;break;}
      }
    }
    if(!best)return {points:simplify([s,start,point(start.x,end.y),end,t]),ok:false,reason:'no-obstacle-free-route-within-budget'};
    const points=simplify([s,...best,t]);
    const ok=clear(points);
    return {points,ok,reason:ok?null:'endpoint-stub-obstructed',feedback:e.source===e.target||context?.feedback.has(e.id)||false,
      source_side:ss,target_side:ts};
  }
  // Shorten an existing orthogonal subpath without moving either terminal.
  // This is a geometry proposal only; the renderer must measure conflicts,
  // labels, exact uses and realized relations before accepting a shortcut.
  function routeShortcuts(edge,positions,labelBoxes=[]){
    const ctx=positions.context,ps=edge.route?.points;
    if(!edge.route?.ok||!ps||ps.length<4||ps.length>24||edge.bundle_members||edge.design_route||edge.context_lane||edge.layout_after||edge.iteration||
      ctx?.feedback?.has(edge.id)||!['data','alias','interface-binding','parameter-read','buffer-read'].includes(edge.kind))return [];
    const length=points=>points.reduce((sum,p,i)=>sum+(i?Math.abs(p.x-points[i-1].x)+Math.abs(p.y-points[i-1].y):0),0),before=length(ps);
    const boxes=[...routeObstacles(edge,positions),...labelBoxes],seen=new Set(),result=[];
    const simplify=points=>{const out=[];for(const p of points){if(out.at(-1)?.x===p.x&&out.at(-1)?.y===p.y)continue;
      while(out.length>1){const a=out.at(-2),b=out.at(-1);
        if(a.x===b.x&&b.x===p.x&&b.y>=Math.min(a.y,p.y)&&b.y<=Math.max(a.y,p.y)||
          a.y===b.y&&b.y===p.y&&b.x>=Math.min(a.x,p.x)&&b.x<=Math.max(a.x,p.x))out.pop();else break;}out.push({...p});}return out;};
    const direction=(a,b)=>[Math.sign(b.x-a.x),Math.sign(b.y-a.y)].join(',');
    const selfClear=points=>{
      for(let i=1;i<points.length-1;i++){const a=points[i-1],b=points[i],c=points[i+1];
        if(a.x===b.x&&b.x===c.x||a.y===b.y&&b.y===c.y)return false;
      }
      for(let i=1;i<points.length;i++)for(let j=i+2;j<points.length;j++){
      const a=points[i-1],b=points[i],c=points[j-1],d=points[j];
      if(Math.max(Math.min(a.x,b.x),Math.min(c.x,d.x))<=Math.min(Math.max(a.x,b.x),Math.max(c.x,d.x))&&
        Math.max(Math.min(a.y,b.y),Math.min(c.y,d.y))<=Math.min(Math.max(a.y,b.y),Math.max(c.y,d.y)))return false;
    }return true;};
    const xs=[...new Set([...ps.flatMap(p=>[p.x-4,p.x+4,p.x-12,p.x+12]),...boxes.flatMap(r=>[r.x-2,r.x+r.w+2])])];
    const ys=[...new Set([...ps.flatMap(p=>[p.y-4,p.y+4,p.y-12,p.y+12]),...boxes.flatMap(r=>[r.y-2,r.y+r.h+2])])];
    // Wider removed spans first. Bound work independently of graph/source names.
    let attempts=0;
    outer:for(let span=ps.length-1;span>=2;span--)for(let i=0;i+span<ps.length;i++){
      const j=i+span,a=ps[i],b=ps[j],middles=[[{x:a.x,y:b.y}],[{x:b.x,y:a.y}],
        ...xs.map(x=>[{x,y:a.y},{x,y:b.y}]),...ys.map(y=>[{x:a.x,y},{x:b.x,y}])];
      for(const middle of middles){if(++attempts>8192)break outer;
        const points=simplify([...ps.slice(0,i+1),...middle,...ps.slice(j)]),wire=length(points);
        if(wire>=before-.1||points.length<2||direction(ps[0],ps[1])!==direction(points[0],points[1])||
          direction(ps.at(-2),ps.at(-1))!==direction(points.at(-2),points.at(-1)))continue;
        const key=JSON.stringify(points);if(seen.has(key))continue;seen.add(key);
        if(!selfClear(points)||points.some((p,k)=>k&&blocked(points[k-1],p,boxes)))continue;
        result.push({points,wire,removed_span:[i,j]});
      }
    }
    return result.sort((a,b)=>a.wire-b.wire||a.points.length-b.points.length).slice(0,64);
  }
  function path(e,positions){const r=route(e,positions);return r.points.map((p,i)=>`${i?'L':'M'}${p.x},${p.y}`).join(' ');}
  const api={withRoutingIndex,allowsPhysicalSides,routeShortcuts,layout,route,path,components,blocked,routeObstacles,sourcePortSwaps,sharedFanouts,architectureFanouts,fanoutInk,fanoutJunctions,contextEntries,contextSourceSide,crossScopeEntries,consumerArguments,operandRows,declaredOperandOrder,emptyBands,neighborOrder,coincidentPorts,regionFollowers,branchGeometry,entryGeometry,entryBandGeometry,inputDockGeometry,labelClearances,localBypassScope,localBypassGeometry};root.SemanticLayout=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
