import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import type { Scene, SceneNode } from '../src/core/types.ts';
import type { RouteRequest, RouteResult } from '../src/core/orthogonalRouter.ts';
import { createOrthogonalRouter, ROUTE_SHORTCUT_BUDGET } from '../src/core/orthogonalRouter.ts';

// The previous router is an observation, not the geometric oracle. Its exact
// bytes remain frozen; all parsing/intersection checks below are handwritten.
const root = new URL('../../', import.meta.url);
const beforeCore = new URL('../../docs/evidence/m4-caption-route-current/before-change/inputs/studio/src/core/', import.meta.url);
const previous = await import(new URL('orthogonalRouter.ts', beforeCore).href) as typeof import('../src/core/orthogonalRouter.ts');
type Point = { x: number; y: number };
const EPS = 1e-7;
function parse(value: string): Point[] {
  const result: Point[] = []; let at = 0;
  for (const token of value.matchAll(/([MHVL])\s*([-+\d.eE]+)(?:[ ,]+([-+\d.eE]+))?/g)) {
    assert.equal(value.slice(at, token.index).trim(), ''); at = token.index! + token[0].length;
    const command = token[1], a = Number(token[2]), b = Number(token[3]);
    const point = command === 'M' || command === 'L' ? { x: a, y: b } :
      command === 'H' ? { x: a, y: result.at(-1)!.y } : { x: result.at(-1)!.x, y: a };
    assert.ok(Number.isFinite(point.x) && Number.isFinite(point.y));
    if (!result.length || result.at(-1)!.x !== point.x || result.at(-1)!.y !== point.y) result.push(point);
  }
  assert.equal(value.slice(at).trim(), ''); assert.ok(result.length >= 2);
  for (let i = 1; i < result.length; i++) assert.ok(result[i].x === result[i-1].x || result[i].y === result[i-1].y);
  return result;
}
const length = (p: Point[]) => p.slice(1).reduce((sum, b, i) => sum + Math.abs(b.x - p[i].x) + Math.abs(b.y - p[i].y), 0);
const dir = (a: Point, b: Point) => [Math.sign(b.x - a.x), Math.sign(b.y - a.y)];
const key = (p: Point) => `${Math.round(p.x * 1e6) / 1e6}:${Math.round(p.y * 1e6) / 1e6}`;
type Pair = { crossings: Set<string>; contacts: Set<string>; overlaps: Map<string, [number, number][]> };
function pair(a: Point[], b: Point[], self = false): Pair {
  const result: Pair = { crossings: new Set(), contacts: new Set(), overlaps: new Map() };
  for (let i = 1; i < a.length; i++) for (let j = self ? i + 2 : 1; j < b.length; j++) {
    const p = a[i-1], q = a[i], r = b[j-1], s = b[j], av = p.x === q.x, bv = r.x === s.x;
    if (av !== bv) {
      const v = av ? [p, q] : [r, s], h = av ? [r, s] : [p, q], point = { x: v[0].x, y: h[0].y };
      if (point.x < Math.min(h[0].x, h[1].x) - EPS || point.x > Math.max(h[0].x, h[1].x) + EPS ||
          point.y < Math.min(v[0].y, v[1].y) - EPS || point.y > Math.max(v[0].y, v[1].y) + EPS) continue;
      result.contacts.add(key(point));
      if (![a[0], a.at(-1)!, b[0], b.at(-1)!].some(end => key(end) === key(point))) result.crossings.add(key(point));
    } else if (Math.abs((av ? p.x : p.y) - (av ? r.x : r.y)) < EPS) {
      const low = Math.max(Math.min(av ? p.y : p.x, av ? q.y : q.x), Math.min(av ? r.y : r.x, av ? s.y : s.x));
      const high = Math.min(Math.max(av ? p.y : p.x, av ? q.y : q.x), Math.max(av ? r.y : r.x, av ? s.y : s.x));
      if (high < low - EPS) continue;
      if (Math.abs(high - low) < EPS) { result.contacts.add(key({ x: av ? p.x : low, y: av ? low : p.y })); continue; }
      const axis = `${av ? 'v' : 'h'}:${av ? p.x : p.y}`, intervals = result.overlaps.get(axis) ?? [];
      intervals.push([low, high]); result.overlaps.set(axis, intervals);
    }
  }
  for (const [axis, intervals] of result.overlaps) {
    const union: [number, number][] = [];
    for (const [low, high] of intervals.sort((x, y) => x[0] - y[0])) {
      if (union.length && low <= union.at(-1)![1] + EPS) union.at(-1)![1] = Math.max(union.at(-1)![1], high);
      else union.push([low, high]);
    }
    result.overlaps.set(axis, union);
  }
  return result;
}
function protectedPair(before: Pair, after: Pair, label: string) {
  for (const p of after.crossings) assert.ok(before.crossings.has(p), `${label}: new crossing ${p}`);
  for (const p of after.contacts) {
    const [x, y] = p.split(':').map(Number);
    const oldOverlap = [...before.overlaps].some(([axis, intervals]) => {
      const [orientation, coordinate] = axis.split(':');
      return Math.abs((orientation === 'v' ? x : y) - Number(coordinate)) < EPS &&
        intervals.some(([low, high]) => (orientation === 'v' ? y : x) >= low - EPS && (orientation === 'v' ? y : x) <= high + EPS);
    });
    assert.ok(before.contacts.has(p) || oldOverlap, `${label}: new contact ${p}`);
  }
  for (const [axis, intervals] of after.overlaps) for (const [low, high] of intervals) {
    assert.ok(before.overlaps.get(axis)?.some(([a, b]) => a <= low + EPS && b >= high - EPS), `${label}: new occupied overlap ${axis} ${low}/${high}`);
  }
}
function preserved(before: RouteResult[], after: RouteResult[], requests: RouteRequest[]) {
  assert.equal(after.length, before.length);
  for (let i = 0; i < after.length; i++) {
    const old = parse(before[i].path), next = parse(after[i].path);
    protectedPair(pair(old, old, true), pair(next, next, true), `${i} non-adjacent self geometry`);
    assert.deepEqual(next[0], old[0]); assert.deepEqual(next.at(-1), old.at(-1));
    assert.deepEqual(dir(next[0], next[1]), dir(old[0], old[1]));
    assert.deepEqual(dir(next.at(-1)!, next.at(-2)!), dir(old.at(-1)!, old.at(-2)!));
    for (let n = 1; n < next.length - 1; n++) {
      const a = dir(next[n-1], next[n]), b = dir(next[n], next[n+1]);
      assert.ok(a[0] * b[0] + a[1] * b[1] >= 0, 'new reversing U-turn');
    }
    if (after[i].path !== before[i].path) {
      assert.ok(length(next) <= length(old) + EPS); assert.ok(next.length <= old.length);
      assert.ok(length(next) < length(old) - EPS || next.length < old.length, 'replacement has no strict improvement');
      assert.ok(length(next.slice(0, 2)) + EPS >= Math.min(6, length(old.slice(0, 2))), 'source escape clearance reduced');
      assert.ok(length(next.slice(-2)) + EPS >= Math.min(6, length(old.slice(-2))), 'target escape clearance reduced');
    }
    for (let j = 0; j < i; j++) protectedPair(pair(parse(before[j].path), old), pair(parse(after[j].path), next),
      `${i}/${j} ${requests[i].tensorId === requests[j].tensorId ? 'same' : 'different'} tensor`);
  }
}
function requestFor(edge: Scene['edges'][number]): RouteRequest {
  const points = parse(edge.path);
  return { sourceId: edge.sourceId, targetId: edge.targetId, start: points[0], end: points.at(-1)!, preferredPath: edge.path,
    tensorId: edge.tensorId, canonicalSource: edge.source, canonicalTarget: edge.target, canonicalEdgeIds: edge.canonicalEdgeIds,
    role: edge.role, appearance: { stroke: edge.stroke, width: edge.width, dashed: edge.dashed, dashPattern: edge.dashPattern } };
}
function node(id: string, x: number, y: number, width = 20, height = 20, extras: Partial<SceneNode> = {}): SceneNode {
  return { id, x, y, width, height, localX: x, localY: y, label: id, subtitle: '', headerHeight: 10, kind: 'Linear', category: 'linear',
    fill: '#fff', stroke: '#000', glyph: 'module', expanded: false, expandable: false, pinned: false, evidence: 'source', ports: [], ...extras };
}
function fixture() {
  const nodes = [node('from', 0, 0), node('to', 80, 100)];
  const requests: RouteRequest[] = [{ sourceId: 'from', targetId: 'to', start: { x: 10, y: 20 }, end: { x: 90, y: 100 },
    preferredPath: 'M 10 20 V 40 H 150 V 80 H 90 V 100', tensorId: 'features' }];
  return { nodes, requests };
}

