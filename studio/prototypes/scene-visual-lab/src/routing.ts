import type {
  Bounds,
  LabEdge,
  LabNode,
  LabScene,
  Point,
  PortSide,
  RoutedEdge,
  RouteStyle,
  SceneBoundaryPortMap,
  SceneMetrics,
} from "./types";

const EPSILON = 0.001;
const NODE_CLEARANCE = 14;
const PORT_STUB = 24;
const BEND_COST = 18;
const PORT_SIDES: readonly PortSide[] = ["left", "right", "top", "bottom"];

interface AnchorPair {
  start: Point;
  end: Point;
  sourceSide: PortSide;
  targetSide: PortSide;
}

interface SidePair {
  sourceSide: PortSide;
  targetSide: PortSide;
}

interface Segment {
  start: Point;
  end: Point;
}

interface AdaptiveEdge {
  edge: LabEdge;
  source: LabNode;
  target: LabNode;
  sourceSide: PortSide;
  targetSide: PortSide;
  sourcePort?: Point;
  targetPort?: Point;
  sourceIsInterior: boolean;
  targetIsInterior: boolean;
}

interface PortReference {
  record: AdaptiveEdge;
  role: "source" | "target";
  opposite: Point;
}

interface GraphLink {
  target: number;
  length: number;
  direction: "horizontal" | "vertical";
  segment: Segment;
}

function center(bounds: Bounds): Point {
  return { x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height / 2 };
}

function sideVector(side: PortSide): Point {
  if (side === "left") return { x: -1, y: 0 };
  if (side === "right") return { x: 1, y: 0 };
  if (side === "top") return { x: 0, y: -1 };
  return { x: 0, y: 1 };
}

function oppositeSide(side: PortSide): PortSide {
  if (side === "left") return "right";
  if (side === "right") return "left";
  if (side === "top") return "bottom";
  return "top";
}

function preferredSidePair(source: LabNode, target: LabNode): SidePair {
  const sourceCenter = center(source.bounds);
  const targetCenter = center(target.bounds);
  const dx = targetCenter.x - sourceCenter.x;
  const dy = targetCenter.y - sourceCenter.y;
  const horizontalWeight = Math.abs(dx) / Math.max(1, (source.bounds.width + target.bounds.width) / 2);
  const verticalWeight = Math.abs(dy) / Math.max(1, (source.bounds.height + target.bounds.height) / 2);
  if (horizontalWeight >= verticalWeight) {
    const sourceSide: PortSide = dx >= 0 ? "right" : "left";
    return { sourceSide, targetSide: oppositeSide(sourceSide) };
  }
  const sourceSide: PortSide = dy >= 0 ? "bottom" : "top";
  return { sourceSide, targetSide: oppositeSide(sourceSide) };
}

function selectSidePair(source: LabNode, target: LabNode, nodes: readonly LabNode[]): SidePair {
  const sourceCenter = center(source.bounds);
  const targetCenter = center(target.bounds);
  const delta = { x: targetCenter.x - sourceCenter.x, y: targetCenter.y - sourceCenter.y };
  const length = Math.max(EPSILON, Math.hypot(delta.x, delta.y));
  const direction = { x: delta.x / length, y: delta.y / length };
  const obstacles = nodes.map((node) => ({ node, bounds: inflate(node.bounds, NODE_CLEARANCE) }));
  let best = preferredSidePair(source, target);
  let bestScore = Number.POSITIVE_INFINITY;
  for (const sourceSide of PORT_SIDES) {
    for (const targetSide of PORT_SIDES) {
      const sourcePort = midpointPort(source, sourceSide);
      const targetPort = midpointPort(target, targetSide);
      const sourceVector = sideVector(sourceSide);
      const targetVector = sideVector(targetSide);
      const sourceOutside = {
        x: sourcePort.x + sourceVector.x * PORT_STUB,
        y: sourcePort.y + sourceVector.y * PORT_STUB,
      };
      const targetOutside = {
        x: targetPort.x + targetVector.x * PORT_STUB,
        y: targetPort.y + targetVector.y * PORT_STUB,
      };
      const sourceAlignment = sourceVector.x * direction.x + sourceVector.y * direction.y;
      const targetAlignment = targetVector.x * -direction.x + targetVector.y * -direction.y;
      const sourceBlocked = obstacles.some(({ node, bounds }) => (
        node.scene_node_id !== source.scene_node_id
        && (pointInsideBounds(sourceOutside, bounds) || segmentBlocked({ start: sourcePort, end: sourceOutside }, [bounds]))
      ));
      const targetBlocked = obstacles.some(({ node, bounds }) => (
        node.scene_node_id !== target.scene_node_id
        && (pointInsideBounds(targetOutside, bounds) || segmentBlocked({ start: targetPort, end: targetOutside }, [bounds]))
      ));
      const score = Math.abs(sourceOutside.x - targetOutside.x)
        + Math.abs(sourceOutside.y - targetOutside.y)
        + (1 - sourceAlignment) * 105
        + (1 - targetAlignment) * 105
        + (sourceAlignment < -0.01 ? 500 : 0)
        + (targetAlignment < -0.01 ? 500 : 0)
        + (sourceBlocked ? 10000 : 0)
        + (targetBlocked ? 10000 : 0);
      if (score < bestScore) {
        bestScore = score;
        best = { sourceSide, targetSide };
      }
    }
  }
  return best;
}

