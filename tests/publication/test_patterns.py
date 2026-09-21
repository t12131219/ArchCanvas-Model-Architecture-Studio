from __future__ import annotations

from pathlib import Path

from archcanvas_publication import PublicationCompiler, StageLayout
from archcanvas_publication.patterns import PublicationPatternRegistry
from archcanvas_pytorch.static import PyTorchProjectStaticAdapter
from archcanvas_renderer import publication_preflight, render_svg

ROOT = Path(__file__).resolve().parents[2]


def _timesnet_exact():
    return PyTorchProjectStaticAdapter().analyze(
        ROOT / "fixtures" / "timesnet_pattern_v1" / "source",
        project_id="fixture:timesnet-pattern-v1",
        entrypoint="model.py:TimesNet",
        resolved_config={"e_layers": 2, "task_name": "long_term_forecast", "top_k": 2},
    )


def _transformer_exact():
    return PyTorchProjectStaticAdapter().analyze(
        ROOT / "fixtures" / "transformer_static_v1" / "source",
        project_id="fixture:transformer-pattern-v1",
        entrypoint="model.py:EncoderModel",
        resolved_config={"depth": 3},
    )


def test_timesnet_pattern_requires_and_carries_the_complete_source_signature() -> None:
    source, exact = _timesnet_exact()

    matches = PublicationPatternRegistry().match(exact)

    assert len(matches) == 1
    match = matches[0]
    assert match.pattern_id == "timesnet_v1"
    assert match.confidence.value == "confirmed"
    assert match.member_node_ids == ["node:timesnet.model"]
    assert match.resolved_parameters == {"e_layers": 2, "task_name": "long_term_forecast", "top_k": 2}
    assert len(match.source_anchor_ids) == 8
    assert set(match.source_anchor_ids) <= {anchor.anchor_id for anchor in source.anchors}
    assert set(match.source_anchor_ids) <= set(exact.node("node:timesnet.model").source_anchor_ids)


def test_timesnet_pattern_compiles_to_an_honest_repeat_group_and_schematic_only_preview() -> None:
    _, exact = _timesnet_exact()

    publication = PublicationCompiler().compile(exact)
    group = next(node for node in publication.nodes if node.node_id == "publication-node:timesnet-blocks")
    scene = StageLayout().layout(publication)
    report = publication_preflight(publication, scene, render_svg(publication, scene))

    assert group.label == "TimesBlock"
    assert group.member_node_ids == ["node:timesnet.model"]
    assert publication.annotations[0].text == "TimesBlock repeated 2 times"
    assert [(miniature.miniature_id, miniature.disclosure.value) for miniature in publication.miniatures] == [
        ("miniature:input-flow-schematic", "illustrative"),
        ("miniature:timesnet-period-schematic", "illustrative"),
        ("miniature:timesnet-detail-inset", "evidence"),
    ]
    assert report.blocking is False


def test_timesnet_pattern_fails_closed_when_a_required_source_marker_is_missing() -> None:
    _, exact = _timesnet_exact()
    evidence = exact.metadata["publication_pattern_evidence"]
    assert isinstance(evidence, list)
    incomplete = [{**evidence[0], "markers": {"fft": "anchor:missing"}}]
    incomplete_exact = exact.model_copy(
        update={"metadata": {**exact.metadata, "publication_pattern_evidence": incomplete}}
    )

    assert PublicationPatternRegistry().match(incomplete_exact) == []
    assert all(node.label != "TimesBlock" for node in PublicationCompiler().compile(incomplete_exact).nodes)


def test_transformer_encoder_pattern_requires_repeat_norm_and_head_evidence() -> None:
    source, exact = _transformer_exact()

    matches = PublicationPatternRegistry().match(exact)

    assert len(matches) == 1
    match = matches[0]
    assert match.pattern_id == "transformer_encoder_layer_v1"
    assert match.confidence.value == "confirmed"
    assert match.member_node_ids == ["node:encodermodel.layers"]
    assert set(match.source_anchor_ids) <= {anchor.anchor_id for anchor in source.anchors}
    assert set(match.source_anchor_ids) <= set(exact.node("node:encodermodel.layers").source_anchor_ids)
    assert match.detail_template == "transformer_encoder_layer_detail_v1"


def test_transformer_encoder_pattern_fails_closed_without_forecast_head() -> None:
    _, exact = _transformer_exact()
    evidence = exact.metadata["publication_pattern_evidence"]
    assert isinstance(evidence, list)
    incomplete = [{**evidence[0], "markers": {"layer_construction": "anchor:missing"}}]
    incomplete_exact = exact.model_copy(
        update={"metadata": {**exact.metadata, "publication_pattern_evidence": incomplete}}
    )

    assert PublicationPatternRegistry().match(incomplete_exact) == []
