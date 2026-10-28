/* Studio binding for Summary's native, reversible semantic cuts. */
(function(root){
  'use strict';
  const G=root.SummaryNativeSemantic,F=root.SemanticCompositionLayout,copy=v=>JSON.parse(JSON.stringify(v));
  const granularities=['overview','modules','stages','semantic','roles','detailed'];
  const recordedRuns=ir=>Array.isArray(ir.runtime?.runs)?ir.runtime.runs:[];
  function enabled(bundle){return bundle?.ir?.semantic_ir?.schema==='archcanvas-source-semantic/2';}
  function state(action){return F.frontier({mode:'source'},action);}
  function nodes(graph){const visible=new Map(graph.nodes.map(n=>[n.id,n]));return graph.generic?Array.from(G.expected(graph).idx.nodes.values()).map(n=>({x:0,y:0,w:160,h:60,expanded:false,...visible.get(n.id),id:n.id,parent:n.parent,label:n.paper?.title||n.label||n.id,semantic:n,presentation_only:!!n.presentation_only})):graph.recursive?.authority.detail.nodes||graph.nodes;}
  function decorate(graph,previous,binding){
    if(previous)for(const field of ['caseId','sourceAdapter','sourceProfile','sourceFacts','studioPresentation','studioCameras','studioCamera','importedDocument','authoringWorkspace'])if(previous[field]!==undefined)graph[field]=copy(previous[field]);
    if(binding){graph.caseId=binding.id;graph.sourceAdapter={version:1,entry:binding.entry,sourceSha256:binding.sourceSha256,irSha256:binding.irSha256};graph.sourceProfile={analysis:'Summary native semantic projection',modelExecuted:false};}
    graph.semanticHierarchy={nodes:nodes(graph)};
    graph.frontierPreset=graph.generic.state.studioFrontierPreset||'custom';
    graph.semanticRevision=(previous?.semanticRevision||0)+1;
    return graph;
  }
  function operation(graph,transition){
    if(!transition)return null;
    if(transition.type==='semantic'){
      const patch=transition.patch||{},allowed=new Set(['mode','runtimeInlineRun','paperGranularity','paperSequenceView','paperReadSummary','paperFrameView','paperRolePaths','paperRoleDetails','paperExpressionDetails','paperFocus','paperRelation','paperRepresentative','paperRepresentativeGroup']);
      if(Object.keys(patch).some(k=>!allowed.has(k)))throw Error('不支持的语义切面选项。');
      if(patch.mode!==undefined&&!['source','runtime','merged'].includes(patch.mode))throw Error('证据视图无效。');
      if(patch.mode==='runtime'&&!graph.generic.ir.nodes.some(n=>n.id==='runtime-observations'))throw Error('当前 IR 没有 CPU 执行轨迹。');
      if(patch.runtimeInlineRun!==undefined){
        const runs=recordedRuns(graph.generic.ir),run=runs[patch.runtimeInlineRun];
        if(!Number.isInteger(patch.runtimeInlineRun)||patch.runtimeInlineRun<0||patch.runtimeInlineRun>=runs.length||!run||typeof run!=='object'||Array.isArray(run))throw Error('CPU 补证样例不存在。');
        if((patch.mode||graph.generic.state.mode||'source')!=='merged')throw Error('CPU 补证样例仅适用于合并视图。');
      }
      if(patch.paperGranularity!==undefined&&!granularities.includes(patch.paperGranularity))throw Error('语义切面无效。');
      for(const [key,values]of [['paperSequenceView',['representatives','summary']],['paperReadSummary',['bindings','boundary']],['paperFrameView',['compact','source']]])if(patch[key]!==undefined&&!values.includes(patch[key]))throw Error('语义展示策略无效。');
      // Requests refer to actual certificates, never to arbitrary role names.
      const cut=G.expected(graph);
      for(const request of patch.paperRolePaths||[]){const certificate=(cut.architecture?.semantic_contracts||[]).find(c=>c.id===request.certificate&&c.node===request.node);if(!certificate||!root.SemanticRoleFrontier.references(certificate.roles,cut.idx.nodes).some(ref=>G.stable(ref.keys)===G.stable(request.role)))throw Error('角色路径不属于当前认证契约。');}
      for(const key of ['paperFocus','paperRepresentative'])if(typeof patch[key]==='string'&&!cut.idx.nodes.has(patch[key]))throw Error('切面定位对象不存在。');
      if(patch.paperRepresentative===true){const group=cut.idx.nodes.get(patch.paperFocus)?.repeat_contract?.structure?.groups?.[patch.paperRepresentativeGroup];if(!group||group.status!=='proved')throw Error('结构代表必须引用已证明的重复组。');}
      if(patch.paperRelation!=null&&!(cut.architecture?.relation_graph?.relations||[]).some(r=>r.id===patch.paperRelation))throw Error('语义关系不存在。');
      return {kind:'state',patch:{...copy(patch),paperCanonical:false,paperAuto:true,open:[],studioFrontierPreset:'custom'}};
    }
    if(transition.type==='preset')return {kind:'frontier',action:transition.preset};
    if(transition.type==='back')return {kind:'back'};
    if(transition.type==='all')return {kind:'all',open:!!transition.expanded};
    if(transition.type==='focus'){
      const cut=G.expected(graph),by=new Map([...graph.generic.ir.nodes,...cut.idx.nodes.values()].map(n=>[n.id,n])),target=by.get(transition.id);
      if(!target)throw Error('切面定位对象不存在。');
      let at=target,observed=false;
      while(at){if(at.id==='runtime-observations'||at.id.startsWith('runtime:')){observed=true;break;}at=by.get(at.parent);}
      const mode=graph.generic.state.mode||'source',next=observed&&(mode==='source'||mode==='merged'&&!cut.idx.nodes.has(target.id))?'runtime':!observed&&mode==='runtime'?'source':mode;
      if(next!==mode){
        const back=copy(graph.generic.state);delete back.nativeFocusReturn;
        return {kind:'state',patch:{mode:next,paperFocus:target.id,paperRelation:null,paperAuto:true,paperCanonical:false,open:[],nativeSourceFocus:null,nativeFocusReturn:back,studioFrontierPreset:'custom'}};
      }
      return {kind:'focus',id:transition.id};
    }
    if(transition.type==='toggle')return {kind:'toggle',id:transition.id,force:transition.expanded};
    throw Error('不支持的原生语义前沿操作。');
  }
  function prepare(message){
    message={...message,options:G.routeOptions({budgetMs:8000,...message.options})};
    // Aesthetic passes may try other physical ports. An explicit inspector
    // endpoint edit takes precedence over those optional layout proposals.
    if(Object.keys(message.options.portOverrides||{}).length)Object.assign(message.options,{refineCrossings:false,refinePlacement:false,refineChannels:false,refineFlow:false});
    const previous=message.graph;let result;
    if(message.task==='generic-build'){
      result=G.prepare({...message,state:message.state||{...state('overview'),studioFrontierPreset:'overview'}});
    }else if(message.task==='generic-route'||!message.transition){
      result=G.prepare({...message,task:'generic-route'});
    }else if(message.transition.type==='expand'){
      let candidate=previous;
      for(const id of message.transition.ids){if(!nodes(candidate).some(n=>n.id===id))throw Error('展开模块不存在。');candidate=G.operate(candidate,{kind:'toggle',id,force:message.transition.expanded});}
      candidate.generic.state={...candidate.generic.state,studioFrontierPreset:'custom'};
      result=G.prepare({...message,task:'generic-route',graph:candidate});
    }else{
      const op=operation(previous,message.transition);
      result=G.prepare({...message,operation:op});
      const preset=message.transition.type==='preset'?message.transition.preset:message.transition.type==='back'?result.graph.generic.state.studioFrontierPreset:'custom';
      // Frontiers carry their own preset through undo, redo and persistence.
      result.graph.generic.state={...result.graph.generic.state,studioFrontierPreset:preset||'custom'};
    }
    decorate(result.graph,previous,message.binding);
    // The retained Studio validator also checks distinct value lanes. Mark
    // every unresolved route explicitly so a continuation retries it against
    // settled lanes instead of publishing a false "complete" status.
    for(const [id,check]of result.validation.edges){const edge=result.graph.edges.find(e=>e.id===id);if(edge&&!check.ok){edge.failed=true;edge.reason=check.violations.join('; ');}}
    const {pending,failed}=routing(result.graph);
    result.graph.nativeRouting=routing(result.graph);
    result.pending=pending;result.failed=pending+failed;
    return result;
  }
  function routing(graph){const pending=graph.edges.filter(e=>e.pendingRouting).length,failed=graph.edges.filter(e=>e.failed&&!e.pendingRouting).length;return {pending,failed,complete:!pending&&!failed};}
  function accepts(graph,validation){
    const unresolved=e=>!!e&&(e.draft||e.failed||e.pendingRouting);
    const ids=new Set(graph.nodes.map(n=>n.id));
    return graph.edges.every(e=>ids.has(e.source)&&ids.has(e.target)&&e.route?.length>=2&&e.route.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)))&&
      validation.source.ok&&!validation.layout.nodes.length&&validation.layout.junctions.ok&&
      validation.edges.every(([id,check])=>check.ok||unresolved(graph.edges.find(e=>e.id===id)))&&
      validation.layout.wires.every(ids=>ids.some(id=>unresolved(graph.edges.find(e=>e.id===id))));
  }
  function inspector(graph,selected=[]){
    if(!graph?.generic)return null;const cut=G.expected(graph),state=graph.generic.state;
    const ir=graph.generic.ir,runs=recordedRuns(ir),inline=cut.publication?.source_runtime;
    return {renderer:G.VERSION,mode:state.mode||'source',availableModes:['source',...(ir.nodes.some(n=>n.id==='runtime-observations')?['runtime']:[]),'merged'],
      runtimeEvidence:{runs:runs.map((run,index)=>({index,case:String(run?.case||'样例 '+(index+1)),mode:String(run?.mode||''),status:String(run?.status||'unknown'),truncated:!!run?.truncated,replayMatched:run?.replay?.matched===true})),
        selectedRun:Number.isInteger(state.runtimeInlineRun)&&runs[state.runtimeInlineRun]?state.runtimeInlineRun:0,integratedRegions:inline?.regions?.length||0,unplacedRegions:inline?.unplaced?.length||0,
        traceDigest:ir.runtime?.trace_digest||null,sourceUnchanged:ir.runtime?.source_unchanged===true,executesModel:false},
      granularity:state.paperGranularity||'roles',sequence:state.paperSequenceView||'representatives',readSummary:state.paperReadSummary||'bindings',frames:state.paperFrameView||'compact',
      recipe:state.paperFrontierRecipe||null,nodeAccounting:copy(cut.node_accounting),edgeAccounting:copy(cut.edge_accounting),representatives:copy(cut.representatives),
      roleRequests:copy(state.paperRolePaths||[]),canBack:!!(state.nativeFocusReturn||state.paperFrontierReturn),routing:routing(graph),
      contracts:copy(cut.architecture?.semantic_contracts||[]),relations:copy(cut.architecture?.relation_graph?.relations||[]),
      roleOptions:(cut.architecture?.semantic_contracts||[]).flatMap(c=>root.SemanticRoleFrontier.references(c.roles,cut.idx.nodes).map(ref=>({node:c.node,certificate:c.id,role:ref.keys,target:ref.node,label:ref.path}))),
      selectionDetails:selected.flatMap(id=>{const node=graph.nodes.find(n=>n.id===id);return node?[{id,evidence:G.nodeEvidence(graph,id),frameOwnership:copy(node.semantic.frame_ownership||[]),repeatGroups:(node.semantic.repeat_contract?.structure?.groups||[]).flatMap((group,index)=>group.status==='proved'?[{index,indices:copy(group.indices)}]:[])}]:[];}),
      selectedNodes:graph.nodes.map(n=>({id:n.id,contractStage:!!n.semantic.contract_stage,localExpression:!!n.semantic.local_expression,semanticType:n.semantic.semantic_type}))};
  }
  const cameraKey=graph=>G.stable([graph.generic.state.mode,graph.nodes.map(n=>[n.id,n.parent,n.expanded]),graph.edges.filter(e=>!e.draft).map(e=>e.id)]);
  const validCamera=value=>value&&['x','y','w','h'].every(k=>Number.isFinite(value[k]))&&value.w>0&&value.h>0&&value.w<1000000&&value.h<1000000;
  function restoreCamera(previous,next,camera){
    const oldKey=cameraKey(previous),newKey=cameraKey(next),rows=(previous.studioCameras||[]).filter(row=>row.key!==oldKey&&validCamera(row.camera));
    rows.push({key:oldKey,camera:copy(camera)});next.studioCameras=rows.slice(-4);
    const saved=next.studioCameras.find(row=>row.key===newKey)?.camera;
    return validCamera(saved)?copy(saved):null;
  }
  root.ArchCanvasSemanticView={enabled,state,nodes,decorate,prepare,inspector,restoreCamera,validCamera,accepts};
})(typeof window!=='undefined'?window:globalThis);
