from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from archcanvas_adapters import adapter_capabilities, analyze_with_adapter
from archcanvas_core.models import SemanticParameterPatch, SemanticStructuralPatch
from archcanvas_core.validation import validate_architecture
from archcanvas_engine.cli import main
from archcanvas_publication import (
    build_scene,
    build_visual_spec,
    compile_views,
    validate_geometry,
    validate_publication,
)
from archcanvas_runtime import trace_runtime
from archcanvas_transactions import commit_transaction, prepare_transaction, verify_transaction

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = [
    ("keras", "keras_subclass", "model:TemporalGate"),
    ("keras", "keras_functional", "model:build_network"),
    ("jax", "jax_flax", "model:ResidualMixer"),
    ("jax", "jax_function", "model:residual_projection"),
    ("keras", "keras_multi_io", "model:build_multi_io"),
    ("jax", "jax_scan", "model:recurrent_scan"),
    ("jax", "jax_prng", "model:keyed_mask"),
    ("onnx", "onnx_residual", "model.onnx"),
]


def _bundle(framework: str, fixture_name: str, entrypoint: str):
    fixture = ROOT / "fixtures" / "cross_framework" / fixture_name
    config = fixture / "config.json"
    return analyze_with_adapter(
        fixture,
        entrypoint,
        "inference",
        "eval",
        config.read_bytes() if config.is_file() else b"{}",
        config if config.is_file() else None,
        framework=framework,
        pattern_packs_enabled=False,
    )


@pytest.mark.parametrize(("framework", "fixture_name", "entrypoint"), FIXTURES)
def test_cross_framework_static_ir_publication_and_geometry(
    framework: str,
    fixture_name: str,
    entrypoint: str,
) -> None:
    if framework == "onnx" and next(
        item for item in adapter_capabilities() if item.framework == "onnx"
    ).status == "unavailable":
        pytest.skip("optional ONNX dependency is not installed")
    bundle = _bundle(framework, fixture_name, entrypoint)
    assert bundle.snapshot.framework == framework
    assert bundle.architecture.framework == framework
    gates, diagnostics = validate_architecture(
        bundle.architecture, bundle.evidence, bundle.snapshot
    )
    assert all(gate.status == "passed" for gate in gates if gate.status != "skipped")
    assert not diagnostics
    views = compile_views(bundle.architecture)
    publication_gates, publication_diagnostics = validate_publication(
        bundle.architecture, views
    )
    assert all(gate.status == "passed" for gate in publication_gates)
    assert not publication_diagnostics
    assert len({view.layout_family for view in views}) == 1
    assert views[0].layout_family in {"single-lane", "dual-lane"}
    for view in views:
        geometry_gate, geometry_diagnostics = validate_geometry(
            build_scene(view, build_visual_spec(view))
        )
        assert geometry_gate.status == "passed"
        assert not geometry_diagnostics


def test_python_source_adapters_do_not_require_framework_packages() -> None:
    capabilities = {item.framework: item for item in adapter_capabilities()}
    assert capabilities["python"].static_analysis is True
    assert capabilities["python"].runtime_evidence is False
    assert capabilities["keras"].static_analysis is True
    assert capabilities["jax"].static_analysis is True
    assert "keras" in capabilities["keras"].required_packages
    assert "jax" in capabilities["jax"].required_packages
    assert capabilities["keras"].capability_status["static"] == "partial"
    assert capabilities["jax"].parameter_transactions is True


def test_capability_matrix_is_explicit_per_framework_form() -> None:
    capabilities = {item.framework: item for item in adapter_capabilities()}
    expected_forms = {
        "pytorch": {"form:pytorch-module-forward"},
        "keras": {
            "form:keras-subclass-call",
            "form:keras-functional",
            "form:keras-custom-layer",
        },
        "jax": {"form:jax-pure-function", "form:flax-module", "form:jax-transformed"},
        "onnx": {
            "form:onnx-standard-op",
            "form:onnx-external-data",
            "form:onnx-custom-op",
        },
    }
    for framework, identifiers in expected_forms.items():
        forms = capabilities[framework].forms
        assert {form.form_id for form in forms} == identifiers
        assert all(form.static and form.runtime and form.artifact_commit for form in forms)
    custom_onnx = next(
        form for form in capabilities["onnx"].forms if form.form_id == "form:onnx-custom-op"
    )
    assert custom_onnx.runtime == "unavailable"
    assert custom_onnx.structural_transaction == "unavailable"


