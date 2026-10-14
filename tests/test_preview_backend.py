"""Independent source/HTTP checks for the migrated recursive preview backend.

Fixtures are authored here from Python statements and expected dependencies.
They do not import a prototype module or depend on generated prototype bundles.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

import archcanvas_preview
from archcanvas_preview import AdapterError, analyze, analyze_for_authoring
from archcanvas_cli.server import ArchCanvasServer
from archcanvas_cli.workspace import Workspace
from archcanvas_python import analyze_source
from archcanvas_publication import capabilities as publication_capabilities

PREVIEW_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="10 20 400 200">
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 Z" fill="#334155" /></marker></defs>
<g transform="translate(20 30)"><rect x="10" y="20" width="120" height="55" rx="8" fill="#e0f2fe" stroke="#334155" /><text x="70" y="50" font-size="14" font-family="DejaVu Sans" text-anchor="middle" fill="#0f172a">CURRENT Linear</text></g>
<path d="M 150 75 L 240 75 L 240 120" fill="none" stroke="#334155" stroke-width="2" marker-end="url(#arrow)" />
<rect x="220" y="120" width="130" height="60" rx="8" fill="#fef3c7" stroke="#334155" />
<text x="235" y="155" font-size="14" font-family="DejaVu Sans" fill="#0f172a">CURRENT ReLU</text>
</svg>'''


FILES = {
    "net/ops.py": """from torch import nn
class Pair(nn.Module):
    def forward(self, x, *, skip):
        return {'value': x + skip, 'gate': x * skip}
""",
    "net/model.py": """from torch import nn
from .ops import Pair
class TwinPath(nn.Module):
    def __init__(self, width=12):
        super().__init__()
        self.pair = Pair()
        self.shared = nn.Linear(width, width)
        self.alias = self.shared
        self.tail = nn.Sequential(nn.GELU(), nn.Dropout(0.15))
    def forward(self, x, skip):
        left = self.shared(x)
        right = self.alias(skip)
        values = self.pair(left, skip=right)
        return self.tail(values['value']), values['gate']
""",
}

EDITABLE = """from torch import nn
class Editable(nn.Module):
    def __init__(self):
        super().__init__()
        self.drop = nn.Dropout(0.15)
    def forward(self, x):
        return self.drop(x)
