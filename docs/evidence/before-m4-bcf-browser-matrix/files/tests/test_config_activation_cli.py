"""CLI holdouts for a shared probability origin and real isolated activation."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from archcanvas_python import analyze_project
from archcanvas_transactions import TransactionManager
from archcanvas_transactions.lowering import LoweringError

ROOT = Path(__file__).resolve().parents[1]
SOURCE = '''from torch import nn
RATE = 0.13  # preserve this unrelated 0.13 and reader expressions
class Configured(nn.Module):
    def __init__(self):
        super().__init__()
        self.incoming = nn.Dropout(RATE)
        self.outgoing = nn.Dropout(p=RATE)
        self.attention = nn.MultiheadAttention(8, 2, dropout=RATE, batch_first=True)
        self.activation = nn.ReLU()
    def forward(self, x):
        a = self.incoming(x)
        b = self.outgoing(a)
        y, weights = self.attention(b, b, b, need_weights=False)
        z = self.activation(y)
        return z
'''
SPEC = {"schemaVersion": 1, "inputs": {"x": {"shape": [2, 3, 8], "dtype": "float32"}}, "constructor": {}, "seed": 73, "modes": ["eval", "train"]}


class ConfigActivationCLITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="archcanvas-config-cli-", dir="/tmp")
        self.base = Path(self.directory.name)
        self.root = self.base / "source"; self.root.mkdir()
        self.path = self.root / "model.py"; self.path.write_bytes(SOURCE.encode())
        self.store = self.base / "transactions"
        self.architecture = analyze_project(self.root, "model:Configured")
        self.spec = self.base / "inputs.json"; self.spec.write_text(json.dumps(SPEC))

    def tearDown(self):
        self.directory.cleanup()

    def cli(self, action, *arguments, expected=0):
        command = [sys.executable, "-m", "archcanvas_cli", "patch", action, "--root", str(self.root), "--entry", "model:Configured", "--store", str(self.store), *map(str, arguments)]
        result = subprocess.run(command, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, capture_output=True, text=True, timeout=120)
        if expected is not None:
            self.assertEqual(result.returncode, expected, result.stderr or result.stdout)
        try:
            return json.loads(result.stdout if result.stdout else result.stderr)
        except json.JSONDecodeError:
            self.assertEqual(result.returncode, 2, result.stderr)
            return {"error": result.stderr}

    def node(self, kind):
        return next(node for node in self.architecture["nodes"] if node["kind"] == kind)

    def common(self, kind):
        return ["--node", self.node(kind)["id"], "--base-source-digest", self.architecture["sourceDigest"]]

    def runtime(self):
        return ["--input-spec", self.spec, "--runtime-interpreter", os.environ.get("ARCHCANVAS_RUNTIME_PYTHON", str(ROOT / ".venv-runtime/bin/python")), "--dependency-lock", os.environ.get("ARCHCANVAS_RUNTIME_LOCK", str(ROOT / "requirements-runtime.lock"))]

    def finish(self, receipt):
        reviewed = self.cli("review", "--transaction", receipt["id"])
        self.assertEqual(reviewed["reviewDigest"], receipt["reviewDigest"])
        approved = self.cli("approve", "--transaction", receipt["id"], "--review-digest", reviewed["reviewDigest"])
        self.assertEqual(approved["status"], "Approved", approved.get("blockers"))
        committed = self.cli("commit", "--transaction", receipt["id"], "--approval-id", approved["approvalId"])
        self.assertEqual(committed["status"], "Committed", committed.get("blockers"))
        return committed

    def test_configuration_complete_cli_review_commit_preserves_all_edges(self):
        receipt = self.cli("configuration", *self.common("Dropout"), "--parameter", "p", "--value", "0.26")
        self.assertEqual(receipt["status"], "ReviewReady")
        self.assertEqual(receipt["intent"]["kind"], "UpdateConfiguration")
        self.assertEqual(len(receipt["affectedNodeIds"]), 3)
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())
        committed = self.finish(receipt)
        self.assertEqual(self.path.read_bytes(), SOURCE.replace("RATE = 0.13", "RATE = 0.26").encode())
        after = committed["committedArchitecture"]
        self.assertEqual(after["edges"], self.architecture["edges"])
        readers = [node for node in after["nodes"] if node["kind"] in ("Dropout", "MultiheadAttention")]
        self.assertEqual([node["parameters"]["p" if node["kind"] == "Dropout" else "dropout"] for node in readers], [0.26, 0.26, 0.26])

    def test_configuration_cli_refuses_derived_reader_and_preserves_bytes(self):
        source = SOURCE.replace("p=RATE", "p=RATE * 2")
        self.path.write_bytes(source.encode())
        self.architecture = analyze_project(self.root, "model:Configured")
        receipt = self.cli("configuration", *self.common("Dropout"), "--parameter", "p", "--value", "0.26", expected=2)
        self.assertEqual(receipt["status"], "Failed")
        self.assertTrue(receipt["blockers"])
        self.assertEqual(self.path.read_bytes(), source.encode())

    def test_activation_cli_requires_explicit_runtime_arguments(self):
        error = self.cli("activation", *self.common("ReLU"), "--activation", "GELU", expected=2)
        self.assertIn("error", error)
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())

    def test_activation_cli_real_g6_and_exact_constructor_commit(self):
        receipt = self.cli("activation", *self.common("ReLU"), "--activation", "GELU", *self.runtime(), expected=0 if os.environ.get("ARCHCANVAS_REQUIRE_RUNTIME") == "1" else None)
        if receipt["status"] == "Failed" and receipt.get("runtimeVerification", {}).get("status") == "unavailable" and os.environ.get("ARCHCANVAS_REQUIRE_RUNTIME") != "1":
            self.skipTest("Mandatory kernel isolation is unavailable in this command sandbox.")
        self.assertEqual(receipt["status"], "ReviewReady", receipt.get("blockers"))
        self.assertEqual(receipt["transform"]["profile"], "structural-verified")
        self.assertEqual(next(g["status"] for g in receipt["gates"] if g["id"] == "G6"), "passed")
        verification = receipt["runtimeVerification"]
        self.assertEqual(verification["status"], "passed")
        self.assertTrue(receipt["checkpointImpact"]["modelExecuted"])
        self.assertFalse(receipt["checkpointImpact"]["checkpointLoaded"])
        self.assertEqual(receipt["checkpointImpact"]["sharing"], {"sharedGroups": [], "sharedStorageGroups": []})
        for field in ("sharedGroups", "sharedStorageGroups"):
            changed = copy.deepcopy(verification)
            changed["observation"]["modes"][0]["state"]["before"][field] = [["attention.in_proj_weight", "attention.out_proj.weight"]]
            with self.assertRaisesRegex(LoweringError, "tied parameter/storage"):
                TransactionManager._verify_runtime_contract(receipt, changed)
        self.assertEqual([mode["mode"] for mode in verification["observation"]["modes"]], ["eval", "train"])
        for mode in verification["observation"]["modes"]:
            activation = next(call for call in mode["calls"] if call["modulePath"] == "activation")
            self.assertTrue(activation["moduleType"].endswith(".GELU"))
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())
        committed = self.finish(receipt)
        self.assertEqual(self.path.read_bytes(), SOURCE.replace("nn.ReLU()", "nn.GELU()").encode())
        self.assertEqual(committed["committedArchitecture"]["edges"], self.architecture["edges"])
        self.assertEqual([n["id"] for n in committed["committedArchitecture"]["nodes"]], [n["id"] for n in self.architecture["nodes"]])


if __name__ == "__main__":
    unittest.main()
