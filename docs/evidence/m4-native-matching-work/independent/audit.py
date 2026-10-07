#!/usr/bin/env python3
"""Run only the independently authored strict native-matching examples.

The script snapshots the exact current inputs before and after a focused Node
run. It does not control a browser, execute a model, mutate product source or
certify paint. Use a new output directory for another run.
"""

from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


PROJECT = Path(__file__).resolve().parents[4]
INPUTS = (
    "studio/src/nativePerformance.ts",
    "studio/src/perf.ts",
    "scripts/validate_native_performance.mjs",
    "studio/tests/native-matching-independent.test.ts",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    for name in ("report.json", "suite.stdout.txt", "suite.stderr.txt"):
        if (output / name).exists():
            raise RuntimeError("Use a fresh output directory; refusing to overwrite " + name)
    started = datetime.now(timezone.utc).isoformat()
    before = {name: {"sha256": digest(PROJECT / name), "bytes": (PROJECT / name).stat().st_size} for name in INPUTS}
    for name in INPUTS:
        destination = output / "bound-source" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT / name, destination)
    node = shutil.which("node")
    command = [node, "--experimental-strip-types", "--test", "--test-isolation=none", "tests/native-matching-independent.test.ts"]
    process = subprocess.run(command, cwd=PROJECT / "studio", capture_output=True, text=False, check=False)
    (output / "suite.stdout.txt").write_bytes(process.stdout)
    (output / "suite.stderr.txt").write_bytes(process.stderr)
    after = {name: {"sha256": digest(PROJECT / name), "bytes": (PROJECT / name).stat().st_size} for name in INPUTS}
    stdout = process.stdout.decode("utf-8")
    passed = process.returncode == 0 and before == after and "tests 9" in stdout and "pass 9" in stdout and "fail 0" in stdout and "skipped 0" in stdout
    report = {
        "schemaVersion": 1,
        "startedAt": started,
        "finishedAt": datetime.now(timezone.utc).isoformat(),
        "status": "passed-bounded-matching-contract" if passed else "failed",
        "scope": "Nine authored strict bilateral-uniqueness native Event Timing match/counterexample tests; no browser measurement",
        "formalProject": str(PROJECT),
        "command": command,
        "cwd": str(PROJECT / "studio"),
        "exitCode": process.returncode,
        "suite": {"tests": 9, "passed": 9 if passed else None, "skipped": 0 if passed else None, "stdout": "suite.stdout.txt", "stderr": "suite.stderr.txt"},
        "assertedContract": "A trial and raw Event Timing entry match only when both have exactly one eligible counterpart in the complete original candidate relation. No iterative assignment or candidate removal resolves ambiguity.",
        "authoredExamples": [
            "Two trusted same-target trials competing for one raw entry both null; reversed trial array remains null; forged first-come receipt rejected.",
            "Two-by-two full overlap all null under both trial and event orders.",
            "A={e1}, B={e1,e2} partial overlap all null; raw graph cannot be simplified greedily; forged two-match receipt rejected.",
            "Exact -8 and +8 ms endpoints included, points 0.000001 ms beyond excluded; a shared boundary entry remains null.",
            "Different target identity isolates simultaneous unique pairs; null/wrong target excluded.",
            "Different click/pointerdown identity isolates simultaneous unique pairs.",
            "Untrusted competing trial does not consume or make a trusted pair ambiguous.",
            "An ambiguous target component does not erase a separate unique component.",
            "Duplicate raw entries remain distinct candidates and do not fabricate uniqueness; forged duplicate receipt rejected.",
        ],
        "expectedReceiptOrigin": "Hand-authored pairs/nulls and literal p95 expected values; expected receipts never call product join or summary functions.",
        "inputsBefore": before,
        "inputsAfter": after,
        "sourceStableAcrossRun": before == after,
        "sourceSnapshots": {name: str(Path("bound-source") / name) for name in INPUTS},
        "artifactDigests": {
            "suite.stdout.txt": digest(output / "suite.stdout.txt"),
            "suite.stderr.txt": digest(output / "suite.stderr.txt"),
            "audit.py": digest(Path(__file__).resolve()),
        },
        "limitations": [
            "This is source/contract evidence, not an actual native browser event or paint measurement.",
            "No fixture/model was imported or executed; no browser UI, performance trial or human participant was involved.",
            "Only the stated matching eligibility and bilateral uniqueness examples are tested; other receipt parsing, hardware/font/environment locks and continuous presentation are not certified.",
            "The validator retains chronological raw-trial ordering. Reversed unequal-time trials test product matching only; event order and equal-time trial permutations are separately tested without weakening chronology.",
            "Strict TypeScript and production build are left to the root's unified check; this report does not claim build success.",
        ],
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not passed:
        raise RuntimeError("Focused native matching audit failed; inspect report and raw suite output")
    print(json.dumps({"status": report["status"], "report": str(output / "report.json")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    run(parser.parse_args().output.resolve())
