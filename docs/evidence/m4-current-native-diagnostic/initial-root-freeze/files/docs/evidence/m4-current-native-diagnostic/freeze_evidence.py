#!/usr/bin/env python3
"""Seal new diagnostics without rewriting an earlier evidence snapshot."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ARCHIVE = ROOT / "docs/evidence/before-current-native-diagnostic"
OUTPUT = ROOT / "docs/evidence/m4-current-native-verification.json"


def fingerprint(path: Path) -> dict:
    body = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest()}


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def seal() -> dict:
    previous_path = ROOT / "docs/evidence/m4-current-verification.json"
    previous = json.loads(previous_path.read_bytes())
    archive_manifest = json.loads((ARCHIVE / "manifest.json").read_bytes())
    archives = {item["originalPath"]: item for item in archive_manifest["files"]}
    for item in archives.values():
        found = fingerprint(ROOT / item["archivePath"])
        assert (found["sha256"], found["bytes"]) == (item["sha256"], item["bytes"])
    assert previous_path.read_bytes() == (ROOT / archives[str(previous_path.relative_to(ROOT))]["archivePath"]).read_bytes()

    resolved = []
    for name, expected in previous["bindings"].items():
        path = ROOT / name
        if name in archives:
            path = ROOT / archives[name]["archivePath"]
        found = fingerprint(path)
        assert found["sha256"] == expected, name
        resolved.append({"originalPath": name, **found})

    audit_path = HERE / "aggregate-current-audit.json"
    audit = json.loads(audit_path.read_bytes())
    assert audit["status"] == "passed-with-retained-pilot-and-explicit-limits"
    sessions = []
    for name, expected_successes, expected_trials, expected_p95 in [
        ("stress300", 5, 5, 2016), ("mlp-pilot", 1, 4, 2008),
        ("mlp-correct-target", 3, 3, 2016),
    ]:
        raw = json.loads((HERE / f"{name}-raw.json").read_bytes())
        validation = json.loads((HERE / f"{name}-validation.json").read_bytes())
        successes = sum(trial["operationSucceeded"] for trial in validation["trials"])
        assert (successes, len(raw["trials"])) == (expected_successes, expected_trials)
        assert validation["latency"]["matchedInteractionP95Ms"] == expected_p95
        assert validation["completeBuffers"] and not validation["errors"]
        sessions.append({"name": name, "requests": expected_trials, "succeeded": successes,
                         "matchedSubsetP95Ms": expected_p95,
                         "raw": fingerprint(HERE / f"{name}-raw.json"),
                         "validation": fingerprint(HERE / f"{name}-validation.json")})
    for model in ["stress300", "mlp"]:
        assert (HERE / f"{model}-saved-browser.svg").read_bytes() == (HERE / f"{model}-reopened-browser.svg").read_bytes()

    research_root = ROOT / ".archcanvas/m4-research-trial-publication-final"
    research_path = research_root / "manifest.json"
    research = json.loads(research_path.read_bytes())
    assert research["researcherCount"] == 0 and len(research["slots"]) == 5
    assert len(research["implementationFiles"]) == 58
    for item in research["implementationFiles"]:
        assert fingerprint(ROOT / item["path"])["sha256"] == item["sha256"]
    for slot in research["slots"]:
        assert slot["assignment"] == "unassigned" and slot["participantCode"] is None
        item = slot["baselineEnvelope"]
        path = research_root / item["path"]
        assert fingerprint(path)["sha256"] == item["sha256"]
        assert list(path.parent.glob("*")) == [path]
        slot_root = research_root / "slots" / slot["slotId"]
        assert not (slot_root / "assignment.json").exists()
        assert not (slot_root / "collected").exists()

    document_paths = [ROOT / name for name in archives if name.endswith(".md")]
    document_paths += list(HERE.glob("*.md")) + [ARCHIVE / "README.md"]
    links = []
    for path in document_paths:
        for target in re.findall(r"\]\(([^)\n]+)\)", path.read_text()):
            target = target.strip().strip("<>").split("#", 1)[0]
            if not target or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            destination = Path(target) if target.startswith("/") else path.parent / target
            assert destination.exists() or destination.resolve() in {OUTPUT, HERE / "manifest.json"}, (path, target)
            links.append({"file": str(path.relative_to(ROOT)), "target": target})

    now = datetime.now(timezone.utc).isoformat()
    summary = {"schemaVersion": 1, "frozenAt": now,
        "status": "partial-native-diagnostics-added-experience-gates-open",
        "formalFromScratch": True, "productBuildChanged": False,
        "previousSnapshot": fingerprint(previous_path),
        "previousBindings": {"count": len(resolved), "allMatchThroughExplicitArchiveResolver": True},
        "archiveManifest": fingerprint(ARCHIVE / "manifest.json"),
        "nativeSessions": sessions, "successfulRequests": 9, "retainedUncoveredRequests": 3,
        "twoSavedReopenedSvgPairsByteExact": True,
        "independentAudit": fingerprint(audit_path),
        "research": {"manifest": fingerprint(research_path), "implementationBindings": 58,
                     "pristineSlots": 5, "assigned": 0, "collected": 0, "researchers": 0,
                     "verification": fingerprint(HERE / "research-package-verification.json")},
        "localLinksChecked": len(links),
        "testsRerun": False, "productionBuildRerun": False,
        "diagnosticService": {"sessionId": 41743, "terminalExitCode": 143, "cause": "unknown", "onlineClaim": False},
        "openGates": ["fixed hardware and actually resolved fonts", "sustained presented input/frame performance",
                      "native active-gesture cancellation", "39-case human publication review and physical-size readability",
                      "3–5 actual researcher tasks"],
        "limitations": ["Three native latency distributions retain separate denominators.",
                        "Continuous input is a DOM proxy; rAF cadence is not presented FPS.",
                        "All agents and browser automation are excluded from human participant counts.",
                        "No unrelated pins were present in these sessions.",
                        "Earlier sealed snapshot/manifest bytes remain unchanged; seven mutable docs resolve to archived original bytes."]}
    write(HERE / "verification-summary.json", summary)
    local = [fingerprint(path) for path in sorted(HERE.rglob("*"))
             if path.is_file() and path.name != "manifest.json"]
    linked_paths = set(document_paths) | {previous_path, ARCHIVE / "manifest.json", research_path}
    linked_paths |= {ROOT / item["archivePath"] for item in archives.values()}
    for item in resolved:
        linked_paths.add(ROOT / item["path"])
    linked = [fingerprint(path) for path in sorted(linked_paths) if path.is_file() and HERE not in path.parents]
    manifest = {"schemaVersion": 1, "generatedAt": now,
                "scope": "Three actual same-build diagnostic sessions, two persistence chains, retained failures and explicit historical doc resolver. No human or performance certification.",
                "files": local, "linkedEvidence": linked,
                "historicalResolver": "before-current-native-diagnostic/files/<original-project-path> for updated documents in the previous 1475-binding snapshot."}
    write(HERE / "manifest.json", manifest)
    bindings = {item["path"]: item["sha256"] for item in local + linked}
    bindings[str((HERE / "manifest.json").relative_to(ROOT))] = fingerprint(HERE / "manifest.json")["sha256"]
    write(OUTPUT, {"schemaVersion": 1, "generatedAt": now, "status": summary["status"],
                   "summary": summary, "previousResolvedBindings": resolved, "bindings": bindings})
    for name, expected in bindings.items():
        assert fingerprint(ROOT / name)["sha256"] == expected, name
    return {"status": summary["status"], "localFiles": len(local), "linkedFiles": len(linked),
            "previousBindingsVerified": len(resolved), "currentBindingsVerified": len(bindings),
            "localLinksChecked": len(links), "allMatch": True,
            "verification": fingerprint(OUTPUT)}


if __name__ == "__main__":
    print(json.dumps(seal(), ensure_ascii=False))
