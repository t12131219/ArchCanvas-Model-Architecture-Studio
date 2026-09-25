from __future__ import annotations

import json
from functools import lru_cache
from itertools import pairwise
from pathlib import Path

import pytest

from archcanvas_publication import (
    LAYOUT_MODES,
    build_scene,
    build_visual_spec,
    compile_hierarchy,
    compile_views,
    render_html,
    render_pdf,
    render_png,
    render_svg,
    validate_geometry,
    validate_publication,
)
from archcanvas_python import analyze_project

ROOT = Path(__file__).resolve().parents[1]
PROFILES = [
    ("transformer", "model:Transformer", "inference"),
    ("autoformer", "models.Autoformer:Model", "long_term_forecast"),
    ("itransformer", "model.iTransformer:Model", "long_term_forecast"),
    ("patchtst", "models.PatchTST:Model", "long_term_forecast"),
    ("timemixer", "models.TimeMixer:Model", "long_term_forecast"),
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
    ("fixture_name", "entrypoint", "task"), PROFILES
)
def test_topology_adapts_every_tier_a_model_and_passes_geometry(
    fixture_name: str, entrypoint: str, task: str
) -> None:
    ir = _architecture(fixture_name, entrypoint, task, True)
    views = compile_views(ir)
    gates, diagnostics = validate_publication(ir, views)
    assert views[0].fully_expanded is False
    assert views[-1].fully_expanded is True
    assert all(view.max_depth >= 2 for view in views)
    assert {view.layout_family for view in views} == {"dual-lane"}
    hierarchy = compile_hierarchy(ir)
    assert len(
        [
            node
            for node in hierarchy.nodes
            if node.parent_hierarchy_node_id == hierarchy.root_node_id
        ]
    ) <= 6
    assert gates[0].status == "passed"
    assert not diagnostics
    for view in views:
        spec = build_visual_spec(view)
        scene = build_scene(view, spec)
        gate, geometry_diagnostics = validate_geometry(scene)
        assert gate.status == "passed", (view.projection_id, geometry_diagnostics)
        assert not geometry_diagnostics


@pytest.mark.parametrize(("fixture_name", "entrypoint", "task"), PROFILES)
def test_generic_fallback_compiles_and_renders_without_family_assumptions(
    fixture_name: str, entrypoint: str, task: str
) -> None:
    ir = _architecture(fixture_name, entrypoint, task, False)
    views = compile_views(ir)
    gates, diagnostics = validate_publication(ir, views)
    assert gates[0].status == "passed"
    assert not diagnostics
    assert {view.layout_family for view in views} == {"dual-lane"}
    for view in (views[0], views[-1]):
        spec = build_visual_spec(view)
        scene = build_scene(view, spec)
        geometry_gate, geometry_diagnostics = validate_geometry(scene)
        assert geometry_gate.status == "passed", geometry_diagnostics
        assert "architecture_profile" not in render_svg(scene)


def test_layout_is_invariant_to_architecture_profile_and_model_name() -> None:
    ir = _architecture("itransformer", "model.iTransformer:Model", "long_term_forecast", True)
    original = compile_hierarchy(ir)
    renamed = ir.model_copy(
        update={
            "architecture_id": "architecture:unseen-adaptive-model",
            "nodes": [
                node.model_copy(
                    update={
                        "semantic_name": (
                            "Unseen root architecture"
                            if node.parent_id is None
                            else node.semantic_name
                        ),
                        "attributes": {
                            **node.attributes,
                            "architecture_profile": "future-family-v17",
                        },
                    }
                )
                for node in ir.nodes
            ],
        }
    )
    renamed_hierarchy = compile_hierarchy(renamed)
    assert compile_views(renamed)[0].layout_family == compile_views(ir)[0].layout_family
    assert {
        node.semantic_name
        for node in renamed_hierarchy.nodes
        if node.parent_hierarchy_node_id == renamed_hierarchy.root_node_id
    } == {
        node.semantic_name
        for node in original.nodes
        if node.parent_hierarchy_node_id == original.root_node_id
    }


