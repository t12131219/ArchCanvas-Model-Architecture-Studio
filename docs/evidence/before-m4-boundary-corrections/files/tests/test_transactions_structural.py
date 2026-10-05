"""Static structural oracles and strict runtime failure, without fallback."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archcanvas_python import analyze_project
from archcanvas_python.structural_rebind import inspect_structural_rebind
from archcanvas_transactions import TransactionManager
from archcanvas_transactions.rebind import expected_structural_rebind, rewrite_name


SOURCE = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.branch = nn.ReLU()
        self.attn = nn.MultiheadAttention(8, 2, dropout=0.1, batch_first=True)
    def forward(self, query, memory, other, mask):
        alternative = self.branch(other)
        output, weights = self.attn(query=query, key=memory, value=memory, attn_mask=mask, need_weights=False)
        return output
'''
SPEC = {"schemaVersion": 1, "inputs": {"query": {"shape": [2, 3, 8], "dtype": "float32"}, "memory": {"shape": [2, 5, 8], "dtype": "float32"}, "other": {"shape": [2, 5, 8], "dtype": "float32"}, "mask": {"shape": [3, 5], "dtype": "bool"}}, "constructor": {}, "seed": 37, "modes": ["eval", "train"]}


class StructuralTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/tmp", prefix="archcanvas-structural-static-")
        self.base = Path(self.temp.name); self.root = self.base / "source"; self.root.mkdir()
        self.path = self.root / "model.py"; self.path.write_text(SOURCE)
        self.arch = analyze_project(self.root, "model:Model")
        self.target = next(node for node in self.arch["nodes"] if node["kind"] == "MultiheadAttention")
        self.producer = next(node for node in self.arch["nodes"] if node["kind"] == "ReLU")
        self.manager = TransactionManager(self.base / "transactions")

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, spec=SPEC, config=None, slot="key"):
        return self.manager.prepare_rebind(self.root, "model:Model", self.target["id"], f"{self.target['id']}:in:{slot}", self.producer["id"], f"{self.producer['id']}:out:output", self.arch["sourceDigest"], inputSpec=copy.deepcopy(spec), runtimeConfig=config)

    def evidence(self, spec=SPEC, slot="key"):
        return inspect_structural_rebind(self.root, "model:Model", self.target["id"], f"{self.target['id']}:in:{slot}", copy.deepcopy(spec), self.arch)

    def test_named_key_splice_and_independent_expected_bindings(self):
        evidence = self.evidence()
        self.assertTrue(evidence["supported"], evidence["blockers"])
        plan, affected, intent = expected_structural_rebind(self.arch, self.root, "model:Model", self.target["id"], f"{self.target['id']}:in:key", self.producer["id"], f"{self.producer['id']}:out:output", SPEC)
        changed = rewrite_name(SOURCE.encode(), intent["origin"], "memory", "alternative")
        self.assertEqual(changed, SOURCE.replace("key=memory", "key=alternative").encode())
        slots = {edge["target"]["portId"].rsplit(":", 1)[-1]: edge for edge in plan["edges"] if edge["target"]["nodeId"] == self.target["id"]}
        self.assertEqual(slots["key"]["source"]["nodeId"], self.producer["id"])
        for name in ("query", "value", "attn_mask"):
            old = next(edge for edge in self.arch["edges"] if edge["target"]["portId"] == f"{self.target['id']}:in:{name}")
            self.assertEqual(slots[name], old)
        self.assertEqual(intent["expectedRuntimeContract"]["outputs"], [{"variable": "output", "contract": {"shape": [2, 3, 8], "dtype": "float32"}}])
        self.assertEqual(len(intent["expectedRuntimeContract"]["state"]), 4)
        self.assertEqual(self.path.read_text(), SOURCE)

    def test_missing_runtime_is_failed_without_static_downgrade(self):
        receipt = self.prepare()
        self.assertEqual(receipt["status"], "Failed")
        self.assertEqual(receipt["transform"]["profile"], "structural-verified")
        self.assertEqual(next(gate["status"] for gate in receipt["gates"] if gate["id"] == "G6"), "failed")
        self.assertEqual(self.path.read_text(), SOURCE)

    def test_runtime_unavailable_or_failed_is_not_review_ready(self):
        interpreter, lock = self.base / "python", self.base / "lock.txt"
        interpreter.write_bytes(b"a frozen interpreter for fault injection only"); lock.write_text("torch==2.5.1+cpu\n")
        config = {"interpreter": str(interpreter), "dependencyLock": str(lock)}
        for state in ("unavailable", "failed"):
            with self.subTest(state=state), patch("archcanvas_runtime.verify_structural", return_value={"status": state, "reason": "injected runtime gate failure"}):
                receipt = self.prepare(config=config)
            self.assertEqual(receipt["status"], "Failed")
            self.assertIn("injected runtime gate failure", receipt["blockers"][0])

    def test_mha_mask_axes_dtype_and_key_value_lengths_are_checked(self):
        mutations = [("mask", "shape", [2, 5]), ("mask", "dtype", "float32"), ("memory", "shape", [2, 5, 7]), ("query", "shape", [3, 3, 8]), ("memory", "dtype", "float64")]
        for name, field, value in mutations:
            with self.subTest(name=name, field=field):
                spec = copy.deepcopy(SPEC); spec["inputs"][name][field] = value
                self.assertFalse(self.evidence(spec)["supported"])
        good = self.evidence()
        self.assertTrue(good["supported"])
        self.assertNotIn("query", [candidate["variable"] for candidate in good["candidates"]])

    def test_worker_pass_label_cannot_replace_independent_runtime_gate(self):
        interpreter, lock = self.base / "python", self.base / "lock.txt"
        interpreter.write_bytes(b"fault-injection-only"); lock.write_text("torch==2.5.1+cpu\n")
        with patch("archcanvas_runtime.verify_structural", return_value={"status": "passed", "profile": "structural-verified", "sourceDigest": "wrong-frozen-source"}):
            receipt = self.prepare(config={"interpreter": str(interpreter), "dependencyLock": str(lock)})
        self.assertEqual(receipt["status"], "Failed")
        self.assertEqual(next(g["status"] for g in receipt["gates"] if g["id"] == "G6"), "failed")
        self.assertIn("Independent structural runtime contract", receipt["blockers"][0])
        self.assertEqual(self.path.read_text(), SOURCE)

    def test_call_ordinal_and_named_keyword_contract_are_distinct(self):
        self.path.write_text(SOURCE.replace("query=query, key=memory, value=memory", "query, memory, memory"))
        self.arch = analyze_project(self.root, "model:Model")
        evidence = self.evidence()
        self.assertTrue(evidence["supported"], evidence["blockers"])
        changed = rewrite_name(self.path.read_bytes(), evidence["target"]["slot"], "memory", "alternative")
        self.assertIn(b"self.attn(query, alternative, memory,", changed)
        self.assertNotIn(b"self.attn(query, memory, alternative,", changed)


if __name__ == "__main__":
    unittest.main()
