import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { applyVisualBatch, buildExportScene, buildScene, createDocument, createHistory, reduceHistory, renderSvg } from '/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/m4-caption-stability-current/before-change/inputs/studio/src/core/index.ts';
import * as before from '/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/m4-caption-stability-current/before-change/inputs/studio/src/core/index.ts';
import type { Architecture, CanvasDocument, EdgeRole, Scene, SceneEdge } from '/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/core/types.ts';

const fixture = new URL('/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/m4-caption-route-current/browser/pre-ui/saved-transformer-final-envelope.json', import.meta.url);
const encoder = 'repeat:instance:model.Transformer.encoder', root = 'call:instance:model.Transformer';
const sourceDocument = () => (JSON.parse(readFileSync(fixture, 'utf8')) as { document: CanvasDocument }).document;
const copy = <T>(input: T): T => JSON.parse(JSON.stringify(input));
type Point = [number, number]; type Box = [number, number, number, number];

// Independent public-coordinate checks. No product parser, label/outline,
// distance, intersection or guide-placement helper is imported as an oracle.
function points(path: string): Point[] {
  const tokens = path.match(/[MLHV]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?/g)!;
  const result: Point[] = [];
  for (let i = 0; i < tokens.length;) {
    const command = tokens[i++];
    const p: Point = command === 'M' || command === 'L' ? [+tokens[i++], +tokens[i++]]
      : command === 'H' ? [+tokens[i++], result.at(-1)![1]] : [result.at(-1)![0], +tokens[i++]];
    if (result.length) assert.ok(p[0] === result.at(-1)![0] || p[1] === result.at(-1)![1]);
    if (!result.length || p.some((value, j) => value !== result.at(-1)![j])) result.push(p);
  }
  return result;
}
function lines(path: string): [Point, Point][] { const p = points(path); return p.slice(1).map((b, i) => [p[i], b]); }
function enters(line: [Point, Point], box: Box, inclusive = false) {
  const [a, b] = line, [l, t, r, bottom] = box;
  return a[0] === b[0] ? (inclusive ? a[0] >= l && a[0] <= r : a[0] > l && a[0] < r)
    && (inclusive ? Math.max(a[1], b[1]) >= t && Math.min(a[1], b[1]) <= bottom : Math.max(Math.min(a[1], b[1]), t) < Math.min(Math.max(a[1], b[1]), bottom))
    : (inclusive ? a[1] >= t && a[1] <= bottom : a[1] > t && a[1] < bottom)
    && (inclusive ? Math.max(a[0], b[0]) >= l && Math.min(a[0], b[0]) <= r : Math.max(Math.min(a[0], b[0]), l) < Math.min(Math.max(a[0], b[0]), r));
}
const caption = (edge: SceneEdge): Box => [edge.labelX - 2, edge.labelY - 11, edge.labelX + [...edge.label].length * 9 + 2, edge.labelY + 5];
function overlaps(a: Box, b: Box) { return Math.min(a[2], b[2]) > Math.max(a[0], b[0]) && Math.min(a[3], b[3]) > Math.max(a[1], b[1]); }
function verifyCaptions(scene: Scene) {
  const bodies: Box[] = scene.nodes.flatMap(n => n.expanded ? [[n.x, n.y, n.x + n.width, n.y + n.headerHeight] as Box]
    : [0, ...(n.repeat ? [3.5, 7] : [])].map(s => [n.x + s, n.y + s, n.x + s + n.width, n.y + s + n.height] as Box));
  bodies.push(...scene.annotations.map(a => [a.x, a.y, a.x + a.width, a.y + a.height] as Box));
  for (const edge of scene.edges.filter(e => e.role === 'memory' && e.label)) {
    const warned = scene.diagnostics.some(d => d.edgeId === edge.id && ['layout-edge-label-blocked', 'layout-edge-label-association'].includes(d.code ?? ''));
    const box = caption(edge), guides = (scene.captionGuides ?? []).filter(g => g.sceneEdgeId === edge.id);
    if (warned) { assert.equal(guides.length, 0, 'a diagnosed unresolved caption cannot claim a clear guide'); continue; }
    for (const body of [...bodies, ...scene.edges.filter(e => e.id !== edge.id && e.label).map(caption)]) assert.equal(overlaps(box, body), false);
    for (const other of scene.edges) for (const line of lines(other.path)) assert.equal(enters(line, box), false, 'resolved captions cannot cover canonical routes');
    const distance = Math.min(...lines(edge.path).map(([a, b]) => Math.hypot(Math.max(box[0] - Math.max(a[0], b[0]), Math.min(a[0], b[0]) - box[2], 0),
      Math.max(box[1] - Math.max(a[1], b[1]), Math.min(a[1], b[1]) - box[3], 0))));
    assert.ok(distance <= 18 || guides.length === 1, 'a far caption needs an explicit owned-route guide');
    for (const guide of guides) {
      const p = points(guide.path); assert.equal(p.length, 2); assert.ok(Math.abs(p[0][0] - p[1][0]) + Math.abs(p[0][1] - p[1][1]) <= 48);
      assert.ok(lines(edge.path).some(([a, b]) => a[0] === b[0] ? p[0][0] === a[0] && p[0][1] > Math.min(a[1], b[1]) && p[0][1] < Math.max(a[1], b[1])
        : p[0][1] === a[1] && p[0][0] > Math.min(a[0], b[0]) && p[0][0] < Math.max(a[0], b[0])));
      for (const other of scene.edges.filter(e => e.id !== edge.id)) for (const [a, b] of lines(other.path)) {
        const clearance = (guide.width + other.width) / 2;
        assert.equal(enters([p[0], p[1]], [Math.min(a[0], b[0]) - clearance, Math.min(a[1], b[1]) - clearance,
          Math.max(a[0], b[0]) + clearance, Math.max(a[1], b[1]) + clearance], true), false);
      }
    }
  }
}
function bindings(scene: Scene) { return scene.edges.map(({ label: _l, labelX: _x, labelY: _y, ...edge }) => edge); }
function protectedScene(old: Scene, scene: Scene) {
  assert.deepEqual(scene.nodes, old.nodes); assert.deepEqual(bindings(scene), bindings(old));
  assert.deepEqual(scene.sourceFacts, old.sourceFacts); assert.deepEqual(scene.hiddenEdges, old.hiddenEdges);
  assert.equal(scene.sourceDigest, old.sourceDigest); assert.equal(scene.irDigest, old.irDigest);
  for (const edge of scene.edges) {
    const path = points(edge.path), source = scene.nodes.find(n => n.id === edge.sourceId)!, target = scene.nodes.find(n => n.id === edge.targetId)!;
    // Initial preferred routes round to 0.1; router-generated routes round to
    // 0.01. Both are public serialization of full-precision Scene ports, so
    // allow only the larger rounding error (0.05), never arbitrary detachment.
    const attached = (value: number, displayed: number) => Math.abs(value - displayed) <= .050000001;
    assert.ok(source.ports.some(p => p.direction === 'out' && edge.canonicalEdgeIds.every(id => p.canonicalEdgeIds.includes(id)) && attached(p.x, path[0][0]) && attached(p.y, path[0][1])), `${edge.id} source endpoint`);
    assert.ok(target.ports.some(p => p.direction === 'in' && edge.canonicalEdgeIds.every(id => p.canonicalEdgeIds.includes(id)) && attached(p.x, path.at(-1)![0]) && attached(p.y, path.at(-1)![1])), `${edge.id} target endpoint`);
  }
}

