import { sameSourceSemantics } from './sourcePresentation';
import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { api, ApiError } from './api';
import type { GeneratedDraft, SourceRegion, EditedSourceRegion } from './api';
import { Icon } from './icons';
import { addDraftNode, arrangeDraft, blankDraft, changeDraft, connectDraft, DRAFT_WIDTH, draftModuleSize, draftNodeSize, draftPortSpacing, draftHistory, draftRoutes, nextDraftPosition, portPoint, removeDraftNode, travelDraft, sourceDraftCatalog, draftSourceKind, moveDraftNodes, selectDraftNode, setDraftPortLayout } from './authoring';
import { nearestPortLayout } from './core/portRouting.ts';
import type { PortLayout, Architecture } from './core/types';
import type { AuthoredDraft, DraftCatalog, DraftEndpoint, DraftFlow, DraftHistory, DraftModule, DraftParameter, DraftValue } from './authoring';
import './AuthoringStudio.css';
import { beginCameraPan, cameraAtPanInput } from './cameraGesture';
import type { CameraPan } from './cameraGesture';
import { fitDraftCamera, parseDraftField, resolveDraftFeedback } from './authoringFeedback';
import type { DraftFeedback } from './authoringFeedback';
import { draftPresets, draftPresetSize, draftPresetUnavailable, insertDraftPreset } from './authoringPresets';
import type { DraftPreset } from './authoringPresets';
import { draftPortPresentation } from './draftPortPresentation';
import { draftParameterHelp } from './draftParameterHelp';
import { draftValidationKey, draftTensorLabel, readDraftValidation } from './draftValidation';
import type { DraftValidation } from './draftValidation';
import { draftCanvasTextScale, draftFittedText } from './draftTextReadability';
import { placeDraftTooltip } from './draftTooltipPlacement';
import { draftEdgeRoles } from './draftEdgeRoles';
import { reprojectSourceDraft, revealSourceRegion, restoreSourceRegion, expandSourceDraftScopes, invalidSourceDraftGeometry } from './sourceDraftFrontier';
import { sourceStructureEntries, filterSourceStructure } from './sourceStructureLibrary.ts';
import { canvasDotGrid, clampCanvasZoom } from './cameraProjection';
import { draftPaletteCategories, draftPaletteCategoryLabel, draftPresetMatches, filterDraftModules } from './draftPalette';
import { authoringCameraAtViewport, reopenAuthoringWorkspace } from './sourceAuthoringSession';
import { AUTHORING_CACHE_ERROR, writeCachedAuthoringWorkspace, restoreCachedAuthoringWorkspace } from './authoringWorkspaceCache';

export type DraftCamera = { x: number; y: number; zoom: number };
type Camera = DraftCamera;
export type { AuthoringWorkspace } from './sourceAuthoringSession';
import type { AuthoringWorkspace } from './sourceAuthoringSession';
import { cameraViewportSize } from './cameraViewport';
import type { CameraViewport } from './cameraViewport';
import { WorkspaceModeSwitch } from './WorkspaceModeSwitch';
import { sameGeneratedDraft } from './generatedWorkspace';
import { CustomModuleDialog } from './CustomModuleDialog';
import { customModuleCatalog } from './customModules';
import { implicitDraftRootIds } from './authoring';
import { FloatingLegend } from './FloatingLegend';
import { draftSourceRelations } from './draftSourceRelations.ts';
import { SOURCE_RELATION_DASH, SOURCE_RELATION_LABEL, SOURCE_RELATION_STROKE, sourceCoveredEdgeIds, tensorEdgeCovered } from './core/sourceRelationRoutes.ts';
import type { CustomModulePreview } from './customModules';
type Gesture = { type: 'node' | 'pan' | 'port' | 'port-layout' | 'marquee'; pointer: number; clientX: number; clientY: number; camera: Camera; base: AuthoredDraft; pan?: CameraPan; nodeId?: string; nodeIds?: string[]; selection?: string[]; additive?: boolean; endpoint?: DraftEndpoint };
type PaletteDrag = { type: 'module' | 'preset'; id: string; label: string };
const UNSUPPORTED_SEARCH_HINTS = [
  { aliases: ['sigmoid'], label: 'Sigmoid', alternative: 'ReLU、GELU 或 SiLU，激活行为不同' },
  { aliases: ['softmax'], label: 'Softmax', alternative: 'ReLU、GELU 或 SiLU，但它们不提供概率归一化' },
  { aliases: ['tanh'], label: 'Tanh', alternative: 'ReLU、GELU 或 SiLU，输出范围与激活行为不同' },
  { aliases: ['conv1d'], label: 'Conv1d', alternative: 'Conv2d，仅用于二维空间输入' },
  { aliases: ['avgpool2d'], label: 'AvgPool2d', alternative: 'MaxPool2d 或 AdaptiveAvgPool2d，池化方式或输出尺寸设置不同' },
  { aliases: ['batchnorm1d'], label: 'BatchNorm1d', alternative: 'BatchNorm2d，仅用于四维图像张量' },
  { aliases: ['multiheadattention', 'attention', '注意力'], label: 'MultiheadAttention / Attention', alternative: 'Embedding、LayerNorm、Linear 或 MLP 网络起点；这些模块不提供注意力计算' },
  { aliases: ['lstm'], label: 'LSTM', alternative: 'Embedding、Linear 或 MLP 网络起点；这些模块不提供循环状态' },
  { aliases: ['gru'], label: 'GRU', alternative: 'Embedding、Linear 或 MLP 网络起点；这些模块不提供循环状态' },
] as const;

export function unsupportedPaletteMessage(value: string): string | null {
  const query = value.trim().toLowerCase();
  const match = UNSUPPORTED_SEARCH_HINTS.find(item => item.aliases.some(alias => query.includes(alias)));
  return match ? `暂不支持 ${match.label}。当前可用选项：${match.alternative}。` : null;
}

