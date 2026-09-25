from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from archcanvas_adapters import analyze_with_adapter
from archcanvas_core.validation import validate_architecture
from archcanvas_python import AnalysisError
from archcanvas_studio.project import discover_project


def probe(project: Path, *, include_components: bool, pattern_packs_enabled: bool) -> dict[str, Any]:
    root = project.resolve()
    discovery = discover_project(root)
    candidates = [
        item
        for item in discovery["entrypoints"]
        if include_components or item["top_level"]
    ]
    outcomes: Counter[str] = Counter()
    failures: list[dict[str, str]] = []
    unresolved: Counter[str] = Counter()
    for item in candidates:
        analysis_root = root / item["analysis_root"]
        try:
            bundle = analyze_with_adapter(
                analysis_root,
                item["analysis_entrypoint"],
                "inference",
                "eval",
                b"{}",
                None,
                framework="auto",
                pattern_packs_enabled=pattern_packs_enabled,
            )
            _, diagnostics = validate_architecture(
                bundle.architecture,
                bundle.evidence,
                bundle.snapshot,
            )
            blocking = [diagnostic for diagnostic in diagnostics if diagnostic.severity == "blocking"]
            if blocking:
                code = blocking[0].code
                outcomes[f"invalid:{code}"] += 1
                failures.append(
                    {
                        "entrypoint": item["entrypoint"],
                        "code": code,
                        "message": blocking[0].message,
                    }
                )
                continue
            outcomes["ok"] += 1
            unresolved.update(fact.code for fact in bundle.architecture.unresolved)
        except AnalysisError as error:
            outcomes[f"analysis-error:{error.code}"] += 1
            failures.append(
                {
                    "entrypoint": item["entrypoint"],
                    "code": error.code,
                    "message": str(error),
                }
            )
        except (OSError, TypeError, ValueError, ValidationError) as error:
            code = type(error).__name__
            outcomes[f"input-error:{code}"] += 1
            failures.append(
                {
                    "entrypoint": item["entrypoint"],
                    "code": code,
                    "message": str(error),
                }
            )
        except Exception as error:  # noqa: BLE001 - mirrors the CLI receipt boundary
            code = type(error).__name__
            outcomes[f"internal-error:{code}"] += 1
            failures.append(
                {
                    "entrypoint": item["entrypoint"],
                    "code": code,
                    "message": str(error),
                }
            )
    return {
        "schema_version": "1.0",
        "project": str(root),
        "source_execution": False,
        "selection": "all" if include_components else "top-level",
        "candidate_count": len(candidates),
        "outcomes": dict(sorted(outcomes.items())),
        "unresolved": dict(sorted(unresolved.items())),
        "failures": failures,
        "discovery_warning_count": len(discovery["warnings"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe static model adaptation without executing source.")
    parser.add_argument("project", type=Path)
    parser.add_argument("--include-components", action="store_true")
    parser.add_argument("--no-pattern-packs", action="store_true")
    args = parser.parse_args()
    report = probe(
        args.project,
        include_components=args.include_components,
        pattern_packs_enabled=not args.no_pattern_packs,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
