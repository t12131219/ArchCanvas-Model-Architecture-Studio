#!/usr/bin/env python3
"""Audit final documentation and frozen local bindings; never run product tools."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
WORK = ROOT / "docs/evidence/m4-bcf-browser-matrix-work"
DOCS = ["README.md", "docs/capability-matrix.md", "docs/acceptance.md", "docs/m4-completion.md",
        "docs/m4-exit-audit.md", "docs/m4-performance.md", "docs/browser-visual-matrix-protocol.md",
        "docs/evidence/README.md", "docs/m4-authoring-feedback.md", "docs/m4-bcf-browser-matrix.md",
        "docs/m4-human-review-handoff.md", "docs/evidence/m4-bcf-browser-matrix-work/README.md"]


def data(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    assert path.is_file() and not path.is_symlink(), str(path)
    return path.read_bytes()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def obj(path):
    return json.loads(data(path))


def binding(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    value = data(path)
    return {"path": str(path.relative_to(ROOT)), "sha256": digest(value), "bytes": len(value)}


def verify(item, path=None):
    value = data(path or item["path"])
    assert digest(value) == item["sha256"], item["path"]
    if "bytes" in item:
        assert len(value) == item["bytes"], item["path"]


def nested_bindings(value):
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
            yield value
        else:
            for child in value.values():
                yield from nested_bindings(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested_bindings(child)


def main():
    status_path = "docs/evidence/m4-human-review-handoff-status.json"
    status = obj(status_path)
    assert status["schemaVersion"] == 6 and len(status["references"]) == 42
    assert status["phaseStatus"] == "partial" and not status["nextPhaseStarted"]
    assert status["productionBuild"] == "index-BcFxpKDY.js"
    refs = []
    for name, item in status["references"].items():
        verify(item)
        refs.append({"name": name, **item, "exact": True})
    document_bindings = [binding(path) for path in DOCS]
    archive_path = "docs/evidence/before-m4-bcf-browser-matrix/manifest.json"
    archive = obj(archive_path)
    assert archive["bindingCount"] == len(archive["bindings"]) == 478
    old_seal_path = "docs/evidence/before-m4-bcf-browser-matrix/previous-seal.json"
    assert digest(data(old_seal_path)) == archive["previousSealSha256"]
    assert data(old_seal_path) == data(archive["previousSeal"])
    old_seal = obj(old_seal_path)
    assert old_seal["bindingCount"] == len(old_seal["bindings"]) == 478
    old = {entry["path"]: entry for entry in old_seal["bindings"]}
    assert len(old) == 478 and set(old) == {entry["path"] for entry in archive["bindings"]}
    archived = []
    for entry in archive["bindings"]:
        assert {key: entry[key] for key in ("path", "sha256", "bytes")} == old[entry["path"]]
        verify(entry, entry["archivePath"])
        archived.append({**entry, "archiveExact": True})
    guard = obj(WORK / "preparation-guard.json")
    assert len(guard["frozenSourceAndBuild"]) == 70
    for path, expected in guard["frozenSourceAndBuild"].items():
        assert digest(data(path)) == expected, path
    native = WORK / "native-current"
    native_prepared = obj(native / "preparation.json")
    native_startup = obj(native / "startup-observation.json")
    for item in native_prepared["sourceBindings"] + native_startup["sourceBindingsAtObservation"]:
        verify(item)
    assert len(native_prepared["sourceBindings"]) == len(native_startup["sourceBindingsAtObservation"]) == 14
    assert status["productionJsSha256"] == digest(data("studio/dist/assets/index-BcFxpKDY.js"))
    assert status["productionCssSha256"] == digest(data("studio/dist/assets/index-NmgHfiF5.css"))
    assert status["frontendSha256"] == digest(data("src/archcanvas_python/frontend.py"))
    nested = []
    for name in ["currentCollectionSummary", "currentPixelManifest", "currentRoutingSummaryManifest",
                 "currentNativeSummaryManifest", "currentNativeLongManifest", "currentNativeSupplementManifest",
                 "currentNativePeerReview", "currentMovementPixelManifest"]:
        entries = list(nested_bindings(obj(status["references"][name]["path"])))
        for item in entries:
            verify(item)
        nested.append({"referenceName": name, "bindingsChecked": len(entries), "allExact": True})
    collection = obj(status["currentMatrix"]["manifest"])
    assert collection["capturedBaselineCount"] == 36 and len(collection["captures"]) == 39
    assert collection["editedAfterModelsCaptured"] == ["mlp", "residual_cnn", "transformer"]
    assert not collection["missingBaselineVariants"] and not collection["editedAfterModelsMissing"]
    assert collection["artifactCoverage"] == "complete"
    assert collection["visualAcceptance"] == "pending-human-review" and not collection["humanAcceptanceCertified"]
    assert status["currentMatrix"]["baselineCases"] == 36 and status["currentMatrix"]["editedModels"] == 3
    assert status["currentMatrix"]["actualScreenshots"] == 39 and status["currentMatrix"]["sealedArtifactFilesByteChecked"] == 234
    assert not status["currentMatrix"]["humanCertified"]
    assert status["currentBrowserRepresentative"]["paperReopened"] is False
    assert status["currentBrowserRepresentative"]["generatedLinearWidths"] == [16, 32, 8]
    research = status["research"]
    assert research["researcherCount"] == research["assignedParticipants"] == research["collectedParticipants"] == 0
    assert research["slots"] == 5 and research["ports"] == [8961, 8962, 8963, 8964, 8965]
    assert not research["aiRolesCountAsHumans"] and not research["humanServicesStarted"] and not research["portsAvailabilityVerified"]
    research_package = obj(Path(research["package"]) / "manifest.json")
    assert len(research_package["implementationFiles"]) == 70
    assert status["authoring"]["modules"] == 17 and not status["authoring"]["runtimeVerified"]
    assert "composite-presets" in status["authoring"]["unsupported"]
    long = obj(native / "independent-observation-audit-3/audit-summary.json")
    supplement = obj(native / "independent-supplement-audit-2/audit-summary.json")
    sessions = {entry["id"]: entry for entry in status["performance"]["currentNativeDiagnostics"]["sessions"]}
    assert len(sessions) == 4
    l = sessions["mlp-four-directions-1"]
    assert l["trials"] == long["trials"] == 16 and l["publicSvgSnapshots"] == long["xmlSnapshotsParsedAndCanonicallyBound"] == 32
    assert l["eventTiming"] == long["eventTiming"]
    assert l["frameDropped"] == long["bufferDrops"]["frames"]["dropped"] == 4102
    assert l["frameCallbacksDropped"] == long["bufferDrops"]["overhead.frameCallbacks"]["dropped"] == 4102
    assert not l["completeBuffers"] and not l["originalPanValidatorPassed"] and not l["originalJournalAvailable"]
    short = sessions["mlp-four-pan-short-1"]
    assert short["eventTiming"] == supplement["shortPanET"]
    assert short["validOperations"] == supplement["shortPanValidOperations"] == 4
    assert short["browserWindowMs"] == supplement["shortPanWindowMs"] == 4547
    assert short["completeBuffers"] and short["bufferDropped"] == 0 and short["pinsEmpty"]
    pilot = sessions["top-mlp-5toggle"]
    assert pilot["validSceneTrials"] == long["pilotValidSceneTrials"] == 2 and pilot["requestedTrials"] == 5
    assert pilot["matchedInteractions"] == 1 and pilot["matchedSubsetP95Ms"] == 4008
    stress = sessions["top-stress300-separated"]
    assert stress["validSceneTrials"] == supplement["stressValidSceneTrials"] == 3
    assert stress["matchedInteractions"] == supplement["stressMatchedInteractions"] == 3
    assert stress["matchedSubsetP95Ms"] == supplement["stressMatchedInteractionP95Ms"] == 176
    assert stress["publicNodesExpanded"] == supplement["stressPublicNodes"] == 304
    assert stress["publicRoutesExpanded"] == supplement["stressPublicRoutes"] == 302
    diag = status["performance"]["currentNativeDiagnostics"]
    assert not diag["rafCadenceIsPresentedFps"] and not diag["hardwareResolvedFontsBrowserVersionLocked"]
    assert not diag["heldPointerCancelCertified"] and not diag["nonemptyPinProtectionCertified"]
    assert not diag["savedCanvasOrHiddenHistoryCertified"] and not diag["independentPortClosureCertified"]
    lifecycle = obj(native / "service-lifecycle.json")
    verify(lifecycle["logSnapshot"], native / lifecycle["logSnapshot"]["path"])
    assert lifecycle["stop"]["exitCode"] == diag["serviceExitCode"] == 130
    assert b"KeyboardInterrupt" in data(native / lifecycle["logSnapshot"]["path"])
    assert not lifecycle["user8765Touched"] and not diag["user8765Touched"]
    stale = []
    stale_pattern = re.compile(r"0\s*/\s*36|not-collected|未collect|待采|尚未采|NATIVE-SUMMARY|采集由主代理进行")
    for path in DOCS:
        for line, text in enumerate(data(path).decode().splitlines(), 1):
            if stale_pattern.search(text):
                # One retained sentence explicitly identifies the earlier8886 collection timing.
                historical = path == "docs/m4-exit-audit.md" and "此8886阶段当时尚未采完整矩阵" in text
                stale.append({"path": path, "line": line, "text": text, "explicitlyHistorical": historical})
    assert all(item["explicitlyHistorical"] for item in stale), stale
    for path in DOCS[:8]:
        text = data(path).decode()
        assert "36/36 基线＋3/3 编辑态" in text.splitlines()[2]
        assert "478" in text and "partial" in text and "真人0" in text
        assert "M5" in text and "319" in text and "obx" in text
        assert "\n\n本构建切换前" in text
    links = []
    for path in ["docs/m4-bcf-browser-matrix.md", "docs/m4-human-review-handoff.md", str((WORK / "README.md").relative_to(ROOT))]:
        for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", data(path).decode()):
            target = match.group(1).strip("<>")
            if re.match(r"[a-z]+://", target) or target.startswith("#"):
                continue
            local = (ROOT / path).parent / target.split("#", 1)[0]
            assert local.exists(), str(local)
            links.append({"document": path, "target": target, "exists": True})
    for entry in document_bindings:
        verify(entry)
    verify(binding(status_path))
    report = {"schemaVersion": 1, "reviewedAtUTC": datetime.now(timezone.utc).isoformat(),
              "status": "passed-with-explicit-scope", "reviewer": "/root/routing_refinement_impl AI local-files reviewer",
              "reviewerIndependence": "This agent earlier implemented routing and capture helpers; this is a fresh file/document comparison against root-produced frozen evidence, not independent of all product implementation.",
              "documents": document_bindings, "statusBinding": binding(status_path), "statusSchemaVersion": 6,
              "references": refs, "referenceCount": 42, "allReferencesExact": True,
              "archiveManifest": binding(archive_path), "archivePreviousSeal": binding(old_seal_path),
              "archiveBindingCount": 478, "archiveBindings": archived, "previousSealBytesExact": True,
              "nestedCurrentManifests": nested, "matrixGuardSourceBuildCount": 70, "nativeSourceBindingCount": 14,
              "sourceBuildUnchanged": True, "currentMatrix": {"baselines": 36, "editedModels": 3, "screenshots": 39, "files": 234},
              "nativeIndependentSources": [binding(native / "independent-observation-audit-3/audit-summary.json"), binding(native / "independent-supplement-audit-2/audit-summary.json")],
              "nativeSessionsCompared": 4, "retainedOriginalPanFailure": True, "retainedLongBufferDropsEach": 4102,
              "pilotValidVsRequested": [2, 5], "latencyOnlyMatchedInteractionSubsets": True,
              "separateAuthoredPaperReopenFalse": True, "goldSvgSaveReopenModels": 3,
              "researchHumans": 0, "humanPublicationReviewers": 0, "m4Partial": True, "m5Started": False,
              "staleSentenceMatches": stale, "staleCurrentSentences": 0, "localLinks": links,
              "newRootSealReviewed": False, "newRootSealReason": "Root will generate its final seal after this fresh review is stable.",
              "rootFilesModified": False, "productTestsRun": False, "browserSamplesRun": False,
              "limits": ["No new product suite, model execution, browser operation or performance sample.",
                         "Lifecycle exit130 is root-attributed and supported by bound KeyboardInterrupt log; independent port closure was not certified. Prior socket probe was sandboxEPERM.",
                         "AI does not count as real researcher/publication reviewer. Presented FPS/overallINP/held-down cancellation/nonempty pin protection/font/hardware remain uncertified.",
                         "An exploratory source read assumed routing-body audit was an object and raised AttributeError; corrected read showed its7-entry list. This was not a validation run and wrote no files."]}
    with (HERE / "review.json").open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "docs": len(DOCS), "schema": 6, "referencesExact": 42,
                      "archiveOriginalBytesExact": 478, "sourceBuildUnchanged": 70, "nativeSessions": 4,
                      "staleCurrentSentences": 0, "productTestsRun": False}))


if __name__ == "__main__":
    main()
