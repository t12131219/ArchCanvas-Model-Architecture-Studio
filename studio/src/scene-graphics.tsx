import React from "react";

import { edgeLabelPoint } from "./scene-performance";

export type SceneMode = "explore" | "layout" | "model";

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Point {
  x: number;
  y: number;
}

export interface SceneNode {
  scene_node_id: string;
  view_node_id: string;
  canonical_node_ids: string[];
  bounds: Rect;
  shape: "container" | "rect" | "tensor" | "merge" | "io" | "state" | "opaque" | "projection" | "activation" | "normalization" | "attention" | "transform" | "condition" | "repeat";
  label_lines: string[];
  secondary_label?: string;
  fill: string;
  stroke: string;
  parent_scene_node_id?: string;
  evidence_ids: string[];
}

export interface SceneEdge {
  scene_edge_id: string;
  source_scene_node_id: string;
  target_scene_node_id: string;
  points: Point[];
  edge_type: string;
  visual_relation: string;
  stroke: string;
  dash?: string;
  width: number;
  label: string;
}

export interface SceneProof {
  status: "checking" | "conditional" | "unproven" | "invalid" | "stale" | "proven" | "review-ready";
  message: string;
}

function nodeShape(node: SceneNode): React.ReactNode {
  const { x, y, width, height } = node.bounds;
  if (node.shape === "merge") {
    return <polygon className="node-shape" points={`${x + width / 2},${y} ${x + width},${y + height / 2} ${x + width / 2},${y + height} ${x},${y + height / 2}`} fill={node.fill} stroke={node.stroke} />;
  }
  if (node.shape === "projection" || node.shape === "transform") {
    const inset = Math.min(22, width * 0.12);
    return <polygon className="node-shape" points={`${x + inset},${y} ${x + width},${y} ${x + width - inset},${y + height} ${x},${y + height}`} fill={node.fill} stroke={node.stroke} />;
  }
  if (node.shape === "condition") {
    const inset = Math.min(28, width * 0.16);
    return <polygon className="node-shape" points={`${x + inset},${y} ${x + width - inset},${y} ${x + width},${y + height / 2} ${x + width - inset},${y + height} ${x + inset},${y + height} ${x},${y + height / 2}`} fill={node.fill} stroke={node.stroke} />;
  }
  if (node.shape === "activation") {
    return <ellipse className="node-shape" cx={x + width / 2} cy={y + height / 2} rx={width / 2} ry={height / 2} fill={node.fill} stroke={node.stroke} />;
  }
  if (node.shape === "tensor" || node.shape === "repeat") {
    return <>{[8, 4, 0].map((offset, index) => <rect key={offset} className={index === 2 ? "node-shape" : "shape-detail"} x={x + offset} y={y - offset} width={width - 8} height={height} rx={5} fill={node.fill} stroke={node.stroke} />)}</>;
  }
  if (node.shape === "normalization" || node.shape === "attention") {
    const radius = node.shape === "normalization" ? 18 : 6;
    return (
      <>
        <rect className="node-shape" x={x} y={y} width={width} height={height} rx={radius} fill={node.fill} stroke={node.stroke} />
        <rect className="shape-detail" x={x + 6} y={y + 6} width={width - 12} height={height - 12} rx={Math.max(3, radius - 5)} fill="none" stroke={node.stroke} />
      </>
    );
  }
  return <rect className="node-shape" x={x} y={y} width={width} height={height} rx={node.shape === "io" ? 28 : node.shape === "container" ? 3 : 6} fill={node.fill} stroke={node.stroke} strokeDasharray={node.shape === "opaque" ? "6 4" : undefined} />;
}

export function relationLabel(relation: string): string {
  const labels = { sequence: "Flow", "parallel-branch": "Branch", merge: "Merge", residual: "Residual", "shape-transform": "Transform", "memory-reference": "Memory", condition: "Condition", routing: "Routing", "state-update": "State", "parameter-share": "Shared", "training-only": "Training" };
  return labels[relation as keyof typeof labels] ?? relation;
}

