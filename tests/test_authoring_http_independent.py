"""Independent HTTP/CAS/source separation acceptance for authored drafts.

Expected graphs and write boundaries are handwritten. Tests do not call the
authoring verifier, execute a model, issue source approvals, or use Studio UI.
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

from archcanvas_cli.drafts import DraftStore
from archcanvas_cli.server import ArchCanvasServer, DocumentStore
from archcanvas_python import analyze_source


SOURCE = """from torch import nn
class Imported(nn.Module):
    def __init__(self):
        super().__init__()
        self.keep = nn.Linear(4, 3)
    def forward(self, x):
        return self.keep(x)
"""


def authored(identity="draft-a1b2"):
    return {"schemaVersion": 1, "mode": "authored-draft", "id": identity, "title": "独立建模", "revision": 0,
            "nodes": [{"id": "features", "kind": "Input", "label": "输入", "parameters": {"shape": [2, 4], "dtype": "float32"}, "position": {"x": 10, "y": 10}},
                      {"id": "linear", "kind": "Linear", "label": "投影", "parameters": {"in_features": 4, "out_features": 3, "bias": False}, "position": {"x": 10, "y": 100}},
                      {"id": "out", "kind": "Output", "label": "输出", "parameters": {}, "position": {"x": 10, "y": 200}}],
            "edges": [{"id": "e1", "source": {"nodeId": "features", "portId": "output"}, "target": {"nodeId": "linear", "portId": "input"}},
                      {"id": "e2", "source": {"nodeId": "linear", "portId": "output"}, "target": {"nodeId": "out", "portId": "input"}}]}


def canvas(architecture, identity="canvas-independent-import"):
    return {"schemaVersion": 1, "id": identity, "title": "Imported original", "revision": 0,
            "sourceBindingDigest": architecture["sourceDigest"], "architecture": architecture,
            "displayAliases": {}, "nodeStyleOverrides": {}, "edgeStyleOverrides": {}, "legendItems": [],
            "annotations": [], "pageSpec": {"widthMm": 180, "background": "#ffffff", "preset": "paper"},
            "expandedIds": [], "layout": {}, "layoutByFrontier": {}, "pinnedObjects": []}


def file_hashes(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob("*") if p.is_file()}


class IndependentAuthoringHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="archcanvas-authoring-independent-")
        self.root = Path(self.temporary.name)
        try:
            self.server = ArchCanvasServer(("127.0.0.1", 0), data_dir=self.root, studio_dir=self.root / "not-built")
        except PermissionError:
            self.temporary.cleanup()
            self.skipTest("Loopback socket creation is unavailable in this sandbox; run the HTTP suite in the permitted host.")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.client = build_opener(ProxyHandler({}))
        status, session = self.request("/api/session")
        self.assertEqual(status, 200)
        self.token = session["token"]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def request(self, path, method="GET", payload=None, token=None, headers=None):
        request = Request(self.url + path, data=json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None,
                          method=method, headers={"Content-Type": "application/json",
                          **({"X-ArchCanvas-Session": token} if token else {}), **(headers or {})})
        try:
            with self.client.open(request, timeout=15) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def post(self, path, payload):
        return self.request(path, "POST", payload, self.token)

    def test_mutations_require_session_and_reject_nonlocal_origin_without_writes(self):
        draft = authored()
        before = file_hashes(self.root)
        for path, payload in [("/api/authoring/validate", {"draft": draft}), ("/api/authoring/generate", {"draft": draft}),
                              ("/api/authoring/drafts/" + draft["id"], {"draft": draft, "expectedRevision": 0})]:
            self.assertEqual(self.request(path, "POST", payload)[0], 403)
            self.assertEqual(self.request(path, "POST", payload, "invalid-token")[0], 403)
            self.assertEqual(self.request(path, "POST", payload, self.token, {"Origin": "https://foreign.example"})[0], 403)
        self.assertEqual(file_hashes(self.root), before)

    def test_draft_cas_reopens_actual_parameters_bindings_positions_and_stale_bytes_survive(self):
        draft = authored()
        status, first = self.post("/api/authoring/drafts/" + draft["id"], {"draft": draft, "expectedRevision": 0})
        self.assertEqual((status, first["revision"]), (200, 1))
        self.assertEqual(first["draft"], draft)
        changed = deepcopy(draft)
        changed["revision"] = 1
        changed["nodes"][1]["parameters"]["out_features"] = 7
        changed["nodes"][1]["position"] = {"x": -40, "y": 155}
        changed["title"] = "保存的真实草稿"
        status, second = self.post("/api/authoring/drafts/" + draft["id"], {"draft": changed, "expectedRevision": 1})
        self.assertEqual((status, second["revision"]), (200, 2))
        saved_bytes = (self.root / "drafts" / (draft["id"] + ".json")).read_bytes()
        status, conflict = self.post("/api/authoring/drafts/" + draft["id"], {"draft": draft, "expectedRevision": 1})
        self.assertEqual((status, conflict["revision"]), (409, 2))
        self.assertEqual((self.root / "drafts" / (draft["id"] + ".json")).read_bytes(), saved_bytes)
        self.assertEqual(self.request("/api/authoring/drafts/" + draft["id"]), (200, second))
        self.assertEqual(DraftStore(self.root / "drafts").get(draft["id"]), second)
        for bad_revision in [True, -1, 1.5]:
            self.assertEqual(self.post("/api/authoring/drafts/" + draft["id"], {"draft": changed, "expectedRevision": bad_revision})[0], 400)
        self.assertEqual((self.root / "drafts" / (draft["id"] + ".json")).read_bytes(), saved_bytes)

    def test_incomplete_draft_is_saved_but_cannot_generate_or_secretly_register(self):
        draft = authored()
        draft["nodes"], draft["edges"] = [], []
        status, checked = self.post("/api/authoring/validate", {"draft": draft})
        self.assertEqual(status, 200)
        self.assertFalse(checked["complete"])
        self.assertTrue(checked["issues"])
        self.assertEqual(self.post("/api/authoring/drafts/" + draft["id"], {"draft": draft, "expectedRevision": 0})[0], 200)
        before = file_hashes(self.root)
        self.assertEqual(self.post("/api/authoring/generate", {"draft": draft})[0], 400)
        self.assertEqual(file_hashes(self.root), before)

    def test_two_concurrent_http_clients_one_cas_wins_without_combining_graphs(self):
        first, second = authored("draft-cafe"), authored("draft-cafe")
        first["title"], second["title"] = "first complete snapshot", "second complete snapshot"
        second["nodes"][1]["parameters"]["out_features"] = 8
        start = threading.Barrier(2)
        results = []

        def save(draft):
            start.wait()
            status, receipt = self.post("/api/authoring/drafts/" + draft["id"], {"draft": draft, "expectedRevision": 0})
            results.append((status, receipt))

        threads = [threading.Thread(target=save, args=(value,)) for value in [first, second]]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertCountEqual([status for status, _ in results], [200, 409])
        winner = next(receipt for status, receipt in results if status == 200)
        self.assertEqual(self.request("/api/authoring/drafts/draft-cafe"), (200, winner))
        self.assertIn(winner["draft"], [first, second])

    def test_reopen_through_new_server_instance_preserves_draft_identity_and_revision(self):
        draft = authored("draft-beef")
        status, saved = self.post("/api/authoring/drafts/" + draft["id"], {"draft": draft, "expectedRevision": 0})
        self.assertEqual(status, 200)
        prior_url = self.url
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.server = ArchCanvasServer(("127.0.0.1", 0), data_dir=self.root, studio_dir=self.root / "not-built")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.assertEqual(self.request("/api/authoring/drafts/" + draft["id"]), (200, saved))
        # A previous service's mutation token is not reused after restart.
        self.assertEqual(self.post("/api/authoring/drafts/" + draft["id"], {"draft": draft, "expectedRevision": 1})[0], 403)
        self.assertEqual(self.request("/api/authoring/drafts/" + draft["id"]), (200, saved))

    def test_source_document_and_draft_are_disjoint_and_source_facts_remain_immutable(self):
        architecture = analyze_source(SOURCE, "Imported")
        document = canvas(architecture)
        status, saved = self.request("/api/documents/" + document["id"], "PUT", {"document": document, "expectedRevision": 0})
        self.assertEqual(status, 200)
        draft = authored()
        self.assertEqual(self.post("/api/authoring/drafts/" + draft["id"], {"draft": draft, "expectedRevision": 0})[0], 200)
        before = file_hashes(self.root)
        for path in ["/api/authoring/validate", "/api/authoring/generate"]:
            self.assertEqual(self.post(path, {"draft": document})[0], 400)
        self.assertEqual(self.post("/api/authoring/drafts/" + draft["id"], {"draft": document, "expectedRevision": 1})[0], 400)
        self.assertEqual(self.request("/api/documents/" + document["id"], "PUT", {"document": draft, "expectedRevision": 1})[0], 400)
        fake = deepcopy(document)
        fake["architecture"]["nodes"][0]["label"] = "forged source identity"
        self.assertEqual(self.request("/api/documents/" + document["id"], "PUT", {"document": fake, "expectedRevision": 1})[0], 400)
        self.assertEqual(file_hashes(self.root), before)
        self.assertEqual(DocumentStore(self.root / "documents").get(document["id"]), saved)
        self.assertEqual(self.post("/api/authoring/drafts/draft-dead", {"draft": draft, "expectedRevision": 0})[0], 400)
        self.assertEqual(self.post("/api/authoring/drafts/../outside", {"draft": draft, "expectedRevision": 0})[0], 400)

    def test_generation_and_new_registration_do_not_touch_imported_original_copy_or_pending_review(self):
        original = self.root / "imported-original"
        original.mkdir()
        (original / "model.py").write_text(SOURCE)
        architecture = analyze_source(SOURCE, "Imported")
        status, imported = self.post("/api/projects", {"entry": architecture["entry"], "sources": architecture["sources"],
                                                      "sourceDigest": architecture["sourceDigest"], "irDigest": architecture["irDigest"]})
        self.assertEqual(status, 201)
        imported_root = self.root / "projects" / imported["id"]
        pending = self.root / "transactions" / "independent-pending-review.json"
        pending.write_text('{"status":"ReviewReady","immutable":"sentinel"}\n')
        originals_before, copy_before, pending_before = file_hashes(original), file_hashes(imported_root), pending.read_bytes()
        before = file_hashes(self.root)
        draft = authored()
        for extra in [{"projectId": imported["id"]}, {"sourceRoot": str(original)}]:
            self.assertEqual(self.post("/api/authoring/generate", {"draft": draft, **extra})[0], 400)
        status, generated = self.post("/api/authoring/generate", {"draft": draft})
        self.assertEqual(status, 200)
        self.assertEqual(file_hashes(self.root), before, "generation must be text-only")
        observed = analyze_source(generated["source"], generated["entry"])
        self.assertEqual(observed, generated["architecture"])
        linear = [n for n in observed["nodes"] if n["kind"] == "Linear"]
        self.assertEqual(len(linear), 1)
        self.assertEqual({k: linear[0]["parameters"][k] for k in ["in_features", "out_features", "bias"]}, {"in_features": 4, "out_features": 3, "bias": False})
        status, new_project = self.post("/api/projects", {"entry": observed["entry"], "sources": observed["sources"],
                                                         "sourceDigest": observed["sourceDigest"], "irDigest": observed["irDigest"]})
        self.assertEqual(status, 201)
        self.assertNotEqual(new_project["id"], imported["id"])
        self.assertEqual(new_project["architecture"], observed)
        self.assertEqual((self.root / "projects" / new_project["id"] / "source/model.py").read_text(), generated["source"])
        self.assertEqual(file_hashes(original), originals_before)
        self.assertEqual(file_hashes(imported_root), copy_before)
        self.assertEqual(pending.read_bytes(), pending_before)
        self.assertEqual(self.request("/api/projects/" + imported["id"])[1]["architecture"], architecture)
        newer = deepcopy(draft)
        newer["revision"] = 1
        newer["nodes"][1]["parameters"]["out_features"] = 5
        status, regeneration = self.post("/api/authoring/generate", {"draft": newer})
        self.assertEqual(status, 200)
        self.assertNotEqual(regeneration["source"], generated["source"])
        self.assertNotEqual(regeneration["draftDigest"], generated["draftDigest"])
        self.assertNotEqual(regeneration["architecture"]["irDigest"], generated["architecture"]["irDigest"])
        self.assertEqual(file_hashes(imported_root), copy_before)
        self.assertEqual(pending.read_bytes(), pending_before)


if __name__ == "__main__":
    unittest.main()
