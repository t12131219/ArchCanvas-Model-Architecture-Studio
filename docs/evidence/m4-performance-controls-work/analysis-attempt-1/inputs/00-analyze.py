"""Independent raw-receipt audit; never imports the browser helper or product.

All supplied attempts are retained. Exclusive output directories prevent retries
from overwriting failures. Statistics are scheduling/DOM/EventTiming diagnostics,
not certification of real display presentation or overall INP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROTOCOL = "archcanvas-fixed-window-performance-observation/1"
DISCRETE = {"pointerdown", "pointerup", "click", "keydown", "keyup"}
PHASE_NAMES = {"warmup", "capture", "drain", "after-planned-drain"}


def binding(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def near(left: Any, right: Any, tolerance: float = 1e-7) -> bool:
    return finite(left) and finite(right) and abs(left - right) <= tolerance


def distribution(values: list[float]) -> dict:
    valid = sorted(value for value in values if finite(value))
    count = len(valid)
    return {"count": count, "min": valid[0] if count else None,
            "median": (valid[(count - 1) // 2] + valid[count // 2]) / 2 if count else None,
            "p95NearestRank": valid[math.ceil(count * .95) - 1] if count else None,
            "max": valid[-1] if count else None, "sum": sum(valid),
            "mean": sum(valid) / count if count else None, "sortedValues": valid}


def counts(items: list, key) -> dict:
    return dict(Counter(str(key(item)) for item in items))


def phase_at(at: float, deadlines: dict) -> str:
    if deadlines.get("captureStart") is None or at < deadlines["captureStart"]:
        return "warmup"
    if at < deadlines["captureEnd"]:
        return "capture"
    if at < deadlines["drainEnd"]:
        return "drain"
    return "after-planned-drain"


def inspect_receipt(raw: dict, baseline: dict | None = None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    check(raw.get("protocol") == PROTOCOL, "raw protocol differs from the frozen measurement protocol")
    mode = raw.get("mode")
    check(mode in {"full", "raf-only"}, "invalid mode")
    check(raw.get("surfaceKind") in {"control", "studio"}, "invalid surface")
    check(raw.get("humanParticipants") == 0 and raw.get("modelsExecuted") is False, "human/model scope flags are inconsistent")
    check(raw.get("presentedPerformanceCertified") is False and raw.get("overallInpCertified") is False, "diagnostic receipt claims forbidden certification")
    measurement = raw["measurement"]
    for name, expected in [("warmupMs", 2000), ("captureMs", 20000), ("inputDeadlineMs", 10000), ("minimumPostInputSettleMs", 10000), ("deliveryDrainMs", 2000), ("matchingToleranceMs", 2), ("eventTimingRequestedDurationThresholdMs", 16)]:
        check(measurement.get(name) == expected, f"measurement {name} differs from frozen value {expected}")
    check(measurement.get("externalPresentationKnown") is False, "external presentation cannot be inferred")
    deadlines = raw["deadlines"]
    check(near(deadlines.get("warmupEnd"), deadlines.get("warmupStart", math.nan) + 2000), "warmup deadline is not exactly 2000 ms")
    complete = raw.get("status") == "fixed-window-complete"
    capture = deadlines.get("captureStart") is not None
    if capture:
        for name, offset in [("inputDeadline", 10000), ("captureEnd", 20000), ("drainEnd", 22000)]:
            check(near(deadlines.get(name), deadlines["captureStart"] + offset), f"{name} was changed from the fixed capture clock")
    check(not complete or capture, "complete window has no capture start")
    boundaries = raw["boundaries"]
    check(all(finite(item.get("actualAt")) for item in boundaries), "nonfinite boundary actual timestamp")
    check(all(a["actualAt"] <= b["actualAt"] for a, b in zip(boundaries, boundaries[1:])), "boundary timestamps decrease")
    expected_boundaries = {"warmup-end": deadlines.get("warmupEnd"), "capture-start": deadlines.get("captureStart"),
                           "capture-end": deadlines.get("captureEnd"), "fixed-window-complete": deadlines.get("drainEnd")}
    if complete:
        for name in expected_boundaries:
            check(sum(item["name"] == name for item in boundaries) == 1, f"complete window lacks exactly one {name} boundary")
    for item in boundaries:
        if item.get("plannedAt") is not None:
            check(near(item["latenessMs"], item["actualAt"] - item["plannedAt"]), f"boundary lateness arithmetic differs for {item['name']}")
            if item["name"] in expected_boundaries:
                check(near(item["plannedAt"], expected_boundaries[item["name"]]), f"boundary plannedAt differs for {item['name']}")
            check(item["actualAt"] >= item["plannedAt"] - 2, f"boundary fired more than 2 ms early for {item['name']}")
        try:
            datetime.fromisoformat(item["utc"].replace("Z", "+00:00"))
        except (ValueError, KeyError, TypeError):
            check(False, f"invalid boundary UTC for {item.get('name')}")
    check(finite(raw.get("disconnectedAt")), "missing actual disconnection timestamp")
    check(not boundaries or raw["disconnectedAt"] >= boundaries[-1]["actualAt"], "disconnection timestamp predates final boundary")
    for environment in [raw["environment"], raw["endEnvironment"]]:
        check(finite(environment.get("timeOrigin")) and finite(environment.get("monotonicAt")), "invalid environment monotonic/time-origin clock")
        check(environment["fonts"].get("resolvedGlyphBytesKnown") is False, "fonts claim unsupported resolved glyph bytes")
        check(environment["flags"]["coverage"].get("externalOcclusionKnown") is False, "coverage claims external occlusion knowledge")
    check(near(raw["environment"]["timeOrigin"], raw["endEnvironment"]["timeOrigin"]), "measured document timeOrigin changed")
    coverage_records = [raw["environment"]["flags"]["coverage"], raw["endEnvironment"]["flags"]["coverage"],
                        *(item["coverage"] for item in raw["environmentChanges"])]
    coverage_records.extend(item["geometry"]["coverage"] for item in raw["frames"] if item.get("geometry") is not None)
    for index, coverage in enumerate(coverage_records):
        rect, viewport = coverage["rect"], coverage["viewport"]
        check(all(finite(rect.get(name)) for name in ["x", "y", "width", "height"]), f"invalid measured rect at record {index}")
        check(finite(viewport.get("width")) and finite(viewport.get("height")), f"invalid top viewport at record {index}")
        expected_inside = rect["x"] >= 0 and rect["y"] >= 0 and rect["x"] + rect["width"] <= viewport["width"] + .5 and rect["y"] + rect["height"] <= viewport["height"] + .5
        check(coverage["fullyInsideTopViewport"] == expected_inside, f"coverage inside flag differs from rect arithmetic at record {index}")
    initial_rect = raw["environment"]["flags"]["coverage"]["rect"]
    check(near(initial_rect["width"], 1280) and any(near(initial_rect["height"], height) for height in [576, 720]), "initial measured size is outside frozen viewport profiles")

    inputs, native_entries, tasks, frames = (raw[name] for name in ["inputs", "eventTiming", "longTasks", "frames"])
    check(len({item["id"] for item in inputs}) == len(inputs), "duplicate raw native input ID")
    for item in inputs:
        check(finite(item.get("eventAt")) and finite(item.get("capturedAt")), f"invalid native timestamp {item.get('id')}")
        check(isinstance(item.get("trusted"), bool), f"native trusted flag is not boolean {item.get('id')}")
        check(item["eventPhase"] == phase_at(item["eventAt"], deadlines), f"native eventPhase mismatch {item['id']}")
        check(item["deliveryPhase"] == phase_at(item["capturedAt"], deadlines), f"native deliveryPhase mismatch {item['id']}")
        check(isinstance(item["target"].get("inMeasuredSurface"), bool), f"surface flag is not boolean {item['id']}")
    check(all(a["capturedAt"] <= b["capturedAt"] for a, b in zip(inputs, inputs[1:])), "native observer timestamps decrease")
    for category, items in [("EventTiming", native_entries), ("longtask", tasks)]:
        for index, item in enumerate(items):
            check(finite(item.get("startAt")) and finite(item.get("observedAt")), f"invalid {category} clocks at index {index}")
            check(item["startPhase"] == phase_at(item["startAt"], deadlines), f"{category} start phase differs at index {index}")
            check(item["deliveryPhase"] == phase_at(item["observedAt"], deadlines), f"{category} delivery phase differs at index {index}")
            check(item.get("origin") in {"callback", "capture-fixed-drain", "final-fixed-drain", "cancel-drain"}, f"unknown {category} delivery origin")
    for index, item in enumerate(frames):
        check(finite(item.get("timestamp")) and finite(item.get("observedAt")), f"invalid rAF clocks at index {index}")
        check(item["timestampPhase"] == phase_at(item["timestamp"], deadlines), f"rAF timestamp phase differs at index {index}")
        check(item["deliveryPhase"] == phase_at(item["observedAt"], deadlines), f"rAF delivery phase differs at index {index}")
        check(item["observedAt"] >= item["timestamp"] - 2, f"rAF timestamp is later than observation at index {index}")
        check((item["geometry"] is None) == (mode == "raf-only"), f"rAF geometry disagrees with mode at index {index}")
    check(all(a["timestamp"] <= b["timestamp"] for a, b in zip(frames, frames[1:])), "rAF timestamps decrease")
    check(all(a["observedAt"] <= b["observedAt"] for a, b in zip(frames, frames[1:])), "rAF observation clocks decrease")

    raw_arrays = {"frames": frames, "inputs": inputs, "eventTiming": native_entries, "longTasks": tasks,
                  "boundaries": boundaries, "environmentChanges": raw["environmentChanges"], "lifecycle": raw["lifecycle"],
                  "drains": raw["drains"], "errors": raw["errors"]}
    raw_arrays.update({f"overhead.{category}": items for category, items in raw["overhead"].items()})
    for name, items in raw_arrays.items():
        buffer = raw["buffers"].get(name)
        if items:
            check(buffer is not None, f"nonempty {name} lacks a buffer denominator")
        if buffer is not None:
            check(buffer["attempted"] == len(items) + buffer["dropped"], f"buffer attempted/recorded/dropped differs for {name}")
            check(0 <= buffer["dropped"] and 0 <= len(items) <= buffer["limit"], f"invalid buffer counts for {name}")
    for category, items in raw["overhead"].items():
        for item in items:
            check(finite(item.get("at")) and finite(item.get("endAt")) and finite(item.get("durationMs")), f"invalid direct overhead clock in {category}")
            check(near(item["durationMs"], item["endAt"] - item["at"], .5), f"direct overhead duration differs in {category}")
            check(item["durationMs"] >= 0, f"negative direct overhead in {category}")
    if mode == "raf-only":
        check(not inputs and not native_entries and not tasks, "raf-only unexpectedly captured native/performance events")
        check(raw["supported"].get("nativeInputsObserved") is False and raw["supported"].get("eventTimingObserved") is False and raw["supported"].get("longTasksObserved") is False, "raf-only support flags claim native observation")
        check(not raw["overhead"]["inputs"] and not raw["overhead"]["performance"], "raf-only reports input/performance callbacks")
    else:
        check(raw["supported"].get("nativeInputsObserved") is True, "full mode lacks native input scope flag")
    if complete:
        for type_name, enabled in [("event", raw["supported"]["eventTimingObserved"]), ("longtask", raw["supported"]["longTasksObserved"])]:
            if enabled:
                for origin in ["capture-fixed-drain", "final-fixed-drain"]:
                    check(sum(item["type"] == type_name and item["origin"] == origin for item in raw["drains"]) == 1, f"complete {type_name} lacks exactly one {origin}")
    for drain in raw["drains"]:
        entries = native_entries if drain["type"] == "event" else tasks
        check(drain["entryCount"] == sum(item["origin"] == drain["origin"] for item in entries), f"drain raw-entry count differs for {drain['type']}/{drain['origin']}")
        check(drain["endedAt"] >= drain["beganAt"], "negative drain duration")

    measured = [item for item in inputs if item["trusted"] and item["target"]["inMeasuredSurface"] and phase_at(item["eventAt"], deadlines) == "capture"]
    candidates = [item for item in measured if item["type"] in DISCRETE]
    relevant = [(index, item) for index, item in enumerate(native_entries) if phase_at(item["startAt"], deadlines) == "capture" and item["target"]["inMeasuredSurface"]]
    # Contract is a bipartite candidate graph, recomputed entirely from raw fields.
    edges: list[tuple[int, int]] = []
    for candidate_index, candidate in enumerate(candidates):
        for relevant_index, (_, entry) in enumerate(relevant):
            if entry["name"] == candidate["type"] and entry["target"]["token"] is not None and entry["target"]["token"] == candidate["target"]["token"] and abs(entry["startAt"] - candidate["eventAt"]) <= 2:
                edges.append((candidate_index, relevant_index))
    candidate_degrees, entry_degrees = Counter(c for c, _ in edges), Counter(e for _, e in edges)
    independently_matched = []
    for candidate_index, candidate in enumerate(candidates):
        selected = [entry_index for c, entry_index in edges if c == candidate_index]
        unique = candidate_degrees[candidate_index] == 1 and entry_degrees[selected[0]] == 1
        entry = relevant[selected[0]][1] if unique else None
        valid = bool(entry and finite(entry.get("durationMs")) and entry["durationMs"] >= 0 and finite(entry.get("processingStart")) and finite(entry.get("processingEnd")) and entry["processingStart"] >= entry["startAt"] and entry["processingEnd"] >= entry["processingStart"])
        independently_matched.append({"inputId": candidate["id"], "candidateEntryIndexes": selected,
            "status": "missing" if not selected else "ambiguous" if not unique else "invalid-entry" if not valid else "matched",
            "entryIndex": selected[0] if unique else None, "durationMs": entry["durationMs"] if valid else None,
            "interactionId": entry["interactionId"] if valid else None})
    ids = lambda items: sorted({item["interactionId"] for item in items if finite(item.get("interactionId")) and item["interactionId"] > 0})
    last_input_at = max((item["eventAt"] for item in measured), default=None)
    # JavaScript Boolean-string keys are explicit here; no trusted-entry filtering is hidden.
    boolean = lambda value: "true" if value else "false"
    recomputed_denominators = {
        "nativeMeasurementEnabled": mode == "full", "allRawInputs": len(inputs),
        "rawByType": counts(inputs, lambda item: item["type"]), "rawByEventPhase": counts(inputs, lambda item: phase_at(item["eventAt"], deadlines)),
        "rawByDeliveryPhase": counts(inputs, lambda item: phase_at(item["capturedAt"], deadlines)),
        "rawByTrusted": counts(inputs, lambda item: boolean(item["trusted"])), "rawByMeasuredSurface": counts(inputs, lambda item: boolean(item["target"]["inMeasuredSurface"])),
        "trustedMeasuredInputsInCapture": len(measured) if mode == "full" else None,
        "discreteCandidatesInCapture": len(candidates) if mode == "full" else None,
        "matches": independently_matched, "candidateMatchCounts": counts(independently_matched, lambda item: item["status"]) if mode == "full" else None,
        "allEventTimingEntries": len(native_entries), "eventTimingByDeliveryPhase": counts(native_entries, lambda item: phase_at(item["observedAt"], deadlines)),
        "eventTimingByStartPhase": counts(native_entries, lambda item: phase_at(item["startAt"], deadlines)),
        "eventTimingByMeasuredSurface": counts(native_entries, lambda item: boolean(item["target"]["inMeasuredSurface"])),
        "eventTimingMeasuredCaptureEntries": len(relevant), "measuredCaptureEntryRawIndexes": [index for index, _ in relevant],
        "unmatchedMeasuredCaptureEntryIndexes": [index for index in range(len(relevant)) if not any(match["status"] == "matched" and match["entryIndex"] == index for match in independently_matched)],
        "allObservedPositiveInteractionIds": ids(native_entries),
        "matchedSubsetPositiveInteractionIds": ids([match for match in independently_matched if match["status"] == "matched"]),
        "allLongTasks": len(tasks), "longTasksByStartPhase": counts(tasks, lambda item: phase_at(item["startAt"], deadlines)),
        "lastMeasuredNativeInputAt": last_input_at, "postInputSettleBeforePlannedCaptureEndMs": None if last_input_at is None else deadlines["captureEnd"] - last_input_at,
        "allBufferAttempted": sum(buffer["attempted"] for buffer in raw["buffers"].values()),
        "allBufferDropped": sum(buffer["dropped"] for buffer in raw["buffers"].values()), "errors": len(raw["errors"]),
    }
    check(raw["denominators"] == recomputed_denominators, "reported denominators/matching differ from independent raw recomputation")

    pointer_starts: dict[Any, dict] = {}
    independent_gestures: list[dict] = []
    orphan_releases: list[str] = []
    for item in measured:
        if item["type"] == "pointerdown":
            if item["pointerId"] in pointer_starts:
                prior = pointer_starts[item["pointerId"]]
                independent_gestures.append({"downId": prior["id"], "terminalId": None, "pointerId": item["pointerId"], "status": "replaced-unclosed", "nativeDurationMs": None})
            pointer_starts[item["pointerId"]] = item
        elif item["type"] in {"pointerup", "pointercancel"}:
            prior = pointer_starts.pop(item["pointerId"], None)
            if prior is None:
                orphan_releases.append(item["id"])
            else:
                independent_gestures.append({"downId": prior["id"], "terminalId": item["id"], "pointerId": item["pointerId"],
                    "status": "cancelled" if item["type"] == "pointercancel" else "released", "nativeDurationMs": item["eventAt"] - prior["eventAt"]})
    for pointer_id, prior in pointer_starts.items():
        independent_gestures.append({"downId": prior["id"], "terminalId": None, "pointerId": pointer_id, "status": "unclosed-at-capture-end", "nativeDurationMs": None})
    normalized_reported = [{"downId": gesture.get("downId", gesture.get("down", {}).get("id")),
                            "terminalId": gesture.get("terminalId"), "pointerId": gesture.get("pointerId", gesture.get("down", {}).get("pointerId")),
                            "status": gesture["status"], "nativeDurationMs": gesture["nativeDurationMs"]} for gesture in raw["gestures"]["gestures"]]
    check(normalized_reported == independent_gestures and raw["gestures"]["orphanReleaseIds"] == orphan_releases, "reported native gesture bounds differ from independent same-pointer pairing")
    check(all(gesture["nativeDurationMs"] is None or gesture["nativeDurationMs"] >= 0 for gesture in independent_gestures), "negative native gesture duration")
    records = [raw["environment"]["flags"], *raw["environmentChanges"], raw["endEnvironment"]["flags"]]
    integrity = raw["integrity"]
    independent_integrity = {
        "anyHiddenRecord": any(item["visibility"] != "visible" or item["topVisibility"] != "visible" for item in records),
        "anyClippedSurfaceRecord": any(not item["coverage"]["fullyInsideTopViewport"] for item in records),
        "lifecycleFreezeOrPagehide": any(item["eventType"] in {"freeze", "pagehide"} for item in raw["lifecycle"]),
        "anyTopFocusFalseRecord": any(not item["topFocused"] for item in records),
        "lastInputCompletedByDeadline": last_input_at <= deadlines["inputDeadline"] if mode == "full" and last_input_at is not None else None,
        "atLeastTenSecondsPostInputSettle": deadlines["captureEnd"] - last_input_at >= 10000 if mode == "full" and last_input_at is not None else None,
        "trustedInputDuringDrain": any(item["trusted"] and phase_at(item["eventAt"], deadlines) == "drain" for item in inputs),
        "unclosedGestures": sum("unclosed" in item["status"] for item in independent_gestures),
        "operationHasMeasuredInput": bool(measured) if mode == "full" else None,
        "expectedIdleHasMeasuredInput": bool(measured) if mode == "full" and raw["operation"] == "idle" else None,
        "timerBoundaries": [item for item in boundaries if item["plannedAt"] is not None],
        "fixedWindowCompleted": complete, "continuousForegroundExternallyCertified": False, "presentedResponseCertified": False,
    }
    for name, expected in independent_integrity.items():
        check(integrity.get(name) == expected, f"integrity flag differs from raw evidence: {name}")
    for name in ["anyHiddenRecord", "anyClippedSurfaceRecord", "lifecycleFreezeOrPagehide", "anyTopFocusFalseRecord", "trustedInputDuringDrain"]:
        if independent_integrity[name]:
            warnings.append(f"retained environmental confound: {name}")
    if not complete:
        warnings.append("retained incomplete/cancelled attempt; not a completed fixed window")
    if mode == "full" and raw["operation"] != "idle" and not measured:
        warnings.append("declared operation has no measured trusted native input")
    if mode == "full" and last_input_at is not None and last_input_at > deadlines["inputDeadline"]:
        warnings.append("last native input is late; predetermined ten-second settle was not achieved")
    if any(item["status"] != "matched" for item in independently_matched):
        warnings.append("missing/ambiguous/invalid native entries retained as unknown; no zero imputation")
    if recomputed_denominators["allBufferDropped"]:
        warnings.append("raw buffers dropped records; all denominators may be incomplete")
    if raw["errors"]:
        warnings.append("browser observer errors retained")

    context = raw["context"]
    check(context.get("humanParticipants") == 0 and context.get("presentedPerformanceCertified") is False, "context certification/human flags differ")
    baseline_by_path = {item["path"]: item for item in baseline["inputBindingsBefore"]} if baseline else {}
    for item in context["helperSources"]:
        if baseline:
            check(item["path"] in baseline_by_path and item == baseline_by_path.get(item["path"]), f"helper context differs from pre-trial immutable baseline: {item['path']}")
    asset_url_evidence = []
    for snapshot_name in ["bindingBefore", "bindingAfter"]:
        snapshot = raw[snapshot_name]
        if snapshot is None:
            check(not complete, f"complete window lacks {snapshot_name}")
            continue
        if raw["surfaceKind"] == "studio":
            check(snapshot["visibleNodeCount"] == len(snapshot["visibleNodes"]), f"public visible membership denominator differs in {snapshot_name}")
            available = {Path(item["path"]).name: item for item in context["productionAssets"]}
            for url in [*snapshot["scriptUrls"], *snapshot["stylesheetUrls"]]:
                basename = url.split("/")[-1].split("?")[0]
                check(basename in available, f"loaded Studio asset URL lacks actual context binding: {url}")
                asset_url_evidence.append({"snapshot": snapshot_name, "url": url, "binding": available.get(basename)})

    capture_frames = [item for item in frames if phase_at(item["timestamp"], deadlines) == "capture" and phase_at(item["observedAt"], deadlines) == "capture"]
    timestamp_intervals = [b["timestamp"] - a["timestamp"] for a, b in zip(capture_frames, capture_frames[1:])]
    observed_intervals = [b["observedAt"] - a["observedAt"] for a, b in zip(capture_frames, capture_frames[1:])]
    matches = [item for item in independently_matched if item["status"] == "matched"]
    interaction_durations: dict[Any, float] = defaultdict(float)
    for item in matches:
        if item["interactionId"] > 0:
            interaction_durations[item["interactionId"]] = max(interaction_durations[item["interactionId"]], item["durationMs"])
    observed_interaction_durations: dict[Any, float] = defaultdict(float)
    for _, entry in relevant:
        if entry["interactionId"] > 0 and finite(entry.get("durationMs")):
            observed_interaction_durations[entry["interactionId"]] = max(observed_interaction_durations[entry["interactionId"]], entry["durationMs"])
    before_snapshot = raw.get("bindingBefore") or {}
    classification = {"surface": raw["surfaceKind"], "mode": mode, "operation": raw["operation"],
                      "renderedNodeCount": before_snapshot.get("visibleNodeCount") if raw["surfaceKind"] == "studio" else 0,
                      "viewport": raw["environment"]["flags"]["coverage"]["rect"],
                      "timeOrigin": raw["environment"]["timeOrigin"], "userAgent": raw["environment"]["userAgent"]}
    return {
        "protocol": "archcanvas-performance-controls-independent-raw-audit/1", "rawLabel": raw.get("label"),
        "validRawAccounting": not errors, "errors": errors, "warnings": warnings, "classification": classification,
        "scope": "Independently reconstructed raw accounting, callback cadence, native gesture bounds and discrete EventTiming subsets; no actual presentation/INP/human certification.",
        "fixedWindowCompleted": complete, "recomputedDenominators": recomputed_denominators,
        "recomputedGestures": {"gestures": independent_gestures, "orphanReleaseIds": orphan_releases},
        "recomputedIntegrity": independent_integrity, "loadedAssetBindings": asset_url_evidence,
        "frameCadence": {"scope": "timestamps AND delivery in predetermined capture interval",
                         "allRawFrameRecords": len(frames), "includedFrameRecords": len(capture_frames),
                         "timestampIntervalsMs": distribution(timestamp_intervals), "observedIntervalsMs": distribution(observed_intervals),
                         "callbackTimestampAgeMs": distribution([item["observedAt"] - item["timestamp"] for item in capture_frames]),
                         "timestampCallbackCadencePerSecond": (len(capture_frames) - 1) * 1000 / sum(timestamp_intervals) if timestamp_intervals and sum(timestamp_intervals) > 0 else None,
                         "notPresentedFps": True},
        "nativeGestureDurationsMs": distribution([item["nativeDurationMs"] for item in independent_gestures if item["status"] == "released"]),
        "nativeEventTiming": {"matchedDiscreteEntryDurationsMs": distribution([item["durationMs"] for item in matches]),
                              "matchedSubsetInteractionMaximaMs": [{"interactionId": key, "durationMs": value} for key, value in sorted(interaction_durations.items())],
                              "matchedSubsetInteractionDistributionMs": distribution(list(interaction_durations.values())),
                              "allObservedMeasuredCaptureInteractionMaximaMs": [{"interactionId": key, "durationMs": value} for key, value in sorted(observed_interaction_durations.items())],
                              "allObservedMeasuredCaptureInteractionDistributionMs": distribution(list(observed_interaction_durations.values())),
                              "allPageInpCertified": False},
        "longTaskDurationsMs": {"allObserved": distribution([item["durationMs"] for item in tasks]),
                               "captureStarted": distribution([item["durationMs"] for item in tasks if phase_at(item["startAt"], deadlines) == "capture"])},
        "directSelfCostsMs": {category: distribution([item["durationMs"] for item in items]) for category, items in raw["overhead"].items()},
        "directSelfCostCategoriesOverlap": True, "presentedPerformanceCertified": False,
        "overallInpCertified": False, "humanParticipants": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, action="append", required=True, help="repeat to retain every actual receipt")
    parser.add_argument("--output-dir", type=Path, required=True, help="must not already exist")
    parser.add_argument("--baseline", type=Path, default=HERE / "helper-baseline-attempt-1/manifest.json")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    raw_paths = [path.resolve() for path in args.raw]
    baseline_path = args.baseline.resolve()
    input_paths = [Path(__file__).resolve(), baseline_path, *raw_paths]
    before = [binding(path) for path in input_paths]
    for index, path in enumerate(input_paths):
        (output_dir / "inputs").mkdir(exist_ok=True)
        with (output_dir / "inputs" / f"{index:02d}-{path.name}").open("xb") as stream:
            stream.write(path.read_bytes())
    baseline = json.loads(baseline_path.read_text())
    results = []
    for index, path in enumerate(raw_paths):
        try:
            raw = json.loads(path.read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Nonstandard JSON number {value}")))
            result = inspect_receipt(raw, baseline)
        except Exception as error:
            result = {"protocol": "archcanvas-performance-controls-independent-raw-audit/1",
                      "validRawAccounting": False, "errors": [f"raw parse/schema exception: {type(error).__name__}: {error}"],
                      "warnings": [], "presentedPerformanceCertified": False, "overallInpCertified": False, "humanParticipants": 0}
        result["rawBinding"] = binding(path)
        with (output_dir / f"raw-{index + 1:02d}-audit.json").open("x") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        results.append(result)
    condition_groups: dict[str, list] = defaultdict(list)
    for index, result in enumerate(results):
        if "classification" in result:
            condition = result["classification"]
            rect = condition["viewport"]
            key = f"{condition['surface']}:{condition['mode']}:{condition['operation']}:{condition['renderedNodeCount']}nodes:{rect['width']}x{rect['height']}"
            condition_groups[key].append({"rawIndex": index + 1, "rawLabel": result.get("rawLabel"),
                                          "validRawAccounting": result["validRawAccounting"], "fixedWindowCompleted": result["fixedWindowCompleted"],
                                          "warnings": result["warnings"], "callbackCadencePerSecond": result["frameCadence"]["timestampCallbackCadencePerSecond"]})
    after = [binding(path) for path in input_paths]
    receipt = {"protocol": "archcanvas-performance-controls-analysis-attempt/1", "createdUtc": datetime.now(timezone.utc).isoformat(),
               "inputBindingsBefore": before, "inputBindingsAfter": after, "inputsUnchanged": before == after,
               "allAttemptsRetained": len(results), "validAccountingAttempts": sum(result["validRawAccounting"] for result in results),
               "conditionGroups": dict(condition_groups), "comparisons": "All groups are shown; no control subtraction, fastest-sample selection, confound erasure or inherited product certification.",
               "serviceLaunched": False, "browserOperated": False, "modelsExecuted": False, "productTestsOrBuildRun": False,
               "presentedPerformanceCertified": False, "overallInpCertified": False, "humanParticipants": 0,
               "exitCode": 0 if before == after and all(result["validRawAccounting"] for result in results) else 2}
    with (output_dir / "receipt.json").open("x") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(output_dir), "attempts": len(results), "validAccounting": receipt["validAccountingAttempts"],
                      "inputsUnchanged": before == after, "exitCode": receipt["exitCode"]}))
    raise SystemExit(receipt["exitCode"])


if __name__ == "__main__":
    main()
