/* UI chrome only. Never walk graph glyphs, source/evidence text, form values or
 * model catalogs: their strings belong to the document, not to the interface. */
(function(root){
  'use strict';
  const key='archcanvas.ui.locale.v1';let locale='zh-CN',english={};
  try{locale=localStorage.getItem(key)==='en'?'en':'zh-CN';}catch{}
  const excluded='#graph,#overviewMap,#modelTitle,#modelCollection,#modelOrigin,#caseList,#sourceLinks,#sourceFacts,#selectionInfo,#evidenceList,#sourceHierarchyText,#sourceCandidates,input,textarea,pre,code,script,style';
  const texts=new Map(),attrs=new Map();
  function message(text){
    if(locale!=='en')return text;
    if(Object.hasOwn(english,text))return english[text];
    for(const [key,value]of Object.entries(english)){
      if(!/\{\d+\}/.test(key))continue;const indices=[];
      const pattern=key.split(/(\{\d+\})/).map(part=>{if(/^\{\d+\}$/.test(part)){indices.push(part.slice(1,-1));return '([\\s\\S]*?)';}return part.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');}).join('');
      const match=new RegExp('^'+pattern+'$').exec(text);
      if(match)return value.replace(/\{(\d+)\}/g,(token,index)=>match[indices.indexOf(index)+1]??token);
    }
    // Expansion control labels contain an opaque module name.
    const toggle=/^(展开|收起) ([\s\S]+)$/.exec(text);
    if(toggle)return (toggle[1]==='展开'?'Expand':'Collapse')+' '+toggle[2];
    return text;
  }
  const allowed=element=>element&&!element.closest(excluded);
  function collectAttributes(element){
    if(!element||(!allowed(element)&&!element.matches('input,textarea,#graph,#overviewMap')))return;
    for(const name of ['title','aria-label','placeholder']){
      const value=element.getAttribute(name);if(value&&/[\u3400-\u9fff]/.test(value)){
        if(!attrs.has(element))attrs.set(element,{});
        const previous=attrs.get(element)[name];
        if(!previous||value!==message(previous))attrs.get(element)[name]=value;
      }
    }
  }
  function collect(element){
    collectAttributes(element);
    if(!allowed(element))return;
    for(const node of element.childNodes)if(node.nodeType===3&&/[\u3400-\u9fff]/.test(node.textContent)){
      const previous=texts.get(node);
      if(!previous||node.textContent!==previous.replace(previous.trim(),message(previous.trim())))texts.set(node,node.textContent);
    }
  }
  function localizeSvg(container){
    // Only renderer-marked chrome annotations can be localized inside the SVG.
    // Preserve their original obstacle width and export the visible SVG verbatim.
    for(const element of container.querySelectorAll('[data-ui-message]')){
      const source=element.getAttribute('data-ui-message');
      element.textContent=source.split(' · ').map(message).join(' · ');
      if(locale==='en'&&Object.keys(english).length){element.setAttribute('textLength',element.getAttribute('data-ui-width'));element.setAttribute('lengthAdjust','spacingAndGlyphs');}
      else {element.removeAttribute('textLength');element.removeAttribute('lengthAdjust');}
    }
    for(const element of container.querySelectorAll('[data-node-id][aria-label]')){
      const label=element.getAttribute('aria-label')||'',suffix=label.replace(/^(Nodes?|节点) /,'');
      element.setAttribute('aria-label',(locale==='en'?'Node':'节点')+' '+suffix);
    }
    for(const element of container.querySelectorAll('[data-edge-id][aria-label]')){
      const id=element.getAttribute('data-edge-id'),source=element.getAttribute('data-source'),target=element.getAttribute('data-target');
      element.setAttribute('aria-label',locale==='en'?`Edge ${id} from ${source} to ${target}`:`边 ${id} ${source} 到 ${target}`);
    }
    for(const control of container.querySelectorAll('.expansion-control')){
      const label=control.getAttribute('aria-label')||'',match=/^(Expand|Collapse|展开|收起) ([\s\S]+)$/.exec(label);
      if(match)control.setAttribute('aria-label',message((['Expand','展开'].includes(match[1])?'展开':'收起')+' '+match[2]));
    }
  }
  root.ArchCanvasUILocale={text:message,svg:localizeSvg,node:(id,label)=>(locale==='en'?'Node':'节点')+' '+id+' '+label,edge:(id,source,target)=>locale==='en'?`Edge ${id} from ${source} to ${target}`:`边 ${id} ${source} 到 ${target}`};
  function paint(){
    observer.disconnect();document.documentElement.lang=locale;
    localizeSvg(document);
    for(const [node,source]of texts){if(!node.isConnected){texts.delete(node);continue;}const trim=source.trim(),next=source.replace(trim,message(trim));if(node.textContent!==next)node.textContent=next;}
    for(const [element,values]of attrs){if(!element.isConnected){attrs.delete(element);continue;}for(const [name,source]of Object.entries(values))element.setAttribute(name,message(source));}
    observer.observe(document.body,{subtree:true,childList:true,characterData:true});
  }
  const observer=new MutationObserver(records=>{
    let changed=false;
    for(const record of records){
      const element=record.target.nodeType===1?record.target:record.target.parentElement;
      if(!allowed(element))continue;
      collect(element);changed=true;
      for(const node of record.addedNodes||[])if(node.nodeType===1){collect(node);for(const child of node.querySelectorAll('*'))collect(child);}
    }
    if(changed)paint();
  });
  for(const element of document.body.querySelectorAll('*'))collect(element);
  function set(value){if(value!=='zh-CN'&&value!=='en')return;locale=value;for(const control of document.querySelectorAll('#graph,#overviewMap,.expansion-control'))collectAttributes(control);paint();}
  root.addEventListener('storage',event=>{if(event.key===key)set(event.newValue);});
  root.addEventListener('message',event=>{if(event.source===root.parent&&event.origin===root.location.origin&&event.data?.type==='archcanvas:ui-locale')set(event.data.locale);});
  fetch('../ui-en.json').then(response=>{if(!response.ok)throw Error('UI dictionary unavailable');return response.json();}).then(value=>{english=value;paint();}).catch(()=>paint());
  paint();
})(window);
