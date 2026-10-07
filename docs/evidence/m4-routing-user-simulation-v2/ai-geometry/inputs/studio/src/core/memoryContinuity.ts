import type { SceneNode } from './types.ts';
import type { RoutePoint, RouteRequest, RouteResult } from './orthogonalRouter.ts';
import { nodeVisualOutline, projectVisualPort, visualPortSide } from './nodeVisualOutline.ts';
import { edgeDashPattern } from './edgePresentation.ts';

/** Work bounds apply only to the late memory projection, after the complete
 * formal batch. Unknown/exhausted checks keep that scene's baseline route. */
export const MEMORY_CONTINUITY_BUDGET = Object.freeze({ maxNodes: 1_024, maxRoutes: 512,
  maxRoutePoints: 4_096, maxPairChecks: 32_768, maxSegmentChecks: 250_000,
  maxObstacleChecks: 100_000, maxCandidates: 128 });
export type MemoryContinuityBudget = { readonly [K in keyof typeof MEMORY_CONTINUITY_BUDGET]: number };
export interface MemoryProjection { start: RoutePoint; end: RoutePoint; points: RoutePoint[]; path: string }
type Rect = { left: number; top: number; right: number; bottom: number };
type Geometry = { contacts: RoutePoint[]; spans: Map<string, [number, number][]> };
const EPS = 1e-7, LEAD = 6;
const rounded = (value: number) => Math.round(value * 100) / 100;
const same = (a: RoutePoint, b: RoutePoint) => Math.abs(a.x - b.x) <= EPS && Math.abs(a.y - b.y) <= EPS;
function validPoints(points: readonly RoutePoint[]) {
  return points.length >= 2 && points.every((p, i) => Number.isFinite(p.x) && Number.isFinite(p.y) &&
    (!i || !same(p, points[i - 1]) && (p.x === points[i - 1].x || p.y === points[i - 1].y)));
}
function length(points: readonly RoutePoint[]) {
  let result = 0;
  for (let i = 1; i < points.length; i++) result += Math.abs(points[i].x - points[i - 1].x) + Math.abs(points[i].y - points[i - 1].y);
  return result;
}
function simplified(points: readonly RoutePoint[]) {
  const result: RoutePoint[] = [];
  for (const point of points) {
    if (result.length && same(point, result.at(-1)!)) continue;
    while (result.length > 1) {
      const a = result.at(-2)!, b = result.at(-1)!;
      if (!(a.x === b.x && b.x === point.x && (b.y - a.y) * (point.y - b.y) >= 0) &&
          !(a.y === b.y && b.y === point.y && (b.x - a.x) * (point.x - b.x) >= 0)) break;
      result.pop();
    }
    result.push({ ...point });
  }
  return result;
}
function path(points: readonly RoutePoint[]) {
  return points.map((p, i) => i === 0 ? `M ${p.x} ${p.y}` : p.x === points[i - 1].x ? `V ${p.y}` : `H ${p.x}`).join(' ');
}
function enters(a: RoutePoint, b: RoutePoint, r: Rect) {
  return a.x === b.x
    ? a.x > r.left + EPS && a.x < r.right - EPS && Math.max(Math.min(a.y, b.y), r.top) < Math.min(Math.max(a.y, b.y), r.bottom) - EPS
    : a.y > r.top + EPS && a.y < r.bottom - EPS && Math.max(Math.min(a.x, b.x), r.left) < Math.min(Math.max(a.x, b.x), r.right) - EPS;
}
function segmentDistance(a: RoutePoint, b: RoutePoint, c: RoutePoint, d: RoutePoint) {
  const x = Math.max(Math.min(a.x, b.x) - Math.max(c.x, d.x), Math.min(c.x, d.x) - Math.max(a.x, b.x), 0);
  const y = Math.max(Math.min(a.y, b.y) - Math.max(c.y, d.y), Math.min(c.y, d.y) - Math.max(a.y, b.y), 0);
  return Math.hypot(x, y);
}

/** Replace only eligible memory display routes. Every other final batch path
 * is fixed, including same-tensor peers. No generic router pass runs afterward. */
