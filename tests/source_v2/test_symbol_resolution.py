from __future__ import annotations

import shutil
from pathlib import Path

from archcanvas_python import analyze_project_v2
from archcanvas_python.lineage import build_lineage_report

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "frontend_v2"


def test_local_reexport_resolves_to_registry_definition(tmp_path: Path) -> None:
    bundle = analyze_project_v2(
        FIXTURES / "reexports",
        "app.model:Model",
        "inference",
        "eval",
        tmp_path / "workspace",
    )
    definitions = {
        call.definition_ref.definition_id
        for call in bundle.exact_ir.calls
        if call.definition_ref is not None
    }

    assert definitions == {"pytorch.nn.conv2d"}


def test_linear_import_spellings_bind_the_same_registry_definition(tmp_path: Path) -> None:
    bundle = analyze_project_v2(
        FIXTURES / "aliases",
        "app.model:Model",
        "inference",
        "eval",
        tmp_path / "workspace",
    )
    linear_instances = [
        item
        for item in bundle.exact_ir.instances
        if item.definition_ref
        and item.definition_ref.definition_id == "pytorch.nn.linear"
    ]

    assert {item.instance_path for item in linear_instances} == {
        "model.from_nn",
        "model.from_torch",
        "model.from_direct",
        "model.from_alias",
        "model.from_reexport",
    }
    assert len({item.definition_ref for item in linear_instances}) == 1


def test_conditional_import_candidates_remain_ambiguous(tmp_path: Path) -> None:
    bundle = analyze_project_v2(
        FIXTURES / "conditional_imports",
        "model:Model",
        "inference",
        "eval",
        tmp_path / "workspace",
    )

    ambiguous = [
        item for item in bundle.exact_ir.diagnostics if item.code == "V2_CALL_AMBIGUOUS"
    ]
    opaque_calls = [
        item
        for item in bundle.exact_ir.calls
        if item.confidence.value == "unresolved"
    ]

    assert len(ambiguous) == 1
    assert "torch.nn.GELU" in ambiguous[0].message
    assert "torch.nn.ReLU" in ambiguous[0].message
    assert len(opaque_calls) == 1
    assert opaque_calls[0].definition_ref is None
    assert [item.port_id for item in opaque_calls[0].input_bindings] == ["input0"]
    assert [item.port_id for item in opaque_calls[0].output_bindings] == ["output"]


def test_shared_instance_has_one_parameter_group_and_two_calls(tmp_path: Path) -> None:
    bundle = analyze_project_v2(
        FIXTURES / "shared_module",
        "model:Model",
        "inference",
        "eval",
        tmp_path / "workspace",
    )
    calls = [
        call
        for call in bundle.exact_ir.calls
        if call.definition_ref and call.definition_ref.definition_id == "pytorch.nn.linear"
    ]
    group = next(
        item
        for item in bundle.exact_ir.parameter_groups
        if item.owner_instance_id.endswith(".projection")
    )

    assert len(calls) == 2
    assert set(group.call_ids) == {item.call_id for item in calls}


def test_comment_insertion_rotates_evidence_but_preserves_call_ids(tmp_path: Path) -> None:
    source = FIXTURES / "shared_module"
    changed = tmp_path / "changed-project"
    shutil.copytree(source, changed)
    original = analyze_project_v2(
        source,
        "model:Model",
        "inference",
        "eval",
        tmp_path / "original-workspace",
    )
    model_path = changed / "src" / "model.py"
    model_path.write_text("# inserted comment\n" + model_path.read_text(encoding="utf-8"), encoding="utf-8")
    updated = analyze_project_v2(
        changed,
        "model:Model",
        "inference",
        "eval",
        tmp_path / "changed-workspace",
    )

    assert {item.call_id for item in original.exact_ir.calls} == {
        item.call_id for item in updated.exact_ir.calls
    }
    assert {item.evidence_id for item in original.exact_ir.evidence}.isdisjoint(
        {item.evidence_id for item in updated.exact_ir.evidence}
    )
    report = build_lineage_report(original.exact_ir, updated.exact_ir)
    assert report.records
    assert {item.status for item in report.records} == {"preserved"}
