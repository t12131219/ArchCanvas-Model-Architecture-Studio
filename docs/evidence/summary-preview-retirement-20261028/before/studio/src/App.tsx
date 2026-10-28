import { rememberPreviewSave, matchesPreviewSave } from './previewSaveState';
import { SourceImportDialog } from './SourceImportDialog';
import { SummaryViewPanel } from './SummaryViewPanel';
import { SummaryAuthoringPanel } from './SummaryAuthoringPanel';
import { SummarySemanticPanel } from './SummarySemanticPanel';
import { useWorkspaceMenus } from './WorkspaceUI';
import { sameSourceSemantics, sourcePresentationOperations } from './sourcePresentation';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { applyVisualBatch, buildScene, createDocument, createHistory, reconcileDocument, reduceHistory, validateArchitecture, presentEditorScene, editorSceneBounds, implicitRootIds } from './core';
import type { Architecture, CanvasDocument, HistoryState, MoveScope, ScenePort, VisualOperation } from './core';
import { api } from './api';
import type { Binding, Capabilities, Example, InputSpec, RebindOptions, Transaction } from './api';
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
import { prepareMovePreview, previewMoveScene } from './core/movePreview';
import type { MovePreviewSession } from './core/movePreview';
import { beginCameraPan, cameraAtPanInput } from './cameraGesture';
import type { CameraState, CameraPan } from './cameraGesture';
import { canvasDotGrid, clampCanvasZoom, fitCameraToBounds, focusCameraOnPoint, paperTranslation, viewportToWorld, zoomCameraAtPoint } from './cameraProjection';
import { canApplyCameraViewTicket, readCameraView, sameCameraViewDocument, writeCameraView } from './cameraViewState';
import type { CameraViewIdentity, CameraViewStorage, CameraViewTicket } from './cameraViewState';
import { cameraViewportSize, resizeCameraViewport } from './cameraViewport';
import type { CameraViewport } from './cameraViewport';
import { edgeAppearance } from './edgeAppearance';
import { edgePatternLabel } from './core/edgePresentation';
import { findAnnotationBodyConflicts, suggestAnnotationPosition } from './core/annotationPlacement';
import { layoutWarnings } from './layoutWarnings';
import { planLayoutRecovery } from './core/layoutRecovery';
import { parseMoveCommand } from './moveCommand';
import type { LayoutRecoveryPlan } from './core/layoutRecovery';
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
import { nearestPortLayout } from './core/portRouting';
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
type Gesture = { type: 'move' | 'port-layout' | 'pan' | 'box'; pointerId: number; x: number; y: number; camera: Camera; pan?: CameraPan; ids: string[]; dx: number; dy: number; document?: CanvasDocument; preview?: MovePreviewSession; moveScope?: MoveScope; port?: ScenePort };
type MovePreview = { document: CanvasDocument; session: MovePreviewSession; dx: number; dy: number };
type RecoveryPreview = { document: CanvasDocument; plan: Extract<LayoutRecoveryPlan, { status: 'ready' }> };
const PALETTE = ['#dcebf6', '#deeee6', '#f4e6d0', '#ece3f4', '#f5dfe3', '#e8ecf0'];
const KEY = 'archcanvas.active-document.v1';
const ACTIVE = 'archcanvas.active-canvas.v2';
const REVIEW = 'archcanvas.source-review.v1';

