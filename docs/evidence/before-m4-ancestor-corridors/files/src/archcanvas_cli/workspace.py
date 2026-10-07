"""Registered source copies and persisted exports. HTTP never accepts a source root."""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path

from archcanvas_python import analyze_project

IDENTITY = re.compile(r"[a-f0-9]{32}\Z")


class Workspace:
    def __init__(self, directory: Path, project_root: Path | None):
        self.directory = directory.resolve()
        self.project_root = project_root
        self.lock = threading.RLock()
        for name in ("projects", "exports"):
            (self.directory / name).mkdir(parents=True, exist_ok=True)

    def location(self, group: str, identity: str) -> Path:
        if not isinstance(identity, str) or not IDENTITY.fullmatch(identity):
            raise ValueError("Unknown workspace identity.")
        path = self.directory / group / identity
        if not path.resolve().is_relative_to(self.directory / group):
            raise ValueError("Workspace path escapes its registered directory.")
        return path

    def register(self, payload: dict) -> dict:
        if set(payload) != {"entry", "sources", "sourceDigest", "irDigest"}:
            raise ValueError("Register requires entry, sources and exact source/IR digests; filesystem roots are not accepted.")
        if not isinstance(payload["entry"], str) or not isinstance(payload["sources"], list) or not 1 <= len(payload["sources"]) <= 80:
            raise ValueError("A managed copy requires an entry and 1–80 source files.")
        identity = uuid.uuid4().hex
        directory = self.location("projects", identity)
        source_root = directory / "source"
        directory.mkdir(mode=0o700)
        source_root.mkdir(mode=0o700)
        paths: set[str] = set()
        total = 0
        try:
            for source in payload["sources"]:
                if not isinstance(source, dict) or set(source) != {"path", "content", "digest"}:
                    raise ValueError("Each source requires path, content and digest.")
                logical = source["path"]
                if not isinstance(logical, str) or "\\" in logical or Path(logical).is_absolute() or ".." in Path(logical).parts or Path(logical).suffix != ".py" or logical in paths:
                    raise ValueError("Source paths must be unique relative Python files without traversal.")
                if not isinstance(source["content"], str):
                    raise ValueError("Source content must be text.")
                raw = source["content"].encode("utf-8")
                # The analyzer decodes a UTF-8 BOM for AST parsing but binds to raw bytes.
                if hashlib.sha256(raw).hexdigest() != source["digest"]:
                    raw = b"\xef\xbb\xbf" + raw
                if hashlib.sha256(raw).hexdigest() != source["digest"]:
                    raise ValueError("Imported source content does not match its exact byte digest.")
                total += len(raw)
                if total > 2_000_000:
                    raise ValueError("Source corpus exceeds the 2 MB analysis budget.")
                path = source_root / logical
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                paths.add(logical)
            architecture = analyze_project(source_root, payload["entry"])
            if architecture["sourceDigest"] != payload["sourceDigest"] or architecture["irDigest"] != payload["irDigest"]:
                raise ValueError("Managed copy re-analysis differs from the imported source/IR binding; no edit is allowed.")
            (directory / "project.json").write_text(json.dumps({"id": identity, "entry": architecture["entry"], "scope": "managed-copy"}), encoding="utf-8")
            return self.project(identity)
        except Exception:
            shutil.rmtree(directory)
            raise

    def metadata(self, identity: str) -> dict:
        directory = self.location("projects", identity)
        metadata = directory / "project.json"
        if not metadata.is_file() or metadata.is_symlink():
            raise ValueError("Managed project not found.")
        result = json.loads(metadata.read_text(encoding="utf-8"))
        if not isinstance(result, dict) or set(result) != {"id", "entry", "scope"} or result["id"] != identity or result["scope"] != "managed-copy" or not isinstance(result["entry"], str):
            raise ValueError("Registered project metadata is invalid.")
        return result

    def project(self, identity: str) -> dict:
        with self.lock:
            directory = self.location("projects", identity)
            result = self.metadata(identity)
            architecture = analyze_project(directory / "source", result["entry"])
            return {**result, "architecture": architecture, "sourceDigest": architecture["sourceDigest"], "irDigest": architecture["irDigest"]}

    def source_root(self, identity: str) -> Path:
        self.metadata(identity)  # Registered identity; the caller decides when to re-analyze.
        return self.location("projects", identity) / "source"

    def export(self, document: dict, format: str, dpi: int, options: dict | None = None) -> dict:
        if format not in ("svg", "pdf", "png") or type(dpi) is not int or not 72 <= dpi <= 1200:
            raise ValueError("Export format must be svg/pdf/png and DPI an integer within 72–1200.")
        if self.project_root is None or shutil.which("node") is None:
            raise ValueError("Export requires the formal checkout and Node 24+ for its authoritative Scene renderer.")
        options = {} if options is None else options
        if not isinstance(options, dict) or set(options) - {"nodeId", "widthMm"}:
            raise ValueError("Export options accept only an exact detail nodeId and physical widthMm.")
        if "nodeId" in options and (not isinstance(options["nodeId"], str) or not 1 <= len(options["nodeId"]) <= 500):
            raise ValueError("Detail nodeId must be an exact nonempty canonical identity.")
        if "widthMm" in options and (type(options["widthMm"]) not in (int, float) or not 25 <= options["widthMm"] <= 1000 or not math.isfinite(options["widthMm"])):
            raise ValueError("Physical widthMm must be a number within 25–1000 mm.")
        identity = uuid.uuid4().hex
        directory = self.location("exports", identity)
        directory.mkdir(mode=0o700)
        input_path = directory / "document.json"
        output_path = directory / f"figure.{format}"
        try:
            input_path.write_text(json.dumps(document, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            command = [shutil.which("node"), str(self.project_root / "scripts/export_canvas.mjs"), "--document", str(input_path), "--output", str(output_path), "--format", format, "--dpi", str(dpi), "--python", sys.executable]
            if "nodeId" in options:
                command.extend(["--scope-node", options["nodeId"]])
            if "widthMm" in options:
                command.extend(["--width-mm", str(options["widthMm"])])
            try:
                completed = subprocess.run(command, cwd=self.project_root, capture_output=True, text=True, timeout=45)
            except subprocess.TimeoutExpired as exc:
                raise ValueError("Export exceeded its 45 second budget; no completed artifact was published.") from exc
            if completed.returncode != 0:
                raise ValueError("Export failed: " + completed.stderr[-1500:])
            receipt = json.loads(Path(f"{output_path}.receipt.json").read_text(encoding="utf-8"))
            return {"id": identity, "format": format, "url": f"/api/exports/{identity}/figure.{format}", "receiptUrl": f"/api/exports/{identity}/receipt", "receipt": receipt}
        except Exception:
            shutil.rmtree(directory)
            raise

    def artifact(self, identity: str, name: str) -> tuple[bytes, str]:
        directory = self.location("exports", identity)
        if name == "receipt":
            receipts = list(directory.glob("figure.*.receipt.json"))
            if len(receipts) != 1:
                raise ValueError("Export receipt not found.")
            return receipts[0].read_bytes(), "application/json"
        mimes = {"figure.svg": "image/svg+xml", "figure.pdf": "application/pdf", "figure.png": "image/png"}
        if name not in mimes or not (directory / name).is_file():
            raise ValueError("Export artifact not found.")
        return (directory / name).read_bytes(), mimes[name]
