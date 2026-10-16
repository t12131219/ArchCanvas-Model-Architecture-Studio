import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

class SvgElement {
  tagName: string; attributes = new Map<string, string>(); children: SvgElement[] = []; textContent = '';
  constructor(tag: string) { this.tagName = tag; }
  setAttribute(name: string, value: unknown) { this.attributes.set(name, String(value)); }
  getAttribute(name: string) { return this.attributes.get(name) ?? null; }
  append(...children: SvgElement[]) { this.children.push(...children); }
  insertBefore(child: SvgElement, before: SvgElement | null) { const index = before ? this.children.indexOf(before) : -1; this.children.splice(index < 0 ? this.children.length : index, 0, child); }
  replaceChildren(...children: SvgElement[]) { this.children = children; }
  querySelectorAll(selector: string): SvgElement[] {
    const match = (item: SvgElement) => selector.startsWith('#') ? item.getAttribute('id') === selector.slice(1)
      : selector.startsWith('[') ? (() => { const [, name, value] = /^\[([^=\]]+)(?:="([^"]*)")?\]$/.exec(selector)!; return item.attributes.has(name) && (value === undefined || item.getAttribute(name) === value); })()
      : item.tagName === selector;
    return this.children.flatMap(child => [...(match(child) ? [child] : []), ...child.querySelectorAll(selector)]);
  }
  querySelector(selector: string): SvgElement | null { return this.querySelectorAll(selector)[0] ?? null; }
}
const plain = (value: any) => JSON.parse(JSON.stringify(value));
function runtime() {
  let response: any;
  const context = vm.createContext({ performance, document: { createElementNS: (_: string, tag: string) => new SvgElement(tag) }, postMessage: (value: any) => { response = plain(value); } });
  context.self = context;
  context.importScripts = (...files: string[]) => files.forEach(file => vm.runInContext(readFileSync(new URL('../public/preview/yworks_edge_router_lab/' + file, import.meta.url), 'utf8'), context, { filename: file }));
  vm.runInContext(readFileSync(new URL('../public/preview/yworks_edge_router_lab/routing-worker.js', import.meta.url), 'utf8'), context);
  return { context, S: context.SummarySourceControls, E: context.SummaryEngine, R: context.EdgeRouterLabRouting, response: () => response };
}
function fixture() {
  const semantic = (sourceKind: string, label: string) => ({ sourceStructure: true, sourceKind, label, source_evidence: ['if-evidence'] });
  return { canvas: [1300, 1000], edges: [], nodes: [
    { id: 'root', x: 20, y: 20, w: 1100, h: 800, expanded: true, routingObstacle: false, labelObstacles: [{ x: 12, y: 8, w: 180, h: 48 }] },
    { id: 'if', parent: 'root', x: 60, y: 80, w: 800, h: 550, expanded: true, routingObstacle: false, labelObstacles: [{ x: 12, y: 8, w: 200, h: 48 }, { x: 72, y: 72, w: 16, h: 16 }], semantic: semantic('SourceConditional', 'if test is not None'), sourceControlPresentation: { schema: 'source-condition-presentation/1', anchor: { x: 80, y: 80 }, obstacle: { x: 72, y: 72, w: 16, h: 16 } } },
    { id: 'yes', parent: 'if', x: 96, y: 204, w: 330, h: 300, expanded: false, routingObstacle: true, labelObstacles: [], semantic: semantic('SourceBranch', 'if test is not None') },
    { id: 'no', parent: 'if', x: 482, y: 204, w: 330, h: 300, expanded: false, routingObstacle: true, labelObstacles: [], semantic: semantic('SourceBranch', 'else') },
  ] } as any;
}
function stackedFixture() {
  const graph = fixture(); graph.canvas = [1500, 1700];
  Object.assign(graph.nodes[0], { w: 1400, h: 1600 });
  Object.assign(graph.nodes[1], { w: 1272, h: 1340 });
  Object.assign(graph.nodes[2], { w: 1200, h: 684, expanded: true, routingObstacle: false,
    labelObstacles: [{ x: 12, y: 8, w: 224, h: 48 }] });
  Object.assign(graph.nodes[3], { x: 495, y: 942, w: 402, h: 436, expanded: true, routingObstacle: false,
    labelObstacles: [{ x: 12, y: 8, w: 142, h: 48 }] });
  graph.nodes.push(
    { id: 'yes-child', parent: 'yes', x: 132, y: 280, w: 270, h: 70, expanded: false, routingObstacle: true },
    { id: 'no-child', parent: 'no', x: 581, y: 1018, w: 230, h: 70, expanded: false, routingObstacle: true });
  return graph;
}
function svg() { const node = new SvgElement('svg'), nodes = new SvgElement('g'); nodes.setAttribute('id', 'nodeLayer'); node.append(nodes); return node; }
function authority(graph: any) { return JSON.stringify([graph.nodes, graph.edges, graph.semanticBaseline, graph.recursive]); }
const overlap = (a: any, b: any) => Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x) > 1e-5 && Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) > 1e-5;

