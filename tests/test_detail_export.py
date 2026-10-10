"""Real shared-renderer detail CLI/HTTP, scope and physical artifact checks.

Runs with the formal publication venv and permitted loopback sockets. No mocked
converter, socket skips or expected-renderer snapshots supply the assertions.
"""
import copy
import hashlib
import json
import re
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from archcanvas_cli.server import ArchCanvasServer
from archcanvas_python import analyze_project

ROOT = Path(__file__).resolve().parents[1]


def current_document(directory):
    architecture = analyze_project(ROOT / "fixtures/mlp", "model:MLP")
    node = next(item for item in architecture["nodes"] if item["label"] == "network")
    architecture_path = directory / "architecture.json"
    path = directory / "document.json"
    architecture_path.write_text(json.dumps(architecture))
    bootstrap = '''import fs from 'node:fs';
import {createDocument,applyVisualBatch} from './studio/src/core/index.ts';
const a=JSON.parse(fs.readFileSync(process.argv[1]));
const d=applyVisualBatch(createDocument(a),[{type:'expand',id:process.argv[3],expanded:true},{type:'alias',id:process.argv[3],label:'CURRENT detailed MLP'},{type:'legend',items:[{id:'custom',label:'CURRENT legend',color:'#123456',glyph:'module'}]}]);
fs.writeFileSync(process.argv[2],JSON.stringify(d));'''
    completed = subprocess.run(["node", "--experimental-strip-types", "--input-type=module", "-e", bootstrap, str(architecture_path), str(path), node["id"]], cwd=ROOT, capture_output=True, timeout=15)
    if completed.returncode:
        raise AssertionError(completed.stderr.decode())
    return json.loads(path.read_text()), path, node["id"]


class DetailCLITests(unittest.TestCase):
    def test_detail_cli_real_svg_pdf_png_at_85_180_mm_and_bound_scope(self):
        with tempfile.TemporaryDirectory(prefix="archcanvas-detail-cli-", dir="/tmp") as temporary:
            directory = Path(temporary)
            document, path, selected = current_document(directory)
            original = path.read_bytes()
            source_bytes = (ROOT / "fixtures/mlp/model.py").read_bytes()
            scope = None
            preflight = {}
            for width in (85, 180):
                for format in ("svg", "pdf", "png"):
                    output = directory / f"detail-{width}.{format}"
                    completed = subprocess.run(["node", "scripts/export_canvas.mjs", "--document", str(path), "--output", str(output), "--format", format, "--python", sys.executable, "--scope-node", selected, "--width-mm", str(width)], cwd=ROOT, capture_output=True, timeout=30)
                    self.assertEqual(completed.returncode, 0, completed.stderr.decode())
                    data = output.read_bytes()
                    receipt = json.loads(Path(str(output) + ".receipt.json").read_text())
                    self.assertEqual(receipt["outputDigest"], hashlib.sha256(data).hexdigest())
                    self.assertEqual(receipt["documentId"], document["id"])
                    self.assertEqual(receipt["revision"], document["revision"])
                    self.assertEqual(receipt["sourceDigest"], document["architecture"]["sourceDigest"])
                    self.assertEqual(receipt["irDigest"], document["architecture"]["irDigest"])
                    self.assertEqual(receipt["widthMm"], width)
                    self.assertTrue(receipt["geometryVerified"])
                    current = receipt["exportScope"]
                    self.assertEqual(current["selectedNodeId"], selected)
                    self.assertEqual(current["selectedLabel"], "CURRENT detailed MLP")
                    self.assertEqual(len(current["boundaryEdges"]), 3)
                    all_ids = current["internalEdgeIds"] + [edge["edgeId"] for edge in current["boundaryEdges"]] + current["omittedEdgeIds"]
                    self.assertEqual(sorted(all_ids), sorted(edge["id"] for edge in document["architecture"]["edges"]))
                    self.assertEqual(len(all_ids), len(set(all_ids)))
                    if scope is not None:
                        self.assertEqual(current, scope)
                    scope = current
                    preflight[width] = receipt["physicalPreflight"]
                    if format == "svg":
                        parsed = ET.fromstring(data)
                        self.assertEqual(parsed.get("width"), f"{width}mm")
                        ns = {"svg": "http://www.w3.org/2000/svg"}
                        self.assertEqual(json.loads(parsed.find("svg:metadata", ns).text)["exportScope"], current)
                        self.assertIn(b"CURRENT legend", data)
                        self.assertIn(b"FROM features", data)
                        self.assertIn(b"TO output", data)
                        self.assertNotIn(b"data-expand-id", data)
                    elif format == "png":
                        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
                        self.assertEqual(struct.unpack(">II", data[16:24])[0], round(width / 25.4 * 300))
                        self.assertEqual(receipt["fonts"]["glyphCoverage"]["status"], "passed")
                    else:
                        self.assertTrue(data.startswith(b"%PDF-"))
                        box = [float(value) for value in re.search(rb"/MediaBox\s*\[([^\]]+)\]", data).group(1).split()]
                        self.assertAlmostEqual(box[2] - box[0], width / 25.4 * 72, delta=0.01)
                        self.assertAlmostEqual(box[3] - box[1], receipt["heightMm"] / 25.4 * 72, delta=0.01)
            self.assertAlmostEqual(preflight[180]["minTextPt"] / preflight[85]["minTextPt"], 180 / 85)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual((ROOT / "fixtures/mlp/model.py").read_bytes(), source_bytes)


class DetailHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="archcanvas-detail-http-", dir="/tmp")
        self.directory = Path(self.temporary.name)
        self.document, self.path, self.selected = current_document(self.directory)
        self.server = ArchCanvasServer(("127.0.0.1", 0), data_dir=self.directory / "managed", studio_dir=self.directory / "dist")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.client = build_opener(ProxyHandler({}))
        self.token = json.loads(self.request("/api/session")[1])["token"]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def request(self, path, payload=None):
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            headers["X-ArchCanvas-Session"] = self.token
        request = Request(self.url + path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
        try:
            with self.client.open(request, timeout=30) as response:
                return response.status, response.read(), dict(response.headers)
        except HTTPError as exc:
            return exc.code, exc.read(), dict(exc.headers)

    def test_http_detail_equals_cli_shared_scene_and_old_whole_request_still_works(self):
        original = self.path.read_bytes()
        status, body, _ = self.request("/api/exports", {"document": self.document, "format": "svg", "dpi": 300, "options": {"nodeId": self.selected, "widthMm": 85}})
        artifact = json.loads(body)
        self.assertEqual(status, 201, artifact)
        status, svg, headers = self.request(artifact["url"])
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "image/svg+xml")
        output = self.directory / "cli.svg"
        completed = subprocess.run(["node", "scripts/export_canvas.mjs", "--document", str(self.path), "--output", str(output), "--python", sys.executable, "--scope-node", self.selected, "--width-mm", "85"], cwd=ROOT, capture_output=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        self.assertEqual(svg, output.read_bytes())
        receipt = json.loads(Path(str(output) + ".receipt.json").read_text())
        self.assertEqual(artifact["receipt"]["sceneSvgDigest"], receipt["sceneSvgDigest"])
        self.assertEqual(artifact["receipt"]["exportScope"], receipt["exportScope"])
        self.assertEqual(json.loads(self.request(artifact["receiptUrl"])[1]), artifact["receipt"])
        status, body, _ = self.request("/api/exports", {"document": self.document, "format": "svg", "dpi": 300})
        whole = json.loads(body)
        self.assertEqual(status, 201, whole)
        self.assertEqual(whole["receipt"]["exportScope"], {"kind": "document"})
        self.assertEqual(whole["receipt"]["widthMm"], 180)
        self.assertEqual(self.path.read_bytes(), original)

    def test_http_invalid_options_and_collapsed_detail_leave_no_export_artifacts(self):
        for options in ({"unknown": True}, {"widthMm": True}, {"widthMm": 24}, {"widthMm": 1001}, {"widthMm": 10 ** 400}, {"nodeId": ""}, {"nodeId": []}, {"nodeId": "missing"}):
            status, body, _ = self.request("/api/exports", {"document": self.document, "format": "svg", "dpi": 300, "options": options})
            self.assertEqual(status, 400, body)
        collapsed = copy.deepcopy(self.document)
        collapsed["expandedIds"].remove(self.selected)
        status, body, _ = self.request("/api/exports", {"document": collapsed, "format": "svg", "dpi": 300, "options": {"nodeId": self.selected}})
        self.assertEqual(status, 400, body)
        self.assertEqual(list((self.directory / "managed/exports").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
