from __future__ import annotations

from archcanvas_core.graph_delta import GraphDeltaValidator, architecture_diff
from archcanvas_core.models.validation import ObservedGraphDelta
from archcanvas_python.fixture_analyzer import analyze_transformer_fixture


def test_after_analysis_has_exact_expected_delta(before_ir, patch_set, fixture_path) -> None:
    _, after_ir = analyze_transformer_fixture((fixture_path / "source" / "after" / "model.py").read_bytes())
    delta = architecture_diff(before_ir, after_ir)
    report = GraphDeltaValidator().validate(patch_set.patches[0].expected_delta, delta)
    assert delta.modified_node_ids == []
    assert delta.parameter_changes[0].node_id == "node:encoder.layers"
    assert delta.parameter_changes[0].parameter == "num_heads"
    assert delta.parameter_changes[0].before == 8
    assert delta.parameter_changes[0].after == 16
    assert not report.blocking
    assert report.issues == []


def test_validator_fails_closed_for_unexpected_delta(patch_set) -> None:
    observed = ObservedGraphDelta(added_node_ids=["node:surprise"])
    report = GraphDeltaValidator().validate(patch_set.patches[0].expected_delta, observed)
    assert report.blocking
    assert {issue.code for issue in report.issues} == {
        "EXPECTED_PARAMETER_CHANGE_MISSING",
        "UNEXPECTED_NODE_ADDITION",
    }
