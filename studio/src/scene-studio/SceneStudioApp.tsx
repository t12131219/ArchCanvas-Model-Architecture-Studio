import { Activity, AlertTriangle, Box, Braces, CheckCircle2, ChevronDown, ChevronRight, ChevronsDownUp, ChevronsUpDown, CornerUpLeft, Eye, FileCode2, FolderOpen, GitCompareArrows, Info, Layers3, Link2, ListChecks, LoaderCircle, LockKeyhole, Moon, PackageCheck, Pin, PinOff, Plus, RefreshCw, Search, ShieldCheck, SlidersHorizontal, Square, Sun, Trash2, Unlink, X, Play } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { compileStudioDraftPreview } from "../codegen/studio-preview";
import { isTerminalJobState } from "../jobs";
import {
  materializeDraftNode,
  MODULE_REGISTRY,
  moduleDefinitionCategory,
  moduleDefinitionLabel,
  resolveDefinitionRef,
} from "../module-registry/registry";
import type { ModuleDefinition } from "../module-registry/types";
import { analyzeGraph } from "../prototype-graph/analyze";
import type { AnalysisSnapshot } from "../prototype-graph/types";
import { App as SceneCanvas } from "./App";
import { ContractMaintenanceDialog } from "./ContractMaintenanceDialog";
import { exportSceneRaster } from "./api/scene-export-api";
import {
  beginTopologyDraft,
  connectDraftPorts,
  createDraftNode,
  deleteDraftNode,
  discardTopologyDraft,
  disconnectDraftEdge,
  submitTopologyDraft,
  updateDraftNodeParameters,
} from "./api/draft-api";
import {
  discardGeneratedProject,
  materializeGeneratedProject,
  prepareGeneratedProject,
  validateGeneratedProject,
} from "./api/generated-project-api";
import {
  cancelJob,
  browseDirectories,
  loadCondaEnvironments,
  loadJob,
  loadStudioState,
  openProject,
  searchStudio,
  setHierarchyExpansion,
  setNavigationView,
  startAnalysis,
  startValidation,
  type CondaEnvironment,
  type DirectoryBrowserState,
  type PendingProject,
  type StudioSearchResult,
} from "./api/project-api";
import { persistPinnedNodes, persistTheme, persistVisualPatch, persistVisualPatchBatch, redoVisualPatch, undoVisualPatch } from "./api/visual-api";
import { loadSourceExcerpt, type SourceExcerpt } from "./api/source-api";
import { commitSourceTransaction, discardSourceTransaction, prepareParameterTransaction, prepareStructuralTransaction } from "./api/transaction-api";
import { isStudioStatePayload, type DraftNode, type EditTargetScope, type StudioStatePayload, type ViewPresetId } from "./domain/source-backed-scene";
import { P0_VIEW_PRESETS, VIEW_PRESETS } from "./domain/view-preset";
import { projectToScene } from "./projection/project-to-scene";
import type { LabEdge, LabNode, LabScene, Selection } from "./types";
import {
  SceneStudioProvider,
  useSceneStudioDispatch,
  useSceneStudioState,
  type StudioMode,
} from "./state/store";
import "./styles.css";

const SourceWorkspace = lazy(() => import("./SourceWorkspace").then((module) => ({ default: module.SourceWorkspace })));

function parseParameterValue(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function syntheticId(kind: "node" | "edge"): string {
  return `draft:${kind}.${Date.now().toString(36)}.${crypto.randomUUID()}`;
}

function parameterText(value: unknown): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value) ?? "";
}

function DraftNodeInspector({
  source,
  node,
  analysis,
  onState,
}: {
  source: StudioStatePayload;
  node: DraftNode;
  analysis: AnalysisSnapshot | null;
  onState: (state: unknown) => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const definition = node.definition_ref ? resolveDefinitionRef(node.definition_ref) : undefined;
  const proof = source.draft?.proofs.find((item) => item.affected_subject_ids.includes(node.node_id));
  const diagnostics = analysis?.diagnostics.filter((item) => item.targetIds.includes(node.node_id)) ?? [];
  const shapeSummary = Object.entries(analysis?.nodeShapes[node.node_id] ?? {}).map(([port, value]) => {
    if (value.status === "known") return `${port}: [${value.shape.dimensions.map((item) => item.kind === "known" ? item.value : item.kind === "symbol" ? item.symbol : "?").join(", ")}]`;
    return `${port}: ${value.status}`;
  });

  useEffect(() => {
    setValues(Object.fromEntries(Object.entries(node.parameters).map(([key, value]) => [key, parameterText(value)])));
    setError(null);
  }, [node.node_id, node.parameters]);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      onState(await updateDraftNodeParameters(
        source,
        node.node_id,
        Object.fromEntries(Object.entries(values).map(([key, value]) => [key, parseParameterValue(value)])),
      ));
    } catch (mutationError) {
      setError(String(mutationError));
    } finally {
      setBusy(false);
    }
  };

  return <section className="draft-node-inspector">
    <header><div><Box size={14} /><strong>Synthetic Graph Draft</strong></div><span className={proof?.status ?? "unproven"}>{proof?.status ?? "unproven"}</span></header>
    <code>{node.node_id}</code>
    <div className="draft-port-grid">
      {node.ports.map((port) => <span key={port.port_id} className={port.direction}><b>{port.name}</b><small>{port.direction} · {port.accepted_relations?.join(", ") || "main"}</small></span>)}
    </div>
    {definition?.parameters.map((parameter) => <label key={parameter.parameter_id}>{parameter.parameter_id}<input
      value={values[parameter.parameter_id] ?? ""}
      onChange={(event) => setValues((current) => ({ ...current, [parameter.parameter_id]: event.target.value }))}
    /></label>)}
    {shapeSummary.length ? <div className="draft-shape-summary">{shapeSummary.map((line) => <code key={line}>{line}</code>)}</div> : null}
    {diagnostics.map((item) => <div className={`draft-inline-diagnostic ${item.severity}`} key={item.diagnosticId}>{item.code} · {item.message}</div>)}
    {error ? <div className="dialog-error">{error}</div> : null}
    <button className="tool-button primary-command" disabled={busy || source.edit_session?.mode !== "topology-draft"} onClick={() => void save()}>
      {busy ? <LoaderCircle className="spin" size={13} /> : <ShieldCheck size={13} />}更新实例参数
    </button>
  </section>;
}

