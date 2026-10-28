import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const args=process.argv.slice(2),option=(name,fallback)=>args.includes(name)?args[args.indexOf(name)+1]:fallback;
const {chromium}=await import(option('--playwright')?pathToFileURL(option('--playwright')).href:'playwright');
const base=option('--base','http://127.0.0.1:8789'),output=option('--output','/tmp/summary-host-source-browser.json');
const browser=await chromium.launch({headless:true,...(option('--chromium')?{executablePath:option('--chromium')}:{}),args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1600,height:1100},acceptDownloads:true}),checks=[],errors=[];
page.setDefaultTimeout(120000);page.setDefaultNavigationTimeout(120000);page.on('pageerror',error=>errors.push(error.message));
checks.push=(...values)=>{for(const value of values)console.log('PASS',value);return Array.prototype.push.apply(checks,values);};
async function command(name,payload={},inspect=false){return page.evaluate(({name,payload,inspect})=>new Promise((resolve,reject)=>{
 const child=document.querySelector('iframe').contentWindow,requestId=crypto.randomUUID();
 const timer=setTimeout(()=>{window.removeEventListener('message',listen);reject(Error('timeout '+name));},120000);
 function listen(event){if(event.source!==child||event.origin!==location.origin||event.data?.requestId!==requestId)return;clearTimeout(timer);window.removeEventListener('message',listen);const data=event.data;
  if(data.type.endsWith(':error')){reject(Error(data.message));return;}
  if(!inspect){resolve(data);return;}
  const d=data.document,ir=d.graph.generic.ir;let occurrences=0;const unique=new Set();
  function walk(value){if(!value||typeof value!=='object')return;if(value.schema==='archcanvas-source-semantic/2'&&Array.isArray(value.nodes)&&Array.isArray(value.edges)){occurrences++;unique.add(value);return;}for(const item of Object.values(value))walk(item);}
  walk(d);resolve({nativeSchema:d.nativeDocument.document.schema,sourceSchemas:[...unique].map(value=>({schema:value.schema,keys:Object.keys(value),digest:value.ir_digest})),occurrences,uniqueSources:unique.size,sourceMatches:JSON.stringify(ir)===JSON.stringify(d.nativeDocument.document.schema==='archcanvas-source-semantic/2'?d.nativeDocument.document:d.nativeDocument.document.baseline),originalMatches:ir===(d.nativeDocument.document.schema==='archcanvas-source-semantic/2'?d.nativeDocument.document:d.nativeDocument.document.baseline),graphAuthoringMatches:!d.graph.generic.authoring||ir===d.graph.generic.authoring.baseline,caseId:d.caseId});
 }
 window.addEventListener('message',listen);child.postMessage({type:'archcanvas:preview:'+name,...payload,requestId},location.origin);
}),{name,payload,inspect});}
const snapshot=async()=>(await command('snapshot')).document;
const ready=()=>page.waitForFunction(()=>document.querySelector('iframe')&&!document.querySelector('.semantic-frontier .segmented button')?.disabled);
try{
 await page.goto(base,{waitUntil:'networkidle'});await ready();
 const catalog=await(await page.request.get(base+'/preview/data/semantic/studio-catalog.json')).json(),model=catalog.models.find(m=>m.title==='SameSource'),ir=await(await page.request.get(base+'/preview/data/semantic/'+model.ir.path)).json();
 await page.locator('.workspace-menu > summary').click();await page.getByRole('button',{name:'Summary 模型库',exact:true}).click();
 const panel=page.locator('.summary-catalog');await panel.getByRole('combobox',{name:'Summary 目录模型',exact:true}).selectOption(model.id);await panel.getByRole('button',{name:'打开 Summary 模型',exact:true}).click();
 await page.waitForFunction(id=>document.querySelector('.summary-catalog select')?.value===id,model.id);
 let doc;for(let i=0;i<100;i++){doc=await snapshot();if(!doc.busy&&doc.graph?.generic?.ir?.ir_digest===model.digest)break;await new Promise(resolve=>setTimeout(resolve,100));}
 assert.deepEqual(doc.graph.generic.ir,ir);
 let sharing=await command('snapshot',{},true);console.log('HOST SHARING',JSON.stringify(sharing));assert.ok(sharing.occurrences>=2);assert.equal(sharing.uniqueSources,1);assert.equal(sharing.originalMatches,true);assert.equal(sharing.sourceMatches,true);
 checks.push('actual parent receives one shared complete source IR across native graph and original imported document');
 for(const preset of ['detail','overview']){await command('set-frontier',{preset});const current=await snapshot();assert.deepEqual(current.graph.generic.ir,ir);sharing=await command('snapshot',{},true);assert.equal(sharing.uniqueSources,1);assert.equal(sharing.originalMatches,true);}
 checks.push('F0/F1 messages preserve all source facts and reuse a single source object within each real structured-clone packet');
 await command('authoring',{action:'begin'});doc=await snapshot();assert.equal(doc.nativeDocument.schema,'archcanvas-summary-authoring/1');
 sharing=await command('snapshot',{},true);assert.ok(sharing.occurrences>=3);assert.equal(sharing.uniqueSources,1);assert.equal(sharing.graphAuthoringMatches,true);assert.equal(sharing.originalMatches,true);
 checks.push('Summary editing shares original source across canonical graph, authoring model and original workspace while Studio panels remain active');
 const saved=(await command('save')).document;
 const frame=page.frames().find(frame=>frame.url().includes('yworks_edge_router_lab'));
 const persisted=await frame.evaluate(key=>new Promise((resolve,reject)=>{const request=indexedDB.open('summary-merge-recursive',1);request.onerror=()=>reject(request.error);request.onsuccess=()=>{const db=request.result,get=db.transaction('models','readonly').objectStore('models').get(key);get.onerror=()=>reject(get.error);get.onsuccess=()=>{resolve(get.result);db.close();};};}),saved.caseId+':unified');
 assert.equal(persisted.version,5);assert.deepEqual(persisted.graph.generic.ir,saved.graph.generic.ir);assert.deepEqual(persisted.graph.nodes,saved.graph.nodes);assert.deepEqual(persisted.graph.studioCamera,saved.graph.studioCamera);
 checks.push('explicit save persists full independent geometry and camera in actual IndexedDB without host-document roundtrip');
 const downloadEvent=page.waitForEvent('download');await command('export-json');const download=await downloadEvent;const portable=JSON.parse(await fs.readFile(await download.path(),'utf8'));
 assert.equal(portable.schema,'summary-merge-recursive/1');assert.deepEqual(portable.graph.generic.ir,saved.graph.generic.ir);await command('load',{bundle:portable});doc=await snapshot();assert.deepEqual(doc.graph.nodes,saved.graph.nodes);
 checks.push('portable JSON retains the existing complete format and reimports through native source and geometry validators');
 await page.getByRole('button',{name:'保存',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('.save-state')?.classList.contains('dirty'));
 const before=await snapshot();await page.reload({waitUntil:'networkidle'});await ready();doc=await snapshot();assert.equal(doc.caseId,before.caseId);assert.deepEqual(doc.graph.generic.ir,before.graph.generic.ir);assert.deepEqual(doc.graph.nodes,before.graph.nodes);
 await page.waitForFunction(()=>document.querySelector('.save-state')?.textContent.trim()==='已保存');
 sharing=await command('snapshot',{},true);assert.equal(sharing.uniqueSources,1);assert.equal(sharing.originalMatches,true);assert.deepEqual(errors,[]);
 checks.push('save and page reload restore the complete native edit document and reestablish exact sharing without browser errors');
 await page.screenshot({path:output.replace(/\.json$/,'.png'),fullPage:true});await fs.writeFile(output,JSON.stringify({ok:true,checks,browserErrors:errors,finalSharing:sharing,scope:'Reference sharing within actual messages; not cross-message transfer caching, compact portable JSON or large-model acceptance.'},null,2)+'\n');
}catch(error){await page.screenshot({path:output.replace(/\.json$/,'-failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(output,JSON.stringify({ok:false,checks,browserErrors:errors,error:String(error)},null,2)+'\n');throw error;}finally{await browser.close();}
