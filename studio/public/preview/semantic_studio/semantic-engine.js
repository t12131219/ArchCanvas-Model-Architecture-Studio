/* Canonical evidence stays immutable; semantic grouping and layout are views. */
(function(root){
  'use strict';
  const A=root.SemanticArchitecture||(typeof require==='function'?require('./architecture.js'):null);
  const L=root.SemanticLayout||(typeof require==='function'?require('./architecture-layout.js'):null);
  const C=root.SemanticRelationConstraints||(typeof require==='function'?require('./relation-constraints.js'):null);
  const clone=x=>JSON.parse(JSON.stringify(x)),plans=new WeakMap();
  function index(ir){
    const nodes=new Map(ir.nodes.map(n=>[n.id,n])),children=new Map();
    for(const n of ir.nodes){if(!children.has(n.parent||null))children.set(n.parent||null,[]);children.get(n.parent||null).push(n.id);}
    return {nodes,children};
  }
  function architecture(ir){if(!plans.has(ir))plans.set(ir,A.build(ir));return plans.get(ir);}
  function drawingOrder(nodes,idx){
    const depths=new Map(),depth=id=>{if(!depths.has(id))depths.set(id,idx.nodes.get(id)?.parent?depth(idx.nodes.get(id).parent)+1:0);return depths.get(id);};
    return nodes.slice().sort((a,b)=>depth(a.id)-depth(b.id));
  }
  const paper=()=>root.SemanticPublication||(typeof require==='function'?require('./publication.js'):null);
  function viewIndex(ir,state={}){return index(state.view==='publication'&&!state.paperCanonical?paper().plan(ir):state.view==='architecture'?architecture(ir):ir);}
  function validate(ir){
    if(ir.schema!=='archcanvas-source-semantic/2'||!Array.isArray(ir.nodes)||!Array.isArray(ir.edges))throw Error('不是通用语义 IR v2');
    if(ir.nodes.length>16000||ir.edges.length>50000)throw Error('超过画布导入预算');
    const idx=index(ir);if(idx.nodes.size!==ir.nodes.length)throw Error('重复节点 ID');
    for(const n of ir.nodes){if(n.parent&&!idx.nodes.has(n.parent))throw Error('父节点不存在');const seen=new Set();let p=n;while(p){if(seen.has(p.id))throw Error('层级成环');seen.add(p.id);p=idx.nodes.get(p.parent);}}
    const edgeIds=new Set();
    for(const e of ir.edges){if(edgeIds.has(e.id))throw Error('重复连接 ID');edgeIds.add(e.id);if(!idx.nodes.has(e.source)||!idx.nodes.has(e.target))throw Error('连接端点不存在');}
    return true;
  }
  function project(ir,state,derivedPlan=null,options={}){
    if(state.view==='publication'&&!derivedPlan){
      const engine=options.semanticOnly?{...api,semanticOnly:true,project:(value,view,plan,inner={})=>api.project(value,view,plan,{...inner,semanticOnly:true})}:api;
      return state.paperCanonical?paper().projectCanonical(ir,state,engine):paper().project(ir,state,engine);
    }
    const plan=derivedPlan||(state.view==='architecture'?architecture(ir):ir),idx=index(plan),mode=state.mode||'source',open=new Set(state.open),visible=new Set();
    const roots=options.roots||(mode==='runtime'&&idx.nodes.has('runtime-observations')?['runtime-observations']:idx.children.get(null)||[]);
    const compact=state.view==='architecture'&&!state.details,bindings=new Map(),resources=new Set(),insBy=new Map(),usesBy=new Map();
    for(const e of ir.edges){if(!insBy.has(e.target))insBy.set(e.target,[]);insBy.get(e.target).push(e);if(!usesBy.has(e.source))usesBy.set(e.source,[]);usesBy.get(e.source).push(e);}
    if(compact)for(const n of ir.nodes){
      const ins=insBy.get(n.id)||[],uses=usesBy.get(n.id)||[];
      // An explicit presentation policy owns the complete binding set. Adding
      // compact defaults back would erase its focused-boundary exceptions.
      if(!options.bindings&&n.kind==='value-alias'&&n.slot==null&&!n.operator&&ins.length===1&&!ins[0].condition&&['alias','interface-binding'].includes(ins[0].kind))bindings.set(n.id,ins[0]);
      if(n.kind==='parameter'&&!options.exposedResources?.has(n.id)&&!ins.length&&uses.length&&uses.every(e=>['data','parameter-read'].includes(e.kind)))resources.add(n.id);
    }
    if(options.bindings)for(const [id,edge]of options.bindings)bindings.set(id,edge);
    const metadata=options.metadata||new Set();
    function eligible(id){if(mode!=='source')return true;while(id){if(id==='runtime-observations'||id.startsWith('runtime:'))return false;id=idx.nodes.get(id)?.parent;}return true;}
    function visit(id){if(!eligible(id)||bindings.has(id)||resources.has(id)||metadata.has(id))return;visible.add(id);if(open.has(id))for(const c of idx.children.get(id)||[])visit(c);}
    roots.forEach(visit);
    const ownership=options.frameOwnership?.({ir,plan,idx,visible,open,roots})||new Map();
    for(const id of ownership.keys())visible.delete(id);
    function rep(id){const seen=new Set();while(id&&!visible.has(id)&&!seen.has(id)){if(!eligible(id))return null;seen.add(id);id=options.metadataTargets?.get(id)||ownership.get(id)?.target||idx.nodes.get(id)?.parent;}return visible.has(id)?id:null;}
    let drawingIdx=idx;
    if(ownership.size){
      const nodes=plan.nodes.map(n=>({...n})),by=new Map(nodes.map(n=>[n.id,n]));
      for(const n of nodes){while(ownership.has(n.parent))n.parent=idx.nodes.get(n.parent)?.parent;}
      for(const record of ownership.values()){
        const target=rep(record.target);if(!target)throw Error('source ownership lost its visible destination');
        const n=by.get(target);if(!n.frame_ownership)n.frame_ownership=[];n.frame_ownership.push({...record,target});
      }
      drawingIdx=index({nodes});for(const n of nodes.filter(n=>n.frame_ownership))options.decorateFrameOwner?.(n,drawingIdx);
    }
    const projected=[],internal=[],excluded=[],contracted=[],attached=[],annotations=new Map();
    for(const raw of ir.edges){
      if(!eligible(raw.source)||!eligible(raw.target)){excluded.push(raw.id);continue;}
      // A closed summary may attach one exact source-alternative cut without
      // turning its producer (and that producer's other uses) into metadata.
      const attachment=options.edgeAttachments?.get(raw.id);
      if(attachment&&!open.has(attachment.owner)&&visible.has(attachment.owner)&&rep(raw.target)===attachment.owner&&rep(raw.source)!==attachment.owner&&
        JSON.stringify(raw)===JSON.stringify(attachment.edge)){
        attached.push(raw.id);if(!annotations.has(attachment.owner))annotations.set(attachment.owner,[]);
        annotations.get(attachment.owner).push({...clone(attachment),edge:clone(raw)});continue;
      }
      if(metadata.has(raw.source)||metadata.has(raw.target)){
        attached.push(raw.id);const id=rep(metadata.has(raw.source)?raw.target:raw.source);
        if(id){if(!annotations.has(id))annotations.set(id,[]);const resource=metadata.has(raw.source)?raw.source:raw.target;annotations.get(id).push({edge:clone(raw),resource:idx.nodes.get(resource),annotation_kind:options.metadataKinds?.get(resource)||'configuration-dependency'});}
        continue;
      }
      if(resources.has(raw.source)){attached.push(raw.id);const id=rep(raw.target);if(id){if(!annotations.has(id))annotations.set(id,[]);annotations.get(id).push({edge:clone(raw),resource:idx.nodes.get(raw.source)});}continue;}
      // An explicit output cut ends at a visible panel terminal even when the
      // original external consumer is a contractible alias.
      if(bindings.has(raw.target)&&!options.boundaryReps?.get(raw.id)?.target){contracted.push(raw.id);continue;}
      let resolved=raw.source,port=raw.source_port;const via=[],seen=new Set();
      while(bindings.has(resolved)&&!seen.has(resolved)){seen.add(resolved);const binding=bindings.get(resolved);via.push(binding.id);resolved=binding.source;const outer=binding.source_port??'out';port=outer==='out'?port:port==='out'?outer:outer+'.'+port;}
      const boundary=options.boundaryReps?.get(raw.id),s=boundary?.source?rep(boundary.source):rep(resolved),t=boundary?.target?rep(boundary.target):rep(raw.target);
      if(!s||!t){excluded.push(raw.id);continue;}
      if(s===t&&!(raw.source===raw.target&&raw.source===s)){internal.push(raw.id);continue;}
      // Do not bundle by module pair: distinct values, operands and conditional
      // alternatives must keep their individual boundary identities.
      const bypass=plan.design_constraints?.find(c=>c.kind==='bypass'&&c.add===raw.target&&c.skip===resolved&&c.skip_slot===port);
      projected.push({...clone(raw),id:raw.id,source:s,target:t,source_port:port,originals:[...via,raw.id],canonical_source:raw.source,canonical_target:raw.target,resolved_source:resolved,
        ...(bypass&&(s===resolved||port==='out'&&idx.nodes.get(s)?.contract_stage?.roles.normalization===resolved)&&(t===raw.target||idx.nodes.get(t)?.contract_stage?.roles.add===raw.target&&idx.nodes.get(t).contract_stage.certificate===bypass.certificate)?{design_route:{kind:'bypass',certificate:bypass.certificate}}:{})});
    }
    const edgeAccounting={visible:projected.map(e=>e.id),internal,excluded,contracted,attached};
    // Mark semantic ports before ribbon selection so state/condition identity
    // cannot disappear into an otherwise ordinary repeated-context bundle.
    C.project(plan,projected,rep,edgeAccounting);
    const presented=options.presentEdges?options.presentEdges(projected,idx):projected;
    const constraintReceipts=C.project(plan,presented,rep,edgeAccounting);
    const positions=options.semanticOnly?new Map([...visible].map(id=>[id,{x:0,y:0,w:1,h:1,expanded:open.has(id)&&!!drawingIdx.children.get(id)?.some(child=>visible.has(child))}])):
      L.layout(drawingIdx,roots,visible,presented,state.offsets||{},{foldSerial:state.view==='architecture'&&state.foldSerial!==false,...options.layout});
    if(options.semanticOnly)positions.context={idx:drawingIdx,fixedInputs:[]};else C.evaluate(constraintReceipts,positions,presented);
    const ps=[...positions.values()];
    const left=Math.min(0,...ps.map(p=>p.x-60)),top=Math.min(0,...ps.map(p=>p.y-60));
    const nodeAccounting={visible:[],collapsed:[],contracted:[],attached:[],excluded:[]},representatives={};
    for(const n of ir.nodes){const representative=rep(n.id);let bucket;
      if(!eligible(n.id)||!representative)bucket='excluded';else if(visible.has(n.id))bucket='visible';else if(bindings.has(n.id))bucket='contracted';else if(resources.has(n.id)||metadata.has(n.id)||ownership.has(n.id))bucket='attached';else bucket='collapsed';
      nodeAccounting[bucket].push(n.id);if(representative)representatives[n.id]=representative;
    }
    return {nodes:plan.nodes.filter(n=>visible.has(n.id)).map(n=>drawingIdx.nodes.get(n.id)),edges:presented,positions,idx:drawingIdx,annotations,architecture:state.view==='architecture'?plan:null,
      ...(ownership.size?{frame_ownership:[...ownership.values()].map(r=>({...r,target:rep(r.target)}))}:{}),
      node_accounting:nodeAccounting,representatives,constraint_receipts:constraintReceipts,
      edge_accounting:edgeAccounting,
      bounds:{x:left,y:top,w:Math.max(900,...ps.map(p=>p.x+p.w+60))-left,h:Math.max(600,...ps.map(p=>p.y+p.h+60))-top}};
  }
  const route=(e,positions)=>positions.context?.routeCache?.get(e.id)||L.route(e,positions);
  const auditConstraintRoutes=(g,routes)=>C.auditRoutes(g.constraint_receipts||[],g.positions,routes);
  const api={clone,index,viewIndex,architecture,drawingOrder,validate,project,auditConstraintRoutes,path:(e,p)=>route(e,p).points.map((v,i)=>`${i?'L':'M'}${v.x},${v.y}`).join(' '),route};root.SemanticEngine=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
