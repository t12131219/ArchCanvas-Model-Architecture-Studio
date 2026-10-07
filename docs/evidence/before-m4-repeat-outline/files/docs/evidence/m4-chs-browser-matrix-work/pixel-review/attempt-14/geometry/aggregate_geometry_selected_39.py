"""Aggregate only independently completed case reviews; no browser/product activity."""
from pathlib import Path
import collections
import hashlib
import json
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
REVIEW = OUT.parents[1]


def bind(path):
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


# Attempt 1 is a duplicate review of the first L0 case. It remains preserved but
# is deliberately not counted again. No excluded raw-case directory is scanned.
excluded_case_ids = {"residual_cnn-level0-paper-180-edited"}
selection_path = OUT / "explicit-selected-39-source-geometry-reports.json"
selection_binding_start = bind(selection_path)
selection = json.loads(selection_path.read_text())["selectedCases"]
paths = [REVIEW / row["relativeReportPath"] for row in selection]
assert len(selection) == 39 and all(bind(path)["sha256"] == row["reportSha256"] for row, path in zip(selection, paths))
report_start = [bind(path) for path in paths]
reviews = [json.loads(path.read_text()) for path in paths]
assert len(reviews) == 39, "Run only once all 36 baseline + 3 edited case reviews are complete"
assert len({r["caseId"] for r in reviews}) == 39
raw_expected = {}
for review in reviews:
    assert review["inputsUnchanged"]
    for binding in review["inputBindingsStart"]:
        assert binding["path"] not in raw_expected or binding == raw_expected[binding["path"]]
        raw_expected[binding["path"]] = binding
raw_start = [bind(Path(path)) for path in sorted(raw_expected)]
assert all(binding == raw_expected[binding["path"]] for binding in raw_start)

cases = []
for path, review in zip(paths, reviews):
    raw = Path(review["inputBindingsStart"][0]["path"]).parent
    svg = ET.parse(raw / "browser-scene.svg").getroot()
    metadata = json.loads(next(element for element in svg if element.tag.endswith("metadata")).text)
    envelope = json.loads((raw / "saved-envelope.json").read_text())
    document = envelope["document"]
    observation_name = review.get("observationFileUsed", "dom-observation.json")
    observation = json.loads((raw / observation_name).read_text())
    x, y, width, height = map(float, svg.attrib["viewBox"].split())
    rects = [{"nodeId": node["id"], **node["mainRect"]} for node in review["visibleNodes"]] + review["repeatDecorativeBackplates"]
    rect_outside = [rect for rect in rects if rect["x"] < x or rect["y"] < y or rect["x"] + rect["width"] > x + width or rect["y"] + rect["height"] > y + height]
    route_outside = [{"edgeId": route["id"], "point": point} for route in review["routes"] for point in route["points"] if not (x <= point[0] <= x + width and y <= point[1] <= y + height)]
    nodes = {node["id"]: node for node in document["architecture"]["nodes"]}
    edges = {edge["id"]: edge for edge in document["architecture"]["edges"]}
    canonical_checks = []
    for binding in metadata["renderedBindings"]:
        members = [edges.get(edge_id) for edge_id in binding["canonicalEdgeIds"]]
        canonical_checks.append({
            "sceneEdgeId": binding["sceneEdgeId"],
            "canonicalEdgeIds": binding["canonicalEdgeIds"],
            "allCanonicalMembersPresent": all(member is not None for member in members),
            "canonicalMemberRoles": [member["role"] if member else None for member in members],
            "sceneRole": binding["role"],
            "allCanonicalMemberRolesMatch": all(member and member["role"] == binding["role"] for member in members),
            "sceneSourceExistsAndPortDeclared": binding["source"]["nodeId"] in nodes and any(port["id"] == binding["source"]["portId"] for port in nodes[binding["source"]["nodeId"]]["ports"]),
            "sceneTargetExistsAndPortDeclared": binding["target"]["nodeId"] in nodes and any(port["id"] == binding["target"]["portId"] for port in nodes[binding["target"]["nodeId"]]["ports"]),
            "tensorId": binding["tensorId"],
            "canonicalMemberTensorIds": [member["tensorId"] if member else None for member in members],
            "tensorLimit": "Canonical fused routes can span distinct intermediary tensors; enumerated rather than forcing all tensor IDs equal. No runtime semantics are certified.",
        })
    cases.append({
        "caseId": review["caseId"],
        "variantId": observation.get("variantId"),
        "state": observation.get("state"),
        "report": bind(path),
        "svgRoot": svg.attrib,
        "canvasDocumentRevision": document["revision"],
        "envelopeTopLevelRevision": envelope["revision"],
        "revisionLimit": "Separately declared fields; top-level storage counter semantics not independently established, no cause/defect inference from difference.",
        "bindingEquality": review["bindingEquality"],
        "domChecks": review["domChecks"],
        "beforeAfterDomByteEqual": review["beforeAfterDomByteEqual"],
        "frontCardCount": review["applicability"]["frontCardCount"],
        "expandedContainerCount": review["applicability"]["expandedContainerCount"],
        "routeCount": len(review["routes"]),
        "roles": review["roleCounts"],
        "endpointSummary": review["endpointSummary"],
        "mainCardOverlaps": review["mainCardOverlaps"],
        "mainCardRoutePenetrations": review["mainCardRoutePenetrations"],
        "repeatBackplateRoutePenetrations": review["repeatBackplateRoutePenetrations"],
        "routeIntersections": review["routeIntersectionSummary"],
        "paperViewBoxNominalBounds": {"viewBox": [x, y, width, height], "auditedRects": len(rects), "rectanglesOutside": rect_outside, "serializedRoutePointsOutside": route_outside},
        "physicalScaleSummary": review.get("physicalScaleSummary"),
        "actualHrefChecks": review.get("hrefChecks"),
        "canonicalMetadataEnvelopeChecks": canonical_checks,
        "sameCasePixelLimit": "No image was opened by this geometry reviewer. Existing parent's modal/grid mismatches are not superseded by source geometry or DOM equality.",
    })

