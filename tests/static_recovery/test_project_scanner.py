from __future__ import annotations

from pathlib import Path

from archcanvas_pytorch.static import PyTorchProjectScanner


def test_project_scanner_reports_entrypoints_and_unparseable_sources(tmp_path: Path) -> None:
    (tmp_path / "model.py").write_text(
        "from torch import nn\n\n"
        "class Model(nn.Module):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self.linear = nn.Linear(2, 1)\n"
        "    def forward(self, x):\n"
        "        return self.linear(x)\n",
        encoding="utf-8",
    )
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "ignored.py").write_text("def broken(:\n", encoding="utf-8")

    report = PyTorchProjectScanner().scan(tmp_path)

    assert report.python_files_scanned == 1
    assert [(item.relative_file, item.model_class) for item in report.entrypoints] == [
        ("model.py", "Model")
    ]
    assert [(item.relative_file, item.code) for item in report.issues] == [
        ("broken.py", "UNPARSEABLE_SOURCE")
    ]


def test_project_scanner_reports_oversized_file_without_reading_it(tmp_path: Path) -> None:
    (tmp_path / "large.py").write_text("# generated\n" * 10, encoding="utf-8")
    report = PyTorchProjectScanner(max_file_bytes=10).scan(tmp_path)
    assert report.python_files_scanned == 0
    assert [(item.relative_file, item.code) for item in report.issues] == [
        ("large.py", "FILE_TOO_LARGE")
    ]
