from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
import tempfile
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from archcanvas_adapters import adapter_capabilities, analyze_with_adapter
from archcanvas_core.models import (
    SCHEMA_MODELS,
    ArchitectureIR,
    CommandReceipt,
    Diagnostic,
    EvidenceRecord,
    GateResult,
    ProposedConnection,
    SemanticAnnotationOverlay,
    SemanticParameterPatch,
    SemanticStructuralPatch,
    SourceSnapshot,
)
from archcanvas_core.validation import validate_architecture
from archcanvas_patterns import (
    apply_pattern_packs,
    build_candidate_reviews,
    exact_ir_digest,
    load_registry,
)
from archcanvas_publication import (
    build_scene,
    build_visual_spec,
    compile_views,
    render_html,
    render_pdf,
    render_png,
    render_svg,
    validate_geometry,
    validate_publication,
)
from archcanvas_python import AnalysisError
from archcanvas_release import create_bundle, install_skill, release_support_matrix, verify_bundle
from archcanvas_runtime import RuntimeTraceError, trace_runtime
from archcanvas_studio import StudioBundle, prepare_studio_bundle, source_binding_digest
from archcanvas_studio.server import create_studio_server
from archcanvas_transactions import (
    TRANSFORM_REGISTRY,
    commit_transaction,
    discard_transaction,
    plan_connection,
    prepare_transaction,
    unsupported_intent_proposal,
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


def _write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
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


def _semantic_overlay(artifact: Path, architecture: ArchitectureIR) -> SemanticAnnotationOverlay | None:
    path = artifact.parent / "semantic-annotation-overlay.json"
    if not path.is_file():
        return None
    overlay = SemanticAnnotationOverlay.model_validate_json(path.read_text(encoding="utf-8"))
    if (
        overlay.architecture_id != architecture.architecture_id
        or overlay.exact_ir_digest != exact_ir_digest(architecture)
    ):
        raise ValueError("semantic annotation overlay binding is stale")
    return overlay


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
    for package in ("pydantic", "jsonschema", "libcst", "cairosvg"):
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
    runtime_packages: dict[str, str | None] = {}
    for package in ("torch", "keras", "jax", "flax", "onnx", "onnxruntime"):
        try:
            runtime_packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            runtime_packages[package] = None
    runtime_frameworks = [
        item.framework for item in adapter_capabilities() if item.runtime_evidence
    ]
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
                "static_analysis": "available-python+pytorch+keras+jax+onnx",
                "semantic_validation": "available",
                "publication_render": "available-svg+html+png+pdf-l1-l4",
                "studio": "available-visual-editing",
                "runtime_trace": "available-opt-in-" + "+".join(runtime_frameworks),
                "source_transactions": "available-parameter+registered-structural",
                "structural_transforms": sorted(TRANSFORM_REGISTRY),
                "agent_proposal": "available-no-execution-permissions",
                "pattern_packs": "available-declarative+builtin+locked-workspace+candidate-preview",
            },
            "runtime_packages": runtime_packages,
            "framework_adapters": [
                item.model_dump(mode="json") for item in adapter_capabilities()
            ],
            "release_support": release_support_matrix().model_dump(mode="json"),
        },
    )


