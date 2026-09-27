import type { IndexableSceneNode, ScenePoint } from "./scene-performance";

type RouteSide = "left" | "right" | "top" | "bottom";

export interface RoutableSceneEdge {
  source_scene_node_id: string;
  target_scene_node_id: string;
  points: ScenePoint[];
}

interface EndpointRouteLock {
  side: RouteSide;
  ratio: number;
  stubLength: number;
}

export interface GestureRouteLock {
  source: EndpointRouteLock;
  target: EndpointRouteLock;
  corridorAxis: "x" | "y";
  corridorValue: number;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value));
}

function endpointSide(
  point: ScenePoint,
  node: IndexableSceneNode,
  adjacent: ScenePoint,
): RouteSide {
  const bounds = node.bounds;
  const distances: Array<[RouteSide, number]> = [
    ["left", Math.abs(point.x - bounds.x)],
    ["right", Math.abs(point.x - bounds.x - bounds.width)],
    ["top", Math.abs(point.y - bounds.y)],
    ["bottom", Math.abs(point.y - bounds.y - bounds.height)],
  ];
  const minimum = Math.min(...distances.map(([, distance]) => distance));
  const candidates = new Set(
    distances
      .filter(([, distance]) => Math.abs(distance - minimum) < 0.01)
      .map(([side]) => side),
  );
  if (candidates.size === 1) return [...candidates][0];

  const dx = adjacent.x - point.x;
  const dy = adjacent.y - point.y;
  const inferred = Math.abs(dx) >= Math.abs(dy)
    ? dx >= 0 ? "right" : "left"
    : dy >= 0 ? "bottom" : "top";
  return candidates.has(inferred) ? inferred : [...candidates][0];
}

function endpointRatio(
  point: ScenePoint,
  node: IndexableSceneNode,
  side: RouteSide,
): number {
  if (side === "left" || side === "right") {
    return clamp((point.y - node.bounds.y) / node.bounds.height, 0, 1);
  }
  return clamp((point.x - node.bounds.x) / node.bounds.width, 0, 1);
}

function endpointPoint(
  node: IndexableSceneNode,
  preview: ScenePoint | undefined,
  lock: EndpointRouteLock,
): ScenePoint {
  const bounds = { ...node.bounds, ...(preview ?? {}) };
  if (lock.side === "left" || lock.side === "right") {
    return {
      x: lock.side === "left" ? bounds.x : bounds.x + bounds.width,
      y: bounds.y + bounds.height * lock.ratio,
    };
  }
  return {
    x: bounds.x + bounds.width * lock.ratio,
    y: lock.side === "top" ? bounds.y : bounds.y + bounds.height,
  };
}

function routeStub(point: ScenePoint, lock: EndpointRouteLock): ScenePoint {
  if (lock.side === "left") return { x: point.x - lock.stubLength, y: point.y };
  if (lock.side === "right") return { x: point.x + lock.stubLength, y: point.y };
  if (lock.side === "top") return { x: point.x, y: point.y - lock.stubLength };
  return { x: point.x, y: point.y + lock.stubLength };
}

function segmentLength(left: ScenePoint, right: ScenePoint): number {
  return Math.abs(right.x - left.x) + Math.abs(right.y - left.y);
}

function simplify(points: ScenePoint[]): ScenePoint[] {
  const result: ScenePoint[] = [];
  for (const point of points) {
    const previous = result.at(-1);
    if (previous && previous.x === point.x && previous.y === point.y) continue;
    result.push(point);
    while (result.length >= 3) {
      const [first, middle, last] = result.slice(-3);
      const betweenX = middle.x >= Math.min(first.x, last.x)
        && middle.x <= Math.max(first.x, last.x);
      const betweenY = middle.y >= Math.min(first.y, last.y)
        && middle.y <= Math.max(first.y, last.y);
      if (first.x === middle.x && middle.x === last.x && betweenY) result.splice(-2, 1);
      else if (first.y === middle.y && middle.y === last.y && betweenX) result.splice(-2, 1);
      else break;
    }
  }
  return result;
}

