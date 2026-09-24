import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertTriangle,
  Box,
  Braces,
  ChevronDown,
  ChevronRight,
  CircleDot,
  CornerDownLeft,
  Download,
  Eye,
  FileCode2,
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
  Redo2,
  Search,
  ShieldCheck,
  Sun,
  Undo2,
  Variable,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";

import "./styles.css";

type Mode = "explore" | "layout" | "model";
type Projection = "module" | "source";

interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface Point {
  x: number;
  y: number;
}

interface SceneNode {
  scene_node_id: string;
  view_node_id: string;
  canonical_node_ids: string[];
  bounds: Rect;
  shape: "container" | "rect" | "merge" | "io" | "state" | "opaque";
  label_lines: string[];
  secondary_label?: string;
  fill: string;
  stroke: string;
  parent_scene_node_id?: string;
  evidence_ids: string[];
}

interface SceneEdge {
  scene_edge_id: string;
  source_scene_node_id: string;
  target_scene_node_id: string;
  points: Point[];
  edge_type: string;
  stroke: string;
  dash?: string;
  width: number;
  label: string;
}

interface Scene {
  scene_id: string;
  view_id: string;
  paper_width: number;
  paper_height: number;
  nodes: SceneNode[];
  edges: SceneEdge[];
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
    target_node_id: string;
    operation: "set_parameter" | "replace_activation" | "insert_layer_norm";
    parameter_name?: string;
    new_value?: unknown;
    parameters?: Record<string, unknown>;
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

interface StudioState {
  session_nonce?: string;
  project: {
    project_id: string;
    root: string;
    generation: number;
    framework: string;
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
    pinned_node_ids?: string[];
    collapsed_node_ids?: string[];
    theme?: string;
    cameras?: Record<string, { x: number; y: number; zoom: number }>;
    module_expansion?: string[];
    source_expansion?: string[];
    font_scale?: number;
    line_weight?: number;
    palette_overrides?: Record<string, string>;
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
    proofs: Array<{
      intent_id: string;
      status: "checking" | "conditional" | "unproven" | "invalid" | "stale" | "proven" | "review-ready";
      message: string;
      reason_codes: string[];
      affected_subject_ids: string[];
    }>;
    writeback_summary: { eligibility: "blocked" | "prepare" | "commit"; blocking_intent_ids: string[] };
  };
  validation_runs: Array<{
    validation_id: string;
    profile: string;
    state: string;
    input_fingerprint: string;
    gate_results: Array<{ gate: string; status: string; message: string }>;
    diagnostics: Diagnostic[];
  }>;
  jobs?: Array<{ job_id: string; state: string; progress: number; profile: string }>;
  diagnostics: Diagnostic[];
  transaction: SourceTransaction | null;
  proposal: AgentProposal | null;
  capabilities: {
    visual_editing: boolean;
    source_editing: boolean;
    runtime_evidence: boolean;
    semantic_transforms: string[];
    proposed_connection: boolean;
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

function visibleNavigationRows(nodes: NavigationNode[], expanded: Set<string>): NavigationNode[] {
  const visible = new Set<string>();
  return nodes.filter((item) => {
    if (item.parent_id === null) {
      visible.add(item.id);
      return true;
    }
    const shown = visible.has(item.parent_id) && expanded.has(item.parent_id);
    if (shown) visible.add(item.id);
    return shown;
  });
}

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

function nodeShape(node: SceneNode): React.ReactNode {
  const { x, y, width, height } = node.bounds;
  if (node.shape === "merge") {
    return (
      <polygon
        className="node-shape"
        points={`${x + width / 2},${y} ${x + width},${y + height / 2} ${x + width / 2},${y + height} ${x},${y + height / 2}`}
        fill={node.fill}
        stroke={node.stroke}
      />
    );
  }
  return (
    <rect
      className="node-shape"
      x={x}
      y={y}
      width={width}
      height={height}
      rx={node.shape === "io" ? 28 : node.shape === "container" ? 3 : 6}
      fill={node.fill}
      stroke={node.stroke}
      strokeDasharray={node.shape === "opaque" ? "6 4" : undefined}
    />
  );
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

function navigationRelationLabel(relation: string): string {
  return {
    "module-containment": "归属",
    "source-containment": "归属",
    invocation: "调用",
    assignment: "赋值",
    return: "返回",
    "producer-output": "产出",
    "consumer-reference": "引用",
  }[relation] ?? relation;
}

function App() {
  const [data, setData] = useState<StudioState | null>(() => embeddedState());
  const [projection, setProjection] = useState<Projection>(
    () => embeddedState()?.navigation?.active_projection ?? embeddedState()?.view_state.navigation_view ?? "module",
  );
  const [expansions, setExpansions] = useState<Record<Projection, Set<string>>>(() => expansionState(embeddedState()));
  const [mode, setMode] = useState<Mode>("explore");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [focusedNavigationRowId, setFocusedNavigationRowId] = useState<string | null>(null);
  const [inspectorTab, setInspectorTab] = useState<"inspect" | "source" | "visual" | "model" | "evidence">("inspect");
  const [bottomTab, setBottomTab] = useState<"problems" | "diff" | "validation" | "jobs" | "activity">("problems");
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [validationProfile, setValidationProfile] = useState("fast-static");
  const [projectDialog, setProjectDialog] = useState(false);
  const [projectRoot, setProjectRoot] = useState(() => embeddedState()?.project.root ?? "");
  const [pendingProject, setPendingProject] = useState<{
    project: StudioState["project"];
    discovery: { entrypoints: Array<{ entrypoint: string; framework: string }>; configs: Array<{ path: string }> };
  } | null>(null);
  const [projectEntrypoint, setProjectEntrypoint] = useState("");
  const [projectFramework, setProjectFramework] = useState("auto");
  const [projectConfig, setProjectConfig] = useState("");
  const [mobileInspector, setMobileInspector] = useState(false);
  const [dark, setDark] = useState(() => embeddedState()?.view_state.theme === "studio-dark");
  const [viewBox, setViewBox] = useState<[number, number, number, number] | null>(null);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [pan, setPan] = useState<PanState | null>(null);
  const [preview, setPreview] = useState<Record<string, Point>>({});
  const [activity, setActivity] = useState<string[]>(["Studio document opened"]);
  const svgRef = useRef<SVGSVGElement>(null);
  const selections = useRef<Record<string, string[]>>({});
  const cameraTimer = useRef<number | null>(null);
  const navigationTimer = useRef<number | null>(null);
  const navigationQueue = useRef<Promise<void>>(Promise.resolve());
  const expansionsRef = useRef(expansions);
  const navigationTouched = useRef(false);
  const previousScene = useRef<Scene | null>(null);
  const viewBoxRef = useRef<[number, number, number, number] | null>(null);
  const viewBoxAnimation = useRef<number | null>(null);
  const pendingHierarchyFocus = useRef<string | null>(null);

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
          const restored = expansionState(state);
          expansionsRef.current = restored;
          setExpansions(restored);
          setProjection(state.navigation.active_projection ?? state.view_state.navigation_view ?? "module");
        }
        setData(state);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => () => {
    if (cameraTimer.current !== null) window.clearTimeout(cameraTimer.current);
    if (navigationTimer.current !== null) window.clearTimeout(navigationTimer.current);
    if (viewBoxAnimation.current !== null) cancelAnimationFrame(viewBoxAnimation.current);
  }, []);

  const scene = activeProjectionId ? data?.scenes[activeProjectionId] : undefined;
  const view = activeProjectionId ? data?.views[activeProjectionId] : undefined;
  const camera = scene ? data?.view_state.cameras?.[scene.scene_id] : undefined;
  useEffect(() => {
    let focusedSceneNodeId: string | null = null;
    if (scene) {
      let target: [number, number, number, number] = camera
        ? [camera.x, camera.y, scene.paper_width / camera.zoom, scene.paper_height / camera.zoom]
        : [0, 0, scene.paper_width, scene.paper_height];
      const focusId = pendingHierarchyFocus.current;
      const focusViewNode = focusId
        ? view?.nodes.find((node) => node.attributes.hierarchy_node_id === focusId)
        : undefined;
      const focusNode = focusViewNode
        ? scene.nodes.find((node) => node.view_node_id === focusViewNode.view_node_id)
        : undefined;
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
        viewBoxRef.current = target;
        setViewBox(target);
      } else {
        const started = performance.now();
        const animate = (now: number) => {
          const progress = Math.min(1, (now - started) / 360);
          const eased = 1 - Math.pow(1 - progress, 3);
          const next = start.map((value, index) =>
            value + (target[index] - value) * eased,
          ) as [number, number, number, number];
          viewBoxRef.current = next;
          setViewBox(next);
          if (progress < 1) viewBoxAnimation.current = requestAnimationFrame(animate);
          else viewBoxAnimation.current = null;
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
    setPreview({});
  }, [activeProjectionId, scene?.scene_id, camera?.x, camera?.y, camera?.zoom]);

  useEffect(() => {
    viewBoxRef.current = viewBox;
  }, [viewBox]);

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
  }, [scene?.scene_id]);

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
  const pinned = new Set(data?.view_state.pinned_node_ids ?? []);
  const collapsed = new Set(data?.view_state.collapsed_node_ids ?? []);

  async function mutate(endpoint: string, payload?: object, activityLabel?: string) {
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
      const visualPatch = payload as VisualPatch | undefined;
      const label = activityLabel ?? (visualPatch?.operation ? `${visualPatch.operation} · ${visualPatch.target_id ?? "document"}` : endpoint.slice(5));
      setActivity((items) => [label, ...items].slice(0, 20));
    } catch (error) {
      setActivity((items) => [`Request failed · ${String(error)}`, ...items].slice(0, 20));
    }
  }

