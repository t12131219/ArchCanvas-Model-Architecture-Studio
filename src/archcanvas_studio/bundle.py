from __future__ import annotations

import difflib
import hashlib
import json
import secrets
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import TypeAdapter

from archcanvas_adapters import adapter_capabilities
from archcanvas_core.builtin_registry import BuiltinModuleRegistry
from archcanvas_core.digest_protocol import domain_digest
from archcanvas_core.models import (
    AffectedObjectReviewBinding,
    AgentProposal,
    ArchitectureIR,
    CanvasDocument,
    Diagnostic,
    DraftEdge,
    DraftGraphDocument,
    DraftNode,
    DraftPort,
    EditIntent,
    EditProofState,
    EditProofStatus,
    EditTargetScope,
    EvidenceRecord,
    FreeformSourceBufferPatch,
    FreeformSourcePatch,
    GraphDelta,
    ParameterEditContext,
    ProjectSession,
    ProposalReconciliationReceipt,
    ProposedConnection,
    ProtocolMigrationReceipt,
    PublicationHierarchy,
    PublicationView,
    RecoveryReceipt,
    RoundTripConformanceReport,
    RuntimeTrace,
    SearchSubject,
    SemanticAnnotationOverlay,
    SemanticIntentV2,
    SemanticParameterPatch,
    SemanticStructuralPatch,
    SourceFile,
    SourceSnapshot,
    SourceTransaction,
    SourceWorkspaceDocument,
    StagedSourceBuffer,
    TopologyDraftCapability,
    TopologyEditSession,
    TopologyReviewReceipt,
    TransactionState,
    ValidationRun,
    WritebackSummary,
)
from archcanvas_core.module_contract import migrate_parameter_values
from archcanvas_core.protocols import read_draft_graph_document_protocol
from archcanvas_core.source_v2 import AnalysisEnvironmentManifest, AnalysisInputManifest
from archcanvas_patterns import exact_ir_digest
from archcanvas_publication import (
    build_scene,
    build_visual_spec,
    compile_hierarchy,
    expandable_node_ids,
    project_hierarchy,
    render_svg,
)
from archcanvas_transactions import (
    commit_transaction,
    discard_transaction,
    plan_connection,
    prepare_freeform_transaction,
    prepare_transaction,
    recover_incomplete_transactions,
    resolve_parameter_edit_contexts,
    verify_transaction,
)
from archcanvas_transactions.store import load_transaction

from .conformance import build_intent_source_report, build_source_view_report
from .contract_maintenance import ContractMaintenanceManager
from .document import (
    create_canvas_document,
    derive_view_state,
    load_canvas_document_with_receipt,
    persist_canvas_document,
    source_binding_digest,
)
from .draft_analysis import analyze_draft_graph
from .generated_projects import GeneratedProjectManager
from .navigation import PROJECTIONS, build_navigation_projections
from .operations import build_search_index, run_validation, studio_fingerprint
from .project import create_project_session, discover_project

STATIC_ROOT = Path(__file__).resolve().parent / "static"
MODULE_REGISTRY = BuiltinModuleRegistry()
DRAFT_DOCUMENT_DIGEST_DOMAIN = "archcanvas:draft-graph-document:v1"


