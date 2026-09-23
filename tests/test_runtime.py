from __future__ import annotations

import hashlib
import json
from pathlib import Path

from archcanvas_core.models import RuntimeInputSpec
from archcanvas_engine.cli import main
from archcanvas_python import analyze_project
from archcanvas_runtime import trace_runtime
from archcanvas_studio import prepare_studio_bundle

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "tier_a" / "transformer"


def _write_analysis(project: Path, config_path: Path, out: Path, entry: str) -> Path:
    bundle = analyze_project(
        project,
        entry,
        "inference",
        "eval",
        config_path.read_bytes(),
        config_path,
    )
    out.mkdir()
    (out / "architecture.json").write_text(bundle.architecture.model_dump_json())
    (out / "source-snapshot.json").write_text(bundle.snapshot.model_dump_json())
    (out / "evidence-ledger.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in bundle.evidence])
    )
    return out / "architecture.json"


def _hashes(paths: list[Path]) -> dict[Path, str]:
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def test_trace_cli_replays_shapes_and_preserves_static_artifacts(
    tmp_path: Path, capsys
) -> None:
    analysis = tmp_path / "analysis"
    artifact = _write_analysis(FIXTURE, FIXTURE / "config.json", analysis, "model:Transformer")
    static_paths = [artifact, analysis / "source-snapshot.json", analysis / "evidence-ledger.json"]
    before = _hashes(static_paths)
    out = analysis

    exit_code = main(
        [
            "trace",
            str(artifact),
            "--input-spec",
            str(FIXTURE / "runtime-input.json"),
            "--out",
            str(out),
            "--json",
        ]
    )
    receipt = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert receipt["status"] == "ok"
    assert receipt["details"]["replay_runs"] == 2
    assert receipt["details"]["static_artifacts_unchanged"] is True
    assert all(gate["status"] == "passed" for gate in receipt["gates"])
    trace = json.loads((out / "runtime-trace.json").read_text())
    assert trace["output_tensors"] == [
        {
            "device": "cpu",
            "dtype": "float32",
            "requires_grad": False,
            "shape": [1, 3, 32000],
        }
    ]
    assert trace["environment"]["torch_version"]
    assert trace["environment"]["deterministic_algorithms"] is True
    evidence = json.loads((out / "runtime-evidence-ledger.json").read_text())
    assert evidence
    assert {item["confidence"] for item in evidence} == {"runtime-confirmed"}
    studio = prepare_studio_bundle(artifact, tmp_path / ".archcanvas")
    studio_state = studio.state()
    assert studio_state["capabilities"]["runtime_evidence"] is True
    assert studio_state["runtime"]["trace"]["trace_id"] == trace["trace_id"]
    assert any(item.kind.value == "runtime" for item in studio.evidence)
    (analysis / "runtime-receipt.json").write_text(json.dumps({"status": "failed"}))
    stale = prepare_studio_bundle(artifact, tmp_path / ".archcanvas-stale")
    assert stale.state()["capabilities"]["runtime_evidence"] is False
    assert _hashes(static_paths) == before


def test_runtime_failure_keeps_static_analysis_usable(tmp_path: Path) -> None:
    analysis = tmp_path / "analysis"
    artifact = _write_analysis(FIXTURE, FIXTURE / "config.json", analysis, "model:Transformer")
    static_paths = [artifact, analysis / "source-snapshot.json", analysis / "evidence-ledger.json"]
    before = _hashes(static_paths)
    bad_spec = RuntimeInputSpec.model_validate_json(
        (FIXTURE / "runtime-input.json").read_text()
    ).model_copy(
        update={
            "inputs": [
                item.model_copy(update={"shape": [1, 4, 63]})
                if item.name == "src"
                else item
                for item in RuntimeInputSpec.model_validate_json(
                    (FIXTURE / "runtime-input.json").read_text()
                ).inputs
            ]
        }
    )
    spec_path = tmp_path / "bad-input.json"
    spec_path.write_text(bad_spec.model_dump_json())

    receipt = trace_runtime(artifact, spec_path, tmp_path / "runtime")

    assert receipt.status == "failed"
    assert receipt.exit_code == 1
    assert receipt.details["static_artifacts_unchanged"] is True
    assert next(gate for gate in receipt.gates if gate.gate == "G-runtime-replay").status == "skipped"
    assert not (tmp_path / "runtime" / "runtime-trace.json").exists()
    assert (tmp_path / "runtime" / "runtime-receipt.json").is_file()
    assert _hashes(static_paths) == before


def test_worker_blocks_network_processes_and_writes_outside_sandbox(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "boundary-project"
    project.mkdir()
    outside = tmp_path / "forbidden.txt"
    (project / "model.py").write_text(
        f"""import os
import socket
import subprocess
from pathlib import Path
from torch import nn

class BoundaryModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.projection = nn.Linear(2, 2)

    def forward(self, x):
        if os.environ.get("ARCHCANVAS_SECRET_TEST"):
            raise RuntimeError("parent environment leaked into worker")
        try:
            Path({str(outside)!r}).write_text("forbidden")
        except PermissionError:
            pass
        try:
            socket.create_connection(("127.0.0.1", 9), timeout=0.01)
        except PermissionError:
            pass
        try:
            subprocess.run(["true"], check=True)
        except PermissionError:
            pass
        return self.projection(x)
"""
    )
    config = project / "config.json"
    config.write_text(json.dumps({"input_shapes": {"x": "[B,D]"}}))
    artifact = _write_analysis(project, config, tmp_path / "analysis", "model:BoundaryModel")
    spec = RuntimeInputSpec(
        seed=7,
        inputs=[{"name": "x", "shape": [1, 2], "dtype": "float32", "generator": "ones"}],
    )
    spec_path = tmp_path / "input.json"
    spec_path.write_text(spec.model_dump_json())
    monkeypatch.setenv("ARCHCANVAS_SECRET_TEST", "must-not-leak")

    receipt = trace_runtime(artifact, spec_path, tmp_path / "runtime")

    assert receipt.status == "ok"
    assert not outside.exists()
    trace = json.loads((tmp_path / "runtime" / "runtime-trace.json").read_text())
    assert {item["operation"] for item in trace["isolation"]["violations"]} == {
        "network",
        "process",
        "write",
    }
    assert receipt.details["blocked_boundary_attempts"] == 3
