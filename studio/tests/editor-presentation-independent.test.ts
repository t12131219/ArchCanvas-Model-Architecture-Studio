import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { applyVisualBatch, buildExportScene, buildScene, createDocument, createHistory, editorLegendItems, editorSceneBounds,
  implicitRootIds, presentEditorScene, reduceHistory, renderSvg } from '../src/core/index.ts';
import type { Architecture, ArchitectureNode, CanvasDocument, Scene } from '../src/core/types.ts';

// Assertions read the public SVG directly, independently of the renderer's
// node, port, root-projection and path helpers.
const visibleBody = (svg: string) => svg.slice(svg.indexOf('</metadata>') + '</metadata>'.length);
const paintedNodes = (svg: string) => [...visibleBody(svg).matchAll(/<g data-node-id="([^"]+)" data-canonical-id=/g)].map(match => match[1]);
const paintedPaths = (svg: string) => [...visibleBody(svg).matchAll(/<g data-edge-id="([^"]+)"[^>]*>(.*?)<\/g>/g)].map(match => {
  const hit = match[2].match(/<path data-route-kind="hit" d="([^"]+)"/);
  const original = hit ?? match[2].match(/<path(?: data-route-kind="visible")? d="([^"]+)"/);
  return [match[1], original![1]];
});
const entities: Record<string, string> = { quot: '"', apos: "'", lt: '<', gt: '>', amp: '&' };
const decode = (value: string) => value.replace(/&(quot|apos|lt|gt|amp);/g, (_, entity: string) => entities[entity]!);
const metadata = (svg: string) => JSON.parse(decode(svg.match(/<metadata>(.*?)<\/metadata>/s)![1]));
const viewBox = (svg: string) => svg.match(/viewBox="([^"]+)"/)![1].split(' ').map(Number);

function namedHierarchy(): Architecture {
  const node = (id: string, parentId?: string, children: string[] = []): ArchitectureNode => ({ id, label: `Name ${id}`, kind: children.length ? 'Module' : 'Linear', category: children.length ? 'container' : 'linear',
    parentId, children, parameters: {}, evidence: 'source', ports: [
      { id: 'in', name: 'input', role: 'data', direction: 'in', ordinal: 0 },
      { id: 'out', name: 'output', role: 'data', direction: 'out', ordinal: 0 },
    ] });
  return { schemaVersion: 1, id: 'arbitrary', label: 'Unrelated & 自定义', sourceDigest: 'literal-source', irDigest: 'literal-ir', entry: 'model:Arbitrary', diagnostics: [], sources: [],
    nodes: [node('outer', undefined, ['input', 'inner', 'output']), node('input', 'outer'), node('inner', 'outer', ['first', 'second']), node('first', 'inner'), node('second', 'inner'), node('output', 'outer')],
    edges: [
      { id: 'enter', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'first', portId: 'in' }, tensorId: 'first-tensor', role: 'data' },
      { id: 'within', source: { nodeId: 'first', portId: 'out' }, target: { nodeId: 'second', portId: 'in' }, tensorId: 'middle-tensor', role: 'data' },
      { id: 'leave', source: { nodeId: 'second', portId: 'out' }, target: { nodeId: 'output', portId: 'in' }, tensorId: 'last-tensor', role: 'data' },
    ] };
}

