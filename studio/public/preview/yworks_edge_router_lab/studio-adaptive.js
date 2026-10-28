/* Summary adaptive-frontier/5 on the single native canvas. Selection loop
 * adapted from Summary_Merge/semantic_studio/publication-renderer.js;
 * candidates and semantic assessment use the unmodified Summary modules. */
(function(root){
  'use strict';
  const G=root.SummaryNativeSemantic,A=root.SemanticAdaptiveFrontier,Goals=root.SemanticExpressionGoals,Summary=root.SemanticSummaryGoals;
  const copy=v=>JSON.parse(JSON.stringify(v)),keys=['paperRoleDetails','paperRolePaths','paperExpressionDetails'];
  const requests=state=>Object.fromEntries(keys.map(k=>[k,copy(state[k]||[])]));
  const decode=s=>s.replace(/&(?:amp|lt|gt|quot|#39);/g,c=>({'&amp;':'&','&lt;':'<','&gt;':'>','&quot;':'"','&#39;':"'"}[c]));
  // Measure only what the native glyph actually prints. Full semantic captions
  // remain evidence, but a truncated caption must not fulfill a printed goal.
  function texts(node){return [...(node.html||'').matchAll(/<text\b([^>]*)>([\s\S]*?)<\/text>/g)].map(([,attrs,text])=>{
    const attr=k=>Number(new RegExp('(?:^|\\s)'+k+'="([^"]+)"').exec(attrs)?.[1]);
    return {text:decode(text.replace(/<[^>]+>/g,'')),x:attr('x'),y:attr('y'),font:attr('font-size'),anchor:/text-anchor="([^"]+)"/.exec(attrs)?.[1]||'start'};
  });}
  function measured(result){
    const native=result.graph,cut=G.expected(native),ir=native.generic.ir,validation=root.SummaryEngine.validateView(native);
    const checks=new Map(validation.edges),routes=native.edges.filter(e=>!e.draft).map(e=>({...copy(e.binding),route:{points:copy(e.route),ok:checks.get(e.id)?.ok===true&&!e.failed&&!e.pendingRouting}}));
    const labels=[],fonts=[],nodes=native.nodes.map(n=>{
      const rows=texts(n),alias=native.studioPresentation?.nodes?.[n.id]?.alias;
      if(alias&&rows.length){rows[0].text=String(alias);rows[0].aliasWidth=Math.max(24,n.w-32);}
      for(const row of rows){
        const natural=root.SemanticPublication.width(row.text,row.font),compressed=row.aliasWidth&&row.text.length*14>row.aliasWidth;
        const width=compressed?row.aliasWidth:natural,left=row.x-(row.anchor==='middle'?width/2:row.anchor==='end'?width:0);
        fonts.push(compressed?row.font*Math.min(1,width/Math.max(1,natural)):row.font);
        if(![row.x,row.y,row.font,width].every(Number.isFinite)||left<-.5||left+width>n.w+.5||row.y-row.font<-.5||row.y+row.font*.25>n.h+.5)labels.push({node:n.id,text:row.text});
      }
      const titleRows=n.modelHeading?rows.length-1:n.expanded?Math.min(2,G.appearance(n.semantic).lines.length):G.appearance(n.semantic).lines.length;
      return {...n.semantic,paper:{...n.semantic.paper,lines:rows.slice(0,titleRows).map(r=>r.text),captions:rows.slice(titleRows).map(r=>r.text)}};
    });
    const R=root.EdgeRouterLabRouting,contacts=[],overlaps=[];let crossings=0;
    const edges=native.edges.filter(e=>!e.draft);
    for(let i=0;i<edges.length;i++)for(let j=i+1;j<edges.length;j++){
      const a=edges[i],b=edges[j],same=a.contract?.wire===b.contract?.wire;
      for(const hit of R.wireContacts(a.route,b.route)){
        if(hit.kind==='crossing')crossings++;else if(!same)contacts.push({edges:[a.id,b.id],...hit.point});
      }
      let length=0;for(let u=1;u<a.route.length;u++)for(let v=1;v<b.route.length;v++)length+=R.overlap(a.route[u-1],a.route[u],b.route[v-1],b.route[v]);
      if(length>1e-5)overlaps.push({edges:[a.id,b.id],length,same_value:same});
    }
    const graph={...cut,nodes,positions:new Map(native.nodes.map(n=>[n.id,{...n}])),constraint_receipts:copy(cut.constraint_receipts||[])};
    const prepared={routes,quality:{native_width_px:native.canvas[0],native_height_px:native.canvas[1],line_geometry:{crossings,unrelated_contacts:contacts,overlapping_paths:overlaps},
      route_failures:routes.filter(e=>!e.route.ok).map(e=>e.id),unplaced_port_labels:labels,min_canvas_font_px:fonts.length?Math.min(...fonts):0,
      issues:[...(!validation.source.ok?['native-source-invalid']:[]),...(!validation.layout.ok?['native-layout-invalid']:[]),...(labels.length?['native-text-outside-glyph']:[])]}};
    root.SemanticEngine.auditConstraintRoutes(graph,routes);
    graph.expression_goals=Goals.build(ir,graph.architecture);graph.expression_coverage=Goals.evaluate(graph.expression_goals,graph,prepared,ir);
    graph.summary_goals=Summary.build(ir,graph.architecture);graph.summary_coverage=Summary.evaluate(graph.summary_goals,ir,graph,prepared);
    return {graph,prepared,nativeResult:result};
  }
  function eligible(graph){const state=graph.generic.state;return !state.moduleCuts?.length&&state.paperAdaptive===true&&(state.paperMedium||'canvas')==='canvas'&&state.paperGranularity==='roles'&&state.paperAuto!==false&&!state.paperCanonical&&!state.paperRelation&&
    !Object.keys(state.offsets||{}).length&&!graph.edges.some(e=>e.draft)&&!graph.sourceDraftOperations?.length;}
  function select(baseline,options,previous){
    const native=baseline.graph,state=native.generic.state;
    if(!eligible(native))return baseline;
    if(previous?.studioPresentation)native.studioPresentation=copy(previous.studioPresentation);
    // A restored document already names its effective, validated cut. Never
    // let a saved receipt license bindings or replace its manual geometry.
    if(state.nativeAdaptiveBase){native.nativeAdaptive={restored:true,requested:true,rule_version:A.VERSION,selected:A.metrics(measured(baseline)),selected_role_details:state.paperRoleDetails||[],selected_role_paths:state.paperRolePaths||[],selected_expression_details:state.paperExpressionDetails||[],scope:'Saved effective requests and native geometry independently validated; no new selection or model execution.'};return baseline;}
    const ir=native.generic.ir,initial=measured(baseline),attempts=[],preflights=[],seen=new Set();let chosen=initial,selectedState={...state},count=0;
    const planning=state.paperAdaptivePolicy==='structure';
    while(count<3&&preflights.length<36){
      const opportunities=A.candidates(chosen.graph,selectedState).filter(c=>!seen.has(c.id)),shortlist=[];
      for(const candidate of opportunities.slice(0,Math.min(12,36-preflights.length))){
        seen.add(candidate.id);const next=A.apply(selectedState,candidate),graph=G.project(ir,next),before=new Set(chosen.graph.nodes.map(n=>n.id)),added=graph.nodes.filter(n=>!before.has(n.id));
        const request=candidate.kind==='roles'?graph.publication.role_frontier?.detail_requests?.find(r=>r.node===candidate.node):null;
        const path=candidate.kind==='role-path'?graph.publication.role_frontier?.path_requests?.find(r=>r.node===candidate.node&&r.certificate===candidate.certificate&&G.stable(r.role)===G.stable(candidate.role)):null;
        let reason=request&&request.status!=='expanded'||candidate.kind==='role-path'&&(!path||path.status!=='exposed')?'protected-or-budgeted-role':!added.length?'no-new-visible-detail':null;
        const estimate=added.filter(n=>['compute','opaque','control'].includes(n.kind)).length,benefit=reason||!planning?null:A.preview(ir,chosen,graph);
        if(benefit?.only_summary_internal&&!benefit.structure&&!benefit.critical)reason='dependency-structure-already-expressed';
        preflights.push({candidate,added_nodes:added.length,estimated_operations:estimate,estimated_benefit:benefit,reason});
        if(!reason)shortlist.push({candidate,next,benefit,estimate,added:added.length});
      }
      shortlist.sort((a,b)=>planning?(A.compare({...a.benefit,cost:1,score:[a.benefit.critical,a.benefit.structure,a.benefit.detail]},{...b.benefit,cost:1,score:[b.benefit.critical,b.benefit.structure,b.benefit.detail]})||b.estimate/Math.max(1,b.added)-a.estimate/Math.max(1,a.added)||a.candidate.id.localeCompare(b.candidate.id)):
        b.candidate.priority-a.candidate.priority||b.estimate/Math.max(1,b.added)-a.estimate/Math.max(1,a.added)||a.candidate.id.localeCompare(b.candidate.id));
      if(planning&&shortlist[0]?.candidate.kind==='roles'){
        const at=shortlist.findIndex((item,i)=>i>0&&item.candidate.kind==='role-path'&&item.candidate.node===shortlist[0].candidate.node);if(at>1)shortlist.splice(1,0,...shortlist.splice(at,1));
      }
      for(const item of shortlist)seen.delete(item.candidate.id);
      if(!shortlist.length){if(opportunities.length>12)continue;break;}
      const trials=[];
      for(const item of shortlist.slice(0,Math.min(planning?2:1,3-count))){
        seen.add(item.candidate.id);count++;
        try{
          const prepared=G.prepare({task:'generic-build',ir,state:{...item.next,nativeAdaptiveBase:requests(state)},options,extra:{authoring:native.generic.authoring,migration:native.generic.migration,layouts:native.generic.layouts}});
          if(native.studioPresentation)prepared.graph.studioPresentation=copy(native.studioPresentation);
          const trial=measured(prepared),assessment=A.assess(ir,chosen,trial);
          trials.push({item,trial,assessment,receipt:{opportunity:item.candidate,requested_state:requests(item.next),...assessment,eligible:assessment.accepted,accepted:false,comparison_round:attempts.length}});
        }catch(error){attempts.push({opportunity:item.candidate,eligible:false,accepted:false,reasons:['native-preparation-rejected'],error:String(error.message)});}
      }
      const best=trials.filter(t=>t.assessment.accepted).sort((a,b)=>A.compare(a.assessment.selection_benefit,b.assessment.selection_benefit)||a.item.candidate.id.localeCompare(b.item.candidate.id))[0];
      for(const trial of trials){if(trial===best)trial.receipt.accepted=true;else if(trial.receipt.eligible){trial.receipt.reasons.push('lower-measured-benefit');seen.delete(trial.item.candidate.id);}attempts.push(trial.receipt);}
      if(best){chosen=best.trial;selectedState=best.item.next;}
    }
    const result=chosen.nativeResult;
    // Also record a base for a rejected/no-op selection: disabling must restore
    // the user's requests, and reopening must not run an expensive search.
    if(!result.graph.generic.state.nativeAdaptiveBase)result.graph.generic.state={...result.graph.generic.state,nativeAdaptiveBase:requests(state)};
    result.graph.nativeAdaptive={requested:true,rule_version:A.VERSION,policy:planning?'structure':'detail',baseline:A.metrics(initial),selected:A.metrics(chosen),attempts,preflights,
      selected_role_details:selectedState.paperRoleDetails||[],selected_role_paths:selectedState.paperRolePaths||[],selected_expression_details:selectedState.paperExpressionDetails||[],
      unmeasured_opportunities:A.candidates(chosen.graph,selectedState).filter(c=>!seen.has(c.id)).length,measurement_limit:3,preflight_limit:36,
      scope:'Summary local role/relation selection measured on native glyph text, exact operand bindings, validated physical ports and actual routes; metrics describe selection-time geometry. No global optimum or execution claim.'};
    return result;
  }
  function patch(graph,value){
    const state=graph.generic.state,next={...value},manual=keys.some(k=>Object.hasOwn(next,k));
    if(state.paperAdaptive&&manual){next.paperAdaptive=false;next.nativeAdaptiveBase=null;}
    else if(state.nativeAdaptiveBase){
      for(const key of keys)if(!Object.hasOwn(next,key))next[key]=copy(state.nativeAdaptiveBase[key]||[]);next.nativeAdaptiveBase=null;
    }
    return next;
  }
  function restored(graph){
    // Edited wrappers can carry arbitrary old receipt JSON. The native graph
    // has already passed source/render/geometry validation at this boundary.
    delete graph.nativeAdaptive;
    if(eligible(graph))graph.nativeAdaptive={restored:true,requested:true,rule_version:A.VERSION,selected:A.metrics(measured({graph})),
      selected_role_details:copy(graph.generic.state.paperRoleDetails||[]),selected_role_paths:copy(graph.generic.state.paperRolePaths||[]),selected_expression_details:copy(graph.generic.state.paperExpressionDetails||[]),
      scope:'Restored effective requests and current native geometry; incoming selection receipts discarded. Not a newly certified automatic choice or model execution.'};
    return graph;
  }
  root.ArchCanvasAdaptiveView={select,measured,patch,eligible,restored};
})(typeof window!=='undefined'?window:globalThis);
