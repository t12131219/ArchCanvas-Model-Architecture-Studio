/* A dependency summary and exposed operation paths can express the same coarse
 * structure. Neither form proves every operand, configuration or execution. */
(function(root){
  'use strict';
  const VERSION='summary-goals/2',flow=e=>['data','alias','interface-binding'].includes(e.kind);
  const normalized=s=>String(s).replace(/\s/g,'');
  function sourceIndex(ir){
    const by=new Map(ir.nodes.map(n=>[n.id,n])),incoming=new Map(),outgoing=new Map();
    for(const e of ir.edges){if(!incoming.has(e.target))incoming.set(e.target,[]);incoming.get(e.target).push(e);
      if(!outgoing.has(e.source))outgoing.set(e.source,[]);outgoing.get(e.source).push(e);}
    const transparent=n=>n&&['interface','value-alias'].includes(n.kind)&&!n.operator;
    const resolve=(id,port='out')=>{const seen=new Set();while(!seen.has(id)){
      seen.add(id);const n=by.get(id),es=incoming.get(id)||[];
      if(!transparent(n)||es.length!==1||!flow(es[0])||es[0].condition)break;
      const e=es[0],outer=n.kind==='value-alias'?n.slot??e.source_port??'out':e.source_port??'out';
      port=outer==='out'?port:port==='out'?outer:outer+'.'+port;id=e.source;
    }return {node:id,port};};
    const label=n=>n.framework_type?.split('.').at(-1)||(n.source_framework_function&&n.source_framework_function===n.function_target?n.function_target.split('.').at(-1):n.operator);
    return {by,incoming,outgoing,transparent,resolve,label};
  }
  function build(ir,plan){
    const index=sourceIndex(ir),{by,resolve,label}=index,planned=new Map(plan.nodes.map(n=>[n.id,n])),goals=[];
    // A source/plan pair is fixed for this proof pass. Build its two ownership
    // indexes once, rather than once per summarized helper in the full IR.
    const children=new Map(),displayChildren=new Map();
    for(const n of ir.nodes){if(!children.has(n.parent))children.set(n.parent,[]);children.get(n.parent).push(n.id);}
    for(const n of plan.nodes){if(!displayChildren.has(n.parent))displayChildren.set(n.parent,[]);displayChildren.get(n.parent).push(n.id);}
    const displayClosure=id=>{const ids=[id];for(let i=0;i<ids.length;i++)ids.push(...displayChildren.get(ids[i])||[]);return ids;};
    const guarded=n=>!n||['opaque','control'].includes(n.kind)||n.mutable||n.condition||n.identity_display||n.observed_calls||n.evidence_status==='runtime-only'||n.runtime_evidence?.length||n.semantic_contracts?.length||n.repeat_contract||n.iteration;
    for(const owner of plan.nodes){
      const p=owner.local_pipeline;if(!p)continue;
      const errors=[],operations=p.operations||[],ids=operations.map(o=>o.node),active=new Set(ids);
      const inside=new Set([owner.id]),todo=[owner.id];
      for(let i=0;i<todo.length;i++)for(const id of children.get(todo[i])||[]){inside.add(id);todo.push(id);}
      const identity=p.source_reads?.length&&p.rule_version==='local-pipelines/6'&&p.owner_identity?.kind==='same-object-calls'&&
        JSON.stringify(p.owner_identity)===JSON.stringify(owner.identity_display);
      if(p.owner_identity&&!identity)errors.push('changed-owner-identity');
      if(p.node!==owner.id||!['source-function','source-module'].includes(by.get(owner.id)?.semantic_type)||
        [...inside].some(id=>guarded(by.get(id))||guarded(identity&&id===owner.id?{...planned.get(id),identity_display:null}:planned.get(id))))errors.push('protected-source-boundary');
      if(ids.length<2||ids.length>6&&(p.dependency_dag||p.dependency_tree)||active.size!==ids.length||operations.some(o=>!inside.has(o.node)||by.get(o.node)?.kind!=='compute'||label(by.get(o.node))!==o.label))errors.push('invalid-operations');
      if(inside.size!==p.canonical_members?.length||new Set(p.canonical_members).size!==inside.size||p.canonical_members?.some(id=>!inside.has(id)))errors.push('incomplete-source-membership');
      // Source ownership proves membership; a display frame may only repartition
      // that same set. Independently check every transparent frame's real cuts.
      const displayed=displayClosure(owner.id),canonicalDisplayed=displayed.filter(id=>by.has(id)),partitions=displayed.filter(id=>!by.has(id));
      if(canonicalDisplayed.length!==inside.size||canonicalDisplayed.some(id=>!inside.has(id)))errors.push('changed-display-membership');
      if(partitions.length!==(p.display_partitions||[]).length||partitions.some(id=>{
        const n=planned.get(id),r=p.display_partitions?.find(r=>r.node===id),members=new Set(displayClosure(id).filter(id=>by.has(id)));
        const cuts=ir.edges.filter(e=>members.has(e.source)!==members.has(e.target));
        const operand=p.rule_version==='local-pipelines/6'&&n?.semantic_type==='operand-expression'&&r?.semantic_type===n.semantic_type;
        const ports=cuts.map(e=>({id:e.id,direction:members.has(e.source)?'output':'input',source:e.source,source_port:e.source_port,target:e.target,target_port:e.target_port,evidence:e.evidence}));
        return guarded(n)||n.kind!=='composite'||!n.presentation_only||!operand&&n.semantic_type!=='structural-region'||!r||
          members.size!==r.canonical_members.length||new Set(r.canonical_members).size!==members.size||r.canonical_members.some(id=>!members.has(id))||
          JSON.stringify(r.cuts)!==JSON.stringify(cuts)||JSON.stringify(n.boundary_ports)!==JSON.stringify(operand?ports:cuts)||
          operand&&JSON.stringify(r.ports)!==JSON.stringify(ports)||
          n.canonical_members.length!==members.size||new Set(n.canonical_members).size!==members.size||n.canonical_members.some(id=>!members.has(id));
      }))errors.push('changed-display-partition');
      const reads=p.source_reads||[],readIds=new Set(reads.map(r=>r.node));
      const expectedReads=new Set((p.bindings||[]).filter(b=>b.kind==='source-read').map(b=>b.producer));
      if(expectedReads.size!==readIds.size||[...expectedReads].some(id=>!readIds.has(id)))errors.push('missing-source-read');
      if(reads.length&&(p.rule_version!=='local-pipelines/6'||readIds.size!==reads.length||reads.some(r=>{
        const n=by.get(r.node),edges=ir.edges.filter(e=>e.source===r.node);
        return !n||guarded(n)||!inside.has(n.id)||n.evidence_status!=='static-only'||n.operator!=='attribute'||
          n.attribute_name!==r.attribute||n.source?.length!==1||r.expression!=='self.'+n.attribute_name||
          r.expression!==n.source[0].expression||JSON.stringify(r.source)!==JSON.stringify(n.source)||
          index.incoming.get(n.id)?.length||!edges.length||JSON.stringify(r.edges)!==JSON.stringify(edges)||
          edges.some(e=>!flow(e)||e.source_port!=='out'||!active.has(e.target));
      })))errors.push('changed-source-read');
      const uses=ir.edges.filter(e=>active.has(e.target)).map(e=>{const from=resolve(e.source,e.source_port);return {edge:e.id,producer:from.node,source_port:from.port,target:e.target,target_port:e.target_port};});
      const key=b=>JSON.stringify([b.edge,b.producer,b.source_port,b.target,b.target_port]);
      if(uses.length!==p.bindings?.length||uses.some(b=>!p.bindings.some(t=>key(t)===key(b))))errors.push('changed-canonical-binding');
      const internal=uses.filter(b=>active.has(b.producer)),inputs=new Map(ids.map(id=>[id,internal.filter(b=>b.target===id)]));
      const order=new Map(ids.map((id,i)=>[id,i]));
      if(internal.some(b=>order.get(b.producer)>=order.get(b.target)))errors.push('non-topological-structure');
      const sinks=ids.filter(id=>!internal.some(b=>b.producer===id));
      if(sinks.length!==1)errors.push('ambiguous-result');
      const cuts=ir.edges.filter(e=>inside.has(e.source)!==inside.has(e.target));
      if(JSON.stringify(cuts)!==JSON.stringify(p.cuts))errors.push('changed-source-cuts');
      const edges=ir.edges.filter(e=>inside.has(e.source)||inside.has(e.target));
      if(edges.some(e=>(!flow(e)&&e.kind!=='parameter-read')||e.condition||e.iteration||e.design_route))errors.push('protected-dependency');
      const refs=new Map(ids.map((id,i)=>[id,'#'+(i+1)])),labels=new Map(operations.map(o=>[o.node,o.label]));
      const external=p.external_inputs||[],expectedExternal=(p.bindings||[]).filter(b=>b.kind==='value'&&!active.has(b.producer));
      if(reads.length&&(external.length!==expectedExternal.length||external.some((b,i)=>{
        const port=by.get(b.port_node),origin=port&&resolve(port.id),expected=expectedExternal[i];
        return !port||port.parent!==owner.id||port.kind!=='interface'||port.role!=='input'||
          origin.node!==b.producer||origin.port!==b.source_port||b.label!==(port.slot||port.label)||
          b.reference!==refs.get(b.target)||key(b)!==key(expected);
      })))errors.push('changed-external-input');
      const expression=(id,seen=new Set())=>seen.has(id)?'?':labels.get(id)+((inputs.get(id)||[]).length?' ← {'+inputs.get(id).map(b=>expression(b.producer,new Set([...seen,id]))).join('; ')+'}':'');
      let title,formulas=[];
      if(p.dependency_dag){
        const actual=p.dependency_dag.nodes||[];
        if(p.dependency_dag.result!==refs.get(sinks[0])||actual.length!==ids.length||actual.some((n,i)=>n.node!==ids[i]||n.reference!==refs.get(n.node)||
          JSON.stringify(n.inputs)!==JSON.stringify((inputs.get(n.node)||[]).map(b=>({edge:b.edge,reference:refs.get(b.producer),source_port:b.source_port,target_port:b.target_port})))))errors.push('changed-dag-reference');
        title='Result '+refs.get(sinks[0]);
        formulas=ids.map(id=>{const bindings=inputs.get(id).slice().sort((a,b)=>String(a.target_port).localeCompare(String(b.target_port))||a.edge.localeCompare(b.edge));
          return refs.get(id)+' '+labels.get(id)+(bindings.length?' ← '+bindings.map(b=>b.target_port+'='+refs.get(b.producer)+(b.source_port==='out'?'':'['+b.source_port+']')).join('; '):'');});
      }else if(p.dependency_tree){
        const tree=(id,seen=new Set())=>seen.has(id)?null:{node:id,inputs:(inputs.get(id)||[]).map(b=>({edge:b.edge,target_port:b.target_port,source_port:b.source_port,expression:tree(b.producer,new Set([...seen,id]))}))};
        if(JSON.stringify(p.dependency_tree)!==JSON.stringify(tree(sinks[0])))errors.push('changed-tree-reference');
        title=expression(sinks[0]);
      }
      else {title=operations.map(o=>o.label).join(' → ');
        if(internal.length!==ids.length-1||ids.slice(1).some((id,i)=>inputs.get(id).length!==1||inputs.get(id)[0].producer!==ids[i]))errors.push('not-a-path');
        if(p.path_display){
          const expected=[];let previous=null;
          for(const o of operations){const n=by.get(o.node),signature=JSON.stringify([n?.operator,n?.framework_type||null,label(n||{}),
            n?.framework_type?'framework-type':n?.source_framework_function&&n.source_framework_function===n.function_target?'source-framework-function':'operator']);
            if(previous?.signature===signature)previous.operations.push(o.node);else {previous={signature,label:label(n||{}),operations:[o.node]};expected.push(previous);}}
          const runs=expected.map(({signature,...r})=>r);
          if(p.path_display.schema!=='dependency-path-display/1'||JSON.stringify(p.path_display.runs)!==JSON.stringify(runs))errors.push('changed-call-label-runs');
          title=runs.map(r=>r.label+(r.operations.length>1?' · '+r.operations.length+' calls':'')).join(' → ');
        }
      }
      goals.push({id:'goal:summary:'+owner.id,kind:'dependency-structure',node:owner.id,form:p.form,
        operations:operations.map(o=>({node:o.node,label:o.label})),internal_bindings:internal,cuts,
        printed_title:title,printed_formulas:formulas,proof_errors:errors,
        ...(reads.length?{source_reads:reads,printed_reads:reads.flatMap(r=>r.edges.map(e=>`Reads ${r.expression} → ${refs.get(e.target)}[${e.target_port}]`)),
          printed_inputs:external.map(b=>`Input ${b.label} → ${b.reference}[${b.target_port}]`),
          ...(identity?{printed_identity:`${p.owner_identity.label} · source call ${p.owner_identity.invocation}/${p.owner_identity.count}`}:{})}:{}),
        scope:'Operation labels and internal dependency structure with routed source cuts. Full operands, parameter/configuration values, unknown behavior and execution order are not covered.'});
      // Independently derive the alternate printed use rows from the checked
      // binding records, not from the presentation recipe or its receipt.
      if(reads.length){
        const inputs=[];for(const b of external)if(!inputs.some(n=>n.node===b.port_node))inputs.push({node:b.port_node,label:b.label,producer:b.producer,source_port:b.source_port,reference:'input'+(inputs.length+1)});
        const resources=reads.map((r,i)=>({node:r.node,reference:'read'+(i+1),expression:r.expression}));
        const rows=operations.map(o=>{const uses=[];
          for(const b of p.bindings){if(b.target!==o.node)continue;
            const r=resources.find(r=>r.node===b.producer),e=external.find(e=>e.edge===b.edge),v=e&&inputs.find(n=>n.node===e.port_node);
            const printed=refs.get(b.producer)||(r?r.reference+'('+JSON.stringify(r.expression)+')':v?v.reference+'('+JSON.stringify(v.label)+')':null);
            if(printed)uses.push({edge:b.edge,producer:b.producer,source_port:b.source_port,target:b.target,target_port:b.target_port,value:printed+(b.source_port==='out'?'':'['+b.source_port+']')});
          }
          uses.sort((a,b)=>String(a.target_port).localeCompare(String(b.target_port))||a.edge.localeCompare(b.edge));
          return {node:o.node,reference:refs.get(o.node),label:o.label,uses,text:refs.get(o.node)+' '+o.label+(uses.length?' ← '+uses.map(b=>b.target_port+'='+b.value).join('; '):'')};
        });
        goals.at(-1).binding_rows={reads:resources,inputs,rows,title:'Result '+refs.get(sinks[0])+' · '+labels.get(sinks[0])};
      }
    }
    return {schema:VERSION,goals};
  }
  // This deliberately weaker view exposes a real source-call boundary. It
  // must not satisfy the internal dependency-structure goal below. The same
  // independently checked operations, reads and cuts remain expandable.
  function callBoundary(goal,ir){
    if(goal.proof_errors.length||!goal.source_reads?.length)return null;
    const source=ir.nodes.find(n=>n.id===goal.node),sinks=goal.operations.filter(o=>!goal.internal_bindings.some(b=>b.producer===o.node));
    if(!source?.label||sinks.length!==1)return null;
    const captions=[goal.operations.length+' operations · folded','Result: '+sinks[0].label,
      goal.source_reads.length+' source read'+(goal.source_reads.length===1?'':'s'),...(goal.printed_identity?[goal.printed_identity]:[])];
    return {schema:'source-call-boundary/1',node:goal.node,label:source.label,operations:goal.operations,
      result:sinks[0],source_reads:goal.source_reads.map(r=>({node:r.node,expression:r.expression})),cuts:goal.cuts,
      identity:goal.printed_identity||null,printed_title:'Source: '+source.label,printed_captions:captions,
      scope:'Source call, result operation, read occurrences and routed boundary only. Internal dependency structure and operands are folded; no purity, value equality, execution or model-family assertion.'};
  }
  function evaluate(goalSet,ir,graph,prepared){
    const {by,resolve,transparent,outgoing}=sourceIndex(ir),paths=new Map();
    for(const path of prepared.routes)for(const member of path.bundle_members||[path])for(const id of new Set([member.id,...member.originals||[]])){
      if(!paths.has(id))paths.set(id,[]);paths.get(id).push({path,member});}
    const targetReachable=(first,last)=>{const todo=[first],seen=new Set();for(let i=0;i<todo.length;i++){
      const at=todo[i];if(at===last)return true;if(seen.has(at)||!transparent(by.get(at)))continue;seen.add(at);
      for(const e of outgoing.get(at)||[])if(flow(e)&&!e.condition)todo.push(e.target);
    }return false;};
    const routeFor=e=>(paths.get(e.id)||[]).filter(({path,member})=>{
      if(!path.route.ok||!graph.positions.has(path.source)||!graph.positions.has(path.target))return false;
      const expected=resolve(e.source,e.source_port),actual=resolve(member.resolved_source??member.canonical_source,member.source_port);
      return expected.node===actual.node&&expected.port===actual.port&&targetReachable(e.target,member.canonical_target??member.target)&&
        (member.id!==e.id||member.target_port===e.target_port);
    });
    const canonical=new Map(ir.edges.map(e=>[e.id,e]));
    return goalSet.goals.map(goal=>{
      const n=graph.nodes.find(n=>n.id===goal.node),position=graph.positions.get(goal.node),folded=!!position&&!position.expanded;
      const title=normalized((n?.paper?.lines||[]).join('')),caption=normalized((n?.paper?.captions||[]).join(''));
      const rows=n?.paper?.read_binding_rows,expected=goal.binding_rows;
      const alternate=rows&&expected&&rows.schema==='dependency-binding-rows/1'&&
        ['reads','inputs','rows','title'].every(k=>JSON.stringify(rows[k])===JSON.stringify(expected[k]));
      // Relocation is a distinct checked printing, not a general permission to
      // satisfy a title from arbitrary caption text or presentation metadata.
      const heading=n?.paper?.source_heading,source=by.get(goal.node);
      const relocated=!!heading&&alternate&&source?.label&&
        heading.schema==='source-summary-heading/1'&&heading.node===goal.node&&heading.label===source.label&&
        heading.result_title===expected.title&&title===normalized('Source: '+source.label)&&
        caption.includes(normalized(expected.title+' · Dependency DAG'));
      const missingText=folded?[...(heading&&!relocated?['invalid-source-heading']:[]),...(rows?[...(!alternate?['invalid-binding-rows']:[]),...(!relocated&&!title.includes(normalized(expected?.title))?['title']:[]),
        ...(expected?.rows||[]).filter(r=>!caption.includes(normalized(r.text))).map(r=>r.text)]:
        [...(!title.includes(normalized(goal.printed_title))?['title']:[]),...goal.printed_formulas.filter(s=>!caption.includes(normalized(s))) ])]:[];
      if(folded)for(const text of [...(!rows?goal.printed_reads||[]:[]),...(!rows?goal.printed_inputs||[]:[]),...goal.printed_identity?[goal.printed_identity]:[]])if(!caption.includes(normalized(text)))missingText.push(text);
      const missingCuts=goal.cuts.filter(e=>!routeFor(e).some(({path})=>!folded||(by.get(e.source)&&path.source===goal.node)||(by.get(e.target)&&path.target===goal.node))).map(e=>e.id);
      const missingNodes=goal.operations.filter(o=>!graph.positions.has(o.node)).map(o=>o.node);
      const missingOperationLabels=goal.operations.filter(o=>{
        const n=graph.nodes.find(n=>n.id===o.node),symbol=graph.positions.get(o.node)?.symbol;
        const expectedSymbol=o.label==='add'||/^aten\.add\./.test(o.label)?'+':
          ['mul','mult'].includes(o.label)||/^aten\.mul\./.test(o.label)?'×':null;
        const printed=symbol?symbol===expectedSymbol:!!n?.paper?.lines?.length&&
          normalized([...n.paper.lines,...n.paper.captions||[]].join('')).includes(normalized(o.label==='structure'?'Pack values':o.label));
        return !printed||n?.operator!==by.get(o.node)?.operator||n?.framework_type!==by.get(o.node)?.framework_type;
      }).map(o=>o.node);
      const missingEdges=goal.internal_bindings.filter(b=>!canonical.has(b.edge)||!routeFor(canonical.get(b.edge)).length).map(b=>b.edge);
      const boundary=n?.paper?.call_boundary,expectedBoundary=boundary&&callBoundary(goal,ir);
      const boundaryValid=folded&&expectedBoundary&&JSON.stringify(boundary)===JSON.stringify(expectedBoundary)&&
        title===normalized(expectedBoundary.printed_title)&&caption===normalized(expectedBoundary.printed_captions.join(''))&&!missingCuts.length;
      const summary=!boundary&&folded&&!goal.proof_errors.length&&!missingText.length&&!missingCuts.length;
      const detail=!goal.proof_errors.length&&!missingNodes.length&&!missingOperationLabels.length&&!missingEdges.length&&!missingCuts.length;
      return {goal:goal.id,kind:goal.kind,node:goal.node,status:summary||detail?'fulfilled':'unfulfilled',
        form:summary?'summary':detail?'operation-paths':boundaryValid?'call-boundary':'deferred',proof_errors:goal.proof_errors,
        ...(boundary?{boundary_status:boundaryValid?'fulfilled':'unfulfilled',boundary_scope:expectedBoundary?.scope,
          refinement_required:'Expand this source call to inspect internal dependency structure and operand bindings.'}:{}),
        missing_summary_text:missingText,missing_cut_paths:missingCuts,missing_operation_nodes:missingNodes,missing_operation_labels:missingOperationLabels,missing_internal_paths:missingEdges,
        detailed_relationships_fulfilled:false,scope:goal.scope};
    });
  }
  const api={VERSION,build,callBoundary,evaluate};root.SemanticSummaryGoals=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
