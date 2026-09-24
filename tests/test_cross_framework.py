from __future__ import annotations

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
    assert {view.layout_family for view in views} == {"generic-dag"}
    for view in views:
        geometry_gate, geometry_diagnostics = validate_geometry(
            build_scene(view, build_visual_spec(view))
        )
        assert geometry_gate.status == "passed"
        assert not geometry_diagnostics


def test_python_source_adapters_do_not_require_framework_packages() -> None:
    capabilities = {item.framework: item for item in adapter_capabilities()}
    assert capabilities["keras"].static_analysis is True
    assert capabilities["jax"].static_analysis is True
    assert "keras" in capabilities["keras"].required_packages
    assert "jax" in capabilities["jax"].required_packages
    assert capabilities["keras"].capability_status["static"] == "partial"
    assert capabilities["jax"].parameter_transactions is True


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
    assert trace["observations"]
    assert trace["output_tensors"]
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


def test_onnx_auto_detection_is_extension_only() -> None:
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
    with pytest.raises(ValueError, match="pass --framework"):
        analyze_with_adapter(
            ROOT / "fixtures" / "cross_framework" / "keras_subclass",
            "model:TemporalGate",
            "inference",
            "eval",
            b"{}",
            None,
            framework="auto",
            pattern_packs_enabled=False,
        )
