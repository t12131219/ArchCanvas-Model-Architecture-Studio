/* Presentation only: keep a certified role and its exclusive ordinary tail in
 * one expandable stage. No operation is erased or made equivalent to its input. */
(function(root){
  'use strict';
  const VERSION='role-operation-stages/1',copy=x=>JSON.parse(JSON.stringify(x));
  const flow=e=>['data','alias','interface-binding'].includes(e.kind);
  function compile({ir,plan,open=new Set(),requested=[]}){
    const nodes=plan.nodes.map(n=>({...n})),by=new Map(nodes.map(n=>[n.id,n])),canonical=new Map(ir.nodes.map(n=>[n.id,n]));
    const incoming=new Map(),outgoing=new Map(),rows=[],claimed=new Set();
    for(const e of ir.edges){if(!incoming.has(e.target))incoming.set(e.target,[]);incoming.get(e.target).push(e);if(!outgoing.has(e.source))outgoing.set(e.source,[]);outgoing.get(e.source).push(e);}
    const guarded=n=>!n||n.kind!=='compute'||n.evidence_status!=='static-only'||n.mutable||n.condition||n.identity_display||n.observed_calls||n.runtime_evidence?.length||
      n.semantic_contracts?.length||n.contract_roles||n.repeat_contract||n.iteration||n.contract_stage||n.role_operation_stage;
    const resource=e=>e.kind==='parameter-read'&&['parameter'].includes(canonical.get(e.source)?.kind);
    const protectedIncident=id=>[...(incoming.get(id)||[]),...(outgoing.get(id)||[])].some(e=>e.condition||e.iteration||e.design_route||!flow(e)&&!resource(e));
    const label=n=>n.framework_type?.split('.').at(-1)||(n.source_framework_function===n.function_target?n.function_target?.split('.').at(-1):null)||n.operator;
    const requestedTargets=new Set(requested);
    for(const anchor of nodes){
      const roles=anchor.role_annotations||[];
      if(!roles.length||guarded(anchor)||protectedIncident(anchor.id)||claimed.has(anchor.id)||requestedTargets.has(anchor.id)||!open.has(anchor.parent))continue;
      // Exact attached certificate membership is required; a free label is not
      // sufficient authority to form a role stage.
      const certs=roles.map(r=>(plan.semantic_contracts||[]).find(c=>c.id===r.certificate&&c.node===r.owner&&c.members?.includes(anchor.id)));
      if(certs.some((c,i)=>!c||(roles[i].role_keys||[]).reduce((v,k)=>v&&typeof v==='object'?v[k]:undefined,c.roles)!==anchor.id)||roles.some(r=>r.node!==anchor.id||r.frontier_node!==anchor.id||r.location!=='internal'))continue;
      const members=[anchor.id],internal=[],tail=[];let at=anchor.id;
      while(tail.length<3){
        const uses=outgoing.get(at)||[];
        if(uses.length!==1)break;
        const edge=uses[0],next=by.get(edge.target),ins=incoming.get(edge.target)||[],values=ins.filter(flow);
        if(!flow(edge)||edge.condition||(edge.source_port??'out')!=='out'||guarded(next)||protectedIncident(next.id)||
          next.parent!==anchor.parent||canonical.get(next.id)?.parent!==canonical.get(anchor.id)?.parent||
          next.role_annotations?.length||claimed.has(next.id)||requestedTargets.has(next.id)||members.includes(next.id)||
          values.length!==1||values[0]!==edge||ins.some(e=>e!==edge&&!resource(e))||
          !label(next)||!certs.every(c=>c.members.includes(next.id)))break;
        tail.push(next.id);members.push(next.id);internal.push(edge.id);at=next.id;
      }
      if(!tail.length)continue;
      // A role's tail remains in the same certified local scope. Stateful,
      // observed and conditional enclosing boundaries are never crossed.
      let parent=by.get(anchor.parent),blocked=false;
      while(parent){if(parent.kind==='control'||parent.mutable||parent.condition||parent.identity_display||parent.observed_calls||parent.runtime_evidence?.length||parent.evidence_status==='runtime-only'){blocked=true;break;}parent=by.get(parent.parent);}
      if(blocked)continue;
      const inside=new Set(members),incident=ir.edges.filter(e=>inside.has(e.source)||inside.has(e.target)),cuts=incident.filter(e=>inside.has(e.source)!==inside.has(e.target));
      if(cuts.some(e=>inside.has(e.source)&&e.source!==at))continue;
      let id='paper:role-operation-stage:'+anchor.id;while(by.has(id))id+=':1';
      const operations=members.map(id=>{const n=by.get(id);return {node:id,label:label(n),operator:n.operator,framework_type:n.framework_type??null,configuration:copy(Object.hasOwn(n,'constructor')?n.constructor:null)};});
      const row={rule_version:VERSION,node:id,anchor:anchor.id,tail,operations,roles:copy(roles),canonical_members:members.slice(),internal_edges:internal,cuts:copy(cuts),
        scope:'One certified role plus at most three exclusive unary operations in its original scope. Ordered dependency labels only; no purity, fusion, input/output equality, shared-parameter or family assertion.'};
      const stage={id,parent:anchor.parent,kind:'composite',semantic_type:'role-operation-stage',label:anchor.label,presentation_only:true,source_parent:null,
        source:members.flatMap(id=>canonical.get(id).source||[]),runtime_evidence:[],evidence_status:'static-only',canonical_members:members.slice(),boundary_ports:copy(cuts),role_operation_stage:row};
      nodes.push(stage);by.set(id,stage);for(const id of members){by.get(id).parent=stage.id;claimed.add(id);}rows.push(row);
    }
    return {plan:{...plan,nodes},rows};
  }
  function receipt(stages,graph){return {rule_version:VERSION,rows:stages.rows.filter(r=>graph.positions.has(r.node)).map(r=>({...r,status:graph.positions.get(r.node).expanded?'expanded':'summary',
    detailed_operations_exposed:r.canonical_members.every(id=>graph.positions.has(id))}))};}
  const api={VERSION,compile,receipt};root.SemanticRoleOperationStages=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
