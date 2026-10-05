#!/usr/bin/env python3
"""Independent current-build DOM/input audit; imports no product or probe code.

Run from any directory: python3 audit_stress300.py
Raw inputs are never rewritten. All bound inputs are hashed before and after.
Only the two actual SVG revision scalars are normalized for history comparisons.
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
RAW = HERE / "stress300-raw.json"
VALIDATION = HERE / "stress300-validation.json"
TARGET = "call:instance:model.DenseStress300.network.0"
NS = "{http://www.w3.org/2000/svg}"


def sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def binding(path: Path) -> dict:
    body = path.read_bytes()
    return {"path": str(path.relative_to(PROJECT)), "bytes": len(body), "sha256": sha(body)}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def equal(a, b, message: str) -> None:
    require(a == b, message)


def close(a: float, b: float, message: str, tolerance: float = 1e-3) -> None:
    require(math.isfinite(a) and math.isfinite(b) and abs(a - b) < tolerance, message)


def percentile(values: list[float], fraction: float = .95):
    return sorted(values)[math.ceil(len(values) * fraction) - 1] if values else None


def cadence(frames: list[dict]) -> dict:
    times = [f["at"] for f in frames]
    intervals = [b - a for a, b in zip(times, times[1:])]
    require(all(i >= 0 for i in intervals), "frame times out of order")
    return {"frames": len(frames), "intervalP95Ms": percentile(intervals),
            "maxIntervalMs": max(intervals) if intervals else None,
            "fps": (len(times) - 1) * 1000 / (times[-1] - times[0])
            if len(times) > 1 and times[-1] > times[0] else None}


def no_revision(markup: str) -> str:
    result, attribute_count = re.subn(r'\bdata-revision="[0-9]+"', 'data-revision="0"', markup)
    result, metadata_count = re.subn(r'"revision":[0-9]+', '"revision":0', result)
    equal((attribute_count, metadata_count), (1, 1), "only actual two revision scalars may normalize")
    return result


def visual_signature(geometry: dict) -> str:
    return json.dumps([geometry["camera"]["matrix"],
        [[key, value["canvas"] if value else None, value["screen"] if value else None,
          value.get("label") if value else None] for key, value in geometry["objects"].items()]],
        separators=(",", ":"), ensure_ascii=False)


raw = json.loads(RAW.read_bytes())
reported = json.loads(VALIDATION.read_bytes())
context_paths = [PROJECT / b["path"] for kind in ["productionAssets", "probeSources"]
                 for b in raw["context"][kind]]
store_paths = sorted(HERE.glob("stress300-store-*.json"))
equal(len(store_paths), 1, "one explicit saved document envelope")
saved_paths = [HERE / "stress300-saved-browser.svg", HERE / "stress300-save-dom.json", *store_paths]
record_paths = [HERE / "stress300-transfer-truncated.txt", HERE / "service-sandbox-failed.txt",
                HERE / "service-raw.txt"]
input_paths = sorted(set([Path(__file__), RAW, VALIDATION, *context_paths, *saved_paths,
                         PROJECT / "fixtures/stress_300/model.py", *[p for p in record_paths if p.is_file()]]))
before_bindings = [binding(path) for path in input_paths]

equal(raw["protocol"], "archcanvas-input-observation/2", "v2 protocol")
equal(raw["schemaVersion"], 2, "v2 schema")
equal(raw["measurement"]["continuousInput"], "observed-geometry-proxy-not-paint", "continuous scope")
equal(raw["measurement"]["frames"], "raf-callback-cadence-not-presented-frames", "frame scope")
equal(raw["measurement"]["coordinateSpace"], "window-client-css-pixels", "input coordinates")
equal(raw["measurement"]["panTerminal"], "same-pointer-up-and-viewport-relative-camera/1", "pan protocol")
equal(raw["harness"]["humanParticipants"], 0, "automation excluded from human denominator")
equal(raw["harness"]["productInputsDispatched"], False, "harness dispatch declaration")
equal(raw["harness"]["productHiddenStateRead"], False, "DOM-only declaration")
equal(raw["environment"]["viewport"], {"width": 1280, "height": 720, "devicePixelRatio": 1}, "actual iframe viewport")
equal(raw["environment"]["isIframe"], True, "measurement is iframe")
equal(raw["environment"]["scripts"], ["http://127.0.0.1:8888/assets/index-DPwoyNJW.js"], "actual script URL")
equal(raw["errors"], [], "raw errors must remain explicit")
for name, accounting in raw["buffers"].items():
    equal(accounting["dropped"], 0, name + " complete buffer")
    values = raw
    for key in name.split("."):
        values = values[key]
    require(len(values) <= accounting["limit"], name + " buffer limit")

context_checks = []
for kind in ["productionAssets", "probeSources"]:
    for expected in raw["context"][kind]:
        actual = binding(PROJECT / expected["path"])
        equal(actual, expected, "disk context: " + expected["path"])
        context_checks.append({**actual, "kind": kind, "matches": True})
equal(len(context_checks), 9, "three production and six probe files")

document = json.loads(store_paths[0].read_bytes())["document"]
equal(document["revision"], 4, "saved Canvas revision")
equal(document["pinnedObjects"], [], "no pins: no pin protection claim")
architecture = document["architecture"]
for source in architecture["sources"]:
    equal(sha(source["content"].encode()), source["digest"], "source content digest")
    equal(sha((PROJECT / "fixtures/stress_300" / source["path"]).read_bytes()), source["digest"], "current fixture source digest")
equal(len(architecture["nodes"]), 304, "source canonical nodes")
equal(len(architecture["edges"]), 304, "source canonical edges")
architecture_ids = {node["id"] for node in architecture["nodes"]}

snapshot_checks = []
full_snapshots = [("start", raw["bindingAtStart"])] + [
    (t["id"] + "." + side, t[side]) for t in raw["trials"] for side in ["before", "after"]]
for name, geometry in full_snapshots:
    equal(geometry["sourceDigest"], architecture["sourceDigest"], name + " source binding")
    equal(geometry["irDigest"], architecture["irDigest"], name + " IR binding")
    equal(geometry["documentId"], document["id"], name + " document binding")
    equal(geometry["pinnedIds"], [], name + " no pins")
    svg = ET.fromstring(geometry["svgMarkup"])
    metadata = json.loads(svg.find(NS + "metadata").text)
    equal(int(svg.attrib["data-revision"]), geometry["revision"], name + " SVG revision")
    equal(metadata["revision"], geometry["revision"], name + " metadata revision")
    for key in ["sourceDigest", "irDigest", "documentId"]:
        equal(metadata[key], geometry[key], name + " SVG " + key)
    groups = {node.attrib["data-node-id"]: node for node in svg.iter()
              if "data-canonical-id" in node.attrib}
    equal(sorted(groups), geometry["visibleIds"], name + " full actual SVG frontier")
    equal(sorted(node["sceneNodeId"] for node in metadata["renderedNodes"]), geometry["visibleIds"], name + " drawn metadata frontier")
    require(set(groups).issubset(architecture_ids), name + " all source canonical ids")
    for id, observed in geometry["objects"].items():
        if observed is None:
            require(id not in groups, name + " absent selected object")
            continue
        group = groups[id]
        equal(group.attrib["data-canonical-id"], observed["canonicalId"], name + " canonical object")
        equal(group.attrib["aria-label"], observed["label"], name + " label")
        body = next(child for child in group if child.tag == NS + "rect" and "stroke-width" in child.attrib)
        for coordinate in ["x", "y", "width", "height"]:
            close(float(body.attrib[coordinate]), observed["canvas"][coordinate], name + " XML canvas " + coordinate, 1e-9)
    snapshot_checks.append({"snapshot": name, "revision": geometry["revision"],
        "visibleNodes": len(groups), "sourceFacts": len(metadata["sourceFacts"]),
        "sceneEdges": len(metadata["renderedBindings"]), "svgBytes": len(geometry["svgMarkup"].encode()),
        "svgSha256": sha(geometry["svgMarkup"].encode()), "normalizedRevisionSvgSha256": sha(no_revision(geometry["svgMarkup"]).encode())})

for frame in raw["frames"]:
    require(raw["startedAt"] <= frame["observedAt"] <= raw["stoppedAt"], "frame bound to actual session")
    if not frame["geometry"]:
        continue
    for obj in frame["geometry"]["objects"].values():
        if obj is None:
            continue
        canvas, transform, screen = obj["canvas"], obj["screenMatrix"], obj["screen"]
        corners = [(canvas["x"], canvas["y"]), (canvas["x"] + canvas["width"], canvas["y"]),
            (canvas["x"], canvas["y"] + canvas["height"]), (canvas["x"] + canvas["width"], canvas["y"] + canvas["height"])]
        points = [(transform["a"] * x + transform["c"] * y + transform["e"],
                   transform["b"] * x + transform["d"] * y + transform["f"]) for x, y in corners]
        expected = {"x": min(x for x, y in points), "y": min(y for x, y in points),
                    "width": max(x for x, y in points) - min(x for x, y in points),
                    "height": max(y for x, y in points) - min(y for x, y in points)}
        for key, value in expected.items():
            close(value, screen[key], "recorded frame transformed screen " + key)
        viewport = frame["geometry"]["viewport"]
        intersects = screen["x"] + screen["width"] > viewport["x"] and screen["x"] < viewport["x"] + viewport["width"] and \
            screen["y"] + screen["height"] > viewport["y"] and screen["y"] < viewport["y"] + viewport["height"]
        equal(intersects, obj["intersectsViewport"], "frame intersection")

discrete_types = {"pointerdown", "pointerup", "click", "keydown", "keyup"}
discrete = [event for event in raw["events"] if event["trusted"] and event["type"] in discrete_types and event["target"]["token"]]
input_candidates, entry_candidates = {}, {}
for event in discrete:
    candidates = [i for i, entry in enumerate(raw["eventTiming"])
        if entry["interactionId"] > 0 and entry["name"] == event["type"] and entry["targetToken"] == event["target"]["token"]
        and abs(entry["startAt"] - event["eventAt"]) <= 8]
    input_candidates[event["id"]] = candidates
    for i in candidates:
        entry_candidates.setdefault(i, []).append(event["id"])
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
            {"nativeEntryIndex": i, "inputs": len(entry_candidates[i])} for i in candidates],
        "missingReason": None if entry else "ambiguous" if candidates else "unavailable-below-threshold-detached-or-truncated"})
equal(matches, reported["latency"]["matches"], "independent native matching graph equals separate validator output")
durations = {}
for match in matches:
    if match["interactionId"] is not None:
        durations[match["interactionId"]] = max(match["nativeDurationMs"], durations.get(match["interactionId"], 0))
latency = {"eligibleDiscreteInputs": len(matches), "matchedDiscreteInputs": sum(m["nativeEntryIndex"] is not None for m in matches),
           "matchedInteractions": len(durations), "matchedInteractionP95Ms": percentile(list(durations.values()))}
for key, value in latency.items():
    equal(value, reported["latency"][key], "independent latency " + key)
equal(cadence(raw["frames"]), reported["frameCadence"], "independent full callback cadence")

equal([t["spec"]["operation"] for t in raw["trials"]], ["toggle", "pan", "drag", "undo", "redo"], "actual five operations")
toggle, pan, drag, undo, redo = raw["trials"]
equal([len(toggle[side]["visibleIds"]) for side in ["before", "after"]], [4, 304], "actual 4 to 304 frontier")
history_pairs = [("drag-to-undo-input", drag["after"], undo["before"]),
    ("undo-restores-entire-drag-before", drag["before"], undo["after"]),
    ("undo-to-redo-input", undo["after"], redo["before"]),
    ("redo-restores-entire-drag-after", drag["after"], redo["after"])]
history_checks = []
for name, left, right in history_pairs:
    equal(no_revision(left["svgMarkup"]), no_revision(right["svgMarkup"]), name + " entire exact SVG except revision")
    equal(left["objects"], right["objects"], name + " selected object facts")
    equal(left["camera"], right["camera"], name + " camera")
    equal(left["expandedIds"], right["expandedIds"], name + " frontier flags")
    history_checks.append({"pair": name, "leftRevision": left["revision"], "rightRevision": right["revision"],
        "fullSvgExactExceptRevision": True, "selectedObjectFactsExact": True,
        "normalizedSvgSha256": sha(no_revision(left["svgMarkup"]).encode())})
equal(pan["before"]["svgMarkup"], pan["after"]["svgMarkup"], "pan public full SVG exact")
for field in ["visibleIds", "expandedIds", "pinnedIds", "selectionMarkup", "revision"]:
    equal(pan["before"][field], pan["after"][field], "pan public " + field + " unchanged")
equal(HERE.joinpath("stress300-saved-browser.svg").read_text(), redo["after"]["svgMarkup"], "saved browser SVG exact redo final")
equal(json.loads(HERE.joinpath("stress300-save-dom.json").read_text())["svgLength"], len(redo["after"]["svgMarkup"]), "saved DOM SVG length")
equal(drag["after"]["objects"][TARGET]["canvas"]["x"] - drag["before"]["objects"][TARGET]["canvas"]["x"], 40, "drag x +40")
equal(drag["after"]["objects"][TARGET]["canvas"]["y"] - drag["before"]["objects"][TARGET]["canvas"]["y"], 24, "drag y +24")

gesture_checks = []
for trial in [pan, drag]:
    events = [e for e in raw["events"] if e["trialId"] == trial["id"]]
    down = next(e for e in events if e["type"] == "pointerdown" and e["trusted"])
    ups = [e for e in events if e["type"] == "pointerup" and e["trusted"] and e["pointerId"] == down["pointerId"]]
    equal(len(ups), 1, "unique same pointer up")
    up = ups[0]
    moves = [e for e in events if e["type"] == "pointermove" and e["trusted"] and e["pointerId"] == down["pointerId"]
             and down["eventAt"] <= e["eventAt"] <= up["eventAt"]]
    equal(len(moves), 8, "eight actual trusted pointermoves")
    equal(down["target"]["nodeId"], TARGET, "actual gesture node body")
    active = [e for e in events if down["eventAt"] <= e["eventAt"] < up["eventAt"]]
    require(not any(e["type"] in ["blur", "pointercancel", "lostpointercapture"] or
                    e["type"] == "keydown" and e.get("key") == "Escape" for e in active), "no active cancellation")
    event_frames = [f for f in raw["frames"] if f["trialId"] == trial["id"] and down["eventAt"] <= f["at"] <= up["eventAt"]]
    observed_frames = [f for f in raw["frames"] if f["trialId"] == trial["id"] and down["capturedAt"] <= f["observedAt"] <= up["capturedAt"]]
    changed = []
    previous = visual_signature(trial["before"])
    for frame in observed_frames:
        signature = visual_signature(frame["geometry"])
        if signature != previous:
            changed.append(frame)
        previous = signature
    duration = up["eventAt"] - down["eventAt"]
    input_delta = {axis: (up[axis] - up["viewport"][axis]) - (down[axis] - down["viewport"][axis]) for axis in ["x", "y"]}
    if trial is pan:
        equal(down["target"]["canvasTool"], "pan", "actual hand tool")
        equal(down["target"]["handToolPressed"], True, "actual hand tool pressed")
        equal(input_delta, {"x": 48, "y": 32}, "pan actual viewport relative terminal input")
        expected_camera = {**trial["before"]["camera"]["matrix"]}
        expected_camera["e"] += input_delta["x"]
        expected_camera["f"] += input_delta["y"]
        for key, value in expected_camera.items():
            close(value, trial["after"]["camera"]["matrix"][key], "actual terminal pan " + key)
        for id in trial["spec"]["targetIds"] + trial["spec"]["anchorIds"]:
            equal(trial["before"]["objects"][id]["canvas"], trial["after"]["objects"][id]["canvas"], "pan canvas facts unchanged")
    else:
        equal(down["target"]["canvasTool"], "select", "actual select tool")
        equal(down["target"]["handToolPressed"], False, "hand off for node move")
    gesture_checks.append({"trialId": trial["id"], "operation": trial["spec"]["operation"],
        "downInputId": down["id"], "upInputId": up["id"], "pointerId": down["pointerId"],
        "downEventAt": down["eventAt"], "upEventAt": up["eventAt"], "downToUpEventWindowMs": duration,
        "trustedMoves": len(moves), "terminalViewportRelativeInputDeltaCssPx": input_delta,
        "eventTimestampBoundedCallbacks": {**cadence(event_frames), "callbackTimes": [f["at"] for f in event_frames],
            "callbacksPerEventWindowSecond": len(event_frames) * 1000 / duration},
        "observedTimestampBoundedCallbacks": {**cadence(observed_frames),
            "geometryChangeCount": len(changed), "changedObservedAt": [f["observedAt"] for f in changed]},
        "eventToCaptureMs": [e["capturedAt"] - e["eventAt"] for e in moves],
        "presentedFramesCertified": False, "causalInputToPaintCertified": False})

after_bindings = [binding(path) for path in input_paths]
equal(before_bindings, after_bindings, "all scoped inputs unchanged during independent audit")
result = {
    "schema": "archcanvas-current-native-independent-audit/1",
    "status": "passed-with-explicit-limits", "script": binding(Path(__file__)),
    "raw": binding(RAW), "separateValidator": binding(VALIDATION),
    "inputBindingsBefore": before_bindings, "inputBindingsAfter": after_bindings,
    "allScopedInputsUnchanged": True, "contextDiskBindings": context_checks,
    "scope": "Frozen current DPwoy same-origin iframe stress300 five-trial automation; independent DOM and discrete matching, no product imports.",
    "counts": {key: len(raw[key]) for key in ["trials", "events", "frames", "eventTiming", "longTasks", "visibility", "errors"]},
    "snapshots": snapshot_checks, "history": history_checks,
    "publicPanContinuityExact": True, "pinProtectionMeasured": False,
    "savedBrowserSvgExactFinalRaw": True, "savedCanvasRevision": document["revision"],
    "latency": {**latency, "perInteractionDurationMs": durations, "matches": matches,
        "missingInputIds": [m["inputId"] for m in matches if m["nativeEntryIndex"] is None],
        "missingValuesRemainNull": True, "scope": "Uniquely matched discrete subset only; no continuous latency/overall INP"},
    "gestureWindows": gesture_checks, "wholeSessionCallbackCadence": cadence(raw["frames"]),
    "wholeSessionWindowMs": raw["stoppedAt"] - raw["startedAt"],
    "wholeSessionCallbacksPerStartStopSecond": len(raw["frames"]) * 1000 / (raw["stoppedAt"] - raw["startedAt"]),
    "visibility": {"observedStates": sorted(set(v["state"] for v in raw["visibility"])),
        "iframeFocusValues": sorted(set(v["hasFocus"] for v in raw["visibility"])),
        "topFocusValues": sorted(set(v["topHasFocus"] for v in raw["visibility"])),
        "hostContinuousPresentationCertified": False},
    "limitations": [
        "Actual source/current disk asset and probe bytes match; network response bodies were not separately captured.",
        "Saved Canvas source/IR, revision and source bytes checked. Save/reopen history persistence is outside this audit.",
        "Zero pinned objects; no protected-pin result was measured.",
        "Two geometry windows are trusted automation lasting about eight seconds; not normal human drag time or participant performance.",
        "rAF callback cadence and DOM change count are not presented FPS or causal continuous input-to-paint.",
        "Native drag pointerdown and all three redo discrete entries are unavailable; missing durations remain null.",
        "Known transfer truncation record is retained; successful later raw JSON parsing does not certify the failed first transfer.",
        "Browser tool public-DOM/frame reads and AX large-frame limit observations are not exhaustively captured by this script; missing UI evidence remains unknown, never zero.",
        "Visible document states and alternating iframe focus do not prove continuous host presentation or a scheduling cause.",
        "Font loading reports loaded with zero loadedFaces; resolved font files/hardware lock remain unverified.",
        "Agent automation is not a researcher, human publication review or completed M4 performance gate.",
    ]}
output = HERE / "stress300-independent-audit.json"
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
summary = ["# 当前构建 stress300 原生输入独立审计", "", "状态：passed-with-explicit-limits。仅新增诊断；不认证 M4 性能目标、持续呈现或真人任务。", "",
    "复现：`python3 docs/evidence/m4-current-native-diagnostic/audit_stress300.py`。脚本不导入产品、observer 或 validator；独立计算与另存 validator 输出逐字段核对。", "",
    f"原始收据 {len(RAW.read_bytes()):,} bytes / SHA256 `{sha(RAW.read_bytes())}`。{len(input_paths)} 个 scoped 输入在审计前后 hash 完全一致；生产3文件和probe6文件均与当前磁盘原字节匹配。未另捕获HTTP响应正文。", "",
    "五试次为4→304对象展开、手工具pan、Linear 1拖动、undo、redo。pan终点+48/+32 CSSpx，完整SVG/frontier/revision/public selection不变；drag节点+40/+24 canvas px。去掉SVG attribute和metadata两个revision数值后，undo恢复全部SVG字节到drag前，redo恢复全部SVG字节到drag后；已保存浏览器SVG与最终raw逐字相同。无pins，因此没有pin保护结果。", "",
    f"离散事件14 eligible /10 matched /4 interactions；matched子集p95 {latency['matchedInteractionP95Ms']} ms。drag pointerdown与redo的down/up/click缺失，共4项保持null，不是零延迟。", "",
    "| 操作 | 实际 down→up 窗口 | 可信moves | 窗口内rAF回调 | 最大回调间隔 | observed时间窗口内几何变更 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
for item in gesture_checks:
    summary.append(f"| {item['operation']} | {item['downToUpEventWindowMs']:.1f} ms | {item['trustedMoves']} | {item['eventTimestampBoundedCallbacks']['frames']} | {item['eventTimestampBoundedCallbacks']['maxIntervalMs']:.1f} ms | {item['observedTimestampBoundedCallbacks']['geometryChangeCount']} |")
summary += ["", "窗口使用实际输入event时间戳，不含Arm后等待；几何变更另用实际observedAt窗口。JSON保留两种分母和完整回调时刻，不把回调或几何变化写成presented FPS。八秒代理输入不是人工任务耗时。", "",
    "文档始终观测为visible，iframe focus有true/false，top focus为true；没有持续宿主呈现证明，调度原因仍未知。fonts loaded/loadedFaces=[]不绑定实际解析字体。", "",
    "首轮传输截断记录保留；工具DOM读取失败与AX大frame限制不在此脚本的完整原始工具日志范围中，不能据缺失判零或成功。saved重开链、机器/字体锁定、人审与研究者任务未纳入本审计。", "",
    "详细结果：[stress300-independent-audit.json](stress300-independent-audit.json)。"]
(HERE / "stress300-independent-audit.md").write_text("\n".join(summary) + "\n")
print(json.dumps({"status": result["status"], "inputs": len(input_paths), "allScopedInputsUnchanged": True,
    "latency": latency, "gestureWindows": [{"operation": g["operation"], "durationMs": g["downToUpEventWindowMs"],
        "callbackCount": g["eventTimestampBoundedCallbacks"]["frames"], "geometryChanges": g["observedTimestampBoundedCallbacks"]["geometryChangeCount"]} for g in gesture_checks],
    "outputs": [str(output), str(HERE / "stress300-independent-audit.md")]}, ensure_ascii=False, indent=2))
