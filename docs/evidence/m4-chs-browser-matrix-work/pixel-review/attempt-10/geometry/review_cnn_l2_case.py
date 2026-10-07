"""Read-only parameterized ResidualCNN L2 source geometry audit, derived from this review's own first-case script; no product imports or browser actions."""
from pathlib import Path
import collections
import hashlib
import itertools
import json
import math
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
CASE_NAME = sys.argv[1]
assert CASE_NAME in {"residual_cnn-level2-paper-85", "residual_cnn-level2-paper-180", "residual_cnn-level2-monochrome-85", "residual_cnn-level2-monochrome-180"}
CASE = ROOT / "raw" / CASE_NAME
EXPECTED_PRESET = "monochrome" if "monochrome" in CASE_NAME else "paper"
OBSERVATION_NAME = "dom-observation-correct-variant.json" if CASE_NAME.endswith("recapture1") else "dom-observation.json"
OUT = Path(__file__).resolve().parent
NAMES = ['before.dom.txt', 'after.dom.txt', 'browser-scene.svg', 'saved-envelope.json', 'saved-envelope.json.receipt.json', 'observed-href.txt', 'export-complete.dom.txt', 'post-close.dom.txt']
NAMES += [p.name for p in sorted(CASE.glob('dom-observation*.json'))]



def bind(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


initial = [bind(CASE / name) for name in NAMES]
svg = ET.parse(CASE / "browser-scene.svg").getroot()
metadata = json.loads(next(x for x in svg if x.tag.endswith("metadata")).text)
observation = json.loads((CASE / OBSERVATION_NAME).read_text())
envelope = json.loads((CASE / "saved-envelope.json").read_text())
document = envelope["document"]
receipt = json.loads((CASE / "saved-envelope.json.receipt.json").read_text())
doms = {name: (CASE / name).read_text() for name in NAMES if name.endswith(".dom.txt")}
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
    "canvasDocumentRevision": int(svg.attrib["data-revision"]) == metadata["revision"] == document["revision"] == public_binding["revision"],
    "topLevelEnvelopeRevisionVsDocument": envelope["revision"] == document["revision"],
    "sourceDigestDeclarations": metadata["sourceDigest"] == document["sourceBindingDigest"] == document["architecture"]["sourceDigest"] == public_binding["sourceDigest"],
    "irDigestDeclarations": metadata["irDigest"] == document["architecture"]["irDigest"] == public_binding["irDigest"],
    "pageWidthMm": float(svg.attrib["width"].removesuffix("mm")) == metadata["widthMm"] == document["pageSpec"]["widthMm"] == observation["pageSpec"]["widthMm"],
    "pagePreset": document["pageSpec"]["preset"] == observation["pageSpec"]["preset"] == EXPECTED_PRESET,
    "expandedIds": document["expandedIds"] == observation["expandedIds"] == ["call:instance:model.ResidualCNN", "repeat:instance:model.ResidualCNN.blocks", "call:instance:model.ResidualCNN.blocks.0", "call:instance:model.ResidualCNN.blocks.1"],
    "renderedNodeIds": {n["id"] for n in visible_nodes} == {n["sceneNodeId"] for n in metadata["renderedNodes"]},
    "renderedEdgeIds": {r["id"] for r in routes} == set(bindings),
    "saveReceiptSnapshotDigest": receipt["sha256"] == initial[NAMES.index("saved-envelope.json")]["sha256"],
    "saveReceiptSnapshotBytes": receipt["bytes"] == initial[NAMES.index("saved-envelope.json")]["bytes"],
}
dom_checks = {}
for name, value in doms.items():
    dom_checks[name] = {
        "containsDialogToken": bool(re.search(r"^\s*- (?:alert)?dialog\b", value, re.M)),
        "savedHeader": '- generic: 已保存' in value,
        "matchingRevisionFooter": f'- generic: rev {document["revision"]}' in value,
        "matchingPageWidth": f'- text: {document["pageSpec"]["widthMm"]} mm' in value,
        "matchingPagePresetBanner": ('- text: PAPER COLOR' if EXPECTED_PRESET == 'paper' else '- text: MONOCHROME') in value,
        "rootCollapseControl": 'Collapse ResidualCNN' in value,
        "stemExpandControl": 'Expand stem' in value,
        "blocksCollapseControl": 'Collapse blocks' in value,
        "allSvgEdgeRoleTitlesPresent": all(f'{r["id"]} · {r["role"]} · {r["tensorId"]}' in value for r in routes),
        "allSvgNodeLabelsPresent": all(n['label'] in value for n in visible_nodes),
    }
    if name == 'export-complete.dom.txt':
        dom_checks[name].update({
            "matchingModalRevision": f'视觉版本 {document["revision"]}' in value,
            "matchingModalCustomWidth": f'- spinbutton "自定义导出宽度": "{document["pageSpec"]["widthMm"]}"' in value,
            "fileGeneratedSvg": '文件已生成 · SVG' in value,
            "matchingObservedExportUrl": observation['actualExport']['observedUrl'] in value,
            "preflightDomText": [line.strip() for line in value.splitlines() if 'pt ·' in line or '至少' in line or '页面 ' in line or '字号按导出尺寸' in line],
        })

