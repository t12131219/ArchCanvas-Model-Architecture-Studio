import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { gzipSync } from 'node:zlib';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Read-only comparison of real Studio frontiers with the original reference.
// The contexts are disposable; no model Python source is imported or executed.
const args = process.argv.slice(2), option = (key, fallback) => args.includes(key) ? args[args.indexOf(key) + 1] : fallback;
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const base = option('--base', 'http://127.0.0.1:8891').replace(/\/$/, ''), caseId = option('--case', '0342f4170c15ba8e');
const customSteps = option('--steps', '').split(',').filter(Boolean), closeupNodes = option('--closeups', 'vae.encoder,vae.posterior,vae.sampling').split(',').filter(Boolean);
const closeupEdges = option('--edge-closeups', '').split(',').filter(Boolean);
const collapseAfterInitial = args.includes('--collapse-after-initial');
const output = path.resolve(option('--output-dir', path.join(root, 'docs/evidence/preview-vae-layout-20261014/baseline')));
const prototypePath = path.resolve(root, '../prototype/Summary_Merge/data/cases/' + caseId + '-detailed.json');
const reference = JSON.parse(await fs.readFile(prototypePath, 'utf8'));
const sha = value => createHash('sha256').update(value).digest('hex');
await fs.mkdir(output, { recursive: true });
const { chromium } = await import(pathToFileURL(option('--playwright', '/home/fzg/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs')).href);
const browser = await chromium.launch({ headless: true, executablePath: option('--chromium', '/home/fzg/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome'), args: ['--no-sandbox'] });
const bundleUrls = new Set();
const report = { base, caseId, reference: { path: prototypePath, sha256: sha(await fs.readFile(prototypePath)) }, stages: [], transitions: [], errors: [], assets: [] };
async function artifact(name, value) {
  const bytes = Buffer.from(typeof value === 'string' ? value : JSON.stringify(value, null, 2) + '\n');
  if (bytes.length > 1024 * 1024) { await fs.writeFile(path.join(output, name + '.gz'), gzipSync(bytes, { mtime: 0 })); return name + '.gz'; }
  await fs.writeFile(path.join(output, name), bytes); return name;
}
async function setup() {
  const context = await browser.newContext({ viewport: { width: 1780, height: 1400 } });
  await context.addInitScript(() => {
    window.vaeState = null;
    window.addEventListener('message', event => { if (event.origin === location.origin && event.data?.document?.graph) window.vaeState = { caseId: event.data.document.caseId, busy: event.data.busy }; });
    window.vaeCommand = (name, payload = {}) => new Promise((resolve, reject) => {
      const frame = document.querySelector('iframe'), requestId = crypto.randomUUID();
      const timeout = setTimeout(() => { window.removeEventListener('message', receive); reject(Error(name + ' timed out')); }, 180000);
      function receive(event) {
        if (event.origin !== location.origin || event.source !== frame?.contentWindow || event.data?.requestId !== requestId) return;
        clearTimeout(timeout); window.removeEventListener('message', receive);
        event.data.type.endsWith(':error') ? reject(Error(event.data.message)) : resolve(event.data);
      }
      window.addEventListener('message', receive); frame.contentWindow.postMessage({ type: 'archcanvas:preview:' + name, requestId, ...payload }, location.origin);
    });
  });
  const page = await context.newPage(); page.on('pageerror', error => report.errors.push(error.message));
  page.on('response', response => { if (/\/assets\/[^/]+\.js$/.test(response.url())) bundleUrls.add(response.url()); });
  await page.goto(base + '/'); await page.waitForFunction(() => window.vaeState && !window.vaeState.busy, null, { timeout: 180000 });
  const frame = page.frame({ url: /preview\/yworks_edge_router_lab\/index.html/ }); assert.ok(frame);
  const command = (name, payload) => page.evaluate(({ name, payload }) => window.vaeCommand(name, payload), { name, payload });
  const menu = page.locator('.studio .workspace-menu'); await menu.locator('summary').click(); await page.getByRole('button', { name: '示例与模块库', exact: true }).click();
  await frame.locator('#search').fill(''); await frame.locator('#collection').selectOption('all');
  await frame.locator(`button[data-case-id="${caseId}"]`).click(); await page.waitForFunction(id => window.vaeState?.caseId === id && !window.vaeState.busy, caseId, { timeout: 180000 });
  await frame.locator('.library .studio-drawer-close').click(); if (await menu.getAttribute('open') !== null) await menu.locator('summary').click();
  return { context, page, frame, command };
}
async function capture(env, name) {
  await env.command('fit'); const state = await env.command('snapshot'), graph = state.document.graph;
  const validation = await env.frame.evaluate(graph => window.SummaryEngine.validateView(graph), graph);
  const metrics = await env.frame.evaluate(({ graph, reference }) => {
    const R = window.EdgeRouterLabRouting;
    const wire = edge => {
      let value = edge.contract?.wire ?? edge.binding?.wire_identity ?? edge.binding?.src ?? edge.source;
      if (typeof value === 'string') try { value = JSON.parse(value); } catch { const i = value.lastIndexOf(':'); if (i >= 0) value = [value.slice(0, i), value.slice(i + 1)]; }
      return JSON.stringify(value);
    };
    function measure(g) {
      const nodes = new Map(g.nodes.map(n => [n.id, n]));
      const top = id => { let n = nodes.get(id); while (n?.parent) n = nodes.get(n.parent); return n; };
      const bounds = points => ({ left: Math.min(...points.map(p => p.x)), right: Math.max(...points.map(p => p.x)), top: Math.min(...points.map(p => p.y)), bottom: Math.max(...points.map(p => p.y)) });
      const edges = g.edges.map(e => {
        const route = R.simplify(e.route), start = route[0], end = route.at(-1), b = bounds(route);
        const length = route.slice(1).reduce((sum, p, i) => sum + R.dist(route[i], p), 0), direct = Math.abs(start.x - end.x) + Math.abs(start.y - end.y);
        const a = top(e.source), z = top(e.target), owner = a?.id === z?.id ? a : null;
        return { id: e.id, source: e.source, target: e.target, wire: wire(e), length, direct, excess: length - direct, ratio: direct ? length / direct : null, points: e.route.length, simplifiedPoints: route.length, bends: Math.max(0, route.length - 2), bounds: b,
          owner: owner?.id ?? null, outsideOwner: owner ? { left: Math.max(0, owner.x - b.left), right: Math.max(0, b.right - owner.x - owner.w), top: Math.max(0, owner.y - b.top), bottom: Math.max(0, b.bottom - owner.y - owner.h) } : null };
      });
      const crossings = [], overlapPairs = [], nearParallelPairs = [];
      for (let i = 0; i < g.edges.length; i++) for (let j = i + 1; j < g.edges.length; j++) {
        const a = g.edges[i], b = g.edges[j]; if (wire(a) === wire(b)) continue;
        let overlap = 0;
        for (let u = 1; u < a.route.length; u++) for (let v = 1; v < b.route.length; v++) {
          if (R.crossing(a.route[u - 1], a.route[u], b.route[v - 1], b.route[v])) crossings.push({ a: a.id, b: b.id, segments: [u, v] });
          overlap += R.overlap(a.route[u - 1], a.route[u], b.route[v - 1], b.route[v]);
          const p = a.route[u - 1], q = a.route[u], r = b.route[v - 1], s = b.route[v];
          const vertical = Math.abs(p.x - q.x) < .00001 && Math.abs(r.x - s.x) < .00001;
          const horizontal = Math.abs(p.y - q.y) < .00001 && Math.abs(r.y - s.y) < .00001;
          if (vertical || horizontal) {
            const axis = vertical ? 'y' : 'x', normal = vertical ? 'x' : 'y', separation = Math.abs(p[normal] - r[normal]);
            const span = Math.min(Math.max(p[axis], q[axis]), Math.max(r[axis], s[axis])) - Math.max(Math.min(p[axis], q[axis]), Math.min(r[axis], s[axis]));
            if (separation > .00001 && separation < 8 && span > 10) nearParallelPairs.push({ a: a.id, b: b.id, segments: [u, v], direction: vertical ? 'vertical' : 'horizontal', separation, commonSpan: span });
          }
        }
        if (overlap > .00001) overlapPairs.push({ a: a.id, b: b.id, length: overlap });
      }
      const main = nodes.get('vae.root') || g.nodes.filter(n => !n.parent && n.expanded).sort((a, b) => b.w * b.h - a.w * a.h)[0], epsilon = nodes.get('vae.epsilon');
      return { canvas: g.canvas, nodes: g.nodes.length, edges: g.edges.length, builtInStats: R.stats(g.edges), totalLength: edges.reduce((s, e) => s + e.length, 0), totalBends: edges.reduce((s, e) => s + e.bends, 0), unrelatedCrossingCount: crossings.length, unrelatedCrossings: crossings, unrelatedOverlaps: overlapPairs, nearParallelPairs,
        root: main && { x: main.x, y: main.y, w: main.w, h: main.h }, epsilon: epsilon && { x: epsilon.x, y: epsilon.y, w: epsilon.w, h: epsilon.h, side: !main ? null : epsilon.x >= main.x + main.w ? 'right' : epsilon.x + epsilon.w <= main.x ? 'left' : 'intersecting-horizontal-span' },
        nodePositions: g.nodes.map(n => ({ id: n.id, parent: n.parent ?? null, x: n.x, y: n.y, w: n.w, h: n.h, expanded: !!n.expanded, relativeRoot: main ? { x: n.x - main.x, y: n.y - main.y } : null })), edgeMetrics: edges.sort((a, b) => b.excess - a.excess), outsideRootEdges: edges.filter(e => e.outsideOwner && Object.values(e.outsideOwner).some(v => v > .00001)) };
    }
    return { studio: measure(graph), prototype: measure(reference) };
  }, { graph, reference });
  await env.frame.locator('#toast.visible').waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
  await env.page.screenshot({ path: path.join(output, name + '.png'), fullPage: true });
  const document = await artifact(name + '.json', state.document), svg = await env.command('svg'); await artifact(name + '.svg', svg.svg || svg.xml);
  const closeups = await captureCloseups(env, graph, name);
  const stage = { name, document, closeups, sourceAuthoritySha256: sha(JSON.stringify(graph.recursive.authority)), expanded: graph.nodes.filter(n => n.expanded).map(n => n.id), validation, ...metrics }; report.stages.push(stage);
  assert.equal(stage.sourceAuthoritySha256, report.stages[0].sourceAuthoritySha256);
  await artifact('report.json', report); console.log(name + ' ' + JSON.stringify({ nodes: metrics.studio.nodes, edges: metrics.studio.edges, root: metrics.studio.root, epsilon: metrics.studio.epsilon, length: metrics.studio.totalLength, bends: metrics.studio.totalBends, crossings: metrics.studio.unrelatedCrossingCount, outside: metrics.studio.outsideRootEdges.length }));
}
async function captureCloseups(env, graph, name) {
  const closeups = [], locator = env.frame.locator('#graph'), box = await locator.boundingBox(); assert.ok(box);
  const oldViewBox = await locator.getAttribute('viewBox');
  try {
    for (const id of closeupNodes) {
      const node = graph.nodes.find(n => n.id === id && n.expanded); if (!node) continue;
      const region = { x: node.x + node.w - 235, y: node.y - 30, w: Math.min(500, box.width), h: Math.min(node.h + 60, 760, box.height) };
      // Temporary display-only viewport in this disposable context. It renders
      // the actual scene at one CSS pixel per graph unit and does not update
      // graph geometry, native camera state, selection, persistence or history.
      await locator.evaluate((element, region) => element.setAttribute('viewBox', `${region.x} ${region.y} ${element.clientWidth} ${element.clientHeight}`), region);
      const screenshot = name + '-' + id.replace(/^vae\./, '') + '-right-1x.png';
      await env.page.screenshot({ path: path.join(output, screenshot), clip: { x: box.x, y: box.y, width: region.w, height: region.h } });
      closeups.push({ screenshot, nodeId: id, region, graphUnitsPerCssPixel: 1 });
    }
    for (const id of closeupEdges) {
      const edge = graph.edges.find(e => e.id === id); if (!edge) continue;
      const terminal = edge.route.at(-1), region = { x: terminal.x - 250, y: terminal.y - 180, w: Math.min(500, box.width), h: Math.min(360, box.height) };
      await locator.evaluate((element, region) => element.setAttribute('viewBox', `${region.x} ${region.y} ${element.clientWidth} ${element.clientHeight}`), region);
      const screenshot = name + '-' + id + '-target-1x.png';
      await env.page.screenshot({ path: path.join(output, screenshot), clip: { x: box.x, y: box.y, width: region.w, height: region.h } });
      closeups.push({ screenshot, edgeId: id, region, graphUnitsPerCssPixel: 1 });
    }
  } finally { await locator.evaluate((element, oldViewBox) => element.setAttribute('viewBox', oldViewBox), oldViewBox); }
  return closeups;
}
async function transition(env, name, payload = {}) {
  const started = performance.now();
  const result = await env.command(name, payload);
  const timing = { command: name, ...payload, elapsedMs: Math.round((performance.now() - started) * 100) / 100,
    measurement: 'Same-origin bridge command dispatch to completed response; excludes subsequent fit, graph snapshot, validation and screenshot.' };
  report.transitions.push(timing); console.log('transition ' + JSON.stringify(timing));
  return result;
}
try {
  if (customSteps.length || collapseAfterInitial) {
    const custom = await setup();
    try {
      await capture(custom, 'initial');
      if (customSteps.length) {
        for (const nodeId of customSteps) await transition(custom, 'set-frontier', { nodeId, expanded: true });
        await capture(custom, 'mixed-target');
      }
      if (collapseAfterInitial) {
        await transition(custom, 'collapse-all');
        await capture(custom, 'all-collapse');
      }
    } finally { await custom.context.close(); }
  } else {
  const mixed = await setup();
  try {
    await capture(mixed, 'overview');
    await transition(mixed, 'set-frontier', { nodeId: 'vae.forward', expanded: true }); await transition(mixed, 'set-frontier', { nodeId: 'vae.encoder', expanded: true });
    await capture(mixed, 'mixed-encoder');
    for (const nodeId of ['vae.sampling', 'vae.sample_operands', 'vae.scaled_noise']) await transition(mixed, 'set-frontier', { nodeId, expanded: true });
    await capture(mixed, 'mixed-scaled-noise');
    await transition(mixed, 'expand-all'); await capture(mixed, 'full-after-mixed');
  } finally { await mixed.context.close(); }
  const direct = await setup();
  try { await transition(direct, 'expand-all'); await capture(direct, 'full-direct'); }
  finally { await direct.context.close(); }
  }
  const context = await browser.newContext();
  for (const name of [...bundleUrls, 'app.js', 'recursive-graph.js', 'semantic-constraints.js', 'router.js', 'routing-worker.js', 'graph-engine.js', 'frontier-task.js', 'studio-bridge.js', 'physical-ports.js', 'source-contracts.js']) {
    const url = name.startsWith('http') ? name : base + '/preview/yworks_edge_router_lab/' + name, response = await context.request.get(url), bytes = await response.body();
    assert.equal(response.status(), 200, url);
    report.assets.push({ url, status: response.status(), bytes: bytes.length, sha256: sha(bytes) });
  }
  await context.close(); await artifact('report.json', report);
} finally { await browser.close(); }
console.log('Evidence: ' + output);
