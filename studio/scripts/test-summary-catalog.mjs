import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
const args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const {chromium}=await import(option('--playwright')?pathToFileURL(option('--playwright')).href:'playwright');
const output=option('--output','/tmp/summary-catalog-browser.json'),base=option('--base','http://127.0.0.1:8789');
const browser=await chromium.launch({headless:true,...(option('--chromium')?{executablePath:option('--chromium')} : {}),args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1600,height:1100}}),checks=[],errors=[],writes=[],requests=[];
page.setDefaultNavigationTimeout(120000);page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{requests.push(r.url());if(r.method()==='POST'&&/transactions|runtime\/run/.test(r.url()))writes.push(r.url());});
checks.push=(...values)=>{for(const v of values)console.log('PASS',v);return Array.prototype.push.apply(checks,values);};
async function command(name,payload={}){return page.evaluate(({name,payload})=>new Promise((resolve,reject)=>{const child=document.querySelector('iframe').contentWindow,requestId=crypto.randomUUID();const timer=setTimeout(()=>{window.removeEventListener('message',listen);reject(Error('timeout '+name));},60000);function listen(e){if(e.source!==child||e.origin!==location.origin||e.data?.requestId!==requestId)return;clearTimeout(timer);window.removeEventListener('message',listen);e.data.type.endsWith(':error')?reject(Error(e.data.message)):resolve(e.data);}window.addEventListener('message',listen);child.postMessage({type:'archcanvas:preview:'+name,...payload,requestId},location.origin);}),{name,payload});}
const snapshot=async()=>(await command('snapshot')).document;
async function waitFor(test){const end=Date.now()+60000;while(Date.now()<end){const d=await snapshot();if(!d.busy&&test(d))return d;await new Promise(r=>setTimeout(r,100));}throw Error('state timeout');}
async function ready(){await page.waitForFunction(()=>document.querySelector('iframe')&&!document.querySelector('.semantic-frontier .segmented button')?.disabled,{timeout:60000});}
async function menu(name){await page.locator('.workspace-menu > summary').click();await page.getByRole('button',{name,exact:true}).click();}
async function open(model){await page.getByRole('textbox',{name:'搜索 Summary 模型',exact:true}).fill('');await page.getByRole('combobox',{name:'Summary 目录模型',exact:true}).selectOption(model.id);await page.getByRole('button',{name:'打开 Summary 模型',exact:true}).click();return waitFor(d=>d.graph?.generic?.ir?.ir_digest===model.digest);}
try{
 await page.goto(base,{waitUntil:'networkidle'});await ready();await menu('Summary 模型库');
 const panel=page.locator('.summary-catalog');await panel.getByRole('button',{name:'打开 Summary 模型',exact:true}).waitFor();
 const catalog=await(await page.request.get(base+'/preview/data/semantic/studio-catalog.json')).json();assert.equal(catalog.models.length,43);
 assert.equal(await panel.locator('select option').count(),43);assert.equal(await panel.locator('select option:disabled').count(),0);
 assert.equal(requests.filter(u=>/\/data\/semantic\//.test(u)&&!u.endsWith('studio-catalog.json')&&!u.endsWith('authoring-presets.json')).length,0);
 assert.equal(await page.frameLocator('iframe').locator('html.studio-library-open').count(),0);
 checks.push('Studio menu opens the retained folding inspector with 43 catalog entries, 43 available under verified bounds, without eager model downloads');
 await panel.getByRole('textbox',{name:'搜索 Summary 模型',exact:true}).fill('Transformer');assert.equal(await panel.locator('select option:disabled').evaluateAll(options=>options.filter(option=>option.value).length),0);assert.equal(await panel.getByRole('button',{name:'打开 Summary 模型',exact:true}).isDisabled(),false);
 await panel.getByRole('textbox',{name:'搜索 Summary 模型',exact:true}).fill('');
 const model=catalog.models.find(m=>m.title==='BranchMLP'),original=await(await page.request.get(base+'/preview/data/semantic/'+model.ir.path)).json();
 let doc=await open(model);assert.deepEqual(doc.graph.generic.ir,original);assert.equal(doc.graph.sourceAdapter,undefined);assert.equal(doc.importedDocument.sourceVerified,false);
 const frame=page.locator('iframe');await frame.evaluate(el=>el.dataset.catalogIdentity='same');
 assert.ok(await page.getByRole('tree',{name:'模型层级',exact:true}).getByRole('treeitem').count()>0);
 checks.push('catalog loading preserves complete archived static/runtime facts and exact identities, updates the Studio hierarchy, and grants no formal source binding');
 const before=doc.graph.generic.ir;await command('set-frontier',{preset:'detail'});doc=await waitFor(d=>d.frontierPreset==='detail');assert.deepEqual(doc.graph.generic.ir,before);
 await command('set-frontier',{preset:'overview'});doc=await waitFor(d=>d.frontierPreset==='overview');assert.deepEqual(doc.graph.generic.ir,before);
 const validation=await frame.evaluate((el,graph)=>el.contentWindow.ArchCanvasSemanticView.accepts(graph,el.contentWindow.SummaryEngine.validateView(graph)),doc.graph);assert.equal(validation,true);
 checks.push('native F0/F1 transitions preserve every catalog fact and keep unresolved routing explicit');
 await page.getByRole('group',{name:'工作区模式',exact:true}).getByRole('button',{name:'编辑',exact:true}).click();
 doc=await waitFor(d=>!!d.authoring);assert.ok(doc.authoring.nodes.length);assert.equal(await frame.getAttribute('data-catalog-identity'),'same');
 await page.getByRole('group',{name:'工作区模式',exact:true}).getByRole('button',{name:'视图',exact:true}).click();
 const saved=(await command('save')).document;await page.getByRole('button',{name:'保存',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('.save-state')?.classList.contains('dirty'));
 await page.reload({waitUntil:'networkidle'});await ready();doc=await waitFor(d=>d.caseId===saved.caseId);assert.deepEqual(doc.graph.generic.ir,saved.graph.generic.ir);assert.deepEqual(doc.graph.studioCamera,saved.graph.studioCamera);
 checks.push('catalog view enters Summary assembly editing in the same iframe; save and real reload restore its complete IR and native camera');
 await menu('Summary 模型库');const old=await snapshot();const other=catalog.models.find(m=>m.title==='TinyCNN');
 await page.route('**/preview/data/semantic/'+other.ir.path,route=>route.fulfill({status:200,contentType:'application/json',body:'{}'}));
 await panel.getByRole('textbox',{name:'搜索 Summary 模型',exact:true}).fill('');await panel.getByRole('combobox',{name:'Summary 目录模型',exact:true}).selectOption(other.id);await panel.getByRole('button',{name:'打开 Summary 模型',exact:true}).click();await panel.getByRole('alert').waitFor();
 doc=await snapshot();assert.equal(doc.caseId,old.caseId);assert.deepEqual(doc.graph.generic.ir,old.graph.generic.ir);assert.equal(await panel.getByRole('button',{name:'打开 Summary 模型',exact:true}).isEnabled(),true);
 checks.push('tampered catalog bytes fail before replacement; current graph, editing document and usable controls survive');
 await page.screenshot({path:output.replace(/\.json$/,'-rejected.png'),fullPage:true});await page.unroute('**/preview/data/semantic/'+other.ir.path);doc=await open(other);assert.equal(doc.graph.generic.ir.ir_digest,other.digest);assert.equal(await panel.getByRole('alert').count(),0);
 checks.push('a verified model can be opened after rejection without reloading or losing usable panel controls');
 assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);assert.equal(requests.some(u=>/\/home\/fzg\/|\/prototype\//.test(u)),false);
 checks.push('catalog interaction makes no prototype source-path requests, source transactions or runtime execution writes and raises no browser errors');
 await page.screenshot({path:output.replace(/\.json$/,'.png'),fullPage:true});await fs.writeFile(output,JSON.stringify({ok:true,checks,browserErrors:errors,sourceWrites:writes},null,2)+'\n');
 console.log(JSON.stringify({ok:true,checks:checks.length,output}));
}catch(error){await page.screenshot({path:output.replace(/\.json$/,'-failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(output,JSON.stringify({ok:false,checks,browserErrors:errors,sourceWrites:writes,error:String(error)},null,2)+'\n');throw error;}finally{await browser.close();}
