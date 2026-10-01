from __future__ import annotations

import argparse
import json
from pathlib import Path

from archcanvas_core.builtin_registry import builtin_registry_bundle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    targets = [
        root / "contracts" / "module-registry-v1.json",
        root / "studio" / "src" / "module-registry" / "module-registry-v1.json",
    ]
    expected = json.dumps(
        builtin_registry_bundle().model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    stale: list[str] = []
    for target in targets:
        if args.check:
            if not target.is_file() or target.read_text(encoding="utf-8") != expected:
                stale.append(str(target.relative_to(root)))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(expected, encoding="utf-8")
    if stale:
        print("stale module registry bundles: " + ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
