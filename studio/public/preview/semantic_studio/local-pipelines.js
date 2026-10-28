/* A folded source helper can describe its modeled dependency path. This is a
 * presentation form, not fusion, purity, scheduling or a new family contract. */
(function(root){
  'use strict';
  const VERSION='local-pipelines/6',flow=e=>['data','alias','interface-binding'].includes(e.kind);
  function compile({ir,plan,bindings,metadata,configurationUses,sourceReads=false}){
    const by=new Map(plan.nodes.map(n=>[n.id,n])),canonical=new Map(ir.nodes.map(n=>[n.id,n])),children=new Map(),result=new Map();
    for(const n of plan.nodes){if(!children.has(n.parent))children.set(n.parent,[]);children.get(n.parent).push(n.id);}
    const closure=id=>{const todo=[id];for(let i=0;i<todo.length;i++)todo.push(...children.get(todo[i])||[]);return todo;};
    // Focus panels deliberately keep their boundary interfaces visible. A
    // canonical single-input interface/alias still proves its value binding;
    // that fact must not depend on whether the display contracts the interface.
    const proofBindings=new Map(bindings),ins=new Map();
    for(const e of ir.edges){if(!ins.has(e.target))ins.set(e.target,[]);ins.get(e.target).push(e);}
    for(const n of ir.nodes){const es=ins.get(n.id)||[];if(['interface','value-alias'].includes(n.kind)&&!n.operator&&
      es.length===1&&flow(es[0])&&!es[0].condition)proofBindings.set(n.id,{...es[0],
        source_port:n.kind==='value-alias'?n.slot??es[0].source_port:es[0].source_port});}
    const resolve=(id,port)=>{const seen=new Set();while(proofBindings.has(id)&&!seen.has(id)){seen.add(id);const e=proofBindings.get(id);id=e.source;const outer=e.source_port??'out';port=outer==='out'?port:port==='out'?outer:outer+'.'+port;}return {node:id,slot:port};};
    const guarded=n=>n.evidence_status==='runtime-only'||['opaque','control'].includes(n.kind)||n.mutable||n.condition||n.identity_display||n.observed_calls||n.state_interface||n.semantic_contracts?.length||n.repeat_contract||n.iteration||n.runtime_evidence?.length;
    for(const owner of plan.nodes){
      const identity=sourceReads&&owner.identity_display?.kind==='same-object-calls'?owner.identity_display:null;
      if(!owner.parent||!['source-function','source-module'].includes(owner.semantic_type)||guarded(identity?{...owner,identity_display:null}:owner))continue;
      const ids=closure(owner.id),inside=new Set(ids),members=ids.slice(1).map(id=>by.get(id));
      // Contiguous topological partitions are display frames, not source or
      // semantic boundaries. Inspect their full canonical contents and exact
      // cuts before looking through them. No other synthetic region is erased.
      const partitions=members.filter(n=>!canonical.has(n.id));
      if(!members.length||members.some(guarded)||partitions.some(n=>{
        if(n.kind!=='composite'||!n.presentation_only||!['structural-region',...(sourceReads?['operand-expression']:[])].includes(n.semantic_type))return true;
        const actual=closure(n.id).filter(id=>canonical.has(id)),set=new Set(actual);
        const cuts=ir.edges.filter(e=>set.has(e.source)!==set.has(e.target));
        const ports=cuts.map(e=>({id:e.id,direction:set.has(e.source)?'output':'input',source:e.source,source_port:e.source_port,target:e.target,target_port:e.target_port,evidence:e.evidence}));
        return actual.length!==n.canonical_members?.length||new Set(n.canonical_members).size!==actual.length||n.canonical_members.some(id=>!set.has(id))||
          JSON.stringify(n.boundary_ports)!==JSON.stringify(n.semantic_type==='operand-expression'?ports:cuts);
      }))continue;
      // Source refactoring alone need not break a proved value path. Nested
      // enclosures retain their own original cuts and provenance; a grouping,
      // certificate, effect or identity boundary cannot authorize composition.
      const boundaries=[owner,...members.filter(n=>n.kind==='composite'&&canonical.has(n.id))];
      if(boundaries.slice(1).some(n=>!['source-function','source-module'].includes(n.semantic_type)||
        ir.edges.some(e=>e.source===n.id||e.target===n.id)))continue;
      const auxiliary=members.filter(n=>n.symbolic_value?.kind==='tensor-attribute'),aux=new Set(auxiliary.map(n=>n.id));
      const steps=members.filter(n=>n.kind==='compute'&&!aux.has(n.id)&&!metadata.has(n.id));
      if(steps.length<2||steps.some(n=>!n.operator&&!n.framework_type))continue;
      // Match the compact projection's read-only parameter attachment policy.
      // Do not absorb writes, incoming values, shared escapes or identity facts.
      const parameters=members.filter(n=>n.kind==='parameter'&&!metadata.has(n.id)),resources=new Set(parameters.map(n=>n.id));
      if(parameters.some(n=>ir.edges.some(e=>e.target===n.id)||!ir.edges.some(e=>e.source===n.id)||
        ir.edges.some(e=>e.source===n.id&&(!['data','parameter-read'].includes(e.kind)||!steps.some(n=>n.id===e.target)))))continue;
      // This is a source read occurrence, not an immutable tensor, registered
      // buffer identity, or a state-update contract. Keep the spelling and all
      // consumers. A write, escaping read or incoming state binding rejects it.
      const reads=members.filter(n=>['state','buffer'].includes(n.kind)&&!metadata.has(n.id)),readIds=new Set(reads.map(n=>n.id));
      if(identity&&!reads.length)continue;
      if(reads.length&&(!sourceReads||reads.some(n=>n.evidence_status!=='static-only'||n.operator!=='attribute'||
        typeof n.attribute_name!=='string'||n.source?.length!==1||n.source[0].expression!=='self.'+n.attribute_name||
        (ins.get(n.id)||[]).length||!ir.edges.some(e=>e.source===n.id)||
        ir.edges.some(e=>e.source===n.id&&(!flow(e)||e.source_port!=='out'||!steps.some(s=>s.id===e.target))))))continue;
      if(members.some(n=>!['compute','interface','value-alias','parameter','state','buffer','composite'].includes(n.kind)||
        ['state','buffer'].includes(n.kind)&&!metadata.has(n.id)&&!readIds.has(n.id)))continue;
      const active=new Set(steps.map(n=>n.id)),edges=ir.edges.filter(e=>inside.has(e.source)||inside.has(e.target));
      if(edges.some(e=>!flow(e)&&!(e.kind==='parameter-read'&&resources.has(e.source))||e.condition||e.design_route||e.iteration))continue;
      const adj=new Map(steps.map(n=>[n.id,new Set()])),incoming=new Map(steps.map(n=>[n.id,[]])),traces=[];
      let valid=true;
      for(const e of edges){
        const from=resolve(e.source,e.source_port??'out'),to=by.get(e.target);
        // Bindings are retained as proof traces, not new shortcut edges.
        if(active.has(e.target)){
          const trace={edge:e.id,producer:from.node,source_port:from.slot,target:e.target,target_port:e.target_port,
            kind:aux.has(from.node)?'symbolic-read':readIds.has(from.node)?'source-read':resources.has(from.node)?'parameter-read':metadata.has(from.node)?'configuration':'value'};traces.push(trace);
          if(aux.has(from.node)&&!configurationUses.has(e.id))valid=false;
          if(active.has(from.node)){adj.get(from.node).add(e.target);incoming.get(e.target).push(trace);}
        }
        if(aux.has(e.target)&&(!active.has(from.node)&&inside.has(from.node)&&by.get(from.node)?.kind!=='interface'))valid=false;
      }
      if(steps.some(n=>{const ports=traces.filter(t=>t.target===n.id).map(t=>t.target_port);return ports.length!==new Set(ports).size;}))valid=false;
      if(!valid)continue;
      // Internal reuse requires references, never recursive inlining of the
      // producer. Multiple operand uses count once for topological indegree,
      // while every use and its exact result/operand slot stays in the proof.
      const dag=!!reads.length||steps.some(n=>adj.get(n.id).size>1||new Set(incoming.get(n.id).map(t=>t.producer)).size!==incoming.get(n.id).length);
      const starts=steps.filter(n=>!incoming.get(n.id).length),sinks=steps.filter(n=>!adj.get(n.id).size);
      if(!starts.length||sinks.length!==1)continue;
      // A tuple pack is not a single semantic result: its externally selectable
      // components need a dedicated output presentation. Internal tuple packs
      // remain legal when a later operation consumes their exact result slots.
      if(dag&&sinks[0].operator==='structure')continue;
      const ordered=[],degree=new Map(steps.map(n=>[n.id,new Set(incoming.get(n.id).map(t=>t.producer)).size])),todo=starts.map(n=>n.id);
      if(dag)todo.sort();
      for(let i=0;i<todo.length;i++){const at=todo[i];ordered.push(at);for(const next of adj.get(at)){degree.set(next,degree.get(next)-1);if(!degree.get(next))todo.push(next);}if(dag)todo.splice(i+1,todo.length-i-1,...todo.slice(i+1).sort());}
      if(ordered.length!==steps.length)continue;
      const tree=!dag&&steps.some(n=>incoming.get(n.id).length>1);
      // Long paths have linear receipts. Trees and reused-result DAGs retain
      // their bounded formula policy, rather than being silently serialized.
      if(steps.length>6&&(dag||tree))continue;
      // An intermediate result escaping the helper requires its own interface;
      // a single output-path summary would hide the distinguishing connection.
      const cuts=edges.filter(e=>inside.has(e.source)!==inside.has(e.target));
      if(cuts.some(e=>inside.has(e.source)&&resolve(e.source,e.source_port??'out').node!==ordered.at(-1)))continue;
      const outputs=members.filter(n=>n.kind==='interface'&&n.role==='output'&&n.parent===owner.id);
      if(!outputs.length||outputs.some(n=>{const es=ir.edges.filter(e=>e.target===n.id);return es.length!==1||resolve(es[0].source,es[0].source_port??'out').node!==ordered.at(-1);}))continue;
      const operations=ordered.map(id=>{const n=by.get(id),framework=n.source_framework_function&&n.source_framework_function===n.function_target;
        return {node:id,operator:n.operator,framework_type:n.framework_type||null,
          label:n.framework_type?.split('.').at(-1)||(framework?n.function_target.split('.').at(-1):n.operator),
          label_basis:n.framework_type?'framework-type':framework?'source-framework-function':'operator'};});
      const runs=[];
      if(operations.length>6)for(const o of operations){
        const previous=runs.at(-1),signature=JSON.stringify([o.operator,o.framework_type,o.label,o.label_basis]);
        if(previous?.signature===signature)previous.operations.push(o.node);
        else runs.push({signature,label:o.label,operations:[o.node]});
      }
      const pathDisplay=runs.length?{schema:'dependency-path-display/1',runs:runs.map(({signature,...r})=>r),
        scope:'Consecutive call labels only. Every call, operand and configuration remains distinct; no value, parameter or behavioral equivalence is asserted.'}:null;
      const expression=id=>({node:id,inputs:incoming.get(id).map(t=>({edge:t.edge,target_port:t.target_port,source_port:t.source_port,expression:expression(t.producer)}))});
      const references=new Map(ordered.map((id,i)=>[id,'#'+(i+1)]));
      const externalInputs=[];
      if(reads.length)for(const b of traces.filter(b=>b.kind==='value'&&!active.has(b.producer))){
        const ports=members.filter(n=>n.kind==='interface'&&n.role==='input'&&n.parent===owner.id&&
          resolve(n.id,'out').node===b.producer&&resolve(n.id,'out').slot===b.source_port);
        if(ports.length!==1){valid=false;break;}
        const port=ports[0];externalInputs.push({...b,port_node:port.id,label:port.slot||port.label,reference:references.get(b.target)});
      }
      if(!valid)continue;
      const dependencyDag=dag?{result:references.get(sinks[0].id),nodes:ordered.map(id=>({node:id,reference:references.get(id),
        inputs:incoming.get(id).map(t=>({edge:t.edge,reference:references.get(t.producer),source_port:t.source_port,target_port:t.target_port}))}))}:null;
      const extended=!!pathDisplay||!!partitions.length,newForm=!!reads.length||partitions.some(n=>n.semantic_type==='operand-expression');
      result.set(owner.id,{rule_version:newForm?VERSION:extended?'local-pipelines/5':dag?'local-pipelines/4':tree||resources.size?'local-pipelines/3':'local-pipelines/2',node:owner.id,form:dag?'dependency-dag-summary':tree?'dependency-tree-summary':'dependency-path-summary',operations,
        ...(identity?{owner_identity:{...identity}}:{}),
        ...(reads.length?{external_inputs:externalInputs}:{}),
        ...(reads.length?{source_reads:reads.map(n=>({node:n.id,expression:n.source[0].expression,attribute:n.attribute_name,source:n.source,
          edges:ir.edges.filter(e=>e.source===n.id).map(e=>({...e})),scope:'Modeled source attribute read occurrence; value, immutability, alias identity and external effects unresolved.'}))}:{}),
        ...(pathDisplay?{path_display:pathDisplay}:{}),
        ...(partitions.length?{display_partitions:partitions.map(n=>({node:n.id,canonical_members:n.canonical_members.slice(),
          ...(n.semantic_type==='operand-expression'?{semantic_type:n.semantic_type,ports:n.boundary_ports.map(e=>({...e}))}:{}),
          cuts:ir.edges.filter(e=>{const set=new Set(n.canonical_members);return set.has(e.source)!==set.has(e.target);}).map(e=>({...e}))}))}:{}),
        ...(tree?{entry_operations:starts.map(n=>n.id),result_operation:sinks[0].id,dependency_tree:expression(sinks[0].id)}:{}),
        ...(dag?{entry_operations:starts.map(n=>n.id).sort(),result_operation:sinks[0].id,dependency_dag:dependencyDag}:{}),
        ...(newForm||extended||dag||tree||resources.size?{parameter_reads:parameters.map(n=>({node:n.id,source:n.source||[],module_identity:n.module_identity??null,
          edges:ir.edges.filter(e=>e.source===n.id).map(e=>({...e}))})),
          output_bindings:cuts.filter(e=>inside.has(e.source)).map(e=>({edge:e.id,producer:resolve(e.source,e.source_port??'out').node,
            source_port:resolve(e.source,e.source_port??'out').slot,target:e.target,target_port:e.target_port}))}:{}),
        auxiliary_reads:auxiliary.map(n=>({node:n.id,fact:n.symbolic_value})),bindings:traces,cuts:cuts.map(e=>({...e})),
        canonical_members:ids.filter(id=>canonical.has(id)),
        source_boundaries:boundaries.map(n=>{const members=new Set(closure(n.id));return {node:n.id,parent:n.parent,semantic_type:n.semantic_type,
          source:n.source||[],module_identity:n.module_identity??null,cuts:ir.edges.filter(e=>members.has(e.source)!==members.has(e.target)).map(e=>({...e}))};}),
        scope:dag?'Modeled bounded dependency DAG; each operation occurs once and internal result uses retain explicit references and slots. Reference numbering does not assert execution order. Exact operands, resources and source cuts retained. No scalar evaluation, purity, fusion, parallel execution, tensor equality or model-family assertion.':tree?'Modeled converging dependency tree across retained source boundaries; exact operands, auxiliary reads and each source cut retained. No scalar evaluation, purity, fusion, parallel execution or model-family assertion.':'Modeled dependency path across retained source boundaries; exact operands, auxiliary reads and each source cut retained. No purity, fusion, execution-order or model-family assertion.'});
    }
    return result;
  }
  function receipt(candidates,graph){const rows=[...candidates.values()].filter(r=>graph.positions.has(r.node));return {rule_version:rows.some(r=>r.rule_version===VERSION)?VERSION:'local-pipelines/5',rows:rows.map(r=>({...r,
    status:graph.positions.get(r.node).expanded?'expanded':'summary',visible_node:r.node,
    detailed_operations_exposed:r.operations.every(o=>graph.positions.has(o.node))}))};}
  function bindingRows(p){
    if(p.rule_version!==VERSION||!p.source_reads?.length||!p.dependency_dag)return null;
    const refs=new Map(p.dependency_dag.nodes.map(n=>[n.node,n.reference]));
    const reads=p.source_reads.map((r,i)=>({node:r.node,reference:'read'+(i+1),expression:r.expression}));
    const inputs=[...new Map(p.external_inputs.map(b=>[b.port_node,{node:b.port_node,label:b.label,producer:b.producer,source_port:b.source_port}])).values()]
      .map((b,i)=>({...b,reference:'input'+(i+1)}));
    const rows=p.operations.map(o=>{const uses=p.bindings.filter(b=>b.target===o.node).flatMap(b=>{
      const read=reads.find(r=>r.node===b.producer),input=p.external_inputs.find(e=>e.edge===b.edge);
      const port=input&&inputs.find(e=>e.node===input.port_node);
      const value=refs.get(b.producer)||(read?read.reference+'('+JSON.stringify(read.expression)+')':port?port.reference+'('+JSON.stringify(port.label)+')':null);
      return value?[{edge:b.edge,producer:b.producer,source_port:b.source_port,target:b.target,target_port:b.target_port,
        value:value+(b.source_port==='out'?'':'['+b.source_port+']')}]:[];
    }).sort((a,b)=>String(a.target_port).localeCompare(String(b.target_port))||a.edge.localeCompare(b.edge));
      return {node:o.node,reference:refs.get(o.node),label:o.label,uses,
        text:refs.get(o.node)+' '+o.label+(uses.length?' ← '+uses.map(b=>b.target_port+'='+b.value).join('; '):'')};});
    const last=p.operations.find(o=>refs.get(o.node)===p.dependency_dag.result);
    return {schema:'dependency-binding-rows/1',reads,inputs,rows,title:'Result '+p.dependency_dag.result+' · '+last.label,
      scope:'One reference per extracted operation, source-read node and input interface; each modeled use keeps its result and operand slot. References do not assert runtime read identity, read equality, evaluation or execution order.'};
  }
  const api={VERSION,compile,receipt,bindingRows};root.SemanticLocalPipelines=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