function midpointPort(node: LabNode, side: PortSide): Point {
  const { x, y, width, height } = node.bounds;
  if (side === "left") return { x, y: y + height / 2 };
  if (side === "right") return { x: x + width, y: y + height / 2 };
  if (side === "top") return { x: x + width / 2, y };
  return { x: x + width / 2, y: y + height };
}

function anchors(
  source: LabNode,
  target: LabNode,
  boundaryPorts?: SceneBoundaryPortMap,
): AnchorPair {
  const { sourceSide, targetSide } = preferredSidePair(source, target);
  const sourcePortal = boundaryPorts?.[source.scene_node_id];
  const targetPortal = boundaryPorts?.[target.scene_node_id];
  return {
    start: sourcePortal?.exit ?? midpointPort(source, sourceSide),
    end: targetPortal?.entry ?? midpointPort(target, targetSide),
    sourceSide: sourcePortal?.exitSide ?? (sourcePortal ? "right" : sourceSide),
    targetSide: targetPortal?.entrySide ?? (targetPortal ? "left" : targetSide),
  };
}

function compact(points: Point[]): Point[] {
  const output: Point[] = [];
  for (const point of points) {
    const previous = output.at(-1);
    if (previous && Math.abs(previous.x - point.x) < EPSILON && Math.abs(previous.y - point.y) < EPSILON) continue;
    output.push(point);
    while (output.length >= 3) {
      const [first, middle, last] = output.slice(-3);
      if (
        Math.abs(first.x - middle.x) < EPSILON && Math.abs(middle.x - last.x) < EPSILON
        || Math.abs(first.y - middle.y) < EPSILON && Math.abs(middle.y - last.y) < EPSILON
      ) output.splice(-2, 1);
      else break;
    }
  }
  return output;
}

function routePoints(start: Point, end: Point, style: RouteStyle, lane: number): Point[] {
  if (style === "direct") return [start, end];
  const horizontal = Math.abs(end.x - start.x) >= Math.abs(end.y - start.y);
  if (style === "orthogonal") {
    if (horizontal) {
      const middleX = (start.x + end.x) / 2 + lane * 10;
      return compact([start, { x: middleX, y: start.y }, { x: middleX, y: end.y }, end]);
    }
    const middleY = (start.y + end.y) / 2 + lane * 10;
    return compact([start, { x: start.x, y: middleY }, { x: end.x, y: middleY }, end]);
  }
  const stub = 24;
  if (horizontal) {
    const direction = end.x >= start.x ? 1 : -1;
    const channelY = (start.y + end.y) / 2 + lane * 22;
    return compact([
      start,
      { x: start.x + direction * stub, y: start.y },
      { x: start.x + direction * stub, y: channelY },
      { x: end.x - direction * stub, y: channelY },
      { x: end.x - direction * stub, y: end.y },
      end,
    ]);
  }
  const direction = end.y >= start.y ? 1 : -1;
  const channelX = (start.x + end.x) / 2 + lane * 22;
  return compact([
    start,
    { x: start.x, y: start.y + direction * stub },
    { x: channelX, y: start.y + direction * stub },
    { x: channelX, y: end.y - direction * stub },
    { x: end.x, y: end.y - direction * stub },
    end,
  ]);
}