function TopologyWorkspace({
  source,
  analysis,
  onAnalysis,
  onState,
}: {
  source: StudioStatePayload;
  analysis: AnalysisSnapshot | null;
  onAnalysis: (analysis: AnalysisSnapshot | null) => void;
  onState: (state: unknown) => void;
}) {
  const draft = source.draft;
  const editing = source.edit_session?.mode === "topology-draft";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selectedDefinition, setSelectedDefinition] = useState<ModuleDefinition | null>(null);
  const [semanticName, setSemanticName] = useState("");
  const [parameterValues, setParameterValues] = useState<Record<string, string>>({});
  const [sourcePort, setSourcePort] = useState("");
  const [targetPort, setTargetPort] = useState("");
  const [edgePolicy, setEdgePolicy] = useState<"fanout" | "replace-input">("fanout");
  const [preview, setPreview] = useState<ReturnType<typeof compileStudioDraftPreview>["preview"]>(null);
  const [previewDiagnostics, setPreviewDiagnostics] = useState<ReturnType<typeof compileStudioDraftPreview>["diagnostics"]>([]);
  const [panelOpen, setPanelOpen] = useState(false);
  const [materializeTarget, setMaterializeTarget] = useState("");

  useEffect(() => {
    let active = true;
    setPreview(null);
    setPreviewDiagnostics([]);
    if (!draft) {
      onAnalysis(null);
      return () => { active = false; };
    }
    void analyzeGraph(draft, { allowExternalBoundaries: true })
      .then((next) => { if (active) onAnalysis(next); })
      .catch((analysisError) => { if (active) setError(String(analysisError)); });
    return () => { active = false; };
  }, [draft?.revision, draft?.draft_id, onAnalysis]);

  const definitions = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return MODULE_REGISTRY.definitions.filter((definition) => !needle || [
      definition.definition_id,
      moduleDefinitionLabel(definition),
      moduleDefinitionCategory(definition),
    ].some((value) => value.toLowerCase().includes(needle)));
  }, [query]);

  const outputPorts = useMemo(() => [
    ...source.architecture.nodes.flatMap((node) => node.output_ports.map((port) => ({
      id: port.port_id,
      label: `${node.semantic_name}.${port.name} · canonical`,
    }))),
    ...(draft?.nodes.flatMap((node) => node.ports.filter((port) => port.direction === "output").map((port) => ({
      id: port.port_id,
      label: `${node.semantic_name}.${port.name} · draft`,
    }))) ?? []),
  ], [draft?.nodes, source.architecture.nodes]);
  const inputPorts = useMemo(() => [
    ...source.architecture.nodes.flatMap((node) => node.input_ports.map((port) => ({
      id: port.port_id,
      label: `${node.semantic_name}.${port.name} · canonical`,
    }))),
    ...(draft?.nodes.flatMap((node) => node.ports.filter((port) => port.direction === "input").map((port) => ({
      id: port.port_id,
      label: `${node.semantic_name}.${port.name} · draft`,
    }))) ?? []),
  ], [draft?.nodes, source.architecture.nodes]);

  useEffect(() => {
    if (!outputPorts.some((port) => port.id === sourcePort)) setSourcePort(outputPorts[0]?.id ?? "");
    if (!inputPorts.some((port) => port.id === targetPort)) setTargetPort(inputPorts[0]?.id ?? "");
  }, [inputPorts, outputPorts, sourcePort, targetPort]);

  const mutate = async (operation: () => Promise<StudioStatePayload>) => {
    setBusy(true);
    setError(null);
    try {
      onState(await operation());
    } catch (mutationError) {
      setError(String(mutationError));
    } finally {
      setBusy(false);
    }
  };

  const chooseDefinition = (definition: ModuleDefinition) => {
    setSelectedDefinition(definition);
    setSemanticName(moduleDefinitionLabel(definition).replaceAll(" ", "_").toLowerCase());
    setParameterValues(Object.fromEntries(definition.parameters.map((parameter) => [
      parameter.parameter_id,
      parameterText(parameter.default),
    ])));
  };

  const createNode = async () => {
    if (!selectedDefinition || !semanticName.trim()) return;
    const node = materializeDraftNode(
      selectedDefinition,
      syntheticId("node"),
      semanticName.trim(),
      source.project.framework,
      null,
    );
    node.parameters = Object.fromEntries(Object.entries(parameterValues).map(([key, value]) => [key, parseParameterValue(value)]));
    await mutate(() => createDraftNode(source, node));
    setSelectedDefinition(null);
  };

  const connect = async () => {
    if (!sourcePort || !targetPort) return;
    await mutate(() => connectDraftPorts(source, {
      edge_id: syntheticId("edge"),
      source_port_id: sourcePort,
      target_port_id: targetPort,
      policy: edgePolicy,
      relation: "main",
      parameters: {},
    }));
  };

  const generatePreview = () => {
    if (!draft) return;
    const result = compileStudioDraftPreview(draft);
    setPreview(result.preview);
    setPreviewDiagnostics(result.diagnostics);
  };

  const blockingCount = analysis?.diagnostics.filter((item) => item.severity === "blocking").length ?? 0;
  const writeback = draft?.writeback_summary;
  const generated = source.generated_projects?.active ?? null;
  const selectedCodegenCapability = source.capabilities?.framework_forms
    ?.find((adapter) => adapter.framework === "pytorch")
    ?.forms.find((form) => form.form_id === "form:pytorch-module-forward")
    ?.code_generation ?? "unavailable";
  const generatorCompatible = selectedCodegenCapability !== "unavailable"
    && draft?.nodes.length === 3
    && draft.edges.length === 2
    && ["archcanvas.input.tensor", "pytorch.nn.conv2d", "pytorch.nn.relu"].every((definitionId) => (
      draft.nodes.filter((node) => node.definition_ref?.definition_id === definitionId).length === 1
    ));

  if (!panelOpen) return <button className="topology-launcher" title="打开拓扑草稿工作台" aria-label="打开拓扑草稿工作台" onClick={() => setPanelOpen(true)}>
    <Box size={15} /><span>Graph Draft</span>{draft?.nodes.length ? <b>{draft.nodes.length}</b> : null}
  </button>;

  return <aside className="topology-workspace" aria-label="拓扑草稿工作台">
    <header>
      <div><LockKeyhole size={15} /><strong>Graph Draft</strong></div>
      <div className="draft-header-actions"><span className={editing ? "active" : "locked"}>{editing ? "capability active" : "visual mode"}</span><button className="icon-button" title="收起拓扑草稿工作台" onClick={() => setPanelOpen(false)}><X size={13} /></button></div>
    </header>
    {!draft || !source.edit_session ? <div className="draft-unavailable"><AlertTriangle size={16} />当前后端未提供 Graph Draft 协议。</div> : !editing ? <div className="draft-locked-state">
      <p>语义拓扑保持锁定。进入草稿模式后，命令会绑定当前 document digest 与限时 capability。</p>
      <button className="tool-button primary-command" disabled={busy || source.edit_session.mode !== "visual"} onClick={() => void mutate(() => beginTopologyDraft(source))}>
        {busy ? <LoaderCircle className="spin" size={14} /> : <LockKeyhole size={14} />}解锁拓扑草稿
      </button>
      {source.topology_review_receipt ? <div className="draft-receipt"><CheckCircle2 size={14} />{source.topology_review_receipt.status} · {source.topology_review_receipt.receipt_id}</div> : null}
    </div> : <div className="topology-workspace-body">
      <section className="draft-session-summary">
        <span><b>rev {draft.revision}</b>{draft.lowering_status}</span>
        <span><b>{draft.nodes.length}</b> nodes</span>
        <span><b>{draft.edges.length}</b> edges</span>
        <span className={blockingCount ? "blocking" : "valid"}><b>{blockingCount}</b> blocking</span>
      </section>

      <section className="registry-palette">
        <div className="section-title"><strong>Registry palette</strong><span>{MODULE_REGISTRY.definitions.length}</span></div>
        <label className="palette-search"><Search size={13} /><input aria-label="搜索模块" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索 definition 或分类" /></label>
        <div className="palette-results" role="listbox" aria-label="模块定义">
          {definitions.map((definition) => <button key={definition.definition_id} role="option" aria-selected={selectedDefinition?.definition_id === definition.definition_id} className={selectedDefinition?.definition_id === definition.definition_id ? "selected" : ""} onClick={() => chooseDefinition(definition)}>
            <Box size={13} /><span><b>{moduleDefinitionLabel(definition)}</b><small>{moduleDefinitionCategory(definition)} · {definition.ports.length} ports</small></span><Plus size={12} />
          </button>)}
        </div>
        {selectedDefinition ? <div className="draft-create-form">
          <div><strong>{moduleDefinitionLabel(selectedDefinition)}</strong><button className="icon-button" title="取消创建" onClick={() => setSelectedDefinition(null)}><X size={13} /></button></div>
          <label>语义名称<input aria-label="语义名称" value={semanticName} onChange={(event) => setSemanticName(event.target.value)} /></label>
          {selectedDefinition.parameters.map((parameter) => <label key={parameter.parameter_id}>{parameter.parameter_id}<input aria-label={parameter.parameter_id} value={parameterValues[parameter.parameter_id] ?? ""} onChange={(event) => setParameterValues((current) => ({ ...current, [parameter.parameter_id]: event.target.value }))} /></label>)}
          <button className="tool-button primary-command" disabled={busy || !semanticName.trim()} onClick={() => void createNode()}><Plus size={13} />创建草稿节点</button>
        </div> : null}
      </section>

      {draft.nodes.length ? <section className="draft-inventory">
        <div className="section-title"><strong>Synthetic nodes</strong><span>{draft.nodes.length}</span></div>
        {draft.nodes.map((node) => <div className="draft-inventory-row" key={node.node_id}>
          <Box size={13} /><span><b>{node.semantic_name}</b><small>{node.node_type}</small></span><button className="icon-button" title={`删除 ${node.semantic_name}`} disabled={busy} onClick={() => void mutate(() => deleteDraftNode(source, node.node_id))}><Trash2 size={12} /></button>
        </div>)}
      </section> : null}

      <section className="draft-connector">
        <div className="section-title"><strong>Named-port connection</strong><span>{draft.edges.length}</span></div>
        <label>输出端口<select aria-label="输出端口" value={sourcePort} onChange={(event) => setSourcePort(event.target.value)}>{outputPorts.map((port) => <option key={port.id} value={port.id}>{port.label}</option>)}</select></label>
        <label>输入端口<select aria-label="输入端口" value={targetPort} onChange={(event) => setTargetPort(event.target.value)}>{inputPorts.map((port) => <option key={port.id} value={port.id}>{port.label}</option>)}</select></label>
        <label>连接策略<select aria-label="连接策略" value={edgePolicy} onChange={(event) => setEdgePolicy(event.target.value as typeof edgePolicy)}><option value="fanout">fanout</option><option value="replace-input">replace-input</option></select></label>
        <button className="tool-button" disabled={busy || !sourcePort || !targetPort} onClick={() => void connect()}><Link2 size={13} />连接严格端口</button>
        {draft.edges.map((edge) => <div className="draft-edge-row" key={edge.edge_id}><span><code>{edge.source_port_id}</code><b>to</b><code>{edge.target_port_id}</code></span><button className="icon-button" title="断开草稿连线" disabled={busy} onClick={() => void mutate(() => disconnectDraftEdge(source, edge.edge_id))}><Unlink size={12} /></button></div>)}
      </section>

      <section className="draft-diagnostics">
        <div className="section-title"><strong>Shape & diagnostics</strong><span>{analysis?.diagnostics.length ?? 0}</span></div>
        {analysis?.diagnostics.length ? analysis.diagnostics.map((item) => <article className={item.severity} key={item.diagnosticId}><AlertTriangle size={12} /><span><b>{item.code}</b><small>{item.message}</small></span></article>) : <div className="draft-valid"><CheckCircle2 size={13} />端口、Shape 与基数检查通过</div>}
        {analysis ? <div className="draft-cost"><span>Parameters <b>{analysis.graphCost.parameterCount ?? "?"}</b></span><span>FLOPs <b>{analysis.graphCost.flops ?? "?"}</b></span></div> : null}
      </section>

      <section className="draft-codegen">
        <div className="section-title"><strong>PyTorch preview</strong><button className="icon-button" title="生成代码预览" disabled={!draft.nodes.length} onClick={generatePreview}><FileCode2 size={13} /></button></div>
        {preview ? <><pre>{preview.source}</pre><span>{Object.keys(preview.sourceMap).length} source-map bindings</span></> : previewDiagnostics.length ? <div className="draft-preview-errors">{previewDiagnostics.map((item) => <span key={item.diagnosticId}>{item.code}</span>)}</div> : null}
      </section>

      <section className="generated-project-workflow">
        <div className="section-title"><strong>Generated Source Project</strong><span>{generated?.state ?? "not prepared"}</span></div>
        {generated ? <>
          <div className="generated-project-summary">
            <span><b>{generated.files.length}</b> files</span>
            <span><b>{generated.source_map.length}</b> mappings</span>
            <span title={generated.receipt.inventory_digest}>inventory {generated.receipt.inventory_digest.slice(0, 8)}</span>
          </div>
          <div className="generated-file-list">{generated.files.map((file) => <span key={file.path}><code>{file.path}</code><small>{file.sha256.slice(0, 8)}</small></span>)}</div>
          {generated.conformance_report ? <div className={`generated-conformance ${generated.conformance_report.semantic_isomorphism}`}>
            {generated.conformance_report.semantic_isomorphism === "exact" ? <CheckCircle2 size={13} /> : <AlertTriangle size={13} />}
            <span><b>{generated.conformance_report.semantic_isomorphism}</b><small>draft-source round trip · IR {generated.conformance_report.result_exact_ir_digest.slice(0, 8)}</small></span>
          </div> : null}
          {generated.state === "review-ready" ? <label className="materialize-target">新项目目录<input aria-label="生成项目目标目录" value={materializeTarget} onChange={(event) => setMaterializeTarget(event.target.value)} placeholder="/absolute/path/new-project" /></label> : null}
          <div className="generated-project-actions">
            {generated.state === "generated-source-draft" ? <button className="tool-button primary-command" disabled={busy} onClick={() => void mutate(() => validateGeneratedProject(source))}><ShieldCheck size={13} />静态验证与重分析</button> : null}
            {generated.state === "review-ready" ? <button className="tool-button primary-command" disabled={busy || !materializeTarget.trim()} onClick={() => void mutate(() => materializeGeneratedProject(source, materializeTarget.trim()))}><PackageCheck size={13} />物化并打开</button> : null}
            {!(["opened-and-reanalyzed", "discarded"] as string[]).includes(generated.state) ? <button className="tool-button" disabled={busy} onClick={() => void mutate(() => discardGeneratedProject(source))}><X size={13} />放弃候选</button> : null}
          </div>
        </> : <button className="tool-button primary-command" disabled={busy || blockingCount > 0 || !generatorCompatible} onClick={() => void mutate(() => prepareGeneratedProject(source))}>
          <PackageCheck size={13} />准备源码工程
        </button>}
        {!generatorCompatible ? <div className="writeback-blocked"><AlertTriangle size={13} />当前固定生成器仅支持 Input → Conv2d → ReLU</div> : null}
      </section>

      {error ? <div className="dialog-error">{error}</div> : null}
      <footer>
        <button className="tool-button" disabled={busy} onClick={() => void mutate(() => discardTopologyDraft(source))}><X size={13} />放弃</button>
        <button className="tool-button primary-command" disabled={busy || !draft.nodes.length || blockingCount > 0 || writeback?.eligibility === "blocked"} onClick={() => void mutate(() => submitTopologyDraft(source))}>
          {busy ? <LoaderCircle className="spin" size={13} /> : <ShieldCheck size={13} />}提交评审
        </button>
      </footer>
      {writeback?.eligibility === "blocked" ? <div className="writeback-blocked"><AlertTriangle size={13} />源码写回被阻断 · {writeback.blocking_intent_ids.length} intents</div> : null}
    </div>}
    {error && !editing ? <div className="dialog-error">{error}</div> : null}
  </aside>;
}

