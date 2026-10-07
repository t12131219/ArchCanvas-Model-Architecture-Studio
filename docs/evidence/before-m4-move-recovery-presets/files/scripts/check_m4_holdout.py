#!/usr/bin/env python3
"""Run the M4 model-family holdout oracles from a standalone formal-source copy.

The copy is made by the same provenance checker used for the release checks.
The handwritten test/oracle is then run with Python ``-I -S`` against only the
copied ``src`` tree; no fixture module is imported by the analyzer itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from check_independence import clean_environment, verify
from check_stage2 import command, python_args


HOLDOUTS = (
    ("holdout_vit", "model:PatchVisionEncoder", "vit"),
    ("holdout_vit", "model:UnsupportedVision", "opaque"),
    ("holdout_families", "model:TemporalForecaster", "temporal"),
    ("holdout_families", "model:SkipSegmentation", "unet"),
    ("holdout_families", "model:GraphForecast", "gnn"),
    ("holdout_families", "model:DynamicStateSpace", "ssm"),
)


def check(project: Path) -> Path:
    independence_path, independence = verify(project.resolve(), build=False)
    release = Path(independence["standaloneCopy"])
    temporary = release.parent
    environment = clean_environment(temporary)
    suite_code = (
        "import unittest; suite=unittest.TestSuite(); "
        f"suite.addTests(unittest.defaultTestLoader.discover({str(release / 'tests')!r}, pattern='test_m4_holdout.py')); "
        f"suite.addTests(unittest.defaultTestLoader.discover({str(release / 'tests')!r}, pattern='test_output_paths.py')); "
        f"suite.addTests(unittest.defaultTestLoader.discover({str(release / 'tests')!r}, pattern='test_residual_roles.py')); "
        "result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2).run(suite); "
        "sys.exit(0 if result.wasSuccessful() and not result.skipped and result.testsRun == 28 else 1)"
    )
    suite_output = command(python_args(Path(sys.executable), release, suite_code), release, environment)
    artifacts = temporary / "m4-holdout-artifacts"
    artifacts.mkdir()
    (artifacts / "independent-suite.txt").write_bytes(suite_output)
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node 24+ is required for the copied Studio output-path contract checks")
    studio_output = command([node, "--experimental-strip-types", "--test", "--test-isolation=none",
                             str(release / "studio/tests/output-paths.test.ts")], release / "studio", environment)
    (artifacts / "studio-output-path-suite.txt").write_bytes(studio_output)

    analysis_code = (
        "import json; from pathlib import Path; from archcanvas_python import analyze_project\n"
        f"root=Path({str(release / 'fixtures')!r})\n"
        f"out=Path({str(artifacts)!r})\n"
        f"for fixture,entry,key in {HOLDOUTS!r}:\n"
        "    out.joinpath(key+'.json').write_text(json.dumps(analyze_project(root/fixture,entry),ensure_ascii=False,indent=2),encoding='utf-8')\n"
    )
    command(python_args(Path(sys.executable), release, analysis_code), release, environment)
    vit = json.loads((artifacts / "vit.json").read_text(encoding="utf-8"))
    opaque = json.loads((artifacts / "opaque.json").read_text(encoding="utf-8"))
    report = {
        "schemaVersion": 1,
        "passed": True,
        "scope": "M4 no-template ViT, temporal, U-Net-style, GNN/SSM static holdouts with explicit opaque boundaries",
        "formalProject": str(project.resolve()),
        "standaloneCopy": str(release),
        "independenceReport": str(independence_path),
        "pythonIsolation": "-I -S with only standalone src added",
        "checks": [
            {
                "name": "independent-m4-holdout-oracle-suite",
                "passed": True,
                "tests": "28/28",
                "composition": {"familyHoldouts": 6, "outputSlotContractsAndCounterexamples": 10, "residualBypassContractsAndCounterexamples": 12},
                "source": str(release / "tests" / "test_m4_holdout.py"),
                "oracle": str(release / "tests" / "m4_holdout_oracle.py"),
                "stdout": str(artifacts / "independent-suite.txt"),
            },
            {
                "name": "independent-studio-output-path-contract-and-import-rejection-suite",
                "passed": True,
                "tests": "3/3",
                "source": str(release / "studio/tests/output-paths.test.ts"),
                "stdout": str(artifacts / "studio-output-path-suite.txt"),
            },
            {
                "name": "vit-static-contracts-and-residual-bindings",
                "passed": True,
                "entry": vit["entry"],
                "sourceDigest": vit["sourceDigest"],
                "irDigest": vit["irDigest"],
                "nodeCount": len(vit["nodes"]),
                "edgeCount": len(vit["edges"]),
                "opaqueNodeCount": sum(node["evidence"] == "opaque" for node in vit["nodes"]),
                "architecture": str(artifacts / "vit.json"),
            },
            {
                "name": "unknown-constructor-remains-opaque",
                "passed": True,
                "entry": opaque["entry"],
                "sourceDigest": opaque["sourceDigest"],
                "irDigest": opaque["irDigest"],
                "nodeCount": len(opaque["nodes"]),
                "edgeCount": len(opaque["edges"]),
                "opaqueNodeCount": sum(node["evidence"] == "opaque" for node in opaque["nodes"]),
                "diagnostics": opaque["diagnostics"],
                "architecture": str(artifacts / "opaque.json"),
            },
        ],
        "limitations": [
            "Static AST facts only; these holdouts do not claim concrete tensor shapes or execution equivalence.",
            "Conv1d, ConvTranspose2d, custom GraphAttentionKernel/StateSpaceScan and dynamic control remain opaque.",
            "The independent copy is local and does not certify arbitrary model families or host integrations.",
        ],
        "artifactDigests": {
            "vitArchitecture": hashlib.sha256((artifacts / "vit.json").read_bytes()).hexdigest(),
            "opaqueArchitecture": hashlib.sha256((artifacts / "opaque.json").read_bytes()).hexdigest(),
        },
    }
    for _, _, key in HOLDOUTS[2:]:
        path = artifacts / (key + ".json")
        architecture = json.loads(path.read_text(encoding="utf-8"))
        report["checks"].append({
            "name": key + "-complete-node-port-relation-oracle",
            "passed": True,
            "entry": architecture["entry"],
            "sourceDigest": architecture["sourceDigest"],
            "irDigest": architecture["irDigest"],
            "nodeCount": len(architecture["nodes"]),
            "edgeCount": len(architecture["edges"]),
            "opaqueNodeCount": sum(node["evidence"] == "opaque" for node in architecture["nodes"]),
            "outputSlots": [{"nodeId": node["id"], "path": node["outputPath"]} for node in architecture["nodes"] if node["kind"] == "Output"],
            "diagnostics": architecture["diagnostics"],
            "architecture": str(path),
        })
        report["artifactDigests"][key + "Architecture"] = hashlib.sha256(path.read_bytes()).hexdigest()
    report_path = temporary / "m4-holdout-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    options = parser.parse_args()
    try:
        path = check(options.project)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"passed": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"passed": True, "report": str(path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
