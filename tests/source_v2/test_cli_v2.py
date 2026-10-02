from __future__ import annotations

import hashlib
import json
from pathlib import Path

from archcanvas_engine.cli import main
from archcanvas_studio import prepare_studio_bundle

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
    assert (output / "analysis-environment-manifest-v1.json").is_file()
    state = prepare_studio_bundle(
        output / "architecture.json",
        tmp_path / "studio",
        write_static=False,
    ).state()
    assert state["analysis_environment"]["environment_manifest_digest"] == state[
        "analysis_input"
    ]["environment_manifest_digest"]


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
    environment = json.loads(
        (output / "analysis-environment-manifest-v1.json").read_text()
    )
    assert analysis_input["environment_manifest_digest"] == environment[
        "environment_manifest_digest"
    ]
    assert analysis_input["pattern_pack_digests"] == []


def test_cli_v2_entry_invocation_changes_analysis_identity(
    tmp_path: Path, capsys
) -> None:
    digests: list[str] = []
    for channels in (16, 32):
        invocation = tmp_path / f"invocation-{channels}.json"
        invocation.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "constructor_args": [],
                    "constructor_kwargs": {"channels": channels},
                    "forward_args": [],
                    "forward_kwargs": {},
                    "static_args": {"image_size": 32},
                    "mode": "eval",
                    "input_structure": {"kind": "tensor", "shape": [1, 3, 32, 32]},
                }
            ),
            encoding="utf-8",
        )
        output = tmp_path / f"artifacts-{channels}"
        assert main(
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
                "--entry-invocation",
                str(invocation),
                "--out",
                str(output),
                "--frontend",
                "v2",
            ]
        ) == 0
        capsys.readouterr()
        analysis_input = json.loads((output / "analysis-input-v2.json").read_text())
        assert analysis_input["entry_invocation"]["constructor_kwargs"] == {
            "channels": channels
        }
        digests.append(analysis_input["analysis_input_digest"])

    assert len(set(digests)) == 2
    assert all(len(value) == len(hashlib.sha256().hexdigest()) for value in digests)