function OperationsDrawer({
  source,
  draftAnalysis,
  onClose,
  onSelectCanonical,
  onRunValidation,
  onCancelJob,
}: {
  source: StudioStatePayload;
  draftAnalysis: AnalysisSnapshot | null;
  onClose: () => void;
  onSelectCanonical: (ids: string[]) => void;
  onRunValidation: (profile: "fast-static" | "publication" | "full") => void;
  onCancelJob: (jobId: string) => void;
}) {
  const [tab, setTab] = useState<"search" | "problems" | "jobs" | "conformance" | "recovery">("search");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<StudioSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [validationProfile, setValidationProfile] = useState<"fast-static" | "publication" | "full">("fast-static");

  useEffect(() => {
    if (tab !== "search") return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setSearching(true);
      setSearchError(null);
      void searchStudio(query, controller.signal)
        .then((response) => setResults(response.results))
        .catch((error) => { if (!controller.signal.aborted) setSearchError(String(error)); })
        .finally(() => { if (!controller.signal.aborted) setSearching(false); });
    }, 180);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, tab]);

  const problems = [
    ...(source.diagnostics ?? []),
    ...(source.transaction?.diagnostics ?? []),
    ...(draftAnalysis?.diagnostics.map((item) => ({
      code: item.code,
      severity: item.severity,
      message: item.message,
      target_ids: item.targetIds,
    })) ?? []),
    ...(source.validation_runs?.at(-1)?.diagnostics ?? []),
  ];
  const jobs = source.jobs ?? [];
  const conformanceReports = source.round_trip_reports ?? [];
  const recoveryReceipts = source.recovery_receipts ?? [];

  return <aside className="operations-drawer" aria-label="搜索、问题与任务">
    <header>
      <div className="operations-tabs" role="tablist">
        <button role="tab" aria-selected={tab === "search"} onClick={() => setTab("search")}><Search size={13} />搜索</button>
        <button role="tab" aria-selected={tab === "problems"} onClick={() => setTab("problems")}><ListChecks size={13} />问题 <span>{problems.length}</span></button>
        <button role="tab" aria-selected={tab === "jobs"} onClick={() => setTab("jobs")}><Activity size={13} />任务 <span>{jobs.length}</span></button>
        <button role="tab" aria-selected={tab === "conformance"} onClick={() => setTab("conformance")}><GitCompareArrows size={13} />一致性 <span>{conformanceReports.length}</span></button>
        <button role="tab" aria-selected={tab === "recovery"} onClick={() => setTab("recovery")}><ShieldCheck size={13} />恢复 <span>{recoveryReceipts.length}</span></button>
      </div>
      <button className="icon-button" title="关闭搜索、问题与任务" onClick={onClose}><X size={13} /></button>
    </header>
    <div className="operations-body">
      {tab === "search" ? <>
        <label className="operations-search"><Search size={14} /><input autoFocus aria-label="搜索语义对象" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="节点、端口、Tensor、证据或诊断" />{searching ? <LoaderCircle className="spin" size={13} /> : null}</label>
        {searchError ? <div className="dialog-error">{searchError}</div> : null}
        <div className="operations-results">{results.map((result) => <button key={result.id} onClick={() => onSelectCanonical(result.canonical_ids)}>
          <span className={`result-kind kind-${result.kind}`}>{result.kind}</span><span><b>{result.title}</b><small>{result.aliases.join(" · ") || result.id}</small></span>
        </button>)}</div>
      </> : null}
      {tab === "problems" ? <div className="problem-list">{problems.length ? problems.map((problem, index) => <article className={problem.severity} key={`${problem.code}:${index}`}>
        <AlertTriangle size={13} /><span><b>{problem.code}</b><small>{problem.message}</small><code>{problem.target_ids.join(" · ")}</code></span>
      </article>) : <div className="operations-empty"><CheckCircle2 size={17} />当前没有诊断问题</div>}</div> : null}
      {tab === "jobs" ? <>
        <div className="validation-runner"><label>验证配置<select value={validationProfile} onChange={(event) => setValidationProfile(event.target.value as typeof validationProfile)}><option value="fast-static">fast-static</option><option value="publication">publication</option><option value="full">full</option></select></label><button className="tool-button primary-command" onClick={() => onRunValidation(validationProfile)}><ShieldCheck size={13} />运行验证</button></div>
        <div className="job-list">{jobs.length ? [...jobs].reverse().map((job) => <article key={job.job_id}><Activity size={13} /><span><b>{job.profile}</b><small>{job.state} · {Math.round(job.progress * 100)}%</small></span>{!isTerminalJobState(job.state) ? <button className="icon-button" title="取消任务" onClick={() => onCancelJob(job.job_id)}><Square size={11} /></button> : null}</article>) : <div className="operations-empty">没有任务记录</div>}</div>
      </> : null}
      {tab === "conformance" ? <div className="conformance-list">{conformanceReports.length ? [...conformanceReports].reverse().map((report) => <article className={report.semantic_isomorphism} key={report.report_id}>
        {report.semantic_isomorphism === "failed" ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
        <span><b>{report.path}</b><small>{report.semantic_isomorphism} · IR {report.result_exact_ir_digest.slice(0, 12)}</small><code>{report.report_id}</code></span>
        <div className="conformance-meta"><span>{report.source_writes.length} writes</span><span>{report.diagnostics.length} diagnostics</span></div>
      </article>) : <div className="operations-empty">没有一致性报告</div>}</div> : null}
      {tab === "recovery" ? <div className="recovery-list">{recoveryReceipts.length ? [...recoveryReceipts].reverse().map((receipt) => <article className={receipt.outcome} key={receipt.receipt_id}>
        {receipt.outcome === "recovery-failed" ? <AlertTriangle size={14} /> : <ShieldCheck size={14} />}
        <span><b>{receipt.outcome}</b><small>{receipt.journal_state} · {receipt.recovered_files.length} 个恢复文件</small><code>{receipt.transaction_id}</code></span>
        <div className="conformance-meta"><span>before {receipt.before_state_proven ? "proved" : "unknown"}</span><span>after {receipt.after_state_proven ? "proved" : "unknown"}</span></div>
      </article>) : <div className="operations-empty">没有崩溃恢复记录</div>}</div> : null}
    </div>
  </aside>;
}

type NavigationProjection = "module" | "source";

function StudioNavigation({
  source,
  scene,
  onState,
  onSelect,
}: {
  source: StudioStatePayload;
  scene?: ReturnType<typeof projectToScene>;
  onState: (state: unknown) => void;
  onSelect: (selection: Selection) => void;
}) {
  const [projection, setProjection] = useState<NavigationProjection>(source.navigation?.active_projection ?? "module");
  const [query, setQuery] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const navigation = source.navigation;
  const rows = navigation?.projections[projection].nodes ?? [];
  const expandedIds = projection === "module"
    ? source.view_state?.module_expansion ?? []
    : source.view_state?.source_expansion ?? [];
  const expanded = useMemo(() => new Set(expandedIds), [expandedIds]);
  const byId = useMemo(() => new Map(rows.map((row) => [row.id, row])), [rows]);
  const visibleRows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (needle) {
      const included = new Set<string>();
      for (const row of rows) {
        if (!`${row.label} ${row.secondary_label ?? ""} ${row.kind} ${row.path ?? ""}`.toLowerCase().includes(needle)) continue;
        let current: typeof row | undefined = row;
        while (current) {
          included.add(current.id);
          current = current.parent_id ? byId.get(current.parent_id) : undefined;
        }
      }
      return rows.filter((row) => included.has(row.id));
    }
    return rows.filter((row) => {
      let parentId = row.parent_id;
      while (parentId) {
        if (!expanded.has(parentId)) return false;
        parentId = byId.get(parentId)?.parent_id ?? null;
      }
      return true;
    });
  }, [byId, expanded, query, rows]);

  const saveNavigation = async (nextProjection: NavigationProjection, nextExpanded: Set<string>) => {
    const expansions = {
      module: nextProjection === "module" ? [...nextExpanded] : source.view_state?.module_expansion ?? [],
      source: nextProjection === "source" ? [...nextExpanded] : source.view_state?.source_expansion ?? [],
    };
    onState(await setNavigationView(source, nextProjection, expansions));
  };

  const changeProjection = (next: NavigationProjection) => {
    setProjection(next);
    const nextExpanded = new Set(next === "module" ? source.view_state?.module_expansion ?? [] : source.view_state?.source_expansion ?? []);
    void saveNavigation(next, nextExpanded);
  };

  const toggle = (id: string) => {
    const next = new Set(expanded);
    if (next.has(id)) next.delete(id); else next.add(id);
    setBusyId(id);
    void saveNavigation(projection, next).finally(() => setBusyId(null));
  };

  const setAllExpanded = (shouldExpand: boolean) => {
    const next = shouldExpand
      ? new Set(rows.filter((row) => row.child_count > 0).map((row) => row.id))
      : new Set<string>();
    setBusyId("navigation:all");
    void saveNavigation(projection, next).finally(() => setBusyId(null));
  };

  const selectRow = (canonicalIds: string[]) => {
    const targets = new Set(canonicalIds.filter((id) => id.startsWith("node:")));
    const node = scene?.nodes.find((item) => item.canonical_node_ids?.some((id) => targets.has(id)));
    onSelect(node ? { kind: "node", id: node.scene_node_id } : null);
  };

  if (!navigation) return <div className="navigation-empty"><Layers3 size={18} /><strong>导航尚未生成</strong><span>重新分析项目以构建模块与源码关系。</span></div>;
  return <div className="studio-navigation">
    <div className="navigation-tabs" role="tablist" aria-label="项目导航">
      <button role="tab" aria-selected={projection === "module"} onClick={() => changeProjection("module")}><Layers3 size={13} />模块</button>
      <button role="tab" aria-selected={projection === "source"} onClick={() => changeProjection("source")}><FileCode2 size={13} />源码</button>
    </div>
    <label className="navigation-search"><Search size={13} /><input aria-label="搜索导航" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={projection === "module" ? "搜索模块" : "搜索文件或符号"} /></label>
    <div className="navigation-summary">
      <span>{navigation.projections[projection].description}</span>
      <b>{rows.length}</b>
      <button
        className="icon-button"
        title={projection === "module" ? "全部展开源码层级" : "全部展开源码树"}
        disabled={busyId !== null}
        onClick={() => setAllExpanded(true)}
      >
        <ChevronsUpDown size={12} />
      </button>
      <button
        className="icon-button"
        title={projection === "module" ? "全部收起源码层级" : "全部收起源码树"}
        disabled={busyId !== null || expanded.size === 0}
        onClick={() => setAllExpanded(false)}
      >
        <ChevronsDownUp size={12} />
      </button>
    </div>
    <div className="navigation-tree" role="tree" aria-label={navigation.projections[projection].label}>
      {visibleRows.map((row) => <div
        className={`navigation-row kind-${row.kind} ${row.reference ? "reference" : ""}`}
        key={row.id}
        role="treeitem"
        aria-expanded={row.child_count ? expanded.has(row.id) : undefined}
        style={{ "--tree-depth": row.depth } as React.CSSProperties}
      >
        {row.child_count ? <button className="tree-toggle" aria-label={`${expanded.has(row.id) ? "收起" : "展开"}${row.label}`} disabled={busyId === row.id} onClick={() => toggle(row.id)}>{expanded.has(row.id) ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</button> : <span className="tree-spacer" />}
        <button className="tree-label" title={row.path ? `${row.path}${row.span ? `:${row.span.start_line}` : ""}` : row.label} onClick={() => selectRow(row.canonical_ids)}>
          <span>{row.label}</span><small>{row.secondary_label ?? row.kind}</small>
        </button>
      </div>)}
      {!visibleRows.length ? <div className="navigation-empty compact">没有匹配项</div> : null}
    </div>
  </div>;
}

