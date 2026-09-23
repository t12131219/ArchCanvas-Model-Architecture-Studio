from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from archcanvas_core.models import EdgeType
from archcanvas_core.validation import validate_architecture
from archcanvas_python import AnalysisError, analyze_project

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "tier_a" / "autoformer"


def autoformer_bundle():
    return analyze_project(
        FIXTURE,
        "models.Autoformer:Model",
        "long_term_forecast",
        "eval",
        (FIXTURE / "config.json").read_bytes(),
        FIXTURE / "config.json",
    )


def test_autoformer_source_contract_and_semantic_gate_pass() -> None:
    bundle = autoformer_bundle()
    gates, diagnostics = validate_architecture(
        bundle.architecture,
        bundle.evidence,
        bundle.snapshot,
    )
    assert next(gate for gate in gates if gate.gate == "A-source-identity").status == "passed"
    assert next(gate for gate in gates if gate.gate == "B-semantic-closure").status == "passed"
    assert next(gate for gate in gates if gate.gate == "B-autoformer").status == "passed"
    assert not diagnostics


def test_autoformer_recovers_source_specific_facts() -> None:
    bundle = autoformer_bundle()
    nodes = {node.node_id: node for node in bundle.architecture.nodes}
    assert nodes["node:enc_embedding"].attributes["position_embedding_used"] is False
    assert nodes["node:dec_embedding"].attributes["position_embedding_used"] is False
    assert not [edge for edge in bundle.architecture.edges if edge.edge_type is EdgeType.CONDITION]

    memory_edges = [edge for edge in bundle.architecture.edges if edge.edge_type is EdgeType.MEMORY]
    assert {edge.consumer_id for edge in memory_edges} == {
        "node:decoder.cross_k_projection",
        "node:decoder.cross_v_projection",
    }
    repeats = {repeat.repeat_id: repeat.count for repeat in bundle.architecture.repeats}
    assert repeats == {"repeat:encoder.layers": 2, "repeat:decoder.layers": 1}
    assert {record.discrepancy_id for record in bundle.discrepancies} == {
        "discrepancy:autoformer.position-embedding",
        "discrepancy:autoformer.add-norm",
        "discrepancy:autoformer.mask",
        "discrepancy:autoformer.dual-path",
    }


def test_position_embedding_mutation_fails_autoformer_gate() -> None:
    bundle = autoformer_bundle()
    nodes = [
        node.model_copy(update={"attributes": {**node.attributes, "position_embedding_used": True}})
        if node.node_id == "node:enc_embedding"
        else node
        for node in bundle.architecture.nodes
    ]
    mutated = bundle.architecture.model_copy(update={"nodes": nodes})
    gates, diagnostics = validate_architecture(mutated, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-autoformer").status == "failed"
    assert any(item.code == "AUTOFORMER_POSITION_EMBEDDING_INVALID" for item in diagnostics)


def test_missing_third_trend_path_fails_autoformer_gate() -> None:
    bundle = autoformer_bundle()
    mutated = bundle.architecture.model_copy(
        update={
            "edges": [
                edge
                for edge in bundle.architecture.edges
                if not (
                    edge.producer_id == "node:decoder.decomp3"
                    and edge.consumer_id == "node:decoder.trend_residual_sum"
                )
            ]
        }
    )
    gates, diagnostics = validate_architecture(mutated, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-autoformer").status == "failed"
    assert any(item.code == "AUTOFORMER_TREND_SUM_INVALID" for item in diagnostics)


def test_fabricated_mask_edge_fails_autoformer_gate() -> None:
    bundle = autoformer_bundle()
    first = bundle.architecture.edges[0]
    mutated = bundle.architecture.model_copy(
        update={
            "edges": [
                first.model_copy(update={"edge_type": EdgeType.CONDITION}),
                *bundle.architecture.edges[1:],
            ]
        }
    )
    gates, diagnostics = validate_architecture(mutated, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-autoformer").status == "failed"
    assert any(item.code == "AUTOFORMER_MASK_SEMANTICS_INVALID" for item in diagnostics)


def test_modified_upstream_fixture_is_rejected(tmp_path: Path) -> None:
    copied = tmp_path / "autoformer"
    shutil.copytree(FIXTURE, copied)
    model_path = copied / "models" / "Autoformer.py"
    model_path.write_text(model_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(AnalysisError) as caught:
        analyze_project(
            copied,
            "models.Autoformer:Model",
            "long_term_forecast",
            "eval",
            (copied / "config.json").read_bytes(),
            copied / "config.json",
        )
    assert caught.value.code == "AUTOFORMER_SOURCE_STALE"


def test_autoformer_cli_artifacts_have_correction_and_skipped_runtime(tmp_path, capsys) -> None:
    from archcanvas_engine.cli import main

    exit_code = main(
        [
            "analyze",
            "--project",
            str(FIXTURE),
            "--entry",
            "models.Autoformer:Model",
            "--config",
            str(FIXTURE / "config.json"),
            "--task",
            "long_term_forecast",
            "--mode",
            "eval",
            "--out",
            str(tmp_path),
            "--json",
        ]
    )
    receipt = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert receipt["details"]["profile"] == "autoformer"
    corrections = json.loads((tmp_path / "source-correction-report.json").read_text())
    runtime = json.loads((tmp_path / "runtime-receipt.json").read_text())
    assert len(corrections["discrepancies"]) == 4
    assert runtime["status"] == "skipped"

    validate_exit = main(["validate", str(tmp_path / "architecture.json"), "--json"])
    validate_receipt = json.loads(capsys.readouterr().out)
    assert validate_exit == 0
    assert (
        next(gate for gate in validate_receipt["gates"] if gate["gate"] == "B-autoformer")["status"]
        == "passed"
    )
