#!/usr/bin/env python3
"""Verify complete six-entry holdout inventories from a standalone formal copy.

This supplementary static receipt preserves earlier holdout reports/checkers.
No fixture is imported or executed; the copied formal analyzer consumes source
as AST data under Python -I -S. Artifacts remain in the standalone /tmp run.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
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
    artifacts = temporary / "m4-holdout-integrity-artifacts"
    artifacts.mkdir()
    suite_code = (
        "import unittest; "
        f"suite=unittest.defaultTestLoader.discover({str(release / 'tests')!r}, pattern='test_m4_holdout_integrity.py'); "
        "result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2).run(suite); "
        "sys.exit(0 if result.wasSuccessful() and not result.skipped and result.testsRun == 22 else 1)"
    )
    suite_output = command(python_args(Path(sys.executable), release, suite_code), release, environment)
    (artifacts / "independent-suite.txt").write_bytes(suite_output)
    proof_code = (
        "import json; from pathlib import Path; "
        f"sys.path.insert(0,{str(release / 'tests')!r}); "
        "from archcanvas_python import analyze_project; "
        "from m4_holdout_integrity_oracle import HOLDOUTS; "
        "from test_m4_holdout_integrity import check_holdout\n"
        f"root=Path({str(release / 'fixtures')!r}); out=Path({str(artifacts)!r})\n"
        "for name, expected in HOLDOUTS.items():\n"
        "    fixture=root/expected['fixture']\n"
        "    architecture=analyze_project(fixture,expected['entry'])\n"
        "    proof=check_holdout(architecture,name,fixture)\n"
        "    out.joinpath(name+'.architecture.json').write_text(json.dumps(architecture,ensure_ascii=False,indent=2)+'\\n',encoding='utf-8')\n"
        "    out.joinpath(name+'.oracle-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\\n',encoding='utf-8')\n"
    )
    command(python_args(Path(sys.executable), release, proof_code), release, environment)
    report = {
        "schemaVersion": 1,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "scope": "Supplementary complete static node/declared-port/tensor/containment oracle for all six formal M4 holdout entries",
        "formalProject": str(project), "standaloneCopy": str(release),
        "independenceReport": str(independence_path), "artifactsRoot": str(artifacts),
        "pythonIsolation": "-I -S with only standalone src and copied oracle tests added",
        "modelExecution": False, "fixtureImport": False,
        "oracleOrigin": "Hand-authored from formal fixture source and public atomic contracts before comparing actual analyzer output; earlier handwritten relationships reused, no analyzer snapshot supplies expectations.",
        "bindingLookup": "Exact (nodeId,portId); complete declared name/direction/role/ordinal; relation Counter and producer-to-tensor bijection.",
        "independentSuite": {"passed": True, "tests": "22/22", "skipped": 0,
                             "composition": {"completeEntries": 6, "deliberateCorruptionTests": 16},
                             "stdout": str(artifacts / "independent-suite.txt")},
        "counterexamples": ["foreign same-named port", "split shared tensor", "merged LSTM output slots",
                            "extra unbound port", "changed port role/ordinal", "duplicate relation",
                            "duplicate containment member", "wrong parent", "swapped repeat members",
                            "false repeat sharing", "merged shared-instance call identity",
                            "unknown given registered semantics", "invented opaque internal child",
                            "changed opaque constructor argument", "missing unknown diagnostic",
                            "wrong source SHA/call expression"],
        "models": [],
        "artifactDigests": {
            "handwrittenOracle": sha256(release / "tests/m4_holdout_integrity_oracle.py"),
            "originalHandwrittenRelations": sha256(release / "tests/m4_holdout_oracle.py"),
            "checkerAndCounterexamples": sha256(release / "tests/test_m4_holdout_integrity.py"),
            "distributionChecker": sha256(release / "scripts/check_m4_holdout_integrity.py"),
            "standaloneDistributionChecker": sha256(release / "scripts/check_independence.py"),
            "frontend": sha256(release / "src/archcanvas_python/frontend.py"),
            "independentSuite": sha256(artifacts / "independent-suite.txt"),
            "independenceReport": sha256(independence_path),
        },
        "limitations": [
            "Exactly these six declared AST fixture entries; no arbitrary family, shape, dtype, numeric equivalence, forward/backward execution or host certification.",
            "Atomic API declarations may include an unused output port (MHA weights); tensor inventory counts actual bound producers, never invents a tensor for need_weights=False.",
            "Opaque nodes preserve visible source dependencies and authored constructor literals without endorsing unknown operator/kernel semantics or inner control flow.",
            "Sibling custom-root containment is checked as a multiset; ordered Repeat/Sequential members are additionally checked in source execution order.",
            "Source bytes/ranges/call expressions are verified, but every parameter origin is not independently certified.",
            "This receipt does not certify current browser publication, presented performance, active native cancellation or real researcher tasks.",
        ],
    }
    for architecture_path in sorted(artifacts.glob("*.architecture.json")):
        name = architecture_path.name.removesuffix(".architecture.json")
        proof_path = artifacts / (name + ".oracle-proof.json")
        architecture = json.loads(architecture_path.read_text(encoding="utf-8"))
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        report["models"].append({
            "name": name, "passed": True, "entry": architecture["entry"],
            "sourceDigest": architecture["sourceDigest"], "irDigest": architecture["irDigest"],
            **{key: proof[key] for key in ("nodeCount", "edgeCount", "portCount", "tensorCount", "callCount", "instanceCount", "opaqueNodeCount")},
            "sourceFiles": [{"path": source["path"], "sha256": source["digest"]} for source in architecture["sources"]],
            "architecture": str(architecture_path), "oracleProof": str(proof_path),
        })
        report["artifactDigests"][name + "Architecture"] = sha256(architecture_path)
        report["artifactDigests"][name + "OracleProof"] = sha256(proof_path)
    report_path = temporary / "m4-holdout-integrity-report.json"
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
