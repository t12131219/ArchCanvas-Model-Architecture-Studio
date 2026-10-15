(function() {
  'use strict';
  const $=id=>document.getElementById(id),NS='http://www.w3.org/2000/svg';
  const catalog=window.SummaryCatalog,R=window.EdgeRouterLabRouting,E=window.SummaryEngine,C=window.SummaryConstraints,M=window.SummaryInteractionMode,F=window.SummaryRecursive,svg=$('graph');
  const names={module_programmatic_guide:'模块 · 76 案例',model_zoo_programmatic_guide:'Model Zoo · 完整模型',timeseries_programmatic_guide:'时序模型',transformer_programmatic_guide:'Transformer 与残差',pytorch_transformer_original:'PyTorch 原始架构',arrow_semantic_audit:'箭头审查与展开视图',yworks_edge_router_lab:'Edge Router 实验',source_adapter:'用户源码 · 静态适配'};
  const importedPackages=new Map(),importedSources=new Map(),A=window.SummarySourceAdapter;
  const studioCanvas=new URLSearchParams(location.search).get('surface')==='canvas';
  let studioBridge=null,startupPromise=null,catalogSources=null,canvasGridVisible=true;
  const sourceAssets=new Map();
  let current=null,view=null,graph=null,original=null,tool='select',selectedNodes=new Set(),selectedEdges=new Set(),selectedAnnotation=null;
  // Every model is edited as one detailed graph. The compact source views are
  // used only as the initial projection and summary routing reference.
  let unifiedSources=null,unifiedState=null;
  let history=[],future=[],ghost=[],drag=null,connection=null,busy=false,dirty=false,loadToken=0,epoch=0;
  let sourceCheck={ok:true,violations:[]},dragFrame=0,dragPoint=null,worker=null,workerId=0,persistTimer=0;
  let interactionMode=(()=>{try{return M.normalize(localStorage.getItem(M.key));}catch(_){return 'compat';}})();
  const pendingTasks=new Map();
  let camera={x:0,y:0,w:1100,h:720},metrics={routed:0,time:0},timer,sessions=new Map();
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const element=(tag,attrs={},text)=>{const n=document.createElementNS(NS,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n;};
  const key=()=>current.id+':unified';
  const unifiedVisible=()=>new Set(graph?.nodes?.map(n=>n.id)||[]);
  const unifiedChildren=id=>graph?.recursive?F.children(graph.recursive.authority,id):[];
  const unifiedHasChildren=id=>unifiedChildren(id).length>0&&!graph.recursive.authority.mandatory.includes(id);
  const unifiedDisplayEdges=()=>graph.edges;
  function syncUnifiedState(){unifiedState=graph?.recursive?{expandedIds:graph.nodes.filter(n=>n.expanded).map(n=>n.id)}:null;}
  function updateUnifiedStatus(){
    syncUnifiedState();if(!graph)return;const a=graph.recursive.authority,total=a.detail.nodes.filter(n=>!n.junction).length,opened=graph.nodes.filter(n=>n.expanded&&!a.mandatory.includes(n.id)).length;
    $('recursiveStatus').textContent=`递归图：已展开 ${opened} 个模块 · 显示 ${graph.nodes.filter(n=>!n.junction).length}/${total} 个节点`;
    $('collapseAll').disabled=busy||!!drag||!opened;$('expandAll').disabled=busy||!!drag||graph.nodes.length===a.detail.nodes.length;
  }
  async function changeFrontier(transition,propagateError=false){
    if(busy||drag||!graph)return;const before=graph,start=performance.now();busy=true;let committed=false,validation=null;
    try{
      render({presentationOnly:true});$('dirtyBadge').textContent='正在展开与整理边界连接…';
      studioBridge?.state();
      const result=await runGraphTask({task:'frontier',graph:before,transition,options:options()});if(!result.ok)throw new Error(result.error);if(result.unchanged)return;
      history.push(before);if(history.length>30)history.shift();future=[];
      graph=result.graph;syncUnifiedState();selectedNodes=new Set([...selectedNodes].filter(id=>node(id)));selectedEdges.clear();ghost=[];dirty=true;
      metrics={routed:result.routed||0,time:Math.round(performance.now()-start)};validation=result.validation;committed=true;
      svg.setAttribute('data-frontier-ms',metrics.time);svg.setAttribute('data-frontier-worker-ms',JSON.stringify(result.timing||{}));
      toast('展开状态与局部布局已保存；可继续选择内部模块。');
    }catch(error){graph=before;toast('展开未提交：'+error.message);if(propagateError)throw error;}finally{busy=false;render(committed?{validation}:{presentationOnly:true});if(committed)persist();studioBridge?.state();}
  }
  const toggleUnifiedNode=(id,force)=>changeFrontier({type:'toggle',id,expanded:force});
  const collapseUnifiedAll=()=>changeFrontier({type:'all',expanded:false});
  const expandUnifiedAll=()=>changeFrontier({type:'all',expanded:true});
  function restoreSourceBaseline(){} // Recursive receipts derive from registered source snapshots.
  const stageScale=()=>$('stage').clientWidth/camera.w;
  const point=event=>{const p=svg.createSVGPoint();p.x=event.clientX;p.y=event.clientY;return p.matrixTransform(svg.getScreenCTM().inverse());};
  const node=id=>graph.nodes.find(n=>n.id===id);
  function toast(message){$('toast').textContent=message;$('toast').classList.add('visible');clearTimeout(timer);timer=setTimeout(()=>$('toast').classList.remove('visible'),4500);}
  function updateInteractionModeUi(){
    const select=$('interactionMode'),badge=$('interactionModeBadge'),description=$('interactionModeDescription'),hint=$('interactionHint');
    if(select)select.value=interactionMode;
    if(badge){badge.textContent=M.label(interactionMode);badge.classList.toggle('realtime',interactionMode==='realtime');}
    if(description)description.textContent=M.description(interactionMode);
    if(hint)hint.textContent=interactionMode==='realtime'
      ? '双击模块或使用检查器逐级展开；收起会记住内部状态。拖动节点时会实时重算箭头、端点、分支和连线路径；每一帧都从拖动前快照执行语义安全移动，非法位置自动保留上一合法状态。模块文字与连线文字跟随。直接拖动连线文字可沿所属路径吸附。Apply 可优化所选范围的布线。'
      : '双击模块或使用检查器逐级展开；收起会记住内部状态。拖动节点时，模块文字与连线文字分别跟随；兼容模式按帧轻量预览，松开后在后台完成完整约束校验。直接拖动连线文字可沿所属路径吸附。Apply 可优化所选范围的布线。';
    if(svg)svg.setAttribute('data-interaction-mode',interactionMode);
  }
  function setInteractionMode(value,notify=true){
    const next=M.normalize(value);if(drag||busy){if($('interactionMode'))$('interactionMode').value=interactionMode;toast('当前正在处理操作，完成后再切换交互模式。');return;}
    interactionMode=next;try{localStorage.setItem(M.key,interactionMode);}catch(_){}
    updateInteractionModeUi();
    if(notify)toast(interactionMode==='realtime'?'已切换到实时模式：拖动中同步更新箭头与连线。':'已切换到兼容模式：拖动结束后后台校验并整理连线。');
  }
  function save(){history.push(E.clone(graph));if(history.length>30)history.shift();future=[];}
  function flushPersist(){clearTimeout(persistTimer);persistTimer=0;if(!graph||!current||busy||drag)return;F.remember(graph);const state={graph:E.clone(graph),history:history.slice(),future:future.slice(),dirty};sessions.set(key(),state);
    const payload={version:5,ir:original.irSha256||null,graph:E.clone(graph),dirty};delete payload.graph.recursive.authority;
    const modelKey=key();window.SummaryRecursiveStorage.put(modelKey,payload).then(()=>{if(current&&key()===modelKey){svg.setAttribute('data-storage-status','saved');$('recursiveStatus').title='展开树、局部布局和当前图已保存到浏览器。';studioBridge?.state();}}).catch(error=>{svg.setAttribute('data-storage-status','error');studioBridge?.emit('error',{command:'save',message:error.message});toast('自动保存失败，请导出 JSON 保留当前状态：'+error.message);});
  }
  function persist(){clearTimeout(persistTimer);persistTimer=setTimeout(flushPersist,180);}
  function options(){return {margin:+$('clearance').value,stub:28,bendCost:40,crossingCost:$('crossings').checked?450:0,overlapCost:$('crossings').checked?2:0,edgeSpacing:$('crossings').checked?12:0,preserve:$('keepBends').checked,sides:$('portSides').value,grid:$('gridEnabled').checked?24:0,style:$('routingStyle').value};}
  function label(n){return graph?.recursive?.state?.studioPresentation?.nodes?.[n.id]?.alias||n.label||n.id;}
  function lab(){
    const nodes=[['A','Source','输入',75,166,132,66],['B','Transform','变换',380,80,138,66],['C','Merge','汇合',748,148,138,66],['D','Output','输出',900,335,132,76],['E','Archive','存储',755,557,138,66],['F','Residual','旁路',82,518,132,66],['G','Observer','观察',371,549,138,66],['O1','Obstacle','拖动我',475,271,142,160],['O2','Block','固定障碍',245,326,118,78]].map(([id,name,sub,x,y,w,h])=>({id,label:name,x,y,w,h,base:[x,y],parent:null,expanded:false,routingObstacle:true,semantic:{kind:'routing sandbox'},html:`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="9" fill="${id.startsWith('O')?'#e5eeec':'#0e9b9f'}" stroke="${id.startsWith('O')?'#c7d9d5':'#078b91'}"/><text x="${x+15}" y="${y+27}" fill="${id.startsWith('O')?'#64867f':'white'}" font-size="16">${name}</text><text x="${x+15}" y="${y+47}" fill="${id.startsWith('O')?'#7c9891':'#b7e5e3'}" font-size="10">${sub}</text>`}));
    const edges=[['A','B'],['B','C'],['C','D'],['A','C'],['A','D'],['F','G'],['G','D'],['G','E'],['D','E'],['A','F'],['B','G']].map(([source,target],i)=>({id:'e'+(i+1),source,target,arrow:'target',style:'orthogonal',route:[],waypoints:[],binding:{evidence:'independent routing sandbox'},draft:false}));
    const g={nodes,edges,canvas:[1100,720],caseId:'routing-lab',viewKey:'overview',definitions:'',extras:'',sourceFacts:['移动障碍或节点后 Apply，比较路径变化。','边样式与路由几何分别编辑，端点重接保留历史记录。'],sourceProfile:{},irSource:null,source:null};
    for(const e of edges){e.route=[E.endpoint(g,e,'source'),E.endpoint(g,e,'target')];}
    const routed=E.routeBatch(g,edges.map(e=>e.id),{margin:14,stub:28,bendCost:40,crossingCost:180,overlapCost:2,edgeSpacing:12,sides:'any',style:'orthogonal'}).graph;
    // The independent sandbox has no imported source snapshots. Register its
    // initial physical interfaces before entering the shared recursive editor.
    for(const e of routed.edges){for(const side of ['source','target']){const port=e[side+'Port'];e[side==='source'?'fixedSource':'fixedTarget']={side:port.side,fraction:port.fraction};}e.portPolicy={source:{mode:'perimeter',shape:'rectangle',spacing:12,gates:[],sharedStem:null,authority:'independent routing sandbox'},target:{mode:'perimeter',shape:'rectangle',spacing:12,gates:[],sharedStem:null,authority:'independent routing sandbox'}};}
    return routed;
  }
  function renderCatalog(){
    const query=$('search').value.toLowerCase(),collection=$('collection').value,historyVisible=$('includeHistory').checked;
    const filtered=catalog.cases.filter(c=>(historyVisible||!c.historical)&&(collection==='all'||collection===c.collection)&&[c.title,c.origin].join(' ').toLowerCase().includes(query));
    $('catalogCount').textContent=`显示 ${filtered.length} 个案例 · 每个模型独立保存展开状态`;
    const list=$('caseList');list.replaceChildren();let previous='';
    for(const c of filtered){if(c.collection!==previous){const h=document.createElement('div');h.className='collection-label';h.textContent=names[c.collection]||c.collection;list.append(h);previous=c.collection;}
      const b=document.createElement('button');b.className='case-button'+(current?.id===c.id?' active':'');b.dataset.caseId=c.id;
      b.innerHTML=`<strong>${esc(c.title)}</strong><small>${c.historical?'历史 · ':''}递归模型图</small>`;
      b.onclick=()=>openCase(c,c.views[0]);list.append(b);
    }
  }
  function asset(descriptor,c){if(importedSources.has(c.id))return Promise.resolve(importedSources.get(c.id)[descriptor.key]);return new Promise((resolve,reject)=>{const id=c.id+':'+descriptor.key;if(window.SummaryCaseData?.[id])return resolve(window.SummaryCaseData[id]);const script=document.createElement('script');script.src='../'+descriptor.asset;script.onload=()=>resolve(window.SummaryCaseData[id]);script.onerror=()=>reject(new Error('无法读取 '+descriptor.asset));document.head.append(script);});}
  async function caseSources(c,builtin=false){
    // The menu exposes overview/detail, while imported sources also supply
    // compact receipts for every nested depth. All receipts are authoritative
    // inputs to folding, reopening and routing; menu entries are not that list.
    if(importedSources.has(c.id))return importedSources.get(c.id);
    return builtin?{overview:lab()}:Object.fromEntries(await Promise.all(c.views.map(async d=>[d.key,await asset(d,c)])));
  }
  async function openCase(c,v,restore){
    if(busy||drag){toast('正在处理图操作，完成后可切换示例。');return false;}
    flushPersist();const token=++loadToken,modelKey=c.id+':unified';let committed=false,validation=null;busy=true;
    render({presentationOnly:true});studioBridge?.state();
    try{
      const builtin=!!v.builtin;
      const sources=await caseSources(c,builtin);
      if(token!==loadToken)return false;
      const nextSources=Object.fromEntries(Object.entries(sources).map(([k,g])=>[k,C.initialize(E.clone(g))]));
      const initial=await runGraphTask({task:'frontier',graph:F.build(F.create(nextSources)),options:{}});
      if(!initial.ok||initial.failed)throw new Error(initial.error||'初始递归图存在无法布线的边界连接');
      const base=initial.graph;let saved=restore||sessions.get(modelKey);
      if(!saved){const stored=await window.SummaryRecursiveStorage.get(modelKey);if(token!==loadToken)return false;if(stored?.version===5&&stored.ir===(base.irSha256||null))saved={graph:stored.graph,history:[],future:[],dirty:stored.dirty};}
      if(!saved)try{const disk=JSON.parse(localStorage.getItem('summary-merge:'+modelKey));if(disk?.version===4&&disk.ir===(base.irSha256||null))saved={graph:disk.graph,history:[],future:[],dirty:disk.dirty};
        else if(disk?.version){localStorage.setItem('summary-merge:archived:'+modelKey+':'+Date.now(),JSON.stringify(disk));toast('早期递归草稿已保留归档，当前使用新的递归文档。');}
      }catch(_){}
      let nextGraph=E.clone(saved?.graph||base);validation=initial.validation;
      if(saved){nextGraph.recursive.authority=E.clone(base.recursive.authority);const prior=nextGraph;nextGraph=F.upgrade(nextGraph);if(nextGraph!==prior){const updated=await runGraphTask({task:'frontier',graph:nextGraph,options:{}});if(!updated.ok||updated.failed)throw new Error(updated.error||'保存的展开图无法恢复合法连接');nextGraph=updated.graph;validation=updated.validation;saved={...saved,history:[],future:[]};}else {const checked=await runGraphTask({task:'validate',graph:nextGraph});if(!checked.ok)throw new Error(checked.error);validation=checked.validation;}if(!validation.source.ok||!validation.layout.ok||invalidSourceRoutes(nextGraph,validation)){
        const archiveKey='summary-merge:archived:'+modelKey+':'+Date.now();localStorage.setItem(archiveKey,JSON.stringify(saved));nextGraph=E.clone(base);validation=initial.validation;saved=null;toast('旧草稿不符合当前层级或连接契约，已保留归档。');}}
      const evidencePath=catalogSources?.cases?.[c.id]?.evidence;if(evidencePath)try{await sourceAsset(evidencePath,true);}catch(error){console.warn('Case evidence:',error.message);}if(token!==loadToken)return false;
      // Publish case identity, source authority and graph together. Loading
      // never lends the old graph a new persistence key or editable source.
      current=c;view={key:'unified',label:'递归图'};unifiedSources=nextSources;original=E.clone(base);graph=nextGraph;committed=true;
      syncUnifiedState();history=saved?.history||[];future=saved?.future||[];dirty=saved?.dirty||false;ghost=[];selectedNodes.clear();selectedEdges.clear();selectedAnnotation=null;connection=null;drag=null;metrics={routed:0,time:0};
      $('routingStyle').value='orthogonal';$('keepBends').checked=false;$('showPorts').checked=c.id==='routing-lab';$('clearance').value=c.id==='routing-lab'?14:6;$('clearanceValue').value=$('clearance').value+' px';
      $('modelTitle').textContent=c.title;$('modelCollection').textContent=names[c.collection]||c.collection;$('modelOrigin').textContent=(c.historical?'历史快照 / ':'')+c.origin;
      
      const data=unifiedSources.overview||Object.values(unifiedSources)[0];
      const docs=Object.entries(data.sourceDocs||{}).map(([name,url])=>[name==='source_map.md'?'源码映射':name==='source_evidence.json'?'源码证据':'案例说明',url]);
      $('sourceLinks').innerHTML=[['原始 SVG',data.source],['布局与接口',data.layoutSource],['语义 IR',data.irSource],...docs,['原始案例',c.sourceIndex]].filter(([,url])=>url&&!(c.id==='pytorch-original'&&url.endsWith('index.html'))).map(([name,url])=>`<a href="../${esc(url)}" target="_blank">${name} ↗</a>`).join('');
      $('sourceFacts').innerHTML=data.sourceFacts?.length?'<ul>'+data.sourceFacts.map(f=>'<li>'+esc(f)+'</li>').join('')+'</ul>':'<p>保留原始图元、层次和连接映射。点击容器逐级展开，视觉编辑可撤销，源模型未执行。</p>';
      if(Object.keys(data.sourceProfile||{}).length)$('sourceFacts').innerHTML+='<pre>'+esc(JSON.stringify(data.sourceProfile,null,2))+'</pre>';
      const imported=importedPackages.get(c.id);$('exportSourcePackage').disabled=!imported;
      if(imported){$('sourceLinks').innerHTML='<button id="downloadAdapterIR">下载统一 IR</button><button id="downloadAdapterBundle">下载源码与证据包</button>';$('downloadAdapterIR').onclick=()=>download(JSON.stringify(imported.ir,null,2),'application/json',c.title+'-source-ir.json');$('downloadAdapterBundle').onclick=()=>download(JSON.stringify(imported,null,2),'application/json',c.title+'-source-adapter.json');
        $('sourceFacts').innerHTML+='<details><summary>源码证据与待解析区域</summary>'+Object.values(imported.evidence).slice(0,60).map(e=>`<p>${esc(e.file)}:${e.line}–${e.endLine}</p><pre>${esc(e.expression)}</pre>`).join('')+'</details>';}
      const url=new URL(location.href);url.searchParams.set('case',c.id);url.searchParams.delete('view');window.history.replaceState(null,'',url);
      renderCatalog();fit();return true;
    }catch(error){toast('示例未切换：'+error.message);if(!graph)$('modelTitle').textContent='示例加载失败';return false;}
    finally{busy=false;render(committed?{validation}:{presentationOnly:true});if(committed)persist();studioBridge?.state();}
  }
  function cameraUpdate(){svg.setAttribute('viewBox',`${camera.x} ${camera.y} ${camera.w} ${camera.h}`);$('zoomLabel').textContent=Math.round(stageScale()*100)+'%';}
  function fit(widthOnly=false){if(!graph)return;const ratio=$('stage').clientWidth/$('stage').clientHeight,w=graph.canvas[0],h=graph.canvas[1];camera=widthOnly?{x:0,y:0,w,h:w/ratio}:w/h>ratio?{x:0,y:(h-w/ratio)/2,w,h:w/ratio}:{x:(w-h*ratio)/2,y:0,w:h*ratio,h};cameraUpdate();}
  function zoom(factor,at){const p=at||{x:camera.x+camera.w/2,y:camera.y+camera.h/2},newWidth=Math.min(graph.canvas[0]*8,Math.max(120,camera.w/factor)),f=newWidth/camera.w;camera={x:p.x-(p.x-camera.x)*f,y:p.y-(p.y-camera.y)*f,w:newWidth,h:camera.h*f};cameraUpdate();render({cameraOnly:true});}
  const scene={key:null,nodes:new Map(),edges:new Map(),labels:new Map(),attachments:new Map(),junctions:new Map(),obstacles:new Map(),checks:new Map(),placements:null};
  const setAttrs=(el,attrs)=>{for(const [k,v] of Object.entries(attrs))if(el.getAttribute(k)!==String(v))el.setAttribute(k,v);};
  function prune(map,ids){for(const [id,v] of map)if(!ids.has(id)){(v.g||v).remove();v.leader?.remove();map.delete(id);}}
  function refreshHandles(scale){
    const layer=$('handleLayer'),handle=Math.min(28,5/scale);layer.replaceChildren();
    for(const id of selectedNodes){const n=node(id);if(!n||n.junction)continue;
      layer.append(element('rect',{x:n.x-4,y:n.y-4,width:n.w+8,height:n.h+8,rx:9,fill:'none',stroke:'#d99160','stroke-width':2/scale,'stroke-dasharray':`${4/scale} ${3/scale}`,'pointer-events':'none','data-editor-only':'selection'}));
      if(window.ArchCanvasStudioPresentation.state(graph).nodes[n.id]?.pinned){
        const badge=element('g',{transform:`translate(${n.x+6} ${n.y+6})`,'pointer-events':'none','data-editor-only':'pin','data-pinned-node':n.id});
        badge.append(element('title',{},'已固定：禁止直接拖动和排列；仍随父容器移动与递归布局更新。'),element('rect',{width:22,height:20,rx:4,fill:'#fff8e9',stroke:'#bd8a39','stroke-width':1/scale}),element('path',{d:'M 7 9 V 6 A 4 4 0 0 1 15 6 V 9 M 6 9 H 16 V 17 H 6 Z',fill:'none',stroke:'#916620','stroke-width':1.4/scale}));layer.append(badge);
      }
    }
    if($('showPorts').checked)for(const n of graph.nodes){if(n.junction||!unifiedVisible().has(n.id))continue;
      const ports=current.id==='routing-lab'?['left','right','top','bottom'].map(side=>({fixed:{side,fraction:.5},p:R.port(n,side),field:side})):graph.edges.flatMap(e=>[['source','fixedSource'],['target','fixedTarget']].filter(([side])=>e[side]===n.id).map(([side])=>({fixed:window.SummaryPhysicalPorts.active(e,side)||{side:E.endpoint(graph,e,side).side,fraction:E.endpoint(graph,e,side).fraction},p:E.endpoint(graph,e,side),field:e.binding?.[side==='source'?'src':'dst']||'视觉草稿'})));
      const seen=new Set();for(const {p,fixed,field} of ports){const key=p.x+':'+p.y;if(seen.has(key))continue;seen.add(key);
        const c=element('circle',{cx:p.x,cy:p.y,r:handle*.65,fill:'#fff',stroke:'#3ca1a3','stroke-width':1/scale,class:'port-handle','data-port':n.id+':'+fixed.side});c.append(element('title',{},field));c.onpointerdown=ev=>tool==='connect'?startConnection(ev,n,fixed):nodeDown(ev,n);layer.append(c);
      }
    }
    for(const id of selectedEdges){const e=graph.edges.find(e=>e.id===id);if(!e)continue;const ps=e.route;if(ps.length<2)continue;
      for(const [side,index] of [['source',0],['target',ps.length-1]]){const p=ps[index],c=element('circle',{cx:p.x,cy:p.y,r:handle*1.3,fill:'#fff4e6',stroke:'#d77944','stroke-width':1.5/scale,class:'endpoint-handle','data-endpoint':e.id+':'+side});c.onpointerdown=ev=>begin(ev,{kind:'endpoint',edge:e,side});layer.append(c);layer.append(element('text',{x:p.x,y:p.y+3/scale,'text-anchor':'middle','font-size':8/scale,fill:'#b86e36','pointer-events':'none'},side==='source'?'S':'T'));}
      e.waypoints.forEach((p,i)=>{const h=element('rect',{x:p.x-handle,y:p.y-handle,width:handle*2,height:handle*2,fill:'#fff',stroke:'#d77944','stroke-width':1.5/scale,class:'bend-handle','data-bend':e.id+':'+i});h.onpointerdown=ev=>begin(ev,{kind:'bend',edge:e,index:i});layer.append(h);});
    }
  }
  function render({interactive=false,presentationOnly=false,cameraOnly=false,validation=null,validationOrigin='worker'}={}){
    const measuredStart=performance.now();if(!graph)return;syncUnifiedState();
    if(cameraOnly){const scale=stageScale();for(const v of scene.edges.values())setAttrs(v.hit,{'stroke-width':Math.min(45,12/scale)});refreshHandles(scale);svg.setAttribute('data-camera-ms',(performance.now()-measuredStart).toFixed(2));return;}
    if(scene.key!==key()){
      for(const name of ['frameLayer','obstacleLayer','ghostLayer','edgeLayer','nodeLayer','labelLayer','handleLayer'])$(name).replaceChildren();
      for(const name of ['nodes','edges','labels','attachments','junctions','obstacles','checks'])scene[name].clear();scene.key=key();scene.placements=null;
    }
    if(!interactive&&!presentationOnly){const validationStart=performance.now();
      const checked=validation||E.validateView(graph);sourceCheck=checked.source;scene.checks=new Map(checked.edges);
      svg.setAttribute('data-layout-constraint-valid',String(checked.layout.ok));svg.setAttribute('data-layout-constraint-reason',checked.layout.violations.join('; '));
      svg.setAttribute('data-validation-ms',(performance.now()-validationStart).toFixed(2));
      svg.setAttribute('data-validation-origin',validation?validationOrigin:'main');
    }
    const realtimeDrag=drag?.kind==='node'&&drag.saved&&interactionMode==='realtime';
    setAttrs(svg,{'data-source-constraint-valid':String(sourceCheck.ok),'data-source-constraint-reason':sourceCheck.violations.join('; '),'data-interaction-mode':interactionMode,'data-interaction-phase':realtimeDrag?'realtime':interactive?'preview':busy?'settling':'committed'});
    if(scene.definitions!==graph.definitions){$('definitions').innerHTML=graph.definitions||'';scene.definitions=graph.definitions;}
    if(scene.extras!==graph.extras){$('annotationLayer').innerHTML=graph.extras||'';scene.extras=graph.extras;}
    const scale=stageScale(),visible=unifiedVisible(),visibleNodes=graph.nodes.filter(n=>!n.junction&&visible.has(n.id));
    for(const n of visibleNodes){if(n.junction)continue;let v=scene.nodes.get(n.id);
      if(!v){const g=element('g',{class:'scene-node','data-render-instance':++epoch}),content=element('g'),hit=element('rect',{rx:8});g.append(content,hit);v={g,content,hit};scene.nodes.set(n.id,v);$(n.expanded?'frameLayer':'nodeLayer').append(g);}
      setAttrs(v.g,{'data-node-id':n.id,'data-parent':n.parent||'','data-expanded':String(!!n.expanded),'data-recursive-children':unifiedChildren(n.id).length,'data-unified-expanded':String(!!unifiedState?.expandedIds?.includes(n.id)),'data-unified-collapsed':String(unifiedHasChildren(n.id)&&!unifiedState?.expandedIds?.includes(n.id)),'data-visual-binding':JSON.stringify(n.visualBinding||{}),'aria-label':`节点 ${n.id} ${label(n)}`});
      const ownerLayer=$(n.expanded?'frameLayer':'nodeLayer');
      // Preserve native click targets and stacking order on selection-only
      // renders. Reparent only when a module changes between node and frame.
      if(v.g.parentNode!==ownerLayer)ownerLayer.append(v.g);
      setAttrs(v.content,{transform:`translate(${n.x-n.base[0]} ${n.y-n.base[1]})`});if(v.html!==n.html){v.content.innerHTML=n.html;v.html=n.html;}if(n.expanded||graph.recursive?.state?.studioPresentation?.nodes?.[n.id]?.width){const rect=v.content.querySelector('rect');if(rect){rect.setAttribute('width',n.w);rect.setAttribute('height',n.h);}}applyStudioPresentation(n,v);
      setAttrs(v.hit,{x:n.x,y:n.y,width:n.w,height:n.h,class:n.expanded?'frame-hit':'node-hit'});v.g.onpointerdown=ev=>nodeDown(ev,n);v.g.ondblclick=ev=>{if(!busy&&!drag&&tool==='select'&&unifiedHasChildren(n.id)){ev.preventDefault();ev.stopPropagation();toggleUnifiedNode(n.id);}};
      if(unifiedHasChildren(n.id)){if(!v.toggle){v.toggle=element('g',{class:'expansion-control',role:'button',tabindex:'0'});v.toggle.append(element('rect',{width:22,height:22,rx:5,fill:'#fff',stroke:'#198e90'}),element('text',{x:11,y:16,'text-anchor':'middle','font-size':18,fill:'#198e90'}));v.g.append(v.toggle);}setAttrs(v.toggle,{transform:`translate(${n.x+n.w-28} ${n.y+5})`,'aria-label':`${n.expanded?'收起':'展开'} ${label(n)}`});v.toggle.querySelector('text').textContent=n.expanded?'−':'＋';v.toggle.onpointerdown=ev=>ev.stopPropagation();v.toggle.onclick=ev=>{ev.preventDefault();ev.stopPropagation();toggleUnifiedNode(n.id);};v.toggle.onkeydown=ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();toggleUnifiedNode(n.id);}};}else if(v.toggle){v.toggle.remove();v.toggle=null;}
      if($('showObstacles').checked&&n.routingObstacle!==false){const b=R.expand(n,+$('clearance').value);let obstacle=scene.obstacles.get(n.id);if(!obstacle){obstacle=element('rect',{fill:'none',stroke:'#c9925680','pointer-events':'none'});scene.obstacles.set(n.id,obstacle);$('obstacleLayer').append(obstacle);}setAttrs(obstacle,{x:b.x,y:b.y,width:b.w,height:b.h,'stroke-width':1/scale,'stroke-dasharray':`${4/scale} ${4/scale}`});}
    }
    prune(scene.nodes,new Set(visibleNodes.map(n=>n.id)));
    prune(scene.obstacles,new Set($('showObstacles').checked?visibleNodes.filter(n=>n.routingObstacle!==false).map(n=>n.id):[]));
    const labelStart=performance.now(),labelPlacements=presentationOnly&&scene.placements?scene.placements:E.routeLabelPlacements(graph,interactive);
    if(!interactive&&!presentationOnly)scene.placements=labelPlacements;svg.setAttribute('data-label-ms',(performance.now()-labelStart).toFixed(2));
    const displayEdges=unifiedDisplayEdges(),displayEdgeIds=new Set(displayEdges.map(e=>e.id));
    for(const a of graph.routeLabels||[]){if(unifiedState&&!displayEdgeIds.has(a.edge))continue;const offset=labelPlacements.get(a.id);if(!offset)continue;let v=scene.labels.get(a.id);
      if(!v){const leader=element('path',{stroke:'#a6adb5','stroke-width':.8,'stroke-dasharray':'2 3',fill:'none','pointer-events':'none','data-label-leader':a.id}),g=element('g',{class:'scene-attachment route-caption',style:'cursor:grab'}),bg=element('rect',{rx:2,fill:'white','fill-opacity':.9}),text=element('g');g.append(bg,text,element('title',{},'拖动文字沿所属连线吸附；模型连接保持绑定。'));v={g,bg,text,leader};scene.labels.set(a.id,v);$('labelLayer').append(leader,g);}
      setAttrs(v.g,{'data-route-label-id':a.id,'data-follow-edge':a.edge,'data-label-anchor':`${offset.point.x},${offset.point.y}`,transform:`translate(${offset.x} ${offset.y})`});
      const [x,y,w,h]=a.bbox;setAttrs(v.bg,{x:x-2,y:y-1,width:w+4,height:h+2});if(v.html!==a.html){v.text.innerHTML=a.html;v.html=a.html;}
      v.leader.setAttribute('display',offset.leader?'inline':'none');if(offset.leader){const b=offset.box,q=offset.point,tx=Math.max(b.x,Math.min(b.x+b.w,q.x)),ty=Math.max(b.y,Math.min(b.y+b.h,q.y));setAttrs(v.leader,{d:`M ${q.x} ${q.y} L ${tx} ${ty}`});}
      v.g.onpointerdown=ev=>{if(busy||ev.button!==0)return;ev.stopPropagation();if(tool==='pan'){begin(ev,{kind:'pan',camera:{...camera}});return;}selectedNodes.clear();selectedAnnotation=null;selectedEdges=new Set([a.edge]);const p=point(ev),center={x:offset.box.x+offset.box.w/2,y:offset.box.y+offset.box.h/2};begin(ev,{kind:'route-label',label:a,grab:{x:center.x-p.x,y:center.y-p.y}});render({presentationOnly:true});};
    }
    prune(scene.labels,new Set([...labelPlacements.keys()].filter(id=>{const a=(graph.routeLabels||[]).find(v=>v.id===id);return !unifiedState||a&&displayEdgeIds.has(a.edge);}))); 
    for(const a of graph.attachments||[]){const owner=node(a.owner);if(!owner||!visible.has(a.owner))continue;let v=scene.attachments.get(a.id);if(!v){const g=element('g',{class:'scene-attachment'});v={g};scene.attachments.set(a.id,v);$('labelLayer').append(g);}const offset=E.attachmentTransform(graph,a);setAttrs(v.g,{'data-attachment-id':a.id,'data-follow-owner':a.owner,'data-follow-kind':a.kind,transform:`translate(${offset.x} ${offset.y})`});if(v.html!==a.html){v.g.innerHTML=a.html;v.html=a.html;}v.g.onpointerdown=ev=>nodeDown(ev,owner);}
    prune(scene.attachments,new Set((graph.attachments||[]).filter(a=>visible.has(a.owner)).map(a=>a.id)));
    if(scene.ghost!==ghost||scene.showGhost!==$('showGhost').checked){$('ghostLayer').replaceChildren();if($('showGhost').checked)for(const e of ghost)$('ghostLayer').append(element('path',{d:E.path(e.route,e.style),fill:'none',stroke:'#a7babb','stroke-width':1.5,'stroke-dasharray':'6 7',opacity:.6,'pointer-events':'none'}));scene.ghost=ghost;scene.showGhost=$('showGhost').checked;}
    for(const e of displayEdges){let v=scene.edges.get(e.id);const edgeGraph=graph;const ps=interactive?R.simplify(e.route):presentationOnly&&v?.points?v.points:E.displayed(edgeGraph,e);if(ps.length<2)continue;const check=scene.checks.get(e.id)||{ok:true,violations:[]},selected=selectedEdges.has(e.id),appearance=window.ArchCanvasStudioPresentation.edgeAppearance(graph,e),color=e.failed||!check.ok?'#d54c60':selected?'#d77944':appearance.stroke,start=e.arrow==='both',end=e.arrow!=='none';
      if(!v){const g=element('g',{'data-render-instance':++epoch}),shaft=element('path',{fill:'none',class:'wire-path','stroke-linecap':'butt'}),head=element('path',{class:'arrow-shape','pointer-events':'none'}),tail=element('path',{class:'arrow-shape','pointer-events':'none'}),hit=element('path',{class:'wire-hit','data-edge-hit':e.id});g.append(shaft,head,tail,hit);v={g,shaft,head,tail,hit};scene.edges.set(e.id,v);$('edgeLayer').append(g);}
      setAttrs(v.g,{'data-edge-id':e.id,'data-source':e.source,'data-target':e.target,'data-role':e.role||'tensor','data-draft':String(!!e.draft),'data-physical-source':JSON.stringify(E.endpoint(edgeGraph,e,'source')),'data-physical-target':JSON.stringify(E.endpoint(edgeGraph,e,'target')),'data-constraint-valid':interactive?'pending':String(check.ok&&!e.failed),'data-constraint-reason':interactive?'drag preview':e.reason||check.violations.join('; '),'data-semantic-binding':JSON.stringify(e.binding),'data-boundary-gates':JSON.stringify(e.contract?.gates||[]),'aria-label':`边 ${e.id} ${e.source} 到 ${e.target}`});
      if(appearance.sourceRelation){v.g.setAttribute('data-source-relation-id',e.id);v.g.setAttribute('aria-label',`源码数据依赖 ${e.id} ${e.source} 到 ${e.target}；执行路径未确定`);}else v.g.removeAttribute('data-source-relation-id');
      const d=interactive?R.polylinePath(ps):presentationOnly&&v.path?v.path:E.path(ps,e.style,edgeGraph,e);
      if(!interactive&&!presentationOnly){v.points=ps;v.path=d;}setAttrs(v.shaft,{d,stroke:color,'stroke-width':selected?2.8:appearance.width,'stroke-dasharray':appearance.dashArray});
      setAttrs(v.head,{display:end?'inline':'none',d:end?E.arrow(ps.at(-1),ps.at(-2),e.arrow==='open'):'',fill:e.arrow==='open'?'none':color,stroke:e.arrow==='open'?color:'none','stroke-width':e.arrow==='open'?1.7:0});
      setAttrs(v.tail,{display:start?'inline':'none',d:start?E.arrow(ps[0],ps[1]):'',fill:color,stroke:'none'});
      setAttrs(v.hit,{d,'stroke-width':Math.min(45,12/scale)});v.hit.onpointerdown=ev=>edgeDown(ev,e);
    }
    prune(scene.edges,new Set(displayEdges.map(e=>e.id)));
    for(const marker of graph.junctionMarkers||[]){const p=E.junctionPoint(graph,marker);let dot=scene.junctions.get(marker.id);if(!dot){dot=element('circle',{'pointer-events':'none'});scene.junctions.set(marker.id,dot);$('edgeLayer').append(dot);}setAttrs(dot,{display:p?'inline':'none',cx:p?.x||0,cy:p?.y||0,r:marker.radius||2.5,fill:marker.fill||'#263b4b','data-junction-id':marker.id,'data-junction-owner':marker.owner,'data-junction-edges':JSON.stringify(marker.edges),'data-junction-wire':JSON.stringify(marker.wire)});}
    prune(scene.junctions,new Set((graph.junctionMarkers||[]).map(m=>m.id)));refreshHandles(scale);
    if(!interactive&&!presentationOnly){const stats=R.stats(displayEdges),count=visibleNodes.length;$('graphCount').textContent=`${count} nodes / ${displayEdges.length} edges`;$('metricNodes').textContent=count+' / '+displayEdges.length;$('metricLength').textContent=stats.length.toLocaleString();$('metricBends').textContent=stats.bends+' / '+stats.crossings;$('metricRouted').textContent=metrics.routed;$('metricTime').textContent=metrics.time;}
    if(!interactive)renderInspector();
    updateUnifiedStatus();$('dirtyBadge').textContent=realtimeDrag?(graph.lastMove?.blocked?'保留上一合法位置':'实时布线'):interactive?'拖动预览':!sourceCheck.ok?'源码语义校验失败':busy?'正在布线…':dirty?'待 Apply · 已编辑':'布局已就绪';$('dirtyBadge').title=sourceCheck.violations.join('; ');$('dirtyBadge').classList.toggle('dirty',dirty||!sourceCheck.ok);$('undo').disabled=busy||!!drag||!history.length;$('redo').disabled=busy||!!drag||!future.length;$('applyLayout').disabled=busy||!!drag||!sourceCheck.ok;$('interactionMode').disabled=busy||!!drag;
    $('exportSvg').disabled=busy||interactive;$('exportJson').disabled=busy||interactive;
    svg.setAttribute('data-render-ms',(performance.now()-measuredStart).toFixed(2));
    window.SummarySourceControls?.render(graph,svg);
    $('modelTitle').textContent=window.ArchCanvasStudioPresentation?.state(graph).title||current.title;window.ArchCanvasStudioPresentation?.render(graph,svg,{selectedAnnotation,onAnnotationDown:studioAnnotationDown});
    if(interactive)svg.setAttribute('data-preview-ms',(performance.now()-measuredStart).toFixed(2));
  }
  function renderInspector(interactive=false){const box=$('selectionInfo');studioBridge?.selection(studioSelection());
      if(selectedEdges.size===1){const e=graph.edges.find(e=>selectedEdges.has(e.id));const validation=scene.checks.get(e.id)||C.validate(graph,e,e.route);box.innerHTML=`<p class="eyebrow">SELECTED EDGE</p><h3>${esc(e.id)}</h3><div class="prop">源端 <code>${esc(e.source)}</code></div><div class="prop">目标端 <code>${esc(e.target)}</code></div><div class="prop">端口 <code>${esc(E.endpoint(graph,e,'source').side||'auto')} → ${esc(E.endpoint(graph,e,'target').side||'auto')}</code></div><div class="prop">途经点 <code>${e.waypoints.length}</code></div><p class="micro">${e.draft?'本页编辑草稿':'导入的原图连接'} · ${esc(e.role||'tensor')}</p><pre>${esc(scene.edges.get(e.id)?.path||E.path(E.displayed(graph,e),e.style,graph,e))}</pre><details><summary>容器接口与边界</summary><pre>${esc(JSON.stringify({gates:e.contract?.gates,originalSource:e.contract?.source,originalTarget:e.contract?.target,validation,reason:e.reason||null},null,2))}</pre></details><details><summary>原始语义映射</summary><pre>${esc(JSON.stringify(e.binding,null,2))}</pre></details><button class="secondary" id="releasePorts">释放固定端口</button><button class="secondary" id="clearBends">清除手动折点</button><button class="secondary" id="deleteEdge">删除这条边</button>`;$('arrowStyle').value=e.arrow;
      $('releasePorts').onclick=()=>{if(busy||drag)return;save();delete e.fixedSource;delete e.fixedTarget;delete e.physicalSource;delete e.physicalTarget;e.draft=true;delete e.contract;C.initialize(graph);dirty=true;render();persist();toast('已释放物理端口；原始语义映射保留在检查器。');};
      $('clearBends').onclick=()=>{if(busy||drag)return;save();e.waypoints=[];dirty=true;render();persist();};$('deleteEdge').onclick=()=>{if(busy||drag)return;save();graph.sourceDraftOperations=graph.sourceDraftOperations||[];graph.sourceDraftOperations.push({kind:'remove-connection',id:e.id,binding:E.clone(e.binding)});graph.edges=graph.edges.filter(x=>x!==e);selectedEdges.clear();dirty=true;render();persist();};
    }else if(selectedNodes.size===1){const n=node([...selectedNodes][0]),canExpand=unifiedHasChildren(n.id),isOpen=unifiedState?.expandedIds?.includes(n.id),pinned=!!window.ArchCanvasStudioPresentation.state(graph).nodes[n.id]?.pinned;box.innerHTML=`<p class="eyebrow">SELECTED NODE</p><h3>${esc(label(n))}</h3><div class="prop">位置 <code>${Math.round(n.x)}, ${Math.round(n.y)}</code></div><div class="prop">尺寸 <code>${Math.round(n.w)} × ${Math.round(n.h)}</code></div><div class="prop">所属容器 <code>${esc(n.parent||"画布")}</code></div><div class="prop">直接移动 <code>${pinned?'已固定':'未固定'}</code></div><p class="micro">固定阻止直接拖动和排列；子节点仍随父容器移动，递归展开也会更新布局。</p>${canExpand?`<button class="secondary" id="toggleSelectedNode">${isOpen?'收起子图':'展开子图'} · ${unifiedChildren(n.id).length} 个直接节点</button>`:''}<p class="micro">${canExpand?(isOpen?'已展开；可继续选择内部容器。':'可逐级展开；双击节点也可切换。'):(n.expanded?'展开的容器；移动时携带可见子节点。':'移动时同步更新所属文字与局部连线。')}</p><details><summary>源码 / IR 节点</summary><pre>${esc(JSON.stringify(n.semantic,null,2))}</pre></details>`;if(canExpand)$('toggleSelectedNode').onclick=()=>toggleUnifiedNode(n.id);
    }else box.innerHTML=`<p class="micro">${selectedNodes.size||selectedEdges.size?`已选 ${selectedNodes.size} 个节点 / ${selectedEdges.size} 条边`:'点击节点或连接，检查图元、端口和源码映射。'}<br>Shift + 点击可多选。</p>`;
  }
  function nearestSide(n,p){const sides=[['left',Math.abs(p.x-n.x),(p.y-n.y)/n.h],['right',Math.abs(p.x-n.x-n.w),(p.y-n.y)/n.h],['top',Math.abs(p.y-n.y),(p.x-n.x)/n.w],['bottom',Math.abs(p.y-n.y-n.h),(p.x-n.x)/n.w]],b=sides.sort((a,b)=>a[1]-b[1])[0];return{side:b[0],fraction:Math.max(.02,Math.min(.98,b[2]))};}
  function hitNode(p){const visible=unifiedVisible();return graph.nodes.filter(n=>!n.junction&&visible.has(n.id)&&p.x>=n.x-4&&p.x<=n.x+n.w+4&&p.y>=n.y-4&&p.y<=n.y+n.h+4).sort((a,b)=>a.w*a.h-b.w*b.h)[0];}
  function begin(ev,item){if(busy||(ev.button!==0&&!(item.kind==='pan'&&ev.button===1)))return;ev.stopPropagation();ev.preventDefault();drag={...item,start:point(ev),last:point(ev),clientX:ev.clientX,clientY:ev.clientY,saved:false};svg.classList.toggle('is-panning',item.kind==='pan');svg.setPointerCapture(ev.pointerId);studioBridge?.state();}
  function restoreGesture(gesture){graph=gesture.before;history=gesture.history;future=gesture.future;dirty=gesture.dirty;}
  function unchangedGesture(gesture){
    const near=(a,b)=>Math.abs(a-b)<1e-5,samePoints=(a,b)=>a?.length===b?.length&&a.every((p,i)=>near(p.x,b[i].x)&&near(p.y,b[i].y));
    if(gesture.kind==='node'){const a=gesture.before.nodes.find(n=>n.id===gesture.node.id),b=node(gesture.node.id);return a&&b&&near(a.x,b.x)&&near(a.y,b.y);}
    if(gesture.kind==='studio-annotation'){const P=window.ArchCanvasStudioPresentation,a=P.state(gesture.before).annotations[gesture.annotation],b=P.state(graph).annotations[gesture.annotation];return a&&b&&near(a.x,b.x)&&near(a.y,b.y);}
    if(gesture.kind==='route-label'){const a=gesture.before.routeLabels.find(a=>a.id===gesture.label.id);return JSON.stringify(a?.anchor)===JSON.stringify(gesture.label.anchor);}
    if(gesture.kind==='bend'){const a=gesture.before.edges.find(e=>e.id===gesture.edge.id),b=gesture.edge;return a&&samePoints(a.route,b.route)&&samePoints(a.waypoints,b.waypoints);}
    return false;
  }
  function selectEdge(e,additive=false){selectedAnnotation=null;if(!additive){selectedEdges.clear();selectedNodes.clear();}if(additive&&selectedEdges.has(e.id))selectedEdges.delete(e.id);else selectedEdges.add(e.id);}
  function nodeDown(ev,n){if(busy||ev.button!==0)return;ev.stopPropagation();if(tool==='pan'){begin(ev,{kind:'pan',camera:{...camera}});return;}selectedAnnotation=null;
    if(tool==='connect'){if(!connection){connection={node:n,fixed:null};selectedNodes=new Set([n.id]);selectedEdges.clear();toast('选择目标节点，或从端口拖动连接。');}else completeConnection(n,nearestSide(n,point(ev)));render();return;}
    if(ev.shiftKey){selectedNodes.has(n.id)?selectedNodes.delete(n.id):selectedNodes.add(n.id);render({presentationOnly:true});return;}
    selectedNodes=new Set([n.id]);selectedEdges.clear();if(!window.ArchCanvasStudioPresentation?.state(graph).nodes[n.id]?.pinned)begin(ev,{kind:'node',node:n});else toast('已固定直接移动；点击工具栏解锁后可拖动。该节点仍随父容器移动。');render({presentationOnly:true});
  }
  function edgeDown(ev,e){if(busy||ev.button!==0)return;ev.stopPropagation();if(tool==='pan'){begin(ev,{kind:'pan',camera:{...camera}});return;}
    if(tool==='bend'&&selectedEdges.has(e.id)){save();const p=point(ev);let closest=Infinity,index=1;for(let i=1;i<e.route.length;i++){const a=e.route[i-1],b=e.route[i],den=(b.x-a.x)**2+(b.y-a.y)**2,t=den?Math.max(0,Math.min(1,((p.x-a.x)*(b.x-a.x)+(p.y-a.y)*(b.y-a.y))/den)):0,d=Math.hypot(p.x-a.x-(b.x-a.x)*t,p.y-a.y-(b.y-a.y)*t);if(d<closest){closest=d;index=i;}}e.route.splice(index,0,{x:p.x,y:p.y});e.waypoints.push({x:p.x,y:p.y});e.style='orthogonal';dirty=true;toast('已添加折点；启用保留途经点后 Apply。');persist();}
    else selectEdge(e,ev.shiftKey);render({presentationOnly:tool!=='bend'});
  }
  function startConnection(ev,n,fixed){connection={node:n,fixed};begin(ev,{kind:'connection',origin:E.port(n,fixed)});}
  function completeConnection(n,fixed){if(!connection)return;save();const e={id:'draft-'+Date.now().toString(36)+'-'+(++epoch),source:connection.node.id,target:n.id,arrow:$('arrowStyle').value,style:'orthogonal',waypoints:[],route:[],fixedSource:connection.fixed||undefined,fixedTarget:fixed||undefined,draft:true,binding:{evidence:'visual edit draft; no source model writeback'}};e.route=[E.endpoint(graph,e,'source'),E.endpoint(graph,e,'target')];graph.edges.push(e);selectedNodes.clear();selectedEdges=new Set([e.id]);connection=null;dirty=true;persist();toast('连接已创建，Apply 计算避障路径。');}
  function studioAnnotationDown(ev,annotation){
    if(busy||ev.button!==0)return;ev.stopPropagation();
    if(tool==='pan'){begin(ev,{kind:'pan',camera:{...camera}});return;}
    selectedNodes.clear();selectedEdges.clear();selectedAnnotation=null;selectedAnnotation=annotation.id;connection=null;
    begin(ev,{kind:'studio-annotation',annotation:annotation.id});render({presentationOnly:true});
  }
  // Capture before node, label, handle and expansion-control handlers so the
  // Studio's middle-button pan works over every part of the canvas.
  svg.addEventListener('pointerdown',ev=>{if(ev.button!==1)return;ev.preventDefault();ev.stopImmediatePropagation();if(!graph||busy||drag)return;begin(ev,{kind:'pan',camera:{...camera}});},true);
  svg.addEventListener('auxclick',ev=>{if(ev.button===1)ev.preventDefault();});
  // Node gestures capture the pointer on the SVG. Browsers can consequently
  // retarget the real double-click to the SVG rather than the node group.
  svg.addEventListener('dblclick',ev=>{
    if(ev.target!==svg||ev.defaultPrevented||!graph||busy||drag||tool!=='select')return;
    const n=hitNode(point(ev));if(!n||!unifiedHasChildren(n.id))return;
    ev.preventDefault();ev.stopPropagation();toggleUnifiedNode(n.id);
  });
  svg.addEventListener('pointerdown',ev=>{if(ev.button!==0)return;if(tool==='pan'){begin(ev,{kind:'pan',camera:{...camera}});return;}if(busy)return;if(ev.target===svg||ev.target.closest('#annotationLayer')){selectedNodes.clear();selectedEdges.clear();selectedAnnotation=null;connection=null;render({presentationOnly:true});}});
  function processDragPoint(p){
    if(!drag)return;
    if(Math.hypot(p.x-drag.last.x,p.y-drag.last.y)<.01)return;
    const frameStart=performance.now();
    if((drag.kind==='node'||drag.kind==='bend'||drag.kind==='route-label'||drag.kind==='studio-annotation')&&!drag.saved){drag.history=history.slice();drag.future=future;drag.dirty=dirty;save();drag.saved=true;drag.before=history.at(-1);}
    if(drag.kind==='node'){
      const n=drag.node;
      if(interactionMode==='realtime'){
        // Rebuild each frame from one immutable gesture baseline. This keeps
        // route repair, port gates, shared stems and semantic checks identical
        // to a committed move while still exposing the new arrow direction.
        const candidate=E.clone(drag.before),origin=candidate.nodes.find(v=>v.id===n.id);
        const totalDx=Math.max(3-origin.x,Math.min(candidate.canvas[0]-3-origin.x-origin.w,p.x-drag.start.x));
        const totalDy=Math.max(3-origin.y,Math.min(candidate.canvas[1]-3-origin.y-origin.h,p.y-drag.start.y));
        E.move(candidate,n.id,totalDx,totalDy,options());
        if(candidate.lastMove?.blocked){
          graph.lastMove={blocked:true,reason:candidate.lastMove.reason||'位置无法保留合法连接'};
        }else{
          graph=candidate;
        }
      }else{
        const dx=p.x-drag.last.x,dy=p.y-drag.last.y;E.movePreview(graph,n.id,dx,dy);
      }
      drag.last=p;dirty=true;render({interactive:interactionMode!=='realtime'});
    }
    else if(drag.kind==='studio-annotation'){
      const P=window.ArchCanvasStudioPresentation,base=P.state(drag.before).annotations[drag.annotation],overlay=P.editable(graph);
      overlay.annotations[drag.annotation]={...base,x:base.x+p.x-drag.start.x,y:base.y+p.y-drag.start.y};
      drag.last=p;dirty=true;render({interactive:true,presentationOnly:true});
    }
    else if(drag.kind==='route-label'){E.snapRouteLabel(graph,drag.label,{x:p.x+drag.grab.x,y:p.y+drag.grab.y});drag.last=p;dirty=true;render({interactive:true});}
    else if(drag.kind==='bend'){const e=drag.edge,old=e.waypoints[drag.index],i=e.route.findIndex(v=>R.dist(v,old)<.01);e.waypoints[drag.index]={x:p.x,y:p.y};if(i>=0)e.route[i]={x:p.x,y:p.y};drag.last=p;dirty=true;render({interactive:true});}
    else{const a=drag.kind==='connection'?drag.origin:drag.edge.route[drag.side==='source'?0:drag.edge.route.length-1];$('previewLayer').replaceChildren(element('path',{d:`M ${a.x} ${a.y} L ${p.x} ${p.y}`,stroke:'#d77944',fill:'none','stroke-width':2/stageScale(),'stroke-dasharray':'5 5','pointer-events':'none'}));}
    const samples=drag.samples||(drag.samples=[]);samples.push(performance.now()-frameStart);const sorted=samples.slice().sort((a,b)=>a-b);svg.setAttribute('data-drag-profile',JSON.stringify({count:sorted.length,p50:+sorted[Math.floor((sorted.length-1)*.5)].toFixed(2),p95:+sorted[Math.floor((sorted.length-1)*.95)].toFixed(2),max:+sorted.at(-1).toFixed(2)}));
  }
  svg.addEventListener('pointermove',ev=>{if(!drag)return;const p=point(ev);
    if(drag.kind==='pan'){const dx=(ev.clientX-(drag.clientX??ev.clientX))/stageScale(),dy=(ev.clientY-(drag.clientY??ev.clientY))/stageScale();camera.x-=dx;camera.y-=dy;drag.clientX=ev.clientX;drag.clientY=ev.clientY;cameraUpdate();return;}
    dragPoint=p;if(dragFrame)return;dragFrame=requestAnimationFrame(()=>{dragFrame=0;const q=dragPoint;dragPoint=null;processDragPoint(q);});
  });
  svg.addEventListener('pointerup',async ev=>{if(!drag)return;const p=point(ev),n=hitNode(p),kind=drag.kind;
    if(dragFrame){cancelAnimationFrame(dragFrame);dragFrame=0;dragPoint=null;processDragPoint(p);}
    else if(drag.saved)processDragPoint(p);
    if(kind==='connection'){if(n)completeConnection(n,nearestSide(n,p));else{connection=null;toast('连接取消：请释放在目标节点或端口上。');}}
    else if(kind==='endpoint'){if(n){save();E.reconnect(graph,drag.edge,drag.side,n.id,nearestSide(n,p));dirty=true;toast('端点已重接；Apply 更新这条路径。');}else toast('端点未落在节点上，保留原连接。');}
    if(kind==='route-label'&&drag.saved)toast('文字已吸附到所属连线；拖动模块与重新布线时自动跟随。');
    if(drag.saved){
      if(unchangedGesture(drag)){
        restoreGesture(drag);drag=null;dragPoint=null;$('previewLayer').replaceChildren();if(svg.hasPointerCapture(ev.pointerId))svg.releasePointerCapture(ev.pointerId);
        render();studioBridge?.state();return;
      }
    }
    if(kind==='node'&&drag.saved&&interactionMode==='realtime'){
      const gesture=drag,base=gesture.before;
      const validation=E.validateView(graph);
      const valid=validation.source.ok&&validation.layout.ok&&validation.edges.every(([,check])=>check.ok);
      if(!valid){restoreGesture(gesture);toast('实时移动已恢复：最终位置未通过完整约束校验。');}
      else {F.captureMove(base,graph,gesture.node.id);toast(graph.lastMove?.blocked?'此位置无法保留合法连接，已停留在上一合法位置。':'实时更新已提交：节点、箭头、所属文字与连接同步保存。');}
      drag=null;dragPoint=null;$('previewLayer').replaceChildren();if(svg.hasPointerCapture(ev.pointerId))svg.releasePointerCapture(ev.pointerId);
      window.SummarySourceControls?.refresh(graph);render({validation:valid?validation:null,validationOrigin:'main'});persist();studioBridge?.state();return;
    }
    if(kind==='node'&&drag.saved){
      const gesture=drag,base=gesture.before,old=base.nodes.find(n=>n.id===gesture.node.id),moved=node(gesture.node.id),dx=moved.x-old.x,dy=moved.y-old.y;
      drag=null;dragPoint=null;$('previewLayer').replaceChildren();if(svg.hasPointerCapture(ev.pointerId))svg.releasePointerCapture(ev.pointerId);
      busy=true;render({interactive:true});svg.setAttribute('data-interaction-phase','settling');$('dirtyBadge').textContent='正在整理连线…';
      let validation=null;try{const start=performance.now(),result=await runGraphTask({task:'move',graph:base,id:old.id,dx,dy,options:options()});if(!result.ok)throw new Error(result.error);
        const committed=result.graph.nodes.find(n=>n.id===old.id);
        if(Math.abs(committed.x-old.x)<1e-5&&Math.abs(committed.y-old.y)<1e-5){restoreGesture(gesture);toast('此位置无法保留合法连接，已保留原位置。');}
        else {graph=result.graph;F.captureMove(base,graph,old.id);svg.setAttribute('data-move-ms',(performance.now()-start).toFixed(2));toast(graph.lastMove?.blocked?'此位置无法保留合法连接，已限制移动。':'节点、所属文字与连接已同步更新。');validation=result.validation;}
      }catch(error){restoreGesture(gesture);toast('移动已恢复：'+error.message);}finally{busy=false;render({validation});persist();studioBridge?.state();}return;
    }
    const changed=drag.saved||kind==='connection'||kind==='endpoint';drag=null;svg.classList.remove('is-panning');$('previewLayer').replaceChildren();if(svg.hasPointerCapture(ev.pointerId))svg.releasePointerCapture(ev.pointerId);if(changed&&(kind==='route-label'||kind==='studio-annotation'))window.SummarySourceControls?.refresh(graph);if(changed)persist();render({presentationOnly:!changed});studioBridge?.state();
  });
  svg.addEventListener('pointercancel',()=>{if(dragFrame)cancelAnimationFrame(dragFrame);dragFrame=0;dragPoint=null;if(drag?.saved)restoreGesture(drag);drag=null;svg.classList.remove('is-panning');connection=null;$('previewLayer').replaceChildren();render();studioBridge?.state();});
  svg.addEventListener('wheel',ev=>{if(!graph)return;ev.preventDefault();zoom(ev.deltaY<0?1.15:1/1.15,point(ev));},{passive:false});
  function ensureWorker(){if(worker||location.protocol==='file:'||typeof Worker==='undefined')return worker;
    try{worker=new Worker('routing-worker.js');worker.onmessage=event=>{const resolve=pendingTasks.get(event.data.requestId);if(resolve){pendingTasks.delete(event.data.requestId);resolve(event.data);}};
      worker.onerror=()=>{worker.terminate();worker=null;for(const resolve of pendingTasks.values())resolve(null);pendingTasks.clear();};
    }catch(_){worker=null;}return worker;
  }
  async function runGraphTask(message){const active=ensureWorker();if(active){const result=await new Promise(resolve=>{const requestId=++workerId;pendingTasks.set(requestId,resolve);try{active.postMessage({...message,requestId});}catch(_){pendingTasks.delete(requestId);resolve(null);}});if(result)return result;}
    await new Promise(resolve=>setTimeout(resolve,0));const copy=E.clone(message.graph);
    if(message.task==='frontier')return window.SummaryFrontierTask.run(copy,message.transition,message.options);
    if(message.task==='validate'){window.SummarySourceControls?.refresh(copy);return {ok:true,graph:copy,validation:E.validateView(copy)};}
    if(message.task==='move'){E.move(copy,message.id,message.dx,message.dy,message.options);const validation=E.validateView(copy);if(!validation.source.ok||!validation.layout.ok||validation.edges.some(([,check])=>!check.ok))return {ok:false,error:'移动后的图未通过完整校验'};window.SummarySourceControls?.refresh(copy);return{ok:true,graph:copy,validation};}
    const result=E.routeBatch(copy,message.ids,message.options);window.SummarySourceControls?.refresh(result.graph);return {ok:true,...result,validation:E.validateView(copy)};
  }
  async function runRouting(ids,opts){C.initialize(graph);return runGraphTask({task:'route',graph,ids,options:opts});}
  async function apply(){if(!graph||busy)return;restoreSourceBaseline();const sourceCheck=C.validateSource(graph);if(!sourceCheck.ok){render();toast('源码语义校验失败：'+sourceCheck.violations[0]);return;}let targets=$('scope').value==='all'?graph.edges:$('scope').value==='selected'?graph.edges.filter(e=>selectedEdges.has(e.id)):graph.edges.filter(e=>selectedNodes.has(e.source)||selectedNodes.has(e.target));
    if(!targets.length){toast('作用范围为空，请先选择节点或边。');return;}if($('policy').value==='never'){metrics={routed:0,time:0};render();toast('Never：保留当前路径。');return;}
    const opts=options();if($('policy').value==='needed')targets=targets.filter(e=>E.conflicts(graph,e,opts));if(!targets.length){metrics={routed:0,time:0};render();toast('当前路径满足约束，无需重算。');return;}
    save();ghost=graph.edges.map(e=>({route:E.clone(e.route),style:e.style}));busy=true;render({presentationOnly:true});const begin=performance.now(),before=JSON.stringify(graph.nodes.map(n=>[n.id,n.x,n.y]));let validation=null;
    try{const result=await runRouting(targets.map(e=>e.id),opts);if(!result.ok)throw new Error(result.error);graph=result.graph;validation=result.validation;if(before!==JSON.stringify(graph.nodes.map(n=>[n.id,n.x,n.y])))throw new Error('布线不应移动节点');metrics={routed:result.routed,time:Math.round(performance.now()-begin)};dirty=result.failed>0;toast(result.failed?`${result.routed} 条完成，${result.failed} 条约束冲突（红色），原路径保留。请检查容器接口、端口或安全距离。`:`${result.routed} 条边已布线${result.retained?' · '+result.retained+' 段原始合法通道/汇流骨架保留':''} · 节点位置不变`);}catch(error){toast(error.message);}finally{busy=false;render({validation});persist();}
  }
  function download(text,type,name){const url=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);}
  function exportSvg(){const out=svg.cloneNode(true);out.setAttribute('xmlns',NS);out.setAttribute('width',graph.canvas[0]);out.setAttribute('height',graph.canvas[1]);out.setAttribute('viewBox','0 0 '+graph.canvas.join(' '));out.removeAttribute('tabindex');out.querySelector('#previewLayer').remove();out.querySelector('#handleLayer').remove();out.querySelector('#obstacleLayer').remove();out.querySelector('#ghostLayer').remove();out.querySelectorAll('.wire-hit,.node-hit,.frame-hit,.expansion-control,[data-editor-only]').forEach(n=>n.remove());const style=element('style',{},'.wire-path{fill:none;stroke-linecap:butt;stroke-linejoin:round}.scene-node text{font-family:DejaVu Sans,Arial,sans-serif}');out.querySelector('defs').append(style);out.prepend(element('rect',{x:0,y:0,width:graph.canvas[0],height:graph.canvas[1],fill:'white'}));out.prepend(element('metadata',{'id':'summary-merge-binding'},JSON.stringify({case:current.id,view:view.key,interactionMode,source:graph.source,irSha256:graph.irSha256,edited:dirty,sourceDraftOperations:graph.sourceDraftOperations||[],sourceValidation:C.validateSource?.(graph),attachments:graph.attachments||[],routeLabels:graph.routeLabels||[],junctionMarkers:graph.junctionMarkers||[],nodes:graph.nodes.map(n=>({id:n.id,parent:n.parent,semantic:n.semantic,visualBinding:n.visualBinding,glyphPresentation:n.glyphPresentation,labelObstacles:n.glyphPresentation?n.labelObstacles:undefined})),edges:graph.edges.map(e=>({id:e.id,source:e.source,target:e.target,draft:e.draft,binding:e.binding,portPolicy:e.portPolicy,physicalSource:e.physicalSource,physicalTarget:e.physicalTarget}))})));download(new XMLSerializer().serializeToString(out),'image/svg+xml',current.title+'-'+view.key+'.svg');toast('已生成当前视图 SVG。');}
  for(const collection of Object.keys(names)){const o=document.createElement('option');o.value=collection;o.textContent=names[collection];$('collection').append(o);}
  $('coverage').textContent=`${catalog.counts.active} 当前案例 / ${catalog.counts.historical} 历史案例`;
  for(const id of ['search','collection','includeHistory'])$(id).addEventListener(id==='search'?'input':'change',renderCatalog);
  function selectTool(value){if(busy||drag)throw new Error('请先完成当前图操作。');if(!['select','connect','bend','pan'].includes(value)||(studioCanvas&&value==='pan'))throw new Error('该工具不可用；按住鼠标中键平移画布。');tool=value;connection=null;for(const x of document.querySelectorAll('[data-tool]'))x.classList.toggle('active',x.dataset.tool===tool);if(tool==='connect')$('showPorts').checked=true;svg.setAttribute('data-active-tool',tool);render({presentationOnly:true});studioBridge?.state();}
  for(const b of document.querySelectorAll('[data-tool]'))b.onclick=()=>{if(busy||drag)return;selectTool(b.dataset.tool);};
  $('interactionMode').onchange=()=>setInteractionMode($('interactionMode').value);
  for(const id of ['showGhost','showObstacles','showPorts'])$(id).onchange=()=>render({presentationOnly:true});
  $('clearance').oninput=()=>{$('clearanceValue').value=$('clearance').value+' px';};$('applyLayout').onclick=apply;
  $('setArrow').onclick=()=>{if(busy||drag)return;if(!selectedEdges.size){toast('先选择一条或多条边。');return;}save();for(const e of graph.edges)if(selectedEdges.has(e.id))e.arrow=$('arrowStyle').value;render();persist();toast('箭头已更新；路线模型保持不变。');};
  $('undo').onclick=()=>{if(busy||drag||!history.length)return;future.push(E.clone(graph));graph=history.pop();selectedNodes.clear();selectedEdges.clear();selectedAnnotation=null;connection=null;dirty=true;ghost=[];render();persist();studioBridge?.state();};
  $('redo').onclick=()=>{if(busy||drag||!future.length)return;history.push(E.clone(graph));graph=future.pop();selectedNodes.clear();selectedEdges.clear();selectedAnnotation=null;connection=null;dirty=true;ghost=[];render();persist();studioBridge?.state();};
  $('reset').onclick=()=>{if(busy||drag)return;save();graph=E.clone(original);syncUnifiedState();selectedNodes.clear();selectedEdges.clear();selectedAnnotation=null;connection=null;ghost=[];dirty=false;fit();render();persist();studioBridge?.state();toast('当前模型已恢复到最精简递归状态，仍可撤销。');};
  $('collapseAll').onclick=collapseUnifiedAll;$('expandAll').onclick=expandUnifiedAll;
  $('fit').onclick=()=>{fit();render({cameraOnly:true});};$('fitWidth').onclick=()=>{fit(true);render({cameraOnly:true});};$('zoomIn').onclick=()=>zoom(1.3);$('zoomOut').onclick=()=>zoom(1/1.3);$('exportSvg').onclick=()=>download(studioSvg(),'image/svg+xml',current.title+'-unified.svg');
  $('exportJson').onclick=()=>{const text=JSON.stringify({schema:'summary-merge-recursive/1',case:current.id,view:view.key,interactionMode,graph,...(importedPackages.has(current.id)?{adapter:importedPackages.get(current.id)}:{})},null,2);
    if(importedPackages.has(current.id)){$('sourceExportText').value=text;$('sourceExportDialog').showModal();}else download(text,'application/json',current.id+'-'+view.key+'.json');};
  $('closeSourceExport').onclick=()=>$('sourceExportDialog').close();$('downloadSourceDocument').onclick=()=>download($('sourceExportText').value,'application/json',current.id+'-unified.json');
  const invalidSourceRoutes=(graph,validation)=>validation.edges.some(([id,v])=>!v.ok&&!graph.edges.find(e=>e.id===id)?.draft);
  async function registerSource(bundle,edited){await A.verify(bundle);const sources=A.sources(bundle),preflight=await runGraphTask({task:'frontier',graph:F.build(F.create(sources)),options:{}});
    if(!preflight.ok||preflight.failed)throw new Error(preflight.error||'适配结果未通过连接/布局校验，请查看源码适配支持范围。');
    if(edited){const restored=E.clone(edited);if(!restored.recursive)throw new Error('编辑 JSON 缺少递归状态。');restored.recursive.authority=F.create(sources).authority;const check=await runGraphTask({task:'validate',graph:restored});if(!check.ok)throw new Error(check.error);const result=check.validation;
      if(restored.irSha256!==bundle.irSha256||!result.source.ok||!result.layout.ok||invalidSourceRoutes(restored,result))throw new Error('编辑 JSON 与源码适配契约不一致。');}
    importedPackages.set(bundle.id,bundle);importedSources.set(bundle.id,sources);let c=catalog.cases.find(v=>v.id===bundle.id);
    if(!c){c={id:bundle.id,title:bundle.title,collection:'source_adapter',origin:bundle.entry,historical:false,views:[{key:'overview',label:'递归图'},{key:'detailed',label:'源码细节'}]};catalog.cases.push(c);}return c;
  }
  async function installSource(payload){
    if(!payload||typeof payload!=='object')throw new Error('源码包格式无效。');
    if(busy||drag)throw new Error('请先完成当前操作。');flushPersist();busy=true;render({presentationOnly:true});studioBridge?.state();
    const bundle=payload.adapter||payload;let c,restored;
    try{
    c=await registerSource(bundle,payload.adapter&&payload.graph);
    // Restore a portable edited frontier only against fresh, verified authority.
    if(payload.adapter&&payload.graph){restored=E.clone(payload.graph);restored.recursive.authority=F.create(importedSources.get(c.id)).authority;}
    await window.SummaryRecursiveStorage.put('source-adapter:bundle:'+c.id,bundle);await window.SummaryRecursiveStorage.put('source-adapter:index',[...importedPackages.keys()]);
    }finally{busy=false;render({presentationOnly:true});studioBridge?.state();}
    $('collection').value='all';$('search').value='';$('sourceImportDialog').close();if(!await openCase(c,c.views[0],restored?{graph:restored,history:[],future:[],dirty:true}:undefined))throw new Error('源码包已验证，但递归视图加载失败。');toast(`已接入 ${c.title}：${bundle.ir.nodes.length} 个源码节点，${bundle.diagnostics.length} 个待解析区域。`);
  }
  const sourceError=error=>{$('sourceImportStatus').textContent=error.message;toast(error.message);};
  function applyStudioPresentation(n,v){window.ArchCanvasStudioPresentation?.applyNode(graph,n,v);}
  function studioDocument(){return graph&&current?{schema:'summary-merge-recursive/1',case:current.id,caseId:current.id,title:current.title,collection:current.collection,view:view.key,interactionMode,tool,showPorts:$('showPorts').checked,gridVisible:canvasGridVisible,dirty,busy:busy||!!drag,dragging:!!drag,canUndo:!!history.length,canRedo:!!future.length,undo:history.length,redo:future.length,presentationVersion:1,sourceAvailable:!!(importedPackages.has(current.id)||catalogSources?.cases?.[current.id]?.available),selectedNodes:[...selectedNodes],selectedEdges:[...selectedEdges],selection:studioSelection(),graph:E.clone(graph),...(importedPackages.has(current.id)?{adapter:E.clone(importedPackages.get(current.id))}:{})}:null;}
  function studioState(){const document=studioDocument();return {document,graph:document?.graph||null,case:current?{id:current.id,title:current.title,collection:current.collection,historical:!!current.historical}:null,bundle:document?.adapter||null,sourceAvailable:!!(document?.adapter||catalogSources?.cases?.[current?.id]?.available),dirty,tool,showPorts:$('showPorts').checked,gridVisible:canvasGridVisible,busy:busy||!!drag,dragging:!!drag,undo:history.length,redo:future.length,selectedNodes:[...selectedNodes],selectedEdges:[...selectedEdges],presentationVersion:1,selection:studioSelection(),camera:{...camera}};}
  async function sourceAsset(path,json=false){
    const cacheKey=path+':'+json;if(sourceAssets.has(cacheKey))return sourceAssets.get(cacheKey);
    if(typeof path!=='string'||path.startsWith('/')||path.split('/').includes('..'))throw new Error('源码资源路径无效。');
    const response=await fetch('../'+path);if(!response.ok)throw new Error('无法读取源码资料：'+path);
    const value=json?await response.json():await response.text();sourceAssets.set(cacheKey,value);return value;
  }
  function caseEvidence(){const bundle=importedPackages.get(current?.id);if(bundle)return bundle.evidence;const path=catalogSources?.cases?.[current?.id]?.evidence;return path?sourceAssets.get(path+':true')||{}:{};}
  function nodeEvidence(n){
    if(!n)return[];const evidence=caseEvidence(),ids=n.semantic?.source_evidence||[],symbols=evidence.symbols||{};
    const matches=ids.flatMap(id=>evidence[id]?[evidence[id]]:symbols[id]?[symbols[id]]:Object.values(symbols).filter(e=>e.evidence_id===id));
    if(!matches.length){const references=n.semantic?.source||[];for(const [key,e]of Object.entries(symbols))if(references.some(ref=>ref===key||ref.endsWith('::'+key)||ref.endsWith('::'+e.symbol)))matches.push(e);}
    return matches;
  }
  function normalizeSourcePath(value){
    if(!value)return null;const files=importedPackages.get(current?.id)?.files||catalogSources?.cases?.[current?.id]?.files||[];
    const aliases=f=>[f.path,f.originalPath].filter(Boolean);
    const exact=files.find(f=>aliases(f).includes(value));
    const suffix=files.filter(f=>aliases(f).some(path=>value.endsWith('/'+path)));
    const basename=files.filter(f=>aliases(f).some(path=>value.endsWith('/'+path.split('/').at(-1))));
    const match=exact||(suffix.length===1?suffix[0]:null)||(basename.length===1?basename[0]:null);
    return match?.path||value.replace(/^.*\/prototype\//,'');
  }
  function studioSelection(){
    const annotation=!graph||selectedNodes.size||selectedEdges.size?null:window.ArchCanvasStudioPresentation?.state(graph).annotations[selectedAnnotation];
    const n=selectedNodes.size===1?node([...selectedNodes][0]):null,e=selectedEdges.size===1?graph?.edges.find(e=>selectedEdges.has(e.id)):null,evidence=nodeEvidence(n),first=evidence[0];
    const path=normalizeSourcePath(first?.file||first?.path||first?.source||(n?.semantic?.source?.[0]?.split('::')[0]));
    const line=first?.line||first?.start,endLine=first?.endLine||first?.end||line;
    return {caseId:current?.id||null,nodeId:n?.id||null,annotationId:annotation?.id||null,annotation:annotation?E.clone(annotation):null,node:n?{id:n.id,label:label(n),parent:n.parent,semantic:E.clone(n.semantic||{}),x:n.x,y:n.y,w:n.w,h:n.h,expanded:!!n.expanded}:null,edge:e?{id:e.id,source:e.source,target:e.target,binding:E.clone(e.binding||{}),arrow:e.arrow,style:e.style,width:e.width,stroke:e.stroke,dashed:e.dashed}:null,nodeIds:[...selectedNodes],edgeIds:[...selectedEdges],selectedNodes:[...selectedNodes],selectedEdges:[...selectedEdges],sourcePath:path,line:line||null,span:line?{startLine:line,endLine,startColumn:first?.column||0,column:first?.column||0,endColumn:first?.endColumn||0,line,expression:first?.expression||first?.snippet}:null,evidence:E.clone(evidence)};
  }
  function normalizedEntry(value){if(typeof value!=='string')return null;if(!value.includes('::'))return value;const [file,symbol]=value.split('::');return file.replace(/(?:\/__init__)?\.py$/,'').replaceAll('/','.')+':'+symbol.split('.')[0];}
  function normalizedEvidence(raw){const result={};for(const [id,e]of Object.entries(raw.symbols||raw)){if(!e||typeof e!=='object'||!Number.isFinite(e.line||e.start))continue;const file=normalizeSourcePath(e.file||e.path||e.source||raw.origin);if(!file)continue;const entry={file,line:e.line||e.start,endLine:e.endLine||e.end||e.line||e.start,expression:e.expression||e.snippet||'',column:e.column||0,endColumn:e.endColumn||0};result[e.evidence_id||id]=entry;}return result;}
  async function studioSource(){
    const caseId=current?.id;if(!caseId)return {message:'尚未加载模型。'};const document=studioDocument(),bundle=importedPackages.get(caseId);
    if(bundle)return {bundle:E.clone(bundle),source:{schema:'archcanvas-preview-source/1',caseId,title:bundle.title,entry:bundle.entry,files:Object.fromEntries(bundle.files.map(f=>[f.path,f.text])),evidence:E.clone(bundle.evidence),profile:E.clone(bundle.ir.profile||{}),sourceSha256:bundle.sourceSha256},document};
    const descriptor=catalogSources?.cases?.[caseId];if(!descriptor?.available)return {message:'当前案例为路由实验或教学 SVG，没有绑定可编辑的模型源码。'};
    const files=Object.create(null);
    for(const file of descriptor.files){const content=await sourceAsset(file.asset),hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(content)))).map(b=>b.toString(16).padStart(2,'0')).join('');if(hash!==file.sha256)throw new Error('案例源码 SHA256 校验失败：'+file.path);files[file.path]=content;}
    if(current?.id!==caseId)throw new Error('模型已切换，请重新打开编辑。');
    return {source:{schema:'archcanvas-preview-source/1',caseId,title:descriptor.title,entry:normalizedEntry(descriptor.entry),files,evidence:normalizedEvidence(descriptor.evidence?await sourceAsset(descriptor.evidence,true):{}),profile:descriptor.profile||{}},document};
  }
  async function studioLoad(payload){
    if(payload?.schema!=='summary-merge-recursive/1'||payload.adapter)return installSource(payload);
    if(busy||drag)throw new Error('请先完成当前图操作。');const c=catalog.cases.find(c=>c.id===(payload.caseId||payload.case));if(!c||!payload.graph?.recursive)throw new Error('编辑 JSON 没有对应的案例或递归状态。');
    flushPersist();busy=true;render({presentationOnly:true});studioBridge?.state();let restored;
    try{
      const sources=await caseSources(c,!!c.views[0]?.builtin),base=F.build(F.create(sources));restored=E.clone(payload.graph);restored.recursive.authority=E.clone(base.recursive.authority);const checked=await runGraphTask({task:'validate',graph:restored});if(!checked.ok)throw new Error(checked.error);const validation=checked.validation;
      if(restored.irSha256!==base.irSha256||!validation.source.ok||!validation.layout.ok||invalidSourceRoutes(restored,validation))throw new Error('编辑 JSON 与当前案例的源码契约不一致。');
    }finally{busy=false;render({presentationOnly:true});studioBridge?.state();}
    if(!await openCase(c,c.views[0],{graph:restored,history:[],future:[],dirty:!!payload.dirty}))throw new Error('编辑 JSON 的递归视图加载失败。');
  }
  function sourceNodes(message){
    const all=graph?.recursive?.authority?.detail?.nodes||graph?.nodes||[];
    if(message.nodeId){const exact=all.filter(n=>n.id===message.nodeId);if(exact.length)return exact;}
    const locations=message.locations||message.sourceLocations||message.source_locations||[message];
    return all.filter(n=>locations.some(location=>{
      const path=location.sourcePath||location.file||location.path,line=location.line||location.startLine;
      if(!path&&!line)return false;
      return nodeEvidence(n).some(e=>{const p=normalizeSourcePath(e.file||e.path||e.source);const start=e.line||e.start,end=e.endLine||e.end||start;return (!path||p===path||p?.endsWith('/'+path)||path.endsWith('/'+p))&&(!line||line>=start&&line<=end);})||n.semantic?.source?.some(ref=>path&&ref.split('::')[0].endsWith(path));
    }));
  }
  async function studioFocus(message){
    if(!graph||busy||drag)throw new Error('请先完成当前图操作。');
    if(message.annotationId){
      const annotation=window.ArchCanvasStudioPresentation.state(graph).annotations[message.annotationId];if(!annotation)throw new Error('当前预览没有匹配的说明文字。');
      selectedNodes.clear();selectedEdges.clear();selectedAnnotation=null;selectedAnnotation=annotation.id;
      camera.x=annotation.x+(annotation.width||380)/2-camera.w/2;camera.y=annotation.y-camera.h/2;cameraUpdate();render({presentationOnly:true});studioBridge?.state();return;
    }
    const target=sourceNodes(message)[0];if(!target)throw new Error('当前预览没有匹配的源码图元。');selectedAnnotation=null;
    if(!node(target.id)){const all=graph.recursive.authority.detail.nodes,ancestors=[];let item=target;while(item.parent){item=all.find(n=>n.id===item.parent);if(!item)break;ancestors.unshift(item.id);}await changeFrontier({type:'expand',ids:ancestors,expanded:true});}
    const visible=node(target.id);if(!visible)throw new Error('图元尚未显示。');selectedNodes=new Set([target.id]);selectedEdges.clear();camera.x=visible.x+visible.w/2-camera.w/2;camera.y=visible.y+visible.h/2-camera.h/2;cameraUpdate();render({presentationOnly:true});studioBridge?.state();
  }
  function selectedLayoutNodes(){
    if(!graph||busy||drag)throw new Error('请先完成当前图操作。');
    const nodes=[...selectedNodes].map(id=>node(id));
    if(!nodes.length)throw new Error('请先选择画布节点；按住 Shift 点击可多选。');
    if(nodes.some(n=>!n||n.junction))throw new Error('请只选择可见模块或图元；分支连接点不能排列或固定。');
    return nodes;
  }
  async function pinSelection(message){
    const nodes=selectedLayoutNodes(),overlay=window.ArchCanvasStudioPresentation.state(graph);
    if(message.pinned!==undefined&&typeof message.pinned!=='boolean')throw new Error('固定状态必须为布尔值。');
    const pinned=message.pinned??!nodes.every(n=>overlay.nodes[n.id]?.pinned);
    const ids=nodes.filter(n=>!!overlay.nodes[n.id]?.pinned!==pinned).map(n=>n.id);
    if(!ids.length){toast(pinned?'所选节点已固定直接移动。':'所选节点已解锁。');return;}
    await studioVisual({operations:[{type:'pin',ids,pinned}]});
    toast(pinned?'已固定所选节点的直接移动；子节点仍随父容器移动与递归布局更新。':'已解锁所选节点，可拖动或排列。');
  }
  async function arrangeSelection(message){
    const kinds=['left','hcenter','right','top','vcenter','bottom','distribute-x','distribute-y'],kind=message.kind;
    if(!kinds.includes(kind))throw new Error('未知排列方式。');
    const nodes=selectedLayoutNodes(),distribution=kind.startsWith('distribute-'),minimum=distribution?3:2;
    if(nodes.length<minimum)throw new Error(distribution?'等距分布需要至少 3 个同级节点。':'对齐需要至少 2 个同级节点。');
    if(new Set(nodes.map(n=>n.parent||null)).size!==1)throw new Error('请选择同一容器内的独立节点；父子节点和跨容器节点不能一起排列。');
    const overlay=window.ArchCanvasStudioPresentation.state(graph),anchors=nodes.filter(n=>overlay.nodes[n.id]?.pinned),horizontal=['left','hcenter','right','distribute-x'].includes(kind),axis=horizontal?'x':'y',size=horizontal?'w':'h',epsilon=1e-5;
    const targets=new Map();
    if(distribution){
      if(anchors.length)throw new Error('等距分布前请解锁所选固定节点。');
      const ordered=nodes.slice().sort((a,b)=>a[axis]-b[axis]||a.id.localeCompare(b.id)),first=ordered[0],last=ordered.at(-1),total=ordered.reduce((sum,n)=>sum+n[size],0),gap=(last[axis]+last[size]-first[axis]-total)/(ordered.length-1);
      if(gap<-epsilon)throw new Error('所选节点之间空间不足，无法保持不重叠的等距分布。');
      let position=first[axis];for(const n of ordered){targets.set(n.id,position);position+=n[size]+Math.max(0,gap);}
    }else{
      const fraction=['hcenter','vcenter'].includes(kind) ? .5 : ['right','bottom'].includes(kind) ? 1 : 0,coordinate=n=>n[axis]+n[size]*fraction;
      if(anchors.length>1&&anchors.some(n=>Math.abs(coordinate(n)-coordinate(anchors[0]))>epsilon))throw new Error('固定节点的对齐基准不同；请解锁部分节点后再排列。');
      const low=Math.min(...nodes.map(n=>n[axis])),high=Math.max(...nodes.map(n=>n[axis]+n[size])),reference=anchors.length?coordinate(anchors[0]):fraction===0?low:fraction===1?high:(low+high)/2;
      for(const n of nodes)if(!anchors.includes(n))targets.set(n.id,reference-n[size]*fraction);
    }
    const moving=nodes.filter(n=>targets.has(n.id)&&Math.abs(targets.get(n.id)-n[axis])>epsilon);
    if(!moving.length){toast('所选节点已满足排列，无需调整。');return;}
    const extent=graph.canvas[horizontal?0:1];
    if(moving.some(n=>{const position=targets.get(n.id),low=position+Math.min(0,...(n.labelObstacles||[]).map(b=>b[axis])),high=position+Math.max(n[size],...(n.labelObstacles||[]).map(b=>b[axis]+b[size]));return low<-epsilon||high>extent+epsilon;}))throw new Error('排列会使图元或所属文字超出画布，请调整基准节点位置。');
    // Vacate positions towards the outer edge first. The original engine then
    // validates each move and the complete candidate as one atomic history step.
    moving.sort((a,b)=>{
      const negativeA=targets.get(a.id)<a[axis],negativeB=targets.get(b.id)<b[axis];
      if(negativeA!==negativeB)return negativeA?-1:1;
      return (negativeA?1:-1)*(a[axis]-b[axis])||a.id.localeCompare(b.id);
    });
    if(message.scope!==undefined&&!['current-frontier','all-frontiers'].includes(message.scope))throw new Error('移动范围无效。');
    await studioVisual({operations:moving.map(n=>({type:'nodeLayout',id:n.id,position:{[axis]:targets.get(n.id)},scope:message.scope||'all-frontiers',exact:true}))});
    toast(distribution?'已按节点间距等距分布；模型连接与源码保持绑定。':'已对齐所选节点；固定节点作为基准，模型连接与源码保持绑定。');
  }
  async function studioVisual(message){
    if(!graph||busy||drag)throw new Error('请先完成当前图操作。');if(!Array.isArray(message.operations)||!message.operations.length||message.operations.length>200)throw new Error('视觉操作清单无效。');
    if(message.operations.every(op=>op.type==='expand'&&op.expanded===message.operations[0].expanded)){
      for(const operation of message.operations)if(!graph.recursive.authority.detail.nodes.some(n=>n.id===operation.id))throw new Error('找不到预览图元：'+operation.id);
      return changeFrontier({type:'expand',ids:message.operations.map(op=>op.id),expanded:!!message.operations[0].expanded},true);
    }
    const before=E.clone(graph);let candidate=E.clone(graph),geometry=false;const P=window.ArchCanvasStudioPresentation,portOverrides={};
    for(const operation of message.operations){
      const all=candidate.recursive.authority.detail.nodes,n=all.find(n=>n.id===operation.id),visible=candidate.nodes.find(n=>n.id===operation.id),p=P.editable(candidate);
      if(['alias','nodeStyle','nodeLayout','expand'].includes(operation.type)&&!n)throw new Error('找不到预览图元：'+operation.id);
      if(operation.type==='title'){if(typeof operation.title!=='string'||operation.title.length>500)throw new Error('图标题无效。');p.title=operation.title;}
      else if(operation.type==='syncPresentation'){
        for(const [id,desired]of Object.entries(operation.nodes||{})){
          if(!all.some(n=>n.id===id)||!desired||typeof desired!=='object')throw new Error('同步的图元身份无效：'+id);
          const retained={...(p.nodes[id]||{})};for(const key of ['alias','fill','stroke','glyph','pinned'])delete retained[key];
          for(const color of ['fill','stroke'])if(desired[color]!==undefined&&!P.color(desired[color]))throw new Error('同步的颜色值无效。');
          if(desired.alias!==undefined&&(typeof desired.alias!=='string'||desired.alias.length>500))throw new Error('同步的显示名称无效。');
          p.nodes[id]={...retained,...E.clone(desired)};
        }
        for(const [id,desired]of Object.entries(operation.edges||{})){
          const edge=candidate.edges.find(e=>e.id===id);if(!edge||!desired||typeof desired!=='object')throw new Error('同步的连接身份无效：'+id);
          if(edge.draft)continue;
          if(desired.stroke!==undefined&&!P.color(desired.stroke)||desired.width!==undefined&&(!Number.isFinite(desired.width)||desired.width<.5||desired.width>12))throw new Error('同步的连接样式无效。');
          const original=all&&candidate.recursive.authority.detail.edges.find(e=>e.id===(edge.projection?.original||id));
          for(const key of ['stroke','width','dashed']){if(original?.[key]!==undefined)edge[key]=E.clone(original[key]);else delete edge[key];if(desired[key]!==undefined)edge[key]=desired[key];}
          for(const overlayId of new Set([edge.id,edge.projection?.original].filter(Boolean))){const retained={...(p.edges[overlayId]||{})};for(const key of ['stroke','width','dashed'])delete retained[key];p.edges[overlayId]={...retained,...E.clone(desired)};}
        }
        if(operation.title!==undefined){if(typeof operation.title!=='string'||operation.title.length>500)throw new Error('同步的图标题无效。');p.title=operation.title;}
        if(operation.legend!==undefined){if(!Array.isArray(operation.legend)||operation.legend.length>80)throw new Error('同步的图例清单无效。');p.legend=E.clone(operation.legend);}
        if(operation.annotations!==undefined){if(!Array.isArray(operation.annotations)||operation.annotations.length>1000)throw new Error('同步的说明清单无效。');const annotations={};for(const a of operation.annotations){if(!a||typeof a.id!=='string'||typeof a.text!=='string'||a.text.length>10000||![a.x,a.y,a.width||380].every(Number.isFinite))throw new Error('同步的说明文字无效。');annotations[a.id]=E.clone(a);}p.annotations=annotations;}
        if(operation.page!==undefined){if(!operation.page||typeof operation.page!=='object'||operation.page.background!==undefined&&!P.color(operation.page.background))throw new Error('同步的页面样式无效。');p.page=E.clone(operation.page);}
      }
      else if(operation.type==='alias'){if(typeof operation.label!=='string'||operation.label.length>500)throw new Error('显示名称无效。');p.nodes[n.id]={...p.nodes[n.id],alias:operation.label};}
      else if(operation.type==='nodeStyle'){const style=operation.style||{};for(const c of ['fill','stroke'])if(style[c]!==undefined&&!P.color(style[c]))throw new Error('颜色值无效。');p.nodes[n.id]={...p.nodes[n.id],...style};}
      else if(operation.type==='expand'){candidate=F.toggle(candidate,n.id,!!operation.expanded)||candidate;geometry=true;}
      else if(operation.type==='pin'){for(const id of operation.ids||[]){if(!all.some(n=>n.id===id))throw new Error('找不到预览图元：'+id);p.nodes[id]={...p.nodes[id],pinned:!!operation.pinned};}}
      else if(operation.type==='nodeLayout'){
        if(!visible)throw new Error('请先展开并显示要调整的图元。');const position=operation.position||{};
        if(p.nodes[n.id]?.pinned)throw new Error('图元已固定，请先解锁。');
        if(position.x!==undefined||position.y!==undefined){const dx=position.x===undefined?0:position.x-visible.x,dy=position.y===undefined?0:position.y-visible.y;if(!Number.isFinite(dx)||!Number.isFinite(dy))throw new Error('坐标无效。');const prior=E.clone(candidate);E.move(candidate,n.id,dx,dy,options());if(candidate.lastMove?.blocked)throw new Error('位置受到节点、容器或连接约束。');if(operation.exact&&(position.x!==undefined&&Math.abs(visible.x-position.x)>1e-5||position.y!==undefined&&Math.abs(visible.y-position.y)>1e-5))throw new Error('容器边界限制了位置，排列未提交。');if(operation.scope!=='current-frontier')F.captureMove(prior,candidate,n.id);}
        for(const [field,key]of [['width','w'],['height','h']])if(position[field]!==undefined){const value=position[field];if(!Number.isFinite(value)||value<32||value>10000)throw new Error('图元尺寸无效。');if(visible.glyphPresentation&&value!==visible[key])throw new Error('源码运算符图元的尺寸受语义契约保护。');visible[key]=value;p.nodes[n.id]={...p.nodes[n.id],[field]:value};}
        geometry=true;
      }else if(operation.type==='move'){
        if(!Number.isFinite(operation.dx)||!Number.isFinite(operation.dy))throw new Error('位移无效。');
        const ids=operation.ids||[];for(const id of ids){if(!candidate.nodes.some(n=>n.id===id))throw new Error('要移动的图元不可见：'+id);if(p.nodes[id]?.pinned)throw new Error('图元已固定，请先解锁。');}
        const roots=ids.filter(id=>{let parent=candidate.nodes.find(n=>n.id===id)?.parent;while(parent){if(ids.includes(parent))return false;parent=candidate.nodes.find(n=>n.id===parent)?.parent;}return true;});
        for(const id of roots){const prior=E.clone(candidate);E.move(candidate,id,operation.dx,operation.dy,options());if(candidate.lastMove?.blocked)throw new Error('位置受到节点、容器或连接约束。');if(operation.scope!=='current-frontier')F.captureMove(prior,candidate,id);}geometry=true;
      }else if(operation.type==='portLayout'){
        const owner=candidate.nodes.find(n=>n.id===operation.ownerId)||candidate.nodes.find(n=>n.id===operation.nodeId);if(!owner)throw new Error('连接点的所属图元当前不可见。');
        const endpointMatches=(edge,side)=>{
          if(edge[side]!==owner.id)return false;
          const semanticNode=edge.projection?.[side]||edge[side];if(operation.nodeId&&operation.nodeId!==owner.id&&semanticNode!==operation.nodeId)return false;
          const role=edge.role||edge.binding?.semantic_kind;if(operation.role&&operation.role!=='data'&&!String(role||'').includes(operation.role))return false;
          return true;
        };
        const endpoints=candidate.edges.flatMap(edge=>['source','target'].filter(side=>endpointMatches(edge,side)).map(side=>({edge,side})));
        if(!endpoints.length)throw new Error('图元没有可调整的当前连接点。');
        for(const {edge,side}of endpoints){
          const field=side==='source'?'physicalSource':'physicalTarget';
          if(operation.layout===null){delete edge[field];}
          else{
            const layout=operation.layout;if(!layout||!['top','right','bottom','left'].includes(layout.side)||!Number.isFinite(layout.offset)||layout.offset<0||layout.offset>1)throw new Error('连接点位置无效。');
            const original=edge[side==='source'?'fixedSource':'fixedTarget'],physical={side:layout.side,fraction:layout.offset,...(original?.inward!==undefined?{inward:original.inward}:{})};
            if(!window.SummaryPhysicalPorts.permitted(candidate,edge,side,physical))throw new Error('请求的连接点违反原图接口或端口间距；请用预览中的端口控制点逐条调整。');
            edge[field]=physical;portOverrides[edge.id]={...portOverrides[edge.id],[side]:physical};
          }
          edge.needsRecursiveRouting=true;
        }geometry=true;
      }else if(operation.type==='edgeStyle'){
        const edge=candidate.edges.find(e=>e.id===operation.id);if(!edge)throw new Error('找不到当前预览连接：'+operation.id);const style=operation.style||{};if(style.stroke!==undefined&&!P.color(style.stroke))throw new Error('连接颜色无效。');if(style.width!==undefined&&(!Number.isFinite(style.width)||style.width<.5||style.width>12))throw new Error('连接线宽无效。');p.edges[edge.id]={...p.edges[edge.id],...style};if(edge.projection?.original)p.edges[edge.projection.original]={...p.edges[edge.projection.original],...style};for(const k of ['stroke','width','dashed','style','arrow'])if(style[k]!==undefined)edge[k]=style[k];
      }else if(operation.type==='legend'){if(!Array.isArray(operation.items)||operation.items.length>80)throw new Error('图例清单无效。');p.legend=E.clone(operation.items);}
      else if(operation.type==='annotation'){const a=operation.annotation;if(!a||typeof a.id!=='string'||typeof a.text!=='string'||a.text.length>10000||![a.x,a.y,a.width||380].every(Number.isFinite))throw new Error('说明文字无效。');p.annotations[a.id]=E.clone(a);}
      else if(operation.type==='removeAnnotation')delete p.annotations[operation.id];
      else if(operation.type==='page'){const page=operation.page||{};if(page.background!==undefined&&!P.color(page.background))throw new Error('页面颜色无效。');p.page={...p.page,...page};}
      else throw new Error('不支持的视觉操作：'+operation.type);
    }
    busy=true;studioBridge?.state();let validation=null,committed=false;
    try{
      if(geometry){const result=await runGraphTask({task:'frontier',graph:candidate,options:{...options(),portOverrides}});if(!result.ok)throw new Error(result.error||'图元布局未通过完整校验。');candidate=result.graph;validation=result.validation;}
      validation=validation||E.validateView(candidate);const invalidEdges=validation.edges.filter(([id,v])=>!v.ok&&(geometry||!candidate.edges.find(e=>e.id===id)?.draft));if(!validation.source.ok||!validation.layout.ok||invalidEdges.length)throw new Error([...validation.source.violations,...validation.layout.violations,...invalidEdges.map(([id])=>'连接无效 '+id)].slice(0,4).join('; '));
      if(!geometry)window.SummarySourceControls?.refresh(candidate);
      history.push(before);if(history.length>30)history.shift();future=[];graph=candidate;dirty=true;syncUnifiedState();committed=true;
    }finally{busy=false;render(committed?{validation}:{presentationOnly:true});if(committed)persist();studioBridge?.state();}
  }
  function studioSvg(message={}){
    if(!graph||busy||drag)throw new Error('请先完成当前图操作。');const out=svg.cloneNode(true),p=window.ArchCanvasStudioPresentation.state(graph);out.setAttribute('xmlns',NS);out.setAttribute('width',graph.canvas[0]);out.setAttribute('height',graph.canvas[1]);out.setAttribute('viewBox','0 0 '+graph.canvas.join(' '));out.removeAttribute('tabindex');
    const originals=[svg,...svg.querySelectorAll('*')],clones=[out,...out.querySelectorAll('*')],properties=['fill','fill-opacity','fill-rule','stroke','stroke-width','stroke-opacity','stroke-dasharray','stroke-dashoffset','stroke-linecap','stroke-linejoin','stroke-miterlimit','font-family','font-size','font-weight','font-style','text-anchor','dominant-baseline','letter-spacing','opacity','visibility','display'];
    const portableColor=value=>value.replace(/rgba?\(\s*(\d+)[, ]+\s*(\d+)[, ]+\s*(\d+)\s*(?:[,/]\s*([\d.]+))?\s*\)/g,(_,r,g,b,alpha)=>'#'+[r,g,b,...(alpha!==undefined?[Math.round(+alpha*255)]:[])].map(v=>Math.max(0,Math.min(255,+v)).toString(16).padStart(2,'0')).join(''));
    originals.forEach((original,index)=>{const clone=clones[index],computed=getComputedStyle(original);for(const property of properties){let value=computed.getPropertyValue(property);if(property==='font-family')value='Noto Sans CJK SC, DejaVu Sans, Arial, sans-serif';if(['stroke-width','font-size','letter-spacing','stroke-dashoffset'].includes(property))value=value==='normal'?'0':value.replace(/px$/,'');if(property==='stroke-dasharray')value=value.replaceAll('px','');if(value)clone.setAttribute(property,portableColor(value));}clone.removeAttribute('style');});
    for(const id of ['previewLayer','handleLayer','obstacleLayer','ghostLayer'])out.querySelector('#'+id)?.remove();out.querySelectorAll('.wire-hit,.node-hit,.frame-hit,.expansion-control,[data-editor-only]').forEach(n=>n.remove());
    let bounds={x:0,y:0,w:graph.canvas[0],h:graph.canvas[1]};
    if(message.nodeId){
      const selected=node(message.nodeId);if(!selected)throw new Error('导出图元当前不可见。');const ids=new Set([selected.id]);let changed=true;while(changed){changed=false;for(const n of graph.nodes)if(ids.has(n.parent)&&!ids.has(n.id)){ids.add(n.id);changed=true;}}
      for(const group of out.querySelectorAll('[data-node-id]'))if(!ids.has(group.getAttribute('data-node-id')))group.remove();
      const edges=new Set(graph.edges.filter(e=>ids.has(e.source)&&ids.has(e.target)).map(e=>e.id));for(const group of out.querySelectorAll('[data-edge-id]'))if(!edges.has(group.getAttribute('data-edge-id')))group.remove();
      for(const group of out.querySelectorAll('[data-follow-owner]'))if(!ids.has(group.getAttribute('data-follow-owner')))group.remove();for(const group of out.querySelectorAll('[data-follow-edge]'))if(!edges.has(group.getAttribute('data-follow-edge')))group.remove();
      for(const group of out.querySelectorAll('[data-source-control-owner]'))if(!ids.has(group.getAttribute('data-source-control-owner'))||group.hasAttribute('data-source-control-target')&&!ids.has(group.getAttribute('data-source-control-target')))group.remove();
      out.querySelector('#studioPresentationLayer')?.remove();
      const regions=graph.nodes.filter(n=>ids.has(n.id)).flatMap(n=>[{x:n.x,y:n.y,w:n.w,h:n.h},...(n.labelObstacles||[]).map(b=>({x:n.x+b.x,y:n.y+b.y,w:b.w,h:b.h}))]);const x=Math.min(...regions.map(n=>n.x))-24,y=Math.min(...regions.map(n=>n.y))-24,w=Math.max(...regions.map(n=>n.x+n.w))-x+24,h=Math.max(...regions.map(n=>n.y+n.h))-y+24;bounds={x,y,w,h};out.setAttribute('width',w);out.setAttribute('height',h);out.setAttribute('viewBox',`${x} ${y} ${w} ${h}`);
    }
    out.prepend(element('rect',{x:bounds.x,y:bounds.y,width:bounds.w,height:bounds.h,fill:p.page.background||'#ffffff'}));out.prepend(element('metadata',{id:'archcanvas-preview-document'},JSON.stringify({schema:'summary-merge-recursive/1',case:current.id,view:view.key,selection:message.nodeId||null,interactionMode,source:graph.source,irSha256:graph.irSha256,edited:dirty,presentation:p,sourceDraftOperations:graph.sourceDraftOperations||[],sourceValidation:C.validateSource(graph),attachments:graph.attachments||[],routeLabels:graph.routeLabels||[],junctionMarkers:graph.junctionMarkers||[],nodes:graph.nodes.map(n=>({id:n.id,parent:n.parent,semantic:n.semantic,visualBinding:n.visualBinding,glyphPresentation:n.glyphPresentation})),edges:graph.edges.map(e=>({id:e.id,source:e.source,target:e.target,draft:e.draft,binding:e.binding,portPolicy:e.portPolicy,physicalSource:e.physicalSource,physicalTarget:e.physicalTarget}))})));return new XMLSerializer().serializeToString(out);
  }
  async function studioCommand(command,message){
    if(command==='visual'||command==='presentation')return studioVisual(message.operations?message:{operations:[{type:'nodeStyle',id:message.nodeId,style:message.style||message.presentation||{}}]});
    if(command==='set-frontier'){const nodes=sourceNodes(message);if(!nodes.length)throw new Error('没有匹配的源码模块。');return studioVisual({operations:nodes.filter(n=>F.children(graph.recursive.authority,n.id).length).map(n=>({type:'expand',id:n.id,expanded:!!message.expanded}))});}
    if(command==='show-library'||command==='show-routing'){document.documentElement.classList.remove('studio-library-open','studio-routing-open');document.documentElement.classList.add(command==='show-library'?'studio-library-open':'studio-routing-open');return;}
    if(command==='show-import')return $('showSourceImport').click();if(command==='show-evidence')return $('showEvidence').click();
    if(command==='undo'||command==='redo'||command==='reset'){if(busy||drag)throw new Error('请先完成当前图操作。');$(command).click();return;}
    if(command==='fit'){$('fit').click();return;}if(command==='zoom'){zoom(message.factor||1.3);return;}
    if(['select-tool','connect-tool','pan-tool','bend-tool'].includes(command)){selectTool(command.replace('-tool',''));return;}
    if(command==='show-ports'){$('showPorts').checked=message.visible??message.enabled??!$('showPorts').checked;render({presentationOnly:true});return;}
    if(command==='grid'){canvasGridVisible=message.visible??message.enabled??!canvasGridVisible;$('stage').style.backgroundImage=canvasGridVisible?'':'none';return;}
    if(command==='arrange-selection')return arrangeSelection(message);if(command==='pin-selection')return pinSelection(message);
    if(command==='apply-layout')return apply();if(command==='collapse-all'||command==='expand-all'){if(busy||drag)throw new Error('请先完成当前图操作。');return changeFrontier({type:'all',expanded:command==='expand-all'},true);}
    throw new Error('不支持的预览命令：'+command);
  }
  $('showSourceImport').onclick=()=>$('sourceImportDialog').showModal();$('closeSourceImport').onclick=()=>$('sourceImportDialog').close();
  const resetSourceDiscovery=()=>{$('sourceCandidateField').hidden=true;$('sourceHierarchy').hidden=true;$('sourceDiscoveryStatus').textContent='';};
  $('sourceFiles').onchange=()=>{$('sourceDirectory').value='';resetSourceDiscovery();};$('sourceDirectory').onchange=()=>{$('sourceFiles').value='';resetSourceDiscovery();};
  async function selectedSourceFiles(){
    const directory=$('sourceDirectory').files.length>0,chosen=directory?[...$('sourceDirectory').files].filter(f=>f.name.endsWith('.py')):[...$('sourceFiles').files];
    if(!chosen.length)throw new Error('请选择 Python 源文件或目录。');if(chosen.length>80||chosen.reduce((v,f)=>v+f.size,0)>2000000)throw new Error('请选择不超过 80 文件、2 MB 的模型源码子目录。');
    // Directory picker paths include the selected root name; module entries
    // are relative to that source root, just as in the CLI.
    const files={};for(const file of chosen){const raw=file.webkitRelativePath||file.name,path=directory&&raw.includes('/')?raw.slice(raw.indexOf('/')+1):raw;if(files[path]!==undefined)throw new Error('源码路径重复：'+path);files[path]=await file.text();}return files;
  }
  $('sourceCandidates').onchange=event=>{if(event.target.value)$('sourceEntry').value=event.target.value;};
  function sourceHierarchyText(result){
    const models=new Map((result.models||[]).map(model=>[model.id,model])),relations=result.relationships||[],lines=[];
    function walk(id,prefix,stack){
      if(lines.length>=600)return;const model=models.get(id);lines.push(prefix+(model?.name||id)+` (${id})`);
      if(stack.includes(id)||stack.length>=12){lines.push(prefix+'  ↳ 已在上层出现或超过显示深度；完整关系可由 Agent 扫描读取。');return;}
      const seen=new Set();for(const relation of relations.filter(item=>item.owner===id)){const key=[relation.slot,relation.target,relation.instanceId,relation.certainty].join('|');if(seen.has(key))continue;seen.add(key);
        const note=relation.certainty==='possible'?' · 条件候选':'',count=relation.count===null||relation.count===undefined?'数量待配置':`数量 ${relation.count}`,location=relation.evidence?` · ${relation.evidence.file}:${relation.evidence.line}`:'';
        lines.push(prefix+`  ├ ${relation.slot} · ${count}${note}${location}`);if(relation.targetLocal)walk(relation.target,prefix+'  │ ',[...stack,id]);else lines.push(prefix+'  │ '+relation.target+' · 外部模块');if(lines.length>=600)break;
      }
    }
    for(const id of result.roots||[])walk(id,'',[]);
    if(!lines.length)for(const id of models.keys())walk(id,'',[]);
    if(lines.length>=600)lines.push('显示已截取前 600 行；完整关系保留在扫描结果中。');
    lines.push('',`已发现 ${models.size} 个本地模型 / 模块。包含关系表示源码可见的构造关系；条件候选不代表同时执行。`);
    if(result.unknowns?.length)lines.push(`另有 ${result.unknowns.length} 项工厂、外部模块或配置待确定；未推测实例数量。`);
    return lines.join('\n');
  }
  $('discoverSource').onclick=async()=>{const button=$('discoverSource');button.disabled=true;
    try{const files=await selectedSourceFiles();$('sourceDiscoveryStatus').textContent='正在读取类、继承与构造证据…';const response=await fetch('/api/models/discover',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({files})});const result=await response.json();if(!response.ok)throw new Error(result.error||'模型扫描失败');
      const models=result.models||[],select=$('sourceCandidates');select.replaceChildren(new Option('选择要打开的模型 / 模块',''));for(const model of models){const id=model.entry||model.id;select.add(new Option(`${model.name||id} · ${id}`,id));}
      $('sourceCandidateField').hidden=false;$('sourceHierarchy').hidden=false;$('sourceDiscoveryStatus').textContent=`找到 ${models.length} 个本地模型 / 模块；动态配置保留为待确定。`;
      $('sourceHierarchyText').textContent=sourceHierarchyText(result);
      if(models.length===1){select.value=models[0].entry||models[0].id;$('sourceEntry').value=select.value;}
    }catch(error){sourceError(error);$('sourceDiscoveryStatus').textContent='扫描未完成；源码未改变。';}finally{button.disabled=false;}};
  $('exportSourcePackage').onclick=()=>{const b=importedPackages.get(current?.id);if(b)download(JSON.stringify(b,null,2),'application/json',b.title+'-source-adapter.json');};
  $('openSourceExample').onclick=async()=>{try{const r=await fetch('../verification/source-adapter/river-net.json');if(!r.ok)throw new Error('无法读取示例适配包');await installSource(await r.json());}catch(e){sourceError(e);}};
    $('sourcePackage').onchange=async event=>{const file=event.target.files[0];if(!file)return;try{if(file.size>16000000)throw new Error('适配包超过 16 MB');await studioLoad(JSON.parse(await file.text()));}catch(e){sourceError(e);}finally{event.target.value='';}};
  $('analyzeSource').onclick=async()=>{const button=$('analyzeSource');button.disabled=true;
    try{const files=await selectedSourceFiles();
      $('sourceImportStatus').textContent='正在静态解析源码并验证连接…';const response=await fetch('/api/source-adapter/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({files,entry:$('sourceEntry').value.trim()||null,config:JSON.parse($('sourceConfig').value||'{}')})});
      if(response.status===404||response.status===405||response.status===501)throw new Error('当前服务不支持源码解析。请使用 ArchCanvas Studio 服务，或导入 CLI 生成的适配包。');const payload=await response.json();if(!response.ok)throw new Error(payload.error||'源码解析失败');await installSource(payload);
    }catch(e){sourceError(e);}finally{button.disabled=false;}};
  function evidence(){const q=$('evidenceSearch').value.toLowerCase();$('evidenceList').innerHTML=catalog.evidence.filter(e=>e.title.toLowerCase().includes(q)).map(e=>`<a class="evidence-row" href="../${esc(e.path)}" target="_blank">${esc(e.title)} <small>${Math.round(e.bytes/1024)} KB</small></a>`).join('');}
  $('showEvidence').onclick=()=>{evidence();$('evidenceDialog').showModal();};$('closeEvidence').onclick=()=>$('evidenceDialog').close();$('evidenceSearch').oninput=evidence;
  document.addEventListener('keydown',ev=>{
    const key=ev.key.toLowerCase(),modifier=ev.ctrlKey||ev.metaKey;
    if(studioCanvas&&modifier&&key==='s'){ev.preventDefault();ev.stopPropagation();studioBridge?.emit('shortcut',{action:'save'});return;}
    if(ev.target.closest('input,select,textarea,[contenteditable="true"]'))return;
    if(modifier&&ev.key==='Enter'){ev.preventDefault();apply();}
    else if(modifier&&key==='z'){ev.preventDefault();(ev.shiftKey?$('redo'):$('undo')).click();}
    else if(modifier&&key==='y'){ev.preventDefault();$('redo').click();}
    else if(!modifier&&!ev.altKey&&['v','c','b'].includes(key)){if(busy||drag)return;ev.preventDefault();selectTool({v:'select',c:'connect',b:'bend'}[key]);}
    else if(!modifier&&!ev.altKey&&key==='f'){ev.preventDefault();$('fit').click();studioBridge?.state();}
    else if(ev.key==='Escape'){connection=null;selectedNodes.clear();selectedEdges.clear();selectedAnnotation=null;render();}
    else if(ev.key==='Delete'&&selectedEdges.size&&!busy&&!drag){save();graph.sourceDraftOperations=graph.sourceDraftOperations||[];for(const e of graph.edges)if(selectedEdges.has(e.id))graph.sourceDraftOperations.push({kind:'remove-connection',id:e.id,binding:E.clone(e.binding)});graph.edges=graph.edges.filter(e=>!selectedEdges.has(e.id));selectedEdges.clear();dirty=true;render();persist();studioBridge?.state();}
  });
  window.addEventListener('beforeunload',()=>{if(drag?.saved)restoreGesture(drag);drag=null;flushPersist();});window.addEventListener('resize',()=>{cameraUpdate();render({cameraOnly:true});});
  ensureWorker();
  updateInteractionModeUi();
  async function start(){try{catalogSources=await sourceAsset('data/catalog-sources.json',true);}catch(e){console.warn('Catalog source index:',e.message);}try{const ids=await window.SummaryRecursiveStorage.get('source-adapter:index')||[];for(const id of ids){try{const b=await window.SummaryRecursiveStorage.get('source-adapter:bundle:'+id);if(b)await registerSource(b);}catch(e){console.warn('Saved source adapter:',e.message);}}}catch(e){console.warn('Source adapter storage:',e.message);}
    const query=new URLSearchParams(location.search),chosen=catalog.cases.find(c=>c.id===query.get('case'))||catalog.cases.find(c=>c.collection==='transformer_programmatic_guide'&&c.title==='Transformer'&&!c.historical)||catalog.cases[0];
    if(chosen.historical)$('includeHistory').checked=true;renderCatalog();await openCase(chosen,chosen.views.find(v=>v.key===query.get('view'))||chosen.views[0]);studioBridge?.ready();}
  studioBridge=window.ArchCanvasPreviewBridge?.create({started:()=>startupPromise,isBusy:()=>busy||!!drag,load:studioLoad,state:studioState,selection:studioSelection,source:studioSource,focus:studioFocus,command:studioCommand,svg:studioSvg,save:async()=>{if(busy||drag)throw new Error('请先完成当前图操作。');flushPersist();const document=studioDocument();if(document){const stored=E.clone(document.graph);delete stored.recursive.authority;await window.SummaryRecursiveStorage.put(key(),{version:5,ir:graph.irSha256||null,graph:stored,dirty});}},export:format=>format==='svg'?download(studioSvg(),'image/svg+xml',current.title+'-unified.svg'):$('exportJson').click()});
  startupPromise=start();
})();
