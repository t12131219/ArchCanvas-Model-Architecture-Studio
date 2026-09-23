from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
import tempfile
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from archcanvas_core.models import (
    SCHEMA_MODELS,
    ArchitectureIR,
    CommandReceipt,
    Diagnostic,
    EvidenceRecord,
    GateResult,
    SemanticParameterPatch,
    SourceSnapshot,
)
from archcanvas_core.validation import validate_architecture
from archcanvas_publication import (
    build_scene,
    build_visual_spec,
    compile_views,
    render_html,
    render_svg,
    validate_geometry,
    validate_publication,
)
from archcanvas_python import AnalysisError, analyze_project
from archcanvas_runtime import RuntimeTraceError, trace_runtime
from archcanvas_studio import StudioBundle, prepare_studio_bundle, source_binding_digest
from archcanvas_studio.server import create_studio_server
from archcanvas_transactions import (
    commit_transaction,
    discard_transaction,
    prepare_transaction,
    verify_transaction,
)

SOURCE_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SOURCE_PACKAGE_ROOT.parent


def _compact(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        default=lambda item: item.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _emit(receipt: CommandReceipt) -> int:
    print(_compact(receipt), flush=True)
    return receipt.exit_code


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _compact(value) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(value)
        temporary = Path(handle.name)
    temporary.replace(path)


def _invalid(command: str, code: str, message: str) -> CommandReceipt:
    return CommandReceipt(
        command=command,
        status="invalid",
        exit_code=2,
        diagnostics=[Diagnostic(code=code, severity="blocking", message=message)],
    )


def _unavailable(command: str, capability: str) -> CommandReceipt:
    return CommandReceipt(
        command=command,
        status="unavailable",
        exit_code=3,
        diagnostics=[
            Diagnostic(
                code="CAPABILITY_UNAVAILABLE",
                severity="blocking",
                message=f"{capability} is not implemented in the rewrite baseline.",
            )
        ],
        details={"capability": capability, "milestone": "planned"},
    )


def doctor() -> CommandReceipt:
    packages: dict[str, str] = {}
    missing: list[str] = []
    for package in ("pydantic", "jsonschema", "libcst"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            missing.append(package)
    source_schema_dir = REPOSITORY_ROOT / "schemas"
    schema_dir = (
        source_schema_dir
        if source_schema_dir.is_dir()
        else SOURCE_PACKAGE_ROOT / "archcanvas_core" / "schemas"
    )
    missing_schemas = [
        filename for filename in SCHEMA_MODELS if not (schema_dir / filename).is_file()
    ]
    diagnostics = [
        Diagnostic(
            code="DEPENDENCY_MISSING",
            severity="blocking",
            message="Missing required packages: " + ", ".join(missing),
        )
        for _ in [0]
        if missing
    ]
    if missing_schemas:
        diagnostics.append(
            Diagnostic(
                code="SCHEMA_MISSING",
                severity="blocking",
                message="Missing exported schemas: " + ", ".join(missing_schemas),
            )
        )
    try:
        torch_version = importlib.metadata.version("torch")
    except importlib.metadata.PackageNotFoundError:
        torch_version = None
    status = "invalid" if diagnostics else "ok"
    return CommandReceipt(
        command="doctor",
        status=status,
        exit_code=2 if diagnostics else 0,
        gates=[
            GateResult(
                gate="A-environment",
                status="failed" if diagnostics else "passed",
                message="Required local protocol dependencies and schemas are present."
                if not diagnostics
                else "Environment is incomplete.",
            )
        ],
        diagnostics=diagnostics,
        details={
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": packages,
            "network_required": False,
            "capabilities": {
                "static_analysis": "available-generic+five-tier-a-profiles",
                "semantic_validation": "available",
                "publication_render": "available-svg+html-l1-l4",
                "studio": "available-visual-editing",
                "runtime_trace": (
                    "available-opt-in-pytorch" if torch_version else "unavailable-missing-torch"
                ),
                "source_transactions": "available-set-parameter",
            },
            "runtime_packages": {"torch": torch_version},
        },
    )


def analyze(args: argparse.Namespace) -> CommandReceipt:
    project = args.project.resolve()
    config_bytes = args.config.read_bytes() if args.config else b"{}"
    bundle = analyze_project(
        project,
        args.entry,
        args.task,
        args.mode,
        config_bytes,
        args.config,
        pattern_packs_enabled=not args.no_pattern_packs,
    )
    gates, diagnostics = validate_architecture(
        bundle.architecture,
        bundle.evidence,
        bundle.snapshot,
    )
    out = args.out.resolve()
    profile = "generic" if args.no_pattern_packs else bundle.snapshot.resolved_config.get(
        "architecture_profile"
    ) or (
        "transformer-l3"
        if bundle.architecture.entrypoint.rsplit(":", 1)[-1].lower() == "transformer"
        else "generic"
    )
    artifacts = {
        "source_snapshot": str(out / "source-snapshot.json"),
        "evidence_ledger": str(out / "evidence-ledger.json"),
        "module_ledger": str(out / "module-ledger.json"),
        "tensor_ledger": str(out / "tensor-ledger.json"),
        "edge_ledger": str(out / "edge-ledger.json"),
        "discrepancy_ledger": str(out / "discrepancy-ledger.json"),
        "omission_ledger": str(out / "omission-ledger.json"),
        "capability_report": str(out / "capability-report.json"),
        "semantic_overlay": str(out / "semantic-annotation-overlay.json"),
        "pattern_receipt": str(out / "pattern-pack-receipt.json"),
        "source_correction_report": str(out / "source-correction-report.json"),
        "runtime_receipt": str(out / "runtime-receipt.json"),
        "architecture": str(out / "architecture.json"),
    }
    blocking = any(item.severity == "blocking" for item in diagnostics)
    if blocking:
        return CommandReceipt(
            command="analyze",
            status="invalid",
            exit_code=2,
            gates=gates,
            diagnostics=diagnostics,
            details={"writes_performed": False},
        )
    _write_json(Path(artifacts["source_snapshot"]), bundle.snapshot)
    _write_json(Path(artifacts["evidence_ledger"]), bundle.evidence)
    _write_json(Path(artifacts["module_ledger"]), bundle.architecture.nodes)
    _write_json(Path(artifacts["tensor_ledger"]), bundle.architecture.tensors)
    _write_json(Path(artifacts["edge_ledger"]), bundle.architecture.edges)
    _write_json(Path(artifacts["discrepancy_ledger"]), bundle.discrepancies)
    _write_json(Path(artifacts["omission_ledger"]), bundle.architecture.unresolved)
    _write_json(
        Path(artifacts["capability_report"]),
        {
            "schema_version": "1.0",
            "adapter": f"python-ast-pytorch-{profile}",
            "static_analysis": True,
            "runtime_evidence": "available-opt-in",
            "supported_profiles": [
                "generic",
                "transformer-l3",
                "autoformer",
                "itransformer",
                "patchtst",
                "timemixer",
            ],
            "semantic_transforms": ["set_parameter"],
        },
    )
    _write_json(
        Path(artifacts["semantic_overlay"]),
        {
            "schema_version": "1.0",
            "architecture_id": bundle.architecture.architecture_id,
            "profile": profile,
            "annotations": []
            if args.no_pattern_packs
            else [
                {
                    "node_id": node.node_id,
                    "semantic_name": node.semantic_name,
                    "evidence_ids": node.evidence_ids,
                }
                for node in bundle.architecture.nodes
            ],
        },
    )
    _write_json(
        Path(artifacts["pattern_receipt"]),
        {
            "schema_version": "1.0",
            "profile": profile,
            "status": "disabled" if args.no_pattern_packs else "matched",
            "source_execution": False,
            "loaded_packs": [] if args.no_pattern_packs else [profile],
            "exact_ir_digest_before": hashlib.sha256(
                _compact(bundle.architecture).encode()
            ).hexdigest(),
            "exact_ir_digest_after": hashlib.sha256(
                _compact(bundle.architecture).encode()
            ).hexdigest(),
        },
    )
    _write_json(
        Path(artifacts["source_correction_report"]),
        {
            "schema_version": "1.0",
            "profile": profile,
            "discrepancies": bundle.discrepancies,
        },
    )
    _write_json(
        Path(artifacts["runtime_receipt"]),
        {
            "schema_version": "1.0",
            "status": "skipped",
            "source_execution": False,
            "reason": "Run archcanvas trace with an explicit input spec to opt in.",
            "gates": [
                GateResult(
                    gate="G-runtime-authorization",
                    status="skipped",
                    message="Static analysis did not receive runtime execution authorization.",
                )
            ],
        },
    )
    _write_json(Path(artifacts["architecture"]), bundle.architecture)
    receipt = CommandReceipt(
        command="analyze",
        status="ok",
        exit_code=0,
        artifacts=artifacts,
        gates=gates,
        diagnostics=diagnostics,
        details={
            "source_execution": False,
            "profile": profile,
            "pattern_packs_enabled": not args.no_pattern_packs,
            "node_count": len(bundle.architecture.nodes),
            "tensor_count": len(bundle.architecture.tensors),
            "edge_count": len(bundle.architecture.edges),
            "fanout_count": len(bundle.architecture.fanouts),
            "unresolved_count": len(bundle.architecture.unresolved),
        },
    )
    _write_json(out / "analysis-receipt.json", receipt)
    return receipt


def validate(args: argparse.Namespace) -> CommandReceipt:
    raw = args.artifact.read_text(encoding="utf-8")
    ir = ArchitectureIR.model_validate_json(raw)
    snapshot_path = args.artifact.parent / "source-snapshot.json"
    evidence_path = args.artifact.parent / "evidence-ledger.json"
    snapshot = (
        SourceSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
        if snapshot_path.is_file()
        else None
    )
    evidence = (
        TypeAdapter(list[EvidenceRecord]).validate_json(evidence_path.read_text(encoding="utf-8"))
        if evidence_path.is_file()
        else None
    )
    gates, diagnostics = validate_architecture(ir, evidence, snapshot)
    publication_available = args.quality == "publication"
    if publication_available:
        gates = [gate for gate in gates if gate.gate != "C-publication-compilation"]
        views = compile_views(ir)
        publication_gates, publication_diagnostics = validate_publication(ir, views)
        gates.extend(publication_gates)
        diagnostics.extend(publication_diagnostics)
        for view in views:
            spec = build_visual_spec(view)
            scene = build_scene(view, spec)
            geometry_gate, geometry_diagnostics = validate_geometry(scene)
            gates.append(
                geometry_gate.model_copy(update={"gate": f"D-geometry-{view.level}"})
            )
            diagnostics.extend(geometry_diagnostics)
    failed = any(gate.status == "failed" for gate in gates)
    return CommandReceipt(
        command="validate",
        status="invalid" if failed else "ok",
        exit_code=2 if failed else 0,
        artifacts={"architecture": str(args.artifact.resolve())},
        gates=gates,
        diagnostics=diagnostics,
        details={
            "quality": args.quality,
            "publication_gates_available": publication_available,
            "evidence_binding_loaded": snapshot is not None and evidence is not None,
        },
    )


VIEW_ALIASES = {
    "paper-overview": "L1",
    "overview": "L1",
    "l1": "L1",
    "module": "L2",
    "l2": "L2",
    "semantic": "L3",
    "l3": "L3",
    "operator": "L4",
    "full": "L4",
    "l4": "L4",
}


def render(args: argparse.Namespace) -> CommandReceipt:
    ir = ArchitectureIR.model_validate_json(args.artifact.read_text(encoding="utf-8"))
    views = compile_views(ir)
    publication_gates, diagnostics = validate_publication(ir, views)
    if args.view == "all":
        selected = views
    else:
        selected_level = VIEW_ALIASES[args.view.lower()]
        selected = [view for view in views if view.level == selected_level]
    compiled: list[tuple[Any, Any, Any]] = []
    geometry_gates: list[GateResult] = []
    for view in selected:
        spec = build_visual_spec(view)
        scene = build_scene(view, spec)
        geometry_gate, geometry_diagnostics = validate_geometry(scene)
        geometry_gates.append(
            geometry_gate.model_copy(
                update={"gate": f"D-geometry-{view.level}" if args.view == "all" else "D-geometry"}
            )
        )
        diagnostics.extend(geometry_diagnostics)
        compiled.append((view, spec, scene))
    gates = [
        *publication_gates,
        *geometry_gates,
        GateResult(
            gate="E-visual-review",
            status="skipped",
            message="Visual review is recorded separately after inspecting rendered artifacts.",
        ),
    ]
    if any(gate.status == "failed" for gate in gates):
        return CommandReceipt(
            command="render",
            status="invalid",
            exit_code=2,
            gates=gates,
            diagnostics=diagnostics,
            details={"writes_performed": False, "view": args.view},
        )

    out = args.out.resolve()
    artifacts: dict[str, str] = {"architecture": str(args.artifact.resolve())}
    for view, spec, scene in compiled:
        target = out / view.level.lower() if args.view == "all" else out
        paths = {
            "publication_view": target / "publication-view.json",
            "visual_spec": target / "visual-spec.json",
            "visual_scene": target / "visual-scene.json",
            "svg": target / "scene.svg",
            "html": target / "view.html",
        }
        prefix = f"{view.level.lower()}_" if args.view == "all" else ""
        artifacts.update({f"{prefix}{key}": str(path) for key, path in paths.items()})
        _write_json(paths["publication_view"], view)
        _write_json(paths["visual_spec"], spec)
        _write_json(paths["visual_scene"], scene)
        _write_text(paths["svg"], render_svg(scene))
        _write_text(paths["html"], render_html(scene, view, spec))
    artifacts["render_receipt"] = str(out / "render-receipt.json")
    receipt = CommandReceipt(
        command="render",
        status="ok",
        exit_code=0,
        artifacts=artifacts,
        gates=gates,
        diagnostics=diagnostics,
        details={
            "view": args.view,
            "levels": [view.level for view, _, _ in compiled],
            "layout_families": {view.level: view.layout_family for view, _, _ in compiled},
            "canonical_surface": "svg",
            "html_self_contained": True,
            "png": "unavailable",
            "pdf": "unavailable",
            "runtime_evidence": "skipped",
            "visual_review": "skipped",
        },
    )
    _write_json(Path(artifacts["render_receipt"]), receipt)
    return receipt


def studio(args: argparse.Namespace) -> tuple[CommandReceipt, StudioBundle | None]:
    workspace = (
        args.workspace.resolve()
        if args.workspace is not None
        else (args.artifact.parent / ".archcanvas").resolve()
    )
    bundle = prepare_studio_bundle(args.artifact, workspace)
    gates: list[GateResult] = []
    diagnostics: list[Diagnostic] = []
    for level, scene in bundle.materialized_scenes().items():
        gate, scene_diagnostics = validate_geometry(scene)
        gates.append(gate.model_copy(update={"gate": f"D-geometry-{level}"}))
        diagnostics.extend(scene_diagnostics)
    source_digest_matches = bundle.document.source_digest == source_binding_digest(bundle.snapshot)
    gates.append(
        GateResult(
            gate="F-visual-source-invariance",
            status="passed" if source_digest_matches else "failed",
            message=(
                "CanvasDocument remains bound to the exact source snapshot digest."
                if source_digest_matches
                else "CanvasDocument source binding is stale."
            ),
        )
    )
    failed = any(gate.status == "failed" for gate in gates)
    artifacts = {
        "studio_html": str(bundle.static_dir / "index.html"),
        "studio_state": str(bundle.static_dir / "studio-state.json"),
        "canvas_document": str(bundle.document_path),
        "workspace": str(bundle.workspace),
    }
    receipt = CommandReceipt(
        command="studio",
        status="invalid" if failed else "ok",
        exit_code=2 if failed else 0,
        artifacts=artifacts,
        gates=gates,
        diagnostics=diagnostics,
        details={
            "serve": args.serve,
            "url": f"http://{args.host}:{args.port}/" if args.serve else None,
            "source_writes": False,
            "visual_patch_count": len(bundle.document.visual_patches),
            "redo_patch_count": len(bundle.document.redo_patches),
            "modes": ["explore", "layout", "model"],
            "source_editing": "available-set-parameter-transaction",
        },
    )
    return receipt, bundle


def trace(args: argparse.Namespace) -> CommandReceipt:
    return trace_runtime(args.artifact, args.input_spec, args.out)


def patch(args: argparse.Namespace) -> CommandReceipt:
    if args.patch_command == "prepare":
        request = SemanticParameterPatch.model_validate_json(
            args.request.read_text(encoding="utf-8")
        )
        transaction, receipt = prepare_transaction(request, args.workspace)
        directory = Path(transaction.workspace) / "transactions" / transaction.transaction_id
    elif args.patch_command == "verify":
        transaction, receipt = verify_transaction(args.transaction)
        directory = Path(transaction.workspace) / "transactions" / transaction.transaction_id
    elif args.patch_command == "commit":
        transaction, receipt = commit_transaction(args.transaction)
        directory = Path(transaction.workspace) / "transactions" / transaction.transaction_id
    elif args.patch_command == "discard":
        transaction, receipt = discard_transaction(args.transaction)
        directory = Path(transaction.workspace) / "transactions" / transaction.transaction_id
    else:  # pragma: no cover - argparse enforces the subcommand
        raise ValueError(f"unknown patch command: {args.patch_command}")
    status = "ok" if receipt.status == "ok" else "invalid"
    return CommandReceipt(
        command=f"patch {args.patch_command}",
        status=status,
        exit_code=0 if status == "ok" else 2,
        artifacts={
            "transaction": str(directory / "transaction.json"),
            "source_diff": str(directory / "source.diff"),
        },
        gates=receipt.gates,
        diagnostics=receipt.diagnostics,
        details={
            "transaction_id": transaction.transaction_id,
            "transaction_state": transaction.state.value,
            "source_writes": receipt.source_writes,
            "expected_delta": transaction.expected_delta.model_dump(mode="json"),
            "observed_delta": (
                transaction.observed_delta.model_dump(mode="json")
                if transaction.observed_delta is not None
                else None
            ),
        },
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="archcanvas")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--json", action="store_true")
    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--project", type=Path, required=True)
    analyze_parser.add_argument("--entry", required=True)
    analyze_parser.add_argument("--config", type=Path)
    analyze_parser.add_argument("--task", required=True)
    analyze_parser.add_argument("--mode", choices=("eval", "train"), required=True)
    analyze_parser.add_argument("--out", type=Path, required=True)
    analyze_parser.add_argument("--no-pattern-packs", action="store_true")
    analyze_parser.add_argument("--json", action="store_true")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("artifact", type=Path)
    validate_parser.add_argument("--quality", choices=("semantic", "publication"), default="semantic")
    validate_parser.add_argument("--json", action="store_true")
    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("artifact", type=Path)
    render_parser.add_argument(
        "--view",
        choices=(*VIEW_ALIASES, "all"),
        default="paper-overview",
    )
    render_parser.add_argument("--out", type=Path, required=True)
    render_parser.add_argument("--json", action="store_true")
    studio_parser = subparsers.add_parser("studio")
    studio_parser.add_argument("artifact", type=Path)
    studio_parser.add_argument("--workspace", type=Path)
    studio_parser.add_argument("--serve", action="store_true")
    studio_parser.add_argument("--host", default="127.0.0.1")
    studio_parser.add_argument("--port", type=int, default=4310)
    studio_parser.add_argument("--json", action="store_true")
    trace_parser = subparsers.add_parser("trace")
    trace_parser.add_argument("artifact", type=Path)
    trace_parser.add_argument("--input-spec", type=Path, required=True)
    trace_parser.add_argument("--out", type=Path, required=True)
    trace_parser.add_argument("--json", action="store_true")
    patch_parser = subparsers.add_parser("patch")
    patch_subparsers = patch_parser.add_subparsers(dest="patch_command", required=True)
    prepare_parser = patch_subparsers.add_parser("prepare")
    prepare_parser.add_argument("request", type=Path)
    prepare_parser.add_argument("--workspace", type=Path, required=True)
    prepare_parser.add_argument("--json", action="store_true")
    for command in ("verify", "commit", "discard"):
        transaction_parser = patch_subparsers.add_parser(command)
        transaction_parser.add_argument("transaction", type=Path)
        transaction_parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            receipt = doctor()
        elif args.command == "analyze":
            receipt = analyze(args)
        elif args.command == "validate":
            receipt = validate(args)
        elif args.command == "render":
            receipt = render(args)
        elif args.command == "studio":
            receipt, bundle = studio(args)
            exit_code = _emit(receipt)
            if args.serve and bundle is not None:
                server = create_studio_server(bundle, args.host, args.port)
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    pass
                finally:
                    server.server_close()
            return exit_code
        elif args.command == "trace":
            receipt = trace(args)
        elif args.command == "patch":
            receipt = patch(args)
        else:
            receipt = _unavailable(args.command, args.command)
        return _emit(receipt)
    except AnalysisError as error:
        return _emit(_invalid(args.command, error.code, str(error)))
    except RuntimeTraceError as error:
        return _emit(_invalid(args.command, "RUNTIME_REQUEST_INVALID", str(error)))
    except (OSError, ValidationError, ValueError, json.JSONDecodeError) as error:
        return _emit(_invalid(args.command, "INPUT_INVALID", str(error)))
    except Exception as error:  # noqa: BLE001  # pragma: no cover - final receipt boundary
        print(f"archcanvas internal error: {error}", file=sys.stderr)
        return _emit(
            CommandReceipt(
                command=args.command,
                status="failed",
                exit_code=1,
                diagnostics=[
                    Diagnostic(code="INTERNAL_ERROR", severity="blocking", message=str(error))
                ],
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())
