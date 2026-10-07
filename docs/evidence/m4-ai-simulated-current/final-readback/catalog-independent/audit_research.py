"""Read-only independent byte/JSON review; never imports or executes a model."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PACKAGE = ROOT / ".archcanvas/m4-research-trial-bxh-current"
EVIDENCE = ROOT / "docs/evidence/m4-ai-simulated-current/research-final-preparation"


def digest(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


checks = []
bindings = []


def check(name: str, condition: bool, detail=None):
    checks.append({"check": name, "passed": bool(condition), "detail": detail})


def bind(base: Path, expected: dict):
    actual = digest(base / expected["path"])
    good = all(actual[key] == expected[key] for key in ("bytes", "sha256"))
    bindings.append({**actual, "exact": good})
    check("byte binding: " + actual["path"], good)


expected_hashes = {
    PACKAGE / "manifest.json": "61ac9fbb61d26d1dd6b68bc0873955a3ec467bd2988b2e927e22f0a299162cdf",
    EVIDENCE / "report.json": "741be9945d6b1ca37a9d0d500b81bda4c07265f6db6e9e61bbae958013467bb0",
    EVIDENCE / "manifest.json": "8bb9e15215c210f45568c711387306cdcdcb732c2fc6da2f0628a584a63b0f84",
}
for path, expected_sha in expected_hashes.items():
    actual = digest(path)
    check("parent-provided final digest: " + actual["path"], actual["sha256"] == expected_sha)

manifest = read(PACKAGE / "manifest.json")
check("formal project path", manifest["formalRoot"] == str(ROOT))
check("no-participant gate", manifest["state"] == "prepared-no-participants"
      and manifest["researcherCount"] == 0 and manifest["researchGate"] == "not_run")
check("implementation inventory", len(manifest["implementationFiles"]) == 83)
for expected in manifest["implementationFiles"]:
    bind(ROOT, expected)
check("baseline inventory", len(manifest["baseline"]["files"]) == 4)
for expected in manifest["baseline"]["files"]:
    bind(PACKAGE, expected)

canvas = read(PACKAGE / "baseline/canvas.json")
canonical = json.dumps(canvas, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(",", ":")).encode("utf-8")
check("baseline canonical digest", hashlib.sha256(canonical).hexdigest()
      == manifest["baseline"]["canvasCanonicalDigest"])
check("baseline identity/revision", canvas["id"] == manifest["baseline"]["documentId"]
      and canvas["revision"] == manifest["baseline"]["visualRevision"] == 0)
slots = []
expected_files = {"README.md", "manifest.json", "environment-template.json"}
expected_files.update(x["path"] for x in manifest["baseline"]["files"])
check("five slot identifiers/ports", [s["slotId"] for s in manifest["slots"]]
      == [f"S{i:02}" for i in range(1, 6)]
      and [s["port"] for s in manifest["slots"]] == list(range(43451, 43456)))
for slot in manifest["slots"]:
    slot_root = PACKAGE / "slots" / slot["slotId"]
    bind(PACKAGE, slot["baselineEnvelope"])
    env = read(PACKAGE / slot["baselineEnvelope"]["path"])
    review_path = f"slots/{slot['slotId']}/review-template.json"
    review = read(PACKAGE / review_path)
    expected_files.update([slot["baselineEnvelope"]["path"], review_path])
    empty_dirs = {}
    for relative in ["incoming", "workspace/exports", "workspace/projects", "workspace/transactions"]:
        path = slot_root / relative
        empty_dirs[relative] = not path.exists() or not any(path.rglob("*"))
    pristine = (slot["participantCode"] is None and slot["assignment"] == "unassigned"
                and slot["baselineStorageRevision"] == env["revision"] == 1
                and env["document"] == canvas
                and list((PACKAGE / slot["dataDir"]).iterdir()) == [PACKAGE / slot["baselineEnvelope"]["path"]]
                and all(empty_dirs.values()))
    review_pending = (review["slotId"] == slot["slotId"] and review["participantCode"] is None
                      and review["reviewer"] is None and review["status"] == "pending-independent-review"
                      and [t["task"] for t in review["tasks"]] == list(range(1, 6))
                      and all(t["status"] == "pending" and t["evidencePaths"] == []
                              and t["notes"] == "" for t in review["tasks"])
                      and all(review[k] == "pending" for k in
                              ["sourceUnchanged", "publicationReadability", "overallOutcome"]))
    check(slot["slotId"] + " pristine equal-baseline workspace", pristine)
    check(slot["slotId"] + " empty pending human review", review_pending)
    slots.append({"slotId": slot["slotId"], "registeredPort": slot["port"],
                  "pristine": pristine, "documentEqualsBaseline": env["document"] == canvas,
                  "reviewPending": review_pending, "emptyDirectories": empty_dirs})
actual_files = {str(p.relative_to(PACKAGE)) for p in PACKAGE.rglob("*") if p.is_file()}
check("exact 17-file fresh package inventory", actual_files == expected_files and len(actual_files) == 17)
environment = read(PACKAGE / "environment-template.json")
check("environment observation pending", environment["status"] == "pending-operator-observation"
      and environment["fontResolutionEvidence"] == []
      and all(environment[k] is None for k in ["browserName", "browserVersion", "hardware", "viewport", "devicePixelRatio"]))

evidence_manifest = read(EVIDENCE / "manifest.json")
for expected in evidence_manifest["artifacts"]:
    bind(EVIDENCE, expected)
for expected in evidence_manifest["externalBindings"]:
    bind(ROOT, expected)

preflight = read(EVIDENCE / "preflight.json")
old_packages = preflight["oldResearchPackages"]
old_files = 0
for relative, old_inventory in old_packages.items():
    old_root = ROOT / relative
    actual_inventory = {str(p.relative_to(old_root)) for p in old_root.rglob("*") if p.is_file()}
    check("historical package exact inventory: " + relative, actual_inventory == set(old_inventory))
    for file_relative, expected in old_inventory.items():
        bind(old_root, {"path": file_relative, **expected})
        old_files += 1
check("historical package totals", len(old_packages) == 19 and old_files == 325)

process_records = read(EVIDENCE / "process.json")["processes"]
process_records.extend([read(EVIDENCE / filename) for filename in
                        ["verify-final.process.json", "readiness-audit-attempt-1.process.json",
                         "old-cc91-stale.process.json", "old-dufx-stale.process.json"]])
for process in process_records:
    expected_exit = 1 if process.get("staleExpected") else 0
    check("recorded process exit: " + process.get("name", process["argv"][-1]),
          process["exitCode"] == expected_exit and process["cwd"] == str(ROOT))
    for stream in ["stdout", "stderr"]:
        actual = digest(EVIDENCE / process[stream])
        expected_sha = process.get(stream + "Sha256", process.get("hashes", {}).get(stream))
        if expected_sha:
            check("process " + stream + " digest: " + actual["path"], actual["sha256"] == expected_sha)
for name in ["old-cc91-stale", "old-dufx-stale"]:
    check(name + " explicit stale refusal", "Formal implementation changed after preparation"
          in (EVIDENCE / (name + ".stderr.txt")).read_text())
verify = read(EVIDENCE / "verify-final.stdout.json")
check("final official verifier frozen-only scope", verify["baselineAndImplementationUnchanged"]
      and verify["researchGate"] == "not_evaluated"
      and verify["verificationScope"] == "frozen-baseline-and-implementation-only")
runtime = preflight["runtime"]
check("formal interpreter prefix and analyzer origin", runtime["prefix"] == str(ROOT / ".venv")
      and runtime["executable"] == str(ROOT / ".venv/bin/python")
      and Path(runtime["analyzerOrigin"]).is_relative_to(ROOT / "src")
      and (ROOT / ".venv/bin/python").resolve() == Path(preflight["pythonResolved"]))
check("bare import failure preserved", (EVIDENCE / preflight["retainedFailure"]).is_file())

report = {"schema": "archcanvas-independent-research-readback/1",
          "createdUtc": datetime.now(timezone.utc).isoformat(),
          "reviewerType": "AI-independent-byte-and-JSON-audit",
          "package": str(PACKAGE.relative_to(ROOT)),
          "packageManifest": digest(PACKAGE / "manifest.json"),
          "checks": checks, "checksPassed": sum(c["passed"] for c in checks),
          "checksTotal": len(checks), "bindings": bindings,
          "bindingCount": len(bindings),
          "freshImplementationBindings": 83, "baselineBindings": 4,
          "preparationEvidenceArtifactBindings": len(evidence_manifest["artifacts"]),
          "preparationEvidenceExternalBindings": len(evidence_manifest["externalBindings"]),
          "historicalPackagesUnchanged": len(old_packages), "historicalFilesUnchanged": old_files,
          "slots": slots, "assigned": 0, "collected": 0, "humanParticipants": 0,
          "boundaries": {"m4": "partial", "m5": "not_started", "servicesStartedByThisAudit": False,
                         "portsAvailabilityChecked": False, "modelExecuted": False,
                         "humanPublicationReviewed": False,
                         "productTestsNotRepeated": True,
                         "readinessChecksAreNotAdditionalProductTests": True},
          "scope": "Frozen bytes and pristine readiness only. Registered ports are not running services. "
                   "AI evidence is not human participation or publication acceptance."}
(HERE / "research-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
failed = [c for c in checks if not c["passed"]]
print(json.dumps({"checksPassed": report["checksPassed"], "checksTotal": len(checks),
                  "bindingCount": len(bindings), "failed": failed}, ensure_ascii=False))
raise SystemExit(1 if failed else 0)
