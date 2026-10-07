"""Read-only, independent public-SVG geometry audit; no product imports."""
from __future__ import annotations

import collections
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[5]
BROWSER = REPO / "docs/evidence/m4-frontier-move-current/browser"
OUT = Path(__file__).with_name("report.json")
NS = "{http://www.w3.org/2000/svg}"
TARGET = "call:instance:model.DenseStress300.network.0"
NETWORK = "call:instance:model.DenseStress300.network"
PIN = "input:model.DenseStress300:features"
OUTPUT = "output:model.DenseStress300:0"
NAMES = [
    "02-right24-current7", "03-right-undo8", "04-up24-current", "05-up-undo",
    "06-down24-current", "07-down-undo", "08-left24-current", "09-left-undo",
    "10-collapsed-current", "11-reexpanded-current", "12-saved16", "13-reopened16",
    "14-collapsed17-fit", "15-reexpanded18-fit",
]


def bind(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.relative_to(REPO)), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def vertices(d: str) -> list[tuple[float, float]]:
    # Every observed public route has only these absolute orthogonal commands.
    # Reject anything else rather than interpreting a curve as a straight line.
    tokens = re.findall(r"[A-Za-z]|[-+]?(?:\d*\.)?\d+(?:[eE][-+]?\d+)?", d)
    points: list[tuple[float, float]] = []
    i = 0
    while i < len(tokens):
        command = tokens[i]
        i += 1
        if command in ("M", "L"):
            point = (float(tokens[i]), float(tokens[i + 1]))
            i += 2
        elif command == "H":
            point = (float(tokens[i]), points[-1][1])
            i += 1
        elif command == "V":
            point = (points[-1][0], float(tokens[i]))
            i += 1
        else:
            raise ValueError(f"unsupported public route command: {command}")
        if not all(math.isfinite(v) for v in point):
            raise ValueError("nonfinite route coordinate")
        if not points or point != points[-1]:
            points.append(point)
    clean: list[tuple[float, float]] = []
    for point in points:
        # Collapse only straight, same-direction segments; never hide backtracking.
        while len(clean) > 1:
            a, b = clean[-2:]
            vertical = a[0] == b[0] == point[0]
            horizontal = a[1] == b[1] == point[1]
            forward = ((b[0] - a[0]) * (point[0] - b[0]) +
                       (b[1] - a[1]) * (point[1] - b[1])) >= 0
            if not ((vertical or horizontal) and forward):
                break
            clean.pop()
        clean.append(point)
    if any(a[0] != b[0] and a[1] != b[1] for a, b in zip(clean, clean[1:])):
        raise ValueError("nonorthogonal route")
    return clean