for (const caseId of ['mlp-level1-base', 'residual_cnn-level2-base', 'transformer-level3-base']) {
  test(`editor omits only root furniture for current ${caseId}, retaining every canonical route and publication object`, () => {
    const document = JSON.parse(readFileSync(new URL(`../../docs/evidence/unified-editor-review-v2/routing-before/${caseId}.canvas.json`, import.meta.url), 'utf8')) as CanvasDocument;
    const original = JSON.stringify(document), scene = buildScene(document), beforeScene = JSON.stringify(scene);
    const expectedImplicit = scene.nodes.filter(node => !node.parentId && node.expanded && node.expandable).map(node => node.id);
    const editor = renderSvg(scene, { presentation: 'editor', interactive: true }), publication = renderSvg(buildExportScene(document));
    assert.equal(expectedImplicit.length, 1);
    assert.deepEqual(paintedNodes(editor), scene.nodes.filter(node => node.expanded && !expectedImplicit.includes(node.id)).concat(scene.nodes.filter(node => !node.expanded)).map(node => node.id));
    for (const id of expectedImplicit) {
      assert.ok(!paintedNodes(editor).includes(id)); assert.ok(paintedNodes(publication).includes(id));
      assert.ok(!visibleBody(editor).includes(`data-expand-id="${id}"`));
      for (const port of scene.nodes.find(node => node.id === id)!.ports) assert.ok(!visibleBody(editor).includes(`data-port-id="${port.id}"`));
    }
    assert.doesNotMatch(visibleBody(editor), /MODEL ARCHITECTURE|data-legend-id=|data-edge-legend-id=/);
    assert.match(visibleBody(publication), /MODEL ARCHITECTURE/); assert.match(visibleBody(publication), /data-legend-id=/);
    assert.deepEqual(paintedPaths(editor), paintedPaths(publication));
    const e = metadata(editor), p = metadata(publication);
    assert.deepEqual(e.renderedBindings, p.renderedBindings); assert.deepEqual(e.sourceFacts, p.sourceFacts);
    assert.deepEqual(e.implicitContainerIds, expectedImplicit);
    assert.deepEqual(e.renderedNodes.map((node: { sceneNodeId: string }) => node.sceneNodeId), scene.nodes.filter(node => !expectedImplicit.includes(node.id)).map(node => node.id));
    assert.equal(e.sourceDigest, document.architecture.sourceDigest); assert.equal(e.irDigest, document.architecture.irDigest);
    const projected = presentEditorScene(scene), bounds = projected.bounds;
    assert.deepEqual(viewBox(editor), [bounds.x, bounds.y, bounds.width, bounds.height].map(value => Math.round(value * 100) / 100));
    assert.equal(projected.nodes, scene.nodes); assert.equal(projected.edges, scene.edges);
    assert.equal(JSON.stringify(document), original); assert.equal(JSON.stringify(scene), beforeScene);
    assert.equal(renderSvg(scene), publication);
  });
}

test('unrelated custom root identity stays implicit only while expanded, and conceptual hierarchy keeps collapse/layout/cache/history', () => {
  let document = applyVisualBatch(createDocument(namedHierarchy()), [{ type: 'expand', id: 'inner', expanded: true }, { type: 'move', ids: ['second'], dx: 24, dy: 16 }]);
  const before = structuredClone(document), initial = buildScene(document);
  assert.deepEqual([...implicitRootIds(initial)], ['outer']);
  assert.ok(paintedNodes(renderSvg(initial, { presentation: 'editor' })).includes('inner'), 'real nested module frame remains');
  let history = reduceHistory(createHistory(document), { type: 'apply', operations: [{ type: 'expand', id: 'outer', expanded: false }] });
  const collapsed = buildScene(history.document), svg = renderSvg(collapsed, { presentation: 'editor', interactive: true });
  assert.deepEqual([...implicitRootIds(collapsed)], []); assert.deepEqual(paintedNodes(svg), ['outer']);
  assert.match(visibleBody(svg), /data-expand-id="outer"/);
  history = reduceHistory(history, { type: 'apply', operations: [{ type: 'expand', id: 'outer', expanded: true }] });
  const reopened = buildScene(history.document);
  assert.deepEqual(reopened.nodes.map(node => [node.id, node.x, node.y, node.width, node.height]), initial.nodes.map(node => [node.id, node.x, node.y, node.width, node.height]));
  assert.deepEqual(reopened.edges, initial.edges); assert.deepEqual(history.document.architecture, before.architecture);
  assert.ok(Object.keys(history.document.layoutByFrontier).length >= 2);
  const undo = reduceHistory(history, { type: 'undo' }), redo = reduceHistory(undo, { type: 'redo' });
  assert.deepEqual(buildScene(undo.document).nodes.map(node => node.id), ['outer']);
  assert.deepEqual(buildScene(redo.document).nodes, reopened.nodes);
  document = JSON.parse(JSON.stringify(history.document));
  assert.deepEqual(buildScene(document), reopened);
});

