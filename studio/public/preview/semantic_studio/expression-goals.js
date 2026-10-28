/* A closed box does not fulfill the detailed relationships it contains.
 * Goals are evaluated against the selected, routed panel, not export intent. */
(function(root){
  'use strict';
  const VERSION='expression-goals/3';
  // A routed ID is only a lookup key. Validate the represented canonical
  // producer, result slot, receiving operand, condition and evidence too.
  // Only unconditional interface/alias chains may explain a projected path.
  function canonicalPaths(ir,routes){
    const by=new Map(ir.nodes.map(n=>[n.id,n])),edges=new Map(ir.edges.map(e=>[e.id,e])),incoming=new Map(),outgoing=new Map(),paths=new Map();
    const flow=e=>['data','alias','interface-binding'].includes(e.kind),transparent=n=>n&&['interface','value-alias'].includes(n.kind)&&!n.operator;
    for(const e of ir.edges){
      if(!incoming.has(e.target))incoming.set(e.target,[]);incoming.get(e.target).push(e);
      if(!outgoing.has(e.source))outgoing.set(e.source,[]);outgoing.get(e.source).push(e);
    }
    for(const path of routes)for(const member of path.bundle_members||[path])for(const id of new Set([member.id,...member.originals||[]])){
      if(!paths.has(id))paths.set(id,[]);paths.get(id).push({path,member});
    }
    const resolved=new Map(),reachable=new Map(),checked=new Map();
    const resolve=(first,slot='out')=>{
      const key=JSON.stringify([first,slot]);if(resolved.has(key))return resolved.get(key);
      let id=first,port=slot;const seen=new Set();while(!seen.has(id)){
        seen.add(id);const n=by.get(id),es=incoming.get(id)||[];if(!transparent(n)||es.length!==1||!flow(es[0])||es[0].condition)break;
        const e=es[0],outer=n.kind==='value-alias'?n.slot??e.source_port??'out':e.source_port??'out';
        port=outer==='out'?port:port==='out'?outer:outer+'.'+port;id=e.source;
      }
      const value=JSON.stringify([id,port]);resolved.set(key,value);return value;
    };
    const reaches=(first,last)=>{
      const key=JSON.stringify([first,last]);if(reachable.has(key))return reachable.get(key);
      const todo=[first],seen=new Set();for(let i=0;i<todo.length;i++){
        const at=todo[i];if(at===last){reachable.set(key,true);return true;}
        if(seen.has(at)||!transparent(by.get(at)))continue;seen.add(at);
        for(const e of outgoing.get(at)||[])if(flow(e)&&!e.condition)todo.push(e.target);
      }
      reachable.set(key,false);return false;
    };
    const exact=id=>{
      if(checked.has(id))return checked.get(id);
      const e=edges.get(id),valid=!!e&&(paths.get(id)||[]).some(({path,member})=>{
        const terminal=edges.get(member.id),source=member.resolved_source??member.canonical_source;
        return terminal&&path.route.ok&&member.canonical_source===terminal.source&&member.canonical_target===terminal.target&&
          member.target_port===terminal.target_port&&member.kind===terminal.kind&&member.evidence===terminal.evidence&&
          JSON.stringify(member.condition)===JSON.stringify(terminal.condition)&&
          resolve(terminal.source,terminal.source_port)===resolve(source,member.source_port)&&
          resolve(e.source,e.source_port)===resolve(source,member.source_port)&&reaches(e.target,member.canonical_target??member.target)&&
          (member.id!==e.id||member.target_port===e.target_port&&member.kind===e.kind&&JSON.stringify(member.condition)===JSON.stringify(e.condition));
      });
      checked.set(id,valid);return valid;
    };
    return {exact,paths,incoming};
  }
  function build(ir,plan){
    const by=new Map(ir.nodes.map(n=>[n.id,n])),goals=[],covered=new Set(),incoming=new Map(),outgoing=new Set();
    for(const e of ir.edges){if(!incoming.has(e.target))incoming.set(e.target,[]);incoming.get(e.target).push(e);outgoing.add(e.source);}
    for(const r of plan.relation_graph?.relations||[]){
      const core=[r.node];
      // Reusing one result is an independently expressible relationship even
      // when no larger module is recognized. The producer and every receiving
      // operation must be physically present, with all exact operand paths.
      if(r.type==='source-uses')core.push(...r.bindings.map(b=>b.target));
      if(['gated-product','gated-join'].includes(r.type))core.push(...r.bindings.filter(b=>b.role==='gate'||b.role.endsWith(':gate')||b.role.startsWith('sum:')).map(b=>b.producer));
      if(r.type==='conditional-join'||r.type==='conditional-region')core.push(...r.members.filter(id=>by.get(id)?.kind==='control'));
      core.push(...r.properties.required_nodes||[]);
      goals.push({id:'goal:'+r.id,kind:r.type,relation:r.id,focus_node:r.node,core:[...new Set(core)],edges:[...new Set(r.bindings.map(b=>b.edge))],provenance_edges:r.edges,
        identity:r.type==='same-object-calls'?{reference:r.properties.reference,calls:r.members}:r.type==='observed-parameter-aliases'?{node:r.node,aliases:r.properties.aliases}:null,
        priority:['unknown-boundary','state-interface','conditional-region','conditional-join','selection','iteration-template','iteration-binding'].includes(r.type)?3:2,
        expression:r.type==='unknown-boundary'?'boundary-summary':['state-interface','selection','gated-product','gated-join','conditional-region','conditional-join','iteration-binding'].includes(r.type)?'role-relationships':'computation-structure'});
      covered.add(r.node);
    }
    for(const n of ir.nodes){
      const externalInput=n.kind==='interface'&&n.role==='input'&&!incoming.has(n.id);
      const externalOutput=n.kind==='interface'&&n.role==='output'&&!outgoing.has(n.id);
      if((!covered.has(n.id)&&['compute','opaque','control'].includes(n.kind))||externalInput||externalOutput)
        goals.push({id:'goal:node:'+n.id,kind:n.kind==='interface'?'external-interface':'computation',focus_node:n.id,core:[n.id],
          edges:externalOutput?(incoming.get(n.id)||[]).filter(e=>['data','alias','interface-binding'].includes(e.kind)).map(e=>e.id):[],
          direction:externalInput?'input':externalOutput?'output':null,priority:n.kind==='opaque'?3:1,expression:n.kind==='opaque'?'boundary-summary':'computation-structure'});
    }
    return {schema:VERSION,goals};
  }
  function evaluate(goalSet,graph,prepared,ir){
    const proof=canonicalPaths(ir,prepared.routes);
    const routed=new Map(prepared.routes.map(e=>[e.id,e])),edges=new Map(),receiptsByRelation=new Map(),nodes=new Map(graph.nodes.map(n=>[n.id,n]));
    // Index this evaluation's receipts, including the undefined relation key.
    // Never cache mutable route/constraint evidence across frontier trials.
    for(const c of graph.constraint_receipts||[]){const key=c.evidence.relation;if(!receiptsByRelation.has(key))receiptsByRelation.set(key,[]);receiptsByRelation.get(key).push(c);}
    for(const e of prepared.routes)for(const m of e.bundle_members||[e])for(const id of new Set([m.id,...m.originals||[]])){
      if(!edges.has(id))edges.set(id,[]);edges.get(id).push(e);
    }
    return goalSet.goals.map(goal=>{
      const missingNodes=goal.core.filter(id=>!graph.positions.has(id));
      const missingEdges=goal.edges.filter(id=>!edges.has(id));
      const failures=goal.edges.filter(id=>(edges.get(id)||[]).some(e=>!routed.get(e.id)?.route.ok));
      const required=[...new Set([...goal.edges,...(goal.kind==='computation'?(proof.incoming.get(goal.focus_node)||[])
        .filter(e=>['data','alias','interface-binding'].includes(e.kind)).map(e=>e.id):[])])];
      const missingBindings=required.filter(id=>!proof.exact(id));
      const receipts=receiptsByRelation.get(goal.relation)||[];
      const conflicts=receipts.filter(c=>c.status==='conflict').map(c=>c.id);
      const printed=n=>(n?.paper?.captions||[]).join('').replace(/\s/g,'');
      const missingIdentity=goal.identity?goal.kind==='same-object-calls'?goal.identity.calls.filter(id=>{
        const n=nodes.get(id),d=n?.identity_display;return d?.reference!==goal.identity.reference||d.relation!==goal.relation||!printed(n).includes(d.label.replace(/\s/g,''))||!printed(n).includes(`sourcecall${d.invocation}/${d.count}`);
      }):[goal.identity.node].filter(id=>{
        const n=nodes.get(id);return n?.identity_display?.relation!==goal.relation||!goal.identity.aliases.every(a=>printed(n).includes(a.replace(/\s/g,'')));
      }):[];
      // Every relation edge has to reach a physical path; hidden internal edges
      // and merely attached evidence cannot count as an expressed relationship.
      const fulfilled=!missingNodes.length&&!missingEdges.length&&!failures.length&&!conflicts.length&&!missingIdentity.length&&!missingBindings.length;
      return {goal:goal.id,kind:goal.kind,expression:goal.expression,status:fulfilled?'fulfilled':'unfulfilled',
        missing_nodes:missingNodes,missing_edges:missingEdges,missing_exact_bindings:missingBindings,missing_identity:missingIdentity,route_failures:failures,constraint_conflicts:conflicts,
        visible_edges:[...new Set(goal.edges.flatMap(id=>(edges.get(id)||[]).map(e=>e.id)))]};
    });
  }
  function panelRequests(goalSet,plan){
    const by=new Map(plan.nodes.map(n=>[n.id,n]));
    const ancestry=id=>{const result=[];while(id){result.push(id);id=by.get(id)?.parent;}return result;};
    const grouped=new Map();
    for(const goal of goalSet.goals){
      const chains=goal.core.map(ancestry),scope=chains[0].find(id=>by.get(id)?.kind==='composite'&&chains.every(c=>c.includes(id)));
      if(!scope)continue;
      if(!grouped.has(scope))grouped.set(scope,{id:scope,goals:[],required_open:new Set(),priority:0});
      const request=grouped.get(scope);request.goals.push(goal.id);request.priority=Math.max(request.priority,goal.priority);
      for(const id of goal.core){let at=by.get(id)?.parent;while(at){request.required_open.add(at);if(at===scope)break;at=by.get(at)?.parent;}}
    }
    return [...grouped.values()].sort((a,b)=>b.priority-a.priority||a.id.localeCompare(b.id)).map(r=>({...r,required_open:[...r.required_open]}));
  }
  const api={VERSION,build,canonicalPaths,evaluate,panelRequests};root.SemanticExpressionGoals=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
