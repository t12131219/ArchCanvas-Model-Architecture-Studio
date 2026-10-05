"""Concrete, frozen input contracts for a bounded multi-input attention scope.

This analysis parses data only. Actual structural verification is a separate
opt-in isolated worker and is mandatory before its transaction reaches review.
"""
from __future__ import annotations

import ast
import copy
import math
from pathlib import Path
from typing import Any

from .frontend import Corpus, UNKNOWN, analyze_project, digest, literal
from .rebind import PRESERVING, _binding, _module_effect_blocker, _span


MHA_INPUTS = ["query", "key", "value", "key_padding_mask", "need_weights", "attn_mask", "average_attn_weights", "is_causal"]
STRUCTURAL_SCOPE = {"version": 1, "profile": "structural-verified", "targetKinds": [*sorted(PRESERVING), "MultiheadAttention"], "slots": ["input", "query", "key", "value", "key_padding_mask", "attn_mask"], "scope": "entry-root-straight-line", "runtimeRequired": True}


class StructuralEvidenceError(ValueError):
    pass


def normalize_input_spec(spec: dict[str, Any], names: list[str] | None = None) -> dict[str, Any]:
    if not isinstance(spec, dict) or set(spec) - {"schemaVersion", "inputs", "seed", "modes", "constructor"} or not {"schemaVersion", "inputs", "seed", "modes"}.issubset(spec) or spec.get("schemaVersion") != 1 or type(spec.get("seed")) is not int or not 0 <= spec["seed"] <= 2**31 - 1:
        raise StructuralEvidenceError("InputSpec requires schemaVersion=1, explicit inputs, seed in [0, 2^31-1] and declared modes.")
    if not isinstance(spec["modes"], list) or not spec["modes"] or len(spec["modes"]) != len(set(spec["modes"])) or any(mode not in ("eval", "train") for mode in spec["modes"]):
        raise StructuralEvidenceError("InputSpec modes must explicitly select eval and/or train without duplication.")
    if spec.get("constructor", {}) != {}:
        raise StructuralEvidenceError("The first structural source/IR contract requires constructor defaults; nonempty constructor arguments need an explicit analysis binding.")
    if not isinstance(spec["inputs"], dict) or not spec["inputs"] or (names is not None and set(spec["inputs"]) != set(names)):
        raise StructuralEvidenceError("InputSpec must bind every forward tensor parameter exactly once.")
    total = 0
    for name, value in spec["inputs"].items():
        if not isinstance(name, str) or not name.isidentifier() or not isinstance(value, dict) or set(value) - {"shape", "dtype", "fill"} or not {"shape", "dtype"}.issubset(value) or value["dtype"] not in ("float32", "float64", "bool"):
            raise StructuralEvidenceError("Each input requires an identifier, concrete shape and float32/float64/bool dtype.")
        shape = value["shape"]
        if not isinstance(shape, list) or not 1 <= len(shape) <= 4 or any(type(size) is not int or not 1 <= size <= 1024 for size in shape):
            raise StructuralEvidenceError("Concrete input dimensions must be 1–1024, rank 1–4.")
        total += math.prod(shape)
        if value.get("fill", "zeros" if value["dtype"] == "bool" else "normal") not in ("normal", "zeros", "ones") or (value["dtype"] == "bool" and value.get("fill", "zeros") == "normal"):
            raise StructuralEvidenceError("Input fill must be normal/zeros/ones; boolean masks require zeros or ones.")
    if total > 1_000_000:
        raise StructuralEvidenceError("Frozen inputs exceed the one-million-element verification budget.")
    normalized = copy.deepcopy(spec)
    normalized["constructor"] = {}
    for value in normalized["inputs"].values():
        value.setdefault("fill", "zeros" if value["dtype"] == "bool" else "normal")
    return normalized


