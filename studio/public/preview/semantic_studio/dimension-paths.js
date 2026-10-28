/* Dimension configuration paths retain their symbolic reads and exact operands.
 * No values, valid shapes, purity or successful execution are inferred. */
(function(root){
'use strict';
const VERSION='dimension-paths/1',flow=e=>['data','alias','interface-binding'].includes(e.kind);
const operators={Add:'add',Sub:'sub',Mult:'mult',FloorDiv:'floordiv',Mod:'mod'};
function compile({ir,configurationUse,unconsumedBindings=true}){
 const by=new Map(ir.nodes.map(n=>[n.id,n])),ins=new Map(),uses=new Map(),cache=new Map(),active=new Set();
 for(const e of ir.edges){if(!ins.has(e.target))ins.set(e.target,[]);ins.get(e.target).push(e);if(!uses.has(e.source))uses.set(e.source,[]);uses.get(e.source).push(e);}
 const symbolic=(root.SemanticSymbolicValues||(typeof require==='function'?require('./symbolic-values.js'):null)).derive(ir);
 const local=n=>n&&n.evidence_status==='static-only'&&!n.mutable&&!n.condition&&!n.identity_display&&!n.observed_calls&&!n.runtime_evidence?.length&&!n.semantic_contracts?.length&&!['opaque','control'].includes(n.kind);
 const safe=n=>{if(!n)return false;const seen=new Set();while(n){if(seen.has(n.id)||!local(n)||n.parent&&!by.has(n.parent))return false;seen.add(n.id);n=by.get(n.parent);}return true;};
 const exact=e=>flow(e)&&!e.condition&&!e.design_route&&!e.iteration&&['source-dependency','static-source'].includes(e.evidence);
 const slot=e=>e.source_port??'out';
 function read(id,port='out',depth=0){
  const key=JSON.stringify([id,port]);if(cache.has(key))return cache.get(key);if(depth>64||active.has(key))return null;active.add(key);
  const n=by.get(id),incoming=ins.get(id)||[],fact=symbolic.get(id);let result=null;
  if(safe(n)&&incoming.every(exact)){
   if(fact?.kind==='tensor-attribute'&&['shape','ndim'].includes(fact.attribute)&&incoming.length===1&&incoming[0].id===fact.edge){
    const scalar=fact.attribute==='ndim'?port==='out':/^-?\d+$/.test(port);
    if(port==='out'||scalar)result={kind:'dimension-read',scalar,roots:[{node:id,slot:port,fact}],dependencies:incoming};
   }else if(['value-alias','interface'].includes(n.kind)&&!n.operator&&incoming.length===1&&
     (n.kind!=='value-alias'||n.slot==null||String(n.slot)===slot(incoming[0]))){
    const e=incoming[0],outer=n.kind==='value-alias'?(n.slot??slot(e)):slot(e),next=outer==='out'?port:port==='out'?outer:outer+'.'+port;
    const v=read(e.source,next,depth+1);if(v)result={kind:'dimension-binding',scalar:v.scalar,roots:v.roots,dependencies:incoming};
   }else if(n.kind==='compute'&&port==='out'&&n.syntax?.type==='BinOp'&&operators[n.syntax.fields?.op?.type]===n.operator){
    const fields=n.syntax.fields,operands=[],expected=[];let valid=true;
    for(const [field,target_port]of [['left','0'],['right','2']]){
     const syntax=fields[field],es=incoming.filter(e=>e.target_port===target_port);
     if(syntax?.operand==='.'+field&&es.length===1){const e=es[0],v=read(e.source,slot(e),depth+1);if(!v?.scalar)valid=false;else operands.push(v);expected.push(e);}
     else if(syntax?.literal_type==='int'&&/^-?\d+$/.test(syntax.literal||'')&&!es.length)continue;
     else valid=false;
    }
    if(valid&&incoming.length===expected.length)result={kind:'dimension-arithmetic',scalar:true,roots:operands.flatMap(v=>v.roots),dependencies:incoming};
   }
  }
  active.delete(key);cache.set(key,result);return result;
 }
 const facts=new Map(ir.nodes.flatMap(n=>{const f=read(n.id);return f?[[n.id,f]]:[];})),configurationOnly=new Set();let changed=true;
 while(changed){changed=false;for(const [id]of facts){const out=uses.get(id)||[];
  if(!configurationOnly.has(id)&&out.length&&out.every(e=>exact(e)&&(configurationUse(e)&&safe(by.get(e.target))||configurationOnly.has(e.target)))){configurationOnly.add(id);changed=true;}
 }}
 // An unused local unpack binding must not turn dimension configuration into
 // a feature branch. License it only beside an already proved configuration
 // use of the same shape read, and only when every remaining use is covered.
 // This changes presentation, not execution: unpack validity remains unproved.
 const unconsumed=new Map(),terminals=new Map();
 if(unconsumedBindings)for(const [id,f]of facts){
  const n=by.get(id),out=uses.get(id)||[];
  if(f.kind!=='dimension-read'||f.scalar||n.attribute_name!=='shape'||!out.some(e=>configurationOnly.has(e.target)))continue;
  const unused=[];let valid=true;
  for(const e of out){
   if(!exact(e)){valid=false;break;}
   if(configurationOnly.has(e.target))continue;
   const target=by.get(e.target),binding=facts.get(e.target),incoming=ins.get(e.target)||[];
   if(!safe(target)||target.kind!=='value-alias'||target.operator||target.parent!==n.parent||
     !/^\d+$/.test(target.slot??'')||target.slot!==slot(e)||e.kind!=='alias'||e.target_port!==target.slot||
     incoming.length!==1||incoming[0]!==e||(uses.get(e.target)||[]).length||
     out.filter(other=>other.kind==='alias'&&slot(other)===slot(e)).length!==1||
     binding?.kind!=='dimension-binding'||!binding.scalar||binding.roots.length!==1||
     binding.roots[0].node!==id||binding.roots[0].slot!==target.slot){valid=false;break;}
   unused.push({node:target.id,slot:target.slot,dependency:{...e},source:target.source||[],uses:[],
    scope:'Unconsumed local source unpack binding; not dead-code elimination. Rank, unpack validity and execution are unproved.'});
  }
  if(!valid||!unused.length)continue;
  unconsumed.set(id,unused);for(const row of unused){configurationOnly.add(row.node);terminals.set(row.node,id);}
 }
 if(unconsumed.size){changed=true;while(changed){changed=false;for(const [id]of facts){const out=uses.get(id)||[];
  if(!configurationOnly.has(id)&&out.length&&out.every(e=>exact(e)&&(configurationUse(e)&&safe(by.get(e.target))||configurationOnly.has(e.target)))){configurationOnly.add(id);changed=true;}
 }}}
 // Only dimension-backed paths activate this policy. The dependency closure
 // also retains shared reads which must remain visible for other feature uses.
 const selected=new Set([...configurationOnly].filter(id=>facts.get(id).roots.length)),proof=new Set(),todo=[...selected];
 for(let i=0;i<todo.length;i++){const id=todo[i];if(proof.has(id))continue;proof.add(id);for(const e of facts.get(id)?.dependencies||[])if(facts.has(e.source))todo.push(e.source);}
 const rows=[...proof].map(id=>{const n=by.get(id),f=facts.get(id);return {rule_version:VERSION,node:id,kind:f.kind,
  basis:'source-tensor-dimensions-and-exact-integer-operands',proof_scope:'full-extracted-graph',configuration_only:configurationOnly.has(id),
  expression:n.source?.[0]?.expression||n.label,roots:f.roots,dependencies:f.dependencies.map(e=>({...e})),uses:(uses.get(id)||[]).map(e=>({...e})),
  ...(unconsumed.has(id)?{unconsumed_bindings:unconsumed.get(id)}:{}),
  ...(terminals.has(id)?{unconsumed_binding_of:terminals.get(id)}:{}),
  value_evaluation:'not-performed',source:n.source||[],scope:'Source Tensor dimension contract and configuration-only uses; concrete dimensions, valid shapes and execution are not asserted.'};});
 return {metadata:new Set([...proof].filter(id=>configurationOnly.has(id))),rows};
}
const api={VERSION,compile};root.SemanticDimensionPaths=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
