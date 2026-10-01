from __future__ import annotations

from pathlib import Path

from archcanvas_core.source_v2 import AnalysisBudget, DiscoveryBudget
from archcanvas_python import analyze_project_v2
from archcanvas_python.pyright_client import PyrightClient

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "frontend_v2" / "budget_limits"


class _UnusedTransport:
    def request(self, method, params):
        raise AssertionError("zero resolver-query budget must not call the sidecar")

    def close(self) -> None:
        pass


def _budget_boundaries(bundle):
    opaque_regions = {
        item.control_region_id
        for item in bundle.exact_ir.control_regions
        if item.kind == "opaque"
    }
    return [
        item
        for item in bundle.exact_ir.calls
        if item.control_region_id in opaque_regions
        and any(output.port_id == "output" for output in item.output_bindings)
    ]


def test_call_depth_budget_emits_ported_opaque_boundary(tmp_path: Path) -> None:
    bundle = analyze_project_v2(
        FIXTURE,
        "model:Model",
        "inference",
        "eval",
        tmp_path / "workspace",
        analysis_budget=AnalysisBudget(max_call_depth=0),
    )

    boundaries = _budget_boundaries(bundle)
    assert any(item.input_bindings for item in boundaries)
    assert {item.code for item in bundle.exact_ir.diagnostics} >= {
        "ANALYSIS_BUDGET_EXCEEDED"
    }
    assert "V2_COMPAT_CONTROL_FLOW_LOSSY" in {
        item.code for item in bundle.compatibility.architecture.unresolved
    }


def test_file_budget_keeps_independent_graph_and_adds_boundary(tmp_path: Path) -> None:
    bundle = analyze_project_v2(
        FIXTURE,
        "model:Model",
        "inference",
        "eval",
        tmp_path / "workspace",
        discovery_budget=DiscoveryBudget(
            max_files=2,
            max_total_bytes=100_000,
            max_file_bytes=100_000,
        ),
    )

    assert any(item.reason == "budget-exhausted" for item in bundle.corpus.excluded)
    assert _budget_boundaries(bundle)
    assert bundle.exact_ir.instances


def test_resolver_query_budget_degrades_with_opaque_boundary(tmp_path: Path) -> None:
    client = PyrightClient(_UnusedTransport(), tmp_path)
    bundle = analyze_project_v2(
        FIXTURE,
        "model:Model",
        "inference",
        "eval",
        tmp_path / "workspace",
        analysis_budget=AnalysisBudget(max_resolver_queries=0),
        pyright_client=client,
        pyright_executable_digest="1" * 64,
    )

    resolver = bundle.analysis_input.resolver
    assert resolver.kind == "pyright-typeserver"
    assert resolver.capability_status == "degraded"
    assert resolver.diagnostic_code == "ANALYSIS_BUDGET_EXCEEDED"
    assert _budget_boundaries(bundle)
