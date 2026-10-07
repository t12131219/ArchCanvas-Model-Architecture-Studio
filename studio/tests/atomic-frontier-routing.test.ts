import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { applyVisualBatch, buildExportScene, buildScene, createDocument, createHistory, reduceHistory, renderSvg } from '../src/core/index.ts';
import { indexAtomicRelations } from '../src/core/atomicFrontier.ts';
import { refineReadableRoutes } from '../src/core/readableRouting.ts';
import type { Architecture, ArchitectureNode, CanvasDocument, Scene, SceneNode } from '../src/core/types.ts';
import type { RoutePoint, RouteRequest, RouteResult } from '../src/core/orthogonalRouter.ts';

// Independent public-path parser and geometric checks. No product projection,
// outline, path parser or collision helper is used as the assertion oracle.
function points(path: string): RoutePoint[] {
  let x = 0, y = 0;
  return [...path.matchAll(/([MLHV])\s*(-?[\d.]+)(?:\s+(-?[\d.]+))?/g)].map(([, c, a, b]) => {
    if (c === 'M' || c === 'L') { x = +a; y = +b; } else if (c === 'H') x = +a; else y = +a;
    return { x, y };
  });
}
const routeLength = (path: string) => points(path).slice(1).reduce((sum, p, i) => sum + Math.abs(p.x - points(path)[i].x) + Math.abs(p.y - points(path)[i].y), 0);
function assertCanonical(scene: Scene, document: CanvasDocument) {
  assert.deepEqual([...scene.hiddenEdges, ...scene.edges.flatMap(e => e.canonicalEdgeIds)].sort(), document.architecture.edges.map(e => e.id).sort());
  assert.equal(scene.sourceDigest, document.architecture.sourceDigest); assert.equal(scene.irDigest, document.architecture.irDigest);
  const edges = new Map(document.architecture.edges.map(e => [e.id, e]));
  const byId = new Map(scene.nodes.map(n => [n.id, n]));
  const ancestors = (id: string) => { const result = new Set<string>(); let parent = byId.get(id)?.parentId;
    while (parent) { result.add(parent); parent = byId.get(parent)?.parentId; } return result; };
  for (const e of scene.edges) {
    const canonical = edges.get(e.id)!;
    assert.deepEqual(e.source, canonical.source); assert.deepEqual(e.target, canonical.target); assert.equal(e.tensorId, canonical.tensorId); assert.equal(e.role, canonical.role);
    const path = points(e.path), owners = new Set([...ancestors(e.sourceId), ...ancestors(e.targetId)]);
    for (const [id, direction, endpoint] of [[e.sourceId, 'out', path[0]], [e.targetId, 'in', path.at(-1)!]] as const) {
      const node = byId.get(id)!;
      const port = node.ports.find(p => p.direction === direction && e.canonicalEdgeIds.every(id => p.canonicalEdgeIds.includes(id)) && Math.abs(p.x - endpoint.x) < .051 && Math.abs(p.y - endpoint.y) < .051);
      assert.ok(port, `Missing attached canonical port for ${e.id}/${direction}`);
      assert.deepEqual(port.canonicalBindings, document.architecture.edges.filter(e => port.canonicalEdgeIds.includes(e.id)).map(e => direction === 'in' ? e.target : e.source));
    }
    if (scene.diagnostics.some(d => d.edgeId === e.id && d.code === 'layout-route-blocked')) continue;
    for (const n of scene.nodes) {
      const plates = n.repeat && !n.expanded ? [0, 3.5, 7] : [0];
      for (const offset of plates) {
        const top = n.y + offset, left = n.x + offset, right = left + n.width, bottom = top + (owners.has(n.id) && n.expanded ? n.headerHeight : n.height);
        for (let i = 1; i < path.length; i++) {
          const a = path[i - 1], b = path[i];
          const intrusion = a.x === b.x ? a.x > left + .05 && a.x < right - .05 && Math.max(Math.min(a.y, b.y), top + .05) < Math.min(Math.max(a.y, b.y), bottom - .05)
            : a.y > top + .05 && a.y < bottom - .05 && Math.max(Math.min(a.x, b.x), left + .05) < Math.min(Math.max(a.x, b.x), right - .05);
          assert.equal(intrusion, false, `${e.id} enters ${n.id} body/plate/header`);
        }
      }
    }
  }
}
function fixture(caseId: string) {
  return JSON.parse(readFileSync(new URL(`../../docs/evidence/browser-visual-matrix-boundary-final/captures/${caseId}/canvas.json`, import.meta.url), 'utf8')) as CanvasDocument;
}
function literalArchitecture(): Architecture {
  const n = (id: string, parentId?: string, children: string[] = [], opaque = false): ArchitectureNode => ({ id, label: id, kind: children.length ? 'Module' : 'Linear', category: children.length ? 'container' : 'linear', parentId, children, parameters: {}, evidence: opaque ? 'opaque' : 'source',
    ports: [{ id: 'in', name: 'input', direction: 'in', ordinal: 0, role: 'data' }, { id: 'out', name: 'output', direction: 'out', ordinal: 0, role: 'data' }] });
  return { schemaVersion: 1, id: 'literal', label: 'Literal', entry: 'model:Literal', sourceDigest: 'source', irDigest: 'ir', sources: [], diagnostics: [],
    nodes: [n('root', undefined, ['input', 'block', 'opaque', 'output']), n('input', 'root'), n('block', 'root', ['nested']), n('nested', 'block', ['atomic']), n('atomic', 'nested'), n('opaque', 'root', ['opaque-child'], true), n('opaque-child', 'opaque'), n('output', 'root')],
    edges: [
      { id: 'coarse', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'block', portId: 'in' }, tensorId: 'x', role: 'data' },
      { id: 'middle', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'nested', portId: 'in' }, tensorId: 'x', role: 'data' },
      { id: 'atomic', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'atomic', portId: 'in' }, tensorId: 'x', role: 'data' },
      { id: 'distinct-tensor', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'block', portId: 'in' }, tensorId: 'y', role: 'data' },
      { id: 'distinct-role', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'block', portId: 'in' }, tensorId: 'x', role: 'residual' },
      { id: 'opaque-coarse', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'opaque', portId: 'in' }, tensorId: 'opaque-x', role: 'data' },
      { id: 'opaque-child', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'opaque-child', portId: 'in' }, tensorId: 'opaque-x', role: 'data' },
      { id: 'exit', source: { nodeId: 'atomic', portId: 'out' }, target: { nodeId: 'output', portId: 'in' }, tensorId: 'out', role: 'data' },
    ] };
}
test('deepest source relation index folds bottom-up and never confuses a tensor name with a binding', () => {
  const architecture = literalArchitecture(), before = JSON.stringify(architecture), index = indexAtomicRelations(architecture);
  let doc = createDocument(architecture);
  assert.deepEqual(buildScene(doc).edges.find(e => e.id === 'coarse')!.canonicalEdgeIds, ['coarse', 'middle', 'atomic']);
  doc = applyVisualBatch(doc, [{ type: 'expand', id: 'block', expanded: true }]);
  let scene = buildScene(doc); assert.ok(scene.hiddenEdges.includes('coarse'));
  assert.equal(scene.edges.find(e => e.id === 'middle')!.targetId, 'nested');
  doc = applyVisualBatch(doc, [{ type: 'expand', id: 'nested', expanded: true }, { type: 'expand', id: 'opaque', expanded: true }]);
  scene = buildScene(doc); assert.ok(scene.hiddenEdges.includes('coarse')); assert.ok(scene.hiddenEdges.includes('middle'));
  assert.equal(scene.edges.find(e => e.id === 'atomic')!.targetId, 'atomic');
  for (const id of ['distinct-tensor', 'distinct-role', 'opaque-coarse', 'opaque-child']) assert.ok(scene.edges.some(e => e.canonicalEdgeIds.includes(id)), id);
  assert.deepEqual(index.refinements.get('coarse')?.target, ['nested', 'atomic']);
  assert.equal(JSON.stringify(architecture), before); assertCanonical(scene, doc);
});

