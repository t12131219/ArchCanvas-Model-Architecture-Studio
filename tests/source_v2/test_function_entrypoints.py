from __future__ import annotations

from pathlib import Path

from archcanvas_python import analyze_project_v2

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "frontend_v2" / "function_entry"


def test_function_entrypoint_expands_cross_file_local_helper(tmp_path: Path) -> None:
    bundle = analyze_project_v2(
        FIXTURE,
        "app.model:model_fn_body",
        "inference",
        "eval",
        tmp_path / "workspace",
    )

    definitions = {item.qualified_name: item.kind for item in bundle.exact_ir.definitions}
    assert definitions == {
        "app.helpers.activate": "function",
        "app.model.model_fn_body": "function",
    }
    helper_call = next(
        item
        for item in bundle.exact_ir.calls
        if item.local_definition_id == "definition:local.app.helpers.activate"
    )
    relu_call = next(
        item
        for item in bundle.exact_ir.calls
        if item.definition_ref and item.definition_ref.definition_id == "pytorch.nn.relu"
    )
    assert [item.port_id for item in helper_call.input_bindings] == ["hidden"]
    assert [item.port_id for item in helper_call.output_bindings] == ["output"]
    assert [item.port_id for item in relu_call.input_bindings] == ["input"]
    assert bundle.exact_ir.graph_input_value_ids == bundle.semantic_graph.graph_input_value_ids
    assert bundle.exact_ir.graph_output_value_ids == bundle.semantic_graph.graph_output_value_ids
    assert bundle.exact_ir.graph_input_value_ids
    assert bundle.exact_ir.graph_output_value_ids
    assert not [
        item
        for item in bundle.exact_ir.definitions
        if item.qualified_name == "archcanvas.graph-output"
    ]
    assert not [item for item in bundle.exact_ir.diagnostics if item.severity == "blocking"]


def test_function_entrypoint_is_deterministic(tmp_path: Path) -> None:
    first = analyze_project_v2(
        FIXTURE,
        "app.model:model_fn_body",
        "inference",
        "eval",
        tmp_path / "first",
    )
    second = analyze_project_v2(
        FIXTURE,
        "app.model:model_fn_body",
        "inference",
        "eval",
        tmp_path / "second",
    )

    assert first.semantic_graph.semantic_graph_digest == second.semantic_graph.semantic_graph_digest
    assert first.exact_ir.exact_ir_digest == second.exact_ir.exact_ir_digest