  function persistNavigation(
    nextProjection: Projection,
    nextExpansions: Record<Projection, Set<string>>,
    activityLabel: string,
  ) {
    if (navigationTimer.current !== null) window.clearTimeout(navigationTimer.current);
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
          setData(state);
          setActivity((items) => [activityLabel, ...items].slice(0, 20));
        })
        .catch((error) => {
          setActivity((items) => [`Navigation persistence failed · ${String(error)}`, ...items].slice(0, 20));
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
      `Prepared ${architectureNode.node_id}.${parameterName}`,
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
      `Prepared ${operation} on ${architectureNode.node_id}`,
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
      `Proposed ${architectureNode.node_id} → ${targetNodeId}`,
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
    const binding = result.view_bindings.find(
      (item) => item.projection_id === activeProjectionId,
    );
    if (binding) {
      selections.current[binding.projection_id] = [binding.scene_node_id];
      setSelectedIds([binding.scene_node_id]);
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
      if (sceneNode) choose(sceneNode.scene_node_id, false, navigationRowId);
    } else if (navigationRowId) {
      choose(null, false, navigationRowId);
    }
  }

  function switchProjection(next: Projection) {
    navigationTouched.current = true;
    setFocusedNavigationRowId(null);
    setProjection(next);
    persistNavigation(next, expansionsRef.current, `${next === "module" ? "模块关系" : "源码关系"} view`);
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
    persistNavigation(kind, nextExpansions, `Navigation ${shouldExpand ? "expanded" : "collapsed"}`);
  }

  function activateNavigationRow(item: NavigationNode) {
    const hierarchyViewNode = view?.nodes.find(
      (node) => node.attributes.hierarchy_node_id === item.id,
    );
    const hierarchySceneNode = hierarchyViewNode
      ? scene?.nodes.find((node) => node.view_node_id === hierarchyViewNode.view_node_id)
      : undefined;
    if (hierarchySceneNode) choose(hierarchySceneNode.scene_node_id, false, item.id);
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
  ) {
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

  function zoom(factor: number) {
    if (!viewBox || !scene) return;
    const [x, y, width, height] = viewBox;
    const nextWidth = width * factor;
    const nextHeight = height * factor;
    const next: [number, number, number, number] = [
      x + (width - nextWidth) / 2,
      y + (height - nextHeight) / 2,
      nextWidth,
      nextHeight,
    ];
    setViewBox(next);
    persistCamera(next, scene);
  }

  function pointerPosition(event: React.PointerEvent): Point | null {
    const svg = svgRef.current;
    if (!svg || !viewBox) return null;
    const rect = svg.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left) * (viewBox[2] / rect.width),
      y: (event.clientY - rect.top) * (viewBox[3] / rect.height),
    };
  }

  function beginDrag(event: React.PointerEvent, node: SceneNode) {
    if (!node.parent_scene_node_id) return;
    choose(node.scene_node_id, event.shiftKey);
    if (event.shiftKey) return;
    if (mode === "explore" || pinned.has(node.scene_node_id)) return;
    const point = pointerPosition(event);
    if (!point) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const movingIds = selectedIds.includes(node.scene_node_id) ? selectedIds : [node.scene_node_id];
    const baselines = Object.fromEntries(
      movingIds
        .filter((nodeId) => !pinned.has(nodeId))
        .map((nodeId) => {
          const current = scene?.nodes.find((item) => item.scene_node_id === nodeId);
          return [nodeId, current?.bounds ?? node.bounds];
        }),
    );
    setDrag({ startClient: point, baselines });
  }

  function moveDrag(event: React.PointerEvent) {
    if (!drag) return;
    const point = pointerPosition(event);
    if (!point) return;
    setPreview(Object.fromEntries(Object.entries(drag.baselines).map(([nodeId, bounds]) => [
      nodeId,
      {
        x: Math.max(0, bounds.x + point.x - drag.startClient.x),
        y: Math.max(0, bounds.y + point.y - drag.startClient.y),
      },
    ])));
  }

  function beginPan(event: React.PointerEvent<SVGSVGElement>) {
    if ((event.target as Element).closest(".scene-node:not(.root)") || !viewBox) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setPan({
      startClient: { x: event.clientX, y: event.clientY },
      startViewBox: viewBox,
    });
  }

