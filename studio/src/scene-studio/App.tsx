import {
  AlignHorizontalJustifyStart,
  AlignHorizontalSpaceAround,
  AlignVerticalJustifyStart,
  AlignVerticalSpaceAround,
  ArrowRightLeft,
  Download,
  GalleryVerticalEnd,
  Maximize2,
  Minus,
  Pin,
  PinOff,
  Plus,
  Redo2,
  RotateCcw,
  Trash2,
  Undo2,
  Waypoints,
} from "lucide-react";
import { memo, useEffect, useMemo, useReducer, useRef, useState, useTransition } from "react";
import type { ReactNode } from "react";

import { applyVisualPatch, clampBounds, cloneScene, editableNodeBounds } from "./model";
import { alignNodeBounds, distributeNodeBounds } from "./layout-commands";
import type { AlignmentCommand, DistributionCommand } from "./layout-commands";
import { expandScene } from "./expansion";
import {
  buildAtomicHierarchyRoutingPlan,
} from "./atomic-hierarchy";
import {
  buildInlineDetailLayout,
  clampDetailOffsetToBounds,
  detailExpansionChildren,
  detailLevelKey,
  detailLevelContentBounds,
  expandedDetailSize,
  findInlineDetailLevel,
  fullyExpandedDetailTree,
  inlineExpandedChildren,
  listDetailNodes,
  toggleDetailExpansionAtPath,
} from "./detail-layout";
import type {
  DetailExpansionBranch,
  DetailExpansionMap,
  DetailLayoutMap,
  DetailNode,
  InlineDetailLevel,
} from "./detail-layout";
import {
  canvasGridSize,
  fitCanvasCamera,
  shouldBeginCanvasPan,
  wheelZoomFactor,
  zoomCameraAt,
} from "./canvas-viewport";
import type { CanvasCamera } from "./canvas-viewport";
import { buildModuleDetail, DETAIL_KIND_NAMES } from "./module-details";
import type { DetailPrimitive } from "./module-details";
import { EMPTY_WORKSPACE_SCENES } from "./empty-workspace";
import {
  DEFAULT_OPTIONS,
  LABEL_STYLE_NAMES,
  LABEL_STYLES,
  NODE_STYLE_NAMES,
  NODE_STYLES,
  ROUTE_NAMES,
  ROUTE_STYLES,
} from "./visual-options";
import { measureScene, routeScene } from "./routing";
import { renderSceneSvg } from "./svg-export";
import type {
  Bounds,
  EdgeLabelStyle,
  EdgeRelation,
  HierarchyRoutingMode,
  LabEdge,
  LabNode,
  LabPatch,
  LabScene,
  NodeShape,
  NodeVisualStyle,
  Point,
  RouteStyle,
  RoutedEdge,
  Selection,
  VisualOptions,
} from "./types";

interface EditorState {
  scene: LabScene;
  past: LabScene[];
  future: LabScene[];
}

type EditorAction =
  | { type: "load"; scene: LabScene }
  | { type: "patch"; patch: LabPatch }
  | { type: "patch-batch"; patches: readonly LabPatch[] }
  | { type: "undo" }
  | { type: "redo" };

interface NodeGesture {
  pointerId: number;
  nodeId: string;
  persistenceTargetId?: string;
  kind: "move" | "resize";
  start: Point;
  initial: Bounds;
}

interface DetailGesture {
  pointerId: number;
  rootId: string;
  levelPath: string[];
  levelKey: string;
  childId: string;
  kind: "detail-move";
  start: Point;
  initialOffset: Point;
  childBounds: Bounds;
  parentBounds: Bounds;
  presentation?: DetailDragPresentation;
}

type Gesture = NodeGesture | DetailGesture;

interface DetailSelection {
  rootId: string;
  levelPath: string[];
  childId: string;
}

interface DetailPreview extends DetailSelection {
  offset: Point;
}

interface CameraGesture {
  pointerId: number;
  start: Point;
  initial: CanvasCamera;
}

interface DetailFlowPresentation {
  element: SVGPolylineElement;
  points: Point[];
  moveStart: boolean;
  moveEnd: boolean;
}

interface DetailDragPresentation {
  element: SVGGElement;
  initialTransform: string | null;
  flows: DetailFlowPresentation[];
}

type PendingGesturePreview =
  | { kind: "node"; value: { nodeId: string; bounds: Bounds } }
  | { kind: "detail"; value: DetailPreview };

interface DetailTreeCacheEntry {
  kind: NonNullable<LabNode["detail_kind"]>;
  bounds: Bounds;
  branch?: DetailExpansionBranch;
  layouts: DetailLayoutMap;
  hierarchyRoutingMode: HierarchyRoutingMode;
  tree: InlineDetailLevel;
}

function sameBounds(first: Bounds, second: Bounds): boolean {
  return first.x === second.x
    && first.y === second.y
    && first.width === second.width
    && first.height === second.height;
}

function pointTouchesBounds(point: Point, bounds: Bounds, tolerance = 16): boolean {
  const dx = point.x < bounds.x
    ? bounds.x - point.x
    : point.x > bounds.x + bounds.width ? point.x - bounds.x - bounds.width : 0;
  const dy = point.y < bounds.y
    ? bounds.y - point.y
    : point.y > bounds.y + bounds.height ? point.y - bounds.y - bounds.height : 0;
  if (dx || dy) return Math.hypot(dx, dy) <= tolerance;
  return Math.min(
    point.x - bounds.x,
    bounds.x + bounds.width - point.x,
    point.y - bounds.y,
    bounds.y + bounds.height - point.y,
  ) <= tolerance;
}

function captureDetailDragPresentation(
  eventTarget: EventTarget | null,
  childBounds: Bounds,
): DetailDragPresentation | undefined {
  if (!(eventTarget instanceof Element)) return undefined;
  const element = eventTarget.closest<SVGGElement>(".detail-interactive-node, .nested-inline-detail");
  const level = element?.parentElement;
  if (!element || !level?.classList.contains("detail-level")) return undefined;
  const detailRoot = element.closest<SVGGElement>(".lab-node") ?? level;
  const flows = [...detailRoot.querySelectorAll<SVGPolylineElement>(".detail-flow")].flatMap((flow) => {
    if (element.contains(flow)) return [];
    const points = Array.from({ length: flow.points.numberOfItems }, (_, index) => {
      const point = flow.points.getItem(index);
      return { x: point.x, y: point.y };
    });
    if (!points.length) return [];
    const moveStart = pointTouchesBounds(points[0], childBounds);
    const moveEnd = pointTouchesBounds(points.at(-1)!, childBounds);
    return moveStart || moveEnd ? [{ element: flow, points, moveStart, moveEnd }] : [];
  });
  return { element, initialTransform: element.getAttribute("transform"), flows };
}

function translatedFlowPoints(flow: DetailFlowPresentation, dx: number, dy: number): Point[] {
  const points = flow.points.map((point) => ({ ...point }));
  const moveEndpoint = (index: number, adjacentIndex: number) => {
    const original = flow.points[index];
    const adjacent = flow.points[adjacentIndex];
    points[index] = { x: original.x + dx, y: original.y + dy };
    if (!adjacent || points.length <= 2) return;
    if (Math.abs(original.y - adjacent.y) <= Math.abs(original.x - adjacent.x)) {
      points[adjacentIndex].y = adjacent.y + dy;
    } else {
      points[adjacentIndex].x = adjacent.x + dx;
    }
  };
  if (flow.moveStart) moveEndpoint(0, 1);
  if (flow.moveEnd) moveEndpoint(points.length - 1, points.length - 2);
  return points;
}

function presentDetailDrag(presentation: DetailDragPresentation, dx: number, dy: number) {
  const suffix = presentation.initialTransform ? ` ${presentation.initialTransform}` : "";
  presentation.element.setAttribute("transform", `translate(${dx} ${dy})${suffix}`);
  for (const flow of presentation.flows) {
    flow.element.setAttribute(
      "points",
      translatedFlowPoints(flow, dx, dy).map((point) => `${point.x},${point.y}`).join(" "),
    );
  }
}

function resetDetailDragPresentation(presentation: DetailDragPresentation | undefined) {
  if (!presentation) return;
  if (presentation.initialTransform === null) presentation.element.removeAttribute("transform");
  else presentation.element.setAttribute("transform", presentation.initialTransform);
  for (const flow of presentation.flows) {
    flow.element.setAttribute("points", flow.points.map((point) => `${point.x},${point.y}`).join(" "));
  }
}

function sameNode(first: LabNode, second: LabNode): boolean {
  return first.scene_node_id === second.scene_node_id
    && first.hierarchy_node_id === second.hierarchy_node_id
    && first.shape === second.shape
    && first.label === second.label
    && first.secondary_label === second.secondary_label
    && first.detail_kind === second.detail_kind
    && first.detail_expanded === second.detail_expanded
    && sameBounds(first.bounds, second.bounds);
}

function persistenceTargetForNode(node: LabNode | undefined): string | undefined {
  return node?.hierarchy_node_id ? `view:${node.hierarchy_node_id}` : undefined;
}

function sameDetailSelection(first?: DetailSelection | null, second?: DetailSelection | null): boolean {
  if (!first || !second) return first === second;
  return first.rootId === second.rootId
    && first.childId === second.childId
    && sameLevelPath(first.levelPath, second.levelPath);
}

function useLatestEvent<T extends (...args: never[]) => unknown>(handler: T): T {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;
  return useMemo(() => ((...args: Parameters<T>) => handlerRef.current(...args)) as T, []);
}

function useStableSet(values: ReadonlySet<string> | undefined): ReadonlySet<string> | undefined {
  const stableRef = useRef(values);
  const stable = stableRef.current;
  const equal = stable === values || Boolean(stable && values
    && stable.size === values.size
    && [...values].every((value) => stable.has(value)));
  if (!equal) stableRef.current = values;
  return stableRef.current;
}

function sameDetailLevelLayout(
  first: DetailLayoutMap[string] | undefined,
  second: DetailLayoutMap[string] | undefined,
): boolean {
  if (first === second) return true;
  const firstEntries = Object.entries(first ?? {});
  const secondEntries = Object.entries(second ?? {});
  return firstEntries.length === secondEntries.length && firstEntries.every(([nodeId, offset]) => (
    offset.x === second?.[nodeId]?.x && offset.y === second[nodeId]?.y
  ));
}

function changedDetailLevelKeys(first: DetailLayoutMap, second: DetailLayoutMap): Set<string> {
  const keys = new Set([...Object.keys(first), ...Object.keys(second)]);
  return new Set([...keys].filter((key) => !sameDetailLevelLayout(first[key], second[key])));
}

const NODE_SHAPES: readonly NodeShape[] = [
  "operation",
  "tensor",
  "convolution",
  "attention",
  "normalization",
  "condition",
  "merge",
  "add",
  "multiply",
  "concat",
  "io",
];

const EDGE_RELATIONS: readonly EdgeRelation[] = [
  "flow",
  "branch",
  "merge",
  "residual",
  "memory",
  "condition",
  "feedback",
];

const NODE_SHAPE_NAMES: Record<NodeShape, string> = {
  operation: "算子",
  tensor: "张量",
  convolution: "卷积",
  attention: "注意力",
  normalization: "归一化",
  condition: "条件",
  merge: "汇聚",
  add: "相加",
  multiply: "相乘",
  concat: "拼接",
  io: "输入/输出",
};

const EDGE_RELATION_NAMES: Record<EdgeRelation, string> = {
  flow: "数据流",
  branch: "分支",
  merge: "汇聚",
  residual: "残差",
  memory: "记忆",
  condition: "条件",
  feedback: "反馈",
};

const RELATION_COLORS: Record<EdgeRelation, string> = {
  flow: "#39444d",
  branch: "#266d66",
  merge: "#725b19",
  residual: "#b33d5a",
  memory: "#7756a2",
  condition: "#a35416",
  feedback: "#2467a5",
};

const NODE_COLORS: Record<NodeShape, { fill: string; stroke: string }> = {
  operation: { fill: "#f7f9fa", stroke: "#64727d" },
  tensor: { fill: "#eef5fb", stroke: "#4f7896" },
  convolution: { fill: "#edf7f5", stroke: "#397b73" },
  attention: { fill: "#fff3e8", stroke: "#a5652e" },
  normalization: { fill: "#eaf6f1", stroke: "#397662" },
  condition: { fill: "#fbf0f8", stroke: "#966487" },
  merge: { fill: "#f8f2df", stroke: "#8d742d" },
  add: { fill: "#fff4cf", stroke: "#8d742d" },
  multiply: { fill: "#fcebdc", stroke: "#a35416" },
  concat: { fill: "#eeeaf8", stroke: "#72549b" },
  io: { fill: "#f8edf1", stroke: "#9b5268" },
};

