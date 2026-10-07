"""Independent read-only byte/inventory/pristine checks for the prepared pack.

This auditor imports no product helper, serves no HTTP, runs no generated model
and cannot certify participant identity, browser hardware/fonts or human tasks.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
PACKAGE = PROJECT / ".archcanvas/m4-research-trial-bxh-current"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def files(directory: Path) -> dict:
    return {str(path.relative_to(directory)): {"bytes": len(path.read_bytes()), "sha256": sha(path.read_bytes())}
            for path in sorted(directory.rglob("*")) if path.is_file()}


def main() -> None:
    before = files(PACKAGE)
    manifest_raw = (PACKAGE / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    checks = []

    def check(name: str, condition: bool) -> None:
        checks.append({"name": name, "passed": bool(condition)})
        assert condition, name

    check("formal root matches independent project path", Path(manifest["formalRoot"]).resolve() == PROJECT)
    check("prepared protocol/version and zero researchers", manifest["schemaVersion"] == 1 and manifest["protocol"] == "archcanvas-m4-trial-package/1"
          and manifest["state"] == "prepared-no-participants" and manifest["researcherCount"] == 0 and manifest["researchGate"] == "not_run")
    expected_implementation = {"scripts/research_trial.py", "scripts/research_trial_core.mjs", "scripts/export_canvas.mjs", "scripts/summarize_research_tasks.py"}
    expected_implementation.update(str(path.relative_to(PROJECT)) for path in (PROJECT / "src").rglob("*.py"))
    expected_implementation.update(str(path.relative_to(PROJECT)) for path in (PROJECT / "studio/src").rglob("*")
                                   if path.is_file() and path.suffix in {".ts", ".tsx", ".css"})
    expected_implementation.update(str(path.relative_to(PROJECT)) for path in (PROJECT / "studio/dist").rglob("*") if path.is_file())
    observed_paths = [item["path"] for item in manifest["implementationFiles"]]
    check("independent current implementation inventory is exactly83", len(observed_paths) == 83 and len(set(observed_paths)) == 83
          and set(observed_paths) == expected_implementation)
    for item in manifest["implementationFiles"]:
        path = PROJECT / item["path"]
        data = path.read_bytes()
        check("implementation bytes " + item["path"], not path.is_symlink() and path.resolve().is_relative_to(PROJECT)
              and len(data) == item["bytes"] and sha(data) == item["sha256"])
    expected_baseline = {"baseline/architecture.json", "baseline/canvas.json", "baseline/source/blocks.py", "baseline/source/model.py"}
    check("baseline inventory is exactly four regular files", set(before).intersection(expected_baseline) == expected_baseline
          and {item["path"] for item in manifest["baseline"]["files"]} == expected_baseline)
    for item in manifest["baseline"]["files"]:
        path = PACKAGE / item["path"]
        data = path.read_bytes()
        check("baseline bytes " + item["path"], not path.is_symlink() and path.resolve().is_relative_to(PACKAGE)
              and len(data) == item["bytes"] and sha(data) == item["sha256"])
    for name in ("blocks.py", "model.py"):
        check("frozen fixture source " + name, (PACKAGE / "baseline/source" / name).read_bytes() == (PROJECT / "fixtures/transformer" / name).read_bytes())
    document = json.loads((PACKAGE / "baseline/canvas.json").read_bytes())
    architecture = json.loads((PACKAGE / "baseline/architecture.json").read_bytes())
    canonical = json.dumps(document, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    baseline = manifest["baseline"]
    check("baseline canonical document digest", sha(canonical) == baseline["canvasCanonicalDigest"])
    check("baseline document/source/IR identity", document["id"] == baseline["documentId"] and document["revision"] == baseline["visualRevision"] == 0
          and document["sourceBindingDigest"] == architecture["sourceDigest"] == baseline["sourceDigest"]
          and architecture["irDigest"] == baseline["irDigest"] and document["architecture"] == architecture)
    check("baseline presentation overrides and pins are pristine", all(not document[key] for key in ["displayAliases", "nodeStyleOverrides", "edgeStyleOverrides", "annotations", "pinnedObjects"]))
    check("five unique slots and requested registered ports", [slot["slotId"] for slot in manifest["slots"]] == ["S01", "S02", "S03", "S04", "S05"]
          and [slot["port"] for slot in manifest["slots"]] == [43451, 43452, 43453, 43454, 43455])
    slot_results = []
    for slot in manifest["slots"]:
        identity = slot["slotId"]
        directory = PACKAGE / "slots" / identity
        check(identity + " no participant or assignment", slot["participantCode"] is None and slot["assignment"] == "unassigned"
              and not (directory / "assignment.json").exists() and not (directory / "collected").exists())
        check(identity + " isolated exact documents dataDir", slot["dataDir"] == f"slots/{identity}/workspace/documents")
        envelope_binding = slot["baselineEnvelope"]
        envelope_path = PACKAGE / envelope_binding["path"]
        envelope_bytes = envelope_path.read_bytes()
        envelope = json.loads(envelope_bytes)
        check(identity + " exact baseline envelope binding", envelope_path.parent == directory / "workspace/documents"
              and not envelope_path.is_symlink() and len(envelope_bytes) == envelope_binding["bytes"] and sha(envelope_bytes) == envelope_binding["sha256"])
        check(identity + " independent baseline document and storage revision", envelope["document"] == document
              and envelope["revision"] == slot["baselineStorageRevision"] == 1)
        check(identity + " only one baseline document", {p.name for p in envelope_path.parent.iterdir()} == {envelope_path.name})
        empty_directories = []
        for relative in ("incoming", "workspace/exports", "workspace/projects", "workspace/transactions"):
            path = directory / relative
            check(identity + " empty " + relative, not path.exists() or (path.is_dir() and not any(path.iterdir())))
            empty_directories.append({"path": relative, "exists": path.exists(), "emptyOrAbsent": True})
        review = json.loads((directory / "review-template.json").read_bytes())
        check(identity + " blank human review template", review["slotId"] == identity and review["participantCode"] is None and review["reviewer"] is None
              and review["status"] == "pending-independent-review" and review["sourceUnchanged"] == review["publicationReadability"] == review["overallOutcome"] == "pending"
              and review["tasks"] == [{"task": i, "status": "pending", "evidencePaths": [], "notes": ""} for i in range(1, 6)])
        slot_results.append({"slotId": identity, "port": slot["port"], "dataDir": slot["dataDir"], "pristine": True,
                             "baselineEnvelope": envelope_binding, "emptyDirectories": empty_directories})
    environment = json.loads((PACKAGE / "environment-template.json").read_bytes())
    check("actual browser/font/hardware environment not fabricated", environment["status"] == "pending-operator-observation"
          and environment["fontResolutionEvidence"] == [] and all(environment[field] is None for field in ["browserName", "browserVersion", "hardware", "viewport", "devicePixelRatio"]))
    check("formal preparation interpreter/analyzer provenance", Path(manifest["preparationRuntime"]["pythonExecutable"]) == PROJECT / ".venv/bin/python"
          and Path(manifest["preparationRuntime"]["analyzerOrigin"]).resolve() == PROJECT / "src/archcanvas_python/frontend.py")
    final_checks = json.loads((PROJECT / "docs/evidence/m4-ai-simulated-current/checks-final-attempt-3/receipt.json").read_text())
    check("current strict347 receipt bound exactly103", len(final_checks["inputs"]) == 100 and len(final_checks["build"]) == 3 and final_checks["studioTests"] == 347 and final_checks["skipped"] == 0 and final_checks["inputsUnchanged"] and all(item["exitCode"] == 0 for item in final_checks["checks"]))
    for item in final_checks["inputs"] + final_checks["build"]:
        data = (PROJECT / item["path"]).read_bytes()
        check("frozen347 source/build unchanged " + item["path"], len(data) == item["bytes"] and sha(data) == item["sha256"])
    old = json.loads((HERE / "preflight.json").read_text())["oldResearchPackages"]
    for name, before_files in old.items():
        check("old package bytes untouched " + name, files(PROJECT / name) == before_files)
    check("new package all17 files unchanged by audit", files(PACKAGE) == before and len(before) == 17)
    report = {"createdUtc": datetime.now(timezone.utc).isoformat(), "status": "passed-independent-frozen-readiness-audit",
              "package": str(PACKAGE), "manifestSha256": sha(manifest_raw), "implementationBindings": 83,
              "baselineBindings": 4, "sourceBuild347BindingsExact": 103, "pristineSlots": 5, "slots": slot_results,
              "oldPackagesUntouched": len(old), "oldPackageFilesUntouched": sum(len(value) for value in old.values()),
              "packageFilesBeforeAfter": before, "passed": sum(check["passed"] for check in checks), "total": len(checks), "checks": checks,
              "boundaries": {"assigned": 0, "collected": 0, "researchers": 0, "servicesStarted": False, "portsAvailabilityChecked": False,
                             "browserTaskPerformed": False, "modelExecuted": False, "humanPublicationReviewed": False,
                             "preparationIsNotHumanAcceptance": True, "m4": "partial", "m5": "not_started"},
              "scope": "Independent JSON/bytes/catalog-free inventory/pristine readiness audit. No product verify/helper imported; does not evaluate real users, screenshots, runtime tensors, performance, fixed browser/fonts or publication quality."}
    (HERE / "readiness-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "passed": report["passed"], "total": report["total"], "pristineSlots": 5,
                      "implementationBindings": 83, "oldPackagesUntouched": len(old), "modelExecution": False}))


if __name__ == "__main__":
    main()
