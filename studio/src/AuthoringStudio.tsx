import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { api, ApiError } from './api';
import type { GeneratedDraft } from './api';
import { Icon } from './icons';
import { addDraftNode, arrangeDraft, blankDraft, changeDraft, connectDraft, DRAFT_WIDTH, draftModuleSize, draftNodeSize, draftPortSpacing, draftHistory, draftRoutes, nextDraftPosition, portPoint, removeDraftNode, travelDraft, sourceDraftCatalog, draftSourceKind, moveDraftNodes, selectDraftNode } from './authoring';
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
import { reprojectSourceDraft } from './sourceDraftFrontier';
import { canvasDotGrid, clampCanvasZoom } from './cameraProjection';
import { draftPaletteCategories, draftPaletteCategoryLabel, draftPresetMatches, filterDraftModules } from './draftPalette';
import { authoringCameraAtViewport, parseAuthoringWorkspace, reopenAuthoringWorkspace } from './sourceAuthoringSession';

const CACHE = 'archcanvas.authored-workspace.v1';
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
import type { CustomModulePreview } from './customModules';
type Gesture = { type: 'node' | 'pan' | 'port' | 'marquee'; pointer: number; clientX: number; clientY: number; camera: Camera; base: AuthoredDraft; pan?: CameraPan; nodeId?: string; nodeIds?: string[]; selection?: string[]; additive?: boolean; endpoint?: DraftEndpoint };
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
function restored() {
  try {
    const stored = parseAuthoringWorkspace(JSON.parse(localStorage.getItem(CACHE) ?? 'null'));
    if (stored) return stored;
  } catch { /* A damaged browser cache is never used as a source document. */ }
  return { draft: createBlank(), storageRevision: 0, savedRevision: -1 };
}

