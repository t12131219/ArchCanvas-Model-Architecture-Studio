import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { applyVisualBatch, buildScene, buildExportScene, createHistory, reduceHistory, renderSvg } from '../src/core/index.ts';
import type { CanvasDocument, Scene, SceneCaptionGuide, SceneEdge, SceneNode } from '../src/core/types.ts';
import { placeEdgeLabels } from '../src/core/edgeLabelPlacement.ts';
import { layoutWarnings } from '../src/layoutWarnings.ts';

const fixture = new URL('../../docs/evidence/m4-visual-next-current/review/label-before/files/docs/evidence/m4-visual-next-current/review/fresh-source-core/transformer-level0-paper-180.canvas.json', import.meta.url);

test('source-grounded distant memory caption has an owned-route guide instead of silently floating beside mask routes', () => {
  const document = JSON.parse(readFileSync(fixture, 'utf8')) as CanvasDocument, before = JSON.stringify(document);
  const scene = buildScene(document), caption = scene.edges.find(edge => edge.label === 'memory')!;
  const guides = (scene as typeof scene & { captionGuides?: { sceneEdgeId: string; path: string }[] }).captionGuides ?? [];
  assert.ok(guides.some(guide => guide.sceneEdgeId === caption.id), 'a distant memory caption requires an explicit decorative connection to its actual rendered route');
  assert.equal(JSON.stringify(document), before);
  verify(scene);
});

