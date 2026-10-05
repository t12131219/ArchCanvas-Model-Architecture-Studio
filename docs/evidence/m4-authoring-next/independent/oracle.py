"""Independent, nonexecuting AST and exact-IR oracle for the hand-authored cases.

No authoring registry, shape inference, generator, verifier, frontend expected
delta or product graph parser is imported here. The caller separately invokes
the real frontend and supplies its fresh result; this oracle inspects the actual
Python syntax and checks facts against the original casebook graph.
"""
from __future__ import annotations

import ast
from collections import Counter
import hashlib
import json


WEIGHTED = {"Linear", "Conv2d", "BatchNorm2d", "LayerNorm", "Embedding"}
DEFAULTS = {"Conv2d": {"bias": True, "dilation": [1, 1], "groups": 1},
            "MaxPool2d": {"dilation": [1, 1], "ceil_mode": False},
            "BatchNorm2d": {"affine": True, "track_running_stats": True},
            "Embedding": {}, "Identity": {}, "ReLU": {}, "SiLU": {},
            "LayerNorm": {}, "Linear": {}, "Dropout": {}, "Flatten": {}, "GELU": {}}
IR_CATEGORIES = {"Input": "input", "Output": "output", "Linear": "linear", "Embedding": "embedding",
                 "LayerNorm": "norm", "BatchNorm2d": "norm", "ReLU": "activation", "GELU": "activation", "SiLU": "activation",
                 "Dropout": "regularization", "Identity": "operator", "Flatten": "operator", "Conv2d": "convolution",
                 "MaxPool2d": "pooling", "AdaptiveAvgPool2d": "pooling", "Concat": "operator"}


def portable(value):
    if isinstance(value, tuple):
        return [portable(item) for item in value]
    if isinstance(value, list):
        return [portable(item) for item in value]
    return value


def exact(actual, expected, context):
    # bool is not equal to integer and integer is not equal to string. Use
    # portable JSON so tuple/list constructor syntax may express the same shape.
    first = json.dumps(portable(actual), sort_keys=True, allow_nan=False)
    second = json.dumps(portable(expected), sort_keys=True, allow_nan=False)
    assert first == second, f"{context}: {first} != {second}"


def literal(expression):
    if (isinstance(expression, ast.Attribute) and isinstance(expression.value, ast.Name)
            and expression.value.id == "torch" and expression.attr == "float32"):
        return {"dtypeLiteral": "torch.float32"}
    value = ast.literal_eval(expression)
    assert value is None or type(value) in (int, float, bool, str, list, tuple), "unsupported literal"
    return portable(value)