function curveGeometry(start: Point, end: Point, lane: number): { path: string; points: Point[] } {
  const horizontal = Math.abs(end.x - start.x) >= Math.abs(end.y - start.y);
  const [controlA, controlB] = horizontal ? (() => {
    const middleX = (start.x + end.x) / 2;
    const offset = lane * 24;
    return [
      { x: middleX, y: start.y + offset },
      { x: middleX, y: end.y + offset },
    ];
  })() : (() => {
    const middleY = (start.y + end.y) / 2;
    const offset = lane * 24;
    return [
      { x: start.x + offset, y: middleY },
      { x: end.x + offset, y: middleY },
    ];
  })();
  const pointAt = (ratio: number): Point => {
    const inverse = 1 - ratio;
    return {
      x: inverse ** 3 * start.x
        + 3 * inverse ** 2 * ratio * controlA.x
        + 3 * inverse * ratio ** 2 * controlB.x
        + ratio ** 3 * end.x,
      y: inverse ** 3 * start.y
        + 3 * inverse ** 2 * ratio * controlA.y
        + 3 * inverse * ratio ** 2 * controlB.y
        + ratio ** 3 * end.y,
    };
  };
  return {
    path: `M ${start.x} ${start.y} C ${controlA.x} ${controlA.y}, ${controlB.x} ${controlB.y}, ${end.x} ${end.y}`,
    points: Array.from({ length: 9 }, (_, index) => pointAt(index / 8)),
  };
}

function polylinePath(points: Point[]): string {
  return points.map((point, index) => `${index ? "L" : "M"} ${point.x} ${point.y}`).join(" ");
}

function roundedPolylinePath(points: Point[], requestedRadius = 8): string {
  if (points.length < 3) return polylinePath(points);
  const commands = [`M ${points[0].x} ${points[0].y}`];
  for (let index = 1; index < points.length - 1; index += 1) {
    const previous = points[index - 1];
    const corner = points[index];
    const next = points[index + 1];
    const incoming = Math.hypot(corner.x - previous.x, corner.y - previous.y);
    const outgoing = Math.hypot(next.x - corner.x, next.y - corner.y);
    const radius = Math.min(requestedRadius, incoming / 2, outgoing / 2);
    const before = {
      x: corner.x + (previous.x - corner.x) * radius / Math.max(incoming, EPSILON),
      y: corner.y + (previous.y - corner.y) * radius / Math.max(incoming, EPSILON),
    };
    const after = {
      x: corner.x + (next.x - corner.x) * radius / Math.max(outgoing, EPSILON),
      y: corner.y + (next.y - corner.y) * radius / Math.max(outgoing, EPSILON),
    };
    commands.push(`L ${before.x} ${before.y}`, `Q ${corner.x} ${corner.y} ${after.x} ${after.y}`);
  }
  const end = points.at(-1)!;
  commands.push(`L ${end.x} ${end.y}`);
  return commands.join(" ");
}

function labelGeometry(points: Point[], allowRotation: boolean): { point: Point; angle: number } {
  let longest = { start: points[0], end: points[1], length: 0 };
  for (let index = 0; index < points.length - 1; index += 1) {
    const start = points[index];
    const end = points[index + 1];
    const length = Math.hypot(end.x - start.x, end.y - start.y);
    if (length > longest.length) longest = { start, end, length };
  }
  const vertical = Math.abs(longest.end.y - longest.start.y) > Math.abs(longest.end.x - longest.start.x) * 1.2;
  return {
    point: {
      x: (longest.start.x + longest.end.x) / 2,
      y: (longest.start.y + longest.end.y) / 2,
    },
    angle: allowRotation && vertical ? -90 : 0,
  };
}

function edgeLane(edge: LabEdge, index: number, edges: readonly LabEdge[]): number {
  const siblings = edges.filter((candidate) => (
    candidate.source_scene_node_id === edge.source_scene_node_id
    || candidate.target_scene_node_id === edge.target_scene_node_id
  ));
  const siblingIndex = siblings.findIndex((candidate) => candidate.scene_edge_id === edge.scene_edge_id);
  const centered = siblingIndex - (siblings.length - 1) / 2;
  return Math.max(-3, Math.min(3, centered || (index % 3) - 1));
}

function portPoint(node: LabNode, side: PortSide, index: number, count: number): Point {
  const { x, y, width, height } = node.bounds;
  const edgeLength = side === "left" || side === "right" ? height : width;
  const margin = Math.min(16, edgeLength * 0.2);
  const usable = Math.max(0, edgeLength - margin * 2);
  const offset = margin + usable * (index + 1) / (count + 1);
  if (side === "left") return { x, y: y + offset };
  if (side === "right") return { x: x + width, y: y + offset };
  if (side === "top") return { x: x + offset, y };
  return { x: x + offset, y: y + height };
}

