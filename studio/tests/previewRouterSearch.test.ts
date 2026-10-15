import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const code = readFileSync(new URL('../public/preview/yworks_edge_router_lab/router.js', import.meta.url), 'utf8');
function load(source: string) { const context = vm.createContext({}); vm.runInContext(source, context); return context.EdgeRouterLabRouting; }
const router = load(code);
const EPS = 1e-6;
// Independent clipping oracle, retaining the original general segment algorithm.
function clip(a: any, b: any, r: any) {
  const inset = { x: r.x + EPS, y: r.y + EPS, w: r.w - EPS * 2, h: r.h - EPS * 2 };
  let lo = 0, hi = 1;
  const p = [a.x - b.x, b.x - a.x, a.y - b.y, b.y - a.y];
  const q = [a.x - inset.x, inset.x + inset.w - a.x, a.y - inset.y, inset.y + inset.h - a.y];
  for (let i = 0; i < 4; i++) {
    if (Math.abs(p[i]) < EPS) { if (q[i] < 0) return false; }
    else { const t = q[i] / p[i]; if (p[i] < 0) lo = Math.max(lo, t); else hi = Math.min(hi, t); if (lo > hi) return false; }
  }
  return lo <= hi && hi > EPS && lo < 1 - EPS;
}

test('fast obstacle clipping preserves open boundaries, reversed segments and endpoint tolerances', () => {
  let seed = 19661014;
  const random = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 2 ** 32);
  const compare = (a: any, b: any, r: any) => assert.equal(router.intersectsRect(a, b, r), clip(a, b, r), JSON.stringify({ a, b, r }));
  const r = { x: 10, y: 20, w: 100, h: 40 };
  for (const x of [10-EPS, 10, 10+EPS, 10+2*EPS, 50, 110-EPS, 110, 110+EPS]) {
    for (const y of [20, 20+EPS, 30, 60-EPS, 60]) {
      for (const d of [0, EPS/2, EPS, 20, -20, 100, -100]) {
        compare({ x, y }, { x, y: y+d }, r);
        compare({ x, y }, { x: x+d, y }, r);
      }
    }
  }
  for (let i = 0; i < 20000; i++) {
    const rect = { x: random()*600-200, y: random()*600-200, w: random()*150, h: random()*150 };
    const a = { x: random()*1000-300, y: random()*1000-300 };
    const b = i%3 === 0 ? { x: a.x, y: random()*1000-300 } : i%3 === 1 ? { x: random()*1000-300, y: a.y } : { x: random()*1000-300, y: random()*1000-300 };
    compare(a, b, rect); compare(b, a, rect);
  }
});

test('A* keeps the Dijkstra route cost through obstacles, crossings, fixed ports and waypoints', () => {
  // Disable only the heuristic to use uniform-cost search as the optimality oracle.
  const begin = code.indexOf('    // A straight leg or one elbow can already attain');
  const end = code.indexOf('    let xs =', begin);
  assert.ok(begin >= 0 && end > begin);
  const uniform = code.slice(0, begin) + code.slice(end);
  const dijkstra = load(uniform.replace('const remaining=p=>Math.abs(p.x-end.x)+Math.abs(p.y-end.y);', 'const remaining=p=>0;'));
  const nodes = [
    { id: 's', x: 30, y: 90, w: 40, h: 40 }, { id: 't', x: 510, y: 270, w: 40, h: 40 },
    { id: 'a', x: 170, y: 20, w: 70, h: 260 }, { id: 'b', x: 330, y: 160, w: 70, h: 260 },
  ];
  const paths = [[{ x: 100, y: 340 }, { x: 460, y: 340 }]];
  const edge = { source: 's', target: 't', fixedSource: { side: 'right', fraction: .5 }, fixedTarget: { side: 'left', fraction: .5 } };
  for (const extra of [{}, { crossingCost: 500 }, { crossingCost: 120, edgeSpacing: 8 }, { preserve: true }]) {
    const options = { width: 620, height: 470, margin: 10, stub: 24, bendCost: 36, ...extra };
    const candidate = extra.preserve ? { ...edge, waypoints: [{ x: 280, y: 320 }] } : edge;
    const result = router.routeEdge(candidate, nodes, paths, options), reference = dijkstra.routeEdge(candidate, nodes, paths, options);
    assert.equal(result.ok, true, result.reason); assert.equal(reference.ok, true, reference.reason);
    assert.ok(result.expanded > 0, 'the fixture must exercise the visibility search');
    assert.ok(Math.abs(result.cost-reference.cost) < EPS, JSON.stringify({ result, reference }));
    assert.ok(result.points.slice(1).every((b: any, i: number) => !nodes.some(n => router.intersectsRect(result.points[i], b, n))));
  }
});

