import { buildModuleDetail, EXPANDED_DETAIL_SIZES } from "./module-details";
import type { DetailPrimitive, ModuleDetailDiagram } from "./module-details";
import type { Bounds, HierarchyRoutingMode, NodeDetailKind, Point, PortSide } from "./types";

type DetailShapePrimitive = Extract<DetailPrimitive, { kind: "rect" | "circle" | "matrix" }>;

export type DetailOffsetMap = Record<string, Point>;
export type DetailLayoutMap = Record<string, DetailOffsetMap>;
export type DetailNodeBoundsMap = Record<string, Bounds>;

export interface DetailExpansionBranch {
  childId: string;
  child?: DetailExpansionBranch;
}

export type DetailExpansionMap = Record<string, DetailExpansionBranch>;

export interface DetailNode {
  id: string;
  primitiveIndex: number;
  primitive: DetailShapePrimitive;
  bounds: Bounds;
  label: string;
  nestedKind?: NodeDetailKind;
}

export interface InlineDetailLevel {
  kind: NodeDetailKind;
  bounds: Bounds;
  diagram: ModuleDetailDiagram;
  nodes: DetailNode[];
  levelKey: string;
  routingMode: HierarchyRoutingMode;
  expandedChild?: {
    node: DetailNode;
    level: InlineDetailLevel;
  };
}

interface DetailLayoutOptions {
  nodeBounds?: DetailNodeBoundsMap;
  entryPoint?: Point;
  exitPoint?: Point;
  bottomTextFromY?: number;
  bottomTextY?: number;
  nodePorts?: Record<string, Partial<Record<PortSide, Point>>>;
  nodePortDirections?: Record<string, Partial<Record<PortSide, PortSide>>>;
  junctionPorts?: Record<string, Point>;
  suppressExitMarker?: boolean;
  suppressExpandedChildMarker?: boolean;
  adaptivePortNodeIds?: ReadonlySet<string>;
}

interface Anchor {
  node: DetailNode;
  side: "left" | "right" | "top" | "bottom";
}

interface OccupiedRoute {
  points: Point[];
  channel?: string;
}

const DETAIL_NODE_PREFIX = "detail-node-";
const ANCHOR_TOLERANCE = 8;
const DIRECTED_ANCHOR_GAP = 72;
const ROUTE_PADDING = 7;
const INLINE_EXPANSION_GAP = 34;
const INLINE_RIGHT_PADDING = 32;
const INLINE_BOTTOM_PADDING = 36;
const ROUTE_CHANNEL_STEP = 14;
const SHARED_ENDPOINT_ALLOWANCE = 14;

export function detailNodeId(primitiveIndex: number): string {
  return `${DETAIL_NODE_PREFIX}${primitiveIndex}`;
}

function primitiveBounds(primitive: DetailShapePrimitive): Bounds {
  if (primitive.kind === "circle") {
    return {
      x: primitive.cx - primitive.radius,
      y: primitive.cy - primitive.radius,
      width: primitive.radius * 2,
      height: primitive.radius * 2,
    };
  }
  return { x: primitive.x, y: primitive.y, width: primitive.width, height: primitive.height };
}

function primitiveLabel(primitive: DetailShapePrimitive): string {
  return primitive.label ?? (primitive.kind === "matrix" ? "tensor" : "submodule");
}

function isInteractivePrimitive(primitive: DetailPrimitive): primitive is DetailShapePrimitive {
  if (primitive.kind !== "rect" && primitive.kind !== "circle" && primitive.kind !== "matrix") return false;
  return primitive.kind !== "rect" || primitive.variant !== "frame";
}

export function inferNestedDetailKind(
  parentKind: NodeDetailKind,
  primitive: DetailShapePrimitive,
): NodeDetailKind | undefined {
  const label = primitiveLabel(primitive);
  const note = primitive.kind === "rect" ? primitive.note ?? "" : "";
  const value = `${label} ${note}`.toLowerCase();
  let nestedKind: NodeDetailKind | undefined;

  if (parentKind === "dual-encoder" && value.includes("image")) nestedKind = "vision-transformer";
  else if (parentKind === "dual-encoder" && value.includes("text")) nestedKind = "attention";
  else if (parentKind === "seq2seq" && /encoder|decoder/.test(value)) nestedKind = "recurrent";
  else if (["autoencoder", "variational-autoencoder"].includes(parentKind) && /encoder|decoder/.test(value)) nestedKind = "mlp";
  else if (parentKind === "unet" && /enc|dec|bottleneck/.test(value)) nestedKind = "convolution";
  else if (/gru/.test(value)) nestedKind = "gru";
  else if (/lstm|\brnn\b|recurrent/.test(value)) nestedKind = "recurrent";
  else if (/transformer|attention|softmax/.test(value)) nestedKind = "attention";
  else if (/depthwise|\bdw\b|pointwise|\bpw\b/.test(value)) nestedKind = "depthwise-convolution";
  else if (/conv|feature map/.test(value)) nestedKind = "convolution";
  else if (/layernorm|\bnorm\b|statistics/.test(value)) nestedKind = "normalization";
  else if (/pool/.test(value)) nestedKind = "pooling";
  else if (/embedding|lookup|position/.test(value)) nestedKind = "embedding";
  else if (parentKind === "graph-message-passing" && /message|update/.test(value)) nestedKind = "mlp";
  else if (parentKind === "dqn" && /qθ|network/.test(value)) nestedKind = "mlp";
  else if (parentKind === "actor-critic" && /actor|critic/.test(value)) nestedKind = "mlp";
  else if (parentKind === "distillation" && /teacher|student/.test(value)) nestedKind = "mlp";
  else if (parentKind === "gan" && /generator|discriminator/.test(value)) nestedKind = "mlp";
  else if (/expert|ffn|mlp|linear/.test(value)) nestedKind = "mlp";

  return nestedKind === parentKind ? undefined : nestedKind;
}