function assignAdaptivePorts(records: AdaptiveEdge[]): void {
  const groups = new Map<string, PortReference[]>();
  const add = (node: LabNode, side: PortSide, reference: PortReference) => {
    const key = `${node.scene_node_id}:${side}`;
    groups.set(key, [...(groups.get(key) ?? []), reference]);
  };
  for (const record of records) {
    if (!record.sourcePort) add(record.source, record.sourceSide, { record, role: "source", opposite: center(record.target.bounds) });
    if (!record.targetPort) add(record.target, record.targetSide, { record, role: "target", opposite: center(record.source.bounds) });
  }
  for (const references of groups.values()) {
    const sample = references[0];
    const node = sample.role === "source" ? sample.record.source : sample.record.target;
    const side = sample.role === "source" ? sample.record.sourceSide : sample.record.targetSide;
    references.sort((first, second) => {
      const firstAxis = side === "left" || side === "right" ? first.opposite.y : first.opposite.x;
      const secondAxis = side === "left" || side === "right" ? second.opposite.y : second.opposite.x;
      return firstAxis - secondAxis || first.record.edge.scene_edge_id.localeCompare(second.record.edge.scene_edge_id);
    });
    references.forEach((reference, index) => {
      const point = node.detail_expanded && (side === "left" || side === "right")
        ? midpointPort(node, side)
        : portPoint(node, side, index, references.length);
      if (reference.role === "source") reference.record.sourcePort = point;
      else reference.record.targetPort = point;
    });
  }
}

function inflate(bounds: Bounds, amount: number): Bounds {
  return {
    x: bounds.x - amount,
    y: bounds.y - amount,
    width: bounds.width + amount * 2,
    height: bounds.height + amount * 2,
  };
}

function uniqueSorted(values: number[]): number[] {
  return [...new Set(values.map((value) => Math.round(value * 1000) / 1000))].sort((a, b) => a - b);
}

function pointInsideBounds(point: Point, bounds: Bounds, inset = 0): boolean {
  return point.x > bounds.x + inset + EPSILON
    && point.x < bounds.x + bounds.width - inset - EPSILON
    && point.y > bounds.y + inset + EPSILON
    && point.y < bounds.y + bounds.height - inset - EPSILON;
}

function intervalsOverlap(firstA: number, firstB: number, secondA: number, secondB: number): boolean {
  return Math.min(Math.max(firstA, firstB), Math.max(secondA, secondB))
    - Math.max(Math.min(firstA, firstB), Math.min(secondA, secondB)) > EPSILON;
}

function segmentBlocked(segment: Segment, obstacles: readonly Bounds[]): boolean {
  const vertical = Math.abs(segment.start.x - segment.end.x) < EPSILON;
  const horizontal = Math.abs(segment.start.y - segment.end.y) < EPSILON;
  if (!vertical && !horizontal) return true;
  return obstacles.some((obstacle) => {
    if (vertical) {
      return segment.start.x > obstacle.x + EPSILON
        && segment.start.x < obstacle.x + obstacle.width - EPSILON
        && intervalsOverlap(segment.start.y, segment.end.y, obstacle.y, obstacle.y + obstacle.height);
    }
    return segment.start.y > obstacle.y + EPSILON
      && segment.start.y < obstacle.y + obstacle.height - EPSILON
      && intervalsOverlap(segment.start.x, segment.end.x, obstacle.x, obstacle.x + obstacle.width);
  });
}

function orientation(a: Point, b: Point, c: Point): number {
  return (b.y - a.y) * (c.x - b.x) - (b.x - a.x) * (c.y - b.y);
}

function segmentsCross(a: Point, b: Point, c: Point, d: Point): boolean {
  return orientation(a, b, c) * orientation(a, b, d) < 0
    && orientation(c, d, a) * orientation(c, d, b) < 0;
}

