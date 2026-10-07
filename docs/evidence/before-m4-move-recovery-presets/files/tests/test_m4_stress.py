"""Source contract for the 300-layer static scene stress fixture."""

import ast
import unittest
from pathlib import Path

from archcanvas_python import analyze_project


ROOT = Path(__file__).resolve().parents[1]


class M4StressSourceTests(unittest.TestCase):
    def test_source_declares_300_layers_without_runtime_generation(self):
        source = ROOT / "fixtures" / "stress_300" / "model.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        forbidden = (ast.For, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
        self.assertFalse(any(isinstance(node, forbidden) for node in ast.walk(tree)))
        declaration = next(node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "Sequential")
        self.assertEqual(len(declaration.args), 300)
        self.assertEqual([item.func.attr for item in declaration.args], ["Linear", "ReLU"] * 150)

        architecture = analyze_project(source.parent, "model:DenseStress300")
        self.assertEqual(len(architecture["nodes"]), 304)
        self.assertEqual(len(architecture["edges"]), 304)
        self.assertFalse(any(node["evidence"] == "opaque" for node in architecture["nodes"]))
        layers = [node for node in architecture["nodes"] if node["kind"] in ("Linear", "ReLU")]
        self.assertEqual([node["kind"] for node in layers], ["Linear", "ReLU"] * 150)
        self.assertEqual(len({node["instanceId"] for node in layers}), 300)
        network = next(node for node in architecture["nodes"] if node["label"] == "network")
        self.assertEqual(network["repeat"], {"count": 300, "sharing": "independent"})
        self.assertEqual(network["children"], [node["id"] for node in layers])
        for left, right in zip(layers, layers[1:]):
            self.assertTrue(any(edge["source"]["nodeId"] == left["id"] and edge["target"]["nodeId"] == right["id"] for edge in architecture["edges"]))
        self.assertEqual([item["level"] for item in architecture["diagnostics"]], ["info"])


if __name__ == "__main__":
    unittest.main()