export function listDetailNodes(diagram: ModuleDetailDiagram): DetailNode[] {
  return diagram.primitives.flatMap((primitive, primitiveIndex) => {
    if (!isInteractivePrimitive(primitive)) return [];
    return [{
      id: detailNodeId(primitiveIndex),
      primitiveIndex,
      primitive,
      bounds: primitiveBounds(primitive),
      label: primitiveLabel(primitive),
      nestedKind: inferNestedDetailKind(diagram.kind, primitive),
    }];
  });
}

function translatePrimitive(primitive: DetailPrimitive, offset: Point): DetailPrimitive {
  if (!offset.x && !offset.y) return primitive;
  if (primitive.kind === "circle") return { ...primitive, cx: primitive.cx + offset.x, cy: primitive.cy + offset.y };
  if (primitive.kind === "rect" || primitive.kind === "matrix") {
    return { ...primitive, x: primitive.x + offset.x, y: primitive.y + offset.y };
  }
  return primitive;
}

function resizePrimitive(primitive: DetailPrimitive, bounds: Bounds | undefined): DetailPrimitive {
  if (!bounds) return primitive;
  if (primitive.kind === "circle") {
    return {
      ...primitive,
      cx: bounds.x + bounds.width / 2,
      cy: bounds.y + bounds.height / 2,
      radius: Math.min(bounds.width, bounds.height) / 2,
    };
  }
  if (primitive.kind === "rect" || primitive.kind === "matrix") {
    return { ...primitive, ...bounds };
  }
  return primitive;
}

function distanceToBoundary(point: Point, bounds: Bounds): number {
  const right = bounds.x + bounds.width;
  const bottom = bounds.y + bounds.height;
  const outsideX = Math.max(bounds.x - point.x, 0, point.x - right);
  const outsideY = Math.max(bounds.y - point.y, 0, point.y - bottom);
  if (outsideX || outsideY) return Math.hypot(outsideX, outsideY);
  return Math.min(
    Math.abs(point.x - bounds.x),
    Math.abs(point.x - right),
    Math.abs(point.y - bounds.y),
    Math.abs(point.y - bottom),
  );
}

function anchorSide(point: Point, bounds: Bounds): Anchor["side"] {
  const distances: Array<[Anchor["side"], number]> = [
    ["left", Math.abs(point.x - bounds.x)],
    ["right", Math.abs(point.x - bounds.x - bounds.width)],
    ["top", Math.abs(point.y - bounds.y)],
    ["bottom", Math.abs(point.y - bounds.y - bounds.height)],
  ];
  distances.sort((a, b) => a[1] - b[1]);
  return distances[0][0];
}

function directedAnchor(
  point: Point,
  adjacent: Point,
  endpoint: "start" | "end",
  nodes: DetailNode[],
): Anchor | undefined {
  const travelX = endpoint === "start" ? adjacent.x - point.x : point.x - adjacent.x;
  const travelY = endpoint === "start" ? adjacent.y - point.y : point.y - adjacent.y;
  if (Math.abs(travelX) < 0.01 && Math.abs(travelY) < 0.01) return undefined;

  const side: Anchor["side"] = Math.abs(travelX) >= Math.abs(travelY)
    ? endpoint === "start"
      ? travelX > 0 ? "right" : "left"
      : travelX > 0 ? "left" : "right"
    : endpoint === "start"
      ? travelY > 0 ? "bottom" : "top"
      : travelY > 0 ? "top" : "bottom";

  const candidates = nodes.flatMap((node) => {
    const { x, y, width, height } = node.bounds;
    const right = x + width;
    const bottom = y + height;
    let gap: number;
    let aligned: boolean;
    if (side === "left") {
      gap = x - point.x;
      aligned = point.y >= y - ANCHOR_TOLERANCE && point.y <= bottom + ANCHOR_TOLERANCE;
    } else if (side === "right") {
      gap = point.x - right;
      aligned = point.y >= y - ANCHOR_TOLERANCE && point.y <= bottom + ANCHOR_TOLERANCE;
    } else if (side === "top") {
      gap = y - point.y;
      aligned = point.x >= x - ANCHOR_TOLERANCE && point.x <= right + ANCHOR_TOLERANCE;
    } else {
      gap = point.y - bottom;
      aligned = point.x >= x - ANCHOR_TOLERANCE && point.x <= right + ANCHOR_TOLERANCE;
    }
    return aligned && gap >= -ANCHOR_TOLERANCE && gap <= DIRECTED_ANCHOR_GAP
      ? [{ node, distance: Math.max(0, gap) }]
      : [];
  }).sort((a, b) => a.distance - b.distance);
  return candidates[0] ? { node: candidates[0].node, side } : undefined;
}

function findAnchor(
  point: Point,
  nodes: DetailNode[],
  adjacent?: Point,
  endpoint?: "start" | "end",
  allowDirectedGap = false,
): Anchor | undefined {
  const candidates = nodes
    .map((node) => ({ node, distance: distanceToBoundary(point, node.bounds) }))
    .filter(({ distance }) => distance <= ANCHOR_TOLERANCE)
    .sort((a, b) => a.distance - b.distance);
  const match = candidates[0]?.node;
  if (match) return { node: match, side: anchorSide(point, match.bounds) };
  return allowDirectedGap && adjacent && endpoint
    ? directedAnchor(point, adjacent, endpoint, nodes)
    : undefined;
}