def test_pytorch_registry_targets_match_the_verified_environment() -> None:
    torch = pytest.importorskip("torch")
    capability = next(item for item in adapter_capabilities() if item.framework == "pytorch")
    assert capability.supported_targets == (
        ["cpu", "cuda"] if torch.cuda.is_available() else ["cpu"]
    )


@pytest.mark.parametrize(
    ("framework", "fixture_name", "entrypoint"),
    [("keras", "keras_subclass", "model:TemporalGate"), ("jax", "jax_function", "model:residual_projection")],
)
def test_cli_cross_framework_analysis(
    framework: str,
    fixture_name: str,
    entrypoint: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = ROOT / "fixtures" / "cross_framework" / fixture_name
    out = tmp_path / framework
    args = [
        "analyze",
        "--framework",
        framework,
        "--project",
        str(fixture),
        "--entry",
        entrypoint,
        "--task",
        "inference",
        "--mode",
        "eval",
        "--out",
        str(out),
        "--no-pattern-packs",
        "--json",
    ]
    config = fixture / "config.json"
    if config.is_file():
        args[7:7] = ["--config", str(config)]
    assert main(args) == 0
    receipt = json.loads(capsys.readouterr().out)
    architecture = json.loads((out / "architecture.json").read_text())
    assert receipt["details"]["framework"] == framework
    assert receipt["details"]["source_execution"] is False
    assert architecture["framework"] == framework


@pytest.mark.parametrize(("framework", "fixture_name", "entrypoint"), FIXTURES)
def test_cross_framework_runtime_replay_is_normalized_and_source_preserving(
    framework: str,
    fixture_name: str,
    entrypoint: str,
    tmp_path: Path,
) -> None:
    capability = next(item for item in adapter_capabilities() if item.framework == framework)
    if not capability.runtime_evidence:
        pytest.skip(f"optional {framework} runtime dependency is not installed")
    fixture = ROOT / "fixtures" / "cross_framework" / fixture_name
    bundle = _bundle(framework, fixture_name, entrypoint)
    analysis = tmp_path / fixture_name
    analysis.mkdir()
    artifact = analysis / "architecture.json"
    artifact.write_text(bundle.architecture.model_dump_json())
    (analysis / "source-snapshot.json").write_text(bundle.snapshot.model_dump_json())
    before = {
        path: path.read_bytes()
        for path in [artifact, analysis / "source-snapshot.json", *fixture.glob("*.py"), *fixture.glob("*.onnx")]
    }
    receipt = trace_runtime(artifact, fixture / "runtime-input.json", analysis)
    assert receipt.status == "ok", receipt.model_dump(mode="json")
    assert receipt.details["replay_runs"] == 2
    trace = json.loads((analysis / "runtime-trace.json").read_text())
    assert trace["framework"] == framework
    assert trace["environment"]["framework"] == framework
    context = trace["environment"]["runtime_context"]
    if framework == "keras":
        assert context["form"] in {"subclassed-model-call", "functional-builder"}
        assert context["custom_train_step_observed"] is False
    elif framework == "jax":
        assert context["form"] in {"flax-module", "pure-function"}
        assert len(context["static_args_digest"]) == 64
        assert context["output_pytree"]
    elif framework == "onnx":
        assert context["instrumentation_persisted"] is False
        assert context["artifact_members"] == ["model.onnx"]
    assert trace["observations"]
    assert trace["output_tensors"]
    if fixture_name == "keras_multi_io":
        assert context["input_structure"] == "mapping"
        assert context["output_count"] == 2
    if fixture_name == "jax_scan":
        assert "scan" in context["transform_primitives"]
    if fixture_name == "jax_prng":
        assert len(context["input_prng_digests"]["key"]) == 64
        assert context["static_args_digest"] != "0" * 64
    assert before == {path: path.read_bytes() for path in before}


def test_keras_config_parameter_transaction_reaches_review_ready(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = ROOT / "fixtures" / "cross_framework" / "keras_subclass"
    out = tmp_path / "analysis"
    assert main(
        [
            "analyze",
            "--framework",
            "keras",
            "--project",
            str(fixture),
            "--entry",
            "model:TemporalGate",
            "--config",
            str(fixture / "config.json"),
            "--task",
            "inference",
            "--mode",
            "eval",
            "--out",
            str(out),
            "--json",
        ]
    ) == 0
    capsys.readouterr()
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "patch_id": "patch:keras-width",
                "operation": "set_parameter",
                "artifact_path": str(out / "architecture.json"),
                "target_node_id": "node:input_projection",
                "parameter_name": "arg0",
                "new_value": 32,
            }
        )
    )
    assert main(
        [
            "patch",
            "prepare",
            str(request),
            "--workspace",
            str(tmp_path / "workspace"),
            "--json",
        ]
    ) == 0
    receipt = json.loads(capsys.readouterr().out)
    transaction = Path(receipt["artifacts"]["transaction"])
    assert main(["patch", "verify", str(transaction), "--json"]) == 0
    verified = json.loads(capsys.readouterr().out)
    assert verified["details"]["transaction_state"] == "review-ready"
    assert verified["details"]["source_writes"] is False


