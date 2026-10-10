"""Identify the actual runtime and assets without running a user model."""
import hashlib
import json
import shutil
import sys
from pathlib import Path
from archcanvas_authoring import module_catalog
from .canvas import canvas_operation


def diagnose() -> dict:
    from .server import project_root
    from . import __version__
    root = project_root()
    assets = []
    if root:
        for file in sorted((root / "studio/dist").rglob("*")):
            if file.is_file():
                assets.append({"path": file.relative_to(root).as_posix(), "sha256": hashlib.sha256(file.read_bytes()).hexdigest()})
    inventory = hashlib.sha256(json.dumps(assets, sort_keys=True).encode()).hexdigest()
    bundle = root / "BUNDLE-MANIFEST.json" if root else None
    version = json.loads(bundle.read_text()).get("version") if bundle and bundle.is_file() else None
    integrity = "development-bytes"
    if version:
        manifest = json.loads(bundle.read_text())
        integrity = "verified" if all((root / row["path"]).is_file() and hashlib.sha256((root / row["path"]).read_bytes()).hexdigest() == row["sha256"]
                                      for row in manifest.get("files", [])) and manifest.get("files") else "mismatch"
    try: presets = canvas_operation(root, {"action": "catalog"})["presets"]
    except ValueError: presets = None
    ready = bool(root and (root / "studio/dist/index.html").is_file() and presets is not None and integrity != "mismatch")
    return {"schemaVersion": 1, "status": "ready-local" if ready else "incomplete", "runtimeVersion": __version__,
            "releaseVersion": version, "releaseIntegrity": integrity, "distribution": "frozen-local-preview" if version else "development-checkout",
            "runtimeRoot": str(root) if root else None, "interpreter": str(Path(sys.executable).resolve()),
            "node": shutil.which("node"), "studio": {"available": bool(assets), "assets": assets, "digest": inventory},
            "catalog": {"atomicModules": len(module_catalog()["modules"]), "presets": presets},
            "modelExecution": False, "hostE2E": "not-tested", "publicationReview": "not-certified",
            "next": "Start serve --data-dir /absolute/independent-state-root, then open --root MODEL_ROOT --entry module:Class --server http://127.0.0.1:8765" if ready else "Install the complete verified release and Node.js 24+, then run doctor again."}
