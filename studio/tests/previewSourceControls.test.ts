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
