#!/usr/bin/env python3
"""Independent, read-only geometry diagnosis of freshly rendered formal scenes.

Uses only serialized Scene coordinates. It imports no production router,
intersection helper, parser, typography helper, or old geometry oracle.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUTPUT = Path(__file__).resolve().parent
EPS = 1e-6


def binding(path: Path):
    raw = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def parse(path: str):
    tokens = re.findall(r"[MLHV]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?", path)
    points, index = [], 0
    while index < len(tokens):
        command = tokens[index]
        index += 1
        if command in ("M", "L"):
            point = (float(tokens[index]), float(tokens[index + 1]))
            index += 2
        elif command == "H":
            point = (float(tokens[index]), points[-1][1])
            index += 1
        elif command == "V":
            point = (points[-1][0], float(tokens[index]))
            index += 1
        else:
            raise ValueError(f"unsupported public route command {command}")
        if not points or point != points[-1]:
            while len(points) >= 2:
                a, b = points[-2:]
                forward_v = a[0] == b[0] == point[0] and (b[1] - a[1]) * (point[1] - b[1]) >= 0
                forward_h = a[1] == b[1] == point[1] and (b[0] - a[0]) * (point[0] - b[0]) >= 0
                if not (forward_v or forward_h):
                    break
                points.pop()
            points.append(point)
    return points


def segments(points):
    return list(zip(points, points[1:]))


def length(points):
    return sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in segments(points))


def reversals(points):
    def direction(a, b):
        return ((b[0] > a[0]) - (b[0] < a[0]), (b[1] > a[1]) - (b[1] < a[1]))
    return sum(direction(a, b)[0] * direction(b, c)[0] + direction(a, b)[1] * direction(b, c)[1] < 0
               for a, b, c in zip(points, points[1:], points[2:]))


def pair(first, second):
    strict, contact, intervals = set(), set(), {}
    endpoints = {first[0], first[-1], second[0], second[-1]}
    for a, b in segments(first):
        for c, d in segments(second):
            av, cv = a[0] == b[0], c[0] == d[0]
            if av != cv:
                va, vb, ha, hb = (a, b, c, d) if av else (c, d, a, b)
                x, y = va[0], ha[1]
                xmin, xmax = sorted((ha[0], hb[0]))
                ymin, ymax = sorted((va[1], vb[1]))
                if xmin + EPS < x < xmax - EPS and ymin + EPS < y < ymax - EPS:
                    strict.add((x, y))
                if xmin - EPS <= x <= xmax + EPS and ymin - EPS <= y <= ymax + EPS and (x, y) not in endpoints:
                    contact.add((x, y))
            elif abs((a[0] if av else a[1]) - (c[0] if av else c[1])) < EPS:
                low = max(min(a[1] if av else a[0], b[1] if av else b[0]), min(c[1] if av else c[0], d[1] if av else d[0]))
                high = min(max(a[1] if av else a[0], b[1] if av else b[0]), max(c[1] if av else c[0], d[1] if av else d[0]))
                if high - low > EPS:
                    intervals.setdefault(("v" if av else "h", a[0] if av else a[1]), []).append((low, high))
    overlap = 0
    for entries in intervals.values():
        entries.sort()
        low, high = entries[0]
        for next_low, next_high in entries[1:]:
            if next_low <= high:
                high = max(high, next_high)
            else:
                overlap += high - low
                low, high = next_low, next_high
        overlap += high - low
    return {"strictCrossingPoints": sorted(strict), "interiorContactPoints": sorted(contact), "overlapLength": overlap}


def rects(node):
    # Nominal rectangles conservatively include rounded corners. Repeat plates
    # are independently taken from their renderer's public +7/+3.5 drawing.
    offsets = [0, 7, 3.5] if node.get("repeat") and not node["expanded"] else [0]
    return [(node["x"] + o, node["y"] + o, node["x"] + node["width"] + o, node["y"] + node["height"] + o) for o in offsets]


def hit_segment(segment, rectangle):
    (x, y), (u, v) = segment
    left, top, right, bottom = rectangle
    if x == u:
        return left + EPS < x < right - EPS and max(min(y, v), top + EPS) < min(max(y, v), bottom - EPS)
    assert y == v, "public route was not orthogonal"
    return top + EPS < y < bottom - EPS and max(min(x, u), left + EPS) < min(max(x, u), right - EPS)


def obstacles(scene, edge):
    by_id = {n["id"]: n for n in scene["nodes"]}
    ancestors = set()
    for endpoint in (edge["sourceId"], edge["targetId"]):
        parent = by_id[endpoint].get("parentId")
        while parent:
            ancestors.add(parent)
            parent = by_id[parent].get("parentId")
    result = []
    for node in scene["nodes"]:
        if node["id"] in ancestors:
            if node["expanded"]:
                result.append((node["id"], "ancestor-header", (node["x"], node["y"], node["x"] + node["width"], node["y"] + node["headerHeight"])))
        else:
            result.extend((node["id"], "card", r) for r in rects(node))
    return result


def blocked(points, obs):
    return sorted({(node_id, kind) for node_id, kind, rect in obs if any(hit_segment(segment, rect) for segment in segments(points))})


def anchor_hits(scene, edge):
    if not edge.get("label"):
        return []
    x, y = edge["labelX"], edge["labelY"]
    # Exact label baseline anchor only, never an inferred font bounding box.
    # Any full text collision requires actual browser getBBox / pixel review.
    return sorted({(node["id"], "card" if not node["expanded"] else "header") for node in scene["nodes"]
                   if any(l + EPS < x < r - EPS and t + EPS < y < b - EPS
                          for l, t, r, b in ([(node["x"], node["y"], node["x"] + node["width"], node["y"] + node["headerHeight"])]
                                            if node["expanded"] else rects(node)))})


def safe_shortcuts(scene, edges, routes):
    output = []
    for index, (edge, original) in enumerate(zip(edges, routes)):
        if reversals(original):
            continue
        original_bends, original_length = max(0, len(original) - 2), length(original)
        if original_bends == 0:
            continue
        obs = obstacles(scene, edge)
        if blocked(original, obs):
            continue
        start, end = original[0], original[-1]
        a, b = original[1], original[-2]
        ds = ((a[0] > start[0]) - (a[0] < start[0]), (a[1] > start[1]) - (a[1] < start[1]))
        de = ((b[0] > end[0]) - (b[0] < end[0]), (b[1] > end[1]) - (b[1] < end[1]))
        xs = {p[0] + d for p in original for d in (0, -8, 8, -16, 16)}
        ys = {p[1] + d for p in original for d in (0, -8, 8, -16, 16)}
        for _, _, (left, top, right, bottom) in obs:
            for delta in (6, 14, 22):
                xs.update((left - delta, right + delta))
                ys.update((top - delta, bottom + delta))
        # First test direct V-H-V / H-V-H shortcuts. Then preserve exact normal
        # stubs and try one obstacle side corridor. This is a finite audit probe,
        # never installed into the product and not a global optimality claim.
        candidates = []
        for y in sorted(ys):
            candidates.append([start, (start[0], y), (end[0], y), end])
        for x in sorted(xs):
            candidates.append([start, (x, start[1]), (x, end[1]), end])
        for stub in (6, 13, 14, 22):
            s = (start[0] + ds[0] * stub, start[1] + ds[1] * stub)
            t = (end[0] + de[0] * stub, end[1] + de[1] * stub)
            for x in sorted(xs):
                candidates.append([start, s, (x, s[1]), (x, t[1]), t, end])
            for y in sorted(ys):
                candidates.append([start, s, (s[0], y), (t[0], y), t, end])
        old_pairs = [None if index == j else pair(original, route) for j, route in enumerate(routes)]
        best = None
        seen = set()
        for candidate in candidates:
            candidate = parse(" ".join(f"{'M' if n == 0 else 'L'} {p[0]} {p[1]}" for n, p in enumerate(candidate)))
            key = tuple(candidate)
            if key in seen:
                continue
            seen.add(key)
            if len(candidate) < 2 or reversals(candidate) or len(candidate) > len(original) or length(candidate) >= original_length - EPS:
                continue
            ca, cb = candidate[1], candidate[-2]
            candidate_ds = ((ca[0] > start[0]) - (ca[0] < start[0]), (ca[1] > start[1]) - (ca[1] < start[1]))
            candidate_de = ((cb[0] > end[0]) - (cb[0] < end[0]), (cb[1] > end[1]) - (cb[1] < end[1]))
            if candidate_ds != ds or candidate_de != de or blocked(candidate, obs):
                continue
            pair_ok = True
            for j, route in enumerate(routes):
                if index == j:
                    continue
                old, current = old_pairs[j], pair(candidate, route)
                if len(current["strictCrossingPoints"]) > len(old["strictCrossingPoints"]) or len(current["interiorContactPoints"]) > len(old["interiorContactPoints"]) or current["overlapLength"] > old["overlapLength"] + EPS:
                    pair_ok = False
                    break
            if not pair_ok:
                continue
            score = length(candidate) + max(0, len(candidate) - 2) * 18
            if best is None or score < best[0]:
                best = (score, candidate)
        if best:
            points = best[1]
            output.append({"edgeId": edge["id"], "role": edge["role"], "tensorId": edge.get("tensorId"), "sourceId": edge["sourceId"], "targetId": edge["targetId"],
                           "originalPath": edge["path"], "candidatePoints": points, "originalLength": original_length, "candidateLength": length(points),
                           "originalBends": original_bends, "candidateBends": max(0, len(points) - 2), "pairwiseAllTensorNoRegression": True,
                           "obstacleSafeNominalRectangles": True, "immutableEndpointsAndNormals": True})
    return output


def audit(scene):
    edges = scene["edges"]
    routes = [parse(e["path"]) for e in edges]
    all_pairs = []
    for i, first in enumerate(edges):
        for j in range(i + 1, len(edges)):
            second = edges[j]
            result = pair(routes[i], routes[j])
            if result["strictCrossingPoints"] or result["interiorContactPoints"] or result["overlapLength"]:
                all_pairs.append({"first": first["id"], "second": second["id"], "roles": [first["role"], second["role"]],
                                  "sameTensor": first.get("tensorId") is not None and first.get("tensorId") == second.get("tensorId"), **result})
    distinct = [p for p in all_pairs if not p["sameTensor"]]
    return {"visibleNodes": len(scene["nodes"]), "visibleEdges": len(edges), "bounds": scene["bounds"],
            "strictDistinctCrossingPairs": sum(bool(p["strictCrossingPoints"]) for p in distinct),
            "strictDistinctCrossingPoints": sum(len(p["strictCrossingPoints"]) for p in distinct),
            "distinctInteriorContactPairs": sum(bool(p["interiorContactPoints"]) for p in distinct),
            "distinctInteriorContactPoints": sum(len(p["interiorContactPoints"]) for p in distinct),
            "distinctOverlapPairs": sum(p["overlapLength"] > EPS for p in distinct), "distinctOverlapLength": sum(p["overlapLength"] for p in distinct),
            "totalBends": sum(max(0, len(route) - 2) for route in routes), "totalLength": sum(length(route) for route in routes),
            "reversingEdges": [e["id"] for e, route in zip(edges, routes) if reversals(route)],
            "routeObstacleHits": [{"edgeId": e["id"], "hits": hits} for e, route in zip(edges, routes) if (hits := blocked(route, obstacles(scene, e)))],
            "labelAnchorHits": [{"edgeId": e["id"], "label": e["label"], "hits": hits} for e in edges if (hits := anchor_hits(scene, e))],
            "conflictingPairs": all_pairs, "safeShorterRouteProposals": safe_shortcuts(scene, edges, routes)}


def controls():
    # Independent parser: zero segments are not bends. Segment subdivision,
    # point contact, whole-edge endpoint contact, and same-axis union controls.
    assert parse("M177 216 V235 H177 V254") == [(177., 216.), (177., 254.)]
    assert pair([(0, 0), (0, 10)], [(-5, 5), (5, 5)])["strictCrossingPoints"] == [(0, 5)]
    contact = pair([(0, 0), (0, 5), (5, 5)], [(-5, 5), (2, 5)])
    assert contact["strictCrossingPoints"] == [] and contact["interiorContactPoints"] == [(0, 5)]
    assert pair([(0, 0), (0, 5)], [(0, 5), (5, 5)])["interiorContactPoints"] == []
    assert pair([(0, 0), (0, 5), (0, 10)], [(0, 2), (0, 8)])["overlapLength"] == 6
    assert hit_segment(((0, 5), (10, 5)), (4, 4, 6, 6))
    assert not hit_segment(((0, 4), (10, 4)), (4, 4, 6, 6))
    assert reversals([(0, 0), (0, 5), (0, 2)]) == 1
    return {"parserZeroLengthAndCollinear": True, "strictCrossing": True, "interiorVertexContact": True,
            "wholeEdgeEndpointExcluded": True, "overlapIntervalUnion": True, "bodyInterior": True,
            "boundaryContactExcluded": True, "reversal": True}


def main():
    assert ROOT.name == "ArchCanvas_Model_Architecture_Studio", ROOT
    receipt_path = ROOT / "docs/evidence/m4-ai-simulated-current/checks-final-attempt-3/receipt.json"
    receipt = json.loads(receipt_path.read_text())
    entries = receipt["inputs"]
    mismatches = [item for item in entries if binding(ROOT / item["path"])["sha256"] != item["sha256"]]
    assert not mismatches, "current implementation differs from B_XH final receipt"
    evidence = []
    for fixture, levels in [("transformer", range(4)), ("mlp", range(2)), ("residual_cnn", range(3))]:
        for level in levels:
            case_id = f"{fixture}-level{level}-paper-180"
            scene_path = OUTPUT / "fresh-source-core" / f"{case_id}.scene.json"
            canvas_path = OUTPUT / "fresh-source-core" / f"{case_id}.canvas.json"
            scene = json.loads(scene_path.read_text())
            evidence.append({"caseId": case_id, "sceneBinding": binding(scene_path), "canvasBinding": binding(canvas_path),
                             "sourceDigest": scene["sourceDigest"], "irDigest": scene["irDigest"], **audit(scene)})
    report = {"schema": "archcanvas-independent-current-complex-geometry-review/1", "controls": controls(),
              "humanParticipants": 0, "browserPixelsCertified": False, "modelExecuted": False,
              "implementationMatchesFinalReceipt": True, "implementationBindingsChecked": len(entries), "receiptBinding": binding(receipt_path),
              "method": "Independent serialized-scene parsing and interval geometry; finite shortcut probes preserve every endpoint/normal, nominal card/header clearance and every all-tensor pair's strict-crossing, interior-contact, overlap-length counts.",
              "records": evidence,
              "limitations": ["New SVGs are current formal core renders, not current browser screenshots.", "Strict crossing excludes intermediate segment vertices; interior-contact additionally reports them and is not a claim that every corner touch is an avoidable crossing.",
                              "Same-tensor overlap is listed, not automatically called a defect.", "Label-anchor checks prove baseline-point location only; actual text extent and glyph collision need browser getBBox/pixels.",
                              "Rectangular card outlines are conservative at rounded corners. Proposals are finite independently checked candidates, not a global optimum or installed fix.", "Nine unique authored frontiers only. ResidualCNN exposes L0/L1/L2, no fabricated L3."]}
    (OUTPUT / "geometry-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"records": len(evidence), "summary": [{"caseId": r["caseId"], "crossings": r["strictDistinctCrossingPairs"], "contacts": r["distinctInteriorContactPairs"], "overlaps": r["distinctOverlapPairs"], "shortcuts": len(r["safeShorterRouteProposals"]), "bodyHits": len(r["routeObstacleHits"]), "labelHits": len(r["labelAnchorHits"])} for r in evidence]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