function samePoint(a: Point, b: Point): boolean {
  return Math.abs(a.x - b.x) < 0.01 && Math.abs(a.y - b.y) < 0.01;
}

function pointKey(point: Point): string {
  return `${point.x.toFixed(3)},${point.y.toFixed(3)}`;
}

function boundsEqual(a: Bounds, b: Bounds): boolean {
  return samePoint(a, b) && Math.abs(a.width - b.width) < 0.01 && Math.abs(a.height - b.height) < 0.01;
}

function centeredBoundaryPoint(side: Anchor["side"], bounds: Bounds): Point {
  if (side === "left") return { x: bounds.x, y: bounds.y + bounds.height / 2 };
  if (side === "right") return { x: bounds.x + bounds.width, y: bounds.y + bounds.height / 2 };
  if (side === "top") return { x: bounds.x + bounds.width / 2, y: bounds.y };
  return { x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height };
}

function boundsCenter(bounds: Bounds): Point {
  return {
    x: bounds.x + bounds.width / 2,
    y: bounds.y + bounds.height / 2,
  };
}

function sideToward(bounds: Bounds, target: Point): Anchor["side"] {
  const center = boundsCenter(bounds);
  const dx = target.x - center.x;
  const dy = target.y - center.y;
  if (Math.abs(dx) >= Math.abs(dy)) return dx < 0 ? "left" : "right";
  return dy < 0 ? "top" : "bottom";
}

function outward(point: Point, side: Anchor["side"], distance: number): Point {
  if (side === "left") return { x: point.x - distance, y: point.y };
  if (side === "right") return { x: point.x + distance, y: point.y };
  if (side === "top") return { x: point.x, y: point.y - distance };
  return { x: point.x, y: point.y + distance };
}

function compactPoints(points: Point[]): Point[] {
  const compacted: Point[] = [];
  for (const point of points) {
    if (compacted.at(-1) && samePoint(compacted.at(-1)!, point)) continue;
    compacted.push(point);
    while (compacted.length >= 3) {
      const previous = compacted[compacted.length - 3];
      const middle = compacted[compacted.length - 2];
      const next = compacted[compacted.length - 1];
      const between = (value: number, first: number, second: number) => (
        value >= Math.min(first, second) && value <= Math.max(first, second)
      );
      const redundantHorizontal = previous.y === middle.y && middle.y === next.y
        && between(middle.x, previous.x, next.x);
      const redundantVertical = previous.x === middle.x && middle.x === next.x
        && between(middle.y, previous.y, next.y);
      if (!redundantHorizontal && !redundantVertical) break;
      compacted.splice(compacted.length - 2, 1);
    }
  }
  return compacted;
}

function padded(bounds: Bounds, amount: number): Bounds {
  return {
    x: bounds.x - amount,
    y: bounds.y - amount,
    width: bounds.width + amount * 2,
    height: bounds.height + amount * 2,
  };
}

function segmentIntersectsBounds(a: Point, b: Point, bounds: Bounds): boolean {
  const right = bounds.x + bounds.width;
  const bottom = bounds.y + bounds.height;
  if (a.y === b.y) {
    return a.y > bounds.y && a.y < bottom && Math.max(Math.min(a.x, b.x), bounds.x) < Math.min(Math.max(a.x, b.x), right);
  }
  if (a.x === b.x) {
    return a.x > bounds.x && a.x < right && Math.max(Math.min(a.y, b.y), bounds.y) < Math.min(Math.max(a.y, b.y), bottom);
  }
  const segmentBox = {
    x: Math.min(a.x, b.x),
    y: Math.min(a.y, b.y),
    width: Math.abs(a.x - b.x),
    height: Math.abs(a.y - b.y),
  };
  return segmentBox.x < right && segmentBox.x + segmentBox.width > bounds.x
    && segmentBox.y < bottom && segmentBox.y + segmentBox.height > bounds.y;
}

function collisionCount(points: Point[], obstacles: Bounds[]): number {
  let count = 0;
  for (let index = 1; index < points.length; index += 1) {
    for (const obstacle of obstacles) {
      if (segmentIntersectsBounds(points[index - 1], points[index], obstacle)) count += 1;
    }
  }
  return count;
}

function routeLength(points: Point[]): number {
  let length = 0;
  for (let index = 1; index < points.length; index += 1) {
    length += Math.abs(points[index].x - points[index - 1].x) + Math.abs(points[index].y - points[index - 1].y);
  }
  return length;
}

function collinearOverlap(a: Point, b: Point, c: Point, d: Point): number {
  if (a.y === b.y && c.y === d.y && a.y === c.y) {
    return Math.max(0, Math.min(Math.max(a.x, b.x), Math.max(c.x, d.x))
      - Math.max(Math.min(a.x, b.x), Math.min(c.x, d.x)));
  }
  if (a.x === b.x && c.x === d.x && a.x === c.x) {
    return Math.max(0, Math.min(Math.max(a.y, b.y), Math.max(c.y, d.y))
      - Math.max(Math.min(a.y, b.y), Math.min(c.y, d.y)));
  }
  return 0;
}

function sharedEndpointAllowance(points: Point[], occupied: Point[], a: Point, b: Point, c: Point, d: Point): number {
  const candidateEndpoints = [points[0], points.at(-1)!];
  const occupiedEndpoints = [occupied[0], occupied.at(-1)!];
  return candidateEndpoints.some((candidate) => occupiedEndpoints.some((endpoint) => samePoint(candidate, endpoint))
    && (samePoint(candidate, a) || samePoint(candidate, b))
    && (samePoint(candidate, c) || samePoint(candidate, d)))
    ? SHARED_ENDPOINT_ALLOWANCE
    : 0;
}

