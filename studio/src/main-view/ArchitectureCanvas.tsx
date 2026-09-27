import {
  AlignHorizontalSpaceBetween,
  AlignStartHorizontal,
  AlignStartVertical,
  AlignVerticalSpaceBetween,
  ChevronDown,
  ChevronRight,
  Focus,
  Maximize2,
  Minus,
  Plus,
  Route,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { buildKernelRenderScene } from "../visual-kernel/layout";
import { renderKernelSceneSvg, type KernelExportArtifact } from "../visual-kernel/export";
import type {
  EdgeLabelStyle,
  KernelNode,
  NodeVisualStyle,
  RenderDetailPrimitive,
  RenderNode,
  RenderTemplateDetail,
  RouteStyle,
} from "../visual-kernel/types";
import { NODE_TOKENS, RELATION_TOKENS } from "../visual-kernel/visual-language";
import { adaptFormalState, type FormalStudioState } from "./formal-state-adapter";
import { normalizedSelectionBox, selectionIntersectsBounds } from "./interaction";
import "./main-view.css";

interface ArchitectureCanvasProps {
  state: FormalStudioState;
  selectedCanonicalIds: string[];
  selectedCanonicalEdgeIds?: string[];
  onSelectNode: (node: KernelNode | null, additive?: boolean) => void;
  onSelectCanonicalIds?: (canonicalIds: string[], options?: { additive?: boolean }) => void;
  onSelectEdge?: (canonicalEdgeIds: string[], additive?: boolean) => void;
  onToggleModule?: (hierarchyNodeId: string, expanded: boolean) => void;
  onCommitVisualBatch?: (
    description: string,
    patches: Array<{ operation: string; targetId?: string; value: Record<string, unknown> }>,
  ) => void;
  onExportArtifactChange?: (artifact: KernelExportArtifact) => void;
  tx: (english: string, chinese: string) => string;
}

type ViewBox = [number, number, number, number];

type GestureSession = {
  kind: "pan" | "box" | "node" | "resize" | "detail";
  pointerId: number;
  clientX: number;
  clientY: number;
  viewBox: ViewBox;
  viewportWidth: number;
  viewportHeight: number;
  moved: boolean;
  nodeId?: string;
  detailPrimitiveId?: string;
  initialPoint?: { x: number; y: number };
  initialSize?: { width: number; height: number };
  nodeMoves?: Record<string, { x: number; y: number }>;
  detailMoveIds?: string[];
  previewPoints?: Record<string, { x: number; y: number }>;
  previewSize?: { width: number; height: number };
  selectNodeOnFinish?: RenderNode;
  selectCanonicalOnFinish?: string[];
  selectionAdditive?: boolean;
  boxStart?: { x: number; y: number };
  additive?: boolean;
};

function readableViewBox(scene: { width: number; height: number }): ViewBox {
  return [0, 0, Math.min(scene.width, 1400), scene.height];
}

function restoredViewBox(
  scene: { width: number; height: number },
  camera?: { x: number; y: number; zoom: number; width?: number; height?: number },
): ViewBox {
  if (!camera) return readableViewBox(scene);
  const width = camera.width ?? Math.min(scene.width, 1400) / camera.zoom;
  const height = camera.height ?? scene.height / camera.zoom;
  return [camera.x, camera.y, width, height];
}

function detailPrimitiveBounds(primitive: Exclude<RenderDetailPrimitive, { kind: "flow" | "text" }>) {
  return primitive.kind === "operator"
    ? { x: primitive.cx - primitive.radius, y: primitive.cy - primitive.radius, width: primitive.radius * 2, height: primitive.radius * 2 }
    : { x: primitive.x, y: primitive.y, width: primitive.width, height: primitive.height };
}

function OperatorSymbol({ node }: { node: RenderNode }) {
  const symbol = node.shape === "concat" ? "||" : node.shape === "multiply" ? "x" : "+";
  return <text className="kernel-node-symbol" textAnchor="middle" x={node.bounds.x + node.bounds.width / 2} y={node.bounds.y + 39}>{symbol}</text>;
}

function MatrixGlyph({ node }: { node: RenderNode }) {
  const x = node.bounds.x + 14;
  const y = node.bounds.y + 22;
  return <g className="kernel-node-glyph matrix-glyph">
    <path d={`M${x + 6} ${y - 6}h48l7 7v39l-7-7h-48z`} />
    <rect x={x} y={y} width={54} height={42} rx={2} />
    {[1, 2, 3].map((column) => <line key={`c-${column}`} x1={x + column * 13.5} y1={y} x2={x + column * 13.5} y2={y + 42} />)}
    {[1, 2].map((row) => <line key={`r-${row}`} x1={x} y1={y + row * 14} x2={x + 54} y2={y + row * 14} />)}
  </g>;
}

function OperationGlyph({ node }: { node: RenderNode }) {
  const x = node.bounds.x + 14;
  const y = node.bounds.y + 24;
  return <g className="kernel-node-glyph operation-glyph">
    <rect x={x} y={y} width={17} height={6} rx={1.5} />
    <rect x={x} y={y + 12} width={22} height={6} rx={1.5} />
    <rect x={x} y={y + 24} width={27} height={6} rx={1.5} />
  </g>;
}

function ConvolutionGlyph({ node }: { node: RenderNode }) {
  const x = node.bounds.x + 14;
  const y = node.bounds.y + 23;
  return <g className="kernel-node-glyph convolution-glyph">
    {[8, 4, 0].map((offset) => <rect key={offset} x={x + offset} y={y - offset} width={45} height={42} rx={2} />)}
    {[1, 2].map((column) => <line key={`c-${column}`} x1={x + 8 + column * 15} y1={y - 8} x2={x + 8 + column * 15} y2={y + 34} />)}
    {[1, 2].map((row) => <line key={`r-${row}`} x1={x + 8} y1={y - 8 + row * 14} x2={x + 53} y2={y - 8 + row * 14} />)}
  </g>;
}

function AttentionGlyph({ node }: { node: RenderNode }) {
  const x = node.bounds.x + 14;
  const y = node.bounds.y + 20;
  return <g className="kernel-node-glyph attention-glyph">
    {["Q", "K", "V"].map((value, index) => <g key={value}>
      <rect x={x} y={y + index * 15} width={18} height={12} rx={2} />
      <text className="kernel-node-glyph-text" x={x + 9} y={y + index * 15 + 9}>{value}</text>
      <line x1={x + 19} y1={y + index * 15 + 6} x2={x + 47} y2={y + 22} />
    </g>)}
    <circle cx={x + 51} cy={y + 22} r={5} />
  </g>;
}

function NormalizationGlyph({ node }: { node: RenderNode }) {
  const x = node.bounds.x + 14;
  const y = node.bounds.y + 24;
  return <g className="kernel-node-glyph normalization-glyph">
    <rect x={x} y={y} width={54} height={38} rx={19} />
    {[20, 27, 34].map((offset) => <line key={offset} x1={x + offset} y1={y + 8} x2={x + offset} y2={y + 30} />)}
    <text className="kernel-node-glyph-text" x={x + 27} y={y + 22}>mu s</text>
  </g>;
}

function ContainerGlyph({ node }: { node: RenderNode }) {
  const x = node.bounds.x + 14;
  const y = node.bounds.y + 20;
  return <g className="kernel-node-glyph container-glyph">
    <rect x={x} y={y} width={48} height={48} rx={3} />
    <rect x={x + 7} y={y + 9} width={13} height={12} rx={2} />
    <rect x={x + 28} y={y + 9} width={13} height={12} rx={2} />
    <rect x={x + 17} y={y + 29} width={14} height={11} rx={2} />
    <path d={`M${x + 20} ${y + 15}h8M${x + 34} ${y + 21}v8M${x + 17} ${y + 34}h-5v-13`} />
  </g>;
}

function NodeShape({ node, selected }: { node: RenderNode; selected: boolean }) {
  const { x, y, width, height } = node.bounds;
  const token = NODE_TOKENS[node.shape];
  const common = { fill: token.fill, stroke: token.stroke, className: selected ? "kernel-node-body selected" : "kernel-node-body" };
  if (node.shape === "condition") {
    const inset = Math.min(24, width * 0.15);
    return <polygon {...common} points={`${x + inset},${y} ${x + width - inset},${y} ${x + width},${y + height / 2} ${x + width - inset},${y + height} ${x + inset},${y + height} ${x},${y + height / 2}`} />;
  }
  if (node.shape === "merge") {
    const cx = x + width / 2;
    const cy = y + 31;
    return <polygon {...common} points={`${cx},${cy - 24} ${cx + 24},${cy} ${cx},${cy + 24} ${cx - 24},${cy}`} />;
  }
  if (["add", "multiply", "concat"].includes(node.shape)) return <circle {...common} cx={x + width / 2} cy={y + 31} r={24} />;
  return <rect {...common} x={x} y={y} width={width} height={height} rx={node.shape === "io" ? Math.min(28, height / 2) : node.shape === "normalization" ? 14 : node.shape === "container" ? 6 : 5} />;
}

function ExpandedModule({ node, selected, onSelect, onToggle, onPointerDown, tx }: {
  node: RenderNode;
  selected: boolean;
  onSelect: (node: RenderNode, additive?: boolean) => void;
  onToggle: (node: RenderNode) => void;
  onPointerDown?: (event: React.PointerEvent<SVGGElement>, node: RenderNode) => void;
  tx: ArchitectureCanvasProps["tx"];
}) {
  return <g className={`kernel-expanded-module${selected ? " selected" : ""}`} data-kernel-node-id={node.nodeId} data-hierarchy-node-id={node.hierarchyNodeId} role="button" tabIndex={0} aria-label={`${node.label}, ${node.containedCanonicalNodeIds.length} canonical`} onPointerDown={(event) => onPointerDown?.(event, node)} onClick={(event) => { event.stopPropagation(); if (event.detail === 0) onSelect(node, event.shiftKey); }} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onSelect(node, event.shiftKey); }}>
    <rect className="kernel-expanded-surface" x={node.bounds.x} y={node.bounds.y} width={node.bounds.width} height={node.bounds.height} rx={6} />
    <path className="kernel-expanded-header" d={`M${node.bounds.x + 6} ${node.bounds.y}h${node.bounds.width - 12}a6 6 0 0 1 6 6v44h-${node.bounds.width}v-44a6 6 0 0 1 6-6z`} />
    <line className="kernel-expanded-divider" x1={node.bounds.x} y1={node.bounds.y + 50} x2={node.bounds.x + node.bounds.width} y2={node.bounds.y + 50} />
    <text className="kernel-expanded-title" x={node.bounds.x + 16} y={node.bounds.y + 22}>{node.label}</text>
    <text className="kernel-expanded-subtitle" x={node.bounds.x + 16} y={node.bounds.y + 39}>{node.childNodeIds.length} {tx("visible modules", "个可见子模块")} · {node.containedCanonicalNodeIds.length} canonical</text>
    {node.parentNodeId && <g className="kernel-module-toggle" role="button" tabIndex={0} aria-label={`${tx("Collapse", "收起")} ${node.label}`} transform={`translate(${node.bounds.x + node.bounds.width - 33} ${node.bounds.y + 13})`} onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); onToggle(node); }} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onToggle(node); }}>
      <rect width={20} height={20} rx={3} /><ChevronDown x={3} y={3} size={14} />
    </g>}
  </g>;
}

