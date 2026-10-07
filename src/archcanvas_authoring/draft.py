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


from .catalog import (CATALOG as _CATALOG, BY_KIND as _BY_KIND, FLOAT_MODULES as _FLOAT_MODULES,
                      IR_CATEGORIES as _IR_CATEGORIES, FUNCTIONAL as _FUNCTIONAL, module_catalog)
from .shape import infer_outputs as _infer_outputs, validate_parameters as _validate_parameters


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
    return _infer_outputs(node, inputs, _fail, _axis)['output']


def validate_draft(draft: dict, *, require_complete: bool = False) -> dict:
    """Normalize a separate draft; reject malformed or contradictory graphs.

    Incomplete graphs can be saved while building. Generation requires all
    ports to be bound and all nodes to contribute to at least one named output.
    Shape facts are deductions from declarations, not sampled execution.
    """
    if isinstance(draft, dict) and "sourceProvenance" in draft:
        from .source_import import validate_source_draft
        return validate_source_draft(draft, require_complete=require_complete)
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
        _validate_parameters({'id': diagnostic_identity, 'kind': raw['kind'], 'parameters': params}, _fail)
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
    issues, tensors, port_tensors = [], {}, {}
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
        elif all((bound[identity, p]['source']['nodeId'], bound[identity, p]['source']['portId']) in port_tensors for p in required):
            outputs = _infer_outputs(node, [port_tensors[bound[identity, p]['source']['nodeId'], bound[identity, p]['source']['portId']] for p in required], _fail, _axis)
            tensors[identity] = outputs['output']
            for port, tensor in outputs.items(): port_tensors[identity, port] = tensor
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
            "issues": issues, "tensors": tensors, "portTensors": {n: {p: t for (i, p), t in port_tensors.items() if i == n} for n in nodes}, "order": order,
            "verification": "static-declared-tensors; no model execution"}


def _name(identity: str) -> str:
    return "node_" + hashlib.sha256(identity.encode()).hexdigest()[:16]


def _value(identity: str, port: str = 'output') -> str:
    return _name(identity) if port == 'output' else _name(identity) + '_' + port


def _expression(node: dict, producers: dict, nodes: dict, tensors: dict, port_tensors: dict | None = None) -> str:
    def arg(port):
        source = producers[node['id'], port]['source']
        return _value(source['nodeId'], source['portId'])
    def tensor(port):
        source = producers[node['id'], port]['source']
        return port_tensors[source['nodeId']][source['portId']] if port_tensors else tensors[source['nodeId']]
    kind, p = node['kind'], node['parameters']
    if kind in ('Add', 'Subtract', 'Multiply', 'Divide'):
        op = {'Add': '+', 'Subtract': '-', 'Multiply': '*', 'Divide': '/'}[kind]
        return f"{arg('left')} {op} {arg('right')}"
    if kind == 'MatMul': return f"{arg('left')} @ {arg('right')}"
    if kind == 'Concat':
        rank = len(tensor('a')['shape'])
        return f"torch.cat(({arg('a')}, {arg('b')}), dim={p['dim'] % rank})"
    if kind in ('Reshape', 'Transpose', 'Permute', 'Unsqueeze', 'Squeeze', 'Mean', 'Sum'):
        shape = tensor('input')['shape']
        rank = len(shape)
        if kind == 'Reshape':
            sizes = p['shape'][:]
            if -1 in sizes: sizes[sizes.index(-1)] = math.prod(shape) // math.prod(x for x in sizes if x != -1)
            return f"{arg('input')}.reshape({tuple(sizes)!r})"
        if kind == 'Transpose': return f"{arg('input')}.transpose({p['dim0'] % rank}, {p['dim1'] % rank})"
        if kind == 'Permute': return f"{arg('input')}.permute({tuple(p['dims'])!r})"
        if kind in ('Unsqueeze', 'Squeeze'): return f"{arg('input')}.{kind.lower()}({p['dim'] % (rank + (1 if kind == 'Unsqueeze' else 0))})"
        return f"{arg('input')}.{kind.lower()}(dim={p['dim'] % rank}, keepdim={p['keepdim']!r})"
    if kind == 'MultiheadAttention':
        return f"self.{_name(node['id'])}({arg('query')}, {arg('key')}, {arg('value')})"
    return f"self.{_name(node['id'])}({arg('input')})"


def _source(validation: dict) -> str:
    draft = validation["draft"]
    nodes = {n["id"]: n for n in draft["nodes"]}
    inputs = [nodes[n] for n in validation["order"] if nodes[n]["kind"] == "Input"]
    modules = [nodes[n] for n in validation["order"] if nodes[n]["kind"] not in ({"Input", "Output"} | _FUNCTIONAL)]
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
            target = _name(identity)
            if node['kind'] == 'LSTM': target += f", ({_value(identity, 'h_n')}, {_value(identity, 'c_n')})"
            elif node['kind'] in ('GRU', 'RNN'): target += f", {_value(identity, 'h_n')}"
            elif node['kind'] == 'MultiheadAttention': target += f", {_value(identity, 'weights')}"
            lines.append(f"        {target} = {_expression(node, producers, nodes, validation['tensors'], validation['portTensors'])}")
    entries = [f"{n['id']!r}: {_value(producers[n['id'], 'input']['source']['nodeId'], producers[n['id'], 'input']['source']['portId'])}" for n in outputs]
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
        elif kind in _FUNCTIONAL:
            expression = _expression(node, producers, nodes, validated["tensors"], validated["portTensors"])
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
        params = {} if kind in ({"Input", "Output"} | _FUNCTIONAL) else deepcopy(node["parameters"])
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
        evidence = "source" if node["kind"] in ('Input', 'Output', 'Add', 'Subtract', 'Multiply', 'Divide', 'MatMul') else "contract"
        if match.get("category") != category or match.get("evidence") != evidence or "repeat" in match:
            raise DraftError(f"{node['label']}: generated category/evidence/repetition differs from the authoring contract.")
        if node["kind"] not in ({"Input", "Output"} | _FUNCTIONAL) and match.get("callId") != match["id"]:
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
            if node['kind'] == 'MultiheadAttention' and draft_port in ('key', 'value'):
                if producers[identity, draft_port]['source'] != producers[identity, 'query']['source']: role = 'memory'
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
        out_name = _name(s["nodeId"]) if nodes[s["nodeId"]]["kind"] == "Input" else s['portId']
        edge_role = "residual" if residual_ports.get(t["nodeId"]) == t["portId"] else "data"
        if nodes[t['nodeId']]['kind'] == 'MultiheadAttention' and t['portId'] in ('key', 'value'):
            if s != producers[t['nodeId'], 'query']['source']: edge_role = 'memory'
        expected_edges.append((bindings[s["nodeId"]], ports[s["nodeId"], s["portId"]],
                               bindings[t["nodeId"]], ports[t["nodeId"], t["portId"]],
                               f"tensor:{bindings[s['nodeId']]}:{out_name}",
                               edge_role))
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
    if isinstance(draft, dict) and "sourceProvenance" in draft:
        from .source_import import generate_source_draft
        return generate_source_draft(draft)
    validation = validate_draft(draft, require_complete=True)
    source = _source(validation)
    architecture = analyze_source(source, ENTRY)
    verification = verify_generated(validation["draft"], architecture)
    return {"draft": validation["draft"], "draftDigest": validation["draftDigest"], "entry": ENTRY,
            "source": source, "architecture": architecture, "nodeBindings": verification["nodeBindings"],
            "portBindings": verification["portBindings"], "tensors": validation["tensors"], "portTensors": validation["portTensors"], "verification": verification}
