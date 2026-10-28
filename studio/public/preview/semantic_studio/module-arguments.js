/* A passed module is a reference, not a call. A closed source consumer can
 * carry that exact argument as an annotation; opening it restores the read. */
(function(root){
  'use strict';
  const VERSION='module-arguments/1',copy=x=>JSON.parse(JSON.stringify(x));
  const guarded=n=>!n||['opaque','control'].includes(n.kind)||n.condition||n.mutable||n.identity_display||n.observed_calls||
    n.runtime_evidence?.length||n.evidence_status!=='static-only'||n.iteration||n.repeat_contract||
    ['loop-template','iteration-region','conditional-region','observed-variant'].includes(n.semantic_type);
  const scalar=x=>x===null||['boolean','number','string'].includes(typeof x)&&(typeof x!=='number'||Number.isFinite(x));
  const format=x=>x===null?'None':x===true?'True':x===false?'False':JSON.stringify(x);
  function compile({ir,plan,open=new Set(),focus,requested=[]}){
    const source=new Map(ir.nodes.map(n=>[n.id,n])),by=new Map(plan.nodes.map(n=>[n.id,n])),ins=new Map(),uses=new Map(),identities=new Map(),wanted=new Set(requested);
    for(const e of ir.edges){if(!ins.has(e.target))ins.set(e.target,[]);ins.get(e.target).push(e);if(!uses.has(e.source))uses.set(e.source,[]);uses.get(e.source).push(e);}
    for(const n of ir.nodes)if(n.module_resource&&n.module_identity){if(!identities.has(n.module_identity))identities.set(n.module_identity,[]);identities.get(n.module_identity).push(n.id);}
    const visible=id=>{if(!by.has(id))return false;while(id!==focus){const p=by.get(id)?.parent;if(!p||!open.has(p))return false;id=p;}return true;};
    const sourceWithin=(id,owner)=>{while(id){if(id===owner)return true;id=source.get(id)?.parent;}return false;};
    // A static repeated ancestor does not change this one concrete argument.
    // The recipe never crosses instances or summarizes the repetition itself.
    const protectedScope=id=>{const seen=new Set();while(id){const n=by.get(id);if(seen.has(id)||guarded(n&&{...n,repeat_contract:null}))return true;seen.add(id);id=n.parent;}return false;};
    const rows=[];
    for(const n of ir.nodes){
      const p=n.module_resource_binding,v=n.symbolic_value,out=uses.get(n.id)||[],drawn=by.get(n.id);
      if(n.kind!=='state'||n.operator!=='attribute'||n.module_resource!==true||guarded(n)||guarded(drawn)||
        !visible(n.id)||ins.has(n.id)||out.length!==1||wanted.has(n.id)||drawn.role_annotations?.length||
        !p||p.rule_version!=='source-module-binding/1'||p.status!=='proved'||p.read!==n.id||
        typeof p.reference!=='string'||!p.reference||p.reference!==n.module_identity||identities.get(p.reference)?.length!==1||
        p.allocation!=='fresh-framework-construction'||!p.construction_evidence?.length||typeof p.scope!=='string'||!p.scope||
        !v||v.rule_version!=='source-symbolic-value/1'||v.kind!=='module-resource'||v.reference!==p.reference||
        typeof v.framework_type!=='string'||v.framework_type!==n.resource_framework_type)continue;
      const edge=out[0],input=source.get(edge.target),consumer=by.get(input?.parent),original=source.get(consumer?.id);
      if(edge.kind!=='interface-binding'||edge.evidence!=='source-dependency'||edge.condition||edge.iteration||edge.design_route||
        (edge.source_port??'out')!=='out'||typeof edge.target_port!=='string'||!edge.target_port||edge.target_port.length>80||
        guarded(input)||input.kind!=='interface'||input.role!=='input'||input.label!==edge.target_port||
        ins.get(input.id)?.length!==1||guarded(consumer)||guarded(original)||consumer.kind!=='composite'||consumer.presentation_only||
        wanted.has(consumer.id)||wanted.has(input.id)||consumer.parent!==drawn.parent||original.parent!==n.parent||
        by.get(input.id)?.parent!==consumer.id||!visible(consumer.id)||protectedScope(n.parent)||protectedScope(consumer.id))continue;
      // Calls inside this consumer may legitimately use the passed module.
      // A call/reference elsewhere keeps the shared object explicit instead.
      if(ir.nodes.some(other=>other.id!==n.id&&other.module_identity===p.reference&&!sourceWithin(other.id,consumer.id)))continue;
      const ctor=n.resource_constructor;
      if(!ctor||!Array.isArray(ctor.args)||!ctor.kwargs||typeof ctor.kwargs!=='object'||Array.isArray(ctor.kwargs)||
        !ctor.args.every(scalar)||!Object.values(ctor.kwargs).every(scalar))continue;
      const configuration=[...ctor.args.map(format),...Object.entries(ctor.kwargs).map(([k,v])=>k+'='+format(v))].join(', ');
      const description=v.framework_type.split('.').at(-1)+'('+configuration+')';
      // An arbitrarily large constructor is better inspected as source detail.
      if(description.length>100)continue;
      rows.push({rule_version:VERSION,node:n.id,consumer:consumer.id,input:input.id,argument:edge.target_port,edge:copy(edge),
        framework_type:v.framework_type,configuration:copy(ctor),module_identity:n.module_identity,proof:copy(p),symbolic_value:copy(v),
        label:'Module arg '+edge.target_port+': '+description,
        status:open.has(consumer.id)?'source-detail':'attached',
        scope:'One exact source module-reference argument. Passing does not assert invocation, purity, parameter sharing or allocation distinctness. Opening the consumer restores the original read and binding.'});
    }
    return {rule_version:VERSION,rows};
  }
  const api={VERSION,compile};root.SemanticModuleArguments=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
