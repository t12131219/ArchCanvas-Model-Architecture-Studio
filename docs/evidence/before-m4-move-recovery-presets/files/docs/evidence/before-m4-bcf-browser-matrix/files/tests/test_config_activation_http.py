"""Independent managed-copy HTTP configuration and activation boundaries."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from archcanvas_cli.server import ArchCanvasServer
from archcanvas_python import analyze_project

SOURCE = '''from torch import nn
DROP_RATE = 0.15  # this 0.15 comment must survive
class HTTPModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.left = nn.Dropout(DROP_RATE)
        self.right = nn.Dropout(p=DROP_RATE)
        self.attention = nn.MultiheadAttention(8, 2, dropout=DROP_RATE, batch_first=True)
        self.activation = nn.ReLU()
    def forward(self, x):
        a = self.left(x)
        b = self.right(a)
        y, weights = self.attention(b, b, b, need_weights=False)
        result = self.activation(y)
        return result
'''
SPEC = {"schemaVersion": 1, "inputs": {"x": {"shape": [2, 4, 8], "dtype": "float32"}}, "seed": 31, "modes": ["eval", "train"]}


class ConfigActivationHTTPTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="archcanvas-config-http-", dir="/tmp")
        self.base = Path(self.directory.name)
        self.original = self.base / "original"; self.original.mkdir()
        self.source = self.original / "model.py"; self.source.write_bytes(SOURCE.encode())
        self.architecture = analyze_project(self.original, "model:HTTPModel")
        try:
            self.server = ArchCanvasServer(("127.0.0.1", 0), data_dir=self.base / "workspace/documents", studio_dir=self.base / "dist")
        except PermissionError:
            self.directory.cleanup()
            if os.environ.get("ARCHCANVAS_REQUIRE_RUNTIME") == "1":
                raise
            self.skipTest("Loopback sockets are unavailable in this command sandbox.")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.client = build_opener(ProxyHandler({}))
        code, project = self.request("/api/projects", "POST", {"entry": "model:HTTPModel", "sources": [{"path": "model.py", "content": SOURCE, "digest": hashlib.sha256(SOURCE.encode()).hexdigest()}], "sourceDigest": self.architecture["sourceDigest"], "irDigest": self.architecture["irDigest"]})
        self.assertEqual(code, 201, project)
        self.project = project
        self.path = self.server.workspace.source_root(project["id"]) / "model.py"

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=3)
        self.directory.cleanup()

    def request(self, path, method="GET", payload=None):
        request = Request(self.url + path, data=None if payload is None else json.dumps(payload).encode(), method=method, headers={"Content-Type": "application/json", "X-ArchCanvas-Session": self.server.session_token})
        try:
            with self.client.open(request, timeout=60) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def route(self, suffix):
        return f"/api/projects/{self.project['id']}/{suffix}"

    def node(self, kind):
        return next(n for n in self.project["architecture"]["nodes"] if n["kind"] == kind)

    def common(self, kind):
        return {"nodeId": self.node(kind)["id"], "baseSourceDigest": self.project["sourceDigest"], "baseIrDigest": self.project["irDigest"]}

    def test_configuration_options_review_and_commit_only_managed_copy(self):
        common = {**self.common("Dropout"), "parameter": "p"}
        code, options = self.request(self.route("configuration-options"), "POST", common)
        self.assertEqual(code, 200)
        self.assertTrue(options["supported"], options.get("blockers"))
        self.assertEqual(options["target"]["name"], "DROP_RATE")
        self.assertEqual(len(options["affectedNodeIds"]), 3)
        code, receipt = self.request(self.route("configuration"), "POST", {**common, "value": 0.3})
        self.assertEqual((code, receipt["status"]), (200, "ReviewReady"))
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())
        code, rejected = self.request(self.route(f"transactions/{receipt['id']}/approve"), "POST", {"reviewDigest": "0" * 64})
        self.assertEqual(code, 400)
        self.assertIn("review", rejected["error"].lower())
        code, approved = self.request(self.route(f"transactions/{receipt['id']}/approve"), "POST", {"reviewDigest": receipt["reviewDigest"]})
        self.assertEqual((code, approved["status"]), (200, "Approved"))
        code, committed = self.request(self.route(f"transactions/{receipt['id']}/commit"), "POST", {"approvalId": approved["approvalId"]})
        self.assertEqual((code, committed["status"]), (200, "Committed"))
        self.assertEqual(self.path.read_bytes(), SOURCE.replace("DROP_RATE = 0.15", "DROP_RATE = 0.3").encode())
        self.assertEqual(self.source.read_bytes(), SOURCE.encode())
        self.assertEqual(committed["committedArchitecture"]["edges"], self.architecture["edges"])

    def test_configuration_rejects_stale_base_and_caller_filesystem_environment(self):
        valid = {**self.common("Dropout"), "parameter": "p", "value": 0.3}
        for key, value in (("root", str(self.original)), ("runtimeConfig", {})):
            code, _ = self.request(self.route("configuration"), "POST", {**valid, key: value})
            self.assertEqual(code, 400)
        code, _ = self.request(self.route("configuration"), "POST", {**valid, "baseIrDigest": "0" * 64})
        self.assertEqual(code, 409)
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())

    def test_activation_null_input_spec_cannot_select_static_profile(self):
        code, error = self.request(self.route("activation-jobs"), "POST", {**self.common("ReLU"), "activation": "GELU", "inputSpec": None})
        self.assertEqual(code, 400, error)
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())

    def test_activation_real_async_job_serializes_event_free_review(self):
        code, job = self.request(self.route("activation-jobs"), "POST", {**self.common("ReLU"), "activation": "GELU", "inputSpec": copy.deepcopy(SPEC)})
        self.assertEqual(code, 202, job)
        self.assertNotIn("cancelEvent", job)
        deadline = time.monotonic() + 100
        while job["status"] == "running" and time.monotonic() < deadline:
            time.sleep(0.1)
            code, job = self.request(self.route(f"runtime-jobs/{job['id']}"))
            self.assertEqual(code, 200, job)
            self.assertNotIn("cancelEvent", job)
        self.assertEqual(job["status"], "complete", job)
        receipt = job["transaction"]
        if receipt["status"] == "Failed" and receipt.get("runtimeVerification", {}).get("status") == "unavailable" and os.environ.get("ARCHCANVAS_REQUIRE_RUNTIME") != "1":
            self.skipTest("Mandatory kernel isolation unavailable in the command sandbox.")
        self.assertEqual(receipt["status"], "ReviewReady", receipt.get("blockers"))
        self.assertEqual(receipt["transform"]["profile"], "structural-verified")
        self.assertEqual(next(g["status"] for g in receipt["gates"] if g["id"] == "G6"), "passed")
        private = json.loads((self.server.transactions.store / receipt["id"] / "record.json").read_text())
        self.assertNotIn("cancelEvent", private["_runtimeConfig"])
        self.assertTrue(receipt["checkpointImpact"]["modelExecuted"])
        self.assertFalse(receipt["checkpointImpact"]["checkpointLoaded"])
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())
        code, approved = self.request(self.route(f"transactions/{receipt['id']}/approve"), "POST", {"reviewDigest": receipt["reviewDigest"]})
        self.assertEqual((code, approved["status"]), (200, "Approved"), approved)
        code, committed = self.request(self.route(f"transactions/{receipt['id']}/commit"), "POST", {"approvalId": approved["approvalId"]})
        self.assertEqual((code, committed["status"]), (200, "Committed"), committed)
        self.assertEqual(self.path.read_bytes(), SOURCE.replace("nn.ReLU()", "nn.GELU()").encode())
        self.assertEqual(self.source.read_bytes(), SOURCE.encode())
        self.assertEqual(committed["committedArchitecture"]["edges"], self.architecture["edges"])


if __name__ == "__main__":
    unittest.main()