// These independent geometry helpers consume public serialized coordinates.
// No production parser/outline/bounds/intersection/association helper is used.
type Point = { x: number; y: number };
type Rect = { x: number; y: number; width: number; height: number };
function points(path: string): Point[] {
  const tokens = path.match(/[MLHV]|[-+]?(?:\d*\.\d+|\d+\.?\d*)/g)!;
  const result: Point[] = [];
  for (let index = 0; index < tokens.length;) {
    const command = tokens[index++];
    const point = command === 'M' || command === 'L' ? { x: +tokens[index++], y: +tokens[index++] }
      : command === 'H' ? { x: +tokens[index++], y: result.at(-1)!.y }
        : { x: result.at(-1)!.x, y: +tokens[index++] };
    if (!result.length || point.x !== result.at(-1)!.x || point.y !== result.at(-1)!.y) result.push(point);
  }
  return result;
}
function contact(a: Point, b: Point, c: Point, d: Point) {
  const av = a.x === b.x, cv = c.x === d.x;
  if (av !== cv) {
    const [v, w, h, k] = av ? [a, b, c, d] : [c, d, a, b];
    return v.x >= Math.min(h.x, k.x) && v.x <= Math.max(h.x, k.x) && h.y >= Math.min(v.y, w.y) && h.y <= Math.max(v.y, w.y);
  }
  return (av ? a.x === c.x : a.y === c.y) && Math.max(Math.min(av ? a.y : a.x, av ? b.y : b.x), Math.min(cv ? c.y : c.x, cv ? d.y : d.x))
    <= Math.min(Math.max(av ? a.y : a.x, av ? b.y : b.x), Math.max(cv ? c.y : c.x, cv ? d.y : d.x));
}
function body(edge: SceneEdge): Rect { return { x: edge.labelX - 2, y: edge.labelY - 11, width: [...edge.label].length * 9 + 4, height: 16 }; }
function enters(a: Point, b: Point, rect: Rect) {
  return a.x === b.x ? a.x > rect.x && a.x < rect.x + rect.width && Math.max(Math.min(a.y, b.y), rect.y) < Math.min(Math.max(a.y, b.y), rect.y + rect.height)
    : a.y > rect.y && a.y < rect.y + rect.height && Math.max(Math.min(a.x, b.x), rect.x) < Math.min(Math.max(a.x, b.x), rect.x + rect.width);
}
function verify(scene: Pick<Scene, 'nodes' | 'edges' | 'captionGuides'> & { annotations?: Rect[]; bounds?: Rect }) {
  const guides = scene.captionGuides ?? [];
  for (const guide of guides) {
    const edge = scene.edges.find(item => item.id === guide.sceneEdgeId)!;
    assert.ok(edge?.label); assert.equal(guide.kind, 'caption-guide'); assert.equal(guide.width, .8);
    const [start, end, ...rest] = points(guide.path), box = body(edge);
    assert.deepEqual(rest, []); assert.ok(start.x === end.x || start.y === end.y);
    assert.ok(Math.abs(end.x - start.x) + Math.abs(end.y - start.y) > 0);
    assert.ok(Math.abs(end.x - start.x) + Math.abs(end.y - start.y) <= 48);
    const owner = points(edge.path);
    assert.ok(owner.slice(1).some((b, index) => {
      const a = owner[index];
      return a.x === b.x ? start.x === a.x && start.y > Math.min(a.y, b.y) && start.y < Math.max(a.y, b.y)
        : start.y === a.y && start.x > Math.min(a.x, b.x) && start.x < Math.max(a.x, b.x);
    }), 'attachment is a strict-interior point of the final rendered owner route');
    assert.ok((end.x === box.x || end.x === box.x + box.width) && end.y >= box.y && end.y <= box.y + box.height
      || (end.y === box.y || end.y === box.y + box.height) && end.x >= box.x && end.x <= box.x + box.width);
    const obstacles = [...scene.nodes.flatMap(node => node.expanded ? [{ x: node.x, y: node.y, width: node.width, height: node.headerHeight }]
      : [0, ...(node.repeat ? [3.5, 7] : [])].map(offset => ({ x: node.x + offset, y: node.y + offset, width: node.width, height: node.height }))),
      ...(scene.annotations ?? []), ...scene.edges.filter(item => item.label && item.id !== edge.id).map(body)];
    for (const rect of obstacles) assert.equal(enters(start, end, rect), false, 'guide enters another visible body');
    for (const other of scene.edges.filter(item => item.id !== edge.id)) {
      const line = points(other.path);
      assert.ok(line.slice(1).every((b, index) => !contact(start, end, line[index], b)), 'guide may not touch an unrelated tensor route');
    }
    for (const other of guides.filter(item => item.id !== guide.id)) {
      const [a, b] = points(other.path); assert.equal(contact(start, end, a, b), false, 'caption guides may not touch each other');
      const combinedRadius: number = (guide.width + other.width) / 2;
      assert.equal(enters(start, end, { x: Math.min(a.x, b.x) - combinedRadius, y: Math.min(a.y, b.y) - combinedRadius,
        width: Math.abs(b.x - a.x) + combinedRadius * 2, height: Math.abs(b.y - a.y) + combinedRadius * 2 }), false, 'visible strokes of separate caption guides must remain clear');
    }
    if (scene.bounds) for (const point of [start, end]) {
      assert.ok(point.x >= scene.bounds.x && point.x <= scene.bounds.x + scene.bounds.width);
      assert.ok(point.y >= scene.bounds.y && point.y <= scene.bounds.y + scene.bounds.height);
    }
  }
}
function node(id: string, x: number, y: number, width: number, height: number): SceneNode {
  return { id, x, y, width, height, localX: x, localY: y, label: id, subtitle: '', headerHeight: 30,
    kind: 'Block', category: 'module', fill: '#fff', stroke: '#000', glyph: 'module', expanded: false,
    expandable: false, pinned: false, evidence: 'source', ports: [] };
}
function edge(id: string, label: string, path: string, x: number, y: number): SceneEdge {
  return { id, label, labelX: x, labelY: y, path, sourceId: 'left', targetId: 'right', source: { nodeId: 'left', portId: 'out' },
    target: { nodeId: 'right', portId: 'in' }, canonicalEdgeIds: [id], tensorId: id, role: 'data', stroke: '#123456', width: 1.5, dashed: false };
}
function generalFixture(dx = 0, dy = 0, label = '投影通道'): { nodes: SceneNode[]; edges: SceneEdge[] } {
  const left = { ...node('left', dx, dy + 30, 100, 60), repeat: { count: 2, sharing: 'independent' as const } };
  const right = node('right', dx + 130, dy + 30, 100, 60);
  return { nodes: [left, right], edges: [edge('own', label, `M ${dx + 107} ${dy + 60} H ${dx + 130}`, dx + 107, dy + 52)] };
}
function placed(fixture: { nodes: SceneNode[]; edges: SceneEdge[] }, notes: (Rect & { id: string })[] = []) {
  const result = placeEdgeLabels(fixture.nodes, fixture.edges, notes);
  return { ...fixture, edges: fixture.edges.map(item => ({ ...item, labelX: result.placements.get(item.id)?.x ?? item.labelX, labelY: result.placements.get(item.id)?.y ?? item.labelY })),
    captionGuides: result.guides, annotations: notes, diagnostics: result.diagnostics };
}

