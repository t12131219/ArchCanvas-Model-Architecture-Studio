import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Real Studio controls and native Shift selection in a fresh ephemeral context.
// Fixtures never reuse the user's saved browser profile or model document.
const args = process.argv.slice(2);
const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const evidence = path.resolve(option('--output-dir', path.join(root, 'docs/evidence/preview-arrangement-20261014')));
const base = option('--base', 'http://127.0.0.1:8891').replace(/\/$/, '');
const automation = option('--playwright', process.env.ARCHCANVAS_TEST_PLAYWRIGHT ?? '/home/fzg/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs');
const executablePath = option('--chromium', process.env.ARCHCANVAS_TEST_CHROMIUM ?? '/home/fzg/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome');
const { chromium } = await import(pathToFileURL(automation).href);
const browser = await chromium.launch({ headless: true, executablePath, args: ['--no-sandbox'] });
const context = await browser.newContext({ viewport: { width: 1640, height: 1080 } });
const page = await context.newPage(), checks = [], errors = [], assets = [];
let frame, lastState;
page.on('pageerror', error => errors.push(error.message));
page.on('response', response => { if (/\/assets\/[^/]+\.js$/.test(response.url())) assets.push(response.url()); });
await context.addInitScript(() => {
  window.arrangementMessages = [];
  window.addEventListener('message', event => {
    if (event.origin === location.origin && typeof event.data?.type === 'string' && event.data.type.startsWith('archcanvas:preview:')) window.arrangementMessages.push(event.data);
  });
  window.arrangementCommand = (name, payload = {}) => new Promise((resolve, reject) => {
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
const command = (name, payload) => page.evaluate(({ name, payload }) => window.arrangementCommand(name, payload), { name, payload });
const snapshot = async () => (lastState = await command('snapshot'));
const waitState = async predicate => {
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
const stableGraph = graph => ({ canvas: graph.canvas, nodes: graph.nodes, edges: graph.edges, sourceDraftOperations: graph.sourceDraftOperations,
  attachments: graph.attachments, routeLabels: graph.routeLabels, junctionMarkers: graph.junctionMarkers,
  authority: graph.recursive.authority, presentation: graph.recursive.state.studioPresentation });
const graphDigest = graph => digest(stableGraph(graph));
const sourceDigest = state => digest(state.document.graph.recursive.authority);
const positions = (state, ids) => ids.map(id => {
  const node = state.document.graph.nodes.find(node => node.id === id);
  return { id, x: node.x, y: node.y, w: node.w, h: node.h };
});
const selected = state => [...state.selectedNodes].sort();
const mark = (name, details) => { checks.push({ name, ...(details ? { details } : {}) }); console.log('PASS ' + name); };
const selectNodes = async ids => {
  await command('select-tool'); await command('fit');
  await frame.locator('#graph').press('Escape');
  for (const id of ids) await frame.locator(`[data-node-id="${id}"] .node-hit, [data-node-id="${id}"] .frame-hit`).first().click({ position: { x: 4, y: 4 }, modifiers: ['Shift'] });
  return waitState(state => canonical(selected(state)) === canonical([...ids].sort()));
};
const assertAtomicRejection = async (name, payload, expression) => {
  const before = await snapshot();
  await assert.rejects(command(name, payload), expression);
  const after = await snapshot();
  assert.equal(graphDigest(after.document.graph), graphDigest(before.document.graph));
  assert.equal(after.undo, before.undo); assert.equal(after.redo, before.redo);
  assert.equal(sourceDigest(after), sourceDigest(before));
  return after;
};
const toolbarPin = pinned => page.getByRole('button', { name: pinned ? '解锁所选节点' : '固定所选节点', exact: true });
const moveNode = async (id, position) => command('visual', { operations: [{ type: 'nodeLayout', id, position, scope: 'current-frontier', exact: true }] });
const dragNode = async (id, dx, dy) => {
  const box = await frame.locator(`[data-node-id="${id}"] .node-hit`).boundingBox();
  assert.ok(box?.width > 0 && box?.height > 0);
  await page.mouse.move(box.x + 8, box.y + 8); await page.mouse.down();
  await page.mouse.move(box.x + 8 + dx, box.y + 8 + dy, { steps: 6 }); await page.mouse.up();
  return waitState(state => !state.busy);
};

await fs.mkdir(evidence, { recursive: true });
try {
  await page.goto(base + '/');
  await page.waitForFunction(() => window.arrangementMessages.some(message => message.type === 'archcanvas:preview:ready'));
  await page.waitForFunction(() => document.querySelector('.import-button') && !document.querySelector('.import-button').disabled);
  frame = page.frame({ url: /preview\/yworks_edge_router_lab\/index.html/ });
  assert.ok(frame);
  const className = 'ArrangementSmoke' + Date.now();
  const source = `from torch import nn\n\nclass Inner(nn.Module):\n    def __init__(self):\n        super().__init__()\n        self.inner_act = nn.Sigmoid()\n    def forward(self, features):\n        return self.inner_act(features)\n\nclass ${className}(nn.Module):\n    def __init__(self):\n        super().__init__()\n        self.project = nn.Linear(4, 4)\n        self.act = nn.ReLU()\n        self.norm = nn.LayerNorm(4)\n        self.nested = Inner()\n    def forward(self, features):\n        value = self.project(features)\n        value = self.act(value)\n        value = self.norm(value)\n        return self.nested(value)\n`;
  await page.locator('.import-button').click();
  await page.getByLabel('模型类名', { exact: true }).fill(className);
  await page.getByLabel('文件名', { exact: true }).fill('arrangement_smoke.py');
  await page.getByLabel('Python 源码', { exact: true }).fill(source);
  await page.getByRole('button', { name: '静态分析并打开画布', exact: true }).click();
  await page.getByRole('dialog', { name: '从 Python 源码开始', exact: true }).waitFor({ state: 'detached' });
  const loaded = await waitState(state => state.document?.adapter?.entry?.endsWith(':' + className));
  await page.waitForFunction(() => !document.querySelector('.canvas-toolbar [aria-label="Apply layout"]')?.disabled);
  assert.equal(await page.getByRole('button', { name: 'Apply layout', exact: true }).count(), 1);
  assert.equal(await page.locator('.canvas-toolbar').getByText('论文彩色', { exact: true }).count(), 0);
  mark('Apply layout appears once in the toolbar and paper color preset is removed');

  const beforeApply = await snapshot();
  await page.getByRole('button', { name: 'Apply layout', exact: true }).click();
  const applied = await waitState(state => !state.busy && state.undo === beforeApply.undo + 1);
  assert.equal(sourceDigest(applied), sourceDigest(beforeApply));
  assert.equal(await frame.locator('#graph').getAttribute('data-source-constraint-valid'), 'true');
  mark('toolbar Apply layout executes the native router and preserves source authority');

  const authorityBefore = sourceDigest(applied), graph = applied.document.graph;
  const modules = graph.nodes.filter(node => ['linear', 'activation', 'normalization'].includes(node.semantic?.kind) && !node.junction);
  assert.ok(modules.length >= 3, 'fixture must provide three ordinary modules');
  const candidates = modules.filter(node => node.parent === modules[0].parent).sort((a, b) => a.y - b.y);
  assert.ok(candidates.length >= 3);
  const ids = candidates.slice(0, 3).map(node => node.id), middleId = ids[1];
  await fs.writeFile(path.join(evidence, 'fixture-source.py'), source);
  mark('fresh source fixture provides real same-parent preview nodes', { className, ids, positions: positions(loaded, ids) });

  // The original router owns validation. Prepare small legal displacements,
  // never editing a graph or semantic receipt behind the engine's back.
  const middle = candidates[1];
  await moveNode(middleId, { x: middle.x + 8 });
  await selectNodes(ids);
  const beforeAlign = await snapshot();
  await page.getByRole('button', { name: '左对齐所选节点', exact: true }).click();
  const aligned = await waitState(state => positions(state, ids).every(node => Math.abs(node.x - positions(state, ids)[0].x) < 1e-5));
  assert.equal(aligned.undo, beforeAlign.undo + 1);
  assert.equal(sourceDigest(aligned), authorityBefore);
  assert.equal(await frame.locator('#graph').getAttribute('data-source-constraint-valid'), 'true');
  mark('native Shift multiselection and parent left-align apply exact preview positions in one undo step');
  await command('undo'); const undone = await snapshot();
  assert.deepEqual(positions(undone, ids), positions(beforeAlign, ids));
  await command('redo'); const redone = await snapshot();
  assert.deepEqual(positions(redone, ids), positions(aligned, ids));
  await selectNodes(ids);
  const beforeNoop = await snapshot(); await command('arrange-selection', { kind: 'left' });
  assert.equal((await snapshot()).undo, beforeNoop.undo);
  mark('alignment undo/redo restores exact geometry and repeated alignment adds no history');

  const afterAlignMiddle = positions(redone, ids)[1];
  await moveNode(middleId, { y: afterAlignMiddle.y + 8 }); await selectNodes(ids);
  const beforeDistribute = await snapshot();
  await page.getByLabel('更多对齐与分布', { exact: true }).click();
  await page.getByRole('button', { name: '垂直等距分布', exact: true }).click();
  const distributed = await waitState(state => state.undo === beforeDistribute.undo + 1);
  const spaced = positions(distributed, ids).sort((a, b) => a.y - b.y);
  assert.ok(Math.abs((spaced[1].y - spaced[0].y - spaced[0].h) - (spaced[2].y - spaced[1].y - spaced[1].h)) < 1e-5);
  assert.deepEqual(spaced[0], positions(beforeDistribute, ids)[0]);
  assert.deepEqual(spaced[2], positions(beforeDistribute, ids)[2]);
  assert.equal(sourceDigest(distributed), authorityBefore);
  mark('parent distribution menu equalizes vertical gaps while retaining endpoints and source authority');

  await toolbarPin(false).click();
  const pinned = await waitState(state => ids.every(id => state.document.graph.recursive.state.studioPresentation.nodes[id]?.pinned));
  assert.equal(await toolbarPin(true).getAttribute('aria-pressed'), 'true');
  assert.equal(await frame.locator('[data-pinned-node]').count(), ids.length);
  const beforePinNoop = await snapshot(); await command('pin-selection', { pinned: true });
  assert.equal((await snapshot()).undo, beforePinNoop.undo);
  const blockedDrag = await dragNode(middleId, 16, 0);
  assert.deepEqual(positions(blockedDrag, ids), positions(pinned, ids));
  assert.equal(blockedDrag.undo, pinned.undo);
  assert.equal(sourceDigest(blockedDrag), authorityBefore);
  mark('toolbar fixes all raw selected nodes, shows editor badges and blocks direct drag without history');
  const exported = await command('svg');
  assert.doesNotMatch(exported.svg, /data-pinned-node|data-editor-only="pin"/);
  assert.match(exported.svg, /archcanvas-preview-document/);
  await fs.writeFile(path.join(evidence, 'arrangement-pinned.svg'), exported.svg);
  mark('fixed-position badges are editor-only and do not enter figure SVG');
  await selectNodes(ids);
  await assertAtomicRejection('arrange-selection', { kind: 'distribute-y' }, /解锁|固定/);
  mark('distribution with fixed nodes rejects atomically and preserves graph, source and history');
  await toolbarPin(true).click(); await waitState(state => ids.every(id => !state.document.graph.recursive.state.studioPresentation.nodes[id]?.pinned));
  await selectNodes([middleId]);
  const beforeUnlockedDrag = await snapshot(), moved = await dragNode(middleId, 12, 0);
  assert.notDeepEqual(positions(moved, [middleId]), positions(beforeUnlockedDrag, [middleId]));
  assert.equal(moved.undo, beforeUnlockedDrag.undo + 1); assert.equal(sourceDigest(moved), authorityBefore);
  await command('undo');
  mark('unlock restores original engine dragging and native undo history');

  await selectNodes(ids);
  await assertAtomicRejection('arrange-selection', { kind: 'top' }, /位置|连接|约束/);
  mark('an overlapping alignment candidate rejects atomically');
  await selectNodes([candidates[0].parent, middleId]);
  await assertAtomicRejection('arrange-selection', { kind: 'left' }, /同一容器|父子|跨容器/);
  assert.equal(await page.getByRole('button', { name: '左对齐所选节点', exact: true }).isDisabled(), true);
  mark('mixed parent-child selection is disabled in the toolbar and rejected by the authoritative engine');
  await selectNodes([middleId]);
  await assertAtomicRejection('arrange-selection', { kind: 'left' }, /至少 2/);
  await assertAtomicRejection('pin-selection', { pinned: 'invalid' }, /布尔/);
  await assertAtomicRejection('arrange-selection', { kind: 'unknown' }, /未知/);
  await assertAtomicRejection('visual', { operations: [{ type: 'nodeLayout', id: middleId, position: { x: -1000 }, exact: true }] }, /容器|边界|位置|约束/);
  mark('too few nodes, invalid commands and an out-of-container exact position reject without partial commits');

  await selectNodes([ids[0]]); await toolbarPin(false).click();
  await selectNodes(ids);
  const anchorBefore = await snapshot();
  const other = positions(anchorBefore, ids)[1];
  await moveNode(other.id, { x: other.x + 8 });
  const anchorPrepared = await snapshot();
  await page.getByRole('button', { name: '左对齐所选节点', exact: true }).click();
  const anchorAligned = await waitState(state => state.undo === anchorPrepared.undo + 1);
  const anchor = positions(anchorPrepared, [ids[0]])[0];
  assert.deepEqual(positions(anchorAligned, [ids[0]])[0], anchor);
  assert.ok(positions(anchorAligned, ids).every(node => Math.abs(node.x - anchor.x) < 1e-5));
  assert.equal(sourceDigest(anchorAligned), authorityBefore);
  mark('a fixed selected node serves as the alignment anchor without being moved');
  await command('pin-selection', { pinned: true });
  const saved = await command('save'); await command('load', { bundle: saved.document });
  const restored = await snapshot();
  assert.deepEqual(positions(restored, ids), positions(saved, ids));
  assert.ok(ids.every(id => restored.document.graph.recursive.state.studioPresentation.nodes[id]?.pinned));
  assert.equal(sourceDigest(restored), authorityBefore);
  mark('save and editing JSON restore preserve arrangement, fixed state and canonical source');

  const nested = restored.document.graph.nodes.find(node => node.semantic?.kind === 'group' && node.parent);
  assert.ok(nested);
  await command('visual', { operations: [{ type: 'expand', id: nested.id, expanded: true }] });
  const expanded = await snapshot();
  const childCandidates = expanded.document.graph.nodes.filter(node => node.parent === nested.id && !node.junction);
  const mappingCoverage = [];
  let unmappedId;
  for (const child of childCandidates) {
    await selectNodes([child.id]);
    await page.waitForTimeout(100);
    const formalCount = await page.locator('.tree [role="treeitem"][aria-selected="true"]').count();
    mappingCoverage.push({ id: child.id, kind: child.semantic?.kind, formalCount });
    if (!formalCount) { unmappedId = child.id; break; }
  }
  if (unmappedId) {
    await toolbarPin(false).click();
    const rawPinned = await waitState(state => state.document.graph.recursive.state.studioPresentation.nodes[unmappedId]?.pinned);
    assert.match(await page.getByLabel('画布选区', { exact: true }).getByRole('heading').innerText(), /已选 1 个节点\s*已固定 1 个/);
    assert.equal(sourceDigest(rawPinned), authorityBefore);
    await toolbarPin(true).click();
    mark('a raw preview node without a formal selected-object mapping can still use toolbar pin and unlock', { unmappedId, mappingCoverage });
  } else mark('nested raw preview selection remains usable through toolbar controls', { mappingCoverage });

  for (const [kind, label, fraction] of [['hcenter', '水平居中对齐', .5], ['right', '右对齐', 1]]) {
    await command('load', { bundle: saved.document }); await selectNodes(ids); await command('pin-selection', { pinned: false });
    const basePositions = positions(await snapshot(), ids);
    await moveNode(middleId, { x: basePositions[1].x + 8 });
    const before = await snapshot();
    await page.getByLabel('更多对齐与分布', { exact: true }).click(); await page.getByRole('button', { name: label, exact: true }).click();
    const after = await waitState(state => state.undo === before.undo + 1);
    const actual = positions(after, ids), coordinate = node => node.x + node.w * fraction;
    assert.ok(actual.every(node => Math.abs(coordinate(node) - coordinate(actual[0])) < 1e-5));
    assert.equal(sourceDigest(after), authorityBefore);
    mark('parent ' + label + ' menu applies exact coordinates with native routing');
  }

  const branchClass = 'BranchArrangementSmoke' + Date.now();
  const branchSource = `from torch import nn\n\nclass ${branchClass}(nn.Module):\n    def __init__(self):\n        super().__init__()\n        self.project = nn.Linear(4, 4)\n        self.act = nn.ReLU()\n        self.norm = nn.LayerNorm(4)\n    def forward(self, features):\n        left = self.project(features)\n        middle = self.act(features)\n        right = self.norm(features)\n        return left, middle, right\n`;
  await page.locator('.import-button').click();
  await page.getByLabel('模型类名', { exact: true }).fill(branchClass);
  await page.getByLabel('文件名', { exact: true }).fill('branch_arrangement_smoke.py');
  await page.getByLabel('Python 源码', { exact: true }).fill(branchSource);
  await page.getByRole('button', { name: '静态分析并打开画布', exact: true }).click();
  await page.getByRole('dialog', { name: '从 Python 源码开始', exact: true }).waitFor({ state: 'detached' });
  const branched = await waitState(state => state.document?.adapter?.entry?.endsWith(':' + branchClass));
  await page.waitForFunction(() => !document.querySelector('.canvas-toolbar [aria-label="Apply layout"]')?.disabled);
  const branchNodes = branched.document.graph.nodes.filter(node => ['linear', 'activation', 'normalization'].includes(node.semantic?.kind)).sort((a, b) => a.x - b.x);
  assert.equal(branchNodes.length, 3);
  const branchIds = branchNodes.map(node => node.id), branchAuthority = sourceDigest(branched), branchSaved = await command('save');
  for (const [kind, label, fraction] of [['top', '顶部对齐', 0], ['vcenter', '垂直居中对齐', .5], ['bottom', '底部对齐', 1], ['distribute-x', '水平等距分布', null]]) {
    await command('load', { bundle: branchSaved.document }); await selectNodes(branchIds);
    await moveNode(branchIds[1], kind === 'distribute-x' ? { x: branchNodes[1].x + 8 } : { y: branchNodes[1].y + 8 });
    const before = await snapshot();
    await page.getByLabel('更多对齐与分布', { exact: true }).click(); await page.getByRole('button', { name: label, exact: true }).click();
    const after = await waitState(state => state.undo === before.undo + 1), actual = positions(after, branchIds);
    if (kind === 'distribute-x') {
      assert.ok(Math.abs((actual[1].x - actual[0].x - actual[0].w) - (actual[2].x - actual[1].x - actual[1].w)) < 1e-5);
      assert.deepEqual(actual[0], positions(before, branchIds)[0]); assert.deepEqual(actual[2], positions(before, branchIds)[2]);
    } else {
      const coordinate = node => node.y + node.h * fraction;
      assert.ok(actual.every(node => Math.abs(coordinate(node) - coordinate(actual[0])) < 1e-5));
    }
    assert.equal(sourceDigest(after), branchAuthority);
    mark('parent ' + label + ' works on real parallel source branches without changing source bindings');
  }
  await fs.writeFile(path.join(evidence, 'branch-fixture-source.py'), branchSource);
  await command('load', { bundle: saved.document });

  await selectNodes(ids);
  assert.deepEqual(errors, []);
  await page.screenshot({ path: path.join(evidence, 'studio-arrangement.png') });
  await fs.writeFile(path.join(evidence, 'report.json'), JSON.stringify({ schema: 'archcanvas-preview-arrangement-smoke/1', ok: true, base,
    browserProfile: 'isolated ephemeral context', checks, browserErrors: errors, servedAssets: [...new Set(assets)],
    sourceAuthoritySha256: authorityBefore, finalPositions: positions(restored, ids), screenshot: 'studio-arrangement.png' }, null, 2) + '\n');
  for (const name of ['failure.json', 'failure.png']) await fs.rm(path.join(evidence, name), { force: true });
  console.log(JSON.stringify({ ok: true, checks: checks.length, output: path.join(evidence, 'report.json') }));
} catch (error) {
  await page.screenshot({ path: path.join(evidence, 'failure.png') }).catch(() => {});
  await fs.writeFile(path.join(evidence, 'failure.json'), JSON.stringify({ ok: false, checks, browserErrors: errors, error: error.stack, lastState,
    pageText: await page.locator('body').innerText().catch(() => '') }, null, 2) + '\n');
  throw error;
} finally { await browser.close(); }
