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

interface GraphDelta {
  added_nodes: string[];
  removed_nodes: string[];
  changed_nodes: string[];
  added_edges: string[];
  removed_edges: string[];
  changed_edges: string[];
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
  request: { target_node_id: string; parameter_name: string; new_value: unknown };
  source_diff: string;
  expected_delta: GraphDelta;
  observed_delta?: GraphDelta;
  gates: Array<{ gate: string; status: string; message: string }>;
  diagnostics: Diagnostic[];
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
  capabilities: {
    visual_editing: boolean;
    source_editing: boolean;
    runtime_evidence: boolean;
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
            {inspectorTab === "model" && <ModelInspector node={architectureNode} transaction={data.transaction} onPrepare={prepareParameter} onCommit={() => mutate("/api/transaction/commit", {}, "Committed source transaction")} onDiscard={() => mutate("/api/transaction/discard", {}, "Discarded source transaction")} />}
            {inspectorTab === "evidence" && <div className="evidence-list">{selectedEvidence.length ? selectedEvidence.map((record) => <section key={record.evidence_id}><div><FileCode2 size={14} /><strong>{record.kind}</strong><span>{record.confidence}</span></div><code>{record.path ?? record.evidence_id}{record.span ? `:${record.span.start_line}` : ""}</code><p>{record.claim}</p></section>) : <div className="empty-state">No linked evidence</div>}</div>}
          </div>}
        </aside>
      </div>

      <section className="bottom-panel">
        <div className="bottom-tabs"><PanelBottom size={14} />{(["problems", "diff", "validation", "activity"] as const).map((tab) => <button key={tab} className={bottomTab === tab ? "active" : ""} onClick={() => setBottomTab(tab)}>{tab === "diff" ? "Source Diff" : tab[0].toUpperCase() + tab.slice(1)}{tab === "problems" && <span>{data.diagnostics.length}</span>}</button>)}</div>
        <div className="bottom-content">{bottomTab === "problems" && (data.diagnostics.length ? data.diagnostics.map((item) => <button key={item.code} onClick={() => choose(item.target_ids[0] ?? null)}><AlertTriangle size={13} /><b>{item.severity}</b><span>{item.message}</span></button>) : <div className="ok-line"><CircleDot size={13} /> No geometry problems</div>)}{bottomTab === "diff" && (data.transaction ? <TransactionReview transaction={data.transaction} onCommit={() => mutate("/api/transaction/commit", {}, "Committed source transaction")} onDiscard={() => mutate("/api/transaction/discard", {}, "Discarded source transaction")} /> : <div className="ok-line"><LockKeyhole size={13} /> Source digest {sourceDigest} unchanged</div>)}{bottomTab === "validation" && <div className="validation-line"><CircleDot size={13} /> CanvasDocument valid · {data.document.visual_patches.length} visual patches · {data.runtime ? `${data.runtime.trace.observations.length} runtime observations` : "runtime not loaded"} · set_parameter transactions available</div>}{bottomTab === "activity" && <div className="activity-list">{activity.map((item, index) => <span key={`${item}-${index}`}><History size={12} />{item}</span>)}</div>}</div>
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

function ModelInspector({ node, transaction, onPrepare, onCommit, onDiscard }: {
  node?: StudioState["architecture"]["nodes"][number];
  transaction: SourceTransaction | null;
  onPrepare: (parameterName: string, newValue: unknown) => Promise<void>;
  onCommit: () => Promise<void>;
  onDiscard: () => Promise<void>;
}) {
  const parameters = node?.parameters ?? [];
  const activeForNode = Boolean(transaction && transaction.request.target_node_id === node?.node_id);
  const initialName = activeForNode ? transaction?.request.parameter_name : parameters[0]?.name;
  const [name, setName] = useState(initialName ?? "");
  const parameter = parameters.find((item) => item.name === name) ?? parameters[0];
  const [value, setValue] = useState(
    activeForNode ? displayValue(transaction?.request.new_value) : parameter ? displayValue(parameter.value) : "",
  );
  useEffect(() => {
    const transactionName = transaction?.request.parameter_name;
    const transactionParameter = transaction?.request.target_node_id === node?.node_id && transactionName
      ? node?.parameters.find((item) => item.name === transactionName)
      : undefined;
    const next = transactionParameter ?? node?.parameters[0];
    setName(next?.name ?? "");
    setValue(transactionParameter ? displayValue(transaction?.request.new_value) : next ? displayValue(next.value) : "");
  }, [node?.node_id, transaction?.transaction_id]);
  useEffect(() => {
    if (parameter && !activeForNode) setValue(displayValue(parameter.value));
  }, [parameter?.name]);
  if (!node || !parameter) {
    return <div className="empty-state"><Braces size={20} /><span>No editable parameter</span></div>;
  }
  const active = transaction && transaction.request.target_node_id === node.node_id;
  const affected = active ? transaction.expected_delta.changed_nodes.length : 0;
  return <>
    <div className="transaction-banner"><GitBranch size={15} /> Safe source transaction</div>
    <label className="model-field"><span>Parameter</span><select value={parameter.name} onChange={(event) => setName(event.target.value)}>{parameters.map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}</select></label>
    <Field label="Current value" value={displayValue(parameter.value)} mono />
    <Field label="Provenance" value={`${parameter.origin} · ${parameter.source_expression}`} mono />
    <label className="model-field"><span>Target value</span><input value={value} onChange={(event) => setValue(event.target.value)} /></label>
    <Field label="Modification type" value="set_parameter" mono />
    <Field label="Expected affected nodes / edges" value={active ? `${affected} / ${transaction.expected_delta.changed_edges.length}` : "Calculated during prepare"} />
    <Field label="Risk" value={parameter.origin === "config" ? "Shared config value · exact delta required" : "Local source literal · exact anchor required"} />
    <button className="prepare-button" disabled={Boolean(transaction && !["discarded", "committed", "failed"].includes(transaction.state)) || value === displayValue(parameter.value)} onClick={() => void onPrepare(parameter.name, parseValue(value))}><GitBranch size={14} /> Prepare change</button>
    {active && <div className={`transaction-state ${transaction.state}`}>{transaction.state}</div>}
    {active && transaction.state === "review-ready" && <div className="transaction-actions"><button className="commit-button" onClick={() => void onCommit()}><CircleDot size={14} /> Commit to source</button><button onClick={() => void onDiscard()}><X size={14} /> Discard</button></div>}
    {active && transaction.state === "failed" && <div className="transaction-actions"><button disabled title="Agent handoff arrives with structural transforms"><Braces size={14} /> Fix with Agent</button><button onClick={() => void onDiscard()}><X size={14} /> Discard</button></div>}
  </>;
}

function deltaSummary(delta?: GraphDelta): string {
  if (!delta) return "Not available";
  return `${delta.changed_parameters.length} parameters · ${delta.changed_nodes.length} nodes · ${delta.changed_edges.length} edges · ${delta.changed_shapes.length} shapes`;
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