test('short waypoint legs match a full uniform-cost search across rotations, mirrors and scales', () => {
  const begin = code.indexOf('    // A straight leg or one elbow can already attain');
  const end = code.indexOf('    let xs =', begin);
  const dijkstra = load((code.slice(0, begin) + code.slice(end)).replace(
    'const remaining=p=>Math.abs(p.x-end.x)+Math.abs(p.y-end.y);', 'const remaining=p=>0;'));
  const opposite: Record<string, string> = { left: 'right', right: 'left', top: 'bottom', bottom: 'top' };
  const turn: Record<string, string> = { left: 'top', top: 'right', right: 'bottom', bottom: 'left' };
  for (const scale of [.5, 1, 2]) for (const mirror of [false, true]) for (let turns = 0; turns < 4; turns++) for (const crowded of [false, true]) {
    const transform = (p: any) => {
      let q = { x: mirror ? 600 - p.x : p.x, y: p.y };
      for (let i = 0; i < turns; i++) q = { x: 600 - q.y, y: q.x };
      return { x: q.x * scale, y: q.y * scale };
    };
    const side = (s: string) => { if (mirror && ['left', 'right'].includes(s)) s = opposite[s]; for (let i = 0; i < turns; i++) s = turn[s]; return s; };
    const nodes = [{ id: 's', x: 40, y: 80, w: 40, h: 40 }, { id: 't', x: 480, y: 340, w: 40, h: 40 }].map(n => {
      const corners = [transform(n), transform({ x: n.x + n.w, y: n.y + n.h })];
      return { id: n.id, x: Math.min(...corners.map(p => p.x)), y: Math.min(...corners.map(p => p.y)),
        w: Math.abs(corners[1].x - corners[0].x), h: Math.abs(corners[1].y - corners[0].y) };
    });
    const edge = { source: 's', target: 't', fixedSource: { side: side('right'), fraction: .5 },
      fixedTarget: { side: side('left'), fraction: .5 }, waypoints: [{ x: 240, y: 100 }, { x: 240, y: 360 }].map(transform) };
    const paths = crowded ? [[{ x: 200, y: 200 }, { x: 300, y: 200 }].map(transform)] : [];
    const options = { width: 600 * scale, height: 600 * scale, margin: 4 * scale, stub: 14 * scale,
      bendCost: 40 * scale, crossingCost: 180 * scale, edgeSpacing: 10 * scale, preserve: true };
    const result = router.routeEdge(edge, nodes, paths, options), reference = dijkstra.routeEdge(edge, nodes, paths, options);
    assert.equal(result.ok, reference.ok);
    assert.equal(result.ok, true, JSON.stringify({ scale, mirror, turns, crowded, result }));
    assert.ok(Math.abs(result.cost - reference.cost) < EPS, JSON.stringify({ result, reference }));
  }
});

test('a stored route must visit preserved waypoints in the requested order before early acceptance', () => {
  const nodes = [{ id: 's', x: 10, y: 100, w: 30, h: 40 }, { id: 't', x: 240, y: 100, w: 30, h: 40 }];
  const reversed = [{ x: 40, y: 120 }, { x: 54, y: 120 }, { x: 54, y: 80 }, { x: 180, y: 80 },
    { x: 180, y: 120 }, { x: 100, y: 120 }, { x: 100, y: 180 }, { x: 200, y: 180 },
    { x: 200, y: 120 }, { x: 240, y: 120 }];
  const waypoints = [{ x: 100, y: 120 }, { x: 180, y: 120 }];
  const edge = { source: 's', target: 't', fixedSource: { side: 'right', fraction: .5 },
    fixedTarget: { side: 'left', fraction: .5 }, route: reversed, waypoints };
  const result = router.routeEdge(edge, nodes, [], { width: 300, height: 240, margin: 4, stub: 14,
    bendCost: 40, preserve: true, firstLegal: true });
  assert.equal(result.ok, true, result.reason);
  let distance = 0;
  const visits = waypoints.map(point => {
    let at: number | undefined;
    for (let i = 1; i < result.points.length; i++) {
      const a = result.points[i - 1], b = result.points[i], length = router.dist(a, b);
      if (router.dist(a, point) + router.dist(point, b) <= length + EPS) { at = distance + router.dist(a, point); break; }
      distance += length;
    }
    distance = 0;
    assert.notEqual(at, undefined);
    return at!;
  });
  assert.ok(visits[0] <= visits[1], 'the old reverse-order route cannot be retained');
});