function segmentOverlapLength(first: Segment, second: Segment): number {
  const firstVertical = Math.abs(first.start.x - first.end.x) < EPSILON;
  const secondVertical = Math.abs(second.start.x - second.end.x) < EPSILON;
  if (firstVertical !== secondVertical) return 0;
  if (firstVertical && Math.abs(first.start.x - second.start.x) >= EPSILON) return 0;
  if (!firstVertical && (
    Math.abs(first.start.y - first.end.y) >= EPSILON
    || Math.abs(second.start.y - second.end.y) >= EPSILON
    || Math.abs(first.start.y - second.start.y) >= EPSILON
  )) return 0;
  const firstRange = firstVertical ? [first.start.y, first.end.y] : [first.start.x, first.end.x];
  const secondRange = firstVertical ? [second.start.y, second.end.y] : [second.start.x, second.end.x];
  return Math.max(0, Math.min(Math.max(...firstRange), Math.max(...secondRange))
    - Math.max(Math.min(...firstRange), Math.min(...secondRange)));
}

function parallelProximityPenalty(first: Segment, second: Segment): number {
  const firstVertical = Math.abs(first.start.x - first.end.x) < EPSILON;
  const secondVertical = Math.abs(second.start.x - second.end.x) < EPSILON;
  if (firstVertical !== secondVertical) return 0;
  const overlap = firstVertical
    ? Math.max(0, Math.min(Math.max(first.start.y, first.end.y), Math.max(second.start.y, second.end.y))
      - Math.max(Math.min(first.start.y, first.end.y), Math.min(second.start.y, second.end.y)))
    : Math.max(0, Math.min(Math.max(first.start.x, first.end.x), Math.max(second.start.x, second.end.x))
      - Math.max(Math.min(first.start.x, first.end.x), Math.min(second.start.x, second.end.x)));
  if (overlap <= EPSILON) return 0;
  const distance = firstVertical
    ? Math.abs(first.start.x - second.start.x)
    : Math.abs(first.start.y - second.start.y);
  return distance < 12 ? (12 - distance) * Math.min(overlap, 80) * 0.45 : 0;
}

function routePenalty(segment: Segment, usedSegments: readonly Segment[]): number {
  return usedSegments.reduce((penalty, used) => {
    const overlap = segmentOverlapLength(segment, used);
    const crossing = segmentsCross(segment.start, segment.end, used.start, used.end) ? 55 : 0;
    return penalty + overlap * 12 + crossing + parallelProximityPenalty(segment, used);
  }, 0);
}

function orthogonalFallback(start: Point, end: Point, obstacles: readonly Bounds[], scene: LabScene): Point[] {
  const candidates = [
    [start, { x: start.x, y: 18 }, { x: end.x, y: 18 }, end],
    [start, { x: start.x, y: scene.paper_height - 18 }, { x: end.x, y: scene.paper_height - 18 }, end],
    [start, { x: 18, y: start.y }, { x: 18, y: end.y }, end],
    [start, { x: scene.paper_width - 18, y: start.y }, { x: scene.paper_width - 18, y: end.y }, end],
    [start, { x: (start.x + end.x) / 2, y: start.y }, { x: (start.x + end.x) / 2, y: end.y }, end],
    [start, { x: start.x, y: (start.y + end.y) / 2 }, { x: end.x, y: (start.y + end.y) / 2 }, end],
  ].map(compact);
  const clear = candidates.filter((candidate) => candidate.slice(0, -1).every((point, index) => (
    !segmentBlocked({ start: point, end: candidate[index + 1] }, obstacles)
  )));
  const pool = clear.length ? clear : candidates;
  return pool.reduce((best, candidate) => {
    const length = candidate.slice(0, -1).reduce((total, point, index) => (
      total + Math.hypot(candidate[index + 1].x - point.x, candidate[index + 1].y - point.y)
    ), 0);
    const bestLength = best.slice(0, -1).reduce((total, point, index) => (
      total + Math.hypot(best[index + 1].x - point.x, best[index + 1].y - point.y)
    ), 0);
    return length < bestLength ? candidate : best;
  });
}

