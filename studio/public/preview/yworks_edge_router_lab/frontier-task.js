/* One isolated recursive transition, followed by the full graph validation. */
(function(root){
  'use strict';
  function modules(graph){
    const detail=graph.recursive.authority.detail,by=new Map(detail.nodes.map(n=>[n.id,n])),children=new Map();
    for(const n of detail.nodes){if(!children.has(n.parent))children.set(n.parent,[]);children.get(n.parent).push(n.id);}
    const measure=id=>{let count=1,depth=0;for(const child of children.get(id)||[]){const m=measure(child);count+=m.count;depth=Math.max(depth,1+m.maxDepth);}return {count,maxDepth:depth};};
    return detail.nodes.filter(n=>!n.junction&&children.has(n.id)).map(n=>({id:n.id,label:n.label||n.id,parent:n.parent||null,...measure(n.id)}));
  }
  function moduleCut(graph,request){
    const E=root.SummaryEngine,F=root.SummaryRecursive,available=modules(graph),by=new Map(available.map(n=>[n.id,n]));
    if(!request||!Array.isArray(request.ids)||!request.ids.length||request.ids.some(id=>!by.has(id))||!request.reset&&!['f0','f1','source'].includes(request.level)||request.depth!==undefined&&(!Number.isInteger(request.depth)||request.depth<0||request.depth>graph.recursive.authority.detail.nodes.length))throw Error('登记预览模块切面无效。');
    const next=E.clone(graph);F.remember(next);const doc=next.recursive,nodes=doc.authority.detail.nodes,source=new Map(nodes.map(n=>[n.id,n]));
    if(!doc.state.moduleBase)doc.state.moduleBase={open:doc.state.open.slice(),folded:doc.state.folded.slice()};
    let cuts=(doc.state.moduleCuts||[]).filter(c=>!request.ids.includes(c.id));
    if(!request.reset)cuts.push(...request.ids.map(id=>({id,level:request.level,...(request.depth!==undefined?{depth:request.depth}:{})})));
    // Rebuild from the original F0 skeleton so removing an override is exact.
    const open=new Set(doc.state.moduleBase.open),folded=new Set(doc.state.moduleBase.folded);
    const depth=id=>{let d=0;while(source.get(id)?.parent){id=source.get(id).parent;d++;}return d;};
    for(const cut of cuts.slice().sort((a,b)=>depth(a.id)-depth(b.id)||a.id.localeCompare(b.id))){
      const walk=(id,d)=>{
        const container=nodes.some(n=>n.parent===id);if(!container)return;
        const snapshot=cut.level==='f0'?doc.authority.variants[0]:doc.authority.variants.find(v=>v.viewKey==='modules'||v.view==='modules')||doc.authority.variants.at(-1);
        const expanded=cut.level==='source'?d<(cut.depth??nodes.length):!!snapshot.nodes.find(n=>n.id===id)?.expanded;
        if(expanded){open.add(id);folded.delete(id);}else {open.delete(id);folded.add(id);}
        for(const n of nodes.filter(n=>n.parent===id))walk(n.id,d+1);
      };walk(cut.id,0);
      let at=source.get(cut.id)?.parent;while(at){open.add(at);folded.delete(at);at=source.get(at)?.parent;}
    }
    const within=(id,owner)=>{while(id){if(id===owner)return true;id=source.get(id)?.parent;}return false;};
    doc.state.moduleManual=Object.fromEntries(Object.entries(doc.state.moduleManual||{}).filter(([id])=>!request.ids.some(owner=>within(id,owner))));
    for(const [id,expanded]of Object.entries(doc.state.moduleManual)){if(expanded){open.add(id);folded.delete(id);}else{open.delete(id);folded.add(id);}}
    doc.state.open=[...open];doc.state.folded=[...folded];doc.state.moduleCuts=cuts;doc.revision++;return F.build(doc);
  }
  function inspector(graph,selected){const F=root.SummaryRecursive,all=modules(graph),cuts=graph.recursive.state.moduleCuts||[];
    return {legacy:true,modules:all,moduleCuts:cuts,suggestedModules:selected.flatMap(id=>{let n=graph.recursive.authority.detail.nodes.find(n=>n.id===id);while(n&&!all.some(m=>m.id===n.id))n=graph.recursive.authority.detail.nodes.find(p=>p.id===n.parent);return n?[n.id]:[];}),
      mixed:{scopes:cuts.map(c=>({...c,depth:c.depth??null,canonicalNodes:all.find(m=>m.id===c.id)?.count||0,visibleNodes:graph.nodes.filter(n=>{let id=n.id;while(id){if(id===c.id)return true;id=graph.recursive.authority.detail.nodes.find(p=>p.id===id)?.parent;}return false;}).length}))},
      roleOptions:[],contracts:[],relations:[],roleRequests:[],nodeAccounting:{registered:graph.recursive.authority.detail.nodes.map(n=>n.id)},edgeAccounting:{registered:graph.recursive.authority.detail.edges.map(e=>e.id)}};
  }
  function run(graph,transition,options){
    const F=root.SummaryRecursive,E=root.SummaryEngine,clock=()=>typeof performance==='object'?performance.now():Date.now();
    const started=clock();let candidate=graph,changed=!transition;
    if(transition){
      if(transition.type==='preset'){
        if(!['overview','detail'].includes(transition.preset))throw Error('登记预览前沿无效。');
        candidate=E.clone(graph);F.remember(candidate);const doc=candidate.recursive;
        const snapshot=transition.preset==='overview'?doc.authority.variants[0]:doc.authority.variants.find(v=>v.viewKey==='modules'||v.view==='modules');
        delete doc.state.moduleCuts;delete doc.state.moduleBase;delete doc.state.moduleManual;
        if(snapshot){doc.state.open=snapshot.nodes.filter(n=>n.expanded).map(n=>n.id);doc.state.folded=F.containers(doc.authority).filter(id=>!doc.state.open.includes(id));}
        else {const by=new Map(doc.authority.detail.nodes.map(n=>[n.id,n])),depth=id=>{let d=0;while(by.get(id)?.parent){id=by.get(id).parent;d++;}return d;},base=Math.min(...doc.authority.mandatory.map(depth));doc.state.open=F.containers(doc.authority).filter(id=>depth(id)<=base+1);doc.state.folded=F.containers(doc.authority).filter(id=>!doc.state.open.includes(id));}
        doc.revision++;candidate=F.build(doc);changed=true;
      }
      else if(transition.type==='module'){candidate=moduleCut(candidate,transition.request);changed=true;}
      else if(transition.type==='all'){
        const expanded=!!transition.expanded,targets=F.containers(candidate.recursive.authority).filter(id=>!candidate.recursive.authority.mandatory.includes(id));
        if(targets.some(id=>F.opened(candidate.recursive,id)!==expanded)){candidate=F.all(candidate,expanded);changed=true;}
      }
      else if(transition.type==='toggle'||transition.type==='expand'){
        const ids=transition.type==='toggle'?[transition.id]:transition.ids;
        if(!Array.isArray(ids)||ids.some(id=>typeof id!=='string'))throw new Error('展开模块身份无效。');
        if(ids.some(id=>!candidate.recursive.authority.detail.nodes.some(node=>node.id===id)))throw new Error('展开模块不存在。');
        for(const id of ids){
          if(transition.expanded!==undefined&&F.opened(candidate.recursive,id)===!!transition.expanded)continue;
          const next=F.toggle(candidate,id,transition.expanded);if(next){candidate=next;changed=true;}
        }
      }else throw new Error('不支持的递归展开操作。');
    }
    if(!changed)return {ok:true,unchanged:true,graph:candidate};
    const built=clock(),result=F.route(candidate,options),routed=clock(),validation=E.validateView(candidate),finished=clock();
    if(result.failed||!validation.source.ok||!validation.layout.ok||validation.edges.some(([,v])=>!v.ok)){
      throw new Error([...validation.source.violations,...validation.layout.violations,
        ...validation.edges.filter(([,v])=>!v.ok).map(([id,v])=>id+': '+v.violations.join(', '))].slice(0,4).join('; ')||'展开连接未通过完整校验。');
    }
    root.SummarySourceControls?.refresh(candidate);
    const presented=clock();
    return {ok:true,...result,validation,timing:{build:built-started,route:routed-built,validation:finished-routed,controls:presented-finished,total:presented-started}};
  }
  root.SummaryFrontierTask={run,modules,moduleCut,inspector};
  if(typeof module!=='undefined'&&module.exports)module.exports=root.SummaryFrontierTask;
})(typeof self!=='undefined'?self:globalThis);