def test_builtin_layout_modes_preserve_identity_and_pass_geometry() -> None:
    ir = _architecture("transformer", "model:Transformer", "inference", True)
    views = compile_views(ir)
    coordinate_signatures: set[tuple[tuple[str, float, float], ...]] = set()

    for view in (views[0], views[-1]):
        expected_nodes = {node.view_node_id for node in view.nodes}
        expected_edges = {edge.view_edge_id for edge in view.edges}
        for layout_mode in LAYOUT_MODES:
            scene = build_scene(view, build_visual_spec(view), layout_mode)
            gate, diagnostics = validate_geometry(scene)
            assert gate.status == "passed", (layout_mode, diagnostics)
            assert {node.view_node_id for node in scene.nodes} == expected_nodes
            assert {edge.view_edge_id for edge in scene.edges} == expected_edges
            if view is views[0] and layout_mode != "auto":
                coordinate_signatures.add(
                    tuple(
                        sorted(
                            (
                                node.view_node_id,
                                node.bounds.x,
                                node.bounds.y,
                            )
                            for node in scene.nodes
                        )
                    )
                )

    assert len(coordinate_signatures) == len(LAYOUT_MODES) - 1
    with pytest.raises(ValueError, match="unknown layout mode"):
        build_scene(views[0], build_visual_spec(views[0]), "spiral")


@pytest.mark.parametrize("view_index", [0, -1])
def test_force_radial_and_orthogonal_layouts_are_deterministic_for_other_models(
    view_index: int,
) -> None:
    ir = _architecture("itransformer", "model.iTransformer:Model", "long_term_forecast", True)
    view = compile_views(ir)[view_index]
    spec = build_visual_spec(view)

    for layout_mode in ("force-directed", "radial", "orthogonal"):
        first = build_scene(view, spec, layout_mode)
        second = build_scene(view, spec, layout_mode)
        assert first.model_dump(mode="json") == second.model_dump(mode="json")
        gate, diagnostics = validate_geometry(first)
        assert gate.status == "passed", (layout_mode, diagnostics)


def test_full_and_collapsed_projections_share_exact_canonical_sets() -> None:
    ir = _architecture("transformer", "model:Transformer", "inference", True)
    views = compile_views(ir)
    full = views[-1]
    executable_nodes = [node for node in full.nodes if node.canonical_node_ids]
    structural_nodes = [node for node in full.nodes if not node.canonical_node_ids]
    assert all(len(node.canonical_node_ids) == 1 for node in executable_nodes)
    assert structural_nodes
    assert all(node.kind.value == "module_container" for node in structural_nodes)
    assert all(len(edge.canonical_edge_ids) == 1 for edge in full.edges)
    assert not full.collapsed_edge_ids
    for view in views[:-1]:
        assert set(view.canonical_node_ids) == set(full.canonical_node_ids)
        assert set(view.canonical_edge_ids) == set(full.canonical_edge_ids)
        assert set(view.canonical_tensor_ids) == set(full.canonical_tensor_ids)
        assert set(view.canonical_port_ids) == set(full.canonical_port_ids)


def test_visual_relations_and_glyphs_are_derived_from_exact_ir() -> None:
    ir = _architecture("transformer", "model:Transformer", "inference", True)
    view = compile_views(ir)[-1]
    scene = build_scene(view, build_visual_spec(view))
    view_by_canonical = {
        canonical_id: node.view_node_id
        for node in view.nodes
        for canonical_id in node.canonical_node_ids
    }

    def relation(source: str, target: str) -> str:
        edge = next(
            edge
            for edge in view.edges
            if edge.source_view_node_id == view_by_canonical[source]
            and edge.target_view_node_id == view_by_canonical[target]
        )
        assert edge.evidence_ids
        return edge.visual_relation.value

    assert relation("node:input.src", "node:encoder_q_proj") == "parallel-branch"
    assert relation("node:encoder_q_proj", "node:enc_q_split") == "shape-transform"
    assert relation("node:enc_q_split", "node:enc_scores_raw") == "merge"
    assert relation("node:encoder_out_proj", "node:enc_residual") == "residual"
    assert relation("node:input.src", "node:enc_residual") == "residual"

    shapes = {
        canonical_id: node.shape
        for node in scene.nodes
        for canonical_id in node.canonical_node_ids
    }
    assert shapes["node:encoder_q_proj"] == "projection"
    assert shapes["node:enc_q_split"] == "transform"
    assert shapes["node:enc_residual"] == "merge"
    assert shapes["node:encoder_norm"] == "normalization"
    svg = render_svg(scene)
    assert 'data-visual-relation="parallel-branch"' in svg
    assert 'data-visual-relation="shape-transform"' in svg


