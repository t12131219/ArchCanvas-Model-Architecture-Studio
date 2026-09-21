from __future__ import annotations

import json
from pathlib import Path

import pytest

from archcanvas_core.models.architecture import ArchitectureIR, NodeKind
from archcanvas_core.models.publication import (
    MiniatureDisclosure,
    MiniatureEvidenceKind,
    PublicationIR,
    PublicationMiniature,
    PublicationMiniatureKind,
    VisualScene,
)
from archcanvas_core.publication_validation import validate_publication_semantics
from archcanvas_publication import PublicationCompiler, StageLayout
from archcanvas_pytorch.static import PyTorchStaticAdapter
from archcanvas_renderer import publication_preflight, render_svg

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = (
    (
        "transformer_static_v1",
        "publication_transformer_v1",
        "fixture:transformer_static_v1",
        "model.py:EncoderModel",
    ),
    (
        "resnet_static_v1",
        "publication_cnn_v1",
        "fixture:resnet_static_v1",
        "model.py:ResidualBlock",
    ),
)


def _exact(fixture_name: str, project_id: str, entrypoint: str) -> ArchitectureIR:
    root = ROOT / "fixtures" / fixture_name
    _, exact = PyTorchStaticAdapter().analyze(
        (root / "source" / "model.py").read_bytes(),
        project_id=project_id,
        relative_file="model.py",
        entrypoint=entrypoint,
    )
    return exact


def test_transformer_is_reduced_to_a_collapsed_repeat_group() -> None:
    exact = _exact(FIXTURES[0][0], FIXTURES[0][2], FIXTURES[0][3])
    publication = PublicationCompiler().compile(exact)

    group = next(node for node in publication.nodes if node.kind.value == "repeat_group")
    assert group.label == "Transformer encoder"
    assert group.member_node_ids == ["node:encodermodel.layers"]
    assert group.collapsed is True
    assert publication.annotations[0].text == "Repeated depth times"
    assert [(item.kind.value, item.disclosure.value) for item in publication.miniatures] == [
        ("signal_preview", "illustrative"),
        ("equation_note", "evidence"),
        ("inset_callout", "evidence"),
    ]
    assert publication.omitted_exact_edge_ids == []
    assert validate_publication_semantics(publication, exact) == []


def test_scientific_miniature_requires_permitted_evidence_and_disclosure() -> None:
    with pytest.raises(ValueError, match="miniature kind is not supported"):
        PublicationMiniature(
            miniature_id="miniature:invalid-distribution",
            target_node_id="publication-node:input",
            kind=PublicationMiniatureKind.DISTRIBUTION_PREVIEW,
            evidence_kind=MiniatureEvidenceKind.DETERMINISTIC_SCHEMATIC,
            disclosure=MiniatureDisclosure.ILLUSTRATIVE,
            label="Invented distribution",
            member_node_ids=["node:input"],
        )
    with pytest.raises(ValueError, match="requires exactly one trace_id"):
        PublicationMiniature(
            miniature_id="miniature:missing-runtime-trace",
            target_node_id="publication-node:input",
            kind=PublicationMiniatureKind.SIGNAL_PREVIEW,
            evidence_kind=MiniatureEvidenceKind.RUNTIME_SUMMARY,
            disclosure=MiniatureDisclosure.EVIDENCE,
            label="Observed signal summary",
            member_node_ids=["node:input"],
        )


