import type { EdgeRole, SceneNode } from './types.ts';
import { nodeVisualOutline, visualPortSide } from './nodeVisualOutline.ts';
import { edgeAppearanceKey, edgeDashPattern } from './edgePresentation.ts';
import { refineReadableRoutes } from './readableRouting.ts';

export type RoutePoint = { x: number; y: number };
type Rectangle = { id: string; left: number; top: number; right: number; bottom: number };
export interface RouteAppearance { stroke: string; width: number; dashed: boolean; dashPattern?: number[] }
export interface RouteCanonicalSource { nodeId: string; portId: string }
export interface RouteRequest {
  sourceId: string; targetId: string; start: RoutePoint; end: RoutePoint; preferredPath: string; tensorId?: string;
  /** Exact source identity and rendered style are required before a shared trunk is proposed. */
  canonicalSource?: RouteCanonicalSource; canonicalEdgeIds?: readonly string[]; role?: EdgeRole; appearance?: RouteAppearance;
  /** Set only when every represented branch targets the same hidden binding through a collapsed proxy. */
  canonicalTarget?: RouteCanonicalSource;
  displaySide?: 'bottom' | 'top' | 'right' | 'left';
}
export interface RouteResult { path: string; points: RoutePoint[]; changed: boolean; blockedBy: string[] }
const CLEARANCE = 6, EPSILON = .01;
const number = (value: number) => Math.round(value * 100) / 100;
function validAppearance(appearance: RouteAppearance | undefined): appearance is RouteAppearance {
  if (!appearance?.stroke || !Number.isFinite(appearance.width) || appearance.width <= 0 || typeof appearance.dashed !== 'boolean') return false;
  try { edgeDashPattern(appearance); return true; } catch { return false; }
}
/** Deterministic work caps, not a wall-clock timeout or a performance claim. */
export const ROUTE_REFINEMENT_BUDGET = Object.freeze({ maxNodes: 1_024, maxRoutes: 512, maxRoutePoints: 4_096, maxPairChecks: 32_768,
  maxSegmentChecks: 150_000, maxObstacleChecks: 60_000, maxCandidates: 384, maxCandidatesPerRoute: 80, maxRefinedRoutes: 8, passes: 2 });
/** A separate final shortcut allowance cannot consume the family/residual pass.
 * Exhaustion leaves the last validated route intact; these are work caps, not FPS. */
export const ROUTE_SHORTCUT_BUDGET = Object.freeze({ maxNodes: 1_024, maxRoutes: 512, maxRoutePoints: 4_096,
  maxPointsPerRoute: 64, maxGeneratedPerRoute: 256, maxCandidatesPerRoute: 32, maxCandidates: 512,
  maxAcceptedRoutes: 32, maxPairChecks: 32_768, maxSegmentChecks: 250_000, maxObstacleChecks: 100_000 });
/** A late component pass has its own visible allowance. It cannot enlarge or
 * consume the generic/family or shortcut allowance. Large conflict components
 * and unknown/exhausted checks keep their last validated complete-batch paths. */
export const ROUTE_COMPONENT_BUDGET = Object.freeze({ maxNodes: 1_024, maxRoutes: 512, maxRoutePoints: 4_096,
  maxComponentRoutes: 8, maxComponents: 128, maxPointsPerRoute: 64, maxCoordinatesPerAxis: 24,
  maxGeneratedPerRoute: 384, maxCandidatesPerRoute: 64, maxCandidates: 2_048, maxRefinedRoutes: 128,
  maxPairChecks: 32_768, maxSegmentChecks: 400_000, maxObstacleChecks: 150_000 });

export function orthogonalPathPoints(path: string): RoutePoint[] {
  const tokens = path.match(/[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?/g) ?? [];
  const result: RoutePoint[] = [];
  for (let index = 0; index < tokens.length;) {
    const command = tokens[index++];
    let point: RoutePoint;
    if (command === 'M' || command === 'L') point = { x: +tokens[index++], y: +tokens[index++] };
    else if (command === 'H' && result.length) point = { x: +tokens[index++], y: result.at(-1)!.y };
    else if (command === 'V' && result.length) point = { x: result.at(-1)!.x, y: +tokens[index++] };
    else throw new Error(`Unsupported orthogonal route command ${command}`);
    if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) throw new Error('Non-finite orthogonal route point');
    result.push(point);
  }
  return result;
}
function simplified(points: RoutePoint[], roundCoordinates = true): RoutePoint[] {
  const result: RoutePoint[] = [];
  for (const point of points) {
    if (result.length && point.x === result.at(-1)!.x && point.y === result.at(-1)!.y) continue;
    while (result.length > 1) {
      const a = result.at(-2)!, b = result.at(-1)!;
      // Remove only forward collinear vertices, never a reversing U-turn.
      const vertical = a.x === b.x && b.x === point.x && (b.y - a.y) * (point.y - b.y) >= 0;
      const horizontal = a.y === b.y && b.y === point.y && (b.x - a.x) * (point.x - b.x) >= 0;
      if (!vertical && !horizontal) break;
      result.pop();
    }
    result.push({ x: roundCoordinates ? number(point.x) : point.x, y: roundCoordinates ? number(point.y) : point.y });
  }
  return result;
}
function path(points: RoutePoint[]): string {
  return points.map((point, index) => !index ? `M ${point.x} ${point.y}` : point.x === points[index - 1].x ? `V ${point.y}` : `H ${point.x}`).join(' ');
}
function penetrates(a: RoutePoint, b: RoutePoint, rectangle: Rectangle): boolean {
  if (a.x === b.x) return a.x > rectangle.left + EPSILON && a.x < rectangle.right - EPSILON &&
    Math.max(Math.min(a.y, b.y), rectangle.top + EPSILON) < Math.min(Math.max(a.y, b.y), rectangle.bottom - EPSILON);
  if (a.y === b.y) return a.y > rectangle.top + EPSILON && a.y < rectangle.bottom - EPSILON &&
    Math.max(Math.min(a.x, b.x), rectangle.left + EPSILON) < Math.min(Math.max(a.x, b.x), rectangle.right - EPSILON);
  throw new Error('A route segment must be axis aligned');
}
function inside(point: RoutePoint, rectangle: Rectangle): boolean {
  return point.x > rectangle.left + EPSILON && point.x < rectangle.right - EPSILON && point.y > rectangle.top + EPSILON && point.y < rectangle.bottom - EPSILON;
}
function collisions(points: RoutePoint[], rectangles: Rectangle[]): string[] {
  const result = new Set<string>();
  for (let index = 1; index < points.length; index++) for (const rectangle of rectangles) {
    if (penetrates(points[index - 1], points[index], rectangle)) result.add(rectangle.id);
  }
  return [...result];
}
function cost(points: RoutePoint[]): number {
  let length = 0;
  for (let index = 1; index < points.length; index++) length += Math.abs(points[index].x - points[index - 1].x) + Math.abs(points[index].y - points[index - 1].y);
  return length + Math.max(0, points.length - 2) * 18;
}
function routeLength(points: RoutePoint[]): number {
  let total = 0;
  for (let index = 1; index < points.length; index++) total += Math.abs(points[index].x - points[index - 1].x) + Math.abs(points[index].y - points[index - 1].y);
  return total;
}
type RouteBounds = { left: number; top: number; right: number; bottom: number };
type ConflictCost = { crossingPairs: number; crossingPoints: number; overlapPairs: number; overlapLength: number;
  disjointCrossingPairs: number; disjointCrossingPoints: number; disjointOverlapPairs: number;
  /** Same-tensor strict crossings are protected even though same-tensor overlap is allowed. */
  sameTensorCrossingPairs: number; sameTensorCrossingPoints: number };
function bounds(points: RoutePoint[]): RouteBounds {
  return { left: Math.min(...points.map(point => point.x)), right: Math.max(...points.map(point => point.x)),
    top: Math.min(...points.map(point => point.y)), bottom: Math.max(...points.map(point => point.y)) };
}
function boundsMeet(a: RouteBounds, b: RouteBounds) {
  return a.right >= b.left - EPSILON && b.right >= a.left - EPSILON && a.bottom >= b.top - EPSILON && b.bottom >= a.top - EPSILON;
}
function direction(a: RoutePoint, b: RoutePoint) { return { x: Math.sign(b.x - a.x), y: Math.sign(b.y - a.y) }; }
function validDirections(points: RoutePoint[], original: RoutePoint[]) {
  if (points.length < 2 || points.some((point, index) => index && point.x !== points[index - 1].x && point.y !== points[index - 1].y)) return false;
  const first = direction(original[0], original[1]), last = direction(original.at(-1)!, original.at(-2)!);
  const candidateFirst = direction(points[0], points[1]), candidateLast = direction(points.at(-1)!, points.at(-2)!);
  if (first.x !== candidateFirst.x || first.y !== candidateFirst.y || last.x !== candidateLast.x || last.y !== candidateLast.y) return false;
  for (let index = 1; index < points.length - 1; index++) {
    const a = direction(points[index - 1], points[index]), b = direction(points[index], points[index + 1]);
    if (a.x * b.x + a.y * b.y < 0) return false;
  }
  return true;
}
/** Final geometry contract for every route published to the scene. Route
 * refinement has several independent candidate generators; this guard keeps
 * a malformed candidate from reaching `path`, whose compact H/V serializer
 * cannot represent a diagonal segment. */
