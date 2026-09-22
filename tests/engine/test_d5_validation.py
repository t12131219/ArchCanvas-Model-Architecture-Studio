from __future__ import annotations

from pathlib import Path

from archcanvas_engine.d5_validation import D5CensusValidator
from archcanvas_pytorch.static import PyTorchModelCensus


def _write_project(root: Path) -> None:
    (root / "model.py").write_text(
        "import torch.nn as nn\n\n"
        "class Projection(nn.Module):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self.linear = nn.Linear(2, 2)\n\n"
        "    def forward(self, value):\n"
        "        return self.linear(value)\n",
        encoding="utf-8",
    )


def test_d5_validator_accepts_mechanical_evidence_but_blocks_pending_human_review(tmp_path: Path) -> None:
    _write_project(tmp_path)
    artifact_root = tmp_path.parent / "evidence"
    census = PyTorchModelCensus().build(
        tmp_path,
        project_id="project:d5",
        assess_publication=True,
        publication_artifact_root=artifact_root,
    ).as_dict()

    report = D5CensusValidator().validate(census, publication_artifact_root=artifact_root)

    assert report.machine_passed is True
    assert report.stage6_exit_ready is False
    assert report.blockers == []
    assert report.manual_review_pending_entrypoints == ["model.py:Projection"]


def test_d5_validator_rejects_incomplete_accounting_and_missing_evidence(tmp_path: Path) -> None:
    _write_project(tmp_path)
    census = PyTorchModelCensus().build(tmp_path, project_id="project:d5-invalid").as_dict()
    census["discovered_entrypoint_count"] = 99

    report = D5CensusValidator().validate(census)

    assert report.machine_passed is False
    assert "ENTRYPOINT_COMPLETENESS_MISMATCH" in report.blockers
    assert "SUPPORTED_ENTRYPOINT_MISSING_PUBLICATION_EVIDENCE" in report.blockers
