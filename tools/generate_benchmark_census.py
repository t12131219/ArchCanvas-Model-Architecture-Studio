"""Generate a generic, read-only Benchmark Model Reference L0/L1 ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from archcanvas_engine.benchmark_census import BenchmarkCensusBuilder
from archcanvas_engine.benchmark_registry import BenchmarkEntrypointRegistry


def _selection(raw: str) -> tuple[str, str]:
    benchmark_id, separator, relative_path = raw.partition(":")
    if not separator or not benchmark_id.isdigit() or len(benchmark_id) != 2 or not relative_path:
        raise argparse.ArgumentTypeError("selection must use BENCHMARK_ID:relative/path")
    return benchmark_id, relative_path


def _config_selection(raw: str) -> tuple[str, Path]:
    benchmark_id, relative_path = _selection(raw)
    return benchmark_id, Path(relative_path)


def _load_configs(path: Path) -> dict[str, dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not all(
        isinstance(entrypoint, str) and isinstance(config, dict)
        for entrypoint, config in payload.items()
    ):
        raise ValueError("resolved config file must be a JSON object of entrypoint-to-object mappings")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark_root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--pytorch-project",
        action="append",
        default=[],
        type=_selection,
        metavar="ID:RELATIVE_PATH",
        help="explicitly approve one catalog record for the existing static PyTorch L1 adapter",
    )
    parser.add_argument(
        "--pytorch-entrypoint-registry-file",
        action="append",
        default=[],
        type=_config_selection,
        metavar="ID:FILE",
        help="optional reviewed entrypoint registry for one selected PyTorch project",
    )
    parser.add_argument(
        "--pytorch-resolved-config-file",
        action="append",
        default=[],
        type=_config_selection,
        metavar="ID:FILE",
        help="optional immutable config map for one selected PyTorch project",
    )
    arguments = parser.parse_args(argv)

    root = arguments.benchmark_root.resolve(strict=True)
    output = arguments.output.resolve()
    if output.is_relative_to(root):
        raise ValueError("output must not be written under the approved benchmark root")
    projects = dict(arguments.pytorch_project)
    config_files = dict(arguments.pytorch_resolved_config_file)
    registry_files = dict(arguments.pytorch_entrypoint_registry_file)
    report = BenchmarkCensusBuilder().build(
        root,
        pytorch_projects=projects,
        pytorch_configs={benchmark_id: _load_configs(path) for benchmark_id, path in config_files.items()},
        pytorch_registries={
            benchmark_id: BenchmarkEntrypointRegistry.load(path, benchmark_id=benchmark_id)
            for benchmark_id, path in registry_files.items()
        },
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
