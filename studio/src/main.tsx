import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertTriangle,
  ArrowRight,
  Box,
  Braces,
  ChevronDown,
  ChevronRight,
  CircleDot,
  CornerDownLeft,
  Download,
  Eye,
  FileCode2,
  FolderOpen,
  Focus,
  GitBranch,
  Grip,
  History,
  Layers3,
  Link2,
  LockKeyhole,
  Maximize2,
  Moon,
  Move,
  PanelBottom,
  PanelLeft,
  PanelRight,
  Pin,
  PinOff,
  Play,
  Plus,
  Redo2,
  RefreshCw,
  Route,
  Save,
  Search,
  ShieldCheck,
  Sun,
  Trash2,
  Undo2,
  Variable,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";

import { JobPollingController, type StudioJob } from "./jobs";
import { initialProjectSelection } from "./project-launch";
import { constrainDragDelta } from "./drag";
import {
  relationLabel,
  SceneEdgeGraphic,
  SceneNodeGraphic,
  updatePreviewEdgeElement,
  type Point,
  type Rect,
  type SceneEdge,
  type SceneNode,
} from "./scene-graphics";
import { buildSceneRenderIndex, previewEdgePoints } from "./scene-performance";
import { nodesInSelection, selectionBounds } from "./selection";
import {
  studioModelIdentity,
  visibleNavigationRows,
  visibleProjectEntrypoints,
} from "./tree";
import "./styles.css";

type Mode = "explore" | "layout" | "model";
type Projection = "module" | "source";
type RouteStrategy = "avoid" | "balanced" | "compact";
type LayoutMode = "auto" | "dual-swimlane" | "single-lane" | "hierarchical" | "branch-tree" | "force-directed" | "radial" | "orthogonal";
type RouteSide = "left" | "right" | "top" | "bottom";
type Locale = "en" | "zh";
type DraftEdgePolicy = "replace-input" | "add-residual" | "concat" | "fanout" | "disconnect";

interface LanguageContextValue {
  locale: Locale;
  tx: (english: string, chinese: string) => string;
}

interface CondaEnvironment {
  name: string;
  path: string;
  python: string;
  active: boolean;
}

interface ProjectEntrypoint {
  entrypoint: string;
  path: string;
  framework: string;
  kind: string;
  confidence: string;
  parent_entrypoint: string | null;
  parent_entrypoints: string[];
  root_entrypoint: string;
  depth: number;
  contains: string[];
  child_count: number;
  top_level: boolean;
  analysis_root: string;
  analysis_entrypoint: string;
  config_paths: string[];
  category: "model" | "encoder" | "decoder" | "backbone" | "attention" | "head" | "block" | "layer" | "component";
}

interface PendingProject {
  project: StudioState["project"];
  discovery: {
    entrypoints: ProjectEntrypoint[];
    configs: Array<{ path: string }>;
    scanned_files: number;
    environment?: CondaEnvironment | null;
  };
}

interface DirectoryBrowserState {
  path: string;
  parent: string | null;
  breadcrumbs: Array<{ name: string; path: string }>;
  directories: Array<{ name: string; path: string }>;
  truncated: boolean;
}

const LanguageContext = React.createContext<LanguageContextValue>({
  locale: "zh",
  tx: (_english, chinese) => chinese,
});

function useLanguage(): LanguageContextValue {
  return React.useContext(LanguageContext);
}

interface SceneAnnotation {
  annotation_id: string;
  text: string;
  bounds: Rect;
  fill: string;
  stroke: string;
}

interface Scene {
  scene_id: string;
  view_id: string;
  layout_family: string;
  paper_width: number;
  paper_height: number;
  nodes: SceneNode[];
  edges: SceneEdge[];
  caption?: string;
  legend_placement?: "top-left" | "top-right" | "bottom-left" | "bottom-right" | "hidden";
  annotations: SceneAnnotation[];
}

interface LayoutCandidate {
  candidate_id: string;
  input_fingerprint: string;
  strategy: string;
  score: number;
  metrics: {
    paper_area: number;
    route_length: number;
    movement: number;
    changed_nodes: number;
    route_changes: number;
  };
  supported_fixes: string[];
  diagnostics: Diagnostic[];
  scene: Scene;
}

interface PublicationNode {
  view_node_id: string;
  semantic_name: string;
  canonical_node_ids: string[];
  collapsed: boolean;
  attributes: Record<string, unknown>;
}

interface PublicationView {
  projection_id: string;
  frontier_digest: string;
  visible_depth: number;
  max_depth: number;
  fully_expanded: boolean;
  name: string;
  nodes: PublicationNode[];
}

interface Evidence {
  evidence_id: string;
  kind: string;
  path?: string;
  symbol?: string;
  claim: string;
  confidence: string;
  span?: { start_line: number; end_line: number };
  runtime_trace_id?: string;
  runtime_observation_ids?: string[];
}

interface Diagnostic {
  code: string;
  severity: string;
  message: string;
  target_ids: string[];
}

interface ArchitectureParameter {
  name: string;
  source_expression: string;
  value: unknown;
  origin: string;
  evidence_ids: string[];
}

interface ArchitecturePort {
  port_id: string;
  name: string;
  direction: "input" | "output";
  role: string;
}

interface ArchitectureNodeView {
  node_id: string;
  semantic_name: string;
  kind: string;
  source_symbol?: string;
  parent_id?: string;
  confidence: string;
  evidence_ids: string[];
  attributes: Record<string, unknown>;
  parameters: ArchitectureParameter[];
  input_ports: ArchitecturePort[];
  output_ports: ArchitecturePort[];
}

interface ArchitectureTensor {
  tensor_id: string;
  role: string;
  producer_id: string;
  consumer_ids: string[];
  symbolic_shape: string;
  semantic_axes: string[];
  dtype: string;
  confidence: string;
}

interface HierarchyNode {
  hierarchy_node_id: string;
  parent_hierarchy_node_id?: string;
  semantic_name: string;
  depth: number;
  canonical_node_ids: string[];
}

interface SourceExcerpt {
  path: string;
  sha256: string;
  revision: string;
  start_line: number;
  end_line: number;
  highlight_start_line: number;
  highlight_end_line: number;
  lines: Array<{ number: number; text: string }>;
}

interface GraphDelta {
  added_nodes: string[];
  removed_nodes: string[];
  changed_nodes: string[];
  added_edges: string[];
  removed_edges: string[];
  changed_edges: string[];
  added_ports: string[];
  removed_ports: string[];
  changed_ports: string[];
  added_tensors: string[];
  removed_tensors: string[];
  changed_tensors: string[];
  added_fanouts: string[];
  removed_fanouts: string[];
  changed_fanouts: string[];
  added_config_predicates: string[];
  removed_config_predicates: string[];
  changed_config_predicates: string[];
  changed_parameters: Array<{
    node_id: string;
    parameter_name: string;
    before: unknown;
    after: unknown;
    source_expression: string;
  }>;
  changed_shapes: Array<{ subject_id: string; before: string; after: string }>;
}

interface SourceTransaction {
  transaction_id: string;
  state: string;
  request: {
    target_node_id?: string;
    operation: "set_parameter" | "replace_activation" | "insert_layer_norm" | "edit_source_buffers";
    parameter_name?: string;
    new_value?: unknown;
    parameters?: Record<string, unknown>;
    buffers?: Array<{ path: string; base_sha256: string; content: string }>;
  };
  source_diff: string;
  expected_delta: GraphDelta;
  observed_delta?: GraphDelta;
  gates: Array<{ gate: string; status: string; message: string }>;
  diagnostics: Diagnostic[];
}

interface AgentProposal {
  proposal_id: string;
  status: "handoff-required";
  reason_code: string;
  summary: string;
  source_context: Record<string, unknown>;
  permissions: { shell: false; network: false; source_write: false };
}

interface SourceWorkspaceFile {
  path: string;
  base_sha256: string;
  staged_sha256: string | null;
  working_sha256: string | null;
  state: "clean" | "modified" | "stale" | "readonly";
  opened: boolean;
  size: number;
  readonly_reason: string | null;
}

interface SourceWorkspaceBuffer {
  path: string;
  revision: number;
  base_sha256: string;
  staged_sha256: string;
  working_sha256: string;
  state: "clean" | "modified" | "stale";
  base_content: string;
  staged_content: string;
  working_content: string;
  diff: string;
}

interface CanonicalDeleteImpact {
  node_id: string;
  semantic_name: string;
  input_fingerprint: string;
  incoming_edge_ids: string[];
  outgoing_edge_ids: string[];
  produced_tensor_ids: string[];
  downstream_node_ids: string[];
  fanout_ids: string[];
  shared_parameter_node_ids: string[];
  child_node_ids: string[];
  repeat_id: string | null;
  execution_predicate: string;
  source_evidence_ids: string[];
  runtime_evidence_ids: string[];
  expected_delta: GraphDelta;
  required_action: string;
  blocking_reasons: string[];
}

interface StudioState {
  session_nonce?: string;
  project: {
    project_id: string;
    root: string;
    generation: number;
    framework: string;
    environment_path?: string | null;
    python_executable?: string | null;
  };
  architecture: {
    architecture_id: string;
    entrypoint: string;
    nodes: ArchitectureNodeView[];
    tensors: ArchitectureTensor[];
  };
  snapshot: {
    project_root: string;
    entrypoint: string;
    revision: string;
    source_files: Array<{ path: string; sha256: string }>;
  };
  hierarchy: { root_node_id: string; max_depth: number; nodes: HierarchyNode[] };
  evidence: Evidence[];
  runtime: {
    trace: {
      trace_id: string;
      environment: { selected_device: string; torch_version: string };
      observations: unknown[];
    };
    node_evidence: Record<string, string[]>;
  } | null;
  active_projection_id: string;
  views: Record<string, PublicationView>;
  scenes: Record<string, Scene>;
  document: {
    source_digest: string;
    visual_patches: unknown[];
    redo_patches: unknown[];
  };
  view_state: {
    navigation_view?: Projection;
    layout_mode?: LayoutMode;
    pinned_node_ids?: string[];
    collapsed_node_ids?: string[];
    theme?: string;
    cameras?: Record<string, { x: number; y: number; zoom: number }>;
    module_expansion?: string[];
    source_expansion?: string[];
    font_scale?: number;
    line_weight?: number;
    palette_overrides?: Record<string, string>;
    caption?: string;
    legend_placement?: "top-left" | "top-right" | "bottom-left" | "bottom-right" | "hidden";
  };
  navigation: {
    active_projection: Projection;
    projections: Record<Projection, {
      projection_id: Projection;
      label: string;
      description: string;
      nodes: NavigationNode[];
    }>;
  };
  draft: {
    draft_id: string;
    revision: number;
    nodes: Array<{
      node_id: string;
      semantic_name: string;
      framework: string;
      node_type: string;
      parent_id?: string | null;
      source_anchor?: string | null;
      parameters: Record<string, unknown>;
      ports: Array<{
        port_id: string;
        name: string;
        direction: "input" | "output";
        role: string;
      }>;
    }>;
    edges: Array<{
      edge_id: string;
      source_port_id: string;
      target_port_id: string;
      policy: DraftEdgePolicy;
      parameters: Record<string, unknown>;
    }>;
    intents: Array<{
      intent_id: string;
      kind: "create-node" | "delete-node" | "connect-ports" | "disconnect-edge" | "replace-node" | "set-parameter" | "edit-source-buffer" | "edit-onnx-initializer" | "edit-onnx-attribute";
      target_ids: string[];
      expected_delta: GraphDelta | null;
      user_input: Record<string, unknown>;
      capability_requirement: string;
    }>;
    lowering_status: "not-planned" | "checking" | "planned" | "blocked";
    proofs: Array<{
      intent_id: string;
      status: "checking" | "conditional" | "unproven" | "invalid" | "stale" | "proven" | "review-ready";
      message: string;
      reason_codes: string[];
      affected_subject_ids: string[];
    }>;
    writeback_summary: { eligibility: "blocked" | "prepare" | "commit"; blocking_intent_ids: string[] };
  };
  source_workspace: {
    workspace_id: string;
    revision: number;
    base_revision: string;
    state: "clean" | "modified" | "stale";
    files: SourceWorkspaceFile[];
  };
  validation_runs: Array<{
    validation_id: string;
    profile: string;
    state: string;
    input_fingerprint: string;
    gate_results: Array<{ gate: string; status: string; message: string }>;
    diagnostics: Diagnostic[];
  }>;
  jobs?: StudioJob<Diagnostic>[];
  diagnostics: Diagnostic[];
  transaction: SourceTransaction | null;
  proposal: AgentProposal | null;
  capabilities: {
    visual_editing: boolean;
    source_editing: boolean;
    runtime_evidence: boolean;
    semantic_transforms: string[];
    proposed_connection: boolean;
    layout_modes?: LayoutMode[];
  };
}

interface VisualPatch {
  patch_id: string;
  operation: string;
  target_id?: string;
  value: Record<string, unknown>;
}

interface DragState {
  startClient: Point;
  baselines: Record<string, Rect>;
  rootIds: string[];
}

interface DragDomPreview {
  nodeElements: Map<string, SVGGElement>;
  edgeElements: Map<string, SVGGElement[]>;
  affectedEdges: Array<{ edge: SceneEdge; index: number }>;
}

interface EdgeEndpointDrag {
  edgeId: string;
  endpoint: "source" | "target";
  points: Point[];
}

interface PanelSizes {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

type PanelResizeEdge = keyof PanelSizes;

interface PanelResizeState {
  edge: PanelResizeEdge;
  startClient: Point;
  sizes: PanelSizes;
}

interface SearchResult {
  id: string;
  kind: string;
  title: string;
  aliases: string[];
  canonical_ids: string[];
  view_bindings: Array<{ projection_id: string; scene_id: string; scene_node_id: string }>;
  facets: Record<string, string>;
}

interface PanState {
  startClient: Point;
  startViewBox: [number, number, number, number];
}

interface MarqueeState {
  start: Point;
  current: Point;
}

interface NavigationNode {
  id: string;
  parent_id: string | null;
  kind: string;
  label: string;
  depth: number;
  relation: string;
  canonical_ids: string[];
  evidence_ids: string[];
  path?: string | null;
  span?: { start_line: number; end_line: number; start_column: number; end_column: number } | null;
  reference: boolean;
  secondary_label?: string | null;
  binding_status: "exact" | "ambiguous" | "unbound";
  child_count: number;
  sibling_index: number;
  sibling_count: number;
}

const EMPTY_POSITION_PREVIEW: Readonly<Record<string, Point>> = {};
const PROOF_RANK: Readonly<Record<string, number>> = {
  invalid: 7,
  stale: 6,
  unproven: 5,
  conditional: 4,
  checking: 3,
  proven: 2,
  "review-ready": 1,
};

function embeddedState(): StudioState | null {
  const element = document.getElementById("archcanvas-studio-data");
  if (!element?.textContent) return null;
  return JSON.parse(element.textContent) as StudioState;
}

function expansionState(state: StudioState | null): Record<Projection, Set<string>> {
  const defaults = (kind: Projection) => new Set(
    state?.navigation?.projections[kind].nodes
      .filter((item) => item.depth === 0 && item.child_count > 0)
      .map((item) => item.id) ?? [],
  );
  return {
    module: state?.view_state.module_expansion
      ? new Set(state.view_state.module_expansion)
      : defaults("module"),
    source: state?.view_state.source_expansion
      ? new Set(state.view_state.source_expansion)
      : defaults("source"),
  };
}

function patchId(operation: string): string {
  const random = crypto.getRandomValues(new Uint32Array(2));
  return `patch:${operation}.${Date.now().toString(36)}.${random[0].toString(36)}${random[1].toString(36)}`;
}

function useStableEvent<Args extends unknown[]>(callback: (...args: Args) => void) {
  const callbackRef = useRef(callback);
  useLayoutEffect(() => {
    callbackRef.current = callback;
  });
  return useMemo(() => (...args: Args) => callbackRef.current(...args), []);
}

function sceneDescendantIds(scene: Scene, rootIds: string[]): string[] {
  const children = new Map<string, string[]>();
  for (const node of scene.nodes) {
    if (!node.parent_scene_node_id) continue;
    children.set(node.parent_scene_node_id, [
      ...(children.get(node.parent_scene_node_id) ?? []),
      node.scene_node_id,
    ]);
  }
  const collected = new Set<string>();
  const visit = (nodeId: string) => {
    if (collected.has(nodeId)) return;
    collected.add(nodeId);
    for (const childId of children.get(nodeId) ?? []) visit(childId);
  };
  for (const rootId of rootIds) visit(rootId);
  return scene.nodes
    .map((node) => node.scene_node_id)
    .filter((nodeId) => collected.has(nodeId));
}

function distanceToPolyline(point: Point, points: Point[]): number {
  let nearest = Number.POSITIVE_INFINITY;
  for (let index = 0; index < points.length - 1; index += 1) {
    const start = points[index];
    const end = points[index + 1];
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const lengthSquared = dx * dx + dy * dy;
    const projection = lengthSquared === 0
      ? 0
      : Math.max(0, Math.min(1, ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared));
    const x = start.x + projection * dx;
    const y = start.y + projection * dy;
    nearest = Math.min(nearest, Math.hypot(point.x - x, point.y - y));
  }
  return nearest;
}

function boundarySide(point: Point, bounds: Rect): RouteSide {
  const distances: Array<[number, RouteSide]> = [
    [Math.abs(point.x - bounds.x), "left"],
    [Math.abs(point.x - bounds.x - bounds.width), "right"],
    [Math.abs(point.y - bounds.y), "top"],
    [Math.abs(point.y - bounds.y - bounds.height), "bottom"],
  ];
  return distances.sort((left, right) => left[0] - right[0])[0][1];
}

function routeStub(point: Point, side: RouteSide, distance = 24): Point {
  if (side === "left") return { x: point.x - distance, y: point.y };
  if (side === "right") return { x: point.x + distance, y: point.y };
  if (side === "top") return { x: point.x, y: point.y - distance };
  return { x: point.x, y: point.y + distance };
}

function compactRoute(route: Point[]): Point[] {
  const compact: Point[] = [];
  for (const point of route) {
    if (compact.length && compact.at(-1)!.x === point.x && compact.at(-1)!.y === point.y) continue;
    compact.push(point);
    while (compact.length >= 3) {
      const [first, middle, last] = compact.slice(-3);
      if ((first.x === middle.x && middle.x === last.x) || (first.y === middle.y && middle.y === last.y)) {
        compact.splice(-2, 1);
      } else break;
    }
  }
  return compact;
}

function segmentLengthInside(start: Point, end: Point, bounds: Rect): number {
  if (Math.abs(start.x - end.x) < 0.001) {
    if (!(bounds.x < start.x && start.x < bounds.x + bounds.width)) return 0;
    return Math.max(0, Math.min(Math.max(start.y, end.y), bounds.y + bounds.height) - Math.max(Math.min(start.y, end.y), bounds.y));
  }
  if (Math.abs(start.y - end.y) < 0.001) {
    if (!(bounds.y < start.y && start.y < bounds.y + bounds.height)) return 0;
    return Math.max(0, Math.min(Math.max(start.x, end.x), bounds.x + bounds.width) - Math.max(Math.min(start.x, end.x), bounds.x));
  }
  return Math.hypot(end.x - start.x, end.y - start.y);
}

function orthogonalSegmentInteraction(firstStart: Point, firstEnd: Point, secondStart: Point, secondEnd: Point): [number, number] {
  const firstVertical = Math.abs(firstStart.x - firstEnd.x) < 0.001;
  const secondVertical = Math.abs(secondStart.x - secondEnd.x) < 0.001;
  if (firstVertical === secondVertical) {
    const firstAxis = firstVertical ? firstStart.x : firstStart.y;
    const secondAxis = secondVertical ? secondStart.x : secondStart.y;
    if (Math.abs(firstAxis - secondAxis) >= 0.001) return [0, 0];
    const firstInterval = firstVertical
      ? [Math.min(firstStart.y, firstEnd.y), Math.max(firstStart.y, firstEnd.y)]
      : [Math.min(firstStart.x, firstEnd.x), Math.max(firstStart.x, firstEnd.x)];
    const secondInterval = secondVertical
      ? [Math.min(secondStart.y, secondEnd.y), Math.max(secondStart.y, secondEnd.y)]
      : [Math.min(secondStart.x, secondEnd.x), Math.max(secondStart.x, secondEnd.x)];
    return [0, Math.max(0, Math.min(firstInterval[1], secondInterval[1]) - Math.max(firstInterval[0], secondInterval[0]))];
  }
  const [verticalStart, verticalEnd] = firstVertical ? [firstStart, firstEnd] : [secondStart, secondEnd];
  const [horizontalStart, horizontalEnd] = firstVertical ? [secondStart, secondEnd] : [firstStart, firstEnd];
  const crossing = horizontalStart.x <= verticalStart.x && verticalStart.x <= horizontalEnd.x
    || horizontalEnd.x <= verticalStart.x && verticalStart.x <= horizontalStart.x;
  const withinVertical = verticalStart.y <= horizontalStart.y && horizontalStart.y <= verticalEnd.y
    || verticalEnd.y <= horizontalStart.y && horizontalStart.y <= verticalStart.y;
  if (!crossing || !withinVertical) return [0, 0];
  const point = { x: verticalStart.x, y: horizontalStart.y };
  const isEndpoint = (candidate: Point, start: Point, end: Point) => (
    (candidate.x === start.x && candidate.y === start.y) || (candidate.x === end.x && candidate.y === end.y)
  );
  return [isEndpoint(point, firstStart, firstEnd) && isEndpoint(point, secondStart, secondEnd) ? 0 : 1, 0];
}

interface RouteReference {
  points: Point[];
  sourceId: string;
  targetId: string;
}

function routeInteractions(
  route: Point[],
  otherRoutes: RouteReference[],
  sourceId: string,
  targetId: string,
): [number, number] {
  let crossings = 0;
  let overlap = 0;
  for (const other of otherRoutes) {
    const routeSegments = route.length - 1;
    const otherSegments = other.points.length - 1;
    for (let index = 0; index < route.length - 1; index += 1) {
      for (let otherIndex = 0; otherIndex < other.points.length - 1; otherIndex += 1) {
        const segmentLength = Math.abs(route[index + 1].x - route[index].x)
          + Math.abs(route[index + 1].y - route[index].y);
        const otherSegmentLength = Math.abs(other.points[otherIndex + 1].x - other.points[otherIndex].x)
          + Math.abs(other.points[otherIndex + 1].y - other.points[otherIndex].y);
        const shortStubs = segmentLength <= 32 && otherSegmentLength <= 32;
        if (
          (shortStubs && sourceId === other.sourceId && index === 0 && otherIndex === 0)
          || (
            shortStubs
            &&
            targetId === other.targetId
            && index === routeSegments - 1
            && otherIndex === otherSegments - 1
          )
        ) continue;
        const [segmentCrossings, segmentOverlap] = orthogonalSegmentInteraction(
          route[index], route[index + 1], other.points[otherIndex], other.points[otherIndex + 1],
        );
        crossings += segmentCrossings;
        overlap += segmentOverlap;
      }
    }
  }
  return [crossings, overlap];
}

function routeMetric(
  route: Point[],
  nodes: SceneNode[],
  relatedIds: Set<string>,
  strategy: RouteStrategy,
  otherRoutes: RouteReference[] = [],
  sourceId = "",
  targetId = "",
): number[] {
  const crossedNodeIds = new Set<string>();
  const crossedContainerIds = new Set<string>();
  let nodeLength = 0;
  let containerLength = 0;
  let clearanceLength = 0;
  let length = 0;
  for (let index = 0; index < route.length - 1; index += 1) {
    const start = route[index];
    const end = route[index + 1];
    length += Math.abs(end.x - start.x) + Math.abs(end.y - start.y);
    for (const node of nodes) {
      if (relatedIds.has(node.scene_node_id)) continue;
      const inside = segmentLengthInside(start, end, node.bounds);
      if (node.shape === "container") {
        containerLength += inside;
        if (inside > 0.001) crossedContainerIds.add(node.scene_node_id);
      }
      else {
        nodeLength += inside;
        if (inside > 0.001) crossedNodeIds.add(node.scene_node_id);
        clearanceLength += segmentLengthInside(start, end, {
          x: node.bounds.x - 10,
          y: node.bounds.y - 10,
          width: node.bounds.width + 20,
          height: node.bounds.height + 20,
        });
      }
    }
  }
  const bends = Math.max(0, route.length - 2);
  const nodeCount = crossedNodeIds.size;
  const containerCount = crossedContainerIds.size;
  const [crossings, overlap] = routeInteractions(route, otherRoutes, sourceId, targetId);
  if (strategy === "avoid") {
    return [
      nodeCount,
      nodeLength,
      containerCount,
      containerLength,
      overlap,
      crossings,
      clearanceLength,
      length,
      bends,
    ];
  }
  if (strategy === "balanced") {
    return [
      nodeCount * 1200 + nodeLength * 24 + containerCount * 300 + clearanceLength * 3
        + containerLength * 5 + crossings * 240 + overlap * 6 + length,
      nodeCount + containerCount,
      crossings,
      overlap,
      bends,
    ];
  }
  return [
    length + nodeCount * 300 + nodeLength * 8 + containerCount * 80 + clearanceLength * 1.5
      + containerLength + crossings * 90 + overlap * 2.5,
    nodeCount + containerCount,
    crossings,
    overlap,
    bends,
  ];
}

function compareMetric(left: number[], right: number[]): number {
  for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
    const difference = (left[index] ?? 0) - (right[index] ?? 0);
    if (difference) return difference;
  }
  return 0;
}