const PAPER_NODE_COLORS: Record<NonNullable<LabNode["paper_tone"]>, { fill: string; stroke: string }> = {
  encoder: { fill: "#e7f4fb", stroke: "#245f85" },
  decoder: { fill: "#fbeaf0", stroke: "#8b405e" },
  input: { fill: "#f8e3ea", stroke: "#96536a" },
  output: { fill: "#e6f4e8", stroke: "#3f7850" },
  neutral: { fill: "#fff9dc", stroke: "#7b6b29" },
};

function visualOptionsForScene(scene: LabScene): VisualOptions {
  return scene.layout_profile === "paper"
    ? { routeStyle: "adaptive", nodeStyle: "semantic", labelStyle: "plain" }
    : DEFAULT_OPTIONS;
}

function initialScenario(scenes: readonly LabScene[], preferredSceneId?: string): LabScene {
  const sceneId = typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("scene");
  return scenes.find((scene) => scene.scene_id === (preferredSceneId ?? sceneId)) ?? scenes[0];
}

function sceneContentBounds(scene: LabScene): Bounds {
  if (!scene.nodes.length) return { x: 0, y: 0, width: scene.paper_width, height: scene.paper_height };
  const left = Math.min(...scene.nodes.map((node) => node.bounds.x));
  const top = Math.min(...scene.nodes.map((node) => node.bounds.y));
  const right = Math.max(...scene.nodes.map((node) => node.bounds.x + node.bounds.width));
  const bottom = Math.max(...scene.nodes.map((node) => node.bounds.y + node.bounds.height));
  return { x: left, y: top, width: right - left, height: bottom - top };
}

function initialExpandedNodeIds(scene: LabScene): Set<string> {
  if (typeof window === "undefined") return new Set();
  const requested = new URLSearchParams(window.location.search).get("expand");
  if (!requested) return new Set();
  const values = new Set(requested.split(",").map((value) => value.trim()).filter(Boolean));
  return new Set(scene.nodes
    .filter((node) => node.detail_kind && (values.has("all") || values.has(node.scene_node_id) || values.has(node.detail_kind)))
    .map((node) => node.scene_node_id));
}

function initialDetailExpansions(scene: LabScene, expandedIds: Set<string>): DetailExpansionMap {
  if (typeof window === "undefined") return {};
  const requested = new URLSearchParams(window.location.search).get("drilldown")?.trim().toLowerCase();
  if (!requested) return {};
  const expandedScene = expandScene(scene, expandedIds);
  for (const parent of expandedScene.nodes) {
    if (!parent.detail_expanded || !parent.detail_kind) continue;
    const child = listDetailNodes(buildModuleDetail(parent.detail_kind, parent.bounds))
      .find((item) => item.nestedKind && item.label.toLowerCase().includes(requested));
    if (child) return { [parent.scene_node_id]: { children: { [child.id]: { children: {} } } } };
  }
  return {};
}

function editorReducer(state: EditorState, action: EditorAction): EditorState {
  if (action.type === "load") return { scene: cloneScene(action.scene), past: [], future: [] };
  if (action.type === "patch") {
    const next = applyVisualPatch(state.scene, action.patch);
    if (next === state.scene) return state;
    return { scene: next, past: [...state.past.slice(-49), state.scene], future: [] };
  }
  if (action.type === "patch-batch") {
    const next = action.patches.reduce(applyVisualPatch, state.scene);
    if (next === state.scene || action.patches.length === 0) return state;
    return { scene: next, past: [...state.past.slice(-49), state.scene], future: [] };
  }
  if (action.type === "undo") {
    const previous = state.past.at(-1);
    if (!previous) return state;
    return {
      scene: previous,
      past: state.past.slice(0, -1),
      future: [state.scene, ...state.future].slice(0, 50),
    };
  }
  const next = state.future[0];
  if (!next) return state;
  return {
    scene: next,
    past: [...state.past, state.scene].slice(-50),
    future: state.future.slice(1),
  };
}

function svgPoint(event: React.PointerEvent<SVGSVGElement>, svg: SVGSVGElement): Point {
  const point = svg.createSVGPoint();
  point.x = event.clientX;
  point.y = event.clientY;
  const matrix = svg.getScreenCTM()?.inverse();
  if (!matrix) return { x: event.clientX, y: event.clientY };
  const transformed = point.matrixTransform(matrix);
  return { x: transformed.x, y: transformed.y };
}

function nextGestureBounds(gesture: NodeGesture, point: Point, scene: LabScene): Bounds {
  const dx = point.x - gesture.start.x;
  const dy = point.y - gesture.start.y;
  return clampBounds(gesture.kind === "move"
    ? { ...gesture.initial, x: gesture.initial.x + dx, y: gesture.initial.y + dy }
    : { ...gesture.initial, width: gesture.initial.width + dx, height: gesture.initial.height + dy }, scene);
}

function polygonPoints(node: LabNode): string | null {
  const { x, y, width, height } = node.bounds;
  if (node.shape === "condition") {
    const inset = Math.min(25, width * 0.16);
    return `${x + inset},${y} ${x + width - inset},${y} ${x + width},${y + height / 2} ${x + width - inset},${y + height} ${x + inset},${y + height} ${x},${y + height / 2}`;
  }
  if (node.shape === "merge") {
    return `${x + width / 2},${y} ${x + width},${y + height / 2} ${x + width / 2},${y + height} ${x},${y + height / 2}`;
  }
  return null;
}

function wrapLabel(value: string, maxCharacters: number): string[] {
  if (value.length <= maxCharacters) return [value];
  const hasSpaces = value.includes(" ");
  const words = hasSpaces ? value.split(/\s+/) : [...value];
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? `${current}${hasSpaces ? " " : ""}${word}` : word;
    if (candidate.length > maxCharacters && current) {
      lines.push(current);
      current = word;
    } else current = candidate;
  }
  if (current) lines.push(current);
  return lines.slice(0, 3);
}

function MatrixGrid({
  x,
  y,
  width,
  height,
  stroke,
  columns = 4,
  rows = 3,
}: {
  x: number;
  y: number;
  width: number;
  height: number;
  stroke: string;
  columns?: number;
  rows?: number;
}) {
  return <g className="node-grid" stroke={stroke}>
    {Array.from({ length: columns - 1 }, (_, index) => <line
      key={`column-${index}`}
      x1={x + width * (index + 1) / columns}
      y1={y}
      x2={x + width * (index + 1) / columns}
      y2={y + height}
    />)}
    {Array.from({ length: rows - 1 }, (_, index) => <line
      key={`row-${index}`}
      x1={x}
      y1={y + height * (index + 1) / rows}
      x2={x + width}
      y2={y + height * (index + 1) / rows}
    />)}
  </g>;
}

function DetailPrimitiveGraphic({
  primitive,
  index,
  atomicEdgeId,
  detailNode,
  selected = false,
  nestedExpanded = false,
  onPointerDown,
  onToggleNested,
}: {
  primitive: DetailPrimitive;
  index: number;
  atomicEdgeId?: string;
  detailNode?: DetailNode;
  selected?: boolean;
  nestedExpanded?: boolean;
  onPointerDown?: (event: React.PointerEvent<SVGGElement>, node: DetailNode) => void;
  onToggleNested?: (node: DetailNode) => void;
}) {
  if (primitive.kind === "flow") {
    const markerId = primitive.tone && primitive.tone !== "neutral"
      ? `internal-arrow-${primitive.tone}`
      : "internal-arrow";
    return <polyline
      key={index}
      className={`detail-flow ${primitive.tone ? `detail-tone-${primitive.tone}` : ""}`}
      data-atomic-edge-id={atomicEdgeId}
      points={primitive.points.map((point) => `${point.x},${point.y}`).join(" ")}
      markerEnd={primitive.marker === false ? undefined : `url(#${markerId})`}
    />;
  }
  if (primitive.kind === "text") {
    return <text
      key={index}
      className={`detail-text ${primitive.emphasis ? "emphasis" : ""} ${primitive.tone ? `detail-tone-${primitive.tone}` : ""}`}
      x={primitive.x}
      y={primitive.y}
      textAnchor={primitive.anchor ?? "middle"}
    >{primitive.value}</text>;
  }
  let graphic: React.ReactNode;
  if (primitive.kind === "circle") {
    graphic = <g className={`detail-shape detail-tone-${primitive.tone}`}>
      <circle cx={primitive.cx} cy={primitive.cy} r={primitive.radius} />
      <text className="detail-symbol" x={primitive.cx} y={primitive.cy + 5}>{primitive.label}</text>
    </g>;
  } else if (primitive.kind === "matrix") {
    graphic = <g className={`detail-shape detail-matrix detail-tone-${primitive.tone}`}>
      {Array.from({ length: primitive.depth ? 2 : 0 }, (_, depthIndex) => <rect
        key={depthIndex}
        x={primitive.x + (2 - depthIndex) * 4}
        y={primitive.y - (2 - depthIndex) * 4}
        width={primitive.width}
        height={primitive.height}
        rx={2}
      />)}
      <rect x={primitive.x} y={primitive.y} width={primitive.width} height={primitive.height} rx={2} />
      <MatrixGrid
        x={primitive.x}
        y={primitive.y}
        width={primitive.width}
        height={primitive.height}
        stroke="currentColor"
        columns={primitive.columns}
        rows={primitive.rows}
      />
      {primitive.label && <text className="detail-matrix-label" x={primitive.x + primitive.width / 2} y={primitive.y - 7}>{primitive.label}</text>}
    </g>;
  } else {
    graphic = <g className={`detail-shape detail-tone-${primitive.tone} detail-${primitive.variant ?? "box"}${primitive.variant === "frame" ? ` detail-frame-${primitive.frameRole ?? "containment"}` : ""}`}>
      <rect x={primitive.x} y={primitive.y} width={primitive.width} height={primitive.height} rx={primitive.rx} />
      {primitive.label && <text className="detail-box-label" x={primitive.x + primitive.width / 2} y={primitive.y + primitive.height / 2 + (primitive.note ? -2 : 4)}>{primitive.label}</text>}
      {primitive.note && <text className="detail-note" x={primitive.x + primitive.width / 2} y={primitive.y + primitive.height / 2 + 13}>{primitive.note}</text>}
    </g>;
  }
  if (!detailNode) return <g key={index}>{graphic}</g>;
  const { bounds } = detailNode;
  return <g
    key={index}
    className={`detail-interactive-node ${selected ? "selected" : ""}`}
    data-detail-node-id={detailNode.id}
    role="button"
    tabIndex={0}
    aria-label={`${detailNode.label} 子模块，可拖动${detailNode.nestedKind ? "，可继续展开" : ""}`}
    onPointerDown={(event) => onPointerDown?.(event, detailNode)}
    onDoubleClick={(event) => {
      if (!detailNode.nestedKind) return;
      event.stopPropagation();
      onToggleNested?.(detailNode);
    }}
  >
    {graphic}
    {selected && <rect
      className="detail-selection"
      x={bounds.x - 4}
      y={bounds.y - 4}
      width={bounds.width + 8}
      height={bounds.height + 8}
      rx={5}
    />}
    {detailNode.nestedKind && <foreignObject
      x={bounds.x + bounds.width - 8}
      y={bounds.y - 10}
      width={20}
      height={20}
    >
      <button
        className="detail-child-toggle"
        type="button"
        aria-label={`${nestedExpanded ? "返回" : "展开"}${detailNode.label}下一层结构`}
        title={`${nestedExpanded ? "返回" : "展开"}${detailNode.label}下一层结构`}
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => { event.stopPropagation(); onToggleNested?.(detailNode); }}
      >{nestedExpanded ? <Minus size={11} /> : <Plus size={11} />}</button>
    </foreignObject>}
  </g>;
}

