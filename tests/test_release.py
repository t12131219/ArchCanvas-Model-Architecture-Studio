from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from archcanvas_engine.cli import main
from archcanvas_release import create_bundle, install_skill, release_support_matrix, verify_bundle

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "holdout" / "residual_mlp"


def _analysis(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    out = tmp_path / "analysis"
    assert main(
        [
            "analyze",
            "--project",
            str(FIXTURE),
            "--entry",
            "model:CrossBlendRegressor",
            "--config",
            str(FIXTURE / "config.json"),
            "--task",
            "forecast",
            "--mode",
            "eval",
            "--out",
            str(out),
            "--no-pattern-packs",
            "--json",
        ]
    ) == 0
    capsys.readouterr()
    return out


def test_offline_bundle_is_redacted_self_contained_and_tamper_evident(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    analysis = _analysis(tmp_path, capsys)
    output = tmp_path / "model.archcanvas"
    manifest, gates = create_bundle(analysis / "architecture.json", output)
    assert manifest.network_required is False
    assert manifest.absolute_paths_redacted is True
    assert {"C-publication", "D-geometry"} <= {gate.split("-")[0] + "-" + gate.split("-")[1] for gate in gates}
    verified = verify_bundle(output)
    assert verified == manifest
    assert (output / "publication/l1/view.html").is_file()
    assert (output / "publication/l4/scene.svg").is_file()
    all_json = "\n".join(
        path.read_text(encoding="utf-8") for path in output.rglob("*.json")
    )
    assert str(ROOT) not in all_json
    assert '"network_required":false' in all_json

    target = output / manifest.files[0].path
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_bundle(output)


def test_bundle_cli_create_and_verify(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    analysis = _analysis(tmp_path, capsys)
    output = tmp_path / "cli.archcanvas"
    assert main(
        [
            "bundle",
            "create",
            str(analysis / "architecture.json"),
            "--out",
            str(output),
            "--json",
        ]
    ) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["details"]["network_required"] is False
    assert receipt["details"]["absolute_paths_redacted"] is True
    assert main(["bundle", "verify", str(output), "--json"]) == 0
    verified = json.loads(capsys.readouterr().out)
    assert verified["details"]["digest_verified"] is True


def test_codex_and_claude_installers_use_identical_skill_and_offline_runtime(
    tmp_path: Path,
) -> None:
    codex_project = tmp_path / "codex-project"
    claude_project = tmp_path / "claude-project"
    codex_project.mkdir()
    claude_project.mkdir()
    codex = install_skill(codex_project, "codex", "copy")
    claude = install_skill(claude_project, "claude-code", "copy")
    codex_root = Path(str(codex["target"]))
    claude_root = Path(str(claude["target"]))
    assert (codex_root / "SKILL.md").read_bytes() == (claude_root / "SKILL.md").read_bytes()
    assert (codex_root / "runtime/src/archcanvas_engine/cli.py").is_file()
    assert (claude_root / "schemas/architecture-ir-v1.schema.json").is_file()
    completed = subprocess.run(
        [sys.executable, str(codex_root / "scripts/archcanvas.py"), "doctor", "--json"],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": ""},
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["details"]["network_required"] is False
    analysis = codex_project / "offline-analysis"
    analyzed = subprocess.run(
        [
            sys.executable,
            str(codex_root / "scripts/archcanvas.py"),
            "analyze",
            "--project",
            str(FIXTURE),
            "--entry",
            "model:CrossBlendRegressor",
            "--config",
            str(FIXTURE / "config.json"),
            "--task",
            "forecast",
            "--mode",
            "eval",
            "--out",
            str(analysis),
            "--no-pattern-packs",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": ""},
    )
    assert analyzed.returncode == 0, analyzed.stderr
    assert (analysis / "architecture.json").is_file()


def test_installer_refuses_overwrite_and_support_matrix_is_honest(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    install_skill(project, "codex", "copy")
    with pytest.raises(FileExistsError):
        install_skill(project, "codex", "copy")
    matrix = release_support_matrix()
    hosts = {item.host: item for item in matrix.hosts}
    assert hosts["codex-local"].status == "verified"
    assert hosts["claude-code-local"].status == "installer-tested"
    assert hosts["claude-api"].status == "unsupported"
    assert hosts["claude.ai"].status == "unsupported"
    adapters = {item.framework: item for item in matrix.adapters}
    assert adapters["pytorch"].runtime_evidence is True
    assert adapters["keras"].runtime_evidence is True
    assert adapters["keras"].capability_status["runtime"] == "experimental"
    assert adapters["keras"].capability_status["structural_transaction"] == "partial"
    assert adapters["jax"].source_transactions is True
    assert adapters["jax"].capability_status["parameter_transaction"] == "partial"
    assert adapters["onnx"].source_transactions is False
    assert adapters["onnx"].capability_status["runtime"] == "experimental"
    assert adapters["onnx"].artifact_commit is True
    assert adapters["onnx"].capability_status["parameter_transaction"] == "partial"


def test_skill_routing_eval_has_balanced_trigger_and_nontrigger_cases() -> None:
    skill = (ROOT / "skill/SKILL.md").read_text(encoding="utf-8")
    frontmatter = skill.split("---", 2)[1]
    description = next(
        line.removeprefix("description: ")
        for line in frontmatter.splitlines()
        if line.startswith("description: ")
    )
    evaluation = json.loads((ROOT / "evals/skill-routing.json").read_text())
    cases = evaluation["cases"]
    assert len(description) <= 1024
    assert "architecture" in description.lower() and "source" in description.lower()
    assert len([case for case in cases if case["should_trigger"]]) >= 3
    assert len([case for case in cases if not case["should_trigger"]]) >= 3
    assert len({case["id"] for case in cases}) == len(cases)