def test_svg_renders_each_supported_scientific_miniature_with_disclosure() -> None:
    exact = _exact(FIXTURES[0][0], FIXTURES[0][2], FIXTURES[0][3])
    publication = PublicationCompiler().compile(exact)
    input_node = next(node for node in publication.nodes if node.kind.value == "input")
    miniatures = [
        PublicationMiniature(
            miniature_id="miniature:tensor", target_node_id=input_node.node_id,
            kind=PublicationMiniatureKind.TENSOR_STRIP,
            evidence_kind=MiniatureEvidenceKind.STATIC_TENSOR_SPEC,
            disclosure=MiniatureDisclosure.EVIDENCE, label="Static tensor specification",
            member_node_ids=input_node.member_node_ids,
        ),
        PublicationMiniature(
            miniature_id="miniature:signal", target_node_id=input_node.node_id,
            kind=PublicationMiniatureKind.SIGNAL_PREVIEW,
            evidence_kind=MiniatureEvidenceKind.RUNTIME_SUMMARY,
            disclosure=MiniatureDisclosure.EVIDENCE, label="Runtime signal summary",
            member_node_ids=input_node.member_node_ids, trace_id="trace:fixture",
        ),
        PublicationMiniature(
            miniature_id="miniature:distribution", target_node_id=input_node.node_id,
            kind=PublicationMiniatureKind.DISTRIBUTION_PREVIEW,
            evidence_kind=MiniatureEvidenceKind.RUNTIME_SUMMARY,
            disclosure=MiniatureDisclosure.EVIDENCE, label="Runtime distribution summary",
            member_node_ids=input_node.member_node_ids, trace_id="trace:fixture",
        ),
        PublicationMiniature(
            miniature_id="miniature:equation", target_node_id=input_node.node_id,
            kind=PublicationMiniatureKind.EQUATION_NOTE,
            evidence_kind=MiniatureEvidenceKind.PUBLICATION_ANNOTATION,
            disclosure=MiniatureDisclosure.EVIDENCE, label="Source-backed equation annotation",
            member_node_ids=input_node.member_node_ids,
        ),
        PublicationMiniature(
            miniature_id="miniature:inset", target_node_id=input_node.node_id,
            kind=PublicationMiniatureKind.INSET_CALLOUT,
            evidence_kind=MiniatureEvidenceKind.PUBLICATION_ANNOTATION,
            disclosure=MiniatureDisclosure.EVIDENCE, label="Source-backed detail callout",
            member_node_ids=input_node.member_node_ids,
        ),
    ]
    enriched = publication.model_copy(update={"miniatures": miniatures})
    svg = render_svg(enriched, StageLayout().layout(enriched))

    for kind in PublicationMiniatureKind:
        assert f'data-miniature-kind="{kind.value}"' in svg
    assert svg.count('data-disclosure="evidence"') == 5
    assert publication_preflight(enriched, StageLayout().layout(enriched), svg).blocking is False


def test_resnet_is_reduced_to_a_residual_stage_with_a_skip_edge() -> None:
    exact = _exact(FIXTURES[1][0], FIXTURES[1][2], FIXTURES[1][3])
    publication = PublicationCompiler().compile(exact)
    scene = StageLayout().layout(publication)
    svg = render_svg(publication, scene)

    group = next(node for node in publication.nodes if node.kind.value == "residual_block")
    assert group.member_node_ids == [
        "node:residualblock.conv1",
        "node:residualblock.conv2",
        "node:residualblock.relu",
    ]
    assert any(edge.kind.value == "residual" for edge in publication.edges)
    assert publication.annotations[0].text == "Residual connection"
    assert publication.omitted_exact_edge_ids == [
        "edge:conv1->conv2:data",
        "edge:conv2->relu:data",
    ]
    assert validate_publication_semantics(publication, exact) == []
    assert publication_preflight(publication, scene, svg).blocking is False


def test_implementation_detail_is_explicitly_omitted_from_the_publication_view() -> None:
    exact = _exact(FIXTURES[0][0], FIXTURES[0][2], FIXTURES[0][3])
    detail = exact.node("node:encodermodel.norm").model_copy(
        update={
            "node_id": "node:encodermodel.reshape",
            "kind": NodeKind.FUNCTION,
            "op_type": "torch.reshape",
            "display_name": "reshape",
            "source_anchor_ids": [],
        }
    )
    enriched = exact.model_copy(update={"nodes": [*exact.nodes, detail]})
    publication = PublicationCompiler().compile(enriched)

    assert "node:encodermodel.reshape" in publication.omitted_exact_node_ids
    assert all("reshape" not in node.label.lower() for node in publication.nodes)
    assert validate_publication_semantics(publication, enriched) == []


