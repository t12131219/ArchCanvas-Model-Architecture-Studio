from __future__ import annotations

import argparse
from pathlib import Path

from archcanvas_publication.routing_fixtures import routing_preview_fixture_text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    path = root / "fixtures" / "routing" / "preview-contract-v1.json"
    expected = routing_preview_fixture_text()
    if args.check:
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            print(f"stale routing fixture: {path.relative_to(root)}")
            return 1
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
