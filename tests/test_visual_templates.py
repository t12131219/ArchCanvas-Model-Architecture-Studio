from __future__ import annotations

from pathlib import Path

import pytest

from archcanvas_core.models import (
    PatternCapture,
    PatternPredicate,
    PatternStage,
    VisualTemplateManifest,
)
from archcanvas_patterns import (
    apply_pattern_packs,
    create_template_binding,
    exact_ir_digest,
    load_registry,
    validate_template_binding,
)
from archcanvas_python import analyze_project

ROOT = Path(__file__).resolve().parents[1]


def _analyze_transformer():
    fixture = ROOT / "fixtures" / "tier_a" / "transformer"
    return analyze_project(
        fixture,
        "model:Transformer",
        "inference",
        "eval",
        (fixture / "config.json").read_bytes(),
        fixture / "config.json",
        pattern_packs_enabled=False,
    ).architecture


def _analyze_holdout():
    fixture = ROOT / "fixtures" / "holdout" / "residual_mlp"
    return analyze_project(
        fixture,
        "model:CrossBlendRegressor",
        "forecast",
        "eval",
        (fixture / "config.json").read_bytes(),
        fixture / "config.json",
        pattern_packs_enabled=False,
    ).architecture


def test_attention_template_binds_three_real_subgraphs_without_changing_ir() -> None:
    architecture = _analyze_transformer()
    registry = load_registry()
    before = exact_ir_digest(architecture)

    overlay, receipt = apply_pattern_packs(architecture, registry)

    assert receipt.exact_ir_digest_before == receipt.exact_ir_digest_after == before
    assert exact_ir_digest(architecture) == before
    assert overlay.status == "matched"
    assert overlay.reasons == []
    assert len(overlay.template_bindings) == 3
    assert {
        binding.root_canonical_node_ids[0] for binding in overlay.template_bindings
    } == {
        "node:enc_scores_raw",
        "node:dec_scores_raw",
        "node:cross_scores_raw",
    }
    template = registry.templates["attention.qkv-v1"]
    node_ids = {node.node_id for node in architecture.nodes}
    evidence_ids = {
        evidence_id for node in architecture.nodes for evidence_id in node.evidence_ids
    }
    for binding in overlay.template_bindings:
        assert binding.fidelity == "exact"
        assert set(binding.node_slots) == {slot.slot_id for slot in template.slots}
        assert all(
            canonical_id in node_ids
            for canonical_ids in binding.node_slots.values()
            for canonical_id in canonical_ids
        )
        assert set(binding.evidence_ids) <= evidence_ids
        validate_template_binding(
            architecture,
            template,
            binding,
            exact_ir_digest=before,
        )


def test_attention_template_negative_and_relation_mutation_do_not_invent_slots() -> None:
    registry = load_registry()
    negative_overlay, _ = apply_pattern_packs(_analyze_holdout(), registry)
    assert negative_overlay.status == "generic"
    assert negative_overlay.template_bindings == []

    architecture = _analyze_transformer()
    mutated = architecture.model_copy(
        update={
            "edges": [
                edge
                for edge in architecture.edges
                if edge.edge_id != "edge:enc_q_split:enc_scores_raw:0"
            ]
        }
    )
    overlay, _ = apply_pattern_packs(mutated, registry)
    assert overlay.status == "matched"
    assert len(overlay.template_bindings) == 2
    assert not any(
        binding.root_canonical_node_ids == ["node:enc_scores_raw"]
        for binding in overlay.template_bindings
    )


def test_equal_structural_assignments_are_rejected_as_ambiguous() -> None:
    architecture = _analyze_transformer()
    original = next(
        node for node in architecture.nodes if node.node_id == "node:encoder_q_proj"
    )
    clone = original.model_copy(
        update={
            "node_id": "node:encoder_q_proj_clone",
            "input_ports": [
                port.model_copy(update={"port_id": "port:encoder_q_proj_clone.in0"})
                for port in original.input_ports
            ],
            "output_ports": [
                port.model_copy(update={"port_id": "port:encoder_q_proj_clone.out"})
                for port in original.output_ports
            ],
        }
    )
    source_edge = next(
        edge
        for edge in architecture.edges
        if edge.edge_id == "edge:encoder_q_proj:enc_q_split:0"
    )
    clone_edge = source_edge.model_copy(
        update={
            "edge_id": "edge:encoder_q_proj_clone:enc_q_split:0",
            "producer_id": clone.node_id,
            "producer_port": clone.output_ports[0].port_id,
        }
    )
    ambiguous = architecture.model_copy(
        update={
            "nodes": [*architecture.nodes, clone],
            "edges": [*architecture.edges, clone_edge],
        }
    )

    overlay, _ = apply_pattern_packs(ambiguous, load_registry())

    assert overlay.status == "matched"
    assert len(overlay.template_bindings) == 2
    assert any(
        reason.startswith(
            "ambiguous_template_binding:attention-exact:node:enc_scores_raw:"
        )
        for reason in overlay.reasons
    )


