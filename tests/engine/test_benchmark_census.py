from __future__ import annotations

import json
from pathlib import Path

import pytest

from archcanvas_engine.benchmark_census import BenchmarkCensusBuilder
from archcanvas_engine.benchmark_registry import BenchmarkEntrypointRegistry
from tools.generate_benchmark_census import main


def _write_index(root: Path) -> None:
    (root / "pytorch" / "models").mkdir(parents=True)
    (root / "pytorch" / "models" / "model.py").write_text(
        "import torch.nn as nn\n\n"
        "class Projection(nn.Module):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self.linear = nn.Linear(2, 2)\n\n"
        "    def forward(self, value):\n"
        "        return self.linear(value)\n",
        encoding="utf-8",
    )
    (root / "BENCHMARK_MODEL_INDEX.md").write_text(
        "# Benchmark Model Index\n\n"
        "## 01 - Static\n\n"
        "- `benchmark`: `Static benchmark`\n"
        "- `status`: `local_model`\n"
        "- `benchmark_path`: `pytorch`\n"
        "- `model_path`: `pytorch/models`\n\n"
        "## 02 - API\n\n"
        "- `benchmark`: `API benchmark`\n"
        "- `status`: `benchmark_only`\n"
        "- `benchmark_path`: `.`\n"
        "- `model_path`: `null`\n",
        encoding="utf-8",
    )


def test_census_keeps_all_catalog_records_and_requires_explicit_adapter_scope(tmp_path: Path) -> None:
    _write_index(tmp_path)

    report = BenchmarkCensusBuilder().build(tmp_path).as_dict()

    assert report["record_count"] == 2
    assert report["l1_status_counts"] == {"no_local_model": 1, "unsupported": 1}
    assert report["records"][0]["unresolved_codes"] == ["SOURCE_CENSUS_ADAPTER_NOT_APPROVED"]
    assert report["records"][1]["l1_status"] == "no_local_model"


def test_census_wraps_explicit_pytorch_scan_with_relative_root_only(tmp_path: Path) -> None:
    _write_index(tmp_path)

    report = BenchmarkCensusBuilder().build(
        tmp_path,
        pytorch_projects={"01": "pytorch/models"},
    ).as_dict()

    record = report["records"][0]
    assert record["l1_status"] == "supported"
    assert record["relative_source_root"] == "pytorch/models"
    assert record["entrypoint_count"] == 1
    assert record["source_files_unchanged"] is True
    assert record["pytorch_census"]["approved_root"] == "."
    assert str(tmp_path) not in json.dumps(report)


def test_census_requires_registry_entries_to_be_discovered(tmp_path: Path) -> None:
    _write_index(tmp_path)
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        '{"schema_version":"1.0","benchmark_id":"01","entries":['
        '{"relative_file":"model.py","symbol":"Missing",'
        '"entrypoint_role":"model","discovery_basis":"manual_seed"}]}',
        encoding="utf-8",
    )
    registry = BenchmarkEntrypointRegistry.load(registry_path, benchmark_id="01")

    report = BenchmarkCensusBuilder().build(
        tmp_path,
        pytorch_projects={"01": "pytorch/models"},
        pytorch_registries={"01": registry},
    ).as_dict()

    record = report["records"][0]
    assert record["l1_status"] == "unresolved"
    assert record["registry_entrypoint_count"] == 1
    assert record["registry_unresolved_codes"] == [
        "model.py:Missing:REGISTRY_ENTRYPOINT_NOT_DISCOVERED",
    ]


def test_census_rejects_unknown_or_outside_pytorch_project_selection(tmp_path: Path) -> None:
    _write_index(tmp_path)

    with pytest.raises(ValueError, match="unknown benchmark"):
        BenchmarkCensusBuilder().build(tmp_path, pytorch_projects={"99": "pytorch/models"})
    with pytest.raises(ValueError, match="approved benchmark root"):
        BenchmarkCensusBuilder().build(tmp_path, pytorch_projects={"01": "../outside"})

    (tmp_path / "other").mkdir()
    with pytest.raises(ValueError, match="approved benchmark root"):
        BenchmarkCensusBuilder().build(tmp_path, pytorch_projects={"01": "other"})


def test_census_tool_keeps_output_outside_benchmark_root(tmp_path: Path) -> None:
    _write_index(tmp_path)
    output = tmp_path.parent / "benchmark-census.json"

    assert main([str(tmp_path), "--output", str(output), "--pytorch-project", "01:pytorch/models"]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["record_count"] == 2
    with pytest.raises(ValueError, match="must not be written under"):
        main([str(tmp_path), "--output", str(tmp_path / "benchmark-census.json")])