def draft_document_digest(draft: DraftGraphDocument) -> str:
    return domain_digest(
        DRAFT_DOCUMENT_DIGEST_DOMAIN,
        draft.model_dump(
            mode="json",
            exclude={"proofs", "lowering_status", "writeback_summary"},
        ),
    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _conformance_report_path(
    workspace: Path, report: RoundTripConformanceReport
) -> Path:
    filename = report.report_id.removeprefix("round-trip:")
    return workspace / "conformance" / f"{filename}.json"


def _load_conformance_reports(workspace: Path) -> list[RoundTripConformanceReport]:
    directory = workspace / "conformance"
    if not directory.is_dir():
        return []
    reports: list[RoundTripConformanceReport] = []
    report_ids: set[str] = set()
    for path in sorted(directory.glob("*.json")):
        report = RoundTripConformanceReport.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if report.report_id in report_ids:
            raise ValueError(f"duplicate round-trip report id: {report.report_id}")
        report_ids.add(report.report_id)
        reports.append(report)
    return reports


def _load_recovery_receipts(workspace: Path) -> list[RecoveryReceipt]:
    transaction_root = workspace / "transactions"
    if not transaction_root.is_dir():
        return []
    return [
        RecoveryReceipt.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(transaction_root.glob("*/recovery-receipt.json"))
    ]


def _load_protocol_migration_receipts(
    workspace: Path,
) -> list[ProtocolMigrationReceipt]:
    directory = workspace / "protocol-migrations"
    if not directory.is_dir():
        return []
    receipts: list[ProtocolMigrationReceipt] = []
    receipt_ids: set[str] = set()
    for path in sorted(directory.glob("*.json")):
        receipt = ProtocolMigrationReceipt.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if receipt.receipt_id in receipt_ids:
            raise ValueError(f"duplicate protocol migration receipt id: {receipt.receipt_id}")
        receipt_ids.add(receipt.receipt_id)
        receipts.append(receipt)
    return receipts


def _parameter_value_matches(value: object, value_type: str) -> bool:
    if value is None or value_type == "any":
        return True
    if value_type == "boolean":
        return isinstance(value, bool)
    if value_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type == "number":
        return isinstance(value, (int, float, str)) and not isinstance(value, bool)
    if value_type == "string":
        return isinstance(value, str)
    if value_type == "shape":
        return isinstance(value, (int, str, list, tuple)) and not isinstance(value, bool)
    return False


def _reachable_expansions(
    navigation: dict[str, object], projection: str, expanded_ids: set[str]
) -> set[str]:
    projections = navigation.get("projections", {})
    projection_data = projections.get(projection, {}) if isinstance(projections, dict) else {}
    rows = projection_data.get("nodes", []) if isinstance(projection_data, dict) else []
    parent_by_id = {
        str(row["id"]): (
            str(row["parent_id"]) if row.get("parent_id") is not None else None
        )
        for row in rows
        if isinstance(row, dict) and "id" in row
    }
    reachable: set[str] = set()
    pending = set(expanded_ids) & set(parent_by_id)
    changed = True
    while changed:
        changed = False
        for row_id in sorted(pending - reachable):
            parent_id = parent_by_id[row_id]
            if parent_id is None or parent_id in reachable:
                reachable.add(row_id)
                changed = True
    return reachable


@dataclass
class StudioBundle:
    artifact_path: Path
    workspace: Path
    static_dir: Path
    document_path: Path
    architecture: ArchitectureIR
    snapshot: SourceSnapshot
    evidence: list[EvidenceRecord]
    runtime_trace: RuntimeTrace | None
    runtime_node_evidence: dict[str, list[str]]
    semantic_overlay: SemanticAnnotationOverlay | None
    hierarchy: PublicationHierarchy
    views: dict[str, PublicationView]
    document: CanvasDocument
    project_session: ProjectSession
    project_discovery: dict[str, object]
    draft_path: Path
    draft: DraftGraphDocument
    source_workspace_path: Path
    source_workspace: SourceWorkspaceDocument
    search_index: list[SearchSubject]
    validation_runs: list[ValidationRun]
    navigation: dict[str, object]
    parameter_edit_contexts: list[ParameterEditContext]
    analysis_environment: AnalysisEnvironmentManifest | None
    analysis_input: AnalysisInputManifest | None
    validation_generation: int = 0
    active_transaction: SourceTransaction | None = None
    active_proposal: AgentProposal | None = None
    topology_session: TopologyEditSession | None = None
    topology_base_draft: DraftGraphDocument | None = None
    topology_review_receipt: TopologyReviewReceipt | None = None
    contract_maintenance: ContractMaintenanceManager | None = None
    generated_projects: GeneratedProjectManager | None = None
    round_trip_reports: list[RoundTripConformanceReport] | None = None
    recovery_receipts: list[RecoveryReceipt] | None = None
    protocol_migration_receipts: list[ProtocolMigrationReceipt] | None = None

    def _verify_transaction_if_prepared(
        self, transaction: SourceTransaction
    ) -> SourceTransaction:
        if transaction.state is not TransactionState.PREPARED:
            return transaction
        verified, _ = verify_transaction(
            self.workspace / "transactions" / transaction.transaction_id
        )
        return verified

    def _all_round_trip_reports(self) -> list[RoundTripConformanceReport]:
        reports = {
            report.report_id: report for report in (self.round_trip_reports or [])
        }
        if self.generated_projects is not None:
            reports.update(
                {
                    report.report_id: report
                    for report in self.generated_projects.conformance_reports()
                }
            )
        return list(reports.values())

    def _semantic_intent_source_digest(self) -> str:
        corpus_path = self.artifact_path.parent / "source-corpus-v2.json"
        if corpus_path.is_file():
            payload = json.loads(corpus_path.read_text(encoding="utf-8"))
            digest = payload.get("source_corpus_digest")
            if isinstance(digest, str):
                return digest
        payload = {
            "snapshot_id": self.snapshot.snapshot_id,
            "revision": self.snapshot.revision,
            "config_digest": self.snapshot.config_digest,
            "source_files": [
                {"path": item.path, "sha256": item.sha256}
                for item in sorted(self.snapshot.source_files, key=lambda item: item.path)
            ],
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def _framework_form_id(self) -> str:
        return self.project_session.form_id

    def _parameter_semantic_intent(
        self,
        request: SemanticParameterPatch,
    ) -> SemanticIntentV2:
        context = next(
            (
                item
                for item in self.parameter_edit_contexts
                if item.target_node_id == request.target_node_id
                and item.parameter_name == request.parameter_name
            ),
            None,
        )
        if context is None:
            raise ValueError("parameter edit context is unavailable")
        scope = request.edit_target_scope or context.default_scope
        if scope is None:
            scope = context.allowed_scopes[0] if context.allowed_scopes else EditTargetScope.DEFINITION
        return SemanticIntentV2(
            intent_id=request.patch_id.replace("patch:", "intent:", 1),
            project_id=self.project_session.project_id,
            project_generation=self.project_session.generation,
            base_source_digest=self._semantic_intent_source_digest(),
            base_exact_ir_digest=exact_ir_digest(self.architecture),
            framework=self.project_session.framework,
            form_id=self._framework_form_id(),
            operation="set-parameter",
            target_ids=[request.target_node_id],
            payload={
                "parameter_name": request.parameter_name,
                "new_value": request.new_value,
            },
            value_origin=context.value_origin,
            edit_target_scope=scope,
            affected_object_review=AffectedObjectReviewBinding(
                review_id=f"review:{request.patch_id.removeprefix('patch:')}",
                affected_object_ids=context.affected_canonical_ids,
                source_anchor_ids=context.value_origin.source_anchor_ids,
                decision="confirmed",
                reviewed_generation=self.project_session.generation,
            ),
        )

    def _structural_semantic_intent(
        self,
        request: SemanticStructuralPatch,
    ) -> SemanticIntentV2:
        operation = {
            "replace_activation": "replace-operation",
            "insert_layer_norm": "insert-normalization",
            "insert_registered_module": "create-node",
        }[request.operation]
        return SemanticIntentV2(
            intent_id=request.patch_id.replace("patch:", "intent:", 1),
            project_id=self.project_session.project_id,
            project_generation=self.project_session.generation,
            base_source_digest=self._semantic_intent_source_digest(),
            base_exact_ir_digest=exact_ir_digest(self.architecture),
            framework=self.project_session.framework,
            form_id=self._framework_form_id(),
            operation=operation,
            target_ids=[request.target_node_id],
            payload=request.parameters,
            affected_object_review=AffectedObjectReviewBinding(
                review_id=f"review:{request.patch_id.removeprefix('patch:')}",
                affected_object_ids=[request.target_node_id],
                decision="confirmed",
                reviewed_generation=self.project_session.generation,
            ),
        )

    def _expanded_hierarchy_ids(self) -> set[str]:
        state = derive_view_state(self.document)
        projection = str(state.get("navigation_view", "module"))
        expandable = expandable_node_ids(self.hierarchy)
        persisted = set(state.get(f"{projection}_expansion", []))
        reachable = _reachable_expansions(self.navigation, projection, persisted)
        if projection == "module":
            return reachable & expandable
        projections = self.navigation.get("projections", {})
        source = projections.get("source", {}) if isinstance(projections, dict) else {}
        rows = source.get("nodes", []) if isinstance(source, dict) else []
        expanded = reachable
        source_expandable = {
            str(row["id"])
            for row in rows
            if isinstance(row, dict) and int(row.get("child_count", 0)) > 0
        }
        if source_expandable and source_expandable <= expanded:
            return expandable
        visible_depth = max(
            (
                int(row.get("depth", 0))
                for row in rows
                if isinstance(row, dict) and row.get("id") in expanded
            ),
            default=0,
        )
        return {
            node.hierarchy_node_id
            for node in self.hierarchy.nodes
            if node.hierarchy_node_id in expandable and node.depth <= visible_depth
        }

    def recompile_projection(self) -> None:
        view = project_hierarchy(
            self.architecture, self.hierarchy, self._expanded_hierarchy_ids()
        )
        self.views = {view.projection_id: view}

    def write_static(self) -> None:
        _write_static_bundle(self)

    def diagnostics(self) -> list[Diagnostic]:
        return []

    def source_excerpt(
        self,
        path: str,
        start_line: int,
        end_line: int,
        *,
        context: int = 4,
    ) -> dict[str, object]:
        source_file = next((item for item in self.snapshot.source_files if item.path == path), None)
        if source_file is None:
            raise ValueError("source path is not part of the frozen snapshot")
        if start_line < 1 or end_line < start_line:
            raise ValueError("source excerpt line range is invalid")
        if not 0 <= context <= 12:
            raise ValueError("source excerpt context must be between 0 and 12")

        root = Path(self.snapshot.project_root).resolve()
        target = (root / source_file.path).resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise ValueError("source path escapes the frozen project root") from error
        if not target.is_file():
            raise ValueError("source file from the frozen snapshot is unavailable")
        payload = target.read_bytes()
        if hashlib.sha256(payload).hexdigest() != source_file.sha256:
            raise ValueError("source file no longer matches the frozen snapshot")

        lines = payload.decode("utf-8").splitlines()
        excerpt_start = max(1, start_line - context)
        excerpt_end = min(len(lines), min(end_line, start_line + 79) + context)
        highlight_end = min(end_line, start_line + 79, len(lines))
        return {
            "path": source_file.path,
            "sha256": source_file.sha256,
            "revision": self.snapshot.revision,
            "start_line": excerpt_start,
            "end_line": excerpt_end,
            "highlight_start_line": start_line,
            "highlight_end_line": highlight_end,
            "lines": [
                {"number": number, "text": lines[number - 1]}
                for number in range(excerpt_start, excerpt_end + 1)
            ],
        }

    def _source_workspace_target(self, path: str) -> tuple[Path, SourceFile]:
        source_file = next(
            (item for item in self.snapshot.source_files if item.path == path), None
        )
        if source_file is None:
            raise ValueError("source path is not part of the frozen snapshot")
        if Path(path).suffix not in {".py", ".json"}:
            raise ValueError("source workspace only edits snapshot Python and JSON files")
        root = Path(self.snapshot.project_root).resolve()
        unresolved = root / path
        if unresolved.is_symlink():
            raise ValueError("source workspace cannot edit symbolic links")
        target = unresolved.resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError("source workspace path is unavailable")
        if target.stat().st_size > 1_000_000:
            raise ValueError("source workspace file exceeds the 1 MB editing limit")
        return target, source_file

    def _working_source(self, path: str) -> tuple[bytes, str]:
        target, _ = self._source_workspace_target(path)
        content = target.read_bytes()
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("source workspace file is not UTF-8 text") from error
        return content, hashlib.sha256(content).hexdigest()

    def source_workspace_summary(self) -> dict[str, object]:
        buffers = {buffer.path: buffer for buffer in self.source_workspace.buffers}
        files: list[dict[str, object]] = []
        any_stale = False
        any_modified = False
        for source_file in sorted(self.snapshot.source_files, key=lambda item: item.path):
            if Path(source_file.path).suffix not in {".py", ".json"}:
                continue
            buffer = buffers.get(source_file.path)
            try:
                working, working_sha256 = self._working_source(source_file.path)
                readonly_reason = None
                size = len(working)
            except ValueError as error:
                working_sha256 = None
                readonly_reason = str(error)
                size = 0
            staged_sha256 = (
                hashlib.sha256(buffer.staged_content.encode("utf-8")).hexdigest()
                if buffer is not None
                else None
            )
            stale = working_sha256 != source_file.sha256
            modified = buffer is not None and staged_sha256 != buffer.base_sha256
            any_stale = any_stale or stale
            any_modified = any_modified or modified
            files.append(
                {
                    "path": source_file.path,
                    "base_sha256": source_file.sha256,
                    "staged_sha256": staged_sha256,
                    "working_sha256": working_sha256,
                    "state": (
                        "readonly"
                        if readonly_reason
                        else "stale"
                        if stale
                        else "modified"
                        if modified
                        else "clean"
                    ),
                    "opened": buffer is not None,
                    "size": size,
                    "readonly_reason": readonly_reason,
                }
            )
        return {
            "workspace_id": self.source_workspace.workspace_id,
            "revision": self.source_workspace.revision,
            "base_revision": self.source_workspace.base_revision,
            "state": "stale" if any_stale else "modified" if any_modified else "clean",
            "files": files,
        }

    def open_source_buffer(self, path: str) -> dict[str, object]:
        existing = next(
            (buffer for buffer in self.source_workspace.buffers if buffer.path == path), None
        )
        if existing is None:
            working, working_sha256 = self._working_source(path)
            _, source_file = self._source_workspace_target(path)
            if working_sha256 != source_file.sha256:
                raise ValueError("working source changed since the frozen snapshot")
            base_content = working.decode("utf-8")
            existing = StagedSourceBuffer(
                path=path,
                base_sha256=source_file.sha256,
                base_content=base_content,
                staged_content=base_content,
            )
            self.source_workspace = self.source_workspace.model_copy(
                update={
                    "revision": self.source_workspace.revision + 1,
                    "buffers": [*self.source_workspace.buffers, existing],
                }
            )
            _write_json(self.source_workspace_path, self.source_workspace)
        return self.source_buffer(path)

    def source_buffer(self, path: str) -> dict[str, object]:
        buffer = next(
            (item for item in self.source_workspace.buffers if item.path == path), None
        )
        if buffer is None:
            raise ValueError("source buffer is not open")
        working, working_sha256 = self._working_source(path)
        staged_bytes = buffer.staged_content.encode("utf-8")
        staged_sha256 = hashlib.sha256(staged_bytes).hexdigest()
        diff = "".join(
            difflib.unified_diff(
                buffer.base_content.splitlines(keepends=True),
                buffer.staged_content.splitlines(keepends=True),
                fromfile=f"a/{buffer.path}",
                tofile=f"b/{buffer.path}",
            )
        )
        return {
            "path": buffer.path,
            "revision": self.source_workspace.revision,
            "base_sha256": buffer.base_sha256,
            "staged_sha256": staged_sha256,
            "working_sha256": working_sha256,
            "state": (
                "stale"
                if working_sha256 != buffer.base_sha256
                else "modified"
                if staged_sha256 != buffer.base_sha256
                else "clean"
            ),
            "base_content": buffer.base_content,
            "staged_content": buffer.staged_content,
            "working_content": working.decode("utf-8"),
            "diff": diff,
        }

    def save_source_buffer(
        self, path: str, content: str, base_sha256: str, expected_revision: int
    ) -> dict[str, object]:
        if expected_revision != self.source_workspace.revision:
            raise ValueError("source workspace revision is stale")
        if self.active_transaction is not None and self.active_transaction.state not in {
            TransactionState.COMMITTED,
            TransactionState.DISCARDED,
            TransactionState.FAILED,
        }:
            raise ValueError("source buffers are locked while a transaction is active")
        if "\x00" in content or len(content.encode("utf-8")) > 1_000_000:
            raise ValueError("staged source buffer is not valid bounded UTF-8 text")
        buffer = next(
            (item for item in self.source_workspace.buffers if item.path == path), None
        )
        if buffer is None:
            raise ValueError("source buffer is not open")
        if buffer.base_sha256 != base_sha256:
            raise ValueError("source buffer base binding is stale")
        updated = buffer.model_copy(update={"staged_content": content})
        self.source_workspace = self.source_workspace.model_copy(
            update={
                "revision": self.source_workspace.revision + 1,
                "buffers": [
                    updated if item.path == path else item
                    for item in self.source_workspace.buffers
                ],
            }
        )
        _write_json(self.source_workspace_path, self.source_workspace)
        return self.source_buffer(path)

    def discard_source_buffer(self, path: str, expected_revision: int) -> None:
        if expected_revision != self.source_workspace.revision:
            raise ValueError("source workspace revision is stale")
        if not any(item.path == path for item in self.source_workspace.buffers):
            raise ValueError("source buffer is not open")
        self.source_workspace = self.source_workspace.model_copy(
            update={
                "revision": self.source_workspace.revision + 1,
                "buffers": [
                    item for item in self.source_workspace.buffers if item.path != path
                ],
            }
        )
        _write_json(self.source_workspace_path, self.source_workspace)

    def prepare_source_workspace(self) -> None:
        modified = [
            buffer
            for buffer in self.source_workspace.buffers
            if hashlib.sha256(buffer.staged_content.encode("utf-8")).hexdigest()
            != buffer.base_sha256
        ]
        if not modified:
            raise ValueError("source workspace has no staged changes")
        request = FreeformSourcePatch(
            patch_id=f"patch:source-workspace.{self.source_workspace.revision}",
            artifact_path=str(self.artifact_path),
            buffers=[
                FreeformSourceBufferPatch(
                    path=buffer.path,
                    base_sha256=buffer.base_sha256,
                    content=buffer.staged_content,
                )
                for buffer in modified
            ],
        )
        transaction, _ = prepare_freeform_transaction(request, self.workspace)
        transaction = self._verify_transaction_if_prepared(transaction)
        self.active_transaction = transaction
        self.active_proposal = None
        self._record_transaction_conformance(transaction)

    def discard_source_workspace(self) -> None:
        if self.active_transaction is not None and self.active_transaction.state not in {
            TransactionState.COMMITTED,
            TransactionState.DISCARDED,
            TransactionState.FAILED,
        }:
            transaction, _ = discard_transaction(
                self.workspace / "transactions" / self.active_transaction.transaction_id
            )
            self.active_transaction = transaction
        self.source_workspace = self.source_workspace.model_copy(
            update={"revision": self.source_workspace.revision + 1, "buffers": []}
        )
        _write_json(self.source_workspace_path, self.source_workspace)

    def state(self) -> dict[str, object]:
        view_state = self._kernel_view_state()
        navigation = dict(self.navigation)
        navigation["active_projection"] = view_state.get("navigation_view", "module")
        return {
            "schema_version": "1.0",
            "project": self.project_session.model_dump(mode="json"),
            "discovery": self.project_discovery,
            "architecture": self.architecture.model_dump(mode="json"),
            "parameter_edit_contexts": [
                context.model_dump(mode="json")
                for context in self.parameter_edit_contexts
            ],
            "snapshot": self.snapshot.model_dump(mode="json"),
            "analysis_environment": (
                self.analysis_environment.model_dump(mode="json")
                if self.analysis_environment is not None
                else None
            ),
            "analysis_input": (
                self.analysis_input.model_dump(mode="json")
                if self.analysis_input is not None
                else None
            ),
            "evidence": [record.model_dump(mode="json") for record in self.evidence],
            "runtime": (
                {
                    "trace": self.runtime_trace.model_dump(mode="json"),
                    "node_evidence": self.runtime_node_evidence,
                }
                if self.runtime_trace is not None
                else None
            ),
            "semantic_overlay": (
                self.semantic_overlay.model_dump(mode="json")
                if self.semantic_overlay is not None
                else None
            ),
            "hierarchy": self.hierarchy.model_dump(mode="json"),
            "active_projection_id": next(iter(self.views)),
            "views": {
                projection_id: view.model_dump(mode="json")
                for projection_id, view in self.views.items()
            },
            "document": self.document.model_dump(mode="json"),
            "integrity": {
                "source_digest": self.document.source_digest,
                "exact_ir_digest": exact_ir_digest(self.architecture),
            },
            "semantic_intent_binding": {
                "base_source_digest": self._semantic_intent_source_digest(),
                "base_exact_ir_digest": exact_ir_digest(self.architecture),
            },
            "draft": self.draft.model_dump(mode="json"),
            "edit_session": (
                self.topology_session.model_copy(
                    update={"current_document_digest": draft_document_digest(self.draft)}
                ).model_dump(mode="json")
                if self.topology_session is not None
                else self.contract_maintenance.session.model_dump(mode="json")
                if (
                    self.contract_maintenance is not None
                    and self.contract_maintenance.session is not None
                )
                else {
                    "mode": "visual",
                    "document_id": self.draft.draft_id,
                    "current_document_digest": draft_document_digest(self.draft),
                }
            ),
            "topology_review_receipt": (
                self.topology_review_receipt.model_dump(mode="json")
                if self.topology_review_receipt is not None
                else None
            ),
            "contract_maintenance": (
                self.contract_maintenance.state()
                if self.contract_maintenance is not None
                else None
            ),
            "generated_projects": (
                self.generated_projects.state()
                if self.generated_projects is not None
                else None
            ),
            "round_trip_reports": [
                report.model_dump(mode="json")
                for report in self._all_round_trip_reports()[-50:]
            ],
            "recovery_receipts": [
                receipt.model_dump(mode="json")
                for receipt in (self.recovery_receipts or [])[-50:]
            ],
            "protocol_migration_receipts": [
                receipt.model_dump(mode="json")
                for receipt in (self.protocol_migration_receipts or [])[-50:]
            ],
            "source_workspace": self.source_workspace_summary(),
            "view_state": view_state,
            "navigation": navigation,
            "diagnostics": [item.model_dump(mode="json") for item in self.diagnostics()],
            "search_subject_count": len(self.search_index),
            "validation_runs": [
                run.model_dump(mode="json") for run in self.validation_runs[-20:]
            ],
            "transaction": (
                self.active_transaction.model_dump(mode="json")
                if self.active_transaction is not None
                else None
            ),
            "proposal": (
                self.active_proposal.model_dump(mode="json")
                if self.active_proposal is not None
                else None
            ),
            "capabilities": {
                "visual_editing": True,
                "source_editing": True,
                "semantic_transforms": [
                    "set_parameter",
                    "replace_activation",
                    "insert_layer_norm",
                ],
                "proposed_connection": True,
                "runtime_evidence": self.runtime_trace is not None,
                "project_analysis": True,
                "patch_batches": True,
                "search_index": True,
                "draft_node_authoring": {
                    "status": "available",
                    "writeback": "proposal-unless-adapter-lowering-is-proven",
                },
                "contract_maintenance": {
                    "status": "available",
                    "writeback": "candidate-validate-review-publish",
                    "separate_from_topology": True,
                },
                "arbitrary_draft_node_lowering": {
                    "status": "unavailable",
                    "reason": "Unknown node types require a framework adapter lowering and proof.",
                },
                "generated_project": {
                    "status": "available",
                    "framework": "pytorch",
                    "generator_version": "pytorch-sequential-v1",
                    "supported_slice": [
                        "archcanvas.input.tensor",
                        "pytorch.nn.conv2d",
                        "pytorch.nn.relu",
                    ],
                },
                "framework_forms": [
                    capability.model_dump(mode="json")
                    for capability in adapter_capabilities()
                ],
                "staged_multi_file_source_editor": {
                    "status": "available",
                    "scope": "frozen-snapshot-python-and-json",
                    "writeback": "validate-review-explicit-commit",
                },
                "navigation_projections": list(PROJECTIONS),
                "validation_profiles": [
                    "fast-static",
                    "publication",
                    "full",
                    "runtime-replay",
                ],
            },
        }

    def _kernel_view_state(self) -> dict[str, object]:
        return derive_view_state(self.document)

    def kernel_visual_targets(self) -> dict[str, set[str]]:
        """Return stable targets owned by the formal visual kernel."""
        hierarchy_nodes = {node.hierarchy_node_id: node for node in self.hierarchy.nodes}
        node_ids = {f"view:{node_id}" for node_id in hierarchy_nodes}
        expansions = set(expandable_node_ids(self.hierarchy))
        detail_prefixes: set[str] = set()
        if self.semantic_overlay is not None:
            canonical_to_hierarchy = {
                canonical_id: node.hierarchy_node_id
                for node in self.hierarchy.nodes
                for canonical_id in node.canonical_node_ids
            }
            for binding in self.semantic_overlay.template_bindings:
                detail_prefixes.add(binding.binding_id)
                expansions.update(
                    canonical_to_hierarchy[canonical_id]
                    for canonical_id in binding.root_canonical_node_ids
                    if canonical_id in canonical_to_hierarchy
                )
        return {
            "nodes": node_ids,
            "detail_nodes": node_ids,
            "detail_prefixes": detail_prefixes,
            "expansions": expansions,
        }

    def set_navigation_view(
        self,
        projection: str,
        expanded_ids: list[str] | None = None,
        expansions: dict[str, list[str]] | None = None,
    ) -> None:
        if projection not in PROJECTIONS:
            raise ValueError(f"unknown navigation projection: {projection}")
        state = dict(self.document.view_state)
        state["navigation_view"] = projection
        state.pop("active_level", None)

        def validate_expansion(kind: str, values: list[str]) -> list[str]:
            projections = self.navigation.get("projections")
            if not isinstance(projections, dict):
                raise TypeError("navigation projections are unavailable")
            projection_data = projections.get(kind)
            if not isinstance(projection_data, dict):
                raise TypeError("navigation projection is unavailable")
            rows = projection_data.get("nodes")
            if not isinstance(rows, list):
                raise TypeError("navigation rows are unavailable")
            known_ids = {
                str(row["id"])
                for row in rows
                if isinstance(row, dict) and "id" in row
            }
            if any(item not in known_ids for item in values):
                raise ValueError("navigation expansion references an unknown row")
            return sorted(set(values))

        if expansions is not None:
            if set(expansions) != set(PROJECTIONS):
                raise ValueError("navigation expansions must include every projection")
            for kind in PROJECTIONS:
                state[f"{kind}_expansion"] = validate_expansion(kind, expansions[kind])
        elif expanded_ids is not None:
            state[f"{projection}_expansion"] = validate_expansion(
                projection, expanded_ids
            )
        self.save_document(self.document.model_copy(update={"view_state": state}))

    def search(self, query: str, limit: int = 50) -> list[dict[str, object]]:
        from .operations import search_subjects

        return [
            subject.model_dump(mode="json")
            for subject in search_subjects(self.search_index, query, limit)
        ]

    def validate(
        self, profile: str, *, runtime_execution_authorized: bool = False
    ) -> ValidationRun:
        self.validation_generation += 1
        validation = run_validation(
            self,
            profile,
            self.validation_generation,
            runtime_execution_authorized=runtime_execution_authorized,
        )
        self.validation_runs.append(validation)
        _write_json(
            self.workspace / "validations" / f"{validation.validation_id.removeprefix('validation:')}.json",
            validation,
        )
        return validation

    def begin_topology_draft(
        self, base_document_digest: str, subject: str
    ) -> TopologyEditSession:
        current_digest = draft_document_digest(self.draft)
        if base_document_digest != current_digest:
            raise ValueError("topology draft base document digest is stale")
        if (
            self.contract_maintenance is not None
            and self.contract_maintenance.session is not None
        ):
            raise ValueError("contract-maintenance mode must be closed before topology editing")
        if self.topology_session is not None:
            if self.topology_session.capability.subject != subject:
                raise ValueError("topology draft is owned by another session")
            return self.topology_session.model_copy(
                update={"current_document_digest": current_digest}
            )
        now = datetime.now(UTC)
        capability = TopologyDraftCapability(
            capability_id=f"capability:topology.{secrets.token_hex(12)}",
            subject=subject,
            draft_id=self.draft.draft_id,
            base_document_digest=current_digest,
            allowed_commands=[
                "CreateNode",
                "DeleteNode",
                "ConnectPorts",
                "DisconnectEdge",
                "SetInstanceParameter",
                "DeleteCanonicalNode",
                "DiscardIntent",
                "SubmitDraft",
            ],
            issued_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=30)).isoformat(),
        )
        self.topology_base_draft = self.draft
        self.topology_review_receipt = None
        self.topology_session = TopologyEditSession(
            capability=capability,
            current_document_digest=current_digest,
        )
        return self.topology_session

    def begin_contract_maintenance(
        self, definition_id: str, version: str, digest: str, subject: str
    ) -> None:
        if self.topology_session is not None:
            raise ValueError("topology draft mode must be closed before contract maintenance")
        if self.active_transaction is not None and self.active_transaction.state not in {
            TransactionState.COMMITTED,
            TransactionState.DISCARDED,
            TransactionState.FAILED,
        }:
            raise ValueError("source transaction must finish before contract maintenance")
        assert self.contract_maintenance is not None
        self.contract_maintenance.begin(definition_id, version, digest, subject)

    def _authorize_topology_command(
        self, command: str, payload: dict[str, object], subject: str
    ) -> None:
        session = self.topology_session
        if session is None:
            raise ValueError("topology draft mode is required")
        capability = session.capability
        if capability.subject != subject:
            raise ValueError("topology capability belongs to another session")
        if str(payload.get("capability_id", "")) != capability.capability_id:
            raise ValueError("topology capability is missing or invalid")
        if command not in capability.allowed_commands:
            raise ValueError(f"topology capability denies {command}")
        if datetime.now(UTC) >= datetime.fromisoformat(capability.expires_at):
            raise ValueError("topology capability has expired")
        expected = str(payload.get("expected_document_digest", ""))
        if expected != draft_document_digest(self.draft):
            raise ValueError("topology command targets a stale draft")

    def dispatch_topology_command(
        self, command: str, payload: dict[str, object], subject: str
    ) -> None:
        self._authorize_topology_command(command, payload, subject)
        handlers = {
            "CreateNode": lambda: self.propose_draft_node(payload),
            "DeleteNode": lambda: self.delete_draft_node(str(payload["node_id"])),
            "ConnectPorts": lambda: self.propose_draft_edge(payload),
            "DisconnectEdge": lambda: self.delete_draft_edge(str(payload["edge_id"])),
            "SetInstanceParameter": lambda: self.set_draft_node_parameters(payload),
            "DeleteCanonicalNode": lambda: self.propose_canonical_delete(payload),
            "DiscardIntent": lambda: self.discard_canonical_delete(
                str(payload["intent_id"])
            ),
        }
        handler = handlers.get(command)
        if handler is None:
            raise ValueError(f"unsupported topology command: {command}")
        handler()
        self.topology_review_receipt = None
        assert self.topology_session is not None
        self.topology_session = self.topology_session.model_copy(
            update={"current_document_digest": draft_document_digest(self.draft)}
        )

    def discard_topology_draft(self, capability_id: str, subject: str) -> None:
        session = self.topology_session
        if session is None:
            raise ValueError("topology draft mode is not active")
        if (
            session.capability.subject != subject
            or session.capability.capability_id != capability_id
        ):
            raise ValueError("topology capability is missing or invalid")
        if self.topology_base_draft is None:
            raise ValueError("topology draft has no recoverable base document")
        self.draft = self.topology_base_draft
        _write_json(self.draft_path, self.draft)
        self.topology_session = None
        self.topology_base_draft = None
        self.topology_review_receipt = None
        self.active_proposal = None

    def _topology_blocking_diagnostics(self) -> list[dict[str, object]]:
        diagnostics: list[dict[str, object]] = []
        for node in self.draft.nodes:
            if node.definition_ref is None:
                diagnostics.append(
                    {
                        "code": "DRAFT_DEFINITION_UNREGISTERED",
                        "severity": "blocking",
                        "message": "Draft node has no exact registered definition.",
                        "target_ids": [node.node_id],
                    }
                )
                continue
            definition = MODULE_REGISTRY.resolve_ref(
                node.definition_ref.definition_id,
                node.definition_ref.version,
                node.definition_ref.digest,
            )
            if definition is None:
                diagnostics.append(
                    {
                        "code": "DRAFT_DEFINITION_STALE",
                        "severity": "blocking",
                        "message": "Draft node definition is unavailable or stale.",
                        "target_ids": [node.node_id],
                    }
                )
                continue
            missing = [
                contract.parameter_id
                for contract in definition.parameters
                if contract.required and node.parameters.get(contract.parameter_id) is None
            ]
            if missing:
                diagnostics.append(
                    {
                        "code": "DRAFT_REQUIRED_PARAMETER_MISSING",
                        "severity": "blocking",
                        "message": "Draft node is missing required parameters.",
                        "target_ids": [node.node_id, *missing],
                    }
                )
            for port in node.ports:
                count = sum(
                    edge.source_port_id == port.port_id
                    if port.direction == "output"
                    else edge.target_port_id == port.port_id
                    for edge in self.draft.edges
                )
                if count < port.min_connections:
                    diagnostics.append(
                        {
                            "code": "DRAFT_PORT_CARDINALITY_INCOMPLETE",
                            "severity": "blocking",
                            "message": "Draft port has fewer connections than required.",
                            "target_ids": [node.node_id, port.port_id],
                        }
                    )

        node_ids = {node.node_id for node in self.draft.nodes}
        adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
        indegree = dict.fromkeys(node_ids, 0)
        for edge in self.draft.edges:
            source_id = self._draft_port_owner(edge.source_port_id)[0]
            target_id = self._draft_port_owner(edge.target_port_id)[0]
            if source_id in node_ids and target_id in node_ids and target_id not in adjacency[source_id]:
                adjacency[source_id].add(target_id)
                indegree[target_id] += 1
        pending = sorted(node_id for node_id, count in indegree.items() if count == 0)
        visited: set[str] = set()
        while pending:
            node_id = pending.pop(0)
            visited.add(node_id)
            for target_id in sorted(adjacency[node_id]):
                indegree[target_id] -= 1
                if indegree[target_id] == 0:
                    pending.append(target_id)
            pending.sort()
        cyclic = sorted(node_ids - visited)
        if cyclic:
            diagnostics.append(
                {
                    "code": "DRAFT_CYCLE_UNSUPPORTED",
                    "severity": "blocking",
                    "message": "Draft graph contains a non-control-flow cycle.",
                    "target_ids": cyclic,
                }
            )
        return diagnostics

    def _registered_insertion_patch(
        self, draft: DraftGraphDocument | None = None
    ) -> SemanticStructuralPatch | None:
        candidate = draft or self.draft
        if len(candidate.nodes) != 1 or len(candidate.edges) != 2:
            return None
        node = candidate.nodes[0]
        if node.definition_ref is None:
            return None
        definition = MODULE_REGISTRY.resolve_ref(
            node.definition_ref.definition_id,
            node.definition_ref.version,
            node.definition_ref.digest,
        )
        if definition is None:
            return None
        inputs = [port for port in node.ports if port.direction == "input"]
        outputs = [port for port in node.ports if port.direction == "output"]
        if len(inputs) != 1 or len(outputs) != 1:
            return None
        incoming = [
            edge for edge in candidate.edges if edge.target_port_id == inputs[0].port_id
        ]
        outgoing = [
            edge for edge in candidate.edges if edge.source_port_id == outputs[0].port_id
        ]
        if len(incoming) != 1 or len(outgoing) != 1:
            return None
        source_node_id, _, _, source_is_draft, _ = self._draft_port_owner(
            incoming[0].source_port_id
        )
        target_node_id, _, _, target_is_draft, _ = self._draft_port_owner(
            outgoing[0].target_port_id
        )
        if source_is_draft or target_is_draft:
            return None
        original = next(
            (
                edge
                for edge in self.architecture.edges
                if edge.producer_id == source_node_id
                and edge.producer_port == incoming[0].source_port_id
                and edge.consumer_id == target_node_id
                and edge.consumer_port == outgoing[0].target_port_id
            ),
            None,
        )
        if original is None:
            return None
        return SemanticStructuralPatch(
            patch_id=f"patch:registered-insert.{node.node_id.removeprefix('draft:')}",
            operation="insert_registered_module",
            artifact_path=str(self.artifact_path),
            target_node_id=source_node_id,
            parameters={
                "module_name": node.semantic_name,
                "definition_ref": node.definition_ref.model_dump(mode="json"),
                "constructor_parameters": node.parameters,
                "correlation_id": (
                    f"correlation:{node.node_id.removeprefix('draft:')}"
                ),
            },
        )

    def _prepare_registered_insertion(self) -> SourceTransaction | None:
        request = self._registered_insertion_patch()
        if request is None:
            return None
        transaction, _ = prepare_transaction(request, self.workspace)
        transaction = self._verify_transaction_if_prepared(transaction)
        if transaction.state is not TransactionState.REVIEW_READY:
            message = (
                transaction.diagnostics[-1].message
                if transaction.diagnostics
                else "registered insertion did not reach review-ready"
            )
            raise ValueError(message)
        realized = set(transaction.realized_subject_ids)
        proofs = [
            proof.model_copy(
                update={
                    "status": EditProofState.REVIEW_READY,
                    "writeback_eligibility": "commit",
                    "reason_codes": [],
                    "message": (
                        "Registered module insertion is bound to a verified source "
                        "transaction and canonical reanalysis result."
                    ),
                    "affected_subject_ids": sorted(
                        set(proof.affected_subject_ids) | realized
                    ),
                    "required_facts": [],
                    "supported_fixes": [],
                    "input_fingerprint": studio_fingerprint(self),
                }
            )
            for proof in self.draft.proofs
        ]
        self.draft = self.draft.model_copy(
            update={
                "proofs": proofs,
                "lowering_status": "planned",
                "writeback_summary": WritebackSummary(
                    eligibility="commit",
                    blocking_intent_ids=[],
                ),
            }
        )
        _write_json(self.draft_path, self.draft)
        return transaction

    def submit_topology_draft(
        self, capability_id: str, expected_document_digest: str, subject: str
    ) -> TopologyReviewReceipt:
        self._authorize_topology_command(
            "SubmitDraft",
            {
                "capability_id": capability_id,
                "expected_document_digest": expected_document_digest,
            },
            subject,
        )
        self._validate_draft_document(self.draft)
        structural_diagnostics = self._topology_blocking_diagnostics()
        analysis = analyze_draft_graph(self.draft, MODULE_REGISTRY)
        diagnostics = [
            *structural_diagnostics,
            *[item.model_dump(mode="json") for item in analysis.diagnostics],
        ]
        blocking = [item for item in diagnostics if item.get("severity") == "blocking"]
        if blocking:
            codes = ", ".join(str(item["code"]) for item in blocking)
            raise ValueError(f"topology draft has blocking diagnostics: {codes}")
        prepared_transaction = self._prepare_registered_insertion()
        digest = draft_document_digest(self.draft)
        now = datetime.now(UTC)
        receipt = TopologyReviewReceipt(
            receipt_id=f"receipt:topology.{secrets.token_hex(12)}",
            draft_id=self.draft.draft_id,
            document_digest=digest,
            registry_digest=MODULE_REGISTRY.bundle.bundle_digest,
            submitted_at=now.isoformat(),
            diagnostics=diagnostics,
        )
        self.topology_review_receipt = receipt
        if prepared_transaction is not None:
            self.active_transaction = prepared_transaction
            self.active_proposal = None
        self.topology_session = None
        self.topology_base_draft = None
        return receipt

    def save_draft(self, draft: DraftGraphDocument, expected_revision: int) -> None:
        if expected_revision != self.draft.revision:
            raise ValueError("draft revision is stale")
        if draft.base_architecture_id != self.architecture.architecture_id:
            raise ValueError("draft belongs to another architecture")
        if draft.base_source_digest != self.document.source_digest:
            raise ValueError("draft source binding is stale")
        self._validate_draft_document(draft)
        if draft.revision != expected_revision + 1:
            raise ValueError("draft revision must advance exactly once")
        current_proofs = {proof.intent_id: proof for proof in self.draft.proofs}
        for proof in draft.proofs:
            if (
                proof.status in {EditProofState.PROVEN, EditProofState.REVIEW_READY}
                and current_proofs.get(proof.intent_id) != proof
            ):
                raise ValueError("client-authored drafts cannot grant proven writeback status")
        _write_json(self.draft_path, draft)
        self.draft = draft

    def _validate_draft_document(self, draft: DraftGraphDocument) -> None:
        registered = [node for node in draft.nodes if node.definition_ref is not None]
        if registered and draft.base_registry_digest != MODULE_REGISTRY.bundle.bundle_digest:
            raise ValueError("registered draft nodes require the exact registry binding")
        if not registered and draft.base_registry_digest not in {
            None,
            MODULE_REGISTRY.bundle.bundle_digest,
        }:
            raise ValueError("draft registry binding is stale")

        prior_nodes = {node.node_id: node for node in self.draft.nodes}
        port_ids: set[str] = {
            port.port_id
            for node in self.architecture.nodes
            for port in [*node.input_ports, *node.output_ports]
        }
        node_ids = {node.node_id for node in self.architecture.nodes}
        node_ids.update(node.node_id for node in draft.nodes)
        for node in draft.nodes:
            if node.framework != self.architecture.framework:
                raise ValueError("draft node framework does not match the active architecture")
            if node.definition_ref is None:
                if prior_nodes.get(node.node_id) != node:
                    raise ValueError(
                        "bulk draft updates cannot create or modify unregistered nodes"
                    )
            elif self._materialize_registered_draft_node(node) != node:
                raise ValueError(
                    "registered draft node does not match its materialized definition"
                )
            if node.parent_id is not None:
                if node.parent_id == node.node_id:
                    raise ValueError("draft node cannot parent itself")
                if node.parent_id not in node_ids:
                    raise ValueError("draft node parent does not exist")
            for port in node.ports:
                if port.port_id in port_ids:
                    raise ValueError("draft port identifiers must be globally unique")
                port_ids.add(port.port_id)

        parents = {
            node.node_id: node.parent_id
            for node in draft.nodes
            if node.parent_id is not None and node.parent_id.startswith("draft:")
        }
        for node_id in parents:
            seen: set[str] = set()
            cursor: str | None = node_id
            while cursor is not None and cursor in parents:
                if cursor in seen:
                    raise ValueError("draft node parent hierarchy contains a cycle")
                seen.add(cursor)
                cursor = parents.get(cursor)

        checked_edges: list[DraftEdge] = []
        for edge in draft.edges:
            self._validate_draft_edge(edge, checked_edges, draft)
            checked_edges.append(edge)

        ordered_groups: dict[str, list[int]] = {}
        for edge in draft.edges:
            _, _, _, _, contract = self._draft_port_owner(
                edge.target_port_id, draft=draft
            )
            if (
                contract is not None
                and contract.definition_port_id is not None
                and contract.ordering == "ordered"
                and contract.max_connections != 1
            ):
                assert edge.target_ordinal is not None
                ordered_groups.setdefault(edge.target_port_id, []).append(
                    edge.target_ordinal
                )
        for port_id, ordinals in ordered_groups.items():
            if sorted(ordinals) != list(range(len(ordinals))):
                raise ValueError(
                    f"ordered draft port {port_id} requires contiguous target ordinals"
                )

    def _materialize_registered_draft_node(self, node: DraftNode) -> DraftNode:
        if node.definition_ref is None:
            return node
        definition = MODULE_REGISTRY.resolve_ref(
            node.definition_ref.definition_id,
            node.definition_ref.version,
            node.definition_ref.digest,
        )
        if definition is None:
            raise ValueError("draft node references an unknown or stale module definition")
        if node.node_type != definition.definition_id:
            raise ValueError("draft node type must match its exact module definition")

        contracts = {item.parameter_id: item for item in definition.parameters}
        parameters = migrate_parameter_values(
            definition,
            definition.parameter_schema_version,
            node.parameters,
        )
        for parameter_id, value in parameters.items():
            contract = contracts[parameter_id]
            if not _parameter_value_matches(value, contract.value_type):
                raise ValueError(
                    f"draft parameter {parameter_id} does not match {contract.value_type}"
                )

        ports = [
            DraftPort(
                port_id=f"{node.node_id}.{contract.port_id}",
                name=contract.port_id,
                direction=contract.direction,
                role=contract.port_id,
                definition_port_id=contract.port_id,
                required=contract.required,
                min_connections=contract.min_connections,
                max_connections=contract.max_connections,
                ordering=contract.ordering,
                accepted_relations=contract.accepted_relations,
                tensor_ranks=contract.tensor_ranks,
                tensor_layouts=contract.tensor_layouts,
            )
            for contract in definition.ports
        ]
        if node.ports and node.ports != ports:
            raise ValueError("draft node ports do not match its registered module definition")
        return node.model_copy(update={"parameters": parameters, "ports": ports})

    def _draft_node_proof(
        self,
        node: DraftNode,
        intent: EditIntent,
        edges: list[DraftEdge],
    ) -> EditProofStatus:
        reason_codes = ["UNREGISTERED_NODE_LOWERING"]
        missing_ports: list[str] = []
        for port in node.ports:
            connected = sum(
                edge.source_port_id == port.port_id
                if port.direction == "output"
                else edge.target_port_id == port.port_id
                for edge in edges
            )
            if connected < port.min_connections:
                missing_ports.append(
                    f"{port.name} ({connected}/{port.min_connections})"
                )
        required_parameters: set[str] = set()
        if node.definition_ref is not None:
            definition = MODULE_REGISTRY.resolve_ref(
                node.definition_ref.definition_id,
                node.definition_ref.version,
                node.definition_ref.digest,
            )
            if definition is not None:
                required_parameters = {
                    parameter.parameter_id
                    for parameter in definition.parameters
                    if parameter.required
                }
        missing_parameters = sorted(
            parameter_id
            for parameter_id in required_parameters
            if node.parameters.get(parameter_id) is None
        )
        if missing_ports:
            reason_codes.insert(0, "DRAFT_PORT_CARDINALITY_INCOMPLETE")
        if missing_parameters:
            reason_codes.insert(0, "DRAFT_REQUIRED_PARAMETER_MISSING")
        details = []
        if missing_parameters:
            details.append("parameters: " + ", ".join(missing_parameters))
        if missing_ports:
            details.append("ports: " + ", ".join(missing_ports))
        suffix = f" Draft is incomplete ({'; '.join(details)})." if details else ""
        return EditProofStatus(
            intent_id=intent.intent_id,
            status=EditProofState.UNPROVEN,
            writeback_eligibility="blocked",
            reason_codes=reason_codes,
            message=(
                f"No registered {node.framework} lowering proves how to create "
                f"{node.node_type}.{suffix}"
            ),
            affected_subject_ids=[node.node_id, *[port.port_id for port in node.ports]],
            required_facts=[
                "constructor anchor",
                "required parameters",
                "input/output compatibility",
                "required port cardinality",
                "delta oracle",
            ],
            supported_fixes=[
                "Complete required parameters and port connections.",
                "Register and test a framework-specific create-node lowering.",
            ],
            checked_generation=self.project_session.generation,
            input_fingerprint=studio_fingerprint(self),
        )

    def _refresh_registered_node_proofs(
        self, draft: DraftGraphDocument
    ) -> DraftGraphDocument:
        intents = {intent.intent_id: intent for intent in draft.intents}
        nodes = {node.node_id: node for node in draft.nodes}
        proofs: list[EditProofStatus] = []
        for proof in draft.proofs:
            intent = intents.get(proof.intent_id)
            node = (
                nodes.get(intent.target_ids[0])
                if intent is not None
                and intent.kind == "create-node"
                and intent.target_ids
                else None
            )
            if node is not None and node.definition_ref is not None:
                proofs.append(self._draft_node_proof(node, intent, draft.edges))
            else:
                proofs.append(proof)
        refreshed = draft.model_copy(update={"proofs": proofs})
        if self._registered_insertion_patch(refreshed) is None:
            return refreshed
        prepared_proofs = [
            proof.model_copy(
                update={
                    "status": EditProofState.PROVEN,
                    "writeback_eligibility": "prepare",
                    "reason_codes": [],
                    "message": (
                        "The complete registered insertion topology has exact source "
                        "anchors and can enter transaction preparation."
                    ),
                    "required_facts": [],
                    "supported_fixes": [],
                    "input_fingerprint": studio_fingerprint(self),
                }
            )
            for proof in proofs
        ]
        return refreshed.model_copy(
            update={
                "proofs": prepared_proofs,
                "lowering_status": "checking",
                "writeback_summary": WritebackSummary(
                    eligibility="prepare",
                    blocking_intent_ids=[],
                ),
            }
        )

    def propose_draft_node(self, payload: dict[str, object]) -> None:
        node = self._materialize_registered_draft_node(
            DraftNode.model_validate(payload["node"])
        )
        if node.framework != self.architecture.framework:
            raise ValueError("draft node framework does not match the active architecture")
        if any(item.node_id == node.node_id for item in self.draft.nodes):
            raise ValueError("draft node identifier already exists")
        intent_id = str(payload.get("intent_id", node.node_id.replace("draft:", "intent:", 1)))
        intent = EditIntent(
            intent_id=intent_id,
            kind="create-node",
            target_ids=[node.node_id],
            preconditions=["registered framework lowering", "exact source anchor", "bounded Graph Delta"],
            user_input=node.model_dump(mode="json"),
            capability_requirement=f"semantic.create-node.{node.framework}.{node.node_type}",
        )
        proof = self._draft_node_proof(node, intent, self.draft.edges)
        self.active_proposal = AgentProposal(
            proposal_id=f"proposal:{intent_id.removeprefix('intent:')}",
            reason_code="UNSUPPORTED_STRUCTURAL_INTENT",
            summary=proof.message,
            requested_intent=intent.model_dump(mode="json"),
            source_context={
                "architecture_id": self.architecture.architecture_id,
                "source_digest": self.document.source_digest,
                "registry_digest": MODULE_REGISTRY.bundle.bundle_digest,
                "definition_ref": (
                    node.definition_ref.model_dump(mode="json")
                    if node.definition_ref is not None
                    else None
                ),
            },
        )
        draft = self.draft.model_copy(
            update={
                "revision": self.draft.revision + 1,
                "base_registry_digest": MODULE_REGISTRY.bundle.bundle_digest,
                "nodes": [*self.draft.nodes, node],
                "intents": [*self.draft.intents, intent],
                "proofs": [*self.draft.proofs, proof],
                "lowering_status": "blocked",
                "writeback_summary": WritebackSummary(
                    eligibility="blocked",
                    blocking_intent_ids=[
                        *self.draft.writeback_summary.blocking_intent_ids,
                        intent_id,
                    ],
                ),
            }
        )
        draft = self._refresh_registered_node_proofs(draft)
        self.draft = DraftGraphDocument.model_validate(draft.model_dump(mode="json"))
        _write_json(self.draft_path, self.draft)

    def set_draft_node_parameters(self, payload: dict[str, object]) -> None:
        node_id = str(payload["node_id"])
        node = next((item for item in self.draft.nodes if item.node_id == node_id), None)
        if node is None:
            raise ValueError("draft node does not exist")
        if node.definition_ref is None:
            raise ValueError("unregistered draft nodes do not expose schema parameters")
        raw_parameters = payload.get("parameters")
        if not isinstance(raw_parameters, dict):
            raise TypeError("draft node parameters must be an object")
        updated = self._materialize_registered_draft_node(
            node.model_copy(update={"parameters": raw_parameters, "ports": []})
        )
        if updated.parameters == node.parameters:
            raise ValueError("draft node parameters are unchanged")

        intent_id = str(
            payload.get(
                "intent_id",
                f"intent:set-parameters.{node_id.removeprefix('draft:')}.{self.draft.revision + 1}",
            )
        )
        intent = EditIntent(
            intent_id=intent_id,
            kind="set-parameter",
            target_ids=[node_id],
            preconditions=[
                "exact registered definition",
                "parameter schema validation",
                "shape and cost reanalysis",
                "registered source lowering",
            ],
            user_input={
                "node_id": node_id,
                "definition_ref": node.definition_ref.model_dump(mode="json"),
                "before": node.parameters,
                "after": updated.parameters,
            },
            capability_requirement=(
                f"semantic.set-parameter.{node.framework}.{node.node_type}"
            ),
        )
        proof = EditProofStatus(
            intent_id=intent_id,
            status=EditProofState.UNPROVEN,
            writeback_eligibility="blocked",
            reason_codes=["UNSUPPORTED_DRAFT_PARAMETER_LOWERING"],
            message=(
                "Draft parameters passed the registered schema, but no exact source "
                "lowering is bound to this synthetic node."
            ),
            affected_subject_ids=[node_id],
            required_facts=["source constructor anchor", "observed Graph Delta oracle"],
            supported_fixes=[
                "Bind the synthetic node to a reviewed insertion proposal before prepare."
            ],
            checked_generation=self.project_session.generation,
            input_fingerprint=studio_fingerprint(self),
        )
        proposal = AgentProposal(
            proposal_id=f"proposal:{intent_id.removeprefix('intent:')}",
            reason_code="UNSUPPORTED_STRUCTURAL_INTENT",
            summary=proof.message,
            requested_intent=intent.model_dump(mode="json"),
            source_context={
                "architecture_id": self.architecture.architecture_id,
                "source_digest": self.document.source_digest,
                "registry_digest": MODULE_REGISTRY.bundle.bundle_digest,
                "definition_ref": node.definition_ref.model_dump(mode="json"),
            },
        )
        draft = self.draft.model_copy(
            update={
                "revision": self.draft.revision + 1,
                "nodes": [updated if item.node_id == node_id else item for item in self.draft.nodes],
                "intents": [*self.draft.intents, intent],
                "proofs": [*self.draft.proofs, proof],
                "lowering_status": "blocked",
                "writeback_summary": WritebackSummary(
                    eligibility="blocked",
                    blocking_intent_ids=[
                        *self.draft.writeback_summary.blocking_intent_ids,
                        intent_id,
                    ],
                ),
            }
        )
        draft = self._refresh_registered_node_proofs(draft)
        self.draft = DraftGraphDocument.model_validate(draft.model_dump(mode="json"))
        self.active_proposal = (
            None if draft.writeback_summary.eligibility == "prepare" else proposal
        )
        _write_json(self.draft_path, self.draft)

    def delete_draft_node(self, node_id: str) -> None:
        node = next((item for item in self.draft.nodes if item.node_id == node_id), None)
        if node is None:
            raise ValueError("draft node does not exist")
        port_ids = {port.port_id for port in node.ports}
        removed_edges = {
            edge.edge_id
            for edge in self.draft.edges
            if edge.source_port_id in port_ids or edge.target_port_id in port_ids
        }
        removed_subjects = {node_id, *port_ids, *removed_edges}
        removed_intents = {
            intent.intent_id
            for intent in self.draft.intents
            if removed_subjects.intersection(intent.target_ids)
        }
        intents = [
            intent
            for intent in self.draft.intents
            if intent.intent_id not in removed_intents
        ]
        proofs = [
            proof for proof in self.draft.proofs if proof.intent_id not in removed_intents
        ]
        blocking = [
            intent_id
            for intent_id in self.draft.writeback_summary.blocking_intent_ids
            if intent_id not in removed_intents
        ]
        draft = self.draft.model_copy(
            update={
                "revision": self.draft.revision + 1,
                "nodes": [item for item in self.draft.nodes if item.node_id != node_id],
                "edges": [
                    edge for edge in self.draft.edges if edge.edge_id not in removed_edges
                ],
                "intents": intents,
                "proofs": proofs,
                "lowering_status": "blocked" if proofs else "not-planned",
                "writeback_summary": WritebackSummary(
                    eligibility="blocked",
                    blocking_intent_ids=blocking,
                ),
            }
        )
        draft = self._refresh_registered_node_proofs(draft)
        self.draft = DraftGraphDocument.model_validate(draft.model_dump(mode="json"))
        self.active_proposal = None
        _write_json(self.draft_path, self.draft)

    def _draft_port_owner(
        self, port_id: str, *, draft: DraftGraphDocument | None = None
    ) -> tuple[str, str, str, bool, DraftPort | None]:
        matches: list[tuple[str, str, str, bool, DraftPort | None]] = []
        for node in self.architecture.nodes:
            matches.extend(
                (node.node_id, port.direction, port.role, False, None)
                for port in [*node.input_ports, *node.output_ports]
                if port.port_id == port_id
            )
        for node in (draft or self.draft).nodes:
            matches.extend(
                (node.node_id, port.direction, port.role, True, port)
                for port in node.ports
                if port.port_id == port_id
            )
        if not matches:
            raise ValueError(f"draft edge references an unknown port: {port_id}")
        if len(matches) > 1:
            raise ValueError(f"draft edge references an ambiguous port: {port_id}")
        return matches[0]

    def _validate_draft_edge(
        self,
        edge: DraftEdge,
        existing_edges: list[DraftEdge],
        draft: DraftGraphDocument,
    ) -> None:
        if edge.policy == "disconnect":
            raise ValueError("disconnect must remove an existing draft edge")
        if any(item.edge_id == edge.edge_id for item in existing_edges):
            raise ValueError("draft edge identifier already exists")
        if any(
            item.source_port_id == edge.source_port_id
            and item.target_port_id == edge.target_port_id
            and item.target_ordinal == edge.target_ordinal
            for item in existing_edges
        ):
            raise ValueError("draft edge endpoints are already connected")
        (
            source_node_id,
            source_direction,
            _,
            _,
            source_contract,
        ) = self._draft_port_owner(edge.source_port_id, draft=draft)
        (
            target_node_id,
            target_direction,
            _,
            _,
            target_contract,
        ) = self._draft_port_owner(edge.target_port_id, draft=draft)
        if source_direction != "output":
            raise ValueError("draft edge source must reference an output port")
        if target_direction != "input":
            raise ValueError("draft edge target must reference an input port")
        if source_node_id == target_node_id:
            raise ValueError("draft edge cannot connect a node to itself")
        expected_relation = {
            "add-residual": "residual",
            "concat": "concat",
        }.get(edge.policy, "main")
        if edge.relation != expected_relation:
            raise ValueError("draft edge relation does not match its connection policy")
        for contract in (source_contract, target_contract):
            if contract is None:
                continue
            if edge.relation not in contract.accepted_relations:
                raise ValueError(
                    f"draft port {contract.port_id} rejects relation {edge.relation}"
                )
            connected = sum(
                item.source_port_id == contract.port_id
                if contract.direction == "output"
                else item.target_port_id == contract.port_id
                for item in existing_edges
            )
            if (
                isinstance(contract.max_connections, int)
                and connected + 1 > contract.max_connections
            ):
                raise ValueError(
                    f"draft port {contract.port_id} exceeds its connection cardinality"
                )
        if target_contract is not None:
            is_ordered_variadic = (
                target_contract.definition_port_id is not None
                and
                target_contract.ordering == "ordered"
                and target_contract.max_connections != 1
            )
            if is_ordered_variadic and edge.target_ordinal is None:
                raise ValueError("ordered variadic draft ports require a target ordinal")
            if target_contract.ordering == "unordered" and edge.target_ordinal is not None:
                raise ValueError("unordered draft ports reject target ordinals")
            if edge.target_ordinal is not None and any(
                item.target_port_id == edge.target_port_id
                and item.target_ordinal == edge.target_ordinal
                for item in existing_edges
            ):
                raise ValueError("draft target ordinal is already connected")

    def propose_draft_edge(self, payload: dict[str, object]) -> None:
        edge = DraftEdge.model_validate(payload["edge"])
        self._validate_draft_edge(edge, self.draft.edges, self.draft)
        (
            source_node_id,
            _,
            source_role,
            source_is_draft,
            _,
        ) = self._draft_port_owner(edge.source_port_id)
        (
            target_node_id,
            _,
            _,
            target_is_draft,
            _,
        ) = self._draft_port_owner(edge.target_port_id)
        intent_id = str(payload.get("intent_id", edge.edge_id.replace("draft:", "intent:", 1)))
        intent = EditIntent(
            intent_id=intent_id,
            kind="connect-ports",
            target_ids=[
                edge.edge_id,
                source_node_id,
                edge.source_port_id,
                target_node_id,
                edge.target_port_id,
            ],
            preconditions=[
                "authored output port",
                "authored input port",
                "proven tensor compatibility",
                "registered connection lowering",
            ],
            user_input={
                **edge.model_dump(mode="json"),
                "source_node_id": source_node_id,
                "target_node_id": target_node_id,
            },
            capability_requirement=f"semantic.connect-ports.{edge.policy}",
        )
        if source_is_draft or target_is_draft:
            reason_code = "UNSUPPORTED_STRUCTURAL_INTENT"
            summary = (
                "The draft connection is recorded for review, but an endpoint has no "
                "canonical source lowering."
            )
            proof_state = EditProofState.UNPROVEN
            source_context = {
                "architecture_id": self.architecture.architecture_id,
                "source_node_id": source_node_id,
                "source_port_id": edge.source_port_id,
                "target_node_id": target_node_id,
                "target_port_id": edge.target_port_id,
                "compatibility": "unresolved",
                "registry_match": None,
            }
            proposal = AgentProposal(
                proposal_id=f"proposal:{edge.edge_id.removeprefix('draft:')}",
                reason_code=reason_code,
                summary=summary,
                requested_intent=intent.model_dump(mode="json"),
                source_context=source_context,
            )
        else:
            request = ProposedConnection(
                proposal_id=f"proposal:{edge.edge_id.removeprefix('draft:')}",
                artifact_path=str(self.artifact_path),
                source_node_id=source_node_id,
                source_port_id=edge.source_port_id,
                target_node_id=target_node_id,
                target_port_id=edge.target_port_id,
                role=edge.relation if edge.relation else source_role,
            )
            proposal = plan_connection(request, self.architecture)
            reason_code = proposal.reason_code
            summary = proposal.summary
            proof_state = (
                EditProofState.INVALID
                if reason_code == "INCOMPATIBLE_PORTS"
                else EditProofState.UNPROVEN
            )

        proof = EditProofStatus(
            intent_id=intent_id,
            status=proof_state,
            writeback_eligibility="blocked",
            reason_codes=[reason_code],
            message=summary,
            affected_subject_ids=intent.target_ids,
            required_facts=["tensor shape compatibility", "exact source anchors"],
            supported_fixes=["Register and test a framework-specific connection lowering."],
            checked_generation=self.project_session.generation,
            input_fingerprint=studio_fingerprint(self),
        )
        draft = self.draft.model_copy(
            update={
                "revision": self.draft.revision + 1,
                "edges": [*self.draft.edges, edge],
                "intents": [*self.draft.intents, intent],
                "proofs": [*self.draft.proofs, proof],
                "lowering_status": "blocked",
                "writeback_summary": WritebackSummary(
                    eligibility="blocked",
                    blocking_intent_ids=[
                        *self.draft.writeback_summary.blocking_intent_ids,
                        intent_id,
                    ],
                ),
            }
        )
        draft = self._refresh_registered_node_proofs(draft)
        self.draft = DraftGraphDocument.model_validate(draft.model_dump(mode="json"))
        self.active_proposal = (
            None if draft.writeback_summary.eligibility == "prepare" else proposal
        )
        _write_json(self.draft_path, self.draft)

    def delete_draft_edge(self, edge_id: str) -> None:
        edge = next((item for item in self.draft.edges if item.edge_id == edge_id), None)
        if edge is None:
            raise ValueError("draft edge does not exist")
        removed_intents = {
            intent.intent_id
            for intent in self.draft.intents
            if edge_id in intent.target_ids
        }
        intents = [
            intent for intent in self.draft.intents if intent.intent_id not in removed_intents
        ]
        proofs = [
            proof for proof in self.draft.proofs if proof.intent_id not in removed_intents
        ]
        blocking = [
            intent_id
            for intent_id in self.draft.writeback_summary.blocking_intent_ids
            if intent_id not in removed_intents
        ]
        draft = self.draft.model_copy(
            update={
                "revision": self.draft.revision + 1,
                "edges": [item for item in self.draft.edges if item.edge_id != edge_id],
                "intents": intents,
                "proofs": proofs,
                "lowering_status": "blocked" if proofs else "not-planned",
                "writeback_summary": WritebackSummary(
                    eligibility="blocked",
                    blocking_intent_ids=blocking,
                ),
            }
        )
        draft = self._refresh_registered_node_proofs(draft)
        self.draft = DraftGraphDocument.model_validate(draft.model_dump(mode="json"))
        self.active_proposal = None
        _write_json(self.draft_path, self.draft)

    def canonical_delete_impact(self, node_id: str) -> dict[str, object]:
        node = next((item for item in self.architecture.nodes if item.node_id == node_id), None)
        if node is None:
            raise ValueError("canonical delete references an unknown node")
        incoming_edges = [
            edge for edge in self.architecture.edges if edge.consumer_id == node_id
        ]
        outgoing_edges = [
            edge for edge in self.architecture.edges if edge.producer_id == node_id
        ]
        affected_edges = sorted(
            {edge.edge_id for edge in [*incoming_edges, *outgoing_edges]}
        )
        produced_tensors = sorted(
            tensor.tensor_id
            for tensor in self.architecture.tensors
            if tensor.producer_id == node_id
        )
        affected_fanouts = sorted(
            relation.relation_id
            for relation in self.architecture.fanouts
            if relation.producer_id == node_id
            or node_id in relation.consumer_ids
        )
        parameter_identity = node.parameter_identity.lower()
        explicitly_shared = any(
            marker in parameter_identity for marker in ("shared", "tied", "reused")
        )
        shared_parameter_nodes = sorted(
            item.node_id
            for item in self.architecture.nodes
            if explicitly_shared
            and item.node_id != node_id
            and item.parameter_identity == node.parameter_identity
        )
        child_ids = sorted(node.children)
        downstream_nodes = sorted({edge.consumer_id for edge in outgoing_edges})
        source_evidence_ids = sorted(
            evidence_id
            for evidence_id in node.evidence_ids
            if any(
                record.evidence_id == evidence_id and record.kind.value == "source"
                for record in self.evidence
            )
        )
        runtime_evidence_ids = sorted(self.runtime_node_evidence.get(node_id, []))
        unresolved: list[str] = []
        if incoming_edges and outgoing_edges:
            unresolved.append("deletion requires an explicit bypass or replacement connection")
        if child_ids:
            unresolved.append("child nodes require an explicit reparent or cascade decision")
        if shared_parameter_nodes:
            unresolved.append("shared parameter ownership must be preserved")
        if affected_fanouts:
            unresolved.append("fanout consumers require an explicit routing decision")
        if node.repeat_id:
            unresolved.append("repeat membership requires an explicit structural update")
        if node.execution_predicate != "always":
            unresolved.append("conditional execution semantics require proof")
        expected_delta = GraphDelta(
            removed_nodes=[node_id],
            removed_edges=affected_edges,
            removed_tensors=produced_tensors,
            removed_fanouts=affected_fanouts,
            unresolved_changes=unresolved,
        )
        return {
            "node_id": node.node_id,
            "semantic_name": node.semantic_name,
            "input_fingerprint": studio_fingerprint(self),
            "incoming_edge_ids": sorted(edge.edge_id for edge in incoming_edges),
            "outgoing_edge_ids": sorted(edge.edge_id for edge in outgoing_edges),
            "produced_tensor_ids": produced_tensors,
            "downstream_node_ids": downstream_nodes,
            "fanout_ids": affected_fanouts,
            "shared_parameter_node_ids": shared_parameter_nodes,
            "child_node_ids": child_ids,
            "repeat_id": node.repeat_id,
            "execution_predicate": node.execution_predicate,
            "source_evidence_ids": source_evidence_ids,
            "runtime_evidence_ids": runtime_evidence_ids,
            "expected_delta": expected_delta.model_dump(mode="json"),
            "required_action": (
                "Choose an explicit bypass or replacement before lowering."
                if incoming_edges and outgoing_edges
                else "Confirm the adapter-specific removal plan before lowering."
            ),
            "blocking_reasons": unresolved,
        }

    def propose_canonical_delete(self, payload: dict[str, object]) -> None:
        node_id = str(payload["node_id"])
        impact = self.canonical_delete_impact(node_id)
        if payload.get("input_fingerprint") != impact["input_fingerprint"]:
            raise ValueError("canonical delete impact preview is stale")
        if any(
            intent.kind == "delete-node" and node_id in intent.target_ids
            for intent in self.draft.intents
        ):
            raise ValueError("canonical node already has a delete intent")
        intent_id = str(payload.get("intent_id", f"intent:delete.{node_id.removeprefix('node:')}"))
        expected_delta = GraphDelta.model_validate(impact["expected_delta"])
        affected_ids = [
            node_id,
            *expected_delta.removed_edges,
            *expected_delta.removed_tensors,
            *expected_delta.removed_fanouts,
        ]
        intent = EditIntent(
            intent_id=intent_id,
            kind="delete-node",
            target_ids=affected_ids,
            preconditions=[
                "impact preview accepted",
                "no unresolved consumers",
                "explicit bypass or replacement",
                "registered adapter lowering",
            ],
            expected_delta=expected_delta,
            user_input={"node_id": node_id, "impact": impact},
            capability_requirement=(
                f"semantic.delete-node.{self.architecture.framework}.{node_id}"
            ),
        )
        summary = (
            f"Deleting {impact['semantic_name']} would remove "
            f"{len(expected_delta.removed_edges)} edge(s) and "
            f"{len(expected_delta.removed_tensors)} produced tensor(s). "
            "No registered adapter lowering proves this deletion safe."
        )
        proof = EditProofStatus(
            intent_id=intent_id,
            status=EditProofState.UNPROVEN,
            writeback_eligibility="blocked",
            reason_codes=["UNSUPPORTED_STRUCTURAL_INTENT"],
            message=summary,
            affected_subject_ids=affected_ids,
            required_facts=[
                "consumer preservation",
                "parameter ownership",
                "source deletion anchor",
                "observed Graph Delta oracle",
            ],
            supported_fixes=[
                "Choose an explicit bypass or replacement connection.",
                "Register and test an adapter-specific delete-node lowering.",
            ],
            checked_generation=self.project_session.generation,
            input_fingerprint=studio_fingerprint(self),
        )
        proposal = AgentProposal(
            proposal_id=f"proposal:{intent_id.removeprefix('intent:')}",
            reason_code="UNSUPPORTED_STRUCTURAL_INTENT",
            summary=summary,
            requested_intent=intent.model_dump(mode="json"),
            source_context={
                "architecture_id": self.architecture.architecture_id,
                "source_digest": self.document.source_digest,
                "impact": impact,
            },
        )
        draft = self.draft.model_copy(
            update={
                "revision": self.draft.revision + 1,
                "intents": [*self.draft.intents, intent],
                "proofs": [*self.draft.proofs, proof],
                "lowering_status": "blocked",
                "writeback_summary": WritebackSummary(
                    eligibility="blocked",
                    blocking_intent_ids=[
                        *self.draft.writeback_summary.blocking_intent_ids,
                        intent_id,
                    ],
                ),
            }
        )
        self.draft = DraftGraphDocument.model_validate(draft.model_dump(mode="json"))
        self.active_proposal = proposal
        _write_json(self.draft_path, self.draft)

    def discard_canonical_delete(self, intent_id: str) -> None:
        intent = next(
            (item for item in self.draft.intents if item.intent_id == intent_id), None
        )
        if intent is None or intent.kind != "delete-node":
            raise ValueError("canonical delete intent does not exist")
        intents = [item for item in self.draft.intents if item.intent_id != intent_id]
        proofs = [item for item in self.draft.proofs if item.intent_id != intent_id]
        blocking = [
            item
            for item in self.draft.writeback_summary.blocking_intent_ids
            if item != intent_id
        ]
        draft = self.draft.model_copy(
            update={
                "revision": self.draft.revision + 1,
                "intents": intents,
                "proofs": proofs,
                "lowering_status": "blocked" if proofs else "not-planned",
                "writeback_summary": WritebackSummary(
                    eligibility="blocked",
                    blocking_intent_ids=blocking,
                ),
            }
        )
        self.draft = DraftGraphDocument.model_validate(draft.model_dump(mode="json"))
        self.active_proposal = None
        _write_json(self.draft_path, self.draft)

    def prepare_parameter(self, payload: dict[str, object]) -> None:
        request = SemanticParameterPatch(
            patch_id=str(payload["patch_id"]),
            artifact_path=str(self.artifact_path),
            target_node_id=str(payload["target_node_id"]),
            parameter_name=str(payload["parameter_name"]),
            new_value=payload.get("new_value"),
            value_origin_id=(
                str(payload["value_origin_id"])
                if payload.get("value_origin_id") is not None
                else None
            ),
            edit_target_scope=payload.get("edit_target_scope"),
            confirmed_affected_ids=payload.get("confirmed_affected_ids", []),
            confirmed_source_anchor_ids=payload.get(
                "confirmed_source_anchor_ids", []
            ),
            targeted_tests=payload.get("targeted_tests", []),
            runtime_input_spec=payload.get("runtime_input_spec"),
        )
        semantic_intent = (
            SemanticIntentV2.model_validate(payload["semantic_intent"])
            if "semantic_intent" in payload
            else self._parameter_semantic_intent(request)
        )
        if (
            semantic_intent.project_id != self.project_session.project_id
            or semantic_intent.project_generation != self.project_session.generation
        ):
            raise ValueError("semantic intent references a stale project generation")
        transaction, _ = prepare_transaction(
            request,
            self.workspace,
            semantic_intent=semantic_intent,
        )
        transaction = self._verify_transaction_if_prepared(transaction)
        self.active_transaction = transaction
        self._record_transaction_conformance(transaction)

    def prepare_structural(self, payload: dict[str, object]) -> None:
        request = SemanticStructuralPatch(
            patch_id=str(payload["patch_id"]),
            operation=str(payload["operation"]),
            artifact_path=str(self.artifact_path),
            target_node_id=str(payload["target_node_id"]),
            parameters=payload.get("parameters", {}),
            targeted_tests=payload.get("targeted_tests", []),
            runtime_input_spec=payload.get("runtime_input_spec"),
        )
        semantic_intent = (
            SemanticIntentV2.model_validate(payload["semantic_intent"])
            if "semantic_intent" in payload
            else self._structural_semantic_intent(request)
        )
        if (
            semantic_intent.project_id != self.project_session.project_id
            or semantic_intent.project_generation != self.project_session.generation
        ):
            raise ValueError("semantic intent references a stale project generation")
        transaction, _ = prepare_transaction(
            request,
            self.workspace,
            semantic_intent=semantic_intent,
        )
        transaction = self._verify_transaction_if_prepared(transaction)
        self.active_transaction = transaction
        self.active_proposal = None
        self._record_transaction_conformance(transaction)

    def propose_connection(self, payload: dict[str, object]) -> None:
        request = ProposedConnection(
            proposal_id=str(payload["proposal_id"]),
            artifact_path=str(self.artifact_path),
            source_node_id=str(payload["source_node_id"]),
            source_port_id=str(payload["source_port_id"]),
            target_node_id=str(payload["target_node_id"]),
            target_port_id=str(payload["target_port_id"]),
            role=str(payload.get("role", "main")),
        )
        self.active_proposal = plan_connection(request, self.architecture)
        intent_id = request.proposal_id.replace("proposal:", "intent:", 1)
        intent = EditIntent(
            intent_id=intent_id,
            kind="connect-ports",
            target_ids=[
                request.source_node_id,
                request.source_port_id,
                request.target_node_id,
                request.target_port_id,
            ],
            capability_requirement=f"semantic.connect-ports.{request.role}",
            user_input={
                "source_node_id": request.source_node_id,
                "source_port_id": request.source_port_id,
                "target_node_id": request.target_node_id,
                "target_port_id": request.target_port_id,
                "policy": payload.get("policy", "fanout"),
            },
        )
        proof_state = (
            EditProofState.INVALID
            if self.active_proposal.reason_code == "INCOMPATIBLE_PORTS"
            else EditProofState.UNPROVEN
        )
        proof = EditProofStatus(
            intent_id=intent_id,
            status=proof_state,
            writeback_eligibility="blocked",
            reason_codes=[self.active_proposal.reason_code],
            message=self.active_proposal.summary,
            affected_subject_ids=intent.target_ids,
            checked_generation=self.project_session.generation,
            input_fingerprint=studio_fingerprint(self),
        )
        intents = [item for item in self.draft.intents if item.intent_id != intent_id]
        proofs = [item for item in self.draft.proofs if item.intent_id != intent_id]
        draft = self.draft.model_copy(
            update={
                "revision": self.draft.revision + 1,
                "intents": [*intents, intent],
                "proofs": [*proofs, proof],
                "lowering_status": "blocked",
                "writeback_summary": WritebackSummary(
                    eligibility="blocked",
                    blocking_intent_ids=[
                        *[item.intent_id for item in proofs],
                        intent_id,
                    ],
                ),
            }
        )
        draft = DraftGraphDocument.model_validate(draft.model_dump(mode="json"))
        _write_json(self.draft_path, draft)
        self.draft = draft

    def commit_parameter(self) -> None:
        if self.active_transaction is None:
            raise ValueError("there is no active source transaction")
        transaction, _ = commit_transaction(
            self.workspace / "transactions" / self.active_transaction.transaction_id
        )
        self.active_transaction = transaction
        self._record_transaction_conformance(transaction)
        if (
            transaction.state is TransactionState.COMMITTED
            and isinstance(transaction.request, FreeformSourcePatch)
        ):
            self.source_workspace = self.source_workspace.model_copy(
                update={"revision": self.source_workspace.revision + 1, "buffers": []}
            )
            _write_json(self.source_workspace_path, self.source_workspace)

    def discard_parameter(self) -> None:
        if self.active_transaction is None:
            raise ValueError("there is no active source transaction")
        transaction, _ = discard_transaction(
            self.workspace / "transactions" / self.active_transaction.transaction_id
        )
        self.active_transaction = transaction
        if transaction.result_exact_ir_digest is not None:
            self._record_transaction_conformance(transaction)

    def _record_transaction_conformance(self, transaction: SourceTransaction) -> None:
        if transaction.result_exact_ir_digest is None:
            return
        report = build_intent_source_report(transaction)
        reports = [
            item
            for item in (self.round_trip_reports or [])
            if item.report_id != report.report_id
        ]
        self.round_trip_reports = [*reports, report]
        _write_json(_conformance_report_path(self.workspace, report), report)

    def save_document(self, document: CanvasDocument) -> None:
        if document.source_digest != self.document.source_digest:
            raise ValueError("CanvasDocument source digest cannot change")
        if document.architecture_id != self.architecture.architecture_id:
            raise ValueError("CanvasDocument architecture binding cannot change")
        ir_digest = exact_ir_digest(self.architecture)
        previous_expansion = derive_view_state(self.document).get("module_expansion", [])
        persist_canvas_document(self.document_path, document)
        self.document = document
        if exact_ir_digest(self.architecture) != ir_digest:
            raise AssertionError("visual document update changed the Exact IR")
        if derive_view_state(document).get("module_expansion", []) != previous_expansion:
            self.recompile_projection()

    def export_svg(self) -> str:
        """Compile the legacy publication artifact only for an explicit export request."""
        view = next(iter(self.views.values()))
        spec = build_visual_spec(view)
        scene = build_scene(
            view,
            spec,
            str(derive_view_state(self.document).get("layout_mode", "auto")),
        )
        return render_svg(scene)


