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
from dataclasses import dataclass
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
from archcanvas_core.architecture_v2 import ExactArchitectureIRV2
from archcanvas_core.builtin_registry import BuiltinModuleRegistry
from archcanvas_core.models import (
    ArchitectureIR,
    Diagnostic,
    EvidenceKind,
    EvidenceRecord,
    FileChange,
    FreeformSourcePatch,
    GateResult,
    SemanticParameterPatch,
    SemanticStructuralPatch,
    SourceAnchor,
    SourceSnapshot,
    SourceTransaction,
    TransactionBaseBlob,
    TransactionReceipt,
    TransactionState,
)
from archcanvas_core.source_v2 import AnalysisInputManifest, ProjectManifest, SourceCorpus
from archcanvas_core.validation import validate_architecture
from archcanvas_engine.source_blob_store import SourceBlobStore
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
from .store import load_transaction, save_transaction
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
    return TransactionReceipt(
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
    )


@dataclass(frozen=True)
class _LoadedArtifact:
    path: Path
    architecture: ArchitectureIR
    snapshot: SourceSnapshot
    evidence: list[EvidenceRecord]
    project_manifest: ProjectManifest | None = None
    source_corpus: SourceCorpus | None = None
    analysis_input: AnalysisInputManifest | None = None
    exact_ir: ExactArchitectureIRV2 | None = None

    @property
    def is_v2(self) -> bool:
        return self.source_corpus is not None


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
    analysis_input = AnalysisInputManifest.model_validate_json(
        v2_paths["analysis_input"].read_text(encoding="utf-8")
    )
    exact_ir = ExactArchitectureIRV2.model_validate_json(
        v2_paths["exact_ir"].read_text(encoding="utf-8")
    )
    corpus_digest = source_corpus.source_corpus_digest
    if (
        analysis_input.source_corpus_digest != corpus_digest
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
        artifact,
        architecture,
        snapshot,
        evidence,
        project_manifest,
        source_corpus,
        analysis_input,
        exact_ir,
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
        return frontend.compatibility
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
    loaded = _load_artifact(artifact)
    architecture = loaded.architecture
    snapshot = loaded.snapshot
    evidence = loaded.evidence
    if architecture.framework != snapshot.framework:
        raise ValueError("architecture and snapshot framework bindings do not match")
    artifact_kind = transaction_artifact_kind(architecture.framework)
    _validate_snapshot(loaded)
    project = _working_project(loaded)
    node = next((item for item in architecture.nodes if item.node_id == request.target_node_id), None)
    if node is None:
        raise ValueError(f"target node is not present in Exact IR: {request.target_node_id}")
    seed = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    transaction_id = f"transaction:{_sha256((seed + datetime.now(UTC).isoformat()).encode())[:16]}"
    workspace = workspace.resolve()
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
        source_anchor=source_anchor,
        base_source_corpus_digest=(
            loaded.source_corpus.source_corpus_digest if loaded.source_corpus else None
        ),
        base_analysis_input_digest=(
            loaded.analysis_input.analysis_input_digest if loaded.analysis_input else None
        ),
        base_registry_digest=(
            loaded.analysis_input.registry_digest if loaded.analysis_input else None
        ),
        base_exact_ir_digest=(loaded.exact_ir.exact_ir_digest if loaded.exact_ir else None),
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
    _validate_snapshot(loaded)
    project = _working_project(loaded)
    snapshot_files = {item.path: item for item in snapshot.source_files}
    seed = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    transaction_id = f"transaction:{_sha256((seed + datetime.now(UTC).isoformat()).encode())[:16]}"
    workspace = workspace.resolve()
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
            base_source_corpus_digest=(
                loaded.source_corpus.source_corpus_digest if loaded.source_corpus else None
            ),
            base_analysis_input_digest=(
                loaded.analysis_input.analysis_input_digest if loaded.analysis_input else None
            ),
            base_registry_digest=(
                loaded.analysis_input.registry_digest if loaded.analysis_input else None
            ),
            base_exact_ir_digest=(loaded.exact_ir.exact_ir_digest if loaded.exact_ir else None),
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
        "base_source_corpus_digest": (
            artifact.source_corpus.source_corpus_digest if artifact.source_corpus else None
        ),
        "base_analysis_input_digest": (
            artifact.analysis_input.analysis_input_digest if artifact.analysis_input else None
        ),
        "base_registry_digest": (
            artifact.analysis_input.registry_digest if artifact.analysis_input else None
        ),
        "base_exact_ir_digest": artifact.exact_ir.exact_ir_digest if artifact.exact_ir else None,
    }
    for field, value in expected.items():
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

    originals: dict[Path, bytes] = {}
    try:
        for change in transaction.file_changes:
            original = Path(transaction.original_project_root) / change.path
            prepared = Path(transaction.temporary_project_root) / change.path
            originals[original] = original.read_bytes()
            _atomic_replace(original, prepared.read_bytes())
        committed_bundle = _analyze_at(
            Path(transaction.original_project_root),
            artifact,
            Path(transaction.workspace)
            / "transactions"
            / transaction.transaction_id
            / "analysis-commit",
        )
        original_architecture = artifact.architecture
        original_evidence = artifact.evidence
        committed_delta = graph_delta(
            original_architecture,
            committed_bundle.architecture,
            original_evidence,
            committed_bundle.evidence,
        )
        if committed_delta != transaction.expected_delta:
            expected_payload = transaction.expected_delta.model_dump(mode="json")
            committed_payload = committed_delta.model_dump(mode="json")
            mismatched_fields = sorted(
                key
                for key in expected_payload
                if expected_payload[key] != committed_payload[key]
            )
            raise ValueError(
                "committed source did not reproduce the verified Graph Delta; "
                f"mismatched fields: {', '.join(mismatched_fields)}"
            )
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