@pytest.mark.parametrize(
    ("framework", "fixture_name", "entrypoint", "target_node", "parameter", "config_key"),
    [
        (
            "keras", "keras_subclass", "model:TemporalGate",
            "node:input_projection", "arg0", "width",
        ),
        (
            "keras", "keras_functional", "model:build_network",
            "node:hidden", "arg0", None,
        ),
        (
            "jax", "jax_flax", "model:ResidualMixer",
            "node:residualmixer", "width", "width",
        ),
    ],
)
def test_cross_framework_config_transaction_commits_atomically(
    framework: str,
    fixture_name: str,
    entrypoint: str,
    target_node: str,
    parameter: str,
    config_key: str | None,
    tmp_path: Path,
) -> None:
    source = ROOT / "fixtures" / "cross_framework" / fixture_name
    project = tmp_path / "project"
    shutil.copytree(source, project)
    config = project / "config.json"
    bundle = analyze_with_adapter(
        project,
        entrypoint,
        "inference",
        "eval",
        config.read_bytes(),
        config,
        framework=framework,
        pattern_packs_enabled=False,
    )
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    artifact = analysis / "architecture.json"
    artifact.write_text(bundle.architecture.model_dump_json())
    (analysis / "source-snapshot.json").write_text(bundle.snapshot.model_dump_json())
    (analysis / "evidence-ledger.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in bundle.evidence])
    )
    request = SemanticParameterPatch(
        patch_id=f"patch:{framework}-config",
        artifact_path=str(artifact),
        target_node_id=target_node,
        parameter_name=parameter,
        new_value=20,
    )
    transaction, prepared = prepare_transaction(request, tmp_path / "workspace")
    assert prepared.status == "ok"
    transaction_path = (
        Path(transaction.workspace) / "transactions" / transaction.transaction_id / "transaction.json"
    )
    transaction, verified = verify_transaction(transaction_path)
    assert verified.status == "ok"
    assert transaction.state.value == "review-ready"
    transaction, committed = commit_transaction(transaction_path)
    assert committed.status == "ok"
    assert transaction.state.value == "committed"
    if config_key is not None:
        assert json.loads(config.read_text())[config_key] == 20
    else:
        assert "layers.Dense(20)(inputs)" in (project / "model.py").read_text()


def test_flax_module_field_transaction_commits_atomically(tmp_path: Path) -> None:
    source = ROOT / "fixtures" / "cross_framework" / "jax_flax"
    project = tmp_path / "project"
    shutil.copytree(source, project)
    config = project / "config.json"
    config.write_text(
        json.dumps(
            {
                "input_shapes": {
                    "signal": "[B,L,D]",
                    "context": "[B,L,D]",
                }
            }
        )
    )
    bundle = analyze_with_adapter(
        project,
        "model:ResidualMixer",
        "inference",
        "eval",
        config.read_bytes(),
        config,
        framework="jax",
        pattern_packs_enabled=False,
    )
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    artifact = analysis / "architecture.json"
    artifact.write_text(bundle.architecture.model_dump_json())
    (analysis / "source-snapshot.json").write_text(bundle.snapshot.model_dump_json())
    (analysis / "evidence-ledger.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in bundle.evidence])
    )
    request = SemanticParameterPatch(
        patch_id="patch:jax-module-field",
        artifact_path=str(artifact),
        target_node_id="node:residualmixer",
        parameter_name="width",
        new_value=20,
    )
    transaction, _ = prepare_transaction(request, tmp_path / "workspace")
    transaction_path = (
        Path(transaction.workspace) / "transactions" / transaction.transaction_id / "transaction.json"
    )
    transaction, verified = verify_transaction(transaction_path)
    assert verified.status == "ok"
    transaction, committed = commit_transaction(transaction_path)
    assert committed.status == "ok"
    assert "width: int = 20" in (project / "model.py").read_text()


