import type { SceneEdge } from './types.ts';
import type { RoutePoint } from './orthogonalRouter.ts';
import { edgeAppearanceKey } from './edgePresentation.ts';

type LaneEdge = Pick<SceneEdge, 'id' | 'sourceId' | 'source' | 'tensorId' | 'role' | 'path' | 'stroke' | 'width' | 'dashed' | 'dashPattern'>;
export interface RouteLaneSpan { axis: 'x' | 'y'; coordinate: number; low: number; high: number }
export interface RouteLaneConflict { firstId: string; secondId: string; length: number; spans: RouteLaneSpan[] }
export interface RouteBranchJunction extends RoutePoint { edgeIds: string[]; stroke: string; width: number }
const EPS = 1e-7;
const same = (a: RoutePoint, b: RoutePoint) => Math.abs(a.x - b.x) <= EPS && Math.abs(a.y - b.y) <= EPS;
const distance = (a: RoutePoint, b: RoutePoint) => Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
function parse(path: string): RoutePoint[] {
  let x = 0, y = 0; const result: RoutePoint[] = [];
  for (const [, op, a, b] of path.matchAll(/([MHV])\s*(-?[\d.]+)(?:\s+(-?[\d.]+))?/g)) {
    if (op === 'M') { x = +a; y = +b; } else if (op === 'H') x = +a; else y = +a;
    const point = { x, y }; if (!result.length || !same(result.at(-1)!, point)) result.push(point);
  }
  return result;
}
function span(a: RoutePoint, b: RoutePoint): RouteLaneSpan {
  const vertical = a.x === b.x, axis = vertical ? 'y' : 'x';
  return { axis, coordinate: vertical ? a.x : a.y, low: Math.min(a[axis], b[axis]), high: Math.max(a[axis], b[axis]) };
}
function overlaps(first: readonly RoutePoint[], second: readonly RoutePoint[]): RouteLaneSpan[] {
  const result: RouteLaneSpan[] = [];
  for (let i = 1; i < first.length; i++) for (let j = 1; j < second.length; j++) {
    const a = span(first[i - 1], first[i]), b = span(second[j - 1], second[j]);
    if (a.axis !== b.axis || Math.abs(a.coordinate - b.coordinate) > EPS) continue;
    const low = Math.max(a.low, b.low), high = Math.min(a.high, b.high);
    if (high > low + EPS) result.push({ ...a, low, high });
  }
  return result;
}
function family(first: LaneEdge, second: LaneEdge, a: readonly RoutePoint[], b: readonly RoutePoint[]) {
  return a.length > 1 && b.length > 1 && same(a[0], b[0]) && first.sourceId === second.sourceId &&
    first.source.nodeId === second.source.nodeId && first.source.portId === second.source.portId &&
    first.tensorId === second.tensorId && first.role === second.role && edgeAppearanceKey(first) === edgeAppearanceKey(second);
}
/** Only a continuous, equally directed prefix of a resolved canonical/style
 * family is a genuine fan-out trunk. Equal tensors or a later rejoin are not. */
function prefix(first: readonly RoutePoint[], second: readonly RoutePoint[]) {
  const result: RoutePoint[] = [{ ...first[0] }]; let i = 1, j = 1, current = first[0];
  // A malformed or numerically unstable candidate must never make the
  // shared-prefix walk spin forever.  Normally each iteration consumes at
  // least one route vertex; the bound is only a defensive contract for
  // diagnostics, which must remain total even when a candidate is rejected.
  let steps = 0, invalid = false;
  while (i < first.length && j < second.length) {
    if (++steps > (first.length + second.length) * 4) { invalid = true; break; }
    const a = first[i], b = second[j], dx = Math.sign(a.x - current.x), dy = Math.sign(a.y - current.y);
    if (dx !== Math.sign(b.x - current.x) || dy !== Math.sign(b.y - current.y)) break;
    const amount = Math.min(distance(current, a), distance(current, b));
    if (!Number.isFinite(amount) || amount <= EPS) { invalid = true; break; }
    const next = { x: current.x + dx * amount, y: current.y + dy * amount };
    if (!Number.isFinite(next.x) || !Number.isFinite(next.y) || same(next, current)) { invalid = true; break; }
    current = next; result.push(current);
    if (same(current, a)) i++; if (same(current, b)) j++;
  }
  // Completely coincident paths have no visible branch, and must be reported
  // as ambiguous rather than concealed behind the family exemption.
  return invalid ? [first[0]] : i === first.length || j === second.length ? [first[0]] : result;
}
/** Canonical fan-out geometry used by both diagnostics and the router's
 * peer guard. The shared prefix is a permitted branch, never an exemption
 * for later crossings, rejoining lanes or a tensor label alone. */
