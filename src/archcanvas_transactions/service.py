from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from archcanvas_adapters import (
    analyze_with_adapter,
    apply_model_transaction,
    framework_form_capability,
    transaction_adapter_id,
    transaction_artifact_kind,
    validate_model_artifact,
    validate_model_transaction_delta,
)
from archcanvas_core.architecture_v2 import ExactArchitectureIRV2
from archcanvas_core.builtin_registry import BuiltinModuleRegistry
from archcanvas_core.models import (
    ArchitectureIR,
    Diagnostic,
    EditTargetScope,
    EvidenceKind,
    EvidenceRecord,
    FileChange,
    FreeformSourcePatch,
    GateResult,
    ParameterEditContext,
    ParameterOrigin,
    RecoveryReceipt,
    SemanticIntentV2,
    SemanticParameterPatch,
    SemanticStructuralPatch,
    SourceAnchor,
    SourceFileMetadata,
    SourceSnapshot,
    SourceTransaction,
    TransactionBaseBlob,
    TransactionJournal,
    TransactionJournalFile,
    TransactionJournalState,
    TransactionReceipt,
    TransactionState,
    ValueOrigin,
    ValueOriginKind,
)
from archcanvas_core.protocols import read_exact_architecture_ir_v2_protocol
from archcanvas_core.source_v2 import (
    AnalysisEnvironmentManifest,
    AnalysisInputManifest,
    ProjectManifest,
    SourceCorpus,
)
from archcanvas_core.validation import validate_architecture
from archcanvas_engine.source_blob_store import SourceBlobStore
from archcanvas_patterns import exact_ir_digest
from archcanvas_publication import (
    build_scene,
    build_visual_spec,
    compile_views,
    validate_geometry,
    validate_publication,
)
from archcanvas_python import analyze_project_v2
from archcanvas_python.corpus import capture_source_corpus
from archcanvas_runtime import trace_runtime

from .delta import graph_delta
from .registry import (
    StructuralTransformResult,
    apply_structural_transform,
    validate_structural_oracle,
)
from .state_migration import build_state_migration_plan
from .store import (
    load_journal,
    load_transaction,
    save_journal,
    save_recovery_receipt,
    save_transaction,
    save_transaction_receipt,
)
from .transforms import (
    insert_pytorch_module,
    set_class_field_parameter,
    set_functional_parameter,
    set_json_value,
    set_python_parameter,
    write_prepared,
)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _diagnostic(code: str, message: str, *target_ids: str) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity="blocking",
        message=message,
        target_ids=list(target_ids),
    )


def _gate(name: str, passed: bool, success: str, failure: str) -> GateResult:
    return GateResult(
        gate=name,
        status="passed" if passed else "failed",
        message=success if passed else failure,
    )


def _receipt(transaction: SourceTransaction, *, source_writes: bool = False) -> TransactionReceipt:
    ok = transaction.state in {
        TransactionState.PREPARED,
        TransactionState.REVIEW_READY,
        TransactionState.COMMITTED,
        TransactionState.DISCARDED,
    }
    source_status = (
        "committed"
        if transaction.state is TransactionState.COMMITTED
        else "discarded"
        if transaction.state is TransactionState.DISCARDED
        else "failed"
        if transaction.state is TransactionState.FAILED
        else "verified"
        if transaction.state is TransactionState.REVIEW_READY
        else "prepared"
    )
    plan = transaction.state_migration_plan
    state_compatibility = "not-bound" if plan is None else plan.status
    if state_compatibility == "not-requested":
        state_compatibility = "not-bound"
    training_compatibility = state_compatibility
    inference_compatibility = state_compatibility
    if plan is not None and plan.status == "verified":
        binding = getattr(transaction.request, "state_asset_binding", None)
        if binding is None or not all(
            (
                binding.optimizer_state_bound,
                binding.scheduler_state_bound,
                binding.progress_state_bound,
                binding.random_state_bound,
            )
        ):
            training_compatibility = "partial"
    receipt = TransactionReceipt(
        transaction_id=transaction.transaction_id,
        framework=transaction.framework,
        transaction_adapter_id=transaction.transaction_adapter_id,
        artifact_kind=transaction.artifact_kind,
        state=transaction.state,
        status="ok" if ok else "invalid",
        gates=transaction.gates,
        diagnostics=transaction.diagnostics,
        proposal_correlation_id=transaction.proposal_correlation_id,
        realized_subject_ids=transaction.realized_subject_ids,
        source_writes=source_writes,
        source_status=source_status,
        state_compatibility=state_compatibility,
        training_resume_compatibility=training_compatibility,
        inference_compatibility=inference_compatibility,
        state_migration_plan_id=(plan.plan_id if plan is not None else None),
    )
    save_transaction_receipt(
        receipt,
        Path(transaction.workspace) / "transactions" / transaction.transaction_id,
    )
    return receipt


@dataclass(frozen=True)
class _LoadedArtifact:
    path: Path
    architecture: ArchitectureIR
    snapshot: SourceSnapshot
    evidence: list[EvidenceRecord]
    project_manifest: ProjectManifest | None = None
    source_corpus: SourceCorpus | None = None
    environment_manifest: AnalysisEnvironmentManifest | None = None
    analysis_input: AnalysisInputManifest | None = None
    exact_ir: ExactArchitectureIRV2 | None = None

    @property
    def is_v2(self) -> bool:
        return self.source_corpus is not None


@dataclass(frozen=True)
class _ReanalysisBundle:
    architecture: ArchitectureIR
    snapshot: SourceSnapshot
    evidence: list[EvidenceRecord]
    source_corpus_digest: str
    exact_ir_digest: str


_UTF8_BOM = b"\xef\xbb\xbf"


def _source_file_metadata(path: Path, content: bytes, kind: str) -> SourceFileMetadata:
    if path.is_symlink():
        raise ValueError(f"symbolic links are not writable source transaction targets: {path}")
    mode = stat.S_IMODE(path.stat().st_mode)
    if kind in {"binary", "onnx"}:
        return SourceFileMetadata(
            encoding="binary",
            has_utf8_bom=False,
            newline="none",
            trailing_newline=False,
            mode=mode,
        )
    has_bom = content.startswith(_UTF8_BOM)
    payload = content[len(_UTF8_BOM) :] if has_bom else content
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"source transaction target is not lossless UTF-8: {path}") from error
    crlf_count = payload.count(b"\r\n")
    bare_lf_count = payload.count(b"\n") - crlf_count
    bare_cr_count = payload.count(b"\r") - crlf_count
    newline_kinds = sum(value > 0 for value in (crlf_count, bare_lf_count, bare_cr_count))
    if bare_cr_count or newline_kinds > 1:
        newline = "mixed"
    elif crlf_count:
        newline = "crlf"
    elif bare_lf_count:
        newline = "lf"
    else:
        newline = "none"
    return SourceFileMetadata(
        encoding="utf-8",
        has_utf8_bom=has_bom,
        newline=newline,
        trailing_newline=payload.endswith((b"\n", b"\r")),
        mode=mode,
    )


def _build_transaction_journal(
    transaction: SourceTransaction,
    state: TransactionJournalState,
) -> TransactionJournal:
    if (
        transaction.base_source_corpus_digest is None
        or transaction.result_source_corpus_digest is None
    ):
        raise ValueError("transaction journal requires bound base and result source digests")
    files: list[TransactionJournalFile] = []
    original_root = Path(transaction.original_project_root)
    prepared_root = Path(transaction.temporary_project_root)
    for index, change in enumerate(transaction.file_changes):
        original = original_root / change.path
        prepared = prepared_root / change.path
        original_bytes = original.read_bytes()
        prepared_bytes = prepared.read_bytes()
        original_metadata = _source_file_metadata(original, original_bytes, change.kind)
        prepared_metadata = _source_file_metadata(prepared, prepared_bytes, change.kind)
        if original_metadata.newline == "mixed":
            raise ValueError(f"mixed or legacy newline style cannot be rewritten losslessly: {change.path}")
        if prepared_metadata != original_metadata:
            raise ValueError(
                "prepared source does not preserve encoding, BOM, newline, trailing newline, "
                f"and mode: {change.path}"
            )
        files.append(
            TransactionJournalFile(
                logical_path=change.path,
                working_path=change.path,
                before_sha256=change.before_sha256,
                after_sha256=change.after_sha256,
                backup_relative_path=f"journal-backups/{index:04d}-{Path(change.path).name}",
                original_metadata=original_metadata,
                prepared_metadata=prepared_metadata,
            )
        )
    now = datetime.now(UTC).isoformat()
    return TransactionJournal(
        journal_id=f"journal:{transaction.transaction_id.removeprefix('transaction:')}",
        transaction_id=transaction.transaction_id,
        base_source_digest=transaction.base_source_corpus_digest,
        result_source_digest=transaction.result_source_corpus_digest,
        state=state,
        files=files,
        created_at=now,
        updated_at=now,
    )


def _transition_journal(
    journal: TransactionJournal,
    transaction_directory: Path,
    state: TransactionJournalState,
    **updates: Any,
) -> TransactionJournal:
    changed = journal.model_copy(
        update={
            "state": state,
            "updated_at": datetime.now(UTC).isoformat(),
            **updates,
        }
    )
    save_journal(changed, transaction_directory)
    return changed


def _load_artifact(artifact_path: Path) -> _LoadedArtifact:
    artifact = artifact_path.resolve()
    architecture = ArchitectureIR.model_validate_json(artifact.read_text(encoding="utf-8"))
    snapshot_path = artifact.parent / "source-snapshot.json"
    evidence_path = artifact.parent / "evidence-ledger.json"
    if not snapshot_path.is_file() or not evidence_path.is_file():
        raise ValueError("transaction preparation requires source-snapshot.json and evidence-ledger.json")
    snapshot = SourceSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
    evidence = TypeAdapter(list[EvidenceRecord]).validate_json(
        evidence_path.read_text(encoding="utf-8")
    )
    if architecture.source_snapshot_id != snapshot.snapshot_id:
        raise ValueError("architecture and source snapshot are stale")
    v2_paths = {
        "project_manifest": artifact.parent / "project-manifest-v2.json",
        "source_corpus": artifact.parent / "source-corpus-v2.json",
        "environment_manifest": artifact.parent / "analysis-environment-manifest-v1.json",
        "analysis_input": artifact.parent / "analysis-input-v2.json",
        "exact_ir": artifact.parent / "architecture-v2.json",
    }
    present = {name for name, path in v2_paths.items() if path.is_file()}
    if present and present != set(v2_paths):
        missing = ", ".join(sorted(set(v2_paths) - present))
        raise ValueError(f"transaction artifact has an incomplete v2 bundle: {missing}")
    if not present:
        return _LoadedArtifact(artifact, architecture, snapshot, evidence)

    project_manifest = ProjectManifest.model_validate_json(
        v2_paths["project_manifest"].read_text(encoding="utf-8")
    )
    source_corpus = SourceCorpus.model_validate_json(
        v2_paths["source_corpus"].read_text(encoding="utf-8")
    )
    environment_manifest = AnalysisEnvironmentManifest.model_validate_json(
        v2_paths["environment_manifest"].read_text(encoding="utf-8")
    )
    analysis_input = AnalysisInputManifest.model_validate_json(
        v2_paths["analysis_input"].read_text(encoding="utf-8")
    )
    exact_ir, _ = read_exact_architecture_ir_v2_protocol(
        json.loads(v2_paths["exact_ir"].read_text(encoding="utf-8"))
    )
    corpus_digest = source_corpus.source_corpus_digest
    if (
        analysis_input.source_corpus_digest != corpus_digest
        or analysis_input.environment_manifest_digest
        != environment_manifest.environment_manifest_digest
        or analysis_input.registry_digest != environment_manifest.registry_digest
        or analysis_input.analyzer_build_digest != environment_manifest.analyzer_digest
        or analysis_input.pattern_pack_digests != environment_manifest.pattern_pack_digests
        or exact_ir.source_corpus_digest != corpus_digest
        or exact_ir.analysis_input_digest != analysis_input.analysis_input_digest
        or exact_ir.registry_digest != analysis_input.registry_digest
        or snapshot.revision != f"corpus:{corpus_digest}"
        or exact_ir.entrypoint != snapshot.entrypoint
        or exact_ir.framework != architecture.framework
    ):
        raise ValueError("v2 transaction artifacts have stale or inconsistent digest bindings")
    expected_files = {(item.logical_path, item.sha256) for item in source_corpus.files}
    snapshot_files = {(item.path, item.sha256) for item in snapshot.source_files}
    if snapshot_files != expected_files:
        raise ValueError("v1 compatibility snapshot does not match the v2 source corpus")
    return _LoadedArtifact(
        path=artifact,
        architecture=architecture,
        snapshot=snapshot,
        evidence=evidence,
        project_manifest=project_manifest,
        source_corpus=source_corpus,
        environment_manifest=environment_manifest,
        analysis_input=analysis_input,
        exact_ir=exact_ir,
    )