  function movePointer(event: React.PointerEvent<SVGSVGElement>) {
    if (drag) {
      moveDrag(event);
      return;
    }
    if (!pan || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const scaleX = pan.startViewBox[2] / rect.width;
    const scaleY = pan.startViewBox[3] / rect.height;
    setViewBox([
      pan.startViewBox[0] - (event.clientX - pan.startClient.x) * scaleX,
      pan.startViewBox[1] - (event.clientY - pan.startClient.y) * scaleY,
      pan.startViewBox[2],
      pan.startViewBox[3],
    ]);
  }

  function endDrag() {
    if (!drag) return;
    const patches = Object.entries(preview).map(([nodeId, position], index) => ({
      patch_id: `${patchId("move-batch")}.${index}`,
      operation: "set-position",
      target_id: nodeId,
      value: { scene_id: scene?.scene_id, x: position.x, y: position.y },
    }));
    if (patches.length) void mutate("/api/patch-batch", {
      batch_id: patchId("drag").replace("patch:", "batch:"),
      description: `Move ${patches.length} node${patches.length === 1 ? "" : "s"}`,
      patches,
    });
    setDrag(null);
    setPreview({});
  }

  function endPointer() {
    if (drag) endDrag();
    if (pan && viewBox && scene) {
      void submit("set-camera", undefined, {
        x: viewBox[0],
        y: viewBox[1],
        zoom: scene.paper_width / viewBox[2],
      });
    }
    setPan(null);
  }

  function cancelPointer() {
    setDrag(null);
    setPan(null);
    setPreview({});
  }

  function align(command: string) {
    if (selectedIds.length < 2) return;
    void mutate("/api/align", {
      batch_id: patchId(`align-${command}`).replace("patch:", "batch:"),
      selected_ids: selectedIds,
      command,
    }, `Aligned ${selectedIds.length} nodes · ${command}`);
  }

  function runValidation() {
    void mutate("/api/validation-runs", {
      profile: validationProfile,
      runtime_execution_authorized: false,
    }, `Validated · ${validationProfile}`);
    setBottomTab("validation");
  }

  async function openProject() {
    try {
      const response = await fetch("/api/projects/open", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(data?.session_nonce ? { "X-ArchCanvas-Nonce": data.session_nonce } : {}) },
        body: JSON.stringify({ root: projectRoot }),
      });
      if (!response.ok) throw new Error(await response.text());
      const result = await response.json() as typeof pendingProject;
      if (!result) return;
      setPendingProject(result);
      const candidate = result.discovery.entrypoints[0];
      setProjectEntrypoint(candidate?.entrypoint ?? "");
      setProjectFramework(candidate?.framework === "unknown" ? "auto" : candidate?.framework ?? "auto");
      setProjectConfig(result.discovery.configs[0]?.path ?? "");
    } catch (error) {
      setActivity((items) => [`Project discovery failed · ${String(error)}`, ...items].slice(0, 20));
    }
  }

  async function analyzeProject() {
    if (!pendingProject || !projectEntrypoint || projectFramework === "auto") return;
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
      const poll = window.setInterval(async () => {
        const jobResponse = await fetch(`/api/jobs/${job.job_id}`, { cache: "no-store" });
        if (!jobResponse.ok) return;
        const current = await jobResponse.json() as { state: string; diagnostics?: Diagnostic[] };
        const stateResponse = await fetch("/api/state", { cache: "no-store" });
        if (stateResponse.ok) setData(await stateResponse.json() as StudioState);
        if (["succeeded", "failed", "cancelled", "stale"].includes(current.state)) {
          window.clearInterval(poll);
          if (current.state === "succeeded") {
            setProjectDialog(false);
            setPendingProject(null);
          }
        }
      }, 300);
    } catch (error) {
      setActivity((items) => [`Analysis start failed · ${String(error)}`, ...items].slice(0, 20));
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
    setViewBox(next);
    void submit("set-camera", undefined, { x: 0, y: 0, zoom: 1 }, scene.scene_id);
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
    persistNavigation(targetProjection, nextExpansions, `Expanded ${candidate.label}`);
  }

  if (!data || !scene || !view || !viewBox || !navigation) {
    return <div className="loading">Loading Studio…</div>;
  }

  const sourceDigest = data.document.source_digest.slice(0, 12);
  const selectedCanonical = selectedCanonicalIds[0];
  const architectureNode = data.architecture.nodes.find((node) => node.node_id === selectedCanonical);
  const breadcrumb = selectedViewNode
    ? `${data.architecture.entrypoint.split(":").at(-1)} / ${view.name} / ${selectedViewNode.semantic_name}`
    : `${data.architecture.entrypoint.split(":").at(-1)} / ${view.name}`;
  const proofRank: Record<string, number> = { invalid: 7, stale: 6, unproven: 5, conditional: 4, checking: 3, proven: 2, "review-ready": 1 };
  const proofs = data.draft.proofs;
  const proofCounts = proofs.reduce<Record<string, number>>((counts, proof) => ({ ...counts, [proof.status]: (counts[proof.status] ?? 0) + 1 }), {});
  const writebackBlocked = data.draft.writeback_summary.eligibility === "blocked" && data.draft.writeback_summary.blocking_intent_ids.length > 0;
  const latestValidation = data.validation_runs.at(-1);
  function renderSceneNode(original: SceneNode) {
    const position = preview[original.scene_node_id];
    const node = position ? { ...original, bounds: { ...original.bounds, ...position } } : original;
    const isRoot = !node.parent_scene_node_id;
    const isSelected = selectedIds.includes(node.scene_node_id);
    const publicationNode = view!.nodes.find((item) => item.view_node_id === node.view_node_id);
    const proof = proofs
      .filter((item) => item.affected_subject_ids.some((id) => node.canonical_node_ids.includes(id)))
      .sort((a, b) => proofRank[b.status] - proofRank[a.status])[0];
    return (
      <g
        key={node.scene_node_id}
        className={`scene-node ${isRoot ? "root" : ""} ${isSelected ? "selected" : ""} ${collapsed.has(node.scene_node_id) ? "collapsed" : ""} ${publicationNode?.collapsed ? "publication-collapsed" : ""} ${proof ? `proof-${proof.status}` : ""}`}
        data-scene-node-id={node.scene_node_id}
        tabIndex={isRoot ? -1 : 0}
        onPointerDown={(event) => beginDrag(event, node)}
        onClick={() => {
          if (!isRoot && mode === "explore" && publicationNode?.collapsed) expandInNavigation(node);
        }}
        onDoubleClick={() => !isRoot && publicationNode?.collapsed && expandInNavigation(node)}
        onKeyDown={(event) => { if (event.key === "Enter" && !isRoot) expandInNavigation(node); }}
      >
        {nodeShape(node)}
        {isRoot ? (
          <text className="container-label" x={node.bounds.x + 14} y={node.bounds.y + 23}>{node.label_lines.join(" ")}</text>
        ) : (
          <>
            {node.label_lines.map((line, index) => (
              <text key={line + index} className="node-label" textAnchor="middle" x={node.bounds.x + node.bounds.width / 2} y={node.bounds.y + node.bounds.height / 2 - ((node.label_lines.length - 1) * 15) / 2 + index * 15}>{line}</text>
            ))}
            {node.secondary_label && <text className="node-secondary" textAnchor="middle" x={node.bounds.x + node.bounds.width / 2} y={node.bounds.y + node.bounds.height - 14}>{node.secondary_label.slice(0, 28)}</text>}
          </>
        )}
        {isSelected && !isRoot && (
          <>
            <rect className="selection-box" x={node.bounds.x - 4} y={node.bounds.y - 4} width={node.bounds.width + 8} height={node.bounds.height + 8} />
            <circle className="port" cx={node.bounds.x} cy={node.bounds.y + node.bounds.height / 2} r={4} />
            <circle className="port" cx={node.bounds.x + node.bounds.width} cy={node.bounds.y + node.bounds.height / 2} r={4} />
          </>
        )}
        {proof && !isRoot && <g className="proof-overlay" aria-label={`${proof.status}: ${proof.message}`}><rect x={node.bounds.x - 7} y={node.bounds.y - 7} width={node.bounds.width + 14} height={node.bounds.height + 14} rx={7} /><text x={node.bounds.x + node.bounds.width - 3} y={node.bounds.y + 3}>{proof.status === "invalid" ? "×" : proof.status === "unproven" ? "?" : "!"}</text></g>}
      </g>
    );
  }

  return (
    <div className={`${dark ? "studio dark" : "studio"}${data.transaction ? " has-transaction" : ""}`}>
      <header className="topbar">
        <div className="product"><Box size={17} /> ArchCanvas</div>
        <button className="project-meta" onClick={() => setProjectDialog(true)} title="Open or switch project">
          <strong>{data.architecture.entrypoint.split(":").at(-1)}</strong>
          <span>{data.snapshot.revision}</span>
        </button>
        <div className="mode-switch" aria-label="Studio mode">
          {(["explore", "layout", "model"] as Mode[]).map((item) => (
            <button key={item} className={mode === item ? "active" : ""} onClick={() => { setMode(item); if (item === "model") setInspectorTab("model"); }}>
              {item === "explore" ? <Eye size={14} /> : item === "layout" ? <Move size={14} /> : <Braces size={14} />}
              {item[0].toUpperCase() + item.slice(1)}
            </button>
          ))}
        </div>
        <div className="top-actions">
          <button className="icon-button" title="Undo" aria-label="Undo" disabled={!data.document.visual_patches.length} onClick={() => void mutate("/api/undo")}><Undo2 /></button>
          <button className="icon-button" title="Redo" aria-label="Redo" disabled={!data.document.redo_patches.length} onClick={() => void mutate("/api/redo")}><Redo2 /></button>
          <div className={`writeback-gate ${writebackBlocked ? "blocked" : "ready"}`} title={writebackBlocked ? "Review blockers before committing" : "No draft blockers"}><ShieldCheck size={14} />{writebackBlocked ? `${proofCounts.invalid ?? 0} invalid · ${proofCounts.unproven ?? 0} unproven` : "Writeback clear"}</div>
          <select className="profile-select" aria-label="Validation profile" value={validationProfile} onChange={(event) => setValidationProfile(event.target.value)}><option value="fast-static">Fast</option><option value="publication">Publication</option><option value="full">Full</option></select>
          <button className="validate-button" onClick={runValidation}><Play size={14} /> Validate <span>{latestValidation?.diagnostics.length ?? data.diagnostics.length}</span></button>
          <a className="primary-action" href="/api/export"><Download size={14} /> Export</a>
        </div>
      </header>

      <div className="workspace">
        <aside className="left-panel panel">
          <div className="panel-title"><PanelLeft size={15} /> Model</div>
          <div className="search-wrap"><div className="search-field"><Search size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && selectSearchResult()} placeholder="Find node, tensor, port, evidence" /></div>{searchResults.length > 0 && <div className="search-results">{searchResults.slice(0, 8).map((result) => <button key={result.id} onClick={() => selectSearchResult(result)}><span>{result.title}</span><small>{result.kind}</small></button>)}</div>}</div>
          <div className="projection-switch" aria-label="Navigation projection">
            {(["module", "source"] as const).map((item) => <button key={item} className={projection === item ? "active" : ""} aria-pressed={projection === item} onClick={() => switchProjection(item)}>{item === "module" ? <Layers3 size={14} /> : <FileCode2 size={14} />}<span>{item === "module" ? "模块关系" : "源码关系"}</span></button>)}
          </div>
          <div className="section-label">{navigation.label}</div>
          <div className="projection-description">{navigation.description}</div>
          <div className="tree-list navigation-tree">
            {visibleNavigation.map((item) => {
              const active = focusedNavigationRowId === item.id;
              const related = !active && item.canonical_ids.some((canonicalId) => selectedNode?.canonical_node_ids.includes(canonicalId));
              const childCount = item.child_count;
              const hasVisibleChildren = childCount > 0;
              const relationLabel = navigationRelationLabel(item.relation);
              const sourceOrder = projection === "source" && item.sibling_count > 1
                ? `${item.sibling_index}/${item.sibling_count}`
                : null;
              const location = item.path
                ? `${item.path}${item.span ? `:${item.span.start_line}:${item.span.start_column + 1}` : ""}`
                : item.relation;
              const indent = 4 + item.depth * 12;
              return <div key={item.id} className={`navigation-row ${active ? "selected" : ""} ${related ? "canonical-related" : ""} ${item.reference ? "reference-row" : ""} ${item.parent_id === null ? "tree-root" : ""}`} style={{ paddingLeft: `${indent}px`, "--tree-indent": `${indent}px` } as React.CSSProperties}><button className="tree-chevron" disabled={!hasVisibleChildren} aria-label={`${expansions[projection].has(item.id) ? "Collapse" : "Expand"} ${item.label}`} onClick={() => toggleNavigationRow(item.id)}>{hasVisibleChildren ? expansions[projection].has(item.id) ? <ChevronDown size={13} /> : <ChevronRight size={13} /> : null}</button><button className="tree-subject" onClick={() => activateNavigationRow(item)} title={`${location} · 语义：${relationLabel}${sourceOrder ? ` · 同级 ${sourceOrder}（稳定源码次序，不代表执行顺序）` : ""}`}>{navigationIcon(item.kind)}<span><b>{item.label}</b><span className="tree-meta">{item.secondary_label && item.secondary_label !== item.label && <small>{item.secondary_label}</small>}<i>{relationLabel}</i>{sourceOrder && <i title="同父节点中的稳定源码次序，不代表执行顺序">同级 {sourceOrder}</i>}{item.binding_status === "ambiguous" && <i className="ambiguous" title="静态证据只能定位到候选集合">候选</i>}</span></span>{item.reference && <Link2 size={10} />}{childCount > 0 && <em>{childCount}</em>}{item.evidence_ids.length > 0 && <CircleDot size={9} />}</button></div>;
            })}
          </div>
        </aside>

        <main className="canvas-column">
          <div className="canvas-toolbar">
            <div className="breadcrumb">{breadcrumb}</div>
            <div className="canvas-actions">
              {mode === "layout" && <><button className="icon-button" title="Align left to primary" onClick={() => align("left")} disabled={selectedIds.length < 2}><Grip /></button><button className="icon-button" title="Distribute horizontally" onClick={() => align("distribute-horizontal")} disabled={selectedIds.length < 2}><Grip /></button><button className="open-full" onClick={() => void mutate("/api/layout", { batch_id: patchId("layout").replace("patch:", "batch:") }, "Auto layout")}><Layers3 size={14} /> Auto layout</button></>}
              <button className="icon-button" title="Zoom out" aria-label="Zoom out" onClick={() => zoom(1.2)}><ZoomOut /></button>
              <button className="icon-button" title="Zoom in" aria-label="Zoom in" onClick={() => zoom(0.82)}><ZoomIn /></button>
              <button className="icon-button" title="Fit scene" aria-label="Fit scene" onClick={fitScene}><Maximize2 /></button>
              <button className="icon-button mobile-only" title="Open inspector" aria-label="Open inspector" onClick={() => setMobileInspector(true)}><PanelRight /></button>
            </div>
          </div>
          <div className="canvas-stage">
            <svg ref={svgRef} className="scene" style={{ "--font-scale": data.view_state.font_scale ?? 1 } as React.CSSProperties} viewBox={viewBox.join(" ")} onPointerDown={beginPan} onPointerMove={movePointer} onPointerUp={endPointer} onPointerCancel={cancelPointer} onWheel={(event) => { event.preventDefault(); zoom(event.deltaY > 0 ? 1.1 : 0.9); }}>
              <defs><marker id="studio-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 10 5 0 10Z" fill="context-stroke" /></marker></defs>
              <rect className="paper" width={scene.paper_width} height={scene.paper_height} />
              <g className="root-layer">{scene.nodes.filter((node) => !node.parent_scene_node_id).map(renderSceneNode)}</g>
              <g className="container-layer">{scene.nodes.filter((node) => node.parent_scene_node_id && node.shape === "container").map(renderSceneNode)}</g>
              <g className="edge-layer">{scene.edges.map((edge) => <g key={edge.scene_edge_id} data-scene-edge-id={edge.scene_edge_id}><polyline points={edge.points.map((point) => `${point.x},${point.y}`).join(" ")} fill="none" stroke={edge.stroke} strokeWidth={edge.width} strokeDasharray={edge.dash} markerEnd="url(#studio-arrow)" /></g>)}</g>
              <g className="node-layer">{scene.nodes.filter((node) => node.parent_scene_node_id && node.shape !== "container").map(renderSceneNode)}</g>
            </svg>
            {selectedNode && <div className="context-bar"><button title="Focus selection"><Focus size={14} /></button><button title={pinned.has(selectedNode.scene_node_id) ? "Unpin" : "Pin"} onClick={() => void submit("set-pin", selectedNode.scene_node_id, { enabled: !pinned.has(selectedNode.scene_node_id) })}>{pinned.has(selectedNode.scene_node_id) ? <PinOff size={14} /> : <Pin size={14} />}</button><button title="Expand in navigation tree" onClick={() => expandInNavigation(selectedNode)}><Maximize2 size={14} /></button></div>}
          </div>
        </main>

        <aside className={`right-panel panel ${mobileInspector ? "mobile-open" : ""}`}>
          <div className="panel-title"><PanelRight size={15} /> Inspector<button className="icon-button mobile-only inspector-close" title="Close inspector" onClick={() => setMobileInspector(false)}><X /></button></div>
          <div className="tab-strip">{(["inspect", "source", "visual", "model", "evidence"] as const).map((tab) => <button key={tab} className={inspectorTab === tab ? "active" : ""} onClick={() => setInspectorTab(tab)}>{tab === "inspect" ? "Overview" : tab[0].toUpperCase() + tab.slice(1)}</button>)}</div>
          {!selectedNode || !selectedViewNode ? <div className="empty-state"><Focus size={20} /><span>No selection</span></div> : <div className="inspector-content">
            {inspectorTab === "inspect" && <StructureInspector label={selectedViewNode.semantic_name} viewNode={selectedViewNode} sceneNode={selectedNode} nodes={selectedArchitectureNodes} tensors={data.architecture.tensors} evidence={selectedEvidence} />}
            {inspectorTab === "source" && <SourceInspector nodes={selectedArchitectureNodes} evidence={selectedEvidence} />}
            {inspectorTab === "visual" && <VisualInspector node={selectedNode} pinned={pinned.has(selectedNode.scene_node_id)} fontScale={data.view_state.font_scale ?? 1} lineWeight={data.view_state.line_weight ?? 1.5} onPatch={submit} onBatch={submitBatch} />}
            {inspectorTab === "model" && <ModelInspector node={architectureNode} nodes={data.architecture.nodes} transaction={data.transaction} proposal={data.proposal} writebackBlocked={writebackBlocked} onPrepareParameter={prepareParameter} onPrepareStructural={prepareStructural} onProposeConnection={proposeConnection} onCommit={() => mutate("/api/transaction/commit", {}, "Committed source transaction")} onDiscard={() => mutate("/api/transaction/discard", {}, "Discarded source transaction")} />}
            {inspectorTab === "evidence" && <div className="evidence-list">{selectedEvidence.length ? selectedEvidence.map((record) => <section key={record.evidence_id}><div><FileCode2 size={14} /><strong>{record.kind}</strong><span>{record.confidence}</span></div><code>{record.path ?? record.evidence_id}{record.span ? `:${record.span.start_line}` : ""}</code><p>{record.claim}</p></section>) : <div className="empty-state">No linked evidence</div>}</div>}
          </div>}
        </aside>
      </div>

      <section className="bottom-panel">
        <div className="bottom-tabs"><PanelBottom size={14} />{(["problems", "diff", "validation", "jobs", "activity"] as const).map((tab) => <button key={tab} className={bottomTab === tab ? "active" : ""} onClick={() => setBottomTab(tab)}>{tab === "diff" ? "Source Diff" : tab[0].toUpperCase() + tab.slice(1)}{tab === "problems" && <span>{data.diagnostics.length}</span>}{tab === "jobs" && data.jobs?.some((job) => ["queued", "running"].includes(job.state)) && <span>1</span>}</button>)}</div>
        <div className="bottom-content">{bottomTab === "problems" && ([...data.diagnostics, ...data.draft.proofs.map((proof) => ({ code: proof.reason_codes[0] ?? proof.status.toUpperCase(), severity: proof.status, message: proof.message, target_ids: proof.affected_subject_ids }))].length ? [...data.diagnostics, ...data.draft.proofs.map((proof) => ({ code: proof.reason_codes[0] ?? proof.status.toUpperCase(), severity: proof.status, message: proof.message, target_ids: proof.affected_subject_ids }))].map((item, index) => <button key={`${item.code}-${index}`} onClick={() => choose(scene.nodes.find((node) => node.canonical_node_ids.some((id) => item.target_ids.includes(id)))?.scene_node_id ?? null)}><AlertTriangle size={13} /><b>{item.severity}</b><span>{item.message}</span></button>) : <div className="ok-line"><CircleDot size={13} /> No geometry or writeback problems</div>)}{bottomTab === "diff" && (data.transaction ? <TransactionReview transaction={data.transaction} writebackBlocked={writebackBlocked} onCommit={() => mutate("/api/transaction/commit", {}, "Committed source transaction")} onDiscard={() => mutate("/api/transaction/discard", {}, "Discarded source transaction")} /> : <div className="ok-line"><LockKeyhole size={13} /> Source digest {sourceDigest} unchanged</div>)}{bottomTab === "validation" && (latestValidation ? <div className="gate-list">{latestValidation.gate_results.map((gate) => <span key={gate.gate} className={gate.status}>{gate.status} · {gate.gate} · {gate.message}</span>)}</div> : <div className="validation-line"><CircleDot size={13} /> Validation has not been run for this fingerprint</div>)}{bottomTab === "jobs" && <div className="job-list">{data.jobs?.length ? data.jobs.map((job) => <div key={job.job_id}><code>{job.job_id}</code><span>{job.profile}</span><b>{job.state} · {Math.round(job.progress * 100)}%</b></div>) : <div className="validation-line">No analysis jobs in this session</div>}</div>}{bottomTab === "activity" && <div className="activity-list">{activity.map((item, index) => <span key={`${item}-${index}`}><History size={12} />{item}</span>)}</div>}</div>
      </section>

      <button className="theme-toggle icon-button" title="Toggle theme" aria-label="Toggle theme" onClick={() => { const next = !dark; setDark(next); void submit("set-theme", undefined, { theme: next ? "studio-dark" : "paper-light" }); }}>{dark ? <Sun /> : <Moon />}</button>
      {projectDialog && <div className="dialog-backdrop" role="presentation" onPointerDown={(event) => { if (event.target === event.currentTarget) setProjectDialog(false); }}><section className="project-dialog" role="dialog" aria-modal="true" aria-label="Open project"><header><div><strong>Open project</strong><span>Static discovery only</span></div><button className="icon-button" title="Close" onClick={() => setProjectDialog(false)}><X /></button></header><label className="model-field"><span>Project root</span><input value={projectRoot} onChange={(event) => setProjectRoot(event.target.value)} /></label><button className="prepare-button" onClick={() => void openProject()}><Search size={14} /> Discover</button>{pendingProject && <div className="project-options"><label className="model-field"><span>Entrypoint</span><select value={projectEntrypoint} onChange={(event) => { setProjectEntrypoint(event.target.value); const candidate = pendingProject.discovery.entrypoints.find((item) => item.entrypoint === event.target.value); if (candidate?.framework !== "unknown") setProjectFramework(candidate?.framework ?? "auto"); }}>{pendingProject.discovery.entrypoints.map((item) => <option key={item.entrypoint} value={item.entrypoint}>{item.entrypoint}</option>)}</select></label><label className="model-field"><span>Framework</span><select value={projectFramework} onChange={(event) => setProjectFramework(event.target.value)}>{["auto", "pytorch", "keras", "jax", "onnx"].map((item) => <option key={item}>{item}</option>)}</select></label><label className="model-field"><span>Config</span><select value={projectConfig} onChange={(event) => setProjectConfig(event.target.value)}><option value="">No config</option>{pendingProject.discovery.configs.map((item) => <option key={item.path}>{item.path}</option>)}</select></label><button className="primary-action analyze-action" disabled={!projectEntrypoint || projectFramework === "auto"} onClick={() => void analyzeProject()}><Play size={14} /> Analyze</button></div>}</section></div>}
    </div>
  );
}

