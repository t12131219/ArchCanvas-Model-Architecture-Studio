import assert from 'node:assert/strict';
import type { Scene, SceneEdge } from '../../../../studio/src/core/types.ts';

export type Point = { x: number; y: number };
const epsilon = 1e-6;
const near = (a: number, b: number) => Math.abs(a - b) < epsilon;
const key = (point: Point) => `${point.x},${point.y}`;
export function parsePath(path: string): Point[] {
  const tokens = path.match(/[MLHV]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?/g) ?? [];
  assert.equal(path.replace(/[MLHV]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?|[\s,]+/g, ''), '', 'unsupported/unparsed path bytes');
  let index = 0, x = 0, y = 0;
  const points: Point[] = [];
  const number = () => { const value = Number(tokens[index++]); assert.ok(Number.isFinite(value), 'nonfinite coordinate'); return value; };
  while (index < tokens.length) {
    const command = tokens[index++];
    assert.ok(['M', 'L', 'H', 'V'].includes(command), 'missing explicit SVG command');
    assert.ok(points.length ? command !== 'M' : command === 'M', 'exactly one starting M');
    if (command === 'M' || command === 'L') { x = number(); y = number(); }
    else if (command === 'H') x = number(); else y = number();
    const previous = points.at(-1);
    if (previous) assert.ok(near(previous.x, x) || near(previous.y, y), 'nonorthogonal path');
    if (!previous || !near(previous.x, x) || !near(previous.y, y)) points.push({ x, y });
  }
  assert.ok(points.length >= 2, 'route must have nonzero length');
  return points;
}
export function compact(points: Point[]): Point[] {
  const result: Point[] = [];
  for (const point of points) {
    while (result.length > 1) {
      const a = result.at(-2)!, b = result.at(-1)!;
      const sameAxis = near(a.x, b.x) && near(b.x, point.x) || near(a.y, b.y) && near(b.y, point.y);
      const sameDirection = (b.x - a.x) * (point.x - b.x) + (b.y - a.y) * (point.y - b.y) >= 0;
      if (!sameAxis || !sameDirection) break;
      result.pop();
    }
    result.push(point);
  }
  return result;
}
function vector(a: Point, b: Point) { return { x: Math.sign(b.x - a.x), y: Math.sign(b.y - a.y) }; }
function segments(points: Point[]) { return points.slice(1).map((end, index) => ({ start: points[index], end })); }
type Segment = ReturnType<typeof segments>[number];
function cross(a: Segment, b: Segment): Point | undefined {
  const av = near(a.start.x, a.end.x), bv = near(b.start.x, b.end.x);
  if (av === bv) return;
  const v = av ? a : b, h = av ? b : a;
  const x = v.start.x, y = h.start.y;
  if (x > Math.min(h.start.x, h.end.x) + epsilon && x < Math.max(h.start.x, h.end.x) - epsilon &&
      y > Math.min(v.start.y, v.end.y) + epsilon && y < Math.max(v.start.y, v.end.y) - epsilon) return { x, y };
}
type Interval = { axis: 'H' | 'V'; coordinate: number; low: number; high: number };
function overlap(a: Segment, b: Segment): Interval | undefined {
  const av = near(a.start.x, a.end.x), bv = near(b.start.x, b.end.x);
  if (av !== bv || !near(av ? a.start.x : a.start.y, bv ? b.start.x : b.start.y)) return;
  const low = Math.max(Math.min(av ? a.start.y : a.start.x, av ? a.end.y : a.end.x), Math.min(av ? b.start.y : b.start.x, av ? b.end.y : b.end.x));
  const high = Math.min(Math.max(av ? a.start.y : a.start.x, av ? a.end.y : a.end.x), Math.max(av ? b.start.y : b.start.x, av ? b.end.y : b.end.x));
  if (high > low + epsilon) return { axis: av ? 'V' : 'H', coordinate: av ? a.start.x : a.start.y, low, high };
}
function overlapLength(intervals: Interval[]) {
  const lanes = new Map<string, Interval[]>();
  for (const interval of intervals) { const id = `${interval.axis}:${interval.coordinate}`; lanes.set(id, [...lanes.get(id) ?? [], interval]); }
  let total = 0;
  for (const lane of lanes.values()) {
    lane.sort((a, b) => a.low - b.low);
    let low = lane[0].low, high = lane[0].high;
    for (const interval of lane.slice(1)) {
      if (interval.low <= high + epsilon) high = Math.max(high, interval.high);
      else { total += high - low; low = interval.low; high = interval.high; }
    }
    total += high - low;
  }
  return total;
}
export function metrics(scene: Scene) {
  const routes = scene.edges.map(edge => {
    const points = compact(parsePath(edge.path)), lines = segments(points);
    const vectors = lines.map(({ start, end }) => vector(start, end));
    const reversals = vectors.slice(1).filter((direction, index) => direction.x * vectors[index].x + direction.y * vectors[index].y < 0).length;
    const length = lines.reduce((sum, line) => sum + Math.abs(line.end.x - line.start.x) + Math.abs(line.end.y - line.start.y), 0);
    return { id: edge.id, points, lines, vectors, reversals, length, bends: vectors.slice(1).filter((direction, index) => direction.x !== vectors[index].x || direction.y !== vectors[index].y).length };
  });
  const pairs: { first: string; second: string; sameTensor: boolean; disjointOwners: boolean; crossings: Point[]; overlaps: Interval[]; overlapLength: number }[] = [];
  for (let i = 0; i < scene.edges.length; i++) for (let j = i + 1; j < scene.edges.length; j++) {
    const a = scene.edges[i], b = scene.edges[j], crossings = new Map<string, Point>(), overlaps: Interval[] = [];
    for (const first of routes[i].lines) for (const second of routes[j].lines) {
      const point = cross(first, second), interval = overlap(first, second);
      if (point) crossings.set(key(point), point);
      if (interval) overlaps.push(interval);
    }
    if (crossings.size || overlaps.length) pairs.push({ first: a.id, second: b.id, sameTensor: a.tensorId === b.tensorId,
      disjointOwners: ![a.sourceId, a.targetId].some(id => [b.sourceId, b.targetId].includes(id)), crossings: [...crossings.values()], overlaps, overlapLength: overlapLength(overlaps) });
  }
  const summary = (selected: typeof pairs) => ({ crossingPairs: selected.filter(pair => pair.crossings.length).length,
    crossingPairPoints: selected.reduce((count, pair) => count + pair.crossings.length, 0), overlapPairs: selected.filter(pair => pair.overlaps.length).length,
    overlapLength: selected.reduce((sum, pair) => sum + pair.overlapLength, 0) });
  return { distinctTensor: summary(pairs.filter(pair => !pair.sameTensor)), disjointOwners: summary(pairs.filter(pair => !pair.sameTensor && pair.disjointOwners)),
    sameTensor: summary(pairs.filter(pair => pair.sameTensor)), totalLength: routes.reduce((sum, route) => sum + route.length, 0),
    totalBends: routes.reduce((sum, route) => sum + route.bends, 0), totalReversals: routes.reduce((sum, route) => sum + route.reversals, 0), pairs, routes };
}
export function intrusions(scene: Scene) {
  const nodes = new Map(scene.nodes.map(node => [node.id, node]));
  const ancestors = (id: string) => { const set = new Set<string>(); let parent = nodes.get(id)?.parentId;
    while (parent) { assert.ok(!set.has(parent), 'scene hierarchy cycle'); set.add(parent); parent = nodes.get(parent)?.parentId; } return set; };
  const result: { edgeId: string; nodeId: string; obstacle: 'body' | 'header' }[] = [];
  for (const edge of scene.edges) {
    const owners = new Set([...ancestors(edge.sourceId), ...ancestors(edge.targetId)]), lines = segments(parsePath(edge.path));
    for (const node of scene.nodes) {
      const header = owners.has(node.id), inset = .25;
      const left = node.x + inset, right = node.x + node.width - inset, top = node.y + inset;
      const bottom = node.y + (header ? node.headerHeight : node.height) - inset;
      const hit = lines.some(({ start, end }) => near(start.x, end.x)
        ? start.x > left && start.x < right && Math.max(Math.min(start.y, end.y), top) < Math.min(Math.max(start.y, end.y), bottom) - epsilon
        : start.y > top && start.y < bottom && Math.max(Math.min(start.x, end.x), left) < Math.min(Math.max(start.x, end.x), right) - epsilon);
      if (hit) result.push({ edgeId: edge.id, nodeId: node.id, obstacle: header ? 'header' : 'body' });
    }
  }
  return result;
}
const edgeSemantics = ({ path, labelX, labelY, ...edge }: SceneEdge) => edge;
const artifact = (value: unknown) => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
export function verifyEndpoints(scene: Scene) {
  for (const edge of scene.edges) {
    const points = parsePath(edge.path);
    for (const [id, direction, point] of [[edge.sourceId, 'out', points[0]], [edge.targetId, 'in', points.at(-1)!]] as const) {
      const node = scene.nodes.find(node => node.id === id); assert.ok(node, 'missing endpoint owner');
      assert.ok(node.ports.some(port => port.direction === direction && port.canonicalEdgeIds.some(id => edge.canonicalEdgeIds.includes(id)) && Math.abs(port.x - point.x) <= .15 && Math.abs(port.y - point.y) <= .15), `unbound ${edge.id} ${direction} endpoint`);
    }
    for (const point of points) assert.ok(point.x >= scene.bounds.x - .01 && point.x <= scene.bounds.x + scene.bounds.width + .01 && point.y >= scene.bounds.y - .01 && point.y <= scene.bounds.y + scene.bounds.height + .01, 'route clipped by scene');
  }
}
export function verifyRefinement(before: Scene, after: Scene) {
  verifyEndpoints(after);
  assert.deepEqual(artifact(after.nodes), artifact(before.nodes), 'routing moved/resized/relabeled an owner or canonical port');
  assert.deepEqual(artifact(after.edges.map(edgeSemantics)), artifact(before.edges.map(edgeSemantics)), 'routing altered edge semantics/style');
  for (const field of ['version', 'documentId', 'revision', 'title', 'pageSpec', 'sourceDigest', 'irDigest', 'sourceFacts', 'hiddenEdges', 'exportScope', 'annotations', 'legend'] as const) assert.deepEqual(artifact(after[field]), artifact(before[field]), `routing altered ${field}`);
  const old = metrics(before), current = metrics(after);
  for (const group of ['distinctTensor', 'disjointOwners'] as const) for (const metric of ['crossingPairs', 'crossingPairPoints', 'overlapPairs'] as const)
    assert.ok(current[group][metric] <= old[group][metric], `${group} ${metric} regressed ${old[group][metric]} -> ${current[group][metric]}`);
  const priorIntrusions = new Set(intrusions(before).map(item => JSON.stringify(item)));
  for (const intrusion of intrusions(after)) assert.ok(priorIntrusions.has(JSON.stringify(intrusion)), `new body/header intrusion: ${JSON.stringify(intrusion)}`);
  for (let index = 0; index < after.edges.length; index++) {
    const a = old.routes[index], b = current.routes[index];
    assert.ok(near(b.points[0].x, a.points[0].x) && near(b.points[0].y, a.points[0].y), 'start anchor moved');
    assert.ok(near(b.points.at(-1)!.x, a.points.at(-1)!.x) && near(b.points.at(-1)!.y, a.points.at(-1)!.y), 'end anchor moved');
    assert.deepEqual(b.vectors[0], a.vectors[0], 'departure direction changed'); assert.deepEqual(b.vectors.at(-1), a.vectors.at(-1), 'arrival direction changed');
    assert.ok(b.reversals <= a.reversals, `new U-turn in ${b.id}`);
  }
  return { before: old, after: current, beforeIntrusions: intrusions(before), afterIntrusions: intrusions(after) };
}