def test_transformer_tree_extremes_preserve_portrait_reading_order() -> None:
    ir = _architecture("transformer", "model:Transformer", "inference", True)
    collapsed, fully_expanded = compile_views(ir)[0], compile_views(ir)[-1]
    collapsed_scene = build_scene(collapsed, build_visual_spec(collapsed))
    collapsed_by_name = {
        node.semantic_name.lower(): next(
            scene_node
            for scene_node in collapsed_scene.nodes
            if scene_node.view_node_id == node.view_node_id
        )
        for node in collapsed.nodes
        if node.semantic_name.lower() in {"encoder", "decoder", "inputs", "ffn", "output"}
    }
    assert collapsed_by_name["encoder"].bounds.x < collapsed_by_name["decoder"].bounds.x
    assert collapsed_by_name["inputs"].bounds.y > collapsed_by_name["encoder"].bounds.y
    assert collapsed_by_name["output"].bounds.y < collapsed_by_name["ffn"].bounds.y
    assert collapsed_by_name["ffn"].bounds.y < collapsed_by_name["decoder"].bounds.y

    expanded_scene = build_scene(fully_expanded, build_visual_spec(fully_expanded))
    expanded_by_canonical = {
        canonical_id: scene_node
        for scene_node in expanded_scene.nodes
        for canonical_id in scene_node.canonical_node_ids
    }
    assert expanded_scene.paper_height > expanded_scene.paper_width
    assert expanded_scene.paper_height < expanded_scene.paper_width * 2.2
    assert expanded_by_canonical["node:input.src"].bounds.y > expanded_by_canonical[
        "node:output.model"
    ].bounds.y
    assert any(
        edge.points[0].y > edge.points[-1].y for edge in expanded_scene.edges
    )


def test_autoformer_reuses_transformer_semantic_overview_and_owns_modules() -> None:
    ir = _architecture("autoformer", "models.Autoformer:Model", "long_term_forecast", True)
    hierarchy = compile_hierarchy(ir)
    root_children = [
        node
        for node in hierarchy.nodes
        if node.parent_hierarchy_node_id == hierarchy.root_node_id
    ]
    root_names = {node.semantic_name.lower() for node in root_children}
    assert root_names == {"inputs", "decomposition", "encoder", "decoder", "output"}
    assert sum(node.semantic_name.lower() == "encoder" for node in root_children) == 1
    assert sum(node.semantic_name.lower() == "decoder" for node in root_children) == 1
    by_name = {node.semantic_name: node for node in hierarchy.nodes}
    encoder_id = by_name["Encoder"].hierarchy_node_id
    decoder_id = by_name["Decoder"].hierarchy_node_id
    assert any(
        node.parent_hierarchy_node_id == encoder_id
        for node in hierarchy.nodes
        if node.semantic_name == "DataEmbedding_wo_pos"
    )
    assert any(
        node.parent_hierarchy_node_id == decoder_id
        for node in hierarchy.nodes
        if node.semantic_name == "DataEmbedding_wo_pos"
    )
    assert any(
        node.parent_hierarchy_node_id == decoder_id
        for node in hierarchy.nodes
        if node.semantic_name == "Decoder Layer"
    )

    collapsed, expanded = compile_views(ir)
    assert [
        node.semantic_name.lower()
        for node in collapsed.nodes
        if node.parent_view_node_id == "viewnode:model"
    ] == ["inputs", "decomposition", "encoder", "decoder", "output"]
    collapsed_scene = build_scene(collapsed, build_visual_spec(collapsed))
    summary_labels = {
        node.label_lines[0].lower()
        for node in collapsed_scene.nodes
        if node.parent_scene_node_id == "scenenode:model"
    }
    assert summary_labels == {"inputs", "decomposition", "encoder", "decoder", "output head"}
    assert collapsed_scene.layout_family == "dual-lane-vertical"
    collapsed_gate, collapsed_diagnostics = validate_geometry(collapsed_scene)
    assert collapsed_gate.status == "passed", collapsed_diagnostics

    expanded_scene = build_scene(expanded, build_visual_spec(expanded))
    assert expanded_scene.layout_family == "dual-lane-vertical"
    expanded_gate, expanded_diagnostics = validate_geometry(expanded_scene)
    assert expanded_gate.status == "passed", expanded_diagnostics