function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="field"><label>{label}</label><div className={mono ? "mono" : ""}>{value}</div></div>;
}

function structureKind(label: string, nodes: ArchitectureNodeView[]): "tensor" | "encoder" | "decoder" | "ffn" | "norm" | "graph" {
  const normalizedLabel = label.trim().toLowerCase();
  const text = `${normalizedLabel} ${nodes.map((node) => `${node.semantic_name} ${String(node.attributes.op_type ?? "")}`).join(" ")}`.toLowerCase();
  if (["q", "k", "v", "query", "key", "value"].includes(normalizedLabel)) return "tensor";
  if (normalizedLabel.includes("encoder")) return nodes.length > 2 ? "encoder" : "norm";
  if (normalizedLabel.includes("decoder") || normalizedLabel === "cross") return "decoder";
  if (text.includes("ffn") || text.includes("feed forward") || text.includes("mlp")) return "ffn";
  if (text.includes("norm")) return "norm";
  if (text.includes("split") || text.includes("transpose") || text.includes("projection")) return "tensor";
  return "graph";
}

function StructureGlyph({ kind, label, count }: { kind: ReturnType<typeof structureKind>; label: string; count: number }) {
  if (kind === "tensor") {
    return <svg className="structure-glyph tensor-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} tensor structure`}>
      <g className="tensor-planes">
        <rect x="35" y="16" width="132" height="70" />
        <rect x="47" y="25" width="132" height="70" />
        <rect x="59" y="34" width="132" height="70" />
        {[81, 103, 125, 147, 169].map((x) => <line key={`x-${x}`} x1={x} y1="34" x2={x} y2="104" />)}
        {[51, 68, 85].map((y) => <line key={`y-${y}`} x1="59" y1={y} x2="191" y2={y} />)}
      </g>
      <text x="202" y="45">heads</text><text x="202" y="64">tokens</text><text x="202" y="83">features</text>
      <text className="glyph-title" x="35" y="112">stacked matrix</text>
    </svg>;
  }
  if (kind === "encoder" || kind === "decoder") {
    const first = kind === "encoder" ? "Q / K / V" : "Self / Cross";
    return <svg className="structure-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} module structure`}>
      <g className="module-flow">
        <rect x="8" y="39" width="57" height="36" /><text x="36" y="61">{first}</text>
        <path d="M65 57H84" /><path d="m79 52 6 5-6 5" />
        <rect x="85" y="32" width="72" height="50" /><text x="121" y="53">Attention</text><text x="121" y="69">context</text>
        <path d="M157 57H176" /><path d="m171 52 6 5-6 5" />
        <rect x="177" y="39" width="74" height="36" /><text x="214" y="53">Add</text><text x="214" y="68">Norm</text>
      </g>
      <text className="glyph-title" x="8" y="108">{count} executable operations</text>
    </svg>;
  }
  if (kind === "ffn") {
    return <svg className="structure-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} feed-forward structure`}>
      <g className="module-flow ffn-flow">
        <rect x="13" y="40" width="45" height="34" /><text x="35" y="61">D</text>
        <path d="M58 57H84" /><path d="m79 52 6 5-6 5" />
        <rect x="85" y="25" width="78" height="64" /><text x="124" y="54">4D</text><text x="124" y="71">activation</text>
        <path d="M163 57H189" /><path d="m184 52 6 5-6 5" />
        <rect x="190" y="40" width="45" height="34" /><text x="212" y="61">D</text>
      </g>
      <text className="glyph-title" x="13" y="108">expand · transform · project</text>
    </svg>;
  }
  if (kind === "norm") {
    return <svg className="structure-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} normalization structure`}>
      <g className="module-flow">
        <rect x="13" y="40" width="58" height="34" /><text x="42" y="61">input</text>
        <path d="M71 57H96" /><path d="m91 52 6 5-6 5" />
        <circle cx="130" cy="57" r="29" /><text x="130" y="53">μ · σ</text><text x="130" y="68">γ · β</text>
        <path d="M159 57H184" /><path d="m179 52 6 5-6 5" />
        <rect x="185" y="40" width="62" height="34" /><text x="216" y="61">normalized</text>
      </g>
      <text className="glyph-title" x="13" y="108">feature-wise normalization</text>
    </svg>;
  }
  return <svg className="structure-glyph" viewBox="0 0 260 118" role="img" aria-label={`${label} contained structure`}>
    <g className="generic-glyph">
      <rect x="12" y="20" width="236" height="78" />
      {Array.from({ length: Math.min(5, Math.max(1, count)) }, (_, index) => {
        const x = 29 + index * 43;
        return <g key={x}><circle cx={x} cy="59" r="12" />{index > 0 && <line x1={x - 31} y1="59" x2={x - 12} y2="59" />}</g>;
      })}
    </g>
    <text className="glyph-title" x="12" y="112">{count} contained operations</text>
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
    <header className="inspector-heading"><div><h2>{label}</h2><span>{kind === "tensor" ? "Tensor transformation" : "Module structure"}</span></div><b>{nodes.length} ops</b></header>
    <div className={`structure-preview preview-${kind}`}><StructureGlyph kind={kind} label={label} count={nodes.length} /></div>
    {shapeStages.length > 0 && <section className="shape-flow"><div className="section-heading">Tensor shape flow</div><div className="shape-track">{shapeStages.map((tensor, index) => <React.Fragment key={tensor.tensor_id}>{index > 0 && <span className="shape-arrow">→</span>}<div className="shape-step"><strong>{tensor.role}</strong><code>{tensor.symbolic_shape.replaceAll(",", " × ").replace("[", "").replace("]", "")}</code></div></React.Fragment>)}</div></section>}
    {primaryTensor?.semantic_axes.length ? <div className="axis-legend">{primaryTensor.semantic_axes.map((axis, index) => <span key={axis}><b>{primaryTensor.symbolic_shape.replace(/[\[\]]/g, "").split(",")[index] ?? `d${index + 1}`}</b>{axis.replaceAll("_", " ")}</span>)}</div> : null}
    <section className="operation-summary"><div className="section-heading">Contained operations</div><div className="operation-chips">{opTypes.slice(0, 8).map((item) => <span key={item}>{item}</span>)}</div></section>
    <div className="status-row"><span>Exact IR</span><b>{nodes.length} canonical</b></div>
    <Field label="Source symbols" value={[...new Set(nodes.map((node) => node.source_symbol).filter(Boolean))].join(", ") || "Structural container"} />
    <Field label="Evidence" value={`${evidence.length} records · ${evidence[0]?.confidence ?? "exact"}`} mono />
    <div className="resolution"><div className="section-label">Resolution</div><dl><dt>Implementation</dt><dd>{String(viewNode.attributes.resolution ? "resolved" : "exact")}</dd><dt>Semantics</dt><dd>{viewNode.collapsed ? "grouped" : "expanded"}</dd><dt>Execution</dt><dd>{sceneNode.canonical_node_ids.length ? "authored" : "structural"}</dd></dl></div>
  </div>;
}

