import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { gzipSync } from 'node:zlib';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Uses a fresh, disposable browser context: no saved user canvas is changed.
const args = process.argv.slice(2), option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const phase = option('--phase', 'final');
const evidence = path.resolve(option('--output-dir', path.join(root, 'docs/evidence/preview-expansion-20261014', phase)));
const base = option('--base', 'http://127.0.0.1:8891').replace(/\/$/, '');
const automation = option('--playwright', '/home/fzg/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs');
const executablePath = option('--chromium', '/home/fzg/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome');
const { chromium } = await import(pathToFileURL(automation).href);
const browser = await chromium.launch({ headless: true, executablePath, args: ['--no-sandbox'] });
const context = await browser.newContext({ viewport: { width: 1640, height: 1080 } });
if (args.includes('--no-worker')) await context.addInitScript(() => { window.Worker = undefined; });
const page = await context.newPage(), errors = [], assets = [], checks = [], steps = [];
page.on('pageerror', error => errors.push(error.message));
page.on('response', response => { if (/\/assets\/[^/]+\.js$/.test(response.url())) assets.push(response.url()); });
await context.addInitScript(() => {
  window.expansionLongTasks = [];
  new PerformanceObserver(list => { for (const entry of list.getEntries()) window.expansionLongTasks.push({ start: entry.startTime, duration: entry.duration, name: entry.name,
    attribution: entry.attribution.map(item => ({ name: item.name, containerType: item.containerType, containerId: item.containerId, containerName: item.containerName, containerSrc: item.containerSrc })) }); }).observe({ type: 'longtask', buffered: true });
  window.expansionMessages = []; window.expansionMeta = null;
  window.addEventListener('message', event => {
    if (event.origin !== location.origin || typeof event.data?.type !== 'string' || !event.data.type.startsWith('archcanvas:preview:')) return;
    const value = event.data;
    window.expansionMessages.push({ type: value.type, at: performance.now(), command: value.command, message: value.message });
    if (value.document?.graph) window.expansionMeta = { at: performance.now(), busy: value.busy, undo: value.undo,
      nodes: value.document.graph.nodes.length, edges: value.document.graph.edges.length,
      caseId: value.document.caseId, expanded: value.document.graph.nodes.filter(node => node.expanded).map(node => node.id) };
  });
  window.expansionCommand = (name, payload = {}) => new Promise((resolve, reject) => {
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
const command = (name, payload) => page.evaluate(({ name, payload }) => window.expansionCommand(name, payload), { name, payload });
let latestState;
const snapshot = async () => (latestState = await command('snapshot'));
const mark = (name, details) => { checks.push({ name, ...(details ? { details } : {}) }); console.log('PASS ' + name); };
const sha = value => createHash('sha256').update(typeof value === 'string' ? value : JSON.stringify(value)).digest('hex');
const canonical = value => JSON.stringify(value, (_key, item) => item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item);
const visualDigest = state => sha(canonical({ nodes: state.document.graph.nodes, edges: state.document.graph.edges,
  canvas: state.document.graph.canvas, open: state.document.graph.recursive.state.open }));
const compressedArtifacts = [];
async function artifact(name, value) {
  const bytes = Buffer.from(typeof value === 'string' ? value : JSON.stringify(value, null, 2) + '\n');
  if (bytes.length <= 1024 * 1024) return fs.writeFile(path.join(evidence, name), bytes);
  const zipped = gzipSync(bytes, { mtime: 0 });
  await fs.writeFile(path.join(evidence, name + '.gz'), zipped);
  compressedArtifacts.push({ original: name, gzip: name + '.gz', bytes: bytes.length, gzipBytes: zipped.length,
    originalSha256: createHash('sha256').update(bytes).digest('hex'), gzipSha256: createHash('sha256').update(zipped).digest('hex') });
  await fs.writeFile(path.join(evidence, 'compressed-artifacts.json'), JSON.stringify(compressedArtifacts, null, 2) + '\n');
}
let frame, sourceSha, initial;
const readMetrics = async () => ({
  parent: await page.evaluate(() => ({ now: performance.now(), longTasks: window.expansionLongTasks })),
  preview: await frame.evaluate(() => ({ now: performance.now(), longTasks: window.expansionLongTasks,
    svg: Object.fromEntries([...document.querySelector('#graph').attributes].filter(item => item.name.startsWith('data-')).map(item => [item.name, item.value])),
    status: document.querySelector('#dirtyBadge')?.textContent, toast: document.querySelector('#toast')?.textContent })),
});
const checkGraph = async state => frame.evaluate(graph => {
  const start = performance.now(), result = window.SummaryEngine.validateView(graph);
  const memory = graph.edges.filter(edge => edge.source === 'enc.memory.value' && ['dec.cross.k', 'dec.cross.v'].includes(edge.target));
  const routeSummary = edge => {
    const target = graph.nodes.find(node => node.id === edge.target), terminal = edge.route.at(-1), previous = edge.route.at(-2);
    return { id: edge.id, source: edge.source, target: edge.target, points: edge.route.length,
      length: edge.route.slice(1).reduce((sum, point, index) => sum + Math.hypot(point.x - edge.route[index].x, point.y - edge.route[index].y), 0),
      sourceSide: edge.sourcePort?.side ?? edge.route[0]?.side, targetSide: edge.targetPort?.side ?? terminal?.side,
      bottomApproach: !!(target && terminal && previous && Math.abs(terminal.y - target.y - target.h) < 1e-5 && previous.y > terminal.y && Math.abs(previous.x - terminal.x) < 1e-5) };
  };
  return { ms: performance.now() - start, source: result.source, layout: result.layout,
    routing: result.routing, failedEdges: result.edges.filter(([, check]) => !check.ok),
    memoryRoutes: memory.map(routeSummary), routes: graph.edges.map(routeSummary) };
}, state.document.graph);
const toggle = async (id, expanded = true) => {
  await command('fit');
  const start = Date.now(), before = await readMetrics(), stateBefore = await snapshot();
  const actionStart = Date.now();
  console.log('STEP ' + (expanded ? 'expand ' : 'collapse ') + id);
  const locator = frame.locator(`[data-node-id="${id}"] .expansion-control`);
  assert.equal(await locator.count(), 1, id + ' must have an expansion control');
  await locator.click({ timeout: 180000 });
  await page.waitForFunction(({ id, expanded, undo }) => {
    const state = window.expansionMeta;
    return state && !state.busy && state.undo === undo + 1 && state.expanded.includes(id) === expanded;
  }, { id, expanded, undo: stateBefore.undo }, { timeout: 180000 });
  // Read state after timing the visible interaction rather than adding its
  // large diagnostic transfer to the reported gesture latency.
  const visibleMs = Date.now() - start, actionMs = Date.now() - actionStart, after = await readMetrics(), state = await snapshot();
  const result = { id, expanded, visibleMs, actionMs, diagnosticSetupMs: actionStart - start, nodes: state.document.graph.nodes.length, edges: state.document.graph.edges.length,
    parentLongTasks: after.parent.longTasks.filter(task => task.start >= before.parent.now),
    previewLongTasks: after.preview.longTasks.filter(task => task.start >= before.preview.now),
    svg: after.preview.svg, sourceAuthoritySha256: sha(state.document.graph.recursive.authority),
    validation: await checkGraph(state) };
  steps.push(result); assert.equal(result.sourceAuthoritySha256, sourceSha);
  await fs.writeFile(path.join(evidence, 'steps.json'), JSON.stringify(steps, null, 2) + '\n');
  console.log(JSON.stringify({ id, expanded, visibleMs, nodes: result.nodes, edges: result.edges,
    parentSelfMs: result.parentLongTasks.filter(task => task.name === 'self').reduce((sum, task) => sum + task.duration, 0),
    previewSelfMs: result.previewLongTasks.filter(task => task.name === 'self').reduce((sum, task) => sum + task.duration, 0),
    laneContacts: result.validation.routing.contacts.length, failedEdges: result.validation.failedEdges.length }));
  if (phase !== 'baseline') {
    assert.equal(result.validation.source.ok, true, id + ': source integrity');
    assert.equal(result.validation.layout.ok, true, id + ': sibling nodes and unrelated tensor lanes');
    assert.deepEqual(result.validation.failedEdges, [], id + ': route constraints');
    if (!args.includes('--diagnostic-contacts')) {
      assert.deepEqual(result.validation.routing.contacts, [], id + ': visible container lane clearance');
      assert.deepEqual(result.validation.routing.constrained, [], id + ': no degraded container lane');
    }
    if (result.validation.memoryRoutes.length) {
      assert.equal(result.validation.memoryRoutes.length, 2, id + ': independent memory K and V consumers');
      assert.ok(result.validation.memoryRoutes.every(edge => edge.bottomApproach), id + ': Memory enters K/V from the recorded bottom direction');
    }
    const maxMs = Number(option('--max-step-ms', Infinity));
    assert.ok(visibleMs <= maxMs, id + ': visible interaction exceeded ' + maxMs + 'ms');
    mark((expanded ? 'expand ' : 'collapse ') + id + ' preserves source, geometry and recorded consumer ports');
  }
  return state;
};
async function sharedTrunkSupplement(catalog, menu) {
  const bindings = graph => sha(canonical({ baseline: graph.semanticBaseline, edges: graph.edges.map(e => ({ id: e.id, source: e.source, target: e.target, binding: e.binding })) }));
  async function dragTen(id, label) {
    await command('select-tool'); await command('fit');
    const before = await snapshot(), node = before.document.graph.nodes.find(n => n.id === id); assert.ok(node);
    const box = await frame.locator(`[data-node-id="${id}"] .node-hit, [data-node-id="${id}"] .frame-hit`).first().boundingBox(); assert.ok(box);
    const x = box.x + Math.min(5, box.width / 2), y = box.y + Math.min(5, box.height / 2), dx = 10 * box.width / node.w;
    await page.mouse.move(x, y); await page.mouse.down(); await page.mouse.move(x + dx, y, { steps: 5 }); await page.mouse.up();
    await page.waitForFunction(undo => window.expansionMeta && !window.expansionMeta.busy && window.expansionMeta.undo === undo + 1, before.undo, { timeout: 30000 });
    const after = await snapshot(), moved = after.document.graph.nodes.find(n => n.id === id);
    assert.ok(Math.abs(moved.x - node.x - 10) < .1, id + ': native move must commit 10 graph units');
    assert.ok(Math.abs(moved.y - node.y) < .1); assert.equal(bindings(after.document.graph), bindings(before.document.graph));
    assert.equal(sha(after.document.graph.recursive.authority), sourceSha);
    const validation = await checkGraph(after); assert.equal(validation.source.ok, true); assert.equal(validation.layout.ok, true);
    assert.deepEqual(validation.failedEdges, []); assert.deepEqual(validation.routing.contacts, []);
    const junctions = await frame.evaluate(({ graph, id }) => {
      const E = window.SummaryEngine, J = window.SummaryJunctionMarkers;
      return (graph.junctionMarkers || []).filter(m => m.owner === id).map(m => {
        const point = E.junctionPoint(graph, m), routes = m.edges.map(edgeId => graph.edges.find(e => e.id === edgeId)?.route);
        return { id: m.id, point, connected: !!point && routes.every(route => route && J.contains(route, point)), rays: point ? J.rays(routes, point).size : 0 };
      });
    }, { graph: after.document.graph, id });
    assert.ok(junctions.length, id + ': source fork marker exists'); assert.ok(junctions.every(m => m.connected && m.rays >= 3));
    await artifact(label + '-moved.json', after.document); await page.screenshot({ path: path.join(evidence, label + '-moved.png'), fullPage: true });
    await command('undo'); assert.equal(visualDigest(await snapshot()), visualDigest(before));
    await command('redo'); assert.equal(visualDigest(await snapshot()), visualDigest(after));
    await command('undo'); mark(label + ' native +10 move retains bindings, real fork junction and exact undo/redo', { nodeId: id, junctions });
  }
  for (const item of [catalog.cases.find(c => c.id === '01093cc06a87b35a'), catalog.cases.find(c => c.id === '87dbdc94e0f6462f')]) {
    assert.ok(item); const label = item.id === '01093cc06a87b35a' ? 'standard' : 'compact';
    if ((await snapshot()).document.caseId !== item.id) {
      if (await menu.getAttribute('open') === null) await menu.locator('summary').click();
      await page.getByRole('button', { name: '示例与模块库', exact: true }).click();
      await frame.locator('#search').fill(''); await frame.locator('#collection').selectOption('all');
      await frame.locator(`button[data-case-id="${item.id}"]`).click();
      await page.waitForFunction(id => window.expansionMeta?.caseId === id && !window.expansionMeta.busy, item.id, { timeout: 180000 });
      await frame.locator('.library .studio-drawer-close').click(); if (await menu.getAttribute('open') !== null) await menu.locator('summary').click();
    }
    sourceSha = sha((await snapshot()).document.graph.recursive.authority);
    await dragTen('enc.norm1', label + '-overview-layernorm');
    await toggle('enc.self');
    const shared = await snapshot(), trunk = await frame.evaluate(graph => {
      const E = window.SummaryEngine, C = window.SummaryConstraints, R = window.EdgeRouterLabRouting;
      return graph.edges.filter(e => e.source === 'src_pe.add' && ['enc.self.q', 'enc.self.k', 'enc.self.v'].includes(e.target)).map(e => {
        const source = E.endpoint(graph, e, 'source'), gates = C.activeGates(graph, e);
        return { id: e.id, target: e.target, points: R.simplify(e.route).length, gateCount: gates.length, wire: e.contract?.wire,
          aligned: gates.every(gate => Math.abs(C.gatePoint(graph.nodes.find(n => n.id === gate.frame), gate).x - source.x) < 1e-5) };
      });
    }, shared.document.graph);
    assert.equal(trunk.length, 3); assert.equal(new Set(trunk.map(e => e.wire)).size, 1, label + ': shared producer remains one wire');
    if (label === 'standard') {
      assert.equal(trunk.find(e => e.target === 'enc.self.k').points, 2, label + ': source-aligned center K remains straight');
      assert.ok(trunk.every(e => e.points <= 4 && e.gateCount === 2 && e.aligned), label + ': source-aligned shared Q/K/V trunk retains aligned gates');
    }
    const sourceReference = await (await context.request.get(base + '/preview/data/cases/' + item.id + '-detailed.json')).json();
    const contractEvidence = await frame.evaluate(({ graph, reference }) => {
      const E = window.SummaryEngine, J = window.SummaryJunctionMarkers, R = window.EdgeRouterLabRouting;
      const branches = graph.edges.filter(e => e.source === 'src_pe.add' && ['enc.self.q', 'enc.self.k', 'enc.self.v'].includes(e.target));
      return { branches: branches.map(e => {
        const original = reference.edges.find(raw => raw.id === e.id);
        return { id: e.id, points: R.simplify(e.route).length, referencePoints: R.simplify(original.route).length,
          sourceBindingIntact: JSON.stringify(e.binding) === JSON.stringify(original.binding),
          gateRolesIntact: JSON.stringify(e.contract.gates.map(({ frame, side, direction, order }) => ({ frame, side, direction, order }))) === JSON.stringify(original.contract.gates.map(({ frame, side, direction, order }) => ({ frame, side, direction, order }))) };
      }), junctions: graph.junctionMarkers.filter(m => m.owner === 'src_pe.add').map(m => {
        const point = E.junctionPoint(graph, m), routes = m.edges.map(id => graph.edges.find(e => e.id === id)?.route);
        return { id: m.id, connected: !!point && routes.every(route => route && J.contains(route, point)), rays: point ? J.rays(routes, point).size : 0 };
      }) };
    }, { graph: shared.document.graph, reference: sourceReference });
    assert.ok(contractEvidence.branches.every(e => e.sourceBindingIntact && e.gateRolesIntact));
    assert.ok(contractEvidence.junctions.length && contractEvidence.junctions.every(m => m.connected && m.rays >= 3));
    await artifact(label + '-shared-qkv.json', shared.document); await page.screenshot({ path: path.join(evidence, label + '-shared-qkv.png'), fullPage: true });
    mark(label + (label === 'standard' ? ' native expansion keeps source-aligned Q/K/V center straight' : ' native expansion retains recorded compact Q/K/V corridor and connected source fork'), { trunk, contractEvidence });
    await toggle('enc.norm1'); await dragTen('enc.norm1.layernorm', label + '-detail-layernorm');
  }
}
await fs.mkdir(evidence, { recursive: true });
try {
  await page.goto(base + '/');
  await page.waitForFunction(() => window.expansionMessages.some(message => message.type === 'archcanvas:preview:ready'), null, { timeout: 180000 });
  frame = page.frame({ url: /preview\/yworks_edge_router_lab\/index.html/ }); assert.ok(frame);
  await page.waitForFunction(() => { const el = document.querySelector('.canvas-toolbar [aria-label="Apply layout"]'); return el && !el.disabled; }, null, { timeout: 180000 });
  const catalog = await (await context.request.get(base + '/preview/data/catalog.json')).json();
  const candidates = catalog.cases.filter(item => /transformer/i.test(item.title));
  await fs.writeFile(path.join(evidence, 'transformer-candidates.json'), JSON.stringify(candidates, null, 2) + '\n');
  const selected = candidates.find(item => item.id === '01093cc06a87b35a'); assert.ok(selected);
  console.log('CASE ' + JSON.stringify(selected));
  const menu = page.locator('.studio .workspace-menu');
  if (await menu.getAttribute('open') === null) await menu.locator('summary').click();
  await page.getByRole('button', { name: '示例与模块库', exact: true }).click();
  await frame.locator('.library').waitFor({ state: 'visible' });
  await frame.locator('#search').fill(''); await frame.locator('#collection').selectOption('all');
  await frame.locator(`button[data-case-id="${selected.id}"]`).click({ timeout: 180000 });
  await page.waitForFunction(id => window.expansionMeta?.caseId === id && !window.expansionMeta.busy, selected.id, { timeout: 180000 });
  await frame.locator('.library .studio-drawer-close').click();
  if (await menu.getAttribute('open') !== null) await menu.locator('summary').click();
  await page.waitForFunction(() => { const el = document.querySelector('.canvas-toolbar [aria-label="Apply layout"]'); return el && !el.disabled; }, null, { timeout: 180000 });
  initial = await snapshot(); sourceSha = sha(initial.document.graph.recursive.authority);
  await artifact('initial.json', initial.document);
  mark('Transformer main case loads through the hidden catalog in a fresh context', { caseId: selected.id, sourceAuthoritySha256: sourceSha });
  if (args.includes('--shared-trunks-only')) await sharedTrunkSupplement(catalog, menu);
  else {
  if (args.includes('--expand-all-only')) {
    const all = await command('expand-all'), validation = await checkGraph(all);
    assert.equal(all.document.graph.nodes.length, all.document.graph.recursive.authority.detail.nodes.length);
    assert.equal(sha(all.document.graph.recursive.authority), sourceSha);
    assert.equal(validation.source.ok, true); assert.equal(validation.layout.ok, true);
    assert.deepEqual(validation.failedEdges, []); assert.deepEqual(validation.routing.contacts, []); assert.deepEqual(validation.routing.constrained, []);
    mark('one native expand-all retains full detailed layout and zero invalid routes or container lane contacts', { nodes: all.document.graph.nodes.length, edges: all.document.graph.edges.length });
  } else await toggle('dec.cross');
  await command('fit');
  await page.screenshot({ path: path.join(evidence, 'decoder-cross-full.png'), fullPage: true });
  await frame.locator('[data-node-id="dec.cross"]').screenshot({ path: path.join(evidence, 'decoder-cross-detail.png') });
  await artifact('decoder-cross.json', (await snapshot()).document);
  const exported = await command('svg'); await artifact('decoder-cross.svg', exported.svg);
  if (args.includes('--transactions')) {
    await frame.evaluate(() => {
      const original = Worker.prototype.postMessage;
      window.frontierTestOriginalPost = original;
      Worker.prototype.postMessage = function (message, ...rest) {
        if (message?.task === 'frontier' && window.frontierTestHoldNext) {
          window.frontierTestHoldNext = false;
          window.frontierTestHeld = { worker: this, message };
          return;
        }
        return original.call(this, message, ...rest);
      };
    });
    const armRejectedTask = async (name, payload) => {
      await frame.evaluate(() => { window.frontierTestHeld = null; window.frontierTestHoldNext = true; });
      await page.evaluate(({ name, payload }) => {
        window.frontierTestResult = window.expansionCommand(name, payload).then(value => ({ ok: true, value }), error => ({ ok: false, error: error.message }));
      }, { name, payload });
      await frame.waitForFunction(() => !!window.frontierTestHeld, null, { timeout: 180000 });
      await page.waitForFunction(() => window.expansionMeta?.busy, null, { timeout: 180000 });
    };
    const rejectHeldTask = async () => {
      await frame.evaluate(() => {
        const held = window.frontierTestHeld;
        held.worker.dispatchEvent(new MessageEvent('message', { data: { requestId: held.message.requestId, ok: false, error: 'Injected frontier rejection for rollback regression' } }));
        window.frontierTestHeld = null;
      });
      const result = await page.evaluate(() => window.frontierTestResult);
      assert.equal(result.ok, false); assert.match(result.error, /Injected frontier rejection/);
      return snapshot();
    };
    const assertAtomicFailure = (before, after) => {
      assert.equal(sha(canonical(after.document.graph)), sha(canonical(before.document.graph)), 'rejected frontier must retain the complete graph');
      assert.equal(after.undo, before.undo); assert.equal(after.redo, before.redo); assert.equal(after.dirty, before.dirty);
      assert.deepEqual(after.selectedEdges, before.selectedEdges); assert.deepEqual(after.selectedNodes, before.selectedNodes);
    };
    await frame.locator('[data-edge-hit="binding-075-74"]').dispatchEvent('pointerdown', { button: 0, pointerId: 7, clientX: 0, clientY: 0 });
    await frame.waitForFunction(() => !!document.querySelector('#deleteEdge'));
    const beforeRace = await snapshot();
    await armRejectedTask('visual', { operations: [{ type: 'expand', id: 'enc.ffn', expanded: true }] });
    const heldDigest = await frame.evaluate(() => JSON.stringify(window.frontierTestHeld.message.graph));
    for (const id of ['releasePorts', 'clearBends', 'deleteEdge', 'setArrow']) await frame.locator('#' + id).dispatchEvent('click');
    assert.equal(await frame.evaluate(() => JSON.stringify(window.frontierTestHeld.message.graph)), heldDigest);
    assertAtomicFailure(beforeRace, await rejectHeldTask());
    mark('held frontier rejects native connection edits while busy and a worker failure restores graph, selection and history');

    // Retain a real redo entry, then ensure bridge all-expand/all-collapse
    // failures propagate rather than being reported as successful commands.
    await command('undo'); const withFuture = await snapshot(); assert.ok(withFuture.redo > 0);
    for (const name of ['expand-all', 'collapse-all']) {
      await armRejectedTask(name, {});
      assertAtomicFailure(withFuture, await rejectHeldTask());
      mark(name + ' propagates worker failure and preserves pending redo');
    }
    await command('redo');
    const restored = await snapshot(); assert.equal(visualDigest(restored), visualDigest(beforeRace));
    await frame.evaluate(() => { Worker.prototype.postMessage = window.frontierTestOriginalPost; });
    await command('fit');
    mark('successful native redo remains available after rejected frontier commands');
  }
  const customSteps = option('--steps', '').split(',').filter(Boolean);
  if (customSteps.length) {
    assert.equal(customSteps[0], 'dec.cross');
    for (const id of customSteps.slice(1)) await toggle(id);
  } else if (!args.includes('--cross-only') && !args.includes('--expand-all-only')) {
    await toggle('dec.ffn'); await toggle('dec.norm2'); await toggle('dec.self'); await toggle('dec.self.sdpa');
    if (phase !== 'baseline' || args.includes('--full')) {
      for (const id of ['dec.norm1', 'dec.norm3', 'enc.ffn', 'enc.norm1', 'enc.norm2', 'enc.self', 'enc.self.sdpa']) await toggle(id);
      const fullyExpanded = await snapshot(), stateDigest = sha([...fullyExpanded.document.graph.recursive.state.open].sort());
      await toggle('dec.cross', false); await toggle('dec.cross', true);
      assert.equal(sha([...(await snapshot()).document.graph.recursive.state.open].sort()), stateDigest);
      const beforeParentFold = await snapshot(), descendant = beforeParentFold.document.graph.nodes.find(node => node.id === 'dec.self.sdpa');
      assert.equal(descendant.expanded, true);
      await toggle('dec.self', false);
      const parentFolded = await snapshot();
      assert.ok(!parentFolded.document.graph.nodes.some(node => node.id === 'dec.self.sdpa'));
      await toggle('dec.self', true);
      const parentRestored = await snapshot();
      assert.equal(parentRestored.document.graph.nodes.find(node => node.id === 'dec.self.sdpa')?.expanded, true);
      assert.equal(sha([...parentRestored.document.graph.recursive.state.open].sort()), stateDigest);
      mark('mixed-depth expansion and parent collapse/reopen retain expanded SDPA descendants and source authority');

      const beforeUndo = await snapshot();
      await page.getByRole('button', { name: '撤销 Ctrl+Z', exact: true }).click();
      await page.waitForFunction(undo => window.expansionMeta?.undo === undo - 1 && !window.expansionMeta.busy, beforeUndo.undo, { timeout: 180000 });
      const undone = await snapshot();
      assert.equal(visualDigest(undone), visualDigest(parentFolded));
      assert.equal(sha(undone.document.graph.recursive.authority), sourceSha);
      await command('visual', { operations: [{ type: 'expand', id: 'dec.self', expanded: false }] });
      const noop = await snapshot();
      assert.equal(noop.undo, undone.undo); assert.equal(noop.redo, undone.redo);
      assert.equal(visualDigest(noop), visualDigest(undone));
      await page.getByRole('button', { name: '重做 Ctrl+Shift+Z', exact: true }).click();
      await page.waitForFunction(undo => window.expansionMeta?.undo === undo && !window.expansionMeta.busy, beforeUndo.undo, { timeout: 180000 });
      const redone = await snapshot();
      assert.equal(visualDigest(redone), visualDigest(beforeUndo));
      assert.equal(sha(redone.document.graph.recursive.authority), sourceSha);
      const redoneCheck = await checkGraph(redone);
      assert.equal(redoneCheck.source.ok, true); assert.equal(redoneCheck.layout.ok, true);
      if (!args.includes('--diagnostic-contacts')) assert.deepEqual(redoneCheck.routing.contacts, []);
      assert.deepEqual(redoneCheck.failedEdges, []);
      mark('native toolbar undo/redo restores exact expanded geometry and an unchanged frontier preserves redo');
    }
  }
  }
  await command('fit');
  await page.screenshot({ path: path.join(evidence, 'final-full.png'), fullPage: true });
  const final = await snapshot();
  await artifact('final.json', final.document);
  await artifact('final.svg', (await command('svg')).svg);
  assert.deepEqual(errors, []); mark('no browser runtime errors during expansion');
  const servedFiles = [...new Set(assets), 'app.js', 'recursive-graph.js', 'router.js', 'routing-worker.js', 'frontier-task.js', 'studio-bridge.js', 'semantic-constraints.js', 'graph-engine.js', 'physical-ports.js', 'source-contracts.js'].map(value => value.startsWith('http') ? value : base + '/preview/yworks_edge_router_lab/' + value);
  const servedAssets = [];
  for (const url of servedFiles) {
    const response = await context.request.get(url);
    assert.equal(response.status(), 200, url);
    const bytes = await response.body();
    servedAssets.push({ url, status: response.status(), bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') });
  }
  await fs.writeFile(path.join(evidence, 'report.json'), JSON.stringify({ phase, base, noWorker: args.includes('--no-worker'), sharedTrunksOnly: args.includes('--shared-trunks-only'), diagnosticContacts: args.includes('--diagnostic-contacts'), checks, errors, steps, assets, servedAssets, finalMetrics: await readMetrics(), finalValidation: await checkGraph(final) }, null, 2) + '\n');
  console.log('Evidence: ' + evidence);
} catch (error) {
  await fs.writeFile(path.join(evidence, 'failure.json'), JSON.stringify({ error: error.stack, steps, errors, assets }, null, 2) + '\n');
  if (latestState?.document) await artifact('failure-state.json', latestState.document);
  await page.screenshot({ path: path.join(evidence, 'failure.png'), fullPage: true }).catch(() => {});
  throw error;
} finally { await context.close(); await browser.close(); }
