from __future__ import annotations

from pathlib import Path

from archcanvas_core.models import EdgeType, NodeKind
from archcanvas_core.validation import validate_architecture
from archcanvas_python import analyze_project

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "tier_a" / "transformer"
GENERIC_FIXTURE = ROOT / "tests" / "fixtures" / "generic"


def transformer_bundle():
    return analyze_project(
        FIXTURE,
        "model:Transformer",
        "inference",
        "eval",
        (FIXTURE / "config.json").read_bytes(),
        FIXTURE / "config.json",
    )


def test_transformer_static_path_has_parallel_qkv_memory_and_residuals() -> None:
    bundle = transformer_bundle()
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
    src_fanout = next(
        relation for relation in bundle.architecture.fanouts if relation.tensor_id == "tensor:src"
    )
    assert set(src_fanout.consumer_ids) >= src_consumers
    memory_consumers = {
        edge.consumer_id for edge in bundle.architecture.edges if edge.role == "memory"
    }
    assert {"node:cross_k_proj", "node:cross_v_proj"} <= memory_consumers
    assert sum(edge.edge_type is EdgeType.RESIDUAL for edge in bundle.architecture.edges) >= 4
    assert any(edge.edge_type is EdgeType.CONDITION for edge in bundle.architecture.edges)
    assert any(
        node.kind is NodeKind.INPUT_OUTPUT and node.attributes.get("io") == "output"
        for node in bundle.architecture.nodes
    )


def test_transformer_ir_passes_semantic_closure() -> None:
    bundle = transformer_bundle()
    gates, diagnostics = validate_architecture(
        bundle.architecture,
        bundle.evidence,
        bundle.snapshot,
    )
    assert next(gate for gate in gates if gate.gate == "B-semantic-closure").status == "passed"
    assert next(gate for gate in gates if gate.gate == "B-transformer-l3").status == "passed"
    assert not [item for item in diagnostics if item.severity == "blocking"]


def test_transformer_shapes_and_parameter_provenance_are_grounded() -> None:
    bundle = transformer_bundle()
    tensors = {tensor.role: tensor for tensor in bundle.architecture.tensors}
    assert tensors["enc_q_split"].symbolic_shape == "[B,H,S,Dh]"
    assert tensors["cross_q_split"].symbolic_shape == "[B,H,T,Dh]"
    assert tensors["cross_k_split"].symbolic_shape == "[B,H,S,Dh]"
    assert tensors["logits"].symbolic_shape == "[B,T,V]"

    projection = next(
        node for node in bundle.architecture.nodes if node.node_id == "node:encoder_q_proj"
    )
    assert [parameter.value for parameter in projection.parameters[:2]] == [64, 64]
    assert {parameter.origin.value for parameter in projection.parameters[:2]} == {"config"}
    assert "evidence:config.d_model" in projection.parameters[0].evidence_ids
    assert bundle.snapshot.config_path == "config.json"
    assert bundle.snapshot.resolved_config["num_heads"] == 8


def test_removing_encoder_memory_path_fails_transformer_gate() -> None:
    bundle = transformer_bundle()
    cross_k = next(
        node
        for node in bundle.architecture.nodes
        if node.attributes.get("assigned_symbol") == "cross_k"
    )
    mutated = bundle.architecture.model_copy(
        update={
            "edges": [
                edge
                for edge in bundle.architecture.edges
                if not (edge.consumer_id == cross_k.node_id and edge.role == "memory")
            ]
        }
    )
    gates, diagnostics = validate_architecture(mutated, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-transformer-l3").status == "failed"
    assert any(item.code == "TRANSFORMER_MEMORY_SOURCE_INVALID" for item in diagnostics)


def test_removing_target_mask_path_fails_transformer_gate() -> None:
    bundle = transformer_bundle()
    mutated = bundle.architecture.model_copy(
        update={
            "edges": [
                edge
                for edge in bundle.architecture.edges
                if not (edge.role == "target_mask" and edge.edge_type is EdgeType.CONDITION)
            ]
        }
    )
    gates, diagnostics = validate_architecture(mutated, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-transformer-l3").status == "failed"
    assert any(item.code == "TRANSFORMER_MASK_PATH_INVALID" for item in diagnostics)


def test_stale_source_evidence_fails_identity_gate() -> None:
    bundle = transformer_bundle()
    source_record = next(record for record in bundle.evidence if record.kind.value == "source")
    stale = source_record.model_copy(update={"file_sha256": "0" * 64})
    evidence = [
        stale if record.evidence_id == stale.evidence_id else record for record in bundle.evidence
    ]
    gates, diagnostics = validate_architecture(bundle.architecture, evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "A-source-identity").status == "failed"
    assert any(item.code == "EVIDENCE_SOURCE_STALE" for item in diagnostics)


def test_missing_fanout_relation_fails_semantic_closure() -> None:
    bundle = transformer_bundle()
    mutated = bundle.architecture.model_copy(
        update={
            "fanouts": [
                relation
                for relation in bundle.architecture.fanouts
                if relation.tensor_id != "tensor:src"
            ]
        }
    )
    gates, diagnostics = validate_architecture(mutated, bundle.evidence, bundle.snapshot)
    assert next(gate for gate in gates if gate.gate == "B-semantic-closure").status == "failed"
    assert any(item.code == "FANOUT_RELATION_MISMATCH" for item in diagnostics)


def test_config_changes_source_snapshot_identity() -> None:
    original = transformer_bundle()
    changed_config = (
        (FIXTURE / "config.json").read_text().replace('"num_heads": 8', '"num_heads": 4')
    )
    changed = analyze_project(
        FIXTURE,
        "model:Transformer",
        "inference",
        "eval",
        changed_config.encode(),
        FIXTURE / "config.json",
    )
    assert original.snapshot.snapshot_id != changed.snapshot.snapshot_id
    assert original.architecture.architecture_id != changed.architecture.architecture_id


def test_tensor2tensor_execution_convention_and_tuple_outputs_are_recovered() -> None:
    bundle = analyze_project(
        GENERIC_FIXTURE,
        "tensor2tensor_model:Transformer",
        "inference",
        "eval",
        framework="keras",
    )
    container = next(node for node in bundle.architecture.nodes if node.parent_id is None)
    assert container.attributes["execution_symbol"] == "Transformer.model_fn_body"

    nodes = {node.semantic_name: node for node in bundle.architecture.nodes}
    encoder_prepare = nodes["transformer_prepare_encoder"]
    decoder_prepare = nodes["transformer_prepare_decoder"]
    assert encoder_prepare.attributes["assigned_symbols"] == [
        "encoder_input",
        "encoder_attention_bias",
    ]
    assert decoder_prepare.attributes["assigned_symbols"] == [
        "decoder_input",
        "decoder_self_attention_bias",
    ]

    decoder = nodes["transformer_decoder"]
    incoming_roles = {
        edge.role
        for edge in bundle.architecture.edges
        if edge.consumer_id == decoder.node_id
    }
    assert {
        "decoder_input",
        "encoder_output",
        "decoder_self_attention_bias",
        "encoder_attention_bias",
    } <= incoming_roles
    assert not any(node.node_id == "node:opaque.execution" for node in nodes.values())
