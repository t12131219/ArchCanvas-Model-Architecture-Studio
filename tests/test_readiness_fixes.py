"""Audit counterexamples and complete nonexecuting CLI→HTTP canvas workflow."""
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener

from archcanvas_cli.server import ArchCanvasServer
from archcanvas_cli.doctor import diagnose
from archcanvas_python import analyze_source

ROOT = Path(__file__).resolve().parents[1]
SOURCE = '''from torch import nn
class Network(nn.Module):
 def __init__(self):
  super().__init__(); self.fc=nn.Linear(4,2)
 def forward(self,x): return self.fc(x)
raise RuntimeError("User model must never execute")
'''


class ReadinessFixes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="archcanvas-readiness-")
        self.root = Path(self.temp.name)
        self.servers = []
        self.client = build_opener(ProxyHandler({}))

    def tearDown(self):
        for server, thread in self.servers:
            server.shutdown(); server.server_close(); thread.join(2)
        self.temp.cleanup()

    def service(self, name):
        server = ArchCanvasServer(("127.0.0.1", 0), data_dir=self.root / name)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.servers.append((server, thread))
        return server, f"http://127.0.0.1:{server.server_address[1]}"

    def call(self, url, path, payload=None):
        token = json.load(self.client.open(url + "/api/session"))["token"]
        request = Request(url + path, data=json.dumps(payload).encode() if payload is not None else None,
                          headers={"Content-Type": "application/json", "X-ArchCanvas-Session": token})
        with self.client.open(request) as response: return json.load(response)

    def cli(self, *args):
        result = subprocess.run([sys.executable, "-I", "-B", "-c",
            "import sys;sys.path.insert(0,sys.argv.pop(1));from archcanvas_cli.__main__ import main;raise SystemExit(main())",
            str(ROOT / "src"), *args], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_sibling_state_roots_isolate_projects_drafts_exports_transactions_and_documents(self):
        alpha, a = self.service("alpha-documents"); beta, b = self.service("beta-documents")
        arch = analyze_source(SOURCE, "model:Network")
        opened = self.call(a, "/api/open", {"architecture": arch})
        with self.assertRaises(HTTPError) as caught: self.call(b, "/api/documents/" + opened["documentId"])
        self.assertEqual(caught.exception.code, 404)
        from tests.test_authoring_http_independent import authored
        alpha.drafts.put("draft-a1b2", authored(), 0)
        self.assertIsNone(beta.drafts.get("draft-a1b2"))
        for store in ("projects", "drafts", "exports", "transactions", "documents"):
            self.assertNotEqual((alpha.state_root / store).resolve(), (beta.state_root / store).resolve())
        self.assertFalse(list((beta.state_root / "projects").iterdir()))

    def test_cli_open_exact_document_apply_undo_reopen_export_and_stale_conflict(self):
        server, url = self.service("workflow")
        source = self.root / "model.py"; source.write_text(SOURCE)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        opened = self.cli("open", "--source", str(source), "--entry", "Network", "--server", url)
        identity = opened["documentId"]
        self.assertIn("?documentId=" + identity, opened["url"])
        self.assertEqual(opened["sessionId"], identity)
        read = self.cli("session", "read", "--document-id", identity, "--server", url)
        target = next(node["id"] for node in read["document"]["architecture"]["nodes"] if node["kind"] == "Linear")
        operations = self.root / "ops.json"; operations.write_text(json.dumps([{"type": "alias", "id": target, "label": "Projection edited"}, {"type": "nodeStyle", "id": target, "style": {"fill": "#abcdef"}}]))
        changed = self.cli("session", "apply", "--document-id", identity, "--server", url, "--expected-revision", "1", "--visual-revision", "0", "--operations", str(operations))
        self.assertEqual(changed["document"]["displayAliases"][target], "Projection edited")
        self.assertEqual(len(changed["history"]["past"]), 1)
        path = "/api/canvas-sessions/" + identity
        with self.assertRaises(HTTPError) as stale: self.call(url, path + "/undo", {"expectedRevision": 1, "visualRevision": 0})
        self.assertEqual(stale.exception.code, 409)
        with self.assertRaises(HTTPError): self.call(url, path + "/apply", {"expectedRevision": 2, "visualRevision": 1,
            "operations": [{"type": "alias", "id": target, "label": "discard this"}, {"type": "deleteSource", "id": target}]})
        self.assertEqual(self.call(url, path), changed, "invalid batch never publishes its first operation")
        undone = self.cli("session", "undo", "--document-id", identity, "--server", url, "--expected-revision", "2", "--visual-revision", "1")
        self.assertNotIn(target, undone["document"]["displayAliases"])
        server.shutdown(); server.server_close(); self.servers.pop()[1].join(2)
        restarted, url = self.service("workflow")
        read = self.call(url, path); self.assertEqual(read, undone)
        redone = self.call(url, path + "/redo", {"expectedRevision": 3, "visualRevision": 2})
        self.assertEqual(redone["document"]["displayAliases"][target], "Projection edited")
        exported = self.cli("session", "export", "--document-id", identity, "--server", url, "--expected-revision", "4", "--visual-revision", "3", "--format", "svg")
        self.assertEqual(exported["receipt"]["documentId"], identity)
        self.assertEqual(exported["receipt"]["revision"], 3)
        svg = self.client.open(url + exported["url"]).read()
        self.assertIn(b"Projection edited", svg)
        self.assertEqual(hashlib.sha256(svg).hexdigest(), exported["receipt"]["outputDigest"])
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)
        self.assertEqual(diagnose()["catalog"], {"atomicModules": 74, "presets": 23})

    def test_receipt_directory_failure_preserves_previous_export_then_success_commits_pair(self):
        from archcanvas_cli.canvas import canvas_operation
        document = canvas_operation(ROOT, {"action": "create", "architecture": analyze_source(SOURCE, "model:Network")})["document"]
        data = self.root / "document.json"; data.write_text(json.dumps(document))
        output = self.root / "figure.svg"; output.write_bytes(b"previous-valid-artifact")
        receipt = self.root / "figure.svg.receipt.json"; receipt.mkdir()
        command = ["node", str(ROOT / "scripts/export_canvas.mjs"), "--document", str(data), "--output", str(output), "--python", sys.executable]
        failed = subprocess.run(command, capture_output=True, text=True, timeout=60)
        self.assertEqual(failed.returncode, 2)
        self.assertEqual(output.read_bytes(), b"previous-valid-artifact")
        self.assertTrue(receipt.is_dir())
        self.assertEqual(list(self.root.glob(".figure.svg-stage-*")), [])
        receipt.rmdir()
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = json.loads(receipt.read_text())
        self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), actual["outputDigest"])
