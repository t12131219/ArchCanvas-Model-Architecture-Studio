"""Read-only, standard-library derivation of saved DOM/pixel cross-check evidence.

This does not operate the browser, recreate a lost operator journal, or certify paint.
"""

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


OUT = Path(__file__).resolve().parent
PROJECT = OUT.parents[4]
RAW_DIR = OUT.parent / "mlp-four-directions-1"
TARGET = "call:instance:model.MLP.network.0"
PARENT = "call:instance:model.MLP.network"
ROOT = "call:instance:model.MLP"
CASE_TRIALS = {
    "right": 0, "left": 3, "up": 5, "down": 7,
    "pan-right": 9, "pan-left": 10, "pan-up": 11, "pan-down": 12,
}


def binding(path):
    content = path.read_bytes()
    return {"path": str(path), "sha256": sha256(content).hexdigest(), "bytes": len(content)}


def points(path):
    tokens = re.findall(r"[A-Za-z]|-?\d+(?:\.\d+)?", path)
    result = []
    index = 0
    while index < len(tokens):
        command = tokens[index]
        index += 1
        if command in ("M", "L"):
            result.append([float(tokens[index]), float(tokens[index + 1])])
            index += 2
        elif command == "H":
            result.append([float(tokens[index]), result[-1][1]])
            index += 1
        elif command == "V":
            result.append([result[-1][0], float(tokens[index])])
            index += 1
        else:
            raise ValueError(f"Unsupported command in recorded edge path: {command}")
    return result


def extract(scene):
    tree = ET.fromstring(scene["svgMarkup"])
    bodies, ports, edges = {}, {}, {}
    metadata = None
    for element in tree.iter():
        if element.tag.endswith("metadata"):
            metadata = json.loads(element.text)
        if "data-node-id" in element.attrib:
            body = next((child for child in element if child.tag.endswith("rect")), None)
            if body is not None:
                bodies[element.attrib["data-node-id"]] = {
                    key: float(body.attrib[key]) for key in ("x", "y", "width", "height")
                }
        if "data-port-id" in element.attrib:
            circle = next(child for child in element if child.tag.endswith("circle"))
            ports[element.attrib["data-port-id"]] = [float(circle.attrib["cx"]), float(circle.attrib["cy"])]
        if "data-edge-id" in element.attrib:
            path = next(child for child in element if child.tag.endswith("path"))
            edges[element.attrib["data-edge-id"]] = {
                "d": path.attrib["d"], "markerEnd": path.attrib.get("marker-end"),
                "tensorId": element.attrib["data-tensor-id"], "points": points(path.attrib["d"]),
            }
    return {"bodies": bodies, "ports": ports, "edges": edges, "metadata": metadata,
            "svgAttributes": tree.attrib}


def simplified(sequence):
    out = []
    for point in sequence:
        if out and point == out[-1]:
            continue
        out.append(point)
        while len(out) > 2:
            a, b, c = out[-3:]
            if a[0] == b[0] == c[0] or a[1] == b[1] == c[1]:
                out.pop(-2)
            else:
                break
    return out


