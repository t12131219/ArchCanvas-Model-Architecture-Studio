"""Explicit source edits rebuild unknown nested structures without tensor inference."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from archcanvas_authoring import DraftError
from archcanvas_authoring.source_regions import prepare_source_region, apply_source_region
from archcanvas_python import analyze_source, analyze_project
from tests.test_source_preservation import source_draft, SOURCE
from tests.test_source_surgery import insert


class SourceRegionTests(unittest.TestCase):
    def draft(self):
        return source_draft(analyze_source(SOURCE, "model:Meadow"))

    def branch(self, draft):
        refs = draft["sourceProvenance"]["nodeRefs"]
        return next(node["id"] for node in draft["nodes"] if refs[node["id"]]["kind"] == "SourceBranch")

    def test_prepare_is_exact_full_file_and_noop_edit_retains_all_source_bytes(self):
        draft = self.draft(); before = deepcopy(draft)
        prepared = prepare_source_region(draft, self.branch(draft))
        self.assertEqual(prepared["source"], SOURCE)
        self.assertEqual(prepared["path"], "model.py")
        self.assertGreater(prepared["startLine"], 1)
        self.assertEqual(prepared["verification"]["editUnit"], "complete-python-file")
        result = apply_source_region(draft, prepared["regionId"], prepared["baselineDigest"], prepared["source"])
        self.assertEqual(result["architecture"], draft["sourceProvenance"]["architecture"])
        self.assertFalse(result["verification"]["tensorLowering"])
        self.assertEqual(draft, before)

    def test_unknown_branch_body_can_be_rebuilt_and_independently_reopened(self):
        draft = self.draft(); before = deepcopy(draft)
        prepared = prepare_source_region(draft, self.branch(draft))
        replacement = SOURCE.replace("self.drop=nn.Dropout(0.1)", "self.drop=nn.Dropout(0.1); self.review=nn.Tanh()")
        replacement = replacement.replace("   x=self.head(x)", "   x=self.review(self.head(x))\n  else:\n   x=self.review(x)")
        result = apply_source_region(draft, prepared["regionId"], prepared["baselineDigest"], replacement)
        self.assertEqual(result["source"], replacement)
        self.assertEqual(result["sourceEdit"]["beforeDigest"], hashlib.sha256(SOURCE.encode()).hexdigest())
        self.assertTrue(any(node.get("sourceStructure") and node["label"] == "review" for node in result["architecture"]["nodes"]))
        with tempfile.TemporaryDirectory() as directory:
            for item in result["architecture"]["sources"]:
                path = Path(directory) / item["path"]; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(item["content"])
            self.assertEqual(analyze_project(directory, result["entry"]), result["architecture"])
        self.assertEqual(draft, before)

    def test_pending_supported_graph_and_parameter_changes_are_included(self):
        draft = insert(self.draft())
        drop = next(node for node in draft["nodes"] if draft["sourceProvenance"]["nodeRefs"].get(node["id"], {}).get("kind") == "Dropout")
        drop["parameters"]["p"] = 0.35
        prepared = prepare_source_region(draft, self.branch(draft))
        self.assertIn("nn.Dropout(0.35)", prepared["source"])
        self.assertIn(".Identity()", prepared["source"])
        result = apply_source_region(draft, prepared["regionId"], prepared["baselineDigest"], prepared["source"].replace("if flag:", "if not flag:"))
        self.assertIn(".Identity()", result["source"])
        self.assertIn("nn.Dropout(0.35)", result["source"])
        self.assertIn("if not flag:", result["source"])

    def test_stale_draft_or_digest_is_rejected_without_modification(self):
        draft = self.draft()
        prepared = prepare_source_region(draft, self.branch(draft))
        for digest in ("0" * 64, None):
            with self.assertRaisesRegex(DraftError, "baseline changed"):
                apply_source_region(draft, prepared["regionId"], digest, prepared["source"])
        draft["revision"] += 1
        with self.assertRaisesRegex(DraftError, "baseline changed"):
            apply_source_region(draft, prepared["regionId"], prepared["baselineDigest"], prepared["source"])

    def test_unsupported_pending_deletion_is_not_discarded_behind_source_edit(self):
        draft = self.draft(); selected = self.branch(draft)
        draft["nodes"] = [node for node in draft["nodes"] if node["id"] != selected]
        draft["edges"] = [edge for edge in draft["edges"] if selected not in (edge["source"]["nodeId"], edge["target"]["nodeId"])]
        with self.assertRaisesRegex(DraftError, "Pending draft edits cannot be preserved"):
            prepare_source_region(draft, selected)

    def test_invalid_source_or_missing_entry_is_rejected(self):
        draft = self.draft(); prepared = prepare_source_region(draft, self.branch(draft))
        for replacement in ("", "if broken", SOURCE.replace("class Meadow", "class RemovedEntry")):
            with self.subTest(replacement=replacement):
                with self.assertRaises(DraftError):
                    apply_source_region(draft, prepared["regionId"], prepared["baselineDigest"], replacement)
        with self.assertRaises(DraftError):
            prepare_source_region(draft, "../../etc/passwd")

    def test_nonselected_files_remain_exact_and_top_level_code_is_not_executed(self):
        source = SOURCE.replace("from torch import nn", "from torch import nn\nfrom helper import SENTINEL")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "model.py").write_text(source)
            (root / "helper.py").write_text("SENTINEL = 1\nraise RuntimeError('never execute source')\n")
            draft = source_draft(analyze_project(root, "model:Meadow"))
            prepared = prepare_source_region(draft, self.branch(draft))
            result = apply_source_region(draft, prepared["regionId"], prepared["baselineDigest"], prepared["source"].replace("if flag:", "if not flag:"))
            self.assertEqual(next(item["content"] for item in result["architecture"]["sources"] if item["path"] == "helper.py"),
                             (root / "helper.py").read_text())
            self.assertEqual(result["verification"]["unchangedFiles"], ["helper.py"])

    def test_http_contract_requires_session_and_explicit_digest_then_opens_new_model(self):
        from archcanvas_cli.server import ArchCanvasServer
        draft = self.draft(); region_id = self.branch(draft)
        with tempfile.TemporaryDirectory(prefix="archcanvas-source-region-http-") as directory:
            try:
                server = ArchCanvasServer(("127.0.0.1", 0), data_dir=Path(directory))
            except PermissionError:
                self.skipTest("Loopback socket unavailable in this sandbox; run permitted local HTTP check.")
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            client = build_opener(ProxyHandler({}))
            url = f"http://127.0.0.1:{server.server_address[1]}"
            def request(path, payload=None, token=None):
                req = Request(url + path, data=json.dumps(payload).encode() if payload is not None else None,
                              headers={"Content-Type": "application/json", **({"X-ArchCanvas-Session": token} if token else {})})
                try:
                    response = client.open(req, timeout=30)
                except HTTPError as exc:
                    response = exc
                with response:
                    return response.status, json.loads(response.read())
            try:
                token = request("/api/session")[1]["token"]
                read = "/api/authoring/source-regions/read"; apply = "/api/authoring/source-regions/apply"
                payload = {"draft": draft, "regionId": region_id}
                self.assertEqual(request(read, payload)[0], 403)
                status, prepared = request(read, payload, token)
                self.assertEqual(status, 200, prepared)
                invalid = {**payload, "baselineDigest": "wrong", "replacement": SOURCE}
                self.assertEqual(request(apply, invalid, token)[0], 400)
                status, result = request(apply, {**invalid, "baselineDigest": prepared["baselineDigest"], "replacement": SOURCE.replace("if flag:", "if not flag:")}, token)
                self.assertEqual(status, 200, result)
                self.assertEqual(result["verification"]["scope"], "explicit-source-file-reanalysis")
                self.assertEqual(request("/api/open", {"architecture": result["architecture"]}, token)[0], 201)
                self.assertEqual(request(read, {**payload, "path": "/etc/passwd"}, token)[0], 400)
            finally:
                server.shutdown(); server.server_close(); thread.join()
