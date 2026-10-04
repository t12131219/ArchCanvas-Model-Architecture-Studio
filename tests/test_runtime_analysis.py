"""Independent expectations taken from fixture source and public call contracts."""

import json
import tempfile
import unittest
from pathlib import Path

from archcanvas_python import AnalysisError, analyze_project, analyze_source
from archcanvas_cli.server import capabilities

ROOT = Path(__file__).resolve().parents[1]


class StaticAnalysisTests(unittest.TestCase):
    def test_transformer_gold_ports_residuals_and_independent_repeat(self):
        architecture = analyze_project(ROOT / "fixtures/transformer", "model:Transformer")
        self.assertEqual([source["path"] for source in architecture["sources"]], ["blocks.py", "model.py"])
        self.assertFalse([node for node in architecture["nodes"] if node["evidence"] == "opaque"])
        repeats = [node for node in architecture["nodes"] if node.get("repeat")]
        self.assertEqual(len(repeats), 1)
        self.assertEqual(repeats[0]["repeat"], {"count": 2, "sharing": "independent"})
        cross = next(node for node in architecture["nodes"] if node["label"] == "cross attention")
        self.assertEqual(cross["kind"], "MultiheadAttention")
        self.assertEqual(cross["evidence"], "contract")
        self.assertEqual(cross["children"], [])  # No fabricated library QKV internals.
        by_port = {port["id"]: port["name"] for port in cross["ports"]}
        incoming = {by_port[edge["target"]["portId"]]: edge for edge in architecture["edges"] if edge["target"]["nodeId"] == cross["id"]}
        self.assertEqual(set(incoming), {"query", "key", "value", "attn_mask"})
        self.assertEqual(incoming["key"]["tensorId"], incoming["value"]["tensorId"])
        self.assertNotEqual(incoming["query"]["tensorId"], incoming["key"]["tensorId"])
        self.assertEqual(incoming["key"]["role"], "memory")
        self.assertEqual(incoming["attn_mask"]["role"], "mask")
        self_attention = next(node for node in architecture["nodes"] if node["kind"] == "MultiheadAttention" and node["id"] != cross["id"])
        self.assertEqual({edge["role"] for edge in architecture["edges"] if edge["target"]["nodeId"] == self_attention["id"] and edge["target"]["portId"].endswith((":query", ":key", ":value"))}, {"data"})
        # Seven explicit additions exist: two in each encoder plus three decoder.
        adds = [node for node in architecture["nodes"] if node["kind"] == "Add"]
        self.assertEqual(len(adds), 7)
        for node in adds:
            bindings = [edge for edge in architecture["edges"] if edge["target"]["nodeId"] == node["id"]]
            self.assertEqual(len(bindings), 2)
            self.assertEqual(len({edge["tensorId"] for edge in bindings}), 2)
        self.assertNotIn("Softmax", [node["kind"] for node in architecture["nodes"]])

    def test_mlp_and_cnn_source_gold(self):
        mlp = analyze_project(ROOT / "fixtures/mlp", "model:MLP")
        self.assertEqual([node["kind"] for node in mlp["nodes"] if node["category"] != "container" and node["kind"] not in ("Input", "Output")], ["Linear", "GELU", "Dropout", "Linear"])
        cnn = analyze_project(ROOT / "fixtures/residual_cnn", "model:ResidualCNN")
        self.assertEqual(sum(node["kind"] == "Conv2d" for node in cnn["nodes"]), 5)
        self.assertEqual(sum(node["kind"] == "Add" for node in cnn["nodes"]), 2)
        self.assertEqual(sum(node["kind"] == "Output" for node in cnn["nodes"]), 1)

    def test_top_level_decorators_and_initializers_never_execute(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "executed"
            source = f'''from torch import nn
open({str(sentinel)!r}, "w").write("top level")
def danger(cls):
    open({str(sentinel)!r}, "w").write("decorator")
    return cls
@danger
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        open({str(sentinel)!r}, "w").write("init")
        self.linear = nn.Linear(4, 2)
    def forward(self, x):
        open({str(sentinel)!r}, "w").write("forward")
        return self.linear(x)
'''
            architecture = analyze_source(source, "Model")
            self.assertFalse(sentinel.exists())
            self.assertIn("Linear", [node["kind"] for node in architecture["nodes"]])
            self.assertTrue(any(node["category"] == "opaque" for node in architecture["nodes"]))

    def test_attention_name_cannot_supply_framework_semantics(self):
        source = '''from torch import nn
class MagicalAttention:
    pass
class Model(nn.Module):
    def __init__(self):
        self.attention = MagicalAttention()
    def forward(self, x):
        return self.attention(x)
'''
        architecture = analyze_source(source, "Model")
        unknown = next(node for node in architecture["nodes"] if node["kind"] == "MagicalAttention")
        self.assertEqual((unknown["category"], unknown["evidence"], unknown["children"]), ("opaque", "opaque", []))
        self.assertFalse(any(node["kind"] == "MultiheadAttention" for node in architecture["nodes"]))

    def test_positional_attention_mask_and_tuple_outputs(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        self.attn = nn.MultiheadAttention(8, 2)
    def forward(self, q, memory, mask):
        y, weights = self.attn(q, memory, memory, mask)
        return y, weights
'''
        architecture = analyze_source(source, "Model")
        attn = next(node for node in architecture["nodes"] if node["kind"] == "MultiheadAttention")
        self.assertIn("key_padding_mask", [port["name"] for port in attn["ports"]])
        self.assertEqual(sum(node["kind"] == "Output" for node in architecture["nodes"]), 2)
        outgoing = [edge for edge in architecture["edges"] if edge["source"]["nodeId"] == attn["id"]]
        self.assertEqual(len({edge["tensorId"] for edge in outgoing}), 2)

    def test_shared_instance_has_distinct_calls(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        self.shared = nn.Linear(8, 8)
        self.alias = self.shared
        self.layers = nn.ModuleList([self.shared] * 2)
    def forward(self, x):
        a = self.shared(x)
        b = self.alias(x)
        for layer in self.layers:
            a = layer(a)
        return a + b
'''
        architecture = analyze_source(source, "Model")
        calls = [node for node in architecture["nodes"] if node["kind"] == "Linear"]
        self.assertEqual(len(calls), 4)
        self.assertEqual(len({node["id"] for node in calls}), 4)
        self.assertEqual(len({node["instanceId"] for node in calls}), 1)
        repeat = next(node for node in architecture["nodes"] if node.get("repeat"))
        self.assertEqual(repeat["repeat"], {"count": 2, "sharing": "shared"})

    def test_attention_disabled_weights_slot_is_not_a_tensor(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        self.attn = nn.MultiheadAttention(8, 2)
    def forward(self, x):
        y, weights = self.attn(x, x, x, need_weights=False)
        return y, weights
'''
        architecture = analyze_source(source, "Model")
        attn = next(node for node in architecture["nodes"] if node["kind"] == "MultiheadAttention")
        self.assertIn("weights", [port["name"] for port in attn["ports"]])
        self.assertEqual(sum(node["kind"] == "Output" for node in architecture["nodes"]), 1)
        self.assertFalse(any(edge["source"]["portId"].endswith(":weights") for edge in architecture["edges"]))

    def test_inherited_forward_is_opaque_but_retains_input(self):
        source = '''from torch import nn
class Base(nn.Module):
    def forward(self, x):
        return x
class Child(Base):
    pass
class Model(nn.Module):
    def __init__(self):
        self.child = Child()
    def forward(self, x):
        return self.child(x)
'''
        architecture = analyze_source(source, "Model")
        child = next(node for node in architecture["nodes"] if node["label"] == "child")
        self.assertEqual(child["evidence"], "opaque")
        self.assertTrue(any(port["direction"] == "in" for port in child["ports"]))
        self.assertTrue(any(edge["target"]["nodeId"] == child["id"] for edge in architecture["edges"]))

    def test_dynamic_control_is_explicit_and_never_merged_as_proven(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        self.linear = nn.Linear(4, 4)
    def forward(self, x):
        if x.sum() > 0:
            x = self.linear(x)
        return x
'''
        architecture = analyze_source(source, "Model")
        boundary = next(node for node in architecture["nodes"] if node["kind"] == "ConditionalRegion")
        output = next(node for node in architecture["nodes"] if node["kind"] == "Output")
        self.assertEqual(boundary["evidence"], "opaque")
        self.assertTrue(any(edge["source"]["nodeId"] == boundary["id"] and edge["target"]["nodeId"] == output["id"] for edge in architecture["edges"]))

    def test_comment_changes_source_digest_but_not_ir_or_ids(self):
        source = (ROOT / "fixtures/mlp/model.py").read_text()
        before = analyze_source(source, "MLP")
        after = analyze_source("# additional explanation\n" + source, "MLP")
        self.assertNotEqual(before["sourceDigest"], after["sourceDigest"])
        self.assertEqual(before["irDigest"], after["irDigest"])
        self.assertEqual([node["id"] for node in before["nodes"]], [node["id"] for node in after["nodes"]])

    def test_invalid_entry_traversal_and_symlink_are_rejected(self):
        with self.assertRaises(AnalysisError):
            analyze_source("", "Model", "../model.py")
        with self.assertRaises(AnalysisError):
            analyze_project(ROOT, "../model:Model")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            outside = Path(directory) / "outside.py"
            outside.write_text("from torch import nn\nclass Model(nn.Module):\n def forward(self,x): return x\n")
            (root / "model.py").symlink_to(outside)
            with self.assertRaises(AnalysisError):
                analyze_project(root, "model:Model")

    def test_local_torch_module_cannot_claim_pytorch_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "torch.py").write_text("class nn:\n class Module: pass\n class Linear: pass\n")
            (root / "model.py").write_text("from torch import nn\nclass Model(nn.Module):\n def forward(self,x): return x\n")
            with self.assertRaisesRegex(AnalysisError, "not statically proven"):
                analyze_project(root, "model:Model")

    def test_local_alias_shadowing_does_not_receive_framework_semantics(self):
        source = '''from torch import nn
from torch.nn import functional as F
class Model(nn.Module):
    def __init__(self):
        nn = plugin_factory()
        self.fake = nn.Linear(8, 8)
    def forward(self, x, F):
        return F.relu(self.fake(x))
'''
        architecture = analyze_source(source, "Model")
        fake = next(node for node in architecture["nodes"] if node["label"] == "fake")
        self.assertEqual(fake["evidence"], "opaque")
        self.assertNotIn("ReLU", [node["kind"] for node in architecture["nodes"]])

    def test_provenance_and_capabilities_are_actual(self):
        receipt = capabilities()
        self.assertEqual(Path(receipt["packageProvenance"]["projectRoot"]), ROOT)
        for name, path in receipt["packageProvenance"]["modules"].items():
            self.assertTrue(Path(path).is_relative_to(ROOT / "src"))
            self.assertTrue(Path(path).is_file())
        self.assertTrue(receipt["packageProvenance"]["independent"])
        self.assertTrue(receipt["semanticWriteback"])
        self.assertEqual(receipt["supportedIntents"], ["set_dropout_probability", "rebind_input"])
        self.assertEqual(receipt["semanticScope"]["origins"], ["explicit-float-literal"])
        self.assertEqual(receipt["semanticScope"]["httpCommit"], "managed-workspace-copy-only")
        self.assertFalse(receipt["runtimeObservation"])
        json.dumps(receipt)


if __name__ == "__main__":
    unittest.main()
