from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from archcanvas_core.validation import validate_architecture
from archcanvas_python import AnalysisError, analyze_project

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "tier_a" / "itransformer"


def itransformer_bundle(config: dict | None = None):
    config_bytes = json.dumps(config).encode() if config is not None else (FIXTURE / "config.json").read_bytes()
    return analyze_project(
        FIXTURE,
        "model.iTransformer:Model",
        "long_term_forecast",
        "eval",
        config_bytes,
        FIXTURE / "config.json",
    )


def test_itransformer_contract_and_gate_pass() -> None:
    bundle = itransformer_bundle()
    gates, diagnostics = validate_architecture(bundle.architecture, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "A-source-identity").status == "passed"
    assert next(gate for gate in gates if gate.gate == "B-semantic-closure").status == "passed"
    assert next(gate for gate in gates if gate.gate == "B-itransformer").status == "passed"
    assert not diagnostics


def test_itransformer_recovers_inverted_tokens_and_conditional_paths() -> None:
    bundle = itransformer_bundle()
    nodes = {node.node_id: node for node in bundle.architecture.nodes}
    assert nodes["node:embedding.permute"].attributes["external_learnable_module"] is False
    assert nodes["node:embedding.projection"].attributes == {
        "in_axis": "L",
        "out_axis": "D",
        "op_type": "nn.Linear",
    }
    assert "node:forecast.trim_covariates" in nodes
    assert "node:normalize" in nodes
    assert "node:denormalize" in nodes
    assert not [node for node in nodes.values() if "decoder" in node.semantic_name.lower()]
    output = next(tensor for tensor in bundle.architecture.tensors if tensor.role == "forecast")
    assert output.symbolic_shape == "[B,S,N]"
    assert {record.discrepancy_id for record in bundle.discrepancies} == {
        "discrepancy:itransformer.internal-permute",
        "discrepancy:itransformer.normalization",
        "discrepancy:itransformer.covariates",
    }


def test_itransformer_false_predicates_remove_optional_paths() -> None:
    config = json.loads((FIXTURE / "config.json").read_text())
    config["use_norm"] = False
    config["use_covariates"] = False
    bundle = itransformer_bundle(config)
    node_ids = {node.node_id for node in bundle.architecture.nodes}
    assert not {"node:normalize", "node:denormalize"} & node_ids
    assert not {
        "node:covariate.permute",
        "node:covariate.concat",
        "node:forecast.trim_covariates",
    } & node_ids
    gates, diagnostics = validate_architecture(bundle.architecture, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-itransformer").status == "passed"
    assert not diagnostics


def test_learnable_external_permute_mutation_fails_gate() -> None:
    bundle = itransformer_bundle()
    nodes = [
        node.model_copy(
            update={"attributes": {**node.attributes, "external_learnable_module": True}}
        )
        if node.node_id == "node:embedding.permute"
        else node
        for node in bundle.architecture.nodes
    ]
    mutated = bundle.architecture.model_copy(update={"nodes": nodes})
    gates, diagnostics = validate_architecture(mutated, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-itransformer").status == "failed"
    assert any(item.code == "ITRANSFORMER_INTERNAL_PERMUTE_INVALID" for item in diagnostics)


def test_missing_covariate_trim_mutation_fails_gate() -> None:
    bundle = itransformer_bundle()
    mutated = bundle.architecture.model_copy(
        update={
            "nodes": [
                node
                for node in bundle.architecture.nodes
                if node.node_id != "node:forecast.trim_covariates"
            ],
            "edges": [
                edge
                for edge in bundle.architecture.edges
                if edge.producer_id != "node:forecast.trim_covariates"
                and edge.consumer_id != "node:forecast.trim_covariates"
            ],
            "tensors": [
                tensor
                for tensor in bundle.architecture.tensors
                if tensor.producer_id != "node:forecast.trim_covariates"
                and "node:forecast.trim_covariates" not in tensor.consumer_ids
            ],
            "fanouts": [],
        }
    )
    gates, diagnostics = validate_architecture(mutated, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-itransformer").status == "failed"
    assert any(item.code == "ITRANSFORMER_COVARIATE_PATH_INVALID" for item in diagnostics)


def test_modified_itransformer_fixture_is_rejected(tmp_path: Path) -> None:
    copied = tmp_path / "itransformer"
    shutil.copytree(FIXTURE, copied)
    model_path = copied / "model" / "iTransformer.py"
    model_path.write_text(model_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(AnalysisError) as caught:
        analyze_project(
            copied,
            "model.iTransformer:Model",
            "long_term_forecast",
            "eval",
            (copied / "config.json").read_bytes(),
            copied / "config.json",
        )
    assert caught.value.code == "ITRANSFORMER_SOURCE_STALE"


def test_itransformer_generic_fallback_closes() -> None:
    bundle = analyze_project(
        FIXTURE,
        "model.iTransformer:Model",
        "long_term_forecast",
        "eval",
        (FIXTURE / "config.json").read_bytes(),
        FIXTURE / "config.json",
        pattern_packs_enabled=False,
    )
    gates, diagnostics = validate_architecture(bundle.architecture, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-semantic-closure").status == "passed"
    assert not [gate for gate in gates if gate.gate == "B-itransformer"]
    assert not diagnostics
