from __future__ import annotations

from pathlib import Path

from archcanvas_python import analyze_project_v2

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "frontend_v2" / "transformer_repeat_tied"


def test_module_list_loop_recovers_repeat_and_tied_parameter_group(tmp_path: Path) -> None:
    bundle = analyze_project_v2(
        FIXTURE,
        "model:Model",
        "inference",
        "eval",
        tmp_path / "workspace",
    )

    repeat = bundle.exact_ir.repeats[0]
    assert repeat.repeat_id == "repeat:model.layers"
    assert repeat.count == 2
    assert repeat.count_symbol is None
    assert repeat.parameter_identity == "distinct-per-iteration"
    assert repeat.body_call_ids
    assert any(
        call.definition_ref
        and call.definition_ref.definition_id == "pytorch.nn.linear"
        and call.call_id in repeat.body_call_ids
        for call in bundle.exact_ir.calls
    )

    tied = next(
        item for item in bundle.exact_ir.parameter_groups if item.binding_kind == "tied"
    )
    instance_paths = {
        item.instance_id: item.instance_path for item in bundle.exact_ir.instances
    }
    assert {instance_paths[item] for item in tied.member_instance_ids} == {
        "model.embedding",
        "model.projection",
    }
    assert tied.shared_attribute == "weight"
    tied_calls = {
        call.call_id
        for call in bundle.exact_ir.calls
        if call.instance_id in tied.member_instance_ids
    }
    assert set(tied.call_ids) == tied_calls

    compatibility = bundle.compatibility.architecture
    projected_repeat = compatibility.repeats[0]
    assert projected_repeat.repeat_id == repeat.repeat_id
    assert projected_repeat.count == 2
    tied_nodes = [
        node
        for node in compatibility.nodes
        if node.attributes.get("v2_instance_id") in tied.member_instance_ids
    ]
    assert len(tied_nodes) == 2
    assert {node.parameter_identity for node in tied_nodes} == {tied.parameter_group_id}