function routeDirectionsValid(route: Point[], sourceSide: RouteSide, targetSide: RouteSide): boolean {
  if (route.length < 2) return false;
  const [first, second] = route;
  const penultimate = route.at(-2)!;
  const last = route.at(-1)!;
  const sourceValid = {
    left: second.y === first.y && second.x <= first.x,
    right: second.y === first.y && second.x >= first.x,
    top: second.x === first.x && second.y <= first.y,
    bottom: second.x === first.x && second.y >= first.y,
  }[sourceSide];
  const targetValid = {
    left: penultimate.y === last.y && penultimate.x <= last.x,
    right: penultimate.y === last.y && penultimate.x >= last.x,
    top: penultimate.x === last.x && penultimate.y <= last.y,
    bottom: penultimate.x === last.x && penultimate.y >= last.y,
  }[targetSide];
  return sourceValid && targetValid;
}

function moveRouteEndpoint(
  points: Point[],
  endpoint: "source" | "target",
  bounds: Rect,
  pointer: Point,
  edge: SceneEdge,
  scene: Scene,
  strategy: RouteStrategy,
): Point[] {
  const clamp = (value: number, minimum: number, maximum: number) => Math.max(minimum, Math.min(maximum, value));
  const inset = Math.min(8, bounds.width / 4, bounds.height / 4);
  const borderCandidates: Array<{ point: Point; side: RouteSide }> = [
    { point: { x: bounds.x, y: clamp(pointer.y, bounds.y + inset, bounds.y + bounds.height - inset) }, side: "left" },
    { point: { x: bounds.x + bounds.width, y: clamp(pointer.y, bounds.y + inset, bounds.y + bounds.height - inset) }, side: "right" },
    { point: { x: clamp(pointer.x, bounds.x + inset, bounds.x + bounds.width - inset), y: bounds.y }, side: "top" },
    { point: { x: clamp(pointer.x, bounds.x + inset, bounds.x + bounds.width - inset), y: bounds.y + bounds.height }, side: "bottom" },
  ];
  const snapped = borderCandidates.sort((left, right) => (
    Math.hypot(pointer.x - left.point.x, pointer.y - left.point.y)
    - Math.hypot(pointer.x - right.point.x, pointer.y - right.point.y)
  ))[0];
  const start = endpoint === "source" ? snapped.point : points[0];
  const end = endpoint === "target" ? snapped.point : points.at(-1)!;
  const sourceNode = scene.nodes.find((node) => node.scene_node_id === edge.source_scene_node_id)!;
  const targetNode = scene.nodes.find((node) => node.scene_node_id === edge.target_scene_node_id)!;
  const sourceSide = endpoint === "source" ? snapped.side : boundarySide(start, sourceNode.bounds);
  const targetSide = endpoint === "target" ? snapped.side : boundarySide(end, targetNode.bounds);
  const sourceStub = routeStub(start, sourceSide);
  const targetStub = routeStub(end, targetSide);
  const routes: Point[][] = [
    [start, sourceStub, { x: sourceStub.x, y: targetStub.y }, targetStub, end],
    [start, sourceStub, { x: targetStub.x, y: sourceStub.y }, targetStub, end],
  ];
  const middleX = (sourceStub.x + targetStub.x) / 2;
  const middleY = (sourceStub.y + targetStub.y) / 2;
  routes.push(
    [start, sourceStub, { x: middleX, y: sourceStub.y }, { x: middleX, y: targetStub.y }, targetStub, end],
    [start, sourceStub, { x: sourceStub.x, y: middleY }, { x: targetStub.x, y: middleY }, targetStub, end],
  );
  const margin = 18;
  const corridorXs = new Set([8, scene.paper_width - 8]);
  const corridorYs = new Set([8, scene.paper_height - 8]);
  for (const node of scene.nodes) {
    const nodeMargin = node.shape === "container" || node.shape === "opaque" ? margin : 10;
    corridorXs.add(Math.max(8, node.bounds.x - nodeMargin));
    corridorXs.add(Math.min(scene.paper_width - 8, node.bounds.x + node.bounds.width + nodeMargin));
    corridorYs.add(Math.max(8, node.bounds.y - nodeMargin));
    corridorYs.add(Math.min(scene.paper_height - 8, node.bounds.y + node.bounds.height + nodeMargin));
  }
  const otherRoutes: RouteReference[] = scene.edges
    .filter((candidate) => candidate.scene_edge_id !== edge.scene_edge_id)
    .map((candidate) => ({
      points: candidate.points,
      sourceId: candidate.source_scene_node_id,
      targetId: candidate.target_scene_node_id,
    }));
  const laneOffsets = [-16, -8, 8, 16];
  for (const other of otherRoutes) {
    for (let index = 0; index < other.points.length - 1; index += 1) {
      const routeStart = other.points[index];
      const routeEnd = other.points[index + 1];
      if (Math.abs(routeEnd.x - routeStart.x) + Math.abs(routeEnd.y - routeStart.y) < 32) continue;
      if (Math.abs(routeStart.x - routeEnd.x) < 0.001) {
        for (const offset of laneOffsets) corridorXs.add(routeStart.x + offset);
      } else if (Math.abs(routeStart.y - routeEnd.y) < 0.001) {
        for (const offset of laneOffsets) corridorYs.add(routeStart.y + offset);
      }
    }
  }
  for (const x of corridorXs) routes.push([start, sourceStub, { x, y: sourceStub.y }, { x, y: targetStub.y }, targetStub, end]);
  for (const y of corridorYs) routes.push([start, sourceStub, { x: sourceStub.x, y }, { x: targetStub.x, y }, targetStub, end]);
  const byId = new Map(scene.nodes.map((node) => [node.scene_node_id, node]));
  const ancestorSets = [edge.source_scene_node_id, edge.target_scene_node_id].map((endpointId) => {
    const ancestors = new Set<string>();
    let current: SceneNode | undefined = byId.get(endpointId);
    while (current) {
      ancestors.add(current.scene_node_id);
      current = current.parent_scene_node_id ? byId.get(current.parent_scene_node_id) : undefined;
    }
    return ancestors;
  });
  const relatedIds = new Set<string>([edge.source_scene_node_id, edge.target_scene_node_id]);
  for (const nodeId of ancestorSets[0]) if (ancestorSets[1].has(nodeId)) relatedIds.add(nodeId);
  return routes
    .map(compactRoute)
    .filter((route) => route.every((point) => point.x >= 0 && point.y >= 0 && point.x <= scene.paper_width && point.y <= scene.paper_height))
    .filter((route) => routeDirectionsValid(route, sourceSide, targetSide))
    .sort((left, right) => compareMetric(
      routeMetric(
        left,
        scene.nodes,
        relatedIds,
        strategy,
        otherRoutes,
        edge.source_scene_node_id,
        edge.target_scene_node_id,
      ),
      routeMetric(
        right,
        scene.nodes,
        relatedIds,
        strategy,
        otherRoutes,
        edge.source_scene_node_id,
        edge.target_scene_node_id,
      ),
    ))[0];
}

function navigationIcon(kind: string): React.ReactNode {
  if (["file", "directory", "repository"].includes(kind)) return <FileCode2 size={12} />;
  if (["class", "function", "control-scope"].includes(kind)) return <Braces size={12} />;
  if (kind === "binding") return <Variable size={12} />;
  if (kind === "return") return <CornerDownLeft size={12} />;
  if (kind === "tensor") return <CircleDot size={12} />;
  if (kind === "callsite") return <GitBranch size={12} />;
  return <Box size={12} />;
}

function navigationRelationLabel(relation: string, locale: Locale): string {
  const labels = locale === "zh" ? {
    "module-containment": "归属", "source-containment": "归属", invocation: "调用", assignment: "赋值", return: "返回", "producer-output": "产出", "consumer-reference": "引用",
  } : {
    "module-containment": "Contains", "source-containment": "Contains", invocation: "Calls", assignment: "Assigns", return: "Returns", "producer-output": "Produces", "consumer-reference": "References",
  };
  return (labels as Record<string, string>)[relation] ?? relation;
}

function navigationSecondaryLabel(label: string | null | undefined, tx: LanguageContextValue["tx"]): string | undefined {
  if (!label) return undefined;
  const contained = label.match(/^包含 (\d+) 个执行对象$/);
  if (!contained) return label;
  const count = Number(contained[1]);
  return tx(
    `Contains ${count} executable ${count === 1 ? "object" : "objects"}`,
    `包含 ${count} 个执行对象`,
  );
}

const DEFAULT_PANEL_SIZES: PanelSizes = { left: 238, right: 320, top: 42, bottom: 132 };

function storedPanelSizes(): PanelSizes {
  try {
    const value = JSON.parse(window.localStorage.getItem("archcanvas.panel-sizes") ?? "null") as Partial<PanelSizes> | null;
    if (!value) return DEFAULT_PANEL_SIZES;
    return {
      left: Number.isFinite(value.left) ? Number(value.left) : DEFAULT_PANEL_SIZES.left,
      right: Number.isFinite(value.right) ? Number(value.right) : DEFAULT_PANEL_SIZES.right,
      top: Number.isFinite(value.top) ? Number(value.top) : DEFAULT_PANEL_SIZES.top,
      bottom: Number.isFinite(value.bottom) ? Number(value.bottom) : DEFAULT_PANEL_SIZES.bottom,
    };
  } catch {
    return DEFAULT_PANEL_SIZES;
  }
}