function SourceInspector({ nodes, evidence }: { nodes: ArchitectureNodeView[]; evidence: Evidence[] }) {
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
        if (!response.ok) throw new Error((await response.json() as { error?: string }).error ?? "Source excerpt unavailable");
        return response.json() as Promise<SourceExcerpt>;
      })
      .then(setExcerpt)
      .catch((error) => { if (!controller.signal.aborted) setSourceError(String(error)); });
    return () => controller.abort();
  }, [activeEvidence?.evidence_id]);

  const paths = [...new Set(sourceEvidence.map((record) => record.path).filter((path): path is string => Boolean(path)))];
  return <div className="source-inspector">
    <header className="inspector-heading"><div><h2>Source structure</h2><span>{paths.length} files · {nodes.length} operations</span></div><FileCode2 size={17} /></header>
    <section className="source-outline"><div className="section-heading">Containment</div>{paths.map((path) => {
      const pathEvidence = sourceEvidence.filter((record) => record.path === path);
      const symbols = [...new Set(pathEvidence.map((record) => record.symbol).filter((symbol): symbol is string => Boolean(symbol)))];
      return <div className="source-file" key={path}><div className="source-file-row"><FileCode2 size={13} /><strong>{path}</strong></div>{symbols.map((symbol) => {
        const symbolEvidenceIds = new Set(pathEvidence.filter((record) => record.symbol === symbol).map((record) => record.evidence_id));
        const symbolNodes = nodes.filter((node) => node.evidence_ids.some((id) => symbolEvidenceIds.has(id)));
        return <div className="source-symbol" key={symbol}><div><Braces size={12} /><b>{symbol}</b></div><div className="source-node-list">{symbolNodes.map((node) => <span key={node.node_id}><CircleDot size={8} />{node.semantic_name}</span>)}</div></div>;
      })}</div>;
    })}</section>
    {sourceEvidence.length > 0 ? <>
      <section className="source-locations"><div className="section-heading">Evidence locations</div>{sourceEvidence.slice(0, 20).map((record) => <button key={record.evidence_id} className={record.evidence_id === activeEvidence?.evidence_id ? "active" : ""} onClick={() => setActiveEvidenceId(record.evidence_id)}><code>{record.path}:{record.span?.start_line}</code><span>{record.symbol}</span></button>)}</section>
      <section className="code-excerpt"><div className="code-header"><span>{excerpt?.path ?? activeEvidence?.path}</span><code>{activeEvidence?.symbol}</code></div>{sourceError ? <div className="source-error">{sourceError}</div> : excerpt ? <pre>{excerpt.lines.map((line) => <div key={line.number} className={line.number >= excerpt.highlight_start_line && line.number <= excerpt.highlight_end_line ? "highlight" : ""}><span>{line.number}</span><code>{line.text || " "}</code></div>)}</pre> : <div className="source-loading">Loading source…</div>}</section>
    </> : <div className="empty-state"><FileCode2 size={20} /><span>No source evidence</span></div>}
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

