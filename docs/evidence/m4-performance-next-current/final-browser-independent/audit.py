"""Independent, read-only BTw browser/exports audit; no product imports/tests."""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "docs/evidence/m4-performance-next-current"
PERF = EVIDENCE / "final-native-browser"
UI = EVIDENCE / "final-browser"
OLDPERF = EVIDENCE / "bxh-before-drain-browser"
OLDUI = ROOT / "docs/evidence/m4-visual-next-current/bxh-browser-before"
BEFORE = EVIDENCE / "before-change"
ASSOC = ROOT / "docs/evidence/m4-visual-next-current/review/association-followup"
NS = {"s": "http://www.w3.org/2000/svg"}


def read(p):
    return json.loads(p.read_text())


def binding(p):
    data = p.read_bytes()
    return {"path": str(p.relative_to(ROOT)), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def bound(p, expected):
    item = binding(p)
    return item["bytes"] == expected["bytes"] and item["sha256"] == expected["sha256"]


def p95(values):
    return sorted(values)[math.ceil(len(values) * .95) - 1] if values else None


checks = []


def check(name, yes):
    checks.append({"name": name, "passed": bool(yes)})
    if not yes:
        raise AssertionError(name)


dirs = [(PERF, 30), (UI, 51), (OLDPERF, 21), (OLDUI, 15)]
paths = {p for directory, _ in dirs for p in directory.rglob("*") if p.is_file()}
seals = []
for directory, expected_count in dirs:
    m = read(directory / "manifest.json")
    check(f"{directory.name} artifact count {expected_count}", len(m["artifacts"]) == expected_count)
    check(f"{directory.name} artifact bytes exact", all(bound(directory / item["path"], item) for item in m["artifacts"]))
    external = m.get("externalBindings", [])
    check(f"{directory.name} external bindings exact", all(bound(ROOT / item["path"], item) for item in external))
    paths.update(ROOT / item["path"] for item in external)
    seals.append({**binding(directory / "manifest.json"), "artifacts": len(m["artifacts"]), "externalBindings": len(external)})
check("new native manifest exact named seal", binding(PERF / "manifest.json")["sha256"] ==
      "e538142157e60b51da7970cdda76154894c9639fcc302abe4ef18cc6fdd8d927")
check("new visual manifest exact named seal", binding(UI / "manifest.json")["sha256"] ==
      "6ccba745690d30ba239c2aec500496a46f8d2b3d08301243b7107007c216b4ce")
check("107 current external bindings equal across new browser receipts", read(PERF / "manifest.json")["externalBindings"] ==
      read(UI / "manifest.json")["externalBindings"] and len(read(UI / "manifest.json")["externalBindings"]) == 107)
baseline = read(BEFORE / "manifest.json")
check("121 historical snapshots exact", len(baseline["inputs"]) == 121 and all(
    bound(ROOT / i["snapshot"], i) for i in baseline["inputs"]))
paths.add(BEFORE / "manifest.json")
paths.update(ROOT / i["snapshot"] for i in baseline["inputs"])
previous_audit = read(EVIDENCE / "browser-independent/manifest.json")
check("previous independent audit six artifacts exact", len(previous_audit["artifacts"]) == 6 and all(
    bound(EVIDENCE / "browser-independent" / i["path"], i) for i in previous_audit["artifacts"]))
paths.update(p for p in (EVIDENCE / "browser-independent").iterdir() if p.is_file())
assoc_seal = read(ASSOC / "final-manifest.json")
check("association followup final artifacts and external bytes", all(
    bound(ROOT / i["path"], i) for i in assoc_seal["files"] + assoc_seal["externalBindings"]))
check("association previous seal exact", bound(ROOT / assoc_seal["previousManifest"]["path"], assoc_seal["previousManifest"]))
paths.add(ASSOC / "final-manifest.json")
paths.update(ROOT / i["path"] for i in assoc_seal["files"] + assoc_seal["externalBindings"])
paths.add(ROOT / assoc_seal["previousManifest"]["path"])
build_receipt_path = EVIDENCE / "checks-final-attempt-2/receipt.json"
build_receipt = read(build_receipt_path)
check("103 source plus three dist receipt bindings exact", len(build_receipt["inputs"]) == 103 and len(build_receipt["build"]) == 3 and
      all(bound(ROOT / i["path"], i) for i in build_receipt["inputs"] + build_receipt["build"]))
paths.add(build_receipt_path)
paths.update(ROOT / c["log"] for c in build_receipt["checks"])
for source in ["blocks.py", "model.py"]:
    paths.add(ROOT / "fixtures/transformer" / source)
inputs_before = [binding(p) for p in sorted(paths)]

raw = read(PERF / "native-raw.json")
trials, events = raw["trials"], raw["snapshot"]["eventTiming"]
check("three expand collapse expand trials and 45 entries", len(trials) == 3 and len(events) == 45 and
      [t["operation"] for t in trials] == ["expand", "collapse", "expand"])
check("all Event Timing timestamps finite with processing chronology", all(
    all(math.isfinite(e[k]) for k in ["startAt", "durationMs", "processingStart", "processingEnd"]) and
    e["durationMs"] >= 0 and e["startAt"] <= e["processingStart"] <= e["processingEnd"] for e in events))
relation = [[i for i, e in enumerate(events) if t["trusted"] and e["name"] == t["eventName"] and
             e.get("targetCanonicalNodeId") == t["targetId"] and e["interactionId"] > 0 and
             abs(e["startAt"] - t["eventAt"]) <= 8 and e["processingStart"] >= e["startAt"] and
             e["processingEnd"] >= e["processingStart"] and math.isfinite(e["durationMs"]) and e["durationMs"] >= 0]
            for t in trials]
check("complete candidate relation unique both sides", all(len(c) == 1 and
      sum(c[0] in other for other in relation) == 1 for c in relation))
matches = [events[c[0]] for c in relation]
check("all stored joined native entries independently reproduce", all(
    t["nativeEventTiming"] == e and t["nativeInputToNextPaintMs"] == e["durationMs"] for t, e in zip(trials, matches)))
check("native durations and nearest rank p95", [e["durationMs"] for e in matches] == [160, 72, 160] and
      p95([e["durationMs"] for e in matches]) == raw["summary"]["nativeInputToNextPaintP95Ms"] == 160)
check("native summary denominator and no pins", [raw["summary"][k] for k in
      ["capturedTrials", "validSceneTrials", "matchedNativeTrials"]] == [3, 3, 3] and
      raw["summary"]["measuredPinCount"] == raw["summary"]["unmeasuredPinCount"] == 0 and
      raw["summary"]["pinCanvasMaxPx"] is None)
native_rows = []
for n, (t, event) in enumerate(zip(trials, matches), 1):
    before, after = t["before"], t["after"]
    check(f"native trial {n} provenance revision", after is not None and t["error"] is None and
          all(before[k] == after[k] == raw["bindingAtStart"][k] for k in ["documentId", "sourceDigest", "irDigest"]) and
          after["revision"] == before["revision"] + 1)
    check(f"native trial {n} expansion only target", set(before["expandedIds"]) ^ set(after["expandedIds"]) == {t["targetId"]} and
          (t["targetId"] in after["expandedIds"]) == (t["operation"] == "expand"))
    check(f"native trial {n} anchor unique sets", all(set(s["anchors"]) == set(s["visibleIds"]) and
          len(s["visibleIds"]) == len(set(s["visibleIds"])) for s in [before, after]))
    a, b = before["anchors"][t["targetId"]]["screen"], after["anchors"][t["targetId"]]["screen"]
    displacement = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
    check(f"native trial {n} target anchor zero, pins absent", displacement == t["anchorScreenDisplacementPx"] == 0 and
          before["pinnedIds"] == [] and t["pins"] == [])
    native_rows.append({"trial": n, "operation": t["operation"], "eventIndex": relation[n-1][0],
                       "interactionId": event["interactionId"], "durationMs": event["durationMs"],
                       "revision": [before["revision"], after["revision"]],
                       "domFrontier": [len(before["visibleIds"]), len(after["visibleIds"])], "targetAnchorCssPx": displacement})
check("native scene chain continuous", [t["before"]["revision"] for t in trials] == [4, 5, 6] and all(
    trials[i-1]["after"] == trials[i]["before"] for i in [1, 2]))
setup = read(PERF / "setup-attempt-1.json")
check("zero-trial setup failure retained as zero", setup["summary"]["capturedTrials"] ==
      setup["summary"]["matchedNativeTrials"] == 0 and setup["summary"]["nativeInputToNextPaintP95Ms"] is None)
frames = raw["frames"]
intervals = frames["intervals"]
span = frames["lastFrameAt"] - frames["firstFrameAt"]
cadence = len(intervals) * 1000 / span
check("2350 callbacks and 2349 positive intervals", frames["frameCount"] == 2350 and len(intervals) == 2349 and
      all(math.isfinite(x) and x > 0 for x in intervals))
check("rAF arithmetic exact", abs(sum(intervals) - span) < 1e-7 and abs(cadence - frames["fps"]) < 1e-10 and
      p95(intervals) == frames["intervalP95Ms"] and frames["bufferTruncated"] is False)
coverage = read(PERF / "expanded-body-coverage.json")
v = coverage["viewport"]
intersecting, contained = [], []
for body in coverage["bodies"]:
    r = body["rect"]
    intersects = min(r["x"] + r["width"], v["x"] + v["width"]) > max(r["x"], v["x"]) and \
        min(r["y"] + r["height"], v["y"] + v["height"]) > max(r["y"], v["y"])
    inside = r["x"] >= v["x"] and r["y"] >= v["y"] and r["x"] + r["width"] <= v["x"] + v["width"] and \
        r["y"] + r["height"] <= v["y"] + v["height"]
    if intersects: intersecting.append(body["id"])
    if inside: contained.append(body["id"])
check("304 unique bodies six intersections four contained", len(coverage["bodies"]) == len({b["id"] for b in coverage["bodies"]}) == 304 and
      len(intersecting) == 6 and len(contained) == 4)
check("native viewport and window exact", (v["width"], v["height"]) == (672, 641) and
      (raw["environment"]["viewport"]["width"], raw["environment"]["viewport"]["height"]) == (1102, 835))
oldraw = read(OLDPERF / "native-raw.json")
check("native viewport differs from B_XH no paired improvement", raw["environment"]["viewport"] != oldraw["environment"]["viewport"])
check("native root receipt matches arithmetic", read(PERF / "receipt.json")["summary"] == raw["summary"] and
      read(PERF / "receipt.json")["bodyCoverage"]["geometricViewportIntersections"] == len(intersecting))
perf_source = (ROOT / "studio/src/perf.ts").read_text()
check("current snapshot drains queued observers source present", "this.flushObservers();" in perf_source and
      "this.eventObserver.takeRecords()" in perf_source and "this.observer.takeRecords()" in perf_source and
      "entry.startTime < this.observationWindowStart" in perf_source)
capture_sizes = []
for name in ["01-stress-before", "02-collapsed-setup-corrected", "03-expand-native", "04-collapse-native", "05-expand-native", "06-sampling-stopped"]:
    d = read(PERF / f"{name}.json")
    check(f"{name} BTw assets", d["assets"] == ["/assets/index-BTw7OHsD.js", "/assets/index--unhoRTb.css"])
    capture_sizes.append({"name": name, "svgStringLength": len(d["svgs"][0]), "svgHasClosingTag": d["svgs"][0].endswith("</svg>")})

before = read(UI / "before-save-reopen.json")
after = read(UI / "after-save-reopen.json")
reselected = read(UI / "same-document-after-reselect.json")
attrs = lambda d: dict(d["svgAttributes"])
doc_id = attrs(before)["data-document-id"]
check("first reload correctly retained as stress, not same-document success", attrs(after)["data-document-id"] != doc_id and
      attrs(after)["aria-label"] == "DenseStress300" and after["labels"] == [])
check("explicit reselect restores Transformer identity revision and label XML", attrs(reselected)["data-document-id"] == doc_id and
      attrs(reselected)["data-revision"] == attrs(before)["data-revision"] == "0" and
      before["labels"][0]["xml"] == reselected["labels"][0]["xml"])
check("camera preservation not claimed", before["paper"] != reselected["paper"] and
      read(UI / "receipt.json")["sameDocumentReopen"]["cameraPreservationClaim"] is False)
old_transformer = ET.fromstring(read(OLDUI / "02-transformer-normal-overview.json")["svgs"][0])
old_meta = json.loads(old_transformer.find("s:metadata", NS).text)
exports = []
for mode, x, y in [("whole-180mm", 280.5, 388.1), ("detail-180mm", 265.5, 400.1)]:
    directory = UI / "exports" / mode
    svg_path = directory / "figure.svg"
    receipt = read(directory / "figure.svg.receipt.json")
    document = read(directory / "document.json")
    svg = ET.parse(svg_path).getroot()
    meta = json.loads(svg.find("s:metadata", NS).text)
    check(f"{mode} output bytes and digest exact", binding(svg_path)["sha256"] == receipt["outputDigest"] == receipt["svgDigest"] and
          binding(svg_path)["bytes"] == receipt["bytes"])
    check(f"{mode} document source IR identity exact", document["id"] == meta["documentId"] == receipt["documentId"] == doc_id and
          document["revision"] == meta["revision"] == receipt["revision"] == 0 and
          document["sourceBindingDigest"] == document["architecture"]["sourceDigest"] == meta["sourceDigest"] == receipt["sourceDigest"] == old_meta["sourceDigest"] and
          document["architecture"]["irDigest"] == meta["irDigest"] == receipt["irDigest"] == old_meta["irDigest"])
    check(f"{mode} original source bytes exact", all(s["content"] == (ROOT / "fixtures/transformer" / s["path"]).read_text()
          for s in document["architecture"]["sources"]))
    check(f"{mode} original source facts and rendered bindings unchanged", meta["sourceFacts"] == old_meta["sourceFacts"] and
          meta["renderedBindings"] == old_meta["renderedBindings"]) 
    labels = [t for t in svg.findall(".//s:text", NS) if "".join(t.itertext()) == "memory"]
    check(f"{mode} one memory label expected point", len(labels) == 1 and float(labels[0].get("x")) == x and float(labels[0].get("y")) == y)
    edge_group = next(g for g in svg.findall(".//s:g", NS) if g.get("data-edge-id") == "edge:44")
    owned_path = edge_group.find("s:path", NS).get("d")
    path_numbers = [float(z) for z in re.findall(r"-?\d+(?:\.\d+)?", owned_path)]
    check(f"{mode} owned route remains 56 world units from caption baseline", len(path_numbers) == 3 and
          abs(path_numbers[1] - y) == 56 and re.fullmatch(r"M [-\d.]+ [-\d.]+ H [-\d.]+", owned_path) is not None)
    width = float(svg.get("width").removesuffix("mm"))
    vb = [float(z) for z in svg.get("viewBox").split()]
    size_pt = min(float(t.get("font-size")) for t in svg.findall(".//s:text", NS) if t.get("font-size")) * width / vb[2] * 72 / 25.4
    check(f"{mode} physical text size arithmetic", abs(size_pt - receipt["physicalPreflight"]["minTextPt"]) < 1e-10 and
          abs(width * vb[3] / vb[2] - receipt["heightMm"]) < 1e-10)
    exports.append({"mode": mode, "digest": receipt["outputDigest"], "bytes": receipt["bytes"], "documentId": doc_id,
                    "viewBox": vb, "labelPoint": [x, y], "ownedPath": owned_path, "captionBaselineRouteDistanceWorld": 56,
                    "nodeGroups": len([g for g in svg.findall(".//s:g", NS) if g.get("data-canonical-id")]),
                    "renderedEdgeGroups": len([g for g in svg.findall(".//s:g", NS) if g.get("data-edge-id")]),
                    "nominalMinTextPt": size_pt})
check("three exports use exact same saved CanvasDocument", all(read(UI / "exports" / m / "document.json") ==
      read(UI / "exports/whole-180mm/document.json") for m in ["detail-180mm", "pdf-attempt-1"]))
whole_svg = ET.parse(UI / "exports/whole-180mm/figure.svg").getroot()
whole_meta = json.loads(whole_svg.find("s:metadata", NS).text)
for name in ["03-transformer-local-100", "04-transformer-local-100-settled", "06-transformer-reselected-reopened", "07-transformer-reopened-100-settled"]:
    state = read(UI / f"{name}.json")
    svg = ET.fromstring(state["svgs"][0])
    metadata = json.loads(svg.find("s:metadata", NS).text)
    check(f"{name} full metadata equals whole export", metadata == whole_meta)
    check(f"{name} BTw assets", state["assets"] == ["/assets/index-BTw7OHsD.js", "/assets/index--unhoRTb.css"])
    memory = next(t for t in svg.findall(".//s:text", NS) if "".join(t.itertext()) == "memory")
    check(f"{name} memory remains 280.5 388.1", float(memory.get("x")) == 280.5 and float(memory.get("y")) == 388.1)
ranges = read(UI / "final-actual-label-card-ranges.json")
label_rect = ranges["memory"][0]["box"]
rect_hits = []
for card in ranges["cards"]:
    for index, body in enumerate(card["rects"]):
        r = body["box"].copy()
        if card["id"] == "call:instance:model.Transformer":
            r["height"] = 42  # Header strip only; model content is intended to contain labels.
        if min(label_rect["x"] + label_rect["width"], r["x"] + r["width"]) > max(label_rect["x"], r["x"]) and \
           min(label_rect["y"] + label_rect["height"], r["y"] + r["height"]) > max(label_rect["y"], r["y"]):
            rect_hits.append({"id": card["id"], "bodyIndex": index})
check("actual screen text rectangle clear of card bodies backplates and root header", rect_hits == [])
check("invalid routes observer preserved, not no-route certification", ranges["routes"] == [] and
      len([g for g in whole_svg.findall(".//s:g", NS) if g.get("data-edge-id")]) == 12)
assoc_report = read(ASSOC / "report.json")
check("association review correctly still reports 56 unimplemented", assoc_report["current"]["baselineVerticalDistanceFromOwnRoute"] == 56 and
      assoc_report["decorativeLeaderProposal"]["implemented"] is False)
pdf_path = UI / "exports/pdf-attempt-1/figure.pdf"
pdf_receipt = read(pdf_path.with_name("figure.pdf.receipt.json"))
check("actual PDF exists and digest receipt exact", pdf_path.read_bytes().startswith(b"%PDF-1.5") and
      binding(pdf_path)["sha256"] == pdf_receipt["outputDigest"] and binding(pdf_path)["bytes"] == pdf_receipt["bytes"])
pdf_attempt = subprocess.run(["pdfinfo", str(pdf_path)], capture_output=True, text=True)
pdf_fallback = subprocess.run(["/usr/bin/pdfinfo", str(pdf_path)], capture_output=True, text=True)
check("system PDF inspection completes despite bundled glibc mismatch", pdf_fallback.returncode == 0)
page = re.search(r"Page size:\s+([\d.]+) x ([\d.]+) pts", pdf_fallback.stdout)
pdf_points = [float(page.group(i)) for i in [1, 2]]
check("PDF single page matches requested physical dimensions", re.search(r"Pages:\s+1\b", pdf_fallback.stdout) is not None and
      abs(pdf_points[0] - 180 * 72 / 25.4) < .001 and
      abs(pdf_points[1] - pdf_receipt["heightMm"] * 72 / 25.4) < .001)
(OUT / "pdf-inspection.txt").write_text("Bundled pdfinfo attempt exit=" + str(pdf_attempt.returncode) + "\n" +
    pdf_attempt.stdout + pdf_attempt.stderr + "\nSystem /usr/bin/pdfinfo exit=" + str(pdf_fallback.returncode) + "\n" +
    pdf_fallback.stdout + pdf_fallback.stderr)
inputs_after = [binding(p) for p in sorted(paths)]
check("all independent inputs unchanged", inputs_before == inputs_after)

report = {"schema": "archcanvas-independent-btw-final-browser/1", "createdUtc": datetime.now(timezone.utc).isoformat(),
          "formalInterpreter": str(Path(sys.executable).absolute()), "method": "Independent arithmetic/relations/XML/hash/PDF page inspection; no product tests or imports.",
          "checks": checks, "inputCount": len(inputs_before), "inputsUnchanged": inputs_before == inputs_after, "seals": seals,
          "currentSourceBuildPlusValidatorBindings": 107, "historicalSnapshotsUnchanged": 121,
          "native": {"rows": native_rows, "p95Ms": 160, "eventTimingEntryCount": 45, "denominatorScope": "3 captured target toggles, not all inputs",
                     "rafCallbackCount": frames["frameCount"], "rafIntervalCount": len(intervals), "callbackHz": cadence,
                     "intervalP95Ms": p95(intervals), "maxIntervalMs": max(intervals), "intervalsOver50Ms": sum(x > 50 for x in intervals),
                     "presentedFps": None, "longTasks": raw["snapshot"]["longTasks"], "targetAnchorMaxCssPx": 0, "measuredPins": 0,
                     "canvasViewport": v, "window": raw["environment"]["viewport"], "visibility": raw["snapshot"]["visibility"],
                     "domFrontierBodies": len(coverage["bodies"]), "geometricIntersections": len(intersecting), "fullyContained": len(contained),
                     "panelRect": coverage["panel"], "viewportIs300Gate": False, "bXhViewportIsDifferent": True,
                     "sourceDrainBoundary": "snapshot drains already queued records, not entries the browser will produce later; 200-entry retention still bounds delivery.",
                     "captureSvgSizes": capture_sizes},
          "reopen": {"originalDocumentId": doc_id, "initialReloadDocumentId": attrs(after)["data-document-id"],
                     "explicitReselectDocumentId": attrs(reselected)["data-document-id"], "revision": 0, "cameraPreserved": False},
          "exports": exports, "pdf": {"bytes": pdf_receipt["bytes"], "digest": pdf_receipt["outputDigest"],
                                      "pagePoints": pdf_points, "pages": 1, "pixelReview": False,
                                      "bundledPdfinfoExitCode": pdf_attempt.returncode, "systemPdfinfoExitCode": pdf_fallback.returncode},
          "actualLabelRect": label_rect, "nonAncestorCardOrRootHeaderRectHits": rect_hits, "captionRouteDistanceWorld": 56,
          "rootActualRouteArrayInvalid": True, "humans": 0, "m4": "partial",
          "limitations": ["The three matched native samples exceed the 50 ms target but are not the full 300-visible-object acceptance run.",
                          "Different windows and canvas sizes prevent a before/after causal improvement claim.",
                          "rAF cadence does not prove actual presented FPS; fixed hardware/font bytes, repeated paired runs and complete input denominator absent.",
                          "Body viewport intersection is a geometric upper bound; benchmark panel can occlude visible objects.",
                          "Large public SVG helper captures remain truncated; complete export SVGs establish only these actual Transformer export modes.",
                          "03 screenshot stale pixels retained; 05 opens shared last-active stress; later explicit reselect is used for persistence.",
                          "Actual screen bounds clear card rectangles; no painted-glyph mask, rounded-fill or resolved-font certification.",
                          "Caption is 56 world units from its short owned arrow; no association-distance rule or guide implemented.",
                          "SVG physical size calculations and PDF page size inspection are not human 85/180 mm publication approval.",
                          "07 and 09 personally viewed by AI only; no model execution or human task session added."]}
(OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
(OUT / "input-receipt.json").write_text(json.dumps({"schema": "archcanvas-independent-btw-inputs/1", "inputs": inputs_before,
                                                 "inputsUnchanged": True}, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"checks": len(checks), "passed": sum(c["passed"] for c in checks), "inputs": len(inputs_before),
                  "p95Ms": 160, "rAFCallbackHz": cadence, "viewportIntersection": len(intersecting), "contained": len(contained),
                  "exports": len(exports), "ownedCaptionDistanceWorld": 56, "pdfPagePoints": pdf_points}, ensure_ascii=False))
