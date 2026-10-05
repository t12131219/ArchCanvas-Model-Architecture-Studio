"""Independent public-SVG checker for bounded AI directional gesture captures.

No product, scene, history, renderer, browser or observer imports. This reads
JSON/XML artifacts only and never reconstructs a product document.
"""
from __future__ import annotations

import argparse
import copy
import decimal
import hashlib
import json
import math
import pathlib
import re
import xml.etree.ElementTree as ET

NS = {"s": "http://www.w3.org/2000/svg"}
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
DIRECTIONS = {"right": ("x", 1), "left": ("x", -1), "down": ("y", 1), "up": ("y", -1)}
ROUNDING_TOLERANCE = .051


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def finite(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def ensure(condition, message):
    if not condition:
        raise ValueError(message)


def same_number(a, b, tolerance=1e-6):
    return abs(a - b) <= tolerance


def point_matches(a, b):
    return same_number(a[0], b[0], ROUNDING_TOLERANCE) and same_number(a[1], b[1], ROUNDING_TOLERANCE)


def path_points(path):
    """Parse only the currently captured explicit straight path grammar.

    Unsupported commands remain an error; do not silently invent endpoints.
    """
    tokens = re.findall(r"[A-Za-z]|" + NUMBER, path)
    ensure(re.sub(r"[\s,]", "", path) == "".join(tokens), "Malformed SVG path tokens")
    cursor, index, points = (0., 0.), 0, []
    while index < len(tokens):
        command = tokens[index]
        ensure(command in ("M", "L", "H", "V"), f"Unsupported path command {command}")
        index += 1
        count = 2 if command in ("M", "L") else 1
        ensure(index + count <= len(tokens), "Missing path coordinate")
        values = [float(token) for token in tokens[index:index + count]]
        ensure(all(finite(value) for value in values), "Invalid path coordinate")
        index += count
        cursor = tuple(values) if count == 2 else (values[0], cursor[1]) if command == "H" else (cursor[0], values[0])
        points.append(cursor)
    ensure(len(points) >= 2 and tokens[0] == "M", "Missing complete edge path")
    return points


def svg_snapshot(text):
    root = ET.fromstring(text)
    ensure(root.tag == f"{{{NS['s']}}}svg", "Not an SVG root")
    metadata = root.find("s:metadata", NS)
    ensure(metadata is not None and metadata.text, "Missing SVG metadata")
    facts = json.loads(metadata.text)
    for key in ("documentId", "revision", "sourceDigest", "irDigest", "sourceFacts", "renderedNodes", "renderedBindings"):
        ensure(key in facts, f"Missing metadata {key}")
    ensure(root.get("data-document-id") == facts["documentId"], "Document identity mismatch")
    ensure(isinstance(facts["revision"], int) and not isinstance(facts["revision"], bool) and facts["revision"] >= 0, "Invalid revision scalar")
    ensure(int(root.get("data-revision")) == facts["revision"], "Revision mismatch")
    ensure(all(re.fullmatch(r"[a-f0-9]{64}", facts[key]) for key in ("sourceDigest", "irDigest")), "Invalid source/IR digest")
    viewbox = [float(value) for value in root.get("viewBox", "").split()]
    ensure(len(viewbox) == 4 and all(finite(value) for value in viewbox) and viewbox[2] > 0 and viewbox[3] > 0, "Invalid scene viewBox")
    bodies, nodes, ports, edges, headers = {}, {}, {}, {}, {}
    for group in root.findall(".//s:g[@data-canonical-id]", NS):
        identity = group.get("data-node-id")
        ensure(identity and identity not in bodies, "Duplicate or absent scene node identity")
        main = next((child for child in group if child.tag == f"{{{NS['s']}}}rect" and child.get("stroke-width") is not None), None)
        ensure(main is not None, "Canonical node lacks a main body")
        body = {key: float(main.get(key, "nan")) for key in ("x", "y", "width", "height")}
        ensure(all(finite(value) for value in body.values()) and body["width"] > 0 and body["height"] > 0, "Invalid main body")
        bodies[identity] = body
        nodes[identity] = {"canonicalId": group.get("data-canonical-id"), "label": group.get("aria-label"), "body": body}
        direct_paths = [child for child in group if child.tag == f"{{{NS['s']}}}path"]
        if main.get("stroke-width") == "1.3" and len(direct_paths) == 1:
            points = path_points(direct_paths[0].get("d", ""))
            if len(points) == 2 and points[0][1] == points[1][1] and body["y"] < points[0][1] < body["y"] + body["height"]:
                headers[identity] = {"x": body["x"], "y": body["y"], "width": body["width"], "height": points[0][1] - body["y"]}
    declared_nodes = {node["sceneNodeId"]: node["canonicalNodeId"] for node in facts["renderedNodes"]}
    ensure(len(declared_nodes) == len(facts["renderedNodes"]) and declared_nodes == {identity: node["canonicalId"] for identity, node in nodes.items()}, "Rendered node metadata differs from actual DOM")
    source_fact_ids = {fact["id"] for fact in facts["sourceFacts"]}
    ensure(len(source_fact_ids) == len(facts["sourceFacts"]) and all(identity in source_fact_ids for identity in declared_nodes.values()), "Canonical rendered identity missing from complete sourceFacts")
    for element in root.findall(".//*[@data-port-id]", NS):
        identity = element.get("data-port-id")
        ensure(identity not in ports, "Duplicate SVG port identity")
        circle = element if element.tag == f"{{{NS['s']}}}circle" else next((child for child in element if child.tag == f"{{{NS['s']}}}circle" and child.get("r") == "2.6"), None)
        ensure(circle is not None, "SVG port lacks its visible circle")
        point = (float(circle.get("cx", "nan")), float(circle.get("cy", "nan")))
        ensure(all(finite(value) for value in point), "Invalid visible port coordinate")
        ports[identity] = {"nodeId": element.get("data-node-id"), "point": point}
    binding_records = {binding["sceneEdgeId"]: binding for binding in facts["renderedBindings"]}
    ensure(len(binding_records) == len(facts["renderedBindings"]), "Duplicate rendered binding identity")
    endpoint_findings = []
    for group in root.findall(".//s:g[@data-edge-id]", NS):
        identity = group.get("data-edge-id")
        ensure(identity not in edges and identity in binding_records, "Missing or duplicate actual edge binding")
        path = group.find("s:path", NS)
        ensure(path is not None, "Rendered edge lacks path")
        points = path_points(path.get("d", ""))
        binding = binding_records[identity]
        ensure(group.get("data-tensor-id") == binding["tensorId"], "Actual edge tensor differs from binding")
        owners = {}
        for side, endpoint in (("source", points[0]), ("target", points[-1])):
            expected_port = binding[side]["portId"]
            # The SVG port carries a scene owner and canonical port identity;
            # projected boundaries may have a different visible scene owner.
            candidates = [(portid, port) for portid, port in ports.items() if ":" + expected_port + ":" in portid and portid.endswith(":" + binding["role"])]
            ensure(len(candidates) == 1, f"Ambiguous/missing bound {side} port on {identity}")
            portid, port = candidates[0]
            ensure(point_matches(endpoint, port["point"]), f"Edge endpoint detached from bound {side} port on {identity}")
            owners[side] = port["nodeId"]
            endpoint_findings.append({"edgeId": identity, "side": side, "canonicalPort": expected_port, "scenePort": portid, "endpoint": endpoint, "port": port["point"], "matchedWithinRounding": True})
        edges[identity] = {"path": path.get("d"), "points": points, "binding": binding, "owners": owners, "stroke": path.get("stroke"), "width": path.get("stroke-width"), "dashed": path.get("stroke-dasharray")}
    ensure(set(edges) == set(binding_records), "Rendered edge metadata differs from actual edge DOM")
    normalized = re.sub(r'(?<=data-revision=")\d+(?=")', "<REVISION>", text, count=1)
    metadata_pattern = re.search(r"<metadata>(.*?)</metadata>", normalized, re.S)
    ensure(metadata_pattern, "Expected explicit metadata element for byte comparison")
    replacement = re.sub(r'("revision":)\d+', r'\1"<REVISION>"', metadata_pattern.group(1), count=1)
    # Browser outerHTML embeds metadata JSON literally; XML source exports may
    # encode quotes, so byte normalization supports that exact spelling too.
    if replacement == metadata_pattern.group(1):
        replacement = re.sub(r'(&quot;revision&quot;:)\d+', r'\1&quot;<REVISION>&quot;', replacement, count=1)
    normalized = normalized[:metadata_pattern.start(1)] + replacement + normalized[metadata_pattern.end(1):]
    ensure("<REVISION>" in normalized, "Revision normalization failed")
    return {"svg": text, "normalizedSvg": normalized, "root": root, "metadata": facts, "bounds": viewbox, "nodes": nodes, "bodies": bodies, "ports": ports, "edges": edges, "headers": headers, "endpointChecks": endpoint_findings}


def read_capture(path):
    raw = path.read_bytes()
    if path.suffix == ".svg":
        return {"binding": {"path": str(path), "bytes": len(raw), "sha256": sha(raw)}, "capture": {}, "scene": svg_snapshot(raw.decode())}
    envelope = json.loads(raw)
    value = envelope.get("dom", envelope)
    ensure(isinstance(value, dict), "Capture public DOM must be an object")
    if "paper" in value and "paperTransform" not in value:
        value = dict(value, paperTransform=value["paper"])
    text = value.get("svgMarkup", value.get("svg", value.get("markup")))
    if text is None and isinstance(value.get("scene"), dict):
        text = value["scene"].get("svgMarkup", value["scene"].get("svg"))
    ensure(isinstance(text, str) and text, "Capture has no complete public SVG")
    return {"binding": {"path": str(path), "bytes": len(raw), "sha256": sha(raw)}, "capture": value, "scene": svg_snapshot(text)}


def matrix_of(capture):
    camera = capture.get("camera")
    if isinstance(camera, dict) and isinstance(camera.get("matrix"), dict):
        values = [camera["matrix"].get(key) for key in "abcdef"]
        ensure(all(finite(value) for value in values), "Invalid captured camera matrix")
        return values
    transform = capture.get("paperTransform", capture.get("cssTransform"))
    if transform is None and isinstance(camera, dict):
        transform = camera.get("cssTransform")
    if transform is None:
        return None
    if transform == "none":
        return [1, 0, 0, 1, 0, 0]
    # A capture may expose the public inline style declaration instead of
    # computed CSS; parse only its documented translate/scale spelling.
    if isinstance(transform, str) and "transform:" in transform:
        declaration = re.search(r"(?:^|;)\s*transform:\s*([^;]+)", transform)
        ensure(declaration, "Missing inline paper transform")
        transform = declaration.group(1).strip()
    inline = re.fullmatch(r"translate\(\s*(" + NUMBER + r")px\s*,\s*(" + NUMBER + r")px\s*\)\s+scale\(\s*(" + NUMBER + r")\s*\)", transform)
    if inline:
        x, y, scale = [float(value) for value in inline.groups()]
        ensure(all(finite(value) for value in (x, y, scale)) and scale > 0, "Invalid inline camera transform")
        return [scale, 0, 0, scale, x, y]
    match = re.fullmatch(r"matrix\(([^)]+)\)", transform)
    ensure(match, "Unsupported camera CSS transform")
    values = [float(value.strip()) for value in match.group(1).split(",")]
    ensure(len(values) == 6 and all(finite(value) for value in values), "Invalid camera CSS matrix")
    return values


def semantic_continuity(before, after):
    a, b = before["scene"], after["scene"]
    keys = ["documentId", "sourceDigest", "irDigest", "sourceFactScope", "sourceFacts", "renderedNodes", "renderedBindings"]
    ensure(all(a["metadata"].get(key) == b["metadata"].get(key) for key in keys), "Source/IR/facts/canonical binding continuity failed")
    for name in ("expandedIds", "pinnedIds"):
        va, vb = before["capture"].get(name), after["capture"].get(name)
        if isinstance(va, str):
            va = json.loads(va)
        if isinstance(vb, str):
            vb = json.loads(vb)
        for value in (va, vb):
            ensure(value is None or isinstance(value, list) and all(isinstance(identity, str) for identity in value) and len(value) == len(set(value)), f"Invalid public {name} membership")
        ensure(va == vb, f"Public {name} continuity failed")
    return {"metadataFields": keys, "matched": True, "expandedPinnedEvidencePresent": all(name in before["capture"] and name in after["capture"] for name in ("expandedIds", "pinnedIds"))}


def segment_collision(a, b, box):
    """Whether an axis-aligned open segment crosses the open body interior."""
    x0, y0, x1, y1 = box["x"], box["y"], box["x"] + box["width"], box["y"] + box["height"]
    if same_number(a[0], b[0]):
        return x0 < a[0] < x1 and max(min(a[1], b[1]), y0) < min(max(a[1], b[1]), y1)
    if same_number(a[1], b[1]):
        return y0 < a[1] < y1 and max(min(a[0], b[0]), x0) < min(max(a[0], b[0]), x1)
    raise ValueError("Non-orthogonal segment cannot use rectangular intersection test")


def geometric_findings(scene):
    leaf_ids = {fact["id"] for fact in scene["metadata"]["sourceFacts"] if fact.get("category") != "container" and fact.get("kind") != "Module"}
    bodies = scene["bodies"]
    overlap = []
    for index, aid in enumerate(sorted(bodies)):
        if aid not in leaf_ids:
            continue
        a = bodies[aid]
        for bid in sorted(bodies)[index + 1:]:
            if bid not in leaf_ids:
                continue
            b = bodies[bid]
            width = min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"])
            height = min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"])
            if width > 0 and height > 0:
                overlap.append({"nodes": [aid, bid], "width": width, "height": height, "area": width * height})
    header_intrusions = []
    for cid, header in scene["headers"].items():
        for lid, leaf in bodies.items():
            if lid not in leaf_ids:
                continue
            width = min(header["x"] + header["width"], leaf["x"] + leaf["width"]) - max(header["x"], leaf["x"])
            height = min(header["y"] + header["height"], leaf["y"] + leaf["height"]) - max(header["y"], leaf["y"])
            if width > 0 and height > 0:
                header_intrusions.append({"leafNode": lid, "containerHeader": cid, "width": width, "height": height, "area": width * height})
    body_intrusions = []
    segments = {}
    for identity, edge in scene["edges"].items():
        segments[identity] = list(zip(edge["points"], edge["points"][1:]))
        for nid, body in bodies.items():
            if nid not in leaf_ids or nid in edge["owners"].values():
                continue
            for index, (a, b) in enumerate(segments[identity]):
                if segment_collision(a, b, body):
                    body_intrusions.append({"edgeId": identity, "unrelatedLeafBody": nid, "segmentIndex": index, "segment": [a, b]})
    crossings = []
    for index, aid in enumerate(sorted(segments)):
        for bid in sorted(segments)[index + 1:]:
            # Exact crossings at shared bound owners are intentionally omitted;
            # full pixel readability remains the independent visual role.
            if set(scene["edges"][aid]["owners"].values()) & set(scene["edges"][bid]["owners"].values()):
                continue
            for ia, (a, b) in enumerate(segments[aid]):
                for ib, (c, d) in enumerate(segments[bid]):
                    ah, bh = same_number(a[1], b[1]), same_number(c[1], d[1])
                    if ah == bh:
                        continue
                    h0, h1, v0, v1 = (a, b, c, d) if ah else (c, d, a, b)
                    x, y = v0[0], h0[1]
                    if min(h0[0], h1[0]) < x < max(h0[0], h1[0]) and min(v0[1], v1[1]) < y < max(v0[1], v1[1]):
                        crossings.append({"edges": [aid, bid], "segmentIndexes": [ia, ib], "point": [x, y]})
    bx, by, bw, bh = scene["bounds"]
    outside = [identity for identity, box in bodies.items() if box["x"] < bx - .051 or box["y"] < by - .051 or box["x"] + box["width"] > bx + bw + .051 or box["y"] + box["height"] > by + bh + .051]
    return {"leafBodyOverlaps": overlap, "leafBodiesInContainerHeaderBands": header_intrusions, "edgeIntrusionsIntoUnrelatedLeafBodies": body_intrusions, "properNonsharedOrthogonalCrossings": crossings, "bodiesOutsideViewBox": outside, "aestheticCertified": False,
            "limits": ["Container/descendant containment is excluded by omitting all containers; external container overlaps are not measured by this narrow leaf test.", "Shared-owner edge intersections and collinear route overlaps are excluded, so zero findings is not an absence-of-crossings proof.", "Rectangular/path geometry omits rendered text, stroke thickness, markers, occlusion and human readability."]}


def check_move(case, captures):
    direction, target = case["direction"], case["targetId"]
    ensure(direction in DIRECTIONS, "Unknown movement direction")
    ensure(set(captures) == {"before", "moved", "undo", "redo"}, "Movement requires four complete phases")
    before, moved, undone, redone = [captures[key] for key in ("before", "moved", "undo", "redo")]
    facts = {fact["id"]: fact for fact in before["scene"]["metadata"]["sourceFacts"]}
    ensure(target in facts and facts[target].get("kind") == "Linear", "Predeclared target must be a canonical Linear")
    ensure(target in before["scene"]["nodes"] and target in moved["scene"]["nodes"], "Target absent from visible node DOM")
    continuity = [semantic_continuity(before, phase) for phase in (moved, undone, redone)]
    a, b = before["scene"]["bodies"][target], moved["scene"]["bodies"][target]
    delta = {key: b[key] - a[key] for key in ("x", "y")}
    axis, sign = DIRECTIONS[direction]
    orthogonal = "y" if axis == "x" else "x"
    ensure(delta[axis] * sign > 0 and same_number(delta[orthogonal], 0), "Actual terminal direction differs from declared axis/sign")
    ensure(a["width"] == b["width"] and a["height"] == b["height"], "Target dimensions unexpectedly changed")
    other_leaf_bodies = {identity: before["scene"]["bodies"][identity] for identity, fact in facts.items() if identity != target and identity in before["scene"]["bodies"] and fact.get("category") != "container" and fact.get("kind") != "Module"}
    ensure(all(moved["scene"]["bodies"][identity] == body for identity, body in other_leaf_bodies.items()), "Movement unexpectedly changed another visible leaf body")
    other_body_changes = {identity: {"before": body, "after": moved["scene"]["bodies"][identity]} for identity, body in before["scene"]["bodies"].items() if identity != target and moved["scene"]["bodies"][identity] != body}
    before_fact, moved_fact = before["scene"]["metadata"], moved["scene"]["metadata"]
    ensure(moved_fact["revision"] == before_fact["revision"] + 1, "Movement is not one committed revision")
    ensure(undone["scene"]["metadata"]["revision"] == moved_fact["revision"] + 1 and redone["scene"]["metadata"]["revision"] == undone["scene"]["metadata"]["revision"] + 1, "Undo/redo is not one revision each")
    ensure(undone["scene"]["normalizedSvg"] == before["scene"]["normalizedSvg"], "Undo did not restore full SVG except revision")
    ensure(redone["scene"]["normalizedSvg"] == moved["scene"]["normalizedSvg"], "Redo did not restore full moved SVG except revision")
    expected = None
    if case.get("input"):
        interaction = case["input"]
        matrix = matrix_of(before["capture"])
        ensure(matrix is not None and same_number(matrix[1], 0) and same_number(matrix[2], 0) and same_number(matrix[0], matrix[3]) and matrix[0] > 0, "Cannot independently compute canvas delta without uniform camera scale")
        ensure(len(interaction["from"]) == len(interaction["to"]) == 2 and all(finite(value) for value in interaction["from"] + interaction["to"]), "Invalid input endpoints")
        # Typed grid snapping uses JS Math.round; floor(x+.5) preserves negative
        # tie behavior rather than Python's half-to-even round().
        expected = {key: math.floor(((interaction["to"][index] - interaction["from"][index]) / matrix[0] / 4) + .5) * 4 for index, key in enumerate(("x", "y"))}
        ensure(all(same_number(delta[key], expected[key], .1) for key in ("x", "y")), "Terminal canvas position differs from independently snapped native endpoint")
    return {"status": "passed-public-SVG-consistency", "direction": direction, "targetId": target, "deltaCanvas": delta, "expectedSnappedCanvasDelta": expected, "otherVisibleLeafBodiesUnchanged": True, "otherBodyChanges": other_body_changes, "canonicalContinuity": continuity, "undoFullSvgExceptRevision": True, "redoFullSvgExceptRevision": True,
            "phases": {name: {"inputBinding": capture["binding"], "revision": capture["scene"]["metadata"]["revision"], "bounds": capture["scene"]["bounds"], "endpointChecks": capture["scene"]["endpointChecks"], "geometricFindings": geometric_findings(capture["scene"])} for name, capture in captures.items()}, "hiddenHistoryCertified": False, "presentedFramesCertified": False, "humanCertified": False}


def check_pan(case, captures):
    ensure(case["direction"] in DIRECTIONS and set(captures) == {"before", "panned", "reversed"}, "Pan requires three complete phases")
    a, b, c = [captures[key] for key in ("before", "panned", "reversed")]
    matrices = [matrix_of(item["capture"]) for item in (a, b, c)]
    ensure(all(matrix is not None for matrix in matrices), "Pan camera matrices missing")
    m0, m1, m2 = matrices
    ensure(a["scene"]["svg"] == b["scene"]["svg"] == c["scene"]["svg"], "Pan changed exact SVG/document revision")
    ensure(m0[:4] == m1[:4] == m2[:4], "Pan changed camera scale/skew")
    axis, sign = DIRECTIONS[case["direction"]]
    delta = {"x": m1[4] - m0[4], "y": m1[5] - m0[5]}
    ensure(delta[axis] * sign > 0 and same_number(delta["y" if axis == "x" else "x"], 0, .001), "Pan direction differs from declared CSS axis/sign")
    ensure(all(same_number(x, y, .001) for x, y in zip(m0, m2)), "Opposite pan did not restore paper camera")
    if case.get("input"):
        expected = {key: case["input"]["to"][index] - case["input"]["from"][index] for index, key in enumerate(("x", "y"))}
        ensure(all(same_number(delta[key], expected[key], .001) for key in ("x", "y")), "Pan terminal translation differs from native endpoint")
    return {"status": "passed-public-camera-consistency", "direction": case["direction"], "deltaCssPx": delta, "exactSvgUnchanged": True, "reversedPaperMatrixRestored": True, "history": "Camera navigation is not a CanvasDocument history operation", "inputBindings": [item["binding"] for item in (a, b, c)], "humanCertified": False, "presentedFramesCertified": False}


def check_export(case, captures):
    ensure(set(captures) == {"interactive", "exported"}, "Export requires interactive and actually exported SVG")
    interactive, exported = captures["interactive"], captures["exported"]
    a, b = interactive["scene"], exported["scene"]
    ensure(a["metadata"] == b["metadata"], "Actual export metadata does not equal current interactive scene")
    ensure(a["bounds"] == b["bounds"] and a["root"].get("aria-label") == b["root"].get("aria-label"), "Actual export viewBox/label differs from current scene")
    dimension_records = []
    for key, metadata_key in (("width", "widthMm"), ("height", "heightMm")):
        canonical = a["metadata"].get(metadata_key)
        ensure(finite(canonical) and canonical > 0, "Missing/invalid canonical physical dimension")
        values = []
        for label, scene in (("interactive", a), ("exported", b)):
            spelling = scene["root"].get(key, "")
            match = re.fullmatch(r"(\d+(?:\.\d+)?)mm", spelling)
            ensure(match, "Physical SVG dimension must be explicit decimal mm")
            digits = len(match.group(1).split(".")[1]) if "." in match.group(1) else 0
            actual = decimal.Decimal(match.group(1))
            tolerance = decimal.Decimal(5) * (decimal.Decimal(10) ** (-digits - 1))
            error = abs(actual - decimal.Decimal(str(canonical)))
            ensure(error <= tolerance + decimal.Decimal("1e-12"), "Physical SVG dimension differs beyond its declared decimal precision")
            values.append({"phase": label, "spelling": spelling, "valueMm": float(actual), "errorToMetadataMm": float(error), "halfDecimalUnitMm": float(tolerance)})
        dimension_records.append({"dimension": key, "metadataMm": canonical, "rootSpellingsExact": values[0]["spelling"] == values[1]["spelling"], "absoluteRootDeltaMm": abs(values[0]["valueMm"] - values[1]["valueMm"]), "values": values})
    ensure(a["nodes"] == b["nodes"] and a["ports"] == b["ports"] and a["edges"] == b["edges"], "Actual export objects/ports/routing differ from current interactive scene")
    # The byte equality is unsuitable here: actual publication SVG deliberately
    # omits interactive buttons/tabindex and uses circle ports instead of groups.
    # Compare all public noninteractive appearance subtrees in addition to facts.
    def publication_tree(scene):
        root = copy.deepcopy(scene["root"])
        # Only dimensions independently checked above may use common metadata
        # spelling for appearance comparison; actual root values remain reported.
        for key, metadata_key in (("width", "widthMm"), ("height", "heightMm")):
            root.set(key, str(scene["metadata"][metadata_key]) + "mm")
        source_facts = {fact["id"]: fact for fact in scene["metadata"]["sourceFacts"]}
        for node in root.findall(".//s:g[@data-canonical-id]", NS):
            node.attrib.pop("tabindex", None); node.attrib.pop("role", None)
            controls = node.findall("s:g[@data-expand-id]", NS)
            body = scene["bodies"][node.get("data-node-id")]
            fact = source_facts.get(node.get("data-canonical-id"), {})
            repeat = fact.get("repeat")
            if repeat and any(control.get("aria-label", "").startswith("Collapse ") for control in controls):
                for badge in node.findall("s:text", NS):
                    if badge.get("text-anchor") == "end" and badge.get("font-size") == "10" and badge.text == f'{repeat["count"]}× · {repeat["sharing"]}':
                        ensure(same_number(float(badge.get("x")), body["x"] + body["width"] - 47, .011), "Unexpected interactive repeat badge coordinate")
                        badge.set("x", str(int(body["x"] + body["width"] - 17)) if float(body["x"] + body["width"] - 17).is_integer() else str(body["x"] + body["width"] - 17))
            for control in controls:
                node.remove(control)
        for parent in root.iter():
            for element in list(parent):
                if element.tag != f"{{{NS['s']}}}g" or not element.get("data-port-id"):
                    continue
                circle = next(child for child in element if child.tag == f"{{{NS['s']}}}circle" and child.get("r") == "2.6")
                replacement = copy.deepcopy(circle)
                replacement.set("data-port-id", element.get("data-port-id"))
                replacement.set("data-node-id", element.get("data-node-id"))
                title = element.find("s:title", NS)
                if title is not None:
                    title_copy = copy.deepcopy(title)
                    if title_copy.text and title_copy.text.endswith(" · 拖向来源输出端口以创建改接提案"):
                        title_copy.text = title_copy.text.removesuffix(" · 拖向来源输出端口以创建改接提案")
                    replacement.append(title_copy)
                parent.insert(list(parent).index(element), replacement); parent.remove(element)
        def structure(element):
            text = element.text if element.text and element.text.strip() else None
            return (element.tag, tuple(sorted(element.attrib.items())), text, tuple(structure(child) for child in element))
        return structure(root)
    ensure(publication_tree(a) == publication_tree(b), "Publication appearance tree differs beyond documented interaction decorations")
    return {"status": "passed-actual-export-consistency", "caseId": case["id"], "metadataExact": True, "viewBoxExact": True, "physicalDimensionsConsistentWithMetadataDecimalPrecision": True, "rootPhysicalDimensionSpellingsExact": all(record["rootSpellingsExact"] for record in dimension_records), "physicalDimensionRounding": dimension_records, "nodesPortsEdgesExact": True, "publicationAppearanceExactExceptInteractiveControls": True, "allowedInteractionDifferences": ["independently checked root physical dimension decimal precision", "node tabindex/role", "expand/collapse controls", "port group/hit circle and drag instruction title", "expanded repeat count badge shifts 30px to occupy the removed control space"], "inputBindings": [interactive["binding"], exported["binding"]], "actualExportTransportCertified": False, "actualExportTransportReceiptDeclared": bool(case.get("actualExportReceipt")), "actualExportReceipt": case.get("actualExportReceipt"), "transportScope": "This checker compares supplied artifact bytes; actual browser export/download transport remains a separate receipt audit", "humanCertified": False, "publicationQualityCertified": False}


def run(journal_path, output_path):
    journal = json.loads(journal_path.read_text())
    ensure(journal.get("schema") == "archcanvas-ai-directional-journal/1" and isinstance(journal.get("cases"), list), "Unsupported directional journal")
    results, issues, targets = [], [], set()
    for case in journal["cases"]:
        try:
            captures = {name: read_capture((journal_path.parent / path).resolve()) for name, path in case["captures"].items()}
            result = check_move(case, captures) if case["kind"] == "move" else check_pan(case, captures) if case["kind"] == "pan" else check_export(case, captures) if case["kind"] == "export" else None
            ensure(result is not None, "Unknown case kind")
            result["caseId"] = case["id"]
            results.append(result)
            if case["kind"] == "move":
                targets.add(case["targetId"])
        except (OSError, ValueError, KeyError, ET.ParseError, TypeError) as error:
            issues.append({"caseId": case.get("id"), "message": str(error)})
    move_directions = {result["direction"] for result in results if result["status"] == "passed-public-SVG-consistency"}
    pan_directions = {result["direction"] for result in results if result["status"] == "passed-public-camera-consistency"}
    full = move_directions == set(DIRECTIONS) and len(targets) == 1 and not issues
    result = {"schema": "archcanvas-ai-directional-audit/1", "status": "all-four-movements-consistent" if full else "incomplete-or-failed", "journalBinding": {"path": str(journal_path), "sha256": sha(journal_path.read_bytes()), "bytes": journal_path.stat().st_size}, "checkerBinding": {"path": __file__, "sha256": sha(pathlib.Path(__file__).read_bytes())}, "sameTargetAcrossFourMoves": len(targets) == 1, "passedMoveDirections": sorted(move_directions), "passedPanDirections": sorted(pan_directions), "fourPanDirectionsComplete": pan_directions == set(DIRECTIONS), "passedActualExportCases": sum(case["status"] == "passed-actual-export-consistency" for case in results), "issues": issues, "cases": results, "humanParticipants": 0, "humanCertified": False, "publicationCertified": False, "presentedPerformanceCertified": False, "trustedInputCertifiedBySvg": False}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("journal", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    result = run(args.journal.resolve(), args.output.resolve())
    print(json.dumps({key: result[key] for key in ("status", "passedMoveDirections", "passedPanDirections", "issues")}, indent=2))
    raise SystemExit(0 if result["status"] == "all-four-movements-consistent" else 1)