function sameLevelPath(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

function expansionAtLevel(
  branch: DetailExpansionBranch | undefined,
  levelPath: readonly string[],
): DetailExpansionBranch | undefined {
  let current = branch;
  for (const childId of levelPath) {
    current = detailExpansionChildren(current).find(([id]) => id === childId)?.[1];
    if (!current) return undefined;
  }
  return current;
}

interface RecursiveDetailLevelGraphicProps {
  root: LabNode;
  level: InlineDetailLevel;
  levelPath: string[];
  selection?: DetailSelection | null;
  onChildPointerDown: (
    event: React.PointerEvent<SVGGElement>,
    root: LabNode,
    levelPath: string[],
    level: InlineDetailLevel,
    child: DetailNode,
  ) => void;
  onToggleNested: (root: LabNode, levelPath: string[], child: DetailNode) => void;
  hiddenFlowIds?: ReadonlySet<string>;
  foregroundFlowIds?: ReadonlySet<string>;
}

function recursiveDetailLevelPropsEqual(
  first: RecursiveDetailLevelGraphicProps,
  second: RecursiveDetailLevelGraphicProps,
): boolean {
  return sameNode(first.root, second.root)
    && first.level === second.level
    && sameLevelPath(first.levelPath, second.levelPath)
    && sameDetailSelection(first.selection, second.selection)
    && first.onChildPointerDown === second.onChildPointerDown
    && first.onToggleNested === second.onToggleNested
    && first.hiddenFlowIds === second.hiddenFlowIds
    && first.foregroundFlowIds === second.foregroundFlowIds;
}

const RecursiveDetailLevelGraphic = memo(function RecursiveDetailLevelGraphic({
  root,
  level,
  levelPath,
  selection,
  onChildPointerDown,
  onToggleNested,
  hiddenFlowIds,
  foregroundFlowIds,
}: RecursiveDetailLevelGraphicProps) {
  const nodesByIndex = new Map(level.nodes.map((child) => [child.primitiveIndex, child]));
  const expanded = inlineExpandedChildren(level);
  const expandedIds = new Set(expanded.map((child) => child.node.id));
  const renderPrimitive = (primitive: DetailPrimitive, index: number, foreground: boolean) => {
      const child = nodesByIndex.get(index);
      const atomicEdgeId = primitive.kind === "flow" ? `${level.levelKey}:flow:${index}` : undefined;
      if (child && expandedIds.has(child.id)) return null;
      if (atomicEdgeId && hiddenFlowIds?.has(atomicEdgeId)) return null;
      if (Boolean(atomicEdgeId && foregroundFlowIds?.has(atomicEdgeId)) !== foreground) return null;
      const selected = Boolean(child && selection?.rootId === root.scene_node_id
        && sameLevelPath(selection.levelPath, levelPath)
        && selection.childId === child.id);
      return <DetailPrimitiveGraphic
        key={index}
        primitive={primitive}
        index={index}
        atomicEdgeId={atomicEdgeId}
        detailNode={child}
        selected={selected}
        onPointerDown={child ? (event) => onChildPointerDown(event, root, levelPath, level, child) : undefined}
        onToggleNested={child ? () => onToggleNested(root, levelPath, child) : undefined}
      />;
  };
  return <g className={`detail-level detail-${level.kind}`} data-detail-level={level.levelKey}>
    {level.diagram.primitives.map((primitive, index) => renderPrimitive(primitive, index, false))}
    {expanded.map((child) => <InlineExpandedDetailGraphic
      key={child.node.id}
      root={root}
      parentLevel={level}
      expanded={child}
      levelPath={levelPath}
      selection={selection}
      onChildPointerDown={onChildPointerDown}
      onToggleNested={onToggleNested}
      hiddenFlowIds={hiddenFlowIds}
      foregroundFlowIds={foregroundFlowIds}
    />)}
    {level.diagram.primitives.map((primitive, index) => renderPrimitive(primitive, index, true))}
  </g>;
}, recursiveDetailLevelPropsEqual);

function InlineExpandedDetailGraphic({
  root,
  parentLevel,
  expanded,
  levelPath,
  selection,
  onChildPointerDown,
  onToggleNested,
  hiddenFlowIds,
  foregroundFlowIds,
}: {
  root: LabNode;
  parentLevel: InlineDetailLevel;
  expanded: NonNullable<InlineDetailLevel["expandedChildren"]>[number];
  levelPath: string[];
  selection?: DetailSelection | null;
  onChildPointerDown: (
    event: React.PointerEvent<SVGGElement>,
    root: LabNode,
    levelPath: string[],
    level: InlineDetailLevel,
    child: DetailNode,
  ) => void;
  onToggleNested: (root: LabNode, levelPath: string[], child: DetailNode) => void;
  hiddenFlowIds?: ReadonlySet<string>;
  foregroundFlowIds?: ReadonlySet<string>;
}) {
  const child = expanded.node;
  const nested = expanded.level;
  const { x, y, width, height } = child.bounds;
  const selected = selection?.rootId === root.scene_node_id
    && sameLevelPath(selection.levelPath, levelPath)
    && selection.childId === child.id;
  return <g
    className={`nested-inline-detail ${selected ? "selected" : ""}`}
    data-detail-node-id={child.id}
    role="group"
    aria-label={`${child.label}，已展开为${DETAIL_KIND_NAMES[nested.kind]}`}
  >
    <rect
      className="nested-inline-surface"
      x={x}
      y={y}
      width={width}
      height={height}
      rx={5}
      onPointerDown={(event) => onChildPointerDown(event, root, levelPath, parentLevel, child)}
    />
    <RecursiveDetailLevelGraphic
      root={root}
      level={nested}
      levelPath={[...levelPath, child.id]}
      selection={selection}
      onChildPointerDown={onChildPointerDown}
      onToggleNested={onToggleNested}
      hiddenFlowIds={hiddenFlowIds}
      foregroundFlowIds={foregroundFlowIds}
    />
    <rect
      className="nested-inline-header"
      x={x}
      y={y}
      width={width}
      height={42}
      rx={5}
      onPointerDown={(event) => onChildPointerDown(event, root, levelPath, parentLevel, child)}
    />
    <line className="nested-inline-divider" x1={x} y1={y + 42} x2={x + width} y2={y + 42} />
    <text className="nested-detail-title" x={x + 12} y={y + 17}>{child.label}</text>
    <text className="nested-detail-subtitle" x={x + 12} y={y + 32}>{DETAIL_KIND_NAMES[nested.kind]}</text>
    <foreignObject x={x + width - 29} y={y + 9} width={20} height={20}>
      <button
        className="detail-child-toggle"
        type="button"
        aria-label={`收起${child.label}下一层结构`}
        title={`收起${child.label}下一层结构`}
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => { event.stopPropagation(); onToggleNested(root, levelPath, child); }}
      ><Minus size={11} /></button>
    </foreignObject>
    {selected && <rect className="detail-selection" x={x - 4} y={y - 4} width={width + 8} height={height + 8} rx={7} />}
  </g>;
}

function ModuleDetailGraphic({
  node,
  level,
  detailSelection,
  onChildPointerDown,
  onToggleNested,
  hiddenFlowIds,
  foregroundFlowIds,
}: {
  node: LabNode;
  level?: InlineDetailLevel;
  detailSelection?: DetailSelection | null;
  onChildPointerDown: (
    event: React.PointerEvent<SVGGElement>,
    root: LabNode,
    levelPath: string[],
    level: InlineDetailLevel,
    child: DetailNode,
  ) => void;
  onToggleNested: (root: LabNode, levelPath: string[], child: DetailNode) => void;
  hiddenFlowIds?: ReadonlySet<string>;
  foregroundFlowIds?: ReadonlySet<string>;
}) {
  if (!node.detail_kind || !level) return null;
  return <g className={`module-detail detail-${level.kind}`} aria-label={DETAIL_KIND_NAMES[level.kind]}>
    <RecursiveDetailLevelGraphic
      root={node}
      level={level}
      levelPath={[]}
      selection={detailSelection}
      onChildPointerDown={onChildPointerDown}
      onToggleNested={onToggleNested}
      hiddenFlowIds={hiddenFlowIds}
      foregroundFlowIds={foregroundFlowIds}
    />
  </g>;
}

function DetailToggle({ node, onToggle }: { node: LabNode; onToggle: (nodeId: string) => void }) {
  if (!node.detail_kind) return null;
  const expanded = Boolean(node.detail_expanded);
  return <foreignObject x={node.bounds.x + node.bounds.width - 35} y={node.bounds.y + 10} width={25} height={25}>
    <button
      className="detail-toggle"
      type="button"
      aria-label={`${expanded ? "收起" : "展开"}${node.label}内部数据流`}
      title={`${expanded ? "收起" : "展开"}${node.label}内部数据流`}
      onPointerDown={(event) => event.stopPropagation()}
      onClick={(event) => { event.stopPropagation(); onToggle(node.scene_node_id); }}
    >{expanded ? <Minus size={14} /> : <Plus size={14} />}</button>
  </foreignObject>;
}

interface NodeGraphicProps {
  node: LabNode;
  visualStyle: NodeVisualStyle;
  paperMode: boolean;
  selected: boolean;
  connecting: boolean;
  onPointerDown: (event: React.PointerEvent<SVGGElement>, node: LabNode) => void;
  onResizePointerDown: (event: React.PointerEvent<SVGRectElement>, node: LabNode) => void;
  onToggleDetail: (nodeId: string) => void;
  detailTree?: InlineDetailLevel;
  detailSelection?: DetailSelection | null;
  onDetailPointerDown: (
    event: React.PointerEvent<SVGGElement>,
    root: LabNode,
    levelPath: string[],
    level: InlineDetailLevel,
    child: DetailNode,
  ) => void;
  onToggleNestedDetail: (root: LabNode, levelPath: string[], child: DetailNode) => void;
  resizeEnabled: boolean;
  hiddenFlowIds?: ReadonlySet<string>;
  foregroundFlowIds?: ReadonlySet<string>;
}

function nodeGraphicPropsEqual(first: NodeGraphicProps, second: NodeGraphicProps): boolean {
  return sameNode(first.node, second.node)
    && first.visualStyle === second.visualStyle
    && first.paperMode === second.paperMode
    && first.selected === second.selected
    && first.connecting === second.connecting
    && first.detailTree === second.detailTree
    && sameDetailSelection(first.detailSelection, second.detailSelection)
    && first.resizeEnabled === second.resizeEnabled
    && first.hiddenFlowIds === second.hiddenFlowIds
    && first.foregroundFlowIds === second.foregroundFlowIds
    && first.onPointerDown === second.onPointerDown
    && first.onResizePointerDown === second.onResizePointerDown
    && first.onToggleDetail === second.onToggleDetail
    && first.onDetailPointerDown === second.onDetailPointerDown
    && first.onToggleNestedDetail === second.onToggleNestedDetail;
}

