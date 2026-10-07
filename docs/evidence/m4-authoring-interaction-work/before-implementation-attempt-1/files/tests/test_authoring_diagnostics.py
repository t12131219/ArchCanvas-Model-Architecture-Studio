"""Handwritten error cases against the public authored-draft contract.

Expected identities/values come from these graphs, not implementation helpers,
labels, generated symbols, or a module execution.
"""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from archcanvas_authoring import DraftError, generate_model, validate_draft


def node(identity, kind, parameters=None, label="重复名称"):
    return {"id": identity, "kind": kind, "label": label, "parameters": parameters or {},
            "position": {"x": 0, "y": 0}}


def connection(identity, source, target, port="input"):
    return {"id": identity, "source": {"nodeId": source, "portId": "output"},
            "target": {"nodeId": target, "portId": port}}


def graph(nodes, edges):
    return {"schemaVersion": 1, "mode": "authored-draft", "id": "draft-abcd",
            "title": "从零建模", "revision": 0, "nodes": nodes, "edges": edges}


def chain(kind="Linear", parameters=None, shape=None, dtype="float32"):
    return graph([node("source", "Input", {"shape": shape or [2, 16], "dtype": dtype}),
                  node("consumer", kind, parameters), node("out", "Output")],
                 [connection("first", "source", "consumer"), connection("last", "consumer", "out")])


