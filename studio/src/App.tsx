import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { applyVisualBatch, buildScene, createDocument, createHistory, reconcileDocument, reduceHistory, renderSvg, validateArchitecture } from './core';
import type { Architecture, ArchitectureNode, CanvasDocument, HistoryState, VisualOperation } from './core';
import { api } from './api';
import type { Binding, Capabilities, Example, Transaction } from './api';
import { Icon } from './icons';
import { ParameterEditor } from './ParameterEditor';
import { ConnectionEditor } from './ConnectionEditor';
import { ReviewDialog } from './ReviewDialog';
import { ExportDialog } from './ExportDialog';

type Selection = { kind: 'node' | 'edge' | 'legend' | 'annotation'; ids: string[] };
type Camera = { x: number; y: number; zoom: number };
type Gesture = { type: 'move' | 'pan' | 'box'; x: number; y: number; camera: Camera; ids: string[]; dx: number; dy: number };
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
  const [preview, setPreview] = useState<VisualOperation[]>([]);
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
  const previewDocument = useMemo(() => current && preview.length ? applyVisualBatch(current, preview) : current, [current, preview]);
  const scene = useMemo(() => previewDocument ? buildScene(previewDocument) : null, [previewDocument]);
  const markup = useMemo(() => scene ? renderSvg(scene, { interactive: true }) : '', [scene]);
  const architecture = current?.architecture;
  const selectedNode = selection.kind === 'node' ? architecture?.nodes.find(n => n.id === selection.ids[0]) : undefined;
  const selectedEdge = selection.kind === 'edge' ? architecture?.edges.find(n => n.id === selection.ids[0]) : undefined;
  const selectedAnnotation = selection.kind === 'annotation' ? current?.annotations.find(n => n.id === selection.ids[0]) : undefined;
  const selectedSceneNode = scene?.nodes.find(n => n.id === selectedNode?.id);
  const dirty = !!current && current.revision !== savedVisualRevision;

  useEffect(() => { document.querySelector('.inspector-content')?.scrollTo({ top: 0 }); }, [selection.ids[0], panel]);

  const apply = useCallback((operations: VisualOperation[], message?: string) => {
    try {
      const previous = historyRef.current;
      if (!previous) return;
      const next = reduceHistory(previous, { type: 'apply', baseRevision: previous.document.revision, operations });
      historyRef.current = next; setHistory(next);
      if (message) setNotice(message);
      setFailure('');
    } catch (error) { setFailure(String(error)); }
  }, []);
  const undo = useCallback(() => { setHistory(p => p ? reduceHistory(p, { type: 'undo' }) : p); setNotice('已撤销一次画布操作'); }, []);
  const redo = useCallback(() => { setHistory(p => p ? reduceHistory(p, { type: 'redo' }) : p); setNotice('已重做一次画布操作'); }, []);

  const fit = useCallback((documentToFit?: CanvasDocument) => {
    const doc = documentToFit ?? historyRef.current?.document;
    if (!doc || !viewportRef.current) return;
    const { bounds } = buildScene(doc);
    const { width, height } = viewportRef.current.getBoundingClientRect();
    const zoom = Math.min((width - 96) / bounds.width, (height - 92) / bounds.height, 1.2);
    setCamera({ x: (width - bounds.width * zoom) / 2, y: (height - bounds.height * zoom) / 2, zoom });
  }, []);

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
    setSelection({ kind: 'node', ids: [] }); setPreview([]); setSourceOpen(false);
    setNotice(saved >= 0 ? '已重开保存的画布' : '静态源码已导入；模型未被执行'); setFailure('');
    requestAnimationFrame(() => fit(document));
  }, [fit]);

  const loadExample = useCallback(async (id: string) => {
    const sequence = ++loadSequence.current;
    setBusy(true); setFailure('');
    try { const arch = await api.example(id); if (sequence !== loadSequence.current) return; setExampleId(id); await openArchitecture(arch, true, sequence); }
    catch (error) { if (sequence === loadSequence.current) setFailure(String(error)); }
    finally { if (sequence === loadSequence.current) setBusy(false); }
  }, [openArchitecture]);

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
      if (editingTarget(event.target) || review || exportDocument) return;
      if (event.code === 'Space') { space.current = true; event.preventDefault(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); event.shiftKey ? redo() : undo(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); void save(); }
      if (event.key === 'Escape') { setSelection({ kind: 'node', ids: [] }); setInline(null); }
      if (event.key.toLowerCase() === 'f') fit();
    };
    const up = (event: KeyboardEvent) => { if (event.code === 'Space') space.current = false; };
    window.addEventListener('keydown', down); window.addEventListener('keyup', up);
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); };
  }, [fit, redo, save, undo, review, exportDocument]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const wheel = (event: WheelEvent) => {
      if (editingTarget(event.target)) return;
      event.preventDefault();
      const rect = viewport.getBoundingClientRect();
      const px = event.clientX - rect.left, py = event.clientY - rect.top;
      setCamera(old => { const zoom = Math.max(0.15, Math.min(3, old.zoom * Math.exp(-event.deltaY * 0.0015))); return { x: px - (px - old.x) * zoom / old.zoom, y: py - (py - old.y) * zoom / old.zoom, zoom }; });
    };
    viewport.addEventListener('wheel', wheel, { passive: false });
    return () => viewport.removeEventListener('wheel', wheel);
  }, []);

  function pointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (editingTarget(event.target) || !scene) return;
    const target = event.target as Element;
    const expandId = target.closest('[data-expand-id]')?.getAttribute('data-expand-id');
    if (expandId) { const n = scene.nodes.find(x => x.id === expandId); if (n) apply([{ type: 'expand', id: expandId, expanded: !n.expanded }], n.expanded ? '已原位收起' : '已原位展开，保留画布位置'); return; }
    const nodeId = target.closest('[data-node-id]')?.getAttribute('data-node-id');
    const edgeId = target.closest('[data-edge-id]')?.getAttribute('data-edge-id');
    const legendId = target.closest('[data-legend-id]')?.getAttribute('data-legend-id');
    const annotationId = target.closest('[data-annotation-id]')?.getAttribute('data-annotation-id');
    if (event.button === 1 || space.current) {
      gesture.current = { type: 'pan', x: event.clientX, y: event.clientY, camera, ids: [], dx: 0, dy: 0 };
    } else if (nodeId) {
      const ids = event.shiftKey ? selection.ids.includes(nodeId) ? selection.ids.filter(id => id !== nodeId) : [...(selection.kind === 'node' ? selection.ids : []), nodeId] : selection.kind === 'node' && selection.ids.includes(nodeId) ? selection.ids : [nodeId];
      setSelection({ kind: 'node', ids }); setPanel('object');
      gesture.current = { type: 'move', x: event.clientX, y: event.clientY, camera, ids, dx: 0, dy: 0 };
    } else if (edgeId) { setSelection({ kind: 'edge', ids: [edgeId] }); setPanel('object'); return; }
    else if (legendId) { setSelection({ kind: 'legend', ids: [legendId] }); setPanel('legend'); return; }
    else if (annotationId) { setSelection({ kind: 'annotation', ids: [annotationId] }); setPanel('object'); return; }
    else {
      if (!event.shiftKey) setSelection({ kind: 'node', ids: [] });
      gesture.current = { type: 'box', x: event.clientX, y: event.clientY, camera, ids: event.shiftKey ? selection.ids : [], dx: 0, dy: 0 };
    }
    event.currentTarget.setPointerCapture(event.pointerId);
    event.preventDefault();
  }
  function pointerMove(event: React.PointerEvent<HTMLDivElement>) {
    const active = gesture.current; if (!active) return;
    active.dx = event.clientX - active.x; active.dy = event.clientY - active.y;
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      if (active.type === 'pan') setCamera({ ...active.camera, x: active.camera.x + active.dx, y: active.camera.y + active.dy });
      else if (active.type === 'move') setPreview([{ type: 'move', ids: active.ids, dx: Math.round(active.dx / active.camera.zoom / 4) * 4, dy: Math.round(active.dy / active.camera.zoom / 4) * 4 }]);
      else { const rect = viewportRef.current!.getBoundingClientRect(); setBox({ x: Math.min(active.x, active.x + active.dx) - rect.left, y: Math.min(active.y, active.y + active.dy) - rect.top, width: Math.abs(active.dx), height: Math.abs(active.dy) }); }
    });
  }
  function pointerUp(event: React.PointerEvent<HTMLDivElement>) {
    const active = gesture.current; if (!active) return;
    cancelAnimationFrame(frame.current); gesture.current = null; setPreview([]); setBox(null);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (active.type === 'move' && Math.hypot(active.dx, active.dy) > 3) apply([{ type: 'move', ids: active.ids, dx: Math.round(active.dx / active.camera.zoom / 4) * 4, dy: Math.round(active.dy / active.camera.zoom / 4) * 4 }], '位置已调整；一次拖动对应一次撤销');
    if (active.type === 'box' && scene && Math.hypot(active.dx, active.dy) > 4) {
      const rect = viewportRef.current!.getBoundingClientRect();
      const x = (Math.min(active.x, active.x + active.dx) - rect.left - camera.x) / camera.zoom + scene.bounds.x;
      const y = (Math.min(active.y, active.y + active.dy) - rect.top - camera.y) / camera.zoom + scene.bounds.y;
      const right = x + Math.abs(active.dx) / camera.zoom, bottom = y + Math.abs(active.dy) / camera.zoom;
      const ids = scene.nodes.filter(n => n.x >= x && n.y >= y && n.x + n.width <= right && n.y + n.height <= bottom).map(n => n.id);
      setSelection({ kind: 'node', ids: [...new Set([...active.ids, ...ids])] });
    }
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
    finally { if (sequence === loadSequence.current) setBusy(false); }
  }
  async function inspectRebind(nodeId: string, portId: string) {
    const base = historyRef.current?.document;
    if (!base || busy) throw new Error('画布正在处理，请稍后重试');
    const sequence = loadSequence.current;
    setBusy(true); setFailure('');
    try {
      const project = await semanticProject(base, sequence);
      return await api.rebindOptions(project, base.architecture, nodeId, portId);
    } finally { if (sequence === loadSequence.current) setBusy(false); }
  }
  function prepareParameter(parameter: string, value: number) {
    if (selectedNode) void prepareSemantic((project, architecture) => api.prepare(project, architecture, selectedNode.id, parameter, value));
  }
  function prepareRebind(nodeId: string, portId: string, producer: Binding) {
    void prepareSemantic((project, architecture) => api.prepareRebind(project, architecture, nodeId, portId, producer));
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
    const sequence = ++loadSequence.current;
    setBusy(true);
    try { const arch = await api.analyze(sourceText, entry, filename); if (sequence !== loadSequence.current) return; await openArchitecture(arch, true, sequence); setExampleId(''); setImportOpen(false); }
    catch (error) { if (sequence === loadSequence.current) setFailure(String(error)); }
    finally { if (sequence === loadSequence.current) setBusy(false); }
  }
  function focusNode(id: string) {
    setSelection({ kind: 'node', ids: [id] }); setPanel('object');
    const node = scene?.nodes.find(n => n.id === id);
    if (!node || !viewportRef.current || !scene) return;
    const { width, height } = viewportRef.current.getBoundingClientRect();
    setCamera(old => ({ ...old, x: width / 2 - (node.x - scene.bounds.x + node.width / 2) * old.zoom, y: height / 2 - (node.y - scene.bounds.y + node.height / 2) * old.zoom }));
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
          {architecture?.nodes.filter(n => !n.parentId).map(node => <TreeNode key={node.id} node={node} architecture={architecture} document={current!} selected={selection.ids} onSelect={id => { setSelection({ kind: 'node', ids: [id] }); setPanel('object'); }} onExpand={(id, expanded) => apply([{ type: 'expand', id, expanded }])} />)}
        </div>
        <div className="navigator-bottom"><button className={sourceOpen ? 'active' : ''} onClick={() => setSourceOpen(x => !x)} disabled={!current}><Icon name="code" size={16} />查看源码证据<Icon name="chevron" size={13} /></button><div className="source-note"><span className="live-dot" />静态分析 · 未执行模型<p>{projectId ? '当前为 Studio 工作副本。' : '样式和显示名仅修改画布。'}</p></div></div>
      </aside>
      <main className="main">
        <div className="canvas-toolbar"><div className="tool-group"><button title="选择 / Shift 多选" className="tool selected"><Icon name="arrow" /></button><span className="tool-divider" /><button className="tool" onClick={undo} disabled={!history?.past.length} title="撤销 Ctrl+Z"><Icon name="undo" /></button><button className="tool" onClick={redo} disabled={!history?.future.length} title="重做 Ctrl+Shift+Z"><Icon name="redo" /></button><span className="tool-divider" /><button className="tool" onClick={align} disabled={selection.ids.length < 2} title="左对齐"><Icon name="align" /></button><button className="tool" onClick={() => apply([{ type: 'pin', ids: selection.ids, pinned: !current?.pinnedObjects.includes(selection.ids[0]) }])} disabled={!selection.ids.length || selection.kind !== 'node'} title="固定 / 解锁"><Icon name="pin" /></button></div><div className="paper-preset"><span className="mini-paper" /><select aria-label="页面预设" value={current?.pageSpec.preset ?? 'paper'} disabled={!current} onChange={e => apply([{ type: 'page', page: { preset: e.target.value as 'paper' | 'monochrome' } }])}><option value="paper">论文 · 彩色</option><option value="monochrome">论文 · 黑白</option></select></div><div className="tool-group"><button className={`tool ${grid ? 'selected' : ''}`} title="显示编辑网格" onClick={() => setGrid(x => !x)}><Icon name="grid" size={16} /></button><button className="tool" onClick={() => fit()} title="适合画布 F"><Icon name="fit" /></button></div></div>
        <div ref={viewportRef} className={`canvas-viewport ${grid ? 'with-grid' : ''}`} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={() => { gesture.current = null; cancelAnimationFrame(frame.current); setPreview([]); setBox(null); }} onDoubleClick={event => { const id = (event.target as Element).closest('[data-node-id]')?.getAttribute('data-node-id'); const n = architecture?.nodes.find(n => n.id === id); if (n) { inlineCancelled.current = false; setInline({ id: n.id, label: current?.displayAliases[n.id] ?? n.label }); setSelection({ kind: 'node', ids: [n.id] }); } }}>
          <div className="canvas-heading"><span>FIGURE WORKSPACE</span><div>{current?.pageSpec.widthMm ?? 180} mm <i /> {current?.pageSpec.preset === 'monochrome' ? 'MONOCHROME' : 'PAPER COLOR'}</div></div>
          {scene && <div className="paper" style={{ width: scene.bounds.width, height: scene.bounds.height, transform: `translate(${camera.x}px, ${camera.y}px) scale(${camera.zoom})` }}>
            <div className="publication-scene" dangerouslySetInnerHTML={{ __html: markup }} />
            {selection.kind === 'node' && scene.nodes.filter(n => selection.ids.includes(n.id)).map(n => <div key={n.id} className="selection-outline" style={{ left: n.x - scene.bounds.x - 3, top: n.y - scene.bounds.y - 3, width: n.width + 6, height: n.height + 6 }}><span /><span /><span /><span />{current?.pinnedObjects.includes(n.id) && <b>固定</b>}</div>)}
            {inline && (() => { const n = scene.nodes.find(n => n.id === inline.id); return n ? <input autoFocus className="inline-editor" aria-label="原位编辑显示名" style={{ left: n.x - scene.bounds.x + 4, top: n.y - scene.bounds.y + 8, width: n.width - 8 }} value={inline.label} onChange={e => setInline({ ...inline, label: e.target.value })} onKeyDown={e => { if (e.nativeEvent.isComposing) return; if (e.key === 'Enter') { inlineCancelled.current = true; apply([{ type: 'alias', id: inline.id, label: inline.label }]); setInline(null); } if (e.key === 'Escape') { inlineCancelled.current = true; setInline(null); } }} onBlur={() => { if (!inlineCancelled.current) apply([{ type: 'alias', id: inline.id, label: inline.label }]); setInline(null); }} /> : null; })()}
          </div>}
          {!scene && <div className="empty-state"><Icon name="layers" size={40} /><h2>让模型结构成为可编辑的论文图</h2><p>{failure || '正在从源码构建第一张画布…'}</p><button onClick={() => void loadExample(examples[0]?.id ?? 'transformer')}>重新连接</button></div>}
          {box && <div className="marquee" style={{ left: box.x, top: box.y, width: box.width, height: box.height }} />}
          <div className="zoom-control"><button onClick={() => setCamera(c => ({ ...c, zoom: Math.max(0.15, c.zoom / 1.2) }))} aria-label="缩小"><Icon name="minus" size={15} /></button><button className="zoom-value" onClick={() => setCamera(c => ({ ...c, zoom: 1 }))} title="100%">{Math.round(camera.zoom * 100)}%</button><button onClick={() => setCamera(c => ({ ...c, zoom: Math.min(3, c.zoom * 1.2) }))} aria-label="放大"><Icon name="plus" size={15} /></button><span /><button onClick={() => fit()} aria-label="适合画布"><Icon name="fit" size={15} /></button></div>
          <div className="canvas-hint">滚轮缩放<span>·</span>空格拖动平移<span>·</span>双击改显示名</div>
        </div>
        <div className="command-bar"><span className="command-icon"><Icon name="message" size={17} /></span><input aria-label="画布文字指令" placeholder={selectedNode ? '让选中节点设为蓝色，或命名为…' : '选择一个节点，用文字修改画布…'} value={command} onChange={e => setCommand(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) runCommand(); }} /><span className="local-label">本地视觉指令</span><button onClick={runCommand} disabled={!command.trim()}>应用 <span>↵</span></button></div>
        {sourceOpen && architecture && <div className="source-drawer"><div className="drawer-header"><Icon name="code" size={16} /><b>源码证据</b><span>{selectedNode?.source ? `${selectedNode.source.path}:${selectedNode.source.line}` : '只读 · 未执行'}</span><button className="tool" onClick={() => setSourceOpen(false)} aria-label="关闭源码"><Icon name="close" size={16} /></button></div><div className="source-content">{architecture.sources.map(source => <div key={source.path}><div className="source-filename">{source.path}</div><pre>{source.content.split('\n').map((line, i) => <div key={i} className={selectedNode?.source?.path === source.path && i + 1 >= selectedNode.source.line && i + 1 <= selectedNode.source.endLine ? 'source-highlight' : ''}><span>{i + 1}</span>{line || ' '}</div>)}</pre></div>)}</div></div>}
      </main>
      <aside className="inspector"><div className="inspector-tabs"><button className={panel === 'object' ? 'active' : ''} onClick={() => setPanel('object')}>对象</button><button className={panel === 'legend' ? 'active' : ''} onClick={() => setPanel('legend')}>图例</button><button className={panel === 'page' ? 'active' : ''} onClick={() => setPanel('page')}>页面</button></div><div className="inspector-content">
        {panel === 'object' && selectedNode && current && <>
          <div className="object-heading"><span className="object-icon" style={{ background: selectedSceneNode?.fill }}><Icon name="layers" size={20} /></span><div><h2>{current.displayAliases[selectedNode.id] ?? selectedNode.label}</h2><span>{selectedNode.kind}</span></div></div><div className={`evidence-tag ${selectedNode.evidence}`}><Icon name="check" size={12} />{statusText(selectedNode.evidence)}</div>
          <section className="property-section"><h3>显示</h3><TextField label="显示名称" value={current.displayAliases[selectedNode.id] ?? selectedNode.label} onCommit={label => apply([{ type: 'alias', id: selectedNode.id, label }])} /><p className="field-help">源名称：{selectedNode.label}</p><label className="field-label">图元样式</label><select className="field-select" aria-label="图元样式" value={current.nodeStyleOverrides[selectedNode.id]?.glyph ?? selectedSceneNode?.glyph ?? 'module'} onChange={e => apply([{ type: 'nodeStyle', id: selectedNode.id, style: { glyph: e.target.value as 'module' } }])}>{['module', 'operator', 'tensor', 'attention', 'norm', 'add', 'opaque'].map(g => <option key={g} value={g}>{({ module: '模块框', operator: '紧凑算子', tensor: '张量条带', attention: 'Attention 图元', norm: '归一化图元', add: '加法图元', opaque: '未知边界' } as Record<string, string>)[g]}</option>)}</select><label className="field-label">填充颜色</label><div className="color-palette">{PALETTE.map(color => <button key={color} aria-label={`填充 ${color}`} className={selectedSceneNode?.fill === color ? 'picked' : ''} style={{ background: color }} onClick={() => apply(selection.ids.map(id => ({ type: 'nodeStyle', id, style: { fill: color } })))} />)}<input type="color" aria-label="自定义填充颜色" value={selectedSceneNode?.fill ?? '#dcebf6'} onChange={e => apply(selection.ids.map(id => ({ type: 'nodeStyle', id, style: { fill: e.target.value } })))} /></div><label className="field-label">边框颜色</label><div className="color-field"><input type="color" aria-label="边框颜色" value={selectedSceneNode?.stroke ?? '#607d91'} onChange={e => apply([{ type: 'nodeStyle', id: selectedNode.id, style: { stroke: e.target.value } }])} /><code>{selectedSceneNode?.stroke}</code></div></section>
          <section className="property-section"><h3>排列与层级</h3><div className="coordinate-row"><label>X <output>{Math.round(selectedSceneNode?.x ?? 0)}</output></label><label>Y <output>{Math.round(selectedSceneNode?.y ?? 0)}</output></label></div><button className="full-button" onClick={() => apply([{ type: 'pin', ids: selection.ids, pinned: !current.pinnedObjects.includes(selectedNode.id) }])}><Icon name="pin" size={14} />{current.pinnedObjects.includes(selectedNode.id) ? '取消固定位置' : '固定位置'}</button>{selectedSceneNode?.expandable && <button className="full-button" onClick={() => apply([{ type: 'expand', id: selectedNode.id, expanded: !selectedSceneNode.expanded }])}><Icon name="layers" size={14} />{selectedSceneNode.expanded ? '原位收起' : '原位展开'}</button>}<button className="text-button" onClick={() => focusNode(selectedNode.id)}>聚焦这个对象</button></section>
          <ParameterEditor node={selectedNode} busy={busy} enabled={!!capabilities?.semanticWriteback} onPrepare={(parameter, value) => void prepareParameter(parameter, value)} />
          {selectedNode.ports.filter(p => p.direction === 'in').map(p => <ConnectionEditor key={`${architecture?.sourceDigest}:${architecture?.irDigest}:${selectedNode.id}:${p.id}`} document={current} nodeId={selectedNode.id} portId={p.id} busy={busy} enabled={!!capabilities?.supportedIntents?.includes('rebind_input')} onInspect={inspectRebind} onPrepare={prepareRebind} />)}
          <section className="property-section"><h3>模型事实<span className="read-only">只读</span></h3>{Object.entries(selectedNode.parameters).length ? <dl className="parameters">{Object.entries(selectedNode.parameters).map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{typeof value === 'string' ? value : JSON.stringify(value)}</dd></div>)}</dl> : <p className="field-help">没有已解析的构造参数。</p>}{selectedNode.repeat && <p className="field-help">{selectedNode.repeat.count} 次重复 · {selectedNode.repeat.sharing === 'shared' ? '共享权重' : '独立权重'}</p>}<button className="full-button" onClick={() => setSourceOpen(true)}><Icon name="code" size={14} />查看源码位置</button></section>
        </>}
        {panel === 'object' && selectedEdge && current && <><div className="object-heading"><Icon name="arrow" /><div><h2>{selectedEdge.label || selectedEdge.role}</h2><span>张量关系 · {selectedEdge.role}</span></div></div><section className="property-section"><h3>连线样式</h3><label className="field-label">颜色</label><input type="color" aria-label="连线颜色" value={current.edgeStyleOverrides[selectedEdge.id]?.stroke ?? '#64748b'} onChange={e => apply([{ type: 'edgeStyle', id: selectedEdge.id, style: { stroke: e.target.value } }])} /><label className="field-label">线宽</label><input aria-label="连线宽度" type="range" min="1" max="4" step="0.5" value={current.edgeStyleOverrides[selectedEdge.id]?.width ?? 1.5} onChange={e => apply([{ type: 'edgeStyle', id: selectedEdge.id, style: { width: Number(e.target.value) } }])} /><label className="check-field"><input type="checkbox" checked={current.edgeStyleOverrides[selectedEdge.id]?.dashed ?? false} onChange={e => apply([{ type: 'edgeStyle', id: selectedEdge.id, style: { dashed: e.target.checked } }])} />虚线</label></section><section className="property-section"><h3>当前端口绑定</h3><p className="field-help">{selectedEdge.source.portId} → {selectedEdge.target.portId}</p><p className="field-help">改走线样式不会改变模型计算关系。</p></section><ConnectionEditor key={`${architecture?.sourceDigest}:${architecture?.irDigest}:${selectedEdge.target.nodeId}:${selectedEdge.target.portId}`} document={current} nodeId={selectedEdge.target.nodeId} portId={selectedEdge.target.portId} busy={busy} enabled={!!capabilities?.supportedIntents?.includes('rebind_input')} onInspect={inspectRebind} onPrepare={prepareRebind} /></>}
        {panel === 'object' && selectedAnnotation && <><h2>说明文字</h2><TextField label="内容" value={selectedAnnotation.text} onCommit={text => apply([{ type: 'annotation', annotation: { ...selectedAnnotation, text } }])} /><button className="full-button" onClick={() => { apply([{ type: 'removeAnnotation', id: selectedAnnotation.id }]); setSelection({ kind: 'node', ids: [] }); }}>移除说明</button></>}
        {panel === 'object' && !selectedNode && !selectedEdge && !selectedAnnotation && <><div className="inspector-empty"><div className="empty-symbol"><Icon name="arrow" size={24} /></div><h2>从一个对象开始</h2><p>选择模块、连线或说明文字，<br />调整论文图的呈现方式。</p><div className="shortcut-line"><kbd>Shift</kbd> 多选对象</div><div className="shortcut-line"><kbd>双击</kbd> 编辑显示名</div></div><div className="document-summary"><div className="eyebrow">SOURCE-GROUNDED CANVAS</div><h3>{current?.title ?? 'ArchCanvas'}</h3><p>一份模型事实，一份可持续编辑的画布。</p><div><b>{architecture?.nodes.length ?? '—'}</b><span>事实对象</span><b>{architecture?.edges.length ?? '—'}</b><span>端口关系</span></div></div>{!!architecture?.diagnostics.length && <div className="diagnostics"><h3>分析边界</h3>{architecture.diagnostics.slice(0, 4).map((d, i) => <p key={i}>{d.message}</p>)}</div>}</>}
        {panel === 'legend' && current && <><div className="panel-heading"><h2>图例编辑</h2><p>图例属于画布，随当前版本保存和导出。</p></div><div className="legend-list">{current.legendItems.map((item, index) => <div className="legend-editor" key={item.id}><div className="legend-row"><input type="color" aria-label={`图例颜色 ${index + 1}`} value={item.color} onChange={e => apply([{ type: 'legend', items: current.legendItems.map(x => x.id === item.id ? { ...x, color: e.target.value } : x) }])} /><TextField label="" value={item.label} onCommit={label => apply([{ type: 'legend', items: current.legendItems.map(x => x.id === item.id ? { ...x, label } : x) }])} /><button className="tool" aria-label={`删除图例 ${index + 1}`} onClick={() => apply([{ type: 'legend', items: current.legendItems.filter(x => x.id !== item.id) }])}><Icon name="close" size={13} /></button></div><div className="legend-controls"><select aria-label={`图例符号 ${index + 1}`} value={item.glyph} onChange={e => apply([{ type: 'legend', items: current.legendItems.map(x => x.id === item.id ? { ...x, glyph: e.target.value as 'module' } : x) }])}>{['module', 'operator', 'tensor', 'attention', 'norm', 'add', 'opaque'].map(g => <option key={g}>{g}</option>)}</select><button disabled={index === 0} onClick={() => { const items = [...current.legendItems]; [items[index - 1], items[index]] = [items[index], items[index - 1]]; apply([{ type: 'legend', items }]); }} title="上移">↑</button><button disabled={index === current.legendItems.length - 1} onClick={() => { const items = [...current.legendItems]; [items[index + 1], items[index]] = [items[index], items[index + 1]]; apply([{ type: 'legend', items }]); }} title="下移">↓</button></div></div>)}</div><button className="full-button" onClick={() => apply([{ type: 'legend', items: [...current.legendItems, { id: `legend-${crypto.randomUUID()}`, label: '自定义图例', color: '#dcebf6', glyph: 'module' }] }])}><Icon name="plus" size={15} />添加图例条目</button></>}
        {panel === 'page' && current && <><div className="panel-heading"><h2>出版页面</h2><p>SVG、PDF 与 PNG 共用当前画布场景。</p></div><section className="property-section"><label className="field-label">物理页宽</label><div className="segmented">{[85, 180].map(widthMm => <button key={widthMm} className={current.pageSpec.widthMm === widthMm ? 'active' : ''} onClick={() => apply([{ type: 'page', page: { widthMm } }])}>{widthMm} mm</button>)}</div><label className="field-label">背景</label><div className="color-field"><input aria-label="页面背景" type="color" value={current.pageSpec.background} onChange={e => apply([{ type: 'page', page: { background: e.target.value } }])} /><code>{current.pageSpec.background}</code></div><label className="field-label">配色</label><div className="segmented"><button className={current.pageSpec.preset === 'paper' ? 'active' : ''} onClick={() => apply([{ type: 'page', page: { preset: 'paper' } }])}>论文彩色</button><button className={current.pageSpec.preset === 'monochrome' ? 'active' : ''} onClick={() => apply([{ type: 'page', page: { preset: 'monochrome' } }])}>黑白</button></div></section><section className="property-section"><h3>说明与工件</h3><button className="full-button" onClick={() => { const id = `annotation-${crypto.randomUUID()}`; apply([{ type: 'annotation', annotation: { id, text: '双击节点编辑显示名；说明不改变计算。', x: scene?.bounds.x ?? 40, y: (scene?.bounds.height ?? 500) - 45, width: 380 } }]); setSelection({ kind: 'annotation', ids: [id] }); setPanel('object'); }}><Icon name="plus" size={14} />添加说明文字</button><button className="full-button" onClick={() => download(`${current.id}.archcanvas.json`, JSON.stringify(current, null, 2), 'application/json')}><Icon name="save" size={14} />下载画布文档</button><p className="field-help">导出论文图可生成 SVG、PDF 或 PNG，并保留可重开的文件链接与导出收据。</p></section></>}
      </div><div className="inspector-footer"><Icon name="info" size={14} /><span>视觉编辑不修改模型源码</span></div></aside>
    </div>
    <footer className={`statusbar ${failure ? 'has-error' : ''}`}><span><i className={busy ? 'busy-dot' : 'live-dot'} />{failure || (busy ? '正在处理…' : notice)}</span><div>{selection.ids.length > 0 && <span>{selection.ids.length} 个已选</span>}<span>SVG SCENE v1</span><span>rev {current?.revision ?? 0}</span></div></footer>
    {review && <ReviewDialog base={review.base} transaction={review.transaction} busy={busy} error={reviewError} onApprove={() => void approveParameter()} onCommit={() => void commitParameter()} onClose={() => void closeReview()} />}
    {exportDocument && <ExportDialog document={exportDocument} capabilities={capabilities} onClose={() => setExportDocument(null)} />}
    {importOpen && <div className="modal-backdrop"><div className="import-modal" role="dialog" aria-modal="true" aria-labelledby="import-title"><div className="modal-heading"><div><div className="eyebrow">STATIC SOURCE IMPORT</div><h2 id="import-title">从 Python 源码开始</h2></div><button className="tool" onClick={() => setImportOpen(false)} aria-label="关闭导入"><Icon name="close" /></button></div><p>导入单文件 nn.Module。分析器只解析源码；不导入模块、不运行 forward。多文件工程可通过 CLI 分析后，读取生成的架构 JSON。</p><div className="import-fields"><label>模型类名<input value={entry} onChange={e => setEntry(e.target.value)} /></label><label>文件名<input value={filename} onChange={e => setFilename(e.target.value)} /></label><button onClick={() => fileRef.current?.click()}><Icon name="file" size={15} />读取 .py / 架构 JSON</button><input ref={fileRef} hidden type="file" accept=".py,.json" onChange={async e => { const file = e.target.files?.[0]; if (!file) return; try { if (file.size > 4_000_000) throw new Error('文件超过 4 MB 导入预算'); const text = await file.text(); if (file.name.endsWith('.json')) { const architecture = validateArchitecture(JSON.parse(text)); await openArchitecture(architecture); setExampleId(''); setImportOpen(false); } else { setSourceText(text); setFilename(file.name); } } catch (error) { setFailure(`导入失败：${String(error)}`); } e.target.value = ''; }} /></div><textarea aria-label="Python 源码" spellCheck={false} placeholder="import torch\nfrom torch import nn\n\nclass Model(nn.Module):\n    ..." value={sourceText} onChange={e => setSourceText(e.target.value)} />{failure && <p className="error-text">{failure}</p>}<div className="modal-actions"><button onClick={() => setImportOpen(false)}>取消</button><button className="primary" onClick={() => void importSource()} disabled={busy || !sourceText.trim()}>静态分析并打开画布</button></div></div></div>}
  </div>;
}

