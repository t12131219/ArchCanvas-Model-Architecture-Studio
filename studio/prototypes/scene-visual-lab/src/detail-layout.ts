import { buildModuleDetail, EXPANDED_DETAIL_SIZES } from "./module-details";
import type { DetailPrimitive, ModuleDetailDiagram } from "./module-details";
import type { Bounds, HierarchyRoutingMode, NodeDetailKind, Point, PortSide } from "./types";

type DetailShapePrimitive = Extract<DetailPrimitive, { kind: "rect" | "circle" | "matrix" }>;

export type DetailOffsetMap = Record<string, Point>;
export type DetailLayoutMap = Record<string, DetailOffsetMap>;
export type DetailNodeBoundsMap = Record<string, Bounds>;

export interface DetailExpansionBranch {
  children?: Record<string, DetailExpansionBranch>;
  /** Legacy single-path representation accepted when reading older snapshots. */
  childId?: string;
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
  expandedChildren?: Array<{
    node: DetailNode;
    level: InlineDetailLevel;
  }>;
  /** Compatibility alias for callers that only inspect a single expansion. */
  expandedChild?: {
    node: DetailNode;
    level: InlineDetailLevel;
  };
}

const EMPTY_DETAIL_EXPANSION: DetailExpansionBranch = { children: {} };

export function detailExpansionChildren(
  branch: DetailExpansionBranch | undefined,
): Array<[string, DetailExpansionBranch]> {
  if (!branch) return [];
  if (branch.children) return Object.entries(branch.children);
  return branch.childId ? [[branch.childId, branch.child ?? EMPTY_DETAIL_EXPANSION]] : [];
}

export function inlineExpandedChildren(level: InlineDetailLevel): NonNullable<InlineDetailLevel["expandedChildren"]> {
  return level.expandedChildren ?? (level.expandedChild ? [level.expandedChild] : []);
}

export function detailExpansionPath(...childIds: string[]): DetailExpansionBranch {
  return childIds.reduceRight<DetailExpansionBranch>(
    (child, childId) => ({ children: { [childId]: child } }),
    EMPTY_DETAIL_EXPANSION,
  );
}

export function toggleDetailExpansionAtPath(
  branch: DetailExpansionBranch | undefined,
  levelPath: readonly string[],
  childId: string,
): DetailExpansionBranch {
  const children = Object.fromEntries(detailExpansionChildren(branch));
  if (!levelPath.length) {
    if (children[childId]) delete children[childId];
    else children[childId] = { children: {} };
    return { children };
  }
  const nested = children[levelPath[0]];
  if (!nested) return { children };
  children[levelPath[0]] = toggleDetailExpansionAtPath(nested, levelPath.slice(1), childId);
  return { children };
}

export function fullyExpandedDetailTree(
  kind: NodeDetailKind,
  ancestors: readonly NodeDetailKind[] = [],
): DetailExpansionBranch {
  if (ancestors.includes(kind) || ancestors.length >= 20) return EMPTY_DETAIL_EXPANSION;
  const bounds = naturalDetailBounds(kind);
  const children = Object.fromEntries(listDetailNodes(buildModuleDetail(kind, bounds)).flatMap((node) => (
    node.nestedKind
      ? [[node.id, fullyExpandedDetailTree(node.nestedKind, [...ancestors, kind])]]
      : []
  )));
  return { children };
}

interface DetailLayoutOptions {
  nodeBounds?: DetailNodeBoundsMap;
  entryPoint?: Point;
  exitPoint?: Point;
  bottomTextFromY?: number;
  bottomTextY?: number;
  nodePorts?: Record<string, Partial<Record<PortSide, Point>>>;
  nodePortDirections?: Record<string, Partial<Record<PortSide, PortSide>>>;
  semanticNodePorts?: Record<string, Record<string, { point: Point; side: PortSide }>>;
  distributedEndpointPorts?: Record<string, Point>;
  junctionPorts?: Record<string, Point>;
  suppressExitMarker?: boolean;
  suppressExpandedChildMarker?: boolean;
  adaptivePortNodeIds?: ReadonlySet<string>;
  routeBounds?: Bounds;
  extraObstacles?: Bounds[];
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
const BOUNDARY_EPSILON = 0.01;
const DIRECTED_ANCHOR_GAP = 72;
const ROUTE_PADDING = 7;
const INLINE_EXPANSION_GAP = 34;
const INLINE_RIGHT_PADDING = 32;
const INLINE_BOTTOM_PADDING = 36;
const SEMANTIC_GROUP_BOTTOM_PADDING = 18;
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