test('source memory captions survive vertical threshold boundaries and all four movement directions in whole/detail and both presets', () => {
  const base = sourceDocument(), bytes = JSON.stringify(base);
  for (const preset of ['paper', 'monochrome'] as const) for (const [dx, dy] of [[0, -24], [0, -16], [0, -15], [0, -14], [0, 0], [0, 14], [0, 15], [0, 16], [0, 24], [-24, 0], [24, 0]]) {
    const doc = applyVisualBatch(base, [{ type: 'page', page: { preset } }, { type: 'move', ids: [encoder], dx, dy }]), unchanged = JSON.stringify(doc);
    for (const scope of [{}, { nodeId: root }]) {
      const old = before.buildExportScene(doc, scope), scene = buildExportScene(doc, scope);
      const memory = scene.edges.find(e => e.id === 'edge:44')!;
      assert.equal(memory.label, 'memory', `preset=${preset} dx=${dx} dy=${dy} scope=${JSON.stringify(scope)}`);
      protectedScene(old, scene); verifyCaptions(scene); assert.deepEqual(scene, buildExportScene(copy(doc), scope));
    }
    assert.equal(JSON.stringify(doc), unchanged); assert.deepEqual(doc.architecture, base.architecture);
  }
  assert.equal(JSON.stringify(base), bytes);
});

test('the actual +24 encoder counterexample keeps its routed endpoints and visible memory after undo/redo and JSON reopening', () => {
  const base = sourceDocument(); let history = createHistory(base);
  history = reduceHistory(history, { type: 'apply', operations: [{ type: 'move', ids: [encoder], dx: 0, dy: 24 }] });
  const edited = copy(history.document), scene = buildScene(edited), memory = scene.edges.find(e => e.id === 'edge:44')!;
  assert.equal(memory.path, 'M 177 503 V 509 H 281 V 404 H 380.67 V 410', 'this label-only change cannot reroute the independently captured actual gesture');
  assert.equal(memory.label, 'memory'); verifyCaptions(scene); protectedScene(before.buildScene(edited), scene);
  history = reduceHistory(history, { type: 'undo' }); assert.deepEqual({ ...history.document, revision: base.revision }, base);
  history = reduceHistory(history, { type: 'redo' }); assert.deepEqual({ ...history.document, revision: edited.revision }, edited);
  assert.deepEqual(buildScene(copy(history.document)), buildScene(history.document));
  const svg = renderSvg(scene), metadata = JSON.parse(svg.match(/<metadata>(.*?)<\/metadata>/s)![1].replaceAll('&quot;', '"').replaceAll('&amp;', '&').replaceAll('&lt;', '<').replaceAll('&gt;', '>'));
  assert.deepEqual(metadata.renderedBindings.find((e: { sceneEdgeId: string }) => e.sceneEdgeId === memory.id), {
    sceneEdgeId: memory.id, canonicalEdgeIds: memory.canonicalEdgeIds, source: memory.source, target: memory.target, tensorId: memory.tensorId, role: memory.role });
  assert.ok(svg.includes('>memory</text>')); assert.deepEqual(edited.architecture, base.architecture);
});