test('conditional presentation proves direct source containment and preserves canonical records', () => {
  const { S, R } = runtime(), graph = fixture(), before = authority(graph), value = S.refresh(graph);
  assert.equal(authority(graph), before); assert.equal(value.controls.length, 2); assert.deepEqual(plain(value.diagnostics), []);
  assert.deepEqual(plain(value.controls.map((c: any) => [c.owner, c.target, c.outcome, c.role])), [['if', 'yes', true, 'source-control'], ['if', 'no', false, 'source-control']]);
  assert.equal(graph.edges.length, 0);
  for (const control of value.controls) {
    assert.equal(control.geometryValidated, true);
    const owner = graph.nodes.find((node: any) => node.id === control.owner), target = graph.nodes.find((node: any) => node.id === control.target);
    assert.deepEqual(plain(control.points.at(-1)), { x: target.x + target.w / 2, y: target.y });
    assert.ok(control.points.every((p: any) => p.x >= owner.x && p.x <= owner.x + owner.w && p.y >= owner.y && p.y <= owner.y + owner.h));
    for (const box of graph.nodes.flatMap((n: any) => n.expanded ? n.labelObstacles.map((b: any) => ({ ...b, x: n.x + b.x, y: n.y + b.y })) : [n])) assert.equal(overlap(control.labelBox, box), false);
    for (const obstacle of graph.nodes.filter((n: any) => !n.expanded && n.id !== control.target)) for (let i = 1; i < control.points.length; i++) assert.equal(R.intersectsRect(control.points[i - 1], control.points[i], obstacle), false);
  }
});

test('mismatched evidence, indirect descendants, ordinary modules and folded conditions never create associations', () => {
  const { S } = runtime(), graph = fixture(); graph.nodes[2].semantic.source_evidence = ['different-if']; graph.nodes[3].parent = 'yes';
  graph.nodes.push({ ...plain(graph.nodes[2]), id: 'not-a-branch', semantic: { ...graph.nodes[2].semantic, sourceKind: 'SourceCode', source_evidence: ['if-evidence'] } });
  assert.equal(S.refresh(graph).controls.length, 0);
  const folded = fixture(); folded.nodes[1].expanded = false; assert.equal(S.refresh(folded).controls.length, 0);
  const ordinary = fixture(); ordinary.nodes[1].semantic.sourceStructure = false; assert.equal(S.refresh(ordinary).controls.length, 0);
});

