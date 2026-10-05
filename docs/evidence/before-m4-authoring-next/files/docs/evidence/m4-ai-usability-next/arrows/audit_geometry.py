#!/usr/bin/env python3
"""Independent axis-aligned geometry observations from actual saved browser SVG.

This does not call the product Scene/router or operate DOM. It records geometry
risks, not publication/human acceptance, and tests its primitives on deliberate
counterexamples before inspecting saved artifacts.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent


def local(tag):
    return tag.rsplit("}", 1)[-1]


def points(path):
    """Parse only explicit M/L/H/V commands; unsupported data fails closed."""
    tokens = re.findall(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?", path)
    index, result = 0, []
    while index < len(tokens):
        command = tokens[index]
        index += 1
        if command in ("M", "L"):
            x, y = float(tokens[index]), float(tokens[index + 1])
            index += 2
        elif command == "H" and result:
            x, y = float(tokens[index]), result[-1][1]
            index += 1
        elif command == "V" and result:
            x, y = result[-1][0], float(tokens[index])
            index += 1
        else:
            raise ValueError("unsupported route command: " + command)
        if not result or result[-1] != (x, y):
            result.append((x, y))
    return result


def segments(path_points):
    return list(zip(path_points, path_points[1:]))


def crosses_interior(segment, box, margin=2):
    (ax, ay), (bx, by) = segment
    left, top, right, bottom = box
    left, top, right, bottom = left + margin, top + margin, right - margin, bottom - margin
    if ax == bx:
        return left < ax < right and max(min(ay, by), top) < min(max(ay, by), bottom)
    if ay == by:
        return top < ay < bottom and max(min(ax, bx), left) < min(max(ax, bx), right)
    raise ValueError("diagonal route not covered")


def proper_crossing(first, second):
    (ax, ay), (bx, by) = first
    (cx, cy), (dx, dy) = second
    if ax == bx and cy == dy:
        if min(cx, dx) < ax < max(cx, dx) and min(ay, by) < cy < max(ay, by):
            return (ax, cy)
    if ay == by and cx == dx:
        if min(ax, bx) < cx < max(ax, bx) and min(cy, dy) < ay < max(cy, dy):
            return (cx, ay)
    return None


def overlap(first, second):
    x1, y1, x2, y2 = first
    a1, b1, a2, b2 = second
    width, height = min(x2, a2) - max(x1, a1), min(y2, b2) - max(y1, b1)
    return width * height if width > 0 and height > 0 else 0


def same_point(first, second, tolerance=.15):
    return abs(first[0] - second[0]) <= tolerance and abs(first[1] - second[1]) <= tolerance


def primitive_counterexamples():
    assert points("M 0 0 V 0 H 10 V 10") == [(0, 0), (10, 0), (10, 10)]
    assert crosses_interior(((0, 5), (20, 5)), (4, 0, 16, 10))
    assert not crosses_interior(((0, 0), (20, 0)), (4, 0, 16, 10))
    assert not crosses_interior(((0, 5), (3, 5)), (4, 0, 16, 10))
    assert proper_crossing(((0, 5), (20, 5)), ((10, 0), (10, 10))) == (10, 5)
    assert proper_crossing(((0, 5), (20, 5)), ((20, 0), (20, 10))) is None
    assert overlap((0, 0, 10, 10), (5, 5, 15, 15)) == 25
    assert overlap((0, 0, 10, 10), (10, 0, 20, 10)) == 0
    try:
        points("M 0 0 C 1 1 2 2 3 3")
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported bezier command silently accepted")
    return {"passed": True, "checks": 9,
            "scope": "zero-length cleanup, body penetration vs border/outside, proper crossing vs shared endpoint, body overlap vs touch, unsupported-command rejection"}


def inspect(svg_path, canvas, case_id, screenshot=None):
    raw = svg_path.read_bytes()
    svg = ET.fromstring(raw)
    metadata = json.loads(next(element.text for element in svg if local(element.tag) == "metadata"))
    architecture = canvas["architecture"]
    if metadata["sourceDigest"] != architecture["sourceDigest"] or metadata["irDigest"] != architecture["irDigest"]:
        raise ValueError("saved SVG source/IR binding differs from canonical architecture")
    canonical = {node["id"]: node for node in architecture["nodes"]}
    marker_ids = {element.get("id") for element in svg.iter() if local(element.tag) == "marker"}
    bodies, labels, port_positions, rendered_edges = {}, {}, {}, {}
    for element in svg.iter():
        if local(element.tag) != "g":
            continue
        node_id = element.get("data-node-id")
        port_id = element.get("data-port-id")
        if node_id and element.get("data-canonical-id"):
            rects = [child for child in element if local(child.tag) == "rect" and child.get("opacity") is None]
            if len(rects) != 1:
                raise ValueError("not exactly one primary body rect for " + node_id)
            body = rects[0]
            x, y, width, height = (float(body.get(field)) for field in ("x", "y", "width", "height"))
            bodies[node_id], labels[node_id] = (x, y, x + width, y + height), element.get("aria-label")
        if node_id and port_id:
            circles = [child for child in element if local(child.tag) == "circle"]
            dots = [circle for circle in circles if circle.get("fill") != "transparent"]
            if len(dots) == 1:
                port_positions[(node_id, port_id)] = (float(dots[0].get("cx")), float(dots[0].get("cy")))
        edge_id = element.get("data-edge-id")
        if edge_id:
            paths = [child for child in element if local(child.tag) == "path"]
            if len(paths) != 1:
                raise ValueError("not exactly one route path for " + edge_id)
            rendered_edges[edge_id] = {"points": points(paths[0].get("d")), "path": paths[0].get("d"),
                                       "marker": paths[0].get("marker-end"), "tensorId": element.get("data-tensor-id")}
    binding_records = {binding["sceneEdgeId"]: binding for binding in metadata["renderedBindings"]}
    if set(binding_records) != set(rendered_edges):
        raise ValueError("rendered edge/metadata inventory differs")

    def ancestors(node_id):
        result = set()
        while canonical[node_id].get("parentId"):
            node_id = canonical[node_id]["parentId"]
            result.add(node_id)
        return result

    def visible(node_id):
        while node_id not in bodies:
            node_id = canonical[node_id].get("parentId")
            if node_id is None:
                raise ValueError("canonical endpoint has no visible representative")
        return node_id

    unrelated_penetrations, endpoint_defects, redundant_vertices = [], [], []
    edge_effective = {}
    for edge_id, rendered in rendered_edges.items():
        binding = binding_records[edge_id]
        source_id, target_id = binding["source"]["nodeId"], binding["target"]["nodeId"]
        source_visible, target_visible = visible(source_id), visible(target_id)
        edge_effective[edge_id] = source_visible, target_visible
        excluded = {source_visible, target_visible} | ancestors(source_id) | ancestors(target_id)
        for node_id, box in bodies.items():
            if node_id in excluded:
                continue
            hits = [index for index, segment in enumerate(segments(rendered["points"])) if crosses_interior(segment, box)]
            if hits:
                unrelated_penetrations.append({"edgeId": edge_id, "canonicalEdgeIds": binding["canonicalEdgeIds"],
                                               "role": binding["role"], "nodeId": node_id, "nodeLabel": labels[node_id],
                                               "segments": hits, "path": rendered["path"]})
        for direction, effective, canonical_binding, endpoint in (
                ("source", source_visible, binding["source"], rendered["points"][0]),
                ("target", target_visible, binding["target"], rendered["points"][-1])):
            prefix = canonical_binding["nodeId"] + ":" + canonical_binding["portId"] + ":"
            positions = [point for (owner, port_id), point in port_positions.items() if owner == effective and port_id.startswith(prefix)]
            if not positions or not any(same_point(endpoint, point) for point in positions):
                endpoint_defects.append({"edgeId": edge_id, "direction": direction, "effectiveNodeId": effective,
                                         "canonicalBinding": canonical_binding, "endpoint": endpoint, "candidateDots": positions})
        path_points = rendered["points"]
        for index in range(1, len(path_points) - 1):
            before, here, after = path_points[index - 1:index + 2]
            if before[0] == here[0] == after[0] or before[1] == here[1] == after[1]:
                redundant_vertices.append({"edgeId": edge_id, "vertex": index, "point": here})
        if not rendered["marker"]:
            endpoint_defects.append({"edgeId": edge_id, "reason": "missing marker-end"})
        elif rendered["marker"].removeprefix("url(#").removesuffix(")") not in marker_ids:
            endpoint_defects.append({"edgeId": edge_id, "reason": "marker-end has no saved marker definition"})
    unrelated_overlap = []
    body_items = list(bodies.items())
    for index, (left_id, left_box) in enumerate(body_items):
        for right_id, right_box in body_items[index + 1:]:
            if left_id in ancestors(right_id) or right_id in ancestors(left_id):
                continue
            area = overlap(left_box, right_box)
            if area > .15:
                unrelated_overlap.append({"firstNodeId": left_id, "firstLabel": labels[left_id],
                                          "secondNodeId": right_id, "secondLabel": labels[right_id], "overlapArea": area})
    crossings = []
    edge_items = list(rendered_edges.items())
    for index, (left_id, left) in enumerate(edge_items):
        for right_id, right in edge_items[index + 1:]:
            if left["tensorId"] == right["tensorId"]:
                continue  # Same producer fanout may intentionally share a lane.
            found = set()
            for first in segments(left["points"]):
                for second in segments(right["points"]):
                    crossing = proper_crossing(first, second)
                    if crossing:
                        found.add(crossing)
            for crossing in sorted(found):
                crossings.append({"firstEdgeId": left_id, "secondEdgeId": right_id, "point": crossing,
                                  "firstRole": binding_records[left_id]["role"], "secondRole": binding_records[right_id]["role"]})
    result = {"caseId": case_id, "svg": str(svg_path.relative_to(ROOT)), "svgSha256": hashlib.sha256(raw).hexdigest(),
              "documentId": metadata["documentId"], "revision": metadata["revision"],
              "nodeCount": len(bodies), "edgeCount": len(rendered_edges), "portDots": len(port_positions),
              "endpointDefects": endpoint_defects, "unrelatedBodyPenetrations": unrelated_penetrations,
              "unrelatedBodyOverlaps": unrelated_overlap, "properCrossingsAcrossDifferentTensors": crossings,
              "redundantCollinearVertices": redundant_vertices,
              "effectiveBendCountDistribution": dict(Counter(max(0, len(value["points"]) - 2) for value in rendered_edges.values()))}
    if screenshot:
        result["screenshot"] = str(screenshot.relative_to(ROOT))
        result["screenshotSha256"] = hashlib.sha256(screenshot.read_bytes()).hexdigest()
    return result


def main():
    matrix_root = ROOT / "docs/evidence/browser-visual-matrix-boundary-final"
    manifest = json.loads((matrix_root / "manifest.json").read_text())
    results = []
    for capture in manifest["captures"]:
        paths = {key: matrix_root / value["path"] for key, value in capture["files"].items()}
        for key in ("browserScene", "canvas", "screenshot"):
            if hashlib.sha256(paths[key].read_bytes()).hexdigest() != capture["files"][key]["sha256"]:
                raise ValueError("matrix source binding changed: " + capture["caseId"] + ":" + key)
        results.append(inspect(paths["browserScene"], json.loads(paths["canvas"].read_text()), capture["caseId"], paths["screenshot"]))
    output = {"schemaVersion": 1, "scope": "AI independent static geometry observations from 39 previously actual browser-captured SVGs on frozen Cr_xKW9U build; no new UI interactions or human certification",
              "humanAcceptanceCertified": False, "primitiveCounterexamples": primitive_counterexamples(),
              "manifest": str((matrix_root / "manifest.json").relative_to(ROOT)),
              "manifestSha256": hashlib.sha256((matrix_root / "manifest.json").read_bytes()).hexdigest(), "cases": results,
              "limitations": ["Route-body intersection is geometric risk; source-backed residual/mask/memory crossings may be unavoidable or intentional.",
                              "Ancestor container interiors and same-producer fanout crossings are excluded.",
                              "Body intersections use a 2 SVG-unit inset; tiny tangent contacts and font/pixel occlusion are not certified.",
                              "Endpoint comparison uses saved port dots; cannot establish presented frame timing or physical readability.",
                              "Cases are the previously captured same frozen build; four-direction move evidence will be independently appended when available."]}
    (OUT / "matrix-geometry.json").write_text(json.dumps(output,ensure_ascii=False,indent=2) + "\n")
    print(json.dumps({"cases": len(results), "endpointDefects": sum(len(case["endpointDefects"]) for case in results),
                      "bodyPenetrations": sum(len(case["unrelatedBodyPenetrations"]) for case in results),
                      "overlaps": sum(len(case["unrelatedBodyOverlaps"]) for case in results),
                      "crossings": sum(len(case["properCrossingsAcrossDifferentTensors"]) for case in results)}, indent=2))


if __name__ == "__main__":
    main()
