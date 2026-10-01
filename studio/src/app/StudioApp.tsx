import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Box,
  Braces,
  ChevronDown,
  ChevronRight,
  CircleDot,
  CornerDownLeft,
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
  PanelRight,
  Pin,
  PinOff,
  Play,
  Plus,
  RefreshCw,
  Route,
  Search,
  Settings2,
  ShieldCheck,
  Sun,
  Trash2,
  Variable,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";

import type { PrintedPyTorchDraft } from "../codegen/pytorch-ir";
import { compileStudioDraftPreview } from "../codegen/studio-preview";
import { JobPollingController, type StudioJob } from "../jobs";
import { initialProjectSelection } from "../project-launch";
import { createStudioActions, patchId } from "./studio-actions";
import {
  browseDirectories,
  loadCondaEnvironments,
  loadStudioState,
  openProject as openProjectRequest,
  previewCanonicalDelete,
  searchStudio,
  startAnalysis,
  startValidation,
  type AnalysisRequest,
  type CondaEnvironment,
  type DirectoryBrowserState,
  type PendingProject,
  type ProjectEntrypoint,
} from "./project-actions";
import { cancelStudioJob, pollStudioJob } from "./job-actions";
import {
  visibleNavigationRows,
} from "../tree";
import { ArchitectureCanvas } from "../main-view/ArchitectureCanvas";
import { SourceWorkspacePanel } from "../inspector/SourceWorkspacePanel";
import { TransactionReview } from "../inspector/TransactionReview";
import { ContractMaintenanceDialog } from "../inspector/ContractMaintenanceDialog";
import {
  EdgeInspector,
  Field,
  InspectorLanguageContext,
  ModelInspector,
  SourceInspector,
  StructureInspector,
  VisualInspector,
} from "../inspector/InspectorPanels";
import { ProjectDialogs } from "../inspector/ProjectDialogs";
import {
  downloadKernelPdf,
  downloadKernelPng,
  downloadKernelSvg,
} from "../main-view/export-download";
import { adaptFormalState, type FormalStudioState } from "../main-view/formal-state-adapter";
import { materializeDraftNode, resolveDefinitionId } from "../module-registry/registry";
import { analyzeGraph } from "../prototype-graph/analyze";
import type { AnalysisSnapshot, AnalyzedValue, DimensionValue } from "../prototype-graph/types";
import type { KernelExportArtifact } from "../visual-kernel/export";
import { buildKernelRenderScene } from "../visual-kernel/layout";
import type { Bounds as Rect, Point, RenderEdge, RenderNode } from "../visual-kernel/types";
import {
  BottomPanel,
  InspectorPanel,
  NavigationPanel,
  PanelResizers,
  shellLayoutStyle,
  TopBar,
  type PanelResizeEdge,
  type StudioLocale,
  type StudioMode,
} from "../shell/StudioShell";
import type {
  AgentProposal,
  ArchitectureNodeView,
  ArchitectureParameter,
  ArchitectureTensor,
  CanonicalDeleteImpact,
  Diagnostic,
  DraftEdgePolicy,
  Evidence,
  LayoutMode,
  Projection,
  PublicationNode,
  SourceExcerpt,
  SourceTransaction,
  StudioState,
} from "./studio-types";
import { embeddedStudioState, initialExpansionState, StudioStateAcceptance } from "./studio-state";
import "../styles.css";

type Mode = StudioMode;
type Locale = StudioLocale;

interface LanguageContextValue {
  locale: Locale;
  tx: (english: string, chinese: string) => string;
}

const LanguageContext = React.createContext<LanguageContextValue>({
  locale: "zh",
  tx: (_english, chinese) => chinese,
});

function useLanguage(): LanguageContextValue {
  return React.useContext(LanguageContext);
}