@pytest.mark.parametrize(
    ("fixture_name", "entrypoint", "target_node"),
    [
        ("keras_subclass", "model:TemporalGate", "node:activation"),
        ("keras_functional", "model:build_network", "node:activated"),
    ],
)
def test_keras_activation_structural_transaction_commits_atomically(
    fixture_name: str,
    entrypoint: str,
    target_node: str,
    tmp_path: Path,
) -> None:
    source = ROOT / "fixtures" / "cross_framework" / fixture_name
    project = tmp_path / "project"
    shutil.copytree(source, project)
    config = project / "config.json"
    bundle = analyze_with_adapter(
        project,
        entrypoint,
        "inference",
        "eval",
        config.read_bytes(),
        config,
        framework="keras",
        pattern_packs_enabled=False,
    )
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    artifact = analysis / "architecture.json"
    artifact.write_text(bundle.architecture.model_dump_json())
    (analysis / "source-snapshot.json").write_text(bundle.snapshot.model_dump_json())
    (analysis / "evidence-ledger.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in bundle.evidence])
    )
    request = SemanticStructuralPatch(
        patch_id=f"patch:{fixture_name}-activation",
        operation="replace_activation",
        artifact_path=str(artifact),
        target_node_id=target_node,
        parameters={"replacement": "ReLU"},
    )
    transaction, prepared = prepare_transaction(request, tmp_path / "workspace")
    assert prepared.status == "ok"
    transaction_path = (
        Path(transaction.workspace) / "transactions" / transaction.transaction_id / "transaction.json"
    )
    transaction, verified = verify_transaction(transaction_path)
    assert verified.status == "ok"
    transaction, committed = commit_transaction(transaction_path)
    assert committed.status == "ok"
    changed_source = (project / "model.py").read_text()
    assert "layers.Activation" in changed_source and "'relu'" in changed_source


def test_keras_subclass_normalization_insertion_commits_atomically(tmp_path: Path) -> None:
    source = ROOT / "fixtures" / "cross_framework" / "keras_subclass"
    project = tmp_path / "project"
    shutil.copytree(source, project)
    config = project / "config.json"
    bundle = analyze_with_adapter(
        project,
        "model:TemporalGate",
        "inference",
        "eval",
        config.read_bytes(),
        config,
        framework="keras",
        pattern_packs_enabled=False,
    )
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    artifact = analysis / "architecture.json"
    artifact.write_text(bundle.architecture.model_dump_json())
    (analysis / "source-snapshot.json").write_text(bundle.snapshot.model_dump_json())
    (analysis / "evidence-ledger.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in bundle.evidence])
    )
    request = SemanticStructuralPatch(
        patch_id="patch:keras-normalization",
        operation="insert_layer_norm",
        artifact_path=str(artifact),
        target_node_id="node:input_projection",
        parameters={"module_name": "inserted_norm", "normalized_shape": 16},
    )
    transaction, prepared = prepare_transaction(request, tmp_path / "workspace")
    assert prepared.status == "ok"
    transaction_path = (
        Path(transaction.workspace) / "transactions" / transaction.transaction_id / "transaction.json"
    )
    transaction, verified = verify_transaction(transaction_path)
    assert verified.status == "ok", verified.model_dump(mode="json")
    transaction, committed = commit_transaction(transaction_path)
    assert committed.status == "ok"
    changed_source = (project / "model.py").read_text()
    assert "self.inserted_norm = layers.LayerNormalization(axis=-1)" in changed_source
    assert "self.inserted_norm(projected)" in changed_source


