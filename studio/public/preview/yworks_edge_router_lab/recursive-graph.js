/* One source hierarchy, independently expandable branches, and audited frontiers.
 * A frontier is a presentation projection; it never rewrites canonical bindings. */
(function(root){
  'use strict';
  const R=root.EdgeRouterLabRouting,E=root.SummaryEngine,C=root.SummaryConstraints;
  const copy=v=>v===undefined?undefined:JSON.parse(JSON.stringify(v)),eq=(a,b)=>JSON.stringify(a)===JSON.stringify(b),EPS=1e-5;
  const receiptCache=new WeakMap();
  const PRESENTATION_VERSION=10;
  function children(authority,id){return authority.detail.nodes.filter(n=>n.parent===id);}
  function containers(authority){return authority.detail.nodes.filter(n=>children(authority,n.id).length&&!n.junction).map(n=>n.id);}
  function create(sources){
    const ordered=['overview','modules','detailed',...Object.keys(sources)].filter((k,i,a)=>sources[k]&&a.indexOf(k)===i);
    const variants=ordered.map(k=>copy(sources[k])),detail=copy(sources.detailed||variants.at(-1)),overview=copy(sources.overview||variants[0]);
    // A single detailed-only audit has no compact snapshot. Its root remains
    // the minimum skeleton, and its nested source containers start folded.
    const mandatory=overview.nodes.filter(n=>n.expanded&&detail.nodes.some(v=>v.parent===n.id)).map(n=>n.id);
    if(!sources.overview){mandatory.splice(0,mandatory.length,...detail.nodes.filter(n=>!n.parent&&children({detail},n.id).length).map(n=>n.id));}
    return {schema:1,presentationVersion:PRESENTATION_VERSION,authority:{detail,variants,mandatory},state:{open:[...mandatory],folded:[],layouts:{},frontiers:{}},revision:0};
  }
  function opened(doc,id){return doc.authority.mandatory.includes(id)||doc.state.open.includes(id)&&!doc.state.folded.includes(id);}
  function visible(doc){const ids=new Set(),nodes=doc.authority.detail.nodes;
    function visit(id){ids.add(id);if(opened(doc,id))for(const n of nodes)if(n.parent===id)visit(n.id);}
    for(const n of nodes)if(!n.parent||!nodes.some(p=>p.id===n.parent))visit(n.id);return ids;
  }
  function representative(doc,id,ids=visible(doc)){const by=new Map(doc.authority.detail.nodes.map(n=>[n.id,n]));let n=by.get(id),seen=new Set();while(n&&!ids.has(n.id)&&!seen.has(n.id)){seen.add(n.id);n=by.get(n.parent);}return n?.id||null;}
  const signature=doc=>[...visible(doc)].sort().join('|');
  const trace=e=>e.binding?.semantic_edges||e.binding?.semantic_trace||e.binding?.trace||[];
  const semanticKey=e=>e.binding?.endpoint_binding?.edge_id||[e.binding?.canonical_src||e.binding?.semantic_src||e.source,e.binding?.canonical_dst||e.binding?.semantic_dst||e.target,e.binding?.semantic_trace||e.binding?.trace||[],e.role||e.binding?.role||'tensor'].map(v=>JSON.stringify(v)).join('→');
  function presentationEdge(graph,visual){
    if(!visual)return null;
    const peers=graph.edges.filter(e=>e.source===visual.source&&e.target===visual.target&&semanticKey(e)===semanticKey(visual));
    // Canonical aliases may depict several segments of the same binding.
    // A caption or fork belongs to one recorded segment, not the first edge
    // with the same tensor identity (e.g. into Memory versus out to K/V).
    return peers.find(e=>e.projection?.visual===visual.id)||peers.find(e=>(e.projection?.originals||[e.projection?.original]).includes(visual.id))||peers[0]||null;
  }
  function exact(doc){const ids=visible(doc);return doc.authority.variants.find(g=>g.nodes.length===ids.size&&g.nodes.every(n=>ids.has(n.id)));}
  function foldedVariant(a,n){return a.variants.map(g=>g.nodes.find(v=>v.id===n.id&&!v.expanded)).find(Boolean)||null;}
  function expandedTemplate(a,n){const wanted=children(a,n.id).filter(v=>!v.junction).map(v=>v.id);return a.variants.find(g=>g.nodes.some(v=>v.id===n.id&&v.expanded)&&wanted.every(id=>g.nodes.some(v=>v.id===id)))||a.detail;}
  function compact(n){const v=copy(n);v.expanded=false;v.routingObstacle=true;v.w=Math.min(330,Math.max(180,n.w));v.h=84;v.labelObstacles=[];v.base=[n.x,n.y];
    const escape=s=>String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    v.html=`<rect x="${v.x}" y="${v.y}" width="${v.w}" height="${v.h}" rx="10" fill="${n.fill||'#e7f5fe'}" stroke="#263348" stroke-width="2"/><text x="${v.x+16}" y="${v.y+29}" font-size="16" fill="#172336">${escape(n.label||n.id)}</text><text x="${v.x+16}" y="${v.y+55}" font-size="11" fill="#526078">${escape(n.id)}</text>`;return v;
  }
  function settleJunctions(nodes,doc){
    const inside=(p,r)=>p.x>r.x-EPS&&p.x<r.x+r.w+EPS&&p.y>r.y-EPS&&p.y<r.y+r.h+EPS;
    const rawBy=new Map(doc.authority.detail.nodes.map(n=>[n.id,n])),by=new Map(nodes.map(n=>[n.id,n]));
    const normals={left:[-1,0],right:[1,0],top:[0,-1],bottom:[0,1]};
    const settled=[];
    for(const n of nodes.filter(n=>n.junction)){
      const parent=nodes.find(v=>v.id===n.parent);if(!parent?.expanded)continue;
      // Branch dots follow their actual module interface, including growth
      // and sibling displacement. A free old pixel is not a stable anchor:
      // after expansion it may lie on the module's output instead of input.
      const incident=doc.authority.detail.edges.filter(e=>e.source===n.id||e.target===n.id);
      const anchor=incident.flatMap(e=>['source','target'].filter(s=>e[s]!==n.id&&!rawBy.get(e[s])?.junction&&by.has(e[s])).map(side=>({e,side,owner:by.get(e[side]),raw:rawBy.get(e[side])}))).sort((a,b)=>(a.owner.id===parent.id)-(b.owner.id===parent.id))[0];
      let outward=null;
      if(anchor){const {e,side,owner,raw}=anchor,f=e['fixed'+(side==='source'?'Source':'Target')],old=root.SummaryPhysicalPorts.point(raw,f),port=E.port(owner,{side:f.side,fraction:f.fraction}),original=rawBy.get(n.id);
        n.x=port.x+original.x-old.x;n.y=port.y+original.y-old.y;
        if(owner.id!==parent.id&&!f.inward)outward={owner,normal:normals[f.side]};
      }
      const padding=26,rectangles=nodes.filter(v=>!v.junction&&v.parent===n.parent).map(v=>({x:v.x-padding,y:v.y-padding,w:v.w+padding*2,h:v.h+padding*2}));
      for(const v of nodes.filter(v=>v.id===parent.id||v.parent===n.parent))for(const b of v.labelObstacles||[])rectangles.push({x:v.x+b.x-3,y:v.y+b.y-3,w:b.w+6,h:b.h+6});
      const low={x:parent.x+12,y:parent.y+12},high={x:parent.x+parent.w-12,y:parent.y+parent.h-12};
      const peers=settled.filter(v=>v.parent===n.parent),free=p=>p.x>=low.x&&p.x<=high.x&&p.y>=low.y&&p.y<=high.y&&!rectangles.some(r=>inside(p,r))&&!peers.some(v=>R.dist(p,v)<20-EPS)&&(!outward||((p.x-outward.owner.x-outward.owner.w/2)*outward.normal[0]+(p.y-outward.owner.y-outward.owner.h/2)*outward.normal[1])>EPS);
      if(free(n)){settled.push(n);continue;}
      const xs=[n.x,low.x,high.x],ys=[n.y,low.y,high.y];
      for(const p of peers){xs.push(p.x-20,p.x+20);ys.push(p.y-20,p.y+20);}
      for(const r of rectangles){xs.push(r.x-1,r.x+r.w+1);ys.push(r.y-1,r.y+r.h+1);}
      const candidates=[...new Set(xs)].flatMap(x=>[...new Set(ys)].map(y=>({x,y}))).filter(free).sort((a,b)=>Math.abs(a.x-n.x)+Math.abs(a.y-n.y)-Math.abs(b.x-n.x)-Math.abs(b.y-n.y)||a.y-b.y||a.x-b.x);
      if(candidates.length){n.x=candidates[0].x;n.y=candidates[0].y;}settled.push(n);
    }
  }
  function packBands(items,origin,axis,gapLimit){
    const size=axis==='x'?'w':'h',bands=[];
    // Captions outside a glyph occupy real space too. The reference glyphs
    // define parallel bands; their visible caption envelopes define the free
    // corridor between bands, so contraction cannot trap an interface gate.
    const envelope=n=>({low:Math.min(0,...(n.labelObstacles||[]).map(b=>b[axis])),high:Math.max(n[size],...(n.labelObstacles||[]).map(b=>b[axis]+b[size]))});
    for(const b of items.filter(b=>!b.node.junction).slice().sort((a,b)=>a.ref[axis]-b.ref[axis])){
      const start=b.ref[axis],end=start+b.ref[size],last=bands.at(-1);
      if(last&&start<last.end-EPS){last.end=Math.max(last.end,end);last.items.push(b);}
      else bands.push({start,end,items:[b]});
    }
    let previous=null;
    for(const band of bands){
      const low=Math.min(...band.items.map(b=>b.ref[axis]-band.start+envelope(b.node).low));
      const start=previous?previous.actualEnd+Math.max(18,Math.min(gapLimit,band.start-previous.end))-low:band.start-origin;
      for(const b of band.items){const position=start+b.ref[axis]-band.start,delta=position-b.node[axis];for(const n of b.items)n[axis]+=delta;}
      band.actualEnd=Math.max(...band.items.map(b=>b.node[axis]+envelope(b.node).high));previous=band;
    }
  }
  function separateExpandedPeers(items){
    const glyphs=items.filter(b=>!b.node.junction);
    // A centered module can bridge both columns in the reference intervals.
    // Keep that alignment, but propagate expansion along the original order
    // when two parallel peers would otherwise touch or overlap.
    for(const axis of ['x','y']){
      const size=axis==='x'?'w':'h',cross=axis==='x'?'y':'x',extent=cross==='x'?'w':'h',limit=axis==='x'?64:40;
      const ordered=glyphs.slice().sort((a,b)=>a.ref[axis]-b.ref[axis]);
      for(const a of ordered)for(const b of ordered){
        if(a===b||a.ref[axis]+a.ref[size]>b.ref[axis]+EPS)continue;
        if(a.node[cross]+a.node[extent]<=b.node[cross]+EPS||b.node[cross]+b.node[extent]<=a.node[cross]+EPS)continue;
        const gap=Math.max(18,Math.min(limit,b.ref[axis]-a.ref[axis]-a.ref[size])),delta=a.node[axis]+a.node[size]+gap-b.node[axis];
        if(delta>EPS)for(const peer of glyphs.filter(v=>v.ref[axis]>=b.ref[axis]-EPS))for(const n of peer.items)n[axis]+=delta;
      }
    }
  }
  function layout(doc){
    const a=doc.authority,ids=visible(doc),out=[],templates=new Map();
    function build(source,parentRef){
      const has=children(a,source.id).length,open=has&&opened(doc,source.id),g=open?expandedTemplate(a,source):null;
      const ref=open?g.nodes.find(n=>n.id===source.id):parentRef&&!parentRef.expanded?parentRef:foldedVariant(a,source)||source;
      const n=copy(!open&&has&&ref.expanded?compact(source):ref);n.parent=source.parent;n.expanded=!!open;n.routingObstacle=!open&&!n.junction;
      n.recursiveVariant={source:open?a.variants.indexOf(g):-1,synthetic:!open&&has&&ref.expanded};
      templates.set(n.id,ref);out.push(n);if(!open)return {node:n,items:[n]};
      const kids=children(a,source.id).filter(v=>ids.has(v.id)),built=kids.map(s=>{
        // Junction IDs are local to each exported view. A same-named dot in
        // another module is not a positional template for this source child.
        const r=g.nodes.find(v=>v.id===s.id&&v.parent===source.id)||{...s,x:ref.x+s.x-source.x,y:ref.y+s.y-source.y};
        const b=build(s,r);b.ref=r;return b;
      });
      for(const b of built){const nx=b.ref.x-ref.x,ny=b.ref.y-ref.y,dx=nx-b.node.x,dy=ny-b.node.y;for(const k of b.items){k.x+=dx;k.y+=dy;}}
      // Overlapping source intervals form one row/column, preserving operand
      // alignment and parallel branches. Only visible sizes reserve space;
      // a folded child releases the band once occupied by its descendants.
      for(const axis of ['x','y'])packBands(built,ref[axis],axis,axis==='x'?64:40);
      separateExpandedPeers(built);
      // Arithmetic/tensor captions may extend left or above their symbol.
      // Keep the whole owned presentation inside the enclosing source frame.
      for(const axis of ['x','y']){
        const low=Math.min(...built.filter(b=>!b.node.junction).map(b=>b.node[axis]+Math.min(0,...(b.node.labelObstacles||[]).map(l=>l[axis])))),shift=Math.max(0,16-low);
        if(shift)for(const b of built)for(const k of b.items)k[axis]+=shift;
      }
      const local=doc.state.layouts[n.id]||{};
      for(const b of built){const offset=local[b.node.id];if(offset){for(const k of b.items){k.x+=offset.x;k.y+=offset.y;}}}
      const glyphs=built.filter(b=>!b.node.junction),padX=Math.max(24,Math.min(48,ref.x+ref.w-Math.max(...glyphs.map(b=>b.ref.x+b.ref.w)))),padY=Math.max(24,Math.min(48,ref.y+ref.h-Math.max(...glyphs.map(b=>b.ref.y+b.ref.h))));
      const minWidth=Math.min(...a.variants.flatMap(v=>v.nodes.filter(v=>v.id===n.id).map(v=>v.w))),labels=n.labelObstacles||[];
      n.w=Math.max(160,minWidth,...labels.map(b=>b.x+b.w+16),...glyphs.map(b=>b.node.x+Math.max(b.node.w,...(b.node.labelObstacles||[]).map(l=>l.x+l.w))+padX));n.h=Math.max(72,...labels.map(b=>b.y+b.h+20),...glyphs.map(b=>b.node.y+Math.max(b.node.h,...(b.node.labelObstacles||[]).map(l=>l.y+l.h))+padY));
      for(const b of built)for(const k of b.items){k.x+=n.x;k.y+=n.y;}
      return {node:n,items:[n,...built.flatMap(b=>b.items)]};
    }
    const roots=a.detail.nodes.filter(n=>!n.parent||!a.detail.nodes.some(p=>p.id===n.parent)),groups=roots.map(n=>{const b=build(n,null);b.ref=a.variants[0].nodes.find(v=>v.id===n.id)||n;return b;});
    // Reuse root columns and row alignment, releasing hidden descendant space
    // all the way to the canvas instead of reserving a future expanded view.
    for(const b of groups){const dx=b.ref.x-b.node.x,dy=b.ref.y-b.node.y;for(const k of b.items){k.x+=dx;k.y+=dy;}}
    for(const axis of ['x','y'])packBands(groups,0,axis,axis==='x'?112:48);
    separateExpandedPeers(groups);
    for(const b of groups){const offset=doc.state.layouts.$root?.[b.node.id];if(offset)for(const n of b.items){n.x+=offset.x;n.y+=offset.y;}}
    // A branch dot belongs to its source container, rather than whichever
    // child now covers its old pixels after a mixed expansion grows a module.
    settleJunctions(out,doc);return out;
  }
  function pointPort(n,p,inward=false){const ds=[['left',Math.abs(p.x-n.x),(p.y-n.y)/n.h],['right',Math.abs(p.x-n.x-n.w),(p.y-n.y)/n.h],['top',Math.abs(p.y-n.y),(p.x-n.x)/n.w],['bottom',Math.abs(p.y-n.y-n.h),(p.x-n.x)/n.w]].sort((a,b)=>a[1]-b[1]);return {side:ds[0][0],fraction:Math.max(.04,Math.min(.96,ds[0][2])),inward};}
  function projectedPort(doc,raw,side,id){
    if(id===raw[side])return copy(raw['fixed'+(side==='source'?'Source':'Target')]||{side:side==='source'?'top':'bottom',fraction:.5});
    const old=doc.authority.detail.nodes.find(n=>n.id===id),cross=C.crossings(raw.route,old).filter(g=>g.direction===(side==='source'?'exit':'enter'));
    const g=side==='source'?cross[0]:cross.at(-1);return g?{side:g.side,fraction:Math.max(.04,Math.min(.96,g.fraction)),inward:false}:pointPort(old,side==='source'?raw.route.at(-1):raw.route[0]);
  }
  function receipts(doc){let r=receiptCache.get(doc.authority);if(!r){r={nodes:new Map(doc.authority.detail.nodes.map(n=>[n.id,n])),edges:new Map(doc.authority.detail.edges.map(e=>[e.id,e])),variants:new Map()};for(const g of doc.authority.variants)for(const n of g.nodes){if(!r.variants.has(n.id))r.variants.set(n.id,[]);r.variants.get(n.id).push(n);}receiptCache.set(doc.authority,r);}return r;}
  function nodeTemplate(doc,n){
    // The geometry and its captions form one presentation. A mixed frontier
    // must not borrow the detailed captions of a compact rectangle.
    for(const [index,g] of doc.authority.variants.entries()){
      const v=g.nodes.find(v=>v.id===n.id&&v.html===n.html&&eq(v.base,n.base));
      if(v)return {index,graph:g,node:v};
    }
    return null;
  }
  function annotations(doc,nodes){
    const out=[];
    for(const n of nodes){const template=nodeTemplate(doc,n);if(!template)continue;
      const {index,graph,node:v}=template;
      for(const a of graph.attachments||[])if(a.owner===n.id){
        const [x,y,w,h]=a.bbox||[v.x,v.y,0,0],inside=x>=v.x-EPS&&y>=v.y-EPS&&x+w<=v.x+v.w+EPS&&y+h<=v.y+v.h+EPS;
        const horizontal=inside&&/text-anchor="end"/.test(a.html)?1:inside&&/text-anchor="middle"/.test(a.html)?.5:0;
        const vertical=inside?(n.expanded?(y>v.y+v.h/2&&y+h>v.y+v.h-28?1:0):.5):0;
        out.push({...copy(a),id:'recursive-caption:'+n.id+':'+a.id,presentation:{variant:index,id:a.id,base:copy(v.base),size:[v.w,v.h],horizontal,vertical}});
      }
    }
    return out;
  }
  function upgrade(graph){
    const doc=graph.recursive,adapterChanged=graph.sourceAdapter&&graph.sourceAdapter.presentationVersion!==doc?.authority.detail.sourceAdapter?.presentationVersion;
    if(!doc||doc.presentationVersion===PRESENTATION_VERSION&&!adapterChanged)return graph;
    // Retain expansion choices, local offsets, edits and label anchors. Only
    // projections made by the defective renderer are rebuilt.
    doc.state.frontiers={};doc.presentationVersion=PRESENTATION_VERSION;
    return build(doc);
  }
  function translateRoute(points,ds,dt){
    // Warp coordinate lanes, not individual vertices. Vertex-index blending
    // turns every horizontal/vertical segment into a diagonal after expansion.
    const start=points[0],end=points.at(-1);
    const shift=(p,axis)=>{const span=end[axis]-start[axis],ratio=Math.abs(span)>EPS?Math.max(0,Math.min(1,(p[axis]-start[axis])/span)):.5;return p[axis]+ds[axis]+(dt[axis]-ds[axis])*ratio;};
    return points.map(p=>({x:shift(p,'x'),y:shift(p,'y')}));
  }
  function separateGates(graph){
    // A compact ancestor can map several operands onto one recorded SVG
    // interface. Allocate physical boundary slots by tensor identity, just
    // like glyph ports; the projection never changes the source interface.
    const groups=new Map();
    for(const e of graph.edges)for(const gate of e.contract.gates){
      if(gate.frame===e.source||gate.frame===e.target)continue;
      const key=gate.frame+'|'+gate.side,entries=groups.get(key)||[];
      entries.push({e,gate});groups.set(key,entries);
    }
    for(const entries of groups.values()){
      const frame=graph.nodes.find(n=>n.id===entries[0].gate.frame),side=entries[0].gate.side;
      const size=['left','right'].includes(side)?frame.h:frame.w,slots=new Map();
      for(const entry of entries){const key=entry.e.contract.wire,list=slots.get(key)||[];list.push(entry);slots.set(key,list);}
      const axis=['left','right'].includes(side)?'y':'x';
      const ordered=[...slots.entries()].map(([wire,list])=>{
        const source=list[0].e.source,common=list.length>1&&list.every(x=>x.e.source===source),port=common&&E.endpoint(graph,list[0].e,'source'),coordinate=port?port[axis]-frame[axis]:list.reduce((v,x)=>v+x.gate.fraction*size,0)/list.length;
        return {wire,list,coordinate,anchor:port&&coordinate>12&&coordinate<size-12?'source':null};
      }).sort((a,b)=>a.coordinate-b.coordinate||a.wire.localeCompare(b.wire));
      const pad=Math.max(12,...entries.map(x=>C.borderClearance(x.e,frame)+1)),spacing=Math.min(14,(size-2*pad)/Math.max(1,ordered.length-1));
      let cursor=pad-spacing;
      for(const slot of ordered){slot.coordinate=Math.max(cursor+spacing,Math.min(size-pad,slot.coordinate));cursor=slot.coordinate;}
      cursor=size-pad+spacing;
      for(const slot of ordered.slice().reverse()){slot.coordinate=Math.min(cursor-spacing,slot.coordinate);cursor=slot.coordinate;}
      for(const slot of ordered)for(const {e,gate} of slot.list){
        const fraction=slot.coordinate/size;
        if(Math.abs(fraction-gate.fraction)<EPS&&!slot.anchor)continue;
        gate.fraction=fraction;
        for(const p of Object.values(e.portPolicy))p.gates=p.gates.filter(g=>g.frame!==gate.frame||g.side!==gate.side||g.direction!==gate.direction);
        const f=root.SummaryPhysicalPorts.active(e,'source');
        if(slot.anchor&&Math.abs(slot.coordinate-(E.endpoint(graph,e,'source')[axis]-frame[axis]))<EPS&&(['top','bottom'].includes(f.side)===['top','bottom'].includes(gate.side)))e.portPolicy.source.gates.push({...copy(gate),anchor:'source'});
      }
    }
  }
  function build(doc){
    const ids=visible(doc),cached=doc.state.frontiers[signature(doc)],source=exact(doc),detail=doc.authority.detail;
    if(cached){const g=copy(cached);g.recursive=doc;return g;}
    const g=copy(source||detail);g.nodes=source?copy(source.nodes):layout(doc);g.viewKey='recursive';g.edges=[];g.routeLabels=[];g.attachments=[];g.junctionMarkers=[];g.extras=source?.extras||'';delete g.semanticBaseline;
    const by=new Map(g.nodes.map(n=>[n.id,n])),rawBy=new Map(detail.nodes.map(n=>[n.id,n]));
    const matching=(raw,s,t)=>doc.authority.variants.flatMap(v=>v.edges.map(e=>({e,g:v,score:semanticKey(e)===semanticKey(raw)?100:trace(e).filter(id=>trace(raw).includes(id)).length}))).filter(v=>v.e.source===s&&v.e.target===t&&v.score>0).sort((a,b)=>a.score-b.score);
    if(source){const offsets=new Map();function delta(id){if(offsets.has(id))return offsets.get(id);const n=by.get(id),p=n?.parent&&by.has(n.parent)?delta(n.parent):{x:0,y:0},own=doc.state.layouts[n?.parent||'$root']?.[id]||{x:0,y:0},v={x:p.x+own.x,y:p.y+own.y};offsets.set(id,v);return v;}for(const n of g.nodes){const d=delta(n.id);n.x+=d.x;n.y+=d.y;}}
    for(const raw of detail.edges){const s=representative(doc,raw.source,ids),t=representative(doc,raw.target,ids);if(!s||!t||s===t&&raw.source!==raw.target)continue;
      const match=matching(raw,s,t).find(v=>source===v.g)||matching(raw,s,t).at(-1),e=copy(raw),visual=match?.e;
      e.source=s;e.target=t;e.projection={original:raw.id,source:raw.source,target:raw.target};e.binding=copy(raw.binding);e.waypoints=[];
      for(const side of ['source','target']){const k=side==='source'?'Source':'Target',fixed=copy(visual?.['fixed'+k]||projectedPort(doc,raw,side,e[side]));if(e[side]!==raw[side]||!by.get(e[side]).expanded)fixed.inward=false;if(fixed.offset&&!by.get(e[side]).visualBinding&&!by.get(e[side]).junction){delete fixed.offset;}e['fixed'+k]=fixed;delete e['physical'+k];delete e['sourcePort'];delete e['targetPort'];
        const policy=copy(visual?.portPolicy?.[side]||raw.portPolicy?.[side]||{mode:'fixed',shape:'rectangle',spacing:12});
        if(e[side]!==raw[side]||!!by.get(e[side]).expanded!==!!rawBy.get(raw[side])?.expanded){
          // A folded module retains its canonical field identity, but its
          // compact rectangle is free to use a legal perimeter port. Pinning
          // an operator's original side onto a summary box can trap an arrow
          // behind another operand or make a neighbouring terminal overlap.
          policy.mode=by.get(e[side]).expanded?'fixed':'perimeter';policy.shape='rectangle';policy.sharedStem=null;
        }
        if(by.get(e[side]).junction){policy.mode='perimeter';policy.shape='rectangle';}
        policy.gates=[];policy.sharedStem=null;e.portPolicy=e.portPolicy||{};e.portPolicy[side]=policy;
      }
      const oldRoute=visual?.route||raw.route,refNodes=match?.g.nodes||detail.nodes;
      // A projected edge may be attached to a visible ancestor while its
      // stored route still uses the original endpoint coordinates.  Resolve
      // the translation against the route's actual endpoints first; using the
      // visible representative here shifts the first/last lane and can make
      // an orthogonal route approach the wrong side of a port.
      const routeSourceId=visual?.source||raw.source,routeTargetId=visual?.target||raw.target;
      const rs=refNodes.find(n=>n.id===routeSourceId)||rawBy.get(routeSourceId)||refNodes.find(n=>n.id===s)||rawBy.get(raw.source);
      const rt=refNodes.find(n=>n.id===routeTargetId)||rawBy.get(routeTargetId)||refNodes.find(n=>n.id===t)||rawBy.get(raw.target);
      const ns=by.get(s),nt=by.get(t),ds={x:ns.x-rs.x,y:ns.y-rs.y},dt={x:nt.x-rt.x,y:nt.y-rt.y};
      e.route=translateRoute(oldRoute,ds,dt);
      const sharedAncestors=C.ancestors({nodes:g.nodes},s).filter(id=>C.ancestors({nodes:g.nodes},t).includes(id)&&id!==s&&id!==t);
      const sourceFrames=C.ancestors({nodes:g.nodes},s),targetFrames=C.ancestors({nodes:g.nodes},t),seenGates=new Set();
      const gates=copy(visual?.contract?.gates||raw.contract?.gates||[]).sort((a,b)=>a.order-b.order).filter(gate=>{
        if(sharedAncestors.includes(gate.frame)||!by.get(gate.frame)?.expanded||!sourceFrames.concat(targetFrames).includes(gate.frame))return false;
        if(gate.frame===s||gate.frame===t)return true;
        // The original SVG may leave and re-enter a frame merely to bypass
        // a neighbour. A new frontier needs only the source-to-target boundary
        // transit. Forcing both optional gates onto an aligned slot would
        // require an immediate U-turn and make every legal route impossible.
        const direction=sourceFrames.includes(gate.frame)?'exit':'enter';
        if(gate.direction!==direction||seenGates.has(gate.frame))return false;
        seenGates.add(gate.frame);return true;
      });
      e.contract={version:1,source:s,target:t,wire:C.wireIdentity(raw),bus:false,gates,sharedStem:null,enforcePortApproach:true,minimumTerminal:9};
      e.route[0]=E.endpoint(g,e,'source');e.route[e.route.length-1]=E.endpoint(g,e,'target');
      // The route is exact when a registered frontier matches. Preserve its
      // physical slots, stems and branch dots without rebuilding that layout.
      if(source&&visual){e.fixedSource=copy(visual.fixedSource);e.fixedTarget=copy(visual.fixedTarget);e.route=translateRoute(visual.route,ds,dt);e.contract=copy(visual.contract);e.contract.wire=C.wireIdentity(raw);e.contract.source=s;e.contract.target=t;e.portPolicy=copy(visual.portPolicy);for(const k of ['physicalSource','physicalTarget'])if(visual[k])e[k]=copy(visual[k]);}e.route[0]=E.endpoint(g,e,'source');e.route[e.route.length-1]=E.endpoint(g,e,'target');
      e.projection.visual=visual?.id||null;e.projection.presentationSlots={source:root.SummaryPhysicalPorts.slot(visual||raw,'source'),target:root.SummaryPhysicalPorts.slot(visual||raw,'target')};
      const peer=visual&&g.edges.find(v=>v.source===s&&v.target===t&&v.contract.wire===e.contract.wire&&v.projection.visual===visual.id&&(s!==raw.source||t!==raw.target));
      if(peer){peer.projection.originals=peer.projection.originals||[peer.projection.original];peer.projection.originals.push(raw.id);}else g.edges.push(e);
    }
    if(!source){for(const n of g.nodes){const slots=[];for(const e of g.edges)for(const side of ['source','target'])if(e[side]===n.id){const k=side==='source'?'Source':'Target',f=e['fixed'+k],destination=e.binding?.endpoint_binding?.destination;
      // A compact SVG may depict a collection with one summary arrow. When
      // the frontier keeps separate tensor edges, its actual operand fields
      // still need separate input slots; a shared visual edge ID does not
      // license mu/logvar or concat operand[0..2] to become one wire.
      const identity=n.expanded?(e.binding?.[side==='source'?'src':'dst']||f.side):side==='source'?e.contract.wire:JSON.stringify([e.projection.target,destination?.port||e.binding?.dst,destination?.operand??null]);
      let slot=slots.find(s=>s.side===f.side&&s.identity===identity);if(!slot){slot={side:f.side,identity,edges:[]};slots.push(slot);}slot.edges.push([e,k]);}for(const side of ['left','right','top','bottom']){const grouped=slots.filter(s=>s.side===side);if(grouped.length>1&&!n.expanded&&children(doc.authority,n.id).length)grouped.forEach((slot,i)=>slot.edges.forEach(([e,k])=>{e['fixed'+k]={side,fraction:(i+1)/(grouped.length+1),inward:e['fixed'+k].inward};}));}}}
    if(!source){for(const e of g.edges){for(const side of ['source','target']){const k=side==='source'?'Source':'Target',n=by.get(e[side]),other=by.get(e[side==='source'?'target':'source']),f=e['fixed'+k];if(n.expanded&&other?.junction){const axis=['top','bottom'].includes(f.side)?'x':'y',size=axis==='x'?'w':'h',fraction=(other[axis]-n[axis])/n[size];if(fraction>.04&&fraction<.96)e['fixed'+k]={side:f.side,fraction,inward:f.inward};}}}for(const e of g.edges)for(const gate of e.contract.gates){const side=gate.frame===e.source?'source':gate.frame===e.target?'target':null;if(side){const f=e[side==='source'?'fixedSource':'fixedTarget'];if(f.side===gate.side)gate.fraction=f.fraction;}}}
    if(!source){for(const e of g.edges)for(const gate of e.contract.gates){const side=gate.direction==='exit'?'source':'target',f=e[side==='source'?'fixedSource':'fixedTarget'],frame=by.get(gate.frame),owner=by.get(e[side]);if(!frame||frame.id===owner.id||f.side!==gate.side)continue;const axis=['top','bottom'].includes(gate.side)?'x':'y',size=axis==='x'?'w':'h',p=E.port(owner,f),fraction=(p[axis]-frame[axis])/frame[size],pad=(C.borderClearance(e,frame)+1)/frame[size];if(fraction>pad&&fraction<1-pad){gate.fraction=fraction;e.portPolicy[side].gates.push({...copy(gate),anchor:side});}}}
    if(!source){for(const e of g.edges){const groups=new Map();for(const gate of e.contract.gates){if(gate.frame===e.source||gate.frame===e.target)continue;const key=gate.side+':'+gate.direction,gates=groups.get(key)||[];gates.push(gate);groups.set(key,gates);}for(const gates of groups.values())if(gates.length>1){const axis=['left','right'].includes(gates[0].side)?'y':'x',size=axis==='x'?'w':'h',low=Math.max(...gates.map(g=>by.get(g.frame)[axis]+12)),high=Math.min(...gates.map(g=>by.get(g.frame)[axis]+by.get(g.frame)[size]-12));if(low<high){const anchor=gates[0].direction==='exit'?'source':'target',f=e[anchor==='source'?'fixedSource':'fixedTarget'],endpoint=E.port(by.get(e[anchor]),f),coordinate=Math.max(low,Math.min(high,endpoint[axis]));for(const gate of gates)gate.fraction=(coordinate-by.get(gate.frame)[axis])/by.get(gate.frame)[size];}}}
    const groups=new Map();for(const e of g.edges){const f=e.fixedSource,key=e.source+'|'+e.contract.wire+'|'+f.side+'|'+f.fraction+'|'+f.inward;const group=groups.get(key)||[];group.push(e);groups.set(key,group);}for(const es of groups.values())if(es.length>1){const n=by.get(es[0].source),f=es[0].fixedSource,p=E.port(n,f),axis=['left','right'].includes(f.side)?'x':'y',sign=(['top','left'].includes(f.side)?-1:1)*(f.inward?-1:1);const stem={side:f.side,length:14,axis,coordinate:p[axis]-(n[axis]-n.base[axis==='x'?0:1])+sign*14,owner:n.id};for(const e of es){e.portPolicy.source.sharedStem=copy(stem);e.contract.sharedStem=copy(stem);}}}
    if(!source){for(const e of g.edges)for(const gate of e.contract.gates){const side=gate.frame===e.source?'source':gate.frame===e.target?'target':null;if(side){const f=e[side==='source'?'fixedSource':'fixedTarget'];if(f.side===gate.side)gate.fraction=f.fraction;}}}
    if(!source)separateGates(g);
    // Slot allocation is complete. Bind route terminals once, to these final
    // slots, before the router or verifier sees the frontier.
    for(const e of g.edges){e.route[0]=E.endpoint(g,e,'source');e.route[e.route.length-1]=E.endpoint(g,e,'target');}
    for(const n of g.nodes){const template=nodeTemplate(doc,n),variant=template?.node;n.projectionVariant=variant?{index:template.index,html:variant.html,base:variant.base,w:variant.w,h:variant.h}:null;}
    g.sourceDraftOperations=copy(doc.state.draftOperations||[]);const removed=new Set(g.sourceDraftOperations.filter(op=>op.kind==='remove-connection').map(op=>op.id));g.edges=g.edges.filter(e=>!(e.projection.originals||[e.projection.original]).every(id=>removed.has(id)));for(const e of g.edges){const edit=doc.state.edgeEdits?.[e.projection.original];if(edit)Object.assign(e,copy(edit));}for(const draft of doc.state.drafts||[]){const e=copy(draft),s=representative(doc,e.source,ids),t=representative(doc,e.target,ids);if(!s||!t||s===t&&e.source!==e.target)continue;e.source=s;e.target=t;delete e.contract;e.fixedSource=e.fixedSource||{side:'top',fraction:.5};e.fixedTarget=e.fixedTarget||{side:'bottom',fraction:.5};e.route=[E.endpoint(g,e,'source'),E.endpoint(g,e,'target')];const sourceIds=new Set(e.projection?.originals||[e.projection?.original]);g.edges=g.edges.filter(v=>v.id!==e.id&&!(v.projection?.originals||[v.projection?.original]).some(id=>id!==undefined&&sourceIds.has(id)));g.edges.push(e);C.initialize(g);}
    const present=new Set(g.edges.map(e=>e.id));
    const labelSources=source?[source]:[detail];
    for(const v of labelSources){for(const label of v.routeLabels||[]){const edge=presentationEdge(g,v.edges.find(e=>e.id===label.edge));if(edge){const a=copy(label);a.edge=edge.id;if(doc.state.captionAnchors?.[a.id])a.anchor=copy(doc.state.captionAnchors[a.id]);g.routeLabels.push(a);}}
      for(const m of source?v.junctionMarkers||[]:[]){const mapped=m.edges.map(id=>presentationEdge(g,v.edges.find(e=>e.id===id))?.id);if(mapped.every(id=>present.has(id))&&new Set(mapped).size>1)g.junctionMarkers.push({...copy(m),edges:[...new Set(mapped)]});}}
    g.attachments=annotations(doc,g.nodes);
    g.canvas=source?copy(source.canvas):[Math.max(detail.canvas[0],...g.nodes.map(n=>n.x+n.w+80)),Math.max(720,...g.nodes.map(n=>n.y+n.h+120))];g.recursive=doc;
    g.recursiveReceipt={signature:signature(doc),edges:Object.fromEntries(g.edges.map(e=>[e.id,{source:e.source,target:e.target,fixedSource:copy(e.fixedSource),fixedTarget:copy(e.fixedTarget),portPolicy:copy(e.portPolicy),contract:copy(e.contract),projection:copy(e.projection)}]))};
    g.recursiveReceipt.annotations={labels:copy(g.routeLabels.map(a=>Object.fromEntries(Object.entries(a).filter(([k])=>k!=='anchor')))),attachments:copy(g.attachments)};
    return g;
  }
  function remember(graph){const doc=graph.recursive;if(!doc)return;doc.state.edgeEdits=doc.state.edgeEdits||{};for(const e of graph.edges)if(!e.draft)for(const id of e.projection?.originals||[e.projection?.original])doc.state.edgeEdits[id]={arrow:e.arrow,style:e.style};doc.state.draftOperations=copy(graph.sourceDraftOperations||[]);doc.state.drafts=copy(graph.edges.filter(e=>e.draft));doc.state.captionAnchors={...(doc.state.captionAnchors||{}),...Object.fromEntries((graph.routeLabels||[]).filter(a=>a.anchor).map(a=>[a.id,a.anchor]))};
    const g=copy({...graph,recursive:undefined});doc.state.frontiers[signature(doc)]=g;
    // Limit cache size, retaining local offsets and the complete open tree.
    const keys=Object.keys(doc.state.frontiers);if(keys.length>16)delete doc.state.frontiers[keys[0]];
  }
  function captureMove(before,after,id){const doc=after.recursive;if(!doc)return;const a=before.nodes.find(n=>n.id===id),b=after.nodes.find(n=>n.id===id);if(!a||!b)return;const dx=b.x-a.x,dy=b.y-a.y;if(!dx&&!dy)return;
    const parent=b.parent||'$root';doc.state.layouts[parent]=doc.state.layouts[parent]||{};const old=doc.state.layouts[parent][id]||{x:0,y:0};doc.state.layouts[parent][id]={x:old.x+dx,y:old.y+dy};
    const all=doc.authority.detail.nodes,desc=new Set([id]);let changed=true;while(changed){changed=false;for(const n of all)if(desc.has(n.parent)&&!desc.has(n.id)){desc.add(n.id);changed=true;}}
    for(const cached of Object.values(doc.state.frontiers)){for(const n of cached.nodes)if(desc.has(n.id)){n.x+=dx;n.y+=dy;}for(const e of cached.edges)if(desc.has(e.source)&&desc.has(e.target)){e.route=e.route.map(p=>({x:p.x+dx,y:p.y+dy}));}else if(desc.has(e.source)||desc.has(e.target)){e.needsRecursiveRouting=true;}}
    remember(after);
  }
  function toggle(graph,id,force){const doc=graph.recursive;if(!doc||!children(doc.authority,id).length||doc.authority.mandatory.includes(id))return null;remember(graph);const next=force===undefined?!opened(doc,id):force;
    if(next){if(!doc.state.open.includes(id))doc.state.open.push(id);doc.state.folded=doc.state.folded.filter(v=>v!==id);}else {if(!doc.state.folded.includes(id))doc.state.folded.push(id);}doc.revision++;return build(doc);
  }
  function all(graph,open){const doc=graph.recursive;remember(graph);if(open){doc.state.open=containers(doc.authority);doc.state.folded=[];}else{doc.state.folded=containers(doc.authority).filter(id=>!doc.authority.mandatory.includes(id));}doc.revision++;return build(doc);}
  function nodeErrors(graph){const doc=graph.recursive;if(!doc)return[];const errors=[],a=doc.authority,r=receipts(doc),ids=visible(doc),actual=new Set(graph.nodes.map(n=>n.id));
    if(!eq([...ids].sort(),[...actual].sort()))errors.push('recursive frontier node set changed');
    const fingerprint=JSON.stringify({nodes:a.detail.nodes.map(n=>[n.id,n.parent,n.semantic,n.visualBinding,n.glyphPresentation,n.html]),edges:a.detail.edges.map(e=>[e.id,e.source,e.target,e.binding,e.fixedSource,e.fixedTarget,e.portPolicy]),baseline:a.detail.semanticBaseline});if(r.authorityFingerprint!==fingerprint){r.authorityCheck=root.SummarySourceContracts.validateGraph(a.detail);r.authorityFingerprint=fingerprint;}errors.push(...r.authorityCheck.violations.map(e=>'recursive authority: '+e));
    if(graph.irSha256!==a.detail.irSha256)errors.push('source IR digest changed');
    for(const n of graph.nodes){const raw=r.nodes.get(n.id);if(!raw){errors.push('unregistered recursive source node '+n.id);continue;}
      for(const k of ['parent','semantic','visualBinding'])if(!eq(n[k]||null,raw[k]||null))errors.push('recursive source '+k+' changed '+n.id);
      const known=(r.variants.get(n.id)||[]).find(v=>v.html===n.html);if(!known&&n.html!==compact(raw).html)errors.push('recursive source glyph markup changed '+n.id);
      if(known&&(!eq(n.glyphPresentation||null,known.glyphPresentation||null)||!eq(n.labelObstacles||[],known.labelObstacles||[])))errors.push('recursive glyph metadata changed '+n.id);
      if(!!n.expanded!==!!(children(a,n.id).length&&opened(doc,n.id)))errors.push('recursive expansion receipt changed '+n.id);
      if(n.glyphPresentation&&(n.w!==raw.w||n.h!==raw.h))errors.push('recursive source glyph size changed '+n.id);
      if(n.parent){const p=graph.nodes.find(v=>v.id===n.parent);if(p&&n.glyphPresentation)for(const b of n.labelObstacles||[])if(n.x+b.x<p.x-EPS||n.y+b.y<p.y-EPS||n.x+b.x+b.w>p.x+p.w+EPS||n.y+b.y+b.h>p.y+p.h+EPS)errors.push('recursive caption leaves owner '+n.id);if(p&&(n.x<p.x-EPS||n.y<p.y-EPS||n.x+n.w>p.x+p.w+EPS||n.y+n.h>p.y+p.h+EPS))errors.push('recursive child leaves owner '+n.id);}
    }if(!eq((graph.routeLabels||[]).map(a=>Object.fromEntries(Object.entries(a).filter(([k])=>k!=='anchor'))),graph.recursiveReceipt?.annotations?.labels||[]))errors.push('recursive source captions changed');if(!eq(graph.attachments||[],annotations(doc,graph.nodes)))errors.push('recursive source captions missing or ownership changed');
    for(const m of graph.junctionMarkers||[]){const es=m.edges.map(id=>graph.edges.find(e=>e.id===id));if(es.some(e=>!e)||!graph.nodes.some(n=>n.id===m.owner)||es.some(e=>e.contract.wire!==es[0].contract.wire))errors.push('recursive junction provenance changed');}
    return errors;
  }
  function edgeErrors(graph,e,points=e.route){if(!graph.recursive)return[];const errors=[],doc=graph.recursive,raw=receipts(doc).edges.get(e.projection?.original);
    if(e.draft){
      // Draft endpoints may change visually; audited bindings and the original
      // projection receipt continue to identify the source relationship.
      const registered=graph.recursiveReceipt?.edges[e.id],sourceIdentity=registered?.projection||receipts(doc).edges.has(e.id);
      if(sourceIdentity||e.projection){if(!e.projection||!registered?.projection||!eq(e.projection,registered.projection))errors.push('recursive draft source provenance changed');if(!raw||!eq(e.binding,raw.binding))errors.push('recursive draft canonical binding changed');}
      return errors;
    }
    if(!raw){errors.push('recursive edge lacks source provenance');return errors;}
    const registered=graph.recursiveReceipt?.edges[e.id];if(!registered){errors.push('recursive projection receipt missing');}else for(const k of ['source','target','fixedSource','fixedTarget','portPolicy','contract','projection'])if(!eq(e[k],registered[k]))errors.push('recursive presentation contract changed '+k);
    if(!eq(e.binding,raw.binding))errors.push('recursive canonical binding changed');
    if(e.source!==representative(doc,raw.source)||e.target!==representative(doc,raw.target))errors.push('recursive edge projection changed');
    if(!eq({original:e.projection.original,source:e.projection.source,target:e.projection.target},{original:raw.id,source:raw.source,target:raw.target}))errors.push('recursive edge provenance changed');
    if(e.contract?.wire!==C.wireIdentity(raw))errors.push('recursive wire identity changed');
    for(const gate of e.contract?.gates||[]){const licensed=doc.authority.variants.some(v=>v.edges.some(ve=>(semanticKey(ve)===semanticKey(raw)||trace(ve).some(id=>trace(raw).includes(id)))&&(ve.contract?.gates||[]).some(g=>g.frame===gate.frame&&g.side===gate.side&&g.direction===gate.direction)));
      if(!licensed)errors.push('recursive boundary has no source interface '+gate.frame);}
    errors.push(...root.SummaryPhysicalPorts.errors(graph,e,points));return errors;
  }
  function validate(graph){const errors=nodeErrors(graph),doc=graph.recursive;if(!doc)return {ok:true,violations:[]};const ids=visible(doc),seen=new Set();
    for(const e of graph.edges){errors.push(...edgeErrors(graph,e).map(v=>e.id+': '+v));if(!e.draft&&seen.has(e.projection?.original))errors.push('duplicate recursive source edge');for(const id of e.projection?.originals||[e.projection?.original]){if(e.draft){if(id!==undefined)seen.add(id);continue;}const raw=receipts(doc).edges.get(id);if(!raw||e.source!==representative(doc,raw.source,ids)||e.target!==representative(doc,raw.target,ids)||e.contract?.wire!==C.wireIdentity(raw))errors.push('recursive bundled source provenance changed '+id);seen.add(id);}}
    for(const raw of doc.authority.detail.edges){const s=representative(doc,raw.source,ids),t=representative(doc,raw.target,ids);if(s&&t&&(s!==t||raw.source===raw.target)&&!seen.has(raw.id)&&!(graph.sourceDraftOperations||[]).some(op=>op.kind==='remove-connection'&&op.id===raw.id&&eq(op.binding,raw.binding)))errors.push('recursive source edge missing '+raw.id);}
    return {ok:!errors.length,violations:[...new Set(errors)]};
  }
  function route(graph,options={}){C.initialize(graph);const context=C.validationContext(graph);
    // Keep the complete invalid frontier in one routing transaction.  The
    // inexpensive elbow pass below may find a legal path for one branch, but
    // leaving that branch out of the batch makes its temporary lane an
    // obstacle for a sibling (especially a shared mu/logvar or z fan-out).
    // Routing all edges that were invalid at the start lets the batch reserve
    // lanes consistently and keeps repeated calls deterministic.
    const initialInvalid=new Set(graph.edges.filter(e=>e.needsRecursiveRouting||C.needsLaneRepair(graph,e,context)||!C.validate(graph,e,e.route,context).ok||E.overlapsWire(graph,e,e.route)).map(e=>e.id));
    // Short boundary-to-boundary links can be smaller than the visibility
    // router's padded stubs. Test exact legal paths before graph search.
    const normals={left:[-1,0],right:[1,0],top:[0,-1],bottom:[0,1]};
    for(const e of graph.edges){if(C.validate(graph,e,e.route,context).ok&&!C.needsLaneRepair(graph,e,context))continue;const s=E.endpoint(graph,e,'source'),t=E.endpoint(graph,e,'target'),candidates=[[s,t],[s,{x:s.x,y:t.y},t],[s,{x:t.x,y:s.y},t],[s,{x:s.x,y:(s.y+t.y)/2},{x:t.x,y:(s.y+t.y)/2},t],[s,{x:(s.x+t.x)/2,y:s.y},{x:(s.x+t.x)/2,y:t.y},t]],stem=C.sharedStemPoint(graph,e,{...context,boundaryLanes:true});
      for(const length of [6,9,14,24]){const fs=root.SummaryPhysicalPorts.active(e,'source'),ft=root.SummaryPhysicalPorts.active(e,'target'),ns=normals[fs.side],nt=normals[ft.side],a=stem||{x:s.x+ns[0]*length*(fs.inward?-1:1),y:s.y+ns[1]*length*(fs.inward?-1:1)},b={x:t.x+nt[0]*length*(ft.inward?-1:1),y:t.y+nt[1]*length*(ft.inward?-1:1)};candidates.push([s,a,{x:a.x,y:b.y},b,t],[s,a,{x:b.x,y:a.y},b,t]);}
      const cost=ps=>ps.slice(1).reduce((v,p,i)=>v+R.dist(ps[i],p),0)+ps.length*40;
      const legal=candidates.map(R.simplify).filter(ps=>C.validate(graph,e,ps,context).ok&&!C.laneContacts(graph,e,ps,context).length&&!C.constraints(graph,e,{margin:0},context).extraObstacles.filter(b=>b.id?.startsWith('label:')).some(b=>ps.slice(1).some((p,i)=>R.intersectsRect(ps[i],p,b)))&&!graph.edges.some(v=>v!==e&&C.validate(graph,v,v.route,context).ok&&v.contract.wire!==e.contract.wire&&ps.slice(1).some((p,i)=>v.route.slice(1).some((q,j)=>R.overlap(ps[i],p,v.route[j],q)>1e-5)))).sort((a,b)=>cost(a)-cost(b));
      if(legal.length){e.route=legal[0];e.failed=false;delete e.reason;}
    }
    const ids=graph.edges.filter(e=>initialInvalid.has(e.id)||e.needsRecursiveRouting||!C.validate(graph,e,e.route,context).ok).map(e=>e.id);if(!ids.length){const topology=C.validateJunctions(graph);return {graph,routed:0,failed:topology.ok?0:1,...(!topology.ok?{reason:topology.violations.join('; ')}:{})};}
    for(const e of graph.edges){delete e.needsRecursiveRouting;if(ids.includes(e.id)){e.waypoints=C.activeGates(graph,e).filter(g=>g.frame!==e.source&&g.frame!==e.target).sort((a,b)=>a.order-b.order).flatMap(g=>{const frame=graph.nodes.find(n=>n.id===g.frame),p=C.gatePoint(frame,g),normal=normals[g.side],pad=C.laneClearances(graph,e,frame,context)[g.side],sign=g.direction==='enter'?1:-1,before=sign>0?pad.outside:pad.inside,after=sign>0?pad.inside:pad.outside;return [{x:p.x+normal[0]*before*sign,y:p.y+normal[1]*before*sign},{x:p.x-normal[0]*after*sign,y:p.y-normal[1]*after*sign}];});}}
    const batchOptions={margin:4,stub:14,bendCost:40,crossingCost:180,overlapCost:2,edgeSpacing:10,sides:'any',style:'orthogonal',optimizeCrossings:false,groupByWire:true,...options,preserve:true};
    const result=E.routeBatch(graph,ids,batchOptions);
    if(!graph.junctionMarkers.length){const groups=new Map();for(const e of graph.edges){const key=e.source+'|'+e.contract.wire,es=groups.get(key)||[];es.push(e);groups.set(key,es);}for(const es of groups.values())if(es.length>1){const raw=graph.recursive.authority.detail.junctionMarkers?.find(m=>m.edges.some(id=>es.some(e=>e.projection.original===id))),owner=es[0].source;if(!raw)continue;const marker={...copy(raw),id:'recursive-fork:'+es[0].id,owner,edges:es.map(e=>e.id),original:[graph.nodes.find(n=>n.id===owner).base[0],graph.nodes.find(n=>n.id===owner).base[1]],fragments:[]};if(root.SummaryJunctionMarkers.point(graph,marker))graph.junctionMarkers.push(marker);}}
    return result;}
  const api={create,children,containers,opened,visible,representative,signature,build,toggle,all,remember,captureMove,nodeErrors,edgeErrors,validate,route,upgrade,annotations};root.SummaryRecursive=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
