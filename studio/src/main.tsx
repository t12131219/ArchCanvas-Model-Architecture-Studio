import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertTriangle,
  Box,
  Braces,
  ChevronDown,
  ChevronRight,
  CircleDot,
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
  Redo2,
  Search,
  ShieldCheck,
  Sun,
  Undo2,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";

import "./styles.css";

type Level = "L1" | "L2" | "L3" | "L4";
type Mode = "explore" | "layout" | "model";

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
  level: Level;
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
  architecture: {
    architecture_id: string;
    entrypoint: string;
    nodes: Array<{
      node_id: string;
      semantic_name: string;
      parent_id?: string;
      attributes: Record<string, unknown>;
      parameters: ArchitectureParameter[];
      input_ports: ArchitecturePort[];
      output_ports: ArchitecturePort[];
    }>;
    tensors: Array<{ tensor_id: string; role: string; symbolic_shape: string }>;
  };
  snapshot: { project_root: string; entrypoint: string; revision: string };
  evidence: Evidence[];
  runtime: {
    trace: {
      trace_id: string;
      environment: { selected_device: string; torch_version: string };
      observations: unknown[];
    };
    node_evidence: Record<string, string[]>;
  } | null;
  views: Record<Level, PublicationView>;
  scenes: Record<Level, Scene>;
  document: {
    source_digest: string;
    visual_patches: unknown[];
    redo_patches: unknown[];
  };
  view_state: {
    pinned_node_ids?: string[];
    collapsed_node_ids?: string[];
    theme?: string;
    cameras?: Record<string, { x: number; y: number; zoom: number }>;
  };
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
  nodeId: string;
  startClient: Point;
  startBounds: Rect;
}

interface PanState {
  startClient: Point;
  startViewBox: [number, number, number, number];
}

const levels: Level[] = ["L1", "L2", "L3", "L4"];

