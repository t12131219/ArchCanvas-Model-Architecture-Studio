/* Open projection protocol. A receipt distinguishes preserved endpoints from
 * actual geometry; unknown handlers defer rather than silently claiming work. */
(function(root){
  'use strict';
  const VERSION='relation-constraints/1',copy=x=>JSON.parse(JSON.stringify(x));
  const types={'source-uses':'source-group','gated-product':'role-correspondence','gated-join':'role-correspondence',
    join:'operand-correspondence','axis-transform':'operand-correspondence','axis-normalization':'operand-correspondence',
    arithmetic:'operand-correspondence','linear-transform':'main-order','state-interface':'state-ports',
    'conditional-region':'conditional-boundary','conditional-join':'conditional-boundary','unknown-boundary':'opaque-boundary',
    selection:'selection-ports','iteration-template':'iteration-boundary','iteration-binding':'iteration-ports',
    'same-object-calls':'object-invocations','observed-parameter-aliases':'parameter-aliases'};
  function compile(plan){
    const result=(plan.relation_graph?.relations||[]).map(r=>({id:'constraint:'+r.id,type:types[r.type]||r.type,node:r.node,members:r.members,
      evidence:{relation:r.id,scope:r.evidence_scope,source_scope:r.source_scope,condition_scope:copy(r.condition_scope||[]),rule_version:r.rule_version},
      strength:r.type==='source-uses'?'soft':'hard',endpoints:copy(r.bindings),properties:copy(r.properties)}));
    for(const [i,c]of(plan.design_constraints||[]).entries())result.push({id:'constraint:design:'+(c.certificate||c.node||i)+':'+c.kind,type:c.kind,
      node:c.node||c.parent||c.add,members:c.members||[],evidence:{certificate:c.certificate||null,scope:'source-contract'},strength:'soft',endpoints:[],properties:copy(c)});
    return result;
  }
  function project(plan,edges,rep,accounting){
    const byOriginal=new Map();
    for(const edge of edges)for(const m of edge.bundle_members||[edge])for(const id of new Set([m.id,...m.originals||[]])){
      if(!byOriginal.has(id))byOriginal.set(id,[]);byOriginal.get(id).push(edge);
    }
    const hidden=new Map();for(const [status,ids]of Object.entries(accounting))for(const id of ids)hidden.set(id,status);
    const receipts=compile(plan).map(c=>({...c,visible_node:rep(c.node),status:'deferred',reason:'not-evaluated',mapping:c.endpoints.map(b=>{
      const drawn=byOriginal.get(b.edge)||[];
      for(const e of drawn){e.semantic_bindings=e.semantic_bindings||[];if(!e.semantic_bindings.some(s=>s.constraint===c.id&&s.edge===b.edge&&s.role===b.role))e.semantic_bindings.push({constraint:c.id,edge:b.edge,role:b.role});
        if(c.type==='state-ports'&&['initial-state','final-state','final-state-pair'].includes(b.role)&&!e.bundle_members&&!e.design_route)e.design_route={kind:'state-interface',certificate:c.evidence.relation};
        if(c.type==='iteration-ports'&&b.role==='iteration-feedback'&&!e.bundle_members&&!e.design_route&&e.target===b.target)
          e.design_route={kind:'iteration-feedback',certificate:c.evidence.relation};
        if(c.type==='iteration-ports'&&b.role==='iteration-completion'&&e.target===b.target){
          const body=rep(c.properties.body);
          if(body&&body!==e.target)e.layout_after=body;
        }
      }
      return {...b,visible_edges:drawn.map(e=>e.id),visible_source:drawn.length?drawn[0].source:rep(b.producer),visible_target:drawn.length?drawn[0].target:rep(b.target),status:drawn.length?'drawn':hidden.get(b.edge)||'excluded'};
    })}));
    return receipts;
  }
  function evaluate(receipts,positions,edges){
    const byEdge=new Map(edges.map(e=>[e.id,e])),known=new Set(Object.values(types));
    for(const r of receipts){
      const mapped=r.mapping.every(b=>b.visible_edges.length),node=positions.get(r.visible_node);
      r.endpoint_preservation={drawn:r.mapping.filter(b=>b.visible_edges.length).length,total:r.mapping.length};
      const defer=reason=>{r.status='deferred';r.reason=reason;};
      const applied=(reason,geometry)=>{r.status='applied';r.reason=reason;r.consumption=geometry;};
      if(!known.has(r.type)&&!['bypass','parallel-projections','serial-sequence'].includes(r.type)){defer('no-handler; canonical graph layout remains available');continue;}
      if(r.type==='bypass'){
        const c=r.properties,edge=edges.find(e=>e.design_route?.certificate===c.certificate&&e.design_route.kind==='bypass');
        if(edge&&positions.get(edge.design_route.owner)?.design_gutter)applied('exact skip operand has a reserved layout lane','reserved-lane');else defer('exact bypass endpoints are not both exposed or semantic lanes are disabled');continue;
      }
      if(r.type==='parallel-projections'){
        const L=root.SemanticLayout||(typeof require==='function'?require('./architecture-layout.js'):null);
        const group=positions.context.branchColumns?.find(g=>r.members.length>1&&r.members.every(id=>positions.has(id))&&
          new Set(r.members.map(id=>g.chains.findIndex(c=>c.nodes.includes(id)))).size===r.members.length&&r.members.every(id=>g.chains.some(c=>c.nodes.includes(id))));
        const ps=r.members.map(id=>positions.get(id));
        if(group&&ps.every(p=>p.y===ps[0].y)&&L.branchGeometry(group,positions)){
          r.path_columns=copy(group);applied('exact members occupy distinct dependency columns and one measured row; execution parallelism is not asserted','branch-columns');
        }else defer('exact members are folded, do not form independent paths, or column geometry is not realized');
        continue;
      }
      if(r.type==='serial-sequence'){defer('legacy declaration; geometry has no unified handler yet');continue;}
      if(!node){defer('outside current evidence or panel scope');continue;}
      if(!mapped){defer('one or more exact roles are folded, attached or outside this panel');continue;}
      if(['object-invocations','parameter-aliases'].includes(r.type)){
        if(r.members.every(id=>positions.has(id)))applied('distinct invocation or parameter nodes exposed; visible identity labels require separate expression audit','identity-endpoints');
        else defer('identity members are folded; a shared enclosing box cannot express invocation identity');
        continue;
      }
      if(r.type==='source-group'){
        const ids=[...new Set(r.mapping.map(b=>b.visible_target))],ps=ids.map(id=>positions.get(id));
        if(ids.length>1&&r.mapping.every(b=>b.visible_target===b.target)&&ps.every(p=>p&&p.y===ps[0].y&&p.w===ps[0].w))applied('distinct consumer ports retained; consumers share a measured row and width','source-alignment');else defer('source uses preserved; topology or folding prevents a common aligned row');continue;
      }
      if(r.type==='state-ports'){
        const state=r.mapping.filter(b=>['initial-state','final-state','final-state-pair'].includes(b.role));
        if(state.length&&state.every(b=>b.visible_edges.every(id=>positions.get(byEdge.get(id)?.design_route?.owner)?.design_gutter)))applied('framework state slots retained in reserved side channels','reserved-state-lanes');else defer('state slots retained; a state channel cannot be reserved at this frontier');continue;
      }
      if(r.type==='iteration-ports'){
        const back=r.mapping.find(b=>b.role==='iteration-feedback');
        const completion=r.mapping.find(b=>b.role==='iteration-completion');
        r.reading_order={scope:'visual preference; the zero-iteration path remains valid',applied:!!completion?.visible_edges.length&&completion.visible_edges.every(id=>{
          const e=byEdge.get(id),body=positions.get(e?.layout_after),result=positions.get(e?.target);
          return body&&result&&result.y>=body.y+body.h;
        })};
        if(r.visible_node!==r.node){defer('iteration binding reaches a folded boundary; detailed feedback is not exposed');continue;}
        if(back?.visible_edges.every(id=>positions.get(byEdge.get(id)?.design_route?.owner)?.design_gutter))
          applied('normal-completion feedback and exact entry/exit bindings retained in a reserved channel','reserved-iteration-lane');
        else defer('iteration bindings retained; feedback channel cannot be reserved at this frontier');
        continue;
      }
      if(r.visible_node!==r.node){defer('roles reach the enclosing boundary; internal relation needs a detail panel');continue;}
      applied('canonical operand, condition and output-slot bindings retained on visible edges','port-bindings');
    }
    return receipts;
  }
  function auditRoutes(receipts,positions,routes){
    const by=new Map(routes.map(r=>[r.id,r]));
    for(const receipt of receipts)if(receipt.status==='applied'&&['reserved-state-lanes','reserved-lane','reserved-iteration-lane','local-bypass-lane'].includes(receipt.consumption)){
      const relevant=receipt.type==='bypass'?routes.filter(e=>e.design_route?.certificate===receipt.properties.certificate):receipt.mapping.filter(b=>['initial-state','final-state','final-state-pair','iteration-feedback'].includes(b.role)).flatMap(b=>b.visible_edges.map(id=>by.get(id)));
      const scopes=receipt.type==='bypass'?(positions.context.localBypassScopes||[]).filter(s=>s.certificate===receipt.properties.certificate):[];
      const L=root.SemanticLayout||(typeof require==='function'?require('./architecture-layout.js'):null);
      const okay=scopes.length?relevant.length===scopes.length&&relevant.every(e=>{
        const s=scopes.find(s=>s.edge===e.id),c=receipt.properties;
        return s&&s.skip===c.skip&&s.skip_slot===c.skip_slot&&s.add===c.add&&
          JSON.stringify(s.mapping.map(m=>m.canonical))===JSON.stringify(c.branch_path)&&L.localBypassGeometry(s,e,positions);
      }):receipt.consumption!=='local-bypass-lane'&&relevant.length&&relevant.every(e=>{const p=positions.get(e?.design_route?.owner);return p&&e.route?.ok&&e.route.points.some(v=>v.x>p.x&&v.x<p.x+p.design_gutter);});
      receipt.route_verified=!!okay;
      if(okay&&scopes.length){receipt.consumption='local-bypass-lane';receipt.reason='exact skip operand bypasses the certified visible branch frontier; original source owner retained';}
      if(!okay){receipt.status='conflict';receipt.reason='reserved channel was not realized by the final obstacle-aware routes';}
    }
    for(const receipt of receipts)if(receipt.status==='applied'&&receipt.consumption==='branch-columns'){
      const L=root.SemanticLayout||(typeof require==='function'?require('./architecture-layout.js'):null),group=receipt.path_columns;
      const okay=L.branchGeometry(group,positions)&&group.chains.every(c=>c.edges.every(id=>by.get(id)?.route.ok));
      receipt.route_verified=!!okay;
      if(!okay){receipt.status='conflict';receipt.reason='dependency columns or their final paths were not realized';}
    }
    return receipts;
  }
  const api={VERSION,compile,project,evaluate,auditRoutes};root.SemanticRelationConstraints=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
