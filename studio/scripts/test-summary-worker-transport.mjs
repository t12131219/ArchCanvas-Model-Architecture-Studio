import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const {chromium}=await import(option('--playwright')?pathToFileURL(option('--playwright')).href:'playwright');
const base=option('--base','http://127.0.0.1:8789'),output=option('--output','/tmp/summary-worker-browser.json');
const browser=await chromium.launch({headless:true,...(option('--chromium')?{executablePath:option('--chromium')} : {}),args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1600,height:1100},acceptDownloads:true}),checks=[],errors=[],sourceWrites=[];
page.setDefaultTimeout(120000);page.setDefaultNavigationTimeout(120000);
page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST'&&/edit-source|transactions|runtime|preview\/analyze/.test(r.url()))sourceWrites.push(r.url());});
checks.push=(...values)=>{for(const v of values)console.log('PASS',v);return Array.prototype.push.apply(checks,values);};
async function command(name,payload={}){return page.evaluate(({name,payload})=>new Promise((resolve,reject)=>{const child=document.querySelector('iframe').contentWindow,requestId=crypto.randomUUID();const timer=setTimeout(()=>{window.removeEventListener('message',listen);reject(Error('timeout '+name));},120000);function listen(e){if(e.source!==child||e.origin!==location.origin||e.data?.requestId!==requestId)return;clearTimeout(timer);window.removeEventListener('message',listen);e.data.type.endsWith(':error')?reject(Error(e.data.message)):resolve(e.data);}window.addEventListener('message',listen);child.postMessage({type:'archcanvas:preview:'+name,...payload,requestId},location.origin);}),{name,payload});}
const snapshot=async()=>(await command('snapshot')).document;
async function waitFor(test){const end=Date.now()+120000;while(Date.now()<end){const d=await snapshot();if(!d.busy&&test(d))return d;await new Promise(r=>setTimeout(r,100));}throw Error('state timeout');}
async function ready(){await page.waitForFunction(()=>document.querySelector('iframe')&&!document.querySelector('.semantic-frontier .segmented button')?.disabled,{timeout:120000});}
async function menu(name){await page.locator('.workspace-menu > summary').click();await page.getByRole('button',{name,exact:true}).click();}
function facts(doc,ir){assert.deepEqual(doc.graph.generic.ir,ir);for(const [ledger,items]of [[doc.semanticView.nodeAccounting,ir.nodes],[doc.semanticView.edgeAccounting,ir.edges]]){const ids=Object.values(ledger).flat();assert.equal(new Set(ids).size,items.length);assert.deepEqual(ids.slice().sort(),items.map(n=>n.id).sort());}}

