import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
const args = process.argv.slice(2), option = (key, fallback) => args.includes(key) ? args[args.indexOf(key) + 1] : fallback;
const { chromium } = await import(option('--playwright') ? pathToFileURL(option('--playwright')).href : 'playwright');
const output = option('--output', '/tmp/summary-local-assembly-browser.json'), base = option('--base', 'http://127.0.0.1:8789');
const browser = await chromium.launch({ headless: true, ...(option('--chromium') ? { executablePath: option('--chromium') } : {}), args: ['--no-sandbox'] });
let page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
const checks = [], errors = [], writes = [], analyses = [];
page.setDefaultNavigationTimeout(120000);
function observe() { page.on('pageerror', e => errors.push(e.message)); page.on('request', r => { if (r.method() === 'POST' && /transactions|runtime\/run/.test(r.url())) writes.push(r.url()); if(r.method() === 'POST' && /api\/preview\/edit-source$/.test(r.url())) analyses.push(r.postDataJSON()); }); }
observe();
checks.push = (...values) => { for(const value of values) console.log('PASS', value); return Array.prototype.push.apply(checks, values); };
async function command(name, payload = {}) {
  return page.evaluate(({ name, payload }) => new Promise((resolve, reject) => {
    const child = document.querySelector('iframe').contentWindow, requestId = crypto.randomUUID();
    const timer = setTimeout(() => { window.removeEventListener('message', listener); reject(Error('timeout: ' + name)); }, 60000);
    function listener(e) { if (e.source !== child || e.origin !== location.origin || e.data?.requestId !== requestId) return; clearTimeout(timer); window.removeEventListener('message', listener); if (e.data.type.endsWith(':error')) reject(Error(e.data.message)); else resolve(e.data); }
    window.addEventListener('message', listener); child.postMessage({ type: 'archcanvas:preview:' + name, ...payload, requestId }, location.origin);
  }), { name, payload });
}
const snapshot = async () => (await command('snapshot')).document;
async function waitFor(test) { const end = Date.now() + 60000; while (Date.now() < end) { const doc = await snapshot(); if (!doc.busy && test(doc)) return doc; await new Promise(r => setTimeout(r, 100)); } throw Error('state condition timed out'); }
async function ready() { await page.waitForFunction(() => document.querySelector('iframe') && !document.querySelector('.semantic-frontier .segmented button')?.disabled, { timeout: 60000 }); }
async function menu(name) { await page.locator('.workspace-menu > summary').click(); await page.getByRole('button', { name, exact: true }).click(); }
async function accept(doc) { const result = await page.locator('iframe').evaluate((iframe, graph) => { const w = iframe.contentWindow, validation = w.SummaryEngine.validateView(graph); return { accepted: w.ArchCanvasSemanticView.accepts(graph, validation), source: validation.source, routes: validation.edges.filter(([,v]) => !v.ok).map(([id]) => id), routing: graph.nativeRouting }; }, doc.graph); assert.equal(result.accepted, true); assert.equal(result.source.ok, true); return result; }

