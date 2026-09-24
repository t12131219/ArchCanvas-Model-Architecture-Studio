from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from archcanvas_adapters import (
    analyze_with_adapter,
    apply_model_transaction,
    transaction_adapter_id,
    transaction_artifact_kind,
    validate_model_artifact,
    validate_model_transaction_delta,
)
from archcanvas_core.models import (
    ArchitectureIR,
    Diagnostic,
    EvidenceKind,
    EvidenceRecord,
    FileChange,
    GateResult,
    SemanticParameterPatch,
    SemanticStructuralPatch,
    SourceSnapshot,
    SourceTransaction,
    TransactionReceipt,
    TransactionState,
)
from archcanvas_core.validation import validate_architecture
from archcanvas_publication import (
    build_scene,
    build_visual_spec,
    compile_views,
    validate_geometry,
    validate_publication,
)
from archcanvas_runtime import trace_runtime

from .delta import graph_delta
from .registry import apply_structural_transform, validate_structural_oracle
from .store import load_transaction, save_transaction
from .transforms import (
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
    return TransactionReceipt(
        transaction_id=transaction.transaction_id,
        framework=transaction.framework,
        transaction_adapter_id=transaction.transaction_adapter_id,
        artifact_kind=transaction.artifact_kind,
        state=transaction.state,
        status="ok" if ok else "invalid",
        gates=transaction.gates,
        diagnostics=transaction.diagnostics,
        source_writes=source_writes,
    )


def _load_artifact(artifact_path: Path) -> tuple[ArchitectureIR, SourceSnapshot, list[EvidenceRecord]]:
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
    return architecture, snapshot, evidence


def _validate_snapshot(snapshot: SourceSnapshot) -> None:
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


def _copy_project(project: Path, target: Path, workspace: Path) -> None:
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


def _analyze_at(project: Path, snapshot: SourceSnapshot):
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
    return analyze_with_adapter(
        project,
        snapshot.entrypoint,
        snapshot.task,
        snapshot.execution_mode,
        config_bytes,
        config_path,
        framework=snapshot.framework,
        pattern_packs_enabled=True,
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
) -> tuple[SourceTransaction, TransactionReceipt]:
    artifact = Path(request.artifact_path).resolve()
    architecture, snapshot, evidence = _load_artifact(artifact)
    if architecture.framework != snapshot.framework:
        raise ValueError("architecture and snapshot framework bindings do not match")
    artifact_kind = transaction_artifact_kind(architecture.framework)
    _validate_snapshot(snapshot)
    project = Path(snapshot.project_root).resolve()
    node = next((item for item in architecture.nodes if item.node_id == request.target_node_id), None)
    if node is None:
        raise ValueError(f"target node is not present in Exact IR: {request.target_node_id}")
    seed = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    transaction_id = f"transaction:{_sha256((seed + datetime.now(UTC).isoformat()).encode())[:16]}"
    workspace = workspace.resolve()
    directory = workspace / "transactions" / transaction_id
    temporary_project = directory / "project"
    directory.mkdir(parents=True, exist_ok=False)
    _copy_project(project, temporary_project, workspace)

    semantic_manifest: str | None = None
    additional_model_files: list[Any] = []
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
        anchor = _anchor_fingerprint(snapshot, node, parameter, evidence)
        if parameter.origin.value == "config":
            relative = _relative_config(snapshot, project)
            original_path = project / relative
            config_records = [
                item
                for item in evidence
                if item.evidence_id in parameter.evidence_ids and item.kind is EvidenceKind.CONFIG
            ]
            key = config_records[-1].symbol if config_records else parameter.source_expression
            if not key:
                raise ValueError("config-backed parameter has no exact config key anchor")
            transformed = set_json_value(original_path.read_bytes(), key, request.new_value)
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
            if definition is None or definition.path is None or definition.span is None:
                raise ValueError("literal parameter has no exact module-definition anchor")
            relative = Path(definition.path)
            original_path = project / relative
            module_path = str(node.attributes.get("module_path", ""))
            functional_anchor = node.attributes.get("functional_anchor")
            if module_path.startswith("self."):
                transformed = set_python_parameter(
                    original_path.read_bytes(),
                    module_name=module_path.removeprefix("self."),
                    parameter_name=parameter.name,
                    source_expression=parameter.source_expression,
                    value=request.new_value,
                    expected_line=definition.span.start_line,
                )
            elif isinstance(functional_anchor, str) and functional_anchor:
                transformed = set_functional_parameter(
                    original_path.read_bytes(),
                    target_name=functional_anchor,
                    parameter_name=parameter.name,
                    source_expression=parameter.source_expression,
                    value=request.new_value,
                    expected_line=definition.span.start_line,
                )
            elif ".field." in definition.evidence_id:
                transformed = set_class_field_parameter(
                    original_path.read_bytes(),
                    class_name=snapshot.entrypoint.split(":", 1)[1],
                    field_name=parameter.name,
                    source_expression=parameter.source_expression,
                    value=request.new_value,
                    expected_line=definition.span.start_line,
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
        anchor = _structural_anchor_fingerprint(snapshot, node, request, evidence)
        structural = apply_structural_transform(request, architecture, snapshot, evidence)
        relative = structural.relative_path
        original_path = project / relative
        transformed = structural.transformed
        kind = "python"

    before = original_path.read_bytes()
    prepared_path = temporary_project / relative
    write_prepared(prepared_path, transformed.content)
    after = prepared_path.read_bytes()
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
    prepared_bundle = _analyze_at(temporary_project, snapshot)
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
        created_at=datetime.now(UTC).isoformat(),
        workspace=str(workspace),
        original_project_root=str(project),
        temporary_project_root=str(temporary_project),
        artifact_path=str(artifact),
        source_snapshot_id=snapshot.snapshot_id,
        base_revision=snapshot.revision,
        anchor_fingerprint=anchor,
        file_changes=file_changes,
        source_diff=semantic_manifest or _unified_diff(relative, before, after),
        expected_delta=expected,
        gates=[
            _gate(
                "F-prepare",
                True,
                "Revision, file hash, anchor fingerprint, isolated copy, and bounded delta passed.",
                "Transaction preparation failed.",
            )
        ],
    )
    save_transaction(transaction)
    (directory / "source.diff").write_text(transaction.source_diff, encoding="utf-8")
    return transaction, _receipt(transaction)


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
    return failed, _receipt(failed)


def _validate_source(path: Path, kind: str) -> None:
    if kind == "onnx":
        validate_model_artifact("onnx", path)
        return
    if kind == "binary":
        if not path.is_file():
            raise ValueError(f"prepared binary artifact is unavailable: {path}")
        return
    content = path.read_text(encoding="utf-8")
    if kind == "python":
        ast.parse(content, filename=str(path))
    else:
        json.loads(content)


def _static_imports_resolve(project: Path, snapshot: SourceSnapshot) -> None:
    for source_file in snapshot.source_files:
        path = project / source_file.path
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
    gates = list(transaction.gates)
    history = list(transaction.state_history)
    try:
        for change in transaction.file_changes:
            _validate_source(project / change.path, change.kind)
        if transaction.artifact_kind != "model-artifact":
            _static_imports_resolve(project, _load_artifact(Path(transaction.artifact_path))[1])
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
    snapshot = _load_artifact(Path(transaction.artifact_path))[1]
    try:
        observed_bundle = _analyze_at(project, snapshot)
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

    original, _, original_evidence = _load_artifact(Path(transaction.artifact_path))
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
    gates.append(
        _gate(
            "F-graph-delta",
            True,
            "Expected and observed Graph Delta match exactly and the operation oracle passed.",
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
            "test_results": test_results,
        }
    )
    save_transaction(verified)
    return verified, _receipt(verified)


def _atomic_replace(path: Path, content: bytes) -> None:
    mode = path.stat().st_mode
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.chmod(mode)
    temporary.replace(path)


def commit_transaction(path: Path) -> tuple[SourceTransaction, TransactionReceipt]:
    transaction = load_transaction(path)
    if transaction.state is not TransactionState.REVIEW_READY:
        raise ValueError(f"only review-ready transactions can be committed, got {transaction.state.value}")
    _, snapshot, _ = _load_artifact(Path(transaction.artifact_path))
    try:
        _validate_snapshot(snapshot)
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

    originals: dict[Path, bytes] = {}
    try:
        for change in transaction.file_changes:
            original = Path(transaction.original_project_root) / change.path
            prepared = Path(transaction.temporary_project_root) / change.path
            originals[original] = original.read_bytes()
            _atomic_replace(original, prepared.read_bytes())
        committed_bundle = _analyze_at(Path(transaction.original_project_root), snapshot)
        original_architecture, _, original_evidence = _load_artifact(Path(transaction.artifact_path))
        committed_delta = graph_delta(
            original_architecture,
            committed_bundle.architecture,
            original_evidence,
            committed_bundle.evidence,
        )
        if committed_delta != transaction.expected_delta:
            raise ValueError("committed source did not reproduce the verified Graph Delta")
    except Exception as error:  # noqa: BLE001
        for original, content in originals.items():
            _atomic_replace(original, content)
        return _fail(
            transaction,
            _gate("F-atomic-commit", False, "Commit passed.", "Atomic commit failed and was rolled back."),
            _diagnostic("ATOMIC_COMMIT_FAILED", str(error)),
        )

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
    return committed, _receipt(committed, source_writes=True)


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
    return discarded, _receipt(discarded)
