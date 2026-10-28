/* Bounded, evidence-driven local detail selection. Names and model families
 * are deliberately absent: candidates are existing roles or relation paths. */
(function(root){
  'use strict';
  const VERSION='adaptive-frontier/5';
  const Roles=root.SemanticRoleFrontier||(typeof require==='function'?require('./role-frontier.js'):null);
  const Expressions=root.SemanticLocalExpressions||(typeof require==='function'?require('./local-expressions.js'):null);
  const Goals=root.SemanticExpressionGoals||(typeof require==='function'?require('./expression-goals.js'):null);
  const critical=new Set(['unknown-boundary','state-interface','selection','conditional-join','conditional-region','iteration-binding','iteration-template','same-object-calls','observed-parameter-aliases']);
  function candidates(graph,state={}){
    const plan=graph.architecture,by=new Map(plan.nodes.map(n=>[n.id,n])),owners=new Set(graph.publication.role_frontier?.modules.map(m=>m.node)||[]);
    const selectedRoles=new Set(Array.isArray(state.paperRoleDetails)?state.paperRoleDetails:[]),selectedExpressions=new Set(Array.isArray(state.paperExpressionDetails)?state.paperExpressionDetails:[]),out=[];
    const refs=value=>typeof value==='string'&&by.has(value)?[value]:value&&typeof value==='object'?Object.values(value).flatMap(refs):[];
    // Compare a complete role layer with exact local paths. Partial requests
    // keep the remaining independent roles available on later iterations.
    // The role compiler remains responsible for checking intervening guards.
    for(const c of plan.semantic_contracts||[]){
      const p=graph.positions.get(c.node);
      const paths=Array.isArray(state.paperRolePaths)?state.paperRolePaths:[],partial=paths.some(r=>r.node===c.node);
      if(!p||selectedRoles.has(c.node)||!partial&&(p.expanded||owners.has(c.node)))continue;
      const targets=[...new Set(refs(c.roles))];
      if(targets.some(id=>id!==c.node&&!graph.positions.has(id))&&!out.some(r=>r.kind==='roles'&&r.node===c.node))out.push({id:'roles:'+c.node,kind:'roles',node:c.node,priority:2,targets,scope:c.scope});
      if(state.paperAdaptivePolicy!=='structure')continue;
      const seenTargets=new Set();
      for(const ref of Roles.references(c.roles,by)){
        if(ref.node===c.node||graph.positions.has(ref.node)||seenTargets.has(ref.node))continue;
        let at=by.get(ref.node)?.parent;while(at&&at!==c.node)at=by.get(at)?.parent;
        if(at!==c.node||paths.some(r=>r.node===c.node&&r.certificate===c.id&&JSON.stringify(r.role)===JSON.stringify(ref.keys)))continue;
        seenTargets.add(ref.node);
        out.push({id:'role-path:'+JSON.stringify([c.node,c.id,ref.keys]),kind:'role-path',node:c.node,certificate:c.id,role:ref.keys,
          priority:2,targets:[ref.node],scope:c.scope});
      }
    }
    const relations=(plan.relation_graph?.relations||[]).filter(r=>!selectedExpressions.has(r.id)&&
      (graph.positions.has(r.node)||graph.positions.has(graph.representatives[r.node])));
    const frontier=Expressions.compile({plan,focus:graph.publication.focus,details:relations.map(r=>r.id)}),dedup=new Set();
    for(const r of frontier.requests.filter(r=>r.requested).sort((a,b)=>Number(critical.has(b.type))-Number(critical.has(a.type))||a.relation.localeCompare(b.relation))){
      const internal=r.targets.filter(t=>t.location==='internal');
      // Unknown/control leaves can be shown as boundaries. Their interiors,
      // unselected certificates and repeat/observation scopes cannot be crossed.
      if(!internal.length||internal.some(t=>t.stop&&t.frontier_node!==t.node))continue;
      const hidden=internal.filter(t=>!graph.positions.has(t.node));
      if(!hidden.length)continue;
      const path=new Set();
      for(const t of hidden){let at=by.get(t.node)?.parent;while(at&&!graph.positions.get(at)?.expanded){path.add(at);at=by.get(at)?.parent;}}
      const signature=JSON.stringify([...path].sort());
      if(!path.size||dedup.has(signature))continue;dedup.add(signature);
      out.push({id:'relation:'+r.relation,kind:'relation',relation:r.relation,type:r.type,priority:critical.has(r.type)?3:2,
        targets:internal.map(t=>t.node),required_open:[...path],scope:r.evidence_scope});
    }
    return out.sort((a,b)=>b.priority-a.priority||Number(a.kind==='role-path')-Number(b.kind==='role-path')||a.targets.length-b.targets.length||a.id.localeCompare(b.id));
  }
  function apply(state,candidate){
    if(candidate.kind==='role-path')return {...state,paperRolePaths:[...(Array.isArray(state.paperRolePaths)?state.paperRolePaths:[]),
      {node:candidate.node,certificate:candidate.certificate,role:candidate.role.slice()}]};
    const key=candidate.kind==='roles'?'paperRoleDetails':'paperExpressionDetails',id=candidate.kind==='roles'?candidate.node:candidate.relation;
    return {...state,[key]:[...new Set([...(Array.isArray(state[key])?state[key]:[]),id])]};
  }
  function metrics(result){
    const g=result.graph,q=result.prepared.quality;
    return {nodes:g.nodes.length,edges:g.edges.length,width:q.native_width_px,height:q.native_height_px,area:q.native_width_px*q.native_height_px,
      crossings:q.line_geometry.crossings,contacts:q.line_geometry.unrelated_contacts.length,
      overlaps:q.line_geometry.overlapping_paths.filter(p=>!p.same_value).length,route_failures:q.route_failures.length,
      unplaced_labels:q.unplaced_port_labels.length,font:q.min_canvas_font_px,issues:q.issues};
  }
  function evidence(ir,result){
    const g=result.graph,coverage=new Map(Goals.evaluate(g.expression_goals,g,result.prepared,ir).map(r=>[r.goal,r])),
      proof=Goals.canonicalPaths(ir,result.prepared.routes),goals=new Map(),by=new Map(ir.nodes.map(n=>[n.id,n]));
    for(const goal of g.expression_goals.goals)if(coverage.get(goal.id)?.status==='fulfilled')
      goals.set(goal.id,{id:goal.id,kind:goal.kind,priority:goal.priority,node:goal.focus_node});
    const roles=new Set((g.publication.role_frontier?.roles||[]).filter(r=>r.status==='exposed').map(r=>JSON.stringify([r.certificate,r.role_keys,r.node])));
    const boundaries=new Set(g.nodes.filter(n=>by.has(n.id)&&(n.kind==='opaque'||n.kind==='control'||n.condition||n.mutable||n.identity_display||n.evidence_status==='runtime-only')).map(n=>n.id));
    const conflicts=new Set((g.constraint_receipts||[]).filter(r=>r.status==='conflict').map(r=>r.id));
    const summaries=new Set((g.summary_coverage||[]).filter(r=>r.status==='fulfilled').map(r=>r.goal));
    const paths=new Map((g.publication.role_frontier?.path_requests||[]).filter(r=>r.selection==='selected').map(r=>{
      const incoming=ir.edges.filter(e=>e.target===r.target&&['data','alias','interface-binding'].includes(e.kind));
      return [JSON.stringify([r.node,r.certificate,r.role]),r.status==='exposed'&&g.positions.has(r.target)&&incoming.length>0&&incoming.every(e=>proof.exact(e.id))];
    }));
    return {goals,roles,boundaries,conflicts,summaries,paths};
  }
  function contribution(baseline,gained,roles,summaries){
    const fulfilled=new Set((baseline.graph.summary_coverage||[]).filter(c=>c.status==='fulfilled').map(c=>c.goal));
    const structures=(baseline.graph.summary_goals?.goals||[]).filter(g=>fulfilled.has(g.id)).map(g=>({
      nodes:new Set(g.operations.map(o=>o.node)),edges:new Set(g.internal_bindings.map(b=>b.edge))}));
    const definitions=new Map(baseline.graph.expression_goals.goals.map(g=>[g.id,g]));
    const covered=g=>{const goal=definitions.get(g.id);return goal&&structures.some(s=>goal.core.every(id=>s.nodes.has(id))&&goal.edges.every(id=>s.edges.has(id)));};
    return {critical:gained.filter(g=>critical.has(g.kind)).reduce((s,g)=>s+g.priority,0),
      structure:roles+2*summaries+gained.filter(g=>g.kind!=='computation'&&!critical.has(g.kind)&&!covered(g)).reduce((s,g)=>s+g.priority,0),
      detail:gained.reduce((s,g)=>s+g.priority,0),
      only_summary_internal:gained.length>0&&gained.every(g=>!critical.has(g.kind)&&covered(g)),
      summary_internal_details:gained.filter(g=>!critical.has(g.kind)&&covered(g)).map(g=>g.id)};
  }
  function density(value,before,after){
    const cost=Math.max(1,after.area/Math.max(1,before.area))*(1+Math.max(0,after.crossings-before.crossings)/Math.max(4,before.crossings+4));
    return {...value,cost,score:[value.critical/cost,value.structure/cost,value.detail/cost]};
  }
  function compare(a,b){
    for(let i=0;i<a.score.length;i++)if(Math.abs(a.score[i]-b.score[i])>1e-9)return b.score[i]-a.score[i];
    return a.cost-b.cost;
  }
  function preview(ir,baseline,graph){
    const before=evidence(ir,baseline),visible=new Set(graph.nodes.map(n=>n.id)),edges=new Set();
    for(const e of graph.edges)for(const member of e.bundle_members||[e])for(const id of [member.id,...member.originals||[]])edges.add(id);
    const gained=baseline.graph.expression_goals.goals.filter(g=>!before.goals.has(g.id)&&g.core.every(id=>visible.has(id))&&g.edges.every(id=>edges.has(id)));
    const roles=new Set((graph.publication.role_frontier?.roles||[]).filter(r=>r.status==='exposed').map(r=>JSON.stringify([r.certificate,r.role_keys,r.node])));
    // Projection estimates rank trials only. Actual text, routes, cuts,
    // evidence and resource checks still decide eligibility and selection.
    return contribution(baseline,gained,[...roles].filter(id=>!before.roles.has(id)).length,0);
  }
  function assess(ir,baseline,trial){
    const b=metrics(baseline),q=metrics(trial),before=evidence(ir,baseline),after=evidence(ir,trial),reasons=[];
    const gained=[...after.goals.values()].filter(g=>!before.goals.has(g.id)),lost=[...before.goals.keys()].filter(id=>!after.goals.has(id));
    const gain=gained.reduce((s,g)=>s+g.priority,0);
    const newSummaries=[...after.summaries].filter(id=>!before.summaries.has(id));
    if(!gain&&!newSummaries.length)reasons.push('no-verified-relationship-gain');
    if(lost.length)reasons.push('previous-expression-lost');
    const lostSummaries=[...before.summaries].filter(id=>!after.summaries.has(id));
    if(lostSummaries.length)reasons.push('previous-dependency-structure-lost');
    if([...before.roles].some(id=>!after.roles.has(id)))reasons.push('previous-role-lost');
    if([...after.paths].some(([id,verified])=>!verified&&(!before.paths.has(id)||before.paths.get(id))))reasons.push('unverified-role-path-binding');
    if([...before.boundaries].some(id=>!after.boundaries.has(id)))reasons.push('visible-boundary-lost');
    if([...after.conflicts].some(id=>!before.conflicts.has(id)))reasons.push('new-constraint-conflict');
    for(const [key,objects]of [['node_accounting',ir.nodes],['edge_accounting',ir.edges]]){
      const ids=Object.values(trial.graph[key]).flat(),expected=new Set(objects.map(o=>o.id));
      if(ids.length!==expected.size||new Set(ids).size!==ids.length||ids.some(id=>!expected.has(id)))reasons.push('incomplete-'+key);
    }
    const cuts=g=>JSON.stringify(g.publication.boundary.map(({visible_node,...r})=>r));
    if(cuts(baseline.graph)!==cuts(trial.graph))reasons.push('changed-focus-boundary');
    if(q.issues.some(issue=>!b.issues.includes(issue)))reasons.push('new-quality-issue');
    for(const key of ['route_failures','unplaced_labels','contacts','overlaps'])if(q[key]>b[key])reasons.push('increased-'+key);
    if(q.font<b.font||q.font<12)reasons.push('smaller-font');
    const limits=trial.graph.publication.canvas_limits;
    if(q.width>Math.max(limits.width_px,b.width)||q.height>Math.max(limits.height_px,b.height)||q.area>Math.max(limits.area_px2,b.area)||
      q.nodes>Math.max(limits.nodes,b.nodes)||q.edges>Math.max(limits.edges,b.edges))reasons.push('resource-budget');
    if(q.area>b.area*2.5)reasons.push('disproportionate-area-cost');
    // Detail adds real paths; allow only a bounded, explicit crossing cost.
    // Contacts and distinct-value overlaps never receive this allowance.
    const crossingAllowance=Math.floor((gain+2*newSummaries.length)/2);
    if(q.crossings>b.crossings+crossingAllowance)reasons.push('crossing-cost');
    const benefit=density(contribution(baseline,gained,[...after.roles].filter(id=>!before.roles.has(id)).length,newSummaries.length),b,q);
    return {accepted:!reasons.length,reasons,gain,gained_goals:gained,gained_summary_goals:newSummaries,selection_benefit:benefit,lost_goals:lost,lost_summary_goals:lostSummaries,
      preserved_summary_goals:[...before.summaries].filter(id=>after.summaries.has(id)),new_exposed_roles:after.roles.size-before.roles.size,
      before:b,candidate:q,crossing_allowance:crossingAllowance};
  }
  const api={VERSION,candidates,apply,metrics,evidence,assess,preview,compare};root.SemanticAdaptiveFrontier=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