function StandardNode({ node, selected, nodeStyle, incoming, outgoing, onSelect, onToggle, onPointerDown, tx }: {
  node: RenderNode;
  selected: boolean;
  nodeStyle: NodeVisualStyle;
  incoming: number;
  outgoing: number;
  onSelect: (node: RenderNode, additive?: boolean) => void;
  onToggle: (node: RenderNode) => void;
  onPointerDown?: (event: React.PointerEvent<SVGGElement>, node: RenderNode) => void;
  tx: ArchitectureCanvasProps["tx"];
}) {
  const symbolNode = ["add", "multiply", "concat"].includes(node.shape);
  const hasSideGlyph = ["tensor", "container", "operation", "convolution", "attention", "normalization"].includes(node.shape);
  const textX = hasSideGlyph ? node.bounds.x + node.bounds.width * 0.69 : node.bounds.x + node.bounds.width / 2;
  return <g className={`kernel-node shape-${node.shape} role-${node.renderRole}${selected ? " selected" : ""}`} data-kernel-node-id={node.nodeId} data-hierarchy-node-id={node.hierarchyNodeId} data-canonical-node-ids={node.canonicalNodeIds.join(" ")} role="button" tabIndex={0} aria-label={`${node.label}, ${node.secondaryLabel ?? node.semanticKind}`} onPointerDown={(event) => onPointerDown?.(event, node)} onClick={(event) => { event.stopPropagation(); if (event.detail === 0) onSelect(node, event.shiftKey); }} onDoubleClick={(event) => { if (node.renderRole === "collapsed-module") { event.stopPropagation(); onToggle(node); } }} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onSelect(node, event.shiftKey); }}>
    <NodeShape node={node} selected={selected} />
    {node.shape === "tensor" && <MatrixGlyph node={node} />}
    {node.shape === "container" && <ContainerGlyph node={node} />}
    {node.shape === "operation" && <OperationGlyph node={node} />}
    {node.shape === "convolution" && <ConvolutionGlyph node={node} />}
    {node.shape === "attention" && <AttentionGlyph node={node} />}
    {node.shape === "normalization" && <NormalizationGlyph node={node} />}
    {symbolNode && <OperatorSymbol node={node} />}
    <text className={`kernel-node-title${symbolNode ? " symbol-label" : ""}`} textAnchor="middle" x={symbolNode ? node.bounds.x + node.bounds.width / 2 : textX} y={symbolNode ? node.bounds.y + 72 : node.bounds.y + node.bounds.height / 2 - (node.secondaryLabel ? 6 : 0)}>{node.label}</text>
    {!symbolNode && node.secondaryLabel && <text className="kernel-node-secondary" textAnchor="middle" x={textX} y={node.bounds.y + node.bounds.height / 2 + 14}>{node.secondaryLabel}</text>}
    {nodeStyle === "technical" && <text className="kernel-node-ports" textAnchor="middle" x={textX} y={node.bounds.y + node.bounds.height - 9}>{incoming} in · {outgoing} out</text>}
    {node.renderRole === "collapsed-module" && <g className="kernel-module-toggle collapsed" role="button" tabIndex={0} aria-label={`${tx("Expand", "展开")} ${node.label}`} transform={`translate(${node.bounds.x + node.bounds.width - 29} ${node.bounds.y + 9})`} onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); onToggle(node); }} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onToggle(node); }}>
      <rect width={20} height={20} rx={3} /><ChevronRight x={3} y={3} size={14} />
    </g>}
  </g>;
}

