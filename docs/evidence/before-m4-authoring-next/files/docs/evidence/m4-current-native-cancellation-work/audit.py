"""Bounded, independent offline audit of one real CUA atomic-drag attempt.

This imports no Studio/observer/validator implementation. It does not issue input,
start a service, execute a model, or infer a missing key event.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def binding(path: pathlib.Path) -> dict:
    raw = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def p95(values):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[(len(ordered) * 95 + 99) // 100 - 1]


def audit() -> dict:
    raw = json.loads((HERE / "atomic-drag-escape-raw.json").read_text())
    validator = json.loads((HERE / "validator.stdout.json").read_text())
    after = json.loads((HERE / "after-dom.json").read_text())
    prep = json.loads((HERE / "preparation.json").read_text())
    assert raw["schemaVersion"] == 2 and len(raw["trials"]) == 1
    trial = raw["trials"][0]
    inputs = [event for event in raw["events"] if event["trialId"] == trial["id"]]
    downs = [event for event in inputs if event["trusted"] and event["type"] == "pointerdown"]
    assert len(downs) == 1
    down = downs[0]
    ups = [event for event in inputs if event["trusted"] and event["type"] == "pointerup" and event["pointerId"] == down["pointerId"]]
    assert len(ups) == 1
    up = ups[0]
    assert down["eventAt"] < up["eventAt"]
    active_inputs = [event for event in inputs if down["eventAt"] <= event["eventAt"] <= up["eventAt"]]
    moves = [event for event in active_inputs if event["trusted"] and event["type"] == "pointermove" and event["pointerId"] == down["pointerId"] and event["buttons"] == 1]
    escapes = [event for event in raw["events"] if event["trusted"] and event["type"] == "keydown" and event["key"] == "Escape"]
    active_escapes = [event for event in escapes if down["eventAt"] < event["eventAt"] < up["eventAt"]]
    # Same-timestamp lostcapture follows the normal up in array order here.
    interruptions = [event for event in raw["events"] if event["trusted"] and down["eventAt"] < event["eventAt"] < up["eventAt"] and (
        event["type"] in ("blur", "pointercancel") or event["type"] == "lostpointercapture" and event["pointerId"] == down["pointerId"])]
    assert not escapes and not active_escapes and not interruptions
    target = trial["spec"]["targetIds"][0]
    before_body = trial["before"]["objects"][target]["canvas"]
    after_body = trial["after"]["objects"][target]["canvas"]
    active_frames = [frame for frame in raw["frames"] if down["capturedAt"] <= frame["observedAt"] <= up["capturedAt"] and frame["trialId"] == trial["id"]]
    preview_frames = [frame for frame in active_frames if frame["geometry"]["objects"][target]["canvas"] != before_body]
    assert len(moves) == 8 and preview_frames
    assert trial["after"]["revision"] == trial["before"]["revision"] + 1
    assert after["svg"] == trial["after"]["svgMarkup"]
    assert after_body["x"] - before_body["x"] == 100
    assert after_body["y"] - before_body["y"] == 60
    for anchor in trial["spec"]["anchorIds"]:
        assert trial["before"]["objects"][anchor]["canvas"] == trial["after"]["objects"][anchor]["canvas"]
    declared = raw["context"]["productionAssets"] + raw["context"]["probeSources"]
    current = []
    for entry in declared:
        now = binding(ROOT / entry["path"])
        assert now == entry
        current.append(now)
    for entry in prep["bindings"]:
        assert binding(ROOT / entry["path"]) == entry
    discrete = {"pointerdown", "pointerup", "click", "keydown", "keyup"}
    eligible = [event for event in raw["events"] if event["trusted"] and event["type"] in discrete and event["target"]["token"]]
    candidates = []
    for event in eligible:
        candidates.append([index for index, native in enumerate(raw["eventTiming"]) if native["interactionId"] > 0 and native["name"] == event["type"] and native["targetToken"] == event["target"]["token"] and abs(native["startAt"] - event["eventAt"]) <= 8])
    uses = {}
    for indexes in candidates:
        for index in indexes:
            uses[index] = uses.get(index, 0) + 1
    matched = [(event, indexes[0]) for event, indexes in zip(eligible, candidates) if len(indexes) == 1 and uses[indexes[0]] == 1]
    interactions = {}
    for _, index in matched:
        native = raw["eventTiming"][index]
        interactions[native["interactionId"]] = max(interactions.get(native["interactionId"], 0), native["durationMs"])
    assert len(eligible) == 2 and len(matched) == 1 and len(interactions) == 1
    assert validator["latency"]["matchedInteractionP95Ms"] == p95(list(interactions.values())) == 24
    times = [frame["at"] for frame in raw["frames"]]
    intervals = [b - a for a, b in zip(times, times[1:])]
    active_times = [frame["at"] for frame in active_frames]
    active_intervals = [b - a for a, b in zip(active_times, active_times[1:])]
    assert all(not value["dropped"] for value in raw["buffers"].values()) and not raw["errors"]
    return {
        "schema": "archcanvas-independent-atomic-drag-cancellation-audit/1",
        "auditedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "inputs": [binding(HERE / name) for name in ["atomic-drag-escape-raw.json", "validator.stdout.json", "after-dom.json", "preparation.json", "cua-operation-attempt.json", "environment-end.json"]],
        "status": "real-drag-verified-active-cancellation-not-observed",
        "productBuildAndProbeBindingsMatchCurrent": True,
        "nativeSequence": {"pointerId": down["pointerId"], "downEventAt": down["eventAt"], "upEventAt": up["eventAt"], "downToUpMs": up["eventAt"] - down["eventAt"], "trustedActiveMoves": len(moves), "trustedProductEscapeEvents": len(escapes), "activeTrustedEscapes": len(active_escapes), "activeInterruptions": len(interruptions), "activeGeometryFrames": len(active_frames), "activePreviewGeometryFrames": len(preview_frames)},
        "committedDOM": {"revisionBefore": trial["before"]["revision"], "revisionAfter": trial["after"]["revision"], "target": target, "deltaCanvas": {"x": 100, "y": 60}, "anchorCanvasUnchanged": True, "finalSvgMatchesIndependentDOM": True, "savedDocumentChecked": False, "historyChecked": False},
        "discreteEventTiming": {"eligibleInputs": len(eligible), "uniqueMatchedInputs": len(matched), "matchedInteractions": len(interactions), "matchedSubsetP95Ms": 24, "missingPointerdown": True, "wholeInteractionMaxCertified": False, "overallInpCertified": False, "nativePointerdownWithNullTargetDurationMs": [event["durationMs"] for event in raw["eventTiming"] if event["name"] == "pointerdown" and event["targetToken"] is None]},
        "rafCallbackCadence": {"sessionFrames": len(times), "sessionMs": raw["stoppedAt"] - raw["startedAt"], "sessionIntervalP95Ms": p95(intervals), "sessionIntervalHz": (len(times) - 1) * 1000 / (times[-1] - times[0]), "activeFrames": len(active_times), "activeIntervalP95Ms": p95(active_intervals), "activeIntervalHz": (len(active_times) - 1) * 1000 / (active_times[-1] - active_times[0]), "presentedFpsCertified": False},
        "environment": raw["environment"], "visibility": raw["visibility"],
        "humanCertified": False, "activeCancellationCertified": False,
        "limitations": ["This is one AI-operated MLP atomic drag in a new iframe session; it is not DenseStress300, a human task, representative p95 or complete performance acceptance.", "Escape API completion supplied no trusted product Escape event; cancellation and rollback remain unverified.", "A trusted native pointerdown exists with targetToken null; it cannot be borrowed into the uniquely matched 24ms pointerup subset.", "Approximately 60Hz rAF callbacks establish this session's callback scheduling only; browser visibility was reported false and presented frames remain unobserved.", "Fonts loaded with an empty loadedFaces list do not bind resolved font files; hardware remains unverified.", "Old slower sessions are preserved without replacement; this nonrandom new session establishes neither a change cause nor a product performance improvement."]
    }


if __name__ == "__main__":
    result = audit()
    (HERE / "independent-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "nativeSequence": result["nativeSequence"], "rafCallbackCadence": result["rafCallbackCadence"]}, indent=2))