function ModelInspector({ node, nodes, transaction, proposal, writebackBlocked, onPrepareParameter, onPrepareStructural, onProposeConnection, onCommit, onDiscard }: {
  node?: StudioState["architecture"]["nodes"][number];
  nodes: StudioState["architecture"]["nodes"];
  transaction: SourceTransaction | null;
  proposal: AgentProposal | null;
  writebackBlocked: boolean;
  onPrepareParameter: (parameterName: string, newValue: unknown) => Promise<void>;
  onPrepareStructural: (operation: string, parameters: Record<string, unknown>) => Promise<void>;
  onProposeConnection: (sourcePortId: string, targetNodeId: string, targetPortId: string) => Promise<void>;
  onCommit: () => Promise<void>;
  onDiscard: () => Promise<void>;
}) {
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
    return <div className="empty-state"><Braces size={20} /><span>No canonical node selected</span></div>;
  }
  const active = transaction && transaction.request.target_node_id === node.node_id;
  const affected = active ? transaction.expected_delta.changed_nodes.length : 0;
  const transactionLocked = Boolean(transaction && !["discarded", "committed", "failed"].includes(transaction.state));
  const activationSupported = ["GELU", "ReLU", "SiLU"].includes(currentActivation);
  return <>
    <div className="transaction-banner"><GitBranch size={15} /> Safe source transaction</div>
    {parameter ? <section className="model-operation"><div className="section-heading">Parameter</div><label className="model-field"><span>Parameter</span><select value={parameter.name} onChange={(event) => setName(event.target.value)}>{parameters.map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}</select></label><Field label="Current / provenance" value={`${displayValue(parameter.value)} · ${parameter.origin}`} mono /><label className="model-field"><span>Target value</span><input value={value} onChange={(event) => setValue(event.target.value)} /></label><button className="prepare-button" disabled={transactionLocked || value === displayValue(parameter.value)} onClick={() => void onPrepareParameter(parameter.name, parseValue(value))}><GitBranch size={14} /> Prepare parameter</button></section> : <div className="operation-unavailable">No exact editable parameter on this node.</div>}
    <section className="model-operation"><div className="section-heading">Registered transforms</div>{activationSupported && <><label className="model-field"><span>Activation</span><select value={replacement} onChange={(event) => setReplacement(event.target.value)}>{["GELU", "ReLU", "SiLU"].filter((item) => item !== currentActivation).map((item) => <option key={item}>{item}</option>)}</select></label><button className="prepare-button" disabled={transactionLocked} onClick={() => void onPrepareStructural("replace_activation", { replacement })}><GitBranch size={14} /> Replace activation</button></>}<label className="model-field"><span>LayerNorm module</span><input value={moduleName} onChange={(event) => setModuleName(event.target.value)} /></label><label className="model-field"><span>Normalized shape</span><input value={normalizedShape} onChange={(event) => setNormalizedShape(event.target.value)} /></label><button className="prepare-button" disabled={transactionLocked || !moduleName || !normalizedShape} onClick={() => void onPrepareStructural("insert_layer_norm", { module_name: moduleName, normalized_shape: parseValue(normalizedShape) })}><GitBranch size={14} /> Insert LayerNorm</button></section>
    <section className="model-operation"><div className="section-heading">Proposed connection</div>{node.output_ports.length && targetNode ? <><label className="model-field"><span>Source output</span><select value={sourcePortId} onChange={(event) => setSourcePortId(event.target.value)}>{node.output_ports.map((port) => <option key={port.port_id} value={port.port_id}>{port.role} · {port.port_id}</option>)}</select></label><label className="model-field"><span>Target node</span><select value={targetNode.node_id} onChange={(event) => setTargetNodeId(event.target.value)}>{targetOptions.map((item) => <option key={item.node_id} value={item.node_id}>{item.semantic_name}</option>)}</select></label><label className="model-field"><span>Target input</span><select value={targetPortId} onChange={(event) => setTargetPortId(event.target.value)}>{targetNode.input_ports.map((port) => <option key={port.port_id} value={port.port_id}>{port.role} · {port.port_id}</option>)}</select></label><button className="prepare-button" onClick={() => void onProposeConnection(sourcePortId, targetNode.node_id, targetPortId)}><Link2 size={14} /> Create handoff</button></> : <div className="operation-unavailable">Select a node with an authored output port.</div>}</section>
    {proposal && <div className="proposal-card"><div><ShieldCheck size={15} /><strong>Agent handoff</strong><code>{proposal.reason_code}</code></div><p>{proposal.summary}</p><dl><dt>Shell</dt><dd>Denied</dd><dt>Network</dt><dd>Denied</dd><dt>Source write</dt><dd>Denied</dd></dl></div>}
    <Field label="Expected affected nodes / edges" value={active ? `${affected} / ${transaction.expected_delta.changed_edges.length}` : "Calculated during prepare"} />
    {active && <div className={`transaction-state ${transaction.state}`}>{transaction.state}</div>}
    {active && transaction.state === "review-ready" && <div className="transaction-actions"><button className="commit-button" disabled={writebackBlocked} title={writebackBlocked ? "Resolve draft blockers before committing" : "Commit verified source transaction"} onClick={() => void onCommit()}><CircleDot size={14} /> Commit to source</button><button onClick={() => void onDiscard()}><X size={14} /> Discard</button></div>}
    {active && transaction.state === "failed" && <div className="transaction-actions"><button disabled title="Agent handoff arrives with structural transforms"><Braces size={14} /> Fix with Agent</button><button onClick={() => void onDiscard()}><X size={14} /> Discard</button></div>}
  </>;
}