function embeddedState(): StudioState | null {
  const element = document.getElementById("archcanvas-studio-data");
  if (!element?.textContent) return null;
  return JSON.parse(element.textContent) as StudioState;
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

function App() {
  const [data, setData] = useState<StudioState | null>(() => embeddedState());
  const [level, setLevel] = useState<Level>("L1");
  const [mode, setMode] = useState<Mode>("explore");
  const [selected, setSelected] = useState<string | null>(null);
  const [inspectorTab, setInspectorTab] = useState<"inspect" | "visual" | "model" | "evidence">("inspect");
  const [bottomTab, setBottomTab] = useState<"problems" | "diff" | "validation" | "activity">("problems");
  const [query, setQuery] = useState("");
  const [dark, setDark] = useState(() => embeddedState()?.view_state.theme === "studio-dark");
  const [viewBox, setViewBox] = useState<[number, number, number, number] | null>(null);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [pan, setPan] = useState<PanState | null>(null);
  const [preview, setPreview] = useState<Record<string, Point>>({});
  const [activity, setActivity] = useState<string[]>(["Studio document opened"]);
  const svgRef = useRef<SVGSVGElement>(null);
  const selections = useRef<Partial<Record<Level, string | null>>>({});
  const cameraTimer = useRef<number | null>(null);

  useEffect(() => {
    fetch("/api/state", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((state: StudioState) => setData(state))
      .catch(() => undefined);
  }, []);

  useEffect(() => () => {
    if (cameraTimer.current !== null) window.clearTimeout(cameraTimer.current);
  }, []);

  const scene = data?.scenes[level];
  const view = data?.views[level];
  const camera = scene ? data?.view_state.cameras?.[scene.scene_id] : undefined;
  useEffect(() => {
    if (scene) {
      setViewBox(
        camera
          ? [camera.x, camera.y, scene.paper_width / camera.zoom, scene.paper_height / camera.zoom]
          : [0, 0, scene.paper_width, scene.paper_height],
      );
    }
    setSelected(selections.current[level] ?? null);
    setPreview({});
  }, [level, scene?.scene_id, camera?.x, camera?.y, camera?.zoom]);

  useEffect(() => {
    setDark(data?.view_state.theme === "studio-dark");
  }, [data?.view_state.theme]);

  const selectedNode = scene?.nodes.find((node) => node.scene_node_id === selected) ?? null;
  const selectedViewNode = view?.nodes.find(
    (node) => node.view_node_id === selectedNode?.view_node_id,
  );
  const selectedEvidence = useMemo(() => {
    const runtimeIds = (selectedNode?.canonical_node_ids ?? []).flatMap(
      (nodeId) => data?.runtime?.node_evidence[nodeId] ?? [],
    );
    const ids = new Set([...(selectedNode?.evidence_ids ?? []), ...runtimeIds]);
    return data?.evidence.filter((record) => ids.has(record.evidence_id)) ?? [];
  }, [data?.evidence, data?.runtime, selectedNode]);
  const pinned = new Set(data?.view_state.pinned_node_ids ?? []);
  const collapsed = new Set(data?.view_state.collapsed_node_ids ?? []);

  async function mutate(endpoint: string, payload?: object, activityLabel?: string) {
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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

  async function submit(operation: string, targetId: string | undefined, value: Record<string, unknown>, sceneId = scene?.scene_id) {
    if (!sceneId) return;
    await mutate("/api/patch", {
      patch_id: patchId(operation),
      operation,
      target_id: targetId,
      value: { ...value, scene_id: sceneId },
    });
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

  function selectSearchResult() {
    if (!scene || !query.trim()) return;
    const lowered = query.toLowerCase();
    const result = scene.nodes.find((node) => {
      const publication = view?.nodes.find((item) => item.view_node_id === node.view_node_id);
      return [publication?.semantic_name, node.scene_node_id, ...node.canonical_node_ids]
        .join(" ")
        .toLowerCase()
        .includes(lowered);
    });
    if (result) choose(result.scene_node_id);
  }

  function choose(nodeId: string | null) {
    selections.current[level] = nodeId;
    setSelected(nodeId);
  }

  function switchLevel(next: Level) {
    selections.current[level] = selected;
    setLevel(next);
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
    choose(node.scene_node_id);
    if (mode === "explore" || pinned.has(node.scene_node_id)) return;
    const point = pointerPosition(event);
    if (!point) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrag({ nodeId: node.scene_node_id, startClient: point, startBounds: node.bounds });
  }

  function moveDrag(event: React.PointerEvent) {
    if (!drag) return;
    const point = pointerPosition(event);
    if (!point) return;
    setPreview({
      [drag.nodeId]: {
        x: Math.max(0, drag.startBounds.x + point.x - drag.startClient.x),
        y: Math.max(0, drag.startBounds.y + point.y - drag.startClient.y),
      },
    });
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
    const position = preview[drag.nodeId];
    if (position) void submit("set-position", drag.nodeId, { x: position.x, y: position.y });
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

  function openNext(node: SceneNode) {
    if (level === "L4") return;
    void submit("set-collapse", node.scene_node_id, { enabled: false });
    switchLevel(levels[Math.min(levels.indexOf(level) + 1, levels.length - 1)]);
  }

  if (!data || !scene || !view || !viewBox) {
    return <div className="loading">Loading Studio…</div>;
  }

  const sourceDigest = data.document.source_digest.slice(0, 12);
  const selectedCanonical = selectedNode?.canonical_node_ids[0];
  const architectureNode = data.architecture.nodes.find((node) => node.node_id === selectedCanonical);
  const breadcrumb = selectedViewNode
    ? `${data.architecture.entrypoint.split(":").at(-1)} / ${view.name} / ${selectedViewNode.semantic_name}`
    : `${data.architecture.entrypoint.split(":").at(-1)} / ${view.name}`;

  function renderSceneNode(original: SceneNode) {
    const position = preview[original.scene_node_id];
    const node = position ? { ...original, bounds: { ...original.bounds, ...position } } : original;
    const isRoot = !node.parent_scene_node_id;
    const isSelected = selected === node.scene_node_id;
    return (
      <g
        key={node.scene_node_id}
        className={`scene-node ${isRoot ? "root" : ""} ${isSelected ? "selected" : ""} ${collapsed.has(node.scene_node_id) ? "collapsed" : ""}`}
        tabIndex={isRoot ? -1 : 0}
        onPointerDown={(event) => beginDrag(event, node)}
        onDoubleClick={() => !isRoot && openNext(node)}
        onKeyDown={(event) => { if (event.key === "Enter" && !isRoot) openNext(node); }}
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
      </g>
    );
  }

  return (
    <div className={`${dark ? "studio dark" : "studio"}${data.transaction ? " has-transaction" : ""}`}>
      <header className="topbar">
        <div className="product"><Box size={17} /> ArchCanvas</div>
        <div className="project-meta">
          <strong>{data.architecture.entrypoint.split(":").at(-1)}</strong>
          <span>{data.snapshot.revision}</span>
        </div>
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
          <button className="validate-button"><CircleDot size={14} /> Validate <span>{data.diagnostics.length}</span></button>
          <a className="primary-action" href={`/api/export?level=${level}`}><Download size={14} /> Export</a>
        </div>
      </header>

      <div className="workspace">
        <aside className="left-panel panel">
          <div className="panel-title"><PanelLeft size={15} /> Model</div>
          <div className="search-field"><Search size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && selectSearchResult()} placeholder="Find node or tensor" /></div>
          <nav className="view-list" aria-label="Publication views">
            {levels.map((item) => <button key={item} className={level === item ? "active" : ""} onClick={() => switchLevel(item)}><Layers3 size={14} /><span>{item}</span><small>{data.views[item].name}</small></button>)}
          </nav>
          <div className="section-label">Execution tree</div>
          <div className="tree-list">
            {scene.nodes.filter((node) => node.parent_scene_node_id).map((node) => {
              const publication = view.nodes.find((item) => item.view_node_id === node.view_node_id);
              return <button key={node.scene_node_id} className={selected === node.scene_node_id ? "selected" : ""} onClick={() => choose(node.scene_node_id)}><ChevronRight size={13} /><span>{publication?.semantic_name ?? node.scene_node_id}</span>{node.evidence_ids.length > 0 && <CircleDot size={10} />}</button>;
            })}
          </div>
          <div className="section-label">Tensors</div>
          <div className="tensor-list">{data.architecture.tensors.slice(0, 8).map((tensor) => <div key={tensor.tensor_id}><span>{tensor.role}</span><code>{tensor.symbolic_shape}</code></div>)}</div>
        </aside>

        <main className="canvas-column">
          <div className="canvas-toolbar">
            <div className="breadcrumb">{breadcrumb}</div>
            <div className="canvas-actions">
              <button className="icon-button" title="Zoom out" aria-label="Zoom out" onClick={() => zoom(1.2)}><ZoomOut /></button>
              <button className="icon-button" title="Zoom in" aria-label="Zoom in" onClick={() => zoom(0.82)}><ZoomIn /></button>
              <button className="icon-button" title="Fit scene" aria-label="Fit scene" onClick={fitScene}><Maximize2 /></button>
              <button className="open-full" onClick={() => switchLevel("L4")}><Layers3 size={14} /> Open full</button>
            </div>
          </div>
          <div className="canvas-stage">
            <svg ref={svgRef} className="scene" viewBox={viewBox.join(" ")} onPointerDown={beginPan} onPointerMove={movePointer} onPointerUp={endPointer} onPointerCancel={endPointer} onWheel={(event) => { event.preventDefault(); zoom(event.deltaY > 0 ? 1.1 : 0.9); }}>
              <defs><marker id="studio-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 10 5 0 10Z" fill="context-stroke" /></marker></defs>
              <rect className="paper" width={scene.paper_width} height={scene.paper_height} />
              <g className="root-layer">{scene.nodes.filter((node) => !node.parent_scene_node_id).map(renderSceneNode)}</g>
              <g className="edge-layer">{scene.edges.map((edge) => <polyline key={edge.scene_edge_id} points={edge.points.map((point) => `${point.x},${point.y}`).join(" ")} fill="none" stroke={edge.stroke} strokeWidth={edge.width} strokeDasharray={edge.dash} markerEnd="url(#studio-arrow)" />)}</g>
              <g className="node-layer">{scene.nodes.filter((node) => node.parent_scene_node_id).map(renderSceneNode)}</g>
            </svg>
            {selectedNode && <div className="context-bar"><button title="Focus selection"><Focus size={14} /></button><button title={pinned.has(selectedNode.scene_node_id) ? "Unpin" : "Pin"} onClick={() => void submit("set-pin", selectedNode.scene_node_id, { enabled: !pinned.has(selectedNode.scene_node_id) })}>{pinned.has(selectedNode.scene_node_id) ? <PinOff size={14} /> : <Pin size={14} />}</button><button title="Expand" onClick={() => openNext(selectedNode)}><Maximize2 size={14} /></button></div>}
          </div>
        </main>

        <aside className="right-panel panel">
          <div className="panel-title"><PanelRight size={15} /> Inspector</div>
          <div className="tab-strip">{(["inspect", "visual", "model", "evidence"] as const).map((tab) => <button key={tab} className={inspectorTab === tab ? "active" : ""} onClick={() => setInspectorTab(tab)}>{tab[0].toUpperCase() + tab.slice(1)}</button>)}</div>
          {!selectedNode || !selectedViewNode ? <div className="empty-state"><Focus size={20} /><span>No selection</span></div> : <div className="inspector-content">
            {inspectorTab === "inspect" && <><h2>{selectedViewNode.semantic_name}</h2><div className="status-row"><span>Exact IR</span><b>{selectedNode.canonical_node_ids.length} canonical</b></div><Field label="Shape" value={selectedNode.secondary_label ?? "Semantic proxy"} mono /><Field label="Source symbol" value={architectureNode?.semantic_name ?? selectedCanonical ?? "—"} /><Field label="Confidence" value={selectedEvidence[0]?.confidence ?? "exact"} /><div className="resolution"><div className="section-label">Resolution</div><dl><dt>Implementation</dt><dd>{String(selectedViewNode.attributes.resolution ? "resolved" : "exact")}</dd><dt>Semantics</dt><dd>{selectedViewNode.collapsed ? "grouped" : "expanded"}</dd><dt>Execution</dt><dd>authored</dd></dl></div></>}
            {inspectorTab === "visual" && <VisualInspector node={selectedNode} pinned={pinned.has(selectedNode.scene_node_id)} onPatch={submit} />}
            {inspectorTab === "model" && <ModelInspector node={architectureNode} nodes={data.architecture.nodes} transaction={data.transaction} proposal={data.proposal} onPrepareParameter={prepareParameter} onPrepareStructural={prepareStructural} onProposeConnection={proposeConnection} onCommit={() => mutate("/api/transaction/commit", {}, "Committed source transaction")} onDiscard={() => mutate("/api/transaction/discard", {}, "Discarded source transaction")} />}
            {inspectorTab === "evidence" && <div className="evidence-list">{selectedEvidence.length ? selectedEvidence.map((record) => <section key={record.evidence_id}><div><FileCode2 size={14} /><strong>{record.kind}</strong><span>{record.confidence}</span></div><code>{record.path ?? record.evidence_id}{record.span ? `:${record.span.start_line}` : ""}</code><p>{record.claim}</p></section>) : <div className="empty-state">No linked evidence</div>}</div>}
          </div>}
        </aside>
      </div>

      <section className="bottom-panel">
        <div className="bottom-tabs"><PanelBottom size={14} />{(["problems", "diff", "validation", "activity"] as const).map((tab) => <button key={tab} className={bottomTab === tab ? "active" : ""} onClick={() => setBottomTab(tab)}>{tab === "diff" ? "Source Diff" : tab[0].toUpperCase() + tab.slice(1)}{tab === "problems" && <span>{data.diagnostics.length}</span>}</button>)}</div>
        <div className="bottom-content">{bottomTab === "problems" && (data.diagnostics.length ? data.diagnostics.map((item) => <button key={item.code} onClick={() => choose(item.target_ids[0] ?? null)}><AlertTriangle size={13} /><b>{item.severity}</b><span>{item.message}</span></button>) : <div className="ok-line"><CircleDot size={13} /> No geometry problems</div>)}{bottomTab === "diff" && (data.transaction ? <TransactionReview transaction={data.transaction} onCommit={() => mutate("/api/transaction/commit", {}, "Committed source transaction")} onDiscard={() => mutate("/api/transaction/discard", {}, "Discarded source transaction")} /> : <div className="ok-line"><LockKeyhole size={13} /> Source digest {sourceDigest} unchanged</div>)}{bottomTab === "validation" && <div className="validation-line"><CircleDot size={13} /> CanvasDocument valid · {data.document.visual_patches.length} visual patches · {data.runtime ? `${data.runtime.trace.observations.length} runtime observations` : "runtime not loaded"} · registered structural transactions available</div>}{bottomTab === "activity" && <div className="activity-list">{activity.map((item, index) => <span key={`${item}-${index}`}><History size={12} />{item}</span>)}</div>}</div>
      </section>

      <button className="theme-toggle icon-button" title="Toggle theme" aria-label="Toggle theme" onClick={() => { const next = !dark; setDark(next); void submit("set-theme", undefined, { theme: next ? "studio-dark" : "paper-light" }); }}>{dark ? <Sun /> : <Moon />}</button>
    </div>
  );
}

function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="field"><label>{label}</label><div className={mono ? "mono" : ""}>{value}</div></div>;
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

function ModelInspector({ node, nodes, transaction, proposal, onPrepareParameter, onPrepareStructural, onProposeConnection, onCommit, onDiscard }: {
  node?: StudioState["architecture"]["nodes"][number];
  nodes: StudioState["architecture"]["nodes"];
  transaction: SourceTransaction | null;
  proposal: AgentProposal | null;
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
    {active && transaction.state === "review-ready" && <div className="transaction-actions"><button className="commit-button" onClick={() => void onCommit()}><CircleDot size={14} /> Commit to source</button><button onClick={() => void onDiscard()}><X size={14} /> Discard</button></div>}
    {active && transaction.state === "failed" && <div className="transaction-actions"><button disabled title="Agent handoff arrives with structural transforms"><Braces size={14} /> Fix with Agent</button><button onClick={() => void onDiscard()}><X size={14} /> Discard</button></div>}
  </>;
}

function deltaSummary(delta?: GraphDelta): string {
  if (!delta) return "Not available";
  const nodes = delta.added_nodes.length + delta.removed_nodes.length + delta.changed_nodes.length;
  const edges = delta.added_edges.length + delta.removed_edges.length + delta.changed_edges.length;
  return `${delta.changed_parameters.length} parameters · ${nodes} nodes · ${edges} edges · ${delta.changed_shapes.length} shapes`;
}

function TransactionReview({ transaction, onCommit, onDiscard }: { transaction: SourceTransaction; onCommit: () => Promise<void>; onDiscard: () => Promise<void> }) {
  return <div className="transaction-review">
    <section><h3>Source diff</h3><pre>{transaction.source_diff || "No textual change"}</pre></section>
    <section><h3>Graph Delta</h3><dl><dt>Expected</dt><dd>{deltaSummary(transaction.expected_delta)}</dd><dt>Observed</dt><dd>{deltaSummary(transaction.observed_delta)}</dd></dl>{transaction.expected_delta.changed_parameters.map((item) => <code key={`${item.node_id}-${item.parameter_name}`}>{item.node_id}.{item.parameter_name}: {displayValue(item.before)} → {displayValue(item.after)}</code>)}</section>
    <section><h3>Validation receipt</h3><div className="gate-list">{transaction.gates.map((gate) => <span key={gate.gate} className={gate.status}>{gate.status} · {gate.gate}</span>)}</div><div className="review-actions">{transaction.state === "review-ready" ? <button className="commit-button" onClick={() => void onCommit()}><CircleDot size={14} /> Commit to source</button> : <button disabled><Braces size={14} /> Fix with Agent</button>} {!['committed', 'discarded'].includes(transaction.state) && <button onClick={() => void onDiscard()}><X size={14} /> Discard</button>}</div></section>
  </div>;
}

function VisualInspector({ node, pinned, onPatch }: { node: SceneNode; pinned: boolean; onPatch: (operation: string, targetId: string | undefined, value: Record<string, unknown>) => Promise<void> }) {
  const [bounds, setBounds] = useState(node.bounds);
  useEffect(() => setBounds(node.bounds), [node.scene_node_id, node.bounds]);
  const update = (key: keyof Rect, value: number) => setBounds((current) => ({ ...current, [key]: value }));
  return <><div className="section-label">Geometry</div><div className="numeric-grid">{(["x", "y", "width", "height"] as const).map((key) => <label key={key}><span>{key.toUpperCase()}</span><input type="number" min={key === "width" || key === "height" ? 1 : 0} value={Math.round(bounds[key])} onChange={(event) => update(key, Number(event.target.value))} /></label>)}</div><button className="apply-visual" onClick={async () => { await onPatch("set-position", node.scene_node_id, { x: bounds.x, y: bounds.y }); await onPatch("set-size", node.scene_node_id, { width: bounds.width, height: bounds.height }); }}>Apply geometry</button><label className="toggle-row"><input type="checkbox" checked={pinned} onChange={() => void onPatch("set-pin", node.scene_node_id, { enabled: !pinned })} /><span>Pin during layout</span></label><Field label="Fill" value={node.fill} mono /><Field label="Stroke" value={node.stroke} mono /></>;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