function createBlank() { return blankDraft(`draft-${crypto.randomUUID()}`); }
export function AuthoringStudio({ onClose, onOpen, initialWorkspace, onViewState, browseBaseline, onReuseView, onNewBlank, onSourceOpen }: { onClose: () => void; onOpen: (generated: GeneratedDraft) => Promise<void>; initialWorkspace?: AuthoringWorkspace; onViewState?: (workspace: AuthoringWorkspace) => void; browseBaseline?: AuthoredDraft; onReuseView?: (workspace: AuthoringWorkspace) => void | boolean | Promise<void | boolean>; onNewBlank?: (workspace: AuthoringWorkspace) => void; onSourceOpen?: (architecture: Architecture) => Promise<void> }) {
  const [initial, setInitial] = useState<AuthoringWorkspace>(() => initialWorkspace ?? { draft: createBlank(), storageRevision: 0, savedRevision: -1 });
  const [cacheReady, setCacheReady] = useState(!!initialWorkspace);
  const [cacheWritable, setCacheWritable] = useState(!!initialWorkspace);
  const cacheWriter = useRef(writeCachedAuthoringWorkspace);
  const [history, setHistory] = useState(() => initial.history ?? draftHistory(initial.draft));
  const [baseCatalog, setBaseCatalog] = useState<DraftCatalog | null>(null);
  const [storageRevision, setStorageRevision] = useState(initial.storageRevision ?? 0);
  const [savedRevision, setSavedRevision] = useState(initial.savedRevision ?? -1);
  const [selection, setSelection] = useState<{ node?: string; nodes?: string[]; edge?: string }>(() => ({ node: initial.selection?.at(-1), nodes: initial.selection ?? [] }));
  const [camera, setCamera] = useState<Camera>(initial.camera ?? { x: 30, y: 30, zoom: 1 });
  const [preview, setPreview] = useState<AuthoredDraft | null>(null);
  const [connection, setConnection] = useState<{ endpoint: DraftEndpoint; x: number; y: number } | null>(null);
  const [tool, setTool] = useState<'select' | 'pan'>(initial.tool ?? 'select');
  const [portEditing, setPortEditing] = useState(false);
  const [marquee, setMarquee] = useState<{ x: number; y: number; width: number; height: number } | null>(null);
  const [search, setSearch] = useState('');
  const [paletteView, setPaletteView] = useState<'modules' | 'presets'>('modules');
  const [paletteCategory, setPaletteCategory] = useState('');
  const [paletteDrag, setPaletteDrag] = useState<PaletteDrag | null>(null);
  const [dropActive, setDropActive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [busyOperation, setBusyOperation] = useState<'check' | 'save' | 'reopen' | 'generate' | 'open' | 'frontier' | null>(null);
  const [notice, storeNotice] = useState('从左侧拖入输入、模块和输出；点击输出端口，再点击输入端口连接。');
  const [error, setError] = useState('');
  const [checkNoticeKey, setCheckNoticeKey] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<DraftFeedback | null>(null);
  const [invalidFields, setInvalidFields] = useState<string[]>([]);
  const [generated, setGenerated] = useState<GeneratedDraft | null>(null);
  const [sourceEditor, setSourceEditor] = useState<{ draft: AuthoredDraft; region: SourceRegion } | null>(null);
  const [customModuleOpen, setCustomModuleOpen] = useState(false);
  const [validation, setValidation] = useState<{ key: string; result: DraftValidation } | null>(null);
  const [hoveredPort, setHoveredPort] = useState<DraftEndpoint | null>(null);
  const [focusedPort, setFocusedPort] = useState<DraftEndpoint | null>(null);
  const portHint = hoveredPort ?? focusedPort;
  const hintRef = useRef<HTMLDivElement>(null);
  const [measuredHint, setMeasuredHint] = useState<{ key: string; left: number; top: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [viewportSize, setViewportSize] = useState({ width: 254, height: 150 });
  const cameraViewport = useRef<CameraViewport | undefined>(initial.viewport);
  const fitSourceOnEntry = useRef(!initial.camera && !!initial.draft.sourceProvenance?.viewCanvas);
  const gesture = useRef<Gesture | null>(null);
  const currentRef = useRef(history); currentRef.current = history;
  const saving = useRef(false);
  const sourceScopesChecked = useRef(false);
  const browsing = useRef(false);
  const invalidFieldsRef = useRef<string[]>([]);
  const draft = preview ?? history.draft;
  const implicitRoots = useMemo(() => implicitDraftRootIds(draft), [draft]);
  const catalog = useMemo(() => sourceDraftCatalog(history.draft, baseCatalog), [history.draft.sourceProvenance, history.draft.customModules, baseCatalog]);
  const paletteCatalog = useMemo(() => baseCatalog ? { ...baseCatalog, modules: [...baseCatalog.modules, ...(history.draft.customModules ?? []).map(customModuleCatalog)] } : null, [baseCatalog, history.draft.customModules]);
  const catalogRef = useRef(catalog); catalogRef.current = catalog;
  const selectedIds = useMemo(() => selection.nodes ?? (selection.node ? [selection.node] : []), [selection]);
  const grid = canvasDotGrid(camera);
  const viewStateRef = useRef(onViewState); viewStateRef.current = onViewState;
  const selected = draft.nodes.find(node => node.id === selection.node);
  const selectedModule = catalog?.modules.find(module => module.kind === selected?.kind);
  const sourceFacts = useMemo(() => new Map(draft.sourceProvenance?.architecture.nodes.map(node => [node.id, node]) ?? []), [draft.sourceProvenance?.architecture]);
  const geometry = useMemo(() => catalog ? draftRoutes(draft, catalog) : { routes: [], overlaps: [], flow: 'horizontal' as const, nodeFlows: {} as Record<string, DraftFlow>, ports: {} as Record<string, Record<string, { x: number; y: number; side: PortLayout['side'] }>> }, [draft, catalog]);
  const edgeRoles = useMemo(() => catalog ? draftEdgeRoles(draft, catalog) : new Map<string, 'data' | 'residual'>(), [draft, catalog]);
  const sourceRouting = useMemo(() => catalog ? draftSourceRelations(draft, catalog) : { relations: [], points: [], diagnostics: [] }, [draft, catalog]);
  const dirty = history.draft.revision !== savedRevision;
  const validationKey = useMemo(() => draftValidationKey(history.draft), [history.draft]);
  const checked = validation?.key === validationKey && !invalidFields.length ? validation.result : null;
  const currentNotice = checkNoticeKey && (checkNoticeKey !== validationKey || !checked) ? '草稿结构已改变；请重新检查声明形状与连接，模型尚未执行。' : notice;
  const labelScale = draftCanvasTextScale(camera.zoom);
  useEffect(() => {
    if (initialWorkspace) return;
    let alive = true;
    void restoreCachedAuthoringWorkspace(() => initial).then(recovered => {
      if (!alive) return;
      restoreWorkspace(recovered.workspace);
      if (recovered.warning) setError(recovered.warning);
      setCacheWritable(recovered.writable); setCacheReady(true);
    });
    return () => { alive = false; };
  }, []);
  function restoreWorkspace(workspace: AuthoringWorkspace) {
    const restoredHistory = workspace.history ?? draftHistory(workspace.draft);
    currentRef.current = restoredHistory;
    cameraViewport.current = workspace.viewport;
    fitSourceOnEntry.current = !workspace.camera && !!workspace.draft.sourceProvenance?.viewCanvas;
    setInitial(workspace); setHistory(restoredHistory);
    setStorageRevision(workspace.storageRevision ?? 0); setSavedRevision(workspace.savedRevision ?? -1);
    setSelection({ node: workspace.selection?.at(-1), nodes: workspace.selection ?? [] });
    setCamera(workspace.camera ?? { x: 30, y: 30, zoom: 1 }); setTool(workspace.tool ?? 'select');
  }
  useEffect(() => {
    if (cacheReady) viewStateRef.current?.({ draft: history.draft, history, storageRevision, savedRevision, selection: selectedIds, camera, viewport: cameraViewport.current, tool, sourceHistory: initial.sourceHistory, viewBaseline: initial.viewBaseline });
  }, [cacheReady, history, storageRevision, savedRevision, selection, camera, tool]);

  useEffect(() => {
    if (!cacheReady) return;
    let alive = true;
    api.authoringCatalog().then(async value => {
      if (!alive) return;
      catalogRef.current = sourceDraftCatalog(currentRef.current.draft, value); setBaseCatalog(value);
      try {
        const result = readDraftValidation(await api.validateDraft(initial.draft));
        if (alive && initial.draft === currentRef.current.draft) receiveValidation(initial.draft, result);
      }
      catch (reason) { if (alive && initial.draft === currentRef.current.draft) reportError(reason, '先前草稿尚未通过检查，编辑已保留：'); }
    }).catch(reason => { if (alive) setError(String(reason)); });
    return () => { alive = false; };
  }, [cacheReady, initial.draft]);
  useEffect(() => {
    if (!cacheReady || !cacheWritable) return;
    let alive = true;
    void cacheWriter.current!({ draft: history.draft, history, storageRevision, savedRevision, selection: selectedIds,
      camera, viewport: cameraViewport.current, tool, sourceHistory: initial.sourceHistory, viewBaseline: initial.viewBaseline })
      .then(() => { if (alive) setError(previous => previous === AUTHORING_CACHE_ERROR ? '' : previous); })
      .catch(() => { if (alive) setError(AUTHORING_CACHE_ERROR); });
    return () => { alive = false; };
  }, [cacheReady, cacheWritable, history, storageRevision, savedRevision, selectedIds, camera, tool]);

  useLayoutEffect(() => {
    const viewport = svgRef.current;
    if (!viewport) return;
    const resize = () => {
      const size = cameraViewportSize({ width: viewport.clientWidth, height: viewport.clientHeight });
      if (!size) return;
      const previous = cameraViewport.current; cameraViewport.current = size;
      setCamera(camera => authoringCameraAtViewport(camera, previous, size));
      setViewportSize(size);
    };
    resize();
    const observer = new ResizeObserver(resize); observer.observe(viewport);
    return () => observer.disconnect();
  }, [cacheReady]);

  useEffect(() => {
    if (!catalog || !fitSourceOnEntry.current) return;
    fitSourceOnEntry.current = false;
    const rect = svgRef.current?.getBoundingClientRect();
    const nodes = initial.draft.nodes.filter(node => !implicitDraftRootIds(initial.draft).has(node.id));
    if (rect && nodes.length) {
      const fitted = fitDraftCamera({ ...initial.draft, nodes }, rect, catalog, draftSourceRelations(initial.draft, catalog).points);
      if (fitted.zoom < .45) {
        const left = Math.min(...nodes.map(node => node.position.x)), right = Math.max(...nodes.map(node => node.position.x + draftNodeSize(node, catalog).width));
        const top = Math.min(...nodes.map(node => node.position.y)), zoom = .55;
        setCamera({ x: rect.width / 2 - (left + right) / 2 * zoom, y: 24 - top * zoom, zoom });
      } else setCamera(fitted);
    }
    setNotice('源码编辑前沿已载入；大型源码区域可按需逐层展开，已支持的基础模块参数可直接编辑。');
  }, [catalog]);

  useEffect(() => {
    if (!cacheReady || !catalog || busy || sourceScopesChecked.current) return;
    sourceScopesChecked.current = true;
    const snapshot = currentRef.current.draft, source = snapshot.sourceProvenance;
    if (!source) return;
    const invalidGeometry = invalidSourceDraftGeometry(snapshot) || invalidSourceDraftGeometry(snapshot, source.originalGraph.nodes);
    if (snapshot.sourceCache && !invalidGeometry) return;
    const expanded = new Set(source.canvas.expandedIds);
    if (!invalidGeometry && !source.architecture.nodes.some(node => node.kind === 'SourceBranch' && node.children.length && !expanded.has(node.id))) return;
    cancel(); setBusy(true); setBusyOperation('frontier');
    void expandSourceDraftScopes(snapshot, catalogRef.current).then(result => {
      if (snapshot !== currentRef.current.draft) return;
      const next = changeDraft(currentRef.current, value => Object.assign(value, result));
      currentRef.current = next; setHistory(next); setGenerated(null); fit(next.draft);
      setNotice('已补全旧草稿的分支内部；可逐层展开、删除，并从“当前模型源码结构”恢复。');
    }).catch(reason => { if (snapshot === currentRef.current.draft) reportError(reason); })
      .finally(() => { setBusy(false); setBusyOperation(null); });
  }, [cacheReady, catalog, busy]);

  function cancel() {
    const active = gesture.current; gesture.current = null; setPreview(null); setConnection(null); setHoveredPort(null); setFocusedPort(null);
    clearPaletteDrag(); setMarquee(null);
    if (active?.type === 'pan') setCamera(active.camera);
    if (active && svgRef.current?.hasPointerCapture(active.pointer)) svgRef.current.releasePointerCapture(active.pointer);
  }
  function setNotice(value: string) { storeNotice(value); setCheckNoticeKey(null); }
  function clearError() { setError(''); setFeedback(null); }
  function startBlankDraft() {
    if (busy) return;
    cancel();
    if (onNewBlank) {
      onNewBlank({ draft: currentRef.current.draft, history: currentRef.current, storageRevision, savedRevision,
        selection: selectedIds, camera, viewport: cameraViewport.current, tool,
        sourceHistory: initial.sourceHistory, viewBaseline: initial.viewBaseline });
      return;
    }
    if (dirty && (history.draft.revision > 0 || history.draft.nodes.length > 0)) {
      setNotice('当前草稿有未保存编辑，请先保存或重开后再新建空白模型。');
      return;
    }
    const next = draftHistory(createBlank());
    currentRef.current = next; setHistory(next); setStorageRevision(0); setSavedRevision(-1);
    setSelection({}); setGenerated(null); setCamera({ x: 30, y: 30, zoom: 1 }); clearError();
  }
  function discardInvalidInput() {
    const message = '未提交的无效输入已放弃；草稿仍保留上次有效参数。';
    setNotice(message);
    setError(previous => previous && !previous.includes(message) ? `${previous} ${message}` : previous);
  }
  function focusDraftNode(id: string) {
    cancel(); const node = currentRef.current.draft.nodes.find(item => item.id === id), rect = svgRef.current?.getBoundingClientRect(), currentCatalog = catalogRef.current;
    if (!node || !rect || !currentCatalog) return;
    setSelection({ node: id, nodes: [id] });
    setCamera(old => { const zoom = Math.max(.7, Math.min(1, old.zoom)); return { zoom, x: rect.width / 2 - (node.position.x + DRAFT_WIDTH / 2) * zoom, y: rect.height / 2 - (node.position.y + draftNodeSize(node, currentCatalog).height / 2) * zoom }; });
  }
  function reportError(reason: unknown, prefix = '') {
    const value = resolveDraftFeedback(reason, currentRef.current.draft, catalogRef.current);
    setError(prefix + value.message); setFeedback(value);
    if (value.target) focusDraftNode(value.target.nodeId);
  }
  function fieldValidity(nodeId: string, parameter: string, invalid: boolean) {
    const key = `${nodeId}:${parameter}`, previous = invalidFieldsRef.current;
    if (previous.includes(key) === invalid) return;
    const next = invalid ? [...previous, key] : previous.filter(item => item !== key);
    invalidFieldsRef.current = next; setInvalidFields(next);
  }
  function apply(update: (draft: AuthoredDraft) => void) {
    if (busy) return;
    cancel();
    try { const next = changeDraft(currentRef.current, update); currentRef.current = next; setHistory(next); setGenerated(null); clearError(); return next.draft; }
    catch (reason) { reportError(reason); }
  }
  function travel(action: 'undo' | 'redo') {
    cancel(); const previous = currentRef.current, next = travelDraft(previous, action);
    currentRef.current = next; setHistory(next); setGenerated(null); clearError();
    if (next !== previous) setNotice(action === 'undo' ? '已撤销上一步草稿修改。' : '已恢复下一步草稿修改。');
  }
  function point(clientX: number, clientY: number) {
    const rect = svgRef.current!.getBoundingClientRect();
    return { x: (clientX - rect.left - camera.x) / camera.zoom, y: (clientY - rect.top - camera.y) / camera.zoom };
  }
  function clearPaletteDrag() { setPaletteDrag(null); setDropActive(false); }
  function startPaletteDrag(event: React.DragEvent<HTMLButtonElement>, entry: PaletteDrag) {
    if (busy || !catalog) { event.preventDefault(); return; }
    event.dataTransfer.setData(`application/x-archcanvas-${entry.type}`, entry.id);
    event.dataTransfer.effectAllowed = 'copy'; setPaletteDrag(entry); setDropActive(false);
  }
  function acceptsPaletteDrag(event: React.DragEvent<HTMLDivElement>) {
    return !busy && !!catalog && Array.from(event.dataTransfer.types).some(type => type === 'application/x-archcanvas-module' || type === 'application/x-archcanvas-preset');
  }
  function paletteDragOver(event: React.DragEvent<HTMLDivElement>) {
    if (!acceptsPaletteDrag(event)) return;
    event.preventDefault(); event.dataTransfer.dropEffect = 'copy'; setDropActive(true);
  }
  function paletteDragLeave(event: React.DragEvent<HTMLDivElement>) {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDropActive(false);
  }
  function paletteDrop(event: React.DragEvent<HTMLDivElement>) {
    const accepts = acceptsPaletteDrag(event); clearPaletteDrag();
    if (!accepts) return;
    event.preventDefault();
    const preset = draftPresets.find(item => item.id === event.dataTransfer.getData('application/x-archcanvas-preset'));
    if (preset) { const at = point(event.clientX, event.clientY); addPreset(preset, { x: at.x - DRAFT_WIDTH / 2, y: at.y - 30 }); return; }
    const module = catalog?.modules.find(item => item.kind === event.dataTransfer.getData('application/x-archcanvas-module'));
    if (module) { const at = point(event.clientX, event.clientY); add(module, { x: at.x - DRAFT_WIDTH / 2, y: at.y - 30 }); }
  }
  function add(module: DraftModule, position?: { x: number; y: number }) {
    if (busy || !catalog) return;
    const size = draftModuleSize(module);
    const rect = svgRef.current?.getBoundingClientRect();
    const center = rect ? point(rect.left + rect.width / 2, rect.top + rect.height / 2) : { x: 80, y: 80 };
    const at = position ?? nextDraftPosition(draft, { x: center.x - DRAFT_WIDTH / 2, y: center.y - size.height / 2 }, module, catalog);
    const id = `n_${crypto.randomUUID().replaceAll('-', '')}`;
    const next = apply(value => addDraftNode(value, module, id, { x: Math.round(at.x), y: Math.round(at.y) }));
    if (!next) return;
    setSelection({ node: id, nodes: [id] }); setNotice(`已添加 ${module.label}；在右侧编辑参数。`);
    if (rect && !position && (at.y * camera.zoom + camera.y + size.height * camera.zoom > rect.height - 20)) setCamera(old => ({ ...old, y: rect.height / 2 - (at.y + size.height / 2) * old.zoom }));
  }
  function insertCustomModule(preview: CustomModulePreview) {
    if (busy || !catalog) return;
    const definition = preview.definition, module = preview.module;
    const nextCatalog = { ...catalog, modules: [...catalog.modules.filter(item => item.kind !== module.kind), module] };
    const rect = svgRef.current?.getBoundingClientRect(), size = draftModuleSize(module);
    const center = rect ? point(rect.left + rect.width / 2, rect.top + rect.height / 2) : { x: 180, y: 150 };
    const position = nextDraftPosition(currentRef.current.draft, { x: center.x - size.width / 2, y: center.y - size.height / 2 }, module, nextCatalog);
    const id = `n_${crypto.randomUUID().replaceAll('-', '')}`;
    const next = apply(value => {
      value.customModules ??= [];
      if (!value.customModules.some(item => item.kind === definition.kind)) value.customModules.push(structuredClone(definition));
      addDraftNode(value, module, id, position);
    });
    if (!next) return;
    setSelection({ node: id, nodes: [id] }); setPaletteView('modules'); setPaletteCategory('custom'); setSearch(''); setCustomModuleOpen(false);
    setNotice(`已添加 ${module.label}；可连接输入与输出，也可从左侧重复插入。输出形状未推测。`);
  }
  function addPreset(preset: DraftPreset, position?: { x: number; y: number }) {
    if (busy || !catalog) return;
    const rect = svgRef.current?.getBoundingClientRect(), size = draftPresetSize(preset, catalog);
    const center = rect ? point(rect.left + rect.width / 2, rect.top + rect.height / 2) : { x: 80 + size.width / 2, y: 130 };
    const at = position ?? { x: center.x - size.width / 2, y: center.y - size.height / 2 };
    try {
      const candidate = structuredClone(currentRef.current.draft), existing = candidate.nodes.length;
      const inserted = insertDraftPreset(candidate, catalog, preset.id, at);
      const next = apply(value => { value.nodes = candidate.nodes; value.edges = candidate.edges; });
      if (!next) return;
      setSelection({ node: inserted.inputNodeId, nodes: [inserted.inputNodeId] }); fit(next);
      setNotice(`已${existing ? '添加一个独立网络' : '添加'}：${preset.label}。可在右侧修改输入形状，逐个选择模块编辑；一次撤销即可移除本次添加。`);
    } catch (reason) { reportError(reason); }
  }
  function connect(source: DraftEndpoint, target: DraftEndpoint) {
    if (!catalog) return;
    // Validate against a copy first: errors are reported outside React's updater.
    try {
      const value = structuredClone(currentRef.current.draft);
      const id = `e_${crypto.randomUUID().replaceAll('-', '')}`;
      connectDraft(value, catalog, source, target, id);
      apply(next => { next.edges = value.edges; }); setNotice('已建立张量连接；可选择连线删除。');
    } catch (reason) { cancel(); reportError(reason); }
  }
  function deleteSelection() {
    if (busy) return;
    if (selectedIds.length) { if (apply(value => { for (const id of selectedIds) removeDraftNode(value, id); })) setNotice(draft.sourceProvenance ? '已删除模块及相连连线；可撤销，或从左侧“当前模型源码结构”恢复。' : '已删除模块及相连连线；请重新检查当前结构。'); }
    else if (selection.edge) { if (apply(value => { value.edges = value.edges.filter(edge => edge.id !== selection.edge); })) setNotice('已删除连线；请重新检查当前结构。'); }
    setSelection({});
  }
  function receiveValidation(snapshot: AuthoredDraft, result: DraftValidation) {
    const key = draftValidationKey(snapshot);
    if (draftValidationKey(result.draft) !== key) throw new Error('检查结果与当前草稿声明不一致，请重新检查。');
    if (key !== draftValidationKey(currentRef.current.draft)) return false;
    setValidation({ key, result }); return true;
  }
  async function check() {
    if (busy || !catalog || invalidFieldsRef.current.length) return;
    cancel(); setBusy(true); setBusyOperation('check'); clearError();
    const snapshot = currentRef.current.draft;
    try {
      const result = readDraftValidation(await api.validateDraft(snapshot));
      if (receiveValidation(snapshot, result)) { setNotice(result.complete ? result.draft.sourceProvenance ? result.generation ? result.generation.supported ? result.generation.topology === 'anchored-edits' ? '连接检查通过；可生成已定位调用处的结构修改副本，保留其余源码；形状与模型执行尚未验证。' : '连接检查通过；可生成保留原分支的源码副本，形状与模型执行尚未验证。' : '连接检查通过；当前修改超出源码保留生成范围，请查看生成限制。' : '连接检查通过；源码生成仍需独立核对，形状与模型执行尚未验证。' : '静态检查通过；声明形状与连接相容，模型尚未执行。' : `还有 ${result.issues.length} 项需要完成；可在右侧定位并继续搭建。`); setCheckNoticeKey(draftValidationKey(snapshot)); }
    } catch (reason) {
      if (draftValidationKey(snapshot) === draftValidationKey(currentRef.current.draft)) { setValidation(null); reportError(reason, '检查未通过：'); }
    } finally { setBusyOperation(null); setBusy(false); }
  }
  async function save() {
    if (saving.current || busy || invalidFieldsRef.current.length) return;
    cancel(); saving.current = true; setBusy(true); setBusyOperation('save');
    const snapshot = currentRef.current.draft;
    try {
      const result = await api.saveDraft(snapshot, storageRevision);
      if (snapshot === currentRef.current.draft) { setStorageRevision(result.revision); setSavedRevision(snapshot.revision); setNotice('模型草稿已保存；可重开继续搭建。'); clearError(); }
    } catch (reason) { if (snapshot === currentRef.current.draft) reportError(reason, '保存失败，草稿已保留：'); }
    finally { saving.current = false; setBusyOperation(null); setBusy(false); }
  }
  async function reopen() {
    if (busy) return;
    const snapshot = currentRef.current.draft;
    cancel(); setBusy(true); setBusyOperation('reopen');
    try {
      const result = await api.draft(history.draft.id);
      if (snapshot === currentRef.current.draft) {
        const restored = reopenAuthoringWorkspace({ draft: snapshot, history: currentRef.current, storageRevision, savedRevision, selection: selectedIds, camera, tool }, result.draft, result.revision);
        const next = restored.history!; currentRef.current = next; setHistory(next); setStorageRevision(result.revision); setSavedRevision(restored.savedRevision!);
        setSelection({ node: restored.selection?.at(-1), nodes: restored.selection }); setGenerated(null); clearError();
        setNotice('已重开保存的模型草稿，视角与已有撤销记录保留；可撤销本次重开。');
      }
    } catch (reason) { if (snapshot === currentRef.current.draft) reportError(reason); }
    finally { setBusyOperation(null); setBusy(false); }
  }
  async function generate() {
    if (busy || invalidFieldsRef.current.length) return;
    cancel(); setBusy(true); setBusyOperation('generate'); clearError();
    const snapshot = currentRef.current.draft;
    try {
      // The server validates this frontier before materializing hidden source
      // facts. Expanding every group here routes intermediate scenes on the UI
      // thread, even when an added module has missing inputs.
      const result = await api.generateDraft(snapshot);
      if (snapshot === currentRef.current.draft) setGenerated({ ...result, presentationDraft: snapshot });
    } catch (reason) { if (snapshot === currentRef.current.draft) reportError(reason); }
    finally { setBusyOperation(null); setBusy(false); }
  }
  async function browse() {
    if (busy || browsing.current || invalidFieldsRef.current.length) return;
    cancel(); clearError();
    const snapshot = currentRef.current.draft;
    const workspace: AuthoringWorkspace = { draft: snapshot, history: currentRef.current, storageRevision, savedRevision,
      selection: selectedIds, camera, viewport: cameraViewport.current, tool, sourceHistory: initial.sourceHistory, viewBaseline: initial.viewBaseline };
    if (browseBaseline && onReuseView && (sameGeneratedDraft(snapshot, browseBaseline) || sameSourceSemantics(snapshot, browseBaseline))) {
      setBusy(true); setBusyOperation('open');
      try { if (await onReuseView(workspace) !== false) return; } catch (reason) { reportError(reason); return; }
      finally { setBusy(false); setBusyOperation(null); }
    }
    browsing.current = true; setBusy(true); setBusyOperation('generate');
    try {
      const result = await api.generateDraft(snapshot);
      if (snapshot !== currentRef.current.draft) return;
      viewStateRef.current?.(workspace); setBusyOperation('open');
      await onOpen({ ...result, presentationDraft: snapshot });
    } catch (reason) { if (snapshot === currentRef.current.draft) reportError(reason, '无法切换到视图，编辑已保留：'); }
    finally { browsing.current = false; setBusyOperation(null); setBusy(false); }
  }
  async function toggleSourceHierarchy(nodeId: string) {
    const snapshot = currentRef.current.draft;
    if (!snapshot.sourceProvenance || busy) return;
    const node = snapshot.nodes.find(item => item.id === nodeId);
    if (!node) return;
    cancel(); setBusy(true); setBusyOperation('frontier'); clearError();
    try {
      const result = await reprojectSourceDraft(snapshot, nodeId, !node.presentation?.group);
      if (snapshot !== currentRef.current.draft) return;
      const next = changeDraft(currentRef.current, draft => { Object.assign(draft, result); });
      currentRef.current = next; setHistory(next); setGenerated(null);
      setSelection({ node: nodeId, nodes: [nodeId] });
      setNotice(node.presentation?.group ? '已折叠源码区域；内部编辑仍保留，展开后继续。' : '已展开源码区域；已有参数、连接与新增部件保留。');
    } catch (reason) { if (snapshot === currentRef.current.draft) reportError(reason); }
    finally { setBusy(false); setBusyOperation(null); }
  }
  async function editSourceRegion(nodeId: string) {
    const snapshot = currentRef.current.draft;
    if (busy || !snapshot.sourceProvenance) return;
    cancel(); setBusy(true); setBusyOperation('generate'); clearError();
    try {
      const region = await api.readSourceRegion(snapshot, nodeId);
      if (snapshot === currentRef.current.draft) setSourceEditor({ draft: snapshot, region });
    } catch (reason) { if (snapshot === currentRef.current.draft) reportError(reason); }
    finally { setBusy(false); setBusyOperation(null); }
  }
  async function openSourceRegion(canonicalId: string, restore = false) {
    const snapshot = currentRef.current.draft;
    if (busy || !snapshot.sourceProvenance) return;
    cancel(); setBusy(true); setBusyOperation('frontier'); clearError();
    try {
      const result = await (restore ? restoreSourceRegion(snapshot, canonicalId, catalogRef.current) : revealSourceRegion(snapshot, canonicalId));
      if (snapshot !== currentRef.current.draft) return;
      const next = changeDraft(currentRef.current, value => Object.assign(value, result));
      currentRef.current = next; setHistory(next); setGenerated(null);
      const id = next.draft.nodes.find(node => next.draft.sourceProvenance?.nodeRefs[node.id]?.nodeId === canonicalId)?.id;
      if (id) setSelection({ node: id, nodes: [id] });
      fit(next.draft);
      setNotice(restore ? '已恢复源码区域及内部结构；原参数、局部修改与未冲突连接保留，可撤销本次恢复。' : '已显示源码区域与直接内部结构；卡片右上角可继续逐层展开。');
    } catch (reason) { if (snapshot === currentRef.current.draft) reportError(reason); }
    finally { setBusy(false); setBusyOperation(null); }
  }
  function fit(documentToFit = currentRef.current.draft) {
    cancel(); const rect = svgRef.current?.getBoundingClientRect(); if (!rect) return;
    const currentCatalog = catalogRef.current;
    const routePoints = currentCatalog ? [...draftRoutes(documentToFit, currentCatalog).routes.flatMap(route => route.points), ...draftSourceRelations(documentToFit, currentCatalog).points] : [];
    const implicit = implicitDraftRootIds(documentToFit);
    if (currentCatalog) setCamera(fitDraftCamera({ ...documentToFit, nodes: documentToFit.nodes.filter(node => !implicit.has(node.id)) }, rect, currentCatalog, routePoints));
  }
  function arrange() { if (!catalogRef.current) return; const rect = svgRef.current?.getBoundingClientRect(); const next = apply(value => arrangeDraft(value, catalogRef.current!, rect)); if (next) { fit(next); setNotice('已按连接排版并适合画布；Ctrl+Z 可撤销排版。'); } }
  function zoom(factor: number) {
    cancel(); const rect = svgRef.current?.getBoundingClientRect(); if (!rect) return;
    setCamera(old => { const next = clampCanvasZoom(old.zoom * factor); return { zoom: next, x: rect.width / 2 - (rect.width / 2 - old.x) * next / old.zoom, y: rect.height / 2 - (rect.height / 2 - old.y) * next / old.zoom }; });
  }
  useEffect(() => {
    if (!cacheReady) return;
    const key = (event: KeyboardEvent) => {
      if ((event.target as Element)?.closest('input,textarea,select') || busy || generated || sourceEditor) return;
      if (event.key === 'Escape') { const pending = !!connection || gesture.current?.type === 'port'; cancel(); setSelection({}); if (pending) { clearError(); setNotice('已取消连线；选择输出端口即可重新连接。'); } }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); travel(event.shiftKey ? 'redo' : 'undo'); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); void save(); }
      if (event.key === 'Delete' || event.key === 'Backspace') { event.preventDefault(); deleteSelection(); }
      const move = { ArrowLeft: [-16, 0], ArrowRight: [16, 0], ArrowUp: [0, -16], ArrowDown: [0, 16] }[event.key];
      if (move && selectedIds.length) { event.preventDefault(); apply(value => moveDraftNodes(value, selectedIds, move[0], move[1])); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a') { event.preventDefault(); const ids = draft.nodes.map(node => node.id); setSelection({ node: ids.at(-1), nodes: ids }); }
    };
    const blur = () => cancel();
    window.addEventListener('keydown', key); window.addEventListener('blur', blur);
    return () => { window.removeEventListener('keydown', key); window.removeEventListener('blur', blur); };
  });
  function pointerDown(event: React.PointerEvent<SVGSVGElement>) {
    if (busy || gesture.current || ![0, 1].includes(event.button)) return;
    const target = event.target as Element;
    if (target.closest('[data-draft-source-toggle]')) return;
    const port = target.closest('[data-draft-port]'), node = target.closest('[data-draft-node]'), edge = target.closest('[data-draft-edge]');
    const base = currentRef.current.draft;
    if (tool === 'pan' || event.button === 1 || event.altKey) { setConnection(null); gesture.current = { type: 'pan', pointer: event.pointerId, clientX: event.clientX, clientY: event.clientY, camera, base, pan: beginCameraPan(camera, panInput(event)) }; }
    else if (port) {
      const endpoint = { nodeId: port.getAttribute('data-node')!, portId: port.getAttribute('data-draft-port')! };
      const module = catalog?.modules.find(item => item.kind === base.nodes.find(item => item.id === endpoint.nodeId)?.kind);
      if (portEditing) {
        setConnection(null); setSelection({ node: endpoint.nodeId, nodes: [endpoint.nodeId] });
        gesture.current = { type: 'port-layout', pointer: event.pointerId, clientX: event.clientX, clientY: event.clientY, camera, base, endpoint };
        event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId); return;
      }
      if (module?.ports.find(item => item.id === endpoint.portId)?.direction === 'in') {
        if (connection) connect(connection.endpoint, endpoint); else setNotice('先点击一个输出端口，再选择此输入端口。'); return;
      }
      const p = point(event.clientX, event.clientY); clearError(); setConnection({ endpoint, ...p });
      gesture.current = { type: 'port', pointer: event.pointerId, clientX: event.clientX, clientY: event.clientY, camera, base, endpoint };
    } else if (node) {
      setConnection(null); const nodeId = node.getAttribute('data-draft-node')!; const ids = selectDraftNode(selectedIds, nodeId, event.shiftKey || event.ctrlKey || event.metaKey); setSelection({ node: ids.at(-1), nodes: ids });
      gesture.current = { type: 'node', pointer: event.pointerId, clientX: event.clientX, clientY: event.clientY, camera, base, nodeId, nodeIds: ids };
    } else if (edge) { setSelection({ edge: edge.getAttribute('data-draft-edge')! }); setConnection(null); return; }
    else { setConnection(null); const additive = event.shiftKey || event.ctrlKey || event.metaKey; if (!additive) setSelection({}); const start = point(event.clientX, event.clientY); setMarquee({ ...start, width: 0, height: 0 }); gesture.current = { type: 'marquee', pointer: event.pointerId, clientX: event.clientX, clientY: event.clientY, camera, base, selection: selectedIds, additive }; }
    event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId);
  }
  function pointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const active = gesture.current;
    if (!active) { if (connection) setConnection(previous => previous && ({ ...previous, ...point(event.clientX, event.clientY) })); return; }
    if (active.pointer !== event.pointerId) return;
    const dx = event.clientX - active.clientX, dy = event.clientY - active.clientY;
    if (active.type === 'pan') { const next = cameraAtPanInput(active.pan!, panInput(event)); if (next) setCamera(next); }
    if (active.type === 'node') {
      const next = structuredClone(active.base); moveDraftNodes(next, active.nodeIds ?? [active.nodeId!], Math.round(dx / active.camera.zoom), Math.round(dy / active.camera.zoom)); setPreview(next);
    }
    if (active.type === 'port-layout' && catalog) {
      const next = structuredClone(active.base), node = next.nodes.find(node => node.id === active.endpoint!.nodeId)!;
      setDraftPortLayout(next, active.endpoint!, nearestPortLayout({ ...node.position, ...draftNodeSize(node, catalog), expanded: false, headerHeight: 0 }, point(event.clientX, event.clientY)));
      setPreview(next);
    }
    if (active.type === 'marquee') { const start = point(active.clientX, active.clientY), end = point(event.clientX, event.clientY); const box = { x: Math.min(start.x, end.x), y: Math.min(start.y, end.y), width: Math.abs(end.x - start.x), height: Math.abs(end.y - start.y) }; setMarquee(box); const ids = active.base.nodes.filter(node => { const size = catalog ? draftNodeSize(node, catalog) : { width: 176, height: 100 }; return !node.presentation?.group && node.position.x < box.x + box.width && node.position.x + size.width > box.x && node.position.y < box.y + box.height && node.position.y + size.height > box.y; }).map(node => node.id); const merged = [...new Set([...(active.additive ? active.selection ?? [] : []), ...ids])]; setSelection({ node: merged.at(-1), nodes: merged }); }
    if (active.type === 'port') setConnection(previous => previous && ({ ...previous, ...point(event.clientX, event.clientY) }));
  }
  function pointerUp(event: React.PointerEvent<SVGSVGElement>) {
    const active = gesture.current; if (!active || active.pointer !== event.pointerId) return;
    gesture.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (active.type === 'node') {
      const dx = Math.round((event.clientX - active.clientX) / active.camera.zoom), dy = Math.round((event.clientY - active.clientY) / active.camera.zoom);
      apply(value => moveDraftNodes(value, active.nodeIds ?? [active.nodeId!], dx, dy));
    } else if (active.type === 'port-layout' && catalog) {
      const node = active.base.nodes.find(node => node.id === active.endpoint!.nodeId)!;
      const layout = nearestPortLayout({ ...node.position, ...draftNodeSize(node, catalog), expanded: false, headerHeight: 0 }, point(event.clientX, event.clientY));
      apply(value => setDraftPortLayout(value, active.endpoint!, layout));
      setNotice('连接点已调整；关闭“移动连接点”可继续连线。');
    } else if (active.type === 'marquee') { setMarquee(null); } else if (active.type === 'pan') {
      const next = cameraAtPanInput(active.pan!, panInput(event)); if (next) setCamera(next);
    } else if (active.type === 'port') {
      const port = document.elementFromPoint(event.clientX, event.clientY)?.closest('[data-draft-port]');
      if (port && port.getAttribute('data-node') !== active.endpoint!.nodeId) connect(active.endpoint!, { nodeId: port.getAttribute('data-node')!, portId: port.getAttribute('data-draft-port')! });
      else setNotice('连接起点已选中；点击目标输入端口，Escape 取消。');
    }
  }
  function panInput(event: React.PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return { pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY, viewportX: rect.left, viewportY: rect.top };
  }
  const query = search.trim().toLowerCase();
  const paletteCategories = draftPaletteCategories(paletteCatalog);
  const activePaletteCategory = paletteCategories.some(category => category.id === paletteCategory) ? paletteCategory : '';
  const matches = query || paletteView === 'modules' ? filterDraftModules(paletteCatalog, query, activePaletteCategory) : [];
  const presetMatches = draftPresets.filter(preset => (!!query || paletteView === 'presets') && draftPresetMatches(preset, catalog, query));
  const groups = [...new Set(matches.map(module => module.category))];
  const connectionNode = draft.nodes.find(node => node.id === connection?.endpoint.nodeId), connectionModule = catalog?.modules.find(module => module.kind === connectionNode?.kind);
  const start = connection && connectionNode && connectionModule ? geometry.ports[connectionNode.id]?.[connection.endpoint.portId] ?? portPoint(connectionNode, connectionModule, connection.endpoint.portId, geometry.nodeFlows[connectionNode.id] ?? 'horizontal') : null;
  const sourceCovered = sourceCoveredEdgeIds(sourceRouting.relations);
  const presentedRoutes = geometry.routes.filter(route => !tensorEdgeCovered({ canonicalEdgeIds: draft.sourceProvenance?.edgeRefs[route.id] ?? [] }, sourceCovered));
  const blocked = presentedRoutes.filter(route => route.blockedBy.length);
  const hintNode = draft.nodes.find(node => node.id === portHint?.nodeId);
  const hintModule = catalog?.modules.find(module => module.kind === hintNode?.kind);
  const hintPort = hintModule?.ports.find(port => port.id === portHint?.portId);
  const hintBinding = hintPort?.direction === 'in' ? draft.edges.find(edge => edge.target.nodeId === hintNode?.id && edge.target.portId === hintPort.id) : undefined;
  const hintProducer = draft.nodes.find(node => node.id === hintBinding?.source.nodeId);
  const hintTensorNode = hintPort?.direction === 'in' ? hintBinding?.source.nodeId ?? '' : hintNode?.id ?? '';
  const hintTensorPort = hintPort?.direction === 'in' ? hintBinding?.source.portId ?? '' : hintPort?.id ?? '';
  const hintTensor = checked?.portTensors?.[hintTensorNode]?.[hintTensorPort] ?? checked?.tensors[hintTensorNode];
  const hintAnchor = hintNode && hintModule && hintPort ? geometry.ports[hintNode.id]?.[hintPort.id] ?? portPoint(hintNode, hintModule, hintPort.id, geometry.nodeFlows[hintNode.id] ?? 'horizontal') : null;
  const hintFlow = hintNode ? geometry.nodeFlows[hintNode.id] ?? 'horizontal' : 'horizontal';
  const hintScreenX = hintAnchor ? camera.x + hintAnchor.x * camera.zoom : 0;
  const hintScreenY = hintAnchor ? camera.y + hintAnchor.y * camera.zoom : 0;
  const hintNodeRect = hintNode && catalog ? { x: camera.x + hintNode.position.x * camera.zoom, y: camera.y + hintNode.position.y * camera.zoom, width: DRAFT_WIDTH * camera.zoom, height: draftNodeSize(hintNode, catalog).height * camera.zoom } : null;
  const hintNodeObstacles = catalog ? draft.nodes.map(node => ({ x: camera.x + node.position.x * camera.zoom, y: camera.y + node.position.y * camera.zoom, width: DRAFT_WIDTH * camera.zoom, height: draftNodeSize(node, catalog).height * camera.zoom })) : [];
  const hintPlacement = hintAnchor && hintNodeRect ? placeDraftTooltip({ port: { x: hintScreenX, y: hintScreenY }, node: hintNodeRect, direction: hintPort?.direction ?? 'out', flow: hintFlow }, { width: 230, height: 114 }, { width: viewportSize.width, height: viewportSize.height }, hintNodeObstacles) : undefined;
  const hintPosition = hintPlacement ? { left: hintPlacement.left, top: hintPlacement.top } : undefined;
  const hintLayoutKey = JSON.stringify([tool, portHint, hintNode?.label, hintProducer?.label, hintTensor, hintScreenX, hintScreenY, hintNodeRect, hintPosition, hintNodeObstacles, viewportSize.width, viewportSize.height]);
  useLayoutEffect(() => {
    const tooltip = hintRef.current, viewport = svgRef.current;
    if (!tooltip || !viewport || !hintNodeRect || !hintPort) return;
    const bounds = tooltip.getBoundingClientRect();
    const position = placeDraftTooltip({ port: { x: hintScreenX, y: hintScreenY }, node: hintNodeRect, direction: hintPort.direction, flow: hintFlow }, { width: bounds.width, height: bounds.height }, { width: viewport.clientWidth, height: viewport.clientHeight }, hintNodeObstacles);
    setMeasuredHint(previous => previous?.key === hintLayoutKey && previous.left === position.left && previous.top === position.top ? previous : { key: hintLayoutKey, left: position.left, top: position.top });
  }, [hintLayoutKey]);

  if (!cacheReady) return <div className="authoring-studio" aria-busy="true"><header className="authoring-header"><b>ArchCanvas</b><button onClick={onClose}>查看原始视图</button></header><p role="status">正在恢复模型草稿与编辑记录…</p></div>;
  return <div className="authoring-studio">
    <header className="authoring-header"><div className="authoring-brand"><b>ArchCanvas</b><span>MODEL ARCHITECTURE STUDIO</span></div><DraftTextInput ariaLabel="模型草稿名称" value={history.draft.title} disabled={busy} onCommit={title => apply(value => { value.title = title; })} /><div className="header-actions"><details className="workspace-menu"><summary>模型 <span>⌄</span></summary><div><button disabled={busy} onClick={startBlankDraft}>新建空白模型</button><button disabled={busy || !storageRevision} onClick={() => void reopen()}>重开已保存草稿</button><button disabled={busy || !draft.nodes.length || !!invalidFields.length} onClick={() => void generate()}><Icon name="code" size={15} />预览生成源码</button><button disabled={busy} onClick={onClose}>查看原始视图</button></div></details><WorkspaceModeSwitch mode="edit" disabled={busy || !catalog || !!invalidFields.length} onView={() => void browse()} onEdit={() => {}} /><span className="authoring-save-state">{dirty ? '有未保存编辑' : '草稿已保存'}</span><button disabled={busy || !catalog || !!invalidFields.length} onClick={() => void save()}><Icon name="save" size={15} />保存</button></div></header>
    <div className="authoring-body">
      <aside className="module-palette"><div className="palette-intro"><span className="eyebrow">MODULE LIBRARY</span><h2>常用模块 <small>{baseCatalog?.modules.length ?? 0}</small></h2><p>拖入画布，或点击添加。<br />输入 → 计算模块 → 输出</p><div className="palette-browse" role="group" aria-label="模块库浏览方式"><button aria-pressed={paletteView === 'modules'} onClick={() => { setPaletteView('modules'); setPaletteCategory(''); }}>基础模块 <span>{baseCatalog?.modules.length ?? 0}</span></button><button aria-pressed={paletteView === 'presets'} onClick={() => { setPaletteView('presets'); setPaletteCategory(''); }}>网络起点 <span>{draftPresets.length}</span></button></div><input aria-label="搜索模块" placeholder="名称、别名或参数，如 FC / padding" value={search} onChange={event => setSearch(event.target.value)} />{paletteView === 'modules' && <label className="palette-category">模块分类<select aria-label="筛选模块分类" disabled={!catalog} value={activePaletteCategory} onChange={event => setPaletteCategory(event.target.value)}><option value="">全部分类 · {baseCatalog?.modules.length ?? 0}</option>{paletteCategories.map(category => <option key={category.id} value={category.id}>{category.label} · {category.count}</option>)}</select></label>}<small className="palette-search-help">可按类别、英文别名或参数搜索；网络起点也按组成模块匹配。</small><button className="custom-module-launch" disabled={busy || !catalog} onClick={() => setCustomModuleOpen(true)}><Icon name="code" size={14} />源码自定义模块</button></div><div className="palette-list" key={query ? 'search' : paletteView}>{draft.sourceProvenance && <SourceStructureLibrary draft={draft} busy={busy} onFocus={focusDraftNode} onReveal={id => void openSourceRegion(id)} onRestore={id => void openSourceRegion(id, true)} />}{(!!query || !!activePaletteCategory) && <div className="palette-search-summary"><p role="status">{query ? '搜索结果' : '分类结果'}：基础模块 {matches.length}{activePaletteCategory && `（${draftPaletteCategoryLabel(activePaletteCategory)}）`}{query && ` · 网络起点 ${presetMatches.length}`}。</p><button onClick={() => { setSearch(''); setPaletteCategory(''); }}>重置筛选</button></div>}{!catalog ? <p role="status" className="palette-empty">正在加载模块库…</p> : !matches.length && !presetMatches.length && <div role="status" className="palette-empty"><b>没有找到匹配的模块或网络</b><p>{unsupportedPaletteMessage(query) ?? '尝试中文名称、英文别名或参数，如“卷积”、FC、padding 或 MLP；也可重置筛选。'}</p></div>}{!!presetMatches.length && <section className="preset-section" aria-label="网络起点"><h3>网络起点 <span>{presetMatches.length}</span></h3><p className="preset-intro">{draft.nodes.length ? '添加一个独立网络。' : '从完整网络开始搭建。'}所有基础模块与连线都可修改。</p>{presetMatches.map(preset => { const unavailable = draftPresetUnavailable(preset, catalog); return <button key={preset.id} aria-label={`添加 ${preset.label}`} className={`preset-card ${paletteDrag?.type === 'preset' && paletteDrag.id === preset.id ? 'dragging' : ''}`} disabled={busy || !!unavailable} draggable={!busy && !unavailable} onDragStart={event => startPaletteDrag(event, { type: 'preset', id: preset.id, label: preset.label })} onDragEnd={clearPaletteDrag} onClick={() => addPreset(preset)} title={unavailable ?? `${preset.description}；输入 ${preset.input}，输出 ${preset.output}`}><span className="preset-heading"><b>{preset.label}</b><Icon name="plus" size={13} /></span><span className="preset-description">{preset.description} · {preset.nodes.length} 模块</span><small>输入 {preset.input}<br />输出 {preset.output}</small><small className="preset-components">模块类型：{[...new Set(preset.nodes.map(node => node.kind))].join(' · ')}</small>{unavailable && <span className="preset-unavailable">{unavailable}</span>}</button>; })}<p className="preset-note">形状是可编辑的声明；生成前会静态检查，模型尚未执行。</p></section>}{!!query && !!matches.length && <h3 className="palette-results-heading">基础模块 · {matches.length}</h3>}{groups.map(group => <section key={group}><h3>{draftPaletteCategoryLabel(group)}</h3>{matches.filter(module => module.category === group).map(module => <button key={module.kind} aria-label={`添加 ${module.kind}`} className={`module-card ${paletteDrag?.type === 'module' && paletteDrag.id === module.kind ? 'dragging' : ''}`} disabled={busy} draggable={!busy} onDragStart={event => startPaletteDrag(event, { type: 'module', id: module.kind, label: `${module.kind} · ${module.label}` })} onDragEnd={clearPaletteDrag} onClick={() => add(module)} title={module.description}><span className={`module-dot kind-${module.category}`} /><span><b>{module.kind}</b><small>{module.label}</small></span><Icon name="plus" size={13} /></button>)}</section>)}</div><div className="palette-note">常用模型的无环草稿。参数和连线通过静态检查后，生成新模型。</div></aside>
      <main className="authoring-main"><div className="workspace-caption"><b>{history.draft.title}</b><span>MODEL ARCHITECTURE · 模型编辑</span>{!!implicitRoots.size && <button disabled={busy} onClick={() => { const id = [...implicitRoots][0]; setSelection({ node: id, nodes: [id] }); }}>模型层级</button>}</div>{draft.sourceProvenance && <div className="draft-help" role="status">搭建撤销 {history.past.length} · 重做 {history.future.length}；制图历史 {initial.sourceHistory?.past ?? 0} / {initial.sourceHistory?.future ?? 0} 在“视图”中继续。两处历史分别保留，撤销不会改写原始源码。</div>}<div className="authoring-toolbar"><button aria-pressed={tool === 'select'} onClick={() => { cancel(); setTool('select'); }}><Icon name="arrow" size={16} />选择</button><button aria-pressed={tool === 'pan'} onClick={() => { cancel(); setTool('pan'); }}><Icon name="hand" size={16} />平移</button><button aria-label="撤销草稿" disabled={busy || !history.past.length} onClick={() => travel('undo')}><Icon name="undo" size={16} /></button><button aria-label="重做草稿" disabled={busy || !history.future.length} onClick={() => travel('redo')}><Icon name="redo" size={16} /></button><button aria-pressed={portEditing} disabled={busy} onClick={() => { cancel(); setTool("select"); setPortEditing(value => !value); }}>移动连接点</button><button disabled={busy || !draft.nodes.length} onClick={arrange}>按连接排版</button><button disabled={busy || !catalog || !!invalidFields.length} onClick={() => void check()}>检查模型</button><button onClick={() => fit()}><Icon name="fit" size={16} />适合画布</button><div className="authoring-zoom"><button aria-label="草稿缩小" onClick={() => zoom(1 / 1.2)}>−</button><button aria-label="草稿缩放百分比" onClick={() => zoom(1 / camera.zoom)}>{Math.round(camera.zoom * 100)}%</button><button aria-label="草稿放大" onClick={() => zoom(1.2)}>+</button></div></div>
        {(geometry.overlaps.length > 0 || blocked.length > 0 || sourceRouting.diagnostics.length > 0) && <div className="draft-layout-warning" role="status">{geometry.overlaps.length ? `${geometry.overlaps.length} 组模块重叠。` : ''}{blocked.length ? `${blocked.length} 条连线无法避开模块。` : ''}{sourceRouting.diagnostics.length ? `${sourceRouting.diagnostics.length} 条源码依赖线无法避开模块。` : ''}可移动模块或使用“按连接排版”。</div>}
        <div className={`draft-viewport ${dropActive ? 'palette-drop-active' : ''}`} data-palette-drop-active={dropActive} onDragEnter={paletteDragOver} onDragOver={paletteDragOver} onDragLeave={paletteDragLeave} onDrop={paletteDrop}>
          {dropActive && <div className="draft-drop-hint" role="status"><b>松开添加 {paletteDrag?.label ?? '模块或网络起点'}</b><span>添加后可编辑参数和连线 · Ctrl+Z 撤销</span></div>}
          <svg ref={svgRef} aria-label="模型搭建画布" data-draft-camera={JSON.stringify(camera)} data-draft-selected={selectedIds.join(",")} data-draft-flow={geometry.flow} data-draft-text-scale={labelScale.toFixed(2)} className={tool === 'pan' ? 'draft-pan' : ''} onWheel={event => { event.preventDefault(); cancel(); const rect = event.currentTarget.getBoundingClientRect(), x = event.clientX - rect.left, y = event.clientY - rect.top; setCamera(old => { const zoom = clampCanvasZoom(old.zoom * Math.exp(-event.deltaY * .001)); return { zoom, x: x - (x - old.x) * zoom / old.zoom, y: y - (y - old.y) * zoom / old.zoom }; }); }} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={cancel} onLostPointerCapture={() => { if (gesture.current) cancel(); }}>
            <defs><pattern id="draft-grid" width={grid.spacing} height={grid.spacing} patternUnits="userSpaceOnUse" x={grid.x} y={grid.y}><circle cx="1" cy="1" r=".8" fill="#cedbd2" /></pattern><marker id="draft-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#628572" /></marker><marker id="draft-skip-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#a76d35" /></marker><marker id="draft-selected-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#c18543" /></marker></defs><rect width="100%" height="100%" fill="url(#draft-grid)" />
            <g transform={`translate(${camera.x} ${camera.y}) scale(${camera.zoom})`}>
              <defs><marker id="draft-source-arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto-start-reverse"><path d="M 1 1 L 9 5 L 1 9 Z" fill={SOURCE_RELATION_STROKE}/></marker></defs>
              {sourceRouting.relations.map(relation => <g key={relation.id} data-source-relation-id={relation.id} pointerEvents="none"><title>{SOURCE_RELATION_LABEL}</title><path d={relation.path} fill="none" stroke={relation.stroke} strokeWidth={relation.width} strokeDasharray={SOURCE_RELATION_DASH} markerEnd="url(#draft-source-arrow)"/></g>)}
              {presentedRoutes.map(route => <g key={route.id} data-draft-edge={route.id} data-draft-role={edgeRoles.get(route.id) ?? 'data'} className={`draft-edge ${edgeRoles.get(route.id) === 'residual' ? 'residual' : ''} ${selection.edge === route.id ? 'selected' : ''}`}><title>{edgeRoles.get(route.id) === 'residual' ? '跳连：跳过中间模块后相加' : '数据流'}</title><path d={route.path} fill="none" stroke="transparent" strokeWidth="14" /><path d={route.path} fill="none" strokeWidth="1.8" markerEnd={selection.edge === route.id ? 'url(#draft-selected-arrow)' : edgeRoles.get(route.id) === 'residual' ? 'url(#draft-skip-arrow)' : 'url(#draft-arrow)'} /></g>)}
              {draft.nodes.filter(node => !implicitRoots.has(node.id)).map(node => { const module = catalog?.modules.find(item => item.kind === node.kind); if (!module) return null; const size = draftNodeSize(node, catalog!); const compact = !!(node.presentation || node.visual) && size.height < 76; const capHeight = Math.min(36, Math.max(24, size.height - 2)); const sourceFact = sourceFacts.get(draft.sourceProvenance?.nodeRefs[node.id]?.nodeId ?? ''); const definitionId = !sourceFact?.children.length && typeof sourceFact?.parameters.definitionReference === 'string' && sourceFacts.get(sourceFact.parameters.definitionReference)?.children.length ? sourceFact.parameters.definitionReference : undefined; const expandable = !!sourceFact?.children.length || !!definitionId; const toggle = () => definitionId ? openSourceRegion(definitionId) : toggleSourceHierarchy(node.id); const titleWidth = Math.max(40, size.width - (expandable ? 56 : 26)); return <g key={node.id} data-draft-node={node.id} onDoubleClick={event => { if (expandable && !(event.target as Element).closest('[data-draft-port],[data-draft-source-toggle]')) { event.stopPropagation(); void toggle(); } }} transform={`translate(${node.position.x} ${node.position.y})`} className={`draft-node ${compact ? 'compact' : ''} ${selectedIds.includes(node.id) ? 'selected' : ''} ${node.presentation?.group ? 'source-group' : ''} ${feedback?.target?.nodeId === node.id ? 'has-error' : ''}`} data-draft-error={feedback?.target?.nodeId === node.id ? 'true' : undefined}><rect width={size.width} height={size.height} rx="9" style={{ fill: node.presentation?.group ? 'transparent' : node.visual?.fill ?? node.presentation?.fill, stroke: node.visual?.stroke ?? node.presentation?.stroke }} /><rect className="draft-node-cap" x="1" y="1" width={size.width - 2} height={capHeight} rx="8" /><text x="13" y="23" className="draft-node-title" style={{ fontSize: 13 * labelScale }}><title>{node.label}</title>{draftFittedText(node.label, 13 * labelScale, titleWidth)}</text>{(!compact || size.height >= 56) && <text x="13" y={Math.max(45, size.height - 8)} className="draft-node-kind" style={{ fontSize: compact ? 8.5 * labelScale : 10 * labelScale }}><title>{draftSourceKind(draft, node)}</title>{draftFittedText(draftSourceKind(draft, node), compact ? 9 * labelScale : 10 * labelScale, titleWidth, true)}</text>}{!compact && checked?.tensors[node.id] && <text x="13" y="49" className="draft-node-tensor" style={{ fontSize: 10 * labelScale }}><title>{draftTensorLabel(checked.tensors[node.id])}</title>{draftFittedText(`声明 [${checked.tensors[node.id].shape.join(",")}]`, 10 * labelScale, titleWidth, true)}</text>}{feedback?.target?.nodeId === node.id && <g className="draft-error-badge"><circle cx={Math.min(size.width - 16, 160)} cy="21" r="9" /><text x={Math.min(size.width - 16, 160)} y="25" textAnchor="middle">!</text></g>}{module.ports.map(port => {
                const anchor = geometry.ports[node.id]?.[port.id];
                const flow = anchor ? anchor.side === 'left' || anchor.side === 'right' ? 'horizontal' : 'vertical' : geometry.nodeFlows[node.id] ?? 'horizontal';
                const p = anchor ?? portPoint(node, module, port.id, flow), x = p.x - node.position.x, y = p.y - node.position.y;
                const presentation = draftPortPresentation(port, x, y, flow, draftPortSpacing(module, port.direction, flow), 9 * labelScale, compact, anchor?.side);
                const active = connection?.endpoint.nodeId === node.id && connection.endpoint.portId === port.id;
                return <g key={port.id} data-node={node.id} data-draft-port={port.id} data-draft-port-flow={flow} className={`draft-port ${port.direction} ${active ? 'active' : ''} ${feedback?.target?.nodeId === node.id && feedback.target.portId === port.id ? 'has-error' : ''}`} role="button" tabIndex={0} aria-pressed={active} aria-describedby={portHint?.nodeId === node.id && portHint.portId === port.id && tool !== 'pan' ? 'draft-port-tooltip' : undefined} aria-label={`${node.label} ${port.name} ${port.direction === 'in' ? '输入端口' : '输出端口'}`} onPointerEnter={() => setHoveredPort({ nodeId: node.id, portId: port.id })} onPointerLeave={() => setHoveredPort(null)} onFocus={() => { setHoveredPort(null); setFocusedPort({ nodeId: node.id, portId: port.id }); }} onBlur={() => setFocusedPort(null)} onKeyDown={event => {
                  if (event.key !== 'Enter' && event.key !== ' ') return;
                  event.preventDefault(); event.stopPropagation(); if (busy || tool === 'pan') return;
                  if (port.direction === 'out') { cancel(); clearError(); setFocusedPort({ nodeId: node.id, portId: port.id }); setConnection({ endpoint: { nodeId: node.id, portId: port.id }, ...p }); setNotice('连接起点已选中；点击目标输入端口，Escape 取消。'); }
                  else if (connection) connect(connection.endpoint, { nodeId: node.id, portId: port.id });
                  else setNotice('先点击一个输出端口，再选择此输入端口。');
                }}><rect className="draft-port-hit" x={presentation.hit.x} y={presentation.hit.y} width={presentation.hit.width} height={presentation.hit.height} rx="4" fill="transparent" stroke="none" pointerEvents="all" style={{ fill: 'transparent', stroke: 'none', filter: 'none' }} /><circle className="draft-port-dot" cx={x} cy={y} r="5" /><text x={presentation.labelX} y={presentation.labelY} textAnchor={presentation.textAnchor} pointerEvents={compact ? 'none' : undefined} style={{ fontSize: presentation.labelFontSize }}>{port.name}</text></g>;
              })}<rect data-draft-drag-handle={node.id} aria-label={`${node.label} 选择并拖动`} x="12" y="2" width={Math.max(1, size.width - (expandable ? 50 : 24))} height={Math.min(capHeight - 2, Math.max(16, size.height / 2))} fill="transparent" stroke="none" pointerEvents="all" style={{ fill: 'transparent', stroke: 'none', filter: 'none' }} />{expandable && <g data-draft-source-toggle={node.id} role="button" tabIndex={0} aria-label={`${node.presentation?.group ? '折叠' : '展开'} ${node.label} 内部结构`} aria-expanded={!!node.presentation?.group} onPointerDown={event => event.stopPropagation()} onClick={event => { event.stopPropagation(); void toggle(); }} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); event.stopPropagation(); void toggle(); } }} transform={`translate(${size.width - 29} 6)`}><rect width="23" height="23" rx="5"/><text x="11.5" y="16" textAnchor="middle">{node.presentation?.group ? '−' : '+'}</text></g>}</g>; })}
              {marquee && <rect className="draft-marquee" {...marquee} fill="#6e997b18" stroke="#608e6e" strokeWidth={1 / camera.zoom} pointerEvents="none" />}
              {start && connection && <path d={`M ${start.x} ${start.y} L ${connection.x} ${connection.y}`} stroke="#b8864e" strokeWidth="2" strokeDasharray="6 4" fill="none" pointerEvents="none" />}
            </g>
          </svg>{!!(geometry.routes.length || sourceRouting.relations.length) && <FloatingLegend scene={{ sourceRelations: sourceRouting.relations, legend: draft.sourceProvenance?.canvas.legendItems ?? [], edges: presentedRoutes.map(route => ({ id: route.id, role: edgeRoles.get(route.id) ?? 'data', stroke: edgeRoles.get(route.id) === 'residual' ? '#a76d35' : '#628572', width: 1.8, dashed: edgeRoles.get(route.id) === 'residual' })) }} />}{tool !== 'pan' && hintNode && hintPort && hintPosition && <div id="draft-port-tooltip" ref={hintRef} className="draft-port-tooltip" role="tooltip" style={{ ...(measuredHint?.key === hintLayoutKey ? { left: measuredHint.left, top: measuredHint.top } : hintPosition), maxHeight: Math.max(1, viewportSize.height - 24) }}><b>{hintNode.label} · {hintPort.name}</b><span>{hintPort.direction === 'in' ? '输入端口' : '输出端口'}{hintBinding && hintProducer ? ` · 来自 ${hintProducer.label}` : hintPort.direction === 'in' ? ' · 尚未连接' : ' · 可连接多个下游'}</span>{hintTensor ? <span>{draftTensorLabel(hintTensor)}</span> : <span>形状待检查 · 模型尚未执行</span>}<small>{portEditing ? '拖动连接点到模块边缘；自动走线会跟随更新。' : hintPort.direction === 'out' ? '点击或按 Enter 选择，再连接输入端口。' : connection ? '点击或按 Enter 连接；形状以静态检查为准。' : '先选择输出端口，再连接到这里。'}</small></div>}{!draft.nodes.length && <div className="draft-empty"><span>{draft.sourceProvenance ? '源码结构已保留，可从左侧恢复' : '从零搭建一个模型'}</span><h2>把第一个 Input 拖到这里</h2><p>再加入 Linear、激活函数与 Output。<br />也可以从左侧“网络起点”加入完整 MLP、CNN 或残差网络。</p><button disabled={!catalog} onClick={() => { const input = catalog?.modules.find(module => module.kind === 'Input'); if (input) add(input, { x: 80, y: 120 }); }}>添加输入</button></div>}
        </div><div className="draft-help">{portEditing && "连接点模式：拖动端口到任一边缘 · "}双击 / ＋− 展开收起 · Shift 连续选择 · 框选 / Ctrl+A 多选 · 拖动整体 · 滚轮缩放 · 中键/Alt 平移 · 输出端口 → 输入端口 · 方向键移动 16 · Delete 删除 · Escape 取消 · Ctrl+Z 撤销</div>
      </main>
      <aside className="draft-inspector"><span className="eyebrow">MODEL PROPERTIES</span>{selected && selectedModule ? <><h2>{draftSourceKind(draft, selected)}</h2>{selectedIds.length > 1 && <p>已选择 {selectedIds.length} 个部件；拖动或方向键可整体移动。</p>}{draft.sourceProvenance?.nodeRefs[selected.id] && <div className="draft-source-evidence"><b>源码编辑副本</b><p>保留完整源码、层级、共享和未知事实。此处结构编辑只影响独立草稿。</p><code>{draft.sourceProvenance.nodeRefs[selected.id].nodeId}</code><details><summary>原始参数与事实</summary><pre>{JSON.stringify(draft.sourceProvenance.architecture.nodes.find(node => node.id === draft.sourceProvenance?.nodeRefs[selected.id]?.nodeId)?.parameters, null, 2)}</pre></details><p>{draft.sourceProvenance.nodeRefs[selected.id].repeat && `重复 ${draft.sourceProvenance.nodeRefs[selected.id].repeat!.count} 次 · ${draft.sourceProvenance.nodeRefs[selected.id].repeat!.sharing}`} {draft.sourceProvenance.nodeRefs[selected.id].evidence === 'opaque' && '未知区域：可查看与调整展示；重连或替换需独立生成合同，源码保留模式不改写动态分支。'}</p></div>}{draft.sourceProvenance?.architecture.nodes.find(node => node.id === draft.sourceProvenance?.nodeRefs[selected.id]?.nodeId)?.children.length ? <button disabled={busy} onClick={() => void toggleSourceHierarchy(selected.id)}>{selected.presentation?.group ? '折叠此源码区域' : '展开此源码区域'}</button> : null}{onSourceOpen && sourceFacts.get(draft.sourceProvenance?.nodeRefs[selected.id]?.nodeId ?? '')?.source && <button disabled={busy || !!invalidFields.length} onClick={() => void editSourceRegion(selected.id)}><Icon name="code" size={14}/>编辑区域源码 / 重建内部</button>}{typeof sourceFacts.get(draft.sourceProvenance?.nodeRefs[selected.id]?.nodeId ?? '')?.parameters.definitionReference === 'string' && <button disabled={busy} onClick={() => void openSourceRegion(String(sourceFacts.get(draft.sourceProvenance?.nodeRefs[selected.id]?.nodeId ?? '')?.parameters.definitionReference))}>查看内部源码定义</button>}<label className="draft-field">显示名称<DraftTextInput ariaLabel="模块显示名称" value={selected.label} disabled={busy} onCommit={label => apply(value => { value.nodes.find(node => node.id === selected.id)!.label = label; })} /></label><div className="draft-param-fields">{selectedModule.parameters.map(parameter => <DraftField key={`${selected.id}:${parameter.name}`} kind={selected.kind} parameter={parameter} value={selected.parameters[parameter.name]} disabled={busy} error={feedback?.target?.nodeId === selected.id && feedback.target.parameter === parameter.name ? feedback.message : undefined} onValidity={invalid => fieldValidity(selected.id, parameter.name, invalid)} onDiscardInvalid={discardInvalidInput} onCommit={value => apply(next => { next.nodes.find(node => node.id === selected.id)!.parameters[parameter.name] = value; })} />)}</div><p className="draft-description">{selectedModule.description}</p><button disabled={busy} onClick={() => apply(value => { for (const port of selectedModule.ports) setDraftPortLayout(value, { nodeId: selected.id, portId: port.id }, null); })}>恢复自动连接点</button>{selected.kind === 'Linear' && <p className="draft-parameter-help">例如输入形状为 [1, 16] 时，in_features 应为 16；out_features 决定输出最后一维。</p>}<div className="draft-coordinate">{(['x', 'y'] as const).map(axis => <label key={axis}>{axis.toUpperCase()}<input aria-label={`模块 ${axis.toUpperCase()} 坐标`} type="number" value={selected.position[axis]} disabled={busy} onChange={event => { if (event.target.value && Number.isFinite(Number(event.target.value))) apply(value => { value.nodes.find(node => node.id === selected.id)!.position[axis] = Number(event.target.value); }); }} /></label>)}</div><button disabled={busy} onClick={deleteSelection}>删除模块及相连连线</button></> : selection.edge ? <><h2>张量连线</h2><p>此连线定义模块的输入来源。</p><button disabled={busy} onClick={deleteSelection}>删除连线</button></> : <><h2>每一步都在图上完成</h2><ol><li>拖入 Input，设置输入形状。</li><li>拖入常用模块，编辑参数。</li><li>连接端口，加入 Output。</li><li>保存草稿，生成模型与论文图。</li></ol><p>随时点击“检查模型”，查看缺少的连接与声明形状；完成后再生成。当前是静态建模，模型尚未执行。</p></>}<label className="check-field"><input type="checkbox" aria-label="保留未使用分支" checked={draft.allowUnusedNodes ?? false} disabled={busy} onChange={event => apply(value => { value.allowUnusedNodes = event.target.checked; })} />保留未使用分支</label><p className="field-help">重建源码中的独立分支时可启用；所有输入端口仍须连接，分支会写入新源码。</p><section className="draft-check" aria-label="模型静态检查"><h3>{checked ? checked.complete ? draft.sourceProvenance ? checked.generation ? checked.generation.supported ? checked.generation.topology === 'anchored-edits' ? '连接通过 · 定位结构可生成' : '连接通过 · 源码保留可生成' : '连接通过 · 源码生成受限' : '连接通过 · 生成需独立核对' : draft.customModules?.length ? '连接检查通过 · 自定义形状未知' : '静态检查通过' : `${checked.issues.length} 项待完成` : '检查当前结构'}</h3><p>{checked ? draft.sourceProvenance ? '保留源码事实；当前连接检查不推测未知形状，模型尚未执行。' : draft.customModules?.length ? '仅检查静态连接；自定义模块及下游输出形状未推测，模型尚未执行。' : '以下形状来自静态声明，模型尚未执行。' : '参数、模块或连接改变后需重新检查；移动和显示名称不影响声明形状。'}</p>{checked?.generation && <div className="source-generation-scope"><b>保留源码生成</b><p>根据源码锚点核对参数修改，以及有限的模块插入、删除、替换和重接，生成独立副本。原有分支、循环和未编辑语句保留；具体支持范围以下列检查为准，模型尚未执行。</p>{checked.generation.limitations.map((item, index) => <p key={index}>{item}</p>)}</div>}{selected && checked?.tensors[selected.id] && <div className="draft-checked-tensor">{draftTensorLabel(checked.tensors[selected.id])}</div>}{checked?.issues.map((issue, index) => { const targets = (issue.nodeId ? [issue.nodeId] : issue.nodeIds ?? []).filter(id => draft.nodes.filter(node => node.id === id).length === 1); return <div className="draft-check-issue" key={`${issue.code}:${index}`}><span>{issue.message}</span>{targets.map(id => <button key={id} onClick={() => { reportError(new ApiError(issue.technical ?? issue.message, 400, [{ ...issue, nodeId: id }])); }}>{`定位 ${draft.nodes.find(node => node.id === id)!.label}`}</button>)}</div>; })}<button disabled={busy || !catalog || !!invalidFields.length} onClick={() => void check()}>{checked ? '重新检查' : '检查模型'}</button></section><div className="draft-summary"><b>{draft.nodes.length}</b> 模块 <b>{draft.edges.length}</b> 连接</div></aside>
    </div><footer className={`authoring-status ${error ? 'error' : ''}`} role={error || invalidFields.length ? 'alert' : 'status'}>{busy ? ({ check: '正在检查模型…', save: '正在保存草稿…', reopen: '正在重开保存的草稿…', generate: '正在生成并核对模型…', open: '正在打开新工作副本…', frontier: '正在展开源码层级并保留草稿编辑…' }[busyOperation ?? 'check']) : invalidFields.length ? '参数输入尚未有效：请修正标记字段，或按 Escape 恢复上次有效值，再保存或生成。' : error || currentNotice}{!busy && error && feedback?.target && <button onClick={() => focusDraftNode(feedback.target!.nodeId)}>定位出错模块</button>}{!busy && error && feedback?.technical && <details><summary>技术详情</summary><span>{feedback.technical}</span></details>}</footer>
    {customModuleOpen && <CustomModuleDialog onClose={() => setCustomModuleOpen(false)} onInsert={insertCustomModule} />}
    {sourceEditor && <SourceRegionEditor value={sourceEditor} onClose={() => setSourceEditor(null)} onOpen={onSourceOpen} />}
    {generated && <div className="modal-backdrop"><section className="authoring-review" role="dialog" aria-modal="true" aria-label="生成的新模型"><div className="modal-heading"><div><span className="eyebrow">NEW MODEL</span><h2>模型已生成并静态核对</h2></div><button onClick={() => setGenerated(null)} disabled={busy}><Icon name="close" /></button></div><p>{generated.draft.sourceProvenance ? generated.verification.scope === 'source-preserved-literal-edit-copy' ? '原分支、循环和未编辑语句已保留在独立新副本；已核对参数修改及其余静态结构。未执行模型。' : generated.verification.scope === 'source-preserved-anchored-expression-edits' ? '已在独立副本中完成源码锚点处的有限结构修改，并核对新源码与模块绑定；原有分支、循环和未编辑语句保留。未执行模型。' : '原源码已保留在独立新副本，生成源码通过语法与静态分析检查；不声明数值等价或执行验证。' : '节点、端口、参数和连接已与新源码的分析结果核对。'}接下来可打开论文图、编辑样式并导出；模型尚未执行。</p><pre>{generated.source}</pre><div className="modal-actions"><button disabled={busy} onClick={() => setGenerated(null)}>继续搭建</button><button className="primary" disabled={busy} onClick={async () => { setBusy(true); setBusyOperation('open'); try { await onOpen(generated); } catch (reason) { reportError(reason); setBusyOperation(null); setBusy(false); } }}>创建新工作副本并打开论文图</button></div></section></div>}
  </div>;
}