test('real MLP expanded network has one atomic input lane and no parent/child arrow ambiguity', () => {
  const doc = fixture('mlp-level1-paper-180'), bytes = JSON.stringify(doc), scene = buildScene(doc);
  assert.ok(scene.hiddenEdges.includes('edge:1')); assert.ok(!scene.edges.some(e => e.canonicalEdgeIds.includes('edge:1')));
  assert.equal(scene.edges.find(e => e.id === 'edge:2')!.targetId, 'call:instance:model.MLP.network.0');
  assert.equal(scene.edges.filter(e => e.sourceId === 'input:model.MLP:features').length, 1);
  assertCanonical(scene, doc); assert.equal(JSON.stringify(doc), bytes);
});
test('detail export keeps folded atomic coverage and does not resurrect coarse parent arrows', () => {
  const doc = fixture('transformer-level2-paper-180'), bytes = JSON.stringify(doc), selected = doc.expandedIds.find(id => doc.architecture.nodes.find(node => node.id === id)?.children.length)!;
  const detail = buildExportScene(doc, { nodeId: selected });
  assertCanonical(detail, doc);
  assert.ok(detail.nodes.some(node => node.id === selected));
  assert.equal(JSON.stringify(doc), bytes);
  assert.deepEqual(detail, buildExportScene(JSON.parse(JSON.stringify(doc)), { nodeId: selected }));
});
for (const caseId of ['mlp-level0-paper-180', 'mlp-level1-paper-180', 'residual_cnn-level0-paper-180', 'residual_cnn-level1-paper-180', 'residual_cnn-level2-paper-180', 'transformer-level0-paper-180', 'transformer-level1-paper-180', 'transformer-level2-paper-180', 'transformer-level3-paper-180']) {
  test(`atomic frontier ${caseId} keeps source facts canonical ports exports and four-direction history`, () => {
    const doc = fixture(caseId), bytes = JSON.stringify(doc), initial = buildScene(doc);
    assertCanonical(initial, doc); assert.equal(renderSvg(buildExportScene(doc)), renderSvg(initial));
    const movable = initial.nodes.find(n => !n.expandable && !['input', 'output'].includes(n.category));
    if (movable) for (const [dx, dy] of [[-8, 0], [8, 0], [0, -8], [0, 8]]) {
      const history = reduceHistory(createHistory(doc), { type: 'apply', operations: [{ type: 'move', ids: [movable.id], dx, dy }] });
      const scene = buildScene(history.document); assertCanonical(scene, history.document);
      assert.deepEqual(history.document.architecture, doc.architecture); assert.deepEqual(scene.sourceFacts, initial.sourceFacts);
      assert.deepEqual(scene, buildScene(JSON.parse(JSON.stringify(history.document))));
      const undo = reduceHistory(history, { type: 'undo' }), redo = reduceHistory(undo, { type: 'redo' });
      assert.deepEqual(undo.document.layout, doc.layout); assert.deepEqual(redo.document.layout, history.document.layout);
    }
    assert.equal(JSON.stringify(doc), bytes);
  });
}

