import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Real catalog navigation and retained Studio panels in an ephemeral context.
// Source bytes are inspected, never imported or executed by this browser test.
const args = process.argv.slice(2), option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const evidence = path.resolve(option('--output-dir', path.join(root, 'docs/evidence/preview-sources-20261014')));
const base = option('--base', 'http://127.0.0.1:8891').replace(/\/$/, '');
const automation = option('--playwright', '/home/fzg/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs');
const executablePath = option('--chromium', '/home/fzg/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome');
const { chromium } = await import(pathToFileURL(automation).href);
const browser = await chromium.launch({ headless: true, executablePath, args: ['--no-sandbox'] });
const context = await browser.newContext({ viewport: { width: 1640, height: 1080 }, acceptDownloads: true });
const page = await context.newPage(), checks = [], browserErrors = [], assets = [], caseResults = [];
let frame, lastState;
page.on('pageerror', error => browserErrors.push(error.message));
page.on('response', response => { if (/\/assets\/[^/]+\.js$/.test(response.url())) assets.push(response.url()); });
await context.addInitScript(() => {
  window.sourceSmokeMessages = [];
  window.addEventListener('message', event => {
    if (event.origin === location.origin && typeof event.data?.type === 'string' && event.data.type.startsWith('archcanvas:preview:')) window.sourceSmokeMessages.push(event.data);
  });
  window.sourceSmokeCommand = (name, payload = {}) => new Promise((resolve, reject) => {
    const frame = document.querySelector('iframe'), requestId = crypto.randomUUID();
    const timeout = setTimeout(() => { window.removeEventListener('message', receive); reject(Error(name + ' timed out')); }, 60000);
    function receive(event) {
      if (event.source !== frame?.contentWindow || event.origin !== location.origin || event.data?.requestId !== requestId) return;
      clearTimeout(timeout); window.removeEventListener('message', receive);
      event.data.type.endsWith(':error') || event.data.type.endsWith(':source-unavailable') ? reject(Error(event.data.message)) : resolve(event.data);
    }
    window.addEventListener('message', receive);
    frame.contentWindow.postMessage({ type: 'archcanvas:preview:' + name, requestId, ...payload }, location.origin);
  });
});
const command = (name, payload) => page.evaluate(({ name, payload }) => window.sourceSmokeCommand(name, payload), { name, payload });
const snapshot = async () => (lastState = await command('snapshot'));
const waitState = async predicate => {
  const started = Date.now();
  while (Date.now() - started < 60000) {
    const state = await snapshot();
    if (predicate(state)) return state;
    await page.waitForTimeout(100);
  }
  throw Error('Preview state did not reach expected condition');
};
const sha = text => createHash('sha256').update(text).digest('hex');
const authoritySha = state => sha(JSON.stringify(state.document.graph.recursive.authority));
const presentation = state => state.document.graph.recursive.state.studioPresentation ?? state.document.graph.studioPresentation;
const mark = (name, details) => { checks.push({ name, ...(details ? { details } : {}) }); console.log('PASS ' + name); };
const status = () => page.locator('.statusbar').innerText();
const assertNoMappingError = async () => assert.doesNotMatch(await status(), /没有对应的预览源码位置|当前源码对象未显示为独立图元|预览正在接入当前源码|预览与正式文档的源码字节不同/);
const ready = async () => page.waitForFunction(() => {
  const button = document.querySelector('.canvas-toolbar [aria-label="Apply layout"]'); return button && !button.disabled;
}, { timeout: 60000 });
const selectCase = async id => {
  const menu = page.locator('.studio .workspace-menu');
  if (await menu.getAttribute('open') === null) await menu.locator('summary').click();
  await page.getByRole('button', { name: '示例与模块库', exact: true }).click();
  await frame.locator('.library').waitFor({ state: 'visible' });
  await frame.locator('#search').fill(''); await frame.locator('#collection').selectOption('all');
  await frame.locator(`button[data-case-id="${id}"]`).click();
  await waitState(state => state.document?.caseId === id && !state.busy);
  await frame.locator('.library .studio-drawer-close').click();
  await ready();
  assert.equal(await frame.locator('.library').isVisible(), false);
  return snapshot();
};
const selectNode = async id => {
  await command('select-tool'); await command('fit');
  await frame.locator(`[data-node-id="${id}"] .node-hit, [data-node-id="${id}"] .frame-hit`).first().click({ position: { x: 5, y: 5 } });
  await waitState(state => state.selectedNodes.length === 1 && state.selectedNodes[0] === id);
  await page.getByLabel('显示名称', { exact: true }).waitFor();
};

