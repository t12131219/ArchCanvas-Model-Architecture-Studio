from __future__ import annotations

import json
from pathlib import Path

import pytest

from archcanvas_pytorch.static import PyTorchModelCensus
from tools.generate_pytorch_model_census import main


def _write_project(root: Path) -> None:
    (root / "stable.py").write_text(
        "import torch.nn as nn\n\n"
        "class Stable(nn.Module):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self.proj = nn.Linear(2, 2)\n\n"
        "    def forward(self, x):\n"
        "        return self.proj(x)\n",
        encoding="utf-8",
    )
    (root / "task.py").write_text(
        "import torch.nn as nn\n\n"
        "class TaskModel(nn.Module):\n"
        "    def __init__(self, configs):\n"
        "        super().__init__()\n"
        "        self.task_name = configs.task_name\n"
        "        if self.task_name == 'forecast':\n"
        "            self.head = nn.Linear(2, 1)\n\n"
        "    def forecast(self, x):\n"
        "        return self.head(x)\n\n"
        "    def forward(self, x):\n"
        "        if self.task_name == 'forecast':\n"
        "            return self.forecast(x)\n"
        "        return x\n",
        encoding="utf-8",
    )
    (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")


def test_census_accounts_for_every_discovered_entrypoint_and_unresolved_case(tmp_path: Path) -> None:
    _write_project(tmp_path)

    report = PyTorchModelCensus().build(tmp_path, project_id="project:census")
    payload = report.as_dict()

    assert payload["discovered_entrypoint_count"] == 2
    assert payload["assessed_entrypoint_count"] == 2
    assert payload["explicit_alias_count"] == 0
    assert payload["status_counts"] == {"supported": 1, "unresolved": 1}
    assert [(item.entrypoint, item.status) for item in report.items] == [
        ("stable.py:Stable", "supported"),
        ("task.py:TaskModel", "unresolved"),
    ]
    task = report.items[1]
    assert task.entrypoint_role == "module_component"
    assert task.owner == "archcanvas-static-adapter"
    assert task.publication_status == "publication_not_assessed"
    assert task.source_files_unchanged is True
    assert task.unresolved_codes == ["DYNAMIC_CONSTRUCTOR_CONTROL_FLOW", "DYNAMIC_CONTROL_FLOW"]
    assert [(item.relative_file, item.code) for item in report.scan_issues] == [
        ("broken.py", "UNPARSEABLE_SOURCE")
    ]


def test_census_uses_explicit_config_without_omitting_the_entrypoint(tmp_path: Path) -> None:
    _write_project(tmp_path)

    report = PyTorchModelCensus().build(
        tmp_path,
        project_id="project:census-config",
        resolved_configs={"task.py:TaskModel": {"task_name": "forecast"}},
    )

    assert [item.status for item in report.items] == ["supported", "supported"]
    task = report.items[1]
    assert task.resolved_config == {"task_name": "forecast"}
    assert task.node_count == 3
    assert task.edge_count == 2


def test_census_writes_publication_evidence_only_outside_the_inspected_project(tmp_path: Path) -> None:
    _write_project(tmp_path)
    evidence_root = tmp_path.parent / "publication-evidence"

    report = PyTorchModelCensus().build(
        tmp_path,
        project_id="project:census-publication",
        assess_publication=True,
        publication_artifact_root=evidence_root,
    )

    stable = next(item for item in report.items if item.entrypoint == "stable.py:Stable")
    task = next(item for item in report.items if item.entrypoint == "task.py:TaskModel")
    assert stable.status == "supported"
    assert stable.publication_status == "publication_svg_ready"
    assert stable.publication_node_count >= 2
    assert stable.publication_edge_count >= 1
    assert stable.publication_svg_sha256 is not None
    assert task.status == "unresolved"
    assert task.publication_status == "publication_not_assessed"
    artifact_directories = [path for path in evidence_root.iterdir() if path.is_dir()]
    assert len(artifact_directories) == 1
    assert {
        path.name for path in artifact_directories[0].iterdir()
    } == {
        "detail.svg",
        "overview.svg",
        "publication-checklist.json",
        "publication.json",
        "scene-detail.json",
        "scene-overview.json",
    }
    checklist = json.loads((artifact_directories[0] / "publication-checklist.json").read_text())
    assert checklist["machine_preflight"] == "passed"
    assert checklist["manual_review"] == "pending"
    assert checklist["visual_iteration_status"] == "provisional_visual_iteration"
    assert report.source_files_unchanged is True

    with pytest.raises(ValueError, match="must not be written under"):
        PyTorchModelCensus().build(
            tmp_path,
            project_id="project:census-publication-invalid",
            assess_publication=True,
            publication_artifact_root=tmp_path / "publication-evidence",
        )


def test_census_command_writes_only_outside_the_inspected_project(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    _write_project(project_root)
    output = tmp_path / "tfb-model-census.json"

    assert main([str(project_root), "--project-id", "project:census-cli", "--output", str(output)]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["execution"]["source_written"] is False
    assert payload["execution"]["source_files_unchanged"] is True
    assert payload["approved_root"] == "."
    assert payload["discovered_entrypoint_count"] == 2

    with pytest.raises(ValueError, match="must not be written under"):
        main([str(project_root), "--output", str(project_root / "census.json")])


def test_census_accounts_for_static_baseline_registry_aliases_and_non_pytorch_exports(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "baselines" / "demo"
    registry.mkdir(parents=True)
    (registry / "__init__.py").write_text(
        "__all__ = ['External', 'Stable']\n"
        "from .model import External, Stable\n",
        encoding="utf-8",
    )
    (registry / "model.py").write_text(
        "import torch.nn as nn\n\n"
        "class External:\n"
        "    pass\n\n"
        "class Stable(nn.Module):\n"
        "    def forward(self, x):\n"
        "        return x\n",
        encoding="utf-8",
    )

    report = PyTorchModelCensus().build(tmp_path, project_id="project:registry-census")
    payload = report.as_dict()

    assert payload["discovered_entrypoint_count"] == 3
    assert payload["assessed_entrypoint_count"] == 2
    assert payload["explicit_aliases"] == [
        {
            "registry_export": "registry:baselines/demo/__init__.py:Stable",
            "target_entrypoint": "baselines/demo/model.py:Stable",
        }
    ]
    registry_item = next(item for item in report.items if item.discovery_source == "static_baseline_registry")
    assert registry_item.entrypoint == "registry:baselines/demo/__init__.py:External"
    assert registry_item.status == "unsupported"
    assert registry_item.unresolved_codes == ["REGISTRY_EXPORT_NOT_STATIC_PYTORCH_ENTRYPOINT"]