function detailTitle(detail: RenderTemplateDetail, primitive: RenderDetailPrimitive): string {
  const canonical = primitive.canonicalIds.length > 0 ? primitive.canonicalIds.join(", ") : "visual-only";
  const evidence = detail.evidenceIds.length > 0 ? detail.evidenceIds.join(", ") : "none";
  return `Slot: ${primitive.slotId}\nCanonical: ${canonical}\nEvidence: ${evidence}`;
}

function DetailFlow({ detail, primitive }: { detail: RenderTemplateDetail; primitive: Extract<RenderDetailPrimitive, { kind: "flow" }> }) {
  const points = primitive.points.map((point) => `${point.x},${point.y}`).join(" ");
  return <polyline
    className={`kernel-detail-flow tone-${primitive.tone}`}
    data-detail-slot-id={primitive.slotId}
    points={points}
    markerEnd={primitive.marker ? "url(#kernel-detail-arrow)" : undefined}
  ><title>{detailTitle(detail, primitive)}</title></polyline>;
}

function DetailPrimitive({ detail, primitive, selected, onSelect, onPointerDown }: {
  detail: RenderTemplateDetail;
  primitive: Exclude<RenderDetailPrimitive, { kind: "flow" }>;
  selected: boolean;
  onSelect?: (canonicalIds: string[], options?: { additive?: boolean }) => void;
  onPointerDown?: (event: React.PointerEvent<SVGGElement>, primitive: Exclude<RenderDetailPrimitive, { kind: "flow" | "text" }>) => void;
}) {
  const title = <title>{detailTitle(detail, primitive)}</title>;
  let graphic: React.ReactNode;
  if (primitive.kind === "box") {
    const isFrame = primitive.slotId.startsWith("frame:");
    graphic = <g className={`kernel-detail-box tone-${primitive.tone}${isFrame ? " kernel-detail-frame" : ""}`} data-detail-slot-id={primitive.slotId}>
      {title}
      <rect x={primitive.x} y={primitive.y} width={primitive.width} height={primitive.height} rx={isFrame ? 5 : 3} />
      {primitive.label && <text className="kernel-detail-label" textAnchor="middle" x={primitive.x + primitive.width / 2} y={primitive.y + primitive.height / 2 + (primitive.note ? -3 : 4)}>{primitive.label}</text>}
      {primitive.note && <text className="kernel-detail-note" textAnchor="middle" x={primitive.x + primitive.width / 2} y={primitive.y + primitive.height / 2 + 12}>{primitive.note}</text>}
    </g>;
  } else if (primitive.kind === "matrix") {
    const columnWidth = primitive.width / primitive.columns;
    const rowHeight = primitive.height / primitive.rows;
    graphic = <g className={`kernel-detail-matrix tone-${primitive.tone}`} data-detail-slot-id={primitive.slotId}>
      {title}
      {primitive.depth > 0 && <path className="kernel-detail-matrix-depth" d={`M${primitive.x + primitive.depth} ${primitive.y - primitive.depth}h${primitive.width}v${primitive.height}M${primitive.x + primitive.width} ${primitive.y}l${primitive.depth} -${primitive.depth}M${primitive.x + primitive.width} ${primitive.y + primitive.height}l${primitive.depth} -${primitive.depth}`} />}
      <rect x={primitive.x} y={primitive.y} width={primitive.width} height={primitive.height} rx={2} />
      {Array.from({ length: primitive.columns - 1 }, (_, index) => <line key={`c-${index}`} x1={primitive.x + columnWidth * (index + 1)} y1={primitive.y} x2={primitive.x + columnWidth * (index + 1)} y2={primitive.y + primitive.height} />)}
      {Array.from({ length: primitive.rows - 1 }, (_, index) => <line key={`r-${index}`} x1={primitive.x} y1={primitive.y + rowHeight * (index + 1)} x2={primitive.x + primitive.width} y2={primitive.y + rowHeight * (index + 1)} />)}
      <text textAnchor="middle" x={primitive.x + primitive.width / 2} y={primitive.y - 7}>{primitive.label}</text>
    </g>;
  } else if (primitive.kind === "operator") {
    graphic = <g className={`kernel-detail-operator tone-${primitive.tone}`} data-detail-slot-id={primitive.slotId}>
      {title}<circle cx={primitive.cx} cy={primitive.cy} r={primitive.radius} /><text textAnchor="middle" x={primitive.cx} y={primitive.cy + 4}>{primitive.label}</text>
    </g>;
  } else {
    graphic = <text className={`kernel-detail-text tone-${primitive.tone}${primitive.emphasis ? " emphasis" : ""}`} data-detail-slot-id={primitive.slotId} textAnchor="middle" x={primitive.x} y={primitive.y}>{title}{primitive.value}</text>;
  }
  if (primitive.canonicalIds.length === 0 || primitive.kind === "text") return graphic;
  const activate = (additive = false) => onSelect?.(primitive.canonicalIds, { additive });
  return <g
    className={`kernel-detail-interactive${selected ? " selected" : ""}`}
    data-detail-primitive-id={primitive.primitiveId}
    data-detail-canonical-ids={primitive.canonicalIds.join(" ")}
    role="button"
    tabIndex={0}
    aria-label={`${primitive.slotId}: ${primitive.canonicalIds.join(", ")}`}
    onPointerDown={(event) => onPointerDown?.(event, primitive)}
    onClick={(event) => { event.stopPropagation(); if (event.detail === 0) activate(event.shiftKey); }}
    onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); event.stopPropagation(); activate(event.shiftKey); } }}
  >{graphic}</g>;
}