function orthogonalSearch(
  start: Point,
  end: Point,
  obstacles: readonly Bounds[],
  scene: LabScene,
  usedSegments: readonly Segment[],
): Point[] {
  const xs = uniqueSorted([
    18,
    scene.paper_width - 18,
    start.x,
    end.x,
    ...obstacles.flatMap((bounds) => [bounds.x, bounds.x + bounds.width]),
  ]);
  const ys = uniqueSorted([
    18,
    scene.paper_height - 18,
    start.y,
    end.y,
    ...obstacles.flatMap((bounds) => [bounds.y, bounds.y + bounds.height]),
  ]);
  const points: Point[] = [];
  const pointIndex = new Map<string, number>();
  const key = (point: Point) => `${Math.round(point.x * 1000) / 1000}:${Math.round(point.y * 1000) / 1000}`;
  for (const y of ys) {
    for (const x of xs) {
      const point = { x, y };
      if (obstacles.some((bounds) => pointInsideBounds(point, bounds))) continue;
      pointIndex.set(key(point), points.length);
      points.push(point);
    }
  }
  const adjacency: GraphLink[][] = Array.from({ length: points.length }, () => []);
  const connect = (first: number, second: number) => {
    const segment = { start: points[first], end: points[second] };
    if (segmentBlocked(segment, obstacles)) return;
    const vertical = Math.abs(segment.start.x - segment.end.x) < EPSILON;
    const link: GraphLink = {
      target: second,
      length: Math.hypot(segment.end.x - segment.start.x, segment.end.y - segment.start.y),
      direction: vertical ? "vertical" : "horizontal",
      segment,
    };
    adjacency[first].push(link);
    adjacency[second].push({ ...link, target: first, segment: { start: segment.end, end: segment.start } });
  };
  for (const y of ys) {
    const row = xs.map((x) => pointIndex.get(key({ x, y }))).filter((value): value is number => value !== undefined);
    for (let index = 0; index < row.length - 1; index += 1) connect(row[index], row[index + 1]);
  }
  for (const x of xs) {
    const column = ys.map((y) => pointIndex.get(key({ x, y }))).filter((value): value is number => value !== undefined);
    for (let index = 0; index < column.length - 1; index += 1) connect(column[index], column[index + 1]);
  }

  const startIndex = pointIndex.get(key(start));
  const endIndex = pointIndex.get(key(end));
  if (startIndex === undefined || endIndex === undefined) return orthogonalFallback(start, end, obstacles, scene);

  type Direction = "none" | "horizontal" | "vertical";
  interface SearchState { node: number; direction: Direction; cost: number }
  const stateKey = (node: number, direction: Direction) => `${node}:${direction}`;
  const queue: SearchState[] = [{ node: startIndex, direction: "none", cost: 0 }];
  const distances = new Map<string, number>([[stateKey(startIndex, "none"), 0]]);
  const previous = new Map<string, string>();
  let finalState: string | null = null;

  while (queue.length) {
    queue.sort((first, second) => first.cost - second.cost);
    const current = queue.shift()!;
    const currentKey = stateKey(current.node, current.direction);
    if (current.cost !== distances.get(currentKey)) continue;
    if (current.node === endIndex) {
      finalState = currentKey;
      break;
    }
    for (const link of adjacency[current.node]) {
      const bend = current.direction !== "none" && current.direction !== link.direction ? BEND_COST : 0;
      const nextCost = current.cost + link.length + bend + routePenalty(link.segment, usedSegments);
      const nextKey = stateKey(link.target, link.direction);
      if (nextCost >= (distances.get(nextKey) ?? Number.POSITIVE_INFINITY)) continue;
      distances.set(nextKey, nextCost);
      previous.set(nextKey, currentKey);
      queue.push({ node: link.target, direction: link.direction, cost: nextCost });
    }
  }
  if (!finalState) return orthogonalFallback(start, end, obstacles, scene);
  const result: Point[] = [];
  let cursor: string | undefined = finalState;
  while (cursor) {
    const node = Number(cursor.split(":")[0]);
    result.push(points[node]);
    cursor = previous.get(cursor);
  }
  return compact(result.reverse());
}