function sharedLength(points: Point[], occupiedRoutes: OccupiedRoute[], channel?: string): number {
  let length = 0;
  for (let index = 1; index < points.length; index += 1) {
    const a = points[index - 1];
    const b = points[index];
    for (const occupied of occupiedRoutes) {
      if (channel && occupied.channel === channel) continue;
      for (let otherIndex = 1; otherIndex < occupied.points.length; otherIndex += 1) {
        const c = occupied.points[otherIndex - 1];
        const d = occupied.points[otherIndex];
        const overlap = collinearOverlap(a, b, c, d);
        if (!overlap) continue;
        length += Math.max(0, overlap - sharedEndpointAllowance(points, occupied.points, a, b, c, d));
      }
    }
  }
  return length;
}

function crossingCount(points: Point[], occupiedRoutes: OccupiedRoute[]): number {
  let count = 0;
  for (let index = 1; index < points.length; index += 1) {
    const a = points[index - 1];
    const b = points[index];
    for (const occupied of occupiedRoutes) {
      for (let otherIndex = 1; otherIndex < occupied.points.length; otherIndex += 1) {
        const c = occupied.points[otherIndex - 1];
        const d = occupied.points[otherIndex];
        const horizontal = a.y === b.y && c.x === d.x;
        const vertical = a.x === b.x && c.y === d.y;
        if (!horizontal && !vertical) continue;
        const horizontalStart = horizontal ? a : c;
        const horizontalEnd = horizontal ? b : d;
        const verticalStart = horizontal ? c : a;
        const verticalEnd = horizontal ? d : b;
        const x = verticalStart.x;
        const y = horizontalStart.y;
        const intersects = x > Math.min(horizontalStart.x, horizontalEnd.x)
          && x < Math.max(horizontalStart.x, horizontalEnd.x)
          && y > Math.min(verticalStart.y, verticalEnd.y)
          && y < Math.max(verticalStart.y, verticalEnd.y);
        if (intersects) count += 1;
      }
    }
  }
  return count;
}

function nearParallelLength(points: Point[], occupiedRoutes: OccupiedRoute[]): number {
  let length = 0;
  for (let index = 1; index < points.length; index += 1) {
    const a = points[index - 1];
    const b = points[index];
    for (const occupied of occupiedRoutes) {
      for (let otherIndex = 1; otherIndex < occupied.points.length; otherIndex += 1) {
        const c = occupied.points[otherIndex - 1];
        const d = occupied.points[otherIndex];
        if (a.y === b.y && c.y === d.y && Math.abs(a.y - c.y) < ROUTE_CHANNEL_STEP) {
          length += Math.max(0, Math.min(Math.max(a.x, b.x), Math.max(c.x, d.x))
            - Math.max(Math.min(a.x, b.x), Math.min(c.x, d.x)));
        } else if (a.x === b.x && c.x === d.x && Math.abs(a.x - c.x) < ROUTE_CHANNEL_STEP) {
          length += Math.max(0, Math.min(Math.max(a.y, b.y), Math.max(c.y, d.y))
            - Math.max(Math.min(a.y, b.y), Math.min(c.y, d.y)));
        }
      }
    }
  }
  return length;
}

function orthogonalRoute(
  start: Point,
  end: Point,
  startSide: Anchor["side"] | undefined,
  endSide: Anchor["side"] | undefined,
  obstacles: Bounds[],
  hardObstacles: Bounds[],
  occupiedRoutes: OccupiedRoute[] = [],
  channel?: string,
): Point[] {
  const sourceStub = startSide ? outward(start, startSide, 12) : start;
  const targetStub = endSide ? outward(end, endSide, 12) : end;
  const allBounds = obstacles.length ? {
    left: Math.min(...obstacles.map((item) => item.x)),
    right: Math.max(...obstacles.map((item) => item.x + item.width)),
    top: Math.min(...obstacles.map((item) => item.y)),
    bottom: Math.max(...obstacles.map((item) => item.y + item.height)),
  } : { left: Math.min(start.x, end.x), right: Math.max(start.x, end.x), top: Math.min(start.y, end.y), bottom: Math.max(start.y, end.y) };
  const middleX = (sourceStub.x + targetStub.x) / 2;
  const middleY = (sourceStub.y + targetStub.y) / 2;
  const channelOffsets = [-2, -1, 1, 2].map((offset) => offset * ROUTE_CHANNEL_STEP);
  const candidates = [
    [start, sourceStub, { x: targetStub.x, y: sourceStub.y }, targetStub, end],
    [start, sourceStub, { x: sourceStub.x, y: targetStub.y }, targetStub, end],
    [start, sourceStub, { x: middleX, y: sourceStub.y }, { x: middleX, y: targetStub.y }, targetStub, end],
    [start, sourceStub, { x: sourceStub.x, y: middleY }, { x: targetStub.x, y: middleY }, targetStub, end],
    [start, sourceStub, { x: sourceStub.x, y: allBounds.top - 14 }, { x: targetStub.x, y: allBounds.top - 14 }, targetStub, end],
    [start, sourceStub, { x: sourceStub.x, y: allBounds.bottom + 14 }, { x: targetStub.x, y: allBounds.bottom + 14 }, targetStub, end],
    [start, sourceStub, { x: allBounds.left - 14, y: sourceStub.y }, { x: allBounds.left - 14, y: targetStub.y }, targetStub, end],
    [start, sourceStub, { x: allBounds.right + 14, y: sourceStub.y }, { x: allBounds.right + 14, y: targetStub.y }, targetStub, end],
    ...channelOffsets.map((offset) => [start, sourceStub, { x: middleX + offset, y: sourceStub.y }, { x: middleX + offset, y: targetStub.y }, targetStub, end]),
    ...channelOffsets.map((offset) => [start, sourceStub, { x: sourceStub.x, y: middleY + offset }, { x: targetStub.x, y: middleY + offset }, targetStub, end]),
    ...[-2, -1, 1, 2].map((offset) => [start, sourceStub, { x: sourceStub.x, y: allBounds.top - 14 + offset * ROUTE_CHANNEL_STEP }, { x: targetStub.x, y: allBounds.top - 14 + offset * ROUTE_CHANNEL_STEP }, targetStub, end]),
    ...[-2, -1, 1, 2].map((offset) => [start, sourceStub, { x: sourceStub.x, y: allBounds.bottom + 14 + offset * ROUTE_CHANNEL_STEP }, { x: targetStub.x, y: allBounds.bottom + 14 + offset * ROUTE_CHANNEL_STEP }, targetStub, end]),
  ].map(compactPoints);
  return candidates.sort((a, b) => {
    const score = (points: Point[]) => [
      collisionCount(points, hardObstacles),
      collisionCount(points, obstacles),
      sharedLength(points, occupiedRoutes, channel),
      crossingCount(points, occupiedRoutes),
      nearParallelLength(points, occupiedRoutes),
      routeLength(points) + points.length * 8,
    ];
    const scoreA = score(a);
    const scoreB = score(b);
    for (let index = 0; index < scoreA.length; index += 1) {
      if (scoreA[index] !== scoreB[index]) return scoreA[index] - scoreB[index];
    }
    return 0;
  })[0];
}

