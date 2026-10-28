import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
const args = process.argv.slice(2), option = (key, fallback) => args.includes(key) ? args[args.indexOf(key) + 1] : fallback;
const { chromium } = await import(option('--playwright') ? pathToFileURL(option('--playwright')).href : 'playwright');
const output = option('--output', '/tmp/summary-preview-retirement-browser.json'), base = option('--base', 'http://127.0.0.1:8789');
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
async function waitFor(test, allowBusy = false) { const end = Date.now() + 60000; while (Date.now() < end) { const doc = await snapshot(); if ((allowBusy || !doc.busy) && test(doc)) return doc; await new Promise(r => setTimeout(r, 100)); } throw Error('state condition timed out'); }
async function ready() { await page.waitForFunction(() => document.querySelector('iframe') && !document.querySelector('.semantic-frontier .segmented button')?.disabled, { timeout: 60000 }); }
async function menu(name) { await page.locator('.workspace-menu > summary').click(); await page.getByRole('button', { name, exact: true }).click(); }
async function accept(doc) { const result = await page.locator('iframe').evaluate((iframe, graph) => { const w = iframe.contentWindow, validation = w.SummaryEngine.validateView(graph); return { accepted: w.ArchCanvasSemanticView.accepts(graph, validation), source: validation.source, routes: validation.edges.filter(([,v]) => !v.ok).map(([id]) => id), routing: graph.nativeRouting }; }, doc.graph); assert.equal(result.accepted, true); assert.equal(result.source.ok, true); return result; }