def _render_index(template: str, state: dict[str, object]) -> str:
    payload = json.dumps(state, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    script = f'<script id="archcanvas-studio-data" type="application/json">{payload}</script>'
    if "<!--ARCHCANVAS_DATA-->" not in template:
        raise ValueError("Studio index is missing its data injection marker")
    return template.replace("<!--ARCHCANVAS_DATA-->", script)


def _write_static_bundle(bundle: StudioBundle) -> None:
    if not (STATIC_ROOT / "index.html").is_file():
        raise ValueError("Studio frontend has not been built")
    bundle.static_dir.mkdir(parents=True, exist_ok=True)
    for source in STATIC_ROOT.iterdir():
        target = bundle.static_dir / source.name
        if source.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
        elif source.name != "index.html":
            shutil.copy2(source, target)
    template = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    (bundle.static_dir / "index.html").write_text(
        _render_index(template, bundle.state()), encoding="utf-8"
    )
    _write_json(bundle.static_dir / "studio-state.json", bundle.state())


def _archive_stale_binding(path: Path) -> Path:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    archive = path.with_name(f"{path.stem}.stale-{digest}{path.suffix}")
    index = 1
    while archive.exists():
        archive = path.with_name(f"{path.stem}.stale-{digest}-{index}{path.suffix}")
        index += 1
    path.rename(archive)
    return archive


def _available_architecture_subject_ids(
    architecture: ArchitectureIR, evidence: list[EvidenceRecord]
) -> set[str]:
    return {
        *[node.node_id for node in architecture.nodes],
        *[
            port.port_id
            for node in architecture.nodes
            for port in [*node.input_ports, *node.output_ports]
        ],
        *[edge.edge_id for edge in architecture.edges],
        *[tensor.tensor_id for tensor in architecture.tensors],
        *[record.evidence_id for record in evidence],
    }


def _committed_reconciliation_transactions(workspace: Path) -> list[SourceTransaction]:
    transactions: list[SourceTransaction] = []
    transaction_root = workspace / "transactions"
    if not transaction_root.is_dir():
        return transactions
    for manifest in sorted(transaction_root.glob("*/transaction.json")):
        try:
            transaction = load_transaction(manifest)
        except (OSError, ValueError):
            continue
        if (
            transaction.state is TransactionState.COMMITTED
            and transaction.proposal_correlation_id is not None
            and transaction.realized_subject_ids
        ):
            transactions.append(transaction)
    return transactions


def _reconcilable_stale_draft_path(
    workspace: Path, project_root: Path, current_path: Path
) -> Path | None:
    expected_nodes = {
        f"draft:{transaction.proposal_correlation_id.removeprefix('correlation:')}"
        for transaction in _committed_reconciliation_transactions(workspace)
        if transaction.proposal_correlation_id is not None
        and Path(transaction.original_project_root).resolve() == project_root
    }
    if not expected_nodes:
        return None
    matches: list[Path] = []
    for path in sorted((workspace / "drafts").glob("*.draft.json")):
        if path == current_path:
            continue
        try:
            candidate, _ = read_draft_graph_document_protocol(
                json.loads(path.read_text(encoding="utf-8"))
            )
        except (OSError, ValueError):
            continue
        if expected_nodes.intersection(node.node_id for node in candidate.nodes):
            matches.append(path)
    if len(matches) > 1:
        raise ValueError("multiple stale draft documents match committed proposal correlations")
    return matches[0] if matches else None


def _reconcile_stale_draft(
    saved: DraftGraphDocument,
    *,
    architecture: ArchitectureIR,
    source_digest: str,
    registry_digest: str,
    evidence: list[EvidenceRecord],
    workspace: Path,
) -> DraftGraphDocument:
    draft = saved.model_copy(
        update={
            "base_architecture_id": architecture.architecture_id,
            "base_source_digest": source_digest,
            "base_registry_digest": registry_digest,
            "revision": saved.revision + 1,
        }
    )
    available = _available_architecture_subject_ids(architecture, evidence)
    receipts = list(saved.reconciliation_receipts)
    handled_correlations = {
        receipt.proposal_correlation_id for receipt in receipts
    }

    for transaction in _committed_reconciliation_transactions(workspace):
        correlation_id = transaction.proposal_correlation_id
        assert correlation_id is not None
        if correlation_id in handled_correlations:
            continue
        draft_node_id = f"draft:{correlation_id.removeprefix('correlation:')}"
        node = next((item for item in draft.nodes if item.node_id == draft_node_id), None)
        if node is None:
            continue
        node_port_ids = {port.port_id for port in node.ports}
        incident_edge_ids = {
            edge.edge_id
            for edge in draft.edges
            if edge.source_port_id in node_port_ids or edge.target_port_id in node_port_ids
        }
        synthetic_subject_ids = {draft_node_id, *node_port_ids, *incident_edge_ids}
        affected_intent_ids = {
            intent.intent_id
            for intent in draft.intents
            if synthetic_subject_ids.intersection(intent.target_ids)
        }
        missing = sorted(set(transaction.realized_subject_ids) - available)
        timestamp = datetime.now(UTC).isoformat()
        if not missing:
            receipt = ProposalReconciliationReceipt(
                receipt_id=f"reconciliation:{transaction.transaction_id}",
                proposal_correlation_id=correlation_id,
                transaction_id=transaction.transaction_id,
                status="realized",
                synthetic_subject_ids=sorted(synthetic_subject_ids),
                canonical_subject_ids=sorted(transaction.realized_subject_ids),
                reconciled_at=timestamp,
                message=(
                    "The committed proposal was found in the refreshed architecture; "
                    "its synthetic draft subjects were retired."
                ),
            )
            remaining_intents = [
                item for item in draft.intents if item.intent_id not in affected_intent_ids
            ]
            remaining_proofs = [
                item for item in draft.proofs if item.intent_id not in affected_intent_ids
            ]
            blocking = [
                item
                for item in draft.writeback_summary.blocking_intent_ids
                if item not in affected_intent_ids
            ]
            draft = draft.model_copy(
                update={
                    "nodes": [item for item in draft.nodes if item.node_id != draft_node_id],
                    "edges": [
                        item for item in draft.edges if item.edge_id not in incident_edge_ids
                    ],
                    "intents": remaining_intents,
                    "proofs": remaining_proofs,
                    "reconciliation_receipts": [*receipts, receipt],
                    "lowering_status": "blocked" if remaining_proofs else "not-planned",
                    "writeback_summary": WritebackSummary(
                        eligibility="blocked",
                        blocking_intent_ids=blocking,
                    ),
                }
            )
            receipts.append(receipt)
            continue

        receipt = ProposalReconciliationReceipt(
            receipt_id=f"reconciliation:{transaction.transaction_id}",
            proposal_correlation_id=correlation_id,
            transaction_id=transaction.transaction_id,
            status="blocked",
            synthetic_subject_ids=sorted(synthetic_subject_ids),
            canonical_subject_ids=sorted(transaction.realized_subject_ids),
            missing_subject_ids=missing,
            reconciled_at=timestamp,
            message=(
                "The committed proposal could not be matched to every expected canonical "
                "node, port, and evidence record; the synthetic draft was retained."
            ),
        )
        proofs = [
            proof.model_copy(
                update={
                    "status": EditProofState.STALE,
                    "writeback_eligibility": "blocked",
                    "reason_codes": ["SYNTHETIC_REALIZATION_MISMATCH"],
                    "message": receipt.message,
                    "required_facts": missing,
                    "supported_fixes": [
                        "Re-run analysis with the committed source and exact registry bundle."
                    ],
                }
            )
            if proof.intent_id in affected_intent_ids
            else proof
            for proof in draft.proofs
        ]
        blocking = sorted(
            set(draft.writeback_summary.blocking_intent_ids) | affected_intent_ids
        )
        draft = draft.model_copy(
            update={
                "proofs": proofs,
                "reconciliation_receipts": [*receipts, receipt],
                "lowering_status": "blocked",
                "writeback_summary": WritebackSummary(
                    eligibility="blocked",
                    blocking_intent_ids=blocking,
                ),
            }
        )
        receipts.append(receipt)

    return DraftGraphDocument.model_validate(draft.model_dump(mode="json"))


def prepare_studio_bundle(
    artifact: Path,
    workspace: Path,
    *,
    write_static: bool = True,
    replace_stale_bindings: bool = False,
) -> StudioBundle:
    artifact = artifact.resolve()
    workspace = workspace.resolve()
    recover_incomplete_transactions(workspace)
    architecture = ArchitectureIR.model_validate_json(artifact.read_text(encoding="utf-8"))
    snapshot_path = artifact.parent / "source-snapshot.json"
    if not snapshot_path.is_file():
        raise ValueError("Studio requires source-snapshot.json beside architecture.json")
    snapshot = SourceSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
    environment_path = artifact.parent / "analysis-environment-manifest-v1.json"
    analysis_input_path = artifact.parent / "analysis-input-v2.json"
    if environment_path.is_file() != analysis_input_path.is_file():
        raise ValueError("Studio found an incomplete v2 analysis manifest set")
    analysis_environment = (
        AnalysisEnvironmentManifest.model_validate_json(
            environment_path.read_text(encoding="utf-8")
        )
        if environment_path.is_file()
        else None
    )
    analysis_input = (
        AnalysisInputManifest.model_validate_json(
            analysis_input_path.read_text(encoding="utf-8")
        )
        if analysis_input_path.is_file()
        else None
    )
    if (
        analysis_environment is not None
        and analysis_input is not None
        and (
            analysis_input.environment_manifest_digest
            != analysis_environment.environment_manifest_digest
            or analysis_input.registry_digest != analysis_environment.registry_digest
            or analysis_input.analyzer_build_digest != analysis_environment.analyzer_digest
            or analysis_input.pattern_pack_digests
            != analysis_environment.pattern_pack_digests
        )
    ):
        raise ValueError("Studio v2 analysis manifests have inconsistent digest bindings")
    evidence_path = artifact.parent / "evidence-ledger.json"
    evidence = (
        TypeAdapter(list[EvidenceRecord]).validate_json(evidence_path.read_text(encoding="utf-8"))
        if evidence_path.is_file()
        else []
    )
    semantic_overlay_path = artifact.parent / "semantic-annotation-overlay.json"
    semantic_overlay = (
        SemanticAnnotationOverlay.model_validate_json(
            semantic_overlay_path.read_text(encoding="utf-8")
        )
        if semantic_overlay_path.is_file()
        else None
    )
    if semantic_overlay is not None and (
        semantic_overlay.architecture_id != architecture.architecture_id
        or semantic_overlay.exact_ir_digest != exact_ir_digest(architecture)
    ):
        raise ValueError("semantic annotation overlay binding is stale")
    runtime_trace_path = artifact.parent / "runtime-trace.json"
    runtime_evidence_path = artifact.parent / "runtime-evidence-ledger.json"
    runtime_overlay_path = artifact.parent / "runtime-evidence-overlay.json"
    runtime_receipt_path = artifact.parent / "runtime-receipt.json"
    runtime_trace: RuntimeTrace | None = None
    runtime_node_evidence: dict[str, list[str]] = {}
    runtime_paths = (runtime_trace_path, runtime_evidence_path, runtime_overlay_path)
    runtime_receipt = (
        json.loads(runtime_receipt_path.read_text(encoding="utf-8"))
        if runtime_receipt_path.is_file()
        else None
    )
    if any(path.is_file() for path in runtime_paths) and runtime_receipt is None:
        raise ValueError("Studio found runtime evidence without a runtime receipt")
    if runtime_receipt is not None and runtime_receipt.get("status") == "ok":
        if not all(
            path.is_file() for path in runtime_paths
        ):
            raise ValueError("Studio found an incomplete runtime evidence bundle")
        runtime_trace = RuntimeTrace.model_validate_json(
            runtime_trace_path.read_text(encoding="utf-8")
        )
        if (
            runtime_trace.architecture_id != architecture.architecture_id
            or runtime_trace.source_snapshot_id != snapshot.snapshot_id
            or runtime_trace.source_revision != snapshot.revision
        ):
            raise ValueError("runtime evidence belongs to a stale architecture or source snapshot")
        runtime_evidence = TypeAdapter(list[EvidenceRecord]).validate_json(
            runtime_evidence_path.read_text(encoding="utf-8")
        )
        overlay = json.loads(runtime_overlay_path.read_text(encoding="utf-8"))
        if (
            overlay.get("architecture_id") != architecture.architecture_id
            or overlay.get("trace_id") != runtime_trace.trace_id
            or runtime_receipt.get("details", {}).get("trace_id") != runtime_trace.trace_id
        ):
            raise ValueError("runtime evidence overlay binding is stale")
        runtime_node_evidence = TypeAdapter(dict[str, list[str]]).validate_python(
            overlay.get("node_evidence", {})
        )
        runtime_ids = {item.evidence_id for item in runtime_evidence}
        if any(
            evidence_id not in runtime_ids
            for ids in runtime_node_evidence.values()
            for evidence_id in ids
        ):
            raise ValueError("runtime evidence overlay references an unknown record")
        evidence.extend(runtime_evidence)
    hierarchy = compile_hierarchy(architecture, semantic_overlay)
    navigation = build_navigation_projections(architecture, snapshot, evidence, hierarchy)
    suffix = architecture.architecture_id.removeprefix("architecture:")
    document_path = workspace / "documents" / f"{suffix}.canvas.json"
    document: CanvasDocument | None = None
    protocol_migration_receipts = _load_protocol_migration_receipts(workspace)
    if document_path.is_file():
        saved_document, migration_receipt = load_canvas_document_with_receipt(document_path)
        protocol_migration_receipts = [
            receipt
            for receipt in protocol_migration_receipts
            if receipt.receipt_id != migration_receipt.receipt_id
        ]
        protocol_migration_receipts.append(migration_receipt)
        _write_json(
            workspace
            / "protocol-migrations"
            / f"{migration_receipt.receipt_id.removeprefix('receipt:')}.json",
            migration_receipt,
        )
        if migration_receipt.status != "current":
            persist_canvas_document(document_path, saved_document)
        expected_digest = source_binding_digest(snapshot)
        stale_reason = next(
            (
                message
                for invalid, message in (
                    (
                        saved_document.architecture_id != architecture.architecture_id,
                        "saved CanvasDocument belongs to a different architecture",
                    ),
                    (
                        saved_document.source_snapshot_id != snapshot.snapshot_id,
                        "saved CanvasDocument belongs to a stale source snapshot",
                    ),
                    (
                        saved_document.source_digest != expected_digest,
                        "saved CanvasDocument source digest is stale",
                    ),
                    (
                        saved_document.base_hierarchy_id not in {None, hierarchy.hierarchy_id},
                        "saved CanvasDocument hierarchy does not match this compilation",
                    ),
                )
                if invalid
            ),
            None,
        )
        if stale_reason is not None:
            if not replace_stale_bindings:
                raise ValueError(stale_reason)
            _archive_stale_binding(document_path)
        else:
            document = saved_document
        if document is not None and document.base_hierarchy_id is None:
            document = document.model_copy(update={"base_hierarchy_id": hierarchy.hierarchy_id})
            persist_canvas_document(document_path, document)
    if document is None:
        document = create_canvas_document(
            architecture, snapshot, hierarchy_id=hierarchy.hierarchy_id
        )
        persist_canvas_document(document_path, document)

    state = derive_view_state(document)
    projection = str(state.get("navigation_view", "module"))
    expandable = expandable_node_ids(hierarchy)
    if projection == "module":
        expanded_ids = (
            _reachable_expansions(
                navigation, "module", set(state.get("module_expansion", []))
            )
            & expandable
        )
    else:
        source_rows = navigation["projections"]["source"]["nodes"]
        source_expanded = _reachable_expansions(
            navigation, "source", set(state.get("source_expansion", []))
        )
        source_expandable = {
            row["id"] for row in source_rows if row["child_count"] > 0
        }
        if source_expandable and source_expandable <= source_expanded:
            expanded_ids = expandable
        else:
            visible_depth = max(
                (row["depth"] for row in source_rows if row["id"] in source_expanded),
                default=0,
            )
            expanded_ids = {
                node.hierarchy_node_id
                for node in hierarchy.nodes
                if node.hierarchy_node_id in expandable and node.depth <= visible_depth
            }
    view = project_hierarchy(architecture, hierarchy, expanded_ids)
    views = {view.projection_id: view}

    project_manifest_path = artifact.parent / "project-manifest-v2.json"
    project_root = Path(snapshot.project_root).resolve()
    if project_manifest_path.is_file():
        project_manifest_payload = json.loads(
            project_manifest_path.read_text(encoding="utf-8")
        )
        project_root_hint = project_manifest_payload.get("project_root_hint")
        if isinstance(project_root_hint, str) and project_root_hint:
            hinted_root = Path(project_root_hint).resolve()
            if hinted_root.is_dir():
                project_root = hinted_root
    project_session = create_project_session(
        project_root,
        workspace,
        generation=1,
        snapshot=snapshot,
    )
    project_discovery = discover_project(project_root)
    draft_path = workspace / "drafts" / f"{suffix}.draft.json"
    stale_draft: DraftGraphDocument | None = None
    if not draft_path.is_file() and replace_stale_bindings:
        prior_draft_path = _reconcilable_stale_draft_path(
            workspace, project_root, draft_path
        )
        if prior_draft_path is not None:
            saved_draft, _ = read_draft_graph_document_protocol(
                json.loads(prior_draft_path.read_text(encoding="utf-8"))
            )
            stale_draft = saved_draft
            _archive_stale_binding(prior_draft_path)
    if draft_path.is_file():
        saved_draft, _ = read_draft_graph_document_protocol(
            json.loads(draft_path.read_text(encoding="utf-8"))
        )
        if (
            saved_draft.base_architecture_id != architecture.architecture_id
            or saved_draft.base_source_digest != document.source_digest
            or saved_draft.base_registry_digest
            not in {None, MODULE_REGISTRY.bundle.bundle_digest}
        ):
            if not replace_stale_bindings:
                raise ValueError("saved DraftGraphDocument binding is stale")
            stale_draft = saved_draft
            _archive_stale_binding(draft_path)
            draft = None
        else:
            draft = saved_draft
    else:
        draft = None
    if draft is None:
        draft = (
            _reconcile_stale_draft(
                stale_draft,
                architecture=architecture,
                source_digest=document.source_digest,
                registry_digest=MODULE_REGISTRY.bundle.bundle_digest,
                evidence=evidence,
                workspace=workspace,
            )
            if stale_draft is not None
            else DraftGraphDocument(
                draft_id=f"draft:{suffix}",
                base_architecture_id=architecture.architecture_id,
                base_source_digest=document.source_digest,
                base_registry_digest=MODULE_REGISTRY.bundle.bundle_digest,
                revision=0,
            )
        )
        _write_json(draft_path, draft)

    source_workspace_path = workspace / "source-workspace" / f"{suffix}.source-workspace.json"
    if source_workspace_path.is_file():
        saved_source_workspace = SourceWorkspaceDocument.model_validate_json(
            source_workspace_path.read_text(encoding="utf-8")
        )
        if (
            saved_source_workspace.source_snapshot_id != snapshot.snapshot_id
            or saved_source_workspace.base_revision != snapshot.revision
        ):
            if not replace_stale_bindings:
                raise ValueError("saved source workspace binding is stale")
            _archive_stale_binding(source_workspace_path)
            source_workspace = None
        else:
            source_workspace = saved_source_workspace
    else:
        source_workspace = None
    if source_workspace is None:
        source_workspace = SourceWorkspaceDocument(
            workspace_id=f"source-workspace:{suffix}",
            source_snapshot_id=snapshot.snapshot_id,
            base_revision=snapshot.revision,
            revision=0,
        )
        _write_json(source_workspace_path, source_workspace)

    round_trip_reports = _load_conformance_reports(workspace)
    source_view_report = build_source_view_report(
        architecture,
        hierarchy,
        document.source_digest,
    )
    round_trip_reports = [
        report
        for report in round_trip_reports
        if report.report_id != source_view_report.report_id
    ]
    round_trip_reports.append(source_view_report)
    _write_json(_conformance_report_path(workspace, source_view_report), source_view_report)

    bundle = StudioBundle(
        artifact_path=artifact,
        workspace=workspace,
        static_dir=workspace / "studio",
        document_path=document_path,
        architecture=architecture,
        snapshot=snapshot,
        evidence=evidence,
        runtime_trace=runtime_trace,
        runtime_node_evidence=runtime_node_evidence,
        semantic_overlay=semantic_overlay,
        hierarchy=hierarchy,
        views=views,
        document=document,
        project_session=project_session,
        project_discovery=project_discovery,
        draft_path=draft_path,
        draft=draft,
        source_workspace_path=source_workspace_path,
        source_workspace=source_workspace,
        search_index=[],
        validation_runs=[],
        navigation=navigation,
        parameter_edit_contexts=resolve_parameter_edit_contexts(artifact),
        analysis_environment=analysis_environment,
        analysis_input=analysis_input,
        contract_maintenance=ContractMaintenanceManager(workspace, MODULE_REGISTRY),
        generated_projects=GeneratedProjectManager(workspace, MODULE_REGISTRY),
        round_trip_reports=round_trip_reports,
        recovery_receipts=_load_recovery_receipts(workspace),
        protocol_migration_receipts=protocol_migration_receipts,
    )
    bundle.search_index = build_search_index(bundle)
    _write_json(workspace / "publication" / "hierarchy.json", hierarchy)
    _write_json(workspace / "publication" / "current" / "publication-view.json", view)
    if write_static:
        _write_static_bundle(bundle)
    return bundle
