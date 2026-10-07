"""Independent graph, declared-shape and generated-Python AST audit.

This reads frontend-generated drafts. Expected nodes/parameters/edges/shapes
are handwritten in expected-contracts.json. It does not use the backend's
expected-graph helpers or generated symbol hashing as the comparison oracle.
It never imports generated source or torch and never runs a model.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from archcanvas_authoring import generate_model, validate_draft  # noqa: E402
import archcanvas_authoring.draft as backend  # noqa: E402
import archcanvas_python.frontend as frontend  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    with path.open("x", encoding="utf-8") as handle:
        handle.write(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def require(condition, detail):
    if not condition:
        raise AssertionError(detail)


def exact_json(left, right):
    return json.dumps(left, ensure_ascii=False, sort_keys=True) == json.dumps(right, ensure_ascii=False, sort_keys=True)


def graph_contract(draft, sequence, contracts):
    expected_nodes, edges, shapes, inventory = [], [], {}, []
    offset = 0
    for preset in sequence:
        contract = contracts[preset]
        chunk = draft["nodes"][offset:offset + len(contract["nodes"])]
        require(len(chunk) == len(contract["nodes"]), f"{preset}: node count differs")
        for node, expected in zip(chunk, contract["nodes"], strict=True):
            require(node["kind"] == expected["kind"], f"{preset}: type differs at node {node['id']}")
            require(exact_json(node["parameters"], expected["parameters"]), f"{preset}: exact declared parameters differ for {node['id']}")
            expected_nodes.append(node)
            shapes[node["id"]] = {"shape": expected["shape"], "dtype": "float32"}
        for source, source_port, target, target_port in contract["edges"]:
            edges.append((chunk[source]["id"], source_port, chunk[target]["id"], target_port))
        inventory.append({"preset": preset, "nodeIds": [n["id"] for n in chunk]})
        offset += len(chunk)
    require(offset == len(draft["nodes"]), "unexpected frontend nodes")
    actual_edges = [(e["source"]["nodeId"], e["source"]["portId"], e["target"]["nodeId"], e["target"]["portId"]) for e in draft["edges"]]
    require(Counter(actual_edges) == Counter(edges), "frontend producers/consumers/ordered ports differ from handwritten topology")
    require(len({n["id"] for n in expected_nodes}) == len(expected_nodes), "duplicate frontend node identities")
    require(len({e["id"] for e in draft["edges"]}) == len(draft["edges"]), "duplicate frontend edge identities")
    return expected_nodes, edges, shapes, inventory


def source_ast_contract(source, expected_nodes, expected_edges):
    tree = ast.parse(source)
    body = list(tree.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body.pop(0)
    require(len(body) == 3, "generated source contains unexpected top-level statements")
    require(isinstance(body[0], ast.Import) and [(a.name, a.asname) for a in body[0].names] == [("torch", None)], "unexpected torch import")
    require(isinstance(body[1], ast.ImportFrom) and body[1].module == "torch" and [(a.name, a.asname) for a in body[1].names] == [("nn", None)] and body[1].level == 0, "unexpected nn import")
    cls = body[2]
    require(isinstance(cls, ast.ClassDef) and cls.name == "AuthoredModel" and len(cls.bases) == 1 and ast.unparse(cls.bases[0]) == "nn.Module" and not cls.decorator_list and not cls.keywords, "unexpected class declaration")
    methods = {m.name: m for m in cls.body if isinstance(m, ast.FunctionDef)}
    require(set(methods) == {"__init__", "forward"} and len(cls.body) == 2, "unexpected class content")
    init, forward = methods["__init__"], methods["forward"]
    require(ast.unparse(init.body[0]) == "super().__init__()", "missing plain Module initializer")
    require([arg.arg for arg in init.args.args] == ["self"] and not init.args.defaults and not init.args.vararg and not init.args.kwarg, "unexpected initializer signature")
    constructors = {}
    for statement in init.body[1:]:
        require(isinstance(statement, ast.Assign) and len(statement.targets) == 1, "unexpected initialization statement")
        target, call = statement.targets[0], statement.value
        require(isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self", "unexpected constructor target")
        require(isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and call.func.value.id == "nn" and not call.args, "unexpected constructor call")
        params = {}
        for keyword in call.keywords:
            require(keyword.arg is not None and keyword.arg not in params, "duplicate or expanded constructor keyword")
            params[keyword.arg] = ast.unparse(keyword.value) if keyword.arg == "dtype" else ast.literal_eval(keyword.value)
        require(target.attr not in constructors, "constructor alias overwritten")
        constructors[target.attr] = {"kind": call.func.attr, "parameters": params}
    inputs = [n for n in expected_nodes if n["kind"] == "Input"]
    require(not forward.args.defaults and not forward.args.kw_defaults and not forward.args.vararg and not forward.args.kwarg and not forward.args.kwonlyargs and not forward.args.posonlyargs, "unexpected forward signature")
    arguments = [a.arg for a in forward.args.args]
    require(arguments and arguments[0] == "self" and len(arguments) == len(inputs) + 1 and len(set(arguments)) == len(arguments), "forward input argument inventory differs")
    node_symbols = {node["id"]: symbol for node, symbol in zip(inputs, arguments[1:], strict=True)}
    assignments = {}
    for statement in forward.body[:-1]:
        require(isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name), "unexpected forward statement")
        symbol = statement.targets[0].id
        require(symbol not in assignments and symbol not in arguments, "forward symbol overwritten")
        assignments[symbol] = statement.value
    returned = forward.body[-1]
    require(isinstance(returned, ast.Return) and isinstance(returned.value, ast.Dict), "output must be an explicit named dictionary")
    outputs = {}
    for key, value in zip(returned.value.keys, returned.value.values, strict=True):
        require(isinstance(key, ast.Constant) and isinstance(key.value, str) and isinstance(value, ast.Name), "unexpected named output expression")
        require(key.value not in outputs, "duplicate named output")
        outputs[key.value] = value.id
    expected_by_id = {n["id"]: n for n in expected_nodes}
    producers = {(target, port): source for source, _, target, port in expected_edges}
    require(set(outputs) == {n["id"] for n in expected_nodes if n["kind"] == "Output"}, "return dictionary keys differ from draft output node identities")
    used_constructors = set()

    def bind(identity, symbol):
        node = expected_by_id[identity]
        if identity in node_symbols:
            require(node_symbols[identity] == symbol, f"producer alias differs for {identity}")
            return
        require(symbol in assignments, f"missing assignment for {identity}")
        require(symbol not in node_symbols.values(), "distinct draft operations alias the same forward value")
        node_symbols[identity] = symbol
        value = assignments[symbol]
        if node["kind"] == "Add":
            require(isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add) and isinstance(value.left, ast.Name) and isinstance(value.right, ast.Name), "Add must use an exact binary tensor addition")
            bind(producers[identity, "left"], value.left.id)
            bind(producers[identity, "right"], value.right.id)
            return
        require(isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and isinstance(value.func.value, ast.Name) and value.func.value.id == "self" and len(value.args) == 1 and isinstance(value.args[0], ast.Name) and not value.keywords, f"{identity}: unexpected forward module call")
        alias = value.func.attr
        require(alias in constructors and alias not in used_constructors, "constructor missing or shared unexpectedly")
        used_constructors.add(alias)
        expected_params = deepcopy(node["parameters"])
        if node["kind"] in {"Linear", "Conv2d"}:
            expected_params["dtype"] = "torch.float32"
        require(exact_json(constructors[alias], {"kind": node["kind"], "parameters": expected_params}), f"{identity}: exact generated constructor type/parameters differ")
        bind(producers[identity, "input"], value.args[0].id)

    for output_id, symbol in outputs.items():
        bind(producers[output_id, "input"], symbol)
    internal = {n["id"] for n in expected_nodes if n["kind"] not in {"Input", "Output"}}
    require(internal == set(node_symbols) - {n["id"] for n in inputs}, "not all declared operations represented in forward")
    require(set(assignments) == {node_symbols[n] for n in internal}, "unexpected or unused forward assignments")
    require(used_constructors == set(constructors), "unexpected or unused constructors")
    return {"constructorCount": len(constructors), "forwardAssignmentCount": len(assignments), "inputs": len(inputs), "namedOutputCount": len(outputs), "nodeSymbols": node_symbols, "returnBindings": outputs, "basis": "Handwritten frontend topology, full stdlib AST traversal from actual named return outputs; no generated-name hash oracle."}


def negative_ast_controls(source, expected_nodes, expected_edges):
    """Verify the oracle rejects semantic/source defects not caught by counts."""
    def methods(tree):
        cls = next(item for item in tree.body if isinstance(item, ast.ClassDef))
        return {item.name: item for item in cls.body}

    controls = []
    tree = ast.parse(source)
    first_constructor = methods(tree)["__init__"].body[1].value
    first_constructor.func.attr = "Identity"
    controls.append(("wrong-constructor-kind", tree))

    tree = ast.parse(source)
    init = methods(tree)["__init__"]
    linear = next(item.value for item in init.body[1:] if item.value.func.attr == "Linear")
    feature = next(keyword for keyword in linear.keywords if keyword.arg == "out_features")
    feature.value = ast.Constant(value=feature.value.value + 1)
    controls.append(("wrong-constructor-parameter", tree))

    tree = ast.parse(source)
    init = methods(tree)["__init__"]
    dtype = next(keyword for item in init.body[1:] for keyword in item.value.keywords if keyword.arg == "dtype")
    dtype.value = ast.Attribute(value=ast.Name(id="torch", ctx=ast.Load()), attr="float64", ctx=ast.Load())
    controls.append(("wrong-constructor-dtype", tree))

    tree = ast.parse(source)
    forward = methods(tree)["forward"]
    forward.body[1].value.args[0] = ast.Name(id=forward.args.args[1].arg, ctx=ast.Load())
    controls.append(("wrong-forward-producer", tree))

    tree = ast.parse(source)
    methods(tree)["forward"].body[-1].value.keys[0].value += "_wrong_output"
    controls.append(("wrong-return-key", tree))

    tree = ast.parse(source)
    forward = methods(tree)["forward"]
    forward.body[-1].value.values[0] = ast.Name(id=forward.args.args[1].arg, ctx=ast.Load())
    controls.append(("wrong-return-producer", tree))

    tree = ast.parse(source)
    methods(tree)["forward"].body.insert(-1, ast.Assign(targets=[ast.Name(id="undeclared_value", ctx=ast.Store())], value=ast.Constant(value=7)))
    controls.append(("undeclared-forward-assignment", tree))

    if any(node["kind"] == "Add" for node in expected_nodes):
        tree = ast.parse(source)
        addition = next(statement.value for statement in methods(tree)["forward"].body[:-1] if isinstance(statement.value, ast.BinOp))
        addition.left, addition.right = addition.right, addition.left
        controls.append(("swapped-ordered-add-producers", tree))

    results = []
    for name, tree in controls:
        mutant_source = ast.unparse(ast.fix_missing_locations(tree)) + "\n"
        try:
            source_ast_contract(mutant_source, expected_nodes, expected_edges)
        except (AssertionError, ValueError, TypeError, KeyError) as error:
            results.append({"name": name, "status": "rejected-as-required", "reason": str(error), "mutantSource": mutant_source})
        else:
            raise AssertionError(f"Independent AST oracle incorrectly accepted negative control {name}")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    contracts_path = HERE / "expected-contracts.json"
    contracts = json.loads(contracts_path.read_text())["presets"]
    samples = json.loads(args.input.read_text())
    product_paths = [ROOT / "studio/src/authoringPresets.ts", ROOT / "studio/src/authoring.ts", Path(backend.__file__), Path(frontend.__file__)]
    origins = {str(p.relative_to(ROOT)): sha(p) for p in product_paths}
    require(all(p.is_relative_to(ROOT) for p in product_paths), "resolved package origin is outside formal project")
    require("torch" not in sys.modules, "torch imported before nonexecuting audit")
    results = []
    negative_controls = []
    try:
        require(all(samples["productBindings"][name] == value for name, value in origins.items() if name.startswith("studio/")), "frontend samples are not bound to the currently audited product bytes")
        for sample in samples["samples"]:
            draft = sample["draft"]
            before = deepcopy(draft)
            expected_nodes, edges, tensors, inventory = graph_contract(draft, sample["presets"], contracts)
            checked = validate_draft(draft, require_complete=True)
            require(checked["complete"] and not checked["issues"], "backend does not validate preset as complete")
            require(checked["tensors"] == tensors, "backend per-node declared shapes/dtypes differ from handwritten calculations")
            generated = generate_model(draft)
            require(generated["tensors"] == tensors, "generated receipt tensor declarations differ")
            require(draft == before, "backend mutated frontend draft input")
            ast_result = source_ast_contract(generated["source"], expected_nodes, edges)
            require("torch" not in sys.modules, "static generation unexpectedly imported torch")
            name = sample["caseId"]
            write_new(args.output / f"{name}-validation.json", checked)
            write_new(args.output / f"{name}-generation.json", generated)
            write_new(args.output / f"{name}-source.py.txt", generated["source"])
            write_new(args.output / f"{name}-independent-ast.json", ast_result)
            if name.startswith("single-"):
                controls = negative_ast_controls(generated["source"], expected_nodes, edges)
                write_new(args.output / f"{name}-negative-controls.json", controls)
                negative_controls.extend({"caseId": name, **{key: value for key, value in control.items() if key != "mutantSource"}} for control in controls)
            results.append({"caseId": name, "status": "passed", "presets": sample["presets"], "nodes": len(expected_nodes), "edges": len(edges), "tensorsChecked": len(tensors), "presetInventory": inventory, "ast": {k: v for k, v in ast_result.items() if k not in {"nodeSymbols", "returnBindings"}}})
        require(origins == {str(p.relative_to(ROOT)): sha(p) for p in product_paths}, "product source bytes changed during audit")
        write_new(args.output / "audit-summary.json", {"status": "passed", "scope": "frontend preset DAGs, hand-calculated declarations, full generated source AST", "modelExecution": "not_run", "torchImported": False, "samples": results, "negativeControls": negative_controls, "frontendIdentityChecks": samples.get("identityChecks"), "bindings": {"input": {"path": str(args.input.relative_to(ROOT)), "sha256": sha(args.input)}, "contracts": {"path": str(contracts_path.relative_to(ROOT)), "sha256": sha(contracts_path)}, "products": origins}, "limitations": ["No numerical runtime, model allocation, training/evaluation, browser gestures, visible layout or publication-size readability is certified.", "Identity collision and history checks reported here originate in the companion frontend script; their actual snapshots must be inspected separately."]})
    except BaseException as error:
        write_new(args.output / "FAILED.json", {"type": type(error).__name__, "message": str(error), "completedSamples": results, "productBindingsBefore": origins})
        raise
    print(json.dumps({"status": "passed", "samples": len(results), "nodes": sum(r["nodes"] for r in results), "modelExecution": "not_run", "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
