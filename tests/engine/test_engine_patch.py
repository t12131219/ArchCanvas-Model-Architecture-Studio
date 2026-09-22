from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from archcanvas_core.models.engine import (
    EngineEnvironment,
    EngineOperation,
    EngineRequest,
    OpenProjectCommand,
    PatchCommand,
    PatchRuntimeProfile,
)
from archcanvas_core.models.patch import InsertLayerNormPatch, PatchSet
from archcanvas_core.models.runtime import (
    RuntimeEnvironment,
    RuntimeNodeObservation,
    RuntimeProviderId,
    RuntimeTensorInput,
    RuntimeTraceResult,
    TraceFailureCode,
    TraceRequest,
    TraceStatus,
)
from archcanvas_engine.service import ArchCanvasEngine
from archcanvas_python.fixture_analyzer import analyze_transformer_fixture
from archcanvas_pytorch.static import PyTorchStaticAdapter

ROOT = Path(__file__).resolve().parents[2]


def _project_copy(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    shutil.copyfile(ROOT / "fixtures/transformer_set_parameter_v1/source/before/model.py", root / "model.py")
    return root


def _analyzer(raw: bytes):
    source, architecture = analyze_transformer_fixture(raw)
    return (
        source.model_copy(update={"project_id": "project:stage7-fixture"}),
        architecture.model_copy(update={"project_id": "project:stage7-fixture"}),
    )


def _open(root: Path) -> OpenProjectCommand:
    import sys

    return OpenProjectCommand(
        project_id="project:stage7-fixture",
        approved_root=str(root),
        entrypoint="model.py:EncoderModel",
        environment=EngineEnvironment(python_executable=sys.executable, environment_name="TFB_py311"),
    )


def _patch_set(analysis) -> PatchSet:
    node = next(node for node in analysis.architecture.nodes if node.node_id.endswith(".layers"))
    parameter = next(parameter for parameter in node.parameters if parameter.name == "num_heads")
    anchor_id = next(anchor for anchor in node.source_anchor_ids if anchor.endswith(".constructor"))
    return PatchSet.model_validate(
        {
            "patch_set_id": "patchset:stage7-num-heads",
            "project_id": "project:stage7-fixture",
            "base_source_revision": analysis.source.file_revisions["model.py"],
            "created_at": datetime(2026, 9, 22, tzinfo=UTC),
            "created_by": "user",
            "patches": [
                {
                    "patch_id": "patch:stage7-num-heads",
                    "target": {"node_id": node.node_id, "parameter": parameter.name, "anchor_id": anchor_id},
                    "before": 8,
                    "after": 16,
                    "anchor_content_fingerprint": next(
                        anchor.content_fingerprint for anchor in analysis.source.anchors if anchor.anchor_id == anchor_id
                    ),
                    "expected_delta": {
                        "required_parameter_changes": [
                            {"node_id": node.node_id, "parameter": parameter.name, "before": 8, "after": 16}
                        ],
                        "allowed_node_additions": [], "allowed_node_removals": [], "allowed_node_modifications": [],
                        "allowed_edge_additions": [], "allowed_edge_removals": [], "allowed_edge_modifications": [],
                        "require_identity_retention": True,
                    },
                }
            ],
        }
    )


def _failed_runtime_result(request: TraceRequest) -> RuntimeTraceResult:
    return RuntimeTraceResult(
        trace_id=f"trace:{request.request_id.removeprefix('trace-request:')}",
        request_id=request.request_id,
        provider=request.provider,
        source_revision=request.source_revision,
        status=TraceStatus.FAILED,
        failure_code=TraceFailureCode.TRACE_UNSUPPORTED,
        message="deliberate candidate runtime failure",
        environment=RuntimeEnvironment(
            python_executable=request.python_executable,
            python_version=None,
            torch_version=None,
            cuda_version=None,
            device=None,
            network_policy=request.network_policy,
            network_enforcement="best_effort",
            environment_name=request.environment_name,
            dependency_lockfile=request.dependency_lockfile,
        ),
        observations=[],
        coverage_gaps=["deliberate-test-failure"],
        elapsed_ms=0,
        peak_memory_bytes=None,
        worker_exit_code=0,
        stdout="",
        stderr="",
        stderr_truncated=False,
    )


def _successful_runtime_result(request: TraceRequest) -> RuntimeTraceResult:
    return RuntimeTraceResult(
        trace_id=f"trace:{request.request_id.removeprefix('trace-request:')}",
        request_id=request.request_id,
        provider=request.provider,
        source_revision=request.source_revision,
        status=TraceStatus.SUCCEEDED,
        failure_code=None,
        message=None,
        environment=RuntimeEnvironment(
            python_executable=request.python_executable,
            python_version=None,
            torch_version=None,
            cuda_version=None,
            device=None,
            network_policy=request.network_policy,
            network_enforcement="best_effort",
            environment_name=request.environment_name,
            dependency_lockfile=request.dependency_lockfile,
        ),
        observations=[],
        coverage_gaps=[],
        elapsed_ms=0,
        peak_memory_bytes=None,
        worker_exit_code=0,
        stdout="",
        stderr="",
        stderr_truncated=False,
    )


def _successful_structural_runtime_result(request: TraceRequest) -> RuntimeTraceResult:
    result = _successful_runtime_result(request)
    return result.model_copy(update={
        "observations": [
            RuntimeNodeObservation(target=target, operation="call_module", input_tensor=None, output_tensor=None)
            for target in ("embedding", "layers.0", "insert_norm", "norm", "head")
        ]
    })


def _structural_project_copy(tmp_path: Path) -> Path:
    root = tmp_path / "structural-project"
    root.mkdir()
    shutil.copyfile(ROOT / "fixtures/transformer_static_v1/source/model.py", root / "model.py")
    return root


def _structural_analyzer(raw: bytes):
    return PyTorchStaticAdapter().analyze(
        raw,
        project_id="project:stage8-fixture",
        relative_file="model.py",
        entrypoint="model.py:EncoderModel",
    )


def _structural_patch_set(source, architecture) -> PatchSet:
    source_node = next(node for node in architecture.nodes if node.display_name == "layers")
    target_node = next(node for node in architecture.nodes if node.display_name == "norm")
    constructor = next(anchor for anchor in source.anchors if anchor.anchor_id.endswith(".norm.constructor"))
    forward = next(anchor for anchor in source.anchors if anchor.anchor_id.endswith(".layers.norm"))
    patch = InsertLayerNormPatch(
        patch_id="patch:stage8-insert-norm",
        source_node_id=source_node.node_id,
        target_node_id=target_node.node_id,
        constructor_anchor_id=constructor.anchor_id,
        forward_anchor_id=forward.anchor_id,
        attribute_name="insert_norm",
        normalized_shape=256,
        constructor_anchor_content_fingerprint=constructor.content_fingerprint,
        forward_anchor_content_fingerprint=forward.content_fingerprint,
        expected_delta={
            "allowed_node_additions": ["node:encodermodel.insert_norm"],
            "allowed_node_removals": [], "allowed_node_modifications": [],
            "allowed_edge_additions": ["edge:layers->insert_norm:data", "edge:insert_norm->norm:data"],
            "allowed_edge_removals": ["edge:layers->norm:data"], "allowed_edge_modifications": [],
            "require_identity_retention": True,
        },
    )
    return PatchSet(
        patch_set_id="patchset:stage8-insert-norm",
        project_id="project:stage8-fixture",
        base_source_revision=source.file_revisions["model.py"],
        created_at=datetime(2026, 9, 22, tzinfo=UTC),
        created_by="user",
        patches=[patch],
    )


def test_engine_patch_plan_validate_and_commit_reanalyzes_without_fixture_fallback(tmp_path: Path) -> None:
    root = _project_copy(tmp_path)
    source_path = root / "model.py"
    source_before = source_path.read_bytes()
    engine = ArchCanvasEngine(tmp_path / "cache", patch_analyzers={"project:stage7-fixture": _analyzer})
    opened = engine.open_project(_open(root))
    assert "d_model" not in opened.patch_parameter_names
    assert {"num_heads", "dropout", "activation"}.issubset(opened.patch_parameter_names)
    analysis = engine.analyze_project(opened.project_id)
    fixture_source, fixture_ir = _analyzer(source_before)
    engine._repository.save_analysis(analysis.manifest, fixture_source, fixture_ir, analysis.publication, analysis.scene, "<svg/>")
    analysis = analysis.model_copy(update={"source": fixture_source, "architecture": fixture_ir})
    patch_set = _patch_set(analysis)
    command = PatchCommand(operation=EngineOperation.PLAN_PATCH, project_id=opened.project_id, patch_set=patch_set)

    missing_plan = engine.dispatch(
        EngineRequest(
            request_id="engine-request:stage7-commit-without-plan",
            command=command.model_copy(update={"operation": EngineOperation.COMMIT_PATCH}),
        )
    )
    assert missing_plan.status == "rejected"
    assert missing_plan.error is not None and missing_plan.error.code == "PATCH_PLAN_NOT_FOUND"

    planned = engine.dispatch(EngineRequest(request_id="engine-request:stage7-plan", command=command))
    assert planned.status == "succeeded", planned.error
    assert planned.result is not None and planned.result.kind == "patch_planned"
    assert "nhead=8" in planned.result.candidate_diff
    assert "nhead=16" in planned.result.candidate_diff
    assert source_path.read_bytes() == source_before

    not_validated = engine.dispatch(
        EngineRequest(
            request_id="engine-request:stage7-commit-without-validation",
            command=command.model_copy(update={"operation": EngineOperation.COMMIT_PATCH}),
        )
    )
    assert not_validated.status == "rejected"
    assert not_validated.error is not None and not_validated.error.code == "PATCH_NOT_VALIDATED"
    assert source_path.read_bytes() == source_before

    mismatched = patch_set.model_copy(
        update={
            "patches": [patch_set.patches[0].model_copy(update={
                "after": 32,
                "expected_delta": patch_set.patches[0].expected_delta.model_copy(update={
                    "required_parameter_changes": [
                        patch_set.patches[0].expected_delta.required_parameter_changes[0].model_copy(update={"after": 32})
                    ]
                }),
            })],
        }
    )
    mismatch_response = engine.dispatch(
        EngineRequest(
            request_id="engine-request:stage7-plan-mismatch",
            command=command.model_copy(update={"operation": EngineOperation.VALIDATE_PATCH, "patch_set": mismatched}),
        )
    )
    assert mismatch_response.status == "rejected"
    assert mismatch_response.error is not None and mismatch_response.error.code == "PATCH_PLAN_MISMATCH"
    assert source_path.read_bytes() == source_before

    validated = engine.dispatch(
        EngineRequest(
            request_id="engine-request:stage7-validate",
            command=command.model_copy(update={"operation": EngineOperation.VALIDATE_PATCH}),
        )
    )
    assert validated.status == "succeeded"
    assert validated.result is not None and validated.result.kind == "patch_validated"
    assert validated.result.confirmation_id is not None
    assert source_path.read_bytes() == source_before

    invalid_confirmation = engine.dispatch(
        EngineRequest(
            request_id="engine-request:stage7-invalid-confirmation",
            command=command.model_copy(update={
                "operation": EngineOperation.COMMIT_PATCH,
                "confirmation_id": "confirmation:incorrect",
            }),
        )
    )
    assert invalid_confirmation.status == "rejected"
    assert invalid_confirmation.error is not None and invalid_confirmation.error.code == "PATCH_CONFIRMATION_INVALID"
    assert source_path.read_bytes() == source_before

    restarted = ArchCanvasEngine(tmp_path / "cache", patch_analyzers={"project:stage7-fixture": _analyzer})
    restarted_commit = restarted.dispatch(
        EngineRequest(
            request_id="engine-request:stage7-restarted-commit",
            command=command.model_copy(update={
                "operation": EngineOperation.COMMIT_PATCH,
                "confirmation_id": validated.result.confirmation_id,
            }),
        )
    )
    assert restarted_commit.status == "rejected"
    assert restarted_commit.error is not None and restarted_commit.error.code == "PATCH_PLAN_NOT_FOUND"
    assert source_path.read_bytes() == source_before

    committed = engine.dispatch(
        EngineRequest(
            request_id="engine-request:stage7-commit",
            command=command.model_copy(update={
                "operation": EngineOperation.COMMIT_PATCH,
                "confirmation_id": validated.result.confirmation_id,
            }),
        )
    )
    assert committed.status == "succeeded"
    assert committed.result is not None and committed.result.kind == "patch_committed"
    assert committed.result.analysis is not None
    assert b"nhead=16" in source_path.read_bytes()
    event_kinds = {event.kind for event in engine._repository.load_events(opened.project_id)}
    assert {"patch_planned", "patch_validated", "patch_committed", "patch_rejected"} <= event_kinds


def test_engine_rolls_back_source_when_post_commit_analysis_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project_copy(tmp_path)
    source_path = root / "model.py"
    source_before = source_path.read_bytes()
    engine = ArchCanvasEngine(tmp_path / "cache", patch_analyzers={"project:stage7-fixture": _analyzer})
    opened = engine.open_project(_open(root))
    analysis = engine.analyze_project(opened.project_id)
    fixture_source, fixture_ir = _analyzer(source_before)
    engine._repository.save_analysis(analysis.manifest, fixture_source, fixture_ir, analysis.publication, analysis.scene, "<svg/>")
    patch_set = _patch_set(analysis.model_copy(update={"source": fixture_source, "architecture": fixture_ir}))
    command = PatchCommand(operation=EngineOperation.PLAN_PATCH, project_id=opened.project_id, patch_set=patch_set)
    assert engine.dispatch(EngineRequest(request_id="engine-request:stage7-rollback-plan", command=command)).status == "succeeded"
    validated = engine.dispatch(
        EngineRequest(
            request_id="engine-request:stage7-rollback-validate",
            command=command.model_copy(update={"operation": EngineOperation.VALIDATE_PATCH}),
        )
    )
    assert validated.status == "succeeded"
    assert validated.result is not None and validated.result.confirmation_id is not None

    original_analyze = engine.analyze_project

    def fail_analysis(project_id: str):
        original_analyze(project_id)
        raise RuntimeError("deliberate post-commit analysis failure")

    monkeypatch.setattr(engine, "analyze_project", fail_analysis)
    rolled_back = engine.dispatch(
        EngineRequest(
            request_id="engine-request:stage7-rollback-commit",
            command=command.model_copy(update={
                "operation": EngineOperation.COMMIT_PATCH,
                "confirmation_id": validated.result.confirmation_id,
            }),
        )
    )
    assert rolled_back.status == "rejected"
    assert rolled_back.error is not None
    assert rolled_back.error.code == "POST_COMMIT_ANALYSIS_FAILED_ROLLED_BACK"
    assert source_path.read_bytes() == source_before
    recovered_source, recovered_architecture, _, _ = engine.load_analysis(opened.project_id)
    assert recovered_source.file_revisions["model.py"] == fixture_source.file_revisions["model.py"]
    assert recovered_architecture.source_revision == fixture_ir.source_revision
    assert "patch_rolled_back" in {event.kind for event in engine._repository.load_events(opened.project_id)}


def test_engine_patch_rejects_unregistered_analyzer_and_stale_source(tmp_path: Path) -> None:
    root = _project_copy(tmp_path)
    engine = ArchCanvasEngine(tmp_path / "cache")
    opened = engine.open_project(_open(root))
    analysis = engine.analyze_project(opened.project_id)
    patch_set = _patch_set(analysis)
    command = PatchCommand(operation=EngineOperation.PLAN_PATCH, project_id=opened.project_id, patch_set=patch_set)

    unavailable = engine.dispatch(EngineRequest(request_id="engine-request:stage7-unavailable", command=command))
    assert unavailable.status == "rejected"
    assert unavailable.error is not None and unavailable.error.code == "PATCH_ANALYZER_UNAVAILABLE"

    engine.register_patch_analyzer(opened.project_id, _analyzer)
    source_path = root / "model.py"
    source_path.write_bytes(source_path.read_bytes() + b"\n# concurrent edit\n")
    stale = engine.dispatch(EngineRequest(request_id="engine-request:stage7-stale", command=command))
    assert stale.status == "rejected"
    assert stale.error is not None and stale.error.code == "PATCH_SOURCE_STALE"
    assert source_path.read_bytes().endswith(b"# concurrent edit\n")


def test_engine_runtime_validation_failure_keeps_approved_source_unchanged(tmp_path: Path) -> None:
    root = _project_copy(tmp_path)
    source_path = root / "model.py"
    source_before = source_path.read_bytes()
    worker_roots: list[Path] = []

    def fail_runtime(request: TraceRequest) -> RuntimeTraceResult:
        worker_root = Path(request.project_root)
        worker_roots.append(worker_root)
        assert worker_root != root
        assert b"nhead=16" in (worker_root / "model.py").read_bytes()
        return _failed_runtime_result(request)

    profile = PatchRuntimeProfile(
        inputs=[RuntimeTensorInput(shape=[2, 256], dtype="float32")],
        provider=RuntimeProviderId.TORCH_FX,
    )
    engine = ArchCanvasEngine(
        tmp_path / "cache",
        patch_analyzers={"project:stage7-fixture": _analyzer},
        patch_runtime_profiles={"project:stage7-fixture": profile},
        runtime_worker=fail_runtime,
    )
    opened = engine.open_project(_open(root))
    assert "d_model" in opened.patch_parameter_names
    analysis = engine.analyze_project(opened.project_id)
    fixture_source, fixture_ir = _analyzer(source_before)
    engine._repository.save_analysis(analysis.manifest, fixture_source, fixture_ir, analysis.publication, analysis.scene, "<svg/>")
    patch_set = _patch_set(analysis.model_copy(update={"source": fixture_source, "architecture": fixture_ir}))
    command = PatchCommand(operation=EngineOperation.PLAN_PATCH, project_id=opened.project_id, patch_set=patch_set)
    assert engine.dispatch(EngineRequest(request_id="engine-request:stage7-runtime-plan", command=command)).status == "succeeded"

    rejected = engine.dispatch(
        EngineRequest(
            request_id="engine-request:stage7-runtime-validate",
            command=command.model_copy(update={"operation": EngineOperation.VALIDATE_PATCH}),
        )
    )
    assert rejected.status == "rejected"
    assert rejected.error is not None and rejected.error.code == "PATCH_RUNTIME_VALIDATION_FAILED"
    assert source_path.read_bytes() == source_before
    assert len(worker_roots) == 1
    assert not worker_roots[0].exists()
    assert "patch_rejected" in {event.kind for event in engine._repository.load_events(opened.project_id)}


def test_engine_runtime_validation_success_is_required_before_commit(tmp_path: Path) -> None:
    root = _project_copy(tmp_path)
    source_path = root / "model.py"
    source_before = source_path.read_bytes()
    profile = PatchRuntimeProfile(
        inputs=[RuntimeTensorInput(shape=[2, 256], dtype="float32")],
        provider=RuntimeProviderId.TORCH_FX,
    )
    engine = ArchCanvasEngine(
        tmp_path / "cache",
        patch_analyzers={"project:stage7-fixture": _analyzer},
        patch_runtime_profiles={"project:stage7-fixture": profile},
        runtime_worker=_successful_runtime_result,
    )
    opened = engine.open_project(_open(root))
    analysis = engine.analyze_project(opened.project_id)
    fixture_source, fixture_ir = _analyzer(source_before)
    engine._repository.save_analysis(analysis.manifest, fixture_source, fixture_ir, analysis.publication, analysis.scene, "<svg/>")
    patch_set = _patch_set(analysis.model_copy(update={"source": fixture_source, "architecture": fixture_ir}))
    command = PatchCommand(operation=EngineOperation.PLAN_PATCH, project_id=opened.project_id, patch_set=patch_set)
    assert engine.dispatch(EngineRequest(request_id="engine-request:stage7-runtime-success-plan", command=command)).status == "succeeded"

    validated = engine.dispatch(
        EngineRequest(
            request_id="engine-request:stage7-runtime-success-validate",
            command=command.model_copy(update={"operation": EngineOperation.VALIDATE_PATCH}),
        )
    )
    assert validated.status == "succeeded"
    assert validated.result is not None and validated.result.confirmation_id is not None
    assert validated.result.runtime_validation is not None
    assert validated.result.runtime_validation.status is TraceStatus.SUCCEEDED
    assert source_path.read_bytes() == source_before

    committed = engine.dispatch(
        EngineRequest(
            request_id="engine-request:stage7-runtime-success-commit",
            command=command.model_copy(update={
                "operation": EngineOperation.COMMIT_PATCH,
                "confirmation_id": validated.result.confirmation_id,
            }),
        )
    )
    assert committed.status == "succeeded"
    assert b"nhead=16" in source_path.read_bytes()


def test_engine_runtime_validation_rejects_symlinked_candidate_tree(tmp_path: Path) -> None:
    root = _project_copy(tmp_path)
    source_path = root / "model.py"
    source_before = source_path.read_bytes()
    (root / "outside-link.py").symlink_to(source_path)
    profile = PatchRuntimeProfile(
        inputs=[RuntimeTensorInput(shape=[2, 256], dtype="float32")],
        provider=RuntimeProviderId.TORCH_FX,
    )
    engine = ArchCanvasEngine(
        tmp_path / "cache",
        patch_analyzers={"project:stage7-fixture": _analyzer},
        patch_runtime_profiles={"project:stage7-fixture": profile},
        runtime_worker=_failed_runtime_result,
    )
    opened = engine.open_project(_open(root))
    analysis = engine.analyze_project(opened.project_id)
    fixture_source, fixture_ir = _analyzer(source_before)
    engine._repository.save_analysis(analysis.manifest, fixture_source, fixture_ir, analysis.publication, analysis.scene, "<svg/>")
    patch_set = _patch_set(analysis.model_copy(update={"source": fixture_source, "architecture": fixture_ir}))
    command = PatchCommand(operation=EngineOperation.PLAN_PATCH, project_id=opened.project_id, patch_set=patch_set)
    assert engine.dispatch(EngineRequest(request_id="engine-request:stage7-symlink-plan", command=command)).status == "succeeded"

    rejected = engine.dispatch(
        EngineRequest(
            request_id="engine-request:stage7-symlink-validate",
            command=command.model_copy(update={"operation": EngineOperation.VALIDATE_PATCH}),
        )
    )
    assert rejected.status == "rejected"
    assert rejected.error is not None and rejected.error.code == "PATCH_RUNTIME_SYMLINK_UNSUPPORTED"
    assert source_path.read_bytes() == source_before


def test_engine_structural_splice_requires_runtime_profile_and_commits_after_shape_validation(
    tmp_path: Path,
) -> None:
    root = _structural_project_copy(tmp_path)
    source_path = root / "model.py"
    source_before = source_path.read_bytes()
    profile = PatchRuntimeProfile(
        inputs=[RuntimeTensorInput(shape=[2, 4], dtype="int64")],
        provider=RuntimeProviderId.TORCH_FX,
    )
    engine = ArchCanvasEngine(
        tmp_path / "cache",
        patch_analyzers={"project:stage8-fixture": _structural_analyzer},
        patch_runtime_profiles={"project:stage8-fixture": profile},
        runtime_worker=_successful_structural_runtime_result,
    )
    opened = engine.open_project(_open(root).model_copy(update={"project_id": "project:stage8-fixture"}))
    analysis = engine.analyze_project(opened.project_id)
    source, architecture = _structural_analyzer(source_before)
    engine._repository.save_analysis(analysis.manifest, source, architecture, analysis.publication, analysis.scene, "<svg/>")
    patch_set = _structural_patch_set(source, architecture)
    command = PatchCommand(operation=EngineOperation.PLAN_PATCH, project_id=opened.project_id, patch_set=patch_set)

    planned = engine.dispatch(EngineRequest(request_id="engine-request:stage8-plan", command=command))
    assert planned.status == "succeeded", planned.error
    assert planned.result is not None and planned.result.candidate_diff.count("@@ ") == 2
    assert source_path.read_bytes() == source_before

    validated = engine.dispatch(
        EngineRequest(
            request_id="engine-request:stage8-validate",
            command=command.model_copy(update={"operation": EngineOperation.VALIDATE_PATCH}),
        )
    )
    assert validated.status == "succeeded", validated.error
    assert validated.result is not None and validated.result.confirmation_id is not None
    assert validated.result.runtime_validation is not None

    committed = engine.dispatch(
        EngineRequest(
            request_id="engine-request:stage8-commit",
            command=command.model_copy(update={
                "operation": EngineOperation.COMMIT_PATCH,
                "confirmation_id": validated.result.confirmation_id,
            }),
        )
    )
    assert committed.status == "succeeded", committed.error
    assert b"self.insert_norm = nn.LayerNorm(256)" in source_path.read_bytes()
    assert b"x = self.insert_norm(x)" in source_path.read_bytes()


def test_engine_structural_splice_rejects_validation_without_runtime_profile(tmp_path: Path) -> None:
    root = _structural_project_copy(tmp_path)
    source_path = root / "model.py"
    source_before = source_path.read_bytes()
    engine = ArchCanvasEngine(tmp_path / "cache", patch_analyzers={"project:stage8-fixture": _structural_analyzer})
    opened = engine.open_project(_open(root).model_copy(update={"project_id": "project:stage8-fixture"}))
    analysis = engine.analyze_project(opened.project_id)
    source, architecture = _structural_analyzer(source_before)
    engine._repository.save_analysis(analysis.manifest, source, architecture, analysis.publication, analysis.scene, "<svg/>")
    command = PatchCommand(
        operation=EngineOperation.PLAN_PATCH,
        project_id=opened.project_id,
        patch_set=_structural_patch_set(source, architecture),
    )
    assert engine.dispatch(EngineRequest(request_id="engine-request:stage8-missing-runtime-plan", command=command)).status == "succeeded"
    rejected = engine.dispatch(
        EngineRequest(
            request_id="engine-request:stage8-missing-runtime-validate",
            command=command.model_copy(update={"operation": EngineOperation.VALIDATE_PATCH}),
        )
    )
    assert rejected.status == "rejected"
    assert rejected.error is not None and rejected.error.code == "PATCH_RUNTIME_VALIDATION_REQUIRED"
    assert source_path.read_bytes() == source_before
