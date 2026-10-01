from __future__ import annotations

from pathlib import Path

from archcanvas_core.digest_protocol import canonical_json_bytes
from archcanvas_core.models import NodeKind
from archcanvas_core.validation import validate_architecture
from archcanvas_python import analyze_project_v2

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "frontend_v2" / "conv_relu"


def test_conv_relu_vertical_slice_has_instances_calls_and_named_ports(tmp_path: Path) -> None:
    bundle = analyze_project_v2(
        FIXTURE,
        "app.model:Model",
        "inference",
        "eval",
        tmp_path / "workspace",
    )

    instance_paths = {item.instance_path for item in bundle.semantic_graph.instances}
    assert {"model", "model.block", "model.block.conv", "model.block.relu"} <= instance_paths
    atomic_calls = [item for item in bundle.exact_ir.calls if item.definition_ref is not None]
    assert [item.definition_ref.definition_id for item in atomic_calls] == [
        "pytorch.nn.conv2d",
        "pytorch.nn.relu",
    ]
    assert [[item.port_id for item in call.input_bindings] for call in atomic_calls] == [
        ["input"],
        ["input"],
    ]
    assert [[item.port_id for item in call.output_bindings] for call in atomic_calls] == [
        ["output"],
        ["output"],
    ]
    assert not [item for item in bundle.exact_ir.diagnostics if item.severity == "blocking"]


def test_v1_compatibility_projection_drives_existing_validation(tmp_path: Path) -> None:
    bundle = analyze_project_v2(
        FIXTURE,
        "app.model:Model",
        "inference",
        "eval",
        tmp_path / "workspace",
    )
    compatibility = bundle.compatibility
    atomic_nodes = [
        item for item in compatibility.architecture.nodes if item.kind is NodeKind.OPERATOR
    ]

    assert [item.attributes["definition_id"] for item in atomic_nodes] == [
        "pytorch.nn.conv2d",
        "pytorch.nn.relu",
    ]
    assert [port.name for port in atomic_nodes[0].input_ports] == ["input"]
    assert [port.name for port in atomic_nodes[0].output_ports] == ["output"]
    gates, diagnostics = validate_architecture(
        compatibility.architecture,
        compatibility.evidence,
        compatibility.snapshot,
    )
    assert not [item for item in diagnostics if item.severity == "blocking"]
    assert all(item.status == "passed" for item in gates if item.status != "skipped")


def test_frontend_is_deterministic_across_absolute_paths(tmp_path: Path) -> None:
    first = analyze_project_v2(
        FIXTURE,
        "app.model:Model",
        "inference",
        "eval",
        tmp_path / "first",
    )
    second = analyze_project_v2(
        FIXTURE,
        "app.model:Model",
        "inference",
        "eval",
        tmp_path / "second",
    )

    assert first.corpus.source_corpus_digest == second.corpus.source_corpus_digest
    assert first.semantic_graph.semantic_graph_digest == second.semantic_graph.semantic_graph_digest
    assert first.exact_ir.exact_ir_digest == second.exact_ir.exact_ir_digest
    assert canonical_json_bytes(first.semantic_graph.model_dump(mode="json")) == canonical_json_bytes(
        second.semantic_graph.model_dump(mode="json")
    )
    assert canonical_json_bytes(first.exact_ir.model_dump(mode="json")) == canonical_json_bytes(
        second.exact_ir.model_dump(mode="json")
    )
