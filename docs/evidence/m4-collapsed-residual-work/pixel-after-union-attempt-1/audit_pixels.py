"""Read-only evidence comparisons and serialization of already performed AI views.

This is an evidence helper, not a renderer, browser test, model runner or product
validator. Fixed observations below were written by the AI auditor after direct
tools.view_image inspection of the original JPEGs in this same session.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
NEW = ROOT / "docs/evidence/m4-collapsed-residual-work/browser-after-union"
OLD = ROOT / "docs/evidence/m4-au3-visual-matrix-work/raw"
STAMP = datetime.now(timezone.utc).isoformat()
CHECKS: list[dict] = []


def read_json(path: Path):
    return json.loads(path.read_text())


def binding(path: Path):
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def put(name: str, value):
    path = OUT / name
    if path.exists():
        raise RuntimeError(f"Do not overwrite evidence output: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return binding(path)


def check(name: str, passed: bool, detail=None):
    row = {"check": name, "passed": bool(passed)}
    if detail is not None:
        row["detail"] = detail
    CHECKS.append(row)
    return row


def without_time(value):
    return {k: v for k, v in value.items() if k != "capturedAt"}


def tag(el):
    return el.tag.split("}")[-1]


def signature(el, publication_node=False):
    # Publication intentionally excludes interactive expand controls and focus
    # attributes. All retained visual and canonical attributes stay compared.
    attrs = sorted((k, v) for k, v in el.attrib.items()
                   if not publication_node or k not in ("tabindex", "role"))
    children = [signature(c, publication_node) for c in el
                if not publication_node or "data-expand-id" not in c.attrib]
    return [tag(el), attrs, el.text or "", children]


def indexed(root, attribute):
    return {el.get(attribute): el for el in root.iter() if el.get(attribute)}


def port_visible(el):
    circle = el if tag(el) == "circle" else next(
        c for c in el if tag(c) == "circle" and c.get("fill") != "transparent")
    return {k: circle.get(k) for k in ("cx", "cy", "r", "fill")}


def path_geometry(path):
    tokens = re.findall(r"[MHV]|-?\d+(?:\.\d+)?", path)
    points, i, x, y = [], 0, 0.0, 0.0
    while i < len(tokens):
        command = tokens[i]
        i += 1
        if command == "M":
            x, y = float(tokens[i]), float(tokens[i + 1])
            i += 2
        elif command == "H":
            x = float(tokens[i])
            i += 1
        elif command == "V":
            y = float(tokens[i])
            i += 1
        else:
            raise ValueError(path)
        if not points or points[-1] != (x, y):
            points.append((x, y))
    length = sum(abs(a[0]-b[0]) + abs(a[1]-b[1])
                 for a, b in zip(points, points[1:]))
    directions = [("H" if a[1] == b[1] else "V")
                  for a, b in zip(points, points[1:])]
    bends = sum(a != b for a, b in zip(directions, directions[1:]))
    return {"path": path, "points": points, "manhattanLengthWorld": length,
            "bends": bends, "maxX": max(p[0] for p in points)}


def freeze_check(label, frozen):
    changed = []
    for original in frozen["inputs"]:
        path = ROOT / original["path"]
        actual = binding(path) if path.is_file() else {"path": original["path"], "missing": True}
        if actual != original:
            changed.append({"before": original, "after": actual})
    actual_paths = sorted(str(p.relative_to(ROOT)) for p in NEW.rglob("*") if p.is_file())
    frozen_paths = sorted(row["path"] for row in frozen["inputs"]
                          if row["path"].startswith(str(NEW.relative_to(ROOT)) + "/"))
    result = {"phase": label, "createdAt": datetime.now(timezone.utc).isoformat(),
              "boundInputs": len(frozen["inputs"]), "unchangedInputs": len(frozen["inputs"])-len(changed),
              "changed": changed, "currentActualFileCount": len(actual_paths),
              "actualInventoryExact": actual_paths == frozen_paths,
              "extraActualFiles": sorted(set(actual_paths)-set(frozen_paths)),
              "missingActualFiles": sorted(set(frozen_paths)-set(actual_paths))}
    check(f"input-freeze-{label}", not changed and actual_paths == frozen_paths,
          {"boundInputs": len(frozen["inputs"]), "actualFiles": len(actual_paths)})
    return result


frozen = read_json(OUT / "inputs-before.json")
start = freeze_check("before-final-comparisons", frozen)
case_rows, view_rows, old_rows = [], [], []

for folder in sorted(p for p in NEW.iterdir() if p.is_dir()):
    case = folder.name
    match = re.fullmatch(r"cnn-level([012])-(paper|monochrome)-(85|180)", case)
    if not match:
        raise ValueError(case)
    level, preset, width = int(match[1]), match[2], int(match[3])
    public = read_json(folder / "fit-before.json")
    document = read_json(folder / "document.json")
    envelope = read_json(folder / "saved-envelope.json")
    exported = ET.parse(folder / "figure.svg").getroot()
    interactive = ET.fromstring(public["svg"])
    export_meta = json.loads(next(e.text for e in exported if tag(e) == "metadata"))
    receipt = read_json(folder / "figure.svg.receipt.json")
    export_binding = read_json(folder / "export-binding.json")
    metadata_differences = [{"key": k, "public": public["metadata"].get(k),
                             "publication": export_meta.get(k)}
                            for k in sorted(set(public["metadata"]) | set(export_meta))
                            if public["metadata"].get(k) != export_meta.get(k)]
    metadata_close = all(row["key"] == "heightMm" and
                         math.isfinite(row["public"]) and math.isfinite(row["publication"]) and
                         abs(row["public"]-row["publication"]) <= 1e-10
                         for row in metadata_differences)
    check(f"{case}:publication-metadata", metadata_close, metadata_differences)
    identities = {
        "savedDocumentExact": envelope["document"] == document,
        "documentIdExact": public["metadata"]["documentId"] == document["id"] == receipt["documentId"] == exported.get("data-document-id"),
        "documentRevisionExact": public["revision"] == public["metadata"]["revision"] == document["revision"] == receipt["revision"] == export_binding["revision"] == int(exported.get("data-revision")),
        "storageRevisionExact": envelope["revision"] == export_binding["storageRevision"],
        "sourceDigestExact": public["metadata"]["sourceDigest"] == document["sourceBindingDigest"] == document["architecture"]["sourceDigest"] == receipt["sourceDigest"],
        "irDigestExact": public["metadata"]["irDigest"] == document["architecture"]["irDigest"] == receipt["irDigest"],
        "frontierExact": public["expandedIds"] == document["expandedIds"],
        "widthExact": width == public["metadata"]["widthMm"] == document["pageSpec"]["widthMm"] == receipt["widthMm"] == float(exported.get("width").removesuffix("mm")),
        "presetExact": preset == document["pageSpec"]["preset"],
        "hrefUuidExact": export_binding["href"] == f'/api/exports/{export_binding["uuid"]}/figure.svg',
        "receiptSourceDirectoryBound": receipt["path"] == export_binding["sourceDirectory"] + "/figure.svg" and Path(export_binding["sourceDirectory"]).name == export_binding["uuid"],
        "svgBytesDigestExact": binding(folder / "figure.svg")["bytes"] == receipt["bytes"] and binding(folder / "figure.svg")["sha256"] == receipt["outputDigest"] == receipt["svgDigest"],
        "viewBoxExact": interactive.get("viewBox") == exported.get("viewBox") and [float(n) for n in exported.get("viewBox").split()] == receipt["viewBox"],
        "assetNamesExact": {u.rsplit("/", 1)[-1] for u in public["assetUrls"]} == {"index-Dzp9we5t.js", "index-B6WbMowt.css"},
    }
    check(f"{case}:actual-document-export-bindings", all(identities.values()), identities)
    visible_groups = {}
    for key in ("data-edge-id", "data-canonical-id", "data-legend-id", "data-port-id"):
        a, b = indexed(interactive, key), indexed(exported, key)
        same_ids = set(a) == set(b)
        if key == "data-port-id":
            same = same_ids and all(port_visible(a[k]) == port_visible(b[k]) and a[k].get("data-node-id") == b[k].get("data-node-id") for k in a)
            method = "same identities, node owner and visible circle cx/cy/r/fill; transparent interactive hit circle excluded"
        else:
            normalize = key == "data-canonical-id"
            same = same_ids and all(signature(a[k], normalize) == signature(b[k], normalize) for k in a)
            method = "exact parsed subtree" if not normalize else "exact retained parsed subtree after removing focus attributes and interactive expand controls"
        visible_groups[key] = {"interactiveCount": len(a), "publicationCount": len(b), "equal": same, "comparison": method}
        check(f"{case}:publication-visible-{key}", same, visible_groups[key])
    residuals = []
    for item in public["metadata"]["renderedBindings"]:
        if item["role"] != "residual":
            continue
        canonical = {edge["id"]: edge for edge in document["architecture"]["edges"]}
        exact = all(canonical[i]["source"] == item["source"] and canonical[i]["target"] == item["target"] and canonical[i]["tensorId"] == item["tensorId"] and canonical[i]["role"] == item["role"] for i in item["canonicalEdgeIds"])
        edge_group = indexed(interactive, "data-edge-id")[item["sceneEdgeId"]]
        path = next(e for e in edge_group if tag(e) == "path")
        residuals.append({"binding": item, "canonicalEdgesExact": exact,
                          "route": path_geometry(path.get("d")), "stroke": path.get("stroke"),
                          "strokeWidth": path.get("stroke-width"), "markerEnd": path.get("marker-end")})
        check(f"{case}:{item['sceneEdgeId']}:canonical-residual-binding", exact)
    case_rows.append({"caseId": case, "level": level, "preset": preset, "widthMm": width,
                      "revision": public["revision"], "storageRevision": envelope["revision"],
                      "heightMmPublic": public["metadata"]["heightMm"], "heightMmPublication": export_meta["heightMm"],
                      "heightMmLiteralSvg": exported.get("height"), "metadataDifferences": metadata_differences,
                      "metadataNumericToleranceMm": 1e-10, "identityChecks": identities,
                      "publicationVisibleGroups": visible_groups,
                      "publicationPhysicalPreflightReportedOnly": receipt["physicalPreflight"],
                      "interactiveSvgSha256": hashlib.sha256(public["svg"].encode()).hexdigest(),
                      "publicationSvg": binding(folder / "figure.svg"),
                      "reportedSceneSvgDigest": receipt["sceneSvgDigest"],
                      "svgBytesAreDifferent": hashlib.sha256(public["svg"].encode()).hexdigest() != receipt["svgDigest"],
                      "residuals": residuals,
                      "files": [binding(folder / n) for n in ("document.json", "saved-envelope.json", "export-binding.json", "figure.svg", "figure.svg.receipt.json")]})
    for image in sorted(folder.glob("*.jpg")):
        view = image.stem
        before, after = read_json(folder / f"{view}-before.json"), read_json(folder / f"{view}-after.json")
        exact = without_time(before) == without_time(after)
        check(f"{case}:{view}:public-before-after", exact,
              {"excludedOnly": "capturedAt", "beforeCapturedAt": before["capturedAt"], "afterCapturedAt": after["capturedAt"]})
        scene_matches_fit = before["svg"] == public["svg"] and before["metadata"] == public["metadata"] and before["revision"] == public["revision"]
        check(f"{case}:{view}:same-current-scene", scene_matches_fit)
        visual = ["Personally viewed this original JPEG through tools.view_image; no renderer or DOM substitute used.",
                  "Visible page preset, width selection, zoom and footer revision match this image's bound public before/after record."]
        limits = ["Screen pixels only; no actual paper-size, physical font, human novice or print acceptance."]
        if view == "fit" and level == 0:
            visual += ["Full page, model title, image→stem→blocks→pool→flatten→classifier→output and legend visible; no obvious whole-page clipping or card-body overlap.",
                       "Stem→collapsed blocks residual U-detour seen in the historical same-frontier screenshot is absent. Separate parallel short links remain."]
            limits += ["46% fit makes labels and endpoint details small; use this case's own 100% local for short-span details."]
        elif view == "local" and level == 0:
            visual += ["100% upper-scene local shows separate stem output ports, collapsed Repeat target ports and independent arrowheads.",
                       "Repeat backplates are visible. No extra U, unnecessary bend or visible crossing in this short stem→blocks span."]
            if preset == "paper":
                visual += ["Left data lane is blue-gray; right residual lane is gold; both retained with separate endpoints."]
            else:
                visual += ["Both parallel lanes are solid gray and look alike. Ports and arrowheads are separate, but no explicit residual edge label is visible."]
                limits += ["A novice could read these as two ordinary connections. Pixel evidence alone does not establish residual role comprehension; canonical metadata is separate evidence."]
            limits += ["This local centers the upper model. Lower pool/output and whole-page legend are outside the viewport; no local whole-page judgment."]
        elif view == "fit" and level == 1:
            visual += ["Full page with expanded blocks and two collapsed ResidualBlock cards, title and legend is visible. Macro cards do not visibly overlap.",
                       "Stem bypass routes around the expanded blocks title remain visibly folded around left/right boundaries."]
            limits += ["38% fit is insufficient for fine arrow, glyph, role or bend-aesthetic certification."]
            if case != "cnn-level1-paper-180":
                limits += ["Fit-only case: no final local screenshot collected. Do not inherit paper/180 local conclusions."]
        elif view == "local" and level == 1:
            visual += ["100% paper/180 local shows stem, expanded blocks header, both collapsed ResidualBlock cards and pool.",
                       "Data from stem travels left around the expanded header; gold residual travels right around it and enters block 1 independently.",
                       "Block 1→block 2 has two short parallel vertical routes with distinct blue-gray/gold styles and independent ports/arrowheads.",
                       "Long stem→block 1 detour is boxy but avoids the expanded title and visible card bodies; no visible card-body penetration or overlap."]
            limits += ["Title avoidance justifies some elbows; no claim of global route optimality. Page title/legend/lower end are outside this local crop."]
        elif view == "fit" and level == 2:
            visual += ["Very tall, thin complete page with both expanded residual blocks fits on screen; no obvious macro card-body overlap.",
                       "At 17% fit, labels and arrowheads are extremely small. Long page remains after the L0 route fix."]
            limits += ["Fit cannot certify fine text, arrowhead legibility, crossings or route beauty.",
                       "Actual SVG page height is approximately 764.168 mm at 180 mm width or 360.857 mm at 85 mm width; width selection is not a physical paper preview."]
            if width == 85:
                limits += ["Fit-only case: no final local screenshot collected. Do not inherit either 180 mm local result."]
        elif level == 2 and view in ("local", "local-block2"):
            block = 1 if view == "local" else 2
            visual += [f"58% local independently shows complete block {block} residual skip, bypassed conv1→norm1→activation→conv2→norm2 chain and actual Add.",
                       "Residual travels outside the block body on the right and enters Add's right operand. Main norm2 branch enters Add's left operand. The two inputs are visibly separate.",
                       "No apparent shortcut through visible operations or operation-card body overlap/penetration. Operator labels identify the chain; subtitles remain small."]
            if block == 1:
                visual += ["View starts at stem output and reaches first Add. Main data takes the left corridor around blocks/ResidualBlock 1 title boundaries."]
            else:
                visual += ["View includes first block's final activation as source, the split around ResidualBlock 2 title and the full second right-hand bypass into Add; final activation is also visible.",
                           "Main route's offset stair around title boundaries remains. Long vertical skip runs parallel to frame edge."]
            if preset == "paper":
                visual += ["Gold residual and blue-gray data remain visibly different."]
            else:
                visual += ["Residual and data are both gray; spatial separation and two Add operands remain visible."]
                limits += ["Long border-parallel gray residual may resemble the frame. Role labeling/comprehension remains a novice usability risk."]
            limits += ["Only the bound block local is judged; page title/legend and other block/end may be outside view. No claim that all routing is optimal or all crossings absent."]
        else:
            raise ValueError((case, view))
        view_rows.append({"caseId": case, "view": view, "level": level, "preset": preset, "widthMm": width,
                          "originalJpeg": binding(image), "before": binding(folder / f"{view}-before.json"),
                          "after": binding(folder / f"{view}-after.json"), "revision": before["revision"],
                          "capturedAtPublicBefore": before["capturedAt"], "capturedAtPublicAfter": after["capturedAt"],
                          "publicBeforeAfterExactExceptCapturedAt": exact, "sceneMatchesCaseFit": scene_matches_fit,
                          "zoom": before["zoom"], "viewport": before["viewport"], "paperTransform": before["paperTransform"],
                          "personallyViewed": True, "viewTool": "tools.view_image",
                          "viewTimestamp": None, "viewTimestampNote": "Direct views occurred before this audit serialization in the same session. No per-view timestamp was recorded; no invented timestamp.",
                          "pixelObservations": visual, "limits": limits})

for preset in ("paper", "monochrome"):
    for width in (85, 180):
        case = f"cnn-level0-{preset}-{width}"
        before_dir = OLD / f"residual_{case}"
        old = read_json(before_dir / "public-observation.json")
        new = read_json(NEW / case / "fit-before.json")
        old_svg, new_svg = ET.fromstring(old["svg"]), ET.fromstring(new["svg"])
        old_edges, new_edges = indexed(old_svg, "data-edge-id"), indexed(new_svg, "data-edge-id")
        changed_edges = [k for k in old_edges if k in new_edges and signature(old_edges[k]) != signature(new_edges[k])]
        comparisons = {"metadataEqualExceptRevision": {k:v for k,v in old["metadata"].items() if k != "revision"} == {k:v for k,v in new["metadata"].items() if k != "revision"},
                       "sameViewBox": old_svg.get("viewBox") == new_svg.get("viewBox"),
                       "sameEdgeIds": set(old_edges) == set(new_edges), "onlyEdge9Changed": changed_edges == ["edge:9"]}
        for attribute in ("data-canonical-id", "data-port-id", "data-legend-id"):
            a, b = indexed(old_svg, attribute), indexed(new_svg, attribute)
            comparisons[f"{attribute}SubtreesExact"] = set(a) == set(b) and all(signature(a[k]) == signature(b[k]) for k in a)
        old_route = path_geometry(next(e.get("d") for e in old_edges["edge:9"] if tag(e) == "path"))
        new_route = path_geometry(next(e.get("d") for e in new_edges["edge:9"] if tag(e) == "path"))
        old_camera = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", old["camera"]["transform"])]
        transform = new["paperTransform"]
        translate = [float(n) for n in re.search(r"translate\(([-.\d]+)px, ([-.\d]+)px\)", transform).groups()]
        scale = float(re.search(r"scale\(([-.\d]+)\)", transform)[1])
        comparisons["equivalentFitCamera"] = old_camera == [scale, 0, 0, scale, *translate]
        check(f"{case}:historical-before-final-comparison", all(comparisons.values()), comparisons)
        old_rows.append({"caseId": case, "historicalOriginalJpeg": binding(before_dir / "screenshot.jpg"),
                         "historicalPublic": binding(before_dir / "public-observation.json"),
                         "historicalSceneSvg": binding(before_dir / "browser-scene.svg"),
                         "historicalDom": binding(before_dir / "fit.dom.txt"),
                         "finalOriginalJpeg": binding(NEW / case / "fit.jpg"), "finalPublic": binding(NEW / case / "fit-before.json"),
                         "historicalCapturedAt": old["capturedAt"], "finalCapturedAt": new["capturedAt"],
                         "historicalRevision": old["metadata"]["revision"], "finalRevision": new["revision"],
                         "historicalAssets": old["assets"], "finalAssetUrls": new["assetUrls"],
                         "historicalCamera": old["camera"]["transform"], "finalPaperTransform": transform,
                         "comparisons": comparisons, "changedEdgeIds": changed_edges,
                         "oldResidualRoute": old_route, "finalResidualRoute": new_route,
                         "oldBeyondModelRightWorld": 22, "modelRightWorld": 304,
                         "personallyViewedHistoricalOriginal": True, "viewTool": "tools.view_image", "viewTimestamp": None,
                         "pixelObservation": "Historical 46% fit visibly has U-detour to the right outside the top-level model frame. Final same-frontier 46% fit removes it; final own 100% local confirms independent straight data/residual lanes and ports.",
                         "limits": ["Historical build, capture time, revision and sidebar title differ. Old sidebar showed ResidualCNN; final sidebar showed Imported model. These are not contemporary recaptures or full-screen pixel-identical scenes.",
                                    "All four historical original JPEGs and all four final own fit+local pairs were personally viewed. Only retained model/port/legend subtrees and camera are compared mechanically; no whole-screen identity claim."]})

folder = NEW / "cnn-level0-paper-180"
first = read_json(folder / "fit-before.json")
reopen = read_json(folder / "reopen-public.json")
reopen_meta = read_json(folder / "reopen-export.json")
initial_doc = read_json(folder / "document.json")
reopen_doc = read_json(folder / "reopen-export-files/document.json")
initial_svg = (folder / "figure.svg").read_bytes()
reopen_svg = (folder / "reopen-export-files/figure.svg").read_bytes()
reopen_receipt = read_json(folder / "reopen-export-files/figure.svg.receipt.json")
reopen_checks = {
    "publicExactExceptCapturedAt": without_time(first) == without_time(reopen),
    "documentExact": initial_doc == reopen_doc,
    "publicationSvgBytesExact": initial_svg == reopen_svg,
    "newExportUuid": reopen_meta["uuid"] != read_json(folder / "export-binding.json")["uuid"],
    "reportedCacheReusedFalse": reopen_meta["cacheReused"] is False,
    "receiptSha256Exact": hashlib.sha256(reopen_svg).hexdigest() == reopen_receipt["outputDigest"] == reopen_receipt["svgDigest"],
    "receiptPathUuidBound": Path(reopen_receipt["path"]).parent.name == reopen_meta["uuid"],
}
check("cnn-level0-paper-180:reopen-artifacts-readback", all(reopen_checks.values()), reopen_checks)
reopen_row = {"checks": reopen_checks, "initialExportUuid": read_json(folder / "export-binding.json")["uuid"],
              "reopenExportUuid": reopen_meta["uuid"], "reportedCacheReused": reopen_meta["cacheReused"],
              "files": [binding(p) for p in [folder / "reopen-public.json", folder / "reopen-export.json", *sorted((folder / "reopen-export-files").iterdir())]],
              "scope": "Read artifact consistency only. This pixel audit did not operate save/reopen/export, observe network/backend behavior, or certify persistence behavior."}

derivatives = [binding(p) for p in sorted((OUT / "footer-crops").iterdir()) if p.is_file()]
derivative_provenance = read_json(OUT / "footer-crops/provenance.json")
derivative_exact = all(binding(ROOT / row["source"])["sha256"] == row["sourceSha256"] and binding(ROOT / row["output"])["sha256"] == row["outputSha256"] for row in derivative_provenance)
check("footer-crop-provenance", derivative_exact, {"originals": len(derivative_provenance), "filesBound": len(derivatives)})
helper_views = {"purpose": "Resolve tiny footer-digit review uncertainty without inventing pixels; original whole JPEGs were independently viewed first.",
                "method": "Each original footer rectangle (1150,695,1280,720), 6× nearest-neighbor derivative. Existing provenance preserved. Grid is a labeled montage of the 21 crop derivatives.",
                "personallyViewed": ["four individual questioned footer derivatives: L1 paper/85 (6), L1 monochrome/180 (8), L2 paper/85 (12), L0 monochrome/180 (3)",
                                     "all21-footer-grid.jpg after those individual views"],
                "gridDimensionsPx": [2460,1260], "gridDisplayDimensionsPx": [2048,1049],
                "result": "Correct bound revisions in all 21 footer crops. Initial difficulty reading tiny digits is resolved and is not a screenshot mismatch or failed capture.",
                "originalsCount": 21, "provenanceExact": derivative_exact, "bindings": derivatives,
                "viewTimestamp": None, "noOriginalScreenshotEdited": True}

end = freeze_check("after-final-comparisons", frozen)
machine_binding = put("machine-comparisons.json", {
    "protocol": "archcanvas-dzp-residual-pixel-artifact-comparisons/1", "createdAt": STAMP,
    "method": "Read-only Python stdlib JSON/XML/SHA256 comparisons. No product execution, browser calls, rendering, test suite, build, model execution or validator.",
    "before": start, "after": end, "checks": CHECKS,
    "passed": all(row["passed"] for row in CHECKS), "checkCount": len(CHECKS),
    "caseCount": len(case_rows), "newViewCount": len(view_rows), "historicalReferenceCount": len(old_rows),
    "cases": case_rows, "historicalL0Comparisons": old_rows, "reopenArtifacts": reopen_row,
    "scopeLimits": ["Artifact metadata/geometry checks are separate from personal pixel judgments.",
                    "Interactive SVG byte digest differs from actual publication SVG; final SVG digest is verified against actual converted output bytes.",
                    "Export preflight values are recorded as reported artifact data, not human/physical publication acceptance."]})
views_binding = put("per-image-review.json", {
    "protocol": "archcanvas-dzp-residual-ai-personal-pixel-observations/1", "createdAt": STAMP,
    "auditor": "AI subagent /root/au3_pixel_audit", "AIOnly": True, "humanParticipantsAdded": 0,
    "method": "Personally viewed all 21 original final JPEGs and all 4 original historical L0 JPEGs via tools.view_image in this same session before serializing this report. Direct views are preserved across conversation compaction; per-image timestamps were not recorded. Read-only comparisons provide bindings and state checks, never substitute for image views.",
    "uniqueOriginalJpegsPersonallyViewed": 25, "newFitCount": 12, "newLocalCount": 9,
    "historicalL0OriginalCount": 4, "newViews": view_rows,
    "historicalViews": old_rows, "footerReviewHelpers": helper_views,
    "machineComparisons": machine_binding})
print(json.dumps({"passed": all(row["passed"] for row in CHECKS), "checkCount": len(CHECKS),
                  "failed": [row for row in CHECKS if not row["passed"]],
                  "machineComparisons": machine_binding, "perImageReview": views_binding}, ensure_ascii=False, indent=2))
