/* Import integrity and source endpoint contracts. No model facts come from geometry. */
(function(root){
  'use strict';
  const P=root.SummaryPhysicalPorts||(typeof require==='function'?require('./physical-ports.js'):null);
  const L=root.SummaryRouteLabels||(typeof require==='function'?require('./route-labels.js'):null);
  const stable=value=>JSON.stringify(normalize(value));
  function markupHash(value){let h=2166136261;for(let i=0;i<value.length;i++)h=Math.imul(h^value.charCodeAt(i),16777619)>>>0;return h.toString(16).padStart(8,'0');}
  function normalize(value){
    if(Array.isArray(value))return value.map(normalize);
    if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().map(k=>[k,normalize(value[k])]));
    return value;
  }
  function edgeErrors(graph,e,points=e.route,options={}){
    if(graph.generic&&root.SummaryNativeSemantic)return root.SummaryNativeSemantic.edgeErrors(graph,e,points);
    if(graph.recursive&&root.SummaryRecursive)return root.SummaryRecursive.edgeErrors(graph,e,points,options);
    const base=graph.semanticBaseline;if(!base)return [];
    const errors=[],saved=base.edges[e.id];
    if(!saved){if(!e.draft)errors.push('unreviewed connection requires a draft');return errors;}
    if(stable(e.binding||{})!==stable(saved.binding))errors.push('canonical source binding or trace changed');
    if(!e.draft&&(e.source!==saved.source||e.target!==saved.target))errors.push('source producer/consumer changed');
    if(!e.draft)for(const key of ['fixedSource','fixedTarget'])if(stable(e[key]||null)!==stable(saved[key]||null))errors.push('source port changed without a draft');
    if(!e.draft&&stable(e.portPolicy||null)!==stable(saved.portPolicy||null))errors.push('source routing policy changed');
    if(!e.draft&&!options.skipPhysical)errors.push(...P.errors(graph,e,points));
    return errors;
  }
  function nodeErrors(graph){
    if(graph.generic&&root.SummaryNativeSemantic)return root.SummaryNativeSemantic.nodeErrors(graph);
    if(graph.recursive&&root.SummaryRecursive)return root.SummaryRecursive.nodeErrors(graph);
    const base=graph.semanticBaseline;if(!base)return [];
    const errors=[],nodes=new Map(graph.nodes.map(n=>[n.id,n]));
    for(const [id,saved]of Object.entries(base.nodes)){
      const n=nodes.get(id);if(!n){errors.push('source glyph missing '+id);continue;}
      if((n.parent||null)!==(saved.parent||null))errors.push('source containment changed '+id);
      if(stable(n.semantic||{})!==stable(saved.semantic))errors.push('source node metadata changed '+id);
      if(stable(n.visualBinding||null)!==stable(saved.visualBinding||null))errors.push('tensor alias owner changed '+id);
      if(saved.glyphPresentation){
        if(stable(n.glyphPresentation)!==stable(saved.glyphPresentation))errors.push('source glyph meaning changed '+id);
        if(markupHash(n.html)!==saved.glyphMarkupHash)errors.push('source glyph markup changed '+id);
        if(stable(n.labelObstacles)!==stable(saved.labelObstacles))errors.push('source glyph caption bounds changed '+id);
        const expected=saved.glyphPresentation.kind==='binary-circle'?[32,32]:[72,32];
        if(n.w!==expected[0]||n.h!==expected[1])errors.push('source glyph outline size changed '+id);
        const parent=nodes.get(n.parent);
        if(parent)for(const b of n.labelObstacles||[])if(n.x+b.x<parent.x-1e-5||n.y+b.y<parent.y-1e-5||n.x+b.x+b.w>parent.x+parent.w+1e-5||n.y+b.y+b.h>parent.y+parent.h+1e-5)errors.push('source glyph caption leaves its owner '+id);
      }else if(n.glyphPresentation)errors.push('unregistered source glyph '+id);
    }
    if(graph.irSha256!==base.irSha256)errors.push('source IR digest changed');
    if(stable(graph.junctionMarkers||[])!==stable(base.junctionMarkers||[]))errors.push('source junction ownership or route references changed');
    const routeLabels=new Map((graph.routeLabels||[]).map(a=>[a.id,a]));
    for(const [id,saved]of Object.entries(base.routeLabels||{})){
      const a=routeLabels.get(id),actual=a?Object.fromEntries(Object.entries(a).filter(([k])=>k!=='anchor')):null;
      if(stable(actual)!==stable(saved))errors.push('source caption binding or content changed '+id);
    }
    for(const id of routeLabels.keys())if(!base.routeLabels?.[id])errors.push('unregistered source caption '+id);
    errors.push(...L.errors(graph));
    const attachments=new Map((graph.attachments||[]).map(a=>[a.id,a]));
    if(attachments.size!==(graph.attachments||[]).length)errors.push('duplicate presentation attachment');
    for(const [id,saved]of Object.entries(base.attachments||{})){
      const a=attachments.get(id);if(!a){errors.push('source presentation attachment missing '+id);continue;}
      if(a.owner!==saved.owner||a.kind!==saved.kind||(a.value_owner||null)!==(saved.value_owner||null)||(a.source_owner||null)!==(saved.source_owner||null))errors.push('presentation attachment owner changed '+id);
    }
    for(const a of attachments.values())if(!nodes.has(a.owner))errors.push('presentation attachment owner missing '+a.id);
    return errors;
  }
  function validateGraph(graph){
    if(graph.generic&&root.SummaryNativeSemantic)return root.SummaryNativeSemantic.validate(graph);
    if(graph.recursive&&root.SummaryRecursive)return root.SummaryRecursive.validate(graph);
    const errors=nodeErrors(graph),base=graph.semanticBaseline;
    if(base){const ids=new Set(graph.edges.map(e=>e.id));for(const id of Object.keys(base.edges))if(!ids.has(id)){
      const deletion=(graph.sourceDraftOperations||[]).find(op=>op.kind==='remove-connection'&&op.id===id&&stable(op.binding)===stable(base.edges[id].binding));
      if(!deletion)errors.push('source connection missing '+id);
    }}
    for(const e of graph.edges)errors.push(...edgeErrors(graph,e).map(v=>e.id+': '+v));
    return {ok:errors.length===0,violations:[...new Set(errors)]};
  }
  const api={edgeErrors,nodeErrors,validateGraph};
  root.SummarySourceContracts=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
