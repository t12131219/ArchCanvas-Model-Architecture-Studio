#!/usr/bin/env python3
"""Read-only geometric review of root's saved actual old-build move artifacts."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from audit_geometry import ROOT, OUT, inspect, local, overlap, points


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


canvas_path = ROOT / "docs/evidence/browser-visual-matrix-boundary-final/captures/mlp-level1-paper-180/canvas.json"
canvas = json.loads(canvas_path.read_text())
canonical = {node["id"]: node for node in canvas["architecture"]["nodes"]}
target_id = "call:instance:model.MLP.network.0"
source = ROOT / "docs/evidence/m4-ai-usability-next/shared-ui"
out = OUT / "saved-ui-svg"
out.mkdir(exist_ok=True)
cases = []
for direction in ("left", "right", "up", "down"):
    for phase in ("before", "moved", "undo", "redo"):
        case_id = f"move-{direction}-{phase}"
        raw_path = source / f"{case_id}.json"
        raw = json.loads(raw_path.read_text())
        svg_path = out / f"{case_id}.svg"
        svg_path.write_text(raw["svgMarkup"])
        screenshot = source / f"{case_id}.png"
        geometry = inspect(svg_path, canvas, case_id, screenshot)
        svg = ET.fromstring(raw["svgMarkup"])
        bodies, headers = {}, {}
        for group in svg.iter():
            if local(group.tag) != "g" or not group.get("data-canonical-id"):
                continue
            node_id = group.get("data-node-id")
            body = next(child for child in group if local(child.tag) == "rect" and child.get("opacity") is None)
            x, y, width, height = (float(body.get(field)) for field in ("x", "y", "width", "height"))
            bodies[node_id] = (x, y, x + width, y + height)
            separator = next((child for child in group if local(child.tag) == "path" and child.get("opacity") == ".28"), None)
            if separator is not None:
                separators = points(separator.get("d"))
                assert len(separators) == 2 and separators[0][1] == separators[1][1]
                headers[node_id] = (x, y, x + width, separators[0][1])
        overlaps = []
        for node_id, body in bodies.items():
            parent = canonical[node_id].get("parentId")
            while parent:
                if parent in headers and overlap(body, headers[parent]) > .15:
                    overlaps.append({"nodeId": node_id, "ancestorId": parent, "visibleHeaderOverlapArea": overlap(body, headers[parent])})
                parent = canonical[parent].get("parentId")
        geometry.update({"rawJsonPath": str(raw_path.relative_to(ROOT)), "rawJsonSha256": digest(raw_path),
                         "capturedAt": raw["capturedAt"], "status": raw["status"], "paperTransform": raw["paperTransform"],
                         "targetBody": list(bodies[target_id]), "ancestorVisibleHeaderOverlaps": overlaps})
        cases.append(geometry)

trials = []
for direction in ("left", "right", "up", "down"):
    selected = {case["caseId"].rsplit("-", 1)[1]: case for case in cases if case["caseId"].startswith(f"move-{direction}-")}
    before, moved = selected["before"]["targetBody"], selected["moved"]["targetBody"]
    assert selected["undo"]["targetBody"] == before
    assert selected["redo"]["targetBody"] == moved
    assert len({case["paperTransform"] for case in selected.values()}) == 1
    trials.append({"direction": direction, "dx": moved[0] - before[0], "dy": moved[1] - before[1],
                   "undoRestoresBodyExactly": True, "redoRestoresBodyExactly": True, "cameraTransformUnchanged": True})

output = {"schemaVersion": 1,
          "scope": "Independent read-only review of 16 saved actual old-build move SVG/JSON/PNG artifacts; no new UI operation and no coverage transfer to DgtJrWU9",
          "humanAcceptanceCertified": False,
          "canonicalCanvasPath": str(canvas_path.relative_to(ROOT)), "canonicalCanvasSha256": digest(canvas_path),
          "scriptSha256": digest(Path(__file__)), "trials": trials, "cases": cases,
          "limitations": ["Route-body oracle uses a 2-unit interior inset and 0.15-unit saved-dot endpoint tolerance.",
                          "Visible-header overlap uses the saved expanded-frame separator line; it excludes the four-unit padding below that line.",
                          "Pixel readability, presentation timing and publication acceptance are not certified."]}
(OUT / "shared-ui-move-geometry.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"trials": trials, "cases": len(cases),
                  "endpointDefects": sum(len(case["endpointDefects"]) for case in cases),
                  "unrelatedBodyPenetrations": sum(len(case["unrelatedBodyPenetrations"]) for case in cases),
                  "visibleHeaderOverlaps": [{"caseId": case["caseId"], "overlaps": case["ancestorVisibleHeaderOverlaps"]} for case in cases if case["ancestorVisibleHeaderOverlaps"]]}, indent=2))
