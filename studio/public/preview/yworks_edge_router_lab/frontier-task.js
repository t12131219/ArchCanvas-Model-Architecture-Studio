/* One isolated recursive transition, followed by the full graph validation. */
(function(root){
  'use strict';
  function run(graph,transition,options){
    const F=root.SummaryRecursive,E=root.SummaryEngine,clock=()=>typeof performance==='object'?performance.now():Date.now();
    const started=clock();let candidate=graph,changed=!transition;
    if(transition){
      if(transition.type==='all'){
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
  root.SummaryFrontierTask={run};
  if(typeof module!=='undefined'&&module.exports)module.exports=root.SummaryFrontierTask;
})(typeof self!=='undefined'?self:globalThis);
