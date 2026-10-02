from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path, PureWindowsPath
from typing import Any

from archcanvas_core.architecture_v2 import PythonSemanticGraph
from archcanvas_core.models import (
    ArchitectureIR,
    OfflineBundleFile,
    OfflineBundleManifest,
    ProtocolMigrationReceipt,
    RecoveryReceipt,
    ReleaseSupportMatrixV2,
    RoundTripConformanceReport,
    SemanticAnnotationOverlay,
    SourceSnapshot,
    StateMigrationPlan,
    TransactionJournal,
    TransactionReceipt,
)
from archcanvas_core.protocols import (
    read_exact_architecture_ir_v2_protocol,
    read_offline_bundle_manifest_protocol,
    read_source_transaction_protocol,
    read_state_migration_plan_protocol,
)
from archcanvas_core.source_v2 import (
    AnalysisEnvironmentManifest,
    AnalysisInputManifest,
    ProjectManifest,
    SourceCorpus,
)
from archcanvas_patterns import exact_ir_digest
from archcanvas_publication import (
    build_scene,
    build_visual_spec,
    compile_hierarchy,
    compile_views,
    render_html,
    render_pdf,
    render_png,
    render_svg,
    validate_geometry,
    validate_publication,
)

from .support import release_support_matrix

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _compact(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and (
        Path(value).is_absolute() or PureWindowsPath(value).is_absolute()
    ):
        name = PureWindowsPath(value).name if PureWindowsPath(value).is_absolute() else Path(value).name
        return f"<redacted>/{name}"
    return value


def _write_json(path: Path, value: Any, *, redact: bool = False) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if redact:
        value = _redact(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_compact(value), encoding="utf-8")


def _overlay(artifact: Path, architecture: ArchitectureIR) -> SemanticAnnotationOverlay | None:
    path = artifact.parent / "semantic-annotation-overlay.json"
    if not path.is_file():
        return None
    overlay = SemanticAnnotationOverlay.model_validate_json(path.read_text(encoding="utf-8"))
    if (
        overlay.architecture_id != architecture.architecture_id
        or overlay.exact_ir_digest != exact_ir_digest(architecture)
    ):
        raise ValueError("semantic annotation overlay binding is stale")
    return overlay


def _bundle_files(root: Path) -> list[OfflineBundleFile]:
    return [
        OfflineBundleFile(
            path=path.relative_to(root).as_posix(),
            sha256=_sha256(path),
            size=path.stat().st_size,
        )
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "bundle-manifest.json"
    ]


def _copy_workspace_receipts(
    workspace: Path,
    target: Path,
    *,
    exact_digest: str,
    source_snapshot_id: str,
) -> None:
    workspace = workspace.resolve()
    if not workspace.is_dir():
        raise ValueError(f"Studio workspace does not exist: {workspace}")

    conformance_target = target / "conformance"
    for path in sorted((workspace / "conformance").glob("*.json")):
        report = RoundTripConformanceReport.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if report.result_exact_ir_digest != exact_digest:
            continue
        _write_json(conformance_target / path.name, report, redact=True)

    migration_target = target / "protocol-migrations"
    for path in sorted((workspace / "protocol-migrations").glob("*.json")):
        receipt = ProtocolMigrationReceipt.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        _write_json(migration_target / path.name, receipt, redact=True)

    transaction_root = workspace / "transactions"
    if not transaction_root.is_dir():
        return
    validators: dict[str, type[Any]] = {
        "transaction-receipt.json": TransactionReceipt,
        "state-migration-plan.json": StateMigrationPlan,
        "transaction-journal.json": TransactionJournal,
        "recovery-receipt.json": RecoveryReceipt,
    }
    for directory in sorted(path for path in transaction_root.iterdir() if path.is_dir()):
        transaction_path = directory / "transaction.json"
        if not transaction_path.is_file():
            continue
        transaction, _ = read_source_transaction_protocol(
            json.loads(transaction_path.read_text(encoding="utf-8"))
        )
        exact_binding = exact_digest in {
            transaction.base_exact_ir_digest,
            transaction.result_exact_ir_digest,
        }
        snapshot_binding = transaction.source_snapshot_id == source_snapshot_id
        if not exact_binding and not snapshot_binding:
            continue
        transaction_target = target / "transactions" / transaction.transaction_id
        _write_json(transaction_target / "transaction.json", transaction, redact=True)
        for filename, model in validators.items():
            source = directory / filename
            if not source.is_file():
                continue
            value = model.model_validate_json(source.read_text(encoding="utf-8"))
            if getattr(value, "transaction_id", transaction.transaction_id) != transaction.transaction_id:
                raise ValueError(f"{filename} belongs to a different transaction")
            if (
                isinstance(value, StateMigrationPlan)
                and transaction.state_migration_plan is not None
                and value.plan_id != transaction.state_migration_plan.plan_id
            ):
                raise ValueError("state migration plan does not match its transaction")
            _write_json(transaction_target / filename, value, redact=True)


def _verify_workspace_receipts(root: Path, manifest: OfflineBundleManifest) -> None:
    receipts = root / "receipts"
    if not receipts.is_dir():
        return
    for path in sorted((receipts / "conformance").glob("*.json")):
        report = RoundTripConformanceReport.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if report.result_exact_ir_digest != manifest.exact_ir_digest:
            raise ValueError("offline bundle conformance report binding is invalid")
    for path in sorted((receipts / "protocol-migrations").glob("*.json")):
        ProtocolMigrationReceipt.model_validate_json(path.read_text(encoding="utf-8"))
    for directory in sorted((receipts / "transactions").glob("*")):
        if not directory.is_dir():
            continue
        transaction, _ = read_source_transaction_protocol(
            json.loads((directory / "transaction.json").read_text(encoding="utf-8"))
        )
        exact_binding = manifest.exact_ir_digest in {
            transaction.base_exact_ir_digest,
            transaction.result_exact_ir_digest,
        }
        snapshot_binding = transaction.source_snapshot_id == manifest.source_snapshot_id
        if not exact_binding and not snapshot_binding:
            raise ValueError("offline bundle transaction binding is invalid")
        receipt_path = directory / "transaction-receipt.json"
        if receipt_path.is_file():
            receipt = TransactionReceipt.model_validate_json(
                receipt_path.read_text(encoding="utf-8")
            )
            if receipt.transaction_id != transaction.transaction_id:
                raise ValueError("offline bundle transaction receipt binding is invalid")
        plan_path = directory / "state-migration-plan.json"
        if plan_path.is_file():
            plan, _ = read_state_migration_plan_protocol(
                json.loads(plan_path.read_text(encoding="utf-8"))
            )
            if (
                transaction.state_migration_plan is None
                or plan.plan_id != transaction.state_migration_plan.plan_id
            ):
                raise ValueError("offline bundle state migration binding is invalid")
        journal_path = directory / "transaction-journal.json"
        if journal_path.is_file():
            journal = TransactionJournal.model_validate_json(
                journal_path.read_text(encoding="utf-8")
            )
            if journal.transaction_id != transaction.transaction_id:
                raise ValueError("offline bundle transaction journal binding is invalid")
        recovery_path = directory / "recovery-receipt.json"
        if recovery_path.is_file():
            recovery = RecoveryReceipt.model_validate_json(
                recovery_path.read_text(encoding="utf-8")
            )
            if recovery.transaction_id != transaction.transaction_id:
                raise ValueError("offline bundle recovery receipt binding is invalid")


def create_bundle(
    artifact: Path,
    output: Path,
    *,
    workspace: Path | None = None,
) -> tuple[OfflineBundleManifest, list[str]]:
    artifact = artifact.resolve()
    output = output.resolve()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"bundle output already exists: {output}")
    architecture = ArchitectureIR.model_validate_json(artifact.read_text(encoding="utf-8"))
    snapshot_path = artifact.parent / "source-snapshot.json"
    if not snapshot_path.is_file():
        raise ValueError("offline bundle requires source-snapshot.json beside architecture.json")
    snapshot = SourceSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
    if snapshot.snapshot_id != architecture.source_snapshot_id:
        raise ValueError("source snapshot does not match architecture")
    semantic_overlay = _overlay(artifact, architecture)
    views = compile_views(architecture, semantic_overlay)
    hierarchy = compile_hierarchy(architecture, semantic_overlay)
    publication_gates, diagnostics = validate_publication(architecture, views)
    gates = [gate.model_dump(mode="json") for gate in publication_gates]
    if diagnostics or any(gate.status == "failed" for gate in publication_gates):
        raise ValueError("publication validation failed; refusing to create release bundle")

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".archcanvas-bundle-", dir=output.parent))
    try:
        analysis_target = staging / "analysis"
        analysis_target.mkdir()
        allowlisted = {
            "architecture.json",
            "source-snapshot.json",
            "evidence-ledger.json",
            "module-ledger.json",
            "tensor-ledger.json",
            "edge-ledger.json",
            "discrepancy-ledger.json",
            "omission-ledger.json",
            "capability-report.json",
            "semantic-annotation-overlay.json",
            "pattern-pack-receipt.json",
            "pattern-candidate-review.json",
            "source-correction-report.json",
            "runtime-receipt.json",
            "runtime-trace.json",
            "runtime-evidence-ledger.json",
            "runtime-evidence-overlay.json",
            "analysis-receipt.json",
            "project-manifest-v2.json",
            "source-corpus-v2.json",
            "analysis-environment-manifest-v1.json",
            "analysis-input-v2.json",
            "semantic-graph-v2.json",
            "architecture-v2.json",
        }
        for source in sorted(artifact.parent.iterdir()):
            if source.is_file() and source.name in allowlisted:
                try:
                    payload = json.loads(source.read_text(encoding="utf-8"))
                except json.JSONDecodeError as error:
                    raise ValueError(f"bundle JSON artifact is invalid: {source.name}") from error
                _write_json(analysis_target / source.name, payload, redact=True)

        _write_json(staging / "publication" / "hierarchy.json", hierarchy)
        for view in views:
            projection_name = "full" if view.fully_expanded else "collapsed"
            target = staging / "publication" / projection_name
            spec = build_visual_spec(view)
            scene = build_scene(view, spec)
            geometry_gate, geometry_diagnostics = validate_geometry(scene)
            gates.append(geometry_gate.model_dump(mode="json"))
            if geometry_gate.status == "failed" or geometry_diagnostics:
                raise ValueError(
                    f"geometry validation failed for {view.projection_id}"
                )
            _write_json(target / "publication-view.json", view)
            _write_json(target / "visual-spec.json", spec)
            _write_json(target / "visual-scene.json", scene)
            (target / "scene.svg").write_text(render_svg(scene), encoding="utf-8")
            (target / "view.html").write_text(render_html(scene, view, spec), encoding="utf-8")
            (target / "scene.png").write_bytes(render_png(scene))
            (target / "scene.pdf").write_bytes(render_pdf(scene))

        digest = exact_ir_digest(architecture)
        if workspace is not None:
            _copy_workspace_receipts(
                workspace,
                staging / "receipts",
                exact_digest=digest,
                source_snapshot_id=snapshot.snapshot_id,
            )

        shutil.copytree(REPOSITORY_ROOT / "schemas", staging / "schemas")
        support_matrix_path = staging / "support-matrix.json"
        _write_json(support_matrix_path, release_support_matrix())
        _write_json(
            staging / "verification-receipt.json",
            {
                "schema_version": "1.0",
                "status": "ok",
                "source_execution": False,
                "network_required": False,
                "gates": gates,
                "visual_review": "not-included",
            },
        )
        files = _bundle_files(staging)
        analysis_input_digest = None
        environment_manifest_digest = None
        v2_names = {
            "project-manifest-v2.json",
            "source-corpus-v2.json",
            "analysis-environment-manifest-v1.json",
            "analysis-input-v2.json",
            "semantic-graph-v2.json",
            "architecture-v2.json",
        }
        present_v2 = {
            name for name in v2_names if (analysis_target / name).is_file()
        }
        if present_v2 and present_v2 != v2_names:
            raise ValueError("offline bundle requires a complete v2 analysis artifact set")
        if present_v2:
            environment = AnalysisEnvironmentManifest.model_validate_json(
                (analysis_target / "analysis-environment-manifest-v1.json").read_text(
                    encoding="utf-8"
                )
            )
            analysis_input = AnalysisInputManifest.model_validate_json(
                (analysis_target / "analysis-input-v2.json").read_text(encoding="utf-8")
            )
            corpus = SourceCorpus.model_validate_json(
                (analysis_target / "source-corpus-v2.json").read_text(encoding="utf-8")
            )
            semantic_graph = PythonSemanticGraph.model_validate_json(
                (analysis_target / "semantic-graph-v2.json").read_text(encoding="utf-8")
            )
            exact_v2, _ = read_exact_architecture_ir_v2_protocol(
                json.loads(
                    (analysis_target / "architecture-v2.json").read_text(
                        encoding="utf-8"
                    )
                )
            )
            if (
                analysis_input.environment_manifest_digest
                != environment.environment_manifest_digest
                or analysis_input.registry_digest != environment.registry_digest
                or exact_v2.analysis_input_digest != analysis_input.analysis_input_digest
                or exact_v2.source_corpus_digest != corpus.source_corpus_digest
                or semantic_graph.source_corpus_digest != corpus.source_corpus_digest
                or exact_v2.registry_digest != environment.registry_digest
            ):
                raise ValueError("offline bundle v2 analysis digest bindings are inconsistent")
            analysis_input_digest = analysis_input.analysis_input_digest
            environment_manifest_digest = environment.environment_manifest_digest
        manifest = OfflineBundleManifest(
            bundle_id=f"bundle:{hashlib.sha256(f'{architecture.architecture_id}:{digest}'.encode()).hexdigest()[:16]}",
            architecture_id=architecture.architecture_id,
            source_snapshot_id=snapshot.snapshot_id,
            exact_ir_digest=digest,
            analysis_input_digest=analysis_input_digest,
            environment_manifest_digest=environment_manifest_digest,
            support_matrix_digest=_sha256(support_matrix_path),
            absolute_paths_redacted=True,
            files=files,
        )
        _write_json(staging / "bundle-manifest.json", manifest)
        os.replace(staging, output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest, [item["gate"] for item in gates if item["status"] == "passed"]


def verify_bundle(root: Path) -> OfflineBundleManifest:
    root = root.resolve()
    manifest_path = root / "bundle-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("bundle-manifest.json is missing")
    manifest, _ = read_offline_bundle_manifest_protocol(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    expected = {item.path: item for item in manifest.files}
    actual = {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() and path.name != "bundle-manifest.json"
    }
    if set(actual) != set(expected):
        raise ValueError("offline bundle file inventory does not match its manifest")
    for relative, path in actual.items():
        record = expected[relative]
        if _sha256(path) != record.sha256 or path.stat().st_size != record.size:
            raise ValueError(f"offline bundle file digest mismatch: {relative}")
    architecture = ArchitectureIR.model_validate_json(
        (root / "analysis" / "architecture.json").read_text(encoding="utf-8")
    )
    if (
        architecture.architecture_id != manifest.architecture_id
        or exact_ir_digest(architecture) != manifest.exact_ir_digest
    ):
        raise ValueError("offline bundle architecture binding is invalid")
    support_matrix_path = root / "support-matrix.json"
    ReleaseSupportMatrixV2.model_validate_json(
        support_matrix_path.read_text(encoding="utf-8")
    )
    if _sha256(support_matrix_path) != manifest.support_matrix_digest:
        raise ValueError("offline bundle support matrix binding is invalid")
    analysis_root = root / "analysis"
    v2_paths = {
        "project": analysis_root / "project-manifest-v2.json",
        "environment": analysis_root / "analysis-environment-manifest-v1.json",
        "input": analysis_root / "analysis-input-v2.json",
        "corpus": analysis_root / "source-corpus-v2.json",
        "semantic_graph": analysis_root / "semantic-graph-v2.json",
        "exact_ir": analysis_root / "architecture-v2.json",
    }
    present_v2 = {name for name, path in v2_paths.items() if path.is_file()}
    if present_v2 and present_v2 != set(v2_paths):
        raise ValueError("offline bundle contains an incomplete v2 analysis artifact set")
    if present_v2:
        ProjectManifest.model_validate_json(
            v2_paths["project"].read_text(encoding="utf-8")
        )
        environment = AnalysisEnvironmentManifest.model_validate_json(
            v2_paths["environment"].read_text(encoding="utf-8")
        )
        analysis_input = AnalysisInputManifest.model_validate_json(
            v2_paths["input"].read_text(encoding="utf-8")
        )
        corpus = SourceCorpus.model_validate_json(
            v2_paths["corpus"].read_text(encoding="utf-8")
        )
        semantic_graph = PythonSemanticGraph.model_validate_json(
            v2_paths["semantic_graph"].read_text(encoding="utf-8")
        )
        exact_v2, _ = read_exact_architecture_ir_v2_protocol(
            json.loads(v2_paths["exact_ir"].read_text(encoding="utf-8"))
        )
        if (
            manifest.analysis_input_digest != analysis_input.analysis_input_digest
            or manifest.environment_manifest_digest
            != environment.environment_manifest_digest
            or analysis_input.environment_manifest_digest
            != environment.environment_manifest_digest
            or analysis_input.registry_digest != environment.registry_digest
            or exact_v2.analysis_input_digest != analysis_input.analysis_input_digest
            or exact_v2.source_corpus_digest != corpus.source_corpus_digest
            or semantic_graph.source_corpus_digest != corpus.source_corpus_digest
            or exact_v2.registry_digest != environment.registry_digest
        ):
            raise ValueError("offline bundle v2 analysis binding is invalid")
    elif manifest.analysis_input_digest is not None or manifest.environment_manifest_digest is not None:
        raise ValueError("offline bundle manifest references missing v2 analysis artifacts")
    _verify_workspace_receipts(root, manifest)
    return manifest
