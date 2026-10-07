"""Literal JSON/orthogonal geometry audit, without importing the preparer/core."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def read(path):
    return json.loads((HERE / path).read_text())


checks = []


def check(name, condition):
    checks.append({"name": name, "passed": bool(condition)})


frozen = read("input-manifest.json")
for row in frozen["inputs"]:
    original, snapshot = ROOT / row["source"], ROOT / row["snapshot"]
    raw = snapshot.read_bytes()
    check("frozen input exact " + row["source"], raw == original.read_bytes() and len(raw) == row["bytes"] and hashlib.sha256(raw).hexdigest() == row["sha256"])
old = read("inputs/previous-workload/grid.canvas.json")
new = read("candidate.canvas.json")
before = read("inputs/previous-workload/grid.scene.json")
after = read("candidate.scene.json")
report = read("preparation-report.json")
op = read("typed-operation.json")
output = report["outputId"]
expected = json.loads(json.dumps(old))
expected["revision"] += 1
for layout in [expected["layout"], *expected["layoutByFrontier"].values()]:
    if output in layout:
        layout[output]["x"] += op["dx"]
        layout[output]["y"] += op["dy"]
check("one typed output move", op["type"] == "move" and op["ids"] == [output] and op["dx"] == 0 and op["dy"] == -28590)
check("complete document exact except revision/output layouts", expected == new)
check("canonical architecture complete exact", old["architecture"] == new["architecture"])
check("source binding exact", old["sourceBindingDigest"] == new["sourceBindingDigest"])
check("source facts complete exact", before["sourceFacts"] == after["sourceFacts"])
check("IR and source digest exact", before["irDigest"] == after["irDigest"] and before["sourceDigest"] == after["sourceDigest"])
network = next(n for n in old["architecture"]["nodes"] if n["id"] == report["networkId"])
leaf_ids = set(network["children"])
check("300 unique source-backed leaf ids", len(leaf_ids) == 300)
oldnodes = {n["id"]: n for n in before["nodes"]}
newnodes = {n["id"]: n for n in after["nodes"]}
check("304 exact visible node identities", set(oldnodes) == set(newnodes) and len(newnodes) == 304)
for leaf in sorted(leaf_ids):
    check("entire leaf scene exact " + leaf, oldnodes[leaf] == newnodes[leaf])
check("network entire scene exact", oldnodes[report["networkId"]] == newnodes[report["networkId"]])
for node_id, keys in [(report["rootId"], {"height"}), (output, {"y", "localY", "ports"})]:
    # Port positions are presentation coordinates only. Canonical port IDs/directions
    # are independently covered by the unchanged canonical architecture.
    a, b = dict(oldnodes[node_id]), dict(newnodes[node_id])
    for key in keys:
        a.pop(key, None)
        b.pop(key, None)
    check("remaining scene node fields exact " + node_id, a == b)
check("root natural height shrinks", oldnodes[report["rootId"]]["height"] == 30346 and newnodes[report["rootId"]]["height"] == 1756)
check("output below network with60world gap", newnodes[output]["y"] - (newnodes[report["networkId"]]["y"] + newnodes[report["networkId"]]["height"]) == 60)
check("output derived local/absolute y each shifts by typed delta", newnodes[output]["y"] - oldnodes[output]["y"] == op["dy"] and newnodes[output]["localY"] - oldnodes[output]["localY"] == op["dy"])
old_port, new_port = oldnodes[output]["ports"][0], newnodes[output]["ports"][0]
check("output port only derived y shifts", {k: v for k, v in old_port.items() if k != "y"} == {k: v for k, v in new_port.items() if k != "y"} and new_port["y"] - old_port["y"] == op["dy"])
oldedges = {e["id"]: e for e in before["edges"]}
newedges = {e["id"]: e for e in after["edges"]}
check("302 exact edge identities", set(oldedges) == set(newedges) and len(newedges) == 302)
changed = []
for edge_id in sorted(oldedges):
    a, b = dict(oldedges[edge_id]), dict(newedges[edge_id])
    if a["path"] != b["path"]:
        changed.append(edge_id)
        for key in ("path", "labelX", "labelY"):
            a.pop(key, None)
            b.pop(key, None)
        check("changed edge canonical/style/label exact " + edge_id, a == b)
    else:
        check("entire unchanged edge exact " + edge_id, a == b)
check("only output edge path changed", changed == ["edge:303"])
check("scene diagnostics remain info only", before["diagnostics"] == after["diagnostics"] and all(d["level"] == "info" for d in after["diagnostics"]))
check("bounds exact expected compact candidate", after["bounds"] == {"x": 0, "y": 0, "width": 4588, "height": 1952})


def segments(path):
    tokens = re.findall(r"[MHVL]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", path)
    points, i, command = [], 0, None
    while i < len(tokens):
        if tokens[i] in ("M", "H", "V", "L"):
            command = tokens[i]
            i += 1
        if command in ("M", "L"):
            point = float(tokens[i]), float(tokens[i + 1])
            i += 2
        elif command == "H":
            point = float(tokens[i]), points[-1][1]
            i += 1
        elif command == "V":
            point = points[-1][0], float(tokens[i])
            i += 1
        else:
            raise ValueError(path)
        points.append(point)
    return [(a, b) for a, b in zip(points, points[1:]) if a != b]


def body_intrusion(segment, body):
    (x1, y1), (x2, y2) = segment
    x, y, w, h = (body[k] for k in ("x", "y", "width", "height"))
    if y1 == y2 and y < y1 < y + h:
        return max(0, min(max(x1, x2), x + w) - max(min(x1, x2), x))
    if x1 == x2 and x < x1 < x + w:
        return max(0, min(max(y1, y2), y + h) - max(min(y1, y2), y))
    return 0


def pair_contact(a, b):
    (ax1, ay1), (ax2, ay2) = a
    (bx1, by1), (bx2, by2) = b
    av, bv = ax1 == ax2, bx1 == bx2
    if av == bv:
        if (ax1 != bx1 if av else ay1 != by1):
            return None
        low = max(min(ay1, ay2), min(by1, by2)) if av else max(min(ax1, ax2), min(bx1, bx2))
        high = min(max(ay1, ay2), max(by1, by2)) if av else min(max(ax1, ax2), max(bx1, bx2))
        return ("overlap", high - low) if high > low else None
    vertical, horizontal = (a, b) if av else (b, a)
    x, y = vertical[0][0], horizontal[0][1]
    if min(horizontal[0][0], horizontal[1][0]) < x < max(horizontal[0][0], horizontal[1][0]) and min(vertical[0][1], vertical[1][1]) < y < max(vertical[0][1], vertical[1][1]):
        return ("proper-crossing", x, y)
    return None


def geometry(scene):
    edges = scene["edges"]
    paths = {e["id"]: segments(e["path"]) for e in edges}
    leaves = {n["id"]: n for n in scene["nodes"] if n["id"] in leaf_ids}
    intrusions, contacts = [], []
    for edge in edges:
        for node_id, body in leaves.items():
            if node_id in (edge["sourceId"], edge["targetId"]):
                continue
            length = sum(body_intrusion(segment, body) for segment in paths[edge["id"]])
            if length > 1e-9:
                intrusions.append({"edge": edge["id"], "unrelatedLeaf": node_id, "length": length})
    for i, left in enumerate(edges):
        for right in edges[i + 1:]:
            if {left["sourceId"], left["targetId"]} & {right["sourceId"], right["targetId"]}:
                continue
            for ai, a in enumerate(paths[left["id"]]):
                for bi, b in enumerate(paths[right["id"]]):
                    contact = pair_contact(a, b)
                    if contact:
                        contacts.append({"left": left["id"], "right": right["id"], "leftSegment": ai, "rightSegment": bi, "contact": contact})
    return {"unrelatedLeafBodyIntrusions": intrusions, "peerSegmentContacts": contacts,
            "totalPathLength": sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for parts in paths.values() for a, b in parts)}


before_geometry, after_geometry = geometry(before), geometry(after)
before_contacts = {json.dumps(x, sort_keys=True) for x in before_geometry["peerSegmentContacts"]}
after_contacts = {json.dumps(x, sort_keys=True) for x in after_geometry["peerSegmentContacts"]}
added_contacts = sorted(after_contacts - before_contacts)
check("no new literal unrelated peer contact", not added_contacts)
check("no new unrelated leaf body intrusion", after_geometry["unrelatedLeafBodyIntrusions"] == before_geometry["unrelatedLeafBodyIntrusions"])
coverage_rows = []
for row in report["coverages"]:
    viewport, bounds = row["viewport"], after["bounds"]
    zoom = min((viewport["width"] - 96) / bounds["width"], (viewport["height"] - 92) / bounds["height"], 1.2)
    x = viewport["width"] / 2 - (bounds["x"] + bounds["width"] / 2) * zoom
    y = viewport["height"] / 2 - (bounds["y"] + bounds["height"] / 2) * zoom
    bodies = [{"id": leaf, "x": x + newnodes[leaf]["x"] * zoom, "y": y + newnodes[leaf]["y"] * zoom,
               "width": newnodes[leaf]["width"] * zoom, "height": newnodes[leaf]["height"] * zoom} for leaf in network["children"]]
    inside = sum(b["x"] >= 0 and b["y"] >= 0 and b["x"] + b["width"] <= viewport["width"] and b["y"] + b["height"] <= viewport["height"] for b in bodies)
    check("300body geometry fully inside " + str(viewport), inside == row["fullyInside"] == 300)
    check("literal projected bodies exact " + str(viewport), row["bodies"] == bodies)
    check("nominal font arithmetic exact " + str(viewport), math.isclose(row["nominalNodeFontPx"], 13 * zoom, abs_tol=1e-12))
    coverage_rows.append({k: v for k, v in row.items() if k != "bodies"})
result = {"schema": "archcanvas-readable-grid-independent-readback/1", "createdUtc": datetime.now(timezone.utc).isoformat(),
          "passed": sum(c["passed"] for c in checks), "total": len(checks), "checks": checks,
          "failedChecks": [c for c in checks if not c["passed"]], "bounds": after["bounds"], "coverages": coverage_rows,
          "beforeGeometry": before_geometry, "afterGeometry": after_geometry, "addedPeerContacts": [json.loads(s) for s in added_contacts],
          "scope": "Independent literal document/hash/orthogonal centreline geometry only. Endpoint-related peers excluded. Does not measure glyphs, strokes/markers, browser viewport occlusion, readability, hardware, fonts, input latency, continuous input, presented FPS, models, humans or physical publication."}
target = HERE / "independent-report-attempt-2.json"
assert not target.exists()
target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"passed": result["passed"], "total": result["total"], "failed": result["failedChecks"],
                  "beforeLeafIntrusions": len(before_geometry["unrelatedLeafBodyIntrusions"]), "afterLeafIntrusions": len(after_geometry["unrelatedLeafBodyIntrusions"]),
                  "beforePeerContacts": len(before_geometry["peerSegmentContacts"]), "afterPeerContacts": len(after_geometry["peerSegmentContacts"]), "addedPeerContacts": len(added_contacts)}, ensure_ascii=False))
raise SystemExit(0 if result["passed"] == result["total"] else 1)