export function AuthoringStudio({ onClose, onOpen, initialWorkspace, onViewState, browseBaseline, onReuseView, onNewBlank }: { onClose: () => void; onOpen: (generated: GeneratedDraft) => Promise<void>; initialWorkspace?: AuthoringWorkspace; onViewState?: (workspace: AuthoringWorkspace) => void; browseBaseline?: AuthoredDraft; onReuseView?: (workspace: AuthoringWorkspace) => void; onNewBlank?: (workspace: AuthoringWorkspace) => void }) {
  const [initial] = useState(() => initialWorkspace ?? restored());
  const [history, setHistory] = useState(() => initial.history ?? draftHistory(initial.draft));
  const [baseCatalog, setBaseCatalog] = useState<DraftCatalog | null>(null);
  const [storageRevision, setStorageRevision] = useState(initial.storageRevision ?? 0);
  const [savedRevision, setSavedRevision] = useState(initial.savedRevision ?? -1);
  const [selection, setSelection] = useState<{ node?: string; nodes?: string[]; edge?: string }>(() => ({ node: initial.selection?.at(-1), nodes: initial.selection ?? [] }));
  const [camera, setCamera] = useState<Camera>(initial.camera ?? { x: 30, y: 30, zoom: 1 });
  const [preview, setPreview] = useState<AuthoredDraft | null>(null);
  const [connection, setConnection] = useState<{ endpoint: DraftEndpoint; x: number; y: number } | null>(null);
  const [tool, setTool] = useState<'select' | 'pan'>(initial.tool ?? 'select');
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
  const gesture = useRef<Gesture | null>(null);
  const currentRef = useRef(history); currentRef.current = history;
  const saving = useRef(false);
  const browsing = useRef(false);
  const invalidFieldsRef = useRef<string[]>([]);
  const draft = preview ?? history.draft;
  const implicitRoots = useMemo(() => implicitDraftRootIds(draft), [draft]);
  const catalog = useMemo(() => sourceDraftCatalog(history.draft, baseCatalog), [history.draft.sourceProvenance, history.draft.customModules, baseCatalog]);
  const paletteCatalog = useMemo(() => baseCatalog ? { ...baseCatalog, modules: [...baseCatalog.modules, ...(history.draft.customModules ?? []).map(customModuleCatalog)] } : null, [baseCatalog, history.draft.customModules]);
  const catalogRef = useRef(catalog); catalogRef.current = catalog;
  const selectedIds = selection.nodes ?? (selection.node ? [selection.node] : []);
  const grid = canvasDotGrid(camera);
  const viewStateRef = useRef(onViewState); viewStateRef.current = onViewState;
  const selected = draft.nodes.find(node => node.id === selection.node);
  const selectedModule = catalog?.modules.find(module => module.kind === selected?.kind);
  const geometry = useMemo(() => catalog ? draftRoutes(draft, catalog) : { routes: [], overlaps: [], flow: 'horizontal' as const, nodeFlows: {} as Record<string, DraftFlow> }, [draft, catalog]);
  const edgeRoles = useMemo(() => catalog ? draftEdgeRoles(draft, catalog) : new Map<string, 'data' | 'residual'>(), [draft, catalog]);
  const dirty = history.draft.revision !== savedRevision;
  const validationKey = useMemo(() => draftValidationKey(history.draft), [history.draft]);
  const checked = validation?.key === validationKey && !invalidFields.length ? validation.result : null;
  const currentNotice = checkNoticeKey && (checkNoticeKey !== validationKey || !checked) ? '草稿结构已改变；请重新检查声明形状与连接，模型尚未执行。' : notice;
  const labelScale = draftCanvasTextScale(camera.zoom);
  useEffect(() => { viewStateRef.current?.({ draft: history.draft, history, storageRevision, savedRevision, selection: selectedIds, camera, viewport: cameraViewport.current, tool, sourceHistory: initial.sourceHistory, viewBaseline: initial.viewBaseline }); }, [history, storageRevision, savedRevision, selection, camera, tool]);

  useEffect(() => {
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
  }, [initial.draft]);
  useEffect(() => {
    try { localStorage.setItem(CACHE, JSON.stringify({ draft: history.draft, history, storageRevision, savedRevision, selection: selectedIds, camera, viewport: cameraViewport.current, tool, viewBaseline: initial.viewBaseline })); }
    catch { setError('浏览器未能保留草稿；请使用“保存草稿”。'); }
  }, [history, storageRevision, savedRevision, selectedIds, camera, tool]);

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
  }, []);

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
  function travel(action: 'undo' | 'redo') { cancel(); const next = travelDraft(currentRef.current, action); currentRef.current = next; setHistory(next); setGenerated(null); clearError(); }
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
    if (selectedIds.length) { if (apply(value => { for (const id of selectedIds) removeDraftNode(value, id); })) setNotice('已删除模块及相连连线；请重新检查当前结构。'); }
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
      if (receiveValidation(snapshot, result)) { setNotice(result.complete ? result.draft.sourceProvenance ? '连接检查通过；源码来源已保留，形状与模型执行尚未验证。' : '静态检查通过；声明形状与连接相容，模型尚未执行。' : `还有 ${result.issues.length} 项需要完成；可在右侧定位并继续搭建。`); setCheckNoticeKey(draftValidationKey(snapshot)); }
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
      const materialized = snapshot.sourceProvenance ? await reprojectSourceDraft(snapshot) : snapshot;
      const result = await api.generateDraft(materialized);
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
    if (browseBaseline && onReuseView && sameGeneratedDraft(snapshot, browseBaseline)) {
      try { onReuseView(workspace); } catch (reason) { reportError(reason); }
      return;
    }
    browsing.current = true; setBusy(true); setBusyOperation('generate');
    try {
      const materialized = snapshot.sourceProvenance ? await reprojectSourceDraft(snapshot) : snapshot;
      const result = await api.generateDraft(materialized);
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
  function fit(documentToFit = currentRef.current.draft) {
    cancel(); const rect = svgRef.current?.getBoundingClientRect(); if (!rect) return;
    const currentCatalog = catalogRef.current;
    const routePoints = currentCatalog ? draftRoutes(documentToFit, currentCatalog).routes.flatMap(route => route.points) : [];
    const implicit = implicitDraftRootIds(documentToFit);
    if (currentCatalog) setCamera(fitDraftCamera({ ...documentToFit, nodes: documentToFit.nodes.filter(node => !implicit.has(node.id)) }, rect, currentCatalog, routePoints));
  }
  function arrange() { if (!catalogRef.current) return; const rect = svgRef.current?.getBoundingClientRect(); const next = apply(value => arrangeDraft(value, catalogRef.current!, rect)); if (next) { fit(next); setNotice('已按连接排版并适合画布；Ctrl+Z 可撤销排版。'); } }
  function zoom(factor: number) {
    cancel(); const rect = svgRef.current?.getBoundingClientRect(); if (!rect) return;
    setCamera(old => { const next = clampCanvasZoom(old.zoom * factor); return { zoom: next, x: rect.width / 2 - (rect.width / 2 - old.x) * next / old.zoom, y: rect.height / 2 - (rect.height / 2 - old.y) * next / old.zoom }; });
  }
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.target as Element)?.closest('input,textarea,select') || busy || generated) return;
      if (event.key === 'Escape') { const pending = !!connection || gesture.current?.type === 'port'; cancel(); setSelection({}); if (pending) { clearError(); setNotice('已取消连线；选择输出端口即可重新连接。'); } }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); travel(event.shiftKey ? 'redo' : 'undo'); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); void save(); }
      if (event.key === 'Delete' || event.key === 'Backspace') { event.preventDefault(); deleteSelection(); }
      const move = { ArrowLeft: [-16, 0], ArrowRight: [16, 0], ArrowUp: [0, -16], ArrowDown: [0, 16] }[event.key];
      if (move && selectedIds.length) { event.preventDefault(); apply(value => moveDraftNodes(value, selectedIds, move[0], move[1])); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a') { event.preventDefault(); const ids = draft.nodes.filter(node => !node.presentation?.group).map(node => node.id); setSelection({ node: ids.at(-1), nodes: ids }); }
    };
    const blur = () => cancel();
    window.addEventListener('keydown', key); window.addEventListener('blur', blur);
    return () => { window.removeEventListener('keydown', key); window.removeEventListener('blur', blur); };
  });
  function pointerDown(event: React.PointerEvent<SVGSVGElement>) {
    if (busy || gesture.current || ![0, 1].includes(event.button)) return;
    const target = event.target as Element, port = target.closest('[data-draft-port]'), node = target.closest('[data-draft-node]'), edge = target.closest('[data-draft-edge]');
    const base = currentRef.current.draft;
    if (tool === 'pan' || event.button === 1 || event.altKey) { setConnection(null); gesture.current = { type: 'pan', pointer: event.pointerId, clientX: event.clientX, clientY: event.clientY, camera, base, pan: beginCameraPan(camera, panInput(event)) }; }
    else if (port) {
      const endpoint = { nodeId: port.getAttribute('data-node')!, portId: port.getAttribute('data-draft-port')! };
      const module = catalog?.modules.find(item => item.kind === base.nodes.find(item => item.id === endpoint.nodeId)?.kind);
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
  const start = connection && connectionNode && connectionModule ? portPoint(connectionNode, connectionModule, connection.endpoint.portId, geometry.nodeFlows[connectionNode.id] ?? 'horizontal') : null;
  const blocked = geometry.routes.filter(route => route.blockedBy.length);
  const hintNode = draft.nodes.find(node => node.id === portHint?.nodeId);
  const hintModule = catalog?.modules.find(module => module.kind === hintNode?.kind);
  const hintPort = hintModule?.ports.find(port => port.id === portHint?.portId);
  const hintBinding = hintPort?.direction === 'in' ? draft.edges.find(edge => edge.target.nodeId === hintNode?.id && edge.target.portId === hintPort.id) : undefined;
  const hintProducer = draft.nodes.find(node => node.id === hintBinding?.source.nodeId);
  const hintTensorNode = hintPort?.direction === 'in' ? hintBinding?.source.nodeId ?? '' : hintNode?.id ?? '';
  const hintTensorPort = hintPort?.direction === 'in' ? hintBinding?.source.portId ?? '' : hintPort?.id ?? '';
  const hintTensor = checked?.portTensors?.[hintTensorNode]?.[hintTensorPort] ?? checked?.tensors[hintTensorNode];
  const hintAnchor = hintNode && hintModule && hintPort ? portPoint(hintNode, hintModule, hintPort.id, geometry.nodeFlows[hintNode.id] ?? 'horizontal') : null;
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

  return <div className="authoring-studio">
    <header className="authoring-header"><div className="authoring-brand"><b>ArchCanvas</b><span>MODEL ARCHITECTURE STUDIO</span></div><DraftTextInput ariaLabel="模型草稿名称" value={history.draft.title} disabled={busy} onCommit={title => apply(value => { value.title = title; })} /><div className="header-actions"><details className="workspace-menu"><summary>模型 <span>⌄</span></summary><div><button disabled={busy} onClick={startBlankDraft}>新建空白模型</button><button disabled={busy || !storageRevision} onClick={() => void reopen()}>重开已保存草稿</button><button disabled={busy || !draft.nodes.length || !!invalidFields.length} onClick={() => void generate()}><Icon name="code" size={15} />预览生成源码</button><button disabled={busy} onClick={onClose}>查看原始视图</button></div></details><WorkspaceModeSwitch mode="edit" disabled={busy || !catalog || !!invalidFields.length} onView={() => void browse()} onEdit={() => {}} /><span className="authoring-save-state">{dirty ? '有未保存编辑' : '草稿已保存'}</span><button disabled={busy || !catalog || !!invalidFields.length} onClick={() => void save()}><Icon name="save" size={15} />保存</button></div></header>
    <div className="authoring-body">
      <aside className="module-palette"><div className="palette-intro"><span className="eyebrow">MODULE LIBRARY</span><h2>常用模块 <small>{baseCatalog?.modules.length ?? 0}</small></h2><p>拖入画布，或点击添加。<br />输入 → 计算模块 → 输出</p><div className="palette-browse" role="group" aria-label="模块库浏览方式"><button aria-pressed={paletteView === 'modules'} onClick={() => { setPaletteView('modules'); setPaletteCategory(''); }}>基础模块 <span>{baseCatalog?.modules.length ?? 0}</span></button><button aria-pressed={paletteView === 'presets'} onClick={() => { setPaletteView('presets'); setPaletteCategory(''); }}>网络起点 <span>{draftPresets.length}</span></button></div><input aria-label="搜索模块" placeholder="名称、别名或参数，如 FC / padding" value={search} onChange={event => setSearch(event.target.value)} />{paletteView === 'modules' && <label className="palette-category">模块分类<select aria-label="筛选模块分类" disabled={!catalog} value={activePaletteCategory} onChange={event => setPaletteCategory(event.target.value)}><option value="">全部分类 · {baseCatalog?.modules.length ?? 0}</option>{paletteCategories.map(category => <option key={category.id} value={category.id}>{category.label} · {category.count}</option>)}</select></label>}<small className="palette-search-help">可按类别、英文别名或参数搜索；网络起点也按组成模块匹配。</small><button className="custom-module-launch" disabled={busy || !catalog} onClick={() => setCustomModuleOpen(true)}><Icon name="code" size={14} />源码自定义模块</button></div><div className="palette-list" key={query ? 'search' : paletteView}>{(!!query || !!activePaletteCategory) && <div className="palette-search-summary"><p role="status">{query ? '搜索结果' : '分类结果'}：基础模块 {matches.length}{activePaletteCategory && `（${draftPaletteCategoryLabel(activePaletteCategory)}）`}{query && ` · 网络起点 ${presetMatches.length}`}。</p><button onClick={() => { setSearch(''); setPaletteCategory(''); }}>重置筛选</button></div>}{!catalog ? <p role="status" className="palette-empty">正在加载模块库…</p> : !matches.length && !presetMatches.length && <div role="status" className="palette-empty"><b>没有找到匹配的模块或网络</b><p>{unsupportedPaletteMessage(query) ?? '尝试中文名称、英文别名或参数，如“卷积”、FC、padding 或 MLP；也可重置筛选。'}</p></div>}{!!presetMatches.length && <section className="preset-section" aria-label="网络起点"><h3>网络起点 <span>{presetMatches.length}</span></h3><p className="preset-intro">{draft.nodes.length ? '添加一个独立网络。' : '从完整网络开始搭建。'}所有基础模块与连线都可修改。</p>{presetMatches.map(preset => { const unavailable = draftPresetUnavailable(preset, catalog); return <button key={preset.id} aria-label={`添加 ${preset.label}`} className={`preset-card ${paletteDrag?.type === 'preset' && paletteDrag.id === preset.id ? 'dragging' : ''}`} disabled={busy || !!unavailable} draggable={!busy && !unavailable} onDragStart={event => startPaletteDrag(event, { type: 'preset', id: preset.id, label: preset.label })} onDragEnd={clearPaletteDrag} onClick={() => addPreset(preset)} title={unavailable ?? `${preset.description}；输入 ${preset.input}，输出 ${preset.output}`}><span className="preset-heading"><b>{preset.label}</b><Icon name="plus" size={13} /></span><span className="preset-description">{preset.description} · {preset.nodes.length} 模块</span><small>输入 {preset.input}<br />输出 {preset.output}</small><small className="preset-components">模块类型：{[...new Set(preset.nodes.map(node => node.kind))].join(' · ')}</small>{unavailable && <span className="preset-unavailable">{unavailable}</span>}</button>; })}<p className="preset-note">形状是可编辑的声明；生成前会静态检查，模型尚未执行。</p></section>}{!!query && !!matches.length && <h3 className="palette-results-heading">基础模块 · {matches.length}</h3>}{groups.map(group => <section key={group}><h3>{draftPaletteCategoryLabel(group)}</h3>{matches.filter(module => module.category === group).map(module => <button key={module.kind} aria-label={`添加 ${module.kind}`} className={`module-card ${paletteDrag?.type === 'module' && paletteDrag.id === module.kind ? 'dragging' : ''}`} disabled={busy} draggable={!busy} onDragStart={event => startPaletteDrag(event, { type: 'module', id: module.kind, label: `${module.kind} · ${module.label}` })} onDragEnd={clearPaletteDrag} onClick={() => add(module)} title={module.description}><span className={`module-dot kind-${module.category}`} /><span><b>{module.kind}</b><small>{module.label}</small></span><Icon name="plus" size={13} /></button>)}</section>)}</div><div className="palette-note">常用模型的无环草稿。参数和连线通过静态检查后，生成新模型。</div></aside>
      <main className="authoring-main"><div className="workspace-caption"><b>{history.draft.title}</b><span>MODEL ARCHITECTURE · 模型编辑</span>{!!implicitRoots.size && <button disabled={busy} onClick={() => { const id = [...implicitRoots][0]; setSelection({ node: id, nodes: [id] }); }}>模型层级</button>}</div>{draft.sourceProvenance && <div className="draft-help" role="status">搭建撤销 {history.past.length} · 重做 {history.future.length}；制图历史 {initial.sourceHistory?.past ?? 0} / {initial.sourceHistory?.future ?? 0} 在“视图”中继续。两处历史分别保留，撤销不会改写原始源码。</div>}<div className="authoring-toolbar"><button aria-pressed={tool === 'select'} onClick={() => { cancel(); setTool('select'); }}><Icon name="arrow" size={16} />选择</button><button aria-pressed={tool === 'pan'} onClick={() => { cancel(); setTool('pan'); }}><Icon name="hand" size={16} />平移</button><button aria-label="撤销草稿" disabled={busy || !history.past.length} onClick={() => travel('undo')}><Icon name="undo" size={16} /></button><button aria-label="重做草稿" disabled={busy || !history.future.length} onClick={() => travel('redo')}><Icon name="redo" size={16} /></button><button disabled={busy || !draft.nodes.length} onClick={arrange}>按连接排版</button><button disabled={busy || !catalog || !!invalidFields.length} onClick={() => void check()}>检查模型</button><button onClick={() => fit()}><Icon name="fit" size={16} />适合画布</button><div className="authoring-zoom"><button aria-label="草稿缩小" onClick={() => zoom(1 / 1.2)}>−</button><button aria-label="草稿缩放百分比" onClick={() => zoom(1 / camera.zoom)}>{Math.round(camera.zoom * 100)}%</button><button aria-label="草稿放大" onClick={() => zoom(1.2)}>+</button></div></div>
        {(geometry.overlaps.length > 0 || blocked.length > 0) && <div className="draft-layout-warning" role="status">{geometry.overlaps.length ? `${geometry.overlaps.length} 组模块重叠。` : ''}{blocked.length ? `${blocked.length} 条连线无法避开模块。` : ''}可移动模块或使用“按连接排版”。</div>}
        <div className={`draft-viewport ${dropActive ? 'palette-drop-active' : ''}`} data-palette-drop-active={dropActive} onDragEnter={paletteDragOver} onDragOver={paletteDragOver} onDragLeave={paletteDragLeave} onDrop={paletteDrop}>
          {dropActive && <div className="draft-drop-hint" role="status"><b>松开添加 {paletteDrag?.label ?? '模块或网络起点'}</b><span>添加后可编辑参数和连线 · Ctrl+Z 撤销</span></div>}
          <svg ref={svgRef} aria-label="模型搭建画布" data-draft-camera={JSON.stringify(camera)} data-draft-selected={selectedIds.join(",")} data-draft-flow={geometry.flow} data-draft-text-scale={labelScale.toFixed(2)} className={tool === 'pan' ? 'draft-pan' : ''} onWheel={event => { event.preventDefault(); cancel(); const rect = event.currentTarget.getBoundingClientRect(), x = event.clientX - rect.left, y = event.clientY - rect.top; setCamera(old => { const zoom = clampCanvasZoom(old.zoom * Math.exp(-event.deltaY * .001)); return { zoom, x: x - (x - old.x) * zoom / old.zoom, y: y - (y - old.y) * zoom / old.zoom }; }); }} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={cancel} onLostPointerCapture={() => { if (gesture.current) cancel(); }}>
            <defs><pattern id="draft-grid" width={grid.spacing} height={grid.spacing} patternUnits="userSpaceOnUse" x={grid.x} y={grid.y}><circle cx="1" cy="1" r=".8" fill="#cedbd2" /></pattern><marker id="draft-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#628572" /></marker><marker id="draft-skip-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#a76d35" /></marker><marker id="draft-selected-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#c18543" /></marker></defs><rect width="100%" height="100%" fill="url(#draft-grid)" />
            <g transform={`translate(${camera.x} ${camera.y}) scale(${camera.zoom})`}>
              {geometry.routes.map(route => <g key={route.id} data-draft-edge={route.id} data-draft-role={edgeRoles.get(route.id) ?? 'data'} className={`draft-edge ${edgeRoles.get(route.id) === 'residual' ? 'residual' : ''} ${selection.edge === route.id ? 'selected' : ''}`}><title>{edgeRoles.get(route.id) === 'residual' ? '跳连：跳过中间模块后相加' : '数据流'}</title><path d={route.path} fill="none" stroke="transparent" strokeWidth="14" /><path d={route.path} fill="none" strokeWidth="1.8" markerEnd={selection.edge === route.id ? 'url(#draft-selected-arrow)' : edgeRoles.get(route.id) === 'residual' ? 'url(#draft-skip-arrow)' : 'url(#draft-arrow)'} /></g>)}
              {draft.nodes.filter(node => !implicitRoots.has(node.id)).map(node => { const module = catalog?.modules.find(item => item.kind === node.kind); if (!module) return null; const size = draftNodeSize(node, catalog!); const compact = !!(node.presentation || node.visual) && size.height < 76; const capHeight = Math.min(36, Math.max(24, size.height - 2)); const titleWidth = Math.max(40, size.width - 26); return <g key={node.id} data-draft-node={node.id} transform={`translate(${node.position.x} ${node.position.y})`} className={`draft-node ${compact ? 'compact' : ''} ${selectedIds.includes(node.id) ? 'selected' : ''} ${node.presentation?.group ? 'source-group' : ''} ${feedback?.target?.nodeId === node.id ? 'has-error' : ''}`} data-draft-error={feedback?.target?.nodeId === node.id ? 'true' : undefined}><rect width={size.width} height={size.height} rx="9" style={{ fill: node.presentation?.group ? 'transparent' : node.visual?.fill ?? node.presentation?.fill, stroke: node.visual?.stroke ?? node.presentation?.stroke }} /><rect className="draft-node-cap" x="1" y="1" width={size.width - 2} height={capHeight} rx="8" /><text x="13" y="23" className="draft-node-title" style={{ fontSize: 13 * labelScale }}><title>{node.label}</title>{draftFittedText(node.label, 13 * labelScale, titleWidth)}</text>{(!compact || size.height >= 56) && <text x="13" y={Math.max(45, size.height - 8)} className="draft-node-kind" style={{ fontSize: compact ? 8.5 * labelScale : 10 * labelScale }}><title>{draftSourceKind(draft, node)}</title>{draftFittedText(draftSourceKind(draft, node), compact ? 9 * labelScale : 10 * labelScale, titleWidth, true)}</text>}{!compact && checked?.tensors[node.id] && <text x="13" y="49" className="draft-node-tensor" style={{ fontSize: 10 * labelScale }}><title>{draftTensorLabel(checked.tensors[node.id])}</title>{draftFittedText(`声明 [${checked.tensors[node.id].shape.join(",")}]`, 10 * labelScale, titleWidth, true)}</text>}{feedback?.target?.nodeId === node.id && <g className="draft-error-badge"><circle cx={Math.min(size.width - 16, 160)} cy="21" r="9" /><text x={Math.min(size.width - 16, 160)} y="25" textAnchor="middle">!</text></g>}{module.ports.map(port => {
                const flow = geometry.nodeFlows[node.id] ?? 'horizontal';
                const p = portPoint(node, module, port.id, flow), x = p.x - node.position.x, y = p.y - node.position.y;
                const presentation = draftPortPresentation(port, x, y, flow, draftPortSpacing(module, port.direction, flow), 9 * labelScale, compact);
                const active = connection?.endpoint.nodeId === node.id && connection.endpoint.portId === port.id;
                return <g key={port.id} data-node={node.id} data-draft-port={port.id} data-draft-port-flow={flow} className={`draft-port ${port.direction} ${active ? 'active' : ''} ${feedback?.target?.nodeId === node.id && feedback.target.portId === port.id ? 'has-error' : ''}`} role="button" tabIndex={0} aria-pressed={active} aria-describedby={portHint?.nodeId === node.id && portHint.portId === port.id && tool !== 'pan' ? 'draft-port-tooltip' : undefined} aria-label={`${node.label} ${port.name} ${port.direction === 'in' ? '输入端口' : '输出端口'}`} onPointerEnter={() => setHoveredPort({ nodeId: node.id, portId: port.id })} onPointerLeave={() => setHoveredPort(null)} onFocus={() => { setHoveredPort(null); setFocusedPort({ nodeId: node.id, portId: port.id }); }} onBlur={() => setFocusedPort(null)} onKeyDown={event => {
                  if (event.key !== 'Enter' && event.key !== ' ') return;
                  event.preventDefault(); event.stopPropagation(); if (busy || tool === 'pan') return;
                  if (port.direction === 'out') { cancel(); clearError(); setFocusedPort({ nodeId: node.id, portId: port.id }); setConnection({ endpoint: { nodeId: node.id, portId: port.id }, ...p }); setNotice('连接起点已选中；点击目标输入端口，Escape 取消。'); }
                  else if (connection) connect(connection.endpoint, { nodeId: node.id, portId: port.id });
                  else setNotice('先点击一个输出端口，再选择此输入端口。');
                }}><rect className="draft-port-hit" x={presentation.hit.x} y={presentation.hit.y} width={presentation.hit.width} height={presentation.hit.height} rx="4" fill="transparent" stroke="none" pointerEvents="all" style={{ fill: 'transparent', stroke: 'none', filter: 'none' }} /><circle className="draft-port-dot" cx={x} cy={y} r="5" /><text x={presentation.labelX} y={presentation.labelY} textAnchor={presentation.textAnchor} pointerEvents={compact ? 'none' : undefined} style={{ fontSize: presentation.labelFontSize }}>{port.name}</text></g>;
              })}<rect data-draft-drag-handle={node.id} aria-label={`${node.label} 选择并拖动`} x="12" y="2" width={Math.max(1, size.width - 24)} height={Math.min(capHeight - 2, Math.max(16, size.height / 2))} fill="transparent" stroke="none" pointerEvents="all" style={{ fill: 'transparent', stroke: 'none', filter: 'none' }} /></g>; })}
              {marquee && <rect className="draft-marquee" {...marquee} fill="#6e997b18" stroke="#608e6e" strokeWidth={1 / camera.zoom} pointerEvents="none" />}
              {start && connection && <path d={`M ${start.x} ${start.y} L ${connection.x} ${connection.y}`} stroke="#b8864e" strokeWidth="2" strokeDasharray="6 4" fill="none" pointerEvents="none" />}
            </g>
          </svg>{!!geometry.routes.length && <FloatingLegend scene={{ legend: draft.sourceProvenance?.canvas.legendItems ?? [], edges: geometry.routes.map(route => ({ id: route.id, role: edgeRoles.get(route.id) ?? 'data', stroke: edgeRoles.get(route.id) === 'residual' ? '#a76d35' : '#628572', width: 1.8, dashed: edgeRoles.get(route.id) === 'residual' })) }} />}{tool !== 'pan' && hintNode && hintPort && hintPosition && <div id="draft-port-tooltip" ref={hintRef} className="draft-port-tooltip" role="tooltip" style={{ ...(measuredHint?.key === hintLayoutKey ? { left: measuredHint.left, top: measuredHint.top } : hintPosition), maxHeight: Math.max(1, viewportSize.height - 24) }}><b>{hintNode.label} · {hintPort.name}</b><span>{hintPort.direction === 'in' ? '输入端口' : '输出端口'}{hintBinding && hintProducer ? ` · 来自 ${hintProducer.label}` : hintPort.direction === 'in' ? ' · 尚未连接' : ' · 可连接多个下游'}</span>{hintTensor ? <span>{draftTensorLabel(hintTensor)}</span> : <span>形状待检查 · 模型尚未执行</span>}<small>{hintPort.direction === 'out' ? '点击或按 Enter 选择，再连接输入端口。' : connection ? '点击或按 Enter 连接；形状以静态检查为准。' : '先选择输出端口，再连接到这里。'}</small></div>}{!draft.nodes.length && <div className="draft-empty"><span>从零搭建一个模型</span><h2>把第一个 Input 拖到这里</h2><p>再加入 Linear、激活函数与 Output。<br />也可以从左侧“网络起点”加入完整 MLP、CNN 或残差网络。</p><button disabled={!catalog} onClick={() => { const input = catalog?.modules.find(module => module.kind === 'Input'); if (input) add(input, { x: 80, y: 120 }); }}>添加输入</button></div>}
        </div><div className="draft-help">Shift 连续选择 · 框选 / Ctrl+A 多选 · 拖动整体 · 滚轮缩放 · 中键/Alt 平移 · 输出端口 → 输入端口 · 方向键移动 16 · Delete 删除 · Escape 取消 · Ctrl+Z 撤销</div>
      </main>
      <aside className="draft-inspector"><span className="eyebrow">MODEL PROPERTIES</span>{selected && selectedModule ? <><h2>{draftSourceKind(draft, selected)}</h2>{selectedIds.length > 1 && <p>已选择 {selectedIds.length} 个部件；拖动或方向键可整体移动。</p>}{draft.sourceProvenance?.nodeRefs[selected.id] && <div className="draft-source-evidence"><b>源码编辑副本</b><p>保留完整源码、层级、共享和未知事实。此处结构编辑只影响独立草稿。</p><code>{draft.sourceProvenance.nodeRefs[selected.id].nodeId}</code><details><summary>原始参数与事实</summary><pre>{JSON.stringify(draft.sourceProvenance.architecture.nodes.find(node => node.id === draft.sourceProvenance?.nodeRefs[selected.id]?.nodeId)?.parameters, null, 2)}</pre></details><p>{draft.sourceProvenance.nodeRefs[selected.id].repeat && `重复 ${draft.sourceProvenance.nodeRefs[selected.id].repeat!.count} 次 · ${draft.sourceProvenance.nodeRefs[selected.id].repeat!.sharing}`} {draft.sourceProvenance.nodeRefs[selected.id].evidence === 'opaque' && '未知区域：可移动、重连或替换；生成需明确表达式。'}</p></div>}{draft.sourceProvenance?.architecture.nodes.find(node => node.id === draft.sourceProvenance?.nodeRefs[selected.id]?.nodeId)?.children.length ? <button disabled={busy} onClick={() => void toggleSourceHierarchy(selected.id)}>{selected.presentation?.group ? '折叠此源码区域' : '展开此源码区域'}</button> : null}<label className="draft-field">显示名称<DraftTextInput ariaLabel="模块显示名称" value={selected.label} disabled={busy} onCommit={label => apply(value => { value.nodes.find(node => node.id === selected.id)!.label = label; })} /></label><div className="draft-param-fields">{selectedModule.parameters.map(parameter => <DraftField key={`${selected.id}:${parameter.name}`} kind={selected.kind} parameter={parameter} value={selected.parameters[parameter.name]} disabled={busy} error={feedback?.target?.nodeId === selected.id && feedback.target.parameter === parameter.name ? feedback.message : undefined} onValidity={invalid => fieldValidity(selected.id, parameter.name, invalid)} onDiscardInvalid={discardInvalidInput} onCommit={value => apply(next => { next.nodes.find(node => node.id === selected.id)!.parameters[parameter.name] = value; })} />)}</div><p className="draft-description">{selectedModule.description}</p>{selected.kind === 'Linear' && <p className="draft-parameter-help">例如输入形状为 [1, 16] 时，in_features 应为 16；out_features 决定输出最后一维。</p>}<div className="draft-coordinate">{(['x', 'y'] as const).map(axis => <label key={axis}>{axis.toUpperCase()}<input aria-label={`模块 ${axis.toUpperCase()} 坐标`} type="number" value={selected.position[axis]} disabled={busy} onChange={event => { if (event.target.value && Number.isFinite(Number(event.target.value))) apply(value => { value.nodes.find(node => node.id === selected.id)!.position[axis] = Number(event.target.value); }); }} /></label>)}</div><button disabled={busy} onClick={deleteSelection}>删除模块及相连连线</button></> : selection.edge ? <><h2>张量连线</h2><p>此连线定义模块的输入来源。</p><button disabled={busy} onClick={deleteSelection}>删除连线</button></> : <><h2>每一步都在图上完成</h2><ol><li>拖入 Input，设置输入形状。</li><li>拖入常用模块，编辑参数。</li><li>连接端口，加入 Output。</li><li>保存草稿，生成模型与论文图。</li></ol><p>随时点击“检查模型”，查看缺少的连接与声明形状；完成后再生成。当前是静态建模，模型尚未执行。</p></>}<section className="draft-check" aria-label="模型静态检查"><h3>{checked ? checked.complete ? draft.customModules?.length ? '连接检查通过 · 自定义形状未知' : draft.sourceProvenance ? '连接检查通过' : '静态检查通过' : `${checked.issues.length} 项待完成` : '检查当前结构'}</h3><p>{checked ? draft.customModules?.length ? '仅检查静态连接；自定义模块及下游输出形状未推测，模型尚未执行。' : draft.sourceProvenance ? '保留源码事实；当前连接检查不推测未知形状，模型尚未执行。' : '以下形状来自静态声明，模型尚未执行。' : '参数、模块或连接改变后需重新检查；移动和显示名称不影响声明形状。'}</p>{selected && checked?.tensors[selected.id] && <div className="draft-checked-tensor">{draftTensorLabel(checked.tensors[selected.id])}</div>}{checked?.issues.map((issue, index) => { const targets = (issue.nodeId ? [issue.nodeId] : issue.nodeIds ?? []).filter(id => draft.nodes.filter(node => node.id === id).length === 1); return <div className="draft-check-issue" key={`${issue.code}:${index}`}><span>{issue.message}</span>{targets.map(id => <button key={id} onClick={() => { reportError(new ApiError(issue.technical ?? issue.message, 400, [{ ...issue, nodeId: id }])); }}>{`定位 ${draft.nodes.find(node => node.id === id)!.label}`}</button>)}</div>; })}<button disabled={busy || !catalog || !!invalidFields.length} onClick={() => void check()}>{checked ? '重新检查' : '检查模型'}</button></section><div className="draft-summary"><b>{draft.nodes.length}</b> 模块 <b>{draft.edges.length}</b> 连接</div></aside>
    </div><footer className={`authoring-status ${error ? 'error' : ''}`} role={error || invalidFields.length ? 'alert' : 'status'}>{busy ? ({ check: '正在检查模型…', save: '正在保存草稿…', reopen: '正在重开保存的草稿…', generate: '正在生成并核对模型…', open: '正在打开新工作副本…', frontier: '正在展开源码层级并保留草稿编辑…' }[busyOperation ?? 'check']) : invalidFields.length ? '参数输入尚未有效：请修正标记字段，或按 Escape 恢复上次有效值，再保存或生成。' : error || currentNotice}{!busy && error && feedback?.target && <button onClick={() => focusDraftNode(feedback.target!.nodeId)}>定位出错模块</button>}{!busy && error && feedback?.technical && <details><summary>技术详情</summary><span>{feedback.technical}</span></details>}</footer>
    {customModuleOpen && <CustomModuleDialog onClose={() => setCustomModuleOpen(false)} onInsert={insertCustomModule} />}
    {generated && <div className="modal-backdrop"><section className="authoring-review" role="dialog" aria-modal="true" aria-label="生成的新模型"><div className="modal-heading"><div><span className="eyebrow">NEW MODEL</span><h2>模型已生成并静态核对</h2></div><button onClick={() => setGenerated(null)} disabled={busy}><Icon name="close" /></button></div><p>{generated.draft.sourceProvenance ? '原源码已保留在独立新副本，生成源码通过语法与静态分析检查；不声明数值等价或执行验证。' : '节点、端口、参数和连接已与新源码的分析结果核对。'}接下来可打开论文图、编辑样式并导出；模型尚未执行。</p><pre>{generated.source}</pre><div className="modal-actions"><button disabled={busy} onClick={() => setGenerated(null)}>继续搭建</button><button className="primary" disabled={busy} onClick={async () => { setBusy(true); setBusyOperation('open'); try { await onOpen(generated); } catch (reason) { reportError(reason); setBusyOperation(null); setBusy(false); } }}>创建新工作副本并打开论文图</button></div></section></div>}
  </div>;
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