interface PanelSizes {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

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

function dimensionLabel(value: DimensionValue): string {
  if (value.kind === "known") return String(value.value);
  if (value.kind === "symbol") return value.symbol;
  if (value.kind === "expression") return value.expression;
  return "?";
}

function analyzedValueLabel(value: AnalyzedValue | undefined): string {
  if (!value) return "?";
  if (value.status === "blocked") return "blocked";
  if (value.status === "unknown") return "unknown";
  return `[${value.shape.dimensions.map(dimensionLabel).join(",")}]`;
}

export function StudioApp() {
  const initialState = useMemo(() => embeddedStudioState(), []);
  const [locale, setLocale] = useState<Locale>(() => {
    const stored = window.localStorage.getItem("archcanvas.locale");
    return stored === "en" || stored === "zh" ? stored : "zh";
  });
  const tx = (english: string, chinese: string) => locale === "zh" ? chinese : english;
  const [data, setData] = useState<StudioState | null>(initialState);
  const [draftAnalysis, setDraftAnalysis] = useState<AnalysisSnapshot | null>(null);
  const [codegenPreview, setCodegenPreview] = useState<PrintedPyTorchDraft | null>(null);
  const [codegenRequested, setCodegenRequested] = useState(false);
  const [projection, setProjection] = useState<Projection>(
    () => initialState?.navigation?.active_projection ?? initialState?.view_state.navigation_view ?? "module",
  );
  const [expansions, setExpansions] = useState<Record<Projection, Set<string>>>(() => initialExpansionState(initialState));
  const [mode, setMode] = useState<Mode>("explore");
  const [selectedCanonicalIds, setSelectedCanonicalIds] = useState<string[]>([]);
  const [selectedCanonicalEdgeIds, setSelectedCanonicalEdgeIds] = useState<string[]>([]);
  const [focusedCanonicalId, setFocusedCanonicalId] = useState<string | null>(null);
  const [focusedNavigationRowId, setFocusedNavigationRowId] = useState<string | null>(null);
  const [inspectorTab, setInspectorTab] = useState<"inspect" | "source" | "visual" | "model" | "evidence">("inspect");
  const [bottomTab, setBottomTab] = useState<"problems" | "source" | "diff" | "validation" | "jobs" | "activity">("problems");
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [validationProfile, setValidationProfile] = useState("fast-static");
  const [projectDialog, setProjectDialog] = useState(true);
  const [draftDialog, setDraftDialog] = useState(false);
  const [contractDialog, setContractDialog] = useState(false);
  const [draftParameterNodeId, setDraftParameterNodeId] = useState<string | null>(null);
  const [draftName, setDraftName] = useState("");
  const [draftType, setDraftType] = useState("");
  const [draftEdgeDialog, setDraftEdgeDialog] = useState(false);
  const [draftEdgeSource, setDraftEdgeSource] = useState("");
  const [draftEdgeTarget, setDraftEdgeTarget] = useState("");
  const [draftEdgePolicy, setDraftEdgePolicy] = useState<DraftEdgePolicy>("fanout");
  const [deleteImpact, setDeleteImpact] = useState<CanonicalDeleteImpact | null>(null);
  const [deleteImpactLoading, setDeleteImpactLoading] = useState(false);
  const [projectRoot, setProjectRoot] = useState(() => initialState?.project.root ?? "");
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
  const [dark, setDark] = useState(() => initialState?.view_state.theme === "studio-dark");
  const [panelSizes, setPanelSizes] = useState<PanelSizes>(storedPanelSizes);
  const [panelResize, setPanelResize] = useState<PanelResizeState | null>(null);
  const [activity, setActivity] = useState<string[]>([tx("Studio document opened", "Studio 文档已打开")]);
  const [kernelExport, setKernelExport] = useState<KernelExportArtifact | null>(null);
  const [exportBusy, setExportBusy] = useState<"png" | "pdf" | null>(null);
  const exportMenuRef = useRef<HTMLDetailsElement>(null);
  const acceptKernelExport = useCallback((artifact: KernelExportArtifact) => {
    setKernelExport((current) => current?.renderDigest === artifact.renderDigest ? current : artifact);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setCodegenPreview(null);
    if (!data) {
      setDraftAnalysis(null);
      return () => { cancelled = true; };
    }
    void analyzeGraph(data.draft, { allowExternalBoundaries: true }).then((snapshot) => {
      if (!cancelled) setDraftAnalysis(snapshot);
    });
    return () => { cancelled = true; };
  }, [data?.draft.revision]);
  const navigationTimer = useRef<number | null>(null);
  const navigationQueue = useRef<Promise<void>>(Promise.resolve());
  const expansionsRef = useRef(expansions);
  const navigationTouched = useRef(false);
  const stateAcceptance = useRef(new StudioStateAcceptance(initialState));
  const pendingHierarchyFocus = useRef<string | null>(null);
  const jobController = useRef<JobPollingController<StudioState> | null>(null);
  if (jobController.current === null) {
    jobController.current = new JobPollingController<StudioState>(
      window.fetch.bind(window),
      (state) => acceptStudioState(state),
    );
  }

  function restoreNavigationState(state: StudioState) {
    const restored = initialExpansionState(state);
    expansionsRef.current = restored;
    setExpansions(restored);
    setProjection(state.navigation.active_projection ?? state.view_state.navigation_view ?? "module");
  }

  function acceptStudioState(state: StudioState): boolean {
    const { modelChanged } = stateAcceptance.current.accept(state);
    if (modelChanged) {
      navigationTouched.current = false;
      restoreNavigationState(state);
      setSelectedCanonicalIds([]);
      setSelectedCanonicalEdgeIds([]);
      setFocusedCanonicalId(null);
      setFocusedNavigationRowId(null);
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
      loadCondaEnvironments(controller.signal)
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
    loadStudioState()
      .then((state: StudioState) => {
        if (!navigationTouched.current) {
          restoreNavigationState(state);
        }
        acceptStudioState(state);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => () => {
    if (navigationTimer.current !== null) window.clearTimeout(navigationTimer.current);
    jobController.current?.dispose();
  }, []);

  const kernel = useMemo(() => {
    if (!data) return undefined;
    const adapted = adaptFormalState(data as unknown as FormalStudioState);
    return {
      ...adapted,
      scene: buildKernelRenderScene(adapted.document, adapted.visualState),
    };
  }, [data]);
  const scene = kernel?.scene;
  const view = activeProjectionId ? data?.views[activeProjectionId] : undefined;
  const pinned = useMemo(() => new Set(data?.view_state.pinned_node_ids ?? []), [data?.view_state.pinned_node_ids]);

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
      searchStudio(query, controller.signal)
        .then((payload) => setSearchResults(payload.results))
        .catch(() => undefined);
    }, 120);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [query, data?.document.source_digest]);

  const selectedNode = [...(scene?.nodes ?? [])]
    .sort((left, right) => right.depth - left.depth)
    .find((node) => [...node.canonicalNodeIds, ...node.containedCanonicalNodeIds]
      .some((id) => selectedCanonicalIds.includes(id))) ?? null;
  const selectedTemplateFidelity = selectedNode?.templateBindingId
    ? kernel?.document.templateBindings.find((binding) => binding.bindingId === selectedNode.templateBindingId)?.fidelity
    : undefined;
  const selectedEdge = scene?.edges.find((edge) =>
    edge.canonicalEdgeIds.some((id) => selectedCanonicalEdgeIds.includes(id)),
  ) ?? null;
  const selectedViewNode = view?.nodes.find(
    (node) => node.attributes.hierarchy_node_id === selectedNode?.hierarchyNodeId,
  );
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
    const ids = new Set([...(selectedNode?.evidenceIds ?? []), ...staticIds, ...runtimeIds]);
    return data?.evidence.filter((record) => ids.has(record.evidence_id)) ?? [];
  }, [data?.architecture.nodes, data?.evidence, data?.runtime, selectedCanonicalIds, selectedNode]);
  const selectedEdgeEvidence = useMemo(() => {
    const ids = new Set(selectedEdge?.evidenceIds ?? []);
    return data?.evidence.filter((record) => ids.has(record.evidence_id)) ?? [];
  }, [data?.evidence, selectedEdge]);
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
  const topologyEditing = data?.edit_session.mode === "topology-draft";

  async function refreshState(): Promise<StudioState | null> {
    return jobController.current?.refreshState() ?? null;
  }

  function pollJob(jobId: string, onSuccess?: () => void) {
    if (jobController.current) pollStudioJob(jobController.current, jobId, onSuccess);
  }

  async function cancelJob(jobId: string) {
    if (!jobController.current) return;
    await cancelStudioJob(jobController.current, jobId, data?.session_nonce, setActivity, {
      success: tx("Cancellation requested", "已请求取消"),
      failure: tx("Cancellation failed", "取消失败"),
    });
  }

  function selectSearchResult(result = searchResults[0]) {
    if (!result) return;
    setSelectedCanonicalEdgeIds([]);
    chooseCanonical(result.canonical_ids);
    setSearchResults([]);
  }

  function chooseCanonical(canonicalIds: string[], navigationRowId?: string) {
    setSelectedCanonicalIds([...new Set(canonicalIds)]);
    setSelectedCanonicalEdgeIds([]);
    setFocusedCanonicalId(canonicalIds[0] ?? null);
    if (navigationRowId !== undefined) setFocusedNavigationRowId(navigationRowId);
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

  function setKernelExpansionLocal(rowId: string, expanded: boolean) {
    navigationTouched.current = true;
    const next = new Set(expansionsRef.current.module);
    if (expanded) next.add(rowId); else next.delete(rowId);
    pendingHierarchyFocus.current = expanded ? rowId : null;
    const nextExpansions = { ...expansionsRef.current, module: next };
    expansionsRef.current = nextExpansions;
    setExpansions(nextExpansions);
  }

  async function beginTopologyDraft() {
    if (!data || data.edit_session.mode !== "visual") return;
    await mutate(
      "/api/draft/session/begin",
      { base_document_digest: data.edit_session.current_document_digest },
      tx("Topology draft unlocked", "拓扑草稿已解锁"),
    );
  }

  async function discardTopologyDraft() {
    if (!window.confirm(tx(
      "Discard all topology changes made in this edit session?",
      "放弃本次编辑会话中的全部拓扑更改？",
    ))) return;
    await mutate(
      "/api/draft/session/discard",
      {},
      tx("Topology draft discarded", "拓扑草稿已放弃"),
    );
  }

  async function submitTopologyDraft() {
    if (codegenRequested && !generateDraftCodePreview()) return;
    const state = await mutate(
      "/api/draft/session/submit",
      {},
      tx("Topology draft is review-ready", "拓扑草稿已进入待评审状态"),
    );
    if (state) setBottomTab(state.transaction ? "diff" : "problems");
  }

  function generateDraftCodePreview(): boolean {
    if (!data) return false;
    setCodegenRequested(true);
    const result = compileStudioDraftPreview(data.draft);
    setCodegenPreview(result.preview);
    const preview = result.preview;
    if (!preview) {
      const codes = result.diagnostics.map((item) => item.code).join(", ");
      setActivity((items) => [
        `${tx("Code generation blocked", "代码生成被阻止")} · ${codes}`,
        ...items,
      ].slice(0, 20));
      setBottomTab("problems");
      return false;
    }
    setActivity((items) => [
      `${tx("Generated reviewed code preview", "已生成受审代码预览")} · ${Object.keys(preview.sourceMap).length} bindings`,
      ...items,
    ].slice(0, 20));
    return true;
  }

  function activateNavigationRow(item: NavigationNode) {
    chooseCanonical(item.canonical_ids, item.id);
    if (item.child_count > 0 && !expansionsRef.current[projection].has(item.id)) {
      setNavigationRowExpanded(projection, item.id, true);
    }
  }


  async function createDraftNode() {
    const semanticName = draftName.trim();
    const definition = resolveDefinitionId(draftType);
    if (!semanticName || !definition) return;
    const nodeId = patchId("draft-node").replace("patch:", "draft:");
    const state = await mutate(
      "/api/proposal/node",
      {
        node: materializeDraftNode(
          definition,
          nodeId,
          semanticName,
          data?.project.framework ?? "pytorch",
          selectedCanonicalIds[0] ?? null,
        ),
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

  async function updateDraftNodeParameters(
    nodeId: string,
    parameters: Record<string, unknown>,
  ): Promise<boolean> {
    const state = await mutate(
      "/api/draft/node/parameters",
      { node_id: nodeId, parameters },
      `${tx("Updated draft parameters", "已更新草稿参数")} · ${nodeId}`,
    );
    if (state) setBottomTab("problems");
    return Boolean(state);
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
          relation: draftEdgePolicy === "add-residual"
            ? "residual"
            : draftEdgePolicy === "concat" ? "concat" : "main",
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
      const result = await previewCanonicalDelete(nodeId, data?.session_nonce);
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
      const job = await startValidation(validationProfile, data?.session_nonce);
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
      const result = await openProjectRequest(projectRoot.trim(), condaEnvironment || null, data?.session_nonce);
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
      setFolderPicker(await browseDirectories(target));
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
      const request: AnalysisRequest = {
        project_id: pendingProject.project.project_id,
        project_generation: pendingProject.project.generation,
        entrypoint: projectEntrypoint,
        framework: projectFramework,
        task: "inference",
        config_path: projectConfig || null,
        execution_mode: "static",
        pattern_packs_enabled: true,
        request_id: `request:${Date.now().toString(36)}`,
      };
      const job = await startAnalysis(request, data?.session_nonce);
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


  function expandInNavigation(node: RenderNode) {
    if (!data) return;
    navigationTouched.current = true;
    const targetProjection: Projection = "module";
    const targetNavigation = data.navigation.projections[targetProjection];
    const hierarchyNodeId = node.hierarchyNodeId;
    const candidates = targetNavigation.nodes
      .filter((item) => item.child_count > 0 && item.canonical_ids.some((id) => node.containedCanonicalNodeIds.includes(id)))
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

  if (!data || !scene || !view || !navigation) {
    return <div className="loading">{tx("Loading Studio...", "正在加载 Studio...")}</div>;
  }

  const sourceDigest = data.document.source_digest.slice(0, 12);
  const selectedCanonical = focusedCanonicalId && selectedCanonicalIds.includes(focusedCanonicalId)
    ? focusedCanonicalId
    : selectedCanonicalIds[0];
  const architectureNode = data.architecture.nodes.find((node) => node.node_id === selectedCanonical);
  const {
    mutate,
    submitGlobal,
    submitKernel,
    submitKernelBatch,
    prepareParameter,
    prepareStructural,
    proposeConnection,
    persistNavigation,
    commitSourceTransaction,
  } = createStudioActions({
    data,
    architectureNode,
    tx,
    acceptStudioState,
    restoreNavigationState,
    setActivity,
    setBottomTab,
    setData,
    navigationTimer,
    navigationQueue,
    pollJob,
  });
  const localizedProjectionName = projection === "module"
    ? tx("Module relations", "模块关系")
    : tx("Source relations", "源码关系");
  const breadcrumb = selectedViewNode
    ? `${data.architecture.entrypoint.split(":").at(-1)} / ${localizedProjectionName} / ${selectedViewNode.semantic_name}`
    : `${data.architecture.entrypoint.split(":").at(-1)} / ${localizedProjectionName}`;
  const proofs = data.draft.proofs;
  const proofCounts = proofs.reduce<Record<string, number>>((counts, proof) => ({ ...counts, [proof.status]: (counts[proof.status] ?? 0) + 1 }), {});
  const writebackBlocked = data.draft.writeback_summary.eligibility === "blocked" && data.draft.writeback_summary.blocking_intent_ids.length > 0;
  const draftBlockingCount = draftAnalysis?.diagnostics.filter((item) => item.severity === "blocking").length ?? 0;
  const problemItems = [
    ...data.diagnostics,
    ...data.draft.proofs.map((proof) => ({
      code: proof.reason_codes[0] ?? proof.status.toUpperCase(),
      severity: proof.status,
      message: proof.message,
      target_ids: proof.affected_subject_ids,
    })),
    ...(draftAnalysis?.diagnostics.map((item) => ({
      code: item.code,
      severity: item.severity,
      message: item.message,
      target_ids: item.targetIds,
    })) ?? []),
  ];
  const latestValidation = data.validation_runs.at(-1);
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

  function selectKernelCanonical(
    canonicalIds: string[],
    fallbackCanonicalIds = canonicalIds,
    additive = false,
    _selectAllMatches = true,
  ) {
    const canonicalId = canonicalIds[0] ?? fallbackCanonicalIds[0] ?? null;
    const candidates = new Set([...canonicalIds, ...fallbackCanonicalIds]);
    setSelectedCanonicalIds((current) => {
      const values = [...candidates];
      if (!additive) return values;
      const next = new Set(current);
      const remove = values.every((id) => next.has(id));
      for (const id of values) {
        if (remove) next.delete(id); else next.add(id);
      }
      return [...next];
    });
    setSelectedCanonicalEdgeIds([]);
    setFocusedCanonicalId(canonicalId);
    const navigationMatch = visibleNavigation.find((item) => item.canonical_ids.some((id) => candidates.has(id)));
    setFocusedNavigationRowId(navigationMatch?.id ?? null);
  }
  const bottomLabels = {
    problems: tx("Problems", "问题"),
    source: tx("Source Workspace", "源码工作区"),
    diff: tx("Source Diff", "源码差异"),
    validation: tx("Validation", "验证"),
    jobs: tx("Jobs", "任务"),
    activity: tx("Activity", "活动"),
  };
  const exportBasename = `archcanvas-${data.architecture.entrypoint.split(":").at(-1) ?? "main-view"}`;
  async function exportMainView(format: "svg" | "png" | "pdf") {
    if (!kernelExport) return;
    exportMenuRef.current?.removeAttribute("open");
    try {
      if (format === "svg") downloadKernelSvg(kernelExport.svg, exportBasename);
      if (format === "png") {
        setExportBusy("png");
        await downloadKernelPng(kernelExport.svg, kernelExport.width, kernelExport.height, exportBasename);
      }
      if (format === "pdf") {
        setExportBusy("pdf");
        await downloadKernelPdf(kernelExport.svg, kernelExport.width, kernelExport.height, exportBasename);
      }
      setActivity((items) => [`${tx("Exported main view", "已导出主视图")} · ${format.toUpperCase()} · ${kernelExport.renderDigest}`, ...items].slice(0, 20));
    } catch (error) {
      setActivity((items) => [`${tx("Main view export failed", "主视图导出失败")} · ${String(error)}`, ...items].slice(0, 20));
    } finally {
      setExportBusy(null);
    }
  }

  return (
    <LanguageContext.Provider value={{ locale, tx }}>
    <InspectorLanguageContext.Provider value={{ tx }}>
    <div
      className={`${dark ? "studio dark" : "studio"}${data.transaction ? " has-transaction" : ""}${data.edit_session.mode === "contract-maintenance" ? " contract-active" : ""}${panelResize ? ` resizing-panel resizing-${panelResize.edge}` : ""}`}
      style={shellLayoutStyle(panelSizes, bottomTab === "source")}
    >
      <TopBar
        entrypointName={data.architecture.entrypoint.split(":").at(-1) ?? data.architecture.entrypoint}
        revision={data.snapshot.revision}
        mode={mode}
        modeLabels={modeLabels}
        locale={locale}
        canUndo={data.document.visual_patches.length > 0}
        canRedo={data.document.redo_patches.length > 0}
        writebackBlocked={writebackBlocked}
        invalidProofs={proofCounts.invalid ?? 0}
        unprovenProofs={proofCounts.unproven ?? 0}
        validationProfile={validationProfile}
        diagnosticCount={latestValidation?.diagnostics.length ?? data.diagnostics.length}
        kernelExport={kernelExport}
        exportBusy={exportBusy}
        exportMenuRef={exportMenuRef}
        tx={tx}
        onOpenProject={() => setProjectDialog(true)}
        onModeChange={(item) => { setMode(item); if (item === "model") setInspectorTab("model"); }}
        onLocaleChange={setLocale}
        onUndo={() => void mutate("/api/undo")}
        onRedo={() => void mutate("/api/redo")}
        onValidationProfileChange={setValidationProfile}
        onValidate={runValidation}
        onExport={(format) => void exportMainView(format)}
      />

      <PanelResizers
        sizes={panelSizes}
        tx={tx}
        onPointerDown={beginPanelResize}
        onPointerMove={movePanelResize}
        onPointerEnd={() => setPanelResize(null)}
        onReset={resetPanelSize}
        onKeyDown={resizePanelWithKeyboard}
      />

      <div className="workspace">
        <NavigationPanel tx={tx}>
          <div className="search-wrap"><div className="search-field"><Search size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && selectSearchResult()} placeholder={tx("Find node, tensor, port, evidence", "查找节点、张量、端口或证据")} /></div>{searchResults.length > 0 && <div className="search-results">{searchResults.slice(0, 8).map((result) => <button key={result.id} onClick={() => selectSearchResult(result)}><span>{result.title}</span><small>{result.kind}</small></button>)}</div>}</div>
          <div className="projection-switch" aria-label={tx("Navigation projection", "导航投影")}>
            {(["module", "source"] as const).map((item) => <button key={item} className={projection === item ? "active" : ""} aria-pressed={projection === item} onClick={() => switchProjection(item)}>{item === "module" ? <Layers3 size={14} /> : <FileCode2 size={14} />}<span>{item === "module" ? tx("Module relations", "模块关系") : tx("Source relations", "源码关系")}</span></button>)}
          </div>
          <div className="section-label">{projection === "module" ? tx("Module hierarchy", "模块层级") : tx("Source hierarchy", "源码层级")}</div>
          <div className="projection-description">{projection === "module" ? tx("Expand modules to reveal their contained architecture.", "展开模块以显示其包含的架构。") : tx("Browse source containment, calls, assignments, and references.", "浏览源码包含、调用、赋值与引用关系。")}</div>
          <div className="tree-list navigation-tree">
            {visibleNavigation.map((item) => {
              const active = focusedNavigationRowId === item.id;
              const related = !active && item.canonical_ids.some((canonicalId) => selectedNode?.containedCanonicalNodeIds.includes(canonicalId));
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
            <header><span><Braces size={13} />{tx("Draft graph", "草稿图")}{draftAnalysis && <i className={draftBlockingCount ? "blocking" : "known"}>{draftBlockingCount ? `${draftBlockingCount} blocking` : "analyzed"}</i>}</span><div className="draft-actions">
              {topologyEditing ? <>
                <button className="icon-button" disabled={!draftAnalysis || draftBlockingCount > 0} title={tx("Submit topology draft", "提交拓扑草稿")} aria-label={tx("Submit topology draft", "提交拓扑草稿")} onClick={() => void submitTopologyDraft()}><ShieldCheck size={13} /></button>
                <button className="icon-button" disabled={!data.draft.nodes.length} title={tx("Generate PyTorch code preview", "生成 PyTorch 代码预览")} aria-label={tx("Generate PyTorch code preview", "生成 PyTorch 代码预览")} onClick={generateDraftCodePreview}><FileCode2 size={13} /></button>
                <button className="icon-button" title={tx("Discard topology draft", "放弃拓扑草稿")} aria-label={tx("Discard topology draft", "放弃拓扑草稿")} onClick={() => void discardTopologyDraft()}><X size={13} /></button>
              </> : <button className="icon-button" disabled={data.edit_session.mode !== "visual"} title={data.edit_session.mode === "contract-maintenance" ? tx("Close contract maintenance before topology editing", "请先结束契约维护再编辑拓扑") : tx("Unlock topology draft", "解锁拓扑草稿")} aria-label={tx("Unlock topology draft", "解锁拓扑草稿")} onClick={() => void beginTopologyDraft()}><LockKeyhole size={13} /></button>}
              <button className="icon-button" title={tx("Module contract maintenance", "模块契约维护")} aria-label={tx("Module contract maintenance", "模块契约维护")} onClick={() => setContractDialog(true)}><Settings2 size={13} /></button>
              <button className="icon-button" disabled={!topologyEditing || !draftSourcePorts.length || !draftTargetPorts.length} title={tx("Create draft connection", "创建草稿连接")} aria-label={tx("Create draft connection", "创建草稿连接")} onClick={openDraftEdgeDialog}><Link2 size={13} /></button>
              <button className="icon-button" disabled={!topologyEditing} title={tx("Create draft node", "创建草稿节点")} aria-label={tx("Create draft node", "创建草稿节点")} onClick={() => setDraftDialog(true)}><Plus size={13} /></button>
            </div></header>
            {data.draft.nodes.length || data.draft.edges.length || canonicalDeleteIntents.length ? <div className="draft-list">{data.draft.nodes.map((node) => {
              const proof = data.draft.proofs.find((item) => item.affected_subject_ids.includes(node.node_id));
              const outputShapes = Object.entries(draftAnalysis?.nodeShapes[node.node_id] ?? {}).map(([portId, value]) => `${portId} ${analyzedValueLabel(value)}`).join(" · ");
              const cost = draftAnalysis?.nodeCosts[node.node_id];
              return <div className="draft-item" key={node.node_id}><Box size={13} /><span><b>{node.semantic_name}</b><small title={cost?.flops ? `FLOPs ${cost.flops}` : undefined}>{node.node_type}{outputShapes ? ` · ${outputShapes}` : ""}</small></span><i className={proof?.status}>{proof?.status ?? data.draft.lowering_status}</i><div className="draft-item-actions"><button className="icon-button" disabled={!topologyEditing || !node.definition_ref} title={tx("Edit draft parameters", "编辑草稿参数")} aria-label={tx("Edit draft parameters", "编辑草稿参数")} onClick={() => setDraftParameterNodeId(node.node_id)}><Settings2 size={12} /></button><button className="icon-button" disabled={!topologyEditing} title={tx("Delete draft node", "删除草稿节点")} aria-label={tx("Delete draft node", "删除草稿节点")} onClick={() => void deleteDraftNode(node.node_id)}><Trash2 size={12} /></button></div></div>;
            })}{data.draft.edges.map((edge) => {
              const proof = data.draft.proofs.find((item) => item.affected_subject_ids.includes(edge.edge_id));
              return <div className="draft-item draft-edge" key={edge.edge_id}><Link2 size={13} /><span><b>{draftPortLabels.get(edge.source_port_id) ?? edge.source_port_id}</b><small>{tx("to", "至")} {draftPortLabels.get(edge.target_port_id) ?? edge.target_port_id} · {edge.policy}</small></span><i className={proof?.status}>{proof?.status ?? data.draft.lowering_status}</i><button className="icon-button" disabled={!topologyEditing} title={tx("Delete draft connection", "删除草稿连接")} aria-label={tx("Delete draft connection", "删除草稿连接")} onClick={() => void deleteDraftEdge(edge.edge_id)}><Trash2 size={12} /></button></div>;
            })}{canonicalDeleteIntents.map((intent) => {
              const proof = data.draft.proofs.find((item) => item.intent_id === intent.intent_id);
              const impact = intent.user_input.impact as CanonicalDeleteImpact | undefined;
              return <div className="draft-item draft-delete" key={intent.intent_id}><Trash2 size={13} /><span><b>{tx("Delete", "删除")} · {impact?.semantic_name ?? intent.target_ids[0]}</b><small>{intent.expected_delta?.removed_edges.length ?? 0} {tx("edges", "条边")} · {intent.expected_delta?.removed_tensors.length ?? 0} Tensor</small></span><i className={proof?.status}>{proof?.status ?? data.draft.lowering_status}</i><button className="icon-button" disabled={!topologyEditing} title={tx("Discard delete intent", "丢弃删除意图")} aria-label={tx("Discard delete intent", "丢弃删除意图")} onClick={() => void discardCanonicalDeleteIntent(intent.intent_id)}><X size={12} /></button></div>;
            })}</div> : <div className="draft-empty">{tx("No draft changes", "没有草稿变更")}</div>}
            {codegenPreview && <div className="codegen-preview"><header><span><FileCode2 size={12} />PyTorch Draft</span><button className="icon-button" title={tx("Close code preview", "关闭代码预览")} aria-label={tx("Close code preview", "关闭代码预览")} onClick={() => setCodegenPreview(null)}><X size={11} /></button></header><pre>{codegenPreview.source}</pre></div>}
          </section>
        </NavigationPanel>

        <main className="canvas-column">
          <div className="canvas-toolbar">
            <div className="breadcrumb">{breadcrumb}</div>
            <div className="canvas-actions">
              <button className="icon-button mobile-only" title={tx("Open inspector", "打开检查器")} aria-label={tx("Open inspector", "打开检查器")} onClick={() => setMobileInspector(true)}><PanelRight /></button>
            </div>
          </div>
          <div className="canvas-stage">
            <ArchitectureCanvas
              state={data as unknown as FormalStudioState}
              selectedCanonicalIds={selectedCanonicalIds}
              selectedCanonicalEdgeIds={selectedCanonicalEdgeIds}
              tx={tx}
              onToggleModule={(hierarchyNodeId, expanded) => {
                setKernelExpansionLocal(hierarchyNodeId, expanded);
              }}
              onCommitVisualBatch={(description, patches) => void submitKernelBatch(description, patches)}
              onExportArtifactChange={acceptKernelExport}
              onSelectCanonicalIds={(canonicalIds, options) => selectKernelCanonical(canonicalIds, canonicalIds, options?.additive)}
              onSelectEdge={(canonicalEdgeIds) => {
                setSelectedCanonicalEdgeIds(canonicalEdgeIds);
                setSelectedCanonicalIds([]);
                setFocusedCanonicalId(null);
                setFocusedNavigationRowId(null);
              }}
              onSelectNode={(kernelNode, additive) => {
                if (!kernelNode) {
                  setSelectedCanonicalIds([]);
                  setSelectedCanonicalEdgeIds([]);
                  setFocusedCanonicalId(null);
                  return;
                }
                selectKernelCanonical(kernelNode.canonicalNodeIds, kernelNode.containedCanonicalNodeIds, additive, false);
              }}
            />
            {selectedNode && <div className="context-bar"><button title={pinned.has(selectedNode.nodeId) ? tx("Unpin", "取消固定") : tx("Pin", "固定")} onClick={() => void submitKernel("set-pin", selectedNode.nodeId, { enabled: !pinned.has(selectedNode.nodeId) })}>{pinned.has(selectedNode.nodeId) ? <PinOff size={14} /> : <Pin size={14} />}</button><button title={tx("Expand in navigation tree", "在导航树中展开")} onClick={() => expandInNavigation(selectedNode)}><Maximize2 size={14} /></button></div>}
          </div>
        </main>

        <InspectorPanel
          mobileOpen={mobileInspector}
          activeTab={inspectorTab}
          labels={inspectorLabels}
          onTabChange={(tab) => setInspectorTab(tab as typeof inspectorTab)}
          onClose={() => setMobileInspector(false)}
          tx={tx}
        >
          {selectedEdge ? <div className="inspector-content">
            {(inspectorTab === "inspect" || inspectorTab === "visual") && <EdgeInspector edge={selectedEdge} evidence={selectedEdgeEvidence} />}
            {inspectorTab === "source" && <SourceInspector nodes={[]} evidence={selectedEdgeEvidence} />}
            {inspectorTab === "model" && <div className="empty-state"><LockKeyhole size={18} /><span>{tx("Edge structure changes use the formal draft workflow.", "边结构修改需使用正式草稿流程。")}</span></div>}
            {inspectorTab === "evidence" && <div className="evidence-list">{selectedEdgeEvidence.length ? selectedEdgeEvidence.map((record) => <section key={record.evidence_id}><div><FileCode2 size={14} /><strong>{record.kind}</strong><span>{record.confidence}</span></div><code>{record.path ?? record.evidence_id}{record.span ? `:${record.span.start_line}` : ""}</code><p>{record.claim}</p></section>) : <div className="empty-state">{tx("No linked evidence", "没有关联证据")}</div>}</div>}
          </div> : !selectedNode || !selectedViewNode ? <div className="empty-state"><Focus size={20} /><span>{tx("No selection", "未选择内容")}</span></div> : <div className="inspector-content">
            {inspectorTab === "inspect" && <StructureInspector label={selectedViewNode.semantic_name} viewNode={selectedViewNode} sceneNode={selectedNode} nodes={selectedArchitectureNodes} tensors={data.architecture.tensors} evidence={selectedEvidence} />}
            {inspectorTab === "source" && <SourceInspector nodes={selectedArchitectureNodes} evidence={selectedEvidence} />}
            {inspectorTab === "visual" && <VisualInspector node={selectedNode} fidelity={selectedTemplateFidelity} pinned={pinned.has(selectedNode.nodeId)} onPatch={submitKernel} onBatch={submitKernelBatch} />}
            {inspectorTab === "model" && <ModelInspector node={architectureNode} nodes={data.architecture.nodes} transaction={data.transaction} proposal={data.proposal} writebackBlocked={writebackBlocked} deleteIntentActive={canonicalDeleteIntents.some((intent) => intent.target_ids[0] === architectureNode?.node_id)} deleteImpactLoading={deleteImpactLoading} onPrepareParameter={prepareParameter} onPrepareStructural={prepareStructural} onProposeConnection={proposeConnection} onReviewDelete={reviewCanonicalDelete} onCommit={commitSourceTransaction} onDiscard={async () => { await mutate("/api/transaction/discard", {}, tx("Discarded source transaction", "已放弃源码事务")); }} />}
            {inspectorTab === "evidence" && <div className="evidence-list">{selectedEvidence.length ? selectedEvidence.map((record) => <section key={record.evidence_id}><div><FileCode2 size={14} /><strong>{record.kind}</strong><span>{record.confidence}</span></div><code>{record.path ?? record.evidence_id}{record.span ? `:${record.span.start_line}` : ""}</code><p>{record.claim}</p></section>) : <div className="empty-state">{tx("No linked evidence", "没有关联证据")}</div>}</div>}
          </div>}
        </InspectorPanel>
      </div>

      <BottomPanel
        activeTab={bottomTab}
        labels={bottomLabels}
        badges={{
          problems: data.diagnostics.length,
          source: data.source_workspace.state !== "clean" ? data.source_workspace.files.filter((file) => file.state !== "clean").length : 0,
          jobs: data.jobs?.some((job) => ["queued", "running"].includes(job.state)),
        }}
        onTabChange={(tab) => setBottomTab(tab as typeof bottomTab)}
      >
          {bottomTab === "problems" && (problemItems.length ? problemItems.map((item, index) => <button key={`${item.code}-${index}`} onClick={() => chooseCanonical(item.target_ids)}><AlertTriangle size={13} /><b>{item.severity}</b><span>{item.message}</span></button>) : <div className="ok-line"><CircleDot size={13} /> {tx("No geometry or writeback problems", "没有几何或回写问题")}</div>)}
          {bottomTab === "source" && <SourceWorkspacePanel workspace={data.source_workspace} transaction={data.transaction} sessionNonce={data.session_nonce} tx={tx} onState={setData} onActivity={(message) => setActivity((items) => [message, ...items].slice(0, 20))} onShowDiff={() => setBottomTab("diff")} />}
          {bottomTab === "diff" && (data.transaction ? <TransactionReview transaction={data.transaction} writebackBlocked={writebackBlocked} tx={tx} onCommit={commitSourceTransaction} onDiscard={async () => { await mutate("/api/transaction/discard", {}, tx("Discarded source transaction", "已放弃源码事务")); }} /> : <div className="ok-line"><LockKeyhole size={13} /> {tx(`Source digest ${sourceDigest} unchanged`, `源码摘要 ${sourceDigest} 未改变`)}</div>)}
          {bottomTab === "validation" && (latestValidation ? <div className="gate-list">{latestValidation.gate_results.map((gate) => <span key={gate.gate} className={gate.status}>{gate.status} · {gate.gate} · {gate.message}</span>)}</div> : <div className="validation-line"><CircleDot size={13} /> {tx("Validation has not been run for this fingerprint", "尚未为此指纹运行验证")}</div>)}
          {bottomTab === "jobs" && <div className="job-list">{data.jobs?.length ? data.jobs.map((job) => <div key={job.job_id}><code>{job.job_id}</code><span>{job.profile}</span><b>{job.state} · {Math.round(job.progress * 100)}%</b>{["queued", "running", "cancelling"].includes(job.state) && <button className="icon-button" title={tx("Cancel job", "取消任务")} aria-label={tx("Cancel job", "取消任务")} onClick={() => void cancelJob(job.job_id)}><X size={12} /></button>}</div>) : <div className="validation-line">{tx("No jobs in this session", "本会话中没有任务")}</div>}</div>}
          {bottomTab === "activity" && <div className="activity-list">{activity.map((item, index) => <span key={`${item}-${index}`}><History size={12} />{item}</span>)}</div>}
      </BottomPanel>

      <button className="theme-toggle icon-button" title={tx("Toggle theme", "切换主题")} aria-label={tx("Toggle theme", "切换主题")} onClick={() => { const next = !dark; setDark(next); void submitGlobal("set-theme", undefined, { theme: next ? "studio-dark" : "paper-light" }); }}>{dark ? <Sun /> : <Moon />}</button>
      <ProjectDialogs
        tx={tx}
        projectDialog={projectDialog}
        setProjectDialog={setProjectDialog}
        condaEnvironments={condaEnvironments}
        environmentLoading={environmentLoading}
        condaEnvironment={condaEnvironment}
        setCondaEnvironment={setCondaEnvironment}
        setCondaEnvironments={setCondaEnvironments}
        projectRoot={projectRoot}
        setProjectRoot={setProjectRoot}
        projectScanning={projectScanning}
        setProjectError={setProjectError}
        projectError={projectError}
        openProject={() => void openProject()}
        pendingProject={pendingProject}
        setPendingProject={setPendingProject}
        folderPicker={folderPicker}
        setFolderPicker={setFolderPicker}
        selectedFolderPath={selectedFolderPath}
        setSelectedFolderPath={setSelectedFolderPath}
        folderLoading={folderLoading}
        browseFolders={(path) => void browseFolders(path)}
        projectModelExpansions={projectModelExpansions}
        setProjectModelExpansions={setProjectModelExpansions}
        projectEntrypoint={projectEntrypoint}
        setProjectEntrypoint={setProjectEntrypoint}
        projectFramework={projectFramework}
        setProjectFramework={setProjectFramework}
        projectConfig={projectConfig}
        setProjectConfig={setProjectConfig}
        selectProjectEntrypoint={selectProjectEntrypoint}
        analyzeProject={() => void analyzeProject()}
        draftDialog={draftDialog}
        setDraftDialog={setDraftDialog}
        draftName={draftName}
        setDraftName={setDraftName}
        draftType={draftType}
        setDraftType={setDraftType}
        selectedCanonicalIds={selectedCanonicalIds}
        createDraftNode={() => void createDraftNode()}
        draftParameterNode={data.draft.nodes.find((node) => node.node_id === draftParameterNodeId) ?? null}
        closeDraftParameters={() => setDraftParameterNodeId(null)}
        updateDraftNodeParameters={updateDraftNodeParameters}
        draftEdgeDialog={draftEdgeDialog}
        setDraftEdgeDialog={setDraftEdgeDialog}
        draftEdgeSource={draftEdgeSource}
        setDraftEdgeSource={setDraftEdgeSource}
        draftEdgeTarget={draftEdgeTarget}
        setDraftEdgeTarget={setDraftEdgeTarget}
        draftEdgePolicy={draftEdgePolicy}
        setDraftEdgePolicy={setDraftEdgePolicy}
        draftSourcePorts={draftSourcePorts}
        draftTargetPorts={draftTargetPorts}
        draftPortLabels={draftPortLabels}
        createDraftEdge={() => void createDraftEdge()}
        deleteImpact={deleteImpact}
        setDeleteImpact={setDeleteImpact}
        createCanonicalDeleteIntent={() => void createCanonicalDeleteIntent()}
      />
      <ContractMaintenanceDialog
        open={contractDialog}
        state={data}
        tx={tx}
        onClose={() => setContractDialog(false)}
        onState={acceptStudioState}
        onActivity={(message) => setActivity((items) => [message, ...items].slice(0, 20))}
      />
    </div>
    </InspectorLanguageContext.Provider>
    </LanguageContext.Provider>
  );
}