test('a safe close caption keeps its coordinates and creates no decorative guide', () => {
  const input = { nodes: [], edges: [edge('near', 'near', 'M 0 100 H 150', 35, 92)] }, before = JSON.stringify(input);
  const scene = placed(input); assert.deepEqual([scene.edges[0].labelX, scene.edges[0].labelY], [35, 92]);
  assert.deepEqual(scene.captionGuides, []); assert.deepEqual(scene.diagnostics, []); assert.equal(JSON.stringify(input), before);
});

test('general translated CJK captions use short collision-free guides without model-name or ID dependencies', () => {
  const first = generalFixture(), second = generalFixture(-260.25, 490.5), snapshot = JSON.stringify(second);
  const base = placed(first), translated = placed(second);
  assert.equal(base.captionGuides.length, 1); assert.equal(translated.captionGuides.length, 1);
  verify(base); verify(translated);
  assert.deepEqual(points(translated.captionGuides[0].path).map(point => ({ x: point.x + 260.25, y: point.y - 490.5 })), points(base.captionGuides[0].path));
  assert.equal(JSON.stringify(second), snapshot); assert.deepEqual(translated, placed(second));
});

test('crowded and shared-route attachments preserve captions and give explicit diagnostics instead of unsafe guide connections', () => {
  const fixture = generalFixture(), own = fixture.edges[0];
  fixture.edges.push({ ...own, id: 'shared-sibling', canonicalEdgeIds: ['shared-sibling'], label: '' });
  const sameBytes = JSON.stringify(fixture), scene = placed(fixture);
  assert.deepEqual(scene.captionGuides, []); assert.deepEqual([scene.edges[0].labelX, scene.edges[0].labelY], [own.labelX, own.labelY]);
  assert.ok(scene.diagnostics.some(item => item.code === 'layout-edge-label-blocked'));
  assert.equal(JSON.stringify(fixture), sameBytes);
  const distant = { nodes: [], edges: [edge('far', 'far', 'M 0 0 H 100', 30, 200)] }, far = placed(distant);
  assert.deepEqual([far.edges[0].labelX, far.edges[0].labelY], [30, 200]); assert.deepEqual(far.captionGuides, []);
  assert.equal(far.diagnostics[0].code, 'layout-edge-label-association');
  const sourceScene = buildScene(JSON.parse(readFileSync(fixtureUrl(), 'utf8')) as CanvasDocument);
  sourceScene.nodes = []; sourceScene.edges = far.edges; sourceScene.diagnostics = far.diagnostics;
  assert.ok(layoutWarnings(sourceScene)[0].includes('离所属连线过远'));
});
function fixtureUrl() { return fixture; }

