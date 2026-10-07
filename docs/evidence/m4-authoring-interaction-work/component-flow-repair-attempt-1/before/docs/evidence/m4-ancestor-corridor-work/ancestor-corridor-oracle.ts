/** Independent public-data oracle. No product geometry or scoring helpers. */
import assert from 'node:assert/strict';
import type { Architecture, Scene, SceneEdge, SceneNode, ScenePort } from '../../../studio/src/core/types.ts';

export type Point = { x: number; y: number };
export type Rectangle = Point & { width: number; height: number };
export type Segment = { a: Point; b: Point; edgeId: string; index: number };
export type Interval = { axis: 'x' | 'y'; coordinate: number; low: number; high: number; edgeId: string };
const GEOMETRY_EPS = 1e-7;
// Frozen public paths round to .1; circles/card attributes round to .01.
const ENDPOINT_EPS = .12;
const near = (a: number, b: number) => Math.abs(a - b) <= GEOMETRY_EPS;
const endpointNear = (a: Point, b: Point) => Math.abs(a.x - b.x) <= ENDPOINT_EPS && Math.abs(a.y - b.y) <= ENDPOINT_EPS;
const artifact = <T>(value: T): T => value === undefined ? value : JSON.parse(JSON.stringify(value));
const portKey = (owner: string, port: string) => JSON.stringify([owner, port]);
const pointKey = (point: Point) => JSON.stringify([point.x, point.y]);
const round = (number: number) => Math.round(number * 100) / 100;

export function parseOrthogonalPath(path: string): Point[] {
  const lexeme = /[MLHV]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?/g;
  assert.equal(path.replace(lexeme, '').replace(/[\s,]/g, ''), '', 'unsupported/unparsed path bytes');
  const tokens = path.match(lexeme) ?? [], points: Point[] = [];
  let i = 0, x = 0, y = 0;
  const number = () => {
    assert.ok(i < tokens.length && !/^[MLHV]$/.test(tokens[i]), 'incomplete route coordinate');
    const value = Number(tokens[i++]); assert.ok(Number.isFinite(value), 'nonfinite route coordinate'); return value;
  };
  while (i < tokens.length) {
    const command = tokens[i++];
    assert.ok(['M', 'L', 'H', 'V'].includes(command), 'missing explicit path command');
    assert.ok(points.length ? command !== 'M' : command === 'M', 'exactly one starting M required');
    if (command === 'M' || command === 'L') { x = number(); y = number(); }
    else if (command === 'H') x = number(); else y = number();
    const previous = points.at(-1);
    assert.ok(!previous || near(previous.x, x) || near(previous.y, y), 'diagonal route segment');
    points.push({ x, y });
  }
  assert.ok(points.length >= 2, 'route has too few points');
  assert.ok(points.some(point => !near(point.x, points[0].x) || !near(point.y, points[0].y)), 'zero-length route');
  return points;
}

export function compact(points: Point[]): Point[] {
  const result: Point[] = [];
  for (const point of points) {
    if (result.length && near(result.at(-1)!.x, point.x) && near(result.at(-1)!.y, point.y)) continue;
    while (result.length > 1) {
      const a = result.at(-2)!, b = result.at(-1)!;
      const collinear = near(a.x, b.x) && near(b.x, point.x) || near(a.y, b.y) && near(b.y, point.y);
      const forward = (b.x - a.x) * (point.x - b.x) + (b.y - a.y) * (point.y - b.y) >= 0;
      if (!collinear || !forward) break;
      result.pop();
    }
    result.push({ ...point });
  }
  return result;
}
function routeSegments(points: Point[], edgeId: string): Segment[] {
  return points.slice(1).map((b, index) => ({ a: points[index], b, edgeId, index }));
}
export function segments(scene: Scene): Segment[] {
  return scene.edges.flatMap(edge => routeSegments(compact(parseOrthogonalPath(edge.path)), edge.id));
}
function interior(value: number, low: number, high: number) { return value > low + GEOMETRY_EPS && value < high - GEOMETRY_EPS; }

