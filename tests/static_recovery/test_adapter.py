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


def test_adapter_does_not_emit_confirmed_nodes_from_constructor_branch() -> None:
    source = b'''import torch.nn as nn

class ConditionalConstructor(nn.Module):
    def __init__(self, enabled):
        super().__init__()
        if enabled:
            self.left = nn.Linear(2, 2)
        else:
            self.right = nn.Linear(2, 2)

    def forward(self, x):
        return x
'''
    _, ir = PyTorchStaticAdapter().analyze(
        source,
        project_id="project:conditional-constructor",
        relative_file="model.py",
        entrypoint="model.py:ConditionalConstructor",
    )
    assert [node.node_id for node in ir.nodes] == ["node:input", "node:output"]
    assert [(item.code, item.blocking) for item in ir.unresolved] == [
        ("DYNAMIC_CONSTRUCTOR_CONTROL_FLOW", False)
    ]


def test_adapter_expands_each_direct_sequential_member_with_source_anchors() -> None:
    source = b'''import torch.nn as nn

class SequentialModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.blocks = nn.Sequential(nn.Linear(2, 4), nn.ReLU(), nn.Linear(4, 2))

    def forward(self, x):
        return self.blocks(x)
'''
    identity, ir = PyTorchStaticAdapter().analyze(
        source,
        project_id="project:sequential",
        relative_file="model.py",
        entrypoint="model.py:SequentialModel",
    )
    assert validate_architecture_semantics(ir, identity) == []
    assert [node.node_id for node in ir.nodes] == [
        "node:input",
        "node:sequentialmodel.blocks.0",
        "node:sequentialmodel.blocks.1",
        "node:sequentialmodel.blocks.2",
        "node:output",
    ]
    assert [(edge.source_node_id, edge.target_node_id) for edge in ir.edges] == [
        ("node:sequentialmodel.blocks.0", "node:sequentialmodel.blocks.1"),
        ("node:sequentialmodel.blocks.1", "node:sequentialmodel.blocks.2"),
        ("node:sequentialmodel.blocks.2", "node:output"),
        ("node:input", "node:sequentialmodel.blocks.0"),
    ]
    assert all(node.source_anchor_ids for node in ir.nodes[1:-1])


def test_adapter_expands_literal_ordered_dict_sequential_members() -> None:
    source = b'''from collections import OrderedDict
import torch.nn as nn

class NamedSequentialModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.blocks = nn.Sequential(OrderedDict([
            ("projection", nn.Linear(2, 4)),
            ("activation", nn.ReLU()),
        ]))

    def forward(self, x):
        return self.blocks(x)
'''
    identity, ir = PyTorchStaticAdapter().analyze(
        source,
        project_id="project:named-sequential",
        relative_file="model.py",
        entrypoint="model.py:NamedSequentialModel",
    )
    assert validate_architecture_semantics(ir, identity) == []
    assert [node.node_id for node in ir.nodes] == [
        "node:input",
        "node:namedsequentialmodel.blocks.projection",
        "node:namedsequentialmodel.blocks.activation",
        "node:output",
    ]
    assert [(edge.source_node_id, edge.target_node_id) for edge in ir.edges] == [
        ("node:namedsequentialmodel.blocks.activation", "node:output"),
        (
            "node:namedsequentialmodel.blocks.projection",
            "node:namedsequentialmodel.blocks.activation",
        ),
        ("node:input", "node:namedsequentialmodel.blocks.projection"),
    ]


def test_adapter_expands_literal_module_list_members_in_loop_order() -> None:
    source = b'''import torch.nn as nn

class ExplicitModuleList(nn.Module):
    def __init__(self):
        super().__init__()
        self.blocks = nn.ModuleList([nn.Linear(2, 4), nn.ReLU(), nn.Linear(4, 2)])

    def forward(self, x):
        for block in self.blocks:
            x = block(x)
        return x
'''
    identity, ir = PyTorchStaticAdapter().analyze(
        source,
        project_id="project:explicit-module-list",
        relative_file="model.py",
        entrypoint="model.py:ExplicitModuleList",
    )
    assert validate_architecture_semantics(ir, identity) == []
    assert [node.node_id for node in ir.nodes] == [
        "node:input",
        "node:explicitmodulelist.blocks.0",
        "node:explicitmodulelist.blocks.1",
        "node:explicitmodulelist.blocks.2",
        "node:output",
    ]
    assert [(edge.source_node_id, edge.target_node_id) for edge in ir.edges] == [
        ("node:explicitmodulelist.blocks.0", "node:explicitmodulelist.blocks.1"),
        ("node:explicitmodulelist.blocks.1", "node:explicitmodulelist.blocks.2"),
        ("node:explicitmodulelist.blocks.2", "node:output"),
        ("node:input", "node:explicitmodulelist.blocks.0"),
    ]


def test_adapter_selects_entrypoint_class_when_source_contains_multiple_modules() -> None:
    source = b'''import torch.nn as nn

class Auxiliary(nn.Module):
    def __init__(self):
        super().__init__()
        self.ignored = nn.ReLU()

    def forward(self, x):
        return self.ignored(x)

class Target(nn.Module):
    def __init__(self):
        super().__init__()
        self.selected = nn.Linear(2, 2)

    def forward(self, x):
        return self.selected(x)
'''
    identity, ir = PyTorchStaticAdapter().analyze(
        source,
        project_id="project:selected-entrypoint",
        relative_file="models.py",
        entrypoint="models.py:Target",
    )

    assert validate_architecture_semantics(ir, identity) == []
    assert ir.model.model_class == "Target"
    assert [node.node_id for node in ir.nodes] == [
        "node:input",
        "node:target.selected",
        "node:output",
    ]
