"""Append-only aggregation of completed independent reviews; no product imports or UI actions."""
from pathlib import Path
from collections import Counter
import datetime
import hashlib
import json
import sys

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
WORK = BASE.parent
GEO_AGG = Path(sys.argv[1]).resolve()


def bind(path):
    path = Path(path)
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


report_specs = [
    (2, "l0-four-combinations-pixel-review.json"),
    (3, "l1-four-combinations-pixel-review.json"),
    (4, "l2-four-combinations-pixel-review.json"),
    (5, "l3-four-combinations-pixel-review.json"),
    (6, "mlp-l0-four-combinations-pixel-review.json"),
    (7, "mlp-l1-four-combinations-pixel-review.json"),
    (8, "cnn-l0-four-combinations-pixel-review.json"),
    (9, "cnn-l1-four-combinations-pixel-review.json"),
    (10, "cnn-l2-four-combinations-pixel-review.json"),
    (12, "mlp-edited-pixel-review.json"),
    (13, "cnn-edited-recapture1-pixel-review.json"),
    (14, "transformer-edited-pixel-review.json"),
]
expected_ids = []
for model, levels in [("transformer", range(4)), ("mlp", range(2)), ("residual_cnn", range(3))]:
    for level in levels:
        for palette in ["paper", "monochrome"]:
            for width in [85, 180]:
                case = f"{model}-level{level}-{palette}-{width}"
                if case == "transformer-level1-paper-85":
                    case += "-recapture1"
                expected_ids.append(case)
expected_ids += ["mlp-level1-paper-180-edited", "residual_cnn-level0-paper-180-edited-recapture1", "transformer-level0-paper-180-edited"]
assert len(expected_ids) == 39 and len(set(expected_ids)) == 39
report_paths = [BASE / f"attempt-{attempt}" / name for attempt, name in report_specs]
reports = [json.loads(path.read_text()) for path in report_paths]
raw_expected = {}
views = {}
case_to_report = {}
for path, report in zip(report_paths, reports):
    for binding in report["inputBindings"]:
        old = raw_expected.get(binding["path"])
        assert old is None or old == binding
        raw_expected[binding["path"]] = binding
    for view in report["actualImageViews"]:
        case = view.get("caseId", report.get("caseId"))
        assert case in expected_ids
        key = (case, view["file"])
        assert key not in views
        views[key] = {**view, "caseId": case, "report": bind(path), "image": bind(WORK / "raw" / case / view["file"])}
        case_to_report[case] = path
assert set(case_to_report) == set(expected_ids)
assert len(views) == 78
for case in expected_ids:
    assert (case, "primer.jpg") in views and (case, "screenshot.jpg") in views
    for filename in ["primer.jpg", "screenshot.jpg"]:
        decoded = views[(case, filename)]["decoded"]
        assert decoded["format"] == "JPEG" and decoded["size"] == [1280, 720] and decoded["mode"] == "RGB"
normal_primers = ["transformer-level0-monochrome-85", "transformer-level3-monochrome-180"]
modal_primers = [case for case in expected_ids if case not in normal_primers]
assert len(modal_primers) == 37
assert all("modal" in views[(case, "primer.jpg")]["classification"] for case in modal_primers)
raw_start = [bind(path) for path in sorted(raw_expected)]
assert all(binding == raw_expected[binding["path"]] for binding in raw_start), "Bound raw input changed"
geo = json.loads(GEO_AGG.read_text())
assert geo["uniqueCaseCount"] == 39 and {case["caseId"] for case in geo["cases"]} == set(expected_ids)

# Bind completed local evidence, including preserved exclusions/corrections and
# review/helper sources. These bindings do not imply original acquisition locks.
evidence_paths = [BASE / "source_field_inventory.py"]
for attempt in range(1, 15):
    evidence_paths.extend(sorted((BASE / f"attempt-{attempt}").rglob("*")))
evidence_paths = sorted({path.resolve() for path in evidence_paths if path.is_file()})
if GEO_AGG not in evidence_paths:
    evidence_paths.append(GEO_AGG)
if GEO_AGG.with_suffix(".md").is_file() and GEO_AGG.with_suffix(".md") not in evidence_paths:
    evidence_paths.append(GEO_AGG.with_suffix(".md"))