def test_transformer_repeat_can_expand_as_a_visual_only_scene_state() -> None:
    exact = _exact(FIXTURES[0][0], FIXTURES[0][2], FIXTURES[0][3])
    publication = PublicationCompiler().compile(exact)
    group = next(node for node in publication.nodes if node.kind.value == "repeat_group")
    layout = StageLayout()
    collapsed = layout.layout(publication)
    expanded = layout.layout(publication, expanded_node_ids={group.node_id})
    svg = render_svg(publication, expanded)

    expanded_node = next(node for node in expanded.nodes if node.publication_node_id == group.node_id)
    assert publication.nodes == PublicationCompiler().compile(exact).nodes
    assert group.collapsed is True
    assert expanded_node.expanded is True
    assert expanded_node.height > next(
        node.height for node in collapsed.nodes if node.publication_node_id == group.node_id
    )
    assert expanded.height > collapsed.height
    assert svg.count('data-repeat-preview=') == 2
    assert publication_preflight(publication, expanded, svg).blocking is False
    assert expanded == layout.layout(publication, expanded_node_ids={group.node_id})
    assert svg == render_svg(publication, expanded)
    expected = ROOT / "fixtures" / "publication_transformer_v1" / "expected"
    assert expanded == VisualScene.model_validate_json((expected / "expanded-scene.json").read_bytes())
    assert svg.encode("utf-8") == (expected / "expanded-scene.svg").read_bytes()


def test_repeat_expansion_rejects_unknown_or_non_repeat_nodes() -> None:
    exact = _exact(FIXTURES[0][0], FIXTURES[0][2], FIXTURES[0][3])
    publication = PublicationCompiler().compile(exact)
    layout = StageLayout()

    with pytest.raises(ValueError, match="unknown publication node"):
        layout.layout(publication, expanded_node_ids={"publication-node:missing"})
    with pytest.raises(ValueError, match="only repeat groups"):
        layout.layout(publication, expanded_node_ids={"publication-node:input"})


def test_preflight_rejects_an_expanded_non_repeat_scene_node() -> None:
    exact = _exact(FIXTURES[0][0], FIXTURES[0][2], FIXTURES[0][3])
    publication = PublicationCompiler().compile(exact)
    scene = StageLayout().layout(publication)
    input_node = next(node for node in scene.nodes if node.publication_node_id == "publication-node:input")
    invalid_scene = scene.model_copy(
        update={
            "nodes": [
                node.model_copy(update={"expanded": True})
                if node.scene_node_id == input_node.scene_node_id
                else node
                for node in scene.nodes
            ]
        }
    )

    report = publication_preflight(publication, invalid_scene, render_svg(publication, invalid_scene))
    assert report.blocking is True
    assert [issue.code for issue in report.issues] == ["EXPANDED_NODE_NOT_REPEAT_GROUP"]


@pytest.mark.parametrize(("source_fixture", "publication_fixture", "project_id", "entrypoint"), FIXTURES)
def test_publication_goldens_are_exact_and_preflight_clean(
    source_fixture: str,
    publication_fixture: str,
    project_id: str,
    entrypoint: str,
) -> None:
    exact = _exact(source_fixture, project_id, entrypoint)
    publication = PublicationCompiler().compile(exact)
    scene = StageLayout().layout(publication)
    svg = render_svg(publication, scene)
    expected = ROOT / "fixtures" / publication_fixture / "expected"

    assert publication == PublicationIR.model_validate_json((expected / "publication.json").read_bytes())
    assert scene == VisualScene.model_validate_json((expected / "scene.json").read_bytes())
    assert svg.encode("utf-8") == (expected / "scene.svg").read_bytes()
    assert publication_preflight(publication, scene, svg).blocking is False


def test_publication_documents_are_canonical_json_and_svg_is_deterministic() -> None:
    exact = _exact("transformer_static_v1", "fixture:transformer_static_v1", "model.py:EncoderModel")
    compiler = PublicationCompiler()
    first = compiler.compile(exact)
    second = compiler.compile(exact)
    first_scene = StageLayout().layout(first)
    second_scene = StageLayout().layout(second)

    assert first.model_dump_json() == second.model_dump_json()
    assert first_scene.model_dump_json() == second_scene.model_dump_json()
    assert render_svg(first, first_scene) == render_svg(second, second_scene)
    for path in ROOT.glob("fixtures/publication_*_v1/expected/*.json"):
        assert path.read_bytes().endswith(b"\n")
        assert json.loads(path.read_text(encoding="utf-8"))
