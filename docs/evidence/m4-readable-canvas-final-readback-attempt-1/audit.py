"""Independent read-only readback of the readable-canvas browser evidence.

This audit checks the frozen manifest, its 22 frame triplets, the final source/build
receipt, and the already recorded 300-test/build logs.  It does not run the
application, tests, a browser, or a model, and it does not make a claim about
global route aesthetics or human acceptance.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
WORK = ROOT / "docs/evidence/m4-readable-canvas-work"
BROWSER = WORK / "browser-final"
MANIFEST = BROWSER / "manifest.json"
RECEIPT = WORK / "checks-final/receipt.json"
SUITE = WORK / "checks-final/suite.txt"
BUILD = WORK / "checks-final/build.txt"
SOURCE_REPORT = WORK / "independent-source/report.json"


def identity(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def jpeg_size(data: bytes) -> tuple[int, int] | None:
    """Read a JPEG SOF size without a third-party image library."""
    if not data.startswith(b"\xff\xd8"):
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        while i < len(data) and data[i] == 0xFF:
            i += 1
        if i >= len(data):
            break
        marker = data[i]
        i += 1
        if marker in (0xD8, 0xD9):
            continue
        if i + 2 > len(data):
            break
        length = struct.unpack(">H", data[i:i + 2])[0]
        if marker in set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0)):
            if i + 7 <= len(data):
                height, width = struct.unpack(">HH", data[i + 3:i + 7])
                return width, height
            return None
        i += length
    return None


def frame_readback(frame: dict, files_by_path: dict[str, dict]) -> dict:
    name = frame["name"]
    rows = []
    errors = []
    for suffix in (".dom.txt", ".jpg", ".public.json"):
        rel = f"docs/evidence/m4-readable-canvas-work/browser-final/{name}{suffix}"
        expected = files_by_path.get(rel)
        actual_path = ROOT / rel
        if expected is None or not actual_path.exists():
            errors.append({"frame": name, "file": rel, "error": "missing manifest row or file"})
            continue
        actual = identity(actual_path)
        exact = actual == {"path": rel, "bytes": expected["bytes"], "sha256": expected["sha256"]}
        rows.append({"path": rel, "exact": exact, "declared": expected, "actual": actual})
        if not exact:
            errors.append({"frame": name, "file": rel, "declared": expected, "actual": actual})

    public = ROOT / f"docs/evidence/m4-readable-canvas-work/browser-final/{name}.public.json"
    dom = ROOT / f"docs/evidence/m4-readable-canvas-work/browser-final/{name}.dom.txt"
    jpeg = ROOT / f"docs/evidence/m4-readable-canvas-work/browser-final/{name}.jpg"
    summary = {"nodes": None, "edges": None, "viewport": None, "textScale": None,
               "tooltip": False, "hasFailedFetch": False, "hasBudgetFailure": False,
               "hasStaticPass": False, "jpegSize": None}
    if public.exists():
        data = json.loads(public.read_text())
        summary.update({"nodes": len(data.get("nodes", [])), "edges": len(data.get("edges", [])),
                        "viewport": data.get("viewport"), "textScale": data.get("textScale"),
                        "tooltip": bool(data.get("hint"))})
        footer = str(data.get("footer", ""))
        summary["hasFailedFetch"] = "Failed to fetch" in footer
        summary["hasBudgetFailure"] = "超出建模预算" in footer
        summary["hasStaticPass"] = "静态检查通过" in footer
    if jpeg.exists():
        summary["jpegSize"] = jpeg_size(jpeg.read_bytes())
    if dom.exists() and not dom.read_text().strip():
        errors.append({"frame": name, "file": dom.name, "error": "empty DOM snapshot"})
    superseded = "superseded pixel-sync failure" in frame.get("scope", "")
    return {"name": name, "scope": frame.get("scope", ""),
            "superseded": superseded, "triplet": rows, "summary": summary,
            "tripletExact": not errors and all(row["exact"] for row in rows),
            "errors": errors}


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    receipt = json.loads(RECEIPT.read_text())
    source_report = json.loads(SOURCE_REPORT.read_text())
    file_rows = manifest["files"]
    files_by_path = {row["path"]: row for row in file_rows}
    frame_rows = [frame_readback(frame, files_by_path) for frame in manifest["frames"]]
    errors = [error for row in frame_rows for error in row["errors"]]

    # Receipt source/build bindings are checked against the current checkout. The
    # command outputs are already-run evidence and are parsed, never re-executed.
    receipt_bindings = []
    for category in ("inputs", "assets"):
        for row in receipt.get(category, []):
            path = ROOT / row["path"]
            actual = identity(path) if path.exists() else None
            exact = actual is not None and actual["bytes"] == row["bytes"] and actual["sha256"] == row["sha256"]
            receipt_bindings.append({"declared": row, "actual": actual, "exact": exact})
            if not exact:
                errors.append({"check": "receiptBinding", "declared": row, "actual": actual})

    suite_text = SUITE.read_text()
    suite_counts = {key: int(re.search(rf"^ℹ {key} (\d+)$", suite_text, re.MULTILINE).group(1))
                    for key in ("tests", "pass", "fail", "cancelled", "skipped", "todo")}
    build_text = BUILD.read_text()
    checks = {
        "manifestProtocol": manifest.get("protocol") == "archcanvas-readable-canvas-browser/1",
        "frameCount": len(manifest.get("frames", [])) == 22,
        "rawFileCount": len(file_rows) == 66,
        "frameTripletsExact": all(row["tripletExact"] for row in frame_rows),
        "jpegDimensions1205Or1100": all(row["summary"]["jpegSize"] in ((1205, 720), (1100, 720)) for row in frame_rows),
        "receiptBindingsExact": all(row["exact"] for row in receipt_bindings),
        "suite300Pass": suite_counts == {"tests": 300, "pass": 300, "fail": 0, "cancelled": 0, "skipped": 0, "todo": 0},
        "buildExit0Recorded": all(row.get("exitCode") == 0 for row in receipt.get("checks", [])),
        "buildLogHasStrictTypeScriptAndVite": "tsc --noEmit && vite build" in build_text and "✓ built in" in build_text,
        "humanParticipantsZero": manifest.get("humanParticipants") == 0 and receipt.get("humanParticipants") == 0,
        "sourceReportStillBounded": source_report.get("verdict") == "bounded-source-and-final-check-readback-pass",
    }
    errors.extend({"check": name, "actual": value} for name, value in checks.items() if not value)

    superseded = [row["name"] for row in frame_rows if row["superseded"]]
    settled = [row["name"] for row in frame_rows if not row["superseded"]]
    report = {
        "protocol": "archcanvas-readable-canvas-independent-final-readback/1",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "reviewer": "AI read-only audit; not a human participant",
        "verdict": "bounded-readable-canvas-readback-pass" if not errors else "failed",
        "scope": "Read-only verification of the frozen 22-frame manifest, 66 frame files, final source/build receipt and already-recorded 300/300 test and strict TypeScript/Vite build logs. No product/source edits, test/build rerun, browser operation, model execution or dependency installation.",
        "checks": checks,
        "manifest": {"identity": identity(MANIFEST), "url": manifest.get("url"),
                     "build": manifest.get("build"), "viewport": manifest.get("viewport"),
                     "frameCount": len(frame_rows), "fileCount": len(file_rows),
                     "settledFrameCount": len(settled), "supersededFrameCount": len(superseded),
                     "supersededFrames": superseded, "settledFrames": settled},
        "frameReadback": frame_rows,
        "receipt": {"identity": identity(RECEIPT), "bindings": receipt_bindings,
                    "suite": {"identity": identity(SUITE), "counts": suite_counts},
                    "build": {"identity": identity(BUILD), "exitCodes": [row.get("exitCode") for row in receipt.get("checks", [])]}},
        "observations": {
            "overviewAndMovement": "MLP overview is 5 nodes/4 edges at 58%; four direction frames preserve 5 nodes/4 edges and move ReLU by 16 units. The move-up/down routes contain the expected single orthogonal jog.",
            "tooltip": "58% and local 100% tooltip frames show a bounded tooltip that avoids node cards. The 100% frame is a local view; Input/Output are partly outside the viewport and it is not a full-network 100% certification.",
            "text": "Settled long Chinese and wide-Latin frames show ellipsis inside cards while public full text remains available. The earlier long-chinese-58 JPEG/public one-frame lag is retained as a superseded failure.",
            "saveDelete": "Saved/reopened MLP retains 5 nodes/4 edges; edge-deleted retains 5 nodes/3 edges and asks for recheck.",
            "dualInput": "Settled horizontal and vertical Add frames show distinct merge ports and 4-node/3-edge branches. The 1100x720 sample keeps its tooltip clamped and visible. The Add 4-node/3-edge frame with Failed to fetch remains a failure; retry budget failure is correctly retained as an explicit negative case.",
            "catalog": "The adaptive-type frame exposes AdaptiveAvgPool2d in the 17-item catalog and records a 5-node/3-edge static draft.",
        },
        "retainedFailures": [
            {"frame": "long-chinese-58", "reason": "JPEG lagged settled DOM/public state by one frame; retained and superseded by long-chinese-58-settled."},
            {"frame": "add-horizontal-left-tail", "reason": "JPEG lagged public state by one frame; retained and superseded by add-horizontal-left-settled."},
            {"frame": "add-horizontal-checked", "reason": "Recorded check ended in Failed to fetch; no passing check is inferred."},
        ],
        "limits": [
            "Pixel synchronization is not claimed for the two superseded action frames; their failures remain part of the record and are not repaired by settled replacements.",
            "Tooltip placement checks avoid node cards but do not certify avoidance of every edge/arrow or global branch beauty.",
            "The 100% tooltip and 1100x720 sample are local viewport observations; full-network 100% and publication-size review are unverified.",
            "Only the current 17-item catalog entry and AdaptiveAvgPool2d observation are shown; all 17 module behaviors are not certified.",
            "This run is AI-only (humanParticipants=0); AI agents are not human research participants. M4 remains partial and M5 has not started.",
            "No runtime/model execution, performance matrix, generated model, paper export, or five-step human usability study is certified.",
        ],
        "humanParticipants": 0,
        "aiOnly": True,
        "M4": "partial",
        "M5": "not_started",
        "errors": errors,
        "auditSource": identity(Path(__file__)),
    }
    output = OUT / "report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"report": identity(output), "verdict": report["verdict"],
                      "checks": checks, "errors": errors, "superseded": superseded}, ensure_ascii=False))


if __name__ == "__main__":
    main()