function layoutFlow(
  primitive: Extract<DetailPrimitive, { kind: "flow" }>,
  diagram: ModuleDetailDiagram,
  baseNodes: DetailNode[],
  movedNodes: DetailNode[],
  options: DetailLayoutOptions,
  occupiedRoutes: OccupiedRoute[] = [],
  forceRoute = false,
): Extract<DetailPrimitive, { kind: "flow" }> {
  const first = primitive.points[0];
  const last = primitive.points.at(-1)!;
  const allowDirectedGap = true;
  const startAnchor = findAnchor(first, baseNodes, primitive.points[1], "start", allowDirectedGap);
  const endAnchor = findAnchor(last, baseNodes, primitive.points.at(-2), "end", allowDirectedGap);
  const startsAtBoundary = samePoint(first, diagram.entryPoint);
  const endsAtBoundary = samePoint(last, diagram.exitPoint);

  const movedById = new Map(movedNodes.map((node) => [node.id, node]));
  const movedStartNode = startAnchor ? movedById.get(startAnchor.node.id) : undefined;
  const movedEndNode = endAnchor ? movedById.get(endAnchor.node.id) : undefined;
  const externalStart = startsAtBoundary && options.entryPoint
    ? options.entryPoint
    : options.junctionPorts?.[pointKey(first)] ?? first;
  const externalEnd = endsAtBoundary && options.exitPoint
    ? options.exitPoint
    : options.junctionPorts?.[pointKey(last)] ?? last;
  const startPortalAnchor = !startAnchor && options.junctionPorts?.[pointKey(first)]
    ? findAnchor(externalStart, movedNodes)
    : undefined;
  const endPortalAnchor = !endAnchor && options.junctionPorts?.[pointKey(last)]
    ? findAnchor(externalEnd, movedNodes)
    : undefined;
  const routeStartNode = movedStartNode ?? startPortalAnchor?.node;
  const routeEndNode = movedEndNode ?? endPortalAnchor?.node;
  const startGeometryChanged = Boolean(startAnchor && movedStartNode
    && !boundsEqual(startAnchor.node.bounds, movedStartNode.bounds));
  const endGeometryChanged = Boolean(endAnchor && movedEndNode
    && !boundsEqual(endAnchor.node.bounds, movedEndNode.bounds));
  const shouldResolveNearestSides = primitive.channel === undefined
    && Boolean(
      movedStartNode && options.adaptivePortNodeIds?.has(movedStartNode.id)
      || movedEndNode && options.adaptivePortNodeIds?.has(movedEndNode.id),
    );
  let resolvedStartSide = startAnchor?.side ?? startPortalAnchor?.side;
  let resolvedEndSide = endAnchor?.side ?? endPortalAnchor?.side;
  if (shouldResolveNearestSides) {
    if (movedStartNode && !options.nodePorts?.[movedStartNode.id]) {
      resolvedStartSide = sideToward(
        movedStartNode.bounds,
        movedEndNode ? boundsCenter(movedEndNode.bounds) : externalEnd,
      );
    }
    if (movedEndNode && !options.nodePorts?.[movedEndNode.id]) {
      resolvedEndSide = sideToward(
        movedEndNode.bounds,
        movedStartNode ? boundsCenter(movedStartNode.bounds) : externalStart,
      );
    }
  }
  const start = movedStartNode && resolvedStartSide
    ? options.nodePorts?.[movedStartNode.id]?.[resolvedStartSide]
      ?? centeredBoundaryPoint(resolvedStartSide, movedStartNode.bounds)
    : externalStart;
  const end = movedEndNode && resolvedEndSide
    ? options.nodePorts?.[movedEndNode.id]?.[resolvedEndSide]
      ?? centeredBoundaryPoint(resolvedEndSide, movedEndNode.bounds)
    : externalEnd;
  const startRouteSide = movedStartNode && resolvedStartSide
    ? options.nodePortDirections?.[movedStartNode.id]?.[resolvedStartSide] ?? resolvedStartSide
    : resolvedStartSide;
  const endRouteSide = movedEndNode && resolvedEndSide
    ? options.nodePortDirections?.[movedEndNode.id]?.[resolvedEndSide] ?? resolvedEndSide
    : resolvedEndSide;
  const points = primitive.points.map((point) => ({ ...point }));
  points[0] = start;
  points[points.length - 1] = end;

  const excluded = new Set([routeStartNode?.id, routeEndNode?.id].filter(Boolean));
  const obstacleNodes = movedNodes.filter((node) => !excluded.has(node.id));
  const hardObstacles = obstacleNodes.map((node) => node.bounds);
  const obstacles = hardObstacles.map((bounds) => padded(bounds, ROUTE_PADDING));
  const interiorPortNodeIds = new Set<string>();
  if (movedStartNode && options.nodePorts?.[movedStartNode.id]?.[resolvedStartSide!]
    && distanceToBoundary(start, movedStartNode.bounds) > ANCHOR_TOLERANCE) {
    interiorPortNodeIds.add(movedStartNode.id);
  }
  if (movedEndNode && options.nodePorts?.[movedEndNode.id]?.[resolvedEndSide!]
    && distanceToBoundary(end, movedEndNode.bounds) > ANCHOR_TOLERANCE) {
    interiorPortNodeIds.add(movedEndNode.id);
  }
  const endpointObstacles = [routeStartNode, routeEndNode]
    .flatMap((node) => node ? [node] : [])
    .filter((node, index, nodes) => nodes.findIndex((candidate) => candidate.id === node.id) === index)
    .filter((node) => !interiorPortNodeIds.has(node.id))
    .map((node) => padded(node.bounds, ROUTE_PADDING));
  const routeObstacles = [...obstacles, ...endpointObstacles];
  const adjusted = compactPoints(points);
  const geometryChanged = !samePoint(start, first) || !samePoint(end, last)
    || startGeometryChanged
    || endGeometryChanged;
  const suppressMarker = options.suppressExitMarker && endsAtBoundary
    || options.suppressExpandedChildMarker && Boolean(movedEndNode && options.nodePorts?.[movedEndNode.id]);
  if (samePoint(start, end)) {
    return { ...primitive, points: [start, end], marker: false };
  }
  if (!forceRoute && !geometryChanged && collisionCount(adjusted, obstacles) === 0) {
    return { ...primitive, points: adjusted, ...(suppressMarker ? { marker: false } : {}) };
  }
  return {
    ...primitive,
    points: orthogonalRoute(start, end, startRouteSide, endRouteSide, routeObstacles, hardObstacles, occupiedRoutes, primitive.channel),
    ...(suppressMarker ? { marker: false } : {}),
  };
}