supplement_paths = [
    REVIEW / "attempt-2/geometry/l0-revision-clarification.json",
    REVIEW / "attempt-2/geometry/l0-revision-clarification.md",
    REVIEW / "attempt-4/geometry/l0-l2-source-geometry-aggregate.json",
    REVIEW / "attempt-5/geometry/transformer-self-route-port-perimeter-supplement.json",
    REVIEW / "attempt-5/geometry/routing-priority-review.json",
    REVIEW / "attempt-5/geometry/routing-priority-review.md",
    REVIEW / "attempt-10/geometry/baseline-other-models-port-selfroute-supplement.json",
    REVIEW / "attempt-11/geometry/excluded-original-cnn-edited-case.json",
    REVIEW / "attempt-12/geometry/mlp-level1-paper-180-edited-annotation-baseline-review.json",
    REVIEW / "attempt-13/geometry/residual_cnn-level0-paper-180-edited-recapture1-annotation-baseline-review.json",
    REVIEW / "attempt-13/geometry/residual-cnn-fresh-frontier-final-review.json",
    REVIEW / "attempt-14/geometry/transformer-level0-paper-180-edited-annotation-baseline-review.json",
    REVIEW / "attempt-14/geometry/edited-note-lines-port-selfroute-supplement.json",
    REVIEW / "attempt-14/geometry/edited-note-lines-port-selfroute-supplement-correction.json",
]
supplement_start = [bind(path) for path in supplement_paths]
raw_end = [bind(Path(path)) for path in sorted(raw_expected)]
report_end = [bind(path) for path in paths]
supplement_end = [bind(path) for path in supplement_paths]
types = sum((collections.Counter(case["routeIntersections"]["segmentIncidenceTypes"]) for case in cases), collections.Counter())
result = {
    "scope": "Independent complete 36 baseline + 3 edited case public SVG/full DOM/stored snapshot source geometry aggregation; zero pixel views in this reviewer role",
    "uniqueCaseCount": len(cases),
    "explicitSelectionBindingStart": selection_binding_start,
    "explicitSelectionBindingEnd": bind(selection_path),
    "explicitSelectionUnchanged": selection_binding_start == bind(selection_path),
    "selectedCases": selection,
    "stateCounts": dict(collections.Counter(case["state"] for case in cases)),
    "uniqueVariantStateCount": len({(case["variantId"], case["state"]) for case in cases}),
    "editedSelfRouteCorrection": "attempt-14 corrected supplement uses consecutive nonzero segment adjacency. Initial edited supplement contacts were consecutive segments separated by serialized zero-length segments and are superseded only for self-route nonadjacency.",
    "totalRouteInstances": sum(case["routeCount"] for case in cases),
    "totalEndpointInstances": sum(case["endpointSummary"]["checkedEndpoints"] for case in cases),
    "totalMainCardOverlapPairs": sum(len(case["mainCardOverlaps"]) for case in cases),
    "totalMainCardPenetrationIncidences": sum(len(case["mainCardRoutePenetrations"]) for case in cases),
    "totalRepeatBackplatePenetrationIncidences": sum(len(case["repeatBackplateRoutePenetrations"]) for case in cases),
    "routeIntersectionSegmentIncidences": dict(types),
    "allRoleSpecificEndpointsWithinDeclaredSerializationTolerance": all(case["endpointSummary"]["allMatchCanonicalPortAndRoleWithinTolerance"] for case in cases),
    "allNominalRectsAndRoutePointsWithinPaperViewBox": all(not case["paperViewBoxNominalBounds"]["rectanglesOutside"] and not case["paperViewBoxNominalBounds"]["serializedRoutePointsOutside"] for case in cases),
    "structuralRawInputCount": len(raw_start),
    "rawBindingsStart": raw_start,
    "rawBindingsEnd": raw_end,
    "structuralRawInputsUnchanged": raw_start == raw_end,
    "reportBindingsStart": report_start,
    "reportBindingsEnd": report_end,
    "perCaseReportsUnchanged": report_start == report_end,
    "supplementBindingsStart": supplement_start,
    "supplementBindingsEnd": supplement_end,
    "supplementsUnchanged": supplement_start == supplement_end,
    "cases": cases,
    "coverageAccounting": "Attempt1 repeats first case and is not counted. Original excluded Transformer L1 paper85 is not read or counted; recapture corrected variant replaces its coverage. Original editedCNN with latent child0/1 expandedIds is excluded from target coverage; its factual reports are preserved separately. Earlier 799-input seal and reports are untouched. Images are reviewed only by parent/other assigned pixel reviewers, not this source-only aggregate.",
    "limits": [
        "Nominal open axis-aligned front card interiors only; expanded enclosing containers excluded, repeat background stack strips retained separately.",
        "Paper SVG viewBox is not Studio workspace. Glyphs, resolved font faces, painted stroke/marker/circle extents, workspace grid and visible pixels are outside numerical bounds certification.",
        "Nominal font units at85/180mm do not prove physical-page readability; fitted same-shape scene may hide scale differences.",
        "Endpoint agreement, zero body penetration or bounded geometry do not imply clean/distinguishable publication routing. All contacts, collinear overlaps and strict crossings remain retained.",
        "Canonical metadata/envelope comparison checks declared IDs/ports/roles, not runtime model/source fidelity or correctness of every fused-route semantic intent.",
        "Storage receipt snapshot consistency does not establish live bytes, save success, acquisition method or screenshot synchronization. Before/after DOM equality is not screenshot proof.",
        "No model execution, capture timing/cause, performance/native environment lock, glyph/arrowhead legibility or human acceptance certification.",
        "L3 routing priority ranks are future review candidates, no applied fix or defect proof; same-tensor overlap may be intentional and different-tensor contact is not automatically unnecessary.",
    ],
}
OUT.mkdir(parents=True, exist_ok=True)
path = OUT / "complete-source-geometry-aggregate.json"
assert not path.exists(), "Append-only evidence: never overwrite a completed aggregate"
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
md = path.with_suffix(".md")
assert not md.exists()
md.write_text(f"# Complete source geometry aggregate\n\n39 unique cases (36 baseline + 3 edited) contain {result['totalRouteInstances']} routes and {result['totalEndpointInstances']} endpoints. {len(raw_start)} structural raw inputs,39 per-case JSON reports and {len(supplement_paths)} supplements rehashed unchanged. The first case duplicate and excluded Transformer capture are not counted.\n\nAll role-specific endpoints match within declared public serialization rounding tolerance. Main/front cards retain {result['totalMainCardOverlapPairs']} overlap pairs and {result['totalMainCardPenetrationIncidences']} route penetration incidences; repeat stack backplates retain {result['totalRepeatBackplatePenetrationIncidences']} penetration incidences. Inter-route serialized segment contacts: {dict(types)}. These findings remain, even when nominal front card clearance and paper viewBox bounds pass.\n\nPaper SVG bounds do not certify workspace grid, glyphs/stroke/markers or pixels. Nominal font units and fitted shapes do not prove physical readability. CanvasDocument and top-level envelope revisions are separate declarations with no inferred cause. Parent pixel modal/grid discrepancies are not resolved by this source-only aggregate. No runtime/performance, acquisition synchronization or human acceptance is certified.\n")
print(json.dumps({"json": bind(path), "md": bind(md), "caseCount": len(cases), "structuralInputs": len(raw_start), "routes": result["totalRouteInstances"], "endpoints": result["totalEndpointInstances"], "routeIntersections": dict(types), "allInputsUnchanged": result["structuralRawInputsUnchanged"] and result["perCaseReportsUnchanged"] and result["supplementsUnchanged"] and result["explicitSelectionUnchanged"]}, ensure_ascii=False, indent=2))
