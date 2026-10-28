import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
const args = process.argv.slice(2), option = (key, fallback) => args.includes(key) ? args[args.indexOf(key) + 1] : fallback;
const { chromium } = await import(option('--playwright') ? pathToFileURL(option('--playwright')).href : 'playwright');
const output = option('--output', '/tmp/summary-authoring-source-browser.json'), base = option('--base', 'http://127.0.0.1:8789');
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
const source='from torch import nn\nclass Block(nn.Module):\n def __init__(self,width=4):\n  super().__init__()\n  self.linear=nn.Linear(width,width)\n def forward(self,x,skip):\n  return self.linear(x)+skip\n';
const modules=[];page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/api/preview/authoring/module'))modules.push(r.postDataJSON());});
const editMode=()=>page.getByRole('group',{name:'工作区模式',exact:true}).getByRole('button',{name:'编辑',exact:true});
async function sourceFields(code=source,width=7){await page.getByLabel('Summary 模块入口',{exact:true}).fill('Block');await page.getByLabel('Summary 模块构造参数',{exact:true}).fill(JSON.stringify({width}));await page.getByLabel('Summary 模块源码',{exact:true}).fill(code);}
try {
 await page.goto(base,{waitUntil:'networkidle'});await ready();await menu('新建空白模型');await page.getByRole('heading',{name:'Summary 模型编辑',exact:true}).waitFor();
 await page.locator('.summary-authoring-panel').getByText('源码模块与参数重解析',{exact:true}).click();await sourceFields();
 await page.getByRole('button',{name:'解析并加入源码模块',exact:true}).click();
 let doc=await waitFor(d=>d.authoring.nodes.some(n=>n.module?.entry==='Block')),root=doc.authoring.nodes.find(n=>n.module?.entry==='Block').id;
 assert.equal(doc.graph.generic.authoring.modules[root].constructor.width,7);assert.equal(doc.graph.generic.ir.runtime.model_executed,false);assert.equal(doc.adapter,undefined);
 const capability=await (await page.request.get(base+'/api/capabilities')).json();assert.equal(capability.preview.nativeAuthoring.analysis,'isolated-static-ast');assert.equal(capability.preview.nativeAuthoring.modelExecuted,false);
 checks.push('Studio source-module form uses the actual bounded static Summary API, preserves Python/constructor evidence and confers no source binding');
 await page.getByRole('button',{name:'添加输入',exact:true}).click();doc=await waitFor(d=>d.authoring.nodes.some(n=>n.label==='input'&&!n.parent));const external=doc.authoring.nodes.find(n=>n.label==='input'&&!n.parent).id;
 const slot=doc.authoring.nodes.find(n=>n.id===root).ports.inputs.find(p=>p.label==='skip');assert.ok(slot);
 await command('authoring',{action:'connect',source:{node:external,port:'out'},target:{node:slot.node,port:slot.port}});
 await command('visual',{operations:[{type:'alias',id:root,label:'Preserved source module alias'}]});await command('focus',{nodeId:root});
 await page.getByLabel('Summary 模块构造参数',{exact:true}).fill('{"width":16}');await page.getByRole('button',{name:'重新解析并替换选中构件',exact:true}).click();
 doc=await waitFor(d=>d.authoring.nodes.some(n=>n.module?.constructor?.width===16));let replacement=doc.authoring.nodes.find(n=>n.module?.constructor?.width===16).id;
 assert.notEqual(replacement,root);const newSlot=doc.authoring.nodes.find(n=>n.id===replacement).ports.inputs.find(p=>p.label==='skip');const edge=doc.authoring.edges.find(e=>e.source===external);
 assert.equal(edge.target,newSlot.node);assert.equal(edge.target_port,newSlot.port);assert.equal(doc.graph.studioPresentation.nodes[replacement].alias,'Preserved source module alias');assert.equal(doc.graph.studioPresentation.nodes[root],undefined);
 assert.ok(doc.graph.generic.authoring.nodes.some(n=>JSON.stringify(n.constructor?.args)==='[16,16]'));
 checks.push('constructor reparse changes actual extracted facts, remaps exact boundary slots and retains Studio presentation on the replacement root');
 const before=JSON.stringify(doc.graph.generic.authoring),undo=doc.undo;
 const incompatible=source.replace('def forward(self,x,skip):','def forward(self,x):').replace('self.linear(x)+skip','self.linear(x)');await sourceFields(incompatible,16);await page.getByRole('button',{name:'重新解析并替换选中构件',exact:true}).click();
 await page.locator('.summary-authoring-panel [role=alert]').filter({hasText:'已连接输入'}).waitFor();doc=await snapshot();assert.equal(JSON.stringify(doc.graph.generic.authoring),before);assert.equal(doc.undo,undo);assert.equal(await page.getByLabel('Summary 模块源码',{exact:true}).inputValue(),incompatible);
 await page.getByRole('button',{name:'撤销画布编辑',exact:true}).click();doc=await waitFor(d=>d.authoring.nodes.some(n=>n.module?.constructor?.width===7));await page.getByRole('button',{name:'重做画布编辑',exact:true}).click();doc=await waitFor(d=>d.authoring.nodes.some(n=>n.module?.constructor?.width===16));
 checks.push('removing a connected input rejects atomically and retains entered source; shared undo/redo restores original/reparsed modules');
 const portable=(await command('save')).document;const requestsBefore=modules.length;await page.reload({waitUntil:'networkidle'});await ready();doc=await waitFor(d=>d.caseId===portable.caseId);assert.deepEqual(doc.graph.generic.authoring,portable.graph.generic.authoring);assert.equal(modules.length,requestsBefore);
 checks.push('saved source modules reopen with source text, parsed constructor facts and slots without an implicit recompile');
 const response=await page.request.post(base+'/api/preview/analyze',{data:{files:{'recipes.py':source},entry:'recipes:Block',semanticMode:'summary'}});assert.equal(response.ok(),true);const bundle=await response.json();await command('load',{bundle});await editMode().click();await page.getByRole('heading',{name:'Summary 模型编辑',exact:true}).waitFor();
 await page.locator('.summary-authoring-panel').getByText('原始构件精确重建',{exact:true}).click();await page.getByRole('button',{name:'清空搭建并开始参考重建',exact:true}).click();doc=await waitFor(d=>d.authoring.recipe&&d.authoring.nodes.length===0);const parts=doc.authoring.recipe.parts;
 for(let i=parts.length-1;i>=0;i--){const part=parts[i];await page.getByRole('button',{name:`恢复构件 · ${part.title}（${part.nodes}）`,exact:true}).click();await waitFor(d=>d.authoring.recipe.parts[i].present);}
 await page.getByRole('button',{name:'恢复现有端点的精确连接',exact:true}).click();doc=await waitFor(d=>d.authoring.recipe.exact);assert.deepEqual(doc.graph.generic.ir,bundle.ir.semantic_ir);assert.equal(doc.adapter,undefined);const reconstructed=doc;
 checks.push('Studio reference reconstruction restores components in reverse order, original parent identities and every exact dependency back to the original IR');
 await page.locator('.summary-authoring-panel').getByText('源码模块与参数重解析',{exact:true}).click();await sourceFields();let release,seen;const held=new Promise(r=>release=r),arrived=new Promise(r=>seen=r);
 await page.route('**/api/preview/authoring/module',async route=>{const result=await route.fetch();seen();await held;await route.fulfill({response:result});});
 await page.getByRole('button',{name:'解析并加入源码模块',exact:true}).click();await Promise.race([arrived,new Promise((_,reject)=>setTimeout(()=>reject(Error('compile intercept timeout')),20000))]);await menu('新建空白模型');const switched=await waitFor(d=>d.caseId!==reconstructed.caseId&&d.authoring.nodes.length===0);release();await page.waitForTimeout(400);doc=await snapshot();assert.equal(doc.caseId,switched.caseId);assert.equal(doc.authoring.nodes.length,0);
 checks.push('a real delayed compiler response cannot enter a newly selected workspace');
 await page.unroute('**/api/preview/authoring/module');await command('load',{bundle:reconstructed});await editMode().click();await page.getByRole('heading',{name:'Summary 模型编辑',exact:true}).waitFor();await page.locator('.summary-authoring-panel').getByText('原始构件精确重建',{exact:true}).click();
 assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);assert.ok(modules.length>=4);assert.equal(modules[0].constructor.width,7);assert.equal(modules[1].constructor.width,16);
 await page.screenshot({path:output.replace(/\.json$/,'.png'),fullPage:true});await fs.writeFile(output,JSON.stringify({ok:true,checks,browserErrors:errors,sourceWrites:writes,moduleRequests:modules},null,2)+'\n');console.log(JSON.stringify({ok:true,checks:checks.length,output}));
}catch(error){await page.screenshot({path:output.replace(/\.json$/,'-failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(output,JSON.stringify({ok:false,checks,browserErrors:errors,sourceWrites:writes,error:String(error)},null,2));throw error;}finally{await browser.close();}
