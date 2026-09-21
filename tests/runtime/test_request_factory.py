from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from archcanvas_core.models.runtime import RuntimeProviderId, RuntimeTensorInput
from archcanvas_core.models.source_identity import SourceIdentityDocument
from archcanvas_pytorch.runtime import TraceRequestFactory, TraceRequestRejected

ROOT = Path(__file__).resolve().parents[2]


def _source_document() -> SourceIdentityDocument:
    return SourceIdentityDocument.model_validate_json(
        (ROOT / "fixtures" / "resnet_static_v1" / "expected" / "source-identity.json").read_bytes()
    )


def test_factory_binds_request_to_current_source_identity() -> None:
    root = ROOT / "fixtures" / "resnet_static_v1" / "source"
    request = TraceRequestFactory().build(
        request_id="trace-request:factory",
        project_root=root,
        source=_source_document(),
        entrypoint="model.py:ResidualBlock",
        python_executable=sys.executable,
        inputs=[RuntimeTensorInput(shape=[2, 16, 8, 8], dtype="float32")],
        provider=RuntimeProviderId.TORCH_FX,
    )
    assert request.source_revision == _source_document().source_revision
    assert request.entrypoint_file_revision == _source_document().file_revisions["model.py"]
    assert request.network_policy.value == "deny"


def test_factory_rejects_stale_source_identity_before_worker_execution(tmp_path: Path) -> None:
    (tmp_path / "model.py").write_bytes(
        (ROOT / "fixtures" / "resnet_static_v1" / "source" / "model.py").read_bytes() + b"\n# changed\n"
    )
    with pytest.raises(TraceRequestRejected, match="STALE_SOURCE_IDENTITY"):
        TraceRequestFactory().build(
            request_id="trace-request:stale-factory",
            project_root=tmp_path,
            source=_source_document(),
            entrypoint="model.py:ResidualBlock",
            python_executable=sys.executable,
            inputs=[RuntimeTensorInput(shape=[2, 16, 8, 8], dtype="float32")],
            provider=RuntimeProviderId.TORCH_FX,
        )


def test_trace_cli_requires_explicit_execution_acknowledgement() -> None:
    root = ROOT / "fixtures" / "resnet_static_v1" / "source"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_pytorch_trace.py",
            "--project-root",
            str(root),
            "--source-identity",
            str(ROOT / "fixtures" / "resnet_static_v1" / "expected" / "source-identity.json"),
            "--entrypoint",
            "model.py:ResidualBlock",
            "--request-id",
            "trace-request:cli-refusal",
            "--input-shape",
            "2,16,8,8",
            "--input-dtype",
            "float32",
        ],
        capture_output=True,
        check=False,
        cwd=ROOT,
        text=True,
    )
    assert completed.returncode == 2
    assert "EXECUTION_NOT_ACKNOWLEDGED" in completed.stderr
