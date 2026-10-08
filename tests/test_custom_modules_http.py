"""Real HTTP preview → draft CAS → source registration for custom modules."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from archcanvas_cli.server import ArchCanvasServer


SOURCE = """from torch import nn
class Pair(nn.Module):
    def __init__(self, width=4):
        super().__init__()
        self.project = nn.Linear(width, width)
    def forward(self, left, right):
        return self.project(left), right
"""


class CustomModuleHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="archcanvas-custom-http-")
        self.root = Path(self.temporary.name)
        try:
            self.server = ArchCanvasServer(("127.0.0.1", 0), data_dir=self.root / "documents", studio_dir=self.root / "studio")
        except PermissionError:
            self.temporary.cleanup()
            self.skipTest("Loopback socket creation unavailable in sandbox; run on permitted host.")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.client = build_opener(ProxyHandler({}))
        self.token = self.request("/api/session")[1]["token"]

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.temporary.cleanup()

    def request(self, path, payload=None, token=None):
        request = Request(self.url + path, data=json.dumps(payload).encode() if payload is not None else None,
                          headers={"Content-Type": "application/json", **({"X-ArchCanvas-Session": token} if token else {})})
        try:
            with self.client.open(request, timeout=15) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_preview_session_errors_and_text_only_boundary(self):
        payload = {"source": SOURCE, "entry": "Pair", "label": "Pair", "constructorValues": {}}
        self.assertEqual(self.request("/api/authoring/custom-modules/preview", payload)[0], 403)
        status, result = self.request("/api/authoring/custom-modules/preview", payload, self.token)
        self.assertEqual(status, 200)
        self.assertEqual([port["id"] for port in result["definition"]["inputs"]], ["left", "right"])
        self.assertEqual([port["id"] for port in result["definition"]["outputs"]], ["output_1", "output_2"])
        self.assertFalse(list((self.root / "projects").glob("*/project.json")))
        status, error = self.request("/api/authoring/custom-modules/preview", {**payload, "source": "invalid :"}, self.token)
        self.assertEqual(status, 400)
        self.assertEqual(error["diagnostics"][0]["code"], "custom_source_syntax")

    def test_persist_generate_register_sources_without_execution_or_original_write(self):
        status, result = self.request("/api/authoring/custom-modules/preview", {"source": SOURCE, "entry": "Pair", "label": "Pair", "constructorValues": {}}, self.token)
        self.assertEqual(status, 200)
        definition = result["definition"]
        def node(identity, kind, params=None):
            return {"id": identity, "kind": kind, "label": identity, "parameters": params or {}, "position": {"x": 20, "y": 20}}
        def edge(identity, source, source_port, target, target_port):
            return {"id": identity, "source": {"nodeId": source, "portId": source_port}, "target": {"nodeId": target, "portId": target_port}}
        draft = {"schemaVersion": 1, "mode": "authored-draft", "id": "draft-cafe", "title": "HTTP custom", "revision": 0,
                 "customModules": [definition], "nodes": [node("in_left", "Input", {"shape": [2, 4], "dtype": "float32"}),
                                                               node("in_right", "Input", {"shape": [2, 4], "dtype": "float32"}),
                                                               node("custom", definition["kind"]), node("out_left", "Output"), node("out_right", "Output")],
                 "edges": [edge("e1", "in_left", "output", "custom", "left"), edge("e2", "in_right", "output", "custom", "right"),
                           edge("e3", "custom", "output_1", "out_left", "input"), edge("e4", "custom", "output_2", "out_right", "input")]}
        draft["nodes"][2]["visual"] = {"width": 240, "height": 120, "fill": "#dfeee7", "stroke": "#20485c"}
        saved_status, saved = self.request("/api/authoring/drafts/draft-cafe", {"draft": draft, "expectedRevision": 0}, self.token)
        self.assertEqual(saved_status, 200)
        self.assertEqual(self.request("/api/authoring/drafts/draft-cafe"), (200, saved))
        # Recreate the HTTP service so reopening uses disk, not the first
        # handler/store instance or any browser-session definition metadata.
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.server = ArchCanvasServer(("127.0.0.1", 0), data_dir=self.root / "documents", studio_dir=self.root / "studio")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.token = self.request("/api/session")[1]["token"]
        reopened_status, reopened = self.request("/api/authoring/drafts/draft-cafe")
        self.assertEqual((reopened_status, reopened), (200, saved))
        status, generated = self.request("/api/authoring/generate", {"draft": reopened["draft"]}, self.token)
        self.assertEqual(status, 200)
        self.assertEqual(generated["verification"]["modelExecution"], "not_run")
        self.assertEqual(len([item for item in generated["architecture"]["nodes"] if item["kind"] == "Output"]), 2)
        self.assertFalse(list((self.root / "projects").glob("*/project.json")))
        architecture = generated["architecture"]
        status, registered = self.request("/api/projects", {"entry": architecture["entry"], "sources": architecture["sources"], "sourceDigest": architecture["sourceDigest"], "irDigest": architecture["irDigest"]}, self.token)
        self.assertEqual(status, 201)
        self.assertEqual(registered["architecture"], architecture)
        managed = self.root / "projects" / registered["id"] / "source"
        custom_files = list(managed.glob("archcanvas_custom_*.py"))
        self.assertEqual(len(custom_files), 1)
        self.assertTrue(custom_files[0].read_text().startswith(SOURCE.rstrip()))


if __name__ == "__main__":
    unittest.main()
