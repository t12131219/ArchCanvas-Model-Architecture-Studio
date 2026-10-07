"""Read-only, byte-bound performance-condition audit; no browser operations."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from math import ceil, isfinite
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def stats(values):
    values = sorted(values)
    return {"count": len(values), "min": min(values) if values else None,
            "p95NearestRank": values[ceil(len(values) * .95) - 1] if values else None,
            "max": max(values) if values else None}


def native(d):
    trials, entries = d["trials"], d["snapshot"]["eventTiming"]
    candidates = []
    for t in trials:
        candidates.append([i for i, e in enumerate(entries)
                           if t["trusted"] and e["name"] == t["eventName"]
                           and e.get("targetCanonicalNodeId") == t["targetId"]
                           and e["interactionId"] > 0
                           and abs(e["startAt"] - t["eventAt"]) <= 8
                           and e["startAt"] <= e["processingStart"] <= e["processingEnd"]
                           and isfinite(e["durationMs"]) and e["durationMs"] >= 0])
    used = Counter(i for indices in candidates for i in indices)
    results, matched = [], []
    for t, indices in zip(trials, candidates):
        before, after = t["before"], t["after"]
        bound = bool(after and all(after[k] == before[k] for k in ("documentId", "sourceDigest", "irDigest"))
                     and after["revision"] == before["revision"] + 1)
        changed = bool(bound and (t["targetId"] in before["expandedIds"]) == (t["operation"] == "collapse")
                       and (t["targetId"] in after["expandedIds"]) == (t["operation"] == "expand"))
        index = indices[0] if len(indices) == 1 and used[indices[0]] == 1 else None
        e = entries[index] if index is not None else None
        valid = changed and not t["error"]
        if valid and e:
            matched.append(e["durationMs"])
        results.append({"targetId": t["targetId"], "operation": t["operation"],
                        "eventAt": t["eventAt"], "candidateIndexes": indices, "uniqueIndex": index,
                        "bindingValid": bound, "targetChanged": changed, "error": t["error"],
                        "visibleCounts": [len(before["visibleIds"]), len(after["visibleIds"]) if after else None],
                        "durationMs": e["durationMs"] if e else None,
                        "queueMs": e["processingStart"] - e["startAt"] if e else None,
                        "processingMs": e["processingEnd"] - e["processingStart"] if e else None,
                        "captureTimestampMinusNativeEventMs": t["capturedAt"] - t["eventAt"],
                        "storedMatchAgrees": t["nativeEventTiming"] == e})
    f = d["frames"]
    span = f["lastFrameAt"] - f["firstFrameAt"] if f["frameCount"] > 1 else None
    cadence = (f["frameCount"] - 1) * 1000 / span if span else None
    valid_count = sum(r["bindingValid"] and r["targetChanged"] and not r["error"] for r in results)
    return {"capturedExpansionTrials": len(trials), "validSceneTrials": valid_count,
            "matchedValidExpansionTrials": len(matched), "matchedExpansionDurationsMs": stats(matched),
            "storedSummaryCountAndP95Agree": d["summary"]["capturedTrials"] == len(trials)
            and d["summary"]["validSceneTrials"] == valid_count
            and d["summary"]["matchedNativeTrials"] == len(matched)
            and d["summary"]["nativeInputToNextPaintP95Ms"] == stats(matched)["p95NearestRank"],
            "trials": results, "allObservedEventTimingEntries": len(entries),
            "allObservedEventTimingByName": dict(Counter(e["name"] for e in entries)),
            "allObservedPositiveInteractionIds": sorted({e["interactionId"] for e in entries if e["interactionId"] > 0}),
            "allNativeInputEventsDenominatorAvailable": False,
            "longTaskCount": len(d["snapshot"]["longTasks"]),
            "domVisibility": d["snapshot"]["visibility"], "environment": d["environment"],
            "elapsedMs": d["elapsedMs"], "frameCount": f["frameCount"],
            "rafTimestampSpanMs": span, "rafCallbackCadencePerSecond": cadence,
            "rafIntervalsMs": stats(f["intervals"]),
            "rafIntervalsAtLeast500Ms": sum(i >= 500 for i in f["intervals"]),
            "presentedFpsCertified": False, "allPageInpCertified": False}


def control(d):
    start, end = d["deadlines"]["captureStart"], d["deadlines"]["captureEnd"]
    frames = [f for f in d["frames"] if start <= f["timestamp"] < end and start <= f["observedAt"] < end]
    times = [f["timestamp"] for f in frames]
    intervals = [b - a for a, b in zip(times, times[1:])]
    eligible = [e for e in d["eventTiming"] if start <= e["startAt"] < end and e["target"]["inMeasuredSurface"]]
    measured_inputs = [i for i in d["inputs"] if i["trusted"] and i["target"]["inMeasuredSurface"] and start <= i["eventAt"] < end]
    return {"label": d["label"], "mode": d["mode"], "surfaceKind": d["surfaceKind"],
            "captureWindowMs": end - start, "allRawFrames": len(d["frames"]), "includedFrames": len(frames),
            "rafCallbackCadencePerSecond": (len(times) - 1) * 1000 / (times[-1] - times[0]) if len(times) > 1 else None,
            "rafIntervalsMs": stats(intervals), "rafIntervalsAtLeast500Ms": sum(i >= 500 for i in intervals),
            "frameDomFlagCombinations": dict(Counter(str((f["visibility"], f["focused"], f["topVisibility"], f["topFocused"])) for f in frames)),
            "environmentStart": d["environment"], "environmentChanges": d["environmentChanges"],
            "allRawInputs": len(d["inputs"]), "trustedMeasuredCaptureInputs": len(measured_inputs),
            "trustedMeasuredCaptureInputTypes": dict(Counter(i["type"] for i in measured_inputs)),
            "allObservedEventTimingEntries": len(d["eventTiming"]),
            "measuredCaptureEventTimingEntries": len(eligible),
            "eventTimingStartPhases": dict(Counter(e["startPhase"] for e in d["eventTiming"])),
            "allLongTaskCount": len(d["longTasks"]),
            "directSelfCostMs": {key: stats(v["durationMs"] for v in values) for key, values in d["overhead"].items()},
            "selfCostsOverlap": True, "presentedFpsCertified": False}


def bind(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": sha256(data).hexdigest()}


if __name__ == "__main__":
    sources = ["AGENTS.md", "skills/archcanvas/SKILL.md", "studio/src/nativePerformance.ts", "studio/src/perf.ts",
               "studio/src/PerfBenchmarkPanel.tsx", "studio/dist/index.html", "studio/dist/assets/index-DuFXKOwG.js",
               "studio/dist/assets/index--unhoRTb.css", "scripts/m4_input_observer.mjs",
               "docs/evidence/m4-performance-controls-work/measurement-contract.json",
               "docs/evidence/m4-performance-controls-work/observer.mjs",
               "docs/evidence/m4-performance-controls-work/control.html",
               "docs/evidence/m4-performance-controls-work/analysis-attempt-3/receipt.json",
               "docs/evidence/m4-performance-controls-work/analysis-attempt-3/supplement-receipt.json",
               "docs/evidence/m4-native-matching-work/browser-smoke/raw.json",
               "docs/evidence/m4-native-matching-work/browser-smoke/assets.public.json",
               "docs/evidence/m4-visible-host-control/raw.json",
               "docs/evidence/m4-visible-host-control/validation.json",
               "docs/evidence/m4-visible-host-control/host-presentation-observations.json",
               "docs/evidence/m4-visible-host-control/README.md"]
    sources += [f"docs/evidence/m4-performance-controls-work/browser-batch-1/{name}.json"
                for name in ("control-raf-idle-r1", "control-full-click-r1", "control-full-idle-r1", "tool-action-log", "tool-action-log-supplement-1")]
    sources += [f"docs/evidence/m4-performance-controls-work/analysis-attempt-3/raw-{i:02d}-audit.json" for i in (1, 2, 3)]
    sources += [str(p.relative_to(ROOT)) for p in sorted((ROOT / "docs/evidence/m4-dufx-performance-visibility").glob("*.json"))]
    paths = [ROOT / p for p in sources] + [ROOT.parent / "ArchCanvas_双向模型可视化与编辑框架_技术计划书.md", Path(__file__)]
    before = [bind(p) for p in paths]
    archived = []
    for index, p in enumerate(paths):
        copy = OUT / "inputs" / f"{index:02d}-{p.name}"
        copy.parent.mkdir(parents=True, exist_ok=True)
        if copy.exists():
            raise RuntimeError(f"Refusing to overwrite audit snapshot: {copy}")
        copy.write_bytes(p.read_bytes())
        archived.append({**before[index], "snapshot": str(copy.relative_to(OUT)), "snapshotSha256": sha256(copy.read_bytes()).hexdigest()})
    load = lambda rel: json.loads((ROOT / rel).read_text())
    historical = native(load("docs/evidence/m4-native-matching-work/browser-smoke/raw.json"))
    controls = [control(load(f"docs/evidence/m4-performance-controls-work/browser-batch-1/{name}.json"))
                for name in ("control-raf-idle-r1", "control-full-click-r1", "control-full-idle-r1")]
    current = {p.name: native(json.loads(p.read_text())) for p in sorted((ROOT / "docs/evidence/m4-dufx-performance-visibility").glob("*-raw.json"))}
    previous_visible = load("docs/evidence/m4-visible-host-control/raw.json")
    visible_times = previous_visible["frames"]
    visible_intervals = [b - a for a, b in zip(visible_times, visible_times[1:])]
    visible_review = {"frameCount": len(visible_times),
                      "elapsedMs": previous_visible["stoppedAt"] - previous_visible["startedAt"],
                      "rafCallbackCadencePerSecond": (len(visible_times) - 1) * 1000 / (visible_times[-1] - visible_times[0]),
                      "rafIntervalsMs": stats(visible_intervals),
                      "hostObservations": load("docs/evidence/m4-visible-host-control/host-presentation-observations.json"),
                      "longTasksObservationAvailable": False, "continuousHostVisibilityCertified": False}
    report = {"protocol": "archcanvas-current-performance-condition-review/1", "createdUtc": datetime.now(timezone.utc).isoformat(),
              "historicalD60": historical, "historicalMinimalControls": controls, "currentDuFX": current,
              "historicalControlWithTwoHostTrueReadings": visible_review,
              "humanParticipants": 0, "presentedPerformanceCertified": False, "causeIdentified": False,
              "browserOperatedByThisAuditor": False, "sourceOrProductChangedByThisAuditor": False}
    (OUT / "independent-statistics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    after = [bind(p) for p in paths]
    receipt = {"protocol": "archcanvas-current-performance-condition-review-bindings/1", "inputs": archived,
               "inputBindingsAfter": after, "inputsUnchangedDuringAudit": before == after,
               "archiveCopiesExact": all(item["sha256"] == item["snapshotSha256"] for item in archived),
               "statisticsBinding": bind(OUT / "independent-statistics.json")}
    (OUT / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"inputs": len(paths), "inputsUnchanged": before == after,
                      "archiveCopiesExact": receipt["archiveCopiesExact"], "currentLabels": list(current)}, ensure_ascii=False))
