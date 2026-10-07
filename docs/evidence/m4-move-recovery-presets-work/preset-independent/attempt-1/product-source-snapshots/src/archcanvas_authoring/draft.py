"""Bounded tensor DAG authoring and nonexecuting source round-trip checks."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
import re
from typing import Any

from archcanvas_python import analyze_source


class DraftError(ValueError):
    """A concrete draft contract violation, safe to display in Studio."""

    def __init__(self, message: str, *, diagnostics: list[dict] | None = None):
        # Keep the English exception string compatible with existing clients.
        # Targets are supplied by validation, never recovered from that string
        # or a display label. Missing targets mean that no exact field is known.
        super().__init__(message)
        self.diagnostics = deepcopy(diagnostics or [])


def _diagnostic(code: str, message: str, technical: str, **details) -> dict:
    """JSON data only; expected is the contract and actual is the declaration."""
    return {"code": code, "message": message, "technical": technical,
            **{key: deepcopy(value) for key, value in details.items() if value is not None}}


def _fail(technical: str, code: str, message: str, **details):
    raise DraftError(technical, diagnostics=[_diagnostic(code, message, technical, **details)])


MAX_NODES = 128
MAX_EDGES = 384
IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
ENTRY = "model:AuthoredModel"


def _field(name, type, default, **constraints):
    return {"name": name, "type": type, "default": default, **constraints}


def _port(name, direction):
    return {"id": name, "name": name, "direction": direction, "type": "tensor"}


def _module(kind, category, description, fields=(), inputs=("input",), outputs=("output",)):
    return {"kind": kind, "label": kind, "category": category, "description": description,
            "defaults": {item["name"]: item["default"] for item in fields}, "parameters": list(fields),
            "ports": [_port(name, "in") for name in inputs] + [_port(name, "out") for name in outputs]}


_POS = {"min": 1, "max": 1000000}
_SPATIAL = {"min": 1, "max": 10000, "length": 2}
_CATALOG = [
    _module("Input", "io", "Declared tensor input; shape/dtype are static contracts, not observed runtime facts.", [
        _field("shape", "integer-array", [1, 16], min=1, max=1000000, minLength=1, maxLength=8),
        _field("dtype", "choice", "float32", options=["float32", "float64", "int64"]),
    ], inputs=()),
    _module("Output", "io", "Named model output.", inputs=("input",), outputs=()),
    _module("Linear", "dense", "Float32 affine transform of the final tensor dimension.", [
        _field("in_features", "integer", 16, **_POS), _field("out_features", "integer", 32, **_POS),
        _field("bias", "boolean", True),
    ]),
    _module("ReLU", "activation", "Elementwise ReLU without in-place mutation."),
    _module("GELU", "activation", "Elementwise GELU without in-place mutation.", [
        _field("approximate", "choice", "none", options=["none", "tanh"]),
    ]),
    _module("SiLU", "activation", "Elementwise SiLU without in-place mutation."),
    _module("Identity", "operator", "Preserves the declared tensor shape and dtype."),
    _module("Dropout", "regularization", "Non-in-place dropout; evaluation and training differ.", [
        _field("p", "number", 0.1, min=0, max=1),
    ]),
    _module("Flatten", "reshape", "Flattens an inclusive declared dimension range.", [
        _field("start_dim", "integer", 1, min=-8, max=7),
        _field("end_dim", "integer", -1, min=-8, max=7),
    ]),
    _module("Conv2d", "convolution", "Float32 NCHW/CHW convolution with integer spatial parameters.", [
        _field("in_channels", "integer", 3, **_POS), _field("out_channels", "integer", 16, **_POS),
        _field("kernel_size", "integer-array", [3, 3], **_SPATIAL),
        _field("stride", "integer-array", [1, 1], **_SPATIAL),
        _field("padding", "integer-array", [0, 0], min=0, max=10000, length=2),
        _field("dilation", "integer-array", [1, 1], **_SPATIAL),
        _field("groups", "integer", 1, **_POS), _field("bias", "boolean", True),
    ]),
    _module("MaxPool2d", "pooling", "Max pooling with tensor-only output and explicit floor/ceil mode.", [
        _field("kernel_size", "integer-array", [2, 2], **_SPATIAL),
        _field("stride", "integer-array", [2, 2], **_SPATIAL),
        _field("padding", "integer-array", [0, 0], min=0, max=10000, length=2),
        _field("dilation", "integer-array", [1, 1], **_SPATIAL),
        _field("ceil_mode", "boolean", False),
    ]),
    _module("AdaptiveAvgPool2d", "pooling", "Adaptive pooling to a fixed positive spatial shape.", [
        _field("output_size", "integer-array", [1, 1], **_SPATIAL),
    ]),
    _module("BatchNorm2d", "normalization", "Float32 four-dimensional channel normalization.", [
        _field("num_features", "integer", 16, **_POS), _field("eps", "number", 1e-5, min=1e-12, max=1),
        _field("momentum", "number", 0.1, min=0, max=1),
        _field("affine", "boolean", True), _field("track_running_stats", "boolean", True),
    ]),
    _module("LayerNorm", "normalization", "Float32 normalization over matching trailing dimensions.", [
        _field("normalized_shape", "integer-array", [16], min=1, max=1000000, minLength=1, maxLength=8),
        _field("eps", "number", 1e-5, min=1e-12, max=1), _field("elementwise_affine", "boolean", True),
    ]),
    _module("Embedding", "embedding", "Int64 index input to float32 embeddings; index bounds need runtime data.", [
        _field("num_embeddings", "integer", 1000, **_POS),
        _field("embedding_dim", "integer", 16, **_POS),
    ]),
    _module("Add", "merge", "Adds two equal-shape, equal-dtype tensors; broadcasting is outside this subset.",
            inputs=("left", "right")),
    _module("Concat", "merge", "Concatenates exactly two tensors with matching other dimensions.", [
        _field("dim", "integer", 1, min=-8, max=7),
    ], inputs=("a", "b")),
]
_BY_KIND = {item["kind"]: item for item in _CATALOG}
_FLOAT_MODULES = {"Linear", "Conv2d", "BatchNorm2d", "LayerNorm", "Embedding"}
_IR_CATEGORIES = {
    "Input": "input", "Output": "output", "Linear": "linear", "Embedding": "embedding",
    "BatchNorm2d": "norm", "LayerNorm": "norm", "ReLU": "activation", "GELU": "activation",
    "SiLU": "activation", "Dropout": "regularization", "Identity": "operator", "Flatten": "operator",
    "Conv2d": "convolution", "MaxPool2d": "pooling", "AdaptiveAvgPool2d": "pooling", "Concat": "operator",
}
_DISPLAY = {
    "Input": ("输入", "声明输入张量的形状与类型，再连接后续模块。"),
    "Output": ("输出", "连接模型结果；可以添加多个命名输出。"),
    "Linear": ("全连接", "把最后一维从输入宽度变为输出宽度，需要 float32 输入。"),
    "ReLU": ("ReLU 激活", "逐元素把负数置零，保留形状，不修改上游张量。"),
    "GELU": ("GELU 激活", "对浮点张量逐元素应用 GELU，可选 tanh 近似。"),
    "SiLU": ("SiLU 激活", "对浮点张量逐元素应用 SiLU，保留形状。"),
    "Identity": ("恒等映射", "直接传递输入，保留形状和类型。"),
    "Dropout": ("随机失活", "训练时以概率 p 丢弃元素，评估时直接传递输入。"),
    "Flatten": ("展平", "将起止维度之间的轴合并；默认保留批次维度。"),
    "Conv2d": ("二维卷积", "处理 CHW 或 NCHW 的 float32 张量，可设置卷积核、步长、填充和分组。"),
    "MaxPool2d": ("二维最大池化", "缩小 CHW 或 NCHW 的空间尺寸，保留每个窗口的最大值。"),
    "AdaptiveAvgPool2d": ("自适应平均池化", "将 CHW 或 NCHW 的空间尺寸变为指定大小。"),
    "BatchNorm2d": ("二维批归一化", "按通道归一化 NCHW 的 float32 张量，通道数须匹配。"),
    "LayerNorm": ("层归一化", "归一化 float32 张量的末尾若干维，形状须与设置匹配。"),
    "Embedding": ("词嵌入", "把 int64 索引变为 float32 向量；最后增加嵌入维度。"),
    "Add": ("张量相加", "相加两路形状与类型完全相同的张量，可用于残差连接。"),
    "Concat": ("张量拼接", "沿指定轴拼接两路张量，其他维度与类型须相同。"),
}
for _item in _CATALOG:
    _item["label"], _item["description"] = _DISPLAY[_item["kind"]]


def module_catalog() -> dict:
    """Return only modules with a generated-source and exact static IR contract."""
    return deepcopy({"schemaVersion": 1, "mode": "authored-draft", "modules": _CATALOG,
                     "unsupported": ["Sigmoid", "Tanh", "Conv1d", "AvgPool2d", "BatchNorm1d",
                                     "MultiheadAttention", "LSTM"],
                     "limits": {"nodes": MAX_NODES, "edges": MAX_EDGES},
                     "verification": "static-declared-tensors; no model import or execution"})


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _identity(value: Any, context: str) -> str:
    if not isinstance(value, str) or not IDENTITY.fullmatch(value):
        _fail(f"{context} must be a 1–64 character ASCII identity using letters, digits, underscores or hyphens.",
              "invalid_identity", "标识必须是 1–64 个 ASCII 字符，只能使用字母、数字、下划线和连字符。")
    return value


def _keys(value: Any, keys: set[str], context: str):
    if not isinstance(value, dict) or set(value) != keys:
        _fail(f"{context} requires exactly: {', '.join(sorted(keys))}.", "invalid_fields",
              "数据字段不符合建模约定；请保留规定字段，并移除额外字段。")


def _text(value: Any, context: str, limit=120) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= limit or any(ord(c) < 32 for c in value):
        _fail(f"{context} must be nonempty text of at most {limit} characters without control characters.",
              "invalid_text", f"名称须为 1–{limit} 个字符的文本，不能包含控制字符。")
    return value


def _parameter(value: Any, field: dict, node: str, node_id: str | None):
    context = f"{node}.{field['name']}"
    type_ = field["type"]
    if type_ == "boolean":
        valid = type(value) is bool
    elif type_ == "choice":
        valid = type(value) is str and value in field["options"]
    elif type_ in ("integer", "number"):
        valid = (type(value) is int if type_ == "integer" else type(value) in (int, float))
        valid = valid and field.get("min", -math.inf) <= value <= field.get("max", math.inf) and math.isfinite(value)
    elif type_ == "integer-array":
        valid = (isinstance(value, list) and field.get("minLength", field.get("length", 1)) <= len(value)
                 <= field.get("maxLength", field.get("length", 8)) and all(
                     type(item) is int and field.get("min", 1) <= item <= field.get("max", 1000000)
                     for item in value))
    else:
        valid = False
    if not valid:
        _fail(f"{context} violates its {type_} parameter contract.", "invalid_parameter",
              f"参数 {field['name']} 不符合该模块的类型、范围或长度要求，请按参数表修改。",
              nodeId=node_id, parameter=field["name"] if node_id else None)
    return deepcopy(value)


def _axis(value: int, rank: int, node: dict, parameter: str) -> int:
    if not -rank <= value < rank:
        _fail(f"{node['label']}: dimension {value} is outside rank {rank}.", "dimension_out_of_range",
              f"参数 {parameter} 为 {value}，但输入只有 {rank} 维；允许的维度索引是 {-rank} 到 {rank - 1}。",
              nodeId=node["id"], parameter=parameter, portId="a" if node["kind"] == "Concat" else "input",
              expected={"min": -rank, "max": rank - 1}, actual=value)
    return value % rank


def _infer(node: dict, inputs: list[dict]) -> dict:
    kind, p, name = node["kind"], node["parameters"], node["label"]
    if kind == "Input":
        result = {"shape": p["shape"][:], "dtype": p["dtype"]}
    else:
        shape, dtype = inputs[0]["shape"][:], inputs[0]["dtype"]
        if kind in _FLOAT_MODULES - {"Embedding"} and dtype != "float32":
            _fail(f"{name}: {kind} uses explicitly float32 parameters and requires a float32 input.",
                  "input_dtype_mismatch", f"{kind} 需要 float32 输入，当前上游声明为 {dtype}。请调整上游输入类型。",
                  nodeId=node["id"], portId="input", expected="float32", actual=dtype)
        if kind in ("ReLU", "GELU", "SiLU", "Dropout", "MaxPool2d", "AdaptiveAvgPool2d") and dtype not in ("float32", "float64"):
            _fail(f"{name}: this {kind} contract requires a floating-point tensor.",
                  "input_dtype_mismatch", f"{kind} 需要浮点输入，当前上游声明为 {dtype}。请使用 float32 或 float64。",
                  nodeId=node["id"], portId="input", expected=["float32", "float64"], actual=dtype)
        if kind == "Linear":
            if shape[-1] != p["in_features"]:
                _fail(f"{name}: final input dimension {shape[-1]} does not equal in_features {p['in_features']}.",
                      "linear_input_features_mismatch",
                      f"Linear 的输入末维为 {shape[-1]}，但 in_features 为 {p['in_features']}。请让 in_features 与上游末维一致。",
                      nodeId=node["id"], parameter="in_features", portId="input",
                      expected=p["in_features"], actual=shape[-1])
            shape[-1] = p["out_features"]
        elif kind == "Embedding":
            if dtype != "int64":
                _fail(f"{name}: Embedding requires int64 indices.", "input_dtype_mismatch",
                      f"Embedding 需要 int64 索引，当前上游声明为 {dtype}。请修改输入的 dtype。",
                      nodeId=node["id"], portId="input", expected="int64", actual=dtype)
            shape.append(p["embedding_dim"])
            dtype = "float32"
        elif kind == "LayerNorm":
            normalized = p["normalized_shape"]
            if shape[-len(normalized):] != normalized:
                _fail(f"{name}: trailing input dimensions must equal normalized_shape.", "layer_norm_shape_mismatch",
                      f"LayerNorm 的输入末尾形状为 {shape[-len(normalized):]}，与 normalized_shape {normalized} 不一致。",
                      nodeId=node["id"], parameter="normalized_shape", portId="input",
                      expected=normalized, actual=shape[-len(normalized):])
        elif kind == "BatchNorm2d":
            if len(shape) != 4:
                _fail(f"{name}: BatchNorm2d requires NCHW with matching num_features.", "input_rank_mismatch",
                      f"BatchNorm2d 需要 4 维 NCHW 输入，当前输入为 {len(shape)} 维。",
                      nodeId=node["id"], portId="input", expected=4, actual=len(shape))
            if shape[1] != p["num_features"]:
                _fail(f"{name}: BatchNorm2d requires NCHW with matching num_features.", "batch_norm_channels_mismatch",
                      f"BatchNorm2d 的输入通道数为 {shape[1]}，但 num_features 为 {p['num_features']}。",
                      nodeId=node["id"], parameter="num_features", portId="input",
                      expected=p["num_features"], actual=shape[1])
            if math.prod(shape) // shape[1] <= 1:
                _fail(f"{name}: this training-capable contract requires more than one value per channel.", "batch_norm_channel_samples",
                      "BatchNorm2d 的训练兼容约定要求每个通道至少有两个值；请增大批次或空间尺寸。",
                      nodeId=node["id"], portId="input", expected={"min": 2}, actual=math.prod(shape) // shape[1])
        elif kind in ("Conv2d", "MaxPool2d", "AdaptiveAvgPool2d"):
            if len(shape) not in (3, 4):
                _fail(f"{name}: {kind} requires a CHW or NCHW tensor.", "input_rank_mismatch",
                      f"{kind} 需要 3 维 CHW 或 4 维 NCHW 输入，当前输入为 {len(shape)} 维。",
                      nodeId=node["id"], portId="input", expected=[3, 4], actual=len(shape))
            if kind == "AdaptiveAvgPool2d":
                shape[-2:] = p["output_size"]
            else:
                if kind == "Conv2d":
                    if shape[-3] != p["in_channels"]:
                        _fail(f"{name}: channel dimension must equal in_channels.", "conv_input_channels_mismatch",
                              f"Conv2d 的输入通道数为 {shape[-3]}，但 in_channels 为 {p['in_channels']}。",
                              nodeId=node["id"], parameter="in_channels", portId="input",
                              expected=p["in_channels"], actual=shape[-3])
                    shape[-3] = p["out_channels"]
                spatial = []
                for size, kernel, stride, padding, dilation in zip(shape[-2:], p["kernel_size"], p["stride"], p["padding"], p["dilation"]):
                    numerator = size + 2 * padding - dilation * (kernel - 1) - 1
                    out = (numerator + (stride - 1 if p.get("ceil_mode") else 0)) // stride + 1
                    # Pool windows starting entirely in right padding are excluded.
                    if p.get("ceil_mode") and (out - 1) * stride >= size + padding:
                        out -= 1
                    if out <= 0:
                        _fail(f"{name}: {kind} would have a nonpositive output spatial dimension.", "nonpositive_spatial_output",
                              f"{kind} 的卷积核、步长、填充或膨胀设置会产生非正空间尺寸。请调整这些参数或增大输入尺寸。",
                              nodeId=node["id"], portId="input", expected={"min": 1}, actual=out)
                    spatial.append(out)
                shape[-2:] = spatial
        elif kind == "Flatten":
            start, end = _axis(p["start_dim"], len(shape), node, "start_dim"), _axis(p["end_dim"], len(shape), node, "end_dim")
            if start > end:
                _fail(f"{name}: start_dim must precede end_dim.", "flatten_dimension_order",
                      "Flatten 的 start_dim 必须位于 end_dim 之前或与其相同；请调整展平范围。",
                      nodeId=node["id"], parameter="start_dim", portId="input",
                      expected={"max": end}, actual=start)
            shape = shape[:start] + [math.prod(shape[start:end + 1])] + shape[end + 1:]
        elif kind in ("Add", "Concat"):
            other = inputs[1]
            other_port = "right" if kind == "Add" else "b"
            if dtype != other["dtype"]:
                _fail(f"{name}: both input tensors must have the same dtype and rank.", "merge_input_dtype_mismatch",
                      f"{kind} 两路输入的类型须一致，当前为 {dtype} 和 {other['dtype']}。",
                      nodeId=node["id"], portId=other_port, expected=dtype, actual=other["dtype"])
            if len(shape) != len(other["shape"]):
                _fail(f"{name}: both input tensors must have the same dtype and rank.", "merge_input_rank_mismatch",
                      f"{kind} 两路输入的维数须一致，当前为 {len(shape)} 维和 {len(other['shape'])} 维。",
                      nodeId=node["id"], portId=other_port, expected=len(shape), actual=len(other["shape"]))
            if kind == "Add":
                if shape != other["shape"]:
                    _fail(f"{name}: Add requires equal shapes; implicit broadcasting is unsupported.", "add_input_shape_mismatch",
                          f"Add 两路输入形状须完全一致，当前为 {shape} 和 {other['shape']}；此建模范围不支持隐式广播。",
                          nodeId=node["id"], portId="right", expected=shape, actual=other["shape"])
            else:
                axis = _axis(p["dim"], len(shape), node, "dim")
                if any(a != b for i, (a, b) in enumerate(zip(shape, other["shape"])) if i != axis):
                    _fail(f"{name}: Concat dimensions other than dim must match.", "concat_input_shape_mismatch",
                          f"Concat 仅允许第 {axis} 轴的尺寸不同，其他尺寸须一致；当前两路形状为 {shape} 和 {other['shape']}。",
                          nodeId=node["id"], parameter="dim", portId="b",
                          expected={"shape": shape, "exceptAxis": axis}, actual=other["shape"])
                shape[axis] += other["shape"][axis]
        result = {"shape": shape, "dtype": dtype}
    if len(result["shape"]) > 8 or math.prod(result["shape"]) > 1000000000:
        _fail(f"{name}: declared tensor exceeds the rank-8 / one-billion-element authoring budget.", "tensor_budget_exceeded",
              "声明的张量超出建模预算：最多 8 维、十亿个元素。请缩小输入或模块尺寸。")
    return result


def validate_draft(draft: dict, *, require_complete: bool = False) -> dict:
    """Normalize a separate draft; reject malformed or contradictory graphs.

    Incomplete graphs can be saved while building. Generation requires all
    ports to be bound and all nodes to contribute to at least one named output.
    Shape facts are deductions from declarations, not sampled execution.
    """
    _keys(draft, {"schemaVersion", "mode", "id", "title", "revision", "nodes", "edges"}, "Authored draft")
    if type(draft["schemaVersion"]) is not int or draft["schemaVersion"] != 1 or draft["mode"] != "authored-draft":
        _fail("Only authored-draft schemaVersion 1 is accepted; imported CanvasDocuments cannot be authored drafts.",
              "invalid_draft_schema", "建模只接受独立的 authored-draft 版本 1 草稿，不能把已导入的图当作建模草稿。")
    _identity(draft["id"], "Draft id")
    _text(draft["title"], "Draft title")
    if type(draft["revision"]) is not int or not 0 <= draft["revision"] <= 2**53 - 1:
        _fail("Draft revision must be a nonnegative safe integer.", "invalid_revision", "草稿版本号须为非负安全整数。")
    if not isinstance(draft["nodes"], list) or len(draft["nodes"]) > MAX_NODES or not isinstance(draft["edges"], list) or len(draft["edges"]) > MAX_EDGES:
        _fail("An authored draft permits at most 128 nodes and 384 connections.", "draft_budget_exceeded",
              "建模草稿最多允许 128 个模块、384 条连接，请缩小草稿。")
    normalized = {key: deepcopy(draft[key]) for key in ("schemaVersion", "mode", "id", "title", "revision")}
    # Do not point at a node if another raw node uses the same identity, even
    # when an earlier parameter failure precedes the duplicate-id check.
    identity_counts = Counter(raw.get("id") for raw in draft["nodes"] if isinstance(raw, dict)
                              and isinstance(raw.get("id"), str) and IDENTITY.fullmatch(raw["id"]))
    nodes = {}
    for raw in draft["nodes"]:
        _keys(raw, {"id", "kind", "label", "parameters", "position"}, "Draft node")
        identity = _identity(raw["id"], "Node id")
        diagnostic_identity = identity if identity_counts[identity] == 1 else None
        if identity in nodes:
            _fail(f"Duplicate node id: {identity}.", "duplicate_node_identity", "草稿存在重复模块标识，无法确定唯一目标。")
        if not isinstance(raw["kind"], str) or raw["kind"] not in _BY_KIND:
            _fail(f"Unsupported authored module: {raw['kind']}.", "unsupported_module",
                  "该模块不在当前可生成并验证的模块目录中，请选择左侧目录中的模块。", nodeId=diagnostic_identity)
        label = _text(raw["label"], f"{identity} label")
        spec = _BY_KIND[raw["kind"]]
        if not isinstance(raw["parameters"], dict) or set(raw["parameters"]) - set(spec["defaults"]):
            _fail(f"{label}: unknown parameter; only the registered fields are accepted.", "unknown_parameter",
                  "模块只接受参数表中已注册的字段，请移除未知参数。", nodeId=diagnostic_identity)
        params = {field["name"]: _parameter(raw["parameters"].get(field["name"], field["default"]), field, label, diagnostic_identity)
                  for field in spec["parameters"]}
        _keys(raw["position"], {"x", "y"}, f"{label} position")
        if any(type(v) not in (int, float) or abs(v) > 1000000 or not math.isfinite(v) for v in raw["position"].values()):
            _fail(f"{label}: position must contain finite coordinates within ±1000000.", "invalid_position",
                  "模块位置必须是有限坐标，且在正负一百万范围内。", nodeId=diagnostic_identity)
        if raw["kind"] == "Conv2d" and (params["in_channels"] % params["groups"] or params["out_channels"] % params["groups"]):
            _fail(f"{label}: groups must divide in_channels and out_channels.", "conv_groups_mismatch",
                  "Conv2d 的 groups 必须同时整除 in_channels 和 out_channels，请调整分组或通道数。",
                  nodeId=diagnostic_identity, parameter="groups" if diagnostic_identity else None)
        if raw["kind"] == "MaxPool2d" and any(p > k // 2 for p, k in zip(params["padding"], params["kernel_size"])):
            _fail(f"{label}: pool padding cannot exceed half the kernel size.", "pool_padding_out_of_range",
                  "MaxPool2d 的 padding 不能超过对应 kernel_size 的一半，请减小填充或增大池化核。",
                  nodeId=diagnostic_identity, parameter="padding" if diagnostic_identity else None)
        nodes[identity] = {"id": identity, "kind": raw["kind"], "label": label,
                           "parameters": params, "position": deepcopy(raw["position"])}
    edges, edge_ids, bound = [], set(), {}
    incoming, outgoing = {n: [] for n in nodes}, {n: [] for n in nodes}
    for raw in draft["edges"]:
        _keys(raw, {"id", "source", "target"}, "Draft connection")
        identity = _identity(raw["id"], "Connection id")
        if identity in edge_ids:
            _fail(f"Duplicate connection id: {identity}.", "duplicate_connection_identity", "草稿存在重复连接标识，无法确定唯一连接。")
        edge_ids.add(identity)
        for endpoint, direction in (("source", "out"), ("target", "in")):
            _keys(raw[endpoint], {"nodeId", "portId"}, f"Connection {identity} {endpoint}")
            node_id, port_id = raw[endpoint]["nodeId"], raw[endpoint]["portId"]
            if not isinstance(node_id, str) or node_id not in nodes or not isinstance(port_id, str) or not any(
                    p["id"] == port_id and p["direction"] == direction for p in _BY_KIND[nodes[node_id]["kind"]]["ports"]):
                _fail(f"Connection {identity}: {endpoint} must identify an exact declared {direction} port of its own node.",
                      "invalid_connection_endpoint", "连接端点须使用该模块已声明且方向正确的端口，请重新连接。",
                      edgeId=identity, endpoint=endpoint)
        key = (raw["target"]["nodeId"], raw["target"]["portId"])
        if key in bound:
            _fail(f"{key[0]}.{key[1]} already has a producer; remove that connection first.", "input_already_bound",
                  "该输入端口已有来源；请先移除原连接，再连接新的来源。", nodeId=key[0], portId=key[1])
        edge = deepcopy(raw)
        bound[key] = edge
        incoming[key[0]].append(edge)
        outgoing[edge["source"]["nodeId"]].append(edge)
        edges.append(edge)
    indegree = {n: len(incoming[n]) for n in nodes}
    queue = [n for n in nodes if indegree[n] == 0]
    order = []
    while queue:
        node_id = queue.pop(0)
        order.append(node_id)
        for edge in outgoing[node_id]:
            target = edge["target"]["nodeId"]
            indegree[target] -= 1
            if not indegree[target]:
                queue.append(target)
    if len(order) != len(nodes):
        _fail("Connections form a cycle; authored forward graphs must be acyclic.", "cyclic_graph",
              "连接形成了环路；当前建模需要有向无环图，请移除构成环路的连接。")
    issues, tensors = [], {}
    if not any(n["kind"] == "Input" for n in nodes.values()):
        issues.append(_diagnostic("missing-input", "请至少添加一个输入模块。", "Add at least one Input module."))
    if not any(n["kind"] == "Output" for n in nodes.values()):
        issues.append(_diagnostic("missing-output", "请至少添加一个输出模块。", "Add at least one Output module."))
    for identity in order:
        node = nodes[identity]
        required = [p["id"] for p in _BY_KIND[node["kind"]]["ports"] if p["direction"] == "in"]
        missing = [p for p in required if (identity, p) not in bound]
        if missing:
            issues.append(_diagnostic("unbound-input", f"{node['kind']} 的输入端口 {', '.join(missing)} 尚未连接，请连接上游模块。",
                                      f"{node['label']}: connect {', '.join(missing)}.", nodeId=identity,
                                      portIds=missing, portId=missing[0] if len(missing) == 1 else None))
        elif all(bound[identity, p]["source"]["nodeId"] in tensors for p in required):
            tensors[identity] = _infer(node, [tensors[bound[identity, p]["source"]["nodeId"]] for p in required])
    used = {n for n in nodes if nodes[n]["kind"] == "Output"}
    pending = list(used)
    while pending:
        for edge in incoming[pending.pop()]:
            producer = edge["source"]["nodeId"]
            if producer not in used:
                used.add(producer)
                pending.append(producer)
    unused = [n for n in nodes if n not in used]
    if unused:
        issues.append(_diagnostic("unused-node", "这些模块尚未通向命名输出；生成 Python 前请连接到输出，或移除未使用模块。",
                                  "Every module must contribute to a named Output before generating Python.", nodeIds=unused))
    normalized["nodes"], normalized["edges"] = list(nodes.values()), edges
    if require_complete and issues:
        raise DraftError("Draft is incomplete: " + " ".join(item["technical"] for item in issues), diagnostics=issues)
    return {"draft": normalized, "draftDigest": _digest(normalized), "complete": not issues,
            "issues": issues, "tensors": tensors, "order": order,
            "verification": "static-declared-tensors; no model execution"}


def _name(identity: str) -> str:
    return "node_" + hashlib.sha256(identity.encode()).hexdigest()[:16]


def _expression(node: dict, producers: dict, nodes: dict, tensors: dict) -> str:
    def arg(port):
        return _name(producers[node["id"], port]["source"]["nodeId"])
    if node["kind"] == "Add":
        return f"{arg('left')} + {arg('right')}"
    if node["kind"] == "Concat":
        rank = len(tensors[producers[node["id"], "a"]["source"]["nodeId"]]["shape"])
        # The declared rank proves this nonnegative axis is equivalent. Avoid
        # creating a spurious Unary tensor node for a negative scalar in the
        # frontend's intentionally bounded expression subset.
        axis = node["parameters"]["dim"] % rank
        return f"torch.cat(({arg('a')}, {arg('b')}), dim={axis})"
    return f"self.{_name(node['id'])}({arg('input')})"


def _source(validation: dict) -> str:
    draft = validation["draft"]
    nodes = {n["id"]: n for n in draft["nodes"]}
    inputs = [nodes[n] for n in validation["order"] if nodes[n]["kind"] == "Input"]
    modules = [nodes[n] for n in validation["order"] if nodes[n]["kind"] not in ("Input", "Output", "Add", "Concat")]
    outputs = [n for n in draft["nodes"] if n["kind"] == "Output"]
    producers = {(e["target"]["nodeId"], e["target"]["portId"]): e for e in draft["edges"]}
    names = [_name(n) for n in nodes]
    if len(set(names)) != len(names):
        raise DraftError("Generated symbol identity collision; generation refused.")
    lines = ["\"\"\"Fresh ArchCanvas authored model; static declarations are not runtime verification.\"\"\"",
             "import torch", "from torch import nn", "", "", "class AuthoredModel(nn.Module):",
             "    def __init__(self):", "        super().__init__()"]
    for node in modules:
        args = [f"{key}={value!r}" for key, value in node["parameters"].items()]
        if node["kind"] in _FLOAT_MODULES:
            args.append("dtype=torch.float32")
        lines.append(f"        self.{_name(node['id'])} = nn.{node['kind']}({', '.join(args)})")
    lines.extend(["", f"    def forward(self, {', '.join(_name(n['id']) for n in inputs)}):"])
    for identity in validation["order"]:
        node = nodes[identity]
        if node["kind"] not in ("Input", "Output"):
            lines.append(f"        {_name(identity)} = {_expression(node, producers, nodes, validation['tensors'])}")
    entries = [f"{n['id']!r}: {_name(producers[n['id'], 'input']['source']['nodeId'])}" for n in outputs]
    lines.append("        return {" + ", ".join(entries) + "}")
    return "\n".join(lines) + "\n"


def verify_generated(draft: dict, architecture: dict) -> dict:
    """Compare a freshly re-analyzed graph to the independently declared DAG.

    Exact node cardinality, constructor parameters, scalar operator arguments,
    named ports, tensor producer identities, root membership and output slots
    are checked. No imported CanvasDocument is accepted by this API.
    """
    validated = validate_draft(draft, require_complete=True)
    draft = validated["draft"]
    nodes = {n["id"]: n for n in draft["nodes"]}
    producers = {(e["target"]["nodeId"], e["target"]["portId"]): e for e in draft["edges"]}
    if not isinstance(architecture, dict) or architecture.get("entry") != ENTRY:
        raise DraftError("Generated static analysis has an unexpected entry.")
    expected_source = _source(validated)
    if architecture.get("sources") != [{"path": "model.py", "content": expected_source,
                                        "digest": hashlib.sha256(expected_source.encode()).hexdigest()}]:
        raise DraftError("Generated source bytes differ from the independently declared source contract.")
    actual = architecture.get("nodes")
    edges = architecture.get("edges")
    if not isinstance(actual, list) or not isinstance(edges, list) or len(actual) != len(nodes) + 1:
        raise DraftError("Generated static graph node inventory differs from the authored draft.")
    if any(not isinstance(n, dict) or not isinstance(n.get("id"), str) for n in actual) or len({n['id'] for n in actual}) != len(actual):
        raise DraftError("Generated static graph has malformed or duplicate node identities.")
    root = next((n for n in actual if n["id"] == "call:instance:model.AuthoredModel"), None)
    if root is None or root.get("category") != "container" or root.get("evidence") != "source" or root.get("kind") != "Module":
        raise DraftError("Generated model root is not an independently parsed module container.")
    bindings, mapped = {}, {}
    for identity, node in nodes.items():
        kind = node["kind"]
        if kind == "Input":
            matches = [n for n in actual if n.get("kind") == "Input" and n.get("label") == _name(identity)]
        elif kind == "Output":
            matches = [n for n in actual if n.get("kind") == "Output" and n.get("outputPath") == [{"kind": "key", "key": identity}]]
        elif kind in ("Add", "Concat"):
            expression = _expression(node, producers, nodes, validated["tensors"])
            line = expected_source.splitlines().index(f"        {_name(identity)} = {expression}") + 1
            matches = [n for n in actual if n.get("kind") == kind and n.get("source", {}).get("expression") == expression
                       and n.get("source", {}).get("line") == line]
        else:
            matches = [n for n in actual if n.get("kind") == kind and n.get("instanceId") == "instance:model.AuthoredModel." + _name(identity)]
        if len(matches) != 1:
            raise DraftError(f"{node['label']}: generated static analysis does not have exactly one matching {kind} node.")
        match = matches[0]
        if match.get("parentId") != root["id"] or match.get("children") != [] or match.get("evidence") == "opaque":
            raise DraftError(f"{node['label']}: generated node containment/evidence differs from its authoring contract.")
        params = {} if kind in ("Input", "Output", "Add", "Concat") else deepcopy(node["parameters"])
        if kind in _FLOAT_MODULES:
            params["dtype"] = {"expression": "torch.float32", "origin": "unknown"}
        if match.get("parameters") != params:
            raise DraftError(f"{node['label']}: generated constructor parameters differ from the declared draft.")
        bindings[identity], mapped[identity] = match["id"], match
    if len(set(bindings.values())) != len(bindings):
        raise DraftError("Generated static graph aliases distinct authored operations.")
    if Counter(root.get("children", [])) != Counter(bindings.values()) or root.get("parentId") is not None:
        raise DraftError("Generated root membership differs from the authored node inventory.")
    ancestors = {}
    for identity in validated["order"]:
        direct = {e["source"]["nodeId"] for e in draft["edges"] if e["target"]["nodeId"] == identity}
        ancestors[identity] = direct | set().union(*(ancestors[n] for n in direct)) if direct else set()
    residual_ports = {}
    for identity, node in nodes.items():
        if node["kind"] == "Add":
            left = producers[identity, "left"]["source"]["nodeId"]
            right = producers[identity, "right"]["source"]["nodeId"]
            if left != right:
                if left in ancestors[right]:
                    residual_ports[identity] = "left"
                elif right in ancestors[left]:
                    residual_ports[identity] = "right"
    ports = {}
    for identity, node in nodes.items():
        match = mapped[identity]
        category = ("residual" if identity in residual_ports else "operator") if node["kind"] == "Add" else _IR_CATEGORIES[node["kind"]]
        evidence = "source" if node["kind"] in ("Input", "Output", "Add") else "contract"
        if match.get("category") != category or match.get("evidence") != evidence or "repeat" in match:
            raise DraftError(f"{node['label']}: generated category/evidence/repetition differs from the authoring contract.")
        if node["kind"] not in ("Input", "Output", "Add", "Concat") and match.get("callId") != match["id"]:
            raise DraftError(f"{node['label']}: generated invocation identity is invalid.")
        names = {p["id"]: (p["id"], p["direction"]) for p in _BY_KIND[node["kind"]]["ports"]}
        if node["kind"] == "Input":
            names = {"output": (_name(identity), "out")}
        elif node["kind"] == "Output":
            names = {"input": ("value", "in")}
        elif node["kind"] == "Concat":
            names = {"a": ("arg0", "in"), "b": ("arg0.1", "in"), "output": ("output", "out")}
        actual_ports = match.get("ports")
        if not isinstance(actual_ports, list) or len(actual_ports) != len(names):
            raise DraftError(f"{node['label']}: generated port inventory differs from its declared contract.")
        ordinals = {"in": 0, "out": 0}
        for draft_port, (name, direction) in names.items():
            expected = f"{match['id']}:{direction}:{name}"
            role = "residual" if residual_ports.get(identity) == draft_port else "data"
            expected_port = {"id": expected, "name": name, "direction": direction,
                             "role": role, "ordinal": ordinals[direction]}
            ordinals[direction] += 1
            found = [p for p in actual_ports if p == expected_port]
            if len(found) != 1:
                raise DraftError(f"{node['label']}.{draft_port}: generated exact port binding is invalid.")
            ports[identity, draft_port] = expected
    input_order = [nodes[n] for n in validated["order"] if nodes[n]["kind"] == "Input"]
    root_ports = [{"id": f"{root['id']}:in:{_name(n['id'])}", "name": _name(n["id"]), "direction": "in",
                   "role": "data", "ordinal": i} for i, n in enumerate(input_order)]
    actual_root_ports = root.get("ports")
    if not isinstance(actual_root_ports, list) or len(actual_root_ports) != len(root_ports) or any(
            not any(p == expected for p in actual_root_ports) for expected in root_ports):
        raise DraftError("Generated root input port inventory differs from the declared inputs.")
    expected_edges = []
    for edge in draft["edges"]:
        s, t = edge["source"], edge["target"]
        out_name = _name(s["nodeId"]) if nodes[s["nodeId"]]["kind"] == "Input" else "output"
        expected_edges.append((bindings[s["nodeId"]], ports[s["nodeId"], s["portId"]],
                               bindings[t["nodeId"]], ports[t["nodeId"], t["portId"]],
                               f"tensor:{bindings[s['nodeId']]}:{out_name}",
                               "residual" if residual_ports.get(t["nodeId"]) == t["portId"] else "data"))
    for identity, node in nodes.items():
        if node["kind"] == "Input":
            name = _name(identity)
            expected_edges.append((bindings[identity], ports[identity, "output"], root["id"],
                                   f"{root['id']}:in:{name}", f"tensor:{bindings[identity]}:{name}", "data"))
    try:
        observed_edges = [(e["source"]["nodeId"], e["source"]["portId"], e["target"]["nodeId"],
                           e["target"]["portId"], e["tensorId"], e["role"]) for e in edges]
        edge_identity_unique = len({e["id"] for e in edges}) == len(edges)
    except (KeyError, TypeError) as exc:
        raise DraftError("Generated graph contains malformed tensor relations.") from exc
    if not edge_identity_unique or Counter(observed_edges) != Counter(expected_edges):
        raise DraftError("Generated exact tensor producers/consumers/ports differ from the declared DAG.")
    return {"status": "passed", "scope": "exact-static-dag-and-declared-tensor-compatibility",
            "modelExecution": "not_run", "nodes": len(nodes), "edges": len(draft["edges"]),
            "nodeBindings": bindings, "portBindings": {n: {p: v for (i, p), v in ports.items() if i == n} for n in nodes},
            "scalarNormalizations": {n["id"]: {"declaredDim": n["parameters"]["dim"],
                "effectiveDim": n["parameters"]["dim"] % len(validated["tensors"][producers[n["id"], "a"]["source"]["nodeId"]]["shape"])}
                for n in draft["nodes"] if n["kind"] == "Concat"},
            "limitations": ["Input shapes and dtypes are declarations, not runtime observations.",
                            "Embedding index bounds, memory allocation, numerical behavior and train/eval execution are unverified.",
                            "This is a fresh managed model, not a structural rewrite of imported source."]}


def generate_model(draft: dict) -> dict:
    """Generate new Python bytes and independently reconcile their static IR."""
    validation = validate_draft(draft, require_complete=True)
    source = _source(validation)
    architecture = analyze_source(source, ENTRY)
    verification = verify_generated(validation["draft"], architecture)
    return {"draft": validation["draft"], "draftDigest": validation["draftDigest"], "entry": ENTRY,
            "source": source, "architecture": architecture, "nodeBindings": verification["nodeBindings"],
            "portBindings": verification["portBindings"], "tensors": validation["tensors"], "verification": verification}
