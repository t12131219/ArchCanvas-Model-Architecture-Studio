from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    bundled_runtime = skill_root / "runtime" / "src"
    development_runtime = skill_root.parent / "src"
    runtime = bundled_runtime if bundled_runtime.is_dir() else development_runtime
    if not runtime.is_dir():
        print("ArchCanvas runtime is missing from this skill installation.", file=sys.stderr)
        return 3
    sys.path.insert(0, str(runtime))
    from archcanvas_engine.cli import main as cli_main

    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
