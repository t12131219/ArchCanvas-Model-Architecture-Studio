from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from archcanvas_core.models.visual_spec import VisualSpec
from archcanvas_core.publication_validation import validate_visual_spec_semantics
from archcanvas_core.schema_registry import SchemaRegistry, SchemaValidationError
from archcanvas_publication import PublicationCompiler, StageLayout, VisualSpecCompiler
from archcanvas_pytorch.static import PyTorchStaticAdapter

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("fixture", ["transformer_static_v1", "resnet_static_v1"])
def test_visual_spec_is_source_mapped_deterministic_and_has_no_fabricated_detail(fixture: str) -> None:
    _, exact = PyTorchStaticAdapter().analyze(
        (ROOT / "fixtures" / fixture / "source" / "model.py").read_bytes(),
        project_id=f"fixture:{fixture}",
        relative_file="model.py",
        entrypoint=("model.py:EncoderModel" if fixture.startswith("transformer") else "model.py:ResidualBlock"),
    )
    publication = PublicationCompiler().compile(exact)
    spec = VisualSpecCompiler().compile(publication, exact)
    expected = ROOT / "fixtures" / (
        "publication_transformer_v1" if fixture.startswith("transformer") else "publication_cnn_v1"
    ) / "expected" / "visual-spec.json"

    assert spec == VisualSpec.model_validate_json(expected.read_bytes())
    SchemaRegistry(ROOT / "schemas").load_and_validate(
        "visual-spec-v1.schema.json", expected.read_bytes()
    )
    assert validate_visual_spec_semantics(spec, publication) == []
    assert spec == VisualSpecCompiler().compile(publication, exact)
    assert StageLayout().layout(publication, visual_spec=spec) == StageLayout().layout(publication)
    assert spec.view_policy.direct_full_detail_supported is False
    assert all(not node.inline_expand and not node.children for node in spec.nodes)
    exact_edges = {edge.edge_id: edge for edge in exact.edges}
    for visual_edge, publication_edge in zip(spec.edges, publication.edges, strict=True):
        if len(publication_edge.member_edge_ids) == 1:
            original = exact_edges[publication_edge.member_edge_ids[0]]
            assert visual_edge.source_port_id == original.source_port_id
            assert visual_edge.target_port_id == original.target_port_id


def test_visual_spec_rejects_unmapped_ports_and_unsupported_detail() -> None:
    _, exact = PyTorchStaticAdapter().analyze(
        (ROOT / "fixtures/transformer_static_v1/source/model.py").read_bytes(),
        project_id="fixture:transformer_static_v1",
        relative_file="model.py",
        entrypoint="model.py:EncoderModel",
    )
    publication = PublicationCompiler().compile(exact)
    spec = VisualSpecCompiler().compile(publication, exact)
    payload = spec.model_dump(mode="json")
    payload["edges"][0]["source_port_id"] = "port:wrong:out"
    with pytest.raises(ValidationError, match="source port is not an output"):
        VisualSpec.model_validate_json(json.dumps(payload))

    payload = spec.model_dump(mode="json")
    payload["view_policy"]["direct_full_detail_supported"] = True
    with pytest.raises(ValidationError, match="full detail requires"):
        VisualSpec.model_validate_json(json.dumps(payload))
    # JSON Schema checks shape; the model enforces the cross-field proof rule.
    payload["nodes"][0]["unexpected"] = True
    with pytest.raises(SchemaValidationError, match="Additional properties"):
        SchemaRegistry(ROOT / "schemas").validate("visual-spec-v1.schema.json", payload)

    assert validate_visual_spec_semantics(
        spec.model_copy(update={"source_revision": "sha256:" + "0" * 64}), publication
    ) == ["VISUAL_SPEC_SOURCE_REVISION_MISMATCH"]


def test_layout_rejects_cyclic_visual_constraints() -> None:
    _, exact = PyTorchStaticAdapter().analyze(
        (ROOT / "fixtures/transformer_static_v1/source/model.py").read_bytes(),
        project_id="fixture:transformer_static_v1",
        relative_file="model.py",
        entrypoint="model.py:EncoderModel",
    )
    publication = PublicationCompiler().compile(exact)
    spec = VisualSpecCompiler().compile(publication, exact)
    reverse = spec.constraints[0].model_copy(
        update={
            "source_node_id": spec.constraints[0].target_node_id,
            "target_node_id": spec.constraints[0].source_node_id,
        }
    )
    with pytest.raises(ValueError, match="contain a cycle"):
        StageLayout().layout(publication, visual_spec=spec.model_copy(
            update={"constraints": [*spec.constraints, reverse]}
        ))
