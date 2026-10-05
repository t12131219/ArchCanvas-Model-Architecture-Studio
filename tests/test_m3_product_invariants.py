"""Independent config/activation holdouts; every approval writes our own /tmp model."""

from __future__ import annotations

import copy
import os
from pathlib import Path
import tempfile
import unittest

from archcanvas_python import analyze_project
from archcanvas_transactions import TransactionError, TransactionManager

ROOT = Path(__file__).resolve().parents[1]
CONFIG_SOURCE = '''from torch import nn

P = 0.1  # shared configuration; preserve comments and direct readers

class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.left = nn.Dropout(P)
        self.right = nn.Dropout(p=P)
        self.spare = nn.Dropout(p=0.1)
        self.attention = nn.MultiheadAttention(8, 2, dropout=P)

    def forward(self, q, memory):
        first = self.left(q)
        second = self.left(first)
        third = self.right(second)
        fourth = self.spare(third)
        output, weights = self.attention(fourth, memory, memory, need_weights=False)
        return output
'''
ACTIVATION_SOURCE = '''from torch import nn

class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.activation = nn.ReLU()  # independent exact class-token expectation

    def forward(self, features):
        result = self.activation(features)
        return result
'''
ACTIVATION_SPEC = {"schemaVersion": 1, "inputs": {"features": {"shape": [2, 3, 8], "dtype": "float32", "fill": "normal"}}, "constructor": {}, "seed": 53, "modes": ["eval", "train"]}