function adaptiveRoutes(scene: LabScene, boundaryPorts?: SceneBoundaryPortMap): RoutedEdge[] {
  const nodes = new Map(scene.nodes.map((node) => [node.scene_node_id, node]));
  const records = scene.edges.flatMap((edge): AdaptiveEdge[] => {
    const source = nodes.get(edge.source_scene_node_id);
    const target = nodes.get(edge.target_scene_node_id);
    if (!source || !target) return [];
    const sides = selectSidePair(source, target, scene.nodes);
    const sourcePortal = boundaryPorts?.[source.scene_node_id];
    const targetPortal = boundaryPorts?.[target.scene_node_id];
    return [{
      edge,
      source,
      target,
      sourceSide: sourcePortal?.exitSide ?? (sourcePortal || source.detail_expanded ? "right" : sides.sourceSide),
      targetSide: targetPortal?.entrySide ?? (targetPortal || target.detail_expanded ? "left" : sides.targetSide),
      sourcePort: sourcePortal?.exit,
      targetPort: targetPortal?.entry,
      sourceIsInterior: sourcePortal?.exitIsInterior ?? false,
      targetIsInterior: targetPortal?.entryIsInterior ?? false,
    }];
  });
  assignAdaptivePorts(records);
  const usedSegments: Segment[] = [];
  return records.map((record) => {
    const sourcePort = record.sourcePort ?? midpointPort(record.source, record.sourceSide);
    const targetPort = record.targetPort ?? midpointPort(record.target, record.targetSide);
    const sourceVector = sideVector(record.sourceSide);
    const targetVector = sideVector(record.targetSide);
    const start = {
      x: sourcePort.x + sourceVector.x * PORT_STUB,
      y: sourcePort.y + sourceVector.y * PORT_STUB,
    };
    const end = {
      x: targetPort.x + targetVector.x * PORT_STUB,
      y: targetPort.y + targetVector.y * PORT_STUB,
    };
    const obstacles = scene.nodes
      .filter((node) => !(
        record.sourceIsInterior && node.scene_node_id === record.source.scene_node_id
        || record.targetIsInterior && node.scene_node_id === record.target.scene_node_id
      ))
      .map((node) => inflate(node.bounds, NODE_CLEARANCE));
    const searched = orthogonalSearch(start, end, obstacles, scene, usedSegments);
    const compacted = compact([sourcePort, start, ...searched, end, targetPort]);
    for (let index = 0; index < compacted.length - 1; index += 1) {
      usedSegments.push({ start: compacted[index], end: compacted[index + 1] });
    }
    const label = labelGeometry(compacted, true);
    return {
      edge: record.edge,
      points: compacted,
      path: roundedPolylinePath(compacted),
      labelPoint: label.point,
      labelAngle: label.angle,
      sourceSide: record.sourceSide,
      targetSide: record.targetSide,
      markerEnd: !boundaryPorts?.[record.target.scene_node_id],
      foreground: record.sourceIsInterior || record.targetIsInterior,
    };
  });
}

export function routeScene(
  scene: LabScene,
  style: RouteStyle,
  boundaryPorts?: SceneBoundaryPortMap,
): RoutedEdge[] {
  if (style === "adaptive") return adaptiveRoutes(scene, boundaryPorts);
  const nodes = new Map(scene.nodes.map((node) => [node.scene_node_id, node]));
  return scene.edges.flatMap((edge, index) => {
    const source = nodes.get(edge.source_scene_node_id);
    const target = nodes.get(edge.target_scene_node_id);
    if (!source || !target) return [];
    const anchor = anchors(source, target, boundaryPorts);
    const lane = edgeLane(edge, index, scene.edges);
    const curve = style === "curve" ? curveGeometry(anchor.start, anchor.end, lane) : null;
    const points = curve?.points ?? routePoints(anchor.start, anchor.end, style, lane);
    const label = labelGeometry(points, !curve);
    return [{
      edge,
      points,
      path: curve?.path ?? polylinePath(points),
      labelPoint: label.point,
      labelAngle: label.angle,
      sourceSide: anchor.sourceSide,
      targetSide: anchor.targetSide,
      markerEnd: !boundaryPorts?.[target.scene_node_id],
      foreground: Boolean(
        boundaryPorts?.[source.scene_node_id]?.exitIsInterior
        || boundaryPorts?.[target.scene_node_id]?.entryIsInterior
      ),
    }];
  });
}

function segmentSamples(segment: Segment, count = 9): Point[] {
  return Array.from({ length: count }, (_, index) => {
    const ratio = index / (count - 1);
    return {
      x: segment.start.x + (segment.end.x - segment.start.x) * ratio,
      y: segment.start.y + (segment.end.y - segment.start.y) * ratio,
    };
  });
}

function segmentNearBounds(segment: Segment, bounds: Bounds, clearance: number): boolean {
  const expanded = inflate(bounds, clearance);
  return segmentSamples(segment).some((point) => pointInsideBounds(point, expanded, -EPSILON));
}

function endpointCongestion(routes: readonly RoutedEdge[]): number {
  const groups = new Map<string, Point[]>();
  for (const route of routes) {
    const start = route.points[0];
    const end = route.points.at(-1)!;
    const sourceKey = `source:${route.edge.source_scene_node_id}`;
    const targetKey = `target:${route.edge.target_scene_node_id}`;
    groups.set(sourceKey, [...(groups.get(sourceKey) ?? []), start]);
    groups.set(targetKey, [...(groups.get(targetKey) ?? []), end]);
  }
  let congestion = 0;
  for (const points of groups.values()) {
    for (let first = 0; first < points.length; first += 1) {
      for (let second = first + 1; second < points.length; second += 1) {
        if (Math.hypot(points[first].x - points[second].x, points[first].y - points[second].y) < 8) congestion += 1;
      }
    }
  }
  return congestion;
}

