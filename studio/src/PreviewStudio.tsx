import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import './PreviewStudio.css';

export type PreviewSource = {
  schema: 'archcanvas-preview-source/1'; caseId: string; title: string; entry: string;
  files: Record<string, string>; evidence?: Record<string, unknown>; profile?: unknown;
};
export type PreviewSnapshot = { graph?: Record<string, unknown>; adapter?: unknown; caseId?: string; snapshotRevision?: number;
  sourceIdentity?: { caseId?: string; sourceSha256?: string | null; irSha256?: string | null }; interactionMode?: 'compat' | 'realtime'; showGhost?: boolean; showObstacles?: boolean; [key: string]: unknown };
export type PreviewSourceResult = { source?: PreviewSource; bundle?: unknown; document?: PreviewSnapshot };
export type PreviewHandle = {
  load: (bundle: unknown) => Promise<void>;
  source: () => Promise<PreviewSourceResult>;
  openCase: (caseId: string) => Promise<PreviewSnapshot>;
  snapshot: () => Promise<PreviewSnapshot>;
  svg: (nodeId?: string) => Promise<string>;
  visual: (operations: Record<string, unknown>[]) => Promise<void>;
  author: (operation: Record<string, unknown>) => Promise<PreviewSnapshot>;
  save: () => Promise<void>;
  focus: (location: { nodeId?: string; sourcePath?: string; line?: number; annotationId?: string; additive?: boolean }) => void;
  command: (command: string, payload?: Record<string, unknown>) => void;
};
type Pending = { resolve: (value: Record<string, unknown>) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> };

