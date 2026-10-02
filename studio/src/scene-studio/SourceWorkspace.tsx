import { AlertTriangle, FileCode2, GitCompareArrows, LoaderCircle, Save, ShieldCheck, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { SourceWorkspaceBuffer, StudioStatePayload } from "./domain/source-backed-scene";
import {
  discardSourceBuffer,
  discardSourceWorkspace,
  openSourceBuffer,
  saveSourceBuffer,
  validateSourceWorkspace,
} from "./api/source-workspace-api";
import { CodeMirrorEditor } from "./CodeMirrorEditor";

export interface SourceWorkspaceProps {
  source: StudioStatePayload;
  anchor?: { path: string; line: number } | null;
  onState: (state: unknown) => void;
  onClose: () => void;
}

export function SourceWorkspace({ source, anchor, onState, onClose }: SourceWorkspaceProps) {
  const workspace = source.source_workspace!;
  const [selectedPath, setSelectedPath] = useState("");
  const [buffer, setBuffer] = useState<SourceWorkspaceBuffer | null>(null);
  const [content, setContent] = useState("");
  const [view, setView] = useState<"editor" | "diff">("editor");
  const [busy, setBusy] = useState<"open" | "save" | "validate" | "discard-file" | "discard-all" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [height, setHeight] = useState(() => Math.min(520, Math.max(320, window.innerHeight * .48)));
  const requestSequence = useRef(0);
  const selectedFile = workspace.files.find((file) => file.path === selectedPath);
  const transactionActive = Boolean(source.transaction && !["committed", "discarded", "failed"].includes(source.transaction.state));
  const sourceReviewReady = source.transaction?.request.operation === "edit_source_buffers" && source.transaction.state === "review-ready";
  const localDirty = Boolean(buffer && content !== buffer.staged_content);
  const modifiedCount = workspace.files.filter((file) => file.state === "modified").length;

  const openPath = useCallback(async (path: string) => {
    if (!path) return;
    const sequence = ++requestSequence.current;
    setBusy("open");
    setError(null);
    setSelectedPath(path);
    try {
      const result = await openSourceBuffer(source, path);
      if (sequence !== requestSequence.current) return;
      setBuffer(result.buffer);
      setContent(result.buffer.staged_content);
      onState(result.state);
    } catch (requestError) {
      if (sequence !== requestSequence.current) return;
      setBuffer(null);
      setError(String(requestError));
    } finally {
      if (sequence === requestSequence.current) setBusy(null);
    }
  }, [onState, source]);

  useEffect(() => {
    const initial = workspace.files.find((file) => file.opened && file.state !== "readonly")
      ?? workspace.files.find((file) => file.state !== "readonly");
    setSelectedPath(initial?.path ?? "");
    setBuffer(null);
    setContent("");
    setView("editor");
    setError(null);
    if (initial) void openPath(initial.path);
  }, [workspace.workspace_id]);

  useEffect(() => {
    if (!anchor?.path || anchor.path === selectedPath) return;
    if (workspace.files.some((file) => file.path === anchor.path && file.state !== "readonly")) {
      void openPath(anchor.path);
    }
  }, [anchor?.path, openPath, selectedPath, workspace.files]);

  const saveDraft = async (baseState = source) => {
    if (!buffer || !localDirty) return { buffer, state: baseState };
    setBusy("save");
    setError(null);
    try {
      const result = await saveSourceBuffer(baseState, buffer, content);
      setBuffer(result.buffer);
      setContent(result.buffer.staged_content);
      onState(result.state);
      return result;
    } catch (requestError) {
      setError(String(requestError));
      return null;
    } finally {
      setBusy(null);
    }
  };

  const validateChanges = async () => {
    if (sourceReviewReady) return;
    const saved = localDirty ? await saveDraft() : { buffer, state: source };
    if (!saved) return;
    setBusy("validate");
    setError(null);
    try {
      onState(await validateSourceWorkspace(saved.state));
    } catch (requestError) {
      setError(String(requestError));
    } finally {
      setBusy(null);
    }
  };

  const discardFile = async () => {
    if (!buffer) return;
    setBusy("discard-file");
    setError(null);
    try {
      onState(await discardSourceBuffer(source, buffer.path));
      setBuffer(null);
      setContent("");
    } catch (requestError) {
      setError(String(requestError));
    } finally {
      setBusy(null);
    }
  };

  const discardAll = async () => {
    setBusy("discard-all");
    setError(null);
    try {
      onState(await discardSourceWorkspace(source));
      setBuffer(null);
      setContent("");
    } catch (requestError) {
      setError(String(requestError));
    } finally {
      setBusy(null);
    }
  };

  const resize = (event: React.PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    const move = (moveEvent: PointerEvent) => setHeight(Math.min(window.innerHeight - 70, Math.max(260, window.innerHeight - moveEvent.clientY)));
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  };

  const shortHash = (value: string | null) => value ? value.slice(0, 10) : "-";
  const anchorLine = anchor?.path === selectedPath ? anchor.line : null;
  const status = useMemo(() => ({
    clean: "干净",
    modified: "已修改",
    stale: "已过期",
    readonly: "只读",
  }), []);

  return <section className="source-workspace-drawer" style={{ height }} aria-label="源码工作区">
    <div className="source-workspace-resizer" onPointerDown={resize} aria-hidden="true" />
    <header>
      <div><FileCode2 size={15} /><strong>Source Workspace</strong><span className={workspace.state}>{workspace.state}</span></div>
      <div className="source-workspace-actions">
        <div className="source-view-switch"><button className={view === "editor" ? "active" : ""} onClick={() => setView("editor")}>编辑器</button><button className={view === "diff" ? "active" : ""} onClick={() => setView("diff")}>Staged diff</button></div>
        <button className="tool-button" disabled={!buffer || !localDirty || busy !== null || transactionActive || buffer?.state === "stale"} onClick={() => void saveDraft()}><Save size={13} />保存草稿</button>
        <button className="tool-button primary-command" disabled={busy !== null || workspace.state === "stale" || (!modifiedCount && !localDirty && !sourceReviewReady) || (transactionActive && !sourceReviewReady)} onClick={() => void validateChanges()}>{busy === "validate" ? <LoaderCircle className="spin" size={13} /> : <ShieldCheck size={13} />}{sourceReviewReady ? "已进入评审" : "验证修改"}</button>
        <button className="icon-button" title="关闭源码工作区" onClick={onClose}><X size={13} /></button>
      </div>
    </header>
    <div className="source-workspace-body">
      <aside className="source-workspace-files">
        <div className="source-file-list">{workspace.files.map((file) => <button key={file.path} className={`${file.path === selectedPath ? "active" : ""} ${file.state}`} title={file.readonly_reason ?? file.path} disabled={busy !== null || file.state === "readonly"} onClick={() => void openPath(file.path)}><FileCode2 size={12} /><span>{file.path}</span><b>{status[file.state]}</b></button>)}</div>
        <footer><span>{workspace.files.length} files · {modifiedCount} modified</span><button className="tool-button" disabled={busy !== null || (!modifiedCount && !transactionActive)} onClick={() => void discardAll()}><Trash2 size={12} />全部丢弃</button></footer>
      </aside>
      <main className="source-editor-pane">
        <div className="source-editor-path"><strong>{selectedPath || "未选择文件"}</strong>{selectedFile ? <span>{selectedFile.size.toLocaleString()} B</span> : null}<button className="icon-button" title="丢弃当前 buffer" disabled={!buffer || busy !== null} onClick={() => void discardFile()}><Trash2 size={12} /></button></div>
        {error ? <div className="source-workspace-error"><AlertTriangle size={13} />{error}</div> : null}
        {buffer ? <>
          <div className="source-hashes"><span>Base <code>{shortHash(buffer.base_sha256)}</code></span><span>Staged <code>{shortHash(buffer.staged_sha256)}</code></span><span>Working <code>{shortHash(buffer.working_sha256)}</code></span><b className={buffer.state}>{buffer.state}</b>{transactionActive ? <i><GitCompareArrows size={11} />transaction locked</i> : null}</div>
          {view === "editor" ? <CodeMirrorEditor value={content} path={buffer.path} readOnly={transactionActive || buffer.state === "stale"} anchorLine={anchorLine} onChange={setContent} /> : <pre className="source-staged-diff">{buffer.diff || "没有 staged 文本差异"}</pre>}
        </> : <div className="source-workspace-empty">{busy === "open" ? <LoaderCircle className="spin" size={17} /> : <FileCode2 size={17} />}<span>{busy === "open" ? "正在打开源码 buffer" : "源码 buffer 未打开"}</span></div>}
      </main>
    </div>
  </section>;
}
