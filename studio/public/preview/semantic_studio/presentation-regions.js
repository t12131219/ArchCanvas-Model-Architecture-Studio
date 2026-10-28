/* Candidate boundaries are selected from dependencies and local facts. The
 * result is a presentation partition, never a certificate of an algorithm. */
(function(root){
  'use strict';
  const VERSION='presentation-regions/2',copy=x=>JSON.parse(JSON.stringify(x));
  function candidates({nodes,children,parent,edges,relations,resolve,eligible,maxUnits=8}){
    const by=new Map(nodes.map(n=>[n.id,n])),units=(children.get(parent)||[]).filter(eligible),active=new Set(units);
    const owner=id=>{while(id!=null&&!active.has(id)){if(id===parent)return null;id=by.get(id)?.parent;}return id;};
    const closure=id=>{const out=[],todo=[id];for(let i=0;i<todo.length;i++){out.push(todo[i]);todo.push(...children.get(todo[i])||[]);}return out;};
    const facts=new Map();for(const r of relations){if(!facts.has(r.node))facts.set(r.node,[]);facts.get(r.node).push(r);}
    const reasons=new Map(units.map(id=>[id,[...new Set(closure(id).flatMap(cid=>{
      const n=by.get(cid),rs=facts.get(cid)||[];
      return [n.kind==='opaque'?'unknown':null,n.mutable?'effects':null,n.kind==='control'?'control':null,n.condition?'condition':null,
        rs.some(r=>r.type==='state-interface')?'state-interface':null,rs.some(r=>r.type==='selection')?'selection-interface':null,['loop-template','iteration-region'].includes(n.semantic_type)?'iteration':null,
        cid===id&&n.kind==='composite'&&!n.presentation_only?'source-interface':null,
        ['branch-region','dependency-band','serial-repeat','repeat-instance','observed-module-call'].includes(n.semantic_type)?'structural-interface':null].filter(Boolean);
    }))]]));
    // Small ordinary scopes already have a meaningful frontier. This planner
    // addresses broad mixed scopes where arbitrary count chunks lose boundaries.
    if(units.length<9||![...reasons.values()].some(rs=>rs.some(r=>['unknown','effects','control','condition','state-interface','iteration'].includes(r))))return null;
    // A join that reconnects a protected interface to ordinary computation is
    // a useful exposed connection point. It must not pull both sides into one
    // region merely because a residual or escaping result connects them.
    const interfaces=new Set(units.filter(id=>reasons.get(id).length));
    for(const id of units)if(!reasons.get(id).length){
      const incoming=edges.filter(e=>['data','alias','interface-binding'].includes(e.kind)&&owner(e.target)===id)
        .map(e=>owner(resolve(e.source,e.source_port))).filter(source=>source&&source!==id);
      if(new Set(incoming).size>1&&incoming.some(source=>interfaces.has(source)))reasons.get(id).push('boundary-join');
    }
    const proposals=[],rejected=[],claimed=new Set(),allNext=new Map(units.map(id=>[id,new Set()]));
    for(const e of edges){const a=owner(resolve(e.source,e.source_port)),b=owner(e.target);if(a&&b&&a!==b)allNext.get(a).add(b);}
    function proposal(members,kind){
      const selected=new Set(members),outside=new Set(),todo=[];
      for(const id of members)for(const next of allNext.get(id))if(!selected.has(next)&&!outside.has(next)){outside.add(next);todo.push(next);}
      for(let i=0;i<todo.length;i++)for(const next of allNext.get(todo[i])){
        if(selected.has(next)){rejected.push({kind,members,reason:'dependency-leaves-and-reenters-region'});return null;}
        if(!outside.has(next)){outside.add(next);todo.push(next);}
      }
      const canonical=new Set(members.flatMap(closure)),cuts=edges.filter(e=>canonical.has(e.source)!==canonical.has(e.target));
      const incoming=cuts.filter(e=>canonical.has(e.target)),outgoing=cuts.filter(e=>canonical.has(e.source));
      const internal=edges.filter(e=>canonical.has(e.source)&&canonical.has(e.target));
      const escaping=[...new Set(outgoing.map(e=>JSON.stringify([e.source,e.source_port])))];
      const result={kind,members,canonical_members:[...canonical],boundary_edges:cuts.map(e=>e.id),
        input_edges:incoming.map(e=>e.id),output_edges:outgoing.map(e=>e.id),escaping_results:escaping.map(s=>JSON.parse(s)),
        internal_edges:internal.length,cut_edges:cuts.length,cohesion:internal.length/Math.max(1,internal.length+cuts.length),
        claims:{algorithm:'not-asserted',purity:'not-asserted',execution_order:'canonical-dependencies-only'},status:'selected'};
      proposals.push(result);members.forEach(id=>claimed.add(id));return result;
    }
    // A condition and its governed bodies are one possible container. Gather
    // alternatives from actual branch bindings; no adjacency or name inference.
    const conditions=new Map();
    for(const r of relations)if(r.type==='conditional-region'){
      const control=r.properties.condition?.branch,a=owner(control),b=owner(r.node);
      if(!a||!b||a===b)continue;
      if(!conditions.has(control))conditions.set(control,new Set([a]));conditions.get(control).add(b);
    }
    for(const r of relations)if(r.type==='conditional-join')for(const binding of r.bindings){
      const set=conditions.get(binding.condition?.branch),id=owner(r.node);if(set&&id)set.add(id);
    }
    for(const members of conditions.values()){
      const ids=[...members];
      if(ids.length>1&&ids.length<=maxUnits&&!ids.some(id=>claimed.has(id)||reasons.get(id).some(r=>['unknown','effects','state-interface','iteration','structural-interface'].includes(r))))proposal(ids,'conditional-collection');
    }
    const ordinary=units.filter(id=>!claimed.has(id)&&!reasons.get(id).length),allowed=new Set(ordinary);
    const adj=new Map(ordinary.map(id=>[id,new Set()])),next=new Map(ordinary.map(id=>[id,new Set()]));
    for(const e of edges){
      if(!['data','alias','interface-binding'].includes(e.kind)||e.condition)continue;
      const a=owner(resolve(e.source,e.source_port)),b=owner(e.target);
      if(a!==b&&allowed.has(a)&&allowed.has(b)){adj.get(a).add(b);adj.get(b).add(a);next.get(a).add(b);}
    }
    const visited=new Set();
    for(const first of ordinary){
      if(visited.has(first))continue;
      const members=[],todo=[first];visited.add(first);
      for(let i=0;i<todo.length;i++){const id=todo[i];members.push(id);for(const n of adj.get(id))if(!visited.has(n)){visited.add(n);todo.push(n);}}
      // A component too large for one readable detail panel stays untouched;
      // count-based fallback can still partition it with explicit cuts. Do not
      // turn an SCC or a disconnected set into an apparent serial pipeline.
      const degree=new Map(members.map(id=>[id,0]));for(const id of members)for(const n of next.get(id))degree.set(n,degree.get(n)+1);
      const sorted=members.filter(id=>!degree.get(id));for(let i=0;i<sorted.length;i++)for(const n of next.get(sorted[i])){degree.set(n,degree.get(n)-1);if(!degree.get(n))sorted.push(n);}
      if(sorted.length===members.length&&members.length>1&&members.length<=maxUnits)proposal(sorted,'computation-region');
    }
    return {schema:VERSION,parent,proposals,rejected,protected:units.filter(id=>reasons.get(id).length&&!claimed.has(id)).map(id=>({id,reasons:reasons.get(id)})),
      ungrouped:units.filter(id=>!claimed.has(id)),basis:'local-boundaries-and-connected-acyclic-computation'};
  }
  function predicates({ir,plan}){
    const nodes=plan.nodes.map(n=>({...n})),by=new Map(nodes.map(n=>[n.id,n])),raw=new Map(ir.nodes.map(n=>[n.id,n])),rows=[],claimed=new Set();
    const guarded=n=>!n||n.condition||n.mutable||n.identity_display||n.observed_calls||n.runtime_evidence?.length||n.evidence_status==='runtime-only'||n.kind==='opaque';
    const effect=n=>!n||n.mutable||n.identity_display||n.observed_calls||n.runtime_evidence?.length||n.evidence_status==='runtime-only'||
      ['opaque','state','buffer'].includes(n.kind)||n.repeat_contract||n.iteration;
    const changes=new Map();
    for(const group of nodes){
      const selection=group.boundary_selection;
      if(!group.presentation_only||group.semantic_type!=='conditional-collection'||!selection||selection.members.length>=8)continue;
      const controls=nodes.filter(n=>n.parent===group.id&&n.kind==='control'&&n.operator==='if');
      if(controls.length!==1)continue;
      const control=controls[0],inputs=ir.edges.filter(e=>e.target===control.id),edge=inputs.length===1?inputs[0]:null,test=edge&&by.get(edge.source);
      // The comparison joins its existing if container only after logical
      // detail allocation. It cannot release budget to open unrelated scopes.
      if(guarded(control)||edge?.kind!=='control'||edge.condition||!test||test.kind!=='compute'||test.operator!=='compare'||
        !raw.has(test.id)||test.parent!==group.parent||guarded(test)||test.semantic_contracts?.length||claimed.has(test.id)||
        ir.edges.filter(e=>e.source===test.id).length!==1||ir.edges.some(e=>e.target===test.id&&(e.condition||!['data','alias','interface-binding'].includes(e.kind)))||
        selection.canonical_members.some(id=>effect(raw.get(id)))||ir.edges.some(e=>e.target===test.id&&selection.canonical_members.includes(e.source))||
        plan.relation_graph?.relations.some(r=>r.node===test.id&&['state-interface','selection','same-object-calls','observed-parameter-aliases'].includes(r.type)))continue;
      const members=[test.id,...group.canonical_members],inside=new Set(members);
      const cuts=ir.edges.filter(e=>inside.has(e.source)!==inside.has(e.target)),incoming=cuts.filter(e=>inside.has(e.target)),outgoing=cuts.filter(e=>inside.has(e.source));
      const predicate={node:test.id,control:control.id,edge:edge.id,source_port:edge.source_port??'out',target_port:edge.target_port??'in',
        label:control.label||'if',scope:'Direct exclusive comparison input to this source if; no purity or branch reachability claim.'};
      const next={...selection,members:[test.id,...selection.members],canonical_members:members,boundary_edges:cuts.map(e=>e.id),
        input_edges:incoming.map(e=>e.id),output_edges:outgoing.map(e=>e.id),escaping_results:[...new Set(outgoing.map(e=>JSON.stringify([e.source,e.source_port])))].map(s=>JSON.parse(s)),
        internal_edges:ir.edges.filter(e=>inside.has(e.source)&&inside.has(e.target)).length,cut_edges:cuts.length,predicate};
      next.cohesion=next.internal_edges/Math.max(1,next.internal_edges+cuts.length);
      group.canonical_members=members;group.boundary_ports=cuts.map(e=>({...e}));group.boundary_selection=next;group.condition_predicate=predicate;
      group.label='If '+predicate.label;group.region_summary='Conditional alternatives · exact interfaces';test.parent=group.id;
      changes.set(group.id,next);claimed.add(test.id);rows.push({group:group.id,...predicate,canonical_members:members,cuts:group.boundary_ports});
    }
    const publication=plan.publication?{...plan.publication,boundary_plans:plan.publication.boundary_plans?.map(p=>({...p,proposals:p.proposals.map(c=>changes.get(c.id)||c)}))}:plan.publication;
    const findings=plan.findings?.map(f=>changes.has(f.id)?{...f,label:by.get(f.id).label,members:changes.get(f.id).members.slice(),
      roles:{...f.roles,units:changes.get(f.id).members.slice(),boundary_selection:changes.get(f.id)},
      proof:[...f.proof,'The direct comparison is exclusively consumed by this source if; predicate and branch details remain expandable.']}:f);
    return {plan:{...plan,nodes,publication,findings},rows};
  }
  function returns({ir,plan}){
    const nodes=plan.nodes.map(n=>({...n})),by=new Map(nodes.map(n=>[n.id,n])),raw=new Map(ir.nodes.map(n=>[n.id,n]));
    const children=new Map(),ins=new Map(),uses=new Map(),rows=[],claimed=new Set(),changes=new Map();
    for(const n of nodes){if(!children.has(n.parent))children.set(n.parent,[]);children.get(n.parent).push(n.id);}
    for(const e of ir.edges){if(!ins.has(e.target))ins.set(e.target,[]);ins.get(e.target).push(e);if(!uses.has(e.source))uses.set(e.source,[]);uses.get(e.source).push(e);}
    const closure=id=>{const out=[],todo=[id];for(let i=0;i<todo.length;i++){out.push(todo[i]);todo.push(...children.get(todo[i])||[]);}return out;};
    const flow=e=>['data','alias','interface-binding'].includes(e.kind);
    const protectedNode=n=>!n||n.kind==='opaque'||n.mutable||n.identity_display||n.observed_calls||n.runtime_evidence?.length||
      n.evidence_status==='runtime-only'||['state','buffer','parameter'].includes(n.kind)||n.repeat_contract||n.iteration||n.semantic_contracts?.length||n.contract_roles;
    for(const group of nodes){
      if(!group.presentation_only||group.semantic_type!=='conditional-collection'||!group.boundary_selection)continue;
      const members=closure(group.id).filter(id=>raw.has(id)),inside=new Set(members),selection=group.boundary_selection;
      if(members.length!==group.canonical_members?.length||group.canonical_members.some(id=>!inside.has(id))||members.some(id=>protectedNode(raw.get(id))||protectedNode(by.get(id))))continue;
      const controls=members.filter(id=>raw.get(id).kind==='control');
      if(controls.length!==1||raw.get(controls[0]).operator!=='if')continue;
      const control=raw.get(controls[0]),sourceScope=control.parent;
      const exits=ir.edges.filter(e=>inside.has(e.source)&&!inside.has(e.target));
      const targets=new Set(exits.map(e=>e.target));if(targets.size!==1)continue;
      const aggregate=by.get(exits[0].target),original=raw.get(aggregate?.id),incoming=ins.get(aggregate?.id)||[],outgoing=uses.get(aggregate?.id)||[];
      // This is a local output boundary with real downstream use. Top-level
      // external output terminals remain physically exposed in their own right.
      if(!original||original.kind!=='interface'||original.role!=='output'||aggregate.kind!=='interface'||aggregate.role!=='output'||aggregate.parent!==group.parent||original.parent!==sourceScope||
        aggregate.condition||original.condition||protectedNode(aggregate)||protectedNode(original)||!outgoing.length||incoming.length<2||incoming.length>8||
        incoming.some(e=>e.kind!=='interface-binding'||e.condition)||new Set(incoming.map(e=>e.target_port??'in')).size!==incoming.length)continue;
      const sites=incoming.map(e=>by.get(e.source));
      if(new Set(sites.map(n=>n?.id)).size!==sites.length||sites.some(n=>!n||n.kind!=='interface'||n.role!=='output'||n.condition||
        protectedNode(n)||protectedNode(raw.get(n.id))||raw.get(n.id).kind!=='interface'||raw.get(n.id).role!=='output'||raw.get(n.id).condition||claimed.has(n.id)||
        !inside.has(n.id)&&(n.parent!==group.parent||raw.get(n.id).parent!==sourceScope)||
        (uses.get(n.id)||[]).length!==1||(ins.get(n.id)||[]).length!==1||
        (ins.get(n.id)||[]).some(e=>!flow(e)||e.condition)))continue;
      // Every old outgoing edge must be one of these concrete return bindings;
      // arbitrary escaping values, effects and other conditional scopes veto.
      if(exits.some(e=>!incoming.includes(e))||claimed.has(aggregate.id))continue;
      const extra=sites.filter(n=>!inside.has(n.id)).map(n=>n.id),canonical=[...members,...extra,aggregate.id],all=new Set(canonical);
      const incident=ir.edges.filter(e=>all.has(e.source)||all.has(e.target));
      if(incident.some(e=>!flow(e)&&e.kind!=='control'||e.iteration||e.condition&&(!all.has(e.condition.branch))))continue;
      const cuts=incident.filter(e=>all.has(e.source)!==all.has(e.target));
      const paths=id=>{const result=[];let at=raw.get(id)?.parent;while(at&&at!==sourceScope){const n=raw.get(at);if(n?.condition)result.push(copy(n.condition));at=n?.parent;}return result;};
      const row={rule_version:'return-regions/1',group:group.id,control:control.id,predicate:control.label||'if',aggregate:aggregate.id,
        added_members:[...extra,aggregate.id],canonical_members:canonical,return_sites:incoming.map(e=>({node:e.source,edge:e.id,source_port:e.source_port??'out',
          aggregate_slot:e.target_port??'in',source_conditions:paths(e.source)})),cuts:cuts.map(copy),
        scope:'Source return sites and their common local output interface; source ancestry conditions only, no fallthrough negation, value equality or selected execution inferred.'};
      const next={...selection,members:[...selection.members,...extra,aggregate.id],canonical_members:canonical,boundary_edges:cuts.map(e=>e.id),
        input_edges:cuts.filter(e=>all.has(e.target)).map(e=>e.id),output_edges:cuts.filter(e=>all.has(e.source)).map(e=>e.id),
        escaping_results:[...new Set(cuts.filter(e=>all.has(e.source)).map(e=>JSON.stringify([e.source,e.source_port])))].map(s=>JSON.parse(s)),
        internal_edges:incident.length-cuts.length,cut_edges:cuts.length,return_boundary:{aggregate:aggregate.id,sites:row.return_sites}};
      next.cohesion=next.internal_edges/Math.max(1,incident.length);
      group.boundary_selection=next;group.canonical_members=canonical;group.boundary_ports=cuts.map(copy);group.return_region=row;
      group.label='Return alternatives';group.region_summary='If '+row.predicate+' · '+sites.length+' source returns';
      for(const id of row.added_members){by.get(id).parent=group.id;claimed.add(id);}
      changes.set(group.id,next);rows.push(row);
    }
    const publication=plan.publication?{...plan.publication,boundary_plans:plan.publication.boundary_plans?.map(p=>({...p,proposals:p.proposals.map(c=>changes.get(c.id)||c)}))}:plan.publication;
    const findings=plan.findings?.map(f=>changes.has(f.id)?{...f,label:by.get(f.id).label,members:changes.get(f.id).members.slice(),
      roles:{...f.roles,units:changes.get(f.id).members.slice(),boundary_selection:changes.get(f.id)},
      proof:[...f.proof,'The concrete return sites share this local output interface; original branches, return slots and cuts remain expandable.']}:f);
    return {plan:{...plan,nodes,publication,findings},rows};
  }
  function normalReturns({ir,plan,open=new Set(),inputs=new Map(),requested=[]}){
    const nodes=plan.nodes.map(n=>({...n})),by=new Map(nodes.map(n=>[n.id,n])),raw=new Map(ir.nodes.map(n=>[n.id,n]));
    const ins=new Map(),uses=new Map(),rows=[],attachments=new Map();
    for(const e of ir.edges){if(!ins.has(e.target))ins.set(e.target,[]);ins.get(e.target).push(e);if(!uses.has(e.source))uses.set(e.source,[]);uses.get(e.source).push(e);}
    const flow=e=>['data','alias','interface-binding'].includes(e.kind);
    const guard=n=>!n||n.mutable||n.identity_display||n.observed_calls||n.runtime_evidence?.length||n.evidence_status==='runtime-only'||
      ['opaque','state','buffer','parameter'].includes(n.kind)||n.repeat_contract||n.iteration;
    for(const group of nodes){
      const region=group.return_region;if(!region||open.has(group.id)||region.return_sites.length!==2)continue;
      const members=new Set(region.canonical_members),control=raw.get(region.control),aggregate=raw.get(region.aggregate),selection=aggregate?.return_selection;
      if(!selection||!selection.scope||region.canonical_members.some(id=>guard(raw.get(id))||guard(by.get(id)))||
        ir.nodes.some(n=>n.parent===control?.parent&&n.kind==='opaque'&&['unsupported-statement','unsupported-expression'].includes(n.reason))||
        requested.some(id=>id===group.id||members.has(id)||id===control?.parent))continue;
      const predicateEdges=ins.get(control?.id)||[],predicate=predicateEdges.length===1?predicateEdges[0]:null,input=raw.get(predicate?.source),fixed=inputs.get(input?.id);
      if(!input||!fixed||typeof fixed.value!=='boolean'||input.role!=='input'||input.kind!=='interface'||guard(input)||guard(by.get(input.id))||
        input.parent!==control.parent||aggregate.parent!==control.parent||input.condition||predicate.kind!=='control'||predicate.condition||predicate.iteration||
        (ins.get(input.id)||[]).length||typeof input.slot!=='string'||selection.call_constants?.[input.slot]!==fixed.value||
        input.source_constant_input?.value!==fixed.value||!control.source?.some(s=>s.expression===input.slot))continue;
      const selected=region.return_sites.find(s=>s.node===selection.selected);if(!selected)continue;
      const branches=(uses.get(control.id)||[]);
      if(branches.length!==2||branches.some(e=>e.kind!=='control'||e.condition||e.iteration||!members.has(e.target)||
        raw.get(e.target)?.condition?.branch!==control.id||raw.get(e.target)?.condition?.outcome!==e.target_port)||
        new Set(branches.map(e=>e.target_port)).size!==2||!branches.every(e=>['true','false'].includes(e.target_port)))continue;
      const ancestry=id=>{const out=[];let at=raw.get(id)?.parent;while(at&&at!==control.parent){const n=raw.get(at);if(!n)return null;if(n.condition)out.push(copy(n.condition));at=n.parent;}return at===control.parent?out:null;};
      if(region.return_sites.some(s=>JSON.stringify(ancestry(s.node))!==JSON.stringify(s.source_conditions)))continue;
      const outcome=fixed.value?'true':'false',other=region.return_sites.find(s=>s!==selected);
      if(selected.source_conditions.length){
        if(selected.source_conditions.length!==1||selected.source_conditions[0].branch!==control.id||selected.source_conditions[0].outcome!==outcome)continue;
      }else{
        // A fallthrough is not a canonical false branch. Only this invocation's
        // recorded normal-return selection can choose it, with an empty false
        // body and a terminating true source return as independent witnesses.
        const empty=branches.find(e=>e.target_port==='false');
        if(fixed.value||other.source_conditions.length!==1||other.source_conditions[0].branch!==control.id||other.source_conditions[0].outcome!=='true'||
          ir.nodes.some(n=>n.parent===empty.target))continue;
      }
      const needed=new Set(),witness=new Set(),visiting=new Set(),visited=new Set();let valid=true;
      const walk=id=>{
        if(visiting.has(id)){valid=false;return;}if(visited.has(id))return;visiting.add(id);
        const incoming=ins.get(id)||[];
        if(!incoming.length||incoming.some(e=>!flow(e)||e.condition||e.iteration)){valid=false;visiting.delete(id);return;}
        for(const e of incoming){
          witness.add(e.id);
          if(members.has(e.source)){if(e.source===aggregate.id||e.source===control.id)valid=false;else walk(e.source);}
          else if(guard(raw.get(e.source))||guard(by.get(e.source)))valid=false;else needed.add(e.id);
        }
        visiting.delete(id);visited.add(id);
      };
      walk(selected.node);if(!valid||!needed.size)continue;
      const cuts=ir.edges.filter(e=>members.has(e.source)!==members.has(e.target));
      if(JSON.stringify(cuts)!==JSON.stringify(region.cuts))continue;
      const incoming=cuts.filter(e=>members.has(e.target));
      if(incoming.some(e=>e.id!==predicate.id&&(!flow(e)||e.condition||e.iteration)))continue;
      const alternatives=incoming.filter(e=>e.id!==predicate.id&&!needed.has(e.id));if(!alternatives.length)continue;
      const binding=ir.edges.find(e=>e.id===selected.edge);
      if(!binding||binding.source!==selected.node||binding.target!==aggregate.id||binding.kind!=='interface-binding'||binding.condition||binding.iteration||
        (binding.source_port??'out')!==selected.source_port||(binding.target_port??'in')!==selected.aggregate_slot)continue;
      const row={rule_version:'normal-returns/1',group:group.id,aggregate:aggregate.id,selected_return:copy(selected),
        predicate:{node:input.id,slot:input.slot,value:fixed.value,edge:copy(predicate)},selection:copy(selection),
        branch_witnesses:branches.map(copy),dependency_witnesses:ir.edges.filter(e=>witness.has(e.id)).map(copy),binding:copy(binding),
        selected_inputs:incoming.filter(e=>needed.has(e.id)).map(copy),alternative_inputs:alternatives.map(copy),
        scope:'Normal return of this statically bound source invocation only; all other source paths and exact bindings remain expandable. No runtime execution, coverage or value equivalence assertion.'};
      group.normal_return=row;rows.push(row);
      for(const edge of alternatives)attachments.set(edge.id,{owner:group.id,edge:copy(edge),annotation_kind:'source-return-alternative',proof:row.rule_version});
    }
    return {plan:{...plan,nodes},rows,attachments};
  }
  const api={VERSION,candidates,predicates,returns,normalReturns};root.SemanticPresentationRegions=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
