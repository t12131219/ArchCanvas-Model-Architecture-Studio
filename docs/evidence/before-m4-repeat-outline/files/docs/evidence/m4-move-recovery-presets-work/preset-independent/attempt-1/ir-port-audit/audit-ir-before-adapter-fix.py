"""Independent IR endpoint audit against saved frontend and actual source AST.

Bindings are recovered from observed source expressions and named outputs,
not copied from generate_model's nodeBindings/portBindings/verifier receipt.
No backend generation or user model execution takes place in this audit.
"""
import argparse
import ast
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
spec = importlib.util.spec_from_file_location("handwritten_preset_ast_audit", HERE / "audit.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_expression(value):
    return ast.dump(ast.parse(value, mode="eval"), include_attributes=False)


def check_ir(generated, expected_nodes, expected_edges, ast_result):
    architecture = generated["architecture"]
    nodes, edges = architecture["nodes"], architecture["edges"]
    require = oracle.require
    symbols = ast_result["nodeSymbols"]
    classes = [item for item in ast.parse(generated["source"]).body if isinstance(item, ast.ClassDef)]
    forward = next(method for method in classes[0].body if method.name == "forward")
    expressions = {statement.targets[0].id: ast.unparse(statement.value) for statement in forward.body[:-1]}
    roots = [node for node in nodes if node["kind"] == "Module"]
    require(len(roots) == 1 and len(nodes) == len(expected_nodes) + 1, "IR root/node inventory differs")
    root = roots[0]
    mapped, ids = {}, set()
    for node in expected_nodes:
        if node["kind"] == "Input":
            matches = [actual for actual in nodes if actual["kind"] == "Input" and actual["label"] == symbols[node["id"]]]
        elif node["kind"] == "Output":
            matches = [actual for actual in nodes if actual["kind"] == "Output" and actual.get("outputPath") == [{"kind": "key", "key": node["id"]}]]
        else:
            expression = parse_expression(expressions[symbols[node["id"]]])
            matches = [actual for actual in nodes if actual["kind"] == node["kind"] and parse_expression(actual["source"]["expression"]) == expression]
        require(len(matches) == 1, f"Cannot uniquely map source operation/output {node['id']} to observed IR")
        actual = matches[0]
        require(actual["id"] not in ids, "Distinct operations alias in IR")
        ids.add(actual["id"])
        mapped[node["id"]] = actual
        require(actual.get("parentId") == root["id"] and actual["children"] == [] and "repeat" not in actual, "Preset IR node has unexpected hierarchy/repeat semantics")
        expected_params = {} if node["kind"] in {"Input", "Output", "Add"} else deepcopy(node["parameters"])
        if node["kind"] in {"Linear", "Conv2d"}:
            expected_params["dtype"] = {"expression": "torch.float32", "origin": "unknown"}
        require(oracle.exact_json(actual["parameters"], expected_params), f"Observed IR exact parameters differ for {node['id']}")
        require(actual["evidence"] == ("source" if node["kind"] in {"Input", "Output", "Add"} else "contract"), "Unexpected source/contract evidence marker")
    require(root.get("parentId") is None and Counter(root["children"]) == Counter(ids), "IR root membership differs")
    categories = {"Input": "input", "Output": "output", "Linear": "linear", "ReLU": "activation", "Conv2d": "convolution", "MaxPool2d": "pooling", "AdaptiveAvgPool2d": "pooling", "Flatten": "operator", "Identity": "operator", "Add": "residual"}
    port_bindings = {}
    all_port_ids = set()
    for node in expected_nodes:
        actual = mapped[node["id"]]
        require(actual["category"] == categories[node["kind"]], f"Observed IR category differs for {node['id']}")
        if node["kind"] == "Input":
            expected_ports = [("output", symbols[node["id"]], "out", "data", 0)]
        elif node["kind"] == "Output":
            expected_ports = [("input", "value", "in", "data", 0)]
        elif node["kind"] == "Add":
            expected_ports = [("left", "left", "in", "data", 0), ("right", "right", "in", "residual", 1), ("output", "output", "out", "data", 0)]
        else:
            expected_ports = [("input", "input", "in", "data", 0), ("output", "output", "out", "data", 0)]
        require(len(actual["ports"]) == len(expected_ports), "Unexpected IR port inventory")
        for draft_port, name, direction, role, ordinal in expected_ports:
            matches = [port for port in actual["ports"] if {k: port.get(k) for k in ("name", "direction", "role", "ordinal")} == {"name": name, "direction": direction, "role": role, "ordinal": ordinal}]
            require(len(matches) == 1, f"Exact observed IR port {node['id']}.{draft_port} differs")
            identity = matches[0]["id"]
            require(isinstance(identity, str) and identity not in all_port_ids, "IR port identity duplicated or invalid")
            all_port_ids.add(identity)
            port_bindings[node["id"], draft_port] = identity
    expected_edges_observed_ids = []
    for source, source_port, target, target_port in expected_edges:
        role = "residual" if mapped[target]["kind"] == "Add" and target_port == "right" else "data"
        expected_edges_observed_ids.append((mapped[source]["id"], port_bindings[source, source_port], mapped[target]["id"], port_bindings[target, target_port], role))
    inputs = [node for node in expected_nodes if node["kind"] == "Input"]
    require(len(root["ports"]) == len(inputs), "Root input port inventory differs")
    for ordinal, node in enumerate(inputs):
        matches = [port for port in root["ports"] if {k: port.get(k) for k in ("name", "direction", "role", "ordinal")} == {"name": symbols[node["id"]], "direction": "in", "role": "data", "ordinal": ordinal}]
        require(len(matches) == 1 and matches[0]["id"] not in all_port_ids, "Root input port differs or aliases child port")
        all_port_ids.add(matches[0]["id"])
        expected_edges_observed_ids.append((mapped[node["id"]]["id"], port_bindings[node["id"], "output"], root["id"], matches[0]["id"], "data"))
    actual_edges = [(e["source"]["nodeId"], e["source"]["portId"], e["target"]["nodeId"], e["target"]["portId"], e["role"]) for e in edges]
    require(Counter(actual_edges) == Counter(expected_edges_observed_ids), "Full IR endpoint/role inventory differs from handwritten graph")
    require(len({e["id"] for e in edges}) == len(edges), "Duplicate IR edge identities")
    producer_tensors = {}
    tensor_producers = {}
    for edge in edges:
        endpoint = edge["source"]["nodeId"], edge["source"]["portId"]
        tensor = edge["tensorId"]
        require(isinstance(tensor, str) and bool(tensor), "Malformed tensor identity")
        if endpoint in producer_tensors:
            require(producer_tensors[endpoint] == tensor, "Fan-out of one producer lost a shared tensor identity")
        if tensor in tensor_producers:
            require(tensor_producers[tensor] == endpoint, "Distinct producers alias one tensor identity")
        producer_tensors[endpoint] = tensor
        tensor_producers[tensor] = endpoint
    return {"status": "passed", "rootCount": 1, "draftNodes": len(expected_nodes), "draftEdges": len(expected_edges), "irNodes": len(nodes), "irEdges": len(edges), "inputRootBindings": len(inputs), "exactPorts": len(all_port_ids), "producerTensors": len(producer_tensors), "nodeBindingsRecoveredFromSourceAndOutputPaths": {key: value["id"] for key, value in mapped.items()}, "scope": "Source/return-derived node inventory, exact type/params/category/evidence/ports/roles, full edge inventory and tensor fan-out identity; receipt nodeBindings and portBindings were not used."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    samples = json.loads(args.input.read_text())
    contracts = json.loads((HERE / "expected-contracts.json").read_text())["presets"]
    input_paths = [args.input, HERE / "expected-contracts.json", HERE / "audit.py", Path(__file__)]
    input_paths.extend(args.receipts / f"{sample['caseId']}-generation.json" for sample in samples["samples"])
    before = {str(path.relative_to(ROOT)): digest(path) for path in input_paths}
    results = []
    negatives = []
    try:
        for sample in samples["samples"]:
            expected_nodes, expected_edges, _, _ = oracle.graph_contract(sample["draft"], sample["presets"], contracts)
            generated = json.loads((args.receipts / f"{sample['caseId']}-generation.json").read_text())
            ast_result = oracle.source_ast_contract(generated["source"], expected_nodes, expected_edges)
            result = check_ir(generated, expected_nodes, expected_edges, ast_result)
            results.append({"caseId": sample["caseId"], **result})
            oracle.write_new(args.output / f"{sample['caseId']}-ir-audit.json", result)
            if sample["caseId"] == "single-residual-mlp":
                for name in ["residual-edge-role-lost", "residual-port-ordinal-swapped", "return-output-key-misbound", "fan-out-tensor-identity-split"]:
                    mutant = deepcopy(generated)
                    graph = mutant["architecture"]
                    if name == "residual-edge-role-lost":
                        next(e for e in graph["edges"] if e["role"] == "residual")["role"] = "data"
                    elif name == "residual-port-ordinal-swapped":
                        addition = next(node for node in graph["nodes"] if node["kind"] == "Add")
                        addition["ports"][1]["ordinal"] = 0
                    elif name == "return-output-key-misbound":
                        next(node for node in graph["nodes"] if node["kind"] == "Output")["outputPath"][0]["key"] += "_wrong"
                    else:
                        next(e for e in graph["edges"] if e["role"] == "residual")["tensorId"] += "_wrong"
                    try:
                        check_ir(mutant, expected_nodes, expected_edges, ast_result)
                    except (AssertionError, ValueError, KeyError, TypeError) as error:
                        negatives.append({"name": name, "status": "rejected-as-required", "reason": str(error)})
                    else:
                        raise AssertionError(f"Independent IR oracle incorrectly accepted {name}")
        oracle.require(before == {str(path.relative_to(ROOT)): digest(path) for path in input_paths}, "Stored input bytes changed during independent IR audit")
        oracle.require("torch" not in sys.modules, "Supplemental static IR audit imported torch")
        oracle.write_new(args.output / "audit-summary.json", {"status": "passed", "modelExecution": "not_run", "samples": results, "negativeControls": negatives, "inputBindings": before, "totals": {key: sum(result[key] for result in results) for key in ("draftNodes", "draftEdges", "irNodes", "irEdges", "inputRootBindings", "exactPorts", "producerTensors")}, "limitations": ["Stored generated source/IR receipts only; no fresh UI, runtime execution or numerical test.", "Tensor shape/dtype conclusions remain declared/static and are proven separately by the primary handwritten oracle."]})
    except BaseException as error:
        oracle.write_new(args.output / "FAILED.json", {"type": type(error).__name__, "message": str(error), "completedSamples": results, "inputBindingsBefore": before})
        raise
    print(json.dumps({"status": "passed", "samples": len(results), "negativeControls": len(negatives), "modelExecution": "not_run", "output": str(args.output)}))


if __name__ == "__main__":
    main()