test('source expansion and collapse retain every visible memory caption without adding hidden bindings or facts', () => {
  const base = sourceDocument(); let doc = applyVisualBatch(base, [{ type: 'move', ids: [encoder], dx: 0, dy: 24 }]);
  for (const expanded of [true, false, true, false]) {
    doc = applyVisualBatch(doc, [{ type: 'expand', id: encoder, expanded }]); const bytes = JSON.stringify(doc);
    for (const scope of [{}, { nodeId: root }]) {
      const scene = buildExportScene(doc, scope); assert.ok(scene.edges.some(e => e.role === 'memory'));
      for (const e of scene.edges.filter(e => e.role === 'memory')) assert.equal(e.label, 'memory');
      protectedScene(before.buildExportScene(doc, scope), scene); verifyCaptions(scene);
    }
    assert.equal(JSON.stringify(doc), bytes); assert.deepEqual(doc.architecture, base.architecture);
  }
});

function generic(role: EdgeRole, label?: string): CanvasDocument {
  const architecture: Architecture = { schemaVersion: 1, id: 'literal-caption-stability', entry: 'oracle:Literal', label: 'Literal caption stability',
    sourceDigest: 'literal-source-not-executed', irDigest: 'literal-ir-not-executed', diagnostics: [], sources: [],
    nodes: [{ id: 'owner', label: 'Owner', kind: 'Block', category: 'container', children: ['left', 'right'], ports: [], parameters: {}, evidence: 'source' },
      ...['left', 'right'].map(id => ({ id, parentId: 'owner', label: id, kind: 'Linear', category: 'linear', children: [], parameters: {}, evidence: 'source' as const,
        ports: [{ id: 'in', name: 'in', direction: 'in' as const, role: 'data', ordinal: 0 }, { id: 'out', name: 'out', direction: 'out' as const, role: 'data', ordinal: 0 }] }))],
    edges: [{ id: 'literal-edge', source: { nodeId: 'left', portId: 'out' }, target: { nodeId: 'right', portId: 'in' }, role, tensorId: 'literal-tensor', ...(label === undefined ? {} : { label }) }] };
  const document = createDocument(architecture), scene = buildScene(document), a = scene.nodes.find(n => n.id === 'left')!, b = scene.nodes.find(n => n.id === 'right')!;
  return applyVisualBatch(document, [{ type: 'move', ids: ['left'], dx: 80 - a.x, dy: 400 - a.y }, { type: 'move', ids: ['right'], dx: 340 - b.x, dy: 100 - b.y }]);
}

test('default memory naming is generic while explicit empty/authored labels and other roles retain their contracts', () => {
  for (const role of ['data', 'residual', 'mask', 'memory'] as const) for (const label of [undefined, '', '研究者指定说明']) {
    const doc = generic(role, label), bytes = JSON.stringify(doc), expected = label ?? (role === 'memory' ? 'memory' : '');
    for (const scope of [{}, { nodeId: 'owner' }]) {
      const scene = buildExportScene(doc, scope); assert.equal(scene.edges[0].label, expected); protectedScene(before.buildExportScene(doc, scope), scene); verifyCaptions(scene);
      if (label === '') assert.ok(!(scene.captionGuides ?? []).some(g => g.sceneEdgeId === 'literal-edge'));
    }
    assert.equal(JSON.stringify(doc), bytes);
  }
});

test('a genuinely blocked moved memory retains its text and reports association failure instead of disappearing', () => {
  const moved = applyVisualBatch(sourceDocument(), [{ type: 'move', ids: [encoder], dx: 0, dy: 24 }]);
  const doc = applyVisualBatch(moved, [{ type: 'annotation', annotation: { id: 'all-caption-space-blocked', text: 'An independently declared occupied note', x: 100, y: 330, width: 440, height: 300 } }]);
  const bytes = JSON.stringify(doc), scene = buildScene(doc), memory = scene.edges.find(e => e.id === 'edge:44')!;
  assert.equal(memory.label, 'memory'); assert.ok(scene.diagnostics.some(d => d.edgeId === memory.id && ['layout-edge-label-blocked', 'layout-edge-label-association'].includes(d.code ?? '')));
  assert.ok(!(scene.captionGuides ?? []).some(g => g.sceneEdgeId === memory.id)); assert.ok(renderSvg(scene).includes('>memory</text>'));
  assert.equal(JSON.stringify(doc), bytes); protectedScene(before.buildScene(doc), scene);
});
