"""Persistence concurrency and localhost API boundary checks."""

import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from archcanvas_python import analyze_project
from archcanvas_cli.server import ArchCanvasServer, ConflictError, DocumentStore

ROOT = Path(__file__).resolve().parents[1]


def document(identity="canvas-test"):
    architecture = analyze_project(ROOT / "fixtures/mlp", "model:MLP")
    return {"schemaVersion": 1, "id": identity, "title": "Source-backed MLP", "revision": 7, "sourceBindingDigest": architecture["sourceDigest"], "architecture": architecture, "displayAliases": {}, "nodeStyleOverrides": {}, "edgeStyleOverrides": {}, "legendItems": [], "annotations": [], "pageSpec": {"widthMm": 180, "background": "#ffffff", "preset": "paper"}, "expandedIds": [], "layout": {}, "layoutByFrontier": {}, "pinnedObjects": []}


class DocumentStoreTests(unittest.TestCase):
    def test_cas_persists_canvas_without_changing_visual_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            original = document()
            saved = store.put(original["id"], original, 0)
            self.assertEqual(saved["revision"], 1)
            self.assertEqual(saved["document"]["revision"], 7)
            changed = copy.deepcopy(original)
            changed["displayAliases"][original["architecture"]["nodes"][0]["id"]] = "My features"
            changed["revision"] = 8
            with self.assertRaises(ConflictError):
                store.put(original["id"], changed, 0)
            self.assertEqual(store.get(original["id"]), saved)
            updated = store.put(original["id"], changed, 1)
            self.assertEqual(updated["revision"], 2)
            reopened = DocumentStore(Path(directory)).get(original["id"])
            self.assertEqual(reopened["document"], changed)
            tampered = copy.deepcopy(changed)
            tampered["architecture"]["nodes"][0]["label"] = "changed source fact"
            with self.assertRaises(ValueError):
                store.put(original["id"], tampered, 2)
            self.assertEqual(store.get(original["id"]), reopened)

    def test_two_concurrent_clients_one_cas_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            canvas = document()
            results = []
            start = threading.Barrier(2)
            def save():
                start.wait()
                try:
                    results.append(store.put(canvas["id"], canvas, 0)["revision"])
                except ConflictError:
                    results.append("conflict")
            threads = [threading.Thread(target=save) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertCountEqual(results, [1, "conflict"])

    def test_store_path_traversal_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory) / "documents")
            for identity in ("../outside", "a/b", "a\\b", "", "a:b"):
                with self.assertRaises(ValueError):
                    store.get(identity)
            target = Path(directory) / "outside.json"
            target.write_text("{}")
            (store.directory / "linked.json").symlink_to(target)
            with self.assertRaises(ValueError):
                store.get("linked")


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        try:
            self.server = ArchCanvasServer(("127.0.0.1", 0), data_dir=Path(self.directory.name) / "documents", studio_dir=Path(self.directory.name) / "dist")
        except PermissionError:
            self.directory.cleanup()
            self.skipTest("The execution sandbox forbids loopback socket creation; run HTTP contract tests in a permitted host.")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.client = build_opener(ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def request(self, path, method="GET", payload=None, headers=None):
        request = Request(self.url + path, data=json.dumps(payload).encode() if payload is not None else None, method=method, headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with self.client.open(request, timeout=3) as response:
                return response.status, json.loads(response.read()), dict(response.headers)
        except HTTPError as error:
            return error.code, json.loads(error.read()), dict(error.headers)

    def test_examples_capabilities_and_text_only_source_import(self):
        status, result, _ = self.request("/api/capabilities")
        self.assertEqual(status, 200)
        self.assertTrue(result["semanticWriteback"])
        self.assertEqual(result["supportedIntents"], ["set_dropout_probability", "rebind_input"])
        self.assertEqual(result["semanticScope"]["origins"], ["explicit-float-literal"])
        self.assertEqual(result["semanticScope"]["httpCommit"], "managed-workspace-copy-only")
        status, examples, _ = self.request("/api/examples")
        self.assertEqual(status, 200)
        self.assertEqual([example["id"] for example in examples], ["transformer", "mlp", "residual_cnn", "rebind"])
        status, architecture, _ = self.request("/api/examples/transformer")
        self.assertEqual((status, architecture["label"]), (200, "Transformer"))
        status, result, _ = self.request("/api/analyze", "POST", {"source": "from torch import nn\nclass Model(nn.Module):\n def forward(self,x): return x\n", "entry": "Model"})
        self.assertEqual((status, result["entry"]), (200, "model:Model"))
        status, _, _ = self.request("/api/analyze", "POST", {"root": str(ROOT), "source": "", "entry": "Model"})
        self.assertEqual(status, 400)

    def test_save_reload_and_conflict_http(self):
        canvas = document()
        status, saved, _ = self.request("/api/documents/canvas-test", "PUT", {"document": canvas, "expectedRevision": 0})
        self.assertEqual(status, 200)
        self.assertEqual(saved["revision"], 1)
        self.assertEqual(saved["document"]["revision"], 7)
        status, reread, _ = self.request("/api/documents/canvas-test")
        self.assertEqual((status, reread), (200, saved))
        status, error, _ = self.request("/api/documents/canvas-test", "PUT", {"document": canvas, "expectedRevision": 0})
        self.assertEqual((status, error["revision"]), (409, 1))

    def test_exact_localhost_origin_host_and_path_restrictions(self):
        status, _, headers = self.request("/api/capabilities", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "http://localhost:5173")
        for headers in ({"Origin": "https://evil.example"}, {"Origin": "http://localhost:5173.evil.example"}, {"Host": "evil.example"}):
            self.assertEqual(self.request("/api/capabilities", headers=headers)[0], 403)
        self.assertEqual(self.request("/api/documents/%2e%2e%2foutside")[0], 400)
        self.assertEqual(self.request("/../secret")[0], 400)
        self.assertEqual(self.request("/api/examples/../../model.py")[0], 404)

    def test_missing_production_build_reports_gap(self):
        status, result, _ = self.request("/")
        self.assertEqual(status, 503)
        self.assertIn("Studio build is not present", result["error"])


if __name__ == "__main__":
    unittest.main()