test('fit measures edited world objects and routes, excluding publication title, legends and implicit root padding', () => {
  const scene = buildScene(createDocument(namedHierarchy()));
  const root = scene.nodes.find(node => node.id === 'outer')!;
  const baseline = editorSceneBounds(scene), before = JSON.stringify(scene);
  const decorationChanged: Scene = { ...scene, title: 'W'.repeat(1000), bounds: { x: -9000, y: -9000, width: 20000, height: 30000 },
    nodes: scene.nodes.map(node => node.id === root.id ? { ...node, x: -10000, y: -10000, width: 90000, height: 80000 } : node),
    legend: scene.legend.map(item => ({ ...item, x: 50000, y: -60000 })) };
  assert.deepEqual(editorSceneBounds(decorationChanged), baseline);
  const one: Scene = { ...scene, nodes: [{ ...scene.nodes.find(node => node.id === 'input')!, parentId: undefined, x: -400, y: -100, width: 120, height: 60 }], edges: [], annotations: [], captionGuides: [] };
  assert.deepEqual(editorSceneBounds(one), { x: -424, y: -124, width: 168, height: 108 });
  const annotation = { id: 'note', text: 'manual note', x: 2000, y: 3000, width: 100, height: 40 };
  const withNote = editorSceneBounds({ ...one, annotations: [annotation] });
  assert.equal(withNote.x + withNote.width, 2124); assert.equal(withNote.y + withNote.height, 3064);
  const remoteEdge = { ...scene.edges[0], path: 'M -400 -100 V -900 H 3200 V 3000', label: '' };
  const withRoute = editorSceneBounds({ ...one, edges: [remoteEdge] });
  assert.ok(withRoute.x + withRoute.width > 3200 && withRoute.y < -900 && withRoute.y + withRoute.height > 3000);
  assert.equal(JSON.stringify(scene), before);
});

test('floating legend content keeps authored order and every actual edge style in color and monochrome', () => {
  let document = applyVisualBatch(createDocument(namedHierarchy()), [{ type: 'expand', id: 'inner', expanded: true },
    { type: 'legend', items: [{ id: 'z', label: 'Edited & 节点', color: '#123456', glyph: 'attention' }, { id: 'a', label: 'Second', color: '#abcdef', glyph: 'tensor' }] },
    { type: 'edgeStyle', id: 'within', style: { stroke: '#ff0000', width: 3, dashed: true } }]);
  for (const preset of ['paper', 'monochrome'] as const) {
    document = applyVisualBatch(document, [{ type: 'page', page: { preset } }]);
    const scene = buildScene(document), before = JSON.stringify(scene), legend = editorLegendItems(scene);
    assert.deepEqual(legend.nodes.map(item => [item.id, item.label, item.glyph]), [['z', 'Edited & 节点', 'attention'], ['a', 'Second', 'tensor']]);
    assert.equal(legend.edges.length, 2); assert.deepEqual(legend.edges.flatMap(item => item.canonicalEdgeIds).sort(), ['enter', 'leave', 'within']);
    const custom = legend.edges.find(item => item.sceneEdgeIds.includes('within'))!;
    assert.equal(custom.lineWidth, 3); assert.equal(custom.dashed, true); assert.ok(custom.dashPattern!.length > 0);
    assert.ok(legend.edges.every(item => !Object.hasOwn(item, 'x') && !Object.hasOwn(item, 'y')));
    assert.ok(legend.nodes.every(item => !Object.hasOwn(item, 'x') && !Object.hasOwn(item, 'y')));
    assert.equal(JSON.stringify(scene), before);
    const publication = renderSvg(scene);
    assert.match(visibleBody(publication), /Edited &amp; 节点/);
    if (preset === 'monochrome') assert.match(visibleBody(publication), /data-edge-legend-id=/);
    assert.doesNotMatch(visibleBody(renderSvg(scene, { presentation: 'editor' })), /data-legend-id=|data-edge-legend-id=/);
  }
});

