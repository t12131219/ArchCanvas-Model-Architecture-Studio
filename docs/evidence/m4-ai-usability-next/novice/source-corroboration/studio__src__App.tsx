import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { buildScene, createDocument, createHistory, reconcileDocument, reduceHistory, renderSvg, validateArchitecture } from './core';
import type { Architecture, CanvasDocument, HistoryState, ScenePort, VisualOperation } from './core';
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
import { studioTelemetry } from './perf';
import { prepareMovePreview, previewMoveScene } from './core/movePreview';
import type { MovePreviewSession } from './core/movePreview';
import { beginCameraPan, cameraAtPanInput } from './cameraGesture';
import type { CameraState, CameraPan } from './cameraGesture';
import { fitCameraToBounds, focusCameraOnPoint, paperTranslation, viewportToWorld } from './cameraProjection';
import { edgeAppearance } from './edgeAppearance';
import { findAnnotationBodyConflicts, suggestAnnotationPosition } from './core/annotationPlacement';

type Selection = { kind: 'node' | 'edge' | 'legend' | 'annotation'; ids: string[] };
type Camera = CameraState;
type Gesture = { type: 'move' | 'pan' | 'box'; pointerId: number; x: number; y: number; camera: Camera; pan?: CameraPan; ids: string[]; dx: number; dy: number; document?: CanvasDocument; preview?: MovePreviewSession };
type MovePreview = { document: CanvasDocument; session: MovePreviewSession; dx: number; dy: number };
const PALETTE = ['#dcebf6', '#deeee6', '#f4e6d0', '#ece3f4', '#f5dfe3', '#e8ecf0'];
const KEY = 'archcanvas.active-document.v1';
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
  const [history, setHistory] = useState<HistoryState | null>(null);
  const [examples, setExamples] = useState<Example[]>([]);
  const [exampleId, setExampleId] = useState('');
  const [selection, setSelection] = useState<Selection>({ kind: 'node', ids: [] });
  const [camera, setCamera] = useState<Camera>({ x: 35, y: 35, zoom: 0.9 });
  const [tool, setTool] = useState<'select' | 'pan'>('select');
  const [isPanning, setIsPanning] = useState(false);
  const [preview, setPreview] = useState<MovePreview | null>(null);
  const [box, setBox] = useState<{ x: number; y: number; width: number; height: number } | null>(null);
  const [panel, setPanel] = useState<'object' | 'legend' | 'page'>('object');
  const [sourceOpen, setSourceOpen] = useState(false);
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
  const fileRef = useRef<HTMLInputElement>(null);
  const inlineCancelled = useRef(false);
  const historyRef = useRef(history); historyRef.current = history;
  const cameraRef = useRef(camera); cameraRef.current = camera;
  const loadSequence = useRef(0);
  const saving = useRef(false);
  const frame = useRef(0);

  const current = history?.document;
  const committedScene = useMemo(() => current ? buildScene(current) : null, [current]);
  const scene = useMemo(() => preview && preview.document === current ? previewMoveScene(preview.session, preview.dx, preview.dy) : committedScene, [current, committedScene, preview]);
  const markup = useMemo(() => scene ? renderSvg(scene, { interactive: true }) : '', [scene]);
  const architecture = current?.architecture;
  const selectedNode = selection.kind === 'node' ? architecture?.nodes.find(n => n.id === selection.ids[0]) : undefined;
  const selectedEdge = selection.kind === 'edge' ? architecture?.edges.find(n => n.id === selection.ids[0]) : undefined;
  const selectedEdgeAppearance = selectedEdge && current && scene ? edgeAppearance(current, selectedEdge.id, scene) : undefined;
  const selectedAnnotation = selection.kind === 'annotation' ? current?.annotations.find(n => n.id === selection.ids[0]) : undefined;
  const selectedSceneNode = scene?.nodes.find(n => n.id === selectedNode?.id);
  const selectedSceneAnnotation = scene?.annotations.find(n => n.id === selectedAnnotation?.id);
  const annotationConflicts = scene && selectedSceneAnnotation ? findAnnotationBodyConflicts(scene, selectedSceneAnnotation) : [];
  const paperPosition = scene ? paperTranslation(camera, scene.bounds) : null;
  const dirty = !!current && current.revision !== savedVisualRevision;
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

  const cancelGesture = useCallback(() => {
    const active = gesture.current;
    const pointerId = active?.pointerId ?? portGesture.current?.pointerId;
    // Clear ownership before releasing capture: lostpointercapture is synchronous.
    gesture.current = null; portGesture.current = null; portRequest.current++;
    cancelAnimationFrame(frame.current); frame.current = 0;
    setPreview(null); setBox(null); setPortDraft(null); setIsPanning(false);
    if (active?.type === 'pan') { cameraRef.current = active.camera; setCamera(active.camera); }
    const viewport = viewportRef.current;
    if (pointerId !== undefined && viewport?.hasPointerCapture(pointerId)) viewport.releasePointerCapture(pointerId);
  }, []);
  function chooseTool(next: 'select' | 'pan') { cancelGesture(); setTool(next); }
  useEffect(() => {
    const blur = () => { space.current = false; cancelGesture(); };
    window.addEventListener('blur', blur);
    return () => { window.removeEventListener('blur', blur); cancelAnimationFrame(frame.current); };
  }, [cancelGesture]);
  useEffect(() => { if (review || exportDocument || importOpen || connectionProposal || runtimeOpen) cancelGesture(); }, [review, exportDocument, importOpen, connectionProposal, runtimeOpen, cancelGesture]);

  const apply = useCallback((operations: VisualOperation[], message?: string) => {
    cancelGesture();
    const interaction = studioTelemetry.beginInteraction(`visual:${operations.map(operation => operation.type === 'expand' && !operation.expanded ? 'collapse' : operation.type).join('+') || 'noop'}`);
    try {
      const previous = historyRef.current;
      if (!previous) return;
      const next = reduceHistory(previous, { type: 'apply', baseRevision: previous.document.revision, operations });
      historyRef.current = next; setHistory(next);
      if (message) setNotice(message);
      setFailure('');
    } catch (error) { setFailure(String(error)); }
    finally { studioTelemetry.endInteraction(interaction); }
  }, [cancelGesture]);
  const selectHierarchyNode = useCallback((id: string) => { setSelection({ kind: 'node', ids: [id] }); setPanel('object'); }, []);
  const expandHierarchyNode = useCallback((id: string, expanded: boolean) => apply([{ type: 'expand', id, expanded }]), [apply]);
  const undo = useCallback(() => { cancelGesture(); setHistory(p => p ? reduceHistory(p, { type: 'undo' }) : p); setNotice('已撤销一次画布操作'); }, [cancelGesture]);
  const redo = useCallback(() => { cancelGesture(); setHistory(p => p ? reduceHistory(p, { type: 'redo' }) : p); setNotice('已重做一次画布操作'); }, [cancelGesture]);

  const fit = useCallback((documentToFit?: CanvasDocument) => {
    cancelGesture();
    const doc = documentToFit ?? historyRef.current?.document;
    if (!doc || !viewportRef.current) return;
    const interaction = studioTelemetry.beginInteraction('fit-canvas');
    const { bounds } = buildScene(doc);
    const { width, height } = viewportRef.current.getBoundingClientRect();
    setCamera(fitCameraToBounds(bounds, { width, height }));
    studioTelemetry.endInteraction(interaction);
  }, [cancelGesture]);

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
    setHistory(createHistory(document)); setStorageRevision(version); setSavedVisualRevision(saved);
    setProjectId(null); setReview(null); localStorage.removeItem(REVIEW);
    setSelection({ kind: 'node', ids: [] }); setPreview(null); setSourceOpen(false);
    setNotice(saved >= 0 ? '已重开保存的画布' : '静态源码已导入；模型未被执行'); setFailure('');
    requestAnimationFrame(() => fit(document));
  }, [fit]);

  const loadExample = useCallback(async (id: string) => {
    cancelGesture();
    const sequence = ++loadSequence.current;
    setBusy(true); setFailure('');
    try { const arch = await api.example(id); if (sequence !== loadSequence.current) return; setExampleId(id); await openArchitecture(arch, true, sequence); }
    catch (error) { if (sequence === loadSequence.current) setFailure(String(error)); }
    finally { if (sequence === loadSequence.current) { setBusy(false); setRuntimeCancel(null); setCancelling(false); } }
  }, [openArchitecture, cancelGesture]);

  useEffect(() => {
    let alive = true;
    api.capabilities().then(result => { if (alive) setCapabilities(result); }).catch(() => {});
    api.examples().then(async items => {
      if (!alive) return;
      setExamples(items);
      try {
        const active = JSON.parse(localStorage.getItem(ACTIVE) ?? 'null') as { documentId: string; projectId: string | null } | null;
        if (active) {
          const stored = await api.document(active.documentId);
          let doc = stored.document; let version = stored.revision; let saved = doc.revision;
          if (active.projectId) {
            const project = await api.project(active.projectId);
            if (project.sourceDigest !== doc.sourceBindingDigest || project.irDigest !== doc.architecture.irDigest) {
              doc = reconcileDocument(doc, project.architecture).document; version = 0; saved = -1;
            }
          }
          if (!alive) return;
          historyRef.current = createHistory(doc); setHistory(historyRef.current); setStorageRevision(version); setSavedVisualRevision(saved); setProjectId(active.projectId);
          setNotice(active.projectId ? '已重开工作副本及保存的画布' : '已重开保存的画布'); requestAnimationFrame(() => fit(doc));
          const pending = JSON.parse(localStorage.getItem(REVIEW) ?? 'null') as { projectId: string; id: string } | null;
          if (pending && pending.projectId === active.projectId) {
            const transaction = await api.transaction(pending.projectId, pending.id);
            if (alive && transaction.status !== 'Discarded') setReview({ transaction, base: doc, projectId: pending.projectId });
          }
          return;
        }
      } catch { /* A missing stored snapshot falls back to an analyzed example. */ }
      const prior = localStorage.getItem(KEY);
      void loadExample(items.find(x => x.id === prior)?.id ?? items[0]?.id ?? 'transformer');
    }).catch(error => { if (alive) { setFailure(`Runtime 未连接：${String(error)}`); setNotice('请按 README 启动正式服务'); } });
    return () => { alive = false; };
  }, [loadExample, fit]);
  useEffect(() => { if (exampleId) localStorage.setItem(KEY, exampleId); }, [exampleId]);
  useEffect(() => { if (current) localStorage.setItem(ACTIVE, JSON.stringify({ documentId: current.id, projectId })); }, [current?.id, projectId]);

  const save = useCallback(async () => {
    if (!historyRef.current || saving.current) return;
    saving.current = true;
    const frozen = historyRef.current.document;
    const sequence = loadSequence.current;
    setBusy(true);
    try {
      const result = await api.save(frozen, storageRevision);
      if (sequence !== loadSequence.current || historyRef.current?.document.id !== frozen.id) return;
      setStorageRevision(result.revision); setSavedVisualRevision(frozen.revision);
      setNotice('画布已保存到正式工程 .archcanvas；可重开继续编辑'); setFailure('');
    } catch (error) { if (sequence === loadSequence.current) setFailure(`保存失败，当前编辑已保留：${String(error)}`); }
    finally { saving.current = false; if (sequence === loadSequence.current) setBusy(false); }
  }, [storageRevision]);

  useEffect(() => {
    const down = (event: KeyboardEvent) => {
      if (editingTarget(event.target) || review || exportDocument || connectionProposal || runtimeOpen || importOpen) return;
      if (event.code === 'Space') { space.current = true; event.preventDefault(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); event.shiftKey ? redo() : undo(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); void save(); }
      if (event.key === 'Escape') { cancelGesture(); setSelection({ kind: 'node', ids: [] }); setInline(null); }
      if (!event.ctrlKey && !event.metaKey && !event.altKey) {
        if (event.key.toLowerCase() === 'f') fit();
        if (event.key.toLowerCase() === 'h') { cancelGesture(); setTool('pan'); }
        if (event.key.toLowerCase() === 'v') { cancelGesture(); setTool('select'); }
      }
    };
    const up = (event: KeyboardEvent) => { if (event.code === 'Space') space.current = false; };
    window.addEventListener('keydown', down); window.addEventListener('keyup', up);
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); };
  }, [fit, redo, save, undo, review, exportDocument, connectionProposal, runtimeOpen, importOpen, cancelGesture]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const wheel = (event: WheelEvent) => {
      if (editingTarget(event.target)) return;
      event.preventDefault();
      if (gesture.current || portGesture.current) return;
      const rect = viewport.getBoundingClientRect();
      const px = event.clientX - rect.left, py = event.clientY - rect.top;
      setCamera(old => { const zoom = Math.max(0.15, Math.min(3, old.zoom * Math.exp(-event.deltaY * 0.0015))); return { x: px - (px - old.x) * zoom / old.zoom, y: py - (py - old.y) * zoom / old.zoom, zoom }; });
    };
    viewport.addEventListener('wheel', wheel, { passive: false });
    return () => viewport.removeEventListener('wheel', wheel);
  }, []);

  function panInput(event: React.PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return { pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY, viewportX: rect.left, viewportY: rect.top };
  }
  function pointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (editingTarget(event.target) || !scene || gesture.current || portGesture.current) return;
    portRequest.current++;
    const input = panInput(event);
    const x = input.clientX - input.viewportX, y = input.clientY - input.viewportY;
    const view = cameraRef.current;
    // Navigation takes priority even over expand handles and input ports.
    if (event.button === 1 || (event.button === 0 && (tool === 'pan' || space.current))) {
      gesture.current = { type: 'pan', pointerId: event.pointerId, x, y, camera: view, pan: beginCameraPan(view, input), ids: [], dx: 0, dy: 0 };
      setIsPanning(true); event.currentTarget.setPointerCapture(event.pointerId); event.preventDefault(); return;
    }
    if (event.button !== 0) return;
    const target = event.target as Element;
    const portId = target.closest('[data-port-id]')?.getAttribute('data-port-id');
    const port = scene.nodes.flatMap(node => node.ports).find(p => p.id === portId);
    if (port?.direction === 'in' && !busy && current) {
      event.preventDefault();
      if (port.proxy || !inputSpec) {
        setConnectionProposal({ nodeId: port.canonicalNodeId, portId: port.canonicalPortId, candidate: null, blockers: [!inputSpec ? '先设置运行输入与模式，再检查可用来源。' : '这是折叠层级的投影端口；请展开至准确调用端口。'] });
        return;
      }
      const sequence = loadSequence.current;
      const promise = inspectRebind(port.canonicalNodeId, port.canonicalPortId);
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
        gesture.current = { type: 'move', pointerId: event.pointerId, x, y, camera: view, ids, dx: 0, dy: 0, document: current, preview: prepareMovePreview(current, ids) };
      } catch (error) { setFailure(String(error)); return; }
    } else if (edgeId) { setSelection({ kind: 'edge', ids: [edgeId] }); setPanel('object'); return; }
    else if (legendId) { setSelection({ kind: 'legend', ids: [legendId] }); setPanel('legend'); return; }
    else if (annotationId) { setSelection({ kind: 'annotation', ids: [annotationId] }); setPanel('object'); return; }
    else {
      if (!event.shiftKey) setSelection({ kind: 'node', ids: [] });
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
      return;
    }
    const active = gesture.current; if (!active || active.pointerId !== event.pointerId) return;
    const input = panInput(event);
    active.dx = input.clientX - input.viewportX - active.x; active.dy = input.clientY - input.viewportY - active.y;
    cancelAnimationFrame(frame.current); frame.current = 0;
    gesture.current = null; setPreview(null); setBox(null); setIsPanning(false);
    if (active.pan) {
      const finalCamera = cameraAtPanInput(active.pan, input);
      if (finalCamera) { cameraRef.current = finalCamera; setCamera(finalCamera); }
    }
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (active.type === 'move' && historyRef.current?.document === active.document && Math.hypot(active.dx, active.dy) > 3) apply([{ type: 'move', ids: active.ids, dx: Math.round(active.dx / active.camera.zoom / 4) * 4, dy: Math.round(active.dy / active.camera.zoom / 4) * 4 }], '位置已调整；一次拖动对应一次撤销');
    if (active.type === 'box' && scene && Math.hypot(active.dx, active.dy) > 4) {
      const { x, y } = viewportToWorld(active.camera, { x: Math.min(active.x, active.x + active.dx), y: Math.min(active.y, active.y + active.dy) });
      const right = x + Math.abs(active.dx) / active.camera.zoom, bottom = y + Math.abs(active.dy) / active.camera.zoom;
      const ids = scene.nodes.filter(n => n.x >= x && n.y >= y && n.x + n.width <= right && n.y + n.height <= bottom).map(n => n.id);
      setSelection({ kind: 'node', ids: [...new Set([...active.ids, ...ids])] });
    }
  }
  function pointerCancelled(event: React.PointerEvent<HTMLDivElement>) {
    if (gesture.current?.pointerId === event.pointerId || portGesture.current?.pointerId === event.pointerId) cancelGesture();
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
  function align() {
    if (!scene || selection.kind !== 'node' || selection.ids.length < 2) return;
    const selected = scene.nodes.filter(n => selection.ids.includes(n.id));
    const left = Math.min(...selected.map(n => n.x));
    apply(selected.map(n => ({ type: 'move', ids: [n.id], dx: left - n.x, dy: 0 })), '已左对齐所选对象');
  }
  function runCommand() {
    if (!selectedNode || !current) { setFailure('先在画布或层级中选择一个节点'); return; }
    const text = command.trim(); const ops: VisualOperation[] = [];
    const colors: Record<string, string> = { 蓝色: '#dcebf6', 绿色: '#deeee6', 紫色: '#ece3f4', 橙色: '#f4e6d0', 灰色: '#e8ecf0' };
    const color = Object.keys(colors).find(c => text.includes(c));
    const alias = text.match(/(?:命名为|改名为|显示名设为|显示名改为)\s*[“"']?(.+?)[”"']?$/);
    if (color) ops.push({ type: 'nodeStyle', id: selectedNode.id, style: { fill: colors[color] } });
    if (alias) ops.push({ type: 'alias', id: selectedNode.id, label: alias[1] });
    if (text.includes('展开') && selectedSceneNode?.expandable) ops.push({ type: 'expand', id: selectedNode.id, expanded: true });
    if (text.includes('收起') && selectedSceneNode?.expandable) ops.push({ type: 'expand', id: selectedNode.id, expanded: false });
    if (text.includes('固定')) ops.push({ type: 'pin', ids: selection.ids, pinned: !text.includes('取消固定') });
    if (!ops.length) { setFailure('本地视觉指令支持：设为蓝色/绿色/紫色、命名为…、展开、收起、固定。Dropout 参数请在对象面板预览并审核。'); return; }
    apply(ops, '文字指令已写入同一画布操作历史'); setCommand('');
  }
  async function importSource() {
    cancelGesture();
    const sequence = ++loadSequence.current;
    setBusy(true);
    try { const arch = await api.analyze(sourceText, entry, filename); if (sequence !== loadSequence.current) return; await openArchitecture(arch, true, sequence); setExampleId(''); setImportOpen(false); }
    catch (error) { if (sequence === loadSequence.current) setFailure(String(error)); }
    finally { if (sequence === loadSequence.current) setBusy(false); }
  }
  function focusNode(id: string) {
    cancelGesture();
    setSelection({ kind: 'node', ids: [id] }); setPanel('object');
    const node = scene?.nodes.find(n => n.id === id);
    if (!node || !viewportRef.current || !scene) return;
    const { width, height } = viewportRef.current.getBoundingClientRect();
    setCamera(old => focusCameraOnPoint(old, { x: node.x + node.width / 2, y: node.y + node.height / 2 }, { width, height }));
  }

  function focusAnnotation(id: string) {
    cancelGesture();
    const document = historyRef.current?.document, viewport = viewportRef.current;
    if (!document || !viewport) return;
    const updated = buildScene(document), annotation = updated.annotations.find(item => item.id === id);
    if (!annotation) return;
    const { width, height } = viewport.getBoundingClientRect();
    setCamera(old => focusCameraOnPoint(old, { x: annotation.x + annotation.width / 2, y: annotation.y + annotation.height / 2 }, { width, height }));
  }
  function addAnnotation() {
    if (!scene) return;
    const id = `annotation-${crypto.randomUUID()}`;
    apply([{ type: 'annotation', annotation: { id, text: '双击节点编辑显示名；说明不改变计算。', ...suggestAnnotationPosition(scene), width: 380 } }]);
    setSelection({ kind: 'annotation', ids: [id] }); setPanel('object'); focusAnnotation(id);
  }
  function moveAnnotationBelow() {
    if (!scene || !selectedAnnotation) return;
    const position = suggestAnnotationPosition(scene, selectedAnnotation.id);
    if (position.x !== selectedAnnotation.x || position.y !== selectedAnnotation.y) apply([{ type: 'annotation', annotation: { ...selectedAnnotation, ...position } }], '说明已移到图下方；可撤销恢复原位置');
    focusAnnotation(selectedAnnotation.id);
  }
  function zoomCamera(factor: number | 'reset') {
    cancelGesture();
    setCamera(old => ({ ...old, zoom: factor === 'reset' ? 1 : Math.max(0.15, Math.min(3, old.zoom * factor)) }));
  }

  return <div className="studio">
    <header className="topbar">
      <div className="brand"><span className="brand-mark"><i /><i /><i /></span><span>ArchCanvas<small>MODEL ARCHITECTURE STUDIO</small></span></div>
      <div className="project-breadcrumb"><span className="slash">/</span><Icon name="file" size={15} /><span>{current?.title ?? '模型工作台'}</span><span className="alpha-tag">ALPHA</span></div>
      <div className="header-actions"><span className={`save-state ${dirty ? 'dirty' : ''}`}><i />{current ? dirty ? '有未保存编辑' : '已保存' : '等待文档'}</span><button onClick={save} disabled={!current || busy}><Icon name="save" size={15} />保存</button><button className="primary" onClick={() => current && setExportDocument(structuredClone(current))} disabled={!current || busy}><Icon name="export" size={16} />导出论文图</button></div>
    </header>
    <div className="workspace">
      <aside className="navigator">
        <div className="navigator-top"><div className="eyebrow">SOURCE WORKSPACE</div><div className="model-switch"><Icon name="layers" /><select aria-label="示例模型" value={exampleId} onChange={e => void loadExample(e.target.value)} disabled={busy}><option value="" disabled>导入的模型</option>{examples.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}</select></div><button className="import-button" disabled={busy} onClick={() => setImportOpen(true)}><Icon name="plus" size={15} />导入 Python 源码</button></div>
        <div className="nav-section-title">模型层级<span>{architecture?.nodes.length ?? 0}</span></div>
        <div className="tree" role="tree" aria-label="模型层级">
          {architecture && current && <HierarchyTree architecture={architecture} document={current} selected={selection.ids} onSelect={selectHierarchyNode} onExpand={expandHierarchyNode} />}
        </div>
        <div className="navigator-bottom"><button className={sourceOpen ? 'active' : ''} onClick={() => setSourceOpen(x => !x)} disabled={!current}><Icon name="code" size={16} />查看源码证据<Icon name="chevron" size={13} /></button><div className="source-note"><span className="live-dot" />静态分析 · 未执行模型<p>{projectId ? '当前为 Studio 工作副本。' : '样式和显示名仅修改画布。'}</p></div></div>
      </aside>
      <main className="main">
        <div className="canvas-toolbar"><div className="tool-group"><button title="选择 / Shift 多选 · V" aria-label="选择对象" aria-pressed={tool === 'select'} className={`tool ${tool === 'select' ? 'selected' : ''}`} onClick={() => chooseTool('select')}><Icon name="arrow" /></button><button title="拖动画布 · H" aria-label="平移画布" aria-pressed={tool === 'pan'} className={`tool ${tool === 'pan' ? 'selected' : ''}`} onClick={() => chooseTool('pan')}><Icon name="hand" /></button><span className="tool-divider" /><button className="tool" onClick={undo} disabled={!history?.past.length} title="撤销 Ctrl+Z"><Icon name="undo" /></button><button className="tool" onClick={redo} disabled={!history?.future.length} title="重做 Ctrl+Shift+Z"><Icon name="redo" /></button><span className="tool-divider" /><button className="tool" onClick={align} disabled={selection.ids.length < 2} title="左对齐"><Icon name="align" /></button><button className="tool" onClick={() => apply([{ type: 'pin', ids: selection.ids, pinned: !current?.pinnedObjects.includes(selection.ids[0]) }])} disabled={!selection.ids.length || selection.kind !== 'node'} title="固定 / 解锁"><Icon name="pin" /></button></div><div className="paper-preset"><span className="mini-paper" /><select aria-label="页面预设" value={current?.pageSpec.preset ?? 'paper'} disabled={!current} onChange={e => apply([{ type: 'page', page: { preset: e.target.value as 'paper' | 'monochrome' } }])}><option value="paper">论文 · 彩色</option><option value="monochrome">论文 · 黑白</option></select></div><div className="tool-group"><button className={`tool ${grid ? 'selected' : ''}`} title="显示编辑网格" onClick={() => setGrid(x => !x)}><Icon name="grid" size={16} /></button><button className="tool" onClick={() => fit()} title="适合画布 F"><Icon name="fit" /></button></div></div>
        <div ref={viewportRef} className={`canvas-viewport ${grid ? 'with-grid' : ''} ${tool === 'pan' ? 'pan-tool' : ''} ${isPanning ? 'is-panning' : ''}`} data-canvas-tool={tool} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={pointerCancelled} onLostPointerCapture={pointerCancelled} onDoubleClick={event => { if (tool === 'pan' || space.current || event.button !== 0 || editingTarget(event.target) || (event.target as Element).closest('[data-port-id],[data-expand-id]')) return; const id = (event.target as Element).closest('[data-node-id]')?.getAttribute('data-node-id'); const n = architecture?.nodes.find(n => n.id === id); if (n) { inlineCancelled.current = false; setInline({ id: n.id, label: current?.displayAliases[n.id] ?? n.label }); setSelection({ kind: 'node', ids: [n.id] }); } }}>
          <div className="canvas-heading"><span>FIGURE WORKSPACE</span><div>{current?.pageSpec.widthMm ?? 180} mm <i /> {current?.pageSpec.preset === 'monochrome' ? 'MONOCHROME' : 'PAPER COLOR'}</div></div>
          {scene?.diagnostics.some(d => d.message.startsWith('Pinned object')) && <div className="layout-warning" role="status">{scene.diagnostics.filter(d => d.message.startsWith('Pinned object')).map((d, i) => <p key={i}>固定对象与展开区域重叠：{d.message} 可移动对象或取消固定后重新排列。</p>)}</div>}
          {scene && paperPosition && <div className="paper" style={{ width: scene.bounds.width, height: scene.bounds.height, transform: `translate(${paperPosition.x}px, ${paperPosition.y}px) scale(${camera.zoom})` }}>
            <div className="publication-scene" data-pinned-ids={JSON.stringify(current?.pinnedObjects ?? [])} data-expanded-ids={JSON.stringify(current?.expandedIds ?? [])} dangerouslySetInnerHTML={{ __html: markup }} />
            {portDraft && <svg className="connection-draft" width={scene.bounds.width} height={scene.bounds.height} viewBox={`${scene.bounds.x} ${scene.bounds.y} ${scene.bounds.width} ${scene.bounds.height}`} aria-label="改接草稿与可用来源"><path d={`M ${portDraft.port.x} ${portDraft.port.y} L ${portDraft.x} ${portDraft.y}`} stroke="#bd7533" strokeWidth="2" strokeDasharray="5 4" fill="none" />{candidatePorts(portDraft.options).map(p => <circle key={p.id} cx={p.x} cy={p.y} r="9" stroke="#35876b" strokeWidth="2" fill="#deeee6" opacity=".8" />)}</svg>}
            {selection.kind === 'node' && scene.nodes.filter(n => selection.ids.includes(n.id)).map(n => <div key={n.id} className="selection-outline" style={{ left: n.x - scene.bounds.x - 3, top: n.y - scene.bounds.y - 3, width: n.width + 6, height: n.height + 6 }}><span /><span /><span /><span />{current?.pinnedObjects.includes(n.id) && <b>固定</b>}</div>)}
            {inline && (() => { const n = scene.nodes.find(n => n.id === inline.id); return n ? <input autoFocus className="inline-editor" aria-label="原位编辑显示名" style={{ left: n.x - scene.bounds.x + 4, top: n.y - scene.bounds.y + 8, width: n.width - 8 }} value={inline.label} onChange={e => setInline({ ...inline, label: e.target.value })} onKeyDown={e => { if (e.nativeEvent.isComposing) return; if (e.key === 'Enter') { inlineCancelled.current = true; apply([{ type: 'alias', id: inline.id, label: inline.label }]); setInline(null); } if (e.key === 'Escape') { inlineCancelled.current = true; setInline(null); } }} onBlur={() => { if (!inlineCancelled.current) apply([{ type: 'alias', id: inline.id, label: inline.label }]); setInline(null); }} /> : null; })()}
          </div>}
          {!scene && <div className="empty-state"><Icon name="layers" size={40} /><h2>让模型结构成为可编辑的论文图</h2><p>{failure || '正在从源码构建第一张画布…'}</p><button onClick={() => void loadExample(examples[0]?.id ?? 'transformer')}>重新连接</button></div>}
          {box && <div className="marquee" style={{ left: box.x, top: box.y, width: box.width, height: box.height }} />}
          <div className="zoom-control" onPointerDown={event => event.stopPropagation()}><button onClick={() => zoomCamera(1 / 1.2)} aria-label="缩小"><Icon name="minus" size={15} /></button><button className="zoom-value" onClick={() => zoomCamera('reset')} title="100%">{Math.round(camera.zoom * 100)}%</button><button onClick={() => zoomCamera(1.2)} aria-label="放大"><Icon name="plus" size={15} /></button><span /><button onClick={() => fit()} aria-label="适合画布"><Icon name="fit" size={15} /></button></div>
          <div className="canvas-hint">{portDraft ? '拖向绿色来源端口；松开只创建提案' : tool === 'pan' ? <>拖动平移<span>·</span>V 返回选择<span>·</span>滚轮缩放</> : <>滚轮缩放<span>·</span>H / 空格平移<span>·</span>输入端口拖向来源创建提案</>}</div>
        </div>
        <div className="command-bar"><span className="command-icon"><Icon name="message" size={17} /></span><input aria-label="画布文字指令" placeholder={selectedNode ? '让选中节点设为蓝色，或命名为…' : '选择一个节点，用文字修改画布…'} value={command} onChange={e => setCommand(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) runCommand(); }} /><span className="local-label">本地视觉指令</span><button onClick={runCommand} disabled={!command.trim()}>应用 <span>↵</span></button></div>
        {sourceOpen && architecture && <div className="source-drawer"><div className="drawer-header"><Icon name="code" size={16} /><b>源码证据</b><span>{selectedNode?.source ? `${selectedNode.source.path}:${selectedNode.source.line}` : '只读 · 未执行'}</span><button className="tool" onClick={() => setSourceOpen(false)} aria-label="关闭源码"><Icon name="close" size={16} /></button></div><div className="source-content">{architecture.sources.map(source => <div key={source.path}><div className="source-filename">{source.path}</div><pre>{source.content.split('\n').map((line, i) => <div key={i} className={selectedNode?.source?.path === source.path && i + 1 >= selectedNode.source.line && i + 1 <= selectedNode.source.endLine ? 'source-highlight' : ''}><span>{i + 1}</span>{line || ' '}</div>)}</pre></div>)}</div></div>}
      </main>
      <aside className="inspector"><div className="inspector-tabs"><button className={panel === 'object' ? 'active' : ''} onClick={() => setPanel('object')}>对象</button><button className={panel === 'legend' ? 'active' : ''} onClick={() => setPanel('legend')}>图例</button><button className={panel === 'page' ? 'active' : ''} onClick={() => setPanel('page')}>页面</button></div><div className="inspector-content">
        {panel === 'object' && selectedNode && current && <>
          <div className="object-heading"><span className="object-icon" style={{ background: selectedSceneNode?.fill }}><Icon name="layers" size={20} /></span><div><h2>{current.displayAliases[selectedNode.id] ?? selectedNode.label}</h2><span>{selectedNode.kind}</span></div></div><div className={`evidence-tag ${selectedNode.evidence}`}><Icon name="check" size={12} />{statusText(selectedNode.evidence)}</div>
          <section className="property-section"><h3>显示</h3><TextField label="显示名称" value={current.displayAliases[selectedNode.id] ?? selectedNode.label} onCommit={label => apply([{ type: 'alias', id: selectedNode.id, label }])} /><p className="field-help">源名称：{selectedNode.label}</p><label className="field-label">图元样式</label><select className="field-select" aria-label="图元样式" value={current.nodeStyleOverrides[selectedNode.id]?.glyph ?? selectedSceneNode?.glyph ?? 'module'} onChange={e => apply([{ type: 'nodeStyle', id: selectedNode.id, style: { glyph: e.target.value as 'module' } }])}>{['module', 'operator', 'tensor', 'attention', 'norm', 'add', 'opaque'].map(g => <option key={g} value={g}>{({ module: '模块框', operator: '紧凑算子', tensor: '张量条带', attention: 'Attention 图元', norm: '归一化图元', add: '加法图元', opaque: '未知边界' } as Record<string, string>)[g]}</option>)}</select><label className="field-label">填充颜色</label><div className="color-palette">{PALETTE.map(color => <button key={color} aria-label={`填充 ${color}`} className={selectedSceneNode?.fill === color ? 'picked' : ''} style={{ background: color }} onClick={() => apply(selection.ids.map(id => ({ type: 'nodeStyle', id, style: { fill: color } })))} />)}<input type="color" aria-label="自定义填充颜色" value={selectedSceneNode?.fill ?? '#dcebf6'} onChange={e => apply(selection.ids.map(id => ({ type: 'nodeStyle', id, style: { fill: e.target.value } })))} /></div><label className="field-label">边框颜色</label><div className="color-field"><input type="color" aria-label="边框颜色" value={selectedSceneNode?.stroke ?? '#607d91'} onChange={e => apply([{ type: 'nodeStyle', id: selectedNode.id, style: { stroke: e.target.value } }])} /><code>{selectedSceneNode?.stroke}</code></div></section>
          <section className="property-section"><h3>排列与层级</h3><div className="coordinate-row"><label>X <output>{Math.round(selectedSceneNode?.x ?? 0)}</output></label><label>Y <output>{Math.round(selectedSceneNode?.y ?? 0)}</output></label></div><button className="full-button" onClick={() => apply([{ type: 'pin', ids: selection.ids, pinned: !current.pinnedObjects.includes(selectedNode.id) }])}><Icon name="pin" size={14} />{current.pinnedObjects.includes(selectedNode.id) ? '取消固定位置' : '固定位置'}</button>{selectedSceneNode?.expandable && <button className="full-button" onClick={() => apply([{ type: 'expand', id: selectedNode.id, expanded: !selectedSceneNode.expanded }])}><Icon name="layers" size={14} />{selectedSceneNode.expanded ? '原位收起' : '原位展开'}</button>}<button className="text-button" onClick={() => focusNode(selectedNode.id)}>聚焦这个对象</button></section>
          <ParameterEditor node={selectedNode} busy={busy} enabled={!!capabilities?.semanticWriteback} onPrepare={prepareParameter} onInspectConfiguration={inspectConfiguration} />
          <ActivationEditor node={selectedNode} busy={busy} enabled={!!capabilities?.supportedIntents?.includes('replace_activation')} inputSpec={inputSpec} onSetup={() => setRuntimeOpen(true)} onPrepare={prepareActivation} />
          <ObjectFacts architecture={current.architecture} node={selectedNode} onSelect={id => { setSelection({ kind: 'node', ids: [id] }); setPanel('object'); }} />
          {selectedNode.ports.some(p => p.direction === 'in') && <ConnectionEditor key={`${architecture?.sourceDigest}:${selectedNode.id}:${JSON.stringify(inputSpec)}`} document={current} nodeId={selectedNode.id} portId={selectedNode.ports.find(p => p.direction === 'in')!.id} busy={busy} inputSpec={inputSpec} onSetup={() => setRuntimeOpen(true)} enabled={!!capabilities?.supportedIntents?.includes('rebind_input')} onInspect={inspectRebind} onPrepare={prepareRebind} />}
          <section className="property-section"><h3>模型事实<span className="read-only">只读</span></h3>{Object.entries(selectedNode.parameters).length ? <dl className="parameters">{Object.entries(selectedNode.parameters).map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{typeof value === 'string' ? value : JSON.stringify(value)}</dd></div>)}</dl> : <p className="field-help">没有已解析的构造参数。</p>}<button className="full-button" onClick={() => setSourceOpen(true)}><Icon name="code" size={14} />查看源码位置</button></section>
        </>}
        {panel === 'object' && selectedEdge && current && <><div className="object-heading"><Icon name="arrow" /><div><h2>{selectedEdge.label || selectedEdge.role}</h2><span>张量关系 · {selectedEdge.role}</span></div></div><section className="property-section"><h3>连线样式</h3><label className="field-label">颜色</label><input type="color" aria-label="连线颜色" value={selectedEdgeAppearance?.stroke ?? '#64748b'} onChange={e => apply([{ type: 'edgeStyle', id: selectedEdge.id, style: { stroke: e.target.value } }])} /><label className="field-label">线宽</label><input aria-label="连线宽度" type="range" min="1" max="4" step="0.5" value={selectedEdgeAppearance?.width ?? 1.5} onChange={e => apply([{ type: 'edgeStyle', id: selectedEdge.id, style: { width: Number(e.target.value) } }])} /><label className="check-field"><input type="checkbox" checked={selectedEdgeAppearance?.dashed ?? false} onChange={e => apply([{ type: 'edgeStyle', id: selectedEdge.id, style: { dashed: e.target.checked } }])} />虚线</label></section><section className="property-section"><h3>当前端口绑定</h3><p className="field-help">{selectedEdge.source.portId} → {selectedEdge.target.portId}</p><p className="field-help">改走线样式不会改变模型计算关系。</p></section><ConnectionEditor key={`${architecture?.sourceDigest}:${selectedEdge.id}:${JSON.stringify(inputSpec)}`} document={current} nodeId={selectedEdge.target.nodeId} portId={selectedEdge.target.portId} busy={busy} inputSpec={inputSpec} onSetup={() => setRuntimeOpen(true)} enabled={!!capabilities?.supportedIntents?.includes('rebind_input')} onInspect={inspectRebind} onPrepare={prepareRebind} /></>}
        {panel === 'object' && selectedAnnotation && <><h2>说明文字</h2><TextField label="内容" value={selectedAnnotation.text} onCommit={text => apply([{ type: 'annotation', annotation: { ...selectedAnnotation, text } }])} />{annotationConflicts.length > 0 && <p className="annotation-overlap" role="status">说明正文与 {annotationConflicts.length} 个对象重叠。可移到图下方，再检查导出。</p>}<button className="full-button" onClick={moveAnnotationBelow}><Icon name="align" size={14} />移到图下方</button><button className="text-button" onClick={() => focusAnnotation(selectedAnnotation.id)}>聚焦这段说明</button><button className="full-button" onClick={() => { apply([{ type: 'removeAnnotation', id: selectedAnnotation.id }]); setSelection({ kind: 'node', ids: [] }); }}>移除说明</button></>}
        {panel === 'object' && !selectedNode && !selectedEdge && !selectedAnnotation && <><div className="inspector-empty"><div className="empty-symbol"><Icon name="arrow" size={24} /></div><h2>从一个对象开始</h2><p>选择模块、连线或说明文字，<br />调整论文图的呈现方式。</p><div className="shortcut-line"><kbd>Shift</kbd> 多选对象</div><div className="shortcut-line"><kbd>双击</kbd> 编辑显示名</div></div><div className="document-summary"><div className="eyebrow">SOURCE-GROUNDED CANVAS</div><h3>{current?.title ?? 'ArchCanvas'}</h3><p>一份模型事实，一份可持续编辑的画布。</p><div><b>{architecture?.nodes.length ?? '—'}</b><span>事实对象</span><b>{architecture?.edges.length ?? '—'}</b><span>端口关系</span></div></div>{!!architecture?.diagnostics.length && <div className="diagnostics"><h3>分析边界</h3>{architecture.diagnostics.slice(0, 4).map((d, i) => <p key={i}>{d.message}</p>)}</div>}</>}
        {panel === 'legend' && current && <><div className="panel-heading"><h2>图例编辑</h2><p>图例属于画布，随当前版本保存和导出。</p></div><div className="legend-list">{current.legendItems.map((item, index) => <div className="legend-editor" key={item.id}><div className="legend-row"><input type="color" aria-label={`图例颜色 ${index + 1}`} value={item.color} onChange={e => apply([{ type: 'legend', items: current.legendItems.map(x => x.id === item.id ? { ...x, color: e.target.value } : x) }])} /><TextField label="" value={item.label} onCommit={label => apply([{ type: 'legend', items: current.legendItems.map(x => x.id === item.id ? { ...x, label } : x) }])} /><button className="tool" aria-label={`删除图例 ${index + 1}`} onClick={() => apply([{ type: 'legend', items: current.legendItems.filter(x => x.id !== item.id) }])}><Icon name="close" size={13} /></button></div><div className="legend-controls"><select aria-label={`图例符号 ${index + 1}`} value={item.glyph} onChange={e => apply([{ type: 'legend', items: current.legendItems.map(x => x.id === item.id ? { ...x, glyph: e.target.value as 'module' } : x) }])}>{['module', 'operator', 'tensor', 'attention', 'norm', 'add', 'opaque'].map(g => <option key={g}>{g}</option>)}</select><button disabled={index === 0} onClick={() => { const items = [...current.legendItems]; [items[index - 1], items[index]] = [items[index], items[index - 1]]; apply([{ type: 'legend', items }]); }} title="上移">↑</button><button disabled={index === current.legendItems.length - 1} onClick={() => { const items = [...current.legendItems]; [items[index + 1], items[index]] = [items[index], items[index + 1]]; apply([{ type: 'legend', items }]); }} title="下移">↓</button></div></div>)}</div><button className="full-button" onClick={() => apply([{ type: 'legend', items: [...current.legendItems, { id: `legend-${crypto.randomUUID()}`, label: '自定义图例', color: '#dcebf6', glyph: 'module' }] }])}><Icon name="plus" size={15} />添加图例条目</button></>}
        {panel === 'page' && current && <><div className="panel-heading"><h2>出版页面</h2><p>SVG、PDF 与 PNG 共用当前画布场景。</p></div><section className="property-section"><label className="field-label">物理页宽</label><div className="segmented">{[85, 180].map(widthMm => <button key={widthMm} className={current.pageSpec.widthMm === widthMm ? 'active' : ''} onClick={() => apply([{ type: 'page', page: { widthMm } }])}>{widthMm} mm</button>)}</div><label className="field-label">背景</label><div className="color-field"><input aria-label="页面背景" type="color" value={current.pageSpec.background} onChange={e => apply([{ type: 'page', page: { background: e.target.value } }])} /><code>{current.pageSpec.background}</code></div><label className="field-label">配色</label><div className="segmented"><button className={current.pageSpec.preset === 'paper' ? 'active' : ''} onClick={() => apply([{ type: 'page', page: { preset: 'paper' } }])}>论文彩色</button><button className={current.pageSpec.preset === 'monochrome' ? 'active' : ''} onClick={() => apply([{ type: 'page', page: { preset: 'monochrome' } }])}>黑白</button></div></section><section className="property-section"><h3>说明与工件</h3><button className="full-button" onClick={addAnnotation}><Icon name="plus" size={14} />添加说明文字</button><button className="full-button" onClick={() => download(`${current.id}.archcanvas.json`, JSON.stringify(current, null, 2), 'application/json')}><Icon name="save" size={14} />下载画布文档</button><p className="field-help">导出论文图可生成 SVG、PDF 或 PNG，并保留可重开的文件链接与导出收据。</p></section></>}
      </div><div className="inspector-footer"><Icon name="info" size={14} /><span>视觉编辑不修改模型源码</span></div></aside>
    </div>
    <footer className={`statusbar ${failure ? 'has-error' : ''}`}><span><i className={busy ? 'busy-dot' : 'live-dot'} />{failure || (runtimeCancel ? cancelling ? '正在取消运行验证…' : '正在隔离运行并核对前后结构…' : busy ? '正在处理…' : notice)}</span><div>{runtimeCancel && <button disabled={cancelling} onClick={() => void cancelRuntime()}>{cancelling ? '取消中…' : '取消运行验证'}</button>}{selection.ids.length > 0 && <span>{selection.ids.length} 个已选</span>}<span>SVG SCENE v1</span><span>rev {current?.revision ?? 0}</span></div></footer>
    {runtimeOpen && architecture && <RuntimeProfileDialog architecture={architecture} initial={inputSpec} example={exampleId === 'multi_input'} onSave={saveInputSpec} onClose={() => setRuntimeOpen(false)} />}
    {connectionProposal && <div className="modal-backdrop"><div className="runtime-modal connection-proposal" role="dialog" aria-modal="true" aria-labelledby="proposal-title"><div className="modal-heading"><div><div className="eyebrow">CONNECTION PROPOSAL</div><h2 id="proposal-title">{connectionProposal.candidate ? '检查改接提案' : '保留未支持的连接提案'}</h2></div><button className="tool" aria-label="关闭连接提案" onClick={() => setConnectionProposal(null)}><Icon name="close" /></button></div>{connectionProposal.candidate ? <p>将选定输入连接到 <b>{connectionProposal.candidate.variable}</b>。当前只创建提案；运行验证后会展示准确源码 diff 和前后关系，批准后才能提交工作副本。</p> : connectionProposal.blockers.map((blocker, i) => <p key={i}>{blocker}</p>)}<div className="modal-actions"><button onClick={() => setConnectionProposal(null)}>保留当前连接</button>{!inputSpec && <button onClick={() => { setConnectionProposal(null); setRuntimeOpen(true); }}>设置运行输入与模式</button>}{connectionProposal.candidate && <button className="primary" disabled={busy} onClick={() => { const proposal = connectionProposal; setConnectionProposal(null); prepareRebind(proposal.nodeId, proposal.portId, proposal.candidate!.binding); }}>运行验证并预览源码修改</button>}</div></div></div>}
    {review && <ReviewDialog base={review.base} transaction={review.transaction} busy={busy} error={reviewError} onApprove={() => void approveParameter()} onCommit={() => void commitParameter()} onClose={() => void closeReview()} />}
    {exportDocument && <ExportDialog document={exportDocument} capabilities={capabilities}
      selectedId={selection.kind === 'node' && selection.ids.length === 1 ? selection.ids[0] : undefined}
      onClose={() => setExportDocument(null)} />}
    {importOpen && <div className="modal-backdrop"><div className="import-modal" role="dialog" aria-modal="true" aria-labelledby="import-title"><div className="modal-heading"><div><div className="eyebrow">STATIC SOURCE IMPORT</div><h2 id="import-title">从 Python 源码开始</h2></div><button className="tool" onClick={() => setImportOpen(false)} aria-label="关闭导入"><Icon name="close" /></button></div><p>导入单文件 nn.Module。分析器只解析源码；不导入模块、不运行 forward。多文件工程可通过 CLI 分析后，读取生成的架构 JSON。</p><div className="import-fields"><label>模型类名<input value={entry} onChange={e => setEntry(e.target.value)} /></label><label>文件名<input value={filename} onChange={e => setFilename(e.target.value)} /></label><button onClick={() => fileRef.current?.click()}><Icon name="file" size={15} />读取 .py / 架构 JSON</button><input ref={fileRef} hidden type="file" accept=".py,.json" onChange={async e => { const file = e.target.files?.[0]; if (!file) return; try { if (file.size > 4_000_000) throw new Error('文件超过 4 MB 导入预算'); const text = await file.text(); if (file.name.endsWith('.json')) { const architecture = validateArchitecture(JSON.parse(text)); await openArchitecture(architecture); setExampleId(''); setImportOpen(false); } else { setSourceText(text); setFilename(file.name); } } catch (error) { setFailure(`导入失败：${String(error)}`); } e.target.value = ''; }} /></div><textarea aria-label="Python 源码" spellCheck={false} placeholder="import torch\nfrom torch import nn\n\nclass Model(nn.Module):\n    ..." value={sourceText} onChange={e => setSourceText(e.target.value)} />{failure && <p className="error-text">{failure}</p>}<div className="modal-actions"><button onClick={() => setImportOpen(false)}>取消</button><button className="primary" onClick={() => void importSource()} disabled={busy || !sourceText.trim()}>静态分析并打开画布</button></div></div></div>}
  </div>;
}

function TextField({ label, value, onCommit }: { label: string; value: string; onCommit: (value: string) => void }) {
  const [draft, setDraft] = useState(value);
  const cancelled = useRef(false);
  useEffect(() => setDraft(value), [value]);
  return <label className="text-field">{label && <span className="field-label">{label}</span>}<input aria-label={label || '图例文字'} value={draft} onChange={e => { cancelled.current = false; setDraft(e.target.value); }} onBlur={() => { if (!cancelled.current && draft !== value) onCommit(draft); cancelled.current = false; }} onKeyDown={e => { if (e.nativeEvent.isComposing) return; if (e.key === 'Enter') e.currentTarget.blur(); if (e.key === 'Escape') { cancelled.current = true; setDraft(value); e.currentTarget.blur(); } }} /></label>;
}