def read(name: str) -> dict:
    root = ET.parse(BROWSER / f"{name}.svg").getroot()
    dom = json.loads((BROWSER / f"{name}.json").read_text())
    nodes, routes, font_sizes = {}, {}, {}
    for group in root.iter(NS + "g"):
        if "data-node-id" in group.attrib:
            rectangles = [el for el in group if el.tag == NS + "rect"]
            if rectangles:
                # Stacked module decorations precede the foreground body.
                rect = rectangles[-1]
                node_id = group.attrib["data-node-id"]
                nodes[node_id] = [float(rect.attrib[k]) for k in ("x", "y", "width", "height")]
                font_sizes[node_id] = [float(el.attrib["font-size"]) for el in group
                                       if el.tag == NS + "text" and "font-size" in el.attrib]
        if "data-edge-id" in group.attrib:
            path = group.find(NS + "path")
            if path is None:
                raise ValueError("missing public route")
            routes[group.attrib["data-edge-id"]] = vertices(path.attrib["d"])
    bounds = [float(v) for v in root.attrib["viewBox"].split()]
    x0, y0, width, height = bounds
    out_of_viewbox = [node_id for node_id, (x, y, w, h) in nodes.items()
                      if x < x0 or y < y0 or x + w > x0 + width or y + h > y0 + height]
    leaves = {node_id: rect for node_id, rect in nodes.items() if ".network." in node_id}
    sibling_overlaps, sibling_contacts = [], []
    leaf_items = list(leaves.items())
    for k, (a_id, (ax, ay, aw, ah)) in enumerate(leaf_items):
        for b_id, (bx, by, bw, bh) in leaf_items[k + 1:]:
            ix = min(ax + aw, bx + bw) - max(ax, bx)
            iy = min(ay + ah, by + bh) - max(ay, by)
            if ix > 0 and iy > 0:
                sibling_overlaps.append([a_id, b_id])
            elif (ix == 0 and iy > 0) or (iy == 0 and ix > 0):
                sibling_contacts.append([a_id, b_id])
    segments = [(edge_id, index, a, b) for edge_id, points in routes.items()
                for index, (a, b) in enumerate(zip(points, points[1:]))]
    crossings, overlaps = [], []
    for k, (a_id, ai, a, b) in enumerate(segments):
        for b_id, bi, c, d in segments[k + 1:]:
            if a_id == b_id:
                continue
            a_horizontal, b_horizontal = a[1] == b[1], c[1] == d[1]
            if a_horizontal == b_horizontal:
                if a_horizontal and a[1] == c[1]:
                    low = max(min(a[0], b[0]), min(c[0], d[0]))
                    high = min(max(a[0], b[0]), max(c[0], d[0]))
                    axis, fixed = "H", a[1]
                elif not a_horizontal and a[0] == c[0]:
                    low = max(min(a[1], b[1]), min(c[1], d[1]))
                    high = min(max(a[1], b[1]), max(c[1], d[1]))
                    axis, fixed = "V", a[0]
                else:
                    continue
                if high > low:
                    overlaps.append({"edges": [a_id, b_id], "segments": [ai, bi],
                                     "axis": axis, "fixed": fixed, "interval": [low, high]})
            else:
                h = (a, b) if a_horizontal else (c, d)
                v = (c, d) if a_horizontal else (a, b)
                x, y = v[0][0], h[0][1]
                # Strict interior intersection excludes any endpoint contact.
                if (min(h[0][0], h[1][0]) < x < max(h[0][0], h[1][0]) and
                        min(v[0][1], v[1][1]) < y < max(v[0][1], v[1][1])):
                    crossings.append({"edges": [a_id, b_id], "point": [x, y],
                                      "segments": [ai, bi]})
    leaf_intrusions = []
    for edge_id, points in routes.items():
        start, end = points[0], points[-1]
        for node_id, (x, y, w, h) in leaves.items():
            def on_boundary(point):
                return (((point[0] == x or point[0] == x + w) and y <= point[1] <= y + h) or
                        ((point[1] == y or point[1] == y + h) and x <= point[0] <= x + w))
            # Endpoint bodies are explicitly excluded, using their public geometry.
            if on_boundary(start) or on_boundary(end):
                continue
            for index, (a, b) in enumerate(zip(points, points[1:])):
                inside = ((a[1] == b[1] and y < a[1] < y + h and
                           max(min(a[0], b[0]), x) < min(max(a[0], b[0]), x + w)) or
                          (a[0] == b[0] and x < a[0] < x + w and
                           max(min(a[1], b[1]), y) < min(max(a[1], b[1]), y + h)))
                if inside:
                    leaf_intrusions.append({"edge": edge_id, "node": node_id, "segment": index})
    header_intrusions = []
    if NETWORK in nodes:
        px, py, pw, ph = nodes[NETWORK]
        # The public header-divider path provides the header bottom, no product token import.
        parent = next(g for g in root.iter(NS + "g") if g.attrib.get("data-node-id") == NETWORK)
        header_path = next((el.attrib.get("d", "") for el in parent
                            if el.tag == NS + "path" and "H" in el.attrib.get("d", "")), "")
        header_match = re.fullmatch(r"M [-\d.]+ ([-\d.]+) H [-\d.]+", header_path)
        if header_match:
            header_bottom = float(header_match.group(1))
            for node_id, (x, y, w, h) in leaves.items():
                if y < header_bottom and y + h > py and x < px + pw and x + w > px:
                    header_intrusions.append({"node": node_id, "headerBottom": header_bottom,
                                              "depthWorldUnits": header_bottom - y})
    scale_match = re.search(r"scale\(([-\d.]+)\)", dom["camera"])
    scale = float(scale_match.group(1)) if scale_match else None
    label_fonts = sorted({size for node_id, sizes in font_sizes.items()
                          if ".network." in node_id for size in sizes})
    return {
        "name": name, "revision": int(root.attrib["data-revision"]), "viewBox": bounds,
        "bodyCount": len(nodes), "leafCount": len(leaves), "routeCount": len(routes),
        "bodyOutsidePublicViewBox": out_of_viewbox, "siblingInteriorOverlaps": sibling_overlaps,
        "siblingBoundaryContacts": sibling_contacts, "networkHeaderIntrusions": header_intrusions,
        "routeSegmentHistogram": dict(sorted(collections.Counter(len(p) - 1 for p in routes.values()).items())),
        "routeBendHistogram": dict(sorted(collections.Counter(max(0, len(p) - 2) for p in routes.values()).items())),
        "strictInteriorCrossings": crossings,
        "strictCrossingEdgePairCount": len({tuple(sorted(x["edges"])) for x in crossings}),
        "positiveCollinearOverlaps": overlaps,
        "routeThroughNonEndpointLeafInteriors": leaf_intrusions,
        "cameraScaleFromPublicDOM": scale, "leafFontSizesWorldUnits": label_fonts,
        "leafFontSizesAtCapturedCameraPx": [round(size * scale, 6) for size in label_fonts] if scale else [],
        "leafFontSizesAt180mmWidthPt": [round(size * 180 / width * 72 / 25.4, 6) for size in label_fonts],
        "nodes": nodes, "routeVertices": routes,
        "sourceDigest": json.loads(root.find(NS + "metadata").text)["sourceDigest"],
        "irDigest": json.loads(root.find(NS + "metadata").text)["irDigest"],
    }


