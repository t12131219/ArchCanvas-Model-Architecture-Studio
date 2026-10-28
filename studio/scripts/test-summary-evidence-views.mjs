import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const {chromium}=await import(option('--playwright')?pathToFileURL(option('--playwright')).href:'playwright');
const base=option('--base','http://127.0.0.1:8789'),output=option('--output','/tmp/summary-evidence-views-browser.json');
const browser=await chromium.launch({headless:true,...(option('--chromium')?{executablePath:option('--chromium')} : {}),args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1600,height:1100},acceptDownloads:true}),checks=[],errors=[],sourceWrites=[];
page.setDefaultNavigationTimeout(120000);page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST'&&/edit-source|transactions|runtime|preview\/analyze/.test(r.url()))sourceWrites.push(r.url());});
checks.push=(...values)=>{for(const v of values)console.log('PASS',v);return Array.prototype.push.apply(checks,values);};
async function command(name,payload={}){return page.evaluate(({name,payload})=>new Promise((resolve,reject)=>{const child=document.querySelector('iframe').contentWindow,requestId=crypto.randomUUID();const timer=setTimeout(()=>{window.removeEventListener('message',listen);reject(Error('timeout '+name));},60000);function listen(e){if(e.source!==child||e.origin!==location.origin||e.data?.requestId!==requestId)return;clearTimeout(timer);window.removeEventListener('message',listen);e.data.type.endsWith(':error')?reject(Error(e.data.message)):resolve(e.data);}window.addEventListener('message',listen);child.postMessage({type:'archcanvas:preview:'+name,...payload,requestId},location.origin);}),{name,payload});}
const snapshot=async()=>(await command('snapshot')).document;
async function waitFor(test){const end=Date.now()+60000;while(Date.now()<end){const d=await snapshot();if(!d.busy&&test(d))return d;await new Promise(r=>setTimeout(r,100));}throw Error('state timeout');}
async function ready(){await page.waitForFunction(()=>document.querySelector('iframe')&&!document.querySelector('.semantic-frontier .segmented button')?.disabled,{timeout:60000});}
async function menu(name){await page.locator('.workspace-menu > summary').click();await page.getByRole('button',{name,exact:true}).click();}
async function openModel(model){await menu('Summary 模型库');const panel=page.locator('.summary-catalog');await panel.getByRole('combobox',{name:'Summary 目录模型',exact:true}).selectOption(model.id);await panel.getByRole('button',{name:'打开 Summary 模型',exact:true}).click();const doc=await waitFor(d=>d.graph?.generic?.ir?.ir_digest===model.digest);await panel.locator(':scope > summary').click();return doc;}
async function mode(value){await page.getByRole('combobox',{name:'Summary 证据视图',exact:true}).selectOption(value);return waitFor(d=>d.semanticView.mode===value);}
function facts(doc,ir){assert.deepEqual(doc.graph.generic.ir,ir);assert.equal(doc.graph.sourceAdapter,undefined);assert.equal(doc.importedDocument.sourceVerified,false);for(const [ledger,items]of [[doc.semanticView.nodeAccounting,ir.nodes],[doc.semanticView.edgeAccounting,ir.edges]]){const ids=Object.values(ledger).flat();assert.equal(ids.length,items.length);assert.equal(new Set(ids).size,items.length);assert.deepEqual(ids.slice().sort(),items.map(n=>n.id).sort());}}
try{
 await page.goto(base,{waitUntil:'networkidle'});await ready();sourceWrites.length=0;
 const catalog=await(await page.request.get(base+'/preview/data/semantic/studio-catalog.json')).json(),model=catalog.models.find(m=>m.title==='BranchMLP'),ir=await(await page.request.get(base+'/preview/data/semantic/'+model.ir.path)).json();
 let doc=await openModel(model);await page.locator('.summary-view > summary').click();const frame=page.locator('iframe');await frame.evaluate(el=>el.dataset.evidenceIdentity='same');
 assert.equal(doc.semanticView.mode,'source');assert.equal(doc.semanticView.runtimeEvidence.runs.length,4);assert.equal(await page.getByRole('combobox',{name:'Summary 证据视图',exact:true}).locator('option').count(),3);facts(doc,ir);
 checks.push('retained Studio folding panel exposes original source, CPU trace and merged evidence views with four archived cases');
 const initial=await snapshot(),camera=(await command('snapshot')).camera;doc=await mode('runtime');facts(doc,ir);assert.ok(doc.graph.nodes.some(n=>n.id==='runtime-observations'||n.id.startsWith('runtime:')));assert.equal(doc.undo,initial.undo+1);
 await page.getByRole('button',{name:'撤销画布编辑',exact:true}).click();doc=await waitFor(d=>d.semanticView.mode==='source');facts(doc,ir);assert.deepEqual(doc.graph.nodes,initial.graph.nodes);assert.deepEqual((await command('snapshot')).camera,camera);
 await page.getByRole('button',{name:'重做画布编辑',exact:true}).click();doc=await waitFor(d=>d.semanticView.mode==='runtime');facts(doc,ir);
 checks.push('CPU view uses native glyphs and one shared undo/redo transaction, retaining all canonical facts and exact source viewport');
 // The complete tree can name latent objects from the other evidence view.
 const staticNode=ir.nodes.find(n=>n.kind==='compute'&&!n.id.startsWith('runtime:')),runtimeNode=ir.nodes.find(n=>n.kind==='compute'&&n.id.startsWith('runtime:'));assert.ok(staticNode&&runtimeNode);
 await command('focus',{nodeId:staticNode.id});doc=await waitFor(d=>d.semanticView.mode==='source'&&d.selectedNodes.includes(staticNode.id));facts(doc,ir);
 await page.locator('.summary-view').getByRole('button',{name:'返回上个语义切面',exact:true}).click();doc=await waitFor(d=>d.semanticView.mode==='runtime');
 await mode('source');await command('focus',{nodeId:runtimeNode.id});doc=await waitFor(d=>d.semanticView.mode==='runtime'&&d.selectedNodes.includes(runtimeNode.id));facts(doc,ir);
 checks.push('latent hierarchy navigation switches source/CPU mode by exact object identity and native back restores the previous evidence cut');
 doc=await mode('merged');facts(doc,ir);await page.getByRole('combobox',{name:'Summary CPU 补证样例',exact:true}).selectOption('3');doc=await waitFor(d=>d.semanticView.runtimeEvidence.selectedRun===3);facts(doc,ir);
 assert.equal(doc.semanticView.runtimeEvidence.integratedRegions,0);assert.equal(doc.semanticView.runtimeEvidence.executesModel,false);assert.match(await page.locator('.summary-view').innerText(),/没有可唯一核对的调用绑定/);
 await command('set-frontier',{preset:'detail'});doc=await waitFor(d=>d.frontierPreset==='detail');assert.equal(doc.semanticView.mode,'merged');assert.equal(doc.semanticView.runtimeEvidence.selectedRun,3);facts(doc,ir);
 checks.push('merged sample selection and F1 retain exact recorded case identity, preserve unknown source boundaries and never invent legacy call bindings');
 const beforeInvalid=await snapshot();await assert.rejects(()=>command('semantic-view',{patch:{runtimeInlineRun:999}}),/样例不存在/);doc=await waitFor(d=>!d.busy);facts(doc,ir);assert.equal(doc.undo,beforeInvalid.undo);assert.deepEqual(doc.graph.nodes,beforeInvalid.graph.nodes);assert.deepEqual(doc.graph.edges,beforeInvalid.graph.edges);
 checks.push('forged run selection refuses atomically without changing visible graph, canonical facts or either history stack');
 const download=page.waitForEvent('download');await command('export-json');const json=JSON.parse(await fs.readFile(await(await download).path(),'utf8'));assert.equal(json.graph.generic.state.mode,'merged');assert.equal(json.graph.generic.state.runtimeInlineRun,3);assert.deepEqual(json.graph.generic.ir,ir);
 await command('load',{bundle:json});doc=await waitFor(d=>d.semanticView.mode==='merged'&&d.semanticView.runtimeEvidence.selectedRun===3);facts(doc,ir);
 const saved=(await command('save')).document;await page.getByRole('button',{name:'保存',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('.save-state')?.classList.contains('dirty'));await page.reload({waitUntil:'networkidle'});await ready();doc=await waitFor(d=>d.caseId===saved.caseId);facts(doc,ir);assert.equal(doc.semanticView.mode,'merged');assert.equal(doc.semanticView.runtimeEvidence.selectedRun,3);assert.deepEqual(doc.graph.studioCamera,saved.graph.studioCamera);
 await page.locator('.summary-view > summary').click();assert.equal(await page.getByRole('combobox',{name:'Summary CPU 补证样例',exact:true}).inputValue(),'3');
 checks.push('editing JSON roundtrip and top-level save with a real reload preserve complete IR, selected evidence mode, recorded case and native camera');
 await page.screenshot({path:output.replace(/\.json$/,'.png'),fullPage:true});
 await page.getByRole('combobox',{name:'Summary 证据视图',exact:true}).selectOption('runtime');doc=await waitFor(d=>d.semanticView.mode==='runtime');
 await page.getByRole('group',{name:'工作区模式',exact:true}).getByRole('button',{name:'编辑',exact:true}).click();doc=await waitFor(d=>!!d.authoring);assert.deepEqual(doc.authoring.nodes.map(n=>n.id).sort(),ir.nodes.map(n=>n.id).sort());assert.deepEqual(doc.graph.generic.authoring.baseline,ir);assert.equal(doc.graph.authoringWorkspace.origin.caseId,saved.caseId);assert.equal(doc.graph.authoringWorkspace.origin.irDigest,ir.ir_digest);assert.equal(doc.graph.authoringWorkspace.origin.sourceSha256,null);
 await page.getByRole('group',{name:'工作区模式',exact:true}).getByRole('button',{name:'视图',exact:true}).click();
 checks.push('editing from a CPU evidence cut creates a Summary assembly from the complete canonical model and keeps declared provenance separate from source transactions');
 // isDisabled() retargets an option inside a label to label.control (the select).
 const plain=catalog.models.find(m=>m.title==='MultilayerPerceptron · mlp');doc=await openModel(plain);const cpuOption=page.getByRole('combobox',{name:'Summary 证据视图',exact:true}).locator('option[value="runtime"]');await page.waitForFunction(()=>document.querySelector('select[aria-label="Summary 证据视图"] option[value="runtime"]')?.disabled===true);assert.equal(await cpuOption.evaluate(option=>option.disabled),true);await assert.rejects(()=>command('semantic-view',{patch:{mode:'runtime'}}),/没有 CPU/);doc=await mode('merged');assert.equal(doc.semanticView.runtimeEvidence.runs.length,0);assert.match(await page.locator('.summary-view').innerText(),/没有运行记录/);
 checks.push('static-only models disable unavailable CPU traces while merged view retains their original source facts without fabricating execution');
 assert.deepEqual(errors,[]);assert.deepEqual(sourceWrites,[]);checks.push('view controls make no source-analysis, runtime or transaction writes and produce no browser errors');
 await fs.writeFile(output,JSON.stringify({ok:true,checks,browserErrors:errors,sourceWrites},null,2)+'\n');console.log(JSON.stringify({ok:true,checks:checks.length,output}));
}catch(error){await page.screenshot({path:output.replace(/\.json$/,'-failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(output,JSON.stringify({ok:false,checks,browserErrors:errors,sourceWrites,error:String(error)},null,2)+'\n');throw error;}finally{await browser.close();}
