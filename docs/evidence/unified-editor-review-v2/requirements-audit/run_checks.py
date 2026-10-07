"""Record current, nonexecuting requirements 1–3 checks with fresh input hashes.

This audit does not certify human usability, numerical execution, or global
routing aesthetics. A prepare run is explicitly provisional while code changes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
RESEARCH = PROJECT / "docs/evidence/catalog-research-v1"
REFERENCE = PROJECT.parent / "Source_Code_Project/DL-Playground"


def stamp():
    return datetime.now(timezone.utc).isoformat()


def binding(path: Path, relative_to=PROJECT):
    body = path.read_bytes()
    return {"path": str(path.relative_to(relative_to)), "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest()}


def inputs():
    files = set()
    for root, suffix in [(PROJECT / "src", ".py"), (PROJECT / "studio/src", ".ts"),
                         (PROJECT / "studio/src", ".tsx"), (PROJECT / "studio/src", ".css"),
                         (PROJECT / "studio/tests", ".ts"), (PROJECT / "tests", ".py")]:
        files.update(root.rglob(f"*{suffix}"))
    for fixture in ("mlp", "residual_cnn", "transformer"):
        files.update((PROJECT / "fixtures" / fixture).rglob("*.py"))
    for name in ("pyproject.toml", "studio/package.json", "studio/package-lock.json", "studio/tsconfig.json"):
        path = PROJECT / name
        if path.exists():
            files.add(path)
    return [binding(path) for path in sorted(files)]


def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def run(name, command, cwd):
    started = stamp()
    result = subprocess.run(command, cwd=cwd, env={**os.environ, "PYTHONPATH": str(PROJECT / "src")},
                            capture_output=True, text=True, timeout=120)
    output = result.stdout + result.stderr
    log = HERE / f"{name}.log"
    log.write_text(output)
    node = re.search(r"ℹ tests (\d+).*?ℹ pass (\d+).*?ℹ fail (\d+)", output, re.S)
    python = re.search(r"Ran (\d+) tests", output)
    return {"command": command, "cwd": str(cwd), "startedAt": started, "finishedAt": stamp(),
            "exitCode": result.returncode, "log": binding(log),
            "tests": {"total": int(node[1]), "passed": int(node[2]), "failed": int(node[3])} if node else
                     {"total": int(python[1]), "passed": int(python[1]) if result.returncode == 0 else None} if python else None}


def research_readback():
    receipt = json.loads((RESEARCH / "network-receipt.json").read_text())
    snapshots = []
    for entry in receipt["entries"]:
        if "snapshot" not in entry:
            continue
        actual = binding(RESEARCH / entry["snapshot"])
        snapshots.append({"url": entry["url"], "httpStatus": entry.get("httpStatus"), **actual,
                          "matches": actual["bytes"] == entry["bytes"] and actual["sha256"] == entry["sha256"],
                          "apiContent": "docs/stable" not in entry["url"]})
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REFERENCE, capture_output=True, text=True, check=True).stdout.strip()
    license_names = subprocess.run(["git", "ls-files", "*LICENSE*", "*COPYING*"], cwd=REFERENCE,
                                   capture_output=True, text=True, check=True).stdout.splitlines()
    expected_head = "c07a79b60bcb67be0bec2276002bd21f92a616de"
    return {"createdAt": stamp(), "scope": "Recorded online research integrity and current licensed/reference source identity; no reference implementation imported",
            "receipt": binding(RESEARCH / "network-receipt.json"), "snapshots": snapshots,
            "allSnapshotHashesMatch": all(entry["matches"] for entry in snapshots),
            "successfulSnapshotCount": len(snapshots),
            "failedRequests": [entry for entry in receipt["entries"] if "error" in entry],
            "dlPlayground": {"path": str(REFERENCE), "head": head, "expectedHead": expected_head,
                             "matchesExpected": head == expected_head, "trackedLicenseFiles": license_names,
                             "referenceFiles": [binding(REFERENCE / name, REFERENCE) for name in ("README.md", "frontend/src/nodes/registry.ts")],
                             "use": "Public category/discovery reference only; no copied implementation or assets"}}


def catalog_readback():
    sys.path.insert(0, str(PROJECT / "src"))
    import archcanvas_authoring
    current = archcanvas_authoring.module_catalog()
    snapshot = json.loads((RESEARCH / "catalog-snapshot.json").read_text())
    atomic = json.loads((RESEARCH / "atomic-roundtrips.json").read_text())
    preset = json.loads((RESEARCH / "preset-roundtrips.json").read_text())
    receipt = json.loads((RESEARCH / "catalog-contract-receipt.json").read_text())
    artifacts = []
    for entry in receipt["artifacts"]:
        actual = binding(PROJECT / entry["path"])
        artifacts.append({**actual, "matches": actual["bytes"] == entry["bytes"] and actual["sha256"] == entry["sha256"]})
    return {"createdAt": stamp(), "runtimeModulePath": str(Path(archcanvas_authoring.__file__).resolve()),
            "runtimeIsFormalSource": Path(archcanvas_authoring.__file__).resolve().is_relative_to(PROJECT / "src"),
            "catalogMatchesRecordedSnapshot": current == snapshot,
            "catalog": {"atomic": len(current["modules"]), "categories": len({entry["category"] for entry in current["modules"]}),
                        "transparentPresets": preset["count"]},
            "atomicKindsMatchActualRuntime": {entry["kind"] for entry in current["modules"]} == {entry["kind"] for entry in atomic["checks"]},
            "atomicChecks": {"total": len(atomic["checks"]), "allPassed": all(entry["status"] == "passed" for entry in atomic["checks"]),
                             "modelExecutionNotRun": all(entry["modelExecution"] == "not_run" for entry in atomic["checks"])},
            "presetChecks": {"total": len(preset["results"]), "allPassed": all(entry["status"] == "passed" for entry in preset["results"]),
                             "modelExecutionNotRun": all(entry["modelExecution"] == "not_run" for entry in preset["results"])},
            "allRecordedArtifactHashesMatch": all(entry["matches"] for entry in artifacts), "artifacts": artifacts,
            "limits": ["Only static generation/AST contracts, not numerical or execution equivalence", "Historical roundtrip receipts checked for integrity; current source also gets fresh tests"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", choices=("prepare", "final"), default="prepare")
    args = parser.parse_args()
    before = inputs()
    write(f"inputs-{args.label}-before.json", before)
    research = research_readback()
    catalog = catalog_readback()
    write(f"research-readback-{args.label}.json", research)
    write(f"catalog-readback-{args.label}.json", catalog)
    node = ["node", "--experimental-strip-types", "--test", "--test-isolation=none"]
    tests = {
        "sourceContinuity": run(f"source-continuity-{args.label}", node + ["tests/source-authoring-session.test.ts", "tests/source-authoring-compact-ui.test.ts", "tests/generated-canvas.test.ts"], PROJECT / "studio"),
        "catalog": run(f"catalog-{args.label}", node + ["tests/draft-palette-discovery-independent.test.ts", "tests/authoring-presets.test.ts"], PROJECT / "studio"),
        "infiniteCanvas": run(f"infinite-canvas-{args.label}", node + ["tests/infinite-canvas.test.ts"], PROJECT / "studio"),
        "pythonBridgeCatalogGroups": run(f"python-focused-{args.label}", [str(PROJECT / ".venv/bin/python"), "-m", "unittest", "tests.test_source_authoring_bridge", "tests.test_authoring_group_generation", "tests.test_authoring_catalog_expanded"], PROJECT),
    }
    after = inputs()
    write(f"inputs-{args.label}-after.json", after)
    current = {"schema": "archcanvas.unified-editor-requirements-1-3-checks/2", "createdAt": stamp(),
               "label": args.label, "provisional": args.label != "final", "inputsStableDuringRun": before == after,
               "tests": tests, "researchReadback": binding(HERE / f"research-readback-{args.label}.json"),
               "catalogReadback": binding(HERE / f"catalog-readback-{args.label}.json"),
               "allChecksPassed": before == after and all(test["exitCode"] == 0 for test in tests.values()) and
                                  research["allSnapshotHashesMatch"] and research["dlPlayground"]["matchesExpected"] and
                                  catalog["catalogMatchesRecordedSnapshot"] and catalog["allRecordedArtifactHashesMatch"],
               "limits": ["Requirements 1–3 only; final route audit/browser readback independently required", "M4 human participants remain 0; publication review remains open", "No model execution"]}
    write(f"checks-{args.label}.json", current)
    print(json.dumps({"label": args.label, "allChecksPassed": current["allChecksPassed"], "inputsStableDuringRun": current["inputsStableDuringRun"],
                      "tests": {name: result["tests"] for name, result in tests.items()}, "researchSnapshots": research["successfulSnapshotCount"],
                      "catalog": catalog["catalog"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
