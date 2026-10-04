"""Source-led evidence tests for bounded, conditional symbolic compatibility."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archcanvas_python import analyze_project
from archcanvas_python.rebind import inspect_rebind


SOURCE = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.first = nn.Identity()
        self.activation = nn.ReLU()
        self.branch = nn.GELU()
        self.foreign = nn.Identity()
        self.output = nn.Dropout(0.1)
        self.later = nn.Identity()
    def forward(self, features, memory):
        a = self.first(features)
        b = self.activation(a)
        branch = self.branch(a)
        foreign = self.foreign(memory)
        out = self.output(b)  # target token b, keep comment
        late = self.later(out)
        return late
'''


class RebindAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="archcanvas-rebind-evidence-", dir="/tmp")
        self.root = Path(self.temporary.name)
        self.path = self.root / "model.py"
        self.path.write_bytes(SOURCE.encode())

    def tearDown(self):
        self.temporary.cleanup()

    def inspect(self, source=None, target_suffix=".output"):
        if source is not None:
            self.path.write_bytes(source.encode())
        architecture = analyze_project(self.root, "model:Model")
        target = next(node for node in architecture["nodes"] if node.get("instanceId", "").endswith(target_suffix))
        return inspect_rebind(self.root, "model:Model", target["id"], architecture), architecture, target

    def test_candidates_match_names_bindings_domination_and_conditional_same_origin(self):
        options, architecture, target = self.inspect()
        self.assertTrue(options["supported"], options["blockers"])
        self.assertEqual(options["status"], "supported")
        self.assertEqual([candidate["variable"] for candidate in options["candidates"]], ["features", "a", "b", "branch"])
        self.assertEqual([candidate["variable"] for candidate in options["excludedCandidates"]], ["memory", "foreign"])
        self.assertNotIn("out", [candidate["variable"] for candidate in options["candidates"]])
        self.assertNotIn("late", [candidate["variable"] for candidate in options["candidates"]])
        incoming = next(edge for edge in architecture["edges"] if edge["target"]["nodeId"] == target["id"])
        self.assertEqual(options["target"]["portId"], incoming["target"]["portId"])
        self.assertEqual(options["target"]["currentBinding"], incoming["source"] | {"tensorId": incoming["tensorId"]})
        base_ids = {candidate["contract"]["baseTensorId"] for candidate in options["candidates"]}
        self.assertEqual(len(base_ids), 1)
        for candidate in options["candidates"]:
            contract = candidate["contract"]
            self.assertEqual(contract["shape"]["kind"], "symbol")
            self.assertEqual(contract["dtype"]["kind"], "symbol")
            self.assertFalse(contract["runtimeVerified"])
            self.assertTrue(contract["conditional"])
            self.assertIn("concrete dimensions and dtype are unknown", contract["condition"])
        branch = next(candidate for candidate in options["candidates"] if candidate["variable"] == "branch")
        producer = next(node for node in architecture["nodes"] if node.get("instanceId", "").endswith(".branch"))
        self.assertEqual(branch["binding"]["nodeId"], producer["id"])
        self.assertFalse(any(edge["source"]["nodeId"] == producer["id"] for edge in architecture["edges"]))
        self.assertEqual(branch["binding"]["tensorId"], f"tensor:{producer['id']}:output")
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())

    def test_source_slot_is_exact_utf8_byte_anchor_not_label_or_line_only(self):
        source = SOURCE.replace("b = self.activation(a)", "中间 = self.activation(a)").replace("self.output(b)", "self.output(中间)")
        options, architecture, target = self.inspect(source)
        self.assertTrue(options["supported"], options["blockers"])
        slot = options["target"]["slot"]
        line = source.splitlines(keepends=True)[slot["line"] - 1].encode()
        self.assertEqual(line[slot["column"]:slot["endColumn"]], "中间".encode())
        self.assertEqual(slot["variable"], "中间")
        self.assertEqual(slot["expression"], "中间")
        self.assertEqual(slot["fileDigest"], architecture["sources"][0]["digest"])
        self.assertEqual(options["target"]["nodeId"], target["id"])

    def test_comments_do_not_change_graph_ids_or_symbolic_identity(self):
        before, old_architecture, _ = self.inspect()
        after, new_architecture, _ = self.inspect("# explaining this source\n" + SOURCE)
        self.assertTrue(after["supported"])
        self.assertNotEqual(before["sourceDigest"], after["sourceDigest"])
        self.assertEqual(before["irDigest"], after["irDigest"])
        self.assertEqual([candidate["binding"] for candidate in before["candidates"]], [candidate["binding"] for candidate in after["candidates"]])
        self.assertEqual([node["id"] for node in old_architecture["nodes"]], [node["id"] for node in new_architecture["nodes"]])

    def test_symbolic_type_compatibility_is_never_assigned_to_different_input(self):
        options, _, _ = self.inspect()
        self.assertTrue(options["supported"])
        self.assertTrue(all(candidate["variable"] not in ("memory", "foreign") for candidate in options["candidates"]))
        self.assertTrue(all("different forward-input origin" in candidate["reason"] for candidate in options["excludedCandidates"]))

    def test_inplace_unknown_control_nested_alias_and_reassignment_scopes_are_rejected(self):
        examples = {
            "inplace_relu": SOURCE.replace("nn.ReLU()", "nn.ReLU(inplace=True)"),
            "inplace_dropout": SOURCE.replace("nn.Dropout(0.1)", "nn.Dropout(0.1, True)"),
            "unknown_inplace": SOURCE.replace("def __init__(self):", "def __init__(self, inplace):").replace("nn.ReLU()", "nn.ReLU(inplace=inplace)"),
            "reassignment": SOURCE.replace("out = self.output(b)", "a = self.first(a)\n        out = self.output(b)"),
            "input_reassignment": SOURCE.replace("a = self.first(features)", "features = self.first(features)\n        a = self.first(features)"),
            "dynamic": SOURCE.replace("b = self.activation(a)", "if features.sum() > 0:\n            b = self.activation(a)\n        else:\n            b = a"),
            "loop": SOURCE.replace("b = self.activation(a)", "for item in range(2):\n            b = self.activation(a)"),
            "mutation": SOURCE.replace("b = self.activation(a)", "a.add_(1)\n        b = self.activation(a)"),
            "unknown_call": SOURCE.replace("b = self.activation(a)", "plugin(a)\n        b = self.activation(a)"),
            "nested_call": SOURCE.replace("out = self.output(b)", "out = self.output(self.activation(a))"),
            "keyword_input": SOURCE.replace("out = self.output(b)", "out = self.output(input=b)"),
            "subscript": SOURCE.replace("out = self.output(b)", "out = self.output(b[0])"),
            "arithmetic": SOURCE.replace("out = self.output(b)", "out = self.output(b + a)"),
            "alias": SOURCE.replace("branch = self.branch(a)", "branch = a"),
            "module_alias": SOURCE.replace("self.branch = nn.GELU()", "self.branch = self.activation"),
            "unknown_type": SOURCE.replace("self.branch = nn.GELU()", "self.branch = nn.Linear(8, 8)"),
            "global_scope": SOURCE.replace("out = self.output(b)", "out = self.output(global_tensor)"),
            "signature": SOURCE.replace("def forward(self, features, memory):", "def forward(receiver, features, memory):"),
            "self_store": SOURCE.replace("b = self.activation(a)", "self = self.first(a)\n        b = self.activation(a)"),
            "descriptor": SOURCE.replace("class Model(nn.Module):", "class Model(nn.Module):\n    __call__ = plugin"),
            "constructor_factory": SOURCE.replace("self.branch = nn.GELU()", "self.branch = plugin_factory()"),
            "initializer_control": SOURCE.replace("self.branch = nn.GELU()", "if True:\n            self.branch = nn.GELU()"),
        }
        for label, source in examples.items():
            with self.subTest(label=label):
                options, _, _ = self.inspect(source)
                self.assertFalse(options["supported"], options)
                self.assertEqual(options["status"], "unsupported")
                self.assertTrue(options["blockers"])
                self.assertEqual(options["candidates"], [])

    def test_ambiguous_same_line_call_anchor_is_not_resolved_by_label(self):
        source = SOURCE.replace("a = self.first(features)\n        b = self.activation(a)", "a = self.first(features); duplicate = self.first(features)\n        b = self.activation(a)")
        options, _, _ = self.inspect(source)
        self.assertFalse(options["supported"])
        self.assertIn("ambiguously", options["blockers"][0])

    def test_client_modified_facts_and_stale_corpus_cannot_supply_evidence(self):
        options, architecture, target = self.inspect()
        forged = copy.deepcopy(architecture)
        forged["edges"][0]["tensorId"] = "forged-compatible-tensor"
        result = inspect_rebind(self.root, "model:Model", target["id"], forged)
        self.assertFalse(result["supported"])
        self.assertIn("Frozen architecture", result["blockers"][0])
        self.path.write_text("# later source revision\n" + SOURCE)
        result = inspect_rebind(self.root, "model:Model", target["id"], architecture)
        self.assertFalse(result["supported"])

    def test_no_import_initializer_decorator_or_forward_execution(self):
        sentinel = self.root / "executed"
        source = f'open({str(sentinel)!r}, "w").write("not allowed")\n' + SOURCE
        options, _, _ = self.inspect(source)
        self.assertFalse(options["supported"])
        self.assertFalse(sentinel.exists())
        source = SOURCE.replace("self.branch = nn.GELU()", f'open({str(sentinel)!r}, "w").write("not allowed")\n        self.branch = nn.GELU()')
        options, _, _ = self.inspect(source)
        self.assertFalse(options["supported"])
        self.assertFalse(sentinel.exists())

    def test_import_time_monkeypatches_method_replacement_and_unknown_imports_block_contract(self):
        for change in ("nn.ReLU = nn.Identity", "setattr(nn, 'ReLU', nn.Identity)", "patch_framework(nn)", "import unknown_plugin"):
            with self.subTest(change=change):
                options, _, _ = self.inspect(SOURCE.replace("from torch import nn", "from torch import nn\n" + change))
                self.assertFalse(options["supported"], options)
                self.assertTrue(options["blockers"])
        for replacement in ("    forward = replace_forward\n", "    __init__ = replace_init\n"):
            with self.subTest(replacement=replacement):
                options, _, _ = self.inspect(SOURCE.replace("    def forward(self, features, memory):", replacement + "    def forward(self, features, memory):"))
                self.assertFalse(options["supported"], options)

    def test_source_change_during_evidence_freezing_cannot_bind_mixed_versions(self):
        architecture = analyze_project(self.root, "model:Model")
        target = next(node for node in architecture["nodes"] if node.get("instanceId", "").endswith(".output"))
        def changing_analysis(root, entry):
            frozen = analyze_project(root, entry)
            self.path.write_text(SOURCE.replace("nn.Dropout(0.1)", "nn.Dropout(0.2)"))
            return frozen
        with patch("archcanvas_python.rebind.analyze_project", changing_analysis):
            result = inspect_rebind(self.root, "model:Model", target["id"])
        self.assertFalse(result["supported"])
        self.assertIn("source corpus changed", result["blockers"][0])

    def test_local_class_creation_hooks_cannot_certify_external_framework_symbols(self):
        hook = '''class Hook:
    def __init_subclass__(cls):
        nn.ReLU = nn.Identity
class Trigger(Hook):
    def placeholder(self):
        pass
'''
        source = SOURCE.replace("class Model(nn.Module):", hook + "class Model(nn.Module):")
        options, architecture, target = self.inspect(source)
        self.assertFalse(options["supported"], options)
        self.assertIn("inheritance hooks", options["blockers"][0])
        self.assertEqual(self.path.read_text(), source)
        # The transaction layer must consume the unsupported source evidence;
        # a plausible original graph must not bypass the import-effects guard.
        from archcanvas_transactions import TransactionManager
        producer = next(node for node in architecture["nodes"] if node.get("instanceId", "").endswith(".first"))
        target_port = next(port for port in target["ports"] if port["direction"] == "in")
        producer_port = next(port for port in producer["ports"] if port["direction"] == "out")
        manager = TransactionManager(self.root / "transactions")
        receipt = manager.prepare_rebind(self.root, "model:Model", target["id"], target_port["id"], producer["id"], producer_port["id"], architecture["sourceDigest"])
        self.assertEqual(receipt["status"], "Failed", receipt)
        self.assertTrue(any("inheritance hooks" in blocker for blocker in receipt["blockers"]))
        self.assertEqual(self.path.read_text(), source)


if __name__ == "__main__":
    unittest.main()