def inspect_structural_rebind(root: str | Path, entry: str, node_id: str, port_id: str, input_spec: dict[str, Any], architecture: dict[str, Any] | None = None) -> dict[str, Any]:
    before = analyze_project(root, entry)
    result = {"schemaVersion": 1, "supported": False, "status": "unsupported", "sourceDigest": before["sourceDigest"], "irDigest": before["irDigest"], "scope": copy.deepcopy(STRUCTURAL_SCOPE), "target": None, "candidates": [], "excludedCandidates": [], "blockers": []}
    def fail(message):
        result["blockers"].append(message)
        return result
    try:
        if architecture is not None and architecture != before:
            raise StructuralEvidenceError("Frozen architecture does not match current source facts.")
        target = next((node for node in before["nodes"] if node["id"] == node_id), None)
        roots = [node for node in before["nodes"] if not node.get("parentId")]
        if target is None or len(roots) != 1 or target.get("parentId") != roots[0]["id"] or target.get("kind") not in STRUCTURAL_SCOPE["targetKinds"] or target.get("evidence") != "contract":
            raise StructuralEvidenceError("Target must be one directly authored registered call in the entry-root forward.")
        model = roots[0]
        corpus = Corpus(Path(root)); corpus.load(entry.split(":", 1)[0])
        definition = corpus.definition(entry.replace(":", "."))
        if not definition or not corpus.framework_is_unshadowed():
            raise StructuralEvidenceError("Entry and external framework provenance are unresolved.")
        if {unit.path: unit.raw_digest for unit in corpus.units.values()} != {source["path"]: source["digest"] for source in before["sources"]}:
            raise StructuralEvidenceError("Source corpus changed while freezing structural evidence.")
        blocker = _module_effect_blocker(corpus)
        if blocker:
            raise StructuralEvidenceError(blocker)
        unit, cls = definition
        methods = [item for item in cls.body if isinstance(item, ast.FunctionDef)]
        if cls.decorator_list or cls.keywords or len(cls.bases) != 1 or unit.resolve(cls.bases[0]) != "torch.nn.Module" or len(methods) != 2 or {item.name for item in methods} != {"__init__", "forward"} or any(not isinstance(item, ast.FunctionDef) and not (isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant)) for item in cls.body):
            raise StructuralEvidenceError("Only direct undecorated Module init/forward methods and docstrings are supported.")
        initializer = next(item for item in methods if item.name == "__init__")
        forward = next(item for item in methods if item.name == "forward")
        for method in methods:
            if method.decorator_list or method.args.vararg or method.args.kwarg or method.args.posonlyargs or not method.args.args or method.args.args[0].arg != "self":
                raise StructuralEvidenceError("Methods require an unshadowed self receiver and finite authored signatures.")
        names = [arg.arg for arg in forward.args.args[1:] + forward.args.kwonlyargs]
        spec = normalize_input_spec(input_spec, names)
        result["inputSpec"] = spec; result["inputSpecDigest"] = digest(spec)
        counts = dict.fromkeys(names, 1)
        for item in ast.walk(forward):
            if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store):
                if item.id == "self":
                    raise StructuralEvidenceError("The self receiver cannot be reassigned.")
                counts[item.id] = counts.get(item.id, 0) + 1
        if any(count != 1 for count in counts.values()):
            raise StructuralEvidenceError("Forward variables cannot be reassigned.")
        attributes = _constructors(unit, initializer)
        values = {}
        for name in names:
            edges = [edge for edge in before["edges"] if edge["target"]["nodeId"] == model["id"] and edge["target"]["portId"] == f"{model['id']}:in:{name}"]
            if len(edges) != 1:
                raise StructuralEvidenceError("Forward input has no unique canonical binding.")
            values[name] = {"variable": name, "binding": _binding(edges[0]), "contract": {key: copy.deepcopy(spec["inputs"][name][key]) for key in ("shape", "dtype")}, "definition": _span(unit, next(arg for arg in forward.args.args[1:] + forward.args.kwonlyargs if arg.arg == name))}
        found = False; returned = False; outputs = []; runtime_calls = []
        for statement in forward.body:
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and not returned:
                continue
            if returned:
                raise StructuralEvidenceError("Unreachable statements after return are unsupported.")
            if isinstance(statement, ast.Return):
                returned = True
                items = statement.value.elts if isinstance(statement.value, ast.Tuple) else [statement.value]
                if not all(isinstance(item, ast.Name) and item.id in values for item in items):
                    raise StructuralEvidenceError("Return must expose explicitly named tensor/None outputs.")
                outputs = [{"variable": item.id, "contract": copy.deepcopy(values[item.id]["contract"])} for item in items]
                continue
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1 or not isinstance(statement.value, ast.Call):
                raise StructuralEvidenceError("Forward requires direct call assignments and one named return; mutation, control and nested calls are unsupported.")
            call = statement.value
            if not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name) or call.func.value.id != "self" or call.func.attr not in attributes:
                raise StructuralEvidenceError("Forward call does not resolve to one registered module attribute.")
            kind, params = attributes[call.func.attr]
            nodes = [node for node in before["nodes"] if node.get("parentId") == model["id"] and node["source"]["path"] == unit.path and node["source"]["line"] == call.lineno and node["source"]["endLine"] == call.end_lineno and node["source"]["expression"] == unit.expression(call)]
            if len(nodes) != 1 or nodes[0]["kind"] != kind or nodes[0].get("evidence") != "contract":
                raise StructuralEvidenceError("Call source anchor is not unique or its framework facts disagree.")
            node = nodes[0]
            arguments = _call_arguments(call, kind)
            tensor_arguments = {name: atom for name, atom in arguments.items() if isinstance(atom, ast.Name)}
            for name, atom in tensor_arguments.items():
                if atom.id not in values or values[atom.id]["contract"] is None:
                    raise StructuralEvidenceError("Tensor producer is not a dominating uniquely defined variable.")
                edge = [edge for edge in before["edges"] if edge["target"] == {"nodeId": node["id"], "portId": f"{node['id']}:in:{name}"}]
                if len(edge) != 1 or _binding(edge[0]) != values[atom.id]["binding"]:
                    raise StructuralEvidenceError("Lexical tensor arguments disagree with complete canonical bindings.")
            contracts = {name: values[atom.id]["contract"] for name, atom in tensor_arguments.items()}
            output_contracts = _call_contracts(kind, params, arguments, contracts)
            runtime_calls.append({"nodeId": node["id"], "instanceId": node["instanceId"], "modulePath": call.func.attr, "kind": kind, "inputs": {name: {"binding": copy.deepcopy(values[atom.id]["binding"]), "contract": copy.deepcopy(values[atom.id]["contract"])} for name, atom in tensor_arguments.items()}, "outputs": {"output" if index == 0 else "weights": copy.deepcopy(contract) for index, contract in enumerate(output_contracts)}})
            if node["id"] == node_id:
                slot_name = next((name for name in tensor_arguments if f"{node_id}:in:{name}" == port_id), None)
                if slot_name is None:
                    raise StructuralEvidenceError("Target port is not one exact named tensor input slot.")
                atom = tensor_arguments[slot_name]; current = values[atom.id]
                origin = _span(unit, atom) | {"variable": atom.id, "argumentName": slot_name, "callKind": kind, "call": _span(unit, call)}
                result["target"] = {"nodeId": node_id, "portId": port_id, "slot": origin, "currentBinding": copy.deepcopy(current["binding"]), "contract": copy.deepcopy(current["contract"]), "argumentName": slot_name, "callContracts": copy.deepcopy(contracts), "constructor": copy.deepcopy(params)}
                for value in values.values():
                    if value["contract"] != current["contract"]:
                        result["excludedCandidates"].append({"variable": value["variable"], "reason": "Concrete shape/dtype differ from the frozen target contract."})
                        continue
                    candidate_contracts = contracts | {slot_name: value["contract"]}
                    _call_contracts(kind, params, arguments, candidate_contracts)
                    contract = {**copy.deepcopy(value["contract"]), "inputSpecDigest": digest(spec), "basis": "frozen-concrete-input-spec-and-registered-operation-contracts", "runtimeVerified": False, "runtimeRequired": True, "condition": "The staged model must pass isolated seeded forward/replay under this frozen input specification before review."}
                    result["candidates"].append({key: copy.deepcopy(value[key]) for key in ("variable", "binding", "definition")} | {"contract": contract})
                found = True
            targets = statement.targets[0].elts if isinstance(statement.targets[0], ast.Tuple) else [statement.targets[0]]
            if len(targets) != len(output_contracts) or any(not isinstance(item, ast.Name) for item in targets):
                raise StructuralEvidenceError("Output assignments must preserve exact registered tuple slot order and arity.")
            for index, (assigned, contract) in enumerate(zip(targets, output_contracts)):
                port_name = "output" if index == 0 else "weights"
                binding = {"nodeId": node["id"], "portId": f"{node['id']}:out:{port_name}", "tensorId": f"tensor:{node['id']}:{port_name}"}
                values[assigned.id] = {"variable": assigned.id, "binding": binding, "contract": copy.deepcopy(contract), "definition": _span(unit, call)}
        if not returned or not found:
            raise StructuralEvidenceError("A unique target and named output return are required.")
        result["outputContracts"] = outputs
        result["runtimeCalls"] = runtime_calls
        result["runtimeParameters"] = {name: {"kind": kind, "parameters": params} for name, (kind, params) in attributes.items()}
        state = []
        for name, (kind, params) in attributes.items():
            if kind != "MultiheadAttention":
                continue
            embed = params["embed_dim"]; key = params.get("kdim") or embed; value = params.get("vdim") or embed
            shapes = {"in_proj_weight": [3 * embed, embed]} if key == value == embed else {"q_proj_weight": [embed, embed], "k_proj_weight": [embed, key], "v_proj_weight": [embed, value]}
            shapes["out_proj.weight"] = [embed, embed]
            if params.get("bias", True):
                shapes.update({"in_proj_bias": [3 * embed], "out_proj.bias": [embed]})
            state.extend({"key": f"{name}.{key}", "shape": shape, "dtype": "float32", "role": "parameter"} for key, shape in shapes.items())
        result["stateContracts"] = sorted(state, key=lambda item: item["key"])
        # Every admitted attribute is a fresh direct constructor. Attribute
        # aliases, parameter assignment and storage mutation are rejected above.
        result["stateSharingContract"] = {"sharedGroups": [], "sharedStorageGroups": []}
        result["supported"] = True; result["status"] = "supported"
        return result
    except StructuralEvidenceError as exc:
        return fail(str(exc))