export function projectMemoryContinuity(nodes: readonly SceneNode[], requests: readonly RouteRequest[],
  baseline: readonly RouteResult[], limits: MemoryContinuityBudget = MEMORY_CONTINUITY_BUDGET): Map<number, MemoryProjection> {
  const accepted = new Map<number, MemoryProjection>();
  const budgetKeys = Object.keys(MEMORY_CONTINUITY_BUDGET) as (keyof MemoryContinuityBudget)[];
  if (!limits || Object.keys(limits).length !== budgetKeys.length || budgetKeys.some(key =>
    !Object.hasOwn(limits, key) || !Number.isSafeInteger(limits[key]) || limits[key] < 0) || nodes.length > limits.maxNodes ||
      requests.length !== baseline.length || requests.length > limits.maxRoutes ||
      baseline.reduce((sum, r) => sum + r.points.length, 0) > limits.maxRoutePoints ||
      nodes.some(n =>
        ![n.x, n.y, n.width, n.height, n.headerHeight].every(Number.isFinite) || n.width <= 0 || n.height <= 0)) return accepted;
  const fixedGeometry = baseline.map(result => simplified(result.points));
  if (fixedGeometry.some(points => !validPoints(points))) return accepted;
  const byId = new Map(nodes.map(node => [node.id, node]));
  const rectangles = new Map(nodes.map(node => [node.id, nodeVisualOutline(node).rectangles.map(r =>
    ({ left: r.x, top: r.y, right: r.x + r.width, bottom: r.y + r.height }))]));
  const ancestors = (node: SceneNode): Set<string> | null => {
    const result = new Set<string>(); let id = node.parentId;
    while (id) {
      if (result.has(id) || !byId.has(id)) return null;
      result.add(id); id = byId.get(id)!.parentId;
    }
    return result;
  };
  const work = { pairs: 0, segments: 0, obstacles: 0, candidates: 0 };
  const geometry = (first: readonly RoutePoint[], second: readonly RoutePoint[], strokeGap?: number, self = false): Geometry | null => {
    if (++work.pairs > limits.maxPairChecks) return null;
    const contacts: RoutePoint[] = [], spans = new Map<string, [number, number][]>();
    const add = (p: RoutePoint) => { if (!contacts.some(q => same(p, q))) contacts.push(p); };
    for (let i = 1; i < first.length; i++) for (let j = self ? i + 2 : 1; j < second.length; j++) {
      if (++work.segments > limits.maxSegmentChecks) return null;
      const a = first[i - 1], b = first[i], c = second[j - 1], d = second[j];
      if (strokeGap !== undefined && segmentDistance(a, b, c, d) <= strokeGap + EPS) return null;
      const vertical = a.x === b.x, otherVertical = c.x === d.x;
      if (vertical !== otherVertical) {
        const [v, w, h, k] = vertical ? [a, b, c, d] : [c, d, a, b];
        if (v.x >= Math.min(h.x, k.x) - EPS && v.x <= Math.max(h.x, k.x) + EPS &&
            h.y >= Math.min(v.y, w.y) - EPS && h.y <= Math.max(v.y, w.y) + EPS) add({ x: v.x, y: h.y });
      } else if (Math.abs((vertical ? a.x : a.y) - (vertical ? c.x : c.y)) <= EPS) {
        const low = Math.max(vertical ? Math.min(a.y, b.y) : Math.min(a.x, b.x), vertical ? Math.min(c.y, d.y) : Math.min(c.x, d.x));
        const high = Math.min(vertical ? Math.max(a.y, b.y) : Math.max(a.x, b.x), vertical ? Math.max(c.y, d.y) : Math.max(c.x, d.x));
        if (high < low - EPS) continue;
        if (high <= low + EPS) add(vertical ? { x: a.x, y: low } : { x: low, y: a.y });
        else { const key = `${vertical ? 'v' : 'h'}:${vertical ? a.x : a.y}`;
          const list = spans.get(key) ?? []; list.push([low, high]); spans.set(key, list); }
      }
    }
    for (const [key, intervals] of spans) {
      intervals.sort((a, b) => a[0] - b[0]); const merged: [number, number][] = [];
      for (const interval of intervals) { const previous = merged.at(-1);
        if (previous && interval[0] <= previous[1] + EPS) previous[1] = Math.max(previous[1], interval[1]);
        else merged.push([...interval]); }
      spans.set(key, merged);
    }
    return { contacts, spans };
  };
  const subset = (after: Geometry, before: Geometry) => after.contacts.every(p => before.contacts.some(q => same(p, q))) &&
    [...after.spans].every(([key, intervals]) => intervals.every(([low, high]) =>
      before.spans.get(key)?.some(([a, b]) => a <= low + EPS && b >= high - EPS)));
  const appearanceWidth = (request: RouteRequest): number | null => {
    const appearance = request.appearance;
    if (!appearance || !Number.isFinite(appearance.width) || appearance.width <= 0 || !appearance.stroke || typeof appearance.dashed !== 'boolean') return null;
    try { edgeDashPattern(appearance); return appearance.width; } catch { return null; }
  };
  const widths = requests.map(appearanceWidth);
  for (let index = 0; index < requests.length; index++) {
    const request = requests[index], original = fixedGeometry[index], width = widths[index];
    if (request.role !== 'memory' || width === null || baseline[index].blockedBy.length) continue;
    if (++work.candidates > limits.maxCandidates) break;
    const source = byId.get(request.sourceId), target = byId.get(request.targetId);
    if (!source || !target || source.expanded || target.expanded) continue;
    const sourceAncestors = ancestors(source), targetAncestors = ancestors(target);
    if (!sourceAncestors || !targetAncestors) continue;
    const owners = new Set([...sourceAncestors, ...targetAncestors]);
    const sourceBounds = nodeVisualOutline(source).bounds, targetBounds = nodeVisualOutline(target).bounds;
    if (Math.min(sourceBounds.y + sourceBounds.height, targetBounds.y + targetBounds.height) - Math.max(sourceBounds.y, targetBounds.y) <= EPS) continue;
    const a = projectVisualPort(source, { x: source.x + source.width, y: source.y + source.height * .55 }, 'right');
    const b = projectVisualPort(target, { x: target.x, y: target.y + target.height * .55 }, 'left');
    const start = { x: rounded(a.x), y: rounded(a.y) }, end = { x: rounded(b.x), y: rounded(b.y) };
    const lane = rounded((start.x + end.x) / 2);
    if (![start.x, start.y, end.x, end.y, lane].every(Number.isFinite) || lane - start.x < LEAD - EPS || end.x - lane < LEAD - EPS) continue;
    const points = simplified([start, { x: lane, y: start.y }, { x: lane, y: end.y }, end]);
    if (!validPoints(points) || length(points) > length(original) + EPS) continue;
    if (path(points) === baseline[index].path) continue;
    // One necessary extra bend may repair an old arrival perpendicular to
    // its actual side port. Otherwise a projection cannot add route bends.
    const last = original.at(-1)!, previous = original.at(-2)!;
    const oldTargetSide = visualPortSide(target, last);
    const oldNormalCorrect = oldTargetSide === 'left' ? previous.x < last.x && previous.y === last.y :
      oldTargetSide === 'right' ? previous.x > last.x && previous.y === last.y :
        oldTargetSide === 'top' ? previous.y < last.y && previous.x === last.x : previous.y > last.y && previous.x === last.x;
    if (points.length > original.length && oldNormalCorrect) continue;
    const self = geometry(points, points, undefined, true);
    if (!self || self.contacts.length || self.spans.size) continue;
    let clear = true;
    for (const node of nodes) {
      const own = node.id === source.id || node.id === target.id;
      const boxes = owners.has(node.id)
        ? node.expanded ? [{ left: node.x, top: node.y, right: node.x + node.width, bottom: node.y + node.headerHeight }] : []
        : rectangles.get(node.id)!;
      for (let segment = 1; segment < points.length && clear; segment++) for (const box of boxes) {
        if (++work.obstacles > limits.maxObstacleChecks) { clear = false; break; }
        // First/last normal leads meet their own exposed body boundary;
        // padded middles and unrelated bodies/headers retain visible clearance.
        const terminal = node.id === source.id && segment === 1 || node.id === target.id && segment === points.length - 1;
        const padding = terminal ? 0 : Math.max(LEAD, width / 2 + (node.expanded ? .65 : .75));
        if (enters(points[segment - 1], points[segment], { left: box.left - padding, right: box.right + padding,
          top: box.top - padding, bottom: box.bottom + padding })) { clear = false; break; }
      }
      if (!clear) break;
    }
    if (!clear) continue;
    for (let peer = 0; peer < requests.length && clear; peer++) {
      if (peer === index) continue;
      if (widths[peer] === null) { clear = false; break; }
      const fixed = fixedGeometry[peer], chosen = accepted.get(peer)?.points;
      const before = geometry(original, fixed), after = geometry(points, fixed, (width + widths[peer]!) / 2);
      if (!before || !after || !subset(after, before)) { clear = false; break; }
      if (chosen) {
        const chosenBefore = geometry(original, chosen), chosenAfter = geometry(points, chosen, (width + widths[peer]!) / 2);
        if (!chosenBefore || !chosenAfter || !subset(chosenAfter, chosenBefore)) clear = false;
      }
    }
    if (clear) accepted.set(index, { start, end, points, path: path(points) });
  }
  return accepted;
}
