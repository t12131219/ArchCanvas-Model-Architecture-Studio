/* Fixed values belong to one extracted source invocation. This changes their
 * presentation, never control flow, operand identity or parameter ownership. */
(function(root){
  'use strict';
  const scalar=value=>value===null||typeof value==='boolean'||typeof value==='string'&&value.length<=40||typeof value==='number'&&Number.isFinite(value);
  const format=value=>value===null?'None':value===true?'True':value===false?'False':JSON.stringify(value);
  function compile(ir){
    const nodes=new Map(ir.nodes.map(n=>[n.id,n])),incoming=new Set(ir.edges.map(e=>e.target)),rows=new Map();
    const guarded=n=>!n||n.condition||n.mutable||n.identity_display||n.observed_calls||n.runtime_evidence?.length||n.evidence_status==='runtime-only'||
      ['opaque','control'].includes(n.kind)||['loop-template','iteration-region','conditional-region','observed-variant'].includes(n.semantic_type);
    for(const n of ir.nodes){
      const proof=n.source_constant_input;
      if(n.kind!=='interface'||n.role!=='input'||!n.parent||incoming.has(n.id)||guarded(n)||n.evidence_status!=='static-only'||
        !proof||!Object.hasOwn(proof,'value')||!scalar(proof.value)||typeof proof.scope!=='string'||!proof.scope||typeof n.label!=='string'||n.label.length>80)continue;
      const seen=new Set();let parent=n.parent,safe=true;
      while(parent!=null){if(seen.has(parent)||guarded(nodes.get(parent))){safe=false;break;}seen.add(parent);parent=nodes.get(parent).parent;}
      if(!safe)continue;
      rows.set(n.id,{node:n.id,source_parent:n.parent,value:proof.value,label:n.label+' = '+format(proof.value),
        proof_scope:proof.scope,uses:ir.edges.filter(e=>e.source===n.id).map(e=>({...e})),
        claim:'Fixed argument of this extracted source invocation only; no branch pruning, input role, purity or execution coverage assertion.'});
    }
    return rows;
  }
  const api={compile,format};root.SemanticInvocationInputs=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