function TextField({ label, value, onCommit }: { label: string; value: string; onCommit: (value: string) => void }) {
  const [draft, setDraft] = useState(value);
  const cancelled = useRef(false);
  useEffect(() => setDraft(value), [value]);
  return <label className="text-field">{label && <span className="field-label">{label}</span>}<input aria-label={label || '图例文字'} value={draft} onChange={e => { cancelled.current = false; setDraft(e.target.value); }} onBlur={() => { if (!cancelled.current && draft !== value) onCommit(draft); cancelled.current = false; }} onKeyDown={e => { if (e.nativeEvent.isComposing) return; if (e.key === 'Enter') e.currentTarget.blur(); if (e.key === 'Escape') { cancelled.current = true; setDraft(value); e.currentTarget.blur(); } }} /></label>;
}

function TreeNode({ node, architecture, document, selected, onSelect, onExpand, depth = 0 }: { node: ArchitectureNode; architecture: Architecture; document: CanvasDocument; selected: string[]; onSelect: (id: string) => void; onExpand: (id: string, expanded: boolean) => void; depth?: number }) {
  const expanded = document.expandedIds.includes(node.id);
  return <div role="treeitem" aria-expanded={node.children.length ? expanded : undefined} aria-selected={selected.includes(node.id)}><div className={`tree-row ${selected.includes(node.id) ? 'selected' : ''}`} style={{ paddingLeft: 14 + depth * 13 }}><button className={`tree-toggle ${expanded ? 'open' : ''}`} disabled={!node.children.length} aria-label={`${expanded ? '收起' : '展开'} ${node.label}`} onClick={() => onExpand(node.id, !expanded)}><Icon name="chevron" size={11} /></button><button className="tree-label" onClick={() => onSelect(node.id)}><span className={`tree-node-dot ${node.category}`} /><span>{document.displayAliases[node.id] ?? node.label}</span>{node.repeat && <small>×{node.repeat.count}</small>}</button>{document.pinnedObjects.includes(node.id) && <Icon name="pin" size={10} />}</div>{expanded && node.children.map(id => { const child = architecture.nodes.find(n => n.id === id); return child ? <TreeNode key={id} node={child} architecture={architecture} document={document} selected={selected} onSelect={onSelect} onExpand={onExpand} depth={depth + 1} /> : null; })}</div>;
}
