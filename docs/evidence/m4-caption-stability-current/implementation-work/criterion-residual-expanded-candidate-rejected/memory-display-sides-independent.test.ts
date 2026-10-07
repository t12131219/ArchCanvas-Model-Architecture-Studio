import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { applyVisualBatch, buildScene, buildExportScene, createDocument, renderSvg } from '../src/core/index.ts';
import * as labelOnly from '../../docs/evidence/m4-caption-stability-current/implementation-work/label-only-snapshot/core/index.ts';
import type { Architecture, CanvasDocument, EdgeRole, Scene, SceneEdge } from '../src/core/types.ts';

const fixture = new URL('../../docs/evidence/m4-caption-route-current/browser/pre-ui/saved-transformer-final-envelope.json', import.meta.url);
const encoder = 'repeat:instance:model.Transformer.encoder', root = 'call:instance:model.Transformer';
const source = () => JSON.parse(readFileSync(fixture, 'utf8')).document as CanvasDocument;
type Point = [number, number];
function points(path: string): Point[] {
  const tokens = path.match(/[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?/g) ?? [];
  assert.equal(tokens.join(''), path.replace(/\s+/g, ''), 'unparsed path bytes');
  const p: Point[] = [];
  for (let i = 0; i < tokens.length;) {
    const command = tokens[i++]; let next: Point;
    if (command === 'M' && !p.length || command === 'L' && p.length) next = [+tokens[i++], +tokens[i++]];
    else if (command === 'H' && p.length) next = [+tokens[i++], p.at(-1)![1]];
    else if (command === 'V' && p.length) next = [p.at(-1)![0], +tokens[i++]];
    else throw new Error(`unsupported command/subpath ${command}`);
    assert.ok(next.every(Number.isFinite)); assert.ok(!p.length || next[0] === p.at(-1)![0] || next[1] === p.at(-1)![1]);
    if (!p.length || next.some((n, j) => n !== p.at(-1)![j])) p.push(next);
  }
  assert.ok(p.length >= 2); return p;
}
function length(path: string) { const p = points(path); return p.slice(1).reduce((n, b, i) => n + Math.abs(b[0] - p[i][0]) + Math.abs(b[1] - p[i][1]), 0); }
function peerContacts(first: string, second: string) {
  const a = points(first), b = points(second), crossings = new Set<string>(), intervals = new Map<string, [number, number][]>();
  const endpoint = (x: number, y: number) => [a[0], a.at(-1)!, b[0], b.at(-1)!].some(p => p[0] === x && p[1] === y);
  for (let i = 1; i < a.length; i++) for (let j = 1; j < b.length; j++) {
    const av = a[i][0] === a[i - 1][0], bv = b[j][0] === b[j - 1][0];
    if (av !== bv) {
      const [v, vp, h, hp] = av ? [a[i], a[i - 1], b[j], b[j - 1]] : [b[j], b[j - 1], a[i], a[i - 1]];
      if (v[0] >= Math.min(h[0], hp[0]) && v[0] <= Math.max(h[0], hp[0]) && h[1] >= Math.min(v[1], vp[1]) && h[1] <= Math.max(v[1], vp[1]) && !endpoint(v[0], h[1])) crossings.add(`${v[0]}/${h[1]}`);
    } else if (av ? a[i][0] === b[j][0] : a[i][1] === b[j][1]) {
      const coordinate = av ? 1 : 0, low = Math.max(Math.min(a[i][coordinate], a[i - 1][coordinate]), Math.min(b[j][coordinate], b[j - 1][coordinate]));
      const high = Math.min(Math.max(a[i][coordinate], a[i - 1][coordinate]), Math.max(b[j][coordinate], b[j - 1][coordinate]));
      if (high > low) { const key = `${av}/${a[i][1 - coordinate]}`; intervals.set(key, [...intervals.get(key) ?? [], [low, high]]); }
    }
  }
  let overlap = 0;
  for (const spans of intervals.values()) {
    spans.sort((a, b) => a[0] - b[0]); let [low, high] = spans[0];
    for (const [l, h] of spans.slice(1)) if (l <= high) high = Math.max(high, h); else { overlap += high - low; low = l; high = h; }
    overlap += high - low;
  }
  return { crossings: crossings.size, overlap };
}
function sideNormals(edge: SceneEdge, minimumLead = 6) {
  const p = points(edge.path), a = p[0], b = p[1], z = p.at(-1)!, y = p.at(-2)!;
  assert.equal(b[1], a[1], `${edge.id} source must leave horizontally`); assert.ok(b[0] - a[0] >= minimumLead - .011, `${edge.id} source right lead`);
  assert.equal(y[1], z[1], `${edge.id} target must arrive horizontally`); assert.ok(z[0] - y[0] >= minimumLead - .011, `${edge.id} target left lead`);
}
function expectedSide(scene: Scene, edge: SceneEdge) {
  const a = scene.nodes.find(n => n.id === edge.sourceId)!, b = scene.nodes.find(n => n.id === edge.targetId)!;
  const repeat = a.repeat && !a.expanded ? 7 : 0, targetRepeat = b.repeat && !b.expanded ? 7 : 0;
  return edge.role === 'memory' && !a.expanded && !b.expanded && b.x - (a.x + a.width + repeat) >= 12
    && Math.min(a.y + a.height + repeat, b.y + b.height + targetRepeat) > Math.max(a.y, b.y);
}
function normalProjection(scene: Scene, edge: SceneEdge) {
  if (expectedSide(scene, edge)) { sideNormals(edge); return; }
  const a = scene.nodes.find(n => n.id === edge.sourceId)!, b = scene.nodes.find(n => n.id === edge.targetId)!, p = points(edge.path);
  assert.ok(Math.abs(p[0][1] - (a.y + a.height + (a.repeat && !a.expanded ? 7 : 0))) <= .05);
  assert.ok(Math.abs(p.at(-1)![1] - b.y) <= .05);
}
function semantic(scene: Scene) {
  return { sourceDigest: scene.sourceDigest, irDigest: scene.irDigest, sourceFacts: scene.sourceFacts, hiddenEdges: scene.hiddenEdges,
    nodes: scene.nodes.map(({ ports: _p, ...node }) => node),
    edges: scene.edges.map(({ path: _p, labelX: _x, labelY: _y, ...edge }) => edge) };
}
function endpoints(scene: Scene, doc: CanvasDocument) {
  for (const e of scene.edges) for (const [id, direction, endpoint] of [[e.sourceId, 'out', points(e.path)[0]], [e.targetId, 'in', points(e.path).at(-1)!]] as const) {
    const n = scene.nodes.find(n => n.id === id)!;
    const p = n.ports.find(p => p.direction === direction && e.canonicalEdgeIds.every(id => p.canonicalEdgeIds.includes(id)) && Math.abs(p.x - endpoint[0]) <= .050000001 && Math.abs(p.y - endpoint[1]) <= .050000001);
    assert.ok(p, `${e.id} detached ${direction}`);
    assert.deepEqual(p.canonicalBindings, doc.architecture.edges.filter(e => p.canonicalEdgeIds.includes(e.id)).map(e => direction === 'out' ? e.source : e.target));
  }
}
function clearOrDiagnosed(scene: Scene) {
  const nodes = new Map(scene.nodes.map(n => [n.id, n]));
  for (const e of scene.edges) {
    const ancestors = new Set<string>(); for (const id of [e.sourceId, e.targetId]) {
      let parent = nodes.get(id)!.parentId; while (parent) { ancestors.add(parent); parent = nodes.get(parent)?.parentId; }
    }
    for (const n of scene.nodes) {
      const shifts = n.repeat && !n.expanded ? [0, 3.5, 7] : [0];
      for (const shift of shifts) {
        const l = n.x + shift, r = l + n.width, t = n.y + shift, b = t + (ancestors.has(n.id) && n.expanded ? n.headerHeight : n.height);
        if (ancestors.has(n.id) && !n.expanded) continue;
        const p = points(e.path), hit = p.slice(1).some((v, i) => v[0] === p[i][0]
          ? v[0] > l + .05 && v[0] < r - .05 && Math.max(Math.min(v[1], p[i][1]), t + .05) < Math.min(Math.max(v[1], p[i][1]), b - .05)
          : v[1] > t + .05 && v[1] < b - .05 && Math.max(Math.min(v[0], p[i][0]), l + .05) < Math.min(Math.max(v[0], p[i][0]), r - .05));
        if (hit) assert.ok(scene.diagnostics.some(d => d.code === 'layout-route-blocked' && d.edgeId === e.id && d.objectIds?.includes(n.id)), `${e.id} crosses ${n.id} without a route diagnostic`);
      }
    }
  }
}
function literal(role: EdgeRole, targetX: number, targetY: number, obstacle = false, repeat = false): CanvasDocument {
  const ids = ['a', 'b', ...(obstacle ? ['obstacle'] : [])];
  const architecture: Architecture = { schemaVersion: 1, id: 'literal-side-normal', entry: 'oracle:Literal', label: 'Independent side-normal geometry',
    sourceDigest: 'literal-source-never-executed', irDigest: 'literal-ir-never-executed', diagnostics: [], sources: [],
    nodes: ids.map(id => ({ id, label: id, kind: 'Linear', category: 'linear', children: [], parameters: {}, evidence: 'source',
      ...(id === 'a' && repeat ? { repeat: { count: 3, sharing: 'independent' as const } } : {}),
      ports: [{ id: 'in', name: 'in', direction: 'in', role: 'data', ordinal: 0 }, { id: 'out', name: 'out', direction: 'out', role: 'data', ordinal: 0 }] })),
    edges: [{ id: 'binding', source: { nodeId: 'a', portId: 'out' }, target: { nodeId: 'b', portId: 'in' }, role, tensorId: 'literal-tensor' }] };
  const doc = createDocument(architecture), scene = buildScene(doc), a = scene.nodes.find(n => n.id === 'a')!, b = scene.nodes.find(n => n.id === 'b')!;
  const ops = [{ type: 'move' as const, ids: ['a'], dx: 80 - a.x, dy: 400 - a.y }, { type: 'move' as const, ids: ['b'], dx: targetX - b.x, dy: targetY - b.y }];
  if (obstacle) { const c = scene.nodes.find(n => n.id === 'obstacle')!; ops.push({ type: 'move', ids: ['obstacle'], dx: 350 - c.x, dy: 220 - c.y }); }
  return applyVisualBatch(doc, ops);
}

test('source-backed memory has continuous right/left ports across ±14/15/16/24/48 with owned six-unit normals', () => {
  const base = source(), bytes = JSON.stringify(base);
  for (const preset of ['paper', 'monochrome'] as const) {
    const lengths = new Map<number, number>();
    for (const dy of [-48, -24, -16, -15, -14, 0, 14, 15, 16, 24, 48]) {
      const doc = applyVisualBatch(base, [{ type: 'page', page: { preset } }, { type: 'move', ids: [encoder], dx: 0, dy }]);
      for (const scope of [{}, { nodeId: root }]) {
        const scene = buildExportScene(doc, scope), before = labelOnly.buildExportScene(doc, scope), e = scene.edges.find(e => e.id === 'edge:44')!;
        assert.deepEqual(semantic(scene), semantic(before)); sideNormals(e); endpoints(scene, doc); clearOrDiagnosed(scene);
        if (!Object.hasOwn(scope, 'nodeId')) lengths.set(dy, length(e.path));
        assert.equal(e.label, 'memory'); assert.ok(!scene.diagnostics.some(d => d.code === 'layout-route-blocked' && d.edgeId === e.id));
        assert.deepEqual(scene, buildExportScene(JSON.parse(JSON.stringify(doc)), scope));
      }
      assert.deepEqual(doc.architecture, base.architecture);
    }
    for (const [a, b] of [[14, 15], [15, 16], [-14, -15], [-15, -16]]) assert.ok(Math.abs(lengths.get(a)! - lengths.get(b)!) <= 1.01, 'one-unit drag cannot become a page-scale detour');
  }
  assert.equal(JSON.stringify(base), bytes);
});

test('generic far targets retain bottom/top fallback while a shared vertical band uses safe side normals and binding metadata', () => {
  for (const y of [-500, 100, 350, 400, 450, 700, 1300]) for (const obstacle of [false, true]) {
    const doc = literal('memory', obstacle ? 700 : 340, y, obstacle), bytes = JSON.stringify(doc), scene = buildScene(doc), e = scene.edges[0];
    normalProjection(scene, e); endpoints(scene, doc); clearOrDiagnosed(scene); assert.deepEqual(semantic(scene), semantic(labelOnly.buildScene(doc)));
    if (!expectedSide(scene, e)) assert.equal(e.path, labelOnly.buildScene(doc).edges[0].path);
    assert.equal(JSON.stringify(doc), bytes);
    const svg = renderSvg(scene); assert.ok(svg.includes('>memory</text>'));
    const meta = JSON.parse(svg.match(/<metadata>(.*?)<\/metadata>/s)![1].replaceAll('&quot;', '"').replaceAll('&amp;', '&').replaceAll('&lt;', '<').replaceAll('&gt;', '>'));
    assert.deepEqual(meta.renderedBindings[0], { sceneEdgeId: e.id, canonicalEdgeIds: e.canonicalEdgeIds, source: e.source, target: e.target, role: e.role, tensorId: e.tensorId });
  }
});

test('horizontal touching/overlap boundaries and other roles retain bottom/top projections', () => {
  const probe = buildScene(literal('memory', 340, 100)), a = probe.nodes.find(n => n.id === 'a')!;
  for (const role of ['memory', 'data', 'mask', 'residual'] as const) for (const x of [a.x + a.width - .1, a.x + a.width, a.x + a.width + .1, 340]) for (const y of [100, 400]) {
    const doc = literal(role, x, y), scene = buildScene(doc), before = labelOnly.buildScene(doc), edge = scene.edges[0];
    const s = scene.nodes.find(n => n.id === edge.sourceId)!, t = scene.nodes.find(n => n.id === edge.targetId)!;
    const p = points(edge.path), side = expectedSide(scene, edge);
    if (side) { assert.ok(Math.abs(p[0][0] - (s.x + s.width)) <= .05); assert.ok(Math.abs(p.at(-1)![0] - t.x) <= .05); }
    else { normalProjection(scene, edge); if (role !== 'memory') { assert.deepEqual(scene.nodes, before.nodes); assert.equal(edge.path, before.edges[0].path); } }
    endpoints(scene, doc); clearOrDiagnosed(scene); assert.deepEqual(semantic(scene), semantic(before));
  }
});

test('narrow gaps and far vertical bands retain bottom/top fallback; sufficient shared-band space keeps six-unit side normals', () => {
  const s = buildScene(literal('memory', 340, 100)).nodes.find(n => n.id === 'a')!;
  for (const gap of [.1, 1, 6, 11.9, 12, 12.1]) for (const y of [100, 400, 700]) {
    const doc = literal('memory', s.x + s.width + gap, y), scene = buildScene(doc), e = scene.edges[0];
    normalProjection(scene, e); endpoints(scene, doc); clearOrDiagnosed(scene);
    assert.equal(e.label, 'memory'); assert.deepEqual(semantic(scene), semantic(labelOnly.buildScene(doc)));
  }
});

test('actual repeat outline sets the side boundary; full cardinal moves retain canonical endpoints or explicit blocked diagnostics', () => {
  const base = source();
  for (const dx of [-48, -24, 0, 24, 34, 35, 36, 42, 48, 80]) for (const dy of [-48, 0, 48]) {
    const doc = applyVisualBatch(base, [{ type: 'move', ids: [encoder], dx, dy }]), scene = buildScene(doc), e = scene.edges.find(e => e.id === 'edge:44')!;
    const s = scene.nodes.find(n => n.id === e.sourceId)!, t = scene.nodes.find(n => n.id === e.targetId)!;
    normalProjection(scene, e);
    endpoints(scene, doc); clearOrDiagnosed(scene); assert.equal(e.label, 'memory'); assert.deepEqual(doc.architecture, base.architecture);
    assert.deepEqual(semantic(scene), semantic(labelOnly.buildScene(doc)));
  }
  const s = buildScene(literal('memory', 340, 100, false, true)).nodes.find(n => n.id === 'a')!;
  for (const delta of [-.1, 0, .1]) {
    const doc = literal('memory', s.x + s.width + 7 + delta, 100, false, true), scene = buildScene(doc), e = scene.edges[0], p = points(e.path);
    normalProjection(scene, e);
    endpoints(scene, doc); clearOrDiagnosed(scene);
  }
});

test('the independent dy24/48 residual-mask overlap counterexample fails criterion-only but clears with a six-unit preferred residual', () => {
  const base = source();
  for (const preset of ['paper', 'monochrome'] as const) for (const dy of [15, 24, 48]) for (const scope of [{}, { nodeId: root }]) {
    const doc = applyVisualBatch(base, [{ type: 'page', page: { preset } }, { type: 'move', ids: [encoder], dx: 0, dy }]);
    const scene = buildExportScene(doc, scope), before = labelOnly.buildExportScene(doc, scope);
    const residual = scene.edges.find(e => e.id === 'edge:51')!, p = points(residual.path);
    assert.equal(p[1][0], p[0][0]); assert.equal(p[1][1] - p[0][1], 6);
    assert.equal(p.at(-1)![0], p.at(-2)![0]); assert.ok(p.at(-1)![1] - p.at(-2)![1] >= 6);
    for (const id of ['edge:45', 'edge:46']) {
      const current = peerContacts(scene.edges.find(e => e.id === id)!.path, residual.path);
      const prior = peerContacts(before.edges.find(e => e.id === id)!.path, before.edges.find(e => e.id === residual.id)!.path);
      assert.equal(current.overlap, 0, `${id}/edge51 must not share an unrelated visible stroke`);
      assert.ok(current.crossings <= prior.crossings, 'removing overlap cannot create more point contacts');
    }
    endpoints(scene, doc); clearOrDiagnosed(scene); assert.deepEqual(semantic(scene), semantic(before));
  }
});