def test_transformer_expanded_ports_and_container_borders_have_clearance() -> None:
    ir = _architecture("transformer", "model:Transformer", "inference", True)
    fully_expanded = compile_views(ir)[-1]
    scene = build_scene(fully_expanded, build_visual_spec(fully_expanded))

    incoming: dict[str, list] = {}
    for edge in scene.edges:
        incoming.setdefault(edge.target_scene_node_id, []).append(edge)
    shared_targets = [edges for edges in incoming.values() if len(edges) > 1]
    assert shared_targets
    for edges in shared_targets:
        endpoints = {(edge.points[-1].x, edge.points[-1].y) for edge in edges}
        assert len(endpoints) == len(edges)

    containers = [
        node
        for node in scene.nodes
        if node.shape == "container" and node.parent_scene_node_id is not None
    ]
    siblings: dict[str, list] = {}
    for container in containers:
        siblings.setdefault(container.parent_scene_node_id, []).append(container)
    qkv_groups = []
    for group in siblings.values():
        qkv = [node for node in group if " ".join(node.label_lines).lower() in {"q", "k", "v"}]
        if len(qkv) == 3:
            qkv_groups.append(sorted(qkv, key=lambda node: node.bounds.x))
    assert qkv_groups
    for group in qkv_groups:
        for left, right in pairwise(group):
            assert right.bounds.x - (left.bounds.x + left.bounds.width) >= 18.0

    for container in containers:
        children = [
            node
            for node in scene.nodes
            if node.parent_scene_node_id == container.scene_node_id
        ]
        if not children:
            continue
        assert min(child.bounds.x - container.bounds.x for child in children) >= 14.0
        assert min(child.bounds.y - container.bounds.y for child in children) >= 14.0
        assert min(
            container.bounds.x
            + container.bounds.width
            - child.bounds.x
            - child.bounds.width
            for child in children
        ) >= 14.0
        assert min(
            container.bounds.y
            + container.bounds.height
            - child.bounds.y
            - child.bounds.height
            for child in children
        ) >= 14.0

    assert 'markerWidth="5.5" markerHeight="5.5"' in render_svg(scene)


def test_fully_expanded_arrows_leave_sources_and_enter_targets() -> None:
    ir = _architecture("transformer", "model:Transformer", "inference", True)
    fully_expanded = compile_views(ir)[-1]
    scene = build_scene(fully_expanded, build_visual_spec(fully_expanded))
    nodes = {node.scene_node_id: node for node in scene.nodes}
    canonical_edges = {edge.edge_id: edge for edge in ir.edges}

    for edge in scene.edges:
        source_node = nodes[edge.source_scene_node_id]
        target_node = nodes[edge.target_scene_node_id]
        source = source_node.bounds
        target = target_node.bounds
        start, after_start = edge.points[0], edge.points[1]
        before_end, end = edge.points[-2], edge.points[-1]

        assert len(edge.canonical_edge_ids) == 1
        canonical = canonical_edges[edge.canonical_edge_ids[0]]
        assert canonical.producer_id in source_node.canonical_node_ids
        assert canonical.consumer_id in target_node.canonical_node_ids

        if start.y == pytest.approx(source.y):
            assert after_start.y < start.y, edge.scene_edge_id
        else:
            assert start.x == pytest.approx(source.x + source.width), edge.scene_edge_id
            assert after_start.x > start.x, edge.scene_edge_id

        if end.y == pytest.approx(target.y + target.height):
            assert before_end.y > end.y, edge.scene_edge_id
        else:
            assert end.x == pytest.approx(target.x), edge.scene_edge_id
            assert before_end.x < end.x, edge.scene_edge_id

        assert (start.x, start.y) != (after_start.x, after_start.y)
        assert (before_end.x, before_end.y) != (end.x, end.y)

    svg = render_svg(scene)
    assert svg.count('marker-end="url(#arrow)"') == len(scene.edges)


def test_hierarchy_depth_is_derived_and_not_capped() -> None:
    ir = _architecture("transformer", "model:Transformer", "inference", True)
    target = ir.nodes[1]
    deep = target.model_copy(
        update={
            "attributes": {
                **target.attributes,
                "module_path": "self.a.b.c.d.e.f.g.h.i.j.operator",
            }
        }
    )
    changed = ir.model_copy(
        update={"nodes": [deep if node == target else node for node in ir.nodes]}
    )
    hierarchy = compile_hierarchy(changed)
    assert hierarchy.max_depth >= 11


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


def test_png_and_pdf_are_derived_from_the_canonical_scene() -> None:
    ir = _architecture("autoformer", "models.Autoformer:Model", "long_term_forecast", True)
    view = compile_views(ir)[0]
    scene = build_scene(view, build_visual_spec(view))
    png = render_png(scene)
    pdf = render_pdf(scene)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert pdf.startswith(b"%PDF-")
    assert len(png) > 1000
    assert len(pdf) > 1000
