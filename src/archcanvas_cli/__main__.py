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
    parser = argparse.ArgumentParser(prog="archcanvas", description="Static analysis and Studio by default; explicit isolated profiles verify reviewed structural source changes.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("capabilities", help="Report implemented capabilities and actual package provenance")
    doctor = subcommands.add_parser("doctor", help="Identify actual runtime version, assets, module counts and next step without model execution")
    doctor.add_argument("--summary", action="store_true", help="Keep integrity checks and inventory digest; omit the per-file asset listing")
    discovery = subcommands.add_parser("discover", help="Scan local Python model classes and source-backed containment without executing models")
    discovery.add_argument("--root", type=Path, required=True)
    discovery.add_argument("--output", type=Path)
    adapter = subcommands.add_parser("adapter", help="Scaffold, verify and persist source-bound data adapters; never execute plugins")
    adapter_actions = adapter.add_subparsers(dest="adapter_action", required=True)
    rule_check = adapter_actions.add_parser("rule-validate", help="Validate an Agent-authored declarative AST rule without a source binding")
    rule_check.add_argument("--rule", type=Path, required=True)
    rule_check.add_argument("--output", type=Path)
    rule_list = adapter_actions.add_parser("rules", help="List persisted reusable AST rule templates")
    rule_list.add_argument("--registry", type=Path, required=True)
    rule_list.add_argument("--output", type=Path)
    for action in ("scaffold", "validate", "register", "list", "preview", "handoff"):
        operation = adapter_actions.add_parser(action)
        operation.add_argument("--root", type=Path, required=True, help="Source corpus used to verify the adapter's exact source binding")
        operation.add_argument("--output", type=Path)
        if action in ("scaffold", "preview", "handoff"):
            operation.add_argument("--entry", required=True)
            operation.add_argument("--config", type=Path, help="JSON constructor configuration, statically declared only")
        if action == "scaffold":
            operation.add_argument("--method", help="Source method to inspect, defaulting to the resolved model entry method")
            operation.add_argument("--rules", type=Path, help="Agent-authored source rule object or array of rule templates")
            operation.add_argument("--registry", type=Path, help="Reuse saved rules to bind a fresh v2 adapter to this source")
        if action in ("validate", "register"):
            operation.add_argument("--definition", type=Path, required=True)
        if action in ("register", "list", "preview"):
            operation.add_argument("--registry", type=Path, required=True, help="Explicit persistent JSON adapter registry")
        if action == "handoff":
            operation.add_argument("--registry", type=Path, help="Read existing adapters without writing them")
            operation.add_argument("--probe-spec", type=Path, help="Explicit semantic-inputs/1 CPU cases; opt in to isolated execution before handoff")
            operation.add_argument("--runtime-interpreter", type=Path)
            operation.add_argument("--dependency-lock", type=Path)
            operation.add_argument("--probe-output", type=Path, help="Persist the full CPU observation result separately")
            operation.add_argument("--probe-timeout", type=int, default=30)
        if action == "preview":
            operation.add_argument("--semantic-mode", choices=("summary", "legacy"), default="legacy")
    opening = subcommands.add_parser("open", help="Statically analyze a model and return its exact persisted canvas session URL")
    inputs = opening.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--root", type=Path)
    inputs.add_argument("--source", type=Path)
    opening.add_argument("--entry", required=True)
    opening.add_argument("--server", default="http://127.0.0.1:8765")
    session = subcommands.add_parser("session", help="Read, apply visual operations, undo, redo, save or export the same persisted canvas")
    actions = session.add_subparsers(dest="session_action", required=True)
    for action in ("read", "apply", "undo", "redo", "save", "export"):
        operation = actions.add_parser(action)
        operation.add_argument("--server", default="http://127.0.0.1:8765")
        operation.add_argument("--document-id", required=True)
        if action != "read":
            operation.add_argument("--expected-revision", type=int, required=True)
        if action not in ("read", "save"):
            operation.add_argument("--visual-revision", type=int, required=True)
        if action == "apply": operation.add_argument("--operations", type=Path, required=True, help="JSON array of the Studio typed visual operations")
        if action == "save": operation.add_argument("--document", type=Path, required=True, help="CanvasDocument or saved history envelope")
        if action == "export":
            operation.add_argument("--format", choices=("svg", "pdf", "png"), default="svg")
            operation.add_argument("--dpi", type=int, default=300)
            operation.add_argument("--width-mm", type=float)
    analyze = subcommands.add_parser("analyze", help="Analyze an explicit model class without importing user source")
    inputs = analyze.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--root", type=Path, help="Python source root; entry is module:Class")
    inputs.add_argument("--source", type=Path, help="Single Python source file; entry may be Class")
    analyze.add_argument("--entry", required=True)
    analyze.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout")
    patch = subcommands.add_parser("patch", help="Prepare/review/explicitly approve/commit a registered source transaction")
    actions = patch.add_subparsers(dest="patch_action", required=True)
    for action in ("prepare", "configuration", "activation", "rebind", "review", "approve", "commit", "discard"):
        operation = actions.add_parser(action, help={"prepare": "Isolate and verify a float-literal diff without changing source", "configuration": "Verify a unique top-level float config and all registered probability readers", "activation": "Verify a default ReLU/GELU replacement with an explicit isolated CPU profile", "rebind": "Verify a named input replacement with an explicit isolated CPU profile; no source commit", "review": "Print the exact diff, impact, gates and reviewDigest", "approve": "Record the human approval of an exact reviewDigest", "commit": "Apply only the concretely approved diff after full freshness checks", "discard": "Invalidate an uncommitted transaction"}[action])
        operation.add_argument("--root", type=Path, required=True, help="Explicit project source root; every action verifies this binding")
        operation.add_argument("--entry", required=True, help="Bound entry module:Class")
        operation.add_argument("--store", type=Path, required=True, help="Private transaction store for this root and entry")
        if action in ("prepare", "configuration", "activation", "rebind"):
            operation.add_argument("--node", required=True, help="Exact node ID from source-bound analysis")
            operation.add_argument("--base-source-digest", required=True, help="Exact reviewed analysis sourceDigest")
            if action in ("prepare", "configuration"):
                operation.add_argument("--parameter", required=True, choices=("p", "dropout"))
                operation.add_argument("--value", type=float, required=True)
            else:
                if action == "rebind":
                    operation.add_argument("--port", required=True, help="Exact canonical input port; named/positional source argument order is preserved")
                    operation.add_argument("--producer-node", required=True)
                    operation.add_argument("--producer-port", required=True)
                else:
                    operation.add_argument("--activation", required=True, choices=("ReLU", "GELU"))
                operation.add_argument("--input-spec", type=Path, required=True, help="JSON declaring all named input shapes/dtypes, seed and modes")
                operation.add_argument("--runtime-interpreter", type=Path, required=True, help="Explicit locked CPU runtime venv interpreter")
                operation.add_argument("--dependency-lock", type=Path, required=True)
        else:
            operation.add_argument("--transaction", required=True, help="Managed transaction ID returned by prepare")
        if action == "approve":
            operation.add_argument("--review-digest", required=True, help="Exact digest from the transaction reviewed by the human")
        elif action == "commit":
            operation.add_argument("--approval-id", required=True, help="Unconsumed approval ID for this transaction")
    serve = subcommands.add_parser("serve", help="Start loopback-only Studio/API service")
    serve.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "localhost"))
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--data-dir", type=Path, help="Complete independent state root (documents, projects, drafts, exports, transactions)")
    serve.add_argument("--studio-dir", type=Path)
    runtime = subcommands.add_parser("runtime", help="Explicit isolated model execution; never required for static source viewing")
    runtime.add_argument("--root", type=Path, required=True)
    runtime.add_argument("--entry", required=True)
    runtime.add_argument("--input-spec", type=Path, required=True)
    runtime.add_argument("--interpreter", type=Path, required=True)
    runtime.add_argument("--dependency-lock", type=Path, required=True)
    runtime.add_argument("--output", type=Path)
    options = parser.parse_args(argv)
    try:
        if options.command == "doctor":
            from .doctor import diagnose
            result = diagnose(summary=options.summary)
        elif options.command == "discover":
            from archcanvas_python.discovery import discover_directory
            result = discover_directory(options.root)
        elif options.command == "adapter":
            from archcanvas_adapters import AdapterRegistry, scaffold_adapter_files, validate_adapter_files
            from archcanvas_python.discovery import read_directory_files
            action = options.adapter_action
            files = read_directory_files(options.root) if hasattr(options, "root") else None
            config = json.loads(options.config.read_text()) if getattr(options, "config", None) else None
            if action == "rule-validate":
                from archcanvas_adapters.source_rules import validate_rule
                result = validate_rule(json.loads(options.rule.read_text()))
            elif action == "rules":
                result = AdapterRegistry(options.registry).rules()
            elif action == "scaffold":
                rules = json.loads(options.rules.read_text()) if options.rules else None
                from archcanvas_adapters.registry import merge_rules
                if options.registry:
                    rules = merge_rules(rules, AdapterRegistry(options.registry).rule_definitions())
                elif rules is not None:
                    rules = merge_rules(rules)
                result = scaffold_adapter_files(files, options.entry, method=options.method, config=config, rules=rules)
            elif action == "validate":
                result = validate_adapter_files(json.loads(options.definition.read_text()), files)
            elif action == "register":
                result = AdapterRegistry(options.registry).register_files(json.loads(options.definition.read_text()), files)
            elif action == "list":
                result = AdapterRegistry(options.registry).list_files(files)
            elif action == "handoff":
                from archcanvas_adapters.handoff import build_handoff
                probe_result = None
                if options.probe_spec:
                    if not options.runtime_interpreter or not options.dependency_lock:
                        raise ValueError("--probe-spec requires --runtime-interpreter and --dependency-lock; no automatic environment fallback.")
                    from archcanvas_runtime.summary import normalize_summary_spec, observe_summary
                    spec = normalize_summary_spec(json.loads(options.probe_spec.read_text()))
                    if config is not None and config != spec.get('constructor', {}):
                        raise ValueError("--config and --probe-spec constructor must match.")
                    config = spec.get('constructor', {})
                    probe_result = observe_summary(files, options.entry, spec, {
                        'interpreter': str(options.runtime_interpreter.absolute()),
                        'dependencyLock': str(options.dependency_lock.absolute()),
                        'timeoutSeconds': options.probe_timeout})
                    if options.probe_output:
                        options.probe_output.parent.mkdir(parents=True, exist_ok=True)
                        options.probe_output.write_text(json.dumps(probe_result, ensure_ascii=False, allow_nan=False, indent=2) + '\n')
                elif options.runtime_interpreter or options.dependency_lock or options.probe_output:
                    raise ValueError("CPU probe options require explicit --probe-spec.")
                result = build_handoff(files, options.entry, config, options.registry, probe_result)
            else:
                import archcanvas_preview
                result = archcanvas_preview.analyze(files, options.entry, config, semantic_mode=options.semantic_mode)
                result = AdapterRegistry(options.registry).preview(result, files)
        elif options.command in ("open", "session"):
            from .client import request
            from urllib.parse import quote
            if options.command == "open":
                architecture = analyze_project(options.root, options.entry) if options.root else analyze_source(options.source.read_text(encoding="utf-8-sig"), options.entry, options.source.name, raw_bytes=options.source.read_bytes())
                result = request(options.server, "/api/open", {"architecture": architecture})
            else:
                path = "/api/canvas-sessions/" + quote(options.document_id, safe="")
                action = options.session_action
                if action == "read": result = request(options.server, path)
                elif action == "save":
                    value = json.loads(options.document.read_text())
                    result = request(options.server, "/api/documents/" + quote(options.document_id, safe=""),
                                     {"document": value.get("document", value), "expectedRevision": options.expected_revision,
                                      **({"history": value["history"]} if "history" in value else {})}, "PUT")
                else:
                    payload = {"expectedRevision": options.expected_revision, "visualRevision": options.visual_revision}
                    if action == "apply": payload["operations"] = json.loads(options.operations.read_text())
                    if action == "export":
                        payload.update(format=options.format, dpi=options.dpi)
                        if options.width_mm is not None: payload["options"] = {"widthMm": options.width_mm}
                    result = request(options.server, path + "/" + action, payload)
        elif options.command == "capabilities":
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
        elif options.command == "runtime":
            from archcanvas_runtime import verify_structural
            result = verify_structural(options.root, options.entry, json.loads(options.input_spec.read_text()), {"interpreter": str(options.interpreter.absolute()), "dependencyLock": str(options.dependency_lock.absolute())})
            encoded = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2)
            if options.output:
                options.output.parent.mkdir(parents=True, exist_ok=True)
                options.output.write_text(encoded + "\n")
            else:
                print(encoded)
            return 0 if result["status"] == "passed" else 2
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
            if options.patch_action in ("prepare", "configuration"):
                prepare = manager.prepare_config if options.patch_action == "configuration" else manager.prepare
                result = prepare(source_root, options.entry, options.node, options.parameter, options.value, options.base_source_digest)
            elif options.patch_action == "activation":
                result = manager.prepare_activation(source_root, options.entry, options.node, options.activation, options.base_source_digest, inputSpec=json.loads(options.input_spec.read_text()), runtimeConfig={"interpreter": str(options.runtime_interpreter.absolute()), "dependencyLock": str(options.dependency_lock.absolute())})
            elif options.patch_action == "rebind":
                result = manager.prepare_rebind(source_root, options.entry, options.node, options.port, options.producer_node, options.producer_port, options.base_source_digest, inputSpec=json.loads(options.input_spec.read_text()), runtimeConfig={"interpreter": str(options.runtime_interpreter.absolute()), "dependencyLock": str(options.dependency_lock.absolute())})
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
        if options.command in ("discover", "adapter") and options.output:
            options.output.parent.mkdir(parents=True, exist_ok=True)
            options.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if options.command == "doctor" and result["status"] != "ready-local" else 0
    except (AnalysisError, OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
