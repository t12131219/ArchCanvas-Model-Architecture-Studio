import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { gzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Real controls in disposable contexts; model code is never executed.
const args = process.argv.slice(2), option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const phase = option('--phase', 'final'), base = option('--base', 'http://127.0.0.1:8891').replace(/\/$/, '');
const evidence = path.resolve(option('--output-dir', path.join(root, 'docs/evidence/preview-generalization-20261014', phase)));
const { chromium } = await import(pathToFileURL(option('--playwright', '/home/fzg/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs')).href);
const browser = await chromium.launch({ headless: true, executablePath: option('--chromium', '/home/fzg/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome'), args: ['--no-sandbox'] });
const canonical = value => JSON.stringify(value, (_key, item) => item && typeof item === 'object' && !Array.isArray(item) ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item);
const sha = value => createHash('sha256').update(typeof value === 'string' || Buffer.isBuffer(value) ? value : canonical(value)).digest('hex');
const visual = state => sha({ nodes: state.document.graph.nodes, edges: state.document.graph.edges, canvas: state.document.graph.canvas, open: state.document.graph.recursive.state.open });
const geometry = state => sha({ nodes: state.document.graph.nodes.map(node => ({ id: node.id, x: node.x, y: node.y, w: node.w, h: node.h, expanded: node.expanded })).sort((a, b) => a.id.localeCompare(b.id)),
  edges: state.document.graph.edges.map(edge => ({ id: edge.id, source: edge.source, target: edge.target, points: edge.route.map(point => ({ x: point.x, y: point.y })) })).sort((a, b) => a.id.localeCompare(b.id)) });
const cases = [
  { id: '654be40c8d6a5cc2', name: 'UNet', prefer: 'unet_enc1', method: 'plus' },
  { id: '2ae45b28d78ba027', name: 'DenseNet', prefer: 'dense_b1', method: 'doubleclick' },
  { id: 'd6dd6f156d262b3c', name: 'Autoformer', prefer: 'af_encoder', method: 'left' },
  { id: '0342f4170c15ba8e', name: 'VAE', prefer: 'vae.forward', method: 'right' },
  { id: 'f7f504118e6dfb95', name: 'Flow Sequential', prefer: 'flow_sequential.body', method: 'plus' },
  { id: '0a438c321af18e8a', name: 'Graph Attention', prefer: 'graph_attention.module', method: 'doubleclick' },
  { id: '3ea7a49a16ba458d', name: 'ResNet', prefer: 'resnet.stage1', method: 'left' },
  { id: '5123a5f6f70c91aa', name: 'TCN Block', prefer: 'tcn.body', method: 'right' },
  { id: 'f43269ed2ea4e6aa', name: 'MobileNetV3', prefer: 'm3.stage3', method: 'plus' },
  { id: '5af4f8d40e3ac7b0', name: 'WaveNet Block', prefer: 'wave.body', method: 'doubleclick' },
];
const results = [], assetUrls = new Set(), errors = [], compressed = [];
const casesOnly = args.includes('--cases');
await fs.mkdir(evidence, { recursive: true });
async function artifact(name, value) {
  const bytes = Buffer.from(typeof value === 'string' ? value : JSON.stringify(value, null, 2) + '\n'), target = path.join(evidence, name);
  if (bytes.length > 1024 * 1024) {
    const zipped = gzipSync(bytes, { mtime: 0 }); await fs.writeFile(target + '.gz', zipped);
    compressed.push({ original: name, gzip: name + '.gz', bytes: bytes.length, gzipBytes: zipped.length, originalSha256: sha(bytes), gzipSha256: sha(zipped) });
  } else await fs.writeFile(target, bytes);
}
async function setup(standalone = false) {
  const context = await browser.newContext({ viewport: { width: 1640, height: 1080 } });
  await context.addInitScript(() => {
    window.genericMessages = []; window.genericMeta = null;
    window.addEventListener('message', event => {
      if (event.origin !== location.origin || typeof event.data?.type !== 'string' || !event.data.type.startsWith('archcanvas:preview:')) return;
      const value = event.data; window.genericMessages.push({ type: value.type, command: value.command, message: value.message });
      if (value.document?.graph) window.genericMeta = { busy: value.busy, undo: value.undo, redo: value.redo, caseId: value.document.caseId,
        expanded: value.document.graph.nodes.filter(node => node.expanded).map(node => node.id) };
    });
    window.genericCommand = (name, payload = {}) => new Promise((resolve, reject) => {
      const frame = document.querySelector('iframe'), requestId = crypto.randomUUID();
      const timeout = setTimeout(() => { window.removeEventListener('message', receive); reject(Error(name + ' timed out')); }, 180000);
      function receive(event) {
        if (event.source !== frame?.contentWindow || event.origin !== location.origin || event.data?.requestId !== requestId) return;
        clearTimeout(timeout); window.removeEventListener('message', receive);
        event.data.type.endsWith(':error') ? reject(Error(event.data.message)) : resolve(event.data);
      }
      window.addEventListener('message', receive);
      frame.contentWindow.postMessage({ type: 'archcanvas:preview:' + name, requestId, ...payload }, location.origin);
    });
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message)); page.on('response', response => { if (/\/assets\/[^/]+\.js$/.test(response.url())) assetUrls.add(response.url()); });
  if (standalone) {
    await page.route(base + '/generalization-standalone.html', route => route.fulfill({ contentType: 'text/html', body: '<!doctype html><iframe style="width:100vw;height:100vh;border:0" src="/preview/yworks_edge_router_lab/index.html"></iframe>' }));
    await page.goto(base + '/generalization-standalone.html');
  } else await page.goto(base + '/');
  await page.waitForFunction(() => window.genericMessages.some(message => message.type === 'archcanvas:preview:ready'), null, { timeout: 180000 });
  const frame = page.frame({ url: /preview\/yworks_edge_router_lab\/index.html/ }); assert.ok(frame);
  const command = (name, payload) => page.evaluate(({ name, payload }) => window.genericCommand(name, payload), { name, payload });
  const snapshot = () => command('snapshot');
  const ready = async () => {
    await page.waitForFunction(() => !window.genericMeta?.busy, null, { timeout: 180000 });
    if (!standalone) await page.waitForFunction(() => { const button = document.querySelector('.canvas-toolbar [aria-label="Apply layout"]'); return button && !button.disabled; }, null, { timeout: 180000 });
  };
  await ready();
  return { context, page, frame, command, snapshot, ready };
}
async function validate(env, state, authority) {
  assert.equal(sha(state.document.graph.recursive.authority), authority);
  const check = await env.frame.evaluate(graph => window.SummaryEngine.validateView(graph), state.document.graph);
  assert.equal(check.source.ok, true); assert.equal(check.layout.ok, true, check.layout.violations.join('; '));
  assert.deepEqual(check.edges.filter(([, value]) => !value.ok), []);
  if (phase !== 'baseline') {
    assert.deepEqual(check.routing.contacts, [], 'container clearance contacts');
    assert.deepEqual(check.routing.constrained, [], 'degraded container lane');
  }
  return { contacts: check.routing.contacts, constrained: check.routing.constrained, nodes: state.document.graph.nodes.length, edges: state.document.graph.edges.length };
}
async function selectCase(env, id) {
  const { page, frame } = env, menu = page.locator('.studio .workspace-menu');
  if (await menu.getAttribute('open') === null) await menu.locator('summary').click();
  await page.getByRole('button', { name: '示例与模块库', exact: true }).click();
  await frame.locator('.library').waitFor({ state: 'visible' });
  await frame.locator('#search').fill(''); await frame.locator('#collection').selectOption('all');
  await frame.locator(`button[data-case-id="${id}"]`).click({ timeout: 180000 });
  await page.waitForFunction(id => window.genericMeta?.caseId === id && !window.genericMeta.busy, id, { timeout: 180000 });
  await frame.locator('.library .studio-drawer-close').click();
  if (await menu.getAttribute('open') !== null) await menu.locator('summary').click();
  await env.ready(); return env.snapshot();
}
async function selectNode(env, id) {
  await env.command('select-tool'); await env.command('fit');
  const box = await env.frame.locator(`[data-node-id="${id}"] .node-hit, [data-node-id="${id}"] .frame-hit`).first().boundingBox(); assert.ok(box);
  // Expanded frame hit rectangles intentionally receive only stroke hits.
  // Actual pointer events on their own filled source glyph bubble to the same
  // node handler; targeting the transparent hit rect with Locator.click would
  // incorrectly demand that it be the browser's hit-test target.
  await env.page.mouse.click(box.x + 4, box.y + 4);
  const state = await env.snapshot(); assert.deepEqual(state.selectedNodes, [id]); return state;
}
async function toggle(env, id, expanded, method, result) {
  const before = await env.snapshot(), n = before.document.graph.nodes.find(node => node.id === id); assert.ok(n);
  const messageOffset = await env.page.evaluate(() => window.genericMessages.length);
  const childCount = before.document.graph.recursive.authority.detail.nodes.filter(node => node.parent === id).length;
  assert.ok(childCount > 0); assert.ok(!before.document.graph.recursive.authority.mandatory.includes(id), id + ' is mandatory, not toggleable');
  await env.command('fit'); const start = Date.now();
  const group = env.frame.locator(`[data-node-id="${id}"]`);
  if (method === 'plus') await group.locator('.expansion-control').click({ timeout: 180000 });
  else if (method === 'doubleclick') {
    await env.frame.evaluate(() => {
      window.genericPointerEvents = [];
      for (const type of ['pointerdown', 'pointerup', 'mousedown', 'mouseup', 'click', 'dblclick']) document.addEventListener(type, event => {
        window.genericPointerEvents.push({ type, tag: event.target.tagName, id: event.target.id, node: event.target.closest('[data-node-id]')?.getAttribute('data-node-id'),
          clientX: event.clientX, clientY: event.clientY, detail: event.detail, defaultPrevented: event.defaultPrevented, buttons: event.buttons, graphPhase: document.querySelector('#graph')?.getAttribute('data-interaction-phase') });
      }, { capture: true });
    });
    const box = await group.locator('.node-hit, .frame-hit').first().boundingBox(); assert.ok(box);
    await env.page.mouse.dblclick(box.x + box.width / 2, box.y + Math.min(box.height / 2, 16), { delay: 100 });
    const events = await env.frame.evaluate(() => window.genericPointerEvents);
    await artifact('events-' + id.replace(/[^\w.-]/g, '_') + '.json', events); console.log('DOUBLECLICK ' + JSON.stringify(events));
  }
  else if (method === 'left') {
    const row = env.page.locator('.tree-row').filter({ has: env.page.getByRole('button', { name: n.label || n.id, exact: true }) });
    assert.equal(await row.count(), 1, 'left hierarchy must expose an unambiguous raw container');
    await row.locator('.tree-toggle').click();
  } else {
    await selectNode(env, id);
    await env.page.getByRole('button', { name: expanded ? '原位展开' : '原位收起', exact: true }).click({ timeout: 180000 });
  }
  await env.page.waitForFunction(({ id, expanded, undo, offset }) => window.genericMeta && !window.genericMeta.busy &&
    ((window.genericMeta.undo === undo + 1 && window.genericMeta.expanded.includes(id) === expanded) || window.genericMessages.slice(offset).some(message => message.type.endsWith(':error'))),
    { id, expanded, undo: before.undo, offset: messageOffset }, { timeout: 45000 });
  const failed = await env.page.evaluate(offset => window.genericMessages.slice(offset).find(message => message.type.endsWith(':error')), messageOffset);
  if (failed) throw Error(failed.message);
  await env.ready(); const state = await env.snapshot();
  result.actions.push({ action: expanded ? 'expand' : 'collapse', id, method, ms: Date.now() - start, childCount, ...(await validate(env, state, result.authority)) });
  return state;
}
async function drag(env, id, dx, dy, result) {
  await env.command('fit'); const before = await selectNode(env, id), n = before.document.graph.nodes.find(node => node.id === id);
  const box = await env.frame.locator(`[data-node-id="${id}"] .node-hit, [data-node-id="${id}"] .frame-hit`).first().boundingBox(); assert.ok(box);
  await env.page.mouse.move(box.x + 4, box.y + 4); await env.page.mouse.down(); await env.page.mouse.move(box.x + 4 + dx, box.y + 4 + dy, { steps: 5 }); await env.page.mouse.up();
  await env.ready(); const after = await env.snapshot(), moved = after.document.graph.nodes.find(node => node.id === id);
  const changed = Math.abs(moved.x - n.x) > 1e-5 || Math.abs(moved.y - n.y) > 1e-5;
  const check = await validate(env, after, result.authority);
  if (changed) {
    assert.equal(after.undo, before.undo + 1);
    for (const child of before.document.graph.nodes.filter(node => node.parent === id)) {
      const next = after.document.graph.nodes.find(node => node.id === child.id); assert.ok(next);
      assert.ok(Math.abs(next.x - child.x - moved.x + n.x) < 1e-5); assert.ok(Math.abs(next.y - child.y - moved.y + n.y) < 1e-5);
    }
    await env.command('undo'); assert.equal(visual(await env.snapshot()), visual(before));
    await env.command('redo'); assert.equal(visual(await env.snapshot()), visual(after));
    await env.command('undo');
  } else assert.equal(visual(after), visual(before));
  result.actions.push({ action: n.expanded ? 'drag-container' : 'drag-node', id, dx, dy, changed, ...check });
}
async function atomicJsonRestore(env, saved, result, label) {
  console.log('RESTORE ' + label + ' begin');
  const before = await env.snapshot(), oldSource = before.document.sourceAvailable ? (await env.command('request-source')).source : null;
  await env.frame.evaluate(() => {
    const original = Worker.prototype.postMessage; window.genericOriginalPost = original;
    window.genericHoldNext = true; window.genericHeld = null;
    Worker.prototype.postMessage = function(message, ...rest) {
      if (['frontier', 'validate'].includes(message?.task) && window.genericHoldNext) {
        window.genericHoldNext = false; window.genericHeld = { worker: this, message }; return;
      }
      return original.call(this, message, ...rest);
    };
  });
  await env.page.evaluate(bundle => {
    window.genericRestoreResult = null;
    window.genericCommand('load', { bundle }).then(() => { window.genericRestoreResult = { ok: true }; }, error => { window.genericRestoreResult = { ok: false, error: error.message }; });
  }, saved);
  await env.frame.waitForFunction(() => !!window.genericHeld, null, { timeout: 180000 });
  console.log('RESTORE ' + label + ' held');
  const held = await env.snapshot(); assert.equal(held.busy, true); assert.equal(sha(held.document.graph), sha(before.document.graph));
  assert.equal(held.document.caseId, before.document.caseId); assert.equal(held.undo, before.undo); assert.equal(held.redo, before.redo);
  if (oldSource) assert.equal(sha((await env.command('request-source')).source), sha(oldSource));
  await assert.rejects(env.command('visual', { operations: [{ type: 'alias', id: before.document.graph.nodes[0].id, label: 'Must reject during restore' }] }), /完成|操作/);
  await env.frame.evaluate(() => {
    const held = window.genericHeld;
    held.worker.dispatchEvent(new MessageEvent('message', { data: { requestId: held.message.requestId, ok: false, error: 'Injected editing JSON restore rejection' } }));
    window.genericHeld = null; Worker.prototype.postMessage = window.genericOriginalPost;
  });
  await env.page.waitForFunction(() => window.genericRestoreResult !== null, null, { timeout: 180000 });
  assert.equal((await env.page.evaluate(() => window.genericRestoreResult)).ok, false);
  await env.ready(); const rejected = await env.snapshot(); assert.equal(sha(rejected.document.graph), sha(before.document.graph));
  console.log('RESTORE ' + label + ' rejection retained old view');
  assert.equal(rejected.document.caseId, before.document.caseId); assert.equal(rejected.undo, before.undo); assert.equal(rejected.redo, before.redo); assert.equal(rejected.dirty, before.dirty);
  await env.page.evaluate(() => {
    window.genericRestoreTransitions = [];
    window.genericRestoreListener = event => {
      if (event.origin !== location.origin || !event.data?.document?.graph) return;
      const document = event.data.document, graph = document.graph;
      window.genericRestoreTransitions.push({ caseId: document.caseId, graph: JSON.stringify({ nodes: graph.nodes.map(node => ({ id: node.id, x: node.x, y: node.y, w: node.w, h: node.h, expanded: node.expanded })), edges: graph.edges.map(edge => ({ id: edge.id, route: edge.route })) }) });
    };
    window.addEventListener('message', window.genericRestoreListener);
  });
  await env.command('load', { bundle: saved }); await env.ready(); const restored = await env.snapshot();
  console.log('RESTORE ' + label + ' retry settled');
  assert.equal(restored.document.caseId, saved.caseId || saved.case); assert.equal(geometry(restored), geometry({ document: saved }));
  const transitions = await env.page.evaluate(() => { window.removeEventListener('message', window.genericRestoreListener); return window.genericRestoreTransitions; });
  const expected = JSON.stringify({ nodes: saved.graph.nodes.map(node => ({ id: node.id, x: node.x, y: node.y, w: node.w, h: node.h, expanded: node.expanded })), edges: saved.graph.edges.map(edge => ({ id: edge.id, route: edge.route })) });
  assert.ok(transitions.some(value => value.caseId === restored.document.caseId));
  for (const transition of transitions.filter(value => value.caseId === restored.document.caseId)) assert.equal(transition.graph, expected, 'JSON restore must publish edited frontier atomically');
  if (saved.adapter) assert.equal(sha((await env.command('request-source')).source.files), sha(Object.fromEntries(saved.adapter.files.map(file => [file.path, file.text]))));
  result.actions.push({ action: label + ': held Worker retains old graph/source, rejection retains history, retry restores edited geometry atomically', transitions: transitions.length });
  return restored;
}
const inventoryEnv = await setup(), catalog = await (await inventoryEnv.context.request.get(base + '/preview/data/catalog.json')).json();
const inventory = [];
for (const item of cases) {
  const descriptor = catalog.cases.find(value => value.id === item.id); assert.ok(descriptor && !descriptor.historical);
  const detail = descriptor.views.find(view => view.key === 'detailed') ?? descriptor.views.at(-1);
  const graph = await (await inventoryEnv.context.request.get(base + '/preview/' + detail.json)).json();
  inventory.push({ ...item, collection: descriptor.collection, nodes: graph.nodes.length, edges: graph.edges.length,
    containers: graph.nodes.map(node => ({ id: node.id, parent: node.parent, directChildren: graph.nodes.filter(value => value.parent === node.id).length })).filter(node => node.directChildren > 0) });
}
await artifact('inventory.json', inventory); await inventoryEnv.context.close();
if (args.includes('--case-load-transactions')) {
  const result = { name: 'Atomic initial case load', phase, ok: false, actions: [] }; let env;
  try {
    env = await setup(); await env.command('save'); const before = await env.snapshot();
    await env.frame.evaluate(() => {
      const original = Worker.prototype.postMessage; window.genericOriginalPost = original;
      window.genericHoldNext = true; window.genericHeld = null;
      Worker.prototype.postMessage = function(message, ...rest) {
        if (message?.task === 'frontier' && window.genericHoldNext) {
          window.genericHoldNext = false; window.genericHeld = { worker: this, message }; return;
        }
        return original.call(this, message, ...rest);
      };
    });
    const menu = env.page.locator('.studio .workspace-menu'); await menu.locator('summary').click();
    await env.page.getByRole('button', { name: '示例与模块库', exact: true }).click();
    await env.frame.locator('button[data-case-id="654be40c8d6a5cc2"]').click();
    await env.frame.waitForFunction(() => !!window.genericHeld, null, { timeout: 180000 });
    const during = await env.snapshot(); assert.equal(during.busy, true); assert.equal(during.document.caseId, before.document.caseId);
    assert.equal(sha(during.document.graph), sha(before.document.graph)); assert.equal(during.undo, before.undo); assert.equal(during.redo, before.redo);
    assert.equal((await env.command('request-source')).source.caseId, before.document.caseId);
    const id = before.document.graph.nodes.find(node => !node.junction).id;
    await assert.rejects(env.command('visual', { operations: [{ type: 'alias', id, label: 'Must not mutate while loading' }] }), /完成|操作/);
    await assert.rejects(env.command('undo'), /完成|操作/);
    await env.frame.evaluate(() => {
      const held = window.genericHeld;
      held.worker.dispatchEvent(new MessageEvent('message', { data: { requestId: held.message.requestId, ok: false, error: 'Injected case load rejection' } }));
      window.genericHeld = null; Worker.prototype.postMessage = window.genericOriginalPost;
    });
    await env.ready(); const rejected = await env.snapshot();
    assert.equal(rejected.document.caseId, before.document.caseId); assert.equal(sha(rejected.document.graph), sha(before.document.graph));
    assert.equal(rejected.undo, before.undo); assert.equal(rejected.redo, before.redo); assert.equal(rejected.dirty, before.dirty);
    await env.frame.locator('.library .studio-drawer-close').click();
    if (await menu.getAttribute('open') !== null) await menu.locator('summary').click();
    const retry = await selectCase(env, '654be40c8d6a5cc2'); assert.equal(retry.document.caseId, '654be40c8d6a5cc2');
    await validate(env, retry, sha(retry.document.graph.recursive.authority));
    result.ok = true; result.actions.push({ action: 'busy old graph/source identity retained, edits reject, failed newcase restores history, retry succeeds' });
    console.log('PASS atomic initial case load');
  } catch (error) {
    result.error = error.stack; console.log('FAIL atomic load: ' + error.message);
    if (env) await artifact('atomic-load-failure.json', (await env.snapshot()).document);
  } finally { if (env) await env.context.close(); }
  results.push(result); await artifact('report.json', { phase, base, results, errors, assets: [...assetUrls], compressed });
}
for (const item of cases.filter(item => !args.includes('--fixtures-only') && (!option('--cases', '') || option('--cases', '').split(',').includes(item.name)))) {
  let env, lastState;
  const result = { ...item, phase, ok: false, actions: [] }; console.log('CASE ' + item.name);
  try {
    env = await setup(); lastState = await selectCase(env, item.id); result.authority = sha(lastState.document.graph.recursive.authority);
    result.initial = await validate(env, lastState, result.authority);
    const g = lastState.document.graph, children = id => g.recursive.authority.detail.nodes.filter(node => node.parent === id);
    let target = g.nodes.find(node => node.id === item.prefer && children(node.id).length && !g.recursive.authority.mandatory.includes(node.id));
    target ??= g.nodes.find(node => children(node.id).length && !node.expanded && !g.recursive.authority.mandatory.includes(node.id)); assert.ok(target, 'case must expose a real collapsed container');
    if (target.expanded) lastState = await toggle(env, target.id, false, 'plus', result);
    lastState = await toggle(env, target.id, true, item.method, result);
    const deeper = lastState.document.graph.nodes.find(node => node.parent === target.id && !node.expanded && children(node.id).length);
    if (deeper) lastState = await toggle(env, deeper.id, true, 'plus', result);
    const opened = lastState.document.graph.recursive.state.open.filter(id => id === target.id || id === deeper?.id).sort();
    const openedGeometry = geometry(lastState);
    lastState = await toggle(env, target.id, false, 'plus', result);
    lastState = await toggle(env, target.id, true, 'plus', result);
    assert.deepEqual(lastState.document.graph.recursive.state.open.filter(id => id === target.id || id === deeper?.id).sort(), opened);
    assert.equal(geometry(lastState), openedGeometry, 'reopening restores exact visible node and route geometry');
    if (deeper) assert.equal(lastState.document.graph.nodes.find(node => node.id === deeper.id)?.expanded, true);
    const leaf = lastState.document.graph.nodes.find(node => node.parent === target.id && !node.expanded && !node.junction);
    if (leaf) await drag(env, leaf.id, 5, 0, result);
    const outer = lastState.document.graph.nodes.find(node => node.expanded && !node.parent && lastState.document.graph.nodes.some(child => child.parent === node.id));
    await drag(env, outer?.id ?? target.id, 5, 0, result);
    const beforeLayout = await env.snapshot();
    await env.page.getByRole('button', { name: 'Apply layout', exact: true }).click();
    await env.page.waitForFunction(undo => !window.genericMeta?.busy && window.genericMeta?.undo === undo + 1, beforeLayout.undo, { timeout: 180000 });
    await env.ready(); const laidOut = await env.snapshot(); await validate(env, laidOut, result.authority);
    await env.page.getByRole('button', { name: '撤销 Ctrl+Z', exact: true }).click(); assert.equal(visual(await env.snapshot()), visual(beforeLayout));
    await env.page.getByRole('button', { name: '重做 Ctrl+Shift+Z', exact: true }).click(); assert.equal(visual(await env.snapshot()), visual(laidOut));
    result.actions.push({ action: 'Apply layout + toolbar undo/redo' });
    lastState = await env.snapshot(); result.final = await validate(env, lastState, result.authority);
    await env.command('fit'); await env.page.screenshot({ path: path.join(evidence, item.id + '.png'), fullPage: true });
    await artifact(item.id + '.json', lastState.document); result.ok = true; console.log('PASS ' + item.name);
  } catch (error) {
    result.error = error.stack; console.log('FAIL ' + item.name + ': ' + error.message);
    if (env) {
      result.ui = await env.frame.evaluate(() => ({ toast: document.querySelector('#toast')?.textContent, dirty: document.querySelector('#dirtyBadge')?.textContent, pointerEvents: window.genericPointerEvents,
        dblclickFallback: [...document.scripts].some(script => script.src.endsWith('/app.js')) }));
      await env.page.screenshot({ path: path.join(evidence, item.id + '-failure.png'), fullPage: true }).catch(() => {});
      lastState = await env.snapshot().catch(() => lastState);
      if (lastState?.document) await artifact(item.id + '-failure.json', lastState.document);
    }
  } finally { if (env) await env.context.close(); }
  results.push(result); await artifact('report.json', { phase, base, results, errors, assets: [...assetUrls], compressed });
}
if (!casesOnly) {
  let env;
  if (!args.includes('--saved-only')) {
  const result = { name: 'Imported shared-value tuple model', phase, ok: false, actions: [] };
  try {
    env = await setup();
    const source = 'from torch import nn\n\nclass Branch(nn.Module):\n    def __init__(self):\n        super().__init__()\n        self.linear = nn.Linear(4, 4)\n        self.relu = nn.ReLU()\n    def forward(self, x):\n        return self.relu(self.linear(x))\n\nclass TupleBranches(nn.Module):\n    def __init__(self):\n        super().__init__()\n        self.shared = nn.Linear(4, 4)\n        self.left = Branch()\n        self.right = Branch()\n    def forward(self, x):\n        shared = self.shared(x)\n        left = self.left(shared)\n        right = self.right(shared)\n        total = left + right\n        return left, right, total\n';
    await artifact('tuple_branches.py', source);
    await env.page.locator('.import-button').click();
    await env.page.getByLabel('模型类名', { exact: true }).fill('TupleBranches');
    await env.page.getByLabel('文件名', { exact: true }).fill('tuple_branches.py');
    await env.page.getByLabel('Python 源码', { exact: true }).fill(source);
    await env.page.getByRole('button', { name: '静态分析并打开画布', exact: true }).click();
    await env.page.getByRole('dialog', { name: '从 Python 源码开始', exact: true }).waitFor({ state: 'detached', timeout: 180000 });
    await env.ready(); let state = await env.snapshot(); result.authority = sha(state.document.graph.recursive.authority);
    assert.match(state.document.adapter.entry, /:TupleBranches$/);
    const all = state.document.graph.recursive.authority.detail.nodes;
    const branches = state.document.graph.nodes.filter(node => all.some(child => child.parent === node.id) && !node.expanded && !state.document.graph.recursive.authority.mandatory.includes(node.id));
    assert.ok(branches.length >= 2, 'source fixture has independent nested branches');
    state = await toggle(env, branches[0].id, true, 'doubleclick', result);
    state = await toggle(env, branches[1].id, true, 'plus', result);
    state = await toggle(env, branches[0].id, false, 'plus', result);
    state = await toggle(env, branches[0].id, true, 'plus', result);
    const leaf = state.document.graph.nodes.find(node => node.parent === branches[0].id && !node.expanded && !node.junction);
    assert.ok(leaf);
    await drag(env, leaf.id, 6, 0, result); await drag(env, branches[0].id, 6, 0, result);
    await env.page.getByRole('button', { name: '导出', exact: true }).click();
    await env.page.getByRole('button', { name: /^编辑 JSON/ }).click();
    const jsonDownload = env.page.waitForEvent('download'); await env.page.getByRole('button', { name: '下载编辑 JSON', exact: true }).click();
    const editingPath = path.join(evidence, 'tuple-edited-canvas.json'); await (await jsonDownload).saveAs(editingPath);
    const editing = JSON.parse(await fs.readFile(editingPath, 'utf8'));
    assert.equal(geometry({ document: editing }), geometry(await env.snapshot()));
    await env.page.getByRole('button', { name: '关闭导出', exact: true }).click();
    await selectCase(env, '654be40c8d6a5cc2');
    await atomicJsonRestore(env, editing, result, 'imported edited JSON');
    await env.page.locator('.import-button').click(); await env.page.locator('.import-modal input[type="file"]').setInputFiles(editingPath);
    await env.page.getByRole('dialog', { name: '从 Python 源码开始', exact: true }).waitFor({ state: 'detached', timeout: 180000 });
    await env.ready(); assert.equal(geometry(await env.snapshot()), geometry({ document: editing }));
    result.actions.push({ action: 'native editing JSON download and import restore source-bound expanded view' });
    const beforeInvalid = await env.snapshot();
    await assert.rejects(env.command('visual', { operations: [{ type: 'nodeLayout', id: leaf.id, position: { x: -10000 }, exact: true }] }), /位置|边界|容器|约束/);
    const invalidRejected = await env.snapshot(); assert.equal(visual(invalidRejected), visual(beforeInvalid));
    assert.equal(invalidRejected.undo, beforeInvalid.undo); assert.equal(invalidRejected.redo, beforeInvalid.redo);
    result.actions.push({ action: 'out-of-container visual move rejects atomically' });
    // A real single-step drag directly onto a same-parent sibling must revert
    // rather than commit a partial unsafe route or consume an undo step.
    const g = beforeInvalid.document.graph, pair = g.nodes.find(node => node.parent === leaf.parent && node.id !== leaf.id && !node.junction);
    assert.ok(pair);
    await env.command('fit'); const selected = await selectNode(env, leaf.id);
    await artifact('tuple-drag-before.json', selected);
    const boxes = await Promise.all([leaf.id, pair.id].map(id => env.frame.locator(`[data-node-id="${id}"] .node-hit, [data-node-id="${id}"] .frame-hit`).first().boundingBox()));
    assert.ok(boxes.every(Boolean));
    await env.page.mouse.move(boxes[0].x + 4, boxes[0].y + 4); await env.page.mouse.down();
    await env.page.mouse.move(boxes[1].x + 4, boxes[1].y + 4); await env.page.mouse.up(); await env.ready();
    const rejectedDrag = await env.snapshot(); await artifact('tuple-drag-after.json', rejectedDrag); assert.equal(visual(rejectedDrag), visual(selected)); assert.equal(rejectedDrag.undo, selected.undo);
    await validate(env, rejectedDrag, result.authority); result.actions.push({ action: 'real overlapping sibling drag reverts without history' });
    await env.page.screenshot({ path: path.join(evidence, 'tuple-import.png'), fullPage: true });
    await artifact('tuple-import.json', rejectedDrag.document); result.ok = true; console.log('PASS imported shared-value tuple model');
  } catch (error) {
    result.error = error.stack; console.log('FAIL tuple import: ' + error.message);
    if (env) { await artifact('tuple-import-failure.json', (await env.snapshot()).document); await env.page.screenshot({ path: path.join(evidence, 'tuple-import-failure.png'), fullPage: true }); }
  } finally { if (env) await env.context.close(); }
  results.push(result); await artifact('report.json', { phase, base, results, errors, assets: [...assetUrls], compressed });

  const sourcefree = { name: 'Source-free catalog editing JSON', phase, ok: false, actions: [] }; env = null;
  try {
    env = await setup(); let routing = await selectCase(env, 'routing-lab'); assert.equal(routing.document.sourceAvailable, false);
    const id = routing.document.graph.nodes.find(node => !node.junction).id;
    await env.command('visual', { operations: [{ type: 'alias', id, label: 'Restored routing fixture' }] }); routing = await env.snapshot();
    const portable = routing.document; sourcefree.authority = sha(portable.graph.recursive.authority);
    await artifact('routing-edited-canvas.json', portable); await selectCase(env, '654be40c8d6a5cc2');
    const restored = await atomicJsonRestore(env, portable, sourcefree, 'source-free edited JSON');
    assert.equal(restored.document.sourceAvailable, false); assert.match((await env.command('request-source')).message, /路由实验|教学 SVG/);
    await validate(env, restored, sourcefree.authority); await env.page.screenshot({ path: path.join(evidence, 'routing-restored.png'), fullPage: true });
    sourcefree.ok = true; console.log('PASS source-free editing JSON');
  } catch (error) { sourcefree.error = error.stack; console.log('FAIL source-free editing JSON: ' + error.message); }
  finally { if (env) await env.context.close(); }
  results.push(sourcefree); await artifact('report.json', { phase, base, results, errors, assets: [...assetUrls], compressed });
  }

  if (args.includes('--saved-recovery')) for (const damage of ['layout', 'route']) {
    const recovered = { name: 'Malformed saved ' + damage + ' recovery', phase, ok: false, actions: [] }; env = null;
    try {
      env = await setup(true); const before = await env.snapshot(); recovered.authority = sha(before.document.graph.recursive.authority);
      await env.command('save');
      const corruption = await env.frame.evaluate(async ({ id, damage, authority }) => {
        const key = id + ':unified', saved = await window.SummaryRecursiveStorage.get(key);
        const check = structuredClone(saved.graph); check.recursive.authority = authority;
        if (damage === 'layout') {
          const moving = check.nodes.find(node => !node.expanded && !node.junction && check.nodes.some(other => other.id !== node.id && !other.expanded && !other.junction && other.parent === node.parent));
          const sibling = check.nodes.find(node => node.id !== moving.id && !node.expanded && !node.junction && node.parent === moving.parent);
          moving.x = sibling.x; moving.y = sibling.y;
          for (const edge of check.edges) {
            if (edge.source === moving.id) edge.route[0] = window.SummaryEngine.endpoint(check, edge, 'source');
            if (edge.target === moving.id) edge.route[edge.route.length - 1] = window.SummaryEngine.endpoint(check, edge, 'target');
          }
        } else {
          const edge = check.edges.find(edge => !edge.draft && edge.route.length >= 2), start = edge.route[0];
          edge.route = [start, { x: start.x + .371, y: start.y + .593 }, ...edge.route.slice(1)];
        }
        saved.graph = structuredClone(check); delete saved.graph.recursive.authority;
        await window.SummaryRecursiveStorage.put(key, saved);
        // Simulate loading an already-damaged persisted draft; prevent this
        // disposable page's unload hook from overwriting it with the good copy.
        const originalPut = window.SummaryRecursiveStorage.put;
        window.SummaryRecursiveStorage.put = (name, value) => name === key ? Promise.resolve() : originalPut(name, value);
        return { version: saved.graph.recursive.presentationVersion, validation: window.SummaryEngine.validateView(check) };
      }, { id: before.document.caseId, damage, authority: before.document.graph.recursive.authority });
      recovered.corruption = corruption;
      assert.equal(corruption.validation.source.ok, true, 'damage must retain the source contract');
      if (damage === 'layout') assert.equal(corruption.validation.layout.ok, false, 'damage must isolate invalid sibling layout');
      else { assert.equal(corruption.validation.layout.ok, true, 'route damage must retain the layout contract'); assert.ok(corruption.validation.edges.some(([, value]) => !value.ok), 'damage must isolate an invalid non-draft route'); }
      await env.page.reload();
      await env.page.waitForFunction(() => window.genericMessages.some(message => message.type === 'archcanvas:preview:ready'), null, { timeout: 180000 });
      env.frame = env.page.frame({ url: /preview\/yworks_edge_router_lab\/index.html/ }); await env.ready(); const restored = await env.snapshot();
      assert.equal(restored.document.caseId, before.document.caseId); assert.equal(geometry(restored), geometry(before));
      const archives = await env.frame.evaluate(id => Object.keys(localStorage).filter(key => key.startsWith('summary-merge:archived:' + id + ':unified:')), before.document.caseId);
      assert.ok(archives.length > 0, 'damaged draft must be retained in archive'); await validate(env, restored, recovered.authority);
      recovered.actions.push({ action: 'source-valid malformed persisted ' + damage + ' archived; valid baseline restored', archives: archives.length }); recovered.ok = true;
      console.log('PASS malformed saved ' + damage + ' recovery');
    } catch (error) { recovered.error = error.stack; console.log('FAIL malformed saved ' + damage + ': ' + error.message); }
    finally { if (env) await env.context.close(); }
    results.push(recovered); await artifact('report.json', { phase, base, results, errors, assets: [...assetUrls], compressed });
  }

  if (!args.includes('--saved-only')) {
  const standalone = { name: 'Standalone original preview surface', phase, ok: false, actions: [] }; env = null;
  try {
    env = await setup(true); const state = await env.snapshot(); standalone.authority = sha(state.document.graph.recursive.authority);
    assert.equal(await env.frame.locator('.toolbar').isVisible(), true);
    assert.ok((await env.command('ping')).capabilities.includes('pan-tool'));
    await toggle(env, 'dec.cross', true, 'plus', standalone);
    await toggle(env, 'dec.cross', false, 'plus', standalone);
    await env.command('undo'); const undone = await env.snapshot(); assert.ok(undone.document.graph.nodes.find(node => node.id === 'dec.cross').expanded);
    await validate(env, undone, standalone.authority);
    const annotationId = 'return-to-origin-test'; await env.command('visual', { operations: [{ type: 'annotation', annotation: { id: annotationId, text: 'No-op annotation gesture', x: 40, y: 40, width: 240 } }] });
    await env.command('focus', { annotationId });
    await env.command('visual', { operations: [{ type: 'alias', id: 'dec.cross', label: 'temporary redo fixture' }] }); await env.command('undo');
    const noteBefore = await env.snapshot(), noteBox = await env.frame.locator(`[data-studio-annotation="${annotationId}"]`).boundingBox(); assert.ok(noteBox);
    const noteX = noteBox.x + 8, noteY = noteBox.y + noteBox.height / 2;
    await env.page.mouse.move(noteX, noteY); await env.page.mouse.down(); await env.page.mouse.move(noteX + 30, noteY + 20, { steps: 3 });
    await env.page.mouse.move(noteX, noteY, { steps: 3 }); await env.page.mouse.up(); await env.ready(); const noteAfter = await env.snapshot();
    assert.equal(sha(noteAfter.document.graph), sha(noteBefore.document.graph)); assert.equal(noteAfter.undo, noteBefore.undo); assert.equal(noteAfter.redo, noteBefore.redo); assert.equal(noteAfter.dirty, noteBefore.dirty);
    standalone.actions.push({ action: 'native annotation drag away/back retains exact graph, dirty state and both history stacks' });
    await env.page.screenshot({ path: path.join(evidence, 'standalone.png'), fullPage: true }); standalone.ok = true; console.log('PASS standalone original preview');
  } catch (error) { standalone.error = error.stack; console.log('FAIL standalone: ' + error.message); }
  finally { if (env) await env.context.close(); }
  results.push(standalone); await artifact('report.json', { phase, base, results, errors, assets: [...assetUrls], compressed });
  }
}
const auditContext = await browser.newContext(), servedAssets = [];
for (const value of [...assetUrls, 'app.js', 'recursive-graph.js', 'frontier-task.js', 'router.js', 'routing-worker.js', 'studio-bridge.js', 'semantic-constraints.js', 'graph-engine.js', 'physical-ports.js', 'source-contracts.js']) {
  const url = value.startsWith('http') ? value : base + '/preview/yworks_edge_router_lab/' + value;
  const response = await auditContext.request.get(url), bytes = await response.body();
  assert.equal(response.status(), 200, url); servedAssets.push({ url, bytes: bytes.length, sha256: sha(bytes) });
}
await artifact('report.json', { phase, base, results, errors, assets: [...assetUrls], servedAssets, compressed });
await auditContext.close(); await browser.close();
console.log(JSON.stringify({ passed: results.filter(result => result.ok).length, total: results.length, evidence }));
if (phase !== 'baseline') assert.ok(results.every(result => result.ok), 'generalization failures: ' + results.filter(result => !result.ok).map(result => result.name).join(', '));
