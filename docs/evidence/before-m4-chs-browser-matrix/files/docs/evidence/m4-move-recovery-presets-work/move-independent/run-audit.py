"""Record focused independent tests and strict compilation without a build."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
OUTPUT = Path(__file__).resolve().parent / sys.argv[1]
OUTPUT.mkdir(exist_ok=False)
INPUTS = [
    "studio/tests/move-recovery-independent.test.ts", "studio/src/core/layoutRecovery.ts",
    "studio/src/core/scene.ts", "studio/src/core/document.ts", "studio/src/core/movePreview.ts",
    "studio/src/core/orthogonalRouter.ts", "studio/src/core/tokens.ts", "studio/src/core/types.ts",
    "studio/src/core/index.ts", "studio/src/layoutWarnings.ts", "studio/src/App.tsx",
    "studio/tsconfig.json", "studio/package.json",
]


def binding(path):
    data = (ROOT / path).read_bytes()
    return {"path": path, "sizeBytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


before = [binding(path) for path in INPUTS]
for entry in before:
    path = OUTPUT / "source-snapshot" / entry["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / entry["path"], path)
node = shutil.which("node")
commands = [
    [node, "--experimental-strip-types", "--test", "--test-isolation=none", "tests/move-recovery-independent.test.ts"],
    [str(ROOT / "studio/node_modules/.bin/tsc"), "--noEmit"],
]
receipts = []
for index, command in enumerate(commands, 1):
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=ROOT / "studio", text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    ended = datetime.now(timezone.utc).isoformat()
    log = f"command-{index}.log"
    (OUTPUT / log).write_text(result.stdout)
    receipts.append({"argv": command, "cwd": str(ROOT / "studio"), "startedAt": started, "endedAt": ended,
                     "exitCode": result.returncode, "combinedOutputPath": log})
after = [binding(path) for path in INPUTS]
receipt = {"actor": "AI subagent /root/move_contract_review", "scope": "focused unit tests and strict compilation; no build/browser/human acceptance",
           "nodeVersion": subprocess.check_output([node, "--version"], text=True).strip(),
           "commands": receipts, "inputsBefore": before, "inputsAfter": after, "inputsStable": before == after}
(OUTPUT / "command-receipts.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
for item in receipts:
    print(json.dumps(item, ensure_ascii=False))
print("inputsStable=" + str(before == after))
sys.exit(0 if before == after and all(item["exitCode"] == 0 for item in receipts) else 1)
