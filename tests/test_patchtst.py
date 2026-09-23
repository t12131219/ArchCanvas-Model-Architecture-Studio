from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from archcanvas_core.validation import validate_architecture
from archcanvas_python import AnalysisError, analyze_project

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "tier_a" / "patchtst"


def patchtst_bundle(config: dict | None = None):
    config_bytes = json.dumps(config).encode() if config is not None else (FIXTURE / "config.json").read_bytes()
    return analyze_project(
        FIXTURE,
        "models.PatchTST:Model",
        "long_term_forecast",
        "eval",
        config_bytes,
        FIXTURE / "config.json",
    )


def test_patchtst_contract_and_gate_pass() -> None:
    bundle = patchtst_bundle()
    gates, diagnostics = validate_architecture(bundle.architecture, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "A-source-identity").status == "passed"
    assert next(gate for gate in gates if gate.gate == "B-semantic-closure").status == "passed"
    assert next(gate for gate in gates if gate.gate == "B-patchtst").status == "passed"
    assert not diagnostics


def test_patchtst_recovers_dual_backbones_and_true_head() -> None:
    bundle = patchtst_bundle()
    nodes = {node.node_id: node for node in bundle.architecture.nodes}
    for lane in ("residual", "trend"):
        assert nodes[f"node:{lane}.unfold"].attributes["patch_count"] == 12
        assert nodes[f"node:{lane}.patch_projection"].attributes["in_axis"] == "P"
        assert nodes[f"node:{lane}.channel_reshape"].attributes["transform"] == (
            "[B,C,Np,D] -> [BC,Np,D]"
        )
        assert nodes[f"node:{lane}.encoder"].attributes["norm"] == "BatchNorm"
        assert nodes[f"node:{lane}.encoder"].attributes["residual_attention"] is True
        assert nodes[f"node:{lane}.flatten"].attributes["transform"] == (
            "[B,C,D,Np] -> [B,C,D*Np]"
        )
        assert nodes[f"node:{lane}.head_linear"].attributes["in_axis"] == "D*Np"
    assert "node:decomposition_add" in nodes
    assert next(tensor for tensor in bundle.architecture.tensors if tensor.role == "forecast").symbolic_shape == "[B,S,C]"


def test_patchtst_single_backbone_config_removes_dual_path() -> None:
    config = json.loads((FIXTURE / "config.json").read_text())
    config["decomposition"] = False
    config["revin"] = False
    config["padding_patch"] = None
    bundle = patchtst_bundle(config)
    node_ids = {node.node_id for node in bundle.architecture.nodes}
    assert "node:main.encoder" in node_ids
    assert "node:decomposition" not in node_ids
    assert not [node_id for node_id in node_ids if "revin_" in node_id or "end_padding" in node_id]
    gates, diagnostics = validate_architecture(bundle.architecture, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-patchtst").status == "passed"
    assert not diagnostics


def test_simplified_head_mutation_fails_patchtst_gate() -> None:
    bundle = patchtst_bundle()
    nodes = [
        node.model_copy(update={"attributes": {**node.attributes, "in_axis": "D"}})
        if node.node_id == "node:residual.head_linear"
        else node
        for node in bundle.architecture.nodes
    ]
    mutated = bundle.architecture.model_copy(update={"nodes": nodes})
    gates, diagnostics = validate_architecture(mutated, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-patchtst").status == "failed"
    assert any(item.code == "PATCHTST_HEAD_LINEAR_INVALID" for item in diagnostics)


def test_missing_trend_merge_mutation_fails_patchtst_gate() -> None:
    bundle = patchtst_bundle()
    mutated = bundle.architecture.model_copy(
        update={
            "edges": [
                edge
                for edge in bundle.architecture.edges
                if not (
                    edge.producer_id == "node:trend.revin_denorm"
                    and edge.consumer_id == "node:decomposition_add"
                )
            ]
        }
    )
    gates, diagnostics = validate_architecture(mutated, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-patchtst").status == "failed"
    assert any(item.code == "PATCHTST_DECOMPOSITION_MERGE_INVALID" for item in diagnostics)


def test_modified_patchtst_fixture_is_rejected(tmp_path: Path) -> None:
    copied = tmp_path / "patchtst"
    shutil.copytree(FIXTURE, copied)
    model_path = copied / "models" / "PatchTST.py"
    model_path.write_text(model_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(AnalysisError) as caught:
        analyze_project(
            copied,
            "models.PatchTST:Model",
            "long_term_forecast",
            "eval",
            (copied / "config.json").read_bytes(),
            copied / "config.json",
        )
    assert caught.value.code == "PATCHTST_SOURCE_STALE"


def test_patchtst_generic_fallback_closes() -> None:
    bundle = analyze_project(
        FIXTURE,
        "models.PatchTST:Model",
        "long_term_forecast",
        "eval",
        (FIXTURE / "config.json").read_bytes(),
        FIXTURE / "config.json",
        pattern_packs_enabled=False,
    )
    gates, diagnostics = validate_architecture(bundle.architecture, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-semantic-closure").status == "passed"
    assert not [gate for gate in gates if gate.gate == "B-patchtst"]
    assert not diagnostics