/** Union is local to an edge pair and geometric lane; never global across pairs. */
export function mergedIntervalLength(intervals: Interval[]) {
  const lanes = new Map<string, Interval[]>();
  for (const interval of intervals) {
    assert.ok(Number.isFinite(interval.coordinate) && Number.isFinite(interval.low) && Number.isFinite(interval.high) && interval.high >= interval.low);
    const key = JSON.stringify([interval.edgeId, interval.axis, interval.coordinate]);
    const lane = lanes.get(key) ?? []; lane.push(interval); lanes.set(key, lane);
  }
  let total = 0;
  for (const lane of lanes.values()) {
    const sorted = [...lane].sort((a, b) => a.low - b.low); let low = sorted[0].low, high = sorted[0].high;
    for (const item of sorted.slice(1)) {
      if (item.low <= high + GEOMETRY_EPS) high = Math.max(high, item.high);
      else { total += high - low; low = item.low; high = item.high; }
    }
    total += high - low;
  }
  return total;
}

export function strictCrossings(scene: Scene) {
  const lines = scene.edges.map(edge => routeSegments(compact(parseOrthogonalPath(edge.path)), edge.id));
  const result: { first: string; second: string; points: Point[]; overlaps: Interval[]; sameTensor: boolean; disjointOwners: boolean; overlapLength: number }[] = [];
  for (let i = 0; i < scene.edges.length; i++) for (let j = i + 1; j < scene.edges.length; j++) {
    const first = scene.edges[i], second = scene.edges[j], points = new Map<string, Point>(), overlaps: Interval[] = [];
    const pair = JSON.stringify([first.id, second.id]);
    for (const { a: p, b: q } of lines[i]) for (const { a: r, b: s } of lines[j]) {
      const av = near(p.x, q.x), bv = near(r.x, s.x);
      if (av !== bv) {
        const v = av ? [p, q] : [r, s], h = av ? [r, s] : [p, q];
        if (interior(v[0].x, Math.min(h[0].x, h[1].x), Math.max(h[0].x, h[1].x)) && interior(h[0].y, Math.min(v[0].y, v[1].y), Math.max(v[0].y, v[1].y))) {
          const point = { x: v[0].x, y: h[0].y }; points.set(pointKey(point), point);
        }
      } else if (av && near(p.x, r.x) || !av && near(p.y, r.y)) {
        const low = Math.max(Math.min(av ? p.y : p.x, av ? q.y : q.x), Math.min(av ? r.y : r.x, av ? s.y : s.x));
        const high = Math.min(Math.max(av ? p.y : p.x, av ? q.y : q.x), Math.max(av ? r.y : r.x, av ? s.y : s.x));
        if (high - low > GEOMETRY_EPS) overlaps.push({ axis: av ? 'y' : 'x', coordinate: av ? p.x : p.y, low, high, edgeId: pair });
      }
    }
    if (points.size || overlaps.length) result.push({ first: first.id, second: second.id, points: [...points.values()], overlaps,
      sameTensor: first.tensorId === second.tensorId, disjointOwners: ![first.sourceId, first.targetId].some(id => [second.sourceId, second.targetId].includes(id)), overlapLength: mergedIntervalLength(overlaps) });
  }
  return result;
}

export function metrics(scene: Scene) {
  const pairs = strictCrossings(scene);
  const summary = (selected: typeof pairs) => ({ crossingPairs: selected.filter(pair => pair.points.length).length,
    crossingPoints: selected.reduce((n, p) => n + p.points.length, 0), overlapPairs: selected.filter(pair => pair.overlapLength > GEOMETRY_EPS).length,
    overlapLength: selected.reduce((n, p) => n + p.overlapLength, 0) });
  const routes = scene.edges.map(edge => {
    const points = compact(parseOrthogonalPath(edge.path)), lines = routeSegments(points, edge.id);
    const directions = lines.map(line => ({ x: Math.sign(line.b.x - line.a.x), y: Math.sign(line.b.y - line.a.y) }));
    return { id: edge.id, points, directions, length: lines.reduce((n, line) => n + Math.abs(line.b.x - line.a.x) + Math.abs(line.b.y - line.a.y), 0),
      bends: directions.slice(1).filter((d, i) => d.x !== directions[i].x || d.y !== directions[i].y).length,
      reversals: directions.slice(1).filter((d, i) => d.x * directions[i].x + d.y * directions[i].y < 0).length };
  });
  return { distinct: summary(pairs.filter(pair => !pair.sameTensor)), same: summary(pairs.filter(pair => pair.sameTensor)),
    disjoint: summary(pairs.filter(pair => !pair.sameTensor && pair.disjointOwners)), all: summary(pairs),
    routeLength: routes.reduce((n, r) => n + r.length, 0), bends: routes.reduce((n, r) => n + r.bends, 0), reversals: routes.reduce((n, r) => n + r.reversals, 0), pairs, routes };
}