try {
 await page.goto(base,{waitUntil:'networkidle'});await ready();await menu('新建空白模型');await page.getByRole('heading',{name:'Summary 模型编辑',exact:true}).waitFor();
 await page.locator('.summary-authoring-panel').getByRole('button',{name:'Residual',exact:true}).click();let doc=await waitFor(d=>d.authoring.nodes.length>5);
 await page.getByRole('group',{name:'工作区模式',exact:true}).getByRole('button',{name:'视图',exact:true}).click();
 await command('expand-all');doc=await waitFor(d=>d.graph.edges.length>0);
 const iframe=page.frameLocator('iframe');const identity=await page.locator('iframe').evaluate(el=>{el.dataset.retirementIdentity='same';return el.getAttribute('src');});
 const node=doc.graph.nodes.filter(n=>!n.junction&&!n.expanded&&doc.graph.edges.some(e=>e.source===n.id||e.target===n.id)).at(-1);assert.ok(node);
 await command('focus',{nodeId:node.id});doc=await waitFor(d=>d.selectedNodes.includes(node.id));
 const initial=await snapshot(),box=await iframe.locator(`[data-node-id="${node.id}"] .node-hit`).boundingBox();assert.ok(box);
 await page.mouse.move(box.x+box.width*.4,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*.4+22,box.y+box.height*.5+12,{steps:4});
 await waitFor(d=>d.dragging,true);await command('cancel-gesture');await page.mouse.up();doc=await waitFor(d=>!d.busy);
 assert.deepEqual(doc.graph.nodes,initial.graph.nodes);assert.deepEqual(doc.graph.edges,initial.graph.edges);assert.equal(doc.undo,initial.undo);assert.equal(doc.redo,initial.redo);assert.deepEqual(doc.graph.generic.ir,initial.graph.generic.ir);
 checks.push('native node drag cancellation restores complete nodes, edges, facts and both history counts; late mouse release cannot commit');
 const panBefore=(await command('snapshot')).camera,stage=await iframe.locator('#stage').boundingBox();assert.ok(stage);
 await page.mouse.move(stage.x+stage.width*.5,stage.y+stage.height*.5);await page.mouse.down({button:'middle'});await page.mouse.move(stage.x+stage.width*.5+60,stage.y+stage.height*.5+30,{steps:4});
 const panDuring=(await command('snapshot')).camera;assert.notDeepEqual(panDuring,panBefore);await command('cancel-gesture');await page.mouse.up({button:'middle'});assert.deepEqual((await command('snapshot')).camera,panBefore);assert.equal((await snapshot()).undo,initial.undo);
 checks.push('middle-button pan cancels to the exact native camera without changing model, selection or history');
 await page.locator('.summary-interaction > summary').click();
 const beforePorts=await snapshot();await page.getByRole('button',{name:'恢复所选自动连接点',exact:true}).click();doc=await waitFor(d=>!d.busy&&d.undo===beforePorts.undo+1);
 assert.deepEqual(doc.graph.generic.ir,beforePorts.graph.generic.ir);assert.deepEqual(doc.graph.edges.map(e=>[e.id,e.source,e.target,e.binding]),beforePorts.graph.edges.map(e=>[e.id,e.source,e.target,e.binding]));
 await page.getByRole('button',{name:'撤销画布编辑',exact:true}).click();doc=await waitFor(d=>d.undo===beforePorts.undo);assert.deepEqual(doc.graph.edges,beforePorts.graph.edges);await page.getByRole('button',{name:'重做画布编辑',exact:true}).click();doc=await waitFor(d=>d.undo===beforePorts.undo+1);
 checks.push('retained folding port panel resets actual Summary physical endpoints as one reversible transaction while canonical operands stay unchanged');
 const beforeLayout=await snapshot();await page.locator('.summary-interaction').getByRole('button',{name:'优化当前布线',exact:true}).click();doc=await waitFor(d=>!d.busy&&d.undo===beforeLayout.undo+1);
 assert.deepEqual(doc.graph.nodes.map(n=>[n.id,n.x,n.y,n.w,n.h]),beforeLayout.graph.nodes.map(n=>[n.id,n.x,n.y,n.w,n.h]));assert.deepEqual(doc.graph.generic.ir,beforeLayout.graph.generic.ir);await accept(doc);
 checks.push('retained layout panel uses native routing with unchanged node geometry and complete semantic facts');
 const zoomBefore=(await command('snapshot')).camera;await iframe.locator('#graph').hover();await page.mouse.wheel(0,-140);await page.waitForFunction(()=>true);const zoomAfter=(await command('snapshot')).camera;assert.ok(zoomAfter.w<zoomBefore.w);await page.getByRole('button',{name:'适合画布',exact:true}).click();
 const fitEnd=Date.now()+20000;while(Date.now()<fitEnd&&(await command('snapshot')).camera.w===zoomAfter.w)await new Promise(r=>setTimeout(r,50));const fit=(await command('snapshot')).camera;assert.notDeepEqual(fit,zoomAfter);
 await page.getByRole('button',{name:'收起模型层级面板',exact:true}).click();assert.deepEqual((await command('snapshot')).camera,fit);await page.getByRole('button',{name:'展开模型层级面板',exact:true}).click();assert.deepEqual((await command('snapshot')).camera,fit);
 assert.equal(await page.locator('iframe').getAttribute('src'),identity);assert.equal(await page.locator('iframe').getAttribute('data-retirement-identity'),'same');
 const hostKeys=await page.evaluate(()=>Object.keys(sessionStorage).filter(key=>key.startsWith('archcanvas.camera')));assert.deepEqual(hostKeys,[]);
 checks.push('wheel zoom, host fit and panel resizing retain the sole native camera and mounted iframe with no retired host camera storage');
 const saved=(await command('save')).document;await page.reload({waitUntil:'networkidle'});await ready();doc=await waitFor(d=>d.caseId===saved.caseId);assert.deepEqual(doc.graph.generic.ir,saved.graph.generic.ir);assert.deepEqual(doc.graph.studioCamera,saved.graph.studioCamera);
 assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);await page.screenshot({path:output.replace(/\.json$/,'.png'),fullPage:true});await fs.writeFile(output,JSON.stringify({ok:true,checks,browserErrors:errors,sourceWrites:writes},null,2)+'\n');console.log(JSON.stringify({ok:true,checks:checks.length,output}));
}catch(error){await page.screenshot({path:output.replace(/\.json$/,'-failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(output,JSON.stringify({ok:false,checks,browserErrors:errors,sourceWrites:writes,error:String(error)},null,2));throw error;}finally{await browser.close();}