test('notes, other caption envelopes, crossing routes and reserved guides remain obstacles in a general multi-label batch', () => {
  const a = generalFixture(), b = generalFixture(300, 220, 'memory'), input = { nodes: [...a.nodes, ...b.nodes.map(item => ({ ...item, id: item.id + ':second' }))],
    edges: [...a.edges, ...b.edges.map(item => ({ ...item, id: item.id + ':second', sourceId: 'left:second', targetId: 'right:second', canonicalEdgeIds: ['second'] }))] };
  const scene = placed(input, [{ id: 'note', x: 102, y: 99, width: 14, height: 30 }]);
  verify(scene); assert.ok(scene.captionGuides.length >= 1); assert.equal(scene.diagnostics.length, 0);
  input.edges.push(edge('interloper', '', 'M 115 61 V 135', 0, 0));
  const crossed = placed(input); verify(crossed);
  assert.ok(crossed.captionGuides.every(guide => guide.sceneEdgeId !== 'interloper'));
});

test('whole/detail, aliases, monochrome, save/reopen and undo/redo keep caption decoration outside canonical metadata', () => {
  let document = JSON.parse(readFileSync(fixture, 'utf8')) as CanvasDocument;
  document = applyVisualBatch(document, [{ type: 'alias', id: 'repeat:instance:model.Transformer.encoder', label: '研究编码器' }]);
  const inputBytes = JSON.stringify(document), full = buildScene(document);
  assert.deepEqual(buildExportScene(document), full);
  const history = reduceHistory(createHistory(document), { type: 'apply', baseRevision: document.revision, operations: [{ type: 'page', page: { preset: 'monochrome' } }] });
  const monochrome = buildScene(history.document), detail = buildExportScene(history.document, { nodeId: document.expandedIds[0] });
  for (const scene of [full, monochrome, detail]) {
    verify(scene); assert.ok(scene.captionGuides?.length);
    for (const interactive of [false, true]) {
      const svg = renderSvg(scene, { interactive }), guideMarkup = [...svg.matchAll(/<path data-caption-guide-id="[^]*?<\/path>/g)].map(match => match[0]);
      assert.equal(guideMarkup.length, scene.captionGuides!.length);
      assert.ok(guideMarkup.every(markup => !/marker-|data-tensor-id|data-edge-id/.test(markup)));
      const metadata = JSON.parse(svg.match(/<metadata>(.*?)<\/metadata>/s)![1].replaceAll('&quot;', '"').replaceAll('&amp;', '&').replaceAll('&lt;', '<').replaceAll('&gt;', '>'));
      assert.equal(metadata.presentationDecorations.length, scene.captionGuides!.length);
      assert.equal(metadata.renderedBindings.length, scene.edges.length);
      assert.deepEqual(metadata.sourceFacts, full.sourceFacts);
      assert.ok(metadata.renderedBindings.every((binding: { sceneEdgeId: string }) => !scene.captionGuides!.some(guide => guide.id === binding.sceneEdgeId)));
    }
  }
  const undo = reduceHistory(history, { type: 'undo' }), redo = reduceHistory(undo, { type: 'redo' });
  const withoutRevision = ({ revision: _revision, ...value }: CanvasDocument) => value;
  assert.deepEqual(withoutRevision(undo.document), withoutRevision(document)); assert.deepEqual(withoutRevision(redo.document), withoutRevision(history.document));
  assert.deepEqual(buildScene(JSON.parse(JSON.stringify(history.document))), monochrome);
  assert.deepEqual(history.document.architecture, document.architecture); assert.equal(JSON.stringify(document), inputBytes);
  assert.equal('captionGuides' in document, false); assert.equal('captionGuides' in history.document, false);
});

test('a general stress batch preserves every canonical edge and produces deterministic nonintersecting decorations', () => {
  const nodes: SceneNode[] = [], edges: SceneEdge[] = [];
  for (let index = 0; index < 24; index++) {
    const row = generalFixture(0, index * 180, `通道${index}`);
    nodes.push(...row.nodes.map(item => ({ ...item, id: item.id + index })));
    edges.push(...row.edges.map(item => ({ ...item, id: item.id + index, sourceId: 'left' + index, targetId: 'right' + index, canonicalEdgeIds: ['canonical:' + index] })));
  }
  const input = { nodes, edges }, bytes = JSON.stringify(input), scene = placed(input);
  assert.equal(scene.edges.length, 24); assert.equal(scene.captionGuides.length, 24); assert.deepEqual(scene.diagnostics, []);
  verify(scene); assert.deepEqual(scene, placed(input)); assert.equal(JSON.stringify(input), bytes);
  assert.deepEqual(scene.edges.map(item => item.canonicalEdgeIds), edges.map(item => item.canonicalEdgeIds));
});

test('a dense batch above the deterministic association limit keeps every label and emits diagnostics', () => {
  const edges = Array.from({ length: 129 }, (_, index) => edge(`dense-${index}`, `标签${index}`, `M 0 ${index * 40} H 150`, 30, index * 40 - 7));
  const bytes = JSON.stringify(edges), result = placeEdgeLabels([], edges);
  assert.equal(result.placements.size, 129); assert.equal(result.diagnostics.length, 129); assert.deepEqual(result.guides, []);
  for (const item of edges) assert.deepEqual(result.placements.get(item.id), { x: item.labelX, y: item.labelY });
  assert.ok(result.diagnostics.every(item => item.code === 'layout-edge-label-association' && item.message.includes('work limits')));
  assert.equal(JSON.stringify(edges), bytes);
});

test('geometry-check exhaustion in a still-supported batch preserves remaining captions with explicit budget evidence', () => {
  const nodes: SceneNode[] = [], edges: SceneEdge[] = [];
  for (let index = 0; index < 80; index++) {
    const row = generalFixture(0, index * 180, `通道${index}`);
    nodes.push(...row.nodes.map(item => ({ ...item, id: item.id + index })));
    edges.push(...row.edges.map(item => ({ ...item, id: item.id + index, sourceId: 'left' + index, targetId: 'right' + index })));
  }
  const inputBytes = JSON.stringify({ nodes, edges }), result = placeEdgeLabels(nodes, edges);
  assert.equal(result.placements.size, 80);
  const exhausted = result.diagnostics.filter(item => item.message.includes('deterministic budget'));
  assert.ok(exhausted.length > 0, 'a bounded dense counterexample must reach the work budget');
  for (const warning of exhausted) {
    const source = edges.find(item => item.id === warning.edgeId)!;
    assert.deepEqual(result.placements.get(source.id), { x: source.labelX, y: source.labelY });
    assert.ok(!result.guides.some(guide => guide.sceneEdgeId === source.id));
  }
  assert.equal(JSON.stringify({ nodes, edges }), inputBytes);
});

test('a later moved caption clears the visible stroke of an earlier reserved guide', () => {
  const input = JSON.parse(readFileSync(fixture, 'utf8')) as CanvasDocument, full = buildScene(input);
  const memory = { ...full.edges.find(item => item.label === 'memory')!, labelX: 280.5, labelY: 436.1 };
  const nodes = full.nodes.filter(item => ['repeat:instance:model.Transformer.encoder', 'call:instance:model.Transformer.decoder'].includes(item.id));
  const later = edge('later-caption', 'q', 'M 300 469.5 H 315', 300.8, 438.5);
  const result = placed({ nodes, edges: [memory, later, edge('nearby-route', '', 'M 290 432 H 315', 0, 0)] });
  assert.ok(result.captionGuides.length > 0); verify(result);
  const caption = body(result.edges[1]);
  for (const guide of result.captionGuides) {
    const [a, b] = points(guide.path), radius = guide.width / 2;
    const strokeBody = { x: Math.min(a.x, b.x) - radius, y: Math.min(a.y, b.y) - radius,
      width: Math.abs(b.x - a.x) + radius * 2, height: Math.abs(b.y - a.y) + radius * 2 };
    assert.ok(Math.min(caption.x + caption.width, strokeBody.x + strokeBody.width) <= Math.max(caption.x, strokeBody.x)
      || Math.min(caption.y + caption.height, strokeBody.y + strokeBody.height) <= Math.max(caption.y, strokeBody.y), 'a nominal caption cannot enter the .8-unit visible stroke of a prior guide');
  }
});