def inspect_python(source):
    """Accept a narrow declaration/straight-line subset and derive real dataflow."""
    tree = ast.parse(source)
    body = list(tree.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body.pop(0)
    assert len(body) == 3, "extra top-level statements"
    assert isinstance(body[0], ast.Import) and [(a.name, a.asname) for a in body[0].names] == [("torch", None)]
    assert isinstance(body[1], ast.ImportFrom) and body[1].module == "torch" and body[1].level == 0 and [(a.name, a.asname) for a in body[1].names] == [("nn", None)]
    cls = body[2]
    assert isinstance(cls, ast.ClassDef) and not cls.decorator_list and not cls.keywords
    assert len(cls.bases) == 1 and ast.unparse(cls.bases[0]) == "nn.Module"
    assert len(cls.body) == 2 and all(isinstance(item, ast.FunctionDef) for item in cls.body)
    init, forward = cls.body
    assert init.name == "__init__" and forward.name == "forward"
    assert not init.decorator_list and not forward.decorator_list
    assert [arg.arg for arg in init.args.args] == ["self"] and not init.args.defaults
    assert init.body and ast.unparse(init.body[0]) == "super().__init__()"
    constructors = {}
    for statement in init.body[1:]:
        assert isinstance(statement, ast.Assign) and len(statement.targets) == 1
        target, call = statement.targets[0], statement.value
        assert isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self"
        assert target.attr not in constructors, "module reassignment"
        assert isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and call.func.value.id == "nn"
        assert not call.args, "constructor positional syntax not in audited generator contract"
        parameters = {}
        for keyword in call.keywords:
            assert keyword.arg and keyword.arg not in parameters, "constructor keyword ambiguity"
            parameters[keyword.arg] = literal(keyword.value)
        constructors[target.attr] = {"kind": call.func.attr, "parameters": parameters, "ast": call}
    args = forward.args
    assert not args.posonlyargs and not args.kwonlyargs and not args.defaults and not args.vararg and not args.kwarg
    assert args.args and args.args[0].arg == "self"
    inputs = [arg.arg for arg in args.args[1:]]
    assert len(set(inputs)) == len(inputs)
    values = {name: name for name in inputs}
    calls, connections, called_modules = {}, [], []

    def ref(value):
        assert isinstance(value, ast.Name) and value.id in values, "undefined/injected tensor expression"
        return values[value.id]

    for statement in forward.body[:-1]:
        assert isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name)
        symbol, expression = statement.targets[0].id, statement.value
        assert symbol not in values, "tensor reassignment"
        if isinstance(expression, ast.Call) and isinstance(expression.func, ast.Attribute) and isinstance(expression.func.value, ast.Name) and expression.func.value.id == "self":
            member = expression.func.attr
            assert member in constructors and member not in called_modules, "unbound or shared module call"
            assert len(expression.args) == 1 and not expression.keywords
            called_modules.append(member)
            calls[symbol] = {"kind": constructors[member]["kind"], "member": member, "parameters": constructors[member]["parameters"], "ast": expression}
            connections.append((ref(expression.args[0]), symbol, "input"))
        elif isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Add):
            calls[symbol] = {"kind": "Add", "parameters": {}, "ast": expression}
            connections.extend([(ref(expression.left), symbol, "left"), (ref(expression.right), symbol, "right")])
        elif isinstance(expression, ast.Call) and ast.unparse(expression.func) == "torch.cat":
            assert len(expression.args) == 1 and isinstance(expression.args[0], (ast.Tuple, ast.List)) and len(expression.args[0].elts) == 2
            assert len(expression.keywords) == 1 and expression.keywords[0].arg == "dim"
            dimension = literal(expression.keywords[0].value)
            assert type(dimension) is int
            calls[symbol] = {"kind": "Concat", "parameters": {"dim": dimension}, "ast": expression}
            connections.extend([(ref(expression.args[0].elts[0]), symbol, "a"), (ref(expression.args[0].elts[1]), symbol, "b")])
        else:
            raise AssertionError("unsupported executable forward statement")
        values[symbol] = symbol
    assert set(called_modules) == set(constructors), "hidden unused constructor"
    returned = forward.body[-1]
    assert isinstance(returned, ast.Return) and isinstance(returned.value, ast.Dict), "explicit named outputs required"
    outputs = {}
    for key, value in zip(returned.value.keys, returned.value.values):
        assert isinstance(key, ast.Constant) and type(key.value) is str and key.value not in outputs
        outputs[key.value] = ref(value)
    return {"class": cls.name, "inputs": inputs, "constructors": constructors,
            "calls": calls, "connections": connections, "outputs": outputs}