export function layoutDetailDiagram(
  diagram: ModuleDetailDiagram,
  offsets: DetailOffsetMap = {},
  options: DetailLayoutOptions = {},
): ModuleDetailDiagram {
  const baseNodes = listDetailNodes(diagram);
  const adaptivePortNodeIds = new Set(Object.entries(offsets)
    .filter(([, offset]) => Math.abs(offset.x) >= 0.01 || Math.abs(offset.y) >= 0.01)
    .map(([id]) => id));
  const layoutOptions = { ...options, adaptivePortNodeIds };
  const movedPrimitives = diagram.primitives.map((primitive, index) => {
    const id = detailNodeId(index);
    const resized = resizePrimitive(primitive, options.nodeBounds?.[id]);
    const moved = translatePrimitive(resized, offsets[id] ?? { x: 0, y: 0 });
    if (moved.kind === "text" && options.bottomTextY !== undefined
      && options.bottomTextFromY !== undefined && moved.y >= options.bottomTextFromY) {
      return { ...moved, y: options.bottomTextY };
    }
    return moved;
  });
  const movedDiagram = { ...diagram, primitives: movedPrimitives };
  const movedNodes = listDetailNodes(movedDiagram);
  const preliminary = movedPrimitives.map((primitive) => primitive.kind === "flow"
    ? layoutFlow(primitive, diagram, baseNodes, movedNodes, layoutOptions)
    : primitive);
  const stableRoutes: OccupiedRoute[] = [];
  const dynamicIndexes = new Set<number>();
  preliminary.forEach((primitive, index) => {
    const original = movedPrimitives[index];
    if (primitive.kind !== "flow" || original.kind !== "flow") return;
    const originalPoints = compactPoints(original.points);
    const stable = primitive.points.length === originalPoints.length
      && primitive.points.every((point, pointIndex) => samePoint(point, originalPoints[pointIndex]));
    if (stable) stableRoutes.push({ points: primitive.points, channel: primitive.channel });
    else dynamicIndexes.add(index);
  });
  const occupiedRoutes = [...stableRoutes];
  const routedPrimitives = preliminary.map((primitive, index) => {
    if (primitive.kind !== "flow" || !dynamicIndexes.has(index)) return primitive;
    const original = movedPrimitives[index];
    if (original.kind !== "flow") return primitive;
    const routed = layoutFlow(original, diagram, baseNodes, movedNodes, layoutOptions, occupiedRoutes, true);
    occupiedRoutes.push({ points: routed.points, channel: routed.channel });
    return routed;
  });
  return {
    ...movedDiagram,
    entryPoint: options.entryPoint ?? diagram.entryPoint,
    exitPoint: options.exitPoint ?? diagram.exitPoint,
    primitives: routedPrimitives,
  };
}

function naturalDetailBounds(kind: NodeDetailKind, x = 0, y = 0): Bounds {
  return { x, y, ...EXPANDED_DETAIL_SIZES[kind] };
}

function shiftedBounds(bounds: Bounds, x: number, y: number): Bounds {
  return { ...bounds, x: bounds.x + x, y: bounds.y + y };
}