function App() {
  const [locale, setLocale] = useState<Locale>(() => {
    const stored = window.localStorage.getItem("archcanvas.locale");
    return stored === "en" || stored === "zh" ? stored : "zh";
  });
  const tx = (english: string, chinese: string) => locale === "zh" ? chinese : english;
  const [data, setData] = useState<StudioState | null>(() => embeddedState());
  const [projection, setProjection] = useState<Projection>(
    () => embeddedState()?.navigation?.active_projection ?? embeddedState()?.view_state.navigation_view ?? "module",
  );
  const [expansions, setExpansions] = useState<Record<Projection, Set<string>>>(() => expansionState(embeddedState()));
  const [mode, setMode] = useState<Mode>("explore");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [focusedCanonicalId, setFocusedCanonicalId] = useState<string | null>(null);
  const [focusedNavigationRowId, setFocusedNavigationRowId] = useState<string | null>(null);
  const [inspectorTab, setInspectorTab] = useState<"inspect" | "source" | "visual" | "model" | "evidence">("inspect");
  const [bottomTab, setBottomTab] = useState<"problems" | "source" | "diff" | "validation" | "jobs" | "activity">("problems");
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [validationProfile, setValidationProfile] = useState("fast-static");
  const [routeStrategy, setRouteStrategy] = useState<RouteStrategy>("avoid");
  const [layoutCandidates, setLayoutCandidates] = useState<LayoutCandidate[]>([]);
  const [layoutPreviewId, setLayoutPreviewId] = useState<string | null>(null);
  const [layoutLoading, setLayoutLoading] = useState(false);
  const [projectDialog, setProjectDialog] = useState(true);
  const [draftDialog, setDraftDialog] = useState(false);
  const [draftName, setDraftName] = useState("");
  const [draftType, setDraftType] = useState("");
  const [draftEdgeDialog, setDraftEdgeDialog] = useState(false);
  const [draftEdgeSource, setDraftEdgeSource] = useState("");
  const [draftEdgeTarget, setDraftEdgeTarget] = useState("");
  const [draftEdgePolicy, setDraftEdgePolicy] = useState<DraftEdgePolicy>("fanout");
  const [deleteImpact, setDeleteImpact] = useState<CanonicalDeleteImpact | null>(null);
  const [deleteImpactLoading, setDeleteImpactLoading] = useState(false);
  const [projectRoot, setProjectRoot] = useState(() => embeddedState()?.project.root ?? "");
  const [pendingProject, setPendingProject] = useState<PendingProject | null>(null);
  const [condaEnvironments, setCondaEnvironments] = useState<CondaEnvironment[]>([]);
  const [condaEnvironment, setCondaEnvironment] = useState("");
  const [environmentLoading, setEnvironmentLoading] = useState(false);
  const [projectScanning, setProjectScanning] = useState(false);
  const [projectError, setProjectError] = useState("");
  const [folderPicker, setFolderPicker] = useState<DirectoryBrowserState | null>(null);
  const [selectedFolderPath, setSelectedFolderPath] = useState<string | null>(null);
  const [folderLoading, setFolderLoading] = useState(false);
  const [projectEntrypoint, setProjectEntrypoint] = useState("");
  const [projectModelExpansions, setProjectModelExpansions] = useState<Set<string>>(new Set());
  const [projectFramework, setProjectFramework] = useState("auto");
  const [projectConfig, setProjectConfig] = useState("");
  const [mobileInspector, setMobileInspector] = useState(false);
  const [dark, setDark] = useState(() => embeddedState()?.view_state.theme === "studio-dark");
  const [viewBox, setViewBox] = useState<[number, number, number, number] | null>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 1, height: 1 });
  const [drag, setDrag] = useState<DragState | null>(null);
  const [pan, setPan] = useState<PanState | null>(null);
  const [marquee, setMarquee] = useState<MarqueeState | null>(null);
  const [edgeEndpointDrag, setEdgeEndpointDrag] = useState<EdgeEndpointDrag | null>(null);
  const [edgeRoutePreview, setEdgeRoutePreview] = useState<Point[] | null>(null);
  const [panelSizes, setPanelSizes] = useState<PanelSizes>(storedPanelSizes);
  const [panelResize, setPanelResize] = useState<PanelResizeState | null>(null);
  const [activity, setActivity] = useState<string[]>([tx("Studio document opened", "Studio 文档已打开")]);
  const svgRef = useRef<SVGSVGElement>(null);
  const selections = useRef<Record<string, string[]>>({});
  const cameraTimer = useRef<number | null>(null);
  const navigationTimer = useRef<number | null>(null);
  const navigationQueue = useRef<Promise<void>>(Promise.resolve());
  const expansionsRef = useRef(expansions);
  const navigationTouched = useRef(false);
  const activeModelIdentity = useRef(studioModelIdentity(embeddedState()));
  const previousScene = useRef<Scene | null>(null);
  const framedLayoutFamily = useRef<string | null>(null);
  const viewBoxRef = useRef<[number, number, number, number] | null>(null);
  const viewBoxAnimation = useRef<number | null>(null);
  const dragPreviewFrame = useRef<number | null>(null);
  const dragPreview = useRef<Record<string, Point>>({});
  const pendingDragPreview = useRef<Record<string, Point> | null>(null);
  const dragDomPreview = useRef<DragDomPreview | null>(null);
  const edgePreviewFrame = useRef<number | null>(null);
  const edgeRoutePreviewRef = useRef<Point[] | null>(null);
  const pendingHierarchyFocus = useRef<string | null>(null);
  const jobController = useRef<JobPollingController<StudioState> | null>(null);
  if (jobController.current === null) {
    jobController.current = new JobPollingController<StudioState>(
      window.fetch.bind(window),
      (state) => acceptStudioState(state),
    );
  }

  function restoreNavigationState(state: StudioState) {
    const restored = expansionState(state);
    expansionsRef.current = restored;
    setExpansions(restored);
    setProjection(state.navigation.active_projection ?? state.view_state.navigation_view ?? "module");
  }

  function acceptStudioState(state: StudioState): boolean {
    const nextIdentity = studioModelIdentity(state);
    const modelChanged = activeModelIdentity.current !== nextIdentity;
    if (modelChanged) {
      activeModelIdentity.current = nextIdentity;
      navigationTouched.current = false;
      restoreNavigationState(state);
      selections.current = {};
      setSelectedIds([]);
      setSelectedEdgeId(null);
      setFocusedCanonicalId(null);
      setFocusedNavigationRowId(null);
      setLayoutCandidates([]);
      setLayoutPreviewId(null);
      pendingHierarchyFocus.current = null;
    }
    setData(state);
    return modelChanged;
  }

  useEffect(() => {
    window.localStorage.setItem("archcanvas.locale", locale);
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
  }, [locale]);

  useEffect(() => {
    window.localStorage.setItem("archcanvas.panel-sizes", JSON.stringify(panelSizes));
  }, [panelSizes]);

  useEffect(() => {
    if (!projectDialog || condaEnvironments.length || environmentLoading) return;
    const controller = new AbortController();
    setEnvironmentLoading(true);
    setProjectError("");
    fetch("/api/environments/conda", { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error(await response.text());
        return response.json() as Promise<{ environments: CondaEnvironment[]; selected: string | null }>;
      })
      .then((result) => {
        setCondaEnvironments(result.environments);
        setCondaEnvironment(result.selected ?? result.environments[0]?.path ?? "");
      })
      .catch((error) => {
        if (!controller.signal.aborted) setProjectError(String(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setEnvironmentLoading(false);
      });
    return () => controller.abort();
  }, [projectDialog, condaEnvironments.length]);

  const navigation = data?.navigation.projections[projection];
  const visibleNavigation = navigation
    ? visibleNavigationRows(navigation.nodes, expansions[projection])
    : [];
  const activeProjectionId = data?.active_projection_id;

  useEffect(() => {
    fetch("/api/state", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((state: StudioState) => {
        if (!navigationTouched.current) {
          restoreNavigationState(state);
        }
        acceptStudioState(state);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => () => {
    if (cameraTimer.current !== null) window.clearTimeout(cameraTimer.current);
    if (navigationTimer.current !== null) window.clearTimeout(navigationTimer.current);
    if (viewBoxAnimation.current !== null) cancelAnimationFrame(viewBoxAnimation.current);
    if (dragPreviewFrame.current !== null) cancelAnimationFrame(dragPreviewFrame.current);
    if (edgePreviewFrame.current !== null) cancelAnimationFrame(edgePreviewFrame.current);
    jobController.current?.dispose();
  }, []);

  const baseScene = activeProjectionId ? data?.scenes[activeProjectionId] : undefined;
  const layoutPreview = layoutCandidates.find((item) => item.candidate_id === layoutPreviewId);
  const scene = layoutPreview?.scene ?? baseScene;
  const view = activeProjectionId ? data?.views[activeProjectionId] : undefined;
  const camera = scene ? data?.view_state.cameras?.[scene.scene_id] : undefined;
  const sceneRenderIndex = useMemo(
    () => scene ? buildSceneRenderIndex(scene.nodes) : null,
    [scene?.nodes],
  );
  const publicationNodesById = useMemo(
    () => new Map(view?.nodes.map((node) => [node.view_node_id, node]) ?? []),
    [view?.nodes],
  );
  const proofBySceneNodeId = useMemo(() => {
    const result = new Map<string, StudioState["draft"]["proofs"][number]>();
    if (!scene || !data) return result;
    const proofsBySubject = new Map<string, StudioState["draft"]["proofs"]>();
    for (const proof of data.draft.proofs) {
      for (const subjectId of proof.affected_subject_ids) {
        const matches = proofsBySubject.get(subjectId);
        if (matches) matches.push(proof);
        else proofsBySubject.set(subjectId, [proof]);
      }
    }
    for (const node of scene.nodes) {
      let strongest: StudioState["draft"]["proofs"][number] | undefined;
      for (const canonicalId of node.canonical_node_ids) {
        for (const proof of proofsBySubject.get(canonicalId) ?? []) {
          if (!strongest || PROOF_RANK[proof.status] > PROOF_RANK[strongest.status]) strongest = proof;
        }
      }
      if (strongest) result.set(node.scene_node_id, strongest);
    }
    return result;
  }, [data?.draft.proofs, scene?.nodes]);
  const pinned = useMemo(() => new Set(data?.view_state.pinned_node_ids ?? []), [data?.view_state.pinned_node_ids]);
  const collapsed = useMemo(() => new Set(data?.view_state.collapsed_node_ids ?? []), [data?.view_state.collapsed_node_ids]);

  function writeViewBox(next: [number, number, number, number]) {
    viewBoxRef.current = next;
    svgRef.current?.setAttribute("viewBox", next.join(" "));
  }

  function commitViewBox(next: [number, number, number, number]) {
    writeViewBox(next);
    setViewBox(next);
  }

  useEffect(() => {
    let focusedSceneNodeId: string | null = null;
    if (scene) {
      const layoutChanged = framedLayoutFamily.current !== null
        && framedLayoutFamily.current !== scene.layout_family;
      framedLayoutFamily.current = scene.layout_family;
      let target: [number, number, number, number] = camera
        ? [camera.x, camera.y, scene.paper_width / camera.zoom, scene.paper_height / camera.zoom]
        : [0, 0, scene.paper_width, scene.paper_height];
      const focusId = pendingHierarchyFocus.current;
      const focusViewNode = focusId
        ? view?.nodes.find((node) => node.attributes.hierarchy_node_id === focusId)
        : undefined;
      const hierarchyFocusNode = focusViewNode
        ? scene.nodes.find((node) => node.view_node_id === focusViewNode.view_node_id)
        : undefined;
      const focusNode = hierarchyFocusNode ?? (layoutChanged
        ? scene.nodes.find((node) => node.scene_node_id === selectedIds.at(-1))
        : undefined);
      if (focusNode && svgRef.current) {
        focusedSceneNodeId = focusNode.scene_node_id;
        const horizontalPadding = Math.max(90, focusNode.bounds.width * 0.06);
        const verticalPadding = Math.max(70, focusNode.bounds.height * 0.14);
        let width = focusNode.bounds.width + horizontalPadding * 2;
        let height = focusNode.bounds.height + verticalPadding * 2;
        const viewportRatio = svgRef.current.clientWidth / Math.max(1, svgRef.current.clientHeight);
        if (width / height > viewportRatio) height = width / viewportRatio;
        else width = height * viewportRatio;
        target = [
          focusNode.bounds.x + focusNode.bounds.width / 2 - width / 2,
          focusNode.bounds.y + focusNode.bounds.height / 2 - height / 2,
          width,
          height,
        ];
      }
      pendingHierarchyFocus.current = null;
      const start = viewBoxRef.current;
      if (viewBoxAnimation.current !== null) cancelAnimationFrame(viewBoxAnimation.current);
      if (!start || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        commitViewBox(target);
      } else {
        const started = performance.now();
        const animate = (now: number) => {
          const progress = Math.min(1, (now - started) / 360);
          const eased = 1 - Math.pow(1 - progress, 3);
          const next = start.map((value, index) =>
            value + (target[index] - value) * eased,
          ) as [number, number, number, number];
          writeViewBox(next);
          if (progress < 1) viewBoxAnimation.current = requestAnimationFrame(animate);
          else {
            viewBoxAnimation.current = null;
            setViewBox(target);
          }
        };
        viewBoxAnimation.current = requestAnimationFrame(animate);
      }
    }
    setSelectedIds((current) => {
      const remembered = activeProjectionId ? selections.current[activeProjectionId] : undefined;
      const next = focusedSceneNodeId
        ? [focusedSceneNodeId]
        : remembered ?? current.filter((id) => scene?.nodes.some((node) => node.scene_node_id === id));
      if (activeProjectionId) selections.current[activeProjectionId] = next;
      return next;
    });
    setSelectedEdgeId(null);
    setEdgeEndpointDrag(null);
    setEdgeRoutePreview(null);
    edgeRoutePreviewRef.current = null;
    clearDragPreview();
  }, [activeProjectionId, scene?.scene_id, scene?.layout_family, scene?.paper_width, scene?.paper_height, camera?.x, camera?.y, camera?.zoom]);

  useEffect(() => {
    viewBoxRef.current = viewBox;
  }, [viewBox]);

  useLayoutEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const updateSize = () => {
      const bounds = svg.getBoundingClientRect();
      setCanvasSize({ width: Math.max(1, bounds.width), height: Math.max(1, bounds.height) });
    };
    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(svg);
    return () => observer.disconnect();
  }, [scene?.scene_id, Boolean(viewBox)]);

  useLayoutEffect(() => {
    if (!scene || !svgRef.current) return;
    const previous = previousScene.current;
    previousScene.current = scene;
    if (!previous || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const oldNodes = new Map(previous.nodes.map((node) => [node.scene_node_id, node]));
    for (const node of scene.nodes) {
      const element = svgRef.current.querySelector<SVGGElement>(`[data-scene-node-id="${node.scene_node_id}"]`);
      if (!element) continue;
      const old = oldNodes.get(node.scene_node_id);
      const origin = old ?? (node.parent_scene_node_id ? oldNodes.get(node.parent_scene_node_id) : undefined);
      const oldCenter = origin
        ? { x: origin.bounds.x + origin.bounds.width / 2, y: origin.bounds.y + origin.bounds.height / 2 }
        : { x: node.bounds.x + node.bounds.width / 2, y: node.bounds.y + node.bounds.height / 2 };
      const nextCenter = { x: node.bounds.x + node.bounds.width / 2, y: node.bounds.y + node.bounds.height / 2 };
      const scaleX = old ? Math.max(0.2, old.bounds.width / node.bounds.width) : 0.72;
      const scaleY = old ? Math.max(0.2, old.bounds.height / node.bounds.height) : 0.72;
      element.animate(
        [
          {
            opacity: old ? 0.72 : 0,
            transform: `translate(${oldCenter.x - nextCenter.x}px, ${oldCenter.y - nextCenter.y}px) scale(${scaleX}, ${scaleY})`,
          },
          { opacity: 1, transform: "translate(0, 0) scale(1, 1)" },
        ],
        { duration: 380, easing: "cubic-bezier(.22,.8,.24,1)", fill: "both" },
      );
    }
    for (const edge of scene.edges) {
      const element = svgRef.current.querySelector<SVGGElement>(`[data-scene-edge-id="${edge.scene_edge_id}"]`);
      if (!element) continue;
      element.animate(
        [{ opacity: previous.edges.some((item) => item.scene_edge_id === edge.scene_edge_id) ? 0.35 : 0 }, { opacity: 1 }],
        { duration: 300, delay: 70, easing: "ease-out", fill: "both" },
      );
    }
  }, [scene?.scene_id, scene?.layout_family]);

  useEffect(() => {
    setDark(data?.view_state.theme === "studio-dark");
  }, [data?.view_state.theme]);

  useEffect(() => {
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetch(`/api/search?q=${encodeURIComponent(query)}`, { signal: controller.signal, cache: "no-store" })
        .then((response) => response.ok ? response.json() : Promise.reject())
        .then((payload: { results: SearchResult[] }) => setSearchResults(payload.results))
        .catch(() => undefined);
    }, 120);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [query, data?.document.source_digest]);

  const selected = selectedIds.at(-1) ?? null;
  const selectedNode = scene?.nodes.find((node) => node.scene_node_id === selected) ?? null;
  const selectedEdge = scene?.edges.find((edge) => edge.scene_edge_id === selectedEdgeId) ?? null;
  const selectedViewNode = view?.nodes.find(
    (node) => node.view_node_id === selectedNode?.view_node_id,
  );
  const selectedCanonicalIds = useMemo(() => {
    if (!data || !selectedViewNode) return [];
    if (selectedViewNode.canonical_node_ids.length) return selectedViewNode.canonical_node_ids;
    const hierarchyId = String(selectedViewNode.attributes.hierarchy_node_id ?? "");
    if (!hierarchyId) return [];
    const children = new Map<string, HierarchyNode[]>();
    for (const item of data.hierarchy.nodes) {
      if (!item.parent_hierarchy_node_id) continue;
      children.set(item.parent_hierarchy_node_id, [
        ...(children.get(item.parent_hierarchy_node_id) ?? []),
        item,
      ]);
    }
    const ids: string[] = [];
    const visit = (nodeId: string) => {
      const item = data.hierarchy.nodes.find((candidate) => candidate.hierarchy_node_id === nodeId);
      if (!item) return;
      ids.push(...item.canonical_node_ids);
      for (const child of children.get(nodeId) ?? []) visit(child.hierarchy_node_id);
    };
    visit(hierarchyId);
    return [...new Set(ids)];
  }, [data?.hierarchy, selectedViewNode]);
  const selectedArchitectureNodes = useMemo(() => {
    const ids = new Set(selectedCanonicalIds);
    return data?.architecture.nodes.filter((node) => ids.has(node.node_id)) ?? [];
  }, [data?.architecture.nodes, selectedCanonicalIds]);
  const selectedEvidence = useMemo(() => {
    const staticIds = selectedCanonicalIds.flatMap(
      (nodeId) => data?.architecture.nodes.find((node) => node.node_id === nodeId)?.evidence_ids ?? [],
    );
    const runtimeIds = selectedCanonicalIds.flatMap(
      (nodeId) => data?.runtime?.node_evidence[nodeId] ?? [],
    );
    const ids = new Set([...(selectedNode?.evidence_ids ?? []), ...staticIds, ...runtimeIds]);
    return data?.evidence.filter((record) => ids.has(record.evidence_id)) ?? [];
  }, [data?.architecture.nodes, data?.evidence, data?.runtime, selectedCanonicalIds, selectedNode]);
  const draftPortOptions = [
    ...(data?.architecture.nodes.flatMap((node) => [
      ...node.input_ports.map((port) => ({
        ...port,
        node_id: node.node_id,
        node_label: node.semantic_name,
        draft: false,
      })),
      ...node.output_ports.map((port) => ({
        ...port,
        node_id: node.node_id,
        node_label: node.semantic_name,
        draft: false,
      })),
    ]) ?? []),
    ...(data?.draft.nodes.flatMap((node) => node.ports.map((port) => ({
      ...port,
      node_id: node.node_id,
      node_label: node.semantic_name,
      draft: true,
    }))) ?? []),
  ];
  const draftSourcePorts = draftPortOptions.filter((port) => port.direction === "output");
  const draftTargetPorts = draftPortOptions.filter((port) => port.direction === "input");
  const draftPortLabels = new Map(
    draftPortOptions.map((port) => [
      port.port_id,
      `${port.node_label} · ${port.name}${port.draft ? ` · ${tx("draft", "草稿")}` : ""}`,
    ]),
  );
  const canonicalDeleteIntents = data?.draft.intents.filter(
    (intent) => intent.kind === "delete-node",
  ) ?? [];

  async function mutate(
    endpoint: string,
    payload?: object,
    activityLabel?: string,
  ): Promise<StudioState | null> {
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(data?.session_nonce ? { "X-ArchCanvas-Nonce": data.session_nonce } : {}),
        },
        body: JSON.stringify(payload ?? {}),
      });
      if (!response.ok) throw new Error(await response.text());
      const state = (await response.json()) as StudioState;
      setData(state);
      setLayoutCandidates([]);
      setLayoutPreviewId(null);
      const visualPatch = payload as VisualPatch | undefined;
      const label = activityLabel ?? (visualPatch?.operation ? `${visualPatch.operation} · ${visualPatch.target_id ?? "document"}` : endpoint.slice(5));
      setActivity((items) => [label, ...items].slice(0, 20));
      return state;
    } catch (error) {
      setActivity((items) => [`${tx("Request failed", "请求失败")} · ${String(error)}`, ...items].slice(0, 20));
      return null;
    }
  }

  async function refreshState(): Promise<StudioState | null> {
    return jobController.current?.refreshState() ?? null;
  }

  function pollJob(jobId: string, onSuccess?: () => void) {
    jobController.current?.start(jobId, (job) => {
      if (job.state === "succeeded") onSuccess?.();
    });
  }

  async function cancelJob(jobId: string) {
    try {
      await jobController.current?.cancel(jobId, data?.session_nonce);
      setActivity((items) => [`${tx("Cancellation requested", "已请求取消")} · ${jobId}`, ...items].slice(0, 20));
    } catch (error) {
      setActivity((items) => [`${tx("Cancellation failed", "取消失败")} · ${String(error)}`, ...items].slice(0, 20));
    }
  }

  async function commitSourceTransaction() {
    try {
      const response = await fetch("/api/transaction/commit", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(data?.session_nonce ? { "X-ArchCanvas-Nonce": data.session_nonce } : {}),
        },
        body: "{}",
      });
      if (!response.ok) throw new Error(await response.text());
      const state = await response.json() as StudioState & { reanalysis_job_id?: string | null };
      setData(state);
      setActivity((items) => [tx("Committed source transaction", "已提交源码事务"), ...items].slice(0, 20));
      if (state.reanalysis_job_id) {
        setBottomTab("jobs");
        pollJob(state.reanalysis_job_id, () => {
          setActivity((items) => [tx("Reanalysis completed on the committed source", "已基于提交后的源码完成重新分析"), ...items].slice(0, 20));
          setBottomTab("problems");
        });
      }
    } catch (error) {
      setActivity((items) => [`${tx("Source commit failed", "源码提交失败")} · ${String(error)}`, ...items].slice(0, 20));
    }
  }

  async function requestLayoutCandidates() {
    setLayoutLoading(true);
    try {
      const response = await fetch("/api/layout-candidates", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(data?.session_nonce ? { "X-ArchCanvas-Nonce": data.session_nonce } : {}),
        },
        body: "{}",
      });
      if (!response.ok) throw new Error(await response.text());
      const payload = await response.json() as { candidates: LayoutCandidate[] };
      setLayoutCandidates(payload.candidates);
      setLayoutPreviewId(payload.candidates[0]?.candidate_id ?? null);
      setActivity((items) => [
        payload.candidates.length
          ? tx(`${payload.candidates.length} valid layout candidates`, `${payload.candidates.length} 个有效布局候选`)
          : tx("No valid layout candidate; document unchanged", "没有合格布局候选，文档未修改"),
        ...items,
      ].slice(0, 20));
    } catch (error) {
      setActivity((items) => [`${tx("Layout candidate generation failed", "布局候选生成失败")} · ${String(error)}`, ...items].slice(0, 20));
    } finally {
      setLayoutLoading(false);
    }
  }

  async function applyLayoutCandidate() {
    if (!layoutPreviewId) return;
    await mutate(
      `/api/layout-candidates/${layoutPreviewId}/apply`,
      {},
      tx("Applied layout candidate", "已应用布局候选"),
    );
  }

  function persistNavigation(
    nextProjection: Projection,
    nextExpansions: Record<Projection, Set<string>>,
    activityLabel: string,
  ) {
    if (navigationTimer.current !== null) window.clearTimeout(navigationTimer.current);
    setLayoutCandidates([]);
    setLayoutPreviewId(null);
    const payload = {
      projection: nextProjection,
      expansions: {
        module: [...nextExpansions.module].sort(),
        source: [...nextExpansions.source].sort(),
      },
    };
    navigationTimer.current = window.setTimeout(() => {
      navigationTimer.current = null;
      navigationQueue.current = navigationQueue.current
        .then(async () => {
          const response = await fetch("/api/navigation", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(data?.session_nonce ? { "X-ArchCanvas-Nonce": data.session_nonce } : {}),
            },
            body: JSON.stringify(payload),
          });
          if (!response.ok) throw new Error(await response.text());
          const state = (await response.json()) as StudioState;
          acceptStudioState(state);
          setActivity((items) => [activityLabel, ...items].slice(0, 20));
        })
        .catch((error) => {
          setActivity((items) => [`${tx("Navigation persistence failed", "导航状态保存失败")} · ${String(error)}`, ...items].slice(0, 20));
        });
    }, 160);
  }

  async function submit(operation: string, targetId: string | undefined, value: Record<string, unknown>, sceneId = scene?.scene_id) {
    if (!sceneId) return;
    await mutate("/api/patch", {
      patch_id: patchId(operation),
      operation,
      target_id: targetId,
      value: { ...value, scene_id: sceneId },
    });
  }

  async function submitBatch(description: string, patches: Array<{ operation: string; targetId?: string; value: Record<string, unknown> }>) {
    if (!scene) return;
    const batchId = patchId("visual-batch").replace("patch:", "batch:");
    await mutate("/api/patch-batch", {
      batch_id: batchId,
      description,
      patches: patches.map((patch, index) => ({
        patch_id: `${batchId.replace("batch:", "patch:")}.${index}`,
        operation: patch.operation,
        target_id: patch.targetId,
        value: { ...patch.value, scene_id: scene.scene_id },
      })),
    }, description);
  }

  async function prepareParameter(parameterName: string, newValue: unknown) {
    if (!architectureNode) return;
    await mutate(
      "/api/transaction/prepare",
      {
        patch_id: patchId("set-parameter"),
        target_node_id: architectureNode.node_id,
        parameter_name: parameterName,
        new_value: newValue,
      },
      `${tx("Prepared", "已准备")} ${architectureNode.node_id}.${parameterName}`,
    );
    setBottomTab("diff");
  }

  async function prepareStructural(operation: string, parameters: Record<string, unknown>) {
    if (!architectureNode) return;
    await mutate(
      "/api/transaction/prepare-structural",
      {
        patch_id: patchId(operation.replaceAll("_", "-")),
        operation,
        target_node_id: architectureNode.node_id,
        parameters,
      },
      `${tx("Prepared", "已准备")} ${operation} ${tx("on", "作用于")} ${architectureNode.node_id}`,
    );
    setBottomTab("diff");
  }

  async function proposeConnection(sourcePortId: string, targetNodeId: string, targetPortId: string) {
    if (!architectureNode) return;
    await mutate(
      "/api/proposal/connection",
      {
        proposal_id: patchId("connection").replace("patch:", "proposal:"),
        source_node_id: architectureNode.node_id,
        source_port_id: sourcePortId,
        target_node_id: targetNodeId,
        target_port_id: targetPortId,
        role: "main",
      },
      `${tx("Proposed", "已提议")} ${architectureNode.node_id} → ${targetNodeId}`,
    );
  }

  function persistCamera(next: [number, number, number, number], currentScene: Scene) {
    if (cameraTimer.current !== null) window.clearTimeout(cameraTimer.current);
    cameraTimer.current = window.setTimeout(() => {
      cameraTimer.current = null;
      void submit("set-camera", undefined, {
        x: next[0],
        y: next[1],
        zoom: currentScene.paper_width / next[2],
      }, currentScene.scene_id);
    }, 180);
  }

  function selectSearchResult(result = searchResults[0]) {
    if (!result) return;
    setSelectedEdgeId(null);
    const binding = result.view_bindings.find(
      (item) => item.projection_id === activeProjectionId,
    );
    if (binding) {
      selections.current[binding.projection_id] = [binding.scene_node_id];
      setSelectedIds([binding.scene_node_id]);
      setFocusedCanonicalId(
        result.canonical_ids.includes(result.id) ? result.id : result.canonical_ids[0] ?? null,
      );
    } else {
      chooseCanonical(result.canonical_ids);
    }
    setSearchResults([]);
  }

  function chooseCanonical(canonicalIds: string[], navigationRowId?: string) {
    const target = canonicalIds.find((canonicalId) =>
      scene?.nodes.some((node) => node.canonical_node_ids.includes(canonicalId)),
    );
    if (target) {
      const sceneNode = scene?.nodes.find((node) => node.canonical_node_ids.includes(target));
      if (sceneNode) choose(sceneNode.scene_node_id, false, navigationRowId, target);
    } else if (navigationRowId) {
      choose(null, false, navigationRowId);
    }
  }

  function switchProjection(next: Projection) {
    navigationTouched.current = true;
    setFocusedNavigationRowId(null);
    setFocusedCanonicalId(null);
    setProjection(next);
    persistNavigation(next, expansionsRef.current, tx(
      `${next === "module" ? "Module" : "Source"} relations view`,
      `${next === "module" ? "模块" : "源码"}关系视图`,
    ));
  }

  function toggleNavigationRow(rowId: string) {
    setNavigationRowExpanded(projection, rowId);
  }

  function setNavigationRowExpanded(kind: Projection, rowId: string, force?: boolean) {
    navigationTouched.current = true;
    const next = new Set(expansionsRef.current[kind]);
    const shouldExpand = force ?? !next.has(rowId);
    if (shouldExpand) next.add(rowId); else next.delete(rowId);
    pendingHierarchyFocus.current = shouldExpand && kind === "module" ? rowId : null;
    const nextExpansions = { ...expansionsRef.current, [kind]: next };
    expansionsRef.current = nextExpansions;
    setExpansions(nextExpansions);
    persistNavigation(kind, nextExpansions, tx(
      `Navigation ${shouldExpand ? "expanded" : "collapsed"}`,
      `导航${shouldExpand ? "已展开" : "已折叠"}`,
    ));
  }

  function activateNavigationRow(item: NavigationNode) {
    const hierarchyViewNode = view?.nodes.find(
      (node) => node.attributes.hierarchy_node_id === item.id,
    );
    const hierarchySceneNode = hierarchyViewNode
      ? scene?.nodes.find((node) => node.view_node_id === hierarchyViewNode.view_node_id)
      : undefined;
    if (hierarchySceneNode) choose(
      hierarchySceneNode.scene_node_id,
      false,
      item.id,
      item.canonical_ids.length === 1 ? item.canonical_ids[0] : null,
    );
    else if (item.canonical_ids.length) chooseCanonical(item.canonical_ids, item.id);
    else choose(null, false, item.id);
    if (item.child_count > 0 && !expansionsRef.current[projection].has(item.id)) {
      setNavigationRowExpanded(projection, item.id, true);
    }
  }

  function choose(
    nodeId: string | null,
    additive = false,
    navigationRowId?: string | null,
    preferredCanonicalId: string | null = null,
  ) {
    setSelectedEdgeId(null);
    setFocusedCanonicalId(preferredCanonicalId);
    const next = !nodeId
      ? []
      : additive
        ? selectedIds.includes(nodeId)
          ? selectedIds.filter((item) => item !== nodeId)
          : [...selectedIds, nodeId]
        : [nodeId];
    if (activeProjectionId) selections.current[activeProjectionId] = next;
    setSelectedIds(next);
    if (navigationRowId !== undefined) {
      setFocusedNavigationRowId(navigationRowId);
    } else if (!additive) {
      const targetNode = scene?.nodes.find((item) => item.scene_node_id === nodeId);
      const candidates = targetNode
        ? visibleNavigation
          .filter((item) => item.canonical_ids.some((id) => targetNode.canonical_node_ids.includes(id)))
          .sort((left, right) => {
            if (left.reference !== right.reference) return Number(left.reference) - Number(right.reference);
            if (left.canonical_ids.length !== right.canonical_ids.length) return left.canonical_ids.length - right.canonical_ids.length;
            if (left.depth !== right.depth) return right.depth - left.depth;
            return left.id.localeCompare(right.id);
          })
        : [];
      setFocusedNavigationRowId(candidates[0]?.id ?? null);
    }
  }

  function collectDragDomPreview(movingIds: readonly string[]) {
    const svg = svgRef.current;
    if (!svg || !scene) return null;
    const moving = new Set(movingIds);
    const nodeElements = new Map<string, SVGGElement>();
    for (const element of svg.querySelectorAll<SVGGElement>("[data-scene-node-id]")) {
      const nodeId = element.dataset.sceneNodeId;
      if (nodeId && moving.has(nodeId)) nodeElements.set(nodeId, element);
    }
    const edgeElements = new Map<string, SVGGElement[]>();
    for (const element of svg.querySelectorAll<SVGGElement>("[data-scene-edge-id]")) {
      const edgeId = element.dataset.sceneEdgeId;
      if (!edgeId) continue;
      const matches = edgeElements.get(edgeId);
      if (matches) matches.push(element);
      else edgeElements.set(edgeId, [element]);
    }
    const affectedEdges = scene.edges
      .map((edge, index) => ({ edge, index }))
      .filter(({ edge }) => moving.has(edge.source_scene_node_id) || moving.has(edge.target_scene_node_id));
    return { nodeElements, edgeElements, affectedEdges };
  }

  function applyDragPreview(next: Record<string, Point>) {
    dragPreview.current = next;
    const dom = dragDomPreview.current;
    if (!dom || !sceneRenderIndex) return;
    for (const [nodeId, position] of Object.entries(next)) {
      const node = sceneRenderIndex.byId.get(nodeId);
      const element = dom.nodeElements.get(nodeId);
      if (!node || !element) continue;
      element.style.transform = `translate(${position.x - node.bounds.x}px, ${position.y - node.bounds.y}px)`;
    }
    for (const { edge, index } of dom.affectedEdges) {
      const points = previewEdgePoints(edge, sceneRenderIndex.byId, next, index);
      for (const element of dom.edgeElements.get(edge.scene_edge_id) ?? []) {
        updatePreviewEdgeElement(element, edge, points);
      }
    }
  }

  function scheduleDragPreview(next: Record<string, Point>) {
    pendingDragPreview.current = next;
    dragPreview.current = next;
    if (dragPreviewFrame.current !== null) return;
    dragPreviewFrame.current = requestAnimationFrame(() => {
      dragPreviewFrame.current = null;
      const pending = pendingDragPreview.current;
      pendingDragPreview.current = null;
      if (pending) applyDragPreview(pending);
    });
  }

  function clearDragPreview() {
    if (dragPreviewFrame.current !== null) cancelAnimationFrame(dragPreviewFrame.current);
    dragPreviewFrame.current = null;
    pendingDragPreview.current = null;
    const dom = dragDomPreview.current;
    if (dom) {
      for (const element of dom.nodeElements.values()) element.style.removeProperty("transform");
      for (const { edge } of dom.affectedEdges) {
        for (const element of dom.edgeElements.get(edge.scene_edge_id) ?? []) {
          updatePreviewEdgeElement(element, edge, edge.points);
        }
      }
    }
    dragPreview.current = {};
    dragDomPreview.current = null;
  }

  function scheduleEdgeRoutePreview(next: Point[]) {
    edgeRoutePreviewRef.current = next;
    if (edgePreviewFrame.current !== null) return;
    edgePreviewFrame.current = requestAnimationFrame(() => {
      edgePreviewFrame.current = null;
      setEdgeRoutePreview(edgeRoutePreviewRef.current);
    });
  }

  function chooseEdge(edgeId: string) {
    const next = selectedEdgeId === edgeId ? null : edgeId;
    setSelectedEdgeId(next);
    setFocusedCanonicalId(null);
    setEdgeEndpointDrag(null);
    setEdgeRoutePreview(null);
    if (!next) return;
    if (activeProjectionId) selections.current[activeProjectionId] = [];
    setSelectedIds([]);
    setFocusedNavigationRowId(null);
  }

  function chooseEdgeAtClient(clientX: number, clientY: number, fallbackEdgeId: string) {
    const point = scenePointFromClient(clientX, clientY);
    if (!scene || !sceneRenderIndex || !point) {
      chooseEdge(fallbackEdgeId);
      return;
    }
    const nearest = scene.edges
      .map((edge, index) => ({
        edge,
        distance: distanceToPolyline(point, previewEdgePoints(edge, sceneRenderIndex.byId, dragPreview.current, index)),
      }))
      .sort((left, right) => left.distance - right.distance)[0];
    chooseEdge(nearest?.edge.scene_edge_id ?? fallbackEdgeId);
  }

  function zoom(factor: number) {
    const current = viewBoxRef.current ?? viewBox;
    if (!current || !scene) return;
    const [x, y, width, height] = current;
    const nextWidth = width * factor;
    const nextHeight = height * factor;
    const next: [number, number, number, number] = [
      x + (width - nextWidth) / 2,
      y + (height - nextHeight) / 2,
      nextWidth,
      nextHeight,
    ];
    commitViewBox(next);
    persistCamera(next, scene);
  }

  function scenePointFromClient(clientX: number, clientY: number): Point | null {
    const svg = svgRef.current;
    if (!svg) return null;
    const matrix = svg.getScreenCTM();
    if (!matrix) return null;
    const point = svg.createSVGPoint();
    point.x = clientX;
    point.y = clientY;
    const transformed = point.matrixTransform(matrix.inverse());
    return { x: transformed.x, y: transformed.y };
  }

  function pointerPosition(event: React.PointerEvent): Point | null {
    return scenePointFromClient(event.clientX, event.clientY);
  }

  function beginDrag(event: React.PointerEvent, node: SceneNode) {
    if (!node.parent_scene_node_id) return;
    choose(node.scene_node_id, event.shiftKey);
    if (event.shiftKey) return;
    if (mode === "explore" || pinned.has(node.scene_node_id)) return;
    const point = pointerPosition(event);
    if (!point) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const selectedRoots = selectedIds.includes(node.scene_node_id) ? selectedIds : [node.scene_node_id];
    const movingRoots = selectedRoots.filter((nodeId) => !pinned.has(nodeId));
    const movingIds = scene ? sceneDescendantIds(scene, movingRoots) : movingRoots;
    const baselines = Object.fromEntries(
      movingIds
        .map((nodeId) => {
          const current = scene?.nodes.find((item) => item.scene_node_id === nodeId);
          return [nodeId, current?.bounds ?? node.bounds];
        }),
    );
    dragDomPreview.current = collectDragDomPreview(movingIds);
    dragPreview.current = {};
    setDrag({ startClient: point, baselines, rootIds: movingRoots });
  }

  function beginEdgeEndpointDrag(
    event: React.PointerEvent<SVGCircleElement>,
    endpoint: "source" | "target",
  ) {
    if (mode !== "layout" || !selectedEdge || !scene) return;
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    const index = scene.edges.indexOf(selectedEdge);
    if (!sceneRenderIndex) return;
    const points = previewEdgePoints(selectedEdge, sceneRenderIndex.byId, dragPreview.current, index);
    edgeRoutePreviewRef.current = points;
    setEdgeRoutePreview(points);
    setEdgeEndpointDrag({ edgeId: selectedEdge.scene_edge_id, endpoint, points });
  }

  function moveEdgeEndpoint(event: React.PointerEvent) {
    if (!edgeEndpointDrag || !edgeRoutePreviewRef.current || !scene) return;
    const point = pointerPosition(event);
    const edge = scene.edges.find((item) => item.scene_edge_id === edgeEndpointDrag.edgeId);
    if (!point || !edge) return;
    const nodeId = edgeEndpointDrag.endpoint === "source"
      ? edge.source_scene_node_id
      : edge.target_scene_node_id;
    const node = scene.nodes.find((item) => item.scene_node_id === nodeId);
    if (!node) return;
    scheduleEdgeRoutePreview(moveRouteEndpoint(
      edgeEndpointDrag.points,
      edgeEndpointDrag.endpoint,
      node.bounds,
      point,
      edge,
      scene,
      routeStrategy,
    ));
  }

  function moveDrag(event: React.PointerEvent) {
    if (!drag || !scene) return;
    const point = pointerPosition(event);
    if (!point) return;
    const delta = constrainDragDelta(
      scene.nodes,
      Object.keys(drag.baselines),
      {
        x: point.x - drag.startClient.x,
        y: point.y - drag.startClient.y,
      },
    );
    scheduleDragPreview(Object.fromEntries(Object.entries(drag.baselines).map(([nodeId, bounds]) => [
      nodeId,
      {
        x: bounds.x + delta.x,
        y: bounds.y + delta.y,
      },
    ])));
  }

  function beginPan(event: React.PointerEvent<SVGSVGElement>) {
    if ((event.target as Element).closest(".scene-edge")) return;
    const currentViewBox = viewBoxRef.current ?? viewBox;
    if ((event.target as Element).closest(".scene-node:not(.root)") || !currentViewBox) return;
    setSelectedEdgeId(null);
    event.currentTarget.setPointerCapture(event.pointerId);
    if (event.shiftKey) {
      const point = pointerPosition(event);
      if (point) setMarquee({ start: point, current: point });
      return;
    }
    setPan({
      startClient: { x: event.clientX, y: event.clientY },
      startViewBox: currentViewBox,
    });
  }

  function movePointer(event: React.PointerEvent<SVGSVGElement>) {
    if (edgeEndpointDrag) {
      moveEdgeEndpoint(event);
      return;
    }
    if (drag) {
      moveDrag(event);
      return;
    }
    if (marquee) {
      const point = pointerPosition(event);
      if (point) setMarquee({ ...marquee, current: point });
      return;
    }
    if (!pan || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const scaleX = pan.startViewBox[2] / rect.width;
    const scaleY = pan.startViewBox[3] / rect.height;
    writeViewBox([
      pan.startViewBox[0] - (event.clientX - pan.startClient.x) * scaleX,
      pan.startViewBox[1] - (event.clientY - pan.startClient.y) * scaleY,
      pan.startViewBox[2],
      pan.startViewBox[3],
    ]);
  }

  function endDrag() {
    if (!drag) return;
    const patches = Object.entries(dragPreview.current).map(([nodeId, position], index) => ({
      patch_id: `${patchId("move-batch")}.${index}`,
      operation: "set-position",
      target_id: nodeId,
      value: { scene_id: scene?.scene_id, x: position.x, y: position.y },
    }));
    if (patches.length) void mutate("/api/patch-batch", {
      batch_id: patchId("drag").replace("patch:", "batch:"),
      description: drag.rootIds.length === 1 && patches.length > 1
        ? tx(`Move container with ${patches.length - 1} descendant${patches.length === 2 ? "" : "s"}`, `移动容器及 ${patches.length - 1} 个后代节点`)
        : tx(`Move ${patches.length} node${patches.length === 1 ? "" : "s"}`, `移动 ${patches.length} 个节点`),
      patches,
    });
    clearDragPreview();
    setDrag(null);
  }

  function endPointer() {
    if (edgeEndpointDrag && edgeRoutePreviewRef.current) {
      const dragState = edgeEndpointDrag;
      const route = edgeRoutePreviewRef.current;
      if (edgePreviewFrame.current !== null) cancelAnimationFrame(edgePreviewFrame.current);
      edgePreviewFrame.current = null;
      setEdgeEndpointDrag(null);
      void submit("set-route-hint", dragState.edgeId, { points: route })
        .finally(() => {
          edgeRoutePreviewRef.current = null;
          setEdgeRoutePreview(null);
        });
      return;
    }
    if (marquee && scene) {
      const enclosed = nodesInSelection(
        scene.nodes,
        selectionBounds(marquee.start, marquee.current),
      );
      const next = [...new Set([...selectedIds, ...enclosed])];
      if (activeProjectionId) selections.current[activeProjectionId] = next;
      setSelectedIds(next);
      setFocusedCanonicalId(null);
      setFocusedNavigationRowId(null);
      setMarquee(null);
      return;
    }
    if (drag) endDrag();
    const finalViewBox = viewBoxRef.current;
    if (pan && finalViewBox && scene) {
      setViewBox(finalViewBox);
      void submit("set-camera", undefined, {
        x: finalViewBox[0],
        y: finalViewBox[1],
        zoom: scene.paper_width / finalViewBox[2],
      });
    }
    setPan(null);
  }

  function cancelPointer() {
    clearDragPreview();
    if (edgePreviewFrame.current !== null) cancelAnimationFrame(edgePreviewFrame.current);
    edgePreviewFrame.current = null;
    edgeRoutePreviewRef.current = null;
    setDrag(null);
    setEdgeEndpointDrag(null);
    setEdgeRoutePreview(null);
    setPan(null);
    setMarquee(null);
  }

  function align(command: string) {
    if (selectedIds.length < 2) return;
    void mutate("/api/align", {
      batch_id: patchId(`align-${command}`).replace("patch:", "batch:"),
      selected_ids: selectedIds,
      command,
    }, `${tx("Aligned", "已对齐")} ${selectedIds.length} ${tx("nodes", "个节点")} · ${command}`);
  }

  async function createDraftNode() {
    const semanticName = draftName.trim();
    const nodeType = draftType.trim();
    if (!semanticName || !nodeType) return;
    const nodeId = patchId("draft-node").replace("patch:", "draft:");
    const state = await mutate(
      "/api/proposal/node",
      {
        node: {
          node_id: nodeId,
          semantic_name: semanticName,
          framework: data?.project.framework ?? "pytorch",
          node_type: nodeType,
          parent_id: selectedCanonicalIds[0] ?? null,
          parameters: {},
          ports: [
            {
              port_id: `${nodeId}.input`,
              name: "input",
              direction: "input",
              role: "main",
            },
            {
              port_id: `${nodeId}.output`,
              name: "output",
              direction: "output",
              role: "main",
            },
          ],
        },
      },
      `${tx("Created draft", "已创建草稿")} · ${semanticName}`,
    );
    if (state) {
      setDraftDialog(false);
      setDraftName("");
      setDraftType("");
      setBottomTab("problems");
    }
  }

  async function deleteDraftNode(nodeId: string) {
    await mutate(
      "/api/draft/node/delete",
      { node_id: nodeId },
      `${tx("Deleted draft", "已删除草稿")} · ${nodeId}`,
    );
  }

  function openDraftEdgeDialog() {
    setDraftEdgeSource((current) => current || draftSourcePorts[0]?.port_id || "");
    setDraftEdgeTarget((current) => current || draftTargetPorts[0]?.port_id || "");
    setDraftEdgeDialog(true);
  }

  async function createDraftEdge() {
    if (!draftEdgeSource || !draftEdgeTarget) return;
    const edgeId = patchId("draft-edge").replace("patch:", "draft:");
    const state = await mutate(
      "/api/proposal/draft-edge",
      {
        edge: {
          edge_id: edgeId,
          source_port_id: draftEdgeSource,
          target_port_id: draftEdgeTarget,
          policy: draftEdgePolicy,
          parameters: {},
        },
      },
      `${tx("Created draft connection", "已创建草稿连接")} · ${draftEdgePolicy}`,
    );
    if (state) {
      setDraftEdgeDialog(false);
      setBottomTab("problems");
    }
  }

  async function deleteDraftEdge(edgeId: string) {
    await mutate(
      "/api/draft/edge/delete",
      { edge_id: edgeId },
      `${tx("Deleted draft connection", "已删除草稿连接")} · ${edgeId}`,
    );
  }

  async function reviewCanonicalDelete(nodeId: string) {
    setDeleteImpactLoading(true);
    try {
      const response = await fetch("/api/proposal/delete-node/preview", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(data?.session_nonce ? { "X-ArchCanvas-Nonce": data.session_nonce } : {}),
        },
        body: JSON.stringify({ node_id: nodeId }),
      });
      if (!response.ok) throw new Error(await response.text());
      const result = await response.json() as { impact: CanonicalDeleteImpact };
      setDeleteImpact(result.impact);
    } catch (error) {
      setActivity((items) => [`${tx("Impact preview failed", "影响预览失败")} · ${String(error)}`, ...items].slice(0, 20));
    } finally {
      setDeleteImpactLoading(false);
    }
  }

  async function createCanonicalDeleteIntent() {
    if (!deleteImpact) return;
    const state = await mutate(
      "/api/proposal/delete-node",
      {
        node_id: deleteImpact.node_id,
        input_fingerprint: deleteImpact.input_fingerprint,
        intent_id: patchId("delete-node").replace("patch:", "intent:"),
      },
      `${tx("Created delete intent", "已创建删除意图")} · ${deleteImpact.semantic_name}`,
    );
    if (state) {
      setDeleteImpact(null);
      setBottomTab("problems");
    }
  }

  async function discardCanonicalDeleteIntent(intentId: string) {
    await mutate(
      "/api/draft/delete-intent/discard",
      { intent_id: intentId },
      `${tx("Discarded delete intent", "已丢弃删除意图")} · ${intentId}`,
    );
  }

  async function runValidation() {
    try {
      const response = await fetch("/api/validation-runs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(data?.session_nonce ? { "X-ArchCanvas-Nonce": data.session_nonce } : {}),
        },
        body: JSON.stringify({
          profile: validationProfile,
          runtime_execution_authorized: false,
        }),
      });
      if (!response.ok) throw new Error(await response.text());
      const job = await response.json() as { job_id: string };
      setBottomTab("jobs");
      pollJob(job.job_id, () => setBottomTab("validation"));
      await refreshState();
    } catch (error) {
      setActivity((items) => [`${tx("Validation start failed", "验证启动失败")} · ${String(error)}`, ...items].slice(0, 20));
    }
  }

  async function openProject() {
    if (!projectRoot.trim()) return;
    setProjectScanning(true);
    setProjectError("");
    setPendingProject(null);
    try {
      const response = await fetch("/api/projects/open", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(data?.session_nonce ? { "X-ArchCanvas-Nonce": data.session_nonce } : {}) },
        body: JSON.stringify({ root: projectRoot.trim(), environment_path: condaEnvironment || null }),
      });
      if (!response.ok) throw new Error(await response.text());
      const result = await response.json() as PendingProject;
      setPendingProject(result);
      const roots = result.discovery.entrypoints.filter((item) => item.depth === 0);
      setProjectModelExpansions(new Set(roots.filter((item) => item.child_count > 0).map((item) => item.entrypoint)));
      const selection = initialProjectSelection(result.discovery.entrypoints);
      setProjectEntrypoint(selection.entrypoint);
      setProjectFramework(selection.framework);
      setProjectConfig(selection.configPath);
    } catch (error) {
      setProjectError(String(error));
      setActivity((items) => [`${tx("Project discovery failed", "项目发现失败")} · ${String(error)}`, ...items].slice(0, 20));
    } finally {
      setProjectScanning(false);
    }
  }

  async function browseFolders(path?: string) {
    setFolderLoading(true);
    try {
      const target = path ?? (projectRoot.trim() || "/home");
      const response = await fetch(`/api/directories?path=${encodeURIComponent(target)}`, { cache: "no-store" });
      if (!response.ok) throw new Error(await response.text());
      setFolderPicker(await response.json() as DirectoryBrowserState);
      setSelectedFolderPath(null);
    } catch (error) {
      setProjectError(String(error));
    } finally {
      setFolderLoading(false);
    }
  }

  function selectProjectEntrypoint(candidate: ProjectEntrypoint) {
    setProjectEntrypoint(candidate.entrypoint);
    setProjectFramework(candidate.framework === "unknown" ? "auto" : candidate.framework);
    const parent = candidate.path.includes("/") ? candidate.path.slice(0, candidate.path.lastIndexOf("/") + 1) : "";
    const nearestConfig = pendingProject?.discovery.configs.find(
      (item) => candidate.config_paths.includes(item.path) && item.path.startsWith(parent),
    );
    setProjectConfig(nearestConfig?.path ?? "");
  }

  async function analyzeProject() {
    if (!pendingProject || !projectEntrypoint) return;
    try {
      const response = await fetch("/api/analyses", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(data?.session_nonce ? { "X-ArchCanvas-Nonce": data.session_nonce } : {}) },
        body: JSON.stringify({
          project_id: pendingProject.project.project_id,
          project_generation: pendingProject.project.generation,
          entrypoint: projectEntrypoint,
          framework: projectFramework,
          task: "inference",
          config_path: projectConfig || null,
          execution_mode: "static",
          pattern_packs_enabled: true,
          request_id: `request:${Date.now().toString(36)}`,
        }),
      });
      if (!response.ok) throw new Error(await response.text());
      const job = await response.json() as { job_id: string };
      setBottomTab("jobs");
      pollJob(job.job_id, () => {
        setProjectDialog(false);
        setPendingProject(null);
      });
      await refreshState();
    } catch (error) {
      setActivity((items) => [`${tx("Analysis start failed", "分析启动失败")} · ${String(error)}`, ...items].slice(0, 20));
    }
  }

  function fitScene() {
    if (!scene) return;
    if (cameraTimer.current !== null) {
      window.clearTimeout(cameraTimer.current);
      cameraTimer.current = null;
    }
    const next: [number, number, number, number] = [
      0,
      0,
      scene.paper_width,
      scene.paper_height,
    ];
    commitViewBox(next);
    void submit("set-camera", undefined, { x: 0, y: 0, zoom: 1 }, scene.scene_id);
  }

  function focusSelection() {
    if (!scene || !selectedNode || !svgRef.current) return;
    const horizontalPadding = Math.max(90, selectedNode.bounds.width * 0.12);
    const verticalPadding = Math.max(70, selectedNode.bounds.height * 0.18);
    let width = selectedNode.bounds.width + horizontalPadding * 2;
    let height = selectedNode.bounds.height + verticalPadding * 2;
    const viewportRatio = svgRef.current.clientWidth / Math.max(1, svgRef.current.clientHeight);
    if (width / height > viewportRatio) height = width / viewportRatio;
    else width = height * viewportRatio;
    const target: [number, number, number, number] = [
      selectedNode.bounds.x + selectedNode.bounds.width / 2 - width / 2,
      selectedNode.bounds.y + selectedNode.bounds.height / 2 - height / 2,
      width,
      height,
    ];
    const start = viewBoxRef.current ?? target;
    if (viewBoxAnimation.current !== null) cancelAnimationFrame(viewBoxAnimation.current);
    const started = performance.now();
    const animate = (now: number) => {
      const progress = Math.min(1, (now - started) / 320);
      const eased = 1 - Math.pow(1 - progress, 3);
      const next = start.map((value, index) => value + (target[index] - value) * eased) as [number, number, number, number];
      writeViewBox(next);
      if (progress < 1) viewBoxAnimation.current = requestAnimationFrame(animate);
      else {
        viewBoxAnimation.current = null;
        setViewBox(target);
        persistCamera(target, scene);
      }
    };
    viewBoxAnimation.current = requestAnimationFrame(animate);
  }

  function expandInNavigation(node: SceneNode) {
    if (!data || !view) return;
    navigationTouched.current = true;
    const targetProjection: Projection = "module";
    const targetNavigation = data.navigation.projections[targetProjection];
    const viewNode = view.nodes.find((item) => item.view_node_id === node.view_node_id);
    const hierarchyNodeId = String(viewNode?.attributes.hierarchy_node_id ?? "");
    const candidates = targetNavigation.nodes
      .filter((item) => item.child_count > 0 && item.canonical_ids.some((id) => node.canonical_node_ids.includes(id)))
      .sort((left, right) => {
        const exactHierarchy = Number(right.id === hierarchyNodeId) - Number(left.id === hierarchyNodeId);
        if (exactHierarchy) return exactHierarchy;
        if (right.depth !== left.depth) return right.depth - left.depth;
        return left.canonical_ids.length - right.canonical_ids.length;
      });
    const candidate = targetNavigation.nodes.find(
      (item) => item.id === hierarchyNodeId && item.child_count > 0,
    ) ?? candidates[0];
    if (!candidate) return;
    const byId = new Map(targetNavigation.nodes.map((item) => [item.id, item]));
    const next = new Set(expansionsRef.current[targetProjection]);
    let current: NavigationNode | undefined = candidate;
    while (current) {
      if (current.child_count > 0) next.add(current.id);
      current = current.parent_id ? byId.get(current.parent_id) : undefined;
    }
    const nextExpansions = { ...expansionsRef.current, [targetProjection]: next };
    pendingHierarchyFocus.current = candidate.id;
    expansionsRef.current = nextExpansions;
    setExpansions(nextExpansions);
    setProjection(targetProjection);
    setFocusedNavigationRowId(candidate.id);
    persistNavigation(targetProjection, nextExpansions, `${tx("Expanded", "已展开")} ${candidate.label}`);
  }

  function constrainPanelSize(edge: PanelResizeEdge, value: number, sizes = panelSizes): number {
    const horizontalRoom = Math.max(180, window.innerWidth - 360);
    const verticalRoom = Math.max(90, window.innerHeight - 280);
    if (edge === "left") return Math.max(180, Math.min(480, horizontalRoom - sizes.right, value));
    if (edge === "right") return Math.max(240, Math.min(520, horizontalRoom - sizes.left, value));
    if (edge === "top") return Math.max(42, Math.min(96, verticalRoom - sizes.bottom, value));
    return Math.max(92, Math.min(360, verticalRoom - sizes.top, value));
  }

  function beginPanelResize(event: React.PointerEvent<HTMLDivElement>, edge: PanelResizeEdge) {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    setPanelResize({
      edge,
      startClient: { x: event.clientX, y: event.clientY },
      sizes: panelSizes,
    });
  }

  function movePanelResize(event: React.PointerEvent<HTMLDivElement>) {
    if (!panelResize) return;
    const deltaX = event.clientX - panelResize.startClient.x;
    const deltaY = event.clientY - panelResize.startClient.y;
    const delta = panelResize.edge === "left"
      ? deltaX
      : panelResize.edge === "right"
        ? -deltaX
        : panelResize.edge === "top"
          ? deltaY
          : -deltaY;
    const next = panelResize.sizes[panelResize.edge] + delta;
    setPanelSizes({
      ...panelResize.sizes,
      [panelResize.edge]: constrainPanelSize(panelResize.edge, next, panelResize.sizes),
    });
  }

  function resizePanelWithKeyboard(event: React.KeyboardEvent<HTMLDivElement>, edge: PanelResizeEdge) {
    const step = event.shiftKey ? 24 : 8;
    let delta = 0;
    if (edge === "left" && event.key === "ArrowLeft") delta = -step;
    if (edge === "left" && event.key === "ArrowRight") delta = step;
    if (edge === "right" && event.key === "ArrowLeft") delta = step;
    if (edge === "right" && event.key === "ArrowRight") delta = -step;
    if (edge === "top" && event.key === "ArrowUp") delta = -step;
    if (edge === "top" && event.key === "ArrowDown") delta = step;
    if (edge === "bottom" && event.key === "ArrowUp") delta = step;
    if (edge === "bottom" && event.key === "ArrowDown") delta = -step;
    if (!delta && event.key !== "Home") return;
    event.preventDefault();
    setPanelSizes((current) => {
      const next = event.key === "Home" ? DEFAULT_PANEL_SIZES[edge] : current[edge] + delta;
      return { ...current, [edge]: constrainPanelSize(edge, next, current) };
    });
  }

  function resetPanelSize(edge: PanelResizeEdge) {
    setPanelSizes((current) => ({
      ...current,
      [edge]: constrainPanelSize(edge, DEFAULT_PANEL_SIZES[edge], current),
    }));
  }

  const beginDragStable = useStableEvent((event: React.PointerEvent, node: SceneNode) => beginDrag(event, node));
  const expandInNavigationStable = useStableEvent((node: SceneNode) => expandInNavigation(node));
  const chooseEdgeStable = useStableEvent((edgeId: string) => chooseEdge(edgeId));
  const chooseEdgeAtClientStable = useStableEvent((clientX: number, clientY: number, edgeId: string) => {
    chooseEdgeAtClient(clientX, clientY, edgeId);
  });

  if (!data || !scene || !view || !viewBox || !navigation) {
    return <div className="loading">{tx("Loading Studio...", "正在加载 Studio...")}</div>;
  }

  const sourceDigest = data.document.source_digest.slice(0, 12);
  const selectedCanonical = focusedCanonicalId && selectedCanonicalIds.includes(focusedCanonicalId)
    ? focusedCanonicalId
    : selectedCanonicalIds[0];
  const architectureNode = data.architecture.nodes.find((node) => node.node_id === selectedCanonical);
  const localizedProjectionName = projection === "module"
    ? tx("Module relations", "模块关系")
    : tx("Source relations", "源码关系");
  const breadcrumb = selectedViewNode
    ? `${data.architecture.entrypoint.split(":").at(-1)} / ${localizedProjectionName} / ${selectedViewNode.semantic_name}`
    : `${data.architecture.entrypoint.split(":").at(-1)} / ${localizedProjectionName}`;
  const proofs = data.draft.proofs;
  const proofCounts = proofs.reduce<Record<string, number>>((counts, proof) => ({ ...counts, [proof.status]: (counts[proof.status] ?? 0) + 1 }), {});
  const writebackBlocked = data.draft.writeback_summary.eligibility === "blocked" && data.draft.writeback_summary.blocking_intent_ids.length > 0;
  const latestValidation = data.validation_runs.at(-1);
  const screenScale = Math.min(canvasSize.width / viewBox[2], canvasSize.height / viewBox[3]);
  const semanticZoom = screenScale < 0.35 ? "overview" : screenScale < 0.82 ? "standard" : "detail";
  const labelScale = Math.min(2.5, Math.max(1, 0.78 / screenScale));
  const containerLabelScale = Math.min(4, Math.max(1, 0.95 / screenScale));
  const sceneIndex = sceneRenderIndex!;
  function renderSceneNode(node: SceneNode) {
    const isSelected = selectedIds.includes(node.scene_node_id);
    const isEdgeSource = selectedEdge?.source_scene_node_id === node.scene_node_id;
    const isEdgeTarget = selectedEdge?.target_scene_node_id === node.scene_node_id;
    const publicationNode = publicationNodesById.get(node.view_node_id);
    return (
      <SceneNodeGraphic
        key={node.scene_node_id}
        node={node}
        depth={sceneIndex.depths.get(node.scene_node_id) ?? 0}
        isSelected={isSelected}
        isEdgeSource={isEdgeSource}
        isEdgeTarget={isEdgeTarget}
        isCollapsed={collapsed.has(node.scene_node_id)}
        publicationCollapsed={publicationNode?.collapsed ?? false}
        isStructuralContainer={node.shape === "container" && !publicationNode?.collapsed}
        proof={proofBySceneNodeId.get(node.scene_node_id)}
        labelScale={labelScale}
        mode={mode}
        onBeginDrag={beginDragStable}
        onExpand={expandInNavigationStable}
      />
    );
  }

  function renderSceneEdge(edge: SceneEdge, index: number, overlay = false) {
    const points = selectedEdgeId === edge.scene_edge_id && edgeRoutePreview
      ? edgeRoutePreview
      : previewEdgePoints(edge, sceneIndex.byId, EMPTY_POSITION_PREVIEW, index);
    const related = selectedIds.includes(edge.source_scene_node_id) || selectedIds.includes(edge.target_scene_node_id);
    const edgeSelected = selectedEdgeId === edge.scene_edge_id;
    const sourceLabel = sceneIndex.byId.get(edge.source_scene_node_id)?.label_lines.join(" ") ?? edge.source_scene_node_id;
    const targetLabel = sceneIndex.byId.get(edge.target_scene_node_id)?.label_lines.join(" ") ?? edge.target_scene_node_id;
    return (
      <SceneEdgeGraphic
        key={`${edge.scene_edge_id}-${overlay ? "overlay" : "base"}`}
        edge={edge}
        points={points}
        overlay={overlay}
        related={related}
        selected={edgeSelected}
        semanticZoom={semanticZoom}
        layoutFamily={scene!.layout_family}
        sourceLabel={sourceLabel}
        targetLabel={targetLabel}
        toLabel={tx("to", "到")}
        onChooseAtClient={chooseEdgeAtClientStable}
        onChoose={chooseEdgeStable}
      />
    );
  }

  const modeLabels: Record<Mode, string> = {
    explore: tx("Explore", "浏览"),
    layout: tx("Layout", "布局"),
    model: tx("Model", "模型"),
  };
  const inspectorLabels = {
    inspect: tx("Overview", "概览"),
    source: tx("Source", "源码"),
    visual: tx("Visual", "视觉"),
    model: tx("Model", "模型"),
    evidence: tx("Evidence", "证据"),
  };
  const bottomLabels = {
    problems: tx("Problems", "问题"),
    source: tx("Source Workspace", "源码工作区"),
    diff: tx("Source Diff", "源码差异"),
    validation: tx("Validation", "验证"),
    jobs: tx("Jobs", "任务"),
    activity: tx("Activity", "活动"),
  };

  return (
    <LanguageContext.Provider value={{ locale, tx }}>
    <div
      className={`${dark ? "studio dark" : "studio"}${data.transaction ? " has-transaction" : ""}${panelResize ? ` resizing-panel resizing-${panelResize.edge}` : ""}`}
      style={{
        "--left-panel-width": `${panelSizes.left}px`,
        "--right-panel-width": `${panelSizes.right}px`,
        "--top-panel-height": `${panelSizes.top}px`,
        "--bottom-panel-height": `${bottomTab === "source" ? Math.max(320, panelSizes.bottom) : panelSizes.bottom}px`,
      } as React.CSSProperties}
    >
      <header className="topbar">
        <div className="product"><Box size={17} /> ArchCanvas</div>
        <button className="project-meta" onClick={() => setProjectDialog(true)} title={tx("Open or switch project", "打开或切换项目")}>
          <strong>{data.architecture.entrypoint.split(":").at(-1)}</strong>
          <span>{data.snapshot.revision}</span>
        </button>
        <div className="mode-switch" aria-label={tx("Studio mode", "Studio 模式")}>
          {(["explore", "layout", "model"] as Mode[]).map((item) => (
            <button key={item} className={mode === item ? "active" : ""} onClick={() => { setMode(item); if (item === "model") setInspectorTab("model"); }}>
              {item === "explore" ? <Eye size={14} /> : item === "layout" ? <Move size={14} /> : <Braces size={14} />}
              {modeLabels[item]}
            </button>
          ))}
        </div>
        <div className="top-actions">
          <div className="language-switch" role="group" aria-label={tx("Interface language", "界面语言")}>
            <button className={locale === "en" ? "active" : ""} aria-pressed={locale === "en"} onClick={() => setLocale("en")}>EN</button>
            <button className={locale === "zh" ? "active" : ""} aria-pressed={locale === "zh"} onClick={() => setLocale("zh")}>中文</button>
          </div>
          <button className="icon-button" title={tx("Undo", "撤销")} aria-label={tx("Undo", "撤销")} disabled={!data.document.visual_patches.length} onClick={() => void mutate("/api/undo")}><Undo2 /></button>
          <button className="icon-button" title={tx("Redo", "重做")} aria-label={tx("Redo", "重做")} disabled={!data.document.redo_patches.length} onClick={() => void mutate("/api/redo")}><Redo2 /></button>
          <div className={`writeback-gate ${writebackBlocked ? "blocked" : "ready"}`} title={writebackBlocked ? tx("Review blockers before committing", "提交前请检查阻断项") : tx("No draft blockers", "没有草稿阻断项")}><ShieldCheck size={14} />{writebackBlocked ? `${proofCounts.invalid ?? 0} ${tx("invalid", "无效")} · ${proofCounts.unproven ?? 0} ${tx("unproven", "未证明")}` : tx("Writeback clear", "可安全回写")}</div>
          <select className="profile-select" aria-label={tx("Validation profile", "验证配置")} value={validationProfile} onChange={(event) => setValidationProfile(event.target.value)}><option value="fast-static">{tx("Fast", "快速")}</option><option value="publication">{tx("Publication", "发布")}</option><option value="full">{tx("Full", "完整")}</option></select>
          <button className="validate-button" onClick={runValidation}><Play size={14} /> {tx("Validate", "验证")} <span>{latestValidation?.diagnostics.length ?? data.diagnostics.length}</span></button>
          <a className="primary-action" href="/api/export"><Download size={14} /> {tx("Export", "导出")}</a>
        </div>
      </header>

      {(["left", "right", "top", "bottom"] as PanelResizeEdge[]).map((edge) => {
        const vertical = edge === "left" || edge === "right";
        const label = {
          left: tx("Resize left sidebar", "调整左侧栏宽度"),
          right: tx("Resize right sidebar", "调整右侧栏宽度"),
          top: tx("Resize top bar", "调整顶部栏高度"),
          bottom: tx("Resize bottom panel", "调整底部面板高度"),
        }[edge];
        return <div
          key={edge}
          className={`panel-resizer resize-${edge}`}
          role="separator"
          aria-label={label}
          aria-orientation={vertical ? "vertical" : "horizontal"}
          aria-valuenow={panelSizes[edge]}
          tabIndex={0}
          title={`${label} · ${tx("Double-click to reset", "双击恢复默认")}`}
          onPointerDown={(event) => beginPanelResize(event, edge)}
          onPointerMove={movePanelResize}
          onPointerUp={() => setPanelResize(null)}
          onPointerCancel={() => setPanelResize(null)}
          onDoubleClick={() => resetPanelSize(edge)}
          onKeyDown={(event) => resizePanelWithKeyboard(event, edge)}
        />;
      })}

      <div className="workspace">
        <aside className="left-panel panel">
          <div className="panel-title"><PanelLeft size={15} /> {tx("Model", "模型")}</div>
          <div className="search-wrap"><div className="search-field"><Search size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && selectSearchResult()} placeholder={tx("Find node, tensor, port, evidence", "查找节点、张量、端口或证据")} /></div>{searchResults.length > 0 && <div className="search-results">{searchResults.slice(0, 8).map((result) => <button key={result.id} onClick={() => selectSearchResult(result)}><span>{result.title}</span><small>{result.kind}</small></button>)}</div>}</div>
          <div className="projection-switch" aria-label={tx("Navigation projection", "导航投影")}>
            {(["module", "source"] as const).map((item) => <button key={item} className={projection === item ? "active" : ""} aria-pressed={projection === item} onClick={() => switchProjection(item)}>{item === "module" ? <Layers3 size={14} /> : <FileCode2 size={14} />}<span>{item === "module" ? tx("Module relations", "模块关系") : tx("Source relations", "源码关系")}</span></button>)}
          </div>
          <div className="section-label">{projection === "module" ? tx("Module hierarchy", "模块层级") : tx("Source hierarchy", "源码层级")}</div>
          <div className="projection-description">{projection === "module" ? tx("Expand modules to reveal their contained architecture.", "展开模块以显示其包含的架构。") : tx("Browse source containment, calls, assignments, and references.", "浏览源码包含、调用、赋值与引用关系。")}</div>
          <div className="tree-list navigation-tree">
            {visibleNavigation.map((item) => {
              const active = focusedNavigationRowId === item.id;
              const related = !active && item.canonical_ids.some((canonicalId) => selectedNode?.canonical_node_ids.includes(canonicalId));
              const childCount = item.child_count;
              const hasVisibleChildren = childCount > 0;
              const relationLabel = navigationRelationLabel(item.relation, locale);
              const sourceOrder = projection === "source" && item.sibling_count > 1
                ? `${item.sibling_index}/${item.sibling_count}`
                : null;
              const location = item.path
                ? `${item.path}${item.span ? `:${item.span.start_line}:${item.span.start_column + 1}` : ""}`
                : item.relation;
              const secondaryLabel = navigationSecondaryLabel(item.secondary_label, tx);
              const indent = 4 + item.depth * 12;
              return <div key={item.id} className={`navigation-row ${active ? "selected" : ""} ${related ? "canonical-related" : ""} ${item.reference ? "reference-row" : ""} ${item.parent_id === null ? "tree-root" : ""}`} style={{ paddingLeft: `${indent}px`, "--tree-indent": `${indent}px` } as React.CSSProperties}><button className="tree-chevron" disabled={!hasVisibleChildren} aria-label={`${expansions[projection].has(item.id) ? tx("Collapse", "折叠") : tx("Expand", "展开")} ${item.label}`} onClick={() => toggleNavigationRow(item.id)}>{hasVisibleChildren ? expansions[projection].has(item.id) ? <ChevronDown size={13} /> : <ChevronRight size={13} /> : null}</button><button className="tree-subject" onClick={() => activateNavigationRow(item)} title={`${location} · ${tx("Relation", "关系")}：${relationLabel}${sourceOrder ? ` · ${tx("Sibling", "同级")} ${sourceOrder}（${tx("stable source order, not execution order", "稳定源码次序，不代表执行顺序")}）` : ""}`}>{navigationIcon(item.kind)}<span><b>{item.label}</b><span className="tree-meta">{secondaryLabel && secondaryLabel !== item.label && <small>{secondaryLabel}</small>}<i>{relationLabel}</i>{sourceOrder && <i title={tx("Stable source order under the same parent; not execution order", "同父节点中的稳定源码次序，不代表执行顺序")}>{tx("Sibling", "同级")} {sourceOrder}</i>}{item.binding_status === "ambiguous" && <i className="ambiguous" title={tx("Static evidence resolves only to a candidate set", "静态证据只能定位到候选集合")}>{tx("Candidate", "候选")}</i>}</span></span>{item.reference && <Link2 size={10} />}{childCount > 0 && <em>{childCount}</em>}{item.evidence_ids.length > 0 && <CircleDot size={9} />}</button></div>;
            })}
          </div>
          <section className="draft-panel">
            <header><span><Braces size={13} />{tx("Draft graph", "草稿图")}</span><div className="draft-actions"><button className="icon-button" disabled={!draftSourcePorts.length || !draftTargetPorts.length} title={tx("Create draft connection", "创建草稿连接")} aria-label={tx("Create draft connection", "创建草稿连接")} onClick={openDraftEdgeDialog}><Link2 size={13} /></button><button className="icon-button" title={tx("Create draft node", "创建草稿节点")} aria-label={tx("Create draft node", "创建草稿节点")} onClick={() => setDraftDialog(true)}><Plus size={13} /></button></div></header>
            {data.draft.nodes.length || data.draft.edges.length || canonicalDeleteIntents.length ? <div className="draft-list">{data.draft.nodes.map((node) => {
              const proof = data.draft.proofs.find((item) => item.affected_subject_ids.includes(node.node_id));
              return <div className="draft-item" key={node.node_id}><Box size={13} /><span><b>{node.semantic_name}</b><small>{node.node_type}</small></span><i className={proof?.status}>{proof?.status ?? data.draft.lowering_status}</i><button className="icon-button" title={tx("Delete draft node", "删除草稿节点")} aria-label={tx("Delete draft node", "删除草稿节点")} onClick={() => void deleteDraftNode(node.node_id)}><Trash2 size={12} /></button></div>;
            })}{data.draft.edges.map((edge) => {
              const proof = data.draft.proofs.find((item) => item.affected_subject_ids.includes(edge.edge_id));
              return <div className="draft-item draft-edge" key={edge.edge_id}><Link2 size={13} /><span><b>{draftPortLabels.get(edge.source_port_id) ?? edge.source_port_id}</b><small>{tx("to", "至")} {draftPortLabels.get(edge.target_port_id) ?? edge.target_port_id} · {edge.policy}</small></span><i className={proof?.status}>{proof?.status ?? data.draft.lowering_status}</i><button className="icon-button" title={tx("Delete draft connection", "删除草稿连接")} aria-label={tx("Delete draft connection", "删除草稿连接")} onClick={() => void deleteDraftEdge(edge.edge_id)}><Trash2 size={12} /></button></div>;
            })}{canonicalDeleteIntents.map((intent) => {
              const proof = data.draft.proofs.find((item) => item.intent_id === intent.intent_id);
              const impact = intent.user_input.impact as CanonicalDeleteImpact | undefined;
              return <div className="draft-item draft-delete" key={intent.intent_id}><Trash2 size={13} /><span><b>{tx("Delete", "删除")} · {impact?.semantic_name ?? intent.target_ids[0]}</b><small>{intent.expected_delta?.removed_edges.length ?? 0} {tx("edges", "条边")} · {intent.expected_delta?.removed_tensors.length ?? 0} Tensor</small></span><i className={proof?.status}>{proof?.status ?? data.draft.lowering_status}</i><button className="icon-button" title={tx("Discard delete intent", "丢弃删除意图")} aria-label={tx("Discard delete intent", "丢弃删除意图")} onClick={() => void discardCanonicalDeleteIntent(intent.intent_id)}><X size={12} /></button></div>;
            })}</div> : <div className="draft-empty">{tx("No draft changes", "没有草稿变更")}</div>}
          </section>
        </aside>

        <main className="canvas-column">
          <div className="canvas-toolbar">
            <div className="breadcrumb">{breadcrumb}</div>
            <div className="canvas-actions">
              <label className="layout-strategy"><Layers3 size={14} /><select aria-label={tx("Diagram layout", "图形布局")} value={data.view_state.layout_mode ?? "auto"} onChange={(event) => void mutate("/api/layout-mode", { layout_mode: event.target.value }, `${tx("Layout", "布局")} · ${event.target.value}`)}><option value="auto">{tx("Auto", "自动")}</option><option value="dual-swimlane">{tx("Dual swimlane", "双泳道")}</option><option value="single-lane">{tx("Single lane", "单泳道")}</option><option value="hierarchical">{tx("Hierarchical DAG", "层级图")}</option><option value="branch-tree">{tx("Branch tree", "分支树")}</option><option value="force-directed">{tx("Force directed", "力导向")}</option><option value="radial">{tx("Radial", "径向")}</option><option value="orthogonal">{tx("Orthogonal", "正交")}</option></select></label>
              {mode === "layout" && <>
                <label className="layout-strategy"><Grip size={14} /><select aria-label={tx("Arrange selection", "排列所选节点")} value="" disabled={selectedIds.length < 2} onChange={(event) => align(event.target.value)}><option value="" disabled>{tx("Arrange", "排列")}</option><option value="left">{tx("Align left", "左对齐")}</option><option value="hcenter">{tx("Align horizontal centers", "水平居中")}</option><option value="right">{tx("Align right", "右对齐")}</option><option value="top">{tx("Align top", "顶部对齐")}</option><option value="vcenter">{tx("Align vertical centers", "垂直居中")}</option><option value="bottom">{tx("Align bottom", "底部对齐")}</option><option value="distribute-horizontal">{tx("Distribute horizontally", "水平分布")}</option><option value="distribute-vertical">{tx("Distribute vertically", "垂直分布")}</option><option value="same-width">{tx("Same width", "等宽")}</option><option value="same-height">{tx("Same height", "等高")}</option><option value="same-size">{tx("Same size", "等尺寸")}</option></select></label>
                <label className="route-strategy"><Route size={14} /><select aria-label={tx("Auto-route strategy", "自动布线方案")} value={routeStrategy} onChange={(event) => setRouteStrategy(event.target.value as RouteStrategy)}><option value="avoid">{tx("Scheme 1 · Avoid obstacles", "方案 1 · 避障优先")}</option><option value="balanced">{tx("Scheme 2 · Balanced", "方案 2 · 平衡")}</option><option value="compact">{tx("Scheme 3 · Shortest path", "方案 3 · 最短路径")}</option></select></label>
                <button className="open-full" title={tx("Apply the selected routing strategy", "应用所选布线方案")} onClick={() => void mutate("/api/route", { batch_id: patchId("route").replace("patch:", "batch:"), strategy: routeStrategy }, `${tx("Auto route", "自动布线")} · ${routeStrategy}`)}><Route size={14} /> {tx("Route", "布线")}</button>
                <button className="open-full" disabled={layoutLoading} onClick={() => void requestLayoutCandidates()}>{layoutLoading ? <RefreshCw className="spin" size={14} /> : <Layers3 size={14} />} {tx("Auto layout", "自动布局")}</button>
              </>}
              <button className="icon-button" title={tx("Zoom out", "缩小")} aria-label={tx("Zoom out", "缩小")} onClick={() => zoom(1.2)}><ZoomOut /></button>
              <button className="icon-button" title={tx("Zoom in", "放大")} aria-label={tx("Zoom in", "放大")} onClick={() => zoom(0.82)}><ZoomIn /></button>
              <button className="icon-button" title={tx("Fit scene", "适应画布")} aria-label={tx("Fit scene", "适应画布")} onClick={fitScene}><Maximize2 /></button>
              <button className="icon-button mobile-only" title={tx("Open inspector", "打开检查器")} aria-label={tx("Open inspector", "打开检查器")} onClick={() => setMobileInspector(true)}><PanelRight /></button>
            </div>
          </div>
          <div className="canvas-stage">
            {layoutCandidates.length > 0 && <section className="layout-candidate-panel" aria-label={tx("Layout candidates", "布局候选")}><header><div><Eye size={14} /><strong>{tx("Layout preview", "布局预览")}</strong></div><button className="icon-button" title={tx("Close preview", "关闭预览")} aria-label={tx("Close preview", "关闭预览")} onClick={() => { setLayoutCandidates([]); setLayoutPreviewId(null); }}><X size={13} /></button></header><div className="layout-candidate-list" role="radiogroup">{layoutCandidates.map((candidate, index) => <button key={candidate.candidate_id} className={candidate.candidate_id === layoutPreviewId ? "selected" : ""} role="radio" aria-checked={candidate.candidate_id === layoutPreviewId} onClick={() => setLayoutPreviewId(candidate.candidate_id)}><span>{index + 1}</span><strong>{candidate.strategy.replaceAll("-", " ")}</strong><small>{tx("score", "评分")} {candidate.score.toFixed(1)} · {candidate.metrics.changed_nodes} {tx("changes", "项变更")}</small></button>)}</div><footer><span>{tx("Preview is not saved", "预览尚未保存")}</span><button className="apply-visual" onClick={() => void applyLayoutCandidate()}>{tx("Apply", "应用")}</button></footer></section>}
            <svg ref={svgRef} className={`scene semantic-${semanticZoom} ${selectedEdge ? "has-edge-selection" : ""}`} style={{ "--font-scale": data.view_state.font_scale ?? 1, "--label-scale": labelScale, "--container-label-scale": containerLabelScale } as React.CSSProperties} viewBox={viewBox.join(" ")} onPointerDown={beginPan} onPointerMove={movePointer} onPointerUp={endPointer} onPointerCancel={cancelPointer} onWheel={(event) => { event.preventDefault(); zoom(event.deltaY > 0 ? 1.1 : 0.9); }}>
              <defs><marker id="studio-arrow" viewBox="0 0 10 10" refX="8.4" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto-start-reverse"><path d="M0 0 10 5 0 10Z" fill="context-stroke" /></marker></defs>
              <rect className="paper" width={scene.paper_width} height={scene.paper_height} />
              <g className="root-layer">{sceneIndex.roots.map(renderSceneNode)}</g>
              <g className="container-layer">{sceneIndex.containers.map(renderSceneNode)}</g>
              <g className="edge-layer">{scene.edges.map((edge, index) => renderSceneEdge(edge, index))}</g>
              <g className="node-layer">{sceneIndex.leaves.map(renderSceneNode)}</g>
              <g className="annotation-layer">{(scene.annotations ?? []).map((annotation) => <g key={annotation.annotation_id} className="scene-annotation" role="note" aria-label={annotation.text}><rect x={annotation.bounds.x} y={annotation.bounds.y} width={annotation.bounds.width} height={annotation.bounds.height} rx={4} fill={annotation.fill} stroke={annotation.stroke} /><text x={annotation.bounds.x + 10} y={annotation.bounds.y + 21}>{annotation.text.slice(0, 52)}</text></g>)}</g>
              {scene.caption && <text className="scene-caption" textAnchor="middle" x={scene.paper_width / 2} y={scene.paper_height - 12}>{scene.caption}</text>}
              {marquee && (() => { const bounds = selectionBounds(marquee.start, marquee.current); return <rect className="marquee-selection" x={bounds.x} y={bounds.y} width={bounds.width} height={bounds.height} />; })()}
              <g className="edge-overlay-layer">{selectedEdge && renderSceneEdge(selectedEdge, scene.edges.indexOf(selectedEdge), true)}</g>
              {mode === "layout" && selectedEdge && (() => {
                const points = edgeRoutePreview ?? previewEdgePoints(selectedEdge, sceneIndex.byId, EMPTY_POSITION_PREVIEW, scene.edges.indexOf(selectedEdge));
                const radius = Math.min(20, Math.max(5, 6 / screenScale));
                return <g className="edge-route-handles"><circle className={`edge-route-handle source ${edgeEndpointDrag?.endpoint === "source" ? "dragging" : ""}`} data-endpoint="source" cx={points[0].x} cy={points[0].y} r={radius} onPointerDown={(event) => beginEdgeEndpointDrag(event, "source")}><title>{tx("Move source connection", "移动起点连接")}</title></circle><circle className={`edge-route-handle target ${edgeEndpointDrag?.endpoint === "target" ? "dragging" : ""}`} data-endpoint="target" cx={points.at(-1)!.x} cy={points.at(-1)!.y} r={radius} onPointerDown={(event) => beginEdgeEndpointDrag(event, "target")}><title>{tx("Move target connection", "移动终点连接")}</title></circle></g>;
              })()}
            </svg>
            {scene.legend_placement !== "hidden" && <div className={`relation-legend legend-${scene.legend_placement ?? "top-left"}`} aria-label={tx("Visible relation types", "可见关系类型")}>{[...new Map(scene.edges.map((edge) => [edge.visual_relation, edge])).values()].map((edge) => <span key={edge.visual_relation}><i className={edge.dash ? "dashed" : ""} style={{ "--relation-color": edge.stroke } as React.CSSProperties} />{relationLabel(edge.visual_relation)}</span>)}</div>}
            {selectedEdge && <div className="edge-flow-status" role="status"><strong>{sceneIndex.byId.get(selectedEdge.source_scene_node_id)?.label_lines.join(" ")}</strong><ArrowRight size={13} /><strong>{sceneIndex.byId.get(selectedEdge.target_scene_node_id)?.label_lines.join(" ")}</strong><span>{relationLabel(selectedEdge.visual_relation)}</span></div>}
            {selectedNode && <div className="context-bar"><button title={tx("Focus selection", "聚焦所选内容")} aria-label={tx("Focus selection", "聚焦所选内容")} onClick={focusSelection}><Focus size={14} /></button><button title={pinned.has(selectedNode.scene_node_id) ? tx("Unpin", "取消固定") : tx("Pin", "固定")} onClick={() => void submit("set-pin", selectedNode.scene_node_id, { enabled: !pinned.has(selectedNode.scene_node_id) })}>{pinned.has(selectedNode.scene_node_id) ? <PinOff size={14} /> : <Pin size={14} />}</button><button title={tx("Expand in navigation tree", "在导航树中展开")} onClick={() => expandInNavigation(selectedNode)}><Maximize2 size={14} /></button></div>}
          </div>
        </main>

        <aside className={`right-panel panel ${mobileInspector ? "mobile-open" : ""}`}>
          <div className="panel-title"><PanelRight size={15} /> {tx("Inspector", "检查器")}<button className="icon-button mobile-only inspector-close" title={tx("Close inspector", "关闭检查器")} onClick={() => setMobileInspector(false)}><X /></button></div>
          <div className="tab-strip">{(["inspect", "source", "visual", "model", "evidence"] as const).map((tab) => <button key={tab} className={inspectorTab === tab ? "active" : ""} onClick={() => setInspectorTab(tab)}>{inspectorLabels[tab]}</button>)}</div>
          {!selectedNode || !selectedViewNode ? <div className="empty-state"><Focus size={20} /><span>{tx("No selection", "未选择内容")}</span></div> : <div className="inspector-content">
            {inspectorTab === "inspect" && <StructureInspector label={selectedViewNode.semantic_name} viewNode={selectedViewNode} sceneNode={selectedNode} nodes={selectedArchitectureNodes} tensors={data.architecture.tensors} evidence={selectedEvidence} />}
            {inspectorTab === "source" && <SourceInspector nodes={selectedArchitectureNodes} evidence={selectedEvidence} />}
            {inspectorTab === "visual" && <VisualInspector node={selectedNode} pinned={pinned.has(selectedNode.scene_node_id)} fontScale={data.view_state.font_scale ?? 1} lineWeight={data.view_state.line_weight ?? 1.5} caption={scene.caption ?? ""} legendPlacement={scene.legend_placement ?? "top-left"} onPatch={submit} onBatch={submitBatch} />}
            {inspectorTab === "model" && <ModelInspector node={architectureNode} nodes={data.architecture.nodes} transaction={data.transaction} proposal={data.proposal} writebackBlocked={writebackBlocked} deleteIntentActive={canonicalDeleteIntents.some((intent) => intent.target_ids[0] === architectureNode?.node_id)} deleteImpactLoading={deleteImpactLoading} onPrepareParameter={prepareParameter} onPrepareStructural={prepareStructural} onProposeConnection={proposeConnection} onReviewDelete={reviewCanonicalDelete} onCommit={commitSourceTransaction} onDiscard={async () => { await mutate("/api/transaction/discard", {}, tx("Discarded source transaction", "已放弃源码事务")); }} />}
            {inspectorTab === "evidence" && <div className="evidence-list">{selectedEvidence.length ? selectedEvidence.map((record) => <section key={record.evidence_id}><div><FileCode2 size={14} /><strong>{record.kind}</strong><span>{record.confidence}</span></div><code>{record.path ?? record.evidence_id}{record.span ? `:${record.span.start_line}` : ""}</code><p>{record.claim}</p></section>) : <div className="empty-state">{tx("No linked evidence", "没有关联证据")}</div>}</div>}
          </div>}
        </aside>
      </div>

      <section className="bottom-panel">
        <div className="bottom-tabs"><PanelBottom size={14} />{(["problems", "source", "diff", "validation", "jobs", "activity"] as const).map((tab) => <button key={tab} className={bottomTab === tab ? "active" : ""} onClick={() => setBottomTab(tab)}>{bottomLabels[tab]}{tab === "problems" && <span>{data.diagnostics.length}</span>}{tab === "source" && data.source_workspace.state !== "clean" && <span>{data.source_workspace.files.filter((file) => file.state !== "clean").length}</span>}{tab === "jobs" && data.jobs?.some((job) => ["queued", "running"].includes(job.state)) && <span>1</span>}</button>)}</div>
        <div className="bottom-content">
          {bottomTab === "problems" && ([...data.diagnostics, ...data.draft.proofs.map((proof) => ({ code: proof.reason_codes[0] ?? proof.status.toUpperCase(), severity: proof.status, message: proof.message, target_ids: proof.affected_subject_ids }))].length ? [...data.diagnostics, ...data.draft.proofs.map((proof) => ({ code: proof.reason_codes[0] ?? proof.status.toUpperCase(), severity: proof.status, message: proof.message, target_ids: proof.affected_subject_ids }))].map((item, index) => <button key={`${item.code}-${index}`} onClick={() => choose(scene.nodes.find((node) => node.canonical_node_ids.some((id) => item.target_ids.includes(id)))?.scene_node_id ?? null)}><AlertTriangle size={13} /><b>{item.severity}</b><span>{item.message}</span></button>) : <div className="ok-line"><CircleDot size={13} /> {tx("No geometry or writeback problems", "没有几何或回写问题")}</div>)}
          {bottomTab === "source" && <SourceWorkspacePanel workspace={data.source_workspace} transaction={data.transaction} sessionNonce={data.session_nonce} onState={setData} onActivity={(message) => setActivity((items) => [message, ...items].slice(0, 20))} onShowDiff={() => setBottomTab("diff")} />}
          {bottomTab === "diff" && (data.transaction ? <TransactionReview transaction={data.transaction} writebackBlocked={writebackBlocked} onCommit={commitSourceTransaction} onDiscard={async () => { await mutate("/api/transaction/discard", {}, tx("Discarded source transaction", "已放弃源码事务")); }} /> : <div className="ok-line"><LockKeyhole size={13} /> {tx(`Source digest ${sourceDigest} unchanged`, `源码摘要 ${sourceDigest} 未改变`)}</div>)}
          {bottomTab === "validation" && (latestValidation ? <div className="gate-list">{latestValidation.gate_results.map((gate) => <span key={gate.gate} className={gate.status}>{gate.status} · {gate.gate} · {gate.message}</span>)}</div> : <div className="validation-line"><CircleDot size={13} /> {tx("Validation has not been run for this fingerprint", "尚未为此指纹运行验证")}</div>)}
          {bottomTab === "jobs" && <div className="job-list">{data.jobs?.length ? data.jobs.map((job) => <div key={job.job_id}><code>{job.job_id}</code><span>{job.profile}</span><b>{job.state} · {Math.round(job.progress * 100)}%</b>{["queued", "running", "cancelling"].includes(job.state) && <button className="icon-button" title={tx("Cancel job", "取消任务")} aria-label={tx("Cancel job", "取消任务")} onClick={() => void cancelJob(job.job_id)}><X size={12} /></button>}</div>) : <div className="validation-line">{tx("No jobs in this session", "本会话中没有任务")}</div>}</div>}
          {bottomTab === "activity" && <div className="activity-list">{activity.map((item, index) => <span key={`${item}-${index}`}><History size={12} />{item}</span>)}</div>}
        </div>
      </section>

      <button className="theme-toggle icon-button" title={tx("Toggle theme", "切换主题")} aria-label={tx("Toggle theme", "切换主题")} onClick={() => { const next = !dark; setDark(next); void submit("set-theme", undefined, { theme: next ? "studio-dark" : "paper-light" }); }}>{dark ? <Sun /> : <Moon />}</button>
      {projectDialog && <div className="dialog-backdrop" role="presentation" onPointerDown={(event) => { if (event.target === event.currentTarget) setProjectDialog(false); }}>
        <section className="project-dialog project-launcher" role="dialog" aria-modal="true" aria-label={tx("Open model", "打开模型")}>
          <header>
            <div className="launcher-title"><Box size={18} /><div><strong>{tx("Open model", "打开模型")}</strong><span>ArchCanvas Model Architecture Studio</span></div></div>
            <button className="icon-button" title={tx("Close", "关闭")} aria-label={tx("Close", "关闭")} onClick={() => setProjectDialog(false)}><X /></button>
          </header>

          <div className="launcher-field">
            <div className="launcher-label"><span>1</span><div><strong>{tx("Conda environment", "Conda 环境")}</strong><small>{environmentLoading ? tx("Loading", "正在加载") : `${condaEnvironments.length} ${tx("available", "个可用")}`}</small></div><button className="icon-button launcher-refresh" aria-label={tx("Reload environments", "重新加载环境")} title={tx("Reload environments", "重新加载环境")} onClick={() => setCondaEnvironments([])} disabled={environmentLoading}><RefreshCw size={14} /></button></div>
            <select aria-label={tx("Conda environment", "Conda 环境")} value={condaEnvironment} disabled={environmentLoading} onChange={(event) => { setCondaEnvironment(event.target.value); setPendingProject(null); }}>
              <option value="">{tx("Studio environment (static analysis)", "Studio 环境（静态分析）")}</option>
              {condaEnvironments.map((item) => <option key={item.path} value={item.path}>{item.active ? "● " : ""}{item.name} — {item.path}</option>)}
            </select>
          </div>

          <div className="launcher-field">
            <div className="launcher-label"><span>2</span><div><strong>{tx("Model location", "模型存放路径")}</strong><small>{tx("Parent folders are supported", "支持选择上级文件夹")}</small></div></div>
            <div className="path-scan-row"><div className="path-input"><FolderOpen size={15} /><input aria-label={tx("Model location", "模型存放路径")} value={projectRoot} onChange={(event) => { setProjectRoot(event.target.value); setPendingProject(null); setProjectError(""); }} onKeyDown={(event) => { if (event.key === "Enter") void openProject(); }} /></div><button className="folder-button icon-button" aria-label={tx("Browse folders", "浏览文件夹")} title={tx("Browse folders", "浏览文件夹")} onClick={() => void browseFolders()}><FolderOpen size={14} /></button><button className="prepare-button" disabled={!projectRoot.trim() || projectScanning} onClick={() => void openProject()}>{projectScanning ? <RefreshCw className="spin" size={14} /> : <Search size={14} />} {tx("Scan", "扫描")}</button></div>
          </div>

          {folderPicker && <div className="folder-picker" role="dialog" aria-label={tx("Choose model folder", "选择模型文件夹")}>
            <div className="folder-picker-header"><strong>{tx("Choose folder", "选择文件夹")}</strong><button className="icon-button" aria-label={tx("Close folder picker", "关闭文件夹选择器")} onClick={() => { setFolderPicker(null); setSelectedFolderPath(null); }}><X size={14} /></button></div>
            <div className="folder-breadcrumbs">{folderPicker.breadcrumbs.map((crumb) => <button key={crumb.path} onClick={() => void browseFolders(crumb.path)}>{crumb.name}</button>)}</div>
            <div className="folder-picker-toolbar"><button className="icon-button" disabled={!folderPicker.parent || folderLoading} aria-label={tx("Parent folder", "上级文件夹")} title={tx("Parent folder", "上级文件夹")} onClick={() => folderPicker.parent && void browseFolders(folderPicker.parent)}><CornerDownLeft size={14} /></button><code>{folderPicker.path}</code></div>
            <div className="folder-list">{folderPicker.directories.map((directory) => <button key={directory.path} className={selectedFolderPath === directory.path ? "selected" : ""} aria-pressed={selectedFolderPath === directory.path} onDoubleClick={() => void browseFolders(directory.path)} onClick={() => setSelectedFolderPath(directory.path)}><FolderOpen size={14} /><span>{directory.name}</span></button>)}{!folderPicker.directories.length && <span className="folder-empty">{tx("No subfolders", "没有子文件夹")}</span>}</div>
            <div className="folder-picker-actions"><button onClick={() => { setFolderPicker(null); setSelectedFolderPath(null); }}>{tx("Cancel", "取消")}</button><button className="primary-action" onClick={() => { setProjectRoot(selectedFolderPath ?? folderPicker.path); setPendingProject(null); setFolderPicker(null); setSelectedFolderPath(null); }}>{selectedFolderPath ? tx("Choose selected folder", "选择已选文件夹") : tx("Choose this folder", "选择此文件夹")}</button></div>
          </div>}

          {projectError && <div className="launcher-error" role="alert"><AlertTriangle size={14} /><span>{projectError}</span></div>}

          {pendingProject && <div className="project-options">
            <div className="launcher-label"><span>3</span><div><strong>{tx("Detected model hierarchy", "检测到的模型层级")}</strong><small>{pendingProject.discovery.entrypoints.filter((item) => item.top_level).length} {tx("top-level models", "个顶层模型")} · {pendingProject.discovery.entrypoints.filter((item) => !item.top_level).length} {tx("components", "个组件")} · {pendingProject.discovery.scanned_files} {tx("files scanned", "个文件已扫描")}</small></div></div>
            {pendingProject.discovery.entrypoints.length ? <div className="model-candidate-list" role="radiogroup" aria-label={tx("Detected models", "检测到的模型")}>
              {visibleProjectEntrypoints(pendingProject.discovery.entrypoints, projectModelExpansions).map((item) => {
                const selected = projectEntrypoint === item.entrypoint;
                const symbolName = item.entrypoint.includes(":") ? item.entrypoint.split(":").at(-1)! : item.path.split("/").at(-1)!;
                const sourceName = item.path.split("/").at(-1)!.replace(/\.py$/i, "");
                const name = item.top_level && symbolName === "Model" && sourceName.toLowerCase() !== "model" ? sourceName : symbolName;
                const categoryLabels: Record<ProjectEntrypoint["category"], string> = { model: tx("Model", "完整模型"), encoder: "Encoder", decoder: "Decoder", backbone: "Backbone", attention: "Attention", head: "Head", block: "Block", layer: "Layer", component: tx("Component", "组件") };
                const expanded = projectModelExpansions.has(item.entrypoint);
                return <div key={item.entrypoint} className={`model-candidate-row depth-${Math.min(item.depth, 8)}`} style={{ "--candidate-depth": item.depth } as React.CSSProperties}>
                  <button className="candidate-chevron" aria-label={expanded ? tx("Collapse children", "收起子级") : tx("Expand children", "展开子级")} disabled={!item.child_count} onClick={() => setProjectModelExpansions((current) => { const next = new Set(current); if (next.has(item.entrypoint)) next.delete(item.entrypoint); else next.add(item.entrypoint); return next; })}>{item.child_count ? (expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />) : null}</button>
                  <button className={`model-candidate ${selected ? "selected" : ""} ${item.top_level ? "top-level" : ""}`} role="radio" aria-checked={selected} onClick={() => selectProjectEntrypoint(item)}><span className="candidate-check">{selected ? <CircleDot size={15} /> : <span />}</span><span className="candidate-main"><strong>{name}</strong><span className={`category-badge category-${item.category}`}>{categoryLabels[item.category]}</span><code>{item.entrypoint}</code><small><FileCode2 size={12} />{item.path}</small></span><span className={`framework-badge framework-${item.framework}`}>{item.framework}</span></button>
                </div>;
              })}
            </div> : <div className="launcher-empty"><Search size={18} /><span>{tx("No supported models found", "未找到支持的模型")}</span></div>}
            {projectEntrypoint && <div className="launcher-options"><label><span>{tx("Framework", "框架")}</span><select value={projectFramework} onChange={(event) => setProjectFramework(event.target.value)}>{["auto", "pytorch", "keras", "jax", "onnx", "python"].map((item) => <option key={item}>{item}</option>)}</select></label><label><span>{tx("Config", "配置")}</span><select value={projectConfig} onChange={(event) => setProjectConfig(event.target.value)}><option value="">{tx("No config", "无配置")}</option>{pendingProject.discovery.configs.filter((item) => pendingProject.discovery.entrypoints.find((candidate) => candidate.entrypoint === projectEntrypoint)?.config_paths.includes(item.path)).map((item) => <option key={item.path}>{item.path}</option>)}</select></label></div>}
            <div className="launcher-actions"><button onClick={() => setProjectDialog(false)}>{tx("Cancel", "取消")}</button><button className="primary-action" disabled={!projectEntrypoint} onClick={() => void analyzeProject()}><Play size={14} /> {tx("Open model", "打开模型")}</button></div>
          </div>}
        </section>
      </div>}
      {draftDialog && <div className="dialog-backdrop" role="presentation" onPointerDown={(event) => { if (event.target === event.currentTarget) setDraftDialog(false); }}>
        <section className="project-dialog draft-dialog" role="dialog" aria-modal="true" aria-label={tx("Create draft node", "创建草稿节点")}>
          <header><div><strong>{tx("Create draft node", "创建草稿节点")}</strong><span>{data.project.framework} · DraftGraphDocument</span></div><button className="icon-button" title={tx("Close", "关闭")} aria-label={tx("Close", "关闭")} onClick={() => setDraftDialog(false)}><X /></button></header>
          <label className="model-field"><span>{tx("Semantic name", "语义名称")}</span><input autoFocus value={draftName} onChange={(event) => setDraftName(event.target.value)} /></label>
          <label className="model-field"><span>{tx("Node type", "节点类型")}</span><input value={draftType} onChange={(event) => setDraftType(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void createDraftNode(); }} /></label>
          <Field label={tx("Parent anchor", "父级锚点")} value={selectedCanonicalIds[0] ?? tx("Architecture root", "架构根节点")} mono />
          <div className="launcher-actions"><button onClick={() => setDraftDialog(false)}>{tx("Cancel", "取消")}</button><button className="primary-action" disabled={!draftName.trim() || !draftType.trim()} onClick={() => void createDraftNode()}><Plus size={14} /> {tx("Create draft", "创建草稿")}</button></div>
        </section>
      </div>}
      {draftEdgeDialog && <div className="dialog-backdrop" role="presentation" onPointerDown={(event) => { if (event.target === event.currentTarget) setDraftEdgeDialog(false); }}>
        <section className="project-dialog draft-dialog" role="dialog" aria-modal="true" aria-label={tx("Create draft connection", "创建草稿连接")}>
          <header><div><strong>{tx("Create draft connection", "创建草稿连接")}</strong><span>DraftGraphDocument · {tx("source remains unchanged", "不修改源码")}</span></div><button className="icon-button" title={tx("Close", "关闭")} aria-label={tx("Close", "关闭")} onClick={() => setDraftEdgeDialog(false)}><X /></button></header>
          <label className="model-field"><span>{tx("Source output", "源输出端口")}</span><select autoFocus value={draftEdgeSource} onChange={(event) => setDraftEdgeSource(event.target.value)}>{draftSourcePorts.map((port) => <option key={port.port_id} value={port.port_id}>{draftPortLabels.get(port.port_id)} · {port.role}</option>)}</select></label>
          <label className="model-field"><span>{tx("Target input", "目标输入端口")}</span><select value={draftEdgeTarget} onChange={(event) => setDraftEdgeTarget(event.target.value)}>{draftTargetPorts.map((port) => <option key={port.port_id} value={port.port_id}>{draftPortLabels.get(port.port_id)} · {port.role}</option>)}</select></label>
          <label className="model-field"><span>{tx("Connection policy", "连接策略")}</span><select value={draftEdgePolicy} onChange={(event) => setDraftEdgePolicy(event.target.value as DraftEdgePolicy)}><option value="replace-input">{tx("Replace input", "替换输入")}</option><option value="add-residual">{tx("Add residual", "添加残差")}</option><option value="concat">{tx("Concatenate", "拼接")}</option><option value="fanout">{tx("Fan out", "扇出")}</option><option value="disconnect">{tx("Disconnect", "断开")}</option></select></label>
          <div className="launcher-actions"><button onClick={() => setDraftEdgeDialog(false)}>{tx("Cancel", "取消")}</button><button className="primary-action" disabled={!draftEdgeSource || !draftEdgeTarget} onClick={() => void createDraftEdge()}><Link2 size={14} /> {tx("Create connection", "创建连接")}</button></div>
        </section>
      </div>}
      {deleteImpact && <div className="dialog-backdrop" role="presentation" onPointerDown={(event) => { if (event.target === event.currentTarget) setDeleteImpact(null); }}>
        <section className="project-dialog impact-dialog" role="dialog" aria-modal="true" aria-label={tx("Deletion impact preview", "删除影响预览")}>
          <header><div><strong>{tx("Deletion impact preview", "删除影响预览")}</strong><span>{deleteImpact.semantic_name} · {deleteImpact.node_id}</span></div><button className="icon-button" title={tx("Close", "关闭")} aria-label={tx("Close", "关闭")} onClick={() => setDeleteImpact(null)}><X /></button></header>
          <div className="impact-warning"><AlertTriangle size={16} /><span>{tx("This preview creates an intent only. Exact IR and source stay unchanged.", "此预览只会创建意图，Exact IR 与源码保持不变。")}</span></div>
          <div className="impact-metrics"><div><strong>{deleteImpact.incoming_edge_ids.length}</strong><span>{tx("incoming edges", "条入边")}</span></div><div><strong>{deleteImpact.outgoing_edge_ids.length}</strong><span>{tx("outgoing edges", "条出边")}</span></div><div><strong>{deleteImpact.produced_tensor_ids.length}</strong><span>{tx("produced tensors", "个输出 Tensor")}</span></div><div><strong>{deleteImpact.downstream_node_ids.length}</strong><span>{tx("downstream nodes", "个下游节点")}</span></div></div>
          <section className="impact-details"><h3>{tx("Structural impact", "结构影响")}</h3><dl><dt>Fanout</dt><dd>{deleteImpact.fanout_ids.length}</dd><dt>{tx("Shared parameters", "共享参数节点")}</dt><dd>{deleteImpact.shared_parameter_node_ids.length}</dd><dt>{tx("Children", "子节点")}</dt><dd>{deleteImpact.child_node_ids.length}</dd><dt>Repeat</dt><dd>{deleteImpact.repeat_id ?? tx("None", "无")}</dd><dt>{tx("Source anchors", "源码锚点")}</dt><dd>{deleteImpact.source_evidence_ids.length}</dd><dt>{tx("Runtime evidence", "运行时证据")}</dt><dd>{deleteImpact.runtime_evidence_ids.length}</dd></dl></section>
          <section className="impact-details"><h3>{tx("Required decisions", "必须决策")}</h3><p>{deleteImpact.required_action}</p>{deleteImpact.blocking_reasons.length ? <ul>{deleteImpact.blocking_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : <p>{tx("Adapter lowering proof is still required.", "仍需适配器 lowering 证明。")}</p>}</section>
          <div className="launcher-actions"><button onClick={() => setDeleteImpact(null)}>{tx("Cancel", "取消")}</button><button className="danger-action" onClick={() => void createCanonicalDeleteIntent()}><Trash2 size={14} /> {tx("Create blocked intent", "创建阻断意图")}</button></div>
        </section>
      </div>}
    </div>
    </LanguageContext.Provider>
  );
}

