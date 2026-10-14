import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import './PreviewStudio.css';

export type PreviewSource = {
  schema: 'archcanvas-preview-source/1'; caseId: string; title: string; entry: string;
  files: Record<string, string>; evidence?: Record<string, unknown>; profile?: unknown;
};
export type PreviewSnapshot = { graph?: Record<string, unknown>; adapter?: unknown; caseId?: string; [key: string]: unknown };
export type PreviewSourceResult = { source?: PreviewSource; bundle?: unknown; document?: PreviewSnapshot };
export type PreviewHandle = {
  load: (bundle: unknown) => Promise<void>;
  source: () => Promise<PreviewSourceResult>;
  snapshot: () => Promise<PreviewSnapshot>;
  svg: (nodeId?: string) => Promise<string>;
  visual: (operations: Record<string, unknown>[]) => Promise<void>;
  save: () => Promise<void>;
  focus: (location: { nodeId?: string; sourcePath?: string; line?: number; annotationId?: string }) => void;
  command: (command: string, payload?: Record<string, unknown>) => void;
};
type Pending = { resolve: (value: Record<string, unknown>) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> };

/** The copied editor owns its graph, routing worker, history and browser storage. */
export const PreviewStudio = forwardRef<PreviewHandle, {
  visible: boolean;
  onState: (document: PreviewSnapshot) => void;
  onSelection: (selection: Record<string, unknown>) => void;
  onEditSource: (result: PreviewSourceResult) => void;
  onError: (message: string) => void;
}>(function PreviewStudio({ visible, onState, onSelection, onEditSource, onError }, ref) {
  const iframe = useRef<HTMLIFrameElement>(null);
  const ready = useRef(false);
  const callbacks = useRef({ onState, onSelection, onEditSource, onError });
  callbacks.current = { onState, onSelection, onEditSource, onError };
  const pending = useRef(new Map<string, Pending>());
  const readyWaiters = useRef(new Set<() => void>());
  const [connected, setConnected] = useState(false);
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
      const timer = setTimeout(() => { readyWaiters.current.delete(done); reject(new Error('预览引擎尚未连接，请重新加载页面。')); }, 30000);
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
    snapshot: async () => {
      const result = await request('snapshot');
      return result.document as PreviewSnapshot;
    },
    svg: async nodeId => { const result = await request('svg', { ...(nodeId ? { nodeId } : {}) }); return String(result.svg); },
    visual: async operations => { await request('visual', { operations }); },
    save: async () => { await request('save'); },
    focus: location => post('focus', location),
    command: (command, payload) => post(command, payload),
  }));
  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.source !== iframe.current?.contentWindow ||
          !event.data || typeof event.data.type !== 'string' || !event.data.type.startsWith('archcanvas:preview:')) return;
      const message = event.data as Record<string, unknown>;
      const type = String(message.type).slice('archcanvas:preview:'.length);
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
      if ((type === 'state' || type === 'saved') && message.document) callbacks.current.onState({
        ...(message.document as PreviewSnapshot), dirty: message.dirty,
        canUndo: Number(message.undo) > 0, canRedo: Number(message.redo) > 0,
        busy: message.busy, selectedNodes: message.selectedNodes, selectedEdges: message.selectedEdges, caseInfo: message.case,
      });
      if (type === 'selection') callbacks.current.onSelection(message);
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
    {!connected && <div className="preview-loading" role="status">正在载入模型图与布线引擎…</div>}
    <iframe ref={iframe} title="ArchCanvas 模型预览与连线编辑器"
      src={sourceUrl} onLoad={() => post('hello')} />
  </section>;
});
