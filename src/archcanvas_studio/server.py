from __future__ import annotations

import json
import sys
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from archcanvas_core.models import VisualPatch

from .bundle import StudioBundle
from .document import apply_patch, redo_patch, undo_patch


class StudioRequestHandler(SimpleHTTPRequestHandler):
    server: StudioHTTPServer

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        server = args[2]
        super().__init__(*args, directory=str(server.bundle.static_dir), **kwargs)

    def log_message(self, format: str, *args: object) -> None:
        print(f"studio: {format % args}", file=sys.stderr)

    def _json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
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

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            with self.server.lock:
                self._json(self.server.bundle.state())
            return
        if parsed.path == "/api/export":
            level = parse_qs(parsed.query).get("level", ["L1"])[0].upper()
            try:
                with self.server.lock:
                    payload = self.server.bundle.export_svg(level).encode()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="archcanvas-{level}.svg"')
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except ValueError as error:
                self._error(error)
            return
        super().do_GET()

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1_000_000:
                raise ValueError("request body exceeds the Studio limit")
            raw = self.rfile.read(length)
            payload = json.loads(raw or b"{}")
            with self.server.lock:
                document = self.server.bundle.document
                if self.path == "/api/patch":
                    patch = VisualPatch.model_validate(payload)
                    scenes = {
                        scene.scene_id: scene
                        for scene in self.server.bundle.base_scenes.values()
                    }
                    changed = apply_patch(document, patch, scenes)
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
                elif self.path == "/api/transaction/commit":
                    self.server.bundle.commit_parameter()
                    self._json(self.server.bundle.state())
                    return
                elif self.path == "/api/transaction/discard":
                    self.server.bundle.discard_parameter()
                    self._json(self.server.bundle.state())
                    return
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self.server.bundle.save_document(changed)
                self._json(self.server.bundle.state())
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self._error(error)


class StudioHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], bundle: StudioBundle):
        self.bundle = bundle
        self.lock = threading.RLock()
        super().__init__(address, StudioRequestHandler)


def create_studio_server(bundle: StudioBundle, host: str, port: int) -> StudioHTTPServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Studio only binds to a loopback address")
    if not 0 <= port <= 65535:
        raise ValueError("Studio port is outside the valid range")
    return StudioHTTPServer((host, port), bundle)
