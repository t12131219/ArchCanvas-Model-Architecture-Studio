/* A measured architecture composition, independent of model names. This is
 * a drawing projection: canonical operations, calls and edges are untouched. */
(function(root){
  'use strict';
  const P=root.SemanticPublication||(typeof require==='function'?require('./publication.js'):null);
  const E=root.SemanticEngine||(typeof require==='function'?require('./semantic-engine.js'):null);
  const L=root.SemanticLayout||(typeof require==='function'?require('./architecture-layout.js'):null);
  function compose(graph,state={}){
    const old=graph.positions,source=old.context.idx;
    const nodes=graph.nodes.map(n=>({...n,paper:{...n.paper}})),by=new Map(nodes.map(n=>[n.id,n]));
    const idx={nodes:new Map(source.nodes),children:new Map()};
    for(const n of nodes){
      let parent=source.nodes.get(n.id)?.parent;while(parent&&!by.has(parent))parent=source.nodes.get(parent)?.parent;
      idx.nodes.set(n.id,{...source.nodes.get(n.id),parent,paper:n.paper});
      if(!idx.children.has(parent||null))idx.children.set(parent||null,[]);idx.children.get(parent||null).push(n.id);
    }
    // Keep nonvisible children in the drawing index too: controls need them
    // to reopen closed summaries. Only visible children participate in layout.
    for(const n of source.nodes.values())if(!by.has(n.id)){
      if(!idx.children.has(n.parent||null))idx.children.set(n.parent||null,[]);idx.children.get(n.parent||null).push(n.id);
    }
    const positions=new Map(),records=[],docks=[],followers=[],streamAlignments=[],streamCompactions=[],sourceKindNotes=[],streamHeadings=[],moduleColumns=[],pathRows=[];
    // Typographic sizes apply to every model. Evidence-heavy summaries keep
    // their wider source size; a semantic role path uses the same narrow
    // column regardless of which certificate established that path.
    const columns=state.paperArchitectureColumns!==false;
    const metrics={card_min_width:240,card_max_width:320,title_fit:'bounded-natural-width',role_path_width:192,sibling_gap:48,sequence_gap:24,
      overview_module_em:columns&&graph.publication.granularity==='stages'?32:0};
    const parents=id=>{const ids=[];while(id){ids.push(id);id=idx.nodes.get(id)?.parent;}return ids;};
    const ordinary=e=>(e.bundle_members||[e]).every(m=>['data','alias','interface-binding'].includes(m.kind)&&!m.condition&&!m.iteration);
    for(const n of nodes){
      const uses=graph.edges.filter(e=>e.source===n.id),oldParent=idx.nodes.get(n.id)?.parent;
      if(n.kind!=='interface'||n.role!=='input'||!uses.length||uses.some(e=>!ordinary(e))||graph.edges.some(e=>e.target===n.id)||n.condition||n.mutable)continue;
      const owners=uses.map(e=>parents(idx.nodes.get(e.target)?.parent));
      const owner=owners[0].find(id=>owners.every(xs=>xs.includes(id)));
      if(!owner||owner===oldParent||!parents(owner).includes(oldParent)||!old.get(owner)?.expanded||
        parents(owner).some(id=>{const a=idx.nodes.get(id);return a?.condition||a?.mutable||['opaque','control'].includes(a?.kind);} ))continue;
      idx.children.set(oldParent,(idx.children.get(oldParent)||[]).filter(id=>id!==n.id));
      if(!idx.children.has(owner))idx.children.set(owner,[]);idx.children.get(owner).push(n.id);
      idx.nodes.set(n.id,{...idx.nodes.get(n.id),parent:owner});n.parent=owner;
      docks.push({node:n.id,source_parent:oldParent,drawing_parent:owner,kind:uses.length===1?'entry':'side',
        edges:uses.map(e=>({edge:e.id,target:e.target,source_port:e.source_port,target_port:e.target_port})),
        scope:'One existing external input moved into its receiving drawing scope. Canonical parent, identity, every use and source availability remain unchanged.'});
    }
    const children=id=>(idx.children.get(id)||[]).filter(id=>old.has(id));
    // A column is a drawing correspondence, not common computation or shared
    // parameters. Widen existing source/semantic frames only; keep their
    // children, headers, source ownership and all exact edges independent.
    function widen(id,width){
      const p=positions.get(id),n=by.get(id),extra=width-p.w,header=p.header;
      if(extra<=0)return;
      for(const child of children(id))positions.get(child).x+=docks.some(d=>d.node===child&&d.kind==='side')||by.get(child)?.invocation_binding?extra:extra/2;
      p.w=width;n.paper.w=width;n.paper.lines=P.wrap(n.paper.title,width-28,n.paper.font);
      const complex=n.paper.read_binding_rows||n.paper.call_boundary||n.local_pipeline;
      n.paper.captions=complex?n.paper.captions.flatMap(s=>P.wrap(s,width-28,13)):
        n.paper.caption?P.wrap(n.paper.caption,width-28,13):[];
      Object.assign(p,{lines:n.paper.lines,captions:n.paper.captions,header:22+n.paper.lines.length*20+n.paper.captions.length*16+12});
      for(const child of children(id))positions.get(child).y+=p.header-header;
      p.h+=p.header-header;n.paper.h=p.h;
      const record=records.find(r=>r.node===id);if(record)Object.assign(record.after,{w:p.w,h:p.h});
    }
    function packPath(id){
      if(state.paperArchitecturePathRows===false||graph.edges.length>128||Object.keys(state.offsets||{}).length)return;
      const p=positions.get(id),n=by.get(id),record=records.find(r=>r.node===id),kids=children(id);
      if(!record||n.condition||n.mutable||n.identity_display||n.observed_calls||n.runtime_evidence?.length||n.evidence_status==='runtime-only'||
        kids.length<2||kids.length>6||record.rows.length!==kids.length||record.rows.some(r=>r.length!==1)||
        kids.some(id=>{const n=by.get(id);return n.kind!=='compute'||n.condition||n.mutable||n.identity_display||n.observed_calls||
          n.runtime_evidence?.length||n.evidence_status==='runtime-only'||positions.get(id).expanded;})||
        kids.some(id=>docks.some(d=>d.node===id)||by.get(id)?.invocation_binding))return;
      const ordered=record.rows.map(r=>r[0]),inside=new Set(kids),links=new Set();
      for(const e of graph.edges){
        if(!inside.has(e.source)&&!inside.has(e.target))continue;
        if(!ordinary(e)||e.layout_after||old.context.feedback?.has(e.id)||e.context_lane||e.design_route&&e.design_route.kind!=='bypass')return;
        if(inside.has(e.source)&&inside.has(e.target))links.add(e.source+'\n'+e.target);
      }
      // A genuine single serial path, not a topological ordering of branches.
      if(links.size!==kids.length-1||ordered.slice(1).some((id,i)=>!links.has(ordered[i]+'\n'+id)))return;
      const resized=ordered.map(id=>{const n=by.get(id),p=positions.get(id);
        if(p.symbol||n.paper.read_binding_rows||n.paper.call_boundary||n.local_pipeline)return {id,p:{...p},paper:{...n.paper}};
        const w=Math.min(p.w,Math.max(154,Math.ceil(P.width(n.paper.title,n.paper.font)+28),
          ...n.paper.captions.map(s=>Math.ceil(P.width(s,13)+28))));
        const lines=P.wrap(n.paper.title,w-28,n.paper.font),captions=n.paper.captions.flatMap(s=>P.wrap(s,w-28,13));
        const h=Math.max(54,22+lines.length*20+captions.length*16);
        return {id,p:{...p,w,h,lines,captions},paper:{...n.paper,w,h,lines,captions}};
      });
      const planned=new Map(resized.map(r=>[r.id,r.p]));
      const pad=18,gap=24,gutter=p.design_gutter||0,available=p.w-2*pad-gutter,rows=[];
      for(const id of ordered){const last=rows.at(-1),w=planned.get(id).w;
        if(w>available)return;
        if(!last||last.width+gap+w>available||ordered.length>3&&last.ids.length>=Math.ceil(ordered.length/2))rows.push({ids:[id],width:w});
        else{last.ids.push(id);last.width+=gap+w;}
      }
      // Avoid a long return lead from a full row to one centered final card.
      // Keep source order and width capacity while balancing the last turn.
      if(rows.length>1&&rows.at(-1).ids.length===1&&rows.at(-2).ids.length>2){
        const last=rows.at(-1),previous=rows.at(-2),id=previous.ids.at(-1),width=planned.get(id).w;
        if(last.width+gap+width<=available){previous.ids.pop();previous.width-=gap+width;last.ids.unshift(id);last.width+=gap+width;}
      }
      if(rows.length>=ordered.length)return;
      const before={w:p.w,h:p.h},rowGap=24;
      const height=p.header+rows.reduce((sum,r)=>sum+Math.max(...r.ids.map(id=>planned.get(id).h)),0)+(rows.length-1)*rowGap+pad;
      if(height>=p.h)return;
      const cards=resized.map(r=>({node:r.id,before:{w:positions.get(r.id).w,h:positions.get(r.id).h},after:{w:r.p.w,h:r.p.h}}));
      for(const r of resized){Object.assign(positions.get(r.id),r.p);Object.assign(by.get(r.id).paper,r.paper);}
      let y=p.header;
      for(let i=0;i<rows.length;i++){
        const row=rows[i],height=Math.max(...row.ids.map(id=>positions.get(id).h));
        let x=gutter+pad+(available-row.width)/2;
        const reverse=!!(i%2)!==(state.paperArchitecturePathRows==='right');
        for(const id of reverse?row.ids.slice().reverse():row.ids){const c=positions.get(id);c.x=x;c.y=y+(height-c.h)/2;x+=c.w+gap;}
        row.y=y;row.height=height;y+=height+rowGap;
      }
      p.h=height;n.paper.h=height;record.after.h=height;
      pathRows.push({node:id,ordered,rows,cards,start:state.paperArchitecturePathRows==='right'?'right':'left',before,after:{w:p.w,h:p.h},
        scope:'The same short visible serial computation path uses measured rows within its existing frame width. Arrows preserve each dependency; alternating physical direction does not change source order, ownership, calls, bindings or semantic claims.'});
    }
    function measure(id){
      const n=by.get(id),original=old.get(id),kids=children(id);
      const p={...original,x:0,y:0};positions.set(id,p);
      const sourceKind=n.semantic_type==='source-function'?['Function']:n.semantic_type==='source-module'?['Module','Source module']:[];
      if(n.kind==='composite'&&original.expanded&&kids.length&&sourceKind.includes(n.paper.caption)&&!n.paper.unknown_count&&!n.condition&&!n.mutable&&
        !n.identity_display&&!n.observed_calls&&!n.role_annotations?.length){
        const note={schema:'source-kind-note/1',node:id,semantic_type:n.semantic_type,caption:n.paper.caption,
          scope:'Only the generic source-kind caption of an expanded frame is moved to its title and inspector. Algorithm, identity, configuration and boundary evidence remain printed.'};
        n.paper.source_kind_note=note;p.source_kind_note=note;sourceKindNotes.push(note);n.paper.caption='';n.paper.captions=[];
      }
      const overviewWidth=!original.expanded&&(n.kind==='composite'||n.framework_type)?metrics.overview_module_em*n.paper.font:0;
      const w=original.symbol?original.w:n.kind==='interface'?Math.max(154,original.w):n.role_path_stage?metrics.role_path_width:
        Math.max(overviewWidth,metrics.card_min_width,Math.min(metrics.card_max_width,Math.max(original.w,Math.ceil(P.width(n.paper.title,n.paper.font)+28))));
      const complex=n.paper.read_binding_rows||n.paper.call_boundary||n.local_pipeline;
      const captions=complex?n.paper.captions.flatMap(s=>P.wrap(s,w-28,13)):n.paper.caption?P.wrap(n.paper.caption,w-28,13):[];
      Object.assign(n.paper,{lines:P.wrap(n.paper.title,w-28,n.paper.font),captions,w});
      Object.assign(p,{lines:n.paper.lines,caption:n.paper.caption,captions,font:n.paper.font});
      const textHeight=22+n.paper.lines.length*20+captions.length*16;
      if(!original.expanded||!kids.length){p.w=w;p.h=original.symbol?original.h:Math.max(n.kind==='interface'?44:54,textHeight);n.paper.h=p.h;return p;}
      for(const child of kids)measure(child);
      const side=kids.filter(child=>docks.some(d=>d.node===child&&d.kind==='side')||by.get(child)?.invocation_binding);
      const core=kids.filter(c=>!side.includes(c)),coreSet=new Set(core);
      const branch=id=>{let at=id;while(at&&!coreSet.has(at))at=idx.nodes.get(at)?.parent;return at;};
      const adj=new Map(core.map(c=>[c,new Set()]));
      for(const e of graph.edges){
        if(e.design_route?.kind==='iteration-feedback'||old.context.feedback?.has(e.id))continue;
        const a=branch(e.source),b=branch(e.target);if(a&&b&&a!==b)adj.get(a).add(b);
      }
      // Rebuild sibling dependency ranks at this frontier. Old y coordinates
      // may belong to containers replaced by certified stages and cannot
      // prove that two computations can share a row.
      const groups=L.components(core,adj),unit=new Map();groups.forEach((g,i)=>g.forEach(c=>unit.set(c,i)));
      const links=groups.map(()=>new Set()),indeg=groups.map(()=>0),rank=groups.map(()=>0);
      for(const [a,bs]of adj)for(const b of bs){const x=unit.get(a),y=unit.get(b);if(x!==y&&!links[x].has(y)){links[x].add(y);indeg[y]++;}}
      const todo=groups.map((_,i)=>i).filter(i=>!indeg[i]);
      for(let k=0;k<todo.length;k++){const i=todo[k];for(const j of links[i]){rank[j]=Math.max(rank[j],rank[i]+1);if(!--indeg[j])todo.push(j);}}
      const rows=[];
      const declaration=id=>{const n=by.get(id),anchor=source.nodes.get(n.role_path_stage?.anchor)||n;return anchor.source?.[0]||{};};
      for(const child of core.sort((a,b)=>{const x=declaration(a),y=declaration(b);return String(x.file||'').localeCompare(String(y.file||''))||
        (x.line??Infinity)-(y.line??Infinity)||(x.column??0)-(y.column??0)||old.get(a).x-old.get(b).x||old.get(a).y-old.get(b).y;})){
        const y=rank[unit.get(child)];let row=rows.find(r=>r.y===y);if(!row){row={y,ids:[]};rows.push(row);}row.ids.push(child);
      }
      rows.sort((a,b)=>a.y-b.y);
      if(columns){
        // Only singleton rows on a strictly ordered data path share width.
        // Parallel modules, cyclic siblings and source helper functions keep
        // their own widths. No child is folded, moved to another owner or
        // substituted by another call to obtain the alignment.
        const candidates=rows.filter(r=>r.ids.length===1).map(r=>r.ids[0]).filter(id=>{
          const n=by.get(id);return !n.condition&&!n.mutable&&!['opaque','control','state','buffer'].includes(n.kind)&&
            positions.get(id).expanded&&children(id).length&&groups[unit.get(id)].length===1&&
            (n.semantic_contracts?.length||n.contract_stage||n.semantic_type==='source-module'||
              n.kind==='composite'&&source.nodes.get(id)?.source_class);
        });
        const flow=new Map(core.map(id=>[id,new Set()]));
        for(const e of graph.edges){const a=branch(e.source),b=branch(e.target);
          if(a&&b&&a!==b&&ordinary(e)&&!e.layout_after&&!old.context.feedback?.has(e.id)&&(!e.design_route||e.design_route.kind==='bypass'))flow.get(a).add(b);
        }
        const reaches=(from,to)=>{const todo=[from],seen=new Set();for(let i=0;i<todo.length;i++){
          const at=todo[i];if(at===to)return true;if(seen.has(at))continue;seen.add(at);todo.push(...flow.get(at)||[]);
        }return false;};
        if(candidates.length>1&&candidates.every((a,i)=>candidates.slice(i+1).every(b=>reaches(a,b)!==reaches(b,a)))){
          const width=Math.max(...candidates.map(id=>positions.get(id).w));
          const changed=candidates.filter(id=>positions.get(id).w<width).map(id=>({node:id,before:{w:positions.get(id).w,h:positions.get(id).h}}));
          for(const r of changed){widen(r.node,width);r.after={w:positions.get(r.node).w,h:positions.get(r.node).h};}
          for(const id of candidates)packPath(id);
          for(const r of changed)r.after={w:positions.get(r.node).w,h:positions.get(r.node).h};
          if(changed.length)moduleColumns.push({owner:id,width,members:candidates,changed,
            scope:'Expanded source and certified module frames on one strictly ordered visible data path share measured width. Every computation, call, condition, source boundary, parameter identity and exact binding is retained. Equal width asserts no semantic equivalence.'});
        }
      }
      const under=(child,scope)=>{let at=child;while(at){if(at===scope)return true;at=idx.nodes.get(at)?.parent;}return false;};
      const streams=core.filter(child=>old.get(child).expanded&&graph.edges.some(e=>under(e.target,child)&&
        by.get(e.source)?.kind==='interface'&&by.get(e.source)?.role==='input'&&!e.condition&&
        graph.edges.filter(v=>v.source===e.source).length===1&&!graph.edges.some(v=>v.target===e.source)&&
        !by.get(e.source)?.invocation_binding&&(()=>{let at=source.nodes.get(e.source)?.parent;while(at){if(at===child)return false;at=source.nodes.get(at)?.parent;}return true;})()));
      if(streams.length>1){
        // Different proof captions may need different heading heights. Give
        // aligned input regions the same heading band before stretching the
        // body; otherwise shorter headings move a core above its peer.
        const header=Math.max(...streams.map(c=>positions.get(c).header));
        for(const child of streams){
          const p=positions.get(child),extra=header-p.header;if(extra<=0)continue;
          for(const id of children(child))positions.get(id).y+=extra;
          p.header=header;p.h+=extra;
          const record=records.find(r=>r.node===child);if(record)record.after.h=p.h;
          streamHeadings.push({owner:id,stream:child,extra_height:extra,header,
            scope:'A shared measured heading band preserves all proof captions and keeps entry and core alignment independent of caption length.'});
        }
        const first=Math.min(...streams.map(c=>rank[unit.get(c)]));
        for(const row of rows)row.ids=row.ids.filter(c=>!streams.includes(c));
        rows.push({y:first+.1,ids:streams.slice().sort((a,b)=>old.get(a).x-old.get(b).x)});
        rows.splice(0,rows.length,...rows.filter(r=>r.ids.length).sort((a,b)=>a.y-b.y));
        // Keep independent entry chains on their shared entry baseline while
        // aligning their exit-side expanded cores. Extra height belongs to
        // the gap before the core, not above a shorter enclosing stream.
        // This uses measured dependency rows, never module names or roles.
        const height=Math.max(...streams.map(c=>positions.get(c).h));
        for(const child of streams){
          const p=positions.get(child),extra=height-p.h;
          if(extra<=0)continue;
          const record=records.find(r=>r.node===child);
          if(!record)continue;
          const expandedRows=record.rows.map((ids,i)=>({i,ids:ids.filter(id=>positions.get(id)?.expanded)})).filter(r=>r.ids.length);
          const last=expandedRows.at(-1);
          if(!last||last.i===0||last.ids.length!==1)continue;
          const landmark=last.ids[0],members=record.rows.flat(),memberSet=new Set(members);
          if(members.some(id=>{const n=by.get(id);return n.condition||n.mutable||['opaque','control'].includes(n.kind);} ))continue;
          const branchOf=id=>{let at=id;while(at&&!memberSet.has(at))at=idx.nodes.get(at)?.parent;return at;};
          const links=new Map(members.map(id=>[id,new Set()]));
          let guarded=false;
          for(const e of graph.edges){const a=branchOf(e.source),b=branchOf(e.target);if(!a||!b||a===b)continue;
            if(!ordinary(e)||(e.design_route&&e.design_route.kind!=='bypass')||old.context.feedback?.has(e.id)){guarded=true;break;}links.get(a).add(b);
          }
          if(guarded)continue;
          const reaches=(from,to)=>{const todo=[from],seen=new Set();for(let i=0;i<todo.length;i++){const at=todo[i];if(at===to)return true;if(seen.has(at))continue;seen.add(at);todo.push(...links.get(at)||[]);}return false;};
          // Require a strictly ordered corridor at this sibling frontier.
          // Parallel branches, cycles and disconnected islands keep their
          // geometry. A certified forward bypass is still an ordinary use.
          if(members.some((a,i)=>members.slice(i+1).some(b=>reaches(a,b)===reaches(b,a))))continue;
          if(state.paperArchitectureStreams==='compact'&&!Object.keys(state.offsets||{}).length){
            streamCompactions.push({owner:id,stream:child,compact_height:p.h,aligned_height:height,removed_slack:extra,
              scope:'Each independently entered region keeps its measured local height and exit-side alignment. Entry cards, source scope, computations and all cross-region dependencies remain present; alignment asserts no scheduling.'});
            continue;
          }
          const boundary=Math.min(...record.rows[last.i].map(id=>positions.get(id).y));
          const shifted=children(child).filter(id=>positions.get(id).y>=boundary);
          for(const id of shifted)positions.get(id).y+=extra;
          p.h=height;record.after.h=height;
          streamAlignments.push({owner:id,stream:child,landmark,extra_height:extra,shifted,
            scope:'Equal measured stream height; the dependency corridor receives slack before its exit-side expanded core. Entry identity, source ownership and every edge remain unchanged.'});
        }
      }
      const gutter=original.design_gutter||0,pad=18,gap=metrics.sequence_gap;
      p.w=Math.max(w,...rows.map(r=>r.ids.reduce((sum,c)=>sum+positions.get(c).w,0)+Math.max(0,r.ids.length-1)*metrics.sibling_gap+pad*2+gutter));
      const bodyWidth=p.w;
      const sideInline=side.length&&side.every(child=>{
        const targets=graph.edges.filter(e=>e.source===child).map(e=>branch(e.target)).filter(Boolean);
        return targets.length&&targets.every(target=>{const row=rows.find(r=>r.ids.includes(target));
          return row?.ids.length===1&&(bodyWidth-gutter-pad*2-positions.get(target).w)/2>=positions.get(child).w+32;});
      });
      if(side.length&&!sideInline)p.w+=Math.max(...side.map(c=>positions.get(c).w))+32;
      n.paper.lines=P.wrap(n.paper.title,p.w-28,n.paper.font);
      n.paper.captions=complex?n.paper.captions.flatMap(s=>P.wrap(s,p.w-28,13)):
        n.paper.caption?P.wrap(n.paper.caption,p.w-28,13):[];
      Object.assign(p,{lines:n.paper.lines,captions:n.paper.captions});
      p.header=22+n.paper.lines.length*20+n.paper.captions.length*16+12;
      let y=p.header;
      for(const row of rows){
        const width=row.ids.reduce((sum,c)=>sum+positions.get(c).w,0)+(row.ids.length-1)*metrics.sibling_gap;
        let x=gutter+pad+(bodyWidth-gutter-pad*2-width)/2;
        const rowHeight=Math.max(...row.ids.map(c=>positions.get(c).h));
        for(const child of row.ids){const c=positions.get(child),exitAligned=state.paperArchitectureStreams==='compact'&&
          !Object.keys(state.offsets||{}).length&&streamCompactions.some(r=>r.owner===id)&&row.ids.every(id=>streams.includes(id));
          Object.assign(c,{x,y:y+(exitAligned?rowHeight-c.h:0)});x+=c.w+metrics.sibling_gap;}
        y+=Math.max(...row.ids.map(c=>positions.get(c).h))+gap;
      }
      p.h=y-gap+pad;
      // A single downstream card follows the unique sibling region that
      // actually supplies it. This does not create a new execution relation.
      const branchOf=target=>{let at=target;while(at&&idx.nodes.get(at)?.parent!==id)at=idx.nodes.get(at)?.parent;return at;};
      for(const row of rows){
        if(row.ids.length!==1)continue;
        const child=row.ids[0],c=positions.get(child);
        if(c.expanded||by.get(child)?.condition||by.get(child)?.mutable)continue;
        const incoming=graph.edges.filter(e=>under(e.target,child));
        if(!incoming.length||incoming.some(e=>!ordinary(e)))continue;
        const origins=[...new Set(incoming.map(e=>branchOf(e.source)).filter(Boolean))];
        if(origins.length!==1||origins[0]===child)continue;
        const from=positions.get(origins[0]);if(!from||from.y>=c.y)continue;
        c.x=Math.max(gutter+pad,Math.min(bodyWidth-pad-c.w,from.x+(from.w-c.w)/2));
        followers.push({node:child,source_scope:origins[0],edges:incoming.map(e=>e.id),
          scope:'A downstream drawing card follows its unique actual source region; canonical relations remain unchanged.'});
      }
      let sideY=p.header;for(const child of side){const c=positions.get(child);
        const consumers=graph.edges.filter(e=>e.source===child).map(e=>positions.get(branchOf(e.target))).filter(Boolean);
        const preferred=consumers.length?Math.min(...consumers.map(p=>p.y)):p.header;
        const placed=Math.max(sideY,preferred);Object.assign(c,{x:sideInline?bodyWidth-pad-c.w:bodyWidth+8,y:placed});sideY=placed+c.h+24;}
      p.h=Math.max(p.h,sideY+pad);
      records.push({node:id,children:kids,rows:rows.map(r=>r.ids),before:{w:original.w,h:original.h},after:{w:p.w,h:p.h},
        scope:'Measured sibling rows and wider cards; dependencies and source ownership unchanged. Row alignment does not assert parallel execution.'});
      return p;
    }
    const roots=nodes.filter(n=>!by.has(idx.nodes.get(n.id)?.parent)).map(n=>n.id);
    let x=32;for(const id of roots){const p=measure(id);p.x=x;p.y=30;x+=p.w+metrics.sibling_gap;}
    // Reverse body rows only. Headings remain above their own body and text
    // is never reflected. The router then recomputes actual upward paths.
    if(state.paperDirection==='up')for(const id of nodes.map(n=>n.id)){
      const p=positions.get(id);if(!p.expanded)continue;
      for(const child of children(id)){const c=positions.get(child);c.y=p.header+p.h-18-c.y-c.h;}
    }
    function absolute(id,dx,dy){const p=positions.get(id),off=state.offsets?.[id]||{};p.x+=dx+(Number(off.x)||0);p.y+=dy+(Number(off.y)||0);for(const child of children(id))absolute(child,p.x,p.y);}
    for(const id of roots)absolute(id,0,0);
    positions.context={...old.context,idx,edges:graph.edges,routeCache:new Map(),reserved:[],
      compoundAlignments:[],contextLanes:[],branchColumns:[],rankClearances:[],inputDocks:[],fixedInputs:[],sourceForkWidths:[],
      crossScopePorts:[],coincidentPorts:[],localBypassScopes:[],entryBandRouting:false};
    const facing=[];
    for(const e of graph.edges){
      if(!ordinary(e)||e.design_route||e.context_lane||old.context.feedback?.has(e.id))continue;
      const a=positions.get(e.source),b=positions.get(e.target),sp=parents(e.source),tp=parents(e.target);
      const common=sp.find(id=>tp.includes(id));
      const branch=(path)=>path[path.indexOf(common)-1];
      const left=positions.get(branch(sp)),right=positions.get(branch(tp));
      const dock=docks.find(d=>d.node===e.source&&d.kind==='side')||by.get(e.source)?.invocation_binding;
      const separate=left&&right&&left!==right&&left.expanded&&right.expanded&&
        (left.x+left.w<=right.x||right.x+right.w<=left.x);
      const externalInput=by.get(e.source)?.kind==='interface'&&by.get(e.source)?.role==='input'&&tp.includes(idx.nodes.get(e.source)?.parent);
      if(!dock&&!separate&&!externalInput)continue;
      // A primary one-use entry remains on its local vertical main chain.
      if(externalInput&&!dock&&graph.edges.filter(x=>x.source===e.source).length===1)continue;
      const sourceSide=a.x+a.w/2<=b.x+b.w/2?'right':'left',targetSide=sourceSide==='right'?'left':'right';
      facing.push({edge:e.id,source_side:sourceSide,target_side:targetSide,
        scope:'Existing cross-region or side-input binding faces its consumer. Canonical source, result slot, target and operand remain distinct.'});
    }
    positions.context.crossScopePorts=facing;
    const boxes=[...positions.values()],left=Math.min(...boxes.map(p=>p.x))-28,top=Math.min(...boxes.map(p=>p.y))-28;
    const bounds={x:left,y:top,w:Math.max(...boxes.map(p=>p.x+p.w))+28-left,h:Math.max(...boxes.map(p=>p.y+p.h))+28-top};
    const result={...graph,nodes,idx,positions,bounds,publication:{...graph.publication,composition:{schema:'architecture-composition/1',round:10,direction:state.paperDirection==='up'?'up':'down',metrics,records,input_docks:docks,facing,followers,stream_alignments:streamAlignments,stream_compactions:streamCompactions,stream_headings:streamHeadings,source_kind_notes:sourceKindNotes,module_columns:moduleColumns,path_rows:pathRows}}};
    return result;
  }
  function frontier(state,action){
    const copy=E.clone(state);
    if(action==='return'&&copy.paperFrontierReturn)return E.clone(copy.paperFrontierReturn);
    const previous=copy.paperFrontierReturn;
    delete copy.paperFrontierReturn;
    for(const key of ['paperFocus','paperRelation','paperRepresentative','paperRepresentativeGroup','paperRoleDetails','paperRolePaths',
      'paperFrontierRecipe','paperExpressionDetails','paperRolePathStageOwners','paperDiagramPlan','paperDiagramReturn','paperCanonical'])delete copy[key];
    Object.assign(copy,{view:'publication',paperMedium:'canvas',paperComposition:'architecture',paperDirection:state.paperDirection||'up',
      paperAuto:true,paperAdaptive:false,paperCompact:true,open:[],offsets:{},paperGranularity:'stages'});
    if(action==='detail'){
      const back=previous||(state.paperGranularity==='stages'?state:copy);
      copy.paperFrontierReturn=E.clone(back);delete copy.paperFrontierReturn.paperFrontierReturn;
      Object.assign(copy,{paperGranularity:'roles',paperRolePathStages:true,paperRoleSourceFrames:true});
    }
    return copy;
  }
  function certifiedDetails(ir,state,options={}){
    const project=(ir,state)=>E.project(ir,state,null,options);
    const defaults={paperSampleFrame:true,paperReadBindingRows:true,paperSourceHeadings:true};
    const first=project(ir,{...defaults,...state});
    const requests=first.nodes.filter(n=>n.kind==='composite'&&n.semantic_contracts?.length&&!first.positions.get(n.id).expanded&&
      !n.condition&&!n.mutable&&n.evidence_status!=='runtime-only'&&!n.runtime_evidence?.length).map(n=>n.id);
    const RF=root.SemanticRoleFrontier||(typeof require==='function'?require('./role-frontier.js'):null);
    const paths=[],deferred=[];
    for(const node of requests)for(const c of first.architecture.semantic_contracts||[]){
      if(c.node!==node)continue;
      if(c.members?.some(id=>{const n=first.idx.nodes.get(id);return n&&(n.condition||n.mutable||['opaque','control'].includes(n.kind)||n.evidence_status==='runtime-only'||n.runtime_evidence?.length);} )){
        deferred.push({node,certificate:c.id,reason:'Nested control/effect/unknown scope remains a separately selectable local detail.'});continue;
      }
      for(const ref of RF.references(c.roles,first.idx.nodes)){
        const target=first.idx.nodes.get(ref.node);if(target?.kind!=='compute')continue;
        let at=target,safe=true;
        while(at&&at.id!==node){if(at.condition||at.mutable||['opaque','control'].includes(at.kind)||
          at.evidence_status==='runtime-only'||at.runtime_evidence?.length){safe=false;break;}at=first.idx.nodes.get(at.parent);}
        if(safe&&at?.id===node)paths.push({node,certificate:c.id,role:ref.keys});
      }
    }
    const selected={...state,paperRolePaths:[...(state.paperRolePaths||[]),...paths]};
    const second=paths.length?project(ir,{...defaults,...selected}):first;
    const stages=second.nodes.filter(n=>n.contract_stage&&!second.positions.get(n.id).expanded).map(n=>n.id);
    return {...selected,paperAuto:false,open:[...new Set([...second.publication.open,...stages])],
      paperFrontierRecipe:{schema:'certified-detail-frontier/1',nested_candidates:requests,role_paths:paths,nested_deferred:deferred,stage_requests:stages,
        scope:'Safe compute roles of one additional visible certificate layer and the computations of certified local stages. Unknown, conditional, mutable, repeated and independent boundaries retain their own expansion controls.'}};
  }
  const api={compose,frontier,certifiedDetails};root.SemanticCompositionLayout=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