def _working_project(artifact: _LoadedArtifact) -> Path:
    root = (
        Path(artifact.project_manifest.project_root_hint)
        if artifact.project_manifest is not None
        else Path(artifact.snapshot.project_root)
    ).resolve()
    if not root.is_dir():
        raise ValueError(f"transaction project root is unavailable: {root}")
    return root


def _working_relative_path(
    artifact: _LoadedArtifact,
    logical_path: str,
    *,
    expected_digest: str | None = None,
) -> Path:
    if artifact.project_manifest is None:
        return Path(logical_path)
    project = _working_project(artifact)
    if logical_path in artifact.project_manifest.config_paths:
        relative = Path(logical_path)
        resolved = (project / relative).resolve()
        if not resolved.is_relative_to(project):
            raise ValueError(f"project config path escapes the project: {logical_path}")
        if resolved.is_file() and (
            expected_digest is None or _sha256(resolved.read_bytes()) == expected_digest
        ):
            return relative
        if expected_digest is not None:
            raise ValueError(f"project config base blob is stale: {logical_path}")
        return relative
    candidates: list[Path] = []
    for root in sorted(
        artifact.project_manifest.source_roots,
        key=lambda item: (item.precedence, item.logical_prefix, item.relative_path),
    ):
        prefix = root.logical_prefix
        if prefix and logical_path != prefix and not logical_path.startswith(f"{prefix}/"):
            continue
        suffix = logical_path.removeprefix(f"{prefix}/") if prefix else logical_path
        relative = Path(root.relative_path) / Path(suffix)
        resolved = (project / relative).resolve()
        if not resolved.is_relative_to(project):
            continue
        candidates.append(relative)
        if resolved.is_file() and (
            expected_digest is None or _sha256(resolved.read_bytes()) == expected_digest
        ):
            return relative
    if candidates:
        return candidates[0]
    raise ValueError(f"logical source path is not covered by the project manifest: {logical_path}")


def _frozen_source_bytes(artifact: _LoadedArtifact, logical_path: str) -> bytes:
    if artifact.source_corpus is None:
        path = (Path(artifact.snapshot.project_root).resolve() / logical_path).resolve()
        return path.read_bytes()
    source = next(
        (item for item in artifact.source_corpus.files if item.logical_path == logical_path),
        None,
    )
    if source is None:
        raise ValueError(f"source path is outside the v2 corpus: {logical_path}")
    snapshot_root = Path(artifact.snapshot.project_root).resolve()
    candidate = (snapshot_root / logical_path).resolve()
    if candidate.is_relative_to(snapshot_root) and candidate.is_file():
        payload = candidate.read_bytes()
    else:
        blob_root = artifact.path.parent / ".frontend-v2" / "source-blobs"
        if not blob_root.is_dir():
            raise ValueError(f"frozen source blob is unavailable: {logical_path}")
        payload = SourceBlobStore(blob_root).read(source.blob_ref)
    if _sha256(payload) != source.sha256:
        raise ValueError(f"frozen source blob is corrupt: {logical_path}")
    return payload


def _transaction_base_blobs(artifact: _LoadedArtifact) -> list[TransactionBaseBlob]:
    if artifact.source_corpus is None:
        return []
    return [
        TransactionBaseBlob(
            logical_path=item.logical_path,
            working_path=_working_relative_path(
                artifact, item.logical_path, expected_digest=item.sha256
            ).as_posix(),
            sha256=item.sha256,
            blob_ref=item.blob_ref,
            size=item.size,
        )
        for item in artifact.source_corpus.files
    ]


def _base_source_digest(artifact: _LoadedArtifact) -> str:
    if artifact.source_corpus is not None:
        return artifact.source_corpus.source_corpus_digest
    payload = {
        "snapshot_id": artifact.snapshot.snapshot_id,
        "revision": artifact.snapshot.revision,
        "config_digest": artifact.snapshot.config_digest,
        "source_files": [
            {"path": item.path, "sha256": item.sha256}
            for item in sorted(artifact.snapshot.source_files, key=lambda item: item.path)
        ],
    }
    return _sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


def _idempotent_transaction(
    workspace: Path,
    request: SemanticParameterPatch | SemanticStructuralPatch | FreeformSourcePatch,
    base_source_digest: str,
) -> SourceTransaction | None:
    root = workspace / "transactions"
    if not root.is_dir():
        return None
    for manifest in sorted(root.glob("*/transaction.json")):
        transaction = load_transaction(manifest)
        if (
            transaction.request.patch_id != request.patch_id
            or transaction.base_source_corpus_digest != base_source_digest
        ):
            continue
        if transaction.request != request:
            raise ValueError(
                "intent id is already bound to a different request on this source digest"
            )
        return transaction
    return None


def _validate_snapshot(artifact: _LoadedArtifact) -> None:
    if artifact.source_corpus is not None and artifact.project_manifest is not None:
        project = _working_project(artifact)
        with tempfile.TemporaryDirectory(prefix="archcanvas-transaction-corpus-") as temporary:
            observed = capture_source_corpus(
                project,
                artifact.project_manifest,
                SourceBlobStore(Path(temporary) / "blobs"),
            )
        if observed.source_corpus_digest != artifact.source_corpus.source_corpus_digest:
            raise ValueError("working-tree source corpus changed since v2 analysis")
        observed_files = {item.logical_path: item.sha256 for item in observed.files}
        for source in artifact.source_corpus.files:
            if observed_files.get(source.logical_path) != source.sha256:
                raise ValueError(f"source base blob changed since analysis: {source.logical_path}")
            _frozen_source_bytes(artifact, source.logical_path)
        return

    snapshot = artifact.snapshot
    project = Path(snapshot.project_root).resolve()
    for source_file in snapshot.source_files:
        path = (project / source_file.path).resolve()
        if not path.is_relative_to(project) or not path.is_file():
            raise ValueError(f"snapshot source file is unavailable: {source_file.path}")
        if _sha256(path.read_bytes()) != source_file.sha256:
            raise ValueError(f"source revision changed since analysis: {source_file.path}")
    if snapshot.revision.startswith("content:"):
        expected = snapshot.revision.removeprefix("content:")
        if not snapshot.source_files or snapshot.source_files[0].sha256 != expected:
            raise ValueError("source snapshot revision does not match its primary file hash")


def _relative_config(snapshot: SourceSnapshot, project: Path) -> Path:
    if not snapshot.config_path:
        raise ValueError("parameter provenance is config but the analysis has no config path")
    candidate = Path(snapshot.config_path)
    path = candidate.resolve() if candidate.is_absolute() else (project / candidate).resolve()
    if not path.is_relative_to(project) or not path.is_file():
        raise ValueError("transaction config must be an existing file inside the project")
    if _sha256(path.read_bytes()) != snapshot.config_digest:
        raise ValueError("config changed since analysis")
    return path.relative_to(project)


def _anchor_fingerprint(
    snapshot: SourceSnapshot,
    node: Any,
    parameter: Any,
    evidence: list[EvidenceRecord],
) -> str:
    records = [
        item.model_dump(mode="json")
        for item in evidence
        if item.evidence_id in parameter.evidence_ids
    ]
    payload = {
        "revision": snapshot.revision,
        "node_id": node.node_id,
        "source_symbol": node.source_symbol,
        "parameter": parameter.model_dump(mode="json"),
        "evidence": records,
    }
    return _sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


def _structural_anchor_fingerprint(
    snapshot: SourceSnapshot,
    node: Any,
    request: SemanticStructuralPatch,
    evidence: list[EvidenceRecord],
) -> str:
    records = [
        item.model_dump(mode="json")
        for item in evidence
        if item.evidence_id in node.evidence_ids
    ]
    payload = {
        "revision": snapshot.revision,
        "node": node.model_dump(mode="json"),
        "request": request.model_dump(mode="json"),
        "evidence": records,
    }
    return _sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


def _exact_source_anchor(
    artifact: _LoadedArtifact,
    node: Any,
    parameter_name: str | None = None,
) -> SourceAnchor | None:
    if artifact.exact_ir is None:
        return None
    instance_id = node.attributes.get("v2_instance_id")
    call_id = node.attributes.get("v2_call_id")
    instance = next(
        (item for item in artifact.exact_ir.instances if item.instance_id == instance_id),
        None,
    )
    if parameter_name is not None and instance is not None:
        argument = next(
            (
                item
                for item in instance.constructor_arguments
                if item.parameter_name == parameter_name
            ),
            None,
        )
        if argument is not None:
            return argument.anchor
    call = next(
        (item for item in artifact.exact_ir.calls if item.call_id == call_id),
        None,
    )
    return call.anchor if call is not None else (instance.anchor if instance is not None else None)