function cameraViewIdentity(document: CanvasDocument): CameraViewIdentity {
  return { documentId: document.id, sourceBindingDigest: document.sourceBindingDigest,
    irDigest: document.architecture.irDigest, visualRevision: document.revision };
}
function cameraSessionStorage(): CameraViewStorage | null {
  try { return sessionStorage; } catch { return null; }
}

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
  const previewNodeBindings = useRef<{ source?: PreviewEvidenceSource; architecture: Architecture; signature: string; bindings: Map<string, string> } | null>(null);
  const previewCase = useRef('');
  const previewLoading = useRef(false);
  const [previewConnecting, setPreviewConnecting] = useState(true);
  const [previewBusy, setPreviewBusy] = useState(false);
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
  const [examples, setExamples] = useState<Example[]>([]);
  const [exampleId, setExampleId] = useState('');
  const [selection, setSelection] = useState<Selection>({ kind: 'node', ids: [] });
  const [camera, setCamera] = useState<Camera>({ x: 35, y: 35, zoom: 0.9 });
  const [tool, setTool] = useState<'select' | 'pan'>('select');
  const [previewTool, setPreviewTool] = useState<'select' | 'connect' | 'bend'>('select');
  const [portEditing, setPortEditing] = useState(false);
  const [portLayoutPreview, setPortLayoutPreview] = useState<{ base: CanvasDocument; document: CanvasDocument } | null>(null);
  const [layoutMoveScope, setLayoutMoveScope] = useState<MoveScope>('all-frontiers');
  const [isPanning, setIsPanning] = useState(false);
  const [preview, setPreview] = useState<MovePreview | null>(null);
  const [recoveryPreview, setRecoveryPreview] = useState<RecoveryPreview | null>(null);
  const [box, setBox] = useState<{ x: number; y: number; width: number; height: number } | null>(null);
  const [panel, setPanel] = useState<'object' | 'legend' | 'page'>('object');
  const [sourceOpen, setSourceOpen] = useState(false);
  useWorkspaceMenus();
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [treeSearch, setTreeSearch] = useState('');
  const [actionFeedback, setActionFeedback] = useState<{message: string; error?: boolean} | null>(null);
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
  const [inline, setInline] = useState<{ id: string; label: string } | null>(null);
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
  const [portDraft, setPortDraft] = useState<{ port: ScenePort; x: number; y: number; options: RebindOptions | null } | null>(null);
  const portRequest = useRef(0);
  const portGesture = useRef<{ request: number; document: CanvasDocument; pointerId: number; port: ScenePort; sequence: number; promise: Promise<RebindOptions> } | null>(null);
  const [connectionProposal, setConnectionProposal] = useState<{ nodeId: string; portId: string; candidate: RebindOptions['candidates'][number] | null; blockers: string[] } | null>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const gesture = useRef<Gesture | null>(null);
  const space = useRef(false);
  const inlineCancelled = useRef(false);
  const historyRef = useRef(history); historyRef.current = history;
  const cameraRef = useRef(camera); cameraRef.current = camera;
  const loadSequence = useRef(0);
  const saving = useRef(false);
  const frame = useRef(0);
  const cameraOwner = useRef<CameraViewIdentity | null>(null);
  const cameraIntent = useRef(0);
  const cameraInitializationFrame = useRef(0);
  const pendingCameraInitialization = useRef<{ ticket: CameraViewTicket; restore: boolean } | null>(null);
  // The size against which cameraRef's translation is defined. DOM dimensions
  // can change before an observer or terminal gesture has coordinated them.
  const cameraViewport = useRef<CameraViewport | null>(null);

  const current = history?.document;
  // The recursive iframe owns preview geometry and routing. Build the formal
  // scene only when an explicitly requested legacy inspection tool needs it.
  const needsFormalScene = !!recoveryPreview || !!portLayoutPreview || !!preview;
  const committedScene = useMemo(() => current && needsFormalScene ? buildScene(current, { presentation: 'editor' }) : null, [current, needsFormalScene]);
  const activeRecovery = recoveryPreview && recoveryPreview.document === current && selection.kind === 'node' && selection.ids.length === 1 && selection.ids[0] === recoveryPreview.plan.id ? recoveryPreview : null;
  const scene = useMemo(() => { const result = portLayoutPreview && portLayoutPreview.base === current ? buildScene(portLayoutPreview.document, { presentation: 'editor' }) : activeRecovery ? activeRecovery.plan.scene : preview && preview.document === current ? previewMoveScene(preview.session, preview.dx, preview.dy, { presentation: 'editor' }) : committedScene; return result ? presentEditorScene(result) : null; }, [current, committedScene, preview, activeRecovery, portLayoutPreview]);
  const implicitRoots = useMemo(() => scene ? implicitRootIds(scene) : new Set<string>(), [scene]);
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
  const selectedEdgeAppearance = selectedEdgePreview ? previewEdgeAppearance(previewSnapshot.current?.graph, selectedEdgePreview) : selectedEdge && current && scene ? edgeAppearance(current, selectedEdge.id, scene) : undefined;
  const selectedPreviewEdgeAppearance = selectedPreviewEdge ? previewEdgeAppearance(previewSnapshot.current?.graph, selectedPreviewEdge) : undefined;
  const selectedAnnotation = selection.kind === 'annotation' ? current?.annotations.find(n => n.id === selection.ids[0]) : undefined;
  const selectedSceneNode = scene?.nodes.find(n => n.id === selectedNode?.id);
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
  const selectedSceneAnnotation = scene?.annotations.find(n => n.id === selectedAnnotation?.id);
  const annotationConflicts = selectedAnnotation && previewSnapshot.current?.graph ? previewAnnotationConflicts(previewSnapshot.current.graph, selectedAnnotation.id) :
    scene && selectedSceneAnnotation ? findAnnotationBodyConflicts(scene, selectedSceneAnnotation) : [];
  const paperPosition = scene ? paperTranslation(camera, scene.bounds) : null;
  const dotGrid = canvasDotGrid(camera);
  const dirty = previewDirty || (!!current && current.revision !== savedVisualRevision);
  const layoutGuidance: string[] = [];
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
    const source = previewSource.current, signature = previewMappingSignature(snapshot), cached = previewNodeBindings.current;
    if (cached?.architecture === architecture && cached.source === source && cached.signature === signature) return cached.bindings;
    const bindings = previewUniqueNodeBindings(architecture, snapshot.graph as unknown as PreviewVisualGraph, source);
    previewNodeBindings.current = { architecture, source, signature, bindings };
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
      setExampleId(''); setPreviewConnecting(false);
      setNotice('原型视图与源码已打开；展示对象可独立编辑，进入编辑模式后按源码建立模型绑定。');
      return;
    }
    previewBoundSource.current = arch.sourceDigest + ':' + arch.irDigest;
    await openArchitecture(arch, true);
    if (sequence !== previewSequence.current || expectedCase !== previewCase.current) return;
    const before = historyRef.current;
    if (before && previewSnapshot.current) await receivePreviewState(previewSnapshot.current);
    setExampleId('');
    setPreviewConnecting(false);
    if (openEditor) await continueModelAuthoring();
  }
  function receivePreviewSelection(message: Record<string, unknown>) {
    if (message.caseId && message.caseId !== previewCase.current) return;
    synchronizePreviewNodeSelection(message.nodeIds ?? message.selectedNodes);
    if (typeof message.annotationId === 'string') {
      setSelection({ kind: 'annotation', ids: [message.annotationId] }); setPanel('object'); return;
    }
    const architecture = historyRef.current?.document.architecture;
    if (!architecture) return;
    const edge = message.edge as PreviewVisualEdge | undefined;
    const graph = graphFromSnapshot();
    if (edge && graph) {
      const raw = previewGraphEdges(previewSnapshot.current?.graph).find(item => item.id === edge.id);
      const ids = raw ? previewFormalEdgeIds(architecture, raw, previewSnapshot.current?.graph, previewSource.current, currentPreviewNodeBindings()) : [];
      setSelection(ids.length === 1 ? { kind: 'edge', ids } : { kind: 'preview-edge', ids: [edge.id] });
      setPanel('object'); return;
    }
    const selected = (message.nodeIds ?? message.selectedNodes) as string[] | undefined;
    const bindings = currentPreviewNodeBindings();
    const ids = selected?.length && graph ? [...new Set(selected.flatMap(id => bindings.has(id) ? [bindings.get(id)!] : []))] :
      typeof message.nodeId === 'string' && bindings.has(message.nodeId) ? [bindings.get(message.nodeId)!] : [];
    setSelection({ kind: 'node', ids }); setPanel('object');
  }
  async function receivePreviewState(snapshot: PreviewSnapshot) {
    previewSnapshot.current = snapshot;
    synchronizePreviewNodeSelection(snapshot.selectedNodes);
    if (snapshot.tool === 'select' || snapshot.tool === 'connect' || snapshot.tool === 'bend') setPreviewTool(snapshot.tool);
    if (typeof snapshot.showPorts === 'boolean') setPortEditing(snapshot.showPorts);
    if (typeof snapshot.gridVisible === 'boolean') setGrid(snapshot.gridVisible);
    setPreviewBusy(Boolean(snapshot.busy));
    const graph = snapshot.graph;
    const caseId = String(graph?.caseId ?? snapshot.caseId ?? '');
    setPreviewDirty(Boolean(snapshot.dirty) && JSON.stringify(graph) !== savedPreviewGraph.current);
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
      setSelection({ kind: 'node', ids: [] }); setExampleId(''); setProjectId(null);
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
      if (next !== before) { historyRef.current = next; setHistory(next); }
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

  useEffect(() => { document.querySelector('.inspector-content')?.scrollTo({ top: 0 }); }, [selection.ids[0], panel]);
  useEffect(() => { setRecoveryPreview(null); }, [selection]);

  function readCameraViewport() {
    return cameraViewportSize(viewportRef.current?.getBoundingClientRect());
  }
  function persistCamera(document = historyRef.current?.document, view = cameraRef.current) {
    if (gesture.current?.type === 'pan') return;
    const viewport = cameraViewport.current;
    if (!document || !viewport || !sameCameraViewDocument(cameraOwner.current, cameraViewIdentity(document))) return;
    writeCameraView(cameraSessionStorage(), cameraViewIdentity(document), view, viewport);
  }
  function claimCamera(document = historyRef.current?.document) {
    cancelAnimationFrame(cameraInitializationFrame.current); cameraInitializationFrame.current = 0;
    pendingCameraInitialization.current = null;
    cameraIntent.current++;
    cameraOwner.current = document ? cameraViewIdentity(document) : null;
  }
  function claimGestureCamera() {
    const document = historyRef.current?.document;
    if (!document || sameCameraViewDocument(cameraOwner.current, cameraViewIdentity(document))) return;
    // An early spatial gesture adopts the view actually under the pointer.
    // A delayed load restore must not move that mapping after its commit.
    claimCamera(document);
    cameraViewport.current = readCameraViewport();
    persistCamera(document);
  }
  const commitCamera = useCallback((view: Camera, document = historyRef.current?.document) => {
    if (!document) return;
    claimCamera(document);
    cameraViewport.current = readCameraViewport();
    cameraRef.current = view; setCamera(view);
    persistCamera(document, view);
  }, []);
  function synchronizeCameraViewport() {
    // Freeze the original pointer mapping until its final sample or rollback.
    if (gesture.current || portGesture.current) return;
    const document = historyRef.current?.document, viewport = readCameraViewport();
    if (!document || !viewport) return;
    if (!sameCameraViewDocument(cameraOwner.current, cameraViewIdentity(document))) {
      const pending = pendingCameraInitialization.current;
      if (pending && !canApplyCameraViewTicket(pending.ticket, cameraViewIdentity(document), loadSequence.current, cameraIntent.current)) {
        pendingCameraInitialization.current = null;
      } else if (pending && !cameraInitializationFrame.current && viewport.width > 96 && viewport.height > 92) {
        // A previously hidden/unmounted viewport can recover when it becomes
        // usable. Keep retries bounded while preserving the original intent.
        initializeCamera(document, pending.ticket.loadSequence, pending.restore);
      }
      return;
    }
    const previous = cameraViewport.current;
    if (!previous) { cameraViewport.current = viewport; return; }
    const view = resizeCameraViewport(cameraRef.current, previous, viewport);
    if (!view || view === cameraRef.current) return;
    cameraViewport.current = viewport;
    cameraRef.current = view; setCamera(view);
    persistCamera(document, view);
  }
  useLayoutEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    synchronizeCameraViewport();
    let active = true;
    const resized = () => {
      if (!active || viewport !== viewportRef.current) return;
      // ResizeObserver runs before paint. Commit the matching translation in
      // this delivery, rather than leaving one frame at the old viewport size.
      flushSync(() => synchronizeCameraViewport());
    };
    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(resized);
      observer.observe(viewport);
      return () => { active = false; observer.disconnect(); };
    }
    window.addEventListener('resize', resized);
    return () => { active = false; window.removeEventListener('resize', resized); };
  }, [authoringOpen]);
  useEffect(() => { persistCamera(); }, [current?.id, current?.revision, current?.sourceBindingDigest, current?.architecture.irDigest]);

  const cancelGesture = useCallback(() => {
    const active = gesture.current;
    const pointerId = active?.pointerId ?? portGesture.current?.pointerId;
    // Clear ownership before releasing capture: lostpointercapture is synchronous.
    gesture.current = null; portGesture.current = null; portRequest.current++;
    cancelAnimationFrame(frame.current); frame.current = 0;
    setPreview(null); setPortLayoutPreview(null); setRecoveryPreview(null); setBox(null); setPortDraft(null); setIsPanning(false);
    if (active?.type === 'pan') { cameraRef.current = active.camera; setCamera(active.camera); }
    synchronizeCameraViewport();
    if (active?.type === 'pan') persistCamera();
    const viewport = viewportRef.current;
    if (pointerId !== undefined && viewport?.hasPointerCapture(pointerId)) viewport.releasePointerCapture(pointerId);
  }, []);
  function chooseTool(next: 'select' | 'connect' | 'bend') {
    cancelGesture(); setTool('select'); setPreviewTool(next);
    previewEngine.current?.command(`${next}-tool`);
  }
  function chooseMoveScope(next: MoveScope) { cancelGesture(); setLayoutMoveScope(next); }
  useEffect(() => {
    const blur = () => { space.current = false; cancelGesture(); };
    window.addEventListener('blur', blur);
    return () => { window.removeEventListener('blur', blur); cancelAnimationFrame(frame.current); cancelAnimationFrame(cameraInitializationFrame.current); };
  }, [cancelGesture]);
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
  function optimizeAutomaticPorts(id: string) {
    const document = historyRef.current?.document;
    if (!document || !readyPreview(document)) return;
    const ports = buildScene(document, { presentation: 'editor' }).nodes.find(node => node.id === id)?.ports ?? [];
    const operations = ports.filter(port => port.layoutKey).map(port => {
      const [ownerId, nodeId, portId, role] = JSON.parse(port.layoutKey!) as [string, string, string, 'data' | 'residual' | 'memory' | 'mask'];
      return { type: 'portLayout' as const, ownerId, nodeId, portId, role, layout: null };
    });
    if (operations.length) apply(operations, '已恢复自动连接点');
  }
  const selectHierarchyNode = useCallback((id: string, additive = false) => {
    const graph = graphFromSnapshot();
    const detail = (previewSnapshot.current?.graph?.recursive as { authority?: { detail?: PreviewVisualGraph } } | undefined)?.authority?.detail ?? graph;
    const mapped = detail?.nodes.some(node => node.id === id && !node.junction) ? id : previewNodeId(id);
    if (!mapped) { setFailure('此源码对象没有唯一对应的画布图元；可直接在画布选择或查看源码。'); return; }
    setFailure('');
    setPanel('object');
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
  function setSemanticFrontier(preset: 'overview' | 'detail') {
    cancelGesture();
    if (!readyPreview()) { setFailure('预览正在接入当前源码，请完成后再切换语义前沿。'); return; }
    setFailure(''); setNotice(preset === 'overview' ? '正在切换到架构概览（F0）…' : '正在切换到架构详图（F1）…');
    previewEngine.current?.command('set-frontier', { preset });
  }
  function focusCurrentFrontier() {
    const id = previewSelectedNodeIds[0] ?? frontier?.expandedIds[frontier.expandedIds.length - 1];
    if (id) { previewEngine.current?.focus({ nodeId: id }); return; }
    fit();
  }
  const undo = useCallback(() => { cancelGesture(); previewEngine.current?.command('undo'); setActionFeedback(null); setNotice('已撤销一次画布操作'); }, [cancelGesture]);
  const redo = useCallback(() => { cancelGesture(); previewEngine.current?.command('redo'); setActionFeedback(null); setNotice('已重做一次画布操作'); }, [cancelGesture]);

  function previewPositionRecovery() {
    cancelGesture();
    const document = historyRef.current?.document;
    if (!document || selection.kind !== 'node' || selection.ids.length !== 1) return;
    try {
      const plan = planLayoutRecovery(document, selection.ids[0], layoutMoveScope, { presentation: 'editor' });
      if (plan.status !== 'ready') { setNotice(plan.reason); return; }
      setRecoveryPreview({ document, plan });
      setNotice('正在预览位置修复；应用后才会写入画布，可一次撤销。');
    } catch (error) { setFailure(String(error)); }
  }
  function applyPositionRecovery() {
    const value = activeRecovery;
    if (!value || value.document !== historyRef.current?.document) { cancelGesture(); return; }
    apply([value.plan.operation], '位置修复已应用；Ctrl+Z 可一次撤销。');
  }

  const initializeCamera = useCallback((document: CanvasDocument, sequence: number, restore = true) => {
    cancelAnimationFrame(cameraInitializationFrame.current);
    cameraOwner.current = null;
    const ticket = { identity: cameraViewIdentity(document), loadSequence: sequence, intentSequence: cameraIntent.current };
    const request = { ticket, restore }; pendingCameraInitialization.current = request;
    const schedule = (attempt: number) => {
      cameraInitializationFrame.current = requestAnimationFrame(() => {
        cameraInitializationFrame.current = 0;
        const active = historyRef.current?.document;
        // createHistory clones its input; the load/revision/identity ticket is
        // the ownership contract, not the raw loader object's reference.
        if (!active || !canApplyCameraViewTicket(ticket, cameraViewIdentity(active), loadSequence.current, cameraIntent.current)) {
          if (pendingCameraInitialization.current === request) pendingCameraInitialization.current = null;
          return;
        }
        if (gesture.current || portGesture.current) return;
        const rect = viewportRef.current?.getBoundingClientRect();
        if (!rect || rect.width <= 96 || rect.height <= 92) { if (attempt < 3) schedule(attempt + 1); return; }
        const viewport = { width: rect.width, height: rect.height };
        const recovered = restore ? readCameraView(cameraSessionStorage(), ticket.identity, viewport) : null;
        const view = recovered ?? fitCameraToBounds(editorSceneBounds(buildScene(active, { presentation: 'editor' })), viewport);
        pendingCameraInitialization.current = null;
        cameraOwner.current = ticket.identity; cameraViewport.current = viewport;
        cameraRef.current = view; setCamera(view);
        persistCamera(active, view);
      });
    };
    schedule(0);
  }, []);

  const fit = useCallback((documentToFit?: CanvasDocument) => {
    cancelGesture();
    previewEngine.current?.command('fit');
    if (!documentToFit && previewSnapshot.current?.graph) return;
    const doc = documentToFit ?? historyRef.current?.document;
    if (!doc || !viewportRef.current) return;
    const interaction = studioTelemetry.beginInteraction('fit-canvas');
    try {
      const bounds = editorSceneBounds(buildScene(doc, { presentation: 'editor' }));
      const { width, height } = viewportRef.current.getBoundingClientRect();
      if (width <= 96 || height <= 92) return;
      commitCamera(fitCameraToBounds(bounds, { width, height }), doc);
    } finally { studioTelemetry.endInteraction(interaction); }
  }, [cancelGesture, commitCamera]);

  const openArchitecture = useCallback(async (arch: Architecture, restore = true, requestSequence?: number, initializeView = true) => {
    const sequence = requestSequence ?? ++loadSequence.current;
    if (sequence !== loadSequence.current) return;
    cameraOwner.current = null; cameraIntent.current++;
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
    setSelection({ kind: 'node', ids: [] }); setPreview(null); setSourceOpen(false);
    setNotice(saved >= 0 ? '已重开保存的画布' : '静态源码已导入；模型未被执行'); setFailure('');
    if (initializeView) initializeCamera(document, sequence, restore);
  }, [initializeCamera]);

  const loadExample = useCallback(async (id: string) => {
    cancelGesture();
    const sequence = ++loadSequence.current;
    cameraOwner.current = null; cameraIntent.current++;
    setBusy(true); setFailure('');
    try { const arch = await api.example(id); if (sequence !== loadSequence.current) return; setExampleId(id); await openArchitecture(arch, true, sequence); }
    catch (error) { if (sequence === loadSequence.current) setFailure(String(error)); }
    finally { if (sequence === loadSequence.current) { setBusy(false); setRuntimeCancel(null); setCancelling(false); } }
  }, [openArchitecture, cancelGesture]);

  useEffect(() => {
    let alive = true;
    const sequence = ++loadSequence.current;
    cameraOwner.current = null; cameraIntent.current++;
    api.capabilities().then(result => { if (alive) setCapabilities(result); }).catch(() => {});
    api.examples().then(async items => {
      if (!alive || sequence !== loadSequence.current) return;
      setExamples(items);
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
          setProjectId(stored.projectId ?? null); setExampleId(''); setReview(null);
          setNotice('已打开指定模型画布'); setFailure(''); initializeCamera(stored.document, sequence);
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
          setNotice(active.projectId ? '已重开工作副本及保存的画布' : '已重开保存的画布'); initializeCamera(doc, sequence);
          if (restored) { initialModelLoading.current = false; await receivePreviewState(restored); }
          const pending = JSON.parse(localStorage.getItem(REVIEW) ?? 'null') as { projectId: string; id: string } | null;
          if (pending && pending.projectId === active.projectId) {
            const transaction = await api.transaction(pending.projectId, pending.id);
            if (alive && transaction.status !== 'Discarded') setReview({ transaction, base: doc, projectId: pending.projectId });
          }
          return;
        }
      } catch { /* A missing stored snapshot falls back to an analyzed example. */ }
      if (!alive || sequence !== loadSequence.current) return;
      const prior = localStorage.getItem(KEY);
      await loadExample(items.find(x => x.id === prior)?.id ?? items[0]?.id ?? 'transformer');
    }).catch(error => { if (alive) { setFailure(`Runtime 未连接：${String(error)}`); setNotice('请按 README 启动正式服务'); } }).finally(() => { if (alive) initialModelLoading.current = false; });
    return () => { alive = false; };
  }, [loadExample, initializeCamera]);
  useEffect(() => {
    if (!current || authoringOpen || busy || exportDocument || review || activeRecovery) return;
    let alive = true, inFlight = false;
    const synchronize = async () => {
      if (inFlight || gesture.current || saving.current || openingExport.current || previewLoading.current) return;
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
  }, [current?.id, authoringOpen, busy, exportDocument, review, activeRecovery, storageRevision, savedVisualRevision]);
  useEffect(() => { if (exampleId) localStorage.setItem(KEY, exampleId); }, [exampleId]);
  useEffect(() => { if (current) localStorage.setItem(ACTIVE, JSON.stringify({ documentId: current.id, projectId, previewCaseId: previewCase.current })); }, [current?.id, projectId, previewCase.current]);

  function updateDocumentUrl(documentId: string) {
    const url = new URL(window.location.href);
    url.searchParams.set('documentId', documentId);
    window.history.replaceState(window.history.state, '', url);
  }

  const save = useCallback(async () => {
    if (activeRecovery) { setNotice('请先应用或取消位置修复预览，再保存画布。'); return; }
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
  }, [storageRevision, activeRecovery]);

  useEffect(() => {
    const down = (event: KeyboardEvent) => {
      if (event.defaultPrevented || authoringOpen || editingTarget(event.target) || review || exportDocument || connectionProposal || runtimeOpen || importOpen) return;
      if (event.code === 'Space') { space.current = true; event.preventDefault(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); event.shiftKey ? redo() : undo(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'y') { event.preventDefault(); redo(); }
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); previewEngine.current?.command('apply-layout'); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); void save(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a') { event.preventDefault(); previewEngine.current?.command('select-nodes', {scope:'all'}); }
      if (event.key === 'Escape') { cancelGesture(); previewEngine.current?.command('select-nodes', {scope:'clear'}); setSelection({ kind: 'node', ids: [] }); setInline(null); }
      if (!event.ctrlKey && !event.metaKey && !event.altKey) {
        if (event.key.toLowerCase() === 'f') fit();
        if (event.key.toLowerCase() === 'v') chooseTool('select');
        if (event.key.toLowerCase() === 'c') chooseTool('connect');
        if (event.key.toLowerCase() === 'b') chooseTool('bend');
      }
    };
    const up = (event: KeyboardEvent) => { if (event.code === 'Space') space.current = false; };
    window.addEventListener('keydown', down); window.addEventListener('keyup', up);
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); };
  }, [fit, redo, save, undo, review, exportDocument, connectionProposal, runtimeOpen, importOpen, cancelGesture, authoringOpen]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const wheel = (event: WheelEvent) => {
      if (editingTarget(event.target)) return;
      event.preventDefault();
      if (gesture.current || portGesture.current) return;
      synchronizeCameraViewport();
      const rect = viewport.getBoundingClientRect();
      const px = event.clientX - rect.left, py = event.clientY - rect.top;
      const old = cameraRef.current, zoom = clampCanvasZoom(old.zoom * Math.exp(-Math.max(-2000, Math.min(2000, event.deltaY)) * 0.0015));
      commitCamera({ x: px - (px - old.x) * zoom / old.zoom, y: py - (py - old.y) * zoom / old.zoom, zoom });
    };
    viewport.addEventListener('wheel', wheel, { passive: false });
    return () => viewport.removeEventListener('wheel', wheel);
  }, [authoringOpen, commitCamera]);

  function panInput(event: React.PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return { pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY, viewportX: rect.left, viewportY: rect.top };
  }
  function pointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (activeRecovery) { cancelGesture(); return; }
    if (editingTarget(event.target) || !scene || gesture.current || portGesture.current) return;
    synchronizeCameraViewport();
    portRequest.current++;
    const input = panInput(event);
    const x = input.clientX - input.viewportX, y = input.clientY - input.viewportY;
    const view = cameraRef.current;
    // Navigation takes priority even over expand handles and input ports.
    if (event.button === 1 || (event.button === 0 && (tool === 'pan' || space.current))) {
      claimCamera();
      cameraViewport.current = readCameraViewport();
      gesture.current = { type: 'pan', pointerId: event.pointerId, x, y, camera: view, pan: beginCameraPan(view, input), ids: [], dx: 0, dy: 0 };
      setIsPanning(true); event.currentTarget.setPointerCapture(event.pointerId); event.preventDefault(); return;
    }
    if (event.button !== 0) return;
    const target = event.target as Element;
    const portId = target.closest('[data-port-id]')?.getAttribute('data-port-id');
    const port = scene.nodes.flatMap(node => node.ports).find(p => p.id === portId);
    if (port && portEditing && !busy && current && port.layoutKey) {
      claimGestureCamera();
      const [ownerId] = JSON.parse(port.layoutKey) as string[];
      setSelection({ kind: 'node', ids: [ownerId] });
      gesture.current = { type: 'port-layout', pointerId: event.pointerId, x, y, camera: view, ids: [ownerId], dx: 0, dy: 0, document: current, port };
      event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId); return;
    }
    if (port?.direction === 'in' && !busy && current) {
      event.preventDefault();
      if (port.proxy || !inputSpec) {
        setConnectionProposal({ nodeId: port.canonicalNodeId, portId: port.canonicalPortId, candidate: null, blockers: [!inputSpec ? '先设置运行输入与模式，再检查可用来源。' : '这是折叠层级的投影端口；请展开至准确调用端口。'] });
        return;
      }
      const sequence = loadSequence.current;
      const promise = inspectRebind(port.canonicalNodeId, port.canonicalPortId);
      claimGestureCamera();
      portGesture.current = { request: portRequest.current, document: current, pointerId: event.pointerId, port, sequence, promise };
      setPortDraft({ port, x: port.x, y: port.y, options: null });
      void promise.then(options => { if (portGesture.current?.promise === promise) setPortDraft(draft => draft && ({ ...draft, options })); }).catch(() => {});
      event.currentTarget.setPointerCapture(event.pointerId); return;
    }
    const expandId = target.closest('[data-expand-id]')?.getAttribute('data-expand-id');
    if (expandId) { const n = scene.nodes.find(x => x.id === expandId); if (n) apply([{ type: 'expand', id: expandId, expanded: !n.expanded }], n.expanded ? '已原位收起' : '已原位展开，保留画布位置'); return; }
    const nodeId = target.closest('[data-node-id]')?.getAttribute('data-node-id');
    const edgeId = target.closest('[data-edge-id]')?.getAttribute('data-edge-id');
    const legendId = target.closest('[data-legend-id]')?.getAttribute('data-legend-id');
    const annotationId = target.closest('[data-annotation-id]')?.getAttribute('data-annotation-id');
    if (nodeId) {
      const ids = event.shiftKey ? selection.ids.includes(nodeId) ? selection.ids.filter(id => id !== nodeId) : [...(selection.kind === 'node' ? selection.ids : []), nodeId] : selection.kind === 'node' && selection.ids.includes(nodeId) ? selection.ids : [nodeId];
      setSelection({ kind: 'node', ids }); setPanel('object');
      if (!current) return;
      try {
        claimGestureCamera();
        gesture.current = { type: 'move', pointerId: event.pointerId, x, y, camera: view, ids, dx: 0, dy: 0, document: current, preview: prepareMovePreview(current, ids, layoutMoveScope), moveScope: layoutMoveScope };
      } catch (error) { setFailure(String(error)); return; }
    } else if (edgeId) { setSelection({ kind: 'edge', ids: [edgeId] }); setPanel('object'); return; }
    else if (legendId) { setSelection({ kind: 'legend', ids: [legendId] }); setPanel('legend'); return; }
    else if (annotationId) { setSelection({ kind: 'annotation', ids: [annotationId] }); setPanel('object'); return; }
    else {
      if (!event.shiftKey) setSelection({ kind: 'node', ids: [] });
      claimGestureCamera();
      gesture.current = { type: 'box', pointerId: event.pointerId, x, y, camera: view, ids: event.shiftKey ? selection.ids : [], dx: 0, dy: 0 };
    }
    event.currentTarget.setPointerCapture(event.pointerId); event.preventDefault();
  }
  function pointerMove(event: React.PointerEvent<HTMLDivElement>) {
    if (portGesture.current?.pointerId === event.pointerId && scene) {
      const input = panInput(event), view = cameraRef.current;
      const point = viewportToWorld(view, { x: input.clientX - input.viewportX, y: input.clientY - input.viewportY });
      setPortDraft(draft => draft && ({ ...draft, ...point }));
      return;
    }
    const active = gesture.current; if (!active || active.pointerId !== event.pointerId) return;
    const input = panInput(event);
    active.dx = input.clientX - input.viewportX - active.x; active.dy = input.clientY - input.viewportY - active.y;
    const panCamera = active.pan ? cameraAtPanInput(active.pan, input) : null;
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      if (gesture.current !== active) return;
      frame.current = 0;
      if (panCamera) { cameraRef.current = panCamera; setCamera(panCamera); }
      else if (active.type === 'move') {
        if (historyRef.current?.document !== active.document || !active.preview || !active.document) { cancelGesture(); return; }
        const dx = Math.round(active.dx / active.camera.zoom / 4) * 4, dy = Math.round(active.dy / active.camera.zoom / 4) * 4;
        const document = active.document, session = active.preview;
        setPreview(previous => previous && previous.session === session && previous.dx === dx && previous.dy === dy ? previous : { document, session, dx, dy });
      }
      else if (active.type === 'port-layout' && active.document) {
        const operation = portLayoutOperation(active, { x: active.x + active.dx, y: active.y + active.dy });
        if (operation) setPortLayoutPreview({ base: active.document, document: applyVisualBatch(active.document, [operation]) });
      }
      else setBox({ x: Math.min(active.x, active.x + active.dx), y: Math.min(active.y, active.y + active.dy), width: Math.abs(active.dx), height: Math.abs(active.dy) });
    });
  }
  function pointerUp(event: React.PointerEvent<HTMLDivElement>) {
    const connecting = portGesture.current;
    if (connecting) {
      if (connecting.pointerId !== event.pointerId || !scene) return;
      portGesture.current = null; setPortDraft(null);
      if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
      const input = panInput(event), view = cameraRef.current;
      const { x, y } = viewportToWorld(view, { x: input.clientX - input.viewportX, y: input.clientY - input.viewportY });
      void connecting.promise.then(options => {
        if (connecting.sequence !== loadSequence.current || connecting.request !== portRequest.current || connecting.document !== historyRef.current?.document) return;
        const producer = candidatePorts(options).find(p => Math.hypot(p.x - x, p.y - y) < 14 / view.zoom);
        const candidate = options.candidates.find(c => c.binding.nodeId === producer?.canonicalNodeId && c.binding.portId === producer?.canonicalPortId) ?? null;
        setConnectionProposal({ nodeId: connecting.port.canonicalNodeId, portId: connecting.port.canonicalPortId, candidate, blockers: candidate ? [] : options.blockers.length ? options.blockers : ['拖线终点不是已证明可用的来源输出端口；原连接保持不变。'] });
      }).catch(error => { if (connecting.sequence === loadSequence.current && connecting.request === portRequest.current && connecting.document === historyRef.current?.document) setConnectionProposal({ nodeId: connecting.port.canonicalNodeId, portId: connecting.port.canonicalPortId, candidate: null, blockers: [String(error)] }); });
      synchronizeCameraViewport();
      return;
    }
    const active = gesture.current; if (!active || active.pointerId !== event.pointerId) return;
    const input = panInput(event);
    active.dx = input.clientX - input.viewportX - active.x; active.dy = input.clientY - input.viewportY - active.y;
    cancelAnimationFrame(frame.current); frame.current = 0;
    gesture.current = null; setPreview(null); setPortLayoutPreview(null); setBox(null); setIsPanning(false);
    if (active.pan) {
      const finalCamera = cameraAtPanInput(active.pan, input);
      if (finalCamera) {
        cameraRef.current = finalCamera; setCamera(finalCamera);
        synchronizeCameraViewport();
        commitCamera(cameraRef.current);
      }
    }
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (active.type === 'move' && historyRef.current?.document === active.document && Math.hypot(active.dx, active.dy) > 3) apply([{ type: 'move', ids: active.ids, dx: Math.round(active.dx / active.camera.zoom / 4) * 4, dy: Math.round(active.dy / active.camera.zoom / 4) * 4, ...(active.moveScope === undefined ? {} : { scope: active.moveScope }) }], '位置已调整；一次拖动对应一次撤销');
    if (active.type === 'port-layout' && historyRef.current?.document === active.document && Math.hypot(active.dx, active.dy) > 3) {
      const operation = portLayoutOperation(active, { x: active.x + active.dx, y: active.y + active.dy });
      if (operation) apply([operation], '连接点已调整；自动走线已更新');
    }
    if (active.type === 'box' && scene && Math.hypot(active.dx, active.dy) > 4) {
      const { x, y } = viewportToWorld(active.camera, { x: Math.min(active.x, active.x + active.dx), y: Math.min(active.y, active.y + active.dy) });
      const right = x + Math.abs(active.dx) / active.camera.zoom, bottom = y + Math.abs(active.dy) / active.camera.zoom;
      const ids = scene.nodes.filter(n => !implicitRoots.has(n.id) && n.x >= x && n.y >= y && n.x + n.width <= right && n.y + n.height <= bottom).map(n => n.id);
      setSelection({ kind: 'node', ids: [...new Set([...active.ids, ...ids])] });
    }
    synchronizeCameraViewport();
  }
  function pointerCancelled(event: React.PointerEvent<HTMLDivElement>) {
    if (gesture.current?.pointerId === event.pointerId || portGesture.current?.pointerId === event.pointerId) cancelGesture();
  }
  function portLayoutOperation(active: Gesture, viewportPoint: { x: number; y: number }): VisualOperation | null {
    const node = committedScene?.nodes.find(node => node.id === active.ids[0]);
    if (!node || !active.port?.layoutKey) return null;
    const [ownerId, nodeId, portId, role] = JSON.parse(active.port.layoutKey) as [string, string, string, 'data' | 'residual' | 'memory' | 'mask'];
    return { type: 'portLayout', ownerId, nodeId, portId, role, layout: nearestPortLayout(node, viewportToWorld(active.camera, viewportPoint)) };
  }

  function candidatePorts(options: RebindOptions | null) {
    return (options?.candidates ?? []).flatMap(candidate => {
      const node = scene?.nodes.find(n => n.id === candidate.binding.nodeId && !n.expanded);
      if (!node) return [];
      const port = node.ports.find(p => p.direction === 'out' && p.canonicalPortId === candidate.binding.portId);
      return [{ id: `${candidate.binding.nodeId}:${candidate.binding.portId}`, canonicalNodeId: candidate.binding.nodeId, canonicalPortId: candidate.binding.portId, x: port?.x ?? node.x + node.width / 2, y: port?.y ?? node.y + node.height }];
    });
  }

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
      claimCamera(next.document); persistCamera(next.document);
      setNotice(`工作副本已提交；保留 ${reconciled.preservedNodeIds.length} 个对象的视觉编辑。源码变更不属于画布撤销。`);
      setExampleId(''); localStorage.removeItem(REVIEW);
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
      setExampleId(''); setImportOpen(false);
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
    setExampleId(''); setImportOpen(false);
  }
  function focusNode(id: string) {
    cancelGesture();
    focusPreviewNode(id);
    setSelection({ kind: 'node', ids: [id] }); setPanel('object');
    const node = scene?.nodes.find(n => n.id === id);
    if (!node || !viewportRef.current || !scene) return;
    const { width, height } = viewportRef.current.getBoundingClientRect();
    commitCamera(focusCameraOnPoint(cameraRef.current, { x: node.x + node.width / 2, y: node.y + node.height / 2 }, { width, height }));
  }

  function focusAnnotation(id: string) {
    cancelGesture();
    previewEngine.current?.focus({ annotationId: id });
    if (previewSnapshot.current?.graph) return;
    const document = historyRef.current?.document, viewport = viewportRef.current;
    if (!document || !viewport) return;
    const updated = buildScene(document), annotation = updated.annotations.find(item => item.id === id);
    if (!annotation) return;
    const { width, height } = viewport.getBoundingClientRect();
    commitCamera(focusCameraOnPoint(cameraRef.current, { x: annotation.x + annotation.width / 2, y: annotation.y + annotation.height / 2 }, { width, height }));
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
    apply([{ type: 'annotation', annotation: { id, text: '双击模块展开或收起；显示名在右侧对象面板编辑。', x, y, width } }]);
    setSelection({ kind: 'annotation', ids: [id] }); setPanel('object'); focusAnnotation(id);
  }
  function moveAnnotationBelow() {
    if (!selectedAnnotation) return;
    const graph = previewSnapshot.current?.graph;
    if (!graph && !scene) return;
    const position = graph ? previewAnnotationPosition(graph, selectedAnnotation.id) : suggestAnnotationPosition(scene!, selectedAnnotation.id);
    if (position.x !== selectedAnnotation.x || position.y !== selectedAnnotation.y) apply([{ type: 'annotation', annotation: { ...selectedAnnotation, ...position } }], '说明已移到图下方；可撤销恢复原位置');
    focusAnnotation(selectedAnnotation.id);
  }
  function zoomCamera(factor: number | 'reset') {
    cancelGesture();
    previewEngine.current?.command('zoom', { factor });
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return;
    const old = cameraRef.current;
    commitCamera(zoomCameraAtPoint(old, factor === 'reset' ? 1 : clampCanvasZoom(old.zoom * factor), { x: rect.width / 2, y: rect.height / 2 }));
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
    if (!frozen || busy || activeRecovery) return;
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
    if (enteringAuthoring.current || busy || activeRecovery || !historyRef.current) return;
    if (!readyPreview()) { setFailure('预览正在接入当前源码，请完成后再进入模型编辑。'); return; }
    enteringAuthoring.current = true;
    const sequence = loadSequence.current;
    try {
      const snapshot = await previewEngine.current?.snapshot();
      if (sequence !== loadSequence.current) return;
      if (snapshot) await receivePreviewState(snapshot);
      if (sequence !== loadSequence.current) return;
      if (snapshot?.graph?.generic) {
        const edited = await previewEngine.current!.author({ action: 'begin' });
        await receivePreviewState(edited); setSummaryEditorId(String(edited.caseId)); setPanel('object'); setFailure('');
      } else await continueModelAuthoring();
    } catch (error) { setFailure(`无法同步当前预览，画布与编辑副本均已保留：${String(error)}`); }
    finally { enteringAuthoring.current = false; }
  }
  async function newSummaryModel() {
    if (busy || previewBusy || review || activeRecovery) return;
    try {
      const snapshot = await previewEngine.current!.author({ action: 'begin', blank: true });
      await receivePreviewState(snapshot); setSummaryEditorId(String(snapshot.caseId)); setPanel('object'); setFailure('');
    } catch (error) { setFailure(String(error)); }
  }
  async function editSummary(operation: Record<string, unknown>) {
    const snapshot = await previewEngine.current!.author(operation);
    await receivePreviewState(snapshot);
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
    if (openingExport.current || !readyPreview() || busy || activeRecovery) return;
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
    cameraOwner.current = null; cameraIntent.current++;
    historyRef.current = next; setHistory(next);
    setStorageRevision(saved.revision); setSavedVisualRevision(document.revision);
    setReview(null); localStorage.removeItem(REVIEW); setPreview(null); setSourceOpen(false);
    setSelection({ kind: 'node', ids: (workspace?.selection ?? []).flatMap(id => retained.nodeBindings[id] ? [retained.nodeBindings[id]] : []) });
    setProjectId(opened.projectId); setExampleId(''); setAuthoringOpen(false);
    updateDocumentUrl(document.id);
    if (workspace?.camera && !workspace.draft.sourceProvenance?.viewCanvas) { commitCamera(workspace.camera, document); setTool(workspace.tool ?? 'select'); }
    else initializeCamera(document, sequence, false);
    setNotice(`已打开新模型工作副本。${retained.hierarchyReflowed ? '新源码层级已重新排布，原草稿布局保留。' : '已保留搭建位置与视角。'}模型未执行。${retained.unmappedNodeIds.length ? ` ${retained.unmappedNodeIds.length} 个展示框没有对应的新源码节点。` : ''}${retained.unresolvedEdgeStyles.length ? ` ${retained.unresolvedEdgeStyles.length} 条连线样式待核对。` : ''}`);
  }
  async function openSourceEditedModel(architecture: Architecture) {
    cancelGesture();
    const sequence = ++loadSequence.current;
    const opened = await api.open(architecture);
    if (sequence !== loadSequence.current) return;
    await openArchitecture(architecture, true, sequence);
    if (sequence !== loadSequence.current) return;
    setProjectId(opened.projectId); setExampleId(''); setAuthoringOpen(false);
    updateDocumentUrl(opened.documentId);
    setNotice('已打开源码修改后的独立模型，并重新建立已解析的模型层级；原草稿与原始项目保留。模型未执行。');
  }
  const authoringView = authoringOpen ? <AuthoringStudio key={authoringSessionKey.current} initialWorkspace={authoringWorkspace} browseBaseline={browseBaseline}
    onViewState={retainAuthoringWorkspace} onClose={() => setAuthoringOpen(false)} onOpen={openGeneratedModel}
    onSourceOpen={openSourceEditedModel}
    onNewBlank={workspace => { retainAuthoringWorkspace(workspace); openBlankAuthoring(); }}
    onReuseView={async workspace => {
      retainAuthoringWorkspace(workspace);
      if (!browseBaseline) throw new Error('缺少原视图绑定。');
      if (!sameGeneratedDraft(workspace.draft, browseBaseline)) {
        if (!sameSourceSemantics(workspace.draft, browseBaseline) || !historyRef.current) throw new Error('编辑内容已变化，需要重新生成视图。');
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
      <div className="brand"><span className="brand-mark"><i /><i /><i /></span><span>ArchCanvas<small>模型架构工作台</small></span></div>
      <div className="project-breadcrumb"><span className="slash">/</span><Icon name="file" size={15} /><span>{current?.title ?? '模型工作台'}</span></div>
      <div className="header-actions"><details className="workspace-menu"><summary>模型 <span>⌄</span></summary><div><button disabled={busy || !!review || !!activeRecovery} onClick={() => void newSummaryModel()}><Icon name="plus" size={15} />新建空白模型</button><button disabled={busy || !!review || !!activeRecovery} onClick={openBlankAuthoring}>新建正式源码模型</button><button disabled={!current || busy || previewBusy || previewConnecting} onClick={() => void formalSourceEditor()}>正式源码工作副本</button><button disabled={busy || !!review} onClick={() => { setFailure(''); setImportOpen(true); }}><Icon name="file" size={15} />导入 Python 源码</button><button disabled={!current} onClick={() => setSourceOpen(true)}><Icon name="code" size={15} />查看源码</button><label className="menu-field">内置示例<select aria-label="示例模型" value={exampleId} onChange={e => void loadExample(e.target.value)} disabled={busy}><option value="" disabled>选择示例</option>{examples.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}</select></label><button onClick={() => previewEngine.current?.command("show-library")}><Icon name="layers" size={15} />示例与模块库</button><button onClick={() => previewEngine.current?.command("show-evidence")}><Icon name="info" size={15} />原型来源与审查记录</button></div></details><WorkspaceModeSwitch mode={summaryEditing ? "edit" : "view"} disabled={!current || busy || previewConnecting || previewBusy || !!review || !!activeRecovery} onView={() => setSummaryEditorId(null)} onEdit={() => void editCurrentPreview()} /><span className={`save-state ${dirty ? 'dirty' : ''}`}><i />{current ? dirty ? '有未保存编辑' : '已保存' : '等待文档'}</span><button onClick={save} disabled={!current || busy || previewConnecting || previewBusy || !!activeRecovery}><Icon name="save" size={15} />保存</button><button className="primary" onClick={() => void openPreviewExport()} disabled={!current || busy || previewConnecting || previewBusy || !!activeRecovery}><Icon name="export" size={16} />导出</button></div>
    </header>
    <div className={`workspace ${leftCollapsed ? 'left-collapsed' : ''} ${rightCollapsed ? 'right-collapsed' : ''}`}>
      <aside className="navigator">
        <div className="navigator-top"><div className="panel-title"><Icon name="layers" size={16} /><b>模型层级</b><span>{navigation?.nodes.length ?? architecture?.nodes.length ?? 0}</span></div><label className="tree-search"><Icon name="search" size={14} /><input aria-label="搜索模型层级" placeholder="搜索模块…" value={treeSearch} onChange={e => setTreeSearch(e.target.value)} />{treeSearch && <button className="tool" aria-label="清除层级搜索" onClick={() => setTreeSearch('')}><Icon name="close" size={12} /></button>}</label></div>
        <div className="tree" role="tree" aria-label="模型层级" aria-multiselectable="true">
          {architecture && current && <HierarchyTree architecture={navigation ?? architecture} document={navigation ?? current} mandatoryIds={navigation?.mandatoryIds} selected={navigation ? previewSelectedNodeIds : selection.ids} onSelect={selectHierarchyNode} onExpand={expandHierarchyNode} query={treeSearch} />}
        </div>
        <div className="navigator-bottom"><button className={sourceOpen ? 'active' : ''} onClick={() => setSourceOpen(x => !x)} disabled={!current}><Icon name="code" size={16} />查看源码证据<Icon name="chevron" size={13} /></button><div className="source-note"><span className="live-dot" />{previewSnapshot.current?.importedDocument ? '导入文档证据' : '静态源码视图'}</div></div>
      </aside>
      <main className="main">
        <div className="workspace-caption"><button className="tool" aria-label={leftCollapsed ? '展开模型层级面板' : '收起模型层级面板'} aria-pressed={!leftCollapsed} onClick={() => setLeftCollapsed(value => !value)} title="模型层级面板"><Icon name="panelLeft" size={16} /></button><b>{current?.title ?? '模型工作台'}</b><span>{summaryEditing ? "Summary 编辑副本" : "预览"}</span><button className="tool" aria-label={rightCollapsed ? '展开属性面板' : '收起属性面板'} aria-pressed={!rightCollapsed} onClick={() => setRightCollapsed(value => !value)} title="属性面板"><Icon name="panelRight" size={16} /></button></div>
        <div className="canvas-toolbar" role="toolbar" aria-label="画布编辑工具">
          <div className="tool-group">
            <button className={`tool ${previewTool === 'select' ? 'selected' : ''}`} title="选择 · 单击选中；Ctrl / Shift / ⌘ 点击增减选区；拖动空白框选 · V" aria-label="选择对象" aria-pressed={previewTool === 'select'} disabled={previewLayoutDisabled} onClick={() => chooseTool('select')}><Icon name="arrow" /></button>
            <details className="selection-menu"><summary aria-label="选区操作" title="选区操作"><Icon name="chevron" size={13} /></summary><div><div className="menu-heading">{previewSelectedNodes.length ? `已选 ${previewSelectedNodes.length} 个节点` : '选择对象'}</div><p className="menu-help">单击选择；Ctrl / Shift / ⌘ 点击增减选区，拖动空白处框选。</p><button disabled={previewLayoutDisabled || !previewSelectedNodes.length} onClick={() => previewEngine.current?.command('select-nodes', { scope: 'siblings' })}>选择同级节点</button><button disabled={previewLayoutDisabled} onClick={() => previewEngine.current?.command('select-nodes', { scope: 'all' })}>选择全部可见模块 <kbd>Ctrl A</kbd></button><button disabled={previewLayoutDisabled || !previewSelectedNodes.length} onClick={() => previewEngine.current?.command('select-nodes', { scope: 'clear' })}>清空选区 <kbd>Esc</kbd></button></div></details>
            {([{ id: 'connect', icon: 'connect', label: '创建连接', hint: '创建视觉草稿连接 · C' }, { id: 'bend', icon: 'bend', label: '编辑折点', hint: '选择连线，添加或拖动折点 · B' }] as const).map(item => <button key={item.id} title={item.hint} aria-label={item.label} aria-pressed={previewTool === item.id} className={`tool ${previewTool === item.id ? 'selected' : ''}`} disabled={!current || busy || previewConnecting || previewBusy} onClick={() => chooseTool(item.id)}><Icon name={item.icon} /></button>)}
            <button className={`tool ${portEditing ? 'selected' : ''}`} title="显示节点端口；选中连线后可拖动 S / T 端点" aria-label="显示连接点" aria-pressed={portEditing} disabled={!current || busy || previewConnecting || previewBusy} onClick={() => { cancelGesture(); previewEngine.current?.command('show-ports', { visible: !portEditing }); }}><Icon name="ports" /></button>
            <span className="tool-divider" />
            <button className="tool" onClick={undo} disabled={!previewUndo || busy || previewConnecting || previewBusy} title="撤销 Ctrl+Z" aria-label="撤销画布编辑"><Icon name="undo" /></button>
            <button className="tool" onClick={redo} disabled={!previewRedo || busy || previewConnecting || previewBusy} title="重做 Ctrl+Shift+Z" aria-label="重做画布编辑"><Icon name="redo" /></button>

            <span className="tool-divider" />
            <button className="tool" aria-label="左对齐所选节点" onClick={() => arrangePreview('left')} disabled={previewLayoutDisabled || !previewCanAlign} title="左对齐 · 选择同一容器内的两个以上节点"><Icon name="align" /></button>
            <details className="alignment-menu"><summary title="更多对齐与分布" aria-label="更多对齐与分布"><Icon name="chevron" size={13} /></summary><div><div className="menu-heading">对齐与分布</div><p className="menu-help">选择同级节点；至少 2 个对齐、3 个分布。</p>
              {([{ kind: 'left', label: '左对齐' }, { kind: 'hcenter', label: '水平居中对齐' }, { kind: 'right', label: '右对齐' }, { kind: 'top', label: '顶部对齐' }, { kind: 'vcenter', label: '垂直居中对齐' }, { kind: 'bottom', label: '底部对齐' }, { kind: 'distribute-x', label: '水平等距分布' }, { kind: 'distribute-y', label: '垂直等距分布' }]).map(item => <button key={item.kind} disabled={previewLayoutDisabled || !previewCanAlign || (item.kind.startsWith('distribute') && (previewSelectedNodes.length < 3 || previewPinnedCount > 0))} onClick={event => { arrangePreview(item.kind); event.currentTarget.closest('details')?.removeAttribute('open'); }}>{item.label}</button>)}
            </div></details>
            <button className={`tool ${previewAllPinned ? 'selected' : ''}`} aria-label={previewAllPinned ? '解锁所选节点' : '固定所选节点'} aria-pressed={previewAllPinned} onClick={pinPreviewSelection} disabled={previewLayoutDisabled || !previewSelectedNodes.length} title={previewAllPinned ? '解锁所选节点，恢复直接拖动' : '固定所选节点的直接拖动；子图仍随父容器移动'}><Icon name="pin" /></button>
          </div>
          <button className="layout-apply" aria-label="Apply layout" title="按当前布线设置应用布局 · Ctrl+Enter" disabled={!current || busy || previewConnecting || previewBusy} onClick={() => previewEngine.current?.command('apply-layout')}><Icon name="bend" size={16} />优化连线</button>
          <div className="tool-group"><button className={`tool ${grid ? 'selected' : ''}`} title="显示点阵网格" aria-label="显示点阵网格" aria-pressed={grid} disabled={previewLayoutDisabled} onClick={() => previewEngine.current?.command('grid', { enabled: !grid })}><Icon name="grid" size={16} /></button><button className="tool" onClick={() => fit()} title="适合画布 F" aria-label="适合画布" disabled={previewLayoutDisabled}><Icon name="fit" /></button><details className="canvas-options"><summary aria-label="画布选项" title="画布选项"><Icon name="more" size={16} /></summary><div><div className="menu-heading">画布</div><button disabled={previewLayoutDisabled} onClick={() => previewEngine.current?.command('show-routing')}>布线与箭头设置</button><button disabled={previewLayoutDisabled} onClick={() => setSemanticFrontier('overview')}>架构概览（F0）</button><button disabled={previewLayoutDisabled} onClick={() => setSemanticFrontier('detail')}>架构详图（F1）</button><button disabled={previewLayoutDisabled} onClick={focusCurrentFrontier}>返回当前前沿</button><button disabled={previewLayoutDisabled} onClick={() => previewEngine.current?.command('expand-all')}>展开全部</button><button disabled={previewLayoutDisabled} onClick={() => previewEngine.current?.command('collapse-all')}>收起全部</button><button disabled={previewLayoutDisabled} onClick={() => { cancelGesture(); previewEngine.current?.command('reset'); }}>恢复初始视图（可撤销）</button></div></details></div>
        </div>
        {actionFeedback && <div className={`canvas-feedback ${actionFeedback.error ? 'error' : ''}`} role={actionFeedback.error ? 'alert' : 'status'}><Icon name={actionFeedback.error ? 'info' : 'check'} size={15} /><span>{actionFeedback.message}</span><button className="tool" aria-label="关闭操作反馈" onClick={() => setActionFeedback(null)}><Icon name="close" size={13} /></button></div>}
        <div ref={viewportRef} className="canvas-viewport prototype-canvas" data-canvas-surface="recursive-preview">
          <PreviewStudio ref={previewEngine} visible={!authoringOpen} onState={snapshot => void receivePreviewState(snapshot)}
            onSelection={receivePreviewSelection} onEditSource={result => { void bindPreviewSource(result, true).catch(error => setFailure(String(error))); }}
            onError={message => { setFailure(message); setActionFeedback({message, error: true}); }} onNotice={(message, error) => { setNotice(message); setFailure(error ? message : ''); setActionFeedback({message, error}); }} onSave={() => void save()} />
        </div>
        {!!layoutGuidance.length && <div className="layout-warning" role="status" aria-label="布局提示">{layoutGuidance.slice(0, 3).map(message => <p key={message}>{message}</p>)}{layoutGuidance.length > 3 && <p>另有 {layoutGuidance.length - 3} 处布局冲突；调整后会重新检查。</p>}</div>}
        {activeRecovery && <div className="layout-recovery-preview" role="status" aria-label="位置修复预览"><p>位置修复预览 · {activeRecovery.plan.operation.scope === 'current-frontier' ? '仅当前视图' : '所有视图'} · 应用后才调整选中对象。</p><div><button className="primary" onClick={applyPositionRecovery}>应用位置修复</button><button onClick={cancelGesture}>取消预览</button></div></div>}
        <div className="command-bar"><span className="command-icon"><Icon name="message" size={17} /></span><input disabled={!selectedNode || previewLayoutDisabled} aria-label="画布文字指令" placeholder={selection.ids.length > 1 ? '向右移动 24，或批量设为蓝色…' : selectedNode ? '向右移动 24，或设为蓝色、命名为…' : '选择一个节点，用文字修改画布…'} value={command} onChange={e => setCommand(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) runCommand(); }} /><span className="local-label">本地视觉指令</span><button onClick={runCommand} disabled={!command.trim() || !selectedNode || previewLayoutDisabled}>应用 <span>↵</span></button></div>
        {sourceOpen && architecture && <div className="source-drawer"><div className="drawer-header"><Icon name="code" size={16} /><b>源码证据</b><span>{previewSourceSpan ? `${previewSourceSpan.path}:${previewSourceSpan.line}` : '只读 · 未执行'}</span><button className="tool" onClick={() => setSourceOpen(false)} aria-label="关闭源码"><Icon name="close" size={16} /></button></div><div className="source-content">{current?.sourceBindingDigest.startsWith('preview-only:') && <p className="field-help">只读源码文本。展示对象没有经过正式模型解析的计算绑定；可在编辑模式中解析支持的源码入口。</p>}{!previewSourceSpan && architecture.sources.length > 0 && <p className="field-help">当前图元没有独立的源码行证据，以下提供完整模型源码供查阅。</p>}{architecture.sources.length === 0 && <p className="field-help">{previewSnapshot.current?.importedDocument ? '当前为 Summary 导入文档，源码位置尚未与 Python 文本验证绑定；可通过原始文档检查声明证据。' : '当前案例是视觉或路由示例，没有模型源码。'}</p>}{architecture.sources.map(source => <div key={source.path}><div className="source-filename">{source.path}</div><pre>{source.content.split('\n').map((line, i) => <div key={i} className={previewSourceSpan?.path === source.path && i + 1 >= previewSourceSpan.line && i + 1 <= previewSourceSpan.endLine ? 'source-highlight' : ''}><span>{i + 1}</span>{line || ' '}</div>)}</pre></div>)}</div></div>}
      </main>
      <aside className="inspector"><div className="inspector-tabs"><button className={panel === 'object' ? 'active' : ''} onClick={() => setPanel('object')}>对象</button><button className={panel === 'legend' ? 'active' : ''} onClick={() => setPanel('legend')}>图例</button><button className={panel === 'page' ? 'active' : ''} onClick={() => setPanel('page')}>页面</button></div><div className="inspector-content">
        {panel === 'object' && frontier && <details className="inspector-section semantic-frontier" open><summary>语义视图<span className="read-only">预览前沿</span></summary><div className="object-heading"><span className="object-icon"><Icon name="layers" size={18} /></span><div><h2>{frontier.label}</h2><span>同一源码语义图的可见切面</span></div></div><div className="coordinate-row"><label>节点 <output>{frontier.visibleNodeCount}</output></label><label>边 <output>{frontier.visibleEdgeCount}</output></label></div><p className="field-help">当前深度 {frontier.depth} · {frontier.expandableCount ? `还有 ${frontier.expandableCount} 个容器可继续细化。` : '当前前沿已展开到可见层级。'}</p><div className="segmented"><button className={frontier.preset === 'overview' ? 'active' : ''} disabled={previewLayoutDisabled} onClick={() => setSemanticFrontier('overview')}>F0 概览</button><button className={frontier.preset === 'detail' ? 'active' : ''} disabled={previewLayoutDisabled} onClick={() => setSemanticFrontier('detail')}>F1 详图</button></div><button className="full-button" disabled={previewLayoutDisabled} onClick={focusCurrentFrontier}>返回当前前沿</button></details>}
        {panel === 'object' && current && <details className="inspector-section summary-interaction"><summary>Summary 交互<span className="read-only">预览辅助</span></summary><label className="field-label" htmlFor="preview-interaction-mode">拖动模式</label><select id="preview-interaction-mode" className="field-select" value={previewSnapshot.current?.interactionMode === 'realtime' ? 'realtime' : 'compat'} disabled={previewLayoutDisabled} onChange={event => previewEngine.current?.command('interaction-mode', { mode: event.target.value })}><option value="compat">兼容模式 · 释放后校验</option><option value="realtime">实时模式 · 拖动中同步</option></select><div className="segmented"><button className={previewSnapshot.current?.showGhost ? 'active' : ''} disabled={previewLayoutDisabled} onClick={() => previewEngine.current?.command('show-ghost', { enabled: !previewSnapshot.current?.showGhost })}>上次路径</button><button className={previewSnapshot.current?.showObstacles ? 'active' : ''} disabled={previewLayoutDisabled} onClick={() => previewEngine.current?.command('show-obstacles', { enabled: !previewSnapshot.current?.showObstacles })}>安全边界</button></div><div className="coordinate-row"><label>快照 <output>{previewSnapshot.current?.snapshotRevision ?? 0}</output></label><label>源码 <output>{previewSnapshot.current?.importedDocument ? '文档证据' : previewSourceIdentity?.sourceSha256 ? '已绑定' : '预览'}</output></label></div><button className="full-button" disabled={previewLayoutDisabled} onClick={() => previewEngine.current?.command('show-routing')}>打开布线与箭头设置</button><button className="full-button" disabled={previewLayoutDisabled} onClick={() => previewEngine.current?.command('show-evidence')}>打开源码与证据</button></details>}
        {panel === 'object' && summaryEditing && <SummaryAuthoringPanel snapshot={previewSnapshot.current} selected={previewSelectedNodeIds} disabled={previewLayoutDisabled} onEdit={editSummary} onCompile={compileSummaryModule} onCertify={certifySummaryAssembly} onFormal={() => void formalSourceEditor()} />}
        {panel === 'object' && <SummaryViewPanel onContinue={() => previewEngine.current?.command('continue-routing')} snapshot={previewSnapshot.current} selectedIds={previewSelectedNodeIds} disabled={previewLayoutDisabled} onCommand={payload => previewEngine.current?.command('semantic-view', payload)} onFocus={id => previewEngine.current?.focus({ nodeId: id })} />}
        {panel === 'object' && current && <SummarySemanticPanel source={previewSource.current} selectedIds={previewSelectedNodeIds} onFocus={id => previewEngine.current?.focus({ nodeId: id })} onEvidence={() => previewEngine.current?.command('show-evidence')} />}
        {panel === 'object' && previewSelectedNodes.length > 0 && <section className="preview-selection-tools" aria-label="画布选区"><h3>已选 {previewSelectedNodes.length} 个节点<span>{previewPinnedCount ? `${previewPinnedCount} 个已固定` : ''}</span><button className="tool" aria-label="清空选区" onClick={() => previewEngine.current?.command('select-nodes', {scope:'clear'})}><Icon name="close" size={13} /></button></h3><p className="selection-names" title={previewSelectedNodes.map(node => node.label || node.id).join('、')}>{previewSelectedNodes.map(node => node.label || node.id).join('、')}</p>{previewSelectedNodes.length > 1 && <p className="field-help">{previewCanAlign ? '使用工具栏的对齐与分布整理所选节点。' : '选区跨越不同容器；选择同级节点后可对齐。'}</p>}</section>}
        {panel === 'object' && previewSelectedNodes.length <= 1 && inspectionNode && inspectionPresentation && <>
          <div className="object-heading"><span className="object-icon" style={{ background: inspectionPresentation.fill }}><Icon name="layers" size={20} /></span><div><h2>{previewPresentation(previewSnapshot.current?.graph)?.nodes?.[inspectionNode.id]?.alias ?? inspectionNode.label ?? inspectionNode.id}</h2><span>{inspectionNode.semantic?.moduleType ?? inspectionNode.semantic?.kind ?? inspectionNode.kind ?? '检查对象'}</span></div></div>
          <div className="evidence-tag opaque">源码检查 · 视觉对象</div>
          <section className="property-section"><h3>显示</h3>
            <TextField label="预览显示名称" value={previewPresentation(previewSnapshot.current?.graph)?.nodes?.[inspectionNode.id]?.alias ?? inspectionNode.label ?? inspectionNode.id} onCommit={label => void applyInspectionVisual([{ type: 'alias', id: inspectionNode.id, label }])} />
            <label className="field-label">填充颜色</label><input type="color" aria-label="检查对象填充颜色" disabled={previewLayoutDisabled || current?.pageSpec.preset === 'monochrome'} value={inspectionPresentation.fill} onChange={event => void applyInspectionVisual([{ type: 'nodeStyle', id: inspectionNode.id, style: { fill: event.target.value } }])} />
            <label className="field-label">边框颜色</label><input type="color" aria-label="检查对象边框颜色" disabled={previewLayoutDisabled || current?.pageSpec.preset === 'monochrome'} value={inspectionPresentation.stroke} onChange={event => void applyInspectionVisual([{ type: 'nodeStyle', id: inspectionNode.id, style: { stroke: event.target.value } }])} />
          </section>
          <details className="inspector-section"><summary>排列与层级</summary><div className="coordinate-row"><label>X <output>{Math.round(inspectionPresentation.x)}</output></label><label>Y <output>{Math.round(inspectionPresentation.y)}</output></label></div>
            {inspectionExpandable && <button className="full-button" disabled={previewLayoutDisabled} onClick={() => void applyInspectionVisual([{ type: 'expand', id: inspectionNode.id, expanded: !inspectionNode.expanded }])}><Icon name="layers" size={14} />{inspectionNode.expanded ? '原位收起检查结构' : '原位展开检查结构'}</button>}
            <button className="text-button" onClick={() => previewEngine.current?.focus({ nodeId: inspectionNode.id })}>聚焦这个检查对象</button>
          </details>
          <section className="property-section"><h3>源码证据</h3><p className="field-help">{inspectionSource ? `${inspectionSource.path}:${inspectionSource.line}–${inspectionSource.endLine}` : '此展示对象没有独立的源码位置。'}</p><button className="full-button" onClick={() => setSourceOpen(true)}><Icon name="code" size={14} />查看检查对象源码</button><p className="field-help">展示和展开保存在递归预览中。此对象没有唯一的正式计算绑定，参数或连接改写请进入模型编辑；视觉调整不改变模型源码。</p></section>
        </>}
        {panel === 'object' && previewSelectedNodes.length <= 1 && selectedNode && current && <>
          <div className="object-heading"><span className="object-icon" style={{ background: (selectedPreviewNodePresentation?.fill ?? selectedSceneNode?.fill) }}><Icon name="layers" size={20} /></span><div><h2>{current.displayAliases[selectedNode.id] ?? selectedNode.label}</h2><span>{selectedNode.kind}</span></div></div><div className={`evidence-tag ${selectedNode.evidence}`}><Icon name="check" size={12} />{statusText(selectedNode.evidence)}</div>
          <section className="property-section"><h3>显示</h3><TextField label="显示名称" value={current.displayAliases[selectedNode.id] ?? selectedNode.label} onCommit={label => apply([{ type: 'alias', id: selectedNode.id, label }])} /><p className="field-help">源名称：{selectedNode.label}</p><label className="field-label">图元样式</label><select className="field-select" aria-label="图元样式" value={current.nodeStyleOverrides[selectedNode.id]?.glyph ?? (selectedPreviewNodePresentation?.glyph ?? selectedSceneNode?.glyph) ?? 'module'} onChange={e => apply([{ type: 'nodeStyle', id: selectedNode.id, style: { glyph: e.target.value as 'module' } }])}>{['module', 'operator', 'tensor', 'attention', 'norm', 'add', 'opaque'].map(g => <option key={g} value={g}>{({ module: '模块框', operator: '紧凑算子', tensor: '张量条带', attention: 'Attention 图元', norm: '归一化图元', add: '加法图元', opaque: '未知边界' } as Record<string, string>)[g]}</option>)}</select><label className="field-label">填充颜色</label><div className="color-palette">{PALETTE.map(color => <button key={color} aria-label={`填充 ${color}`} className={(selectedPreviewNodePresentation?.fill ?? selectedSceneNode?.fill) === color ? 'picked' : ''} style={{ background: color }} onClick={() => apply(selection.ids.map(id => ({ type: 'nodeStyle', id, style: { fill: color } })))} />)}<input type="color" aria-label="自定义填充颜色" value={(selectedPreviewNodePresentation?.fill ?? selectedSceneNode?.fill) ?? '#dcebf6'} onChange={e => apply(selection.ids.map(id => ({ type: 'nodeStyle', id, style: { fill: e.target.value } })))} /></div><label className="field-label">边框颜色</label><div className="color-field"><input type="color" aria-label="边框颜色" value={(selectedPreviewNodePresentation?.stroke ?? selectedSceneNode?.stroke) ?? '#607d91'} onChange={e => apply([{ type: 'nodeStyle', id: selectedNode.id, style: { stroke: e.target.value } }])} /><code>{(selectedPreviewNodePresentation?.stroke ?? selectedSceneNode?.stroke)}</code></div></section>
          <details className="inspector-section"><summary>排列与层级</summary><div className="coordinate-row"><label>X <output>{Math.round(selectedPreviewNodePresentation?.x ?? selectedSceneNode?.x ?? 0)}</output></label><label>Y <output>{Math.round(selectedPreviewNodePresentation?.y ?? selectedSceneNode?.y ?? 0)}</output></label></div><label className="field-label" htmlFor="layout-move-scope">移动范围</label><select id="layout-move-scope" className="field-select" aria-label="移动范围" value={layoutMoveScope} onChange={e => chooseMoveScope(e.target.value as MoveScope)}><option value="all-frontiers">所有视图</option><option value="current-frontier">仅当前视图</option></select><p className="field-help">对齐、位置修复和文字移动使用此范围。{layoutMoveScope === 'current-frontier' ? '调整当前可见前沿；其他层级保留自己的布局。' : '同步调整已保存的展开层级布局。'}</p>{!!selectedNode.children.length && <button className="full-button" disabled={previewLayoutDisabled} onClick={() => apply([{ type: 'expand', id: selectedNode.id, expanded: !current.expandedIds.includes(selectedNode.id) }])}><Icon name="layers" size={14} />{current.expandedIds.includes(selectedNode.id) ? '原位收起' : '原位展开'}</button>}<button className="full-button" onClick={previewPositionRecovery} disabled={busy || selection.ids.length !== 1}><Icon name="align" size={14} />预览位置修复</button><button className="text-button" onClick={() => focusNode(selectedNode.id)}>聚焦这个对象</button></details>
          <details className="inspector-section"><summary>连接点</summary><p className="field-help">{portEditing ? "拖动端口到模块任一边缘。" : "点击“优化自动连接点”比较侧面；使用“显示连接点”查看端口；选中连线后可拖动 S / T 端点。"}</p><button className="full-button" disabled={busy || (!selectedNode.ports.length && !selectedNode.children.length)} onClick={() => optimizeAutomaticPorts(selectedNode.id)}>优化自动连接点</button></details><ParameterEditor node={selectedNode} busy={busy} enabled={!current.sourceBindingDigest.startsWith('preview-only:') && !!capabilities?.semanticWriteback} onPrepare={prepareParameter} onInspectConfiguration={inspectConfiguration} />
          <ActivationEditor node={selectedNode} busy={busy} enabled={!current.sourceBindingDigest.startsWith('preview-only:') && !!capabilities?.supportedIntents?.includes('replace_activation')} inputSpec={inputSpec} onSetup={() => setRuntimeOpen(true)} onPrepare={prepareActivation} />
          <ObjectFacts architecture={current.architecture} node={selectedNode} onSelect={id => { setSelection({ kind: 'node', ids: [id] }); setPanel('object'); }} />
          {selectedNode.ports.some(p => p.direction === 'in') && <ConnectionEditor key={`${architecture?.sourceDigest}:${selectedNode.id}:${JSON.stringify(inputSpec)}`} document={current} nodeId={selectedNode.id} portId={selectedNode.ports.find(p => p.direction === 'in')!.id} busy={busy} inputSpec={inputSpec} onSetup={() => setRuntimeOpen(true)} enabled={!current.sourceBindingDigest.startsWith('preview-only:') && !!capabilities?.supportedIntents?.includes('rebind_input')} onInspect={inspectRebind} onPrepare={prepareRebind} />}
          <details className="inspector-section"><summary>模型事实<span className="read-only">只读</span></summary>{Object.entries(selectedNode.parameters).length ? <dl className="parameters">{Object.entries(selectedNode.parameters).map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{typeof value === 'string' ? value : JSON.stringify(value)}</dd></div>)}</dl> : <p className="field-help">没有已解析的构造参数。</p>}<button className="full-button" onClick={() => setSourceOpen(true)}><Icon name="code" size={14} />查看源码位置</button></details>
        </>}
        {panel === 'object' && selectedEdge && current && <><div className="object-heading"><Icon name="arrow" /><div><h2>{selectedEdge.label || selectedEdge.role}</h2><span>张量关系 · {selectedEdge.role}</span></div></div><section className="property-section"><h3>连线样式</h3><label className="field-label">颜色</label><input type="color" aria-label="连线颜色" disabled={current.pageSpec.preset === 'monochrome'} value={selectedEdgeAppearance?.stroke ?? '#64748b'} onChange={e => apply([{ type: 'edgeStyle', id: selectedEdge.id, style: { stroke: e.target.value } }])} />{current.pageSpec.preset === 'monochrome' && <p className="field-help">黑白模式统一使用灰色；已设置的颜色在论文彩色模式生效。</p>}<label className="field-label">线宽</label><input aria-label="连线宽度" type="range" min="1" max="4" step="0.5" value={selectedEdgeAppearance?.width ?? 1.5} onChange={e => apply([{ type: 'edgeStyle', id: selectedEdge.id, style: { width: Number(e.target.value) } }])} /><label className="check-field"><input type="checkbox" checked={selectedEdgeAppearance?.dashed ?? false} onChange={e => apply([{ type: 'edgeStyle', id: selectedEdge.id, style: { dashed: e.target.checked } }])} />使用虚线</label>{selectedEdgeAppearance && <p className="field-help">当前线型：{edgePatternLabel(selectedEdgeAppearance)} · {current.edgeStyleOverrides[selectedEdge.id]?.dashed === undefined ? '角色默认' : '用户覆盖'}。更改复选框后使用显式实线或通用虚线；可撤销最近编辑。</p>}</section><section className="property-section"><h3>当前端口绑定</h3><p className="field-help">{selectedEdge.source.portId} → {selectedEdge.target.portId}</p><p className="field-help">改走线样式不会改变模型计算关系。</p></section><ConnectionEditor key={`${architecture?.sourceDigest}:${selectedEdge.id}:${JSON.stringify(inputSpec)}`} document={current} nodeId={selectedEdge.target.nodeId} portId={selectedEdge.target.portId} busy={busy} inputSpec={inputSpec} onSetup={() => setRuntimeOpen(true)} enabled={!current.sourceBindingDigest.startsWith('preview-only:') && !!capabilities?.supportedIntents?.includes('rebind_input')} onInspect={inspectRebind} onPrepare={prepareRebind} /></>}
        {panel === 'object' && selectedAnnotation && <><h2>说明文字</h2><TextField label="内容" value={selectedAnnotation.text} onCommit={text => apply([{ type: 'annotation', annotation: { ...selectedAnnotation, text } }])} />{annotationConflicts.length > 0 && <p className="annotation-overlap" role="status">说明正文与 {annotationConflicts.length} 个对象重叠。可移到图下方，再检查导出。</p>}<button className="full-button" onClick={moveAnnotationBelow}><Icon name="align" size={14} />移到图下方</button><button className="text-button" onClick={() => focusAnnotation(selectedAnnotation.id)}>聚焦这段说明</button><button className="full-button" onClick={() => { apply([{ type: 'removeAnnotation', id: selectedAnnotation.id }]); setSelection({ kind: 'node', ids: [] }); }}>移除说明</button></>}
        {panel === 'object' && selectedPreviewEdge && <>
          <div className="object-heading"><Icon name="arrow" /><div><h2>{isPreviewDraftEdge(selectedPreviewEdge) ? '视觉草稿连接' : '预览连接'}</h2><span>{selectedPreviewEdge.id}</span></div></div>
          <section className="property-section"><h3>连线样式</h3>
            <label className="field-label">颜色</label><input type="color" aria-label="视觉连接颜色" disabled={busy || current?.pageSpec.preset === 'monochrome'} value={selectedPreviewEdgeAppearance?.stroke ?? '#263b4b'} onChange={e => void stylePreviewEdge(selectedPreviewEdge.id, { stroke: e.target.value })} />
            {current?.pageSpec.preset === 'monochrome' && <p className="field-help">黑白模式统一使用灰色；已设置的颜色在论文彩色模式生效。</p>}
            <label className="field-label">线宽</label><input aria-label="视觉连接宽度" type="range" min="0.5" max="12" step="0.1" disabled={busy} value={selectedPreviewEdgeAppearance?.width ?? 2.2} onChange={e => void stylePreviewEdge(selectedPreviewEdge.id, { width: Number(e.target.value) })} />
            <label className="check-field"><input type="checkbox" disabled={busy} checked={selectedPreviewEdgeAppearance?.dashed ?? false} onChange={e => void stylePreviewEdge(selectedPreviewEdge.id, { dashed: e.target.checked })} />使用虚线</label>
          </section>
          <section className="property-section"><h3>当前视觉端点</h3>
            <p className="field-help">{graphFromSnapshot()?.nodes.find(node => node.id === selectedPreviewEdge.source)?.label ?? selectedPreviewEdge.source} → {graphFromSnapshot()?.nodes.find(node => node.id === selectedPreviewEdge.target)?.label ?? selectedPreviewEdge.target}</p>
            <p className="field-help">连接及样式保存在当前预览中，可撤销或通过编辑 JSON 恢复。视觉草稿不会自动写入模型源码。</p>
          </section>
        </>}
        {panel === 'object' && !selectedNode && !selectedEdge && !selectedPreviewEdge && !selectedAnnotation && !previewSelectedNodes.length && <><div className="inspector-empty"><div className="empty-symbol"><Icon name="arrow" size={24} /></div><h2>从一个对象开始</h2><p>选择模块、连线或说明文字，<br />调整论文图的呈现方式。</p><div className="shortcut-line"><kbd>拖动空白处</kbd> 框选模块</div><div className="shortcut-line"><kbd>Shift / Ctrl</kbd> 多选对象</div><div className="shortcut-line"><kbd>双击</kbd> 展开 / 收起模块</div></div><div className="document-summary"><h3>{current?.title ?? 'ArchCanvas'}</h3><div><b>{summaryCounts?.nodes ?? architecture?.nodes.length ?? '—'}</b><span>{previewSnapshot.current?.importedDocument ? '文档对象' : summaryCounts ? '源码对象' : '事实对象'}</span><b>{summaryCounts?.edges ?? architecture?.edges.length ?? '—'}</b><span>{summaryCounts ? '依赖关系' : '端口关系'}</span></div></div>{!!architecture?.diagnostics.length && <details className="diagnostics"><summary>{previewSnapshot.current?.importedDocument ? '文档导入边界' : summaryCounts ? '正式编辑分析边界' : '分析边界'}</summary>{architecture.diagnostics.slice(0, 4).map((d, i) => <p key={i}>{d.message}</p>)}</details>}</>}
        {panel === 'legend' && current && <><div className="panel-heading"><h2>图例编辑</h2><p>图例属于画布，随当前版本保存和导出。</p>{current.pageSpec.preset === 'monochrome' && <p className="field-help">悬浮图例显示当前可见连线的角色与实际线型；出版图例随视图和样式自动更新。</p>}</div><div className="legend-list">{current.legendItems.map((item, index) => <div className="legend-editor" key={item.id}><div className="legend-row"><input type="color" aria-label={`图例颜色 ${index + 1}`} value={item.color} onChange={e => apply([{ type: 'legend', items: current.legendItems.map(x => x.id === item.id ? { ...x, color: e.target.value } : x) }])} /><TextField label="" value={item.label} onCommit={label => apply([{ type: 'legend', items: current.legendItems.map(x => x.id === item.id ? { ...x, label } : x) }])} /><button className="tool" aria-label={`删除图例 ${index + 1}`} onClick={() => apply([{ type: 'legend', items: current.legendItems.filter(x => x.id !== item.id) }])}><Icon name="close" size={13} /></button></div><div className="legend-controls"><select aria-label={`图例符号 ${index + 1}`} value={item.glyph} onChange={e => apply([{ type: 'legend', items: current.legendItems.map(x => x.id === item.id ? { ...x, glyph: e.target.value as 'module' } : x) }])}>{['module', 'operator', 'tensor', 'attention', 'norm', 'add', 'opaque'].map(g => <option key={g}>{g}</option>)}</select><button disabled={index === 0} onClick={() => { const items = [...current.legendItems]; [items[index - 1], items[index]] = [items[index], items[index - 1]]; apply([{ type: 'legend', items }]); }} title="上移">↑</button><button disabled={index === current.legendItems.length - 1} onClick={() => { const items = [...current.legendItems]; [items[index + 1], items[index]] = [items[index], items[index + 1]]; apply([{ type: 'legend', items }]); }} title="下移">↓</button></div></div>)}</div><button className="full-button" onClick={() => apply([{ type: 'legend', items: [...current.legendItems, { id: `legend-${crypto.randomUUID()}`, label: '自定义图例', color: '#dcebf6', glyph: 'module' }] }])}><Icon name="plus" size={15} />添加图例条目</button></>}
        {panel === 'page' && current && <><div className="panel-heading"><h2>出版页面</h2><p>SVG、PDF 与 PNG 共用当前画布场景。</p></div><section className="property-section"><label className="field-label">物理页宽</label><div className="segmented">{[85, 180].map(widthMm => <button key={widthMm} className={current.pageSpec.widthMm === widthMm ? 'active' : ''} onClick={() => apply([{ type: 'page', page: { widthMm } }])}>{widthMm} mm</button>)}</div><label className="field-label">背景</label><div className="color-field"><input aria-label="页面背景" type="color" value={current.pageSpec.background} onChange={e => apply([{ type: 'page', page: { background: e.target.value } }])} /><code>{current.pageSpec.background}</code></div><label className="field-label">配色</label><div className="segmented"><button className={current.pageSpec.preset === 'paper' ? 'active' : ''} onClick={() => apply([{ type: 'page', page: { preset: 'paper' } }])}>论文彩色</button><button className={current.pageSpec.preset === 'monochrome' ? 'active' : ''} onClick={() => apply([{ type: 'page', page: { preset: 'monochrome' } }])}>黑白</button></div></section><section className="property-section"><h3>说明文字</h3><button className="full-button" onClick={addAnnotation}><Icon name="plus" size={14} />添加说明文字</button><p className="field-help">使用右上角“导出”生成 SVG、PDF、PNG 或完整编辑 JSON。</p></section></>}
      </div><div className="inspector-footer"><Icon name="info" size={14} /><span>视觉编辑不修改模型源码</span></div></aside>
    </div>
    <footer className={`statusbar ${failure ? 'has-error' : ''}`}><span><i className={busy ? 'busy-dot' : 'live-dot'} />{failure || (runtimeCancel ? cancelling ? '正在取消运行验证…' : '正在隔离运行并核对前后结构…' : busy ? '正在处理…' : notice)}</span><div>{runtimeCancel && <button disabled={cancelling} onClick={() => void cancelRuntime()}>{cancelling ? '取消中…' : '取消运行验证'}</button>}{selection.ids.length > 0 && <span>{selection.ids.length} 个已选</span>}<span>RECURSIVE PREVIEW</span><span>rev {current?.revision ?? 0}</span></div></footer>
    {runtimeOpen && architecture && <RuntimeProfileDialog architecture={architecture} initial={inputSpec} example={exampleId === 'multi_input'} onSave={saveInputSpec} onClose={() => setRuntimeOpen(false)} />}
    {connectionProposal && <div className="modal-backdrop"><div className="runtime-modal connection-proposal" role="dialog" aria-modal="true" aria-labelledby="proposal-title"><div className="modal-heading"><div><div className="eyebrow">CONNECTION PROPOSAL</div><h2 id="proposal-title">{connectionProposal.candidate ? '检查改接提案' : '保留未支持的连接提案'}</h2></div><button className="tool" aria-label="关闭连接提案" onClick={() => setConnectionProposal(null)}><Icon name="close" /></button></div>{connectionProposal.candidate ? <p>将选定输入连接到 <b>{connectionProposal.candidate.variable}</b>。当前只创建提案；运行验证后会展示准确源码 diff 和前后关系，批准后才能提交工作副本。</p> : connectionProposal.blockers.map((blocker, i) => <p key={i}>{blocker}</p>)}<div className="modal-actions"><button onClick={() => setConnectionProposal(null)}>保留当前连接</button>{!inputSpec && <button onClick={() => { setConnectionProposal(null); setRuntimeOpen(true); }}>设置运行输入与模式</button>}{connectionProposal.candidate && <button className="primary" disabled={busy} onClick={() => { const proposal = connectionProposal; setConnectionProposal(null); prepareRebind(proposal.nodeId, proposal.portId, proposal.candidate!.binding); }}>运行验证并预览源码修改</button>}</div></div></div>}
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
  return <label className="text-field">{label && <span className="field-label">{label}</span>}<input aria-label={label || '图例文字'} value={draft} onChange={e => { cancelled.current = false; setDraft(e.target.value); }} onBlur={() => { if (!cancelled.current && draft !== value) onCommit(draft); cancelled.current = false; }} onKeyDown={e => { if (e.nativeEvent.isComposing) return; if (e.key === 'Enter') e.currentTarget.blur(); if (e.key === 'Escape') { cancelled.current = true; setDraft(value); e.currentTarget.blur(); } }} /></label>;
}
