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
