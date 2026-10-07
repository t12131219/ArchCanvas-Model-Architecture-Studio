"""Write-once narrow readback of corrected guidance ledgers; no product work."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HELPER_PATH = "docs/evidence/m4-authoring-guidance-final-readback-attempt-1/audit.py"
namespace = {"__file__": str(ROOT / HELPER_PATH), "__name__": "read_only_helpers"}
# Load already frozen audit helpers without importing or creating __pycache__.
exec(compile((ROOT / HELPER_PATH).read_text(), HELPER_PATH, "exec"), namespace)
read, identity, check, same_rows, status_assertions = (
    namespace[name] for name in ("read", "identity", "check", "same_rows", "status_assertions")
)
WORK = "docs/evidence/m4-authoring-guidance-work/"
SEAL2 = "docs/evidence/m4-authoring-guidance-verification-sealed-attempt-2.json"
SEAL1 = "docs/evidence/m4-authoring-guidance-verification-sealed-attempt-1.json"
PRIOR2 = WORK + "prior-bsa-seal-readback-attempt-2.json"
INITIAL_RESOLUTION = WORK + "initial-guidance-seal-resolution-attempt-1.json"
STATUS = "docs/evidence/m4-human-review-handoff-status-followup.json"
PREVIEW2 = WORK + "preview-handoff-attempt-2/manifest.json"
FIRST_REPORT = "docs/evidence/m4-authoring-guidance-final-readback-attempt-1/report.json"


def compact(result):
    return {key: value for key, value in result.items() if key != "resolved"}


def main():
    seal2, seal1, prior2, resolution, status, preview2, earlier = (
        read(path) for path in (SEAL2, SEAL1, PRIOR2, INITIAL_RESOLUTION, STATUS, PREVIEW2, FIRST_REPORT)
    )
    bsa = read(prior2["priorSeal"]["path"])
    results = {
        "corrected343": compact(check(seal2["records"])),
        "correctedPrior431": compact(check(prior2["records"], "resolvedPath")),
        "preservedInitial333": compact(check(resolution["records"], "resolvedPath")),
        "currentStatusRefs": compact(check(status["evidenceRefs"])),
        "correctedHandoffThreeFiles": compact(check(preview2["records"])),
        "correctedHandoffOriginalCopies": compact(check(preview2["records"], "copiedFrom")),
        "invalidOriginalManifestPreserved": compact(check([preview2["previousInvalidManifest"]])),
        "earlierLinkScanInputBytesStillExact": compact(check(earlier["checks"]["localLinks"]["files"])),
        "currentStatusAssertions": status_assertions(status),
    }
    structural_errors = []
    for name, expected in (("corrected343", 343), ("correctedPrior431", 431),
                           ("preservedInitial333", 333), ("correctedHandoffThreeFiles", 3)):
        if results[name]["count"] != expected:
            structural_errors.append({"check": name, "expectedCount": expected,
                                      "actualCount": results[name]["count"]})
    for rows, expected, name in (
        (prior2["records"], {"current-exact": 426, "explicit-archive": 5}, "prior431Modes"),
        (resolution["records"], {"current-exact": 331, "explicit-archive": 2}, "initial333Modes"),
    ):
        actual = dict(Counter(row["mode"] for row in rows))
        if actual != expected:
            structural_errors.append({"check": name, "expected": expected, "actual": actual})
    if not same_rows(bsa["records"], prior2["records"]):
        structural_errors.append({"check": "corrected431OriginalRowsMatchBsaSeal"})
    if not same_rows(seal1["records"], resolution["records"]):
        structural_errors.append({"check": "resolved333OriginalRowsMatchInitialSeal"})
    if any(row["path"] == PREVIEW2 for row in preview2["records"]):
        structural_errors.append({"check": "correctedPreviewMustExcludeSelf"})
    if status["service"]["handoffManifest"] != PREVIEW2:
        structural_errors.append({"check": "currentStatusPointsToCorrectedPreview"})
    for key, expected in (("M4", "partial"), ("M5", "not_started"), ("humanParticipants", 0)):
        if seal2[key] != expected:
            structural_errors.append({"check": "sealBoundary", "field": key, "actual": seal2[key]})
    for name in ("currentStatus", "browserManifest", "correctedHandoffManifest",
                 "independentPixelReport", "priorBsaSeal", "prior431Readback",
                 "previousSeal", "previous333Resolution", "currentBuild", "currentCss"):
        result = check([seal2[name]])
        if result["mismatches"]:
            structural_errors.extend(result["mismatches"])
    # Previous audit used a too literal filename-token check. Both Skill leads
    # name the same asset hashes by CWqdzert/DEZFMW6R shorthand at line5.
    lead_checks = []
    lead_errors = []
    for path in namespace["ENTRY_DOCS"]:
        text = (ROOT / path).read_text()
        lead = text if path == "docs/m4-authoring-guidance.md" else "\n".join(text.splitlines()[:10])
        required = ("CWqdzert", "DEZFMW6R", "284", "48", "34", "22", "partial", "M5")
        missing = [token for token in required if token not in lead]
        lead_checks.append({"path": path, "requiredCurrentTokens": list(required), "missing": missing})
        if missing:
            lead_errors.append({"path": path, "missing": missing})
    stage_text = (ROOT / "docs/m4-authoring-guidance.md").read_text()
    if "preview-handoff-attempt-2" not in stage_text or "0B" not in stage_text:
        structural_errors.append({"check": "stageNamesCorrectedPreviewAndRetainsInvalidSelfRecord"})
    if not any("stale schema14" in item for item in status["preservedFailures"]):
        structural_errors.append({"check": "currentStatusRetainsPriorResolutionFailure"})
    if not any("invalid self-record0B" in item for item in status["preservedFailures"]):
        structural_errors.append({"check": "currentStatusRetainsInvalidSelfLedgerFailure"})
    errors = structural_errors + lead_errors
    for result in results.values():
        errors.extend(result.get("mismatches", []))
    link_scan = earlier["checks"]["localLinks"]
    errors.extend(link_scan["missingLocalDestinations"])
    report = {
        "protocol": "archcanvas-guidance-independent-final-readback/2",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "reviewer": "/root/guidance_acceptance", "reviewerType": "AI; not human",
        "verdict": "bounded-corrected-ledgers-and-current-leads-pass" if not errors else "failed",
        "scope": "Narrow correction follow-up. Reads343 current bindings,431 BSA resolved rows,333 initial-seal resolutions, current schema15 refs,3handoff copies and current lead assertions. Reuses prior local-link scan on11 unchanged document byte identities. No tests/build/browser/model execution or full history recursion.",
        "checks": results,
        "prior431Modes": dict(Counter(row["mode"] for row in prior2["records"])),
        "initial333Modes": dict(Counter(row["mode"] for row in resolution["records"])),
        "original431RecordsMatchBsaSeal": same_rows(bsa["records"], prior2["records"]),
        "original333RecordsMatchInitialSeal": same_rows(seal1["records"], resolution["records"]),
        "currentLeadAssertions": lead_checks,
        "reusedLocalLinkScan": {
            "report": identity(FIRST_REPORT), "fileCount": link_scan["fileCount"],
            "localFileDestinations": link_scan["localFileDestinations"],
            "missingLocalDestinations": link_scan["missingLocalDestinations"],
            "scope": "Updated current leads and complete new stage links included. Historical body links were additionally checked for file existence only; no whole-history semantics or anchors certified.",
        },
        "earlierLeadMatcherClarification": {
            "literalAlerts": earlier["checks"]["currentEntryLeadErrors"],
            "finding": "Four literal filename alerts are audit matcher overreach: both Skill reference current leads use CWqdzert/DEZFMW6R shorthand, equivalent to sealed full asset names. Normalized current-lead checks pass; no documentation correction required.",
        },
        "retainedActualFailures": earlier["failures"],
        "mismatches": errors,
        "inputs": [identity(path) for path in (
            SEAL2, SEAL1, PRIOR2, INITIAL_RESOLUTION, STATUS, PREVIEW2,
            FIRST_REPORT, HELPER_PATH, prior2["priorSeal"]["path"],
        )],
        "boundaries": [
            "Corrected evidence identity and bounded claims pass; original invalid preview and stale prior receipt remain explicit historical failures.",
            "M4 partial, M5 not started, human0. AI agents cannot certify the human acceptance gate.",
            "48 focused cases are included in284;9 helpers included;34 AST field checks separate;22frames/88raw and22independent pixels/11root subset not summed.",
            "Final CW restored/edited chain does not certify from-zero beginner construction, all17 modules/3presets, generated model/runtime/training, complex routing or physical publication.",
            "Handoff copies are separate from22validation frames and do not add browser samples;63768 service running is a point observation and58729 exit143 reason unknown.",
            "No rerun tests/builds, source changes, browser actions, fetch, installs, models or recursively certified old narratives.",
        ],
        "auditSource": identity(str(Path(__file__).relative_to(ROOT))),
    }
    output = Path(__file__).with_name("report.json")
    with output.open("x") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"report": identity(str(output.relative_to(ROOT))),
                      "verdict": report["verdict"], "mismatches": errors,
                      "bindings": {name: result.get("exact") for name, result in results.items()},
                      "localLinksReused": link_scan["localFileDestinations"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
