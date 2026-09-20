"""Print a machine-readable, read-only PyTorch project entrypoint report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from archcanvas_pytorch.static import PyTorchProjectScanner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--max-file-bytes", type=int, default=1_000_000)
    arguments = parser.parse_args()
    report = PyTorchProjectScanner(max_file_bytes=arguments.max_file_bytes).scan(arguments.project_root)
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
