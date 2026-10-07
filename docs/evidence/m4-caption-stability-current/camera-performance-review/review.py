"""Read-only camera/visibility review; frozen screen geometry, no model imports."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PATHS = [
    "AGENTS.md", "skills/archcanvas/SKILL.md", "studio/src/App.tsx",
    "studio/src/cameraGesture.ts", "studio/src/cameraProjection.ts",
    "studio/src/core/types.ts", "studio/src/core/document.ts",
    "studio/src/nativePerformance.ts", "studio/src/perf.ts",
    "studio/src/PerfBenchmarkPanel.tsx", "studio/src/perfBenchmark.ts",
    "fixtures/stress_300/model.py", "scripts/check_m4_stress.py",
    "studio/tests/camera-projection.test.ts", "studio/tests/camera-gesture.test.ts",
    "studio/tests/stress-fixture.test.ts", "scripts/validate_native_performance.mjs",
    "docs/evidence/m4-presented-performance-capability-audit/report.json",
    "docs/evidence/m4-current-performance-condition-review/README.md",
    "docs/evidence/m4-performance-next-current/final-native-browser/receipt.json",
    "docs/evidence/m4-performance-next-current/final-native-browser/expanded-body-coverage.json",
    "docs/evidence/m4-caption-route-current/final-browser/receipt.json",
    "docs/evidence/m4-caption-route-current/browser-gesture-final/report.json",
]


def binding(path):
    raw = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def rect_overlap(a, b):
    width = max(0, min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"]))
    height = max(0, min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"]))
    return width > 0 and height > 0


def contained(a, b):
    return a["x"] >= b["x"] and a["y"] >= b["y"] and a["x"] + a["width"] <= b["x"] + b["width"] and a["y"] + a["height"] <= b["y"] + b["height"]


def main():
    assert not (HERE / "report.json").exists(), "Never replace previous evidence"
    inputs = []
    for name in PATHS:
        path = ROOT / name
        before = binding(path)
        copy = HERE / "inputs" / name
        copy.parent.mkdir(parents=True, exist_ok=True)
        assert not copy.exists()
        copy.write_bytes(path.read_bytes())
        inputs.append({**before, "snapshot": str(copy.relative_to(ROOT)),
                       "snapshotExact": copy.read_bytes() == path.read_bytes()})
    app = (HERE / "inputs/studio/src/App.tsx").read_text()
    lines = app.splitlines()
    camera_uses = [{"line": i + 1, "text": line.strip()}
                   for i, line in enumerate(lines) if any(token in line for token in ["setCamera", "=> fit(document)", "=> fit(doc)", "localStorage.setItem(ACTIVE"])]
    coverage = json.loads((HERE / "inputs/docs/evidence/m4-performance-next-current/final-native-browser/expanded-body-coverage.json").read_text())
    bodies = coverage["bodies"]
    view = coverage["viewport"]
    full = [row["id"] for row in bodies if contained(row["rect"], view)]
    intersects = [row["id"] for row in bodies if rect_overlap(row["rect"], view)]
    leaves = [row for row in bodies if ".network." in row["id"]]
    actual_extent = {"left": min(row["rect"]["x"] for row in bodies),
                     "top": min(row["rect"]["y"] for row in bodies),
                     "right": max(row["rect"]["x"] + row["rect"]["width"] for row in bodies),
                     "bottom": max(row["rect"]["y"] + row["rect"]["height"] for row in bodies)}
    extent_width = actual_extent["right"] - actual_extent["left"]
    extent_height = actual_extent["bottom"] - actual_extent["top"]
    fit_relative = min((view["width"] - 96) / extent_width, (view["height"] - 92) / extent_height)
    # This fits only the frozen body extent, not the full Scene/legend/annotations.
    projected_leaf = {"widthPx": leaves[0]["rect"]["width"] * fit_relative,
                      "heightPx": leaves[0]["rect"]["height"] * fit_relative}
    rows = []
    # Layout hypothesis only: ordinary194x62 world cards plus32x24 gaps.
    for columns, rows_count, zoom in [(12, 25, .15), (20, 15, .15), (20, 15, .85)]:
        rows.append({"columns": columns, "rows": rows_count, "objects": columns * rows_count,
                     "zoom": zoom, "bodyWorld": [194, 62], "gapsWorld": [32, 24],
                     "extentCssPx": [(columns * 194 + (columns - 1) * 32) * zoom,
                                     (rows_count * 62 + (rows_count - 1) * 24) * zoom],
                     "bodyCssPx": [194 * zoom, 62 * zoom], "nominal13UnitTitlePx": 13 * zoom,
                     "scope": "Arithmetic compact-layout hypothesis, not an existing source-backed/interactive demo or viewport/hardware proof"})
    capability = json.loads((HERE / "inputs/docs/evidence/m4-presented-performance-capability-audit/report.json").read_text())
    gestures = json.loads((HERE / "inputs/docs/evidence/m4-caption-route-current/browser-gesture-final/report.json").read_text())
    report = {
        "schema": "archcanvas-camera-performance-next-step-review/1",
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "camera": {
            "allCurrentCameraUses": camera_uses,
            "initialState": {"x": 35, "y": 35, "zoom": .9},
            "architectureAndReloadScheduleUnconditionalFit": True,
            "generatedModelSchedulesFitAgain": True,
            "cameraStorageImplemented": False,
            "resizeObserverImplemented": "ResizeObserver" in app,
            "resizeEventImplemented": bool(re.search(r"addEventListener\(['\"]resize", app)),
            "scheduledLoadFitRechecksLoadGeneration": False,
            "scheduledLoadFitRisk": "Source shows rAF callback captures doc without a fresh loadSequence/history identity check. A cross-load/manual-fit overwrite is a source-level risk, not a new reproduced browser failure.",
            "resetMeaning": "100% is zoom=1 around viewport centre world point; explicitFit recomputes bounds. They are separate public actions.",
            "actualPriorReopen": gestures["additionalObservations"]["saveReopen"],
            "viewStateProposal": {
                "status": "recommendation_only_not_implemented",
                "separateFromDocumentHistory": True,
                "schema": {"schemaVersion": 1, "documentId": "exact", "sourceBindingDigest": "exact",
                           "irDigest": "exact", "zoom": "finite positive validated range",
                           "worldCenter": {"x": "finite", "y": "finite"},
                           "viewportAtCapture": {"width": "finite positive", "height": "finite positive"},
                           "mode": "manual|fit", "savedVisualRevision": "readback bound; reject view newer than restored document"},
                "scopeChoice": "Session storage is minimal reload preservation without cross-tab clobber. Full close/reopen across tabs requires a separately chosen origin/service namespace and last-view local preference policy; do not silently share transient camera ownership.",
                "restoreFormula": "x=newViewport.width/2-worldCenter.x*zoom; y=newViewport.height/2-worldCenter.y*zoom",
                "manualResize": "Preserve world centre and scale by reprojection, not old pixel translation",
                "fitResize": "Recompute fit to current committed bounds if mode remains fit",
                "precedence": "Explicit fit/reset/focus/pan/zoom increments camera intent generation. A delayed initial restore/fit cannot supersede it; recheck document/source/IR/loadSequence and viewport readiness before applying.",
                "writePolicy": "Persist committed camera only after pan release/zoom/fit/focus; do not persist active pan intermediates or cancelled gesture. Storage parse/quota failure keeps current view; writes never change visual revision/source/history.",
                "initialLoadPolicy": "No matching valid state uses fit once after positive viewport. Do not record stale prior document camera under next document key. Reconcile to new source/IR invalidates old state unless explicit mapping is independently reviewed.",
                "necessaryProof": ["new document/source/IR rejection", "malformed/nonfinite/tiny viewport handling", "same viewport exact restore", "different viewport same world centre", "manual resize versus fit resize", "explicit fit wins over delayed restore", "switch document before pending callback", "cancelled active pan rollback does not persist intermediate camera", "native pan/zoom save/reload and untouched Canvas/history/export"]},
        },
        "stressVisibility": {
            "frozenBuild": "index-BTw7OHsD.js", "renderedBodies": len(bodies),
            "ordinaryLayerBodies": len(leaves), "canvasViewport": view,
            "bodyIntersections": len(intersects), "fullyContained": len(full),
            "intersectingIds": intersects, "fullyContainedIds": full,
            "bodyExtentCssPx": {"width": extent_width, "height": extent_height},
            "ordinaryBodyCssPx": leaves[0]["rect"],
            "benchmarkPanel": coverage["panel"],
            "occludedIntersectingBodies": [row["id"] for row in bodies if rect_overlap(row["rect"], view) and rect_overlap(row["rect"], coverage["panel"])],
            "reason": "Source has one 300-layer Sequential; expanded default vertical chain extends far outside viewport. DOM frontier is not viewport visibility.",
            "bodyExtentFitHypothesis": {"relativeScale": fit_relative,
                                        "projectedLeafBody": projected_leaf,
                                        "notReadableOrActualFitProof": True},
            "compactLayoutHypotheses": rows,
            "nextDemoRequirements": ["A genuine source-backed graph with300 distinct visible bodies, nonoverlap and actual uncovered viewport coverage", "record actual effective viewport and zoom plus minimum painted object/text size", "keep camera unchanged across timed samples", "do not count offscreen bodies, collapsed canonical IDs,1px cards or occluded control overlay as readable300-object experience", "use ordinary typed layout operations/new isolated document; no canonical mutation or overlapping-body count trick"],
        },
        "performance": {
            "targets": {"visibleObjects": 300, "nativeInputToPaintP95Ms": 50,
                        "presentedFps": 50, "mediumIncrementalP95MsExclusive": 500,
                        "screenAnchorMaxPx": 8, "unrelatedPinCanvasMaxPx": 0},
            "currentlyAvailableEngineeringSignals": ["trusted discrete toggle EventTiming duration with both-sideunique matching", "rAF cadence intervals", "longtasks", "public DOM body coverage/anchors/pins", "2rAF geometry boundary"],
            "missingAcceptanceSignals": ["continuous input and complete denominator", "same surface presentation feedback joined to input", "fixed browser/hardware/fontbytes/DPR/power", "genuine readable300visible workload", "same conditionsA/Bx3 alternatingorder", "mediumincremental processing denominator and visibleunrelatedpins"],
            "existingTraceCapabilityBoundary": capability["specificBlocker"],
            "existingOperatorTraceRoute": capability["oneActionableNextStep"],
            "noUnsupportedApiRetries": True,
            "safeAvailableWork": ["prepare independent compact/source workload and nominal visibility/readability report", "instrument/measure observer readScene overhead and fullinputlog in a separate bounded stage", "fresh samebuild discreet trusted sample with explicit warmup/settle/drain and no pins-zero promotion", "bind available actual hardware/font files rather than merelydocument.fonts.status", "reuse retained host trace route; do not try undisclosedCDP/IPC/DevTools methods"],
            "claimBoundary": "More callback/DOM sampling cannot certify actual presentedFPS or compositorinput response; keep gate failed_or_unverified until exact surface feedback evidence exists.",
        },
        "stageRecommendation": {
            "camera": "Technically useful independent followup, but not prerequisite to fixing the current memorylabel threshold. Root chooses stage scope; camera needs its own async/resize/storage/browser proofs and freshbuild/research freeze.",
            "performance": "Prepare real300visibility/readability workload before another300 claim; native matching can advance engineering evidence but host presentedstream remains unavailable to documented tools.",
            "notRootDecision": True,
        },
        "boundaries": {"productChanged": False, "currentDocsChanged": False, "browserOperated": False,
                       "servicesOperated": False, "modelExecuted": False, "humanParticipants": 0,
                       "cameraStateImplemented": False, "presentedPerformanceCertified": False},
        "inputs": inputs,
    }
    report["inputBytesStillExact"] = all(binding(ROOT / row["path"]) == {k: row[k] for k in ["path", "bytes", "sha256"]} for row in inputs)
    assert report["inputBytesStillExact"]
    (HERE / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"inputs": len(inputs), "cameraStored": False, "bodyIntersections": len(intersects), "fullyInside": len(full),
                      "bodyExtentCssPx": report["stressVisibility"]["bodyExtentCssPx"],
                      "report": str((HERE / "report.json").relative_to(ROOT))}, indent=2))


if __name__ == "__main__":
    main()
