#!/usr/bin/env python3
"""Audit the frozen two-trial native receipt without importing product/probe code.

Parses exactly the bytes hashed as inputs. Recomputes DOM facts and native
matching independently, and compares a fresh offline validator with its saved
output. Never rewrites the raw receipt or drives a browser.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
NS = "{http://www.w3.org/2000/svg}"
FROZEN: dict[Path, bytes] = {}


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def exact(left, right, message):
    check(left == right, message)


def close(left, right, message, tolerance=1e-3):
    check(math.isfinite(left) and math.isfinite(right) and abs(left - right) < tolerance, message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def freeze(path):
    path = path.resolve()
    if path not in FROZEN:
        FROZEN[path] = path.read_bytes()
    return FROZEN[path]


def parsed(path):
    return json.loads(freeze(path))


def binding(path, body=None):
    path = path.resolve()
    value = freeze(path) if body is None else body
    return {"path": str(path.relative_to(PROJECT)), "bytes": len(value), "sha256": sha(value)}


def p95(values):
    return sorted(values)[math.ceil(len(values) * .95) - 1] if values else None


def cadence(frames):
    times = [frame["at"] for frame in frames]
    intervals = [right - left for left, right in zip(times, times[1:])]
    check(all(value >= 0 for value in intervals), "callback timestamps ordered")
    return {"frames": len(frames), "intervalP95Ms": p95(intervals),
            "maxIntervalMs": max(intervals) if intervals else None,
            "fps": (len(times) - 1) * 1000 / (times[-1] - times[0])
            if len(times) > 1 and times[-1] > times[0] else None}


def visual_signature(geometry):
    return [geometry["camera"]["matrix"], [[key, value["canvas"] if value else None,
        value["screen"] if value else None, value.get("label") if value else None]
        for key, value in geometry["objects"].items()]]


def semantic_digest(value):
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())


raw_path = HERE / "native-stress300-raw.json"
validation_path = HERE / "native-stress300-validation.json"
validator_path = PROJECT / "scripts/validate_input_observation.mjs"
raw = parsed(raw_path)
reported = parsed(validation_path)
build = parsed(HERE / "build-context.json")
probe_binding = parsed(HERE / "react-probe-dist/source-bindings.json")
fixture = parsed(HERE / "react-probe-dist/fixture.json")
envelope_path = PROJECT / probe_binding["fixture"]["path"]
envelope = parsed(envelope_path)
freeze(Path(__file__))
freeze(validator_path)
freeze(PROJECT / "src/archcanvas_python/frontend.py")
freeze(HERE / "native-stress300-validation-stderr.txt")
tool_observations = parsed(HERE / "tool-observations.json")

context_checks = []
for kind in ["productionAssets", "probeSources"]:
    for declared in raw["context"][kind]:
        actual = binding(PROJECT / declared["path"])
        exact(actual, declared, "frozen context bytes: " + declared["path"])
        context_checks.append({**actual, "kind": kind})
exact(len(context_checks), 9, "three production and six probe inputs")
for declared in build["bindings"]:
    exact(binding(PROJECT / declared["path"]), declared, "build-context disk binding")
exact([value for value in build["bindings"] if value["path"].startswith("studio/dist/")],
      raw["context"]["productionAssets"], "build-context and raw assets exact")
exact(binding(envelope_path), {key: probe_binding["fixture"][key] for key in ["path", "bytes", "sha256"]},
      "source-bound fixture original envelope")
exact(fixture, envelope, "probe fixture and original envelope exact parsed fields")
architecture = envelope["document"]["architecture"]
exact(architecture["entry"], "model:DenseStress300", "formal source entry")
exact(len(architecture["nodes"]), 304, "304 canonical nodes")
exact(len(architecture["edges"]), 304, "304 canonical edges")
nodes = {node["id"]: node for node in architecture["nodes"]}
exact(len(nodes), 304, "unique canonical ids")
network = nodes["call:instance:model.DenseStress300.network"]
exact(network["kind"], "Module", "source-recovered generic module kind")
exact(network["category"], "container", "source-recovered network container")
exact(network["repeat"], {"count": 300, "sharing": "independent"}, "independent source instances")
exact(len(network["children"]), 300, "300 recovered children")
exact([nodes[id]["kind"] for id in network["children"]], [kind for _ in range(150) for kind in ["Linear", "ReLU"]],
      "alternating independently recovered layers")
source_checks = []
for source in architecture["sources"]:
    source_path = PROJECT / "fixtures/stress_300" / source["path"]
    exact(sha(source["content"].encode()), source["digest"], "included source raw digest")
    exact(sha(freeze(source_path)), source["digest"], "formal fixture current bytes")
    tree = ast.parse(freeze(source_path))
    sequential = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                  and node.func.value.id == "nn" and node.func.attr == "Sequential"]
    exact(len(sequential), 1, "one authored Sequential")
    exact([call.func.attr for call in sequential[0].args if isinstance(call, ast.Call)],
          [kind for _ in range(150) for kind in ["Linear", "ReLU"]], "300 explicit source declarations")
    source_checks.append(binding(source_path))
exact(semantic_digest([{key: value for key, value in source.items() if key != "content"}
                       for source in architecture["sources"]]), architecture["sourceDigest"], "source aggregate digest")
semantic_nodes = []
for node in architecture["nodes"]:
    item = {key: value for key, value in node.items() if key not in ["source", "parameterOrigins"]}
    if "parameterOrigins" in node:
        item["parameterOrigins"] = {name: {key: origin[key] for key in ["kind", "expression", "path"]}
                                    for name, origin in node["parameterOrigins"].items()}
    semantic_nodes.append(item)
exact(semantic_digest({"entry": architecture["entry"], "nodes": semantic_nodes, "edges": architecture["edges"]}),
      architecture["irDigest"], "declared semantic IR digest independently recomputed")
calls = {}
for node in architecture["nodes"]:
    if node.get("instanceId") and node.get("callId"):
        calls.setdefault(node["instanceId"], set()).add(node["callId"])
source_facts = []
for node in architecture["nodes"]:
    fact = {"id": node["id"], "sourceLabel": node["label"], "kind": node["kind"],
            "category": node["category"], "evidence": node["evidence"]}
    if node.get("instanceId"):
        fact.update(instanceId=node["instanceId"], callCount=len(calls.get(node["instanceId"], set())))
    for key in ["callId", "repeat", "outputPath", "source"]:
        if key in node:
            fact[key] = node[key]
    source_facts.append(fact)

exact(raw["schemaVersion"], 2, "native schema v2")
exact(raw["protocol"], "archcanvas-input-observation/2", "native protocol v2")
exact(raw["measurement"]["runtimeAccess"], "DOM-only", "public DOM scope")
exact(raw["measurement"]["continuousInput"], "observed-geometry-proxy-not-paint", "continuous proxy scope")
exact(raw["measurement"]["frames"], "raf-callback-cadence-not-presented-frames", "callback scope")
exact(raw["measurement"]["coordinateSpace"], "window-client-css-pixels", "input coordinate scope")
exact(raw["harness"]["humanParticipants"], 0, "automation is not a researcher")
exact(raw["harness"]["productInputsDispatched"], False, "harness dispatch declaration")
exact(raw["harness"]["productHiddenStateRead"], False, "hidden-state declaration")
exact(raw["environment"]["viewport"], {"width": 1280, "height": 720, "devicePixelRatio": 1}, "actual iframe viewport")
exact(raw["environment"]["scripts"], ["http://127.0.0.1:8889/assets/index-oI5sT67U.js"], "actual new script URL")
exact(raw["errors"], [], "no recorded observer errors")
for name, accounting in raw["buffers"].items():
    exact(accounting["dropped"], 0, name + " no dropped buffer values")
    values = raw
    for part in name.split("."):
        values = values[part]
    check(len(values) <= accounting["limit"], name + " bounded input")

snapshot_checks = []
geometries = [("start", raw["bindingAtStart"])] + [(trial["id"] + "." + side, trial[side])
             for trial in raw["trials"] for side in ["before", "after"]]
for name, geometry in geometries:
    for key in ["sourceDigest", "irDigest"]:
        exact(geometry[key], architecture[key], name + " canonical binding")
    exact(geometry["documentId"], envelope["document"]["id"], name + " source-bound document id")
    exact(geometry["pinnedIds"], [], name + " no pins")
    svg = ET.fromstring(geometry["svgMarkup"])
    metadata = json.loads(svg.find(NS + "metadata").text)
    exact(int(svg.attrib["data-revision"]), geometry["revision"], name + " SVG revision")
    exact(metadata["revision"], geometry["revision"], name + " metadata revision")
    for key in ["sourceDigest", "irDigest", "documentId"]:
        exact(metadata[key], geometry[key], name + " metadata binding")
    exact(metadata["sourceFacts"], source_facts, name + " full canonical source facts")
    groups = {element.attrib["data-node-id"]: element for element in svg.iter() if "data-canonical-id" in element.attrib}
    exact(sorted(groups), geometry["visibleIds"], name + " actual SVG frontier")
    exact(sorted(value["sceneNodeId"] for value in metadata["renderedNodes"]), geometry["visibleIds"], name + " metadata frontier")
    check(set(groups).issubset(nodes), name + " frontier canonical ids")
    for id, observed in geometry["objects"].items():
        if observed is None:
            check(id not in groups, name + " absent object")
            continue
        group = groups[id]
        exact(group.attrib["data-canonical-id"], observed["canonicalId"], name + " observed canonical id")
        exact(group.attrib["aria-label"], observed["label"], name + " observed label")
        body = next(child for child in group if child.tag == NS + "rect" and "stroke-width" in child.attrib)
        for coordinate in ["x", "y", "width", "height"]:
            exact(float(body.attrib[coordinate]), observed["canvas"][coordinate], name + " exact XML canvas " + coordinate)
    snapshot_checks.append({"snapshot": name, "revision": geometry["revision"], "visibleNodes": len(groups),
        "canonicalSourceFacts": len(metadata["sourceFacts"]), "sceneEdges": len(metadata["renderedBindings"]),
        "svgBytes": len(geometry["svgMarkup"].encode()), "svgSha256": sha(geometry["svgMarkup"].encode())})
for geometry in [value for _, value in geometries] + [frame["geometry"] for frame in raw["frames"] if frame["geometry"]]:
    for obj in geometry["objects"].values():
        if obj is None:
            continue
        body, matrix = obj["canvas"], obj["screenMatrix"]
        corners = [(body["x"], body["y"]), (body["x"] + body["width"], body["y"]),
                   (body["x"], body["y"] + body["height"]), (body["x"] + body["width"], body["y"] + body["height"])]
        points = [(matrix["a"] * x + matrix["c"] * y + matrix["e"],
                   matrix["b"] * x + matrix["d"] * y + matrix["f"]) for x, y in corners]
        expected = {"x": min(x for x, y in points), "y": min(y for x, y in points),
                    "width": max(x for x, y in points) - min(x for x, y in points),
                    "height": max(y for x, y in points) - min(y for x, y in points)}
        for key, value in expected.items():
            close(value, obj["screen"][key], "recorded screen transform")
        screen, viewport = obj["screen"], geometry["viewport"]
        intersects = screen["x"] + screen["width"] > viewport["x"] and screen["x"] < viewport["x"] + viewport["width"] and \
            screen["y"] + screen["height"] > viewport["y"] and screen["y"] < viewport["y"] + viewport["height"]
        exact(intersects, obj["intersectsViewport"], "observed screen intersection")

discrete = [event for event in raw["events"] if event["trusted"]
            and event["type"] in ["pointerdown", "pointerup", "click", "keydown", "keyup"] and event["target"]["token"]]
input_candidates, entry_candidates = {}, {}
for event in discrete:
    candidates = [index for index, entry in enumerate(raw["eventTiming"])
        if entry["interactionId"] > 0 and entry["name"] == event["type"]
        and entry["targetToken"] == event["target"]["token"] and abs(entry["startAt"] - event["eventAt"]) <= 8]
    input_candidates[event["id"]] = candidates
    for index in candidates:
        entry_candidates.setdefault(index, []).append(event["id"])
matches = []
for event in discrete:
    if not event["trialId"]:
        continue
    candidates = input_candidates[event["id"]]
    index = candidates[0] if len(candidates) == 1 and len(entry_candidates[candidates[0]]) == 1 else None
    entry = raw["eventTiming"][index] if index is not None else None
    matches.append({"inputId": event["id"], "trialId": event["trialId"], "nativeEntryIndex": index,
        "nativeDurationMs": entry["durationMs"] if entry else None, "interactionId": entry["interactionId"] if entry else None,
        "inputCandidateCount": len(candidates), "candidateEntryInputCounts": [
            {"nativeEntryIndex": index, "inputs": len(entry_candidates[index])} for index in candidates],
        "missingReason": None if entry else "ambiguous" if candidates else "unavailable-below-threshold-detached-or-truncated"})
exact(matches, reported["latency"]["matches"], "independent full matching graph")
durations = {}
for match in matches:
    if match["interactionId"] is not None:
        durations[match["interactionId"]] = max(match["nativeDurationMs"], durations.get(match["interactionId"], 0))
latency = {"eligibleDiscreteInputs": len(matches), "matchedDiscreteInputs": sum(value["nativeEntryIndex"] is not None for value in matches),
           "matchedInteractions": len(durations), "matchedInteractionP95Ms": p95(list(durations.values()))}
for key, value in latency.items():
    exact(value, reported["latency"][key], "independent native subset metric")
exact(latency, {"eligibleDiscreteInputs": 6, "matchedDiscreteInputs": 3, "matchedInteractions": 1,
                "matchedInteractionP95Ms": 2016}, "actual six/three/one matching scope")
exact(cadence(raw["frames"]), reported["frameCadence"], "whole callback cadence exact")
idle = [right["at"] - left["at"] for left, right in zip(raw["frames"], raw["frames"][1:])
        if left["trialId"] is None and right["trialId"] is None]
exact({"intervals": len(idle), "intervalP95Ms": p95(idle), "fps": len(idle) * 1000 / sum(idle) if idle and sum(idle) > 0 else None},
      reported["idleCadence"], "idle callback cadence exact")
for name, samples in raw["overhead"].items():
    exact({"samples": len(samples), "p95Ms": p95([sample["durationMs"] for sample in samples]),
        "maxMs": max(sample["durationMs"] for sample in samples) if samples else None},
        reported["observerSelfCost"][name], "independent observer cost")

exact([trial["spec"]["operation"] for trial in raw["trials"]], ["toggle", "pan"], "actual two operations")
toggle, pan = raw["trials"]
exact([len(toggle[side]["visibleIds"]) for side in ["before", "after"]], [4, 304], "actual toggle frontier")
exact(toggle["after"]["revision"] - toggle["before"]["revision"], 1, "toggle revision increment")
check(network["id"] not in toggle["before"]["expandedIds"] and network["id"] in toggle["after"]["expandedIds"], "toggle expands actual network")
exact(toggle["before"]["camera"], toggle["after"]["camera"], "toggle camera unchanged")
exact(toggle["after"]["svgMarkup"], pan["before"]["svgMarkup"], "actual expanded scene remains at pan start")
exact(pan["before"]["svgMarkup"], pan["after"]["svgMarkup"], "pan full SVG byte exact")
for key in ["revision", "visibleIds", "expandedIds", "pinnedIds", "selectionMarkup"]:
    exact(pan["before"][key], pan["after"][key], "pan public continuity " + key)
exact(pan["before"]["revision"], 1, "pan revision one")
target = pan["spec"]["targetIds"][0]
exact(target, network["children"][0], "pan observed Linear1")
exact(pan["before"]["objects"][target]["canvas"], pan["after"]["objects"][target]["canvas"], "pan canvas body unchanged")

gesture_windows = []
trial_checks = []
for trial, validation in zip(raw["trials"], reported["trials"]):
    events = [event for event in raw["events"] if event["trialId"] == trial["id"]]
    frames = [frame for frame in raw["frames"] if frame["trialId"] == trial["id"]]
    exact(events[0]["id"], trial["firstEventId"], "trial first event")
    exact(events[-1]["id"], trial["lastEventId"], "trial last event")
    exact(trial["status"], "finished", "trial settled finish")
    check(all(event["trusted"] for event in events), "all trial inputs trusted")
    down = next(event for event in events if event["type"] == "pointerdown")
    ups = [event for event in events if event["type"] == "pointerup" and event["pointerId"] == down["pointerId"]]
    exact(len(ups), 1, "one actual same-pointer up")
    up = ups[0]
    moves = [event for event in events if event["type"] == "pointermove" and event["pointerId"] == down["pointerId"]
             and down["eventAt"] <= event["eventAt"] <= up["eventAt"]]
    active = [event for event in events if down["eventAt"] <= event["eventAt"] < up["eventAt"]]
    cancelled = any(event["type"] in ["blur", "pointercancel", "lostpointercapture"]
                    or event["type"] == "keydown" and event["key"] == "Escape" for event in active)
    exact(cancelled, False, "no active cancellation experiment")
    event_frames = [frame for frame in frames if down["eventAt"] <= frame["at"] <= up["eventAt"]]
    observed_frames = [frame for frame in frames if down["capturedAt"] <= frame["observedAt"] <= up["capturedAt"]]
    previous = visual_signature(trial["before"])
    changed = []
    for frame in observed_frames:
        signature = visual_signature(frame["geometry"])
        if signature != previous:
            changed.append(frame)
        previous = signature
    entire_changes, previous = [], [trial["before"]["revision"], visual_signature(trial["before"])]
    for frame in frames:
        signature = [frame["geometry"]["revision"], visual_signature(frame["geometry"])]
        if signature != previous:
            entire_changes.append(frame)
        previous = signature
    proxies = []
    for event in moves:
        observed = next((frame for frame in entire_changes if frame["observedAt"] >= event["capturedAt"]), None)
        proxies.append({"inputId": event["id"], "observedAt": observed["observedAt"] if observed else None,
            "inputToObservedChangeProxyMs": observed["observedAt"] - event["eventAt"] if observed else None,
            "presentedPaintCertified": False, "causalInputIdentified": False})
    exact(proxies, validation["continuousProxies"], "independent continuous DOM proxy values")
    exact(cadence(frames), validation["frameCadence"], "full trial callback cadence exact")
    exact(len(events), validation["trustedInputs"], "trial trusted input count")
    exact(len(moves), validation["trustedPointerMoves"], "trial trusted move count")
    exact(cancelled, validation["cancelled"], "trial cancellation classifier")
    tasks = [task for task in raw["longTasks"] if task["at"] < trial["finishedAt"]
             and task["at"] + task["durationMs"] > trial["before"]["at"]]
    exact(len(tasks), validation["activeLongTasks"], "trial long task count")
    exact(max(task["durationMs"] for task in tasks) if tasks else None, validation["maxActiveLongTaskMs"], "trial long task maximum")
    if trial is toggle:
        exact(down["target"]["kind"], "toggle", "actual toggle control")
        exact(down["target"]["nodeId"], network["id"], "actual toggle target")
        exact(len(moves), 0, "discrete toggle without pointermoves")
        succeeded = len(events) > 0 and trial["after"]["revision"] - trial["before"]["revision"] == 1 \
            and network["id"] not in trial["before"]["expandedIds"] and network["id"] in trial["after"]["expandedIds"]
    else:
        exact(len(moves), 8, "eight trusted pan pointermoves")
        exact(down["target"]["kind"], "viewport", "actual pan began on viewport")
        exact(down["target"]["canvasTool"], "pan", "actual public pan mode")
        exact(down["target"]["handToolPressed"], True, "actual hand tool pressed")
        check(down["target"]["inCanvas"] and not down["target"]["editingTarget"] and not down["target"]["canvasControl"], "actual pan navigation trigger")
        exact(down["button"], 0, "left mouse pan")
        delta = {axis: (up[axis] - up["viewport"][axis]) - (down[axis] - down["viewport"][axis]) for axis in ["x", "y"]}
        exact(delta, {"x": 40, "y": 24}, "actual viewport-relative terminal pan")
        expected = {**trial["before"]["camera"]["matrix"]}
        expected["e"] += delta["x"]
        expected["f"] += delta["y"]
        exact(expected, trial["after"]["camera"]["matrix"], "actual terminal camera exact")
        for coordinate in ["x", "y"]:
            exact(trial["after"]["objects"][target]["screen"][coordinate] - trial["before"]["objects"][target]["screen"][coordinate],
                  delta[coordinate], "actual iframe-client screen delta")
        exact(validation["panTerminal"]["expectedCamera"], expected, "validator terminal expectation")
        exact(validation["panTerminal"]["actualCamera"], expected, "validator terminal observation")
        exact(validation["panTerminal"]["deltaCssPx"], delta, "validator terminal delta")
        exact(validation["publicDocumentContinuity"]["matched"], True, "validator public continuity")
        succeeded = not cancelled and trial["after"]["revision"] == trial["before"]["revision"] \
            and expected != trial["before"]["camera"]["matrix"] and expected == trial["after"]["camera"]["matrix"] \
            and trial["before"]["svgMarkup"] == trial["after"]["svgMarkup"]
    exact(succeeded, True, "independent requested operation succeeds")
    exact(succeeded, validation["operationSucceeded"], "separate validator success")
    duration = up["eventAt"] - down["eventAt"]
    gesture_windows.append({"trialId": trial["id"], "operation": trial["spec"]["operation"],
        "actualInputTargetKind": down["target"]["kind"], "actualInputTargetNodeId": down["target"]["nodeId"],
        "downInputId": down["id"], "upInputId": up["id"], "pointerId": down["pointerId"],
        "downEventAt": down["eventAt"], "upEventAt": up["eventAt"], "downToUpEventWindowMs": duration,
        "trustedMoves": len(moves), "eventTimestampBoundedCallbacks": {**cadence(event_frames),
            "callbackTimes": [frame["at"] for frame in event_frames], "callbacksPerEventWindowSecond": len(event_frames) * 1000 / duration},
        "observedTimestampBoundedCallbacks": {**cadence(observed_frames), "geometryChangeCount": len(changed),
            "changedObservedAt": [frame["observedAt"] for frame in changed]},
        "eventToCaptureMs": [event["capturedAt"] - event["eventAt"] for event in moves],
        "postTerminalEvents": [{"id": event["id"], "type": event["type"], "eventAt": event["eventAt"]}
            for event in events if event["eventAt"] >= up["eventAt"] and event["type"] in ["blur", "lostpointercapture"]],
        "presentedFramesCertified": False, "causalInputToPaintCertified": False})
    trial_checks.append({"id": trial["id"], "operation": trial["spec"]["operation"], "operationSucceeded": succeeded,
        "fullTrialCallbackCadence": cadence(frames), "activeLongTasks": tasks,
        "revisionBefore": trial["before"]["revision"], "revisionAfter": trial["after"]["revision"]})

fresh = subprocess.run(["node", str(validator_path), str(raw_path)], cwd=PROJECT, capture_output=True, timeout=30)
exact(fresh.returncode, 0, "fresh offline validator exits zero")
exact(json.loads(fresh.stdout), reported, "fresh validator complete parsed output exact")
exact(fresh.stderr, freeze(HERE / "native-stress300-validation-stderr.txt"), "fresh validator stderr exact")
before = [binding(path, body) for path, body in sorted(FROZEN.items())]
after = [binding(path, path.read_bytes()) for path in sorted(FROZEN)]
exact(before, after, "all scoped hashed-and-parsed bytes remain unchanged")
frames = raw["frames"]
frame_rects = [geometry["frameRect"] for _, geometry in geometries] + [frame["geometry"]["frameRect"] for frame in frames if frame["geometry"]]
rect_values = []
for rectangle in frame_rects:
    if rectangle not in rect_values:
        rect_values.append(rectangle)
result = {"schema": "archcanvas-hierarchy-native-independent-audit/1", "status": "passed-with-explicit-limits",
    "scope": "Frozen oI5 new-build two-trial stress300 same-origin iframe automation; independent static facts, public DOM and discrete matching; no browser control.",
    "script": binding(Path(__file__)), "raw": binding(raw_path), "separateValidator": binding(validation_path),
    "scopedInputsBefore": before, "scopedInputsAfter": after, "inputsAfter": after, "allScopedInputsUnchanged": True,
    "hashedBytesAreParsedBytes": True, "rawParsedBytes": len(FROZEN[raw_path.resolve()]), "contextDiskBindings": context_checks,
    "buildContextExact": True, "freshValidator": {"exitCode": fresh.returncode, "allParsedFieldsExact": True,
        "stdoutBytes": len(fresh.stdout), "stdoutSha256": sha(fresh.stdout), "stderrBytes": len(fresh.stderr),
        "stderrSha256": sha(fresh.stderr), "rawFileStillExactFrozenBytes": True},
    "sourceFacts": {"entry": architecture["entry"], "sourceDigest": architecture["sourceDigest"], "irDigest": architecture["irDigest"],
        "sourceFiles": source_checks, "canonicalNodes": 304, "canonicalEdges": 304, "explicitLayers": 300,
        "sourceAndSemanticIrDigestsIndependentlyRecomputed": True, "sourceFactsExactEveryFullSnapshot": True,
        "modelExecuted": False, "frontendReexecuted": False},
    "counts": {key: len(raw[key]) for key in ["trials", "events", "frames", "eventTiming", "longTasks", "visibility", "errors"]},
    "snapshots": snapshot_checks, "requestedTrials": trial_checks, "gestureWindows": gesture_windows,
    "panPublicContinuity": {"svgByteExact": True, "svgSha256": sha(pan["before"]["svgMarkup"].encode()),
        "revisionUnchanged": 1, "frontierPinsSelectionExact": True, "canvasBodyExact": True,
        "terminalDeltaCssPx": {"x": 40, "y": 24}, "hiddenCanvasOrHistoryCertified": False},
    "latency": {**latency, "matches": matches, "perInteractionDurationMs": durations,
        "missingInputIds": [value["inputId"] for value in matches if value["nativeEntryIndex"] is None],
        "missingValuesRemainNull": True, "scope": "Uniquely matched discrete subset only; pan inputs unmatched, no continuous latency/overall INP"},
    "wholeSessionCallbackCadence": cadence(frames), "wholeSessionWindowMs": raw["stoppedAt"] - raw["startedAt"],
    "wholeSessionCallbacksPerStartStopSecond": len(frames) * 1000 / (raw["stoppedAt"] - raw["startedAt"]),
    "callbackMetricNameNote": "fps field preserves validator arithmetic only: rAF callback cadence, not presented FPS.",
    "idleCallbackCadence": reported["idleCadence"], "visibility": {"observedStates": sorted({value["state"] for value in raw["visibility"]}),
        "iframeFocusValues": sorted({value["hasFocus"] for value in raw["visibility"]}),
        "topFocusValues": sorted({value["topHasFocus"] for value in raw["visibility"]}), "hostContinuousPresentationCertified": False},
    "coordinateEnvironment": {"iframeViewport": raw["environment"]["viewport"], "uniqueFrameRects": rect_values,
        "recordedObjectScreenCoordinateSpace": "iframe-window-client-css-pixels; frameRect separately records outer placement",
        "hostScreenContinuityCertified": False},
    "toolFailureRecord": {"binding": binding(HERE / "tool-observations.json"), "scope": tool_observations["scope"],
        "nativeRelatedFailures": [value for value in tool_observations["failures"] if "stress300" in value["action"] or "iframe" in value["action"]],
        "rawReadClaim": tool_observations["rawReads"]["native"], "originalFailedToolLogsCertified": False},
    "auditDevelopmentObservation": {"source": "auditing agent tool-response transcription, chunk 5b4a70",
        "failedAssertion": "source-recovered network", "cause": "Initial handwritten audit expected Sequential as kind; frozen formal IR records Module/category container with repeat300 independent.",
        "resolution": "Read actual canonical kind and source construction separately; replaced incorrect audit assumption. Original receipt unchanged.",
        "failedRunCountedAsSuccess": False, "originalRawFailureLogFileCaptured": False},
    "pinProtectionMeasured": False, "nativeActiveCancellationTested": False, "humanParticipants": 0,
    "performanceGateCertified": False, "screenshotsAudited": 0,
    "limits": [
        "Frozen hashes bind actual parsed bytes and current disk assets/probes; HTTP response-body bytes were not separately captured.",
        "Static source declarations, included architecture and metadata/digests match; frontend reexecution and model execution are outside this audit.",
        "Pan begins on viewport with actual left-mouse hand mode, not on observed Linear1 body; Linear1 is the sampled geometry target.",
        "Toggle down/up 2.7 ms has zero rAF callbacks in that interval. Its full trial includes preparation/settling and is not click latency.",
        "Pan lasts about eight seconds with eight trusted automation moves; not normal human task duration.",
        "rAF callbacks and observed geometry changes are proxies, never presented FPS or causal continuous input-to-paint.",
        "Three pan discrete inputs are unmatched and remain null; 2016 ms p95 is the one matched toggle interaction subset.",
        "No pinned objects; public unchanged empty pin/selection markup does not prove hidden Canvas/history or pin protection.",
        "Blur and lostpointercapture after terminal up are preserved, not active gesture cancellation tests.",
        "iframe y changes -8 to 144; object screen coordinates are iframe client CSSpx, not fixed outer-host screen continuity.",
        "Visible document and alternating iframe focus do not certify continuous host presentation or scheduling cause.",
        "Fonts report loaded and zero loadedFaces; resolved font bytes and hardware lock remain unknown.",
        "Wrong option selector deadline and iframe contentDocument TypeError are retained only as root tool-response transcription, not exhaustive original logs.",
        "No native screenshot file exists for these trials; transient tool images are outside this audit, no pixel/publication claim.",
        "Save/reopen, active cancellation, sustained presented performance, publication review and real researcher tasks are outside these two trials."]}
(HERE / "native-independent-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
lines = ["# 层级优化构建：两试次原生输入独立审计", "", "状态：passed-with-explicit-limits；M4 完整性能与人类门仍未认证。", "",
    "复现：`python3 docs/evidence/m4-hierarchy-optimization/audit_native.py`。脚本不导入产品或 observer，不操作浏览器；独立重算 source/IR/DOM/匹配，另外运行离线 validator 并核完整 parsed output exact。", "",
    f"Raw {len(FROZEN[raw_path.resolve()]):,} bytes / SHA256 `{sha(FROZEN[raw_path.resolve()])}`。{len(before)} 个 scoped 输入全部使用同一份先hash后parse的冻结bytes，审计后磁盘重读全部相同。生产3/probe6及build-context exact；不声称另捕获HTTP正文。", "",
    "正式 fixture 300 个显式 Linear/ReLU 声明、304 canonical nodes/304 edges、source aggregate 与 semantic IR digest 独立重算相符。5 个完整 SVG snapshot 的 canonical sourceFacts 全字段相符；未重执行 frontend 或模型。", "",
    "| 请求 | 结果 | DOM事实 |", "| --- | --- | --- |",
    "| toggle network | true | 4→304，可见源码身份，rev0→1，相机不变 |",
    "| viewport hand-tool pan | true | 可信左键down/up＋8moves，+40/+24 CSSpx，rev1不变 |", "",
    "Pan 全 SVG、frontier、空pin/selection markup逐字相同，目标Linear1 canvas body不变；实际输入开始于viewport，Linear1仅是几何观测对象。无pins，因此没有固定对象保护认证。", "",
    "离散 eligible 6 / matched 3 / interactions 1，matched subset p95 2016 ms，全部来自toggle一个interaction。Pan down/up/click三项未匹配，保持null，不以0填充或借用其他输入。", "",
    "| 实际down→up窗口 | duration | trusted moves | event时间窗口rAF | observed时间窗口rAF | observed几何变化 |",
    "| --- | ---: | ---: | ---: | ---: | ---: |"]
for gesture in gesture_windows:
    lines.append(f"| {gesture['operation']} | {gesture['downToUpEventWindowMs']:.4f} ms | {gesture['trustedMoves']} | {gesture['eventTimestampBoundedCallbacks']['frames']} | {gesture['observedTimestampBoundedCallbacks']['frames']} | {gesture['observedTimestampBoundedCallbacks']['geometryChangeCount']} |")
lines += ["", f"全session {len(frames)} rAF / {result['wholeSessionWindowMs']:.4f} ms；first→last callback cadence {result['wholeSessionCallbackCadence']['fps']:.8f} callbacks/s，start→stop分母 {result['wholeSessionCallbacksPerStartStopSecond']:.8f} callbacks/s。二者均不是 presented FPS；完整trial包含外页准备/等待，不能当持续交互速率。", "",
    "toggle实际down/up窗口零回调；pan八秒是可信自动化输入的实际时间，不是人类任务耗时。toggle有90ms longtask，pan无观测longtask；不证明长期或完整产品CPU耗时。", "",
    "iframe1280×720/DPR1，frameRect y−8↔144；公开对象screen记录使用iframe client CSSpx，不是固定宿主屏幕。document观测visible，iframe focus true/false，top focus true，没有连续host呈现认证。", "",
    "活动cancel未执行；post-up blur/lostcapture保留原事件。字体loaded且loadedFaces空，不绑定解析font文件；hardware未知。native截图文件未保存，瞬时工具image不纳入像素审计。真人0，研究任务/人审/保存重开均不由本轮认证。", "",
    "wrong stress300 option的selector deadline及contentDocument TypeError见tool-observations.json，仅root工具响应转录，原完整失败工具日志未捕获；不抹除、不算请求试次成功。", "",
    "审计首跑（tool chunk5b4a70）误把nn.Sequential源码构造当成IR kind，‘source-recovered network’断言失败；实际正式IR为Module/container、repeat300 independent。修正仅审计假设，源码与raw未改，失败不计成功；记录为工具响应转录。", "",
    "[完整JSON](native-independent-audit.json) 保留独立计算、全部绑定、fresh validator stdout hash、缺失项与限制。"]
(HERE / "native-independent-audit.md").write_text("\n".join(lines) + "\n")
print(json.dumps({"status": result["status"], "scopedInputs": len(before), "allScopedInputsUnchanged": True,
    "freshValidatorAllFieldsExact": True, "latency": latency, "requestedOutcomes": [value["operationSucceeded"] for value in trial_checks],
    "gestureWindows": [{"operation": value["operation"], "durationMs": value["downToUpEventWindowMs"],
        "eventFrames": value["eventTimestampBoundedCallbacks"]["frames"],
        "observedFrames": value["observedTimestampBoundedCallbacks"]["frames"],
        "geometryChanges": value["observedTimestampBoundedCallbacks"]["geometryChangeCount"]} for value in gesture_windows]}, ensure_ascii=False, indent=2))