function isOrthogonal(points: readonly RoutePoint[]) {
  return points.length >= 2 && points.every((point, index) => Number.isFinite(point.x) && Number.isFinite(point.y) &&
    (index === 0 || point.x === points[index - 1].x || point.y === points[index - 1].y));
}
function conflictNoWorse(candidate: ConflictCost, original: ConflictCost) {
  return candidate.crossingPairs <= original.crossingPairs && candidate.crossingPoints <= original.crossingPoints && candidate.overlapPairs <= original.overlapPairs &&
    candidate.disjointCrossingPairs <= original.disjointCrossingPairs && candidate.disjointCrossingPoints <= original.disjointCrossingPoints && candidate.disjointOverlapPairs <= original.disjointOverlapPairs &&
    candidate.sameTensorCrossingPairs <= original.sameTensorCrossingPairs && candidate.sameTensorCrossingPoints <= original.sameTensorCrossingPoints;
}
function conflictBetter(candidate: ConflictCost, candidatePath: RoutePoint[], original: ConflictCost, originalPath: RoutePoint[]) {
  const a = [candidate.crossingPairs + candidate.overlapPairs, candidate.crossingPoints, candidate.overlapLength, cost(candidatePath)];
  const b = [original.crossingPairs + original.overlapPairs, original.crossingPoints, original.overlapLength, cost(originalPath)];
  for (let index = 0; index < a.length; index++) if (Math.abs(a[index] - b[index]) > EPSILON) return a[index] < b[index];
  return false;
}
/** Existing refinement uses strict segment interiors. The residual proposal
 * additionally counts intermediate vertices, excluding only whole-edge ends. */
function pairConflict(first: RoutePoint[], second: RoutePoint[], budget: { segmentChecks: number }, wholePolyline = false) {
  const crossingPoints = new Set<string>(); let overlapLength = 0;
  const overlapIntervals = wholePolyline ? new Map<string, [number, number][]>() : undefined;
  for (let i = 1; i < first.length; i++) for (let j = 1; j < second.length; j++) {
    if (budget.segmentChecks >= ROUTE_REFINEMENT_BUDGET.maxSegmentChecks) return undefined;
    budget.segmentChecks++;
    const a = first[i - 1], b = first[i], c = second[j - 1], d = second[j];
    const av = a.x === b.x, cv = c.x === d.x;
    if (av !== cv) {
      const verticalA = av ? a : c, verticalB = av ? b : d, horizontalA = av ? c : a, horizontalB = av ? d : b;
      const x = verticalA.x, y = horizontalA.y;
      const atWholeEndpoint = wholePolyline && [first[0], first.at(-1)!, second[0], second.at(-1)!]
        .some(point => Math.abs(point.x - x) < EPSILON && Math.abs(point.y - y) < EPSILON);
      const intersects = wholePolyline
        ? x >= Math.min(horizontalA.x, horizontalB.x) - EPSILON && x <= Math.max(horizontalA.x, horizontalB.x) + EPSILON &&
          y >= Math.min(verticalA.y, verticalB.y) - EPSILON && y <= Math.max(verticalA.y, verticalB.y) + EPSILON
        : x > Math.min(horizontalA.x, horizontalB.x) + EPSILON && x < Math.max(horizontalA.x, horizontalB.x) - EPSILON &&
          y > Math.min(verticalA.y, verticalB.y) + EPSILON && y < Math.max(verticalA.y, verticalB.y) - EPSILON;
      if (intersects && !atWholeEndpoint) {
        crossingPoints.add(`${verticalA.x}:${horizontalA.y}`);
      }
    } else if (av ? Math.abs(a.x - c.x) < EPSILON : Math.abs(a.y - c.y) < EPSILON) {
      const low = Math.max(av ? Math.min(a.y, b.y) : Math.min(a.x, b.x), av ? Math.min(c.y, d.y) : Math.min(c.x, d.x));
      const high = Math.min(av ? Math.max(a.y, b.y) : Math.max(a.x, b.x), av ? Math.max(c.y, d.y) : Math.max(c.x, d.x));
      if (high > low) {
        if (overlapIntervals) {
          const key = `${av ? 'v' : 'h'}:${av ? a.x : a.y}`;
          const intervals = overlapIntervals.get(key);
          if (intervals) intervals.push([low, high]); else overlapIntervals.set(key, [[low, high]]);
        } else overlapLength += high - low;
      }
    }
  }
  // The residual guard measures occupied geometry, not retracing multiplicity.
  // Existing generic/family refinement retains its segment-pair metric.
  for (const intervals of overlapIntervals?.values() ?? []) {
    intervals.sort((a, b) => a[0] - b[0]); let low = intervals[0][0], high = intervals[0][1];
    for (const [nextLow, nextHigh] of intervals.slice(1)) {
      if (nextLow <= high) high = Math.max(high, nextHigh);
      else { overlapLength += high - low; low = nextLow; high = nextHigh; }
    }
    overlapLength += high - low;
  }
  return { crossingPairs: Number(crossingPoints.size > 0), crossingPoints: crossingPoints.size,
    overlapPairs: Number(overlapLength > EPSILON), overlapLength };
}
function verticalIndex(rectangles: Rectangle[]) {
  const sorted = [...rectangles].sort((a, b) => a.top - b.top), prefixBottom: number[] = [];
  for (let i = 0; i < sorted.length; i++) prefixBottom.push(Math.max(sorted[i].bottom, prefixBottom[i - 1] ?? -Infinity));
  return (top: number, bottom: number): Rectangle[] => {
    let low = 0, high = sorted.length;
    while (low < high) { const middle = (low + high) >> 1; if (sorted[middle].top <= bottom) low = middle + 1; else high = middle; }
    const result = [];
    for (let i = low - 1; i >= 0 && prefixBottom[i] >= top; i--) if (sorted[i].bottom >= top) result.push(sorted[i]);
    return result;
  };
}

type ShortcutGeometry = { crossings: RoutePoint[]; contacts: RoutePoint[]; overlaps: Map<string, [number, number][]> };
type ShortcutWork = { pairs: number; segments: number; obstacles: number; candidates: number; accepted: number };
const SHORTCUT_EPSILON = 1e-7;
function shortcutPenetrates(a: RoutePoint, b: RoutePoint, rectangle: Rectangle): boolean {
  if (a.x === b.x) return a.x > rectangle.left + SHORTCUT_EPSILON && a.x < rectangle.right - SHORTCUT_EPSILON &&
    Math.max(Math.min(a.y, b.y), rectangle.top) < Math.min(Math.max(a.y, b.y), rectangle.bottom) - SHORTCUT_EPSILON;
  return a.y > rectangle.top + SHORTCUT_EPSILON && a.y < rectangle.bottom - SHORTCUT_EPSILON &&
    Math.max(Math.min(a.x, b.x), rectangle.left) < Math.min(Math.max(a.x, b.x), rectangle.right) - SHORTCUT_EPSILON;
}
/** Includes bend-vertex and collinear point contacts. Whole-edge endpoint
 * contacts are retained too: a shortcut cannot invent an attachment to a peer. */
function shortcutPair(first: RoutePoint[], second: RoutePoint[], work: ShortcutWork, self = false,
  limits: { maxPairChecks: number; maxSegmentChecks: number } = ROUTE_SHORTCUT_BUDGET): ShortcutGeometry | undefined {
  if (++work.pairs > limits.maxPairChecks) return undefined;
  const crossingMap = new Map<string, RoutePoint>(), contactMap = new Map<string, RoutePoint>();
  const overlaps = new Map<string, [number, number][]>();
  const record = (target: Map<string, RoutePoint>, x: number, y: number) => target.set(`${x}:${y}`, { x, y });
  // A route's adjacent segments share their ordinary bend by construction.
  // Its non-adjacent segments need the same occupied-geometry protection as
  // peers, counting each unordered pair once within the same work allowance.
  for (let i = 1; i < first.length; i++) for (let j = self ? i + 2 : 1; j < second.length; j++) {
    if (++work.segments > limits.maxSegmentChecks) return undefined;
    const a = first[i - 1], b = first[i], c = second[j - 1], d = second[j];
    const av = a.x === b.x, cv = c.x === d.x;
    if (av !== cv) {
      const v = av ? [a, b] : [c, d], h = av ? [c, d] : [a, b], x = v[0].x, y = h[0].y;
      if (x < Math.min(h[0].x, h[1].x) - SHORTCUT_EPSILON || x > Math.max(h[0].x, h[1].x) + SHORTCUT_EPSILON ||
          y < Math.min(v[0].y, v[1].y) - SHORTCUT_EPSILON || y > Math.max(v[0].y, v[1].y) + SHORTCUT_EPSILON) continue;
      record(contactMap, x, y);
      const endpoint = [first[0], first.at(-1)!, second[0], second.at(-1)!].some(p => Math.abs(p.x - x) < SHORTCUT_EPSILON && Math.abs(p.y - y) < SHORTCUT_EPSILON);
      if (!endpoint) record(crossingMap, x, y);
    } else if (Math.abs((av ? a.x : a.y) - (av ? c.x : c.y)) < SHORTCUT_EPSILON) {
      const low = Math.max(Math.min(av ? a.y : a.x, av ? b.y : b.x), Math.min(av ? c.y : c.x, av ? d.y : d.x));
      const high = Math.min(Math.max(av ? a.y : a.x, av ? b.y : b.x), Math.max(av ? c.y : c.x, av ? d.y : d.x));
      if (high < low - SHORTCUT_EPSILON) continue;
      if (high <= low + SHORTCUT_EPSILON) { record(contactMap, av ? a.x : low, av ? low : a.y); continue; }
      const key = `${av ? 'v' : 'h'}:${av ? a.x : a.y}`, intervals = overlaps.get(key) ?? [];
      intervals.push([low, high]); overlaps.set(key, intervals);
    }
  }
  for (const [key, intervals] of overlaps) {
    intervals.sort((a, b) => a[0] - b[0]); const merged: [number, number][] = [];
    for (const interval of intervals) {
      const last = merged.at(-1);
      if (last && interval[0] <= last[1] + SHORTCUT_EPSILON) last[1] = Math.max(last[1], interval[1]);
      else merged.push([...interval]);
    }
    overlaps.set(key, merged);
  }
  return { crossings: [...crossingMap.values()], contacts: [...contactMap.values()], overlaps };
}
function shortcutGeometrySubset(after: ShortcutGeometry, before: ShortcutGeometry) {
  const hasPoint = (points: RoutePoint[], p: RoutePoint) => points.some(q => Math.abs(p.x - q.x) < SHORTCUT_EPSILON && Math.abs(p.y - q.y) < SHORTCUT_EPSILON);
  const previouslyOccupied = (p: RoutePoint) => hasPoint(before.contacts, p) || [...before.overlaps].some(([key, intervals]) => {
    const [axis, coordinate] = key.split(':');
    return Math.abs((axis === 'v' ? p.x : p.y) - +coordinate) < SHORTCUT_EPSILON && intervals.some(([low, high]) =>
      (axis === 'v' ? p.y : p.x) >= low - SHORTCUT_EPSILON && (axis === 'v' ? p.y : p.x) <= high + SHORTCUT_EPSILON);
  });
  // Same-tensor overlap is still occupied geometry. A semantic identity never
  // licenses a newly shared trunk, moved crossing or contact with another edge.
  return after.crossings.every(p => hasPoint(before.crossings, p)) && after.contacts.every(previouslyOccupied) &&
    [...after.overlaps].every(([key, intervals]) => intervals.every(([low, high]) =>
      before.overlaps.get(key)?.some(([a, b]) => a <= low + SHORTCUT_EPSILON && b >= high - SHORTCUT_EPSILON)));
}
function lead(point: RoutePoint, node: SceneNode): RoutePoint {
  const side = visualPortSide(node, point);
  return { x: number(point.x + (side === 'right' ? CLEARANCE : side === 'left' ? -CLEARANCE : 0)),
    y: number(point.y + (side === 'bottom' ? CLEARANCE : side === 'top' ? -CLEARANCE : 0)) };
}

