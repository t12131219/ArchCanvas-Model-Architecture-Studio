from __future__ import annotations

import json
from pathlib import Path

import pytest

from archcanvas_engine.benchmark_registry import BenchmarkEntrypointRegistry


def _write_registry(path: Path, *, relative_file: str = "model.py") -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "benchmark_id": "01",
                "entries": [
                    {
                        "relative_file": relative_file,
                        "symbol": "Projection",
                        "entrypoint_role": "model",
                        "discovery_basis": "static_nn_module",
                        "source_anchor": {"line": 1},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_registry_requires_relative_source_and_reports_source_scope(tmp_path: Path) -> None:
    source_root = tmp_path / "project"
    source_root.mkdir()
    (source_root / "model.py").write_text("class Projection: pass\n", encoding="utf-8")
    registry_path = tmp_path / "registry.json"
    _write_registry(registry_path)

    registry = BenchmarkEntrypointRegistry.load(registry_path, benchmark_id="01")

    assert registry.entries[0].entrypoint == "model.py:Projection"
    assert registry.validate_source_root(source_root) == []
    assert registry.as_dict()["registry_revision"].startswith("sha256:")


def test_registry_rejects_absolute_and_unsupported_entries(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    _write_registry(registry_path, relative_file="/outside.py")
    with pytest.raises(ValueError, match="normalized and remain relative"):
        BenchmarkEntrypointRegistry.load(registry_path, benchmark_id="01")

    _write_registry(registry_path)
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    payload["entries"][0]["discovery_basis"] = "import_execution"
    registry_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported registry discovery_basis"):
        BenchmarkEntrypointRegistry.load(registry_path, benchmark_id="01")