export function ArchitectureCanvas({ state, selectedCanonicalIds, selectedCanonicalEdgeIds = [], onSelectNode, onSelectCanonicalIds, onSelectEdge, onToggleModule, onCommitVisualBatch, onExportArtifactChange, tx }: ArchitectureCanvasProps) {
  const serverExpansionKey = (state.view_state.module_expansion ?? []).join("|");
  const [expandedHierarchyIds, setExpandedHierarchyIds] = useState(() => new Set(state.view_state.module_expansion ?? []));
  useEffect(() => setExpandedHierarchyIds(new Set(state.view_state.module_expansion ?? [])), [serverExpansionKey]);
  const projectedState = useMemo(() => ({ ...state, view_state: { ...state.view_state, module_expansion: [...expandedHierarchyIds] } }), [state, expandedHierarchyIds]);
  const adapted = useMemo(() => adaptFormalState(projectedState), [projectedState]);
  const [routeStyle, setRouteStyle] = useState<RouteStyle>(adapted.visualState.routeStyle);
  const [nodeStyle, setNodeStyle] = useState<NodeVisualStyle>(adapted.visualState.nodeStyle);
  const [labelStyle, setLabelStyle] = useState<EdgeLabelStyle>(adapted.visualState.labelStyle);
  const [localNodePositions, setLocalNodePositions] = useState<Record<string, { x: number; y: number }>>({});
  const [localNodeSizes, setLocalNodeSizes] = useState<Record<string, { width: number; height: number }>>({});
  const [localDetailOffsets, setLocalDetailOffsets] = useState<Record<string, { x: number; y: number }>>({});
  const [activeRenderNodeId, setActiveRenderNodeId] = useState<string | null>(null);
  const visualState = useMemo(() => ({
    ...adapted.visualState,
    routeStyle,
    nodeStyle,
    labelStyle,
    nodePositions: { ...adapted.visualState.nodePositions, ...localNodePositions },
    nodeSizes: { ...adapted.visualState.nodeSizes, ...localNodeSizes },
    detailOffsets: { ...adapted.visualState.detailOffsets, ...localDetailOffsets },
  }), [adapted.visualState, labelStyle, localDetailOffsets, localNodePositions, localNodeSizes, nodeStyle, routeStyle]);
  const scene = useMemo(() => buildKernelRenderScene(adapted.document, visualState), [adapted.document, visualState]);
  const exportArtifact = useMemo(
    () => renderKernelSceneSvg(adapted.document, visualState, scene),
    [adapted.document, scene, visualState],
  );
  useEffect(() => onExportArtifactChange?.(exportArtifact), [exportArtifact, onExportArtifactChange]);
  const persistedCamera = state.view_state.cameras?.[scene.sceneId];
  const cameraKey = JSON.stringify(persistedCamera ?? null);
  const [viewBox, setViewBox] = useState<ViewBox>(() => restoredViewBox(scene, persistedCamera));
  const latestViewBox = useRef<ViewBox>(viewBox);
  const cameraTimer = useRef<number | null>(null);
  const gesture = useRef<GestureSession | null>(null);
  const suppressBackgroundClick = useRef(false);
  const [activeGesture, setActiveGesture] = useState<GestureSession["kind"] | null>(null);
  const [selectionBox, setSelectionBox] = useState<{ x: number; y: number; width: number; height: number } | null>(null);
  useEffect(() => {
    const restored = restoredViewBox(scene, persistedCamera);
    latestViewBox.current = restored;
    setViewBox(restored);
  }, [scene.sceneId, cameraKey]);
  useEffect(() => () => {
    if (cameraTimer.current !== null) window.clearTimeout(cameraTimer.current);
  }, []);
  const geometryKey = JSON.stringify([
    adapted.visualState.nodePositions,
    adapted.visualState.nodeSizes,
    adapted.visualState.detailOffsets,
  ]);
  useEffect(() => {
    setLocalNodePositions({});
    setLocalNodeSizes({});
    setLocalDetailOffsets({});
    setActiveRenderNodeId(null);
  }, [adapted.document.sourceDigest, geometryKey]);
  useEffect(() => setRouteStyle(adapted.visualState.routeStyle), [adapted.visualState.routeStyle]);
  useEffect(() => setNodeStyle(adapted.visualState.nodeStyle), [adapted.visualState.nodeStyle]);
  useEffect(() => setLabelStyle(adapted.visualState.labelStyle), [adapted.visualState.labelStyle]);

  const nodeByPort = useMemo(() => new Map(adapted.document.ports.map((port) => [port.portId, port.ownerNodeId])), [adapted.document.ports]);
  const nodeById = useMemo(() => new Map(scene.nodes.map((node) => [node.nodeId, node])), [scene.nodes]);
  const visibleRelations = useMemo(() => [...new Set(scene.edges.map((edge) => edge.relation))], [scene.edges]);
  const selected = new Set(selectedCanonicalIds);
  const selectedEdges = new Set(selectedCanonicalEdgeIds);
  const commitBatch = (
    description: string,
    patches: Array<{ operation: string; targetId?: string; value: Record<string, unknown> }>,
  ) => {
    if (patches.length > 0) onCommitVisualBatch?.(description, patches);
  };
  const scheduleCameraCommit = (next: ViewBox) => {
    if (!onCommitVisualBatch) return;
    if (cameraTimer.current !== null) window.clearTimeout(cameraTimer.current);
    cameraTimer.current = window.setTimeout(() => {
      cameraTimer.current = null;
      commitBatch(tx("Update canvas camera", "更新画布相机"), [{
        operation: "set-camera",
        value: {
          x: next[0], y: next[1], width: next[2], height: next[3],
          zoom: Math.max(0.0001, Math.min(scene.width / next[2], scene.height / next[3])),
        },
      }]);
    }, 180);
  };
  const updateViewBox = (next: ViewBox, persist = true) => {
    latestViewBox.current = next;
    setViewBox(next);
    if (persist) scheduleCameraCommit(next);
  };
  const zoom = (factor: number) => {
    const [x, y, width, height] = latestViewBox.current;
    const nextWidth = width * factor;
    const nextHeight = height * factor;
    updateViewBox([x + (width - nextWidth) / 2, y + (height - nextHeight) / 2, nextWidth, nextHeight]);
  };
  const toggleModule = (node: RenderNode) => {
    const nextExpanded = !node.expanded;
    setExpandedHierarchyIds((current) => {
      const next = new Set(current);
      if (nextExpanded) next.add(node.hierarchyNodeId); else next.delete(node.hierarchyNodeId);
      return next;
    });
    onToggleModule?.(node.hierarchyNodeId, nextExpanded);
    commitBatch(tx("Update module expansion", "更新模块展开状态"), [{
      operation: "set-detail-expansion",
      targetId: node.hierarchyNodeId,
      value: { enabled: nextExpanded },
    }]);
  };
  const expandedNodes = scene.nodes.filter((node) => node.renderRole === "expanded-module").sort((left, right) => left.depth - right.depth);
  const standardNodes = scene.nodes.filter((node) => node.renderRole !== "expanded-module");
  const selectedRenderNodes = activeRenderNodeId
    ? scene.nodes.filter((node) => node.nodeId === activeRenderNodeId)
    : scene.nodes.filter((node) => node.canonicalNodeIds.some((id) => selected.has(id)));
  const renderNodeSelected = (node: RenderNode) => node.nodeId === activeRenderNodeId
    || (!activeRenderNodeId && node.canonicalNodeIds.some((id) => selected.has(id)));
  const selectRenderNode = (node: RenderNode | null, additive = false) => {
    setActiveRenderNodeId(node?.nodeId ?? null);
    onSelectNode(node, additive);
  };
  const selectDetailCanonical: NonNullable<ArchitectureCanvasProps["onSelectCanonicalIds"]> = (canonicalIds, options) => {
    setActiveRenderNodeId(null);
    onSelectCanonicalIds?.(canonicalIds, options);
  };
  const arrangeSelection = (command: "align-left" | "align-top" | "distribute-horizontal" | "distribute-vertical") => {
    if (selectedRenderNodes.length < 2) return;
    const desired = new Map(selectedRenderNodes.map((node) => [node.nodeId, { x: node.bounds.x, y: node.bounds.y }]));
    if (command === "align-left") {
      const x = Math.min(...selectedRenderNodes.map((node) => node.bounds.x));
      selectedRenderNodes.forEach((node) => desired.set(node.nodeId, { x, y: node.bounds.y }));
    } else if (command === "align-top") {
      const y = Math.min(...selectedRenderNodes.map((node) => node.bounds.y));
      selectedRenderNodes.forEach((node) => desired.set(node.nodeId, { x: node.bounds.x, y }));
    } else {
      if (selectedRenderNodes.length < 3) return;
      const horizontal = command === "distribute-horizontal";
      const ordered = [...selectedRenderNodes].sort((left, right) => (
        horizontal
          ? left.bounds.x + left.bounds.width / 2 - right.bounds.x - right.bounds.width / 2
          : left.bounds.y + left.bounds.height / 2 - right.bounds.y - right.bounds.height / 2
      ));
      const first = ordered[0];
      const last = ordered[ordered.length - 1];
      const start = horizontal
        ? first.bounds.x + first.bounds.width / 2
        : first.bounds.y + first.bounds.height / 2;
      const end = horizontal
        ? last.bounds.x + last.bounds.width / 2
        : last.bounds.y + last.bounds.height / 2;
      const step = (end - start) / (ordered.length - 1);
      ordered.forEach((node, index) => desired.set(node.nodeId, horizontal
        ? { x: start + step * index - node.bounds.width / 2, y: node.bounds.y }
        : { x: node.bounds.x, y: start + step * index - node.bounds.height / 2 }));
    }
    const rootPositions: Record<string, { x: number; y: number }> = {};
    const detailOffsets: Record<string, { x: number; y: number }> = {};
    const patches = selectedRenderNodes.map((node) => {
      const target = desired.get(node.nodeId)!;
      if (node.parentNodeId) {
        const current = visualState.detailOffsets[node.nodeId] ?? { x: 0, y: 0 };
        const value = {
          x: current.x + target.x - node.bounds.x,
          y: current.y + target.y - node.bounds.y,
        };
        detailOffsets[node.nodeId] = value;
        return { operation: "set-detail-offset", targetId: node.nodeId, value };
      }
      rootPositions[node.nodeId] = target;
      return { operation: "set-position", targetId: node.nodeId, value: target };
    });
    setLocalNodePositions((current) => ({ ...current, ...rootPositions }));
    setLocalDetailOffsets((current) => ({ ...current, ...detailOffsets }));
    commitBatch(tx("Arrange selected nodes", "排列所选节点"), patches);
  };

  const beginGesture = (
    event: React.PointerEvent<SVGElement>,
    session: Omit<GestureSession, "pointerId" | "clientX" | "clientY" | "viewBox" | "viewportWidth" | "viewportHeight" | "moved">,
  ) => {
    if (event.button !== 0) return;
    const svg = event.currentTarget instanceof SVGSVGElement ? event.currentTarget : event.currentTarget.ownerSVGElement;
    if (!svg) return;
    event.stopPropagation();
    svg.setPointerCapture(event.pointerId);
    gesture.current = {
      ...session,
      pointerId: event.pointerId,
      clientX: event.clientX,
      clientY: event.clientY,
      viewBox,
      viewportWidth: svg.clientWidth,
      viewportHeight: svg.clientHeight,
      moved: false,
    };
    setActiveGesture(session.kind);
  };
  const beginNodeGesture = (event: React.PointerEvent<SVGGElement>, node: RenderNode) => {
    const wasSelected = renderNodeSelected(node);
    const initialPoint = node.parentNodeId
      ? visualState.detailOffsets[node.nodeId] ?? { x: 0, y: 0 }
      : { x: node.bounds.x, y: node.bounds.y };
    const movableSelection = wasSelected
      ? selectedRenderNodes.filter((item) => (
        node.parentNodeId
          ? item.parentNodeId === node.parentNodeId
          : !item.parentNodeId
      ))
      : [];
    const nodeMoves = movableSelection.length > 1
      ? Object.fromEntries(movableSelection.map((item) => [
        item.nodeId,
        item.parentNodeId
          ? visualState.detailOffsets[item.nodeId] ?? { x: 0, y: 0 }
          : { x: item.bounds.x, y: item.bounds.y },
      ]))
      : undefined;
    beginGesture(event, {
      kind: "node",
      nodeId: node.nodeId,
      initialPoint,
      nodeMoves,
      detailMoveIds: movableSelection.filter((item) => item.parentNodeId).map((item) => item.nodeId),
      selectNodeOnFinish: wasSelected ? undefined : node,
      selectionAdditive: event.shiftKey,
    });
  };
  const beginDetailGesture = (event: React.PointerEvent<SVGGElement>, primitive: Exclude<RenderDetailPrimitive, { kind: "flow" | "text" }>) => {
    const alreadySelected = primitive.canonicalIds.some((id) => selected.has(id));
    beginGesture(event, {
      kind: "detail",
      detailPrimitiveId: primitive.primitiveId,
      initialPoint: visualState.detailOffsets[primitive.primitiveId] ?? { x: 0, y: 0 },
      selectCanonicalOnFinish: alreadySelected ? undefined : primitive.canonicalIds,
      selectionAdditive: event.shiftKey,
    });
  };
  const beginResizeGesture = (event: React.PointerEvent<SVGRectElement>, node: RenderNode) => {
    beginGesture(event, { kind: "resize", nodeId: node.nodeId, initialSize: { width: node.bounds.width, height: node.bounds.height } });
  };
  const focusSelection = () => {
    const bounds = [
      ...selectedRenderNodes.map((node) => node.bounds),
      ...scene.details.flatMap((detail) => detail.primitives.filter((primitive): primitive is Exclude<RenderDetailPrimitive, { kind: "flow" | "text" }> => primitive.kind !== "flow" && primitive.kind !== "text" && primitive.canonicalIds.some((id) => selected.has(id))).map(detailPrimitiveBounds)),
    ];
    if (bounds.length === 0) return;
    const minX = Math.min(...bounds.map((item) => item.x));
    const minY = Math.min(...bounds.map((item) => item.y));
    const maxX = Math.max(...bounds.map((item) => item.x + item.width));
    const maxY = Math.max(...bounds.map((item) => item.y + item.height));
    const padding = 72;
    updateViewBox([minX - padding, minY - padding, Math.max(180, maxX - minX + padding * 2), Math.max(140, maxY - minY + padding * 2)]);
  };

  const finishGesture = (event: React.PointerEvent<SVGSVGElement>, cancelled = false) => {
    const session = gesture.current;
    if (!session || session.pointerId !== event.pointerId) return;
    if (!cancelled && session.kind === "box" && selectionBox) {
      const canonicalIds = new Set<string>();
      for (const node of scene.nodes) {
        const intersects = selectionIntersectsBounds(selectionBox, node.bounds);
        const containsExpanded = node.renderRole !== "expanded-module"
          || (selectionBox.x <= node.bounds.x
            && selectionBox.y <= node.bounds.y
            && selectionBox.x + selectionBox.width >= node.bounds.x + node.bounds.width
            && selectionBox.y + selectionBox.height >= node.bounds.y + node.bounds.height);
        if (!intersects || !containsExpanded) continue;
        const ids = node.canonicalNodeIds.length > 0 ? node.canonicalNodeIds : node.containedCanonicalNodeIds;
        ids.forEach((id) => canonicalIds.add(id));
      }
      for (const detail of scene.details) {
        for (const primitive of detail.primitives) {
          if (primitive.kind === "flow" || primitive.kind === "text" || primitive.canonicalIds.length === 0) continue;
          if (selectionIntersectsBounds(selectionBox, detailPrimitiveBounds(primitive))) {
            primitive.canonicalIds.forEach((id) => canonicalIds.add(id));
          }
        }
      }
      if (onSelectCanonicalIds) onSelectCanonicalIds([...canonicalIds], { additive: session.additive });
      else if (canonicalIds.size === 0 && !session.additive) onSelectNode(null);
      setActiveRenderNodeId(null);
    }
    if (cancelled) {
      setLocalNodePositions({});
      setLocalNodeSizes({});
      setLocalDetailOffsets({});
    } else if (session.moved && session.kind === "node" && session.nodeId) {
      const node = nodeById.get(session.nodeId);
      if (session.previewPoints && Object.keys(session.previewPoints).length > 0) {
        commitBatch(tx("Move selected nodes", "移动所选节点"), Object.entries(session.previewPoints).map(([targetId, point]) => ({
          operation: session.detailMoveIds?.includes(targetId) || (targetId === session.nodeId && node?.parentNodeId)
            ? "set-detail-offset"
            : "set-position",
          targetId,
          value: point,
        })));
      }
    } else if (session.moved && session.kind === "detail" && session.detailPrimitiveId && session.previewPoints?.[session.detailPrimitiveId]) {
      commitBatch(tx("Move detail element", "移动内部图例元素"), [{
        operation: "set-detail-offset",
        targetId: session.detailPrimitiveId,
        value: session.previewPoints[session.detailPrimitiveId],
      }]);
    } else if (session.moved && session.kind === "resize" && session.nodeId && session.previewSize) {
      commitBatch(tx("Resize visual node", "调整可视节点尺寸"), [{
        operation: "set-size",
        targetId: session.nodeId,
        value: session.previewSize,
      }]);
    } else if (session.moved && session.kind === "pan") {
      scheduleCameraCommit(latestViewBox.current);
    }
    suppressBackgroundClick.current = session.kind !== "pan" || session.moved;
    gesture.current = null;
    setActiveGesture(null);
    setSelectionBox(null);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (!cancelled && session.selectNodeOnFinish) {
      selectRenderNode(session.selectNodeOnFinish, session.selectionAdditive);
    } else if (!cancelled && session.selectCanonicalOnFinish) {
      selectDetailCanonical(session.selectCanonicalOnFinish, { additive: session.selectionAdditive });
    }
  };

  return <div className="kernel-main-view" data-kernel-scene-id={scene.sceneId} data-kernel-render-digest={exportArtifact.renderDigest}>
    <div className="kernel-control-strip">
      <label><Route size={13} /><span>{tx("Route", "路由")}</span><select value={routeStyle} onChange={(event) => { const value = event.target.value as RouteStyle; setRouteStyle(value); commitBatch(tx("Change route style", "更改路由样式"), [{ operation: "set-kernel-options", value: { route_style: value } }]); }}><option value="adaptive">Adaptive</option><option value="direct">Direct</option><option value="orthogonal">Orthogonal</option><option value="channel">Channel</option><option value="curve">Curve</option></select></label>
      <label><span>{tx("Nodes", "节点")}</span><select value={nodeStyle} onChange={(event) => { const value = event.target.value as NodeVisualStyle; setNodeStyle(value); commitBatch(tx("Change node style", "更改节点样式"), [{ operation: "set-kernel-options", value: { node_style: value } }]); }}><option value="semantic">Semantic</option><option value="technical">Technical</option><option value="compact">Compact</option></select></label>
      <label><span>{tx("Labels", "标签")}</span><select value={labelStyle} onChange={(event) => { const value = event.target.value as EdgeLabelStyle; setLabelStyle(value); commitBatch(tx("Change label style", "更改标签样式"), [{ operation: "set-kernel-options", value: { label_style: value } }]); }}><option value="plate">Plate</option><option value="plain">Plain</option><option value="endpoint">Endpoint</option></select></label>
      <button type="button" aria-label={tx("Align left", "左对齐")} title={tx("Align left", "左对齐")} disabled={selectedRenderNodes.length < 2} onClick={() => arrangeSelection("align-left")}><AlignStartVertical size={14} /></button>
      <button type="button" aria-label={tx("Align top", "顶对齐")} title={tx("Align top", "顶对齐")} disabled={selectedRenderNodes.length < 2} onClick={() => arrangeSelection("align-top")}><AlignStartHorizontal size={14} /></button>
      <button type="button" aria-label={tx("Distribute horizontally", "水平分布")} title={tx("Distribute horizontally", "水平分布")} disabled={selectedRenderNodes.length < 3} onClick={() => arrangeSelection("distribute-horizontal")}><AlignHorizontalSpaceBetween size={14} /></button>
      <button type="button" aria-label={tx("Distribute vertically", "垂直分布")} title={tx("Distribute vertically", "垂直分布")} disabled={selectedRenderNodes.length < 3} onClick={() => arrangeSelection("distribute-vertical")}><AlignVerticalSpaceBetween size={14} /></button>
      <button type="button" aria-label={tx("Zoom out", "缩小")} title={tx("Zoom out", "缩小")} onClick={() => zoom(1.18)}><Minus size={14} /></button>
      <button type="button" aria-label={tx("Zoom in", "放大")} title={tx("Zoom in", "放大")} onClick={() => zoom(0.84)}><Plus size={14} /></button>
      <button type="button" aria-label={tx("Fit scene", "适应画布")} title={tx("Fit scene", "适应画布")} onClick={() => updateViewBox([0, 0, scene.width, scene.height])}><Maximize2 size={14} /></button>
      <button type="button" aria-label={tx("Focus selection", "聚焦所选内容")} title={tx("Focus selection", "聚焦所选内容")} disabled={selectedRenderNodes.length === 0 && !scene.details.some((detail) => detail.primitives.some((primitive) => primitive.canonicalIds.some((id) => selected.has(id))))} onClick={focusSelection}><Focus size={14} /></button>
    </div>
    <svg
      className={`kernel-scene${activeGesture === "pan" ? " panning" : ""}${activeGesture === "box" ? " box-selecting" : ""}${activeGesture === "node" || activeGesture === "detail" ? " dragging" : ""}`}
      viewBox={viewBox.join(" ")}
      data-kernel-render-digest={exportArtifact.renderDigest}
      data-source-digest={scene.sourceDigest}
      role="img"
      aria-label={tx("Model architecture", "模型架构")}
      onClick={() => {
        if (suppressBackgroundClick.current) {
          suppressBackgroundClick.current = false;
          return;
        }
        selectRenderNode(null);
      }}
      onWheel={(event) => { event.preventDefault(); zoom(event.deltaY > 0 ? 1.08 : 0.92); }}
      onPointerDown={(event) => {
        if (!(event.target instanceof SVGSVGElement || (event.target as Element).classList.contains("kernel-paper") || (event.target as Element).classList.contains("kernel-grid"))) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        const boxStart = {
          x: viewBox[0] + (event.clientX - bounds.left) * viewBox[2] / Math.max(1, bounds.width),
          y: viewBox[1] + (event.clientY - bounds.top) * viewBox[3] / Math.max(1, bounds.height),
        };
        beginGesture(event, event.shiftKey
          ? { kind: "box", boxStart, additive: event.ctrlKey || event.metaKey }
          : { kind: "pan" });
        if (event.shiftKey) setSelectionBox({ ...boxStart, width: 0, height: 0 });
      }}
      onPointerMove={(event) => {
        const session = gesture.current;
        if (!session || session.pointerId !== event.pointerId) return;
        const clientDx = event.clientX - session.clientX;
        const clientDy = event.clientY - session.clientY;
        const dx = clientDx * session.viewBox[2] / Math.max(1, session.viewportWidth);
        const dy = clientDy * session.viewBox[3] / Math.max(1, session.viewportHeight);
        if (Math.hypot(clientDx, clientDy) > 2) session.moved = true;
        if (session.kind === "pan") {
          updateViewBox([session.viewBox[0] - dx, session.viewBox[1] - dy, session.viewBox[2], session.viewBox[3]], false);
        } else if (session.kind === "box" && session.boxStart) {
          setSelectionBox(normalizedSelectionBox(session.boxStart, { x: session.boxStart.x + dx, y: session.boxStart.y + dy }));
        } else if (session.kind === "node" && session.nodeId && session.initialPoint) {
          const node = nodeById.get(session.nodeId);
          const points = session.nodeMoves
            ? Object.fromEntries(Object.entries(session.nodeMoves).map(([nodeId, point]) => [nodeId, { x: point.x + dx, y: point.y + dy }]))
            : { [session.nodeId]: { x: session.initialPoint.x + dx, y: session.initialPoint.y + dy } };
          session.previewPoints = points;
          if (node?.parentNodeId) setLocalDetailOffsets((current) => ({ ...current, ...points }));
          else setLocalNodePositions((current) => ({ ...current, ...points }));
        } else if (session.kind === "detail" && session.detailPrimitiveId && session.initialPoint) {
          const point = { x: session.initialPoint.x + dx, y: session.initialPoint.y + dy };
          session.previewPoints = { [session.detailPrimitiveId]: point };
          setLocalDetailOffsets((current) => ({ ...current, [session.detailPrimitiveId!]: point }));
        } else if (session.kind === "resize" && session.nodeId && session.initialSize) {
          const size = {
            width: Math.max(82, session.initialSize.width + dx),
            height: Math.max(70, session.initialSize.height + dy),
          };
          session.previewSize = size;
          setLocalNodeSizes((current) => ({
            ...current,
            [session.nodeId!]: size,
          }));
        }
      }}
      onPointerUp={(event) => finishGesture(event)}
      onPointerCancel={(event) => finishGesture(event, true)}
    >
      <defs>
        <pattern id="kernel-grid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0L0 0 0 20" fill="none" /></pattern>
        <marker id="kernel-arrow" viewBox="0 0 10 10" refX="8.4" refY="5" markerWidth="5.8" markerHeight="5.8" orient="auto"><path d="M0 1 9 5 0 9Z" fill="context-stroke" /></marker>
        <marker id="kernel-detail-arrow" viewBox="0 0 10 10" refX="8.4" refY="5" markerWidth="4.8" markerHeight="4.8" orient="auto"><path d="M0 1 9 5 0 9Z" fill="context-stroke" /></marker>
      </defs>
      <rect className="kernel-paper" width={scene.width} height={scene.height} />
      <rect className="kernel-grid" x={12} y={12} width={Math.max(0, scene.width - 24)} height={Math.max(0, scene.height - 24)} fill="url(#kernel-grid)" />
      <g className="kernel-expanded-layer">{expandedNodes.map((node) => <ExpandedModule key={node.nodeId} node={node} selected={renderNodeSelected(node)} onSelect={selectRenderNode} onToggle={toggleModule} onPointerDown={beginNodeGesture} tx={tx} />)}</g>
      <g className="kernel-edge-layer">{scene.edges.map((edge) => {
        const token = RELATION_TOKENS[edge.relation];
        const edgeSelected = edge.canonicalEdgeIds.some((id) => selectedEdges.has(id));
        return <g key={edge.edgeId} className={`kernel-edge${edgeSelected ? " selected" : ""}`} data-kernel-edge-id={edge.edgeId} data-canonical-edge-ids={edge.canonicalEdgeIds.join(" ")}>
          <path d={edge.path} stroke={token.color} strokeDasharray={token.dash} markerEnd="url(#kernel-arrow)" />
          <path className="kernel-edge-hit" d={edge.path} onClick={(event) => { event.stopPropagation(); setActiveRenderNodeId(null); onSelectEdge?.(edge.canonicalEdgeIds, event.shiftKey); }} />
          {labelStyle !== "endpoint" && <g className={`kernel-edge-label ${labelStyle}`} transform={`translate(${edge.labelPoint.x} ${edge.labelPoint.y}) rotate(${edge.labelAngle})`}>
            {labelStyle === "plate" && <rect x={-Math.max(22, edge.label.length * 3.1)} y={-9} width={Math.max(44, edge.label.length * 6.2)} height={18} rx={3} />}
            <text textAnchor="middle" y={3}>{edge.label}</text>
          </g>}
        </g>;
      })}</g>
      <g className="kernel-detail-flow-layer">{scene.details.flatMap((detail) => detail.primitives.filter((primitive): primitive is Extract<RenderDetailPrimitive, { kind: "flow" }> => primitive.kind === "flow").map((primitive) => <DetailFlow key={primitive.primitiveId} detail={detail} primitive={primitive} />))}</g>
      <g className="kernel-detail-primitive-layer">{scene.details.flatMap((detail) => detail.primitives.filter((primitive): primitive is Exclude<RenderDetailPrimitive, { kind: "flow" }> => primitive.kind !== "flow").map((primitive) => <DetailPrimitive key={primitive.primitiveId} detail={detail} primitive={primitive} selected={primitive.canonicalIds.some((id) => selected.has(id))} onSelect={selectDetailCanonical} onPointerDown={beginDetailGesture} />))}</g>
      <g className="kernel-detail-boundary-layer">{scene.details.flatMap((detail) => [
        <circle key={`${detail.bindingId}:entry`} className="kernel-detail-boundary-portal entry" cx={detail.entryPoint.x} cy={detail.entryPoint.y} r={4} data-detail-binding-id={detail.bindingId}><title>{`Entry portal: ${detail.templateId}`}</title></circle>,
        <circle key={`${detail.bindingId}:exit`} className="kernel-detail-boundary-portal exit" cx={detail.exitPoint.x} cy={detail.exitPoint.y} r={4} data-detail-binding-id={detail.bindingId}><title>{`Exit portal: ${detail.templateId}`}</title></circle>,
      ])}</g>
      <g className="kernel-portal-layer">{scene.portals.map((portal) => <circle key={portal.portalId} className={`kernel-portal ${portal.direction}`} cx={portal.point.x} cy={portal.point.y} r={3.4} data-portal-id={portal.portalId} data-module-node-id={portal.moduleNodeId} data-edge-id={portal.edgeId} />)}</g>
      <g className="kernel-node-layer">{standardNodes.map((node) => <StandardNode key={node.nodeId} node={node} selected={renderNodeSelected(node)} nodeStyle={nodeStyle} incoming={scene.edges.filter((edge) => nodeByPort.get(edge.targetPortId) === node.nodeId).length} outgoing={scene.edges.filter((edge) => nodeByPort.get(edge.sourcePortId) === node.nodeId).length} onSelect={selectRenderNode} onToggle={toggleModule} onPointerDown={beginNodeGesture} tx={tx} />)}</g>
      <g className="kernel-resize-layer">{selectedRenderNodes.filter((node) => !scene.details.some((detail) => detail.nodeId === node.nodeId)).map((node) => <rect
        key={node.nodeId}
        className="kernel-resize-handle"
        x={node.bounds.x + node.bounds.width - 6}
        y={node.bounds.y + node.bounds.height - 6}
        width={12}
        height={12}
        rx={2}
        data-resize-node-id={node.nodeId}
        onPointerDown={(event) => beginResizeGesture(event, node)}
        onClick={(event) => event.stopPropagation()}
      />)}</g>
      {labelStyle === "endpoint" && <g className="kernel-endpoint-labels">{scene.edges.map((edge) => {
        const target = nodeById.get(nodeByPort.get(edge.targetPortId) ?? "");
        if (!target) return null;
        return <text key={edge.edgeId} x={target.bounds.x + 8} y={target.bounds.y - 7}>{edge.label}</text>;
      })}</g>}
      {selectionBox && <rect className="kernel-selection-box" x={selectionBox.x} y={selectionBox.y} width={selectionBox.width} height={selectionBox.height} />}
    </svg>
    <div className="kernel-relation-legend" aria-label={tx("Visible relation types", "可见关系类型")}>{visibleRelations.map((relation) => {
      const token = RELATION_TOKENS[relation];
      return <span key={relation}><i style={{ borderColor: token.color, borderTopStyle: token.dash ? "dashed" : "solid" }} />{token.label}</span>;
    })}</div>
    {scene.diagnostics.length > 0 && <div className="kernel-diagnostics" title={scene.diagnostics.map((item) => item.message).join("\n")}>{scene.diagnostics.length} {tx("projection diagnostics", "条投影诊断")}</div>}
  </div>;
}