/** Local bounded Hanan-grid fallback, used only when a single corridor fails. */
function gridRoute(start: RoutePoint, end: RoutePoint, rectangles: Rectangle[], xs: number[], ys: number[]): RoutePoint[] | undefined {
  if (xs.length * ys.length > 40_000) return undefined;
  const width = xs.length, total = width * ys.length;
  const valid = new Uint8Array(total);
  for (let y = 0; y < ys.length; y++) for (let x = 0; x < width; x++) {
    if (!rectangles.some(rectangle => inside({ x: xs[x], y: ys[y] }, rectangle))) valid[y * width + x] = 1;
  }
  const source = ys.indexOf(start.y) * width + xs.indexOf(start.x), target = ys.indexOf(end.y) * width + xs.indexOf(end.x);
  if (!valid[source] || !valid[target]) return undefined;
  // Direction is state because each bend has a cost. A small binary heap keeps
  // the rare fallback proportional to reachable grid cells, not their square.
  const distance = new Float64Array(total * 3).fill(Infinity), previous = new Int32Array(total * 3).fill(-1);
  const heap: { state: number; cost: number; priority: number }[] = [];
  function push(item: typeof heap[number]) {
    heap.push(item); let index = heap.length - 1;
    while (index) { const parent = (index - 1) >> 1; if (heap[parent].priority <= item.priority) break; heap[index] = heap[parent]; index = parent; }
    heap[index] = item;
  }
  function pop() {
    const first = heap[0], last = heap.pop()!;
    if (heap.length) { let index = 0; while (index * 2 + 1 < heap.length) { let child = index * 2 + 1;
      if (child + 1 < heap.length && heap[child + 1].priority < heap[child].priority) child++;
      if (last.priority <= heap[child].priority) break; heap[index] = heap[child]; index = child;
    } heap[index] = last; }
    return first;
  }
  const point = (cell: number) => ({ x: xs[cell % width], y: ys[Math.floor(cell / width)] });
  const heuristic = (cell: number) => Math.abs(point(cell).x - end.x) + Math.abs(point(cell).y - end.y);
  distance[source * 3] = 0; push({ state: source * 3, cost: 0, priority: heuristic(source) });
  let final = -1;
  while (heap.length) {
    const current = pop(); if (current.cost !== distance[current.state]) continue;
    const cell = Math.floor(current.state / 3), direction = current.state % 3;
    if (cell === target) { final = current.state; break; }
    const x = cell % width, y = Math.floor(cell / width), a = point(cell);
    for (const [nx, ny, nextDirection] of [[x - 1, y, 1], [x + 1, y, 1], [x, y - 1, 2], [x, y + 1, 2]]) {
      if (nx < 0 || nx >= width || ny < 0 || ny >= ys.length) continue;
      const neighbor = ny * width + nx; if (!valid[neighbor]) continue;
      const b = point(neighbor); if (rectangles.some(rectangle => penetrates(a, b, rectangle))) continue;
      const candidate = current.cost + Math.abs(a.x - b.x) + Math.abs(a.y - b.y) + (direction && direction !== nextDirection ? 18 : 0);
      const state = neighbor * 3 + nextDirection;
      if (candidate < distance[state]) { distance[state] = candidate; previous[state] = current.state; push({ state, cost: candidate, priority: candidate + heuristic(neighbor) }); }
    }
  }
  if (final < 0) return undefined;
  const result = [];
  for (let state = final; state >= 0; state = previous[state]) result.push(point(Math.floor(state / 3)));
  return simplified(result.reverse());
}

