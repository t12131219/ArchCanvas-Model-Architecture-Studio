#!/usr/bin/env python3
"""Package completed root snapshots only; never snapshot/read a live store."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
HELPER = WORK / "capture_workflow.py"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def completed(case: str) -> bool:
    return (WORK / "cases" / case / "screen-receipt-stamped.json").is_file()


def process(case: str) -> dict:
    observation = WORK / "bound-observations" / case
    commands = []
    if not (WORK / "cases" / case).exists():
        commands.append(("package", [str(ROOT / ".venv/bin/python"), str(HELPER), "package",
                        "--raw", str(observation / "dom-observation.json"),
                        "--saved-envelope", str(observation / "actual-document-store.json"),
                        "--browser-scene", str(WORK / "raw" / case / "browser-scene.svg"),
                        "--screenshot", str(WORK / "raw" / case / "screenshot.jpg")]))
    if not completed(case):
        commands.append(("stamp", [str(ROOT / ".venv/bin/python"), str(HELPER), "stamp", "--case", case]))
    journal = WORK / "processing" / case
    journal.mkdir(parents=True, exist_ok=True)
    if (journal / "execution.json").exists():
        raise ValueError("Previous processing receipt exists; preserve it and investigate before retry.")
    receipts = []
    for action, command in commands:
        started = now()
        result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = journal / (action + ".txt")
        with log.open("x") as stream:
            stream.write(result.stdout)
        receipts.append({"action": action, "command": command, "startedAt": started, "endedAt": now(),
                         "exitCode": result.returncode, "log": str(log.relative_to(ROOT)), "sha256": digest(log)})
        if result.returncode:
            break
    record = {"schemaVersion": 1, "caseId": case, "commands": receipts,
              "allRequestedActionsPassed": all(item["exitCode"] == 0 for item in receipts),
              "snapshotExecuted": False, "browserOperationExecuted": False,
              "humanAcceptanceCertified": False, "completed": completed(case)}
    with (journal / "execution.json").open("x") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    if not record["allRequestedActionsPassed"]:
        raise ValueError(f"Processing failed for {case}; retained {journal} logs. No fallback or retry.")
    helper = json.loads((WORK / "cases" / case / "case-helper.json").read_bytes())
    return {"caseId": case, "exactExportArtifactId": helper["exactExportArtifactId"],
            "state": helper["state"], "variantId": helper["variantId"], "packagedAndStamped": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch-seconds", type=float, default=0,
                        help="Bounded local-file observation window, at most45seconds; default once.")
    args = parser.parse_args()
    if not 0 <= args.watch_seconds <= 45:
        parser.error("watch-seconds must be0–45.")
    deadline = time.monotonic() + args.watch_seconds
    handled = []
    try:
        while True:
            for path in sorted((WORK / "bound-observations").glob("*/snapshot-receipt.json")):
                case = path.parent.name
                if not completed(case):
                    record = process(case)
                    handled.append(record)
                    print(json.dumps(record, ensure_ascii=False), flush=True)
            if time.monotonic() >= deadline:
                break
            time.sleep(min(5, max(0, deadline - time.monotonic())))
        total = len(list((WORK / "cases").glob("*/screen-receipt-stamped.json")))
        print(json.dumps({"handledThisRun": len(handled), "totalPackagedAndStamped": total,
                          "snapshotExecuted": False, "browserOperationExecuted": False}), flush=True)
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