def analyze(args: argparse.Namespace) -> CommandReceipt:
    project = args.project.resolve()
    config_bytes = args.config.read_bytes() if args.config else b"{}"
    bundle = analyze_with_adapter(
        project,
        args.entry,
        args.task,
        args.mode,
        config_bytes,
        args.config,
        framework=args.framework,
        pattern_packs_enabled=not args.no_pattern_packs,
    )
    gates, diagnostics = validate_architecture(
        bundle.architecture,
        bundle.evidence,
        bundle.snapshot,
    )
    out = args.out.resolve()
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
        "pattern_candidate_review": str(out / "pattern-candidate-review.json"),
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
    registry = load_registry(
        workspace_paths=args.pattern_workspace,
        workspace_locks=args.pattern_lock,
        candidate_paths=args.pattern_candidate,
    )
    semantic_overlay, pattern_receipt = apply_pattern_packs(
        bundle.architecture,
        registry,
        enabled=not args.no_pattern_packs,
    )
    candidate_reviews = build_candidate_reviews(bundle.architecture, registry)
    profile = "generic"
    if bundle.architecture.framework == "pytorch" and not args.no_pattern_packs:
        profile = bundle.snapshot.resolved_config.get("architecture_profile") or next(
            (
                str(node.attributes["architecture_profile"])
                for node in bundle.architecture.nodes
                if node.attributes.get("architecture_profile") not in {None, "generic"}
            ),
            "generic",
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
            "adapter": f"{bundle.architecture.framework}-static-{profile}",
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
            "semantic_transforms": ["set_parameter", *sorted(TRANSFORM_REGISTRY)],
        },
    )
    _write_json(Path(artifacts["semantic_overlay"]), semantic_overlay)
    _write_json(Path(artifacts["pattern_receipt"]), pattern_receipt)
    _write_json(Path(artifacts["pattern_candidate_review"]), candidate_reviews)
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
            "framework": bundle.architecture.framework,
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
            "framework": bundle.architecture.framework,
            "profile": profile,
            "pattern_packs_enabled": not args.no_pattern_packs,
            "pattern_status": pattern_receipt.status,
            "selected_pattern_packs": pattern_receipt.selected_pack_ids,
            "candidate_pattern_packs": [
                match.pack_id
                for match in pattern_receipt.matches
                if match.status == "candidate-match"
            ],
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
        views = compile_views(ir, _semantic_overlay(args.artifact, ir))
        publication_gates, publication_diagnostics = validate_publication(ir, views)
        gates.extend(publication_gates)
        diagnostics.extend(publication_diagnostics)
        for view in views:
            spec = build_visual_spec(view)
            scene = build_scene(view, spec)
            geometry_gate, geometry_diagnostics = validate_geometry(scene)
            gates.append(
                geometry_gate.model_copy(
                    update={"gate": f"D-geometry-{view.frontier_digest[:12]}"}
                )
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


def render(args: argparse.Namespace) -> CommandReceipt:
    ir = ArchitectureIR.model_validate_json(args.artifact.read_text(encoding="utf-8"))
    overlay = _semantic_overlay(args.artifact, ir)
    views = compile_views(ir, overlay)
    publication_gates, diagnostics = validate_publication(ir, views)
    selected = views if args.view == "all" else [views[-1 if args.view == "full" else 0]]
    compiled: list[tuple[Any, Any, Any]] = []
    geometry_gates: list[GateResult] = []
    for view in selected:
        spec = build_visual_spec(view)
        scene = build_scene(view, spec)
        geometry_gate, geometry_diagnostics = validate_geometry(scene)
        geometry_gates.append(
            geometry_gate.model_copy(
                update={
                    "gate": (
                        f"D-geometry-{view.frontier_digest[:12]}"
                        if args.view == "all"
                        else "D-geometry"
                    )
                }
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
        projection_name = "full" if view.fully_expanded else "collapsed"
        target = out / projection_name if args.view == "all" else out
        paths = {
            "publication_view": target / "publication-view.json",
            "visual_spec": target / "visual-spec.json",
            "visual_scene": target / "visual-scene.json",
            "svg": target / "scene.svg",
            "html": target / "view.html",
            "png": target / "scene.png",
            "pdf": target / "scene.pdf",
        }
        prefix = f"{projection_name}_" if args.view == "all" else ""
        artifacts.update({f"{prefix}{key}": str(path) for key, path in paths.items()})
        _write_json(paths["publication_view"], view)
        _write_json(paths["visual_spec"], spec)
        _write_json(paths["visual_scene"], scene)
        _write_text(paths["svg"], render_svg(scene))
        _write_text(paths["html"], render_html(scene, view, spec))
        _write_bytes(paths["png"], render_png(scene))
        _write_bytes(paths["pdf"], render_pdf(scene))
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
            "projections": [view.projection_id for view, _, _ in compiled],
            "layout_families": {
                view.projection_id: view.layout_family for view, _, _ in compiled
            },
            "canonical_surface": "svg",
            "html_self_contained": True,
            "png": "available",
            "pdf": "available",
            "runtime_evidence": "skipped",
            "visual_review": "skipped",
            "semantic_overlay": overlay.status if overlay is not None else "not-present",
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
    for projection_id, scene in bundle.materialized_scenes().items():
        gate, scene_diagnostics = validate_geometry(scene)
        gates.append(gate.model_copy(update={"gate": f"D-geometry-{projection_id}"}))
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
            "source_editing": "available-registered-transaction",
            "structural_transforms": sorted(TRANSFORM_REGISTRY),
            "agent_proposal": "available-no-execution-permissions",
        },
    )
    return receipt, bundle


def trace(args: argparse.Namespace) -> CommandReceipt:
    return trace_runtime(args.artifact, args.input_spec, args.out)


def bundle_command(args: argparse.Namespace) -> CommandReceipt:
    if args.bundle_command == "create":
        manifest, passed_gates = create_bundle(args.artifact, args.out)
        return CommandReceipt(
            command="bundle create",
            status="ok",
            exit_code=0,
            artifacts={
                "bundle": str(args.out.resolve()),
                "manifest": str(args.out.resolve() / "bundle-manifest.json"),
            },
            details={
                "bundle_id": manifest.bundle_id,
                "file_count": len(manifest.files),
                "network_required": False,
                "source_execution": False,
                "absolute_paths_redacted": manifest.absolute_paths_redacted,
                "passed_gates": passed_gates,
            },
        )
    manifest = verify_bundle(args.bundle)
    return CommandReceipt(
        command="bundle verify",
        status="ok",
        exit_code=0,
        artifacts={"bundle": str(args.bundle.resolve())},
        details={
            "bundle_id": manifest.bundle_id,
            "file_count": len(manifest.files),
            "digest_verified": True,
            "network_required": False,
        },
    )


def install_skill_command(args: argparse.Namespace) -> CommandReceipt:
    details = install_skill(args.project, args.host, args.mode)
    return CommandReceipt(
        command="install-skill",
        status="ok",
        exit_code=0,
        artifacts={"skill": str(details["target"])},
        details={**details, "project_writes": True},
    )


def patch(args: argparse.Namespace) -> CommandReceipt:
    if args.patch_command == "prepare":
        payload = json.loads(args.request.read_text(encoding="utf-8"))
        operation = payload.get("operation") if isinstance(payload, dict) else None
        if operation == "set_parameter":
            request = SemanticParameterPatch.model_validate(payload)
        else:
            request = SemanticStructuralPatch.model_validate(payload)
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


def propose(args: argparse.Namespace) -> CommandReceipt:
    payload = json.loads(args.request.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("proposal request must be a JSON object")
    if payload.get("kind") == "proposed_connection":
        request = ProposedConnection.model_validate(payload)
        architecture = ArchitectureIR.model_validate_json(
            Path(request.artifact_path).read_text(encoding="utf-8")
        )
        proposal = plan_connection(request, architecture)
    else:
        proposal = unsupported_intent_proposal(payload)
    output = args.out.resolve()
    _write_json(output, proposal)
    return CommandReceipt(
        command="propose",
        status="ok",
        exit_code=0,
        artifacts={"agent_proposal": str(output)},
        gates=[
            GateResult(
                gate="F-proposal-boundary",
                status="passed",
                message="Unsupported structural intent was routed to a no-permission handoff.",
            )
        ],
        details={
            "proposal_id": proposal.proposal_id,
            "reason_code": proposal.reason_code,
            "permissions": proposal.permissions,
            "source_writes": False,
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
    analyze_parser.add_argument(
        "--framework",
        choices=("pytorch", "keras", "jax", "onnx", "python", "auto"),
        default="pytorch",
    )
    analyze_parser.add_argument("--config", type=Path)
    analyze_parser.add_argument("--task", required=True)
    analyze_parser.add_argument("--mode", choices=("eval", "train"), required=True)
    analyze_parser.add_argument("--out", type=Path, required=True)
    analyze_parser.add_argument("--no-pattern-packs", action="store_true")
    analyze_parser.add_argument("--pattern-workspace", type=Path, action="append", default=[])
    analyze_parser.add_argument("--pattern-lock", action="append", default=[])
    analyze_parser.add_argument("--pattern-candidate", type=Path, action="append", default=[])
    analyze_parser.add_argument("--json", action="store_true")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("artifact", type=Path)
    validate_parser.add_argument("--quality", choices=("semantic", "publication"), default="semantic")
    validate_parser.add_argument("--json", action="store_true")
    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("artifact", type=Path)
    render_parser.add_argument(
        "--view",
        choices=("collapsed", "full", "all"),
        default="collapsed",
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
    propose_parser = subparsers.add_parser("propose")
    propose_parser.add_argument("request", type=Path)
    propose_parser.add_argument("--out", type=Path, required=True)
    propose_parser.add_argument("--json", action="store_true")
    bundle_parser = subparsers.add_parser("bundle")
    bundle_subparsers = bundle_parser.add_subparsers(dest="bundle_command", required=True)
    bundle_create_parser = bundle_subparsers.add_parser("create")
    bundle_create_parser.add_argument("artifact", type=Path)
    bundle_create_parser.add_argument("--out", type=Path, required=True)
    bundle_create_parser.add_argument("--json", action="store_true")
    bundle_verify_parser = bundle_subparsers.add_parser("verify")
    bundle_verify_parser.add_argument("bundle", type=Path)
    bundle_verify_parser.add_argument("--json", action="store_true")
    install_parser = subparsers.add_parser("install-skill")
    install_parser.add_argument("--project", type=Path, required=True)
    install_parser.add_argument("--host", choices=("codex", "claude-code"), required=True)
    install_parser.add_argument("--mode", choices=("copy", "symlink"), default="copy")
    install_parser.add_argument("--json", action="store_true")
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
        elif args.command == "propose":
            receipt = propose(args)
        elif args.command == "bundle":
            receipt = bundle_command(args)
        elif args.command == "install-skill":
            receipt = install_skill_command(args)
        else:
            receipt = _unavailable(args.command, args.command)
        return _emit(receipt)
    except AnalysisError as error:
        return _emit(_invalid(args.command, error.code, str(error)))
    except RuntimeTraceError as error:
        return _emit(_invalid(args.command, "RUNTIME_REQUEST_INVALID", str(error)))
    except (OSError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as error:
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
