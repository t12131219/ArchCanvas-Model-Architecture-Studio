import type { RouteRequest, RouteResult, RoutePoint } from './core/orthogonalRouter.ts';

type Box = { id: string; x: number; y: number; width: number; height: number };
type Rect = { left: number; top: number; right: number; bottom: number };
const EPS = .001, GAP = 8, LEAD = 12;
const round = (n: number) => Math.round(n * 100) / 100;
const same = (a: RoutePoint, b: RoutePoint) => Math.abs(a.x - b.x) < EPS && Math.abs(a.y - b.y) < EPS;
const direction = (a: RoutePoint, b: RoutePoint) => a.x < b.x ? 0 : a.y < b.y ? 1 : a.x > b.x ? 2 : 3;
const vectors = [{ x: 1, y: 0 }, { x: 0, y: 1 }, { x: -1, y: 0 }, { x: 0, y: -1 }];
const segments = (points: RoutePoint[]) => points.slice(1).map((b, i) => [points[i], b] as const);

function touches(a: RoutePoint, b: RoutePoint, c: RoutePoint, d: RoutePoint) {
  const av = a.x === b.x, cv = c.x === d.x;
  if (av !== cv) {
    const [v, w, h, k] = av ? [a, b, c, d] : [c, d, a, b];
    return v.x >= Math.min(h.x, k.x) - EPS && v.x <= Math.max(h.x, k.x) + EPS &&
      h.y >= Math.min(v.y, w.y) - EPS && h.y <= Math.max(v.y, w.y) + EPS;
  }
  return Math.abs((av ? a.x : a.y) - (cv ? c.x : c.y)) < EPS &&
    Math.max(av ? Math.min(a.y, b.y) : Math.min(a.x, b.x), av ? Math.min(c.y, d.y) : Math.min(c.x, d.x)) <=
    Math.min(av ? Math.max(a.y, b.y) : Math.max(a.x, b.x), av ? Math.max(c.y, d.y) : Math.max(c.x, d.x)) + EPS;
}
function enters(a: RoutePoint, b: RoutePoint, r: Rect) {
  return a.x === b.x ? a.x > r.left + EPS && a.x < r.right - EPS &&
    Math.max(Math.min(a.y, b.y), r.top + EPS) < Math.min(Math.max(a.y, b.y), r.bottom - EPS)
    : a.y > r.top + EPS && a.y < r.bottom - EPS &&
      Math.max(Math.min(a.x, b.x), r.left + EPS) < Math.min(Math.max(a.x, b.x), r.right - EPS);
}
function simplify(points: RoutePoint[]) {
  const result: RoutePoint[] = [];
  for (const p of points) {
    const point = { x: round(p.x), y: round(p.y) };
    if (result.length && same(point, result.at(-1)!)) continue;
    while (result.length > 1 && direction(result.at(-2)!, result.at(-1)!) === direction(result.at(-1)!, point)) result.pop();
    result.push(point);
  }
  return result;
}
const encode = (points: RoutePoint[]) => points.map((p, i) => !i ? `M ${p.x} ${p.y}` :
  p.x === points[i - 1].x ? `V ${p.y}` : `H ${p.x}`).join(' ');

/** Draft-only visibility search. A crossing can require several corridors,
 * which the shared renderer's conservative local proposals do not enumerate.
 * Keep that renderer's contracts intact and retain every draft edge identity.
 * Limits bound work; exhaustion keeps the original visible route. */
export const DRAFT_ROUTING_BUDGET = Object.freeze({ maxNodes: 24, maxEdges: 64, maxCells: 16_000,
  maxExpandedStates: 64_000, maxSearches: 8, maxGeometryChecks: 250_000, maxConflictChecks: 100_000 });
