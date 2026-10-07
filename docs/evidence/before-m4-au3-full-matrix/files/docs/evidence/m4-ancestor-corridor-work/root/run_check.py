"""Run one declared check, preserving stdout, stderr and exact source bindings."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[4]
label, *argv = sys.argv[1:]
assert label and argv
output = Path(__file__).parent / label
output.mkdir(exist_ok=False)

def now():
    return datetime.now(timezone.utc).isoformat()

def binding(path):
    data = path.read_bytes()
    return {"path": str(path.relative_to(root)), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

paths = sorted(set(path for folder in [root / "studio/src", root / "studio/tests"]
    for path in folder.rglob("*") if path.is_file()) | set(root / "studio" / name
    for name in ["package.json", "package-lock.json", "tsconfig.json", "vite.config.ts"] if (root / "studio" / name).is_file()))
before = [binding(path) for path in paths]
started = now()
with (output / "stdout.log").open("xb") as stdout, (output / "stderr.log").open("xb") as stderr:
    result = subprocess.run(argv, cwd=root, stdout=stdout, stderr=stderr, check=False)
after = [binding(path) for path in paths]
receipt = {"schemaVersion": 1, "argv": argv, "cwd": str(root), "startedAt": started, "finishedAt": now(),
    "exitCode": result.returncode, "sourceBeforeAfterExact": before == after, "bindings": before,
    "after": after, "logs": [binding(output / name) for name in ["stdout.log", "stderr.log"]]}
with (output / "receipt.json").open("x") as stream:
    json.dump(receipt, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print(json.dumps({"exitCode": result.returncode, "sourceBeforeAfterExact": before == after,
    "receipt": str((output / "receipt.json").relative_to(root))}))
raise SystemExit(result.returncode)