const decode = (value: string) => value.replace(/&(?:quot|apos|lt|gt|amp);/g, entity =>
  ({ '&quot;': '"', '&apos;': "'", '&lt;': '<', '&gt;': '>', '&amp;': '&' })[entity]!);
export type SvgGeometry = { cards: Map<string, Rectangle[]>; circles: Map<string, Point>; paths: Map<string, Point[]>;
  styles: Map<string, { stroke: string; width: number; dashed: boolean; tensorId: string }>; metadata: Record<string, unknown>; bounds: Rectangle };
export function parseSvg(svg: string): SvgGeometry {
  const cards = new Map<string, Rectangle[]>(), circles = new Map<string, Point>(), paths = new Map<string, Point[]>();
  const styles = new Map<string, { stroke: string; width: number; dashed: boolean; tensorId: string }>();
  const stack: { tag: string; attrs: Record<string, string> }[] = [];
  for (const match of svg.matchAll(/<\/?[a-z][^>]*>/gi)) {
    const token = match[0], tag = /^<\/?([a-z][\w:-]*)/i.exec(token)![1];
    if (token.startsWith('</')) { assert.equal(stack.pop()?.tag, tag, 'unbalanced SVG'); continue; }
    const attrs = Object.fromEntries([...token.matchAll(/([\w:-]+)="([^"]*)"/g)].map(([, name, value]) => [name, decode(value)]));
    const parent = stack.at(-1)?.attrs;
    if (tag === 'rect' && parent?.['data-node-id'] && !parent['data-port-id']) {
      const card = { x: Number(attrs.x), y: Number(attrs.y), width: Number(attrs.width), height: Number(attrs.height) };
      assert.ok(Object.values(card).every(Number.isFinite)); const owner = parent['data-node-id'];
      const owned = cards.get(owner) ?? []; owned.push(card); cards.set(owner, owned);
    }
    if (tag === 'circle' && Number(attrs.r) === 2.6) {
      const owner = attrs['data-port-id'] ? attrs : parent;
      assert.ok(owner?.['data-node-id'] && owner['data-port-id'], 'port circle missing identity');
      const key = portKey(owner['data-node-id'], owner['data-port-id']); assert.ok(!circles.has(key), 'duplicate public port circle');
      const point = { x: Number(attrs.cx), y: Number(attrs.cy) }; assert.ok(Object.values(point).every(Number.isFinite)); circles.set(key, point);
    }
    if (tag === 'path' && parent?.['data-edge-id']) {
      const id = parent['data-edge-id']; assert.ok(!paths.has(id), 'duplicate public edge route');
      paths.set(id, parseOrthogonalPath(attrs.d)); styles.set(id, { stroke: attrs.stroke, width: Number(attrs['stroke-width']), dashed: attrs['stroke-dasharray'] !== undefined, tensorId: parent['data-tensor-id'] });
    }
    if (!token.endsWith('/>')) stack.push({ tag, attrs });
  }
  assert.equal(stack.length, 0, 'unclosed SVG');
  const raw = /<metadata>(.*?)<\/metadata>/s.exec(svg); assert.ok(raw, 'SVG metadata missing');
  const metadata = JSON.parse(decode(raw[1])) as Record<string, unknown>;
  const viewBox = /viewBox="([^"]+)"/.exec(svg); assert.ok(viewBox);
  const values = viewBox[1].split(/\s+/).map(Number); assert.equal(values.length, 4); assert.ok(values.every(Number.isFinite));
  const [x, y, width, height] = values; return { cards, circles, paths, styles, metadata, bounds: { x, y, width, height } };
}

