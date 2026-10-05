"""Authored graph contracts with hand-calculated examples and corruptions.

No model import or execution is used. Generated Python is parsed as data.
"""
from copy import deepcopy
import ast
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from archcanvas_authoring import DraftError, generate_model, module_catalog, validate_draft, verify_generated
from archcanvas_python import analyze_source


def node(identity, kind, parameters=None, label=None):
    return {"id": identity, "kind": kind, "label": label or identity, "parameters": parameters or {},
            "position": {"x": 20, "y": 30}}


def edge(identity, source, target, port="input"):
    return {"id": identity, "source": {"nodeId": source, "portId": "output"},
            "target": {"nodeId": target, "portId": port}}


def graph(nodes, edges):
    return {"schemaVersion": 1, "mode": "authored-draft", "id": "draft-test", "title": "新模型",
            "revision": 0, "nodes": nodes, "edges": edges}


def linear_graph():
    return graph([node("x", "Input", {"shape": [2, 4]}),
                  node("fc", "Linear", {"in_features": 4, "out_features": 3}), node("out", "Output")],
                 [edge("a", "x", "fc"), edge("b", "fc", "out")])


class AuthoringContractTests(unittest.TestCase):
    def test_blank_and_dangling_can_be_saved_but_cannot_generate(self):
        blank = graph([], [])
        self.assertFalse(validate_draft(blank)["complete"])
        with self.assertRaises(DraftError):
            generate_model(blank)
        partial = linear_graph()
        partial["edges"].pop()
        self.assertFalse(validate_draft(partial)["complete"])
        with self.assertRaises(DraftError):
            generate_model(partial)

    def test_static_fresh_source_roundtrip_and_labels_never_become_code(self):
        draft = linear_graph()
        draft["nodes"][1]["label"] = "投影'); raise RuntimeError('labels are data')"
        before = json.dumps(draft)
        result = generate_model(draft)
        self.assertEqual(json.dumps(draft), before)
        self.assertEqual(result["tensors"]["out"], {"shape": [2, 3], "dtype": "float32"})
        self.assertEqual(result["verification"]["modelExecution"], "not_run")
        self.assertNotIn("labels are data", result["source"])
        tree = ast.parse(result["source"])
        constructor = next(n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "Linear")
        args = {a.arg: ast.unparse(a.value) for a in constructor.keywords}
        self.assertEqual(args, {"in_features": "4", "out_features": "3", "bias": "True", "dtype": "torch.float32"})
        self.assertEqual(verify_generated(draft, analyze_source(result["source"], result["entry"]))["status"], "passed")

    def test_no_model_import_execution_or_original_source_write(self):
        draft = linear_graph()
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            source = Path(directory) / "original.py"
            source.write_text("raise RuntimeError('must remain data')\n")
            before = source.read_bytes()
            # The authoring pipeline cannot invoke any execution API. It only
            # reaches the already loaded standard-library AST frontend.
            with patch("builtins.exec", side_effect=AssertionError("execution forbidden")), patch("builtins.eval", side_effect=AssertionError("evaluation forbidden")):
                result = generate_model(draft)
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(result["verification"]["status"], "passed")

    def test_asymmetric_strided_dilated_conv_and_ceil_pool(self):
        # Conv: H=(9+2-2*(3-1)-1)//2+1=4, W=(11+0-1*(2-1)-1)//3+1=4.
        # Ceil pool k3,s2,p1: both axes -> 3.
        draft = graph([node("image", "Input", {"shape": [2, 4, 9, 11]}),
                       node("conv", "Conv2d", {"in_channels": 4, "out_channels": 6, "groups": 2,
                                               "kernel_size": [3, 2], "stride": [2, 3], "padding": [1, 0], "dilation": [2, 1]}),
                       node("pool", "MaxPool2d", {"kernel_size": [3, 3], "stride": [2, 2], "padding": [1, 1], "ceil_mode": True}),
                       node("out", "Output")],
                      [edge("a", "image", "conv"), edge("b", "conv", "pool"), edge("c", "pool", "out")])
        result = generate_model(draft)
        self.assertEqual(result["tensors"]["conv"]["shape"], [2, 6, 4, 4])
        self.assertEqual(result["tensors"]["out"]["shape"], [2, 6, 3, 3])

    def test_ceil_pool_excludes_window_starting_in_right_padding(self):
        draft = graph([node("x", "Input", {"shape": [1, 2, 3, 3]}),
                       node("pool", "MaxPool2d", {"kernel_size": [2, 2], "stride": [2, 2], "padding": [1, 1], "ceil_mode": True}),
                       node("out", "Output")], [edge("a", "x", "pool"), edge("b", "pool", "out")])
        self.assertEqual(generate_model(draft)["tensors"]["out"]["shape"], [1, 2, 2, 2])

    def test_negative_concat_axis_is_explicitly_normalized(self):
        draft = graph([node("a", "Input", {"shape": [2, 3]}), node("b", "Input", {"shape": [2, 5]}),
                       node("cat", "Concat", {"dim": -1}), node("out", "Output")],
                      [edge("a1", "a", "cat", "a"), edge("b1", "b", "cat", "b"), edge("o", "cat", "out")])
        result = generate_model(draft)
        self.assertEqual(result["tensors"]["out"]["shape"], [2, 8])
        self.assertIn("dim=1)", result["source"])
        self.assertEqual(result["verification"]["scalarNormalizations"]["cat"], {"declaredDim": -1, "effectiveDim": 1})
        self.assertFalse(any(n["kind"] == "Unary" for n in result["architecture"]["nodes"]))
        tampered = result["source"].replace("dim=1)", "dim=0)")
        with self.assertRaises(DraftError):
            verify_generated(draft, analyze_source(tampered, result["entry"]))

    def test_repeated_same_expression_operations_have_distinct_identities(self):
        draft = graph([node("x", "Input", {"shape": [2, 4]}), node("sum1", "Add"), node("sum2", "Add"),
                       node("out1", "Output"), node("out2", "Output")],
                      [edge("a", "x", "sum1", "left"), edge("b", "x", "sum1", "right"),
                       edge("c", "x", "sum2", "left"), edge("d", "x", "sum2", "right"),
                       edge("o1", "sum1", "out1"), edge("o2", "sum2", "out2")])
        result = generate_model(draft)
        self.assertNotEqual(result["nodeBindings"]["sum1"], result["nodeBindings"]["sum2"])
        self.assertEqual(len(result["architecture"]["nodes"]), 6)

    def test_multiple_named_outputs_preserve_same_tensor_occurrences(self):
        draft = graph([node("x", "Input", {"shape": [3], "dtype": "int64"}), node("a", "Output"), node("b", "Output")],
                      [edge("a1", "x", "a"), edge("b1", "x", "b")])
        result = generate_model(draft)
        outputs = [n for n in result["architecture"]["nodes"] if n["kind"] == "Output"]
        self.assertEqual([n["outputPath"] for n in outputs], [[{"kind": "key", "key": "a"}], [{"kind": "key", "key": "b"}]])
        self.assertEqual(len({e["tensorId"] for e in result["architecture"]["edges"]}), 1)

    def test_source_bound_fields_cannot_enter_draft_contract(self):
        for extra in ({"sourceDigest": "fake"}, {"architecture": {}}, {"projectId": "imported"}):
            draft = linear_graph()
            draft.update(extra)
            with self.assertRaises(DraftError):
                validate_draft(draft)
        draft = linear_graph()
        draft["nodes"][1]["source"] = {"path": "original.py"}
        with self.assertRaises(DraftError):
            validate_draft(draft)

    def test_bool_and_extreme_integer_fields_are_contract_errors(self):
        for value in (True, -1, 0, 2**10000, 1.2):
            draft = linear_graph()
            draft["nodes"][1]["parameters"]["in_features"] = value
            with self.assertRaises(DraftError):
                validate_draft(draft)
        draft = linear_graph()
        draft["nodes"][0]["position"]["x"] = 2**10000
        with self.assertRaises(DraftError):
            validate_draft(draft)

    def test_port_ownership_duplicate_producer_and_cycle_reject(self):
        draft = linear_graph()
        for mutate in (lambda d: d["edges"][0]["source"].update(nodeId="out"),
                       lambda d: d["edges"].append(edge("extra", "x", "fc")),
                       lambda d: d["edges"][0]["source"].update(nodeId="fc")):
            case = deepcopy(draft)
            mutate(case)
            with self.assertRaises(DraftError):
                validate_draft(case)

    def test_catalog_only_advertises_static_supported_modules_and_returns_copy(self):
        catalog = module_catalog()
        kinds = {m["kind"] for m in catalog["modules"]}
        self.assertEqual(kinds, {"Input", "Output", "Linear", "ReLU", "GELU", "SiLU", "Identity", "Dropout", "Flatten",
                                 "Conv2d", "MaxPool2d", "AdaptiveAvgPool2d", "BatchNorm2d", "LayerNorm", "Embedding", "Add", "Concat"})
        self.assertIn("MultiheadAttention", catalog["unsupported"])
        catalog["modules"][0]["defaults"]["shape"].append(99)
        self.assertEqual(module_catalog()["modules"][0]["defaults"]["shape"], [1, 16])

    def test_exact_graph_checker_rejects_nonisomorphic_inventory_and_tensor_corruption(self):
        draft = linear_graph()
        original = generate_model(draft)["architecture"]
        cases = []
        case = deepcopy(original); case["nodes"].append(deepcopy(case["nodes"][0])); cases.append(case)
        case = deepcopy(original); case["nodes"].pop(); cases.append(case)
        case = deepcopy(original); case["edges"][0]["tensorId"] = "foreign"; cases.append(case)
        case = deepcopy(original); case["edges"][0]["source"]["portId"] = "same-name-foreign-port"; cases.append(case)
        case = deepcopy(original); case["edges"].append(deepcopy(case["edges"][0])); cases.append(case)
        case = deepcopy(original); case["nodes"][0]["ports"][0]["ordinal"] = 9; cases.append(case)
        case = deepcopy(original); case["nodes"][0]["ports"][0]["role"] = "memory"; cases.append(case)
        case = deepcopy(original); next(n for n in case["nodes"] if n["kind"] == "Linear")["parameters"]["bias"] = False; cases.append(case)
        case = deepcopy(original); next(n for n in case["nodes"] if n["kind"] == "Linear")["category"] = "activation"; cases.append(case)
        case = deepcopy(original); case["edges"][0]["role"] = "residual"; cases.append(case)
        for i, case in enumerate(cases):
            with self.subTest(corruption=i), self.assertRaises(DraftError):
                verify_generated(draft, case)


if __name__ == "__main__":
    unittest.main()
