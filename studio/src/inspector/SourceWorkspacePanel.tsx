import { useEffect, useRef, useState } from "react";
import { AlertTriangle, FileCode2, LockKeyhole, Save, ShieldCheck, Trash2, X } from "lucide-react";

import { postStudioJson } from "../api/studio-client";
import type {
  SourceTransaction,
  SourceWorkspaceBuffer,
  SourceWorkspaceFile,
  StudioState,
} from "../app/studio-types";

export interface SourceWorkspacePanelProps {
  workspace: StudioState["source_workspace"];
  transaction: SourceTransaction | null;
  sessionNonce?: string;
  tx: (english: string, chinese: string) => string;
  onState: (state: StudioState) => void;
  onActivity: (message: string) => void;
  onShowDiff: () => void;
}

export function SourceWorkspacePanel({ workspace, transaction, sessionNonce, tx, onState, onActivity, onShowDiff }: SourceWorkspacePanelProps) {
  const [selectedPath, setSelectedPath] = useState("");
  const [buffer, setBuffer] = useState<SourceWorkspaceBuffer | null>(null);
  const [content, setContent] = useState("");
  const [view, setView] = useState<"editor" | "diff">("editor");
  const [busy, setBusy] = useState<"open" | "save" | "validate" | "discard-file" | "discard-all" | null>(null);
  const [error, setError] = useState("");
  const lineNumbers = useRef<HTMLPreElement>(null);
  const requestSequence = useRef(0);
  const selectedFile = workspace.files.find((file) => file.path === selectedPath);
  const transactionActive = Boolean(transaction && !["committed", "discarded", "failed"].includes(transaction.state));
  const sourceReviewReady = transaction?.request.operation === "edit_source_buffers" && transaction.state === "review-ready";
  const localDirty = Boolean(buffer && content !== buffer.staged_content);
  const modifiedCount = workspace.files.filter((file) => file.state === "modified").length;

  async function openPath(path: string) {
    if (!path) return;
    const sequence = ++requestSequence.current;
    setBusy("open");
    setError("");
    setSelectedPath(path);
    try {
      const result = await postStudioJson<{ buffer: SourceWorkspaceBuffer; state: StudioState }>(
        "/api/source-workspace/open", { path }, { nonce: sessionNonce },
      );
      if (sequence !== requestSequence.current) return;
      setBuffer(result.buffer);
      setContent(result.buffer.staged_content);
      onState({ ...result.state, session_nonce: result.state.session_nonce ?? sessionNonce });
    } catch (requestError) {
      if (sequence !== requestSequence.current) return;
      setBuffer(null);
      setError(String(requestError));
    } finally {
      if (sequence === requestSequence.current) setBusy(null);
    }
  }

  useEffect(() => {
    const initial = workspace.files.find((file) => file.opened && file.state !== "readonly")
      ?? workspace.files.find((file) => file.state !== "readonly");
    setSelectedPath(initial?.path ?? "");
    setBuffer(null);
    setContent("");
    setView("editor");
    setError("");
    if (initial) void openPath(initial.path);
  }, [workspace.workspace_id]);

  async function saveDraft(): Promise<SourceWorkspaceBuffer | null> {
    if (!buffer || !localDirty) return buffer;
    setBusy("save");
    setError("");
    try {
      const result = await postStudioJson<{ buffer: SourceWorkspaceBuffer; state: StudioState }>(
        "/api/source-workspace/save",
        { path: buffer.path, content, base_sha256: buffer.base_sha256, expected_revision: workspace.revision },
        { nonce: sessionNonce },
      );
      setBuffer(result.buffer);
      setContent(result.buffer.staged_content);
      onState({ ...result.state, session_nonce: result.state.session_nonce ?? sessionNonce });
      onActivity(`${tx("Saved source draft", "已保存源码草稿")} · ${buffer.path}`);
      return result.buffer;
    } catch (requestError) {
      setError(String(requestError));
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function validateChanges() {
    if (sourceReviewReady) {
      onShowDiff();
      return;
    }
    if (localDirty && !await saveDraft()) return;
    setBusy("validate");
    setError("");
    try {
      const state = await postStudioJson<StudioState>("/api/source-workspace/validate", {}, { nonce: sessionNonce });
      onState(state);
      onActivity(tx("Source workspace passed validation and is ready for review", "源码工作区已通过验证，可以审查"));
      onShowDiff();
    } catch (requestError) {
      setError(String(requestError));
    } finally {
      setBusy(null);
    }
  }

  async function discardFile() {
    if (!buffer) return;
    setBusy("discard-file");
    setError("");
    try {
      const state = await postStudioJson<StudioState>("/api/source-workspace/buffer/discard", {
        path: buffer.path, expected_revision: workspace.revision,
      }, { nonce: sessionNonce });
      onState(state);
      onActivity(`${tx("Discarded source draft", "已丢弃源码草稿")} · ${buffer.path}`);
      setBuffer(null);
      setContent("");
    } catch (requestError) {
      setError(String(requestError));
    } finally {
      setBusy(null);
    }
  }

  async function discardWorkspace() {
    setBusy("discard-all");
    setError("");
    try {
      const state = await postStudioJson<StudioState>("/api/source-workspace/discard", {}, { nonce: sessionNonce });
      onState(state);
      onActivity(tx("Discarded all staged source changes", "已丢弃全部暂存源码修改"));
      setBuffer(null);
      setContent("");
    } catch (requestError) {
      setError(String(requestError));
    } finally {
      setBusy(null);
    }
  }

  const shortHash = (value: string | null) => value ? value.slice(0, 12) : tx("Unavailable", "不可用");
  const stateLabel = (state: SourceWorkspaceFile["state"]) => ({
    clean: tx("Clean", "干净"), modified: tx("Modified", "已修改"), stale: tx("Stale", "已过期"), readonly: tx("Read only", "只读"),
  })[state];
  const lineCount = Math.max(1, content.split("\n").length);

  return <div className="source-workspace">
    <aside className="source-workspace-files">
      <header><strong>{tx("Snapshot files", "快照文件")}</strong><span className={`source-workspace-state ${workspace.state}`}>{workspace.state}</span></header>
      <div className="source-file-list">{workspace.files.map((file) => <button key={file.path} className={`${file.path === selectedPath ? "active" : ""} ${file.state}`} title={file.readonly_reason ?? file.path} onClick={() => { setBuffer(null); setContent(""); void openPath(file.path); }} disabled={busy !== null || file.state === "readonly"}>
        <FileCode2 size={13} /><span>{file.path}</span><b>{stateLabel(file.state)}</b>
      </button>)}</div>
      <footer><span>{workspace.files.length} {tx("files", "个文件")} · {modifiedCount} {tx("modified", "个已修改")}</span><button disabled={busy !== null || (!modifiedCount && !transactionActive)} onClick={() => void discardWorkspace()}><Trash2 size={13} />{tx("Discard all", "全部丢弃")}</button></footer>
    </aside>
    <section className="source-workspace-editor">
      <header className="source-editor-toolbar"><div><strong>{selectedPath || tx("No source file", "没有源码文件")}</strong>{selectedFile && <span>{selectedFile.size.toLocaleString()} B</span>}</div>
        <div className="source-view-switch"><button className={view === "editor" ? "active" : ""} onClick={() => setView("editor")}>{tx("Editor", "编辑器")}</button><button className={view === "diff" ? "active" : ""} onClick={() => setView("diff")}>{tx("Staged diff", "暂存差异")}</button></div>
        <button className="source-action" disabled={!buffer || !localDirty || busy !== null || transactionActive || buffer?.state === "stale"} onClick={() => void saveDraft()}><Save size={13} />{tx("Save draft", "保存草稿")}</button>
        <button className="source-action primary" disabled={busy !== null || workspace.state === "stale" || (!modifiedCount && !localDirty && !sourceReviewReady) || (transactionActive && !sourceReviewReady)} onClick={() => void validateChanges()}><ShieldCheck size={13} />{sourceReviewReady ? tx("Review changes", "审查修改") : busy === "validate" ? tx("Validating", "正在验证") : tx("Validate changes", "验证修改")}</button>
        <button className="icon-button" title={tx("Discard selected buffer", "丢弃所选缓冲区")} aria-label={tx("Discard selected buffer", "丢弃所选缓冲区")} disabled={!buffer || busy !== null} onClick={() => void discardFile()}><X size={13} /></button>
      </header>
      {error && <div className="source-workspace-error"><AlertTriangle size={13} />{error}</div>}
      {buffer ? <><div className="source-hashes"><span>Base <code title={buffer.base_sha256}>{shortHash(buffer.base_sha256)}</code></span><span>Staged <code title={buffer.staged_sha256}>{shortHash(buffer.staged_sha256)}</code></span><span>Working <code title={buffer.working_sha256}>{shortHash(buffer.working_sha256)}</code></span><b className={buffer.state}>{buffer.state}</b></div>
        {view === "editor" ? <div className="source-code-editor"><pre ref={lineNumbers} aria-hidden="true">{Array.from({ length: lineCount }, (_, index) => index + 1).join("\n")}</pre><textarea aria-label={tx("Staged source content", "暂存源码内容")} spellCheck={false} wrap="off" value={content} readOnly={transactionActive || buffer.state === "stale"} onScroll={(event) => { if (lineNumbers.current) lineNumbers.current.scrollTop = event.currentTarget.scrollTop; }} onChange={(event) => setContent(event.target.value)} /></div> : <pre className="source-staged-diff">{buffer.diff || tx("No staged textual changes", "没有暂存文本修改")}</pre>}
      </> : selectedFile?.state === "readonly" ? <div className="source-workspace-empty"><LockKeyhole size={18} /><span>{selectedFile.readonly_reason}</span></div> : <div className="source-workspace-empty"><FileCode2 size={18} /><span>{busy === "open" ? tx("Opening source buffer", "正在打开源码缓冲区") : tx("Buffer is closed", "缓冲区已关闭")}</span>{busy !== "open" && selectedPath && <button onClick={() => void openPath(selectedPath)}>{tx("Open file", "打开文件")}</button>}</div>}
    </section>
  </div>;
}