test('nested and independently expanded branches only receive arrows from their own condition', () => {
  const { S } = runtime(), graph = fixture(); graph.nodes[2].expanded = true; graph.nodes[2].routingObstacle = false;
  const nested = plain(graph.nodes.slice(1));
  for (const n of nested) { n.id = 'nested-' + n.id; n.parent = n.id === 'nested-if' ? 'yes' : 'nested-if'; n.x += 160; n.y += 400; }
  graph.nodes[2].w = 1000; graph.nodes[2].h = 1100; graph.nodes[3].x += 1100; graph.nodes[1].w = 2000; graph.nodes[1].h = 1600; graph.nodes[0].w = 2200; graph.nodes[0].h = 1800; graph.canvas = [2400, 2000]; graph.nodes.push(...nested);
  const value = S.refresh(graph); assert.equal(value.controls.length, 4);
  assert.ok(value.controls.every((c: any) => graph.nodes.find((n: any) => n.id === c.target).parent === c.owner));
  assert.ok(value.controls.every((c: any) => c.owner === 'if' || c.owner === 'nested-if'));
});

test('vertically stacked expanded branches retain safe controls outside the earlier arm', () => {
  const { S, E, context, response } = runtime(), graph = stackedFixture(), before = authority(graph);
  const original = E.routeOne;
  // Exercise the bounded recovery when the normal search has exhausted its
  // candidates. Every replacement still passes the real geometry validator.
  E.routeOne = (...args: any[]) => args[1].target === 'no' ? { ok: false } : original(...args);
  const controls = S.refresh(graph);
  assert.equal(controls.controls.length, 2); assert.deepEqual(plain(controls.diagnostics), []);
  assert.equal(authority(graph), before); assert.equal(graph.edges.length, 0);
  const otherwise = controls.controls.find((item: any) => item.target === 'no');
  assert.ok(otherwise.points.some((point: any) => point.x < graph.nodes[2].x || point.x > graph.nodes[2].x + graph.nodes[2].w));
  assert.ok(otherwise.points.every((point: any) => point.x > graph.nodes[1].x && point.x < graph.nodes[1].x + graph.nodes[1].w));
  const worker = plain(graph); delete worker.sourceControls;
  context.onmessage({ data: { requestId: 25, task: 'validate', graph: worker, options: {} } });
  assert.equal(response().ok, true);
  assert.deepEqual(response().graph.sourceControls, plain(controls));
});

test('a canonical tensor entering the branch centre keeps its own lane and syntax selects another top slot', () => {
  const { S, E, context, response } = runtime(), graph = stackedFixture();
  graph.nodes.push({ id: 'feed', parent: 'if', x: 1200, y: 898, w: 60, h: 24, expanded: false, routingObstacle: true });
  graph.edges.push({ id: 'canonical-input', source: 'feed', target: 'no-child', style: 'orthogonal', arrow: 'filled',
    fixedSource: { side: 'bottom', fraction: .5 }, fixedTarget: { side: 'top', fraction: .5 },
    binding: { src: 'feed:out', dst: 'no-child:in' },
    route: [{ x: 1230, y: 922 }, { x: 1230, y: 930 }, { x: 696, y: 930 }, { x: 696, y: 1018 }], waypoints: [] });
  context.SummaryConstraints.initialize(graph);
  assert.equal(E.validateView(graph).layout.ok, true);
  const before = authority(graph), controls = S.refresh(graph);
  assert.equal(controls.controls.length, 2); assert.deepEqual(plain(controls.diagnostics), []);
  const otherwise = controls.controls.find((item: any) => item.target === 'no');
  assert.notEqual(otherwise.points.at(-1).x, 696);
  assert.equal(otherwise.points.at(-1).y, graph.nodes[3].y);
  assert.equal(authority(graph), before); assert.equal(graph.edges.length, 1);
  context.onmessage({ data: { requestId: 26, task: 'validate', graph: plain(graph), options: {} } });
  assert.equal(response().ok, true); assert.deepEqual(response().graph.sourceControls, plain(controls));
});

