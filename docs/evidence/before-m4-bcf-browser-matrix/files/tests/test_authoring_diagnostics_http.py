"""Loopback transport and persistence boundaries for structured draft errors.

Fixtures and error expectations are handwritten. No Studio private state,
generated symbols, model imports, or tensor execution is used.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from archcanvas_cli.server import ArchCanvasServer


def draft():
    return {"schemaVersion": 1, "mode": "authored-draft", "id": "draft-abcd",
            "title": "重复标签错误定位", "revision": 0,
            "nodes": [
                {"id": "input", "kind": "Input", "label": "重复名称", "parameters": {"shape": [2, 16]}, "position": {"x": 0, "y": 0}},
                {"id": "linear", "kind": "Linear", "label": "重复名称", "parameters": {"in_features": 16}, "position": {"x": 0, "y": 80}},
                {"id": "output", "kind": "Output", "label": "重复名称", "parameters": {}, "position": {"x": 0, "y": 160}}],
            "edges": [
                {"id": "e1", "source": {"nodeId": "input", "portId": "output"}, "target": {"nodeId": "linear", "portId": "input"}},
                {"id": "e2", "source": {"nodeId": "linear", "portId": "output"}, "target": {"nodeId": "output", "portId": "input"}}]}


def file_hashes(directory):
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob("*") if path.is_file()}


class AuthoringDiagnosticHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="archcanvas-diagnostic-http-")
        self.root = Path(self.temporary.name)
        try:
            self.server = ArchCanvasServer(("127.0.0.1", 0), data_dir=self.root / "documents", studio_dir=self.root / "not-built")
        except PermissionError:
            self.temporary.cleanup()
            self.skipTest("Loopback socket creation is unavailable in this sandbox; run in the permitted host.")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.client = build_opener(ProxyHandler({}))
        status, session, _ = self.request("/api/session")
        self.assertEqual(status, 200)
        self.token = session["token"]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def request(self, path, payload=None, token=None):
        request = Request(self.url + path, data=json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None,
                          method="POST" if payload is not None else "GET",
                          headers={"Content-Type": "application/json", **({"X-ArchCanvas-Session": token} if token else {})})
        try:
            response = self.client.open(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read()), dict(response.headers)

    def post(self, path, payload):
        return self.request(path, payload, self.token)

    def test_same_shape_error_over_validate_generate_save_preserves_existing_storage(self):
        good = draft()
        status, receipt, _ = self.post("/api/authoring/drafts/draft-abcd", {"draft": good, "expectedRevision": 0})
        self.assertEqual((status, receipt["revision"]), (200, 1))
        before = file_hashes(self.root)
        bad = deepcopy(good)
        bad["nodes"][1]["parameters"]["in_features"] = 12
        responses = []
        for path, payload in [("/api/authoring/validate", {"draft": bad}),
                              ("/api/authoring/generate", {"draft": bad}),
                              ("/api/authoring/drafts/draft-abcd", {"draft": bad, "expectedRevision": 1})]:
            status, body, headers = self.post(path, payload)
            self.assertEqual(status, 400)
            self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
            self.assertEqual(body["error"], "重复名称: final input dimension 16 does not equal in_features 12.")
            self.assertEqual(body["diagnostics"][0]["technical"], body["error"])
            self.assertEqual({key: body["diagnostics"][0][key] for key in ["code", "nodeId", "parameter", "portId", "expected", "actual"]},
                             {"code": "linear_input_features_mismatch", "nodeId": "linear", "parameter": "in_features",
                              "portId": "input", "expected": 12, "actual": 16})
            self.assertEqual(file_hashes(self.root), before)
            responses.append(body)
        self.assertEqual(responses, [responses[0]] * 3)
        self.assertEqual(self.request("/api/authoring/drafts/draft-abcd")[1], receipt)

    def test_incomplete_validate_save_allowed_generate_reports_same_issues_no_writes(self):
        partial = draft()
        partial["edges"].pop()
        status, validation, _ = self.post("/api/authoring/validate", {"draft": partial})
        self.assertEqual(status, 200)
        self.assertFalse(validation["complete"])
        issue = next(item for item in validation["issues"] if item["code"] == "unbound-input")
        self.assertEqual((issue["nodeId"], issue["portId"]), ("output", "input"))
        self.assertRegex(issue["message"], "[\u4e00-\u9fff]")
        status, saved, _ = self.post("/api/authoring/drafts/draft-abcd", {"draft": partial, "expectedRevision": 0})
        self.assertEqual((status, saved["draft"]), (200, partial))
        before = file_hashes(self.root)
        status, error, _ = self.post("/api/authoring/generate", {"draft": partial})
        self.assertEqual(status, 400)
        self.assertEqual(error["diagnostics"], validation["issues"])
        self.assertTrue(error["error"].startswith("Draft is incomplete: 重复名称: connect input."))
        self.assertEqual(file_hashes(self.root), before)

    def test_blank_draft_global_issues_have_no_fake_target_and_reopen_is_exact(self):
        blank = draft()
        blank["nodes"], blank["edges"] = [], []
        status, validation, _ = self.post("/api/authoring/validate", {"draft": blank})
        self.assertEqual(status, 200)
        self.assertEqual([item["code"] for item in validation["issues"]], ["missing-input", "missing-output"])
        self.assertTrue(all("nodeId" not in item for item in validation["issues"]))
        self.assertEqual(self.post("/api/authoring/drafts/draft-abcd", {"draft": blank, "expectedRevision": 0})[0], 200)
        self.assertEqual(self.request("/api/authoring/drafts/draft-abcd")[1]["draft"], blank)
        before = file_hashes(self.root)
        status, error, _ = self.post("/api/authoring/generate", {"draft": blank})
        self.assertEqual(status, 400)
        self.assertEqual(error["diagnostics"], validation["issues"])
        self.assertEqual(error["error"], "Draft is incomplete: Add at least one Input module. Add at least one Output module.")
        self.assertEqual(file_hashes(self.root), before)

    def test_unrelated_http_and_cas_errors_do_not_claim_a_draft_field(self):
        good = draft()
        cases = [("/api/authoring/generate", {"draft": good, "sourceRoot": "/etc"}, 400),
                 ("/api/authoring/drafts/draft-abcd", {"draft": good, "expectedRevision": -1}, 400)]
        for path, payload, expected in cases:
            status, body, _ = self.post(path, payload)
            self.assertEqual(status, expected)
            self.assertNotIn("diagnostics", body)
        self.assertEqual(self.post("/api/authoring/drafts/draft-abcd", {"draft": good, "expectedRevision": 0})[0], 200)
        status, body, _ = self.post("/api/authoring/drafts/draft-abcd", {"draft": good, "expectedRevision": 0})
        self.assertEqual(status, 409)
        self.assertEqual(body["revision"], 1)
        self.assertNotIn("diagnostics", body)
        status, body, _ = self.request("/api/authoring/generate", {"draft": good}, "wrong-token")
        self.assertEqual(status, 403)
        self.assertNotIn("diagnostics", body)

    def test_identity_budget_and_port_errors_do_not_overlocate_or_write(self):
        bad_id = draft(); bad_id["nodes"][1]["id"] = "../../file"
        duplicate = draft(); duplicate["nodes"].append(deepcopy(duplicate["nodes"][1]))
        budget = draft(); budget["nodes"] *= 43
        port = draft(); port["edges"][0]["target"]["portId"] = "nonexistent"
        field = draft(); field["nodes"][1]["source"] = "import torch"
        before = file_hashes(self.root)
        for bad in (bad_id, duplicate, budget, port, field):
            for path, payload in [("/api/authoring/validate", {"draft": bad}),
                                  ("/api/authoring/generate", {"draft": bad}),
                                  ("/api/authoring/drafts/draft-abcd", {"draft": bad, "expectedRevision": 0})]:
                with self.subTest(path=path):
                    status, body, _ = self.post(path, payload)
                    self.assertEqual(status, 400)
                    self.assertEqual(len(body["diagnostics"]), 1)
                    for target in ("nodeId", "parameter", "portId"):
                        self.assertNotIn(target, body["diagnostics"][0])
                    self.assertEqual(file_hashes(self.root), before)

    def test_injection_label_is_json_data_and_generation_never_adds_it_to_source(self):
        crafted = draft()
        label = "<script>throw new Error('unsafe')</script>'); __import__('os').system('false')"
        crafted["nodes"][1]["label"] = label
        crafted["nodes"][1]["parameters"]["in_features"] = 12
        before = file_hashes(self.root)
        status, body, headers = self.post("/api/authoring/generate", {"draft": crafted})
        self.assertEqual(status, 400)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertTrue(body["error"].startswith(label))
        self.assertNotIn(label, body["diagnostics"][0]["message"])
        self.assertEqual(body["diagnostics"][0]["nodeId"], "linear")
        crafted["nodes"][1]["parameters"]["in_features"] = 16
        status, body, _ = self.post("/api/authoring/generate", {"draft": crafted})
        self.assertEqual(status, 200)
        self.assertNotIn(label, body["source"])
        self.assertEqual(body["verification"]["modelExecution"], "not_run")
        self.assertEqual(file_hashes(self.root), before)


if __name__ == "__main__":
    unittest.main()