class AuthoringDiagnosticTests(unittest.TestCase):
    def failure(self, draft, function=validate_draft):
        before = deepcopy(draft)
        with self.assertRaises(DraftError) as captured:
            function(draft)
        self.assertEqual(draft, before, "failed validation/generation must not mutate the input")
        self.assertTrue(captured.exception.diagnostics)
        diagnostic = captured.exception.diagnostics[0]
        self.assertIn("code", diagnostic)
        self.assertIn("technical", diagnostic)
        self.assertRegex(diagnostic["message"], "[\u4e00-\u9fff]")
        # Diagnostics must be JSON, never exceptions/AST/source callables.
        json.dumps(captured.exception.diagnostics, allow_nan=False)
        return str(captured.exception), diagnostic

    def test_linear_contract_expected_is_parameter_actual_is_upstream_last_dimension(self):
        draft = chain(parameters={"in_features": 12})
        draft["nodes"].insert(1, node("other-linear", "Linear", {"in_features": 16}))
        # An identically labelled valid Linear cannot become the error target.
        for function in (validate_draft, generate_model):
            technical, error = self.failure(draft, function)
            self.assertEqual(technical, "重复名称: final input dimension 16 does not equal in_features 12.")
            self.assertEqual(error, {"code": "linear_input_features_mismatch",
                "message": "Linear 的输入末维为 16，但 in_features 为 12。请让 in_features 与上游末维一致。",
                "technical": technical, "nodeId": "consumer", "parameter": "in_features",
                "portId": "input", "expected": 12, "actual": 16})

    def test_parameter_type_and_range_failures_name_registered_field_only(self):
        cases = [("Input", "shape", [0]), ("Input", "dtype", "half"),
                 ("Linear", "in_features", True), ("GELU", "approximate", "fast"),
                 ("Dropout", "p", 2), ("Flatten", "start_dim", 9),
                 ("Conv2d", "stride", [1]), ("MaxPool2d", "ceil_mode", 1),
                 ("AdaptiveAvgPool2d", "output_size", [0, 1]),
                 ("BatchNorm2d", "momentum", -1), ("LayerNorm", "eps", 0),
                 ("Embedding", "num_embeddings", -4), ("Concat", "dim", 10)]
        for kind, parameter, value in cases:
            with self.subTest(kind=kind, parameter=parameter):
                draft = graph([node("exact-node", kind, {parameter: value})], [])
                _, error = self.failure(draft)
                self.assertEqual((error["code"], error["nodeId"], error["parameter"]),
                                 ("invalid_parameter", "exact-node", parameter))
                self.assertNotIn("actual", error, "arbitrary invalid values are not diagnostic payloads")
                self.assertNotIn("portId", error)

    def test_dtype_contracts_locate_input_port_without_inventing_parameter(self):
        cases = [(kind, "float64", "float32") for kind in ("Linear", "Conv2d", "BatchNorm2d", "LayerNorm")]
        cases += [(kind, "int64", ["float32", "float64"]) for kind in
                  ("ReLU", "GELU", "SiLU", "Dropout", "MaxPool2d", "AdaptiveAvgPool2d")]
        cases += [("Embedding", "float32", "int64")]
        for kind, actual, expected in cases:
            with self.subTest(kind=kind):
                _, error = self.failure(chain(kind, dtype=actual))
                self.assertEqual((error["nodeId"], error["portId"], error["expected"], error["actual"]),
                                 ("consumer", "input", expected, actual))
                self.assertNotIn("parameter", error)
        # Identity and Output have no floating-only restriction.
        self.assertTrue(validate_draft(chain("Identity", dtype="int64"))["complete"])

    def test_normalization_and_convolution_distinguish_rank_from_channels(self):
        cases = [("LayerNorm", {"normalized_shape": [12]}, [2, 16], "layer_norm_shape_mismatch", "normalized_shape", [12], [16]),
                 ("BatchNorm2d", {}, [2, 16], "input_rank_mismatch", None, 4, 2),
                 ("BatchNorm2d", {"num_features": 4}, [2, 3, 8, 8], "batch_norm_channels_mismatch", "num_features", 4, 3),
                 ("Conv2d", {}, [2, 16], "input_rank_mismatch", None, [3, 4], 2),
                 ("Conv2d", {"in_channels": 4}, [2, 3, 8, 8], "conv_input_channels_mismatch", "in_channels", 4, 3),
                 ("MaxPool2d", {}, [2, 16], "input_rank_mismatch", None, [3, 4], 2),
                 ("AdaptiveAvgPool2d", {}, [2, 16], "input_rank_mismatch", None, [3, 4], 2)]
        for kind, params, shape, code, parameter, expected, actual in cases:
            with self.subTest(kind=kind, code=code):
                _, error = self.failure(chain(kind, params, shape))
                self.assertEqual((error["code"], error.get("parameter"), error["expected"], error["actual"]),
                                 (code, parameter, expected, actual))
                self.assertEqual((error["nodeId"], error["portId"]), ("consumer", "input"))

    def test_spatial_invalidity_does_not_blame_one_of_multiple_possible_parameters(self):
        for kind, params, shape in [("Conv2d", {"kernel_size": [9, 9]}, [1, 3, 2, 2]),
                                   ("MaxPool2d", {"kernel_size": [9, 9]}, [1, 3, 2, 2])]:
            with self.subTest(kind=kind):
                _, error = self.failure(chain(kind, params, shape))
                self.assertEqual((error["code"], error["nodeId"], error["portId"]),
                                 ("nonpositive_spatial_output", "consumer", "input"))
                self.assertNotIn("parameter", error)
                self.assertLessEqual(error["actual"], 0)

    def test_existing_constructor_constraints_localize_real_field(self):
        cases = [("Conv2d", {"in_channels": 3, "out_channels": 4, "groups": 2}, "conv_groups_mismatch", "groups"),
                 ("MaxPool2d", {"kernel_size": [2, 2], "padding": [2, 0]}, "pool_padding_out_of_range", "padding")]
        for kind, params, code, parameter in cases:
            with self.subTest(kind=kind):
                _, error = self.failure(chain(kind, params, [1, 3, 8, 8]))
                self.assertEqual((error["code"], error["nodeId"], error["parameter"]),
                                 (code, "consumer", parameter))

    def test_batch_norm_small_sample_and_flatten_axes_use_declared_tensor(self):
        _, error = self.failure(chain("BatchNorm2d", {"num_features": 3}, [1, 3, 1, 1]))
        self.assertEqual((error["code"], error["actual"]), ("batch_norm_channel_samples", 1))
        for params, code, parameter in [({"start_dim": 3}, "dimension_out_of_range", "start_dim"),
                                       ({"end_dim": -3}, "dimension_out_of_range", "end_dim"),
                                       ({"start_dim": 1, "end_dim": 0}, "flatten_dimension_order", "start_dim")]:
            with self.subTest(params=params):
                _, error = self.failure(chain("Flatten", params))
                self.assertEqual((error["code"], error["nodeId"], error["parameter"], error["portId"]),
                                 (code, "consumer", parameter, "input"))

    def test_merge_diagnostics_use_actual_second_port_and_no_label_matching(self):
        cases = [("Add", "left", "right", {}, [2, 4], [2, 5], "float32", "add_input_shape_mismatch", None),
                 ("Add", "left", "right", {}, [2, 4], [2, 4], "int64", "merge_input_dtype_mismatch", None),
                 ("Add", "left", "right", {}, [2, 4], [4], "float32", "merge_input_rank_mismatch", None),
                 ("Concat", "a", "b", {"dim": 1}, [2, 4], [3, 4], "float32", "concat_input_shape_mismatch", "dim"),
                 ("Concat", "a", "b", {"dim": 3}, [2, 4], [2, 4], "float32", "dimension_out_of_range", "dim")]
        for kind, first, second, params, a, b, dtype, code, parameter in cases:
            with self.subTest(kind=kind, code=code):
                draft = graph([node("a-input", "Input", {"shape": a}),
                               node("b-input", "Input", {"shape": b, "dtype": dtype}),
                               node("merge", kind, params), node("out", "Output")],
                              [connection("e1", "a-input", "merge", first),
                               connection("e2", "b-input", "merge", second), connection("e3", "merge", "out")])
                _, error = self.failure(draft)
                self.assertEqual((error["code"], error["nodeId"], error.get("parameter")), (code, "merge", parameter))
                self.assertEqual(error["portId"], first if code == "dimension_out_of_range" else second)

    def test_incomplete_issues_are_chinese_and_generate_reuses_exact_declared_targets(self):
        draft = graph([node("input", "Input"), node("add", "Add"), node("out", "Output")],
                      [connection("to-output", "add", "out")])
        validation = validate_draft(draft)
        self.assertFalse(validation["complete"])
        issue = next(i for i in validation["issues"] if i["code"] == "unbound-input")
        self.assertEqual((issue["nodeId"], issue["portIds"]), ("add", ["left", "right"]))
        self.assertNotIn("portId", issue, "two missing ports have no single blame target")
        with self.assertRaises(DraftError) as caught:
            generate_model(draft)
        self.assertEqual(caught.exception.diagnostics, validation["issues"])
        self.assertEqual(str(caught.exception), "Draft is incomplete: 重复名称: connect left, right. Every module must contribute to a named Output before generating Python.")
        single = chain()
        single["edges"].pop()
        issue = next(i for i in validate_draft(single)["issues"] if i["code"] == "unbound-input")
        self.assertEqual((issue["nodeId"], issue["portId"], issue["portIds"]), ("out", "input", ["input"]))

    def test_malformed_global_budget_identity_and_duplicates_never_fabricate_node_target(self):
        cases = []
        malformed = chain(); malformed["extra"] = True; cases.append(malformed)
        bad_id = chain(); bad_id["nodes"][1]["id"] = "<script>"; cases.append(bad_id)
        duplicated = chain(); duplicated["nodes"].append(deepcopy(duplicated["nodes"][1])); cases.append(duplicated)
        early_bad_duplicate = deepcopy(duplicated); early_bad_duplicate["nodes"][1]["parameters"]["bias"] = 4; cases.append(early_bad_duplicate)
        too_many = chain(); too_many["nodes"] = too_many["nodes"] * 43; cases.append(too_many)
        tensor_budget = chain("Identity", shape=[1000000, 1000000]); cases.append(tensor_budget)
        for index, draft in enumerate(cases):
            with self.subTest(index=index):
                _, error = self.failure(draft)
                self.assertNotIn("nodeId", error)
                self.assertNotIn("parameter", error)
                self.assertNotIn("portId", error)

    def test_unknown_field_and_nonexistent_port_do_not_suggest_a_fake_editor_field(self):
        unknown = chain(); unknown["nodes"][1]["parameters"]["__import__"] = "bad"
        _, error = self.failure(unknown)
        self.assertEqual((error["code"], error["nodeId"]), ("unknown_parameter", "consumer"))
        self.assertNotIn("parameter", error)
        port = chain(); port["edges"][0]["target"]["portId"] = "imaginary"
        _, error = self.failure(port)
        self.assertEqual((error["code"], error["edgeId"], error["endpoint"]),
                         ("invalid_connection_endpoint", "first", "target"))
        self.assertNotIn("nodeId", error)
        self.assertNotIn("portId", error)
        rebound = chain(); rebound["edges"].append(connection("duplicate-input", "source", "consumer"))
        _, error = self.failure(rebound)
        self.assertEqual((error["code"], error["nodeId"], error["portId"]),
                         ("input_already_bound", "consumer", "input"))

    def test_injected_labels_and_parameters_remain_data_and_invalid_graph_never_reaches_source_analysis(self):
        label = "<img src=x onerror=alert(1)>'); __import__('os').system('false')"
        draft = chain(parameters={"in_features": 12})
        draft["nodes"][1]["label"] = label
        with patch("archcanvas_authoring.draft.analyze_source", side_effect=AssertionError("invalid graph parsed")), \
             patch("builtins.exec", side_effect=AssertionError("execution forbidden")), \
             patch("builtins.eval", side_effect=AssertionError("evaluation forbidden")):
            technical, diagnostic = self.failure(draft, generate_model)
        self.assertTrue(technical.startswith(label + ":"))
        self.assertNotIn(label, diagnostic["message"])
        self.assertEqual(diagnostic["nodeId"], "consumer")
        draft["nodes"][1]["parameters"]["in_features"] = 16
        with patch("builtins.exec", side_effect=AssertionError("execution forbidden")), \
             patch("builtins.eval", side_effect=AssertionError("evaluation forbidden")):
            result = generate_model(draft)
        self.assertNotIn(label, result["source"])
        self.assertEqual(result["verification"]["modelExecution"], "not_run")
        draft["nodes"][1]["parameters"]["in_features"] = "__import__('os').system('false')"
        _, diagnostic = self.failure(draft)
        self.assertEqual(diagnostic["code"], "invalid_parameter")
        self.assertNotIn("actual", diagnostic)

    def test_draft_error_legacy_constructor_keeps_no_unproven_diagnostic(self):
        self.assertEqual(DraftError("legacy contract").diagnostics, [])
        raw = [{"code": "test", "message": "错误", "technical": "failure"}]
        error = DraftError("failure", diagnostics=raw)
        raw[0]["message"] = "changed"
        self.assertEqual(str(error), "failure")
        self.assertEqual(error.diagnostics[0]["message"], "错误")


if __name__ == "__main__":
    unittest.main()
