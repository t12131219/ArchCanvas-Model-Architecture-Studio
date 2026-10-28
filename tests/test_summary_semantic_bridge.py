"""Independent holdouts for the migrated Summary static semantic boundary."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import archcanvas_preview
from archcanvas_summary_semantic.schema import validate_ir

SOURCE = """import torch
from torch import nn
class Model(nn.Module):
    def __init__(self, width=4):
        super().__init__()
        self.left = nn.Linear(width, width)
        self.right = nn.ReLU()
    def forward(self, x):
        return x + self.right(self.left(x))
"""


class SummarySemanticBridgeTests(unittest.TestCase):
    def analyze(self, files=None, entry="Model", config=None):
        return archcanvas_preview.analyze(files or {"model.py": SOURCE}, entry, config, semantic_mode="summary")

    def test_native_schema_contracts_identity_and_exact_utf8_evidence(self):
        source = SOURCE.replace("x", "特征")
        bundle = self.analyze({"model.py": source})
        semantic = bundle["ir"]["semantic_ir"]
        self.assertEqual(semantic["schema"], "archcanvas-source-semantic/2")
        self.assertTrue(validate_ir(semantic)["ok"], validate_ir(semantic))
        self.assertFalse(semantic["runtime"]["model_executed"])
        self.assertFalse(semantic["coverage"]["complete"])
        self.assertTrue(semantic["semantic_contracts"], "the actual residual contract must survive relocation")
        self.assertEqual(len(semantic["nodes"]), len(bundle["ir"]["nodes"]))
        self.assertEqual(len(semantic["edges"]), len(bundle["ir"]["edges"]))
        for span in bundle["evidence"].values():
            self.assertFalse(Path(span["file"]).is_absolute())
            lines = source.split("\n")[span["line"] - 1:span["endLine"]]
            chunks = [line.encode("utf-8") for line in lines]
            chunks[-1] = chunks[-1][:span["endColumn"]]
            chunks[0] = chunks[0][span["column"]:]
            self.assertEqual(span["expression"], b"\n".join(chunks).decode("utf-8"))
        # Native spans retain their own schema; no camel-case rewrite inside v2.
        self.assertTrue(all("end_line" in span for node in semantic["nodes"] for span in node["source"]))

    def test_same_corpus_constructor_and_entry_have_stable_identity(self):
        before = self.analyze(config={"width": 8})
        again = self.analyze(config={"width": 8})
        self.assertEqual(before, again, "temporary directories must not leak into facts, certificates or IDs")
        self.assertNotIn("archcanvas-summary-semantic-", json.dumps(before))
        self.assertEqual(before["config"], {"width": 8})
        self.assertNotEqual(before["id"], self.analyze(config={"width": 16})["id"])

    def test_multifile_entry_chooses_qualified_file_not_first_sorted_source(self):
        files = {"a_helper.py": "from torch import nn\nclass Helper(nn.Module):\n def forward(self,x): return x.relu()\n",
                 "models/__init__.py": "", "models/net.py": SOURCE}
        bundle = self.analyze(files, "models.net:Model")
        self.assertEqual(bundle["entry"], "models.net:Model")
        self.assertEqual(bundle["ir"]["semantic_ir"]["entry"]["file"], "models/net.py")
        self.assertEqual({e["file"] for e in bundle["evidence"].values()}, {"models/net.py"})
        self.assertEqual(self.analyze({"net.py": SOURCE}, None)["entry"], "net:Model")
        with self.assertRaises(archcanvas_preview.AdapterError):
            self.analyze({"a.py": SOURCE, "b.py": SOURCE}, "Model")

    def test_crossfile_helper_is_lowered_without_executing_imports(self):
        files = {"helpers.py": "def apply(x):\n return x.sigmoid()\n",
                 "model.py": "from torch import nn\nfrom helpers import apply\nclass Model(nn.Module):\n def forward(self,x): return apply(x)\n"}
        bundle = self.analyze(files, "model:Model")
        self.assertEqual({e["file"] for e in bundle["evidence"].values()}, {"helpers.py", "model.py"})
        self.assertTrue(any(n["kind"] == "activation" for n in bundle["ir"]["nodes"]))

    def test_source_module_and_constructor_never_execute(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "executed"
            source = f"open({str(marker)!r}, 'w').write('executed')\n" + SOURCE.replace("super().__init__()", f"open({str(marker)!r}, 'w').write('ctor')")
            self.analyze({"model.py": source})
            self.assertFalse(marker.exists())

    def test_invalid_inputs_and_nonfinite_values_are_rejected(self):
        for config in [[], "config", {"width": float("nan")}, {"width": float("inf")}]:
            with self.subTest(config=config), self.assertRaises(archcanvas_preview.AdapterError):
                self.analyze(config=config)
        for entry in [[], 42, "", "missing:Model"]:
            with self.subTest(entry=entry), self.assertRaises(archcanvas_preview.AdapterError):
                self.analyze(entry=entry)
        with self.assertRaises(archcanvas_preview.AdapterError):
            self.analyze({"../escape.py": SOURCE})

    def test_mode_selector_does_not_steal_constructor_parameter(self):
        bundle = self.analyze(config={"semanticMode": "actual constructor argument"})
        self.assertEqual(bundle["config"]["semanticMode"], "actual constructor argument")
        self.assertEqual(bundle["semanticMode"], "summary")

    def test_legacy_wire_contract_and_formal_authoring_remain_available(self):
        bundle = archcanvas_preview.analyze({"model.py": SOURCE}, "Model")
        self.assertNotIn("semantic_ir", bundle["ir"])
        architecture = archcanvas_preview.analyze_for_authoring({"model.py": SOURCE}, "Model")
        self.assertEqual(architecture["schemaVersion"], 1)
        self.assertEqual(architecture["entry"], "model:Model")


if __name__ == "__main__":
    unittest.main()
