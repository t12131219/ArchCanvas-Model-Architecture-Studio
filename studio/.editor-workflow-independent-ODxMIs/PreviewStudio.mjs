import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';

/** The copied editor owns its graph, routing worker, history and browser storage. */
export const PreviewStudio = forwardRef(function PreviewStudio({ visible, onState, onSelection, onEditSource, onError, onSave, onNotice }, ref) {
    const iframe = useRef(null);
    const ready = useRef(false);
    const callbacks = useRef({ onState, onSelection, onEditSource, onError, onSave, onNotice });
    callbacks.current = { onState, onSelection, onEditSource, onError, onSave, onNotice };
    const pending = useRef(new Map());
    const readyWaiters = useRef(new Set());
    // Toolbar commands are fire-and-forget at the React call sites, but they
    // still need the same ordering guarantee as request-based operations.  A
    // command posted before the iframe handshake would otherwise disappear.
    const commandSequence = useRef(Promise.resolve());
    const [connected, setConnected] = useState(false);
    const [sourceUrl] = useState(() => {
        const base = '/preview/yworks_edge_router_lab/index.html?embed=1&surface=canvas';
        try {
            const active = JSON.parse(localStorage.getItem('archcanvas.active-canvas.v2') ?? 'null');
            return typeof active?.previewCaseId === 'string' ? `${base}&case=${encodeURIComponent(active.previewCaseId)}` : base;
        }
        catch {
            return base;
        }
    });
    function post(type, payload = {}) {
        iframe.current?.contentWindow?.postMessage({ type: `archcanvas:preview:${type}`, ...payload }, window.location.origin);
    }
    function waitReady() {
        if (ready.current)
            return Promise.resolve();
        return new Promise((resolve, reject) => {
            const done = () => { clearTimeout(timer); readyWaiters.current.delete(done); resolve(); };
            const timer = setTimeout(() => { readyWaiters.current.delete(done); reject(new Error('预览引擎尚未连接，请重新加载页面。')); }, 30000);
            readyWaiters.current.add(done);
        });
    }
    async function request(type, payload = {}) {
        await waitReady();
        const requestId = crypto.randomUUID();
        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => { pending.current.delete(requestId); reject(new Error('预览处理超时；当前图与编辑草稿仍保留。')); }, 60000);
            pending.current.set(requestId, { resolve, reject, timer });
            post(type, { ...payload, requestId });
        });
    }
    useImperativeHandle(ref, () => ({
        load: async (bundle) => { await request('load', { bundle }); },
        source: async () => await request('request-source'),
        snapshot: async () => {
            const result = await request('snapshot');
            return result.document;
        },
        svg: async (nodeId) => { const result = await request('svg', { ...(nodeId ? { nodeId } : {}) }); return String(result.svg); },
        visual: async (operations) => { await request('visual', { operations }); },
        save: async () => { await request('save'); },
        // Keep focus behind a preceding creation/load request, including when the
        // bridge is already ready. A direct post can overtake request's await.
        focus: location => { void request('focus', location).catch(error => callbacks.current.onError(String(error))); },
        command: (command, payload = {}) => {
            const run = commandSequence.current.then(async () => {
                await waitReady();
                post(command, { ...payload, requestId: crypto.randomUUID() });
            });
            commandSequence.current = run.catch(() => { });
            void run.catch(error => callbacks.current.onError(String(error)));
        },
    }));
    useEffect(() => {
        const receive = (event) => {
            if (event.origin !== window.location.origin || event.source !== iframe.current?.contentWindow ||
                !event.data || typeof event.data.type !== 'string' || !event.data.type.startsWith('archcanvas:preview:'))
                return;
            const message = event.data;
            const type = String(message.type).slice('archcanvas:preview:'.length);
            if (type === 'ready') {
                ready.current = true;
                setConnected(true);
                for (const done of readyWaiters.current)
                    done();
            }
            if (type === 'loaded' && message.document)
                callbacks.current.onState({
                    ...message.document, dirty: message.dirty, canUndo: Number(message.undo) > 0, canRedo: Number(message.redo) > 0,
                });
            const id = typeof message.requestId === 'string' ? message.requestId : '';
            const task = pending.current.get(id);
            if (task) {
                pending.current.delete(id);
                clearTimeout(task.timer);
                if (type === 'error' || type === 'source-unavailable')
                    task.reject(new Error(String(message.error ?? message.message ?? '当前示例没有可编辑模型源码。')));
                else
                    task.resolve(message);
            }
            if ((type === 'state' || type === 'saved') && message.document)
                callbacks.current.onState({
                    ...message.document, dirty: message.dirty,
                    canUndo: Number(message.undo) > 0, canRedo: Number(message.redo) > 0,
                    busy: message.busy, selectedNodes: message.selectedNodes, selectedEdges: message.selectedEdges, caseInfo: message.case,
                });
            if (type === 'notice')
                callbacks.current.onNotice(String(message.message ?? ''), Boolean(message.error));
            if (type === 'selection')
                callbacks.current.onSelection(message);
            if (type === 'shortcut' && message.action === 'save')
                callbacks.current.onSave();
            if (type === 'edit-source')
                callbacks.current.onEditSource(message);
            if (type === 'error' && !task)
                callbacks.current.onError(String(message.error ?? message.message ?? '预览处理失败'));
        };
        window.addEventListener('message', receive);
        return () => {
            window.removeEventListener('message', receive);
            for (const task of pending.current.values()) {
                clearTimeout(task.timer);
                task.reject(new Error('预览已关闭。'));
            }
            pending.current.clear();
        };
    }, []);
    return _jsxs("section", { className: "prototype-preview", hidden: !visible, "aria-label": "\u6A21\u578B\u67B6\u6784\u9884\u89C8", children: [!connected && _jsx("div", { className: "preview-loading", role: "status", children: "\u6B63\u5728\u8F7D\u5165\u6A21\u578B\u56FE\u4E0E\u5E03\u7EBF\u5F15\u64CE\u2026" }), _jsx("iframe", { ref: iframe, title: "ArchCanvas \u6A21\u578B\u9884\u89C8\u4E0E\u8FDE\u7EBF\u7F16\u8F91\u5668", src: sourceUrl, onLoad: () => post('hello') })] });
});