await fs.mkdir(evidence, { recursive: true });
try {
  await page.goto(base + '/');
  await page.waitForFunction(() => window.sourceSmokeMessages.some(message => message.type === 'archcanvas:preview:ready'));
  frame = page.frame({ url: /preview\/yworks_edge_router_lab\/index.html/ });
  assert.ok(frame); await ready();
  const sourceIndex = await (await context.request.get(base + '/preview/data/catalog-sources.json')).json();
  assert.equal(await frame.locator('.library').isVisible(), false);
  mark('catalog remains hidden behind the Studio model menu');

  const cases = [
    { id: '771109e666204fb7', name: 'AlexNet' },
    { id: '25a45edcfd7a974c', name: 'ActNorm' },
    { id: 'f43269ed2ea4e6aa', name: 'MobileNetV3' },
    { id: 'pytorch-original', name: 'PyTorch original' },
    { id: 'ff136a438eea65f7', name: 'DCGAN', unsupported: true },
  ];
  for (const item of cases) {
    const state = await selectCase(item.id), source = (await command('request-source')).source, descriptor = sourceIndex.cases[item.id];
    assert.equal(source.caseId, item.id); assert.equal(source.schema, 'archcanvas-preview-source/1');
    assert.match(source.entry, /^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*$/);
    const files = Object.entries(source.files);
    assert.ok(files.length > 0);
    for (const [filename, text] of files) {
      assert.match(filename, /^(?:[A-Za-z_]\w*\/)*[A-Za-z_]\w*\.py$/);
      assert.equal(sha(text), descriptor.files.find(file => file.path === filename)?.sha256);
      assert.ok(text.includes('import ') || text.includes('class '));
    }
    const evidenceEntries = Object.values(source.evidence ?? {});
    if (descriptor.evidence) assert.ok(evidenceEntries.length > 0);
    for (const entry of evidenceEntries) { assert.ok(Object.hasOwn(source.files, entry.file), entry.file); assert.ok(entry.line > 0); }
    const result = { ...item, entry: source.entry, files: files.map(([filename, text]) => ({ path: filename, sha256: sha(text), bytes: Buffer.byteLength(text) })), evidence: evidenceEntries.length,
      ...(evidenceEntries.length ? {} : { evidenceLimitation: 'Catalog supplies no standalone evidence file for this source; complete source bytes remain available.' }) };
    caseResults.push(result);
    await page.getByRole('button', { name: '查看源码证据', exact: true }).click();
    await page.locator('.source-drawer pre').first().waitFor();
    assert.ok((await page.locator('.source-content').innerText()).includes(files[0][0]));
    assert.ok((await page.locator('.source-content').innerText()).includes('import'));
    await page.getByRole('button', { name: '关闭源码', exact: true }).click();
    mark(item.name + ' loads canonical source paths, exact source SHA256, matching evidence and source text', result);

    const node = state.document.graph.nodes.find(node => !node.junction && !node.expanded && node.w > 40) ?? state.document.graph.nodes.find(node => !node.junction);
    assert.ok(node);
    const baseline = authoritySha(state), label = 'Source QA ' + item.name;
    await selectNode(node.id);
    const beforeAlias = await snapshot();
    await page.getByLabel('显示名称', { exact: true }).fill(label); await page.getByLabel('显示名称', { exact: true }).press('Enter');
    const aliasState = await waitState(state => presentation(state)?.nodes?.[node.id]?.alias === label);
    assert.equal(aliasState.undo, beforeAlias.undo + 1); assert.equal(authoritySha(aliasState), baseline);
    await page.getByRole('button', { name: '撤销 Ctrl+Z', exact: true }).click();
    await waitState(state => presentation(state)?.nodes?.[node.id]?.alias !== label);
    await page.getByRole('button', { name: '重做 Ctrl+Shift+Z', exact: true }).click();
    await waitState(state => presentation(state)?.nodes?.[node.id]?.alias === label);
    await selectNode(node.id);
    await page.getByLabel('自定义填充颜色', { exact: true }).fill('#eeddaa');
    await waitState(state => presentation(state)?.nodes?.[node.id]?.fill === '#eeddaa');
    await page.getByRole('button', { name: '图例', exact: true }).click();
    await page.getByRole('button', { name: '添加图例条目', exact: true }).click();
    const legendState = await waitState(state => presentation(state)?.legend?.some(entry => entry.label === '自定义图例'));
    assert.equal(authoritySha(legendState), baseline); await assertNoMappingError();
    await page.getByRole('button', { name: '对象', exact: true }).click();
    mark(item.name + ' retained object and legend panels edit the original preview with shared undo/redo');

    if (item.name === 'AlexNet') {
      await page.getByRole('button', { name: '保存', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('.save-state')?.textContent === '已保存');
      assert.equal((await snapshot()).document.caseId, item.id);
      await page.getByRole('button', { name: '导出', exact: true }).click();
      await page.getByRole('button', { name: /^编辑 JSON/ }).click();
      const downloaded = page.waitForEvent('download');
      await page.getByRole('button', { name: '下载编辑 JSON', exact: true }).click();
      const target = path.join(evidence, 'alexnet-canvas.json'); await (await downloaded).saveAs(target);
      const saved = JSON.parse(await fs.readFile(target, 'utf8'));
      assert.equal(saved.caseId, item.id); assert.equal(sha(JSON.stringify(saved.graph.recursive.authority)), baseline);
      assert.equal((saved.graph.recursive.state.studioPresentation ?? saved.graph.studioPresentation).nodes[node.id].alias, label);
      await page.getByRole('button', { name: '关闭导出', exact: true }).click();
      await command('load', { bundle: saved }); await ready();
      assert.equal((await snapshot()).document.caseId, item.id);
      mark('save and downloaded editing JSON preserve catalog identity, exact source authority and preview style');
      await page.getByRole('button', { name: '编辑', exact: true }).click();
      await page.locator('.authoring-header').waitFor({ state: 'visible', timeout: 60000 });
      assert.equal(await page.locator('.authoring-header').getByRole('button', { name: '编辑', exact: true }).getAttribute('aria-pressed'), 'true');
      assert.ok(await page.locator('[data-draft-node]').count() > 0);
      mark('supported AlexNet enters the existing formal source authoring workspace');
      await page.locator('.authoring-header .workspace-menu > summary').click();
      await page.getByRole('button', { name: '查看原始视图', exact: true }).click();
      await ready();
      assert.equal((await snapshot()).document.caseId, item.id);
    }
    if (item.unsupported) {
      await page.getByRole('button', { name: '编辑', exact: true }).click();
      await page.waitForFunction(() => /超出|不能进入|无法进入|无法同步|不支持/.test(document.querySelector('.statusbar')?.textContent ?? ''), { timeout: 60000 });
      assert.equal(await page.locator('.authoring-header:visible').count(), 0);
      assert.equal((await snapshot()).document.caseId, item.id);
      await page.locator('.source-drawer pre').first().waitFor();
      assert.match(await page.locator('.source-content').innerText(), /只读/);
      mark('unsupported DCGAN authoring keeps the original preview and readable source with an explicit contract limitation');
      await page.getByRole('button', { name: '关闭源码', exact: true }).click();
    }
    await page.screenshot({ path: path.join(evidence, item.id + '.png'), fullPage: true });
  }
  assert.deepEqual(browserErrors, []);
  const report = { ok: true, checks, browserErrors, assets: [...new Set(assets)], cases: caseResults };
  await fs.writeFile(path.join(evidence, 'browser-sources.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ ok: true, checks: checks.length, cases: caseResults.length }));
} catch (error) {
  await page.screenshot({ path: path.join(evidence, 'failure.png'), fullPage: true }).catch(() => {});
  await fs.writeFile(path.join(evidence, 'failure.json'), JSON.stringify({ ok: false, checks, browserErrors, assets, error: String(error.stack ?? error), lastState }, null, 2) + '\n');
  throw error;
} finally { await browser.close(); }
