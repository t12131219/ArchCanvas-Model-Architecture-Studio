import {
  ArrowRightLeft,
  Download,
  GalleryVerticalEnd,
  Maximize2,
  Minus,
  Plus,
  Redo2,
  RotateCcw,
  Trash2,
  Undo2,
  Waypoints,
} from "lucide-react";
import { useEffect, useMemo, useReducer, useRef, useState } from "react";

import { applyVisualPatch, clampBounds, cloneScene } from "./model";
import { expandScene } from "./expansion";
import {
  buildAtomicHierarchyProjection,
  projectedAtomicExit,
  projectedNestedExitBridgeIds,
  projectedSceneBoundaryPorts,
} from "./atomic-hierarchy";
import {
  buildInlineDetailLayout,
  clampDetailOffset,
  detailLevelKey,
  expandedDetailSize,
  findInlineDetailLevel,
  listDetailNodes,
} from "./detail-layout";
import type {
  DetailExpansionBranch,
  DetailExpansionMap,
  DetailLayoutMap,
  DetailNode,
  InlineDetailLevel,
} from "./detail-layout";
import { buildModuleDetail, DETAIL_KIND_NAMES } from "./module-details";
import type { DetailPrimitive } from "./module-details";
import {
  DEFAULT_OPTIONS,
  LABEL_STYLES,
  LABEL_STYLE_NAMES,
  NODE_STYLES,
  NODE_STYLE_NAMES,
  ROUTE_NAMES,
  ROUTE_STYLES,
  SCENARIOS,
} from "./scenarios";
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
  | { type: "undo" }
  | { type: "redo" };

interface NodeGesture {
  pointerId: number;
  nodeId: string;
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

function initialScenario(): LabScene {
  const sceneId = typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("scene");
  return SCENARIOS.find((scene) => scene.scene_id === sceneId) ?? SCENARIOS[0];
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
    if (child) return { [parent.scene_node_id]: { childId: child.id } };
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
    graphic = <g className={`detail-shape detail-tone-${primitive.tone} detail-${primitive.variant ?? "box"}`}>
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
    if (current?.childId !== childId) return undefined;
    current = current.child;
  }
  return current;
}

function RecursiveDetailLevelGraphic({
  root,
  level,
  levelPath,
  selection,
  onChildPointerDown,
  onToggleNested,
  hiddenFlowIds,
}: {
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
}) {
  const nodesByIndex = new Map(level.nodes.map((child) => [child.primitiveIndex, child]));
  const expanded = level.expandedChild;
  return <g className={`detail-level detail-${level.kind}`} data-detail-level={level.levelKey}>
    {expanded && <InlineExpandedDetailGraphic
      root={root}
      parentLevel={level}
      levelPath={levelPath}
      selection={selection}
      onChildPointerDown={onChildPointerDown}
      onToggleNested={onToggleNested}
      hiddenFlowIds={hiddenFlowIds}
    />}
    {level.diagram.primitives.map((primitive, index) => {
      const child = nodesByIndex.get(index);
      const atomicEdgeId = primitive.kind === "flow" ? `${level.levelKey}:flow:${index}` : undefined;
      if (expanded && child?.id === expanded.node.id) return null;
      if (atomicEdgeId && hiddenFlowIds?.has(atomicEdgeId)) return null;
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
    })}
  </g>;
}

