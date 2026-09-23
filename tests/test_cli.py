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
    for filename in (
        "architecture.json",
        "module-ledger.json",
        "tensor-ledger.json",
        "edge-ledger.json",
        "evidence-ledger.json",
        "discrepancy-ledger.json",
        "omission-ledger.json",
    ):
        assert (tmp_path / filename).is_file()
    assert json.loads((tmp_path / "architecture.json").read_text())["schema_version"] == "1.0"
    assert (
        next(gate for gate in receipt["gates"] if gate["gate"] == "B-transformer-l3")["status"]
        == "passed"
    )

    validate_exit = main(["validate", str(tmp_path / "architecture.json"), "--json"])
    validate_receipt = json.loads(capsys.readouterr().out)
    assert validate_exit == 0
    assert validate_receipt["details"]["evidence_binding_loaded"] is True
    assert (
        next(gate for gate in validate_receipt["gates"] if gate["gate"] == "A-source-identity")[
            "status"
        ]
        == "passed"
    )


def test_unavailable_command_is_explicit(capsys) -> None:
    exit_code = main(["render", "--json"])
    receipt = json.loads(capsys.readouterr().out)
    assert exit_code == 3
    assert receipt["status"] == "unavailable"
    assert receipt["diagnostics"][0]["code"] == "CAPABILITY_UNAVAILABLE"
