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
        raise DraftError(f"{context} must be a 1–64 character ASCII identity using letters, digits, underscores or hyphens.")
    return value


def _keys(value: Any, keys: set[str], context: str):
    if not isinstance(value, dict) or set(value) != keys:
        raise DraftError(f"{context} requires exactly: {', '.join(sorted(keys))}.")


def _text(value: Any, context: str, limit=120) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= limit or any(ord(c) < 32 for c in value):
        raise DraftError(f"{context} must be nonempty text of at most {limit} characters without control characters.")
    return value


def _parameter(value: Any, field: dict, node: str):
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
        raise DraftError(f"{context} violates its {type_} parameter contract.")
    return deepcopy(value)


def _axis(value: int, rank: int, node: str) -> int:
    if not -rank <= value < rank:
        raise DraftError(f"{node}: dimension {value} is outside rank {rank}.")
    return value % rank


def _infer(node: dict, inputs: list[dict]) -> dict:
    kind, p, name = node["kind"], node["parameters"], node["label"]
    if kind == "Input":
        result = {"shape": p["shape"][:], "dtype": p["dtype"]}
    else:
        shape, dtype = inputs[0]["shape"][:], inputs[0]["dtype"]
        if kind in _FLOAT_MODULES - {"Embedding"} and dtype != "float32":
            raise DraftError(f"{name}: {kind} uses explicitly float32 parameters and requires a float32 input.")
        if kind in ("ReLU", "GELU", "SiLU", "Dropout", "MaxPool2d", "AdaptiveAvgPool2d") and dtype not in ("float32", "float64"):
            raise DraftError(f"{name}: this {kind} contract requires a floating-point tensor.")
        if kind == "Linear":
            if shape[-1] != p["in_features"]:
                raise DraftError(f"{name}: final input dimension {shape[-1]} does not equal in_features {p['in_features']}.")
            shape[-1] = p["out_features"]
        elif kind == "Embedding":
            if dtype != "int64":
                raise DraftError(f"{name}: Embedding requires int64 indices.")
            shape.append(p["embedding_dim"])
            dtype = "float32"
        elif kind == "LayerNorm":
            normalized = p["normalized_shape"]
            if shape[-len(normalized):] != normalized:
                raise DraftError(f"{name}: trailing input dimensions must equal normalized_shape.")
        elif kind == "BatchNorm2d":
            if len(shape) != 4 or shape[1] != p["num_features"]:
                raise DraftError(f"{name}: BatchNorm2d requires NCHW with matching num_features.")
            if math.prod(shape) // shape[1] <= 1:
                raise DraftError(f"{name}: this training-capable contract requires more than one value per channel.")
        elif kind in ("Conv2d", "MaxPool2d", "AdaptiveAvgPool2d"):
            if len(shape) not in (3, 4):
                raise DraftError(f"{name}: {kind} requires a CHW or NCHW tensor.")
            if kind == "AdaptiveAvgPool2d":
                shape[-2:] = p["output_size"]
            else:
                if kind == "Conv2d":
                    if shape[-3] != p["in_channels"]:
                        raise DraftError(f"{name}: channel dimension must equal in_channels.")
                    shape[-3] = p["out_channels"]
                spatial = []
                for size, kernel, stride, padding, dilation in zip(shape[-2:], p["kernel_size"], p["stride"], p["padding"], p["dilation"]):
                    numerator = size + 2 * padding - dilation * (kernel - 1) - 1
                    out = (numerator + (stride - 1 if p.get("ceil_mode") else 0)) // stride + 1
                    # Pool windows starting entirely in right padding are excluded.
                    if p.get("ceil_mode") and (out - 1) * stride >= size + padding:
                        out -= 1
                    if out <= 0:
                        raise DraftError(f"{name}: {kind} would have a nonpositive output spatial dimension.")
                    spatial.append(out)
                shape[-2:] = spatial
        elif kind == "Flatten":
            start, end = _axis(p["start_dim"], len(shape), name), _axis(p["end_dim"], len(shape), name)
            if start > end:
                raise DraftError(f"{name}: start_dim must precede end_dim.")
            shape = shape[:start] + [math.prod(shape[start:end + 1])] + shape[end + 1:]
        elif kind in ("Add", "Concat"):
            other = inputs[1]
            if dtype != other["dtype"] or len(shape) != len(other["shape"]):
                raise DraftError(f"{name}: both input tensors must have the same dtype and rank.")
            if kind == "Add":
                if shape != other["shape"]:
                    raise DraftError(f"{name}: Add requires equal shapes; implicit broadcasting is unsupported.")
            else:
                axis = _axis(p["dim"], len(shape), name)
                if any(a != b for i, (a, b) in enumerate(zip(shape, other["shape"])) if i != axis):
                    raise DraftError(f"{name}: Concat dimensions other than dim must match.")
                shape[axis] += other["shape"][axis]
        result = {"shape": shape, "dtype": dtype}
    if len(result["shape"]) > 8 or math.prod(result["shape"]) > 1000000000:
        raise DraftError(f"{name}: declared tensor exceeds the rank-8 / one-billion-element authoring budget.")
    return result