function reverseExitCount(scene: LabScene, routes: readonly RoutedEdge[]): number {
  const nodes = new Map(scene.nodes.map((node) => [node.scene_node_id, node]));
  let count = 0;
  for (const route of routes) {
    if (route.points.length < 2) continue;
    const source = nodes.get(route.edge.source_scene_node_id);
    const target = nodes.get(route.edge.target_scene_node_id);
    if (!source || !target) continue;
    const desired = {
      x: center(target.bounds).x - center(source.bounds).x,
      y: center(target.bounds).y - center(source.bounds).y,
    };
    const start = route.points[0];
    const afterStart = route.points[1];
    const beforeEnd = route.points.at(-2)!;
    const end = route.points.at(-1)!;
    if ((afterStart.x - start.x) * desired.x + (afterStart.y - start.y) * desired.y < -EPSILON) count += 1;
    if ((end.x - beforeEnd.x) * desired.x + (end.y - beforeEnd.y) * desired.y < -EPSILON) count += 1;
  }
  return count;
}

export function measureScene(scene: LabScene, routed: RoutedEdge[]): SceneMetrics {
  let crossings = 0;
  let overlaps = 0;
  let nodeIntersections = 0;
  let labelIntersections = 0;
  let clearanceViolations = 0;
  let sharedLength = 0;
  let bends = 0;
  let routeLength = 0;
  const segments = routed.flatMap((route, routeIndex) => route.points.slice(0, -1).map((start, index) => ({
    routeIndex,
    start,
    end: route.points[index + 1],
  })));
  for (const route of routed) {
    bends += Math.max(0, route.points.length - 2);
    for (let index = 0; index < route.points.length - 1; index += 1) {
      const segment = { start: route.points[index], end: route.points[index + 1] };
      routeLength += Math.hypot(segment.end.x - segment.start.x, segment.end.y - segment.start.y);
      for (const node of scene.nodes) {
        const isSource = route.edge.source_scene_node_id === node.scene_node_id;
        const isTarget = route.edge.target_scene_node_id === node.scene_node_id;
        const allowedEndpointSegment = isSource && index === 0
          || isTarget && index === route.points.length - 2;
        if (!isSource && !isTarget && segmentNearBounds(segment, node.bounds, 0)) nodeIntersections += 1;
        if (!allowedEndpointSegment && segmentNearBounds(segment, node.bounds, 9)) clearanceViolations += 1;
      }
    }
    const labelWidth = Math.max(44, route.edge.label.length * 6.8);
    const vertical = Math.abs(route.labelAngle) === 90;
    const labelBounds = {
      x: route.labelPoint.x - (vertical ? 10 : labelWidth / 2),
      y: route.labelPoint.y - (vertical ? labelWidth / 2 : 13),
      width: vertical ? 20 : labelWidth,
      height: vertical ? labelWidth : 20,
    };
    if (scene.nodes.some((node) => (
      labelBounds.x < node.bounds.x + node.bounds.width
      && labelBounds.x + labelBounds.width > node.bounds.x
      && labelBounds.y < node.bounds.y + node.bounds.height
      && labelBounds.y + labelBounds.height > node.bounds.y
    ))) labelIntersections += 1;
  }
  for (let first = 0; first < segments.length; first += 1) {
    for (let second = first + 1; second < segments.length; second += 1) {
      if (segments[first].routeIndex === segments[second].routeIndex) continue;
      if (segmentsCross(segments[first].start, segments[first].end, segments[second].start, segments[second].end)) crossings += 1;
      const overlap = segmentOverlapLength(segments[first], segments[second]);
      if (overlap > 4) overlaps += 1;
      sharedLength += overlap;
    }
  }
  return {
    crossings,
    overlaps,
    nodeIntersections,
    labelIntersections,
    clearanceViolations,
    endpointCongestion: endpointCongestion(routed),
    reverseExits: reverseExitCount(scene, routed),
    sharedLength: Math.round(sharedLength),
    bends,
    routeLength: Math.round(routeLength),
  };
}