class M3ProductInvariantTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="archcanvas-product-oracle-", dir="/tmp")
        self.base = Path(self.directory.name)
        self.project = self.base / "project"; self.project.mkdir()
        self.model = self.project / "model.py"
        self.manager = TransactionManager(self.base / "transactions")

    def tearDown(self):
        self.directory.cleanup()

    def source(self, content):
        self.model.write_bytes(content.encode())
        self.architecture = analyze_project(self.project, "model:Model")

    def config(self):
        node = next(n for n in self.architecture["nodes"] if n.get("instanceId", "").endswith(".left"))
        return self.manager.prepare_config(self.project, "model:Model", node["id"], "p", 0.25, self.architecture["sourceDigest"])

    def activation(self, **kwargs):
        node = next(n for n in self.architecture["nodes"] if n.get("instanceId", "").endswith(".activation"))
        return self.manager.prepare_activation(self.project, "model:Model", node["id"], "GELU", self.architecture["sourceDigest"], **kwargs)

    def rejected(self, action):
        before = self.model.read_bytes()
        try:
            record = action()
        except TransactionError:
            pass
        else:
            self.assertIn(record["status"], {"Failed", "Stale", "RolledBack", "ManualRecovery"}, record)
            self.assertTrue(record.get("blockers") or record.get("recovery"))
        self.assertEqual(self.model.read_bytes(), before)

    def commit(self, record):
        self.assertEqual(record["status"], "ReviewReady", record.get("blockers"))
        approved = self.manager.approve(record["id"], record["reviewDigest"])
        committed = self.manager.commit(record["id"], approved["approvalId"])
        self.assertEqual(committed["status"], "Committed", committed.get("blockers"))
        return committed

    def test_configuration_changes_only_definition_and_all_probability_readers(self):
        self.source(CONFIG_SOURCE)
        record = self.config()
        self.assertEqual(self.model.read_bytes(), CONFIG_SOURCE.encode())
        self.assertEqual(record["intent"]["kind"], "UpdateConfiguration")
        self.assertEqual(record["intent"]["scope"], "all_configuration_readers")
        committed = self.commit(record)
        self.assertEqual(self.model.read_bytes(), CONFIG_SOURCE.encode().replace(b"P = 0.1", b"P = 0.25", 1))
        after = committed["committedArchitecture"]
        self.assertEqual(after["edges"], self.architecture["edges"])
        self.assertEqual([n["ports"] for n in after["nodes"]], [n["ports"] for n in self.architecture["nodes"]])
        readers = [n for n in after["nodes"] if n.get("instanceId", "").endswith((".left", ".right", ".attention"))]
        self.assertEqual(len(readers), 4, "Shared left is called twice and all four calls must be reviewed")
        for n in readers:
            self.assertEqual(n["parameters"]["dropout" if n["kind"] == "MultiheadAttention" else "p"], 0.25)
        spare = next(n for n in after["nodes"] if n.get("instanceId", "").endswith(".spare"))
        self.assertEqual(spare["parameters"]["p"], 0.1)

    def test_configuration_rejects_derived_and_unregistered_reads(self):
        for extra in ("UNRELATED = P\n", "DERIVED = P * 2\n"):
            with self.subTest(extra=extra):
                self.source(CONFIG_SOURCE.replace("P = 0.1", extra + "P = 0.1"))
                self.rejected(self.config)
        self.source(CONFIG_SOURCE.replace("nn.Dropout(p=P)", "nn.Dropout(p=P / 2)"))
        self.rejected(self.config)

    def test_configuration_rejects_shadow_reassignment_and_hidden_readers(self):
        variants = [
            CONFIG_SOURCE.replace("def __init__(self):", "def __init__(self, P=0.1):"),
            CONFIG_SOURCE.replace("P = 0.1", "P = 0.2\nP = 0.1"),
            CONFIG_SOURCE + "\nclass Hidden(nn.Module):\n    def __init__(self):\n        super().__init__()\n        self.hidden = nn.Dropout(P)\n",
        ]
        for source in variants:
            with self.subTest(source=source):
                self.source(source); self.rejected(self.config)

    def test_static_activation_changes_one_class_token_and_all_shared_calls(self):
        source = ACTIVATION_SOURCE.replace("return result", "again = self.activation(result)\n        return again")
        self.source(source)
        record = self.activation()
        self.assertEqual(record["intent"]["kind"], "ReplaceActivation")
        self.assertEqual(record["intent"]["scope"], "all_constructor_instances")
        committed = self.commit(record)
        self.assertEqual(self.model.read_bytes(), source.encode().replace(b"nn.ReLU()", b"nn.GELU()", 1))
        after = committed["committedArchitecture"]
        self.assertEqual(after["edges"], self.architecture["edges"])
        calls = [n for n in after["nodes"] if n.get("instanceId", "").endswith(".activation")]
        self.assertEqual(len(calls), 2)
        self.assertEqual({n["kind"] for n in calls}, {"GELU"})

    def test_activation_rejects_custom_constructor_arguments(self):
        for constructor in ("nn.ReLU(inplace=False)", "nn.ReLU(True)", "nn.GELU(approximate='tanh')"):
            with self.subTest(constructor=constructor):
                self.source(ACTIVATION_SOURCE.replace("nn.ReLU()", constructor))
                self.rejected(self.activation)

    def test_activation_explicit_sample_without_runtime_cannot_downgrade(self):
        self.source(ACTIVATION_SOURCE)
        self.rejected(lambda: self.activation(inputSpec=copy.deepcopy(ACTIVATION_SPEC), runtimeConfig={}))

    def test_verified_activation_actual_train_eval_commit_has_mandatory_G6(self):
        self.source(ACTIVATION_SOURCE)
        config = {"interpreter": os.environ.get("ARCHCANVAS_RUNTIME_PYTHON", str(ROOT / ".venv-runtime/bin/python")),
                  "dependencyLock": os.environ.get("ARCHCANVAS_RUNTIME_LOCK", str(ROOT / "requirements-runtime.lock")),
                  "timeoutSeconds": 20, "cpuSeconds": 20, "memoryMb": 4096}
        record = self.activation(inputSpec=copy.deepcopy(ACTIVATION_SPEC), runtimeConfig=config)
        if record["status"] != "ReviewReady" and any("unavailable" in b.lower() for b in record.get("blockers", [])) and os.environ.get("ARCHCANVAS_REQUIRE_RUNTIME") != "1":
            self.skipTest("Required formal kernel-isolated runtime is unavailable")
        self.assertEqual(record["status"], "ReviewReady", record.get("blockers"))
        self.assertEqual(record["intent"]["validationProfile"], "structural-verified")
        self.assertEqual(next(g["status"] for g in record["gates"] if g["id"] == "G6"), "passed")
        self.commit(record)
        self.assertEqual(self.model.read_bytes(), ACTIVATION_SOURCE.encode().replace(b"nn.ReLU()", b"nn.GELU()", 1))
