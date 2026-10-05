"""HTTP scope and exact managed-copy connection commit, using authored source."""
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import ProxyHandler, build_opener
from unittest.mock import patch

import test_stage2_http as http_helpers
from archcanvas_cli.server import ArchCanvasServer
from archcanvas_python import analyze_project

SOURCE = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.first = nn.Identity()
        self.branch = nn.GELU()
        self.sink = nn.Dropout(0.1)
    def forward(self, features):
        initial = self.first(features)
        alternate = self.branch(initial)
        result = self.sink(initial)  # initial stays here
        return result
'''


class Stage3HTTPTests(unittest.TestCase):
    request = http_helpers.Stage2HTTPTests.request
    json_request = http_helpers.Stage2HTTPTests.json_request
    registration = http_helpers.Stage2HTTPTests.registration
    register = http_helpers.Stage2HTTPTests.register
    transaction_action = http_helpers.Stage2HTTPTests.transaction_action
    tearDown = http_helpers.Stage2HTTPTests.tearDown

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="archcanvas-http-stage3-", dir="/tmp")
        self.workspace = Path(self.temporary.name)
        self.original_root = self.workspace / "original"
        self.original_root.mkdir()
        self.original_path = self.original_root / "model.py"
        self.original_path.write_bytes(SOURCE.encode())
        self.before = analyze_project(self.original_root, "model:Model")
        try:
            self.server = ArchCanvasServer(("127.0.0.1", 0), data_dir=self.workspace / "managed/documents", studio_dir=self.workspace / "dist")
        except PermissionError:
            self.temporary.cleanup()
            self.skipTest("Loopback socket tests require an allowed local host.")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.client = build_opener(ProxyHandler({}))
        self.token = self.json_request("/api/session")[1]["token"]

    def target(self, project):
        node = next(n for n in project["architecture"]["nodes"] if n["kind"] == "Dropout")
        return {"nodeId": node["id"], "portId": next(p["id"] for p in node["ports"] if p["direction"] == "in"), "baseSourceDigest": project["sourceDigest"], "baseIrDigest": project["irDigest"]}

    def options(self, project):
        status, options = self.json_request(f"/api/projects/{project['id']}/rebind-options", "POST", self.target(project))
        self.assertEqual((status, options["status"]), (200, "supported"), options)
        self.assertEqual(options["target"]["slot"]["variable"], "initial")
        return options

    def test_inspect_prepare_exact_review_commit_reanalysis_and_reopen(self):
        project = self.register()
        options = self.options(project)
        alternate = next(c for c in options["candidates"] if c["variable"] == "alternate")
        self.assertFalse(alternate["contract"]["runtimeVerified"])
        self.assertTrue(alternate["contract"]["conditional"])
        payload = self.target(project) | {"producerNodeId": alternate["binding"]["nodeId"], "producerPortId": alternate["binding"]["portId"]}
        status, receipt = self.json_request(f"/api/projects/{project['id']}/rebind", "POST", payload)
        self.assertEqual((status, receipt["status"]), (200, "ReviewReady"), receipt)
        self.assertEqual(receipt["intent"]["kind"], "RebindInput")
        managed_path = self.server.workspace.source_root(project["id"]) / "model.py"
        self.assertEqual(managed_path.read_bytes(), SOURCE.encode())
        before_edge = next(e for e in receipt["beforeArchitecture"]["edges"] if e["target"]["nodeId"] == payload["nodeId"])
        after_edge = next(e for e in receipt["afterArchitecture"]["edges"] if e["target"]["nodeId"] == payload["nodeId"])
        self.assertEqual(after_edge, before_edge | {"source": {k: alternate["binding"][k] for k in ("nodeId", "portId")}, "tensorId": alternate["binding"]["tensorId"]})
        self.assertEqual(self.transaction_action(project, receipt, "approve", {"reviewDigest": "wrong"})[0], 400)
        self.assertEqual(self.transaction_action(project, receipt, "commit", {"approvalId": "wrong"})[0], 400)
        status, approved = self.transaction_action(project, receipt, "approve", {"reviewDigest": receipt["reviewDigest"]})
        self.assertEqual((status, approved["status"]), (200, "Approved"))
        status, committed = self.transaction_action(project, receipt, "commit", {"approvalId": approved["approvalId"]})
        self.assertEqual((status, committed["status"]), (200, "Committed"), committed)
        expected = SOURCE.replace("self.sink(initial)", "self.sink(alternate)")
        self.assertEqual(managed_path.read_bytes(), expected.encode())
        self.assertEqual(self.original_path.read_bytes(), SOURCE.encode())
        current = self.json_request(f"/api/projects/{project['id']}")[1]
        self.assertEqual(current["architecture"]["sources"][0]["content"], expected)
        doc = http_helpers.visual_document(current["architecture"])
        status, saved = self.json_request(f"/api/documents/{doc['id']}", "PUT", {"document": doc, "expectedRevision": 0})
        self.assertEqual(status, 200, saved)
        reopened = self.json_request(f"/api/documents/{doc['id']}")[1]["document"]
        self.assertEqual(reopened, doc)
        self.assertEqual(self.json_request(f"/api/projects/{project['id']}/transactions/{receipt['id']}")[1]["status"], "Committed")
        self.assertEqual(self.json_request(f"/api/projects/{project['id']}/rebind-options", "POST", self.target(project))[0], 409)

    def test_security_exact_versions_targets_and_project_binding(self):
        one, two = self.register(), self.register()
        target = self.target(one)
        route = f"/api/projects/{one['id']}/rebind-options"
        self.assertEqual(self.json_request(route, "POST", target, session=False)[0], 403)
        self.assertEqual(self.json_request(route, "POST", target, extra_headers={"Origin": "https://other.example"})[0], 403)
        self.assertEqual(self.json_request(route, "POST", target | {"root": str(self.original_root)})[0], 400)
        for field in ("baseSourceDigest", "baseIrDigest"):
            self.assertEqual(self.json_request(route, "POST", target | {field: "stale"})[0], 409)
        status, unsupported = self.json_request(route, "POST", target | {"portId": "wrong"})
        self.assertEqual((status, unsupported["supported"]), (200, False))
        self.assertEqual(unsupported["candidates"], [])
        status, unsupported = self.json_request(route, "POST", target | {"nodeId": "missing"})
        self.assertEqual((status, unsupported["status"]), (200, "unsupported"))
        self.assertTrue(unsupported["blockers"])
        candidate = next(c for c in self.options(one)["candidates"] if c["variable"] == "alternate")
        payload = target | {"producerNodeId": candidate["binding"]["nodeId"], "producerPortId": candidate["binding"]["portId"]}
        receipt = self.json_request(f"/api/projects/{one['id']}/rebind", "POST", payload)[1]
        self.assertEqual(receipt["status"], "ReviewReady")
        self.assertEqual(self.transaction_action(two, receipt, "approve", {"reviewDigest": receipt["reviewDigest"]})[0], 400)
        self.assertEqual(self.original_path.read_bytes(), SOURCE.encode())

    def test_unsupported_source_remains_a_proposal_without_transaction(self):
        self.original_path.write_text(SOURCE.replace("        return result", "        if features is None:\n            return initial\n        return result"))
        self.before = analyze_project(self.original_root, "model:Model")
        project = self.register()
        status, options = self.json_request(f"/api/projects/{project['id']}/rebind-options", "POST", self.target(project))
        self.assertEqual((status, options["supported"]), (200, False))
        self.assertTrue(options["blockers"])
        self.assertEqual(list((self.workspace / "managed/transactions").glob("*/receipt.json")), [])

    def test_source_changed_during_inspection_cannot_return_another_version_candidate(self):
        from archcanvas_python.rebind import inspect_rebind
        project = self.register()
        managed_path = self.server.workspace.source_root(project["id"]) / "model.py"
        def changed_inspection(*args, **kwargs):
            managed_path.write_bytes(SOURCE.encode() + b"# external edit during inspection\n")
            return inspect_rebind(*args, **kwargs)
        with patch("archcanvas_python.rebind.inspect_rebind", changed_inspection):
            status, response = self.json_request(f"/api/projects/{project['id']}/rebind-options", "POST", self.target(project))
        self.assertEqual(status, 409, response)
        self.assertEqual(self.original_path.read_bytes(), SOURCE.encode())


if __name__ == "__main__":
    unittest.main()