def _anchor_digest(anchor: SourceAnchor) -> str:
    return _sha256(
        json.dumps(
            anchor.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )


def _exact_parameter_position(
    artifact: _LoadedArtifact,
    node: Any,
    parameter_name: str,
) -> int | None:
    if artifact.exact_ir is None:
        return None
    instance_id = node.attributes.get("v2_instance_id")
    instance = next(
        (item for item in artifact.exact_ir.instances if item.instance_id == instance_id),
        None,
    )
    if instance is None or instance.definition_ref is None:
        return None
    definition = BuiltinModuleRegistry().resolve_ref(
        instance.definition_ref.definition_id,
        instance.definition_ref.version,
        instance.definition_ref.digest,
    )
    if definition is None:
        raise ValueError("v2 parameter target definition is missing from the bound registry")
    parameter = next(
        (item for item in definition.parameters if item.parameter_id == parameter_name),
        None,
    )
    return parameter.positional_index if parameter is not None else None


def _parameter_edit_context(
    artifact: _LoadedArtifact,
    node: Any,
    parameter: Any,
) -> ParameterEditContext:
    exact_anchor = _exact_source_anchor(artifact, node, parameter.name)
    source_anchor_ids = (
        [f"source-anchor:{_anchor_digest(exact_anchor)[:24]}"]
        if exact_anchor is not None
        else sorted(
            item.evidence_id
            for item in artifact.evidence
            if item.evidence_id in parameter.evidence_ids
            and item.kind in {EvidenceKind.SOURCE, EvidenceKind.CONFIG}
        )
    )
    if artifact.architecture.framework == "onnx" and not source_anchor_ids:
        source_anchor_ids = sorted(parameter.evidence_ids)
    origin_kind = {
        ParameterOrigin.LITERAL: ValueOriginKind.CONSTRUCTOR_LITERAL,
        ParameterOrigin.CONFIG: ValueOriginKind.CONFIG_KEY,
        ParameterOrigin.CONSTRUCTOR_DEFAULT: ValueOriginKind.FUNCTION_DEFAULT,
        ParameterOrigin.COMPUTED: ValueOriginKind.COMPUTED_EXPRESSION,
        ParameterOrigin.UNRESOLVED: ValueOriginKind.RUNTIME_ONLY,
    }[parameter.origin]
    if parameter.origin is ParameterOrigin.LITERAL and any(
        f".field.{parameter.name}" in evidence_id
        for evidence_id in parameter.evidence_ids
    ):
        origin_kind = ValueOriginKind.MODULE_FIELD
    direct = parameter.origin in {ParameterOrigin.LITERAL, ParameterOrigin.CONFIG}
    confidence = "exact" if direct and source_anchor_ids else (
        "conditional" if parameter.origin is ParameterOrigin.CONSTRUCTOR_DEFAULT else "unknown"
    )
    editability = "direct" if direct and source_anchor_ids else (
        "readonly"
        if parameter.origin is ParameterOrigin.UNRESOLVED
        else "adapter-required"
    )

    affected = {node.node_id}
    instance_id = node.attributes.get("v2_instance_id")
    parameter_identity = node.parameter_identity
    has_parameter_group = parameter_identity.startswith("parameter-group:")
    for candidate in artifact.architecture.nodes:
        candidate_parameter = next(
            (item for item in candidate.parameters if item.name == parameter.name),
            None,
        )
        if candidate_parameter is None:
            continue
        same_config = (
            parameter.origin is ParameterOrigin.CONFIG
            and candidate_parameter.origin is ParameterOrigin.CONFIG
            and candidate_parameter.source_expression == parameter.source_expression
        )
        same_instance = bool(
            instance_id
            and candidate.attributes.get("v2_instance_id") == instance_id
        )
        same_parameter_group = bool(
            has_parameter_group
            and candidate.parameter_identity == parameter_identity
        )
        if same_config or same_instance or same_parameter_group:
            affected.add(candidate.node_id)

    if parameter.origin is ParameterOrigin.CONFIG:
        allowed_scopes = [EditTargetScope.CONFIG_VALUE]
    elif node.repeat_id is not None:
        allowed_scopes = [EditTargetScope.REPEAT_TEMPLATE]
    elif has_parameter_group and len(
        {
            candidate.attributes.get("v2_instance_id")
            for candidate in artifact.architecture.nodes
            if candidate.node_id in affected
        }
    ) > 1:
        allowed_scopes = [
            EditTargetScope.PARAMETER_SHARING_GROUP,
            EditTargetScope.ALL_SHARED_USES,
        ]
    elif origin_kind is ValueOriginKind.MODULE_FIELD:
        allowed_scopes = [EditTargetScope.DEFINITION]
    else:
        allowed_scopes = [EditTargetScope.MODULE_INSTANCE]
    if editability != "direct":
        allowed_scopes = []

    origin_payload = {
        "node_id": node.node_id,
        "parameter_name": parameter.name,
        "kind": origin_kind.value,
        "source_expression": parameter.source_expression,
        "source_anchor_ids": source_anchor_ids,
    }
    origin_digest = _sha256(
        json.dumps(origin_payload, sort_keys=True, separators=(",", ":")).encode()
    )
    value_origin = ValueOrigin(
        origin_id=f"value-origin:{origin_digest[:24]}",
        kind=origin_kind,
        source_anchor_ids=source_anchor_ids,
        config_path=artifact.snapshot.config_path if origin_kind is ValueOriginKind.CONFIG_KEY else None,
        config_key_path=(
            [parameter.source_expression]
            if origin_kind is ValueOriginKind.CONFIG_KEY
            else []
        ),
        confidence=confidence,
        editability=editability,
        evidence_ids=sorted(parameter.evidence_ids),
    )
    context_digest = _sha256(
        json.dumps(
            {
                "origin_id": value_origin.origin_id,
                "affected": sorted(affected),
                "allowed_scopes": [item.value for item in allowed_scopes],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )
    return ParameterEditContext(
        context_id=f"parameter-edit:{context_digest[:24]}",
        target_node_id=node.node_id,
        parameter_name=parameter.name,
        current_value=parameter.value,
        value_origin=value_origin,
        allowed_scopes=allowed_scopes,
        default_scope=allowed_scopes[0] if len(allowed_scopes) == 1 else None,
        affected_canonical_ids=sorted(affected),
        blocking_reason=(
            None
            if editability == "direct"
            else f"{origin_kind.value} requires a registered parameter lowering adapter"
        ),
    )


def resolve_parameter_edit_context(
    artifact_path: Path,
    node_id: str,
    parameter_name: str,
) -> ParameterEditContext:
    artifact = _load_artifact(artifact_path)
    node = next(
        (item for item in artifact.architecture.nodes if item.node_id == node_id),
        None,
    )
    if node is None:
        raise ValueError(f"parameter edit node is unavailable: {node_id}")
    parameter = next(
        (item for item in node.parameters if item.name == parameter_name),
        None,
    )
    if parameter is None:
        raise ValueError(f"parameter edit target is unavailable: {node_id}.{parameter_name}")
    return _parameter_edit_context(artifact, node, parameter)


def resolve_parameter_edit_contexts(artifact_path: Path) -> list[ParameterEditContext]:
    artifact = _load_artifact(artifact_path)
    return [
        _parameter_edit_context(artifact, node, parameter)
        for node in artifact.architecture.nodes
        for parameter in node.parameters
    ]


def _python_literal(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, int):
        if abs(value) > 2**53 - 1:
            raise ValueError("registered module integer exceeds the cross-runtime safe range")
        return str(value)
    if isinstance(value, float):
        if not (-float("inf") < value < float("inf")):
            raise ValueError("registered module numeric parameters must be finite")
        return repr(value)
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_python_literal(item) for item in value) + "]"
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("registered module object parameters require string keys")
        return "{" + ", ".join(
            f"{key!r}: {_python_literal(value[key])}" for key in sorted(value)
        ) + "}"
    raise ValueError(f"unsupported registered module parameter type: {type(value).__name__}")


def _registered_constructor_expression(request: SemanticStructuralPatch) -> str:
    reference = request.parameters["definition_ref"]
    definition = BuiltinModuleRegistry().resolve_ref(
        str(reference["definition_id"]),
        str(reference["version"]),
        str(reference["digest"]),
    )
    if definition is None:
        raise ValueError("registered module definition reference is stale")
    inputs = [item for item in definition.ports if item.direction == "input"]
    outputs = [item for item in definition.ports if item.direction == "output"]
    if (
        len(inputs) != 1
        or len(outputs) != 1
        or inputs[0].min_connections != 1
        or inputs[0].max_connections != 1
    ):
        raise ValueError(
            "registered sequential insertion currently requires one input and one output port"
        )
    qualified_name = next(
        (item for item in definition.qualified_names if item.startswith("torch.nn.")),
        None,
    )
    if qualified_name is None or definition.codegen_rule_id is None:
        raise ValueError("registered module has no approved PyTorch constructor rule")
    parameters = request.parameters["constructor_parameters"]
    contracts = {item.parameter_id: item for item in definition.parameters}
    unknown = sorted(set(parameters) - set(contracts))
    if unknown:
        raise ValueError(
            "registered module parameters are not in the pinned schema: " + ", ".join(unknown)
        )
    missing = sorted(
        item.parameter_id
        for item in definition.parameters
        if item.required and parameters.get(item.parameter_id) is None
    )
    if missing:
        raise ValueError(
            "registered module is missing required parameters: " + ", ".join(missing)
        )
    positional: list[str] = []
    keywords: list[str] = []
    positional_open = True
    ordered = sorted(
        definition.parameters,
        key=lambda item: (
            item.positional_index if item.positional_index is not None else 2**31,
            item.parameter_id,
        ),
    )
    for contract in ordered:
        provided = contract.parameter_id in parameters
        is_default = (
            provided
            and not contract.required
            and parameters[contract.parameter_id] == contract.default
        )
        if not provided or is_default:
            positional_open = False
            continue
        expression = _python_literal(parameters[contract.parameter_id])
        if positional_open and contract.positional_index == len(positional):
            positional.append(expression)
        else:
            positional_open = False
            keywords.append(f"{contract.parameter_id}={expression}")
    class_name = qualified_name.rsplit(".", 1)[-1]
    arguments = ", ".join([*positional, *keywords])
    return f"nn.{class_name}({arguments})"


def _apply_v2_registered_insertion(
    request: SemanticStructuralPatch,
    loaded: _LoadedArtifact,
    node: Any,
) -> tuple[StructuralTransformResult, SourceAnchor]:
    if loaded.exact_ir is None:
        raise ValueError("registered module insertion requires Exact Architecture IR v2")
    instance_id = node.attributes.get("v2_instance_id")
    call_id = node.attributes.get("v2_call_id")
    instance = next(
        (item for item in loaded.exact_ir.instances if item.instance_id == instance_id),
        None,
    )
    call = next(
        (item for item in loaded.exact_ir.calls if item.call_id == call_id),
        None,
    )
    if instance is None or call is None or instance.definition_ref is None:
        raise ValueError("registered module insertion target lacks exact instance/call anchors")
    if (
        instance.anchor.logical_path != call.anchor.logical_path
        or instance.anchor.blob_digest != call.anchor.blob_digest
    ):
        raise ValueError(
            "registered module insertion requires constructor and call anchors in one frozen file"
        )
    outgoing = [
        item for item in loaded.architecture.edges if item.producer_id == node.node_id
    ]
    if len(outgoing) != 1:
        raise ValueError("registered module insertion requires one authored downstream consumer")
    target_module = instance.instance_path.rsplit(".", 1)[-1]
    if not target_module or target_module.endswith("[]"):
        raise ValueError("registered module insertion target is not a direct module field")
    source = _frozen_source_bytes(loaded, call.anchor.logical_path)
    transformed = insert_pytorch_module(
        source,
        target_module=target_module,
        new_module=str(request.parameters["module_name"]),
        constructor_expression=_registered_constructor_expression(request),
        init_line=instance.anchor.line_span.start_line,
        forward_line=call.anchor.line_span.start_line,
    )
    return (
        StructuralTransformResult(
            relative_path=Path(call.anchor.logical_path),
            transformed=transformed,
        ),
        call.anchor,
    )


def _copy_project(
    project: Path,
    target: Path,
    workspace: Path,
    artifact: _LoadedArtifact,
) -> None:
    ignored = {".git", ".archcanvas", "__pycache__", ".pytest_cache", ".ruff_cache", "build"}
    workspace = workspace.resolve()

    def ignore(directory: str, names: list[str]) -> list[str]:
        current = Path(directory).resolve()
        result = [name for name in names if name in ignored or name.endswith(".pyc")]
        for name in names:
            candidate = (current / name).resolve()
            if candidate == workspace or workspace.is_relative_to(candidate):
                result.append(name)
        return result

    shutil.copytree(project, target, ignore=ignore)
    if artifact.source_corpus is None:
        return
    for source in artifact.source_corpus.files:
        relative = _working_relative_path(
            artifact, source.logical_path, expected_digest=source.sha256
        )
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_frozen_source_bytes(artifact, source.logical_path))
    for excluded in artifact.source_corpus.excluded:
        if excluded.reason != "excluded-pattern":
            continue
        relative = _working_relative_path(artifact, excluded.logical_path)
        destination = target / relative
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"")


