import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from './api';
import type { GeneratedDraft } from './api';
import { Icon } from './icons';
import { addDraftNode, arrangeDraft, blankDraft, changeDraft, connectDraft, DRAFT_HEIGHT, DRAFT_WIDTH, draftHistory, draftRoutes, nextDraftPosition, parseDraftCache, portPoint, removeDraftNode, travelDraft } from './authoring';
import type { AuthoredDraft, DraftCatalog, DraftEndpoint, DraftFlow, DraftHistory, DraftModule, DraftParameter, DraftValue } from './authoring';
import './AuthoringStudio.css';
import { beginCameraPan, cameraAtPanInput } from './cameraGesture';
import type { CameraPan } from './cameraGesture';
import { fitDraftCamera, parseDraftField, resolveDraftFeedback } from './authoringFeedback';
import type { DraftFeedback } from './authoringFeedback';
import { draftPresets, draftPresetSize, draftPresetUnavailable, insertDraftPreset } from './authoringPresets';
import type { DraftPreset } from './authoringPresets';
import { draftPortPresentation } from './draftPortPresentation';

const CACHE = 'archcanvas.authored-workspace.v1';
type Camera = { x: number; y: number; zoom: number };
type Gesture = { type: 'node' | 'pan' | 'port'; pointer: number; clientX: number; clientY: number; camera: Camera; base: AuthoredDraft; pan?: CameraPan; nodeId?: string; endpoint?: DraftEndpoint };
function createBlank() { return blankDraft(`draft-${crypto.randomUUID()}`); }
function restored() {
  try {
    const stored = parseDraftCache(JSON.parse(localStorage.getItem(CACHE) ?? 'null'));
    if (stored) return stored;
  } catch { /* A damaged browser cache is never used as a source document. */ }
  return { draft: createBlank(), storageRevision: 0, savedRevision: -1 };
}