function deltaSummary(delta?: GraphDelta): string {
  if (!delta) return "Not available";
  const nodes = delta.added_nodes.length + delta.removed_nodes.length + delta.changed_nodes.length;
  const edges = delta.added_edges.length + delta.removed_edges.length + delta.changed_edges.length;
  return `${delta.changed_parameters.length} parameters · ${nodes} nodes · ${edges} edges · ${delta.changed_shapes.length} shapes`;
}

function TransactionReview({ transaction, writebackBlocked, onCommit, onDiscard }: { transaction: SourceTransaction; writebackBlocked: boolean; onCommit: () => Promise<void>; onDiscard: () => Promise<void> }) {
  return <div className="transaction-review">
    <section><h3>Source diff</h3><pre>{transaction.source_diff || "No textual change"}</pre></section>
    <section><h3>Graph Delta</h3><dl><dt>Expected</dt><dd>{deltaSummary(transaction.expected_delta)}</dd><dt>Observed</dt><dd>{deltaSummary(transaction.observed_delta)}</dd></dl>{transaction.expected_delta.changed_parameters.map((item) => <code key={`${item.node_id}-${item.parameter_name}`}>{item.node_id}.{item.parameter_name}: {displayValue(item.before)} → {displayValue(item.after)}</code>)}</section>
    <section><h3>Validation receipt</h3><div className="gate-list">{transaction.gates.map((gate) => <span key={gate.gate} className={gate.status}>{gate.status} · {gate.gate}</span>)}</div><div className="review-actions">{transaction.state === "review-ready" ? <button className="commit-button" disabled={writebackBlocked} title={writebackBlocked ? "Resolve draft blockers before committing" : "Commit verified source transaction"} onClick={() => void onCommit()}><CircleDot size={14} /> Commit to source</button> : <button disabled><Braces size={14} /> Fix with Agent</button>} {!['committed', 'discarded'].includes(transaction.state) && <button onClick={() => void onDiscard()}><X size={14} /> Discard</button>}</div></section>
  </div>;
}