function expandedJunctionPorts(
  diagram: ModuleDetailDiagram,
  active: DetailNode,
  entryPoint: Point,
  exitPoint: Point,
): Record<string, Point> {
  const nodes = listDetailNodes(diagram);
  const flows = diagram.primitives.filter((primitive) => primitive.kind === "flow");
  const endpointCounts = new Map<string, number>();
  for (const flow of flows) {
    for (const point of [flow.points[0], flow.points.at(-1)!]) {
      endpointCounts.set(pointKey(point), (endpointCounts.get(pointKey(point)) ?? 0) + 1);
    }
  }

  const ports: Record<string, Point> = {};
  const portalForSide = (side: Anchor["side"]) => side === "left" ? entryPoint : exitPoint;
  for (const flow of flows) {
    const first = flow.points[0];
    const last = flow.points.at(-1)!;
    const allowDirectedGap = true;
    const startAnchor = findAnchor(first, nodes, flow.points[1], "start", allowDirectedGap);
    const endAnchor = findAnchor(last, nodes, flow.points.at(-2), "end", allowDirectedGap);
    if (startAnchor?.node.id === active.id && !endAnchor && (endpointCounts.get(pointKey(last)) ?? 0) > 1) {
      ports[pointKey(last)] = portalForSide(startAnchor.side);
    }
    if (endAnchor?.node.id === active.id && !startAnchor && (endpointCounts.get(pointKey(first)) ?? 0) > 1) {
      ports[pointKey(first)] = portalForSide(endAnchor.side);
    }
  }
  return ports;
}

interface InlineAtomicExit {
  point: Point;
  side: PortSide;
}

function pointInsideOrOnBounds(point: Point, bounds: Bounds): boolean {
  return point.x >= bounds.x - 0.01
    && point.x <= bounds.x + bounds.width + 0.01
    && point.y >= bounds.y - 0.01
    && point.y <= bounds.y + bounds.height + 0.01;
}

function inlineAtomicExit(level: InlineDetailLevel): InlineAtomicExit | undefined {
  let cursor = level.diagram.exitPoint;
  const visited = new Set<number>();
  for (let depth = 0; depth <= level.diagram.primitives.length; depth += 1) {
    const candidates = level.diagram.primitives.flatMap((primitive, index) => (
      primitive.kind === "flow" && !visited.has(index) && samePoint(primitive.points.at(-1)!, cursor)
        ? [{ primitive, index }]
        : []
    ));
    if (candidates.length !== 1) return undefined;
    const { primitive, index } = candidates[0];
    visited.add(index);
    const source = primitive.points[0];
    const anchor = findAnchor(source, level.nodes, primitive.points[1], "start", true);
    if (anchor) {
      if (level.expandedChild?.node.id === anchor.node.id) {
        return inlineAtomicExit(level.expandedChild.level);
      }
      return { point: { ...source }, side: anchor.side };
    }
    if (level.expandedChild && pointInsideOrOnBounds(source, level.expandedChild.node.bounds)) {
      return inlineAtomicExit(level.expandedChild.level);
    }
    cursor = source;
  }
  return undefined;
}

function automaticExpandedBounds(
  kind: NodeDetailKind,
  branch: DetailExpansionBranch,
): { size: Pick<Bounds, "width" | "height">; overrides: DetailNodeBoundsMap } | undefined {
  const baseBounds = naturalDetailBounds(kind);
  const nodes = listDetailNodes(buildModuleDetail(kind, baseBounds));
  const active = nodes.find((node) => node.id === branch.childId && node.nestedKind);
  if (!active?.nestedKind) return undefined;

  const childSize = expandedDetailSize(active.nestedKind, branch.child);
  const expanded = {
    x: active.bounds.x,
    y: Math.max(baseBounds.y + 58, active.bounds.y),
    width: childSize.width,
    height: childSize.height,
  };
  const overrides: DetailNodeBoundsMap = { [active.id]: expanded };
  const activeCenterX = active.bounds.x + active.bounds.width / 2;
  const activeBottom = active.bounds.y + active.bounds.height;
  const growthX = Math.max(0, expanded.width - active.bounds.width) + INLINE_EXPANSION_GAP;
  const growthY = Math.max(0, expanded.height - active.bounds.height) + INLINE_EXPANSION_GAP;

  for (const node of nodes) {
    if (node.id === active.id) continue;
    const centerX = node.bounds.x + node.bounds.width / 2;
    let next = { ...node.bounds };
    if (centerX > activeCenterX + Math.max(8, active.bounds.width * 0.25)) {
      next.x += growthX;
    } else if (node.bounds.x + node.bounds.width <= active.bounds.x) {
      // Upstream peers keep their original lane and continue into the expanded left boundary.
    } else if (node.bounds.y >= activeBottom - 4) {
      const horizontalOverlap = node.bounds.x < expanded.x + expanded.width + INLINE_EXPANSION_GAP
        && node.bounds.x + node.bounds.width > expanded.x - INLINE_EXPANSION_GAP;
      if (horizontalOverlap) next.y += growthY;
    } else {
      const overlaps = next.x < expanded.x + expanded.width + INLINE_EXPANSION_GAP
        && next.x + next.width > expanded.x - INLINE_EXPANSION_GAP
        && next.y < expanded.y + expanded.height + INLINE_EXPANSION_GAP
        && next.y + next.height > expanded.y - INLINE_EXPANSION_GAP;
      if (overlaps) next.x += growthX;
    }
    if (!boundsEqual(next, node.bounds)) overrides[node.id] = next;
  }

  const finalBounds = nodes.map((node) => overrides[node.id] ?? node.bounds);
  const right = Math.max(baseBounds.width, ...finalBounds.map((bounds) => bounds.x + bounds.width + INLINE_RIGHT_PADDING));
  const bottom = Math.max(baseBounds.height, ...finalBounds.map((bounds) => bounds.y + bounds.height + INLINE_BOTTOM_PADDING));
  return { size: { width: right, height: bottom }, overrides };
}