test('shortcut source inputs are bound to previous router and evidence candidates, not model-name heuristics', () => {
  const manifest = JSON.parse(readFileSync(new URL('docs/evidence/m4-caption-route-current/before-change/manifest.json', root), 'utf8'));
  const entry = manifest.inputs.find((i: { path: string }) => i.path === 'studio/src/core/orthogonalRouter.ts');
  const bytes = readFileSync(new URL(entry.snapshot, root));
  assert.equal(bytes.length, entry.bytes); assert.equal(createHash('sha256').update(bytes).digest('hex'), entry.sha256);
  const geometry = JSON.parse(readFileSync(new URL('docs/evidence/m4-visual-next-current/review/historical-document-current-geometry.json', root), 'utf8'));
  assert.equal(geometry.records.length, 9); assert.equal(geometry.records.reduce((sum: number, r: { safeShorterRouteProposals: unknown[] }) => sum + r.safeShorterRouteProposals.length, 0), 21,
    'the frozen named JSON has 21 candidates; no claimed 22nd candidate is invented');
});

test('independent pair sensor rejects split-vertex and collinear contacts, changed positions and new same-tensor overlaps', () => {
  const p = (text: string) => parse(text);
  assert.deepEqual(pair(p('M 0 0 H 10 H 20'), p('M 10 -10 V 0 V 10')).crossings, new Set(['10:0']));
  assert.throws(() => protectedPair(pair(p('M 0 0 H 20'), p('M 30 -10 V 10')),
    pair(p('M 0 0 H 30 V 10'), p('M 30 -10 V 10')), 'vertex'), /new crossing|new contact|new occupied overlap/);
  assert.throws(() => protectedPair(pair(p('M 0 0 H 20'), p('M 25 0 H 40')),
    pair(p('M 0 0 H 25'), p('M 25 0 H 40')), 'collinear'), /new contact/);
  assert.throws(() => protectedPair(pair(p('M 0 0 H 20'), p('M 5 -10 V 10')),
    pair(p('M 0 1 H 20'), p('M 5 -10 V 10')), 'moved'), /new crossing/);
  assert.throws(() => protectedPair(pair(p('M 0 0 H 20'), p('M 5 1 H 15')),
    pair(p('M 0 1 H 20'), p('M 5 1 H 15')), 'same tensor'), /new occupied overlap/);
});

