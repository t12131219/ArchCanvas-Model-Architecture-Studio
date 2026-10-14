/* Typed static source IR → the existing recursive editor. Never accepts SVG from a bundle. */
(function(root){
  'use strict';
  const E=root.SummaryEngine,C=root.SummaryConstraints;
  const clone=v=>JSON.parse(JSON.stringify(v));
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const stable=v=>JSON.stringify(v&&typeof v==='object'?Array.isArray(v)?v.map(x=>JSON.parse(stable(x))):Object.fromEntries(Object.keys(v).sort().map(k=>[k,JSON.parse(stable(v[k]))])):v);
  const fail=s=>{throw new Error('源码适配包：'+s);};
  function validate(bundle){
    if(bundle?.schema!=='summary-source-adapter/1'||bundle.ir?.schema!=='summary-source-ir/1')fail('不支持的格式');
    if(typeof bundle.id!=='string'||!/^source-[a-f0-9]{16}$/.test(bundle.id)||typeof bundle.title!=='string'||typeof bundle.entry!=='string'||!Array.isArray(bundle.diagnostics))fail('模型清单无效');
    const ir=bundle.ir;if(ir.modelExecuted!==false||ir.analysis!=='static-source-dependencies')fail('缺少静态分析声明');
    if(!Array.isArray(ir.nodes)||!ir.nodes.length||ir.nodes.length>480||!Array.isArray(ir.edges)||ir.edges.length>3600)fail('图规模超限');
    if(!Array.isArray(bundle.files)||bundle.files.length>80||!bundle.files.length)fail('源码清单不合法');
    if(stable(JSON.parse(bundle.canonicalIR))!==stable(ir))fail('IR 与校验内容不一致');
    const files=new Map();let size=0;
    for(const f of bundle.files){if(typeof f.path!=='string'||f.path.startsWith('/')||f.path.split(/[\\/]/).includes('..')||!f.path.endsWith('.py')||typeof f.text!=='string'||files.has(f.path))fail('源码路径无效');files.set(f.path,f);size+=new TextEncoder().encode(f.text).length;}
    if(size>2000000)fail('源码超过 2 MB');
    const evidence=bundle.evidence||{},by=new Map(ir.nodes.map(n=>[n.id,n]));
    if(by.size!==ir.nodes.length||ir.nodes.some(n=>typeof n.id!=='string'||typeof n.label!=='string'||typeof n.kind!=='string'))fail('节点身份无效');
    for(const [id,e]of Object.entries(evidence)){
      const file=files.get(e.file);if(!file||!Number.isInteger(e.line)||!Number.isInteger(e.endLine)||e.line<1||e.endLine<e.line||typeof e.expression!=='string'||!Number.isInteger(e.column)||!Number.isInteger(e.endColumn)||e.column<0||e.endColumn<0||e.endLine>file.text.split('\n').length)fail('证据位置无效 '+id);
      // Python AST columns are UTF-8 byte offsets, not JavaScript code units.
      const lines=file.text.split('\n'),encoder=new TextEncoder(),decoder=new TextDecoder();
      const slice=lines.slice(e.line-1,e.endLine).map((s,i)=>decoder.decode(encoder.encode(s).slice(i===0?e.column:0,i===e.endLine-e.line?e.endColumn:undefined))).join('\n');
      if(slice!==e.expression)fail('源码片段不匹配 '+id);
    }
    const checkEvidence=n=>{if(!Array.isArray(n.source_evidence)||!n.source_evidence.length||n.source_evidence.some(id=>!evidence[id]))fail('缺少源码证据 '+n.id);};
    for(const n of ir.nodes){checkEvidence(n);let p=n,seen=new Set();while(p.parent){if(!by.has(p.parent)||seen.has(p.parent))fail('包含关系无效');seen.add(p.parent);p=by.get(p.parent);if(seen.size>12)fail('包含深度超限');}}
    const ids=new Set();for(const e of ir.edges){checkEvidence(e);if(typeof e.id!=='string'||ids.has(e.id)||!by.has(e.source)||!by.has(e.target)||e.sourcePort!=='out'||typeof e.targetPort!=='string'||!['source_dependency','shape_dependency'].includes(e.role)||e.wire!==e.source+':out')fail('连接身份无效');ids.add(e.id);}
    if(ir.nodes.filter(n=>!n.parent).length!==1)fail('需要唯一模型根节点');
    return bundle;
  }
  async function verify(bundle){validate(bundle);const digest=async s=>Array.from(new Uint8Array(await root.crypto.subtle.digest('SHA-256',new TextEncoder().encode(s)))).map(b=>b.toString(16).padStart(2,'0')).join('');
    if(await digest(bundle.canonicalIR)!==bundle.irSha256)fail('IR SHA256 不匹配');
    for(const f of bundle.files)if(await digest(f.text)!==f.sha256)fail('源码 SHA256 不匹配 '+f.path);
    if(await digest(stable(bundle.files.map(({path,sha256})=>({path,sha256}))))!==bundle.sourceSha256)fail('源码清单 SHA256 不匹配');
    return bundle;
  }
  const colors={group:'#e7f5fe',input:'#e3f3ef',output:'#e3f3ef',opaque:'#fff0d9',normalization:'#fff6bd',activation:'#c9f1cd',linear:'#dfdff8',convolution:'#dbeafa',literal:'#f2f3f5'};
  const presentationVersion=2;
  // Conservative glyph advances keep the obstacle close to the actual text;
  // reserving a 180/300 px box for every short caption falsely blocks ports.
  const textWidth=(s,size)=>Math.ceil([...s].reduce((sum,c)=>sum+size*(/[^\u0000-\u00ff]/.test(c)?1:.64),0))+8;
  const titleOf=raw=>raw.label.length>29?raw.label.slice(0,28)+'…':raw.label;
  const detailOf=(raw,bundle)=>raw.kind==='opaque'?'待解析 · 保留源码依赖':raw.instance?'实例 '+raw.instance.split('.').slice(-2).join('.'):'源码 L'+bundle.evidence[raw.source_evidence[0]].line;
  function sources(bundle){validate(bundle);const ir=bundle.ir,by=new Map(ir.nodes.map(n=>[n.id,n])),children=id=>ir.nodes.filter(n=>n.parent===id);
    function graph(folded){
      const visible=ir.nodes.filter(n=>!folded||!n.parent||!by.get(n.parent)?.parent),shown=new Set(visible.map(n=>n.id));
      const representative=id=>{let n=by.get(id);while(n&&!shown.has(n.id))n=by.get(n.parent);return n?.id;};
      const projected=ir.edges.map(e=>({...e,source:representative(e.source),target:representative(e.target),raw:e})).filter(e=>e.source!==e.target);
      const nodes=[],positions=new Map(),sizing=new Map();
      function measure(raw){const kids=children(raw.id).filter(n=>shown.has(n.id));
        const incoming=ir.edges.filter(e=>e.target===raw.id),binary=['add','multiply'].includes(raw.kind)&&incoming.length===2;
        if(!kids.length){const group=children(raw.id).length>0,w=binary?32:group?270:230,h=binary?32:70;
          const captionW=Math.max(textWidth(titleOf(raw),12),textWidth(detailOf(raw,bundle).slice(0,30),10));
          const out={w,h,slotW:binary?Math.max(180,32+captionW+12):w,slotH:binary?44:h,kids:[],binary};sizing.set(raw.id,out);return out;}
        for(const n of kids)measure(n);const kidIds=new Set(kids.map(n=>n.id));
        const owner=id=>{let n=by.get(id);while(n&&!kidIds.has(n.id)&&n.id!==raw.id)n=by.get(n.parent);return kidIds.has(n?.id)?n.id:null;};
        const deps=new Map(kids.map(n=>[n.id,new Set()]));for(const e of projected){const s=owner(e.source),t=owner(e.target);if(s&&t&&s!==t)deps.get(t).add(s);}
        const rank=new Map(),visiting=new Set();function level(id){if(rank.has(id))return rank.get(id);if(visiting.has(id))fail('数据依赖有环；需要不透明循环边界');visiting.add(id);const value=Math.max(-1,...[...deps.get(id)].map(level))+1;visiting.delete(id);rank.set(id,value);return value;}
        kids.forEach(n=>level(n.id));const rows=[];for(const n of kids){const index=rank.get(n.id);(rows[index]||=([])).push(n);}
        // Keep a caption-aware but compact band.  The old 252 px binary slot
        // and 86 px row gap reserved space for a right-hand title even when
        // the title was the only object in that band.  A binary glyph is only
        // 32 px wide; its caption is an obstacle that is placed independently
        // below, so the layout should reserve a readable lane, not a full
        // rectangle around the caption on every side.
        const widths=rows.map(row=>row.reduce((v,n)=>v+sizing.get(n.id).slotW,0)+(row.length-1)*56),heights=rows.map(row=>Math.max(...row.map(n=>sizing.get(n.id).slotH)));
        const w=Math.max(330,...widths)+72,h=84+heights.reduce((a,b)=>a+b,0)+(rows.length-1)*54+34;
        const out={w,h,slotW:w,slotH:h,kids,rows,widths,heights};sizing.set(raw.id,out);return out;
      }
      const rootNode=visible.find(n=>!n.parent);measure(rootNode);
      function place(raw,x,y){const m=sizing.get(raw.id),expanded=!!m.kids.length;
        const n={id:raw.id,label:raw.label,parent:raw.parent,semantic:clone(raw),x,y,w:m.w,h:m.h,base:[x,y],expanded,routingObstacle:!expanded,fill:colors[raw.kind]||'#eef1fa',labelObstacles:[]};
        const title=titleOf(raw),detail=detailOf(raw,bundle);
        if(m.binary){const symbol=raw.kind==='add'?'+':'×',caption=title.slice(0,25),box={x:44,y:-6,w:180,h:44};
          n.glyphPresentation={schema:'source-glyph-presentation/1',kind:'binary-circle',operation:raw.kind,symbol,semantic_node:raw.id,silhouette:'circle',source_evidence:raw.source_evidence,authority:'Python AST binary expression or registered call; no runtime dtype claim'};
          n.labelObstacles=[box];n.html=`<circle cx="${x+16}" cy="${y+16}" r="16" fill="white" stroke="#263348" stroke-width="2"/><text x="${x+16}" y="${y+23}" text-anchor="middle" font-size="23" fill="#172336">${symbol}</text><text x="${x+44}" y="${y+9}" font-size="12" fill="#172336">${esc(caption)}</text><text x="${x+44}" y="${y+29}" font-size="10" fill="#526078">${esc(detail.slice(0,30))}</text>`;
        }else{n.html=`<rect x="${x}" y="${y}" width="${m.w}" height="${m.h}" rx="${expanded?16:9}" fill="${n.fill}" stroke="#263348" stroke-width="2"${raw.kind==='opaque'?' stroke-dasharray="6 4"':''}/><text x="${x+16}" y="${y+27}" font-size="15" font-weight="600" fill="#172336">${esc(title)}</text><text x="${x+16}" y="${y+49}" font-size="10" fill="#526078">${esc(detail.slice(0,38))}</text>`;
          if(expanded)n.labelObstacles=[{x:12,y:8,w:Math.min(m.w-24,Math.max(textWidth(title,15),textWidth(detail.slice(0,38),10))+4),h:48}];}
        positions.set(n.id,n);nodes.push(n);let yy=y+76;
        if(expanded)m.rows.forEach((row,i)=>{let xx=x+(m.w-m.widths[i])/2;for(const kid of row){const km=sizing.get(kid.id);place(kid,xx+(km.binary?(km.slotW-32)/2:0),yy);xx+=km.slotW+56;}yy+=m.heights[i]+54;});
      }
      place(rootNode,60,60);

      // Binary glyph captions and input ports are one presentation decision.
      // Choose the side from the actual projected neighbours instead of
      // baking the title on the right and the auxiliary input on the left.
      // This is deliberately model-independent: every statically analysed
      // add/multiply node gets the same deterministic geometry pass.
      const sideVectors={left:[-1,0],right:[1,0],top:[0,-1],bottom:[0,1]};
      const labelBox=(side,w)=>({
        right:{x:44,y:-6,w,h:44},
        left:{x:-w-12,y:-6,w,h:44},
        top:{x:16-w/2,y:-52,w,h:44},
        bottom:{x:16-w/2,y:40,w,h:44}
      }[side]);
      const absoluteBox=(n,b)=>({x:n.x+b.x,y:n.y+b.y,w:b.w,h:b.h});
      const overlapArea=(a,b)=>{const w=Math.max(0,Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x)),h=Math.max(0,Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y));return w*h;};
      const centre=n=>({x:n.x+n.w/2,y:n.y+n.h/2});
      function decorateBinaryGlyphs(){
        const byPosition=new Map(nodes.map(n=>[n.id,n]));
        const binaryNodes=nodes.filter(n=>n.glyphPresentation?.kind==='binary-circle');
        for(const n of binaryNodes){
          const raw=n.semantic,title=titleOf(raw),detail=detailOf(raw,bundle),captionW=Math.max(textWidth(title,12),textWidth(detail.slice(0,30),10));
          const incoming=projected.filter(e=>e.target===n.id).map(e=>byPosition.get(e.source)).filter(Boolean);
          const owner=n.parent&&byPosition.get(n.parent);
          const scores=[];
          for(const side of ['right','left','top','bottom']){
            const box=labelBox(side,captionW),abs=absoluteBox(n,box);let score=0;
            // Keep a title inside its owning frame. A side that cannot fit is
            // still considered as a last resort, but only after a large cost.
            if(owner){const pad=10;const out=Math.max(owner.x+pad-abs.x,0)+Math.max(owner.y+pad-abs.y,0)+Math.max(abs.x+abs.w-(owner.x+owner.w-pad),0)+Math.max(abs.y+abs.h-(owner.y+owner.h-pad),0);score+=out*120;}
            for(const other of nodes){if(other===n||other.junction)continue;if(!other.expanded)score+=overlapArea(abs,{x:other.x-8,y:other.y-8,w:other.w+16,h:other.h+16})*4;for(const lb of other.labelObstacles||[])score+=overlapArea(abs,absoluteBox(other,lb))*5;}
            const v=sideVectors[side],c=centre(n);
            const outgoing=projected.filter(e=>e.source===n.id).map(e=>byPosition.get(e.target)).filter(Boolean);
            for(const source of [...incoming,...outgoing]){const s=centre(source),dx=s.x-c.x,dy=s.y-c.y,projection=dx*v[0]+dy*v[1];
              // A caption on the same side as a producer blocks the natural
              // terminal corridor and forces a long detour around the glyph.
              if(projection>0)score+=Math.min(260,projection*.9+80);
              // Keep labels out of the dominant value-flow lane. For a
              // vertical predecessor/successor, a top/bottom caption would
              // sit directly on the wire and create the very detour this
              // pass is intended to remove; horizontal flow uses the dual
              // rule.
              if(Math.abs(dy)>=Math.abs(dx)&&['top','bottom'].includes(side))score+=110;
              if(Math.abs(dx)>Math.abs(dy)&&['left','right'].includes(side))score+=110;
              const transverse=Math.abs(dx*v[1]-dy*v[0]);score+=transverse*.025;
            }
            // Stable tie-break: retain the familiar right title when it is
            // geometrically equivalent, then prefer a horizontal side.
            score+=side==='right'?0:side==='left'?0.01:0.02;
            scores.push({side,score});
          }
          scores.sort((a,b)=>a.score-b.score||a.side.localeCompare(b.side));
          const labelSide=scores[0].side,box=labelBox(labelSide,captionW),symbol=raw.kind==='add'?'+':'×';
          n.glyphPresentation.labelSide=labelSide;
          n.glyphPresentation.labelBox=clone(box);
          n.labelObstacles=[clone(box)];
          const circleX=n.x+16,circleY=n.y+16;
          const text={right:{x:n.x+44,anchor:'start',y:n.y+9},left:{x:n.x-12,anchor:'end',y:n.y+9},top:{x:n.x+box.x,anchor:'start',y:n.y-35},bottom:{x:n.x+box.x,anchor:'start',y:n.y+55}}[labelSide];
          n.html=`<circle cx="${circleX}" cy="${circleY}" r="16" fill="white" stroke="#263348" stroke-width="2"/><text x="${circleX}" y="${circleY+7}" text-anchor="middle" font-size="23" fill="#172336">${symbol}</text><text x="${text.x}" y="${text.y}" text-anchor="${text.anchor}" font-size="12" fill="#172336">${esc(title)}</text><text x="${text.x}" y="${text.y+20}" text-anchor="${text.anchor}" font-size="10" fill="#526078">${esc(detail.slice(0,30))}</text>`;
        }
      }
      decorateBinaryGlyphs();

      // Allocate binary input sides jointly. The first source keeps the
      // closest canonical slot; a second source may use the nearest right or
      // left side when that removes an avoidable vertical loop. The assignment
      // is stable for equal costs and never changes the semantic targetPort.
      const binaryTargetPorts=new Map();
      for(const n of nodes.filter(v=>v.glyphPresentation?.kind==='binary-circle')){
        const incoming=projected.filter(e=>e.target===n.id).sort((a,b)=>String(a.targetPort).localeCompare(String(b.targetPort)));
        const choices=['top','right','bottom','left'].filter(side=>side!==n.glyphPresentation.labelSide);
        const combinations=[];
        const recurse=(i,used,current)=>{if(i===incoming.length){combinations.push(current.slice());return;}const source=positions.get(incoming[i].source),sc=centre(source),nc=centre(n);
          for(const side of choices){if(used.has(side)&&incoming.length<=choices.length)continue;const fraction=.5,p={x:side==='left'?n.x:side==='right'?n.x+n.w:n.x+n.w*fraction,y:side==='top'?n.y:side==='bottom'?n.y+n.h:n.y+n.h*fraction};const normal=sideVectors[side],dx=sc.x-nc.x,dy=sc.y-nc.y;let cost=Math.abs(sc.x-p.x)+Math.abs(sc.y-p.y)+(dx*normal[0]+dy*normal[1]>0?0:90);if(i===0&&side!=='top'&&choices.includes('top'))cost+=18;if(i>0&&side==='top')cost+=10;current.push({side,fraction,cost});used.add(side);recurse(i+1,used,current);used.delete(side);current.pop();}
        };
        recurse(0,new Set(),[]);combinations.sort((a,b)=>a.reduce((v,x)=>v+x.cost,0)-b.reduce((v,x)=>v+x.cost,0)||a.map(x=>x.side).join().localeCompare(b.map(x=>x.side).join()));
        const best=combinations[0]||incoming.map((e,i)=>({side:i?'right':'top',fraction:.5,cost:0}));incoming.forEach((e,i)=>binaryTargetPorts.set(e.id,{side:best[i].side,fraction:best[i].fraction}));
      }
      const port=(n,f)=>({x:n.x+(f.side==='left'?0:f.side==='right'?n.w:n.w*f.fraction),y:n.y+(f.side==='top'?0:f.side==='bottom'?n.h:n.h*f.fraction)});
      const edges=projected.map(e=>{const s=positions.get(e.source),t=positions.get(e.target),targets=projected.filter(v=>v.target===e.target),fields=[...new Set(targets.map(v=>v.targetPort))],index=fields.indexOf(e.targetPort),binary=t.glyphPresentation?.kind==='binary-circle';
        const fixedSource={side:'bottom',fraction:.5},fixedTarget=binary?(binaryTargetPorts.get(e.id)||{side:index===0?'top':'right',fraction:.5}):{side:'top',fraction:(index+1)/(fields.length+1)};
        const a=port(s,fixedSource),b=port(t,fixedTarget);
        const ancestors=id=>{const out=[];let n=positions.get(id);while(n?.parent){n=positions.get(n.parent);if(n?.expanded)out.push(n);}return out;};
        const sa=ancestors(s.id),ta=ancestors(t.id),exit=sa.filter(n=>!ta.some(v=>v.id===n.id)),enter=ta.filter(n=>!sa.some(v=>v.id===n.id));
        const low=Math.max(a.y+24,...exit.map(n=>n.y+n.h+24)),high=Math.min(b.y-24,...enter.map(n=>n.y-24)),lane=(low+high)/2;
        const ps=[a,{x:a.x,y:lane},{x:fixedTarget.side==='left'?b.x-24:b.x,y:lane},fixedTarget.side==='left'?{x:b.x-24,y:b.y}:b,b].filter((p,i,arr)=>!i||p.x!==arr[i-1].x||p.y!==arr[i-1].y);
        const binding={src:e.raw.source+':'+e.sourcePort,dst:e.raw.target+':'+e.targetPort,canonical_src:e.raw.source+':'+e.sourcePort,canonical_dst:e.raw.target+':'+e.targetPort,wire_identity:e.raw.wire,semantic_edges:[e.id],source_evidence:e.source_evidence,semantic_kind:e.role};
        const policy=(n,side)=>({mode:'perimeter',shape:n.glyphPresentation?'circle':'rectangle',spacing:12,gates:[],sharedStem:null,authority:'typed source dependency; display side is movable'});
        return {id:e.id,source:e.source,target:e.target,role:e.role,binding,fixedSource,fixedTarget,portPolicy:{source:policy(s),target:policy(t)},route:ps,waypoints:[],style:'orthogonal',width:2.2,arrow:'target',dashed:e.role==='shape_dependency',draft:false,needsRecursiveRouting:true};
      });
      const g={nodes,edges,canvas:[sizing.get(rootNode.id).w+180,Math.max(720,sizing.get(rootNode.id).h+180)],definitions:'',extras:'',attachments:[],junctionMarkers:[],routeLabels:[],sourceDraftOperations:[],caseId:bundle.id,viewKey:folded?'overview':'detailed',irSha256:bundle.irSha256,
        sourceAdapter:{version:1,presentationVersion,entry:bundle.entry,sourceSha256:bundle.sourceSha256,irSha256:bundle.irSha256},sourceProfile:{analysis:'static source dependencies',modelExecuted:false,entry:bundle.entry,opaqueRegions:bundle.diagnostics.length,tensorShapes:'未推断'},
        sourceFacts:['源码经 Python AST 静态解析，未导入或执行模型。','箭头表示可证明的源码值依赖；不代表已验证的张量形状或运行轨迹。','相同 instance 标识保留源码中的模块复用；未知调用和动态控制流使用虚线边框。',...bundle.diagnostics.slice(0,12).map(d=>d.message)]};
      C.initialize(g);
      g.semanticBaseline={schema:'imported-source-baseline/1',irSha256:g.irSha256,nodes:Object.fromEntries(nodes.map(n=>[n.id,{parent:n.parent,semantic:clone(n.semantic),visualBinding:null,...(n.glyphPresentation?{glyphPresentation:clone(n.glyphPresentation),glyphMarkupHash:hash(n.html),labelObstacles:clone(n.labelObstacles)}:{})}])),edges:Object.fromEntries(edges.map(e=>[e.id,{source:e.source,target:e.target,binding:clone(e.binding),fixedSource:clone(e.fixedSource),fixedTarget:clone(e.fixedTarget),portPolicy:clone(e.portPolicy)}])),attachments:{},routeLabels:{},junctionMarkers:[]};
      return g;
    }
    return {overview:graph(true),detailed:graph(false)};
  }
  function hash(s){let h=2166136261;for(let i=0;i<s.length;i++)h=Math.imul(h^s.charCodeAt(i),16777619)>>>0;return h.toString(16).padStart(8,'0');}
  const api={validate,verify,sources};root.SummarySourceAdapter=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
