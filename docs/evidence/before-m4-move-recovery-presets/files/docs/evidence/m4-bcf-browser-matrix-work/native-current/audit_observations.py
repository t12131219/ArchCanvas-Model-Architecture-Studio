"""Read-only independent audit of current native evidence; no product imports.

Creates a fresh sibling output directory. Raw captures and earlier manifests
are never edited. Public SVG geometry is parsed directly from captured markup;
only canonical architecture facts come from the separately sealed matrix.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
NS = "{http://www.w3.org/2000/svg}"


def seal(path):
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    with path.open("x") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def p95(values):
    return sorted(values)[math.ceil(.95 * len(values)) - 1] if values else None


def close(a, b):
    return abs(a - b) < .001


def normalize_svg(markup):
    # Remove only the two public revision fields. Preserve all other XML,
    # source facts, routes, ports, labels, styles and viewBox attributes.
    svg = ET.fromstring(markup)
    svg.attrib.pop("data-revision", None)
    metadata = svg.find(NS + "metadata")
    facts = json.loads(metadata.text)
    facts.pop("revision")
    metadata.text = json.dumps(facts, ensure_ascii=False, separators=(",", ":"))
    return ET.tostring(svg, encoding="unicode")


def public_restore(a, b):
    return {
        "svgEqualExceptPublicRevision": normalize_svg(a["svgMarkup"]) == normalize_svg(b["svgMarkup"]),
        "frontierEqual": a["visibleIds"] == b["visibleIds"] and a["expandedIds"] == b["expandedIds"],
        "pinsEqual": a["pinnedIds"] == b["pinnedIds"],
        "selectionMarkupEqual": a["selectionMarkup"] == b["selectionMarkup"],
        "cameraEqual": a["camera"] == b["camera"],
        "scope": "Recorded public markup/geometry; no saved Canvas or hidden history certification",
    }


def parse_public_geometry(g, architecture):
    """Direct standard-XML adapter; never synthesizes an actual CanvasDocument."""
    svg = ET.fromstring(g["svgMarkup"])
    metadata = json.loads(svg.find(NS + "metadata").text)
    assert svg.get("data-document-id") == metadata["documentId"] == g["documentId"]
    assert int(svg.get("data-revision")) == metadata["revision"] == g["revision"]
    assert metadata["sourceDigest"] == g["sourceDigest"] == architecture["sourceDigest"]
    assert metadata["irDigest"] == g["irDigest"] == architecture["irDigest"]
    canonical = {n["id"]: n for n in architecture["nodes"]}
    canonical_edges = {e["id"]: e for e in architecture["edges"]}
    assert len(metadata["sourceFacts"]) == len(canonical)
    for fact in metadata["sourceFacts"]:
        original = canonical[fact["id"]]
        assert fact["sourceLabel"] == original["label"]
        for key in ("kind", "category", "source", "evidence", "instanceId", "callId", "repeat", "outputPath"):
            assert fact.get(key) == original.get(key), (fact["id"], key)
        if fact.get("instanceId"):
            assert fact["callCount"] == sum(n.get("instanceId") == fact["instanceId"] for n in architecture["nodes"])
    groups = {e.get("data-node-id"): e for e in svg.iter() if e.get("data-node-id") and not e.get("data-port-id")}
    assert len(groups) == len(metadata["renderedNodes"])
    assert set(groups) == set(g["visibleIds"]) == {n["sceneNodeId"] for n in metadata["renderedNodes"]}
    nodes = []
    for node_id, group in groups.items():
        bodies = [e for e in group if e.tag == NS + "rect" and e.get("stroke-width")]
        assert len(bodies) == 1
        body = bodies[0]
        node = {"id": node_id, **{k: float(body.get(k)) for k in ("x", "y", "width", "height")}, "ports": []}
        if canonical[node_id].get("parentId"):
            node["parentId"] = canonical[node_id]["parentId"]
        dividers = [e for e in group if e.tag == NS + "path" and e.get("opacity") == ".28"]
        assert len(dividers) == int(node_id in g["expandedIds"])
        node["headerHeight"] = float(re.fullmatch(r"M\s+[-\d.]+\s+([-\d.]+)\s+H\s+[-\d.]+", dividers[0].get("d"))[1]) - node["y"] + 4 if dividers else node["height"]
        observed = g["objects"].get(node_id)
        if observed:
            assert all(close(node[k], observed["canvas"][k]) for k in ("x", "y", "width", "height"))
        nodes.append(node)
    by_node = {n["id"]: n for n in nodes}

    def representative(identity):
        seen = set()
        while identity not in groups:
            assert identity not in seen and identity in canonical
            seen.add(identity)
            identity = canonical[identity].get("parentId")
        return identity

    bindings = metadata["renderedBindings"]
    represented = set()
    for binding in bindings:
        assert binding["canonicalEdgeIds"] and not represented.intersection(binding["canonicalEdgeIds"])
        represented.update(binding["canonicalEdgeIds"])
        has_canonical_binding = False
        for edge_id in binding["canonicalEdgeIds"]:
            edge = canonical_edges[edge_id]
            assert edge["tensorId"] == binding["tensorId"] and edge["role"] == binding["role"]
            for endpoint, direction in (("source", "out"), ("target", "in")):
                a, b = edge[endpoint], binding[endpoint]
                assert representative(a["nodeId"]) == representative(b["nodeId"])
                assert any(p["id"] == a["portId"] and p["direction"] == direction for p in canonical[a["nodeId"]]["ports"])
            has_canonical_binding |= edge["source"] == binding["source"] and edge["target"] == binding["target"]
        assert has_canonical_binding
    for group in svg.iter():
        if not group.get("data-port-id"):
            continue
        circle = group if group.tag == NS + "circle" else next(e for e in group if e.tag == NS + "circle")
        owner, port_id = group.get("data-node-id"), group.get("data-port-id")
        matches = []
        for binding in bindings:
            for endpoint, direction in (("source", "out"), ("target", "in")):
                b = binding[endpoint]
                if owner == representative(b["nodeId"]) and port_id == f'{b["nodeId"]}:{b["portId"]}:{binding["role"]}':
                    matches.append((binding, direction))
        assert matches and len({direction for _, direction in matches}) == 1
        by_node[owner]["ports"].append({"id": port_id, "direction": matches[0][1], "canonicalEdgeIds": list(dict.fromkeys(i for b, _ in matches for i in b["canonicalEdgeIds"])), "x": float(circle.get("cx")), "y": float(circle.get("cy"))})
    edge_groups = {e.get("data-edge-id"): e for e in svg.iter() if e.get("data-edge-id")}
    assert set(edge_groups) == {b["sceneEdgeId"] for b in bindings}
    edges = []
    for b in bindings:
        group = edge_groups[b["sceneEdgeId"]]
        assert group.get("data-tensor-id") == b["tensorId"]
        path = next(e for e in group if e.tag == NS + "path")
        edges.append({"id": b["sceneEdgeId"], "sourceId": representative(b["source"]["nodeId"]), "targetId": representative(b["target"]["nodeId"]), **{k: b[k] for k in ("source", "target", "canonicalEdgeIds", "tensorId", "role")}, "path": path.get("d")})
    x, y, w, h = map(float, svg.get("viewBox").split())
    return {"documentId": g["documentId"], "revision": g["revision"], "sourceDigest": g["sourceDigest"], "irDigest": g["irDigest"], "bounds": {"x": x, "y": y, "width": w, "height": h}, "nodes": nodes, "edges": edges}


def collision_geometry(scene):
    by_id = {n["id"]: n for n in scene["nodes"]}

    def ancestors(n):
        result = set()
        parent = n.get("parentId")
        while parent:
            assert parent not in result
            result.add(parent)
            parent = by_id.get(parent, {}).get("parentId")
        return result

    body_pairs, header_pairs, outside = [], [], []
    for i, a in enumerate(scene["nodes"]):
        for b in scene["nodes"][i + 1:]:
            if a["id"] in ancestors(b) or b["id"] in ancestors(a):
                continue
            width = min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"])
            height = min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"])
            if width > 0 and height > 0:
                body_pairs.append({"first": a["id"], "second": b["id"], "width": width, "height": height})
        p = by_id.get(a.get("parentId"))
        if p:
            if a["x"] < p["x"] or a["x"] + a["width"] > p["x"] + p["width"] or a["y"] + a["height"] > p["y"] + p["height"]:
                outside.append({"node": a["id"], "parent": p["id"]})
            if a["y"] < p["y"] + p["headerHeight"] and a["y"] + a["height"] > p["y"] and a["x"] < p["x"] + p["width"] and a["x"] + a["width"] > p["x"]:
                header_pairs.append({"node": a["id"], "parent": p["id"], "headerBottom": p["y"] + p["headerHeight"]})
    return {"nonAncestorBodyOverlaps": body_pairs, "directChildHeaderOverlaps": header_pairs, "directChildOutsideParentBody": outside, "scope": "Geometric body/header observations only; no UI warning-text reconstruction or aesthetic approval"}


def matching_audit(raw, validator):
    inputs = [e for e in raw["events"] if e["trusted"] and e["type"] in ("pointerdown", "pointerup", "click", "keydown", "keyup") and e["target"]["token"]]
    candidate = {e["id"]: [i for i, t in enumerate(raw["eventTiming"]) if t["interactionId"] > 0 and t["name"] == e["type"] and t["targetToken"] == e["target"]["token"] and abs(t["startAt"] - e["eventAt"]) <= 8] for e in inputs}
    reverse = {i: [e["id"] for e in inputs if i in candidate[e["id"]]] for i in range(len(raw["eventTiming"]))}
    matches, durations = [], {}
    for e in inputs:
        if e["trialId"] is None:
            continue
        c = candidate[e["id"]]
        index = c[0] if len(c) == 1 and len(reverse[c[0]]) == 1 else None
        t = raw["eventTiming"][index] if index is not None else None
        matches.append({"inputId": e["id"], "nativeEntryIndex": index, "interactionId": t["interactionId"] if t else None, "nativeDurationMs": t["durationMs"] if t else None})
        if t:
            durations[t["interactionId"]] = max(durations.get(t["interactionId"], 0), t["durationMs"])
    reference = [{k: m[k] for k in ("inputId", "nativeEntryIndex", "interactionId", "nativeDurationMs")} for m in validator["latency"]["matches"]]
    assert matches == reference
    assert p95(list(durations.values())) == validator["latency"]["matchedInteractionP95Ms"]
    return {"bilateralUniqueMatchesEqualValidator": True, "allRawTrustedDiscreteInputsCompete": len(inputs), "eligibleAssignedInputs": len(matches), "matchedAssignedInputs": sum(m["nativeEntryIndex"] is not None for m in matches), "interactionMaxDurationsMs": durations, "matchedInteractions": len(durations), "matchedInteractionP95Ms": p95(list(durations.values())), "matches": matches, "scope": "Matched subset; interaction max counted once, not overall page INP or continuous-input latency"}


def audit_trials(raw, validator):
    results = []
    for trial, checked in zip(raw["trials"], validator["trials"]):
        inputs = [e for e in raw["events"] if e["trialId"] == trial["id"]]
        trusted = [e for e in inputs if e["trusted"]]
        down = next((e for e in trusted if e["type"] == "pointerdown"), None)
        ups = [e for e in trusted if down and e["type"] == "pointerup" and e["pointerId"] == down["pointerId"] and e["eventAt"] >= down["eventAt"]]
        up = ups[0] if len(ups) == 1 else None
        moves = [e for e in trusted if down and e["type"] == "pointermove" and e["pointerId"] == down["pointerId"] and down["eventAt"] <= e["eventAt"] and (not up or e["eventAt"] <= up["eventAt"])]
        before, after = trial["before"], trial["after"]
        frames = [f for f in raw["frames"] if f["trialId"] == trial["id"]]
        active_frames = [f for f in frames if down and up and down["eventAt"] <= f["at"] <= up["eventAt"]]
        intervals = [b["at"] - a["at"] for a, b in zip(active_frames, active_frames[1:])]
        row = {"id": trial["id"], "operation": trial["spec"]["operation"], "requestedTargets": trial["spec"]["targetIds"], "eventIds": [e["id"] for e in inputs], "allRecordedInputsTrusted": len(trusted) == len(inputs), "down": down, "up": up, "samePointerUpCount": len(ups), "trustedMoveCount": len(moves), "downToUpMs": up["eventAt"] - down["eventAt"] if down and up else None, "revisionDelta": after["revision"] - before["revision"], "sourceAndIRUnchanged": all(before[k] == after[k] for k in ("documentId", "sourceDigest", "irDigest")), "cameraBefore": before["camera"], "cameraAfter": after["camera"], "recordedTrialFrames": len(frames), "recordedActiveGestureFrames": len(active_frames), "activeCallbackIntervalP95Ms": p95(intervals), "activeCallbackMaxIntervalMs": max(intervals) if intervals else None, "existingValidatorOperationSucceeded": checked["operationSucceeded"], "existingValidatorPanTerminal": checked.get("panTerminal"), "continuousProxies": checked["continuousProxies"], "pinClaims": trial["spec"]["pinnedIds"], "presentedPaintCertified": False}
        if down and up:
            active = [e for e in trusted if down["eventAt"] <= e["eventAt"] <= up["eventAt"] and trusted.index(e) < trusted.index(up)]
            row["cancellationBeforeRelease"] = [e["id"] for e in active if e["type"] in ("pointercancel", "lostpointercapture", "blur") or e["type"] == "keydown" and e.get("key") == "Escape"]
            row["normalCaptureLossAfterRelease"] = [e["id"] for e in trusted if e["type"] == "lostpointercapture" and trusted.index(e) > trusted.index(up)]
        if row["operation"] == "drag":
            target = row["requestedTargets"][0]
            a, b = before["objects"][target]["canvas"], after["objects"][target]["canvas"]
            row["bodyBefore"] = a
            row["bodyAfter"] = b
            row["actualCanvasDelta"] = {k: b[k] - a[k] for k in ("x", "y")}
            row["terminalCssDelta"] = {"x": up["x"] - down["x"], "y": up["y"] - down["y"]}
            row["targetHitExact"] = down["target"]["nodeId"] == target and down["target"]["kind"] == "node"
        if row["operation"] == "pan":
            a, b = before["camera"]["matrix"], after["camera"]["matrix"]
            dx = (up["x"] - up["viewport"]["x"]) - (down["x"] - down["viewport"]["x"])
            dy = (up["y"] - up["viewport"]["y"]) - (down["y"] - down["viewport"]["y"])
            expected = {**a, "e": a["e"] + dx, "f": a["f"] + dy}
            row["independentRecordedTerminalCamera"] = {"matched": all(close(expected[k], b[k]) for k in expected), "deltaCssPx": {"x": dx, "y": dy}, "expected": expected, "eventBufferComplete": raw["buffers"]["events"]["dropped"] == 0, "afterNotBeforePointerUpCapture": after["at"] >= up["capturedAt"], "scope": "Complete recorded event buffer plus terminal public snapshots only; does not override global validator failure"}
            row["publicMarkupContinuity"] = {"svgExact": before["svgMarkup"] == after["svgMarkup"], **{k + "Exact": before[k] == after[k] for k in ("visibleIds", "expandedIds", "pinnedIds", "selectionMarkup")}}
        results.append(row)
    return results


def main():
    out = HERE / (sys.argv[1] if len(sys.argv) > 1 else "independent-observation-audit-1")
    assert out.parent == HERE and out.name.startswith("independent-observation-audit-"), "Fresh local audit directory required"
    assert not out.exists(), "Refusing to overwrite any earlier audit"
    inputs = HERE / "mlp-four-directions-1"
    pilot = HERE / "top-mlp-5toggle"
    canonical_path = ROOT / "docs/evidence/browser-visual-matrix-bcf-full/captures/mlp-level1-paper-180/canvas.json"
    analyzer = ROOT / "docs/evidence/m4-bcf-browser-matrix-work/routing-quality/analyze_scene.ts"
    sources = [Path(__file__), ROOT / "scripts/validate_input_observation.mjs", ROOT / "scripts/validate_native_performance.mjs", analyzer, ROOT / "docs/evidence/m4-routing-refinement/independent/oracle.ts", ROOT / "docs/evidence/m4-routing-refinement/independent/controls.ts", ROOT / "docs/evidence/m4-routing-refinement/independent/fixtures.ts"]
    raw = load(inputs / "raw-full.json")
    production = [ROOT / r["path"] for r in raw["context"]["productionAssets"] + raw["context"]["probeSources"]]
    files = sorted(p for p in inputs.rglob("*") if p.is_file()) + sorted(p for p in pilot.rglob("*") if p.is_file()) + [canonical_path] + sources + production
    initial = [seal(p) for p in files]
    out.mkdir()
    executions = []
    for kind, command in (("input-validator", ["node", str(ROOT / "scripts/validate_input_observation.mjs"), str(inputs / "raw-full.json")]), ("pilot-validator", ["node", str(ROOT / "scripts/validate_native_performance.mjs"), str(pilot / "raw.json")]), ("oracle-controls", ["node", "--experimental-strip-types", str(analyzer), "--controls"])):
        process = subprocess.run(command, capture_output=True, text=True)
        receipt = {"command": command, "exitCode": process.returncode, "stdout": process.stdout, "stderr": process.stderr}
        save(out / (kind + "-execution.json"), receipt)
        executions.append(receipt)
        assert process.returncode == 0, kind
        save(out / (kind + ".json"), json.loads(process.stdout))
    validated = load(out / "input-validator.json")
    index, reconstruction = load(inputs / "raw-chunk-index.json"), load(inputs / "raw-reassembly.json")
    chunks, chunk_bindings, offset = [], [], 0
    assert len(index["chunks"]) == len(reconstruction["parts"]) == 70
    for entry, recorded in zip(index["chunks"], reconstruction["parts"]):
        path = inputs / "raw-chunks" / recorded["path"]
        chunk = path.read_text()
        assert recorded["offset"] == entry["offset"] == offset
        assert recorded["characters"] == entry["length"] == len(chunk)
        binding = seal(path)
        assert binding["sha256"] == recorded["sha256"] and binding["bytes"] == recorded["bytes"]
        assert Path(entry["file"]).name == path.name
        chunk_bindings.append({**binding, "offset": offset, "unicodeCharacters": len(chunk)})
        chunks.append(chunk)
        offset += len(chunk)
    full = (inputs / "raw-full.json").read_bytes()
    assert "".join(chunks).encode() == full
    assert offset == index["actualTextareaLength"] == reconstruction["actualTextareaCharacters"]
    assert hashlib.sha256(full).hexdigest() == reconstruction["fullSha256"]
    try:
        load(inputs / "raw.json")
        truncated_error = None
    except json.JSONDecodeError as e:
        truncated_error = str(e)
    assert truncated_error is not None
    reassembly = {"chunks": chunk_bindings, "contiguousUnicodeOffsets": True, "joinedBytesExactRawFull": True, "unicodeCharacters": offset, "utf8Bytes": len(full), "full": seal(inputs / "raw-full.json"), "truncatedOriginal": {**seal(inputs / "raw.json"), "jsonParseError": truncated_error}, "scope": "Filesystem reassembly/coherence check; root attributes chunks to UI reads. Auditor did not replay browser capture."}
    save(out / "reassembly-audit.json", reassembly)
    matching = matching_audit(raw, validated)
    save(out / "bilateral-event-timing-audit.json", matching)
    trials = audit_trials(raw, validated)
    save(out / "trial-audit.json", trials)
    architecture_doc = load(canonical_path)
    architecture_doc = architecture_doc.get("document", architecture_doc)
    architecture = architecture_doc["architecture"]
    scenes = {(t["id"], kind): parse_public_geometry(t[kind], architecture) for t in raw["trials"] for kind in ("before", "after")}
    geometry = []
    for trial_id, kind in (("trial-1", "before"), ("trial-1", "after"), ("trial-4", "after"), ("trial-6", "after"), ("trial-8", "after"), ("trial-15", "after"), ("trial-16", "after")):
        scene = scenes[trial_id, kind]
        name = f"{trial_id}-{kind}"
        scene_path = out / (name + ".public-xml-scene.json")
        save(scene_path, scene)
        process = subprocess.run(["node", "--experimental-strip-types", str(analyzer), str(scene_path)], capture_output=True, text=True)
        save(out / (name + ".oracle-execution.json"), {"exitCode": process.returncode, "stdout": process.stdout, "stderr": process.stderr})
        assert process.returncode == 0
        metric = json.loads(process.stdout)
        save(out / (name + ".routing.json"), metric)
        geometry.append({"trialId": trial_id, "snapshot": kind, "scene": scene_path.name, "xmlAndCanonicalProjectionCheck": True, "bodyGeometry": collision_geometry(scene), **{k: metric[k] for k in ("distinctTensor", "sameTensor", "disjointOwners", "totalBends", "totalReversals", "bodyHeaderIntrusions", "endpointAndViewBoxCheck")}})
    save(out / "routing-body-audit.json", geometry)
    restoration = [{"fromTrial": drag, "undoTrial": undo, **public_restore(raw["trials"][drag - 1]["before"], raw["trials"][undo - 1]["after"])} for drag, undo in ((1, 2), (4, 5), (6, 7), (8, 9))]
    restoration.append({"rightRedo": True, **public_restore(raw["trials"][0]["after"], raw["trials"][2]["after"])})
    restoration.append({"collapseReexpand": True, **public_restore(raw["trials"][14]["before"], raw["trials"][15]["after"])})
    save(out / "public-restoration-audit.json", restoration)
    contexts = []
    for declared in raw["context"]["productionAssets"] + raw["context"]["probeSources"]:
        actual = seal(ROOT / declared["path"])
        assert actual["bytes"] == declared["bytes"] and actual["sha256"] == declared["sha256"]
        contexts.append({"declared": declared, "actual": actual, "diskHashExact": True})
    native = load(pilot / "raw.json")
    # Stronger bilateral check for this older sampler. The sampler and its
    # validator match by sequential unused entry; retain their original result.
    candidates = [[i for i, e in enumerate(native["snapshot"]["eventTiming"]) if t["trusted"] and e["name"] == t["eventName"] and e["targetCanonicalNodeId"] == t["targetId"] and e["interactionId"] > 0 and abs(e["startAt"] - t["eventAt"]) <= 8] for t in native["trials"]]
    reverse = {i: [j for j, c in enumerate(candidates) if i in c] for i in range(len(native["snapshot"]["eventTiming"]))}
    pilot_matches, interaction_max, valid_interaction_max = [], {}, {}
    for j, (t, c) in enumerate(zip(native["trials"], candidates)):
        i = c[0] if len(c) == 1 and len(reverse[c[0]]) == 1 else None
        e = native["snapshot"]["eventTiming"][i] if i is not None else None
        assert t["nativeEventTiming"] == e
        if e:
            interaction_max[e["interactionId"]] = max(interaction_max.get(e["interactionId"], 0), e["durationMs"])
            if t["bindingValid"] and t["targetChanged"] and not t["error"]:
                valid_interaction_max[e["interactionId"]] = max(valid_interaction_max.get(e["interactionId"], 0), e["durationMs"])
        pilot_matches.append({"trial": j + 1, "operation": t["operation"], "beforeRevision": t["before"]["revision"], "afterRevision": t["after"]["revision"] if t["after"] else None, "error": t["error"], "bindingValid": t["bindingValid"], "targetChanged": t["targetChanged"], "candidateIndices": c, "bilateralMatchedIndex": i, "interactionId": e["interactionId"] if e else None, "durationMs": e["durationMs"] if e else None})
    public_env = load(pilot / "public-env.json")
    pilot_assets = [{"url": url, "disk": seal(ROOT / "studio/dist" / url.split("8982/", 1)[1])} for url in public_env["assetUrls"]]
    save(out / "pilot-independent-audit.json", {"raw": seal(pilot / "raw.json"), "trials": pilot_matches, "bilateralMatchesAgreeSampler": True, "matchedInteractionMaxMs": interaction_max, "validMatchedInteractionMaxMs": valid_interaction_max, "validMatchedInteractionP95Ms": p95(list(valid_interaction_max.values())), "publicEnv": public_env, "rawEnvironment": native["environment"], "sameRecordedViewport": native["environment"]["viewport"]["width"] == public_env["viewport"]["width"] and native["environment"]["viewport"]["height"] == public_env["viewport"]["height"], "publicAssetUrlDiskBindings": pilot_assets, "frameBufferTruncatedDeclared": native["frames"]["bufferTruncated"], "limitations": ["5 recorded clicks do not establish 5 correctly sampled transitions: only 2 valid, two revision +2, last missing after", "One matched native interaction reports4008ms; p95 over one is not a population or full-page INP", "Raw1280x720 and later public1102x835 viewport disagree; no fixed environment certification", "rAF callback cadence approximately1Hz has unknown cause and is not presented frame rate", "Loaded public asset URLs bind disk files but not fetched response bytes", "Recorded journal is root-authored browser evidence; auditor did not reproduce input", "Fonts loadedFaces empty is not resolved font lock", "No pins were specified/measured"]})
    final = [seal(p) for p in files]
    assert final == initial, "Read-only audit input changed"
    summary = {"schema": "archcanvas-independent-current-native-audit/1", "createdAtUTC": datetime.now(timezone.utc).isoformat(), "inputBindings": initial, "inputBytesUnchanged": True, "reassemblyPassed": True, "trials": len(raw["trials"]), "xmlSnapshotsParsedAndCanonicallyBound": len(scenes), "bufferDrops": raw["buffers"], "globalExistingValidatorCompleteBuffers": validated["completeBuffers"], "lastStoredFrameAt": raw["frames"][-1]["at"], "firstStoredFrameAt": raw["frames"][0]["at"], "lastStoredFrameObservedAt": raw["frames"][-1]["observedAt"], "observationStoppedAt": raw["stoppedAt"], "eventTiming": {k: matching[k] for k in ("eligibleAssignedInputs", "matchedAssignedInputs", "matchedInteractions", "matchedInteractionP95Ms")}, "sourceContext": contexts, "publicLoadedScriptUrls": raw["environment"]["scripts"], "unassignedDiscreteInputs": [e for e in raw["events"] if e["trialId"] is None and e["type"] in ("pointerdown", "pointerup", "click")], "pilotValidSceneTrials": native["summary"]["validSceneTrials"], "humanCertified": False, "publicationCertified": False, "presentedPerformanceCertified": False, "hiddenCanvasCertified": False, "originalOperationJournalAvailable": False, "limits": ["No current saved CanvasDocument was available for four-direction gestures; only captured public SVG and selected geometry, not persistence", "Sealed matrix architecture supplies canonical facts only, never claimed as actual current gesture Canvas", "Root lost its in-memory operation journal after AX timeout/reset; no reconstruction as original evidence", "Original truncated raw.json preserved; fullJSON assembled from70captured chunks", "Frame/frameCallback buffers drop4102 each; event/ET buffers drop0; existing validator pan failure preserved", "Laststoredframe298615.7 means pan up/down zoom/toggles lack stored callback samples; null retained", "Atomic trusted drags do not test held-pointer cancel, Escape/blur during gesture or compositor trace", "All pin specs empty; no pin protection certification", "Continuous proxy is first later changed sampled geometry, not causal per-event response or paint", "Same-origin iframe overhead, uncontrolled fonts/hardware and unknown top-level1Hz scheduling", "AI operators/auditors are not real participants or publication reviewers"]}
    save(out / "audit-summary.json", summary)
    outputs = [seal(p) for p in sorted(out.iterdir()) if p.is_file()]
    save(out / "manifest.json", {"schema": "archcanvas-independent-native-audit-manifest/1", "inputsUnchanged": True, "inputs": initial, "outputs": outputs})
    print(json.dumps({"output": str(out), "summary": {k: summary[k] for k in ("inputBytesUnchanged", "reassemblyPassed", "trials", "xmlSnapshotsParsedAndCanonicallyBound", "globalExistingValidatorCompleteBuffers", "eventTiming", "pilotValidSceneTrials")}, "manifest": seal(out / "manifest.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