function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="field"><label>{label}</label><div className={mono ? "mono" : ""}>{value}</div></div>;
}

function structureKind(label: string, nodes: ArchitectureNodeView[]): "tensor" | "encoder" | "decoder" | "ffn" | "norm" | "attention" | "residual" | "convolution" | "pooling" | "recurrent" | "graph" | "moe" | "diffusion" | "state-space" | "embedding" | "activation" | "dropout" | "generic" {
  const normalizedLabel = label.trim().toLowerCase();
  const text = `${normalizedLabel} ${nodes.map((node) => `${node.semantic_name} ${String(node.attributes.op_type ?? "")}`).join(" ")}`.toLowerCase();
  if (["q", "k", "v", "query", "key", "value"].includes(normalizedLabel)) return "tensor";
  if (normalizedLabel.includes("residual") || normalizedLabel.includes("skip") || normalizedLabel === "add") return "residual";
  if (text.includes("diffusion") || text.includes("denois") || text.includes("timestep") || text.includes("noise schedule") || text.includes("unet")) return "diffusion";
  if (text.includes("mixture of expert") || text.includes("moe") || text.includes("expert") || text.includes("router") || text.includes("gating")) return "moe";
  if (text.includes("state space") || text.includes("ssm") || text.includes("mamba") || text.includes("selective scan")) return "state-space";
  if (text.includes("lstm") || text.includes("gru") || text.includes("rnn") || text.includes("recurrent") || text.includes("hidden state")) return "recurrent";
  if (text.includes("graph") || text.includes("gcn") || text.includes("gat") || text.includes("neighbor") || text.includes("message passing")) return "graph";
  if (text.includes("conv1d") || text.includes("conv2d") || text.includes("convolution") || text.includes("conv ")) return "convolution";
  if (text.includes("pool") || text.includes("adaptive avg") || text.includes("global avg")) return "pooling";
  if (text.includes("residual") || text.includes("skip connection") || normalizedLabel === "add" || normalizedLabel === "skip") return "residual";
  if (text.includes("multihead") || text.includes("multi-head") || text.includes("attention") || text.includes("qkv")) return "attention";
  if (text.includes("embedding") || text.includes("positional") || text.includes("token embedding")) return "embedding";
  if (text.includes("dropout")) return "dropout";
  if (text.includes("activation") || text.includes("relu") || text.includes("gelu") || text.includes("silu") || text.includes("swish")) return "activation";
  if (normalizedLabel.includes("encoder")) return nodes.length > 2 ? "encoder" : "norm";
  if (normalizedLabel.includes("decoder") || normalizedLabel === "cross") return "decoder";
  if (text.includes("ffn") || text.includes("feed forward") || text.includes("mlp")) return "ffn";
  if (text.includes("norm")) return "norm";
  if (text.includes("split") || text.includes("transpose") || text.includes("projection")) return "tensor";
  return "generic";
}