type EvidenceSection = "all" | "source" | "model" | "evidence";

function SourceEvidencePanel({ node, onState, section = "all" }: { node: LabNode; onState: (state: unknown) => void; section?: EvidenceSection }) {
  const studio = useSceneStudioState();
  const source = studio.projectSlice.source;
  const [excerpt, setExcerpt] = useState<SourceExcerpt | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [parameterName, setParameterName] = useState("");
  const [parameterValue, setParameterValue] = useState("");
  const [editScope, setEditScope] = useState<EditTargetScope | "">("");
  const [preparing, setPreparing] = useState(false);
  const [structuralOperation, setStructuralOperation] = useState<"replace_activation" | "insert_layer_norm">("replace_activation");
  const [replacement, setReplacement] = useState("ReLU");
  const [moduleName, setModuleName] = useState("layer_norm");
  const [normalizedShape, setNormalizedShape] = useState("d_model");
  const evidence = useMemo(() => {
    const ids = new Set(node.evidence_ids ?? []);
    return source?.evidence.filter((item) => ids.has(item.evidence_id)) ?? [];
  }, [node.evidence_ids, source?.evidence]);
  const active = evidence.find((item) => item.path && item.span);
  const canonicalId = node.canonical_node_ids?.length === 1 ? node.canonical_node_ids[0] : null;
  const canonicalNode = canonicalId ? source?.architecture.nodes.find((item) => item.node_id === canonicalId) : undefined;
  const parameters = canonicalNode?.parameters ?? [];
  const activeParameter = parameters.find((parameter) => parameter.name === parameterName) ?? parameters[0];
  const parameterContext = source?.parameter_edit_contexts?.find((context) => (
    context.target_node_id === canonicalId && context.parameter_name === activeParameter?.name
  ));
  const structuralCapabilities = useMemo(() => {
    if (!source || !canonicalNode || !canonicalId) return [];
    const advertised = new Set(source.capabilities?.semantic_transforms ?? []);
    const sourceRecords = evidence.filter((item) => item.kind === "source" && item.path && item.span);
    const definition = sourceRecords.find((item) => item.evidence_id.includes(".init."));
    const flow = sourceRecords.find((item) => (
      item.evidence_id.includes(".forward.")
      || item.evidence_id.includes(".call.")
      || item.evidence_id.includes(".id-__call__.")
    ));
    const framework = source.project.framework;
    const opType = String(canonicalNode.attributes.op_type ?? "");
    const modulePath = String(canonicalNode.attributes.module_path ?? "");
    const assignedSymbol = String(canonicalNode.attributes.assigned_symbol ?? "");
    const hasAnchorPair = framework === "jax"
      ? Boolean(flow)
      : Boolean(definition && flow && definition.path === flow.path);
    if (!hasAnchorPair) return [];

    const applicable: Array<"replace_activation" | "insert_layer_norm"> = [];
    const explicitActivation = framework === "pytorch"
      ? ["nn.GELU", "nn.ReLU", "nn.SiLU"].includes(opType) && modulePath.startsWith("self.")
      : framework === "keras"
        ? opType === "layers.Activation" && canonicalNode.parameters?.some((item) => item.name === "arg0" && ["gelu", "relu", "silu"].includes(String(item.value)))
        : framework === "jax"
          ? ["nn.gelu", "nn.relu", "nn.silu", "jax.nn.gelu", "jax.nn.relu", "jax.nn.silu", "jnp.tanh"].includes(opType)
          : false;
    if (advertised.has("replace_activation") && explicitActivation) applicable.push("replace_activation");

    const outgoing = source.architecture.edges.filter((edge) => edge.producer_id === canonicalId);
    const directSequentialOutput = ["pytorch", "keras"].includes(framework)
      && modulePath.startsWith("self.")
      && !canonicalNode.attributes.functional_anchor
      && Boolean(assignedSymbol)
      && outgoing.length === 1;
    if (advertised.has("insert_layer_norm") && directSequentialOutput) applicable.push("insert_layer_norm");
    return applicable;
  }, [canonicalId, canonicalNode, evidence, source]);

  useEffect(() => {
    if (structuralCapabilities.includes(structuralOperation)) return;
    const first = structuralCapabilities[0];
    if (first) setStructuralOperation(first);
  }, [structuralCapabilities, structuralOperation]);

  useEffect(() => {
    if (!activeParameter) {
      setParameterName("");
      setParameterValue("");
      return;
    }
    setParameterName(activeParameter.name);
    setParameterValue(typeof activeParameter.value === "string" ? activeParameter.value : JSON.stringify(activeParameter.value));
    const context = source?.parameter_edit_contexts?.find((item) => (
      item.target_node_id === canonicalId && item.parameter_name === activeParameter.name
    ));
    setEditScope(context?.default_scope ?? context?.allowed_scopes[0] ?? "");
  }, [activeParameter?.name, canonicalId, source?.parameter_edit_contexts]);

  useEffect(() => {
    setExcerpt(null);
    setError(null);
    if (!active?.path || !active.span) return;
    const controller = new AbortController();
    loadSourceExcerpt(active.path, active.span.start_line, active.span.end_line, controller.signal)
      .then(setExcerpt)
      .catch((loadError) => {
        if (!controller.signal.aborted) setError(String(loadError));
      });
    return () => controller.abort();
  }, [active?.evidence_id, active?.path, active?.span?.end_line, active?.span?.start_line]);

  const showSource = section === "all" || section === "source";
  const showEvidence = section === "all" || section === "evidence";
  const showModel = section === "all" || section === "model";
  if (!evidence.length && !parameters.length && !(canonicalId && structuralCapabilities.length)) return <div className="inspector-empty-state">当前对象没有可用的源码证据或模型操作。</div>;
  return <>
  {showEvidence && evidence.length ? <section className="source-evidence-panel">
    <header><strong>证据与源码</strong><span>{evidence.length}</span></header>
    <div className="evidence-records">
      {evidence.slice(0, 4).map((item) => <article key={item.evidence_id}>
        <div><b>{item.kind}</b><span>{item.confidence}</span></div>
        <p>{item.claim}</p>
        {item.path ? <code>{item.path}{item.span ? `:${item.span.start_line}` : ""}</code> : null}
      </article>)}
    </div>
  </section> : null}
  {showSource ? <section className="source-evidence-panel source-only-panel">
    <header><strong>源码定位</strong><span>{active?.path ?? "无锚点"}</span></header>
    {excerpt ? <div className="source-excerpt">
      <div><strong>{excerpt.path}</strong><span>{excerpt.revision}</span></div>
      <pre>{excerpt.lines.map((line) => <span key={line.number} className={line.number >= excerpt.highlight_start_line && line.number <= excerpt.highlight_end_line ? "highlight" : ""}>
        <i>{line.number}</i>{line.text || " "}
      </span>)}</pre>
    </div> : error ? <div className="excerpt-error">{error}</div> : active ? <div className="excerpt-loading"><LoaderCircle className="spin" size={13} />读取源码片段</div> : null}
    {!active ? <div className="inspector-empty-state">当前聚合视图没有唯一源码锚点，请在模块树中选择更细粒度对象。</div> : null}
  </section> : null}
  {showModel && source && parameters.length && canonicalId ? <section className="parameter-transaction-panel">
    <header><strong>参数事务</strong><span>精确锚点</span></header>
    <label>参数<select value={activeParameter?.name ?? ""} onChange={(event) => {
      const selected = parameters.find((parameter) => parameter.name === event.target.value);
      setParameterName(event.target.value);
      setParameterValue(typeof selected?.value === "string" ? selected.value : JSON.stringify(selected?.value));
    }}>
      {parameters.map((parameter) => <option key={parameter.name} value={parameter.name}>{parameter.name}</option>)}
    </select></label>
    <label>新值<input value={parameterValue} onChange={(event) => setParameterValue(event.target.value)} /></label>
    <div className="parameter-origin"><span>来源</span><code>{parameterContext?.value_origin.kind ?? activeParameter?.origin ?? "unknown"}</code><span>置信度</span><code>{parameterContext?.value_origin.confidence ?? "unknown"}</code><span>表达式</span><code>{activeParameter?.source_expression ?? "-"}</code></div>
    {parameterContext?.allowed_scopes.length ? <label>编辑作用域<select value={editScope} onChange={(event) => setEditScope(event.target.value as EditTargetScope)}>
      {parameterContext.allowed_scopes.map((scope) => <option key={scope} value={scope}>{scope}</option>)}
    </select></label> : null}
    {parameterContext ? <div className={`parameter-impact ${parameterContext.value_origin.editability}`}>
      <span>{parameterContext.value_origin.editability}</span>
      <b>{parameterContext.affected_canonical_ids.length} 个受影响对象</b>
      <code>{parameterContext.affected_canonical_ids.join(" · ")}</code>
      {parameterContext.blocking_reason ? <small>{parameterContext.blocking_reason}</small> : null}
    </div> : null}
    <button className="tool-button primary-command" disabled={preparing || !source.capabilities?.source_editing || parameterContext?.value_origin.editability !== "direct" || !editScope} onClick={() => {
      setPreparing(true);
      setError(null);
      void prepareParameterTransaction(source, canonicalId, activeParameter!.name, parseParameterValue(parameterValue), parameterContext!, editScope as EditTargetScope)
        .then(onState)
        .catch((prepareError) => setError(String(prepareError)))
        .finally(() => setPreparing(false));
    }}>{preparing ? <LoaderCircle className="spin" size={14} /> : <Braces size={14} />}准备并验证</button>
  </section> : null}
  {showModel && source && canonicalId && structuralCapabilities.length ? <section className="structural-transaction-panel">
    <header><strong>结构事务</strong><span>LibCST adapter</span></header>
    <label>操作<select value={structuralOperation} onChange={(event) => setStructuralOperation(event.target.value as typeof structuralOperation)}>
      <option value="replace_activation" disabled={!structuralCapabilities.includes("replace_activation")}>替换激活函数</option>
      <option value="insert_layer_norm" disabled={!structuralCapabilities.includes("insert_layer_norm")}>插入 LayerNorm</option>
    </select></label>
    {structuralOperation === "replace_activation" ? <label>替换为<select value={replacement} onChange={(event) => setReplacement(event.target.value)}><option>ReLU</option><option>GELU</option><option>SiLU</option></select></label> : <>
      <label>模块名<input value={moduleName} onChange={(event) => setModuleName(event.target.value)} /></label>
      <label>normalized_shape<input value={normalizedShape} onChange={(event) => setNormalizedShape(event.target.value)} /></label>
    </>}
    <button className="tool-button primary-command" disabled={preparing || !structuralCapabilities.includes(structuralOperation) || Boolean(source.transaction && !["committed", "discarded", "failed"].includes(source.transaction.state))} onClick={() => {
      setPreparing(true);
      setError(null);
      const parameters = structuralOperation === "replace_activation"
        ? { replacement }
        : { module_name: moduleName, normalized_shape: normalizedShape };
      void prepareStructuralTransaction(source, canonicalId, structuralOperation, parameters)
        .then(onState)
        .catch((prepareError) => setError(String(prepareError)))
        .finally(() => setPreparing(false));
    }}>{preparing ? <LoaderCircle className="spin" size={14} /> : <GitCompareArrows size={14} />}准备结构变换</button>
    <div className="unsupported-structure"><AlertTriangle size={12} />任意 connect/delete 没有 adapter proof 时保持 proposal-only。</div>
  </section> : null}
  {showModel && error ? <div className="excerpt-error">{error}</div> : null}
  </>;
}

