#!/usr/bin/env python3
"""Independent aggregate audit. No product, observer or validator imports.

Raw sessions and initial stress audit remain intact. Run from any directory.
Only this script's two aggregate output files are written. Input bytes are
bound before and after to reject changes during the audit.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
NS = "{http://www.w3.org/2000/svg}"
SESSIONS = ["stress300", "mlp-pilot", "mlp-correct-target"]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def equal(actual, expected, message):
    require(actual == expected, message)


def close(actual, expected, message, tolerance=.001):
    require(math.isfinite(actual) and math.isfinite(expected) and abs(actual - expected) < tolerance, message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def binding(path):
    body = path.read_bytes()
    return {"path": str(path.relative_to(PROJECT)), "bytes": len(body), "sha256": digest(body)}


def percentile(values):
    return sorted(values)[math.ceil(len(values) * .95) - 1] if values else None


def summary(values):
    return {"samples": len(values), "p95Ms": percentile(values), "maxMs": max(values) if values else None}


def cadence(frames):
    intervals = [b["at"] - a["at"] for a, b in zip(frames, frames[1:])]
    require(all(i >= 0 for i in intervals), "ordered frames")
    return {"frames": len(frames), "intervalP95Ms": percentile(intervals),
        "maxIntervalMs": max(intervals) if intervals else None,
        "fps": (len(frames) - 1) * 1000 / (frames[-1]["at"] - frames[0]["at"])
        if len(frames) > 1 and frames[-1]["at"] > frames[0]["at"] else None}


def normalized_svg(markup):
    text, attribute_count = re.subn(r'\bdata-revision="[0-9]+"', 'data-revision="0"', markup)
    text, metadata_count = re.subn(r'"revision":[0-9]+', '"revision":0', text)
    equal((attribute_count, metadata_count), (1, 1), "normalize exactly two actual revision scalars")
    return text


def parsed_svg(markup):
    svg = ET.fromstring(markup)
    metadata = json.loads(svg.find(NS + "metadata").text)
    groups = {node.attrib["data-node-id"]: node for node in svg.iter() if "data-canonical-id" in node.attrib}
    bodies = {id: {key: float(body.attrib[key]) for key in ["x", "y", "width", "height"]}
        for id, node in groups.items()
        for body in [next(child for child in node if child.tag == NS + "rect" and "stroke-width" in child.attrib)]}
    return svg, metadata, groups, bodies


def visual_signature(geometry):
    return json.dumps([geometry["camera"]["matrix"],
        [[key, obj["canvas"] if obj else None, obj["screen"] if obj else None,
          obj.get("label") if obj else None] for key, obj in geometry["objects"].items()]], separators=(",", ":"))


raw_sessions = {name: json.loads((HERE / (name + "-raw.json")).read_bytes()) for name in SESSIONS}
validation_sessions = {name: json.loads((HERE / (name + "-validation.json")).read_bytes()) for name in SESSIONS}
input_paths = [Path(__file__)]
for name, raw in raw_sessions.items():
    input_paths += [HERE / (name + "-raw.json"), HERE / (name + "-validation.json")]
    input_paths += [PROJECT / item["path"] for kind in ["productionAssets", "probeSources"] for item in raw["context"][kind]]
input_paths += [HERE / name for name in ["audit_stress300.py", "stress300-independent-audit.json", "stress300-independent-audit.md",
    "service-raw.txt", "service-sandbox-failed.txt", "stress300-transfer-truncated.txt", "aggregate-audit-first-failure.txt"]]
saved_chains = {}
for model in ["stress300", "mlp"]:
    envelope_paths = sorted(HERE.glob(model + "-store-*.json"))
    equal(len(envelope_paths), 1, model + " explicit single envelope")
    envelope = json.loads(envelope_paths[0].read_bytes())
    saved_chains[model] = {"envelopePath": envelope_paths[0], "envelope": envelope}
    current_store = PROJECT / ".archcanvas/m4-current-native-diagnostic/documents" / (envelope["document"]["id"] + ".json")
    saved_chains[model]["currentStorePath"] = current_store
    input_paths += [envelope_paths[0], current_store]
    input_paths += [HERE / (model + "-" + suffix) for suffix in ["saved-browser.svg", "reopened-browser.svg", "saved.jpg", "reopened.jpg", "save-dom.json", "reopen-dom.json"]]
    input_paths += [PROJECT / "fixtures" / ("stress_300" if model == "stress300" else "mlp") / source["path"]
                    for source in envelope["document"]["architecture"]["sources"]]
input_paths = sorted(set(input_paths))
before = [binding(path) for path in input_paths]
initial_stress_bindings = [binding(HERE / name) for name in ["audit_stress300.py", "stress300-independent-audit.json", "stress300-independent-audit.md"]]


def check_geometry(geometry, full=False):
    if geometry is None:
        return None
    require(isinstance(geometry["revision"], int), "integer revision")
    for obj in geometry["objects"].values():
        if obj is None:
            continue
        canvas, screen, matrix = obj["canvas"], obj["screen"], obj["screenMatrix"]
        corners = [(canvas["x"], canvas["y"]), (canvas["x"] + canvas["width"], canvas["y"]),
            (canvas["x"], canvas["y"] + canvas["height"]), (canvas["x"] + canvas["width"], canvas["y"] + canvas["height"])]
        points = [(matrix["a"] * x + matrix["c"] * y + matrix["e"],
                   matrix["b"] * x + matrix["d"] * y + matrix["f"]) for x, y in corners]
        expected = {"x": min(p[0] for p in points), "y": min(p[1] for p in points),
            "width": max(p[0] for p in points) - min(p[0] for p in points),
            "height": max(p[1] for p in points) - min(p[1] for p in points)}
        for key, value in expected.items():
            close(value, screen[key], "recorded screen transform " + key)
        viewport = geometry["viewport"]
        intersects = screen["x"] + screen["width"] > viewport["x"] and screen["x"] < viewport["x"] + viewport["width"] and \
            screen["y"] + screen["height"] > viewport["y"] and screen["y"] < viewport["y"] + viewport["height"]
        equal(intersects, obj["intersectsViewport"], "viewport intersection")
    if not full:
        return None
    svg, metadata, groups, bodies = parsed_svg(geometry["svgMarkup"])
    equal(sorted(groups), geometry["visibleIds"], "full actual SVG frontier")
    equal(sorted(item["sceneNodeId"] for item in metadata["renderedNodes"]), geometry["visibleIds"], "metadata drawn frontier")
    equal(int(svg.attrib["data-revision"]), geometry["revision"], "SVG revision")
    equal(metadata["revision"], geometry["revision"], "metadata revision")
    for key in ["documentId", "sourceDigest", "irDigest"]:
        equal(metadata[key], geometry[key], "metadata source binding " + key)
    equal(geometry["pinnedIds"], [], "zero observed pins")
    for id, obj in geometry["objects"].items():
        if obj is None:
            require(id not in groups, "absence represented accurately")
            continue
        equal(groups[id].attrib["data-canonical-id"], obj["canonicalId"], "actual canonical id")
        equal(groups[id].attrib["aria-label"], obj["label"], "actual label")
        equal(bodies[id], obj["canvas"], "XML body and DOM canvas facts")
    return {"revision": geometry["revision"], "visibleNodes": len(groups), "sceneEdges": len(metadata["renderedBindings"]),
        "svgSha256": digest(geometry["svgMarkup"].encode()), "svgBytes": len(geometry["svgMarkup"].encode()),
        "normalizedSvgSha256": digest(normalized_svg(geometry["svgMarkup"]).encode())}


def native_matching(raw):
    eligible = [event for event in raw["events"] if event["trusted"] and event["type"] in
                ["pointerdown", "pointerup", "click", "keydown", "keyup"] and event["target"]["token"]]
    by_input, by_entry = {}, {}
    for event in eligible:
        candidates = [index for index, native in enumerate(raw["eventTiming"])
            if native["interactionId"] > 0 and native["name"] == event["type"] and native["targetToken"] == event["target"]["token"]
            and abs(native["startAt"] - event["eventAt"]) <= 8]
        by_input[event["id"]] = candidates
        for index in candidates:
            by_entry.setdefault(index, []).append(event["id"])
    matches = []
    interactions = {}
    for event in eligible:
        if not event["trialId"]:
            continue
        candidates = by_input[event["id"]]
        index = candidates[0] if len(candidates) == 1 and len(by_entry[candidates[0]]) == 1 else None
        native = raw["eventTiming"][index] if index is not None else None
        match = {"inputId": event["id"], "trialId": event["trialId"], "nativeEntryIndex": index,
            "nativeDurationMs": native["durationMs"] if native else None, "interactionId": native["interactionId"] if native else None,
            "inputCandidateCount": len(candidates), "candidateEntryInputCounts": [{"nativeEntryIndex": i, "inputs": len(by_entry[i])} for i in candidates],
            "missingReason": None if native else "ambiguous" if candidates else "unavailable-below-threshold-detached-or-truncated"}
        matches.append(match)
        if native:
            interactions[native["interactionId"]] = max(native["durationMs"], interactions.get(native["interactionId"], 0))
    return {"eligibleDiscreteInputs": len(matches), "matchedDiscreteInputs": sum(m["nativeEntryIndex"] is not None for m in matches),
        "matchedInteractions": len(interactions), "matchedInteractionP95Ms": percentile(list(interactions.values())),
        "interactionDurationsMs": interactions, "matches": matches,
        "missingInputIds": [m["inputId"] for m in matches if m["nativeEntryIndex"] is None],
        "missingRemainNull": True, "scope": "Unique discrete matching subset, independent denominators per raw session"}


def window(raw, trial, down, up, assigned=True):
    events = [e for e in raw["events"] if e["pointerId"] == down["pointerId"] and down["eventAt"] <= e["eventAt"] <= up["eventAt"]]
    moves = [e for e in events if e["type"] == "pointermove" and e["trusted"]]
    equal(len(moves), 8, "eight actual moves in gesture window")
    timed_frames = [f for f in raw["frames"] if down["eventAt"] <= f["at"] <= up["eventAt"]]
    observed_frames = [f for f in raw["frames"] if down["capturedAt"] <= f["observedAt"] <= up["capturedAt"]]
    if assigned:
        require(all(f["trialId"] == trial["id"] and f["geometry"] for f in timed_frames + observed_frames), "actual assigned gesture frame coverage")
        previous = visual_signature(trial["before"])
        changed = []
        for frame in observed_frames:
            signature = visual_signature(frame["geometry"])
            if signature != previous:
                changed.append(frame)
            previous = signature
    else:
        require(all(f["trialId"] is None and f["geometry"] is None for f in timed_frames + observed_frames), "unassigned pilot has no requested geometry coverage")
        changed = None
    duration = up["eventAt"] - down["eventAt"]
    return {"operation": trial["spec"]["operation"], "trialId": trial["id"], "assignedToRequestedTrial": assigned,
        "actualDownTargetId": down["target"]["nodeId"], "downInputId": down["id"], "upInputId": up["id"],
        "downToUpEventWindowMs": duration, "trustedMoves": len(moves), "downEventAt": down["eventAt"], "upEventAt": up["eventAt"],
        "eventTimestampBoundedCallbacks": {**cadence(timed_frames), "callbackTimes": [f["at"] for f in timed_frames],
            "callbacksPerEventWindowSecond": len(timed_frames) * 1000 / duration},
        "observedTimestampBoundedCallbacks": {**cadence(observed_frames),
            "geometryChangeCount": len(changed) if changed is not None else None,
            "geometryChangeObservedAt": [f["observedAt"] for f in changed] if changed is not None else None},
        "eventToCaptureMs": summary([e["capturedAt"] - e["eventAt"] for e in moves]),
        "nativeLatencyForUnassignedInputsCertified": False,
        "presentedFpsCertified": False, "continuousCausalInputToPaintCertified": False}


session_results = []
for name, raw in raw_sessions.items():
    validation = validation_sessions[name]
    equal(raw["schemaVersion"], 2, name + " schema")
    equal(raw["protocol"], "archcanvas-input-observation/2", name + " protocol")
    equal(raw["measurement"]["continuousInput"], "observed-geometry-proxy-not-paint", name + " proxy scope")
    equal(raw["measurement"]["frames"], "raf-callback-cadence-not-presented-frames", name + " frame scope")
    equal(raw["measurement"]["coordinateSpace"], "window-client-css-pixels", name + " coordinate contract")
    equal(raw["harness"]["humanParticipants"], 0, name + " no participants")
    equal(raw["harness"]["productInputsDispatched"], False, name + " no harness dispatch")
    equal(raw["harness"]["productHiddenStateRead"], False, name + " no hidden state")
    equal(raw["environment"]["viewport"], {"width": 1280, "height": 720, "devicePixelRatio": 1}, name + " actual iframe viewport")
    equal(raw["environment"]["scripts"], ["http://127.0.0.1:8888/assets/index-DPwoyNJW.js"], name + " observed current script")
    equal(raw["environment"]["isIframe"], True, name + " actual iframe")
    equal(raw["errors"], [], name + " raw errors")
    context_checks = []
    for kind in ["productionAssets", "probeSources"]:
        for expected in raw["context"][kind]:
            actual = binding(PROJECT / expected["path"])
            equal(actual, expected, name + " disk context exact")
            context_checks.append({**actual, "kind": kind, "matches": True})
    equal(len(context_checks), 9, name + " nine file context")
    for path, accounting in raw["buffers"].items():
        equal(accounting["dropped"], 0, name + " no dropped buffer " + path)
        values = raw
        for key in path.split("."):
            values = values[key]
        require(len(values) <= accounting["limit"], name + " bounds " + path)
    clock_events = [e["eventAt"] for e in raw["events"]]
    require(clock_events == sorted(clock_events), name + " ordered actual input timestamps")
    require(all(raw["startedAt"] <= e["capturedAt"] <= raw["stoppedAt"] and e["eventAt"] <= e["capturedAt"] + 8 for e in raw["events"]), name + " input clock/window")
    require(all(raw["startedAt"] <= f["observedAt"] <= raw["stoppedAt"] for f in raw["frames"]), name + " frame clock/window")
    snapshots = [("bindingAtStart", raw["bindingAtStart"])]
    snapshots += [(trial["id"] + "." + side, trial[side]) for trial in raw["trials"] for side in ["before", "after"] if trial[side] is not None]
    snapshot_results = []
    for snapshot_name, geometry in snapshots:
        for key in ["documentId", "sourceDigest", "irDigest"]:
            equal(geometry[key], raw["bindingAtStart"][key], name + " consistent source/IR binding")
        snapshot_results.append({"snapshot": snapshot_name, **check_geometry(geometry, True)})
    for frame in raw["frames"]:
        check_geometry(frame["geometry"])
    latency = native_matching(raw)
    equal(latency["matches"], validation["latency"]["matches"], name + " independent matching graph")
    for key in ["eligibleDiscreteInputs", "matchedDiscreteInputs", "matchedInteractions", "matchedInteractionP95Ms"]:
        equal(latency[key], validation["latency"][key], name + " native summary " + key)
    equal(cadence(raw["frames"]), validation["frameCadence"], name + " independent callback cadence")
    trial_results = []
    windows = []
    for index, trial in enumerate(raw["trials"]):
        actual_report = validation["trials"][index]
        events = [e for e in raw["events"] if e["trialId"] == trial["id"]]
        expected = {"trialId": trial["id"], "operation": trial["spec"]["operation"], "status": trial["status"],
            "sourceBindingValid": True, "pinCount": len(trial["spec"]["pinnedIds"])}
        equal(expected["pinCount"], 0, "no pins measured")
        if trial["status"] == "no-input":
            equal(trial["before"], None, "no input means no requested before snapshot")
            equal(events, [], "no trial-assigned input for missed target")
            require(not any(f["trialId"] == trial["id"] for f in raw["frames"]), "no requested-trial frame binding")
            outside = [e for e in raw["events"] if trial["armedAt"] <= e["capturedAt"] <= trial["finishedAt"] and e["trusted"]]
            down = next(e for e in outside if e["type"] == "pointerdown")
            up = next(e for e in outside if e["type"] == "pointerup" and e["pointerId"] == down["pointerId"])
            equal(down["target"]["nodeId"], "call:instance:model.MLP.network.3", "pilot actually hit Linear4")
            require(down["target"]["nodeId"] not in trial["spec"]["targetIds"], "pilot does not count wrong node as target")
            expected.update(observed=False, operationSucceeded=False, outsideInputCount=len(outside),
                actualOutsideTargetId=down["target"]["nodeId"], requestedBeforeGeometry=None)
            equal(expected["outsideInputCount"], actual_report["outsideRequestedTrialInputCount"], "pilot outside inputs independently counted")
            windows.append(window(raw, trial, down, up, False))
        else:
            equal(events[0]["id"], trial["firstEventId"], "trial first actual input")
            equal(events[-1]["id"], trial["lastEventId"], "trial last actual input")
            require(all(e["trusted"] for e in events), "actual browser input trusted")
            revision_delta = trial["after"]["revision"] - trial["before"]["revision"]
            canvas_deltas = {id: {key: trial["after"]["objects"][id]["canvas"][key] - trial["before"]["objects"][id]["canvas"][key]
                for key in ["x", "y", "width", "height"]} for id in trial["spec"]["targetIds"] + trial["spec"]["anchorIds"]}
            shape_changed = visual_signature(trial["before"]) != visual_signature(trial["after"])
            down = next((e for e in events if e["type"] == "pointerdown"), None)
            up = next((e for e in events if e["type"] == "pointerup" and e["pointerId"] == down["pointerId"]), None) if down else None
            active = [e for e in events if down and down["eventAt"] <= e["eventAt"] < up["eventAt"]] if up else []
            cancelled = any(e["type"] in ["blur", "pointercancel", "lostpointercapture"] or e["type"] == "keydown" and e.get("key") == "Escape" for e in active)
            equal(cancelled, False, "no active canceled gesture sample")
            operation = trial["spec"]["operation"]
            if operation == "pan":
                equal(down["target"]["canvasTool"], "pan", "pan actual tool")
                equal(down["target"]["handToolPressed"], True, "pan actual pressed hand")
                equal(trial["before"]["svgMarkup"], trial["after"]["svgMarkup"], "pan full SVG exact")
                for key in ["visibleIds", "expandedIds", "pinnedIds", "selectionMarkup", "revision"]:
                    equal(trial["before"][key], trial["after"][key], "pan public " + key)
                camera = {**trial["before"]["camera"]["matrix"]}
                delta = {axis: (up[axis] - up["viewport"][axis]) - (down[axis] - down["viewport"][axis]) for axis in ["x", "y"]}
                camera["e"] += delta["x"]
                camera["f"] += delta["y"]
                for key, value in camera.items():
                    close(value, trial["after"]["camera"]["matrix"][key], "pan true terminal camera")
                require(all(all(value == 0 for value in d.values()) for d in canvas_deltas.values()), "pan unchanged canvas geometry")
                succeeded = revision_delta == 0
                expected.update(panTerminalInputDeltaCssPx=delta, publicSvgContinuityExact=True)
                windows.append(window(raw, trial, down, up))
            elif operation == "drag":
                equal(down["target"]["canvasTool"], "select", "correct drag select tool")
                require(down["target"]["nodeId"] in trial["spec"]["targetIds"], "correct actual drag target")
                succeeded = revision_delta == 1 and any(d["x"] or d["y"] for id, d in canvas_deltas.items() if id in trial["spec"]["targetIds"])
                windows.append(window(raw, trial, down, up))
            elif operation == "toggle":
                require(down["target"]["nodeId"] in trial["spec"]["targetIds"], "toggle actual target")
                succeeded = revision_delta == 1 and trial["before"]["expandedIds"] != trial["after"]["expandedIds"]
            else:
                equal(down["target"]["action"], operation, "actual history button")
                succeeded = revision_delta == 1 and shape_changed
            expected.update(observed=True, operationSucceeded=bool(succeeded), revisionDelta=revision_delta,
                selectedCanvasDeltas=canvas_deltas, selectedShapeChanged=shape_changed, cancelled=False,
                fullSvgChangedExceptRevision=normalized_svg(trial["before"]["svgMarkup"]) != normalized_svg(trial["after"]["svgMarkup"]))
        equal(expected["observed"], actual_report["observed"], name + " trial observed result")
        equal(expected["operationSucceeded"], actual_report["operationSucceeded"], name + " requested trial outcome")
        trial_results.append(expected)
    frame_rects = [g["frameRect"] for _, g in snapshots] + [f["geometry"]["frameRect"] for f in raw["frames"] if f["geometry"]]
    unique_frame_rects = sorted({json.dumps(r, sort_keys=True) for r in frame_rects})
    session_results.append({"name": name, "raw": binding(HERE / (name + "-raw.json")),
        "separateValidator": binding(HERE / (name + "-validation.json")), "contextDiskBindings": context_checks,
        "counts": {key: len(raw[key]) for key in ["trials", "events", "frames", "eventTiming", "longTasks", "visibility", "errors"]},
        "snapshotChecks": snapshot_results, "latency": latency, "requestedTrials": trial_results, "gestureWindows": windows,
        "wholeSessionCallbackCadence": cadence(raw["frames"]), "wholeSessionWindowMs": raw["stoppedAt"] - raw["startedAt"],
        "wholeSessionCallbacksPerStartStopSecond": len(raw["frames"]) * 1000 / (raw["stoppedAt"] - raw["startedAt"]),
        "visibility": {"observedStates": sorted({v["state"] for v in raw["visibility"]}),
            "iframeFocusValues": sorted({v["hasFocus"] for v in raw["visibility"]}), "topFocusValues": sorted({v["topHasFocus"] for v in raw["visibility"]}),
            "continuousHostPresentationCertified": False}, "fonts": raw["environment"]["fonts"],
        "actualOuterIframeRectangles": [json.loads(r) for r in unique_frame_rects],
        "outerFrameRectChanged": len(unique_frame_rects) > 1,
        "coordinateScope": "Object screenMatrix/screen are iframe window-client CSS pixels; outer frameRect is separately recorded and never added into those coordinates."})

history_results = []
for name in ["stress300", "mlp-correct-target"]:
    raw = raw_sessions[name]
    drag = next(t for t in raw["trials"] if t["spec"]["operation"] == "drag")
    undo = next(t for t in raw["trials"] if t["spec"]["operation"] == "undo")
    redo = next(t for t in raw["trials"] if t["spec"]["operation"] == "redo")
    for pair_name, left, right in [("drag-after equals undo-before", drag["after"], undo["before"]),
        ("undo restores whole drag-before", drag["before"], undo["after"]),
        ("undo-after equals redo-before", undo["after"], redo["before"]),
        ("redo restores whole drag-after", drag["after"], redo["after"])]:
        equal(normalized_svg(left["svgMarkup"]), normalized_svg(right["svgMarkup"]), name + " full SVG history restoration")
        for key in ["objects", "camera", "expandedIds", "visibleIds", "pinnedIds"]:
            equal(left[key], right[key], name + " actual selected facts history " + key)
        history_results.append({"session": name, "pair": pair_name, "leftRevision": left["revision"], "rightRevision": right["revision"],
            "svgExactExceptTwoRevisionScalars": True, "selectedObjectFactsExact": True,
            "normalizedSvgSha256": digest(normalized_svg(left["svgMarkup"]).encode())})
    target = drag["spec"]["targetIds"][0]
    expected_delta = {"x": 40, "y": 24} if name == "stress300" else {"x": 52, "y": 36}
    for coordinate, delta in expected_delta.items():
        equal(drag["after"]["objects"][target]["canvas"][coordinate] - drag["before"]["objects"][target]["canvas"][coordinate], delta, name + " exact requested target delta")

pilot = raw_sessions["mlp-pilot"]["trials"]
pilot_before, pilot_moved, pilot_undo, pilot_redo = [t["after"] for t in pilot]
for left, right in [(pilot_before, pilot_undo), (pilot_moved, pilot_redo)]:
    equal(normalized_svg(left["svgMarkup"]), normalized_svg(right["svgMarkup"]), "pilot full SVG restores unintended move")
_, _, _, before_bodies = parsed_svg(pilot_before["svgMarkup"])
_, _, _, moved_bodies = parsed_svg(pilot_moved["svgMarkup"])
affected = [{"id": id, "before": body, "after": moved_bodies[id],
    "delta": {key: moved_bodies[id][key] - body[key] for key in body}}
    for id, body in before_bodies.items() if body != moved_bodies[id]]
equal([a["id"] for a in affected], ["call:instance:model.MLP", "call:instance:model.MLP.network", "call:instance:model.MLP.network.3"], "pilot actual moved node and two growing ancestors")
equal([a["delta"] for a in affected], [{"x": 0, "y": 0, "width": 52, "height": 0},
    {"x": 0, "y": 0, "width": 52, "height": 36}, {"x": 52, "y": 36, "width": 0, "height": 0}], "pilot actual body deltas")
pilot_result = {"requestedTarget": "call:instance:model.MLP.network.0", "actualInputTarget": "call:instance:model.MLP.network.3",
    "missedDragRequestedOutcome": "no-input; no requested before or active geometry samples",
    "fullSvgRevealsAffectedBody": affected, "wholeSvgUndoRedoRestoresUnintendedLinear4": True,
    "requestedLinear1UndoRedoSucceeded": False, "pilotDiscarded": False,
    "explanation": "The DOM observed an unintended Linear4 move plus two growing ancestor bodies. These inputs remain unassigned and cannot count toward requested Linear1 drag timing/geometry. Requested selected Linear1 facts do not change on pilot undo/redo; full SVG does restore all unintended move geometry."}

persistence = []
for model, chain in saved_chains.items():
    final_raw = raw_sessions["stress300" if model == "stress300" else "mlp-correct-target"]["trials"][-1]["after"]
    saved = (HERE / (model + "-saved-browser.svg")).read_bytes()
    reopened = (HERE / (model + "-reopened-browser.svg")).read_bytes()
    equal(saved, reopened, model + " real saved/reopened SVG bytes")
    equal(saved, final_raw["svgMarkup"].encode(), model + " actual raw final to saved SVG")
    equal(chain["envelopePath"].read_bytes(), chain["currentStorePath"].read_bytes(), model + " current authoritative envelope exact copy")
    document = chain["envelope"]["document"]
    equal(document["revision"], final_raw["revision"], model + " saved visual revision")
    equal(document["id"], final_raw["documentId"], model + " saved document identity")
    equal(document["pinnedObjects"], [], model + " no hidden saved pins")
    equal(sorted(document["expandedIds"]), sorted(final_raw["expandedIds"]), model + " saved expansion flags")
    architecture = document["architecture"]
    for key in ["sourceDigest", "irDigest"]:
        equal(architecture[key], final_raw[key], model + " saved architecture " + key)
    for source in architecture["sources"]:
        equal(digest(source["content"].encode()), source["digest"], model + " included source digest")
        source_path = PROJECT / "fixtures" / ("stress_300" if model == "stress300" else "mlp") / source["path"]
        equal(digest(source_path.read_bytes()), source["digest"], model + " formal fixture source exact")
    svg, metadata, _, _ = parsed_svg(saved.decode())
    equal(metadata["revision"], document["revision"], model + " saved DOM same document revision")
    save_dom = json.loads((HERE / (model + "-save-dom.json")).read_bytes())
    reopen_dom = json.loads((HERE / (model + "-reopen-dom.json")).read_bytes())
    require("已保存" in save_dom["header"] and "已保存" in reopen_dom["header"], model + " actual saved header")
    require("画布已保存" in save_dom["footer"] and "已重开保存的画布" in reopen_dom["footer"], model + " actual saved/reopened footer")
    require("rev " + str(document["revision"]) in save_dom["footer"] and "rev " + str(document["revision"]) in reopen_dom["footer"], model + " actual footer revisions")
    for dom in [save_dom, reopen_dom]:
        if "svgLength" in dom:
            equal(dom["svgLength"], len(saved.decode()), model + " actual measured SVG length")
    persistence.append({"model": model, "documentId": document["id"], "visualRevision": document["revision"],
        "storageRevision": chain["envelope"]["revision"], "savedToReopenedSvgByteExact": True,
        "finalRawToSavedSvgByteExact": True, "envelopeCopyToCurrentStoreByteExact": True,
        "svgSha256": digest(saved), "envelope": binding(chain["envelopePath"]), "currentStore": binding(chain["currentStorePath"]),
        "saveDom": save_dom, "reopenDom": reopen_dom,
        "cameraPersistenceCertified": False, "undoHistoryPersistenceCertified": False,
        "publicationReadabilityCertified": False})

after = [binding(path) for path in input_paths]
equal(before, after, "all scoped inputs unchanged during aggregate audit")
equal(initial_stress_bindings, [binding(HERE / name) for name in ["audit_stress300.py", "stress300-independent-audit.json", "stress300-independent-audit.md"]], "initial stress audit bytes preserved")
result = {"schema": "archcanvas-current-native-aggregate-independent-audit/1", "status": "passed-with-retained-pilot-and-explicit-limits",
    "script": binding(Path(__file__)), "scopedInputsBefore": before, "scopedInputsAfter": after,
    "allScopedInputsUnchanged": True, "initialStressAuditUnmodified": initial_stress_bindings,
    "sessions": session_results, "wholeSvgHistoryRestoration": history_results, "retainedPilot": pilot_result,
    "persistence": persistence, "sessionLatencyDenominatorsMerged": False,
    "pinProtectionMeasured": False, "humanParticipants": 0, "performanceGateCertified": False,
    "limits": ["Three sessions retain separate native latency and frame denominators. The failed requested-target pilot is preserved.",
        "rAF callbacks, observed geometry and complete buffers do not certify presented FPS or causal continuous input-to-paint.",
        "Unassigned Linear4 pilot gesture lacks before/active requested geometry; its geometry-change count and native requested latency remain null.",
        "Actual trusted automation drag windows last about eight seconds; not normal human task duration or researcher performance.",
        "All documents observed visible, with iframe focus true/false; outer scrolling moves iframe y between -8 and 144, and continuous host presentation is unverified.",
        "No pinned objects; pin protection not measured.",
        "Fonts report loaded with zero loadedFaces; resolved fonts/hardware lock remain unverified.",
        "Actual current disk asset/probe bytes bind three raw contexts; no independently captured HTTP response-body proof.",
        "Save/reopen SVG and current envelope copies are byte exact; camera and undo history persistence are not certified.",
        "Initial sandbox service-launch failure and raw-transfer truncation bytes are retained; failed attempts are not counted as successful measurements.",
        "The first aggregate audit failed on an overly narrow only-one-body-change assertion; its tool-response transcription is retained, and corrected audit records all three actual pilot body changes.",
        "Tool public-DOM read failures and AX large-frame limits are outside an exhaustive raw tool-response inventory; absent UI evidence remains unknown.",
        "Screenshots are bound bytes but this script does not inspect pixels or certify physical-size publication readability.",
        "Native active-gesture cancellation, sustained presented performance, human publication review and researcher tasks remain open."]}
output = HERE / "aggregate-current-audit.json"
output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
lines = ["# 当前构建三会话独立审计", "", "状态：passed-with-retained-pilot-and-explicit-limits。M4 性能、人审与真人任务均未认证。", "",
    "复现：`python3 docs/evidence/m4-current-native-diagnostic/audit_current_native.py`。脚本不导入产品、observer、validator；独立计算与单列validator结果比对。初版stress300脚本/JSON/MD原字节保持。", "",
    f"{len(input_paths)} 个scoped输入在审计前后hash完全一致；三份raw的各生产3/probe6绑定均与实际磁盘一致。两模型正式source内容/fixture和保存source/IR一致。", "",
    "| 会话 | 请求试次结果 | Eligible / matched / interactions | matched子集p95 |", "| --- | --- | ---: | ---: |"]
for session in session_results:
    latency = session["latency"]
    outcomes = ", ".join(t["operation"] + ":" + str(t["operationSucceeded"]).lower() for t in session["requestedTrials"])
    lines.append(f"| {session['name']} | {outcomes} | {latency['eligibleDiscreteInputs']} / {latency['matchedDiscreteInputs']} / {latency['matchedInteractions']} | {latency['matchedInteractionP95Ms']} ms |")
lines += ["", "三个分母不合并；未匹配输入仍null。Pilot drag请求Linear1，实际命中Linear4，记录为no-input、没有请求before/active geometry；该次实际Linear4+52/+36保留。随后undo/redo对请求Linear1无变化，false；完整SVG证明其恢复的是意外Linear4移动，不计请求成功。", "",
    "| 会话/手势 | down→up实际窗口 | moves | event窗口回调 | 最大间隔 | observed窗口几何变化 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
for session in session_results:
    for gesture in session["gestureWindows"]:
        frame = gesture["eventTimestampBoundedCallbacks"]
        changed = gesture["observedTimestampBoundedCallbacks"]["geometryChangeCount"]
        lines.append(f"| {session['name']}/{gesture['operation']} | {gesture['downToUpEventWindowMs']:.1f} ms | {gesture['trustedMoves']} | {frame['frames']} | {frame['maxIntervalMs']:.1f} ms | {'null（未绑定请求）' if changed is None else changed} |")
lines += ["", "此表按实际event down/up去掉外页准备等待；几何另按observedAt窗口。回调与DOM变化不认证呈现FPS。", "",
    "Stress300目标+40/+24，MLP corrected目标+52/+36；两链全SVG除attribute/metadata两个revision标量外逐字undo/redo恢复。两模型保存→真实重开SVG和finalraw完全相同，封存envelope→当前隔离store原字节相同（visual rev4/8，storage rev1/1）。这些结果不认证相机或undo历史持久化。", "",
    "iframe实际1280×720/DPR1；文档观测visible，iframe focus true/false，top focus true。三个会话外页frameRect均有y−8↔144滚动，iframe-client对象screen坐标与outer页面坐标不混用；不证明固定连续宿主呈现。无pins/真人，解析font/hardware未知。", "",
    "Pilot意外Linear4移动还使root body宽+52、network body宽+52/高+36；完整恢复核对包括这些祖先变化。首跑审计的过窄‘仅一个body变化’断言失败记录保留，不计成功。", "",
    "服务启动sandbox失败、首raw transfer截断和初版stress审计原bytes均保留。工具DOM读取失败与AX frame限制缺完整工具日志范围，不据缺失判0；脚本绑定截图bytes但不声称像素或物理尺寸审看。", "",
    "详细结果：[aggregate-current-audit.json](aggregate-current-audit.json)。"]
(HERE / "aggregate-current-audit.md").write_text("\n".join(lines) + "\n")
print(json.dumps({"status": result["status"], "scopedInputs": len(input_paths), "allScopedInputsUnchanged": True,
    "sessions": [{"name": s["name"], "latency": {key: s["latency"][key] for key in ["eligibleDiscreteInputs", "matchedDiscreteInputs", "matchedInteractions", "matchedInteractionP95Ms"]},
        "requestedOutcomes": [t["operationSucceeded"] for t in s["requestedTrials"]]} for s in session_results],
    "persistence": [{"model": p["model"], "visualRevision": p["visualRevision"], "savedToReopenedSvgByteExact": True, "envelopeCopyToCurrentStoreByteExact": True} for p in persistence]}, ensure_ascii=False, indent=2))
