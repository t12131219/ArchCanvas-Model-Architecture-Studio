"""Read only edited snapshot/public SVG comparisons; no operation-history proof."""
from pathlib import Path
import hashlib
import json
import sys
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
BASE = OUT.parents[2]
CASE_ID, BASELINE_ID = sys.argv[1:3]
CASE = BASE / "raw" / CASE_ID
BASELINE = BASE / "raw" / BASELINE_ID


def bind(path):
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


inputs = [CASE / "browser-scene.svg", CASE / "saved-envelope.json", BASELINE / "browser-scene.svg", BASELINE / "saved-envelope.json"]
inputs += sorted(CASE.glob("dom-observation*.json"))
start = [bind(path) for path in inputs]
saved = json.loads((CASE / "saved-envelope.json").read_text())["document"]
baseline = json.loads((BASELINE / "saved-envelope.json").read_text())["document"]
svg = ET.parse(CASE / "browser-scene.svg").getroot()
baseline_svg = ET.parse(BASELINE / "browser-scene.svg").getroot()
x, y, width, height = map(float, svg.attrib["viewBox"].split())


def difference(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        return [row for key in sorted(a.keys() | b.keys()) for row in (difference(a[key], b[key], path + "/" + key) if key in a and key in b else [{"jsonPointer": path + "/" + key, "baseline": a.get(key), "edited": b.get(key)}])]
    return [] if a == b else [{"jsonPointer": path, "baseline": a, "edited": b}]


fields = ["revision", "displayAliases", "annotations", "pinnedObjects", "nodeStyleOverrides", "edgeStyleOverrides", "legendItems", "layout", "layoutByFrontier", "expandedIds", "pageSpec"]
field_differences = {key: difference(baseline[key], saved[key], "/" + key) for key in fields if baseline[key] != saved[key]}
annotations = []
for group in svg.iter():
    if "data-annotation-id" not in group.attrib:
        continue
    annotation = next(item for item in saved["annotations"] if item["id"] == group.attrib["data-annotation-id"])
    rect = next(child for child in group if child.tag.endswith("rect"))
    text = next(child for child in group if child.tag.endswith("text"))
    nominal = {key: float(rect.attrib[key]) for key in ["x", "y", "width", "height"]}
    anchor_x, anchor_y = float(text.attrib["x"]), float(text.attrib["y"])
    annotations.append({
        "id": annotation["id"], "savedAnnotation": annotation, "svgRect": rect.attrib, "svgText": text.attrib,
        "textContent": "".join(text.itertext()),
        "tspans": [child.attrib | {"text": "".join(child.itertext())} for child in text if child.tag.endswith("tspan")],
        "textMatchesSaved": "".join(text.itertext()) == annotation["text"],
        "rectXYWidthMatchesSaved": all(nominal[key] == annotation[key] for key in ["x", "y", "width"]),
        "nominalRectInsidePaperViewBox": nominal["x"] >= x and nominal["y"] >= y and nominal["x"] + nominal["width"] <= x + width and nominal["y"] + nominal["height"] <= y + height,
        "textAnchorInsideRect": nominal["x"] <= anchor_x <= nominal["x"] + nominal["width"] and nominal["y"] <= anchor_y <= nominal["y"] + nominal["height"],
        "textAnchorInsidePaperViewBox": x <= anchor_x <= x + width and y <= anchor_y <= y + height,
        "nominalFontSizePt": float(text.attrib["font-size"]) * saved["pageSpec"]["widthMm"] / width * 72 / 25.4,
        "boundsLimit": "Nominal rectangle/text anchor only, no glyph extent, clipping or physical readability certificate.",
    })


def public_geometry(root):
    node_groups = [element for element in root.iter() if element.attrib.get("data-canonical-id")]
    edge_groups = [element for element in root.iter() if element.attrib.get("data-edge-id")]
    return {
        "nodes": {group.attrib["data-node-id"]: {"rects": [child.attrib for child in group if child.tag.endswith("rect")], "textAnchors": [child.attrib | {"text": "".join(child.itertext())} for child in group if child.tag.endswith("text")]} for group in node_groups},
        "routes": {group.attrib["data-edge-id"]: [child.attrib for child in group if child.tag.endswith("path")] for group in edge_groups},
    }


old = json.loads((CASE / "dom-observation-original-caseid.json").read_text()) if (CASE / "dom-observation-original-caseid.json").exists() else None
corrected = json.loads((CASE / "dom-observation-correct-variant.json").read_text()) if (CASE / "dom-observation-correct-variant.json").exists() else None
end = [bind(path) for path in inputs]
result = {
    "scope": "Append-only edited-case annotation/nominal geometry comparison, no operation history certification",
    "caseId": CASE_ID, "baselineCaseId": BASELINE_ID,
    "inputBindingsStart": start, "inputBindingsEnd": end, "inputsUnchanged": start == end,
    "baselineSvgRoot": baseline_svg.attrib, "editedSvgRoot": svg.attrib,
    "architectureDeepEqual": baseline["architecture"] == saved["architecture"],
    "sourceBindingDigestEqual": baseline["sourceBindingDigest"] == saved["sourceBindingDigest"],
    "documentFieldDifferences": field_differences,
    "publicNodeRouteGeometryExactDifferences": difference(public_geometry(baseline_svg), public_geometry(svg)),
    "annotations": annotations,
    "observationCorrectionExactDifference": difference(old, corrected) if old is not None and corrected is not None else None,
    "originalObservationByteEqual": (CASE / "dom-observation.json").read_bytes() == (CASE / "dom-observation-original-caseid.json").read_bytes() if old is not None else None,
    "limits": [
        "Final stored/public declaration comparison only, not proof of gestures, source edit, undo/redo, save acquisition, reopening, causal behavior or history.",
        "No image opened in this reviewer role. Parent pixel/modal/grid observations remain independent and unchanged.",
        "Nominal paper rect/anchor bounds do not certify glyph extents, font resolution, arrows/stroke/markers, workspace grid or pixels.",
        "Deep equal architecture/source declarations do not establish model runtime fidelity, performance or human acceptance.",
    ],
}
path = OUT / (CASE_ID + "-annotation-baseline-review.json")
assert not path.exists()
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
md = path.with_suffix(".md")
assert not md.exists()
md.write_text(f"# {CASE_ID} annotation/baseline review\n\nCompared final edited declarations with {BASELINE_ID}. Changed fields: {', '.join(field_differences)}. Architecture and source binding declarations equal: {result['architectureDeepEqual']}/{result['sourceBindingDigestEqual']}. SVG viewBox changes from{baseline_svg.attrib['viewBox']} to{svg.attrib['viewBox']}; nominal public node/route geometry difference count is{len(result['publicNodeRouteGeometryExactDifferences'])}.\n\n{len(annotations)} note(s) checked for exact saved/SVG text, rectangle position/width and text anchor inside nominal paper/rect bounds. Complete coordinates and nominal fontsize retained in JSON; glyph extent/clipping/readability unverified. This is final-state evidence, not operation history, runtime/performance, live-save acquisition, raster synchronization or human acceptance.\n")
print(json.dumps({"json": bind(path), "md": bind(md), "changedFields": list(field_differences), "publicGeometryDifferenceCount": len(result["publicNodeRouteGeometryExactDifferences"]), "inputsUnchanged": result["inputsUnchanged"], "annotations": annotations}, ensure_ascii=False, indent=2))