def assert_generated(case, receipt, fresh_architecture=None):
    draft, source, architecture = case["draft"], receipt["source"], receipt["architecture"]
    syntax = inspect_python(source)
    assert receipt["entry"] == f"model:{syntax['class']}"
    if fresh_architecture is not None:
        exact(architecture, fresh_architecture, "receipt vs separately re-analyzed source")
    exact(architecture["sources"], [{"path": "model.py", "content": source,
                                   "digest": hashlib.sha256(source.encode()).hexdigest()}], "source byte binding")
    original_nodes = {node["id"]: node for node in draft["nodes"]}
    assert len(original_nodes) == len(draft["nodes"])
    bindings, ports = receipt["nodeBindings"], receipt["portBindings"]
    assert set(bindings) == set(original_nodes) and len(set(bindings.values())) == len(bindings)
    assert set(ports) == set(original_nodes)
    by_id = {node["id"]: node for node in architecture["nodes"]}
    assert len(by_id) == len(architecture["nodes"])
    roots = [node for node in architecture["nodes"] if not node.get("parentId")]
    assert len(roots) == 1 and roots[0]["kind"] == "Module" and roots[0]["category"] == "container"
    root = roots[0]
    assert set(by_id) == set(bindings.values()) | {root["id"]}, "extra/omitted canonical node"
    assert len(root["children"]) == len(bindings) and set(root["children"]) == set(bindings.values())
    assert len(syntax["inputs"]) == sum(node["kind"] == "Input" for node in draft["nodes"])
    assert len(syntax["calls"]) == sum(node["kind"] not in ("Input", "Output") for node in draft["nodes"])
    assert set(syntax["outputs"]) == {node["id"] for node in draft["nodes"] if node["kind"] == "Output"}
    symbols = {}
    expected_ir_ports = {}
    for identity, node in original_nodes.items():
        observed = by_id[bindings[identity]]
        assert observed["kind"] == node["kind"] and observed["parentId"] == root["id"] and observed["children"] == []
        assert "repeat" not in observed, "unexpected repeat/sharing"
        kind = node["kind"]
        role_by_input = {edge["target"]["portId"]: case.get("edgeRoles", {}).get(edge["id"], "data")
                         for edge in draft["edges"] if edge["target"]["nodeId"] == identity}
        expected_category = ("residual" if "residual" in role_by_input.values() else "operator") if kind == "Add" else IR_CATEGORIES[kind]
        assert observed["category"] == expected_category
        assert observed["evidence"] == ("source" if kind in ("Input", "Output", "Add") else "contract")
        if kind == "Input":
            outgoing = [port for port in observed["ports"] if port["direction"] == "out"]
            assert len(outgoing) == 1 and outgoing[0]["name"] in syntax["inputs"]
            symbols[identity] = outgoing[0]["name"]
            expected_ir_ports[identity] = {"output": (symbols[identity], "out")}
            exact(observed["parameters"], {}, "input has no invented constructor")
        elif kind == "Output":
            expected_ir_ports[identity] = {"input": ("value", "in")}
            exact(observed["outputPath"], [{"kind": "key", "key": identity}], "return identity")
            exact(observed["parameters"], {}, "output has no invented constructor")
        else:
            matches = [(symbol, call) for symbol, call in syntax["calls"].items()
                       if call["ast"].lineno == observed["source"]["line"] and call["kind"] == kind]
            assert len(matches) == 1, "source span/call identity mismatch"
            symbol, call = matches[0]
            symbols[identity] = symbol
            assert observed["source"]["expression"] == ast.get_source_segment(source, call["ast"])
            expected_parameters = DEFAULTS.get(kind, {}) | node["parameters"]
            if kind == "Concat":
                # This worked case has rank 2 and declared -1. The expected
                # equivalent axis is written here, not inferred by the backend.
                expected_parameters = {"dim": case.get("effectiveConcatDim", 1)}
            if kind in WEIGHTED:
                expected_parameters["dtype"] = {"dtypeLiteral": "torch.float32"}
            # Additional generated defaults must be independently declared in
            # the casebook/DEFAULTS before they can count as checked.
            exact(call["parameters"], expected_parameters, f"{identity}: actual constructor/function parameters")
            if kind not in ("Add", "Concat"):
                assert observed["instanceId"] == f"instance:model.{syntax['class']}.{call['member']}"
                assert observed["callId"] == observed["id"] and observed["id"] == "call:" + observed["instanceId"]
                expected_ir_parameters = {key: ({"expression": "torch.float32", "origin": "unknown"} if key == "dtype" else value)
                                          for key, value in expected_parameters.items()}
                exact(observed["parameters"], expected_ir_parameters, f"{identity}: static parameters")
            else:
                exact(observed["parameters"], {}, f"{identity}: functional IR parameters are empty; AST checks actual values")
            expected_ir_ports[identity] = ({"left": ("left", "in"), "right": ("right", "in"), "output": ("output", "out")} if kind == "Add" else
                                            {"a": ("arg0", "in"), "b": ("arg0.1", "in"), "output": ("output", "out")} if kind == "Concat" else
                                            {"input": ("input", "in"), "output": ("output", "out")})
        expected_port_set = expected_ir_ports[identity]
        assert set(ports[identity]) == set(expected_port_set), f"{identity}: draft port inventory"
        assert len(observed["ports"]) == len(expected_port_set), f"{identity}: extra canonical port"
        directional_ordinals = {"in": 0, "out": 0}
        for draft_port, (name, direction) in expected_port_set.items():
            selected = [p for p in observed["ports"] if p["id"] == ports[identity][draft_port]]
            assert len(selected) == 1 and selected[0]["name"] == name and selected[0]["direction"] == direction
            assert selected[0]["id"] == f"{observed['id']}:{direction}:{name}", "foreign canonical port"
            assert selected[0]["ordinal"] == directional_ordinals[direction], "canonical port ordinal"
            directional_ordinals[direction] += 1
            assert selected[0]["role"] == (role_by_input.get(draft_port, "data") if direction == "in" else "data"), "canonical port role"
    assert len(set(symbols.values())) == len(symbols), "two draft nodes share one actual tensor call"
    expected_ast_edges = []
    expected_ir_edges, expected_ir_roles = [], {}
    for edge in draft["edges"]:
        source_id, target_id = edge["source"]["nodeId"], edge["target"]["nodeId"]
        source_port, target_port = edge["source"]["portId"], edge["target"]["portId"]
        if original_nodes[target_id]["kind"] == "Output":
            assert syntax["outputs"][target_id] == symbols[source_id], "return producer mismatch"
        else:
            expected_ast_edges.append((symbols[source_id], symbols[target_id], target_port))
        relation = (bindings[source_id], ports[source_id][source_port], bindings[target_id], ports[target_id][target_port])
        expected_ir_edges.append(relation)
        expected_ir_roles[relation] = case.get("edgeRoles", {}).get(edge["id"], "data")
    assert Counter(syntax["connections"]) == Counter(expected_ast_edges), "actual Python tensor binding differs from original graph"
    # Explicit root-input edges are the only relations outside authored nodes.
    root_edges = [edge for edge in architecture["edges"] if edge["target"]["nodeId"] == root["id"]]
    assert len(root_edges) == len(syntax["inputs"])
    root_ports = root["ports"]
    assert len(root_ports) == len(syntax["inputs"])
    for node in draft["nodes"]:
        if node["kind"] != "Input":
            continue
        identity = node["id"]
        selected = [edge for edge in root_edges if edge["source"]["nodeId"] == bindings[identity]]
        assert len(selected) == 1 and selected[0]["source"]["portId"] == ports[identity]["output"]
        assert selected[0]["target"]["portId"] == f"{root['id']}:in:{symbols[identity]}"
    actual_ir_edges = [edge for edge in architecture["edges"] if edge not in root_edges]
    actual_relations = [(e["source"]["nodeId"], e["source"]["portId"], e["target"]["nodeId"], e["target"]["portId"]) for e in actual_ir_edges]
    assert Counter(actual_relations) == Counter(expected_ir_edges), "missing/extra/external tensor binding"
    for edge in architecture["edges"]:
        relation = (edge["source"]["nodeId"], edge["source"]["portId"], edge["target"]["nodeId"], edge["target"]["portId"])
        expected_role = expected_ir_roles.get(relation, "data")
        assert edge["role"] == expected_role, "canonical relation role differs from authored worked case"
    assert len({edge["id"] for edge in architecture["edges"]}) == len(architecture["edges"])
    producer_tensors, tensor_producers = {}, {}
    for edge in architecture["edges"]:
        producer = (edge["source"]["nodeId"], edge["source"]["portId"])
        assert edge["tensorId"] == f"tensor:{producer[0]}:{next(p['name'] for p in by_id[producer[0]]['ports'] if p['id'] == producer[1])}"
        producer_tensors.setdefault(producer, set()).add(edge["tensorId"])
        tensor_producers.setdefault(edge["tensorId"], set()).add(producer)
    assert all(len(values) == 1 for values in producer_tensors.values()), "fanout tensor split"
    assert all(len(values) == 1 for values in tensor_producers.values()), "different producers share tensor"
    expected_tensors = {identity: {"shape": shape, "dtype": dtype} for identity, (shape, dtype) in case["outputs"].items()}
    exact(receipt["tensors"], expected_tensors, "hand-calculated tensor contracts")
    return {"nodes": len(original_nodes), "edges": len(draft["edges"]), "constructors": len(syntax["constructors"]),
            "inputInterfaces": len(syntax["inputs"]), "namedOutputs": len(syntax["outputs"])}
