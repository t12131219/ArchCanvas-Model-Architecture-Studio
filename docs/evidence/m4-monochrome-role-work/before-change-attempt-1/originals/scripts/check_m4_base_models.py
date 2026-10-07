#!/usr/bin/env python3
"""Verify full handwritten MLP/CNN facts from an independent formal-source copy.

This is a static source oracle, not an execution, browser-performance or human
research acceptance receipt. Original fixtures and prior holdout reports stay
untouched; generated artifacts live under the checked standalone /tmp copy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from check_independence import clean_environment, verify
from check_stage2 import command, python_args


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(project: Path) -> Path:
    project = project.resolve()
    independence_path, independence = verify(project, build=False)
    release = Path(independence["standaloneCopy"])
    temporary = release.parent
    environment = clean_environment(temporary)
    artifacts = temporary / "m4-base-model-artifacts"
    artifacts.mkdir()
    suite_code = (
        "import unittest; "
        f"suite=unittest.defaultTestLoader.discover({str(release / 'tests')!r}, pattern='test_m4_base_models.py'); "
        "result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2).run(suite); "
        "sys.exit(0 if result.wasSuccessful() and not result.skipped and result.testsRun == 11 else 1)"
    )
    suite_output = command(python_args(Path(sys.executable), release, suite_code), release, environment)
    (artifacts / "independent-suite.txt").write_bytes(suite_output)
    proof_code = (
        "import json; from pathlib import Path; "
        f"sys.path.insert(0,{str(release / 'tests')!r}); "
        "from archcanvas_python import analyze_project; "
        "from m4_base_model_oracle import BASE_MODELS; "
        "from test_m4_base_models import check_base_model\n"
        f"root=Path({str(release / 'fixtures')!r}); out=Path({str(artifacts)!r})\n"
        "for name, expected in BASE_MODELS.items():\n"
        "    fixture=root/expected['fixture']\n"
        "    architecture=analyze_project(fixture,expected['entry'])\n"
        "    proof=check_base_model(architecture,name,fixture)\n"
        "    out.joinpath(name+'.architecture.json').write_text(json.dumps(architecture,ensure_ascii=False,indent=2)+'\\n',encoding='utf-8')\n"
        "    out.joinpath(name+'.oracle-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\\n',encoding='utf-8')\n"
    )
    command(python_args(Path(sys.executable), release, proof_code), release, environment)
    report = {
        "schemaVersion": 1, "passed": True,
        "scope": "M4 complete source-authored MLP/ResidualCNN node-port-tensor-containment-repeat oracles",
        "formalProject": str(project), "standaloneCopy": str(release),
        "independenceReport": str(independence_path),
        "pythonIsolation": "-I -S with only standalone src and copied oracle tests added",
        "independentSuite": {"passed": True, "tests": "11/11", "skipped": 0,
                             "composition": {"completeBaseModels": 2, "deliberateCorruptions": 9},
                             "stdout": str(artifacts / "independent-suite.txt")},
        "oracleOrigin": "Manually authored from the two formal fixtures and registered public call contracts; no analyzer output snapshot supplies expected facts.",
        "bindingLookup": "Exact (nodeId,portId) pair, with declared direction/name/role/ordinal and a producer-to-tensor bijection.",
        "counterexamples": ["wrong Add target port", "valid port with wrong producer",
                            "foreign same-named port", "split adapter tensor", "merged tensor producers",
                            "extra unbound port", "wrong containment", "false independent activation instance",
                            "false repeat count"],
        "models": [],
        "artifactDigests": {
            "handwrittenOracle": sha256(release / "tests/m4_base_model_oracle.py"),
            "checkerAndCounterexamples": sha256(release / "tests/test_m4_base_models.py"),
            "distributionChecker": sha256(release / "scripts/check_m4_base_models.py"),
            "frontend": sha256(release / "src/archcanvas_python/frontend.py"),
            "independentSuite": sha256(artifacts / "independent-suite.txt"),
        },
        "limitations": [
            "Static source facts only; no model import/execution, concrete tensor shape, backward pass or numerical equivalence is claimed.",
            "This local standalone-copy receipt does not certify browser interaction/performance, visual research acceptance or arbitrary model families.",
            "The full source ranges and authored expressions are checked; every parameter origin is not independently certified by this receipt.",
        ],
    }
    for name, fixture in (("MLP", "mlp"), ("ResidualCNN", "residual_cnn")):
        architecture_path, proof_path = artifacts / (name + ".architecture.json"), artifacts / (name + ".oracle-proof.json")
        architecture = json.loads(architecture_path.read_text(encoding="utf-8"))
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        report["models"].append({
            "name": name, "passed": True, "entry": architecture["entry"],
            "sourceDigest": architecture["sourceDigest"], "irDigest": architecture["irDigest"],
            "nodeCount": proof["nodeCount"], "edgeCount": proof["edgeCount"],
            "portCount": proof["portCount"], "tensorCount": proof["tensorCount"],
            "callCount": proof["callCount"], "instanceCount": proof["instanceCount"],
            "opaqueNodeCount": sum(node["evidence"] == "opaque" for node in architecture["nodes"]),
            "sourceFiles": [{"path": source["path"], "sha256": sha256(release / "fixtures" / fixture / source["path"])}
                            for source in architecture["sources"]],
            "architecture": str(architecture_path), "oracleProof": str(proof_path),
        })
        report["artifactDigests"][name + "Architecture"] = sha256(architecture_path)
        report["artifactDigests"][name + "OracleProof"] = sha256(proof_path)
    report_path = temporary / "m4-base-model-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    options = parser.parse_args()
    try:
        report = check(options.project)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"passed": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"passed": True, "report": str(report)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
