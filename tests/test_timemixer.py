from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from archcanvas_core.validation import validate_architecture
from archcanvas_python import AnalysisError, analyze_project

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "tier_a" / "timemixer"


def timemixer_bundle(config: dict | None = None):
    config_bytes = json.dumps(config).encode() if config is not None else (FIXTURE / "config.json").read_bytes()
    return analyze_project(
        FIXTURE,
        "models.TimeMixer:Model",
        "long_term_forecast",
        "eval",
        config_bytes,
        FIXTURE / "config.json",
    )


def test_timemixer_contract_and_gate_pass() -> None:
    bundle = timemixer_bundle()
    gates, diagnostics = validate_architecture(bundle.architecture, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "A-source-identity").status == "passed"
    assert next(gate for gate in gates if gate.gate == "B-semantic-closure").status == "passed"
    assert next(gate for gate in gates if gate.gate == "B-timemixer").status == "passed"
    assert not diagnostics


def test_timemixer_recovers_bidirectional_scale_mixing_and_prediction_merge() -> None:
    bundle = timemixer_bundle()
    nodes = {node.node_id: node for node in bundle.architecture.nodes}
    assert nodes["node:season.bottom_up"].attributes["direction"] == (
        "high-resolution-to-low-resolution"
    )
    assert nodes["node:trend.top_down"].attributes["direction"] == (
        "low-resolution-to-high-resolution"
    )
    for scale in range(3):
        assert f"node:scale.{scale}.normalize" in nodes
        assert nodes[f"node:scale.{scale}.embedding"].attributes["position_embedding_used"] is False
        assert nodes[f"node:scale.{scale}.decomposition"].attributes["method"] == "moving_avg"
        assert f"node:scale.{scale}.predictor" in nodes
        assert f"node:scale.{scale}.projection" in nodes
        assert nodes[f"node:scale.{scale}.mark_repeat"].attributes["transform"].startswith(
            "[B,"
        )
        assert nodes[f"node:scale.{scale}.restore_forecast"].attributes["transform"] == (
            "[B*N,S,1] -> [B,S,C]"
        )
    assert nodes["node:forecast.sum"].attributes["operation"] == "reduce_sum"
    assert not [
        node
        for node in nodes.values()
        if "conv" in node.semantic_name.lower()
        and any(word in node.semantic_name.lower() for word in ("short", "mid", "long"))
    ]
    assert next(tensor for tensor in bundle.architecture.tensors if tensor.role == "forecast").symbolic_shape == "[B,S,C]"


def test_timemixer_dft_config_selects_dft_decomposition() -> None:
    config = json.loads((FIXTURE / "config.json").read_text())
    config["decomp_method"] = "dft_decomp"
    bundle = timemixer_bundle(config)
    decomposition_nodes = [
        node for node in bundle.architecture.nodes if node.node_id.endswith(".decomposition")
    ]
    assert decomposition_nodes
    assert {node.attributes["method"] for node in decomposition_nodes} == {"dft_decomp"}
    gates, diagnostics = validate_architecture(bundle.architecture, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-timemixer").status == "passed"
    assert not diagnostics


def test_reversed_season_direction_mutation_fails_gate() -> None:
    bundle = timemixer_bundle()
    nodes = [
        node.model_copy(
            update={
                "attributes": {
                    **node.attributes,
                    "direction": "low-resolution-to-high-resolution",
                }
            }
        )
        if node.node_id == "node:season.bottom_up"
        else node
        for node in bundle.architecture.nodes
    ]
    mutated = bundle.architecture.model_copy(update={"nodes": nodes})
    gates, diagnostics = validate_architecture(mutated, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-timemixer").status == "failed"
    assert any(item.code == "TIMEMIXER_SEASON_DIRECTION_INVALID" for item in diagnostics)


def test_missing_scale_forecast_mutation_fails_gate() -> None:
    bundle = timemixer_bundle()
    mutated = bundle.architecture.model_copy(
        update={
            "edges": [
                edge
                for edge in bundle.architecture.edges
                if not (
                    edge.producer_id == "node:scale.2.restore_forecast"
                    and edge.consumer_id == "node:forecast.stack"
                )
            ]
        }
    )
    gates, diagnostics = validate_architecture(mutated, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-timemixer").status == "failed"
    assert any(item.code == "TIMEMIXER_SCALE_FORECAST_MISSING" for item in diagnostics)


def test_modified_timemixer_fixture_is_rejected(tmp_path: Path) -> None:
    copied = tmp_path / "timemixer"
    shutil.copytree(FIXTURE, copied)
    model_path = copied / "models" / "TimeMixer.py"
    model_path.write_text(model_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(AnalysisError) as caught:
        analyze_project(
            copied,
            "models.TimeMixer:Model",
            "long_term_forecast",
            "eval",
            (copied / "config.json").read_bytes(),
            copied / "config.json",
        )
    assert caught.value.code == "TIMEMIXER_SOURCE_STALE"


def test_timemixer_generic_fallback_closes() -> None:
    bundle = analyze_project(
        FIXTURE,
        "models.TimeMixer:Model",
        "long_term_forecast",
        "eval",
        (FIXTURE / "config.json").read_bytes(),
        FIXTURE / "config.json",
        pattern_packs_enabled=False,
    )
    gates, diagnostics = validate_architecture(bundle.architecture, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-semantic-closure").status == "passed"
    assert not [gate for gate in gates if gate.gate == "B-timemixer"]
    assert not diagnostics
