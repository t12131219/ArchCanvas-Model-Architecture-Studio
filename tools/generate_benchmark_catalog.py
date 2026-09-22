"""Generate a read-only L0 catalog for an approved Benchmark Model Reference root."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from archcanvas_engine.benchmark_catalog import BenchmarkCatalogBuilder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark_root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)

    root = arguments.benchmark_root.resolve(strict=True)
    output = arguments.output.resolve()
    if output.is_relative_to(root):
        raise ValueError("output must not be written under the approved benchmark root")
    report = BenchmarkCatalogBuilder().build(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