test('unconflicted arbitrary typed route shortens without source/canonical evidence, object mutation or nondeterminism', () => {
  const f = fixture(), unchanged = JSON.stringify(f), old = previous.createOrthogonalRouter(f.nodes).batch(f.requests);
  const next = createOrthogonalRouter(f.nodes).batch(f.requests); preserved(old, next, f.requests);
  assert.ok(length(parse(next[0].path)) < length(parse(old[0].path)) - 50);
  assert.equal(next[0].blockedBy.length, 0); assert.equal(JSON.stringify(f), unchanged);
  assert.deepEqual(next, createOrthogonalRouter(f.nodes).batch(f.requests));
});

const report = JSON.parse(readFileSync(new URL('docs/evidence/m4-visual-next-current/review/historical-document-current-geometry.json', root), 'utf8')) as {
  records: { caseId: string; currentSceneBinding: { path: string; bytes: number; sha256: string } }[] };
for (const record of report.records) test(`source-backed ${record.caseId} shortens only pairwise protected routes and preserves nodes/source facts`, () => {
  const bytes = readFileSync(new URL(record.currentSceneBinding.path, root));
  assert.equal(bytes.length, record.currentSceneBinding.bytes); assert.equal(createHash('sha256').update(bytes).digest('hex'), record.currentSceneBinding.sha256);
  const scene = JSON.parse(bytes.toString()) as Scene, original = JSON.stringify(scene);
  const requests = scene.edges.map(requestFor), old = previous.createOrthogonalRouter(scene.nodes).batch(requests);
  const next = createOrthogonalRouter(scene.nodes).batch(requests); preserved(old, next, requests);
  assert.equal(JSON.stringify(scene), original); assert.deepEqual(next, createOrthogonalRouter(scene.nodes).batch(requests));
  if (record.caseId === 'transformer-level1-paper-180' || record.caseId === 'residual_cnn-level2-paper-180')
    assert.ok(next.some((route, i) => route.path !== old[i].path), 'real source-backed frontier should exercise the generic shortcut');
  if (record.caseId === 'transformer-level0-paper-180') assert.deepEqual(next, old,
    'count-safe historical proposals do not authorize relocated intersections or occupied overlaps');
});

