"""Loopback-only document service with atomic compare-and-swap persistence."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import tempfile
import threading
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import archcanvas_cli
import archcanvas_python
import archcanvas_transactions
import archcanvas_publication
import archcanvas_runtime
import archcanvas_authoring
from archcanvas_python import AnalysisError, analyze_project, analyze_source, validate_output_paths
from archcanvas_transactions import TransactionManager
from .workspace import Workspace
from .drafts import DraftStore, DraftConflict

MAX_REQUEST_BYTES = 4_000_000
DOCUMENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
EXAMPLES = (
    {"id": "transformer", "name": "Encoder–Decoder Transformer", "description": "Multi-file source, independent repeated encoder layers, cross-attention Q/K/V, masks and residual paths.", "entry": "model:Transformer"},
    {"id": "mlp", "name": "Multilayer Perceptron", "description": "A small source-backed Sequential classifier with Linear, GELU and Dropout.", "entry": "model:MLP"},
    {"id": "residual_cnn", "name": "Residual CNN", "description": "Multi-file residual blocks, shared-width convolutions, pooling and classifier.", "entry": "model:ResidualCNN"},
    {"id": "holdout_vit", "name": "Vision Transformer holdout", "description": "Independent patch projection, token attention and residual MLP; unsupported Conv1d remains an opaque boundary in the companion holdout.", "entry": "model:PatchVisionEncoder"},
    {"id": "stress_300", "name": "Dense 300-layer stress", "description": "Static source declaration of 150 Linear/ReLU pairs in one collapsed Sequential; expand it for a source-backed 300-object performance scenario.", "entry": "model:DenseStress300"},
    {"id": "rebind", "name": "Input Rebinding Lab", "description": "Authored straight-line tensor branches for reviewed input rebinding, without model execution.", "entry": "model:RebindDemo"},
    {"id": "multi_input", "name": "Multi-input Attention", "description": "Explicit Q/K/V and padding-mask contracts for isolated train/eval connection verification.", "entry": "model:MultiInputAttention"},
)


def project_root() -> Path | None:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file() and (candidate / "src" / "archcanvas_cli").is_dir():
            return candidate
    return None


def runtime_config() -> dict[str, str] | None:
    root = project_root()
    if root is None:
        return None
    return {"interpreter": str(root / ".venv-runtime/bin/python"), "dependencyLock": str(root / "requirements-runtime.lock")}


def capabilities() -> dict:
    root = project_root()
    modules = {name: str(Path(module.__file__).resolve()) for name, module in {"archcanvas_cli": archcanvas_cli, "archcanvas_python": archcanvas_python, "archcanvas_transactions": archcanvas_transactions, "archcanvas_publication": archcanvas_publication, "archcanvas_runtime": archcanvas_runtime, "archcanvas_authoring": archcanvas_authoring}.items()}
    independent = all("ArchCanvas_Model Architecture Studio_Temp" not in path for path in modules.values())
    runtime_profile = archcanvas_runtime.runtime_capabilities(runtime_config())
    return {
        "schemaVersion": 1,
        "runtimeVersion": archcanvas_cli.__version__,
        "sourceAnalysis": True,
        "modelAuthoring": {"mode": "authored-draft", "catalog": "/api/authoring/catalog", "generation": "new-managed-copy", "sourceImport": "/api/authoring/import-source", "sourceFrontier": "/api/authoring/source-frontier", "runtimeVerified": False},
        "documentPersistence": True,
        "semanticWriteback": True,
        "supportedIntents": ["set_dropout_probability", "update_configuration", "replace_activation", "rebind_input"],
        "semanticScope": {"operators": {"Dropout": ["p"], "MultiheadAttention": ["dropout"]}, "origins": ["explicit-float-literal", "unique-module-top-level-float-all-probability-readers"], "httpCommit": "managed-workspace-copy-only", "runtimeVerified": False},
        "activationScope": {"operators": ["ReLU", "GELU"], "constructors": "direct-no-argument", "structuralProfile": "root-straight-line-floating-input", "runtimeRequiredInStudio": True},
        "rebindScope": {"operators": ["Identity", "Dropout", "ReLU", "GELU"], "control": "entry-forward-straight-line", "compatibility": "same-input-symbolic-shape-and-dtype", "runtimeVerified": False},
        "structuralRebindScope": {"operators": ["Identity", "Dropout", "ReLU", "GELU", "MultiheadAttention"], "ports": ["input", "query", "key", "value", "attn_mask", "key_padding_mask"], "sourceArguments": ["positional-name", "keyword-name"], "control": "entry-forward-straight-line", "profile": "structural-verified", "inputs": "explicit-named-shape-dtype-seed-modes", "device": "cpu", "constructor": "source-default-only", "coverage": "frozen-samples-only", "runtimeRequired": True},
        "publicationExport": archcanvas_publication.capabilities(),
        "runtimeObservation": runtime_profile["available"],
        "runtimeProfiles": runtime_profile,
        "frontend": "stdlib-ast-subset",
        "packageProvenance": {"projectRoot": str(root) if root else None, "modules": modules, "independent": independent},
        "supported": ["local-module-imports", "literal-module-construction", "named-attention-ports", "tuple-outputs", "residual-dataflow", "bounded-module-list", "shared-instance-identity"],
        "limitations": ["Source analysis never executes models; structural execution requires an explicit frozen CPU profile and mandatory kernel isolation", "Sample runtime observations do not establish full-program coverage or old/new numerical equivalence", "HTTP source edits affect registered managed copies only", "Only directly authored forward methods", "Unsupported dynamic control, state, factories and reflection remain opaque", "80 source files, 2 MB corpus, 1200 nodes, 16 repeat iterations", "One service process per data directory; document CAS is process-local"],
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
    validate_output_paths(architecture["nodes"])
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
        self.workspace = Workspace(self.store.directory.parent, root)
        self.drafts = DraftStore(self.store.directory.parent / "drafts")
        self.transactions = TransactionManager(self.store.directory.parent / "transactions")
        self.session_token = secrets.token_urlsafe(32)
        self.studio_dir = (studio_dir or (root / "studio" / "dist" if root else Path.cwd() / "studio" / "dist")).resolve()
        self.fixture_root = root / "fixtures" if root else None
        self.example_cache: dict[str, dict] = {}
        self.runtime_jobs: dict[str, dict] = {}
        self.runtime_jobs_lock = threading.RLock()
        super().__init__(address, Handler)
        port = self.server_address[1]
        self.origins = {f"http://{host}:{number}" for host in ("127.0.0.1", "localhost") for number in (5173, port)}
        self.hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    def runtime_job(self, project: str, identity: str) -> dict:
        with self.runtime_jobs_lock:
            job = self.runtime_jobs.get(identity)
            if job is None or job["projectId"] != project:
                raise ValueError("Runtime job does not belong to this registered project.")
            return {key: value for key, value in job.items() if key != "cancelEvent"}

    def start_runtime_job(self, project_id: str, payload: dict, action: str) -> dict:
        if not isinstance(payload.get("inputSpec"), dict):
            raise ValueError("An explicit input spec is mandatory; runtime previews never select the legacy static profile.")
        archcanvas_runtime.normalize_input_spec(payload["inputSpec"])
        self.workspace.metadata(project_id)
        with self.runtime_jobs_lock:
            if any(job["status"] == "running" for job in self.runtime_jobs.values()):
                raise ValueError("A runtime preview is already running; wait or cancel it before preparing another.")
            identity = secrets.token_hex(16)
            event = threading.Event()
            self.runtime_jobs[identity] = {"id": identity, "projectId": project_id, "status": "running", "cancelEvent": event}
        def run():
            try:
                with self.workspace.lock:
                    project = self.workspace.project(project_id)
                    if project["sourceDigest"] != payload["baseSourceDigest"] or project["irDigest"] != payload["baseIrDigest"]:
                        raise ValueError("Project source or IR changed before runtime preparation; reload.")
                    config = runtime_config()
                    config = {**config, "cancelEvent": event} if config else None
                    common = {"root": self.workspace.source_root(project_id), "entry": project["entry"], "nodeId": payload["nodeId"], "baseSourceDigest": payload["baseSourceDigest"], "inputSpec": payload["inputSpec"], "runtimeConfig": config}
                    if action == "activation":
                        receipt = self.transactions.prepare_activation(**common, activation=payload["activation"])
                    else:
                        receipt = self.transactions.prepare_rebind(**common, portId=payload["portId"], producerNodeId=payload["producerNodeId"], producerPortId=payload["producerPortId"])
                    directory = self.workspace.location("projects", project_id) / "transactions"
                    directory.mkdir(exist_ok=True)
                    (directory / receipt["id"]).write_text("managed-copy", encoding="utf-8")
                result = {"status": "complete", "transaction": receipt}
            except Exception as exc:
                result = {"status": "failed", "error": str(exc)}
            with self.runtime_jobs_lock:
                self.runtime_jobs[identity].update(result)
        threading.Thread(target=run, name=f"archcanvas-runtime-{identity}", daemon=True).start()
        return self.runtime_job(project_id, identity)

    def server_close(self):
        with self.runtime_jobs_lock:
            for job in self.runtime_jobs.values():
                if job["status"] == "running":
                    job["cancelEvent"].set()
        super().server_close()


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
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-ArchCanvas-Session")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self):
        if not self.guard():
            return
        path = unquote(urlsplit(self.path).path)
        try:
            if path == "/api/capabilities":
                self.send_json(200, capabilities())
            elif path == "/api/session":
                self.send_json(200, {"token": self.server.session_token})
            elif path == "/api/authoring/catalog":
                self.send_json(200, archcanvas_authoring.module_catalog())
            elif path.startswith("/api/authoring/drafts/"):
                draft = self.server.drafts.get(path.removeprefix("/api/authoring/drafts/"))
                self.send_json(200 if draft else 404, draft or {"error": "Draft not found."})
            elif path.startswith("/api/projects/"):
                parts = path.removeprefix("/api/projects/").split("/")
                if len(parts) == 1:
                    self.send_json(200, self.server.workspace.project(parts[0]))
                elif len(parts) == 3 and parts[1] == "transactions":
                    self.transaction_binding(parts[0], parts[2])
                    self.send_json(200, self.server.transactions.get(parts[2]))
                elif len(parts) == 3 and parts[1] == "runtime-jobs":
                    if self.session_guard():
                        self.send_json(200, self.server.runtime_job(parts[0], parts[2]))
                else:
                    self.send_json(404, {"error": "Unknown project route."})
            elif path.startswith("/api/exports/"):
                parts = path.removeprefix("/api/exports/").split("/")
                if len(parts) != 2:
                    raise ValueError("Invalid export artifact route.")
                body, mime = self.server.workspace.artifact(*parts)
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; sandbox")
                self.end_headers()
                self.wfile.write(body)
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
        except archcanvas_authoring.DraftError as exc:
            self.send_json(400, {"error": str(exc), "diagnostics": exc.diagnostics})
        except (AnalysisError, ValueError, OSError) as exc:
            self.send_json(400, {"error": str(exc)})

    def transaction_binding(self, project_id: str, transaction_id: str, create=False):
        if not isinstance(transaction_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", transaction_id):
            raise ValueError("Invalid transaction identity.")
        directory = self.server.workspace.location("projects", project_id) / "transactions"
        project = self.server.workspace.metadata(project_id)
        if not self.server.transactions.matches_project(transaction_id, self.server.workspace.location("projects", project_id) / "source", project["entry"]):
            raise ValueError("Transaction source binding does not match this registered project.")
        if create:
            directory.mkdir(exist_ok=True)
            (directory / transaction_id).write_text("managed-copy", encoding="utf-8")
        elif not (directory / transaction_id).is_file():
            raise ValueError("Transaction does not belong to this registered project.")

    def session_guard(self) -> bool:
        if not secrets.compare_digest(self.headers.get("X-ArchCanvas-Session", ""), self.server.session_token):
            self.send_json(403, {"error": "A current Studio session token is required for this action."})
            return False
        return True

    def do_POST(self):
        if not self.guard():
            return
        path = urlsplit(self.path).path
        if path != "/api/analyze" and not self.session_guard():
            return
        try:
            payload = self.body()
            if path == "/api/analyze":
                if set(payload) - {"source", "entry", "filename"}:
                    raise ValueError("Analyze accepts source text, entry and optional logical filename only; filesystem roots are not accepted over HTTP.")
                if not isinstance(payload.get("entry"), str) or not isinstance(payload.get("filename", "model.py"), str):
                    raise ValueError("Entry and filename must be text.")
                self.send_json(200, analyze_source(payload.get("source"), payload["entry"], payload.get("filename", "model.py")))
            elif path == "/api/projects":
                self.send_json(201, self.server.workspace.register(payload))
            elif path == "/api/authoring/import-source":
                if set(payload) != {"document", "scene"}:
                    raise ValueError("Source import requires the current document and scene.")
                validate_document(payload["document"], payload["document"].get("id", ""))
                self.send_json(201, archcanvas_authoring.import_source_draft(payload["document"], payload["scene"]))
            elif path == "/api/authoring/source-frontier":
                if set(payload) != {"draft", "document", "scene"}:
                    raise ValueError("Source frontier requires draft, current source document and scene.")
                validate_document(payload["document"], payload["document"].get("id", ""))
                from archcanvas_authoring.source_import import rebase_source_frontier
                self.send_json(200, rebase_source_frontier(payload["draft"], payload["document"], payload["scene"]))
            elif path in ("/api/authoring/validate", "/api/authoring/generate"):
                if set(payload) != {"draft"}:
                    raise ValueError("Authoring requires one draft; paths and existing project ids are not accepted.")
                result = archcanvas_authoring.generate_model(payload["draft"]) if path.endswith("/generate") else archcanvas_authoring.validate_draft(payload["draft"])
                self.send_json(200, result)
            elif path.startswith("/api/authoring/drafts/"):
                if set(payload) != {"draft", "expectedRevision"}:
                    raise ValueError("Draft save requires draft and expectedRevision.")
                self.send_json(200, self.server.drafts.put(path.removeprefix("/api/authoring/drafts/"), payload["draft"], payload["expectedRevision"]))
            elif path == "/api/exports":
                if set(payload) not in ({"document", "format", "dpi"}, {"document", "format", "dpi", "options"}):
                    raise ValueError("Export requires the current document, format, DPI and optional exact detail options.")
                document = payload["document"]
                validate_document(document, document.get("id", "") if isinstance(document, dict) else "")
                self.send_json(201, self.server.workspace.export(document, payload["format"], payload["dpi"], payload.get("options")))
            elif path.startswith("/api/projects/"):
                parts = path.removeprefix("/api/projects/").split("/")
                if len(parts) == 4 and parts[1] == "runtime-jobs" and parts[3] == "cancel":
                    if payload:
                        raise ValueError("Runtime cancellation accepts no model or environment fields.")
                    self.server.runtime_job(parts[0], parts[2])
                    with self.server.runtime_jobs_lock:
                        self.server.runtime_jobs[parts[2]]["cancelEvent"].set()
                    self.send_json(200, self.server.runtime_job(parts[0], parts[2]))
                    return
                if len(parts) == 2 and parts[1] in ("structural-rebind-jobs", "activation-jobs"):
                    activation = parts[1] == "activation-jobs"
                    expected = {"nodeId", "baseSourceDigest", "baseIrDigest", "inputSpec"} | ({"activation"} if activation else {"portId", "producerNodeId", "producerPortId"})
                    if set(payload) != expected:
                        raise ValueError("Runtime preview requires its exact target, frozen inputs and source/IR versions.")
                    self.send_json(202, self.server.start_runtime_job(parts[0], payload, "activation" if activation else "rebind"))
                    return
                with self.server.workspace.lock:
                    if len(parts) == 2 and parts[1] in ("transactions", "configuration", "configuration-options", "rebind", "rebind-options", "structural-rebind", "structural-rebind-options"):
                        structural = parts[1].startswith("structural-")
                        expected = {"nodeId", "baseSourceDigest", "baseIrDigest"}
                        expected |= {"parameter", "value"} if parts[1] in ("transactions", "configuration") else {"parameter"} if parts[1] == "configuration-options" else {"portId"}
                        if structural:
                            expected.add("inputSpec")
                        if parts[1] in ("rebind", "structural-rebind"):
                            expected |= {"producerNodeId", "producerPortId"}
                        if set(payload) != expected:
                            raise ValueError("A semantic request requires its exact target fields and source/IR versions.")
                        if structural:
                            if not isinstance(payload["inputSpec"], dict):
                                raise ValueError("An explicit input spec is mandatory; structural routes never select the legacy static profile.")
                            archcanvas_runtime.normalize_input_spec(payload["inputSpec"])
                        project = self.server.workspace.project(parts[0])
                        if project["sourceDigest"] != payload["baseSourceDigest"] or project["irDigest"] != payload["baseIrDigest"]:
                            self.send_json(409, {"error": "The project source or IR changed; reload before preparing."})
                            return
                        if parts[1] == "configuration-options":
                            from archcanvas_transactions.config_activation import inspect_configuration_origin
                            options = inspect_configuration_origin(self.server.workspace.source_root(parts[0]), project["entry"], payload["nodeId"], payload["parameter"], project["architecture"])
                            self.send_json(200, options)
                            return
                        if parts[1] in ("rebind-options", "structural-rebind-options"):
                            if structural:
                                from archcanvas_python.structural_rebind import inspect_structural_rebind
                                options = inspect_structural_rebind(self.server.workspace.source_root(parts[0]), project["entry"], payload["nodeId"], payload["portId"], payload["inputSpec"], architecture=project["architecture"])
                            else:
                                from archcanvas_python.rebind import inspect_rebind
                                options = inspect_rebind(self.server.workspace.source_root(parts[0]), project["entry"], payload["nodeId"], architecture=project["architecture"])
                            if options["sourceDigest"] != payload["baseSourceDigest"] or options["irDigest"] != payload["baseIrDigest"]:
                                self.send_json(409, {"error": "The project source or IR changed while inspecting; reload before preparing."})
                                return
                            if (options.get("target") or {}).get("portId") != payload["portId"]:
                                # Invalid or unsupported canonical slot remains a proposal.
                                options = {**options, "status": "unsupported", "supported": False, "candidates": [], "blockers": [*options.get("blockers", []), "The selected port is not the uniquely authored unary input slot."]}
                            self.send_json(200, options)
                            return
                        if parts[1] in ("rebind", "structural-rebind"):
                            extra = {"inputSpec": payload["inputSpec"], "runtimeConfig": runtime_config()} if structural else {}
                            receipt = self.server.transactions.prepare_rebind(root=self.server.workspace.source_root(parts[0]), entry=project["entry"], nodeId=payload["nodeId"], portId=payload["portId"], producerNodeId=payload["producerNodeId"], producerPortId=payload["producerPortId"], baseSourceDigest=payload["baseSourceDigest"], **extra)
                        else:
                            prepare = self.server.transactions.prepare_config if parts[1] == "configuration" else self.server.transactions.prepare
                            receipt = prepare(root=self.server.workspace.source_root(parts[0]), entry=project["entry"], nodeId=payload["nodeId"], parameter=payload["parameter"], value=payload["value"], baseSourceDigest=payload["baseSourceDigest"])
                        self.transaction_binding(parts[0], receipt["id"], create=True)
                    elif len(parts) == 4 and parts[1] == "transactions":
                        self.transaction_binding(parts[0], parts[2])
                        action = parts[3]
                        if action == "approve" and set(payload) == {"reviewDigest"}:
                            receipt = self.server.transactions.approve(parts[2], payload["reviewDigest"])
                        elif action == "commit" and set(payload) == {"approvalId"}:
                            receipt = self.server.transactions.commit(parts[2], payload["approvalId"])
                        elif action == "discard" and not payload:
                            receipt = self.server.transactions.discard(parts[2])
                        else:
                            raise ValueError("Invalid transaction action or approval binding.")
                    else:
                        raise ValueError("Unknown transaction route.")
                self.send_json(200, receipt)
            else:
                self.send_json(404, {"error": "Unknown API route."})
        except DraftConflict as exc:
            self.send_json(409, {"error": str(exc), "revision": exc.revision})
        except archcanvas_authoring.DraftError as exc:
            self.send_json(400, {"error": str(exc), "diagnostics": exc.diagnostics})
        except (AnalysisError, ValueError, OSError) as exc:
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