def _v2_config_bytes(artifact: _LoadedArtifact, project: Path) -> bytes:
    if artifact.source_corpus is None or artifact.analysis_input is None:
        raise ValueError("v2 config lookup requires a complete v2 artifact")
    digest = artifact.analysis_input.config_digest
    source = next(
        (
            item
            for item in artifact.source_corpus.files
            if item.sha256 == digest and item.file_kind in {"config", "project-metadata"}
        ),
        None,
    )
    if source is not None:
        path = project / _working_relative_path(artifact, source.logical_path)
        payload = path.read_bytes()
        return payload
    empty = b"{}"
    if _sha256(empty) == digest:
        return empty
    raise ValueError("v2 analysis config bytes are not present in the frozen source corpus")


def _analyze_at(
    project: Path,
    artifact: _LoadedArtifact,
    workspace: Path,
):
    snapshot = artifact.snapshot
    if artifact.source_corpus is not None and artifact.analysis_input is not None:
        frontend = analyze_project_v2(
            project,
            artifact.analysis_input.entrypoint,
            artifact.analysis_input.task,
            artifact.analysis_input.execution_mode,
            workspace,
            config_bytes=_v2_config_bytes(artifact, project),
        )
        if frontend.analysis_input.registry_digest != artifact.analysis_input.registry_digest:
            raise ValueError("v2 registry digest changed during transaction reanalysis")
        blocking = [
            item for item in frontend.exact_ir.diagnostics if item.severity == "blocking"
        ]
        if blocking:
            raise ValueError("v2 reanalysis produced blocking Exact IR diagnostics")
        return _ReanalysisBundle(
            architecture=frontend.compatibility.architecture,
            snapshot=frontend.compatibility.snapshot,
            evidence=frontend.compatibility.evidence,
            source_corpus_digest=frontend.corpus.source_corpus_digest,
            exact_ir_digest=frontend.exact_ir.exact_ir_digest,
        )
    config_path: Path | None = None
    config_bytes = b"{}"
    if snapshot.config_path:
        original = Path(snapshot.config_path)
        relative = (
            original.resolve().relative_to(Path(snapshot.project_root).resolve())
            if original.is_absolute()
            else original
        )
        config_path = project / relative
        config_bytes = config_path.read_bytes()
    compatibility = analyze_with_adapter(
        project,
        snapshot.entrypoint,
        snapshot.task,
        snapshot.execution_mode,
        config_bytes,
        config_path,
        framework=snapshot.framework,
        pattern_packs_enabled=True,
    )
    return _ReanalysisBundle(
        architecture=compatibility.architecture,
        snapshot=compatibility.snapshot,
        evidence=compatibility.evidence,
        source_corpus_digest=(
            compatibility.snapshot.revision.removeprefix("corpus:")
            if compatibility.snapshot.revision.startswith("corpus:")
            else _sha256(compatibility.snapshot.model_dump_json().encode())
        ),
        exact_ir_digest=exact_ir_digest(compatibility.architecture),
    )


def _unified_diff(relative: Path, before: bytes, after: bytes) -> str:
    return "".join(
        difflib.unified_diff(
            before.decode("utf-8").splitlines(keepends=True),
            after.decode("utf-8").splitlines(keepends=True),
            fromfile=f"a/{relative.as_posix()}",
            tofile=f"b/{relative.as_posix()}",
        )
    )


