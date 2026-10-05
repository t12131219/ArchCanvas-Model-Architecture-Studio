"""Source-authored bypass counterexamples; variable names and operand side are not evidence."""

import unittest
from pathlib import Path

from archcanvas_python import analyze_project, analyze_source


ROOT = Path(__file__).resolve().parents[1]


class ResidualRoleTests(unittest.TestCase):
    def assert_add(self, body, roles, category="operator"):
        source = """from torch import nn
class Model(nn.Module):
    def __init__(self):
        self.linear = nn.Linear(4, 4)
        self.other = nn.Linear(4, 4)
        self.activation = nn.ReLU()
        self.recurrent = nn.LSTM(4, 4)
    def forward(self, x, independent):
""" + "\n".join("        " + line for line in body.splitlines()) + "\n"
        architecture = analyze_source(source, "Model")
        adds = [node for node in architecture["nodes"] if node["kind"] == "Add"]
        self.assertEqual(len(adds), 1)
        node = adds[0]
        ports = {port["id"]: port for port in node["ports"]}
        incoming = {ports[edge["target"]["portId"]]["name"]: edge["role"]
                    for edge in architecture["edges"] if edge["target"]["nodeId"] == node["id"]}
        self.assertEqual(incoming, roles)
        self.assertEqual({port["name"]: port["role"] for port in node["ports"] if port["direction"] == "in"}, roles)
        self.assertEqual(node["category"], category)
        return architecture

    def test_bypass_on_left_is_recovered_despite_misleading_variable_name(self):
        self.assert_add("residual = self.activation(self.linear(x))\nreturn x + residual",
                        {"left": "residual", "right": "data"}, "residual")

    def test_bypass_on_right_is_recovered_across_known_chain(self):
        self.assert_add("branch = self.activation(self.linear(x))\nreturn branch + x",
                        {"left": "data", "right": "residual"}, "residual")

    def test_parallel_branches_are_data_even_with_residual_variable_name(self):
        self.assert_add("residual = self.linear(x)\nother = self.other(x)\nreturn residual + other",
                        {"left": "data", "right": "data"})

    def test_independent_input_is_not_a_bypass(self):
        self.assert_add("return self.linear(x) + independent", {"left": "data", "right": "data"})

    def test_opaque_intermediate_cannot_prove_bypass(self):
        architecture = self.assert_add("branch = self.linear(plugin(x))\nreturn x + branch",
                                       {"left": "data", "right": "data"})
        self.assertTrue(any(node["evidence"] == "opaque" for node in architecture["nodes"]))

    def test_opaque_endpoint_cannot_prove_bypass(self):
        self.assert_add("unknown = plugin(x)\nreturn unknown + self.linear(unknown)",
                        {"left": "data", "right": "data"})

    def test_missing_return_is_opaque_and_cannot_prove_bypass(self):
        source = """from torch import nn
class NoResult(nn.Module):
    def __init__(self):
        self.linear = nn.Linear(4, 4)
    def forward(self, x):
        y = self.linear(x)
class Model(nn.Module):
    def __init__(self):
        self.empty = NoResult()
    def forward(self, x):
        return x + self.empty(x)
"""
        architecture = analyze_source(source, "Model")
        empty = next(node for node in architecture["nodes"] if node["label"] == "empty")
        self.assertEqual((empty["category"], empty["evidence"]), ("opaque", "opaque"))
        add = next(node for node in architecture["nodes"] if node["kind"] == "Add")
        self.assertEqual(add["category"], "operator")
        self.assertEqual({edge["role"] for edge in architecture["edges"]
                          if edge["target"]["nodeId"] == add["id"]}, {"data"})

    def test_same_tensor_twice_is_data(self):
        architecture = self.assert_add("residual = self.linear(x)\nreturn residual + residual",
                                       {"left": "data", "right": "data"})
        add = next(node for node in architecture["nodes"] if node["kind"] == "Add")
        self.assertEqual(len({edge["tensorId"] for edge in architecture["edges"]
                              if edge["target"]["nodeId"] == add["id"]}), 1)

    def test_distinct_slots_of_one_producer_are_not_ancestors(self):
        self.assert_add("y, (hidden, cell) = self.recurrent(x)\nreturn hidden + cell",
                        {"left": "data", "right": "data"})

    def test_path_from_sibling_output_does_not_claim_other_slot_is_ancestor(self):
        self.assert_add("y, (hidden, cell) = self.recurrent(x)\nreturn hidden + self.activation(y)",
                        {"left": "data", "right": "data"})

    def test_augmented_add_uses_the_same_proven_dependency_rule(self):
        self.assert_add("branch = self.linear(x)\nx += branch\nreturn x",
                        {"left": "residual", "right": "data"}, "residual")
        self.assert_add("branch = self.linear(x)\nbranch += x\nreturn branch",
                        {"left": "data", "right": "residual"}, "residual")

    def test_formal_cnn_bypass_is_the_right_operand(self):
        architecture = analyze_project(ROOT / "fixtures/residual_cnn", "model:ResidualCNN")
        adds = [node for node in architecture["nodes"] if node["kind"] == "Add"]
        self.assertEqual(len(adds), 2)
        for node in adds:
            ports = {port["id"]: port["name"] for port in node["ports"]}
            self.assertEqual({ports[edge["target"]["portId"]]: edge["role"]
                              for edge in architecture["edges"] if edge["target"]["nodeId"] == node["id"]},
                             {"left": "data", "right": "residual"})


if __name__ == "__main__":
    unittest.main()
