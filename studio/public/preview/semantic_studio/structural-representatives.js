/* Recheck local structure against current facts before sharing a panel.
 * A structural receipt never fulfills concrete instance boundaries/identities. */
(function(root){
'use strict';
const stable=x=>JSON.stringify(x,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
const equal=(a,b)=>stable(a)===stable(b),flow=new Set(['data','alias','interface-binding']);
const Symbolic=root.SemanticSymbolicValues||(typeof require==='function'?require('./symbolic-values.js'):null);
function inspect(ir){
  const by=new Map(ir.nodes.map(n=>[n.id,n])),children=new Map(),ins=new Map();
  for(const n of ir.nodes){if(!children.has(n.parent))children.set(n.parent,[]);children.get(n.parent).push(n.id);}
  for(const e of ir.edges){if(!ins.has(e.target))ins.set(e.target,[]);ins.get(e.target).push(e);}
  const symbolic=new Map([...Symbolic.derive(ir)].filter(([id,c])=>equal(by.get(id).symbolic_value,c)));
  const closure=id=>{const s=new Set(),todo=[id];while(todo.length){const id=todo.pop();if(s.has(id))continue;s.add(id);todo.push(...children.get(id)||[]);}return s;};
  const clean=v=>{if(v&&typeof v==='object'){if(!Array.isArray(v)&&'unresolved'in v)throw Error('unresolved configuration');for(const child of Object.values(v))clean(child);}return v??null;};
  function instance(root){
    const members=closure(root),atoms=ir.nodes.filter(n=>members.has(n.id)&&(!['composite','interface','value-alias'].includes(n.kind)||n.return_selection||n.source_constant_input));
    for(const n of ir.nodes.filter(n=>members.has(n.id))){
      if(n.kind==='opaque'||n.mutable)throw Error('unknown or mutable computation');
      if(n.kind==='control'&&!['if','if-expression'].includes(n.operator)&&!Symbolic.exceptionFor(n,by,ins))throw Error('unsupported control or nested iteration');
      if(n.kind==='value-alias'&&n.operator&&n.operator!=='phi')throw Error('unresolved value binding');
      if(['state','buffer'].includes(n.kind))clean(symbolic.has(n.id)?Symbolic.valueFor(n,symbolic):n.value??{unresolved:true});
    }
    if(ir.edges.some(e=>e.kind==='state-write'&&(members.has(e.source)||members.has(e.target))))throw Error('state write');
    atoms.push(...ir.nodes.filter(n=>members.has(n.id)&&n.kind==='value-alias'&&n.operator==='phi'));
    const atomIds=new Set(atoms.map(n=>n.id)),local=new Map(),external=new Map(),objects=new Map(),records=[],active=new Set();
    function resolve(at,port='out',seen=new Set()){
      const key=stable([at,port]);if(seen.has(key))throw Error('cyclic binding');seen.add(key);
      if(!members.has(at)){if(!external.has(key))external.set(key,external.size);return ['external',external.get(key)];}
      const n=by.get(at),es=(ins.get(at)||[]).filter(e=>flow.has(e.kind));
      if(['interface','value-alias'].includes(n.kind)&&!n.operator&&es.length===1&&!es[0].condition){
        const e=es[0];if(n.kind==='value-alias'&&n.slot!=null&&String(n.slot)!==String(e.source_port))throw Error('unresolved slot');
        const outer=e.source_port??'out';return resolve(e.source,outer==='out'?port:port==='out'?outer:outer+'.'+port,seen);
      }
      if(!atomIds.has(at))throw Error('incomplete interface');return ['local',visit(at),port];
    }
    const condition=c=>c?{branch:resolve(c.branch),outcome:c.outcome}:null;
    const binding=e=>({kind:flow.has(e.kind)?'value':e.kind,port:e.target_port??'in',source:resolve(e.source,e.source_port??'out'),condition:condition(e.condition)});
    function visit(at){
      if(local.has(at))return local.get(at);if(active.has(at))throw Error('cyclic graph');active.add(at);
      const n=by.get(at);let target=n.function_target??null;
      if(target&&!target.startsWith('torch.')&&!target.startsWith('math.')){
        const scalar=n.operator==='scalar-cast'&&n.source_scalar_cast===target&&['float','int','bool'].includes(target);
        if(!scalar&&!(ins.get(at)||[]).some(e=>e.target_port==='receiver'))throw Error('unresolved function');if(!scalar)target='receiver.'+target.split('.').at(-1);
      }
      if(n.kind==='compute'&&!n.syntax)throw Error('missing syntax');
      const ports=new Set((ins.get(at)||[]).filter(e=>flow.has(e.kind)).map(e=>e.target_port)),args={};
      for(const [kind,values]of Object.entries(n.arguments||{}))args[kind]=Object.fromEntries(Object.entries(values).map(([k,v])=>{const port=(kind==='args'?'arg:':'kw:')+k;return[k,ports.has(port)?{binding:port}:clean(v)];}));
      const op={kind:n.kind,operator:n.operator??null,framework_type:n.framework_type??null,function:target,constructor:clean(Object.hasOwn(n,'constructor')?n.constructor:null),arguments:args,syntax:n.syntax??null,value:clean(Symbolic.valueFor(n,symbolic)),structure_kind:n.structure_kind??null};
      if(n.operator==='exception-exit')op.exception_exit=Symbolic.exceptionFor(n,by,ins);
      if(n.source_constant_input){if(n.role!=='input'||(ins.get(at)||[]).length)throw Error('invalid invocation constant');op.invocation_constant=clean(n.source_constant_input);}
      if(n.return_selection){
        const c=n.return_selection,choices=(ins.get(at)||[]).filter(e=>e.source===c.selected&&e.kind==='interface-binding');if(choices.length!==1)throw Error('invalid normal return selection');
        const inputs=ir.nodes.filter(v=>v.parent===n.parent&&v.kind==='interface'&&v.role==='input'),constants=Object.fromEntries(inputs.flatMap((v,i)=>Object.hasOwn(c.call_constants,v.slot)?[[String(i),c.call_constants[v.slot]]]:[]));
        op.normal_returns={constants:clean(constants),selected_input:choices[0].target_port??'in',scope:c.scope};
      }
      if(n.module_resource){op.resource_type=n.resource_framework_type;op.resource_constructor=clean(n.resource_constructor);}
      if((n.framework_type&&n.kind==='compute')||n.module_resource){
        const b=n.module_binding||n.module_resource_binding;if(b?.status!=='proved'||b.reference!==n.module_identity)throw Error('unresolved module selection');
        if(!objects.has(b.reference))objects.set(b.reference,objects.size);op.object_selection=objects.get(b.reference);
      }
      const scopes=[];let parent=n.parent;while(members.has(parent)){const c=by.get(parent).condition;if(c)scopes.push(condition(c));parent=by.get(parent).parent;}
      const ordered=(ins.get(at)||[]).slice().sort((a,b)=>{const x=[a.kind,a.target_port??'in'],y=[b.kind,b.target_port??'in'];return x[0]<y[0]?-1:x[0]>y[0]?1:x[1]<y[1]?-1:x[1]>y[1]?1:0;});
      const bindings=ordered.map(binding),i=records.length;local.set(at,i);records.push({operation:op,bindings,conditions:scopes});active.delete(at);return i;
    }
    atoms.forEach(n=>visit(n.id));
    const outputs=ir.edges.filter(e=>members.has(e.source)&&!members.has(e.target)).map(e=>({source:resolve(e.source,e.source_port??'out'),kind:flow.has(e.kind)?'value':e.kind,condition:condition(e.condition)}));
    if(!records.length)throw Error('no modeled operations');
    const structure={operations:records,outputs,inputs:external.size};
    return {instance:root,status:'proved',structure,node_mapping:Object.fromEntries(local),members:[...members],boundary_edges:ir.edges.filter(e=>members.has(e.source)!==members.has(e.target)).map(e=>e.id),
      edge_keys:new Map(ir.edges.filter(e=>local.has(e.target)).map(e=>[e.id,stable({target:local.get(e.target),...binding(e)})]))};
  }
  const sequences=[],diagnostics=[];
  for(const sequence of ir.nodes.filter(n=>n.repeat_contract?.structure)){
    const c=sequence.repeat_contract,s=c.structure,ids=(children.get(sequence.id)||[]).filter(id=>by.get(id).semantic_type==='repeat-instance');
    try{
      if(s.rule_version!=='local-structure/1'||s.instances.length!==ids.length||c.count!==ids.length||!equal(ids.map(id=>by.get(id).repeat_index),ids.map((_,i)=>i))||!equal(c.instances,ids.map(id=>by.get(id).module_identity)))throw Error('invalid sequence cardinality');
      const rows=ids.map((id,index)=>{try{return {...instance(id),index};}catch(e){return{instance:id,index,status:'unresolved',reason:e.message};}}),groups=[];
      for(const row of rows){
        const recorded=s.instances.find(r=>r.instance===row.instance);
        if(recorded?.status!==row.status||recorded.index!==row.index)throw Error('stale structural status');
        if(row.status==='proved'){
          for(const key of ['structure','node_mapping','boundary_edges'])if(!equal(recorded[key],row[key])){
            const error=Error('stale structural facts: '+key);error.comparison={recorded:recorded[key],actual:row[key]};throw error;
          }
          if(!equal([...recorded.members].sort(),[...row.members].sort()))throw Error('stale structural members');
        }
        let group=row.status==='proved'?groups.find(g=>g.status==='proved'&&equal(g.structure,row.structure)):null;
        if(!group){group={representative:row.instance,indices:[],instances:[],status:row.status,structure:row.structure};groups.push(group);}
        group.indices.push(row.index);group.instances.push(row.instance);
      }
      if(groups.length!==s.groups.length||groups.some((g,i)=>!equal({representative:g.representative,indices:g.indices,instances:g.instances,status:g.status},{representative:s.groups[i].representative,indices:s.groups[i].indices,instances:s.groups[i].instances,status:s.groups[i].status})))throw Error('stale structural groups');
      sequences.push({id:sequence.id,groups,rows,closure});
    }catch(e){diagnostics.push({sequence:sequence.id,reason:e.message,...(e.comparison?{comparison:e.comparison}:{})});}
  }
  return {sequences,diagnostics,by};
}
function plan(ir,goals){
  const checked=inspect(ir),mappings=new Map(),pages=[],boundaries=[];
  for(const seq of checked.sequences){
    for(const row of seq.rows){
      const members=seq.closure(row.instance);
      for(const e of ir.edges.filter(e=>members.has(e.source)!==members.has(e.target)))boundaries.push({id:'goal:instance-boundary:'+row.instance+':'+e.id,kind:'instance-boundary',focus_node:row.instance,core:[],edges:[e.id],priority:3,expression:'role-relationships',instance:row.instance,sequence:seq.id});
    }
    for(const [groupIndex,group]of seq.groups.entries()){
    if(group.status!=='proved')continue;
    const rep=seq.rows.find(r=>r.instance===group.representative),repBySlot=new Map(Object.entries(rep.node_mapping).map(([id,slot])=>[slot,id]));
    pages.push({id:seq.id,group:groupIndex,instance:rep.instance,label:'Structure · source positions '+group.indices.map(i=>i+1).join(', ')});
    for(const row of seq.rows.filter(r=>group.instances.includes(r.instance))){
      if(row.instance===rep.instance)continue;
      const nodes=Object.fromEntries(Object.entries(row.node_mapping).map(([id,slot])=>[id,repBySlot.get(slot)])),repEdges=new Map();
      for(const [id,key]of rep.edge_keys){if(!repEdges.has(key))repEdges.set(key,[]);repEdges.get(key).push(id);}
      const edges={};for(const [id,key]of row.edge_keys){const candidates=repEdges.get(key)||[];if(candidates.length===1)edges[id]=candidates[0];}
      for(const goal of goals){
        if(goal.identity||goal.kind==='external-interface'||!goal.core.length||!goal.core.every(id=>nodes[id])||!goal.edges.every(id=>edges[id]))continue;
        const core=goal.core.map(id=>nodes[id]).sort(),mappedEdges=goal.edges.map(id=>edges[id]).sort();
        const target=goals.find(g=>!g.identity&&g.kind===goal.kind&&g.expression===goal.expression&&equal([...g.core].sort(),core)&&equal([...g.edges].sort(),mappedEdges));
        if(!target)continue;
        mappings.set(goal.id,{goal:goal.id,representative_goal:target.id,sequence:seq.id,group:groupIndex,instance:row.instance,representative:rep.instance,source_positions:group.indices.map(i=>i+1),
          node_map:Object.fromEntries(goal.core.map(id=>[id,nodes[id]])),edge_map:Object.fromEntries(goal.edges.map(id=>[id,edges[id]])),scope:'local structure only; concrete boundary and identity goals require direct paths'});
      }
    }
  }}
  // Retain both sides of an inter-instance edge as separate obligations.
  return {...checked,mappings,pages,boundaries};
}
function coverage(planning,out){
  const rep=out.graph.publication.representative,group=rep?.structural_group;
  if(!group)return[];
  const n=out.graph.nodes.find(n=>n.id===rep.instance),caption=(n?.paper?.captions||[]).join(' ').replace(/\s/g,'');
  if(!caption.includes('structureonly')||!caption.includes('sourcepositions'+group.indices.map(i=>i+1).join(',')))return[];
  const direct=new Map(out.graph.expression_coverage.filter(c=>c.status==='fulfilled').map(c=>[c.goal,c]));
  return [...planning.mappings.values()].filter(m=>m.sequence===rep.sequence&&m.group===group.group&&m.representative===rep.instance&&direct.has(m.representative_goal))
    .map(m=>({...m,status:'fulfilled',method:'structural-representative',visible_edges:direct.get(m.representative_goal).visible_edges}));
}
const api={inspect,plan,coverage};root.SemanticStructuralRepresentatives=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
