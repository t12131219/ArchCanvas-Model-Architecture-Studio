from __future__ import annotations

from dataclasses import replace
from itertools import pairwise
from pathlib import Path

import pytest

from archcanvas_core.models import NodeKind, PublicationNode
from archcanvas_publication import (
    build_routing_graph,
    build_scene,
    build_visual_spec,
    compile_views,
    route_atomic_scene,
    route_graph,
    routing_input_digest,
)
from archcanvas_publication.glyphs import resolve_node_glyph
from archcanvas_publication.routing_fixtures import (
    build_routing_preview_fixture,
    routing_contract_signature,
    routing_preview_fixture_text,
)
from archcanvas_publication.routing_models import (
    EvidenceBackedRoutingGraph,
    PortSide,
    RoutingEdge,
    RoutingNode,
    RoutingPort,
    RoutingRect,
)
from archcanvas_python import analyze_project

ROOT = Path(__file__).resolve().parents[1]


def _simple_graph(*, with_obstacle: bool = False) -> EvidenceBackedRoutingGraph:
    nodes = [
        RoutingNode(
            routing_node_id="routing-node:source",
            scene_node_id="scene-node:source",
            view_node_id="view-node:source",
            canonical_node_ids=("node:source",),
            parent_routing_node_id=None,
            bounds=RoutingRect(x=20, y=90, width=80, height=50),
            semantic_kind="operator",
            collapsed=False,
            evidence_ids=("evidence:source",),
        ),
        RoutingNode(
            routing_node_id="routing-node:target",
            scene_node_id="scene-node:target",
            view_node_id="view-node:target",
            canonical_node_ids=("node:target",),
            parent_routing_node_id=None,
            bounds=RoutingRect(x=320, y=90, width=80, height=50),
            semantic_kind="operator",
            collapsed=False,
            evidence_ids=("evidence:target",),
        ),
    ]
    if with_obstacle:
        nodes.append(
            RoutingNode(
                routing_node_id="routing-node:obstacle",
                scene_node_id="scene-node:obstacle",
                view_node_id="view-node:obstacle",
                canonical_node_ids=("node:obstacle",),
                parent_routing_node_id=None,
                bounds=RoutingRect(x=160, y=70, width=90, height=90),
                semantic_kind="operator",
                collapsed=False,
                evidence_ids=("evidence:obstacle",),
            )
        )
    ports = (
        RoutingPort(
            routing_port_id="routing-port:source",
            owner_routing_node_id="routing-node:source",
            canonical_port_ids=("port:source.out",),
            direction="output",
            semantic_role="flow",
            semantic_channel="flow",
            allowed_sides=(PortSide.RIGHT,),
            preferred_side=PortSide.RIGHT,
            evidence_ids=("evidence:edge",),
        ),
        RoutingPort(
            routing_port_id="routing-port:target",
            owner_routing_node_id="routing-node:target",
            canonical_port_ids=("port:target.in",),
            direction="input",
            semantic_role="flow",
            semantic_channel="flow",
            allowed_sides=(PortSide.LEFT,),
            preferred_side=PortSide.LEFT,
            evidence_ids=("evidence:edge",),
        ),
    )
    edge = RoutingEdge(
        routing_edge_id="routing-edge:flow",
        view_edge_id="view-edge:flow",
        canonical_edge_ids=("edge:flow",),
        source_port_id="routing-port:source",
        target_port_id="routing-port:target",
        tensor_ids=("tensor:flow",),
        semantic_channel="flow",
        visual_relation="sequence",
        evidence_ids=("evidence:edge",),
    )
    return EvidenceBackedRoutingGraph(
        architecture_id="architecture:routing-test",
        view_id="view:routing-test",
        nodes=tuple(nodes),
        ports=ports,
        edges=(edge,),
    )


def test_route_kernel_is_orthogonal_deterministic_and_attached() -> None:
    graph = _simple_graph()
    first, first_receipt = route_graph(graph)
    second, second_receipt = route_graph(graph)

    assert first == second
    assert first_receipt.route_digest == second_receipt.route_digest
    assert first_receipt.input_digest == second_receipt.input_digest
    assert not first_receipt.metrics.has_hard_errors
    assert first[0].points[0].x == 100
    assert first[0].points[-1].x == 320
    assert all(
        left.x == right.x or left.y == right.y
        for left, right in pairwise(first[0].points)
    )


def test_route_kernel_avoids_unrelated_nodes() -> None:
    routes, receipt = route_graph(_simple_graph(with_obstacle=True))
    assert receipt.metrics.obstacle_intersection_count == 0
    assert receipt.metrics.invalid_endpoint_count == 0
    assert len(routes[0].points) >= 4


def test_routing_digest_is_independent_of_collection_order() -> None:
    graph = _simple_graph(with_obstacle=True)
    reordered = replace(
        graph,
        nodes=tuple(reversed(graph.nodes)),
        ports=tuple(reversed(graph.ports)),
    )
    assert routing_input_digest(graph) == routing_input_digest(reordered)
    assert route_graph(graph)[1].route_digest == route_graph(reordered)[1].route_digest