def test_flax_activation_structural_transaction_commits_atomically(tmp_path: Path) -> None:
    source = ROOT / "fixtures" / "cross_framework" / "jax_flax"
    project = tmp_path / "project"
    shutil.copytree(source, project)
    config = project / "config.json"
    bundle = analyze_with_adapter(
        project,
        "model:ResidualMixer",
        "inference",
        "eval",
        config.read_bytes(),
        config,
        framework="jax",
        pattern_packs_enabled=False,
    )
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    artifact = analysis / "architecture.json"
    artifact.write_text(bundle.architecture.model_dump_json())
    (analysis / "source-snapshot.json").write_text(bundle.snapshot.model_dump_json())
    (analysis / "evidence-ledger.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in bundle.evidence])
    )
    request = SemanticStructuralPatch(
        patch_id="patch:jax-activation",
        operation="replace_activation",
        artifact_path=str(artifact),
        target_node_id="node:activated",
        parameters={"replacement": "ReLU"},
    )
    transaction, prepared = prepare_transaction(request, tmp_path / "workspace")
    assert prepared.status == "ok"
    transaction_path = (
        Path(transaction.workspace) / "transactions" / transaction.transaction_id / "transaction.json"
    )
    transaction, verified = verify_transaction(transaction_path)
    assert verified.status == "ok"
    transaction, committed = commit_transaction(transaction_path)
    assert committed.status == "ok"
    assert "activated = nn.relu(mixed)" in (project / "model.py").read_text()


def test_onnx_initializer_transaction_replays_and_commits_atomically(tmp_path: Path) -> None:
    onnx = pytest.importorskip("onnx")
    source = ROOT / "fixtures" / "cross_framework" / "onnx_residual"
    project = tmp_path / "project"
    shutil.copytree(source, project)
    bundle = analyze_with_adapter(
        project,
        "model.onnx",
        "inference",
        "eval",
        b"{}",
        None,
        framework="onnx",
        pattern_packs_enabled=False,
    )
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    artifact = analysis / "architecture.json"
    artifact.write_text(bundle.architecture.model_dump_json())
    (analysis / "source-snapshot.json").write_text(bundle.snapshot.model_dump_json())
    (analysis / "evidence-ledger.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in bundle.evidence])
    )
    new_weight = [
        [2.0, 0.0, 0.0, 0.0],
        [0.0, 2.0, 0.0, 0.0],
        [0.0, 0.0, 2.0, 0.0],
        [0.0, 0.0, 0.0, 2.0],
    ]
    request = SemanticParameterPatch(
        patch_id="patch:onnx-initializer",
        artifact_path=str(artifact),
        target_node_id="node:initializer.weight",
        parameter_name="value",
        new_value=new_weight,
        runtime_input_spec="runtime-input.json",
    )
    original_digest = (project / "model.onnx").read_bytes()
    transaction, prepared = prepare_transaction(request, tmp_path / "workspace")
    assert prepared.status == "ok"
    assert transaction.artifact_kind == "model-artifact"
    assert (project / "model.onnx").read_bytes() == original_digest
    transaction_path = (
        Path(transaction.workspace) / "transactions" / transaction.transaction_id / "transaction.json"
    )
    transaction, verified = verify_transaction(transaction_path)
    assert verified.status == "ok", verified.model_dump(mode="json")
    transaction, committed = commit_transaction(transaction_path)
    assert committed.status == "ok"
    model = onnx.load(project / "model.onnx")
    weight = next(item for item in model.graph.initializer if item.name == "weight")
    assert onnx.numpy_helper.to_array(weight).tolist() == new_weight


def _onnx_external_data_project(project: Path) -> None:
    np = pytest.importorskip("numpy")
    onnx = pytest.importorskip("onnx")
    project.mkdir()
    signal = onnx.helper.make_tensor_value_info("signal", onnx.TensorProto.FLOAT, [1, 4])
    output = onnx.helper.make_tensor_value_info("output", onnx.TensorProto.FLOAT, [1, 4])
    weight = onnx.numpy_helper.from_array(np.eye(4, dtype=np.float32), name="weight")
    node = onnx.helper.make_node("MatMul", ["signal", "weight"], ["output"], name="matmul")
    graph = onnx.helper.make_graph([node], "ExternalWeightGraph", [signal], [output], [weight])
    model = onnx.helper.make_model(graph, opset_imports=[onnx.helper.make_opsetid("", 20)])
    model.ir_version = 13
    onnx.save_model(
        model,
        project / "model.onnx",
        save_as_external_data=True,
        all_tensors_to_one_file=True,
        location="weights.bin",
        size_threshold=0,
    )
    (project / "runtime-input.json").write_text(
        json.dumps(
            {
                "inputs": [
                    {
                        "name": "signal",
                        "shape": [1, 4],
                        "dtype": "float32",
                        "generator": "ones",
                    }
                ]
            }
        )
    )


