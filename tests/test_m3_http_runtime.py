"""Real asynchronous HTTP structural runtime, review and scoped commit."""
import copy
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.request import ProxyHandler, build_opener

from archcanvas_cli.server import ArchCanvasServer
from archcanvas_python import analyze_project
from m3_runtime_oracle import INPUT_SPEC, SOURCE, expected_source
import test_stage2_http as http_helpers


class M3HTTPRuntimeTests(unittest.TestCase):
    request = http_helpers.Stage2HTTPTests.request
    json_request = http_helpers.Stage2HTTPTests.json_request
    registration = http_helpers.Stage2HTTPTests.registration
    register = http_helpers.Stage2HTTPTests.register
    transaction_action = http_helpers.Stage2HTTPTests.transaction_action
    tearDown = http_helpers.Stage2HTTPTests.tearDown

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="archcanvas-runtime-http-")
        self.workspace = Path(self.temporary.name)
        self.original_root = self.workspace / "original"
        self.original_root.mkdir()
        self.original_path = self.original_root / "model.py"
        self.original_path.write_text(SOURCE)
        self.before = analyze_project(self.original_root, "model:CrossAttention")
        try:
            self.server = ArchCanvasServer(("127.0.0.1", 0), data_dir=self.workspace / "managed/documents", studio_dir=self.workspace / "dist")
        except PermissionError:
            self.temporary.cleanup()
            if os.environ.get("ARCHCANVAS_REQUIRE_RUNTIME") == "1":
                raise
            self.skipTest("The restricted shell denies local HTTP sockets.")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.client = build_opener(ProxyHandler({}))
        self.token = self.json_request("/api/session")[1]["token"]

    def payload(self, project):
        node = next(node for node in project["architecture"]["nodes"] if node["kind"] == "MultiheadAttention")
        key_port = next(port["id"] for port in node["ports"] if port["direction"] == "in" and port["name"] == "key")
        target = {"nodeId": node["id"], "portId": key_port, "baseSourceDigest": project["sourceDigest"], "baseIrDigest": project["irDigest"], "inputSpec": copy.deepcopy(INPUT_SPEC)}
        status, options = self.json_request(f"/api/projects/{project['id']}/structural-rebind-options", "POST", target)
        self.assertEqual((status, options["status"]), (200, "supported"), options)
        alternate = next(candidate for candidate in options["candidates"] if candidate["variable"] == "alternative")
        return target | {"producerNodeId": alternate["binding"]["nodeId"], "producerPortId": alternate["binding"]["portId"]}

    def await_job(self, project, job):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            status, value = self.json_request(f"/api/projects/{project['id']}/runtime-jobs/{job['id']}", extra_headers={"X-ArchCanvas-Session": self.token})
            self.assertEqual(status, 200, value)
            if value["status"] != "running":
                return value
            time.sleep(0.05)
        self.fail("Asynchronous runtime job did not terminate within its declared wall budget.")

    def test_async_profile_review_and_commit_bind_real_runtime_and_only_managed_source(self):
        project = self.register()
        payload = self.payload(project)
        route = f"/api/projects/{project['id']}/structural-rebind-jobs"
        self.assertEqual(self.json_request(route, "POST", payload, session=False)[0], 403)
        self.assertEqual(self.json_request(route, "POST", payload | {"interpreter": "/usr/bin/python3"})[0], 400)
        started = time.monotonic()
        status, job = self.json_request(route, "POST", payload)
        self.assertEqual(status, 202, job)
        self.assertLess(time.monotonic() - started, 1)
        self.assertEqual(self.json_request(f"/api/projects/{project['id']}/runtime-jobs/{job['id']}", session=False)[0], 403)
        self.assertEqual(self.json_request(f"/api/projects/wrong-project/runtime-jobs/{job['id']}", extra_headers={"X-ArchCanvas-Session": self.token})[0], 400)
        finished = self.await_job(project, job)
        self.assertEqual(finished["status"], "complete", finished)
        receipt = finished["transaction"]
        if receipt["status"] == "Failed" and os.environ.get("ARCHCANVAS_REQUIRE_RUNTIME") != "1":
            self.skipTest(str(receipt.get("blockers")))
        self.assertEqual(receipt["status"], "ReviewReady", receipt.get("blockers"))
        self.assertEqual(receipt["intent"]["validationProfile"], "structural-verified")
        managed = self.server.workspace.source_root(project["id"]) / "model.py"
        self.assertEqual(managed.read_text(), SOURCE)
        self.assertNotIn("approvalId", receipt)
        status, approved = self.transaction_action(project, receipt, "approve", {"reviewDigest": receipt["reviewDigest"]})
        self.assertEqual((status, approved["status"]), (200, "Approved"), approved)
        status, committed = self.transaction_action(project, receipt, "commit", {"approvalId": approved["approvalId"]})
        self.assertEqual((status, committed["status"]), (200, "Committed"), committed)
        self.assertEqual(managed.read_bytes(), expected_source())
        self.assertEqual(self.original_path.read_text(), SOURCE)
        self.assertEqual(self.json_request(f"/api/projects/{project['id']}")[1]["architecture"]["sources"][0]["content"], expected_source().decode())

    def test_asynchronous_cancel_prevents_reviewready_and_source_changes(self):
        project = self.register()
        payload = self.payload(project)
        route = f"/api/projects/{project['id']}/structural-rebind-jobs"
        status, job = self.json_request(route, "POST", payload)
        self.assertEqual(status, 202, job)
        status, _ = self.json_request(f"/api/projects/{project['id']}/runtime-jobs/{job['id']}/cancel", "POST", {})
        self.assertEqual(status, 200)
        finished = self.await_job(project, job)
        self.assertEqual(finished["status"], "complete", finished)
        receipt = finished["transaction"]
        self.assertEqual(receipt["status"], "Failed", receipt)
        self.assertIn("cancel", str(receipt).lower())
        self.assertNotIn("approvalId", receipt)
        self.assertEqual((self.server.workspace.source_root(project["id"]) / "model.py").read_text(), SOURCE)
        self.assertEqual(self.original_path.read_text(), SOURCE)


if __name__ == "__main__":
    unittest.main()
