from __future__ import annotations

import hashlib
import json
import os
import secrets
import signal
import subprocess
import sys
import threading
from copy import deepcopy
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from archcanvas_core.models import (
    AnalysisJob,
    AnalysisRequest,
    Diagnostic,
    DraftGraphDocument,
    JobState,
    PatchBatch,
    ProjectSession,
    TransactionState,
    VisualPatch,
)

from .bundle import StudioBundle, prepare_studio_bundle
from .document import apply_patch, apply_patch_batch, redo_patch, undo_patch
from .operations import (
    alignment_batch,
    auto_layout_batch,
    auto_route_batch,
    run_validation,
    studio_fingerprint,
)
from .project import (
    browse_directories,
    create_project_session,
    discover_conda_environments,
    discover_project,
    resolve_conda_environment,
)


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

    def _studio_state(self) -> dict[str, object]:
        state = self.server.bundle.state()
        state["session_nonce"] = self.server.session_nonce
        state["jobs"] = [job.model_dump(mode="json") for job in self.server.jobs.values()]
        return state

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
        if parsed.path == "/api/environments/conda":
            self._json(discover_conda_environments())
            return
        if parsed.path == "/api/directories":
            try:
                requested = parse_qs(parsed.query).get("path", [None])[0]
                self._json(browse_directories(Path(requested) if requested else None))
            except (TypeError, ValueError) as error:
                self._error(error)
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
                    environment_path = payload.get("environment_path")
                    environment = (
                        resolve_conda_environment(str(environment_path))
                        if environment_path
                        else None
                    )
                    generation = self.server.next_project_generation()
                    session = create_project_session(
                        root,
                        self.server.bundle.workspace,
                        generation=generation,
                        entrypoint=str(payload["entrypoint"]) if payload.get("entrypoint") else None,
                        framework=str(payload.get("framework", "auto")),
                        task=str(payload.get("task", "inference")),
                        config_path=str(payload["config_path"]) if payload.get("config_path") else None,
                        environment=environment,
                    )
                    discovery = discover_project(Path(session.root))
                    discovery["environment"] = environment
                    self.server.activate_project(session, discovery)
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
                    self.server.layout_candidates.clear()
                    self._json(self.server.bundle.state())
                    return
                if self.path == "/api/layout-mode":
                    self.server.bundle.set_layout_mode(str(payload.get("layout_mode", "")))
                    self.server.layout_candidates.clear()
                    self._json(self.server.bundle.state())
                    return
                if self.path == "/api/layout-candidates":
                    self._json({"candidates": self.server.create_layout_candidates()})
                    return
                if self.path.startswith("/api/layout-candidates/") and self.path.endswith(
                    "/apply"
                ):
                    candidate_id = self.path[
                        len("/api/layout-candidates/") : -len("/apply")
                    ]
                    self._json(self.server.apply_layout_candidate(candidate_id))
                    return
                if self.path == "/api/patch":
                    patch = VisualPatch.model_validate(payload)
                    scenes = {
                        scene.scene_id: scene
                        for scene in self.server.bundle.base_scenes.values()
                    }
                    changed = apply_patch(
                        document, patch, scenes, enforce_containment=True
                    )
                elif self.path == "/api/patch-batch":
                    batch = PatchBatch.model_validate(payload)
                    scenes = {
                        scene.scene_id: scene
                        for scene in self.server.bundle.base_scenes.values()
                    }
                    changed = apply_patch_batch(
                        document, batch, scenes, enforce_containment=True
                    )
                elif self.path == "/api/layout":
                    scene = next(iter(self.server.bundle.materialized_scenes().values()))
                    baseline_scene = next(iter(self.server.bundle.base_scenes.values()))
                    try:
                        batch = auto_layout_batch(
                            scene,
                            baseline_scene=baseline_scene,
                            pinned_ids=set(
                                self.server.bundle.state()["view_state"]["pinned_node_ids"]
                            ),
                            batch_id=str(payload["batch_id"]),
                        )
                    except ValueError as error:
                        if str(error) != "the current scene is already at its deterministic layout":
                            raise
                        self._json(self.server.bundle.state())
                        return
                    scenes = {
                        item.scene_id: item for item in self.server.bundle.base_scenes.values()
                    }
                    changed = apply_patch_batch(
                        document, batch, scenes, enforce_containment=True
                    )
                elif self.path == "/api/route":
                    scene = next(iter(self.server.bundle.materialized_scenes().values()))
                    batch = auto_route_batch(
                        scene,
                        batch_id=str(payload["batch_id"]),
                        strategy=str(payload.get("strategy", "avoid")),
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
                    changed = apply_patch_batch(
                        document, batch, scenes, enforce_containment=True
                    )
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
                elif self.path == "/api/proposal/draft-edge":
                    self.server.bundle.propose_draft_edge(payload)
                    self._json(self.server.bundle.state())
                    return
                elif self.path == "/api/proposal/delete-node/preview":
                    self._json(
                        {
                            "impact": self.server.bundle.canonical_delete_impact(
                                str(payload["node_id"])
                            )
                        }
                    )
                    return
                elif self.path == "/api/proposal/delete-node":
                    self.server.bundle.propose_canonical_delete(payload)
                    self._json(self.server.bundle.state())
                    return
                elif self.path == "/api/draft/node/delete":
                    self.server.bundle.delete_draft_node(str(payload["node_id"]))
                    self._json(self.server.bundle.state())
                    return
                elif self.path == "/api/draft/edge/delete":
                    self.server.bundle.delete_draft_edge(str(payload["edge_id"]))
                    self._json(self.server.bundle.state())
                    return
                elif self.path == "/api/draft/delete-intent/discard":
                    self.server.bundle.discard_canonical_delete(str(payload["intent_id"]))
                    self._json(self.server.bundle.state())
                    return
                elif self.path == "/api/source-workspace/open":
                    buffer = self.server.bundle.open_source_buffer(str(payload["path"]))
                    self._json({"buffer": buffer, "state": self._studio_state()})
                    return
                elif self.path == "/api/source-workspace/save":
                    buffer = self.server.bundle.save_source_buffer(
                        str(payload["path"]),
                        str(payload["content"]),
                        str(payload["base_sha256"]),
                        int(payload["expected_revision"]),
                    )
                    self._json({"buffer": buffer, "state": self._studio_state()})
                    return
                elif self.path == "/api/source-workspace/buffer/discard":
                    self.server.bundle.discard_source_buffer(
                        str(payload["path"]), int(payload["expected_revision"])
                    )
                    self._json(self.server.bundle.state())
                    return
                elif self.path == "/api/source-workspace/validate":
                    self.server.bundle.prepare_source_workspace()
                    self._json(self.server.bundle.state())
                    return
                elif self.path == "/api/source-workspace/discard":
                    self.server.bundle.discard_source_workspace()
                    self._json(self.server.bundle.state())
                    return
                elif self.path == "/api/transaction/commit":
                    job = self.server.commit_transaction_and_reanalyze()
                    state = self.server.bundle.state()
                    state["reanalysis_job_id"] = job.job_id if job is not None else None
                    self._json(state)
                    return
                elif self.path == "/api/transaction/discard":
                    self.server.bundle.discard_parameter()
                    self._json(self.server.bundle.state())
                    return
                elif self.path == "/api/validation-runs":
                    job = self.server.start_validation(
                        str(payload.get("profile", "fast-static")),
                        runtime_execution_authorized=bool(
                            payload.get("runtime_execution_authorized", False)
                        ),
                    )
                    self._json(job, HTTPStatus.ACCEPTED)
                    return
                elif self.path.startswith("/api/jobs/") and self.path.endswith("/cancel"):
                    job_id = self.path[len("/api/jobs/") : -len("/cancel")]
                    job = self.server.jobs.get(job_id)
                    if job is None:
                        self.send_error(HTTPStatus.NOT_FOUND)
                        return
                    self._json(self.server.cancel_job(job_id))
                    return
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self.server.bundle.save_document(changed)
                self.server.layout_candidates.clear()
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
        self.job_processes: dict[str, subprocess.Popen[str]] = {}
        self.job_cancellations: dict[str, threading.Event] = {}
        self.project_generation = bundle.project_session.generation
        self.validation_generation = bundle.validation_generation
        self.layout_candidates: dict[str, tuple[str, PatchBatch]] = {}
        self.active_project_key = (
            bundle.project_session.project_id,
            bundle.project_session.generation,
        )
        super().__init__(address, StudioRequestHandler)

    def next_project_generation(self) -> int:
        with self.lock:
            self.project_generation += 1
            return self.project_generation

    def activate_project(
        self, session: ProjectSession, discovery: dict[str, object]
    ) -> None:
        """Select one project generation and invalidate every older in-flight job."""
        with self.lock:
            self.active_project_key = (session.project_id, session.generation)
            self.pending_projects = {session.project_id: (session, discovery)}
            self.layout_candidates.clear()
            for job_id, job in list(self.jobs.items()):
                if job.state not in {
                    JobState.QUEUED,
                    JobState.RUNNING,
                    JobState.CANCELLING,
                }:
                    continue
                if (job.project_id, job.generation) != self.active_project_key:
                    self._cancel_job_locked(job_id, stale=True)

    def _terminate_process_locked(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGTERM)
                return
            except ProcessLookupError:
                return
        process.terminate()

    def _finish_cancelled_locked(self, job_id: str) -> AnalysisJob:
        current = self.jobs[job_id]
        state = JobState.STALE if current.state is JobState.STALE else JobState.CANCELLED
        finished = current.model_copy(
            update={
                "state": state,
                "progress": 1,
                "finished_at": datetime.now(UTC).isoformat(),
            }
        )
        self.jobs[job_id] = finished
        return finished

    def _cancel_job_locked(self, job_id: str, *, stale: bool = False) -> AnalysisJob:
        job = self.jobs[job_id]
        if job.state not in {JobState.QUEUED, JobState.RUNNING, JobState.CANCELLING}:
            return job
        cancellation = self.job_cancellations.setdefault(job_id, threading.Event())
        cancellation.set()
        process = self.job_processes.get(job_id)
        if process is not None:
            self._terminate_process_locked(process)
        state = JobState.STALE if stale else JobState.CANCELLING
        update: dict[str, object] = {"state": state}
        if stale:
            update.update(
                {
                    "progress": 1,
                    "finished_at": datetime.now(UTC).isoformat(),
                }
            )
        changed = job.model_copy(update=update)
        self.jobs[job_id] = changed
        return changed

    def cancel_job(self, job_id: str) -> AnalysisJob:
        with self.lock:
            if job_id not in self.jobs:
                raise ValueError("job does not exist")
            return self._cancel_job_locked(job_id)

    def create_layout_candidates(self) -> list[dict[str, object]]:
        with self.lock:
            candidates = self.bundle.layout_candidates()
            self.layout_candidates = {
                str(payload["candidate_id"]): (
                    str(payload["input_fingerprint"]),
                    batch,
                )
                for payload, batch in candidates
            }
            return [payload for payload, _ in candidates]

    def apply_layout_candidate(self, candidate_id: str) -> dict[str, object]:
        with self.lock:
            candidate = self.layout_candidates.get(candidate_id)
            if candidate is None:
                raise ValueError("layout candidate does not exist or has expired")
            fingerprint, batch = candidate
            if fingerprint != studio_fingerprint(self.bundle):
                self.layout_candidates.clear()
                raise ValueError("layout candidate input fingerprint is stale")
            scenes = {
                scene.scene_id: scene for scene in self.bundle.base_scenes.values()
            }
            changed = apply_patch_batch(
                self.bundle.document, batch, scenes, enforce_containment=True
            )
            self.bundle.save_document(changed)
            self.layout_candidates.clear()
            return self.bundle.state()

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
            if (request.project_id, request.project_generation) != self.active_project_key:
                raise ValueError("analysis does not target the active project generation")
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
            self.job_cancellations[job_id] = threading.Event()
            discovery = deepcopy(pending[1]) if pending is not None else {}
            workspace = self.bundle.workspace
        threading.Thread(
            target=self._run_analysis,
            args=(request, session, discovery, workspace, job_id),
            daemon=True,
            name=f"archcanvas-{job_id}",
        ).start()
        return job

    def commit_transaction_and_reanalyze(self) -> AnalysisJob | None:
        with self.lock:
            self.bundle.commit_parameter()
            transaction = self.bundle.active_transaction
            if transaction is None or transaction.state is not TransactionState.COMMITTED:
                return None
            project = self.bundle.project_session
            request = AnalysisRequest(
                project_id=project.project_id,
                project_generation=project.generation,
                entrypoint=project.entrypoint or self.bundle.snapshot.entrypoint,
                framework=project.framework,
                task=project.task,
                config_path=project.config_path,
                execution_mode="static",
                pattern_packs_enabled=True,
                request_id=f"request:reanalysis.{secrets.token_hex(10)}",
            )
            return self.start_analysis(request)

    def start_validation(
        self, profile: str, *, runtime_execution_authorized: bool = False
    ) -> AnalysisJob:
        with self.lock:
            if profile not in {"fast-static", "publication", "full", "runtime-replay"}:
                raise ValueError("unknown validation profile")
            if profile == "runtime-replay" and not runtime_execution_authorized:
                raise ValueError("runtime replay requires explicit execution authorization")
            target_bundle = self.bundle
            validation_input = deepcopy(target_bundle)
            project = target_bundle.project_session
            request_id = secrets.token_hex(10)
            job_id = f"job:validation.{request_id}"
            fingerprint = studio_fingerprint(validation_input)
            job = AnalysisJob(
                job_id=job_id,
                project_id=project.project_id,
                generation=project.generation,
                input_fingerprint=fingerprint,
                profile=f"validation:{profile}",
                state=JobState.QUEUED,
                progress=0,
            )
            self.jobs[job_id] = job
            self.job_cancellations[job_id] = threading.Event()
            self.validation_generation += 1
            validation_generation = self.validation_generation
        threading.Thread(
            target=self._run_validation,
            args=(
                validation_input,
                target_bundle,
                profile,
                runtime_execution_authorized,
                validation_generation,
                job_id,
            ),
            daemon=True,
            name=f"archcanvas-{job_id}",
        ).start()
        return job

    def _run_validation(
        self,
        validation_input: StudioBundle,
        target_bundle: StudioBundle,
        profile: str,
        runtime_execution_authorized: bool,
        validation_generation: int,
        job_id: str,
    ) -> None:
        with self.lock:
            if self.job_cancellations[job_id].is_set():
                self._finish_cancelled_locked(job_id)
                return
            self.jobs[job_id] = self.jobs[job_id].model_copy(
                update={
                    "state": JobState.RUNNING,
                    "progress": 0.1,
                    "started_at": datetime.now(UTC).isoformat(),
                }
            )
        try:
            validation = run_validation(
                validation_input,
                profile,
                validation_generation,
                runtime_execution_authorized=runtime_execution_authorized,
            )
            with self.lock:
                current = self.jobs[job_id]
                cancelled = self.job_cancellations[job_id].is_set()
                active = self.bundle is target_bundle and (
                    current.project_id,
                    current.generation,
                ) == self.active_project_key
                if cancelled:
                    state = (
                        JobState.STALE
                        if current.state is JobState.STALE
                        else JobState.CANCELLED
                    )
                    self.jobs[job_id] = current.model_copy(
                        update={
                            "state": state,
                            "progress": 1,
                            "finished_at": datetime.now(UTC).isoformat(),
                        }
                    )
                elif not active:
                    self.jobs[job_id] = current.model_copy(
                        update={
                            "state": JobState.STALE,
                            "progress": 1,
                            "finished_at": datetime.now(UTC).isoformat(),
                        }
                    )
                else:
                    target_bundle.validation_generation = max(
                        target_bundle.validation_generation,
                        validation_generation,
                    )
                    target_bundle.validation_runs.append(validation)
                    target_bundle.validation_runs.sort(key=lambda run: run.generation)
                    validation_path = (
                        target_bundle.workspace
                        / "validations"
                        / f"{validation.validation_id.removeprefix('validation:')}.json"
                    )
                    validation_path.parent.mkdir(parents=True, exist_ok=True)
                    validation_path.write_text(
                        validation.model_dump_json() + "\n", encoding="utf-8"
                    )
                    self.jobs[job_id] = current.model_copy(
                        update={
                            "state": JobState.SUCCEEDED,
                            "progress": 1,
                            "finished_at": datetime.now(UTC).isoformat(),
                            "receipt": {
                                "status": validation.state.value,
                                "validation_id": validation.validation_id,
                            },
                        }
                    )
        except Exception as error:  # noqa: BLE001
            self._finish_failed_job(job_id, "VALIDATION_FAILED", error)

    def _run_analysis(
        self,
        request: AnalysisRequest,
        session: ProjectSession,
        discovery: dict[str, object],
        workspace: Path,
        job_id: str,
    ) -> None:
        started = datetime.now(UTC).isoformat()
        with self.lock:
            cancellation = self.job_cancellations[job_id]
            if cancellation.is_set():
                self._finish_cancelled_locked(job_id)
                return
            self.jobs[job_id] = self.jobs[job_id].model_copy(
                update={"state": JobState.RUNNING, "progress": 0.1, "started_at": started}
            )
        try:
            root = Path(session.root)
            selected = next(
                (
                    item
                    for item in discovery.get("entrypoints", [])
                    if item.get("entrypoint") == request.entrypoint
                ),
                None,
            )
            analysis_root = root / str(selected.get("analysis_root", ".")) if selected else root
            analysis_entrypoint = str(selected.get("analysis_entrypoint", request.entrypoint)) if selected else request.entrypoint
            selected_config = request.config_path
            if selected is not None and selected_config is not None:
                if selected_config not in selected.get("config_paths", []):
                    raise ValueError("selected config is outside the entrypoint analysis scope")
                selected_config = str(
                    Path(selected_config).relative_to(Path(selected.get("analysis_root", ".")))
                )
            config_path = analysis_root / selected_config if selected_config else None
            if config_path is not None:
                config_path = config_path.resolve()
                if not config_path.is_relative_to(root) or not config_path.is_file():
                    raise ValueError("analysis config escapes the project root or does not exist")
            analysis_dir = workspace / "analyses" / job_id.removeprefix("job:")
            command = [
                sys.executable,
                "-m",
                "archcanvas_engine.cli",
                "analyze",
                "--project",
                str(analysis_root),
                "--entry",
                analysis_entrypoint,
                "--framework",
                request.framework,
                "--task",
                request.task,
                "--mode",
                "eval",
                "--out",
                str(analysis_dir),
                "--json",
            ]
            if config_path is not None:
                command.extend(["--config", str(config_path)])
            if not request.pattern_packs_enabled:
                command.append("--no-pattern-packs")
            source_root = str(Path(__file__).resolve().parents[1])
            environment = dict(os.environ)
            environment["PYTHONPATH"] = os.pathsep.join(
                part
                for part in (source_root, environment.get("PYTHONPATH"))
                if part
            )
            process_options: dict[str, object] = {}
            if os.name == "posix":
                process_options["start_new_session"] = True
            process = subprocess.Popen(  # type: ignore[arg-type]
                command,
                cwd=analysis_root,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                **process_options,
            )
            with self.lock:
                self.job_processes[job_id] = process
                if cancellation.is_set():
                    self._terminate_process_locked(process)
            stdout, stderr = process.communicate()
            with self.lock:
                self.job_processes.pop(job_id, None)
            if cancellation.is_set():
                with self.lock:
                    self._finish_cancelled_locked(job_id)
                return
            receipt = json.loads(stdout.strip().splitlines()[-1]) if stdout.strip() else {}
            if process.returncode != 0:
                diagnostic = next(iter(receipt.get("diagnostics", [])), {})
                raise ValueError(
                    diagnostic.get("message")
                    or stderr.strip().splitlines()[-1]
                    or f"analysis subprocess exited with code {process.returncode}"
                )
            receipt_details = dict(receipt.get("details", {}))
            receipt["details"] = {
                **receipt_details,
                "analysis_python": sys.executable,
                "target_environment_python": session.python_executable,
                "target_environment_usage": "runtime-only",
            }
            replacement = prepare_studio_bundle(
                analysis_dir / "architecture.json",
                workspace,
                write_static=False,
                replace_stale_bindings=True,
            )
            replacement.project_session = session.model_copy(
                update={
                    "entrypoint": request.entrypoint,
                    "framework": replacement.snapshot.framework,
                    "task": request.task,
                    "config_path": request.config_path,
                    "config_digest": replacement.snapshot.config_digest,
                }
            )
            replacement.project_discovery = discovery
            finished = datetime.now(UTC).isoformat()
            with self.lock:
                current = self.jobs[job_id]
                if cancellation.is_set() or current.state is JobState.CANCELLING:
                    self._finish_cancelled_locked(job_id)
                    return
                if (request.project_id, request.project_generation) != self.active_project_key:
                    self.jobs[job_id] = current.model_copy(
                        update={"state": JobState.STALE, "progress": 1, "finished_at": finished}
                    )
                    return
                self.bundle = replacement
                self.layout_candidates.clear()
                replacement.write_static()
                self.jobs[job_id] = current.model_copy(
                    update={
                        "state": JobState.SUCCEEDED,
                        "progress": 1,
                        "finished_at": finished,
                        "receipt": {
                            **receipt,
                            "artifact": str(replacement.artifact_path),
                        },
                    }
                )
        except Exception as error:  # noqa: BLE001 - background jobs must end with a receipt
            self._finish_failed_job(job_id, "ANALYSIS_FAILED", error)
        finally:
            with self.lock:
                self.job_processes.pop(job_id, None)

    def _finish_failed_job(self, job_id: str, code: str, error: Exception) -> None:
        diagnostic = Diagnostic(
            code=code,
            severity="blocking",
            message=str(error),
        )
        with self.lock:
            current = self.jobs[job_id]
            if current.state in {JobState.CANCELLED, JobState.STALE}:
                return
            if self.job_cancellations.get(job_id, threading.Event()).is_set():
                self.jobs[job_id] = current.model_copy(
                    update={
                        "state": JobState.CANCELLED,
                        "progress": 1,
                        "finished_at": datetime.now(UTC).isoformat(),
                    }
                )
                return
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
