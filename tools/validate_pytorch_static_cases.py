"""Create a reproducible, read-only Stage 2 observation for selected PyTorch entrypoints.

The caller supplies the approved root and each entrypoint. This tool never imports project code,
installs dependencies, changes ``sys.path``, or writes under the inspected root.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from archcanvas_pytorch.static import PyTorchProjectScanner, PyTorchProjectStaticAdapter


def _case_report(
    root: Path,
    entrypoint: str,
    *,
    project_id: str,
    scanner: PyTorchProjectScanner,
    discovered: set[tuple[str, str]],
) -> dict[str, Any]:
    try:
        relative_file, model_class = entrypoint.split(":", maxsplit=1)
    except ValueError:
        return {
            "entrypoint": entrypoint,
            "status": "invalid_entrypoint",
            "message": "entrypoint must use relative_file.py:ClassName",
            "acceptance": "A1_FAIL",
        }
    if (relative_file, model_class) not in discovered:
        return {
            "entrypoint": entrypoint,
            "status": "not_discovered",
            "message": "entrypoint was not found by the bounded project scan",
            "acceptance": "A1_FAIL",
        }

    try:
        symbols = scanner.build_symbol_table(root)
        resolution = symbols.resolve_entrypoint(entrypoint)
        source, ir = PyTorchProjectStaticAdapter(project_scanner=scanner).analyze(
            root,
            project_id=project_id,
            entrypoint=entrypoint,
        )
    except (OSError, SyntaxError, UnicodeDecodeError, ValueError) as error:
        return {
            "entrypoint": entrypoint,
            "status": "static_analysis_error",
            "message": str(error),
            "acceptance": "A1_PASS_CAPABILITY_BOUNDARY",
        }

    return {
        "entrypoint": entrypoint,
        "status": "observed",
        "acceptance": "A1_PASS_CAPABILITY_BOUNDARY",
        "source_revision": source.source_revision,
        "file_revisions": source.file_revisions,
        "direct_local_bindings": resolution.as_dict()["local_module_bindings"],
        "symbol_issues": resolution.as_dict()["issues"],
        "node_count": len(ir.nodes),
        "edge_count": len(ir.edges),
        "node_kinds": dict(sorted(Counter(node.kind.value for node in ir.nodes).items())),
        "unresolved": [item.model_dump(mode="json") for item in ir.unresolved],
        "transitive_local_call_evidence": ir.metadata.get("transitive_local_call_evidence", []),
        "a2_status": "NOT_ASSESSED_STAGE2_ONLY",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument(
        "--entrypoint",
        action="append",
        required=True,
        help="selected relative_file.py:ClassName; repeat for multiple cases",
    )
    parser.add_argument("--project-id", default="project:external-static-observation")
    parser.add_argument("--max-file-bytes", type=int, default=1_000_000)
    parser.add_argument(
        "--provenance-status",
        choices=("complete", "incomplete", "unknown"),
        default="unknown",
        help="caller-recorded provenance state; this tool does not infer it from local files",
    )
    parser.add_argument("--output", type=Path, help="optional report path outside the inspected root")
    arguments = parser.parse_args(argv)

    root = arguments.project_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("project_root must be a directory")
    scanner = PyTorchProjectScanner(max_file_bytes=arguments.max_file_bytes)
    scan = scanner.scan(root)
    discovered = {(item.relative_file, item.model_class) for item in scan.entrypoints}
    report = {
        "report_kind": "pytorch-static-stage-2-observation-v1",
        "execution": {
            "read_only": True,
            "source_imported": False,
            "source_executed": False,
            "dependencies_installed": False,
            "sys_path_modified": False,
        },
        "approved_root": str(root),
        "provenance_status": arguments.provenance_status,
        "project_scan": {
            "python_files_scanned": scan.python_files_scanned,
            "entrypoint_count": len(scan.entrypoints),
            "issues": [
                {"relative_file": item.relative_file, "code": item.code, "message": item.message}
                for item in scan.issues
            ],
        },
        "cases": [
            _case_report(
                root,
                entrypoint,
                project_id=arguments.project_id,
                scanner=scanner,
                discovered=discovered,
            )
            for entrypoint in arguments.entrypoint
        ],
        "stage_boundary": (
            "This is an A1 capability observation. It does not claim A0 provenance approval, "
            "A2 Exact IR acceptance, visualization, runtime trace, or source editing."
        ),
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if arguments.output is not None:
        output = arguments.output.resolve()
        if output.is_relative_to(root):
            raise ValueError("output must not be written under the inspected project root")
        output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