def _constructors(unit, initializer):
    params = initializer.args.args[1:]
    constants = dict(unit.constants)
    for param, default in zip(params[-len(initializer.args.defaults):], initializer.args.defaults):
        constants[param.arg] = literal(default, constants)
    shadowed = {arg.arg: None for arg in initializer.args.args + initializer.args.kwonlyargs}
    shadowed.update({item.id: None for item in ast.walk(initializer) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)})
    if "super" in shadowed or any(isinstance(item, ast.Name) and item.id == "self" and isinstance(item.ctx, ast.Store) for item in ast.walk(initializer)):
        raise StructuralEvidenceError("Initializer framework/self receiver shadowing is unsupported.")
    attributes = {}
    for statement in initializer.body:
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
            continue
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call) and ast.dump(statement.value, include_attributes=False) == "Call(func=Attribute(value=Call(func=Name(id='super', ctx=Load()), args=[], keywords=[]), attr='__init__', ctx=Load()), args=[], keywords=[])":
            continue
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            raise StructuralEvidenceError("Initializer must contain direct immutable registered module assignments.")
        target, call = statement.targets[0], statement.value
        if isinstance(target, ast.Name):
            value = literal(call, constants)
            if value is UNKNOWN:
                raise StructuralEvidenceError("Initializer local values must have frozen literal definitions.")
            constants[target.id] = value; continue
        if not isinstance(target, ast.Attribute) or not isinstance(target.value, ast.Name) or target.value.id != "self" or target.attr in attributes or not isinstance(call, ast.Call):
            raise StructuralEvidenceError("Module attributes need unique direct constructors, without alias/state mutation.")
        qualified = unit.resolve(call.func, shadowed); kind = qualified.rsplit(".", 1)[-1]
        names = {"Identity": [], "Dropout": ["p", "inplace"], "ReLU": ["inplace"], "GELU": ["approximate"], "MultiheadAttention": ["embed_dim", "num_heads", "dropout", "bias", "add_bias_kv", "add_zero_attn", "kdim", "vdim", "batch_first"]}.get(kind)
        if qualified != f"torch.nn.{kind}" or names is None or len(call.args) > len(names) or any(isinstance(arg, ast.Starred) for arg in call.args):
            raise StructuralEvidenceError("Constructor is outside the registered attention/preserving contracts.")
        bound = {name: literal(arg, constants) for name, arg in zip(names, call.args)}
        for keyword in call.keywords:
            if keyword.arg not in names or keyword.arg in bound:
                raise StructuralEvidenceError("Unknown/unpacked/duplicate constructor argument is unsupported.")
            bound[keyword.arg] = literal(keyword.value, constants)
        if any(value is UNKNOWN for value in bound.values()):
            raise StructuralEvidenceError("All constructor arguments must have concrete frozen values.")
        if kind in ("Dropout", "ReLU") and bound.get("inplace", False) is not False:
            raise StructuralEvidenceError("In-place mutation invalidates the connection proof.")
        if kind == "Dropout" and (type(bound.get("p", 0.5)) not in (int, float) or not 0 <= bound.get("p", 0.5) <= 1):
            raise StructuralEvidenceError("Dropout probability violates its public contract.")
        if kind == "GELU" and bound.get("approximate", "none") not in ("none", "tanh"):
            raise StructuralEvidenceError("GELU approximate violates its public contract.")
        if kind == "MultiheadAttention":
            embed, heads = bound.get("embed_dim"), bound.get("num_heads")
            if type(embed) is not int or type(heads) is not int or not 1 <= embed <= 1024 or not 1 <= heads <= 64 or embed % heads:
                raise StructuralEvidenceError("MHA embed_dim must be positive and divisible by num_heads.")
            if any(type(bound.get(flag, False if flag != "bias" else True)) is not bool for flag in ("bias", "add_bias_kv", "add_zero_attn", "batch_first")) or bound.get("add_bias_kv", False) or bound.get("add_zero_attn", False):
                raise StructuralEvidenceError("MHA flags must be concrete booleans; added bias/zero attention slots are unsupported.")
            if type(bound.get("dropout", 0.0)) not in (int, float) or not 0 <= bound.get("dropout", 0.0) <= 1:
                raise StructuralEvidenceError("MHA dropout violates its public contract.")
            if any(bound.get(name) is not None and (type(bound[name]) is not int or not 1 <= bound[name] <= 1024) for name in ("kdim", "vdim")):
                raise StructuralEvidenceError("MHA kdim/vdim must be positive concrete dimensions.")
        attributes[target.attr] = kind, bound
    return attributes


