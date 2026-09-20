from __future__ import annotations

from pathlib import Path

from archcanvas_core.semantic_validation import validate_architecture_semantics
from archcanvas_pytorch.static import PyTorchStaticAdapter, PyTorchStaticScanner


def _source() -> bytes:
    return (Path(__file__).resolve().parents[2] / "fixtures" / "concat_static_v1" / "source" / "model.py").read_bytes()


def test_scanner_recovers_cat_merge_with_both_inputs() -> None:
    result = PyTorchStaticScanner().scan(_source())
    assert [(item.name, item.operation, item.inputs) for item in result.merges] == [
        ("merge:merged", "torch.cat", ["left", "right"])
    ]


def test_adapter_emits_merge_node_and_edges() -> None:
    source, ir = PyTorchStaticAdapter().analyze(_source(), project_id="project:concat-static-v1", relative_file="model.py", entrypoint="model.py:FusionModel")
    assert validate_architecture_semantics(ir, source) == []
    merge = next(node for node in ir.nodes if node.kind.value == "merge")
    assert merge.op_type == "torch.cat"
    assert merge.metadata == {"input_count": 2}
    assert {(edge.source_node_id, edge.target_node_id) for edge in ir.edges if edge.target_node_id == merge.node_id} == {
        ("node:fusionmodel.left", merge.node_id),
        ("node:fusionmodel.right", merge.node_id),
    }
