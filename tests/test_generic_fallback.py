from __future__ import annotations

import json
from pathlib import Path

import pytest

from archcanvas_core.models import NodeKind
from archcanvas_core.validation import validate_architecture
from archcanvas_engine.cli import main
from archcanvas_python import analyze_project

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("fixture_name", "entrypoint", "task"),
    [
        ("transformer", "model:Transformer", "inference"),
        ("autoformer", "models.Autoformer:Model", "long_term_forecast"),
        ("itransformer", "model.iTransformer:Model", "long_term_forecast"),
        ("patchtst", "models.PatchTST:Model", "long_term_forecast"),
        ("timemixer", "models.TimeMixer:Model", "long_term_forecast"),
    ],
)
def test_tier_a_fixture_closes_without_pattern_packs(
    fixture_name: str,
    entrypoint: str,
    task: str,
) -> None:
    fixture = ROOT / "fixtures" / "tier_a" / fixture_name
    bundle = analyze_project(
        fixture,
        entrypoint,
        task,
        "eval",
        (fixture / "config.json").read_bytes(),
        fixture / "config.json",
        pattern_packs_enabled=False,
    )
    gates, diagnostics = validate_architecture(
        bundle.architecture,
        bundle.evidence,
        bundle.snapshot,
    )
    assert next(gate for gate in gates if gate.gate == "A-source-identity").status == "passed"
    assert next(gate for gate in gates if gate.gate == "B-semantic-closure").status == "passed"
    assert not [
        gate
        for gate in gates
        if gate.gate
        in {
            "B-transformer-l3",
            "B-autoformer",
            "B-itransformer",
            "B-patchtst",
            "B-timemixer",
        }
    ]
    assert not diagnostics

    container = next(node for node in bundle.architecture.nodes if node.parent_id is None)
    assert container.attributes["architecture_profile"] == "generic"
    assert container.attributes["pattern_packs_enabled"] is False
    if fixture_name == "autoformer":
        boundary = next(
            node
            for node in bundle.architecture.nodes
            if node.kind is NodeKind.OPAQUE_COMPOSITE
            and node.attributes.get("contains_return")
        )
        assert boundary.attributes["implementation_status"] == "boundary-only"
        assert boundary.attributes["semantic_status"] == "unnamed"
        assert boundary.attributes["execution_status"] == "unresolved"


def test_cli_no_pattern_packs_emits_disabled_receipt(tmp_path: Path, capsys) -> None:
    fixture = ROOT / "fixtures" / "tier_a" / "autoformer"
    exit_code = main(
        [
            "analyze",
            "--project",
            str(fixture),
            "--entry",
            "models.Autoformer:Model",
            "--config",
            str(fixture / "config.json"),
            "--task",
            "long_term_forecast",
            "--mode",
            "eval",
            "--out",
            str(tmp_path),
            "--no-pattern-packs",
            "--json",
        ]
    )
    receipt = json.loads(capsys.readouterr().out)
    pattern_receipt = json.loads((tmp_path / "pattern-pack-receipt.json").read_text())
    overlay = json.loads((tmp_path / "semantic-annotation-overlay.json").read_text())
    assert exit_code == 0
    assert receipt["details"]["profile"] == "generic"
    assert receipt["details"]["pattern_packs_enabled"] is False
    assert pattern_receipt["status"] == "disabled"
    assert pattern_receipt["loaded_packs"] == []
    assert pattern_receipt["exact_ir_digest_before"] == pattern_receipt["exact_ir_digest_after"]
    assert overlay["annotations"] == []
