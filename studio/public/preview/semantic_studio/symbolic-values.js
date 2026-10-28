/* Recompute source symbolic-read contracts independently of stored receipts. */
(function(root){
'use strict';
const version='source-symbolic-value/1',flow=new Set(['data','alias','interface-binding']);
const namespaces=new Set(['torch','torch.nn','torch.nn.functional','math']);
const constants=new Set('bool uint8 int8 int16 short int32 int int64 long float16 half float32 float float64 double bfloat16 complex64 cfloat complex128 cdouble'.split(' ').map(s=>'torch.'+s));
const attrs=new Set(['shape','device','dtype','ndim']);
const tensorModules=new Set('Linear Conv1d Conv2d Conv3d Embedding LayerNorm BatchNorm1d BatchNorm2d GroupNorm Dropout ReLU GELU Sigmoid Tanh Identity Flatten Softmax LogSoftmax'.split(' '));
const tensorOps=new Set('reshape transpose copy detach device-cast dtype-cast activation softmax normalization mask nan-guard expand linear convolution pooling matmul concat stack create random sqrt exp pow rsqrt abs sin cos clamp'.split(' '));
const exceptions=new Set(['ValueError','TypeError','RuntimeError','NotImplementedError','IndexError','KeyError','AssertionError']);
function derive(ir){
 const by=new Map(ir.nodes.map(n=>[n.id,n])),ins=new Map(),writes=new Set(ir.edges.filter(e=>e.kind==='state-write').map(e=>e.target));
 for(const e of ir.edges){if(!ins.has(e.target))ins.set(e.target,[]);ins.get(e.target).push(e);}
 const facts=new Map(),tensor=new Map(),active=new Set();let barrier=null;
 function tensorContract(at){
  if(tensor.has(at))return tensor.get(at);if(active.has(at)||!by.has(at))return false;active.add(at);
  const n=by.get(at),es=(ins.get(at)||[]).filter(e=>flow.has(e.kind));let result=n.source_tensor_annotation==='torch.Tensor';
  if(!result&&['interface','value-alias'].includes(n.kind)&&!n.operator&&es.length===1){
   const e=es[0];result=(e.source_port??'out')==='out'&&n.slot==null&&tensorContract(e.source);
   if(n.kind==='interface'&&(e.source_port??'out')==='out')result=tensorContract(e.source);
  }
  if(n.operator==='phi'&&es.length===2&&new Set(es.map(e=>e.target_port)).size===2&&es.every(e=>['true','false'].includes(e.target_port)))result=es.every(e=>(e.source_port??'out')==='out'&&tensorContract(e.source));
  if(n.kind==='compute'&&!n.mutable){
   const f=n.framework_type||'';
   if(n.source_framework_module===f&&f.startsWith('torch.nn.')&&tensorModules.has(f.split('.').at(-1)))result=n.module_binding?.status==='proved';
   else if(n.source_framework_function===n.function_target&&n.function_target?.startsWith('torch.')&&tensorOps.has(n.operator))result=true;
   else if(es.some(e=>e.target_port==='receiver'&&tensorContract(e.source))&&tensorOps.has(n.operator))result=true;
   else if(['add','sub','mult','div'].includes(n.operator))result=es.some(e=>tensorContract(e.source));
  }
  active.delete(at);tensor.set(at,result);return result;
 }
 for(const n of ir.nodes){
  if(!barrier){
   const imported=n.framework_value_import;
   if(namespaces.has(imported)||constants.has(imported))facts.set(n.id,{rule_version:version,kind:'framework-symbol',symbol:imported,scope:'unshadowed source import in modeled prefix; no monkey-patching claim'});
   else if(n.module_resource&&n.resource_framework_type?.startsWith('torch.nn.')){
    const b=n.module_resource_binding;if(b?.status==='proved'&&b.reference===n.module_identity)facts.set(n.id,{rule_version:version,kind:'module-resource',reference:b.reference,framework_type:n.resource_framework_type,scope:'constructor resource selected at this source read; not a call or parameter-stability claim'});
   }else if(n.operator==='attribute'&&n.kind==='compute'){
    const es=(ins.get(n.id)||[]).filter(e=>flow.has(e.kind)),attr=n.attribute_name;
    if(es.length===1&&n.syntax?.type==='Attribute'&&n.syntax.fields?.attr===attr){
     const e=es[0];let receiver=facts.get(e.source)||{};
     const imported=by.get(e.source)?.framework_value_import;if(namespaces.has(imported))receiver={kind:'framework-symbol',symbol:imported};
     const symbol=(receiver.symbol||'')+'.'+attr;
     if(receiver.kind==='framework-symbol'&&constants.has(symbol))facts.set(n.id,{rule_version:version,kind:'framework-attribute',symbol,receiver:e.source,edge:e.id,attribute:attr,scope:'framework constant binding; no tensor value claim'});
     else if(attrs.has(attr)&&(e.source_port??'out')==='out'&&tensorContract(e.source))facts.set(n.id,{rule_version:version,kind:'tensor-attribute',receiver:e.source,edge:e.id,attribute:attr,scope:'source Tensor contract only; annotation is not runtime validation; actual value unresolved'});
    }
   }
  }
  if(n.kind==='opaque'||n.mutable||writes.has(n.id)||(n.kind==='control'&&n.operator==='loop'))barrier=barrier||n.id;
 }
 return facts;
}
function valueFor(n,facts){
 const f=facts.get(n.id);if(!f)return n.value??null;
 if(['framework-symbol','framework-attribute'].includes(f.kind))return{framework_symbol:f.symbol};
 if(f.kind==='module-resource')return{module_resource:f.framework_type};
 return{derived_attribute:f.attribute,basis:'source Tensor contract'};
}
function exceptionFor(n,by,ins){
 const c=n.exception_signature;if(n.operator!=='exception-exit'||!c||!exceptions.has(c.builtin)||c.scope!=='source exceptional exit; reachability and execution not asserted'||c.syntax?.type!=='Call'||c.syntax.fields?.keywords?.length)return null;
 const args=c.syntax.fields.args,es=ins.get(n.id)||[];if(!Array.isArray(args))return null;
 const expressions=args.map((v,i)=>Object.hasOwn(v,'literal')?v.literal:es.find(e=>e.kind==='control'&&e.target_port===String(i))?.source).map((v,i)=>Object.hasOwn(args[i],'literal')?v:by.get(v)?.source?.[0]?.expression);
 if(expressions.some(v=>typeof v!=='string')||n.exception_expression!==c.builtin+'('+expressions.join(', ')+')')return null;
 return c;
}
const api={derive,valueFor,exceptionFor};root.SemanticSymbolicValues=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