const NodeGraphic = memo(function NodeGraphic({
  node,
  visualStyle,
  paperMode,
  selected,
  connecting,
  onPointerDown,
  onResizePointerDown,
  onToggleDetail,
  detailTree,
  detailSelection,
  onDetailPointerDown,
  onToggleNestedDetail,
  resizeEnabled,
  hiddenFlowIds,
  foregroundFlowIds,
}: NodeGraphicProps) {
  const { x, y, width, height } = node.bounds;
  const colors = paperMode
    ? PAPER_NODE_COLORS[node.paper_tone ?? "neutral"]
    : NODE_COLORS[node.shape];
  const fill = paperMode ? colors.fill : visualStyle === "compact" ? "#ffffff" : colors.fill;
  const polygon = polygonPoints(node);
  const symbol = node.shape === "add" ? "+" : node.shape === "multiply" ? "×" : node.shape === "concat" ? "||" : null;
  const detailed = !paperMode && ["tensor", "convolution", "attention", "normalization"].includes(node.shape) && width >= 110;
  const labelX = detailed ? x + width * 0.68 : x + width / 2;
  const labelWidth = detailed ? width * 0.53 : width - 22;
  const maxCharacters = Math.max(5, Math.floor(labelWidth / (visualStyle === "compact" ? 7.1 : 6.7)));
  const lines = wrapLabel(node.label, maxCharacters);
  const titleY = visualStyle === "technical"
    ? y + 31
    : y + height / 2 - (lines.length - 1) * 8 - (visualStyle !== "compact" && height >= 62 ? 4 : 0);
  const glyphX = x + 12;
  const glyphY = y + Math.max(11, (height - Math.min(44, height - 22)) / 2);
  const glyphWidth = Math.min(52, width * 0.37);
  const glyphHeight = Math.min(44, height - 22);
  if (node.detail_expanded && node.detail_kind) {
    return <g
      className={`lab-node expanded-node ${paperMode ? `paper-node paper-tone-${node.paper_tone ?? "neutral"}` : ""} ${selected ? "selected" : ""} ${connecting ? "connecting" : ""}`}
      data-node-id={node.scene_node_id}
      data-hierarchy-node-id={node.hierarchy_node_id}
      tabIndex={0}
      role="group"
      aria-label={`${node.label}, ${DETAIL_KIND_NAMES[node.detail_kind]}, 已展开`}
      onPointerDown={(event) => onPointerDown(event, node)}
    >
      <rect className="node-surface expanded-surface" x={x} y={y} width={width} height={height} rx={6} fill="#ffffff" stroke={colors.stroke} />
      <rect className="expanded-header" x={x} y={y} width={width} height={50} rx={6} fill={colors.fill} />
      <line className="expanded-divider" x1={x} y1={y + 50} x2={x + width} y2={y + 50} />
      <text className="expanded-title" x={x + 16} y={y + 22}>{node.label}</text>
      <text className="expanded-subtitle" x={x + 16} y={y + 39}>{DETAIL_KIND_NAMES[node.detail_kind]}</text>
      <ModuleDetailGraphic
        node={node}
        level={detailTree}
        detailSelection={detailSelection}
        onChildPointerDown={onDetailPointerDown}
        onToggleNested={onToggleNestedDetail}
        hiddenFlowIds={hiddenFlowIds}
        foregroundFlowIds={foregroundFlowIds}
      />
      <DetailToggle node={node} onToggle={onToggleDetail} />
      {selected && <rect className="node-selection" x={x - 5} y={y - 5} width={width + 10} height={height + 10} rx={8} />}
    </g>;
  }
  return (
    <g
      className={`lab-node node-${visualStyle} ${paperMode ? `paper-node paper-tone-${node.paper_tone ?? "neutral"}` : ""} ${selected ? "selected" : ""} ${connecting ? "connecting" : ""}`}
      data-node-id={node.scene_node_id}
      data-hierarchy-node-id={node.hierarchy_node_id}
      tabIndex={0}
      role="button"
      aria-label={`${node.label}, ${NODE_SHAPE_NAMES[node.shape]}`}
      onPointerDown={(event) => onPointerDown(event, node)}
    >
      {symbol ? <>
        <circle className="node-surface" cx={x + width / 2} cy={y + height * 0.42} r={Math.min(width, height) * 0.27} fill={fill} stroke={colors.stroke} />
        <text className="node-symbol" x={x + width / 2} y={y + height * 0.42 + 8}>{symbol}</text>
      </> : polygon
        ? <polygon className="node-surface" points={polygon} fill={fill} stroke={colors.stroke} />
        : <rect
          className="node-surface"
          x={x}
          y={y}
          width={width}
          height={height}
          rx={paperMode ? 4 : node.shape === "io" ? Math.min(26, height / 2) : node.shape === "normalization" ? 14 : 5}
          fill={fill}
          stroke={colors.stroke}
        />}
      {node.shape === "tensor" && detailed && <g className="node-glyph" stroke={colors.stroke}>
        <path d={`M ${glyphX + 6} ${glyphY - 6} h ${glyphWidth} l 7 7 v ${glyphHeight} l -7 -7 h -${glyphWidth} z`} fill="none" />
        <rect x={glyphX} y={glyphY} width={glyphWidth} height={glyphHeight} rx={2} fill={fill} />
        <MatrixGrid x={glyphX} y={glyphY} width={glyphWidth} height={glyphHeight} stroke={colors.stroke} />
      </g>}
      {node.shape === "convolution" && detailed && <g className="node-glyph" stroke={colors.stroke}>
        {[8, 4, 0].map((offset) => <rect key={offset} x={glyphX + offset} y={glyphY - offset} width={glyphWidth - 8} height={glyphHeight} rx={2} fill={fill} />)}
        <MatrixGrid x={glyphX + 8} y={glyphY - 8} width={glyphWidth - 8} height={glyphHeight} stroke={colors.stroke} columns={3} rows={3} />
      </g>}
      {node.shape === "attention" && detailed && <g className="node-glyph" stroke={colors.stroke}>
        {["Q", "K", "V"].map((value, index) => <g key={value}>
          <rect x={glyphX} y={glyphY + index * (glyphHeight / 3)} width={17} height={glyphHeight / 3 - 2} rx={2} fill={fill} />
          <text className="node-glyph-text" x={glyphX + 8.5} y={glyphY + index * (glyphHeight / 3) + glyphHeight / 6 + 3}>{value}</text>
          <line x1={glyphX + 18} y1={glyphY + index * (glyphHeight / 3) + glyphHeight / 6} x2={glyphX + glyphWidth - 8} y2={glyphY + glyphHeight / 2} />
        </g>)}
        <circle cx={glyphX + glyphWidth - 5} cy={glyphY + glyphHeight / 2} r={5} fill={fill} />
      </g>}
      {node.shape === "normalization" && detailed && <g className="node-glyph" stroke={colors.stroke}>
        <rect x={glyphX} y={glyphY} width={glyphWidth} height={glyphHeight} rx={glyphHeight / 2} fill={fill} />
        {[-0.26, 0, 0.26].map((ratio) => <line key={ratio} x1={glyphX + glyphWidth / 2 + ratio * glyphWidth} y1={glyphY + 8} x2={glyphX + glyphWidth / 2 + ratio * glyphWidth} y2={glyphY + glyphHeight - 8} />)}
        <text className="node-glyph-text" x={glyphX + glyphWidth / 2} y={glyphY + glyphHeight / 2 + 3}>μ σ</text>
      </g>}
      {!paperMode && node.shape === "operation" && width >= 100 && <g className="node-glyph operation-glyph" stroke={colors.stroke}>
        {[0, 1, 2].map((index) => <rect key={index} x={x + 10} y={y + 13 + index * 11} width={15 + index * 3} height={6} rx={1.5} fill={colors.stroke} />)}
      </g>}
      {!paperMode && visualStyle === "technical" && !symbol && <>
        <rect className="node-rail" x={x} y={y} width={5} height={height} rx={2} fill={colors.stroke} />
        <text className="node-kind" x={x + 13} y={y + 14}>{node.shape.toUpperCase()}</text>
      </>}
      <text className={`node-label ${symbol ? "symbol-label" : ""}`} x={symbol ? x + width / 2 : labelX} y={symbol ? y + height - 8 : titleY}>
        {lines.map((line, index) => <tspan key={`${line}-${index}`} x={symbol ? x + width / 2 : labelX} dy={index ? 16 : 0}>{line}</tspan>)}
      </text>
      {!symbol && visualStyle !== "compact" && height >= 58 && <text className="node-secondary" x={labelX} y={y + height - 11}>{node.secondary_label}</text>}
      <DetailToggle node={node} onToggle={onToggleDetail} />
      {selected && <rect className="node-selection" x={x - 5} y={y - 5} width={width + 10} height={height + 10} rx={7} />}
      {selected && resizeEnabled && <rect
        className="resize-handle"
        x={x + width - 5}
        y={y + height - 5}
        width={11}
        height={11}
        rx={2}
        onPointerDown={(event) => onResizePointerDown(event, node)}
      />}
    </g>
  );
}, nodeGraphicPropsEqual);

function labelPosition(route: RoutedEdge, style: EdgeLabelStyle): Point & { angle: number } {
  if (style !== "endpoint") return { x: route.labelPoint.x, y: route.labelPoint.y, angle: route.labelAngle };
  const end = route.points.at(-1)!;
  const previous = route.points.at(-2)!;
  const vertical = Math.abs(end.y - previous.y) > Math.abs(end.x - previous.x);
  return {
    x: end.x + (previous.x - end.x) * 0.48,
    y: end.y + (previous.y - end.y) * 0.48,
    angle: vertical ? -90 : 0,
  };
}

interface EdgeGraphicProps {
  route: RoutedEdge;
  labelStyle: EdgeLabelStyle;
  selected: boolean;
  onSelect: (edge: LabEdge) => void;
}

function edgeGraphicPropsEqual(first: EdgeGraphicProps, second: EdgeGraphicProps): boolean {
  return first.route.path === second.route.path
    && first.route.edge.scene_edge_id === second.route.edge.scene_edge_id
    && first.route.edge.source_scene_node_id === second.route.edge.source_scene_node_id
    && first.route.edge.target_scene_node_id === second.route.edge.target_scene_node_id
    && first.route.edge.label === second.route.edge.label
    && first.route.edge.relation === second.route.edge.relation
    && first.route.labelPoint.x === second.route.labelPoint.x
    && first.route.labelPoint.y === second.route.labelPoint.y
    && first.route.labelAngle === second.route.labelAngle
    && first.route.sourceSide === second.route.sourceSide
    && first.route.targetSide === second.route.targetSide
    && first.route.markerEnd === second.route.markerEnd
    && first.route.foreground === second.route.foreground
    && first.labelStyle === second.labelStyle
    && first.selected === second.selected
    && first.onSelect === second.onSelect;
}

const EdgeGraphic = memo(function EdgeGraphic({
  route,
  labelStyle,
  selected,
  onSelect,
}: EdgeGraphicProps) {
  const color = RELATION_COLORS[route.edge.relation];
  const labelPoint = labelPosition(route, labelStyle);
  const labelWidth = Math.max(42, Math.min(220, route.edge.label.length * 6.6 + 16));
  const dashed = route.edge.relation === "residual" || route.edge.relation === "feedback";
  return (
    <g className={`lab-edge relation-${route.edge.relation} ${selected ? "selected" : ""}`} data-edge-id={route.edge.scene_edge_id}>
      {selected && <path className="edge-selection" d={route.path} fill="none" />}
      <path className="edge-hit" d={route.path} fill="none" onPointerDown={(event) => { event.stopPropagation(); onSelect(route.edge); }} />
      <path
        className="edge-path"
        d={route.path}
        fill="none"
        stroke={color}
        strokeDasharray={dashed ? "7 5" : undefined}
        markerEnd={route.markerEnd === false ? undefined : `url(#arrow-${route.edge.relation})`}
      />
      <g className="edge-label-group" transform={`rotate(${labelPoint.angle} ${labelPoint.x} ${labelPoint.y})`}>
        {labelStyle === "plate" && <rect className="edge-label-plate" x={labelPoint.x - labelWidth / 2} y={labelPoint.y - 17} width={labelWidth} height={18} rx={3} />}
        <text className="edge-label" x={labelPoint.x} y={labelPoint.y - 4}>{route.edge.label}</text>
      </g>
    </g>
  );
}, edgeGraphicPropsEqual);

function MarkerDefinitions() {
  return <defs>
    {Object.entries(RELATION_COLORS).map(([relation, color]) => <marker key={relation} id={`arrow-${relation}`} viewBox="0 0 10 10" refX="8.8" refY="5" markerWidth="5.8" markerHeight="5.8" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill={color} />
    </marker>)}
    <marker id="internal-arrow" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="4.8" markerHeight="4.8" orient="auto">
      <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#68706a" />
    </marker>
    {Object.entries({ blue: "#3b789e", green: "#397b63", pink: "#a45d7d", orange: "#a5652e", violet: "#7156a0" }).map(([tone, color]) => <marker key={tone} id={`internal-arrow-${tone}`} viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="4.8" markerHeight="4.8" orient="auto">
      <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill={color} />
    </marker>)}
  </defs>;
}

function MetricStrip({ metrics }: { metrics: ReturnType<typeof measureScene> }) {
  return <div className="metric-strip" aria-label="当前方案指标">
    <span><b>{metrics.crossings}</b>交叉</span>
    <span><b>{metrics.overlaps}</b>重叠</span>
    <span><b>{metrics.nodeIntersections}</b>穿越</span>
    <span><b>{metrics.labelIntersections}</b>标签碰撞</span>
    <span><b>{metrics.clearanceViolations}</b>净距</span>
    <span><b>{metrics.endpointCongestion}</b>端口拥挤</span>
    <span><b>{metrics.reverseExits}</b>反向</span>
    <span><b>{metrics.sharedLength}</b>共享线长</span>
    <span><b>{metrics.bends}</b>折点</span>
    <span><b>{metrics.routeLength}</b>长度</span>
  </div>;
}

export interface SceneCanvasProps {
  scenes?: readonly LabScene[];
  initialSceneId?: string;
  productLabel?: string;
  collectionLabel?: string;
  toolbarContent?: ReactNode;
  selection?: Selection;
  readOnlySemantic?: boolean;
  onSceneChange?: (scene: LabScene) => void;
  onSelectionChange?: (selection: Selection, scene: LabScene) => void;
  onVisualPatch?: (patch: LabPatch, scene: LabScene) => void;
  onVisualPatchBatch?: (patches: readonly LabPatch[], scene: LabScene, description: string) => void;
  onPinNodes?: (sceneNodeIds: readonly string[], enabled: boolean, scene: LabScene) => void;
  pinnedNodeIds?: readonly string[];
  onUndo?: () => void;
  onRedo?: () => void;
  canUndo?: boolean;
  canRedo?: boolean;
  renderSourceInspector?: (node: LabNode) => ReactNode;
  onHierarchyExpand?: (hierarchyNodeId: string) => void;
  onHierarchyCollapse?: (hierarchyNodeId: string) => void;
  exportRaster?: (svg: string, format: "png" | "pdf") => Promise<Blob>;
}