export function expandedDetailSize(
  kind: NodeDetailKind,
  branch?: DetailExpansionBranch,
): Pick<Bounds, "width" | "height"> {
  if (!branch) return EXPANDED_DETAIL_SIZES[kind];
  return automaticExpandedBounds(kind, branch)?.size ?? EXPANDED_DETAIL_SIZES[kind];
}

export function detailLevelKey(rootId: string, levelPath: readonly string[] = []): string {
  return [rootId, ...levelPath].join("/");
}

export function buildInlineDetailLayout(
  kind: NodeDetailKind,
  bounds: Bounds,
  branch: DetailExpansionBranch | undefined,
  layouts: DetailLayoutMap,
  rootId: string,
  levelPath: readonly string[] = [],
  routingMode: HierarchyRoutingMode = "atomic-bottom-up",
): InlineDetailLevel {
  const levelKey = detailLevelKey(rootId, levelPath);
  const natural = naturalDetailBounds(kind, bounds.x, bounds.y);
  const baseDiagram = buildModuleDetail(kind, natural);
  const automatic = branch ? automaticExpandedBounds(kind, branch) : undefined;
  const translatedOverrides = Object.fromEntries(Object.entries(automatic?.overrides ?? {}).map(([id, value]) => [
    id,
    shiftedBounds(value, bounds.x, bounds.y),
  ]));
  const entryPoint = routingMode === "atomic-bottom-up"
    ? { x: bounds.x, y: baseDiagram.entryPoint.y }
    : { x: bounds.x, y: bounds.y + bounds.height / 2 };
  const exitPoint = routingMode === "atomic-bottom-up"
    ? { x: bounds.x + bounds.width, y: baseDiagram.exitPoint.y }
    : { x: bounds.x + bounds.width, y: bounds.y + bounds.height / 2 };
  const commonOptions: DetailLayoutOptions = {
    nodeBounds: translatedOverrides,
    entryPoint,
    exitPoint,
    bottomTextFromY: natural.y + natural.height - 52,
    bottomTextY: bounds.y + bounds.height - 28,
    suppressExitMarker: routingMode === "atomic-bottom-up",
  };
  const preliminaryDiagram = layoutDetailDiagram(baseDiagram, layouts[levelKey] ?? {}, commonOptions);
  const preliminaryNodes = listDetailNodes(preliminaryDiagram);
  const active = branch
    ? preliminaryNodes.find((node) => node.id === branch.childId && node.nestedKind)
    : undefined;
  if (!active?.nestedKind) {
    return {
      kind,
      bounds,
      diagram: preliminaryDiagram,
      nodes: preliminaryNodes,
      levelKey,
      routingMode,
    };
  }
  const childLevel = buildInlineDetailLayout(
    active.nestedKind,
    active.bounds,
    branch?.child,
    layouts,
    rootId,
    [...levelPath, active.id],
    routingMode,
  );
  const childAtomicExit = routingMode === "atomic-bottom-up" ? inlineAtomicExit(childLevel) : undefined;
  const baseActive = listDetailNodes(baseDiagram).find((node) => node.id === active.id);
  const junctionPorts = baseActive
    ? expandedJunctionPorts(
      baseDiagram,
      baseActive,
      childLevel.diagram.entryPoint,
      childAtomicExit?.point ?? childLevel.diagram.exitPoint,
    )
    : {};
  if (routingMode === "recursive") {
    const diagram = layoutDetailDiagram(baseDiagram, layouts[levelKey] ?? {}, {
      ...commonOptions,
      junctionPorts,
    });
    return {
      kind,
      bounds,
      diagram,
      nodes: listDetailNodes(diagram),
      levelKey,
      routingMode,
      expandedChild: { node: active, level: childLevel },
    };
  }

  const diagram = layoutDetailDiagram(baseDiagram, layouts[levelKey] ?? {}, {
    ...commonOptions,
    junctionPorts,
    nodePorts: {
      [active.id]: {
        left: childLevel.diagram.entryPoint,
        right: childAtomicExit?.point ?? childLevel.diagram.exitPoint,
      },
    },
    nodePortDirections: {
      [active.id]: {
        right: childAtomicExit?.side ?? "right",
      },
    },
    suppressExpandedChildMarker: true,
  });
  const nodes = listDetailNodes(diagram);
  const finalActive = nodes.find((node) => node.id === active.id) ?? active;
  return {
    kind,
    bounds,
    diagram,
    nodes,
    levelKey,
    routingMode,
    expandedChild: { node: finalActive, level: childLevel },
  };
}

export function findInlineDetailLevel(
  root: InlineDetailLevel,
  levelPath: readonly string[],
): InlineDetailLevel | undefined {
  let level: InlineDetailLevel | undefined = root;
  for (const childId of levelPath) {
    if (level?.expandedChild?.node.id !== childId) return undefined;
    level = level.expandedChild.level;
  }
  return level;
}

export function clampDetailOffset(parentBounds: Bounds, childBounds: Bounds, offset: Point): Point {
  const left = parentBounds.x + 12;
  const right = parentBounds.x + parentBounds.width - 12;
  const top = parentBounds.y + 62;
  const bottom = parentBounds.y + parentBounds.height - 36;
  return {
    x: Math.min(right - childBounds.x - childBounds.width, Math.max(left - childBounds.x, offset.x)),
    y: Math.min(bottom - childBounds.y - childBounds.height, Math.max(top - childBounds.y, offset.y)),
  };
}
