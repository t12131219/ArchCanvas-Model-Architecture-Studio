"""Independent, read-only guidance ledger/document audit; report is write-once.

No product execution, browser operations, dependency installs, or tests/builds.
File identity checks do not certify every nested narrative or visual aesthetics.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[3]
WORK = "docs/evidence/m4-authoring-guidance-work/"
SEAL1 = "docs/evidence/m4-authoring-guidance-verification-sealed-attempt-1.json"
ENTRY_DOCS = [
    "README.md", "docs/acceptance.md", "docs/capability-matrix.md",
    "docs/m4-ai-usability-audit.md", "docs/m4-authoring-feedback.md",
    "docs/m4-authoring-guidance.md", "docs/m4-authoring.md",
    "docs/m4-completion.md", "docs/m4-exit-audit.md",
    "skills/archcanvas/references/formal-alpha.md",
    "skills/archcanvas/references/runtime-compatibility.md",
]


def read(path):
    return json.loads((ROOT / path).read_text())


def identity(path):
    data = (ROOT / path).read_bytes()
    return {"path": path, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def check(rows, path_key="path", overrides=None):
    overrides = overrides or {}
    errors = []
    resolved = []
    for row in rows:
        path = overrides.get(row["path"], row.get(path_key, row["path"]))
        try:
            actual = identity(path)
        except (OSError, ValueError) as exc:
            errors.append({"declaredPath": row["path"], "resolvedPath": path,
                           "error": str(exc)})
            continue
        if (row["bytes"], row["sha256"]) != (actual["bytes"], actual["sha256"]):
            errors.append({"declaredPath": row["path"], "resolvedPath": path,
                           "expected": {"bytes": row["bytes"], "sha256": row["sha256"]},
                           "actual": actual})
        resolved.append({"declaredPath": row["path"], **actual})
    return {"count": len(rows), "exact": len(rows) - len(errors),
            "mismatches": errors, "resolved": resolved}


def same_rows(original, resolved):
    def keys(rows):
        return sorted((row["path"], row["bytes"], row["sha256"]) for row in rows)
    return keys(original) == keys(resolved)


def local_links(paths):
    """Resolve inline/image and reference destinations outside fenced blocks.

    Checks file existence only. Same-document fragments are accounted for but
    anchors/external destinations are not certified. Full MD files are scanned,
    including their explicitly historical sections.
    """
    results = []
    errors = []
    for path in paths:
        lines = (ROOT / path).read_text().splitlines()
        fence = None
        count = 0
        external = 0
        fragments = 0
        refs = {}
        content = []
        for number, line in enumerate(lines, 1):
            token = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
            if token:
                mark = token.group(1)[0]
                if fence is None:
                    fence = mark
                elif mark == fence:
                    fence = None
                continue
            if fence:
                continue
            content.append((number, line))
            ref = re.match(r"^\s{0,3}\[([^]]+)\]:\s*(<[^>]+>|\S+)", line)
            if ref:
                refs[ref.group(1).strip().lower()] = (number, ref.group(2))
        destinations = []
        for number, line in content:
            for match in re.finditer(r"!?\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)", line):
                destinations.append((number, match.group(1), "inline"))
        destinations += [(number, dest, "reference-definition")
                         for number, dest in refs.values()]
        for number, dest, syntax in destinations:
            dest = dest.strip("<>")
            dest = re.sub(r"\\([() ])", r"\1", dest)
            parsed = urlsplit(dest)
            if parsed.scheme or parsed.netloc:
                external += 1
                continue
            if not parsed.path:
                fragments += 1
                continue
            target = Path(unquote(parsed.path))
            if not target.is_absolute():
                target = (ROOT / path).parent / target
            count += 1
            if not target.exists():
                errors.append({"path": path, "line": number,
                               "destination": dest, "syntax": syntax,
                               "resolvedPath": str(target.resolve())})
        results.append({**identity(path), "localFileDestinations": count,
                        "externalDestinationsNotFetched": external,
                        "sameDocumentFragmentsNotChecked": fragments})
    return {"files": results, "fileCount": len(paths),
            "localFileDestinations": sum(row["localFileDestinations"] for row in results),
            "missingLocalDestinations": errors,
            "scope": "File existence, not Markdown anchor or external URL certification."}


def status_assertions(status):
    expected = {
        "schemaVersion": 15, "productionBuild": "index-CWqdzert.js",
        "productionCss": "index-DEZFMW6R.css", "nextPhaseStarted": False,
        "humanAcceptanceCertified": False,
        "tests.studio.passed": 284, "tests.studio.failed": 0,
        "tests.focusedSeparateRun.passed": 48,
        "tests.focusedIsSuiteSubset": True, "tests.countsCombined": False,
        "tests.independentHelperCasesIncludedInSuite": 9,
        "tests.parameterHelpCatalogCoverage.fields": 34,
        "tests.parameterHelpCatalogCoverage.parameterizedModules": 12,
        "tests.parameterHelpCatalogCoverage.coverage": 34,
        "tests.strictTypescriptExitCode": 0, "tests.buildExitCode": 0,
        "authoring.baseModules": 17, "authoring.transparentStartingGraphs": 3,
        "authoring.modulesOrPresetsAddedThisRound": 0,
        "authoring.finalBrowserGraph.nodes": 4, "authoring.finalBrowserGraph.edges": 3,
        "authoring.savedDraftRevision": 44, "authoring.savedDraftStorageRevision": 2,
        "authoring.finalBuildFromZeroConstruction": False,
        "authoring.finalBuildRestoredAndEditedDraft": True,
        "authoring.generatedSourceThisRound": False,
        "authoring.newManagedOpenedThisRound": False,
        "authoring.publicationExportedThisRound": False,
        "authoring.fullReopenedParameterUIExposed": False,
        "authoring.actualDeferredOutOfOrderBrowserSample": False,
        "authoring.humanNoviceCertification": False,
        "authoring.runtimeOrTrainingCertification": False,
        "browser.frameCount": 22, "browser.rawFileCount": 88,
        "browser.jpegCount": 22, "browser.independentPublicEndpointChecks": 61,
        "browser.independentPixelsPersonallyObserved": 22,
        "browser.rootPixelsPersonallyObservedSubset": 11,
        "browser.countsCombined": False, "browser.actual100PercentLocalPairObserved": True,
        "browser.full100PercentOverviewCertified": False,
        "browser.fullAestheticsCertified": False,
        "humanResearch.assigned": 0, "humanResearch.collected": 0,
        "humanResearch.researchers": 0, "humanResearch.aiCountedAsHuman": False,
        "aiReview.rolesAreHumanParticipants": False,
        "performance.currentStudioAbMeasured": False,
        "performance.threeReplicateMatrixComplete": False,
        "performance.presentedFpsCertified": False,
        "service.priorSession": 58729, "service.priorLastExitCode": 143,
        "service.priorExitReason": "unknown", "service.restartSession": 63768,
        "implementationDirection.failedPrototypeRuntimeUsed": False,
        "implementationDirection.failedPrototypeFallback": False,
        "implementationDirection.certifiedPrototypeReuseCandidates": 0,
        "implementationDirection.modelExecutionThisRound": False,
        "implementationDirection.dependenciesInstalledThisRound": False,
    }
    errors = []
    for key, value in expected.items():
        actual = status
        try:
            for part in key.split("."):
                actual = actual[part]
        except (KeyError, TypeError):
            actual = "MISSING"
        if actual != value:
            errors.append({"field": key, "expected": value, "actual": actual})
    if not status["phaseStatus"].startswith("M4 partial"):
        errors.append({"field": "phaseStatus", "actual": status["phaseStatus"]})
    return {"assertionCount": len(expected) + 1, "mismatches": errors}


def main():
    seal = read(SEAL1)
    prior_path = WORK + "prior-bsa-seal-readback-attempt-1.json"
    prior = read(prior_path)
    bsa = read(prior["priorSeal"]["path"])
    correction_path = WORK + "handoff-manifest-correction-attempt-1/before-manifest.json"
    correction = read(correction_path)
    overrides = {row["path"]: row["archive"] for row in correction["records"]}
    top = check(seal["records"], overrides=overrides)
    old_prior = check(prior["records"], "resolvedPath")
    preview1_path = WORK + "preview-handoff-attempt-1/manifest.json"
    preview1 = read(preview1_path)
    preview1_check = check(preview1["records"])
    preview2_path = WORK + "preview-handoff-attempt-2/manifest.json"
    preview2 = read(preview2_path)
    preview2_check = check(preview2["records"])
    copy_check = check(preview2["records"], "copiedFrom")
    status_path = "docs/evidence/m4-human-review-handoff-status-followup.json"
    status = read(status_path)
    links = local_links(ENTRY_DOCS)
    archive_path = WORK + "before-current-doc-update-attempt-1/manifest.json"
    archives = read(archive_path)
    source_path = WORK + "acceptance-attempt-1/source-and-checks-report-attempt-4.json"
    source = read(source_path)
    counts = {row["kind"]: row["stdoutSummary"] for row in source["receipts"]}
    browser_path = WORK + "browser-attempt-3/manifest.json"
    browser = read(browser_path)
    assertions = status_assertions(status)
    lead_errors = []
    for path in ENTRY_DOCS:
        text = (ROOT / path).read_text()
        lead = "\n".join(text.splitlines()[:10])
        if path == "docs/m4-authoring-guidance.md":
            lead = text
        for token in ("index-CWqdzert.js", "index-DEZFMW6R.css", "284", "48", "34", "22", "partial", "M5"):
            if token not in lead:
                lead_errors.append({"path": path, "missingCurrentLeadToken": token})
    reports = {
        "initialSealResolved": {k:v for k,v in top.items() if k != "resolved"},
        "initialSealExplicitArchivePaths": overrides,
        "priorReceiptOriginal431RecordsMatchSeal": same_rows(bsa["records"], prior["records"]),
        "priorReceiptOriginal431Readback": {k:v for k,v in old_prior.items() if k != "resolved"},
        "previewAttempt1InternalBindings": {k:v for k,v in preview1_check.items() if k != "resolved"},
        "correctionArchiveBindings": {k:v for k,v in check(correction["records"], "archive").items() if k != "resolved"},
        "beforeCurrentDocArchiveBindings": {k:v for k,v in check(archives["records"], "archive").items() if k != "resolved"},
        "correctedPreviewBindings": {k:v for k,v in preview2_check.items() if k != "resolved"},
        "correctedPreviewExactOriginalCopies": {k:v for k,v in copy_check.items() if k != "resolved"},
        "currentStatusRefBindings": {k:v for k,v in check(status["evidenceRefs"]).items() if k != "resolved"},
        "currentStatusAssertions": assertions,
        "localLinks": links, "currentEntryLeadErrors": lead_errors,
        "sourceReportBoundCounts": counts,
        "sourceParameterCoverage": source["parameterCoverage"],
        "browserRawBindings": {k:v for k,v in check(browser["records"]).items() if k != "resolved"},
        "browserAssets": {k:v for k,v in check(browser["assets"]).items() if k != "resolved"},
    }
    failures = [
        {"id": "F1", "kind": "internally-invalid-preview-self-record",
         "finding": "Original preview manifest declares its own bytes=0 and empty-file SHA, contrary to its actual bytes. Identity of this manifest in seal1 does not validate its nested self-record.",
         "evidence": preview1_check["mismatches"],
         "resolution": "Original preserved; corrected attempt2 excludes itself and contains three exact copies, with no new browser actions."},
        {"id": "F2", "kind": "stale-prior-status-current-exact-resolution",
         "finding": "Prior receipt attempt1 still resolves old schema14 status as current-exact after schema15 replaced it. Its original 431 records match BSA seal, but one resolvedPath is now stale.",
         "evidence": old_prior["mismatches"],
         "resolution": "Original preserved; subsequent independent narrow audit must inspect corrected prior receipt attempt2 with five explicit archives."},
    ]
    inputs = [SEAL1, prior_path, prior["priorSeal"]["path"], correction_path,
              archive_path, preview1_path, preview2_path, status_path, source_path,
              browser_path, WORK + "acceptance-attempt-1/browser-and-save-report-attempt-1.json",
              WORK + "pixel-review-attempt-1/report.json", WORK + "root-pixel-review-attempt-1.json"]
    report = {
        "protocol": "archcanvas-guidance-independent-final-readback/1",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "reviewer": "/root/guidance_acceptance", "reviewerType": "AI; not human",
        "verdict": "failed-original-nested-ledgers-with-explicit-corrections-retained",
        "scope": "Read-only file binding, current entry/stage local links and bounded claim audit. Earlier independent source/check/DOM/save work is reused. No browser/test/build/model execution.",
        "initialObservation": "Before correction, seal1 333/333 top-level records independently read exact. Following correction, the same original 333 records resolve via two explicitly archived pre-correction files.",
        "failures": failures, "checks": reports,
        "inputs": [identity(path) for path in inputs],
        "boundaries": [
            "M4 partial; M5 not started; real human participants zero.",
            "48 focused cases are a subset of284; nine helper cases are included,34 AST field checks are not extra test cases.",
            "22 final frame groups/88raw are restored/edited final-CW chain evidence; intermediate DS from-zero construction retains historical scope.",
            "61 endpoint checks certify sampled anchor consistency; pixels are attributed to the separate22-image AI reviewer and11-image root subset, never added together.",
            "Handoff preview three files are separate from22validation frames; service exit143 reason remains unknown and restored session63768 is a point observation.",
            "No all-module beginner, generation, physical publication, arbitrary routing, presented FPS, out-of-order response browser or full reopened-parameter UI certification.",
            "Historical nested pixel input hashes retain original-time roles; top-level identity is not complete recursive narrative certification.",
        ],
        "auditSource": identity(str(Path(__file__).relative_to(ROOT))),
    }
    output = Path(__file__).with_name("report.json")
    with output.open("x") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"report": identity(str(output.relative_to(ROOT))),
                      "retainedFailures": len(failures),
                      "original333Resolved": top["exact"],
                      "old431ResolvedPathMismatches": len(old_prior["mismatches"]),
                      "linkDestinations": links["localFileDestinations"],
                      "linkErrors": links["missingLocalDestinations"],
                      "statusAssertionErrors": assertions["mismatches"],
                      "entryLeadErrors": lead_errors}, ensure_ascii=False))


if __name__ == "__main__":
    main()
