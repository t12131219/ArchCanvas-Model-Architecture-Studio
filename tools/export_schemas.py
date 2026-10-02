from __future__ import annotations

import argparse
import json
from pathlib import Path

from archcanvas_core.schema_registry import SCHEMA_MODELS


def schema_text(model: type) -> str:
    return json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--only",
        action="append",
        choices=sorted(SCHEMA_MODELS),
        help="Export or check only the named schema; may be repeated.",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    schema_dirs = [root / "schemas", root / "src" / "archcanvas_core" / "schemas"]
    for schema_dir in schema_dirs:
        schema_dir.mkdir(exist_ok=True)
    stale: list[str] = []
    selected = set(args.only or SCHEMA_MODELS)
    for filename, model in SCHEMA_MODELS.items():
        if filename not in selected:
            continue
        expected = schema_text(model)
        for schema_dir in schema_dirs:
            path = schema_dir / filename
            if args.check:
                if not path.exists() or path.read_text(encoding="utf-8") != expected:
                    stale.append(str(path.relative_to(root)))
            else:
                path.write_text(expected, encoding="utf-8")
    if stale:
        print("stale schemas: " + ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
