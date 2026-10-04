"""Run with PYTHONPATH=src python -m archcanvas_cli from the formal project."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from archcanvas_python import AnalysisError, analyze_project, analyze_source
from archcanvas_transactions import TransactionManager
from .server import ArchCanvasServer, capabilities


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="archcanvas", description="Static analysis, reviewed parameter transactions and local Studio. Model code is never executed.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("capabilities", help="Report implemented capabilities and actual package provenance")
    analyze = subcommands.add_parser("analyze", help="Analyze an explicit model class without importing user source")
    inputs = analyze.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--root", type=Path, help="Python source root; entry is module:Class")
    inputs.add_argument("--source", type=Path, help="Single Python source file; entry may be Class")
    analyze.add_argument("--entry", required=True)
    analyze.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout")
    patch = subcommands.add_parser("patch", help="Prepare/review/explicitly approve/commit a bounded source parameter transaction")
    actions = patch.add_subparsers(dest="patch_action", required=True)
    for action in ("prepare", "review", "approve", "commit", "discard"):
        operation = actions.add_parser(action, help={"prepare": "Isolate and verify a float-literal diff without changing source", "review": "Print the exact diff, impact, gates and reviewDigest", "approve": "Record the human approval of an exact reviewDigest", "commit": "Apply only the concretely approved diff after full freshness checks", "discard": "Invalidate an uncommitted transaction"}[action])
        operation.add_argument("--root", type=Path, required=True, help="Explicit project source root; every action verifies this binding")
        operation.add_argument("--entry", required=True, help="Bound entry module:Class")
        operation.add_argument("--store", type=Path, required=True, help="Private transaction store for this root and entry")
        if action == "prepare":
            operation.add_argument("--node", required=True, help="Exact node ID from source-bound analysis")
            operation.add_argument("--parameter", required=True, choices=("p", "dropout"))
            operation.add_argument("--value", type=float, required=True)
            operation.add_argument("--base-source-digest", required=True, help="Exact reviewed analysis sourceDigest")
        else:
            operation.add_argument("--transaction", required=True, help="Managed transaction ID returned by prepare")
        if action == "approve":
            operation.add_argument("--review-digest", required=True, help="Exact digest from the transaction reviewed by the human")
        elif action == "commit":
            operation.add_argument("--approval-id", required=True, help="Unconsumed approval ID for this transaction")
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
                raw = options.source.read_bytes()
                result = analyze_source(raw.decode("utf-8-sig"), options.entry, options.source.name, raw_bytes=raw)
            if options.output:
                options.output.parent.mkdir(parents=True, exist_ok=True)
                options.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                return 0
        elif options.command == "patch":
            source_root = options.root.resolve()
            registry = options.store.resolve() / "registered.json"
            # Manager startup may perform guarded recovery. Verify the CLI's
            # explicit project scope BEFORE allowing that startup recovery.
            if registry.exists():
                registered = json.loads(registry.read_text(encoding="utf-8"))
                if not isinstance(registered, dict) or any(not isinstance(binding, dict) or binding.get("root") != str(source_root) or binding.get("entry") != options.entry for binding in registered.values()):
                    raise ValueError("CLI patch store belongs to another root/entry; select this project's private transaction store.")
            manager = TransactionManager(options.store)
            if options.patch_action == "prepare":
                result = manager.prepare(source_root, options.entry, options.node, options.parameter, options.value, options.base_source_digest)
            else:
                if not manager.matches_project(options.transaction, source_root, options.entry):
                    raise ValueError("Transaction source root or entry does not match the explicit CLI project binding.")
                if options.patch_action == "review":
                    result = manager.get(options.transaction)
                elif options.patch_action == "approve":
                    result = manager.approve(options.transaction, options.review_digest)
                elif options.patch_action == "commit":
                    result = manager.commit(options.transaction, options.approval_id)
                else:
                    result = manager.discard(options.transaction)
            print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
            return 0 if result["status"] in ("ReviewReady", "Approved", "Committed", "Discarded") else 2
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