def _external_transaction(project: Path, root: Path):
    root.mkdir(parents=True, exist_ok=True)
    artifact = _onnx_transaction_artifacts(project, root / "analysis")
    request = SemanticParameterPatch(
        patch_id="patch:onnx-external-initializer",
        artifact_path=str(artifact),
        target_node_id="node:initializer.weight",
        parameter_name="value",
        new_value=[
            [3.0, 0.0, 0.0, 0.0],
            [0.0, 3.0, 0.0, 0.0],
            [0.0, 0.0, 3.0, 0.0],
            [0.0, 0.0, 0.0, 3.0],
        ],
        runtime_input_spec="runtime-input.json",
    )
    transaction, prepared = prepare_transaction(request, root / "workspace")
    assert prepared.status == "ok"
    assert {change.path for change in transaction.file_changes} == {
        "model.onnx",
        "weights.bin",
    }
    transaction_path = (
        Path(transaction.workspace) / "transactions" / transaction.transaction_id / "transaction.json"
    )
    transaction, verified = verify_transaction(transaction_path)
    assert verified.status == "ok", verified.model_dump(mode="json")
    return transaction_path


def test_onnx_external_data_transaction_replays_and_commits_as_artifact_set(
    tmp_path: Path,
) -> None:
    onnx = pytest.importorskip("onnx")
    project = tmp_path / "project"
    _onnx_external_data_project(project)
    bundle = analyze_with_adapter(
        project,
        "model.onnx",
        "inference",
        "eval",
        b"{}",
        None,
        framework="onnx",
        pattern_packs_enabled=False,
    )
    assert {item.path for item in bundle.snapshot.source_files} == {"model.onnx", "weights.bin"}
    transaction_path = _external_transaction(project, tmp_path)
    _, committed = commit_transaction(transaction_path)
    assert committed.status == "ok", committed.model_dump(mode="json")
    model = onnx.load(project / "model.onnx", load_external_data=True)
    weight = next(item for item in model.graph.initializer if item.name == "weight")
    assert onnx.numpy_helper.to_array(weight)[0, 0] == pytest.approx(3.0)


def test_onnx_external_data_concurrency_and_rollback_cover_every_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from archcanvas_transactions import service

    project = tmp_path / "project"
    _onnx_external_data_project(project)
    transaction_path = _external_transaction(project, tmp_path / "stale")
    external = project / "weights.bin"
    external.write_bytes(external.read_bytes() + b"concurrent")
    _, stale = commit_transaction(transaction_path)
    assert stale.status == "invalid"
    assert stale.diagnostics[0].code == "CONCURRENT_MODIFICATION"

    project = tmp_path / "rollback-project"
    _onnx_external_data_project(project)
    originals = {path: path.read_bytes() for path in (project / "model.onnx", project / "weights.bin")}
    transaction_path = _external_transaction(project, tmp_path / "rollback")
    monkeypatch.setattr(service, "_analyze_at", lambda *_: (_ for _ in ()).throw(RuntimeError("boom")))
    _, rolled_back = commit_transaction(transaction_path)
    assert rolled_back.status == "invalid"
    assert rolled_back.diagnostics[0].code == "ATOMIC_COMMIT_FAILED"
    assert originals == {path: path.read_bytes() for path in originals}


