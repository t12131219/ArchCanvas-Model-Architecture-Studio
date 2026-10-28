/* Source literal configurations, not inferred tensor shapes or axis meanings. */
(function(root){
  'use strict';
  const VERSION='transform-configurations/1';
  const recipes={transpose:{operator:'transpose',count:[2,2],keys:['dim0','dim1']},
    permute:{operator:'transpose',count:[1,16],keys:['dims']},
    view:{operator:'reshape',count:[1,16],keys:['size']},reshape:{operator:'reshape',count:[1,16],keys:['shape']},
    flatten:{operator:'reshape',count:[1,2],keys:['start_dim','end_dim']},
    squeeze:{operator:'reshape',count:[1,1],keys:['dim']},unsqueeze:{operator:'reshape',count:[1,1],keys:['dim']},
    expand:{operator:'expand',count:[1,16],keys:['size']}};
  const flow=e=>['data','alias','interface-binding'].includes(e.kind);
  function literal(s,depth=0){
    if(depth>2||!s)return undefined;
    if(s.literal_type==='int'&&/^-?\d+$/.test(s.literal||'')){
      const value=Number(s.literal);return Number.isSafeInteger(value)?value:undefined;
    }
    const signed=/^UnaryOp\(op=(USub|UAdd)\(\), operand=Constant\(value=(\d+)\)\)$/.exec(s.literal_expression||'');
    if(signed){const value=Number(signed[2])*(signed[1]==='USub'?-1:1);return Number.isSafeInteger(value)?value:undefined;}
    if(['Tuple','List'].includes(s.type)&&Array.isArray(s.fields?.elts)&&s.fields.elts.length<=16){
      const values=s.fields.elts.map(v=>literal(v,depth+1));return values.every(v=>Number.isSafeInteger(v))?values:undefined;
    }
    return undefined;
  }
  function compile(ir,{operands=false,sequences=true}={}){
    const by=new Map(ir.nodes.map(n=>[n.id,n])),incoming=new Map(),result=new Map();
    for(const e of ir.edges){if(!incoming.has(e.target))incoming.set(e.target,[]);incoming.get(e.target).push(e);}
    const safe=n=>{const seen=new Set();while(n){
      if(seen.has(n.id)||n.evidence_status!=='static-only'||n.mutable||n.condition||n.runtime_evidence?.length||
        n.observed_calls||n.identity_display||['opaque','control'].includes(n.kind))return false;
      seen.add(n.id);if(n.parent&&!by.has(n.parent))return false;n=by.get(n.parent);
    }return true;};
    const format=value=>Array.isArray(value)?'['+value.join(', ')+']':String(value);
    const exact=e=>flow(e)&&!e.condition&&!e.iteration&&!e.design_route&&['source-dependency','static-source'].includes(e.evidence);
    // These are source expressions, not dimension values. In particular a
    // constructor-resolved attribute value cannot replace its source read.
    const binary={Add:['add','+'],Sub:['sub','-'],Mult:['mult','*'],FloorDiv:['floordiv','//'],Mod:['mod','%']};
    function expression(id,port='out',seen=new Set(),budget={remaining:64}){
      if(--budget.remaining<0||seen.size>=24||seen.has(id)||port!=='out')return null;
      const n=by.get(id),es=incoming.get(id)||[];if(!n||!safe(n)||!es.every(exact))return null;
      const visited=new Set([...seen,id]),source=n.source?.length===1?n.source[0].expression:null;
      const reference=typeof source==='string'&&/^([A-Za-z_]\w*)(?:\.[A-Za-z_]\w*)*$/.test(source)?source:
        n.kind==='interface'&&typeof source==='string'?/^([A-Za-z_]\w*)\s*:/.exec(source)?.[1]:null;
      if(reference&&((['interface','value-alias'].includes(n.kind)&&!n.operator&&es.length<=1)||
        n.kind==='state'&&n.operator==='attribute'&&reference.endsWith('.'+n.attribute_name)&&!es.length)){
        // A symbolic name preserves the actual local binding. Do not follow
        // tuple aliases as if they were the complete producer result.
        if(es.some(e=>!by.has(e.source)||!safe(by.get(e.source))))return null;
        return {kind:'source-reference',node:id,port,text:reference,dependencies:es.map(e=>({...e}))};
      }
      if(n.kind!=='compute')return null;
      const fields=n.syntax?.fields,op=binary[fields?.op?.type];
      // Keep a directly constructed sequence as source syntax. Never inline
      // a named list/tuple binding: it may escape or be mutated elsewhere.
      // Each element keeps its exact construction slot and original edge.
      if(sequences&&n.operator==='structure'&&['tuple','list'].includes(n.structure_kind)&&
        n.syntax?.type===(n.structure_kind==='tuple'?'Tuple':'List')&&Array.isArray(fields?.elts)&&fields.elts.length<=16){
        const elements=[],used=[];
        for(let i=0;i<fields.elts.length;i++){
          const syntax=fields.elts[i],edges=es.filter(e=>e.target_port===String(i)),value=literal(syntax);
          if(Number.isSafeInteger(value)&&!edges.length){
            if(--budget.remaining<0)return null;
            elements.push({kind:'literal',value,text:String(value)});
          }else if(syntax?.operand==='.elts:'+i&&edges.length===1){
            const e=edges[0],child=expression(e.source,e.source_port??'out',visited,budget);
            if(!child)return null;elements.push(child);used.push(e);
          }else return null;
        }
        if(es.length!==used.length)return null;
        const tuple=n.structure_kind==='tuple',body=elements.map(e=>e.text).join(', ')+(tuple&&elements.length===1?',':'');
        return {kind:'source-sequence',node:id,port,sequence_kind:n.structure_kind,elements,
          text:(tuple?'(':'[')+body+(tuple?')':']'),dependencies:used.map(e=>({...e}))};
      }
      if(n.syntax?.type==='BinOp'&&op?.[0]===n.operator){
        const children=[],used=[];
        for(const [field,slot]of [['left','0'],['right','2']]){
          const syntax=fields[field],edges=es.filter(e=>e.target_port===slot),value=literal(syntax);
          if(value!==undefined&&!Array.isArray(value)&&!edges.length)children.push({kind:'literal',value,text:String(value)});
          else if(syntax?.operand==='.'+field&&edges.length===1){const e=edges[0],child=expression(e.source,e.source_port??'out',visited,budget);if(!child)return null;children.push(child);used.push(e);}
          else return null;
        }
        if(es.length!==used.length)return null;
        return {kind:'source-arithmetic',node:id,port,operator:op[0],operands:children,
          text:'('+children[0].text+' '+op[1]+' '+children[1].text+')',dependencies:used.map(e=>({...e}))};
      }
      // The extracted Subscript preserves the actual base edge and literal
      // selector. Display it without asserting a tensor rank or dimension role.
      if(n.operator==='getitem'&&n.syntax?.type==='Subscript'&&fields?.value?.operand==='.value'&&es.length===1&&es[0].target_port==='value'){
        const value=literal(fields.slice),e=es[0],base=expression(e.source,e.source_port??'out',visited,budget);
        if(Number.isSafeInteger(value)&&base)return {kind:'source-subscript',node:id,port,base,index:value,
          text:base.text+'['+value+']',dependencies:[{...e}]};
      }
      if(n.operator==='attribute'&&n.syntax?.type==='Attribute'&&fields?.value?.operand==='.value'&&
        /^[A-Za-z_]\w*$/.test(fields.attr||'')&&fields.attr===n.attribute_name&&es.length===1&&es[0].target_port==='in'){
        const e=es[0],base=expression(e.source,e.source_port??'out',visited,budget);
        if(base)return {kind:'source-attribute',node:id,port,base,attribute:fields.attr,
          text:base.text+'.'+fields.attr,dependencies:[{...e}]};
      }
      return null;
    }
    for(const n of ir.nodes){
      const name=n.function_target?.split('.').at(-1),recipe=Object.hasOwn(recipes,name)?recipes[name]:null,s=n.syntax?.fields;
      if(!recipe||n.kind!=='compute'||n.operator!==recipe.operator||n.syntax?.type!=='Call'||!safe(n)||
        !Array.isArray(s?.args)||!Array.isArray(s.keywords)||!Array.isArray(n.arguments?.args)||!n.arguments.kwargs)continue;
      const edges=incoming.get(n.id)||[],method=edges.some(e=>e.target_port==='receiver');
      // A chained expression beginning with a framework call is still a
      // receiver method. The actual input port determines the call convention.
      const functional=!method&&!!n.source_framework_function&&n.source_framework_function===n.function_target&&
        /^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$/.test(n.function_target);
      if(!method&&!functional)continue;
      const offset=functional?1:0,receiver=functional?'arg:0':'receiver';
      if((!operands&&edges.length!==1)||edges.filter(e=>e.target_port===receiver&&flow(e)&&!e.condition&&!e.iteration).length!==1||
        edges.some(e=>e.condition||e.iteration||e.design_route||!flow(e)||!['source-dependency','static-source'].includes(e.evidence)))continue;
      const args=s.args.slice(offset),values=n.arguments.args.slice(offset),slots=[];
      if(s.args.length!==n.arguments.args.length||args.length>recipe.count[1]||s.keywords.length!==Object.keys(n.arguments.kwargs).length)continue;
      let valid=true;
      for(let i=0;i<args.length;i++){
        const value=literal(args[i]),port='arg:'+(i+offset);
        const bound=edges.filter(e=>e.target_port===port);
        if(operands&&args[i]?.operand==='.args:'+(i+offset)&&bound.length===1){
          const edge=bound[0],expr=expression(edge.source,edge.source_port??'out');
          if(!expr)valid=false;slots.push({port,syntax:args[i],expression:expr,binding:{...edge}});
        }else{
          if(value===undefined||JSON.stringify(value)!==JSON.stringify(values[i])||bound.length)valid=false;
          slots.push({port,syntax:args[i],value});
        }
      }
      const keys=new Set();
      for(const k of s.keywords){
        const key=k.fields?.arg,value=literal(k.fields?.value),port='kw:'+key;
        if(!recipe.keys.includes(key)||keys.has(key)||recipe.keys.indexOf(key)<args.length||!Object.hasOwn(n.arguments.kwargs,key))valid=false;
        const bound=edges.filter(e=>e.target_port===port),syntax=k.fields?.value;
        if(operands&&syntax?.operand==='.keywords:'+keys.size+'.value'&&bound.length===1){
          const edge=bound[0],expr=expression(edge.source,edge.source_port??'out');
          if(!expr)valid=false;slots.push({port,syntax,expression:expr,binding:{...edge}});
        }else{
          if(value===undefined||JSON.stringify(value)!==JSON.stringify(n.arguments.kwargs[key])||bound.length)valid=false;
          slots.push({port,syntax,value});
        }
        keys.add(key);
      }
      if(!valid||slots.length<recipe.count[0]||slots.length>recipe.count[1]||
        recipe.count[0]===2&&slots.length!==2||edges.length!==1+slots.filter(r=>r.binding).length)continue;
      const bound=slots.some(r=>r.binding),text=name+'('+slots.map(r=>(r.port.startsWith('kw:')?r.port.slice(3)+'=':'')+(r.binding?r.expression.text:format(r.value))).join(', ')+')';
      result.set(n.id,{rule_version:bound?'transform-operands/1':VERSION,node:n.id,operator:n.operator,method:name,slots,text,
        receiver_edge:edges.find(e=>e.target_port===receiver).id,
        scope:bound?'Exact source argument expressions and bindings; symbolic references are not evaluated. No integer type, tensor rank, valid shape, axis role, value equivalence or execution assertion.':
          'Exact source literal call configuration; no tensor rank, valid shape, axis role, value equivalence or execution assertion.'});
    }
    return result;
  }
  const api={VERSION,compile};root.SemanticTransformConfigurations=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