export function assertEndpointBindings(scene: Scene) {
  const owners = new Map(scene.nodes.map(node => [node.id, node]));
  assert.equal(owners.size, scene.nodes.length, 'duplicate node identity');
  assert.equal(new Set(scene.edges.map(edge => edge.id)).size, scene.edges.length, 'duplicate edge identity');
  for (const edge of scene.edges) {
    assert.ok(edge.canonicalEdgeIds.length > 0 && new Set(edge.canonicalEdgeIds).size === edge.canonicalEdgeIds.length, 'missing/duplicate branch membership');
    const points = parseOrthogonalPath(edge.path);
    for (const [ownerId, direction, point] of [[edge.sourceId, 'out', points[0]], [edge.targetId, 'in', points.at(-1)!]] as const) {
      const owner = owners.get(ownerId); assert.ok(owner, `missing route owner ${ownerId}`);
      const candidates = owner.ports.filter(port => port.direction === direction && edge.canonicalEdgeIds.every(id => port.canonicalEdgeIds.includes(id)) && endpointNear(port, point));
      assert.equal(candidates.length, 1, `${edge.id} ${direction} endpoint lacks one fully covered typed public port`);
    }
  }
}

export function assertCanonicalCoverage(scene: Scene, architecture: Architecture) {
  const canonical = new Map(architecture.edges.map(edge => [edge.id, edge]));
  const compareBindings = (bindings: { nodeId: string; portId: string }[]) => bindings.map(binding => JSON.stringify(binding)).sort();
  for (const node of scene.nodes) for (const port of node.ports) {
    assert.ok(port.canonicalEdgeIds.length && new Set(port.canonicalEdgeIds).size === port.canonicalEdgeIds.length, 'incomplete/duplicate port coverage');
    const expected = port.canonicalEdgeIds.map(id => {
      const edge = canonical.get(id); assert.ok(edge, `unknown canonical port member ${id}`); return port.direction === 'out' ? edge.source : edge.target;
    });
    assert.deepEqual(compareBindings(port.canonicalBindings), compareBindings(expected), `${node.id}/${port.id} canonical binding coverage differs`);
  }
  for (const edge of scene.edges) for (const id of edge.canonicalEdgeIds) {
    const member = canonical.get(id); assert.ok(member, `unknown canonical edge ${id}`);
    assert.equal(member.tensorId, edge.tensorId, 'canonical tensor identity differs'); assert.equal(member.role, edge.role, 'canonical role differs');
  }
}