function InlineExpandedDetailGraphic({
  root,
  parentLevel,
  levelPath,
  selection,
  onChildPointerDown,
  onToggleNested,
  hiddenFlowIds,
}: {
  root: LabNode;
  parentLevel: InlineDetailLevel;
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
}) {
  const expanded = parentLevel.expandedChild!;
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
    />
    <rect className="nested-inline-header" x={x} y={y} width={width} height={42} rx={5} />
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

function NodeGraphic({
  node,
  visualStyle,
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
}: {
  node: LabNode;
  visualStyle: NodeVisualStyle;
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
}) {
  const { x, y, width, height } = node.bounds;
  const colors = NODE_COLORS[node.shape];
  const fill = visualStyle === "compact" ? "#ffffff" : colors.fill;
  const polygon = polygonPoints(node);
  const symbol = node.shape === "add" ? "+" : node.shape === "multiply" ? "×" : node.shape === "concat" ? "||" : null;
  const detailed = ["tensor", "convolution", "attention", "normalization"].includes(node.shape) && width >= 110;
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
      className={`lab-node expanded-node ${selected ? "selected" : ""} ${connecting ? "connecting" : ""}`}
      data-node-id={node.scene_node_id}
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
      />
      <DetailToggle node={node} onToggle={onToggleDetail} />
      {selected && <rect className="node-selection" x={x - 5} y={y - 5} width={width + 10} height={height + 10} rx={8} />}
    </g>;
  }
  return (
    <g
      className={`lab-node node-${visualStyle} ${selected ? "selected" : ""} ${connecting ? "connecting" : ""}`}
      data-node-id={node.scene_node_id}
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
          rx={node.shape === "io" ? Math.min(26, height / 2) : node.shape === "normalization" ? 14 : 5}
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
      {node.shape === "operation" && width >= 100 && <g className="node-glyph operation-glyph" stroke={colors.stroke}>
        {[0, 1, 2].map((index) => <rect key={index} x={x + 10} y={y + 13 + index * 11} width={15 + index * 3} height={6} rx={1.5} fill={colors.stroke} />)}
      </g>}
      {visualStyle === "technical" && !symbol && <>
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
}

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

function EdgeGraphic({
  route,
  labelStyle,
  selected,
  onSelect,
}: {
  route: RoutedEdge;
  labelStyle: EdgeLabelStyle;
  selected: boolean;
  onSelect: (edge: LabEdge) => void;
}) {
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
}

function MarkerDefinitions() {
  return <defs>
    <pattern id="lab-grid" width="20" height="20" patternUnits="userSpaceOnUse">
      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#dfe3e1" strokeWidth={0.7} />
    </pattern>
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

function App() {
  const initialSceneRef = useRef<LabScene>(initialScenario());
  const initialExpandedRef = useRef<Set<string>>(initialExpandedNodeIds(initialSceneRef.current));
  const initialExpansionRef = useRef<DetailExpansionMap>(initialDetailExpansions(initialSceneRef.current, initialExpandedRef.current));
  const initialNestedSelection = Object.entries(initialExpansionRef.current)[0];
  const [editor, dispatch] = useReducer(editorReducer, {
    scene: cloneScene(initialSceneRef.current),
    past: [],
    future: [],
  });
  const [options, setOptions] = useState<VisualOptions>(DEFAULT_OPTIONS);
  const [hierarchyRoutingMode, setHierarchyRoutingMode] = useState<HierarchyRoutingMode>(() => (
    new URLSearchParams(window.location.search).get("hierarchy") === "recursive"
      ? "recursive"
      : "atomic-bottom-up"
  ));
  const [selection, setSelection] = useState<Selection>(null);
  const [preview, setPreview] = useState<{ nodeId: string; bounds: Bounds } | null>(null);
  const [detailLayouts, setDetailLayouts] = useState<DetailLayoutMap>({});
  const [detailPreview, setDetailPreview] = useState<DetailPreview | null>(null);
  const [detailSelection, setDetailSelection] = useState<DetailSelection | null>(() => initialNestedSelection
    ? { rootId: initialNestedSelection[0], levelPath: [], childId: initialNestedSelection[1].childId }
    : null);
  const [detailExpansions, setDetailExpansions] = useState<DetailExpansionMap>(() => initialExpansionRef.current);
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(() => new Set(initialExpandedRef.current));
  const [edgeMode, setEdgeMode] = useState(false);
  const [edgeSource, setEdgeSource] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const gestureRef = useRef<Gesture | null>(null);
  const pendingFocusNodeRef = useRef<string | null>(null);
  const sequence = useRef(1);

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
  const detailTrees = useMemo<Record<string, InlineDetailLevel>>(() => Object.fromEntries(
    displayScene.nodes.flatMap((node) => (
      node.detail_expanded && node.detail_kind
        ? [[node.scene_node_id, buildInlineDetailLayout(
          node.detail_kind,
          node.bounds,
          detailExpansions[node.scene_node_id],
          effectiveDetailLayouts,
          node.scene_node_id,
          [],
          hierarchyRoutingMode,
        )]]
        : []
    )),
  ), [detailExpansions, displayScene, effectiveDetailLayouts, hierarchyRoutingMode]);
  const atomicProjections = useMemo(() => hierarchyRoutingMode === "atomic-bottom-up"
    ? Object.fromEntries(Object.entries(detailTrees).map(([nodeId, tree]) => [
      nodeId,
      buildAtomicHierarchyProjection(tree),
    ]))
    : {}, [detailTrees, hierarchyRoutingMode]);
  const boundaryPorts = useMemo(() => hierarchyRoutingMode === "atomic-bottom-up"
    ? projectedSceneBoundaryPorts(atomicProjections)
    : undefined, [atomicProjections, hierarchyRoutingMode]);
  const hiddenExitBridgeIds = useMemo(() => {
    if (hierarchyRoutingMode !== "atomic-bottom-up") return new Set<string>();
    const outgoingNodeIds = new Set(displayScene.edges.map((edge) => edge.source_scene_node_id));
    return new Set(Object.entries(atomicProjections).flatMap(([nodeId, projection]) => [
      ...projectedNestedExitBridgeIds(projection),
      ...(outgoingNodeIds.has(nodeId) ? projectedAtomicExit(projection)?.bridgeEdgeIds ?? [] : []),
    ]));
  }, [atomicProjections, displayScene.edges, hierarchyRoutingMode]);
  const routed = useMemo(
    () => routeScene(displayScene, options.routeStyle, boundaryPorts),
    [boundaryPorts, displayScene, options.routeStyle],
  );
  const metrics = useMemo(() => measureScene(displayScene, routed), [displayScene, routed]);
  const canvasWidthPercent = Math.max(100, displayScene.paper_width / editor.scene.paper_width * 100);
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
    viewport.scrollLeft += nodeBounds.left - viewportBounds.left - (viewportBounds.width - nodeBounds.width) / 2;
  }, [displayScene]);

  function patch(next: LabPatch) {
    dispatch({ type: "patch", patch: next });
  }

  function loadScene(scene: LabScene) {
    dispatch({ type: "load", scene });
    setSelection(null);
    setPreview(null);
    setDetailLayouts({});
    setDetailPreview(null);
    setDetailSelection(null);
    setDetailExpansions({});
    setExpandedNodeIds(new Set());
    if (viewportRef.current) viewportRef.current.scrollLeft = 0;
    setEdgeMode(false);
    setEdgeSource(null);
  }

  function beginNode(event: React.PointerEvent<SVGGElement>, node: LabNode) {
    event.stopPropagation();
    setDetailSelection(null);
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
    if (expandedNodeIds.size) return;
    const svg = svgRef.current;
    if (!svg) return;
    svg.setPointerCapture(event.pointerId);
    gestureRef.current = {
      pointerId: event.pointerId,
      nodeId: node.scene_node_id,
      kind: "move",
      start: svgPoint(event as unknown as React.PointerEvent<SVGSVGElement>, svg),
      initial: { ...node.bounds },
    };
  }

  function beginDetailNode(
    event: React.PointerEvent<SVGGElement>,
    root: LabNode,
    levelPath: string[],
    level: InlineDetailLevel,
    child: DetailNode,
  ) {
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
      parentBounds: level.bounds,
    };
  }

  function beginResize(event: React.PointerEvent<SVGRectElement>, node: LabNode) {
    event.stopPropagation();
    if (expandedNodeIds.size) return;
    const svg = svgRef.current;
    if (!svg) return;
    svg.setPointerCapture(event.pointerId);
    gestureRef.current = {
      pointerId: event.pointerId,
      nodeId: node.scene_node_id,
      kind: "resize",
      start: svgPoint(event as unknown as React.PointerEvent<SVGSVGElement>, svg),
      initial: { ...node.bounds },
    };
  }

  function movePointer(event: React.PointerEvent<SVGSVGElement>) {
    const gesture = gestureRef.current;
    if (!gesture || gesture.pointerId !== event.pointerId) return;
    if (gesture.kind === "detail-move") {
      const point = svgPoint(event, event.currentTarget);
      const offset = clampDetailOffset(gesture.parentBounds, gesture.childBounds, {
        x: gesture.initialOffset.x + point.x - gesture.start.x,
        y: gesture.initialOffset.y + point.y - gesture.start.y,
      });
      setDetailPreview({ rootId: gesture.rootId, levelPath: gesture.levelPath, childId: gesture.childId, offset });
      return;
    }
    setPreview({
      nodeId: gesture.nodeId,
      bounds: nextGestureBounds(gesture, svgPoint(event, event.currentTarget), editor.scene),
    });
  }

  function finishPointer(event: React.PointerEvent<SVGSVGElement>) {
    const gesture = gestureRef.current;
    if (!gesture || gesture.pointerId !== event.pointerId) return;
    if (gesture.kind === "detail-move") {
      const point = svgPoint(event, event.currentTarget);
      const offset = clampDetailOffset(gesture.parentBounds, gesture.childBounds, {
        x: gesture.initialOffset.x + point.x - gesture.start.x,
        y: gesture.initialOffset.y + point.y - gesture.start.y,
      });
      gestureRef.current = null;
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
    setPreview(null);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    patch({ operation: "update-node", nodeId: gesture.nodeId, changes: { bounds } });
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
    setExpandedNodeIds((current) => {
      const next = new Set(current);
      if (next.has(nodeId)) next.delete(nodeId);
      else {
        next.add(nodeId);
        pendingFocusNodeRef.current = nodeId;
      }
      return next;
    });
    setSelection({ kind: "node", id: nodeId });
    setPreview(null);
  }

  function toggleNestedDetail(root: LabNode, levelPath: string[], child: DetailNode) {
    if (!child.nestedKind) return;
    setSelection(null);
    setDetailSelection({ rootId: root.scene_node_id, levelPath, childId: child.id });
    setDetailExpansions((current) => {
      function toggleAtPath(branch: DetailExpansionBranch | undefined, path: readonly string[]): DetailExpansionBranch | undefined {
        if (!path.length) return branch?.childId === child.id ? undefined : { childId: child.id };
        if (!branch || branch.childId !== path[0]) return branch;
        const nested = toggleAtPath(branch.child, path.slice(1));
        return nested ? { ...branch, child: nested } : { childId: branch.childId };
      }
      const nextBranch = toggleAtPath(current[root.scene_node_id], levelPath);
      if (!nextBranch) {
        const next = { ...current };
        delete next[root.scene_node_id];
        return next;
      }
      return { ...current, [root.scene_node_id]: nextBranch };
    });
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
    const offset = clampDetailOffset(selectedDetail.level.bounds, baseChild, nextOffset);
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
    const scenario = SCENARIOS.find((item) => item.scene_id === editor.scene.scene_id) ?? SCENARIOS[0];
    loadScene(scenario);
  }

  function exportCurrent() {
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
    const url = URL.createObjectURL(new Blob([payload], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${editor.scene.scene_id}-${options.routeStyle}-${options.nodeStyle}-${options.labelStyle}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function updateNode(changes: Partial<Omit<LabNode, "scene_node_id">>) {
    if (!selectedNode) return;
    patch({ operation: "update-node", nodeId: selectedNode.scene_node_id, changes });
  }

  function updateEdge(changes: Partial<Omit<LabEdge, "scene_edge_id">>) {
    if (!selectedEdge) return;
    patch({ operation: "update-edge", edgeId: selectedEdge.scene_edge_id, changes });
  }

  return <div className="scene-lab">
    <header className="lab-topbar">
      <div className="lab-product"><Waypoints size={17} /><strong>ArchCanvas</strong><span>Scene Lab</span></div>
      <div className="toolbar-group" aria-label="编辑操作">
        <button className="tool-button" onClick={addNode}><Plus size={15} />节点</button>
        <button
          className={`tool-button ${edgeMode ? "active" : ""}`}
          aria-pressed={edgeMode}
          onClick={() => { setEdgeMode((value) => !value); setEdgeSource(null); }}
        ><ArrowRightLeft size={15} />连线</button>
        <button className="icon-button" title="删除所选" disabled={!selection} onClick={removeSelection}><Trash2 size={15} /></button>
      </div>
      <div className="toolbar-group" aria-label="历史操作">
        <button className="icon-button" title="撤销" disabled={!editor.past.length} onClick={() => dispatch({ type: "undo" })}><Undo2 size={15} /></button>
        <button className="icon-button" title="重做" disabled={!editor.future.length} onClick={() => dispatch({ type: "redo" })}><Redo2 size={15} /></button>
        <button className="icon-button" title="重置当前案例" onClick={resetScene}><RotateCcw size={15} /></button>
      </div>
      <div className="toolbar-spacer" />
      {edgeMode && <span className="edge-mode-status">{edgeSource ? "选择终点" : "选择起点"}</span>}
      <a className="tool-button" href="./cases/index.html" target="_blank" rel="noreferrer"><GalleryVerticalEnd size={15} />案例矩阵</a>
      <button className="tool-button" onClick={exportCurrent}><Download size={15} />导出方案</button>
    </header>

    <main className="lab-workspace">
      <aside className="case-panel">
        <div className="panel-heading"><GalleryVerticalEnd size={15} /><strong>压力场景</strong><span>{SCENARIOS.length}</span></div>
        <div className="case-list">
          {SCENARIOS.map((scenario) => <button
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
          <div className="scene-caption"><strong>{editor.scene.title}</strong><span>{editor.scene.description}</span></div>
        </div>
        <div ref={viewportRef} className="canvas-viewport">
          <svg
            ref={svgRef}
            className={`lab-canvas ${edgeMode ? "edge-mode" : ""}`}
            style={{ width: `${canvasWidthPercent}%`, aspectRatio: `${displayScene.paper_width} / ${displayScene.paper_height}` }}
            viewBox={`0 0 ${displayScene.paper_width} ${displayScene.paper_height}`}
            role="application"
            aria-label={`${displayScene.title} 架构图编辑画布`}
            onPointerDown={(event) => {
              if (event.target !== event.currentTarget) return;
              setSelection(null);
              setDetailSelection(null);
            }}
            onPointerMove={movePointer}
            onPointerUp={finishPointer}
            onPointerCancel={finishPointer}
          >
            <MarkerDefinitions />
            <rect className="canvas-paper" x={12} y={12} width={displayScene.paper_width - 24} height={displayScene.paper_height - 24} />
            {routed.filter((route) => !route.foreground).map((route) => <EdgeGraphic
              key={route.edge.scene_edge_id}
              route={route}
              labelStyle={options.labelStyle}
              selected={selection?.kind === "edge" && selection.id === route.edge.scene_edge_id}
              onSelect={(edge) => setSelection({ kind: "edge", id: edge.scene_edge_id })}
            />)}
            {displayScene.nodes.map((node) => <NodeGraphic
              key={node.scene_node_id}
              node={node}
              visualStyle={options.nodeStyle}
              selected={selection?.kind === "node" && selection.id === node.scene_node_id}
              connecting={edgeSource === node.scene_node_id}
              onPointerDown={beginNode}
              onResizePointerDown={beginResize}
              onToggleDetail={toggleNodeDetail}
              detailTree={detailTrees[node.scene_node_id]}
              detailSelection={detailSelection?.rootId === node.scene_node_id ? detailSelection : undefined}
              onDetailPointerDown={beginDetailNode}
              onToggleNestedDetail={toggleNestedDetail}
              resizeEnabled={!expandedNodeIds.size}
              hiddenFlowIds={hiddenExitBridgeIds}
            />)}
            {routed.filter((route) => route.foreground).map((route) => <EdgeGraphic
              key={route.edge.scene_edge_id}
              route={route}
              labelStyle={options.labelStyle}
              selected={selection?.kind === "edge" && selection.id === route.edge.scene_edge_id}
              onSelect={(edge) => setSelection({ kind: "edge", id: edge.scene_edge_id })}
            />)}
          </svg>
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
          ><Maximize2 size={14} />{expansionAtLevel(
              detailExpansions[selectedDetail.root.scene_node_id],
              detailSelection?.levelPath ?? [],
            )?.childId === selectedDetail.child.id ? "收起当前层" : "展开下一层"}</button>}
          <button className="tool-button inspector-action" onClick={resetSelectedDetailOffset}><RotateCcw size={14} />复位子模块位置</button>
        </div> : selectedNode ? <div className="inspector-form">
          <div className="selection-title"><span>节点</span><strong>{selectedNode.label}</strong></div>
          <label>名称<input value={selectedNode.label} onChange={(event) => updateNode({ label: event.target.value })} /></label>
          <label>副标题<input value={selectedNode.secondary_label} onChange={(event) => updateNode({ secondary_label: event.target.value })} /></label>
          <label>形状<select value={selectedNode.shape} onChange={(event) => updateNode({ shape: event.target.value as NodeShape })}>
            {NODE_SHAPES.map((shape) => <option key={shape} value={shape}>{NODE_SHAPE_NAMES[shape]}</option>)}
          </select></label>
          <div className="field-grid">
            <label>宽度<input type="number" min={72} max={320} value={Math.round(selectedNode.bounds.width)} onChange={(event) => updateNode({ bounds: clampBounds({ ...selectedNode.bounds, width: Number(event.target.value) }, editor.scene) })} /></label>
            <label>高度<input type="number" min={42} max={180} value={Math.round(selectedNode.bounds.height)} onChange={(event) => updateNode({ bounds: clampBounds({ ...selectedNode.bounds, height: Number(event.target.value) }, editor.scene) })} /></label>
            <label>X<input type="number" value={Math.round(selectedNode.bounds.x)} onChange={(event) => updateNode({ bounds: clampBounds({ ...selectedNode.bounds, x: Number(event.target.value) }, editor.scene) })} /></label>
            <label>Y<input type="number" value={Math.round(selectedNode.bounds.y)} onChange={(event) => updateNode({ bounds: clampBounds({ ...selectedNode.bounds, y: Number(event.target.value) }, editor.scene) })} /></label>
          </div>
          <button className="danger-button" onClick={removeSelection}><Trash2 size={14} />删除节点及关联连线</button>
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
          <button className="danger-button" onClick={removeSelection}><Trash2 size={14} />删除连线</button>
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