function VisualInspector({ node, pinned, fontScale, lineWeight, onPatch, onBatch }: { node: SceneNode; pinned: boolean; fontScale: number; lineWeight: number; onPatch: (operation: string, targetId: string | undefined, value: Record<string, unknown>) => Promise<void>; onBatch: (description: string, patches: Array<{ operation: string; targetId?: string; value: Record<string, unknown> }>) => Promise<void> }) {
  const [bounds, setBounds] = useState(node.bounds);
  const [label, setLabel] = useState(node.label_lines.join("\n"));
  useEffect(() => setBounds(node.bounds), [node.scene_node_id, node.bounds]);
  useEffect(() => setLabel(node.label_lines.join("\n")), [node.scene_node_id, node.label_lines]);
  const update = (key: keyof Rect, value: number) => setBounds((current) => ({ ...current, [key]: value }));
  return <><div className="section-label">Geometry</div><div className="numeric-grid">{(["x", "y", "width", "height"] as const).map((key) => <label key={key}><span>{key.toUpperCase()}</span><input type="number" min={key === "width" || key === "height" ? 1 : 0} value={Math.round(bounds[key])} onChange={(event) => update(key, Number(event.target.value))} /></label>)}</div><button className="apply-visual" onClick={() => void onBatch("Apply geometry", [{ operation: "set-position", targetId: node.scene_node_id, value: { x: bounds.x, y: bounds.y } }, { operation: "set-size", targetId: node.scene_node_id, value: { width: bounds.width, height: bounds.height } }])}>Apply geometry</button><label className="toggle-row"><input type="checkbox" checked={pinned} onChange={() => void onPatch("set-pin", node.scene_node_id, { enabled: !pinned })} /><span>Pin during layout</span></label><label className="model-field"><span>Fill</span><input type="color" value={node.fill.startsWith("#") ? node.fill.slice(0, 7) : "#ffffff"} onChange={(event) => void onPatch("set-palette", undefined, { overrides: { [node.scene_node_id]: event.target.value } })} /></label><label className="model-field"><span>Label lines</span><textarea rows={3} value={label} onChange={(event) => setLabel(event.target.value)} /></label><button className="apply-visual" onClick={() => void onPatch("set-label-wrap", node.scene_node_id, { lines: label.split("\n").filter(Boolean).slice(0, 3) })}>Apply label wrap</button><label className="model-field"><span>Font scale · {fontScale.toFixed(2)}</span><input type="range" min="0.75" max="1.5" step="0.05" value={fontScale} onChange={(event) => void onPatch("set-font-scale", undefined, { scale: Number(event.target.value) })} /></label><label className="model-field"><span>Line weight · {lineWeight.toFixed(1)}</span><input type="range" min="0.5" max="5" step="0.5" value={lineWeight} onChange={(event) => void onPatch("set-line-weight", undefined, { width: Number(event.target.value) })} /></label><Field label="Stroke" value={node.stroke} mono /></>;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
