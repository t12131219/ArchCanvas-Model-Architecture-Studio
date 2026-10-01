from __future__ import annotations

from pathlib import Path

from archcanvas_python import analyze_project_v2

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "frontend_v2"


def test_mha_keyword_order_binds_named_ports(tmp_path: Path) -> None:
    bundle = analyze_project_v2(
        FIXTURES / "mha_ports",
        "model:Model",
        "inference",
        "eval",
        tmp_path / "workspace",
    )
    call = next(
        item
        for item in bundle.exact_ir.calls
        if item.definition_ref
        and item.definition_ref.definition_id == "pytorch.nn.multiheadattention"
    )

    assert [(item.port_id, item.argument_name) for item in call.input_bindings] == [
        ("query", "query"),
        ("key", "key"),
        ("value", "value"),
        ("attention_mask", "attn_mask"),
    ]
    assert [item.port_id for item in call.output_bindings] == ["context", "weights"]
    assert not [item for item in bundle.exact_ir.diagnostics if item.severity == "blocking"]


def test_lstm_nested_tuple_materializes_all_outputs(tmp_path: Path) -> None:
    bundle = analyze_project_v2(
        FIXTURES / "lstm_outputs",
        "model:Model",
        "inference",
        "eval",
        tmp_path / "workspace",
    )
    call = next(
        item
        for item in bundle.exact_ir.calls
        if item.definition_ref and item.definition_ref.definition_id == "pytorch.nn.lstm"
    )

    assert [item.port_id for item in call.output_bindings] == ["sequence", "hn", "cn"]
    values = {item.semantic_name for item in bundle.exact_ir.values}
    assert {"sequence", "hn", "cn"} <= values
    compatibility_codes = {item.code for item in bundle.compatibility.architecture.unresolved}
    assert "V2_COMPAT_MULTIPLE_OUTPUTS" in compatibility_codes