def validate_draft(draft: dict, *, require_complete: bool = False) -> dict:
    """Normalize a separate draft; reject malformed or contradictory graphs.

    Incomplete graphs can be saved while building. Generation requires all
    ports to be bound and all nodes to contribute to at least one named output.
    Shape facts are deductions from declarations, not sampled execution.
    """
    _keys(draft, {"schemaVersion", "mode", "id", "title", "revision", "nodes", "edges"}, "Authored draft")
    if type(draft["schemaVersion"]) is not int or draft["schemaVersion"] != 1 or draft["mode"] != "authored-draft":
        raise DraftError("Only authored-draft schemaVersion 1 is accepted; imported CanvasDocuments cannot be authored drafts.")
    _identity(draft["id"], "Draft id")
    _text(draft["title"], "Draft title")
    if type(draft["revision"]) is not int or not 0 <= draft["revision"] <= 2**53 - 1:
        raise DraftError("Draft revision must be a nonnegative safe integer.")
    if not isinstance(draft["nodes"], list) or len(draft["nodes"]) > MAX_NODES or not isinstance(draft["edges"], list) or len(draft["edges"]) > MAX_EDGES:
        raise DraftError("An authored draft permits at most 128 nodes and 384 connections.")
    normalized = {key: deepcopy(draft[key]) for key in ("schemaVersion", "mode", "id", "title", "revision")}
    nodes = {}
    for raw in draft["nodes"]:
        _keys(raw, {"id", "kind", "label", "parameters", "position"}, "Draft node")
        identity = _identity(raw["id"], "Node id")
        if identity in nodes:
            raise DraftError(f"Duplicate node id: {identity}.")
        if not isinstance(raw["kind"], str) or raw["kind"] not in _BY_KIND:
            raise DraftError(f"Unsupported authored module: {raw['kind']}.")
        label = _text(raw["label"], f"{identity} label")
        spec = _BY_KIND[raw["kind"]]
        if not isinstance(raw["parameters"], dict) or set(raw["parameters"]) - set(spec["defaults"]):
            raise DraftError(f"{label}: unknown parameter; only the registered fields are accepted.")
        params = {field["name"]: _parameter(raw["parameters"].get(field["name"], field["default"]), field, label)
                  for field in spec["parameters"]}
        _keys(raw["position"], {"x", "y"}, f"{label} position")
        if any(type(v) not in (int, float) or abs(v) > 1000000 or not math.isfinite(v) for v in raw["position"].values()):
            raise DraftError(f"{label}: position must contain finite coordinates within ±1000000.")
        if raw["kind"] == "Conv2d" and (params["in_channels"] % params["groups"] or params["out_channels"] % params["groups"]):
            raise DraftError(f"{label}: groups must divide in_channels and out_channels.")
        if raw["kind"] == "MaxPool2d" and any(p > k // 2 for p, k in zip(params["padding"], params["kernel_size"])):
            raise DraftError(f"{label}: pool padding cannot exceed half the kernel size.")
        nodes[identity] = {"id": identity, "kind": raw["kind"], "label": label,
                           "parameters": params, "position": deepcopy(raw["position"])}
    edges, edge_ids, bound = [], set(), {}
    incoming, outgoing = {n: [] for n in nodes}, {n: [] for n in nodes}
    for raw in draft["edges"]:
        _keys(raw, {"id", "source", "target"}, "Draft connection")
        identity = _identity(raw["id"], "Connection id")
        if identity in edge_ids:
            raise DraftError(f"Duplicate connection id: {identity}.")
        edge_ids.add(identity)
        for endpoint, direction in (("source", "out"), ("target", "in")):
            _keys(raw[endpoint], {"nodeId", "portId"}, f"Connection {identity} {endpoint}")
            node_id, port_id = raw[endpoint]["nodeId"], raw[endpoint]["portId"]
            if not isinstance(node_id, str) or node_id not in nodes or not isinstance(port_id, str) or not any(
                    p["id"] == port_id and p["direction"] == direction for p in _BY_KIND[nodes[node_id]["kind"]]["ports"]):
                raise DraftError(f"Connection {identity}: {endpoint} must identify an exact declared {direction} port of its own node.")
        key = (raw["target"]["nodeId"], raw["target"]["portId"])
        if key in bound:
            raise DraftError(f"{key[0]}.{key[1]} already has a producer; remove that connection first.")
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
        raise DraftError("Connections form a cycle; authored forward graphs must be acyclic.")
    issues, tensors = [], {}
    if not any(n["kind"] == "Input" for n in nodes.values()):
        issues.append({"code": "missing-input", "message": "Add at least one Input module."})
    if not any(n["kind"] == "Output" for n in nodes.values()):
        issues.append({"code": "missing-output", "message": "Add at least one Output module."})
    for identity in order:
        node = nodes[identity]
        required = [p["id"] for p in _BY_KIND[node["kind"]]["ports"] if p["direction"] == "in"]
        missing = [p for p in required if (identity, p) not in bound]
        if missing:
            issues.append({"code": "unbound-input", "nodeId": identity, "portIds": missing,
                           "message": f"{node['label']}: connect {', '.join(missing)}."})
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
        issues.append({"code": "unused-node", "nodeIds": unused,
                       "message": "Every module must contribute to a named Output before generating Python."})
    normalized["nodes"], normalized["edges"] = list(nodes.values()), edges
    if require_complete and issues:
        raise DraftError("Draft is incomplete: " + " ".join(item["message"] for item in issues))
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
