import { t, uiMessage } from './i18n';
import { LanguageSelector } from './LanguageSelector';
import { modelName } from './modelName';
import { rememberPreviewSave, matchesPreviewSave } from './previewSaveState';
import { SourceImportDialog } from './SourceImportDialog';
import { SummaryViewPanel } from './SummaryViewPanel';
import { SummaryRuntimePanel } from './SummaryRuntimePanel';
import { SummaryAuthoringPanel } from './SummaryAuthoringPanel';
import { SummarySemanticPanel } from './SummarySemanticPanel';
import { SummaryCatalogPanel } from './SummaryCatalogPanel';
import { loadSummaryCatalog, loadSummaryCatalogModel, type SummaryCatalogModel } from './summaryCatalog';
import { useWorkspaceMenus } from './WorkspaceUI';
import { WorkspaceDialog } from './WorkspaceDialog';
import { sameSourceSemantics, sourcePresentationOperations } from './sourcePresentation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { buildScene, createDocument, createHistory, reconcileDocument, reduceHistory, validateArchitecture } from './core';
import type { Architecture, CanvasDocument, HistoryState, MoveScope, VisualOperation } from './core';
import { api } from './api';
import type { Binding, Capabilities, InputSpec, RebindOptions, Transaction, SummaryRuntimeResult } from './api';
import { Icon } from './icons';
import { ParameterEditor } from './ParameterEditor';
import { ActivationEditor } from './ActivationEditor';
import { ConnectionEditor } from './ConnectionEditor';
import { RuntimeProfileDialog } from './RuntimeProfileDialog';
import { ReviewDialog } from './ReviewDialog';
import { ExportDialog } from './ExportDialog';
import { ObjectFacts } from './ObjectFacts';
import { HierarchyTree } from './HierarchyTree';
import { previewFrontier, previewHierarchy, previewHierarchyExpansion } from './previewHierarchy';
import { studioTelemetry } from './perf';
import type { CameraState } from './cameraGesture';
import { cameraViewportSize } from './cameraViewport';
import { edgePatternLabel } from './core/edgePresentation';
import { parseMoveCommand } from './moveCommand';
import { AuthoringStudio } from './AuthoringStudio';
import type { AuthoringWorkspace } from './AuthoringStudio';
import type { GeneratedDraft } from './api';
import { createGeneratedCanvas } from './generatedCanvas';
import { followSourceView, resumeSourceAuthoring, sourceAuthoringKey } from './sourceAuthoringSession';
import { readSourceAuthoringWorkspace, writeSourceAuthoringWorkspace } from './sourceAuthoringCache';
import { WorkspaceModeSwitch } from './WorkspaceModeSwitch';
import { FloatingLegend } from './FloatingLegend';
import { resumeGeneratedWorkspace, generatedSourceView, sameGeneratedDraft, readPersistentGeneratedWorkspace, writePersistentGeneratedWorkspace, authoringViewSelection } from './generatedWorkspace';
import type { GeneratedWorkspaceBinding } from './generatedWorkspace';
import { blankDraft } from './authoring';
import type { AuthoredDraft } from './authoring';
import { PreviewStudio } from './PreviewStudio';
import type { PreviewHandle, PreviewSnapshot, PreviewSourceResult } from './PreviewStudio';
import { architecturePreviewRequest, architecturePreviewFocus, bundlePreviewRequest, rawPreviewSourceRequest, previewSelectionDraftIds, previewNodeLayoutOperation, previewExpansionOperations, previewSourceMatchesArchitecture, previewUniqueNodeBindings, previewSourceLocation } from './previewInterop';
import type { PreviewEvidenceSource, PreviewSelection, PreviewSourceBundle, PreviewVisualGraph } from './previewInterop';
import { previewMappingSignature, previewNeedsPanelDocument, previewPanelDocument, projectPreviewHistory } from './previewPanelDocument';
import { isPreviewDraftEdge, previewEdgeAppearance, previewFormalEdgeIds, previewGraphEdges, previewDocumentSyncOperations, previewNodePresentation, previewPresentation, previewAnnotationConflicts, previewAnnotationPosition } from './previewPresentation';
import type { PreviewVisualEdge } from './previewPresentation';
import type { PreviewExportSource } from './previewPublication';
import { previewExportBinding } from './previewPublication';

type Selection = { kind: 'node' | 'edge' | 'preview-edge' | 'legend' | 'annotation'; ids: string[] };
type Camera = CameraState;
const PALETTE = ['#dcebf6', '#deeee6', '#f4e6d0', '#ece3f4', '#f5dfe3', '#e8ecf0'];
const ACTIVE = 'archcanvas.active-canvas.v2';
const REVIEW = 'archcanvas.source-review.v1';

