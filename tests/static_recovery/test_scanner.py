from __future__ import annotations

from pathlib import Path

from archcanvas_pytorch.static import PyTorchStaticScanner


def test_scanner_recovers_transformer_constructor_and_forward_topology(before_raw) -> None:
    result = PyTorchStaticScanner().scan(before_raw)
    assert result.model_classes == ["EncoderModel"]
    assert [(item.attribute_path, item.op_type, item.container) for item in result.modules] == [
        ("embedding", "torch.nn.Embedding", None),
        ("layers", "torch.nn.TransformerEncoderLayer", "ModuleList"),
        ("norm", "torch.nn.LayerNorm", None),
        ("head", "torch.nn.Linear", None),
    ]
    assert [(edge.source, edge.target) for edge in result.edges] == [
        ("embedding", "layers"),
        ("head", "output"),
        ("input", "embedding"),
        ("layers", "norm"),
        ("norm", "head"),
    ]
    assert result.unresolved == []


def test_scanner_recovers_parameter_provenance_and_module_list_repeat(before_raw) -> None:
    result = PyTorchStaticScanner().scan(before_raw)
    layers = next(item for item in result.modules if item.attribute_path == "layers")
    assert (layers.repeat_count, layers.repeat_symbol) == (None, "depth")
    assert [(item.name, item.source_name, item.value, item.expression, item.origin) for item in layers.parameters] == [
        ("d_model", "d_model", None, "d_model", "argument"),
        ("num_heads", "nhead", 8, None, "literal"),
        ("dropout", "dropout", 0.1, None, "literal"),
        ("batch_first", "batch_first", True, None, "literal"),
    ]


def test_scanner_classifies_static_parameter_origins_without_evaluating_expressions() -> None:
    source = b'''import torch.nn as nn

WIDTH = 12

class Configured(nn.Module):
    def __init__(self, config, features):
        super().__init__()
        self.proj = nn.Linear(WIDTH, config.classes)
        self.out = nn.Linear(features * 2, 4)

    def forward(self, x):
        return self.out(self.proj(x))
'''
    result = PyTorchStaticScanner().scan(source)
    parameters = [parameter for module in result.modules for parameter in module.parameters]
    assert [(item.name, item.origin, item.value, item.expression) for item in parameters] == [
        ("in_features", "constant", 12, "WIDTH"),
        ("out_features", "config_attribute", None, "config.classes"),
        ("in_features", "computed", None, "features * 2"),
        ("out_features", "literal", 4, None),
    ]
    assert [item.code for item in result.unresolved] == ["UNRESOLVED_PARAMETER_PROVENANCE"]


def test_scanner_marks_dynamic_control_flow_unresolved() -> None:
    source = b'''import torch.nn as nn

class Conditional(nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(4, 4)

    def forward(self, x):
        if x.shape[0] > 1:
            return self.linear(x)
        return x
'''
    result = PyTorchStaticScanner().scan(source)
    assert result.model_classes == ["Conditional"]
    assert [item.code for item in result.unresolved] == ["DYNAMIC_CONTROL_FLOW"]


def test_scanner_fails_closed_for_constructor_control_flow() -> None:
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
    result = PyTorchStaticScanner().scan(source)
    assert result.modules == []
    assert [(item.code, item.message) for item in result.unresolved] == [
        ("DYNAMIC_CONSTRUCTOR_CONTROL_FLOW", "if in __init__")
    ]


def test_scanner_expands_sequential_members_in_order() -> None:
    source = b'''import torch.nn as nn

class SequentialModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.blocks = nn.Sequential(nn.Linear(2, 4), nn.ReLU(), nn.Linear(4, 2))

    def forward(self, x):
        return self.blocks(x)
'''
    result = PyTorchStaticScanner().scan(source)
    assert [(item.attribute_path, item.op_type, item.container) for item in result.modules] == [
        ("blocks.0", "torch.nn.Linear", "Sequential"),
        ("blocks.1", "torch.nn.ReLU", "Sequential"),
        ("blocks.2", "torch.nn.Linear", "Sequential"),
    ]
    assert [(item.source, item.target) for item in result.edges] == [
        ("blocks.0", "blocks.1"),
        ("blocks.1", "blocks.2"),
        ("blocks.2", "output"),
        ("input", "blocks.0"),
    ]


def test_scanner_expands_literal_ordered_dict_sequential_members_in_order() -> None:
    source = b'''from collections import OrderedDict
import torch.nn as nn

class NamedSequentialModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.blocks = nn.Sequential(OrderedDict([
            ("projection", nn.Linear(2, 4)),
            ("activation", nn.ReLU()),
            ("head", nn.Linear(4, 2)),
        ]))

    def forward(self, x):
        return self.blocks(x)
'''
    result = PyTorchStaticScanner().scan(source)
    assert [(item.attribute_path, item.op_type, item.container) for item in result.modules] == [
        ("blocks.projection", "torch.nn.Linear", "Sequential"),
        ("blocks.activation", "torch.nn.ReLU", "Sequential"),
        ("blocks.head", "torch.nn.Linear", "Sequential"),
    ]
    assert [(item.source, item.target) for item in result.edges] == [
        ("blocks.activation", "blocks.head"),
        ("blocks.head", "output"),
        ("blocks.projection", "blocks.activation"),
        ("input", "blocks.projection"),
    ]
    assert result.unresolved == []


