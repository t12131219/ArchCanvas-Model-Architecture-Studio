#!/usr/bin/env python3
"""Copy current formal base-model inputs and run the 11 static tests in isolation.

Only Python standard-library facilities are used. No installed framework or
failed prototype is needed; the complete temporary release and runtime output
are preserved at the requested output, including their original provenance.
"""

from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


PROJECT = Path(__file__).resolve().parents[3]
HISTORICAL_REPORTS = (
    "docs/evidence/m4-base-model-report.json",
    "docs/evidence/m4-base-model-independent-suite.txt",
    "docs/evidence/m4-holdout-report.json",
)
RUNNER = '''from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import unittest

release = Path(__file__).resolve().parent / "release"
artifacts = Path(__file__).resolve().parent / "artifacts"
artifacts.mkdir()
sys.path[:0] = [str(release / "src"), str(release / "tests")]
assert sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.flags.ignore_environment == 1
assert all("site-packages" not in path and "Studio_Temp" not in path and "Architecture Studio_Temp" not in path for path in sys.path)
blocked_import_attempts, blocked_execution_attempts = [], []
def enforce_static(event, arguments):
    if event == "import" and arguments[0].split(".")[0] in ("torch", "model", "blocks"):
        blocked_import_attempts.append(arguments[0])
        raise RuntimeError("Fixture/framework import prohibited in static audit: " + arguments[0])
    if event == "exec":
        filename = Path(arguments[0].co_filename)
        if filename.is_absolute() and filename.resolve().is_relative_to(release / "fixtures"):
            blocked_execution_attempts.append(str(filename))
            raise RuntimeError("Fixture execution prohibited in static audit")
sys.addaudithook(enforce_static)
import archcanvas_python
import archcanvas_python.frontend
import m4_base_model_oracle
import test_m4_base_models
suite = unittest.defaultTestLoader.loadTestsFromModule(test_m4_base_models)
result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
passed = result.wasSuccessful() and result.testsRun == 11 and not result.skipped
models = []
if passed:
    for name, expected in m4_base_model_oracle.BASE_MODELS.items():
        fixture = release / "fixtures" / expected["fixture"]
        architecture = archcanvas_python.analyze_project(fixture, expected["entry"])
        proof = test_m4_base_models.check_base_model(architecture, name, fixture)
        architecture_file = artifacts / (name + ".architecture.json")
        proof_file = artifacts / (name + ".oracle-proof.json")
        architecture_file.write_text(json.dumps(architecture, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
        proof_file.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
        models.append({"name": name, "entry": expected["entry"], "sourceDigest": architecture["sourceDigest"], "irDigest": architecture["irDigest"],
                       **{key: proof[key] for key in ("nodeCount", "edgeCount", "portCount", "tensorCount", "callCount", "instanceCount")},
                       "opaqueNodeCount": sum(node["evidence"] == "opaque" for node in architecture["nodes"]),
                       "architecture": str(architecture_file), "oracleProof": str(proof_file)})
origins = {name: str(Path(module.__file__).resolve()) for name, module in sorted(sys.modules.items())
           if name.startswith("archcanvas_") and getattr(module, "__file__", None)}
assert origins and all(Path(path).is_relative_to(release / "src") for path in origins.values())
assert Path(test_m4_base_models.__file__).resolve().is_relative_to(release / "tests")
assert Path(m4_base_model_oracle.__file__).resolve().is_relative_to(release / "tests")
fixture_module_origins = {name: str(Path(module.__file__).resolve()) for name, module in sys.modules.items()
                         if getattr(module, "__file__", None) and Path(module.__file__).resolve().is_relative_to(release / "fixtures")}
assert not fixture_module_origins and not blocked_import_attempts and not blocked_execution_attempts
report = {"schemaVersion": 1, "finishedAt": datetime.now(timezone.utc).isoformat(), "passed": passed,
          "scope": "Exactly the current 11 MLP/ResidualCNN static source-authored oracle tests, including 9 deliberate corruption cases",
          "standaloneCopy": str(release), "python": sys.executable, "pythonVersion": sys.version,
          "pythonIsolation": {"isolated": sys.flags.isolated, "noSite": sys.flags.no_site, "ignoreEnvironment": sys.flags.ignore_environment, "sysPath": sys.path},
          "independentSuite": {"testsRun": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)},
          "models": models, "packageOrigins": origins,
          "testOrigins": {"checker": str(Path(test_m4_base_models.__file__).resolve()), "oracle": str(Path(m4_base_model_oracle.__file__).resolve())},
          "fixtureModuleOrigins": fixture_module_origins, "blockedFixtureOrFrameworkImportAttempts": blocked_import_attempts,
          "blockedFixtureExecutionAttempts": blocked_execution_attempts,
          "fixtureImport": False, "modelExecution": False,
          "limitations": ["Static AST contracts only; no concrete shape/dtype, numerical forward/backward equivalence or arbitrary model family certification.",
                          "No browser interaction/performance, publication readability, paint, native cancellation or human acceptance is certified.",
                          "Source ranges and expressions are checked; every parameter origin is not independently certified."]}
(artifacts / "static-oracle-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
sys.exit(0 if passed else 1)
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(root):
    return [{"path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": sha(path)}
            for path in sorted(root.rglob("*")) if path.is_file()]


def run(output):
    if (output / "run").exists() or (output / "report.json").exists():
        raise RuntimeError("Use a fresh output directory; refusing to overwrite retained evidence")
    started = datetime.now(timezone.utc).isoformat()
    temporary = Path(tempfile.mkdtemp(prefix="archcanvas-base-model-current-", dir="/tmp"))
    release = temporary / "release"
    release.mkdir()
    paths = sorted(path.relative_to(PROJECT) for path in (PROJECT / "src").rglob("*.py"))
    paths += [Path(name) for name in (
        "tests/test_m4_base_models.py", "tests/m4_base_model_oracle.py",
        "fixtures/mlp/model.py", "fixtures/residual_cnn/model.py", "fixtures/residual_cnn/blocks.py",
    )]
    before = {str(path): {"bytes": (PROJECT / path).stat().st_size, "sha256": sha(PROJECT / path)} for path in paths}
    historical_before = {name: sha(PROJECT / name) for name in HISTORICAL_REPORTS}
    for path in paths:
        source, target = PROJECT / path, release / path
        if source.is_symlink():
            raise RuntimeError("Formal source symlink is not allowed: " + str(source))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (temporary / "runner.py").write_text(RUNNER, encoding="utf-8")
    (temporary / "input-manifest.json").write_text(json.dumps(records(release), indent=2) + "\n", encoding="utf-8")
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX", "NODE_PATH"):
        environment.pop(key, None)
    environment["PATH"] = os.pathsep.join(part for part in environment.get("PATH", "").split(os.pathsep) if part and "ArchCanvas" not in part)
    environment["PYTHONNOUSERSITE"] = "1"
    command = [str(PROJECT / ".venv/bin/python"), "-I", "-S", "-B", str(temporary / "runner.py")]
    command_receipt = {"command": command, "cwd": str(temporary), "environmentPolicy": "Remove PYTHONPATH/PYTHONHOME/VIRTUAL_ENV/CONDA_PREFIX/NODE_PATH; filter ArchCanvas entries from PATH; explicit -I -S -B interpreter"}
    (temporary / "command.json").write_text(json.dumps(command_receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    process = subprocess.run(command, cwd=temporary, env=environment, capture_output=True, check=False, timeout=120)
    (temporary / "suite.stdout.txt").write_bytes(process.stdout)
    (temporary / "suite.stderr.txt").write_bytes(process.stderr)
    after = {str(path): {"bytes": (PROJECT / path).stat().st_size, "sha256": sha(PROJECT / path)} for path in paths}
    historical_after = {name: sha(PROJECT / name) for name in HISTORICAL_REPORTS}
    copied_stable = before == {item["path"]: {"bytes": item["bytes"], "sha256": item["sha256"]} for item in records(release)}
    oracle_report = json.loads((temporary / "artifacts/static-oracle-report.json").read_text(encoding="utf-8")) if (temporary / "artifacts/static-oracle-report.json").exists() else None
    passed = process.returncode == 0 and before == after and historical_before == historical_after and copied_stable and oracle_report and oracle_report["passed"]
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(temporary, output / "run")
    retained = records(output / "run")
    assert retained == records(temporary)
    report = {"schemaVersion": 1, "startedAt": started, "finishedAt": datetime.now(timezone.utc).isoformat(),
              "status": "passed-bounded-static-base-model-audit" if passed else "failed", "passed": bool(passed),
              "formalProject": str(PROJECT), "temporaryRun": str(temporary), "standaloneCopy": str(release),
              "retainedCompleteRun": "run", "retainedRunExactByteCopy": True, "command": command_receipt, "exitCode": process.returncode,
              "suite": oracle_report["independentSuite"] if oracle_report else None,
              "models": oracle_report["models"] if oracle_report else [],
              "sourceInputCount": len(before), "formalInputsBefore": before, "formalInputsAfter": after,
              "formalInputsStable": before == after, "copiedInputsStable": copied_stable,
              "historicalReportsBefore": historical_before, "historicalReportsAfter": historical_after,
              "historicalReportsUnchanged": historical_before == historical_after,
              "tempIsolation": {"pythonIsolation": oracle_report["pythonIsolation"] if oracle_report else None,
                                "packageOrigins": oracle_report["packageOrigins"] if oracle_report else None,
                                "fixtureImport": False, "modelExecution": False,
                                "failedPrototypeFallback": False, "onlyCopiedFormalProjectPathsAdded": True},
              "retainedManifest": retained, "auditScriptSha256": sha(Path(__file__).resolve()),
              "limitations": oracle_report["limitations"] if oracle_report else ["Run failed; no certification"]}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not passed:
        raise RuntimeError("Base-model current audit failed; retained complete run for inspection")
    print(json.dumps({"status": report["status"], "tests": "11/11", "report": str(output / "report.json")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    run(parser.parse_args().output.resolve())
