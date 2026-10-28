import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const args = process.argv.slice(2), option = (key, fallback) => args.includes(key) ? args[args.indexOf(key) + 1] : fallback;
const { chromium } = await import(option('--playwright') ? pathToFileURL(option('--playwright')).href : 'playwright');
const base = option('--base', 'http://127.0.0.1:8789'), output = option('--output', '/tmp/summary-documents-browser.json');
const browser = await chromium.launch({ headless: true, ...(option('--chromium') ? { executablePath: option('--chromium') } : {}), args: ['--no-sandbox'] });
let page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
const checks = [], errors = [], sourceWrites = [];
page.setDefaultNavigationTimeout(120000);
function observePage(target) {
  target.on('pageerror', error => errors.push(error.message));
  target.on('request', request => { if (request.method() === 'POST' && /edit-source|transactions|runtime\/run/.test(request.url())) sourceWrites.push(request.url()); });
}
observePage(page);
async function command(name, payload = {}) {
  return page.evaluate(({ name, payload }) => new Promise((resolve, reject) => {
    const child = document.querySelector('iframe').contentWindow, requestId = 'documents-' + crypto.randomUUID();
    const timer = setTimeout(() => { window.removeEventListener('message', listener); reject(Error('Bridge timeout: ' + name)); }, 60000);
    function listener(event) {
      if (event.source !== child || event.origin !== location.origin || event.data?.requestId !== requestId) return;
      clearTimeout(timer); window.removeEventListener('message', listener);
      if (event.data.type.endsWith(':error')) reject(Error(JSON.stringify(event.data))); else resolve(event.data);
    }
    window.addEventListener('message', listener);
    child.postMessage({ type: 'archcanvas:preview:' + name, requestId, ...payload }, location.origin);
  }), { name, payload });
}
const snapshot = async () => (await command('snapshot')).document;
async function importJson(value) {
  await page.locator('.workspace-menu > summary').click();
  await page.getByRole('button', { name: '导入 Python 源码', exact: true }).click();
  await page.getByRole('tab', { name: '工程目录 / 已有文档', exact: true }).click();
  await page.getByRole('button', { name: '选择 Summary / 编辑 JSON', exact: true }).waitFor();
  await page.getByLabel('选择源文件', { exact: true }).setInputFiles({ name: 'summary.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(value)) });
  await page.getByRole('dialog', { name: '打开模型', exact: true }).waitFor({ state: 'hidden', timeout: 60000 });
  await page.waitForFunction(() => !document.querySelector('.semantic-frontier .segmented button')?.disabled);
  return snapshot();
}
async function verify(doc, ir) {
  assert.equal(doc.sourceAvailable, false); assert.equal(doc.adapter, undefined);
  assert.equal(doc.graph.sourceAdapter, undefined);
  assert.equal(doc.importedDocument.sourceVerified, false); assert.equal(doc.importedDocument.modelExecuted, false);
  assert.deepEqual(doc.graph.generic.ir, ir);
  // Validate the actual committed snapshot, including route geometry and accounting.
  const check = await page.locator('iframe').evaluate((iframe, graph) => {
    const w = iframe.contentWindow, result = w.SummaryEngine.validateView(graph);
    return { accepted: w.ArchCanvasSemanticView.accepts(graph, result), source: result.source, invalid: result.edges.filter(([, value]) => !value.ok), routing: graph.nativeRouting };
  }, doc.graph);
  assert.equal(check.accepted, true); assert.equal(check.source.ok, true);
  assert.deepEqual(check.invalid, []); assert.equal(check.routing.complete, true);
  await page.getByRole('tree', { name: '模型层级' }).waitFor();
}
try {
  await page.goto(base + '/?benchmark=1&study=1', { waitUntil: 'networkidle' });
  assert.equal(await page.locator('[aria-label="Studio 性能验收"]').count(), 0);
  assert.equal(await page.evaluate(() => typeof window.__ARCHCANVAS_BENCHMARK__), 'undefined');
  checks.push('production entry no longer exposes benchmark hooks or panels for the retired formal scene');
  await page.waitForFunction(() => !document.querySelector('.semantic-frontier .segmented button')?.disabled, { timeout: 60000 });
  const response = await page.request.post(base + '/api/preview/analyze', { data: { files: { 'doc.py': 'from torch import nn\nclass Model(nn.Module):\n def forward(self,x):\n  return x+x\n' }, entry: 'doc:Model', semanticMode: 'summary' } });
  assert.equal(response.ok(), true); const bundle = await response.json(), ir = bundle.ir.semantic_ir;
  let doc = await importJson(ir); await verify(doc, ir);
  const variants = await page.locator('iframe').evaluate((iframe, graph) => {
    const w = iframe.contentWindow;
    return [w.SummaryNativeSemantic.document(graph), { schema: 'semantic-canvas/1', ir: graph.generic.ir, state: graph.generic.state, geometry: { historical: true } }, { schema: 'archcanvas-architecture-document/1', ir: graph.generic.ir, state: graph.generic.state }, w.SemanticAuthoring.fromIR(graph.generic.ir)];
  }, doc.graph);
  checks.push('Studio project/document tab imports raw v2 IR through the native authority, with honest provenance and legal routes');
  for (const value of variants) {
    doc = await importJson(value); await verify(doc, ir);
    assert.deepEqual(doc.nativeDocument.document, value);
    checks.push('Studio imports and preserves ' + value.schema);
  }
  await page.locator('.summary-view > summary').click();
  assert.match(await page.locator('.summary-view').innerText(), /尚未验证 Python 源码/);
  for (const [name, preset] of [['F0 概览', 'overview'], ['F1 详图', 'detail'], ['F0 概览', 'overview']]) {
    await page.getByRole('button', { name, exact: true }).click();
    await page.waitForFunction(preset => [...document.querySelectorAll('.semantic-frontier .segmented button')].some(button => button.classList.contains('active') && button.textContent.startsWith(preset === 'overview' ? 'F0' : 'F1')), preset);
    doc = await snapshot(); assert.equal(doc.frontierPreset, preset); await verify(doc, ir);
  }
  checks.push('host F0/F1 controls retain imported authoring evidence, hierarchy, provenance and route legality');
  const source = await command('request-source');
  assert.match(source.type, /source-unavailable$/); assert.match(source.message, /未与 Python 文本验证绑定/);
  await page.getByRole('button', { name: '查看源码证据', exact: true }).click();
  await page.getByText('当前为 Summary 导入文档，源码位置尚未与 Python 文本验证绑定；可通过原始文档检查声明证据。', { exact: true }).waitFor();
  await page.getByRole('button', { name: '关闭源码', exact: true }).click();
  await page.locator('.workspace-menu > summary').click();
  await page.getByRole('button', { name: '正式源码工作副本', exact: true }).click();
  await page.getByText(/当前为 Summary 导入文档；源码证据尚未与 Python 文本验证绑定/).waitFor();
  assert.equal(await page.locator('.authoring-studio').count(), 0);
  assert.deepEqual((await snapshot()).graph.generic.ir, ir);
  checks.push('imported documents show honest source-drawer evidence, deny unbound formal editing and never forge a verified adapter');

  const id = doc.graph.nodes.find(node => !node.modelHeading).id;
  await command('visual', { operations: [{ type: 'alias', id, label: '文档显示别名' }, { type: 'nodeStyle', id, style: { fill: '#ffeedd' } }, { type: 'annotation', annotation: { id: 'document-note', text: 'Studio 面板与 Summary 画布', x: 20, y: 20, width: 220 } }] });
  await command('zoom', { factor: 1.25 });
  const portable = (await command('save')).document;
  await command('load', { bundle: portable });
  let restored = await snapshot();
  assert.deepEqual(restored.graph.studioPresentation, portable.graph.studioPresentation);
  assert.deepEqual(restored.graph.studioCamera, portable.graph.studioCamera);
  assert.deepEqual(restored.nativeDocument, portable.nativeDocument);
  checks.push('portable editing document restores original authoring document, visual overlays and live camera');
  for (const corrupt of [
    value => value.graph.generic.ir.nodes[0].label = 'forged',
    value => value.nativeDocument.document.title = 'forged',
    value => value.graph.generic.authoring.title = 'forged',
    value => value.graph.caseId = 'wrong-case',
    value => value.graph.nodes[0].html += '<svg onload="window.injected=true"/>',
    value => value.graph.extras = '<svg onload="window.injected=true"/>',
  ]) { const forged = structuredClone(portable); corrupt(forged); await assert.rejects(command('load', { bundle: forged }), /原始文档语义|身份与内容|案例身份|原生文档/); }
  assert.deepEqual((await snapshot()).graph.generic.ir, ir);
  assert.equal(await page.locator('iframe').evaluate(iframe => iframe.contentWindow.injected), undefined);
  checks.push('canonical IR, original document digest, authoring authority, case and SVG payload tampering reject without replacing current graph');
  const dismiss = page.getByRole('button', { name: '关闭操作反馈' }); if (await dismiss.isVisible()) await dismiss.click();
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await page.getByText('当前预览已保存到浏览器；可下载编辑 JSON 搬运完整图。', { exact: true }).waitFor();
  const saved = await snapshot();
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForFunction(() => !document.querySelector('.semantic-frontier .segmented button')?.disabled, { timeout: 60000 });
  restored = await snapshot(); await verify(restored, ir);
  assert.equal(restored.caseId, saved.caseId);
  assert.deepEqual(restored.graph.studioPresentation, saved.graph.studioPresentation);
  assert.deepEqual(restored.graph.studioCamera, saved.graph.studioCamera);
  assert.deepEqual(restored.nativeDocument, saved.nativeDocument);
  checks.push('top save and real page reload restore the imported case, origin record, authoring evidence, overlays and camera');
  const svg = await command('svg'); assert.match(svg.svg, /<svg/); assert.doesNotMatch(svg.svg, /id="handleLayer"|class="wire-hit"/);
  const [download] = await Promise.all([page.waitForEvent('download'), command('export-json')]);
  const json = JSON.parse(await fs.readFile(await download.path(), 'utf8'));
  assert.deepEqual(json.nativeDocument, saved.nativeDocument); assert.deepEqual(json.graph.generic.ir, ir);
  await importJson(json); await verify(await snapshot(), ir);
  checks.push('SVG export omits editor targets; downloaded JSON imports through the Studio dialog with full origin evidence');
  await fs.writeFile(output.replace(/\.json$/, '-portable.json'), JSON.stringify(json, null, 2) + '\n');
  page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
  page.setDefaultNavigationTimeout(120000);
  observePage(page);
  await page.goto(base, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => !document.querySelector('.semantic-frontier .segmented button')?.disabled, null, { timeout: 60000 });
  assert.equal(await page.locator('iframe').evaluate(iframe => iframe.contentWindow.SummaryRecursiveStorage.get('summary-document:index:v1')), null);
  const independent = await importJson(json);
  await verify(independent, ir);
  assert.deepEqual(independent.nativeDocument, json.nativeDocument);
  assert.deepEqual(independent.graph.studioPresentation, json.graph.studioPresentation);
  assert.deepEqual(independent.graph.studioCamera, json.graph.studioCamera);
  checks.push('the downloaded editing JSON restores in a fresh browser context with no document index, source package or prior preview storage');

  await command('fit');
  if (!await page.locator('.summary-view').evaluate(element => element.open)) await page.locator('.summary-view > summary').click();
  await page.screenshot({ path: output.replace(/\.json$/, '.png'), fullPage: true });
  assert.deepEqual(errors, []); assert.deepEqual(sourceWrites, []);
  checks.push('all document import and visual operations issue no formal source edit, transaction or model execution request');
  const result = { ok: true, checks, browserErrors: errors, sourceWrites };
  await fs.writeFile(output, JSON.stringify(result, null, 2) + '\n'); console.log(JSON.stringify(result));
} catch (error) {
  await page.screenshot({ path: output.replace(/\.json$/, '-failed.png'), fullPage: true });
  await fs.writeFile(output, JSON.stringify({ ok: false, checks, browserErrors: errors, error: String(error), body: await page.locator('body').innerText() }, null, 2));
  throw error;
} finally { await browser.close(); }