export function assertSvgAgreement(scene: Scene, svg: string): SvgGeometry {
  const geometry = parseSvg(svg); assertEndpointBindings(scene);
  assert.equal(geometry.cards.size, scene.nodes.length, 'public node/card membership differs');
  assert.equal(geometry.circles.size, scene.nodes.reduce((n, node) => n + node.ports.length, 0), 'public port membership differs');
  assert.equal(geometry.paths.size, scene.edges.length, 'public branch path membership differs');
  const contains = (point: Point) => point.x >= geometry.bounds.x - ENDPOINT_EPS && point.y >= geometry.bounds.y - ENDPOINT_EPS && point.x <= geometry.bounds.x + geometry.bounds.width + ENDPOINT_EPS && point.y <= geometry.bounds.y + geometry.bounds.height + ENDPOINT_EPS;
  for (const node of scene.nodes) {
    const cards = geometry.cards.get(node.id); assert.ok(cards, 'public cards missing');
    const offsets = node.repeat && !node.expanded ? [7, 3.5, 0] : [0];
    assert.deepEqual(cards, offsets.map(offset => ({ x: round(node.x + offset), y: round(node.y + offset), width: round(node.width), height: round(node.height) })), 'public card geometry differs');
    for (const card of cards) assert.ok(contains(card) && contains({ x: card.x + card.width, y: card.y + card.height }), 'clipped public card');
    for (const port of node.ports) {
      const point = geometry.circles.get(portKey(node.id, port.id)); assert.ok(point, 'public circle missing');
      assert.deepEqual(point, { x: round(port.x), y: round(port.y) }, 'public port circle moved');
    }
  }
  for (const edge of scene.edges) {
    const points = geometry.paths.get(edge.id); assert.ok(points, 'public route missing');
    assert.deepEqual(points, parseOrthogonalPath(edge.path), 'public route differs'); assert.ok(points.every(contains), 'clipped public route');
    assert.deepEqual(geometry.styles.get(edge.id), { stroke: edge.stroke, width: round(edge.width), dashed: edge.dashed, tensorId: edge.tensorId }, 'public route appearance differs');
    for (const [ownerId, direction, point] of [[edge.sourceId, 'out', points[0]], [edge.targetId, 'in', points.at(-1)!]] as const) {
      const port = scene.nodes.find(node => node.id === ownerId)!.ports.find(port => port.direction === direction && edge.canonicalEdgeIds.every(id => port.canonicalEdgeIds.includes(id)) && endpointNear(port, point))!;
      assert.ok(endpointNear(geometry.circles.get(portKey(ownerId, port.id))!, point), 'public path endpoint/circle disagreement');
    }
  }
  const metadata = geometry.metadata;
  for (const field of ['documentId', 'revision', 'sourceDigest', 'irDigest', 'sourceFacts'] as const) assert.deepEqual(metadata[field], artifact(scene[field]), `public metadata ${field} differs`);
  assert.deepEqual(metadata.renderedBindings, scene.edges.map(edge => ({ sceneEdgeId: edge.id, canonicalEdgeIds: edge.canonicalEdgeIds, source: edge.source, target: edge.target, tensorId: edge.tensorId, role: edge.role })), 'public canonical branch metadata differs');
  assert.deepEqual(metadata.renderedNodes, scene.nodes.map(node => ({ sceneNodeId: node.id, canonicalNodeId: node.canonicalNodeId ?? node.id, boundary: node.boundary ?? false })), 'public canonical node metadata differs');
  assert.deepEqual(metadata.exportScope, artifact(scene.exportScope), 'public export scope differs'); return geometry;
}

function ancestors(scene: Scene, id: string) {
  const byId = new Map(scene.nodes.map(node => [node.id, node])), result = new Set<string>(); let parent = byId.get(id)?.parentId;
  while (parent) { assert.ok(!result.has(parent), 'scene hierarchy cycle'); result.add(parent); parent = byId.get(parent)?.parentId; } return result;
}
export function penetrates(a: Point, b: Point, box: Rectangle) {
  const left = box.x + .01, right = box.x + box.width - .01, top = box.y + .01, bottom = box.y + box.height - .01;
  return near(a.x, b.x) ? a.x > left && a.x < right && Math.max(Math.min(a.y, b.y), top) < Math.min(Math.max(a.y, b.y), bottom) - GEOMETRY_EPS
    : a.y > top && a.y < bottom && Math.max(Math.min(a.x, b.x), left) < Math.min(Math.max(a.x, b.x), right) - GEOMETRY_EPS;
}
export function bodyAndHeaderHits(scene: Scene, svg: string) {
  const geometry = parseSvg(svg), hits: { edgeId: string; nodeId: string; cardIndex: number; obstacle: 'body' | 'header' }[] = [];
  for (const edge of scene.edges) {
    const ancestorIds = new Set([...ancestors(scene, edge.sourceId), ...ancestors(scene, edge.targetId)]), points = geometry.paths.get(edge.id)!;
    for (const node of scene.nodes) {
      const header = ancestorIds.has(node.id) && node.id !== edge.sourceId && node.id !== edge.targetId;
      const boxes = header ? [{ x: node.x, y: node.y, width: node.width, height: node.headerHeight }] : geometry.cards.get(node.id)!;
      boxes.forEach((box, cardIndex) => {
        if (points.slice(1).some((b, i) => penetrates(points[i], b, box))) hits.push({ edgeId: edge.id, nodeId: node.id, cardIndex, obstacle: header ? 'header' : 'body' });
      });
    }
  }
  return hits;
}
export function assertBodyAndHeaderClear(scene: Scene, svg: string) { assert.deepEqual(bodyAndHeaderHits(scene, svg), [], 'public body/backplate/header intrusion'); }
const edgeSemantics = ({ path: _path, labelX: _x, labelY: _y, ...edge }: SceneEdge) => edge;

