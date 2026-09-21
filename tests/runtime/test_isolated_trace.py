from __future__ import annotations

import sys
from pathlib import Path

from archcanvas_core.models.architecture import TensorSpec
from archcanvas_core.models.common import source_snapshot_revision
from archcanvas_core.models.runtime import (
    RuntimeProviderId,
    RuntimeTensorInput,
    TraceFailureCode,
    TraceRequest,
    TraceStatus,
)
from archcanvas_core.semantic_validation import validate_architecture_semantics
from archcanvas_python.source_revision import file_revision
from archcanvas_pytorch.runtime import (
    IsolatedTraceWorker,
    RuntimeEvidenceResolver,
    RuntimeShapeValidator,
)
from archcanvas_pytorch.static import PyTorchStaticAdapter

ROOT = Path(__file__).resolve().parents[2]


def _request(root: Path, *, request_id: str, provider: RuntimeProviderId = RuntimeProviderId.TORCH_FX) -> TraceRequest:
    raw = (root / "model.py").read_bytes()
    revision = file_revision(raw)
    return TraceRequest(
        request_id=request_id,
        project_root=str(root),
        python_executable=sys.executable,
        entrypoint="model.py:ResidualBlock" if request_id != "trace-request:dynamic" else "model.py:DynamicModel",
        entrypoint_file_revision=revision,
        source_revision=source_snapshot_revision({"model.py": revision}),
        constructor_kwargs={},
        inputs=[RuntimeTensorInput(shape=[2, 16, 8, 8], dtype="float32")],
        provider=provider,
        timeout_seconds=20,
        memory_limit_mb=8192,
    )


def test_fx_trace_runs_in_worker_and_preserves_static_source_anchors() -> None:
    fixture_root = ROOT / "fixtures" / "resnet_static_v1" / "source"
    before_source = (fixture_root / "model.py").read_bytes()
    before_cwd = Path.cwd()
    result = IsolatedTraceWorker().run(_request(fixture_root, request_id="trace-request:resnet"))

    assert result.status is TraceStatus.SUCCEEDED
    assert result.failure_code is None
    assert {item.target for item in result.observations} >= {"conv1", "conv2", "relu"}
    assert Path.cwd() == before_cwd
    assert "model" not in sys.modules
    assert (fixture_root / "model.py").read_bytes() == before_source

    source, ir = PyTorchStaticAdapter().analyze(
        (fixture_root / "model.py").read_bytes(),
        project_id="project:resnet-runtime",
        relative_file="model.py",
        entrypoint="model.py:ResidualBlock",
    )
    anchors_before = [node.source_anchor_ids for node in ir.nodes]
    enriched, resolution = RuntimeEvidenceResolver().resolve(ir, result)
    assert resolution.observed_node_ids == [
        "node:residualblock.conv1",
        "node:residualblock.conv2",
        "node:residualblock.relu",
    ]
    assert [node.source_anchor_ids for node in enriched.nodes] == anchors_before
    assert validate_architecture_semantics(enriched, source) == []
    assert enriched.node("node:residualblock.conv1").metadata["runtime_status"] == "observed"


def test_torch_export_provider_runs_in_worker() -> None:
    fixture_root = ROOT / "fixtures" / "resnet_static_v1" / "source"
    result = IsolatedTraceWorker().run(
        _request(
            fixture_root,
            request_id="trace-request:export",
            provider=RuntimeProviderId.TORCH_EXPORT,
        )
    )
    assert result.status is TraceStatus.SUCCEEDED
    assert result.provider is RuntimeProviderId.TORCH_EXPORT
    assert result.observations


def test_dynamic_fx_failure_returns_safe_coverage_gap_and_blocks_structural_change(tmp_path: Path) -> None:
    (tmp_path / "model.py").write_text(
        "import torch.nn as nn\n\n"
        "class DynamicModel(nn.Module):\n"
        "    def forward(self, x):\n"
        "        if x.sum() > 0:\n"
        "            return x\n"
        "        return -x\n",
        encoding="utf-8",
    )
    result = IsolatedTraceWorker().run(_request(tmp_path, request_id="trace-request:dynamic"))
    assert result.status is TraceStatus.FAILED
    assert result.failure_code is TraceFailureCode.TRACE_UNSUPPORTED
    assert result.observations == []
    assert result.coverage_gaps == ["runtime-trace-unavailable"]

    _, ir = PyTorchStaticAdapter().analyze(
        (tmp_path / "model.py").read_bytes(),
        project_id="project:dynamic-runtime",
        relative_file="model.py",
        entrypoint="model.py:DynamicModel",
    )
    report = RuntimeShapeValidator().validate(ir, result, structural_change=True)
    assert report.blocking is True
    assert [item.code for item in report.issues] == ["RUNTIME_TRACE_UNAVAILABLE"]


def test_shape_mismatch_blocks_structural_change() -> None:
    fixture_root = ROOT / "fixtures" / "resnet_static_v1" / "source"
    result = IsolatedTraceWorker().run(_request(fixture_root, request_id="trace-request:shape"))
    assert result.status is TraceStatus.SUCCEEDED
    _, ir = PyTorchStaticAdapter().analyze(
        (fixture_root / "model.py").read_bytes(),
        project_id="project:resnet-shape",
        relative_file="model.py",
        entrypoint="model.py:ResidualBlock",
    )
    conv1 = ir.node("node:residualblock.conv1")
    wrong_port = conv1.output_ports[0].model_copy(
        update={
            "tensor": TensorSpec(
                shape=[2, 1, 8, 8],
                dtype="float32",
                device=None,
                requires_grad=None,
                semantic_axes=[],
            )
        }
    )
    wrong_ir = ir.model_copy(
        update={"nodes": [node.model_copy(update={"output_ports": [wrong_port]}) if node.node_id == conv1.node_id else node for node in ir.nodes]}
    )
    report = RuntimeShapeValidator().validate(wrong_ir, result, structural_change=True)
    assert report.blocking is True
    assert [item.code for item in report.issues] == ["RUNTIME_SHAPE_MISMATCH"]


def test_source_revision_mismatch_does_not_attach_runtime_evidence() -> None:
    fixture_root = ROOT / "fixtures" / "resnet_static_v1" / "source"
    result = IsolatedTraceWorker().run(_request(fixture_root, request_id="trace-request:revision"))
    _, ir = PyTorchStaticAdapter().analyze(
        (fixture_root / "model.py").read_bytes(),
        project_id="project:resnet-revision",
        relative_file="model.py",
        entrypoint="model.py:ResidualBlock",
    )
    mismatched = result.model_copy(update={"source_revision": "sha256:" + "1" * 64})
    enriched, resolution = RuntimeEvidenceResolver().resolve(ir, mismatched)
    assert enriched == ir
    assert resolution.observed_node_ids == []
    assert resolution.unobserved_node_ids == [
        "node:residualblock.conv1",
        "node:residualblock.conv2",
        "node:residualblock.relu",
    ]


def test_worker_rejects_stale_entrypoint_revision() -> None:
    fixture_root = ROOT / "fixtures" / "resnet_static_v1" / "source"
    request = _request(fixture_root, request_id="trace-request:stale").model_copy(
        update={"entrypoint_file_revision": "sha256:" + "0" * 64}
    )
    result = IsolatedTraceWorker().run(request)
    assert result.status is TraceStatus.FAILED
    assert result.failure_code is TraceFailureCode.STALE_ENTRYPOINT_REVISION