/** One geometry-only router for canvas and detail export. It never moves nodes. */
export function createOrthogonalRouter(nodes: readonly SceneNode[]) {
  const byId = new Map(nodes.map(node => [node.id, node]));
  const outlines = nodes.map(node => ({ node, outline: nodeVisualOutline(node) }));
  const bodyById = new Map(outlines.map(({ node, outline }) => [node.id, outline.rectangles.map(rectangle => ({
    id: node.id, left: rectangle.x, top: rectangle.y, right: rectangle.x + rectangle.width, bottom: rectangle.y + rectangle.height }))]));
  const rectangles = [...bodyById.values()].flat();
  const ownerBounds = outlines.map(({ node, outline: { bounds } }) => ({
    id: node.id, left: bounds.x, top: bounds.y, right: bounds.x + bounds.width, bottom: bounds.y + bounds.height }));
  // Long expanded frames belong in their own index: their large vertical span
  // must not keep every earlier leaf in a dense Sequential's broad phase.
  const expandedIds = new Set(nodes.filter(node => node.expanded).map(node => node.id));
  const leavesNearY = verticalIndex(rectangles.filter(rectangle => !expandedIds.has(rectangle.id)));
  const framesNearY = verticalIndex(rectangles.filter(rectangle => expandedIds.has(rectangle.id)));
  const nearY = (top: number, bottom: number) => [...leavesNearY(top, bottom), ...framesNearY(top, bottom)];
  const headers = new Map(nodes.filter(node => node.expanded).map(node => [node.id,
    { id: node.id, left: node.x, top: node.y, right: node.x + node.width, bottom: node.y + node.headerHeight }]));
  const ancestors = new Map<string, Set<string>>();
  for (const node of nodes) { const ids = new Set<string>(); let parent = node.parentId;
    while (parent && !ids.has(parent)) { ids.add(parent); parent = byId.get(parent)?.parentId; }
    ancestors.set(node.id, ids);
  }
  const overlaps: { first: string; second: string }[] = [];
  const headerOverlaps: { node: string; ancestor: string }[] = [];
  const order = new Map(ownerBounds.map((rectangle, index) => [rectangle.id, index]));
  const ownersNearY = verticalIndex(ownerBounds);
  const overlapsInterior = (first: Rectangle, second: Rectangle) =>
    Math.min(first.right, second.right) - Math.max(first.left, second.left) > EPSILON &&
    Math.min(first.bottom, second.bottom) - Math.max(first.top, second.top) > EPSILON;
  for (let i = 0; i < ownerBounds.length; i++) for (const second of ownersNearY(ownerBounds[i].top, ownerBounds[i].bottom)) {
    if (order.get(second.id)! <= i) continue;
    const first = ownerBounds[i];
    if (ancestors.get(first.id)!.has(second.id) || ancestors.get(second.id)!.has(first.id)) continue;
    if (bodyById.get(first.id)!.some(a => bodyById.get(second.id)!.some(b => overlapsInterior(a, b)))) overlaps.push({ first: first.id, second: second.id });
  }
  for (const rectangle of ownerBounds) for (const ancestor of ancestors.get(rectangle.id)!) {
    const header = headers.get(ancestor); if (!header) continue;
    if (bodyById.get(rectangle.id)!.some(body => overlapsInterior(body, header))) headerOverlaps.push({ node: rectangle.id, ancestor });
  }
  const route = (request: RouteRequest): RouteResult => {
    const original = orthogonalPathPoints(request.preferredPath);
    const sourceBodies = bodyById.get(request.sourceId)!, targetBodies = bodyById.get(request.targetId)!;
    const excluded = new Set([request.sourceId, request.targetId, ...ancestors.get(request.sourceId) ?? [], ...ancestors.get(request.targetId) ?? []]);
    const ancestorHeaders = [...excluded].filter(id => id !== request.sourceId && id !== request.targetId).flatMap(id => headers.get(id) ?? []);
    const endpointBodies = [...sourceBodies, ...(request.sourceId === request.targetId ? [] : targetBodies)];
    const blocked = new Set(collisions(original, [...ancestorHeaders, ...endpointBodies]));
    for (let index = 1; index < original.length; index++) {
      const a = original[index - 1], b = original[index];
      for (const rectangle of nearY(Math.min(a.y, b.y), Math.max(a.y, b.y))) {
        if (!excluded.has(rectangle.id) && penetrates(a, b, rectangle)) blocked.add(rectangle.id);
      }
    }
    const blockedBy = [...blocked];
    if (!blockedBy.length) return { path: request.preferredPath, points: original, changed: false, blockedBy: [] };
    const unrelated = rectangles.filter(rectangle => !excluded.has(rectangle.id));
    const visibleObstacles = [...unrelated, ...ancestorHeaders];
    const start = { x: number(request.start.x), y: number(request.start.y) }, end = { x: number(request.end.x), y: number(request.end.y) };
    const a = lead(start, byId.get(request.sourceId)!), b = lead(end, byId.get(request.targetId)!);
    const padded = visibleObstacles.map(rectangle => ({ ...rectangle, left: rectangle.left - CLEARANCE, top: rectangle.top - CLEARANCE,
      right: rectangle.right + CLEARANCE, bottom: rectangle.bottom + CLEARANCE }));
    // Endpoint bodies remain obstacles during the middle search. Leads alone
    // are allowed to meet their own body boundary; no new route re-enters it.
    const obstacles = [...padded, ...endpointBodies];
    if (collisions([start, a], visibleObstacles).length || collisions([b, end], visibleObstacles).length ||
      obstacles.some(rectangle => inside(a, rectangle) || inside(b, rectangle))) {
      return { path: request.preferredPath, points: original, changed: false, blockedBy };
    }
    const xs = [...new Set([a.x, b.x, ...obstacles.flatMap(rectangle => [number(rectangle.left), number(rectangle.right)])])].sort((x, y) => x - y);
    const ys = [...new Set([a.y, b.y, ...obstacles.flatMap(rectangle => [number(rectangle.top), number(rectangle.bottom)])])].sort((x, y) => x - y);
    const candidates: RoutePoint[][] = [[a, { x: b.x, y: a.y }, b], [a, { x: a.x, y: b.y }, b]];
    for (const x of xs) candidates.push([a, { x, y: a.y }, { x, y: b.y }, b]);
    for (const y of ys) candidates.push([a, { x: a.x, y }, { x: b.x, y }, b]);
    let best: RoutePoint[] | undefined, bestCost = Infinity;
    for (const candidate of candidates) {
      const middle = simplified(candidate); if (collisions(middle, obstacles).length) continue;
      const complete = simplified([start, ...middle, end]);
      const candidateCost = cost(complete);
      if (candidateCost < bestCost && !collisions(complete, [...visibleObstacles, ...endpointBodies]).length) { best = complete; bestCost = candidateCost; }
    }
    if (!best) {
      const middle = gridRoute(a, b, obstacles, xs, ys);
      if (middle) { const complete = simplified([start, ...middle, end]); if (!collisions(complete, [...visibleObstacles, ...endpointBodies]).length) best = complete; }
    }
    return best ? { path: path(best), points: best, changed: true, blockedBy: [] } : { path: request.preferredPath, points: original, changed: false, blockedBy };
  };
  /** Batch refinement starts from the obstacle-safe routes above. It has no
   * hidden geometry cache: preview, commit and export receive the same paths.
   * Every accepted replacement is monotone for crossing/overlap counts against
   * the current complete batch, including the disjoint-owner subset. */
  const batch = (requests: readonly RouteRequest[]): RouteResult[] => {
    // Retain an immutable, axis-checked result as the final safety net for
    // every refinement phase. A malformed candidate must never replace this
    // baseline in the published batch.
    const initialResults = requests.map(route);
    const results = initialResults.map(result => ({ ...result, points: result.points.slice() }));
    if (!requests.length || requests.length > ROUTE_REFINEMENT_BUDGET.maxRoutes || nodes.length > ROUTE_REFINEMENT_BUDGET.maxNodes ||
      results.reduce((total, result) => total + result.points.length, 0) > ROUTE_REFINEMENT_BUDGET.maxRoutePoints) return results;
    const geometry = results.map(result => simplified(result.points, false)), boxes = geometry.map(bounds);
    const budget = { segmentChecks: 0, obstacleChecks: 0, pairChecks: 0, candidates: 0, refinedRoutes: 0 };
    const candidateAttempts = new Uint16Array(requests.length);
    const sameTensor = (i: number, j: number) => requests[i].tensorId !== undefined && requests[i].tensorId === requests[j].tensorId;
    const disjoint = (i: number, j: number) => requests[i].sourceId !== requests[j].sourceId && requests[i].sourceId !== requests[j].targetId &&
      requests[i].targetId !== requests[j].sourceId && requests[i].targetId !== requests[j].targetId;
    const measure = (i: number, candidate: RoutePoint[], candidateBounds: RouteBounds, limit?: ConflictCost): ConflictCost | undefined => {
      const metric: ConflictCost = { crossingPairs: 0, crossingPoints: 0, overlapPairs: 0, overlapLength: 0,
        disjointCrossingPairs: 0, disjointCrossingPoints: 0, disjointOverlapPairs: 0,
        sameTensorCrossingPairs: 0, sameTensorCrossingPoints: 0 };
      for (let j = 0; j < geometry.length; j++) {
        if (i === j || sameTensor(i, j) || !boundsMeet(candidateBounds, boxes[j])) continue;
        const pair = pairConflict(candidate, geometry[j], budget); if (!pair) return undefined;
        metric.crossingPairs += pair.crossingPairs; metric.crossingPoints += pair.crossingPoints;
        metric.overlapPairs += pair.overlapPairs; metric.overlapLength += pair.overlapLength;
        if (disjoint(i, j)) { metric.disjointCrossingPairs += pair.crossingPairs;
          metric.disjointCrossingPoints += pair.crossingPoints; metric.disjointOverlapPairs += pair.overlapPairs; }
        // Counts only accumulate. Once any protected count exceeds its
        // baseline, the candidate cannot be accepted and needs no full scan.
        if (limit && !conflictNoWorse(metric, limit)) return metric;
      }
      return metric;
    };
    // A vertical sweep cheaply rejects sparse chains before constructing any
    // candidate corridors. Dense batches have a separate fixed pair budget.
    const ordered = boxes.map((box, index) => ({ box, index })).sort((a, b) => a.box.top - b.box.top || a.index - b.index);
    const pressure = new Float64Array(requests.length), overlapPressure = new Float64Array(requests.length);
    for (let i = 0; i < ordered.length; i++) for (let j = i + 1; j < ordered.length; j++) {
      if (ordered[j].box.top > ordered[i].box.bottom + EPSILON) break;
      if (budget.pairChecks >= ROUTE_REFINEMENT_BUDGET.maxPairChecks) return results;
      budget.pairChecks++;
      const a = ordered[i].index, b = ordered[j].index;
      if (sameTensor(a, b) || !boundsMeet(boxes[a], boxes[b])) continue;
      const metric = pairConflict(geometry[a], geometry[b], budget); if (!metric) return results;
      for (const index of [a, b]) { pressure[index] += metric.crossingPoints + metric.overlapPairs; overlapPressure[index] += metric.overlapLength; }
    }
    const conflicted = [...pressure.keys()].filter(index => pressure[index]).sort((a, b) => pressure[b] - pressure[a] || overlapPressure[b] - overlapPressure[a] || a - b);
    const clear = (i: number, candidate: RoutePoint[]): boolean | undefined => {
      const request = requests[i], excluded = new Set([request.sourceId, request.targetId,
        ...ancestors.get(request.sourceId) ?? [], ...ancestors.get(request.targetId) ?? []]);
      const fixedObstacles = [...excluded].filter(id => id !== request.sourceId && id !== request.targetId).flatMap(id => headers.get(id) ?? []);
      fixedObstacles.push(...bodyById.get(request.sourceId)!, ...bodyById.get(request.targetId)!);
      for (let segment = 1; segment < candidate.length; segment++) {
        const a = candidate[segment - 1], b = candidate[segment];
        for (const rectangle of fixedObstacles) {
          if (budget.obstacleChecks >= ROUTE_REFINEMENT_BUDGET.maxObstacleChecks) return undefined;
          budget.obstacleChecks++;
          if (penetrates(a, b, rectangle)) return false;
        }
        for (const rectangle of nearY(Math.min(a.y, b.y), Math.max(a.y, b.y))) {
          if (excluded.has(rectangle.id)) continue;
          if (budget.obstacleChecks >= ROUTE_REFINEMENT_BUDGET.maxObstacleChecks) return undefined;
          budget.obstacleChecks++;
          if (penetrates(a, b, rectangle)) return false;
        }
      }
      return true;
    };
    const refineShortcuts = () => {
      const work: ShortcutWork = { pairs: 0, segments: 0, obstacles: 0, candidates: 0, accepted: 0 };
      const exhausted = () => work.pairs >= ROUTE_SHORTCUT_BUDGET.maxPairChecks || work.segments >= ROUTE_SHORTCUT_BUDGET.maxSegmentChecks ||
        work.obstacles >= ROUTE_SHORTCUT_BUDGET.maxObstacleChecks || work.candidates >= ROUTE_SHORTCUT_BUDGET.maxCandidates ||
        work.accepted >= ROUTE_SHORTCUT_BUDGET.maxAcceptedRoutes;
      if (nodes.length > ROUTE_SHORTCUT_BUDGET.maxNodes || requests.length > ROUTE_SHORTCUT_BUDGET.maxRoutes ||
          geometry.reduce((sum, points) => sum + points.length, 0) > ROUTE_SHORTCUT_BUDGET.maxRoutePoints) return;
      for (let i = 0; i < requests.length && !exhausted(); i++) {
        const original = geometry[i];
        if (results[i].blockedBy.length || original.length < 4 || original.length > ROUTE_SHORTCUT_BUDGET.maxPointsPerRoute ||
            !validDirections(original, original)) continue;
        const start = original[0], end = original.at(-1)!, first = direction(start, original[1]), last = direction(end, original.at(-2)!);
        const generated = new Map<string, RoutePoint[]>();
        const add = (points: RoutePoint[]) => {
          if (generated.size >= ROUTE_SHORTCUT_BUDGET.maxGeneratedPerRoute) return;
          const candidate = simplified(points, false), key = path(candidate);
          if (candidate.length > original.length || !validDirections(candidate, original) ||
              routeLength(candidate) > routeLength(original) + EPSILON || cost(candidate) >= cost(original) - EPSILON) return;
          // At least the existing six-unit escape (or shorter original lead)
          // remains before either endpoint normal is allowed to bend.
          if (routeLength(candidate.slice(0, 2)) + EPSILON < Math.min(CLEARANCE, routeLength(original.slice(0, 2))) ||
              routeLength(candidate.slice(-2)) + EPSILON < Math.min(CLEARANCE, routeLength(original.slice(-2)))) return;
          generated.set(key, candidate);
        };
        // Splicing larger subpaths first removes needless doglegs in arbitrary
        // multi-bend routes; endpoints and retained portions remain literal.
        for (let span = original.length - 1; span >= 2; span--) for (let a = 0; a + span < original.length; a++) {
          const b = a + span, p = original[a], q = original[b], prefix = original.slice(0, a + 1), suffix = original.slice(b);
          if (p.x === q.x || p.y === q.y) add([...prefix, ...suffix]);
          else { add([...prefix, { x: q.x, y: p.y }, ...suffix]); add([...prefix, { x: p.x, y: q.y }, ...suffix]); }
        }
        const coordinates = (axis: 'x' | 'y') => {
          const values = new Set(original.map(point => point[axis]));
          for (const point of original) for (const offset of [-8, 8, -16, 16]) values.add(number(point[axis] + offset));
          for (const rectangle of rectangles) {
            values.add(number((axis === 'x' ? rectangle.left : rectangle.top) - CLEARANCE));
            values.add(number((axis === 'x' ? rectangle.right : rectangle.bottom) + CLEARANCE));
          }
          const low = Math.min(start[axis], end[axis]), high = Math.max(start[axis], end[axis]);
          return [...values].sort((a, b) => Math.max(low - a, a - high, 0) - Math.max(low - b, b - high, 0) || a - b).slice(0, 64);
        };
        const xs = coordinates('x'), ys = coordinates('y');
        for (const leadLength of [undefined, CLEARANCE]) {
          const a = leadLength === undefined ? original[1] : { x: start.x + first.x * leadLength, y: start.y + first.y * leadLength };
          const b = leadLength === undefined ? original.at(-2)! : { x: end.x + last.x * leadLength, y: end.y + last.y * leadLength };
          add([start, a, { x: b.x, y: a.y }, b, end]); add([start, a, { x: a.x, y: b.y }, b, end]);
          for (const x of xs) add([start, a, { x, y: a.y }, { x, y: b.y }, b, end]);
          for (const y of ys) add([start, a, { x: a.x, y }, { x: b.x, y }, b, end]);
        }
        const request = requests[i], excluded = new Set([request.sourceId, request.targetId,
          ...ancestors.get(request.sourceId) ?? [], ...ancestors.get(request.targetId) ?? []]);
        const ownBodies = [...bodyById.get(request.sourceId)!, ...bodyById.get(request.targetId)!];
        const ancestorHeaders = [...excluded].filter(id => id !== request.sourceId && id !== request.targetId).flatMap(id => headers.get(id) ?? []);
        const padded = (rectangle: Rectangle) => ({ ...rectangle, left: rectangle.left - CLEARANCE, right: rectangle.right + CLEARANCE,
          top: rectangle.top - CLEARANCE, bottom: rectangle.bottom + CLEARANCE });
        const safelyClear = (candidate: RoutePoint[]) => {
          for (let segment = 1; segment < candidate.length; segment++) {
            const a = candidate[segment - 1], b = candidate[segment];
            const visible = nearY(Math.min(a.y, b.y) - CLEARANCE, Math.max(a.y, b.y) + CLEARANCE).filter(rectangle => !excluded.has(rectangle.id));
            const obstacles = [...ownBodies, ...ancestorHeaders.map(padded), ...visible.map(padded)];
            // Endpoint escapes may cross their padding, never the body union.
            if (segment > 1 && segment < candidate.length - 1) obstacles.push(...ownBodies.map(padded));
            for (const rectangle of obstacles) {
              if (++work.obstacles > ROUTE_SHORTCUT_BUDGET.maxObstacleChecks || shortcutPenetrates(a, b, rectangle)) return false;
            }
          }
          return true;
        };
        const candidates = [...generated.values()].sort((a, b) => cost(a) - cost(b) || path(a).localeCompare(path(b)))
          .slice(0, ROUTE_SHORTCUT_BUDGET.maxCandidatesPerRoute);
        const originalSelf = shortcutPair(original, original, work, true);
        if (!originalSelf) break;
        for (const candidate of candidates) {
          if (exhausted()) break;
          work.candidates++;
          if (!safelyClear(candidate)) continue;
          const candidateSelf = shortcutPair(candidate, candidate, work, true);
          if (!candidateSelf || !shortcutGeometrySubset(candidateSelf, originalSelf)) continue;
          const candidateBounds = bounds(candidate); let safe = true;
          for (let j = 0; j < geometry.length; j++) {
            if (i === j || !boundsMeet(candidateBounds, boxes[j]) && !boundsMeet(boxes[i], boxes[j])) continue;
            const before = shortcutPair(original, geometry[j], work), after = before && shortcutPair(candidate, geometry[j], work);
            if (!before || !after || !shortcutGeometrySubset(after, before)) { safe = false; break; }
          }
          if (!safe) continue;
          geometry[i] = candidate; boxes[i] = candidateBounds;
          results[i] = { path: path(candidate), points: candidate, changed: true, blockedBy: [] }; work.accepted++;
          break;
        }
      }
    };
    const refineComponents = () => {
      const limits = ROUTE_COMPONENT_BUDGET;
      if (nodes.length > limits.maxNodes || requests.length > limits.maxRoutes ||
          geometry.reduce((sum, points) => sum + points.length, 0) > limits.maxRoutePoints) return;
      // Keep the established source-bound route bytes for ordinary figures.
      // This pass targets the dense stress frontier where local conflicts are
      // numerous enough to justify a second bounded search. Smaller figures
      // continue through the existing family/residual/shortcut contracts.
      if (requests.length < 128) return;
      const work: ShortcutWork = { pairs: 0, segments: 0, obstacles: 0, candidates: 0, accepted: 0 };
      const exhausted = () => work.pairs >= limits.maxPairChecks || work.segments >= limits.maxSegmentChecks ||
        work.obstacles >= limits.maxObstacleChecks || work.candidates >= limits.maxCandidates || work.accepted >= limits.maxRefinedRoutes;
      const checkedPair = (a: RoutePoint[], b: RoutePoint[], self = false) => shortcutPair(a, b, work, self, limits);
      const overlapLength = (pair: ShortcutGeometry) => [...pair.overlaps.values()].flat().reduce((sum, [a, b]) => sum + b - a, 0);
      const pairScore = (pair: ShortcutGeometry, shared: boolean) => [Number(pair.crossings.length > 0) + Number(!shared && pair.overlaps.size > 0),
        pair.crossings.length, shared ? 0 : overlapLength(pair)];
      const compare = (a: number[], b: number[]) => {
        for (let n = 0; n < a.length; n++) if (Math.abs(a[n] - b[n]) > SHORTCUT_EPSILON) return a[n] < b[n] ? -1 : 1;
        return 0;
      };
      // This graph is built from the final existing batch, not the old initial
      // pressure array. A sweep leaves sparse chains cheap and a pair/segment
      // cap makes dense or unusually long polylines an explicit early exit.
      const adjacency = geometry.map(() => new Set<number>()), pressure = new Float64Array(requests.length);
      const ordered = boxes.map((box, index) => ({ box, index })).sort((a, b) => a.box.top - b.box.top || a.index - b.index);
      for (let a = 0; a < ordered.length; a++) for (let b = a + 1; b < ordered.length; b++) {
        if (ordered[b].box.top > ordered[a].box.bottom + SHORTCUT_EPSILON) break;
        const i = ordered[a].index, j = ordered[b].index;
        // The component pass targets ordinary data lanes. Memory/residual
        // continuity and family projections have stricter independent
        // contracts and are intentionally left to their existing passes.
        if (requests[i].role !== 'data' || requests[j].role !== 'data') continue;
        if (!boundsMeet(boxes[i], boxes[j])) continue;
        const pair = checkedPair(geometry[i], geometry[j]); if (!pair) return;
        const score = pairScore(pair, sameTensor(i, j));
        if (!score[0]) continue;
        adjacency[i].add(j); adjacency[j].add(i);
        pressure[i] += score[0] + score[1]; pressure[j] += score[0] + score[1];
      }
      const components: number[][] = [], visited = new Set<number>();
      for (let i = 0; i < geometry.length; i++) {
        if (visited.has(i) || !adjacency[i].size) continue;
        const pending = [i], component: number[] = []; visited.add(i);
        while (pending.length) {
          const member = pending.pop()!; component.push(member);
          for (const peer of adjacency[member]) if (!visited.has(peer)) { visited.add(peer); pending.push(peer); }
        }
        // A component must contain a genuinely routed multi-bend lane. This
        // excludes ordinary adjacent memory/residual fanout geometry whose
        // byte continuity is handled by its dedicated projection pass.
        if (component.length <= limits.maxComponentRoutes && component.some(index => geometry[index].length >= 5))
          components.push(component.sort((a, b) => pressure[b] - pressure[a] || a - b));
      }
      components.sort((a, b) => b.reduce((sum, i) => sum + pressure[i], 0) - a.reduce((sum, i) => sum + pressure[i], 0) || Math.min(...a) - Math.min(...b));
      let examined = 0;
      for (const members of components) {
        if (exhausted() || examined++ >= limits.maxComponents) break;
        // Only these members supply peer lanes. Every outside route still
        // participates in acceptance, including same-tensor routes and peers
        // whose old bounds did not meet this component.
        const componentPoints = members.flatMap(i => geometry[i]), componentBounds = bounds(componentPoints);
        for (const i of members) {
          if (exhausted()) return;
          if (requests[i].role !== 'data') continue;
          const original = geometry[i];
          if (results[i].blockedBy.length || original.length < 5 || original.length > limits.maxPointsPerRoute || !validDirections(original, original)) continue;
          const start = original[0], end = original.at(-1)!, first = direction(start, original[1]), last = direction(end, original.at(-2)!);
          const request = requests[i], excluded = new Set([request.sourceId, request.targetId,
            ...ancestors.get(request.sourceId) ?? [], ...ancestors.get(request.targetId) ?? []]);
          const ownBodies = [...bodyById.get(request.sourceId)!, ...bodyById.get(request.targetId)!];
          const ancestorHeaders = [...excluded].filter(id => id !== request.sourceId && id !== request.targetId).flatMap(id => headers.get(id) ?? []);
          const padded = (rectangle: Rectangle) => ({ ...rectangle, left: rectangle.left - CLEARANCE, right: rectangle.right + CLEARANCE,
            top: rectangle.top - CLEARANCE, bottom: rectangle.bottom + CLEARANCE });
          const safelyClear = (candidate: RoutePoint[]) => {
            for (let segment = 1; segment < candidate.length; segment++) {
              const a = candidate[segment - 1], b = candidate[segment];
              const visible = nearY(Math.min(a.y, b.y) - CLEARANCE, Math.max(a.y, b.y) + CLEARANCE).filter(rectangle => !excluded.has(rectangle.id));
              const obstacles = [...ownBodies, ...ancestorHeaders.map(padded), ...visible.map(padded)];
              if (segment > 1 && segment < candidate.length - 1) obstacles.push(...ownBodies.map(padded));
              for (const rectangle of obstacles) {
                if (++work.obstacles > limits.maxObstacleChecks || shortcutPenetrates(a, b, rectangle)) return false;
              }
            }
            return true;
          };
          const coordinates = (axis: 'x' | 'y') => {
            const values = new Set<number>(original.map(p => p[axis]));
            const addSides = (rectangle: Rectangle) => {
              for (const gap of [CLEARANCE, 14, 22]) {
                values.add(number((axis === 'x' ? rectangle.left : rectangle.top) - gap));
                values.add(number((axis === 'x' ? rectangle.right : rectangle.bottom) + gap));
              }
            };
            // Endpoint body sides and local peer segments are retained before
            // distant obstacle coordinates can crowd them out of the search.
            for (const rectangle of ownBodies) addSides(rectangle);
            for (const p of componentPoints) for (const gap of [-CLEARANCE, CLEARANCE, -14, 14, -22, 22]) values.add(number(p[axis] + gap));
            const local = { left: componentBounds.left - 22, right: componentBounds.right + 22,
              top: componentBounds.top - 22, bottom: componentBounds.bottom + 22 };
            for (const rectangle of nearY(local.top, local.bottom)) if (!excluded.has(rectangle.id) && boundsMeet(local, rectangle)) addSides(rectangle);
            const low = Math.min(start[axis], end[axis]), high = Math.max(start[axis], end[axis]);
            return [...values].sort((a, b) => Math.max(low - a, a - high, 0) - Math.max(low - b, b - high, 0) || a - b).slice(0, limits.maxCoordinatesPerAxis);
          };
          const xs = coordinates('x'), ys = coordinates('y'), generated = new Map<string, RoutePoint[]>();
          const add = (points: RoutePoint[]) => {
            if (generated.size >= limits.maxGeneratedPerRoute) return;
            const candidate = simplified(points, false), key = path(candidate);
            if (key === path(original) || candidate.length > original.length + 2 || !validDirections(candidate, original) ||
                routeLength(candidate.slice(0, 2)) + SHORTCUT_EPSILON < Math.min(CLEARANCE, routeLength(original.slice(0, 2))) ||
                routeLength(candidate.slice(-2)) + SHORTCUT_EPSILON < Math.min(CLEARANCE, routeLength(original.slice(-2)))) return;
            generated.set(key, candidate);
          };
          for (const leadLength of [CLEARANCE, 14, 22]) {
            const a = { x: start.x + first.x * leadLength, y: start.y + first.y * leadLength };
            const b = { x: end.x + last.x * leadLength, y: end.y + last.y * leadLength };
            add([start, a, { x: b.x, y: a.y }, b, end]); add([start, a, { x: a.x, y: b.y }, b, end]);
            for (const x of xs) add([start, a, { x, y: a.y }, { x, y: b.y }, b, end]);
            for (const y of ys) add([start, a, { x: a.x, y }, { x: b.x, y }, b, end]);
          }
          // A second local lane allows a dogleg around a peer and an endpoint
          // body. The existing generic pass offers only one x or one y lane.
          const a = { x: start.x + first.x * CLEARANCE, y: start.y + first.y * CLEARANCE };
          const b = { x: end.x + last.x * CLEARANCE, y: end.y + last.y * CLEARANCE };
          for (let lane = 0; lane < 8; lane++) for (let other = 0; other < 8; other++) for (let bridge = 0; bridge < 4; bridge++) {
            if (first.y && last.y && xs[lane] !== undefined && xs[other] !== undefined && ys[bridge] !== undefined)
              add([start, a, { x: xs[lane], y: a.y }, { x: xs[lane], y: ys[bridge] }, { x: xs[other], y: ys[bridge] }, { x: xs[other], y: b.y }, b, end]);
            if (first.x && last.x && ys[lane] !== undefined && ys[other] !== undefined && xs[bridge] !== undefined)
              add([start, a, { x: a.x, y: ys[lane] }, { x: xs[bridge], y: ys[lane] }, { x: xs[bridge], y: ys[other] }, { x: b.x, y: ys[other] }, b, end]);
          }
          const candidates = [...generated.values()].sort((a, b) => cost(a) - cost(b) || path(a).localeCompare(path(b))).slice(0, limits.maxCandidatesPerRoute);
          const originalSelf = checkedPair(original, original, true); if (!originalSelf) return;
          const beforePairs = new Map<number, ShortcutGeometry>();
          const beforeFor = (j: number) => {
            let pair = beforePairs.get(j);
            if (!pair) { pair = checkedPair(original, geometry[j]); if (pair) beforePairs.set(j, pair); }
            return pair;
          };
          let best: RoutePoint[] | undefined, bestScore: number[] | undefined;
          for (const candidate of candidates) {
            if (exhausted()) break;
            work.candidates++;
            if (!safelyClear(candidate)) continue;
            const self = checkedPair(candidate, candidate, true); if (!self || !shortcutGeometrySubset(self, originalSelf)) continue;
            const candidateBounds = bounds(candidate), beforeScore = [0, 0, 0], afterScore = [0, 0, 0]; let safe = true;
            for (let j = 0; j < geometry.length; j++) {
              if (i === j || !boundsMeet(candidateBounds, boxes[j]) && !boundsMeet(boxes[i], boxes[j])) continue;
              const before = beforeFor(j), after = before && checkedPair(candidate, geometry[j]);
              // Geometry, rather than a same-tensor label or an aggregate
              // improvement, authorizes every affected pair. Existing shared
              // trunks may shrink, but no new trunk/contact/crossing is hidden.
              if (!before || !after || !shortcutGeometrySubset(after, before)) { safe = false; break; }
              const oldMetric = pairScore(before, sameTensor(i, j)), newMetric = pairScore(after, sameTensor(i, j));
              for (let n = 0; n < 3; n++) { beforeScore[n] += oldMetric[n]; afterScore[n] += newMetric[n]; }
            }
            if (!safe) continue;
            const benefit = compare(afterScore, beforeScore);
            if (benefit > 0 || benefit === 0 && (candidate.length > original.length || cost(candidate) >= cost(original) - SHORTCUT_EPSILON)) continue;
            const score = [...afterScore, cost(candidate)], better = !bestScore || compare(score, bestScore) < 0;
            if (better) { best = candidate; bestScore = score; }
            // The lowest-cost checked candidate with no forbidden pair left
            // is optimal inside this generated finite set; no later candidate
            // can improve its conflict score or length/bend cost.
            if (!afterScore[0] && !afterScore[1] && !afterScore[2]) break;
          }
          if (best) {
            geometry[i] = best; boxes[i] = bounds(best); work.accepted++;
            results[i] = { path: path(best), points: best, changed: true, blockedBy: [] };
          }
        }
      }
    };
    const refineCollapsedResiduals = () => {
      for (const [i, request] of requests.entries()) {
        const source = byId.get(request.sourceId)!, target = byId.get(request.targetId)!;
        const canonicalSource = request.canonicalSource, canonicalTarget = request.canonicalTarget, appearance = request.appearance;
        if (request.role !== 'residual' || !canonicalSource?.nodeId || !canonicalSource.portId ||
            !canonicalTarget?.nodeId || !canonicalTarget.portId || canonicalTarget.nodeId === target.id ||
            !target.expandable || target.expanded || !request.tensorId || !request.canonicalEdgeIds?.length ||
            !validAppearance(appearance) ||
            results[i].blockedBy.length || request.displaySide !== 'bottom' || visualPortSide(source, request.start) !== 'bottom' ||
            visualPortSide(target, request.end) !== 'top' || request.end.y - request.start.y < CLEARANCE * 2) continue;
        const hasPort = (node: SceneNode, endpoint: RoutePoint, canonical: RouteCanonicalSource, direction: 'in' | 'out', proxy: boolean) =>
          node.ports.some(port => port.direction === direction && (!proxy || port.proxy) && port.x === endpoint.x && port.y === endpoint.y &&
            port.canonicalNodeId === canonical.nodeId && port.canonicalPortId === canonical.portId &&
            port.canonicalBindings.length > 0 && port.canonicalBindings.every(binding => binding.nodeId === canonical.nodeId && binding.portId === canonical.portId) &&
            request.canonicalEdgeIds!.every(id => port.canonicalEdgeIds.includes(id)));
        if (!hasPort(source, request.start, canonicalSource, 'out', false) || !hasPort(target, request.end, canonicalTarget, 'in', true)) continue;
        if (budget.refinedRoutes >= ROUTE_REFINEMENT_BUDGET.maxRefinedRoutes || budget.candidates >= ROUTE_REFINEMENT_BUDGET.maxCandidates) break;
        const original = geometry[i], start = original[0], end = original.at(-1)!;
        // Scene preferred paths serialize to tenths; obstacle fallback paths
        // serialize to hundredths. Keep those exact existing path endpoints,
        // while verifying they are projections of the immutable public ports.
        const projected = (actual: number, endpoint: number) => actual === number(endpoint) || actual === Math.round(endpoint * 10) / 10;
        if (original.length < 2 || !projected(start.x, request.start.x) || !projected(start.y, request.start.y) ||
            !projected(end.x, request.end.x) || !projected(end.y, request.end.y)) continue;
        budget.refinedRoutes++;
        let best = original, bestCost = cost(original);
        const lanes = [...new Set([number((start.y + end.y) / 2), number(start.y + CLEARANCE), number(end.y - CLEARANCE)])];
        for (const y of lanes) {
          if (budget.candidates >= ROUTE_REFINEMENT_BUDGET.maxCandidates || candidateAttempts[i] >= ROUTE_REFINEMENT_BUDGET.maxCandidatesPerRoute) break;
          budget.candidates++; candidateAttempts[i]++;
          const candidate = simplified([start, { x: start.x, y }, { x: end.x, y }, end], false);
          if (candidate.length > original.length || routeLength(candidate) >= routeLength(original) - EPSILON || !validDirections(candidate, original)) continue;
          const safe = clear(i, candidate); if (safe !== true) continue;
          const candidateBounds = bounds(candidate); let monotone = true;
          // All affected pairs are protected individually. Equal tensor IDs
          // do not permit data/residual merging or hide new overlaps/crossings.
          for (let j = 0; j < geometry.length; j++) {
            if (i === j || !boundsMeet(candidateBounds, boxes[j]) && !boundsMeet(boxes[i], boxes[j])) continue;
            if (budget.pairChecks + 2 > ROUTE_REFINEMENT_BUDGET.maxPairChecks) { monotone = false; break; }
            budget.pairChecks += 2;
            const before = pairConflict(original, geometry[j], budget, true), after = pairConflict(candidate, geometry[j], budget, true);
            if (!before || !after || after.crossingPairs > before.crossingPairs || after.crossingPoints > before.crossingPoints ||
                after.overlapPairs > before.overlapPairs || after.overlapLength > before.overlapLength + EPSILON) { monotone = false; break; }
          }
          if (monotone && cost(candidate) < bestCost - EPSILON) { best = candidate; bestCost = cost(candidate); }
        }
        if (best !== original) {
          geometry[i] = best; boxes[i] = bounds(best);
          results[i] = { path: path(best), points: best, changed: true, blockedBy: [] };
        }
        if (budget.segmentChecks >= ROUTE_REFINEMENT_BUDGET.maxSegmentChecks || budget.obstacleChecks >= ROUTE_REFINEMENT_BUDGET.maxObstacleChecks) break;
      }
    };
    // A clear proxy residual can still make a long detour without conflict
    // pressure. It needs this bounded proposal even when the generic pass exits.
    if (!conflicted.length) { refineCollapsedResiduals(); refineShortcuts(); refineComponents(); return refineReadableRoutes(nodes, requests, results); }
    // Shared-source proposals use exact, resolved canonical identity and the
    // current rendered appearance. Equal tensor names alone are insufficient.
    const familyMembers = new Map<string, number[]>(), familyKeys = new Map<number, string>();
    for (const [index, request] of requests.entries()) {
      const { canonicalSource: canonical, appearance } = request, source = byId.get(request.sourceId)!;
      if (request.role !== 'memory' || !canonical?.nodeId || !canonical.portId || !request.tensorId || !validAppearance(appearance) || results[index].blockedBy.length) continue;
      const port = source.ports.find(item => item.direction === 'out' && item.x === request.start.x && item.y === request.start.y &&
        item.canonicalBindings.length > 0 && item.canonicalBindings.every(binding => binding.nodeId === canonical.nodeId && binding.portId === canonical.portId) &&
        request.canonicalEdgeIds?.length && request.canonicalEdgeIds.every(id => item.canonicalEdgeIds.includes(id)));
      if (!port) continue;
      const side = visualPortSide(source, request.start);
      if (request.displaySide !== undefined && request.displaySide !== side) continue;
      const key = JSON.stringify([request.sourceId, canonical.nodeId, canonical.portId, request.tensorId, request.role,
        edgeAppearanceKey(appearance), side, request.start.x, request.start.y]);
      const members = familyMembers.get(key) ?? []; members.push(index); familyMembers.set(key, members); familyKeys.set(index, key);
    }
    const familyDone = new Set<string>();
    const ancestorCorridors = (members: number[]): number[] => {
      const first = requests[members[0]], sourceChain = [first.sourceId, ...ancestors.get(first.sourceId) ?? []];
      // Find the outermost source-only frame before the common ancestry. This
      // selects a corridor beside the endpoint branches rather than the page.
      const sourceOnly = sourceChain.filter(id => members.every(index => id !== requests[index].targetId && !ancestors.get(requests[index].targetId)?.has(id)));
      const frame = sourceOnly.map(id => byId.get(id)!).filter(node => node.expanded).at(-1);
      if (!frame) return [];
      const outline = nodeVisualOutline(frame).bounds;
      const targetCenters = members.map(index => { const target = byId.get(requests[index].targetId)!; return target.x + target.width / 2; });
      const rightward = targetCenters.every(x => x > outline.x + outline.width);
      const leftward = targetCenters.every(x => x < outline.x);
      if (!rightward && !leftward) return [];
      const border = rightward ? outline.x + outline.width : outline.x, sign = rightward ? 1 : -1;
      // These are the existing bounded obstacle offsets, promoted ahead of
      // nearest-coordinate candidates for a relevant ancestor corridor.
      return [number(border + sign * CLEARANCE), number(border + sign * 14)];
    };
    const familyCandidate = (members: number[], lane: number): RoutePoint[][] | undefined => {
      const originals = members.map(index => geometry[index]);
      // This bounded proposal only replaces a V-H-V-H-V corridor. More complex
      // routes stay with the existing single-route refinement.
      if (originals.some(points => points.length !== 6 || points[0].x !== points[1].x || points[1].y !== points[2].y ||
          points[2].x !== points[3].x || points[3].y !== points[4].y || points[4].x !== points[5].x)) return undefined;
      const source = originals[0][0], firstDirection = direction(source, originals[0][1]);
      if (!firstDirection.y || originals.some(points => points[0].x !== source.x || points[0].y !== source.y ||
          direction(points[0], points[1]).y !== firstDirection.y)) return undefined;
      const gate = firstDirection.y > 0 ? Math.min(...originals.map(points => points[1].y)) : Math.max(...originals.map(points => points[1].y));
      return originals.map(points => simplified([points[0], { x: source.x, y: gate }, { x: lane, y: gate },
        { x: lane, y: points[4].y }, points[4], points[5]], false));
    };
    const measureFamily = (members: number[], candidates: RoutePoint[][], limit?: ConflictCost): ConflictCost | undefined => {
      const candidateByIndex = new Map(members.map((index, n) => [index, candidates[n]]));
      const metric: ConflictCost = { crossingPairs: 0, crossingPoints: 0, overlapPairs: 0, overlapLength: 0,
        disjointCrossingPairs: 0, disjointCrossingPoints: 0, disjointOverlapPairs: 0, sameTensorCrossingPairs: 0, sameTensorCrossingPoints: 0 };
      // Score every affected unordered pair once, including pairs within the
      // family. Unaffected pairs cancel in the complete-batch comparison.
      for (const i of members) for (let j = 0; j < geometry.length; j++) {
        if (i === j || candidateByIndex.has(j) && j < i) continue;
        const a = candidateByIndex.get(i)!, b = candidateByIndex.get(j) ?? geometry[j];
        if (!boundsMeet(bounds(a), bounds(b))) continue;
        const pair = pairConflict(a, b, budget); if (!pair) return undefined;
        if (sameTensor(i, j)) {
          metric.sameTensorCrossingPairs += pair.crossingPairs; metric.sameTensorCrossingPoints += pair.crossingPoints;
          if (limit && pair.crossingPoints) {
            const baseline = pairConflict(geometry[i], geometry[j], budget); if (!baseline) return undefined;
            if (pair.crossingPairs > baseline.crossingPairs || pair.crossingPoints > baseline.crossingPoints) {
              metric.sameTensorCrossingPairs = limit.sameTensorCrossingPairs + 1;
              metric.sameTensorCrossingPoints = limit.sameTensorCrossingPoints + 1;
              return metric;
            }
          }
        }
        else {
          metric.crossingPairs += pair.crossingPairs; metric.crossingPoints += pair.crossingPoints;
          metric.overlapPairs += pair.overlapPairs; metric.overlapLength += pair.overlapLength;
          if (disjoint(i, j)) { metric.disjointCrossingPairs += pair.crossingPairs; metric.disjointCrossingPoints += pair.crossingPoints; metric.disjointOverlapPairs += pair.overlapPairs; }
        }
        if (limit && !conflictNoWorse(metric, limit)) return metric;
      }
      return metric;
    };
    const familyQueue = [...familyMembers.entries()].filter(([, members]) => members.length > 1 && members.some(index => pressure[index] > 0))
      .sort((a, b) => Math.max(...b[1].map(index => overlapPressure[index])) - Math.max(...a[1].map(index => overlapPressure[index])) || a[1][0] - b[1][0]);
    const reservedFamily = familyQueue.find(([, members]) => members.length === 2 && ancestorCorridors(members).length > 0 &&
      familyCandidate(members, ancestorCorridors(members)[0]) !== undefined);
    const reservedMembers = new Set(reservedFamily?.[1] ?? []);
    const genericCandidateCap = ROUTE_REFINEMENT_BUDGET.maxCandidates - reservedMembers.size * 2;
    const genericRouteCap = ROUTE_REFINEMENT_BUDGET.maxRefinedRoutes - reservedMembers.size;
    const refineFamilies = () => { for (const [key, members] of familyQueue) {
      if (budget.refinedRoutes + members.length > ROUTE_REFINEMENT_BUDGET.maxRefinedRoutes) continue;
      const lanes = ancestorCorridors(members); if (!lanes.length) continue;
      const original = members.map(index => geometry[index]), originalMetric = measureFamily(members, original); if (!originalMetric) break;
      const originalLength = original.reduce((sum, points) => sum + routeLength(points), 0), originalBends = original.reduce((sum, points) => sum + points.length - 2, 0);
      budget.refinedRoutes += members.length;
      let best: RoutePoint[][] | undefined, bestMetric = originalMetric, bestLength = originalLength;
      for (const lane of lanes) {
        if (budget.candidates + members.length > ROUTE_REFINEMENT_BUDGET.maxCandidates || members.some(index => candidateAttempts[index] >= ROUTE_REFINEMENT_BUDGET.maxCandidatesPerRoute)) break;
        budget.candidates += members.length; for (const index of members) candidateAttempts[index]++;
        const candidate = familyCandidate(members, lane); if (!candidate) continue;
        const candidateLength = candidate.reduce((sum, points) => sum + routeLength(points), 0), candidateBends = candidate.reduce((sum, points) => sum + points.length - 2, 0);
        if (candidateLength > originalLength + EPSILON || candidateBends > originalBends || candidate.some((points, n) => !validDirections(points, original[n]))) continue;
        let safe = true;
        for (const [n, index] of members.entries()) { const outcome = clear(index, candidate[n]); if (outcome !== true) { safe = false; break; } }
        if (!safe) continue;
        const metric = measureFamily(members, candidate, originalMetric); if (!metric || !conflictNoWorse(metric, originalMetric)) continue;
        const current = [metric.crossingPairs + metric.overlapPairs, metric.crossingPoints, metric.overlapLength, candidateLength];
        const previous = [bestMetric.crossingPairs + bestMetric.overlapPairs, bestMetric.crossingPoints, bestMetric.overlapLength, bestLength];
        const firstDifference = current.findIndex((value, n) => Math.abs(value - previous[n]) > EPSILON);
        if (firstDifference >= 0 && current[firstDifference] < previous[firstDifference]) { best = candidate; bestMetric = metric; bestLength = candidateLength; }
      }
      if (best) {
        for (const [n, index] of members.entries()) { geometry[index] = best[n]; boxes[index] = bounds(best[n]); results[index] = { path: path(best[n]), points: best[n], changed: true, blockedBy: [] }; }
        familyDone.add(key);
      }
      if (budget.segmentChecks >= ROUTE_REFINEMENT_BUDGET.maxSegmentChecks || budget.obstacleChecks >= ROUTE_REFINEMENT_BUDGET.maxObstacleChecks) break;
    } };
    const coordinates = (axis: 'x' | 'y', points: RoutePoint[]) => {
      const existing = points.map(point => point[axis]), values = new Set<number>();
      // Preserve nearby authored lanes first; obstacle side lanes then supply
      // shortcuts around expanded frames without changing any object anchor.
      for (const value of existing) for (const delta of [0, -8, 8, -16, 16]) values.add(number(value + delta));
      for (const rectangle of rectangles) for (const delta of [CLEARANCE, 14, 22]) {
        values.add(number((axis === 'x' ? rectangle.left : rectangle.top) - delta));
        values.add(number((axis === 'x' ? rectangle.right : rectangle.bottom) + delta));
      }
      const ranked = [...values].map(value => {
        let distance = Infinity; for (const anchor of existing) distance = Math.min(distance, Math.abs(value - anchor));
        return { value, distance };
      });
      return ranked.sort((a, b) => a.distance - b.distance || a.value - b.value).slice(0, 24).map(item => item.value);
    };
    outer: for (let pass = 0; pass < ROUTE_REFINEMENT_BUDGET.passes; pass++) for (const i of conflicted) {
      const resolvedFamilyKey = familyKeys.get(i);
      if (resolvedFamilyKey && familyDone.has(resolvedFamilyKey)) continue;
      if (results[i].blockedBy.length || geometry[i].length < 2) continue;
      if (budget.refinedRoutes >= genericRouteCap || budget.candidates >= genericCandidateCap) break outer;
      const original = geometry[i], originalMetric = measure(i, original, boxes[i]); if (!originalMetric) break outer;
      if (!originalMetric.crossingPairs && !originalMetric.overlapPairs) continue;
      budget.refinedRoutes++;
      const start = original[0], end = original.at(-1)!, sourceDirection = direction(start, original[1]), targetDirection = direction(end, original.at(-2)!);
      const xs = coordinates('x', original), ys = coordinates('y', original), seen = new Set<string>();
      let best = original, bestMetric = originalMetric, attempted = 0;
      const leads = [6, 14, 22].map(leadLength => {
        const a = { x: start.x + sourceDirection.x * leadLength, y: start.y + sourceDirection.y * leadLength };
        const b = { x: end.x + targetDirection.x * leadLength, y: end.y + targetDirection.y * leadLength };
        return { a, b };
      });
      const middles: RoutePoint[][] = leads.flatMap(({ a, b }) => [[a, { x: b.x, y: a.y }, b], [a, { x: a.x, y: b.y }, b]]);
      for (let lane = 0; lane < Math.max(xs.length, ys.length); lane++) for (const { a, b } of leads) {
        if (lane < xs.length) middles.push([a, { x: xs[lane], y: a.y }, { x: xs[lane], y: b.y }, b]);
        if (lane < ys.length) middles.push([a, { x: a.x, y: ys[lane] }, { x: b.x, y: ys[lane] }, b]);
      }
      for (const middle of middles) {
          if (attempted >= ROUTE_REFINEMENT_BUDGET.maxCandidatesPerRoute - (reservedMembers.has(i) ? 2 : 0) || budget.candidates >= genericCandidateCap) break;
          attempted++; candidateAttempts[i]++; budget.candidates++;
          const candidate = simplified([start, ...middle, end], false), key = path(candidate);
          if (seen.has(key) || !validDirections(candidate, original)) continue; seen.add(key);
          const safe = clear(i, candidate); if (safe === undefined) break; if (!safe) continue;
          const metric = measure(i, candidate, bounds(candidate), originalMetric); if (!metric) break;
          if (conflictNoWorse(metric, originalMetric) && conflictBetter(metric, candidate, bestMetric, best)) { best = candidate; bestMetric = metric; }
      }
      if (best !== original) {
        geometry[i] = best; boxes[i] = bounds(best);
        results[i] = { path: path(best), points: best, changed: true, blockedBy: [] };
      }
      if (budget.segmentChecks >= ROUTE_REFINEMENT_BUDGET.maxSegmentChecks || budget.obstacleChecks >= ROUTE_REFINEMENT_BUDGET.maxObstacleChecks) break outer;
    }
    refineFamilies();
    refineCollapsedResiduals();
    refineShortcuts();
    refineComponents();
    const refined = refineReadableRoutes(nodes, requests, results);
    return refined.map((result, index) => {
      if (isOrthogonal(result.points)) return result;
      const fallback = initialResults[index];
      return { ...fallback, points: fallback.points.slice() };
    });
  };
  return Object.assign(route, { overlaps, headerOverlaps, batch });
}