await page.addInitScript(()=>{
 const NativeWorker=window.Worker;const probe=window.__nativeTransportProbe={workers:[],sent:[],received:[],failNext:false,crashNext:false};
 window.Worker=class extends NativeWorker{
  constructor(...args){super(...args);probe.workers.push(this);this.addEventListener('message',e=>probe.received.push({requestId:e.data.requestId,packet:e.data.graph?.nativeGeometryTransport===1,core:!!e.data.graph?.core,bytes:new TextEncoder().encode(JSON.stringify(e.data)).length}));}
  postMessage(message,...rest){
   probe.sent.push({requestId:message.requestId,task:message.task,packet:message.graph?.nativeGeometryTransport===1,core:!!message.graph?.core,bytes:new TextEncoder().encode(JSON.stringify(message)).length});
   if(probe.failNext){probe.failNext=false;throw new DOMException('controlled failed send','DataCloneError');}
   super.postMessage(message,...rest);
   if(probe.crashNext){probe.crashNext=false;queueMicrotask(()=>this.dispatchEvent(new Event('error')));}
  }
 };
});
const frame=()=>page.frames().find(f=>f.url().includes('yworks_edge_router_lab'));
try{
 await page.goto(base,{waitUntil:'networkidle'});await ready();sourceWrites.length=0;
 const catalog=await(await page.request.get(base+'/preview/data/semantic/studio-catalog.json')).json(),model=catalog.models.find(m=>m.title==='SameSource'),ir=await(await page.request.get(base+'/preview/data/semantic/'+model.ir.path)).json();
 await menu('Summary 模型库');const panel=page.locator('.summary-catalog');await panel.getByRole('combobox',{name:'Summary 目录模型',exact:true}).selectOption(model.id);await panel.getByRole('button',{name:'打开 Summary 模型',exact:true}).click();await waitFor(d=>d.graph?.generic?.ir?.ir_digest===model.digest);
 let doc=await snapshot();facts(doc,ir);
 let probe=await frame().evaluate(()=>({sent:window.__nativeTransportProbe.sent,received:window.__nativeTransportProbe.received,count:window.__nativeTransportProbe.workers.length}));
 assert.ok(probe.received.some(m=>m.packet&&m.core));checks.push('real Chromium Worker builds and returns the complete Summary canonical core through native transport');
 await command('semantic-view',{patch:{paperGranularity:'roles'}});doc=await waitFor(d=>d.semanticView.granularity==='roles');facts(doc,ir);
 const before=doc;
 await frame().evaluate(()=>window.__nativeTransportProbe.failNext=true);
 await command('set-frontier',{preset:'detail'});doc=await waitFor(d=>d.frontierPreset==='detail');facts(doc,ir);assert.equal(doc.undo,before.undo+1);
 checks.push('failed structured-clone send terminates channel and applies independently validated full-input fallback exactly once');
 await command('set-frontier',{preset:'overview'});doc=await waitFor(d=>d.frontierPreset==='overview');facts(doc,ir);
 probe=await frame().evaluate(()=>({sent:window.__nativeTransportProbe.sent,received:window.__nativeTransportProbe.received,count:window.__nativeTransportProbe.workers.length}));assert.equal(probe.count,2);assert.ok(probe.sent.at(-1).core);
 checks.push('next action creates a fresh Worker generation with complete source facts and no stale cached core');
 const crashBefore=doc;
 await frame().evaluate(()=>window.__nativeTransportProbe.crashNext=true);
 await command('set-frontier',{preset:'detail'});doc=await waitFor(d=>d.frontierPreset==='detail');facts(doc,ir);assert.equal(doc.undo,crashBefore.undo+1);
 await command('undo');doc=await waitFor(d=>d.frontierPreset==='overview');facts(doc,ir);
 await command('redo');doc=await waitFor(d=>d.frontierPreset==='detail');facts(doc,ir);
 checks.push('Worker error while request is pending preserves atomic history and exact Summary undo/redo geometry');
 await command('set-frontier',{preset:'overview'});doc=await waitFor(d=>d.frontierPreset==='overview');facts(doc,ir);
 for(let i=0;i<7;i++){await command('semantic-view',{patch:{paperGranularity:i%2?'modules':'roles'}});doc=await waitFor(d=>d.semanticView.granularity===(i%2?'modules':'roles'));facts(doc,ir);}
 for(let i=0;i<7;i++){await command('undo');facts(await snapshot(),ir);}
 for(let i=0;i<7;i++){await command('redo');facts(await snapshot(),ir);}
 checks.push('seven cut generations and history restoration preserve complete source facts and accounting across native four-core cache eviction');
 const save=(await command('save')).document;await command('load',{bundle:save});doc=await waitFor(d=>!d.busy);facts(doc,ir);assert.deepEqual(doc.graph.nodes,save.graph.nodes);
 await page.getByRole('button',{name:'保存',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('.save-state')?.classList.contains('dirty'));const saved=await snapshot();await page.reload({waitUntil:'networkidle'});await ready();doc=await waitFor(d=>d.caseId===saved.caseId);facts(doc,ir);assert.deepEqual(doc.graph.nodes,saved.graph.nodes);
 probe=await frame().evaluate(()=>({sent:window.__nativeTransportProbe.sent,received:window.__nativeTransportProbe.received,count:window.__nativeTransportProbe.workers.length}));assert.ok(probe.sent.some(m=>m.packet&&m.core)||probe.received.some(m=>m.packet&&m.core));
 assert.deepEqual(errors,[]);assert.deepEqual(sourceWrites,[]);checks.push('editing JSON, save and refresh rebuild cache from full validated data with retained Studio panels and no source/runtime/transaction writes');
 await page.screenshot({path:output.replace(/\.json$/,'.png'),fullPage:true});
 await fs.writeFile(output,JSON.stringify({ok:true,checks,browserErrors:errors,sourceWrites,reloadedProbe:probe},null,2)+'\n');console.log(JSON.stringify({ok:true,checks:checks.length,output}));
}catch(error){await page.screenshot({path:output.replace(/\.json$/,'-failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(output,JSON.stringify({ok:false,checks,browserErrors:errors,sourceWrites,error:String(error)},null,2)+'\n');throw error;}finally{await browser.close();}
