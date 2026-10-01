import React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  FileJson2,
  LockKeyhole,
  RefreshCw,
  Save,
  Send,
  ShieldCheck,
  X,
} from "lucide-react";

import { postStudioJson } from "../api/studio-client";
import type {
  ContractMaintenanceState,
  ContractMigration,
  StudioState,
} from "../app/studio-types";
import {
  MODULE_REGISTRY,
  moduleDefinitionLabel,
  resolveDefinitionId,
} from "../module-registry/registry";
import type { ModuleDefinition } from "../module-registry/types";

interface ContractMaintenanceDialogProps {
  open: boolean;
  state: StudioState;
  tx: (english: string, chinese: string) => string;
  onClose: () => void;
  onState: (state: StudioState) => void;
  onActivity: (message: string) => void;
}

function parseObject<T>(source: string, label: string): T {
  const value = JSON.parse(source) as unknown;
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} must be a JSON object.`);
  }
  return value as T;
}

export function ContractMaintenanceDialog({
  open,
  state,
  tx,
  onClose,
  onState,
  onActivity,
}: ContractMaintenanceDialogProps) {
  const maintenance = state.contract_maintenance;
  const [definitionId, setDefinitionId] = React.useState(
    MODULE_REGISTRY.definitions[0]?.definition_id ?? "",
  );
  const [candidateSource, setCandidateSource] = React.useState("");
  const [migrationSource, setMigrationSource] = React.useState("");
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!maintenance?.draft) return;
    setCandidateSource(JSON.stringify(maintenance.draft.candidate, null, 2));
    setMigrationSource(
      maintenance.draft.migration
        ? JSON.stringify(maintenance.draft.migration, null, 2)
        : "",
    );
    setError("");
  }, [maintenance?.draft?.draft_id, maintenance?.draft?.revision]);

  if (!open) return null;

  async function request(
    endpoint: string,
    payload: Record<string, unknown>,
    label: string,
  ): Promise<StudioState | null> {
    setBusy(endpoint);
    setError("");
    try {
      const next = await postStudioJson<StudioState>(endpoint, payload, {
        nonce: state.session_nonce,
      });
      onState(next);
      onActivity(label);
      return next;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function begin() {
    const definition = resolveDefinitionId(definitionId);
    if (!definition) return;
    await request(
      "/api/contracts/session/begin",
      {
        base: {
          definition_id: definition.definition_id,
          version: definition.version,
          digest: definition.digest,
        },
      },
      `${tx("Contract maintenance started", "已进入契约维护模式")} · ${definition.definition_id}`,
    );
  }

  function editorPayload(current: ContractMaintenanceState) {
    const session = current.session;
    const draft = current.draft;
    if (!session || !draft) throw new Error("Contract maintenance session is unavailable.");
    const candidate = parseObject<ModuleDefinition>(candidateSource, "Candidate");
    const migration = migrationSource.trim()
      ? parseObject<ContractMigration>(migrationSource, "Migration")
      : null;
    return {
      capability_id: session.capability.capability_id,
      expected_candidate_digest: draft.candidate_digest,
      candidate,
      migration,
    };
  }

  async function saveCandidate(): Promise<StudioState | null> {
    if (!maintenance) return null;
    try {
      return await request(
        "/api/contracts/candidate",
        editorPayload(maintenance),
        tx("Contract candidate saved", "契约候选已保存"),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      return null;
    }
  }

  async function validateCandidate() {
    const saved = await saveCandidate();
    const session = saved?.contract_maintenance?.session;
    if (!session) return;
    await request(
      "/api/contracts/validate",
      { capability_id: session.capability.capability_id },
      tx("Contract candidate validated", "契约候选已验证"),
    );
  }

  async function review(decision: "approved" | "rejected") {
    const session = maintenance?.session;
    if (!session) return;
    await request(
      "/api/contracts/review",
      { capability_id: session.capability.capability_id, decision },
      `${tx("Contract review recorded", "契约评审已记录")} · ${decision}`,
    );
  }

  async function publish() {
    const session = maintenance?.session;
    if (!session) return;
    const result = await request(
      "/api/contracts/publish",
      { capability_id: session.capability.capability_id },
      tx("Approved contract published", "已发布批准的契约"),
    );
    if (result) onClose();
  }

  async function discard() {
    const session = maintenance?.session;
    if (!session) return;
    const result = await request(
      "/api/contracts/session/discard",
      { capability_id: session.capability.capability_id },
      tx("Contract draft discarded", "契约草稿已放弃"),
    );
    if (result) onClose();
  }

  const session = maintenance?.session ?? null;
  const draft = maintenance?.draft ?? null;
  const validation = maintenance?.validation ?? null;
  const receipt = maintenance?.review_receipt ?? null;
  const base = draft ? resolveDefinitionId(draft.base.definition_id) : undefined;
  const topologyActive = state.edit_session.mode === "topology-draft";
  const sourceTransactionActive = Boolean(state.transaction);

  return <div className="dialog-backdrop" role="presentation" onPointerDown={(event) => {
    if (event.target === event.currentTarget) onClose();
  }}>
    <section className="project-dialog contract-maintenance-dialog" role="dialog" aria-modal="true" aria-label={tx("Module contract maintenance", "模块契约维护")}>
      <header>
        <div><strong>{tx("Module contract maintenance", "模块契约维护")}</strong><span>{session ? `${session.capability.base.definition_id}@${session.capability.base.version}` : tx("Approved definitions are immutable", "已批准定义不可原地修改")}</span></div>
        <button className="icon-button" title={tx("Close", "关闭")} aria-label={tx("Close", "关闭")} onClick={onClose}><X /></button>
      </header>

      {!session || !draft ? <>
        <div className="contract-lock-note"><LockKeyhole size={16} /><span>{tx("Start from an exact approved definition reference. Topology and source transactions must be closed first.", "必须从精确的已批准定义引用创建草稿；拓扑会话和源码事务需先结束。")}</span></div>
        <label className="model-field"><span>{tx("Approved base definition", "已批准基础定义")}</span><select value={definitionId} onChange={(event) => setDefinitionId(event.target.value)}>{MODULE_REGISTRY.definitions.map((definition) => <option key={`${definition.definition_id}@${definition.version}`} value={definition.definition_id}>{moduleDefinitionLabel(definition)} · {definition.version}</option>)}</select></label>
        {resolveDefinitionId(definitionId) && <div className="module-contract-summary"><code>{resolveDefinitionId(definitionId)!.digest.slice(0, 16)}</code><span>{resolveDefinitionId(definitionId)!.definition_id}</span></div>}
        <div className="launcher-actions"><button onClick={onClose}>{tx("Cancel", "取消")}</button><button className="primary-action" disabled={busy !== null || topologyActive || sourceTransactionActive} onClick={() => void begin()}><LockKeyhole size={14} />{tx("Create contract draft", "创建契约草稿")}</button></div>
      </> : <>
        <div className="contract-status-line"><span className={`contract-state state-${draft.state}`}>{draft.state}</span><code>{draft.candidate_digest.slice(0, 16)}</code><span>rev {draft.revision}</span></div>
        <div className="contract-editor-grid">
          <label><span>{tx("Candidate definition", "候选定义")}</span><textarea spellCheck={false} value={candidateSource} onChange={(event) => setCandidateSource(event.target.value)} /></label>
          <label><span>{tx("Migration (required for breaking changes)", "迁移说明（破坏性变更必填）")}</span><textarea spellCheck={false} placeholder={'{"migration_id":"migration:...","from_version":"1.0.0","to_version":"2.0.0","parameter_map":{},"port_map":{},"fixture_results":[]}'} value={migrationSource} onChange={(event) => setMigrationSource(event.target.value)} /></label>
        </div>
        <div className="contract-base-line"><FileJson2 size={13} /><span>{base?.definition_id ?? draft.base.definition_id}</span><code>{draft.base.version} · {draft.base.digest.slice(0, 12)}</code></div>

        {validation && <section className="contract-validation-summary"><header><strong>{tx("Validation", "验证")}</strong><span className={validation.status}>{validation.status} · {validation.diff.compatibility} · {validation.diff.required_version_bump}</span></header>{validation.diff.changes.length ? <div>{validation.diff.changes.map((change) => <p key={`${change.kind}:${change.subject}`}><b>{change.compatibility}</b><code>{change.subject}</code><span>{change.message}</span></p>)}</div> : <span>{tx("No contract changes", "没有契约变更")}</span>}{validation.diagnostics.map((item) => <p className="contract-diagnostic" key={item.code}><AlertTriangle size={12} /><code>{item.code}</code><span>{item.message}</span></p>)}</section>}
        {receipt && <div className={`contract-receipt receipt-${receipt.decision}`}><ShieldCheck size={14} /><span>{receipt.decision} · {receipt.reviewer}</span><code>{receipt.validation_digest.slice(0, 12)}</code></div>}
        {error && <div className="launcher-error" role="alert"><AlertTriangle size={14} /><span>{error}</span></div>}
        <div className="contract-action-bar">
          <button disabled={busy !== null} title={tx("Save candidate and invalidate prior validation", "保存候选并使旧验证失效")} onClick={() => void saveCandidate()}><Save size={14} />{tx("Save", "保存")}</button>
          <button disabled={busy !== null} onClick={() => void validateCandidate()}>{busy ? <RefreshCw className="spin" size={14} /> : <CheckCircle2 size={14} />}{tx("Validate", "验证")}</button>
          <button disabled={busy !== null || validation?.status !== "passed"} onClick={() => void review("approved")}><ShieldCheck size={14} />{tx("Approve", "批准")}</button>
          <button disabled={busy !== null || !validation} onClick={() => void review("rejected")}><X size={14} />{tx("Reject", "拒绝")}</button>
          <button className="primary-action" disabled={busy !== null || receipt?.decision !== "approved" || draft.state !== "approved"} onClick={() => void publish()}><Send size={14} />{tx("Publish", "发布")}</button>
          <button disabled={busy !== null} onClick={() => void discard()}>{tx("Discard", "放弃")}</button>
        </div>
      </>}
      {!draft && error && <div className="launcher-error" role="alert"><AlertTriangle size={14} /><span>{error}</span></div>}
    </section>
  </div>;
}
