import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const {chromium}=await import(option('--playwright')?pathToFileURL(option('--playwright')).href:'playwright');
const base=option('--base','http://127.0.0.1:8789'),output=option('--output','/tmp/summary-large-operations.json');
const browser=await chromium.launch({headless:true,...(option('--chromium')?{executablePath:option('--chromium')} : {}),args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1600,height:1100},acceptDownloads:true}),checks=[],errors=[],sourceWrites=[],measurements=[],models=[];
page.setDefaultTimeout(180000);page.setDefaultNavigationTimeout(180000);
page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST'&&/edit-source|transactions|runtime|preview\/analyze/.test(r.url()))sourceWrites.push(r.url());});
checks.push=(...values)=>{for(const v of values)console.log('PASS',v);return Array.prototype.push.apply(checks,values);};
await page.addInitScript(()=>{
 const hash=async v=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(v))))).map(v=>v.toString(16).padStart(2,'0')).join('');
 window.__largeCommand=async(name,payload={},facts=false)=>{
  const response=await new Promise((resolve,reject)=>{const child=document.querySelector('iframe').contentWindow,requestId=crypto.randomUUID(),timer=setTimeout(()=>{window.removeEventListener('message',listen);reject(Error('timeout '+name));},180000);
   function listen(e){if(e.source!==child||e.origin!==location.origin||e.data?.requestId!==requestId)return;clearTimeout(timer);window.removeEventListener('message',listen);e.data.type.endsWith(':error')?reject(Error(e.data.message)):resolve(e.data);}window.addEventListener('message',listen);child.postMessage({type:'archcanvas:preview:'+name,...payload,requestId},location.origin);
  });
  const d=response.document;if(!d)return {};
  window.__largeLast=d;const ir=d.graph.generic.ir;
  if(facts){const ref=window.__largeReference;if(!ref||JSON.stringify(ref)!==JSON.stringify(ir))throw Error('complete source facts changed');for(const [ledger,items]of [[d.semanticView.nodeAccounting,ir.nodes],[d.semanticView.edgeAccounting,ir.edges]]){const a=Object.values(ledger).flat().sort(),b=items.map(n=>n.id).sort();if(new Set(a).size!==b.length||JSON.stringify(a)!==JSON.stringify(b))throw Error('complete accounting changed');}}
  return {caseId:d.caseId,title:d.title,dirty:d.dirty,busy:d.busy,canCancel:d.canCancel,undo:d.undo,redo:d.redo,preset:d.frontierPreset,digest:ir.ir_digest,total:[ir.nodes.length,ir.edges.length],visible:[d.graph.nodes.length,d.graph.edges.length],routing:d.graph.nativeRouting,
   geometry:await hash({nodes:d.graph.nodes,edges:d.graph.edges}),camera:d.graph.studioCamera,firstNode:d.graph.nodes.find(n=>!n.modelHeading)?.id,presentation:d.graph.studioPresentation||null,authoring:d.authoring?{nodes:d.authoring.nodes.length,edges:d.authoring.edges.length,workspace:d.authoring.workspaceId}:null};
 };
});
const command=(name,payload={},facts=false)=>page.evaluate(({name,payload,facts})=>window.__largeCommand(name,payload,facts),{name,payload,facts});
const snapshot=()=>command('snapshot');
async function ready(){await page.waitForFunction(()=>document.querySelector('iframe')&&document.querySelector('.semantic-frontier .segmented button')&&!document.querySelector('.semantic-frontier .segmented button').disabled,{timeout:180000});}
async function idle(){await page.waitForFunction(()=>document.querySelector('.semantic-frontier .segmented button')&&!document.querySelector('.semantic-frontier .segmented button').disabled,{timeout:180000});return snapshot();}
async function menu(name){await page.locator('.workspace-menu > summary').click();await page.getByRole('button',{name,exact:true}).click();}
const cdp=await browser.newBrowserCDPSession();
async function memory(label){const {processInfo}=await cdp.send('SystemInfo.getProcessInfo');let aggregateRssBytes=0;for(const p of processInfo){try{const text=await fs.readFile('/proc/'+p.id+'/status','utf8'),kb=Number(text.match(/^VmRSS:\s+(\d+)/m)?.[1]||0);aggregateRssBytes+=kb*1024;}catch{}}const value={label,aggregateRssBytes,processes:processInfo.length,note:'sum of live Chromium process RSS; shared pages can be counted more than once; includes test probes'};measurements.push(value);console.log('MEMORY',JSON.stringify(value));}
async function routeComplete(doc){for(let i=0;i<5&&!doc.routing?.complete;i++){doc=await command('continue-routing',{},true);console.log('ROUTE',JSON.stringify(doc.routing));}assert.equal(doc.routing.complete,true);return doc;}
async function saveReload(){console.log('SAVE begin');await page.getByRole('button',{name:'保存',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.save-state')?.textContent.includes('已保存'));const saved=await snapshot();console.log('SAVE marked',saved.caseId);await page.reload({waitUntil:'networkidle'});await ready();console.log('RELOAD ready');const doc=await snapshot();assert.equal(doc.caseId,saved.caseId);assert.equal(doc.geometry,saved.geometry);assert.deepEqual(doc.camera,saved.camera);await page.waitForFunction(()=>document.querySelector('.save-state')?.textContent.includes('已保存'));assert.equal(await page.locator('.save-state').innerText(),'已保存');return doc;}
try{
 await page.goto(base,{waitUntil:'networkidle'});await ready();sourceWrites.length=0;
 const catalog=await(await page.request.get(base+'/preview/data/semantic/studio-catalog.json')).json();
 await menu('Summary 模型库');assert.equal(await page.locator('.summary-catalog select option:disabled').count(),0);
 for(const title of ['Transformer · 语义架构','ForeignComposition','Transformer · CPU 运行证据']){
  const model=catalog.models.find(m=>m.title===title),started=Date.now();await page.evaluate(async url=>{window.__largeReference=await(await fetch(url)).json();},base+'/preview/data/semantic/'+model.ir.path);
  await page.locator('.summary-catalog select').selectOption(model.id);await page.getByRole('button',{name:'打开 Summary 模型',exact:true}).click();await ready();
  let doc=await command('snapshot',{},true);assert.equal(doc.digest,model.digest);assert.deepEqual(doc.total,[model.nodes,model.edges]);doc=await routeComplete(doc);await memory(title+' F0');
  const overview=doc;doc=await command('set-frontier',{preset:'detail'},true);doc=await routeComplete(doc);await memory(title+' F1');
  await command('set-frontier',{preset:'overview'},true);
  const hidden=await page.evaluate(()=>{const d=window.__largeLast,visible=new Set(d.graph.nodes.map(n=>n.id));return d.graph.generic.ir.nodes.find(n=>!visible.has(n.id)&&!d.graph.generic.ir.nodes.some(c=>c.parent===n.id))?.id;});
  if(hidden){await command('focus',{nodeId:hidden});doc=await command('snapshot',{},true);assert.equal(await page.evaluate(id=>window.__largeLast.graph.nodes.some(n=>n.id===id),hidden),true);await routeComplete(doc);await command('set-frontier',{preset:'overview'},true);}
  checks.push(title+': Studio catalog, complete IR/accounting, F0/F1, explicit routing continuation and exact hidden-node focus');
  if(title==='Transformer · 语义架构'&&!args.includes('--skip-history')){
   doc=await snapshot();const before=doc,node=doc.firstNode;
   for(let i=0;i<30;i++){doc=await command('visual',{operations:[{type:'alias',id:node,label:'大图历史 '+i}]});if(i===14||i===29)await memory(title+' history '+(i+1));}
   assert.equal(doc.undo,30);assert.equal(doc.presentation.nodes[node].alias,'大图历史 29');const edited=doc;
   for(let i=0;i<30;i++)doc=await command('undo');assert.equal(doc.undo,0);assert.equal(doc.geometry,before.geometry);assert.deepEqual(doc.presentation,before.presentation);
   for(let i=0;i<30;i++)doc=await command('redo');assert.equal(doc.redo,0);assert.equal(doc.geometry,edited.geometry);assert.deepEqual(doc.presentation,edited.presentation);await command('snapshot',{},true);
   checks.push(title+': thirty actual presentation edits plus thirty undo and redo operations retain complete facts and exact geometry');
  }
  doc=await saveReload();await memory(title+' saved/reloaded');
  // The JSON is generated by the product's actual export command, then read
  // through Studio's file input rather than bypassing its file-size contract.
  const downloading=page.waitForEvent('download');await command('export-json');const download=await downloading,path=output.replace(/\.json$/,'-'+model.id+'.json');await download.saveAs(path);const bytes=(await fs.stat(path)).size;
  if(title==='Transformer · 语义架构')assert.ok(bytes>16000000);assert.ok(bytes<128000000);
  const before=await snapshot();await menu('导入 Python 源码');await page.getByRole('tab',{name:'工程目录 / 已有文档',exact:true}).click();await page.getByLabel('选择源文件',{exact:true}).setInputFiles(path);await page.getByRole('dialog',{name:'打开模型',exact:true}).waitFor({state:'hidden'});await ready();doc=await snapshot();assert.equal(doc.geometry,before.geometry);assert.equal(doc.caseId,before.caseId);assert.deepEqual(doc.presentation,before.presentation);assert.deepEqual(doc.camera,before.camera);
  checks.push(title+': IndexedDB/browser save, refresh marker and actual portable JSON export/file import preserve complete geometry and presentation ('+bytes+' bytes)');
  await page.getByRole('group',{name:'工作区模式'}).getByRole('button',{name:'编辑',exact:true}).click();await page.getByRole('heading',{name:'Summary 模型编辑',exact:true}).waitFor();doc=await idle();assert.equal(doc.authoring.nodes,model.nodes);assert.equal(doc.authoring.edges,model.edges);
  await command('authoring',{action:'title',title:'大图编辑 · '+title});doc=await snapshot();assert.ok(doc.authoring);await page.getByRole('group',{name:'工作区模式'}).getByRole('button',{name:'视图',exact:true}).click();assert.equal(await page.getByRole('group',{name:'工作区模式'}).getByRole('button',{name:'视图',exact:true}).getAttribute('aria-pressed'),'true');await saveReload();
  checks.push(title+': full native authoring copy, title edit, return to view and saved authored restore through retained Studio panels');
  models.push({title,nodes:model.nodes,edges:model.edges,jsonBytes:bytes,elapsedMs:Date.now()-started,overview:overview.visible});
  await menu('Summary 模型库');await memory(title+' edit/reloaded');
 }
 assert.deepEqual(errors,[]);assert.deepEqual(sourceWrites,[]);checks.push('three large models switch in one retained Studio session without Python execution, source writes or runtime/transaction requests');
 await page.screenshot({path:output.replace(/\.json$/,'.png'),fullPage:true});
 await fs.writeFile(output,JSON.stringify({ok:true,historyScope:args.includes('--skip-history')?'Prior retained browser evidence covers thirty edits/undo/redo; this run covers final save/reload and model roundtrips.':'Thirty edits/undo/redo included.',checks,models,measurements,browserErrors:errors,sourceWrites},null,2)+'\n');console.log(JSON.stringify({ok:true,checks:checks.length,output}));
}catch(error){const state=await page.evaluate(()=>({status:document.querySelector('.statusbar')?.textContent,save:document.querySelector('.save-state')?.textContent,active:localStorage.getItem('archcanvas.active-canvas.v2'),markers:Object.keys(localStorage).filter(k=>k.startsWith('archcanvas.preview-saved.v1:')).map(k=>[k,localStorage.getItem(k)]),lastCase:window.__largeLast?.caseId})).catch(()=>null);console.log('FAIL STATE',JSON.stringify(state));await page.screenshot({path:output.replace(/\.json$/,'-failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(output,JSON.stringify({ok:false,checks,models,measurements,browserErrors:errors,sourceWrites,state,error:String(error)},null,2)+'\n');throw error;}finally{await browser.close();}
