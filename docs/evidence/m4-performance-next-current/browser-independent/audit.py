"""Read-only arithmetic audit of frozen B_XH browser diagnostic inputs.

No ArchCanvas product code, validator, statistics helper or test oracle is imported.
Only this directory receives output. Run with the formal .venv Python.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
PERF = ROOT / "docs/evidence/m4-performance-next-current/bxh-before-drain-browser"
VISUAL = ROOT / "docs/evidence/m4-visual-next-current/bxh-browser-before"
BASELINE = ROOT / "docs/evidence/m4-performance-next-current/before-change"


def read(path: Path):
    return json.loads(path.read_text())


def digest(path: Path):
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def percentile95(values):
    values = sorted(values)
    return values[math.ceil(len(values) * 0.95) - 1] if values else None


def intersection(a, b):
    width = min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"])
    height = min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"])
    return {"widthCssPx": max(0, width), "heightCssPx": max(0, height),
            "areaCssPx2": max(0, width) * max(0, height), "positive": width > 0 and height > 0}


checks = []


def check(name, condition):
    checks.append({"name": name, "passed": bool(condition)})
    if not condition:
        raise AssertionError(name)


baseline_manifest = read(BASELINE / "manifest.json")
frozen_inputs = [ROOT / item["snapshot"] for item in baseline_manifest["inputs"]]
input_paths = sorted(set(list(PERF.rglob("*")) + list(VISUAL.rglob("*")) +
                         [BASELINE / "manifest.json"] + frozen_inputs))
input_paths = [p for p in input_paths if p.is_file()]
inputs_before = [digest(p) for p in input_paths]
check("all pre-change manifest snapshot bytes exact", all(
    digest(ROOT / i["snapshot"])["sha256"] == i["sha256"] and
    (ROOT / i["snapshot"]).stat().st_size == i["bytes"] for i in baseline_manifest["inputs"]))
sealed_manifests = []
for directory, expected_count in [(PERF, 21), (VISUAL, 15)]:
    manifest = read(directory / "manifest.json")
    check(f"{directory.name} sealed artifact count", len(manifest["artifacts"]) == expected_count)
    check(f"{directory.name} sealed artifact bytes", all(
        digest(directory / item["path"])["sha256"] == item["sha256"] and
        (directory / item["path"]).stat().st_size == item["bytes"] for item in manifest["artifacts"]))
    external = manifest.get("externalBindings", [])
    check(f"{directory.name} external snapshot bytes", all(
        digest(ROOT / item["path"])["sha256"] == item["sha256"] and
        (ROOT / item["path"]).stat().st_size == item["bytes"] for item in external))
    sealed_manifests.append({"path": str((directory / "manifest.json").relative_to(ROOT)),
                             "artifactCount": len(manifest["artifacts"]), "externalCount": len(external)})
raw = read(PERF / "native-raw.json")
trials = raw["trials"]
events = raw["snapshot"]["eventTiming"]
check("native protocol and trusted automation scope", raw["protocol"] == "archcanvas-native-performance/1" and
      raw["measurement"]["nativeInputSource"] == "trusted-browser-events-not-human-certification")
check("exactly three recorded native toggles", len(trials) == 3 and
      [t["operation"] for t in trials] == ["expand", "collapse", "expand"])
check("raw event timestamps finite and ordered within entry", all(
    all(math.isfinite(e[k]) for k in ["startAt", "durationMs", "processingStart", "processingEnd"]) and
    e["durationMs"] >= 0 and e["processingStart"] >= e["startAt"] and
    e["processingEnd"] >= e["processingStart"] for e in events))
check("64 Event Timing entries are not three input denominator", len(events) == 64)

# Construct the entire bipartite relation before selecting any match.
relation = []
for t in trials:
    relation.append([i for i, e in enumerate(events) if
        t["trusted"] and e["name"] == t["eventName"] and
        e.get("targetCanonicalNodeId") == t["targetId"] and e["interactionId"] > 0 and
        abs(e["startAt"] - t["eventAt"]) <= 8 and
        e["processingStart"] >= e["startAt"] and e["processingEnd"] >= e["processingStart"] and
        math.isfinite(e["durationMs"]) and e["durationMs"] >= 0])
event_degrees = {i: sum(i in candidates for candidates in relation) for candidates in relation for i in candidates}
check("all three joins unique on both sides of complete relation", all(
    len(candidates) == 1 and event_degrees[candidates[0]] == 1 for candidates in relation))
matches = [events[candidates[0]] for candidates in relation]
check("stored joins equal independently selected raw entries", all(
    t["nativeEventTiming"] == e and t["nativeInputToNextPaintMs"] == e["durationMs"]
    for t, e in zip(trials, matches)))
check("different positive interaction ids", len({e["interactionId"] for e in matches}) == 3)

joins = []
for n, (t, e) in enumerate(zip(trials, matches), 1):
    before, after = t["before"], t["after"]
    check(f"trial {n} provenance and revision", after is not None and not t["error"] and all(
        after[k] == before[k] == raw["bindingAtStart"][k] for k in ["documentId", "sourceDigest", "irDigest"]) and
        after["revision"] == before["revision"] + 1)
    check(f"trial {n} target expansion flips only target", set(before["expandedIds"]) ^ set(after["expandedIds"]) == {t["targetId"]} and
          (t["targetId"] in before["expandedIds"]) == (t["operation"] == "collapse") and
          (t["targetId"] in after["expandedIds"]) == (t["operation"] == "expand"))
    check(f"trial {n} visible ids and anchors unique exact", all(
        len(s["visibleIds"]) == len(set(s["visibleIds"])) and set(s["visibleIds"]) == set(s["anchors"])
        for s in [before, after]))
    anchor_before = before["anchors"][t["targetId"]]["screen"]
    anchor_after = after["anchors"][t["targetId"]]["screen"]
    anchor_delta = math.hypot(anchor_after["x"] - anchor_before["x"], anchor_after["y"] - anchor_before["y"])
    check(f"trial {n} target anchor stationary", anchor_delta == t["anchorScreenDisplacementPx"] == 0)
    check(f"trial {n} no unrelated pins measured", before["pinnedIds"] == [] and t["pins"] == [])
    joins.append({"trial": n, "operation": t["operation"], "eventIndex": relation[n-1][0],
                  "interactionId": e["interactionId"], "eventAt": t["eventAt"],
                  "captureDelayMs": t["capturedAt"] - t["eventAt"],
                  "nativeDurationMs": e["durationMs"], "processingDurationMs": e["processingEnd"] - e["processingStart"],
                  "revisionBefore": before["revision"], "revisionAfter": after["revision"],
                  "frontierBefore": len(before["visibleIds"]), "frontierAfter": len(after["visibleIds"]),
                  "targetAnchorScreenPx": anchor_delta})
check("scene chain revisions contiguous", [t["before"]["revision"] for t in trials] == [0, 1, 2] and
      all(trials[i-1]["after"] == trials[i]["before"] for i in range(1, 3)))
durations = [e["durationMs"] for e in matches]
check("nearest rank p95 equals 224 ms", durations == [224, 72, 160] and
      percentile95(durations) == raw["summary"]["nativeInputToNextPaintP95Ms"] == 224)
check("reported summary denominator exact", [raw["summary"][k] for k in
    ["capturedTrials", "validSceneTrials", "matchedNativeTrials"]] == [3, 3, 3] and
      raw["summary"]["anchorScreenMaxPx"] == 0 and raw["summary"]["measuredPinCount"] == 0 and
      raw["summary"]["pinCanvasMaxPx"] is None and raw["summary"]["unmeasuredPinCount"] == 0)

frames = raw["frames"]
intervals = frames["intervals"]
span = frames["lastFrameAt"] - frames["firstFrameAt"]
raf_hz = len(intervals) * 1000 / span
check("4906 callbacks reconstruct 4905 positive intervals", frames["frameCount"] == 4906 and
      len(intervals) == 4905 and all(math.isfinite(x) and x > 0 for x in intervals))
check("frame intervals reconstruct callback span", abs(sum(intervals) - span) < 1e-7)
check("rAF cadence and nearest rank p95 exact", abs(raf_hz - frames["fps"]) < 1e-10 and
      percentile95(intervals) == frames["intervalP95Ms"])
check("frame buffer not truncated", frames["bufferTruncated"] is False)
long_tasks = raw["snapshot"]["longTasks"]
check("two finite positive Long Task entries", len(long_tasks) == 2 and all(
    math.isfinite(task["startAt"]) and math.isfinite(task["durationMs"]) and task["durationMs"] >= 50
    for task in long_tasks))
long_task_overlap = [{**task, "overlapsTrialNativeDurationWindow": [n for n, t in enumerate(trials, 1) if
    max(task["startAt"], t["eventAt"]) < min(task["startAt"] + task["durationMs"],
                                               t["eventAt"] + t["nativeInputToNextPaintMs"])]}
    for task in long_tasks]

coverage = read(PERF / "02-viewport-coverage.json")
viewport = coverage["viewport"]
inside, intersects = [], []
for node in coverage["nodes"]:
    rect = node["rect"]
    overlaps = intersection(rect, viewport)["positive"]
    contained = (rect["x"] >= viewport["x"] and rect["y"] >= viewport["y"] and
                 rect["x"] + rect["width"] <= viewport["x"] + viewport["width"] and
                 rect["y"] + rect["height"] <= viewport["y"] + viewport["height"])
    check(f"body viewport flags {node['id']}", overlaps == node["intersects"] and contained == node["fullyInside"])
    if overlaps:
        intersects.append(node["id"])
    if contained:
        inside.append(node["id"])
check("304 unique DOM frontier bodies, six geometric intersections and four contained", len(coverage["nodes"]) ==
      len({n["id"] for n in coverage["nodes"]}) == 304 and len(intersects) == 6 and len(inside) == 4)
check("coverage corresponds to expanded native scene", set(n["id"] for n in coverage["nodes"]) ==
      set(trials[0]["after"]["visibleIds"]))
capture_names = ["01-stress-before", "02-stress-expanded", "03-stress-collapsed", "04-stress-expanded-again"]
capture_summary = []
for n, name in enumerate(capture_names):
    captured = read(PERF / f"{name}.json")
    svg = captured["svgs"][0]
    check(f"{name} assets B_XH", captured["assets"] == ["/assets/index-B_XHk-wz.js", "/assets/index--unhoRTb.css"])
    check(f"{name} public root revision", re.search(r'data-revision="(\d+)"', svg).group(1) == str(n))
    capture_summary.append({"name": name, "publicSvgStringLength": len(svg), "svgHasClosingTag": svg.endswith("</svg>")})
try:
    ET.fromstring(read(PERF / "02-stress-expanded.json")["svgs"][0])
    svg_error = None
except ET.ParseError as error:
    svg_error = str(error)
check("expanded public SVG visibly truncated, complete XML not claimed", svg_error is not None and
      capture_summary[1]["svgHasClosingTag"] is False)

label_data = read(VISUAL / "memory-label-bounds.json")
label = next(item for item in label_data["labels"] if item["text"] == "memory")
hits = []
for card in label_data["cards"]:
    if card["id"] == "call:instance:model.Transformer":
        continue  # Containing model frame is an intended ancestor.
    for i, body in enumerate(card["bodies"]):
        hit = intersection(label["screen"], body["screen"])
        if hit["positive"]:
            hits.append({"id": card["id"], "bodyIndex": i, **hit, "markup": body["markup"]})
check("memory screen rectangle touches only encoder last rear plate and decoder front", [(h["id"], h["bodyIndex"]) for h in hits] ==
      [("repeat:instance:model.Transformer.encoder", 0), ("call:instance:model.Transformer.decoder", 0)])
check("horizontal overlap below one CSS pixel, vertical overlap seven", all(
    0 < h["widthCssPx"] < 1 and h["heightCssPx"] == 7 for h in hits))
check("getBBox failure preserved", read(VISUAL / "bbox-attempt-1.json")["status"] == "unsupported")
root_perf_receipt = read(PERF / "receipt.json")
check("root sealed performance receipt matches raw arithmetic and scope", root_perf_receipt["summary"] == raw["summary"] and
      root_perf_receipt["bodyCoverage"]["geometricViewportIntersections"] == len(intersects) and
      root_perf_receipt["bodyCoverage"]["fullyInsideViewport"] == len(inside) and
      root_perf_receipt["bodyCoverage"]["is300ViewportObjectGate"] is False and root_perf_receipt["humans"] == 0)
check("root sealed visual receipt remains bounded AI review", read(VISUAL / "receipt.json")["humans"] == 0 and
      read(VISUAL / "receipt.json")["getBBoxSupported"] is False)

inputs_after = [digest(p) for p in input_paths]
check("all audited input bytes unchanged", inputs_after == inputs_before)
report = {
    "schema": "archcanvas-independent-bxh-browser-diagnostic/1",
    "createdUtc": datetime.now(timezone.utc).isoformat(),
    "formalInterpreter": str(Path(sys.executable).absolute()),
    "method": "Independently handwritten relations/arithmetic; no product imports or verifier reused.",
    "scope": "Three B_XH AI native toggles; geometric body viewport coverage; two personally viewed B_XH Transformer JPEGs.",
    "checks": checks,
    "inputCount": len(inputs_before), "inputsUnchanged": inputs_before == inputs_after,
    "preChangeSnapshotBindings": len(frozen_inputs),
    "sealedRootManifests": sealed_manifests,
    "native": {"rawEventTimingEntries": len(events), "joins": joins, "summaryDenominator": 3,
               "durationsMs": durations, "nearestRankP95Ms": percentile95(durations),
               "longTasks": long_task_overlap, "measuredPinCount": 0,
               "raf": {"callbackCount": frames["frameCount"], "intervalCount": len(intervals),
                       "spanMs": span, "callbackHz": raf_hz, "intervalP95Ms": percentile95(intervals),
                       "maximumIntervalMs": max(intervals), "intervalsOver50Ms": sum(x > 50 for x in intervals),
                       "presentedFps": None}, "visibility": raw["snapshot"]["visibility"]},
    "viewport": {"recordedBodyMethod": "Per canonical group, direct :scope > rect[stroke-width] getBoundingClientRect; compared with .canvas-viewport. Collector method supplied by root; rectangle arithmetic independently verified.",
                 "rect": viewport, "domFrontierBodies": 304, "intersectingCount": len(intersects),
                 "fullyInsideCount": len(inside), "intersectingIds": intersects, "fullyInsideIds": inside,
                 "meaning": "Geometric upper bound only: benchmark overlay can occlude the viewport. Not 300 on-screen objects and not six necessarily unobscured objects."},
    "publicCapture": {"states": capture_summary, "expandedSvgParseError": svg_error,
                      "meaning": "Truncated public SVG strings cannot establish complete SVG geometry or export fidelity. Native raw scene/provenance and body rectangle arrays remain independently inspectable."},
    "memoryLabel": {"screenRect": label["screen"], "nonAncestorBodyIntersections": hits,
                    "bboxMethod": "getBoundingClientRect; SVG getBBox unavailable and preserved.",
                    "meaning": "Bounding rectangles overlap; actual glyph ink, rounded body fill and occlusion are not proven by these rectangles. Both personally viewed images show readable memory text in a crowded gap."},
    "limitations": ["AI automation is not a human participant or a physical publication review.",
                    "This is a three-sample diagnosis, not the 300-visible-object, complete-input, repeated fixed-environment gate.",
                    "Event Timing is thresholded and quantized; unrecorded eligible input denominator is not established.",
                    "rAF cadence is not actual presented FPS; hardware and fallback font bytes are unbound.",
                    "No unrelated pinned-object operation was measured.",
                    "Observer/DOM readScene/onProgress measurement overhead is not separately estimated.",
                    "This B_XH observer records no end-boundary takeRecords drain; queued entries can be omitted. Buffered pre-session entries are present but excluded from unique target/time joins.",
                    "Long Task temporal overlap does not establish causal attribution to model layout or the observer."]
}
(OUT / "input-receipt.json").write_text(json.dumps({"schema": "archcanvas-independent-input-binding/1", "inputs": inputs_before,
                                                 "inputsUnchanged": True}, ensure_ascii=False, indent=2) + "\n")
(OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"passed": sum(c["passed"] for c in checks), "checks": len(checks), "inputs": len(inputs_before),
                  "p95Ms": percentile95(durations), "rafCallbackHz": raf_hz,
                  "viewportIntersections": len(intersects), "viewportContained": len(inside),
                  "memoryHorizontalOverlapsCssPx": [h["widthCssPx"] for h in hits]}, ensure_ascii=False))
