from __future__ import annotations

import hashlib
import json
import secrets
import sys
import threading
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from archcanvas_adapters import analyze_with_adapter
from archcanvas_core.models import (
    AnalysisJob,
    AnalysisRequest,
    Diagnostic,
    DraftGraphDocument,
    JobState,
    PatchBatch,
    ProjectSession,
    VisualPatch,
)
from archcanvas_python import AnalysisError

from .bundle import StudioBundle, prepare_studio_bundle
from .document import apply_patch, apply_patch_batch, redo_patch, undo_patch
from .operations import alignment_batch, auto_layout_batch, studio_fingerprint
from .project import create_project_session, discover_project


class StudioRequestHandler(SimpleHTTPRequestHandler):
    server: StudioHTTPServer

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        server = args[2]
        super().__init__(*args, directory=str(server.bundle.static_dir), **kwargs)

    def log_message(self, format: str, *args: object) -> None:
        print(f"studio: {format % args}", file=sys.stderr)

    def _json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        if isinstance(value, dict) and "architecture" in value and "document" in value:
            value.setdefault("session_nonce", self.server.session_nonce)
            value.setdefault(
                "jobs",
                [job.model_dump(mode="json") for job in self.server.jobs.values()],
            )
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _error(self, error: Exception) -> None:
        self._json(
            {"status": "invalid", "error": str(error)},
            HTTPStatus.UNPROCESSABLE_ENTITY,
        )

    def _payload(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            raise ValueError("request body exceeds the Studio limit")
        raw = self.rfile.read(length)
        payload = json.loads(raw or b"{}")
        if not isinstance(payload, dict):
            raise TypeError("request body must be a JSON object")
        return payload

    def _check_write_origin(self) -> None:
        host = self.headers.get("Host", "")
        if host and not host.startswith(("127.0.0.1:", "localhost:", "[::1]:")):
            raise ValueError("Studio rejected a non-loopback host")
        origin = self.headers.get("Origin")
        if origin and not origin.startswith(("http://127.0.0.1", "http://localhost", "http://[::1]")):
            raise ValueError("Studio rejected a non-loopback request origin")
        if origin and self.headers.get("X-ArchCanvas-Nonce") != self.server.session_nonce:
            raise ValueError("Studio session nonce is missing or invalid")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            with self.server.lock:
                state = self.server.bundle.state()
                state["session_nonce"] = self.server.session_nonce
                state["jobs"] = [
                    job.model_dump(mode="json") for job in self.server.jobs.values()
                ]
                self._json(state)
            return
        if parsed.path == "/api/projects/recent":
            with self.server.lock:
                self._json({"projects": [self.server.bundle.project_session.model_dump(mode="json")]})
            return
        if parsed.path.endswith("/discovery") and parsed.path.startswith("/api/projects/"):
            with self.server.lock:
                project_id = parsed.path.split("/")[3]
                if project_id != self.server.bundle.project_session.project_id:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self._json(self.server.bundle.project_discovery)
            return
        if parsed.path == "/api/search":
            query = parse_qs(parsed.query).get("q", [""])[0]
            limit = min(100, max(1, int(parse_qs(parsed.query).get("limit", ["50"])[0])))
            with self.server.lock:
                self._json(
                    {
                        "input_fingerprint": studio_fingerprint(self.server.bundle),
                        "results": self.server.bundle.search(query, limit),
                    }
                )
            return
        if parsed.path == "/api/source-excerpt":
            try:
                query = parse_qs(parsed.query)
                path = query.get("path", [""])[0]
                start_line = int(query.get("start", ["1"])[0])
                end_line = int(query.get("end", [str(start_line)])[0])
                context = int(query.get("context", ["4"])[0])
                with self.server.lock:
                    self._json(
                        self.server.bundle.source_excerpt(
                            path,
                            start_line,
                            end_line,
                            context=context,
                        )
                    )
            except (TypeError, ValueError) as error:
                self._error(error)
            return
        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.removeprefix("/api/jobs/")
            with self.server.lock:
                job = self.server.jobs.get(job_id)
                if job is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                else:
                    self._json(job)
            return
        if parsed.path == "/api/export":
            try:
                with self.server.lock:
                    payload = self.server.bundle.export_svg().encode()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="archcanvas.svg"')
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except ValueError as error:
                self._error(error)
            return
        super().do_GET()

    def do_POST(self) -> None:
        try:
            self._check_write_origin()
            payload = self._payload()
            if self.path == "/api/projects/open":
                root = Path(str(payload["root"]))
                with self.server.lock:
                    generation = self.server.bundle.project_session.generation + 1
                    session = create_project_session(
                        root,
                        self.server.bundle.workspace,
                        generation=generation,
                        entrypoint=str(payload["entrypoint"]) if payload.get("entrypoint") else None,
                        framework=str(payload.get("framework", "auto")),
                        task=str(payload.get("task", "inference")),
                        config_path=str(payload["config_path"]) if payload.get("config_path") else None,
                    )
                    discovery = discover_project(Path(session.root))
                    self.server.pending_projects[session.project_id] = (session, discovery)
                    self._json(
                        {
                            "project": session.model_dump(mode="json"),
                            "discovery": discovery,
                        }
                    )
                return
            if self.path == "/api/analyses":
                request = AnalysisRequest.model_validate(payload)
                job = self.server.start_analysis(request)
                self._json(job, HTTPStatus.ACCEPTED)
                return
            with self.server.lock:
                document = self.server.bundle.document
                if self.path == "/api/navigation":
                    expanded_ids = payload.get("expanded_ids")
                    if expanded_ids is not None and not isinstance(expanded_ids, list):
                        raise TypeError("expanded_ids must be an ordered list")
                    expansions = payload.get("expansions")
                    if expansions is not None:
                        if not isinstance(expansions, dict):
                            raise TypeError("expansions must be an object")
                        if any(
                            not isinstance(values, list)
                            for values in expansions.values()
                        ):
                            raise TypeError("each navigation expansion must be a list")
                    self.server.bundle.set_navigation_view(
                        str(payload.get("projection", "")),
                        [str(item) for item in expanded_ids]
                        if expanded_ids is not None
                        else None,
                        {
                            str(kind): [str(item) for item in values]
                            for kind, values in expansions.items()
                        }
                        if expansions is not None
                        else None,
                    )
                    self._json(self.server.bundle.state())
                    return
                if self.path == "/api/patch":
                    patch = VisualPatch.model_validate(payload)
                    scenes = {
                        scene.scene_id: scene
                        for scene in self.server.bundle.base_scenes.values()
                    }
                    changed = apply_patch(document, patch, scenes)
                elif self.path == "/api/patch-batch":
                    batch = PatchBatch.model_validate(payload)
                    scenes = {
                        scene.scene_id: scene
                        for scene in self.server.bundle.base_scenes.values()
                    }
                    changed = apply_patch_batch(document, batch, scenes)
                elif self.path == "/api/layout":
                    scene = next(iter(self.server.bundle.materialized_scenes().values()))
                    batch = auto_layout_batch(
                        scene,
                        pinned_ids=set(self.server.bundle.state()["view_state"]["pinned_node_ids"]),
                        batch_id=str(payload["batch_id"]),
                    )
                    scenes = {
                        item.scene_id: item for item in self.server.bundle.base_scenes.values()
                    }
                    changed = apply_patch_batch(document, batch, scenes)
                elif self.path == "/api/align":
                    scene = next(iter(self.server.bundle.materialized_scenes().values()))
                    selected_ids = payload.get("selected_ids")
                    if not isinstance(selected_ids, list):
                        raise TypeError("selected_ids must be an ordered list")
                    batch = alignment_batch(
                        scene,
                        [str(item) for item in selected_ids],
                        str(payload["command"]),
                        pinned_ids=set(self.server.bundle.state()["view_state"]["pinned_node_ids"]),
                        gap=float(payload["gap"]) if payload.get("gap") is not None else None,
                        batch_id=str(payload["batch_id"]),
                    )
                    scenes = {
                        item.scene_id: item for item in self.server.bundle.base_scenes.values()
                    }
                    changed = apply_patch_batch(document, batch, scenes)
                elif self.path == "/api/undo":
                    changed = undo_patch(document)
                elif self.path == "/api/redo":
                    changed = redo_patch(document)
                elif self.path == "/api/transaction/prepare":
                    self.server.bundle.prepare_parameter(payload)
                    self._json(self.server.bundle.state())
                    return
                elif self.path == "/api/transaction/prepare-structural":
                    self.server.bundle.prepare_structural(payload)
                    self._json(self.server.bundle.state())
                    return
                elif self.path == "/api/proposal/connection":
                    self.server.bundle.propose_connection(payload)
                    self._json(self.server.bundle.state())
                    return
                elif self.path == "/api/proposal/node":
                    self.server.bundle.propose_draft_node(payload)
                    self._json(self.server.bundle.state())
                    return
                elif self.path == "/api/transaction/commit":
                    self.server.bundle.commit_parameter()
                    self._json(self.server.bundle.state())
                    return
                elif self.path == "/api/transaction/discard":
                    self.server.bundle.discard_parameter()
                    self._json(self.server.bundle.state())
                    return
                elif self.path == "/api/validation-runs":
                    validation = self.server.bundle.validate(
                        str(payload.get("profile", "fast-static")),
                        runtime_execution_authorized=bool(
                            payload.get("runtime_execution_authorized", False)
                        ),
                    )
                    state = self.server.bundle.state()
                    state["active_validation"] = validation.model_dump(mode="json")
                    self._json(state)
                    return
                elif self.path.startswith("/api/jobs/") and self.path.endswith("/cancel"):
                    job_id = self.path[len("/api/jobs/") : -len("/cancel")]
                    job = self.server.jobs.get(job_id)
                    if job is None:
                        self.send_error(HTTPStatus.NOT_FOUND)
                        return
                    if job.state in {JobState.QUEUED, JobState.RUNNING}:
                        self.server.jobs[job_id] = job.model_copy(
                            update={"state": JobState.CANCELLED, "finished_at": datetime.now(UTC).isoformat()}
                        )
                    self._json(self.server.jobs[job_id])
                    return
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self.server.bundle.save_document(changed)
                self._json(self.server.bundle.state())
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self._error(error)

    def do_PUT(self) -> None:
        try:
            self._check_write_origin()
            payload = self._payload()
            if not self.path.startswith("/api/drafts/"):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            expected_revision = int(payload.pop("expected_revision"))
            draft = DraftGraphDocument.model_validate(payload)
            with self.server.lock:
                if self.path.removeprefix("/api/drafts/") != self.server.bundle.draft.draft_id:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self.server.bundle.save_draft(draft, expected_revision)
                self._json(self.server.bundle.state())
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self._error(error)


class StudioHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], bundle: StudioBundle):
        self.bundle = bundle
        self.lock = threading.RLock()
        self.session_nonce = secrets.token_urlsafe(24)
        self.jobs: dict[str, AnalysisJob] = {}
        self.pending_projects: dict[str, tuple[ProjectSession, dict[str, object]]] = {}
        super().__init__(address, StudioRequestHandler)

    def start_analysis(self, request: AnalysisRequest) -> AnalysisJob:
        with self.lock:
            pending = self.pending_projects.get(request.project_id)
            if pending is None:
                if request.project_id != self.bundle.project_session.project_id:
                    raise ValueError("analysis references an unknown project session")
                session = self.bundle.project_session
            else:
                session = pending[0]
            if request.project_generation != session.generation:
                raise ValueError("analysis project generation is stale")
            encoded = json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()
            fingerprint = hashlib.sha256(encoded).hexdigest()
            job_id = f"job:{request.request_id.removeprefix('request:')}"
            existing = self.jobs.get(job_id)
            if existing is not None:
                return existing
            job = AnalysisJob(
                job_id=job_id,
                project_id=request.project_id,
                generation=request.project_generation,
                input_fingerprint=fingerprint,
                profile="static-analysis",
                state=JobState.QUEUED,
                progress=0,
            )
            self.jobs[job_id] = job
        threading.Thread(
            target=self._run_analysis,
            args=(request, session, job_id),
            daemon=True,
            name=f"archcanvas-{job_id}",
        ).start()
        return job

    def _run_analysis(
        self, request: AnalysisRequest, session: ProjectSession, job_id: str
    ) -> None:
        started = datetime.now(UTC).isoformat()
        with self.lock:
            self.jobs[job_id] = self.jobs[job_id].model_copy(
                update={"state": JobState.RUNNING, "progress": 0.1, "started_at": started}
            )
        try:
            root = Path(session.root)
            config_path = root / request.config_path if request.config_path else None
            if config_path is not None:
                config_path = config_path.resolve()
                if not config_path.is_relative_to(root) or not config_path.is_file():
                    raise ValueError("analysis config escapes the project root or does not exist")
                config_bytes = config_path.read_bytes()
            else:
                config_bytes = b"{}"
            analyzed = analyze_with_adapter(
                root,
                request.entrypoint,
                request.task,
                "eval",
                config_bytes,
                config_path,
                framework=request.framework,
                pattern_packs_enabled=request.pattern_packs_enabled,
            )
            analysis_dir = self.bundle.workspace / "analyses" / job_id.removeprefix("job:")
            analysis_dir.mkdir(parents=True, exist_ok=True)
            (analysis_dir / "architecture.json").write_text(
                analyzed.architecture.model_dump_json(), encoding="utf-8"
            )
            (analysis_dir / "source-snapshot.json").write_text(
                analyzed.snapshot.model_dump_json(), encoding="utf-8"
            )
            (analysis_dir / "evidence-ledger.json").write_text(
                json.dumps(
                    [item.model_dump(mode="json") for item in analyzed.evidence],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            replacement = prepare_studio_bundle(
                analysis_dir / "architecture.json",
                self.bundle.workspace,
                write_static=False,
            )
            replacement.project_session = session.model_copy(
                update={
                    "entrypoint": request.entrypoint,
                    "framework": analyzed.snapshot.framework,
                    "task": request.task,
                    "config_path": request.config_path,
                    "config_digest": analyzed.snapshot.config_digest,
                }
            )
            pending = self.pending_projects.get(request.project_id)
            if pending is not None:
                replacement.project_discovery = pending[1]
            finished = datetime.now(UTC).isoformat()
            with self.lock:
                current = self.jobs[job_id]
                if current.state is JobState.CANCELLED:
                    return
                latest = self.pending_projects.get(request.project_id)
                if latest is not None and latest[0].generation != request.project_generation:
                    self.jobs[job_id] = current.model_copy(
                        update={"state": JobState.STALE, "progress": 1, "finished_at": finished}
                    )
                    return
                self.bundle = replacement
                replacement.write_static()
                self.jobs[job_id] = current.model_copy(
                    update={
                        "state": JobState.SUCCEEDED,
                        "progress": 1,
                        "finished_at": finished,
                        "receipt": {"status": "ok", "artifact": str(replacement.artifact_path)},
                    }
                )
        except Exception as error:  # noqa: BLE001 - background jobs must end with a receipt
            code = error.code if isinstance(error, AnalysisError) else "ANALYSIS_FAILED"
            diagnostic = Diagnostic(
                code=code if str(code).isupper() else "ANALYSIS_FAILED",
                severity="blocking",
                message=str(error),
            )
            with self.lock:
                current = self.jobs[job_id]
                if current.state is not JobState.CANCELLED:
                    self.jobs[job_id] = current.model_copy(
                        update={
                            "state": JobState.FAILED,
                            "progress": 1,
                            "finished_at": datetime.now(UTC).isoformat(),
                            "diagnostics": [diagnostic],
                        }
                    )


def create_studio_server(bundle: StudioBundle, host: str, port: int) -> StudioHTTPServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Studio only binds to a loopback address")
    if not 0 <= port <= 65535:
        raise ValueError("Studio port is outside the valid range")
    return StudioHTTPServer((host, port), bundle)