states = {name: read(name) for name in NAMES}
base = states["03-right-undo8"]
directions = []
for label, applied, undone, delta in [
    ("right", "02-right24-current7", "03-right-undo8", [24, 0]),
    ("up", "04-up24-current", "05-up-undo", [0, -24]),
    ("down", "06-down24-current", "07-down-undo", [0, 24]),
    ("left", "08-left24-current", "09-left-undo", [-24, 0]),
]:
    a, u = states[applied], states[undone]
    moved = [node_id for node_id, rect in a["nodes"].items() if rect != base["nodes"].get(node_id)]
    changed_routes = [edge_id for edge_id, path in a["routeVertices"].items()
                      if path != base["routeVertices"].get(edge_id)]
    b, got = base["nodes"][TARGET], a["nodes"][TARGET]
    actual_delta = [got[0] - b[0], got[1] - b[1]]
    directions.append({"direction": label, "apply": applied, "undo": undone,
                       "expectedWorldDelta": delta, "actualWorldDelta": actual_delta,
                       "exactDelta": actual_delta == delta,
                       "changedBodies": moved, "onlySelectedBodyChanged": moved == [TARGET],
                       "changedRouteIds": changed_routes,
                       "undoBodiesExactToBaseline": u["nodes"] == base["nodes"],
                       "undoRoutesExactToBaseline": u["routeVertices"] == base["routeVertices"],
                       "sourceAndIrStable": a["sourceDigest"] == base["sourceDigest"] and
                                            a["irDigest"] == base["irDigest"]})

inputs = []
for name in ["01-expanded-seed6"] + NAMES:
    for suffix in ("json", "svg", "png"):
        path = BROWSER / f"{name}.{suffix}"
        if path.exists():
            inputs.append(bind(path))
for relative in [
    "docs/evidence/m4-frontier-move-current/independent/workload-readback-report.json",
    "docs/evidence/m4-frontier-move-current/independent/workload/preparation-report.json",
    "docs/evidence/m4-frontier-move-current/independent/workload/pinned.canvas.json",
    "docs/evidence/m4-frontier-move-current/independent/workload/collapsed.canvas.json",
]:
    inputs.append(bind(REPO / relative))

summary = []
for state in states.values():
    summary.append({k: v for k, v in state.items() if k not in ("nodes", "routeVertices")})
result = {
    "schema": "archcanvas-ai-public-svg-gesture-audit/1", "agentKind": "AI-simulated-reviewer",
    "humanParticipantsAdded": 0, "newBrowserInputsByThisAgent": 0,
    "inputs": inputs, "directionReadback": directions, "states": summary,
    "saveReopenSvgByteExact": (BROWSER / "12-saved16.svg").read_bytes() ==
                               (BROWSER / "13-reopened16.svg").read_bytes(),
    "reexpandedBodiesExactToBaseline": states["11-reexpanded-current"]["nodes"] == base["nodes"],
    "reexpandedRoutesExactToBaseline": states["11-reexpanded-current"]["routeVertices"] == base["routeVertices"],
    "settledExpandedBodiesExactToBaseline": states["15-reexpanded18-fit"]["nodes"] == base["nodes"],
    "settledExpandedRoutesExactToBaseline": states["15-reexpanded18-fit"]["routeVertices"] == base["routeVertices"],
    "inputPinBodies": {name: state["nodes"].get(PIN) for name, state in states.items()},
    "outputBodies": {name: state["nodes"].get(OUTPUT) for name, state in states.items()},
    "limits": [
        "Strict centerline geometry only; excludes endpoint contacts, stroke width, arrowhead areas, captions and text boxes.",
        "Sibling overlap scope is the finite 300-leaf set; ancestor-container containment is intentional.",
        "Crossing/overlap counts do not prove each intersection or bend unnecessary or establish a global route optimum.",
        "Nominal font world units times DOM camera or physical-width scale are arithmetic, not font raster or human reading certification.",
        "No new mouse drag, viewport pan, timing, model execution, semantic source writeback or human acceptance.",
    ],
}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"states": len(summary), "inputs": len(inputs), "directions": directions,
                  "expandedCrossingPairs": states["15-reexpanded18-fit"]["strictCrossingEdgePairCount"],
                  "expandedOverlapGroups": len(states["15-reexpanded18-fit"]["positiveCollinearOverlaps"]),
                  "saveReopenSvgByteExact": result["saveReopenSvgByteExact"]}, ensure_ascii=False, indent=2))