function lockedCorridor(
  points: readonly ScenePoint[],
  index: number,
): Pick<GestureRouteLock, "corridorAxis" | "corridorValue"> {
  const internal = points.slice(1, -1).slice(0, -1).map((point, internalIndex) => {
    const next = points[internalIndex + 2];
    const vertical = Math.abs(point.x - next.x) < 0.01;
    const horizontal = Math.abs(point.y - next.y) < 0.01;
    return {
      axis: vertical ? "x" as const : "y" as const,
      value: vertical ? point.x : point.y,
      length: vertical || horizontal ? segmentLength(point, next) : -1,
    };
  }).sort((left, right) => right.length - left.length);
  if (internal[0]?.length >= 0) {
    return {
      corridorAxis: internal[0].axis,
      corridorValue: internal[0].value,
    };
  }
  const start = points[0];
  const end = points.at(-1)!;
  const offset = ((index % 5) - 2) * 5;
  if (Math.abs(end.x - start.x) >= Math.abs(end.y - start.y)) {
    return { corridorAxis: "x", corridorValue: (start.x + end.x) / 2 + offset };
  }
  return { corridorAxis: "y", corridorValue: (start.y + end.y) / 2 + offset };
}

export function createGestureRouteLock(
  edge: RoutableSceneEdge,
  nodesById: ReadonlyMap<string, IndexableSceneNode>,
  index: number,
): GestureRouteLock | null {
  const source = nodesById.get(edge.source_scene_node_id);
  const target = nodesById.get(edge.target_scene_node_id);
  if (!source || !target || edge.points.length < 2) return null;
  const start = edge.points[0];
  const sourceAdjacent = edge.points[1];
  const end = edge.points.at(-1)!;
  const targetAdjacent = edge.points.at(-2)!;
  const sourceSide = endpointSide(start, source, sourceAdjacent);
  const targetSide = endpointSide(end, target, targetAdjacent);
  return {
    source: {
      side: sourceSide,
      ratio: endpointRatio(start, source, sourceSide),
      stubLength: Math.max(8, segmentLength(start, sourceAdjacent)),
    },
    target: {
      side: targetSide,
      ratio: endpointRatio(end, target, targetSide),
      stubLength: Math.max(8, segmentLength(end, targetAdjacent)),
    },
    ...lockedCorridor(edge.points, index),
  };
}

export function previewEdgePoints(
  edge: RoutableSceneEdge,
  nodesById: ReadonlyMap<string, IndexableSceneNode>,
  preview: Readonly<Record<string, ScenePoint>>,
  index: number,
  gestureLock?: GestureRouteLock | null,
): ScenePoint[] {
  const source = nodesById.get(edge.source_scene_node_id);
  const target = nodesById.get(edge.target_scene_node_id);
  if (!source || !target) return edge.points;
  const sourcePreview = preview[source.scene_node_id];
  const targetPreview = preview[target.scene_node_id];
  if (!sourcePreview && !targetPreview) return edge.points;

  const sourceDelta = sourcePreview
    ? { x: sourcePreview.x - source.bounds.x, y: sourcePreview.y - source.bounds.y }
    : { x: 0, y: 0 };
  const targetDelta = targetPreview
    ? { x: targetPreview.x - target.bounds.x, y: targetPreview.y - target.bounds.y }
    : { x: 0, y: 0 };
  if (
    sourcePreview
    && targetPreview
    && Math.abs(sourceDelta.x - targetDelta.x) < 0.01
    && Math.abs(sourceDelta.y - targetDelta.y) < 0.01
  ) {
    return edge.points.map((point) => ({
      x: point.x + sourceDelta.x,
      y: point.y + sourceDelta.y,
    }));
  }

  const lock = gestureLock ?? createGestureRouteLock(edge, nodesById, index);
  if (!lock) return edge.points;
  const start = sourcePreview
    ? endpointPoint(source, sourcePreview, lock.source)
    : edge.points[0];
  const end = targetPreview
    ? endpointPoint(target, targetPreview, lock.target)
    : edge.points.at(-1)!;
  const sourceStub = routeStub(start, lock.source);
  const targetStub = routeStub(end, lock.target);
  if (lock.corridorAxis === "x") {
    return simplify([
      start,
      sourceStub,
      { x: lock.corridorValue, y: sourceStub.y },
      { x: lock.corridorValue, y: targetStub.y },
      targetStub,
      end,
    ]);
  }
  return simplify([
    start,
    sourceStub,
    { x: sourceStub.x, y: lock.corridorValue },
    { x: targetStub.x, y: lock.corridorValue },
    targetStub,
    end,
  ]);
}
