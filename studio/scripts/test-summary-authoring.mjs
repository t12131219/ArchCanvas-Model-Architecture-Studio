import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
const args = process.argv.slice(2), option = (key, fallback) => args.includes(key) ? args[args.indexOf(key) + 1] : fallback;
const { chromium } = await import(option('--playwright') ? pathToFileURL(option('--playwright')).href : 'playwright');
const output = option('--output', '/tmp/summary-authoring-browser.json'), base = option('--base', 'http://127.0.0.1:8789');
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
  await page.goto(base, { waitUntil: 'networkidle' }); await ready();
  const frame = await page.locator('iframe').elementHandle();
  await menu('新建空白模型');
  await page.getByRole('heading', { name: 'Summary 模型编辑', exact: true }).waitFor();
  let doc = await waitFor(d => !!d.authoring), workspace = doc.caseId;
  assert.equal(doc.nativeDocument.schema, 'archcanvas-summary-authoring/1'); assert.equal(doc.sourceAvailable, false);
  assert.equal(await frame.evaluate(f => f.isConnected), true);
  checks.push('Studio new-model action creates an explicit Summary workspace in the retained iframe and panel shell');
  for (const [button, count] of [['添加输入', 1], ['添加输入', 2], ['添加输出', 3]]) { await page.getByRole('button', { name: button, exact: true }).click(); doc = await waitFor(d => d.authoring.nodes.length === count); }
  const [first, second, last] = doc.authoring.nodes.map(n => n.id);
  await page.locator('.summary-authoring-panel').getByText('精确槽位连接', { exact: true }).click();
  const from = id => JSON.stringify({ node: id, port: 'out' }), to = JSON.stringify({ node: last, port: 'in' });
  await page.getByLabel('Summary 输出槽位', { exact: true }).selectOption(from(first)); await page.getByLabel('Summary 输入槽位', { exact: true }).selectOption(to);
  await page.getByRole('button', { name: '建立精确连接', exact: true }).click(); doc = await waitFor(d => d.authoring.edges.length === 1);
  assert.equal(doc.authoring.edges[0].source, first); assert.equal(doc.authoring.edges[0].target_port, 'in');
  const before = JSON.stringify(doc.graph.generic.authoring), undo = doc.undo;
  await page.getByLabel('Summary 输出槽位', { exact: true }).selectOption(from(second)); await page.getByRole('button', { name: '建立精确连接', exact: true }).click();
  await page.locator('.summary-authoring-panel [role=alert]').filter({ hasText: '输入已有连接' }).waitFor();
  doc = await snapshot(); assert.equal(JSON.stringify(doc.graph.generic.authoring), before); assert.equal(doc.undo, undo);
  await page.getByLabel('明确替换输入已有连接').check(); await page.getByRole('button', { name: '建立精确连接', exact: true }).click();
  doc = await waitFor(d => d.authoring.edges.length === 1 && d.authoring.edges[0].source === second);
  checks.push('Studio exact-slot controls create canonical authored dependencies, reject occupied inputs atomically and require explicit replacement');
  await page.getByRole('button', { name: '撤销画布编辑', exact: true }).click(); doc = await waitFor(d => d.authoring.edges[0]?.source === first);
  await page.getByRole('button', { name: '重做画布编辑', exact: true }).click(); doc = await waitFor(d => d.authoring.edges[0]?.source === second);
  await page.getByLabel('Summary 原始依赖', { exact: true }).selectOption(doc.authoring.edges[0].id); await page.getByLabel('Summary 输出槽位', { exact: true }).selectOption(from(first));
  await page.getByRole('button', { name: '重接原始依赖', exact: true }).click(); doc = await waitFor(d => d.authoring.edges[0]?.source === first);
  checks.push('one shared preview history restores/replays semantic edits; original-dependency rewiring uses exact slots');
  await command('select-nodes', { ids: [first, second, last] });
  await page.getByLabel('Summary 组合名称', { exact: true }).fill('UI Group'); await page.getByRole('button', { name: '组合为模块', exact: true }).click();
  doc = await waitFor(d => d.authoring.nodes.some(n => n.label === 'UI Group'));
  const group = doc.authoring.nodes.find(n => n.label === 'UI Group').id;
  assert.ok([first, second, last].every(id => doc.authoring.nodes.find(n => n.id === id).parent === group));
  await page.getByRole('button', { name: '保存组合到库', exact: true }).click(); doc = await waitFor(d => d.authoring.library.length === 1);
  await page.getByLabel('Summary 编辑层级', { exact: true }).selectOption(group); doc = await waitFor(d => d.authoring.scope === group);
  await page.getByRole('button', { name: 'ReLU · 原子', exact: true }).click(); doc = await waitFor(d => d.authoring.nodes.length > 4);
  const addedRoot = doc.graph.generic.authoring.nodes.find(n => n.id.startsWith('edit:') && n.parent === group && n.kind === 'composite');
  assert.ok(addedRoot); assert.equal(doc.graph.generic.ir.runtime.model_executed, false);
  checks.push('Studio multi-selection, grouping, reusable modules, nested scope and Summary atomic source presets operate on one authoring model');
  await command('focus', { nodeId: addedRoot.id });
  await page.getByLabel('Summary 节点名称', { exact: true }).fill('Edited ReLU'); await page.getByRole('button', { name: '应用节点名称', exact: true }).click();
  doc = await waitFor(d => d.authoring.nodes.some(n => n.label === 'Edited ReLU'));
  await command('visual', { operations: [{ type: 'alias', id: group, label: 'Studio alias' }, { type: 'page', page: { background: '#fff8ee' } }] });
  await page.getByRole('button', { name: '复制选中构件', exact: true }).click(); doc = await waitFor(d => d.authoring.nodes.length > 8);
  assert.equal(doc.graph.studioPresentation.nodes[group].alias, 'Studio alias'); assert.equal(doc.graph.studioPresentation.page.background, '#fff8ee');
  assert.equal(doc.caseId, workspace); await accept(doc);
  checks.push('node edits and subtree copying clear stale execution claims while retaining Studio aliases and page controls');
  const mode = page.getByRole('group', { name: '工作区模式', exact: true });
  await mode.getByRole('button', { name: '视图', exact: true }).click(); await page.getByRole('heading', { name: 'Summary 模型编辑' }).waitFor({ state: 'hidden' });
  const irBefore = JSON.stringify((await snapshot()).graph.generic.ir);
  for (const [label, preset] of [['F0 概览', 'overview'], ['F1 详图', 'detail']]) { await page.getByRole('button', { name: label, exact: true }).click(); doc = await waitFor(d => d.frontierPreset === preset); assert.equal(JSON.stringify(doc.graph.generic.ir), irBefore); await accept(doc); }
  await mode.getByRole('button', { name: '编辑', exact: true }).click(); await page.getByRole('heading', { name: 'Summary 模型编辑' }).waitFor();
  assert.equal((await snapshot()).caseId, workspace); assert.equal(await frame.evaluate(f => f.isConnected), true);
  checks.push('view/edit and F0/F1 preserve authored facts, source boundaries and the original iframe');
  await page.getByLabel('Summary 模型名称', { exact: true }).fill('Portable Summary Draft');
  await page.getByRole('button', { name: '应用模型名称', exact: true }).click();
  const auto = await waitFor(d => d.title === 'Portable Summary Draft');
  await page.locator('iframe').evaluate(async (iframe, expected) => {
    const end = Date.now() + 15000;
    while(Date.now() < end) { const record = await iframe.contentWindow.SummaryRecursiveStorage.get('summary-document:v1:' + expected.id); if(record?.documentSha256 === expected.digest) return; await new Promise(r => setTimeout(r, 100)); }
    throw Error('autosave record not durable');
  }, {id: workspace, digest: auto.nativeDocument.documentSha256});
  await page.reload({ waitUntil: 'networkidle' }); await ready();
  doc = await waitFor(d => d.caseId === workspace);
  assert.deepEqual(doc.graph.generic.authoring, auto.graph.generic.authoring);
  assert.equal(doc.graph.studioPresentation.nodes[group].alias, 'Studio alias');
  checks.push('autosave alone survives a real reload after IR identity changes, including model title and retained Studio presentation');

  await page.getByRole('button', { name: '保存', exact: true }).click(); await page.getByText('当前预览已保存到浏览器；可下载编辑 JSON 搬运完整图。', { exact: true }).waitFor();
  const portable = await snapshot(); await page.reload({ waitUntil: 'networkidle' }); await ready();
  doc = await waitFor(d => d.caseId === workspace);
  assert.deepEqual(doc.graph.generic.authoring, portable.graph.generic.authoring); assert.deepEqual(doc.graph.generic.ir, portable.graph.generic.ir);
  assert.equal(doc.graph.studioPresentation.nodes[group].alias, 'Studio alias');
  checks.push('top save and real page reload restore the stable workspace identity, latest declared facts and Studio presentation');
  const context = await browser.newContext({ viewport: { width: 1600, height: 1100 } }); page = await context.newPage(); page.setDefaultNavigationTimeout(120000); observe();
  await page.goto(base, { waitUntil: 'networkidle' }); await ready();
  await command('load', { bundle: portable }); doc = await snapshot();
  assert.equal(doc.caseId, workspace); assert.deepEqual(doc.graph.generic.authoring, portable.graph.generic.authoring); assert.equal(doc.adapter, undefined); await accept(doc);
  const forged = structuredClone(portable); forged.nativeDocument.document.title = 'forged';
  await assert.rejects(command('load', { bundle: forged }), /摘要/);
  assert.deepEqual((await snapshot()).graph.generic.authoring, portable.graph.generic.authoring);
  checks.push('portable editing JSON restores in a fresh browser context; altered draft content rejects without changing the committed model');
  const response = await page.request.post(base + '/api/preview/analyze', {data: {files: {'sourced.py': 'from torch import nn\nclass Model(nn.Module):\n def forward(self,x):\n  return x+x\n'}, entry: 'sourced:Model', semanticMode: 'summary'}});
  assert.equal(response.ok(), true); const bundle = await response.json();
  await command('load', {bundle}); doc = await snapshot();
  const sourcedId = doc.graph.nodes.find(n => !n.modelHeading).id;
  await command('visual', {operations: [{type:'alias',id:sourcedId,label:'Original source alias'}]});
  await page.getByRole('group', {name:'工作区模式',exact:true}).getByRole('button',{name:'编辑',exact:true}).click();
  await page.getByRole('heading', {name:'Summary 模型编辑',exact:true}).waitFor();
  doc = await snapshot();
  assert.notEqual(doc.caseId,bundle.id); assert.deepEqual(doc.graph.generic.authoring.baseline,bundle.ir.semantic_ir);
  assert.equal(doc.graph.studioPresentation.nodes[sourcedId].alias,'Original source alias');
  assert.equal(doc.nativeDocument.origin.sourceSha256,bundle.sourceSha256); assert.equal(doc.adapter,undefined);
  const fork = doc;
  await command('authoring', {action:'source'}); doc = await snapshot();
  assert.equal(doc.caseId,bundle.id); assert.deepEqual(doc.adapter.files,bundle.files);
  assert.equal(doc.graph.studioPresentation.nodes[sourcedId].alias,'Original source alias');
  await command('load', {bundle:fork});
  checks.push('verified native source forks into an independent declared editor, preserves Studio presentation, and can return to the untouched original source case');
  await page.locator('.summary-authoring-panel').getByText('正式源码编辑', {exact:true}).click();
  await page.getByRole('button', {name:'打开正式源码工作副本',exact:true}).click();
  const formalMode=page.locator('.authoring-studio').getByRole('group',{name:'工作区模式',exact:true});
  await formalMode.getByRole('button',{name:'视图',exact:true}).waitFor();
  await formalMode.getByRole('button',{name:'视图',exact:true}).click();
  assert.equal((await snapshot()).caseId,bundle.id);
  assert.deepEqual((await command('request-source')).source.files,Object.fromEntries(bundle.files.map(f=>[f.path,f.text])));
  await command('load',{bundle:fork});
  await page.getByRole('group',{name:'工作区模式',exact:true}).getByRole('button',{name:'编辑',exact:true}).click();
  await page.getByRole('heading',{name:'Summary 模型编辑',exact:true}).waitFor();
  checks.push('native editing panel opens the retained formal source workspace against original Python, then restores the independent Summary draft');

  await command('undo'); await command('redo'); // Empty restored history is harmless.
  const svg = await command('svg'); assert.match(svg.svg, /<svg/); assert.ok(!svg.svg.includes('<script'));
  assert.deepEqual(errors, []); assert.deepEqual(writes, []);
  const originalFiles=Object.fromEntries(bundle.files.map(f=>[f.path,f.text]));
  for(const request of analyses){assert.equal(request.entry,bundle.entry);assert.deepEqual(request.files,originalFiles);}
  checks.push('formal source bridge only analyses original frozen Python bytes; no assembled facts enter source transactions or runtime');
  await page.screenshot({ path: output.replace(/\.json$/, '.png'), fullPage: true });
  await fs.writeFile(output, JSON.stringify({ ok: true, checks, browserErrors: errors, sourceWrites: writes, sourceAnalysisRequests: analyses }, null, 2) + '\n');
  console.log(JSON.stringify({ ok: true, checks: checks.length, output }));
} catch (error) { await page.screenshot({ path: output.replace(/\.json$/, '-failure.png'), fullPage: true }).catch(() => {}); await fs.writeFile(output, JSON.stringify({ ok: false, checks, browserErrors: errors, sourceWrites: writes, sourceAnalysisRequests: analyses, error: String(error) }, null, 2)); throw error; }
finally { await browser.close(); }
