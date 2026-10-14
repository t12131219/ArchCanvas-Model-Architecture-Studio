/* Same-origin Studio integration. Commands operate the preview, never source files. */
(function(root){
  'use strict';
  const prefix='archcanvas:preview:';
  function create(api){
    const embedded=root.parent!==root&&root.location.origin!=='null';
    let ready=false,selectionSignature='',queue=Promise.resolve();
    const query=new URLSearchParams(root.location.search);
    if(query.get('embed')==='1')document.documentElement.classList.add('studio-embedded');
    if(query.get('surface')==='canvas'){
      document.documentElement.classList.add('studio-canvas');
      const close=()=>document.documentElement.classList.remove('studio-library-open','studio-routing-open');
      const backdrop=document.createElement('button');backdrop.className='studio-drawer-backdrop';backdrop.setAttribute('aria-label','关闭预览面板');backdrop.onclick=close;document.body.append(backdrop);
      for(const panel of document.querySelectorAll('.library,.settings')){const button=document.createElement('button');button.className='studio-drawer-close';button.textContent='关闭 ×';button.onclick=close;panel.prepend(button);}
      const sourceContext=document.createElement('dialog');sourceContext.id='studioSourceContext';
      const sourceHeader=document.createElement('div');sourceHeader.className='dialog-head';const sourceTitle=document.createElement('h2');sourceTitle.textContent='当前模型 · 源码与 IR';const sourceClose=document.createElement('button');sourceClose.textContent='关闭 ×';sourceClose.onclick=()=>sourceContext.close();sourceHeader.append(sourceTitle,sourceClose);sourceContext.append(sourceHeader);
      for(const selector of ['.source-bar','.facts']){const section=document.querySelector(selector);if(section)sourceContext.append(section);}document.body.append(sourceContext);
      const contextButton=document.createElement('button');contextButton.textContent='当前模型源码、IR 与来源';contextButton.onclick=()=>sourceContext.showModal();document.querySelector('#evidenceDialog .evidence-shortcuts')?.prepend(contextButton);
      const routing=document.querySelector('.settings');for(const selector of ['.metrics','.hint']){const section=document.querySelector(selector);if(section)routing?.append(section);}
      document.addEventListener('keydown',event=>{if(event.key==='Escape')close();});
    }
    function emit(name,payload={}){
      if(embedded)root.parent.postMessage({type:prefix+name,...payload},root.location.origin);
    }
    function state(){if(ready)emit('state',api.state());}
    function selection(payload){
      const signature=JSON.stringify([payload.caseId,payload.nodeId,payload.annotationId,payload.edgeIds,payload.nodeIds]);
      if(ready&&signature!==selectionSignature){selectionSignature=signature;emit('selection',payload);}
    }
    async function source(requestId){
      const result=await api.source();
      if(result?.source||result?.bundle)emit('source',{requestId,...result});
      else emit('source-unavailable',{requestId,caseId:api.state().case?.id,message:result?.message||'当前案例没有可编辑的模型源码。'});
    }
    async function receive(event){
      if(!embedded||event.source!==root.parent||event.origin!==root.location.origin)return;
      const message=event.data;
      if(!message||typeof message!=='object'||typeof message.type!=='string'||!message.type.startsWith(prefix))return;
      const requestId=message.requestId;
      if(requestId!==undefined&&typeof requestId!=='string'&&typeof requestId!=='number')return;
      const command=message.type.slice(prefix.length);
      if(!capabilities().includes(command)&&command!=='hello')return;
      try{
        await api.started();
        if(command==='ping'||command==='hello'){emit('ready',{requestId,version:1,capabilities:capabilities()});state();}
        else if(command==='load'){
          if(!message.bundle||typeof message.bundle!=='object')throw new Error('缺少源码适配包或编辑 JSON。');
          await api.load(message.bundle);
          emit('loaded',{requestId,...api.state()});state();
        }else if(command==='snapshot')emit('snapshot',{requestId,...api.state()});
        else if(command==='request-source')await source(requestId);
        else if(command==='focus'){await api.focus(message);emit('focused',{requestId,...api.selection()});}
        else if(command==='save'){await api.save();emit('saved',{requestId,...api.state()});}
        else if(command==='svg'){const xml=await api.svg(message);emit('svg',{requestId,xml,svg:xml,...api.state()});}
        else if(command==='export-svg'||command==='export-json'){await api.export(command==='export-svg'?'svg':'json');emit('exported',{requestId,format:command==='export-svg'?'svg':'json'});}
        else {await api.command(command,message);emit('applied',{requestId,command,...api.state()});state();}
      }catch(error){emit('error',{requestId,command,message:error?.message||String(error)});}
    }
    function capabilities(){return ['load','snapshot','request-source','focus','save','export-svg','export-json','svg','visual','presentation','set-frontier','show-library','show-routing','show-import','show-evidence','undo','redo','fit','zoom','select-tool','connect-tool','pan-tool','bend-tool','show-ports','grid','apply-layout','collapse-all','expand-all','ping'];}
    root.addEventListener('message',event=>{
      // Serialize async loads so an earlier request cannot overwrite a later model.
      queue=queue.then(()=>receive(event)).catch(error=>emit('error',{message:error.message}));
    });
    return {emit,state,selection,source,ready(){ready=true;emit('ready',{version:1,capabilities:capabilities()});state();}};
  }
  root.ArchCanvasPreviewBridge={create};
})(window);
