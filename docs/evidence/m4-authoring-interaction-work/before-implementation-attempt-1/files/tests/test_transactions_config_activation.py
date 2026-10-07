"""Independent byte and complete impact expectations for two narrow P0 rules."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archcanvas_python import analyze_project
from archcanvas_transactions import TransactionManager
from archcanvas_transactions.config_activation import inspect_configuration_origin


SOURCE = '''from torch import nn
PROBABILITY = 0.1  # keep every reader expression and this 0.1
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.first = nn.Dropout(PROBABILITY)
        self.second = nn.Dropout(p=PROBABILITY)
        self.attn = nn.MultiheadAttention(8, 2, dropout=PROBABILITY, batch_first=True)
        self.activation = nn.ReLU()
    def forward(self, x):
        a = self.first(x)
        b = self.second(a)
        y, weights = self.attn(b, b, b, need_weights=False)
        return self.activation(y)
'''


class ConfigActivationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/tmp", prefix="archcanvas-config-activation-")
        self.base = Path(self.temp.name); self.root = self.base / "source"; self.root.mkdir()
        self.path = self.root / "model.py"; self.path.write_text(SOURCE)
        self.manager = TransactionManager(self.base / "transactions")
        self.analyze()

    def tearDown(self):
        self.temp.cleanup()

    def analyze(self):
        self.arch = analyze_project(self.root, "model:Model")
        self.drop = next(node for node in self.arch["nodes"] if node["kind"] == "Dropout")
        self.activation = next(node for node in self.arch["nodes"] if node["kind"] in ("ReLU", "GELU"))

    def config(self):
        return self.manager.prepare_config(self.root, "model:Model", self.drop["id"], "p", 0.2, self.arch["sourceDigest"])

    def replace_activation(self):
        return self.manager.prepare_activation(self.root, "model:Model", self.activation["id"], "GELU", self.arch["sourceDigest"])

    def commit(self, receipt):
        self.assertEqual(receipt["status"], "ReviewReady", receipt["blockers"])
        approved = self.manager.approve(receipt["id"], receipt["reviewDigest"])
        result = self.manager.commit(receipt["id"], approved["approvalId"])
        self.assertEqual(result["status"], "Committed", result["blockers"])
        return result

    def test_config_changes_one_origin_and_all_mixed_readers(self):
        evidence = inspect_configuration_origin(self.root, "model:Model", self.drop["id"], "p", self.arch)
        self.assertTrue(evidence["supported"], evidence["blockers"])
        self.assertEqual(len(evidence["affectedNodeIds"]), 3)
        receipt = self.config()
        self.assertEqual(self.path.read_text(), SOURCE)
        self.assertEqual(receipt["intent"]["configurationName"], "PROBABILITY")
        committed = self.commit(receipt)
        self.assertEqual(self.path.read_text(), SOURCE.replace("PROBABILITY = 0.1", "PROBABILITY = 0.2"))
        probabilities = [node["parameters"]["p" if node["kind"] == "Dropout" else "dropout"] for node in committed["committedArchitecture"]["nodes"] if node["kind"] in ("Dropout", "MultiheadAttention")]
        self.assertEqual(probabilities, [0.2, 0.2, 0.2])
        self.assertEqual(committed["committedArchitecture"]["edges"], self.arch["edges"])

    def test_config_derived_unregistered_shadowed_or_unused_reader_refused(self):
        changed_sources = [
            SOURCE.replace("nn.Dropout(p=PROBABILITY)", "nn.Dropout(p=PROBABILITY * 2)"),
            SOURCE.replace("class Model", "OTHER = PROBABILITY\nclass Model"),
            SOURCE.replace("self.first =", "PROBABILITY = 0.1\n        self.first ="),
            SOURCE + '\nclass Hidden(nn.Module):\n    def __init__(self): self.d = nn.Dropout(PROBABILITY)\n    def forward(self,x): return self.d(x)\n',
        ]
        for source in changed_sources:
            with self.subTest(source=source[-90:]):
                self.path.write_text(source); self.analyze()
                before = self.path.read_bytes()
                receipt = self.config()
                self.assertEqual(receipt["status"], "Failed")
                self.assertEqual(self.path.read_bytes(), before)

    def test_activation_only_changes_constructor_token_and_kind(self):
        receipt = self.replace_activation()
        self.assertEqual(self.path.read_text(), SOURCE)
        self.assertEqual(receipt["transform"]["profile"], "parameter-static")
        after = self.commit(receipt)["committedArchitecture"]
        self.assertEqual(self.path.read_text(), SOURCE.replace("nn.ReLU()", "nn.GELU()"))
        self.assertEqual(after["edges"], self.arch["edges"])
        self.assertEqual([node["id"] for node in after["nodes"]], [node["id"] for node in self.arch["nodes"]])
        changed = next(node for node in after["nodes"] if node["id"] == self.activation["id"])
        self.assertEqual(changed["kind"], "GELU")
        self.assertEqual(changed["ports"], self.activation["ports"])

    def test_activation_arguments_and_requested_unknown_kind_refused(self):
        self.path.write_text(SOURCE.replace("nn.ReLU()", "nn.ReLU(inplace=False)")); self.analyze()
        receipt = self.replace_activation()
        self.assertEqual(receipt["status"], "Failed")
        self.assertIn("no-argument", receipt["blockers"][0])
        receipt = self.manager.prepare_activation(self.root, "model:Model", self.activation["id"], "SiLU", self.arch["sourceDigest"])
        self.assertEqual(receipt["status"], "Failed")

    def test_activation_wrong_lowering_is_rejected_by_independent_kind_oracle(self):
        def wrong(raw, origin, before_value, after_value, kind):
            return raw
        with patch("archcanvas_transactions.service.rewrite_registered_atom", wrong):
            receipt = self.replace_activation()
        self.assertEqual(receipt["status"], "Failed")
        self.assertIn("ExpectedDelta", receipt["blockers"][0])
        self.assertEqual(self.path.read_text(), SOURCE)

    def test_configuration_wrong_probability_lowering_is_not_expected_oracle(self):
        def wrong(raw, origin, before_value, after_value, kind):
            return raw.replace(b"PROBABILITY = 0.1", b"PROBABILITY = 0.3")
        with patch("archcanvas_transactions.service.rewrite_registered_atom", wrong):
            receipt = self.config()
        self.assertEqual(receipt["status"], "Failed")
        self.assertIn("ExpectedDelta", receipt["blockers"][0])

    def test_configuration_and_activation_use_exact_approval_and_stale_guard(self):
        one, two = self.config(), self.replace_activation()
        a = self.manager.approve(one["id"], one["reviewDigest"])
        b = self.manager.approve(two["id"], two["reviewDigest"])
        self.assertEqual(self.manager.commit(one["id"], a["approvalId"])["status"], "Committed")
        self.assertEqual(self.manager.commit(two["id"], b["approvalId"])["status"], "Stale")
        self.assertIn("nn.ReLU()", self.path.read_text())


if __name__ == "__main__":
    unittest.main()
