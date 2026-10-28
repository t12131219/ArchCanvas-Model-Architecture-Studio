/* Shared evidence text. Pure facts only; independent of geometry and glyphs. */
(function(root){
  'use strict';
  function nodeTitle(n,idx){
    const uses=n.boundary_uses||[];
    const contents=n.content_inventory;
    const pipeline=n.local_pipeline,labels=new Map(pipeline?.operations.map(o=>[o.node,o.label])||[]);
    const expression=t=>labels.get(t.node)+(t.inputs.length?' ← {'+t.inputs.map(i=>expression(i.expression)).join('; ')+'}':'');
    return [n.label,...(n.paper?.captions?.length?[n.paper.captions.join('\n')]:[]),...(n.paper?.source_kind_note?['Source kind: '+n.paper.source_kind_note.caption,n.paper.source_kind_note.scope]:[]),...(n.paper?.call_boundary?[n.paper.call_boundary.scope,'Expand to inspect the retained dependency DAG and exact operand bindings.']:[]),...(n.transform_configurations||[]).flatMap(r=>['Source literal configuration: '+r.text,r.scope,
      'Original operation: '+r.node+'; slots: '+JSON.stringify(r.slots)]),...(n.normal_return?[n.normal_return.scope,'Selected source return: '+n.normal_return.selected_return.node,
      'Fixed predicate: '+n.normal_return.predicate.slot+' = '+n.normal_return.predicate.value,
      'Retained source-alternative inputs: '+JSON.stringify(n.normal_return.alternative_inputs)]:[]),...(n.module_arguments||[]).flatMap(r=>[r.label,r.scope,'Reference: '+r.module_identity,JSON.stringify(r.edge),'Construction evidence: '+JSON.stringify(r.proof.construction_evidence)]),...(n.invocation_binding?['Fixed call argument: '+n.invocation_binding.label,n.invocation_binding.proof_scope,n.invocation_binding.claim,
      ...n.invocation_binding.uses.map(e=>`${e.id}: ${e.source} [${e.source_port}] → ${e.target} [${e.target_port}] · ${e.kind}`)]:[]),...(n.contract_stage?['Certified role subregion: '+n.contract_stage.certificate,n.contract_stage.scope,'Original operations remain individually expandable.']:[]),...(pipeline?[
      pipeline.dependency_dag?'Local dependency DAG: '+JSON.stringify(pipeline.dependency_dag):pipeline.dependency_tree?'Local dependency tree: '+expression(pipeline.dependency_tree):'Local dependency path: '+pipeline.operations.map(o=>o.label).join(' → '),pipeline.scope,
      ...(pipeline.path_display?[pipeline.path_display.scope,'Individual calls: '+JSON.stringify(pipeline.operations)]:[]),
      ...(pipeline.dependency_tree||pipeline.dependency_dag?pipeline.bindings.map(b=>`${b.edge}: ${b.producer} [${b.source_port}] → ${b.target} [${b.target_port}]`):[]),
      ...(pipeline.parameter_reads||[]).flatMap(p=>p.edges.map(e=>`Parameter read ${e.id}: ${p.node} → ${e.target} [${e.target_port}]`)),
      ...(pipeline.source_reads||[]).flatMap(p=>[p.scope,...p.edges.map(e=>`Source read ${e.id}: ${p.expression} (${p.node}) → ${e.target} [${e.target_port}]`)])]:[]),...(n.role_annotations||[]).map(r=>'Certified role: '+r.role+
        (r.role_keys?.some(k=>k.includes('.')||/^\d+$/.test(k))?' · exact keys: '+JSON.stringify(r.role_keys):'')+' · '+r.certificate+' · '+r.scope),...(n.frame_ownership||[]).map(r=>'Source ownership: '+r.label+' ['+r.node+'] · '+r.kind+' · '+r.scope),...(n.source_label?['Source label: '+n.source_label]:[]),
      ...(n.contract_evidence||[]).flatMap(c=>[c.rule+': '+c.scope,...c.proof,'Not asserted: '+c.not_asserted.join('; ')]),
      ...(n.observed_calls?[`${n.observed_calls.observations.length} observed calls; ${n.observed_calls.basis}`]:[]),
      ...(contents?['Contents of extracted units (unordered; parameter sharing not asserted):',
      ...contents.terms.map(t=>`${t.label} × ${t.count}`),...contents.units.map(u=>`${u.label}: ${u.term} · ${u.evidence_status}`)]:[]),
      ...uses.map(e=>`${e.id}: ${idx.nodes.get(e.target)?.label||e.target} [${e.target_port}] · ${e.evidence}`)].join('\n');
  }
  function nodeDetails(n,idx){
    return [
      n.evidence_status?'Evidence status: '+n.evidence_status:'',n.reason||'',
      ...(n.source||[]).map(s=>'Source: '+s.file+':'+s.line+(s.end_line&&s.end_line!==s.line?'-'+s.end_line:'')),
      nodeTitle(n,idx),...(n.source||[]).filter(s=>s.expression).map(s=>'Source expression:\n'+s.expression),
      n.condition?'Condition: '+JSON.stringify(n.condition):'',
      n.identity_display?'Identity: '+JSON.stringify(n.identity_display):'',
      n.iteration?'Iteration: '+JSON.stringify(n.iteration):''
    ].filter(Boolean).join('\n');
  }
  const api={nodeTitle,nodeDetails};root.SemanticEvidence=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
