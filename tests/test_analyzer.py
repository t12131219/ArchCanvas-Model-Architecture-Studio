from __future__ import annotations

from pathlib import Path

from archcanvas_core.models import EdgeType, NodeKind
from archcanvas_core.validation import validate_architecture
from archcanvas_python import analyze_project


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "tier_a" / "transformer"


def test_transformer_static_path_has_parallel_qkv_memory_and_residuals() -> None:
    bundle = analyze_project(
        FIXTURE,
        "model:Transformer",
        "inference",
        "eval",
        (FIXTURE / "config.json").read_bytes(),
    )
    node_ids = {node.node_id for node in bundle.architecture.nodes}
    assert {
        "node:encoder_q_proj",
        "node:encoder_k_proj",
        "node:encoder_v_proj",
        "node:cross_q_proj",
        "node:cross_k_proj",
        "node:cross_v_proj",
        "node:generator",
    } <= node_ids
    src_consumers = {
        edge.consumer_id
        for edge in bundle.architecture.edges
        if edge.producer_id == "node:input.src"
    }
    assert {
        "node:encoder_q_proj",
        "node:encoder_k_proj",
        "node:encoder_v_proj",
    } <= src_consumers
    memory_consumers = {
        edge.consumer_id
        for edge in bundle.architecture.edges
        if edge.role == "memory"
    }
    assert {"node:cross_k_proj", "node:cross_v_proj"} <= memory_consumers
    assert sum(edge.edge_type is EdgeType.RESIDUAL for edge in bundle.architecture.edges) >= 4
    assert any(edge.edge_type is EdgeType.CONDITION for edge in bundle.architecture.edges)
    assert any(
        node.kind is NodeKind.INPUT_OUTPUT and node.attributes.get("io") == "output"
        for node in bundle.architecture.nodes
    )


def test_transformer_ir_passes_semantic_closure() -> None:
    architecture = analyze_project(
        FIXTURE, "model:Transformer", "inference", "eval"
    ).architecture
    gates, diagnostics = validate_architecture(architecture)
    assert next(gate for gate in gates if gate.gate == "B-semantic-closure").status == "passed"
    assert not [item for item in diagnostics if item.severity == "blocking"]

