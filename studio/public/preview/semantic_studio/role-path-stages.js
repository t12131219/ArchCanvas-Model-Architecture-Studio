/* Compose two already proved expressions without erasing either source path.
 * Opening a stage restores the role and helper; the helper opens separately. */
(function(root){
  'use strict';
  const VERSION='role-path-stages/2',copy=x=>JSON.parse(JSON.stringify(x));
  const flow=e=>['data','alias','interface-binding'].includes(e.kind);
  function compile({ir,plan,open=new Set(),requested=[],owners=null}){
    const nodes=plan.nodes.map(n=>({...n})),by=new Map(nodes.map(n=>[n.id,n])),canonical=new Map(ir.nodes.map(n=>[n.id,n]));
    const children=new Map(),incoming=new Map(),outgoing=new Map(),rows=[],claimed=new Set(),wanted=new Set(requested);
    for(const n of nodes){if(!children.has(n.parent))children.set(n.parent,[]);children.get(n.parent).push(n.id);}
    for(const e of ir.edges){if(!incoming.has(e.target))incoming.set(e.target,[]);incoming.get(e.target).push(e);if(!outgoing.has(e.source))outgoing.set(e.source,[]);outgoing.get(e.source).push(e);}
    const closure=id=>{const todo=[id];for(let i=0;i<todo.length;i++)todo.push(...children.get(todo[i])||[]);return todo;};
    const guarded=n=>!n||['opaque','control'].includes(n.kind)||n.mutable||n.condition||n.identity_display||n.observed_calls||n.runtime_evidence?.length||n.evidence_status!=='static-only'||
      n.semantic_contracts?.length||n.contract_roles||n.repeat_contract||n.iteration||n.contract_stage||n.role_operation_stage||n.role_path_stage;
    const resource=e=>e.kind==='parameter-read'&&canonical.get(e.source)?.kind==='parameter';
    const protectedEdge=e=>e.condition||e.iteration||e.design_route||!flow(e)&&!resource(e);
    const goals=(root.SemanticSummaryGoals||(typeof require==='function'?require('./summary-goals.js'):null)).build(ir,plan);
    const certifiedPaths=new Set(goals.goals.filter(g=>!g.proof_errors.length).map(g=>g.node));
    const operation=id=>{const n=canonical.get(id);return {node:id,label:n.framework_type?.split('.').at(-1)||
      (n.source_framework_function===n.function_target?n.function_target?.split('.').at(-1):null)||n.operator,
      operator:n.operator,framework_type:n.framework_type??null,configuration:copy(Object.hasOwn(n,'constructor')?n.constructor:null)};};
    for(const anchor of nodes.slice()){
      const roles=anchor.role_annotations||[],uses=outgoing.get(anchor.id)||[];
      if(Array.isArray(owners)&&!roles.every(r=>owners.includes(r.owner)))continue;
      if(anchor.kind!=='compute'||!roles.length||guarded(anchor)||guarded(canonical.get(anchor.id))||wanted.has(anchor.id)||claimed.has(anchor.id)||!open.has(anchor.parent)||uses.length!==1)continue;
      const edge=uses[0],input=by.get(edge.target),helper=by.get(input?.parent),p=helper?.local_pipeline;
      if(!p||p.form!=='dependency-path-summary'||p.operations.length>6||!certifiedPaths.has(helper.id)||guarded(helper)||
        input.kind!=='interface'||input.role!=='input'||helper.parent!==anchor.parent||canonical.get(helper.id)?.parent!==canonical.get(anchor.id)?.parent||
        open.has(helper.id)&&!open.has('paper:role-path-stage:'+anchor.id)||!flow(edge)||(edge.source_port??'out')!=='out')continue;
      const display=closure(helper.id),members=[anchor.id,...display.filter(id=>canonical.has(id))],inside=new Set(members),helperSet=new Set(p.canonical_members);
      if(display.some(id=>guarded(by.get(id))||wanted.has(id)||claimed.has(id)||by.get(id).role_annotations?.length)||
        display.filter(id=>canonical.has(id)).length!==helperSet.size||display.some(id=>canonical.has(id)&&!helperSet.has(id)))continue;
      const compute=new Set(p.operations.map(o=>o.node));
      if(ir.edges.some(e=>compute.has(e.source)&&flow(e)&&(e.source_port??'out')!=='out'))continue;
      const certs=roles.map(r=>(plan.semantic_contracts||[]).find(c=>c.id===r.certificate&&c.node===r.owner));
      if(certs.some((c,i)=>!c||!(ir.semantic_contracts||[]).some(source=>JSON.stringify(source)===JSON.stringify(c))||!members.every(id=>c.members?.includes(id))||roles[i].node!==anchor.id||roles[i].frontier_node!==anchor.id||roles[i].location!=='internal'||
        (roles[i].role_keys||[]).reduce((v,k)=>v&&typeof v==='object'?v[k]:undefined,c.roles)!==anchor.id))continue;
      const incident=ir.edges.filter(e=>inside.has(e.source)||inside.has(e.target)),cuts=incident.filter(e=>inside.has(e.source)!==inside.has(e.target));
      const helperCuts=ir.edges.filter(e=>helperSet.has(e.source)!==helperSet.has(e.target));
      // The anchor has no other use, and the helper has no other external
      // dependency. Shape/configuration/resource reads inside remain distinct.
      if(incident.some(protectedEdge)||helperCuts.filter(e=>helperSet.has(e.target)).length!==1||
        helperCuts.find(e=>helperSet.has(e.target))!==edge||!helperCuts.some(e=>helperSet.has(e.source))||
        cuts.some(e=>inside.has(e.target)&&e.target!==anchor.id||inside.has(e.source)&&!helperSet.has(e.source)))continue;
      let at=by.get(anchor.parent),blocked=false;
      while(at){if(at.kind==='control'||at.mutable||at.condition||at.identity_display||at.observed_calls||at.runtime_evidence?.length||at.evidence_status==='runtime-only'){blocked=true;break;}at=by.get(at.parent);}
      if(blocked)continue;
      let id='paper:role-path-stage:'+anchor.id;while(by.has(id))id+=':1';
      const operations=[operation(anchor.id),...p.operations.map(o=>operation(o.node))];
      const row={rule_version:VERSION,node:id,anchor:anchor.id,helper:helper.id,display_members:[anchor.id,helper.id],roles:copy(roles),
        role_title:anchor.paper.title,operations,canonical_members:members,internal_edges:incident.filter(e=>inside.has(e.source)&&inside.has(e.target)).map(e=>e.id),
        cuts:copy(cuts),helper_path:copy(p),
        scope:'Certified role and one exclusive proved source dependency path. Two-step expansion preserves helper ownership, all operands, reads and cuts. No fusion, purity, equivalence or family assertion.'};
      const stage={id,parent:anchor.parent,kind:'composite',semantic_type:'role-path-stage',label:anchor.label,presentation_only:true,source_parent:null,
        source:members.flatMap(id=>canonical.get(id).source||[]),runtime_evidence:[],evidence_status:'static-only',canonical_members:members.slice(),boundary_ports:copy(cuts),role_path_stage:row};
      nodes.push(stage);by.set(id,stage);by.get(anchor.id).parent=id;by.get(helper.id).parent=id;members.forEach(id=>claimed.add(id));rows.push(row);
    }
    // Prefer the established role -> helper composition above. A remaining
    // certified role may instead consume one exclusive proved helper path.
    // Only ordinary, unused-elsewhere aliases may bridge the source scopes;
    // the aliases are retained as members, never interpreted as computations.
    for(const anchor of nodes.slice()){
      const roles=anchor.role_annotations||[],inputs=(incoming.get(anchor.id)||[]).filter(e=>!resource(e));
      if(Array.isArray(owners)&&!roles.every(r=>owners.includes(r.owner)))continue;
      if(anchor.kind!=='compute'||!roles.length||guarded(anchor)||guarded(canonical.get(anchor.id))||wanted.has(anchor.id)||claimed.has(anchor.id)||!open.has(anchor.parent)||inputs.length!==1)continue;
      const bridge=[],seen=new Set();let edge=inputs[0],input=by.get(edge.source),blocked=false;
      while(input?.kind==='value-alias'){
        const source=canonical.get(input.id),ins=incoming.get(input.id)||[],outs=outgoing.get(input.id)||[];
        if(seen.has(input.id)||guarded(input)||guarded(source)||input.operator||source.operator||input.slot!=null||source.slot!=null||
          input.parent!==anchor.parent||source.parent!==canonical.get(anchor.id).parent||input.role_annotations?.length||
          wanted.has(input.id)||claimed.has(input.id)||ins.length!==1||outs.length!==1||outs[0]!==edge||
          protectedEdge(edge)||(edge.source_port??'out')!=='out'){blocked=true;break;}
        seen.add(input.id);bridge.unshift(input.id);edge=ins[0];input=by.get(edge.source);
      }
      const helper=by.get(input?.parent),p=helper?.local_pipeline;
      if(blocked||!p||p.form!=='dependency-path-summary'||p.operations.length>6||!certifiedPaths.has(helper.id)||guarded(helper)||
        input.kind!=='interface'||input.role!=='output'||helper.parent!==anchor.parent||canonical.get(helper.id)?.parent!==canonical.get(anchor.id).parent||
        open.has(helper.id)&&!open.has('paper:role-path-stage:'+anchor.id)||!flow(edge)||(edge.source_port??'out')!=='out')continue;
      const display=closure(helper.id),members=[...display.filter(id=>canonical.has(id)),...bridge,anchor.id],inside=new Set(members),helperSet=new Set(p.canonical_members);
      if(display.some(id=>guarded(by.get(id))||canonical.has(id)&&guarded(canonical.get(id))||wanted.has(id)||claimed.has(id)||by.get(id).role_annotations?.length)||
        display.filter(id=>canonical.has(id)).length!==helperSet.size||display.some(id=>canonical.has(id)&&!helperSet.has(id)))continue;
      const compute=new Set([anchor.id,...p.operations.map(o=>o.node)]);
      if(ir.edges.some(e=>compute.has(e.source)&&flow(e)&&(e.source_port??'out')!=='out'))continue;
      const certs=roles.map(r=>(plan.semantic_contracts||[]).find(c=>c.id===r.certificate&&c.node===r.owner));
      if(certs.some((c,i)=>!c||!(ir.semantic_contracts||[]).some(source=>JSON.stringify(source)===JSON.stringify(c))||!members.every(id=>c.members?.includes(id))||roles[i].node!==anchor.id||roles[i].frontier_node!==anchor.id||roles[i].location!=='internal'||
        (roles[i].role_keys||[]).reduce((v,k)=>v&&typeof v==='object'?v[k]:undefined,c.roles)!==anchor.id))continue;
      const incident=ir.edges.filter(e=>inside.has(e.source)||inside.has(e.target)),cuts=incident.filter(e=>inside.has(e.source)!==inside.has(e.target));
      const helperCuts=ir.edges.filter(e=>helperSet.has(e.source)!==helperSet.has(e.target)),outputs=helperCuts.filter(e=>helperSet.has(e.source));
      // A helper already adjacent to a role on its input belongs to the
      // established suffix candidate, even when that candidate is rejected.
      // Do not turn failed evidence or a shared role result into a prefix
      // fallback at the opposite end of the same helper.
      if(helperCuts.some(e=>helperSet.has(e.target)&&by.get(e.source)?.role_annotations?.length))continue;
      if(incident.some(protectedEdge)||outputs.length!==1||outputs[0]!==edge||!helperCuts.some(e=>helperSet.has(e.target))||
        cuts.some(e=>inside.has(e.target)&&!helperSet.has(e.target)&&!(e.target===anchor.id&&resource(e))||inside.has(e.source)&&e.source!==anchor.id))continue;
      let at=by.get(anchor.parent);
      while(at){if(at.kind==='control'||at.mutable||at.condition||at.identity_display||at.observed_calls||at.runtime_evidence?.length||at.evidence_status==='runtime-only'){blocked=true;break;}at=by.get(at.parent);}
      if(blocked)continue;
      let id='paper:role-path-stage:'+anchor.id;while(by.has(id))id+=':1';
      const operations=[...p.operations.map(o=>operation(o.node)),operation(anchor.id)];
      const row={rule_version:VERSION,node:id,direction:'helper-before-role',anchor:anchor.id,helper:helper.id,bridge_aliases:bridge,
        display_members:[helper.id,anchor.id],roles:copy(roles),role_title:anchor.paper.title,operations,canonical_members:members,
        internal_edges:incident.filter(e=>inside.has(e.source)&&inside.has(e.target)).map(e=>e.id),cuts:copy(cuts),helper_path:copy(p),
        scope:'One exclusive proved source dependency path before a certified role, through ordinary single-use aliases only. Two-step expansion preserves helper ownership, all operands, reads and cuts. No fusion, purity, equivalence or family assertion.'};
      const stage={id,parent:anchor.parent,kind:'composite',semantic_type:'role-path-stage',label:anchor.label,presentation_only:true,source_parent:null,
        source:members.flatMap(id=>canonical.get(id).source||[]),runtime_evidence:[],evidence_status:'static-only',canonical_members:members.slice(),boundary_ports:copy(cuts),role_path_stage:row};
      nodes.push(stage);by.set(id,stage);[helper.id,...bridge,anchor.id].forEach(id=>by.get(id).parent=stage.id);members.forEach(id=>claimed.add(id));rows.push(row);
    }
    return {plan:{...plan,nodes},rows};
  }
  function receipt(stages,graph){return {rule_version:VERSION,rows:stages.rows.filter(r=>graph.positions.has(r.node)).map(r=>({...r,
    status:graph.positions.get(r.node).expanded?'expanded':'summary',stage_children_exposed:r.display_members.every(id=>graph.positions.has(id)),
    detailed_operations_exposed:r.operations.every(o=>graph.positions.has(o.node))}))};}
  const api={VERSION,compile,receipt};root.SemanticRolePathStages=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