export function assertProtectedMetrics(old: ReturnType<typeof metrics>, current: ReturnType<typeof metrics>) {
  for (const group of ['distinct', 'disjoint'] as const) for (const metric of ['crossingPairs', 'crossingPoints', 'overlapPairs'] as const)
    assert.ok(current[group][metric] <= old[group][metric], `${group} ${metric} regressed ${old[group][metric]} -> ${current[group][metric]}`);
  for (const metric of ['crossingPairs', 'crossingPoints'] as const) assert.ok(current.same[metric] <= old.same[metric], `same-tensor ${metric} regressed ${old.same[metric]} -> ${current.same[metric]}`);
  for (const pair of current.pairs.filter(pair => pair.sameTensor && pair.points.length)) {
    const previous = old.pairs.find(item => item.first === pair.first && item.second === pair.second);
    assert.ok(pair.points.length <= (previous?.points.length ?? 0), `new same-tensor crossing for pair ${pair.first}/${pair.second}`);
  }
}

/** For a routing-only change, endpoints and all public object facts are frozen. */
export function verifyRefinement(before: Scene, after: Scene, svg: string, beforeSvg: string) {
  const priorGeometry = assertSvgAgreement(before, beforeSvg), geometry = assertSvgAgreement(after, svg);
  assert.deepEqual(artifact(after.nodes), artifact(before.nodes), 'routing moved/resized/relabeled an owner or canonical port');
  assert.deepEqual(artifact(after.edges.map(edgeSemantics)), artifact(before.edges.map(edgeSemantics)), 'routing altered branch semantics/style');
  for (const field of ['version', 'documentId', 'revision', 'title', 'pageSpec', 'sourceDigest', 'irDigest', 'sourceFacts', 'hiddenEdges', 'exportScope', 'annotations', 'legend'] as const)
    assert.deepEqual(artifact(after[field]), artifact(before[field]), `routing altered ${field}`);
  assert.deepEqual([...geometry.cards], [...priorGeometry.cards], 'public immutable card geometry changed');
  assert.deepEqual([...geometry.circles], [...priorGeometry.circles], 'public immutable circle geometry changed');
  const old = metrics(before), current = metrics(after);
  assertProtectedMetrics(old, current);
  const priorHits = new Set(bodyAndHeaderHits(before, beforeSvg).map(hit => JSON.stringify(hit)));
  for (const hit of bodyAndHeaderHits(after, svg)) {
    assert.ok(priorHits.has(JSON.stringify(hit)), `new public body/backplate/header intrusion ${JSON.stringify(hit)}`);
    assert.ok(after.diagnostics.some(diagnostic => diagnostic.code === 'layout-route-blocked' && diagnostic.edgeId === hit.edgeId && diagnostic.objectIds?.includes(hit.nodeId)), 'retained intrusion must remain explicitly blocked');
  }
  old.routes.forEach((route, i) => {
    const result = current.routes[i];
    assert.deepEqual(result.points[0], route.points[0], 'routing moved departure anchor'); assert.deepEqual(result.points.at(-1), route.points.at(-1), 'routing moved arrival anchor');
    assert.deepEqual(result.directions[0], route.directions[0], 'routing changed departure direction'); assert.deepEqual(result.directions.at(-1), route.directions.at(-1), 'routing changed arrival direction');
    assert.ok(result.reversals <= route.reversals, 'routing introduced U-turn');
  });
  return { before: old, after: current, beforeHits: [...priorHits], afterHits: bodyAndHeaderHits(after, svg) };
}

