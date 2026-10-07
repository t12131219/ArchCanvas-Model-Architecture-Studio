"""Seal current evidence; preserve older bytes and explicitly exclude live state."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "docs/evidence/m4-bcf-browser-matrix-work"
SEAL = ROOT / "docs/evidence/m4-bcf-browser-matrix-current-verification-sealed.json"
OLD_SEAL = ROOT / "docs/evidence/m4-authoring-feedback-current-verification-sealed.json"
ARCHIVE = ROOT / "docs/evidence/before-m4-bcf-browser-matrix/manifest.json"
STATUS = ROOT / "docs/evidence/m4-human-review-handoff-status.json"
LIVE_LOGS = {
    "docs/evidence/m4-bcf-browser-matrix-work/service-permitted.log",
    "docs/evidence/m4-authoring-feedback/root/service-permitted.log",
}


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def binding(path: Path) -> dict:
    relative = path.relative_to(ROOT).as_posix()
    if path.is_symlink() or ROOT not in path.resolve().parents:
        raise ValueError(f"Refusing nonlocal/symlink binding: {relative}")
    data = path.read_bytes()
    return {"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check(item: dict, path: Path) -> None:
    actual = binding(path)
    assert actual["sha256"] == item["sha256"], f"SHA changed: {path}"
    if "bytes" in item:
        assert actual["bytes"] == item["bytes"], f"Size changed: {path}"


def check_archive(path: Path, expected_count: int) -> dict:
    archive = read(path)
    assert archive["bindingCount"] == len(archive["bindings"]) == expected_count
    previous = ROOT / archive["previousSeal"]
    assert binding(previous)["sha256"] == archive["previousSealSha256"]
    archived_previous = path.parent / "previous-seal.json"
    assert previous.read_bytes() == archived_previous.read_bytes()
    old = read(previous)
    old_items = {(item["path"], item["sha256"], item["bytes"]) for item in old["bindings"]}
    archived_items = {(item["path"], item["sha256"], item["bytes"]) for item in archive["bindings"]}
    assert old_items == archived_items
    for item in archive["bindings"]:
        check(item, ROOT / item["archivePath"])
    return {"manifest": binding(path), "previousSeal": binding(previous), "bindingsExact": expected_count}


def checks() -> dict:
    status = read(STATUS)
    assert status["schemaVersion"] == 6
    assert status["phaseStatus"] == "partial" and status["nextPhaseStarted"] is False
    assert status["research"]["researcherCount"] == status["research"]["collectedParticipants"] == 0
    assert status["currentMatrix"]["baselineCases"] == 36 and status["currentMatrix"]["editedModels"] == 3
    assert status["currentMatrix"]["humanCertified"] is False
    for reference in status["references"].values():
        check(reference, ROOT / reference["path"])
    guard = read(WORK / "preparation-guard.json")
    assert len(guard["frozenSourceAndBuild"]) == 70
    for relative, sha in guard["frozenSourceAndBuild"].items():
        check({"sha256": sha}, ROOT / relative)
    matrix = read(ROOT / "docs/evidence/browser-visual-matrix-bcf-full/manifest.json")
    assert matrix["capturedBaselineCount"] == 36 and matrix["missingBaselineVariants"] == []
    assert len(matrix["captures"]) == 39 and len(matrix["editedAfterModelsCaptured"]) == 3
    assert matrix["artifactCoverage"] == "complete"
    assert matrix["visualAcceptance"] == "pending-human-review" and matrix["humanAcceptanceCertified"] is False
    return {
        "statusReferencesExact": len(status["references"]),
        "currentSourceBuildGuardExact": 70,
        "previousArchives": [
            check_archive(ARCHIVE, 478),
            check_archive(ROOT / "docs/evidence/before-m4-authoring-feedback/manifest.json", 1277),
        ],
        "matrixCounts": {"baselines": 36, "editedModels": 3, "captures": 39},
        "humanAcceptanceCertified": False,
        "productTestsRerun": False,
    }


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    return not (
        "__pycache__" in path.parts
        or path.suffix == ".pyc"
        or relative in LIVE_LOGS
        or relative.startswith("docs/evidence/m4-bcf-browser-matrix-work/native-current/service-data/")
        or relative.startswith("docs/evidence/m4-bcf-browser-matrix-work/final-seal-review-")
        or path.name.startswith("seal-verification-")
        or path == SEAL
    )


def create() -> None:
    assert not SEAL.exists(), "Use a new seal path; no overwrite"
    report = checks()
    assert (WORK / "final-document-review-1/manifest.json").is_file(), "Wait for independent document review"
    paths = {ROOT / item["path"] for item in read(OLD_SEAL)["bindings"]}
    directories = [
        WORK,
        ROOT / "docs/evidence/browser-visual-matrix-bcf-full",
        ARCHIVE.parent,
        ROOT / ".archcanvas/browser-visual-matrix-authoring-feedback-bcf",
        ROOT / ".archcanvas/m4-research-trial-authoring-feedback-bcf",
        *[ROOT / part for part in ("src", "scripts", "tests", "fixtures", "schemas", "skills/archcanvas", "studio/src", "studio/tests", "studio/dist")],
    ]
    for directory in directories:
        paths.update(path for path in directory.rglob("*") if path.is_file())
    paths.update({OLD_SEAL, STATUS, ROOT / "docs/m4-bcf-browser-matrix.md"})
    records = [binding(path) for path in sorted(paths) if included(path)]
    status = read(STATUS)
    seal = {
        "schemaVersion": 1,
        "sealedAt": datetime.now(timezone.utc).isoformat(),
        "state": "complete-current-artifact-coverage-diagnostics-with-failures-M4-partial",
        "scope": "Unchanged Bc production/source bytes; root-operated native browser evidence, independent AI pixel/XML/event/file audits, current documents/status and recoverable prior478 bytes. Hash checks certify bytes and explicit coverage, not publication aesthetics, presented performance or human acceptance.",
        "currentStatus": binding(STATUS),
        "productionBuild": status["productionBuild"],
        "productionJsSha256": status["productionJsSha256"],
        "productionCssSha256": status["productionCssSha256"],
        "verification": report,
        "bindingCount": len(records),
        "bindings": records,
        "excludedMutableOrPostSealPaths": [*sorted(LIVE_LOGS), "native-current/service-data/**", "**/__pycache__/**", "**/*.pyc", "final-seal-review-*/**", "seal-verification-*.json", "live8968/8947 stores are outside selected directories"],
        "limits": [
            "AI operator/auditor roles count as zero human researchers/publication reviewers.",
            "39-case baseline/edited collection is separate from four native diagnostic sessions.",
            "Long16 native frame buffers each dropped4102; original failed pan verdict and truncated reads are preserved.",
            "EventTiming percentiles use unique matched subsets per session; never overall INP or presented FPS.",
            "Four-direction node drag exposes parent/header/sibling conflicts and body paths; commit success is not aesthetics.",
            "No compositor presented trace, active held-pointer cancel, nonempty pins, physical-size/fonts/hardware certification.",
            "Native public SVG restoration does not certify hidden history, saved Canvas or novice task completion.",
            "Current17 module palette has no composite presets; no all17-module actual-browser retest this round.",
            "Studio136 and standalone9 are retained Bc test scope; Python319 retains obx-time binding/unchanged Python scope. No product suite rerun or model execution this collection round.",
            "Old failures/manifests/seals/raw retained; M4partial, no M5 entry.",
        ],
    }
    with SEAL.open("x") as stream:
        json.dump(seal, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    verify()


def verify() -> None:
    seal = read(SEAL)
    assert seal["bindingCount"] == len(seal["bindings"])
    paths = [item["path"] for item in seal["bindings"]]
    assert len(paths) == len(set(paths))
    for item in seal["bindings"]:
        check(item, ROOT / item["path"])
    report = checks()
    print(json.dumps({"seal": binding(SEAL), "bindingCount": seal["bindingCount"], "checks": report}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("create", "verify"))
    args = parser.parse_args()
    create() if args.command == "create" else verify()