test('obstacles, Repeat backplates and expanded ancestor headers retain a safe route rather than take the Manhattan shortcut', () => {
  for (const obstacle of [node('wall', 30, 35, 35, 50), node('stack', 30, 35, 35, 50, { repeat: { count: 3, sharing: 'independent' } })]) {
    const f = fixture(); f.nodes.push(obstacle); const old = previous.createOrthogonalRouter(f.nodes).batch(f.requests), next = createOrthogonalRouter(f.nodes).batch(f.requests);
    preserved(old, next, f.requests);
    for (const [i, route] of next.entries()) for (let n = 1, points = parse(route.path); n < points.length; n++) {
      const a = points[n-1], b = points[n];
      for (const offset of obstacle.repeat ? [0, 3.5, 7] : [0]) {
        const left = obstacle.x + offset - 6, right = left + obstacle.width + 12, top = obstacle.y + offset - 6, bottom = top + obstacle.height + 12;
        assert.equal(a.x === b.x ? a.x > left + EPS && a.x < right - EPS && Math.max(Math.min(a.y,b.y),top) < Math.min(Math.max(a.y,b.y),bottom) - EPS :
          a.y > top + EPS && a.y < bottom - EPS && Math.max(Math.min(a.x,b.x),left) < Math.min(Math.max(a.x,b.x),right) - EPS, false, `route${i} padding/body intrusion`);
      }
    }
  }
  const f = fixture(); f.nodes.push(node('owner', -20, 35, 180, 80, { expanded: true, headerHeight: 18 })); f.nodes[1].parentId = 'owner';
  const old = previous.createOrthogonalRouter(f.nodes).batch(f.requests), next = createOrthogonalRouter(f.nodes).batch(f.requests);
  preserved(old, next, f.requests); assert.equal(next[0].blockedBy.length, 0);
});

test('covered endpoint, invalid reversal and work-cap inputs preserve honest fallback routes', () => {
  const blocked = fixture(); blocked.nodes.push(node('cover', 0, 10));
  const result = createOrthogonalRouter(blocked.nodes).batch(blocked.requests);
  assert.equal(result[0].path, blocked.requests[0].preferredPath); assert.ok(result[0].blockedBy.includes('cover'));
  const reverse = fixture(); reverse.requests[0].preferredPath = 'M 10 20 V 40 V 30 H 90 V 100';
  assert.equal(createOrthogonalRouter(reverse.nodes).batch(reverse.requests)[0].path, reverse.requests[0].preferredPath);
  const cap = fixture(); for (let n = 0; n < ROUTE_SHORTCUT_BUDGET.maxNodes; n++) cap.nodes.push(node(`distant${n}`, 1000 + n*30, 1000));
  assert.equal(createOrthogonalRouter(cap.nodes).batch(cap.requests)[0].path, cap.requests[0].preferredPath);
  const tooMany = fixture(); tooMany.requests = Array.from({ length: ROUTE_SHORTCUT_BUDGET.maxRoutes + 1 }, () => ({ ...tooMany.requests[0] }));
  assert.ok(createOrthogonalRouter(tooMany.nodes).batch(tooMany.requests).every(route => route.path === tooMany.requests[0].preferredPath));
  const complex = fixture(); complex.nodes[1] = node('to', 190, 300);
  const route = ['M 10 20']; let x = 10, y = 20;
  for (let n = 0; n < 35; n++) { route.push(`V ${++y}`, `H ${++x}`); }
  route.push('V 280', 'H 200', 'V 300'); complex.requests[0].preferredPath = route.join(' '); complex.requests[0].end = { x: 200, y: 300 };
  assert.ok(parse(complex.requests[0].preferredPath).length > ROUTE_SHORTCUT_BUDGET.maxPointsPerRoute);
  assert.equal(createOrthogonalRouter(complex.nodes).batch(complex.requests)[0].path, complex.requests[0].preferredPath);
});

test('same-tensor and different-tensor peer geometry cannot gain hidden crossings contacts or overlaps', () => {
  for (const tensor of ['shared', 'distinct']) {
    const f = fixture(); f.requests[0].tensorId = 'shared';
    f.nodes.push(node('guard-start', 45, 40, 10, 10), node('guard-end', 105, 60, 10, 10));
    f.requests.push({ sourceId: 'guard-start', targetId: 'guard-end', start: { x: 50, y: 50 }, end: { x: 110, y: 60 },
      preferredPath: 'M 50 50 V 65 H 100 V 55 H 110 V 60', tensorId: tensor });
    const old = previous.createOrthogonalRouter(f.nodes).batch(f.requests), next = createOrthogonalRouter(f.nodes).batch(f.requests);
    preserved(old, next, f.requests);
  }
});