export function updatePreviewEdgeElement(element: SVGGElement, edge: SceneEdge, points: Point[]) {
  const pointString = points.map((point) => `${point.x},${point.y}`).join(" ");
  for (const polyline of element.querySelectorAll<SVGPolylineElement>("polyline")) polyline.setAttribute("points", pointString);
  const label = element.querySelector<SVGTextElement>(".edge-label");
  if (label) {
    const labelPoint = edgeLabelPoint({ ...edge, points });
    label.setAttribute("x", String(labelPoint.x));
    label.setAttribute("y", String(labelPoint.y));
  }
  const junction = element.querySelector<SVGCircleElement>(".edge-junction");
  if (junction) {
    const point = edge.visual_relation === "parallel-branch" ? points[0] : points.at(-1);
    if (point) {
      junction.setAttribute("cx", String(point.x));
      junction.setAttribute("cy", String(point.y));
    }
  }
}

interface SceneNodeGraphicProps {
  node: SceneNode;
  depth: number;
  isSelected: boolean;
  isEdgeSource: boolean;
  isEdgeTarget: boolean;
  isCollapsed: boolean;
  publicationCollapsed: boolean;
  isStructuralContainer: boolean;
  proof?: SceneProof;
  labelScale: number;
  mode: SceneMode;
  onBeginDrag: (event: React.PointerEvent, node: SceneNode) => void;
  onExpand: (node: SceneNode) => void;
}

export const SceneNodeGraphic = React.memo(function SceneNodeGraphic({
  node, depth, isSelected, isEdgeSource, isEdgeTarget, isCollapsed, publicationCollapsed,
  isStructuralContainer, proof, labelScale, mode, onBeginDrag, onExpand,
}: SceneNodeGraphicProps) {
  const isRoot = !node.parent_scene_node_id;
  return (
    <g className={`scene-node scene-depth-${Math.min(depth, 4)} ${isRoot ? "root" : ""} ${isSelected ? "selected" : ""} ${isEdgeSource ? "edge-source" : ""} ${isEdgeTarget ? "edge-target" : ""} ${isCollapsed ? "collapsed" : ""} ${publicationCollapsed ? "publication-collapsed" : ""} ${proof ? `proof-${proof.status}` : ""}`} data-scene-node-id={node.scene_node_id} data-scene-depth={depth} data-node-shape={node.shape} tabIndex={isRoot ? -1 : 0} onPointerDown={(event) => onBeginDrag(event, node)} onClick={() => { if (!isRoot && mode === "explore" && publicationCollapsed) onExpand(node); }} onDoubleClick={() => !isRoot && publicationCollapsed && onExpand(node)} onKeyDown={(event) => { if (event.key === "Enter" && !isRoot) onExpand(node); }}>
      {nodeShape(node)}
      {isRoot || isStructuralContainer ? <text className="container-label" x={node.bounds.x + 14} y={isRoot ? node.bounds.y + 23 : node.bounds.y - 8}>{node.label_lines.join(" ")}</text> : <>{node.label_lines.map((line, index) => <text key={line + index} className="node-label" textAnchor="middle" x={node.bounds.x + node.bounds.width / 2} y={node.bounds.y + node.bounds.height / 2 - ((node.label_lines.length - 1) * 15 * Math.min(labelScale, 1.7)) / 2 + index * 15 * Math.min(labelScale, 1.7)}>{line}</text>)}{node.secondary_label && <text className="node-secondary" textAnchor="middle" x={node.bounds.x + node.bounds.width / 2} y={node.bounds.y + node.bounds.height - 14}>{node.secondary_label.slice(0, 28)}</text>}</>}
      {isSelected && !isRoot && <><rect className="selection-box" x={node.bounds.x - 4} y={node.bounds.y - 4} width={node.bounds.width + 8} height={node.bounds.height + 8} /><circle className="port" cx={node.bounds.x} cy={node.bounds.y + node.bounds.height / 2} r={4} /><circle className="port" cx={node.bounds.x + node.bounds.width} cy={node.bounds.y + node.bounds.height / 2} r={4} /></>}
      {proof && !isRoot && <g className="proof-overlay" aria-label={`${proof.status}: ${proof.message}`}><rect x={node.bounds.x - 7} y={node.bounds.y - 7} width={node.bounds.width + 14} height={node.bounds.height + 14} rx={7} /><text x={node.bounds.x + node.bounds.width - 3} y={node.bounds.y + 3}>{proof.status === "invalid" ? "×" : proof.status === "unproven" ? "?" : "!"}</text></g>}
    </g>
  );
});

