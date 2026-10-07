"""Independent M4 holdout checks for a fresh vision architecture."""

import unittest
from pathlib import Path

from archcanvas_python import analyze_project

from m4_holdout_oracle import (EXPECTED_OPAQUE, EXPECTED_VIT_CONTRACT_COUNTS,
                               EXPECTED_VIT_PARAMETERS, EXPECTED_VIT_RELATIONS,
                               FAMILY_EXPECTATIONS)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "holdout_vit"


class M4HoldoutTests(unittest.TestCase):
    def family(self, entry):
        architecture = analyze_project(ROOT / "fixtures" / "holdout_families", "model:" + entry)
        expected = FAMILY_EXPECTATIONS[entry]
        prefix = "instance:model." + entry
        names = {}
        nodes = {}
        ports = {}
        for node in architecture["nodes"]:
            instance = node.get("instanceId", "")
            if instance == prefix:
                name = "root"
            elif instance.startswith(prefix + "."):
                name = instance.removeprefix(prefix + ".")
                if "@" in node["id"]:
                    name += "@" + node["id"].rsplit("@", 1)[1]
            elif node["kind"] == "Input":
                name = "input." + node["label"]
            elif node["kind"] == "Output":
                name = "output" + node["id"].rsplit(":", 1)[1]
            elif node["kind"] == "Repeat":
                name = "repeat." + node["label"]
            else:
                name = node["kind"]
            self.assertNotIn(name, nodes, "Ambiguous holdout node " + name)
            names[node["id"]] = name
            nodes[name] = node
            ports.update({port["id"]: port["name"] for port in node["ports"]})
        observed_nodes = {name: (node["kind"], node["category"], node["evidence"]) for name, node in nodes.items()}
        self.assertEqual(observed_nodes, expected["nodes"])
        observed_relations = {
            (names[edge["source"]["nodeId"]], ports[edge["source"]["portId"]],
             names[edge["target"]["nodeId"]], ports[edge["target"]["portId"]], edge["role"])
            for edge in architecture["edges"]
        }
        self.assertEqual(observed_relations, expected["relations"])
        self.assertEqual(len(architecture["edges"]), len(expected["relations"]))
        for name, parameters in expected["parameters"].items():
            self.assertEqual(nodes[name]["parameters"], parameters)
        for name, path in expected.get("outputPaths", {}).items():
            self.assertEqual(nodes[name]["outputPath"], path)
        warnings = [item["message"] for item in architecture["diagnostics"] if item["level"] == "warning"]
        self.assertEqual(len(warnings), len(expected["warnings"]))
        for fragment in expected["warnings"]:
            self.assertTrue(any(fragment in warning for warning in warnings))
        return architecture, nodes

    def vit_relations(self, architecture):
        instance_names = {
            "instance:model.PatchVisionEncoder": "root",
            "instance:model.PatchVisionEncoder.patch_projection": "patch",
            "instance:model.PatchVisionEncoder.block": "block",
            "instance:model.PatchVisionEncoder.block.norm": "norm",
            "instance:model.PatchVisionEncoder.block.attention": "attention",
            "instance:model.PatchVisionEncoder.block.mlp": "mlp",
            "instance:model.PatchVisionEncoder.block.mlp.0": "expand",
            "instance:model.PatchVisionEncoder.block.mlp.1": "gelu",
            "instance:model.PatchVisionEncoder.block.mlp.2": "project",
            "instance:model.PatchVisionEncoder.classifier": "classifier",
        }
        operator_names = {
            "Flatten": "flatten", "Transpose": "transpose", "Mean": "pool",
            "Input": "image", "Output": "output",
        }
        names = {}
        ports = {}
        for node in architecture["nodes"]:
            if node.get("instanceId") in instance_names:
                name = instance_names[node["instanceId"]]
            elif node["kind"] == "Add":
                name = {
                    "tokens + attended": "attention_residual",
                    "tokens + self.mlp(tokens)": "mlp_residual",
                }[node["source"]["expression"]]
            else:
                name = operator_names[node["kind"]]
            names[node["id"]] = name
            ports.update({port["id"]: port["name"] for port in node["ports"]})
        return {
            (names[edge["source"]["nodeId"]], ports[edge["source"]["portId"]],
             names[edge["target"]["nodeId"]], ports[edge["target"]["portId"]], edge["role"])
            for edge in architecture["edges"]
        }

    def test_vit_patch_attention_and_residual_oracle(self):
        architecture = analyze_project(FIXTURE, "model:PatchVisionEncoder")
        self.assertEqual(architecture["entry"], "model:PatchVisionEncoder")
        self.assertEqual([item["path"] for item in architecture["sources"]], ["model.py"])
        self.assertFalse([node for node in architecture["nodes"] if node["evidence"] == "opaque"])

        counts = {
            kind: sum(node["kind"] == kind for node in architecture["nodes"])
            for kind in EXPECTED_VIT_CONTRACT_COUNTS
        }
        self.assertEqual(counts, EXPECTED_VIT_CONTRACT_COUNTS)
        self.assertEqual(len(architecture["nodes"]), sum(EXPECTED_VIT_CONTRACT_COUNTS.values()))
        self.assertEqual(len(architecture["edges"]), len(EXPECTED_VIT_RELATIONS))
        self.assertEqual(self.vit_relations(architecture), EXPECTED_VIT_RELATIONS)

        by_instance = {node.get("instanceId", "").rsplit(".", 1)[-1]: node for node in architecture["nodes"]}
        for instance, expected in EXPECTED_VIT_PARAMETERS.items():
            node = by_instance[instance]
            self.assertEqual(node["kind"], expected["kind"])
            for key, value in expected["parameters"].items():
                self.assertEqual(node["parameters"].get(key), value, (instance, key))

        patch = by_instance["patch_projection"]
        flatten = next(node for node in architecture["nodes"] if node["kind"] == "Flatten")
        transpose = next(node for node in architecture["nodes"] if node["kind"] == "Transpose")
        block = by_instance["block"]
        edges = architecture["edges"]
        self.assertTrue(any(edge["source"]["nodeId"] == patch["id"] and edge["target"]["nodeId"] == flatten["id"] for edge in edges))
        self.assertTrue(any(edge["source"]["nodeId"] == flatten["id"] and edge["target"]["nodeId"] == transpose["id"] for edge in edges))
        self.assertTrue(any(edge["source"]["nodeId"] == transpose["id"] and edge["target"]["nodeId"] == block["id"] for edge in edges))

        attention = by_instance["attention"]
        self.assertEqual(attention["children"], [])
        self.assertFalse(any(edge["source"]["nodeId"] == attention["id"] and edge["source"]["portId"].endswith(":weights") for edge in edges))
        port_names = {port["id"]: port["name"] for port in attention["ports"]}
        incoming = [edge for edge in edges if edge["target"]["nodeId"] == attention["id"]]
        self.assertEqual({port_names[edge["target"]["portId"]] for edge in incoming}, {"query", "key", "value"})
        self.assertEqual({edge["role"] for edge in incoming}, {"data"})
        self.assertEqual(len({edge["tensorId"] for edge in incoming}), 1)

        for add in [node for node in architecture["nodes"] if node["kind"] == "Add"]:
            incoming = [edge for edge in edges if edge["target"]["nodeId"] == add["id"]]
            self.assertEqual(len(incoming), 2)
            self.assertEqual({edge["role"] for edge in incoming}, {"residual", "data"})
            self.assertEqual(len({edge["tensorId"] for edge in incoming}), 2)

        output = next(node for node in architecture["nodes"] if node["kind"] == "Output")
        classifier = by_instance["classifier"]
        self.assertTrue(any(edge["source"]["nodeId"] == classifier["id"] and edge["target"]["nodeId"] == output["id"] for edge in edges))

    def test_historical_conv1d_now_has_official_atomic_contract_without_execution(self):
        architecture = analyze_project(FIXTURE, "model:UnsupportedVision")
        mixer = next(n for n in architecture['nodes'] if n['kind'] == 'Conv1d')
        self.assertEqual((mixer['category'], mixer['evidence']), ('convolution', 'contract'))
        self.assertEqual(mixer['parameters'], {'in_channels': 16, 'out_channels': 16, 'kernel_size': 3, 'padding': 1})
        self.assertEqual([(p['name'], p['direction']) for p in mixer['ports']], [('input', 'in'), ('output', 'out')])
        self.assertEqual(mixer['children'], [])
        self.assertFalse([d for d in architecture['diagnostics'] if d['level'] in ('warning', 'error')])

    def test_unsupported_holdout_is_an_explicit_opaque_boundary(self):
        architecture = analyze_project(ROOT / "fixtures" / "holdout_catalog_boundaries", EXPECTED_OPAQUE["entry"])
        opaque = [node for node in architecture["nodes"] if node["kind"] == EXPECTED_OPAQUE["kind"]]
        self.assertEqual(len(opaque), 1)
        self.assertEqual(opaque[0]["category"], EXPECTED_OPAQUE["category"])
        self.assertEqual(opaque[0]["evidence"], EXPECTED_OPAQUE["evidence"])
        self.assertEqual(opaque[0]["children"], [])
        self.assertTrue(any(EXPECTED_OPAQUE["warning_fragment"] in item["message"] for item in architecture["diagnostics"]))
        self.assertFalse(any(node["kind"] in ("Conv2d", "MultiheadAttention", "Linear") for node in architecture["nodes"]))
        output = next(node for node in architecture["nodes"] if node["kind"] == "Output")
        self.assertTrue(any(edge["source"]["nodeId"] == opaque[0]["id"] and edge["target"]["nodeId"] == output["id"] for edge in architecture["edges"]))

    def test_temporal_lstm_nested_outputs_and_shared_projection(self):
        architecture, nodes = self.family("TemporalForecaster")
        recurrent = nodes["recurrent"]
        self.assertEqual({port["name"] for port in recurrent["ports"] if port["direction"] == "out"}, {"output", "h_n", "c_n"})
        self.assertEqual(nodes["projection"]["instanceId"], nodes["projection@2"]["instanceId"])
        self.assertNotEqual(nodes["projection"]["callId"], nodes["projection@2"]["callId"])
        output_ids = {node["id"] for node in architecture["nodes"] if node["kind"] == "Output"}
        outputs = [edge for edge in architecture["edges"] if edge["target"]["nodeId"] in output_ids]
        self.assertEqual(len(outputs), 4)
        self.assertEqual(len({edge["tensorId"] for edge in outputs}), 4)

    def test_unet_skip_concat_and_independent_repeat_with_supported_upsampling(self):
        architecture, nodes = self.family("SkipSegmentation")
        repeat = nodes["repeat.refinement"]
        self.assertEqual(repeat["repeat"], {"count": 2, "sharing": "independent"})
        self.assertEqual(set(repeat["children"]), {nodes["refinement.0"]["id"], nodes["refinement.1"]["id"]})
        self.assertNotEqual(nodes["refinement.0.conv"]["instanceId"], nodes["refinement.1.conv"]["instanceId"])
        self.assertEqual(nodes["upsample"]["children"], [])
        concat_inputs = [edge for edge in architecture["edges"] if edge["target"]["nodeId"] == nodes["Concat"]["id"]]
        self.assertEqual(len({edge["tensorId"] for edge in concat_inputs}), 2)
        self.assertEqual({edge["source"]["nodeId"] for edge in concat_inputs}, {nodes["refinement.1.activation"]["id"], nodes["upsample"]["id"]})

    def test_gnn_named_attention_and_dynamic_condition_are_opaque(self):
        architecture, nodes = self.family("GraphForecast")
        self.assertEqual(nodes["message"]["children"], [])
        self.assertFalse(any(node["kind"] in ("MultiheadAttention", "ReLU", "Softmax") for node in architecture["nodes"]))
        self.assertEqual(nodes["ConditionalRegion"]["children"], [])

    def test_ssm_named_scan_and_dynamic_loop_are_opaque(self):
        architecture, nodes = self.family("DynamicStateSpace")
        self.assertEqual(nodes["scan"]["children"], [])
        self.assertEqual(nodes["DynamicLoop"]["children"], [])
        self.assertFalse(any(node["kind"] in ("LSTM", "Linear", "Repeat") for node in architecture["nodes"]))


if __name__ == "__main__":
    unittest.main()
