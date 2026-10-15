import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Exercises the real built Studio in an isolated browser context. No persistent
// user profile, catalog document or model source is edited by this smoke run.
const args = process.argv.slice(2);
const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const evidence = path.resolve(option('--output-dir', path.join(root, 'docs/evidence/preview-toolbar-20261014')));
const base = option('--base', 'http://127.0.0.1:8891').replace(/\/$/, '');
const automation = option('--playwright', process.env.ARCHCANVAS_TEST_PLAYWRIGHT ?? '/home/fzg/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs');
const executablePath = option('--chromium', process.env.ARCHCANVAS_TEST_CHROMIUM ?? '/home/fzg/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome');
const { chromium } = await import(pathToFileURL(automation).href);
const browser = await chromium.launch({ headless: true, executablePath, args: ['--no-sandbox'] });
const context = await browser.newContext({ viewport: { width: 1640, height: 1080 }, acceptDownloads: true });
const page = await context.newPage();
const checks = [], errors = [], saves = [], networkAssets = [];
let lastState;
page.on('pageerror', error => errors.push(error.message));
page.on('response', response => {
  if (response.request().method() === 'PUT' && /\/api\/documents\//.test(response.url())) saves.push({ url: response.url(), status: response.status() });
  if (/\/assets\/[^/]+\.js$/.test(response.url())) networkAssets.push(response.url());
});
await context.addInitScript(() => {
  window.toolbarSmokeMessages = [];
  window.addEventListener('message', event => {
    if (event.origin === location.origin && typeof event.data?.type === 'string' && event.data.type.startsWith('archcanvas:preview:')) window.toolbarSmokeMessages.push(event.data);
  });
  window.toolbarSmokeCommand = (name, payload = {}) => new Promise((resolve, reject) => {
    const frame = document.querySelector('iframe'), requestId = crypto.randomUUID();
    const timeout = setTimeout(() => { window.removeEventListener('message', receive); reject(Error(name + ' timed out')); }, 30000);
    function receive(event) {
      if (event.source !== frame?.contentWindow || event.origin !== location.origin || event.data?.requestId !== requestId) return;
      clearTimeout(timeout); window.removeEventListener('message', receive);
      event.data.type.endsWith(':error') ? reject(Error(event.data.message)) : resolve(event.data);
    }
    window.addEventListener('message', receive);
    frame.contentWindow.postMessage({ type: 'archcanvas:preview:' + name, requestId, ...payload }, location.origin);
  });
});
const command = (name, payload) => page.evaluate(({ name, payload }) => window.toolbarSmokeCommand(name, payload), { name, payload });
const snapshot = async () => (lastState = await command('snapshot'));
const waitSnapshot = async predicate => {
  const start = Date.now();
  while (Date.now() - start < 30000) {
    const state = await snapshot();
    if (predicate(state)) return state;
    await page.waitForTimeout(80);
  }
  throw new Error('Preview state did not reach expected condition');
};
const canonical = value => JSON.stringify(value, (_key, item) => item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item);
const digest = value => createHash('sha256').update(canonical(value)).digest('hex');
// Recursive frontiers/drafts are memoized render caches and are intentionally
// refreshed by flushPersist; compare graph semantics and visible geometry only.
const stableGraph = graph => ({
  canvas: graph.canvas, nodes: graph.nodes, edges: graph.edges,
  sourceDraftOperations: graph.sourceDraftOperations ?? [],
  attachments: graph.attachments ?? [], routeLabels: graph.routeLabels ?? [],
  junctionMarkers: graph.junctionMarkers ?? [],
  recursive: { authority: graph.recursive?.authority, state: { studioPresentation: graph.recursive?.state?.studioPresentation } },
});
const graphDigest = graph => digest(stableGraph(graph));
const mark = (name, details) => { checks.push({ name, ...(details ? { details } : {}) }); console.log('PASS ' + name); };
const parentTool = name => page.getByRole('button', { name, exact: true });
let frame;
const clickFit = async () => { await page.locator('.canvas-toolbar button[title^="适合画布"]').click(); await snapshot(); };
const screenPoint = async (selector, fraction = .5) => {
  const outer = await page.locator('iframe').boundingBox();
  const point = await frame.locator(selector).first().evaluate((element, fraction) => {
    if (element instanceof SVGPathElement) {
      const point = element.getPointAtLength(element.getTotalLength() * fraction), transformed = point.matrixTransform(element.getScreenCTM());
      return { x: transformed.x, y: transformed.y };
    }
    const rect = element.getBoundingClientRect();
    return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
  }, fraction);
  return { x: outer.x + point.x, y: outer.y + point.y };
};

await fs.mkdir(evidence, { recursive: true });
try {
  await page.goto(base + '/');
  await page.waitForFunction(() => window.toolbarSmokeMessages.some(message => message.type === 'archcanvas:preview:ready'));
  await page.waitForFunction(() => document.querySelector('.import-button') && !document.querySelector('.import-button').disabled);
  frame = page.frame({ url: /preview\/yworks_edge_router_lab\/index.html/ });
  assert.ok(frame);

  const className = 'ToolbarSmoke' + Date.now();
  const source = `from torch import nn\n\nclass ${className}(nn.Module):\n    def __init__(self):\n        super().__init__()\n        self.project = nn.Linear(4, 4)\n        self.act = nn.ReLU()\n    def forward(self, features):\n        value = self.project(features)\n        return self.act(value)\n`;
  await page.locator('.import-button').click();
  await page.getByLabel('模型类名', { exact: true }).fill(className);
  await page.getByLabel('文件名', { exact: true }).fill('toolbar_smoke.py');
  await page.getByLabel('Python 源码', { exact: true }).fill(source);
  await page.getByRole('button', { name: '静态分析并打开画布', exact: true }).click();
  await page.getByRole('dialog', { name: '从 Python 源码开始', exact: true }).waitFor({ state: 'detached' });
  await waitSnapshot(state => state.document?.adapter?.entry === className || state.document?.adapter?.entry?.endsWith(':' + className));
  await page.waitForFunction(() => document.querySelector('.project-breadcrumb')?.textContent.includes('ToolbarSmoke'));
  await parentTool('选择对象').waitFor({ state: 'visible' });
  await page.getByRole('button', { name: '导出', exact: true }).waitFor({ state: 'visible' });
  await page.waitForFunction(() => !Array.from(document.querySelectorAll('.topbar button')).find(button => button.textContent.includes('导出'))?.disabled);
  mark('unique source fixture opens in the real Studio and original panels remain', { className });

  assert.equal(await page.locator('.canvas-toolbar:visible').count(), 1);
  assert.equal(await frame.locator('.toolbar').isVisible(), false);
  assert.equal(await frame.locator('#fit').isVisible(), false);
  assert.equal(await frame.locator('#fitWidth').isVisible(), true);
  assert.equal(await page.getByRole('button', { name: /平移/ }).count(), 0);
  assert.equal(await frame.getByRole('button', { name: /平移/ }).count(), 0);
  assert.equal(await page.getByRole('button', { name: '保存', exact: true }).count(), 1);
  assert.equal(await page.getByRole('button', { name: '导出', exact: true }).count(), 1);
  mark('one parent toolbar and save/export entry; child toolbar/fit/pan controls are hidden');

  for (const [name, tool, shortcut] of [['创建连接', 'connect', 'c'], ['编辑折点', 'bend', 'b'], ['选择对象', 'select', 'v']]) {
    await parentTool(name).click();
    await frame.waitForFunction(tool => document.querySelector(`[data-tool="${tool}"]`)?.classList.contains('active'), tool);
    assert.equal(await parentTool(name).getAttribute('aria-pressed'), 'true');
    await frame.locator('#graph').press(shortcut);
    assert.equal(await parentTool(name).getAttribute('aria-pressed'), 'true');
  }
  await frame.locator('#graph').press('c');
  await page.waitForFunction(() => document.querySelector('[aria-label="创建连接"]')?.getAttribute('aria-pressed') === 'true');
  await frame.locator('#graph').press('b');
  await page.waitForFunction(() => document.querySelector('[aria-label="编辑折点"]')?.getAttribute('aria-pressed') === 'true');
  await frame.locator('#graph').press('v');
  await page.waitForFunction(() => document.querySelector('[aria-label="选择对象"]')?.getAttribute('aria-pressed') === 'true');
  mark('parent tools and iframe V/C/B shortcuts share actual active modes');

  const baseState = await snapshot(), firstNodeId = baseState.document.graph.nodes.find(node => !node.junction && !node.expanded)?.id;
  assert.ok(firstNodeId);
  await frame.locator(`[data-node-id="${firstNodeId}"] .node-hit`).click({ position: { x: 8, y: 8 } });
  await waitSnapshot(state => state.selection.nodeId === firstNodeId);
  const firstEdgeId = baseState.document.graph.edges[0].id;
  const panTargets = [
    ['node', `[data-node-id="${firstNodeId}"] .node-hit`],
    ['edge', `[data-edge-id="${firstEdgeId}"] .wire-path`],
    ['label', '[data-node-id] text'],
    ['blank', null],
  ];
  for (const [name, selector] of panTargets) {
    await clickFit();
    const before = await snapshot();
    let point;
    if (selector) point = await screenPoint(selector);
    else { const box = await frame.locator('#graph').boundingBox(); point = { x: box.x + 24, y: box.y + box.height - 24 }; }
    await page.mouse.move(point.x, point.y);
    await page.mouse.down({ button: 'middle' });
    await page.mouse.move(point.x - 52, point.y - 38, { steps: 8 });
    await page.mouse.up({ button: 'middle' });
    const after = await snapshot();
    assert.notDeepEqual(after.camera, before.camera, name + ' middle drag must pan');
    assert.equal(graphDigest(after.document.graph), graphDigest(before.document.graph), name + ' middle drag must preserve graph');
    assert.equal(after.undo, before.undo); assert.equal(after.redo, before.redo);
    assert.deepEqual(after.selection, before.selection);
    mark('middle drag on ' + name + ' changes camera while preserving graph, history and selection');
  }

  const routeGridBefore = await frame.locator('#gridEnabled').isChecked();
  await page.getByRole('button', { name: '显示点阵网格', exact: true }).click();
  await snapshot();
  assert.equal(await frame.locator('#gridEnabled').isChecked(), routeGridBefore);
  await page.getByRole('button', { name: '显示点阵网格', exact: true }).click();
  assert.equal(await frame.locator('#gridEnabled').isChecked(), routeGridBefore);
  mark('display dot grid toggle preserves routing candidate grid policy');

  await clickFit();
  await parentTool('创建连接').click();
  const hits = frame.locator('[data-node-id] .node-hit');
  const endpoints = await hits.evaluateAll(elements => elements.slice(0, 2).map(element => element.closest('[data-node-id]').getAttribute('data-node-id')));
  const beforeDraft = await snapshot();
  await hits.nth(0).click({ position: { x: 8, y: 8 } });
  await hits.nth(1).click({ position: { x: 8, y: 8 } });
  const withDraft = await waitSnapshot(state => state.document.graph.edges.some(edge => edge.draft));
  const draft = withDraft.document.graph.edges.find(edge => edge.draft);
  assert.equal(draft.source, endpoints[0]); assert.equal(draft.target, endpoints[1]);
  assert.equal(withDraft.document.graph.edges.length, beforeDraft.document.graph.edges.length + 1);
  await page.getByRole('heading', { name: '视觉草稿连接', exact: true }).waitFor();
  mark('parent connect tool creates and selects a visual draft edge');

  await parentTool('编辑折点').click();
  await waitSnapshot(state => state.tool === 'bend');
  const wireHit = frame.locator(`[data-edge-id="${draft.id}"] .wire-hit`);
  await wireHit.click({ force: true });
  const withBend = await waitSnapshot(state => state.document.graph.edges.find(edge => edge.id === draft.id)?.waypoints?.length > 0);
  assert.equal(withBend.undo, withDraft.undo + 1);
  await page.getByRole('button', { name: '撤销 Ctrl+Z', exact: true }).click();
  const withoutBend = await waitSnapshot(state => state.document.graph.edges.find(edge => edge.id === draft.id)?.waypoints?.length === 0);
  assert.equal(graphDigest(withoutBend.document.graph), graphDigest(withDraft.document.graph));
  await page.getByRole('button', { name: '撤销 Ctrl+Z', exact: true }).click();
  await waitSnapshot(state => !state.document.graph.edges.some(edge => edge.id === draft.id));
  await page.getByRole('button', { name: '重做 Ctrl+Shift+Z', exact: true }).click();
  await waitSnapshot(state => state.document.graph.edges.some(edge => edge.id === draft.id));
  await page.getByRole('button', { name: '重做 Ctrl+Shift+Z', exact: true }).click();
  const redone = await waitSnapshot(state => state.document.graph.edges.find(edge => edge.id === draft.id)?.waypoints?.length > 0);
  assert.equal(graphDigest(redone.document.graph), graphDigest(withBend.document.graph));
  mark('parent bend tool, undo and redo restore exact draft edge geometry and history');

  await parentTool('恢复初始视图').click();
  await waitSnapshot(state => !state.document.graph.edges.some(edge => edge.id === draft.id));
  await page.getByRole('button', { name: '撤销 Ctrl+Z', exact: true }).click();
  const resetUndone = await waitSnapshot(state => state.document.graph.edges.find(edge => edge.id === draft.id)?.waypoints?.length > 0);
  assert.equal(graphDigest(resetUndone.document.graph), graphDigest(withBend.document.graph));
  mark('restore initial view is one undoable action and undo restores the complete draft');

  const saveResponse = page.waitForResponse(response => response.request().method() === 'PUT' && /\/api\/documents\//.test(response.url()), { timeout: 30000 });
  await frame.locator('#graph').press('Control+s');
  assert.equal((await saveResponse).status(), 200);
  await page.waitForFunction(() => document.querySelector('.save-state')?.textContent === '已保存');
  mark('Ctrl+S with iframe focus invokes formal Studio document save', { requests: saves.length });

  const exportedState = await snapshot();
  await page.getByRole('button', { name: '导出', exact: true }).click();
  await page.getByRole('button', { name: /^编辑 JSON/ }).waitFor({ state: 'visible' });
  assert.equal(await page.locator('.export-formats button').count(), 5);
  for (const label of [/^SVG/, /^PDF/, /^PNG/, /^编辑 JSON/, /^源码包/]) assert.equal(await page.getByRole('button', { name: label }).isVisible(), true);
  await page.getByRole('button', { name: /^源码包/ }).click();
  const sourceDownloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载源码包', exact: true }).click();
  const sourceDownload = await sourceDownloadPromise, sourceDownloadPath = path.join(evidence, 'toolbar-source-adapter.json');
  await sourceDownload.saveAs(sourceDownloadPath);
  const sourcePackage = JSON.parse(await fs.readFile(sourceDownloadPath, 'utf8'));
  assert.equal(sourcePackage.schema, 'summary-source-adapter/1');
  assert.equal(sourcePackage.files[0].text, source);
  mark('unified export retains five formats and source adapter package downloads exact imported bytes');
  await page.getByRole('button', { name: /^编辑 JSON/ }).click();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载编辑 JSON', exact: true }).click();
  const download = await downloadPromise, downloadPath = path.join(evidence, 'toolbar-canvas.json');
  await download.saveAs(downloadPath);
  const exported = JSON.parse(await fs.readFile(downloadPath, 'utf8'));
  assert.equal(exported.schema, 'summary-merge-recursive/1');
  assert.equal(graphDigest(exported.graph), graphDigest(exportedState.document.graph));
  assert.ok(exported.graph.edges.some(edge => edge.id === draft.id && edge.waypoints.length));
  await page.getByRole('button', { name: '关闭导出', exact: true }).click();
  await page.locator('.import-button').click();
  await page.locator('.import-modal input[type="file"]').setInputFiles(downloadPath);
  await page.getByRole('dialog', { name: '从 Python 源码开始', exact: true }).waitFor({ state: 'detached' });
  const restored = await waitSnapshot(state => state.document.graph.edges.some(edge => edge.id === draft.id && edge.waypoints.length));
  assert.equal(graphDigest(restored.document.graph), graphDigest(exported.graph));
  mark('right upper export downloads complete editing JSON and native reimport restores exact graph');

  await page.getByRole('button', { name: '导出', exact: true }).click();
  await page.getByRole('button', { name: /^SVG/ }).click();
  const publicationResponse = page.waitForResponse(response => response.request().method() === 'POST' && response.url().endsWith('/api/preview/exports'), { timeout: 30000 });
  await page.getByRole('button', { name: '生成文件', exact: true }).click();
  const response = await publicationResponse;
  assert.equal(response.ok(), true);
  const publication = await response.json();
  const svgResponse = await page.request.get(base + publication.url);
  assert.equal(svgResponse.status(), 200);
  const svg = await svgResponse.text();
  assert.match(svg, /<svg/); assert.match(svg, /archcanvas-preview-document/);
  assert.ok(svg.includes(draft.id));
  assert.doesNotMatch(svg, /id="handleLayer"|class="wire-hit"/);
  await fs.writeFile(path.join(evidence, 'toolbar-figure.svg'), svg);
  await fs.writeFile(path.join(evidence, 'export-receipt.json'), JSON.stringify(publication.receipt, null, 2) + '\n');
  await page.getByRole('button', { name: '关闭导出', exact: true }).click();
  mark('unified export generates actual SVG containing the current graph and no editor controls', { url: publication.url });

  await parentTool('选择对象').click();
  await waitSnapshot(state => state.tool === 'select');
  await frame.locator('#graph').press('Escape');
  await page.locator('.inspector-empty').waitFor({ state: 'visible' });
  assert.match(await page.locator('.inspector-empty').innerText(), /双击\s+展开 \/ 收起模块/);
  await page.getByRole('button', { name: '页面', exact: true }).click();
  await page.getByRole('button', { name: '添加说明文字', exact: true }).click();
  await waitSnapshot(state => Object.values(state.document.graph.studioPresentation?.annotations ?? {}).some(annotation => annotation.text === '双击模块展开或收起；显示名在右侧对象面板编辑。'));
  await page.getByRole('button', { name: '撤销 Ctrl+Z', exact: true }).click();
  await waitSnapshot(state => Object.keys(state.document.graph.studioPresentation?.annotations ?? {}).length === 0);
  await page.getByRole('button', { name: '对象', exact: true }).click();
  mark('final parent bundle instructions match recursive double click and sidebar alias editing');

  assert.deepEqual(errors, []);
  await page.screenshot({ path: path.join(evidence, 'studio-toolbar.png') });
  const report = { schema: 'archcanvas-preview-toolbar-smoke/1', ok: true, base, browserProfile: 'isolated ephemeral context', checks, browserErrors: errors, formalSaves: saves, servedAssets: [...new Set(networkAssets)], editingDocumentSha256: graphDigest(exported.graph), sourceAuthoritySha256: digest(exported.graph.recursive.authority), screenshot: 'studio-toolbar.png' };
  await fs.writeFile(path.join(evidence, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  for (const filename of ['failure.json', 'failure.png', 'undo-debug.json']) await fs.rm(path.join(evidence, filename), { force: true });
  console.log(JSON.stringify({ ok: true, checks: checks.length, output: path.join(evidence, 'report.json') }));
} catch (error) {
  await page.screenshot({ path: path.join(evidence, 'failure.png') }).catch(() => {});
  await fs.writeFile(path.join(evidence, 'failure.json'), JSON.stringify({ ok: false, base, checks, browserErrors: errors, formalSaves: saves, error: error.stack, lastState, pageText: await page.locator('body').innerText().catch(() => '') }, null, 2) + '\n');
  throw error;
} finally { await browser.close(); }