export type FamilyMeta = { sourceId: string; source: { nodeId: string; portId: string }; tensorId: string; role: string;
  stroke: string; width: number; dashed: boolean; displaySide: string; start: Point; canonicalBindings: { nodeId: string; portId: string }[];
  canonicalEdgeIds: string[]; portCanonicalEdgeIds: string[]; expectedBindings: { nodeId: string; portId: string }[]; proxy: boolean; resolved: boolean };
function resolvedMemory(member: FamilyMeta) {
  const bindingKey = (value: { nodeId: string; portId: string }) => JSON.stringify(value);
  return member.resolved && member.role === 'memory' && !!member.tensorId && !!member.stroke && Number.isFinite(member.width) && member.width > 0 &&
    member.canonicalEdgeIds.length > 0 && member.canonicalEdgeIds.every(id => member.portCanonicalEdgeIds.includes(id)) &&
    member.canonicalBindings.length > 0 && member.canonicalBindings.every(binding => bindingKey(binding) === bindingKey(member.source)) &&
    JSON.stringify(member.canonicalBindings.map(bindingKey).sort()) === JSON.stringify(member.expectedBindings.map(bindingKey).sort());
}
export function familyEligible(a: FamilyMeta, b: FamilyMeta) {
  return resolvedMemory(a) && resolvedMemory(b) && a.sourceId === b.sourceId && a.source.nodeId === b.source.nodeId && a.source.portId === b.source.portId &&
    a.tensorId === b.tensorId && a.role === b.role && a.stroke === b.stroke && a.width === b.width && a.dashed === b.dashed && a.displaySide === b.displaySide && near(a.start.x, b.start.x) && near(a.start.y, b.start.y);
}
function literalSide(node: SceneNode, port: ScenePort) {
  const offsets = node.repeat && !node.expanded ? [0, 3.5, 7] : [0];
  const bodies = offsets.map(offset => ({ x: node.x + offset, y: node.y + offset, width: node.width, height: node.height }));
  const sides = ['bottom', 'top', 'right', 'left'].filter(side => bodies.some(body => side === 'bottom' || side === 'top'
    ? Math.abs(port.y - (body.y + (side === 'bottom' ? body.height : 0))) <= ENDPOINT_EPS && port.x >= body.x && port.x <= body.x + body.width
    : Math.abs(port.x - (body.x + (side === 'right' ? body.width : 0))) <= ENDPOINT_EPS && port.y >= body.y && port.y <= body.y + body.height));
  assert.equal(sides.length, 1, 'source public circle does not identify one literal side'); return sides[0];
}
export function edgeFamilyMeta(scene: Scene, edge: SceneEdge, architecture: Architecture): FamilyMeta {
  const node = scene.nodes.find(node => node.id === edge.sourceId)!; assert.ok(node);
  const start = parseOrthogonalPath(edge.path)[0];
  const candidates = node.ports.filter(port => port.direction === 'out' && edge.canonicalEdgeIds.every(id => port.canonicalEdgeIds.includes(id)) && endpointNear(port, start));
  assert.equal(candidates.length, 1, 'unresolved display source port'); const port = candidates[0];
  const canonical = new Map(architecture.edges.map(edge => [edge.id, edge]));
  const expectedBindings = port.canonicalEdgeIds.map(id => canonical.get(id)?.source).filter((binding): binding is { nodeId: string; portId: string } => !!binding);
  const resolved = expectedBindings.length === port.canonicalEdgeIds.length && edge.canonicalEdgeIds.every(id => {
    const canonicalEdge = canonical.get(id); return canonicalEdge && canonicalEdge.source.nodeId === edge.source.nodeId && canonicalEdge.source.portId === edge.source.portId && canonicalEdge.role === edge.role && canonicalEdge.tensorId === edge.tensorId;
  });
  return { sourceId: edge.sourceId, source: edge.source, tensorId: edge.tensorId, role: edge.role, stroke: edge.stroke, width: edge.width, dashed: edge.dashed,
    displaySide: literalSide(node, port), start: { x: port.x, y: port.y }, canonicalBindings: port.canonicalBindings, canonicalEdgeIds: edge.canonicalEdgeIds,
    portCanonicalEdgeIds: port.canonicalEdgeIds, expectedBindings, proxy: port.proxy, resolved };
}