try {
 await page.goto(base,{waitUntil:'networkidle'});await ready();await menu('新建空白模型');await page.getByRole('heading',{name:'Summary 模型编辑',exact:true}).waitFor();
 await page.locator('.summary-authoring-panel').getByRole('button',{name:'Residual',exact:true}).click();let doc=await waitFor(d=>d.authoring.nodes.length>5);const original=JSON.stringify(doc.graph.generic.authoring),nodes=structuredClone(doc.graph.generic.ir.nodes),edges=structuredClone(doc.graph.generic.ir.edges);
 await page.locator('.summary-authoring-panel').getByText('组装局部结构复核',{exact:true}).click();await page.getByRole('button',{name:'复核当前组装结构',exact:true}).click();doc=await waitFor(d=>d.authoring.localAnalysis?.contracts>0);
 assert.equal(doc.authoring.localAnalysis.modelExecuted,false);assert.equal(doc.authoring.localAnalysis.sourceTransactionBinding,false);assert.equal(JSON.stringify(doc.graph.generic.authoring),original);assert.deepEqual(doc.graph.generic.ir.nodes,nodes);assert.deepEqual(doc.graph.generic.ir.edges,edges);assert.equal(doc.adapter,undefined);
 assert.ok(doc.graph.generic.ir.semantic_contracts.every(c=>c.scope.includes('declared user assembly')&&c.not_asserted.includes('shape compatibility')));
 checks.push('Studio folding panel invokes the real Summary local recognizer and preserves every node, edge and declared authoring fact without source or execution authority');
 await page.getByRole('button',{name:'撤销画布编辑',exact:true}).click();await waitFor(d=>!d.authoring.localAnalysis);await page.getByRole('button',{name:'重做画布编辑',exact:true}).click();doc=await waitFor(d=>d.authoring.localAnalysis?.contracts>0);
 const portable=(await command('save')).document;await page.reload({waitUntil:'networkidle'});await ready();doc=await waitFor(d=>d.caseId===portable.caseId&&d.authoring.localAnalysis?.contracts>0);assert.deepEqual(doc.graph.generic.ir,portable.graph.generic.ir);
 checks.push('local results use one shared undo entry and strict browser restore retains the declaration, result and limited contracts');
 await page.getByRole('group',{name:'工作区模式',exact:true}).getByRole('button',{name:'编辑',exact:true}).click();await page.getByRole('heading',{name:'Summary 模型编辑',exact:true}).waitFor();
 for(const name of ['F0 概览','F1 详图']){await page.locator('.semantic-frontier').getByRole('button',{name,exact:true}).click();await waitFor(d=>!d.busy);doc=await snapshot();assert.deepEqual(doc.graph.generic.ir,portable.graph.generic.ir);assert.ok(doc.authoring.localAnalysis);}
 await page.getByLabel('Summary 模型名称',{exact:true}).fill('Changed declared assembly');await page.getByRole('button',{name:'应用模型名称',exact:true}).click();doc=await waitFor(d=>d.authoring.title==='Changed declared assembly');assert.equal(doc.authoring.localAnalysis,null);assert.equal(doc.graph.generic.ir.semantic_contracts.length,0);await page.getByRole('button',{name:'撤销画布编辑',exact:true}).click();await waitFor(d=>d.authoring.localAnalysis?.contracts>0);
 checks.push('certified semantic cuts retain local contracts while a later declaration edit clears them and undo restores the exact previous result');
 const saved=(await command('save')).document,context=await browser.newContext({viewport:{width:1600,height:1100}});await page.close();page=await context.newPage();page.setDefaultNavigationTimeout(120000);observe();await page.goto(base,{waitUntil:'networkidle'});await ready();await command('load',{bundle:saved});doc=await waitFor(d=>d.caseId===saved.caseId&&d.authoring.localAnalysis?.contracts>0);assert.deepEqual(doc.graph.generic.ir,saved.graph.generic.ir);
 const bad=structuredClone(saved),local=bad.nativeDocument.localAnalysis,ir=JSON.parse(local.irText);ir.nodes[0].label='injected fact';local.irText=JSON.stringify(ir);local.resultSha256=await page.evaluate(async text=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)))).map(n=>n.toString(16).padStart(2,'0')).join(''),local.irText);const before=JSON.stringify(doc.graph.generic.ir);await assert.rejects(command('load',{bundle:bad}),/局部/);assert.equal(JSON.stringify((await snapshot()).graph.generic.ir),before);
 checks.push('portable results restore in a fresh browser context and even a rehashed fact-changing result rejects without replacing the committed document');
 await page.getByRole('group',{name:'工作区模式',exact:true}).getByRole('button',{name:'编辑',exact:true}).click();await page.getByRole('heading',{name:'Summary 模型编辑',exact:true}).waitFor();await page.locator('.summary-authoring-panel').getByText('组装局部结构复核',{exact:true}).click();let release,seen;const held=new Promise(r=>release=r),arrived=new Promise(r=>seen=r);
 await page.route('**/api/preview/authoring/certify',async route=>{const result=await route.fetch();seen();await held;await route.fulfill({response:result});});await page.getByRole('button',{name:'复核当前组装结构',exact:true}).click();await Promise.race([arrived,new Promise((_,reject)=>setTimeout(()=>reject(Error('analysis intercept timeout')),20000))]);await command('authoring',{action:'title',title:'Changed while reviewing'});release();await page.locator('.summary-authoring-panel [role=alert]').filter({hasText:'已变化'}).waitFor();doc=await snapshot();assert.equal(doc.authoring.title,'Changed while reviewing');assert.equal(doc.authoring.localAnalysis,null);await page.unroute('**/api/preview/authoring/certify');
 checks.push('a real delayed analysis result cannot certify a later revision of the same workspace');
 await page.getByRole('button',{name:'复核当前组装结构',exact:true}).click();doc=await waitFor(d=>d.authoring.localAnalysis?.contracts>0);await accept(doc);assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);await page.screenshot({path:output.replace(/\.json$/,'.png'),fullPage:true});await fs.writeFile(output,JSON.stringify({ok:true,checks,browserErrors:errors,sourceWrites:writes},null,2)+'\n');console.log(JSON.stringify({ok:true,checks:checks.length,output}));
}catch(error){await page.screenshot({path:output.replace(/\.json$/,'-failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(output,JSON.stringify({ok:false,checks,browserErrors:errors,sourceWrites:writes,error:String(error)},null,2));throw error;}finally{await browser.close();}