test('a 0.005-world-unit moved same-tensor crossing cannot masquerade as its old geometric point', () => {
  const nodes = [node('a', 0, 0), node('b', 100, 0), node('c', 50, -40), node('d', 50, 40)];
  const requests: RouteRequest[] = [
    { sourceId: 'a', targetId: 'b', start: { x: 20, y: 10 }, end: { x: 100, y: 10 },
      preferredPath: 'M 20 10 H 40 V 10.005 H 80 V 10 H 100', tensorId: 'shared' },
    { sourceId: 'c', targetId: 'd', start: { x: 60, y: -20 }, end: { x: 60, y: 40 }, preferredPath: 'M 60 -20 V 40', tensorId: 'shared' }
  ];
  const old = previous.createOrthogonalRouter(nodes).batch(requests), next = createOrthogonalRouter(nodes).batch(requests);
  preserved(old, next, requests);
  assert.equal(next[0].path, requests[0].preferredPath, 'straightening would relocate its protected crossing by 0.005');
});

test('shortcut cannot make its source escape hit its own endpoint through a non-adjacent segment', () => {
  const nodes = [node('from', -4, 0, 8, 8), node('to', 0, -108, 8, 8), node('wall', -16, -96, 8, 24)];
  const requests: RouteRequest[] = [{ sourceId: 'from', targetId: 'to', start: { x: 0, y: 0 }, end: { x: 0, y: -104 },
    preferredPath: 'M 0 0 V -24 H -16 V -64 H 56 V -104 H 40 V -128 H -48 V -104 H 0', tensorId: 'any' }];
  const old = previous.createOrthogonalRouter(nodes).batch(requests), next = createOrthogonalRouter(nodes).batch(requests);
  assert.equal(old[0].path, requests[0].preferredPath); assert.equal(old[0].blockedBy.length, 0);
  assert.deepEqual(pair(parse(old[0].path), parse(old[0].path), true), { crossings: new Set(), contacts: new Set(), overlaps: new Map() });
  preserved(old, next, requests);
  assert.notEqual(next[0].path, 'M 0 0 V -114 H -6 V -104 H 0');
  assert.ok(length(parse(next[0].path)) < length(parse(old[0].path)), 'a checked simple alternative can still improve the route');
});

test('existing self contacts and crossings remain eligible for a checked shorter subset', () => {
  const nodes = [node('from', -4, 0, 8, 8), node('to', 0, -108, 8, 8), node('wall', -16, -96, 8, 24)];
  const requests: RouteRequest[] = [{ sourceId: 'from', targetId: 'to', start: { x: 0, y: 0 }, end: { x: 0, y: -104 },
    preferredPath: 'M 0 0 V -150 H -16 V -64 H 56 V -104 H 40 V -128 H -48 V -104 H 0', tensorId: 'any' }];
  const old = previous.createOrthogonalRouter(nodes).batch(requests), next = createOrthogonalRouter(nodes).batch(requests);
  const existing = pair(parse(old[0].path), parse(old[0].path), true);
  assert.ok(existing.crossings.size > 0); assert.ok(existing.contacts.has('0:-104'));
  preserved(old, next, requests);
  assert.ok(length(parse(next[0].path)) < length(parse(old[0].path)));
  assert.ok(pair(parse(next[0].path), parse(next[0].path), true).contacts.has('0:-104'), 'an old contact is preserved, not silently treated as forbidden input');
});

test('independent self sensor ignores adjacent bends but detects non-adjacent crossing, point contact and retracing', () => {
  const p = (s: string) => parse(s), self = (s: string) => pair(p(s), p(s), true);
  assert.deepEqual(self('M 0 0 H 10 V 10 H 20'), { crossings: new Set(), contacts: new Set(), overlaps: new Map() });
  assert.ok(self('M 0 0 H 20 V 20 H 10 V -10').crossings.has('10:0'));
  assert.ok(self('M 0 0 V -114 H -6 V -104 H 0').contacts.has('0:-104'));
  assert.deepEqual(self('M 0 0 H 20 V 20 H 10 V 0 H 30').overlaps.get('h:0'), [[10, 20]]);
});