export function sharedBindingPrefix(first: LaneEdge, second: LaneEdge, a: readonly RoutePoint[], b: readonly RoutePoint[]) {
  return family(first, second, a, b) ? prefix(a, b) : [];
}
function subtract(occupied: RouteLaneSpan[], allowed: readonly RouteLaneSpan[]) {
  for (const shared of allowed) occupied = occupied.flatMap(part => {
    if (part.axis !== shared.axis || Math.abs(part.coordinate - shared.coordinate) > EPS || shared.high <= part.low + EPS || shared.low >= part.high - EPS) return [part];
    const result: RouteLaneSpan[] = [];
    if (shared.low > part.low + EPS) result.push({ ...part, high: Math.min(shared.low, part.high) });
    if (shared.high < part.high - EPS) result.push({ ...part, low: Math.max(shared.high, part.low) });
    return result;
  });
  return occupied;
}

/** Independent derived diagnostics: no node, port, binding or route mutates.
 * The input is the public final scene geometry, including later projections. */
export function routeLaneConflicts(edges: readonly LaneEdge[]): RouteLaneConflict[] {
  const points = edges.map(edge => parse(edge.path)), result: RouteLaneConflict[] = [];
  for (let i = 0; i < edges.length; i++) for (let j = i + 1; j < edges.length; j++) {
    let spans = overlaps(points[i], points[j]); if (!spans.length) continue;
    if (family(edges[i], edges[j], points[i], points[j])) {
      const trunk = prefix(points[i], points[j]); spans = subtract(spans, trunk.slice(1).map((point, n) => span(trunk[n], point)));
    }
    if (spans.length) result.push({ firstId: edges[i].id, secondId: edges[j].id, length: spans.reduce((sum, part) => sum + part.high - part.low, 0), spans });
  }
  return result;
}

/** Render genuine fan-out once, with a dot at the actual branch. Full paths
 * remain available on scene edges for canonical selection and metadata. */
export function sharedRoutePresentation(edges: readonly LaneEdge[]) {
  const points = edges.map(edge => parse(edge.path)), paths = new Map<string, string>(), prefixLengths = new Map<string, number>(), junctions = new Map<string, RouteBranchJunction>();
  for (let i = 0; i < edges.length; i++) {
    let removed = 0;
    for (let j = 0; j < i; j++) if (family(edges[i], edges[j], points[i], points[j])) {
      const trunk = prefix(points[i], points[j]); if (trunk.length < 2) continue;
      const amount = trunk.slice(1).reduce((sum, point, n) => sum + distance(trunk[n], point), 0); removed = Math.max(removed, amount);
      const point = trunk.at(-1)!, key = JSON.stringify([edges[i].sourceId, edges[i].source, edges[i].tensorId, edges[i].role, edgeAppearanceKey(edges[i]), point]);
      const existing = junctions.get(key);
      if (existing) existing.edgeIds = [...new Set([...existing.edgeIds, edges[i].id, edges[j].id])];
      else junctions.set(key, { ...point, edgeIds: [edges[j].id, edges[i].id], stroke: edges[i].stroke, width: edges[i].width });
    }
    prefixLengths.set(edges[i].id, removed);
    if (removed <= EPS) { paths.set(edges[i].id, edges[i].path); continue; }
    const route: RoutePoint[] = []; let remaining = removed;
    for (let n = 1; n < points[i].length; n++) {
      const a = points[i][n - 1], b = points[i][n], amount = distance(a, b);
      if (remaining >= amount - EPS) { remaining -= amount; continue; }
      if (!route.length) route.push({ x: a.x + Math.sign(b.x - a.x) * remaining, y: a.y + Math.sign(b.y - a.y) * remaining });
      route.push(b); remaining = 0;
    }
    paths.set(edges[i].id, route.map((point, n) => n === 0 ? `M ${point.x} ${point.y}` : point.x === route[n - 1].x ? `V ${point.y}` : `H ${point.x}`).join(' '));
  }
  return { paths, prefixLengths, junctions: [...junctions.values()] };
}
