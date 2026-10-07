"""Independent read-only byte/inventory/pristine checks for the prepared pack.

This auditor imports no product helper, serves no HTTP, runs no generated model
and cannot certify participant identity, browser hardware/fonts or human tasks.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
PACKAGE = PROJECT / ".archcanvas/m4-research-trial-viewport-resize-current"


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
    check("independent current implementation inventory matches dynamic formal source/build enumeration", len(observed_paths) == len(set(observed_paths)) == len(expected_implementation)
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
          and [slot["port"] for slot in manifest["slots"]] == list(range(43621, 43626)))
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
    prep = HERE.parent / "research-final-preparation"
    preparation_receipt = json.loads((prep / "process.json").read_bytes())
    official_receipt = json.loads((prep / "verify-initial.process.json").read_bytes())
    official_result = json.loads((prep / "verify-initial.stdout.json").read_bytes())
    check("reported formal prepare and verify succeeded with the exact package manifest", preparation_receipt["prepareExitCode"] == preparation_receipt["initialVerifyExitCode"] == official_receipt["exitCode"] == 0
          and preparation_receipt["preparedManifestSha256"] == sha(manifest_raw)
          and preparation_receipt["implementationBindings"] == len(expected_implementation)
          and official_receipt["command"] == [str(PROJECT / ".venv/bin/python"), "scripts/research_trial.py", "verify", "--package", str(PACKAGE)]
          and official_result["baselineAndImplementationUnchanged"] is True
          and official_result["preparationState"] == "prepared-no-participants" and official_result["researchGate"] == "not_evaluated")
    final_checks = json.loads((HERE.parent / "checks-final-attempt-2/receipt.json").read_bytes())
    check("current strict430 receipt binds separate source/build/publication inputs", len(final_checks["inputs"]) == 112 and len(final_checks["build"]) == 3 and len(final_checks["publicationInputs"]) == 11
          and final_checks["publicationInputsUnchanged"] and final_checks["inputsUnchanged"]
          and [item["label"] for item in final_checks["checks"]] == ["studio", "strict-build", "publication"]
          and all(item["exitCode"] == 0 for item in final_checks["checks"]))
    studio_log = (HERE.parent / "checks-final-attempt-2/studio.txt").read_text()
    publication_log = (HERE.parent / "checks-final-attempt-2/publication.txt").read_text()
    check("actual Studio430 passed0fail0skip", all(re.search(r"^ℹ " + label + " " + str(count) + r"$", studio_log, re.M) for label, count in [("tests", 430), ("pass", 430), ("fail", 0), ("skipped", 0), ("cancelled", 0)]))
    check("actual publication11 passed0skip", len(re.findall(r" \.\.\. ok$", publication_log, re.M)) == 11 and "Ran 11 tests in" in publication_log and publication_log.rstrip().endswith("OK") and "skipped" not in publication_log)
    for item in final_checks["inputs"] + final_checks["build"] + final_checks["publicationInputs"]:
        data = (PROJECT / item["path"]).read_bytes()
        check("frozen430 source/build/publication input unchanged " + item["path"], len(data) == item["bytes"] and sha(data) == item["sha256"])
    old_rows = json.loads((prep / "old-packages-before.json").read_bytes())
    old = {}
    for row in old_rows:
        package, relative = row["path"].split("/", 2)[1:]
        old.setdefault(".archcanvas/" + package, {})[relative] = {"bytes": row["bytes"], "sha256": row["sha256"]}
    current_old = {str(path.relative_to(PROJECT)) for path in (PROJECT / ".archcanvas").glob("m4-research-trial-*") if path.is_dir() and path != PACKAGE}
    check("old frozen inventory matches dynamic current package enumeration without duplicate records", len(old_rows) == len({row["path"] for row in old_rows})
          and set(old) == current_old and sum(len(value) for value in old.values()) == len(old_rows))
    for name, before_files in old.items():
        check("old package bytes untouched " + name, files(PROJECT / name) == before_files)
    check("new package all17 files unchanged by audit", files(PACKAGE) == before and len(before) == 17)
    report = {"createdUtc": datetime.now(timezone.utc).isoformat(), "status": "passed-independent-frozen-readiness-audit",
              "package": str(PACKAGE), "manifestSha256": sha(manifest_raw), "implementationBindings": len(observed_paths),
              "baselineBindings": 4, "sourceBuild430BindingsExact": len(final_checks["inputs"]) + len(final_checks["build"]), "publicationInputBindingsExact": 11, "pristineSlots": 5, "slots": slot_results,
              "oldPackagesUntouched": len(old), "oldPackageFilesUntouched": sum(len(value) for value in old.values()),
              "packageFilesBeforeAfter": before, "passed": sum(check["passed"] for check in checks), "total": len(checks), "checks": checks,
              "boundaries": {"assigned": 0, "collected": 0, "researchers": 0, "servicesStarted": False, "portsAvailabilityChecked": False,
                             "browserTaskPerformed": False, "modelExecuted": False, "humanPublicationReviewed": False,
                             "preparationIsNotHumanAcceptance": True, "m4": "partial", "m5": "not_started"},
              "scope": "Independent JSON/bytes/catalog-free inventory/pristine readiness audit. No product verify/helper imported; does not evaluate real users, screenshots, runtime tensors, performance, fixed browser/fonts or publication quality."}
    (HERE / "readiness-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "passed": report["passed"], "total": report["total"], "pristineSlots": 5,
                      "implementationBindings": len(observed_paths), "oldPackagesUntouched": len(old), "modelExecution": False}))


if __name__ == "__main__":
    main()
