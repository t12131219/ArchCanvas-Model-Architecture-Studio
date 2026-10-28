/* Studio appearance overlays keep the audited source glyphs and IR immutable. */
(function(root){
  'use strict';
  const NS='http://www.w3.org/2000/svg',clone=v=>JSON.parse(JSON.stringify(v));
  const node=(tag,attrs={},text)=>{const e=document.createElementNS(NS,tag);for(const [k,v]of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e;};
  const color=v=>typeof v==='string'&&/^#[a-f0-9]{3,8}$/i.test(v);
  function state(graph){const value=graph.recursive?.state?.studioPresentation||graph.studioPresentation||{version:1,nodes:{},edges:{},annotations:{},legend:[],page:{}};if(graph.recursive?.state?.studioPresentation)graph.studioPresentation=value;return value;}
  function editable(graph){const value=clone(state(graph));value.version=1;for(const key of ['nodes','edges','annotations','page'])value[key]=value[key]||{};value.legend=value.legend||[];graph.studioPresentation=value;if(graph.recursive)graph.recursive.state.studioPresentation=value;return value;}
  // Source inspection arrows carry def/use evidence, never a tensor binding.
  // The endpoint fallback also recognizes saved frontiers from older adapters.
  function isSourceDependency(graph,edge){
    if(edge.draft||/visual edit draft/i.test(String(edge.binding?.evidence||'')))return false;
    if(edge.role&&edge.role!=='source_dependency')return false;
    if(edge.role==='source_dependency'&&edge.syntaxOnly===true)return true;
    const detail=graph.recursive?.authority?.detail,original=detail?.edges?.find(e=>e.id===edge.projection?.original)||edge;
    if((edge.role||original.role)!=='source_dependency')return false;
    if(edge.syntaxOnly===true||original.syntaxOnly===true)return true;
    const nodes=detail?.nodes||graph.nodes||[];
    return [original.source,original.target].every(id=>nodes.find(n=>n.id===id)?.semantic?.sourceStructure===true);
  }
  function edgeAppearance(graph,edge){
    const overlay=state(graph),p=overlay.edges[edge.id]||overlay.edges[edge.projection?.original]||{},source=isSourceDependency(graph,edge),mono=overlay.page.preset==='monochrome';
    const dashed=p.dashed!==undefined?p.dashed:edge.dashed!==undefined?edge.dashed:source;
    return {sourceRelation:source,stroke:mono?'#4b5563':color(p.stroke)?p.stroke:color(edge.stroke)?edge.stroke:source?'#776095':'#263b4b',
      width:p.width??edge.width??2.2,dashed,dashArray:dashed?(source?'2 4':'7 5'):'none'};
  }
  function applyNode(graph,n,view){
    const overlay=state(graph),p=overlay.nodes[n.id]||{},mono=overlay.page.preset==='monochrome',signature=JSON.stringify([p,mono]);
    if(view.studioSignature!==signature){view.content.innerHTML=n.html;view.html=n.html;view.studioSignature=signature;}
    const shape=view.content.querySelector('rect,circle,ellipse,path');
    if(shape){
      if(color(p.fill))shape.setAttribute('fill',p.fill);
      if(color(p.stroke))shape.setAttribute('stroke',p.stroke);
      if(Number.isFinite(p.strokeWidth))shape.setAttribute('stroke-width',Math.max(.5,Math.min(8,p.strokeWidth)));
      if(p.glyph&&!n.glyphPresentation){
        if(p.glyph==='operator'||p.glyph==='add'){
          const replacement=node('ellipse',{cx:n.base[0]+n.w/2,cy:n.base[1]+n.h/2,rx:n.w/2,ry:n.h/2,fill:color(p.fill)?p.fill:(shape.getAttribute('fill')||n.fill||'#eef1fa'),stroke:color(p.stroke)?p.stroke:(shape.getAttribute('stroke')||'#263348'),'stroke-width':2});
          shape.replaceWith(replacement);
        }else if(shape.tagName==='rect')shape.setAttribute('rx',p.glyph==='tensor'?2:p.glyph==='norm'?20:10);
      }
    }
    const rect=view.content.querySelector('rect');if(rect&&(n.expanded||p.width||p.height)){rect.setAttribute('width',n.w);rect.setAttribute('height',n.h);}
    if(p.alias){
      const text=n.glyphPresentation?view.content.querySelectorAll('text')[1]:view.content.querySelector('text');
      if(text){text.textContent=p.alias;const width=Math.max(24,n.glyphPresentation?(n.labelObstacles?.[0]?.w||100):n.w-32);if(p.alias.length*14>width){text.setAttribute('textLength',width);text.setAttribute('lengthAdjust','spacingAndGlyphs');}}
    }
    if(mono)for(const e of view.content.querySelectorAll('*')){
      if(e.hasAttribute('fill')&&!['none','transparent'].includes(e.getAttribute('fill')))e.setAttribute('fill',e.tagName==='text'||e.tagName==='tspan'?'#20252b':'#ffffff');
      if(e.hasAttribute('stroke')&&e.getAttribute('stroke')!=='none')e.setAttribute('stroke','#343a40');
    }
    view.g.setAttribute('data-studio-pinned',String(!!p.pinned));
    if(p.pinned){
      if(!view.pinTitle){view.pinTitle=node('title',{'data-editor-only':'pin'},'已固定直接移动；子节点仍随父容器移动与递归布局更新。');view.g.append(view.pinTitle);}
    }else if(view.pinTitle){view.pinTitle.remove();view.pinTitle=null;}
    view.g.setAttribute('data-studio-glyph',p.glyph||'source');
    view.g.setAttribute('data-studio-alias',p.alias||'');
  }
  function render(graph,svg,interaction={}){
    const overlay=state(graph),mono=overlay.page.preset==='monochrome';
    let layer=svg.querySelector('#studioPresentationLayer');if(!layer){layer=node('g',{id:'studioPresentationLayer'});svg.insertBefore(layer,svg.querySelector('#handleLayer'));}
    layer.replaceChildren();
    for(const annotation of Object.values(overlay.annotations)){
      const x=annotation.x||0,y=annotation.y||0,width=Math.max(80,annotation.width||380),text=node('text',{x,y,'font-size':14,fill:'#334155','data-studio-annotation':annotation.id});
      const lines=String(annotation.text||'').split('\n').flatMap(line=>{const chunks=[];const length=Math.max(10,Math.floor(width/9));for(let i=0;i<line.length||!i;i+=length)chunks.push(line.slice(i,i+length));return chunks;});
      lines.forEach((line,i)=>text.append(node('tspan',{x,dy:i?20:0},line)));
      if(interaction.onAnnotationDown){text.setAttribute('cursor','move');text.onpointerdown=event=>interaction.onAnnotationDown(event,annotation);}
      if(interaction.selectedAnnotation===annotation.id)layer.append(node('rect',{x:x-5,y:y-17,width:width+10,height:lines.length*20+7,fill:'none',stroke:'#d99160','stroke-width':1.5,'stroke-dasharray':'5 4','pointer-events':'none','data-editor-only':'annotation-selection'}));
      layer.append(text);
    }
    const sourceEdge=graph.edges.find(edge=>isSourceDependency(graph,edge)),controlRows=root.SummarySourceControls?.legendRows(graph)||[];
    // Node category legends stay in Studio's inspector, outside the diagram.
    if(sourceEdge||controlRows.length){
      const legend=node('g',{'data-studio-legend':'true'}),width=sourceEdge||controlRows.length?360:250,height=((sourceEdge?1:0)+controlRows.length)*28+32,x=Math.max(10,graph.canvas[0]-width-20),y=Math.max(10,graph.canvas[1]-height-20);
      legend.append(node('rect',{x,y,width,height,rx:8,fill:'#ffffff',stroke:'#ccd7df'}));
      if(sourceEdge){const row=y+24,appearance=edgeAppearance(graph,sourceEdge),relation=node('g',{'data-source-relation-legend':'true'});
        relation.append(node('path',{d:`M ${x+12} ${row-5} H ${x+36}`,fill:'none',stroke:appearance.stroke,'stroke-width':1.5,'stroke-dasharray':appearance.dashArray}),node('path',{d:`M ${x+31} ${row-9} L ${x+37} ${row-5} L ${x+31} ${row-1}`,fill:'none',stroke:appearance.stroke,'stroke-width':1.5}),node('text',{x:x+44,y:row,'font-size':12,fill:'#334155'},'源码数据依赖 · 执行路径未确定'));legend.append(relation);}
      controlRows.forEach((item,index)=>{const row=y+24+((sourceEdge?1:0)+index)*28,stroke=mono?'#4b5563':item.stroke,relation=node('g',{'data-source-control-legend':'true'});
        relation.append(node('path',{d:`M ${x+12} ${row-5} H ${x+36}`,fill:'none',stroke,'stroke-width':1.5,'stroke-dasharray':item.dashArray}),node('path',{d:`M ${x+31} ${row-9} L ${x+37} ${row-5} L ${x+31} ${row-1}`,fill:'none',stroke,'stroke-width':1.5}),node('text',{x:x+44,y:row,'font-size':12,fill:'#334155'},item.label));legend.append(relation);});
      layer.append(legend);
    }
    for(const e of graph.edges){const p=overlay.edges[e.id]||overlay.edges[e.projection?.original]||{},appearance=edgeAppearance(graph,e),group=svg.querySelector(`[data-edge-id="${CSS.escape(e.id)}"]`),path=group?.querySelector('.wire-path'),stroke=mono||color(p.stroke)||color(e.stroke)?appearance.stroke:null;if(path){if(p.width!==undefined)path.setAttribute('stroke-width',p.width);if(p.dashed!==undefined)path.setAttribute('stroke-dasharray',appearance.dashArray);if(stroke){path.setAttribute('stroke',stroke);for(const arrow of group.querySelectorAll('.arrow-shape')){if(arrow.getAttribute('fill')!=='none')arrow.setAttribute('fill',stroke);if(arrow.getAttribute('stroke')!=='none')arrow.setAttribute('stroke',stroke);}}}}
    const stage=document.getElementById('stage');if(stage)stage.style.backgroundColor=overlay.page.background||'#fafcfb';
    svg.setAttribute('data-studio-presentation-version','1');svg.setAttribute('data-studio-page-width-mm',String(overlay.page.widthMm||180));
  }
  root.ArchCanvasStudioPresentation={state,editable,applyNode,render,color,isSourceDependency,edgeAppearance};
})(window);
