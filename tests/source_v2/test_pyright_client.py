from __future__ import annotations

from pathlib import Path
from typing import Any

from archcanvas_python import analyze_project_v2
from archcanvas_python.pyright_client import (
    PyrightClient,
    PyrightTimeoutError,
    ResolverQuery,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "frontend_v2" / "conv_relu"
INHERITANCE_FIXTURE = ROOT / "tests" / "fixtures" / "frontend_v2" / "inheritance"


class FakeTransport:
    def __init__(
        self,
        snapshots: list[str],
        result: Any = None,
        *,
        fail: bool = False,
        timeout: bool = False,
    ) -> None:
        self.snapshots = iter(snapshots)
        self.result = result
        self.fail = fail
        self.timeout = timeout
        self.requests: list[tuple[str, dict[str, Any]]] = []

    def request(self, method: str, params: dict[str, Any]) -> Any:
        self.requests.append((method, params))
        if self.fail:
            raise RuntimeError("unavailable")
        if self.timeout:
            raise PyrightTimeoutError("timed out")
        if method == "typeServer/getSnapshot":
            return next(self.snapshots)
        return self.result

    def close(self) -> None:
        pass


def test_snapshot_consistent_batch_returns_all_results(tmp_path: Path) -> None:
    transport = FakeTransport(["snapshot:1", "snapshot:1"], {"type": "torch.Tensor"})
    client = PyrightClient(transport, tmp_path)
    result = client.query_batch(
        [ResolverQuery("typeServer/getComputedType", "model.py", 4, 8)]
    )

    assert result.status == "ok"
    assert result.snapshot == "snapshot:1"
    assert result.results == ({"type": "torch.Tensor"},)
    assert transport.requests[1][1]["file"] == str(tmp_path / "model.py")


def test_changed_snapshot_discards_entire_batch(tmp_path: Path) -> None:
    client = PyrightClient(
        FakeTransport(
            ["snapshot:1", "snapshot:2", "snapshot:3", "snapshot:4"],
            "result",
        ),
        tmp_path,
    )
    result = client.query_batch(
        [ResolverQuery("typeServer/resolveImport", "model.py", 1, 0)]
    )

    assert result.status == "discarded"
    assert result.results == ()
    assert result.diagnostic_code == "PYRIGHT_SNAPSHOT_CHANGED"


def test_changed_snapshot_is_retried_as_one_atomic_batch(tmp_path: Path) -> None:
    transport = FakeTransport(
        ["snapshot:1", "snapshot:2", "snapshot:3", "snapshot:3"],
        "result",
    )
    client = PyrightClient(transport, tmp_path)

    result = client.query_batch(
        [ResolverQuery("typeServer/getComputedType", "model.py", 4, 8)]
    )

    assert result.status == "ok"
    assert result.snapshot == "snapshot:3"
    assert result.results == ("result",)
    assert [method for method, _ in transport.requests].count(
        "typeServer/getComputedType"
    ) == 2


def test_sidecar_failure_degrades_deterministically(tmp_path: Path) -> None:
    client = PyrightClient(FakeTransport([], fail=True), tmp_path)
    result = client.query_batch([])

    assert result.status == "unavailable"
    assert result.diagnostic_code == "PYRIGHT_UNAVAILABLE"


def test_sidecar_timeout_has_a_distinct_degradation_code(tmp_path: Path) -> None:
    client = PyrightClient(FakeTransport([], timeout=True), tmp_path)

    result = client.query_batch([])

    assert result.status == "unavailable"
    assert result.diagnostic_code == "PYRIGHT_TIMEOUT"


def test_frontend_records_libcst_only_resolver_degradation(tmp_path: Path) -> None:
    bundle = analyze_project_v2(
        FIXTURE,
        "app.model:Model",
        "inference",
        "eval",
        tmp_path / "workspace",
    )

    resolver = bundle.analysis_input.resolver
    assert resolver.kind == "libcst-only"
    assert resolver.capability_status == "degraded"
    assert resolver.diagnostic_code == "PYRIGHT_UNAVAILABLE"
    assert resolver.python_target == "3.11"
    assert {item.code for item in bundle.exact_ir.diagnostics} >= {"PYRIGHT_UNAVAILABLE"}


def test_frontend_records_active_snapshot_consistent_sidecar(tmp_path: Path) -> None:
    client = PyrightClient(
        FakeTransport(["snapshot:active", "snapshot:active"], {"type": "torch.Tensor"}),
        tmp_path,
    )
    bundle = analyze_project_v2(
        FIXTURE,
        "app.model:Model",
        "inference",
        "eval",
        tmp_path / "workspace",
        pyright_client=client,
        pyright_executable_digest="2" * 64,
    )

    resolver = bundle.analysis_input.resolver
    assert resolver.kind == "pyright-typeserver"
    assert resolver.capability_status == "active"
    assert resolver.snapshot_id == "snapshot:active"
    assert resolver.query_count > 0
    assert resolver.query_digest is not None
    assert resolver.result_digest is not None
    assert "PYRIGHT_UNAVAILABLE" not in {
        item.code for item in bundle.exact_ir.diagnostics
    }


def test_snapshot_consistent_type_fact_resolves_inherited_factory_attribute(
    tmp_path: Path,
) -> None:
    degraded = analyze_project_v2(
        INHERITANCE_FIXTURE,
        "app.model:Model",
        "inference",
        "eval",
        tmp_path / "degraded",
    )
    assert any(
        item.code == "V2_CONSTRUCTOR_UNRESOLVED"
        for item in degraded.semantic_graph.diagnostics
    )
    assert not any(
        item.definition_ref
        and item.definition_ref.definition_id == "pytorch.nn.relu"
        for item in degraded.semantic_graph.instances
    )

    client = PyrightClient(
        FakeTransport(
            ["snapshot:inheritance", "snapshot:inheritance"],
            {"type": "torch.nn.ReLU"},
        ),
        tmp_path,
    )
    resolved = analyze_project_v2(
        INHERITANCE_FIXTURE,
        "app.model:Model",
        "inference",
        "eval",
        tmp_path / "resolved",
        pyright_client=client,
        pyright_executable_digest="5" * 64,
    )

    activation = next(
        item
        for item in resolved.semantic_graph.instances
        if item.instance_path == "model.activation"
    )
    assert activation.definition_ref is not None
    assert activation.definition_ref.definition_id == "pytorch.nn.relu"
    activation_call = next(
        item
        for item in resolved.semantic_graph.calls
        if item.instance_id == activation.instance_id
    )
    assert activation_call.confidence.value == "inferred"
    resolver_evidence = [
        item
        for item in resolved.semantic_graph.evidence
        if item.anchor.semantic_role == "resolver-type-binding"
    ]
    assert len(resolver_evidence) == 1
    assert resolver_evidence[0].confidence.value == "inferred"
    assert "snapshot:inheritance" in resolver_evidence[0].claim
    assert "torch.nn.ReLU" in resolver_evidence[0].claim


def test_frontend_discards_changed_sidecar_snapshot(tmp_path: Path) -> None:
    client = PyrightClient(
        FakeTransport(
            ["snapshot:1", "snapshot:2", "snapshot:3", "snapshot:4"],
            {},
        ),
        tmp_path,
    )
    bundle = analyze_project_v2(
        FIXTURE,
        "app.model:Model",
        "inference",
        "eval",
        tmp_path / "workspace",
        pyright_client=client,
        pyright_executable_digest="3" * 64,
    )

    resolver = bundle.analysis_input.resolver
    assert resolver.capability_status == "degraded"
    assert resolver.diagnostic_code == "PYRIGHT_SNAPSHOT_CHANGED"
    assert {item.code for item in bundle.exact_ir.diagnostics} >= {
        "PYRIGHT_SNAPSHOT_CHANGED"
    }


def test_frontend_records_timeout_without_losing_local_analysis(tmp_path: Path) -> None:
    client = PyrightClient(FakeTransport([], timeout=True), tmp_path)

    bundle = analyze_project_v2(
        FIXTURE,
        "app.model:Model",
        "inference",
        "eval",
        tmp_path / "workspace",
        pyright_client=client,
        pyright_executable_digest="4" * 64,
    )

    assert bundle.analysis_input.resolver.capability_status == "degraded"
    assert bundle.analysis_input.resolver.diagnostic_code == "PYRIGHT_TIMEOUT"
    assert bundle.exact_ir.calls
    assert {item.code for item in bundle.exact_ir.diagnostics} >= {"PYRIGHT_TIMEOUT"}
