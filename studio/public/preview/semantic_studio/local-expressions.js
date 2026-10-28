/* Local expression requests consume independent relation facts. They do not
 * recognize whole models, create containers, or change canonical bindings. */
(function(root){
  'use strict';
  const VERSION='local-expressions/1';
  const forms={'gated-product':'calculation','gated-join':'calculation','state-interface':'interface',
    selection:'interface','unknown-boundary':'boundary','conditional-join':'condition',
    'conditional-region':'condition','iteration-binding':'iteration','iteration-template':'iteration',
    'same-object-calls':'identity','observed-parameter-aliases':'identity'};
  function compile({plan,focus,details=[]}){
    const requested=new Set(Array.isArray(details)?details.filter(id=>typeof id==='string'):[]),preferred=new Set();
    const by=new Map(plan.nodes.map(n=>[n.id,n])),open=new Set(),scopes=new Set(),requests=[];
    const within=(id,owner)=>{const seen=new Set();while(id&&!seen.has(id)){if(id===owner)return true;seen.add(id);id=by.get(id)?.parent;}return false;};
    const certificates=new Set((plan.semantic_contracts||[]).map(c=>c.node));
    const boundary=n=>n.contract_stage?'certified-role-stage':certificates.has(n.id)?'certificate':n.kind==='opaque'||n.mutable?'effects':
      n.condition||n.kind==='control'||n.semantic_type==='conditional-collection'?'condition':n.identity_display||n.observed_calls||n.evidence_status==='runtime-only'||n.runtime_evidence?.length?'identity-or-observation':
      ['loop-template','iteration-region','serial-repeat','repeat-instance','serial-remainder'].includes(n.semantic_type)&&!n.sequence_frontier?'iteration-or-repeat':null;
    for(const r of plan.relation_graph?.relations||[]){
      const explicit=requested.has(r.id);
      if((!forms[r.type]&&!explicit)||!within(r.node,focus))continue;
      const targets=[...new Set([r.node,...(forms[r.type]==='calculation'?r.members:forms[r.type]==='identity'?r.members:[]),
        ...(r.properties.required_nodes||[]),...(forms[r.type]==='condition'?r.members.filter(id=>by.get(id)?.kind==='control'):[]),
        ...(explicit?r.bindings.flatMap(b=>[b.producer,b.target]):[])])];
      const scope=by.get(r.source_scope)?.kind==='composite'&&within(r.source_scope,focus)?r.source_scope:focus;
      const rows=targets.filter(id=>by.has(id)).map(node=>{
        // External inputs remain external. A local relation cannot ask to
        // unwrap arbitrary consumers, condition bodies, or certified modules.
        if(!within(node,scope))return {node,frontier_node:node,location:'external',stop:null};
        const chain=[];let at=node;while(at&&at!==focus){chain.unshift(at);at=by.get(at)?.parent;}
        let frontier=node,stop=null;
        for(const id of [focus,...chain]){const why=boundary(by.get(id));if(why){frontier=id;stop=why;break;}}
        at=by.get(frontier)?.parent;
        while(at&&within(at,focus)){open.add(at);if(explicit)preferred.add(at);if(at===focus)break;at=by.get(at)?.parent;}
        return {node,frontier_node:frontier,location:'internal',stop};
      });
      // A source scope gets a budget only when this request can reach its
      // contents. A folded certified or conditional scope is never a shortcut.
      if(scope!==focus&&rows.some(row=>row.location==='internal'&&within(row.frontier_node,scope)&&row.frontier_node!==scope))scopes.add(scope);
      requests.push({relation:r.id,type:r.type,form:forms[r.type]||'structure',scope,targets:rows,...(explicit?{requested:true}:{}),
        bindings:r.bindings,not_asserted:r.not_asserted,evidence_scope:r.evidence_scope,
        condition_scope:r.condition_scope,rule_version:r.rule_version});
    }
    return {version:VERSION,open,scopes,requests,preferred};
  }
  function receipt(frontier,graph){
    const positions=graph.positions,byConstraint=new Map((graph.constraint_receipts||[]).map(c=>[c.evidence.relation,c]));
    return {rule_version:VERSION,scope:'Local expression requests; no new computation, family label, purity or execution claim.',
      requests:frontier.requests.map(r=>{
        const c=byConstraint.get(r.relation),targets=r.targets.map(t=>({...t,visible_node:positions.has(t.node)?t.node:graph.representatives[t.node]||null,
          status:positions.has(t.node)?'exposed':positions.has(t.frontier_node)?'boundary':'folded'}));
        const internal=targets.filter(t=>t.location==='internal'),bindings=c?.mapping||[];
        const fulfilled=internal.length>0&&internal.every(t=>t.status==='exposed')&&bindings.length===r.bindings.length&&bindings.every(b=>b.visible_edges.length);
        return {...r,targets,bindings,status:fulfilled?'ready':'deferred',
          reason:fulfilled?'Exact local operations and bindings are projected; final route and expression checks remain.':
            internal.some(t=>t.status!=='exposed'&&t.stop)?'A certified, conditional, effect, identity or iteration boundary limits this expression.':
            'One or more local operations or bindings remain folded, attached or outside the frontier budget.'};
      })};
  }
  function select(frontier,{plan,focus,open,budget,eligible,budgetScopes}){
    const by=new Map(plan.nodes.map(n=>[n.id,n])),children=new Map();
    for(const n of plan.nodes){if(!children.has(n.parent))children.set(n.parent,[]);children.get(n.parent).push(n.id);}
    const selected=new Set(open),scopes=new Set([...budgetScopes,...frontier.scopes]);
    const scopeOf=id=>{let at=by.get(id)?.parent;while(at){if(scopes.has(at)||by.get(at)?.sequence_frontier)return at;at=by.get(at)?.parent;}return null;};
    const cost=id=>by.get(id).kind==='interface'?.25:1;
    const leaves=()=>{const todo=[focus],out=[];for(let i=0;i<todo.length;i++){const id=todo[i];if(!eligible(id))continue;if(selected.has(id))todo.push(...children.get(id)||[]);else out.push(id);}return out;};
    const usedIn=scope=>{const seen=new Set();return leaves().reduce((total,id)=>{
      let local=scopeOf(id);if(local===scope)return total+cost(id);
      while(local&&scopeOf(local)!==scope)local=scopeOf(local);
      if(!local||seen.has(local))return total;seen.add(local);return total+1;
    },0);};
    const depth=id=>{let d=0;while(by.get(id)?.parent){d++;id=by.get(id).parent;}return d;};
    // Supplement the existing frontier only along requested paths. Independent
    // budgets must not release space for unrelated automatic helper expansion.
    for(const id of [...frontier.open].sort((a,b)=>Number(frontier.preferred?.has(b)||false)-Number(frontier.preferred?.has(a)||false)||depth(a)-depth(b))){
      if(selected.has(id)||!leaves().includes(id))continue;
      const kids=(children.get(id)||[]).filter(eligible),childCost=kids.reduce((sum,id)=>sum+cost(id),0);
      const delta=scopes.has(id)?0:childCost-cost(id);
      if(!kids.length||usedIn(scopeOf(id))+delta>budget||scopes.has(id)&&childCost>budget)continue;
      selected.add(id);
    }
    return [...selected];
  }
  function verify(receipt,graph,prepared){
    const coverage=new Map(graph.expression_coverage.map(c=>[c.goal,c]));
    for(const r of receipt.requests){
      const checked=coverage.get('goal:'+r.relation),edgeIds=new Set(r.bindings.flatMap(b=>b.visible_edges));
      const labels=prepared.labeling.suppressed.filter(l=>edgeIds.has(l.edge));
      r.expression_check=checked?.status||'missing';r.unplaced_role_labels=labels.map(l=>l.edge);
      if(r.status==='ready'){
        r.status=checked?.status==='fulfilled'&&!labels.length?'fulfilled':'deferred';
        r.reason=r.status==='fulfilled'?'Exact local operations, canonical operand/output paths and requested labels passed final rendering checks.':
          'Projected endpoints are present, but final route, identity, control or role-label checks are incomplete.';
      }
    }
    return receipt;
  }
  const api={VERSION,compile,select,receipt,verify};root.SemanticLocalExpressions=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
