"""Independent complete 20-phase SVG, restore and public warning audit.

Only the local standalone XML checker and captured JSON are read. No Studio
renderer/history/observer imports, browser operations or model execution.
"""
import argparse
import json
from pathlib import Path

from check_directional import ensure, finite, geometric_findings, matrix_of, read_capture, semantic_continuity, sha

BUILD = "/assets/index-C7L6p5cl.js"
DIRECTIONS = ("right", "left", "up", "down")
PHASES = ("before", "moved", "undo", "redo", "restored")


def warning_visible(dom):
    box, viewport = dom.get("warningBox"), dom.get("viewport")
    if not box:
        return False
    ensure(isinstance(box, dict) and isinstance(viewport, dict), "Missing warning/viewport bounds")
    ensure(all(finite(item.get(key)) for item in (box, viewport) for key in ("left", "right", "top", "bottom", "width", "height")), "Invalid warning/viewport rectangle")
    return box["width"] > 0 and box["height"] > 0 and box["left"] >= viewport["left"] and box["right"] <= viewport["right"] and box["top"] >= viewport["top"] and box["bottom"] <= viewport["bottom"]


def check_warning(dom, findings, expected):
    has_header = bool(findings["leafBodiesInContainerHeaderBands"])
    ensure(has_header == expected, "Unexpected measured header conflict")
    text = dom.get("warnings")
    if expected:
        ensure(isinstance(text, str) and all(word in text for word in ("Linear 1", "network", "标题区", "向下")), "Header conflict lacks target-specific recovery guidance")
        ensure(warning_visible(dom), "Header warning is clipped/outside the viewport")
        ensure(dom.get("warningParent") == "main", "Warning placement evidence is missing")
    else:
        ensure(text is None and dom.get("warningBox") is None, "Restored/baseline layout still has public warning")
    return {"measuredHeaderConflict": has_header, "publicWarningText": text, "publicWarningFullyInsideViewport": warning_visible(dom), "pixelVisibilityCertifiedByGeometry": False}


def run(scope, output):
    cases, issues, all_captures = [], [], []
    first = previous_restored = None
    for direction in DIRECTIONS:
        try:
            captures = {phase: read_capture(scope / (direction + "-" + phase + ".json")) for phase in PHASES}
            before = captures["before"]
            if first is None:
                first = before
            if previous_restored:
                ensure(before["scene"]["svg"] == previous_restored["scene"]["svg"], "Next direction does not begin at exact restored SVG/revision")
            entries = []
            for phase, capture in captures.items():
                dom, scene = capture["capture"], capture["scene"]
                ensure(dom.get("scripts") == [BUILD], "Capture belongs to another build or lacks script provenance")
                ensure(json.loads(dom["metadata"]) == scene["metadata"], "Captured metadata text differs from actual SVG metadata")
                continuity = semantic_continuity(first, capture)
                ensure(continuity["expandedPinnedEvidencePresent"], "Missing public expanded/pinned memberships")
                ensure(dom["expandedIds"] is not None and dom["pinnedIds"] is not None, "Null public memberships cannot certify continuity")
                ensure(matrix_of(dom) == matrix_of(first["capture"]), "Node operation changed public camera")
                ensure(dom.get("viewportScroll") == first["capture"].get("viewportScroll") and isinstance(dom.get("viewportScroll"), dict), "Node operation changed viewport scroll or lacks scroll evidence")
                ensure("rev " + str(scene["metadata"]["revision"]) in dom.get("footer", ""), "Public footer revision differs from SVG")
                findings = geometric_findings(scene)
                conflict_expected = direction == "up" and phase in ("moved", "redo")
                entries.append({"phase": phase, "binding": capture["binding"], "revision": scene["metadata"]["revision"], "canonicalContinuity": continuity, "warning": check_warning(dom, findings, conflict_expected), "geometricFindings": findings})
                all_captures.append(capture)
            restored, redo = captures["restored"], captures["redo"]
            ensure(restored["scene"]["metadata"]["revision"] == redo["scene"]["metadata"]["revision"] + 1, "Restore is not one public revision")
            ensure(restored["scene"]["normalizedSvg"] == before["scene"]["normalizedSvg"], "Final restore did not restore full before SVG except revision")
            cases.append({"direction": direction, "status": "passed-complete-visible-restore-chain", "restoreFullSvgExceptRevision": True, "phases": entries})
            previous_restored = restored
        except (ValueError, KeyError, TypeError, OSError) as error:
            issues.append({"direction": direction, "message": str(error)})
    result = {"schema": "archcanvas-independent-visible-chain-audit/1", "status": "passed-public-20-phase-chain" if len(cases) == 4 and not issues else "incomplete-or-failed", "scope": str(scope), "checkerBinding": {"path": __file__, "sha256": sha(Path(__file__).read_bytes())}, "scriptPublicIdentity": BUILD, "phaseCount": len(all_captures), "issues": issues, "cases": cases, "headerConflictVisibleGuidanceCertifiedFromPublicDom": len(cases) == 4 and not issues, "actualScreenshotInspectionRequiredSeparately": True, "oldRightFirstFilesUsed": False, "humanParticipants": 0, "publicationCertified": False, "presentedFramesCertified": False}
    ensure(not output.exists(), "Use a fresh result filename; previous audit results are retained")
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scope", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.scope.resolve(), args.output.resolve())
    print(json.dumps({key: result[key] for key in ("status", "phaseCount", "issues")}, indent=2))
    raise SystemExit(0 if result["status"] == "passed-public-20-phase-chain" else 1)