function download(name: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = name; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function editingTarget(target: EventTarget | null) { return target instanceof Element && !!target.closest('input,textarea,select,[contenteditable]'); }
function statusText(evidence: string) { return evidence === 'opaque' ? '未解析内部' : evidence === 'contract' ? '框架契约' : '源码事实'; }

export default function App() {
  const previewEngine = useRef<PreviewHandle>(null);
  const previewSnapshot = useRef<PreviewSnapshot | null>(null);
  const previewSource = useRef<PreviewEvidenceSource | undefined>(undefined);
  const previewBoundSource = useRef('');
  const previewSourceMatch = useRef<{ source: PreviewEvidenceSource; architecture: Architecture; matches: boolean } | null>(null);
  const previewNodeBindings = useRef<{ source?: PreviewEvidenceSource; architecture: Architecture; graph?: Record<string, unknown>; signature: string; bindings: Map<string, string> } | null>(null);
  const previewCase = useRef('');
  const previewLoading = useRef(false);
  const [previewConnecting, setPreviewConnecting] = useState(true);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewCanCancel, setPreviewCanCancel] = useState(false);
  const [summaryCatalogOpen, setSummaryCatalogOpen] = useState(false);
  const synchronizingPreview = useRef(false);
  const initialModelLoading = useRef(true);
  const previewSequence = useRef(0);
  const [previewVersion, setPreviewVersion] = useState(0);
  const [previewDirty, setPreviewDirty] = useState(false);
  const [previewUndo, setPreviewUndo] = useState(false);
  const [previewRedo, setPreviewRedo] = useState(false);
  const [previewSelectedNodeIds, setPreviewSelectedNodeIds] = useState<string[]>([]);
  const savedPreviewGraph = useRef<string | null>(null);
  const enteringAuthoring = useRef(false);
  const openingExport = useRef(false);
  const [authoringOpen, setAuthoringOpen] = useState(false);
  const [summaryEditorId, setSummaryEditorId] = useState<string | null>(null);
  const [authoringWorkspace, setAuthoringWorkspace] = useState<AuthoringWorkspace | undefined>();
  const authoringSessions = useRef(new Map<string, AuthoringWorkspace>());
  const authoringSessionKey = useRef<string | null>(null);
  const generatedWorkspaces = useRef(new Map<string, GeneratedWorkspaceBinding>());
  const [browseBaseline, setBrowseBaseline] = useState<AuthoredDraft | undefined>();
  const [history, setHistory] = useState<HistoryState | null>(null);
  const [selection, setSelection] = useState<Selection>({ kind: 'node', ids: [] });
  const [tool, setTool] = useState<'select' | 'pan'>('select');
  const [previewTool, setPreviewTool] = useState<'select' | 'connect' | 'bend'>('select');
  const [portEditing, setPortEditing] = useState(false);
  const [layoutMoveScope, setLayoutMoveScope] = useState<MoveScope>('all-frontiers');
  const [taskDialog, setTaskDialog] = useState<'library' | 'expansion' | 'runtime' | null>(null);
  const [assemblyOpen, setAssemblyOpen] = useState(false);
  const [newModelOpen, setNewModelOpen] = useState(false);
  const [newModelTitle, setNewModelTitle] = useState('');
  const [newModelError, setNewModelError] = useState('');
  const [creatingModel, setCreatingModel] = useState(false);
  const [sourceOpen, setSourceOpen] = useState(false);
  useWorkspaceMenus();
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [treeSearch, setTreeSearch] = useState('');
  const [actionFeedback, setActionFeedback] = useState<{message: string; error?: boolean} | null>(null);
  useEffect(() => {
    if (!actionFeedback || actionFeedback.error) return;
    const timer = window.setTimeout(() => setActionFeedback(null), 5000);
    return () => window.clearTimeout(timer);
  }, [actionFeedback]);
  const [importOpen, setImportOpen] = useState(false);
  const [sourceText, setSourceText] = useState('');
  const [entry, setEntry] = useState('Model');
  const [filename, setFilename] = useState('model.py');
  const [busy, setBusy] = useState(false);
  const [grid, setGrid] = useState(true);
  const [notice, setNotice] = useState('正在连接独立 runtime…');
  const [failure, setFailure] = useState('');
  const [storageRevision, setStorageRevision] = useState(0);
  const [savedVisualRevision, setSavedVisualRevision] = useState(-1);
  const [command, setCommand] = useState('');
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [review, setReview] = useState<{ transaction: Transaction; base: CanvasDocument; projectId: string } | null>(null);
  const [reviewError, setReviewError] = useState('');
  const [exportDocument, setExportDocument] = useState<CanvasDocument | null>(null);
  const [exportPreview, setExportPreview] = useState<PreviewExportSource | null>(null);
  const [inputSpec, setInputSpec] = useState<InputSpec | null>(null);
  const [runtimeOpen, setRuntimeOpen] = useState(false);
  const [runtimeCancel, setRuntimeCancel] = useState<(() => Promise<void>) | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [connectionProposal, setConnectionProposal] = useState<{ nodeId: string; portId: string; candidate: RebindOptions['candidates'][number] | null; blockers: string[] } | null>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const historyRef = useRef(history); historyRef.current = history;
  // Retained formal source-editor view metadata; never controls the Summary canvas.
  const cameraRef = useRef<Camera>({ x: 30, y: 30, zoom: 1 });
  const loadSequence = useRef(0);
  const saving = useRef(false);
  const current = history?.document;
  const architecture = current?.architecture;
  const summaryEditing = !!summaryEditorId && summaryEditorId === previewSnapshot.current?.caseId;
  const summaryIR = (previewSnapshot.current?.graph?.generic as { ir?: { schema?: string; nodes?: unknown[]; edges?: unknown[] } } | undefined)?.ir;
  const summaryCounts = summaryIR?.schema === 'archcanvas-source-semantic/2' && Array.isArray(summaryIR.nodes) && Array.isArray(summaryIR.edges)
    ? { nodes: summaryIR.nodes.length, edges: summaryIR.edges.length } : null;
  const navigation = useMemo(() => previewHierarchy(previewSnapshot.current), [previewVersion]);
  const frontier = useMemo(() => previewFrontier(previewSnapshot.current, navigation), [previewVersion, navigation]);
  const previewSourceIdentity = previewSnapshot.current?.sourceIdentity;
  const selectedNode = selection.kind === 'node' ? architecture?.nodes.find(n => n.id === selection.ids[0]) : undefined;
  const formalPreviewBindings = currentPreviewNodeBindings();
  const selectedEdge = selection.kind === 'edge' ? architecture?.edges.find(n => n.id === selection.ids[0]) : undefined;
  const selectedPreviewEdge = selection.kind === 'preview-edge' ? previewGraphEdges(previewSnapshot.current?.graph).find(edge => edge.id === selection.ids[0]) : undefined;
  const selectedEdgePreview = selectedEdge && architecture ? previewGraphEdges(previewSnapshot.current?.graph).find(edge => {
    const ids = previewFormalEdgeIds(architecture, edge, previewSnapshot.current?.graph, previewSource.current, formalPreviewBindings);
    return ids.length === 1 && ids[0] === selectedEdge.id;
  }) : undefined;
  const selectedEdgeAppearance = selectedEdgePreview ? previewEdgeAppearance(previewSnapshot.current?.graph, selectedEdgePreview) : undefined;
  const selectedPreviewEdgeAppearance = selectedPreviewEdge ? previewEdgeAppearance(previewSnapshot.current?.graph, selectedPreviewEdge) : undefined;
  const selectedAnnotation = selection.kind === 'annotation' ? current?.annotations.find(n => n.id === selection.ids[0]) : undefined;
  const selectedVisiblePreviewNode = selectedNode && architecture ? graphFromSnapshot()?.nodes.find(node => formalPreviewBindings.get(node.id) === selectedNode.id) : undefined;
  const selectedPreviewNodePresentation = selectedVisiblePreviewNode ? previewNodePresentation(previewSnapshot.current?.graph, selectedVisiblePreviewNode) : undefined;
  const previewSelectedNodes = (graphFromSnapshot()?.nodes ?? []).filter(node => previewSelectedNodeIds.includes(node.id) && !node.junction);
  const inspectionNode = !selectedNode && selection.kind === 'node' && !selection.ids.length && previewSelectedNodes.length === 1 ? previewSelectedNodes[0] : undefined;
  const inspectionPresentation = inspectionNode ? previewNodePresentation(previewSnapshot.current?.graph, inspectionNode) : undefined;
  const inspectionSource = inspectionNode ? previewSourceLocation({ nodeId: inspectionNode.id, node: inspectionNode }, previewSource.current) : null;
  const previewSourceSpan = selectedNode?.source ?? inspectionSource;
  const inspectionExpandable = inspectionNode && (graphFromSnapshot()?.nodes.some(node => node.parent === inspectionNode.id) ||
    navigation?.nodes.some(node => node.parentId === inspectionNode.id));
  const previewPinnedCount = previewSelectedNodes.filter(node => previewPresentation(previewSnapshot.current?.graph)?.nodes?.[node.id]?.pinned).length;
  const previewAllPinned = previewSelectedNodes.length > 0 && previewPinnedCount === previewSelectedNodes.length;
  const previewLayoutDisabled = !current || busy || previewConnecting || previewBusy;
  const previewCanAlign = previewSelectedNodes.length >= 2 && previewSelectedNodes.every(node => (node.parent ?? null) === (previewSelectedNodes[0].parent ?? null));
  const annotationConflicts = selectedAnnotation && previewSnapshot.current?.graph ? previewAnnotationConflicts(previewSnapshot.current.graph, selectedAnnotation.id) : [];
  const summaryRuntimeReceipt = (previewSnapshot.current?.graph?.generic as { ir?: { runtime?: Record<string, unknown> } } | undefined)?.ir?.runtime;
  const summaryRuntimeHasSource = Boolean(previewSource.current || summaryRuntimeReceipt?.source_files);
  const dirty = previewDirty || (!!current && current.revision !== savedVisualRevision);
  function sourceFromResult(result: PreviewSourceResult): PreviewEvidenceSource | undefined {
    return (result.bundle ?? result.source ?? result.document?.adapter) as PreviewEvidenceSource | undefined;
  }
  function graphFromSnapshot(snapshot = previewSnapshot.current): PreviewVisualGraph | null {
    const graph = snapshot?.graph;
    return graph && Array.isArray(graph.nodes) ? graph as unknown as PreviewVisualGraph : null;
  }
  function currentPreviewSourceMatches(architecture: Architecture): boolean {
    const source = previewSource.current;
    if (!source) return false;
    // Imported source corpora and architecture are immutable for a generation;
    // all source edits install new objects and invalidate this checked pair.
    const checked = previewSourceMatch.current;
    if (checked?.source === source && checked.architecture === architecture) return checked.matches;
    const matches = previewSourceMatchesArchitecture(source, architecture);
    previewSourceMatch.current = { source, architecture, matches };
    return matches;
  }
  function currentPreviewNodeBindings(): Map<string, string> {
    const architecture = historyRef.current?.document.architecture, snapshot = previewSnapshot.current;
    if (!architecture || !snapshot?.graph) return new Map();
    const source = previewSource.current, cached = previewNodeBindings.current;
    if (cached?.architecture === architecture && cached.source === source && cached.graph === snapshot.graph) return cached.bindings;
    const signature = previewMappingSignature(snapshot);
    if (cached?.architecture === architecture && cached.source === source && cached.signature === signature) { cached.graph = snapshot.graph; return cached.bindings; }
    const bindings = previewUniqueNodeBindings(architecture, snapshot.graph as unknown as PreviewVisualGraph, source);
    previewNodeBindings.current = { architecture, source, graph: snapshot.graph, signature, bindings };
    return bindings;
  }
  function readyPreview(document = historyRef.current?.document): boolean {
    if (!document || initialModelLoading.current || previewLoading.current || synchronizingPreview.current || !previewSnapshot.current?.graph || previewSnapshot.current.busy) return false;
    if (document.sourceBindingDigest.startsWith('preview-only:')) return document.sourceBindingDigest === `preview-only:${previewCase.current}`;
    return !!previewSource.current && previewBoundSource.current === document.architecture.sourceDigest + ':' + document.architecture.irDigest &&
      currentPreviewSourceMatches(document.architecture) &&
      (previewSource.current.schema === 'summary-source-adapter/1' ? previewSource.current.id : previewSource.current.caseId) === previewCase.current;
  }
  async function restoreMatchingPreview(document: CanvasDocument, caseId: string | undefined, sequence: number): Promise<PreviewSnapshot | null> {
    if (!caseId) return null;
    try {
      const snapshot = await previewEngine.current!.snapshot();
      if (sequence !== loadSequence.current || snapshot.caseId !== caseId) return null;
      if (snapshot.importedDocument && document.sourceBindingDigest === `preview-only:${caseId}`) {
        previewSource.current = undefined; previewCase.current = caseId; previewSnapshot.current = snapshot;
        previewBoundSource.current = '';
        const saved = await matchesPreviewSave(localStorage, document, snapshot.graph);
        if (sequence !== loadSequence.current) return null;
        if (saved) savedPreviewGraph.current = JSON.stringify(snapshot.graph);
        setPreviewConnecting(false);
        return snapshot;
      }
      const result = await previewEngine.current!.source(), source = sourceFromResult(result);
      if (sequence !== loadSequence.current || result.document?.caseId !== caseId || !source || !previewSourceMatchesArchitecture(source, document.architecture)) return null;
      previewSource.current = source; previewCase.current = caseId; previewSnapshot.current = snapshot;
      previewBoundSource.current = document.architecture.sourceDigest + ':' + document.architecture.irDigest;
      const saved = await matchesPreviewSave(localStorage, document, snapshot.graph);
      if (sequence !== loadSequence.current) return null;
      if (saved) savedPreviewGraph.current = JSON.stringify(snapshot.graph);
      setPreviewConnecting(false);
      return snapshot;
    } catch { return null; }
  }
  function previewNodeId(id: string): string | undefined {
    const document = historyRef.current?.document, graph = graphFromSnapshot();
    if (!document || !graph) return undefined;
    const detail = (previewSnapshot.current?.graph?.recursive as { authority?: { detail?: PreviewVisualGraph } } | undefined)?.authority?.detail;
    const nodes = detail?.nodes ?? graph.nodes;
    const bindings = currentPreviewNodeBindings();
    return nodes.find(node => bindings.get(node.id) === id)?.id;
  }
  function focusPreviewNode(id: string) {
    const nodeId = previewNodeId(id);
    if (nodeId) previewEngine.current?.focus({ nodeId });
    else setNotice('该源码对象在当前目录图中没有直接对应图元；可在源码面板查看，或进入模型编辑。');
  }
  function mapPreviewOperations(operations: VisualOperation[]): Record<string, unknown>[] {
    const byId = (id: string) => {
      const mapped = previewNodeId(id);
      if (!mapped) throw new Error('当前源码对象未显示为独立图元；可进入模型编辑，或在原型画布选择对应的展示对象。');
      return mapped;
    };
    return operations.flatMap<Record<string, unknown>>(operation => {
      if (operation.type === 'edgeStyle') {
        const architecture = historyRef.current?.document.architecture;
        const formal = architecture?.edges.find(edge => edge.id === operation.id);
        const graph = previewSnapshot.current?.graph;
        if (!formal || !architecture || !graph) throw new Error('连接的源码绑定不可用。');
        const bindings = currentPreviewNodeBindings();
        const found = previewGraphEdges(graph).filter(edge => {
          const ids = previewFormalEdgeIds(architecture, edge, graph, previewSource.current, bindings);
          return ids.length === 1 && ids[0] === formal.id;
        });
        if (!found.length) throw new Error('当前前沿没有显示该连接，请先展开所属模块。');
        return found.map(edge => ({ ...operation, id: edge.id }));
      }
      if (operation.type === 'move' || operation.type === 'pin') return [{ ...operation, ids: operation.ids.map(byId) }];
      if (operation.type === 'nodeLayout') {
        return [previewNodeLayoutOperation(historyRef.current!.document, operation, graphFromSnapshot()!, previewSource.current)];
      }
      if (operation.type === 'alias' || operation.type === 'nodeStyle' || operation.type === 'expand') return [{ ...operation, id: byId(operation.id) }];
      if (operation.type === 'portLayout') return [{ ...operation, ownerId: byId(operation.ownerId), nodeId: byId(operation.nodeId) }];
      return [{ ...operation }];
    });
  }
  async function bindPreviewSource(result: PreviewSourceResult, openEditor = false) {
    const source = sourceFromResult(result);
    if (!source) throw new Error('当前示例没有模型源码；可新建模型或导入 Python 源码。');
    previewSource.current = source;
    const sequence = ++previewSequence.current;
    const expectedCase = previewCase.current;
    setPreviewConnecting(true);
    const bound = historyRef.current?.document;
    // A source-inspection projection may contain additional opaque objects.
    // That does not revoke an existing, byte-matched formal source contract.
    if (bound && !bound.sourceBindingDigest.startsWith('preview-only:') && previewSourceMatchesArchitecture(source, bound.architecture)) {
      previewBoundSource.current = bound.architecture.sourceDigest + ':' + bound.architecture.irDigest;
      if (previewSnapshot.current) await receivePreviewState(previewSnapshot.current);
      setPreviewConnecting(false);
      if (openEditor) await continueModelAuthoring();
      return;
    }
    let arch: Architecture;
    try {
      const request = source.schema === 'summary-source-adapter/1' ? bundlePreviewRequest(source) : rawPreviewSourceRequest(source);
      arch = await api.previewEditSource(request);
    }
    catch (error) {
      if (sequence !== previewSequence.current || expectedCase !== previewCase.current) return;
      if (previewSnapshot.current) {
        const panelDocument = previewPanelDocument(previewSnapshot.current, source);
        historyRef.current = createHistory(panelDocument); setHistory(historyRef.current);
        previewBoundSource.current = '';
        setProjectId(null); setStorageRevision(0); setSavedVisualRevision(-1);
        await receivePreviewState(previewSnapshot.current);
        setPreviewConnecting(false);
        setNotice(`源码文本已打开，只读查看；此入口暂超出模型编辑契约：${String(error)}`);
      }
      if (openEditor) { setSourceOpen(true); throw error; }
      return;
    }
    if (sequence !== previewSequence.current || expectedCase !== previewCase.current) return;
    if (!openEditor && previewSnapshot.current && previewNeedsPanelDocument(previewSnapshot.current, arch, source)) {
      historyRef.current = createHistory(previewPanelDocument(previewSnapshot.current, source)); setHistory(historyRef.current);
      previewBoundSource.current = ''; setProjectId(null); setStorageRevision(0); setSavedVisualRevision(-1);
      await receivePreviewState(previewSnapshot.current);
      setPreviewConnecting(false);
      setNotice('原型视图与源码已打开；展示对象可独立编辑，进入编辑模式后按源码建立模型绑定。');
      return;
    }
    previewBoundSource.current = arch.sourceDigest + ':' + arch.irDigest;
    await openArchitecture(arch, true);
    if (sequence !== previewSequence.current || expectedCase !== previewCase.current) return;
    const before = historyRef.current;
    if (before && previewSnapshot.current) await receivePreviewState(previewSnapshot.current);

    setPreviewConnecting(false);
    if (openEditor) await continueModelAuthoring();
  }
  function receivePreviewSelection(message: Record<string, unknown>) {
    if (message.caseId && message.caseId !== previewCase.current) return;
    synchronizePreviewNodeSelection(message.nodeIds ?? message.selectedNodes);
    if (typeof message.annotationId === 'string') {
      setSelection({ kind: 'annotation', ids: [message.annotationId] }); return;
    }
    const architecture = historyRef.current?.document.architecture;
    if (!architecture) return;
    const edge = message.edge as PreviewVisualEdge | undefined;
    const graph = graphFromSnapshot();
    if (edge && graph) {
      const raw = previewGraphEdges(previewSnapshot.current?.graph).find(item => item.id === edge.id);
      const ids = raw ? previewFormalEdgeIds(architecture, raw, previewSnapshot.current?.graph, previewSource.current, currentPreviewNodeBindings()) : [];
      setSelection(ids.length === 1 ? { kind: 'edge', ids } : { kind: 'preview-edge', ids: [edge.id] });
      return;
    }
    const selected = (message.nodeIds ?? message.selectedNodes) as string[] | undefined;
    const bindings = currentPreviewNodeBindings();
    const ids = selected?.length && graph ? [...new Set(selected.flatMap(id => bindings.has(id) ? [bindings.get(id)!] : []))] :
      typeof message.nodeId === 'string' && bindings.has(message.nodeId) ? [bindings.get(message.nodeId)!] : [];
    setSelection({ kind: 'node', ids });
  }
  function receivePreviewInteraction(status: Record<string, unknown>) {
    const snapshot = previewSnapshot.current;
    if (!snapshot || status.caseId !== snapshot.caseId) return;
    // Keep the last committed graph, source ownership and selection intact.
    // Escape/cancel reads these live flags without rebuilding the panel model.
    snapshot.busy = status.busy === true;
    snapshot.dragging = status.dragging === true;
    snapshot.canCancel = status.canCancel === true;
    setPreviewBusy(status.busy === true);
    setPreviewCanCancel(status.canCancel === true);
  }
  async function receivePreviewState(snapshot: PreviewSnapshot) {
    previewSnapshot.current = snapshot;
    synchronizePreviewNodeSelection(snapshot.selectedNodes);
    if (snapshot.tool === 'select' || snapshot.tool === 'connect' || snapshot.tool === 'bend') setPreviewTool(snapshot.tool);
    if (typeof snapshot.showPorts === 'boolean') setPortEditing(snapshot.showPorts);
    if (typeof snapshot.gridVisible === 'boolean') setGrid(snapshot.gridVisible);
    setPreviewBusy(Boolean(snapshot.busy));
    setPreviewCanCancel(snapshot.canCancel === true);
    const graph = snapshot.graph;
    const caseId = String(graph?.caseId ?? snapshot.caseId ?? '');
    const graphText = JSON.stringify(graph), matchesSavedGraph = graphText === savedPreviewGraph.current;
    setPreviewDirty(Boolean(snapshot.dirty) && !matchesSavedGraph);
    setPreviewUndo(Boolean(snapshot.canUndo)); setPreviewRedo(Boolean(snapshot.canRedo));
    setPreviewVersion(version => version + 1);
    setSelection(before => before.kind === 'preview-edge' && !previewGraphEdges(graph).some(edge => edge.id === before.ids[0]) ? { kind: 'node', ids: [] } : before);
    if (initialModelLoading.current) { previewCase.current = caseId; return; }
    if (previewLoading.current) { previewCase.current = caseId; return; }
    // A loading/route transaction publishes toolbar state with the previous
    // committed graph. Source ownership changes only after its final snapshot.
    if (snapshot.busy) return;
    if (caseId && caseId !== previewCase.current) {
      ++previewSequence.current; ++loadSequence.current;
      previewCase.current = caseId; previewBoundSource.current = ''; previewSource.current = undefined;
      setBusy(false); setPreviewConnecting(true);
      const panelDocument = previewPanelDocument(snapshot);
      historyRef.current = createHistory(panelDocument); setHistory(historyRef.current);
      setSelection({ kind: 'node', ids: [] }); setProjectId(null);
      if (snapshot.importedDocument) {
        setPreviewConnecting(false);
        setNotice('已打开 Summary 文档；视觉编辑保存到浏览器，可通过编辑 JSON 搬运。文档证据未绑定 Python 源码。');
        return;
      }
      const frozenCase = caseId;
      const generation = previewSequence.current, loadGeneration = loadSequence.current;
      try {
        const result = await previewEngine.current!.source();
        if (previewCase.current !== frozenCase || generation !== previewSequence.current || loadGeneration !== loadSequence.current) return;
        await bindPreviewSource(result);
      } catch (error) { if (previewCase.current === frozenCase && generation === previewSequence.current && loadGeneration === loadSequence.current) { setPreviewConnecting(false); setNotice(`预览已打开；源码编辑入口：${String(error)}`); } }
      return;
    }
    if (synchronizingPreview.current) return;
    if (snapshot.authoring && historyRef.current?.document.sourceBindingDigest.startsWith('preview-only:')) {
      const next = createHistory(previewPanelDocument(snapshot)); historyRef.current = next; setHistory(next); return;
    }
    const before = historyRef.current;
    const visual = graphFromSnapshot(snapshot);
    if (before && !before.document.sourceBindingDigest.startsWith('preview-only:') && (!previewSource.current ||
      !currentPreviewSourceMatches(before.document.architecture) ||
      (previewSource.current.schema === 'summary-source-adapter/1' ? previewSource.current.id : previewSource.current.caseId) !== caseId)) return;
    // Project uniquely mapped presentation only. Extra inspection objects stay
    // in the preview graph and never replace formal facts or project ownership.
    if (before && visual) {
      const presentationTitle = ((graph?.recursive as { state?: { studioPresentation?: { title?: string } } } | undefined)?.state?.studioPresentation ?? graph?.studioPresentation) as { title?: string } | undefined;
      const next = projectPreviewHistory(before, visual, previewSource.current, presentationTitle?.title ?? String(snapshot.title ?? before.document.title), currentPreviewNodeBindings());
      if (next !== before) {
        historyRef.current = next; setHistory(next);
        // A browser restore may project aliases/legend into the panel after
        // the saved native graph has already been verified. This mirror is
        // derived state, so its new revision stays saved with that exact graph.
        if (before.document.sourceBindingDigest.startsWith('preview-only:') && matchesSavedGraph) setSavedVisualRevision(next.document.revision);
      }
    }
  }
  useEffect(() => {
    const architecture = current?.architecture;
    if (!architecture) return;
    if (architecture.sourceDigest.startsWith('preview-only:')) return;
    const identity = architecture.sourceDigest + ':' + architecture.irDigest;
    if (previewBoundSource.current === identity) return;
    const sequence = ++previewSequence.current;
    previewBoundSource.current = identity; previewLoading.current = true;
    setPreviewConnecting(true);
    let alive = true;
    (async () => {
      try {
        const bundle = await api.previewAnalyze(architecturePreviewRequest(architecture));
        if (!alive || sequence !== previewSequence.current) return;
        previewSource.current = bundle; previewCase.current = bundle.id;
        await previewEngine.current!.load(bundle);
        const document = historyRef.current?.document;
        if (document?.architecture.sourceDigest === architecture.sourceDigest && document.architecture.irDigest === architecture.irDigest) {
          const detail = (previewSnapshot.current?.graph?.recursive as { authority?: { detail?: PreviewVisualGraph } } | undefined)?.authority?.detail;
          const expansion = detail ? previewExpansionOperations(document, detail, previewSource.current) : [];
          const operations = previewDocumentSyncOperations(undefined, document, previewSnapshot.current?.graph, previewSource.current);
          await previewEngine.current!.visual([...expansion, ...operations]);
          await previewEngine.current!.command('fit');
        }
        if (alive) setNotice('源码已接入递归预览；模型未执行。');
      } catch (error) { if (alive) { previewBoundSource.current = ''; setFailure(`预览解析失败：${String(error)}`); } }
      finally {
        if (sequence === previewSequence.current) {
          previewLoading.current = false; setPreviewConnecting(false);
          if (alive && previewSnapshot.current) await receivePreviewState(previewSnapshot.current);
        }
      }
    })();
    return () => { alive = false; };
  }, [current?.architecture.sourceDigest, current?.architecture.irDigest]);
  useEffect(() => {
    try { setInputSpec(JSON.parse(localStorage.getItem(`archcanvas.runtime-profile:${current?.id}`) ?? 'null')); }
    catch { setInputSpec(null); }
    setRuntimeOpen(false);
  }, [current?.id]);
  function saveInputSpec(spec: InputSpec) {
    if (current) localStorage.setItem(`archcanvas.runtime-profile:${current.id}`, JSON.stringify(spec));
    setInputSpec(spec); setRuntimeOpen(false); setNotice('运行输入已登记；候选检查仍是静态，连接预览才执行隔离验证');
  }

  function readCameraViewport() {
    return cameraViewportSize(viewportRef.current?.getBoundingClientRect());
  }
  // Source-editor sessions retain their own camera, independently of preview navigation.
  const commitCamera = useCallback((view: Camera) => { cameraRef.current = { ...view }; }, []);
  const cancelGesture = useCallback(() => { if (previewSnapshot.current?.dragging) previewEngine.current?.command('cancel-gesture'); }, []);
  function chooseTool(next: 'select' | 'connect' | 'bend') {
    cancelGesture(); setPreviewTool(next);
    previewEngine.current?.command(`${next}-tool`);
  }
  function chooseMoveScope(next: MoveScope) { cancelGesture(); setLayoutMoveScope(next); }
  useEffect(() => { if (review || exportDocument || importOpen || connectionProposal || runtimeOpen) cancelGesture(); }, [review, exportDocument, importOpen, connectionProposal, runtimeOpen, cancelGesture]);

  const apply = useCallback((operations: VisualOperation[], message?: string) => {
    cancelGesture();
    const interaction = studioTelemetry.beginInteraction(`visual:${operations.map(operation => operation.type === 'expand' && !operation.expanded ? 'collapse' : operation.type).join('+') || 'noop'}`);
    try {
      const previous = historyRef.current;
      if (!previous) return;
      if (!readyPreview(previous.document)) throw new Error('预览正在接入当前源码，请完成后再编辑画布。');
      const translated = mapPreviewOperations(operations);
      if (operations.some(operation => operation.type === 'expand')) {
        // The preview transaction owns validation, neighbor displacement and
        // one undo entry. Its resulting snapshot updates the formal mirror.
        const sequence = loadSequence.current;
        void previewEngine.current?.visual(translated).catch(error => {
          if (sequence === loadSequence.current) setFailure(String(error));
        });
        if (message) setNotice(message);
        setFailure('');
        return;
      }
      const next = reduceHistory(previous, { type: 'apply', baseRevision: previous.document.revision, operations });
      historyRef.current = next; setHistory(next);
      void previewEngine.current?.visual(translated).catch(error => {
        if (historyRef.current === next) { historyRef.current = previous; setHistory(previous); }
        setFailure(String(error));
      });
      if (message) setNotice(message);
      setFailure('');
    } catch (error) { setFailure(String(error)); }
    finally { studioTelemetry.endInteraction(interaction); }
  }, [cancelGesture]);
  async function stylePreviewEdge(id: string, style: CanvasDocument['edgeStyleOverrides'][string]) {
    const engine = previewEngine.current;
    if (!engine || !readyPreview() || !previewGraphEdges(previewSnapshot.current?.graph).some(edge => edge.id === id)) return;
    try { await engine.visual([{ type: 'edgeStyle', id, style }]); setFailure(''); }
    catch (error) { setFailure(String(error)); }
  }
  function optimizeAutomaticPorts(id: string, previewIdentity = false) {
    if (!readyPreview()) return;
    const nodeId = previewIdentity ? graphFromSnapshot()?.nodes.find(node => node.id === id)?.id : previewNodeId(id);
    if (!nodeId) { setFailure('此对象没有唯一对应的可见 Summary 图元。'); return; }
    const sequence = loadSequence.current;
    void previewEngine.current?.visual([{ type: 'portLayout', ownerId: nodeId, nodeId, layout: null }]).then(() => {
      if (sequence === loadSequence.current) { setNotice('已由 Summary 恢复当前图元的自动连接点；可撤销。'); setFailure(''); }
    }).catch(error => { if (sequence === loadSequence.current) setFailure(String(error)); });
  }
  const selectHierarchyNode = useCallback((id: string, additive = false) => {
    const graph = graphFromSnapshot();
    const detail = (previewSnapshot.current?.graph?.recursive as { authority?: { detail?: PreviewVisualGraph } } | undefined)?.authority?.detail ?? graph;
    const mapped = detail?.nodes.some(node => node.id === id && !node.junction) ? id : previewNodeId(id);
    if (!mapped) { setFailure('此源码对象没有唯一对应的画布图元；可直接在画布选择或查看源码。'); return; }
    setFailure('');
    previewEngine.current?.focus({ nodeId: mapped, additive });
  }, []);
  const expandHierarchyNode = useCallback((id: string, expanded: boolean) => {
    const hierarchy = previewHierarchy(previewSnapshot.current);
    if (!hierarchy?.nodes.some(node => node.id === id)) { apply([{ type: 'expand', id, expanded }]); return; }
    if (!readyPreview()) { setFailure('预览正在接入当前源码，请完成后再展开。'); return; }
    setFailure('');
    const operations = previewHierarchyExpansion(hierarchy, id, expanded);
    if (!operations.length) return;
    const sequence = loadSequence.current;
    void previewEngine.current?.visual(operations).catch(error => {
      if (sequence === loadSequence.current) setFailure(String(error));
    });
  }, [apply]);
  function focusCurrentFrontier() {
    const id = previewSelectedNodeIds[0] ?? frontier?.expandedIds[frontier.expandedIds.length - 1];
    if (id) { previewEngine.current?.focus({ nodeId: id }); return; }
    fit();
  }
  const undo = useCallback(() => { cancelGesture(); previewEngine.current?.command('undo'); setActionFeedback(null); setNotice('已撤销一次画布操作'); }, [cancelGesture]);
  const redo = useCallback(() => { cancelGesture(); previewEngine.current?.command('redo'); setActionFeedback(null); setNotice('已重做一次画布操作'); }, [cancelGesture]);

  function repairSummaryLayout() {
    if (!readyPreview()) return;
    cancelGesture();
    previewEngine.current?.command('apply-layout');
  }
  const fit = useCallback(() => { cancelGesture(); previewEngine.current?.command('fit'); }, [cancelGesture]);

  const openArchitecture = useCallback(async (arch: Architecture, restore = true, requestSequence?: number) => {
    const sequence = requestSequence ?? ++loadSequence.current;
    if (sequence !== loadSequence.current) return;
    let document = createDocument(arch);
    let saved = -1; let version = 0;
    if (restore) {
      try {
        const stored = await api.document(document.id);
        if (stored.document.sourceBindingDigest === arch.sourceDigest && stored.document.architecture.irDigest === arch.irDigest) {
          document = stored.document; saved = document.revision; version = stored.revision;
        }
      } catch { /* A new source has no saved document yet. */ }
    }
    if (sequence !== loadSequence.current) return;
    historyRef.current = createHistory(document); setHistory(historyRef.current); setStorageRevision(version); setSavedVisualRevision(saved);
    setProjectId(null); setReview(null); localStorage.removeItem(REVIEW);
    setSelection({ kind: 'node', ids: [] }); setSourceOpen(false);
    setNotice(saved >= 0 ? '已重开保存的画布' : '静态源码已导入；模型未被执行'); setFailure('');
  }, []);

  useEffect(() => {
    let alive = true;
    const sequence = ++loadSequence.current;
    api.capabilities().then(result => { if (alive) setCapabilities(result); }).catch(() => {});
    loadSummaryCatalog().then(async catalog => {
      if (!alive || sequence !== loadSequence.current) return;
      const requested = new URLSearchParams(window.location.search).get('documentId');
      if (requested) {
        try {
          const stored = await api.document(requested);
          if (!alive || sequence !== loadSequence.current) return;
          const active = JSON.parse(localStorage.getItem(ACTIVE) ?? 'null') as { documentId?: string; previewCaseId?: string } | null;
          const restored = await restoreMatchingPreview(stored.document, active?.documentId === requested ? active.previewCaseId : undefined, sequence);
          if (!alive || sequence !== loadSequence.current) return;
          historyRef.current = stored.history ?? createHistory(stored.document); setHistory(historyRef.current);
          setStorageRevision(stored.revision); setSavedVisualRevision(stored.document.revision);
          setProjectId(stored.projectId ?? null); setReview(null);
          setNotice('已打开指定模型画布'); setFailure('');
          if (restored) { initialModelLoading.current = false; await receivePreviewState(restored); }
        } catch (error) { if (alive) { setFailure(`无法打开指定画布：${String(error)}`); setNotice('请核对文档地址与当前运行时'); } }
        return;
      }
      try {
        const active = JSON.parse(localStorage.getItem(ACTIVE) ?? 'null') as { documentId: string; projectId: string | null; previewCaseId?: string } | null;
        if (active) {
          const stored = await api.document(active.documentId).catch(async error => {
            if (!active.previewCaseId) throw error;
            const snapshot = await previewEngine.current!.snapshot();
            if (snapshot.caseId !== active.previewCaseId || !alive || sequence !== loadSequence.current) throw error;
            initialModelLoading.current = false; previewCase.current = '';
            await receivePreviewState(snapshot);
            const recovered = historyRef.current?.document, recoveredSequence = loadSequence.current;
            const saved = recovered && await matchesPreviewSave(localStorage, recovered, snapshot.graph);
            const latest = historyRef.current?.document;
            if (!alive || recoveredSequence !== loadSequence.current || !recovered || latest?.id !== recovered.id || latest.sourceBindingDigest !== recovered.sourceBindingDigest || latest.architecture.irDigest !== recovered.architecture.irDigest || previewSnapshot.current?.caseId !== snapshot.caseId || JSON.stringify(previewSnapshot.current?.graph) !== JSON.stringify(snapshot.graph)) return null;
            if (saved) {
              savedPreviewGraph.current = JSON.stringify(snapshot.graph);
              setPreviewDirty(false); setSavedVisualRevision(latest.revision);
            }
            setNotice('已从浏览器重开递归预览；可通过编辑 JSON 搬运完整图。');
            return null;
          });
          if (!stored) return;
          let doc = stored.document; let version = stored.revision; let saved = doc.revision;
          if (active.projectId) {
            const project = await api.project(active.projectId);
            if (project.sourceDigest !== doc.sourceBindingDigest || project.irDigest !== doc.architecture.irDigest) {
              doc = reconcileDocument(doc, project.architecture).document; version = 0; saved = -1;
            }
          }
          if (!alive || sequence !== loadSequence.current) return;
          const restored = await restoreMatchingPreview(doc, active.previewCaseId, sequence);
          if (!alive || sequence !== loadSequence.current) return;
          historyRef.current = stored.history && doc === stored.document ? stored.history : createHistory(doc); setHistory(historyRef.current); setStorageRevision(version); setSavedVisualRevision(saved); setProjectId(active.projectId);
          setNotice(active.projectId ? '已重开工作副本及保存的画布' : '已重开保存的画布');
          if (restored) { initialModelLoading.current = false; await receivePreviewState(restored); }
          const pending = JSON.parse(localStorage.getItem(REVIEW) ?? 'null') as { projectId: string; id: string } | null;
          if (pending && pending.projectId === active.projectId) {
            const transaction = await api.transaction(pending.projectId, pending.id);
            if (alive && transaction.status !== 'Discarded') setReview({ transaction, base: doc, projectId: pending.projectId });
          }
          return;
        }
      } catch { /* A missing stored snapshot falls back to the current Summary catalog. */ }
      if (!alive || sequence !== loadSequence.current) return;
      const model = catalog.models[0];
      if (!model) throw Error('Summary 模型库为空。');
      await openSummaryCatalog(model, true);
    }).catch(error => { if (alive) { setFailure(`Runtime 未连接：${String(error)}`); setNotice('请按 README 启动正式服务'); } }).finally(() => { if (alive) initialModelLoading.current = false; });
    return () => { alive = false; };
  }, []);
  useEffect(() => {
    if (!current || authoringOpen || busy || exportDocument || review) return;
    let alive = true, inFlight = false;
    const synchronize = async () => {
      if (inFlight || saving.current || openingExport.current || previewLoading.current) return;
      const before = historyRef.current;
      if (!before || before.document.id !== current.id) return;
      inFlight = true;
      try {
        const saved = await api.document(current.id);
        if (!alive || saved.revision <= storageRevision || historyRef.current !== before) return;
        if (before.document.revision !== savedVisualRevision) {
          setFailure('同一画布已被其他操作更新；当前未保存编辑保留，请先另存或核对后重开。');
          return;
        }
        if (saved.document.sourceBindingDigest === before.document.sourceBindingDigest && saved.document.architecture.irDigest === before.document.architecture.irDigest) {
          if (!readyPreview(before.document)) return;
          const operations = previewDocumentSyncOperations(before.document, saved.document, previewSnapshot.current?.graph, previewSource.current);
          if (operations.length) {
            synchronizingPreview.current = true; setPreviewConnecting(true);
            for (let offset = 0; offset < operations.length; offset += 200) {
              if (!alive || historyRef.current !== before) return;
              await previewEngine.current!.visual(operations.slice(offset, offset + 200));
            }
          }
          if (!alive || historyRef.current !== before) return;
          const snapshot = await previewEngine.current!.snapshot();
          if (!alive || historyRef.current !== before || snapshot.caseId !== previewCase.current) return;
          previewSnapshot.current = snapshot;
          savedPreviewGraph.current = JSON.stringify(snapshot.graph); setPreviewDirty(false);
        }
        historyRef.current = saved.history ?? createHistory(saved.document); setHistory(historyRef.current);
        setStorageRevision(saved.revision); setSavedVisualRevision(saved.document.revision);
        synchronizingPreview.current = false;
        if (previewSnapshot.current) await receivePreviewState(previewSnapshot.current);
        setNotice('已同步当前模型的视觉操作与撤销记录');
      } catch (error) { if (alive && synchronizingPreview.current) setFailure(`外部视觉同步失败，当前预览已保留：${String(error)}`); }
      finally { synchronizingPreview.current = false; setPreviewConnecting(false); inFlight = false; }
    };
    const timer = setInterval(() => void synchronize(), 2000);
    return () => { alive = false; clearInterval(timer); };
  }, [current?.id, authoringOpen, busy, exportDocument, review, storageRevision, savedVisualRevision]);
  useEffect(() => { if (current) localStorage.setItem(ACTIVE, JSON.stringify({ documentId: current.id, projectId, previewCaseId: previewCase.current })); }, [current?.id, projectId, previewCase.current]);

  function updateDocumentUrl(documentId: string) {
    const url = new URL(window.location.href);
    url.searchParams.set('documentId', documentId);
    window.history.replaceState(window.history.state, '', url);
  }

  const save = useCallback(async () => {
    if (!historyRef.current || saving.current) return;
    if (!readyPreview()) { setFailure('预览正在接入当前源码，请完成后再保存。'); return; }
    if (historyRef.current.document.sourceBindingDigest.startsWith('preview-only:')) {
      try {
        await previewEngine.current?.save();
        const snapshot = await previewEngine.current?.snapshot();
        if (snapshot) { await receivePreviewState(snapshot); savedPreviewGraph.current = JSON.stringify(snapshot.graph); if (historyRef.current) await rememberPreviewSave(localStorage, historyRef.current.document, snapshot.graph); }
        setPreviewDirty(false); setSavedVisualRevision(historyRef.current?.document.revision ?? -1);
        setNotice('当前预览已保存到浏览器；可下载编辑 JSON 搬运完整图。'); setFailure('');
      }
      catch (error) { setFailure(String(error)); }
      return;
    }
    saving.current = true;
    const sequence = loadSequence.current;
    setBusy(true);
    try {
      await previewEngine.current?.save();
      const snapshot = await previewEngine.current?.snapshot();
      if (sequence !== loadSequence.current) return;
      if (snapshot) await receivePreviewState(snapshot);
      const frozenHistory = historyRef.current;
      if (!frozenHistory || sequence !== loadSequence.current) return;
      const frozen = frozenHistory.document;
      const result = await api.save(frozen, storageRevision, frozenHistory);
      if (sequence !== loadSequence.current || historyRef.current?.document.id !== frozen.id) return;
      if (snapshot) { savedPreviewGraph.current = JSON.stringify(snapshot.graph); await rememberPreviewSave(localStorage, frozen, snapshot.graph); }
      setPreviewDirty(false);
      setStorageRevision(result.revision); setSavedVisualRevision(frozen.revision);
      updateDocumentUrl(frozen.id);
      setNotice('画布已保存到正式工程 .archcanvas；可重开继续编辑'); setFailure('');
    } catch (error) { if (sequence === loadSequence.current) setFailure(`保存失败，当前编辑已保留：${String(error)}`); }
    finally { saving.current = false; if (sequence === loadSequence.current) setBusy(false); }
  }, [storageRevision]);

  useEffect(() => {
    const down = (event: KeyboardEvent) => {
      if (event.defaultPrevented || taskDialog || authoringOpen || editingTarget(event.target) || review || exportDocument || connectionProposal || runtimeOpen || importOpen) return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); event.shiftKey ? redo() : undo(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'y') { event.preventDefault(); redo(); }
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); previewEngine.current?.command('apply-layout'); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); void save(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a') { event.preventDefault(); previewEngine.current?.command('select-nodes', {scope:'all'}); }
      if (event.key === 'Escape' && previewSnapshot.current?.canCancel) { event.preventDefault(); previewEngine.current?.command('cancel-operation'); return; }
      if (event.key === 'Escape') { cancelGesture(); previewEngine.current?.command('select-nodes', {scope:'clear'}); setSelection({ kind: 'node', ids: [] }); }
      if (!event.ctrlKey && !event.metaKey && !event.altKey) {
        if (event.key.toLowerCase() === 'f') fit();
        if (event.key.toLowerCase() === 'v') chooseTool('select');
        if (event.key.toLowerCase() === 'c') chooseTool('connect');
        if (event.key.toLowerCase() === 'b') chooseTool('bend');
      }
    };
    window.addEventListener('keydown', down);
    return () => { window.removeEventListener('keydown', down); };
  }, [fit, redo, save, undo, review, exportDocument, connectionProposal, runtimeOpen, importOpen, cancelGesture, authoringOpen, taskDialog]);

  async function semanticProject(base: CanvasDocument, sequence: number) {
    if (base.sourceBindingDigest.startsWith('preview-only:')) throw new Error('请先进入编辑模式，从原 Python 建立正式源码绑定。');
    // Save the current presentation before opening a source-bound review.
    if (base.revision !== savedVisualRevision) {
      const saved = await api.save(base, storageRevision);
      if (sequence !== loadSequence.current) throw new Error('已切换文档，请重新准备');
      setStorageRevision(saved.revision); setSavedVisualRevision(base.revision);
    }
    const project = projectId ?? (await api.register(base.architecture)).id;
    if (sequence !== loadSequence.current) throw new Error('已切换文档，请重新准备');
    setProjectId(project);
    return project;
  }
  async function prepareSemantic(prepare: (project: string, architecture: Architecture) => Promise<Transaction>) {
    const base = historyRef.current?.document;
    if (!base || busy) return;
    const sequence = loadSequence.current;
    setBusy(true); setFailure(''); setReviewError('');
    try {
      const project = await semanticProject(base, sequence);
      const transaction = await prepare(project, base.architecture);
      if (sequence !== loadSequence.current) return;
      setReview({ transaction, base, projectId: project });
      localStorage.setItem(REVIEW, JSON.stringify({ projectId: project, id: transaction.id }));
      setNotice(transaction.status === 'ReviewReady' ? '工作副本修改已验证，等待具体审核' : '已保留未通过的事务及原因');
    } catch (error) { if (sequence === loadSequence.current) setFailure(`修改预览失败：${String(error)}`); }
    finally { if (sequence === loadSequence.current) { setBusy(false); setRuntimeCancel(null); setCancelling(false); } }
  }
  async function inspectRebind(nodeId: string, portId: string) {
    const base = historyRef.current?.document;
    if (!base || busy) throw new Error('画布正在处理，请稍后重试');
    const sequence = loadSequence.current;
    setBusy(true); setFailure('');
    try {
      const project = await semanticProject(base, sequence);
      if (!inputSpec) throw new Error('先设置运行输入与模式；连接操作不会自动降级为静态提交');
      return await api.structuralRebindOptions(project, base.architecture, nodeId, portId, inputSpec);
    } finally { if (sequence === loadSequence.current) setBusy(false); }
  }
  async function inspectConfiguration(parameter: string) {
    const base = historyRef.current?.document;
    if (!base || busy || !selectedNode) throw new Error('先选择参数对象');
    const sequence = loadSequence.current;
    setBusy(true);
    try { return await api.configurationOptions(await semanticProject(base, sequence), base.architecture, selectedNode.id, parameter); }
    finally { if (sequence === loadSequence.current) setBusy(false); }
  }
  function prepareParameter(parameter: string, value: number, configuration: boolean) {
    if (selectedNode) void prepareSemantic((project, architecture) => (configuration ? api.prepareConfiguration : api.prepare)(project, architecture, selectedNode.id, parameter, value));
  }
  function prepareActivation(activation: string) {
    if (!inputSpec || !selectedNode) return;
    void prepareSemantic((project, architecture) => api.prepareActivation(project, architecture, selectedNode.id, activation, inputSpec, cancel => setRuntimeCancel(() => cancel)));
  }
  function prepareRebind(nodeId: string, portId: string, producer: Binding) {
    if (!inputSpec) { setFailure('缺少运行输入与模式，连接提案无法提交'); return; }
    void prepareSemantic((project, architecture) => api.prepareStructuralRebind(project, architecture, nodeId, portId, producer, inputSpec, cancel => setRuntimeCancel(() => cancel)));
  }
  async function cancelRuntime() {
    if (!runtimeCancel || cancelling) return;
    setCancelling(true); setNotice('正在取消运行验证…');
    try { await runtimeCancel(); }
    catch (error) { setFailure(`取消请求失败：${String(error)}`); setCancelling(false); }
  }
  async function approveParameter() {
    if (!review || busy) return;
    setBusy(true); setReviewError('');
    try { const transaction = await api.approve(review.projectId, review.transaction); setReview({ ...review, transaction }); }
    catch (error) { setReviewError(String(error)); }
    finally { setBusy(false); }
  }
  async function commitParameter() {
    if (!review || busy) return;
    setBusy(true); setReviewError('');
    try {
      const transaction = await api.commit(review.projectId, review.transaction);
      setReview({ ...review, transaction });
      if (transaction.status !== 'Committed' || !transaction.committedArchitecture) return;
      const prior = historyRef.current?.document ?? review.base;
      const reconciled = reconcileDocument(prior, transaction.committedArchitecture);
      const next = createHistory(reconciled.document);
      if (inputSpec) localStorage.setItem(`archcanvas.runtime-profile:${next.document.id}`, JSON.stringify(inputSpec));
      historyRef.current = next; setHistory(next); setStorageRevision(0); setSavedVisualRevision(-1);
      setNotice(`工作副本已提交；保留 ${reconciled.preservedNodeIds.length} 个对象的视觉编辑。源码变更不属于画布撤销。`);
      localStorage.removeItem(REVIEW);
      try {
        const saved = await api.save(next.document, 0);
        setStorageRevision(saved.revision); setSavedVisualRevision(next.document.revision);
      } catch (error) { setReviewError(`源码已提交，画布保存失败；当前编辑仍保留：${String(error)}`); }
    } catch (error) { setReviewError(String(error)); }
    finally { setBusy(false); }
  }
  async function closeReview() {
    if (!review || busy) return;
    if (['ReviewReady', 'Approved', 'Failed', 'Stale'].includes(review.transaction.status)) {
      setBusy(true);
      try { await api.discard(review.projectId, review.transaction.id); }
      catch (error) { setReviewError(String(error)); setBusy(false); return; }
      setBusy(false);
    }
    localStorage.removeItem(REVIEW); setReview(null); setReviewError('');
  }
  function synchronizePreviewNodeSelection(value: unknown) {
    const ids = Array.isArray(value) ? [...new Set(value.filter((id): id is string => typeof id === 'string'))] : [];
    setPreviewSelectedNodeIds(previous => previous.length === ids.length && previous.every((id, index) => id === ids[index]) ? previous : ids);
  }
  function arrangePreview(kind: string) {
    if (previewLayoutDisabled || !previewCanAlign) return;
    setFailure(''); setActionFeedback(null); previewEngine.current?.command('arrange-selection', { kind, scope: layoutMoveScope });
  }
  function pinPreviewSelection() {
    if (previewLayoutDisabled || !previewSelectedNodes.length) return;
    setFailure(''); previewEngine.current?.command('pin-selection', { pinned: !previewAllPinned });
  }
  async function applyInspectionVisual(operations: Record<string, unknown>[]) {
    if (!readyPreview() || previewLayoutDisabled) return;
    const sequence = loadSequence.current;
    try { await previewEngine.current!.visual(operations); }
    catch (error) { if (sequence === loadSequence.current) setFailure(String(error)); }
  }
  function runCommand() {
    if (!selectedNode || !current) { setFailure('先在画布或层级中选择一个节点'); return; }
    const text = command.trim(); const ops: VisualOperation[] = [];
    const movement = parseMoveCommand(text, selection.ids, layoutMoveScope);
    if (movement.status === 'invalid') { setFailure(movement.reason); return; }
    if (movement.status === 'ready') { apply([movement.operation], `文字移动已应用 · ${movement.operation.scope === 'current-frontier' ? '仅当前视图' : '所有视图'}；Ctrl+Z 可撤销。`); setCommand(''); return; }
    const colors: Record<string, string> = { 蓝色: '#dcebf6', 绿色: '#deeee6', 紫色: '#ece3f4', 橙色: '#f4e6d0', 灰色: '#e8ecf0' };
    const color = Object.keys(colors).find(c => text.includes(c));
    const alias = text.match(/(?:命名为|改名为|显示名设为|显示名改为)\s*[“"']?(.+?)[”"']?$/);
    if (color) for (const id of selection.ids) ops.push({ type: 'nodeStyle', id, style: { fill: colors[color] } });
    if (alias && selection.ids.length !== 1) { setFailure('修改显示名称时请选择一个节点。'); return; }
    if (alias) ops.push({ type: 'alias', id: selectedNode.id, label: alias[1] });
    if (text.includes('展开') && selectedNode.children.length > 0) ops.push({ type: 'expand', id: selectedNode.id, expanded: true });
    if (text.includes('收起') && selectedNode.children.length > 0) ops.push({ type: 'expand', id: selectedNode.id, expanded: false });
    if (text.includes('固定')) ops.push({ type: 'pin', ids: selection.ids, pinned: !text.includes('取消固定') });
    if (!ops.length) { setFailure('本地视觉指令支持：向右移动 24、仅当前视图向下移动 16、设为蓝色/绿色/紫色、命名为…、展开、收起、固定。Dropout 参数请在对象面板预览并审核。'); return; }
    apply(ops, '文字指令已写入同一画布操作历史'); setCommand('');
  }
  async function importSource() {
    if (busy || previewConnecting || previewBusy) { setFailure('请等待当前模型载入或图操作完成后再导入。'); return; }
    cancelGesture();
    const sequence = ++loadSequence.current;
    ++previewSequence.current;
    previewLoading.current = true; setPreviewConnecting(true); setBusy(true); setFailure('');
    try {
      const request = { files: { [filename]: sourceText }, entry, config: {}, semanticMode: 'summary' as const };
      const bundle = await api.previewAnalyze(request);
      if (sequence !== loadSequence.current) return;
      previewSource.current = bundle; previewCase.current = bundle.id;
      await previewEngine.current!.load(bundle);
      const snapshot = await previewEngine.current!.snapshot();
      if (sequence !== loadSequence.current) return;
      previewSnapshot.current = snapshot;
      try {
        const arch = await api.previewEditSource(request);
        if (sequence !== loadSequence.current) return;
        if (previewNeedsPanelDocument(snapshot, arch, bundle)) {
          previewBoundSource.current = '';
          historyRef.current = createHistory(previewPanelDocument(snapshot, bundle)); setHistory(historyRef.current);
          setProjectId(null); setStorageRevision(0); setSavedVisualRevision(-1);
          setNotice('递归预览与源码已打开；展示图元可独立编辑，模型编辑使用已解析的源码对象。');
        } else {
          previewBoundSource.current = arch.sourceDigest + ':' + arch.irDigest;
          await openArchitecture(arch, true, sequence);
        }
      } catch (error) {
        if (sequence !== loadSequence.current) return;
        previewBoundSource.current = '';
        historyRef.current = createHistory(previewPanelDocument(snapshot, bundle)); setHistory(historyRef.current);
        setProjectId(null); setStorageRevision(0); setSavedVisualRevision(-1);
        setNotice(`递归预览已打开；此源码暂超出现有编辑契约：${String(error)}`);
      }
      if (sequence !== loadSequence.current) return;
      previewLoading.current = false;
      await receivePreviewState(snapshot);
      setImportOpen(false);
    }
    catch (error) { if (sequence === loadSequence.current) setFailure(String(error)); }
    finally { if (sequence === loadSequence.current) { previewLoading.current = false; setPreviewConnecting(false); setBusy(false); } }
  }
  async function importCanvasJson(text: string) {
    const value = JSON.parse(text);
    if (['summary-source-adapter/1', 'summary-merge-recursive/1', 'archcanvas-native-semantic/1', 'semantic-canvas/1', 'archcanvas-architecture-document/1', 'semantic-authoring/1', 'archcanvas-source-semantic/2'].includes(value?.schema) || value?.graph?.recursive) {
      await previewEngine.current!.load(value);
    } else {
      await openArchitecture(validateArchitecture(value));
    }
    setImportOpen(false);
  }
  function focusNode(id: string) {
    cancelGesture();
    focusPreviewNode(id);
    setSelection({ kind: 'node', ids: [id] });
  }

  function focusAnnotation(id: string) {
    cancelGesture();
    previewEngine.current?.focus({ annotationId: id });
  }

  function addAnnotation() {
    if (!current || !readyPreview()) return;
    const id = `annotation-${crypto.randomUUID()}`;
    const raw = previewSnapshot.current?.graph as ({ nodes?: { x: number; y: number; w?: number; h?: number }[]; canvas?: [number, number] } | undefined);
    const visible = raw?.nodes?.filter(node => Number.isFinite(node.x) && Number.isFinite(node.y)) ?? [];
    const maxY = visible.length ? Math.max(...visible.map(node => node.y + (node.h ?? 70))) : 40;
    const maxX = visible.length ? Math.max(...visible.map(node => node.x + (node.w ?? 180))) : 40;
    const canvas = raw?.canvas;
    const width = 380, height = 64;
    const x = canvas ? Math.max(12, Math.min(maxX - width, canvas[0] - width - 12)) : Math.max(12, maxX - width);
    const y = canvas ? Math.max(12, Math.min(maxY + 24, canvas[1] - height - 12)) : maxY + 24;
    apply([{ type: 'annotation', annotation: { id, text: '双击模块展开或收起；使用视图菜单调整阅读范围。', x, y, width } }]);
    setSelection({ kind: 'annotation', ids: [id] });  focusAnnotation(id);
  }
  function moveAnnotationBelow() {
    if (!selectedAnnotation) return;
    const graph = previewSnapshot.current?.graph;
    if (!graph) return;
    const position = previewAnnotationPosition(graph, selectedAnnotation.id);
    if (position.x !== selectedAnnotation.x || position.y !== selectedAnnotation.y) apply([{ type: 'annotation', annotation: { ...selectedAnnotation, ...position } }], '说明已移到图下方；可撤销恢复原位置');
    focusAnnotation(selectedAnnotation.id);
  }
  function zoomCamera(factor: number | 'reset') {
    cancelGesture();
    previewEngine.current?.command('zoom', { factor });
  }

  function sourceDraftKey(document: CanvasDocument) { return sourceAuthoringKey(document); }
  async function cacheGeneratedWorkspace(workspace: AuthoringWorkspace, binding: GeneratedWorkspaceBinding) {
    const sequence = loadSequence.current;
    try { await writePersistentGeneratedWorkspace(workspace, binding); }
    catch { if (sequence === loadSequence.current) setFailure('浏览器未能保留工作区恢复记录；请保存当前草稿与画布。'); }
  }
  function retainAuthoringWorkspace(workspace: AuthoringWorkspace) {
    const key = authoringSessionKey.current;
    if (!key) return;
    const retained = { ...workspace, viewBaseline: workspace.viewBaseline ?? authoringSessions.current.get(key)?.viewBaseline,
      sourceHistory: { past: historyRef.current?.past.length ?? 0, future: historyRef.current?.future.length ?? 0 } };
    authoringSessions.current.set(key, retained);
    if (retained.draft.sourceProvenance) {
      const sequence = loadSequence.current;
      void writeSourceAuthoringWorkspace(retained).catch(() => {
        if (sequence === loadSequence.current) setFailure('浏览器未能保留源码编辑恢复记录；请保存当前草稿。');
      });
    }
    for (const binding of generatedWorkspaces.current.values()) if (binding.workspaceKey === key) cacheGeneratedWorkspace(retained, binding);
  }
  function openBlankAuthoring() {
    cancelGesture();
    const draft = blankDraft(`draft-${crypto.randomUUID()}`);
    const key = `draft:${draft.id}`;
    const workspace: AuthoringWorkspace = { draft, storageRevision: 0, savedRevision: -1 };
    authoringSessions.current.set(key, workspace);
    authoringSessionKey.current = key;
    setAuthoringWorkspace(workspace);
    setBrowseBaseline(undefined);
    setAuthoringOpen(true);
  }
  async function continueModelAuthoring() {
    cancelGesture();
    const frozen = historyRef.current?.document;
    if (!frozen || busy) return;
    if (frozen.sourceBindingDigest.startsWith('preview-only:')) {
      try { await bindPreviewSource(await previewEngine.current!.source(), true); }
      catch (error) { setFailure(`当前源码暂不能进入现有编辑契约：${String(error)}`); }
      return;
    }
    const sequence = loadSequence.current, key = sourceDraftKey(frozen);
    let generatedBinding = generatedWorkspaces.current.get(key);
    if (!generatedBinding) {
      const recovered = await readPersistentGeneratedWorkspace(frozen);
      if (sequence !== loadSequence.current || frozen !== historyRef.current?.document) return;
      if (recovered) {
        generatedBinding = recovered.binding; generatedWorkspaces.current.set(key, generatedBinding);
        authoringSessions.current.set(generatedBinding.workspaceKey, recovered.workspace);
      }
    }
    if (generatedBinding) {
      const workspace = authoringSessions.current.get(generatedBinding.workspaceKey);
      if (workspace) {
        setBusy(true); setFailure('');
        try {
          const view = { selection: selection.kind === 'node' ? selection.ids : [],
            camera: { ...cameraRef.current }, viewport: readCameraViewport() ?? undefined, tool,
            sourceHistory: { past: historyRef.current?.past.length ?? 0, future: historyRef.current?.future.length ?? 0 } };
          const translated = generatedSourceView(workspace, frozen, generatedBinding);
          const rebased = translated ? await resumeSourceAuthoring(workspace, translated, view,
            (draft, document, scene) => api.sourceDraftFrontier(draft, document, scene, true)) : workspace;
          if (sequence !== loadSequence.current || frozen !== historyRef.current?.document) return;
          const resumed = resumeGeneratedWorkspace(rebased, frozen, generatedBinding, view);
          authoringSessions.current.set(generatedBinding.workspaceKey, resumed); authoringSessionKey.current = generatedBinding.workspaceKey;
          cacheGeneratedWorkspace(resumed, generatedBinding);
          setBrowseBaseline(resumed.draft); setAuthoringWorkspace(resumed); setAuthoringOpen(true); return;
        } catch (error) { if (sequence === loadSequence.current) setFailure(String(error)); return; }
        finally { if (sequence === loadSequence.current) setBusy(false); }
      }
    }
    let retained = authoringSessions.current.get(key), recoveredSource = false;
    if (!retained) {
      try {
        const recovered = await readSourceAuthoringWorkspace(frozen);
        if (sequence !== loadSequence.current || frozen !== historyRef.current?.document) return;
        if (recovered) { retained = recovered; recoveredSource = true; authoringSessions.current.set(key, recovered); }
      } catch (error) {
        if (sequence === loadSequence.current) setFailure(`无法恢复源码编辑副本，原记录与画布已保留：${String(error)}`);
        return;
      }
    }
    if (retained) {
      const sourceView = { selection: recoveredSource ? authoringViewSelection(retained) : selection.kind === 'node' ? selection.ids : [],
        camera: recoveredSource && retained.camera ? { ...retained.camera } : { ...cameraRef.current },
        viewport: recoveredSource ? retained.viewport : readCameraViewport() ?? undefined, tool: recoveredSource ? retained.tool ?? tool : tool,
        sourceHistory: recoveredSource && retained.sourceHistory ? { ...retained.sourceHistory } : { past: historyRef.current?.past.length ?? 0, future: historyRef.current?.future.length ?? 0 } };
      const retainedRevision = retained.draft.sourceProvenance?.visualRevision;
      if (retainedRevision === frozen.revision) {
        const workspace = recoveredSource ? retained : followSourceView(retained, sourceView);
        authoringSessions.current.set(key, workspace); authoringSessionKey.current = key; setBrowseBaseline(workspace.viewBaseline); setAuthoringWorkspace(workspace); setAuthoringOpen(true); return;
      }
      setBusy(true); setFailure('');
      try {
        const workspace = await resumeSourceAuthoring(retained, frozen, sourceView,
          (draft, document, scene) => api.sourceDraftFrontier(draft, document, scene, true));
        if (sequence !== loadSequence.current || frozen !== historyRef.current?.document) return;
        authoringSessions.current.set(key, workspace); authoringSessionKey.current = key;
        setBrowseBaseline(workspace.viewBaseline);
        setAuthoringWorkspace(workspace); setAuthoringOpen(true); return;
      } catch (error) {
        if (sequence === loadSequence.current) setFailure(`源码视图已变化，无法安全重连编辑副本：${String(error)}`);
        return;
      } finally { if (sequence === loadSequence.current) setBusy(false); }
    }
    const conflicting = [...authoringSessions.current.values()].find(workspace => workspace.draft.sourceProvenance?.documentId === frozen.id &&
      (workspace.draft.sourceProvenance.sourceDigest !== frozen.sourceBindingDigest || workspace.draft.sourceProvenance.irDigest !== frozen.architecture.irDigest));
    if (conflicting) {
      setFailure('源码或 IR 摘要已变化；原搭建会话仍保留，请先回到原模型或另建独立草稿。');
      return;
    }
    setBusy(true); setFailure('');
    try {
      const imported = await api.importSourceDraft(frozen, buildScene(frozen));
      if (sequence !== loadSequence.current || frozen !== historyRef.current?.document) return;
      const workspace: AuthoringWorkspace = { draft: imported.draft, viewBaseline: structuredClone(imported.draft), storageRevision: 0, savedRevision: -1,
        selection: selection.kind === 'node' ? selection.ids.map(id => imported.sceneNodeBindings[id]).filter(Boolean) : [],
        camera: imported.draft.sourceProvenance?.viewCanvas ? undefined : { ...cameraRef.current },
        viewport: imported.draft.sourceProvenance?.viewCanvas ? undefined : readCameraViewport() ?? undefined, tool,
        sourceHistory: { past: historyRef.current?.past.length ?? 0, future: historyRef.current?.future.length ?? 0 } };
      authoringSessions.current.set(key, workspace); authoringSessionKey.current = key;
      setBrowseBaseline(workspace.draft);
      setAuthoringWorkspace(workspace); setAuthoringOpen(true);
    } catch (error) {
      if (sequence === loadSequence.current) setFailure(`无法进入模型编辑，当前画布已保留：${String(error)}`);
    } finally { if (sequence === loadSequence.current) setBusy(false); }
  }
  async function editCurrentPreview() {
    if (enteringAuthoring.current || busy || !historyRef.current) return;
    if (!readyPreview()) { setFailure('预览正在接入当前源码，请完成后再进入模型编辑。'); return; }
    enteringAuthoring.current = true;
    setBusy(true);
    setNotice('正在保留当前展开层级并准备编辑副本…');
    const sequence = loadSequence.current;
    try {
      // Begin is serialized against the iframe's current graph. No preliminary
      // full-source snapshot is needed just to choose the editor.
      const snapshot = previewSnapshot.current?.graph?.generic ? previewSnapshot.current : await previewEngine.current?.snapshot();
      if (sequence !== loadSequence.current) return;
      if (snapshot && !snapshot.graph?.generic) await receivePreviewState(snapshot);
      if (sequence !== loadSequence.current) return;
      if (snapshot?.graph?.generic) {
        const edited = await previewEngine.current!.author({ action: 'begin' });
        await receivePreviewState(edited); setSummaryEditorId(String(edited.caseId)); setAssemblyOpen(true); setFailure('');
        setNotice('已进入编辑副本，当前展开层级已保留。');
      } else await continueModelAuthoring();
    } catch (error) { setFailure(`无法同步当前预览，画布与编辑副本均已保留：${String(error)}`); }
    finally { enteringAuthoring.current = false; if (sequence === loadSequence.current) setBusy(false); }
  }
  async function openSummaryCatalog(model: SummaryCatalogModel, startup = false) {
    if (!startup && (busy || previewBusy || previewConnecting || review)) throw Error('请先完成当前模型操作。');
    const sequence = ++loadSequence.current;
    ++previewSequence.current;
    previewLoading.current = true; setBusy(true); setPreviewConnecting(true); setFailure('');
    try {
      const document = await loadSummaryCatalogModel(model);
      if (sequence !== loadSequence.current) return;
      await previewEngine.current!.load(document);
      const snapshot = await previewEngine.current!.snapshot();
      if (sequence !== loadSequence.current) return;
      previewSource.current = undefined; previewBoundSource.current = ''; previewCase.current = String(snapshot.caseId);
      historyRef.current = createHistory(previewPanelDocument(snapshot)); setHistory(historyRef.current);
      setSelection({ kind: 'node', ids: [] }); setProjectId(null); setStorageRevision(0); setSavedVisualRevision(-1);
      setSummaryEditorId(null); if (!startup) setTaskDialog(null);
      previewLoading.current = false;
      await receivePreviewState(snapshot);
      setNotice(`已打开 ${model.title}；保留原始语义与归档证据，本次未执行模型。`);
    } finally {
      if (sequence === loadSequence.current) { previewLoading.current = false; setBusy(false); setPreviewConnecting(false); }
    }
  }
  async function newSummaryModel() {
    if (busy || previewBusy || review || creatingModel) return;
    let title: string;
    try { title = modelName(newModelTitle); } catch (error) { setNewModelError(String(error)); return; }
    setCreatingModel(true); setBusy(true); setNewModelError('');
    try {
      const snapshot = await previewEngine.current!.author({ action: 'begin', blank: true, title });
      await receivePreviewState(snapshot); setSummaryEditorId(String(snapshot.caseId)); setAssemblyOpen(true); setFailure(''); setNewModelOpen(false);
    } catch (error) { setNewModelError(String(error)); } finally { setCreatingModel(false); setBusy(false); }
  }
  async function editSummary(operation: Record<string, unknown>) {
    const snapshot = await previewEngine.current!.author(operation);
    await receivePreviewState(snapshot);
    if (operation.action === 'import-source-model') { setSummaryEditorId(String(snapshot.caseId)); setAssemblyOpen(true); setNotice('已从源码创建完整模型副本；源码已保存，本次未执行代码。'); }
  }
  async function runSummaryObservation(inputSpec: Record<string, unknown>, onStart: (cancel: () => Promise<void>) => void): Promise<SummaryRuntimeResult> {
    if (!readyPreview() || previewLayoutDisabled) throw Error('请等待当前模型就绪。');
    const sequence = loadSequence.current, caseId = previewCase.current;
    const stored = (previewSnapshot.current?.graph?.generic as { ir?: { runtime?: Record<string, unknown> } } | undefined)?.ir?.runtime;
    const binding = stored?.binding as Record<string, unknown> | undefined;
    let files: Record<string, string>, entry: string, sourceSha256: string | undefined;
    if (stored?.source_files && typeof binding?.entry === 'string') {
      files = stored.source_files as Record<string, string>; entry = binding.entry;
      sourceSha256 = typeof binding.source_manifest_sha256 === 'string' ? binding.source_manifest_sha256 : undefined;
    } else {
      const source = sourceFromResult(await previewEngine.current!.source());
      if (!source) throw Error('当前模型没有可执行的 Python 文本。');
      const request = source.schema === 'summary-source-adapter/1' ? bundlePreviewRequest(source) : rawPreviewSourceRequest(source);
      files = request.files; entry = request.entry;
      if (source.schema === 'summary-source-adapter/1') sourceSha256 = source.sourceSha256;
    }
    if (sequence !== loadSequence.current || caseId !== previewCase.current) throw Error('模型已切换，未开始 CPU 观察。');
    const result = await api.observeSummary({ files, entry, inputSpec, ...(sourceSha256 ? { sourceSha256 } : {}) }, onStart);
    if (sequence !== loadSequence.current || caseId !== previewCase.current) throw Error('模型已切换，CPU 观察结果未应用。');
    return result;
  }

  async function compileSummaryModule(value: { source: string; entry: string; constructor: Record<string, unknown> }) {
    const generation = loadSequence.current, caseId = previewCase.current;
    const module = await api.summaryModule(value);
    if (generation !== loadSequence.current || caseId !== previewCase.current) throw new Error('模型已切换；源码解析结果未应用。');
    return module;
  }
  async function certifySummaryAssembly(ir: Record<string, unknown>) {
    const generation = loadSequence.current, caseId = previewCase.current;
    const result = await api.summaryAssembly(ir);
    if (generation !== loadSequence.current || caseId !== previewCase.current) throw new Error('模型已切换；局部复核结果未应用。');
    return result;
  }
  async function formalSourceEditor() {
    try {
      if (previewSnapshot.current?.authoring) {
        const snapshot = await previewEngine.current!.author({ action: 'source' });
        await receivePreviewState(snapshot); setSummaryEditorId(null);
        await bindPreviewSource(await previewEngine.current!.source(), true);
      } else await continueModelAuthoring();
    } catch (error) { setFailure(`正式源码工作副本未打开：${String(error)}`); }
  }
  async function openPreviewExport() {
    if (openingExport.current || !readyPreview() || busy) return;
    const engine = previewEngine.current!;
    const sequence = loadSequence.current, generation = previewSequence.current;
    openingExport.current = true; setPreviewConnecting(true);
    try {
      const snapshot = await engine.snapshot();
      if (sequence !== loadSequence.current || generation !== previewSequence.current || snapshot.caseId !== previewCase.current) throw new Error('模型已切换，请重新打开导出。');
      await receivePreviewState(snapshot);
      const frozen = historyRef.current?.document;
      if (!frozen || !readyPreview(frozen)) throw new Error('预览与当前源码尚未完成绑定。');
      const signature = JSON.stringify(snapshot.graph), frozenCase = String(snapshot.caseId), sourceDigest = frozen.sourceBindingDigest, irDigest = frozen.architecture.irDigest;
      const assertFrozen = async () => {
        const actual = await engine.snapshot();
        if (sequence !== loadSequence.current || generation !== previewSequence.current || actual.caseId !== frozenCase ||
          historyRef.current?.document.sourceBindingDigest !== sourceDigest || historyRef.current.document.architecture.irDigest !== irDigest ||
          JSON.stringify(actual.graph) !== signature) throw new Error('当前预览已变化，请关闭并重新打开导出，以保持图与来源一致。');
      };
      const whole = await engine.svg();
      await assertFrozen();
      const graph = graphFromSnapshot(snapshot)!;
      const mapped = new Map<string, string>(), choices: { nodeId: string; pathLabel: string }[] = [];
      const bindings = currentPreviewNodeBindings();
      for (const node of graph.nodes) {
        const id = bindings.get(node.id);
        if (!id) continue;
        mapped.set(id, node.id);
        if (node.expanded && frozen.architecture.nodes.find(item => item.id === id)?.children.length) {
          choices.push({ nodeId: id, pathLabel: frozen.displayAliases[id] ?? node.label ?? id });
        }
      }
      const detailSvg = new Map<string, string>();
      setExportPreview({ binding: previewExportBinding({ caseId: frozenCase, sourceDigest, irDigest, revision: previewVersion }), detailChoices: choices,
        editingDocument: JSON.stringify(snapshot, null, 2),
        sourcePackage: snapshot.adapter ? JSON.stringify(snapshot.adapter, null, 2) : undefined,
        svg: async id => {
          if (!id) return whole;
          if (detailSvg.has(id)) return detailSvg.get(id)!;
          const raw = mapped.get(id);
          if (!raw) throw new Error('所选详情没有对应的可见预览图元，请先展开并选择该模块。');
          await assertFrozen();
          const svg = await engine.svg(raw);
          await assertFrozen(); detailSvg.set(id, svg); return svg;
        } });
      setExportDocument(structuredClone(frozen)); setFailure('');
    } catch (error) { setFailure(`无法打开当前预览导出：${String(error)}`); }
    finally { openingExport.current = false; setPreviewConnecting(false); }
  }
  async function openGeneratedModel(generated: GeneratedDraft) {
    cancelGesture();
    const workspaceKey = authoringSessionKey.current;
    const workspace = workspaceKey ? authoringSessions.current.get(workspaceKey) : undefined;
    const sequence = ++loadSequence.current;
    const retained = createGeneratedCanvas(generated.architecture, generated.draft, generated, generated.presentationDraft);
    const document = retained.document;
    // Persist the exact generated model and its retained presentation before
    // switching away from the editor. Reload must reopen this generation.
    const opened = await api.open(generated.architecture);
    if (sequence !== loadSequence.current) return;
    if (opened.documentId !== document.id) throw new Error('新模型画布身份与生成结果不一致；当前编辑已保留。');
    const next = createHistory(document);
    const saved = await api.save(document, opened.revision, next);
    if (sequence !== loadSequence.current) return;
    if (workspace && workspaceKey) {
      const binding = { workspaceKey,
        documentId: document.id, sourceDigest: document.sourceBindingDigest, irDigest: document.architecture.irDigest,
        draft: structuredClone(workspace.draft), nodeBindings: { ...generated.nodeBindings, ...generated.containerBindings, ...retained.nodeBindings }, edgeBindings: generated.edgeBindings, visualRevision: document.revision };
      generatedWorkspaces.current.set(sourceDraftKey(document), binding);
      await cacheGeneratedWorkspace(workspace, binding);
    }
    if (sequence !== loadSequence.current) return;
    historyRef.current = next; setHistory(next);
    setStorageRevision(saved.revision); setSavedVisualRevision(document.revision);
    setReview(null); localStorage.removeItem(REVIEW); setSourceOpen(false);
    setSelection({ kind: 'node', ids: (workspace?.selection ?? []).flatMap(id => retained.nodeBindings[id] ? [retained.nodeBindings[id]] : []) });
    setProjectId(opened.projectId); setAuthoringOpen(false);
    updateDocumentUrl(document.id);
    if (workspace?.camera && !workspace.draft.sourceProvenance?.viewCanvas) { commitCamera(workspace.camera); setTool(workspace.tool ?? 'select'); }
    setNotice(`已打开新模型工作副本。${retained.hierarchyReflowed ? '新源码层级已重新排布，原草稿布局保留。' : '已保留搭建位置与视角。'}模型未执行。${retained.unmappedNodeIds.length ? ` ${retained.unmappedNodeIds.length} 个展示框没有对应的新源码节点。` : ''}${retained.unresolvedEdgeStyles.length ? ` ${retained.unresolvedEdgeStyles.length} 条连线样式待核对。` : ''}`);
  }
  async function openSourceEditedModel(architecture: Architecture) {
    cancelGesture();
    const sequence = ++loadSequence.current;
    const opened = await api.open(architecture);
    if (sequence !== loadSequence.current) return;
    await openArchitecture(architecture, true, sequence);
    if (sequence !== loadSequence.current) return;
    setProjectId(opened.projectId); setAuthoringOpen(false);
    updateDocumentUrl(opened.documentId);
    setNotice('已打开源码修改后的独立模型，并重新建立已解析的模型层级；原草稿与原始项目保留。模型未执行。');
  }
  const authoringView = authoringOpen ? <AuthoringStudio key={authoringSessionKey.current} initialWorkspace={authoringWorkspace} browseBaseline={browseBaseline}
    onViewState={retainAuthoringWorkspace} onClose={() => setAuthoringOpen(false)} onOpen={openGeneratedModel}
    onSourceOpen={openSourceEditedModel}
    onNewBlank={workspace => { retainAuthoringWorkspace(workspace); openBlankAuthoring(); }}
    onReuseView={async workspace => {
      retainAuthoringWorkspace(workspace);
      if (!browseBaseline) throw new Error(t("缺少原视图绑定。"));
      if (!sameGeneratedDraft(workspace.draft, browseBaseline)) {
        if (!sameSourceSemantics(workspace.draft, browseBaseline) || !historyRef.current) throw new Error(t("编辑内容已变化，需要重新生成视图。"));
        if (workspace.draft.sourceProvenance?.documentId !== historyRef.current.document.id) return false;
        const operations = sourcePresentationOperations(historyRef.current.document, browseBaseline, workspace.draft);
        if (operations.length) {
          const before = historyRef.current;
          await previewEngine.current?.visual(mapPreviewOperations(operations));
          const next = reduceHistory(before, { type: 'apply', operations });
          historyRef.current = next; setHistory(next);
        }
      }
      if (workspace.camera && !workspace.draft.sourceProvenance?.viewCanvas) commitCamera(workspace.camera);
      const selected = authoringViewSelection(workspace, current ? generatedWorkspaces.current.get(sourceDraftKey(current)) : undefined);
      setSelection({ kind: 'node', ids: selected });
      const focus = selected[0] ? previewNodeId(selected[0]) : undefined;
      if (focus) previewEngine.current?.focus({ nodeId: focus });
      setTool(workspace.tool ?? 'select'); setAuthoringOpen(false);
    }} /> : null;

  return <><div className="studio" hidden={authoringOpen}>
    <header className="topbar">
      <div className="brand"><span className="brand-mark"><i /><i /><i /></span><span>ArchCanvas<small>{t("模型架构工作台")}</small></span></div>
      <div className="project-breadcrumb"><span className="slash">/</span><Icon name="file" size={15} /><span>{current?.title ?? t("模型工作台")}</span></div>
      <nav className="workspace-menus" aria-label={t("工作台菜单")}>
        <details className="workspace-menu"><summary>{t("模型")}<span>⌄</span></summary><div>
          <div className="menu-heading">{t("打开与创建")}</div>
          <button disabled={busy || !!review} onClick={() => { setFailure(''); setImportOpen(true); }}><Icon name="file" size={15} />{t("导入 Python / 文档")}</button>
          <button disabled={busy || previewConnecting || previewBusy} onClick={() => { setSummaryCatalogOpen(true); setTaskDialog('library'); }}><Icon name="layers" size={15} />{t("浏览模型库")}</button>
          <button disabled={busy || !!review} onClick={() => { setNewModelTitle(''); setNewModelError(''); setNewModelOpen(true); }}><Icon name="plus" size={15} />{t("新建空白模型")}</button>
        </div></details>
        <details className="workspace-menu"><summary>{t("编辑")}<span>⌄</span></summary><div>
          <div className="menu-heading">{t("图形与组装副本")}</div>
          <button disabled={previewLayoutDisabled} onClick={() => { if (summaryEditing) setAssemblyOpen(true); else void editCurrentPreview(); }}>{t("打开构件编辑…")}</button>
          <button disabled={previewLayoutDisabled || !previewUndo} onClick={undo}>{t("撤销画布编辑")}<kbd>Ctrl Z</kbd></button>
          <button disabled={previewLayoutDisabled || !previewRedo} onClick={redo}>{t("重做画布编辑")}<kbd>Ctrl ⇧ Z</kbd></button>
          <div className="menu-heading">{t("源码工作流")}</div>
          <button disabled={!current || busy || previewBusy || previewConnecting} onClick={() => void formalSourceEditor()}>{t("正式源码工作副本")}</button>
          <button disabled={busy || !!review} onClick={openBlankAuthoring}>{t("新建正式源码模型")}</button>
        </div></details>
        <details className="workspace-menu"><summary>{t("视图")}<span>⌄</span></summary><div>
          <button disabled={previewLayoutDisabled} onClick={() => setTaskDialog('expansion')}><Icon name="layers" size={15} />{t("模块展开与预设…")}</button>
          <button disabled={previewLayoutDisabled} onClick={focusCurrentFrontier}>{t("定位当前模块")}</button>
          <button disabled={previewLayoutDisabled} onClick={() => fit()}><Icon name="fit" size={15} />{t("适合画布")}<kbd>F</kbd></button>
          <button aria-pressed={grid} disabled={previewLayoutDisabled} onClick={() => previewEngine.current?.command('grid', { enabled: !grid })}>{grid ? t("隐藏") : t("显示")}{t("点阵网格")}</button>
          <div className="menu-heading">{t("来源与观察")}</div>
          <button disabled={!current} onClick={() => setSourceOpen(true)}>{t("查看源码证据")}</button>
          <button disabled={previewLayoutDisabled} onClick={() => setTaskDialog('runtime')}>{t("运行观察与语义证据…")}</button>
          <div className="menu-heading">{t("展开范围")}</div>
          <button disabled={previewLayoutDisabled} onClick={() => previewEngine.current?.command('expand-all')}>{t("展开全部")}</button>
          <button disabled={previewLayoutDisabled} onClick={() => previewEngine.current?.command('collapse-all')}>{t("收起全部")}</button>
          <button disabled={previewLayoutDisabled} onClick={() => { cancelGesture(); previewEngine.current?.command('reset'); }}>{t("恢复初始视图（可撤销）")}</button>
        </div></details>
        <details className="workspace-menu"><summary>{t("排列")}<span>⌄</span></summary><div>
          <button disabled={previewLayoutDisabled} onClick={repairSummaryLayout}><Icon name="bend" size={15} />{t("优化当前连线")}<kbd>Ctrl ↵</kbd></button>
          <button disabled={previewLayoutDisabled} onClick={() => previewEngine.current?.command('show-routing')}>{t("布线与箭头设置…")}</button>
          <button disabled={previewLayoutDisabled} onClick={() => previewEngine.current?.command('continue-routing')}>{t("继续未完成布线")}</button>
          <div className="menu-heading">{t("对齐与分布 · 同级节点")}</div>
          <label className="menu-field">{t("移动范围")}<select aria-label={t("布局移动范围")} value={layoutMoveScope} onChange={event => setLayoutMoveScope(event.target.value as MoveScope)}><option value="all-frontiers">{t("所有视图")}</option><option value="current-frontier">{t("仅当前视图")}</option></select></label>
          {([{ kind: 'left', label: t("左对齐") }, { kind: 'hcenter', label: t("水平居中对齐") }, { kind: 'right', label: t("右对齐") }, { kind: 'top', label: t("顶部对齐") }, { kind: 'vcenter', label: t("垂直居中对齐") }, { kind: 'bottom', label: t("底部对齐") }, { kind: 'distribute-x', label: t("水平等距分布") }, { kind: 'distribute-y', label: t("垂直等距分布") }]).map(item => <button key={item.kind} disabled={previewLayoutDisabled || !previewCanAlign || (item.kind.startsWith('distribute') && (previewSelectedNodes.length < 3 || previewPinnedCount > 0))} onClick={() => arrangePreview(item.kind)}>{item.label}</button>)}
          <button aria-pressed={previewAllPinned} disabled={previewLayoutDisabled || !previewSelectedNodes.length} onClick={pinPreviewSelection}><Icon name="pin" size={15} />{previewAllPinned ? t("解锁所选节点") : t("固定所选节点")}</button>
        </div></details>
      </nav>
      <div className="header-actions"><LanguageSelector /><WorkspaceModeSwitch mode={summaryEditing ? 'edit' : 'view'} disabled={!current || busy || previewConnecting || previewBusy || !!review} onView={() => { setSummaryEditorId(null); setAssemblyOpen(false); setTaskDialog(null); }} onEdit={() => void editCurrentPreview()} /><span className={`save-state ${dirty ? 'dirty' : ''}`} aria-live="polite"><i />{current ? dirty ? t("未保存") : t("已保存") : t("等待文档")}</span><button onClick={save} disabled={!current || busy || previewConnecting || previewBusy}><Icon name="save" size={15} /><span>{t("保存")}</span></button><button className="primary" onClick={() => void openPreviewExport()} disabled={!current || busy || previewConnecting || previewBusy}><Icon name="export" size={16} />{t("导出")}</button></div>
    </header>
    <div className={`workspace ${leftCollapsed ? 'left-collapsed' : ''}`}>
      <nav className="workspace-rail" aria-label={t("工作区导航")}>
        <button aria-label={t("模型层级")} aria-pressed={!leftCollapsed && !assemblyOpen} onClick={() => { setAssemblyOpen(false); setLeftCollapsed(value => assemblyOpen ? false : !value); }}><Icon name="layers" size={19} /><span>{t("层级")}</span></button>
        <button aria-label={t("浏览模型库")} aria-pressed={taskDialog === 'library'} disabled={busy || previewConnecting || previewBusy} onClick={() => { setSummaryCatalogOpen(true); setTaskDialog('library'); }}><Icon name="grid" size={19} /><span>{t("模型库")}</span></button>
        <button aria-label={t("查看源码")} aria-pressed={sourceOpen} disabled={!current} onClick={() => setSourceOpen(value => !value)}><Icon name="code" size={19} /><span>{t("源码")}</span></button>
        {summaryEditing && <button aria-label={t("编辑模型构件")} aria-pressed={assemblyOpen} onClick={() => setAssemblyOpen(value => !value)}><Icon name="plus" size={19} /><span>{t("构件")}</span></button>}
        <button className="rail-bottom" aria-label={t("运行观察与语义证据")} aria-pressed={taskDialog === 'runtime'} disabled={previewLayoutDisabled} onClick={() => setTaskDialog('runtime')}><Icon name="info" size={19} /><span>{t("证据")}</span></button>
      </nav>
      <aside className="navigator" hidden={summaryEditing && assemblyOpen}>
        <div className="navigator-top"><div className="panel-title"><Icon name="layers" size={16} /><b>{t("模型层级")}</b><span>{navigation?.nodes.length ?? architecture?.nodes.length ?? 0}</span></div><label className="tree-search"><Icon name="search" size={14} /><input aria-label={t("搜索模型层级")} placeholder={t("搜索模块…")} value={treeSearch} onChange={e => setTreeSearch(e.target.value)} />{treeSearch && <button className="tool" aria-label={t("清除层级搜索")} onClick={() => setTreeSearch('')}><Icon name="close" size={12} /></button>}</label></div>
        <div className="tree" role="tree" aria-label={t("模型层级")} aria-multiselectable="true">
          {architecture && current && <HierarchyTree architecture={navigation ?? architecture} document={navigation ?? current} mandatoryIds={navigation?.mandatoryIds} selected={navigation ? previewSelectedNodeIds : selection.ids} onSelect={selectHierarchyNode} onExpand={expandHierarchyNode} query={treeSearch} />}
        </div>
        <div className="navigator-bottom"><button className={sourceOpen ? 'active' : ''} onClick={() => setSourceOpen(x => !x)} disabled={!current}><Icon name="code" size={16} />{t("查看源码证据")}<Icon name="chevron" size={13} /></button><div className="source-note"><span className="live-dot" />{previewSnapshot.current?.importedDocument ? t("导入文档证据") : t("静态源码视图")}</div></div>
      </aside>
      {summaryEditing && <aside className="assembly-dock" aria-label={t("模型构件编辑")} hidden={!assemblyOpen}>
        <div className="dock-heading"><div><b>{t("模型构件")}</b><span>{t("在编辑副本中组装")}</span></div><button className="tool" aria-label={t("关闭构件编辑")} onClick={() => setAssemblyOpen(false)}><Icon name="close" size={16} /></button></div>
        <div className="dock-content"><SummaryAuthoringPanel snapshot={previewSnapshot.current} selected={previewSelectedNodeIds} disabled={previewLayoutDisabled} onEdit={editSummary} onCompile={compileSummaryModule} onCertify={certifySummaryAssembly} onFormal={() => void formalSourceEditor()} /></div>
      </aside>}
      <main className="main" data-work-panel>
        <div className="workspace-caption"><button className="tool" aria-label={assemblyOpen ? t("显示模型层级面板") : leftCollapsed ? t("展开模型层级面板") : t("收起模型层级面板")} aria-pressed={!leftCollapsed && !assemblyOpen} onClick={() => { setAssemblyOpen(false); setLeftCollapsed(value => assemblyOpen ? false : !value); }} title={t("模型层级面板")}><Icon name="panelLeft" size={16} /></button><b>{current?.title ?? t("模型工作台")}</b><span className="workspace-context">{summaryEditing ? t("编辑副本") : t("模型视图")}</span><div className="caption-actions">{summaryEditing && <button onClick={() => setAssemblyOpen(value => !value)} aria-pressed={assemblyOpen}><Icon name="plus" size={14} />{t("构件")}</button>}<button disabled={previewLayoutDisabled} onClick={() => setTaskDialog('expansion')}><Icon name="layers" size={14} />{t("模块展开")}</button><button className="layout-apply" aria-label={t("优化当前连线")} title={t("按当前布线设置应用布局 · Ctrl+Enter")} disabled={previewLayoutDisabled} onClick={repairSummaryLayout}><Icon name="bend" size={14} />{t("优化连线")}</button></div></div>
        <div className="canvas-toolbar" role="toolbar" aria-label={t("画布编辑工具")}>
          <div className="tool-group">
            <button className={`tool ${previewTool === 'select' ? 'selected' : ''}`} title={t("选择与框选 · V")} aria-label={t("选择对象")} aria-pressed={previewTool === 'select'} disabled={previewLayoutDisabled} onClick={() => chooseTool('select')}><Icon name="arrow" /></button>
            <details className="selection-menu"><summary aria-label={t("选区操作")} title={t("选区操作")}><Icon name="chevron" size={13} /></summary><div><div className="menu-heading">{previewSelectedNodes.length ? t("已选 {0} 个节点", {"0": previewSelectedNodes.length}) : t("选择对象")}</div><p className="menu-help">{t("单击选择；Ctrl / Shift / ⌘ 点击增减选区，拖动空白处框选。")}</p><button disabled={previewLayoutDisabled || !previewSelectedNodes.length} onClick={() => previewEngine.current?.command('select-nodes', { scope: 'siblings' })}>{t("选择同级节点")}</button><button disabled={previewLayoutDisabled} onClick={() => previewEngine.current?.command('select-nodes', { scope: 'all' })}>{t("选择全部可见模块")}<kbd>Ctrl A</kbd></button><button disabled={previewLayoutDisabled || !previewSelectedNodes.length} onClick={() => previewEngine.current?.command('select-nodes', { scope: 'clear' })}>{t("清空选区")}<kbd>Esc</kbd></button></div></details>
            {([{ id: 'connect', icon: 'connect', label: t("创建连接"), hint: t("创建视觉草稿连接 · C") }, { id: 'bend', icon: 'bend', label: t("编辑折点"), hint: t("选择连线，添加或拖动折点 · B") }] as const).map(item => <button key={item.id} title={item.hint} aria-label={item.label} aria-pressed={previewTool === item.id} className={`tool ${previewTool === item.id ? 'selected' : ''}`} disabled={previewLayoutDisabled} onClick={() => chooseTool(item.id)}><Icon name={item.icon} /></button>)}
            <button className={`tool ${portEditing ? 'selected' : ''}`} title={t("显示连接点；选中连线后可拖动 S / T 端点")} aria-label={t("显示连接点")} aria-pressed={portEditing} disabled={previewLayoutDisabled} onClick={() => { cancelGesture(); previewEngine.current?.command('show-ports', { visible: !portEditing }); }}><Icon name="ports" /></button>
            <span className="tool-divider" />
            <button className="tool" onClick={undo} disabled={!previewUndo || previewLayoutDisabled} title={t("撤销 Ctrl+Z")} aria-label={t("撤销画布编辑")}><Icon name="undo" /></button>
            <button className="tool" onClick={redo} disabled={!previewRedo || previewLayoutDisabled} title={t("重做 Ctrl+Shift+Z")} aria-label={t("重做画布编辑")}><Icon name="redo" /></button>
            <span className="tool-divider" />
            <button className="tool" onClick={() => fit()} title={t("适合画布 · F")} aria-label={t("适合画布")} disabled={previewLayoutDisabled}><Icon name="fit" /></button>
          </div>
        </div>
        {actionFeedback && <div className={`canvas-feedback ${actionFeedback.error ? 'error' : ''}`} role={actionFeedback.error ? 'alert' : 'status'}><Icon name={actionFeedback.error ? 'info' : 'check'} size={15} /><span>{uiMessage(actionFeedback.message)}</span><button className="tool" aria-label={t("关闭操作反馈")} onClick={() => setActionFeedback(null)}><Icon name="close" size={13} /></button></div>}
        <div ref={viewportRef} className="canvas-viewport prototype-canvas" data-canvas-surface="recursive-preview">
          <PreviewStudio ref={previewEngine} visible={!authoringOpen} onState={snapshot => void receivePreviewState(snapshot)} onInteraction={receivePreviewInteraction}
            onSelection={receivePreviewSelection} onEditSource={result => { void bindPreviewSource(result, true).catch(error => setFailure(String(error))); }}
            onError={message => { setFailure(message); setActionFeedback({message, error: true}); }} onNotice={(message, error) => { setNotice(message); setFailure(error ? message : ''); setActionFeedback({message, error}); }} onSave={() => void save()} />
        </div>

        {sourceOpen && architecture && <div className="source-drawer"><div className="drawer-header"><Icon name="code" size={16} /><b>{t("源码证据")}</b><span>{previewSourceSpan ? `${previewSourceSpan.path}:${previewSourceSpan.line}` : t("只读 · 未执行")}</span><button className="tool" onClick={() => setSourceOpen(false)} aria-label={t("关闭源码")}><Icon name="close" size={16} /></button></div><div className="source-content">{current?.sourceBindingDigest.startsWith('preview-only:') && <p className="field-help">{t("只读源码文本。展示对象没有经过正式模型解析的计算绑定；可在编辑模式中解析支持的源码入口。")}</p>}{!previewSourceSpan && architecture.sources.length > 0 && <p className="field-help">{t("当前图元没有独立的源码行证据，以下提供完整模型源码供查阅。")}</p>}{architecture.sources.length === 0 && <p className="field-help">{previewSnapshot.current?.importedDocument ? t("当前为 Summary 导入文档，源码位置尚未与 Python 文本验证绑定；可通过原始文档检查声明证据。") : t("当前案例是视觉或路由示例，没有模型源码。")}</p>}{architecture.sources.map(source => <div key={source.path}><div className="source-filename">{source.path}</div><pre>{source.content.split('\n').map((line, i) => <div key={i} className={previewSourceSpan?.path === source.path && i + 1 >= previewSourceSpan.line && i + 1 <= previewSourceSpan.endLine ? 'source-highlight' : ''}><span>{i + 1}</span>{line || ' '}</div>)}</pre></div>)}</div></div>}
      </main>

    </div>
    <footer className={`statusbar ${failure ? 'has-error' : ''}`}><span><i className={busy ? 'busy-dot' : 'live-dot'} />{uiMessage(failure || (runtimeCancel ? cancelling ? t("正在取消运行验证…") : t("正在隔离运行并核对前后结构…") : busy ? t("正在处理…") : notice))}</span><div>{previewCanCancel && <button onClick={() => previewEngine.current?.command('cancel-operation')}>{t("取消当前图操作")}</button>}{runtimeCancel && <button disabled={cancelling} onClick={() => void cancelRuntime()}>{cancelling ? t("取消中…") : t("取消运行验证")}</button>}{selection.ids.length > 0 && <span>{selection.ids.length}{t("个已选")}</span>}<span>RECURSIVE PREVIEW</span><span>rev {current?.revision ?? 0}</span></div></footer>
    {newModelOpen && <WorkspaceDialog title={t("新建空白模型")} description={t("设置模型名称，然后添加构件或导入自定义源码模块。名称可在编辑面板中随时修改。")} onClose={() => { if (!creatingModel) setNewModelOpen(false); }}>
      <form className="new-model-form" onSubmit={event => { event.preventDefault(); void newSummaryModel(); }}>
        <label className="field-label">{t("模型名称")}<input aria-label={t("新模型名称")} autoFocus maxLength={240} placeholder={t("例如 VisionEncoder")} value={newModelTitle} disabled={creatingModel} onChange={event => setNewModelTitle(event.target.value)} /></label>
        {newModelError && <p role="alert">{uiMessage(newModelError)}</p>}
        <p className="field-help">{t("界面语言切换不会改变此名称、模块名称或 Python 标识符。")}</p>
        <div className="modal-actions"><button type="button" disabled={creatingModel} onClick={() => setNewModelOpen(false)}>{t("取消")}</button><button className="primary" type="submit" disabled={creatingModel || !newModelTitle.trim()}>{creatingModel ? t("正在创建…") : t("创建模型")}</button></div>
      </form>
    </WorkspaceDialog>}
    {taskDialog === 'library' && <WorkspaceDialog title={t("模型库")} description={t("选择一个模型，或恢复已保存的文档。")} onClose={() => setTaskDialog(null)}>
      <SummaryCatalogPanel open={summaryCatalogOpen} onToggle={setSummaryCatalogOpen} disabled={busy || previewBusy || previewConnecting || !!review} onOpen={async model => { await openSummaryCatalog(model); setTaskDialog(null); }} onBrowseSaved={() => { setTaskDialog(null); previewEngine.current?.command('show-library'); }} />
    </WorkspaceDialog>}
    {taskDialog === 'expansion' && <WorkspaceDialog title={t("模块展开")} description={t("选择阅读范围；每个模块可以保留自己的展开深度。")} onClose={() => setTaskDialog(null)}>
      <SummaryViewPanel onContinue={() => previewEngine.current?.command('continue-routing')} snapshot={previewSnapshot.current} selectedIds={previewSelectedNodeIds} disabled={previewLayoutDisabled} onCommand={payload => previewEngine.current?.command('semantic-view', payload)} onFocus={id => previewEngine.current?.focus({ nodeId: id })} />
      {!previewSnapshot.current?.semanticView && <p className="field-help">{t("当前文档使用递归视图，可在左侧层级树或画布中双击展开模块。")}</p>}
    </WorkspaceDialog>}
    {taskDialog === 'runtime' && current && <WorkspaceDialog title={t("运行观察与语义证据")} description={t("查看来源与已有观察；新运行需要明确填写输入规格。")} onClose={() => setTaskDialog(null)}>
      <SummaryRuntimePanel key={previewCase.current} available={capabilities?.runtimeProfiles?.summaryObserved === true} reason={capabilities?.runtimeProfiles?.unavailableReason} hasSource={summaryRuntimeHasSource} storedReceipt={summaryRuntimeReceipt} disabled={previewLayoutDisabled} onRun={runSummaryObservation} onSaveEvidence={document => download('summary-observation.json', JSON.stringify(document, null, 2), 'application/json')} snapshot={previewSnapshot.current} selectedIds={previewSelectedNodeIds} onCommand={payload => previewEngine.current?.command('semantic-view', payload)}>
        <SummarySemanticPanel embedded source={previewSource.current} selectedIds={previewSelectedNodeIds} onFocus={id => previewEngine.current?.focus({ nodeId: id })} onEvidence={() => { setTaskDialog(null); previewEngine.current?.command('show-evidence'); }} />
      </SummaryRuntimePanel>
    </WorkspaceDialog>}

    {runtimeOpen && architecture && <RuntimeProfileDialog architecture={architecture} initial={inputSpec} example={false} onSave={saveInputSpec} onClose={() => setRuntimeOpen(false)} />}
    {connectionProposal && <div className="modal-backdrop"><div className="runtime-modal connection-proposal" role="dialog" aria-modal="true" aria-labelledby="proposal-title"><div className="modal-heading"><div><div className="eyebrow">CONNECTION PROPOSAL</div><h2 id="proposal-title">{connectionProposal.candidate ? t("检查改接提案") : t("保留未支持的连接提案")}</h2></div><button className="tool" aria-label={t("关闭连接提案")} onClick={() => setConnectionProposal(null)}><Icon name="close" /></button></div>{connectionProposal.candidate ? <p>{t("将选定输入连接到")}<b>{connectionProposal.candidate.variable}</b>{t("。当前只创建提案；运行验证后会展示准确源码 diff 和前后关系，批准后才能提交工作副本。")}</p> : connectionProposal.blockers.map((blocker, i) => <p key={i}>{blocker}</p>)}<div className="modal-actions"><button onClick={() => setConnectionProposal(null)}>{t("保留当前连接")}</button>{!inputSpec && <button onClick={() => { setConnectionProposal(null); setRuntimeOpen(true); }}>{t("设置运行输入与模式")}</button>}{connectionProposal.candidate && <button className="primary" disabled={busy} onClick={() => { const proposal = connectionProposal; setConnectionProposal(null); prepareRebind(proposal.nodeId, proposal.portId, proposal.candidate!.binding); }}>{t("运行验证并预览源码修改")}</button>}</div></div></div>}
    {review && <ReviewDialog base={review.base} transaction={review.transaction} busy={busy} error={reviewError} onApprove={() => void approveParameter()} onCommit={() => void commitParameter()} onClose={() => void closeReview()} />}
    {exportDocument && exportPreview && <ExportDialog document={exportDocument} capabilities={capabilities}
      selectedId={selection.kind === 'node' && selection.ids.length === 1 ? selection.ids[0] : undefined}
      previewExport={exportPreview}
      onClose={() => { setExportDocument(null); setExportPreview(null); }} />}
    {importOpen && <SourceImportDialog entry={entry} filename={filename} source={sourceText} busy={busy} error={failure} onEntry={setEntry} onFilename={setFilename} onSource={setSourceText} onJson={importCanvasJson} onError={setFailure} onAnalyze={() => void importSource()} onClose={() => setImportOpen(false)} onProject={() => { setImportOpen(false); previewEngine.current?.command('show-import'); }} />}

  </div>{authoringView}</>;
}

function TextField({ label, value, onCommit }: { label: string; value: string; onCommit: (value: string) => void }) {
  const [draft, setDraft] = useState(value);
  const cancelled = useRef(false);
  useEffect(() => setDraft(value), [value]);
  return <label className="text-field">{label && <span className="field-label">{label}</span>}<input aria-label={label || t("图例文字")} value={draft} onChange={e => { cancelled.current = false; setDraft(e.target.value); }} onBlur={() => { if (!cancelled.current && draft !== value) onCommit(draft); cancelled.current = false; }} onKeyDown={e => { if (e.nativeEvent.isComposing) return; if (e.key === 'Enter') e.currentTarget.blur(); if (e.key === 'Escape') { cancelled.current = true; setDraft(value); e.currentTarget.blur(); } }} /></label>;
}
