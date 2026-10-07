"""Read-only route research over sealed scenes; no product geometry imports.

This produces proposal geometry, never a CanvasDocument or accepted product
scene. A proposal rejected by any check leaves the sealed baseline untouched.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INPUT = ROOT / "docs/evidence/m4-caption-stability-current/independent-review"
EPS = 1e-6


def binding(path):
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def points(path):
    tokens = re.findall(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?", path)
    assert "".join(tokens) == re.sub(r"\s+", "", path)
    result = []
    i = 0
    while i < len(tokens):
        command = tokens[i]
        i += 1
        if command in ["M", "L"]:
            p = (float(tokens[i]), float(tokens[i + 1]))
            i += 2
        elif command == "H":
            p = (float(tokens[i]), result[-1][1])
            i += 1
        elif command == "V":
            p = (result[-1][0], float(tokens[i]))
            i += 1
        else:
            raise ValueError(command)
        assert all(math.isfinite(x) for x in p)
        assert not result or p[0] == result[-1][0] or p[1] == result[-1][1]
        if not result or p != result[-1]:
            result.append(p)
    return result


def length(route):
    return sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(route, route[1:]))


def rectangles(node):
    # Matches documented nominal renderer front/backplate geometry, without
    # importing nodeVisualOutline or routing helpers.
    shifts = [0, 3.5, 7] if node.get("repeat") and not node["expanded"] else [0]
    return [(node["x"] + shift, node["y"] + shift,
             node["x"] + node["width"] + shift, node["y"] + node["height"] + shift)
            for shift in shifts]


def enters(segment, rectangle):
    (x, y), (u, v) = segment
    left, top, right, bottom = rectangle
    if x == u:
        return left + EPS < x < right - EPS and max(min(y, v), top + EPS) < min(max(y, v), bottom - EPS)
    return top + EPS < y < bottom - EPS and max(min(x, u), left + EPS) < min(max(x, u), right - EPS)


def pair_geometry(first, second):
    contacts = set()
    spans = []
    for a, b in zip(first, first[1:]):
        for c, d in zip(second, second[1:]):
            av, cv = a[0] == b[0], c[0] == d[0]
            if av != cv:
                v, w, h, k = (a, b, c, d) if av else (c, d, a, b)
                if min(h[0], k[0]) - EPS <= v[0] <= max(h[0], k[0]) + EPS and min(v[1], w[1]) - EPS <= h[1] <= max(v[1], w[1]) + EPS:
                    contacts.add((v[0], h[1]))
            elif abs((a[0] if av else a[1]) - (c[0] if cv else c[1])) < EPS:
                axis = 1 if av else 0
                lo = max(min(a[axis], b[axis]), min(c[axis], d[axis]))
                hi = min(max(a[axis], b[axis]), max(c[axis], d[axis]))
                if hi > lo + EPS:
                    spans.append(("v" if av else "h", a[1 - axis], lo, hi))
                elif abs(hi - lo) < EPS:
                    contacts.add((a[0], lo) if av else (lo, a[1]))
    return contacts, spans


def geometry_subset(after, before):
    contacts, spans = after
    oldcontacts, oldspans = before
    if not contacts.issubset(oldcontacts):
        return False
    for axis, where, lo, hi in spans:
        covered = lo
        for a, b in sorted((a, b) for direction, fixed, a, b in oldspans if axis == direction and abs(where - fixed) < EPS):
            if a > covered + EPS:
                break
            covered = max(covered, b)
        if covered < hi - EPS:
            return False
    return True


def segment_distance(a, b, c, d):
    # Orthogonal segment AABB distance is exact for separated orthogonal
    # segments and zero for touching/crossing segments.
    dx = max(min(a[0], b[0]) - max(c[0], d[0]), min(c[0], d[0]) - max(a[0], b[0]), 0)
    dy = max(min(a[1], b[1]) - max(c[1], d[1]), min(c[1], d[1]) - max(a[1], b[1]), 0)
    return math.hypot(dx, dy)


def propose(scene, edge):
    nodes = {n["id"]: n for n in scene["nodes"]}
    source, target = nodes[edge["sourceId"]], nodes[edge["targetId"]]
    if source["expanded"] or target["expanded"]:
        return {"status": "retained", "reason": "expanded endpoint outside narrow proposal"}
    sy, ty = source["y"] + source["height"] * .55, target["y"] + target["height"] * .55
    sx = max(r for l, t, r, b in rectangles(source) if t <= sy <= b)
    tx = min(l for l, t, r, b in rectangles(target) if t <= ty <= b)
    gap = tx - sx
    source_bottom = max(b for l, t, r, b in rectangles(source))
    target_bottom = max(b for l, t, r, b in rectangles(target))
    shared_band = min(source_bottom, target_bottom) - max(source["y"], target["y"])
    if gap < 12 - EPS or shared_band <= EPS:
        return {"status": "retained", "reason": "insufficient two six-unit leads or no shared vertical band", "gap": gap, "sharedBand": shared_band}
    sx, sy, tx, ty = [round(v, 2) for v in [sx, sy, tx, ty]]
    lane = round((sx + tx) / 2, 2)
    route = [(sx, sy), (lane, sy), (lane, ty), (tx, ty)]
    if sy == ty:
        route = [(sx, sy), (tx, ty)]
    original = points(edge["path"])
    reasons, body_hits, peer_changes, stroke_hits = [], [], [], []
    ancestors = set()
    for endpoint in [source, target]:
        parent = endpoint.get("parentId")
        while parent:
            ancestors.add(parent)
            parent = nodes[parent].get("parentId")
    for node in scene["nodes"]:
        if node["id"] in ancestors:
            boxes = [(node["x"], node["y"], node["x"] + node["width"], node["y"] + node["headerHeight"])] if node["expanded"] else []
        else:
            boxes = rectangles(node)
        own = node["id"] in [source["id"], target["id"]]
        for i, (a, b) in enumerate(zip(route, route[1:])):
            for box in boxes:
                padding = 0 if own and (i == 0 or i == len(route) - 2) else 6
                l, t, r, bottom = box
                if enters((a, b), (l - padding, t - padding, r + padding, bottom + padding)):
                    body_hits.append(node["id"])
    if body_hits:
        reasons.append("body-or-six-unit-clearance")
    for peer in scene["edges"]:
        if peer["id"] == edge["id"]:
            continue
        peer_route = points(peer["path"])
        before = pair_geometry(original, peer_route)
        after = pair_geometry(route, peer_route)
        if not geometry_subset(after, before):
            peer_changes.append({"peerId": peer["id"], "contacts": sorted(after[0]), "spans": after[1]})
        minimum = min(segment_distance(a, b, c, d) for a, b in zip(route, route[1:]) for c, d in zip(peer_route, peer_route[1:]))
        required = (edge["width"] + peer["width"]) / 2
        if minimum < required + EPS:
            stroke_hits.append({"peerId": peer["id"], "minimumCenterlineDistance": minimum, "combinedHalfWidth": required})
    if peer_changes:
        reasons.append("new-peer-centerline-geometry")
    if stroke_hits:
        reasons.append("peer-visible-stroke-contact")
    if length(route) > length(original) + EPS:
        reasons.append("longer-than-sealed-baseline")
    # Only this edge proposal is evaluated. There is deliberately no batch
    # rerun, residual rescue, source mutation or warning-based exception.
    return {"status": "rejected" if reasons else "eligible", "reasons": reasons,
            "gap": gap, "sharedBand": shared_band, "pathBefore": edge["path"],
            "proposalPoints": route, "lengthBefore": length(original), "lengthAfter": length(route),
            "bendsBefore": max(0, len(original) - 2), "bendsAfter": max(0, len(route) - 2),
            "bodyHits": sorted(set(body_hits)), "peerChanges": peer_changes, "strokeContacts": stroke_hits,
            "canonicalProjectionUnchangedByConstruction": True,
            "otherRouteBytesUnchangedByConstruction": True}


def main():
    out = HERE / "frozen-proposal-attempt-1"
    assert not out.exists(), "Evidence is append-only; use a new attempt name"
    out.mkdir()
    rows, inputs = [], []
    for group in ["production-label-only", "gap-label-only", "side-gap-label-only"]:
        capture_path = INPUT / group / "capture.json"
        inputs.append(binding(capture_path))
        capture = json.loads(capture_path.read_text())
        for record in capture["sceneRecords"]:
            p = INPUT / record["sceneBinding"]["path"]
            actual = binding(p)
            assert actual["bytes"] == record["sceneBinding"]["bytes"] and actual["sha256"] == record["sceneBinding"]["sha256"]
            inputs.append(actual)
            scene = json.loads(p.read_text())
            for edge in scene["edges"]:
                if edge["role"] == "memory":
                    rows.append({"case": record["stem"], "group": group, "edgeId": edge["id"],
                                 "sourceId": edge["sourceId"], "targetId": edge["targetId"], **propose(scene, edge)})
    counts = Counter(row["status"] for row in rows)
    threshold = []
    for mode in ["default", "custom", "empty"]:
        a = next(row for row in rows if row["case"] == f"{mode}-dy14-paper-180-whole")
        b = next(row for row in rows if row["case"] == f"{mode}-dy15-paper-180-whole")
        threshold.append({"mode": mode, "bothEligible": a["status"] == b["status"] == "eligible",
                          "beforeLengths": [a["lengthBefore"], b["lengthBefore"]],
                          "proposalLengths": [a["lengthAfter"], b["lengthAfter"]],
                          "proposalSourceDisplacement": math.dist(a["proposalPoints"][0], b["proposalPoints"][0]),
                          "proposalTargetDisplacement": math.dist(a["proposalPoints"][-1], b["proposalPoints"][-1])})
    report = {"schema": "archcanvas-frozen-single-memory-proposal-analysis/1",
              "createdUtc": datetime.now(timezone.utc).isoformat(), "scenes": 504,
              "proposalRows": len(rows), "statusCounts": counts, "thresholdDy14To15": threshold,
              "rows": rows, "inputBindings": inputs,
              "scope": "Read-only proposal geometry over one sealed source-backed Transformer and three finite capture groups. Nominal rectangles and stroke widths; no product geometry helpers, product implementation, browser gesture, measured fonts, model execution, physical publication or global aesthetic approval. Other route bytes are fixed by construction; proposal adoption is not implemented. Retained/rejected rows remain limitations and do not pass by warnings."}
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ["scenes", "proposalRows", "statusCounts", "thresholdDy14To15"]}))


if __name__ == "__main__":
    main()
