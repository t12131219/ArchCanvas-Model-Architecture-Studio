from datetime import datetime, timezone
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
        architecture_file.write_text(json.dumps(architecture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        proof_file.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
(artifacts / "static-oracle-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
sys.exit(0 if passed else 1)