function SourceRegionEditor({ value, onClose, onOpen }: { value: { draft: AuthoredDraft; region: SourceRegion };
  onClose: () => void; onOpen?: (architecture: Architecture) => Promise<void> }) {
  const { draft, region } = value;
  const [source, setSource] = useState(region.source);
  const [result, setResult] = useState<EditedSourceRegion | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const textarea = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => { if (textarea.current) textarea.current.scrollTop = Math.max(0, region.startLine - 4) * 20; }, [region]);
  async function analyze() {
    setBusy(true); setError('');
    try { setResult(await api.applySourceRegion(draft, region.regionId, region.baselineDigest, source)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }
  return <div className="modal-backdrop"><section className="custom-source-modal source-region-modal" role="dialog" aria-modal="true" aria-label="编辑模型区域源码">
    <div className="modal-heading"><div><span className="eyebrow">MODEL SOURCE</span><h2>编辑区域源码 / 重建内部</h2></div><button disabled={busy} aria-label="关闭区域源码编辑" onClick={onClose}><Icon name="close"/></button></div>
    <p><b>{region.path}</b> · 所选区域位于第 {region.startLine}–{region.endLine} 行。下方保留完整文件，可重建 if/else、循环及嵌套模块；已有可生成的草稿修改已包含。</p>
    <label className="custom-source-label" htmlFor="source-region-code">模型源码</label><textarea id="source-region-code" aria-label="区域所在完整源码" className="custom-source-editor" ref={textarea} value={source} disabled={busy} spellCheck={false} onChange={event => { setSource(event.target.value); setResult(null); setError(''); }}/>
    <p>静态检查后创建独立工作副本并重新解析层级。原始项目和当前草稿保留；模型不执行。</p>
    {error && <p role="alert" className="source-region-error">{error}</p>}
    {result && <div className="custom-contract" role="status"><b>新源码已通过语法与独立静态重分析</b><p>{result.architecture.nodes.length} 个结构对象 · {result.architecture.diagnostics.length} 条分析提示。可在新预览中展开，并继续进入编辑模式。</p><details><summary>查看此次修改前的源码</summary><pre>{region.source}</pre></details></div>}
    <div className="modal-actions"><button disabled={busy} onClick={onClose}>取消源码修改</button><button disabled={busy || source === region.source} onClick={() => { setSource(region.source); setResult(null); }}>恢复打开时源码</button><button disabled={busy || !source.trim()} onClick={() => void analyze()}>{busy ? '正在核对源码…' : '检查新源码'}</button>{result && onOpen && <button className="primary" disabled={busy} onClick={async () => { setBusy(true); setError(''); try { await onOpen(result.architecture); } catch (reason) { setError(String(reason)); setBusy(false); } }}>创建新工作副本并打开预览</button>}</div>
  </section></div>;
}

function SourceStructureLibrary({ draft, busy, onFocus, onReveal, onRestore }: { draft: AuthoredDraft; busy: boolean;
  onFocus: (id: string) => void; onReveal: (id: string) => void; onRestore: (id: string) => void }) {
  const [query, setQuery] = useState('');
  const entries = useMemo(() => sourceStructureEntries(draft), [draft]);
  const byId = new Map(entries.map(entry => [entry.id, entry]));
  const matches = filterSourceStructure(entries, query);
  const deleted = entries.filter(entry => entry.deleted && (!entry.parentId || !byId.get(entry.parentId)?.deleted));
  const row = (id: string, depth = 0): React.ReactNode => {
    const entry = byId.get(id); if (!entry || !matches.has(id)) return null;
    const children = entry.children.filter(child => matches.has(child));
    const body = <div className={`source-structure-entry ${entry.deleted ? 'deleted' : ''}`}>
      <span title={entry.source}><b>{entry.label}</b><small>{entry.kind}{entry.deleted ? ' · 已删除' : entry.draftId ? ' · 画布中' : ' · 未展开'}</small></span>
      <button disabled={busy} aria-label={`${entry.deleted ? '恢复' : '显示'}源码区域 ${entry.label}`}
        onClick={event => { event.preventDefault(); event.stopPropagation(); entry.deleted ? onRestore(entry.id) : entry.definitionId ? onReveal(entry.definitionId) : entry.draftId && !entry.children.length ? onFocus(entry.draftId) : onReveal(entry.id); }}>{entry.deleted ? '恢复' : entry.definitionId ? '定义' : '显示'}</button>
    </div>;
    return children.length ? <details key={id} className="source-structure-branch" open={query.trim() ? true : undefined} style={{ marginLeft: depth ? 8 : 0 }}><summary>{body}</summary>{children.map(child => row(child, depth + 1))}</details>
      : <div key={id} className="source-structure-leaf" style={{ marginLeft: depth ? 12 : 0 }}>{body}</div>;
  };
  return <details className="source-structure-library" open><summary>当前模型源码结构 <small>{entries.length}</small></summary>
    <p>逐层显示和编辑原模型内部；删除后可按原结构恢复，保存后仍保留。预设与自定义模块可继续添加。</p>
    <input aria-label="搜索当前模型源码结构" placeholder="查找分支、模块或源码路径" value={query} onChange={event => setQuery(event.target.value)}/>
    {!!deleted.length && <section aria-label="已删除的源码区域" className="source-structure-recovery"><h3>已删除 · 可恢复</h3>{deleted.map(entry => <button key={entry.id} disabled={busy} aria-label={`恢复已删除区域 ${entry.label}`} onClick={() => onRestore(entry.id)}>恢复 {entry.label}</button>)}</section>}
    <div className="source-structure-tree">{entries.filter(entry => !entry.parentId).map(entry => row(entry.id))}{!matches.size && <p>没有匹配的源码结构。</p>}</div>
  </details>;
}

function DraftTextInput({ ariaLabel, value, disabled, onCommit }: { ariaLabel: string; value: string; disabled: boolean; onCommit: (value: string) => void }) {
  const [text, setText] = useState(value);
  const [invalid, setInvalid] = useState(false);
  const errorId = useId();
  useEffect(() => { setText(value); setInvalid(false); }, [value]);
  function commit() {
    const next = text.trim();
    if (!next || next.length > 120 || /[\x00-\x1f]/.test(next)) { setInvalid(true); return; }
    setInvalid(false);
    if (next !== value) onCommit(next);
  }
  function restore() { setText(value); setInvalid(false); }
  return <><input aria-label={ariaLabel} aria-invalid={invalid} aria-describedby={invalid ? errorId : undefined} maxLength={120} value={text} disabled={disabled} onChange={event => { setText(event.target.value); }} onBlur={commit} onKeyDown={event => { if (event.key === 'Enter') event.currentTarget.blur(); if (event.key === 'Escape') restore(); }} />{invalid && <small id={errorId} role="alert">名称须为 1–120 个字符，不能含控制字符；按 Escape 恢复上次有效名称。</small>}</>;
}

function DraftField({ kind, parameter, value, disabled, error, onCommit, onValidity, onDiscardInvalid }: { kind: string; parameter: DraftParameter; value: DraftValue; disabled: boolean; error?: string; onCommit: (value: DraftValue) => void; onValidity: (invalid: boolean) => void; onDiscardInvalid: () => void }) {
  const display = () => Array.isArray(value) ? value.join(', ') : String(value);
  const [text, setText] = useState(display);
  const [invalid, setInvalid] = useState('');
  const effectiveValue = JSON.stringify(value);
  const invalidRef = useRef(false);
  const callbacks = useRef({ onValidity, onDiscardInvalid }); callbacks.current = { onValidity, onDiscardInvalid };
  const message = '请输入范围内的有效数值；数组用逗号分隔且不能留空。';
  function validity(bad: boolean) { invalidRef.current = bad; callbacks.current.onValidity(bad); setInvalid(bad ? message : ''); }
  useEffect(() => { if (invalidRef.current) callbacks.current.onDiscardInvalid(); setText(display()); validity(false); }, [effectiveValue]);
  useEffect(() => () => { callbacks.current.onValidity(false); if (invalidRef.current) callbacks.current.onDiscardInvalid(); }, []);
  function commit() {
    const next = parseDraftField(text, parameter);
    validity(next === null);
    if (next !== null && JSON.stringify(next) !== JSON.stringify(value)) onCommit(next);
  }
  function restore() { if (invalidRef.current) callbacks.current.onDiscardInvalid(); setText(display()); validity(false); }
  const errorId = `draft-parameter-${parameter.name}-error`, helpId = `draft-parameter-${parameter.name}-help`, help = invalid || error;
  const guidance = draftParameterHelp(kind, parameter.name);
  const describedBy = [guidance && helpId, help && errorId].filter(Boolean).join(' ') || undefined;
  return <label className={`draft-field ${help ? 'has-error' : ''}`} data-draft-parameter={parameter.name}><span>{guidance?.label ?? parameter.name}{guidance && <code className="draft-parameter-name">{parameter.name}</code>}</span>{parameter.type === 'boolean' ? <input type="checkbox" aria-label={parameter.name} aria-describedby={describedBy} checked={value === true} disabled={disabled} onChange={event => onCommit(event.target.checked)} /> : parameter.type === 'choice' ? <select aria-label={parameter.name} aria-describedby={describedBy} value={String(value)} disabled={disabled} onChange={event => onCommit(event.target.value)}>{parameter.options?.map(option => <option key={option} value={option}>{option}</option>)}</select> : <input aria-label={parameter.name} aria-invalid={!!help} aria-describedby={describedBy} inputMode={parameter.type === 'integer-array' ? 'text' : 'decimal'} value={text} disabled={disabled} onChange={event => { setText(event.target.value); validity(parseDraftField(event.target.value, parameter) === null); }} onBlur={commit} onKeyDown={event => { if (event.key === 'Enter') event.currentTarget.blur(); if (event.key === 'Escape') restore(); }} />}{guidance && <small id={helpId} className="draft-field-help">{guidance.description}{parameter.type === 'integer-array' && ' 填写逗号分隔的数字（如 1, 3），无需输入方括号。'}</small>}{help && <small id={errorId} role="alert">{help}</small>}</label>;
}
