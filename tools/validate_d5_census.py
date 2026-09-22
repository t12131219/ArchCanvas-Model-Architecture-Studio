"""Validate a saved D5 PyTorch census and optional external Publication evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from archcanvas_engine.d5_validation import D5CensusValidator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("census", type=Path)
    parser.add_argument("--publication-artifact-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--require-stage6-exit-ready",
        action="store_true",
        help="return nonzero until machine evidence and every manual checklist are complete",
    )
    arguments = parser.parse_args(argv)

    payload = json.loads(arguments.census.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("census must be a JSON object")
    report = D5CensusValidator().validate(
        payload,
        publication_artifact_root=arguments.publication_artifact_root,
    )
    encoded = json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if arguments.output is not None:
        arguments.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    passed = report.stage6_exit_ready if arguments.require_stage6_exit_ready else report.machine_passed
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