  if (["transformer-encoder", "transformer-decoder", "tensor2tensor-encoder", "tensor2tensor-decoder"].includes(parentKind)) {
    if (/^(self-attention|masked self-attn|cross-attention)$/i.test(label)) return "attention";
    if (/^add\s*&\s*norm$/i.test(label)) return "add-norm";
    if (/^feed-forward$/i.test(label)) return "feedforward";
    return undefined;
  }
  if (parentKind === "sinusoidal-embedding") return undefined;

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
    if (Math.abs(bounds.width - bounds.height) > 0.01) {
      return {
        kind: "rect",
        x: bounds.x,
        y: bounds.y,
        width: bounds.width,
        height: bounds.height,
        rx: 4,
        label: primitive.label,
        tone: primitive.tone,
      };
    }
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

function flowEndpointKey(primitiveIndex: number, endpoint: "start" | "end"): string {
  return `${primitiveIndex}:${endpoint}`;
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

function distributedBoundaryPoint(
  node: DetailNode,
  side: Anchor["side"],
  slot: number,
  slotCount: number,
): Point {
  const { bounds } = node;
  if (node.primitive.kind === "circle") {
    const center = boundsCenter(bounds);
    const radius = Math.min(bounds.width, bounds.height) / 2;
    const centerAngle = {
      left: Math.PI,
      right: 0,
      top: -Math.PI / 2,
      bottom: Math.PI / 2,
    }[side];
    const spread = Math.PI * 35 / 180;
    const offset = slotCount === 1
      ? 0
      : -spread + slot * spread * 2 / (slotCount - 1);
    return {
      x: center.x + Math.cos(centerAngle + offset) * radius,
      y: center.y + Math.sin(centerAngle + offset) * radius,
    };
  }
  const fraction = (slot + 1) / (slotCount + 1);
  if (side === "left") return { x: bounds.x, y: bounds.y + bounds.height * fraction };
  if (side === "right") return { x: bounds.x + bounds.width, y: bounds.y + bounds.height * fraction };
  if (side === "top") return { x: bounds.x + bounds.width * fraction, y: bounds.y };
  return { x: bounds.x + bounds.width * fraction, y: bounds.y + bounds.height };
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

function routeBoundaryOverflow(points: Point[], bounds: Bounds | undefined): number {
  if (!bounds) return 0;
  const right = bounds.x + bounds.width;
  const bottom = bounds.y + bounds.height;
  return points.reduce((sum, point) => sum
    + Math.max(0, bounds.x - point.x)
    + Math.max(0, point.x - right)
    + Math.max(0, bounds.y - point.y)
    + Math.max(0, point.y - bottom), 0);
}

function routeLength(points: Point[]): number {
  let length = 0;
  for (let index = 1; index < points.length; index += 1) {
    length += Math.abs(points[index].x - points[index - 1].x) + Math.abs(points[index].y - points[index - 1].y);
  }
  return length;
}

function routeBacktrackLength(points: Point[]): number {
  let length = 0;
  for (let index = 2; index < points.length; index += 1) {
    const first = points[index - 2];
    const middle = points[index - 1];
    const last = points[index];
    if (first.y === middle.y && middle.y === last.y) {
      const incoming = middle.x - first.x;
      const outgoing = last.x - middle.x;
      if (incoming * outgoing < 0) length += Math.min(Math.abs(incoming), Math.abs(outgoing));
    } else if (first.x === middle.x && middle.x === last.x) {
      const incoming = middle.y - first.y;
      const outgoing = last.y - middle.y;
      if (incoming * outgoing < 0) length += Math.min(Math.abs(incoming), Math.abs(outgoing));
    }
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
  routeBounds?: Bounds,
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
  const boundaryChannels = routeBounds ? {
    left: routeBounds.x + 12,
    right: routeBounds.x + routeBounds.width - 12,
    top: routeBounds.y + 12,
    bottom: routeBounds.y + routeBounds.height - 12,
  } : undefined;
  const withinHorizontalBounds = (x: number) => !routeBounds
    || x >= routeBounds.x && x <= routeBounds.x + routeBounds.width;
  const withinVerticalBounds = (y: number) => !routeBounds
    || y >= routeBounds.y && y <= routeBounds.y + routeBounds.height;
  const obstacleXLanes = [...new Set(obstacles.flatMap((bounds) => [bounds.x, bounds.x + bounds.width]))]
    .filter(withinHorizontalBounds);
  const obstacleYLanes = [...new Set(obstacles.flatMap((bounds) => [bounds.y, bounds.y + bounds.height]))]
    .filter(withinVerticalBounds);
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
    ...(boundaryChannels ? [
      [start, sourceStub, { x: sourceStub.x, y: boundaryChannels.top }, { x: targetStub.x, y: boundaryChannels.top }, targetStub, end],
      [start, sourceStub, { x: sourceStub.x, y: boundaryChannels.bottom }, { x: targetStub.x, y: boundaryChannels.bottom }, targetStub, end],
      [start, sourceStub, { x: boundaryChannels.left, y: sourceStub.y }, { x: boundaryChannels.left, y: targetStub.y }, targetStub, end],
      [start, sourceStub, { x: boundaryChannels.right, y: sourceStub.y }, { x: boundaryChannels.right, y: targetStub.y }, targetStub, end],
    ] : []),
    ...obstacleXLanes.map((x) => [
      start,
      sourceStub,
      { x, y: sourceStub.y },
      { x, y: targetStub.y },
      targetStub,
      end,
    ]),
    ...obstacleYLanes.map((y) => [
      start,
      sourceStub,
      { x: sourceStub.x, y },
      { x: targetStub.x, y },
      targetStub,
      end,
    ]),
  ].map(compactPoints);
  return candidates.sort((a, b) => {
    const score = (points: Point[]) => [
      routeBoundaryOverflow(points, routeBounds),
      collisionCount(points, hardObstacles),
      collisionCount(points, obstacles),
      routeBacktrackLength(points),
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
  primitiveIndex: number,
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
  const isSharedEndpoint = (point: Point) => diagram.primitives.filter((candidate) => (
    candidate.kind === "flow"
    && (samePoint(candidate.points[0], point) || samePoint(candidate.points.at(-1)!, point))
  )).length > 1;
  const candidateStartAnchor = findAnchor(first, baseNodes, primitive.points[1], "start", allowDirectedGap);
  const candidateEndAnchor = findAnchor(last, baseNodes, primitive.points.at(-2), "end", allowDirectedGap);
  const startAnchor = isSharedEndpoint(first)
    && !options.nodePorts?.[candidateStartAnchor?.node.id ?? ""]
    && (!candidateStartAnchor || distanceToBoundary(first, candidateStartAnchor.node.bounds) > BOUNDARY_EPSILON)
    ? undefined
    : candidateStartAnchor;
  const endAnchor = isSharedEndpoint(last)
    && !options.nodePorts?.[candidateEndAnchor?.node.id ?? ""]
    && (!candidateEndAnchor || distanceToBoundary(last, candidateEndAnchor.node.bounds) > BOUNDARY_EPSILON)
    ? undefined
    : candidateEndAnchor;
  const startsAtBoundary = samePoint(first, diagram.entryPoint);
  const endsAtBoundary = samePoint(last, diagram.exitPoint);

  const movedById = new Map(movedNodes.map((node) => [node.id, node]));
  const movedStartNode = startAnchor ? movedById.get(startAnchor.node.id) : undefined;
  const movedEndNode = endAnchor ? movedById.get(endAnchor.node.id) : undefined;
  const semanticEndPort = movedEndNode && primitive.targetPortRole
    ? options.semanticNodePorts?.[movedEndNode.id]?.[primitive.targetPortRole]
    : undefined;
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
  const shouldResolveNearestSides = Boolean(
    movedStartNode && options.adaptivePortNodeIds?.has(movedStartNode.id)
    || movedEndNode && options.adaptivePortNodeIds?.has(movedEndNode.id),
  );
  let resolvedStartSide = startAnchor?.side ?? startPortalAnchor?.side;
  let resolvedEndSide = semanticEndPort?.side ?? endAnchor?.side ?? endPortalAnchor?.side;
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
    ? options.distributedEndpointPorts?.[flowEndpointKey(primitiveIndex, "start")]
      ?? options.nodePorts?.[movedStartNode.id]?.[resolvedStartSide]
      ?? centeredBoundaryPoint(resolvedStartSide, movedStartNode.bounds)
    : externalStart;
  const end = movedEndNode && resolvedEndSide
    ? options.distributedEndpointPorts?.[flowEndpointKey(primitiveIndex, "end")]
      ?? semanticEndPort?.point
      ?? options.nodePorts?.[movedEndNode.id]?.[resolvedEndSide]
      ?? centeredBoundaryPoint(resolvedEndSide, movedEndNode.bounds)
    : externalEnd;
  const startRouteSide = movedStartNode && resolvedStartSide
    ? options.nodePortDirections?.[movedStartNode.id]?.[resolvedStartSide] ?? resolvedStartSide
    : resolvedStartSide;
  const endRouteSide = movedEndNode && resolvedEndSide
    ? semanticEndPort?.side
      ?? options.nodePortDirections?.[movedEndNode.id]?.[resolvedEndSide]
      ?? resolvedEndSide
    : resolvedEndSide;
  const points = primitive.points.map((point) => ({ ...point }));
  points[0] = start;
  points[points.length - 1] = end;

  const excluded = new Set([routeStartNode?.id, routeEndNode?.id].filter(Boolean));
  const obstacleNodes = movedNodes.filter((node) => !excluded.has(node.id));
  const endpointTouches = (bounds: Bounds) => (
    pointInsideOrOnBounds(start, bounds)
    || pointInsideOrOnBounds(end, bounds)
    || distanceToBoundary(start, bounds) <= ANCHOR_TOLERANCE
    || distanceToBoundary(end, bounds) <= ANCHOR_TOLERANCE
  );
  const extraObstacles = (options.extraObstacles ?? []).filter((bounds) => !endpointTouches(bounds));
  const hardObstacles = [...obstacleNodes.map((node) => node.bounds), ...extraObstacles];
  const obstacles = hardObstacles.map((bounds) => padded(bounds, ROUTE_PADDING));
  const interiorPortNodeIds = new Set<string>();
  if (movedStartNode && options.nodePorts?.[movedStartNode.id]?.[resolvedStartSide!]
    && distanceToBoundary(start, movedStartNode.bounds) > ANCHOR_TOLERANCE) {
    interiorPortNodeIds.add(movedStartNode.id);
  }
  if (movedEndNode && (semanticEndPort || options.nodePorts?.[movedEndNode.id]?.[resolvedEndSide!])
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
    || options.suppressExpandedChildMarker && Boolean(
      movedEndNode && options.nodePorts?.[movedEndNode.id] && !semanticEndPort,
    );
  if (samePoint(start, end)) {
    return { ...primitive, points: [start, end], marker: false };
  }
  if (!forceRoute && !geometryChanged && collisionCount(adjusted, obstacles) === 0) {
    return { ...primitive, points: adjusted, ...(suppressMarker ? { marker: false } : {}) };
  }
  return {
    ...primitive,
    points: orthogonalRoute(
      start,
      end,
      startRouteSide,
      endRouteSide,
      routeObstacles,
      hardObstacles,
      occupiedRoutes,
      primitive.channel,
      options.routeBounds,
    ),
    ...(suppressMarker ? { marker: false } : {}),
  };
}

interface DynamicEndpointCandidate {
  key: string;
  node: DetailNode;
  side: Anchor["side"];
  point: Point;
  opposite: Point;
}

function distributedDynamicEndpointPorts(
  diagram: ModuleDetailDiagram,
  preliminary: DetailPrimitive[],
  baseNodes: DetailNode[],
  movedNodes: DetailNode[],
  options: DetailLayoutOptions,
): Record<string, Point> {
  const movedById = new Map(movedNodes.map((node) => [node.id, node]));
  const endpointUseCount = new Map<string, number>();
  for (const candidate of diagram.primitives) {
    if (candidate.kind !== "flow") continue;
    for (const point of [candidate.points[0], candidate.points.at(-1)!]) {
      const key = pointKey(point);
      endpointUseCount.set(key, (endpointUseCount.get(key) ?? 0) + 1);
    }
  }

  const groups = new Map<string, DynamicEndpointCandidate[]>();
  const addCandidate = (
    primitiveIndex: number,
    endpoint: "start" | "end",
    anchor: Anchor | undefined,
    point: Point,
    opposite: Point,
    originalPoint: Point,
    targetPortRole?: string,
  ) => {
    if (!anchor) return;
    const sharedFreeJunction = (endpointUseCount.get(pointKey(originalPoint)) ?? 0) > 1
      && distanceToBoundary(originalPoint, anchor.node.bounds) > BOUNDARY_EPSILON;
    if (sharedFreeJunction) return;
    const node = movedById.get(anchor.node.id);
    if (!node) return;
    const side = anchorSide(point, node.bounds);
    if (options.nodePorts?.[node.id]?.[side]) return;
    if (endpoint === "end" && targetPortRole && options.semanticNodePorts?.[node.id]?.[targetPortRole]) return;
    const groupKey = `${node.id}:${side}`;
    const group = groups.get(groupKey) ?? [];
    group.push({
      key: flowEndpointKey(primitiveIndex, endpoint),
      node,
      side,
      point,
      opposite,
    });
    groups.set(groupKey, group);
  };

  diagram.primitives.forEach((primitive, primitiveIndex) => {
    const routed = preliminary[primitiveIndex];
    if (primitive.kind !== "flow" || routed.kind !== "flow") return;
    const startAnchor = findAnchor(primitive.points[0], baseNodes, primitive.points[1], "start", true);
    const endAnchor = findAnchor(primitive.points.at(-1)!, baseNodes, primitive.points.at(-2), "end", true);
    addCandidate(
      primitiveIndex,
      "start",
      startAnchor,
      routed.points[0],
      routed.points.at(-1)!,
      primitive.points[0],
    );
    addCandidate(
      primitiveIndex,
      "end",
      endAnchor,
      routed.points.at(-1)!,
      routed.points[0],
      primitive.points.at(-1)!,
      primitive.targetPortRole,
    );
  });

  const ports: Record<string, Point> = {};
  for (const candidates of groups.values()) {
    if (candidates.length < 2 || !candidates.some((candidate, index) => (
      candidates.slice(index + 1).some((other) => samePoint(candidate.point, other.point))
    ))) continue;
    const horizontal = candidates[0].side === "top" || candidates[0].side === "bottom";
    candidates.sort((first, second) => (
      horizontal
        ? first.opposite.x - second.opposite.x
        : first.opposite.y - second.opposite.y
    ) || first.key.localeCompare(second.key));
    candidates.forEach((candidate, slot) => {
      ports[candidate.key] = distributedBoundaryPoint(
        candidate.node,
        candidate.side,
        slot,
        candidates.length,
      );
    });
  }
  return ports;
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
  const initialLayoutOptions = { ...options, adaptivePortNodeIds };
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
  const semanticInputPorts = diagram.semanticInputPorts && Object.fromEntries(Object.entries(diagram.semanticInputPorts).map(([role, port]) => {
    const anchor = findAnchor(port.point, baseNodes);
    const movedNode = anchor ? movedNodes.find((node) => node.id === anchor.node.id) : undefined;
    return [role, movedNode ? {
      point: centeredBoundaryPoint(anchor!.side, movedNode.bounds),
      side: anchor!.side,
    } : port];
  }));
  const initialPreliminary = movedPrimitives.map((primitive, index) => primitive.kind === "flow"
    ? layoutFlow(primitive, index, diagram, baseNodes, movedNodes, initialLayoutOptions)
    : primitive);
  const distributedEndpointPorts = distributedDynamicEndpointPorts(
    diagram,
    initialPreliminary,
    baseNodes,
    movedNodes,
    initialLayoutOptions,
  );
  const layoutOptions = { ...initialLayoutOptions, distributedEndpointPorts };
  const preliminary = Object.keys(distributedEndpointPorts).length
    ? movedPrimitives.map((primitive, index) => primitive.kind === "flow"
      ? layoutFlow(primitive, index, diagram, baseNodes, movedNodes, layoutOptions)
      : primitive)
    : initialPreliminary;
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
    const routed = layoutFlow(original, index, diagram, baseNodes, movedNodes, layoutOptions, occupiedRoutes, true);
    occupiedRoutes.push({ points: routed.points, channel: routed.channel });
    return routed;
  });
  return {
    ...movedDiagram,
    semanticInputPorts,
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

interface ContainmentFrameCandidate extends Bounds {
  index: number;
  area: number;
}

function containmentFrameCandidate(
  diagram: ModuleDetailDiagram,
  referenceBounds: Bounds,
): ContainmentFrameCandidate | undefined {
  return diagram.primitives.flatMap((primitive, index) => {
    if (primitive.kind !== "rect"
      || primitive.variant !== "frame"
      || (primitive.frameRole ?? "containment") !== "containment") return [];
    const frameBounds = {
      x: primitive.x,
      y: primitive.y,
      width: primitive.width,
      height: primitive.height,
    };
    const frameRight = frameBounds.x + frameBounds.width;
    const frameBottom = frameBounds.y + frameBounds.height;
    if (frameBounds.x < referenceBounds.x - 0.01
      || frameBounds.y < referenceBounds.y - 0.01
      || frameRight > referenceBounds.x + referenceBounds.width + 0.01
      || frameBottom > referenceBounds.y + referenceBounds.height + 0.01) return [];
    return [{
      index,
      ...frameBounds,
      area: primitive.width * primitive.height,
    }];
  }).sort((first, second) => second.area - first.area)[0];
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

export interface InlineAtomicEntry {
  point: Point;
  side: PortSide;
}

function pointInsideOrOnBounds(point: Point, bounds: Bounds): boolean {
  return point.x >= bounds.x - 0.01
    && point.x <= bounds.x + bounds.width + 0.01
    && point.y >= bounds.y - 0.01
    && point.y <= bounds.y + bounds.height + 0.01;
}

function boundsInsideOrOnBounds(inner: Bounds, outer: Bounds): boolean {
  return pointInsideOrOnBounds({ x: inner.x, y: inner.y }, outer)
    && pointInsideOrOnBounds({ x: inner.x + inner.width, y: inner.y + inner.height }, outer);
}

function layoutSemanticGroupFrames(
  baseDiagram: ModuleDetailDiagram,
  diagram: ModuleDetailDiagram,
): ModuleDetailDiagram {
  const baseNodes = listDetailNodes(baseDiagram);
  let primitives = diagram.primitives;

  for (const [frameIndex, primitive] of baseDiagram.primitives.entries()) {
    if (primitive.kind !== "rect"
      || primitive.variant !== "frame"
      || primitive.frameRole !== "semantic-group") continue;
    const originalFrame: Bounds = {
      x: primitive.x,
      y: primitive.y,
      width: primitive.width,
      height: primitive.height,
    };
    const members = baseNodes.filter((node) => boundsInsideOrOnBounds(node.bounds, originalFrame));
    if (!members.length) continue;
    const movedMembers = members.map((member) => {
      const moved = primitives[member.primitiveIndex];
      return moved.kind === "rect" || moved.kind === "circle" || moved.kind === "matrix"
        ? primitiveBounds(moved)
        : member.bounds;
    });
    const baseLeft = Math.min(...members.map((member) => member.bounds.x));
    const baseTop = Math.min(...members.map((member) => member.bounds.y));
    const baseRight = Math.max(...members.map((member) => member.bounds.x + member.bounds.width));
    const baseBottom = Math.max(...members.map((member) => member.bounds.y + member.bounds.height));
    const inFrameFlowBottom = Math.max(baseBottom, ...baseDiagram.primitives.flatMap((candidate) => (
      candidate.kind === "flow"
        ? candidate.points
          .filter((point) => pointInsideOrOnBounds(point, originalFrame))
          .map((point) => point.y)
        : []
    )));
    const movedLeft = Math.min(...movedMembers.map((bounds) => bounds.x));
    const movedTop = Math.min(...movedMembers.map((bounds) => bounds.y));
    const movedRight = Math.max(...movedMembers.map((bounds) => bounds.x + bounds.width));
    const movedBottom = Math.max(
      inFrameFlowBottom,
      ...movedMembers.map((bounds) => bounds.y + bounds.height),
    );
    const bottomPadding = Math.min(
      SEMANTIC_GROUP_BOTTOM_PADDING,
      Math.max(0, originalFrame.y + originalFrame.height - inFrameFlowBottom),
    );
    const nextFrame: Bounds = {
      x: movedLeft - (baseLeft - originalFrame.x),
      y: movedTop - (baseTop - originalFrame.y),
      width: movedRight - movedLeft + (baseLeft - originalFrame.x) + (originalFrame.x + originalFrame.width - baseRight),
      height: movedBottom - movedTop + (baseTop - originalFrame.y) + bottomPadding,
    };
    const shift = { x: nextFrame.x - originalFrame.x, y: nextFrame.y - originalFrame.y };
    primitives = primitives.map((current, index) => {
      if (index === frameIndex && current.kind === "rect") return { ...current, ...nextFrame };
      const original = baseDiagram.primitives[index];
      if (original?.kind !== "text"
        || !pointInsideOrOnBounds({ x: original.x, y: original.y }, originalFrame)) return current;
      return current.kind === "text" ? { ...current, x: original.x + shift.x, y: original.y + shift.y } : current;
    });
  }

  return { ...diagram, primitives };
}

function resizeContainmentFrame(
  diagram: ModuleDetailDiagram,
  baseBounds: Bounds,
  targetBounds: Bounds,
): ModuleDetailDiagram {
  const outer = containmentFrameCandidate(diagram, baseBounds);
  if (!outer) return diagram;
  const left = outer.x - baseBounds.x;
  const top = outer.y - baseBounds.y;
  const right = baseBounds.x + baseBounds.width - outer.x - outer.width;
  const bottom = baseBounds.y + baseBounds.height - outer.y - outer.height;
  const detailNodes = listDetailNodes(diagram);
  const contentLeft = detailNodes.length
    ? Math.min(...detailNodes.map((node) => node.bounds.x)) - 12
    : targetBounds.x + left;
  const contentTop = detailNodes.length
    ? Math.min(...detailNodes.map((node) => node.bounds.y)) - 12
    : targetBounds.y + top;
  const contentRight = detailNodes.length
    ? Math.max(...detailNodes.map((node) => node.bounds.x + node.bounds.width)) + 12
    : targetBounds.x + targetBounds.width - right;
  const contentBottom = detailNodes.length
    ? Math.max(...detailNodes.map((node) => node.bounds.y + node.bounds.height)) + 12
    : targetBounds.y + targetBounds.height - bottom;
  const defaultX = targetBounds.x + left;
  const defaultY = targetBounds.y + top;
  const frameX = Math.max(targetBounds.x + 4, Math.min(defaultX, contentLeft));
  const frameY = Math.max(targetBounds.y + 50, Math.min(defaultY, contentTop));
  const defaultRight = targetBounds.x + targetBounds.width - right;
  const defaultBottom = targetBounds.y + targetBounds.height - bottom;
  const frameRight = Math.min(targetBounds.x + targetBounds.width - 4, Math.max(defaultRight, contentRight));
  const frameBottom = Math.min(targetBounds.y + targetBounds.height - 4, Math.max(defaultBottom, contentBottom));
  return {
    ...diagram,
    primitives: diagram.primitives.map((primitive, index) => {
      if (index !== outer.index || primitive.kind !== "rect") return primitive;
      return {
        ...primitive,
        x: frameX,
        y: frameY,
        width: Math.max(1, frameRight - frameX),
        height: Math.max(1, frameBottom - frameY),
      };
    }),
  };
}

export function visibleContainmentFrameBounds(level: InlineDetailLevel): Bounds | undefined {
  const frame = containmentFrameCandidate(level.diagram, level.bounds);
  return frame ? {
    x: frame.x,
    y: frame.y,
    width: frame.width,
    height: frame.height,
  } : undefined;
}

/** Compatibility alias. Only true containment frames define a level boundary. */
export const visibleDetailFrameBounds = visibleContainmentFrameBounds;

export function detailLevelContentBounds(level: InlineDetailLevel): Bounds {
  const frame = visibleContainmentFrameBounds(level);
  if (frame) {
    return {
      x: frame.x + 12,
      y: frame.y + 12,
      width: Math.max(1, frame.width - 24),
      height: Math.max(1, frame.height - 24),
    };
  }
  return {
    x: level.bounds.x + 12,
    y: level.bounds.y + 62,
    width: Math.max(1, level.bounds.width - 24),
    height: Math.max(1, level.bounds.height - 98),
  };
}

export function inlineAtomicEntry(level: InlineDetailLevel): InlineAtomicEntry | undefined {
  let cursor = level.diagram.entryPoint;
  const visited = new Set<number>();
  for (let depth = 0; depth <= level.diagram.primitives.length; depth += 1) {
    const candidates = level.diagram.primitives.flatMap((primitive, index) => (
      primitive.kind === "flow" && !visited.has(index) && samePoint(primitive.points[0], cursor)
        ? [{ primitive, index }]
        : []
    ));
    if (candidates.length !== 1) return undefined;
    const { primitive, index } = candidates[0];
    visited.add(index);
    const point = primitive.points.at(-1)!;
    const anchor = findAnchor(point, level.nodes, primitive.points.at(-2), "end", true);
    const next = level.diagram.primitives.filter((candidate, candidateIndex) => (
      candidate.kind === "flow"
      && !visited.has(candidateIndex)
      && samePoint(candidate.points[0], point)
    ));
    const isBoundaryAnchor = anchor && distanceToBoundary(point, anchor.node.bounds) <= ANCHOR_TOLERANCE;
    if (anchor && isBoundaryAnchor) {
      const expanded = inlineExpandedChildren(level).find((child) => child.node.id === anchor.node.id);
      if (expanded) {
        return inlineAtomicEntry(expanded.level)
          ?? { point: { ...level.diagram.entryPoint }, side: "left" };
      }
      return { point: { ...point }, side: anchor.side };
    }
    if (next.length !== 1) {
      return next.length > 1 ? { point: { ...level.diagram.entryPoint }, side: "left" } : undefined;
    }
    if (anchor) return { point: { ...point }, side: anchor.side };
    cursor = point;
  }
  return undefined;
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
      const expanded = inlineExpandedChildren(level).find((child) => child.node.id === anchor.node.id);
      if (expanded) {
        return inlineAtomicExit(expanded.level);
      }
      return { point: { ...source }, side: anchor.side };
    }
    const expanded = inlineExpandedChildren(level).find((child) => pointInsideOrOnBounds(source, child.node.bounds));
    if (expanded) return inlineAtomicExit(expanded.level);
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
  const branches = new Map(detailExpansionChildren(branch));
  const activeNodes = nodes.filter((node) => node.nestedKind && branches.has(node.id))
    .sort((first, second) => first.bounds.x - second.bounds.x || first.bounds.y - second.bounds.y || first.id.localeCompare(second.id));
  if (!activeNodes.length) return undefined;

  const currentBounds = new Map(nodes.map((node) => [node.id, { ...node.bounds }]));
  for (const active of activeNodes) {
    const activeBounds = currentBounds.get(active.id)!;
    const childSize = expandedDetailSize(active.nestedKind!, branches.get(active.id));
    const expanded = {
      x: activeBounds.x,
      y: Math.max(baseBounds.y + 58, activeBounds.y),
      width: childSize.width,
      height: childSize.height,
    };
    currentBounds.set(active.id, expanded);
    const activeCenterX = activeBounds.x + activeBounds.width / 2;
    const activeBottom = activeBounds.y + activeBounds.height;
    const growthX = Math.max(0, expanded.width - activeBounds.width) + INLINE_EXPANSION_GAP;
    const growthY = Math.max(0, expanded.height - activeBounds.height) + INLINE_EXPANSION_GAP;

    for (const node of nodes) {
      if (node.id === active.id) continue;
      const nodeBounds = currentBounds.get(node.id)!;
      const centerX = nodeBounds.x + nodeBounds.width / 2;
      const next = { ...nodeBounds };
      if (centerX > activeCenterX + Math.max(8, activeBounds.width * 0.25)) {
        next.x += growthX;
      } else if (nodeBounds.x + nodeBounds.width <= activeBounds.x) {
        // Upstream peers keep their lane and continue into the expanded boundary.
      } else if (nodeBounds.y >= activeBottom - 4) {
        const horizontalOverlap = nodeBounds.x < expanded.x + expanded.width + INLINE_EXPANSION_GAP
          && nodeBounds.x + nodeBounds.width > expanded.x - INLINE_EXPANSION_GAP;
        if (horizontalOverlap) next.y += growthY;
      } else {
        const overlaps = next.x < expanded.x + expanded.width + INLINE_EXPANSION_GAP
          && next.x + next.width > expanded.x - INLINE_EXPANSION_GAP
          && next.y < expanded.y + expanded.height + INLINE_EXPANSION_GAP
          && next.y + next.height > expanded.y - INLINE_EXPANSION_GAP;
        if (overlaps) next.x += growthX;
      }
      currentBounds.set(node.id, next);
    }
  }

  const overrides: DetailNodeBoundsMap = Object.fromEntries(nodes.flatMap((node) => {
    const next = currentBounds.get(node.id)!;
    return boundsEqual(next, node.bounds) ? [] : [[node.id, next]];
  }));
  const finalBounds = nodes.map((node) => currentBounds.get(node.id)!);
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
  previousLevel?: InlineDetailLevel,
  changedLevelKeys?: ReadonlySet<string>,
): InlineDetailLevel {
  const levelKey = detailLevelKey(rootId, levelPath);
  const levelIsAffected = !changedLevelKeys || [...changedLevelKeys].some((changedKey) => (
    changedKey === levelKey || changedKey.startsWith(`${levelKey}/`)
  ));
  if (previousLevel
    && previousLevel.kind === kind
    && previousLevel.levelKey === levelKey
    && previousLevel.routingMode === routingMode
    && boundsEqual(previousLevel.bounds, bounds)
    && !levelIsAffected) {
    return previousLevel;
  }
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
    routeBounds: bounds,
  };
  const preliminaryDiagram = resizeContainmentFrame(
    layoutSemanticGroupFrames(
      baseDiagram,
      layoutDetailDiagram(baseDiagram, layouts[levelKey] ?? {}, commonOptions),
    ),
    natural,
    bounds,
  );
  const preliminaryNodes = listDetailNodes(preliminaryDiagram);
  const childBranches = new Map(detailExpansionChildren(branch));
  const activeNodes = preliminaryNodes.filter((node) => node.nestedKind && childBranches.has(node.id));
  if (!activeNodes.length) {
    return {
      kind,
      bounds,
      diagram: preliminaryDiagram,
      nodes: preliminaryNodes,
      levelKey,
      routingMode,
      expandedChildren: [],
    };
  }
  const baseNodes = listDetailNodes(baseDiagram);
  const previousChildren = new Map((previousLevel ? inlineExpandedChildren(previousLevel) : []).map((expanded) => [
    expanded.node.id,
    expanded.level,
  ]));
  const expandedChildren = activeNodes.map((active) => ({
    node: active,
    level: buildInlineDetailLayout(
      active.nestedKind!,
      active.bounds,
      childBranches.get(active.id),
      layouts,
      rootId,
      [...levelPath, active.id],
      routingMode,
      previousChildren.get(active.id),
      changedLevelKeys,
    ),
  }));
  const atomicPorts = new Map(expandedChildren.map((expanded) => [expanded.node.id, {
    entry: routingMode === "atomic-bottom-up" ? inlineAtomicEntry(expanded.level) : undefined,
    exit: routingMode === "atomic-bottom-up" ? inlineAtomicExit(expanded.level) : undefined,
  }]));
  const junctionPorts = Object.assign({}, ...expandedChildren.map((expanded) => {
    const baseActive = baseNodes.find((node) => node.id === expanded.node.id);
    const ports = atomicPorts.get(expanded.node.id)!;
    return baseActive ? expandedJunctionPorts(
      baseDiagram,
      baseActive,
      ports.entry?.point ?? expanded.level.diagram.entryPoint,
      ports.exit?.point ?? expanded.level.diagram.exitPoint,
    ) : {};
  }));
  const childObstacles = expandedChildren.flatMap((expanded) => leafDetailNodeBounds(expanded.level));
  if (routingMode === "recursive") {
    const diagram = resizeContainmentFrame(layoutSemanticGroupFrames(
      baseDiagram,
      layoutDetailDiagram(baseDiagram, layouts[levelKey] ?? {}, {
        ...commonOptions,
        junctionPorts,
        semanticNodePorts: Object.fromEntries(expandedChildren.map((expanded) => [
          expanded.node.id,
          expanded.level.diagram.semanticInputPorts ?? {},
        ])),
        extraObstacles: childObstacles,
      }),
    ), natural, bounds);
    const nodes = listDetailNodes(diagram);
    const finalChildren = expandedChildren.map((expanded) => ({
      ...expanded,
      node: nodes.find((node) => node.id === expanded.node.id) ?? expanded.node,
    }));
    return {
      kind,
      bounds,
      diagram,
      nodes,
      levelKey,
      routingMode,
      expandedChildren: finalChildren,
      expandedChild: finalChildren[0],
    };
  }

  const diagram = resizeContainmentFrame(layoutSemanticGroupFrames(
    baseDiagram,
    layoutDetailDiagram(baseDiagram, layouts[levelKey] ?? {}, {
      ...commonOptions,
      junctionPorts,
      semanticNodePorts: Object.fromEntries(expandedChildren.map((expanded) => [
        expanded.node.id,
        expanded.level.diagram.semanticInputPorts ?? {},
      ])),
      extraObstacles: childObstacles,
      nodePorts: Object.fromEntries(expandedChildren.map((expanded) => {
        const ports = atomicPorts.get(expanded.node.id)!;
        return [expanded.node.id, {
          left: ports.entry?.point ?? expanded.level.diagram.entryPoint,
          right: ports.exit?.point ?? expanded.level.diagram.exitPoint,
        }];
      })),
      nodePortDirections: Object.fromEntries(expandedChildren.map((expanded) => {
        const ports = atomicPorts.get(expanded.node.id)!;
        return [expanded.node.id, {
          left: ports.entry?.side ?? "left",
          right: ports.exit?.side ?? "right",
        }];
      })),
      suppressExpandedChildMarker: true,
    }),
  ), natural, bounds);
  const nodes = listDetailNodes(diagram);
  const finalChildren = expandedChildren.map((expanded) => ({
    ...expanded,
    node: nodes.find((node) => node.id === expanded.node.id) ?? expanded.node,
  }));
  return {
    kind,
    bounds,
    diagram,
    nodes,
    levelKey,
    routingMode,
    expandedChildren: finalChildren,
    expandedChild: finalChildren[0],
  };
}

function leafDetailNodeBounds(level: InlineDetailLevel): Bounds[] {
  const children = inlineExpandedChildren(level);
  const expandedIds = new Set(children.map((child) => child.node.id));
  return [
    ...level.nodes.filter((node) => !expandedIds.has(node.id)).map((node) => node.bounds),
    ...children.flatMap((child) => leafDetailNodeBounds(child.level)),
  ];
}

export function findInlineDetailLevel(
  root: InlineDetailLevel,
  levelPath: readonly string[],
): InlineDetailLevel | undefined {
  let level: InlineDetailLevel | undefined = root;
  for (const childId of levelPath) {
    const child: NonNullable<InlineDetailLevel["expandedChildren"]>[number] | undefined = level
      ? inlineExpandedChildren(level).find((expanded) => expanded.node.id === childId)
      : undefined;
    if (!child) return undefined;
    level = child.level;
  }
  return level;
}

export function clampDetailOffset(parentBounds: Bounds, childBounds: Bounds, offset: Point): Point {
  return clampDetailOffsetToBounds({
    x: parentBounds.x + 12,
    y: parentBounds.y + 62,
    width: Math.max(1, parentBounds.width - 24),
    height: Math.max(1, parentBounds.height - 98),
  }, childBounds, offset);
}

export function clampDetailOffsetToBounds(
  contentBounds: Bounds,
  childBounds: Bounds,
  offset: Point,
): Point {
  const left = contentBounds.x;
  const right = contentBounds.x + contentBounds.width;
  const top = contentBounds.y;
  const bottom = contentBounds.y + contentBounds.height;
  return {
    x: Math.min(right - childBounds.x - childBounds.width, Math.max(left - childBounds.x, offset.x)),
    y: Math.min(bottom - childBounds.y - childBounds.height, Math.max(top - childBounds.y, offset.y)),
  };
}