evidence_paths.append(Path(__file__).resolve())
evidence_start = [bind(path) for path in evidence_paths]
cases = []
geo_cases = {case["caseId"]: case for case in geo["cases"]}
for case in expected_ids:
    public = json.loads((WORK / "raw" / case / ("dom-observation-correct-variant.json" if (WORK / "raw" / case / "dom-observation-correct-variant.json").exists() else "dom-observation.json")).read_text())
    g = geo_cases[case]
    cases.append({"caseId": case, "variantId": public["variantId"], "state": public["state"], "pixelReport": bind(case_to_report[case]), "documentBinding": public["documentBinding"], "expandedIds": public["expandedIds"], "pageSpec": public["pageSpec"], "actualExport": public["actualExport"], "svgRoot": g["svgRoot"], "canvasDocumentRevision": g["canvasDocumentRevision"], "envelopeTopLevelRevision": g["envelopeTopLevelRevision"], "actualOriginalViews": [views[(case, "primer.jpg")], views[(case, "screenshot.jpg")]], "finalCoarseFieldConclusion": "Main final fields consistent within the recorded per-case limits; no publication/human acceptance", "primerCoverage": "modal intermediate only" if case in modal_primers else "normal primer; not an extra final success"})
raw_end = [bind(path) for path in sorted(raw_expected)]
evidence_end = [bind(path) for path in evidence_paths]
assert raw_start == raw_end and evidence_start == evidence_end
result = {
    "kind": "Independent bounded review of selected ChS 36 baseline +3 edited browser matrix",
    "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "scope": "Original image views are actual reviewer observations recorded per case; source geometry separately supplied by independent child. Product/build/capture/raw/old reports are untouched.",
    "selectedCaseIds": expected_ids,
    "counts": {"baselineCases": 36, "editedCases": 3, "selectedCases": 39, "selectedUniqueOriginalImagesActuallyViewed": 78, "finalScreenshotsMainCoarseFieldsConsistentWithinLimits": 39, "modalPrimersAgainstPairedFinalBaseline": 37, "normalPrimers": 2, "primersCountedAsExtraFinalSuccess": 0, "excludedCNNUniqueImagesActuallyViewed": 2, "totalUniqueOriginalImagesActuallyViewedIncludingExcludedCNN": 80, "selectedRawAndContextDeduplicatedBindings": len(raw_start), "boundCompletedEvidenceAndHelperFiles": len(evidence_start), "performanceTrials": 0},
    "normalPrimerCaseIds": normal_primers,
    "modalPrimerCaseIds": modal_primers,
    "exclusions": [
        {"caseId": "transformer-level1-paper-85", "reason": "Wrong reused actual export href, root excluded. recapture1 replaces target coverage.", "imagesViewedByThisReviewer": 0, "scope": "Excluded original raw not counted; no independent pixel observation claimed here."},
        {"caseId": "residual_cnn-level0-paper-180-edited", "reason": "Latent child0/1 expandedIds inconsistent with intended canonical L0, root excluded. Fresh recapture1 replaces target coverage.", "imagesViewedByThisReviewer": 2, "pixelExclusion": bind(BASE / "attempt-11/cnn-edited-pixel-exclusion.json"), "scope": "Preserved endpoint observations only; not target success."},
        {"caseId": "transformer-level0-paper-85", "reason": "Attempt1 is a duplicate actual review of the accepted first case. It remains preserved but counts once via attempt2."},
    ],
    "workspaceObservation": {"selectedFinalImagesWithExplicitDottedGridObservation": 25, "baseline": 22, "edited": 3, "limits": "Public observation JSON lacks grid state; full DOM shows unpressed-marker-free grid button. Workspace is outside paperSVG. State equality and cause unknown; no assumption from root action history. Later UI softness observed without product/capture attribution."},
    "fitZoomObservationsPercent": {"Transformer": {"L0": 54, "L1": 26, "L2": 18, "L3": 14, "editedL0": 49}, "MLP": {"L0": 79, "L1": 46, "editedL1": 43}, "ResidualCNN": {"L0": 46, "L1": 38, "L2": 17, "editedL0": 17}},
    "editedNotes": [report["noteEvidence"] for report in reports[-3:]],
    "freshCNNClarification": "Fresh main graph and legend occupy paper top; blocksBottom416/poolTop454 gap38. Annotation y2529 remains far below, with viewBox595×2584 /180×781.71mm page. Excluded original1614 nodegap is not reused. Layout/continuity cause is not inferred.",
    "geometryAggregate": bind(GEO_AGG),
    "geometrySummary": {key: geo[key] for key in ["totalRouteInstances", "totalEndpointInstances", "totalMainCardOverlapPairs", "totalMainCardPenetrationIncidences", "totalRepeatBackplatePenetrationIncidences", "routeIntersectionSegmentIncidences", "allRoleSpecificEndpointsWithinDeclaredSerializationTolerance", "allNominalRectsAndRoutePointsWithinPaperViewBox"]},
    "cases": cases,
    "rawBindingsStart": raw_start,
    "rawBindingsEnd": raw_end,
    "rawAndContextInputsUnchanged": raw_start == raw_end,
    "completedEvidenceAndHelperBindingsStart": evidence_start,
    "completedEvidenceAndHelperBindingsEnd": evidence_end,
    "completedEvidenceAndHelperInputsUnchanged": evidence_start == evidence_end,
    "limits": [
        "Discovery reads preceded some bindings; no immutable first-acquisition or capture/raster synchronization claim. DOM equality is not screenshot proof.",
        "Coarse final-field consistency does not certify every label, detailed path, glyph, arrowhead, marker or clipping. The most detailed graphs are too small at fit zoom.",
        "Fitted85/180mm images with same pixel shape do not certify physical-page readability. Source point sizes and preflight warnings/recommendations are declarations, not publication/human acceptance.",
        "Exact note wording is saved/SVG/DOM evidence; tiny note strips do not provide full pixel text proof. Transformer note tspans line-joined with a space reproduce saved wording; raw itertext/DOM concatenation omits the line separator.",
        "Role-specific endpoints within0.051 scene-unit rounding tolerance and0front-card penetration do not erase distinct-route overlaps/crossings or repeat-backplate penetrations.",
        "Nominal axis-aligned rectangles and serialized routepoint bounds within paperSVG exclude glyph/stroke/marker/rounded-corner/circle-radius/raster extents and workspace grid.",
        "Segment incidence totals are not unique pixel/net crossing counts. Different-tensor overlap candidates do not prove wrong topology or unnecessary crossings.",
        "Top envelope revision and CanvasDocument revision are separate; counter semantics are not inferred. Images do not certify action/undo/redo/save/reopen history; separate persistence/journal reviews apply.",
        "Source declarations and canonical bindings are not runtime/sourceIR recomputation or human semantic acceptance. User model was not executed here.",
        "UA/DPR originate from same selected IAB support iframe, not matrix-native browser/version/font/hardware lock. Performance trials0; no FPS claim.",
        "The old799-input seal and frozen reports/manifests remain untouched. Current formal package copy/index/UUID/hash checks are a separate append-only review after pack freeze.",
    ],
}
target = OUT / "selected-39-independent-review.json"
with target.open("x") as handle:
    json.dump(result, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
md = target.with_suffix(".md")
with md.open("x") as handle:
    handle.write("# Selected39 independent review\n\n39 selected cases (36baseline+3edited),78 unique original JPEG RGB1280×720 images actually viewed.39finalscreenshots match main coarse fields within recorded limits.37primers retain an export modal;2are normal. No primer counts as extra final success.\n\nTwo exclusions remain: wrong-href original TransformerL1paper85 and latent-childflag original CNNedited. Fresh replacements provide coverage. The oldCNNtwo actually viewed images are separate, bringing all unique viewed images including excludedCNN to80. Attempt1 duplicate counts once.\n\n25selectedfinals explicitly show dotted workspace; publicgridstate/cause remain unknown. Detailed fitzoom does not establish physical85/180mm readability. All edited notes are source-only exactwording evidence; Transformer wraps into2tspans, whose rawconcatenation loses the line separator.\n\nFreshCNNhascompactmaingraphatpaper top, blocks/poolgap38, distantnoteaty2529 and180×781.71mm page. Excluded old1614gap is not carried forward.\n\nIndependent geometry retains "+str(result["geometrySummary"])+". These are serialized incidences, not uniquepixel crossings. Nominalbody/bounds checks exclude glyphs/strokes/markers/raster/workspace.\n\n"+str(len(raw_start))+" deduplicated raw/context inputs and "+str(len(evidence_start))+" completed evidence/helper files rehash unchanged. Discovery/acquisition/synchronization/runtime/nativeenv/performance/human acceptance remain outside scope. The old seal is untouched.\n")
for path in [target, md, Path(__file__)]:
    print(json.dumps(bind(path), ensure_ascii=False))
