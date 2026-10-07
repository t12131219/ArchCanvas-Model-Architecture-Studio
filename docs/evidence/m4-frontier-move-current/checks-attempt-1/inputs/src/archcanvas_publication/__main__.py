"""stdin SVG → stdout artifact; JSON capability/receipt through explicit flags."""

import argparse
import json
import sys

from . import PublicationError, capabilities, export_svg
from .exporter import MAX_SVG_BYTES


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capabilities", action="store_true")
    parser.add_argument("--format", choices=("svg", "pdf", "png"), default="svg")
    parser.add_argument("--width-mm", type=float, default=180)
    parser.add_argument("--dpi", type=int, default=300)
    options = parser.parse_args(argv)
    try:
        if options.capabilities:
            print(json.dumps(capabilities(), ensure_ascii=False))
            return 0
        source = sys.stdin.buffer.read(MAX_SVG_BYTES + 1)
        if len(source) > MAX_SVG_BYTES:
            raise PublicationError("SVG exceeds the 8 MB input budget.")
        result = export_svg(source.decode("utf-8"), options.format, options.width_mm, options.dpi)
        sys.stdout.buffer.write(result["data"])
        sys.stdout.buffer.flush()
        print(json.dumps(result["receipt"], ensure_ascii=False), file=sys.stderr)
        return 0
    except (PublicationError, UnicodeError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