def overlap(a, b):
    width = max(0, min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"]))
    height = max(0, min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"]))
    return {"width": width, "height": height, "area": width * height}


def interior_hits(sequence, body):
    hits = []
    x0, x1 = body["x"], body["x"] + body["width"]
    y0, y1 = body["y"], body["y"] + body["height"]
    for index, (a, b) in enumerate(zip(sequence, sequence[1:])):
        if a == b:
            continue
        if a[0] == b[0] and x0 < a[0] < x1:
            start, end = max(y0, min(a[1], b[1])), min(y1, max(a[1], b[1]))
            if start < end:
                hits.append({"segmentIndex": index, "interiorLength": end - start})
        elif a[1] == b[1] and y0 < a[1] < y1:
            start, end = max(x0, min(a[0], b[0])), min(x1, max(a[0], b[0]))
            if start < end:
                hits.append({"segmentIndex": index, "interiorLength": end - start})
    return hits


def proper_crossings(extracted):
    hits = []
    items = list(extracted["edges"].items())
    for i, (left_id, left) in enumerate(items):
        for right_id, right in items[i + 1:]:
            found = set()
            for a, b in zip(left["points"], left["points"][1:]):
                for c, d in zip(right["points"], right["points"][1:]):
                    if a == b or c == d:
                        continue
                    if a[1] == b[1] and c[0] == d[0]:
                        x, y = c[0], a[1]
                        if min(a[0], b[0]) < x < max(a[0], b[0]) and min(c[1], d[1]) < y < max(c[1], d[1]):
                            found.add((x, y))
                    elif a[0] == b[0] and c[1] == d[1]:
                        x, y = a[0], c[1]
                        if min(c[0], d[0]) < x < max(c[0], d[0]) and min(a[1], b[1]) < y < max(a[1], b[1]):
                            found.add((x, y))
            for point in sorted(found):
                hits.append({"edges": [left_id, right_id], "point": list(point),
                             "sameTensor": left["tensorId"] == right["tensorId"]})
    return hits


def route_audit(extracted):
    records = []
    for edge in extracted["metadata"]["renderedBindings"]:
        edge_id = edge["sceneEdgeId"]
        route = extracted["edges"][edge_id]
        source = edge["source"]
        target = edge["target"]
        source_port = f'{source["nodeId"]}:{source["portId"]}:data'
        target_port = f'{target["nodeId"]}:{target["portId"]}:data'
        simple = simplified(route["points"])
        leaf_hits = []
        for node_id, body in extracted["bodies"].items():
            if node_id in (ROOT, PARENT):
                continue
            hits = interior_hits(route["points"], body)
            if hits:
                leaf_hits.append({"nodeId": node_id, "role": "source" if node_id == source["nodeId"] else "target" if node_id == target["nodeId"] else "other", "segments": hits})
        records.append({
            "edgeId": edge_id, "binding": edge, **route,
            "sourcePublicPort": extracted["ports"][source_port],
            "targetPublicPort": extracted["ports"][target_port],
            "startMatchesPublicPort": route["points"][0] == extracted["ports"][source_port],
            "endMatchesPublicPort": route["points"][-1] == extracted["ports"][target_port],
            "allSegmentsOrthogonal": all(a[0] == b[0] or a[1] == b[1] for a, b in zip(route["points"], route["points"][1:])),
            "nonzeroSimplifiedBends": max(0, len(simple) - 2),
            "leafBodyInteriorIntersections": leaf_hits,
        })
    return {"routes": records, "strictInteriorPerpendicularCrossings": proper_crossings(extracted),
            "definition": "Perpendicular intersections strictly inside both nonzero segments; excludes endpoints, collinear overlap, T-contact, marker outlines and same-source branching. This is not a global route necessity/aesthetic proof."}


def normalize_svg_without_revision(markup):
    root = ET.fromstring(markup)
    root.attrib.pop("data-revision", None)
    for element in root.iter():
        if element.tag.endswith("metadata"):
            metadata = json.loads(element.text)
            metadata.pop("revision", None)
            element.text = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
    return ET.tostring(root, encoding="unicode")


def main():
    raw_path = RAW_DIR / "raw-full.json"
    raw_text = raw_path.read_text()
    raw = json.loads(raw_text)
    pixel_path = OUT / "mlp-four-directions-pixel-observations.json"
    pixels = json.loads(pixel_path.read_text())
    pixel_cases = {case["name"]: case for case in pixels["cases"]}
    reassembly = json.loads((RAW_DIR / "raw-reassembly.json").read_text())
    parts = sorted(reassembly["parts"], key=lambda item: item["offset"])
    rebuilt = ""
    for item in parts:
        path = RAW_DIR / "raw-chunks" / item["path"]
        part = path.read_text()
        assert binding(path)["sha256"] == item["sha256"]
        assert binding(path)["bytes"] == item["bytes"]
        # The textarea offsets are JavaScript UTF-16 code units.
        assert len(part.encode("utf-16-le")) // 2 == item["characters"]
        assert len(rebuilt.encode("utf-16-le")) // 2 == item["offset"]
        rebuilt += part
    assert rebuilt == raw_text
    cases = []
    for name, index in CASE_TRIALS.items():
        trial = raw["trials"][index]
        before, after = trial["before"], trial["after"]
        a, b = extract(before), extract(after)
        image_binding = binding(RAW_DIR / f"{name}.jpg")
        assert image_binding == pixel_cases[name]["inputBinding"]
        visible_xy = {k: float(v) for k, v in pixel_cases[name]["pixelObservations"]["visibleCoordinateFields"].items()}
        assert all(b["bodies"][TARGET][key] == value for key, value in visible_xy.items())
        events = [event for event in raw["events"] if event["trialId"] == trial["id"]]
        down = next(event for event in events if event["type"] == "pointerdown")
        up = next(event for event in events if event["type"] == "pointerup")
        camera_delta = {k: after["camera"]["matrix"][k] - before["camera"]["matrix"][k] for k in ("a", "b", "c", "d", "e", "f")}
        selected_delta = {k: b["bodies"][TARGET][k] - a["bodies"][TARGET][k] for k in ("x", "y", "width", "height")}
        body, parent = b["bodies"][TARGET], b["bodies"][PARENT]
        header = {**parent, "height": 42.0}
        checks = {key: before[key] == after[key] for key in ("documentId", "sourceDigest", "irDigest", "visibleIds", "expandedIds", "pinnedIds")}
        checks["cameraScaleStable"] = all(camera_delta[k] == 0 for k in ("a", "b", "c", "d"))
        case = {
            "name": name, "trialId": trial["id"], "trialIndex": index,
            "operation": trial["spec"]["operation"], "status": trial["status"],
            "screenshot": image_binding,
            "screenshotAssociation": "Operator-supplied chronological filenames plus independently observed inspector coordinates and pan displacement. No surviving operator capture journal/timestamp binds the JPEG atomically to this trial.",
            "pixelCoordinatesMatchRecordedPublicSVGBody": True,
            "before": {key: before[key] for key in ("at", "revision", "camera", "viewport", "frameRect", "objects", "documentId", "sourceDigest", "irDigest", "visibleIds", "expandedIds", "pinnedIds", "selectionMarkup")},
            "after": {key: after[key] for key in ("at", "revision", "camera", "viewport", "frameRect", "objects", "documentId", "sourceDigest", "irDigest", "visibleIds", "expandedIds", "pinnedIds", "selectionMarkup")},
            "publicSVG": {"beforeSha256": sha256(before["svgMarkup"].encode()).hexdigest(), "afterSha256": sha256(after["svgMarkup"].encode()).hexdigest(), "beforeBodies": a["bodies"], "afterBodies": b["bodies"], "svgAttributesAfter": b["svgAttributes"]},
            "continuityChecks": checks,
            "changedBodyIds": [key for key in a["bodies"] if a["bodies"][key] != b["bodies"][key]],
            "changedRouteIds": [key for key in a["edges"] if a["edges"][key] != b["edges"][key]],
            "selectedBodyCanvasDelta": selected_delta, "cameraDeltaCSSPixels": camera_delta,
            "inputSummary": {"eventCount": len(events), "pointerdown": {key: down[key] for key in ("id", "x", "y", "trusted", "pointerId", "button", "target")}, "pointerup": {key: up[key] for key in ("id", "x", "y", "trusted", "pointerId", "button", "target")}, "pointerDeltaCSSPixels": {"x": up["x"] - down["x"], "y": up["y"] - down["y"]}, "trustedFlagsAllTrue": all(event["trusted"] for event in events), "sameTerminalPointerId": down["pointerId"] == up["pointerId"]},
            "bodyAudit": {"selectedContainedInKnownNetworkBody": body["x"] >= parent["x"] and body["y"] >= parent["y"] and body["x"] + body["width"] <= parent["x"] + parent["width"] and body["y"] + body["height"] <= parent["y"] + parent["height"], "leftEscapeCanvasUnits": max(0, parent["x"] - body["x"]), "networkHeaderOverlap": overlap(body, header), "gelu2Overlap": overlap(body, b["bodies"]["call:instance:model.MLP.network.1"]), "headerDefinition": "Known network SVG body top42 units, corroborated by recorded header divider path at y296; not an inferred generic parent relation."},
            "routeAudit": route_audit(b),
            "pixelResult": pixel_cases[name]["pixelObservations"],
        }
        if name.startswith("pan-"):
            case["exactPublicSVGUnchanged"] = before["svgMarkup"] == after["svgMarkup"]
            case["selectionMarkupUnchanged"] = before["selectionMarkup"] == after["selectionMarkup"]
            case["cameraDeltaMatchesPointerDelta"] = abs(camera_delta["e"] - (up["x"] - down["x"])) < .001 and abs(camera_delta["f"] - (up["y"] - down["y"])) < .001
        else:
            undo = raw["trials"][index + 1]
            assert undo["spec"]["operation"] == "undo"
            case["undoCrossCheck"] = {"trialId": undo["id"], "publicBodyReturnsToBefore": extract(undo["after"])["bodies"] == a["bodies"], "publicSVGExcludingRevisionReturnsToBefore": normalize_svg_without_revision(undo["after"]["svgMarkup"]) == normalize_svg_without_revision(before["svgMarkup"]), "selectionMarkupReturnsToBefore": undo["after"]["selectionMarkup"] == before["selectionMarkup"], "hiddenHistoryEqualityCertified": False}
        cases.append(case)
    report = {
        "schema": "archcanvas.bcf-native-four-directions-independent-dom-pixel-cross-check.v1",
        "createdAtUtc": datetime.now(timezone.utc).isoformat(),
        "reviewer": "Codex subagent /root/proxy_novice",
        "inputBindings": [binding(path) for path in (raw_path, RAW_DIR / "raw-reassembly.json", RAW_DIR / "raw-chunk-index.json", RAW_DIR / "raw.json", pixel_path)],
        "rawReassemblyIndependentlyChecked": {"chunks": len(parts), "allChunkHashesAndUTF16OffsetsMatch": True, "joinedRawEqualsSavedRawFullBytes": True},
        "originalSingleReadRaw": {"status": "preserved-invalid-truncated-json", "replacedOrRepaired": False},
        "environment": raw["environment"], "harness": raw["harness"],
        "measurement": raw["measurement"], "context": raw["context"], "buffers": raw["buffers"],
        "scope": "8 actually individually viewed original JPEGs vs public-DOM observer16 recorded trials; numerical checks derive only from saved raw SVG, ports, input events and camera. Lost operator journal is not reconstructed.",
        "cases": cases,
        "rightRedoCrossCheck": {"trialId": raw["trials"][2]["id"], "publicSVGExcludingRevisionEqualsRightDrag": normalize_svg_without_revision(raw["trials"][2]["after"]["svgMarkup"]) == normalize_svg_without_revision(raw["trials"][0]["after"]["svgMarkup"])},
        "findings": [
            "All8 inspector coordinates match recorded selected body; all8 direction signs agree with trusted automation input sequences.",
            "All48 after-state route endpoints match the exact public SVG port circles; all recorded route segments are orthogonal. This does not certify unobstructed routes or marker appearance.",
            "Right drag expands network and root MLP widths52 units, moving network input port26 units and rerouting edge1 along with incident edges2/3.",
            "Left drag escapes known network left boundary22 units; pixel-only near-edge phrasing is superseded by this independent geometry finding.",
            "Up drag overlaps known network title/header by32 units vertically; the screenshot warning names this condition. It also creates common-tensor route contacts whose aesthetics are not certified.",
            "Down drag overlaps GELU2 by14 units vertically; edge3 has4 nonzero bends and crosses source/target card interiors due to overlap. It is not a clean route/layout pass.",
            "All4 pan trials keep exact SVG and selection markup equal before/after; camera translations equal pointer displacements40/40/32/32 CSS pixels and agree with coarse paper shifts in pixels.",
            "All4 undo trials restore pre-drag public SVG after removing only revision fields. First right-drag undo retains selection where before was unselected, so selection equality is false; hidden history equality is not certified.",
        ],
        "limitations": raw["limitations"] + [
            "JPEG-to-trial association has filenames, chronological operator account, visible coordinates and coarse pan shifts, but no surviving atomic operator capture journal/timestamp. A CUA timeout/reset lost that journal; this derivative is not a replacement raw journal.",
            "JPEG1425x1089 differs from declared outer1440x1100 and inner1280x720. Dimensions are retained separately; screenshots are not rescaled or interpreted as physical-size proof.",
            "Strict-interior perpendicular crossing count excludes collinear shared paths, T-contacts, endpoints, node/marker overlaps and aesthetic necessity. Zero such crossings is not a clean-layout certificate.",
            "Raw warning HTML is not part of saved public SVG observations; warning text comes from actual screenshot review, not reconstructed DOM.",
            "Frames/frameCallbacks dropped4102 entries; this is not a native performance pass, direct non-iframe measurement, resolved-font lock, human novice trial or physical publication review.",
            "AI subagents do not count as human researchers, novice participants or publication reviewers. M4 acceptance remains partial.",
        ],
        "humanAcceptanceCertified": False, "nativePerformanceCertified": False, "physicalPublicationCertified": False,
    }
    for case in cases:
        assert all(case["continuityChecks"].values())
        assert all(route["startMatchesPublicPort"] and route["endMatchesPublicPort"] and route["allSegmentsOrthogonal"] for route in case["routeAudit"]["routes"])
    output = OUT / "mlp-four-directions-journal-cross-check.json"
    assert not output.exists(), "Evidence output exists; preserve original and choose a new derivation name"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(binding(output), ensure_ascii=False))


if __name__ == "__main__":
    main()
