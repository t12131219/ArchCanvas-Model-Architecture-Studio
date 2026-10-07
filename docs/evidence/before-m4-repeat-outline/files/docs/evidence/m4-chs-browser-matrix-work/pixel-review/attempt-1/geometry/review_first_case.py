"""Read-only first-case source geometry audit; no product imports or browser actions."""
from pathlib import Path
import collections
import hashlib
import itertools
import json
import math
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
CASE = ROOT / "raw" / "transformer-level0-paper-85"
OUT = Path(__file__).resolve().parent
NAMES = ["before.dom.txt", "after.dom.txt", "browser-scene.svg", "dom-observation.json", "saved-envelope.json", "saved-envelope.json.receipt.json"]


def bind(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


initial = [bind(CASE / name) for name in NAMES]
svg = ET.parse(CASE / "browser-scene.svg").getroot()
metadata = json.loads(next(x for x in svg if x.tag.endswith("metadata")).text)
observation = json.loads((CASE / "dom-observation.json").read_text())
envelope = json.loads((CASE / "saved-envelope.json").read_text())
document = envelope["document"]
receipt = json.loads((CASE / "saved-envelope.json.receipt.json").read_text())
doms = {name: (CASE / name).read_text() for name in ["before.dom.txt", "after.dom.txt"]}
parents = {child: parent for parent in svg.iter() for child in parent}


def ancestor_transforms(element):
    result = []
    while element is not None:
        if "transform" in element.attrib:
            result.append(element.attrib["transform"])
        element = parents.get(element)
    return result


def route_points(d):
    tokens = re.findall(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?", d)
    residue = re.sub(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?|[\s,]", "", d)
    assert not residue, residue
    points, position, command, i = [], None, None, 0
    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]
            i += 1
        assert command in {"M", "L", "H", "V"}, (d, command)
        if command in {"M", "L"}:
            position = [float(tokens[i]), float(tokens[i + 1])]
            i += 2
        elif command == "H":
            assert position is not None
            position = [float(tokens[i]), position[1]]
            i += 1
        else:
            assert position is not None
            position = [position[0], float(tokens[i])]
            i += 1
        points.append(position)
        if command == "M":
            command = "L"
    assert points
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(points, points[1:])), d
    return points


def rectangle(element):
    return {k: float(element.attrib[k]) for k in ["x", "y", "width", "height"]}


cards, backplates, containers, visible_nodes = [], [], [], []
architecture_nodes = {n["id"]: n for n in document["architecture"]["nodes"]}
for element in svg.iter():
    if element.attrib.get("data-node-id") and element.attrib.get("role") == "button":
        assert not ancestor_transforms(element)
        node_id = element.attrib["data-node-id"]
        rects = [x for x in element if x.tag.endswith("rect")]
        front = [x for x in rects if x.attrib.get("stroke-width")]
        assert len(front) == 1
        front_rect = front[0]
        node = architecture_nodes[element.attrib["data-canonical-id"]]
        visible_nodes.append({"id": node_id, "label": element.attrib.get("aria-label"), "kind": node["kind"], "category": node["category"], "text": ["".join(x.itertext()) for x in element if x.tag.endswith("text")], "mainRect": rectangle(front_rect), "rx": front_rect.attrib.get("rx"), "expanded": node_id in document["expandedIds"]})
        target = containers if node_id in document["expandedIds"] else cards
        target.append({"nodeId": node_id, **rectangle(front_rect)})
        for index, rect in enumerate(rects):
            if rect is not front_rect:
                backplates.append({"nodeId": node_id, "rectIndex": index, **rectangle(rect), "opacity": rect.attrib.get("opacity")})

ports = []
for element in svg.iter():
    if "data-port-id" not in element.attrib:
        continue
    assert not ancestor_transforms(element)
    circles = [x for x in element if x.tag.endswith("circle")]
    assert len(circles) == 2
    points = {(float(x.attrib["cx"]), float(x.attrib["cy"])) for x in circles}
    assert len(points) == 1
    ports.append({"id": element.attrib["data-port-id"], "sceneNodeId": element.attrib["data-node-id"], "point": list(next(iter(points))), "title": "".join(next(x for x in element if x.tag.endswith("title")).itertext())})

routes = []
bindings = {x["sceneEdgeId"]: x for x in metadata["renderedBindings"]}
for element in svg.iter():
    if "data-edge-id" not in element.attrib:
        continue
    assert not ancestor_transforms(element)
    paths = [x for x in element if x.tag.endswith("path")]
    assert len(paths) == 1
    path = paths[0]
    points = route_points(path.attrib["d"])
    binding = bindings[element.attrib["data-edge-id"]]
    endpoints = {}
    for end, point in [("source", points[0]), ("target", points[-1])]:
        suffix = ":" + binding[end]["portId"] + ":" + binding["role"]
        matches = [x for x in ports if x["id"].endswith(suffix)]
        assert len(matches) == 1, (binding, end, suffix, matches)
        port = matches[0]
        error = math.dist(point, port["point"])
        endpoints[end] = {"pathPoint": point, "publicPort": port, "distance": error, "withinDeclaredRoundingTolerance": error <= 0.051}
    routes.append({"id": element.attrib["data-edge-id"], "role": binding["role"], "tensorId": element.attrib["data-tensor-id"], "canonicalEdgeIds": binding["canonicalEdgeIds"], "d": path.attrib["d"], "points": points, "stroke": path.attrib.get("stroke"), "strokeWidth": path.attrib.get("stroke-width"), "dasharray": path.attrib.get("stroke-dasharray"), "markerEnd": path.attrib.get("marker-end"), "endpoints": endpoints})


def segments(route):
    return [(index, a, b) for index, (a, b) in enumerate(zip(route["points"], route["points"][1:])) if a != b]


def penetration(a, b, rect):
    x0, y0 = rect["x"], rect["y"]
    x1, y1 = x0 + rect["width"], y0 + rect["height"]
    if a[1] == b[1] and y0 < a[1] < y1:
        lo, hi = max(min(a[0], b[0]), x0), min(max(a[0], b[0]), x1)
        if lo < hi:
            return [[lo, a[1]], [hi, a[1]]]
    if a[0] == b[0] and x0 < a[0] < x1:
        lo, hi = max(min(a[1], b[1]), y0), min(max(a[1], b[1]), y1)
        if lo < hi:
            return [[a[0], lo], [a[0], hi]]


def penetrations(rects):
    return [{"edgeId": r["id"], "segmentIndex": i, "rect": rect, "openInteriorSpan": span} for r in routes for i, a, b in segments(r) for rect in rects if (span := penetration(a, b, rect))]


def overlap_rects(rects):
    result = []
    for a, b in itertools.combinations(rects, 2):
        lo = [max(a["x"], b["x"]), max(a["y"], b["y"])]
        hi = [min(a["x"] + a["width"], b["x"] + b["width"]), min(a["y"] + a["height"], b["y"] + b["height"])]
        if all(l < h for l, h in zip(lo, hi)):
            result.append({"nodeA": a["nodeId"], "nodeB": b["nodeId"], "openOverlapBounds": [lo, hi]})
    return result


def intersect(a, b, c, d):
    ah, ch = a[1] == b[1], c[1] == d[1]
    if ah == ch:
        same = a[1] == c[1] if ah else a[0] == c[0]
        if not same:
            return None
        dim = 0 if ah else 1
        lo, hi = max(min(a[dim], b[dim]), min(c[dim], d[dim])), min(max(a[dim], b[dim]), max(c[dim], d[dim]))
        if lo > hi:
            return None
        if ah:
            span = [[lo, a[1]], [hi, a[1]]]
        else:
            span = [[a[0], lo], [a[0], hi]]
        return {"type": "collinear-overlap" if lo < hi else "point-touch", "span": span}
    h0, h1, v0, v1 = (a, b, c, d) if ah else (c, d, a, b)
    point = [v0[0], h0[1]]
    if min(h0[0], h1[0]) <= point[0] <= max(h0[0], h1[0]) and min(v0[1], v1[1]) <= point[1] <= max(v0[1], v1[1]):
        strict = min(h0[0], h1[0]) < point[0] < max(h0[0], h1[0]) and min(v0[1], v1[1]) < point[1] < max(v0[1], v1[1])
        return {"type": "strict-perpendicular-crossing" if strict else "point-touch", "point": point}


route_intersections = []
for ra, rb in itertools.combinations(routes, 2):
    hits = []
    for ia, a, b in segments(ra):
        for ib, c, d in segments(rb):
            hit = intersect(a, b, c, d)
            if hit:
                hits.append({"segmentA": ia, "segmentB": ib, **hit})
    if hits:
        route_intersections.append({"edgeA": ra["id"], "edgeB": rb["id"], "roleA": ra["role"], "roleB": rb["role"], "segmentIncidences": hits})

public_binding = observation["documentBinding"]
binding_equality = {
    "documentId": svg.attrib["data-document-id"] == metadata["documentId"] == document["id"] == public_binding["documentId"],
    "revision": int(svg.attrib["data-revision"]) == metadata["revision"] == document["revision"] == envelope["revision"] == public_binding["revision"],
    "sourceDigestDeclarations": metadata["sourceDigest"] == document["sourceBindingDigest"] == document["architecture"]["sourceDigest"] == public_binding["sourceDigest"],
    "irDigestDeclarations": metadata["irDigest"] == document["architecture"]["irDigest"] == public_binding["irDigest"],
    "pageWidthMm": float(svg.attrib["width"].removesuffix("mm")) == metadata["widthMm"] == document["pageSpec"]["widthMm"] == observation["pageSpec"]["widthMm"],
    "pagePreset": document["pageSpec"]["preset"] == observation["pageSpec"]["preset"] == "paper",
    "expandedIds": document["expandedIds"] == observation["expandedIds"] == ["call:instance:model.Transformer"],
    "renderedNodeIds": {n["id"] for n in visible_nodes} == {n["sceneNodeId"] for n in metadata["renderedNodes"]},
    "renderedEdgeIds": {r["id"] for r in routes} == set(bindings),
    "saveReceiptSnapshotDigest": receipt["sha256"] == initial[NAMES.index("saved-envelope.json")]["sha256"],
    "saveReceiptSnapshotBytes": receipt["bytes"] == initial[NAMES.index("saved-envelope.json")]["bytes"],
}
dom_checks = {name: {"containsDialogToken": bool(re.search(r"^\s*- (?:alert)?dialog\b", value, re.M)), "savedHeader": '- generic: 已保存' in value, "revision1Footer": '- generic: rev 1' in value, "page85mm": '- text: 85 mm' in value, "paperColor": '- text: PAPER COLOR' in value, "rootCollapseControl": 'Collapse Transformer' in value, "encoderExpandControl": 'Expand encoder' in value, "decoderExpandControl": 'Expand decoder' in value, "allSvgEdgeRoleTitlesPresent": all(f'{r["id"]} · {r["role"]} · {r["tensorId"]}' in value for r in routes), "allSvgNodeLabelsPresent": all(n['label'] in value for n in visible_nodes)} for name, value in doms.items()}
end = [bind(CASE / name) for name in NAMES]
report = {
    "scope": "Independent read-only public SVG/full DOM/stored snapshot source geometry review of transformer-level0-paper-85",
    "acquisitionNote": "Six assigned input files bound before this script's content parsing and independently rehashed at finish; earlier agent initial binding also preceded structural content reads. This is not a proof of immutable first acquisition or capture synchronization.",
    "inputBindingsStart": initial,
    "inputBindingsEnd": end,
    "inputsUnchanged": initial == end,
    "svgRoot": svg.attrib,
    "metadataBinding": {k: metadata[k] for k in ['renderer','documentId','revision','sourceDigest','irDigest','widthMm','heightMm','sourceFactScope']},
    "bindingEquality": binding_equality,
    "declaredArchitectureNodeCount": len(document['architecture']['nodes']),
    "declaredArchitectureEdgeCount": len(document['architecture']['edges']),
    "beforeAfterDomByteEqual": (CASE / 'before.dom.txt').read_bytes() == (CASE / 'after.dom.txt').read_bytes(),
    "domChecks": dom_checks,
    "observationDialogCount": observation['dialogCount'],
    "applicability": {
        "independentImplementation": "stdlib XML/JSON parsing and explicit M/L/H/V route parser; no old helper or product import",
        "routeCount": len(routes),
        "frontCardCount": len(cards),
        "expandedContainerCount": len(containers),
        "repeatDecorativeBackplateCount": len(backplates),
        "publicPortCount": len(ports),
        "ancestorTransformCountForAuditedCardsRoutesPorts": 0,
        "endpointToleranceSceneUnits": 0.051,
        "toleranceReason": "Route coordinate serialization uses tenths in some endpoint values while matching public circle coordinates use hundredths (e.g. 144.7 vs 144.67). Exact differences are retained.",
        "rectangleDefinition": "Strict open axis-aligned interior of each main/front collapsed card; expanded Transformer enclosing rectangle and same-node repeat stack backplates are separately classified. Rounded corners and stroke outlines are not resolved by this test.",
        "routeIntersectionDefinition": "Every nonzero segment pair between distinct routes, exact public serialized coordinates; shared corners/touches and collinear overlaps are retained separately from strict segment-interior perpendicular crossings. Counts are segment incidences, not rendered pixel or unique-net crossing counts."
    },
    "visibleNodes": visible_nodes,
    "containers": containers,
    "repeatDecorativeBackplates": backplates,
    "roleCounts": dict(collections.Counter(r['role'] for r in routes)),
    "routes": routes,
    "endpointSummary": {"checkedEndpoints": len(routes) * 2, "allMatchCanonicalPortAndRoleWithinTolerance": all(e['withinDeclaredRoundingTolerance'] for r in routes for e in r['endpoints'].values()), "maxDistanceSceneUnits": max(e['distance'] for r in routes for e in r['endpoints'].values())},
    "mainCardOverlaps": overlap_rects(cards),
    "mainCardRoutePenetrations": penetrations(cards),
    "repeatBackplateRoutePenetrations": penetrations(backplates),
    "routeIntersections": route_intersections,
    "routeIntersectionSummary": {"distinctRoutePairs": len(route_intersections), "segmentIncidenceTypes": dict(collections.Counter(h['type'] for pair in route_intersections for h in pair['segmentIncidences']))},
    "limits": ["Source geometry only. No images opened by this reviewer; no pixel conclusions, raster synchronization, arrowhead legibility, font glyph bounds, text clipping/readability, runtime model fidelity, native browser/version/hardware lock, performance or human acceptance certified.", "Declared source/IR digest consistency is checked, not independently recomputed from source here.", "Saved snapshot receipt consistency does not prove live store bytes, save success, or receipt acquisition method.", "Before/after DOM byte equality and matching field declarations do not prove screenshot state; parent's separately observed primer modal discrepancy remains untouched.", "Mask/residual route contacts and overlaps remain findings; correct endpoints and zero main-card penetration do not imply all routes are distinguishable."]
}
OUT.mkdir(parents=True, exist_ok=True)
json_path = OUT / 'transformer-level0-paper-85-source-geometry.json'
json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
summary = report['routeIntersectionSummary']
md = f'''# Transformer level 0 / paper 85 mm source geometry review

Six assigned inputs were bound before structural content review and rehashed unchanged at finish. The SVG, DOM observation and stored snapshot agree on document ID, revision 1, declared source/IR digests, paper width 85 mm, and only the Transformer root expanded. SVG root: 85 × 98.43 mm, viewBox 0 0 696 806. Both full DOM snapshots are byte identical, report saved/rev 1, and contain no dialog token; DOM equality is not screenshot proof.

The public scene contains 12 visible node cards/containers, 12 routes (6 data, 3 mask, 2 residual, 1 memory), and 24 public ports. Each route is an untransformed orthogonal M/L/H/V path. All 24 endpoints match the canonical role-specific public port within 0.051 scene units; the maximum retained rounding difference is {report['endpointSummary']['maxDistanceSceneUnits']:.6f}. Eleven main collapsed/front rectangles have {len(report['mainCardOverlaps'])} pair overlaps and {len(report['mainCardRoutePenetrations'])} route segments entering their strict open interiors. The expanded enclosing Transformer is not a leaf obstacle.

The repeat encoder has two decorative stack backplates. The memory route edge:44 traverses their exposed right strips ({len(report['repeatBackplateRoutePenetrations'])} segment/backplate incidences); they are retained separately, not silently treated as clean space. Distinct routes have {summary['distinctRoutePairs']} intersecting pairs, with serialized segment incidences {json.dumps(summary['segmentIncidenceTypes'], ensure_ascii=False)}. Collinear mask/mask and mask/residual spans and point contacts at y=209 and y=397 remain explicit in JSON. This is not an all-clear routing finding.

This independent stdlib script imports no product or old audit helper. It certifies source geometry only. It does not certify pixels, arrowheads, tiny text, typography, capture synchronization, live persistence, model execution, runtime fidelity, performance or human acceptance. The parent's actual primer modal mismatch is neither disproved nor explained by the structure checks.
'''
(OUT / 'transformer-level0-paper-85-source-geometry.md').write_text(md)
print(json.dumps({'json': bind(json_path), 'md': bind(OUT / 'transformer-level0-paper-85-source-geometry.md'), 'script': bind(Path(__file__)), 'inputsUnchanged': report['inputsUnchanged'], 'bindingEquality': binding_equality, 'endpointSummary': report['endpointSummary'], 'mainCardOverlaps': len(report['mainCardOverlaps']), 'mainCardRoutePenetrations': len(report['mainCardRoutePenetrations']), 'repeatBackplateRoutePenetrations': report['repeatBackplateRoutePenetrations'], 'routeIntersectionSummary': summary}, ensure_ascii=False, indent=2))
