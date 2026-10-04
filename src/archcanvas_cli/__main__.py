"""Run with PYTHONPATH=src python -m archcanvas_cli from the formal project."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from archcanvas_python import AnalysisError, analyze_project, analyze_source
from .server import ArchCanvasServer, capabilities


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="archcanvas", description="Static source analysis and local visual document service. Model code is never executed.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("capabilities", help="Report implemented capabilities and actual package provenance")
    analyze = subcommands.add_parser("analyze", help="Analyze an explicit model class without importing user source")
    inputs = analyze.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--root", type=Path, help="Python source root; entry is module:Class")
    inputs.add_argument("--source", type=Path, help="Single Python source file; entry may be Class")
    analyze.add_argument("--entry", required=True)
    analyze.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout")
    serve = subcommands.add_parser("serve", help="Start loopback-only Studio/API service")
    serve.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "localhost"))
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--data-dir", type=Path)
    serve.add_argument("--studio-dir", type=Path)
    options = parser.parse_args(argv)
    try:
        if options.command == "capabilities":
            result = capabilities()
        elif options.command == "analyze":
            if options.root:
                result = analyze_project(options.root, options.entry)
            else:
                result = analyze_source(options.source.read_text(encoding="utf-8"), options.entry, options.source.name)
            if options.output:
                options.output.parent.mkdir(parents=True, exist_ok=True)
                options.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                return 0
        else:
            if not 0 <= options.port <= 65535:
                raise ValueError("Port must be in the range 0–65535.")
            server = ArchCanvasServer((options.host, options.port), data_dir=options.data_dir, studio_dir=options.studio_dir)
            print(json.dumps({"url": f"http://127.0.0.1:{server.server_address[1]}", "capabilities": capabilities()}, ensure_ascii=False), flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
            return 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (AnalysisError, OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
