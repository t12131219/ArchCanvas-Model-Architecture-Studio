"""Run one fresh, preserved preset audit attempt with exact command receipts."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

here = Path(__file__).resolve().parent
root = here.parents[3]
target = Path(sys.argv[1]).resolve()
target.mkdir(parents=True, exist_ok=False)
audit_env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(root / "src")}
python = str(root / ".venv/bin/python")
node = shutil.which("node")
assert node is not None
commands = [
    [python, str(here / "catalog-producer.py"), str(target / "catalog.json")],
    [node, "--experimental-strip-types", str(here / "sample-frontends.mjs"), str(target / "catalog.json"), str(target / "frontend-drafts.json")],
    [python, str(here / "audit.py"), "--input", str(target / "frontend-drafts.json"), "--output", str(target / "backend-ast-audit")],
]
receipts = []
for index, command in enumerate(commands):
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=root, env=audit_env, capture_output=True, text=True, timeout=60, check=False)
    with (target / f"stage-{index + 1}-output.txt").open("x", encoding="utf-8") as handle:
        handle.write(result.stdout)
        if result.stderr:
            handle.write("\nSTDERR:\n" + result.stderr)
    receipts.append({"command": command, "cwd": str(root), "environmentOverrides": {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(root / "src")}, "startedUtc": started, "finishedUtc": datetime.now(timezone.utc).isoformat(), "exitCode": result.returncode, "outputLog": f"stage-{index + 1}-output.txt"})
    if result.returncode != 0:
        with (target / "FAILED-command-receipts.json").open("x", encoding="utf-8") as handle:
            json.dump(receipts, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(json.dumps({"status": "failed", "stage": index + 1, "output": str(target)}))
        sys.exit(result.returncode)
with (target / "command-receipts.json").open("x", encoding="utf-8") as handle:
    json.dump(receipts, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
print(json.dumps({"status": "passed", "stages": len(receipts), "output": str(target)}))