def test_cross_language_routing_preview_fixture_is_current() -> None:
    path = ROOT / "fixtures" / "routing" / "preview-contract-v1.json"
    fixture = build_routing_preview_fixture()
    assert path.read_text(encoding="utf-8") == routing_preview_fixture_text()
    edge = fixture["edge"]
    expected = fixture["expected"]
    assert isinstance(edge, dict)
    assert isinstance(expected, dict)
    assert expected["contract_signature"] == routing_contract_signature(
        str(edge["source_port_id"]),
        tuple(str(portal_id) for portal_id in edge["portal_ids"]),
        str(edge["target_port_id"]),
    )


def test_route_kernel_rejects_invalid_formal_contract() -> None:
    graph = _simple_graph()
    invalid_port = replace(graph.ports[0], allowed_sides=())
    invalid = replace(graph, ports=(invalid_port, *graph.ports[1:]))
    with pytest.raises(ValueError, match="no allowed side"):
        route_graph(invalid)


def test_formal_ir_adapter_preserves_edge_and_port_provenance() -> None:
    fixture = ROOT / "fixtures" / "tier_a" / "transformer"
    architecture = analyze_project(
        fixture,
        "model:Transformer",
        "inference",
        "eval",
        (fixture / "config.json").read_bytes(),
        fixture / "config.json",
        pattern_packs_enabled=True,
    ).architecture
    view = compile_views(architecture)[-1]
    scene = build_scene(view, build_visual_spec(view))
    graph = build_routing_graph(architecture, view, scene.nodes)

    assert {edge.view_edge_id for edge in graph.edges} == {
        edge.view_edge_id for edge in view.edges
    }
    assert {
        canonical_id for edge in graph.edges for canonical_id in edge.canonical_edge_ids
    } == set(view.canonical_edge_ids)
    architecture_port_ids = {
        port.port_id
        for node in architecture.nodes
        for port in [*node.input_ports, *node.output_ports]
    }
    assert all(
        canonical_port_id in architecture_port_ids
        for port in graph.ports
        for canonical_port_id in port.canonical_port_ids
    )
    assert all(edge.evidence_ids for edge in graph.edges)
    assert routing_input_digest(graph) == routing_input_digest(
        build_routing_graph(architecture, view, tuple(reversed(scene.nodes)))
    )
    nodes_by_id = {node.routing_node_id: node for node in graph.nodes}
    ports_by_id = {port.routing_port_id: port for port in graph.ports}
    edges_by_id = {edge.routing_edge_id: edge for edge in graph.edges}
    portals_by_id = {portal.portal_id: portal for portal in graph.portals}

    def ancestors(node_id: str) -> list[str]:
        result = [node_id]
        while nodes_by_id[result[-1]].parent_routing_node_id is not None:
            result.append(nodes_by_id[result[-1]].parent_routing_node_id or "")
        return result

    assert any(chain.portal_ids for chain in graph.portal_chains)
    for chain in graph.portal_chains:
        edge = edges_by_id[chain.routing_edge_id]
        source_path = ancestors(ports_by_id[edge.source_port_id].owner_routing_node_id)
        target_path = set(ancestors(ports_by_id[edge.target_port_id].owner_routing_node_id))
        lca = next(node_id for node_id in source_path if node_id in target_path)
        assert all(
            portals_by_id[portal_id].owner_routing_node_id != lca
            for portal_id in chain.portal_ids
        )

    routed_scene, routed_report = route_atomic_scene(architecture, view, scene)
    fixed_scene, fixed_report = route_atomic_scene(
        architecture,
        view,
        routed_scene,
        fixed_scene_edge_ids=frozenset({routed_scene.edges[0].scene_edge_id}),
    )
    assert routed_report.status == "routed"
    assert fixed_report.status == "routed"
    assert fixed_report.fixed_route_count == 1
    assert fixed_report.receipt is not None
    assert routed_report.receipt is not None
    assert fixed_report.receipt.input_digest != routed_report.receipt.input_digest
    assert fixed_report.receipt.route_digest == routed_report.receipt.route_digest
    assert fixed_scene.edges[0].points == routed_scene.edges[0].points


def test_glyph_resolver_consumes_unambiguous_validated_annotation() -> None:
    node = PublicationNode(
        view_node_id="view-node:annotated",
        canonical_node_ids=["node:annotated"],
        semantic_name="custom operation",
        kind=NodeKind.OPERATOR,
        parent_view_node_id="view-node:parent",
        collapsed=False,
        evidence_ids=["evidence:annotated"],
        attributes={
            "semantic_annotations": [
                {
                    "annotation_id": "annotation:custom",
                    "glyph": "attention",
                }
            ]
        },
    )
    assert resolve_node_glyph(node, True).glyph == "attention"

    exact_linear = node.model_copy(
        update={"attributes": {**node.attributes, "op_type": "nn.Linear"}}
    )
    assert resolve_node_glyph(exact_linear, True).glyph == "projection"


def test_production_python_does_not_depend_on_scene_visual_lab() -> None:
    forbidden = ("scene-visual-lab", "studio.prototypes", "studio/prototypes")
    for path in (ROOT / "src").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert not any(value in source for value in forbidden), path