def test_onnx_external_data_location_must_be_confined_to_project(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    onnx = pytest.importorskip("onnx")
    project = tmp_path / "project"
    project.mkdir()
    signal = onnx.helper.make_tensor_value_info("signal", onnx.TensorProto.FLOAT, [1, 2])
    output = onnx.helper.make_tensor_value_info("output", onnx.TensorProto.FLOAT, [1, 2])
    weight = onnx.numpy_helper.from_array(np.eye(2, dtype=np.float32), name="weight")
    external_bytes = bytes(weight.raw_data)
    onnx.external_data_helper.set_external_data(weight, location="../outside.bin")
    weight.ClearField("raw_data")
    node = onnx.helper.make_node("MatMul", ["signal", "weight"], ["output"])
    graph = onnx.helper.make_graph([node], "EscapingGraph", [signal], [output], [weight])
    model = onnx.helper.make_model(graph, opset_imports=[onnx.helper.make_opsetid("", 20)])
    (tmp_path / "outside.bin").write_bytes(external_bytes)
    (project / "model.onnx").write_bytes(model.SerializeToString())
    with pytest.raises(ValueError, match="not confined"):
        analyze_with_adapter(
            project,
            "model.onnx",
            "inference",
            "eval",
            b"{}",
            None,
            framework="onnx",
            pattern_packs_enabled=False,
        )


def test_onnx_runtime_rejects_unavailable_provider_without_artifact_changes(
    tmp_path: Path,
) -> None:
    if importlib.util.find_spec("onnxruntime") is None:
        pytest.skip("optional ONNX Runtime dependency is not installed")
    repository_entries = set(ROOT.iterdir())
    source = ROOT / "fixtures" / "cross_framework" / "onnx_residual"
    project = tmp_path / "project"
    shutil.copytree(source, project)
    artifact = _onnx_transaction_artifacts(project, tmp_path / "analysis")
    spec = json.loads((project / "runtime-input.json").read_text())
    spec["selected_target"] = "UnavailableExecutionProvider"
    input_path = tmp_path / "provider-input.json"
    input_path.write_text(json.dumps(spec))
    protected = {path: path.read_bytes() for path in (project / "model.onnx", artifact)}
    receipt = trace_runtime(artifact, input_path, tmp_path / "runtime")
    assert receipt.status == "failed"
    assert receipt.gates[0].status == "passed"
    assert "unavailable" in receipt.diagnostics[0].message
    assert protected == {path: path.read_bytes() for path in protected}
    assert set(ROOT.iterdir()) == repository_entries


def test_onnx_custom_op_requires_provider_and_preserves_original_model(tmp_path: Path) -> None:
    onnx = pytest.importorskip("onnx")
    if importlib.util.find_spec("onnxruntime") is None:
        pytest.skip("optional ONNX Runtime dependency is not installed")
    project = tmp_path / "project"
    project.mkdir()
    signal = onnx.helper.make_tensor_value_info("signal", onnx.TensorProto.FLOAT, [1, 4])
    output = onnx.helper.make_tensor_value_info("output", onnx.TensorProto.FLOAT, [1, 4])
    custom = onnx.helper.make_node(
        "ResearchOp",
        ["signal"],
        ["output"],
        name="custom",
        domain="research.archcanvas",
    )
    graph = onnx.helper.make_graph([custom], "CustomGraph", [signal], [output])
    model = onnx.helper.make_model(
        graph,
        opset_imports=[
            onnx.helper.make_opsetid("", 20),
            onnx.helper.make_opsetid("research.archcanvas", 1),
        ],
    )
    model.ir_version = 13
    model_path = project / "model.onnx"
    model_path.write_bytes(model.SerializeToString())
    input_path = project / "runtime-input.json"
    input_path.write_text(
        json.dumps(
            {
                "selected_target": "CPUExecutionProvider",
                "inputs": [
                    {
                        "name": "signal",
                        "shape": [1, 4],
                        "dtype": "float32",
                        "generator": "ones",
                    }
                ],
            }
        )
    )
    artifact = _onnx_transaction_artifacts(project, tmp_path / "analysis")
    before = model_path.read_bytes()
    receipt = trace_runtime(artifact, input_path, tmp_path / "runtime")
    assert receipt.status == "failed"
    assert receipt.gates[0].status == "passed"
    assert "ResearchOp" in receipt.diagnostics[0].message
    assert model_path.read_bytes() == before


def _onnx_activation_project(project: Path, op_type: str, **attributes: object) -> None:
    onnx = pytest.importorskip("onnx")
    project.mkdir()
    input_info = onnx.helper.make_tensor_value_info("signal", onnx.TensorProto.FLOAT, [1, 4])
    output_info = onnx.helper.make_tensor_value_info("output", onnx.TensorProto.FLOAT, [1, 4])
    node = onnx.helper.make_node(op_type, ["signal"], ["output"], name="activation", **attributes)
    graph = onnx.helper.make_graph([node], "ActivationGraph", [input_info], [output_info])
    model = onnx.helper.make_model(
        graph,
        opset_imports=[onnx.helper.make_opsetid("", 20)],
    )
    model.ir_version = 13
    onnx.checker.check_model(model)
    onnx.save(model, project / "model.onnx")
    (project / "runtime-input.json").write_text(
        json.dumps(
            {
                "inputs": [
                    {
                        "name": "signal",
                        "shape": [1, 4],
                        "dtype": "float32",
                        "generator": "ones",
                    }
                ]
            }
        )
    )


def _onnx_transaction_artifacts(project: Path, analysis: Path) -> Path:
    bundle = analyze_with_adapter(
        project,
        "model.onnx",
        "inference",
        "eval",
        b"{}",
        None,
        framework="onnx",
        pattern_packs_enabled=False,
    )
    analysis.mkdir()
    artifact = analysis / "architecture.json"
    artifact.write_text(bundle.architecture.model_dump_json())
    (analysis / "source-snapshot.json").write_text(bundle.snapshot.model_dump_json())
    (analysis / "evidence-ledger.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in bundle.evidence])
    )
    return artifact


def test_onnx_attribute_transaction_commits_atomically(tmp_path: Path) -> None:
    onnx = pytest.importorskip("onnx")
    project = tmp_path / "project"
    _onnx_activation_project(project, "LeakyRelu", alpha=0.1)
    artifact = _onnx_transaction_artifacts(project, tmp_path / "analysis")
    request = SemanticParameterPatch(
        patch_id="patch:onnx-attribute",
        artifact_path=str(artifact),
        target_node_id="node:onnx.activation",
        parameter_name="alpha",
        new_value=0.2,
        runtime_input_spec="runtime-input.json",
    )
    transaction, _ = prepare_transaction(request, tmp_path / "workspace")
    transaction_path = (
        Path(transaction.workspace) / "transactions" / transaction.transaction_id / "transaction.json"
    )
    transaction, verified = verify_transaction(transaction_path)
    assert verified.status == "ok"
    transaction, committed = commit_transaction(transaction_path)
    assert committed.status == "ok"
    node = onnx.load(project / "model.onnx").graph.node[0]
    assert onnx.helper.get_attribute_value(node.attribute[0]) == pytest.approx(0.2)


def test_onnx_limited_node_transform_commits_atomically(tmp_path: Path) -> None:
    onnx = pytest.importorskip("onnx")
    project = tmp_path / "project"
    _onnx_activation_project(project, "Relu")
    artifact = _onnx_transaction_artifacts(project, tmp_path / "analysis")
    request = SemanticStructuralPatch(
        patch_id="patch:onnx-node",
        operation="replace_activation",
        artifact_path=str(artifact),
        target_node_id="node:onnx.activation",
        parameters={"replacement": "GELU"},
        runtime_input_spec="runtime-input.json",
    )
    transaction, _ = prepare_transaction(request, tmp_path / "workspace")
    transaction_path = (
        Path(transaction.workspace) / "transactions" / transaction.transaction_id / "transaction.json"
    )
    transaction, verified = verify_transaction(transaction_path)
    assert verified.status == "ok", verified.model_dump(mode="json")
    transaction, committed = commit_transaction(transaction_path)
    assert committed.status == "ok"
    assert onnx.load(project / "model.onnx").graph.node[0].op_type == "Gelu"


def test_framework_auto_detection_supports_onnx_and_python_source() -> None:
    if next(item for item in adapter_capabilities() if item.framework == "onnx").status == "unavailable":
        pytest.skip("optional ONNX dependency is not installed")
    fixture = ROOT / "fixtures" / "cross_framework" / "onnx_residual"
    bundle = analyze_with_adapter(
        fixture,
        "model.onnx",
        "inference",
        "eval",
        b"{}",
        None,
        framework="auto",
        pattern_packs_enabled=False,
    )
    assert bundle.architecture.framework == "onnx"
    python_bundle = analyze_with_adapter(
        ROOT / "fixtures" / "cross_framework" / "keras_subclass",
        "model:TemporalGate",
        "inference",
        "eval",
        b"{}",
        None,
        framework="auto",
        pattern_packs_enabled=False,
    )
    assert python_bundle.architecture.framework == "keras"
