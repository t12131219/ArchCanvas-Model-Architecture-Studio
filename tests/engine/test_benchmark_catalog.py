from __future__ import annotations

import json
from pathlib import Path

import pytest

from archcanvas_engine.benchmark_catalog import BenchmarkCatalogBuilder
from tools.generate_benchmark_catalog import main


def _write_index(root: Path, *, model_path: str = "models") -> None:
    (root / "models").mkdir(exist_ok=True)
    (root / "BENCHMARK_MODEL_INDEX.md").write_text(
        "# Benchmark Model Index\n\n"
        "## 01 - Local\n\n"
        "- `benchmark`: `Local benchmark`\n"
        "- `status`: `local_model`\n"
        "- `benchmark_path`: `.`\n"
        f"- `model_path`: `{model_path}`\n"
        "- `representative_models`: `Projection`; `Encoder`\n"
        "- `notes`: local regression fixture\n\n"
        "## 02 - API\n\n"
        "- `benchmark`: `API benchmark`\n"
        "- `status`: `benchmark_only`\n"
        "- `benchmark_path`: `.`\n"
        "- `model_path`: `null`\n",
        encoding="utf-8",
    )


def test_catalog_normalizes_paths_and_retains_benchmark_only_records(tmp_path: Path) -> None:
    _write_index(tmp_path)

    report = BenchmarkCatalogBuilder().build(tmp_path)
    payload = report.as_dict()

    assert payload["approved_benchmark_root"] == "."
    assert payload["record_count"] == 2
    assert payload["records"] == [
        {
            "benchmark_id": "01",
            "benchmark": "Local benchmark",
            "status": "local_model",
            "relative_benchmark_path": ".",
            "relative_model_paths": ["models"],
            "relative_config_paths": [],
            "representative_models": ["Projection", "Encoder"],
            "notes": "local regression fixture",
            "catalog_status": "ready_for_source_census",
            "issues": [],
            "source_files_unchanged": True,
        },
        {
            "benchmark_id": "02",
            "benchmark": "API benchmark",
            "status": "benchmark_only",
            "relative_benchmark_path": ".",
            "relative_model_paths": [],
            "relative_config_paths": [],
            "representative_models": [],
            "notes": None,
            "catalog_status": "no_local_model",
            "issues": [],
            "source_files_unchanged": True,
        },
    ]


def test_catalog_blocks_missing_or_outside_paths_without_omitting_the_record(tmp_path: Path) -> None:
    _write_index(tmp_path, model_path="/outside-root/models")

    record = BenchmarkCatalogBuilder().build(tmp_path).records[0]

    assert record.catalog_status == "blocked"
    assert record.relative_model_paths == []
    assert record.issues == ["MISSING_MODEL_PATH", "MODEL_PATH_OUTSIDE_APPROVED_ROOT"]


def test_catalog_tool_writes_only_outside_the_approved_root(tmp_path: Path) -> None:
    _write_index(tmp_path)
    output = tmp_path.parent / "benchmark-catalog.json"

    assert main([str(tmp_path), "--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["record_count"] == 2

    with pytest.raises(ValueError, match="must not be written under"):
        main([str(tmp_path), "--output", str(tmp_path / "catalog.json")])
