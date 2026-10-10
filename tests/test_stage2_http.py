"""End-to-end HTTP boundaries, managed-copy transactions and persistent exports.

These tests use their own small source model and temporary workspace. Source
expectations come from authored text; no prototype or analyzer output snapshot
supplies expected replacements. Run with the project publication environment.
"""

import copy
import hashlib
import json
import re
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from archcanvas_cli.server import ArchCanvasServer
from archcanvas_publication import capabilities as publication_capabilities
from archcanvas_python import analyze_project


SOURCE = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.dropout = nn.Dropout(0.1)  # keep this 0.1 comment
    def forward(self, features):
        return self.dropout(features)
'''


def visual_document(architecture, width=180):
    root = next(node for node in architecture["nodes"] if not node.get("parentId"))
    model_input = next(node for node in architecture["nodes"] if node["kind"] == "Input")
    return {
        "schemaVersion": 1, "id": "canvas-http-stage2", "title": "CURRENT edited source figure", "revision": 9,
        "sourceBindingDigest": architecture["sourceDigest"], "architecture": copy.deepcopy(architecture),
        "displayAliases": {model_input["id"]: "CURRENT feature alias"}, "nodeStyleOverrides": {}, "edgeStyleOverrides": {},
        "legendItems": [{"id": "manual", "label": "CURRENT manual legend", "color": "#345678", "glyph": "module"}],
        "annotations": [{"id": "annotation", "text": "CURRENT note", "x": 50, "y": 400}],
        "pageSpec": {"widthMm": width, "background": "#ffffff", "preset": "paper"},
        "expandedIds": [root["id"]], "layout": {}, "layoutByFrontier": {}, "pinnedObjects": [],
    }


class Stage2HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="archcanvas-http-stage2-", dir="/tmp")
        self.workspace = Path(self.temporary.name)
        self.original_root = self.workspace / "original"
        self.original_root.mkdir()
        self.original_path = self.original_root / "model.py"
        self.original_path.write_bytes(SOURCE.encode())
        self.before = analyze_project(self.original_root, "model:Model")
        try:
            # ``data_dir`` is the complete state root. Documents, projects,
            # drafts, exports and transactions are all isolated beneath it.
            self.server = ArchCanvasServer(("127.0.0.1", 0), data_dir=self.workspace / "managed", studio_dir=self.workspace / "dist")
        except PermissionError:
            self.temporary.cleanup()
            self.skipTest("The execution sandbox forbids loopback sockets; run these HTTP tests in an allowed local host.")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.client = build_opener(ProxyHandler({}))
        status, session = self.json_request("/api/session")
        self.assertEqual(status, 200)
        self.token = session["token"]

    def tearDown(self):
        if hasattr(self, "server"):
            self.server.shutdown()
            self.server.server_close()
            self.thread.join()
        self.temporary.cleanup()

    def request(self, path, method="GET", payload=None, *, session=True, extra_headers=None):
        headers = {"Content-Type": "application/json"}
        if method == "POST" and session:
            headers["X-ArchCanvas-Session"] = self.token
        headers.update(extra_headers or {})
        request = Request(self.url + path, data=json.dumps(payload).encode() if payload is not None else None, method=method, headers=headers)
        try:
            with self.client.open(request, timeout=30) as response:
                return response.status, response.read(), dict(response.headers)
        except HTTPError as exc:
            return exc.code, exc.read(), dict(exc.headers)

    def json_request(self, *args, **kwargs):
        status, body, _ = self.request(*args, **kwargs)
        return status, json.loads(body)

    def registration(self):
        return {key: self.before[key] for key in ("entry", "sources", "sourceDigest", "irDigest")}

    def register(self):
        status, project = self.json_request("/api/projects", "POST", self.registration())
        self.assertEqual(status, 201, project)
        self.assertEqual(project["scope"], "managed-copy")
        self.assertEqual(project["sourceDigest"], self.before["sourceDigest"])
        return project

    def prepare(self, project, value=0.2):
        selected = next(node for node in project["architecture"]["nodes"] if node["kind"] == "Dropout")
        payload = {"nodeId": selected["id"], "parameter": "p", "value": value, "baseSourceDigest": project["sourceDigest"], "baseIrDigest": project["irDigest"]}
        status, receipt = self.json_request(f"/api/projects/{project['id']}/transactions", "POST", payload)
        self.assertEqual(status, 200, receipt)
        self.assertEqual(receipt["status"], "ReviewReady", receipt.get("blockers"))
        return receipt

    def transaction_action(self, project, receipt, action, payload):
        return self.json_request(f"/api/projects/{project['id']}/transactions/{receipt['id']}/{action}", "POST", payload)

    def test_registered_managed_copy_review_approve_commit_and_reanalysis(self):
        project = self.register()
        receipt = self.prepare(project)
        managed = self.server.workspace.source_root(project["id"]) / "model.py"
        self.assertEqual(managed.read_bytes(), SOURCE.encode())
        self.assertEqual(self.original_path.read_bytes(), SOURCE.encode())
        self.assertIn("nn.Dropout(0.2)", receipt["diff"])
        self.assertNotIn("approvalId", receipt)
        status, rejected = self.transaction_action(project, receipt, "commit", {"approvalId": "not approved"})
        self.assertEqual(status, 400, rejected)
        status, rejected = self.transaction_action(project, receipt, "approve", {"reviewDigest": "0" * 64})
        self.assertEqual(status, 400, rejected)
        status, approved = self.transaction_action(project, receipt, "approve", {"reviewDigest": receipt["reviewDigest"]})
        self.assertEqual((status, approved["status"]), (200, "Approved"))
        status, committed = self.transaction_action(project, receipt, "commit", {"approvalId": approved["approvalId"]})
        self.assertEqual((status, committed["status"]), (200, "Committed"))
        expected = SOURCE.replace("nn.Dropout(0.1)", "nn.Dropout(0.2)").encode()
        self.assertEqual(managed.read_bytes(), expected)
        self.assertEqual(self.original_path.read_bytes(), SOURCE.encode())
        status, current = self.json_request(f"/api/projects/{project['id']}")
        self.assertEqual(status, 200)
        self.assertNotEqual(current["sourceDigest"], project["sourceDigest"])
        self.assertEqual(current["sourceDigest"], committed["committedArchitecture"]["sourceDigest"])
        self.assertEqual(next(node for node in current["architecture"]["nodes"] if node["kind"] == "Dropout")["parameters"]["p"], 0.2)
        self.assertEqual(current["architecture"]["sources"][0]["content"], expected.decode())
        status, fetched = self.json_request(f"/api/projects/{project['id']}/transactions/{receipt['id']}")
        self.assertEqual((status, fetched["status"]), (200, "Committed"))
        self.assertEqual(self.transaction_action(project, receipt, "commit", {"approvalId": approved["approvalId"]})[0], 400)

    def test_sessions_origins_registration_digests_paths_and_transaction_scope(self):
        for headers in ({}, {"X-ArchCanvas-Session": "wrong"}):
            status, _ = self.json_request("/api/projects", "POST", self.registration(), session=False, extra_headers=headers)
            self.assertEqual(status, 403)
        for endpoint in ("/api/projects", "/api/exports"):
            self.assertEqual(self.json_request(endpoint, "POST", {}, session=False)[0], 403)
        self.assertEqual(self.json_request("/api/session", extra_headers={"Origin": "https://external.example"})[0], 403)
        invalid_payloads = []
        root_payload = self.registration() | {"root": str(self.original_root)}
        invalid_payloads.append(root_payload)
        for field in ("sourceDigest", "irDigest"):
            invalid_payloads.append(self.registration() | {field: "0" * 64})
        for logical in ("../model.py", "/tmp/model.py", "sub\\model.py"):
            payload = copy.deepcopy(self.registration())
            payload["sources"][0]["path"] = logical
            invalid_payloads.append(payload)
        bad_source = copy.deepcopy(self.registration())
        bad_source["sources"][0]["content"] += "# changed client content\n"
        invalid_payloads.append(bad_source)
        for payload in invalid_payloads:
            status, result = self.json_request("/api/projects", "POST", payload)
            self.assertEqual(status, 400, result)
        self.assertEqual(list((self.workspace / "managed" / "projects").iterdir()), [])
        one = self.register()
        two = self.register()
        receipt = self.prepare(one)
        self.assertEqual(self.transaction_action(two, receipt, "approve", {"reviewDigest": receipt["reviewDigest"]})[0], 400)
        self.assertEqual(self.json_request(f"/api/projects/{one['id']}/transactions/{receipt['id']}/discard", "POST", {}, session=False)[0], 403)
        self.assertEqual(self.json_request("/api/projects/%2e%2e")[0], 400)
        self.assertEqual(self.json_request(f"/api/projects/{one['id']}/transactions/%2e%2e")[0], 400)
        status, discarded = self.transaction_action(one, receipt, "discard", {})
        self.assertEqual((status, discarded["status"]), (200, "Discarded"))
        self.assertEqual(self.original_path.read_bytes(), SOURCE.encode())

    def test_stale_digest_and_staged_tamper_reject_commit_without_source_overwrite(self):
        project = self.register()
        selected = next(node for node in project["architecture"]["nodes"] if node["kind"] == "Dropout")
        payload = {"nodeId": selected["id"], "parameter": "p", "value": 0.2, "baseSourceDigest": "0" * 64, "baseIrDigest": project["irDigest"]}
        self.assertEqual(self.json_request(f"/api/projects/{project['id']}/transactions", "POST", payload)[0], 409)
        receipt = self.prepare(project)
        status, approved = self.transaction_action(project, receipt, "approve", {"reviewDigest": receipt["reviewDigest"]})
        self.assertEqual(status, 200)
        staged = self.workspace / "managed" / "transactions" / receipt["id"] / "staged" / "model.py"
        staged.write_bytes(staged.read_bytes().replace(b"nn.Dropout(0.2)", b"nn.Dropout(0.8)"))
        status, blocked = self.transaction_action(project, receipt, "commit", {"approvalId": approved["approvalId"]})
        self.assertEqual((status, blocked["status"]), (200, "Stale"))
        self.assertEqual((self.server.workspace.source_root(project["id"]) / "model.py").read_bytes(), SOURCE.encode())
        self.assertEqual(self.original_path.read_bytes(), SOURCE.encode())

    def test_modified_managed_source_invalidates_approval_and_get_reanalyzes(self):
        project = self.register()
        receipt = self.prepare(project)
        status, approved = self.transaction_action(project, receipt, "approve", {"reviewDigest": receipt["reviewDigest"]})
        self.assertEqual(status, 200)
        managed = self.server.workspace.source_root(project["id"]) / "model.py"
        updated = b"# later local editor\n" + SOURCE.encode()
        managed.write_bytes(updated)
        status, blocked = self.transaction_action(project, receipt, "commit", {"approvalId": approved["approvalId"]})
        self.assertEqual((status, blocked["status"]), (200, "Stale"))
        self.assertEqual(managed.read_bytes(), updated)
        status, current = self.json_request(f"/api/projects/{project['id']}")
        self.assertEqual(status, 200)
        self.assertNotEqual(current["sourceDigest"], project["sourceDigest"])
        self.assertEqual(current["irDigest"], project["irDigest"])
        self.assertEqual(self.original_path.read_bytes(), SOURCE.encode())

    @unittest.skipUnless(publication_capabilities()["png"] and publication_capabilities()["pdf"], "Project-local publication converter is unavailable")
    def test_export_current_document_persists_real_png_pdf_and_bound_receipts(self):
        original_bytes = self.original_path.read_bytes()
        for width, format in ((85, "png"), (180, "pdf"), (180, "svg")):
            canvas = visual_document(self.before, width)
            status, artifact = self.json_request("/api/exports", "POST", {"document": canvas, "format": format, "dpi": 300})
            self.assertEqual(status, 201, artifact)
            receipt = artifact["receipt"]
            self.assertEqual(receipt["documentId"], canvas["id"])
            self.assertEqual(receipt["revision"], 9)
            self.assertEqual(receipt["sourceDigest"], self.before["sourceDigest"])
            self.assertEqual(receipt["irDigest"], self.before["irDigest"])
            self.assertEqual(receipt["widthMm"], width)
            self.assertTrue(receipt["geometryVerified"])
            status, body, headers = self.request(artifact["url"])
            self.assertEqual(status, 200)
            self.assertEqual(hashlib.sha256(body).hexdigest(), receipt["outputDigest"])
            self.assertEqual(headers["Content-Type"], {"png": "image/png", "pdf": "application/pdf", "svg": "image/svg+xml"}[format])
            stored = self.workspace / "managed" / "exports" / artifact["id"] / f"figure.{format}"
            self.assertEqual(stored.read_bytes(), body)
            status, reread = self.json_request(artifact["receiptUrl"])
            self.assertEqual((status, reread), (200, receipt))
            if format == "png":
                self.assertEqual(body[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(struct.unpack(">II", body[16:24])[0], 1004)
            elif format == "pdf":
                self.assertTrue(body.startswith(b"%PDF-"))
                values = [float(item) for item in re.search(rb"/MediaBox\s*\[([^\]]+)\]", body).group(1).split()]
                self.assertAlmostEqual(values[2] - values[0], 180 / 25.4 * 72, delta=0.01)
            else:
                self.assertIn(b"CURRENT feature alias", body)
                self.assertIn(b"CURRENT manual legend", body)
                self.assertIn(b"CURRENT note", body)
                self.assertNotIn(b"data-expand-id", body)
        self.assertEqual(self.original_path.read_bytes(), original_bytes)
        self.assertEqual(self.json_request("/api/exports/%2e%2e/receipt")[0], 400)

    def test_export_document_semantic_field_injection_rejected_by_core(self):
        canvas = visual_document(self.before)
        selected = next(node for node in canvas["architecture"]["nodes"] if node["kind"] == "Dropout")
        canvas["nodeStyleOverrides"][selected["id"]] = {"fill": "#abcdef", "parameters": {"p": 0.9}}
        status, error = self.json_request("/api/exports", "POST", {"document": canvas, "format": "svg", "dpi": 300})
        self.assertEqual(status, 400, error)
        self.assertEqual(list((self.workspace / "managed" / "exports").iterdir()), [])
        self.assertEqual(self.original_path.read_bytes(), SOURCE.encode())


if __name__ == "__main__":
    unittest.main()
