from __future__ import annotations

import json
from pathlib import Path

from archcanvas_engine.cli import main

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "frontend_v2" / "conv_relu"


def test_cli_v2_writes_parallel_artifacts(tmp_path: Path, capsys) -> None:
    output = tmp_path / "artifacts"
    exit_code = main(
        [
            "analyze",
            "--project",
            str(FIXTURE),
            "--entry",
            "app.model:Model",
            "--task",
            "inference",
            "--mode",
            "eval",
            "--out",
            str(output),
            "--frontend",
            "v2",
        ]
    )
    receipt = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert receipt["status"] == "ok"
    assert receipt["details"]["frontend"] == "v2"
    assert receipt["details"]["resolver"]["kind"] == "libcst-only"
    assert (output / "architecture.json").is_file()
    assert (output / "architecture-v2.json").is_file()
    assert (output / "project-manifest-v2.json").is_file()
    assert (output / "source-corpus-v2.json").is_file()


def test_cli_v2_disables_builtin_pattern_packs(tmp_path: Path, capsys) -> None:
    output = tmp_path / "artifacts"
    exit_code = main(
        [
            "analyze",
            "--project",
            str(FIXTURE),
            "--entry",
            "app.model:Model",
            "--task",
            "inference",
            "--mode",
            "eval",
            "--out",
            str(output),
            "--frontend",
            "v2",
            "--no-pattern-packs",
        ]
    )
    capsys.readouterr()

    assert exit_code == 0
    analysis_input = json.loads((output / "analysis-input-v2.json").read_text())
    assert analysis_input["pattern_pack_digests"] == []