"""


class PreviewSourceTests(unittest.TestCase):
    def test_multifile_composition_shared_identity_and_slot_dependencies(self):
        bundle = analyze(FILES, "TwinPath", {"width": 24})
        self.assertEqual(bundle["entry"], "net.model:TwinPath")
        self.assertEqual(bundle["schema"], "summary-source-adapter/1")
        self.assertEqual(bundle["ir"]["schema"], "summary-source-ir/1")
        self.assertFalse(bundle["ir"]["modelExecuted"])
        self.assertEqual(bundle["diagnostics"], [])
        self.assertEqual(bundle, analyze(FILES, "net.model:TwinPath", {"width": 24}))
        nodes = bundle["ir"]["nodes"]
        self.assertEqual(sum(node["kind"] == "add" for node in nodes), 1)
        self.assertEqual(sum(node["kind"] == "multiply" for node in nodes), 1)
        shared = bundle["ir"]["instances"]["net.model:TwinPath.shared"]
        self.assertEqual(len(shared), 2)
        self.assertTrue(all(next(n for n in nodes if n["id"] == identity)["constructorArgs"] == [24, 24] for identity in shared))
        self.assertTrue(any(node["label"] == "return[value]" for node in nodes))
        self.assertTrue(any(node["label"] == "return[gate]" for node in nodes))
        self.assertTrue(any(node["label"] == "return[0]" for node in nodes))
        self.assertTrue(any(node["label"] == "return[1]" for node in nodes))
        identities = {node["id"] for node in nodes}
        for edge in bundle["ir"]["edges"]:
            self.assertIn(edge["source"], identities)
            self.assertIn(edge["target"], identities)
            self.assertEqual(edge["wire"], edge["source"] + ":out")
        self.assertEqual(hashlib.sha256(bundle["canonicalIR"].encode()).hexdigest(), bundle["irSha256"])
        self.assertEqual(json.loads(bundle["canonicalIR"]), bundle["ir"])
        for evidence in bundle["evidence"].values():
            lines = FILES[evidence["file"]].encode().split(b"\n")
            span = b"\n".join(lines[evidence["line"] - 1:evidence["endLine"]])
            self.assertIn(evidence["expression"].encode(), span)

    def test_source_and_authoring_projection_never_execute_user_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "executed"
            text = f"import torch\nfrom torch import nn\nopen({str(marker)!r}, 'w').write('top-level')\nclass NeverRun(nn.Module):\n    def __init__(self):\n        open({str(marker)!r}, 'w').write('constructor')\n    def forward(self, x):\n        return x + x\n"
            self.assertFalse(analyze({"model.py": text}, "NeverRun")["ir"]["modelExecuted"])
            architecture = analyze_for_authoring({"model.py": text}, "model:NeverRun")
            self.assertEqual(architecture["entry"], "model:NeverRun")
            self.assertFalse(marker.exists())

    def test_dynamic_and_mutating_regions_preserve_whole_source(self):
        for statement in ("if x.sum() > 0:\n            x = x + x", "x.add_(1)"):
            source = "from torch import nn\nclass Region(nn.Module):\n    def forward(self, x):\n        " + statement + "\n        return x * x\n"
            bundle = analyze({"model.py": source}, "Region")
            self.assertEqual(sum(n["kind"] == "opaque" for n in bundle["ir"]["nodes"]), 1)
            self.assertFalse(any(n["kind"] in ("add", "multiply") for n in bundle["ir"]["nodes"]))
            self.assertTrue(any("return x * x" in e["expression"] for e in bundle["evidence"].values()))
            self.assertTrue(bundle["diagnostics"])

    def test_limits_invalid_paths_and_nonfinite_config_are_rejected(self):
        cases = [({"../model.py": EDITABLE}, "Editable", None),
                 ({"/model.py": EDITABLE}, "Editable", None),
                 ({"model.txt": EDITABLE}, "Editable", None),
                 ({"model.py": "#" * 2_000_001}, "Editable", None),
                 ({f"model{i}.py": EDITABLE for i in range(81)}, "Editable", None),
                 ({"model.py": "class"}, "Editable", None),
                 ({"model.py": EDITABLE}, {}, None),
                 ({"model.py": EDITABLE}, "Editable", {"p": math.inf})]
        for files, entry, config in cases:
            with self.subTest(entry=entry, files=len(files)), self.assertRaises(AdapterError):
                analyze(files, entry, config)

    def test_formal_authoring_projection_binds_multifile_sources(self):
        architecture = analyze_for_authoring(FILES, "TwinPath")
        self.assertEqual(architecture["schemaVersion"], 1)
        self.assertEqual(architecture["entry"], "net.model:TwinPath")
        self.assertEqual({source["path"]: source["content"] for source in architecture["sources"]}, FILES)
        for source in architecture["sources"]:
            self.assertEqual(hashlib.sha256(source["content"].encode()).hexdigest(), source["digest"])
        self.assertEqual(analyze_for_authoring({"model.py": EDITABLE}, "Editable"), analyze_source(EDITABLE, "Editable"))

    def test_package_loads_in_isolated_process_without_prototype_path(self):
        package_root = Path(archcanvas_preview.__file__).resolve().parent.parent
        program = "import json,sys;sys.path.insert(0,sys.argv[1]);import archcanvas_preview;from archcanvas_preview.analyze import REGISTRY;print(json.dumps({'path':archcanvas_preview.__file__,'registry':REGISTRY['modules']['Conv1d']}))"
        result = subprocess.run([sys.executable, "-I", "-B", "-c", program, str(package_root)], cwd="/tmp", capture_output=True, text=True, check=True)
        loaded = json.loads(result.stdout)
        self.assertTrue(Path(loaded["path"]).resolve().is_relative_to(package_root))
        self.assertEqual(loaded["registry"], "convolution")

    def test_preview_export_preserves_current_svg_geometry_and_binds_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Workspace(Path(temporary), None)
            binding = {"caseId": "imported-preview", "sourceDigest": "a" * 64, "irDigest": "b" * 64, "revision": 7}
            artifact = workspace.export_preview(PREVIEW_SVG, "svg", 300, 85, binding)
            receipt = artifact["receipt"]
            self.assertEqual(receipt["previewSvgDigest"], hashlib.sha256(PREVIEW_SVG.encode()).hexdigest())
            self.assertEqual(receipt["inputSvgDigest"], receipt["previewSvgDigest"])
            self.assertEqual(receipt["viewBox"], [10.0, 20.0, 400.0, 200.0])
            self.assertEqual((receipt["widthMm"], receipt["heightMm"]), (85, 42.5))
            self.assertEqual(receipt["sourceIdentityOrigin"], "browser-declared-preview-binding")
            self.assertFalse(receipt["sourceBindingVerified"])
            self.assertTrue(receipt["geometryVerified"])
            self.assertEqual({key: receipt[key] for key in binding}, binding)
            svg, mime = workspace.artifact(artifact["id"], "figure.svg")
            self.assertEqual(mime, "image/svg+xml")
            self.assertEqual(hashlib.sha256(svg).hexdigest(), receipt["outputDigest"])
            self.assertIn(b'viewBox="10 20 400 200"', svg)
            self.assertIn(b'width="85mm"', svg)
            self.assertIn(b'CURRENT Linear', svg)
            self.assertIn(b'M 150 75 L 240 75 L 240 120', svg)
            self.assertEqual(json.loads(workspace.artifact(artifact["id"], "receipt")[0]), receipt)

    def test_preview_export_rejects_resources_and_executable_svg_without_persisting(self):
        malicious = [
            '<script>alert(1)</script>',
            '<foreignObject><div>HTML</div></foreignObject>',
            '<image href="file:///etc/passwd" />',
            '<rect x="0" y="0" width="20" height="20" onload="alert(1)" />',
            '<rect x="0" y="0" width="20" height="20" style="fill:url(https://invalid.example/a)" />',
            '<path d="M0 0 L10 10" marker-end="url(https://invalid.example/m.svg#marker)" />',
        ]
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Workspace(Path(temporary), None)
            for content in malicious:
                svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50">' + content + '</svg>'
                with self.subTest(content=content), self.assertRaises(ValueError):
                    workspace.export_preview(svg, "svg", 300, 85, {"caseId": "case"})
                self.assertEqual(list((Path(temporary) / "exports").iterdir()), [])
            for binding in ({"caseId": "case", "root": "/tmp"}, {"caseId": "case", "sourceDigest": "bad"}, {"caseId": "case", "revision": True}):
                with self.subTest(binding=binding), self.assertRaises(ValueError):
                    workspace.export_preview(PREVIEW_SVG, "svg", 300, 85, binding)


class PreviewHTTPTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="archcanvas-preview-http-", dir="/tmp")
        self.root = Path(self.directory.name)
        try:
            self.server = ArchCanvasServer(("127.0.0.1", 0), data_dir=self.root / "managed", studio_dir=self.root / "dist")
        except PermissionError:
            self.directory.cleanup()
            self.skipTest("Loopback sockets are unavailable in the command sandbox.")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.client = build_opener(ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.directory.cleanup()

    def request(self, path, payload=None, *, token=True, origin=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-ArchCanvas-Session"] = self.server.session_token
        if origin is not None:
            headers["Origin"] = origin
        request = Request(self.url + path, data=None if payload is None else json.dumps(payload).encode(), method="GET" if payload is None else "POST", headers=headers)
        try:
            with self.client.open(request, timeout=15) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def register(self, architecture):
        code, project = self.request("/api/projects", {key: architecture[key] for key in ("entry", "sources", "sourceDigest", "irDigest")})
        self.assertEqual(code, 201, project)
        return project

    def test_upload_and_legacy_route_share_portable_protocol(self):
        payload = {"files": FILES, "entry": "TwinPath", "config": {"width": 24}}
        code, preview = self.request("/api/preview/analyze", payload, token=False)
        self.assertEqual(code, 200, preview)
        code, compatibility = self.request("/api/source-adapter/analyze", payload, token=False)
        self.assertEqual((code, compatibility), (200, preview))
        self.assertEqual(preview, analyze(FILES, "TwinPath", {"width": 24}))
        self.assertEqual(self.request("/api/preview/analyze", {**payload, "root": "/etc"})[0], 400)
        self.assertEqual(self.request("/api/preview/analyze", payload, origin="http://untrusted.invalid")[0], 403)

    def test_edit_source_bridge_requires_session_and_can_register_multifile_model(self):
        payload = {"files": FILES, "entry": "TwinPath"}
        self.assertEqual(self.request("/api/preview/edit-source", payload, token=False)[0], 403)
        code, architecture = self.request("/api/preview/edit-source", payload)
        self.assertEqual(code, 200, architecture)
        project = self.register(architecture)
        code, preview = self.request(f"/api/projects/{project['id']}/preview", {})
        self.assertEqual(code, 200, preview)
        self.assertEqual(preview["studioBinding"], {"projectId": project["id"], **{key: project[key] for key in ("entry", "sourceDigest", "irDigest")}})
        self.assertEqual({source["path"]: source["text"] for source in preview["files"]}, FILES)
        self.assertEqual(self.request(f"/api/projects/{project['id']}/preview", {}, token=False)[0], 403)
        self.assertEqual(self.request("/api/preview/edit-source", {**payload, "root": "/tmp"})[0], 400)

    def test_managed_preview_refreshes_after_reviewed_source_edit_and_rejects_stale_version(self):
        original = self.root / "original.py"
        original.write_text(EDITABLE)
        project = self.register(analyze_source(EDITABLE, "Editable"))
        preview_route = f"/api/projects/{project['id']}/preview"
        code, before = self.request(preview_route, {"baseSourceDigest": project["sourceDigest"], "baseIrDigest": project["irDigest"]})
        self.assertEqual(code, 200, before)
        dropout = next(n for n in project["architecture"]["nodes"] if n["kind"] == "Dropout")
        code, receipt = self.request(f"/api/projects/{project['id']}/transactions", {"nodeId": dropout["id"], "parameter": "p", "value": 0.3, "baseSourceDigest": project["sourceDigest"], "baseIrDigest": project["irDigest"]})
        self.assertEqual((code, receipt["status"]), (200, "ReviewReady"))
        transaction_route = f"/api/projects/{project['id']}/transactions/{receipt['id']}"
        code, approved = self.request(transaction_route + "/approve", {"reviewDigest": receipt["reviewDigest"]})
        self.assertEqual((code, approved["status"]), (200, "Approved"))
        code, committed = self.request(transaction_route + "/commit", {"approvalId": approved["approvalId"]})
        self.assertEqual((code, committed["status"]), (200, "Committed"))
        self.assertEqual(self.request(preview_route, {"baseSourceDigest": project["sourceDigest"]})[0], 409)
        code, after = self.request(preview_route, {})
        self.assertEqual(code, 200, after)
        self.assertNotEqual(after["sourceSha256"], before["sourceSha256"])
        self.assertNotEqual(after["studioBinding"]["sourceDigest"], before["studioBinding"]["sourceDigest"])
        layer = next(n for n in after["ir"]["nodes"] if n.get("moduleType") == "Dropout")
        self.assertEqual(layer["constructorArgs"], [0.3])
        self.assertEqual(original.read_text(), EDITABLE)

    def test_capabilities_report_formal_preview_package_and_limits(self):
        code, capabilities = self.request("/api/capabilities")
        self.assertEqual(code, 200)
        self.assertEqual(capabilities["preview"]["limits"], {"files": 80, "sourceBytes": 2_000_000, "nodes": 480, "edges": 3600, "depth": 10})
        self.assertEqual(capabilities["preview"]["authoringArchitecture"], "/api/preview/edit-source")
        origin = Path(capabilities["packageProvenance"]["modules"]["archcanvas_preview"])
        self.assertEqual(origin.resolve(), Path(archcanvas_preview.__file__).resolve())
        self.assertTrue(capabilities["packageProvenance"]["independent"])

    def test_preview_export_http_uses_validated_current_snapshot_for_available_formats(self):
        available = publication_capabilities()
        for format in ("svg", "pdf", "png"):
            if not available[format]:
                continue
            payload = {"svg": PREVIEW_SVG, "format": format, "dpi": 300, "widthMm": 85, "binding": {"caseId": "current-case", "revision": 3}}
            code, artifact = self.request("/api/preview/exports", payload)
            self.assertEqual(code, 201, artifact)
            with self.client.open(self.url + artifact["url"], timeout=15) as response:
                body = response.read()
                self.assertEqual(response.headers["Content-Type"], {"svg": "image/svg+xml", "png": "image/png", "pdf": "application/pdf"}[format])
            receipt = artifact["receipt"]
            self.assertEqual(hashlib.sha256(body).hexdigest(), receipt["outputDigest"])
            self.assertEqual(receipt["previewSvgDigest"], hashlib.sha256(PREVIEW_SVG.encode()).hexdigest())
            self.assertEqual(receipt["caseId"], "current-case")
            self.assertEqual(receipt["revision"], 3)
            self.assertEqual(receipt["viewBox"], [10.0, 20.0, 400.0, 200.0])
            if format == "png":
                self.assertEqual(body[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(struct.unpack(">II", body[16:24]), (1004, 502))
            elif format == "pdf":
                self.assertTrue(body.startswith(b"%PDF-"))
            else:
                self.assertIn(b"CURRENT Linear", body)
        payload = {"svg": PREVIEW_SVG, "format": "svg", "dpi": 300, "widthMm": 85, "binding": {"caseId": "current-case"}}
        self.assertEqual(self.request("/api/preview/exports", payload, token=False)[0], 403)
        payload["svg"] = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><image href="https://invalid.example/a" /></svg>'
        self.assertEqual(self.request("/api/preview/exports", payload)[0], 400)


if __name__ == "__main__":
    unittest.main()
