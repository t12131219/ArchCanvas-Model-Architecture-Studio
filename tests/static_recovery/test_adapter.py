from __future__ import annotations

from pathlib import Path

from archcanvas_core.semantic_validation import validate_architecture_semantics
from archcanvas_pytorch.static import PyTorchStaticAdapter


def test_adapter_emits_strict_source_identity_and_architecture_ir(before_raw) -> None:
    source, ir = PyTorchStaticAdapter().analyze(
        before_raw,
        project_id="project:transformer-static-v1",
        relative_file="model.py",
        entrypoint="model.py:EncoderModel",
    )
    assert validate_architecture_semantics(ir, source) == []
    assert [node.node_id for node in ir.nodes] == [
        "node:input",
        "node:encodermodel.embedding",
        "node:encodermodel.layers",
        "node:encodermodel.norm",
        "node:encodermodel.head",
        "node:output",
    ]
    assert [(edge.source_node_id, edge.target_node_id) for edge in ir.edges] == [
        ("node:encodermodel.embedding", "node:encodermodel.layers"),
        ("node:encodermodel.head", "node:output"),
        ("node:input", "node:encodermodel.embedding"),
        ("node:encodermodel.layers", "node:encodermodel.norm"),
        ("node:encodermodel.norm", "node:encodermodel.head"),
    ]
    layers = ir.node("node:encodermodel.layers")
    assert [(item.name, item.source_name, item.value, item.expression, item.origin.kind.value) for item in layers.parameters] == [
        ("d_model", "d_model", None, "d_model", "argument"),
        ("num_heads", "nhead", 8, None, "literal"),
        ("dropout", "dropout", 0.1, None, "literal"),
        ("batch_first", "batch_first", True, None, "literal"),
    ]
    assert [(item.repeat_id, item.count, item.count_symbol) for item in ir.repeats] == [
        ("repeat:encodermodel.layers", None, "depth")
    ]
    parameter_anchor_ids = [anchor_id for item in layers.parameters for anchor_id in item.origin.anchor_ids]
    assert set(parameter_anchor_ids) <= {anchor.anchor_id for anchor in source.anchors}
    assert all(item.evidence[0].anchor_id in parameter_anchor_ids for item in layers.parameters)


def test_adapter_preserves_residual_edge_kind() -> None:
    source_bytes = (
        Path(__file__).resolve().parents[2] / "fixtures" / "resnet_static_v1" / "source" / "model.py"
    ).read_bytes()
    source, ir = PyTorchStaticAdapter().analyze(
        source_bytes,
        project_id="project:resnet-static-v1",
        relative_file="model.py",
        entrypoint="model.py:ResidualBlock",
    )
    assert validate_architecture_semantics(ir, source) == []
    assert [(edge.source_node_id, edge.target_node_id) for edge in ir.edges if edge.kind.value == "residual"] == [
        ("node:residualblock.conv1", "node:residualblock.conv2")
    ]


def test_adapter_reconciles_identities_after_irrelevant_blank_line_change(before_raw) -> None:
    adapter = PyTorchStaticAdapter()
    initial_source, initial_ir = adapter.analyze(
        before_raw,
        project_id="project:transformer-static-v1",
        relative_file="model.py",
        entrypoint="model.py:EncoderModel",
    )
    refreshed_source, refreshed_ir = adapter.analyze(
        before_raw.replace(b"\n\nclass EncoderModel", b"\n\n\nclass EncoderModel"),
        project_id="project:transformer-static-v1",
        relative_file="model.py",
        entrypoint="model.py:EncoderModel",
        previous_source=initial_source,
    )
    assert [item.identity_id for item in refreshed_source.identities] == [
        item.identity_id for item in initial_source.identities
    ]
    assert [item.decision.value for item in refreshed_source.reconciliations] == [
        "exact",
        "exact",
        "exact",
        "exact",
    ]
    assert [item.node_id for item in refreshed_ir.nodes] == [item.node_id for item in initial_ir.nodes]
    assert refreshed_ir.unresolved == []
