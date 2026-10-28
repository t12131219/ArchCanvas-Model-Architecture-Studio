import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { isPreviewSourceDependency, previewAnnotationConflicts, previewEdgeAppearance } from '../src/previewPresentation.ts';

// Exercise the shipped SVG renderer independently of React and browser storage.
class SvgElement {
  tagName: string; attributes = new Map<string, string>(); children: SvgElement[] = []; style: Record<string, string> = {}; textContent = '';
  constructor(tag: string) { this.tagName = tag; }
  setAttribute(name: string, value: unknown) { this.attributes.set(name, String(value)); }
  getAttribute(name: string) { return this.attributes.get(name) ?? null; }
  hasAttribute(name: string) { return this.attributes.has(name); }
  append(...children: SvgElement[]) { this.children.push(...children); }
  insertBefore(child: SvgElement, before: SvgElement | null) { const index = before ? this.children.indexOf(before) : -1; this.children.splice(index < 0 ? this.children.length : index, 0, child); }
  replaceChildren(...children: SvgElement[]) { this.children = children; }
  querySelectorAll(selector: string): SvgElement[] {
    const match = (item: SvgElement) => selector.startsWith('#') ? item.getAttribute('id') === selector.slice(1)
      : selector.startsWith('.') ? item.getAttribute('class')?.split(' ').includes(selector.slice(1))
      : selector.startsWith('[') ? (() => { const [, name, value] = /^\[([^=\]]+)(?:="([^"]*)")?\]$/.exec(selector)!; return item.hasAttribute(name) && (value === undefined || item.getAttribute(name) === value); })()
      : item.tagName === selector;
    return this.children.flatMap(child => [...(match(child) ? [child] : []), ...child.querySelectorAll(selector)]);
  }
  querySelector(selector: string): SvgElement | null { return this.querySelectorAll(selector)[0] ?? null; }
}
function runtime(controlRows: unknown[] = []) {
  const stage = new SvgElement('div');
  const context = vm.createContext({ window: { SummarySourceControls: { legendRows: () => controlRows } }, CSS: { escape: (value: string) => value }, document: {
    createElementNS: (_: string, tag: string) => new SvgElement(tag), getElementById: () => stage,
  } });
  vm.runInContext(readFileSync(new URL('../public/preview/yworks_edge_router_lab/studio-presentation.js', import.meta.url), 'utf8'), context);
  return context.window.ArchCanvasStudioPresentation;
}
function fixture() {
  return { nodes: ['a', 'b'].map(id => ({ id, x: 0, y: 0, w: 50, h: 40, semantic: { sourceStructure: true } })), canvas: [900, 700],
    edges: [{ id: 'source-arrow', source: 'a', target: 'b', role: 'source_dependency', syntaxOnly: true, dashed: true,
      binding: { canonical_src: 'a:out', canonical_dst: 'b:source-dependency', semantic_kind: 'source_dependency', source_evidence: ['e1'] } }],
    studioPresentation: { nodes: {}, edges: {}, annotations: {}, legend: [], page: {} } } as any;
}
function svgFor(graph: any) {
  const svg = new SvgElement('svg'), handles = new SvgElement('g'); handles.setAttribute('id', 'handleLayer');
  for (const edge of graph.edges) {
    const group = new SvgElement('g'), path = new SvgElement('path'), arrow = new SvgElement('path');
    group.setAttribute('data-edge-id', edge.id); path.setAttribute('class', 'wire-path'); path.setAttribute('stroke', '#776095'); path.setAttribute('stroke-dasharray', '2 4');
    arrow.setAttribute('class', 'arrow-shape'); arrow.setAttribute('fill', '#776095'); arrow.setAttribute('stroke', 'none'); group.append(path, arrow); svg.append(group);
  }
  svg.append(handles); return svg;
}
const plain = (value: any) => JSON.parse(JSON.stringify(value));

test('source inspection defaults distinguish value evidence from tensor, shape and visual draft arrows', () => {
  const graph = fixture(), P = runtime(), edge = graph.edges[0];
  assert.equal(P.isSourceDependency(graph, edge), true); assert.equal(isPreviewSourceDependency(graph, edge), true);
  assert.deepEqual(previewEdgeAppearance(graph, edge), { stroke: '#776095', width: 2.2, dashed: true });
  assert.deepEqual(plain(P.edgeAppearance(graph, edge)), { sourceRelation: true, stroke: '#776095', width: 2.2, dashed: true, dashArray: '2 4' });
  for (const changed of [{ role: 'data' }, { role: 'shape_dependency' }, { draft: true }, { binding: { evidence: 'visual edit draft; no source model writeback' } }]) {
    assert.equal(P.isSourceDependency(graph, { ...edge, ...changed }), false);
    assert.equal(isPreviewSourceDependency(graph, { ...edge, ...changed }), false);
  }
  const normal = { ...edge, syntaxOnly: undefined, source: 'input', target: 'output' };
  assert.equal(P.isSourceDependency(graph, normal), false); assert.equal(isPreviewSourceDependency(graph, normal), false);
});

test('recursive projections and pre-migration cached syntax arrows keep their source classification', () => {
  const graph = fixture(), original = { ...graph.edges[0], syntaxOnly: undefined };
  graph.recursive = { authority: { detail: { nodes: graph.nodes, edges: [original] } }, state: { studioPresentation: graph.studioPresentation } };
  const projected = { id: 'folded', source: 'container-a', target: 'container-b', projection: { original: original.id } };
  const P = runtime();
  assert.equal(P.isSourceDependency(graph, projected), true); assert.equal(isPreviewSourceDependency(graph, projected), true);
  assert.equal(P.edgeAppearance(graph, projected).stroke, '#776095');
  assert.equal(previewEdgeAppearance(graph, projected).stroke, '#776095');
  graph.recursive.authority.detail.nodes[1].semantic.sourceStructure = false;
  assert.equal(P.isSourceDependency(graph, projected), false); assert.equal(isPreviewSourceDependency(graph, projected), false);
});

test('user paint and line choices survive syntax defaults and monochrome only changes color', () => {
  const graph = fixture(), P = runtime(), edge = graph.edges[0];
  graph.studioPresentation.edges[edge.id] = { stroke: '#123456', width: 4, dashed: false };
  assert.deepEqual(previewEdgeAppearance(graph, edge), { stroke: '#123456', width: 4, dashed: false });
  assert.deepEqual(plain(P.edgeAppearance(graph, edge)), { sourceRelation: true, stroke: '#123456', width: 4, dashed: false, dashArray: 'none' });
  graph.studioPresentation.page.preset = 'monochrome';
  assert.equal(P.edgeAppearance(graph, edge).stroke, '#4b5563'); assert.equal(previewEdgeAppearance(graph, edge).stroke, '#4b5563');
  delete graph.studioPresentation.edges[edge.id];
  assert.equal(P.edgeAppearance(graph, edge).dashArray, '2 4'); assert.equal(P.edgeAppearance(graph, edge).dashed, true);
});

test('renderer omits node categories while retaining source evidence labels without mutating source bindings', () => {
  const graph = fixture(), P = runtime(), before = JSON.stringify(graph), svg = svgFor(graph);
  graph.studioPresentation.legend = [{ id: 'linear', label: 'Linear', color: '#abcdef', glyph: 'module' }];
  const sourceFacts = JSON.stringify([graph.nodes, graph.edges]);
  P.render(graph, svg); P.render(graph, svg);
  assert.equal(svg.querySelectorAll('[data-studio-legend]').length, 1);
  assert.equal(svg.querySelectorAll('[data-source-relation-legend]').length, 1);
  const text = svg.querySelectorAll('text').map(node => node.textContent);
  assert.deepEqual(text, ['源码数据依赖 · 执行路径未确定']);
  const relation = svg.querySelector('[data-source-relation-legend]')!;
  assert.equal(relation.querySelector('path')!.getAttribute('stroke-dasharray'), '2 4');
  assert.equal(JSON.stringify([graph.nodes, graph.edges]), sourceFacts);
  graph.studioPresentation.legend = []; P.render(graph, svg);
  assert.equal(svg.querySelectorAll('[data-studio-legend]').length, 1);
  assert.equal(JSON.stringify(graph), before);
  graph.edges = []; graph.studioPresentation.legend = [{ id: 'linear', label: 'Linear', color: '#abcdef', glyph: 'module' }]; P.render(graph, svg);
  assert.equal(svg.querySelectorAll('[data-studio-legend]').length, 0);
});

test('the actual SVG overlay applies explicit edge colors to shaft and arrows and keeps mono patterns', () => {
  const graph = fixture(), P = runtime(), svg = svgFor(graph), edge = graph.edges[0];
  graph.studioPresentation.edges[edge.id] = { stroke: '#123456', width: 4, dashed: true };
  P.render(graph, svg);
  assert.equal(svg.querySelector('.wire-path')!.getAttribute('stroke'), '#123456');
  assert.equal(svg.querySelector('.wire-path')!.getAttribute('stroke-width'), '4');
  assert.equal(svg.querySelector('.wire-path')!.getAttribute('stroke-dasharray'), '2 4');
  assert.equal(svg.querySelector('.arrow-shape')!.getAttribute('fill'), '#123456');
  graph.studioPresentation.page.preset = 'monochrome'; P.render(graph, svg);
  assert.equal(svg.querySelector('.wire-path')!.getAttribute('stroke'), '#4b5563');
  assert.equal(svg.querySelector('.arrow-shape')!.getAttribute('fill'), '#4b5563');
  assert.equal(svg.querySelector('.wire-path')!.getAttribute('stroke-dasharray'), '2 4');
});

test('source legend participates in preview annotation avoidance with no extra node legend', () => {
  const graph = fixture(); graph.studioPresentation.annotations.note = { id: 'note', text: 'note', x: 560, y: 650, width: 200 };
  assert.deepEqual(previewAnnotationConflicts(graph, 'note'), [{ kind: 'legend', id: 'studio:legend' }]);
});

test('control branches and source values share one legend while retaining distinct grammar', () => {
  const graph = fixture(), P = runtime([{ label: '条件分支 · 非张量', stroke: '#8a6a46', dashArray: '4 4' }]), svg = svgFor(graph);
  graph.sourceControls = { controls: [{ id: 'branch' }] };
  P.render(graph, svg);
  assert.equal(svg.querySelectorAll('[data-studio-legend]').length, 1);
  assert.equal(svg.querySelectorAll('[data-source-relation-legend]').length, 1);
  assert.equal(svg.querySelectorAll('[data-source-control-legend]').length, 1);
  assert.equal(svg.querySelector('[data-source-control-legend]')!.querySelector('path')!.getAttribute('stroke-dasharray'), '4 4');
  assert.deepEqual(svg.querySelectorAll('text').map(node => node.textContent), ['源码数据依赖 · 执行路径未确定', '条件分支 · 非张量']);
});