function StructureGlyph({ kind, label, count }: { kind: ReturnType<typeof structureKind>; label: string; count: number }) {
  const { tx } = useLanguage();
  if (kind === "tensor") {
    return <svg className="structure-glyph tensor-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} ${tx("tensor structure", "张量结构")}`}>
      <g className="tensor-planes">
        <rect x="35" y="16" width="132" height="70" />
        <rect x="47" y="25" width="132" height="70" />
        <rect x="59" y="34" width="132" height="70" />
        {[81, 103, 125, 147, 169].map((x) => <line key={`x-${x}`} x1={x} y1="34" x2={x} y2="104" />)}
        {[51, 68, 85].map((y) => <line key={`y-${y}`} x1="59" y1={y} x2="191" y2={y} />)}
      </g>
      <text x="202" y="45">{tx("heads", "头")}</text><text x="202" y="64">{tx("tokens", "词元")}</text><text x="202" y="83">{tx("features", "特征")}</text>
      <text className="glyph-title" x="35" y="112">{tx("stacked matrix", "堆叠矩阵")}</text>
    </svg>;
  }
  if (kind === "encoder" || kind === "decoder") {
    const first = kind === "encoder" ? "Q / K / V" : "Self / Cross";
    return <svg className="structure-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} ${tx("module structure", "模块结构")}`}>
      <g className="module-flow">
        <rect x="8" y="39" width="57" height="36" /><text x="36" y="61">{first}</text>
        <path d="M65 57H84" /><path d="m79 52 6 5-6 5" />
        <rect x="85" y="32" width="72" height="50" /><text x="121" y="53">{tx("Attention", "注意力")}</text><text x="121" y="69">{tx("context", "上下文")}</text>
        <path d="M157 57H176" /><path d="m171 52 6 5-6 5" />
        <rect x="177" y="39" width="74" height="36" /><text x="214" y="53">{tx("Add", "相加")}</text><text x="214" y="68">{tx("Norm", "归一化")}</text>
      </g>
      <text className="glyph-title" x="8" y="108">{count} {tx("executable operations", "个可执行操作")}</text>
    </svg>;
  }
  if (kind === "ffn") {
    return <svg className="structure-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} ${tx("feed-forward structure", "前馈结构")}`}>
      <g className="module-flow ffn-flow">
        <rect x="13" y="40" width="45" height="34" /><text x="35" y="61">D</text>
        <path d="M58 57H84" /><path d="m79 52 6 5-6 5" />
        <rect x="85" y="25" width="78" height="64" /><text x="124" y="54">4D</text><text x="124" y="71">{tx("activation", "激活")}</text>
        <path d="M163 57H189" /><path d="m184 52 6 5-6 5" />
        <rect x="190" y="40" width="45" height="34" /><text x="212" y="61">D</text>
      </g>
      <text className="glyph-title" x="13" y="108">{tx("expand · transform · project", "扩展 · 变换 · 投影")}</text>
    </svg>;
  }
  if (kind === "norm") {
    return <svg className="structure-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} ${tx("normalization structure", "归一化结构")}`}>
      <g className="module-flow">
        <rect x="13" y="40" width="58" height="34" /><text x="42" y="61">{tx("input", "输入")}</text>
        <path d="M71 57H96" /><path d="m91 52 6 5-6 5" />
        <circle cx="130" cy="57" r="29" /><text x="130" y="53">μ · σ</text><text x="130" y="68">γ · β</text>
        <path d="M159 57H184" /><path d="m179 52 6 5-6 5" />
        <rect x="185" y="40" width="62" height="34" /><text x="216" y="61">{tx("normalized", "已归一化")}</text>
      </g>
      <text className="glyph-title" x="13" y="108">{tx("feature-wise normalization", "按特征归一化")}</text>
    </svg>;
  }
  if (kind === "attention") {
    return <svg className="structure-glyph attention-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} attention structure`}>
      <g className="glyph-flow">
        <rect x="8" y="18" width="37" height="22" /><text x="26" y="32">Q</text>
        <rect x="8" y="47" width="37" height="22" /><text x="26" y="61">K</text>
        <rect x="8" y="76" width="37" height="22" /><text x="26" y="90">V</text>
        <path d="M45 29H66M45 58H66M45 87H66" /><path d="m61 24 6 5-6 5M61 53 67 58 61 63M61 82 67 87 61 92" />
        <rect className="attention-score" x="69" y="39" width="46" height="46" />
        {[81, 93, 105].map((x) => <line key={`sx-${x}`} x1={x} y1="39" x2={x} y2="85" />)}
        {[51, 63, 75].map((y) => <line key={`sy-${y}`} x1="69" y1={y} x2="115" y2={y} />)}
        <text x="92" y="94">QKᵀ</text>
        <path d="M115 62H132" /><path d="m127 57 6 5-6 5" />
        <rect x="135" y="45" width="42" height="34" /><text x="156" y="59">softmax</text><text x="156" y="71">A</text>
        <path d="M177 62H194" /><path d="m189 57 6 5-6 5" />
        <rect x="197" y="45" width="46" height="34" /><text x="220" y="59">A V</text><text x="220" y="71">context</text>
      </g>
      <text className="glyph-title" x="8" y="112">multi-head attention · {count} ops</text>
    </svg>;
  }
  if (kind === "residual") {
    return <svg className="structure-glyph residual-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} residual structure`}>
      <g className="glyph-flow">
        <rect x="10" y="45" width="38" height="28" /><text x="29" y="62">x</text>
        <path d="M48 59H74" /><path d="m68 54 6 5-6 5" />
        <rect x="77" y="43" width="59" height="32" /><text x="106" y="57">F(x)</text><text x="106" y="69">block</text>
        <path d="M136 59H166" /><path d="m160 54 6 5-6 5" />
        <circle cx="184" cy="59" r="17" /><text x="184" y="64">+</text>
        <path className="skip-path" d="M29 45V19H184V42" /><path d="m179 37 5 6 5-6" />
        <path d="M201 59H247" /><path d="m241 54 6 5-6 5" /><text x="224" y="50">y</text>
      </g>
      <text className="glyph-title" x="10" y="108">identity skip + transform</text>
    </svg>;
  }
  if (kind === "convolution") {
    return <svg className="structure-glyph convolution-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} convolution structure`}>
      <g className="glyph-flow">
        <rect className="feature-grid" x="10" y="27" width="58" height="58" />
        {[24, 38, 52].map((x) => <line key={`ix-${x}`} x1={x} y1="27" x2={x} y2="85" />)}
        {[41, 55, 69].map((y) => <line key={`iy-${y}`} x1="10" y1={y} x2="68" y2={y} />)}
        <rect className="kernel" x="24" y="41" width="28" height="28" /><text x="38" y="57">K</text>
        <path d="M68 56H88" /><path d="m82 51 6 5-6 5" />
        <rect x="92" y="39" width="61" height="35" /><text x="123" y="53">∑ wᵢxᵢ</text><text x="123" y="66">+ bias</text>
        <path d="M153 56H173" /><path d="m167 51 6 5-6 5" />
        <rect className="feature-grid output-grid" x="177" y="34" width="65" height="45" />
        {[199, 221].map((x) => <line key={`ox-${x}`} x1={x} y1="34" x2={x} y2="79" />)}
        {[49, 64].map((y) => <line key={`oy-${y}`} x1="177" y1={y} x2="242" y2={y} />)}
      </g>
      <text className="glyph-title" x="10" y="108">sliding kernel · feature map</text>
    </svg>;
  }
  if (kind === "pooling") {
    return <svg className="structure-glyph pooling-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} pooling structure`}>
      <g className="glyph-flow">
        <rect className="feature-grid" x="10" y="26" width="70" height="62" />
        {[27, 44, 61].map((x) => <line key={`px-${x}`} x1={x} y1="26" x2={x} y2="88" />)}
        {[41, 57, 73].map((y) => <line key={`py-${y}`} x1="10" y1={y} x2="80" y2={y} />)}
        <rect className="pool-window" x="27" y="41" width="34" height="32" /><text x="44" y="60">max</text>
        <path d="M80 57H109" /><path d="m103 52 6 5-6 5" />
        <circle cx="137" cy="57" r="24" /><text x="137" y="53">max</text><text x="137" y="67">mean</text>
        <path d="M161 57H188" /><path d="m182 52 6 5-6 5" />
        <rect x="192" y="39" width="52" height="36" /><text x="218" y="55">H/2 ×</text><text x="218" y="68">W/2</text>
      </g>
      <text className="glyph-title" x="10" y="108">spatial aggregation</text>
    </svg>;
  }
  if (kind === "recurrent") {
    return <svg className="structure-glyph recurrent-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} recurrent structure`}>
      <g className="glyph-flow">
        <rect x="20" y="43" width="43" height="32" /><text x="41" y="56">cell</text><text x="41" y="68">t−1</text>
        <rect x="91" y="43" width="43" height="32" /><text x="112" y="56">cell</text><text x="112" y="68">t</text>
        <rect x="162" y="43" width="43" height="32" /><text x="183" y="56">cell</text><text x="183" y="68">t+1</text>
        <path d="M63 59H91M134 59H162" /><path d="m85 54 6 5-6 5M156 54 162 59 156 64" />
        <path className="state-loop" d="M41 43V20H183V43" /><path d="m177 37 6 6 6-6" /><text x="112" y="17">hidden state hₜ</text>
        <path d="M41 75V91M112 75V91M183 75V91" /><text x="41" y="103">xₜ₋₁</text><text x="112" y="103">xₜ</text><text x="183" y="103">xₜ₊₁</text>
      </g>
      <text className="glyph-title" x="210" y="112">time</text>
    </svg>;
  }
  if (kind === "graph") {
    return <svg className="structure-glyph graph-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} graph structure`}>
      <g className="graph-links">
        <line x1="40" y1="34" x2="104" y2="57" /><line x1="40" y1="83" x2="104" y2="57" /><line x1="104" y1="57" x2="166" y2="31" /><line x1="104" y1="57" x2="166" y2="84" /><line x1="166" y1="31" x2="222" y2="57" /><line x1="166" y1="84" x2="222" y2="57" />
      </g>
      <g className="graph-nodes"><circle cx="40" cy="34" r="13" /><circle cx="40" cy="83" r="13" /><circle className="graph-center" cx="104" cy="57" r="17" /><circle cx="166" cy="31" r="13" /><circle cx="166" cy="84" r="13" /><circle cx="222" cy="57" r="13" /></g>
      <text x="104" y="61">Σ</text><text className="glyph-title" x="10" y="108">neighbor message passing</text>
    </svg>;
  }
  if (kind === "moe") {
    return <svg className="structure-glyph moe-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} mixture of experts structure`}>
      <g className="glyph-flow">
        <rect x="10" y="43" width="38" height="30" /><text x="29" y="62">x</text>
        <path d="M48 58H68M68 58V28H88M68 58V58H88M68 58V88H88" /><path d="m82 23 6 5-6 5M82 53 88 58 82 63M82 83 88 88 82 93" />
        <rect className="router" x="88" y="43" width="42" height="30" /><text x="109" y="56">router</text><text x="109" y="67">gate</text>
        <path d="M130 58H143M143 58V27H153M143 58V58H153M143 58V89H153" /><path d="m147 22 6 5-6 5M147 53 153 58 147 63M147 84 153 89 147 94" />
        <rect x="153" y="16" width="42" height="22" /><text x="174" y="30">E1</text><rect x="153" y="47" width="42" height="22" /><text x="174" y="61">E2</text><rect x="153" y="78" width="42" height="22" /><text x="174" y="92">E3</text>
        <path d="M195 27H213V58M195 58H213M195 89H213V58M213 58H244" /><path d="m238 53 6 5-6 5" /><text x="226" y="51">weighted sum</text>
      </g>
      <text className="glyph-title" x="10" y="112">sparse expert routing</text>
    </svg>;
  }
  if (kind === "diffusion") {
    return <svg className="structure-glyph diffusion-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} diffusion structure`}>
      <g className="glyph-flow">
        <rect x="8" y="43" width="42" height="30" /><text x="29" y="62">x₀</text>
        <path d="M50 58H66" /><path d="m60 53 6 5-6 5" /><circle cx="83" cy="58" r="17" /><text x="83" y="55">+ ε</text><text x="83" y="68">noise</text>
        <path d="M100 58H116" /><path d="m110 53 6 5-6 5" /><rect x="119" y="43" width="39" height="30" /><text x="138" y="56">xₜ</text><text x="138" y="68">t</text>
        <path d="M158 58H176" /><path d="m170 53 6 5-6 5" /><rect x="179" y="35" width="44" height="46" /><text x="201" y="54">εθ</text><text x="201" y="67">denoise</text>
        <path d="M223 58H247" /><path d="m241 53 6 5-6 5" /><text x="225" y="96">x̂₀</text>
      </g>
      <path className="time-axis" d="M17 19H242" /><path d="m236 14 6 5-6 5" /><text x="17" y="13">forward noise</text><text x="207" y="13">reverse t→0</text>
    </svg>;
  }
  if (kind === "state-space") {
    return <svg className="structure-glyph state-space-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} state space structure`}>
      <g className="glyph-flow">
        <rect x="10" y="45" width="40" height="28" /><text x="30" y="62">uₜ</text>
        <path d="M50 59H73" /><path d="m67 54 6 5-6 5" /><rect x="76" y="39" width="64" height="40" /><text x="108" y="54">ΔA + B</text><text x="108" y="68">state xₜ</text>
        <path d="M140 59H164" /><path d="m158 54 6 5-6 5" /><rect x="167" y="45" width="39" height="28" /><text x="186" y="62">C xₜ</text>
        <path d="M108 39V20H220V59H206" /><path d="m200 54 6 5-6 5" /><text x="145" y="17">selective scan / memory</text>
        <path d="M206 59H247" /><path d="m241 54 6 5-6 5" /><text x="225" y="84">yₜ</text>
      </g>
      <text className="glyph-title" x="10" y="108">continuous state update</text>
    </svg>;
  }
  if (kind === "embedding") {
    return <svg className="structure-glyph embedding-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} embedding structure`}>
      <g className="glyph-flow">
        <rect x="10" y="45" width="45" height="28" /><text x="32" y="62">token id</text>
        <path d="M55 59H74" /><path d="m68 54 6 5-6 5" />
        <rect className="lookup-table" x="78" y="20" width="65" height="78" />
        {[40, 60, 80].map((y) => <line key={y} x1="78" y1={y} x2="143" y2={y} />)}
        {[94, 110, 126].map((x) => <line key={x} x1={x} y1="20" x2={x} y2="98" />)}
        <text x="111" y="112">lookup table</text>
        <path d="M143 59H164" /><path d="m158 54 6 5-6 5" /><rect x="168" y="45" width="76" height="28" /><text x="206" y="62">vector eᵢ</text>
      </g>
      <text className="glyph-title" x="10" y="14">token / positional embedding</text>
    </svg>;
  }
  if (kind === "activation") {
    return <svg className="structure-glyph activation-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} activation structure`}>
      <g className="activation-plot"><path d="M28 91H238M50 104V15" /><path className="activation-curve" d="M51 90C74 90 85 88 101 78S122 50 137 42 163 31 186 28 218 25 236 24" /><path className="activation-relu" d="M51 90H130L236 24" /></g>
      <text x="219" y="101">x</text><text x="39" y="22">f(x)</text><text className="glyph-title" x="10" y="115">non-linear activation</text>
    </svg>;
  }
  if (kind === "dropout") {
    return <svg className="structure-glyph dropout-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} dropout structure`}>
      <g className="dropout-nodes">
        {[28, 53, 78].map((x, index) => <circle key={`di-${x}`} cx={x} cy="45" r="9" className={index === 1 ? "masked" : "kept"} />)}
        {[28, 53, 78].map((x, index) => <circle key={`do-${x}`} cx={x + 151} cy="45" r="9" className={index === 1 ? "masked" : "kept"} />)}
      </g>
      <path d="M87 45H112" /><path d="m106 40 6 5-6 5" /><rect className="mask-box" x="116" y="27" width="38" height="36" /><text x="135" y="42">mask</text><text x="135" y="55">p=0.1</text>
      <path d="M28 54V78H179V54" /><path d="m173 49 6 5-6 5" /><text className="glyph-title" x="10" y="108">stochastic feature masking</text>
    </svg>;
  }
  return <svg className="structure-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} ${tx("contained structure", "包含结构")}`}>
    <g className="generic-glyph">
      <rect x="12" y="20" width="236" height="78" />
      {Array.from({ length: Math.min(5, Math.max(1, count)) }, (_, index) => {
        const x = 29 + index * 43;
        return <g key={x}><circle cx={x} cy="59" r="12" />{index > 0 && <line x1={x - 31} y1="59" x2={x - 12} y2="59" />}</g>;
      })}
    </g>
    <text className="glyph-title" x="12" y="112">{count} {tx("contained operations", "个包含操作")}</text>
  </svg>;
}

