from __future__ import annotations

import json
from pathlib import Path

from archcanvas_engine.cli import main

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "tier_a" / "transformer"


def test_cli_render_all_writes_versioned_publication_artifacts(tmp_path: Path, capsys) -> None:
    analysis = tmp_path / "analysis"
    assert (
        main(
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
                str(analysis),
                "--json",
            ]
        )
        == 0
    )
    json.loads(capsys.readouterr().out)
    publication = tmp_path / "publication"
    assert (
        main(
            [
                "render",
                str(analysis / "architecture.json"),
                "--view",
                "all",
                "--out",
                str(publication),
                "--json",
            ]
        )
        == 0
    )
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "ok"
    assert next(gate for gate in receipt["gates"] if gate["gate"] == "C-publication")[
        "status"
    ] == "passed"
    assert receipt["details"]["visual_review"] == "skipped"
    assert receipt["details"]["projections"]
    for projection in ("collapsed", "full"):
        for filename in (
            "publication-view.json",
            "visual-spec.json",
            "visual-scene.json",
            "scene.svg",
            "view.html",
            "scene.png",
            "scene.pdf",
        ):
            assert (publication / projection / filename).is_file()
    stored = json.loads((publication / "render-receipt.json").read_text())
    assert stored == receipt

    assert (
        main(
            [
                "validate",
                str(analysis / "architecture.json"),
                "--quality",
                "publication",
                "--json",
            ]
        )
        == 0
    )
    validation = json.loads(capsys.readouterr().out)
    assert validation["details"]["publication_gates_available"] is True
    assert all(gate["status"] == "passed" for gate in validation["gates"])
