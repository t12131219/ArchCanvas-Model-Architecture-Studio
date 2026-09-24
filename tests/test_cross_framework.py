from __future__ import annotations

import json
from pathlib import Path

import pytest

from archcanvas_adapters import adapter_capabilities, analyze_with_adapter
from archcanvas_core.validation import validate_architecture
from archcanvas_engine.cli import main
from archcanvas_publication import (
    build_scene,
    build_visual_spec,
    compile_views,
    validate_geometry,
    validate_publication,
)

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
    assert capabilities["keras"].required_packages == {"tensorflow-or-keras": None}
    assert capabilities["jax"].required_packages == {"jax-or-flax": None}
    assert capabilities["keras"].runtime_evidence is False
    assert capabilities["jax"].source_transactions is False


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


def test_non_pytorch_runtime_trace_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = ROOT / "fixtures" / "cross_framework" / "jax_function"
    out = tmp_path / "analysis"
    assert main(
        [
            "analyze",
            "--framework",
            "jax",
            "--project",
            str(fixture),
            "--entry",
            "model:residual_projection",
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
    input_spec = tmp_path / "input.json"
    input_spec.write_text('{"inputs": [{"name": "signal", "shape": [1, 4]}]}')
    assert main(
        [
            "trace",
            str(out / "architecture.json"),
            "--input-spec",
            str(input_spec),
            "--out",
            str(out),
            "--json",
        ]
    ) == 2
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "invalid"
    assert "only for PyTorch" in receipt["diagnostics"][0]["message"]


def test_non_pytorch_source_transaction_is_rejected(
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
                "patch_id": "patch:keras-denied",
                "operation": "set_parameter",
                "artifact_path": str(out / "architecture.json"),
                "target_node_id": "node:input_projection",
                "parameter_name": "units",
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
    ) == 2
    receipt = json.loads(capsys.readouterr().out)
    assert "only for PyTorch" in receipt["diagnostics"][0]["message"]


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