def _call_arguments(call, kind):
    names = MHA_INPUTS if kind == "MultiheadAttention" else ["input"]
    if len(call.args) > len(names) or any(isinstance(arg, ast.Starred) for arg in call.args):
        raise StructuralEvidenceError("Unpacked or excessive positional inputs are unsupported.")
    bound = dict(zip(names, call.args))
    for keyword in call.keywords:
        if keyword.arg not in names or keyword.arg in bound:
            raise StructuralEvidenceError("Unknown/unpacked/duplicate call input is unsupported.")
        bound[keyword.arg] = keyword.value
    required = names[:3] if kind == "MultiheadAttention" else names
    if any(not isinstance(bound.get(name), ast.Name) for name in required):
        raise StructuralEvidenceError("Required tensor slots must be explicitly authored single Name arguments.")
    tensor_slots = ("query", "key", "value", "key_padding_mask", "attn_mask") if kind == "MultiheadAttention" else ("input",)
    for name, value in bound.items():
        if name in tensor_slots:
            if not isinstance(value, ast.Name) and not (isinstance(value, ast.Constant) and value.value is None and name not in required):
                raise StructuralEvidenceError("Tensor/mask slots require direct names or explicit optional None.")
        elif not isinstance(value, ast.Constant) or type(value.value) is not bool:
            raise StructuralEvidenceError("Attention control flags must be explicit boolean literals.")
    if isinstance(bound.get("is_causal"), ast.Constant) and bound["is_causal"].value:
        raise StructuralEvidenceError("Causal-hint changes require a separate registered mask rule.")
    return bound