test('geometry, actual routes and labels invalidate cached controls while render and legend never route', () => {
  const { S, E } = runtime(), graph = fixture(), out = svg(); S.refresh(graph);
  let routed = 0; const original = E.routeOne; E.routeOne = (...args: any[]) => { routed++; return original(...args); };
  S.render(graph, out); S.render(graph, out); S.legendRows(graph); assert.equal(routed, 0);
  assert.equal(out.querySelectorAll('[data-role="source-control"]').length, 2);
  graph.nodes[2].x += 20; assert.equal(S.ensure(graph).controls.length, 0); S.render(graph, out); assert.equal(out.querySelectorAll('[data-role="source-control"]').length, 0);
  S.refresh(graph); assert.ok(routed > 0); const count = routed; S.render(graph, out); S.legendRows(graph); assert.equal(routed, count);
  graph.studioPresentation = { annotations: { note: { id: 'note', x: 200, y: 180, text: 'condition note', width: 160 } } }; assert.equal(S.ensure(graph).controls.length, 0);
  const sig = S.signature(graph); graph.edges.push({ id: 'actual-route', source: 'root', target: 'yes', route: [{ x: 22, y: 22 }, { x: 23, y: 23 }] }); assert.notEqual(S.signature(graph), sig); assert.equal(S.ensure(graph).controls.length, 0);
});

test('blocked routing omits unsafe arrows and exposes a diagnostic without crossing the container', () => {
  const { S } = runtime(), graph = fixture(); graph.nodes.push({ id: 'blocker', parent: 'if', x: 65, y: 168, w: 790, h: 33, expanded: false, routingObstacle: true });
  const value = S.refresh(graph), out = svg(); assert.equal(value.controls.length, 0); assert.equal(value.diagnostics.length, 2); assert.equal(graph.edges.length, 0); S.render(graph, out);
  assert.equal(out.querySelectorAll('[data-role="source-control"]').length, 0); assert.equal(out.querySelectorAll('[data-source-control-diagnostic]').length, 1); assert.match(out.querySelector('title')!.textContent, /没有合法/);
});

test('serialized forged control results are replaced by the worker and match the fallback', () => {
  const { S, context, response } = runtime(), graph = fixture(); graph.sourceControls = { version: 1, signature: S.signature(graph), controls: [{ id: 'forged', owner: 'yes', target: 'no' }] };
  context.onmessage({ data: { requestId: 17, task: 'validate', graph, options: {} } }); const result = response(); assert.equal(result.ok, true); assert.equal(result.validation.layout.ok, true);
  assert.equal(result.graph.sourceControls.controls.length, 2); assert.ok(result.graph.sourceControls.controls.every((c: any) => c.owner === 'if'));
  assert.deepEqual(plain(S.refresh(fixture())), result.graph.sourceControls);
});

