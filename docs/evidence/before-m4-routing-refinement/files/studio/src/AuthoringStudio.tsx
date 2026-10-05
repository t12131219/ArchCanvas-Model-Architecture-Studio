import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from './api';
import type { GeneratedDraft } from './api';
import { Icon } from './icons';
import { addDraftNode, arrangeDraft, blankDraft, changeDraft, connectDraft, DRAFT_HEIGHT, DRAFT_WIDTH, draftHistory, draftRoutes, nextDraftPosition, parseDraftCache, portPoint, removeDraftNode, travelDraft } from './authoring';
import type { AuthoredDraft, DraftCatalog, DraftEndpoint, DraftHistory, DraftModule, DraftParameter, DraftValue } from './authoring';
import './AuthoringStudio.css';
import { beginCameraPan, cameraAtPanInput } from './cameraGesture';
import type { CameraPan } from './cameraGesture';

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
  const [generated, setGenerated] = useState<GeneratedDraft | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const gesture = useRef<Gesture | null>(null);
  const currentRef = useRef(history); currentRef.current = history;
  const saving = useRef(false);
  const draft = preview ?? history.draft;
  const selected = draft.nodes.find(node => node.id === selection.node);
  const selectedModule = catalog?.modules.find(module => module.kind === selected?.kind);
  const geometry = useMemo(() => catalog ? draftRoutes(draft, catalog) : { routes: [], overlaps: [] }, [draft, catalog]);
  const dirty = history.draft.revision !== savedRevision;

  useEffect(() => {
    let alive = true;
    api.authoringCatalog().then(async value => {
      try { await api.validateDraft(initial.draft); }
      catch (reason) { if (alive) setError(`先前草稿尚未通过检查，编辑已保留：${String(reason)}`); }
      if (alive) setCatalog(value);
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
  function apply(update: (draft: AuthoredDraft) => void) {
    cancel();
    try { const next = changeDraft(currentRef.current, update); currentRef.current = next; setHistory(next); setGenerated(null); setError(''); }
    catch (reason) { setError(String(reason)); }
  }
  function travel(action: 'undo' | 'redo') { cancel(); const next = travelDraft(currentRef.current, action); currentRef.current = next; setHistory(next); setGenerated(null); setError(''); }
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
  function connect(source: DraftEndpoint, target: DraftEndpoint) {
    if (!catalog) return;
    // Validate against a copy first: errors are reported outside React's updater.
    try {
      const value = structuredClone(currentRef.current.draft);
      const id = `e_${crypto.randomUUID().replaceAll('-', '')}`;
      connectDraft(value, catalog, source, target, id);
      apply(next => { next.edges = value.edges; }); setNotice('已建立张量连接；可选择连线删除。');
    } catch (reason) { cancel(); setError(String(reason)); }
  }
  function deleteSelection() {
    if (busy) return;
    if (selection.node) apply(value => removeDraftNode(value, selection.node!));
    else if (selection.edge) apply(value => { value.edges = value.edges.filter(edge => edge.id !== selection.edge); });
    setSelection({});
  }
  async function save() {
    if (saving.current) return;
    cancel(); saving.current = true; setBusy(true);
    const snapshot = currentRef.current.draft;
    try {
      const result = await api.saveDraft(snapshot, storageRevision);
      if (snapshot.id === currentRef.current.draft.id) { setStorageRevision(result.revision); setSavedRevision(snapshot.revision); }
      setNotice('模型草稿已保存；可重开继续搭建。'); setError('');
    } catch (reason) { setError(`保存失败，草稿已保留：${String(reason)}`); }
    finally { saving.current = false; setBusy(false); }
  }
  async function reopen() {
    cancel(); setBusy(true);
    try {
      const result = await api.draft(history.draft.id);
      setHistory(draftHistory(result.draft)); setStorageRevision(result.revision); setSavedRevision(result.draft.revision); setSelection({}); setGenerated(null); setError(''); setNotice('已重开保存的模型草稿。');
    } catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  async function generate() {
    cancel(); setBusy(true); setError('');
    const snapshot = currentRef.current.draft;
    try {
      const result = await api.generateDraft(snapshot);
      if (snapshot === currentRef.current.draft) setGenerated(result);
    } catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  function fit() {
    cancel(); const rect = svgRef.current?.getBoundingClientRect(); if (!rect) return;
    if (!draft.nodes.length) { setCamera({ x: 30, y: 30, zoom: 1 }); return; }
    const xs = draft.nodes.map(node => node.position.x), ys = draft.nodes.map(node => node.position.y);
    const left = Math.min(...xs) - 32, top = Math.min(...ys) - 32, width = Math.max(...xs) + DRAFT_WIDTH + 32 - left, height = Math.max(...ys) + DRAFT_HEIGHT + 32 - top;
    const zoom = Math.max(.15, Math.min(1, (rect.width - 30) / width, (rect.height - 30) / height));
    setCamera({ x: (rect.width - width * zoom) / 2 - left * zoom, y: (rect.height - height * zoom) / 2 - top * zoom, zoom });
  }
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
  const groups = [...new Set(catalog?.modules.filter(module => `${module.kind} ${module.label} ${module.description}`.toLowerCase().includes(search.toLowerCase())).map(module => module.category))];
  const connectionNode = draft.nodes.find(node => node.id === connection?.endpoint.nodeId), connectionModule = catalog?.modules.find(module => module.kind === connectionNode?.kind);
  const start = connection && connectionNode && connectionModule ? portPoint(connectionNode, connectionModule, connection.endpoint.portId) : null;
  const blocked = geometry.routes.filter(route => route.blockedBy.length);

  return <div className="authoring-studio">
    <header className="authoring-header"><div><b>ArchCanvas</b><span>模型搭建</span></div><input aria-label="模型草稿名称" value={history.draft.title} disabled={busy} onChange={event => apply(value => { value.title = event.target.value; })} /><span className="authoring-save-state">{dirty ? '有未保存编辑' : '草稿已保存'}</span><button disabled={busy || !storageRevision} onClick={() => void reopen()}>重开已保存</button><button disabled={busy || !catalog} onClick={() => void save()}><Icon name="save" size={15} />保存草稿</button><button className="primary" disabled={busy || !catalog || !draft.nodes.length} onClick={() => void generate()}>生成模型与论文图</button><button disabled={busy} onClick={onClose}>返回制图</button></header>
    <div className="authoring-body">
      <aside className="module-palette"><div className="palette-intro"><span className="eyebrow">MODULE LIBRARY</span><h2>常用模块 <small>{catalog?.modules.length ?? 0}</small></h2><p>拖入画布，或点击添加。<br />输入 → 计算模块 → 输出</p><input aria-label="搜索模块" placeholder="搜索模块，如 Linear / 卷积" value={search} onChange={event => setSearch(event.target.value)} /><button disabled={busy} onClick={() => { cancel(); setHistory(draftHistory(createBlank())); setStorageRevision(0); setSavedRevision(-1); setSelection({}); setGenerated(null); setCamera({ x: 30, y: 30, zoom: 1 }); setError(''); }}>新建空白模型</button></div><div className="palette-list">{groups.map(group => <section key={group}><h3>{categories[group] ?? group}</h3>{catalog!.modules.filter(module => module.category === group && `${module.kind} ${module.label} ${module.description}`.toLowerCase().includes(search.toLowerCase())).map(module => <button key={module.kind} aria-label={`添加 ${module.kind}`} className="module-card" disabled={busy} draggable={!busy} onDragStart={event => { event.dataTransfer.setData('application/x-archcanvas-module', module.kind); event.dataTransfer.effectAllowed = 'copy'; }} onClick={() => add(module)} title={module.description}><span className={`module-dot kind-${module.category}`} /><span><b>{module.kind}</b><small>{module.label}</small></span><Icon name="plus" size={13} /></button>)}</section>)}</div><div className="palette-note">常用模型的无环草稿。参数和连线通过静态检查后，生成新模型。</div></aside>
      <main className="authoring-main"><div className="authoring-toolbar"><button aria-pressed={tool === 'select'} onClick={() => { cancel(); setTool('select'); }}><Icon name="arrow" size={16} />选择</button><button aria-pressed={tool === 'pan'} onClick={() => { cancel(); setTool('pan'); }}><Icon name="hand" size={16} />平移</button><button aria-label="撤销草稿" disabled={busy || !history.past.length} onClick={() => travel('undo')}><Icon name="undo" size={16} /></button><button aria-label="重做草稿" disabled={busy || !history.future.length} onClick={() => travel('redo')}><Icon name="redo" size={16} /></button><button disabled={busy || !draft.nodes.length} onClick={() => { try { const next = structuredClone(history.draft); arrangeDraft(next); apply(value => { value.nodes = next.nodes; }); setNotice('已按连接顺序排版；可以撤销。'); } catch (reason) { setError(String(reason)); } }}>按连接排版</button><button onClick={fit}><Icon name="fit" size={16} />适合画布</button><div className="authoring-zoom"><button aria-label="草稿缩小" onClick={() => zoom(1 / 1.2)}>−</button><button aria-label="草稿缩放百分比" onClick={() => zoom(1 / camera.zoom)}>{Math.round(camera.zoom * 100)}%</button><button aria-label="草稿放大" onClick={() => zoom(1.2)}>+</button></div></div>
        {(geometry.overlaps.length > 0 || blocked.length > 0) && <div className="draft-layout-warning" role="status">{geometry.overlaps.length ? `${geometry.overlaps.length} 组模块重叠。` : ''}{blocked.length ? `${blocked.length} 条连线无法避开模块。` : ''}可移动模块或使用“按连接排版”。</div>}
        <div className="draft-viewport" onDragOver={event => { event.preventDefault(); event.dataTransfer.dropEffect = 'copy'; }} onDrop={event => { event.preventDefault(); const module = catalog?.modules.find(item => item.kind === event.dataTransfer.getData('application/x-archcanvas-module')); if (module) { const at = point(event.clientX, event.clientY); add(module, { x: at.x - DRAFT_WIDTH / 2, y: at.y - 30 }); } }}>
          <svg ref={svgRef} aria-label="模型搭建画布" className={tool === 'pan' ? 'draft-pan' : ''} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={cancel} onLostPointerCapture={() => { if (gesture.current) cancel(); }}>
            <defs><pattern id="draft-grid" width={20 * camera.zoom} height={20 * camera.zoom} patternUnits="userSpaceOnUse" x={camera.x} y={camera.y}><circle cx="1" cy="1" r=".8" fill="#cedbd2" /></pattern><marker id="draft-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#628572" /></marker></defs><rect width="100%" height="100%" fill="url(#draft-grid)" />
            <g transform={`translate(${camera.x} ${camera.y}) scale(${camera.zoom})`}>
              {geometry.routes.map(route => <g key={route.id} data-draft-edge={route.id} className={selection.edge === route.id ? 'draft-edge selected' : 'draft-edge'}><path d={route.path} fill="none" stroke="transparent" strokeWidth="14" /><path d={route.path} fill="none" strokeWidth="1.8" markerEnd="url(#draft-arrow)" /></g>)}
              {draft.nodes.map(node => { const module = catalog?.modules.find(item => item.kind === node.kind); if (!module) return null; return <g key={node.id} data-draft-node={node.id} transform={`translate(${node.position.x} ${node.position.y})`} className={`draft-node ${selection.node === node.id ? 'selected' : ''}`}><rect width={DRAFT_WIDTH} height={DRAFT_HEIGHT} rx="9" /><rect className="draft-node-cap" x="1" y="1" width={DRAFT_WIDTH - 2} height="36" rx="8" /><text x="13" y="23" className="draft-node-title">{node.label.length > 19 ? `${node.label.slice(0, 18)}…` : node.label}</text><text x="13" y="92" className="draft-node-kind">{node.kind}</text>{module.ports.map(port => { const p = portPoint(node, module, port.id), x = p.x - node.position.x, y = p.y - node.position.y; return <g key={port.id} data-node={node.id} data-draft-port={port.id} className={`draft-port ${port.direction}`} role="button" aria-label={`${node.label} ${port.name} ${port.direction === 'in' ? '输入端口' : '输出端口'}`}><circle cx={x} cy={y} r="11" fill="transparent" stroke="none" /><circle cx={x} cy={y} r="5" /><text x={port.direction === 'in' ? x + 12 : x - 12} y={y + 3} textAnchor={port.direction === 'in' ? 'start' : 'end'}>{port.name}</text></g>; })}</g>; })}
              {start && connection && <path d={`M ${start.x} ${start.y} L ${connection.x} ${connection.y}`} stroke="#b8864e" strokeWidth="2" strokeDasharray="6 4" fill="none" pointerEvents="none" />}
            </g>
          </svg>{!draft.nodes.length && <div className="draft-empty"><span>从零搭建一个模型</span><h2>把第一个 Input 拖到这里</h2><p>再加入 Linear、激活函数与 Output。<br />从圆形输出端口拖到输入端口，或依次点击两个端口。</p><button disabled={!catalog} onClick={() => { const input = catalog?.modules.find(module => module.kind === 'Input'); if (input) add(input, { x: 80, y: 120 }); }}>添加输入</button></div>}
        </div><div className="draft-help">拖动模块 · 输出端口 → 输入端口 · 方向键移动 16 · Delete 删除 · Escape 取消 · Ctrl+Z 撤销</div>
      </main>
      <aside className="draft-inspector"><span className="eyebrow">MODEL PROPERTIES</span>{selected && selectedModule ? <><h2>{selected.kind}</h2><label className="draft-field">显示名称<input aria-label="模块显示名称" value={selected.label} disabled={busy} onChange={event => apply(value => { value.nodes.find(node => node.id === selected.id)!.label = event.target.value; })} /></label><div className="draft-param-fields">{selectedModule.parameters.map(parameter => <DraftField key={`${selected.id}:${parameter.name}`} parameter={parameter} value={selected.parameters[parameter.name]} disabled={busy} onCommit={value => apply(next => { next.nodes.find(node => node.id === selected.id)!.parameters[parameter.name] = value; })} />)}</div><p className="draft-description">{selectedModule.description}</p><div className="draft-coordinate">{(['x', 'y'] as const).map(axis => <label key={axis}>{axis.toUpperCase()}<input aria-label={`模块 ${axis.toUpperCase()} 坐标`} type="number" value={selected.position[axis]} disabled={busy} onChange={event => { if (event.target.value && Number.isFinite(Number(event.target.value))) apply(value => { value.nodes.find(node => node.id === selected.id)!.position[axis] = Number(event.target.value); }); }} /></label>)}</div><button disabled={busy} onClick={deleteSelection}>删除模块及相连连线</button></> : selection.edge ? <><h2>张量连线</h2><p>此连线定义模块的输入来源。</p><button disabled={busy} onClick={deleteSelection}>删除连线</button></> : <><h2>每一步都在图上完成</h2><ol><li>拖入 Input，设置输入形状。</li><li>拖入常用模块，编辑参数。</li><li>连接端口，加入 Output。</li><li>保存草稿，生成模型与论文图。</li></ol><p>形状与数据类型会在生成时检查。当前是静态建模，尚未运行训练。</p></>}<div className="draft-summary"><b>{draft.nodes.length}</b> 模块 <b>{draft.edges.length}</b> 连接</div></aside>
    </div><footer className={`authoring-status ${error ? 'error' : ''}`} role={error ? 'alert' : 'status'}>{busy ? '正在检查模型…' : error || notice}</footer>
    {generated && <div className="modal-backdrop"><section className="authoring-review" role="dialog" aria-modal="true" aria-label="生成的新模型"><div className="modal-heading"><div><span className="eyebrow">NEW MODEL</span><h2>模型已生成并静态核对</h2></div><button onClick={() => setGenerated(null)} disabled={busy}><Icon name="close" /></button></div><p>节点、端口、参数和连接已与新源码的分析结果核对。接下来可打开论文图、编辑样式并导出；模型尚未执行。</p><pre>{generated.source}</pre><div className="modal-actions"><button disabled={busy} onClick={() => setGenerated(null)}>继续搭建</button><button className="primary" disabled={busy} onClick={async () => { setBusy(true); try { await onOpen(generated); } catch (reason) { setError(String(reason)); setBusy(false); } }}>创建新工作副本并打开论文图</button></div></section></div>}
  </div>;
}

function DraftField({ parameter, value, disabled, onCommit }: { parameter: DraftParameter; value: DraftValue; disabled: boolean; onCommit: (value: DraftValue) => void }) {
  const [text, setText] = useState(Array.isArray(value) ? value.join(', ') : String(value));
  const [invalid, setInvalid] = useState('');
  useEffect(() => { setText(Array.isArray(value) ? value.join(', ') : String(value)); setInvalid(''); }, [value]);
  function commit() {
    const next = parameter.type === 'integer-array' ? text.split(',').map(item => Number(item.trim())) : Number(text);
    const values = Array.isArray(next) ? next : [next];
    if (!text.trim() || values.some(item => !Number.isFinite(item) || ((parameter.type === 'integer' || parameter.type === 'integer-array') && !Number.isInteger(item)) || (parameter.min !== undefined && item < parameter.min) || (parameter.max !== undefined && item > parameter.max))) { setInvalid('请输入范围内的有效数值。'); return; }
    setInvalid(''); if (JSON.stringify(next) !== JSON.stringify(value)) onCommit(next);
  }
  return <label className="draft-field">{parameter.name}{parameter.type === 'boolean' ? <input type="checkbox" aria-label={parameter.name} checked={value === true} disabled={disabled} onChange={event => onCommit(event.target.checked)} /> : parameter.type === 'choice' ? <select aria-label={parameter.name} value={String(value)} disabled={disabled} onChange={event => onCommit(event.target.value)}>{parameter.options?.map(option => <option key={option} value={option}>{option}</option>)}</select> : <input aria-label={parameter.name} inputMode={parameter.type === 'integer-array' ? 'text' : 'decimal'} value={text} disabled={disabled} onChange={event => { setText(event.target.value); setInvalid(''); }} onBlur={commit} onKeyDown={event => { if (event.key === 'Enter') event.currentTarget.blur(); if (event.key === 'Escape') { setText(Array.isArray(value) ? value.join(', ') : String(value)); setInvalid(''); } }} />}{invalid && <small role="alert">{invalid}</small>}</label>;
}