export function refineDraftRoutes(boxes: readonly Box[], requests: readonly RouteRequest[], input: readonly RouteResult[]): RouteResult[] {
  const results = input.map(r => ({ ...r }));
  if (boxes.length > DRAFT_ROUTING_BUDGET.maxNodes || requests.length > DRAFT_ROUTING_BUDGET.maxEdges) return results;
  const family = (i: number, j: number) => requests[i].tensorId !== undefined && requests[i].tensorId === requests[j].tensorId;
  let conflictChecks = 0, conflictExhausted = false;
  const conflict = (i: number, j: number) => {
    if (family(i, j)) return false;
    for (const [a, b] of segments(results[i].points)) for (const [c, d] of segments(results[j].points)) {
      if (conflictChecks++ >= DRAFT_ROUTING_BUDGET.maxConflictChecks) { conflictExhausted = true; return false; }
      if (touches(a, b, c, d)) return true;
    }
    return false;
  };
  let searches = 0, geometryChecks = 0;
  // Long fan-out routes are tried first on equal pressure: this lets a branch
  // use an exterior corridor while short ordered merge arrivals stay local.
  const order = requests.map((_, i) => ({ i, pressure: requests.reduce((n, _, j) => n + Number(i !== j && conflict(i, j)), 0),
    length: segments(results[i].points).reduce((n, [a, b]) => n + Math.abs(a.x - b.x) + Math.abs(a.y - b.y), 0) }))
    .sort((a, b) => b.pressure - a.pressure || b.length - a.length || a.i - b.i);
  if (conflictExhausted) return results;
  for (const { i } of order) {
    if (results[i].blockedBy.length) continue;
    const needsRoute = requests.some((_, j) => i !== j && conflict(i, j));
    if (conflictExhausted) break;
    if (!needsRoute) continue;
    if (searches++ >= DRAFT_ROUTING_BUDGET.maxSearches) break;
    const request = requests[i], original = simplify(results[i].points);
    if (original.length < 2) continue;
    const start = original[0], end = original.at(-1)!;
    const sd = direction(start, original[1]), td = direction(original.at(-2)!, end);
    const a = { x: round(start.x + vectors[sd].x * LEAD), y: round(start.y + vectors[sd].y * LEAD) };
    const b = { x: round(end.x - vectors[td].x * LEAD), y: round(end.y - vectors[td].y * LEAD) };
    const obstacles = boxes.map(box => {
      const pad = box.id === request.sourceId || box.id === request.targetId ? 0 : 6;
      return { left: box.x - pad, top: box.y - pad, right: box.x + box.width + pad, bottom: box.y + box.height + pad };
    });
    const occupied = results.flatMap((r, j) => i === j || family(i, j) ? [] : segments(r.points));
    const clear = (p: RoutePoint, q: RoutePoint) => {
      for (const r of obstacles) {
        if (geometryChecks++ >= DRAFT_ROUTING_BUDGET.maxGeometryChecks || enters(p, q, r)) return false;
      }
      for (const [c, d] of occupied) {
        if (geometryChecks++ >= DRAFT_ROUTING_BUDGET.maxGeometryChecks || touches(p, q, c, d)) return false;
      }
      return true;
    };
    if (!clear(start, a) || !clear(b, end)) continue;
    const axis = (key: 'x' | 'y') => {
      const values = new Set([a[key], b[key]]);
      for (const r of obstacles) for (const v of key === 'x' ? [r.left, r.right] : [r.top, r.bottom])
        for (const offset of [-GAP, 0, GAP]) values.add(round(v + offset));
      for (const [p, q] of occupied) for (const v of [p[key], q[key]])
        for (const offset of [-GAP, GAP]) values.add(round(v + offset));
      return [...values].sort((x, y) => x - y);
    };
    const xs = axis('x'), ys = axis('y'), width = xs.length, cells = width * ys.length;
    if (cells > DRAFT_ROUTING_BUDGET.maxCells) continue;
    const cell = (p: RoutePoint) => ys.indexOf(p.y) * width + xs.indexOf(p.x);
    const point = (c: number) => ({ x: xs[c % width], y: ys[Math.floor(c / width)] });
    const source = cell(a), target = cell(b), distances = new Float64Array(cells * 4).fill(Infinity);
    const previous = new Int32Array(cells * 4).fill(-1);
    const heap: { state: number; cost: number; score: number }[] = [];
    const push = (item: typeof heap[number]) => {
      heap.push(item); let k = heap.length - 1;
      while (k) { const parent = (k - 1) >> 1; if (heap[parent].score <= item.score) break; heap[k] = heap[parent]; k = parent; }
      heap[k] = item;
    };
    const pop = () => {
      const first = heap[0], last = heap.pop()!;
      if (heap.length) {
        let k = 0;
        while (k * 2 + 1 < heap.length) {
          let child = k * 2 + 1;
          if (child + 1 < heap.length && heap[child + 1].score < heap[child].score) child++;
          if (last.score <= heap[child].score) break; heap[k] = heap[child]; k = child;
        }
        heap[k] = last;
      }
      return first;
    };
    const heuristic = (c: number) => Math.abs(point(c).x - b.x) + Math.abs(point(c).y - b.y);
    const initial = source * 4 + sd;
    distances[initial] = 0; push({ state: initial, cost: 0, score: heuristic(source) });
    let final = -1, expanded = 0;
    while (heap.length && expanded++ < DRAFT_ROUTING_BUDGET.maxExpandedStates && geometryChecks < DRAFT_ROUTING_BUDGET.maxGeometryChecks) {
      const current = pop(); if (current.cost !== distances[current.state]) continue;
      const c = Math.floor(current.state / 4), d = current.state % 4;
      if (c === target && (d + 2) % 4 !== td) { final = current.state; break; }
      const x = c % width, y = Math.floor(c / width), p = point(c);
      for (let nd = 0; nd < 4; nd++) {
        if ((nd + 2) % 4 === d) continue;
        const nx = x + vectors[nd].x, ny = y + vectors[nd].y;
        if (nx < 0 || ny < 0 || nx >= width || ny >= ys.length) continue;
        const nc = ny * width + nx, q = point(nc);
        if (!clear(p, q)) continue;
        const cost = current.cost + Math.abs(p.x - q.x) + Math.abs(p.y - q.y) + (nd === d ? 0 : 24);
        const state = nc * 4 + nd;
        if (cost < distances[state]) { distances[state] = cost; previous[state] = current.state; push({ state, cost, score: cost + heuristic(nc) }); }
      }
    }
    if (final < 0) continue;
    const middle: RoutePoint[] = [];
    for (let state = final; state >= 0; state = previous[state]) middle.push(point(Math.floor(state / 4)));
    const candidate = simplify([start, ...middle.reverse(), end]);
    if (segments(candidate).some(([p, q]) => !clear(p, q)) || direction(candidate[0], candidate[1]) !== sd ||
      direction(candidate.at(-2)!, candidate.at(-1)!) !== td) continue;
    results[i] = { path: encode(candidate), points: candidate, changed: true, blockedBy: [] };
  }
  return results;
}
