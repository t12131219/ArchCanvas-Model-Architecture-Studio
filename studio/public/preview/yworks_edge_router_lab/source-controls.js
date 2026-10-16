/* Source conditional containment, kept separate from canonical tensor edges. */
(function(root){
  'use strict';
  const R=root.EdgeRouterLabRouting,E=root.SummaryEngine,C=root.SummaryConstraints,L=root.SummaryRouteLabels;
  const NS='http://www.w3.org/2000/svg',VERSION=2,cache=new Map(),clone=E.clone;
  const kind=n=>n.semantic?.sourceStructure===true?n.semantic.sourceKind:null;
  const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  const overlay=graph=>graph.recursive?.state?.studioPresentation||graph.studioPresentation||{};
  function signature(graph){return JSON.stringify([VERSION,graph.irSha256,graph.canvas,
    graph.nodes.map(n=>[n.id,n.parent,n.x,n.y,n.w,n.h,n.base,!!n.expanded,n.routingObstacle,n.junction,n.glyphPresentation,n.labelObstacles,kind(n),n.semantic?.label,n.semantic?.source_evidence,n.sourceControlPresentation]),
    graph.edges.map(e=>[e.id,e.source,e.target,e.route,e.style,e.width,e.contract?.wire]),
    (graph.routeLabels||[]).map(label=>[label.id,label.edge,label.bbox,label.anchor,label.scope]),
    (graph.attachments||[]).map(a=>[a.id,a.owner,a.bbox,a.presentation]),graph.junctionMarkers,
    overlay(graph).annotations,(overlay(graph).legend||[]).length]);}
  function definitions(graph){
    const result=[];
    for(const owner of graph.nodes){
      if(!owner.expanded||kind(owner)!=='SourceConditional')continue;
      const evidence=owner.semantic.source_evidence,branches=graph.nodes.filter(n=>n.parent===owner.id&&kind(n)==='SourceBranch');
      if(!Array.isArray(evidence)||!evidence.length)continue;
      for(const branch of branches){
        const caption=branch.semantic.label,outcome=caption==='else'?false:caption===owner.semantic.label&&/^if\s/.test(caption)?true:null;
        if(outcome===null||!same(branch.semantic.source_evidence,evidence))continue;
        result.push({id:'source-control:'+owner.id+':'+branch.id,owner:owner.id,target:branch.id,outcome,
          role:'source-control',source_evidence:clone(evidence),label:outcome?'条件成立 · true':'否则 · false'});
      }
    }
    return result;
  }
  function paths(graph){return graph.edges.filter(e=>e.route?.length>1).map(e=>Object.assign(clone(e.route),{wire:e.contract?.wire||'canonical:'+e.id}));}
  function routeBoxes(routes){return routes.flatMap(route=>route.slice(1).map((b,i)=>{
    const a=route[i];return {x:Math.min(a.x,b.x)-2,y:Math.min(a.y,b.y)-2,w:Math.abs(a.x-b.x)+4,h:Math.abs(a.y-b.y)+4};
  }));}
  function compute(graph,key){
    const result={version:VERSION,signature:key,controls:[],decisions:[],diagnostics:[]},defs=definitions(graph);
    if(!defs.length)return result;
    // A temporary geometric graph has no imported source baseline. Its
    // controls receive their own containment proof above; all real bodies,
    // headings, nested walls and canonical routes remain routing obstacles.
    const geometry={nodes:clone(graph.nodes),edges:[],canvas:clone(graph.canvas)},prior=paths(graph),occupied=routeBoxes(prior),decisions=new Map();
    const obstacle=(id,box)=>{occupied.push(box);geometry.nodes.push({id:'source-control-obstacle:'+id,...box,routingObstacle:true,expanded:false});};
    // Existing route captions are painted obstacles too. This is evaluated
    // once per committed geometry, never from render or pointer movement.
    for(const [id,placed]of E.routeLabelPlacements(graph)){
      obstacle('route-label:'+id,{x:placed.box.x-2,y:placed.box.y-1,w:placed.box.w+4,h:placed.box.h+2});
    }
    for(const a of graph.attachments||[])if(graph.nodes.some(n=>n.id===a.owner)&&a.bbox?.length===4){
      const offset=E.attachmentTransform(graph,a),[x,y,w,h]=a.bbox;obstacle('attachment:'+a.id,{x:x+offset.x,y:y+offset.y,w,h});
    }
    for(const marker of graph.junctionMarkers||[]){const p=E.junctionPoint(graph,marker),r=marker.radius||2.5;if(p)obstacle('junction:'+marker.id,{x:p.x-r,y:p.y-r,w:r*2,h:r*2});}
    for(const a of Object.values(overlay(graph).annotations||{})){
      const width=Math.max(80,a.width||380),length=Math.max(10,Math.floor(width/9)),lines=String(a.text||'').split('\n').reduce((count,line)=>count+Math.max(1,Math.ceil(line.length/length)),0);
      obstacle('annotation:'+a.id,{x:(a.x||0)-5,y:(a.y||0)-17,w:width+10,h:lines*20+7});
    }
    for(const definition of defs){
      const owner=geometry.nodes.find(n=>n.id===definition.owner),target=geometry.nodes.find(n=>n.id===definition.target),presentation=owner.sourceControlPresentation;
      if(presentation?.schema!=='source-condition-presentation/1'||!Number.isFinite(presentation.anchor?.x)||!Number.isFinite(presentation.anchor?.y)){
        result.diagnostics.push({owner:owner.id,target:target.id,message:'条件分支缺少预留的判定区域；关联箭头未绘制。'});continue;
      }
      let decision=decisions.get(owner.id);
      if(!decision){
        const centre={x:owner.x+presentation.anchor.x,y:owner.y+presentation.anchor.y};
        decision={id:'source-control-decision:'+owner.id,parent:owner.id,x:centre.x-6,y:centre.y-6,w:12,h:12,routingObstacle:true,expanded:false,junction:false};
        // The marker is an endpoint here; canonical routes still see its
        // registered heading obstacle in the original source graph.
        owner.labelObstacles=(owner.labelObstacles||[]).filter(box=>!same(box,presentation.obstacle));
        geometry.nodes.push(decision);decisions.set(owner.id,decision);
      }
      const a={x:decision.x+6,y:decision.y+12},b={x:target.x+target.w/2,y:target.y},lane=a.y+12;
      const edge={id:definition.id,source:decision.id,target:target.id,style:'orthogonal',arrow:'open',draft:false,
        fixedSource:{side:'bottom',fraction:.5},fixedTarget:{side:'top',fraction:.5},
        binding:{representation:'source-conditional-control',src:decision.id+':predicate',dst:target.id+':guard'},
        portPolicy:{source:{mode:'fixed',shape:'rectangle',spacing:0},target:{mode:'fixed',shape:'rectangle',spacing:0}},
        route:R.simplify([a,{x:a.x,y:lane},{x:b.x,y:lane},b]),waypoints:[]};
      geometry.edges.push(edge);C.initialize(geometry);
      const options={margin:3,stub:12,bendCost:40,crossingCost:450,overlapCost:2,edgeSpacing:4,style:'orthogonal',sides:'any',boundaryLanes:false};
      const safe=points=>C.validate(geometry,edge,points).ok&&
        !prior.some(path=>path.wire!==edge.contract.wire&&path.slice(1).some((b,i)=>points.slice(1).some((d,j)=>R.overlap(path[i],b,points[j],d)>1e-5)))&&
        !E.overlapsWire(geometry,edge,points)&&points.every(p=>p.x>=owner.x+2&&p.y>=owner.y+2&&p.x<=owner.x+owner.w-2&&p.y<=owner.y+owner.h-2);
      const routed=E.routeOne(geometry,edge,prior,options);
      let valid=routed.ok&&safe(edge.route);
      if(!valid){
        // Stacked, independently expanded arms can fill the direct corridor.
        // Search a bounded pair of owner-side detours as well. These are only
        // geometric proposals: the same walls, headings, canonical routes and
        // containment checks still have to prove the entire path safe.
        const terminal=Math.max(12,edge.contract.minimumTerminal||0),inset=terminal+6;
        // A canonical tensor can already enter at the branch's top centre.
        // This syntax association owns no tensor port, so it may use another
        // top slot; never conceal the existing tensor terminal underneath it.
        edge.portPolicy.target.mode='side';
        const candidates=[.5,.25,.75].flatMap(fraction=>{
          const endpoint={x:target.x+target.w*fraction,y:target.y};
          return [owner.x+inset,owner.x+owner.w-inset].flatMap(x=>[0,6,12,24].map(extra=>({fraction,points:R.simplify([
            a,{x:a.x,y:a.y+terminal},{x,y:a.y+terminal},
            {x,y:endpoint.y-terminal-extra},{x:endpoint.x,y:endpoint.y-terminal-extra},endpoint])})));
        });
        const fallback=candidates.find(candidate=>{edge.physicalTarget={side:'top',fraction:candidate.fraction};return safe(candidate.points);});
        if(fallback){edge.route=fallback.points;edge.failed=false;delete edge.reason;valid=true;}
      }
      if(!valid){
        geometry.edges.pop();result.diagnostics.push({owner:owner.id,target:target.id,message:'条件分支没有合法的容器内通道；关联箭头未绘制。'});continue;
      }
      const label={bbox:[0,0,102,16],scope:[owner.id],anchor:{mode:'target',ratio:.8,distance:18,gap:5,side:{x:1,y:-1}}};
      const placed=L.place(geometry,label,edge.route,occupied);
      if(!placed||placed.score>=1e6||placed.leader){
        geometry.edges.pop();result.diagnostics.push({owner:owner.id,target:target.id,message:'条件分支标签没有安全空间；关联箭头未绘制。'});continue;
      }
      result.controls.push({...definition,points:clone(edge.route),labelBox:clone(placed.box),geometryValidated:true});
      prior.push(Object.assign(clone(edge.route),{wire:edge.contract.wire}));occupied.push(placed.box,...routeBoxes([edge.route]));
      geometry.nodes.push({id:'source-control-label:'+definition.id,parent:owner.id,...placed.box,routingObstacle:true,expanded:false});
    }
    for(const [owner,decision]of decisions)
      result.decisions.push({owner,x:decision.x+6,y:decision.y+6,diagnostics:result.diagnostics.filter(item=>item.owner===owner).map(item=>item.message)});
    return result;
  }
  function refresh(graph){
    const key=signature(graph);let value=cache.get(key);
    if(!value){value=compute(graph,key);cache.set(key,value);while(cache.size>4)cache.delete(cache.keys().next().value);}
    graph.sourceControls=clone(value);return graph.sourceControls;
  }
  // Render never invokes the router. A drag with stale coordinates hides
  // these associations until its normal validated transaction completes.
  function ensure(graph){const value=graph.sourceControls;return value?.version===VERSION&&value.signature===signature(graph)?value:
    {version:VERSION,controls:[],decisions:[],diagnostics:[]};}
  function legendRows(graph){return ensure(graph).controls.length?[{label:'条件分支 · 非张量',stroke:'#8a6a46',dashArray:'4 4'}]:[];}
  function render(graph,svg){
    let layer=svg.querySelector('#sourceControlLayer');
    if(!layer){layer=document.createElementNS(NS,'g');layer.setAttribute('id','sourceControlLayer');layer.setAttribute('pointer-events','none');svg.insertBefore(layer,svg.querySelector('#nodeLayer'));}
    const value=ensure(graph),mono=(graph.recursive?.state?.studioPresentation||graph.studioPresentation)?.page?.preset==='monochrome',stroke=mono?'#4b5563':'#8a6a46';
    const renderKey=value.signature+'|'+stroke;
    if(layer.getAttribute('data-source-control-signature')===renderKey)return;
    layer.setAttribute('data-source-control-signature',renderKey);layer.setAttribute('data-source-control-diagnostics',String(value.diagnostics.length));layer.replaceChildren();
    const element=(tag,attrs,text)=>{const node=document.createElementNS(NS,tag);for(const [key,value]of Object.entries(attrs))node.setAttribute(key,value);if(text!==undefined)node.textContent=text;return node;};
    for(const decision of value.decisions){
      const {x,y}=decision,g=element('g',{'data-source-control-owner':decision.owner,'data-source-control-decision':'true'});
      g.append(element('path',{d:`M ${x} ${y-6} L ${x+6} ${y} L ${x} ${y+6} L ${x-6} ${y} Z`,fill:'#ffffff',stroke,'stroke-width':1.4}),element('title',{},['源码条件判定 · 分支互斥 · 非张量连接',...(decision.diagnostics||[])].join('\n')));
      if(decision.diagnostics?.length)g.append(element('text',{x,y:y+3,'text-anchor':'middle','font-size':9,fill:stroke,'data-source-control-diagnostic':'true'},'!'));
      layer.append(g);
    }
    for(const control of value.controls){
      const g=element('g',{'data-source-control-id':control.id,'data-source-control-owner':control.owner,'data-source-control-target':control.target,'data-role':'source-control','data-geometry-valid':'true'}),points=control.points,box=control.labelBox;
      g.append(element('path',{d:R.polylinePath(points),fill:'none',stroke,'stroke-width':1.5,'stroke-dasharray':'4 4'}),
        element('path',{d:E.arrow(points.at(-1),points.at(-2),true),fill:'none',stroke,'stroke-width':1.5}),
        element('rect',{x:box.x,y:box.y,width:box.w,height:box.h,rx:2,fill:'#ffffff','fill-opacity':.95}),
        element('text',{x:box.x+2,y:box.y+12,'font-size':10,fill:stroke},control.label),
        element('title',{},'条件分支语法关联（非张量）：'+(control.outcome?'条件成立':'否则')));layer.append(g);
    }
  }
  const api={definitions,refresh,ensure,render,legendRows,signature};root.SummarySourceControls=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof self!=='undefined'?self:globalThis);