def _call_contracts(kind, params, arguments, contracts):
    if kind != "MultiheadAttention":
        value = contracts["input"]
        if kind != "Identity" and value["dtype"] not in ("float32", "float64"):
            raise StructuralEvidenceError("Activation/dropout tensor dtype must be a supported floating dtype.")
        return [copy.deepcopy(value)]
    q, k, v = (contracts[name] for name in ("query", "key", "value"))
    if any(len(value["shape"]) != 3 for value in (q, k, v)) or q["dtype"] != "float32" or len({value["dtype"] for value in (q, k, v)}) != 1:
        raise StructuralEvidenceError("MHA query/key/value require rank-3 float32 tensors matching the registered default-construction parameter dtype.")
    batch_axis, sequence_axis = (0, 1) if params.get("batch_first", False) else (1, 0)
    batch, query_length, source_length = q["shape"][batch_axis], q["shape"][sequence_axis], k["shape"][sequence_axis]
    if q["shape"][2] != params["embed_dim"] or k["shape"][2] != (params.get("kdim") or params["embed_dim"]) or v["shape"][2] != (params.get("vdim") or params["embed_dim"]) or k["shape"][batch_axis] != batch or v["shape"][batch_axis] != batch or v["shape"][sequence_axis] != source_length:
        raise StructuralEvidenceError("MHA batch, key/value sequence and feature dimensions violate the frozen constructor contract.")
    for name, shape_options in (("key_padding_mask", [[batch, source_length]]), ("attn_mask", [[query_length, source_length], [batch * params["num_heads"], query_length, source_length]])):
        if name in contracts and (contracts[name]["dtype"] != "bool" or contracts[name]["shape"] not in shape_options):
            raise StructuralEvidenceError("Attention masks require correctly ranked bool masks with named batch/head/query/source axes.")
    need_weights = arguments.get("need_weights", ast.Constant(value=True)).value
    average = arguments.get("average_attn_weights", ast.Constant(value=True)).value
    weights = {"shape": [batch, query_length, source_length] if average else [batch, params["num_heads"], query_length, source_length], "dtype": q["dtype"]} if need_weights else None
    return [copy.deepcopy(q), weights]