end = [bind(CASE / name) for name in NAMES]
report = {
    "scope": "Independent read-only public SVG/full DOM/stored snapshot source geometry review of " + CASE_NAME,
    "caseId": CASE_NAME,
    "acquisitionNote": "All assigned structural input files bound before this script's content parsing and independently rehashed at finish; agent initial batch binding also preceded new-case content reads. L0 cases had been independently reviewed earlier; ResidualCNN L2 specific applicability was inspected before reuse of this review's own parameterized script. This is not a proof of immutable first acquisition or capture synchronization.",
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
    "observationFileUsed": OBSERVATION_NAME,
    "revisionDeclarations": {'svgRoot': svg.attrib['data-revision'], 'svgMetadata': metadata['revision'], 'canvasDocument': document['revision'], 'envelopeTopLevel': envelope['revision'], 'domObservation': public_binding['revision']},
    "revisionLimit": 'Top-level envelope revision is a separately recorded declaration; its semantic relation to CanvasDocument.revision is not independently established here. No stale-save or defect inference from numerical difference.',
    "hrefChecks": {
        'observedHrefFile': (CASE / 'observed-href.txt').read_text().strip(),
        'observationActualExport': observation.get('actualExport'),
        'observationSourceScene': observation.get('sourceScene'),
        'exportCompleteViewSvgLinks': re.findall(r'- link "查看 SVG":\n\s+- /url: (\S+)', doms['export-complete.dom.txt']),
        'hrefVsActualExport': (CASE / 'observed-href.txt').read_text().strip() == observation['actualExport']['observedUrl'],
        'hrefVsModalViewSvg': re.findall(r'- link "查看 SVG":\n\s+- /url: (\S+)', doms['export-complete.dom.txt']) == [(CASE / 'observed-href.txt').read_text().strip()],
        'limit': 'Actual observed href/DOM declarations compared, not predicted URL or network fetch. SourceScene is recorded if present, otherwise unavailable.'
    },
    "applicability": {
        "independentImplementation": "stdlib XML/JSON parsing and explicit M/L/H/V route parser, derived from the independent first-case script in this new matrix review; no historical helper or product import",
        "routeCount": len(routes),
        "frontCardCount": len(cards),
        "expandedContainerCount": len(containers),
        "repeatDecorativeBackplateCount": len(backplates),
        "publicPortCount": len(ports),
        "ancestorTransformCountForAuditedCardsRoutesPorts": 0,
        "endpointToleranceSceneUnits": 0.051,
        "toleranceReason": "Route coordinate serialization uses tenths in some endpoint values while matching public circle coordinates may use hundredths (the exact endpoint errors of this case remain recorded). Exact differences are retained.",
        "rectangleDefinition": "Strict open axis-aligned interior of each main/front collapsed card; expanded root enclosing rectangle and same-node repeat stack backplates are separately classified. Rounded corners and stroke outlines are not resolved by this test.",
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
    "limits": ["Source geometry only. No images opened by this reviewer; no pixel conclusions, raster synchronization, arrowhead legibility, font glyph bounds, text clipping/readability, runtime model fidelity, native browser/version/hardware lock, performance or human acceptance certified.", "Declared source/IR digest consistency is checked, not independently recomputed from source here.", "Saved snapshot receipt consistency does not prove live store bytes, save success, or receipt acquisition method.", "Before/after DOM byte equality and matching field declarations do not prove screenshot state; parent's separately reviewed raster/public-field differences remains untouched.", "Mask/residual route contacts and overlaps remain findings; correct endpoints and zero main-card penetration do not imply all routes are distinguishable."]
}
view_width = float(svg.attrib['viewBox'].split()[2])
font_sizes = sorted({float(element.attrib['font-size']) for element in svg.iter() if 'font-size' in element.attrib})
physical_factor = metadata['widthMm'] / view_width * 72 / 25.4
report['physicalScaleSummary'] = {
    'declaredMmWidth': metadata['widthMm'],
    'declaredMmHeight': metadata['heightMm'],
    'viewBoxWidth': view_width,
    'fontSizeSceneUnitsPresent': font_sizes,
    'minEmittedFontSizePt': min(font_sizes) * physical_factor,
    'nodeName13SceneUnitsPt': 13 * physical_factor,
    'routeStroke1p5SceneUnitsPt': 1.5 * physical_factor,
    'limits': 'Nominal serialized units only; fitted same-size scene or emitted font units do not certify physical-page text readability, resolved fonts, glyph bounds, arrowheads, or distinguishable routes.'
}
vb_x, vb_y, vb_width, vb_height = map(float, svg.attrib['viewBox'].split())
all_rects = cards + containers + backplates
rect_outside = []
for rect in all_rects:
    if rect['x'] < vb_x or rect['y'] < vb_y or rect['x'] + rect['width'] > vb_x + vb_width or rect['y'] + rect['height'] > vb_y + vb_height:
        rect_outside.append(rect)
route_outside = [{'edgeId': route['id'], 'pointIndex': index, 'point': point} for route in routes for index, point in enumerate(route['points']) if not (vb_x <= point[0] <= vb_x + vb_width and vb_y <= point[1] <= vb_y + vb_height)]
report['viewBoxBoundsCheck'] = {
    'viewBox': [vb_x, vb_y, vb_width, vb_height],
    'auditedRectCount': len(all_rects),
    'rectangleBoundsOutside': rect_outside,
    'routePointBoundsOutside': route_outside,
    'limits': 'Paper SVG viewBox only, not Studio workspace. Axis-aligned nominal rectangle and serialized route point bounds only. Does not certify emitted glyph extents, stroke/marker extents, font resolution, browser clipping, workspace grid state or all visible pixels.'
}
OUT.mkdir(parents=True, exist_ok=True)
json_path = OUT / (CASE_NAME + '-source-geometry.json')
json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
summary = report['routeIntersectionSummary']
md = f"""# {CASE_NAME} source geometry review

{len(NAMES)} assigned structural inputs were bound and rehashed unchanged at finish. SVG/meta/CanvasDocument/DOM observation agree on revision {document['revision']}; top-level envelope revision is separately {envelope['revision']}, with semantics not independently established here. Other bindings, {EXPECTED_PRESET} width {metadata['widthMm']} mm and four ResidualCNN/container expanded IDs agree. SVG: {svg.attrib['width']} × {svg.attrib['height']}, viewBox {svg.attrib['viewBox']}. Final before/after DOM is byte identical and contains no dialog. Export-complete contains a modal; post-close is nonmodal. Declared observed href matches the actual DOM View SVG link and actualExport field. SourceScene is {observation.get('sourceScene')}. DOM equality is not raster state proof.

All {len(routes)} routes / {len(routes)*2} role-specific endpoints match within the 0.051 scene-unit serialization rounding tolerance (max {report['endpointSummary']['maxDistanceSceneUnits']:.6f}). {len(cards)} main front card rectangles have {len(report['mainCardOverlaps'])} pair overlaps and {len(report['mainCardRoutePenetrations'])} segment/card penetrations. {len(containers)} expanded enclosing rectangles are containers, not leaf obstacles. {len(backplates)} decorative backplates have {len(report['repeatBackplateRoutePenetrations'])} route penetration incidences. {summary['distinctRoutePairs']} distinct route pairs retain segment incidence types {json.dumps(summary['segmentIncidenceTypes'])}. Every route and rectangle is tested; endpoint agreement does not imply clean or distinguishable routing.

Nominal min emitted font size is {report['physicalScaleSummary']['minEmittedFontSizePt']:.4f} pt; node-name 13 scene units is {report['physicalScaleSummary']['nodeName13SceneUnitsPt']:.4f} pt. Fit scene shape does not prove readability at physical size. This is source geometry only, no image review, glyph or arrowhead certification, raster synchronization, live-store acquisition proof, runtime/performance or human acceptance. L0/L1 reports are retained unchanged; excluded raw captures are not matrix coverage.
"""
md_path = OUT / (CASE_NAME + '-source-geometry.md')
md_path.write_text(md)
print(json.dumps({'json': bind(json_path), 'md': bind(md_path), 'inputsUnchanged': report['inputsUnchanged'], 'endpointSummary': report['endpointSummary'], 'routeIntersectionSummary': report['routeIntersectionSummary'], 'mainCardOverlaps': len(report['mainCardOverlaps']), 'mainCardRoutePenetrations': len(report['mainCardRoutePenetrations']), 'repeatBackplateRoutePenetrations': len(report['repeatBackplateRoutePenetrations']), 'bindingEquality': binding_equality, 'revisionDeclarations': report['revisionDeclarations'], 'viewBoxBoundsCheck': report['viewBoxBoundsCheck']}, ensure_ascii=False, indent=2))