def test_opaque_binding_keeps_only_real_parent_identity() -> None:
    architecture = _analyze_transformer()
    registry = load_registry()
    template = registry.templates["attention.qkv-v1"]
    digest = exact_ir_digest(architecture)

    binding = create_template_binding(
        architecture,
        template,
        exact_ir_digest=digest,
        root_canonical_node_ids=["node:transformer"],
        fidelity="opaque",
    )

    assert binding.fidelity == "opaque"
    assert binding.root_canonical_node_ids == ["node:transformer"]
    assert binding.node_slots == {}
    assert binding.edge_slots == {}
    validate_template_binding(
        architecture,
        template,
        binding,
        exact_ir_digest=digest,
    )
    stale = binding.model_copy(update={"binding_digest": "0" * 64})
    with pytest.raises(ValueError, match="binding digest is stale"):
        validate_template_binding(
            architecture,
            template,
            stale,
            exact_ir_digest=digest,
        )


def test_binding_validates_node_edge_port_and_tensor_provenance() -> None:
    architecture = _analyze_transformer()
    edge = next(
        item
        for item in architecture.edges
        if item.edge_id == "edge:input.src:encoder_q_proj:0"
    )
    nodes = {node.node_id: node for node in architecture.nodes}
    tensor = next(item for item in architecture.tensors if item.tensor_id == edge.tensor_id)
    source = nodes[edge.producer_id]
    target = nodes[edge.consumer_id]
    source_port = next(
        port for port in source.output_ports if port.port_id == edge.producer_port
    )
    target_port = next(
        port for port in target.input_ports if port.port_id == edge.consumer_port
    )
    template = VisualTemplateManifest(
        template_id="test.provenance-v1",
        version="1.0.0",
        root_role="test",
        supported_ir_versions=["1.0"],
        slots=[
            {"slot_id": "source", "kind": "node", "accepts": [source.kind.value], "cardinality": "one"},
            {"slot_id": "target", "kind": "node", "accepts": [str(target.attributes["op_type"])], "cardinality": "one"},
            {"slot_id": "flow", "kind": "edge", "accepts": [edge.edge_type.value], "cardinality": "one"},
            {"slot_id": "source_port", "kind": "port", "accepts": [source_port.role], "cardinality": "one"},
            {"slot_id": "target_port", "kind": "port", "accepts": [target_port.role], "cardinality": "one"},
            {"slot_id": "value", "kind": "tensor", "accepts": [tensor.role], "cardinality": "one"},
        ],
        fallback_glyph="test",
        test_inventory=["provenance"],
    )
    digest = exact_ir_digest(architecture)

    binding = create_template_binding(
        architecture,
        template,
        exact_ir_digest=digest,
        root_canonical_node_ids=[target.node_id],
        node_slots={"source": [source.node_id], "target": [target.node_id]},
        edge_slots={"flow": [edge.edge_id]},
        port_slots={
            "source_port": [source_port.port_id],
            "target_port": [target_port.port_id],
        },
        tensor_slots={"value": [tensor.tensor_id]},
    )

    validate_template_binding(
        architecture,
        template,
        binding,
        exact_ir_digest=digest,
    )
    assert binding.evidence_ids == sorted(
        {
            *source.evidence_ids,
            *target.evidence_ids,
            *edge.evidence_ids,
            *tensor.evidence_ids,
        }
    )


def test_capture_selector_must_match_declared_entity() -> None:
    with pytest.raises(ValueError, match="cannot select a port capture"):
        PatternCapture(
            capture_id="invalid-port",
            entity="port",
            selector=PatternPredicate(
                predicate_id="node-only",
                stage=PatternStage.STRUCTURE,
                fact="node-kind",
                value="operator",
            ),
            cardinality="one",
        )