type InspectorTab = "overview" | "source" | "visual" | "model" | "evidence";

function StudioInspector({
  source,
  node,
  edge,
  scene,
  updateNode,
  draftAnalysis,
  onState,
  onOpenSourceWorkspace,
  onOpenContractMaintenance,
  pinned,
  onTogglePinned,
  onHierarchyExpand,
  onHierarchyCollapse,
}: {
  source: StudioStatePayload;
  node?: LabNode;
  edge?: LabEdge;
  scene: LabScene;
  updateNode: (changes: Partial<Omit<LabNode, "scene_node_id">>) => void;
  draftAnalysis: AnalysisSnapshot | null;
  onState: (state: unknown) => void;
  onOpenSourceWorkspace: () => void;
  onOpenContractMaintenance: () => void;
  pinned: boolean;
  onTogglePinned: () => void;
  onHierarchyExpand: (id: string) => void;
  onHierarchyCollapse: (id: string) => void;
}) {
  const [tab, setTab] = useState<InspectorTab>("overview");
  const canonicalIds = node?.canonical_node_ids ?? [];
  const canonicalNodes = source.architecture.nodes.filter((item) => canonicalIds.includes(item.node_id));
  const inputPorts = [...new Map(canonicalNodes.flatMap((item) => item.input_ports).map((port) => [port.role, port])).values()];
  const outputPorts = [...new Map(canonicalNodes.flatMap((item) => item.output_ports).map((port) => [port.role, port])).values()];
  const draftNode = node?.draft_node_id ? source.draft?.nodes.find((item) => item.node_id === node.draft_node_id) : undefined;

  const setBound = (key: "x" | "y" | "width" | "height", raw: string) => {
    if (!node) return;
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) return;
    const value = key === "width" ? Math.max(72, Math.min(640, parsed))
      : key === "height" ? Math.max(42, Math.min(1200, parsed))
        : parsed;
    updateNode({ bounds: { ...node.bounds, [key]: value } });
  };

  return <div className="studio-inspector">
    <div className="inspector-tabs" role="tablist" aria-label="对象检查器">
      {([
        ["overview", "概览", Info],
        ["source", "源码", FileCode2],
        ["visual", "视觉", Eye],
        ["model", "模型", SlidersHorizontal],
        ["evidence", "证据", ShieldCheck],
      ] as const).map(([id, label, Icon]) => <button key={id} role="tab" title={label} aria-label={label} aria-selected={tab === id} onClick={() => setTab(id)}><Icon size={13} /><span>{label}</span></button>)}
    </div>
    <div className="studio-inspector-body">
      {!node && !edge ? <div className="project-inspector-summary">
        <strong>{source.architecture.entrypoint}</strong>
        <span>{source.project.framework} · generation {source.project.generation}</span>
        <dl><div><dt>语义节点</dt><dd>{source.architecture.nodes.length}</dd></div><div><dt>事实边</dt><dd>{source.architecture.edges.length}</dd></div><div><dt>层级节点</dt><dd>{source.hierarchy.nodes.length}</dd></div><div><dt>当前视图</dt><dd>{scene.nodes.length} / {scene.edges.length}</dd></div></dl>
      </div> : null}

      {tab === "overview" && node ? <section className="inspector-section overview-section">
        <div className="selection-title"><span>{node.fidelity ?? "schematic"} · {node.shape}</span><strong>{node.label}</strong><small>{node.secondary_label}</small></div>
        <dl className="object-facts">
          <div><dt>视图对象</dt><dd><code>{node.scene_node_id}</code></dd></div>
          <div><dt>层级</dt><dd>{node.hierarchy_node_id ?? "visual slot"}</dd></div>
          <div><dt>输入 / 输出端口</dt><dd>{inputPorts.length} / {outputPorts.length}</dd></div>
          <div><dt>源码证据</dt><dd>{node.evidence_ids?.length ?? 0}</dd></div>
        </dl>
        {canonicalIds.length ? <div className="canonical-list"><strong>Canonical bindings</strong>{canonicalIds.map((id) => <code key={id}>{id}</code>)}</div> : <div className="schematic-notice"><Info size={13} />此节点是结构 profile 的 schematic 槽位，不冒充 Exact IR 对象。</div>}
        {inputPorts.length || outputPorts.length ? <div className="port-summary"><strong>Named ports</strong>{inputPorts.map((port) => <span key={port.port_id}><i>IN</i><code>{port.role}</code></span>)}{outputPorts.map((port) => <span key={port.port_id}><i>OUT</i><code>{port.role}</code></span>)}</div> : null}
      </section> : null}
      {tab === "overview" && edge ? <section className="inspector-section overview-section"><div className="selection-title"><span>连线 · {edge.relation}</span><strong>{edge.label || edge.relation}</strong></div><dl className="object-facts"><div><dt>起点</dt><dd>{edge.source_scene_node_id}</dd></div><div><dt>终点</dt><dd>{edge.target_scene_node_id}</dd></div><div><dt>事实绑定</dt><dd>{edge.canonical_edge_ids?.length ?? 0}</dd></div></dl></section> : null}

      {tab === "source" && node ? <><SourceEvidencePanel node={node} onState={onState} section="source" />{source.source_workspace ? <button className="tool-button inspector-wide-command" onClick={onOpenSourceWorkspace}><FileCode2 size={13} />打开源码工作区</button> : null}</> : null}

      {tab === "visual" && node ? <section className="inspector-section visual-inspector-section">
        <div className="field-grid"><label>X<input type="number" value={Math.round(node.bounds.x)} onChange={(event) => setBound("x", event.target.value)} /></label><label>Y<input type="number" value={Math.round(node.bounds.y)} onChange={(event) => setBound("y", event.target.value)} /></label><label>宽度<input type="number" value={Math.round(node.bounds.width)} onChange={(event) => setBound("width", event.target.value)} /></label><label>高度<input type="number" value={Math.round(node.bounds.height)} onChange={(event) => setBound("height", event.target.value)} /></label></div>
        <dl className="object-facts"><div><dt>泳道</dt><dd>{node.layout_lane ?? "自由布局"}</dd></div><div><dt>排序</dt><dd>{node.layout_rank ?? "-"}</dd></div><div><dt>视觉语调</dt><dd>{node.paper_tone ?? "default"}</dd></div></dl>
        <button className="tool-button inspector-wide-command" onClick={onTogglePinned}>{pinned ? <PinOff size={13} /> : <Pin size={13} />}{pinned ? "取消固定节点" : "固定节点位置"}</button>
        {node.hierarchy_expandable && node.hierarchy_node_id ? <button className="tool-button inspector-wide-command" onClick={() => onHierarchyExpand(node.hierarchy_node_id!)}><Plus size={13} />展开源码层级</button> : null}
        {node.parent_hierarchy_node_id ? <button className="tool-button inspector-wide-command" onClick={() => onHierarchyCollapse(node.parent_hierarchy_node_id!)}><ChevronRight size={13} />收起父层级</button> : null}
      </section> : null}

      {tab === "model" ? <>{node ? (draftNode
        ? <DraftNodeInspector source={source} node={draftNode} analysis={draftAnalysis} onState={onState} />
        : <SourceEvidencePanel node={node} onState={onState} section="model" />) : null}
        <button className="tool-button inspector-wide-command" onClick={onOpenContractMaintenance}><ShieldCheck size={13} />模块契约维护</button>
      </> : null}

      {tab === "evidence" && node ? <SourceEvidencePanel node={node} onState={onState} section="evidence" /> : null}
      {((tab !== "overview" && tab !== "model" && !node) || (tab === "visual" && edge) || (tab === "source" && edge) || (tab === "evidence" && edge)) ? <div className="inspector-empty-state">选择一个模块或节点以查看此页签。</div> : null}
    </div>
  </div>;
}

