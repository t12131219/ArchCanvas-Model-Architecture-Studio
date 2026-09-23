from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
import tempfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from archcanvas_core.models import ArchitectureIR, CommandReceipt, Diagnostic, GateResult, SCHEMA_MODELS
from archcanvas_core.validation import validate_architecture
from archcanvas_python import AnalysisError, analyze_project

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
    print(_compact(receipt))
    return receipt.exit_code


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _compact(value) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(data)
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
    missing_schemas = [filename for filename in SCHEMA_MODELS if not (schema_dir / filename).is_file()]
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
    status = "invalid" if diagnostics else "ok"
    return CommandReceipt(
        command="doctor",
        status=status,
        exit_code=2 if diagnostics else 0,
        gates=[
            GateResult(
                gate="A-environment",
                status="failed" if diagnostics else "passed",
                message="Required local protocol dependencies and schemas are present." if not diagnostics else "Environment is incomplete.",
            )
        ],
        diagnostics=diagnostics,
        details={
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": packages,
            "network_required": False,
            "capabilities": {
                "static_analysis": "available-initial-subset",
                "semantic_validation": "available",
                "publication_render": "unavailable",
                "studio": "unavailable",
                "runtime_trace": "unavailable",
                "source_transactions": "unavailable",
            },
        },
    )


def analyze(args: argparse.Namespace) -> CommandReceipt:
    project = args.project.resolve()
    config_bytes = args.config.read_bytes() if args.config else b"{}"
    bundle = analyze_project(project, args.entry, args.task, args.mode, config_bytes)
    gates, diagnostics = validate_architecture(bundle.architecture)
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
    _write_json(Path(artifacts["discrepancy_ledger"]), [])
    _write_json(Path(artifacts["omission_ledger"]), bundle.architecture.unresolved)
    _write_json(
        Path(artifacts["capability_report"]),
        {
            "schema_version": "1.0",
            "adapter": "python-ast-pytorch-initial-subset",
            "static_analysis": True,
            "runtime_evidence": False,
            "semantic_transforms": [],
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
            "node_count": len(bundle.architecture.nodes),
            "tensor_count": len(bundle.architecture.tensors),
            "edge_count": len(bundle.architecture.edges),
            "unresolved_count": len(bundle.architecture.unresolved),
        },
    )
    _write_json(out / "analysis-receipt.json", receipt)
    return receipt


def validate(args: argparse.Namespace) -> CommandReceipt:
    raw = args.artifact.read_text(encoding="utf-8")
    ir = ArchitectureIR.model_validate_json(raw)
    gates, diagnostics = validate_architecture(ir)
    failed = any(gate.status == "failed" for gate in gates)
    return CommandReceipt(
        command="validate",
        status="invalid" if failed else "ok",
        exit_code=2 if failed else 0,
        artifacts={"architecture": str(args.artifact.resolve())},
        gates=gates,
        diagnostics=diagnostics,
        details={"quality": args.quality, "publication_gates_available": False},
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
    analyze_parser.add_argument("--json", action="store_true")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("artifact", type=Path)
    validate_parser.add_argument("--quality", default="semantic")
    validate_parser.add_argument("--json", action="store_true")
    for command in ("render", "studio", "patch"):
        unavailable = subparsers.add_parser(command)
        unavailable.add_argument("arguments", nargs="*")
        unavailable.add_argument("--json", action="store_true")
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
        else:
            receipt = _unavailable(args.command, args.command)
        return _emit(receipt)
    except AnalysisError as error:
        return _emit(_invalid(args.command, error.code, str(error)))
    except (OSError, ValidationError, ValueError, json.JSONDecodeError) as error:
        return _emit(_invalid(args.command, "INPUT_INVALID", str(error)))
    except Exception as error:  # pragma: no cover - final receipt boundary
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
