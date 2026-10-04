"""Loopback-only document service with atomic compare-and-swap persistence."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import archcanvas_cli
import archcanvas_python
from archcanvas_python import AnalysisError, analyze_project, analyze_source

MAX_REQUEST_BYTES = 4_000_000
DOCUMENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
EXAMPLES = (
    {"id": "transformer", "name": "Encoder–Decoder Transformer", "description": "Multi-file source, independent repeated encoder layers, cross-attention Q/K/V, masks and residual paths.", "entry": "model:Transformer"},
    {"id": "mlp", "name": "Multilayer Perceptron", "description": "A small source-backed Sequential classifier with Linear, GELU and Dropout.", "entry": "model:MLP"},
    {"id": "residual_cnn", "name": "Residual CNN", "description": "Multi-file residual blocks, shared-width convolutions, pooling and classifier.", "entry": "model:ResidualCNN"},
)


def project_root() -> Path | None:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file() and (candidate / "src" / "archcanvas_cli").is_dir():
            return candidate
    return None


def capabilities() -> dict:
    root = project_root()
    modules = {"archcanvas_cli": str(Path(archcanvas_cli.__file__).resolve()), "archcanvas_python": str(Path(archcanvas_python.__file__).resolve())}
    independent = all("ArchCanvas_Model Architecture Studio_Temp" not in path for path in modules.values())
    return {
        "schemaVersion": 1,
        "runtimeVersion": archcanvas_cli.__version__,
        "sourceAnalysis": True,
        "documentPersistence": True,
        "semanticWriteback": False,
        "runtimeObservation": False,
        "frontend": "stdlib-ast-subset",
        "packageProvenance": {"projectRoot": str(root) if root else None, "modules": modules, "independent": independent},
        "supported": ["local-module-imports", "literal-module-construction", "named-attention-ports", "tuple-outputs", "residual-dataflow", "bounded-module-list", "shared-instance-identity"],
        "limitations": ["No execution, shape inference or source writeback", "Only directly authored forward methods", "Unsupported dynamic control, state, factories and reflection remain opaque", "80 source files, 2 MB corpus, 1200 nodes, 16 repeat iterations"],
    }


class ConflictError(ValueError):
    def __init__(self, revision: int):
        self.revision = revision
        super().__init__(f"Document storage revision is {revision}; reload before saving.")


def validate_document(document: object, identity: str):
    """Validate the persistent envelope; visual operations live in the TS core.

    This endpoint cannot write source. Architecture facts are immutable after
    document creation, so a save cannot disguise a visual edit as an IR edit.
    """
    if not isinstance(document, dict) or document.get("schemaVersion") != 1 or document.get("id") != identity:
        raise ValueError("Document schemaVersion must be 1 and id must match the URL.")
    if type(document.get("revision")) is not int or document["revision"] < 0:
        raise ValueError("Document visual revision must be a non-negative integer.")
    architecture = document.get("architecture")
    if not isinstance(architecture, dict) or architecture.get("schemaVersion") != 1:
        raise ValueError("Document requires an Architecture schemaVersion 1.")
    if not isinstance(architecture.get("nodes"), list) or not isinstance(architecture.get("edges"), list):
        raise ValueError("Architecture nodes and edges must be lists.")
    if document.get("sourceBindingDigest") != architecture.get("sourceDigest") or not isinstance(architecture.get("sourceDigest"), str) or not isinstance(architecture.get("irDigest"), str):
        raise ValueError("Document source binding must match its architecture digest.")
    for field in ("displayAliases", "nodeStyleOverrides", "edgeStyleOverrides", "layout", "layoutByFrontier", "pageSpec"):
        if not isinstance(document.get(field), dict):
            raise ValueError(f"Document {field} must be an object.")
    for field in ("legendItems", "annotations", "expandedIds", "pinnedObjects"):
        if not isinstance(document.get(field), list):
            raise ValueError(f"Document {field} must be a list.")
    if not isinstance(document.get("title"), str) or len(document["title"]) > 500:
        raise ValueError("Document title must be text within 500 characters.")
    canonical_ids = {node.get("id") for node in architecture["nodes"] if isinstance(node, dict)}
    if None in canonical_ids or len(canonical_ids) != len(architecture["nodes"]):
        raise ValueError("Architecture node identities must be unique.")
    if not all(isinstance(value, str) and value in canonical_ids for value in document["expandedIds"] + document["pinnedObjects"]):
        raise ValueError("Expanded and pinned objects must reference canonical node identities.")


class DocumentStore:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def path(self, identity: str) -> Path:
        if not DOCUMENT_ID.fullmatch(identity):
            raise ValueError("Document id must contain only letters, digits, dots, underscores or hyphens.")
        path = self.directory / f"{identity}.json"
        if not path.resolve().is_relative_to(self.directory):
            raise ValueError("Document path escapes the persistence directory.")
        return path

    def get(self, identity: str) -> dict | None:
        with self.lock:
            path = self.path(identity)
            if not path.is_file():
                return None
            if path.stat().st_size > MAX_REQUEST_BYTES:
                raise ValueError("Saved document exceeds the size budget.")
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError("Saved document is unreadable; it was not overwritten.") from exc
            if not isinstance(value, dict) or type(value.get("revision")) is not int or value["revision"] < 1:
                raise ValueError("Saved document envelope is invalid; it was not overwritten.")
            validate_document(value.get("document"), identity)
            return value

    def put(self, identity: str, document: dict, expected_revision: int) -> dict:
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expectedRevision must be a non-negative storage revision.")
        validate_document(document, identity)
        with self.lock:
            current = self.get(identity)
            revision = current["revision"] if current else 0
            if revision != expected_revision:
                raise ConflictError(revision)
            if current and (current["document"]["architecture"] != document["architecture"] or current["document"]["sourceBindingDigest"] != document["sourceBindingDigest"]):
                raise ValueError("A visual document save cannot change canonical architecture or source binding.")
            result = {"document": document, "revision": revision + 1}
            encoded = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
            if len(encoded) > MAX_REQUEST_BYTES:
                raise ValueError("Document exceeds the 4 MB persistence budget.")
            path = self.path(identity)
            descriptor, temporary = tempfile.mkstemp(prefix=".save-", suffix=".json", dir=self.directory)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            return result


class ArchCanvasServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], *, data_dir: Path | None = None, studio_dir: Path | None = None):
        if address[0] not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("The ArchCanvas service accepts loopback addresses only.")
        root = project_root()
        self.store = DocumentStore(data_dir or (root or Path.cwd()) / ".archcanvas" / "documents")
        self.studio_dir = (studio_dir or (root / "studio" / "dist" if root else Path.cwd() / "studio" / "dist")).resolve()
        self.fixture_root = root / "fixtures" if root else None
        self.example_cache: dict[str, dict] = {}
        super().__init__(address, Handler)
        port = self.server_address[1]
        self.origins = {f"http://{host}:{number}" for host in ("127.0.0.1", "localhost") for number in (5173, port)}
        self.hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}


class Handler(BaseHTTPRequestHandler):
    server: ArchCanvasServer

    def log_message(self, format, *args):
        # Do not log user source or canvas content.
        return

    def origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        return (origin is None or origin in self.server.origins) and self.headers.get("Host") in self.server.hosts

    def send_json(self, status: int, value: object):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        origin = self.headers.get("Origin")
        if origin in self.server.origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def guard(self) -> bool:
        if not self.origin_allowed():
            self.send_json(403, {"error": "Only the local Studio origin and local service host are allowed."})
            return False
        return True

    def body(self) -> dict:
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Request Content-Type must be application/json.")
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("Chunked request bodies are not supported.")
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError as exc:
            raise ValueError("Content-Length must be an integer.") from exc
        if not 0 <= length <= MAX_REQUEST_BYTES:
            raise ValueError("JSON request body must fit within 4 MB.")
        try:
            result = json.loads(self.rfile.read(length).decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON values are not supported.")))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Request body must contain valid UTF-8 JSON.") from exc
        if not isinstance(result, dict):
            raise ValueError("JSON request must be an object.")
        return result

    def do_OPTIONS(self):
        if not self.guard():
            return
        self.send_response(204)
        origin = self.headers.get("Origin")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self):
        if not self.guard():
            return
        path = unquote(urlsplit(self.path).path)
        try:
            if path == "/api/capabilities":
                self.send_json(200, capabilities())
            elif path == "/api/examples":
                self.send_json(200, [{key: item[key] for key in ("id", "name", "description")} for item in EXAMPLES])
            elif path.startswith("/api/examples/"):
                identity = path.removeprefix("/api/examples/")
                example = next((item for item in EXAMPLES if item["id"] == identity), None)
                if example is None:
                    self.send_json(404, {"error": "Unknown example id."})
                elif self.server.fixture_root is None:
                    self.send_json(503, {"error": "Bundled example sources are not present in this installation."})
                else:
                    if identity not in self.server.example_cache:
                        self.server.example_cache[identity] = analyze_project(self.server.fixture_root / identity, example["entry"])
                    self.send_json(200, self.server.example_cache[identity])
            elif path.startswith("/api/documents/"):
                document = self.server.store.get(path.removeprefix("/api/documents/"))
                self.send_json(200 if document else 404, document or {"error": "Document not found."})
            elif path.startswith("/api/"):
                self.send_json(404, {"error": "Unknown API route."})
            else:
                self.static(path)
        except (AnalysisError, ValueError) as exc:
            self.send_json(400, {"error": str(exc)})

    def do_POST(self):
        if not self.guard():
            return
        if urlsplit(self.path).path != "/api/analyze":
            self.send_json(404, {"error": "Unknown API route."})
            return
        try:
            payload = self.body()
            if set(payload) - {"source", "entry", "filename"}:
                raise ValueError("Analyze accepts source text, entry and optional logical filename only; filesystem roots are not accepted over HTTP.")
            if not isinstance(payload.get("entry"), str) or not isinstance(payload.get("filename", "model.py"), str):
                raise ValueError("Entry and filename must be text.")
            self.send_json(200, analyze_source(payload.get("source"), payload["entry"], payload.get("filename", "model.py")))
        except (AnalysisError, ValueError) as exc:
            self.send_json(400, {"error": str(exc)})

    def do_PUT(self):
        if not self.guard():
            return
        path = unquote(urlsplit(self.path).path)
        if not path.startswith("/api/documents/"):
            self.send_json(404, {"error": "Unknown API route."})
            return
        try:
            payload = self.body()
            if set(payload) != {"document", "expectedRevision"}:
                raise ValueError("Document save requires document and expectedRevision.")
            self.send_json(200, self.server.store.put(path.removeprefix("/api/documents/"), payload["document"], payload["expectedRevision"]))
        except ConflictError as exc:
            self.send_json(409, {"error": str(exc), "revision": exc.revision})
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})

    def static(self, logical_path: str):
        if ".." in Path(logical_path).parts or "\\" in logical_path:
            self.send_json(400, {"error": "Static path traversal is not accepted."})
            return
        root = self.server.studio_dir
        path = (root / logical_path.lstrip("/")).resolve()
        if not path.is_relative_to(root):
            self.send_json(400, {"error": "Static file is outside Studio's distribution directory."})
            return
        if not path.is_file():
            path = root / "index.html"
        if not path.is_file():
            self.send_json(503, {"error": "Studio build is not present. Build studio/dist or use the Vite development server on localhost:5173."})
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(path))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