def prepare_transaction(
    request: SemanticParameterPatch | SemanticStructuralPatch,
    workspace: Path,
    *,
    semantic_intent: SemanticIntentV2 | None = None,
) -> tuple[SourceTransaction, TransactionReceipt]:
    artifact = Path(request.artifact_path).resolve()
    loaded = _load_artifact(artifact)
    architecture = loaded.architecture
    snapshot = loaded.snapshot
    evidence = loaded.evidence
    if architecture.framework != snapshot.framework:
        raise ValueError("architecture and snapshot framework bindings do not match")
    artifact_kind = transaction_artifact_kind(architecture.framework)
    workspace = workspace.resolve()
    base_source_digest = _base_source_digest(loaded)
    if semantic_intent is not None:
        expected_operation = (
            "set-parameter"
            if isinstance(request, SemanticParameterPatch)
            else {
                "replace_activation": "replace-operation",
                "insert_layer_norm": "insert-normalization",
                "insert_registered_module": "create-node",
            }[request.operation]
        )
        expected_exact_ir_digest = exact_ir_digest(architecture)
        if (
            semantic_intent.framework != architecture.framework
            or semantic_intent.operation != expected_operation
            or request.target_node_id not in semantic_intent.target_ids
            or semantic_intent.base_source_digest != base_source_digest
            or semantic_intent.base_exact_ir_digest != expected_exact_ir_digest
        ):
            raise ValueError("semantic intent binding is stale or does not match the request")
        capability_action = (
            "parameter_transaction"
            if isinstance(request, SemanticParameterPatch)
            else "structural_transaction"
        )
        if framework_form_capability(
            semantic_intent.framework,
            semantic_intent.form_id,
            capability_action,
        ) == "unavailable":
            raise ValueError(
                f"{capability_action} is unavailable for {semantic_intent.form_id}"
            )
    existing = _idempotent_transaction(workspace, request, base_source_digest)
    if existing is not None:
        return existing, _receipt(
            existing, source_writes=existing.state is TransactionState.COMMITTED
        )
    _validate_snapshot(loaded)
    project = _working_project(loaded)
    node = next((item for item in architecture.nodes if item.node_id == request.target_node_id), None)
    if node is None:
        raise ValueError(f"target node is not present in Exact IR: {request.target_node_id}")
    parameter_context: ParameterEditContext | None = None
    if isinstance(request, SemanticParameterPatch):
        parameter = next(
            (item for item in node.parameters if item.name == request.parameter_name), None
        )
        if parameter is None:
            raise ValueError(
                f"target parameter is not present on {node.node_id}: {request.parameter_name}"
            )
        if parameter.value == request.new_value:
            raise ValueError("new parameter value is identical to the current value")
        parameter_context = _parameter_edit_context(loaded, node, parameter)
        contract_supplied = any(
            (
                request.value_origin_id is not None,
                request.edit_target_scope is not None,
                bool(request.confirmed_affected_ids),
                bool(request.confirmed_source_anchor_ids),
            )
        )
        if contract_supplied and (
            request.value_origin_id is None
            or request.edit_target_scope is None
            or not request.confirmed_affected_ids
            or not request.confirmed_source_anchor_ids
        ):
            raise ValueError("parameter edit intent has an incomplete origin and scope contract")
        if request.value_origin_id is not None:
            if request.value_origin_id != parameter_context.value_origin.origin_id:
                raise ValueError("parameter value origin binding is stale")
            if request.edit_target_scope not in parameter_context.allowed_scopes:
                raise ValueError("parameter edit target scope is unavailable")
            if sorted(request.confirmed_affected_ids) != parameter_context.affected_canonical_ids:
                raise ValueError("parameter edit affected canonical objects are stale")
            if sorted(request.confirmed_source_anchor_ids) != sorted(
                parameter_context.value_origin.source_anchor_ids
            ):
                raise ValueError("parameter edit source anchor confirmation is stale")
        if parameter_context.value_origin.editability != "direct":
            raise ValueError(
                parameter_context.blocking_reason
                or "parameter value origin is not directly editable"
            )
    seed = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    transaction_id = f"transaction:{_sha256((seed + datetime.now(UTC).isoformat()).encode())[:16]}"
    directory = workspace / "transactions" / transaction_id
    temporary_project = directory / "project"
    directory.mkdir(parents=True, exist_ok=False)
    _copy_project(project, temporary_project, workspace, loaded)

    semantic_manifest: str | None = None
    additional_model_files: list[Any] = []
    source_anchor: SourceAnchor | None = None
    if artifact_kind == "model-artifact":
        if isinstance(request, SemanticParameterPatch):
            parameter = next(
                (item for item in node.parameters if item.name == request.parameter_name), None
            )
            if parameter is None:
                raise ValueError(
                    f"target parameter is not present on {node.node_id}: {request.parameter_name}"
                )
            if parameter.value == request.new_value:
                raise ValueError("new parameter value is identical to the current value")
            anchor = _anchor_fingerprint(snapshot, node, parameter, evidence)
        else:
            anchor = _structural_anchor_fingerprint(snapshot, node, request, evidence)
        model_transform = apply_model_transaction(request, architecture, snapshot)
        relative = model_transform.relative_path
        original_path = project / relative
        transformed = model_transform
        before = original_path.read_bytes()
        semantic_manifest = model_transform.semantic_manifest
        additional_model_files = list(model_transform.additional_files)
        kind = "onnx"
    elif isinstance(request, SemanticParameterPatch):
        parameter = next(
            (item for item in node.parameters if item.name == request.parameter_name), None
        )
        if parameter is None:
            raise ValueError(
                f"target parameter is not present on {node.node_id}: {request.parameter_name}"
            )
        if parameter.value == request.new_value:
            raise ValueError("new parameter value is identical to the current value")
        source_anchor = _exact_source_anchor(loaded, node, parameter.name)
        anchor = (
            _anchor_digest(source_anchor)
            if source_anchor is not None
            else _anchor_fingerprint(snapshot, node, parameter, evidence)
        )
        if parameter.origin.value == "config":
            relative = _relative_config(snapshot, project)
            original_path = project / relative
            before = original_path.read_bytes()
            config_records = [
                item
                for item in evidence
                if item.evidence_id in parameter.evidence_ids and item.kind is EvidenceKind.CONFIG
            ]
            key = config_records[-1].symbol if config_records else parameter.source_expression
            if not key:
                raise ValueError("config-backed parameter has no exact config key anchor")
            transformed = set_json_value(before, key, request.new_value)
            kind = "json"
        elif parameter.origin.value == "literal":
            source_records = [
                item
                for item in evidence
                if item.evidence_id in parameter.evidence_ids
                and item.kind is EvidenceKind.SOURCE
                and item.span is not None
                and item.path is not None
            ]
            definition = next(
                (
                    item
                    for item in source_records
                    if ".init." in item.evidence_id
                    or f".field.{parameter.name}" in item.evidence_id
                ),
                None,
            )
            if source_anchor is None and (
                definition is None or definition.path is None or definition.span is None
            ):
                raise ValueError("literal parameter has no exact module-definition anchor")
            logical_path = (
                source_anchor.logical_path
                if source_anchor is not None
                else str(definition.path)
            )
            relative = _working_relative_path(
                loaded,
                logical_path,
                expected_digest=(source_anchor.blob_digest if source_anchor is not None else None),
            )
            before = (
                _frozen_source_bytes(loaded, logical_path)
                if loaded.is_v2
                else (project / relative).read_bytes()
            )
            module_path = str(node.attributes.get("module_path", ""))
            if source_anchor is not None and not module_path:
                instance_path = str(node.attributes.get("v2_instance_id", "")).removeprefix(
                    "instance:"
                )
                if instance_path:
                    module_path = f"self.{instance_path.rsplit('.', 1)[-1]}"
            functional_anchor = node.attributes.get("functional_anchor")
            expected_line = (
                source_anchor.line_span.start_line
                if source_anchor is not None
                else definition.span.start_line  # type: ignore[union-attr]
            )
            if module_path.startswith("self."):
                transformed = set_python_parameter(
                    before,
                    module_name=module_path.removeprefix("self."),
                    parameter_name=parameter.name,
                    source_expression=parameter.source_expression,
                    value=request.new_value,
                    expected_line=expected_line,
                    positional_index=_exact_parameter_position(
                        loaded, node, parameter.name
                    ),
                )
            elif isinstance(functional_anchor, str) and functional_anchor:
                transformed = set_functional_parameter(
                    before,
                    target_name=functional_anchor,
                    parameter_name=parameter.name,
                    source_expression=parameter.source_expression,
                    value=request.new_value,
                    expected_line=expected_line,
                )
            elif definition is not None and ".field." in definition.evidence_id:
                transformed = set_class_field_parameter(
                    before,
                    class_name=snapshot.entrypoint.split(":", 1)[1],
                    field_name=parameter.name,
                    source_expression=parameter.source_expression,
                    value=request.new_value,
                    expected_line=expected_line,
                )
            else:
                raise ValueError(
                    "literal parameter is not attached to a supported module or functional anchor"
                )
            kind = "python"
        else:
            raise ValueError(
                f"set_parameter does not have an exact transform for {parameter.origin.value} provenance"
            )
    else:
        source_anchor = _exact_source_anchor(loaded, node)
        if request.operation == "insert_registered_module":
            structural, source_anchor = _apply_v2_registered_insertion(
                request, loaded, node
            )
        else:
            structural = apply_structural_transform(
                request, architecture, snapshot, evidence
            )
        anchor = (
            _anchor_digest(source_anchor)
            if source_anchor is not None
            else _structural_anchor_fingerprint(snapshot, node, request, evidence)
        )
        logical_path = structural.relative_path.as_posix()
        relative = _working_relative_path(loaded, logical_path)
        before = (
            _frozen_source_bytes(loaded, logical_path)
            if loaded.is_v2
            else (project / relative).read_bytes()
        )
        transformed = structural.transformed
        kind = "python"

    prepared_path = temporary_project / relative
    write_prepared(prepared_path, transformed.content)
    after = prepared_path.read_bytes()
    if artifact_kind == "source-artifact" and before == after:
        shutil.rmtree(directory)
        raise ValueError("semantic intent produces no source change")
    file_changes = [
        FileChange(
            path=relative.as_posix(),
            kind=kind,
            before_sha256=_sha256(before),
            after_sha256=_sha256(after),
        )
    ]
    for additional in additional_model_files:
        additional_original = project / additional.relative_path
        additional_before = additional_original.read_bytes()
        additional_prepared = temporary_project / additional.relative_path
        write_prepared(additional_prepared, additional.content)
        file_changes.append(
            FileChange(
                path=additional.relative_path.as_posix(),
                kind=additional.kind,
                before_sha256=_sha256(additional_before),
                after_sha256=_sha256(additional_prepared.read_bytes()),
            )
        )
    prepared_bundle = _analyze_at(temporary_project, loaded, directory / "analysis-prepare")
    expected = graph_delta(
        architecture,
        prepared_bundle.architecture,
        evidence,
        prepared_bundle.evidence,
    )
    if artifact_kind == "model-artifact":
        validate_model_transaction_delta(
            request,
            architecture,
            prepared_bundle.architecture,
            expected,
        )
    elif isinstance(request, SemanticParameterPatch):
        target_change = next(
            (
                item
                for item in expected.changed_parameters
                if item.node_id == request.target_node_id
                and item.parameter_name == request.parameter_name
                and item.after == request.new_value
            ),
            None,
        )
        topology_changed = any(
            (
                expected.added_nodes,
                expected.removed_nodes,
                expected.added_edges,
                expected.removed_edges,
                expected.added_ports,
                expected.removed_ports,
                expected.changed_ports,
                expected.added_tensors,
                expected.removed_tensors,
                expected.added_fanouts,
                expected.removed_fanouts,
                expected.changed_fanouts,
                expected.changed_repeats,
                expected.added_config_predicates,
                expected.removed_config_predicates,
                expected.changed_config_predicates,
                expected.changed_sharing,
                expected.unresolved_changes,
            )
        )
        if target_change is None or topology_changed:
            raise ValueError(
                "prepared set_parameter change does not produce the required bounded graph delta"
            )
    else:
        validate_structural_oracle(
            request,
            architecture,
            prepared_bundle.architecture,
            expected,
        )

    proposal_correlation_id: str | None = None
    realized_subject_ids: list[str] = []
    if (
        isinstance(request, SemanticStructuralPatch)
        and request.operation == "insert_registered_module"
    ):
        proposal_correlation_id = str(request.parameters["correlation_id"])
        inserted = next(
            item
            for item in prepared_bundle.architecture.nodes
            if item.node_id in expected.added_nodes
        )
        realized_subject_ids = [
            inserted.node_id,
            *[port.port_id for port in [*inserted.input_ports, *inserted.output_ports]],
            *inserted.evidence_ids,
        ]

    state_binding = request.state_asset_binding
    state_plan = (
        build_state_migration_plan(
            state_binding,
            framework=architecture.framework,
            base_source_digest=base_source_digest,
            result_source_digest=prepared_bundle.source_corpus_digest,
            result_exact_ir_digest=prepared_bundle.exact_ir_digest,
            expected_delta=expected,
        )
        if state_binding is not None
        else None
    )
    transaction = SourceTransaction(
        transaction_id=transaction_id,
        framework=architecture.framework,
        transaction_adapter_id=transaction_adapter_id(architecture.framework),
        artifact_kind=artifact_kind,
        validators=(
            ["onnx-checker", "shape-inference", "graph-delta", "publication"]
            if artifact_kind == "model-artifact"
            else ["parse", "static-analysis", "graph-delta", "publication"]
        ),
        state=TransactionState.PREPARED,
        state_history=[
            TransactionState.DRAFT,
            TransactionState.PLANNED,
            TransactionState.PREPARED,
        ],
        request=request,
        semantic_intent=semantic_intent,
        parameter_edit_context=parameter_context,
        state_migration_plan=state_plan,
        created_at=datetime.now(UTC).isoformat(),
        workspace=str(workspace),
        original_project_root=str(project),
        temporary_project_root=str(temporary_project),
        artifact_path=str(artifact),
        source_snapshot_id=snapshot.snapshot_id,
        base_revision=snapshot.revision,
        anchor_fingerprint=anchor,
        source_anchor=source_anchor,
        base_source_corpus_digest=base_source_digest,
        base_analysis_input_digest=(
            loaded.analysis_input.analysis_input_digest if loaded.analysis_input else None
        ),
        base_registry_digest=(
            loaded.analysis_input.registry_digest if loaded.analysis_input else None
        ),
        base_exact_ir_digest=(loaded.exact_ir.exact_ir_digest if loaded.exact_ir else None),
        result_source_corpus_digest=prepared_bundle.source_corpus_digest,
        result_exact_ir_digest=prepared_bundle.exact_ir_digest,
        base_source_blobs=_transaction_base_blobs(loaded),
        proposal_correlation_id=proposal_correlation_id,
        realized_subject_ids=realized_subject_ids,
        reanalysis_route=(
            "analyze_project_v2+project_v1_compatibility"
            if loaded.is_v2
            else "analyze_with_adapter"
        ),
        file_changes=file_changes,
        source_diff=semantic_manifest or _unified_diff(relative, before, after),
        expected_delta=expected,
        gates=[
            _gate(
                "F-prepare",
                True,
                "Corpus, base blobs, exact anchor, isolated copy, and bounded delta passed.",
                "Transaction preparation failed.",
            )
        ],
    )
    save_transaction(transaction)
    save_journal(
        _build_transaction_journal(transaction, TransactionJournalState.PREPARED),
        directory,
    )
    (directory / "source.diff").write_text(transaction.source_diff, encoding="utf-8")
    return transaction, _receipt(transaction)


