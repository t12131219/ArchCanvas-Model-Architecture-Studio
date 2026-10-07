"""Prepare a draft gate and common headers from already frozen checks/readiness.

Browser-derived fields intentionally remain pending. This draft cannot be applied
by update_entries.py until those observations are supplied and reviewed.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def load(path):
    return json.loads((ROOT / path).read_bytes())


def main():
    out = HERE / "draft-facts.json"
    assert not out.exists(), "Do not overwrite an earlier facts draft"
    old = load("docs/evidence/m4-caption-route-current/before-change/inputs/docs/evidence/m4-current-gate-audit.json")
    independent = load("docs/evidence/m4-caption-route-current/independent-review/continuation-review/report.json")
    ready = load("docs/evidence/m4-caption-route-current/research-final-preparation/report.json")
    gate = deepcopy(old)
    gate["schema"] = "archcanvas-m4-current-gate-audit/5"
    gate["updated"] = "2026-10-06"
    gate["historicalBtwBuild"] = deepcopy(old["build"])
    gate["build"] = {
        "js": "index-Divs1MJA.js", "css": "index--unhoRTb.css",
        "checks": "docs/evidence/m4-caption-route-current/checks-final-attempt-3/receipt.json",
        "studioTests": 389, "skipped": 0, "strictBuildExitCode": 0,
        "publicationTests": 9, "publicationSkipped": 0,
        "sourceTestConfigBindings": 105, "distBindings": 3,
        "totalSourceBuildBindings": 108, "publicationInputBindings": 11,
        "focusedSuiteCountsAreOverlapping": True,
    }
    gate["historicalBtwResearchPackage"] = {
        **deepcopy(old["currentResearchPackage"]),
        "currentVerification": "stale",
        "officialStaleReceipt": "docs/evidence/m4-caption-route-current/research-preflight/btw-stale.process.json",
        "scope": "Historical BTw frozen readiness only; exact original package bytes retained. Official verify now refuses changed formal implementation. No participant data collected.",
    }
    gate["currentResearchPackage"] = {
        "path": ready["package"], "manifestSha256": ready["packageManifest"]["sha256"],
        "pristineSlots": 5, "assigned": 0, "collected": 0, "humans": 0,
        "registeredPorts": ready["readiness"]["portsRegistered"],
        "servicesStarted": False, "portsAvailabilityChecked": False,
        "currentVerification": "prepared_and_verified",
        "independentReadiness": ready["currentBuild"]["independentReadiness"],
        "implementationBindings": 84, "baselineBindings": 4,
        "preparationReport": "docs/evidence/m4-caption-route-current/research-final-preparation/report.json",
        "oldPackagesPreserved": 21, "oldPackageFilesPreserved": 359,
        "scope": "Frozen preparation/pristine readiness only; no browser task, human participants, service, assignment or collection. Registered ports not checked for availability.",
    }
    gate["currentStage"] = "docs/m4-caption-association-shortcuts.md"
    gate["currentEntryPreChangeArchive"] = "docs/evidence/m4-caption-route-current/before-change/manifest.json"
    gate["currentVisualApproval"] = "not_approved_bounded_caption_route_followup"
    reqs = {item["id"]: item for item in gate["requirements"]}
    visual = reqs["visual-authoring"]
    visual["historicalBtwScope"] = visual["scope"]
    visual["observedHistoricalBtwCaption"] = visual.pop("observedCurrentCaption")
    visual["scope"] = "Derived caption association and bounded final route shortcut now implemented. Browser/export followup pending in this draft; no global visual approval, full gesture matrix, per-kind generation/execution or human certification. Three actual historical AI roles remain DuFX/CC91/B_XH, auditors add no participants; 17 base modules and three transparent starts unchanged."
    visual["observedCurrentCaptionRoute"] = {
        "build": "index-Divs1MJA.js", "browserFollowup": "pending",
        "derivedCaptionGuideOnly": True, "guideArrow": False,
        "canonicalBindingAndDocumentSchemaChanged": False,
        "sourceFrontiers": independent["sourceFrontierScope"],
        "independentFiniteNominalMatrix": independent["matrix"],
        "independentAdversarial": independent["adversarial"],
        "independentStrokeRectangles": independent["visibleStrokes"],
        "independentNonadjacentSelf": independent["nonadjacentSelf"],
        "visualQualityApproved": False,
    }
    visual["evidence"] += [
        gate["currentStage"], gate["build"]["checks"],
        "docs/evidence/m4-caption-route-current/independent-review/continuation-review/report.json",
        "docs/evidence/m4-caption-route-current/independent-review/continuation-review/manifest.json",
        "docs/evidence/m4-caption-route-current/self-route-review/report.json",
    ]
    perf = reqs["browser-performance"]
    perf["historicalBtwScope"] = perf["scope"]
    perf["observedHistoricalBtw7"] = perf.pop("observedCurrentBtw7")
    perf["scope"] = "No new Divs native/performance sampling. BTw three matched durations160/72/160ms p95160 and rAF58.605395179Hz remain historical bounded subset; 304 DOM bodies then only6 geometric viewport intersections/4 fully inside. Different old viewports preclude A/B or improvement claim. Callback cadence is not presented FPS; current300-visible-objects, fullinputdenominator, observeroverhead, fixedhardware/fonts A/Bx3 and unrelatedpins/anchor acceptance remain unproved."
    perf["observedCurrentDivs"] = {"build": "index-Divs1MJA.js", "nativeSamplingPerformed": False,
                                   "performanceGatePassed": False, "presentedFpsCertified": False}
    research = reqs["research-task"]
    research["historicalBtwScope"] = research["scope"]
    research["scope"] = "Fresh Divs package prepare/verify and295/295 independent frozen readiness only. Five pristine seats43561–43565; none assigned/collected/served, availability notchecked. Twenty-one old packages359files exact. Human participants0; 3–5 realresearchers five-step tasks<=180s and>=80percentcompletion notdone. AI is not human evidence."
    research["evidence"] += [gate["currentResearchPackage"]["preparationReport"],
                             "docs/evidence/m4-caption-route-current/research-final-preparation/manifest.json",
                             "docs/evidence/m4-caption-route-current/research-preflight/btw-stale.process.json"]
    publication = reqs["publication-review"]
    publication["historicalBtwScope"] = publication["scope"]
    publication["observedHistoricalBtwExportPreflight"] = publication.pop("observedCurrentExportPreflight")
    publication["scope"] = "Divs actual browser export followup pending in draft. Historical BTw whole180min6.60pt/detail180min7.42pt are physical arithmetic only. 85/180mm humanreview, resolvedfonts, marker/join pixels, PDF publication approval notdone. Nominal geometry and AI reviews cannot approve this gate."
    facts = {
        "status": "draft_waiting_browser_receipt",
        "buildReceipt": gate["build"]["checks"], "browserReceipt": None,
        "independentReceipt": "docs/evidence/m4-caption-route-current/independent-review/continuation-review/report.json",
        "researchReadiness": gate["currentResearchPackage"]["preparationReport"],
        "finalGate": gate,
        "headers": {"cn": "PENDING FINAL BROWSER PROSE", "en": "PENDING FINAL BROWSER PROSE"},
        "researchCommandSection": "PENDING FINAL HEADER",
    }
    out.write_text(json.dumps(facts, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"draft": str(out.relative_to(ROOT)), "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
                      "applied": False, "waitingFor": "final browser/export receipt"}, indent=2))


if __name__ == "__main__":
    main()