test('actual saved-case loader commits the worker-refreshed control graph when no geometry upgrade is needed', async () => {
  const { S, context, response } = runtime(), F = context.SummaryRecursive;
  const sources = { overview: fixture(), detailed: fixture() }, saved = F.build(F.create(sources));
  saved.sourceControls = { version: 1, controls: [], decisions: [], diagnostics: [] };
  const canonical = JSON.stringify([saved.nodes, saved.edges]), caseItem = { id: 'saved-condition', title: 'Saved condition',
    collection: 'source_adapter', origin: 'model:Model', views: [{ key: 'overview' }] };
  let request = 30, validations = 0, published: any;
  Object.assign(context, {
    E: context.SummaryEngine, C: context.SummaryConstraints, F, busy: false, drag: null, loadToken: 0,
    sessions: new Map(), catalogSources: null, importedPackages: new Map(), names: {}, graph: null, studioBridge: null,
    selectedNodes: new Set(), selectedEdges: new Set(), URL, location: { href: 'http://127.0.0.1/preview/' },
    window: { history: { replaceState() {} } },
    $: () => ({ value: '', checked: false, innerHTML: '', textContent: '' }),
    flushPersist() {}, render() {}, syncUnifiedState() {}, renderCatalog() {}, fit() {}, persist() {}, toast() {}, esc: (v: unknown) => String(v),
    caseSources: async () => sources,
    invalidSourceRoutes: (_graph: any, validation: any) => validation.edges.some(([, value]: any) => !value.ok),
    runGraphTask: async (message: any) => {
      context.onmessage({ data: { ...plain(message), requestId: ++request } });
      const result = response(); if (message.task === 'validate') { validations++; published = result.graph; }
      return result;
    },
  });
  const app = readFileSync(new URL('../public/preview/yworks_edge_router_lab/app.js', import.meta.url), 'utf8');
  const start = app.indexOf('  async function openCase('), end = app.indexOf('  function cameraUpdate(', start);
  assert.ok(start >= 0 && end > start);
  vm.runInContext(app.slice(start, end) + '\nglobalThis.loadSavedCase=openCase;', context, { filename: 'app.js:openCase' });
  assert.equal(await context.loadSavedCase(caseItem, caseItem.views[0], { graph: saved, history: [], future: [], dirty: true }), true);
  assert.equal(validations, 1, 'current geometry uses validation without an extra layout transaction');
  assert.equal(context.graph, published, 'publish the actual validated worker graph, including refreshed overlays');
  assert.equal(S.ensure(context.graph).controls.length, 2); assert.deepEqual(plain(S.ensure(context.graph).diagnostics), []);
  assert.equal(JSON.stringify([context.graph.nodes, context.graph.edges]), canonical);
});

test('monochrome retains non-tensor dash grammar, export scopes and a single control legend row', () => {
  const { S } = runtime(), graph = fixture(), out = svg(); S.refresh(graph); S.render(graph, out); const original = plain(graph.sourceControls);
  graph.studioPresentation = { page: { preset: 'monochrome' } }; S.render(graph, out); assert.deepEqual(plain(graph.sourceControls), original);
  const controls = out.querySelectorAll('[data-role="source-control"]'); assert.equal(controls.length, 2);
  for (const c of controls) { assert.equal(c.getAttribute('data-source-control-owner'), 'if'); assert.ok(['yes', 'no'].includes(c.getAttribute('data-source-control-target')!)); assert.equal(c.querySelector('path')!.getAttribute('stroke'), '#4b5563'); assert.equal(c.querySelector('path')!.getAttribute('stroke-dasharray'), '4 4'); assert.match(c.querySelector('title')!.textContent, /非张量/); }
  assert.equal(out.querySelectorAll('[data-source-control-decision]')[0].getAttribute('data-source-control-owner'), 'if'); assert.deepEqual(plain(S.legendRows(graph)), [{ label: '条件分支 · 非张量', stroke: '#8a6a46', dashArray: '4 4' }]);
});

test('owner-following attachments and movable notes reserve real painted bounds', () => {
  for (const type of ['attachment', 'annotation']) {
    const { S } = runtime(), graph = fixture();
    if (type === 'attachment') {
      graph.nodes[0].base = [20, 20];
      graph.attachments = [{ id: 'owner-caption', owner: 'root', bbox: [65, 168, 790, 33] }];
    } else graph.studioPresentation = { annotations: { note: { id: 'note', x: 70, y: 185, width: 790, text: 'reserved note' } } };
    const before = authority(graph), blocked = S.refresh(graph);
    assert.equal(blocked.controls.length, 0, type + ' must block the narrow reserved lane');
    assert.equal(blocked.diagnostics.length, 2); assert.equal(authority(graph), before);
    if (type === 'attachment') graph.attachments[0].bbox[1] = 700;
    else graph.studioPresentation.annotations.note.y = 700;
    assert.equal(S.ensure(graph).controls.length, 0, 'moving text invalidates cached controls');
    const clear = S.refresh(graph); assert.equal(clear.controls.length, 2); assert.equal(clear.diagnostics.length, 0);
  }
});