function StructureInspector({ label, viewNode, sceneNode, nodes, tensors, evidence }: {
  label: string;
  viewNode: PublicationNode;
  sceneNode: SceneNode;
  nodes: ArchitectureNodeView[];
  tensors: ArchitectureTensor[];
  evidence: Evidence[];
}) {
  const { tx } = useLanguage();
  const nodeIds = new Set(nodes.map((node) => node.node_id));
  const relevant = tensors.filter((tensor) =>
    nodeIds.has(tensor.producer_id) || tensor.consumer_ids.some((id) => nodeIds.has(id)),
  );
  const nodeOrder = new Map(nodes.map((node, index) => [node.node_id, index]));
  const orderedTensors = [...relevant].sort((left, right) => {
    const leftRank = nodeIds.has(left.producer_id) ? (nodeOrder.get(left.producer_id) ?? 0) + 1 : 0;
    const rightRank = nodeIds.has(right.producer_id) ? (nodeOrder.get(right.producer_id) ?? 0) + 1 : 0;
    return leftRank - rightRank || left.tensor_id.localeCompare(right.tensor_id);
  });
  const shapeStages = orderedTensors.filter(
    (tensor, index, all) => all.findIndex((item) => item.role === tensor.role && item.symbolic_shape === tensor.symbolic_shape) === index,
  ).slice(0, 6);
  const opTypes = [...new Set(nodes.map((node) => String(node.attributes.op_type ?? node.kind)))];
  const kind = structureKind(label, nodes);
  const primaryTensor = [...shapeStages].sort(
    (left, right) => right.semantic_axes.length - left.semantic_axes.length,
  )[0];
  return <div className="structure-inspector">
    <header className="inspector-heading"><div><h2>{label}</h2><span>{kind === "tensor" ? tx("Tensor transformation", "张量变换") : tx("Module structure", "模块结构")}</span></div><b>{nodes.length} {tx("ops", "个操作")}</b></header>
    <div className={`structure-preview preview-${kind}`}><StructureGlyph kind={kind} label={label} count={nodes.length} /></div>
    {shapeStages.length > 0 && <section className="shape-flow"><div className="section-heading">{tx("Tensor shape flow", "张量形状流")}</div><div className="shape-track">{shapeStages.map((tensor, index) => <React.Fragment key={tensor.tensor_id}>{index > 0 && <span className="shape-arrow">→</span>}<div className="shape-step"><strong>{tensor.role}</strong><code>{tensor.symbolic_shape.replaceAll(",", " × ").replace("[", "").replace("]", "")}</code></div></React.Fragment>)}</div></section>}
    {primaryTensor?.semantic_axes.length ? <div className="axis-legend">{primaryTensor.semantic_axes.map((axis, index) => <span key={axis}><b>{primaryTensor.symbolic_shape.replace(/[\[\]]/g, "").split(",")[index] ?? `d${index + 1}`}</b>{axis.replaceAll("_", " ")}</span>)}</div> : null}
    <section className="operation-summary"><div className="section-heading">{tx("Contained operations", "包含的操作")}</div><div className="operation-chips">{opTypes.slice(0, 8).map((item) => <span key={item}>{item}</span>)}</div></section>
    <div className="status-row"><span>Exact IR</span><b>{nodes.length} {tx("canonical", "个规范节点")}</b></div>
    <Field label={tx("Source symbols", "源码符号")} value={[...new Set(nodes.map((node) => node.source_symbol).filter(Boolean))].join(", ") || tx("Structural container", "结构容器")} />
    <Field label={tx("Evidence", "证据")} value={`${evidence.length} ${tx("records", "条记录")} · ${evidence[0]?.confidence ?? "exact"}`} mono />
    <div className="resolution"><div className="section-label">{tx("Resolution", "解析状态")}</div><dl><dt>{tx("Implementation", "实现")}</dt><dd>{viewNode.attributes.resolution ? tx("resolved", "已解析") : tx("exact", "精确")}</dd><dt>{tx("Semantics", "语义")}</dt><dd>{viewNode.collapsed ? tx("grouped", "已分组") : tx("expanded", "已展开")}</dd><dt>{tx("Execution", "执行")}</dt><dd>{sceneNode.canonical_node_ids.length ? tx("authored", "源码定义") : tx("structural", "结构生成")}</dd></dl></div>
  </div>;
}

