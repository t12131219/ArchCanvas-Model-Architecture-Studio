import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const {chromium}=await import(option('--playwright')?pathToFileURL(option('--playwright')).href:'playwright');
const base=option('--base','http://127.0.0.1:8789'),output=option('--output','/tmp/summary-cancellation-browser.json');
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
 const NativeWorker=window.Worker;
 const probe=window.__cancelProbe={workers:[],holdNext:false,held:[],sent:[]};
 window.Worker=class extends NativeWorker{
  constructor(...args){super(...args);this.terminated=false;probe.workers.push(this);this.addEventListener('message',event=>{if(probe.holdNext){probe.holdNext=false;probe.held.push({owner:this,event});}else this.reply?.(event);});}
  set onmessage(value){this.reply=value;}get onmessage(){return this.reply;}
  postMessage(message,...rest){probe.sent.push({task:message.task,core:!!message.graph?.core});super.postMessage(message,...rest);}
  terminate(){this.terminated=true;super.terminate();}
 };
});
const frame=()=>page.frames().find(f=>f.url().includes('yworks_edge_router_lab'));
try{
 await page.goto(base,{waitUntil:'networkidle'});await ready();sourceWrites.length=0;
 const catalog=await(await page.request.get(base+'/preview/data/semantic/studio-catalog.json')).json(),model=catalog.models.find(m=>m.title===option('--model-title','SameSource')),ir=await(await page.request.get(base+'/preview/data/semantic/'+model.ir.path)).json();
 await menu('Summary 模型库');const panel=page.locator('.summary-catalog');await panel.getByRole('combobox',{name:'Summary 目录模型',exact:true}).selectOption(model.id);await panel.getByRole('button',{name:'打开 Summary 模型',exact:true}).click();await waitFor(d=>d.graph?.generic?.ir?.ir_digest===model.digest);
 let doc=await snapshot();facts(doc,ir);
 await command('select-nodes',{scope:'all'});await command('zoom',{factor:1.1});
 const before=await snapshot();
 async function cancelPending(name,payload,method='button'){
  await frame().evaluate(()=>window.__cancelProbe.holdNext=true);
  const outcome=command(name,payload).then(value=>({value}),error=>({error:String(error)}));
  await page.waitForFunction(()=>!!document.querySelector('iframe')?.contentWindow.__cancelProbe?.sent.length);
  await page.getByRole('button',{name:'取消当前图操作',exact:true}).waitFor({state:'visible'});
  if(method==='escape')await page.keyboard.press('Escape');else await page.getByRole('button',{name:'取消当前图操作',exact:true}).click();
  const result=await outcome;assert.match(result.error,/取消|加载失败/);await waitFor(d=>!d.canCancel);
  const after=await snapshot();assert.deepEqual(after.graph,before.graph);assert.equal(after.undo,before.undo);assert.equal(after.redo,before.redo);assert.equal(after.dirty,before.dirty);assert.deepEqual(after.selectedNodes,before.selectedNodes);assert.deepEqual(after.selectedEdges,before.selectedEdges);
  await frame().evaluate(()=>{const p=window.__cancelProbe;p.holdNext=false;for(const held of p.held.splice(0))held.owner.reply?.(held.event);});
  const late=await snapshot();assert.deepEqual(late.graph,before.graph);assert.equal(late.undo,before.undo);
  return after;
 }
 await cancelPending('set-frontier',{preset:'detail'});
 checks.push('Studio cancel button terminates a pending frontier operation and preserves exact graph, camera, selection, dirty flag and undo/redo');
 await cancelPending('load',{bundle:ir},'escape');
 checks.push('Escape rejects an in-flight document load before registration and leaves the current model untouched');
 const count=await frame().evaluate(()=>window.__cancelProbe.workers.length);
 await command('set-frontier',{preset:'detail'});doc=await waitFor(d=>d.frontierPreset==='detail');facts(doc,ir);assert.equal(doc.undo,before.undo+1);
 let probe=await frame().evaluate(()=>({count:window.__cancelProbe.workers.length,terminated:window.__cancelProbe.workers.filter(w=>w.terminated).length,sent:window.__cancelProbe.sent}));
 assert.equal(probe.count,count+1);assert.ok(probe.terminated>=2);assert.ok(probe.sent.at(-1).core);
 checks.push('next real action creates a fresh Worker with full canonical source, commits once, and ignores abandoned replies');
 await command('undo');doc=await snapshot();assert.deepEqual(doc.graph.nodes,before.graph.nodes);await command('redo');doc=await snapshot();facts(doc,ir);
 await page.getByRole('button',{name:'保存',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('.save-state')?.classList.contains('dirty'));
 const saved=await snapshot();await page.reload({waitUntil:'networkidle'});await ready();doc=await waitFor(d=>d.caseId===saved.caseId);facts(doc,ir);assert.deepEqual(doc.graph.nodes,saved.graph.nodes);
 assert.equal(doc.canCancel,false);assert.deepEqual(errors,[]);assert.deepEqual(sourceWrites,[]);
 checks.push('undo/redo, save and refresh still work after cancellation, with Studio panels retained and no model execution or source writes');
 await page.screenshot({path:output.replace(/\.json$/,'.png'),fullPage:true});
 await fs.writeFile(output,JSON.stringify({ok:true,checks,browserErrors:errors,sourceWrites,workerProbe:probe},null,2)+'\n');console.log(JSON.stringify({ok:true,checks:checks.length,output}));
}catch(error){await page.screenshot({path:output.replace(/\.json$/,'-failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(output,JSON.stringify({ok:false,checks,browserErrors:errors,sourceWrites,error:String(error)},null,2)+'\n');throw error;}finally{await browser.close();}
