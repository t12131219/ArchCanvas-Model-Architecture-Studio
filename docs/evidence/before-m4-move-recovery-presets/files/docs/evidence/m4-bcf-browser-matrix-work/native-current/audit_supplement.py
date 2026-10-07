"""Independent additions for short pan and top-level DenseStress300 inputs.

Reads preserved evidence only; does not operate a browser or import product
code. The older audit helper is frozen and imported for XML/geometry utilities.
"""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
spec = importlib.util.spec_from_file_location("frozen_independent_native_audit", HERE / "audit_observations.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
seal, load, save, p95 = audit.seal, audit.load, audit.save, audit.p95


def native_contract(r):
    """Independent bilateral matching, operation binding and interaction max."""
    candidates = []
    entries = r["snapshot"]["eventTiming"]
    for t in r["trials"]:
        candidates.append([i for i, e in enumerate(entries) if t["trusted"] and e["name"] == t["eventName"] and e["targetCanonicalNodeId"] == t["targetId"] and e["interactionId"] > 0 and abs(e["startAt"] - t["eventAt"]) <= 8 and e["processingStart"] >= e["startAt"] and e["processingEnd"] >= e["processingStart"] and math.isfinite(e["durationMs"]) and e["durationMs"] >= 0])
    reverse = {i: [j for j, c in enumerate(candidates) if i in c] for i in range(len(entries))}
    trials, interaction_max = [], {}
    for j, t in enumerate(r["trials"]):
        c = candidates[j]
        i = c[0] if len(c) == 1 and len(reverse[c[0]]) == 1 else None
        e = entries[i] if i is not None else None
        assert t["nativeEventTiming"] == e and t["nativeInputToNextPaintMs"] == (e["durationMs"] if e else None)
        a, b = t["before"], t["after"]
        valid = b is not None and all(a[k] == b[k] for k in ("documentId", "sourceDigest", "irDigest")) and b["revision"] == a["revision"] + 1
        changed = valid and (t["targetId"] in a["expandedIds"]) == (t["operation"] == "collapse") and (t["targetId"] in b["expandedIds"]) == (t["operation"] == "expand")
        assert t["bindingValid"] == valid and t["targetChanged"] == changed
        anchor = math.hypot(a["anchors"][t["targetId"]]["screen"]["x"] - b["anchors"][t["targetId"]]["screen"]["x"], a["anchors"][t["targetId"]]["screen"]["y"] - b["anchors"][t["targetId"]]["screen"]["y"]) if changed else None
        assert t["anchorScreenDisplacementPx"] == anchor
        if changed and not t["error"] and e:
            interaction_max[e["interactionId"]] = max(interaction_max.get(e["interactionId"], 0), e["durationMs"])
        trials.append({"trial": j + 1, "operation": t["operation"], "targetId": t["targetId"], "trusted": t["trusted"], "eventAt": t["eventAt"], "capturedAt": t["capturedAt"], "beforeRevision": a["revision"], "afterRevision": b["revision"] if b else None, "bindingValid": valid, "targetChanged": changed, "error": t["error"], "beforeVisibleCount": len(a["visibleIds"]), "afterVisibleCount": len(b["visibleIds"]) if b else None, "candidateIndices": c, "bilateralUniqueMatchIndex": i, "interactionId": e["interactionId"] if e else None, "durationMs": e["durationMs"] if e else None, "processingMs": e["processingEnd"] - e["processingStart"] if e else None, "anchorScreenDisplacementPx": anchor, "beforePinIds": a["pinnedIds"], "measuredPinCount": len(t["pins"])})
    f = r["frames"]
    assert len(f["intervals"]) == f["frameCount"] - 1
    assert abs(sum(f["intervals"]) - (f["lastFrameAt"] - f["firstFrameAt"])) < .0001
    return {"trials": trials, "bilateralUniqueMatchesAgreeSampler": True, "validMatchedInteractionMaxMs": interaction_max, "validMatchedInteractionP95Ms": p95(list(interaction_max.values())), "interactionCount": len(interaction_max), "frameIntervalSumEqualsLastMinusFirst": True, "frameCount": f["frameCount"], "declaredFrameBufferTruncated": f["bufferTruncated"], "callbackIntervalP95Ms": p95(f["intervals"]), "callbackIntervalMaxMs": max(f["intervals"]), "scope": "Matched expansion/collapse interactions only; no page INP or presented frame rate"}


def main():
    destination = HERE / (sys.argv[1] if len(sys.argv) > 1 else "independent-supplement-audit-1")
    assert destination.parent == HERE and destination.name.startswith("independent-supplement-audit-")
    assert not destination.exists()
    short = HERE / "mlp-four-pan-short-1"
    stress = HERE / "top-stress300-separated"
    mlp_canonical = ROOT / "docs/evidence/browser-visual-matrix-bcf-full/captures/mlp-level1-paper-180/canvas.json"
    stress_canonical = ROOT / "docs/evidence/m4-current-native-diagnostic/stress300-store-canvas-architecture-model.DenseStress300-24baae6df5c3-d01ce879.json"
    native_sources = [ROOT / p for p in ("studio/src/nativePerformance.ts", "studio/src/perf.ts", "studio/src/PerfBenchmarkPanel.tsx", "studio/src/App.tsx")]
    analyzer = ROOT / "docs/evidence/m4-bcf-browser-matrix-work/routing-quality/analyze_scene.ts"
    r = load(short / "raw-full.json")
    product_bindings = [ROOT / x["path"] for x in r["context"]["productionAssets"] + r["context"]["probeSources"]]
    files = sorted(p for d in (short, stress) for p in d.rglob("*") if p.is_file()) + [mlp_canonical, stress_canonical, HERE / "audit_observations.py", Path(__file__), ROOT / "scripts/validate_input_observation.mjs", ROOT / "scripts/validate_native_performance.mjs", analyzer, ROOT / "docs/evidence/m4-routing-refinement/independent/oracle.ts"] + native_sources + product_bindings
    before = [seal(p) for p in files]
    destination.mkdir()
    for name, source, script in (("short-pan", short / "raw-full.json", "validate_input_observation.mjs"), ("stress300", stress / "raw-full.json", "validate_native_performance.mjs")):
        command = ["node", str(ROOT / "scripts" / script), str(source)]
        process = subprocess.run(command, capture_output=True, text=True)
        save(destination / (name + "-validator-execution.json"), {"command": command, "exitCode": process.returncode, "stdout": process.stdout, "stderr": process.stderr})
        assert process.returncode == 0
        save(destination / (name + "-validator.json"), json.loads(process.stdout))
    v = load(destination / "short-pan-validator.json")
    short_match = audit.matching_audit(r, v)
    short_trials = audit.audit_trials(r, v)
    assert v["completeBuffers"] and all(t["operationSucceeded"] for t in v["trials"])
    assert all(t["independentRecordedTerminalCamera"]["matched"] for t in short_trials)
    assert all(t["revisionDelta"] == 0 and t["sourceAndIRUnchanged"] for t in short_trials)
    assert all(all(t["publicMarkupContinuity"].values()) for t in short_trials)
    short_read = load(short / "read-receipt.json")
    short_bytes = (short / "raw-full.json").read_bytes()
    assert len(short_bytes.decode()) == short_read["actualTextareaCharacters"]
    journal = load(short / "journal.json")
    assert len(journal) == len(r["trials"])
    journal_checks = []
    for j, trial in zip(journal, r["trials"]):
        assert j == load(short / (j["direction"] + ".json"))
        assert j["before"]["svg"] == trial["before"]["svgMarkup"]
        assert j["after"]["svg"] == trial["after"]["svgMarkup"]
        assert j["before"]["transform"] == trial["before"]["camera"]["cssTransform"]
        assert j["after"]["transform"] == trial["after"]["camera"]["cssTransform"]
        assert int(j["before"]["revision"]) == trial["before"]["revision"] and int(j["after"]["revision"]) == trial["after"]["revision"]
        journal_checks.append({"direction": j["direction"], "publicSVGAndCameraExactRaw": True, "journalFinishedAtUTC": j["finishedAt"], "browserRawFinishedAtUTC": datetime.fromtimestamp((r["environment"]["timeOrigin"] + trial["finishedAt"]) / 1000, timezone.utc).isoformat()})
    document = load(mlp_canonical)
    document = document.get("document", document)
    for t in r["trials"]:
        for kind in ("before", "after"):
            audit.parse_public_geometry(t[kind], document["architecture"])
    contexts = []
    for declared in r["context"]["productionAssets"] + r["context"]["probeSources"]:
        actual = seal(ROOT / declared["path"])
        assert actual["sha256"] == declared["sha256"] and actual["bytes"] == declared["bytes"]
        contexts.append({"declared": declared, "actual": actual, "exact": True})
    short_summary = {"raw": seal(short / "raw-full.json"), "readReceiptCharactersEqualFile": True, "chunksRetainedForIndependentReassembly": False, "rawMeasurementWindowMs": r["stoppedAt"] - r["startedAt"], "completeBuffers": v["completeBuffers"], "bufferAccounting": r["buffers"], "counts": {k: len(r[k]) for k in ("events", "eventTiming", "frames", "visibility", "longTasks", "errors")}, "allFourRecordedPanTrialsPassedExistingValidator": True, "independentEventTiming": short_match, "trials": short_trials, "publicXMLCanonicalSnapshotsChecked": 8, "journalChecks": journal_checks, "sourceContext": contexts, "hiddenCanvasHistoryCertified": False, "noPinProtectionClaim": True, "limits": ["Raw browser measurement window4547ms; later UI read and journal wall timestamps use separate clocks; do not replace it with41.6sec", "Root attributes nine contiguous textarea slices; individual slices not retained, only valid full file/read receipt", "Atomic drags cover completed gestures, not held-pointer Escape/blur/cancel", "Selection, pins/frontier and SVG exact; no saved hidden Canvas/history or persistence evidence", "ET is matched discrete subset; changed-geometry proxies and rAF are not presented frames", "Fonts/hardware uncontrolled; same-origin iframe; AIoperator not human"]}
    save(destination / "short-pan-audit.json", short_summary)
    native = load(stress / "raw-full.json")
    independent_native = native_contract(native)
    assert len(independent_native["trials"]) == 3 and all(t["bindingValid"] and t["targetChanged"] and t["trusted"] for t in independent_native["trials"])
    assert independent_native["validMatchedInteractionP95Ms"] == 176
    native_read = load(stress / "read-receipt.json")
    assert len((stress / "raw-full.json").read_text()) == native_read["textareaCharacters"]
    truncated = (stress / "raw-single-read.json").read_text()
    try:
        json.loads(truncated)
        parse_error = None
    except json.JSONDecodeError as e:
        parse_error = str(e)
    assert parse_error is not None
    dom = load(stress / "final-public-dom.json")
    expanded = load(stress / "expanded-observation.json")
    svg_read = load(stress / "svg-read-receipt.json")
    svg_bytes = (stress / "final-browser-scene-full.svg").read_bytes()
    assert len(svg_bytes.decode()) == svg_read["domOuterHtmlCharacters"]
    svg = ET.fromstring(svg_bytes)
    meta = json.loads(svg.find(audit.NS + "metadata").text)
    assert meta["documentId"] == native["trials"][-1]["after"]["documentId"] and meta["revision"] == native["trials"][-1]["after"]["revision"]
    source_document = load(stress_canonical)
    source_document = source_document.get("document", source_document)
    public = {"svgMarkup": svg_bytes.decode(), "documentId": meta["documentId"], "revision": meta["revision"], "sourceDigest": meta["sourceDigest"], "irDigest": meta["irDigest"], "visibleIds": native["trials"][-1]["after"]["visibleIds"], "expandedIds": dom["expandedIds"], "objects": {}}
    scene = audit.parse_public_geometry(public, source_document["architecture"])
    assert len(scene["nodes"]) == expanded["actualNodeCount"] == dom["nodeCount"] == 304
    assert len(scene["edges"]) == expanded["actualRouteCount"] == dom["routeCount"] == 302
    assert svg.get("viewBox") == expanded["viewBox"] == "0 0 595 30542"
    assert meta["sourceFacts"] == expanded["metadata"]["sourceFacts"]
    assert meta["renderedBindings"] == expanded["metadata"]["renderedBindings"]
    assert meta["renderedNodes"] == expanded["metadata"]["renderedNodes"]
    save(destination / "stress300.public-xml-scene.json", scene)
    command = ["node", "--experimental-strip-types", str(analyzer), str(destination / "stress300.public-xml-scene.json")]
    process = subprocess.run(command, capture_output=True, text=True)
    save(destination / "stress300-routing-execution.json", {"command": command, "exitCode": process.returncode, "stdout": process.stdout, "stderr": process.stderr})
    assert process.returncode == 0
    routing = json.loads(process.stdout)
    save(destination / "stress300-routing.json", routing)
    assets = [{"url": url, "disk": seal(ROOT / "studio/dist" / url.split("8982/", 1)[1])} for url in dom["assetUrls"]]
    viewport_equal = all(native["environment"]["viewport"][k] == dom["viewport"][k] for k in ("width", "height"))
    save(destination / "stress300-audit.json", {"raw": seal(stress / "raw-full.json"), "rawCharactersEqualReceipt": True, "truncatedSingleRead": {**seal(stress / "raw-single-read.json"), "jsonParseError": parse_error}, "originalPublicDomSvgCharacters": len(dom["svg"]), "originalPublicDomSvgEqualsFull": dom["svg"] == svg_bytes.decode(), "fullSvg": seal(stress / "final-browser-scene-full.svg"), "fullSvgCharactersEqualReceipt": True, "chunksRetainedForIndependentReassembly": False, "canonicalReference": seal(stress_canonical), "canonicalReferenceUse": "Previously sealed architecture facts only, not current saved300-node canvas", "publicSourceProjectionExact": True, "publicNodes": len(scene["nodes"]), "publicRoutes": len(scene["edges"]), "actualViewBox": scene["bounds"], "paperWidthAttribute": svg.get("width"), "paperHeightAttribute": svg.get("height"), "physicalHeightMmFromMetadata": meta["heightMm"], "sameRecordedRawAndPublicViewport": viewport_equal, "rawEnvironment": native["environment"], "laterPublicViewport": dom["viewport"], "assetUrlDiskBindings": assets, "sourceBindings": [seal(p) for p in native_sources], "nativeIndependentContract": independent_native, "rawLongTasks": native["snapshot"]["longTasks"], "rawVisibility": native["snapshot"]["visibility"], "routing": {k: routing[k] for k in ("distinctTensor", "sameTensor", "totalBends", "totalReversals", "bodyHeaderIntrusions", "endpointAndViewBoxCheck")}, "bodyGeometry": audit.collision_geometry(scene), "limits": ["3real trusted toggle inputs; no20synthetic groups, no fullperformancepopulation", "Frame6547 under20000 cap, declaredfalse; ET60/longTasks2 under200 rolling cap, but no explicit dropped accounting exists for those older sampler fields", "Source sampler sequential unique join and pertrialdurations; independent bilateralinteractionmax agrees for these3distinctinteractions only", "Native telemetry geometry is selected public anchors sampled after2rAF, not paint or hiddenhistory", "Read receipts attribute11raw and18SVG UI slices; individual slices not retained, cannot independently replay chunk origin/reassembly", "Public asset URLs bind disk file hashes, not fetched bytes or compile provenance of every source", "304visible nodes302routes prove static full-source expansion only, not executable forward semantics", "180mm paper height9239.6mm is actual single-strip geometry, not publicationapproval or practicalpageproof", "Sourcefacts/projection checked against previously sealed architecture, not current savedCanvas persistence", "Callback interval /approx60rAF cadence is not presentedframe rate or smoothness", "No pins, hardware orresolvedfontlock; AIoperator nothuman"]})
    assert [seal(p) for p in files] == before
    aggregate = {"schema": "archcanvas-independent-native-supplement/1", "createdAtUTC": datetime.now(timezone.utc).isoformat(), "inputsUnchanged": True, "inputBindings": before, "shortPanCompleteBuffers": True, "shortPanValidOperations": 4, "shortPanWindowMs": short_summary["rawMeasurementWindowMs"], "shortPanET": {k: short_match[k] for k in ("eligibleAssignedInputs", "matchedAssignedInputs", "matchedInteractions", "matchedInteractionP95Ms")}, "stressValidSceneTrials": 3, "stressMatchedInteractions": independent_native["interactionCount"], "stressMatchedInteractionP95Ms": independent_native["validMatchedInteractionP95Ms"], "stressPublicNodes": 304, "stressPublicRoutes": 302, "humanCertified": False, "publicationCertified": False, "presentedPerformanceCertified": False, "scope": "New independent shortpan/stress samples supplement, never overwrite long-session overflow or rapidpilot failures"}
    save(destination / "audit-summary.json", aggregate)
    save(destination / "manifest.json", {"schema": "archcanvas-independent-native-supplement-manifest/1", "inputsUnchanged": True, "inputs": before, "outputs": [seal(p) for p in sorted(destination.iterdir()) if p.is_file()]})
    print(json.dumps({"output": str(destination), "summary": {k: v for k, v in aggregate.items() if k not in ("inputBindings", "scope")}, "manifest": seal(destination / "manifest.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