function SourceInspector({ nodes, evidence }: { nodes: ArchitectureNodeView[]; evidence: Evidence[] }) {
  const { tx } = useLanguage();
  const sourceEvidence = useMemo(
    () => evidence.filter((record) => record.kind === "source" && record.path && record.span),
    [evidence],
  );
  const sourceKey = sourceEvidence.map((record) => record.evidence_id).join("|");
  const [activeEvidenceId, setActiveEvidenceId] = useState(sourceEvidence[0]?.evidence_id ?? "");
  const [excerpt, setExcerpt] = useState<SourceExcerpt | null>(null);
  const [sourceError, setSourceError] = useState("");
  useEffect(() => {
    setActiveEvidenceId(sourceEvidence[0]?.evidence_id ?? "");
  }, [sourceKey]);
  const activeEvidence = sourceEvidence.find((record) => record.evidence_id === activeEvidenceId) ?? sourceEvidence[0];
  useEffect(() => {
    if (!activeEvidence?.path || !activeEvidence.span) {
      setExcerpt(null);
      return;
    }
    const controller = new AbortController();
    setSourceError("");
    fetch(`/api/source-excerpt?path=${encodeURIComponent(activeEvidence.path)}&start=${activeEvidence.span.start_line}&end=${activeEvidence.span.end_line}&context=4`, { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error((await response.json() as { error?: string }).error ?? tx("Source excerpt unavailable", "源码片段不可用"));
        return response.json() as Promise<SourceExcerpt>;
      })
      .then(setExcerpt)
      .catch((error) => { if (!controller.signal.aborted) setSourceError(String(error)); });
    return () => controller.abort();
  }, [activeEvidence?.evidence_id]);

  const paths = [...new Set(sourceEvidence.map((record) => record.path).filter((path): path is string => Boolean(path)))];
  return <div className="source-inspector">
    <header className="inspector-heading"><div><h2>{tx("Source structure", "源码结构")}</h2><span>{paths.length} {tx("files", "个文件")} · {nodes.length} {tx("operations", "个操作")}</span></div><FileCode2 size={17} /></header>
    <section className="source-outline"><div className="section-heading">{tx("Containment", "包含关系")}</div>{paths.map((path) => {
      const pathEvidence = sourceEvidence.filter((record) => record.path === path);
      const symbols = [...new Set(pathEvidence.map((record) => record.symbol).filter((symbol): symbol is string => Boolean(symbol)))];
      return <div className="source-file" key={path}><div className="source-file-row"><FileCode2 size={13} /><strong>{path}</strong></div>{symbols.map((symbol) => {
        const symbolEvidenceIds = new Set(pathEvidence.filter((record) => record.symbol === symbol).map((record) => record.evidence_id));
        const symbolNodes = nodes.filter((node) => node.evidence_ids.some((id) => symbolEvidenceIds.has(id)));
        return <div className="source-symbol" key={symbol}><div><Braces size={12} /><b>{symbol}</b></div><div className="source-node-list">{symbolNodes.map((node) => <span key={node.node_id}><CircleDot size={8} />{node.semantic_name}</span>)}</div></div>;
      })}</div>;
    })}</section>
    {sourceEvidence.length > 0 ? <>
      <section className="source-locations"><div className="section-heading">{tx("Evidence locations", "证据位置")}</div>{sourceEvidence.slice(0, 20).map((record) => <button key={record.evidence_id} className={record.evidence_id === activeEvidence?.evidence_id ? "active" : ""} onClick={() => setActiveEvidenceId(record.evidence_id)}><code>{record.path}:{record.span?.start_line}</code><span>{record.symbol}</span></button>)}</section>
      <section className="code-excerpt"><div className="code-header"><span>{excerpt?.path ?? activeEvidence?.path}</span><code>{activeEvidence?.symbol}</code></div>{sourceError ? <div className="source-error">{sourceError}</div> : excerpt ? <pre>{excerpt.lines.map((line) => <div key={line.number} className={line.number >= excerpt.highlight_start_line && line.number <= excerpt.highlight_end_line ? "highlight" : ""}><span>{line.number}</span><code>{line.text || " "}</code></div>)}</pre> : <div className="source-loading">{tx("Loading source...", "正在加载源码...")}</div>}</section>
    </> : <div className="empty-state"><FileCode2 size={20} /><span>{tx("No source evidence", "没有源码证据")}</span></div>}
  </div>;
}