function routeCase() {
  const node = (id: string, x: number, y: number): SceneNode => ({ id, x, y, width: 20, height: 20, localX: x, localY: y, label: id, subtitle: '', headerHeight: 20, kind: 'Linear', category: 'linear', fill: '#fff', stroke: '#444', glyph: 'operator', expanded: false, expandable: false, pinned: false, evidence: 'source', ports: [] });
  const nodes = [node('a', 0, 0), node('b', 100, 120)], path = 'M 10 20 V 36 H 250 V 104 H 110 V 120';
  const request: RouteRequest = { sourceId: 'a', targetId: 'b', start: { x: 10, y: 20 }, end: { x: 110, y: 120 }, preferredPath: path };
  const result: RouteResult = { path, points: points(path), changed: false, blockedBy: [] };
  return { nodes, requests: [request], baseline: [result] };
}
test('clear arbitrary route takes the local Manhattan corridor without touching nodes or endpoints', () => {
  const input = routeCase(), bytes = JSON.stringify(input), result = refineReadableRoutes(input.nodes, input.requests, input.baseline)[0];
  assert.equal(routeLength(result.path), 200); assert.ok(routeLength(result.path) < routeLength(input.baseline[0].path));
  assert.deepEqual(result.points[0], input.requests[0].start); assert.deepEqual(result.points.at(-1), input.requests[0].end);
  assert.equal(JSON.stringify(input), bytes);
});
test('route improvement cannot create a new peer crossing even for equal tensor identifiers', () => {
  for (const sameTensor of [false, true]) {
    const input = routeCase();
    input.nodes.push({ ...input.nodes[0], id: 'c', x: 50, y: 50 }, { ...input.nodes[0], id: 'd', x: 150, y: 50 });
    const peer = 'M 70 60 H 150';
    input.requests[0].tensorId = 'tensor';
    input.requests.push({ sourceId: 'c', targetId: 'd', start: { x: 70, y: 60 }, end: { x: 150, y: 60 }, preferredPath: peer, tensorId: sameTensor ? 'tensor' : 'different' });
    input.baseline.push({ path: peer, points: points(peer), changed: false, blockedBy: [] });
    const result = refineReadableRoutes(input.nodes, input.requests, input.baseline);
    // A direct vertical arrival x=110 through y=60 would hit this peer and
    // its endpoint card. The valid shortened lane stays outside that band.
    for (let i = 1, p = result[0].points; i < p.length; i++) {
      assert.equal(p[i].x === p[i - 1].x && p[i].x > 70 && p[i].x < 150 && Math.min(p[i].y, p[i - 1].y) < 60 && Math.max(p[i].y, p[i - 1].y) > 60, false);
    }
    assert.equal(result[1].path, peer);
  }
});
