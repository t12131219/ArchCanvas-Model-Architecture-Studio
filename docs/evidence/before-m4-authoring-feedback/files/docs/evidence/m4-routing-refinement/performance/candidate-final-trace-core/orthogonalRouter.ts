import type { SceneNode } from './types.ts';

export type RoutePoint = { x: number; y: number };
type Rectangle = { id: string; left: number; top: number; right: number; bottom: number };
export interface RouteRequest { sourceId: string; targetId: string; start: RoutePoint; end: RoutePoint; preferredPath: string; tensorId?: string }
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
type RouteBounds = { left: number; top: number; right: number; bottom: number };
type ConflictCost = { crossingPairs: number; crossingPoints: number; overlapPairs: number; overlapLength: number;
  disjointCrossingPairs: number; disjointCrossingPoints: number; disjointOverlapPairs: number };
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
    candidate.disjointCrossingPairs <= original.disjointCrossingPairs && candidate.disjointCrossingPoints <= original.disjointCrossingPoints && candidate.disjointOverlapPairs <= original.disjointOverlapPairs;
}
function conflictBetter(candidate: ConflictCost, candidatePath: RoutePoint[], original: ConflictCost, originalPath: RoutePoint[]) {
  const a = [candidate.crossingPairs + candidate.overlapPairs, candidate.crossingPoints, candidate.overlapLength, cost(candidatePath)];
  const b = [original.crossingPairs + original.overlapPairs, original.crossingPoints, original.overlapLength, cost(originalPath)];
  for (let index = 0; index < a.length; index++) if (Math.abs(a[index] - b[index]) > EPSILON) return a[index] < b[index];
  return false;
}
/** Strict segment intersections exclude mere endpoint contact; identical tensors may share a trunk. */
function pairConflict(first: RoutePoint[], second: RoutePoint[], budget: { segmentChecks: number }) {
  const crossingPoints = new Set<string>(); let overlapLength = 0;
  for (let i = 1; i < first.length; i++) for (let j = 1; j < second.length; j++) {
    if (budget.segmentChecks >= ROUTE_REFINEMENT_BUDGET.maxSegmentChecks) return undefined;
    budget.segmentChecks++;
    const a = first[i - 1], b = first[i], c = second[j - 1], d = second[j];
    const av = a.x === b.x, cv = c.x === d.x;
    if (av !== cv) {
      const verticalA = av ? a : c, verticalB = av ? b : d, horizontalA = av ? c : a, horizontalB = av ? d : b;
      if (verticalA.x > Math.min(horizontalA.x, horizontalB.x) + EPSILON && verticalA.x < Math.max(horizontalA.x, horizontalB.x) - EPSILON &&
        horizontalA.y > Math.min(verticalA.y, verticalB.y) + EPSILON && horizontalA.y < Math.max(verticalA.y, verticalB.y) - EPSILON) {
        crossingPoints.add(`${verticalA.x}:${horizontalA.y}`);
      }
    } else if (av && Math.abs(a.x - c.x) < EPSILON) {
      overlapLength += Math.max(0, Math.min(Math.max(a.y, b.y), Math.max(c.y, d.y)) - Math.max(Math.min(a.y, b.y), Math.min(c.y, d.y)));
    } else if (!av && Math.abs(a.y - c.y) < EPSILON) {
      overlapLength += Math.max(0, Math.min(Math.max(a.x, b.x), Math.max(c.x, d.x)) - Math.max(Math.min(a.x, b.x), Math.min(c.x, d.x)));
    }
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
function lead(point: RoutePoint, rectangle: Rectangle): RoutePoint {
  const sides = [
    { distance: Math.abs(point.y - rectangle.bottom), x: point.x, y: point.y + CLEARANCE },
    { distance: Math.abs(point.y - rectangle.top), x: point.x, y: point.y - CLEARANCE },
    { distance: Math.abs(point.x - rectangle.right), x: point.x + CLEARANCE, y: point.y },
    { distance: Math.abs(point.x - rectangle.left), x: point.x - CLEARANCE, y: point.y },
  ].sort((a, b) => a.distance - b.distance);
  return { x: number(sides[0].x), y: number(sides[0].y) };
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
  const rectangles = nodes.map(node => ({ id: node.id, left: node.x, top: node.y, right: node.x + node.width, bottom: node.y + node.height }));
  const rectangleById = new Map(rectangles.map(rectangle => [rectangle.id, rectangle]));
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
  const order = new Map(rectangles.map((rectangle, index) => [rectangle.id, index]));
  for (let i = 0; i < rectangles.length; i++) for (const second of nearY(rectangles[i].top, rectangles[i].bottom)) {
    if (order.get(second.id)! <= i) continue;
    const first = rectangles[i];
    if (ancestors.get(first.id)!.has(second.id) || ancestors.get(second.id)!.has(first.id)) continue;
    if (Math.min(first.right, second.right) - Math.max(first.left, second.left) > EPSILON &&
      Math.min(first.bottom, second.bottom) - Math.max(first.top, second.top) > EPSILON) overlaps.push({ first: first.id, second: second.id });
  }
  for (const rectangle of rectangles) for (const ancestor of ancestors.get(rectangle.id)!) {
    const header = headers.get(ancestor); if (!header) continue;
    if (Math.min(rectangle.right, header.right) - Math.max(rectangle.left, header.left) > EPSILON &&
      Math.min(rectangle.bottom, header.bottom) - Math.max(rectangle.top, header.top) > EPSILON) headerOverlaps.push({ node: rectangle.id, ancestor });
  }
  const route = (request: RouteRequest): RouteResult => {
    const original = orthogonalPathPoints(request.preferredPath);
    const source = rectangleById.get(request.sourceId)!, target = rectangleById.get(request.targetId)!;
    const excluded = new Set([request.sourceId, request.targetId, ...ancestors.get(request.sourceId) ?? [], ...ancestors.get(request.targetId) ?? []]);
    const ancestorHeaders = [...excluded].filter(id => id !== request.sourceId && id !== request.targetId).flatMap(id => headers.get(id) ?? []);
    const endpointBodies = [source, ...(source.id === target.id ? [] : [target])];
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
    const a = lead(start, source), b = lead(end, target);
    const padded = visibleObstacles.map(rectangle => ({ ...rectangle, left: rectangle.left - CLEARANCE, top: rectangle.top - CLEARANCE,
      right: rectangle.right + CLEARANCE, bottom: rectangle.bottom + CLEARANCE }));
    // Endpoint bodies remain obstacles during the middle search. Leads alone
    // are allowed to meet their own body boundary; no new route re-enters it.
    const obstacles = [...padded, source, ...(source.id === target.id ? [] : [target])];
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
    const auditCall: any = { nodes: nodes.length, routes: requests.length, routePoints: results.reduce((total, result) => total + result.points.length, 0) };
    (globalThis as any).__ARCHCANVAS_ROUTE_CPU_TRACE__.push(auditCall);
    if (requests.length < 2 || requests.length > ROUTE_REFINEMENT_BUDGET.maxRoutes || nodes.length > ROUTE_REFINEMENT_BUDGET.maxNodes ||
      results.reduce((total, result) => total + result.points.length, 0) > ROUTE_REFINEMENT_BUDGET.maxRoutePoints) return results;
    const geometry = results.map(result => simplified(result.points, false)), boxes = geometry.map(bounds);
    const budget = { segmentChecks: 0, obstacleChecks: 0, pairChecks: 0, candidates: 0, refinedRoutes: 0 };
    auditCall.budget = budget;
    const sameTensor = (i: number, j: number) => requests[i].tensorId !== undefined && requests[i].tensorId === requests[j].tensorId;
    const disjoint = (i: number, j: number) => requests[i].sourceId !== requests[j].sourceId && requests[i].sourceId !== requests[j].targetId &&
      requests[i].targetId !== requests[j].sourceId && requests[i].targetId !== requests[j].targetId;
    const measure = (i: number, candidate: RoutePoint[], candidateBounds: RouteBounds, limit?: ConflictCost): ConflictCost | undefined => {
      const metric: ConflictCost = { crossingPairs: 0, crossingPoints: 0, overlapPairs: 0, overlapLength: 0,
        disjointCrossingPairs: 0, disjointCrossingPoints: 0, disjointOverlapPairs: 0 };
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
    if (!conflicted.length) return results;
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
      if (results[i].blockedBy.length || geometry[i].length < 2) continue;
      if (budget.refinedRoutes >= ROUTE_REFINEMENT_BUDGET.maxRefinedRoutes || budget.candidates >= ROUTE_REFINEMENT_BUDGET.maxCandidates) break outer;
      const original = geometry[i], originalMetric = measure(i, original, boxes[i]); if (!originalMetric) break outer;
      if (!originalMetric.crossingPairs && !originalMetric.overlapPairs) continue;
      budget.refinedRoutes++;
      const request = requests[i], excluded = new Set([request.sourceId, request.targetId,
        ...ancestors.get(request.sourceId) ?? [], ...ancestors.get(request.targetId) ?? []]);
      const fixedObstacles = [...excluded].filter(id => id !== request.sourceId && id !== request.targetId).flatMap(id => headers.get(id) ?? []);
      fixedObstacles.push(rectangleById.get(request.sourceId)!, rectangleById.get(request.targetId)!);
      const clear = (candidate: RoutePoint[]): boolean | undefined => {
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
          if (attempted >= ROUTE_REFINEMENT_BUDGET.maxCandidatesPerRoute || budget.candidates >= ROUTE_REFINEMENT_BUDGET.maxCandidates) break;
          attempted++; budget.candidates++;
          const candidate = simplified([start, ...middle, end], false), key = path(candidate);
          if (seen.has(key) || !validDirections(candidate, original)) continue; seen.add(key);
          const safe = clear(candidate); if (safe === undefined) break; if (!safe) continue;
          const metric = measure(i, candidate, bounds(candidate), originalMetric); if (!metric) break;
          if (conflictNoWorse(metric, originalMetric) && conflictBetter(metric, candidate, bestMetric, best)) { best = candidate; bestMetric = metric; }
      }
      if (best !== original) {
        geometry[i] = best; boxes[i] = bounds(best);
        results[i] = { path: path(best), points: best, changed: true, blockedBy: [] };
      }
      if (budget.segmentChecks >= ROUTE_REFINEMENT_BUDGET.maxSegmentChecks || budget.obstacleChecks >= ROUTE_REFINEMENT_BUDGET.maxObstacleChecks) break outer;
    }
    return results;
  };
  return Object.assign(route, { overlaps, headerOverlaps, batch });
}
