"""Independent read-only audit for the frontier-status-v2 research package."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
PACKAGE = PROJECT / ".archcanvas/m4-research-trial-frontier-status-v2"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inventory(root: Path) -> dict[str, dict[str, object]]:
    return {
        str(path.relative_to(root)): {"bytes": path.stat().st_size, "sha256": digest(path.read_bytes())}
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def main() -> None:
    before = inventory(PACKAGE)
    manifest_path = PACKAGE / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    checks: list[dict[str, object]] = []

    def check(name: str, condition: bool) -> None:
        checks.append({"name": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)

    check("formal root and protocol", Path(manifest["formalRoot"]).resolve() == PROJECT and manifest["protocol"] == "archcanvas-m4-trial-package/1")
    check("prepared state has no researchers", manifest["state"] == "prepared-no-participants" and manifest["researcherCount"] == 0 and manifest["researchGate"] == "not_run")

    expected = {"scripts/research_trial.py", "scripts/research_trial_core.mjs", "scripts/export_canvas.mjs", "scripts/summarize_research_tasks.py"}
    expected.update(str(path.relative_to(PROJECT)) for path in (PROJECT / "src").rglob("*.py"))
    expected.update(str(path.relative_to(PROJECT)) for path in (PROJECT / "studio/src").rglob("*") if path.is_file() and path.suffix in {".ts", ".tsx", ".css"})
    expected.update(str(path.relative_to(PROJECT)) for path in (PROJECT / "studio/dist").rglob("*") if path.is_file())
    observed = {item["path"] for item in manifest["implementationFiles"]}
    check("implementation inventory is complete and unique", len(observed) == len(manifest["implementationFiles"]) == len(expected) and observed == expected)
    for item in manifest["implementationFiles"]:
        path = PROJECT / item["path"]
        check("implementation bytes " + item["path"], path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(PROJECT) and path.stat().st_size == item["bytes"] and digest(path.read_bytes()) == item["sha256"])

    baseline_files = {item["path"] for item in manifest["baseline"]["files"]}
    check("baseline has four exact files", baseline_files == {"baseline/architecture.json", "baseline/canvas.json", "baseline/source/blocks.py", "baseline/source/model.py"})
    baseline_doc = json.loads((PACKAGE / "baseline/canvas.json").read_bytes())
    baseline_arch = json.loads((PACKAGE / "baseline/architecture.json").read_bytes())
    canonical = json.dumps(baseline_doc, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    check("baseline identity and digest", baseline_doc["id"] == manifest["baseline"]["documentId"] and baseline_doc["revision"] == 0 and baseline_doc["architecture"] == baseline_arch and digest(canonical) == manifest["baseline"]["canvasCanonicalDigest"])
    check("baseline is pristine", all(not baseline_doc[key] for key in ["displayAliases", "nodeStyleOverrides", "edgeStyleOverrides", "annotations", "pinnedObjects"]))

    slots = manifest["slots"]
    check("five unique pristine slots and registered ports", [slot["slotId"] for slot in slots] == ["S01", "S02", "S03", "S04", "S05"] and [slot["port"] for slot in slots] == [43711, 43712, 43713, 43714, 43715])
    for slot in slots:
        slot_dir = PACKAGE / "slots" / slot["slotId"]
        envelope_path = PACKAGE / slot["baselineEnvelope"]["path"]
        envelope = json.loads(envelope_path.read_bytes())
        check(slot["slotId"] + " unassigned and exact baseline", slot["participantCode"] is None and slot["assignment"] == "unassigned" and not (slot_dir / "assignment.json").exists() and envelope["document"] == baseline_doc and envelope["revision"] == 1 and envelope_path.stat().st_size == slot["baselineEnvelope"]["bytes"] and digest(envelope_path.read_bytes()) == slot["baselineEnvelope"]["sha256"])
        for relative in ("incoming", "workspace/exports", "workspace/projects", "workspace/transactions"):
            path = slot_dir / relative
            check(slot["slotId"] + " empty " + relative, not path.exists() or not any(path.iterdir()))
        review = json.loads((slot_dir / "review-template.json").read_bytes())
        check(slot["slotId"] + " blank review template", review["slotId"] == slot["slotId"] and review["participantCode"] is None and review["reviewer"] is None and review["status"] == "pending-independent-review")

    environment = json.loads((PACKAGE / "environment-template.json").read_bytes())
    check("environment awaits operator observation", environment["status"] == "pending-operator-observation" and environment["browserName"] is None and environment["browserVersion"] is None and environment["hardware"] is None and environment["viewport"] is None and environment["devicePixelRatio"] is None and environment["fontResolutionEvidence"] == [])
    check("audit does not mutate package", inventory(PACKAGE) == before)
    report = {
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "status": "passed-independent-frozen-readiness-audit",
        "package": str(PACKAGE),
        "manifestSha256": digest(manifest_bytes),
        "implementationBindings": len(observed),
        "baselineBindings": 4,
        "pristineSlots": len(slots),
        "registeredPorts": [slot["port"] for slot in slots],
        "passed": sum(item["passed"] for item in checks),
        "total": len(checks),
        "checks": checks,
        "boundaries": {"assigned": 0, "collected": 0, "researchers": 0, "servicesStarted": False, "portsAvailabilityChecked": False, "browserTaskPerformed": False, "modelExecuted": False, "humanPublicationReviewed": False, "preparationIsNotHumanAcceptance": True, "m4": "partial", "m5": "not_started"},
        "scope": "Independent JSON/bytes/inventory/pristine readiness audit only; no product helper import, service, assignment, collection, model execution, human task, performance or publication acceptance.",
    }
    (HERE / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "passed": report["passed"], "total": report["total"], "implementationBindings": len(observed), "pristineSlots": len(slots), "researchers": 0}))


if __name__ == "__main__":
    main()
