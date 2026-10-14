(function() {
  'use strict';
  const $=id=>document.getElementById(id),NS='http://www.w3.org/2000/svg';
  const catalog=window.SummaryCatalog,R=window.EdgeRouterLabRouting,E=window.SummaryEngine,C=window.SummaryConstraints,svg=$('graph');
  const names={module_programmatic_guide:'模块 · 76 案例',model_zoo_programmatic_guide:'Model Zoo · 完整模型',timeseries_programmatic_guide:'时序模型',transformer_programmatic_guide:'Transformer 与残差',pytorch_transformer_original:'PyTorch 原始架构',arrow_semantic_audit:'箭头审查与展开视图',yworks_edge_router_lab:'Edge Router 实验'};
  let current=null,view=null,graph=null,original=null,tool='select',selectedNodes=new Set(),selectedEdges=new Set();
  let history=[],future=[],ghost=[],drag=null,connection=null,busy=false,dirty=false,loadToken=0,epoch=0;
  let camera={x:0,y:0,w:1100,h:720},metrics={routed:0,time:0},timer,sessions=new Map();
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const element=(tag,attrs={},text)=>{const n=document.createElementNS(NS,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n;};
  const key=()=>current.id+':'+view.key;
  function restoreSourceBaseline(){E.upgradePresentation(graph,original);}
  const stageScale=()=>$('stage').clientWidth/camera.w;
  const point=event=>{const p=svg.createSVGPoint();p.x=event.clientX;p.y=event.clientY;return p.matrixTransform(svg.getScreenCTM().inverse());};
  const node=id=>graph.nodes.find(n=>n.id===id);
  function toast(message){$('toast').textContent=message;$('toast').classList.add('visible');clearTimeout(timer);timer=setTimeout(()=>$('toast').classList.remove('visible'),4500);}
  function save(){history.push(E.clone(graph));if(history.length>30)history.shift();future=[];}
  function persist(){if(!graph||!current)return;sessions.set(key(),{graph:E.clone(graph),history:history.slice(),future:future.slice(),dirty});try{localStorage.setItem('summary-merge:'+key(),JSON.stringify({version:2,ir:original.irSha256||null,graph,dirty}));}catch(_){} }
  function options(){return {margin:+$('clearance').value,stub:28,bendCost:40,crossingCost:$('crossings').checked?180:0,overlapCost:$('crossings').checked?2:0,edgeSpacing:$('crossings').checked?12:0,preserve:$('keepBends').checked,sides:$('portSides').value,grid:$('gridEnabled').checked?24:0,style:$('routingStyle').value};}
  function label(n){return n.label||n.id;}
  function lab(){
    const nodes=[['A','Source','输入',75,166,132,66],['B','Transform','变换',380,80,138,66],['C','Merge','汇合',748,148,138,66],['D','Output','输出',900,335,132,76],['E','Archive','存储',755,557,138,66],['F','Residual','旁路',82,518,132,66],['G','Observer','观察',371,549,138,66],['O1','Obstacle','拖动我',475,271,142,160],['O2','Block','固定障碍',245,326,118,78]].map(([id,name,sub,x,y,w,h])=>({id,label:name,x,y,w,h,base:[x,y],parent:null,expanded:false,routingObstacle:true,semantic:{kind:'routing sandbox'},html:`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="9" fill="${id.startsWith('O')?'#e5eeec':'#0e9b9f'}" stroke="${id.startsWith('O')?'#c7d9d5':'#078b91'}"/><text x="${x+15}" y="${y+27}" fill="${id.startsWith('O')?'#64867f':'white'}" font-size="16">${name}</text><text x="${x+15}" y="${y+47}" fill="${id.startsWith('O')?'#7c9891':'#b7e5e3'}" font-size="10">${sub}</text>`}));
    const edges=[['A','B'],['B','C'],['C','D'],['A','C'],['A','D'],['F','G'],['G','D'],['G','E'],['D','E'],['A','F'],['B','G']].map(([source,target],i)=>({id:'e'+(i+1),source,target,arrow:'target',style:'orthogonal',route:[],waypoints:[],binding:{evidence:'independent routing sandbox'},draft:false}));
    const g={nodes,edges,canvas:[1100,720],caseId:'routing-lab',viewKey:'overview',definitions:'',extras:'',sourceFacts:['移动障碍或节点后 Apply，比较路径变化。','边样式与路由几何分别编辑，端点重接保留历史记录。'],sourceProfile:{},irSource:null,source:null};
    for(const e of edges){e.route=[E.endpoint(g,e,'source'),E.endpoint(g,e,'target')];}
    return E.routeBatch(g,edges.map(e=>e.id),{margin:14,stub:28,bendCost:40,crossingCost:180,overlapCost:2,edgeSpacing:12,sides:'any',style:'orthogonal'}).graph;
  }
  function renderCatalog(){
    const query=$('search').value.toLowerCase(),collection=$('collection').value,historyVisible=$('includeHistory').checked;
    const filtered=catalog.cases.filter(c=>(historyVisible||!c.historical)&&(collection==='all'||collection===c.collection)&&[c.title,c.origin].join(' ').toLowerCase().includes(query));
    $('catalogCount').textContent=`显示 ${filtered.length} 个案例 · ${catalog.counts.views} 个记录视图`;
    const list=$('caseList');list.replaceChildren();let previous='';
    for(const c of filtered){if(c.collection!==previous){const h=document.createElement('div');h.className='collection-label';h.textContent=names[c.collection]||c.collection;list.append(h);previous=c.collection;}
      const b=document.createElement('button');b.className='case-button'+(current?.id===c.id?' active':'');b.dataset.caseId=c.id;
      b.innerHTML=`<strong>${esc(c.title)}</strong><small>${c.historical?'历史 · ':''}${c.views.length} 个视图${c.views[0].nodes?' · '+c.views[0].nodes+' nodes':''}</small>`;
      b.onclick=()=>openCase(c,c.views[0]);list.append(b);
    }
  }
  function asset(descriptor,c){return new Promise((resolve,reject)=>{const id=c.id+':'+descriptor.key;if(window.SummaryCaseData?.[id])return resolve(window.SummaryCaseData[id]);const script=document.createElement('script');script.src='../'+descriptor.asset;script.onload=()=>resolve(window.SummaryCaseData[id]);script.onerror=()=>reject(new Error('无法读取 '+descriptor.asset));document.head.append(script);});}
  async function openCase(c,v){
    if(busy){toast('正在重新布线，完成后可切换示例。');return;}
    persist();const token=++loadToken;current=c;view=v;
    try{
      const data=v.builtin?lab():await asset(v,c);if(token!==loadToken)return;
      original=C.initialize(E.clone(data));let saved=sessions.get(key());
      if(!saved)try{const disk=JSON.parse(localStorage.getItem('summary-merge:'+key()));if(disk?.version===2&&disk.ir===(data.irSha256||null))saved={graph:disk.graph,history:[],future:[],dirty:disk.dirty};}catch(_){}
      graph=E.clone(saved?.graph||original);restoreSourceBaseline();C.initialize(graph);
      if(saved)for(const state of [...saved.history,...saved.future])E.upgradePresentation(state,original);
      if(saved&&!C.validateSource(graph).ok){
        const archiveKey='summary-merge:archived:'+key()+':'+Date.now();sessions.set(archiveKey,saved);
        try{localStorage.setItem(archiveKey,JSON.stringify(saved));}catch(error){throw new Error('旧草稿与更新后的原图不兼容，且无法归档；请先导出旧草稿。');}
        graph=E.clone(original);saved=null;toast('原图连接已更新；旧缓存草稿已归档，现显示最新原图。');
      }
      history=saved?.history||[];future=saved?.future||[];dirty=saved?.dirty||false;ghost=[];selectedNodes.clear();selectedEdges.clear();connection=null;drag=null;
      metrics={routed:0,time:0};
      if(saved&&C.validateSource(graph).ok){const repair=graph.edges.filter(e=>C.validate(graph,e,e.route).violations.some(v=>v.startsWith('border stroke clearance'))).map(e=>e.id);
        if(repair.length){history.push(E.clone(graph));future=[];const result=E.routeBatch(graph,repair,{margin:6,stub:28,bendCost:40,crossingCost:180,overlapCost:2,edgeSpacing:12,sides:'any',style:'orthogonal'});
          metrics.routed=result.routed;dirty=true;toast(result.failed?'部分旧路径需要调整空间；边框间距检查已标出。':'旧草稿中的边框重叠路径已修复，保留手动模块位置。');}
      }
      $('routingStyle').value='orthogonal';$('keepBends').checked=false;$('showPorts').checked=c.id==='routing-lab';$('clearance').value=c.id==='routing-lab'?14:6;$('clearanceValue').value=$('clearance').value+' px';
      $('modelTitle').textContent=c.title;$('modelCollection').textContent=names[c.collection]||c.collection;$('modelOrigin').textContent=(c.historical?'历史快照 / ':'')+c.origin;
      $('viewTabs').replaceChildren();for(const d of c.views){const b=document.createElement('button');b.textContent=d.label;b.className=d.key===v.key?'active':'';b.dataset.view=d.key;b.onclick=()=>openCase(c,d);$('viewTabs').append(b);}
      const docs=Object.entries(data.sourceDocs||{}).map(([name,url])=>[name==='source_map.md'?'源码映射':name==='source_evidence.json'?'源码证据':'案例说明',url]);
      $('sourceLinks').innerHTML=[['原始 SVG',data.source],['布局与接口',data.layoutSource],['语义 IR',data.irSource],...docs,['原始案例',c.sourceIndex]].filter(([,url])=>url&&!(c.id==='pytorch-original'&&url.endsWith('index.html'))).map(([name,url])=>`<a href="../${esc(url)}" target="_blank">${name} ↗</a>`).join('');
      $('sourceFacts').innerHTML=data.sourceFacts?.length?'<ul>'+data.sourceFacts.map(f=>'<li>'+esc(f)+'</li>').join('')+'</ul>':'<p>保留原始图元、层次和连接映射。视觉编辑可在本页撤销，源模型未执行。</p>';
      if(Object.keys(data.sourceProfile||{}).length)$('sourceFacts').innerHTML+='<pre>'+esc(JSON.stringify(data.sourceProfile,null,2))+'</pre>';
      const url=new URL(location.href);url.searchParams.set('case',c.id);url.searchParams.set('view',v.key);window.history.replaceState(null,'',url);
      renderCatalog();fit();render();persist();
    }catch(error){toast(error.message);$('modelTitle').textContent='示例加载失败';}
  }
  function cameraUpdate(){svg.setAttribute('viewBox',`${camera.x} ${camera.y} ${camera.w} ${camera.h}`);$('zoomLabel').textContent=Math.round(stageScale()*100)+'%';}
  function fit(widthOnly=false){if(!graph)return;const ratio=$('stage').clientWidth/$('stage').clientHeight,w=graph.canvas[0],h=graph.canvas[1];camera=widthOnly?{x:0,y:0,w,h:w/ratio}:w/h>ratio?{x:0,y:(h-w/ratio)/2,w,h:w/ratio}:{x:(w-h*ratio)/2,y:0,w:h*ratio,h};cameraUpdate();}
  function zoom(factor,at){const p=at||{x:camera.x+camera.w/2,y:camera.y+camera.h/2},newWidth=Math.min(graph.canvas[0]*8,Math.max(120,camera.w/factor)),f=newWidth/camera.w;camera={x:p.x-(p.x-camera.x)*f,y:p.y-(p.y-camera.y)*f,w:newWidth,h:camera.h*f};cameraUpdate();render();}
  function arrow(layer,tip,from,color,open){const d=E.arrow(tip,from,open);if(d)layer.append(element('path',{d,fill:open?'none':color,stroke:open?color:'none','stroke-width':open?1.7:0,class:'arrow-shape','pointer-events':'none'}));}
  function render(){if(!graph)return;restoreSourceBaseline();C.initialize(graph);const sourceCheck=C.validateSource(graph);
    svg.setAttribute('data-source-constraint-valid',String(sourceCheck.ok));svg.setAttribute('data-source-constraint-reason',sourceCheck.violations.join('; '));
    for(const name of ['frameLayer','obstacleLayer','ghostLayer','edgeLayer','nodeLayer','labelLayer','handleLayer'])$(name).replaceChildren();
    $('definitions').innerHTML=graph.definitions||'';$('annotationLayer').innerHTML=graph.extras||'';
    const scale=stageScale(),handle=Math.min(28,5/scale);
    for(const n of graph.nodes){if(n.junction)continue;const g=element('g',{'data-node-id':n.id,'data-parent':n.parent||'','data-expanded':String(!!n.expanded),'data-visual-binding':JSON.stringify(n.visualBinding||{}),'aria-label':`节点 ${n.id} ${label(n)}`,class:'scene-node'});
      const content=element('g',{transform:`translate(${n.x-n.base[0]} ${n.y-n.base[1]})`});content.innerHTML=n.html;g.append(content);
      const hit=element('rect',{x:n.x,y:n.y,width:n.w,height:n.h,rx:8,class:n.expanded?'frame-hit':'node-hit'});g.append(hit);
      if(selectedNodes.has(n.id))g.append(element('rect',{x:n.x-4,y:n.y-4,width:n.w+8,height:n.h+8,rx:9,fill:'none',stroke:'#d99160','stroke-width':2/scale,'stroke-dasharray':`${4/scale} ${3/scale}`,'pointer-events':'none','data-editor-only':'selection'}));
      g.addEventListener('pointerdown',ev=>nodeDown(ev,n));$(n.expanded?'frameLayer':'nodeLayer').append(g);
      if($('showObstacles').checked&&n.routingObstacle!==false){const b=R.expand(n,+$('clearance').value);$('obstacleLayer').append(element('rect',{x:b.x,y:b.y,width:b.w,height:b.h,fill:'none',stroke:'#c9925680','stroke-width':1/scale,'stroke-dasharray':`${4/scale} ${4/scale}`,'pointer-events':'none'}));}
      if($('showPorts').checked){const ports=current.id==='routing-lab'?['left','right','top','bottom'].map(side=>({fixed:{side,fraction:.5},p:R.port(n,side),field:side})):graph.edges.flatMap(e=>[['source','fixedSource'],['target','fixedTarget']].filter(([side])=>e[side]===n.id).map(([side,f])=>({fixed:window.SummaryPhysicalPorts.active(e,side)||{side:E.endpoint(graph,e,side).side,fraction:E.endpoint(graph,e,side).fraction},p:E.endpoint(graph,e,side),field:e.binding?.[side==='source'?'src':'dst']||'视觉草稿'})));const seen=new Set();for(const {p,fixed,field} of ports){const key=p.x+':'+p.y;if(seen.has(key))continue;seen.add(key);const c=element('circle',{cx:p.x,cy:p.y,r:handle*.65,fill:'#fff',stroke:'#3ca1a3','stroke-width':1/scale,class:'port-handle','data-port':n.id+':'+fixed.side});c.append(element('title',{},field));c.addEventListener('pointerdown',ev=>tool==='connect'?startConnection(ev,n,fixed):nodeDown(ev,n));$('handleLayer').append(c);}}
    }
    const labelPlacements=E.routeLabelPlacements(graph);
    for(const a of graph.routeLabels||[]){const offset=labelPlacements.get(a.id);if(!offset)continue;
      const g=element('g',{'data-route-label-id':a.id,'data-follow-edge':a.edge,'data-label-anchor':`${offset.point.x},${offset.point.y}`,
        transform:`translate(${offset.x} ${offset.y})`,class:'scene-attachment route-caption',style:'cursor:grab'});
      if(offset.leader){const b=offset.box,q=offset.point,tx=Math.max(b.x,Math.min(b.x+b.w,q.x)),ty=Math.max(b.y,Math.min(b.y+b.h,q.y));
        $('labelLayer').append(element('path',{d:`M ${q.x} ${q.y} L ${tx} ${ty}`,stroke:'#a6adb5','stroke-width':.8,'stroke-dasharray':'2 3',fill:'none','pointer-events':'none','data-label-leader':a.id}));}
      const [x,y,w,h]=a.bbox;g.append(element('rect',{x:x-2,y:y-1,width:w+4,height:h+2,rx:2,fill:'white','fill-opacity':.9}));
      const text=element('g');text.innerHTML=a.html;g.append(text);g.append(element('title',{},'拖动文字沿所属连线吸附；模型连接保持绑定。'));
      g.addEventListener('pointerdown',ev=>{if(busy||ev.button!==0)return;ev.stopPropagation();if(tool==='pan'){begin(ev,{kind:'pan',camera:{...camera}});return;}
        selectedNodes.clear();selectedEdges=new Set([a.edge]);
        const p=point(ev),center={x:offset.box.x+offset.box.w/2,y:offset.box.y+offset.box.h/2};
        begin(ev,{kind:'route-label',label:a,grab:{x:center.x-p.x,y:center.y-p.y}});render();});$('labelLayer').append(g);
    }
    for(const a of graph.attachments||[]){const owner=node(a.owner);if(!owner)continue;
      const offset=E.attachmentTransform(graph,a);
      const g=element('g',{'data-attachment-id':a.id,'data-follow-owner':a.owner,'data-follow-kind':a.kind,
        transform:`translate(${offset.x} ${offset.y})`,class:'scene-attachment'});
      g.innerHTML=a.html;g.addEventListener('pointerdown',ev=>nodeDown(ev,owner));$('labelLayer').append(g);
    }
    if($('showGhost').checked)for(const e of ghost)$('ghostLayer').append(element('path',{d:E.path(e.route,e.style),fill:'none',stroke:'#a7babb','stroke-width':1.5,'stroke-dasharray':'6 7',opacity:.6,'pointer-events':'none'}));
    for(const e of graph.edges){const ps=E.displayed(graph,e);if(ps.length<2)continue;const check=C.validate(graph,e,e.route),selected=selectedEdges.has(e.id),color=e.failed||!check.ok?'#d54c60':selected?'#d77944':'#263b4b',start=e.arrow==='both',end=e.arrow!=='none';
      const g=element('g',{'data-edge-id':e.id,'data-source':e.source,'data-target':e.target,'data-role':e.role||'tensor','data-draft':String(!!e.draft),'data-physical-source':JSON.stringify(E.endpoint(graph,e,'source')),'data-physical-target':JSON.stringify(E.endpoint(graph,e,'target')),'data-constraint-valid':String(check.ok&&!e.failed),'data-constraint-reason':e.reason||check.violations.join('; '),'data-semantic-binding':JSON.stringify(e.binding),'data-boundary-gates':JSON.stringify(e.contract?.gates||[]),'aria-label':`边 ${e.id} ${e.source} 到 ${e.target}`});
      g.append(element('path',{d:E.path(E.crop(ps,start,end),e.style,graph,e),fill:'none',stroke:color,'stroke-width':selected?2.8:e.width||2.2,'stroke-dasharray':e.dashed?'7 5':'none',class:'wire-path','stroke-linecap':'butt'}));
      if(end)arrow(g,ps.at(-1),ps.at(-2),color,e.arrow==='open');if(start)arrow(g,ps[0],ps[1],color,false);
      const hit=element('path',{d:E.path(ps,e.style,graph,e),class:'wire-hit','stroke-width':Math.min(45,12/scale),'data-edge-hit':e.id});hit.addEventListener('pointerdown',ev=>edgeDown(ev,e));g.append(hit);$('edgeLayer').append(g);
      if(selected){for(const [side,index] of [['source',0],['target',ps.length-1]]){const p=ps[index],c=element('circle',{cx:p.x,cy:p.y,r:handle*1.3,fill:'#fff4e6',stroke:'#d77944','stroke-width':1.5/scale,class:'endpoint-handle','data-endpoint':e.id+':'+side});c.addEventListener('pointerdown',ev=>begin(ev,{kind:'endpoint',edge:e,side}));$('handleLayer').append(c);$('handleLayer').append(element('text',{x:p.x,y:p.y+3/scale,'text-anchor':'middle','font-size':8/scale,fill:'#b86e36','pointer-events':'none'},side==='source'?'S':'T'));}
        e.waypoints.forEach((p,i)=>{const h=element('rect',{x:p.x-handle,y:p.y-handle,width:handle*2,height:handle*2,fill:'#fff',stroke:'#d77944','stroke-width':1.5/scale,class:'bend-handle','data-bend':e.id+':'+i});h.addEventListener('pointerdown',ev=>begin(ev,{kind:'bend',edge:e,index:i}));$('handleLayer').append(h);});}
    }
    for(const marker of graph.junctionMarkers||[]){const p=E.junctionPoint(graph,marker);if(!p)continue;
      $('edgeLayer').append(element('circle',{cx:p.x,cy:p.y,r:marker.radius||2.5,fill:marker.fill||'#263b4b',
        'data-junction-id':marker.id,'data-junction-owner':marker.owner,'data-junction-edges':JSON.stringify(marker.edges),
        'data-junction-wire':JSON.stringify(marker.wire),'pointer-events':'none'}));
    }
    const stats=R.stats(graph.edges);$('graphCount').textContent=`${graph.nodes.filter(n=>!n.junction).length} nodes / ${graph.edges.length} edges`;$('metricNodes').textContent=graph.nodes.filter(n=>!n.junction).length+' / '+graph.edges.length;$('metricLength').textContent=stats.length.toLocaleString();$('metricBends').textContent=stats.bends+' / '+stats.crossings;$('metricRouted').textContent=metrics.routed;$('metricTime').textContent=metrics.time;
    $('dirtyBadge').textContent=!sourceCheck.ok?'源码语义校验失败':busy?'正在布线…':dirty?'待 Apply · 已编辑':'布局已就绪';$('dirtyBadge').title=sourceCheck.violations.join('; ');$('dirtyBadge').classList.toggle('dirty',dirty||!sourceCheck.ok);$('undo').disabled=busy||!history.length;$('redo').disabled=busy||!future.length;$('applyLayout').disabled=busy||!sourceCheck.ok;
    renderInspector();
  }
  function renderInspector(){const box=$('selectionInfo');
    if(selectedEdges.size===1){const e=graph.edges.find(e=>selectedEdges.has(e.id));box.innerHTML=`<p class="eyebrow">SELECTED EDGE</p><h3>${esc(e.id)}</h3><div class="prop">源端 <code>${esc(e.source)}</code></div><div class="prop">目标端 <code>${esc(e.target)}</code></div><div class="prop">端口 <code>${esc(E.endpoint(graph,e,'source').side||'auto')} → ${esc(E.endpoint(graph,e,'target').side||'auto')}</code></div><div class="prop">途经点 <code>${e.waypoints.length}</code></div><p class="micro">${e.draft?'本页编辑草稿':'导入的原图连接'} · ${esc(e.role||'tensor')}</p><pre>${esc(E.path(E.displayed(graph,e),e.style,graph,e))}</pre><details><summary>容器接口与边界</summary><pre>${esc(JSON.stringify({gates:e.contract?.gates,originalSource:e.contract?.source,originalTarget:e.contract?.target,validation:C.validate(graph,e,e.route),reason:e.reason||null},null,2))}</pre></details><details><summary>原始语义映射</summary><pre>${esc(JSON.stringify(e.binding,null,2))}</pre></details><button class="secondary" id="releasePorts">释放固定端口</button><button class="secondary" id="clearBends">清除手动折点</button><button class="secondary" id="deleteEdge">删除这条边</button>`;$('arrowStyle').value=e.arrow;
      $('releasePorts').onclick=()=>{save();delete e.fixedSource;delete e.fixedTarget;delete e.physicalSource;delete e.physicalTarget;e.draft=true;delete e.contract;C.initialize(graph);dirty=true;render();persist();toast('已释放物理端口；原始语义映射保留在检查器。');};
      $('clearBends').onclick=()=>{save();e.waypoints=[];dirty=true;render();persist();};$('deleteEdge').onclick=()=>{save();graph.sourceDraftOperations=graph.sourceDraftOperations||[];graph.sourceDraftOperations.push({kind:'remove-connection',id:e.id,binding:E.clone(e.binding)});graph.edges=graph.edges.filter(x=>x!==e);selectedEdges.clear();dirty=true;render();persist();};
    }else if(selectedNodes.size===1){const n=node([...selectedNodes][0]);box.innerHTML=`<p class="eyebrow">SELECTED NODE</p><h3>${esc(label(n))}</h3><div class="prop">位置 <code>${Math.round(n.x)}, ${Math.round(n.y)}</code></div><div class="prop">尺寸 <code>${Math.round(n.w)} × ${Math.round(n.h)}</code></div><div class="prop">所属容器 <code>${esc(n.parent||"画布")}</code></div><p class="micro">${n.expanded?'展开的容器；移动时携带可见子节点。':'移动时同步更新所属文字与局部连线。'}</p><details><summary>源码 / IR 节点</summary><pre>${esc(JSON.stringify(n.semantic,null,2))}</pre></details>`;
    }else box.innerHTML=`<p class="micro">${selectedNodes.size||selectedEdges.size?`已选 ${selectedNodes.size} 个节点 / ${selectedEdges.size} 条边`:'点击节点或连接，检查图元、端口和源码映射。'}<br>Shift + 点击可多选。</p>`;
  }
  function nearestSide(n,p){const sides=[['left',Math.abs(p.x-n.x),(p.y-n.y)/n.h],['right',Math.abs(p.x-n.x-n.w),(p.y-n.y)/n.h],['top',Math.abs(p.y-n.y),(p.x-n.x)/n.w],['bottom',Math.abs(p.y-n.y-n.h),(p.x-n.x)/n.w]],b=sides.sort((a,b)=>a[1]-b[1])[0];return{side:b[0],fraction:Math.max(.02,Math.min(.98,b[2]))};}
  function hitNode(p){return graph.nodes.filter(n=>!n.junction&&p.x>=n.x-4&&p.x<=n.x+n.w+4&&p.y>=n.y-4&&p.y<=n.y+n.h+4).sort((a,b)=>a.w*a.h-b.w*b.h)[0];}
  function begin(ev,item){if(busy||ev.button!==0)return;ev.stopPropagation();ev.preventDefault();drag={...item,start:point(ev),last:point(ev),clientX:ev.clientX,clientY:ev.clientY,saved:false};svg.setPointerCapture(ev.pointerId);}
  function selectEdge(e,additive=false){if(!additive){selectedEdges.clear();selectedNodes.clear();}if(additive&&selectedEdges.has(e.id))selectedEdges.delete(e.id);else selectedEdges.add(e.id);}
  function nodeDown(ev,n){if(busy||ev.button!==0)return;ev.stopPropagation();if(tool==='pan'){begin(ev,{kind:'pan',camera:{...camera}});return;}
    if(tool==='connect'){if(!connection){connection={node:n,fixed:null};selectedNodes=new Set([n.id]);selectedEdges.clear();toast('选择目标节点，或从端口拖动连接。');}else completeConnection(n,nearestSide(n,point(ev)));render();return;}
    if(ev.shiftKey){selectedNodes.has(n.id)?selectedNodes.delete(n.id):selectedNodes.add(n.id);render();return;}
    selectedNodes=new Set([n.id]);selectedEdges.clear();begin(ev,{kind:'node',node:n});render();
  }
  function edgeDown(ev,e){if(busy||ev.button!==0)return;ev.stopPropagation();if(tool==='pan'){begin(ev,{kind:'pan',camera:{...camera}});return;}
    if(tool==='bend'&&selectedEdges.has(e.id)){save();const p=point(ev);let closest=Infinity,index=1;for(let i=1;i<e.route.length;i++){const a=e.route[i-1],b=e.route[i],den=(b.x-a.x)**2+(b.y-a.y)**2,t=den?Math.max(0,Math.min(1,((p.x-a.x)*(b.x-a.x)+(p.y-a.y)*(b.y-a.y))/den)):0,d=Math.hypot(p.x-a.x-(b.x-a.x)*t,p.y-a.y-(b.y-a.y)*t);if(d<closest){closest=d;index=i;}}e.route.splice(index,0,{x:p.x,y:p.y});e.waypoints.push({x:p.x,y:p.y});e.style='orthogonal';dirty=true;toast('已添加折点；启用保留途经点后 Apply。');persist();}
    else selectEdge(e,ev.shiftKey);render();
  }
  function startConnection(ev,n,fixed){connection={node:n,fixed};begin(ev,{kind:'connection',origin:E.port(n,fixed)});}
  function completeConnection(n,fixed){if(!connection)return;save();const e={id:'draft-'+Date.now().toString(36)+'-'+(++epoch),source:connection.node.id,target:n.id,arrow:$('arrowStyle').value,style:'orthogonal',waypoints:[],route:[],fixedSource:connection.fixed||undefined,fixedTarget:fixed||undefined,draft:true,binding:{evidence:'visual edit draft; no source model writeback'}};e.route=[E.endpoint(graph,e,'source'),E.endpoint(graph,e,'target')];graph.edges.push(e);selectedNodes.clear();selectedEdges=new Set([e.id]);connection=null;dirty=true;persist();toast('连接已创建，Apply 计算避障路径。');}
  svg.addEventListener('pointerdown',ev=>{if(busy||ev.button!==0)return;if(tool==='pan'||ev.button===1){begin(ev,{kind:'pan',camera:{...camera}});return;}if(ev.target===svg||ev.target.closest('#annotationLayer')){selectedNodes.clear();selectedEdges.clear();connection=null;render();}});
  svg.addEventListener('pointermove',ev=>{if(!drag)return;const p=point(ev);
    if(drag.kind==='pan'){const dx=(ev.clientX-(drag.clientX??ev.clientX))/stageScale(),dy=(ev.clientY-(drag.clientY??ev.clientY))/stageScale();camera.x-=dx;camera.y-=dy;drag.clientX=ev.clientX;drag.clientY=ev.clientY;cameraUpdate();return;}
    if((drag.kind==='node'||drag.kind==='bend'||drag.kind==='route-label')&&!drag.saved){save();drag.saved=true;}
    if(drag.kind==='node'){const n=drag.node,dx=Math.max(3-n.x,Math.min(graph.canvas[0]-3-n.x-n.w,p.x-drag.last.x)),dy=Math.max(3-n.y,Math.min(graph.canvas[1]-3-n.y-n.h,p.y-drag.last.y));E.move(graph,n.id,dx,dy,options());drag.last=p;dirty=true;render();}
    else if(drag.kind==='route-label'){E.snapRouteLabel(graph,drag.label,{x:p.x+drag.grab.x,y:p.y+drag.grab.y});dirty=true;render();}
    else if(drag.kind==='bend'){const e=drag.edge,old=e.waypoints[drag.index],i=e.route.findIndex(v=>R.dist(v,old)<.01);e.waypoints[drag.index]={x:p.x,y:p.y};if(i>=0)e.route[i]={x:p.x,y:p.y};dirty=true;render();}
    else{const a=drag.kind==='connection'?drag.origin:drag.edge.route[drag.side==='source'?0:drag.edge.route.length-1];$('previewLayer').replaceChildren(element('path',{d:`M ${a.x} ${a.y} L ${p.x} ${p.y}`,stroke:'#d77944',fill:'none','stroke-width':2/stageScale(),'stroke-dasharray':'5 5','pointer-events':'none'}));}
  });
  svg.addEventListener('pointerup',ev=>{if(!drag)return;const p=point(ev),n=hitNode(p),kind=drag.kind;
    if(kind==='connection'){if(n)completeConnection(n,nearestSide(n,p));else{connection=null;toast('连接取消：请释放在目标节点或端口上。');}}
    else if(kind==='endpoint'){if(n){save();E.reconnect(graph,drag.edge,drag.side,n.id,nearestSide(n,p));dirty=true;toast('端点已重接；Apply 更新这条路径。');}else toast('端点未落在节点上，保留原连接。');}
    if(kind==='route-label'&&drag.saved)toast('文字已吸附到所属连线；拖动模块与重新布线时自动跟随。');
    if(kind==='node'&&drag.saved)toast(graph.lastMove?.blocked?'此位置无法保留合法连接，已限制移动。':'节点、所属文字与连接已同步更新。');
    drag=null;$('previewLayer').replaceChildren();if(svg.hasPointerCapture(ev.pointerId))svg.releasePointerCapture(ev.pointerId);persist();render();
  });
  svg.addEventListener('pointercancel',()=>{drag=null;connection=null;$('previewLayer').replaceChildren();render();});
  svg.addEventListener('wheel',ev=>{if(!graph)return;ev.preventDefault();zoom(ev.deltaY<0?1.15:1/1.15,point(ev));},{passive:false});
  async function runRouting(ids,opts){
    C.initialize(graph);
    if(location.protocol!=='file:'&&typeof Worker!=='undefined'){
      const result=await new Promise(resolve=>{const worker=new Worker('routing-worker.js');worker.onmessage=event=>{worker.terminate();resolve(event.data);};worker.onerror=()=>{worker.terminate();resolve(null);};worker.postMessage({graph:E.clone(graph),ids,options:opts});});
      if(result?.ok)return result;
    }
    await new Promise(resolve=>setTimeout(resolve,0));
    return E.routeBatch(graph,ids,opts);
  }
  async function apply(){if(!graph||busy)return;restoreSourceBaseline();const sourceCheck=C.validateSource(graph);if(!sourceCheck.ok){render();toast('源码语义校验失败：'+sourceCheck.violations[0]);return;}let targets=$('scope').value==='all'?graph.edges:$('scope').value==='selected'?graph.edges.filter(e=>selectedEdges.has(e.id)):graph.edges.filter(e=>selectedNodes.has(e.source)||selectedNodes.has(e.target));
    if(!targets.length){toast('作用范围为空，请先选择节点或边。');return;}if($('policy').value==='never'){metrics={routed:0,time:0};render();toast('Never：保留当前路径。');return;}
    const opts=options();if($('policy').value==='needed')targets=targets.filter(e=>E.conflicts(graph,e,opts));if(!targets.length){metrics={routed:0,time:0};render();toast('当前路径满足约束，无需重算。');return;}
    save();ghost=graph.edges.map(e=>({route:E.clone(e.route),style:e.style}));busy=true;render();const begin=performance.now(),before=JSON.stringify(graph.nodes.map(n=>[n.id,n.x,n.y]));
    try{const result=await runRouting(targets.map(e=>e.id),opts);graph=result.graph;if(before!==JSON.stringify(graph.nodes.map(n=>[n.id,n.x,n.y])))throw new Error('布线不应移动节点');metrics={routed:result.routed,time:Math.round(performance.now()-begin)};dirty=result.failed>0;toast(result.failed?`${result.routed} 条完成，${result.failed} 条约束冲突（红色），原路径保留。请检查容器接口、端口或安全距离。`:`${result.routed} 条边已布线${result.retained?' · '+result.retained+' 段原始合法通道/汇流骨架保留':''} · 节点位置不变`);}catch(error){toast(error.message);}finally{busy=false;render();persist();}
  }
  function download(text,type,name){const url=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);}
  function exportSvg(){const out=svg.cloneNode(true);out.setAttribute('xmlns',NS);out.setAttribute('width',graph.canvas[0]);out.setAttribute('height',graph.canvas[1]);out.setAttribute('viewBox','0 0 '+graph.canvas.join(' '));out.removeAttribute('tabindex');out.querySelector('#previewLayer').remove();out.querySelector('#handleLayer').remove();out.querySelector('#obstacleLayer').remove();out.querySelector('#ghostLayer').remove();out.querySelectorAll('.wire-hit,.node-hit,.frame-hit,[data-editor-only]').forEach(n=>n.remove());const style=element('style',{},'.wire-path{fill:none;stroke-linecap:butt;stroke-linejoin:round}.scene-node text{font-family:DejaVu Sans,Arial,sans-serif}');out.querySelector('defs').append(style);out.prepend(element('rect',{x:0,y:0,width:graph.canvas[0],height:graph.canvas[1],fill:'white'}));out.prepend(element('metadata',{'id':'summary-merge-binding'},JSON.stringify({case:current.id,view:view.key,source:graph.source,irSha256:graph.irSha256,edited:dirty,sourceDraftOperations:graph.sourceDraftOperations||[],sourceValidation:C.validateSource?.(graph),attachments:graph.attachments||[],routeLabels:graph.routeLabels||[],junctionMarkers:graph.junctionMarkers||[],nodes:graph.nodes.map(n=>({id:n.id,parent:n.parent,semantic:n.semantic,visualBinding:n.visualBinding})),edges:graph.edges.map(e=>({id:e.id,source:e.source,target:e.target,draft:e.draft,binding:e.binding,portPolicy:e.portPolicy,physicalSource:e.physicalSource,physicalTarget:e.physicalTarget}))})));download(new XMLSerializer().serializeToString(out),'image/svg+xml',current.title+'-'+view.key+'.svg');toast('已生成当前视图 SVG。');}
  for(const collection of Object.keys(names)){const o=document.createElement('option');o.value=collection;o.textContent=names[collection];$('collection').append(o);}
  $('coverage').textContent=`${catalog.counts.active} 当前案例 / ${catalog.counts.historical} 历史案例`;
  for(const id of ['search','collection','includeHistory'])$(id).addEventListener(id==='search'?'input':'change',renderCatalog);
  for(const b of document.querySelectorAll('[data-tool]'))b.onclick=()=>{if(busy)return;tool=b.dataset.tool;connection=null;for(const x of document.querySelectorAll('[data-tool]'))x.classList.toggle('active',x===b);if(tool==='connect')$('showPorts').checked=true;render();};
  for(const id of ['showGhost','showObstacles','showPorts'])$(id).onchange=render;
  $('clearance').oninput=()=>{$('clearanceValue').value=$('clearance').value+' px';};$('applyLayout').onclick=apply;
  $('setArrow').onclick=()=>{if(!selectedEdges.size){toast('先选择一条或多条边。');return;}save();for(const e of graph.edges)if(selectedEdges.has(e.id))e.arrow=$('arrowStyle').value;render();persist();toast('箭头已更新；路线模型保持不变。');};
  $('undo').onclick=()=>{if(busy||!history.length)return;future.push(E.clone(graph));graph=history.pop();selectedNodes.clear();selectedEdges.clear();dirty=true;ghost=[];render();persist();};
  $('redo').onclick=()=>{if(busy||!future.length)return;history.push(E.clone(graph));graph=future.pop();selectedNodes.clear();selectedEdges.clear();dirty=true;ghost=[];render();persist();};
  $('reset').onclick=()=>{if(busy)return;save();graph=E.clone(original);selectedNodes.clear();selectedEdges.clear();ghost=[];dirty=false;fit();render();persist();toast('当前视图已恢复，仍可撤销。');};
  $('fit').onclick=()=>{fit();render();};$('fitWidth').onclick=()=>{fit(true);render();};$('zoomIn').onclick=()=>zoom(1.3);$('zoomOut').onclick=()=>zoom(1/1.3);$('exportSvg').onclick=exportSvg;
  $('exportJson').onclick=()=>download(JSON.stringify({schema:'summary-merge-edit/1',case:current.id,view:view.key,graph},null,2),'application/json',current.id+'-'+view.key+'.json');
  function evidence(){const q=$('evidenceSearch').value.toLowerCase();$('evidenceList').innerHTML=catalog.evidence.filter(e=>e.title.toLowerCase().includes(q)).map(e=>`<a class="evidence-row" href="../${esc(e.path)}" target="_blank">${esc(e.title)} <small>${Math.round(e.bytes/1024)} KB</small></a>`).join('');}
  $('showEvidence').onclick=()=>{evidence();$('evidenceDialog').showModal();};$('closeEvidence').onclick=()=>$('evidenceDialog').close();$('evidenceSearch').oninput=evidence;
  document.addEventListener('keydown',ev=>{if(ev.target.matches('input,select,textarea'))return;if((ev.ctrlKey||ev.metaKey)&&ev.key==='Enter'){ev.preventDefault();apply();}else if((ev.ctrlKey||ev.metaKey)&&ev.key.toLowerCase()==='z'){ev.preventDefault();(ev.shiftKey?$('redo'):$('undo')).click();}else if(ev.key==='Escape'){connection=null;selectedNodes.clear();selectedEdges.clear();render();}else if(ev.key==='Delete'&&selectedEdges.size){save();graph.sourceDraftOperations=graph.sourceDraftOperations||[];for(const e of graph.edges)if(selectedEdges.has(e.id))graph.sourceDraftOperations.push({kind:'remove-connection',id:e.id,binding:E.clone(e.binding)});graph.edges=graph.edges.filter(e=>!selectedEdges.has(e.id));selectedEdges.clear();dirty=true;render();persist();}});
  window.addEventListener('beforeunload',persist);window.addEventListener('resize',()=>{cameraUpdate();render();});
  const query=new URLSearchParams(location.search),chosen=catalog.cases.find(c=>c.id===query.get('case'))||catalog.cases.find(c=>c.collection==='transformer_programmatic_guide'&&c.title==='Transformer'&&!c.historical)||catalog.cases[0];
  if(chosen.historical)$('includeHistory').checked=true;
  renderCatalog();openCase(chosen,chosen.views.find(v=>v.key===query.get('view'))||chosen.views[0]);
})();