function displayValue(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

function parseValue(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function ModelInspector({ node, nodes, transaction, proposal, writebackBlocked, deleteIntentActive, deleteImpactLoading, onPrepareParameter, onPrepareStructural, onProposeConnection, onReviewDelete, onCommit, onDiscard }: {
  node?: StudioState["architecture"]["nodes"][number];
  nodes: StudioState["architecture"]["nodes"];
  transaction: SourceTransaction | null;
  proposal: AgentProposal | null;
  writebackBlocked: boolean;
  deleteIntentActive: boolean;
  deleteImpactLoading: boolean;
  onPrepareParameter: (parameterName: string, newValue: unknown) => Promise<void>;
  onPrepareStructural: (operation: string, parameters: Record<string, unknown>) => Promise<void>;
  onProposeConnection: (sourcePortId: string, targetNodeId: string, targetPortId: string) => Promise<void>;
  onReviewDelete: (nodeId: string) => Promise<void>;
  onCommit: () => Promise<void>;
  onDiscard: () => Promise<void>;
}) {
  const { tx } = useLanguage();
  const parameters = node?.parameters ?? [];
  const parameterRequest = transaction?.request.operation === "set_parameter" ? transaction.request : null;
  const activeForNode = Boolean(transaction && transaction.request.target_node_id === node?.node_id);
  const initialName = activeForNode && parameterRequest ? parameterRequest.parameter_name : parameters[0]?.name;
  const [name, setName] = useState(initialName ?? "");
  const parameter = parameters.find((item) => item.name === name) ?? parameters[0];
  const [value, setValue] = useState(
    activeForNode && parameterRequest ? displayValue(parameterRequest.new_value) : parameter ? displayValue(parameter.value) : "",
  );
  const currentActivation = String(node?.attributes.op_type ?? "").replace("nn.", "");
  const [replacement, setReplacement] = useState(currentActivation === "ReLU" ? "GELU" : "ReLU");
  const [moduleName, setModuleName] = useState(`${String(node?.attributes.module_path ?? "layer").replace("self.", "")}_norm`);
  const [normalizedShape, setNormalizedShape] = useState("d_model");
  const targetOptions = nodes.filter((item) => item.node_id !== node?.node_id && item.input_ports.length);
  const [targetNodeId, setTargetNodeId] = useState(targetOptions[0]?.node_id ?? "");
  const targetNode = targetOptions.find((item) => item.node_id === targetNodeId) ?? targetOptions[0];
  const [sourcePortId, setSourcePortId] = useState(node?.output_ports[0]?.port_id ?? "");
  const [targetPortId, setTargetPortId] = useState(targetNode?.input_ports[0]?.port_id ?? "");
  useEffect(() => {
    const transactionName = parameterRequest?.parameter_name;
    const transactionParameter = parameterRequest?.target_node_id === node?.node_id && transactionName
      ? node?.parameters.find((item) => item.name === transactionName)
      : undefined;
    const next = transactionParameter ?? node?.parameters[0];
    setName(next?.name ?? "");
    setValue(transactionParameter ? displayValue(parameterRequest?.new_value) : next ? displayValue(next.value) : "");
    const activation = String(node?.attributes.op_type ?? "").replace("nn.", "");
    setReplacement(activation === "ReLU" ? "GELU" : "ReLU");
    setModuleName(`${String(node?.attributes.module_path ?? "layer").replace("self.", "")}_norm`);
    setSourcePortId(node?.output_ports[0]?.port_id ?? "");
  }, [node?.node_id, transaction?.transaction_id]);
  useEffect(() => {
    if (parameter && !activeForNode) setValue(displayValue(parameter.value));
  }, [parameter?.name]);
  useEffect(() => {
    setTargetPortId(targetNode?.input_ports[0]?.port_id ?? "");
  }, [targetNode?.node_id]);
  if (!node) {
    return <div className="empty-state"><Braces size={20} /><span>{tx("No canonical node selected", "未选择规范节点")}</span></div>;
  }
  const active = transaction && transaction.request.target_node_id === node.node_id;
  const affected = active ? transaction.expected_delta.changed_nodes.length : 0;
  const transactionLocked = Boolean(transaction && !["discarded", "committed", "failed"].includes(transaction.state));
  const activationSupported = ["GELU", "ReLU", "SiLU"].includes(currentActivation);
  return <>
    <div className="transaction-banner"><GitBranch size={15} /> {tx("Safe source transaction", "安全源码事务")}</div>
    {parameter ? <section className="model-operation"><div className="section-heading">{tx("Parameter", "参数")}</div><label className="model-field"><span>{tx("Parameter", "参数")}</span><select value={parameter.name} onChange={(event) => setName(event.target.value)}>{parameters.map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}</select></label><Field label={tx("Current / provenance", "当前值 / 来源")} value={`${displayValue(parameter.value)} · ${parameter.origin}`} mono /><label className="model-field"><span>{tx("Target value", "目标值")}</span><input value={value} onChange={(event) => setValue(event.target.value)} /></label><button className="prepare-button" disabled={transactionLocked || value === displayValue(parameter.value)} onClick={() => void onPrepareParameter(parameter.name, parseValue(value))}><GitBranch size={14} /> {tx("Prepare parameter", "准备参数修改")}</button></section> : <div className="operation-unavailable">{tx("No exact editable parameter on this node.", "此节点没有可精确编辑的参数。")}</div>}
    <section className="model-operation"><div className="section-heading">{tx("Registered transforms", "已注册变换")}</div>{activationSupported && <><label className="model-field"><span>{tx("Activation", "激活函数")}</span><select value={replacement} onChange={(event) => setReplacement(event.target.value)}>{["GELU", "ReLU", "SiLU"].filter((item) => item !== currentActivation).map((item) => <option key={item}>{item}</option>)}</select></label><button className="prepare-button" disabled={transactionLocked} onClick={() => void onPrepareStructural("replace_activation", { replacement })}><GitBranch size={14} /> {tx("Replace activation", "替换激活函数")}</button></>}<label className="model-field"><span>{tx("LayerNorm module", "LayerNorm 模块")}</span><input value={moduleName} onChange={(event) => setModuleName(event.target.value)} /></label><label className="model-field"><span>{tx("Normalized shape", "归一化形状")}</span><input value={normalizedShape} onChange={(event) => setNormalizedShape(event.target.value)} /></label><button className="prepare-button" disabled={transactionLocked || !moduleName || !normalizedShape} onClick={() => void onPrepareStructural("insert_layer_norm", { module_name: moduleName, normalized_shape: parseValue(normalizedShape) })}><GitBranch size={14} /> {tx("Insert LayerNorm", "插入 LayerNorm")}</button></section>
    <section className="model-operation"><div className="section-heading">{tx("Proposed connection", "连接提议")}</div>{node.output_ports.length && targetNode ? <><label className="model-field"><span>{tx("Source output", "源输出")}</span><select value={sourcePortId} onChange={(event) => setSourcePortId(event.target.value)}>{node.output_ports.map((port) => <option key={port.port_id} value={port.port_id}>{port.role} · {port.port_id}</option>)}</select></label><label className="model-field"><span>{tx("Target node", "目标节点")}</span><select value={targetNode.node_id} onChange={(event) => setTargetNodeId(event.target.value)}>{targetOptions.map((item) => <option key={item.node_id} value={item.node_id}>{item.semantic_name}</option>)}</select></label><label className="model-field"><span>{tx("Target input", "目标输入")}</span><select value={targetPortId} onChange={(event) => setTargetPortId(event.target.value)}>{targetNode.input_ports.map((port) => <option key={port.port_id} value={port.port_id}>{port.role} · {port.port_id}</option>)}</select></label><button className="prepare-button" onClick={() => void onProposeConnection(sourcePortId, targetNode.node_id, targetPortId)}><Link2 size={14} /> {tx("Create handoff", "创建交接")}</button></> : <div className="operation-unavailable">{tx("Select a node with an authored output port.", "请选择带源码定义输出端口的节点。")}</div>}</section>
    <section className="model-operation danger-zone"><div className="section-heading">{tx("Canonical deletion", "规范节点删除")}</div><p>{tx("Review graph impact before creating a typed delete intent.", "创建类型化删除意图前先审查图影响。")}</p><button className="prepare-button danger-action" disabled={deleteIntentActive || deleteImpactLoading} onClick={() => void onReviewDelete(node.node_id)}><Trash2 size={14} /> {deleteIntentActive ? tx("Delete intent pending", "删除意图待处理") : deleteImpactLoading ? tx("Calculating impact", "正在计算影响") : tx("Review deletion impact", "审查删除影响")}</button></section>
    {proposal && <div className="proposal-card"><div><ShieldCheck size={15} /><strong>{tx("Agent handoff", "代理交接")}</strong><code>{proposal.reason_code}</code></div><p>{proposal.summary}</p><dl><dt>{tx("Shell", "终端")}</dt><dd>{tx("Denied", "已拒绝")}</dd><dt>{tx("Network", "网络")}</dt><dd>{tx("Denied", "已拒绝")}</dd><dt>{tx("Source write", "源码写入")}</dt><dd>{tx("Denied", "已拒绝")}</dd></dl></div>}
    <Field label={tx("Expected affected nodes / edges", "预计影响的节点 / 边")} value={active ? `${affected} / ${transaction.expected_delta.changed_edges.length}` : tx("Calculated during prepare", "在准备阶段计算")} />
    {active && <div className={`transaction-state ${transaction.state}`}>{transaction.state}</div>}
    {active && transaction.state === "review-ready" && <div className="transaction-actions"><button className="commit-button" disabled={writebackBlocked} title={writebackBlocked ? tx("Resolve draft blockers before committing", "提交前请解决草稿阻断项") : tx("Commit verified source transaction", "提交已验证的源码事务")} onClick={() => void onCommit()}><CircleDot size={14} /> {tx("Commit to source", "提交到源码")}</button><button onClick={() => void onDiscard()}><X size={14} /> {tx("Discard", "放弃")}</button></div>}
    {active && transaction.state === "failed" && <div className="transaction-actions"><span className="agent-handoff-status"><Braces size={14} /> {tx("Agent handoff is unavailable for this failed transaction", "当前失败事务不提供代理交接")}</span><button onClick={() => void onDiscard()}><X size={14} /> {tx("Discard", "放弃")}</button></div>}
  </>;
}

function deltaSummary(delta: GraphDelta | undefined, tx: LanguageContextValue["tx"]): string {
  if (!delta) return tx("Not available", "不可用");
  const nodes = delta.added_nodes.length + delta.removed_nodes.length + delta.changed_nodes.length;
  const edges = delta.added_edges.length + delta.removed_edges.length + delta.changed_edges.length;
  return `${delta.changed_parameters.length} ${tx("parameters", "个参数")} · ${nodes} ${tx("nodes", "个节点")} · ${edges} ${tx("edges", "条边")} · ${delta.changed_shapes.length} ${tx("shapes", "个形状")}`;
}

function SourceWorkspacePanel({ workspace, transaction, sessionNonce, onState, onActivity, onShowDiff }: {
  workspace: StudioState["source_workspace"];
  transaction: SourceTransaction | null;
  sessionNonce?: string;
  onState: (state: StudioState) => void;
  onActivity: (message: string) => void;
  onShowDiff: () => void;
}) {
  const { tx } = useLanguage();
  const [selectedPath, setSelectedPath] = useState("");
  const [buffer, setBuffer] = useState<SourceWorkspaceBuffer | null>(null);
  const [content, setContent] = useState("");
  const [view, setView] = useState<"editor" | "diff">("editor");
  const [busy, setBusy] = useState<"open" | "save" | "validate" | "discard-file" | "discard-all" | null>(null);
  const [error, setError] = useState("");
  const lineNumbers = useRef<HTMLPreElement>(null);
  const requestSequence = useRef(0);
  const selectedFile = workspace.files.find((file) => file.path === selectedPath);
  const transactionActive = Boolean(transaction && !["committed", "discarded", "failed"].includes(transaction.state));
  const sourceReviewReady = transaction?.request.operation === "edit_source_buffers" && transaction.state === "review-ready";
  const localDirty = Boolean(buffer && content !== buffer.staged_content);
  const modifiedCount = workspace.files.filter((file) => file.state === "modified").length;

  async function request<T>(endpoint: string, payload: object): Promise<T> {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(sessionNonce ? { "X-ArchCanvas-Nonce": sessionNonce } : {}),
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const detail = await response.text();
      try {
        const parsed = JSON.parse(detail) as { error?: string };
        throw new Error(parsed.error ?? detail);
      } catch (parseError) {
        if (parseError instanceof SyntaxError) throw new Error(detail || response.statusText);
        throw parseError;
      }
    }
    return await response.json() as T;
  }

  async function openPath(path: string) {
    if (!path) return;
    const sequence = ++requestSequence.current;
    setBusy("open");
    setError("");
    setSelectedPath(path);
    try {
      const result = await request<{ buffer: SourceWorkspaceBuffer; state: StudioState }>(
        "/api/source-workspace/open",
        { path },
      );
      if (sequence !== requestSequence.current) return;
      setBuffer(result.buffer);
      setContent(result.buffer.staged_content);
      onState({ ...result.state, session_nonce: result.state.session_nonce ?? sessionNonce });
    } catch (requestError) {
      if (sequence !== requestSequence.current) return;
      setBuffer(null);
      setError(String(requestError));
    } finally {
      if (sequence === requestSequence.current) setBusy(null);
    }
  }

  useEffect(() => {
    const initial = workspace.files.find((file) => file.opened && file.state !== "readonly")
      ?? workspace.files.find((file) => file.state !== "readonly");
    setSelectedPath(initial?.path ?? "");
    setBuffer(null);
    setContent("");
    setView("editor");
    setError("");
    if (initial) void openPath(initial.path);
  }, [workspace.workspace_id]);

  async function saveDraft(): Promise<SourceWorkspaceBuffer | null> {
    if (!buffer || !localDirty) return buffer;
    setBusy("save");
    setError("");
    try {
      const result = await request<{ buffer: SourceWorkspaceBuffer; state: StudioState }>(
        "/api/source-workspace/save",
        {
          path: buffer.path,
          content,
          base_sha256: buffer.base_sha256,
          expected_revision: workspace.revision,
        },
      );
      setBuffer(result.buffer);
      setContent(result.buffer.staged_content);
      onState({ ...result.state, session_nonce: result.state.session_nonce ?? sessionNonce });
      onActivity(`${tx("Saved source draft", "已保存源码草稿")} · ${buffer.path}`);
      return result.buffer;
    } catch (requestError) {
      setError(String(requestError));
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function validateChanges() {
    if (sourceReviewReady) {
      onShowDiff();
      return;
    }
    if (localDirty && !await saveDraft()) return;
    setBusy("validate");
    setError("");
    try {
      const state = await request<StudioState>("/api/source-workspace/validate", {});
      onState(state);
      onActivity(tx("Source workspace passed validation and is ready for review", "源码工作区已通过验证，可以审查"));
      onShowDiff();
    } catch (requestError) {
      setError(String(requestError));
    } finally {
      setBusy(null);
    }
  }

  async function discardFile() {
    if (!buffer) return;
    setBusy("discard-file");
    setError("");
    try {
      const state = await request<StudioState>("/api/source-workspace/buffer/discard", {
        path: buffer.path,
        expected_revision: workspace.revision,
      });
      onState(state);
      onActivity(`${tx("Discarded source draft", "已丢弃源码草稿")} · ${buffer.path}`);
      setBuffer(null);
      setContent("");
    } catch (requestError) {
      setError(String(requestError));
    } finally {
      setBusy(null);
    }
  }

  async function discardWorkspace() {
    setBusy("discard-all");
    setError("");
    try {
      const state = await request<StudioState>("/api/source-workspace/discard", {});
      onState(state);
      onActivity(tx("Discarded all staged source changes", "已丢弃全部暂存源码修改"));
      setBuffer(null);
      setContent("");
    } catch (requestError) {
      setError(String(requestError));
    } finally {
      setBusy(null);
    }
  }

  const shortHash = (value: string | null) => value ? value.slice(0, 12) : tx("Unavailable", "不可用");
  const stateLabel = (state: SourceWorkspaceFile["state"]) => ({
    clean: tx("Clean", "干净"),
    modified: tx("Modified", "已修改"),
    stale: tx("Stale", "已过期"),
    readonly: tx("Read only", "只读"),
  })[state];
  const lineCount = Math.max(1, content.split("\n").length);

  return <div className="source-workspace">
    <aside className="source-workspace-files">
      <header><strong>{tx("Snapshot files", "快照文件")}</strong><span className={`source-workspace-state ${workspace.state}`}>{workspace.state}</span></header>
      <div className="source-file-list">
        {workspace.files.map((file) => <button key={file.path} className={`${file.path === selectedPath ? "active" : ""} ${file.state}`} title={file.readonly_reason ?? file.path} onClick={() => { setBuffer(null); setContent(""); void openPath(file.path); }} disabled={busy !== null || file.state === "readonly"}>
          <FileCode2 size={13} /><span>{file.path}</span><b>{stateLabel(file.state)}</b>
        </button>)}
      </div>
      <footer><span>{workspace.files.length} {tx("files", "个文件")} · {modifiedCount} {tx("modified", "个已修改")}</span><button disabled={busy !== null || (!modifiedCount && !transactionActive)} onClick={() => void discardWorkspace()}><Trash2 size={13} />{tx("Discard all", "全部丢弃")}</button></footer>
    </aside>
    <section className="source-workspace-editor">
      <header className="source-editor-toolbar">
        <div><strong>{selectedPath || tx("No source file", "没有源码文件")}</strong>{selectedFile && <span>{selectedFile.size.toLocaleString()} B</span>}</div>
        <div className="source-view-switch"><button className={view === "editor" ? "active" : ""} onClick={() => setView("editor")}>{tx("Editor", "编辑器")}</button><button className={view === "diff" ? "active" : ""} onClick={() => setView("diff")}>{tx("Staged diff", "暂存差异")}</button></div>
        <button className="source-action" disabled={!buffer || !localDirty || busy !== null || transactionActive || buffer?.state === "stale"} onClick={() => void saveDraft()}><Save size={13} />{tx("Save draft", "保存草稿")}</button>
        <button className="source-action primary" disabled={busy !== null || workspace.state === "stale" || (!modifiedCount && !localDirty && !sourceReviewReady) || (transactionActive && !sourceReviewReady)} onClick={() => void validateChanges()}><ShieldCheck size={13} />{sourceReviewReady ? tx("Review changes", "审查修改") : busy === "validate" ? tx("Validating", "正在验证") : tx("Validate changes", "验证修改")}</button>
        <button className="icon-button" title={tx("Discard selected buffer", "丢弃所选缓冲区")} aria-label={tx("Discard selected buffer", "丢弃所选缓冲区")} disabled={!buffer || busy !== null} onClick={() => void discardFile()}><X size={13} /></button>
      </header>
      {error && <div className="source-workspace-error"><AlertTriangle size={13} />{error}</div>}
      {buffer ? <>
        <div className="source-hashes"><span>Base <code title={buffer.base_sha256}>{shortHash(buffer.base_sha256)}</code></span><span>Staged <code title={buffer.staged_sha256}>{shortHash(buffer.staged_sha256)}</code></span><span>Working <code title={buffer.working_sha256}>{shortHash(buffer.working_sha256)}</code></span><b className={buffer.state}>{buffer.state}</b></div>
        {view === "editor" ? <div className="source-code-editor"><pre ref={lineNumbers} aria-hidden="true">{Array.from({ length: lineCount }, (_, index) => index + 1).join("\n")}</pre><textarea aria-label={tx("Staged source content", "暂存源码内容")} spellCheck={false} wrap="off" value={content} readOnly={transactionActive || buffer.state === "stale"} onScroll={(event) => { if (lineNumbers.current) lineNumbers.current.scrollTop = event.currentTarget.scrollTop; }} onChange={(event) => setContent(event.target.value)} /></div> : <pre className="source-staged-diff">{buffer.diff || tx("No staged textual changes", "没有暂存文本修改")}</pre>}
      </> : selectedFile?.state === "readonly" ? <div className="source-workspace-empty"><LockKeyhole size={18} /><span>{selectedFile.readonly_reason}</span></div> : <div className="source-workspace-empty"><FileCode2 size={18} /><span>{busy === "open" ? tx("Opening source buffer", "正在打开源码缓冲区") : tx("Buffer is closed", "缓冲区已关闭")}</span>{busy !== "open" && selectedPath && <button onClick={() => void openPath(selectedPath)}>{tx("Open file", "打开文件")}</button>}</div>}
    </section>
  </div>;
}

function TransactionReview({ transaction, writebackBlocked, onCommit, onDiscard }: { transaction: SourceTransaction; writebackBlocked: boolean; onCommit: () => Promise<void>; onDiscard: () => Promise<void> }) {
  const { tx } = useLanguage();
  return <div className="transaction-review">
    <section><h3>{tx("Source diff", "源码差异")}</h3><pre>{transaction.source_diff || tx("No textual change", "没有文本变化")}</pre></section>
    <section><h3>Graph Delta</h3><dl><dt>{tx("Expected", "预期")}</dt><dd>{deltaSummary(transaction.expected_delta, tx)}</dd><dt>{tx("Observed", "观测")}</dt><dd>{deltaSummary(transaction.observed_delta, tx)}</dd></dl>{transaction.expected_delta.changed_parameters.map((item) => <code key={`${item.node_id}-${item.parameter_name}`}>{item.node_id}.{item.parameter_name}: {displayValue(item.before)} → {displayValue(item.after)}</code>)}</section>
    <section><h3>{tx("Validation receipt", "验证凭据")}</h3><div className="gate-list">{transaction.gates.map((gate) => <span key={gate.gate} className={gate.status}>{gate.status} · {gate.gate}</span>)}</div><div className="review-actions">{transaction.state === "review-ready" ? <button className="commit-button" disabled={writebackBlocked} title={writebackBlocked ? tx("Resolve draft blockers before committing", "提交前请解决草稿阻断项") : tx("Commit verified source transaction", "提交已验证的源码事务")} onClick={() => void onCommit()}><CircleDot size={14} /> {tx("Commit to source", "提交到源码")}</button> : <span className="agent-handoff-status"><Braces size={14} /> {tx("No commit action until every validation gate passes", "全部验证门通过后才可提交")}</span>} {!['committed', 'discarded'].includes(transaction.state) && <button onClick={() => void onDiscard()}><X size={14} /> {tx("Discard", "放弃")}</button>}</div></section>
  </div>;
}

function VisualInspector({ node, pinned, fontScale, lineWeight, caption, legendPlacement, onPatch, onBatch }: { node: SceneNode; pinned: boolean; fontScale: number; lineWeight: number; caption: string; legendPlacement: "top-left" | "top-right" | "bottom-left" | "bottom-right" | "hidden"; onPatch: (operation: string, targetId: string | undefined, value: Record<string, unknown>) => Promise<void>; onBatch: (description: string, patches: Array<{ operation: string; targetId?: string; value: Record<string, unknown> }>) => Promise<void> }) {
  const { tx } = useLanguage();
  const [bounds, setBounds] = useState(node.bounds);
  const [label, setLabel] = useState(node.label_lines.join("\n"));
  const [captionText, setCaptionText] = useState(caption);
  const [annotationText, setAnnotationText] = useState("");
  useEffect(() => setBounds(node.bounds), [node.scene_node_id, node.bounds]);
  useEffect(() => setLabel(node.label_lines.join("\n")), [node.scene_node_id, node.label_lines]);
  useEffect(() => setCaptionText(caption), [caption]);
  const update = (key: keyof Rect, value: number) => setBounds((current) => ({ ...current, [key]: value }));
  const addAnnotation = async () => {
    const text = annotationText.trim();
    if (!text) return;
    const annotationId = patchId("annotation").replace("patch:", "annotation:");
    await onPatch("add-annotation", annotationId, { text, x: node.bounds.x, y: node.bounds.y + node.bounds.height + 12, width: 190, height: 52 });
    setAnnotationText("");
  };
  return <><div className="section-label">{tx("Geometry", "几何")}</div><div className="numeric-grid">{(["x", "y", "width", "height"] as const).map((key) => <label key={key}><span>{key.toUpperCase()}</span><input type="number" min={key === "width" || key === "height" ? 1 : 0} value={Math.round(bounds[key])} onChange={(event) => update(key, Number(event.target.value))} /></label>)}</div><button className="apply-visual" onClick={() => void onBatch(tx("Apply geometry", "应用几何设置"), [{ operation: "set-position", targetId: node.scene_node_id, value: { x: bounds.x, y: bounds.y } }, { operation: "set-size", targetId: node.scene_node_id, value: { width: bounds.width, height: bounds.height } }])}>{tx("Apply geometry", "应用几何设置")}</button><label className="toggle-row"><input type="checkbox" checked={pinned} onChange={() => void onPatch("set-pin", node.scene_node_id, { enabled: !pinned })} /><span>{tx("Pin during layout", "布局时固定")}</span></label><label className="model-field"><span>{tx("Fill", "填充色")}</span><input type="color" value={node.fill.startsWith("#") ? node.fill.slice(0, 7) : "#ffffff"} onChange={(event) => void onPatch("set-palette", undefined, { overrides: { [node.scene_node_id]: event.target.value } })} /></label><label className="model-field"><span>{tx("Stroke", "描边色")}</span><input type="color" value={node.stroke.startsWith("#") ? node.stroke.slice(0, 7) : "#1b1d1a"} onChange={(event) => void onPatch("set-palette", undefined, { overrides: { [`${node.scene_node_id}:stroke`]: event.target.value } })} /></label><label className="model-field"><span>{tx("Label lines", "标签行")}</span><textarea rows={3} value={label} onChange={(event) => setLabel(event.target.value)} /></label><button className="apply-visual" onClick={() => void onPatch("set-label-wrap", node.scene_node_id, { lines: label.split("\n").filter(Boolean).slice(0, 3) })}>{tx("Apply label wrap", "应用标签换行")}</button><label className="model-field"><span>{tx("Font scale", "字体缩放")} · {fontScale.toFixed(2)}</span><input type="range" min="0.75" max="1.5" step="0.05" value={fontScale} onChange={(event) => void onPatch("set-font-scale", undefined, { scale: Number(event.target.value) })} /></label><label className="model-field"><span>{tx("Line weight", "线宽")} · {lineWeight.toFixed(1)}</span><input type="range" min="0.5" max="5" step="0.5" value={lineWeight} onChange={(event) => void onPatch("set-line-weight", undefined, { width: Number(event.target.value) })} /></label><div className="section-label">{tx("Document", "文档")}</div><label className="model-field"><span>{tx("Caption", "图注")}</span><input value={captionText} maxLength={240} onChange={(event) => setCaptionText(event.target.value)} /></label><button className="apply-visual" onClick={() => void onPatch("set-caption", undefined, { caption: captionText })}>{tx("Apply caption", "应用图注")}</button><label className="model-field"><span>{tx("Legend placement", "图例位置")}</span><select value={legendPlacement} onChange={(event) => void onPatch("set-legend-placement", undefined, { placement: event.target.value })}><option value="top-left">{tx("Top left", "左上")}</option><option value="top-right">{tx("Top right", "右上")}</option><option value="bottom-left">{tx("Bottom left", "左下")}</option><option value="bottom-right">{tx("Bottom right", "右下")}</option><option value="hidden">{tx("Hidden", "隐藏")}</option></select></label><label className="model-field"><span>{tx("Annotation", "批注")}</span><textarea rows={2} maxLength={500} value={annotationText} onChange={(event) => setAnnotationText(event.target.value)} /></label><button className="apply-visual" disabled={!annotationText.trim()} onClick={() => void addAnnotation()}>{tx("Add annotation", "添加批注")}</button></>;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
