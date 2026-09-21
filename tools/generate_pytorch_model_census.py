"""Generate a complete, read-only census for every discovered PyTorch model entrypoint."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path

from archcanvas_pytorch.static import PyTorchModelCensus


def _load_configs(path: Path | None) -> dict[str, Mapping[str, object]]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not all(
        isinstance(entrypoint, str) and isinstance(config, dict)
        for entrypoint, config in payload.items()
    ):
        raise ValueError("resolved config file must be a JSON object of entrypoint-to-object mappings")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--project-id", default="project:pytorch-model-census")
    parser.add_argument("--resolved-config-file", type=Path)
    parser.add_argument("--output", type=Path, help="optional report path outside the inspected root")
    parser.add_argument(
        "--assess-publication",
        action="store_true",
        help="compile static-supported entries into read-only Publication/SVG preflight evidence",
    )
    parser.add_argument(
        "--publication-artifact-root",
        type=Path,
        help="optional external directory for per-entrypoint publication evidence files",
    )
    parser.add_argument("--quiet", action="store_true", help="write only the optional output file")
    arguments = parser.parse_args(argv)

    root = arguments.project_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("project_root must be a directory")
    report = PyTorchModelCensus().build(
        root,
        project_id=arguments.project_id,
        resolved_configs=_load_configs(arguments.resolved_config_file),
        assess_publication=arguments.assess_publication,
        publication_artifact_root=arguments.publication_artifact_root,
    )
    payload = json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if arguments.output is not None:
        output = arguments.output.resolve()
        if output.is_relative_to(root):
            raise ValueError("output must not be written under the inspected project root")
        output.write_text(payload, encoding="utf-8")
    if not arguments.quiet:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