export function App({
  scenes,
  initialSceneId,
  productLabel = "Scene Lab",
  collectionLabel = "压力场景",
  toolbarContent,
  selection: controlledSelection,
  readOnlySemantic = false,
  onSceneChange,
  onSelectionChange,
  onVisualPatch,
  onVisualPatchBatch,
  onPinNodes,
  pinnedNodeIds = [],
  onUndo,
  onRedo,
  canUndo,
  canRedo,
  renderSourceInspector,
  onHierarchyExpand,
  onHierarchyCollapse,
  exportRaster,
}: SceneCanvasProps = {}) {
  const availableScenes = scenes?.length ? scenes : EMPTY_WORKSPACE_SCENES;
  const initialSceneRef = useRef<LabScene>(initialScenario(availableScenes, initialSceneId));
  const initialExpandedRef = useRef<Set<string>>(initialExpandedNodeIds(initialSceneRef.current));
  const initialExpansionRef = useRef<DetailExpansionMap>(initialDetailExpansions(initialSceneRef.current, initialExpandedRef.current));
  const initialNestedSelection = Object.entries(initialExpansionRef.current)[0];
  const initialNestedChildId = initialNestedSelection
    ? detailExpansionChildren(initialNestedSelection[1])[0]?.[0]
    : undefined;
  const [editor, dispatch] = useReducer(editorReducer, {
    scene: cloneScene(initialSceneRef.current),
    past: [],
    future: [],
  });
  const [options, setOptions] = useState<VisualOptions>(() => visualOptionsForScene(initialSceneRef.current));
  const [hierarchyRoutingMode, setHierarchyRoutingMode] = useState<HierarchyRoutingMode>(() => (
    new URLSearchParams(window.location.search).get("hierarchy") === "recursive"
      ? "recursive"
      : "atomic-bottom-up"
  ));
  const [selection, setSelection] = useState<Selection>(null);
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
  const [preview, setPreview] = useState<{ nodeId: string; bounds: Bounds } | null>(null);
  const [detailLayouts, setDetailLayouts] = useState<DetailLayoutMap>({});
  const [detailPreview, setDetailPreview] = useState<DetailPreview | null>(null);
  const [detailSelection, setDetailSelection] = useState<DetailSelection | null>(() => initialNestedSelection && initialNestedChildId
    ? { rootId: initialNestedSelection[0], levelPath: [], childId: initialNestedChildId }
    : null);
  const [detailExpansions, setDetailExpansions] = useState<DetailExpansionMap>(() => initialExpansionRef.current);
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(() => new Set(initialExpandedRef.current));
  const [edgeMode, setEdgeMode] = useState(false);
  const [edgeSource, setEdgeSource] = useState<string | null>(null);
  const [camera, setCamera] = useState<CanvasCamera>({ x: 0, y: 0, zoom: 1 });
  const [isPanning, setIsPanning] = useState(false);
  const [isHierarchyPending, startHierarchyTransition] = useTransition();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const zoomOutputRef = useRef<HTMLOutputElement | null>(null);
  const gestureRef = useRef<Gesture | null>(null);
  const cameraGestureRef = useRef<CameraGesture | null>(null);
  const cameraRef = useRef(camera);
  const pendingCameraRef = useRef<CanvasCamera | null>(null);
  const cameraFrameRef = useRef<number | null>(null);
  const cameraCommitTimerRef = useRef<number | null>(null);
  const pendingGesturePreviewRef = useRef<PendingGesturePreview | null>(null);
  const gestureFrameRef = useRef<number | null>(null);

  useEffect(() => {
    if (controlledSelection !== undefined) setSelection(controlledSelection);
  }, [controlledSelection]);
  useEffect(() => {
    if (selection?.kind !== "node") {
      setSelectedNodeIds([]);
      return;
    }
    setSelectedNodeIds((current) => current.includes(selection.id) ? current : [selection.id]);
  }, [selection]);
  const pendingDetailPresentationRef = useRef<{
    presentation: DetailDragPresentation;
    dx: number;
    dy: number;
  } | null>(null);
  const detailPresentationFrameRef = useRef<number | null>(null);
  const detailTreeCacheRef = useRef(new Map<string, DetailTreeCacheEntry>());
  const lastMetricsRef = useRef<ReturnType<typeof measureScene> | null>(null);
  const pendingCameraFitRef = useRef(true);
  const pendingFocusNodeRef = useRef<string | null>(null);
  const sequence = useRef(1);

  useEffect(() => {
    const next = availableScenes.find((scene) => scene.scene_id === initialSceneId)
      ?? availableScenes.find((scene) => scene.scene_id === editor.scene.scene_id)
      ?? availableScenes[0];
    if (next && (
      next.scene_id !== editor.scene.scene_id
      || next.title !== editor.scene.title
      || next.nodes.length !== editor.scene.nodes.length
      || next.edges.length !== editor.scene.edges.length
    )) loadScene(next);
  }, [availableScenes, initialSceneId]);

  useEffect(() => {
    onSelectionChange?.(selection, editor.scene);
  }, [editor.scene, onSelectionChange, selection]);

  const displayScene = useMemo(() => {
    const previewScene = preview ? {
      ...editor.scene,
      nodes: editor.scene.nodes.map((node) => node.scene_node_id === preview.nodeId
        ? { ...node, bounds: preview.bounds }
        : node),
    } : editor.scene;
    const sizeOverrides = Object.fromEntries(previewScene.nodes.flatMap((node) => (
      node.detail_kind && expandedNodeIds.has(node.scene_node_id)
        ? [[node.scene_node_id, expandedDetailSize(node.detail_kind, detailExpansions[node.scene_node_id])]]
        : []
    )));
    return expandScene(previewScene, expandedNodeIds, sizeOverrides);
  }, [detailExpansions, editor.scene, expandedNodeIds, preview]);
  const effectiveDetailLayouts = useMemo(() => {
    if (!detailPreview) return detailLayouts;
    return {
      ...detailLayouts,
      [detailLevelKey(detailPreview.rootId, detailPreview.levelPath)]: {
        ...(detailLayouts[detailLevelKey(detailPreview.rootId, detailPreview.levelPath)] ?? {}),
        [detailPreview.childId]: detailPreview.offset,
      },
    };
  }, [detailLayouts, detailPreview]);
  const detailTrees = useMemo<Record<string, InlineDetailLevel>>(() => {
    const trees: Record<string, InlineDetailLevel> = {};
    const activeIds = new Set<string>();
    for (const node of displayScene.nodes) {
      if (!node.detail_expanded || !node.detail_kind) continue;
      activeIds.add(node.scene_node_id);
      const branch = detailExpansions[node.scene_node_id];
      const layouts = detailPreview?.rootId === node.scene_node_id
        ? effectiveDetailLayouts
        : detailLayouts;
      const cached = detailTreeCacheRef.current.get(node.scene_node_id);
      const changedLayoutKeys = cached ? changedDetailLevelKeys(cached.layouts, layouts) : undefined;
      if (cached
        && cached.kind === node.detail_kind
        && sameBounds(cached.bounds, node.bounds)
        && cached.branch === branch
        && changedLayoutKeys?.size === 0
        && cached.hierarchyRoutingMode === hierarchyRoutingMode) {
        trees[node.scene_node_id] = cached.tree;
        continue;
      }
      const tree = buildInlineDetailLayout(
        node.detail_kind,
        node.bounds,
        branch,
        layouts,
        node.scene_node_id,
        [],
        hierarchyRoutingMode,
        cached && cached.branch === branch && cached.hierarchyRoutingMode === hierarchyRoutingMode
          ? cached.tree
          : undefined,
        changedLayoutKeys,
      );
      trees[node.scene_node_id] = tree;
      detailTreeCacheRef.current.set(node.scene_node_id, {
        kind: node.detail_kind,
        bounds: { ...node.bounds },
        branch,
        layouts,
        hierarchyRoutingMode,
        tree,
      });
    }
    for (const nodeId of detailTreeCacheRef.current.keys()) {
      if (!activeIds.has(nodeId)) detailTreeCacheRef.current.delete(nodeId);
    }
    return trees;
  }, [detailExpansions, detailLayouts, detailPreview?.rootId, displayScene, effectiveDetailLayouts, hierarchyRoutingMode]);
  const atomicRoutingPlan = useMemo(() => {
    if (hierarchyRoutingMode !== "atomic-bottom-up") return undefined;
    return buildAtomicHierarchyRoutingPlan(
      detailTrees,
      new Set(displayScene.edges.map((edge) => edge.target_scene_node_id)),
      new Set(displayScene.edges.map((edge) => edge.source_scene_node_id)),
    );
  }, [detailTrees, displayScene.edges, hierarchyRoutingMode]);
  const boundaryPorts = atomicRoutingPlan?.boundaryPorts;
  const hiddenFlowIds = useStableSet(atomicRoutingPlan?.hiddenFlowIds);
  const foregroundFlowIds = useStableSet(atomicRoutingPlan?.foregroundFlowIds);
  const routed = useMemo(
    () => routeScene(displayScene, options.routeStyle, boundaryPorts),
    [boundaryPorts, displayScene, options.routeStyle],
  );
  const metrics = useMemo(() => {
    if ((preview || detailPreview) && lastMetricsRef.current) return lastMetricsRef.current;
    const next = measureScene(displayScene, routed);
    lastMetricsRef.current = next;
    return next;
  }, [detailPreview, displayScene, preview, routed]);
  const contentBounds = useMemo(() => sceneContentBounds(displayScene), [displayScene]);
  const selectedNode = selection?.kind === "node"
    ? editor.scene.nodes.find((node) => node.scene_node_id === selection.id)
    : undefined;
  const selectedEdge = selection?.kind === "edge"
    ? editor.scene.edges.find((edge) => edge.scene_edge_id === selection.id)
    : undefined;
  const selectedDetail = useMemo(() => {
    if (!detailSelection) return undefined;
    const root = displayScene.nodes.find((node) => node.scene_node_id === detailSelection.rootId);
    if (!root?.detail_kind || !root.detail_expanded) return undefined;
    const tree = detailTrees[root.scene_node_id];
    if (!tree) return undefined;
    const level = findInlineDetailLevel(tree, detailSelection.levelPath);
    const child = level?.nodes.find((item) => item.id === detailSelection.childId);
    return child && level ? { root, level, child } : undefined;
  }, [detailSelection, detailTrees, displayScene]);
  const selectedDetailOffset = detailSelection
    ? effectiveDetailLayouts[detailLevelKey(detailSelection.rootId, detailSelection.levelPath)]?.[detailSelection.childId] ?? { x: 0, y: 0 }
    : { x: 0, y: 0 };
  const selectedDetailExpanded = Boolean(selectedDetail && detailExpansionChildren(expansionAtLevel(
    detailExpansions[selectedDetail.root.scene_node_id],
    detailSelection?.levelPath ?? [],
  )).some(([id]) => id === selectedDetail.child.id));

  useEffect(() => {
    cameraRef.current = camera;
    applyCameraPresentation(camera);
  }, [camera]);

  useEffect(() => () => {
    if (cameraFrameRef.current !== null) cancelAnimationFrame(cameraFrameRef.current);
    if (gestureFrameRef.current !== null) cancelAnimationFrame(gestureFrameRef.current);
    if (detailPresentationFrameRef.current !== null) cancelAnimationFrame(detailPresentationFrameRef.current);
    if (cameraCommitTimerRef.current !== null) window.clearTimeout(cameraCommitTimerRef.current);
  }, []);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport || !pendingCameraFitRef.current) return;
    pendingCameraFitRef.current = false;
    setCamera(fitCanvasCamera(
      viewport.getBoundingClientRect(),
      contentBounds,
    ));
  }, [contentBounds, editor.scene.scene_id]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const handleWheel = (event: WheelEvent) => {
      const bounds = viewport.getBoundingClientRect();
      const anchor = { x: event.clientX - bounds.left, y: event.clientY - bounds.top };
      event.preventDefault();
      event.stopPropagation();
      const factor = wheelZoomFactor(event.deltaY, event.deltaMode);
      const current = pendingCameraRef.current ?? cameraRef.current;
      const next = zoomCameraAt(current, current.zoom * factor, anchor);
      scheduleCameraPresentation(next);
      if (cameraCommitTimerRef.current !== null) window.clearTimeout(cameraCommitTimerRef.current);
      cameraCommitTimerRef.current = window.setTimeout(() => {
        cameraCommitTimerRef.current = null;
        setCamera(cameraRef.current);
      }, 80);
    };
    viewport.addEventListener("wheel", handleWheel, { passive: false });
    return () => viewport.removeEventListener("wheel", handleWheel);
  }, []);

  function applyCameraPresentation(next: CanvasCamera) {
    cameraRef.current = next;
    if (svgRef.current) {
      svgRef.current.style.transform = `translate(${next.x}px, ${next.y}px) scale(${next.zoom})`;
    }
    if (viewportRef.current) {
      viewportRef.current.style.setProperty("--canvas-grid-size", `${canvasGridSize(next.zoom)}px`);
      viewportRef.current.style.setProperty("--canvas-grid-x", `${next.x}px`);
      viewportRef.current.style.setProperty("--canvas-grid-y", `${next.y}px`);
    }
    if (zoomOutputRef.current) zoomOutputRef.current.value = `${Math.round(next.zoom * 100)}%`;
  }

  function scheduleCameraPresentation(next: CanvasCamera) {
    cameraRef.current = next;
    pendingCameraRef.current = next;
    if (cameraFrameRef.current !== null) return;
    cameraFrameRef.current = requestAnimationFrame(() => {
      cameraFrameRef.current = null;
      const pending = pendingCameraRef.current;
      pendingCameraRef.current = null;
      if (pending) applyCameraPresentation(pending);
    });
  }

  function flushCameraPresentation(next: CanvasCamera) {
    if (cameraFrameRef.current !== null) cancelAnimationFrame(cameraFrameRef.current);
    cameraFrameRef.current = null;
    pendingCameraRef.current = null;
    applyCameraPresentation(next);
  }

  function scheduleGesturePreview(next: PendingGesturePreview) {
    pendingGesturePreviewRef.current = next;
    if (gestureFrameRef.current !== null) return;
    gestureFrameRef.current = requestAnimationFrame(() => {
      gestureFrameRef.current = null;
      const pending = pendingGesturePreviewRef.current;
      pendingGesturePreviewRef.current = null;
      if (pending?.kind === "node") setPreview(pending.value);
      else if (pending) setDetailPreview(pending.value);
    });
  }

  function cancelGesturePreview() {
    if (gestureFrameRef.current !== null) cancelAnimationFrame(gestureFrameRef.current);
    gestureFrameRef.current = null;
    pendingGesturePreviewRef.current = null;
  }

  function scheduleDetailPresentation(presentation: DetailDragPresentation, dx: number, dy: number) {
    pendingDetailPresentationRef.current = { presentation, dx, dy };
    if (detailPresentationFrameRef.current !== null) return;
    detailPresentationFrameRef.current = requestAnimationFrame(() => {
      detailPresentationFrameRef.current = null;
      const pending = pendingDetailPresentationRef.current;
      pendingDetailPresentationRef.current = null;
      if (pending) presentDetailDrag(pending.presentation, pending.dx, pending.dy);
    });
  }

  function finishDetailPresentation(presentation: DetailDragPresentation | undefined) {
    if (detailPresentationFrameRef.current !== null) cancelAnimationFrame(detailPresentationFrameRef.current);
    detailPresentationFrameRef.current = null;
    pendingDetailPresentationRef.current = null;
    resetDetailDragPresentation(presentation);
  }

  useEffect(() => {
    const nodeId = pendingFocusNodeRef.current;
    const viewport = viewportRef.current;
    const svg = svgRef.current;
    if (!nodeId || !viewport || !svg) return;
    const nodeElement = svg.querySelector<SVGGElement>(`[data-node-id="${nodeId}"]`);
    if (!nodeElement) return;
    pendingFocusNodeRef.current = null;
    const viewportBounds = viewport.getBoundingClientRect();
    const nodeBounds = nodeElement.getBoundingClientRect();
    setCamera((current) => ({
      ...current,
      x: current.x + viewportBounds.left + viewportBounds.width / 2 - nodeBounds.left - nodeBounds.width / 2,
      y: current.y + viewportBounds.top + viewportBounds.height / 2 - nodeBounds.top - nodeBounds.height / 2,
    }));
  }, [displayScene]);

  function fitCamera() {
    const viewport = viewportRef.current;
    if (!viewport) return;
    setCamera(fitCanvasCamera(
      viewport.getBoundingClientRect(),
      contentBounds,
    ));
  }

  function zoomFromCenter(factor: number) {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const bounds = viewport.getBoundingClientRect();
    setCamera((current) => zoomCameraAt(current, current.zoom * factor, {
      x: bounds.width / 2,
      y: bounds.height / 2,
    }));
  }

  function patch(next: LabPatch) {
    onVisualPatch?.(next, editor.scene);
    dispatch({ type: "patch", patch: next });
  }

  function patchBatch(patches: readonly LabPatch[], description: string) {
    if (!patches.length) return;
    onVisualPatchBatch?.(patches, editor.scene, description);
    dispatch({ type: "patch-batch", patches });
  }

  function selectedNodes(): LabNode[] {
    const ids = new Set(selectedNodeIds);
    return editor.scene.nodes.filter((node) => ids.has(node.scene_node_id));
  }

  function applyAlignment(command: AlignmentCommand) {
    const nodes = selectedNodes();
    const changes = alignNodeBounds(nodes, command, new Set(pinnedNodeIds));
    patchBatch([...changes].map(([nodeId, bounds]) => ({
      operation: "update-node" as const,
      nodeId,
      changes: { bounds },
      persistenceTargetId: persistenceTargetForNode(nodes.find((node) => node.scene_node_id === nodeId)),
    })), `Align selected nodes: ${command}`);
  }

  function applyDistribution(command: DistributionCommand) {
    const nodes = selectedNodes();
    const changes = distributeNodeBounds(nodes, command, new Set(pinnedNodeIds));
    patchBatch([...changes].map(([nodeId, bounds]) => ({
      operation: "update-node" as const,
      nodeId,
      changes: { bounds },
      persistenceTargetId: persistenceTargetForNode(nodes.find((node) => node.scene_node_id === nodeId)),
    })), `Distribute selected nodes: ${command}`);
  }

  function loadScene(scene: LabScene) {
    cancelGesturePreview();
    dispatch({ type: "load", scene });
    setSelection(null);
    setPreview(null);
    setDetailLayouts({});
    setDetailPreview(null);
    setDetailSelection(null);
    setDetailExpansions({});
    setExpandedNodeIds(new Set());
    setOptions(visualOptionsForScene(scene));
    const viewport = viewportRef.current;
    if (viewport) {
      pendingCameraFitRef.current = false;
      setCamera(fitCanvasCamera(
        viewport.getBoundingClientRect(),
        sceneContentBounds(scene),
      ));
    } else {
      pendingCameraFitRef.current = true;
    }
    cameraGestureRef.current = null;
    setIsPanning(false);
    setEdgeMode(false);
    setEdgeSource(null);
    onSceneChange?.(scene);
  }

  function beginNode(event: React.PointerEvent<SVGGElement>, node: LabNode) {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    setDetailSelection(null);
    if (event.shiftKey && !edgeMode) {
      const next = selectedNodeIds.includes(node.scene_node_id)
        ? selectedNodeIds.filter((id) => id !== node.scene_node_id)
        : [...selectedNodeIds, node.scene_node_id];
      setSelectedNodeIds(next);
      const primary = next.at(-1);
      setSelection(primary ? { kind: "node", id: primary } : null);
      return;
    }
    if (!selectedNodeIds.includes(node.scene_node_id)) setSelectedNodeIds([node.scene_node_id]);
    setSelection({ kind: "node", id: node.scene_node_id });
    if (edgeMode) {
      if (!edgeSource) {
        setEdgeSource(node.scene_node_id);
        return;
      }
      if (edgeSource !== node.scene_node_id) {
        const id = `edge-prototype-${Date.now().toString(36)}-${sequence.current++}`;
        patch({
          operation: "add-edge",
          edge: {
            scene_edge_id: id,
            source_scene_node_id: edgeSource,
            target_scene_node_id: node.scene_node_id,
            relation: "flow",
            label: "new flow",
          },
        });
        setSelection({ kind: "edge", id });
        setEdgeMode(false);
        setEdgeSource(null);
      }
      return;
    }
    if (pinnedNodeIds.includes(node.scene_node_id)) return;
    const svg = svgRef.current;
    if (!svg) return;
    svg.setPointerCapture(event.pointerId);
    gestureRef.current = {
      pointerId: event.pointerId,
      nodeId: node.scene_node_id,
      persistenceTargetId: persistenceTargetForNode(node),
      kind: "move",
      start: svgPoint(event as unknown as React.PointerEvent<SVGSVGElement>, svg),
      initial: editableNodeBounds(editor.scene, node),
    };
  }

  function beginDetailNode(
    event: React.PointerEvent<SVGGElement>,
    root: LabNode,
    levelPath: string[],
    level: InlineDetailLevel,
    child: DetailNode,
  ) {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    setSelection(null);
    setDetailSelection({ rootId: root.scene_node_id, levelPath, childId: child.id });
    const svg = svgRef.current;
    if (!svg || !root.detail_kind) return;
    const levelKey = detailLevelKey(root.scene_node_id, levelPath);
    const initialOffset = detailLayouts[levelKey]?.[child.id] ?? { x: 0, y: 0 };
    svg.setPointerCapture(event.pointerId);
    gestureRef.current = {
      pointerId: event.pointerId,
      rootId: root.scene_node_id,
      levelPath,
      levelKey,
      childId: child.id,
      kind: "detail-move",
      start: svgPoint(event as unknown as React.PointerEvent<SVGSVGElement>, svg),
      initialOffset,
      childBounds: {
        ...child.bounds,
        x: child.bounds.x - initialOffset.x,
        y: child.bounds.y - initialOffset.y,
      },
      parentBounds: detailLevelContentBounds(level),
      presentation: captureDetailDragPresentation(event.target, child.bounds),
    };
  }

  function beginResize(event: React.PointerEvent<SVGRectElement>, node: LabNode) {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    const svg = svgRef.current;
    if (!svg) return;
    svg.setPointerCapture(event.pointerId);
    gestureRef.current = {
      pointerId: event.pointerId,
      nodeId: node.scene_node_id,
      persistenceTargetId: persistenceTargetForNode(node),
      kind: "resize",
      start: svgPoint(event as unknown as React.PointerEvent<SVGSVGElement>, svg),
      initial: editableNodeBounds(editor.scene, node),
    };
  }

  function movePointer(event: React.PointerEvent<SVGSVGElement>) {
    const gesture = gestureRef.current;
    if (!gesture || gesture.pointerId !== event.pointerId) return;
    if (gesture.kind === "detail-move") {
      const point = svgPoint(event, event.currentTarget);
      const offset = clampDetailOffsetToBounds(gesture.parentBounds, gesture.childBounds, {
        x: gesture.initialOffset.x + point.x - gesture.start.x,
        y: gesture.initialOffset.y + point.y - gesture.start.y,
      });
      if (gesture.presentation) {
        scheduleDetailPresentation(
          gesture.presentation,
          offset.x - gesture.initialOffset.x,
          offset.y - gesture.initialOffset.y,
        );
        return;
      }
      scheduleGesturePreview({
        kind: "detail",
        value: { rootId: gesture.rootId, levelPath: gesture.levelPath, childId: gesture.childId, offset },
      });
      return;
    }
    scheduleGesturePreview({
      kind: "node",
      value: {
        nodeId: gesture.nodeId,
        bounds: nextGestureBounds(gesture, svgPoint(event, event.currentTarget), editor.scene),
      },
    });
  }

  function finishPointer(event: React.PointerEvent<SVGSVGElement>) {
    const gesture = gestureRef.current;
    if (!gesture || gesture.pointerId !== event.pointerId) return;
    if (gesture.kind === "detail-move") {
      const point = svgPoint(event, event.currentTarget);
      const offset = clampDetailOffsetToBounds(gesture.parentBounds, gesture.childBounds, {
        x: gesture.initialOffset.x + point.x - gesture.start.x,
        y: gesture.initialOffset.y + point.y - gesture.start.y,
      });
      gestureRef.current = null;
      finishDetailPresentation(gesture.presentation);
      cancelGesturePreview();
      setDetailPreview(null);
      setDetailLayouts((current) => ({
        ...current,
        [gesture.levelKey]: {
          ...(current[gesture.levelKey] ?? {}),
          [gesture.childId]: offset,
        },
      }));
      if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
      return;
    }
    const bounds = nextGestureBounds(gesture, svgPoint(event, event.currentTarget), editor.scene);
    gestureRef.current = null;
    cancelGesturePreview();
    setPreview(null);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    patch({
      operation: "update-node",
      nodeId: gesture.nodeId,
      changes: { bounds },
      persistenceTargetId: gesture.persistenceTargetId,
    });
  }

  function beginCameraPan(event: React.PointerEvent<HTMLDivElement>) {
    const isEmptySurface = event.target === event.currentTarget || event.target === svgRef.current;
    if (!shouldBeginCanvasPan(event.button, isEmptySurface, edgeMode)) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    cameraGestureRef.current = {
      pointerId: event.pointerId,
      start: { x: event.clientX, y: event.clientY },
      initial: cameraRef.current,
    };
    setIsPanning(true);
    setSelection(null);
    setDetailSelection(null);
  }

  function moveCameraPan(event: React.PointerEvent<HTMLDivElement>) {
    const gesture = cameraGestureRef.current;
    if (!gesture || gesture.pointerId !== event.pointerId) return;
    scheduleCameraPresentation({
      ...gesture.initial,
      x: gesture.initial.x + event.clientX - gesture.start.x,
      y: gesture.initial.y + event.clientY - gesture.start.y,
    });
  }

  function finishCameraPan(event: React.PointerEvent<HTMLDivElement>) {
    const gesture = cameraGestureRef.current;
    if (!gesture || gesture.pointerId !== event.pointerId) return;
    const next = {
      ...gesture.initial,
      x: gesture.initial.x + event.clientX - gesture.start.x,
      y: gesture.initial.y + event.clientY - gesture.start.y,
    };
    cameraGestureRef.current = null;
    flushCameraPresentation(next);
    setCamera(next);
    setIsPanning(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }

  function addNode() {
    const index = sequence.current++;
    const id = `node-prototype-${Date.now().toString(36)}-${index}`;
    const width = 152;
    const height = 72;
    patch({
      operation: "add-node",
      node: {
        scene_node_id: id,
        bounds: {
          x: editor.scene.paper_width / 2 - width / 2 + (index % 4) * 16,
          y: editor.scene.paper_height / 2 - height / 2 + (index % 3) * 14,
          width,
          height,
        },
        shape: "operation",
        label: "New operation",
        secondary_label: "prototype node",
      },
    });
    setSelection({ kind: "node", id });
  }

  function removeSelection() {
    if (!selection) return;
    patch(selection.kind === "node"
      ? { operation: "remove-node", nodeId: selection.id }
      : { operation: "remove-edge", edgeId: selection.id });
    if (selection.kind === "node") {
      setExpandedNodeIds((current) => {
        const next = new Set(current);
        next.delete(selection.id);
        return next;
      });
    }
    setSelection(null);
  }

  function toggleNodeDetail(nodeId: string) {
    const collapsing = expandedNodeIds.has(nodeId);
    if (collapsing) {
      if (detailSelection?.rootId === nodeId) setDetailSelection(null);
      setDetailExpansions((current) => {
        const next = { ...current };
        delete next[nodeId];
        return next;
      });
    }
    const updateExpansion = () => {
      setExpandedNodeIds((current) => {
        const next = new Set(current);
        if (next.has(nodeId)) next.delete(nodeId);
        else {
          next.add(nodeId);
          pendingFocusNodeRef.current = nodeId;
        }
        return next;
      });
    };
    if (collapsing) updateExpansion();
    else startHierarchyTransition(updateExpansion);
    setSelection({ kind: "node", id: nodeId });
    setPreview(null);
  }

  function toggleNestedDetail(root: LabNode, levelPath: string[], child: DetailNode) {
    if (!child.nestedKind) return;
    const collapsing = detailExpansionChildren(expansionAtLevel(
      detailExpansions[root.scene_node_id],
      levelPath,
    )).some(([id]) => id === child.id);
    setSelection(null);
    setDetailSelection({ rootId: root.scene_node_id, levelPath, childId: child.id });
    const updateExpansion = () => {
      setDetailExpansions((current) => {
        const nextBranch = toggleDetailExpansionAtPath(current[root.scene_node_id], levelPath, child.id);
        if (!detailExpansionChildren(nextBranch).length) {
          const next = { ...current };
          delete next[root.scene_node_id];
          return next;
        }
        return { ...current, [root.scene_node_id]: nextBranch };
      });
    };
    if (collapsing) updateExpansion();
    else startHierarchyTransition(updateExpansion);
  }

  function expandAllDetails() {
    const expandable = editor.scene.nodes.filter((node) => node.detail_kind);
    const nextExpansions = Object.fromEntries(expandable.map((node) => [
      node.scene_node_id,
      fullyExpandedDetailTree(node.detail_kind!),
    ]));
    startHierarchyTransition(() => {
      setExpandedNodeIds(new Set(expandable.map((node) => node.scene_node_id)));
      setDetailExpansions(nextExpansions);
      setSelection(null);
      setDetailSelection(null);
      setPreview(null);
      setDetailPreview(null);
    });
    pendingCameraFitRef.current = true;
  }

  function collapseAllDetails() {
    setExpandedNodeIds(new Set());
    setDetailExpansions({});
    setSelection(null);
    setDetailSelection(null);
    setPreview(null);
    setDetailPreview(null);
    pendingCameraFitRef.current = true;
  }

  function updateSelectedDetailOffset(nextOffset: Point) {
    if (!selectedDetail) return;
    const levelKey = detailLevelKey(selectedDetail.root.scene_node_id, detailSelection?.levelPath ?? []);
    const currentOffset = detailLayouts[levelKey]?.[selectedDetail.child.id] ?? { x: 0, y: 0 };
    const baseChild = {
      ...selectedDetail.child.bounds,
      x: selectedDetail.child.bounds.x - currentOffset.x,
      y: selectedDetail.child.bounds.y - currentOffset.y,
    };
    const offset = clampDetailOffsetToBounds(
      detailLevelContentBounds(selectedDetail.level),
      baseChild,
      nextOffset,
    );
    setDetailLayouts((current) => ({
      ...current,
      [levelKey]: {
        ...(current[levelKey] ?? {}),
        [selectedDetail.child.id]: offset,
      },
    }));
  }

  function resetSelectedDetailOffset() {
    if (!selectedDetail) return;
    const levelKey = detailLevelKey(selectedDetail.root.scene_node_id, detailSelection?.levelPath ?? []);
    setDetailLayouts((current) => ({
      ...current,
      [levelKey]: {
        ...(current[levelKey] ?? {}),
        [selectedDetail.child.id]: { x: 0, y: 0 },
      },
    }));
  }

  function resetScene() {
    const scenario = availableScenes.find((item) => item.scene_id === editor.scene.scene_id) ?? availableScenes[0];
    loadScene(scenario);
  }

  async function exportCurrent() {
    const { svg, metrics: exportMetrics } = renderSceneSvg(
      displayScene,
      options,
      detailLayouts,
      detailExpansions,
      hierarchyRoutingMode,
    );
    const payload = JSON.stringify({
      scene: displayScene,
      options,
      expandedNodeIds: [...expandedNodeIds],
      detailLayouts,
      detailExpansions,
      hierarchyRoutingMode,
      metrics: exportMetrics,
      svg,
    }, null, 2);
    const basename = `${editor.scene.scene_id}-${options.routeStyle}-${options.nodeStyle}-${options.labelStyle}`;
    const download = (content: string | Blob, type: string, extension: string) => {
      const blob = content instanceof Blob ? content : new Blob([content], { type });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${basename}.${extension}`;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    };
    download(svg, "image/svg+xml", "svg");
    download(payload, "application/json", "json");
    if (exportRaster) {
      const [png, pdf] = await Promise.all([
        exportRaster(svg, "png"),
        exportRaster(svg, "pdf"),
      ]);
      download(png, "image/png", "png");
      download(pdf, "application/pdf", "pdf");
    }
  }

  function updateNode(changes: Partial<Omit<LabNode, "scene_node_id">>) {
    if (!selectedNode) return;
    patch({
      operation: "update-node",
      nodeId: selectedNode.scene_node_id,
      changes,
      persistenceTargetId: persistenceTargetForNode(selectedNode),
    });
  }

  function updateEdge(changes: Partial<Omit<LabEdge, "scene_edge_id">>) {
    if (!selectedEdge) return;
    patch({ operation: "update-edge", edgeId: selectedEdge.scene_edge_id, changes });
  }

  function selectEdge(edge: LabEdge) {
    setSelection({ kind: "edge", id: edge.scene_edge_id });
  }

  const handleNodePointerDown = useLatestEvent(beginNode);
  const handleResizePointerDown = useLatestEvent(beginResize);
  const handleToggleNodeDetail = useLatestEvent(toggleNodeDetail);
  const handleDetailPointerDown = useLatestEvent(beginDetailNode);
  const handleToggleNestedDetail = useLatestEvent(toggleNestedDetail);
  const handleSelectEdge = useLatestEvent(selectEdge);

  const paperMode = editor.scene.layout_profile === "paper";
  const selectedPins = selectedNodeIds.filter((id) => pinnedNodeIds.includes(id));
  const selectedNodesPinned = selectedNodeIds.length > 0 && selectedPins.length === selectedNodeIds.length;
  return <div className={`scene-lab ${paperMode ? "paper-layout" : ""}`}>
    <header className="lab-topbar">
      <div className="lab-product"><Waypoints size={17} /><strong>ArchCanvas</strong><span>{productLabel}</span></div>
      {toolbarContent}
      <div className="toolbar-group" aria-label="编辑操作">
        <button className="tool-button" disabled={readOnlySemantic} onClick={addNode}><Plus size={15} />节点</button>
        <button
          className={`tool-button ${edgeMode ? "active" : ""}`}
          aria-pressed={edgeMode}
          disabled={readOnlySemantic}
          onClick={() => { setEdgeMode((value) => !value); setEdgeSource(null); }}
        ><ArrowRightLeft size={15} />连线</button>
        <button className="icon-button" title="删除所选" disabled={!selection || readOnlySemantic} onClick={removeSelection}><Trash2 size={15} /></button>
      </div>
      <div className="toolbar-group" aria-label="历史操作">
        <button className="icon-button" title="撤销" disabled={!editor.past.length && !canUndo} onClick={() => { dispatch({ type: "undo" }); onUndo?.(); }}><Undo2 size={15} /></button>
        <button className="icon-button" title="重做" disabled={!editor.future.length && !canRedo} onClick={() => { dispatch({ type: "redo" }); onRedo?.(); }}><Redo2 size={15} /></button>
        <button className="icon-button" title="重置当前案例" onClick={resetScene}><RotateCcw size={15} /></button>
      </div>
      {selectedNodeIds.length ? <div className="toolbar-group layout-command-group" role="group" aria-label="对齐、分布与固定">
        <span>{selectedNodeIds.length} 已选</span>
        <button className="icon-button" title="左对齐" disabled={selectedNodeIds.length < 2} onClick={() => applyAlignment("left")}><AlignHorizontalJustifyStart size={14} /></button>
        <button className="icon-button" title="水平居中对齐" disabled={selectedNodeIds.length < 2} onClick={() => applyAlignment("horizontal-center")}><AlignVerticalJustifyStart size={14} /></button>
        <button className="icon-button" title="顶端对齐" disabled={selectedNodeIds.length < 2} onClick={() => applyAlignment("top")}><AlignVerticalJustifyStart size={14} /></button>
        <button className="icon-button" title="垂直居中对齐" disabled={selectedNodeIds.length < 2} onClick={() => applyAlignment("vertical-center")}><AlignHorizontalJustifyStart size={14} /></button>
        <button className="icon-button" title="水平等距分布" disabled={selectedNodeIds.length < 3} onClick={() => applyDistribution("horizontal")}><AlignHorizontalSpaceAround size={14} /></button>
        <button className="icon-button" title="垂直等距分布" disabled={selectedNodeIds.length < 3} onClick={() => applyDistribution("vertical")}><AlignVerticalSpaceAround size={14} /></button>
        <button className="icon-button" title={selectedNodesPinned ? "取消固定所选节点" : "固定所选节点"} onClick={() => onPinNodes?.(selectedNodeIds, !selectedNodesPinned, editor.scene)}>{selectedNodesPinned ? <PinOff size={14} /> : <Pin size={14} />}</button>
      </div> : null}
      <div className="toolbar-spacer" />
      {edgeMode && <span className="edge-mode-status">{edgeSource ? "选择终点" : "选择起点"}</span>}
      <a className="tool-button" href="./cases/index.html" target="_blank" rel="noreferrer"><GalleryVerticalEnd size={15} />案例矩阵</a>
      <button className="tool-button" onClick={() => void exportCurrent()}><Download size={15} />{exportRaster ? "导出 SVG/PNG/PDF/JSON" : "导出 SVG/JSON"}</button>
    </header>

    <main className="lab-workspace">
      <aside className="case-panel">
        <div className="panel-heading"><GalleryVerticalEnd size={15} /><strong>{collectionLabel}</strong><span>{availableScenes.length}</span></div>
        <div className="case-list">
          {availableScenes.map((scenario) => <button
            key={scenario.scene_id}
            className={scenario.scene_id === editor.scene.scene_id ? "active" : ""}
            onClick={() => loadScene(scenario)}
          >
            <strong>{scenario.title}</strong>
            <span>{scenario.nodes.length} 节点 · {scenario.edges.length} 连线</span>
          </button>)}
        </div>
      </aside>

      <section className="canvas-column">
        <div className="variant-toolbar">
          <label>布线<select value={options.routeStyle} onChange={(event) => setOptions((current) => ({ ...current, routeStyle: event.target.value as RouteStyle }))}>
            {ROUTE_STYLES.map((style) => <option key={style} value={style}>{ROUTE_NAMES[style]}</option>)}
          </select></label>
          <label>节点<select value={options.nodeStyle} onChange={(event) => setOptions((current) => ({ ...current, nodeStyle: event.target.value as NodeVisualStyle }))}>
            {NODE_STYLES.map((style) => <option key={style} value={style}>{NODE_STYLE_NAMES[style]}</option>)}
          </select></label>
          <label>标签<select value={options.labelStyle} onChange={(event) => setOptions((current) => ({ ...current, labelStyle: event.target.value as EdgeLabelStyle }))}>
            {LABEL_STYLES.map((style) => <option key={style} value={style}>{LABEL_STYLE_NAMES[style]}</option>)}
          </select></label>
          <label>层级<select value={hierarchyRoutingMode} onChange={(event) => setHierarchyRoutingMode(event.target.value as HierarchyRoutingMode)}>
            <option value="atomic-bottom-up">原子收束</option>
            <option value="recursive">逐层</option>
          </select></label>
          <div className="detail-bulk-actions" aria-label="层级展开操作" aria-busy={isHierarchyPending}>
            <button className="tool-button" onClick={expandAllDetails} disabled={isHierarchyPending}><Plus size={14} />全部展开</button>
            <button className="tool-button" onClick={collapseAllDetails} disabled={isHierarchyPending || !expandedNodeIds.size}><Minus size={14} />全部收起</button>
          </div>
          <div className="scene-caption"><strong>{editor.scene.title}</strong><span>{editor.scene.description}</span></div>
        </div>
        <div
          ref={viewportRef}
          className={`canvas-viewport ${isPanning ? "panning" : ""}`}
          style={{
            "--canvas-grid-size": `${canvasGridSize(camera.zoom)}px`,
            "--canvas-grid-x": `${camera.x}px`,
            "--canvas-grid-y": `${camera.y}px`,
          } as React.CSSProperties}
          onPointerDown={beginCameraPan}
          onPointerMove={moveCameraPan}
          onPointerUp={finishCameraPan}
          onPointerCancel={finishCameraPan}
          onAuxClick={(event) => event.preventDefault()}
          onDragStart={(event) => event.preventDefault()}
        >
          <svg
            ref={svgRef}
            className={`lab-canvas ${edgeMode ? "edge-mode" : ""}`}
            width={displayScene.paper_width}
            height={displayScene.paper_height}
            style={{ transform: `translate(${camera.x}px, ${camera.y}px) scale(${camera.zoom})` }}
            viewBox={`0 0 ${displayScene.paper_width} ${displayScene.paper_height}`}
            role="application"
            aria-label={`${displayScene.title} 架构图编辑画布`}
            onPointerMove={movePointer}
            onPointerUp={finishPointer}
            onPointerCancel={finishPointer}
          >
            <MarkerDefinitions />
            {routed.filter((route) => !route.foreground).map((route) => <EdgeGraphic
              key={route.edge.scene_edge_id}
              route={route}
              labelStyle={options.labelStyle}
              selected={selection?.kind === "edge" && selection.id === route.edge.scene_edge_id}
              onSelect={handleSelectEdge}
            />)}
            {displayScene.nodes.map((node) => <NodeGraphic
              key={node.scene_node_id}
              node={node}
              visualStyle={options.nodeStyle}
              paperMode={paperMode}
              selected={selectedNodeIds.includes(node.scene_node_id)}
              connecting={edgeSource === node.scene_node_id}
              onPointerDown={handleNodePointerDown}
              onResizePointerDown={handleResizePointerDown}
              onToggleDetail={handleToggleNodeDetail}
              detailTree={detailTrees[node.scene_node_id]}
              detailSelection={detailSelection?.rootId === node.scene_node_id ? detailSelection : undefined}
              onDetailPointerDown={handleDetailPointerDown}
              onToggleNestedDetail={handleToggleNestedDetail}
              resizeEnabled={!pinnedNodeIds.includes(node.scene_node_id)}
              hiddenFlowIds={hiddenFlowIds}
              foregroundFlowIds={foregroundFlowIds}
            />)}
            {routed.filter((route) => route.foreground).map((route) => <EdgeGraphic
              key={route.edge.scene_edge_id}
              route={route}
              labelStyle={options.labelStyle}
              selected={selection?.kind === "edge" && selection.id === route.edge.scene_edge_id}
              onSelect={handleSelectEdge}
            />)}
          </svg>
          <div className="canvas-controls" aria-label="画布视图">
            <button className="icon-button" title="缩小" onClick={() => zoomFromCenter(1 / 1.2)}><Minus size={15} /></button>
            <output ref={zoomOutputRef} aria-label="当前缩放比例">{Math.round(camera.zoom * 100)}%</output>
            <button className="icon-button" title="放大" onClick={() => zoomFromCenter(1.2)}><Plus size={15} /></button>
            <button className="icon-button" title="适合视图" onClick={fitCamera}><Maximize2 size={15} /></button>
          </div>
        </div>
        <MetricStrip metrics={metrics} />
      </section>

      <aside className="inspector-panel">
        <div className="panel-heading"><Maximize2 size={15} /><strong>检查器</strong></div>
        {selectedDetail ? <div className="inspector-form">
          <div className="selection-title"><span>父模块内子模块</span><strong>{selectedDetail.child.label}</strong></div>
          <label>根模块<input value={selectedDetail.root.label} readOnly /></label>
          <label>所在层级<input value={detailSelection?.levelPath.length ? `第 ${(detailSelection?.levelPath.length ?? 0) + 1} 层` : "父模块直属"} readOnly /></label>
          <label>结构类型<input value={selectedDetail.child.nestedKind ? DETAIL_KIND_NAMES[selectedDetail.child.nestedKind] : "原子图元"} readOnly /></label>
          <div className="field-grid">
            <label>X<input
              type="number"
              value={Math.round(selectedDetail.child.bounds.x)}
              onChange={(event) => updateSelectedDetailOffset({
                x: selectedDetailOffset.x + Number(event.target.value) - selectedDetail.child.bounds.x,
                y: selectedDetailOffset.y,
              })}
            /></label>
            <label>Y<input
              type="number"
              value={Math.round(selectedDetail.child.bounds.y)}
              onChange={(event) => updateSelectedDetailOffset({
                x: selectedDetailOffset.x,
                y: selectedDetailOffset.y + Number(event.target.value) - selectedDetail.child.bounds.y,
              })}
            /></label>
          </div>
          {selectedDetail.child.nestedKind && <button
            className="tool-button inspector-action"
            onClick={() => toggleNestedDetail(selectedDetail.root, detailSelection?.levelPath ?? [], selectedDetail.child)}
          ><Maximize2 size={14} />{selectedDetailExpanded ? "收起当前层" : "展开下一层"}</button>}
          <button className="tool-button inspector-action" onClick={resetSelectedDetailOffset}><RotateCcw size={14} />复位子模块位置</button>
        </div> : selectedNode ? <div className="inspector-form">
          <div className="selection-title"><span>节点</span><strong>{selectedNode.label}</strong></div>
          <label>名称<input disabled={Boolean(selectedNode.canonical_node_ids?.length)} value={selectedNode.label} onChange={(event) => updateNode({ label: event.target.value })} /></label>
          <label>副标题<input disabled={Boolean(selectedNode.canonical_node_ids?.length)} value={selectedNode.secondary_label} onChange={(event) => updateNode({ secondary_label: event.target.value })} /></label>
          <label>形状<select disabled={Boolean(selectedNode.canonical_node_ids?.length)} value={selectedNode.shape} onChange={(event) => updateNode({ shape: event.target.value as NodeShape })}>
            {NODE_SHAPES.map((shape) => <option key={shape} value={shape}>{NODE_SHAPE_NAMES[shape]}</option>)}
          </select></label>
          <div className="field-grid">
            <label>宽度<input type="number" min={72} max={320} value={Math.round(selectedNode.bounds.width)} onChange={(event) => updateNode({ bounds: clampBounds({ ...selectedNode.bounds, width: Number(event.target.value) }, editor.scene) })} /></label>
            <label>高度<input type="number" min={42} max={180} value={Math.round(selectedNode.bounds.height)} onChange={(event) => updateNode({ bounds: clampBounds({ ...selectedNode.bounds, height: Number(event.target.value) }, editor.scene) })} /></label>
            <label>X<input type="number" value={Math.round(selectedNode.bounds.x)} onChange={(event) => updateNode({ bounds: clampBounds({ ...selectedNode.bounds, x: Number(event.target.value) }, editor.scene) })} /></label>
            <label>Y<input type="number" value={Math.round(selectedNode.bounds.y)} onChange={(event) => updateNode({ bounds: clampBounds({ ...selectedNode.bounds, y: Number(event.target.value) }, editor.scene) })} /></label>
          </div>
          {selectedNode.canonical_node_ids?.length ? <section className="source-binding-summary">
            <strong>源码绑定</strong>
            <code>{selectedNode.canonical_node_ids.join("\n")}</code>
            <span>{selectedNode.fidelity ?? "exact"} · {selectedNode.evidence_ids?.length ?? 0} 条证据</span>
          </section> : null}
          {renderSourceInspector?.(selectedNode)}
          {selectedNode.hierarchy_expandable && selectedNode.hierarchy_node_id ? <button
            className="tool-button inspector-action"
            onClick={() => onHierarchyExpand?.(selectedNode.hierarchy_node_id!)}
          ><Plus size={14} />展开源码层级</button> : null}
          {selectedNode.parent_hierarchy_node_id ? <button
            className="tool-button inspector-action"
            onClick={() => onHierarchyCollapse?.(selectedNode.parent_hierarchy_node_id!)}
          ><Minus size={14} />收起父层级</button> : null}
          <button className="danger-button" disabled={readOnlySemantic} onClick={removeSelection}><Trash2 size={14} />删除节点及关联连线</button>
        </div> : selectedEdge ? <div className="inspector-form">
          <div className="selection-title"><span>连线</span><strong>{selectedEdge.label}</strong></div>
          <label>标签<input value={selectedEdge.label} onChange={(event) => updateEdge({ label: event.target.value })} /></label>
          <label>关系<select value={selectedEdge.relation} onChange={(event) => updateEdge({ relation: event.target.value as EdgeRelation })}>
            {EDGE_RELATIONS.map((relation) => <option key={relation} value={relation}>{EDGE_RELATION_NAMES[relation]}</option>)}
          </select></label>
          <label>起点<select value={selectedEdge.source_scene_node_id} onChange={(event) => updateEdge({ source_scene_node_id: event.target.value })}>
            {editor.scene.nodes.filter((node) => node.scene_node_id !== selectedEdge.target_scene_node_id).map((node) => <option key={node.scene_node_id} value={node.scene_node_id}>{node.label}</option>)}
          </select></label>
          <label>终点<select value={selectedEdge.target_scene_node_id} onChange={(event) => updateEdge({ target_scene_node_id: event.target.value })}>
            {editor.scene.nodes.filter((node) => node.scene_node_id !== selectedEdge.source_scene_node_id).map((node) => <option key={node.scene_node_id} value={node.scene_node_id}>{node.label}</option>)}
          </select></label>
          <button className="danger-button" disabled={readOnlySemantic} onClick={removeSelection}><Trash2 size={14} />删除连线</button>
        </div> : <div className="empty-inspector">
          <Waypoints size={20} />
          <strong>{editor.scene.nodes.length} 个节点</strong>
          <span>{editor.scene.edges.length} 条连线</span>
          <span>{options.routeStyle} · {options.nodeStyle} · {options.labelStyle} · {hierarchyRoutingMode}</span>
        </div>}
      </aside>
    </main>
  </div>;
}

export default App;
