import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const {chromium}=await import(option('--playwright')?pathToFileURL(option('--playwright')).href:'playwright');
const base=option('--base','http://127.0.0.1:8790'),output=option('--output','/tmp/summary-runtime-browser.json');
const browser=await chromium.launch({headless:true,...(option('--chromium')?{executablePath:option('--chromium')} : {}),args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1600,height:1100},acceptDownloads:true}),checks=[],errors=[],sourceWrites=[],observations=[],starts=[];
page.setDefaultTimeout(120000);page.setDefaultNavigationTimeout(120000);
page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST'&&/transactions|source-regions\/apply|authoring\/generate/.test(r.url()))sourceWrites.push(r.url());if(r.method()==='POST'&&r.url().endsWith('/api/preview/runtime-jobs'))starts.push(r.postDataJSON());});
page.on('response',async r=>{if(/\/api\/preview\/runtime-jobs\/[a-f0-9]+$/.test(r.url())){const v=await r.json().catch(()=>null);if(v?.status==='complete')observations.push(v.result);}});
checks.push=(...values)=>{for(const v of values)console.log('PASS',v);return Array.prototype.push.apply(checks,values);};
async function command(name,payload={}){return page.evaluate(({name,payload})=>new Promise((resolve,reject)=>{const child=document.querySelector('iframe').contentWindow,requestId=crypto.randomUUID(),timer=setTimeout(()=>{window.removeEventListener('message',listen);reject(Error('timeout '+name));},120000);function listen(e){if(e.source!==child||e.origin!==location.origin||e.data?.requestId!==requestId)return;clearTimeout(timer);window.removeEventListener('message',listen);e.data.type.endsWith(':error')?reject(Error(e.data.message)):resolve(e.data);}window.addEventListener('message',listen);child.postMessage({type:'archcanvas:preview:'+name,...payload,requestId},location.origin);}),{name,payload});}
const snapshot=async()=>(await command('snapshot')).document;
async function ready(){await page.waitForFunction(()=>document.querySelector('iframe')&&document.querySelector('.semantic-frontier .segmented button')&&!document.querySelector('.semantic-frontier .segmented button').disabled);}
async function menu(name){await page.locator('.workspace-menu > summary').click();await page.getByRole('button',{name,exact:true}).click();}
const source=await fs.readFile(new URL('../../fixtures/summary_runtime/model.py',import.meta.url),'utf8');
const spec={schema:'semantic-inputs/1',constructor:{width:3},modes:['eval'],cases:[['positive',true],['negative',false]].map(([id,flag])=>({id,seed:7,inputs:{x:{shape:[2,3],dtype:'float32',fill:'ones'},flag:{value:flag}}}))};
try{
 await page.goto(base,{waitUntil:'networkidle'});await ready();
 await menu('导入 Python 源码');await page.getByLabel('Python 源码',{exact:true}).fill(source);await page.getByLabel('模型入口类名',{exact:true}).fill('RuntimeFixture');await page.getByLabel('源文件名',{exact:true}).fill('model.py');await page.getByRole('button',{name:'分析并打开',exact:true}).click();await page.getByRole('dialog',{name:'打开模型',exact:true}).waitFor({state:'hidden'});await ready();
 // Flush the normal debounced layout cache before testing observation purity.
 // A source read alone does not populate generic.layouts; save does.
 await command('request-source');await command('save');const original=await snapshot();assert.equal(original.graph.generic.ir.runtime.model_executed,false);assert.equal(starts.length,0);
 await page.locator('.summary-runtime > summary').click();assert.equal(await page.getByRole('button',{name:'运行 CPU 观察',exact:true}).isEnabled(),true);
 checks.push('retained Studio source import and CPU fold never execute before an explicit profile/run action');
 await page.getByLabel('Summary CPU 输入规格',{exact:true}).fill(JSON.stringify(spec,null,2));await page.getByRole('button',{name:'运行 CPU 观察',exact:true}).click();await page.getByRole('button',{name:'打开本次观察结果',exact:true}).waitFor();
 const observed=observations.find(v=>v?.receipt?.status==='passed');assert.ok(observed);const receipt=observed.receipt,ir=observed.document;
 assert.equal(receipt.runtimeVerified,true);assert.equal(receipt.source_unchanged,true);assert.deepEqual(receipt.source_files,{'model.py':source});assert.ok(Object.values(receipt.isolation.formalProbe.checks).every(Boolean));assert.equal(ir.source_runtime_index.regions.length,4);assert.equal(ir.coverage.complete,false);
 assert.deepEqual(receipt.runs.map(r=>r.events.map(e=>e.operator)),[['aten.t.default','aten.mm.default','aten.t.default','aten.mm.default','aten.add.Tensor'],['aten.t.default','aten.mm.default','aten.t.default','aten.mm.default','aten.sub.Tensor']]);
 assert.deepEqual((await snapshot()).graph,original.graph);
 checks.push('real isolated HTTP job records Summary ATen/producers/source-stack and four unknown-call regions while retaining the original view');
 await page.getByRole('button',{name:'打开本次观察结果',exact:true}).click();await page.getByText('已打开本次 CPU 观察的独立结果；原模型保留，源码写回仍使用正式事务。',{exact:true}).waitFor();await ready();let doc=await snapshot();assert.notEqual(doc.caseId,original.caseId);assert.deepEqual(doc.graph.generic.ir,ir);assert.equal(doc.adapter,undefined);
 for(const mode of ['runtime','merged','source']){await command('semantic-view',{patch:{mode}});doc=await snapshot();assert.equal(doc.semanticView.mode,mode);assert.deepEqual(doc.graph.generic.ir,ir);}
 for(const preset of ['detail','overview']){await command('set-frontier',{preset});doc=await snapshot();assert.deepEqual(doc.graph.generic.ir,ir);}
 checks.push('explicit native result open, CPU/merged/source modes and F0/F1 retain every fact and unknown boundary');
 await page.getByRole('button',{name:'保存',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.save-state')?.textContent==='已保存');const saved=await snapshot();await page.reload({waitUntil:'networkidle'});await ready();doc=await snapshot();assert.equal(doc.caseId,saved.caseId);assert.deepEqual(doc.graph.generic.ir,ir);await page.waitForFunction(()=>document.querySelector('.save-state')?.textContent==='已保存');
 await page.locator('.summary-runtime > summary').click();assert.deepEqual(JSON.parse(await page.getByLabel('Summary CPU 输入规格',{exact:true}).inputValue()),spec);
 const downloading=page.waitForEvent('download');await command('export-json');const download=await downloading,path=output.replace(/\.json$/,'-portable.json');await download.saveAs(path);
 await menu('导入 Python 源码');await page.getByRole('tab',{name:'工程目录 / 已有文档',exact:true}).click();await page.getByLabel('选择源文件',{exact:true}).setInputFiles(path);await page.getByRole('dialog',{name:'打开模型',exact:true}).waitFor({state:'hidden'});await ready();assert.deepEqual((await snapshot()).graph.generic.ir,ir);
 checks.push('full receipt/source/profile survives save, refresh and actual portable JSON file import without re-execution');
 if(!await page.locator('.summary-runtime').evaluate(el=>el.open))await page.locator('.summary-runtime > summary').click();
 await command('save');const beforeCancel=await snapshot(),count=observations.length;await page.getByRole('button',{name:'运行 CPU 观察',exact:true}).click();await page.getByRole('button',{name:'取消 CPU 观察',exact:true}).click();await page.getByRole('button',{name:'取消 CPU 观察',exact:true}).waitFor({state:'hidden'});
 const cancelled=observations.slice(count).find(v=>v?.receipt?.reason==='cancelled');assert.ok(cancelled);assert.equal(cancelled.document,null);const afterCancel=await snapshot();assert.deepEqual(afterCancel.graph,beforeCancel.graph);assert.equal(afterCancel.undo,beforeCancel.undo);assert.equal(afterCancel.redo,beforeCancel.redo);assert.equal(await page.getByRole('button',{name:'打开本次观察结果',exact:true}).count(),0);
 checks.push('real CPU cancellation preserves graph/history and returns a failed receipt without a replacement');
 await page.getByRole('group',{name:'工作区模式'}).getByRole('button',{name:'编辑',exact:true}).click();await page.getByRole('heading',{name:'Summary 模型编辑',exact:true}).waitFor();doc=await snapshot();assert.deepEqual(doc.graph.generic.authoring.baseline,ir);const workspace=doc.caseId;await page.getByRole('group',{name:'工作区模式'}).getByRole('button',{name:'视图',exact:true}).click();await page.getByRole('heading',{name:'Summary 模型编辑',exact:true}).waitFor({state:'hidden'});await ready();doc=await snapshot();assert.equal(doc.caseId,workspace);assert.deepEqual(doc.graph.generic.authoring.baseline,ir);
 checks.push('observed result enters retained edit/view modes with the full immutable baseline and no source write authority');
 assert.deepEqual(errors,[]);assert.deepEqual(sourceWrites,[]);await page.screenshot({path:output.replace(/\.json$/,'.png'),fullPage:true});
 await fs.writeFile(output,JSON.stringify({ok:true,checks,starts:starts.length,receipt,documentFacts:{nodes:ir.nodes.length,edges:ir.edges.length,regions:ir.source_runtime_index.regions.length},browserErrors:errors,sourceWrites},null,2)+'\n');console.log(JSON.stringify({ok:true,checks:checks.length,output}));
}catch(error){await page.screenshot({path:output.replace(/\.json$/,'-failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(output,JSON.stringify({ok:false,checks,starts:starts.length,observations:observations.map(v=>({status:v?.receipt?.status,reason:v?.receipt?.reason})),browserErrors:errors,sourceWrites,error:String(error)},null,2)+'\n');throw error;}finally{await browser.close();}
