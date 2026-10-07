"""Freeze this helper and syntax-only checks before native browser trials."""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NODE = Path("/home/fzg/.nvm/versions/node/v24.19.0/bin/node")
FILES = [HERE / name for name in [
    "measurement-contract.json", "README.md", "serve.py", "control.html", "studio.html",
    "controller.css", "controller.mjs", "observer.mjs", "capture_baseline.py",
]]
REFERENCES = [ROOT / name for name in [
    "docs/evidence/m4-collapsed-residual-work/performance-plan/analysis.json",
    "docs/evidence/m4-collapsed-residual-work/performance-plan/event-window-supplement.json",
    "scripts/m4_input_observer.mjs",
]]


def binding(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main() -> None:
    destination = HERE / "helper-baseline-attempt-1"
    destination.mkdir(exist_ok=False)
    before = [binding(path) for path in FILES + REFERENCES]
    for path in FILES + REFERENCES:
        target = destination / "files" / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(path.read_bytes())
    commands = []
    for filename in ["observer.mjs", "controller.mjs"]:
        argv = [str(NODE), "--check", str(HERE / filename)]
        start = datetime.now(timezone.utc).isoformat()
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)
        commands.append({"argv": argv, "cwd": str(ROOT), "startedUtc": start,
                         "endedUtc": datetime.now(timezone.utc).isoformat(),
                         "exitCode": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
    ast.parse((HERE / "serve.py").read_text(), filename=str(HERE / "serve.py"))
    json.loads((HERE / "measurement-contract.json").read_text())
    after = [binding(path) for path in FILES + REFERENCES]
    node_raw = NODE.read_bytes()
    receipt = {
        "protocol": "archcanvas-performance-controls-helper-baseline/1",
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "Independent measurement helper frozen before any browser/control/service attempt; syntax-only checks do not establish browser or performance correctness.",
        "helperFiles": len(FILES), "readonlyReferenceFiles": len(REFERENCES),
        "inputBindingsBefore": before, "inputBindingsAfter": after, "inputBindingsUnchanged": before == after,
        "archiveCopiesExact": all(binding(path)["sha256"] == hashlib.sha256((destination / "files" / path.relative_to(ROOT)).read_bytes()).hexdigest() for path in FILES + REFERENCES),
        "commands": commands,
        "node": {"argument": str(NODE), "resolved": str(NODE.resolve()), "bytes": len(node_raw), "sha256": hashlib.sha256(node_raw).hexdigest()},
        "pythonAstParse": True, "contractJsonParse": True,
        "serviceLaunched": False, "browserOperated": False, "modelExecuted": False,
        "testsRun": False, "productBuildRun": False, "performanceCertified": False,
    }
    with (destination / "manifest.json").open("x") as output:
        json.dump(receipt, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(json.dumps({"path": str((destination / "manifest.json").relative_to(ROOT)),
                      "binding": binding(destination / "manifest.json"),
                      "inputsUnchanged": before == after, "syntaxExitCodes": [command["exitCode"] for command in commands]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
