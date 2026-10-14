/* UI for the independent Edge Router reconstruction. */
(function () {
  'use strict';
  const R = window.EdgeRouterLabRouting, $ = id => document.getElementById(id), svg = $('graph'), NS = 'http://www.w3.org/2000/svg';
  const initial = {
    nodes: [
      { id: 'A', label: 'Source', sub: '输入', x: 75, y: 166, w: 132, h: 66 },
      { id: 'B', label: 'Transform', sub: '变换', x: 380, y: 80, w: 138, h: 66 },
      { id: 'C', label: 'Merge', sub: '汇合', x: 748, y: 148, w: 138, h: 66 },
      { id: 'D', label: 'Output', sub: '输出', x: 900, y: 335, w: 132, h: 76 },
      { id: 'E', label: 'Archive', sub: '存储', x: 755, y: 557, w: 138, h: 66 },
      { id: 'F', label: 'Residual', sub: '旁路', x: 82, y: 518, w: 132, h: 66 },
      { id: 'G', label: 'Observer', sub: '观察', x: 371, y: 549, w: 138, h: 66 },
      { id: 'O1', label: 'Obstacle', sub: '拖动我 · 观察路径变化', x: 475, y: 271, w: 142, h: 160, obstacle: true },
      { id: 'O2', label: 'Block', sub: '固定障碍', x: 245, y: 326, w: 118, h: 78, obstacle: true }
    ],
    edges: [ ['A','B'],['B','C'],['C','D'],['A','C'],['A','D'],['F','G'],['G','D'],['G','E'],['D','E'],['A','F'],['B','G'] ].map((pair,i) => ({ id: `e${i+1}`, source: pair[0], target: pair[1], arrow: 'target', style: 'orthogonal', route: [], waypoints: [] }))
  };
  let state = structuredClone(window.EdgeRouterLabFixture || initial), tool = 'select', selectedNodes = new Set(), selectedEdges = new Set(), connection = null, drag = null, dirty = false;
  let history = [], future = [], ghost = [], toastTimer, lastMetrics = { routed: 0, time: 0 }, epoch = 0;
  function save() { history.push(JSON.stringify(state)); if (history.length > 40) history.shift(); future = []; }
  function restore(serialized) { state = JSON.parse(serialized); selectedNodes.clear(); selectedEdges.clear(); connection = null; ghost = []; dirty = false; render(); }
  function element(tag, attrs = {}, content) { const el = document.createElementNS(NS, tag); Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v)); if(content !== undefined) el.textContent = content; return el; }
  function point(ev) { const p = svg.createSVGPoint(); p.x = ev.clientX; p.y = ev.clientY; return p.matrixTransform(svg.getScreenCTM().inverse()); }
  function node(id) { return state.nodes.find(n => n.id === id); }
  function nearestSide(n, p) { const candidates = [{ side:'left',delta:Math.abs(p.x-n.x),fraction:(p.y-n.y)/n.h },{ side:'right',delta:Math.abs(p.x-n.x-n.w),fraction:(p.y-n.y)/n.h },{ side:'top',delta:Math.abs(p.y-n.y),fraction:(p.x-n.x)/n.w },{ side:'bottom',delta:Math.abs(p.y-n.y-n.h),fraction:(p.x-n.x)/n.w }]; const b=candidates.sort((a,b)=>a.delta-b.delta)[0];return { side:b.side, fraction:Math.max(.12,Math.min(.88,b.fraction)) }; }
  function hitNode(p) { return state.nodes.find(n => p.x >= n.x - 7 && p.x <= n.x+n.w+7 && p.y >= n.y-7 && p.y <= n.y+n.h+7); }
  function toast(text) { $('toast').textContent=text; $('toast').classList.add('visible'); clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('toast').classList.remove('visible'),3500); }
  function settings() { return { margin: +$('clearance').value, stub: 28, bendCost: 40, crossingCost: $('crossings').checked ? 220 : 0, overlapCost: $('crossings').checked ? 3 : 0, edgeSpacing: $('crossings').checked ? 12 : 0, preserve: $('keepBends').checked, sides: $('portSides').value, grid: $('gridEnabled').checked ? 24 : 0 }; }
  function selectEdge(e, additive=false) { if (!additive) { selectedEdges.clear(); selectedNodes.clear(); } if(additive && selectedEdges.has(e.id))selectedEdges.delete(e.id);else selectedEdges.add(e.id); }
  function selectedPort(e, side) { const n=node(side==='source'?e.source:e.target), other=node(side==='source'?e.target:e.source); const fixed=side==='source'?e.fixedSource:e.fixedTarget, stored=side==='source'?e.sourcePort:e.targetPort; return R.port(n, fixed?.side || stored?.side || R.candidateSides(n, other)[0], fixed?.fraction ?? stored?.fraction ?? .5); }
  function updateEndpoints(e) { if(e.route.length >= 2) { e.route[0]=selectedPort(e,'source');e.route[e.route.length-1]=selectedPort(e,'target'); } }
  function displayed(e) { return e.style==='octilinear' ? R.chamfer(e.route,state.nodes,18) : e.route; }
  function dFor(points, style) { return style === 'curved' ? R.roundedPath(points, Math.min(12,+$('clearance').value*.65)) : R.polylinePath(points); }
  function crop(points) { return R.simplify(points); }
  function drawArrow(layer,tip,from,color,open=false) { const len=R.dist(tip,from);if(len<1)return;const u={x:(tip.x-from.x)/len,y:(tip.y-from.y)/len},v={x:-u.y,y:u.x},b={x:tip.x-u.x*9,y:tip.y-u.y*9};const a={x:b.x+v.x*4,y:b.y+v.y*4},c={x:b.x-v.x*4,y:b.y-v.y*4};layer.append(element('path',{d:`M ${a.x} ${a.y} L ${tip.x} ${tip.y} L ${c.x} ${c.y}${open?'':' Z'}`,fill:open?'none':color,stroke:open?color:'none','stroke-width':open?1.8:0,'pointer-events':'none',class:'arrow-shape'})); }
  function render() {
    $('obstacleLayer').replaceChildren();$('ghostLayer').replaceChildren();$('edgeLayer').replaceChildren();$('nodeLayer').replaceChildren();$('handleLayer').replaceChildren();
    if ($('showObstacles').checked) for (const n of state.nodes) { const r=R.expand(n,+$('clearance').value);$('obstacleLayer').append(element('rect',{x:r.x,y:r.y,width:r.w,height:r.h,rx:4,fill:'#efb47c08',stroke:'#d8a37488','stroke-dasharray':'5 5','stroke-width':1})); }
    if ($('showGhost').checked) for(const e of ghost) $('ghostLayer').append(element('path',{d:dFor(e.route,e.style),fill:'none',stroke:'#a4b8ba','stroke-width':1.5,'stroke-dasharray':'5 6',opacity:.65,'pointer-events':'none'}));
    for(const e of state.edges) {
      const ps=displayed(e); if(ps.length<2)continue;const selected=selectedEdges.has(e.id),color=e.failed?'#d94b59':selected?'#d77944':'#197c88';const start=e.arrow==='both',end=e.arrow!=='none';
      const group=element('g',{'data-edge-id':e.id,'aria-label':`边 ${e.id} ${e.source} 到 ${e.target}`});
      group.append(element('path',{d:dFor(crop(ps,start,end),e.style),stroke:color,'stroke-width':selected?2.8:1.8,class:'edge-path','stroke-linecap':'butt'}));
      if(end)drawArrow(group,ps[ps.length-1],ps[ps.length-2],color,e.arrow==='open');if(start)drawArrow(group,ps[0],ps[1],color);
      const hit=element('path',{d:dFor(ps,e.style),class:'edge-hit','data-edge-hit':e.id});hit.addEventListener('pointerdown',ev=>onEdgeDown(ev,e));group.append(hit);$('edgeLayer').append(group);
    }
    for(const n of state.nodes) {
      const selected=selectedNodes.has(n.id),g=element('g',{class:'node','data-node-id':n.id,'aria-label':`节点 ${n.id} ${n.label}`});
      if(selected)g.append(element('rect',{x:n.x-5,y:n.y-5,width:n.w+10,height:n.h+10,rx:11,fill:'none',stroke:'#d99160','stroke-width':2,'stroke-dasharray':'4 3'}));
      g.append(element('rect',{x:n.x,y:n.y,width:n.w,height:n.h,rx:9,fill:n.obstacle?'#e5eeec':(n.id==='D'?'#096f7c':'#0e9b9f'),stroke:n.obstacle?'#c7d9d5':'#078b91','stroke-width':1,filter:'url(#nodeShadow)'}));
      g.append(element('text',{x:n.x+15,y:n.y+27,fill:n.obstacle?'#6e8b86':'white','font-size':16,'font-weight':550,class:'node-label'},n.label));
      g.append(element('text',{x:n.x+15,y:n.y+46,fill:n.obstacle?'#96aaa5':'#bdece7','font-size':10,class:'node-label'},n.sub));
      if(n.obstacle)g.append(element('text',{x:n.x+15,y:n.y+n.h-16,fill:'#b4c8c0','font-size':25,class:'node-label'},'╱╱╱'));
      g.addEventListener('pointerdown',ev=>onNodeDown(ev,n));$('nodeLayer').append(g);
      if($('showPorts').checked || tool==='connect' || drag?.kind==='endpoint') for(const side of ['left','right','top','bottom']) {
        const p=R.port(n,side),c=element('circle',{cx:p.x,cy:p.y,r:tool==='connect'?5.5:3.3,fill:'#fff',stroke:n.obstacle?'#adbfba':'#147f86','stroke-width':1.2,class:'port-hit','data-port':`${n.id}-${side}`});
        c.addEventListener('pointerdown',ev=>{if(tool==='connect')startConnection(ev,n,{side,fraction:.5});else onNodeDown(ev,n)});$('handleLayer').append(c);
      }
    }
    for(const e of state.edges.filter(e=>selectedEdges.has(e.id))) {
      e.waypoints.forEach((p,index)=>{const h=element('rect',{x:p.x-5,y:p.y-5,width:10,height:10,rx:2,fill:'#fff',stroke:'#d77944','stroke-width':2,class:'bend-handle','data-bend':`${e.id}-${index}`});h.addEventListener('pointerdown',ev=>startDrag(ev,{kind:'bend',edge:e,index}));$('handleLayer').append(h)});
      for(const [side,index]of [['source',0],['target',e.route.length-1]]) { const p=e.route[index];if(!p)continue;const c=element('circle',{cx:p.x,cy:p.y,r:8,fill:'#fff5e8',stroke:'#d77944','stroke-width':2,class:'endpoint-handle','data-endpoint':`${e.id}-${side}`});c.addEventListener('pointerdown',ev=>startDrag(ev,{kind:'endpoint',edge:e,side}));$('handleLayer').append(c);$('handleLayer').append(element('text',{x:p.x,y:p.y+3,'text-anchor':'middle',fill:'#bf753b','font-size':8,'font-weight':700,'pointer-events':'none'},side==='source'?'S':'T')); }
    }
    const st=R.stats(state.edges);$('metricLength').textContent=st.length.toLocaleString();$('metricBends').textContent=st.bends;$('metricCrossings').textContent=st.crossings;$('metricRouted').textContent=lastMetrics.routed;$('metricTime').textContent=lastMetrics.time;
    $('graphCount').textContent=`${state.nodes.length} nodes / ${state.edges.length} edges`;$('dirtyBadge').textContent=dirty?'待 Apply · 路径已编辑':'路径已计算';$('dirtyBadge').classList.toggle('dirty',dirty);$('undo').disabled=!history.length;$('redo').disabled=!future.length;
    renderInspector();
  }
  function renderInspector() {
    const box=$('selectionInfo');box.replaceChildren();
    if(selectedEdges.size===1) {
      const e=state.edges.find(e=>selectedEdges.has(e.id));box.innerHTML=`<p class="eyebrow">SELECTED EDGE</p><h3>${e.id} <span style="color:#cf8250">${e.source} → ${e.target}</span></h3><div class="prop">路径风格 <code>${e.style}</code></div><div class="prop">源端口 <code>${e.sourcePort?.side||'auto'}${e.fixedSource?' · fixed':''}</code></div><div class="prop">目标端口 <code>${e.targetPort?.side||'auto'}${e.fixedTarget?' · fixed':''}</code></div><div class="prop">手动途经点 <code>${e.waypoints.length}</code></div><p class="path-data"></p><button class="secondary" id="releasePorts">释放固定端口</button><button class="secondary" id="clearBends">清除手动折点</button><button class="secondary" id="deleteEdge">删除这条边</button>`;
      box.querySelector('.path-data').textContent=dFor(displayed(e),e.style);$('arrowStyle').value=e.arrow;
      $('releasePorts').onclick=()=>{save();delete e.fixedSource;delete e.fixedTarget;dirty=true;render();toast('已释放固定端口，下次 Apply 将自由选择端口。')};
      $('clearBends').onclick=()=>{save();e.waypoints=[];dirty=true;render()};$('deleteEdge').onclick=()=>{save();state.edges=state.edges.filter(x=>x!==e);selectedEdges.clear();dirty=true;render()};
    } else if(selectedNodes.size===1) {
      const n=state.nodes.find(n=>selectedNodes.has(n.id)),count=state.edges.filter(e=>e.source===n.id||e.target===n.id).length;box.innerHTML=`<p class="eyebrow">SELECTED NODE</p><h3>${n.label} / ${n.id}</h3><div class="prop">位置 <code>${Math.round(n.x)}, ${Math.round(n.y)}</code></div><div class="prop">大小 <code>${n.w} × ${n.h}</code></div><div class="prop">相邻边 <code>${count}</code></div><p class="micro">拖动仅更新相邻端点。重新布线时，这个节点及其它节点的坐标不会改变。</p>`;
    } else if(selectedNodes.size||selectedEdges.size) box.innerHTML=`<div class="empty">已选 ${selectedNodes.size} 个节点 / ${selectedEdges.size} 条边。<br>Shift + 点击可多选。</div>`;
    else box.innerHTML='<div class="empty">↖ 点击一条边或一个节点<br><span class="micro">检查端口、路径坐标与手动折点。</span></div>';
  }
  function onNodeDown(ev,n) {
    if(ev.button!==0)return;ev.stopPropagation();
    if(tool==='connect') {
      if(!connection){connection={node:n,fixed:null};selectedNodes=new Set([n.id]);selectedEdges.clear();toast(`已选择 ${n.id}，点击目标节点完成连接。`)}
      else if(connection.node.id!==n.id || connection.fixed)completeConnection(n,null);render();return;
    }
    if(ev.shiftKey){selectedNodes.has(n.id)?selectedNodes.delete(n.id):selectedNodes.add(n.id);render();return;}
    selectedNodes=new Set([n.id]);selectedEdges.clear();startDrag(ev,{kind:'node',node:n,start:point(ev),x:n.x,y:n.y});
  }
  function onEdgeDown(ev,e) {
    if(ev.button!==0)return;ev.stopPropagation();
    if(tool==='bend' && selectedEdges.has(e.id)) {
      save();const p=point(ev);let best=Infinity,index=1;
      for(let i=1;i<e.route.length;i++){const a=e.route[i-1],b=e.route[i],den=(b.x-a.x)**2+(b.y-a.y)**2,t=den?Math.max(0,Math.min(1,((p.x-a.x)*(b.x-a.x)+(p.y-a.y)*(b.y-a.y))/den)):0,near={x:a.x+t*(b.x-a.x),y:a.y+t*(b.y-a.y)},d=R.dist(p,near);if(d<best){best=d;index=i}}
      e.route.splice(index,0,{x:p.x,y:p.y});e.waypoints.push({x:p.x,y:p.y});e.style='orthogonal';dirty=true;render();toast('已添加途经点。拖动小方块；勾选“保留手动折点”后 Apply。');
    }else{selectEdge(e,ev.shiftKey);render();}
  }
  function startDrag(ev,obj) {
    ev.stopPropagation();ev.preventDefault();if(obj.kind==='endpoint'){save();obj.saved=true;}drag=obj;svg.setPointerCapture(ev.pointerId);render();
  }
  function startConnection(ev,n,fixed) { if(ev.button!==0)return;ev.stopPropagation();ev.preventDefault();connection={node:n,fixed};drag={kind:'connection',start:R.port(n,fixed.side,fixed.fraction)};svg.setPointerCapture(ev.pointerId);render(); }
  function completeConnection(n,fixed) {
    save();const e={id:'e'+(++epoch+100),source:connection.node.id,target:n.id,arrow:$('arrowStyle').value,style:'orthogonal',route:[],waypoints:[],fixedSource:connection.fixed||undefined,fixedTarget:fixed||undefined};
    state.edges.push(e);const a=selectedPort(e,'source'),b=selectedPort(e,'target');e.route=[a,b];selectedNodes.clear();selectedEdges=new Set([e.id]);connection=null;dirty=true;toast(`已创建 ${e.source} → ${e.target}。Apply Layout 计算避障路径。`);
  }
  svg.addEventListener('pointermove',ev=>{
    if(!drag)return;const p=point(ev);
    if((drag.kind==='node'||drag.kind==='bend')&&!drag.saved){save();drag.saved=true;}
    if(drag.kind==='node') {
      const n=drag.node;n.x=Math.max(42,Math.min(1058-n.w,drag.x+p.x-drag.start.x));n.y=Math.max(45,Math.min(661-n.h,drag.y+p.y-drag.start.y));
      for(const e of state.edges)if(e.source===n.id||e.target===n.id)updateEndpoints(e);dirty=true;render();
    }else if(drag.kind==='bend'){
      const e=drag.edge,old=e.waypoints[drag.index],idx=e.route.findIndex(v=>R.dist(v,old)<.01);e.waypoints[drag.index]={x:p.x,y:p.y};if(idx>=0)e.route[idx]={x:p.x,y:p.y};dirty=true;render();
    }else{
      $('previewLayer').replaceChildren();const start=drag.kind==='connection'?drag.start:drag.edge.route[drag.side==='source'?0:drag.edge.route.length-1];
      $('previewLayer').append(element('path',{d:`M ${start.x} ${start.y} L ${p.x} ${p.y}`,fill:'none',stroke:'#d77944','stroke-width':2,'stroke-dasharray':'5 4','pointer-events':'none'}));
    }
  });
  svg.addEventListener('pointerup',ev=>{
    if(!drag)return;const p=point(ev),n=hitNode(p),kind=drag.kind;
    if(kind==='connection') { if(n)completeConnection(n,nearestSide(n,p));else {connection=null;toast('连接未落在节点上，已取消。')} }
    else if(kind==='endpoint') { if(n){const e=drag.edge,key=drag.side==='source'?'fixedSource':'fixedTarget';e[drag.side]=n.id;e[key]=nearestSide(n,p);const newPort=selectedPort(e,drag.side);e[drag.side==='source'?'sourcePort':'targetPort']=newPort;updateEndpoints(e);dirty=true;toast(`${e.id} ${drag.side==='source'?'源端':'目标端'}已重新连接到 ${n.id}；Apply 重新计算路径。`)}else{history.pop();toast('端点未落在节点上，保留原连接。')} }
    if(kind==='node'&&drag.saved)toast('节点位置已更改。旧中间路径保留，Apply Layout 才全局重新布线。');
    drag=null;$('previewLayer').replaceChildren();if(svg.hasPointerCapture(ev.pointerId))svg.releasePointerCapture(ev.pointerId);render();
  });
  svg.addEventListener('pointercancel',()=>{drag=null;connection=null;$('previewLayer').replaceChildren();render()});
  svg.addEventListener('pointerdown',ev=>{if(ev.target.classList.contains('background')){selectedNodes.clear();selectedEdges.clear();connection=null;render()}});
  function conflicts(e,opts) {
    const wanted=$('routingStyle').value;if(e.style!==wanted||e.route.length<2)return true;
    for(let i=1;i<e.route.length;i++)for(const n of state.nodes){if(i===1&&n.id===e.source)continue;if(i===e.route.length-1&&n.id===e.target)continue;if(R.intersectsRect(e.route[i-1],e.route[i],R.expand(n,opts.margin)))return true;}
    if(opts.sides!=='any'){const sides=opts.sides==='lr'?['left','right']:['top','bottom'];if(!sides.includes(e.sourcePort?.side)||!sides.includes(e.targetPort?.side))return true;}return false;
  }
  function fraction(edge,nodeId,side) { const siblings=state.edges.filter(e=>e.source===nodeId||e.target===nodeId),index=siblings.indexOf(edge);return .2+.6*(index+1)/(siblings.length+1); }
  async function apply(initialRun=false) {
    const scope=$('scope').value,policy=$('policy').value;let targets=scope==='all'?state.edges:scope==='selected'?state.edges.filter(e=>selectedEdges.has(e.id)):state.edges.filter(e=>selectedNodes.has(e.source)||selectedNodes.has(e.target));
    if(!targets.length){toast('当前作用范围为空。先选择边或节点。');return;}
    if(policy==='never'){lastMetrics={routed:0,time:0};render();toast('Never：保留所有路径。');return;}
    const opts=settings();if(policy==='needed')targets=targets.filter(e=>conflicts(e,opts));if(!targets.length){lastMetrics={routed:0,time:0};render();toast('当前路径满足约束，无需重新计算。');return;}
    if(!initialRun)save();ghost=state.edges.map(e=>({id:e.id,route:structuredClone(e.route),style:e.style}));
    $('applyLayout').disabled=true;await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    const begin=performance.now(),positions=JSON.stringify(state.nodes.map(n=>[n.id,n.x,n.y])),targetIds=new Set(targets.map(e=>e.id));
    let prior=state.edges.filter(e=>!targetIds.has(e.id)).map(e=>e.route),routed=0,failures=0;
    for(const e of targets){const result=R.routeEdge(e,state.nodes,prior,{...opts,sourceFraction:fraction(e,e.source),targetFraction:fraction(e,e.target)});if(result.ok){e.route=result.points;e.sourcePort=result.sourcePort;e.targetPort=result.targetPort;e.style=$('routingStyle').value;e.failed=false;routed++;}else{e.failed=true;failures++;}prior.push(e.route);}
    // Second pass is a reconstruction choice: price existing crossings then retry.
    if(opts.crossingCost>0 && targets.length>1) for(const e of targets){const paths=state.edges.filter(x=>x!==e).map(x=>x.route);const result=R.routeEdge(e,state.nodes,paths,{...opts,sourceFraction:fraction(e,e.source),targetFraction:fraction(e,e.target)});if(result.ok&&(e.failed||result.cost<routeCost(e.route,paths,opts))){e.route=result.points;e.sourcePort=result.sourcePort;e.targetPort=result.targetPort;e.failed=false;}}
    failures=targets.filter(e=>e.failed).length;routed=targets.length-failures;
    lastMetrics={routed,time:Math.round(performance.now()-begin)};dirty=failures>0;$('applyLayout').disabled=false;render();
    if(positions!==JSON.stringify(state.nodes.map(n=>[n.id,n.x,n.y])))throw new Error('Router changed node positions');
    if(!initialRun)toast(failures?`${routed} 条成功，${failures} 条无可行路径（红色）。尝试移动节点、清除折点或释放端口。`:`重新布线 ${routed} 条边 · 节点坐标保持不变 · ${lastMetrics.time} ms`);
  }
  function routeCost(points,paths,opts){let cost=0;for(let i=1;i<points.length;i++){cost+=R.dist(points[i-1],points[i]);if(i>1)cost+=opts.bendCost;for(const path of paths)for(let j=1;j<path.length;j++){if(R.crossing(points[i-1],points[i],path[j-1],path[j]))cost+=opts.crossingCost;cost+=R.overlap(points[i-1],points[i],path[j-1],path[j])*opts.overlapCost;}}return cost;}
  document.querySelectorAll('[data-tool]').forEach(button=>button.onclick=()=>{tool=button.dataset.tool;connection=null;document.querySelectorAll('[data-tool]').forEach(b=>b.classList.toggle('active',b===button));$('interactionHint').textContent=tool==='connect'?'从源端口拖到目标端口；也可依次点击两个节点。连接关系先更新，Apply 再计算避障路径。':tool==='bend'?'先点击选中一条边，再点击路径添加途经点。拖动小方块编辑；勾选保留手动折点后 Apply。':'拖动节点 → 旧路径保留 → Apply Layout 重新避障。选中边可拖动两个端点，改变连接关系。';render()});
  $('clearance').oninput=()=>{$('clearanceValue').value=$('clearance').value+' px'};['showGhost','showObstacles','showPorts'].forEach(id=>$(id).onchange=render);
  $('setArrow').onclick=()=>{if(!selectedEdges.size){toast('请先选择至少一条边。');return;}save();for(const e of state.edges)if(selectedEdges.has(e.id))e.arrow=$('arrowStyle').value;render();toast('箭头样式已更新；路径坐标保持不变。')};
  $('applyLayout').onclick=()=>apply();$('undo').onclick=()=>{if(history.length){future.push(JSON.stringify(state));restore(history.pop());toast('已撤销')}};$('redo').onclick=()=>{if(future.length){history.push(JSON.stringify(state));restore(future.pop());toast('已重做')}};
  $('reset').onclick=()=>{save();state=structuredClone(initial);selectedNodes.clear();selectedEdges.clear();connection=null;ghost=[];$('routingStyle').value='orthogonal';$('scope').value='all';$('policy').value='always';$('portSides').value='any';$('keepBends').checked=false;apply(true)};
  $('exportSvg').onclick=()=>{const clone=svg.cloneNode(true);clone.setAttribute('xmlns',NS);clone.setAttribute('width','1100');clone.setAttribute('height','720');clone.removeAttribute('tabindex');clone.querySelector('#previewLayer').remove();clone.querySelectorAll('.edge-hit,.port-hit,.bend-handle,.endpoint-handle').forEach(e=>e.remove());const style=element('style',{},'.edge-path{fill:none;stroke-linejoin:round;stroke-linecap:butt}.node-label{font-family:system-ui,sans-serif}');clone.prepend(style);const blob=new Blob([new XMLSerializer().serializeToString(clone)],{type:'image/svg+xml'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='edge-router-reconstruction.svg';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
  document.addEventListener('keydown',ev=>{if(ev.target.matches('select,input,textarea'))return;if((ev.ctrlKey||ev.metaKey)&&ev.key==='Enter'){ev.preventDefault();apply()}else if((ev.ctrlKey||ev.metaKey)&&ev.key.toLowerCase()==='z'){ev.preventDefault();(ev.shiftKey?$('redo'):$('undo')).click()}else if(ev.key==='Escape'){connection=null;selectedEdges.clear();selectedNodes.clear();render()}else if(ev.key==='Delete'&&selectedEdges.size){save();state.edges=state.edges.filter(e=>!selectedEdges.has(e.id));selectedEdges.clear();render()}});
  render();apply(true);
})();
