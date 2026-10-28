/* Source-led runtime supplementation. Canonical facts never become view rewrites. */
(function(root){
  'use strict';
  const copy=x=>JSON.parse(JSON.stringify(x)),cache=new WeakMap();
  const observed=id=>id==='runtime-observations'||id.startsWith('runtime:');
  function enabled(ir,state){return state.mode==='merged'&&ir.runtime?.runs?.length>0;}
  // Recheck bridge identities against the saved receipt and both canonical
  // graphs. A saved presentation index cannot invent a wire or an operand.
  function regions(ir,run){
    const ix=ir.source_runtime_index,r=ir.runtime?.runs?.[run],by=new Map(ir.nodes.map(n=>[n.id,n])),edges=new Map(ir.edges.map(e=>[e.id,e]));
    if(ix?.schema!=='source-runtime-integration/1'||ix.receipt_digest!==ir.runtime.trace_digest||!ir.runtime.source_unchanged||ir.runtime.isolation?.status!=='passed'||r?.status!=='passed'||r.truncated||!r.replay?.matched)return [];
    const generation=ir.runtime.binding?.source_generation||{},sourceRoot=ir.runtime.binding?.source_root?.replace(/\/$/,'');
    if(!sourceRoot||ir.sources.some(s=>ir.nodes.some(n=>!observed(n.id)&&n.source?.some(t=>t.file===s.path))&&generation[s.physical.slice(sourceRoot.length+1)]!==s.sha256))return [];
    const prefix='runtime:'+run+':',events=new Map(r.events.map(e=>[prefix+e.id,e])),calls=new Map(r.module_events.filter(e=>e.event==='enter').map(e=>[prefix+e.id,e])),exits=new Map(r.module_events.filter(e=>e.event==='exit').map(e=>[prefix+e.id,e]));
    const candidates=ix.regions.filter(v=>v.run===run),counts=new Map();for(const v of candidates)counts.set(v.source,(counts.get(v.source)||0)+1);
    const valid=candidates.filter(v=>{
      const source=by.get(v.source),call=calls.get(v.call),exit=exits.get(v.call);
      if(counts.get(v.source)!==1||source?.kind!=='opaque'||!call||!call.parent_call||!exit?.output_is_tensor||exit.outputs?.length!==1||v.case!==r.case||v.mode!==r.mode||call.module_type!==v.module_type||call.path!==v.module_path)return false;
      const sites=call.source_stack||[];
      if(!sites.some(s=>{
        const same=n=>n.source?.some(t=>t.file===sourceRoot+'/'+s.file&&t.symbol===s.symbol&&['line','end_line','column','end_column'].every(k=>t[k]!=null&&t[k]===s[k]));
        const matches=ir.nodes.filter(n=>!observed(n.id)&&['compute','opaque'].includes(n.kind)&&same(n));return matches.length===1&&matches[0].id===v.source;
      }))return false;
      const descendants=new Set([v.call]);for(const [id,c]of calls)if(descendants.has(prefix+c.parent_call))descendants.add(id);
      const expected=[...events].filter(([,e])=>descendants.has(prefix+e.module_call));
      if(!expected.length||expected.length!==v.events.length||new Set(v.events).size!==v.events.length||expected.some(([id,e])=>!v.events.includes(id)||e.mutable||by.get(id)?.operator!==e.operator||JSON.stringify(by.get(id)?.inputs)!==JSON.stringify(e.inputs)||JSON.stringify(by.get(id)?.outputs)!==JSON.stringify(e.outputs)))return false;
      const out=exit.outputs[0],producer=events.get(v.output?.source);
      if(v.output?.source!==prefix+out.producer||v.output?.source_port!==String(out.slot)||v.output?.tensor!==out.id||!v.events.includes(v.output.source)||!producer?.outputs.some(t=>t.id===out.id&&String(t.slot)===String(out.slot)))return false;
      if(ir.edges.some(e=>e.source===v.source&&(!['data','alias','interface-binding'].includes(e.kind)||e.source_port!=='out')))return false;
      const set=new Set(v.events),ports=new Set(),used=new Set(),resources=new Set();
      for(const e of ir.edges.filter(e=>set.has(e.target)&&!set.has(e.source))){
        if(['parameter','buffer'].includes(by.get(e.source)?.kind)){resources.add(e.source);continue;}
        const b=v.inputs.find(b=>b.runtime_edge===e.id),a=b&&edges.get(b.source_edge),t=events.get(e.target)?.inputs[Number(e.target_port)];
        if(e.kind!=='data'||e.evidence!=='runtime-tensor'||String(t?.slot)!==e.source_port||e.source!==prefix+(t?.producer||('unresolved:'+t?.id)))return false;
        if(!b||!a||a.target!==v.source||a.kind!=='data'||a.condition||a.target_port!==b.argument_port||e.target!==b.target||e.target_port!==b.target_port||t?.id!==b.tensor||ports.has(a.id))return false;
        const bound=(call.input_bindings||[]).filter(t=>t.id===b.tensor&&!t.component&&t.port===b.argument_port);if(bound.length!==1)return false;
        ports.add(a.id);used.add(b.runtime_edge);
      }
      return used.size===v.inputs.length&&resources.size===v.resources.length&&v.resources.every(id=>resources.has(id));
    });
    // Nested overlapping regions and repeated executions need an occurrence
    // interface. Never fuse different invocations into one source operation.
    return valid.filter(v=>!valid.some(w=>w!==v&&v.events.some(id=>w.events.includes(id))));
  }
  function prepare(ir,run){
    let rows=cache.get(ir);if(!rows)cache.set(ir,rows=new Map());if(rows.has(run))return rows.get(run);
    const selected=regions(ir,run),by=new Map(ir.nodes.map(n=>[n.id,n])),source=ir.nodes.filter(n=>!observed(n.id)).map(copy),outBy=new Map(source.map(n=>[n.id,n]));
    const owners=new Map(),inputs=new Map(),outputs=new Map(),eventSet=new Set(),resourceOwners=new Map();
    for(const v of selected){
      const n=outBy.get(v.source);n.kind='composite';n.granularity='composite';n.source_runtime={...copy(v),static_kind:'opaque',scope:'only this recorded input and mode; unobserved paths remain unknown'};
      for(const id of v.events){eventSet.add(id);owners.set(id,n.id);const child=copy(by.get(id));child.parent=n.id;source.push(child);}
      owners.set(v.call,n.id);
      for(const id of v.resources){if(!resourceOwners.has(id))resourceOwners.set(id,[]);resourceOwners.get(id).push(n.id);}
      for(const b of v.inputs)inputs.set(b.source_edge,{...b,owner:v.source,call:v.call});outputs.set(v.source,v);
    }
    const sourceRoot=source.find(n=>!n.parent)?.id;
    for(const [id,os]of resourceOwners){const child=copy(by.get(id));child.parent=os.length===1?os[0]:sourceRoot;source.push(child);owners.set(id,child.parent);}
    const bridgedInputs=new Set(selected.flatMap(v=>v.inputs.map(b=>b.runtime_edge))),edges=[];
    for(const e of ir.edges){
      if(!observed(e.source)&&!observed(e.target)){
        const edge=copy(e),input=inputs.get(e.id),output=outputs.get(e.source);
        if(input){edge.target=input.target;edge.target_port=input.target_port;}
        if(output){edge.source=output.output.source;edge.source_port=output.output.source_port;}
        if(input||output)edge.runtime_bridge={source_binding:copy(e),...(input?{input:copy(input)}:{}),...(output?{output:{owner:output.source,call:output.call,...copy(output.output)}}:{}),run,case:ir.runtime.runs[run].case,mode:ir.runtime.runs[run].mode};
        edges.push(edge);
      }else if(!bridgedInputs.has(e.id)&&eventSet.has(e.target)&&(eventSet.has(e.source)||resourceOwners.has(e.source)))edges.push(copy(e));
    }
    const value={ir:{...ir,nodes:source,edges},selected,owners,run};rows.set(run,value);return value;
  }
  function project(ir,state,engine){
    if(state.moduleCuts?.length)validateCuts(scopeIR(ir,state),state.moduleCuts);
    if(state.moduleCuts?.length&&!enabled(ir,state))return mixedProject(ir,{...state,moduleCuts:state.moduleCuts.filter(c=>ir.nodes.some(n=>n.id===c.id&&n.kind==='composite'))},engine);
    if(!enabled(ir,state))return engine.project(ir,state);
    const run=Number.isInteger(state.runtimeInlineRun)&&ir.runtime.runs[state.runtimeInlineRun]?state.runtimeInlineRun:0;
    const prepared=prepare(ir,run),view=prepared.ir;
    const render=next=>next.moduleCuts?.length?mixedProject(view,{...next,moduleCuts:next.moduleCuts.filter(c=>view.nodes.some(n=>n.id===c.id&&n.kind==='composite'))},engine):engine.project(view,next);
    let cut=render(state);
    if(state.runtimeInlineInitialized!==run&&!state.paperCanonical){
      const open=[...new Set([...(cut.publication?.open||state.open||[]),...prepared.selected.map(v=>v.source)])];
      cut=render({...state,paperAuto:false,open});
    }
    for(const n of cut.nodes)if(n.source_runtime){n.paper={...n.paper,captions:[`CPU 观测 · ${ir.runtime.runs[run].case} / ${ir.runtime.runs[run].mode}`,'未覆盖输入仍未知']};}
    const canonicalEdges=new Map(ir.edges.map(e=>[e.id,e])),viewEdges=new Map(view.edges.map(e=>[e.id,e]));
    function provenance(e){
      const proofs=(e.originals||[e.id]).map(id=>viewEdges.get(id)?.runtime_bridge).filter(Boolean);if(proofs.length)e.runtime_bridges=copy(proofs);
      if(e.runtime_bridge){const original=canonicalEdges.get(e.id);e.canonical_source=original.source;e.canonical_target=original.target;}
      for(const m of e.bundle_members||[])provenance(m);
    }
    cut.edges.forEach(provenance);
    // Normalize the ledger back to the complete immutable IR. Unshown runs,
    // wrappers and redundant known operators remain inspectable attachments.
    for(const [key,all]of [['node_accounting',ir.nodes],['edge_accounting',ir.edges]]){
      const seen=new Set(Object.values(cut[key]).flat());
      for(const item of all)if(!seen.has(item.id))cut[key].attached.push(item.id);
    }
    const rootId=cut.nodes.find(n=>!n.parent)?.id||cut.nodes[0]?.id;
    for(const n of ir.nodes)if(!cut.representatives[n.id])cut.representatives[n.id]=cut.representatives[prepared.owners.get(n.id)]||rootId;
    const record={schema:'source-runtime-view/1',run,case:ir.runtime.runs[run].case,mode:ir.runtime.runs[run].mode,regions:copy(prepared.selected),raw_trace:'available in CPU 轨迹 evidence view',unplaced:copy(ir.source_runtime_index?.unplaced||[]),scope:'selected invocation evidence; canonical static unknowns and all source branches preserved'};
    cut.publication={...cut.publication,source_runtime:record};
    if(rootId){const notes=cut.annotations.get(rootId)||[];notes.push({annotation_kind:'source-runtime-evidence',...record});cut.annotations.set(rootId,notes);}
    return cut;
  }
  // Compile each requested source scope with Summary's own publication rules,
  // then run ONE canonical projection. Never splice SVGs or trust saved receipts.
  const levels=['f0','f1','overview','modules','stages','semantic','roles','detailed','source'];
  function moduleIndex(ir){
    const E=root.SemanticEngine,idx=E.index(ir),counts=new Map(),depths=new Map();
    function size(id){if(counts.has(id))return counts.get(id);let count=1,depth=0;for(const child of idx.children.get(id)||[]){count+=size(child);depth=Math.max(depth,1+depths.get(child));}counts.set(id,count);depths.set(id,depth);return count;}
    ir.nodes.forEach(n=>size(n.id));
    return ir.nodes.filter(n=>n.kind==='composite').map(n=>({id:n.id,label:n.label||n.id,parent:n.parent,count:counts.get(n.id),maxDepth:depths.get(n.id)}));
  }
  function validateCuts(ir,cuts){
    if(!Array.isArray(cuts)||cuts.length>ir.nodes.length)throw Error('模块切面列表无效。');
    const by=new Map(ir.nodes.map(n=>[n.id,n])),seen=new Set();
    for(const c of cuts){if(!c||typeof c!=='object'||Object.keys(c).some(k=>!['id','level','depth','open'].includes(k))||by.get(c.id)?.kind!=='composite'||seen.has(c.id)||!levels.includes(c.level)||
      c.depth!==undefined&&(!Number.isInteger(c.depth)||c.depth<0||c.depth>ir.nodes.length)||c.open!==undefined&&(!Array.isArray(c.open)||c.open.some(id=>typeof id!=='string')))throw Error('模块切面或源码深度无效。');seen.add(c.id);}
    return cuts;
  }
  function mixedProject(ir,state,engine){
    const E=root.SemanticEngine,P=root.SemanticPublication,F=root.SemanticCompositionLayout;
    validateCuts(ir,state.moduleCuts);
    const plain={...state};delete plain.moduleCuts;
    let captured;
    const capture={...engine,semanticOnly:true,project:(value,view,plan,opts={})=>{
      if(plan){captured={view,plan,opts};return engine.project(value,view,plan,opts);}
      return view.paperCanonical?P.projectCanonical(value,view,capture):P.project(value,view,capture);
    }};
    const compile=view=>{captured=null;const cut=capture.project(ir,view);return {cut,policy:captured?.opts||{}};};
    const base=compile(plain),raw=E.index(ir),by=new Map(base.cut.nodes.map(n=>[n.id,copy(n)]));
    const reps=new Map(Object.entries(base.cut.representatives)),bindings=new Map(base.policy.bindings||[]),metadata=new Set(base.policy.metadata||[]);
    const edgeAttachments=new Map(base.policy.edgeAttachments||[]),metadataKinds=new Map(base.policy.metadataKinds||[]);
    const presentations=new Map(base.cut.edges.map(e=>[e.id,e]));
    const expanded=new Set(base.cut.nodes.filter(n=>base.cut.positions.get(n.id)?.expanded).map(n=>n.id));
    const navigation=new Map([...raw.nodes,...base.cut.idx.nodes]);
    const touched=new Set(),rows=[],rank=id=>{let n=raw.nodes.get(id),d=0;while(n?.parent){d++;n=raw.nodes.get(n.parent);}return d;};
    const isWithin=(id,owner,idx)=>{const seen=new Set();while(id&&!seen.has(id)){if(id===owner)return true;seen.add(id);id=idx.get(id)?.parent;}return false;};
    const runtimeNode=id=>{while(id){if(observed(id))return true;id=raw.nodes.get(id)?.parent;}return false;};
    // More specific children override their ancestors, independent of click order.
    for(const request of state.moduleCuts.slice().sort((a,b)=>rank(a.id)-rank(b.id)||a.id.localeCompare(b.id))){
      let at=raw.nodes.get(request.id),runtime=false;
      while(at){if(observed(at.id))runtime=true;at=raw.nodes.get(at.parent);}
      if(state.mode==='runtime'&&!runtime||state.mode==='source'&&runtime)continue;
      const scope=new Set(),walk=id=>{scope.add(id);touched.add(id);for(const c of raw.children.get(id)||[])walk(c);};walk(request.id);
      const anchor=by.get(request.id)||copy(raw.nodes.get(request.id));
      // A latent scope needs its real source ancestors exposed. Sibling modules
      // retain their current representatives rather than inheriting this depth.
      const chain=[];let parent=raw.nodes.get(request.id)?.parent;
      while(parent&&!by.has(parent)){
        if(state.mode==='runtime'&&!runtimeNode(parent))break;
        chain.unshift(parent);parent=raw.nodes.get(parent)?.parent;
      }
      for(const id of chain){const n=copy(raw.nodes.get(id));by.set(id,n);expanded.add(id);}
      anchor.parent=raw.nodes.get(request.id).parent;
      const affected=new Set([...by].filter(([id,n])=>scope.has(id)||isWithin(id,request.id,navigation)||n.canonical_members?.length&&n.canonical_members.every(id=>scope.has(id))).map(([id])=>id));
      let local;
      if(request.level==='source'){
        const depth=request.depth??ir.nodes.length,open=[];
        const visit=(id,d)=>{if(d<depth&&(raw.children.get(id)||[]).length){open.push(id);for(const c of raw.children.get(id)||[])visit(c,d+1);}};visit(request.id,0);
        local=compile({...plain,paperCanonical:true,paperAuto:false,open:request.open||open,nativeSourceFocus:request.id});
      }else{
        // Select a frontier in the whole model before extracting its scope.
        // Focusing a publication panel changes budgets, aliases and return
        // attachments; it is not the same operation as changing module depth.
        let view={...plain,paperCanonical:false,paperAuto:true,paperFocus:null,paperRelation:null,paperRepresentative:false,open:[],paperAdaptive:false};
        const detail=()=>{if(request.level==='f1')view=F.certifiedDetails(ir,view,{semanticOnly:true});};
        if(['f0','f1'].includes(request.level)){view=F.frontier(view,request.level==='f0'?'overview':'detail');detail();}
        else view.paperGranularity=request.level;
        local=compile(view);
        // A latent instance has no frontier in the global representative view.
        // Only that case needs Summary's separately focused source panel.
        if(!local.cut.nodes.some(n=>n.id===request.id)){
          view={...view,paperFocus:request.id,paperAuto:true,open:[]};detail();local=compile(view);
        }
        if(request.open){
          // Summary's frontier receipts also contain latent region openings
          // consumed during lowering. Those are valid even when no longer in
          // the final drawing index; arbitrary IDs still have no authority.
          const allowed=new Set([...(local.cut.publication?.open||[]),...[...local.cut.idx.children].filter(([id,kids])=>id&&kids.length).map(([id])=>id)]);
          if(request.open.some(id=>!allowed.has(id)))throw Error('局部展开节点不属于当前语义层级。');
          local=compile({...view,paperAuto:false,open:request.open});
        }
      }
      if(request.level==='source'&&request.open?.some(id=>!scope.has(id)||!raw.children.get(id)?.length))throw Error('局部展开节点不属于当前源码模块。');
      // boundary_ports is the cut inventory of real presentation regions
      // (Add & Norm, role paths, repeated calls), not a panel-only terminal.
      // Removing those regions strands their children and destroys the DAG.
      const keep=local.cut.nodes.filter(n=>!n.boundary_edge&&n.semantic_type!=='boundary-interface-group'&&isWithin(n.id,request.id,local.cut.idx.nodes));
      for(const id of affected){by.delete(id);expanded.delete(id);}
      by.set(anchor.id,anchor);
      for(const n of keep){const value=copy(n);if(n.id===anchor.id)value.parent=anchor.parent;by.set(n.id,value);if(local.cut.positions.get(n.id)?.expanded)expanded.add(n.id);navigation.set(n.id,n);}
      const keptIds=new Set(keep.map(n=>n.id));
      for(const e of local.cut.edges)if(keptIds.has(e.source)||keptIds.has(e.target))presentations.set(e.id,e);
      for(const e of ir.edges)if(scope.has(e.source)||scope.has(e.target)){
        edgeAttachments.delete(e.id);
        if(local.policy.edgeAttachments?.has(e.id))edgeAttachments.set(e.id,local.policy.edgeAttachments.get(e.id));
      }
      for(const id of scope){
        const rep=local.cut.representatives[id];reps.set(id,by.has(rep)?rep:request.id);
        bindings.delete(id);metadata.delete(id);
        const binding=local.policy.bindings?.get(id);
        // Panel extraction may redirect an alias to a synthetic boundary port.
        // Restore its exact canonical binding when joining the full model.
        if(binding){const original=local.cut.idx.nodes.get(binding.source)?.boundary_edge?ir.edges.find(e=>e.id===binding.id):binding;if(original)bindings.set(id,original);}
        if(local.policy.metadata?.has(id))metadata.add(id);
        metadataKinds.delete(id);if(local.policy.metadataKinds?.has(id))metadataKinds.set(id,local.policy.metadataKinds.get(id));
      }
      for(const id of chain)reps.set(id,id);
      let ancestor=raw.nodes.get(request.id)?.parent;while(ancestor){expanded.add(ancestor);ancestor=raw.nodes.get(ancestor)?.parent;}
      reps.set(request.id,request.id);
      rows.push({id:request.id,level:request.level,depth:request.depth??null,canonicalNodes:scope.size,visibleNodes:keep.length,open:local.cut.publication?.open||[]});
    }
    // A base presentation group can cover an ancestor and a requested subtree.
    // Keep the group for untouched facts; ensure every representative exists.
    for(const [id,rep]of reps)if(!by.has(rep)){
      let at=raw.nodes.get(id);while(at&&!by.has(at.id))at=raw.nodes.get(at.parent);
      if(at)reps.set(id,at.id);else reps.delete(id);
    }
    for(const n of by.values()){
      let parent=n.parent;const seen=new Set();while(parent&&!by.has(parent)&&!seen.has(parent)){seen.add(parent);parent=navigation.get(parent)?.parent;}n.parent=parent||null;
    }
    const plan={...base.cut.architecture,nodes:[...by.values()]},idx=E.index(plan),roots=idx.children.get(null)||[];
    // Exact binding traversal and every condition/slot/kind are handled by the
    // original canonical projector, including bundles and dependency accounting.
    const cut=engine.project(ir,{...plain,view:'architecture',details:false,open:[...expanded]},plan,{
      roots,bindings,metadata,metadataKinds,edgeAttachments,metadataTargets:reps,semanticOnly:true,exposedResources:new Set([...by.values()].filter(n=>n.kind==='parameter').map(n=>n.id)),
      presentEdges:base.policy.presentEdges
    });
    // Retain every unaffected outer dependency exactly, including existing
    // bundles, conditions and attachment policies. Only touching paths lower
    // through the newly selected source scope.
    const changed=new Set(ir.edges.filter(e=>touched.has(e.source)||touched.has(e.target)).map(e=>e.id));
    const originals=e=>[e.id,...(e.originals||[]),...(e.bundle_members||[]).flatMap(originals)];
    for(const edge of base.cut.edges)if(originals(edge).some(id=>changed.has(id)))for(const id of originals(edge))changed.add(id);
    const retained=base.cut.edges.filter(edge=>!originals(edge).some(id=>changed.has(id))),retainedIds=new Set(retained.flatMap(originals));
    cut.edges=[...retained,...cut.edges.filter(edge=>!originals(edge).some(id=>retainedIds.has(id)))];
    for(const e of cut.edges){const p=presentations.get(e.id);if(p&&['source','target','source_port','target_port'].every(k=>p[k]===e[k])&&p.paper_labels)e.paper_labels=copy(p.paper_labels);}
    const oldBuckets=new Map(Object.entries(base.cut.edge_accounting).flatMap(([key,ids])=>ids.map(id=>[id,key])));
    const newBuckets=new Map(Object.entries(cut.edge_accounting).flatMap(([key,ids])=>ids.map(id=>[id,key])));
    cut.edge_accounting=Object.fromEntries(Object.keys(cut.edge_accounting).map(key=>[key,[]]));
    for(const edge of ir.edges){const key=(changed.has(edge.id)?newBuckets:oldBuckets).get(edge.id);cut.edge_accounting[key||'excluded'].push(edge.id);}
    const mixedAnnotations=cut.annotations;cut.annotations=new Map([...base.cut.annotations].filter(([id])=>by.has(id)&&!touched.has(id)));
    for(const [id,notes]of mixedAnnotations)if(touched.has(id)||!cut.annotations.has(id))cut.annotations.set(id,notes);
    const fullNodes=new Map([...navigation,...cut.idx.nodes]);
    cut.idx=E.index({nodes:[...fullNodes.values()]});cut.positions.context.idx=cut.idx;
    cut.architecture={...plan,nodes:[...fullNodes.values()]};
    cut.publication={...base.cut.publication,open:[...expanded],mixed:{schema:'mixed-semantic-frontier/1',scopes:rows,sourceNodes:ir.nodes.length,sourceEdges:ir.edges.length}};
    return cut;
  }
  function fullyExpandedIR(ir,state){return enabled(ir,state)?prepare(ir,Number.isInteger(state.runtimeInlineRun)?state.runtimeInlineRun:0).ir:ir;}
  function scopeIR(ir,state){
    if(!ir.runtime?.runs?.length)return ir;
    const run=Number.isInteger(state.runtimeInlineRun)&&ir.runtime.runs[state.runtimeInlineRun]?state.runtimeInlineRun:0;
    return {...ir,nodes:[...new Map([...ir.nodes,...prepare(ir,run).ir.nodes].map(n=>[n.id,n])).values()]};
  }
  const api={enabled,regions,prepare,project,fullyExpandedIR,scopeIR,moduleIndex,validateCuts,levels};root.SummarySourceRuntime=api;if(typeof module==='object'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);
