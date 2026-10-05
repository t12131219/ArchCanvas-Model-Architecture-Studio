"""Handwritten return-slot contracts and unknown dictionary counterexamples."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from archcanvas_python import AnalysisError, analyze_source, validate_output_paths
from archcanvas_cli.server import DocumentStore


def analyze(return_expression, *, extra="", arguments="x"):
    source = f'''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.identity = nn.Identity()
    def forward(self, {arguments}):
        y = self.identity(x)
{extra}        return {return_expression}
'''
    return analyze_source(source, "Model")


def outputs(architecture):
    return [node for node in architecture["nodes"] if node["kind"] == "Output"]


class OutputPathTests(unittest.TestCase):
    def test_nested_duplicate_producer_returns_have_distinct_slots_and_identities(self):
        architecture = analyze('{"main": (y, {"copy": y}), 0: [x, None, y]}')
        expected = [
            [{"kind": "key", "key": "main"}, {"kind": "index", "index": 0}],
            [{"kind": "key", "key": "main"}, {"kind": "index", "index": 1}, {"kind": "key", "key": "copy"}],
            [{"kind": "key", "key": 0}, {"kind": "index", "index": 0}],
            [{"kind": "key", "key": 0}, {"kind": "index", "index": 2}],
        ]
        returned = outputs(architecture)
        self.assertEqual([node["outputPath"] for node in returned], expected)
        self.assertEqual(len({node["id"] for node in returned}), 4)
        edges = {edge["target"]["nodeId"]: edge for edge in architecture["edges"] if edge["target"]["nodeId"] in {node["id"] for node in returned}}
        self.assertEqual([edges[node["id"]]["source"]["nodeId"] for node in returned], [
            "call:instance:model.Model.identity", "call:instance:model.Model.identity",
            "input:model.Model:x", "call:instance:model.Model.identity",
        ])
        self.assertEqual(len({edges[returned[i]["id"]]["tensorId"] for i in (0, 1, 3)}), 1)
        self.assertEqual(json.loads(json.dumps(architecture))["nodes"], architecture["nodes"])

    def test_tuple_none_gaps_and_json_key_types_are_preserved(self):
        architecture = analyze('{None: (None, y), "0": x, 2: y, False: y, 1.5: x}')
        self.assertEqual([node["outputPath"] for node in outputs(architecture)], [
            [{"kind": "key", "key": None}, {"kind": "index", "index": 1}],
            [{"kind": "key", "key": "0"}],
            [{"kind": "key", "key": 2}],
            [{"kind": "key", "key": False}],
            [{"kind": "key", "key": 1.5}],
        ])

    def test_literal_local_key_and_duplicate_dictionary_keys_follow_source_semantics(self):
        architecture = analyze('{key: y, "same": x, "same": y}', extra='        key = "forecast"\n')
        self.assertEqual([node["outputPath"] for node in outputs(architecture)], [
            [{"kind": "key", "key": "forecast"}], [{"kind": "key", "key": "same"}],
        ])
        self.assertTrue(all(edge["source"]["nodeId"] == "call:instance:model.Model.identity" for edge in architecture["edges"] if edge["target"]["nodeId"].startswith("output:")))

    def test_whole_tensor_return_has_root_slot(self):
        self.assertEqual(outputs(analyze('y'))[0]["outputPath"], [])

    def test_unknown_name_key_keeps_all_dependencies_without_claiming_inner_slots(self):
        architecture = analyze('{label: y, "known": x}', arguments='x, label')
        boundary = next(node for node in architecture["nodes"] if node["kind"] == "OpaqueDictionary")
        self.assertEqual((boundary["category"], boundary["evidence"]), ("opaque", "opaque"))
        self.assertEqual([node["outputPath"] for node in outputs(architecture)], [[]])
        inputs = {edge["source"]["nodeId"] for edge in architecture["edges"] if edge["target"]["nodeId"] == boundary["id"]}
        self.assertEqual(inputs, {"input:model.Model:x", "input:model.Model:label", "call:instance:model.Model.identity"})
        self.assertTrue(any('no claimed key slots' in item["message"] for item in architecture["diagnostics"]))

    def test_dynamic_attribute_key_is_not_misrepresented_as_none_key(self):
        architecture = analyze('{x.shape[0]: y}')
        self.assertEqual([node["outputPath"] for node in outputs(architecture)], [[]])
        self.assertTrue(any(node["kind"] == "OpaqueDictionary" for node in architecture["nodes"]))

    def test_dictionary_unpack_and_nonportable_keys_stay_opaque(self):
        for expression, arguments in [('{"known": y, **extras}', 'x, extras'),
                                      ('{("tuple", 0): y}', 'x'), ('{9007199254740992: y}', 'x'),
                                      ('{1e100: y}', 'x')]:
            with self.subTest(expression=expression):
                architecture = analyze(expression, arguments=arguments)
                self.assertTrue(any(node["kind"] == "OpaqueDictionary" and node["evidence"] == "opaque" for node in architecture["nodes"]))
                self.assertEqual([node["outputPath"] for node in outputs(architecture)], [[]])

    def test_output_key_change_alters_semantic_digest_and_not_producer_tensor(self):
        before, after = analyze('{"left": y}'), analyze('{"right": y}')
        self.assertNotEqual(before["irDigest"], after["irDigest"])
        self.assertEqual([edge for edge in before["edges"] if edge["target"]["nodeId"].startswith("output:")],
                         [edge for edge in after["edges"] if edge["target"]["nodeId"].startswith("output:")])

    def test_python_output_path_validator_rejects_malformed_or_wrong_node_slots(self):
        node = outputs(analyze('y'))[0]
        for invalid in (None, {}, [{"kind": "index", "index": -1}], [{"kind": "index", "index": True}],
                        [{"kind": "index", "index": 9007199254740992}], [{"kind": "key", "key": []}],
                        [{"kind": "key", "key": float('nan')}], [{"kind": "key"}],
                        [{"kind": "index", "index": 0, "key": "x"}], [{"kind": "unknown"}]):
            with self.subTest(invalid=invalid):
                wrong = {**node, "outputPath": invalid}
                with self.assertRaises(AnalysisError):
                    validate_output_paths([wrong])
        with self.assertRaises(AnalysisError):
            validate_output_paths([{**node, "kind": "Input"}])

    def test_document_save_rejects_invalid_slot_evidence_before_persistence(self):
        architecture = analyze('y')
        canvas = {"schemaVersion": 1, "id": "canvas-output-test", "title": "Output", "revision": 0,
                  "sourceBindingDigest": architecture["sourceDigest"], "architecture": architecture,
                  "displayAliases": {}, "nodeStyleOverrides": {}, "edgeStyleOverrides": {}, "layout": {},
                  "layoutByFrontier": {}, "pageSpec": {}, "legendItems": [], "annotations": [], "expandedIds": [], "pinnedObjects": []}
        with tempfile.TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            store.put(canvas["id"], canvas, 0)
            tampered = copy.deepcopy(canvas)
            outputs(tampered["architecture"])[0]["outputPath"] = [{"kind": "index", "index": -1}]
            with self.assertRaises(AnalysisError):
                store.put(canvas["id"], tampered, 1)
            self.assertEqual(store.get(canvas["id"])["document"], canvas)


if __name__ == "__main__":
    unittest.main()