function TransactionDrawer({
  source,
  busy,
  onCommit,
  onDiscard,
}: {
  source: NonNullable<ReturnType<typeof useSceneStudioState>["projectSlice"]["source"]>;
  busy: boolean;
  onCommit: () => void;
  onDiscard: () => void;
}) {
  const transaction = source.transaction;
  if (!transaction || ["committed", "discarded"].includes(transaction.state)) return null;
  const migrationPlan = transaction.state_migration_plan;
  const stateCompatibility = migrationPlan?.status ?? "not-bound";
  const sourceCompatibility = transaction.state === "review-ready" ? "verified" : transaction.state;
  return <aside className="transaction-drawer" aria-label="源码事务审查">
    <header><div><GitCompareArrows size={16} /><strong>源码事务审查</strong></div><span>{transaction.state}</span></header>
    <div className="transaction-body">
      <section><h3>源码差异</h3><pre>{transaction.source_diff || "没有文本变化"}</pre></section>
      <section className="delta-grid">
        <div><h3>Expected Graph Delta</h3><pre>{JSON.stringify(transaction.expected_delta, null, 2)}</pre></div>
        <div><h3>Observed Graph Delta</h3><pre>{JSON.stringify(transaction.observed_delta ?? {}, null, 2)}</pre></div>
      </section>
      <section><h3>提交与状态兼容性</h3><div className="compatibility-grid">
        <span><small>source</small><b>{sourceCompatibility}</b></span>
        <span><small>checkpoint/state</small><b>{stateCompatibility}</b></span>
        <span><small>training resume</small><b>{migrationPlan ? "blocked" : "not-bound"}</b></span>
        <span><small>inference</small><b>{stateCompatibility}</b></span>
      </div>{migrationPlan ? <div className="state-migration-warning"><AlertTriangle size={13} /><span>状态迁移计划 {migrationPlan.plan_id} 为 {migrationPlan.status}；当前只能 source-only 提交，原 checkpoint 不再视为已绑定。</span></div> : <div className="state-migration-note"><LockKeyhole size={13} />未绑定 checkpoint/state asset。</div>}</section>
      <section><h3>验证门</h3><div className="transaction-gates">{transaction.gates.map((gate) => <span key={gate.gate} className={gate.status}><ShieldCheck size={12} />{gate.status} · {gate.gate}</span>)}</div></section>
    </div>
    <footer>
      <button className="tool-button" disabled={busy} onClick={onDiscard}><X size={14} />放弃</button>
      <button className="tool-button primary-command" disabled={busy || transaction.state !== "review-ready"} onClick={onCommit}>{busy ? <LoaderCircle className="spin" size={14} /> : <CheckCircle2 size={14} />}{migrationPlan ? "仅提交源码" : "提交到源码"}</button>
    </footer>
  </aside>;
}

