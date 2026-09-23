from __future__ import annotations

import json
from pathlib import Path

from archcanvas_engine.cli import main


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "tier_a" / "transformer"


def test_doctor_emits_one_json_receipt(capsys) -> None:
    exit_code = main(["doctor", "--json"])
    receipt = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert receipt["status"] == "ok"
    assert receipt["details"]["network_required"] is False


def test_analyze_writes_versioned_artifacts(tmp_path, capsys) -> None:
    exit_code = main(
        [
            "analyze",
            "--project",
            str(FIXTURE),
            "--entry",
            "model:Transformer",
            "--config",
            str(FIXTURE / "config.json"),
            "--task",
            "inference",
            "--mode",
            "eval",
            "--out",
            str(tmp_path),
            "--json",
        ]
    )
    receipt = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert receipt["details"]["source_execution"] is False
    assert (tmp_path / "architecture.json").is_file()
    assert (tmp_path / "evidence-ledger.json").is_file()
    assert json.loads((tmp_path / "architecture.json").read_text())["schema_version"] == "1.0"


def test_unavailable_command_is_explicit(capsys) -> None:
    exit_code = main(["render", "--json"])
    receipt = json.loads(capsys.readouterr().out)
    assert exit_code == 3
    assert receipt["status"] == "unavailable"
    assert receipt["diagnostics"][0]["code"] == "CAPABILITY_UNAVAILABLE"
