import type { SceneNode } from './types.ts';
import type { RoutePoint, RouteRequest, RouteResult } from './orthogonalRouter.ts';
import { nodeVisualOutline, visualPortSide } from './nodeVisualOutline.ts';

/** Independent allowance for visible lane separation after obstacle routing.
 * It applies to ordinary and auxiliary bindings alike. Work exhaustion retains
 * the last checked route, rather than moving a node or inventing a connection. */
export const READABLE_ROUTE_BUDGET = Object.freeze({ maxNodes: 1_024, maxRoutes: 512, maxRoutePoints: 4_096,
  maxCandidatesPerRoute: 64, maxCandidates: 2_048, maxAccepted: 64, maxPairChecks: 100_000,
  maxSegmentChecks: 400_000, maxObstacleChecks: 250_000 });
type Rect = { id: string; x: number; y: number; width: number; height: number };
type Metric = { crossings: number; overlap: number; contacts: number;
  crossingPoints: RoutePoint[]; contactPoints: RoutePoint[]; spans: Map<string, [number, number][]> };
const EPS = 1e-7, GAP = 8;
const round = (n: number) => Math.round(n * 100) / 100;
const equal = (a: RoutePoint, b: RoutePoint) => Math.abs(a.x - b.x) <= EPS && Math.abs(a.y - b.y) <= EPS;
const length = (points: readonly RoutePoint[]) => points.slice(1).reduce((total, p, i) => total + Math.abs(p.x - points[i].x) + Math.abs(p.y - points[i].y), 0);
function simplify(points: readonly RoutePoint[]) {
  const result: RoutePoint[] = [];
  for (const p of points) {
    if (result.length && equal(p, result.at(-1)!)) continue;
    while (result.length > 1) {
      const a = result.at(-2)!, b = result.at(-1)!;
      if (!(a.x === b.x && b.x === p.x && (b.y - a.y) * (p.y - b.y) >= 0) &&
          !(a.y === b.y && b.y === p.y && (b.x - a.x) * (p.x - b.x) >= 0)) break;
      result.pop();
    }
    result.push({ ...p });
  }
  return result;
}
const path = (points: readonly RoutePoint[]) => points.map((p, i) => i === 0 ? `M ${p.x} ${p.y}` : p.x === points[i - 1].x ? `V ${p.y}` : `H ${p.x}`).join(' ');
const enters = (a: RoutePoint, b: RoutePoint, r: Rect, gap = 0) => a.x === b.x
  ? a.x > r.x - gap + EPS && a.x < r.x + r.width + gap - EPS && Math.max(Math.min(a.y, b.y), r.y - gap) < Math.min(Math.max(a.y, b.y), r.y + r.height + gap) - EPS
  : a.y > r.y - gap + EPS && a.y < r.y + r.height + gap - EPS && Math.max(Math.min(a.x, b.x), r.x - gap) < Math.min(Math.max(a.x, b.x), r.x + r.width + gap) - EPS;
const normal = (node: SceneNode, p: RoutePoint) => {
  const side = visualPortSide(node, p);
  return { x: side === 'left' ? -1 : side === 'right' ? 1 : 0, y: side === 'top' ? -1 : side === 'bottom' ? 1 : 0 };
};

/** Refine geometry, never canonical binding/style/port identities. Every peer
 * pair is checked individually: improvements elsewhere cannot conceal a newly
 * introduced crossing or a longer overlap. Equal tensor IDs do not bypass it. */
