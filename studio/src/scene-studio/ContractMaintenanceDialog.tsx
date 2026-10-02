import { AlertTriangle, CheckCircle2, FileJson2, LockKeyhole, Save, Send, ShieldCheck, X } from "lucide-react";
import { useEffect, useState } from "react";

import { postStudioJson } from "../api/studio-client";
import { MODULE_REGISTRY, moduleDefinitionLabel, resolveDefinitionId } from "../module-registry/registry";
import type { ModuleDefinition } from "../module-registry/types";
import type { ContractMigration, ContractMaintenanceState, StudioStatePayload } from "./domain/source-backed-scene";

interface Props {
  open: boolean;
  state: StudioStatePayload;
  onClose: () => void;
  onState: (state: StudioStatePayload) => void;
}

function parseObject<T>(source: string, label: string): T {
  const value = JSON.parse(source) as unknown;
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} must be a JSON object.`);
  }
  return value as T;
}

export function ContractMaintenanceDialog({ open, state, onClose, onState }: Props) {
  const maintenance = state.contract_maintenance;
  const [definitionId, setDefinitionId] = useState(MODULE_REGISTRY.definitions[0]?.definition_id ?? "");
  const [candidateSource, setCandidateSource] = useState("");
  const [migrationSource, setMigrationSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!maintenance?.draft) return;
    setCandidateSource(JSON.stringify(maintenance.draft.candidate, null, 2));
    setMigrationSource(maintenance.draft.migration ? JSON.stringify(maintenance.draft.migration, null, 2) : "");
    setError("");
  }, [maintenance?.draft?.draft_id, maintenance?.draft?.revision]);

  if (!open) return null;

  async function request(endpoint: string, payload: Record<string, unknown>) {
    setBusy(true);
    setError("");
    try {
      const next = await postStudioJson<StudioStatePayload>(endpoint, payload, { nonce: state.session_nonce });
      onState(next);
      return next;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function begin() {
    const definition = resolveDefinitionId(definitionId);
    if (!definition) return;
    await request("/api/contracts/session/begin", {
      base: { definition_id: definition.definition_id, version: definition.version, digest: definition.digest },
    });
  }

  function editorPayload(current: ContractMaintenanceState) {
    if (!current.session || !current.draft) throw new Error("Contract maintenance session is unavailable.");
    return {
      capability_id: current.session.capability.capability_id,
      expected_candidate_digest: current.draft.candidate_digest,
      candidate: parseObject<ModuleDefinition>(candidateSource, "Candidate"),
      migration: migrationSource.trim() ? parseObject<ContractMigration>(migrationSource, "Migration") : null,
    };
  }

  async function saveCandidate() {
    if (!maintenance) return null;
    try {
      return await request("/api/contracts/candidate", editorPayload(maintenance));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      return null;
    }
  }

  async function validateCandidate() {
    const saved = await saveCandidate();
    const capabilityId = saved?.contract_maintenance?.session?.capability.capability_id;
    if (capabilityId) await request("/api/contracts/validate", { capability_id: capabilityId });
  }

  async function review(decision: "approved" | "rejected") {
    const capabilityId = maintenance?.session?.capability.capability_id;
    if (capabilityId) await request("/api/contracts/review", { capability_id: capabilityId, decision });
  }

  async function closeSession(endpoint: string) {
    const capabilityId = maintenance?.session?.capability.capability_id;
    if (!capabilityId) return;
    if (await request(endpoint, { capability_id: capabilityId })) onClose();
  }

  const session = maintenance?.session;
  const draft = maintenance?.draft;
  const validation = maintenance?.validation;
  const receipt = maintenance?.review_receipt;
  const transactionActive = Boolean(
    state.transaction && !["committed", "discarded", "failed"].includes(state.transaction.state),
  );
  const locked = state.edit_session?.mode === "topology-draft" || transactionActive;

  return <div className="source-dialog-backdrop" role="presentation">
    <section className="source-dialog contract-maintenance-dialog" role="dialog" aria-modal="true" aria-label="Module contract maintenance">
      <header><div><strong>Module contract maintenance</strong><span>Approved definitions are immutable</span></div><button className="icon-button" aria-label="Close" onClick={onClose}><X size={15} /></button></header>
      <div className="source-dialog-body">
        {!session || !draft ? <>
          <div className="contract-lock-note"><LockKeyhole size={15} />Start from an exact approved definition reference.</div>
          <label>Approved base definition<select value={definitionId} onChange={(event) => setDefinitionId(event.target.value)}>{MODULE_REGISTRY.definitions.map((definition) => <option key={`${definition.definition_id}@${definition.version}`} value={definition.definition_id}>{moduleDefinitionLabel(definition)} · {definition.version}</option>)}</select></label>
          <button className="tool-button primary-command" disabled={busy || locked} onClick={() => void begin()}><LockKeyhole size={14} />Create contract draft</button>
        </> : <>
          <div className="contract-status-line"><span>{draft.state}</span><code>{draft.candidate_digest.slice(0, 16)}</code><span>rev {draft.revision}</span></div>
          <div className="contract-editor-grid">
            <label>Candidate definition<textarea rows={14} spellCheck={false} value={candidateSource} onChange={(event) => setCandidateSource(event.target.value)} /></label>
            <label>Migration (required for breaking changes)<textarea rows={14} spellCheck={false} value={migrationSource} onChange={(event) => setMigrationSource(event.target.value)} /></label>
          </div>
          <div className="contract-base-line"><FileJson2 size={13} /><code>{draft.base.definition_id}@{draft.base.version}</code></div>
          {validation ? <section className="contract-validation-summary"><strong>Validation · {validation.status} · {validation.diff.compatibility}</strong>{validation.diff.changes.map((change) => <p key={`${change.subject}:${change.message}`}><code>{change.subject}</code> {change.message}</p>)}{validation.diagnostics.map((item) => <p key={item.code}><AlertTriangle size={12} />{item.code} · {item.message}</p>)}</section> : null}
          {receipt ? <div className="contract-receipt"><ShieldCheck size={14} />{receipt.decision} · {receipt.reviewer}</div> : null}
          <div className="contract-action-bar">
            <button className="tool-button" disabled={busy} onClick={() => void saveCandidate()}><Save size={14} />Save</button>
            <button className="tool-button" disabled={busy} onClick={() => void validateCandidate()}><CheckCircle2 size={14} />Validate</button>
            <button className="tool-button" disabled={busy || validation?.status !== "passed"} onClick={() => void review("approved")}><ShieldCheck size={14} />Approve</button>
            <button className="tool-button" disabled={busy || !validation} onClick={() => void review("rejected")}><X size={14} />Reject</button>
            <button className="tool-button primary-command" disabled={busy || receipt?.decision !== "approved" || draft.state !== "approved"} onClick={() => void closeSession("/api/contracts/publish")}><Send size={14} />Publish</button>
            <button className="tool-button" disabled={busy} onClick={() => void closeSession("/api/contracts/session/discard")}>Discard</button>
          </div>
        </>}
        {error ? <div className="dialog-error" role="alert">{error}</div> : null}
      </div>
    </section>
  </div>;
}
