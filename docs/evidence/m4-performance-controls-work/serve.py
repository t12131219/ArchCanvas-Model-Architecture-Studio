"""Independent loopback control routes over an unchanged formal Studio build.

Run with the formal .venv/bin/python. No user model is imported or executed.
Each launch owns a fresh private document/workspace store and emits provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import mimetypes
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FORMAL_SRC = (ROOT / "src").resolve()
ROUTES = {
    "/__m4_controls/": "control.html",
    "/__m4_controls/control": "control.html",
    "/__m4_controls/studio": "studio.html",
    "/__m4_controls/controller.css": "controller.css",
    "/__m4_controls/controller.mjs": "controller.mjs",
    "/__m4_controls/observer.mjs": "observer.mjs",
    "/__m4_controls/measurement-contract.json": "measurement-contract.json",
}
PACKAGE_NAMES = (
    "archcanvas_cli", "archcanvas_python", "archcanvas_transactions",
    "archcanvas_publication", "archcanvas_runtime", "archcanvas_authoring",
)


def fingerprint(path: Path) -> dict:
    body = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
    }


def verify_formal_identity() -> dict:
    if not (ROOT / "pyproject.toml").is_file() or not FORMAL_SRC.is_dir():
        raise RuntimeError("This helper must reside inside the formal ArchCanvas checkout")
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise RuntimeError("Use the formal .venv/bin/python; no alternate/prototype interpreter fallback")
    packages = []
    for name in PACKAGE_NAMES:
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(FORMAL_SRC / name):
            raise RuntimeError(f"Unexpected package origin for {name}: {path}")
        packages.append({"name": name, "origin": str(path), "binding": fingerprint(path)})
    return {
        "projectRoot": str(ROOT), "formalSourceRoot": str(FORMAL_SRC),
        "interpreterArgument": sys.executable,
        "interpreterResolved": str(Path(sys.executable).resolve()),
        "interpreterBinding": fingerprint(Path(sys.executable).resolve()),
        "sysPrefix": sys.prefix, "pythonVersion": sys.version, "packages": packages,
        "modelsImportedOrExecuted": False,
    }


def context(provenance: dict, studio_dir: Path, store: Path) -> dict:
    assets = [fingerprint(path) for path in sorted(studio_dir.rglob("*")) if path.is_file()]
    helpers = [HERE / filename for filename in ["serve.py", "control.html", "studio.html", "controller.css", "controller.mjs", "observer.mjs", "measurement-contract.json"]]
    return {
        "protocol": "archcanvas-performance-controls-context/1",
        "capturedAt": datetime.now(timezone.utc).isoformat(), "provenance": provenance,
        "formalStudioAssetsUnmodifiedByHelper": True, "productionAssets": assets,
        "helperSources": [fingerprint(path) for path in helpers],
        "formalServerSource": fingerprint(FORMAL_SRC / "archcanvas_cli/server.py"),
        "independentStore": str(store), "sourceAnalysisDoesNotExecuteModels": True,
        "humanParticipants": 0, "presentedPerformanceCertified": False,
        "limitations": ["Same-origin Studio iframe is a distinct measured environment",
                        "New observer is independent of historical observer measurements",
                        "Browser callbacks/DOM observations do not establish actual presentation",
                        "Resolved glyph font bytes and fixed CPU/GPU/display environment remain unknown"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0, help="fresh loopback port; 0 selects an available port")
    parser.add_argument("--describe-only", action="store_true", help="read-only provenance and bindings without a listener/store")
    parser.add_argument("--store-parent", type=Path, default=ROOT / ".archcanvas/m4-performance-controls-sessions")
    args = parser.parse_args()
    provenance = verify_formal_identity()
    studio_dir = (ROOT / "studio/dist").resolve()
    if not (studio_dir / "index.html").is_file():
        raise RuntimeError("The actual formal Studio build must already exist; this helper never builds")
    if args.describe_only:
        print(json.dumps(context(provenance, studio_dir, args.store_parent.resolve() / "NOT-CREATED-DESCRIBE-ONLY"), ensure_ascii=False, indent=2))
        return
    # Fresh, exclusive session store. Existing user/service documents are never reused.
    store_parent = args.store_parent.resolve()
    if not store_parent.is_relative_to(ROOT / ".archcanvas"):
        raise RuntimeError("The independent store parent must be inside the formal .archcanvas directory")
    store = store_parent / uuid.uuid4().hex / "documents"
    store.mkdir(parents=True, exist_ok=False)
    from archcanvas_cli.server import ArchCanvasServer, Handler

    class ControlHandler(Handler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if not path.startswith("/__m4_controls/"):
                return super().do_GET()
            if not self.guard():
                return
            if path == "/__m4_controls/context.json":
                return self.send_json(200, context(provenance, self.server.studio_dir, store))
            filename = ROUTES.get(path)
            if filename is None:
                return self.send_json(404, {"error": "Unknown independent control route"})
            file = HERE / filename
            body = file.read_bytes()
            content_type = "text/javascript" if file.suffix == ".mjs" else mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-src 'self'; connect-src 'self'; frame-ancestors 'self'")
            self.end_headers()
            self.wfile.write(body)

    with ArchCanvasServer(("127.0.0.1", args.port), data_dir=store, studio_dir=studio_dir) as server:
        server.RequestHandlerClass = ControlHandler
        port = server.server_address[1]
        print(json.dumps({"protocol": "archcanvas-performance-controls-launch/1",
                          "utc": datetime.now(timezone.utc).isoformat(),
                          "controlUrl": f"http://127.0.0.1:{port}/__m4_controls/control",
                          "studioUrl": f"http://127.0.0.1:{port}/__m4_controls/studio",
                          "store": str(store), "context": context(provenance, studio_dir, store)},
                         ensure_ascii=False, indent=2), flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
