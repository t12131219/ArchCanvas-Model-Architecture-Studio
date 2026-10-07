#!/usr/bin/env python3
"""Run the small, repeatable M5 beta demo/export preflight.

This command prepares a fresh document from a formal fixture, runs the real
export adapter at the two planned paper widths, and writes one JSON receipt.
It deliberately reports missing Cairo/raster conversion and unresolved font
embedding as limitations; a green receipt is not a human demo or publication
approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, cwd: Path = ROOT, timeout: float = 60) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        detail = (result.stdout + result.stderr).strip()
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{detail}")
    return result


def json_command(python: str, source: str, *args: str, isolated: bool = True) -> Any:
    flags = [python]
    if isolated:
        flags += ["-I", "-B"]
    flags += ["-c", source, *args]
    return json.loads(run(flags).stdout)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_receipt(artifact: Path, receipt_path: Path, *, width: int, fmt: str) -> dict[str, Any]:
    receipt = json.loads(receipt_path.read_text())
    actual_digest = sha256(artifact)
    errors: list[str] = []
    if receipt.get("outputDigest") != actual_digest:
        errors.append("receipt outputDigest does not match the artifact")
    if receipt.get("widthMm") != width:
        errors.append(f"receipt widthMm is {receipt.get('widthMm')!r}, expected {width}")
    if receipt.get("format") != fmt:
        errors.append("receipt format does not match the requested artifact")
    if not receipt.get("geometryVerified"):
        errors.append("publication geometry was not verified")
    data = artifact.read_bytes()
    if fmt == "svg":
        root = ET.fromstring(data)
        actual_width = float(root.get("width", "0").removesuffix("mm"))
        actual_height = float(root.get("height", "0").removesuffix("mm"))
        if abs(actual_width - width) > .0001 or abs(actual_height - receipt.get("heightMm", 0)) > .0001:
            errors.append("actual SVG physical dimensions do not match its receipt")
    elif fmt == "pdf":
        match = re.search(rb"/MediaBox\s*\[([^\]]+)\]", data)
        dimensions = [float(value) for value in match.group(1).split()] if match else []
        if len(dimensions) != 4 or abs(dimensions[2] - dimensions[0] - width / 25.4 * 72) > .05 or abs(dimensions[3] - dimensions[1] - receipt.get("heightMm", 0) / 25.4 * 72) > .05:
            errors.append("actual PDF physical dimensions do not match its receipt")
    elif fmt == "png":
        dimensions = list(struct.unpack(">II", data[16:24])) if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24 else []
        wanted = [round(width / 25.4 * receipt.get("dpi", 0)), round(receipt.get("heightMm", 0) / 25.4 * receipt.get("dpi", 0))]
        if dimensions != receipt.get("pixelDimensions") or dimensions != wanted:
            errors.append("actual PNG pixel dimensions do not match its receipt")
    preflight = receipt.get("physicalPreflight") or {}
    for field in ("minTextPt", "nodeLabelPt", "minMainLinePt", "heightMm"):
        value = preflight.get(field)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            errors.append(f"physicalPreflight.{field} is missing")
    fonts = receipt.get("fonts") or {}
    coverage = (fonts.get("glyphCoverage") or {}).get("status", "not-checked-text-svg" if fmt == "svg" else None)
    # Text SVG intentionally retains family references. Cairo performs a
    # coverage check only when producing PDF/PNG; keep that distinction.
    if coverage not in {"passed", "not-checked-text-svg"}:
        errors.append(f"unexpected glyphCoverage status: {coverage!r}")
    return {
        "artifact": str(artifact),
        "receipt": str(receipt_path),
        "format": fmt,
        "widthMm": width,
        "bytes": artifact.stat().st_size,
        "sha256": actual_digest,
        "geometryVerified": bool(receipt.get("geometryVerified")),
        "glyphCoverage": coverage,
        "fontEmbeddingGuaranteed": bool(fonts.get("embeddingGuaranteed", False)),
        "fonts": fonts,
        "unresolved": receipt.get("unresolved", []),
        "physicalPreflight": preflight,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", default="mlp", choices=("mlp", "transformer", "residual_cnn"))
    parser.add_argument("--entry", default=None, help="analyzer entry; defaults to the fixture's canonical entry")
    parser.add_argument("--python", default=sys.executable, help="formal publication Python interpreter")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/evidence/m5-beta-preflight")
    parser.add_argument("--width-mm", type=int, nargs="+", default=[85, 180], choices=(85, 180))
    parser.add_argument("--formats", nargs="+", default=["svg", "pdf", "png"], choices=("svg", "pdf", "png"))
    parser.add_argument("--max-seconds", type=float, default=90.0)
    options = parser.parse_args()
    if not math.isfinite(options.max_seconds) or options.max_seconds <= 0:
        parser.error("--max-seconds must be positive and finite")
    started = time.monotonic()
    fixture = options.fixture
    fixture_dir = ROOT / "fixtures" / fixture
    entries = {"mlp": "model:MLP", "transformer": "model:Transformer", "residual_cnn": "model:ResidualCNN"}
    entry = options.entry or entries[fixture]
    output_dir = options.output_dir.resolve()
    if (output_dir / "receipt.json").exists():
        parser.error("output-dir already contains a receipt; select a fresh directory to preserve earlier evidence")
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="archcanvas-m5-preflight-", dir="/tmp"))
    records: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    errors: list[str] = []
    try:
        if shutil.which("node") is None:
            raise RuntimeError("Node.js is required to construct the formal CanvasDocument")
        source_digest = sha256(fixture_dir / "model.py")
        source_files = {str(path): sha256(path) for path in sorted(fixture_dir.glob("*.py"))}
        analyze = (
            "import sys,json; from pathlib import Path; "
            "sys.path.insert(0,sys.argv[1]); "
            "from archcanvas_python import analyze_project; "
            "print(json.dumps(analyze_project(Path(sys.argv[2]),sys.argv[3])))"
        )
        architecture = json_command(options.python, analyze, str(ROOT / "src"), str(fixture_dir), entry)
        architecture_path = temporary / "architecture.json"
        architecture_path.write_text(json.dumps(architecture, ensure_ascii=False, indent=2) + "\n")
        document_path = temporary / "document.json"
        create = (
            "import fs from 'node:fs'; "
            "import {createDocument} from './studio/src/core/index.ts'; "
            "const architecture=JSON.parse(fs.readFileSync(process.argv[1],'utf8')); "
            "fs.writeFileSync(process.argv[2],JSON.stringify(createDocument(architecture),null,2)+'\\n');"
        )
        run(["node", "--experimental-strip-types", "--input-type=module", "-e", create,
             str(architecture_path), str(document_path)])
        document_digest = sha256(document_path)
        shutil.copy2(architecture_path, output_dir / f"{fixture}.architecture.json")
        shutil.copy2(document_path, output_dir / f"{fixture}.canvas.json")

        capabilities_source = (
            "import sys,json; sys.path.insert(0,sys.argv[1]); "
            "from archcanvas_publication import capabilities; print(json.dumps(capabilities()))"
        )
        capabilities = json_command(options.python, capabilities_source, str(ROOT / "src"))
        if not Path(capabilities["moduleOrigin"]).resolve().is_relative_to(ROOT / "src"):
            raise RuntimeError("publication module resolved outside the formal source tree")
        available = {"svg": True, "pdf": bool(capabilities.get("pdf")), "png": bool(capabilities.get("png"))}
        for fmt in options.formats:
            if not available.get(fmt, False):
                skipped.append({"format": fmt, "reason": capabilities.get("unavailableReason", "format unavailable")})
                continue
            for width in sorted(set(options.width_mm)):
                artifact = output_dir / f"{fixture}-{width}.{fmt}"
                command = ["node", "scripts/export_canvas.mjs", "--document", str(document_path),
                           "--output", str(artifact), "--format", fmt, "--python", options.python,
                           "--width-mm", str(width)]
                try:
                    run(command, timeout=60)
                    receipt_path = Path(f"{artifact}.receipt.json")
                    records.append(check_receipt(artifact, receipt_path, width=width, fmt=fmt))
                except (RuntimeError, ValueError, OSError, ET.ParseError, subprocess.TimeoutExpired) as exc:
                    errors.append(f"{fmt} at {width} mm: {exc}")
        errors.extend(item for record in records for item in record["errors"])
        sources_unchanged = all(digest == sha256(Path(path)) for path, digest in source_files.items())
        if not sources_unchanged:
            errors.append("export changed its fixture source")
        if document_digest != sha256(document_path):
            errors.append("export changed its CanvasDocument")
        elapsed = time.monotonic() - started
        input_paths = [ROOT / "scripts/m5_beta_preflight.py", ROOT / "scripts/export_canvas.mjs",
                       *sorted((ROOT / "studio/src/core").glob("*.ts")),
                       *sorted((ROOT / "src/archcanvas_publication").glob("*.py")),
                       *sorted(fixture_dir.glob("*.py"))]
        input_paths += sorted((ROOT / "studio/dist").glob("assets/*"))
        advisories = []
        for record in records:
            if record["physicalPreflight"].get("minTextPt", 0) < 7:
                advisories.append({"artifact": record["artifact"], "code": "text-below-example-target", "minTextPt": record["physicalPreflight"].get("minTextPt"), "suggestedWidthMm": record["physicalPreflight"].get("suggestedWidthFor7Pt")})
        report = {
            "schemaVersion": 1,
            "schema": "archcanvas-m5-beta-preflight/1",
            "fixture": fixture,
            "entry": entry,
            "sourceFile": str(fixture_dir / "model.py"),
            "sourceFileSha256": source_digest,
            "sourceDigest": architecture.get("sourceDigest"),
            "irDigest": architecture.get("irDigest"),
            "architectureFile": str(output_dir / f"{fixture}.architecture.json"),
            "documentFile": str(output_dir / f"{fixture}.canvas.json"),
            "documentDigest": document_digest,
            "sourceUnchanged": sources_unchanged,
            "sourceFiles": source_files,
            "documentUnchanged": document_digest == sha256(document_path),
            "python": options.python,
            "node": run(["node", "--version"]).stdout.strip(),
            "capabilities": capabilities,
            "artifacts": records,
            "skipped": skipped,
            "advisories": advisories,
            "inputs": [{"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in input_paths],
            "inputScope": "Selected fixture, shared core, export/preflight adapters and current dist assets; not a complete transitive dependency seal.",
            "fontPolicy": {
                "embeddingGuaranteed": bool(records) and all(item["fontEmbeddingGuaranteed"] for item in records),
                "coverageStatuses": sorted({item["glyphCoverage"] for item in records}),
                "claim": "Coverage is checked by the formal exporter; resolved font identity, shaping fidelity, embedding and physical human readability remain open.",
            },
            "demo": {
                "targetSeconds": options.max_seconds,
                "preflightElapsedSeconds": round(elapsed, 3),
                "withinTarget": elapsed <= options.max_seconds,
                "manualSteps": [
                    "Open the source-bound Transformer overview.",
                    "Expand Encoder and Attention, then drag and align one block.",
                    "Change a display name, colour and legend entry; undo once.",
                    "Export white-background SVG/PDF at the chosen paper width.",
                    "Change dropout, inspect impact/minimal diff, approve write-back and re-analyze.",
                ],
                "claim": "The five steps are a recording checklist; this command cannot impersonate a browser operator or human reviewer.",
            },
            "status": "failed" if errors else "partial" if skipped else "passed",
            "errors": errors,
        }
        report_path = output_dir / "receipt.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"status": report["status"], "receipt": str(report_path), "artifacts": len(records), "skipped": len(skipped), "elapsedSeconds": report["demo"]["preflightElapsedSeconds"]}, ensure_ascii=False))
        return 0 if not errors else 2
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