function SceneStudioWorkspace() {
  const state = useSceneStudioState();
  const dispatch = useSceneStudioDispatch();
  const [projectDialogOpen, setProjectDialogOpen] = useState(false);
  const [projectRoot, setProjectRoot] = useState("");
  const [environments, setEnvironments] = useState<CondaEnvironment[]>([]);
  const [environmentPath, setEnvironmentPath] = useState("");
  const [pendingProject, setPendingProject] = useState<PendingProject | null>(null);
  const [folderBrowser, setFolderBrowser] = useState<DirectoryBrowserState | null>(null);
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);
  const [folderLoading, setFolderLoading] = useState(false);
  const [entrypoint, setEntrypoint] = useState("");
  const [frameworkFormId, setFrameworkFormId] = useState("");
  const [configPath, setConfigPath] = useState("");
  const [invocationMode, setInvocationMode] = useState<"eval" | "train">("eval");
  const [constructorArgs, setConstructorArgs] = useState("[]");
  const [constructorKwargs, setConstructorKwargs] = useState("{}");
  const [forwardArgs, setForwardArgs] = useState("[]");
  const [forwardKwargs, setForwardKwargs] = useState("{}");
  const [staticArgs, setStaticArgs] = useState("{}");
  const [inputStructure, setInputStructure] = useState("null");
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [transactionBusy, setTransactionBusy] = useState(false);
  const [draftAnalysis, setDraftAnalysis] = useState<AnalysisSnapshot | null>(null);
  const [operationsOpen, setOperationsOpen] = useState(false);
  const [sourceWorkspaceOpen, setSourceWorkspaceOpen] = useState(false);
  const [contractMaintenanceOpen, setContractMaintenanceOpen] = useState(false);
  const activeJobIdRef = useRef<string | null>(null);
  const visualQueueRef = useRef<Promise<void>>(Promise.resolve());
  const navigationQueueRef = useRef<Promise<void>>(Promise.resolve());

  const acceptSource = useCallback((source: unknown) => {
    if (!isStudioStatePayload(source)) throw new Error("后端返回的 StudioState 缺少 Exact Architecture IR 字段");
    const scenes = P0_VIEW_PRESETS.map((presetId) => projectToScene(source, presetId));
    dispatch({ type: "source-loaded", source, scenes });
  }, [dispatch]);

  const hydrate = useCallback(async (signal?: AbortSignal) => {
    try {
      const source = await loadStudioState(signal);
      acceptSource(source);
    } catch (error) {
      if (signal?.aborted) return;
      dispatch({ type: "status", status: "idle", error: String(error) });
    }
  }, [acceptSource, dispatch]);

  useEffect(() => {
    const controller = new AbortController();
    void hydrate(controller.signal);
    return () => controller.abort();
  }, [hydrate]);

  useEffect(() => () => {
    activeJobIdRef.current = null;
  }, []);

  const activeSceneId = state.projectSlice.source
    ? `source:${state.projectSlice.source.project.project_id}:${state.viewSlice.presetId}`
    : undefined;
  const sourceScenes = useMemo(() => state.viewSlice.scenes, [state.viewSlice.scenes]);
  // Opening a replacement project is transactional from the workspace's point of
  // view: keep the current analyzed scene visible until the new analysis succeeds.
  const sourceReady = Boolean(state.projectSlice.source) && sourceScenes.length > 0;
  const activeScene = sourceScenes.find((item) => item.scene_id === activeSceneId) ?? sourceScenes[0];
  const sourceAnchor = useMemo(() => {
    const source = state.projectSlice.source;
    const selection = state.viewSlice.selection;
    if (!source || selection?.kind !== "node") return null;
    const scene = sourceScenes.find((item) => item.scene_id === activeSceneId) ?? sourceScenes[0];
    const node = scene?.nodes.find((item) => item.scene_node_id === selection.id);
    const evidenceIds = new Set(node?.evidence_ids ?? []);
    const record = source.evidence.find((item) => evidenceIds.has(item.evidence_id) && item.path && item.span);
    return record?.path && record.span ? { path: record.path, line: record.span.start_line } : null;
  }, [activeSceneId, sourceScenes, state.projectSlice.source, state.viewSlice.selection]);

  const openSourceDialog = useCallback(async () => {
    setProjectDialogOpen(true);
    setDialogError(null);
    if (environments.length) return;
    try {
      const result = await loadCondaEnvironments();
      setEnvironments(result.environments);
      setEnvironmentPath(result.selected ?? result.environments.find((item) => item.active)?.path ?? "");
    } catch {
      setEnvironments([]);
    }
  }, [environments.length]);

  const scanProject = useCallback(async () => {
    if (!projectRoot.trim()) return;
    setDialogError(null);
    dispatch({ type: "status", status: "opening" });
    try {
      const result = await openProject(projectRoot.trim(), environmentPath || null, state.projectSlice.source?.session_nonce);
      setPendingProject(result);
      const first = result.discovery.entrypoints[0];
      setEntrypoint(first?.entrypoint ?? "");
      const adapter = result.framework_forms.find((item) => item.framework === first?.framework);
      setFrameworkFormId(adapter?.forms[0]?.form_id ?? "form:python-callable");
      setConfigPath(first?.config_paths[0] ?? result.discovery.configs[0]?.path ?? "");
      dispatch({ type: "status", status: state.projectSlice.source ? "ready" : "idle" });
    } catch (error) {
      setDialogError(String(error));
      dispatch({
        type: "status",
        status: state.projectSlice.source ? "ready" : "error",
        error: String(error),
      });
    }
  }, [dispatch, environmentPath, projectRoot, state.projectSlice.source]);

  const browseFolders = useCallback(async (path?: string) => {
    setFolderLoading(true);
    setDialogError(null);
    try {
      setFolderBrowser(await browseDirectories(path));
      setSelectedFolder(null);
    } catch (error) {
      setDialogError(String(error));
    } finally {
      setFolderLoading(false);
    }
  }, []);

  const pollAnalysis = useCallback(async (jobId: string) => {
    while (activeJobIdRef.current === jobId) {
      const job = await loadJob(jobId);
      dispatch({ type: "job", job });
      if (isTerminalJobState(job.state)) {
        activeJobIdRef.current = null;
        if (job.state === "succeeded") {
          await hydrate();
          setProjectDialogOpen(false);
        } else {
          const message = `分析任务 ${job.state}`;
          setDialogError(message);
          dispatch({ type: "status", status: "error", error: message });
        }
        return;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 400));
    }
  }, [dispatch, hydrate]);

  const analyzeProject = useCallback(async () => {
    if (!pendingProject || !entrypoint) return;
    setDialogError(null);
    dispatch({ type: "status", status: "analyzing" });
    try {
      const parsedConstructorArgs = JSON.parse(constructorArgs) as unknown;
      const parsedConstructorKwargs = JSON.parse(constructorKwargs) as unknown;
      const parsedForwardArgs = JSON.parse(forwardArgs) as unknown;
      const parsedForwardKwargs = JSON.parse(forwardKwargs) as unknown;
      const parsedStaticArgs = JSON.parse(staticArgs) as unknown;
      if (!Array.isArray(parsedConstructorArgs) || !Array.isArray(parsedForwardArgs)) {
        throw new Error("constructor args 与 forward args 必须是 JSON 数组");
      }
      if (!parsedConstructorKwargs || Array.isArray(parsedConstructorKwargs) || typeof parsedConstructorKwargs !== "object"
        || !parsedForwardKwargs || Array.isArray(parsedForwardKwargs) || typeof parsedForwardKwargs !== "object"
        || !parsedStaticArgs || Array.isArray(parsedStaticArgs) || typeof parsedStaticArgs !== "object") {
        throw new Error("kwargs 与 static args 必须是 JSON 对象");
      }
      const selected = pendingProject.discovery.entrypoints.find((item) => item.entrypoint === entrypoint);
      const job = await startAnalysis({
        project_id: pendingProject.project.project_id,
        project_generation: pendingProject.project.generation,
        entrypoint,
        framework: selected?.framework || pendingProject.project.framework || "auto",
        form_id: frameworkFormId,
        task: "inference",
        config_path: configPath || null,
        execution_mode: "static",
        pattern_packs_enabled: true,
        entry_invocation: {
          schema_version: "1.0",
          constructor_args: parsedConstructorArgs,
          constructor_kwargs: parsedConstructorKwargs as Record<string, unknown>,
          forward_args: parsedForwardArgs,
          forward_kwargs: parsedForwardKwargs as Record<string, unknown>,
          static_args: parsedStaticArgs as Record<string, unknown>,
          mode: invocationMode,
          input_structure: JSON.parse(inputStructure) as unknown,
        },
        request_id: `request:${crypto.randomUUID()}`,
      }, state.projectSlice.source?.session_nonce);
      activeJobIdRef.current = job.job_id;
      dispatch({ type: "job", job });
      void pollAnalysis(job.job_id);
    } catch (error) {
      setDialogError(String(error));
      dispatch({ type: "status", status: "error", error: String(error) });
    }
  }, [configPath, constructorArgs, constructorKwargs, dispatch, entrypoint, forwardArgs, forwardKwargs, frameworkFormId, inputStructure, invocationMode, pendingProject, pollAnalysis, state.projectSlice.source?.session_nonce, staticArgs]);

  const stopAnalysis = useCallback(async () => {
    const jobId = activeJobIdRef.current;
    if (!jobId) return;
    const job = await cancelJob(jobId, state.projectSlice.source?.session_nonce);
    dispatch({ type: "job", job });
  }, [dispatch, state.projectSlice.source?.session_nonce]);

  const runValidation = useCallback(async (profile: "fast-static" | "publication" | "full") => {
    const source = state.projectSlice.source;
    if (!source) return;
    try {
      const job = await startValidation(profile, source.session_nonce);
      activeJobIdRef.current = job.job_id;
      dispatch({ type: "job", job });
      void pollAnalysis(job.job_id);
    } catch (error) {
      dispatch({ type: "status", status: "error", error: String(error) });
    }
  }, [dispatch, pollAnalysis, state.projectSlice.source]);

  const cancelListedJob = useCallback(async (jobId: string) => {
    const source = state.projectSlice.source;
    if (!source) return;
    try {
      const job = await cancelJob(jobId, source.session_nonce);
      dispatch({ type: "job", job });
      await hydrate();
    } catch (error) {
      dispatch({ type: "status", status: "error", error: String(error) });
    }
  }, [dispatch, hydrate, state.projectSlice.source]);

  const persistPatch = useCallback((patch: Parameters<typeof persistVisualPatch>[1], scene: Parameters<typeof persistVisualPatch>[2]) => {
    dispatch({ type: "visual-patch", patch });
    const source = state.projectSlice.source;
    if (!source) return;
    visualQueueRef.current = visualQueueRef.current.then(async () => {
      const next = await persistVisualPatch(source, patch, scene);
      if (next) acceptSource(next);
    }).catch((error) => dispatch({ type: "status", status: "error", error: String(error) }));
  }, [acceptSource, dispatch, state.projectSlice.source]);

  const persistPatchBatch = useCallback((
    patches: Parameters<typeof persistVisualPatchBatch>[1],
    scene: Parameters<typeof persistVisualPatchBatch>[2],
    description: string,
  ) => {
    const source = state.projectSlice.source;
    if (!source) return;
    visualQueueRef.current = visualQueueRef.current.then(async () => {
      const next = await persistVisualPatchBatch(source, patches, scene, description);
      if (next) acceptSource(next);
    }).catch((error) => dispatch({ type: "status", status: "error", error: String(error) }));
  }, [acceptSource, dispatch, state.projectSlice.source]);

  const persistPins = useCallback((sceneNodeIds: readonly string[], enabled: boolean, scene: Parameters<typeof persistPinnedNodes>[1]) => {
    const source = state.projectSlice.source;
    if (!source) return;
    visualQueueRef.current = visualQueueRef.current.then(async () => {
      const next = await persistPinnedNodes(source, scene, sceneNodeIds, enabled);
      if (next) acceptSource(next);
    }).catch((error) => dispatch({ type: "status", status: "error", error: String(error) }));
  }, [acceptSource, dispatch, state.projectSlice.source]);

  const updateTheme = useCallback(() => {
    const source = state.projectSlice.source;
    if (!source) return;
    const nextTheme = source.view_state?.theme === "studio-dark" ? "paper-light" : "studio-dark";
    visualQueueRef.current = visualQueueRef.current.then(async () => {
      acceptSource(await persistTheme(source, nextTheme));
    }).catch((error) => dispatch({ type: "status", status: "error", error: String(error) }));
  }, [acceptSource, dispatch, state.projectSlice.source]);

  const persistHistory = useCallback((direction: "undo" | "redo") => {
    const source = state.projectSlice.source;
    if (!source) return;
    visualQueueRef.current = visualQueueRef.current.then(async () => {
      const next = direction === "undo" ? await undoVisualPatch(source) : await redoVisualPatch(source);
      acceptSource(next);
    }).catch((error) => dispatch({ type: "status", status: "error", error: String(error) }));
  }, [acceptSource, dispatch, state.projectSlice.source]);

  const updateHierarchy = useCallback((operation: "expand" | "collapse" | "expand-all" | "collapse-all", hierarchyNodeId?: string) => {
    const source = state.projectSlice.source;
    if (!source) return;
    const expanded = new Set(source.view_state?.module_expansion ?? []);
    if (operation === "expand" && hierarchyNodeId) expanded.add(hierarchyNodeId);
    if (operation === "collapse" && hierarchyNodeId) expanded.delete(hierarchyNodeId);
    if (operation === "collapse-all") expanded.clear();
    if (operation === "expand-all") {
      const parentIds = new Set(source.hierarchy.nodes.flatMap((item) => item.parent_hierarchy_node_id ? [item.parent_hierarchy_node_id] : []));
      parentIds.forEach((id) => {
        if (id !== source.hierarchy.root_node_id) expanded.add(id);
      });
    }
    navigationQueueRef.current = navigationQueueRef.current.then(async () => {
      const next = await setHierarchyExpansion(source, [...expanded]);
      acceptSource(next);
    }).catch((error) => dispatch({ type: "status", status: "error", error: String(error) }));
  }, [acceptSource, dispatch, state.projectSlice.source]);

  const handleSelectionChange = useCallback((selection: Selection) => {
    dispatch({ type: "selection", selection });
  }, [dispatch]);

  const commitTransaction = useCallback(async () => {
    const source = state.projectSlice.source;
    if (!source?.transaction) return;
    setTransactionBusy(true);
    try {
      const next = await commitSourceTransaction(source);
      acceptSource(next);
      if (next.reanalysis_job_id) {
        activeJobIdRef.current = next.reanalysis_job_id;
        void pollAnalysis(next.reanalysis_job_id);
      }
    } catch (error) {
      dispatch({ type: "status", status: "error", error: String(error) });
    } finally {
      setTransactionBusy(false);
    }
  }, [acceptSource, dispatch, pollAnalysis, state.projectSlice.source]);

  const discardTransaction = useCallback(async () => {
    const source = state.projectSlice.source;
    if (!source?.transaction) return;
    setTransactionBusy(true);
    try {
      acceptSource(await discardSourceTransaction(source));
    } catch (error) {
      dispatch({ type: "status", status: "error", error: String(error) });
    } finally {
      setTransactionBusy(false);
    }
  }, [acceptSource, dispatch, state.projectSlice.source]);

  const toolbar = <>
    <div className="source-toolbar" aria-label="源码项目与视图">
      <button className="tool-button" onClick={() => void openSourceDialog()}><FolderOpen size={14} />从源码构建</button>
      {sourceReady ? <label className="preset-control">
        <span>视图</span>
        <select value={state.viewSlice.presetId} onChange={(event) => dispatch({ type: "preset", presetId: event.target.value as ViewPresetId })}>
          {P0_VIEW_PRESETS.map((id) => <option key={id} value={id}>{VIEW_PRESETS[id].label}</option>)}
        </select>
      </label> : null}
      <button className="icon-button" title="重新加载分析状态" onClick={() => void hydrate()}><RefreshCw size={14} /></button>
      {sourceReady ? <>
        <button className="icon-button" title="打开搜索、问题与任务" onClick={() => setOperationsOpen(true)}><Search size={14} /></button>
        <button className="icon-button" title={state.projectSlice.source?.view_state?.theme === "studio-dark" ? "切换浅色主题" : "切换深色主题"} onClick={updateTheme}>{state.projectSlice.source?.view_state?.theme === "studio-dark" ? <Sun size={14} /> : <Moon size={14} />}</button>
      </> : null}
    </div>
    <div className="mode-switch" aria-label="工作模式">
      {(["explore", "layout", "model"] as StudioMode[]).map((mode) => <button
        key={mode}
        className={state.interactionSlice.mode === mode ? "active" : ""}
        aria-pressed={state.interactionSlice.mode === mode}
        onClick={() => dispatch({ type: "mode", mode })}
      >{{ explore: "浏览", layout: "布局", model: "模型" }[mode]}</button>)}
    </div>
    <span className={`source-state source-state-${state.projectSlice.status}`} title={state.projectSlice.error ?? undefined}>
      {state.projectSlice.status === "booting" && "连接后端"}
      {state.projectSlice.status === "idle" && "未打开项目"}
      {state.projectSlice.status === "ready" && `${state.projectSlice.source?.project.project_id} · IR ${state.semanticSlice.exactIrDigest?.slice(0, 8) ?? "-"}`}
      {state.projectSlice.status === "opening" && "发现入口"}
      {state.projectSlice.status === "analyzing" && `分析 ${Math.round((state.jobSlice.active?.progress ?? 0) * 100)}%`}
      {state.projectSlice.status === "error" && "分析失败"}
    </span>
  </>;

  const theme = state.projectSlice.source?.view_state?.theme ?? "paper-light";
  const pinnedTargets = new Set(state.projectSlice.source?.view_state?.pinned_node_ids ?? []);
  const pinnedSceneNodeIds = sourceScenes.flatMap((scene) => scene.nodes.flatMap((node) => (
    node.hierarchy_node_id && pinnedTargets.has(`view:${node.hierarchy_node_id}`)
      ? [node.scene_node_id]
      : []
  )));

  return <div className={`scene-studio-root theme-${theme}`}>
    <SceneCanvas
      scenes={sourceReady ? sourceScenes : []}
      initialSceneId={activeSceneId}
      productLabel="Model Architecture Studio"
      collectionLabel={sourceReady ? "源码视图" : "工作区"}
      toolbarContent={toolbar}
      navigationContent={sourceReady && state.projectSlice.source ? <StudioNavigation
        source={state.projectSlice.source}
        scene={activeScene}
        onState={acceptSource}
        onSelect={handleSelectionChange}
      /> : undefined}
      renderInspectorPanel={state.projectSlice.source ? ({ node, edge, scene, updateNode }) => <StudioInspector
        source={state.projectSlice.source!}
        node={node}
        edge={edge}
        scene={scene}
        updateNode={updateNode}
        draftAnalysis={draftAnalysis}
        onState={acceptSource}
        onOpenSourceWorkspace={() => setSourceWorkspaceOpen(true)}
        onOpenContractMaintenance={() => setContractMaintenanceOpen(true)}
        pinned={Boolean(node && pinnedSceneNodeIds.includes(node.scene_node_id))}
        onTogglePinned={() => {
          if (!node) return;
          persistPins([node.scene_node_id], !pinnedSceneNodeIds.includes(node.scene_node_id), scene);
        }}
        onHierarchyExpand={(id) => updateHierarchy("expand", id)}
        onHierarchyCollapse={(id) => updateHierarchy("collapse", id)}
      /> : undefined}
      showCaseMatrix={false}
      allowAutomaticLayout={state.viewSlice.presetId !== "paper-publication"}
      layoutToolsEnabled={state.interactionSlice.mode === "layout"}
      collapsiblePanels
      selection={state.viewSlice.selection}
      readOnlySemantic={state.interactionSlice.mode !== "model" || sourceReady}
      onSelectionChange={handleSelectionChange}
      onVisualPatch={persistPatch}
      onVisualPatchBatch={persistPatchBatch}
      onPinNodes={persistPins}
      pinnedNodeIds={pinnedSceneNodeIds}
      onUndo={() => persistHistory("undo")}
      onRedo={() => persistHistory("redo")}
      canUndo={Boolean(state.projectSlice.source?.document.visual_patches?.length)}
      canRedo={Boolean(state.projectSlice.source?.document.redo_patches?.length)}
      onHierarchyExpand={(id) => updateHierarchy("expand", id)}
      onHierarchyCollapse={(id) => updateHierarchy("collapse", id)}
      exportRaster={(svg, format) => exportSceneRaster(
        svg,
        format,
        state.projectSlice.source?.session_nonce,
      )}
    />

    {state.interactionSlice.mode === "model" && state.projectSlice.source ? <TopologyWorkspace
      source={state.projectSlice.source}
      analysis={draftAnalysis}
      onAnalysis={setDraftAnalysis}
      onState={acceptSource}
    /> : null}

    {operationsOpen && state.projectSlice.source ? <OperationsDrawer
      source={state.projectSlice.source}
      draftAnalysis={draftAnalysis}
      onClose={() => setOperationsOpen(false)}
      onSelectCanonical={(ids) => {
        const scene = sourceScenes.find((item) => item.scene_id === activeSceneId) ?? sourceScenes[0];
        const targets = new Set(ids);
        const node = scene?.nodes.find((item) => item.canonical_node_ids?.some((id) => targets.has(id)));
        if (node) {
          dispatch({ type: "selection", selection: { kind: "node", id: node.scene_node_id } });
          setOperationsOpen(false);
        }
      }}
      onRunValidation={(profile) => void runValidation(profile)}
      onCancelJob={(jobId) => void cancelListedJob(jobId)}
    /> : null}

    {sourceWorkspaceOpen && state.projectSlice.source?.source_workspace ? <Suspense fallback={<div className="source-workspace-loading"><LoaderCircle className="spin" size={16} />加载源码编辑器</div>}><SourceWorkspace
      source={state.projectSlice.source}
      anchor={sourceAnchor}
      onState={acceptSource}
      onClose={() => setSourceWorkspaceOpen(false)}
    /></Suspense> : null}

    {projectDialogOpen ? <div className="source-dialog-backdrop" role="presentation">
      <section className="source-dialog" role="dialog" aria-modal="true" aria-labelledby="source-dialog-title">
        <header>
          <div><strong id="source-dialog-title">从源码构建</strong><span>静态分析，不导入或执行用户工程</span></div>
          <button className="icon-button" title="关闭" onClick={() => setProjectDialogOpen(false)}><X size={15} /></button>
        </header>
        <div className="source-dialog-body">
          <label>项目根目录<div className="path-input-row"><input value={projectRoot} onChange={(event) => setProjectRoot(event.target.value)} placeholder="/path/to/project" /><button className="icon-button" title="浏览目录" onClick={() => void browseFolders(projectRoot || state.projectSlice.source?.project.root)}><FolderOpen size={14} /></button></div></label>
          {folderBrowser ? <section className="folder-browser" aria-label="选择项目目录">
            <div className="folder-breadcrumbs">{folderBrowser.breadcrumbs.map((crumb) => <button key={crumb.path} onClick={() => void browseFolders(crumb.path)}>{crumb.name}</button>)}</div>
            <div className="folder-browser-toolbar"><button className="icon-button" title="上级目录" disabled={!folderBrowser.parent || folderLoading} onClick={() => folderBrowser.parent && void browseFolders(folderBrowser.parent)}><CornerUpLeft size={13} /></button><code>{folderBrowser.path}</code>{folderLoading ? <LoaderCircle className="spin" size={13} /> : null}</div>
            <div className="folder-browser-list">{folderBrowser.directories.map((directory) => <button key={directory.path} className={selectedFolder === directory.path ? "selected" : ""} aria-pressed={selectedFolder === directory.path} onClick={() => setSelectedFolder(directory.path)} onDoubleClick={() => void browseFolders(directory.path)}><FolderOpen size={13} /><span>{directory.name}</span></button>)}{!folderBrowser.directories.length ? <span>当前目录没有子目录</span> : null}</div>
            <footer><button className="tool-button" onClick={() => setFolderBrowser(null)}>取消</button><button className="tool-button primary-command" onClick={() => { setProjectRoot(selectedFolder ?? folderBrowser.path); setPendingProject(null); setFolderBrowser(null); }}>选择此目录</button></footer>
          </section> : null}
          <label>分析环境<select value={environmentPath} onChange={(event) => setEnvironmentPath(event.target.value)}>
            <option value="">当前服务环境</option>
            {environments.map((environment) => <option key={environment.path} value={environment.path}>{environment.name} · {environment.python}</option>)}
          </select></label>
          <button className="tool-button primary-command" disabled={!projectRoot.trim() || state.projectSlice.status === "opening"} onClick={() => void scanProject()}>
            {state.projectSlice.status === "opening" ? <LoaderCircle className="spin" size={15} /> : <FolderOpen size={15} />}发现入口
          </button>
          {pendingProject ? <div className="analysis-config">
            <div className="analysis-summary"><strong>{pendingProject.discovery.scanned_files}</strong><span>个源码文件</span><strong>{pendingProject.discovery.entrypoints.length}</strong><span>个入口</span></div>
            <label>入口<select value={entrypoint} onChange={(event) => {
              const value = event.target.value;
              setEntrypoint(value);
              const selected = pendingProject.discovery.entrypoints.find((item) => item.entrypoint === value);
              setConfigPath(selected?.config_paths[0] ?? "");
              const adapter = pendingProject.framework_forms.find((item) => item.framework === selected?.framework);
              setFrameworkFormId(adapter?.forms[0]?.form_id ?? "form:python-callable");
            }}>
              {pendingProject.discovery.entrypoints.map((item) => <option key={item.entrypoint} value={item.entrypoint}>{item.entrypoint} · {item.confidence}</option>)}
            </select></label>
            <label>配置文件<select value={configPath} onChange={(event) => setConfigPath(event.target.value)}>
              <option value="">无</option>
              {pendingProject.discovery.configs.map((config) => <option key={config.path} value={config.path}>{config.path}</option>)}
            </select></label>
            <label>源码形态<select value={frameworkFormId} onChange={(event) => setFrameworkFormId(event.target.value)}>
              {pendingProject.framework_forms.find((item) => item.framework === pendingProject.discovery.entrypoints.find((candidate) => candidate.entrypoint === entrypoint)?.framework)?.forms.map((form) => <option key={form.form_id} value={form.form_id} disabled={form.static_analysis === "unavailable"}>{form.form_name} · {form.static_analysis}</option>)}
            </select></label>
            <label>运行模式<select value={invocationMode} onChange={(event) => setInvocationMode(event.target.value as "eval" | "train")}><option value="eval">eval</option><option value="train">train</option></select></label>
            <label>构造位置参数<textarea rows={2} value={constructorArgs} onChange={(event) => setConstructorArgs(event.target.value)} spellCheck={false} /></label>
            <label>构造关键字参数<textarea rows={2} value={constructorKwargs} onChange={(event) => setConstructorKwargs(event.target.value)} spellCheck={false} /></label>
            <label>forward 位置参数<textarea rows={2} value={forwardArgs} onChange={(event) => setForwardArgs(event.target.value)} spellCheck={false} /></label>
            <label>forward 关键字参数<textarea rows={2} value={forwardKwargs} onChange={(event) => setForwardKwargs(event.target.value)} spellCheck={false} /></label>
            <label>静态参数<textarea rows={2} value={staticArgs} onChange={(event) => setStaticArgs(event.target.value)} spellCheck={false} /></label>
            <label>输入结构<textarea rows={2} value={inputStructure} onChange={(event) => setInputStructure(event.target.value)} spellCheck={false} /></label>
          </div> : null}
          {dialogError ? <div className="dialog-error">{dialogError}</div> : null}
        </div>
        <footer>
          {activeJobIdRef.current ? <button className="tool-button" onClick={() => void stopAnalysis()}><Square size={14} />取消分析</button> : null}
          <button className="tool-button" onClick={() => setProjectDialogOpen(false)}>关闭</button>
          <button className="tool-button primary-command" disabled={!pendingProject || !entrypoint || Boolean(activeJobIdRef.current)} onClick={() => void analyzeProject()}>
            {activeJobIdRef.current ? <LoaderCircle className="spin" size={15} /> : <Play size={15} />}开始静态分析
          </button>
        </footer>
      </section>
    </div> : null}
    {state.projectSlice.source ? <TransactionDrawer
      source={state.projectSlice.source}
      busy={transactionBusy}
      onCommit={() => void commitTransaction()}
      onDiscard={() => void discardTransaction()}
    /> : null}
    {contractMaintenanceOpen && state.projectSlice.source ? <ContractMaintenanceDialog
      open
      state={state.projectSlice.source}
      onClose={() => setContractMaintenanceOpen(false)}
      onState={acceptSource}
    /> : null}
  </div>;
}

export function SceneStudioApp() {
  return <SceneStudioProvider><SceneStudioWorkspace /></SceneStudioProvider>;
}

export default SceneStudioApp;
