"""Opt-in loopback measurement pages; serve unmodified formal Studio assets.

This development-only service uses independent persistence. It adds read-only
measurement routes to the formal service; it does not dispatch product input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from archcanvas_cli.server import ArchCanvasServer, Handler

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = Path(__file__).resolve().parent / "m4_input_support"
ROUTES = {
    "/__m4/": (SUPPORT / "harness.html", "text/html; charset=utf-8"),
    "/__m4/harness.mjs": (SUPPORT / "harness.mjs", "text/javascript; charset=utf-8"),
    "/__m4/control": (SUPPORT / "control.html", "text/html; charset=utf-8"),
    "/__m4/control.mjs": (SUPPORT / "control.mjs", "text/javascript; charset=utf-8"),
    "/__m4/observer.mjs": (ROOT / "scripts/m4_input_observer.mjs", "text/javascript; charset=utf-8"),
}


def fingerprint(path: Path) -> dict:
    body = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def context(studio_dir: Path) -> dict:
    assets = [fingerprint(path) for path in sorted(studio_dir.rglob("*")) if path.is_file()]
    probes = [Path(__file__).resolve(), *sorted(SUPPORT.glob("*")), ROOT / "scripts/m4_input_observer.mjs"]
    return {
        "schema": "archcanvas-measurement-context/1",
        "formalStudioUnmodified": True,
        "productionAssets": assets,
        "probeSources": [fingerprint(path) for path in probes if path.is_file()],
        "limits": ["Agent-operated diagnostic; no human study or visual approval",
                   "Same-origin iframe adds measurement overhead",
                   "Continuous input to DOM observation is a proxy, never native paint latency",
                   "No independently locked resolved font environment"],
    }


class MeasurementHandler(Handler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if not path.startswith("/__m4/"):
            return super().do_GET()
        if not self.guard():
            return
        if path == "/__m4/context.json":
            return self.send_json(200, context(self.server.studio_dir))
        route = ROUTES.get(path)
        if route is None:
            return self.send_json(404, {"error": "Unknown measurement route."})
        file, mime = route
        if not file.is_file():
            return self.send_json(503, {"error": "Measurement component is not present."})
        body = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-src 'self'; frame-ancestors 'self'")
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8773)
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".archcanvas/m4-input-observation/documents")
    args = parser.parse_args()
    with ArchCanvasServer(("127.0.0.1", args.port), data_dir=args.data_dir, studio_dir=ROOT / "studio/dist") as server:
        server.RequestHandlerClass = MeasurementHandler
        print(f"Measurement pages: http://127.0.0.1:{server.server_address[1]}/__m4/", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