def prepare_freeform_transaction(
    request: FreeformSourcePatch,
    workspace: Path,
) -> tuple[SourceTransaction, TransactionReceipt]:
    artifact = Path(request.artifact_path).resolve()
    loaded = _load_artifact(artifact)
    architecture = loaded.architecture
    snapshot = loaded.snapshot
    evidence = loaded.evidence
    if architecture.framework != snapshot.framework:
        raise ValueError("architecture and snapshot framework bindings do not match")
    if transaction_artifact_kind(architecture.framework) != "source-artifact":
        raise ValueError("freeform source buffers are unavailable for model artifacts")
    workspace = workspace.resolve()
    base_source_digest = _base_source_digest(loaded)
    existing = _idempotent_transaction(workspace, request, base_source_digest)
    if existing is not None:
        return existing, _receipt(
            existing, source_writes=existing.state is TransactionState.COMMITTED
        )
    _validate_snapshot(loaded)
    project = _working_project(loaded)
    snapshot_files = {item.path: item for item in snapshot.source_files}
    seed = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    transaction_id = f"transaction:{_sha256((seed + datetime.now(UTC).isoformat()).encode())[:16]}"
    directory = workspace / "transactions" / transaction_id
    temporary_project = directory / "project"
    directory.mkdir(parents=True, exist_ok=False)
    try:
        _copy_project(project, temporary_project, workspace, loaded)
        file_changes: list[FileChange] = []
        diffs: list[str] = []
        anchor_payload: list[dict[str, str]] = []
        for buffer in request.buffers:
            source_file = snapshot_files.get(buffer.path)
            if source_file is None:
                raise ValueError(f"source buffer is outside the frozen snapshot: {buffer.path}")
            if source_file.sha256 != buffer.base_sha256:
                raise ValueError(f"source buffer base hash is stale: {buffer.path}")
            logical_path = buffer.path
            relative = _working_relative_path(
                loaded,
                logical_path,
                expected_digest=source_file.sha256,
            )
            unresolved = project / relative
            if unresolved.is_symlink():
                raise ValueError(f"source buffer cannot target a symbolic link: {buffer.path}")
            original_path = unresolved.resolve()
            if not original_path.is_relative_to(project) or not original_path.is_file():
                raise ValueError(f"source buffer path is unavailable: {buffer.path}")
            if relative.suffix not in {".py", ".json"}:
                raise ValueError(f"source buffer is not an editable text type: {buffer.path}")
            before = (
                _frozen_source_bytes(loaded, logical_path)
                if loaded.is_v2
                else original_path.read_bytes()
            )
            if len(before) > 1_000_000:
                raise ValueError(f"source buffer exceeds the 1 MB editing limit: {buffer.path}")
            try:
                before.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError(f"source buffer is not UTF-8 text: {buffer.path}") from error
            after = buffer.content.encode("utf-8")
            if b"\x00" in after:
                raise ValueError(f"source buffer contains a NUL byte: {buffer.path}")
            if len(after) > 1_000_000:
                raise ValueError(f"staged source buffer exceeds the 1 MB limit: {buffer.path}")
            if before == after:
                continue
            prepared_path = temporary_project / relative
            write_prepared(prepared_path, after)
            kind = "python" if relative.suffix == ".py" else "json"
            file_changes.append(
                FileChange(
                    path=relative.as_posix(),
                    kind=kind,
                    before_sha256=_sha256(before),
                    after_sha256=_sha256(after),
                )
            )
            diffs.append(_unified_diff(relative, before, after))
            anchor_payload.append(
                {"path": logical_path, "base_sha256": buffer.base_sha256}
            )
        if not file_changes:
            raise ValueError("source workspace has no staged changes")

        prepared_bundle = _analyze_at(
            temporary_project,
            loaded,
            directory / "analysis-prepare",
        )
        expected = graph_delta(
            architecture,
            prepared_bundle.architecture,
            evidence,
            prepared_bundle.evidence,
        )
        anchor = _sha256(
            json.dumps(
                {"revision": snapshot.revision, "buffers": anchor_payload},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        )
        transaction = SourceTransaction(
            transaction_id=transaction_id,
            framework=architecture.framework,
            transaction_adapter_id=transaction_adapter_id(architecture.framework),
            artifact_kind="source-artifact",
            validators=[
                "parse",
                "static-analysis",
                "full-observed-graph-delta",
                "publication",
            ],
            state=TransactionState.PREPARED,
            state_history=[
                TransactionState.DRAFT,
                TransactionState.PLANNED,
                TransactionState.PREPARED,
            ],
            request=request,
            created_at=datetime.now(UTC).isoformat(),
            workspace=str(workspace),
            original_project_root=str(project),
            temporary_project_root=str(temporary_project),
            artifact_path=str(artifact),
            source_snapshot_id=snapshot.snapshot_id,
            base_revision=snapshot.revision,
            anchor_fingerprint=anchor,
            base_source_corpus_digest=base_source_digest,
            base_analysis_input_digest=(
                loaded.analysis_input.analysis_input_digest if loaded.analysis_input else None
            ),
            base_registry_digest=(
                loaded.analysis_input.registry_digest if loaded.analysis_input else None
            ),
            base_exact_ir_digest=(loaded.exact_ir.exact_ir_digest if loaded.exact_ir else None),
            result_source_corpus_digest=prepared_bundle.source_corpus_digest,
            result_exact_ir_digest=prepared_bundle.exact_ir_digest,
            base_source_blobs=_transaction_base_blobs(loaded),
            reanalysis_route=(
                "analyze_project_v2+project_v1_compatibility"
                if loaded.is_v2
                else "analyze_with_adapter"
            ),
            file_changes=file_changes,
            source_diff="\n".join(diffs),
            expected_delta=expected,
            gates=[
                _gate(
                    "F-freeform-staging",
                    True,
                    "Snapshot paths, base hashes, UTF-8 limits, isolated staging, and full "
                    "observed Graph Delta capture passed.",
                    "Freeform source staging failed.",
                )
            ],
        )
        save_transaction(transaction)
        save_journal(
            _build_transaction_journal(transaction, TransactionJournalState.PREPARED),
            directory,
        )
        (directory / "source.diff").write_text(transaction.source_diff, encoding="utf-8")
        return transaction, _receipt(transaction)
    except Exception:
        if directory.is_dir():
            shutil.rmtree(directory)
        raise


def _fail(
    transaction: SourceTransaction,
    gate: GateResult,
    diagnostic: Diagnostic,
) -> tuple[SourceTransaction, TransactionReceipt]:
    failed = transaction.model_copy(
        update={
            "state": TransactionState.FAILED,
            "state_history": [*transaction.state_history, TransactionState.FAILED],
            "gates": [*transaction.gates, gate],
            "diagnostics": [*transaction.diagnostics, diagnostic],
        }
    )
    save_transaction(failed)
    transaction_directory = (
        Path(transaction.workspace) / "transactions" / transaction.transaction_id
    )
    journal_path = transaction_directory / "transaction-journal.json"
    if journal_path.is_file():
        journal = load_journal(journal_path)
        if journal.state in {
            TransactionJournalState.PREPARED,
            TransactionJournalState.VERIFIED,
        }:
            _transition_journal(
                journal,
                transaction_directory,
                TransactionJournalState.DISCARDED,
                diagnostics=[*journal.diagnostics, diagnostic],
            )
    return failed, _receipt(failed)


def _validate_source(path: Path, kind: str) -> None:
    if kind == "onnx":
        validate_model_artifact("onnx", path)
        return
    if kind == "binary":
        if not path.is_file():
            raise ValueError(f"prepared binary artifact is unavailable: {path}")
        return
    content = path.read_text(encoding="utf-8-sig")
    if kind == "python":
        ast.parse(content, filename=str(path))
    else:
        json.loads(content)


def _static_imports_resolve(project: Path, artifact: _LoadedArtifact) -> None:
    for source_file in artifact.snapshot.source_files:
        if Path(source_file.path).suffix not in {".py", ".pyi"}:
            continue
        path = project / _working_relative_path(artifact, source_file.path)
        tree = ast.parse(path.read_bytes(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.level:
                continue
            base = path.parent
            for _ in range(node.level - 1):
                base = base.parent
            module = Path(*(node.module or "").split("."))
            candidate = base / module
            if not candidate.with_suffix(".py").is_file() and not (candidate / "__init__.py").is_file():
                raise ValueError(f"relative import cannot be resolved statically: {node.module or '.'}")


def _validate_transaction_binding(
    transaction: SourceTransaction,
    artifact: _LoadedArtifact,
) -> None:
    expected = {
        "base_source_corpus_digest": _base_source_digest(artifact),
        "base_analysis_input_digest": (
            artifact.analysis_input.analysis_input_digest if artifact.analysis_input else None
        ),
        "base_registry_digest": (
            artifact.analysis_input.registry_digest if artifact.analysis_input else None
        ),
        "base_exact_ir_digest": artifact.exact_ir.exact_ir_digest if artifact.exact_ir else None,
    }
    for field, value in expected.items():
        if (
            field == "base_source_corpus_digest"
            and artifact.source_corpus is None
            and transaction.base_source_corpus_digest is None
        ):
            continue
        if getattr(transaction, field) != value:
            raise ValueError(f"transaction {field} no longer matches its analysis artifact")
    if artifact.source_corpus is not None:
        current = _transaction_base_blobs(artifact)
        if transaction.base_source_blobs != current:
            raise ValueError("transaction base blob set no longer matches its source corpus")
        if transaction.source_anchor is not None:
            source = next(
                (
                    item
                    for item in artifact.source_corpus.files
                    if item.logical_path == transaction.source_anchor.logical_path
                ),
                None,
            )
            if source is None or source.sha256 != transaction.source_anchor.blob_digest:
                raise ValueError("transaction SourceAnchor is outside its frozen source corpus")


def _shape_invariants(bundle: Any) -> None:
    config = bundle.snapshot.resolved_config
    d_model = config.get("d_model")
    num_heads = config.get("num_heads")
    if (
        isinstance(d_model, int)
        and isinstance(num_heads, int)
        and (d_model <= 0 or num_heads <= 0 or d_model % num_heads)
    ):
        raise ValueError("d_model must be positive and divisible by num_heads")
    for node in bundle.architecture.nodes:
        for parameter in node.parameters:
            if (
                parameter.name in {"in_features", "out_features", "normalized_shape"}
                and isinstance(parameter.value, (int, float))
                and parameter.value <= 0
            ):
                raise ValueError(f"{node.node_id}.{parameter.name} must be positive")


def _run_tests(project: Path, commands: list[list[str]]) -> list[dict[str, Any]]:
    all_commands = [[sys.executable, "-m", "compileall", "-q", "."], *commands]
    results: list[dict[str, Any]] = []
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    for command in all_commands:
        completed = subprocess.run(
            command,
            cwd=project,
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        result = {
            "command": command,
            "exit_code": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
        results.append(result)
        if completed.returncode:
            raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return results


def verify_transaction(path: Path) -> tuple[SourceTransaction, TransactionReceipt]:
    transaction = load_transaction(path)
    if transaction.state is not TransactionState.PREPARED:
        raise ValueError(f"only prepared transactions can be verified, got {transaction.state.value}")
    project = Path(transaction.temporary_project_root)
    artifact = _load_artifact(Path(transaction.artifact_path))
    gates = list(transaction.gates)
    history = list(transaction.state_history)
    try:
        for change in transaction.file_changes:
            _validate_source(project / change.path, change.kind)
        if transaction.artifact_kind != "model-artifact":
            _validate_transaction_binding(transaction, artifact)
            _static_imports_resolve(project, artifact)
    except Exception as error:  # noqa: BLE001
        return _fail(
            transaction,
            _gate("F-source-validation", False, "Source is valid.", "Source validation failed."),
            _diagnostic("TRANSACTION_SOURCE_INVALID", str(error)),
        )
    gates.append(
        _gate(
            "F-source-validation",
            True,
            "Prepared source parses and relative imports resolve statically.",
            "Source validation failed.",
        )
    )
    history.append(TransactionState.SOURCE_VALIDATED)
    try:
        observed_bundle = _analyze_at(
            project,
            artifact,
            Path(transaction.workspace)
            / "transactions"
            / transaction.transaction_id
            / "analysis-verify",
        )
        semantic_gates, semantic_diagnostics = validate_architecture(
            observed_bundle.architecture,
            observed_bundle.evidence,
            observed_bundle.snapshot,
        )
        if semantic_diagnostics or any(item.status == "failed" for item in semantic_gates):
            raise ValueError("reanalyzed Exact IR failed semantic validation")
    except Exception as error:  # noqa: BLE001
        staged = transaction.model_copy(update={"gates": gates, "state_history": history})
        return _fail(
            staged,
            _gate("F-reanalysis", False, "Reanalysis passed.", "Exact IR reanalysis failed."),
            _diagnostic("TRANSACTION_REANALYSIS_FAILED", str(error)),
        )
    gates.append(_gate("F-reanalysis", True, "Exact IR reanalysis passed.", "Reanalysis failed."))
    history.append(TransactionState.REANALYZED)

    original = artifact.architecture
    original_evidence = artifact.evidence
    observed = graph_delta(
        original,
        observed_bundle.architecture,
        original_evidence,
        observed_bundle.evidence,
    )
    if observed != transaction.expected_delta:
        staged = transaction.model_copy(
            update={"gates": gates, "observed_delta": observed, "state_history": history}
        )
        return _fail(
            staged,
            _gate(
                "F-graph-delta",
                False,
                "Graph delta matched.",
                "Observed Graph Delta differs from Expected Graph Delta.",
            ),
            _diagnostic("GRAPH_DELTA_MISMATCH", "Expected and observed Graph Delta differ."),
        )
    if transaction.artifact_kind == "model-artifact":
        try:
            validate_model_transaction_delta(
                transaction.request,
                original,
                observed_bundle.architecture,
                observed,
            )
        except ValueError as error:
            staged = transaction.model_copy(
                update={"gates": gates, "observed_delta": observed, "state_history": history}
            )
            return _fail(
                staged,
                _gate(
                    "F-graph-delta",
                    False,
                    "Model artifact oracle passed.",
                    "Model artifact Graph Delta oracle failed.",
                ),
                _diagnostic("MODEL_DELTA_ORACLE_FAILED", str(error)),
            )
    elif isinstance(transaction.request, SemanticStructuralPatch):
        try:
            validate_structural_oracle(
                transaction.request,
                original,
                observed_bundle.architecture,
                observed,
            )
        except ValueError as error:
            staged = transaction.model_copy(
                update={"gates": gates, "observed_delta": observed, "state_history": history}
            )
            return _fail(
                staged,
                _gate(
                    "F-graph-delta",
                    False,
                    "Structural oracle passed.",
                    "Structural Graph Delta oracle failed.",
                ),
                _diagnostic("STRUCTURAL_DELTA_ORACLE_FAILED", str(error)),
            )
    freeform = isinstance(transaction.request, FreeformSourcePatch)
    gates.append(
        _gate(
            "F-graph-delta",
            True,
            (
                "The complete staged Graph Delta was reproduced exactly for high-risk review."
                if freeform
                else "Expected and observed Graph Delta match exactly and the operation oracle passed."
            ),
            "Graph Delta validation failed.",
        )
    )
    history.append(TransactionState.GRAPH_DELTA_VALIDATED)
    try:
        _shape_invariants(observed_bundle)
    except ValueError as error:
        staged = transaction.model_copy(
            update={"gates": gates, "observed_delta": observed, "state_history": history}
        )
        return _fail(
            staged,
            _gate("F-shape-type", False, "Shape invariants passed.", "Shape invariants failed."),
            _diagnostic("SHAPE_INVARIANT_FAILED", str(error)),
        )
    gates.append(_gate("F-shape-type", True, "Shape/type invariants passed.", "Shape checks failed."))

    try:
        test_results = _run_tests(project, transaction.request.targeted_tests)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        staged = transaction.model_copy(
            update={"gates": gates, "observed_delta": observed, "state_history": history}
        )
        return _fail(
            staged,
            _gate("F-targeted-tests", False, "Targeted tests passed.", "Targeted tests failed."),
            _diagnostic("TARGETED_TEST_FAILED", str(error)),
        )
    gates.append(
        _gate(
            "F-targeted-tests",
            True,
            f"Built-in compile check and {len(transaction.request.targeted_tests)} requested tests passed.",
            "Targeted tests failed.",
        )
    )
    history.append(TransactionState.TESTS_PASSED)

    try:
        views = compile_views(observed_bundle.architecture)
        publication_gates, publication_diagnostics = validate_publication(
            observed_bundle.architecture, views
        )
        scenes = [build_scene(view, build_visual_spec(view)) for view in views]
        geometry_failures = [
            diagnostic
            for scene in scenes
            for _, diagnostics in [validate_geometry(scene)]
            for diagnostic in diagnostics
        ]
        if publication_diagnostics or geometry_failures or any(
            item.status == "failed" for item in publication_gates
        ):
            raise ValueError("publication or geometry validation failed")
    except Exception as error:  # noqa: BLE001
        staged = transaction.model_copy(
            update={
                "gates": gates,
                "observed_delta": observed,
                "test_results": test_results,
                "state_history": history,
            }
        )
        return _fail(
            staged,
            _gate("F-visual-recompile", False, "Visual recompile passed.", "Visual recompile failed."),
            _diagnostic("VISUAL_RECOMPILE_FAILED", str(error)),
        )
    gates.append(
        _gate(
            "F-visual-recompile",
            True,
            "Collapsed and fully expanded containment projections passed deterministic geometry gates.",
            "Visual recompile failed.",
        )
    )

    if transaction.request.runtime_input_spec:
        verification_dir = (
            Path(transaction.workspace) / "transactions" / transaction.transaction_id / "runtime"
        )
        verification_dir.mkdir(parents=True, exist_ok=True)
        artifact = verification_dir / "architecture.json"
        artifact.write_text(observed_bundle.architecture.model_dump_json(), encoding="utf-8")
        (verification_dir / "source-snapshot.json").write_text(
            observed_bundle.snapshot.model_dump_json(), encoding="utf-8"
        )
        input_path = Path(transaction.request.runtime_input_spec)
        if not input_path.is_absolute():
            input_path = Path(transaction.original_project_root) / input_path
        runtime_receipt = trace_runtime(artifact, input_path, verification_dir)
        if runtime_receipt.status != "ok":
            staged = transaction.model_copy(
                update={
                    "gates": gates,
                    "observed_delta": observed,
                    "test_results": test_results,
                    "state_history": history,
                }
            )
            return _fail(
                staged,
                _gate("F-runtime-replay", False, "Runtime replay passed.", "Runtime replay failed."),
                _diagnostic("RUNTIME_REPLAY_FAILED", "Requested isolated runtime replay failed."),
            )
        gates.append(
            _gate(
                "F-runtime-replay",
                True,
                "Requested isolated runtime replay passed.",
                "Runtime replay failed.",
            )
        )

    verified = transaction.model_copy(
        update={
            "state": TransactionState.REVIEW_READY,
            "state_history": [*history, TransactionState.REVIEW_READY],
            "gates": gates,
            "observed_delta": observed,
            "result_source_corpus_digest": observed_bundle.source_corpus_digest,
            "result_exact_ir_digest": observed_bundle.exact_ir_digest,
            "test_results": test_results,
        }
    )
    save_transaction(verified)
    transaction_directory = (
        Path(transaction.workspace) / "transactions" / transaction.transaction_id
    )
    journal = load_journal(transaction_directory)
    _transition_journal(
        journal,
        transaction_directory,
        TransactionJournalState.VERIFIED,
    )
    return verified, _receipt(verified)


def _atomic_replace(path: Path, content: bytes, *, mode: int | None = None) -> None:
    if path.is_symlink():
        raise ValueError(f"refusing to replace symbolic link: {path}")
    target_mode = stat.S_IMODE(path.stat().st_mode) if mode is None else mode
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.chmod(target_mode)
    temporary.replace(path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _write_verified_backup(path: Path, content: bytes, *, mode: int, digest: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.chmod(mode)
    temporary.replace(path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    if _sha256(path.read_bytes()) != digest:
        raise ValueError(f"transaction backup verification failed: {path}")


def _validate_committed_result(
    transaction: SourceTransaction,
    artifact: _LoadedArtifact,
    analysis_directory: Path,
) -> _ReanalysisBundle:
    committed_bundle = _analyze_at(
        Path(transaction.original_project_root),
        artifact,
        analysis_directory,
    )
    committed_delta = graph_delta(
        artifact.architecture,
        committed_bundle.architecture,
        artifact.evidence,
        committed_bundle.evidence,
    )
    if committed_delta != transaction.expected_delta:
        expected_payload = transaction.expected_delta.model_dump(mode="json")
        committed_payload = committed_delta.model_dump(mode="json")
        mismatched_fields = sorted(
            key for key in expected_payload if expected_payload[key] != committed_payload[key]
        )
        raise ValueError(
            "committed source did not reproduce the verified Graph Delta; "
            f"mismatched fields: {', '.join(mismatched_fields)}"
        )
    if transaction.base_analysis_input_digest is not None and (
        transaction.result_source_corpus_digest != committed_bundle.source_corpus_digest
        or transaction.result_exact_ir_digest != committed_bundle.exact_ir_digest
    ):
        raise ValueError("post-commit analysis digests differ from the verified result")
    return committed_bundle


def _rollback_journal_files(
    transaction: SourceTransaction,
    journal: TransactionJournal,
    transaction_directory: Path,
) -> tuple[TransactionJournal, list[str]]:
    recovered: list[str] = []
    files = list(journal.files)
    for index, entry in enumerate(files):
        original = Path(transaction.original_project_root) / entry.working_path
        backup = transaction_directory / entry.backup_relative_path
        current_digest = _sha256(original.read_bytes())
        if current_digest != entry.before_sha256:
            if not backup.is_file() or _sha256(backup.read_bytes()) != entry.before_sha256:
                raise ValueError(f"verified rollback backup is unavailable: {entry.logical_path}")
            _atomic_replace(
                original,
                backup.read_bytes(),
                mode=entry.original_metadata.mode,
            )
            recovered.append(entry.logical_path)
        if _sha256(original.read_bytes()) != entry.before_sha256:
            raise ValueError(f"rollback digest proof failed: {entry.logical_path}")
        files[index] = entry.model_copy(
            update={
                "replacement_status": "rolled-back",
                "rename_completed": True,
                "directory_fsync_completed": True,
            }
        )
        journal = _transition_journal(
            journal,
            transaction_directory,
            TransactionJournalState.ROLLBACK_REQUIRED,
            files=files,
        )
    return journal, recovered


def _recovery_receipt(
    transaction: SourceTransaction,
    journal: TransactionJournal,
    *,
    outcome: str,
    before_state_proven: bool,
    after_state_proven: bool,
    source_writes: bool,
    recovered_files: list[str],
    diagnostics: list[Diagnostic] | None = None,
) -> RecoveryReceipt:
    return RecoveryReceipt(
        receipt_id=(
            f"recovery:{transaction.transaction_id.removeprefix('transaction:')}:"
            f"{outcome}"
        ),
        transaction_id=transaction.transaction_id,
        journal_id=journal.journal_id,
        outcome=outcome,
        journal_state=journal.state,
        before_state_proven=before_state_proven,
        after_state_proven=after_state_proven,
        source_writes=source_writes,
        recovered_files=recovered_files,
        diagnostics=diagnostics or [],
        created_at=datetime.now(UTC).isoformat(),
    )


def commit_transaction(path: Path) -> tuple[SourceTransaction, TransactionReceipt]:
    transaction = load_transaction(path)
    if transaction.state is not TransactionState.REVIEW_READY:
        raise ValueError(f"only review-ready transactions can be committed, got {transaction.state.value}")
    if (
        transaction.semantic_intent is not None
        and framework_form_capability(
            transaction.semantic_intent.framework,
            transaction.semantic_intent.form_id,
            "artifact_commit",
        )
        == "unavailable"
    ):
        return _fail(
            transaction,
            _gate(
                "F-form-artifact-commit",
                False,
                "Framework form permits artifact commit.",
                "Artifact commit is unavailable for the selected framework form.",
            ),
            _diagnostic(
                "FORM_ARTIFACT_COMMIT_UNAVAILABLE",
                f"artifact_commit is unavailable for {transaction.semantic_intent.form_id}",
            ),
        )
    artifact = _load_artifact(Path(transaction.artifact_path))
    try:
        _validate_transaction_binding(transaction, artifact)
        _validate_snapshot(artifact)
        for change in transaction.file_changes:
            original = Path(transaction.original_project_root) / change.path
            if _sha256(original.read_bytes()) != change.before_sha256:
                raise ValueError(f"concurrent modification detected: {change.path}")
            prepared = Path(transaction.temporary_project_root) / change.path
            if _sha256(prepared.read_bytes()) != change.after_sha256:
                raise ValueError(f"prepared transaction content changed after verification: {change.path}")
    except Exception as error:  # noqa: BLE001
        return _fail(
            transaction,
            _gate("F-commit-concurrency", False, "Source is current.", "Commit freshness failed."),
            _diagnostic("CONCURRENT_MODIFICATION", str(error)),
        )

    transaction_directory = (
        Path(transaction.workspace) / "transactions" / transaction.transaction_id
    )
    journal = load_journal(transaction_directory)
    if journal.transaction_id != transaction.transaction_id:
        raise ValueError("transaction journal identity does not match the transaction")
    if journal.state is not TransactionJournalState.VERIFIED:
        raise ValueError(f"transaction journal is not verified: {journal.state.value}")
    try:
        files = list(journal.files)
        for index, entry in enumerate(files):
            original = Path(transaction.original_project_root) / entry.working_path
            backup = transaction_directory / entry.backup_relative_path
            content = original.read_bytes()
            _write_verified_backup(
                backup,
                content,
                mode=entry.original_metadata.mode,
                digest=entry.before_sha256,
            )
            files[index] = entry.model_copy(update={"backup_verified": True})
        journal = _transition_journal(
            journal,
            transaction_directory,
            TransactionJournalState.COMMIT_INTENT_RECORDED,
            files=files,
        )
        journal = _transition_journal(
            journal,
            transaction_directory,
            TransactionJournalState.REPLACING_FILES,
        )
        files = list(journal.files)
        for index, entry in enumerate(files):
            original = Path(transaction.original_project_root) / entry.working_path
            prepared = Path(transaction.temporary_project_root) / entry.working_path
            _atomic_replace(
                original,
                prepared.read_bytes(),
                mode=entry.original_metadata.mode,
            )
            if _sha256(original.read_bytes()) != entry.after_sha256:
                raise ValueError(f"replacement digest proof failed: {entry.logical_path}")
            files[index] = entry.model_copy(
                update={
                    "replacement_status": "replaced",
                    "rename_completed": True,
                    "directory_fsync_completed": True,
                }
            )
            journal = _transition_journal(
                journal,
                transaction_directory,
                TransactionJournalState.REPLACING_FILES,
                files=files,
            )
        journal = _transition_journal(
            journal,
            transaction_directory,
            TransactionJournalState.POST_COMMIT_VALIDATING,
        )
        _validate_committed_result(
            transaction,
            artifact,
            transaction_directory / "analysis-commit",
        )
    except Exception as error:  # noqa: BLE001
        diagnostic = _diagnostic("ATOMIC_COMMIT_FAILED", str(error))
        journal = _transition_journal(
            journal,
            transaction_directory,
            TransactionJournalState.ROLLBACK_REQUIRED,
            diagnostics=[*journal.diagnostics, diagnostic],
        )
        try:
            journal, recovered_files = _rollback_journal_files(
                transaction,
                journal,
                transaction_directory,
            )
            journal = _transition_journal(
                journal,
                transaction_directory,
                TransactionJournalState.ROLLED_BACK,
            )
            recovery = _recovery_receipt(
                transaction,
                journal,
                outcome="rolled-back",
                before_state_proven=True,
                after_state_proven=False,
                source_writes=False,
                recovered_files=recovered_files,
                diagnostics=[diagnostic],
            )
        except Exception as rollback_error:  # noqa: BLE001
            recovery_diagnostic = _diagnostic("RECOVERY_FAILED", str(rollback_error))
            journal = _transition_journal(
                journal,
                transaction_directory,
                TransactionJournalState.RECOVERY_FAILED,
                diagnostics=[*journal.diagnostics, recovery_diagnostic],
            )
            recovery = _recovery_receipt(
                transaction,
                journal,
                outcome="recovery-failed",
                before_state_proven=False,
                after_state_proven=False,
                source_writes=True,
                recovered_files=[],
                diagnostics=[diagnostic, recovery_diagnostic],
            )
        save_recovery_receipt(recovery, transaction_directory)
        failed = transaction.model_copy(
            update={
                "state": TransactionState.FAILED,
                "state_history": [*transaction.state_history, TransactionState.FAILED],
                "gates": [
                    *transaction.gates,
                    _gate(
                        "F-atomic-commit",
                        False,
                        "Commit passed.",
                        "Journaled commit failed; see the recovery receipt.",
                    ),
                ],
                "diagnostics": [*transaction.diagnostics, diagnostic, *recovery.diagnostics],
            }
        )
        save_transaction(failed)
        receipt = _receipt(failed, source_writes=recovery.source_writes).model_copy(
            update={"recovery_receipt_id": recovery.receipt_id}
        )
        save_transaction_receipt(receipt, transaction_directory)
        return failed, receipt

    committed = transaction.model_copy(
        update={
            "state": TransactionState.COMMITTED,
            "state_history": [*transaction.state_history, TransactionState.COMMITTED],
            "gates": [
                *transaction.gates,
                _gate(
                    "F-commit-concurrency",
                    True,
                    "Original revision and file hashes are unchanged.",
                    "Commit freshness failed.",
                ),
                _gate(
                    "F-atomic-commit",
                    True,
                    "Atomic source replacement and post-commit reanalysis passed.",
                    "Atomic commit failed.",
                ),
            ],
        }
    )
    save_transaction(committed)
    journal = _transition_journal(
        journal,
        transaction_directory,
        TransactionJournalState.COMMITTED,
        post_commit_gates=[
            *journal.post_commit_gates,
            _gate(
                "F-post-commit-reanalysis",
                True,
                "Committed source reproduced verified source and Exact IR digests.",
                "Post-commit reanalysis failed.",
            ),
        ],
    )
    return committed, _receipt(committed, source_writes=True)


def _persist_recovery_failure(
    transaction: SourceTransaction,
    diagnostic: Diagnostic,
) -> SourceTransaction:
    if transaction.state is TransactionState.COMMITTED:
        return transaction
    failed = transaction.model_copy(
        update={
            "state": TransactionState.FAILED,
            "state_history": [*transaction.state_history, TransactionState.FAILED],
            "diagnostics": [*transaction.diagnostics, diagnostic],
        }
    )
    save_transaction(failed)
    return failed


def recover_incomplete_transactions(workspace: Path) -> list[RecoveryReceipt]:
    transaction_root = workspace.resolve() / "transactions"
    if not transaction_root.is_dir():
        return []
    receipts: list[RecoveryReceipt] = []
    recoverable = {
        TransactionJournalState.COMMIT_INTENT_RECORDED,
        TransactionJournalState.REPLACING_FILES,
        TransactionJournalState.POST_COMMIT_VALIDATING,
        TransactionJournalState.ROLLBACK_REQUIRED,
    }
    for transaction_directory in sorted(path for path in transaction_root.iterdir() if path.is_dir()):
        journal_path = transaction_directory / "transaction-journal.json"
        transaction_path = transaction_directory / "transaction.json"
        if not journal_path.is_file() or not transaction_path.is_file():
            continue
        journal = load_journal(journal_path)
        if journal.state not in recoverable:
            continue
        transaction = load_transaction(transaction_path)
        before_matches: list[bool] = []
        after_matches: list[bool] = []
        try:
            for entry in journal.files:
                original = Path(transaction.original_project_root) / entry.working_path
                current = _sha256(original.read_bytes())
                before_matches.append(current == entry.before_sha256)
                after_matches.append(current == entry.after_sha256)
            all_before = all(before_matches)
            all_after = all(after_matches)
            if all_before:
                outcome = (
                    "rolled-back"
                    if journal.state is TransactionJournalState.ROLLBACK_REQUIRED
                    else "discarded"
                )
                terminal = (
                    TransactionJournalState.ROLLED_BACK
                    if outcome == "rolled-back"
                    else TransactionJournalState.DISCARDED
                )
                journal = _transition_journal(
                    journal,
                    transaction_directory,
                    terminal,
                )
                diagnostic = _diagnostic(
                    "COMMIT_RECOVERY_DISCARDED",
                    "Startup recovery proved that every source file remained at its before digest.",
                )
                _persist_recovery_failure(transaction, diagnostic)
                receipt = _recovery_receipt(
                    transaction,
                    journal,
                    outcome=outcome,
                    before_state_proven=True,
                    after_state_proven=False,
                    source_writes=False,
                    recovered_files=[],
                    diagnostics=[diagnostic],
                )
            elif all_after:
                artifact = _load_artifact(Path(transaction.artifact_path))
                journal = _transition_journal(
                    journal,
                    transaction_directory,
                    TransactionJournalState.POST_COMMIT_VALIDATING,
                )
                _validate_committed_result(
                    transaction,
                    artifact,
                    transaction_directory / "analysis-recovery",
                )
                committed = transaction.model_copy(
                    update={
                        "state": TransactionState.COMMITTED,
                        "state_history": [
                            *transaction.state_history,
                            TransactionState.COMMITTED,
                        ],
                    }
                )
                save_transaction(committed)
                transaction = committed
                journal = _transition_journal(
                    journal,
                    transaction_directory,
                    TransactionJournalState.COMMITTED,
                    post_commit_gates=[
                        *journal.post_commit_gates,
                        _gate(
                            "F-recovery-reanalysis",
                            True,
                            "Startup recovery reproduced the verified source and Exact IR digests.",
                            "Recovery reanalysis failed.",
                        ),
                    ],
                )
                receipt = _recovery_receipt(
                    transaction,
                    journal,
                    outcome="committed",
                    before_state_proven=False,
                    after_state_proven=True,
                    source_writes=True,
                    recovered_files=[],
                )
            else:
                journal = _transition_journal(
                    journal,
                    transaction_directory,
                    TransactionJournalState.ROLLBACK_REQUIRED,
                )
                journal, recovered_files = _rollback_journal_files(
                    transaction,
                    journal,
                    transaction_directory,
                )
                journal = _transition_journal(
                    journal,
                    transaction_directory,
                    TransactionJournalState.ROLLED_BACK,
                )
                diagnostic = _diagnostic(
                    "MIXED_COMMIT_RECOVERED",
                    "Startup recovery found mixed before/after file state and restored verified backups.",
                )
                _persist_recovery_failure(transaction, diagnostic)
                receipt = _recovery_receipt(
                    transaction,
                    journal,
                    outcome="rolled-back",
                    before_state_proven=True,
                    after_state_proven=False,
                    source_writes=False,
                    recovered_files=recovered_files,
                    diagnostics=[diagnostic],
                )
        except Exception as error:  # noqa: BLE001
            diagnostic = _diagnostic("RECOVERY_FAILED", str(error))
            journal = _transition_journal(
                journal,
                transaction_directory,
                TransactionJournalState.RECOVERY_FAILED,
                diagnostics=[*journal.diagnostics, diagnostic],
            )
            _persist_recovery_failure(transaction, diagnostic)
            receipt = _recovery_receipt(
                transaction,
                journal,
                outcome="recovery-failed",
                before_state_proven=False,
                after_state_proven=False,
                source_writes=True,
                recovered_files=[],
                diagnostics=[diagnostic],
            )
        save_recovery_receipt(receipt, transaction_directory)
        receipts.append(receipt)
    return receipts


def discard_transaction(path: Path) -> tuple[SourceTransaction, TransactionReceipt]:
    transaction = load_transaction(path)
    if transaction.state in {TransactionState.COMMITTED, TransactionState.DISCARDED}:
        raise ValueError(f"transaction cannot be discarded from {transaction.state.value}")
    temporary_project = Path(transaction.temporary_project_root)
    if temporary_project.is_dir():
        shutil.rmtree(temporary_project)
    discarded = transaction.model_copy(
        update={
            "state": TransactionState.DISCARDED,
            "state_history": [*transaction.state_history, TransactionState.DISCARDED],
        }
    )
    save_transaction(discarded)
    transaction_directory = (
        Path(transaction.workspace) / "transactions" / transaction.transaction_id
    )
    journal_path = transaction_directory / "transaction-journal.json"
    if journal_path.is_file():
        journal = load_journal(journal_path)
        if journal.state not in {
            TransactionJournalState.COMMITTED,
            TransactionJournalState.ROLLED_BACK,
            TransactionJournalState.RECOVERY_FAILED,
            TransactionJournalState.DISCARDED,
        }:
            _transition_journal(
                journal,
                transaction_directory,
                TransactionJournalState.DISCARDED,
            )
    return discarded, _receipt(discarded)