def test_scanner_marks_dynamic_ordered_dict_sequential_members_unresolved() -> None:
    source = b'''from collections import OrderedDict
import torch.nn as nn

class DynamicNamedSequential(nn.Module):
    def __init__(self, members):
        super().__init__()
        self.blocks = nn.Sequential(OrderedDict(members))
'''
    result = PyTorchStaticScanner().scan(source)
    assert result.modules == []
    assert [(item.code, item.message) for item in result.unresolved] == [
        ("UNRESOLVED_CONTAINER_MEMBER", "blocks")
    ]


def test_scanner_expands_literal_module_list_members_in_loop_order() -> None:
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
    result = PyTorchStaticScanner().scan(source)
    assert [(item.attribute_path, item.op_type, item.container) for item in result.modules] == [
        ("blocks.0", "torch.nn.Linear", "ModuleList"),
        ("blocks.1", "torch.nn.ReLU", "ModuleList"),
        ("blocks.2", "torch.nn.Linear", "ModuleList"),
    ]
    assert [(item.source, item.target) for item in result.edges] == [
        ("blocks.0", "blocks.1"),
        ("blocks.1", "blocks.2"),
        ("blocks.2", "output"),
        ("input", "blocks.0"),
    ]
    assert result.unresolved == []


def test_scanner_does_not_partially_recover_dynamic_module_list_members() -> None:
    source = b'''import torch.nn as nn

class DynamicModuleList(nn.Module):
    def __init__(self, member):
        super().__init__()
        self.blocks = nn.ModuleList([nn.Linear(2, 2), member])
'''
    result = PyTorchStaticScanner().scan(source)
    assert result.modules == []
    assert [(item.code, item.message) for item in result.unresolved] == [
        ("UNRESOLVED_CONTAINER_MEMBER", "blocks")
    ]


def test_scanner_resolves_direct_torch_nn_imports() -> None:
    source = b'''from torch.nn import Linear, Module

class DirectImports(Module):
    def __init__(self):
        super().__init__()
        self.proj = Linear(4, 2)

    def forward(self, x):
        return self.proj(x)
'''
    result = PyTorchStaticScanner().scan(source)
    assert result.model_classes == ["DirectImports"]
    assert [(item.attribute_path, item.op_type) for item in result.modules] == [
        ("proj", "torch.nn.Linear")
    ]


def test_scanner_marks_residual_addition_without_guessing_merge_node() -> None:
    source = (
        Path(__file__).resolve().parents[2] / "fixtures" / "resnet_static_v1" / "source" / "model.py"
    ).read_bytes()
    result = PyTorchStaticScanner().scan(source)
    assert [(edge.source, edge.target, edge.kind) for edge in result.edges] == [
        ("conv1", "conv2", "data"),
        ("conv1", "conv2", "residual"),
        ("conv2", "relu", "data"),
        ("input", "conv1", "data"),
        ("relu", "output", "data"),
    ]


def test_scanner_recovers_bounded_functional_calls_with_known_producers() -> None:
    source = b'''import torch
import torch.nn as nn
import torch.nn.functional as F

class FunctionalModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.proj = nn.Linear(2, 2)

    def forward(self, x):
        x = self.proj(x)
        x = F.gelu(x)
        return x
'''
    result = PyTorchStaticScanner().scan(source)
    assert [(item.name, item.operation, item.input) for item in result.functions] == [
        ("function:x.12", "torch.nn.functional.gelu", "proj"),
    ]
    assert [(edge.source, edge.target) for edge in result.edges] == [
        ("function:x.12", "output"),
        ("input", "proj"),
        ("proj", "function:x.12"),
    ]


def test_scanner_does_not_confirm_functional_call_without_a_known_producer() -> None:
    source = b'''import torch.nn as nn
import torch.nn.functional as F

class FunctionalModel(nn.Module):
    def forward(self, x):
        unknown = F.relu(y)
        return unknown
'''
    result = PyTorchStaticScanner().scan(source)
    assert result.functions == []
    assert [(item.code, item.message) for item in result.unresolved] == [
        ("UNRESOLVED_FUNCTION_INPUT", "torch.nn.functional.relu")
    ]


def test_scanner_recovers_functional_return_and_distinct_repeated_assignments() -> None:
    source = b'''import torch.nn as nn
import torch.nn.functional as F

class FunctionalModel(nn.Module):
    def forward(self, x):
        x = F.relu(x)
        x = F.gelu(x)
        return F.silu(x)
'''
    result = PyTorchStaticScanner().scan(source)
    assert [(item.name, item.operation, item.input) for item in result.functions] == [
        ("function:x.6", "torch.nn.functional.relu", "input"),
        ("function:x.7", "torch.nn.functional.gelu", "function:x.6"),
        ("function:return.8", "torch.nn.functional.silu", "function:x.7"),
    ]
    assert [(edge.source, edge.target) for edge in result.edges] == [
        ("function:return.8", "output"),
        ("function:x.6", "function:x.7"),
        ("function:x.7", "function:return.8"),
        ("input", "function:x.6"),
    ]
