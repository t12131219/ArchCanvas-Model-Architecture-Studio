from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from archcanvas_core.models.architecture import ArchitectureIR
from archcanvas_core.models.patch import PatchSet
from archcanvas_core.models.source_identity import SourceIdentityDocument
from archcanvas_core.schema_registry import SchemaRegistry

from .analyzers import AnalyzerUnavailable, fixture_analyzer_registry
from .transactions.set_parameter import TransactionRejected, commit_candidate, plan_set_parameter


def _load_fixture_documents(fixture_dir: Path) -> tuple[PatchSet, SourceIdentityDocument, ArchitectureIR]:
    root = Path(__file__).resolve().parents[2]
    registry = SchemaRegistry(root / "schemas")
    patch_raw = (fixture_dir / "request.patch.json").read_bytes()
    source_raw = (fixture_dir / "expected" / "source-identity.before.json").read_bytes()
    ir_raw = (fixture_dir / "expected" / "architecture.before.json").read_bytes()
    registry.load_and_validate("patch-protocol-v1.schema.json", patch_raw)
    registry.load_and_validate("source-identity-v1.schema.json", source_raw)
    registry.load_and_validate("architecture-ir-v1.schema.json", ir_raw)
    return (
        PatchSet.model_validate_json(patch_raw),
        SourceIdentityDocument.model_validate_json(source_raw),
        ArchitectureIR.model_validate_json(ir_raw),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Stage 1 Transformer fixture transaction.")
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--source-file", type=Path, required=True)
    parser.add_argument("--commit", action="store_true", help="Atomically replace source after validation.")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        patch_set, source, ir = _load_fixture_documents(arguments.fixture_dir)
        analyzer = fixture_analyzer_registry().resolve(patch_set.project_id)
        candidate = plan_set_parameter(arguments.source_file.read_bytes(), patch_set, source, ir, analyzer)
        result = {
            "status": "candidate",
            "committed": False,
            "blocking": candidate.blocking,
            "diff": candidate.diff,
            "observed_delta": candidate.observed_delta.model_dump(mode="json"),
            "validation": candidate.validation.model_dump(mode="json"),
        }
        if arguments.commit:
            result["source_revision"] = commit_candidate(arguments.source_file, candidate)
            result["committed"] = True
            result["status"] = "committed"
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, TransactionRejected, AnalyzerUnavailable, ValueError) as error:
        code = error.code if isinstance(error, TransactionRejected) else "TRANSACTION_INPUT_ERROR"
        print(json.dumps({"status": "rejected", "code": code, "message": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
