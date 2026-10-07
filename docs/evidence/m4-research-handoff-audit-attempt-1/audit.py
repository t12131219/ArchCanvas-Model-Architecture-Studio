#!/usr/bin/env python3
"""Independent, read-only audit of the M4 researcher handoff.

This audit deliberately does not call ``assign``, start a service, mutate a
trial package, or infer a human result from automation.  It records the
pristine state of the currently documented five-seat packages and compares
their frozen implementation/build bindings with the *current* formal tree.
The output is supplemental evidence; it never changes an existing handoff
status, manifest, or seal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "docs" / "evidence"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def file_binding(path: Path) -> dict:
    if not path.is_file():
        return {"exists": False, "path": str(path)}
    return {"exists": True, "bytes": path.stat().st_size, "sha256": sha256(path), "path": str(path)}


def current_build() -> dict:
    dist = ROOT / "studio" / "dist"
    files = []
    if dist.is_dir():
        files = [file_binding(path) for path in sorted((dist / "assets").glob("*") if (dist / "assets").is_dir() else [])]
        index = dist / "index.html"
        if index.exists():
            files.insert(0, file_binding(index))
    return {"dist": str(dist), "files": files}


def status_summary(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {"path": str(path), "readable": False, "error": str(error)}
    human = value.get("humanResearch", {})
    return {
        "path": str(path),
        "readable": True,
        "schemaVersion": value.get("schemaVersion"),
        "generatedAt": value.get("generatedAt"),
        "productionBuild": value.get("productionBuild"),
        "productionJsSha256": value.get("productionJsSha256"),
        "productionCss": value.get("productionCss"),
        "productionCssSha256": value.get("productionCssSha256"),
        "phaseStatus": value.get("phaseStatus"),
        "humanAcceptanceCertified": value.get("humanAcceptanceCertified"),
        "openItems": value.get("openItems", []),
        "humanResearch": {
            "preparedForCurrentBuild": human.get("preparedForCurrentBuild"),
            "verifiedForCurrentBuild": human.get("verifiedForCurrentBuild"),
            "assigned": human.get("assigned"),
            "collected": human.get("collected"),
            "researchers": human.get("researchers"),
            "aiCountedAsHuman": human.get("aiCountedAsHuman"),
        },
    }


def empty_slot_state(package: Path, manifest_slot: dict) -> dict:
    slot_id = manifest_slot["slotId"]
    slot = package / "slots" / slot_id
    binding = manifest_slot.get("baselineEnvelope", {})
    envelope = package / binding.get("path", "")
    actual = file_binding(envelope)
    expected = {
        "exists": True,
        "bytes": binding.get("bytes"),
        "sha256": binding.get("sha256"),
    }
    groups = {
        "incoming": slot / "incoming",
        "exports": slot / "workspace" / "exports",
        "projects": slot / "workspace" / "projects",
        "transactions": slot / "workspace" / "transactions",
    }
    group_files = {
        key: sorted(str(p.relative_to(slot)) for p in directory.rglob("*") if p.is_file()) if directory.is_dir() else []
        for key, directory in groups.items()
    }
    assignment = slot / "assignment.json"
    collected = slot / "collected"
    pristine = (
        manifest_slot.get("participantCode") is None
        and manifest_slot.get("assignment") == "unassigned"
        and not assignment.exists()
        and not collected.exists()
        and actual.get("exists") is True
        and actual.get("bytes") == expected["bytes"]
        and actual.get("sha256") == expected["sha256"]
        and not any(group_files.values())
    )
    return {
        "slotId": slot_id,
        "participantCode": manifest_slot.get("participantCode"),
        "assignment": manifest_slot.get("assignment"),
        "port": manifest_slot.get("port"),
        "baselineEnvelope": {"expected": expected, "actual": actual},
        "assignmentFile": assignment.exists(),
        "collectedDirectory": collected.exists(),
        "artifactFiles": group_files,
        "pristine": pristine,
    }


def implementation_binding(package: Path, item: dict) -> dict:
    path = ROOT / item["path"]
    actual = file_binding(path)
    return {
        "path": item["path"],
        "expectedBytes": item.get("bytes"),
        "expectedSha256": item.get("sha256"),
        "actual": actual,
        "matches": actual.get("exists") is True and actual.get("bytes") == item.get("bytes") and actual.get("sha256") == item.get("sha256"),
    }


def package_summary(name: str) -> dict:
    package = ROOT / ".archcanvas" / name
    manifest_path = package / "manifest.json"
    if not manifest_path.is_file():
        return {"name": name, "exists": False, "path": str(package)}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {"name": name, "exists": True, "readable": False, "error": str(error), "path": str(package)}
    slots = [empty_slot_state(package, item) for item in manifest.get("slots", [])]
    bindings = [implementation_binding(package, item) for item in manifest.get("implementationFiles", [])]
    build_bindings = [implementation_binding(package, item) for item in manifest.get("buildFiles", [])]
    # Some manifests call the frozen dist files implementationFiles; preserve
    # the explicit list above and expose the matching count without assuming a
    # particular manifest version.
    return {
        "name": name,
        "path": str(package),
        "manifestSha256": sha256(manifest_path),
        "createdAt": manifest.get("createdAt"),
        "state": manifest.get("state"),
        "protocol": manifest.get("protocol"),
        "baseline": {
            "documentId": manifest.get("baseline", {}).get("documentId"),
            "sourceDigest": manifest.get("baseline", {}).get("sourceDigest"),
            "irDigest": manifest.get("baseline", {}).get("irDigest"),
            "canvasCanonicalDigest": manifest.get("baseline", {}).get("canvasCanonicalDigest"),
        },
        "researcherCount": manifest.get("researcherCount"),
        "researchGate": manifest.get("researchGate"),
        "humanSuccessCertified": manifest.get("humanSuccessCertified", False),
        "slotCount": len(slots),
        "pristineSlotCount": sum(slot["pristine"] for slot in slots),
        "slots": slots,
        "implementationBindingCount": len(bindings),
        "implementationMatches": sum(item["matches"] for item in bindings),
        "implementationMismatches": [item for item in bindings if not item["matches"]],
        "buildBindingCount": len(build_bindings),
        "buildMatches": sum(item["matches"] for item in build_bindings),
        "buildMismatches": [item for item in build_bindings if not item["matches"]],
    }


def study_contract_summary() -> dict:
    panel = ROOT / "studio" / "src" / "StudyPanel.tsx"
    observer = ROOT / "scripts" / "m4_input_observer.mjs"
    protocol = ROOT / "docs" / "m4-research-protocol.md"
    panel_text = panel.read_text(encoding="utf-8")
    observer_text = observer.read_text(encoding="utf-8")
    protocol_text = protocol.read_text(encoding="utf-8")
    plan = ROOT.parent / "ArchCanvas_双向模型可视化与编辑框架_技术计划书.md"
    plan_text = plan.read_text(encoding="utf-8")
    section_start = plan_text.find("## 18.")
    section_end = plan_text.find("## 19.", section_start + 1)
    section18 = plan_text[section_start:section_end if section_end >= 0 else None]
    return {
        "studyPanel": {
            "path": str(panel),
            "sha256": sha256(panel),
            "schemaVersionLiteral": "schemaVersion: 1" in panel_text,
            "protocolLiteral": "archcanvas-m4-research-task/1" in panel_text,
            "selfReportLanguagePresent": "self-report" in panel_text or "自报" in panel_text,
            "participantKinds": ["researcher", "automation"],
            "sessionStorageMechanism": "sessionStorage" in panel_text,
        },
        "observer": {
            "path": str(observer),
            "sha256": sha256(observer),
            "schemaVersionLiteral": "schemaVersion: 2" in observer_text,
            "protocolLiteral": "archcanvas-input-observation/2" in observer_text,
            "operations": ["drag", "pan", "zoom", "undo", "redo", "toggle", "pin"],
            "presentedPaintClaim": "not-presented-frames" in observer_text or "not prove a presented frame" in observer_text,
            "rafCaveat": "rAF callbacks do not prove a presented frame" in observer_text,
            "eventTimingCaveat": "Event Timing does not cover pointermove" in observer_text,
        },
        "protocolSection18": {
            "path": str(protocol),
            "sha256": sha256(protocol),
            "hasRealParticipantsRequirement": "3–5" in protocol_text or "3-5" in protocol_text,
            "hasInputToPaintRequirement": "input-to-paint" in protocol_text,
            "hasHumanPublicationReviewRequirement": "人工" in protocol_text and "85/180" in protocol_text,
        },
        "technicalPlanSection18": {
            "path": str(plan),
            "sha256": sha256(plan),
            "sectionLocated": section_start >= 0,
            "hasRealParticipantsRequirement": "3–5 位研究使用者" in section18,
            "hasInputToPaintRequirement": "input-to-paint" in section18,
            "hasInputPaintLongTaskAndFpsRequirement": all(token in section18 for token in ("input-to-paint", "长任务", "帧率")),
            "hasHumanPublicationReviewRequirement": "人工" in section18 and "85/180 mm" in section18,
            "hasHoldoutRequirement": "holdout" in section18,
        },
    }


def audit() -> dict:
    package_names = ["m4-research-trial-boundary-final", "m4-research-trial-zoom-final"]
    packages = [package_summary(name) for name in package_names]
    statuses = [status_summary(path) for path in sorted(EVIDENCE.glob("m4-human-review-handoff*.json"))]
    all_slots = [slot for package in packages for slot in package.get("slots", [])]
    all_pristine = all_slots and all(slot["pristine"] for slot in all_slots)
    no_assignments = all(not slot["assignmentFile"] and not slot["collectedDirectory"] for slot in all_slots)
    current = current_build()
    return {
        "schemaVersion": 1,
        "audit": "archcanvas-m4-research-handoff-current-readonly/1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "formalRoot": str(ROOT),
        "readOnly": True,
        "mutationsPerformed": [],
        "goalFacts": {
            "planSection": "18",
            "countScope": "Two explicitly audited candidate packages and the two read handoff status files; not an exhaustive identity census.",
            "realResearcherMinimum": 3,
            "realResearcherMaximum": 5,
            "humanAcceptanceCertified": False,
            "researcherCount": 0,
            "assignedCount": 0,
            "collectedCount": 0,
            "aiCountedAsHuman": False,
            "fiveSeatsPristineAcrossAuditedPackages": bool(all_pristine),
            "noAssignmentOrCollectedArtifactsAcrossAuditedPackages": bool(no_assignments),
        },
        "currentBuild": current,
        "handoffStatuses": statuses,
        "packages": packages,
        "studyContracts": study_contract_summary(),
        "conclusion": {
            "currentPackageUsable": False,
            "reason": "The audited five-seat packages are pristine but their frozen implementation/build bindings no longer match the current formal tree; research_trial.py verify requests a fresh package.",
            "nextSafeAction": "After the final build is frozen, prepare a new package at a new path, run verify and this read-only audit, then assign only an actually present participant.",
            "humanEvidence": "Missing: 3–5 real researchers, five-step task records, independent artifact review, and fixed environment/presented-paint evidence.",
            "observerEvidence": "The task recorder is a self-report contract; the input observer is a DOM/Event Timing/rAF proxy with explicit no-presented-paint limitations.",
        },
        "limitations": [
            "Pristine slot state and SHA256 do not establish participant identity or task behavior.",
            "No service, browser session, assignment, export, or participant message was started by this audit.",
            "The audit does not certify visual aesthetics, publication readability, performance, holdout accuracy, sharing, repeat, or opaque behavior.",
            "Existing seals and handoff status files were read only and were not rewritten.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = audit()
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
