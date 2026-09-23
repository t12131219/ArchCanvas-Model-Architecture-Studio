from __future__ import annotations

import json
from pathlib import Path

import pytest

from archcanvas_engine.cli import main

ROOT = Path(__file__).resolve().parents[1]

PROFILES = [
    ("transformer", "model:Transformer", "inference", "B-transformer-l3"),
    ("autoformer", "models.Autoformer:Model", "long_term_forecast", "B-autoformer"),
    (
        "itransformer",
        "model.iTransformer:Model",
        "long_term_forecast",
        "B-itransformer",
    ),
    ("patchtst", "models.PatchTST:Model", "long_term_forecast", "B-patchtst"),
    ("timemixer", "models.TimeMixer:Model", "long_term_forecast", "B-timemixer"),
]


@pytest.mark.parametrize(("fixture_name", "entrypoint", "task", "profile_gate"), PROFILES)
def test_every_tier_a_profile_emits_fixed_stage2_artifacts(
    fixture_name: str,
    entrypoint: str,
    task: str,
    profile_gate: str,
    tmp_path: Path,
    capsys,
) -> None:
    fixture = ROOT / "fixtures" / "tier_a" / fixture_name
    out = tmp_path / fixture_name
    exit_code = main(
        [
            "analyze",
            "--project",
            str(fixture),
            "--entry",
            entrypoint,
            "--config",
            str(fixture / "config.json"),
            "--task",
            task,
            "--mode",
            "eval",
            "--out",
            str(out),
            "--json",
        ]
    )
    receipt = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert next(gate for gate in receipt["gates"] if gate["gate"] == profile_gate)["status"] == (
        "passed"
    )
    for filename in (
        "source-snapshot.json",
        "architecture.json",
        "module-ledger.json",
        "tensor-ledger.json",
        "edge-ledger.json",
        "evidence-ledger.json",
        "discrepancy-ledger.json",
        "omission-ledger.json",
        "semantic-annotation-overlay.json",
        "pattern-pack-receipt.json",
        "source-correction-report.json",
        "runtime-receipt.json",
        "analysis-receipt.json",
    ):
        assert (out / filename).is_file()
    runtime = json.loads((out / "runtime-receipt.json").read_text())
    pattern = json.loads((out / "pattern-pack-receipt.json").read_text())
    assert runtime["status"] == "skipped"
    assert pattern["exact_ir_digest_before"] == pattern["exact_ir_digest_after"]

    validate_exit = main(["validate", str(out / "architecture.json"), "--json"])
    validate_receipt = json.loads(capsys.readouterr().out)
    assert validate_exit == 0
    assert next(
        gate for gate in validate_receipt["gates"] if gate["gate"] == profile_gate
    )["status"] == "passed"