test('coincident gate legs retain signed turn cost and match the complete search', () => {
  const begin = code.indexOf('    // A straight leg or one elbow can already attain');
  const end = code.indexOf('    let xs =', begin);
  const full = load(code.slice(0, begin) + code.slice(end));
  const nodes = [{ id: 's', x: 30, y: 60, w: 30, h: 40 }, { id: 't', x: 400, y: 270, w: 30, h: 40 }];
  for (const middle of [[{ x: 180, y: 80 }, { x: 180, y: 80 }, { x: 180, y: 290 }],
    [{ x: 180, y: 80 }, { x: 180, y: 290 }, { x: 180, y: 290 }]]) {
    const edge = { source: 's', target: 't', fixedSource: { side: 'right', fraction: .5 },
      fixedTarget: { side: 'left', fraction: .5 }, waypoints: middle };
    const settings = { width: 500, height: 400, margin: 4, stub: 14, bendCost: 40, preserve: true };
    const actual = router.routeEdge(edge, nodes, [], settings), expected = full.routeEdge(edge, nodes, [], settings);
    assert.equal(actual.ok, true); assert.equal(expected.ok, true);
    assert.ok(Math.abs(actual.cost - expected.cost) < EPS, JSON.stringify({ actual, expected }));
  }
});

test('route-local gate memo preserves obstacle, heading and legacy terminal-stem distinctions', () => {
  const instrument = (source: string) => load(source.replace(
    'function search(start, end, obstacles, priorPaths, settings, boundary, incoming = 0, outgoing = 0) {',
    'function search(start, end, obstacles, priorPaths, settings, boundary, incoming = 0, outgoing = 0) { root.searchCalls=(root.searchCalls||0)+1;')
    .replace('const api = { routeEdge', 'const api = { get searchCalls() { return root.searchCalls || 0; }, routeEdge'));
  const uncached = code.replace('if (legCache.has(key)) return legCache.get(key);', '')
    .replace('if (legCache.size < 256) legCache.set(key, result);', '');
  const cached = instrument(code), reference = instrument(uncached);
  const nodes = [{ id: 's', x: 30, y: 70, w: 40, h: 40 }, { id: 't', x: 410, y: 270, w: 40, h: 40 },
    { id: 'block', x: 210, y: 140, w: 50, h: 90 }];
  const edge = { source: 's', target: 't', waypoints: [{ x: 180, y: 100 }, { x: 180, y: 100 }, { x: 180, y: 250 }] };
  for (const tagged of [false, true]) {
    const path: any = [{ x: 50, y: 90 }, { x: 100, y: 90 }, { x: 100, y: 140 }];
    if (tagged) path.wire = 'independent';
    const options = { width: 520, height: 400, margin: 4, stub: 14, bendCost: 40, crossingCost: 180,
      edgeSpacing: 10, preserve: true,
      obstaclesForPorts: (s: any, t: any) => s.side === t.side ? [{ x: 140, y: 120, w: 20, h: 20 }] : [] };
    const actual = cached.routeEdge(edge, nodes, [path], options), expected = reference.routeEdge(edge, nodes, [path], options);
    assert.equal(actual.ok, expected.ok);
    assert.equal(actual.ok, true, actual.reason);
    assert.ok(Math.abs(actual.cost - expected.cost) < EPS, JSON.stringify({ tagged, actual, expected }));
    assert.deepEqual(JSON.parse(JSON.stringify(actual.points)), JSON.parse(JSON.stringify(expected.points)));
  }
  assert.ok(cached.searchCalls < reference.searchCalls, 'repeated exact gate legs should be solved once');
});
