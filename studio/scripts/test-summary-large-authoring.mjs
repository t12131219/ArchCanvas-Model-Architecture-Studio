import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const {chromium}=await import(option('--playwright')?pathToFileURL(option('--playwright')).href:'playwright');
const base=option('--base','http://127.0.0.1:8789'),output=option('--output','/tmp/summary-large-authoring.json');
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
 for(const title of ['Transformer · 语义架构','ForeignComposition','Transformer · CPU 运行证据']){
  const model=catalog.models.find(m=>m.title===title);await page.evaluate(async url=>{window.__largeReference=await(await fetch(url)).json();},base+'/preview/data/semantic/'+model.ir.path);
  await menu('Summary 模型库');await page.locator('.summary-catalog select').selectOption(model.id);await page.getByRole('button',{name:'打开 Summary 模型',exact:true}).click();await ready();await command('snapshot',{},true);
  await page.getByRole('group',{name:'工作区模式'}).getByRole('button',{name:'编辑',exact:true}).click();await page.getByRole('heading',{name:'Summary 模型编辑',exact:true}).waitFor();let doc=await idle();assert.equal(doc.authoring.nodes,model.nodes);assert.equal(doc.authoring.edges,model.edges);
  await command('authoring',{action:'title',title:'大图便携编辑 · '+title});doc=await snapshot();
  const baseline=await page.evaluate(()=>{const d=window.__largeLast,a=d.graph.generic.authoring;return {equal:JSON.stringify(a.baseline)===JSON.stringify(window.__largeReference),nodes:a.nodes.length,edges:a.edges.length,sourceVerified:d.importedDocument.sourceVerified,modelExecuted:d.importedDocument.modelExecuted};});assert.equal(baseline.equal,true);assert.equal(baseline.sourceVerified,false);assert.equal(baseline.modelExecuted,false);
  const exporting=page.waitForEvent('download');await command('export-json');const download=await exporting,path=output.replace(/\.json$/,'-'+model.id+'-authoring.json');await download.saveAs(path);const bytes=(await fs.stat(path)).size;assert.ok(bytes<128000000);if(model.nodes>3000)assert.ok(bytes>16000000);
  const before=await snapshot();await menu('导入 Python 源码');await page.getByRole('tab',{name:'工程目录 / 已有文档',exact:true}).click();await page.getByLabel('选择源文件',{exact:true}).setInputFiles(path);await page.getByRole('dialog',{name:'打开模型',exact:true}).waitFor({state:'hidden'});await ready();doc=await snapshot();assert.equal(doc.caseId,before.caseId);assert.equal(doc.geometry,before.geometry);assert.deepEqual(doc.presentation,before.presentation);assert.deepEqual(doc.camera,before.camera);assert.equal(doc.authoring.nodes,model.nodes);assert.equal(doc.authoring.edges,model.edges);
  await saveReload();await memory(title+' authoring JSON restored');models.push({title,jsonBytes:bytes,nodes:model.nodes,edges:model.edges});checks.push(title+': full edited workspace baseline and all nodes/edges survive actual product JSON export, Studio file import, IndexedDB save and refresh without source/runtime authority');
 }
 assert.deepEqual(errors,[]);assert.deepEqual(sourceWrites,[]);await page.screenshot({path:output.replace(/\.json$/,'.png'),fullPage:true});await fs.writeFile(output,JSON.stringify({ok:true,checks,models,measurements,browserErrors:errors,sourceWrites},null,2)+'\n');console.log(JSON.stringify({ok:true,checks:checks.length,output}));
}catch(error){const state=await page.evaluate(()=>({status:document.querySelector('.statusbar')?.textContent,save:document.querySelector('.save-state')?.textContent,active:localStorage.getItem('archcanvas.active-canvas.v2'),markers:Object.keys(localStorage).filter(k=>k.startsWith('archcanvas.preview-saved.v1:')).map(k=>[k,localStorage.getItem(k)]),lastCase:window.__largeLast?.caseId})).catch(()=>null);console.log('FAIL STATE',JSON.stringify(state));await page.screenshot({path:output.replace(/\.json$/,'-failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(output,JSON.stringify({ok:false,checks,models,measurements,browserErrors:errors,sourceWrites,state,error:String(error)},null,2)+'\n');throw error;}finally{await browser.close();}