/** The copied editor owns its graph, routing worker, history and browser storage. */
export const PreviewStudio = forwardRef<PreviewHandle, {
  visible: boolean;
  onState: (document: PreviewSnapshot) => void;
  onInteraction: (status: Record<string, unknown>) => void;
  onSelection: (selection: Record<string, unknown>) => void;
  onEditSource: (result: PreviewSourceResult) => void;
  onError: (message: string) => void;
  onSave: () => void;
  onNotice: (message: string, error: boolean) => void;
}>(function PreviewStudio({ visible, onState, onInteraction, onSelection, onEditSource, onError, onSave, onNotice }, ref) {
  const iframe = useRef<HTMLIFrameElement>(null);
  const ready = useRef(false);
  const callbacks = useRef({ onState, onInteraction, onSelection, onEditSource, onError, onSave, onNotice });
  callbacks.current = { onState, onInteraction, onSelection, onEditSource, onError, onSave, onNotice };
  const pending = useRef(new Map<string, Pending>());
  const readyWaiters = useRef(new Set<() => void>());
  // Toolbar commands are fire-and-forget at the React call sites, but they
  // still need the same ordering guarantee as request-based operations.  A
  // command posted before the iframe handshake would otherwise disappear.
  const commandSequence = useRef(Promise.resolve());
  const [connected, setConnected] = useState(false);
  const [startup, setStartup] = useState({ message: '正在载入模型图与布线引擎…', canCancel: false });
  const [sourceUrl] = useState(() => {
    const base = '/preview/yworks_edge_router_lab/index.html?embed=1&surface=canvas';
    try {
      const active = JSON.parse(localStorage.getItem('archcanvas.active-canvas.v2') ?? 'null');
      return typeof active?.previewCaseId === 'string' ? `${base}&case=${encodeURIComponent(active.previewCaseId)}` : base;
    } catch { return base; }
  });

  function post(type: string, payload: Record<string, unknown> = {}) {
    iframe.current?.contentWindow?.postMessage({ type: `archcanvas:preview:${type}`, ...payload }, window.location.origin);
  }
  function waitReady() {
    if (ready.current) return Promise.resolve();
    return new Promise<void>((resolve, reject) => {
      const done = () => { clearTimeout(timer); readyWaiters.current.delete(done); resolve(); };
      const timer = setTimeout(() => { readyWaiters.current.delete(done); reject(new Error('预览引擎尚未连接，请重新加载页面。')); }, 120000);
      readyWaiters.current.add(done);
    });
  }
  async function request(type: string, payload: Record<string, unknown> = {}) {
    await waitReady();
    const requestId = crypto.randomUUID();
    return new Promise<Record<string, unknown>>((resolve, reject) => {
      const timer = setTimeout(() => { pending.current.delete(requestId); reject(new Error('预览处理超时；当前图与编辑草稿仍保留。')); }, 60000);
      pending.current.set(requestId, { resolve, reject, timer });
      post(type, { ...payload, requestId });
    });
  }
  useImperativeHandle(ref, () => ({
    load: async bundle => { await request('load', { bundle }); },
    source: async () => await request('request-source') as PreviewSourceResult,
    openCase: async caseId => (await request('open-case', { caseId })).document as PreviewSnapshot,
    snapshot: async () => {
      const result = await request('snapshot');
      return result.document as PreviewSnapshot;
    },
    svg: async nodeId => { const result = await request('svg', { ...(nodeId ? { nodeId } : {}) }); return String(result.svg); },
    visual: async operations => { await request('visual', { operations }); },
    author: async operation => { const result = await request('authoring', operation); return result.document as PreviewSnapshot; },
    save: async () => { await request('save'); },
    // Keep focus behind a preceding creation/load request, including when the
    // bridge is already ready. A direct post can overtake request's await.
    focus: location => { void request('focus', location).catch(error => callbacks.current.onError(String(error))); },
    command: (command, payload = {}) => {
      // Gesture cancellation must precede the next visual request even while busy.
      if ((command === 'cancel-gesture' || command === 'cancel-operation') && ready.current) { post(command, { ...payload, requestId: crypto.randomUUID() }); return; }
      const run = commandSequence.current.then(async () => {
        await waitReady();
        post(command, { ...payload, requestId: crypto.randomUUID() });
      });
      commandSequence.current = run.catch(() => {});
      void run.catch(error => callbacks.current.onError(String(error)));
    },
  }));
  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.source !== iframe.current?.contentWindow ||
          !event.data || typeof event.data.type !== 'string' || !event.data.type.startsWith('archcanvas:preview:')) return;
      const message = event.data as Record<string, unknown>;
      const type = String(message.type).slice('archcanvas:preview:'.length);
      if (type === 'progress' && !ready.current) setStartup({ message: String(message.message ?? '正在恢复模型…'), canCancel: message.canCancel === true });
      if (type === 'ready') {
        ready.current = true; setConnected(true);
        for (const done of readyWaiters.current) done();
      }
      if (type === 'loaded' && message.document) callbacks.current.onState({
        ...(message.document as PreviewSnapshot), dirty: message.dirty, canUndo: Number(message.undo) > 0, canRedo: Number(message.redo) > 0,
      });
      const id = typeof message.requestId === 'string' ? message.requestId : '';
      const task = pending.current.get(id);
      if (task) {
        pending.current.delete(id); clearTimeout(task.timer);
        if (type === 'error' || type === 'source-unavailable') task.reject(new Error(String(message.error ?? message.message ?? '当前示例没有可编辑模型源码。')));
        else task.resolve(message);
      }
      if ((type === 'state' || type === 'saved' || type === 'applied' && message.command === 'apply-layout') && message.document) callbacks.current.onState({
        ...(message.document as PreviewSnapshot), dirty: message.dirty,
        canUndo: Number(message.undo) > 0, canRedo: Number(message.redo) > 0,
        busy: message.busy, canCancel: message.canCancel, dragging: message.dragging, selectedNodes: message.selectedNodes, selectedEdges: message.selectedEdges, caseInfo: message.case,
      });
      if (type === 'interaction') callbacks.current.onInteraction(message);
      if (type === 'notice') callbacks.current.onNotice(String(message.message ?? ''), Boolean(message.error));
      if (type === 'selection') callbacks.current.onSelection(message);
      if (type === 'shortcut' && message.action === 'save') callbacks.current.onSave();
      if (type === 'edit-source') callbacks.current.onEditSource(message as PreviewSourceResult);
      if (type === 'error' && !task) callbacks.current.onError(String(message.error ?? message.message ?? '预览处理失败'));
    };
    window.addEventListener('message', receive);
    return () => {
      window.removeEventListener('message', receive);
      for (const task of pending.current.values()) { clearTimeout(task.timer); task.reject(new Error('预览已关闭。')); }
      pending.current.clear();
    };
  }, []);
  return <section className="prototype-preview" hidden={!visible} aria-label="模型架构预览">
    {!connected && <div className="preview-loading" role="status">{startup.message}{startup.canCancel && <button onClick={() => post('cancel-operation', { requestId: crypto.randomUUID() })}>取消恢复操作</button>}</div>}
    <iframe ref={iframe} title="ArchCanvas 模型预览与连线编辑器"
      src={sourceUrl} onLoad={() => post('hello')} />
  </section>;
});