test('independent parentless leaves and explicit detail boundary cards never become hidden roots', () => {
  assert.deepEqual([...implicitRootIds({ nodes: [
    { id: 'input', expanded: false, expandable: false },
    { id: 'output', expanded: false, expandable: false },
    { id: 'collapsed', expanded: false, expandable: true },
    { id: 'detail-boundary', expanded: true, expandable: true, boundary: true },
    { id: 'inner', expanded: true, expandable: true, parentId: 'outside' },
  ] })], []);
});

test('editor paints an exact tensor fan-out prefix once with its real junction while preserving complete selectable bindings and export paths', () => {
  const source = { nodeId: 'input', portId: 'out' }, scene = buildScene(createDocument(namedHierarchy()));
  const paths = ['M 10 20 V 80 H 50 V 120 H 70', 'M 10 20 V 80 H 50 V 170 H 100'];
  scene.edges = ['branch-one', 'branch-two'].map((id, index) => ({ ...scene.edges[0], id, sourceId: 'input', source,
    targetId: index ? 'output' : 'inner', target: { nodeId: index ? 'output' : 'inner', portId: 'in' },
    tensorId: 'shared-source', role: 'mask', stroke: '#987654', width: 2, dashed: true, dashPattern: [4, 4],
    canonicalEdgeIds: [id], label: '', path: paths[index] }));
  const before = JSON.stringify(scene), editor = renderSvg(scene, { presentation: 'editor', interactive: true }), publication = renderSvg(scene);
  const body = visibleBody(editor), groups = [...body.matchAll(/<g data-edge-id="([^"]+)"[^>]*>(.*?)<\/g>/g)];
  assert.equal(groups.length, 2); assert.deepEqual(paintedPaths(editor).map(([, path]) => path), paths);
  assert.match(groups[0][2], /data-route-kind="visible" d="M 10 20 V 80 H 50 V 120 H 70"/);
  assert.match(groups[1][2], /data-route-kind="visible" d="M 50 120 V 170 H 100"/);
  assert.match(groups[1][2], /stroke-dashoffset="-140"/);
  assert.equal([...body.matchAll(/data-route-junction-id=/g)].length, 1);
  assert.match(body, /data-route-junction-id="editor-branch:1"[^>]*cx="50" cy="120"/);
  const saved = metadata(editor), exported = metadata(publication);
  assert.deepEqual(saved.renderedBindings, exported.renderedBindings);
  assert.deepEqual(saved.routePresentation.bindings.map((edge: { fullPath: string }) => edge.fullPath), paths);
  assert.deepEqual(paintedPaths(publication).map(([, path]) => path), paths);
  assert.doesNotMatch(visibleBody(publication), /data-route-kind="hit"|data-route-junction-id=/);
  assert.equal(JSON.stringify(scene), before);
  const readonlySvg = renderSvg(scene, { presentation: 'editor' });
  assert.doesNotMatch(visibleBody(readonlySvg), /data-route-kind="hit"/);
  assert.match(visibleBody(readonlySvg), /data-route-kind="visible" d="M 50 120 V 170 H 100"/);
  assert.deepEqual(metadata(readonlySvg).routePresentation.bindings.map((edge: { fullPath: string }) => edge.fullPath), paths);
  for (const mutate of [
    (value: Scene) => { value.edges[1].source = { nodeId: 'other-producer', portId: 'out' }; },
    (value: Scene) => { value.edges[1].tensorId = 'different-tensor'; },
    (value: Scene) => { value.edges[1].role = 'data'; },
    (value: Scene) => { value.edges[1].stroke = '#aaaaaa'; },
  ]) {
    const different = structuredClone(scene); mutate(different);
    const svg = renderSvg(different, { presentation: 'editor', interactive: true });
    assert.doesNotMatch(visibleBody(svg), /data-route-junction-id=/);
    assert.match(visibleBody(svg), /data-route-kind="visible" d="M 10 20 V 80 H 50 V 170 H 100"/);
  }
});
