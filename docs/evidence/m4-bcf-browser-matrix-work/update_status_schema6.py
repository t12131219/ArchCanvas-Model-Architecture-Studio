"""Record completed Bc collection/diagnostics without promoting acceptance gates."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "docs/evidence/m4-bcf-browser-matrix-work"
STATUS = ROOT / "docs/evidence/m4-human-review-handoff-status.json"


def read(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text())


def reference(relative: str) -> dict:
    data = (ROOT / relative).read_bytes()
    return {"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main() -> None:
    status = json.loads(STATUS.read_text())
    assert status["schemaVersion"] == 5, "Only the explicitly archived schema5 may be updated"
    archive = read("docs/evidence/before-m4-bcf-browser-matrix/manifest.json")
    assert archive["bindingCount"] == 478
    archived_status = next(item for item in archive["bindings"] if item["path"] == str(STATUS.relative_to(ROOT)))
    assert hashlib.sha256(STATUS.read_bytes()).hexdigest() == archived_status["sha256"]
    long = read("docs/evidence/m4-bcf-browser-matrix-work/native-current/independent-observation-audit-3/audit-summary.json")
    supplement = read("docs/evidence/m4-bcf-browser-matrix-work/native-current/independent-supplement-audit-2/audit-summary.json")
    status["schemaVersion"] = 6
    status["generatedAt"] = datetime.now(timezone.utc).isoformat()
    status["scope"] = "Unchanged Bc build: root-operated actual-browser 36+3 collection and four native diagnostic sessions, independently audited by AI proxies; human/publication/presented-performance acceptance remains uncertified. Historical Python319 and exact-core CPU scopes are preserved."
    status["tests"]["productSuitesRerunThisCollectionRound"] = False
    status["authoring"]["currentModuleCoverageReview"] = "17 entries/11 categories; search/click/drag interfaces exist; no all17 actual-browser retest this round, no composite presets or bounded Attention/sequence contract."
    status["currentBrowserRepresentative"]["scope"] = "Retained earlier Bc authored 16-to32-to8 representative on8947, not the new gold matrix or current native samples; its paper reopen remains false."
    status["routing"]["scope"] = "Historical73 scenes/13 exact core files only; no inherited browser/native acceptance."
    status["currentMatrix"] = {
        "status": "collected-complete-artifacts-pending-human-review",
        "spec": ".archcanvas/browser-visual-matrix-authoring-feedback-bcf/spec.json",
        "manifest": "docs/evidence/browser-visual-matrix-bcf-full/manifest.json",
        "baselineCases": 36,
        "editedModels": 3,
        "expectedBaselineCases": 36,
        "expectedEditedModels": 3,
        "frontiers": 9,
        "actualScreenshots": 39,
        "screenshotPixels": [1280, 720],
        "sealedArtifactFilesByteChecked": 234,
        "coverageInheritedFromPreviousBuild": False,
        "artifactCoverage": "complete",
        "visualAcceptance": "pending-human-review",
        "humanCertified": False,
        "aiPixelImagesOpened": 39,
        "excludedStaleHrefImageAlsoReviewed": True,
        "browserPublicationGeometryEqualCases": 39,
        "canonicalProjectionEndpointsViewBoxChecked": True,
        "baselineCenterlineBodyHeaderIntrusions": 0,
        "baselineUTurns": 0,
        "editedModelsUndoRedoSaveReopenSvgChecked": 3,
        "retainedFailures": ["stale-paper85-href-excluded-and-recaptured", "build-path-audit-failure", "old-before-journal-assumption-failure", "early-visibleNodes-selector-zero"],
        "limits": ["fit images are not physical85/180mm review", "deep text/arrows unreadable at13-18percent fit", "stroke/arrowhead/text/near-miss not certified by centerline geometry", "no inherited authored-model paper reopen"]
    }
    status["currentRoutingObservations"] = {
        "source": "docs/evidence/m4-bcf-browser-matrix-work/routing-quality/full-matrix-analysis/analysis-summary.json",
        "representatives": [
            {"model": "Transformer", "level": 0, "crossingPairs": 1, "crossingPoints": 1, "overlapPairs": 7, "bends": 20},
            {"model": "Transformer", "level": 1, "crossingPairs": 20, "crossingPoints": 21, "overlapPairs": 7, "bends": 72},
            {"model": "Transformer", "level": 2, "crossingPairs": 22, "crossingPoints": 25, "overlapPairs": 19, "bends": 116},
            {"model": "Transformer", "level": 3, "crossingPairs": 20, "crossingPoints": 23, "overlapPairs": 19, "bends": 124},
            {"model": "MLP", "level": 0, "crossingPairs": 0, "crossingPoints": 0, "overlapPairs": 0, "bends": 0},
            {"model": "MLP", "level": 1, "crossingPairs": 0, "crossingPoints": 0, "overlapPairs": 0, "bends": 8},
            {"model": "Residual CNN", "level": 0, "crossingPairs": 0, "crossingPoints": 0, "overlapPairs": 0, "bends": 4},
            {"model": "Residual CNN", "level": 1, "crossingPairs": 0, "crossingPoints": 0, "overlapPairs": 0, "bends": 14},
            {"model": "Residual CNN", "level": 2, "crossingPairs": 0, "crossingPoints": 0, "overlapPairs": 0, "bends": 28},
        ],
        "crossingAndOverlapScope": "different-tensor centerlines; shared same-tensor trunks separate; counts cannot certify unnecessary crossings/bends or aesthetics",
        "aestheticsCertified": False,
    }
    status["performance"]["currentNativeDiagnostics"] = {
        "status": "completed-with-retained-failures-and-uncertified-gates",
        "serviceUrl": "http://127.0.0.1:8982/",
        "serviceStoppedByRootCtrlC": True,
        "serviceExitCode": 130,
        "independentPortClosureCertified": False,
        "operator": "root actual CUA; child read-only independent auditors",
        "sessions": [
            {"id": "mlp-four-directions-1", "trials": long["trials"], "publicSvgSnapshots": long["xmlSnapshotsParsedAndCanonicallyBound"], "eventTiming": long["eventTiming"], "completeBuffers": long["globalExistingValidatorCompleteBuffers"], "frameDropped": 4102, "frameCallbacksDropped": 4102, "nativeNodeDragDirections": 4, "originalPanValidatorPassed": False, "originalJournalAvailable": False, "rawChunksIndependentlyReassembled": 70},
            {"id": "mlp-four-pan-short-1", "validOperations": supplement["shortPanValidOperations"], "completeBuffers": supplement["shortPanCompleteBuffers"], "bufferDropped": 0, "browserWindowMs": supplement["shortPanWindowMs"], "toolWallWindowSeconds": 41.6, "eventTiming": supplement["shortPanET"], "rafCallbacks": 273, "panXCssPx": 40, "panYCssPx": 32, "publicSceneSelectionFrontierEqual": True, "pinsEmpty": True, "rawSliceReceiptsRetained": False},
            {"id": "top-mlp-5toggle", "requestedTrials": 5, "validSceneTrials": long["pilotValidSceneTrials"], "matchedInteractions": 1, "matchedSubsetP95Ms": 4008, "failures": ["after-revision-plus2", "last-after-null", "unknown-about1Hz-raf"], "rawViewport": [1280, 720], "laterEnvironmentViewport": [1102, 835]},
            {"id": "top-stress300-separated", "validSceneTrials": supplement["stressValidSceneTrials"], "eligibleInputs": 3, "matchedInputs": 3, "matchedInteractions": supplement["stressMatchedInteractions"], "matchedSubsetP95Ms": supplement["stressMatchedInteractionP95Ms"], "publicNodesExpanded": supplement["stressPublicNodes"], "publicRoutesExpanded": supplement["stressPublicRoutes"], "rafCallbacks": 6547, "longTaskMs": [138, 112], "viewBox": [0, 0, 595, 30542], "paperWidthMm": 180, "paperHeightMm": 9239.6, "fitScaleApprox": 0.0179752, "rawSliceReceiptsRetained": False},
        ],
        "latencyScope": "bilaterally unique matched EventTiming inputs/entries; per-interaction max duration; separate subset p95, not overall INP",
        "rafCadenceIsPresentedFps": False,
        "hardwareResolvedFontsBrowserVersionLocked": False,
        "heldPointerCancelCertified": False,
        "nonemptyPinProtectionCertified": False,
        "savedCanvasOrHiddenHistoryCertified": False,
        "retainedTruncatedReads": True,
        "user8765Touched": False,
    }
    status["currentNativeMovementObservations"] = {
        "nodeDragDirections": 4,
        "nodeDeltaWorld": 52,
        "endpointsMatchPublicPorts": True,
        "canonicalSourceProjectionPreserved": True,
        "issues": [
            {"direction": "left", "kind": "child-outside-parent", "units": 22, "warningShown": False},
            {"direction": "up", "kind": "visible-header-intrusion-and-edge2-header-path", "visibleHeaderIntrusionUnits": 32, "warningShown": True},
            {"direction": "down", "kind": "sibling-overlap-and-edge3-body-path", "overlapHeightUnits": 14, "warningShown": True},
        ],
        "undoPublicSvgRestoredDirectionsIgnoringRevision": 4,
        "firstUndoSelectionRestored": False,
        "rightRedoSvgRestored": True,
        "movementAestheticsCertified": False,
    }
    status["proxyExploration"]["currentMatrixAndNativeRoles"] = {
        "roles": 3,
        "mode": "root actual-browser operator; independent child pixel/novice, routing/module, and native event/XML audits",
        "childrenOperateBrowser": False,
        "newRealNoviceParticipants": 0,
        "all17ModulesRetested": False,
        "aiCountsAsHuman": False,
    }
    status["historicalPreviousFrozenScope"] = status["previousFrozenScope"]
    status["previousFrozenScope"] = {
        "build": "index-BcFxpKDY.js",
        "seal": "docs/evidence/m4-authoring-feedback-current-verification-sealed.json",
        "archive": "docs/evidence/before-m4-bcf-browser-matrix/manifest.json",
        "bindingCount": 478,
        "archiveBytesVerified": True,
        "olderBindingChainPreserved": [1277, 904, 327],
    }
    new_references = {
        "currentCollectionReport": "docs/m4-bcf-browser-matrix.md",
        "currentCollectionManifest": "docs/evidence/browser-visual-matrix-bcf-full/manifest.json",
        "currentCaptures": "docs/evidence/m4-bcf-browser-matrix-work/captures-039.json",
        "currentCollectionSummary": "docs/evidence/m4-bcf-browser-matrix-work/completed-collection-summary.json",
        "currentCollectionByteAudit": "docs/evidence/m4-bcf-browser-matrix-work/full-collection-byte-audit.json",
        "currentEditedJournalAudit": "docs/evidence/m4-bcf-browser-matrix-work/edited-journal-svg-audit.json",
        "currentPixelManifest": "docs/evidence/m4-bcf-browser-matrix-work/pixel-review/evidence-manifest.json",
        "currentRoutingSummaryManifest": "docs/evidence/m4-bcf-browser-matrix-work/routing-quality/full-matrix-analysis/analysis-summary-manifest.json",
        "currentModuleCoverage": "docs/evidence/m4-bcf-browser-matrix-work/routing-quality/module-coverage.md",
        "currentNativeSummary": "docs/evidence/m4-bcf-browser-matrix-work/native-current/independent-audit-summary-1/README.md",
        "currentNativeSummaryManifest": "docs/evidence/m4-bcf-browser-matrix-work/native-current/independent-audit-summary-1/manifest.json",
        "currentNativeLongManifest": "docs/evidence/m4-bcf-browser-matrix-work/native-current/independent-observation-audit-3/manifest.json",
        "currentNativeSupplementManifest": "docs/evidence/m4-bcf-browser-matrix-work/native-current/independent-supplement-audit-2/manifest.json",
        "currentNativePeerReview": "docs/evidence/m4-bcf-browser-matrix-work/native-current/independent-observation-audit-review-1/manifest.json",
        "currentMovementPixelManifest": "docs/evidence/m4-bcf-browser-matrix-work/native-current/pixel-audit/evidence-manifest.json",
        "currentMeasurementLifecycle": "docs/evidence/m4-bcf-browser-matrix-work/native-current/service-lifecycle.json",
        "priorBcSeal": "docs/evidence/m4-authoring-feedback-current-verification-sealed.json",
        "priorBcArchive": "docs/evidence/before-m4-bcf-browser-matrix/manifest.json",
        "deliveryScreenshot": "docs/evidence/m4-bcf-browser-matrix-work/delivery.jpg",
    }
    for key, path in new_references.items():
        status["references"][key] = reference(path)
    for key, old_reference in list(status["references"].items()):
        status["references"][key] = reference(old_reference["path"])
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"schemaVersion": 6, "references": len(status["references"]), "matrix": [36, 3], "phaseStatus": status["phaseStatus"], "humanCount": status["research"]["researcherCount"]}))


if __name__ == "__main__":
    main()