export function AuthoringStudio({ onClose, onOpen }: { onClose: () => void; onOpen: (generated: GeneratedDraft) => Promise<void> }) {
  const [initial] = useState(restored);
  const [history, setHistory] = useState(() => draftHistory(initial.draft));
  const [catalog, setCatalog] = useState<DraftCatalog | null>(null);
  const [storageRevision, setStorageRevision] = useState(initial.storageRevision);
  const [savedRevision, setSavedRevision] = useState(initial.savedRevision);
  const [selection, setSelection] = useState<{ node?: string; edge?: string }>({});
  const [camera, setCamera] = useState<Camera>({ x: 30, y: 30, zoom: 1 });
  const [preview, setPreview] = useState<AuthoredDraft | null>(null);
  const [connection, setConnection] = useState<{ endpoint: DraftEndpoint; x: number; y: number } | null>(null);
  const [tool, setTool] = useState<'select' | 'pan'>('select');
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('从左侧拖入输入、模块和输出；点击输出端口，再点击输入端口连接。');
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState<DraftFeedback | null>(null);
  const [invalidFields, setInvalidFields] = useState<string[]>([]);
  const [generated, setGenerated] = useState<GeneratedDraft | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const gesture = useRef<Gesture | null>(null);
  const currentRef = useRef(history); currentRef.current = history;
  const saving = useRef(false);
  const invalidFieldsRef = useRef<string[]>([]);
  const catalogRef = useRef(catalog); catalogRef.current = catalog;
  const draft = preview ?? history.draft;
  const selected = draft.nodes.find(node => node.id === selection.node);
  const selectedModule = catalog?.modules.find(module => module.kind === selected?.kind);
  const geometry = useMemo(() => catalog ? draftRoutes(draft, catalog) : { routes: [], overlaps: [], flow: 'horizontal' as const, nodeFlows: {} as Record<string, DraftFlow> }, [draft, catalog]);
  const dirty = history.draft.revision !== savedRevision;

  useEffect(() => {
    let alive = true;
    api.authoringCatalog().then(async value => {
      if (!alive) return;
      catalogRef.current = value; setCatalog(value);
      try { await api.validateDraft(initial.draft); }
      catch (reason) { if (alive && initial.draft === currentRef.current.draft) reportError(reason, '先前草稿尚未通过检查，编辑已保留：'); }
    }).catch(reason => { if (alive) setError(String(reason)); });
    return () => { alive = false; };
  }, [initial.draft]);
  useEffect(() => {
    try { localStorage.setItem(CACHE, JSON.stringify({ draft: history.draft, storageRevision, savedRevision })); }
    catch { setError('浏览器未能保留草稿；请使用“保存草稿”。'); }
  }, [history.draft, storageRevision, savedRevision]);

  function cancel() {
    const active = gesture.current; gesture.current = null; setPreview(null); setConnection(null);
    if (active?.type === 'pan') setCamera(active.camera);
    if (active && svgRef.current?.hasPointerCapture(active.pointer)) svgRef.current.releasePointerCapture(active.pointer);
  }
  function clearError() { setError(''); setFeedback(null); }
  function discardInvalidInput() {
    const message = '未提交的无效输入已放弃；草稿仍保留上次有效参数。';
    setNotice(message);
    setError(previous => previous && !previous.includes(message) ? `${previous} ${message}` : previous);
  }
  function focusDraftNode(id: string) {
    cancel(); const node = currentRef.current.draft.nodes.find(item => item.id === id), rect = svgRef.current?.getBoundingClientRect();
    if (!node || !rect) return;
    setSelection({ node: id });
    setCamera(old => { const zoom = Math.max(.7, Math.min(1, old.zoom)); return { zoom, x: rect.width / 2 - (node.position.x + DRAFT_WIDTH / 2) * zoom, y: rect.height / 2 - (node.position.y + DRAFT_HEIGHT / 2) * zoom }; });
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
  function add(module: DraftModule, position?: { x: number; y: number }) {
    if (busy) return;
    const rect = svgRef.current?.getBoundingClientRect();
    const center = rect ? point(rect.left + rect.width / 2, rect.top + rect.height / 2) : { x: 80, y: 80 };
    const at = position ?? nextDraftPosition(draft, { x: center.x - DRAFT_WIDTH / 2, y: center.y - DRAFT_HEIGHT / 2 });
    const id = `n_${crypto.randomUUID().replaceAll('-', '')}`;
    apply(value => addDraftNode(value, module, id, { x: Math.round(at.x), y: Math.round(at.y) }));
    setSelection({ node: id }); setNotice(`已添加 ${module.label}；在右侧编辑参数。`);
    if (rect && !position && (at.y * camera.zoom + camera.y + DRAFT_HEIGHT * camera.zoom > rect.height - 20)) setCamera(old => ({ ...old, y: rect.height / 2 - (at.y + DRAFT_HEIGHT / 2) * old.zoom }));
  }
  function addPreset(preset: DraftPreset, position?: { x: number; y: number }) {
    if (busy || !catalog) return;
    const rect = svgRef.current?.getBoundingClientRect(), size = draftPresetSize(preset);
    const center = rect ? point(rect.left + rect.width / 2, rect.top + rect.height / 2) : { x: 80 + size.width / 2, y: 130 };
    const at = position ?? { x: center.x - size.width / 2, y: center.y - size.height / 2 };
    try {
      const candidate = structuredClone(currentRef.current.draft), existing = candidate.nodes.length;
      const inserted = insertDraftPreset(candidate, catalog, preset.id, at);
      const next = apply(value => { value.nodes = candidate.nodes; value.edges = candidate.edges; });
      if (!next) return;
      setSelection({ node: inserted.inputNodeId }); fit(next);
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
    if (selection.node) apply(value => removeDraftNode(value, selection.node!));
    else if (selection.edge) apply(value => { value.edges = value.edges.filter(edge => edge.id !== selection.edge); });
    setSelection({});
  }
  async function save() {
    if (saving.current || busy || invalidFieldsRef.current.length) return;
    cancel(); saving.current = true; setBusy(true);
    const snapshot = currentRef.current.draft;
    try {
      const result = await api.saveDraft(snapshot, storageRevision);
      if (snapshot === currentRef.current.draft) { setStorageRevision(result.revision); setSavedRevision(snapshot.revision); setNotice('模型草稿已保存；可重开继续搭建。'); clearError(); }
    } catch (reason) { if (snapshot === currentRef.current.draft) reportError(reason, '保存失败，草稿已保留：'); }
    finally { saving.current = false; setBusy(false); }
  }
  async function reopen() {
    if (busy) return;
    const snapshot = currentRef.current.draft;
    cancel(); setBusy(true);
    try {
      const result = await api.draft(history.draft.id);
      if (snapshot === currentRef.current.draft) { const next = draftHistory(result.draft); currentRef.current = next; setHistory(next); setStorageRevision(result.revision); setSavedRevision(result.draft.revision); setSelection({}); setGenerated(null); clearError(); setNotice('已重开保存的模型草稿。'); fit(result.draft); }
    } catch (reason) { if (snapshot === currentRef.current.draft) reportError(reason); }
    finally { setBusy(false); }
  }
  async function generate() {
    if (busy || invalidFieldsRef.current.length) return;
    cancel(); setBusy(true); clearError();
    const snapshot = currentRef.current.draft;
    try {
      const result = await api.generateDraft(snapshot);
      if (snapshot === currentRef.current.draft) setGenerated(result);
    } catch (reason) { if (snapshot === currentRef.current.draft) reportError(reason); }
    finally { setBusy(false); }
  }
  function fit(documentToFit = currentRef.current.draft) {
    cancel(); const rect = svgRef.current?.getBoundingClientRect(); if (!rect) return;
    const routePoints = catalogRef.current ? draftRoutes(documentToFit, catalogRef.current).routes.flatMap(route => route.points) : [];
    setCamera(fitDraftCamera(documentToFit, rect, routePoints));
  }
  function arrange() { const next = apply(arrangeDraft); if (next) { fit(next); setNotice('已按连接排版并适合画布；Ctrl+Z 可撤销排版。'); } }
  function zoom(factor: number) {
    cancel(); const rect = svgRef.current?.getBoundingClientRect(); if (!rect) return;
    setCamera(old => { const next = Math.max(.15, Math.min(3, old.zoom * factor)); return { zoom: next, x: rect.width / 2 - (rect.width / 2 - old.x) * next / old.zoom, y: rect.height / 2 - (rect.height / 2 - old.y) * next / old.zoom }; });
  }
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.target as Element)?.closest('input,textarea,select') || busy || generated) return;
      if (event.key === 'Escape') { cancel(); setSelection({}); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); travel(event.shiftKey ? 'redo' : 'undo'); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); void save(); }
      if (event.key === 'Delete' || event.key === 'Backspace') { event.preventDefault(); deleteSelection(); }
      const move = { ArrowLeft: [-16, 0], ArrowRight: [16, 0], ArrowUp: [0, -16], ArrowDown: [0, 16] }[event.key];
      if (move && selection.node) { event.preventDefault(); apply(value => { const node = value.nodes.find(item => item.id === selection.node)!; node.position.x += move[0]; node.position.y += move[1]; }); }
    };
    const blur = () => cancel();
    window.addEventListener('keydown', key); window.addEventListener('blur', blur);
    return () => { window.removeEventListener('keydown', key); window.removeEventListener('blur', blur); };
  });
  function pointerDown(event: React.PointerEvent<SVGSVGElement>) {
    if (busy || gesture.current || event.button !== 0) return;
    const target = event.target as Element, port = target.closest('[data-draft-port]'), node = target.closest('[data-draft-node]'), edge = target.closest('[data-draft-edge]');
    const base = currentRef.current.draft;
    if (tool === 'pan') { setConnection(null); gesture.current = { type: 'pan', pointer: event.pointerId, clientX: event.clientX, clientY: event.clientY, camera, base, pan: beginCameraPan(camera, panInput(event)) }; }
    else if (port) {
      const endpoint = { nodeId: port.getAttribute('data-node')!, portId: port.getAttribute('data-draft-port')! };
      const module = catalog?.modules.find(item => item.kind === base.nodes.find(item => item.id === endpoint.nodeId)?.kind);
      if (module?.ports.find(item => item.id === endpoint.portId)?.direction === 'in') {
        if (connection) connect(connection.endpoint, endpoint); else setNotice('先点击一个输出端口，再选择此输入端口。'); return;
      }
      const p = point(event.clientX, event.clientY); setConnection({ endpoint, ...p });
      gesture.current = { type: 'port', pointer: event.pointerId, clientX: event.clientX, clientY: event.clientY, camera, base, endpoint };
    } else if (node) {
      setConnection(null); const nodeId = node.getAttribute('data-draft-node')!; setSelection({ node: nodeId });
      gesture.current = { type: 'node', pointer: event.pointerId, clientX: event.clientX, clientY: event.clientY, camera, base, nodeId };
    } else if (edge) { setSelection({ edge: edge.getAttribute('data-draft-edge')! }); setConnection(null); return; }
    else { setSelection({}); setConnection(null); return; }
    event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId);
  }
  function pointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const active = gesture.current;
    if (!active) { if (connection) setConnection(previous => previous && ({ ...previous, ...point(event.clientX, event.clientY) })); return; }
    if (active.pointer !== event.pointerId) return;
    const dx = event.clientX - active.clientX, dy = event.clientY - active.clientY;
    if (active.type === 'pan') { const next = cameraAtPanInput(active.pan!, panInput(event)); if (next) setCamera(next); }
    if (active.type === 'node') {
      const next = structuredClone(active.base), node = next.nodes.find(item => item.id === active.nodeId)!;
      node.position.x += Math.round(dx / active.camera.zoom); node.position.y += Math.round(dy / active.camera.zoom); setPreview(next);
    }
    if (active.type === 'port') setConnection(previous => previous && ({ ...previous, ...point(event.clientX, event.clientY) }));
  }
  function pointerUp(event: React.PointerEvent<SVGSVGElement>) {
    const active = gesture.current; if (!active || active.pointer !== event.pointerId) return;
    gesture.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (active.type === 'node') {
      const dx = Math.round((event.clientX - active.clientX) / active.camera.zoom), dy = Math.round((event.clientY - active.clientY) / active.camera.zoom);
      apply(value => { const node = value.nodes.find(item => item.id === active.nodeId)!; node.position.x += dx; node.position.y += dy; });
    } else if (active.type === 'pan') {
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
  const categories: Record<string, string> = { io: '输入与输出', dense: '全连接', activation: '激活函数', operator: '基础算子', regularization: '正则化', reshape: '形状变换', convolution: '卷积', pooling: '池化', normalization: '归一化', embedding: '嵌入', merge: '合并与分支' };
  const query = search.trim().toLowerCase();
  const matches = catalog?.modules.filter(module => `${module.kind} ${module.label} ${module.description}`.toLowerCase().includes(query)) ?? [];
  const presetMatches = draftPresets.filter(preset => `${preset.id} ${preset.label} ${preset.description}`.toLowerCase().includes(query));
  const groups = [...new Set(matches.map(module => module.category))];
  const connectionNode = draft.nodes.find(node => node.id === connection?.endpoint.nodeId), connectionModule = catalog?.modules.find(module => module.kind === connectionNode?.kind);
  const start = connection && connectionNode && connectionModule ? portPoint(connectionNode, connectionModule, connection.endpoint.portId, geometry.nodeFlows[connectionNode.id] ?? 'horizontal') : null;
  const blocked = geometry.routes.filter(route => route.blockedBy.length);

  return <div className="authoring-studio">
    <header className="authoring-header"><div><b>ArchCanvas</b><span>模型搭建</span></div><input aria-label="模型草稿名称" value={history.draft.title} disabled={busy} onChange={event => apply(value => { value.title = event.target.value; })} /><span className="authoring-save-state">{dirty ? '有未保存编辑' : '草稿已保存'}</span><button disabled={busy || !storageRevision} onClick={() => void reopen()}>重开已保存</button><button disabled={busy || !catalog || !!invalidFields.length} onClick={() => void save()}><Icon name="save" size={15} />保存草稿</button><button className="primary" disabled={busy || !catalog || !draft.nodes.length || !!invalidFields.length} onClick={() => void generate()}>生成模型与论文图</button><button disabled={busy} onClick={onClose}>返回制图</button></header>
    <div className="authoring-body">
      <aside className="module-palette"><div className="palette-intro"><span className="eyebrow">MODULE LIBRARY</span><h2>常用模块 <small>{catalog?.modules.length ?? 0}</small></h2><p>拖入画布，或点击添加。<br />输入 → 计算模块 → 输出</p><input aria-label="搜索模块" placeholder="搜索模块或网络，如 Linear / CNN" value={search} onChange={event => setSearch(event.target.value)} /><button disabled={busy} onClick={() => { cancel(); const next = draftHistory(createBlank()); currentRef.current = next; setHistory(next); setStorageRevision(0); setSavedRevision(-1); setSelection({}); setGenerated(null); setCamera({ x: 30, y: 30, zoom: 1 }); clearError(); }}>新建空白模型</button></div><div className="palette-list">{!catalog ? <p role="status" className="palette-empty">正在加载模块库…</p> : !matches.length && !presetMatches.length && <div role="status" className="palette-empty"><b>没有找到匹配的模块或网络</b><p>尝试中文名称或英文类型，如“卷积”、Linear 或 MLP。当前模块库尚不支持 Attention 和 LSTM。</p><button onClick={() => setSearch('')}>清空搜索</button></div>}{!!presetMatches.length && <section className="preset-section" aria-label="网络起点"><h3>网络起点 <span>{draftPresets.length}</span></h3><p className="preset-intro">{draft.nodes.length ? '添加一个独立网络。' : '从完整网络开始搭建。'}所有基础模块与连线都可修改。</p>{presetMatches.map(preset => { const unavailable = draftPresetUnavailable(preset, catalog); return <button key={preset.id} aria-label={`添加 ${preset.label}`} className="preset-card" disabled={busy || !!unavailable} draggable={!busy && !unavailable} onDragStart={event => { event.dataTransfer.setData('application/x-archcanvas-preset', preset.id); event.dataTransfer.effectAllowed = 'copy'; }} onClick={() => addPreset(preset)} title={unavailable ?? `${preset.description}；输入 ${preset.input}，输出 ${preset.output}`}><span className="preset-heading"><b>{preset.label}</b><Icon name="plus" size={13} /></span><span className="preset-description">{preset.description} · {preset.nodes.length} 模块</span><small>输入 {preset.input}<br />输出 {preset.output}</small>{unavailable && <span className="preset-unavailable">{unavailable}</span>}</button>; })}<p className="preset-note">形状是可编辑的声明；生成前会静态检查，模型尚未执行。</p></section>}{groups.map(group => <section key={group}><h3>{categories[group] ?? group}</h3>{matches.filter(module => module.category === group).map(module => <button key={module.kind} aria-label={`添加 ${module.kind}`} className="module-card" disabled={busy} draggable={!busy} onDragStart={event => { event.dataTransfer.setData('application/x-archcanvas-module', module.kind); event.dataTransfer.effectAllowed = 'copy'; }} onClick={() => add(module)} title={module.description}><span className={`module-dot kind-${module.category}`} /><span><b>{module.kind}</b><small>{module.label}</small></span><Icon name="plus" size={13} /></button>)}</section>)}</div><div className="palette-note">常用模型的无环草稿。参数和连线通过静态检查后，生成新模型。</div></aside>
      <main className="authoring-main"><div className="authoring-toolbar"><button aria-pressed={tool === 'select'} onClick={() => { cancel(); setTool('select'); }}><Icon name="arrow" size={16} />选择</button><button aria-pressed={tool === 'pan'} onClick={() => { cancel(); setTool('pan'); }}><Icon name="hand" size={16} />平移</button><button aria-label="撤销草稿" disabled={busy || !history.past.length} onClick={() => travel('undo')}><Icon name="undo" size={16} /></button><button aria-label="重做草稿" disabled={busy || !history.future.length} onClick={() => travel('redo')}><Icon name="redo" size={16} /></button><button disabled={busy || !draft.nodes.length} onClick={arrange}>按连接排版</button><button onClick={() => fit()}><Icon name="fit" size={16} />适合画布</button><div className="authoring-zoom"><button aria-label="草稿缩小" onClick={() => zoom(1 / 1.2)}>−</button><button aria-label="草稿缩放百分比" onClick={() => zoom(1 / camera.zoom)}>{Math.round(camera.zoom * 100)}%</button><button aria-label="草稿放大" onClick={() => zoom(1.2)}>+</button></div></div>
        {(geometry.overlaps.length > 0 || blocked.length > 0) && <div className="draft-layout-warning" role="status">{geometry.overlaps.length ? `${geometry.overlaps.length} 组模块重叠。` : ''}{blocked.length ? `${blocked.length} 条连线无法避开模块。` : ''}可移动模块或使用“按连接排版”。</div>}
        <div className="draft-viewport" onDragOver={event => { event.preventDefault(); event.dataTransfer.dropEffect = 'copy'; }} onDrop={event => { event.preventDefault(); const preset = draftPresets.find(item => item.id === event.dataTransfer.getData('application/x-archcanvas-preset')); if (preset) { const at = point(event.clientX, event.clientY); addPreset(preset, { x: at.x - DRAFT_WIDTH / 2, y: at.y - 30 }); return; } const module = catalog?.modules.find(item => item.kind === event.dataTransfer.getData('application/x-archcanvas-module')); if (module) { const at = point(event.clientX, event.clientY); add(module, { x: at.x - DRAFT_WIDTH / 2, y: at.y - 30 }); } }}>
          <svg ref={svgRef} aria-label="模型搭建画布" data-draft-flow={geometry.flow} className={tool === 'pan' ? 'draft-pan' : ''} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={cancel} onLostPointerCapture={() => { if (gesture.current) cancel(); }}>
            <defs><pattern id="draft-grid" width={20 * camera.zoom} height={20 * camera.zoom} patternUnits="userSpaceOnUse" x={camera.x} y={camera.y}><circle cx="1" cy="1" r=".8" fill="#cedbd2" /></pattern><marker id="draft-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#628572" /></marker></defs><rect width="100%" height="100%" fill="url(#draft-grid)" />
            <g transform={`translate(${camera.x} ${camera.y}) scale(${camera.zoom})`}>
              {geometry.routes.map(route => <g key={route.id} data-draft-edge={route.id} className={selection.edge === route.id ? 'draft-edge selected' : 'draft-edge'}><path d={route.path} fill="none" stroke="transparent" strokeWidth="14" /><path d={route.path} fill="none" strokeWidth="1.8" markerEnd="url(#draft-arrow)" /></g>)}
              {draft.nodes.map(node => { const module = catalog?.modules.find(item => item.kind === node.kind); if (!module) return null; return <g key={node.id} data-draft-node={node.id} transform={`translate(${node.position.x} ${node.position.y})`} className={`draft-node ${selection.node === node.id ? 'selected' : ''} ${feedback?.target?.nodeId === node.id ? 'has-error' : ''}`} data-draft-error={feedback?.target?.nodeId === node.id ? 'true' : undefined}><rect width={DRAFT_WIDTH} height={DRAFT_HEIGHT} rx="9" /><rect className="draft-node-cap" x="1" y="1" width={DRAFT_WIDTH - 2} height="36" rx="8" /><text x="13" y="23" className="draft-node-title">{node.label.length > 19 ? `${node.label.slice(0, 18)}…` : node.label}</text><text x="13" y="92" className="draft-node-kind">{node.kind}</text>{feedback?.target?.nodeId === node.id && <g className="draft-error-badge"><circle cx="160" cy="21" r="9" /><text x="160" y="25" textAnchor="middle">!</text></g>}{module.ports.map(port => {
                const flow = geometry.nodeFlows[node.id] ?? 'horizontal';
                const p = portPoint(node, module, port.id, flow), x = p.x - node.position.x, y = p.y - node.position.y;
                const peerCount = module.ports.filter(peer => peer.direction === port.direction).length;
                const presentation = draftPortPresentation(port, x, y, flow, peerCount > 1 ? (flow === 'horizontal' ? 36 : DRAFT_WIDTH) / (peerCount + 1) : Infinity);
                const active = connection?.endpoint.nodeId === node.id && connection.endpoint.portId === port.id;
                return <g key={port.id} data-node={node.id} data-draft-port={port.id} data-draft-port-flow={flow} className={`draft-port ${port.direction} ${active ? 'active' : ''} ${feedback?.target?.nodeId === node.id && feedback.target.portId === port.id ? 'has-error' : ''}`} role="button" tabIndex={0} aria-pressed={active} aria-label={`${node.label} ${port.name} ${port.direction === 'in' ? '输入端口' : '输出端口'}`} onKeyDown={event => {
                  if (event.key !== 'Enter' && event.key !== ' ') return;
                  event.preventDefault(); event.stopPropagation(); if (busy || tool === 'pan') return;
                  if (port.direction === 'out') { cancel(); setConnection({ endpoint: { nodeId: node.id, portId: port.id }, ...p }); setNotice('连接起点已选中；点击目标输入端口，Escape 取消。'); }
                  else if (connection) connect(connection.endpoint, { nodeId: node.id, portId: port.id });
                  else setNotice('先点击一个输出端口，再选择此输入端口。');
                }}><rect className="draft-port-hit" x={presentation.hit.x} y={presentation.hit.y} width={presentation.hit.width} height={presentation.hit.height} rx="4" fill="transparent" stroke="none" pointerEvents="all" /><circle className="draft-port-dot" cx={x} cy={y} r="5" /><text x={presentation.labelX} y={presentation.labelY} textAnchor={presentation.textAnchor}>{port.name}</text></g>;
              })}</g>; })}
              {start && connection && <path d={`M ${start.x} ${start.y} L ${connection.x} ${connection.y}`} stroke="#b8864e" strokeWidth="2" strokeDasharray="6 4" fill="none" pointerEvents="none" />}
            </g>
          </svg>{!draft.nodes.length && <div className="draft-empty"><span>从零搭建一个模型</span><h2>把第一个 Input 拖到这里</h2><p>再加入 Linear、激活函数与 Output。<br />也可以从左侧“网络起点”加入完整 MLP、CNN 或残差网络。</p><button disabled={!catalog} onClick={() => { const input = catalog?.modules.find(module => module.kind === 'Input'); if (input) add(input, { x: 80, y: 120 }); }}>添加输入</button></div>}
        </div><div className="draft-help">拖动模块 · 输出端口 → 输入端口 · 方向键移动 16 · Delete 删除 · Escape 取消 · Ctrl+Z 撤销</div>
      </main>
      <aside className="draft-inspector"><span className="eyebrow">MODEL PROPERTIES</span>{selected && selectedModule ? <><h2>{selected.kind}</h2><label className="draft-field">显示名称<input aria-label="模块显示名称" value={selected.label} disabled={busy} onChange={event => apply(value => { value.nodes.find(node => node.id === selected.id)!.label = event.target.value; })} /></label><div className="draft-param-fields">{selectedModule.parameters.map(parameter => <DraftField key={`${selected.id}:${parameter.name}`} parameter={parameter} value={selected.parameters[parameter.name]} disabled={busy} error={feedback?.target?.nodeId === selected.id && feedback.target.parameter === parameter.name ? feedback.message : undefined} onValidity={invalid => fieldValidity(selected.id, parameter.name, invalid)} onDiscardInvalid={discardInvalidInput} onCommit={value => apply(next => { next.nodes.find(node => node.id === selected.id)!.parameters[parameter.name] = value; })} />)}</div><p className="draft-description">{selectedModule.description}</p>{selected.kind === 'Linear' && <p className="draft-parameter-help">例如输入形状为 [1, 16] 时，in_features 应为 16；out_features 决定输出最后一维。</p>}<div className="draft-coordinate">{(['x', 'y'] as const).map(axis => <label key={axis}>{axis.toUpperCase()}<input aria-label={`模块 ${axis.toUpperCase()} 坐标`} type="number" value={selected.position[axis]} disabled={busy} onChange={event => { if (event.target.value && Number.isFinite(Number(event.target.value))) apply(value => { value.nodes.find(node => node.id === selected.id)!.position[axis] = Number(event.target.value); }); }} /></label>)}</div><button disabled={busy} onClick={deleteSelection}>删除模块及相连连线</button></> : selection.edge ? <><h2>张量连线</h2><p>此连线定义模块的输入来源。</p><button disabled={busy} onClick={deleteSelection}>删除连线</button></> : <><h2>每一步都在图上完成</h2><ol><li>拖入 Input，设置输入形状。</li><li>拖入常用模块，编辑参数。</li><li>连接端口，加入 Output。</li><li>保存草稿，生成模型与论文图。</li></ol><p>形状与数据类型会在生成时检查。当前是静态建模，尚未运行训练。</p></>}<div className="draft-summary"><b>{draft.nodes.length}</b> 模块 <b>{draft.edges.length}</b> 连接</div></aside>
    </div><footer className={`authoring-status ${error ? 'error' : ''}`} role={error || invalidFields.length ? 'alert' : 'status'}>{busy ? '正在检查模型…' : invalidFields.length ? '参数输入尚未有效：请修正标记字段，或按 Escape 恢复上次有效值，再保存或生成。' : error || notice}{!busy && error && feedback?.target && <button onClick={() => focusDraftNode(feedback.target!.nodeId)}>定位出错模块</button>}{!busy && error && feedback?.technical && <details><summary>技术详情</summary><span>{feedback.technical}</span></details>}</footer>
    {generated && <div className="modal-backdrop"><section className="authoring-review" role="dialog" aria-modal="true" aria-label="生成的新模型"><div className="modal-heading"><div><span className="eyebrow">NEW MODEL</span><h2>模型已生成并静态核对</h2></div><button onClick={() => setGenerated(null)} disabled={busy}><Icon name="close" /></button></div><p>节点、端口、参数和连接已与新源码的分析结果核对。接下来可打开论文图、编辑样式并导出；模型尚未执行。</p><pre>{generated.source}</pre><div className="modal-actions"><button disabled={busy} onClick={() => setGenerated(null)}>继续搭建</button><button className="primary" disabled={busy} onClick={async () => { setBusy(true); try { await onOpen(generated); } catch (reason) { reportError(reason); setBusy(false); } }}>创建新工作副本并打开论文图</button></div></section></div>}
  </div>;
}

function DraftField({ parameter, value, disabled, error, onCommit, onValidity, onDiscardInvalid }: { parameter: DraftParameter; value: DraftValue; disabled: boolean; error?: string; onCommit: (value: DraftValue) => void; onValidity: (invalid: boolean) => void; onDiscardInvalid: () => void }) {
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
  const errorId = `draft-parameter-${parameter.name}-error`, help = invalid || error;
  return <label className={`draft-field ${help ? 'has-error' : ''}`} data-draft-parameter={parameter.name}>{parameter.name}{parameter.type === 'boolean' ? <input type="checkbox" aria-label={parameter.name} checked={value === true} disabled={disabled} onChange={event => onCommit(event.target.checked)} /> : parameter.type === 'choice' ? <select aria-label={parameter.name} value={String(value)} disabled={disabled} onChange={event => onCommit(event.target.value)}>{parameter.options?.map(option => <option key={option} value={option}>{option}</option>)}</select> : <input aria-label={parameter.name} aria-invalid={!!help} aria-describedby={help ? errorId : undefined} inputMode={parameter.type === 'integer-array' ? 'text' : 'decimal'} value={text} disabled={disabled} onChange={event => { setText(event.target.value); validity(parseDraftField(event.target.value, parameter) === null); }} onBlur={commit} onKeyDown={event => { if (event.key === 'Enter') event.currentTarget.blur(); if (event.key === 'Escape') restore(); }} />}{help && <small id={errorId} role="alert">{help}</small>}</label>;
}
