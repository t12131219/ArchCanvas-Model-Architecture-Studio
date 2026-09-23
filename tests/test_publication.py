from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pytest

from archcanvas_publication import (
    build_scene,
    build_visual_spec,
    compile_views,
    render_html,
    render_svg,
    validate_geometry,
    validate_publication,
)
from archcanvas_python import analyze_project

ROOT = Path(__file__).resolve().parents[1]
PROFILES = [
    ("transformer", "model:Transformer", "inference", "dual-lane"),
    ("autoformer", "models.Autoformer:Model", "long_term_forecast", "dual-lane"),
    ("itransformer", "model.iTransformer:Model", "long_term_forecast", "single-lane"),
    ("patchtst", "models.PatchTST:Model", "long_term_forecast", "dual-backbone"),
    ("timemixer", "models.TimeMixer:Model", "long_term_forecast", "multiscale-ladder"),
]


@lru_cache(maxsize=10)
def _architecture(fixture_name: str, entrypoint: str, task: str, patterns: bool):
    fixture = ROOT / "fixtures" / "tier_a" / fixture_name
    return analyze_project(
        fixture,
        entrypoint,
        task,
        "eval",
        (fixture / "config.json").read_bytes(),
        fixture / "config.json",
        pattern_packs_enabled=patterns,
    ).architecture


@pytest.mark.parametrize(
    ("fixture_name", "entrypoint", "task", "layout_family"), PROFILES
)
def test_specialized_profiles_compile_l1_l4_and_pass_geometry(
    fixture_name: str, entrypoint: str, task: str, layout_family: str
) -> None:
    ir = _architecture(fixture_name, entrypoint, task, True)
    views = compile_views(ir)
    gates, diagnostics = validate_publication(ir, views)
    assert [view.level for view in views] == ["L1", "L2", "L3", "L4"]
    assert {view.layout_family for view in views} == {layout_family}
    assert gates[0].status == "passed"
    assert not diagnostics
    for view in views:
        spec = build_visual_spec(view)
        scene = build_scene(view, spec)
        gate, geometry_diagnostics = validate_geometry(scene)
        assert gate.status == "passed", (view.level, geometry_diagnostics)
        assert not geometry_diagnostics


@pytest.mark.parametrize(("fixture_name", "entrypoint", "task", "_"), PROFILES)
def test_generic_fallback_compiles_and_renders_without_family_assumptions(
    fixture_name: str, entrypoint: str, task: str, _: str
) -> None:
    ir = _architecture(fixture_name, entrypoint, task, False)
    views = compile_views(ir)
    gates, diagnostics = validate_publication(ir, views)
    assert gates[0].status == "passed"
    assert not diagnostics
    assert {view.layout_family for view in views} == {"generic-dag"}
    for view in (views[0], views[-1]):
        spec = build_visual_spec(view)
        scene = build_scene(view, spec)
        geometry_gate, geometry_diagnostics = validate_geometry(scene)
        assert geometry_gate.status == "passed", geometry_diagnostics
        assert "architecture_profile" not in render_svg(scene)


def test_l4_and_progressive_views_share_exact_canonical_sets() -> None:
    ir = _architecture("transformer", "model:Transformer", "inference", True)
    views = compile_views(ir)
    l4 = views[-1]
    assert all(len(node.canonical_node_ids) == 1 for node in l4.nodes)
    assert all(len(edge.canonical_edge_ids) == 1 for edge in l4.edges)
    assert not l4.collapsed_edge_ids
    for view in views[:-1]:
        assert set(view.canonical_node_ids) == set(l4.canonical_node_ids)
        assert set(view.canonical_edge_ids) == set(l4.canonical_edge_ids)
        assert set(view.canonical_tensor_ids) == set(l4.canonical_tensor_ids)
        assert set(view.canonical_port_ids) == set(l4.canonical_port_ids)


def test_publication_gate_rejects_missing_canonical_mapping() -> None:
    ir = _architecture("transformer", "model:Transformer", "inference", True)
    views = compile_views(ir)
    first = views[0]
    node = next(node for node in first.nodes if len(node.canonical_node_ids) > 1)
    damaged_node = node.model_copy(update={"canonical_node_ids": node.canonical_node_ids[1:]})
    damaged = first.model_copy(
        update={"nodes": [damaged_node if item == node else item for item in first.nodes]}
    )
    gates, diagnostics = validate_publication(ir, [damaged, *views[1:]])
    assert gates[0].status == "failed"
    assert any(item.code == "PUBLICATION_NODE_MAPPING_INVALID" for item in diagnostics)


def test_geometry_gate_rejects_overlap() -> None:
    ir = _architecture("transformer", "model:Transformer", "inference", True)
    view = compile_views(ir)[0]
    scene = build_scene(view, build_visual_spec(view))
    children = [node for node in scene.nodes if node.parent_scene_node_id]
    moved = children[1].model_copy(update={"bounds": children[0].bounds})
    damaged = scene.model_copy(
        update={"nodes": [moved if node == children[1] else node for node in scene.nodes]}
    )
    gate, diagnostics = validate_geometry(damaged)
    assert gate.status == "failed"
    assert any(item.code == "GEOMETRY_NODE_OVERLAP" for item in diagnostics)


def test_geometry_gate_rejects_edge_through_unrelated_opaque_node() -> None:
    ir = _architecture("transformer", "model:Transformer", "inference", True)
    view = compile_views(ir)[0]
    scene = build_scene(view, build_visual_spec(view))
    edge = scene.edges[0]
    point = edge.points[1]
    blocker = next(
        node
        for node in scene.nodes
        if node.parent_scene_node_id
        and node.scene_node_id
        not in {edge.source_scene_node_id, edge.target_scene_node_id}
    )
    moved = blocker.model_copy(
        update={
            "shape": "opaque",
            "bounds": blocker.bounds.model_copy(
                update={"x": max(0.0, point.x - 10.0), "y": max(0.0, point.y - 10.0)}
            ),
        }
    )
    damaged = scene.model_copy(
        update={"nodes": [moved if node == blocker else node for node in scene.nodes]}
    )
    gate, diagnostics = validate_geometry(damaged)
    assert gate.status == "failed"
    assert any(item.code == "GEOMETRY_EDGE_THROUGH_OPAQUE" for item in diagnostics)


def test_svg_and_html_share_scene_and_html_is_self_contained() -> None:
    ir = _architecture("autoformer", "models.Autoformer:Model", "long_term_forecast", True)
    view = compile_views(ir)[0]
    spec = build_visual_spec(view)
    scene = build_scene(view, spec)
    svg = render_svg(scene)
    page = render_html(scene, view, spec)
    assert scene.scene_id in svg and scene.scene_id in page
    assert "data-canonical-node-ids" in svg
    assert "linearGradient" not in svg and "filter=" not in svg
    assert "https://" not in page and "src=\"http" not in page
    for control in ("search", "upstream", "downstream", "zoom-in", "theme", "details"):
        assert f'id="{control}"' in page
    assert json.loads(page.split('<script id="archcanvas-data" type="application/json">', 1)[1].split("</script>", 1)[0])
