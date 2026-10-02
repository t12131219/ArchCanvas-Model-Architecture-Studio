from __future__ import annotations

import json
from pathlib import Path

import pytest

from archcanvas_engine.cli import main

ROOT = Path(__file__).resolve().parents[1]

PROFILES = [
    ("transformer", "model:Transformer", "inference"),
    ("autoformer", "models.Autoformer:Model", "long_term_forecast"),
    ("itransformer", "model.iTransformer:Model", "long_term_forecast"),
    ("patchtst", "models.PatchTST:Model", "long_term_forecast"),
    ("timemixer", "models.TimeMixer:Model", "long_term_forecast"),
]


@pytest.mark.parametrize(("fixture_name", "entrypoint", "task"), PROFILES)
def test_every_tier_a_project_emits_generic_v2_stage2_artifacts(
    fixture_name: str,
    entrypoint: str,
    task: str,
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
            "--frontend",
            "v2",
            "--json",
        ]
    )
    receipt = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert receipt["details"]["frontend"] == "v2"
    assert receipt["details"]["compatibility_projection"] is True
    assert next(
        gate for gate in receipt["gates"] if gate["gate"] == "B-semantic-closure"
    )["status"] == "passed"
    assert not {
        "B-autoformer",
        "B-itransformer",
        "B-patchtst",
        "B-timemixer",
    } & {gate["gate"] for gate in receipt["gates"]}
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
        "source-corpus-v2.json",
        "project-manifest-v2.json",
        "analysis-input-v2.json",
        "analysis-environment-manifest-v1.json",
        "semantic-graph-v2.json",
        "architecture-v2.json",
    ):
        assert (out / filename).is_file()
    runtime = json.loads((out / "runtime-receipt.json").read_text())
    pattern = json.loads((out / "pattern-pack-receipt.json").read_text())
    assert runtime["status"] == "skipped"
    assert pattern["exact_ir_digest_before"] == pattern["exact_ir_digest_after"]
    exact_ir = json.loads((out / "architecture-v2.json").read_text())
    for field in ("definitions", "instances", "calls", "values"):
        assert exact_ir[field]
    assert exact_ir["graph_input_value_ids"]
    assert exact_ir["graph_output_value_ids"]
    assert not [
        diagnostic
        for diagnostic in exact_ir["diagnostics"]
        if diagnostic["severity"] == "blocking"
    ]

    validate_exit = main(["validate", str(out / "architecture.json"), "--json"])
    validate_receipt = json.loads(capsys.readouterr().out)
    assert validate_exit == 0
    assert next(
        gate
        for gate in validate_receipt["gates"]
        if gate["gate"] == "B-semantic-closure"
    )["status"] == "passed"
