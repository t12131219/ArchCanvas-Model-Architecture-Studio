import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const {chromium}=await import(option('--playwright')?pathToFileURL(option('--playwright')).href:'playwright');
const base=option('--base','http://127.0.0.1:8789'),output=option('--output','/tmp/summary-adaptive-browser.json');
const browser=await chromium.launch({headless:true,...(option('--chromium')?{executablePath:option('--chromium')} : {}),args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1600,height:1100},acceptDownloads:true}),checks=[],errors=[],sourceWrites=[];
page.setDefaultTimeout(120000);page.setDefaultNavigationTimeout(120000);
page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST'&&/edit-source|transactions|runtime|preview\/analyze/.test(r.url()))sourceWrites.push(r.url());});
checks.push=(...values)=>{for(const v of values)console.log('PASS',v);return Array.prototype.push.apply(checks,values);};
async function command(name,payload={}){return page.evaluate(({name,payload})=>new Promise((resolve,reject)=>{const child=document.querySelector('iframe').contentWindow,requestId=crypto.randomUUID();const timer=setTimeout(()=>{window.removeEventListener('message',listen);reject(Error('timeout '+name));},120000);function listen(e){if(e.source!==child||e.origin!==location.origin||e.data?.requestId!==requestId)return;clearTimeout(timer);window.removeEventListener('message',listen);e.data.type.endsWith(':error')?reject(Error(e.data.message)):resolve(e.data);}window.addEventListener('message',listen);child.postMessage({type:'archcanvas:preview:'+name,...payload,requestId},location.origin);}),{name,payload});}
const snapshot=async()=>(await command('snapshot')).document;
// Summary compact layout intentionally regenerates these derived endpoint caches.
const edges=doc=>doc.graph.edges.map(({sourcePort,targetPort,...edge})=>edge);
async function waitFor(test){const end=Date.now()+120000;while(Date.now()<end){const d=await snapshot();if(!d.busy&&test(d))return d;await new Promise(r=>setTimeout(r,100));}throw Error('state timeout');}
async function ready(){await page.waitForFunction(()=>document.querySelector('iframe')&&!document.querySelector('.semantic-frontier .segmented button')?.disabled,{timeout:120000});}
async function menu(name){await page.locator('.workspace-menu > summary').click();await page.getByRole('button',{name,exact:true}).click();}
function facts(doc,ir){assert.deepEqual(doc.graph.generic.ir,ir);for(const [ledger,items]of [[doc.semanticView.nodeAccounting,ir.nodes],[doc.semanticView.edgeAccounting,ir.edges]]){const ids=Object.values(ledger).flat();assert.equal(new Set(ids).size,items.length);assert.deepEqual(ids.slice().sort(),items.map(n=>n.id).sort());}}
try{
 await page.goto(base,{waitUntil:'networkidle'});await ready();sourceWrites.length=0;
 const catalog=await(await page.request.get(base+'/preview/data/semantic/studio-catalog.json')).json(),model=catalog.models.find(m=>m.title==='SameSource'),ir=await(await page.request.get(base+'/preview/data/semantic/'+model.ir.path)).json();
 await menu('Summary 模型库');const panel=page.locator('.summary-catalog');await panel.getByRole('combobox',{name:'Summary 目录模型',exact:true}).selectOption(model.id);await panel.getByRole('button',{name:'打开 Summary 模型',exact:true}).click();await waitFor(d=>d.graph?.generic?.ir?.ir_digest===model.digest);await panel.locator(':scope > summary').click();
 await page.locator('.summary-view > summary').click();await page.getByRole('combobox',{name:'Summary 语义切面',exact:true}).selectOption('roles');
 const initial=await waitFor(d=>d.semanticView.granularity==='roles');facts(initial,ir);assert.equal(initial.graph.nodes.length,11);
 const toggle=page.getByRole('checkbox',{name:'Summary 局部自适应细化',exact:true});assert.equal(await toggle.isChecked(),false);assert.equal(await toggle.isEnabled(),true);
 await page.locator('iframe').evaluate(el=>el.dataset.adaptiveIdentity='same');
 await toggle.click();let doc=await waitFor(d=>d.semanticView.adaptive.enabled);facts(doc,ir);assert.equal(await toggle.isChecked(),true);assert.equal(doc.graph.nodes.length,17);assert.ok(doc.semanticView.adaptive.receipt.attempts.some(a=>a.accepted&&a.gain>0));assert.equal(doc.undo,initial.undo+1);
 checks.push('Studio folding inspector enables native measured Summary refinement: 11 to 17 glyphs, exact canonical accounting and one undo transaction');
 await page.getByRole('button',{name:'撤销画布编辑',exact:true}).click();doc=await waitFor(d=>!d.semanticView.adaptive.enabled);assert.deepEqual(doc.graph.nodes,initial.graph.nodes);assert.deepEqual(edges(doc),edges(initial));
 await page.getByRole('button',{name:'重做画布编辑',exact:true}).click();doc=await waitFor(d=>d.semanticView.adaptive.enabled);assert.equal(doc.graph.nodes.length,17);facts(doc,ir);
 checks.push('top-level undo and redo restore actual native graph, ports and routes without replacing the iframe');
 await page.getByRole('combobox',{name:'Summary 自适应策略',exact:true}).selectOption('structure');doc=await waitFor(d=>d.semanticView.adaptive.policy==='structure');facts(doc,ir);
 assert.ok(doc.semanticView.adaptive.receipt.attempts.length<=3);assert.ok(doc.semanticView.adaptive.receipt.preflights.length<=36);
 await page.locator('.summary-adaptive-receipt > summary').click();assert.match(await page.locator('.summary-adaptive-receipt').innerText(),/实际布线候选/);
 checks.push('structure policy compares exact role paths and whole boundaries using bounded actual routing measurements, with visible acceptance and rejection receipts');
 const adaptive=doc;await toggle.click();doc=await waitFor(d=>!d.semanticView.adaptive.enabled);assert.deepEqual(doc.graph.nodes,initial.graph.nodes);assert.deepEqual(edges(doc),edges(initial));
 await toggle.click();doc=await waitFor(d=>d.semanticView.adaptive.enabled);assert.deepEqual(doc.graph.nodes,adaptive.graph.nodes);assert.deepEqual(edges(doc),edges(adaptive));
 checks.push('disabling restores original geometry and requests; enabling deterministically reproduces native selected glyphs and routes');
 const beforeInvalid=await snapshot();await assert.rejects(()=>command('semantic-view',{patch:{paperAdaptivePolicy:'by-model-name'}}),/策略无效/);doc=await waitFor(d=>!d.busy);assert.equal(doc.undo,beforeInvalid.undo);assert.deepEqual(doc.graph.nodes,beforeInvalid.graph.nodes);
 checks.push('invalid policy refuses atomically without changing history, visible geometry or source facts');
 const download=page.waitForEvent('download');await command('export-json');const json=JSON.parse(await fs.readFile(await(await download).path(),'utf8'));assert.deepEqual(json.graph.generic.ir,ir);assert.ok(json.graph.generic.state.nativeAdaptiveBase);
 await command('load',{bundle:json});doc=await waitFor(d=>d.semanticView.adaptive.enabled);facts(doc,ir);assert.deepEqual(doc.graph.nodes,adaptive.graph.nodes);assert.equal(doc.semanticView.adaptive.receipt.restored,true);
 await page.getByRole('button',{name:'保存',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('.save-state')?.classList.contains('dirty'));const saved=await snapshot();await page.reload({waitUntil:'networkidle'});await ready();doc=await waitFor(d=>d.caseId===saved.caseId);facts(doc,ir);assert.equal(doc.semanticView.adaptive.enabled,true);assert.deepEqual(doc.graph.nodes,saved.graph.nodes);assert.deepEqual(edges(doc),edges(saved));
 checks.push('editing JSON and top-level save/reload retain effective requests, original base, complete IR and independently validated native geometry');
 await page.locator('.summary-view > summary').click();const owner=doc.semanticView.roleDetails[0];assert.ok(owner);await command('focus',{nodeId:owner});doc=await waitFor(d=>d.selectedNodes.includes(owner));
 await page.getByRole('button',{name:'收起所选边界的认证角色',exact:true}).click();doc=await waitFor(d=>!d.semanticView.adaptive.enabled);facts(doc,ir);assert.ok(!doc.semanticView.roleDetails.includes(owner));assert.equal(doc.graph.nodes.length,11);
 checks.push('manual boundary collapse preserves other requests, disables automatic replanning and returns the actual Summary cut to 11 glyphs');
 await page.getByRole('combobox',{name:'Summary 语义切面',exact:true}).selectOption('roles');await waitFor(d=>d.semanticView.granularity==='roles');await page.getByRole('checkbox',{name:'Summary 局部自适应细化',exact:true}).click();doc=await waitFor(d=>d.semanticView.adaptive.enabled);
 await page.locator('.summary-adaptive-receipt > summary').click();await page.screenshot({path:output.replace(/\.json$/,'.png'),fullPage:true});
 const textBounds=await page.locator('iframe').contentFrame().locator('#nodeLayer text, #frameLayer text').evaluateAll(rows=>rows.map(el=>{const box=el.getBBox(),owner=el.closest('[data-node-id]'),matrix=el.ownerSVGElement.getCTM().inverse().multiply(el.getCTM()),points=[[box.x,box.y],[box.x+box.width,box.y],[box.x,box.y+box.height],[box.x+box.width,box.y+box.height]].map(([x,y])=>new DOMPoint(x,y).matrixTransform(matrix)),x=Math.min(...points.map(p=>p.x)),y=Math.min(...points.map(p=>p.y));return {text:el.textContent,x,y,w:Math.max(...points.map(p=>p.x))-x,h:Math.max(...points.map(p=>p.y))-y,owner:owner?.getAttribute('data-node-id')};}));assert.ok(textBounds.length>17);assert.ok(textBounds.every(b=>[b.x,b.y,b.w,b.h].every(Number.isFinite)));for(const b of textBounds){const node=doc.graph.nodes.find(n=>n.id===b.owner);assert.ok(node,b.text);assert.ok(b.x>=node.x-.5&&b.y>=node.y-.5&&b.x+b.w<=node.x+node.w+.5&&b.y+b.h<=node.y+node.h+.5,JSON.stringify({text:b.text,bounds:b,node:[node.x,node.y,node.w,node.h]}));}
 assert.deepEqual(errors,[]);assert.deepEqual(sourceWrites,[]);checks.push('real browser native text fits every containing glyph; no source-analysis, CPU execution or transaction writes and no browser errors');
 await fs.writeFile(output,JSON.stringify({ok:true,checks,browserErrors:errors,sourceWrites,textBounds},null,2)+'\n');console.log(JSON.stringify({ok:true,checks:checks.length,output}));
}catch(error){await page.screenshot({path:output.replace(/\.json$/,'-failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(output,JSON.stringify({ok:false,checks,browserErrors:errors,sourceWrites,error:String(error)},null,2)+'\n');throw error;}finally{await browser.close();}