export function refineReadableRoutes(nodes: readonly SceneNode[], requests: readonly RouteRequest[], baseline: readonly RouteResult[]) {
  const limits = READABLE_ROUTE_BUDGET, results = baseline.map(result => ({ ...result }));
  if (nodes.length > limits.maxNodes || requests.length > limits.maxRoutes || requests.length !== baseline.length ||
      baseline.reduce((sum, r) => sum + r.points.length, 0) > limits.maxRoutePoints) return results;
  const byId = new Map(nodes.map(n => [n.id, n])), geometry = baseline.map(r => simplify(r.points));
  const outlines = new Map(nodes.map(n => [n.id, nodeVisualOutline(n).rectangles.map(r => ({ id: n.id, ...r }))]));
  const ancestors = (id: string) => { const result = new Set<string>(); let parent = byId.get(id)?.parentId;
    while (parent && byId.has(parent) && !result.has(parent)) { result.add(parent); parent = byId.get(parent)?.parentId; } return result; };
  const work = { candidates: 0, accepted: 0, pairs: 0, segments: 0, obstacles: 0 };
  const exhausted = () => work.candidates >= limits.maxCandidates || work.accepted >= limits.maxAccepted ||
    work.pairs >= limits.maxPairChecks || work.segments >= limits.maxSegmentChecks || work.obstacles >= limits.maxObstacleChecks;
  const bounds = (points: readonly RoutePoint[]) => ({ left: Math.min(...points.map(p => p.x)), right: Math.max(...points.map(p => p.x)),
    top: Math.min(...points.map(p => p.y)), bottom: Math.max(...points.map(p => p.y)) });
  const boxes = geometry.map(bounds);
  const meets = (a: ReturnType<typeof bounds>, b: ReturnType<typeof bounds>) => a.right >= b.left - EPS && b.right >= a.left - EPS && a.bottom >= b.top - EPS && b.bottom >= a.top - EPS;
  const empty = (): Metric => ({ crossings: 0, contacts: 0, overlap: 0, crossingPoints: [], contactPoints: [], spans: new Map() });
  const pair = (first: readonly RoutePoint[], second: readonly RoutePoint[], self = false): Metric | undefined => {
    if (++work.pairs > limits.maxPairChecks) return undefined;
    const intersections: RoutePoint[] = [], contacts: RoutePoint[] = [], spans = new Map<string, [number, number][]>(); let overlap = 0;
    const add = (list: RoutePoint[], p: RoutePoint) => { if (!list.some(q => equal(q, p))) list.push(p); };
    for (let i = 1; i < first.length; i++) for (let j = self ? i + 2 : 1; j < second.length; j++) {
      if (++work.segments > limits.maxSegmentChecks) return undefined;
      const a = first[i - 1], b = first[i], c = second[j - 1], d = second[j], vertical = a.x === b.x, otherVertical = c.x === d.x;
      if (vertical !== otherVertical) {
        const [v, w, h, k] = vertical ? [a, b, c, d] : [c, d, a, b];
        if (v.x >= Math.min(h.x, k.x) - EPS && v.x <= Math.max(h.x, k.x) + EPS && h.y >= Math.min(v.y, w.y) - EPS && h.y <= Math.max(v.y, w.y) + EPS) {
          const p = { x: v.x, y: h.y };
          if (v.x > Math.min(h.x, k.x) + EPS && v.x < Math.max(h.x, k.x) - EPS && h.y > Math.min(v.y, w.y) + EPS && h.y < Math.max(v.y, w.y) - EPS) add(intersections, p);
          else add(contacts, p);
        }
      } else if (Math.abs((vertical ? a.x : a.y) - (vertical ? c.x : c.y)) <= EPS) {
        const low = Math.max(vertical ? Math.min(a.y, b.y) : Math.min(a.x, b.x), vertical ? Math.min(c.y, d.y) : Math.min(c.x, d.x));
        const high = Math.min(vertical ? Math.max(a.y, b.y) : Math.max(a.x, b.x), vertical ? Math.max(c.y, d.y) : Math.max(c.x, d.x));
        if (high > low + EPS) {
          overlap += high - low;
          const key = `${vertical ? 'v' : 'h'}:${vertical ? a.x : a.y}`, list = spans.get(key) ?? [];
          list.push([low, high]); spans.set(key, list);
        }
        else if (high >= low - EPS) { const p = vertical ? { x: a.x, y: low } : { x: low, y: a.y }; add(contacts, p); }
      }
    }
    return { crossings: intersections.length, contacts: contacts.length, overlap, crossingPoints: intersections, contactPoints: contacts, spans };
  };
  const occupied = (p: RoutePoint, m: Metric) => m.contactPoints.some(q => equal(p, q)) || [...m.spans].some(([key, spans]) => {
    const [axis, coordinate] = key.split(':'); return Math.abs((axis === 'v' ? p.x : p.y) - +coordinate) <= EPS &&
      spans.some(([low, high]) => (axis === 'v' ? p.y : p.x) >= low - EPS && (axis === 'v' ? p.y : p.x) <= high + EPS);
  });
  const noWorse = (a: Metric, b: Metric) => a.crossingPoints.every(p => b.crossingPoints.some(q => equal(p, q))) &&
    a.contactPoints.every(p => occupied(p, b)) && a.overlap <= b.overlap + EPS &&
    [...a.spans].every(([key, spans]) => spans.every(([low, high]) => b.spans.get(key)?.some(([a, b]) => a <= low + EPS && b >= high - EPS)));
  const penalty = (m: Metric) => m.crossings * 1_000 + m.contacts * 100 + m.overlap;
  for (let i = 0; i < requests.length && !exhausted(); i++) {
    const request = requests[i], original = geometry[i], source = byId.get(request.sourceId), target = byId.get(request.targetId);
    if (!source || !target || baseline[i].blockedBy.length || original.length < 2 || original.length > 64) continue;
    if (original.some((p, n) => !Number.isFinite(p.x) || !Number.isFinite(p.y) || n > 0 && p.x !== original[n - 1].x && p.y !== original[n - 1].y ||
        n > 1 && (p.x - original[n - 1].x) * (original[n - 1].x - original[n - 2].x) + (p.y - original[n - 1].y) * (original[n - 1].y - original[n - 2].y) < 0)) continue;
    const start = original[0], end = original.at(-1)!, first = normal(source, start), last = normal(target, end);
    const owners = new Set([...ancestors(source.id), ...ancestors(target.id)]);
    const rectangles: Rect[] = nodes.flatMap(n => owners.has(n.id) ? n.expanded
      ? [{ id: n.id, x: n.x, y: n.y, width: n.width, height: n.headerHeight }] : [] : outlines.get(n.id)!);
    const clear = (candidate: readonly RoutePoint[], gap: number) => {
      for (let segment = 1; segment < candidate.length; segment++) {
        const a = candidate[segment - 1], b = candidate[segment];
        for (const r of rectangles) {
          if (++work.obstacles > limits.maxObstacleChecks) return false;
          const terminal = r.id === source.id && segment === 1 || r.id === target.id && segment === candidate.length - 1;
          if (enters(a, b, r, terminal ? 0 : gap)) return false;
        }
        // Crossing an ancestor boundary is necessary. Running alongside it
        // needs breathing room; a border is never a free routing lane.
        for (const id of owners) {
          const n = byId.get(id)!; if (!n.expanded) continue;
          if (++work.obstacles > limits.maxObstacleChecks) return false;
          const vertical = a.x === b.x;
          if (vertical && Math.min(Math.max(a.y, b.y), n.y + n.height) - Math.max(Math.min(a.y, b.y), n.y) > GAP &&
              Math.min(Math.abs(a.x - n.x), Math.abs(a.x - n.x - n.width)) < gap - EPS) return false;
          if (!vertical && Math.min(Math.max(a.x, b.x), n.x + n.width) - Math.max(Math.min(a.x, b.x), n.x) > GAP &&
              Math.min(Math.abs(a.y - n.y), Math.abs(a.y - n.y - n.height)) < gap - EPS) return false;
        }
      }
      return true;
    };
    const originalClear = clear(original, GAP);
    const previous = geometry.map((points, j) => j === i || !meets(boxes[i], boxes[j]) ? empty() : pair(original, points));
    if (previous.some(metric => !metric) || exhausted()) break;
    const beforePenalty = previous.reduce((sum, metric) => sum + penalty(metric!), 0), originalCost = length(original) + (original.length - 2) * 18;
    // The sparse 300-layer chain has no conflict or detour to improve. Reject
    // it before building candidate axes; do not spend a quadratic candidate
    // search on each adjacent straight binding during every pointer move.
    if (originalClear && !beforePenalty && original.length <= 4 &&
        length(original) <= Math.abs(start.x - end.x) + Math.abs(start.y - end.y) + EPS) continue;
    const originalSelf = pair(original, original, true);
    if (!originalSelf || originalSelf.crossings || originalSelf.overlap || originalSelf.contacts) continue;
    const coordinates = (axis: 'x' | 'y') => {
      const values = new Set<number>(original.map(p => p[axis]));
      for (const n of nodes) {
        const bounds = nodeVisualOutline(n).bounds;
        for (const gap of [GAP, 18, 28]) {
          values.add(round((axis === 'x' ? bounds.x : bounds.y) - gap));
          values.add(round((axis === 'x' ? bounds.x + bounds.width : bounds.y + bounds.height) + gap));
          if (n.expanded) { values.add(round((axis === 'x' ? bounds.x : bounds.y) + gap)); values.add(round((axis === 'x' ? bounds.x + bounds.width : bounds.y + bounds.height) - gap)); }
        }
      }
      // Nearby occupied lanes get distinct ±8 coordinates. They are candidates
      // only; complete-batch acceptance still checks every binding.
      for (const points of geometry) for (const p of points) if (p.y >= Math.min(start.y, end.y) - 30 && p.y <= Math.max(start.y, end.y) + 30)
        for (const gap of [-GAP, GAP]) values.add(round(p[axis] + gap));
      const low = Math.min(start[axis], end[axis]), high = Math.max(start[axis], end[axis]);
      return [...values].sort((a, b) => Math.max(low - a, a - high, 0) - Math.max(low - b, b - high, 0) ||
        Math.min(Math.abs(a - start[axis]), Math.abs(a - end[axis])) - Math.min(Math.abs(b - start[axis]), Math.abs(b - end[axis])) || a - b).slice(0, 30);
    };
    // A nearby-axis cap can omit every corridor outside a wide ancestor
    // header. Reserve candidates for those boundaries before inexpensive
    // paths through the header consume the per-route allowance. Wider frames
    // come first; no fixture identity or tensor name participates.
    const escapeAxes = (axis: 'x' | 'y') => {
      const perpendicular = axis === 'x' ? 'y' : 'x';
      const low = Math.min(start[perpendicular], end[perpendicular]);
      const high = Math.max(start[perpendicular], end[perpendicular]);
      const frames = [...owners].map(id => byId.get(id)!).filter(n => n.expanded &&
        (axis === 'x' ? n.y < high && n.y + n.headerHeight > low : n.x < high && n.x + n.width > low))
        .sort((a, b) => (axis === 'x' ? b.width - a.width : b.headerHeight - a.headerHeight) || a.id.localeCompare(b.id));
      return [...new Set(frames.flatMap(n => axis === 'x'
        ? [round(n.x - GAP), round(n.x + n.width + GAP)]
        : [round(n.y - GAP), round(n.y + n.headerHeight + GAP)]))].slice(0, 8);
    };
    const xs = coordinates('x'), ys = coordinates('y'), escapeXs = first.y || last.y ? escapeAxes('x') : [],
      escapeYs = first.x || last.x ? escapeAxes('y') : [], generated = new Map<string, RoutePoint[]>(), escapes = new Set<string>();
    const add = (points: RoutePoint[], escape = false) => {
      const candidate = simplify(points);
      if (candidate.length < 2 || candidate.length > original.length + 2 || path(candidate) === path(original)) return;
      const p = candidate[1], q = candidate.at(-2)!;
      if ((p.x - start.x) * first.x + (p.y - start.y) * first.y < GAP - EPS ||
          (q.x - end.x) * last.x + (q.y - end.y) * last.y < GAP - EPS ||
          first.x && p.y !== start.y || first.y && p.x !== start.x || last.x && q.y !== end.y || last.y && q.x !== end.x) return;
      if (length(candidate) > length(original) + 64) return;
      const key = path(candidate); generated.set(key, candidate); if (escape) escapes.add(key);
    };
    for (const lead of [GAP, 18, 28]) {
      const a = { x: start.x + first.x * lead, y: start.y + first.y * lead }, b = { x: end.x + last.x * lead, y: end.y + last.y * lead };
      for (const x of escapeXs) add([start, a, { x, y: a.y }, { x, y: b.y }, b, end], true);
      for (const y of escapeYs) add([start, a, { x: a.x, y }, { x: b.x, y }, b, end], true);
      add([start, a, { x: b.x, y: a.y }, b, end]); add([start, a, { x: a.x, y: b.y }, b, end]);
      for (const x of xs) add([start, a, { x, y: a.y }, { x, y: b.y }, b, end]);
      for (const y of ys) add([start, a, { x: a.x, y }, { x: b.x, y }, b, end]);
    }
    const reserved = [...escapes].slice(0, limits.maxCandidatesPerRoute / 2).map(key => generated.get(key)!);
    const candidates = [...reserved, ...[...generated.values()].filter(candidate => !reserved.some(p => path(p) === path(candidate)))
      .sort((a, b) => length(a) + (a.length - 2) * 18 - length(b) - (b.length - 2) * 18 || path(a).localeCompare(path(b)))
      .slice(0, limits.maxCandidatesPerRoute - reserved.length)];
    let best: RoutePoint[] | undefined, bestPenalty = beforePenalty, bestCost = originalCost;
    for (const candidate of candidates) {
      if (exhausted()) break; work.candidates++;
      if (!clear(candidate, GAP)) continue;
      const self = pair(candidate, candidate, true); if (!self || self.crossings || self.overlap || self.contacts) continue;
      let sum = 0, safe = true;
      const candidateBounds = bounds(candidate);
      for (let j = 0; j < geometry.length; j++) {
        if (j === i || !meets(candidateBounds, boxes[j]) && !meets(boxes[i], boxes[j])) continue;
        const after = pair(candidate, geometry[j]); if (!after || !noWorse(after, previous[j]!)) { safe = false; break; } sum += penalty(after);
      }
      const cost = length(candidate) + (candidate.length - 2) * 18;
      if (safe && (sum < bestPenalty - EPS || Math.abs(sum - bestPenalty) <= EPS &&
          (cost < bestCost - EPS || !originalClear && best === undefined && cost <= originalCost + 64))) {
        best = candidate; bestPenalty = sum; bestCost = cost;
      }
    }
    if (best) { geometry[i] = best; boxes[i] = bounds(best); results[i] = { path: path(best), points: best, changed: true, blockedBy: [] }; work.accepted++; }
  }
  return results;
}
