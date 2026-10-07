import type { EdgeRole, SceneNode } from './types.ts';
import { nodeVisualOutline, visualPortSide } from './nodeVisualOutline.ts';

export type RoutePoint = { x: number; y: number };
type Rectangle = { id: string; left: number; top: number; right: number; bottom: number };
export interface RouteAppearance { stroke: string; width: number; dashed: boolean }
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
/** Deterministic work caps, not a wall-clock timeout or a performance claim. */
export const ROUTE_REFINEMENT_BUDGET = Object.freeze({ maxNodes: 1_024, maxRoutes: 512, maxRoutePoints: 4_096, maxPairChecks: 32_768,
  maxSegmentChecks: 150_000, maxObstacleChecks: 60_000, maxCandidates: 384, maxCandidatesPerRoute: 80, maxRefinedRoutes: 8, passes: 2 });

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
    const results = requests.map(route);
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
    const refineCollapsedResiduals = () => {
      for (const [i, request] of requests.entries()) {
        const source = byId.get(request.sourceId)!, target = byId.get(request.targetId)!;
        const canonicalSource = request.canonicalSource, canonicalTarget = request.canonicalTarget, appearance = request.appearance;
        if (request.role !== 'residual' || !canonicalSource?.nodeId || !canonicalSource.portId ||
            !canonicalTarget?.nodeId || !canonicalTarget.portId || canonicalTarget.nodeId === target.id ||
            !target.expandable || target.expanded || !request.tensorId || !request.canonicalEdgeIds?.length ||
            !appearance?.stroke || !Number.isFinite(appearance.width) || appearance.width <= 0 || typeof appearance.dashed !== 'boolean' ||
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
    if (!conflicted.length) { refineCollapsedResiduals(); return results; }
    // Shared-source proposals use exact, resolved canonical identity and the
    // current rendered appearance. Equal tensor names alone are insufficient.
    const familyMembers = new Map<string, number[]>(), familyKeys = new Map<number, string>();
    for (const [index, request] of requests.entries()) {
      const { canonicalSource: canonical, appearance } = request, source = byId.get(request.sourceId)!;
      if (request.role !== 'memory' || !canonical?.nodeId || !canonical.portId || !request.tensorId || !appearance?.stroke ||
          !Number.isFinite(appearance.width) || appearance.width <= 0 || typeof appearance.dashed !== 'boolean' || results[index].blockedBy.length) continue;
      const port = source.ports.find(item => item.direction === 'out' && item.x === request.start.x && item.y === request.start.y &&
        item.canonicalBindings.length > 0 && item.canonicalBindings.every(binding => binding.nodeId === canonical.nodeId && binding.portId === canonical.portId) &&
        request.canonicalEdgeIds?.length && request.canonicalEdgeIds.every(id => item.canonicalEdgeIds.includes(id)));
      if (!port) continue;
      const side = visualPortSide(source, request.start);
      if (request.displaySide !== undefined && request.displaySide !== side) continue;
      const key = JSON.stringify([request.sourceId, canonical.nodeId, canonical.portId, request.tensorId, request.role,
        appearance.stroke, appearance.width, appearance.dashed, side, request.start.x, request.start.y]);
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
    return results;
  };
  return Object.assign(route, { overlaps, headerOverlaps, batch });
}
