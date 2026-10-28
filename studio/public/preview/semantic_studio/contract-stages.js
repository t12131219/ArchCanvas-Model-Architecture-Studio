/* Reversible presentation subregions selected from certified roles. A stage
 * never takes ownership of the certificate or of its entire proof scope. */
(function(root){
  'use strict';
  const VERSION='contract-stages/2',copy=x=>JSON.parse(JSON.stringify(x)),flow=e=>['data','alias','interface-binding'].includes(e.kind);
  function compile({ir,plan,branchTails=true,open=new Set()}){
    const nodes=plan.nodes.map(n=>({...n})),by=new Map(nodes.map(n=>[n.id,n])),canonical=new Map(ir.nodes.map(n=>[n.id,n])),ins=new Map(),uses=new Map(),rows=[],rejected=[],claimed=new Set();
    for(const e of ir.edges){if(!ins.has(e.target))ins.set(e.target,[]);ins.get(e.target).push(e);if(!uses.has(e.source))uses.set(e.source,[]);uses.get(e.source).push(e);}
    const guarded=n=>!n||n.kind==='opaque'||n.kind==='control'||n.mutable||n.condition||n.identity_display||n.observed_calls||n.evidence_status==='runtime-only'||n.runtime_evidence?.length;
    const resolve=(node,slot='out')=>{const seen=new Set();while(!seen.has(node)){
      seen.add(node);const n=canonical.get(node),incoming=ins.get(node)||[];
      if(!n||!['interface','value-alias'].includes(n.kind)||n.operator||guarded(n)||incoming.length!==1||!flow(incoming[0])||incoming[0].condition)break;
      const e=incoming[0],outer=n.kind==='value-alias'?(n.slot??e.source_port??'out'):(e.source_port??'out');
      slot=outer==='out'?slot:slot==='out'?outer:outer+'.'+slot;node=e.source;
    }return {node,slot};};
    for(const c of plan.semantic_contracts||[]){
      // This recipe is a local operation relation, independent of the enclosing
      // source/model name. Other certified role recipes can share this protocol.
      if(c.rule!=='residual-postnorm')continue;
      const r=c.roles||{},add=by.get(r.add),norm=by.get(r.normalization),core=[r.add,r.normalization];
      const reject=reason=>rejected.push({certificate:c.id,roles:core,reason});
      if(c.rule_version!=='source-contracts/1'||c.node!==r.normalization||r.output!==r.normalization||r.order!=='postnorm'||
        new Set(core).size!==2||core.some(id=>!canonical.has(id)||!c.members?.includes(id))){reject('incompatible-certificate');continue;}
      if(core.some(id=>claimed.has(id))){reject('overlapping-stage-roles');continue;}
      if(core.some(id=>guarded(by.get(id))||by.get(id)?.kind!=='compute')||!add.parent||add.parent!==norm.parent||
        norm.framework_type!==r.normalization_type||add.operator!=='add'){reject('incompatible-role-boundary');continue;}
      let parent=by.get(add.parent),blocked=false;while(parent){if(guarded(parent)){blocked=true;break;}parent=by.get(parent.parent);}
      if(blocked){reject('protected-enclosing-boundary');continue;}
      const incident=ir.edges.filter(e=>core.includes(e.source)||core.includes(e.target));
      if(incident.some(e=>e.condition||!flow(e)&&!['parameter-read','buffer-read','state-read'].includes(e.kind))){reject('effect-or-control-boundary');continue;}
      const outgoing=uses.get(add.id)||[],input=(ins.get(norm.id)||[]).filter(flow),operands=(ins.get(add.id)||[]).filter(flow);
      if(outgoing.length!==1||input.length!==1||outgoing[0]!==input[0]||input[0].target!==norm.id||
        (input[0].source_port??'out')!=='out'||operands.length!==2){reject('escaping-or-indirect-intermediate');continue;}
      const matches=(e,node,slot)=>{const v=resolve(e.source,e.source_port??'out');return v.node===node&&v.slot===slot;};
      const skip=operands.filter(e=>matches(e,r.skip,r.skip_slot)),branch=operands.filter(e=>matches(e,r.branch,r.branch_slot));
      if(skip.length!==1||branch.length!==1||skip[0]===branch[0]||skip[0].target_port===branch[0].target_port){reject('operand-role-mismatch');continue;}
      // A resource may enter as an annotation; it is never reparented or treated
      // as a tensor operand. Unknown sources cannot be hidden in this stage.
      if(incident.some(e=>!flow(e)&&(!['parameter','buffer','state'].includes(canonical.get(e.source)?.kind)||e.target!==norm.id))){reject('unresolved-resource-boundary');continue;}
      // A final unary operation of a longer proved branch may share this
      // presentation boundary. This groups computation; it does not make
      // that operation transparent, pure or equivalent to its input.
      let branchTail=null,stageParent=add.parent;
      const tail=by.get(r.branch),tailInputs=(ins.get(r.branch)||[]).filter(flow),tailUses=uses.get(r.branch)||[];
      const sourceParent=canonical.get(add.id)?.parent;
      const placementPath=id=>{
        const path=[];let at=by.get(id)?.parent;
        while(at&&at!==sourceParent){const n=by.get(at);
          if(!n?.presentation_only||n.semantic_type!=='structural-region'||guarded(n)||n.semantic_contracts?.length||
            n.contract_roles||n.repeat_contract||n.iteration||!open.has(at))return null;
          path.push(at);at=n.parent;
        }return at===sourceParent&&open.has(sourceParent)?path:null;
      };
      const paths=tail&&tail.parent!==add.parent?[tail.id,add.id,norm.id].map(placementPath):null;
      const sameScope=tail&&canonical.get(tail.id)?.parent===sourceParent&&canonical.get(norm.id)?.parent===sourceParent&&
        (tail.parent===add.parent||paths?.every(p=>p!==null));
      const aliases=[];let exit=tailUses.length===1?tailUses[0]:null;
      const visited=new Set([r.branch]);
      while(exit&&exit!==branch[0]){
        const alias=by.get(exit.target),incoming=ins.get(exit.target)||[],outgoing=uses.get(exit.target)||[];
        if(!alias||visited.has(alias.id)||alias.kind!=='value-alias'||alias.operator||alias.slot!=null||guarded(alias)||
          alias.semantic_contracts?.length||alias.contract_roles||alias.parent!==tail.parent||canonical.get(alias.id)?.parent!==sourceParent||
          incoming.length!==1||incoming[0]!==exit||outgoing.length!==1||!flow(exit)||exit.condition||
          (exit.source_port??'out')!=='out')break;
        visited.add(alias.id);aliases.push(alias.id);exit=outgoing[0];
      }
      if(branchTails&&tail?.kind==='compute'&&!guarded(tail)&&sameScope&&!claimed.has(tail.id)&&
        !tail.semantic_contracts?.length&&!tail.contract_roles&&c.members.includes(tail.id)&&r.branch_slot==='out'&&
        tailInputs.length===1&&exit===branch[0]&&aliases.every(id=>!claimed.has(id))){
        const input=resolve(tailInputs[0].source,tailInputs[0].source_port??'out');
        const tailEdges=ir.edges.filter(e=>e.source===tail.id||e.target===tail.id);
        const protectedEdge=tailEdges.some(e=>e.condition||!flow(e)&&
          (!['parameter-read','buffer-read','state-read'].includes(e.kind)||e.target!==tail.id||
           !['parameter','buffer','state'].includes(canonical.get(e.source)?.kind)));
        // A single operation directly on the skip is the whole branch, not
        // its tail. Keep it exposed. The certificate must prove a longer
        // branch, and its predecessor retains the actual interface boundary.
        if(!protectedEdge&&!core.includes(input.node)&&input.node!==tail.id&&
          (input.node!==r.skip||input.slot!==r.skip_slot)&&r.branch_path?.some(id=>id!==tail.id&&canonical.get(id)?.kind==='compute')){
          branchTail={node:tail.id,operator:tail.operator,framework_type:tail.framework_type??null,aliases,
            input:{edge:tailInputs[0].id,...input,target:tail.id,target_port:tailInputs[0].target_port},
            output_edge:branch[0].id,label:tail.framework_type?.split('.').at(-1)||
              (tail.source_framework_function===tail.function_target?tail.function_target?.split('.').at(-1):null)||tail.operator,
            scope:'One exclusive unary branch operation; its predecessor remains outside, and no input/output equivalence is asserted.',
            ...(paths?{placement:{source_parent:sourceParent,partitions:[...new Set(paths.flat())],
              scope:'Only already-open source-count partitions may be crossed; source, semantic and control boundaries remain.'}}:{})};
          if(paths)stageParent=sourceParent;
          core.unshift(tail.id,...aliases);
        }
      }
      let id='paper:contract-stage:'+c.id;while(by.has(id))id+=':1';
      const allIncident=ir.edges.filter(e=>core.includes(e.source)||core.includes(e.target));
      const cuts=allIncident.filter(e=>core.includes(e.source)!==core.includes(e.target));
      const row={rule_version:VERSION,node:id,form:'certified-role-subregion',certificate:c.id,certificate_node:c.node,
        recipe:'residual-postnorm-tail',roles:{add:add.id,normalization:norm.id,skip:r.skip,skip_slot:r.skip_slot,branch:r.branch,branch_slot:r.branch_slot},
        canonical_members:core.slice(),cuts:copy(cuts),internal_edges:allIncident.filter(e=>core.includes(e.source)&&core.includes(e.target)).map(e=>e.id),
        ...(branchTail?{branch_tail:branchTail}:{}),
        operands:operands.map(e=>({edge:e.id,role:e===skip[0]?'skip':'branch',...resolve(e.source,e.source_port??'out'),target:e.target,target_port:e.target_port})),
        normalization_type:r.normalization_type,scope:c.scope,not_asserted:copy(c.not_asserted||[])};
      const stage={id,parent:stageParent,kind:'composite',semantic_type:'certified-role-stage',label:'Add & Norm',
        presentation_only:true,source_parent:null,source:core.flatMap(id=>canonical.get(id).source||[]),runtime_evidence:[],evidence_status:'static-only',
        canonical_members:core.slice(),boundary_ports:copy(cuts),contract_stage:row};
      nodes.push(stage);by.set(id,stage);for(const member of core)by.get(member).parent=id;core.forEach(id=>claimed.add(id));rows.push(row);
    }
    // Recompute affected drawing partitions after moving a proved stage out
    // of count-based wrappers. Their current members and cuts must not keep
    // claiming operations now owned by the stage. Source IR stays unchanged.
    const touched=new Set(rows.flatMap(r=>r.branch_tail?.placement?.partitions||[])),repairs=[];
    const findings=(plan.findings||[]).map(f=>({...f}));
    for(const id of touched){
      const n=by.get(id),children=nodes.filter(n=>n.parent===id),todo=children.map(n=>n.id),members=[];
      for(let i=0;i<todo.length;i++){if(canonical.has(todo[i]))members.push(todo[i]);todo.push(...nodes.filter(n=>n.parent===todo[i]).map(n=>n.id));}
      const inside=new Set(members),previous=n.canonical_members||[];
      n.canonical_members=members;n.boundary_ports=ir.edges.filter(e=>inside.has(e.source)!==inside.has(e.target)).map(copy);
      n.region_summary=children.length+' remaining dependency units';
      const finding=findings.find(f=>f.id===n.finding);if(finding){finding.members=children.map(n=>n.id);finding.proof=[...(finding.proof||[]),
        'Membership recomputed after a certified local stage crosses already-open count partitions within the same source scope.'];}
      repairs.push({node:id,previous_members:previous,canonical_members:members,children:children.map(n=>n.id),cuts:copy(n.boundary_ports)});
    }
    return {plan:{...plan,nodes,findings},rows,rejected,partitions:repairs};
  }
  function receipt(stages,graph){return {rule_version:VERSION,rows:stages.rows.map(r=>({...r,
    visible_node:graph.positions.has(r.node)?r.node:graph.representatives[r.canonical_members[0]]||null,
    status:graph.positions.has(r.node)?graph.positions.get(r.node).expanded?'expanded':'summary':'folded',
    detailed_operations_exposed:r.canonical_members.filter(id=>graph.idx.nodes.get(id)?.kind==='compute').every(id=>graph.positions.has(id)),
    bypass_constraint:'constraint:design:'+r.certificate+':bypass'})),rejected:stages.rejected,partitions:stages.partitions};}
  const api={VERSION,compile,receipt};root.SemanticContractStages=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