interface SceneEdgeGraphicProps {
  edge: SceneEdge;
  points: Point[];
  overlay: boolean;
  related: boolean;
  selected: boolean;
  semanticZoom: "overview" | "standard" | "detail";
  layoutFamily: string;
  sourceLabel: string;
  targetLabel: string;
  toLabel: string;
  onChooseAtClient: (clientX: number, clientY: number, edgeId: string) => void;
  onChoose: (edgeId: string) => void;
}

export const SceneEdgeGraphic = React.memo(function SceneEdgeGraphic({
  edge, points, overlay, related, selected, semanticZoom, layoutFamily, sourceLabel,
  targetLabel, toLabel, onChooseAtClient, onChoose,
}: SceneEdgeGraphicProps) {
  const labelPoint = edgeLabelPoint({ ...edge, points });
  const criticalLabel = ["residual", "shape-transform", "memory-reference", "condition", "routing", "state-update"].includes(edge.visual_relation);
  const showLabel = semanticZoom === "detail" ? !layoutFamily.endsWith("-vertical") || !["sequence", "parallel-branch"].includes(edge.visual_relation) : semanticZoom === "standard" ? !["sequence", "parallel-branch"].includes(edge.visual_relation) : false;
  const pointString = points.map((point) => `${point.x},${point.y}`).join(" ");
  const visibleLabel = semanticZoom === "detail" ? edge.label.slice(0, 38) : relationLabel(edge.visual_relation);
  return (
    <g className={`scene-edge relation-${edge.visual_relation} ${related ? "edge-related" : ""} ${selected ? "edge-selected" : ""} ${overlay ? "edge-overlay" : "edge-base"}`} data-scene-edge-id={edge.scene_edge_id} data-edge-layer={overlay ? "overlay" : "base"} data-visual-relation={edge.visual_relation} role={overlay ? undefined : "button"} tabIndex={overlay ? undefined : 0} aria-label={overlay ? undefined : `${sourceLabel} ${toLabel} ${targetLabel}, ${relationLabel(edge.visual_relation)}`} aria-pressed={overlay ? undefined : selected} aria-hidden={overlay || undefined} onPointerDown={overlay ? undefined : (event) => event.stopPropagation()} onClick={overlay ? undefined : (event) => { event.stopPropagation(); onChooseAtClient(event.clientX, event.clientY, edge.scene_edge_id); }} onKeyDown={overlay ? undefined : (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onChoose(edge.scene_edge_id); } }}>
      {!overlay && <polyline className="edge-hit-target" points={pointString} fill="none" stroke="transparent" vectorEffect="non-scaling-stroke" />}
      {overlay && <polyline className="edge-highlight-halo" points={pointString} fill="none" vectorEffect="non-scaling-stroke" />}
      <polyline className="edge-path" points={pointString} fill="none" stroke={edge.stroke} strokeWidth={Math.max(edge.width, related ? 3.2 : 2.15)} strokeDasharray={edge.dash} markerEnd="url(#studio-arrow)" vectorEffect="non-scaling-stroke" />
      {edge.visual_relation === "parallel-branch" && <circle className="edge-junction" cx={points[0].x} cy={points[0].y} r={3.2} fill={edge.stroke} />}
      {edge.visual_relation === "merge" && <circle className="edge-junction" cx={points.at(-1)!.x} cy={points.at(-1)!.y} r={3.2} fill="var(--paper)" stroke={edge.stroke} strokeWidth={1.5} />}
      {showLabel && <text className={`edge-label ${criticalLabel ? "critical" : ""}`} textAnchor="middle" x={labelPoint.x} y={labelPoint.y}>{visibleLabel}</text>}
      {!overlay && <title>{sourceLabel} → {targetLabel} · {relationLabel(edge.visual_relation)}</title>}
    </g>
  );
});
