from __future__ import annotations

import json
from dataclasses import asdict

from .routing_kernel import ENGINE_NAME, ENGINE_VERSION, route_graph
from .routing_models import (
    BoundaryPortal,
    EvidenceBackedRoutingGraph,
    PortalChain,
    PortSide,
    RoutingEdge,
    RoutingNode,
    RoutingPort,
    RoutingRect,
)


def routing_contract_signature(
    source_port_id: str,
    portal_ids: tuple[str, ...],
    target_port_id: str,
) -> str:
    return " > ".join((source_port_id, *portal_ids, target_port_id))


def _preview_contract_graph() -> EvidenceBackedRoutingGraph:
    nodes = (
        RoutingNode(
            routing_node_id="routing-node:root",
            scene_node_id="root",
            view_node_id="view-node:root",
            canonical_node_ids=("node:root",),
            parent_routing_node_id=None,
            bounds=RoutingRect(x=0, y=0, width=640, height=360),
            semantic_kind="module_container",
            collapsed=False,
            evidence_ids=("evidence:root",),
        ),
        RoutingNode(
            routing_node_id="routing-node:source-group",
            scene_node_id="source-group",
            view_node_id="view-node:source-group",
            canonical_node_ids=("node:source-group",),
            parent_routing_node_id="routing-node:root",
            bounds=RoutingRect(x=20, y=40, width=260, height=260),
            semantic_kind="module_container",
            collapsed=False,
            evidence_ids=("evidence:source-group",),
        ),
        RoutingNode(
            routing_node_id="routing-node:source",
            scene_node_id="source",
            view_node_id="view-node:source",
            canonical_node_ids=("node:source",),
            parent_routing_node_id="routing-node:source-group",
            bounds=RoutingRect(x=80, y=140, width=80, height=48),
            semantic_kind="operator",
            collapsed=False,
            evidence_ids=("evidence:source",),
        ),
        RoutingNode(
            routing_node_id="routing-node:target-group",
            scene_node_id="target-group",
            view_node_id="view-node:target-group",
            canonical_node_ids=("node:target-group",),
            parent_routing_node_id="routing-node:root",
            bounds=RoutingRect(x=360, y=40, width=260, height=260),
            semantic_kind="module_container",
            collapsed=False,
            evidence_ids=("evidence:target-group",),
        ),
        RoutingNode(
            routing_node_id="routing-node:target",
            scene_node_id="target",
            view_node_id="view-node:target",
            canonical_node_ids=("node:target",),
            parent_routing_node_id="routing-node:target-group",
            bounds=RoutingRect(x=460, y=160, width=90, height=56),
            semantic_kind="operator",
            collapsed=False,
            evidence_ids=("evidence:target",),
        ),
    )
    source_port = RoutingPort(
        routing_port_id="routing-port:source",
        owner_routing_node_id="routing-node:source",
        canonical_port_ids=("port:source.out",),
        direction="output",
        semantic_role="flow",
        semantic_channel="flow",
        allowed_sides=(PortSide.RIGHT,),
        preferred_side=PortSide.RIGHT,
        evidence_ids=("evidence:edge",),
    )
    target_port = RoutingPort(
        routing_port_id="routing-port:target",
        owner_routing_node_id="routing-node:target",
        canonical_port_ids=("port:target.in",),
        direction="input",
        semantic_role="flow",
        semantic_channel="flow",
        allowed_sides=(PortSide.LEFT,),
        preferred_side=PortSide.LEFT,
        evidence_ids=("evidence:edge",),
    )
    edge = RoutingEdge(
        routing_edge_id="routing-edge:flow",
        view_edge_id="view-edge:flow",
        canonical_edge_ids=("edge:flow",),
        source_port_id=source_port.routing_port_id,
        target_port_id=target_port.routing_port_id,
        tensor_ids=("tensor:flow",),
        semantic_channel="flow",
        visual_relation="sequence",
        evidence_ids=("evidence:edge",),
    )
    source_portal = BoundaryPortal(
        portal_id="routing-portal:source-group:flow:output",
        owner_routing_node_id="routing-node:source-group",
        child_routing_node_id="routing-node:source",
        direction="output",
        canonical_edge_ids=edge.canonical_edge_ids,
    )
    target_portal = BoundaryPortal(
        portal_id="routing-portal:target-group:flow:input",
        owner_routing_node_id="routing-node:target-group",
        child_routing_node_id="routing-node:target",
        direction="input",
        canonical_edge_ids=edge.canonical_edge_ids,
    )
    chain = PortalChain(
        routing_edge_id=edge.routing_edge_id,
        source_port_id=source_port.routing_port_id,
        portal_ids=(source_portal.portal_id, target_portal.portal_id),
        target_port_id=target_port.routing_port_id,
    )
    return EvidenceBackedRoutingGraph(
        architecture_id="architecture:routing-preview-contract",
        view_id="view:routing-preview-contract",
        nodes=nodes,
        ports=(source_port, target_port),
        edges=(edge,),
        portals=(source_portal, target_portal),
        portal_chains=(chain,),
    )


def build_routing_preview_fixture() -> dict[str, object]:
    graph = _preview_contract_graph()
    routes, receipt = route_graph(graph)
    route = routes[0]
    nodes_by_id = {node.routing_node_id: node for node in graph.nodes}
    ports_by_id = {port.routing_port_id: port for port in graph.ports}
    source_node = nodes_by_id[ports_by_id[route.source_port_id].owner_routing_node_id]
    target_node = nodes_by_id[ports_by_id[route.target_port_id].owner_routing_node_id]
    scene_id_by_routing_id = {
        node.routing_node_id: node.scene_node_id for node in graph.nodes
    }
    nodes = []
    for node in graph.nodes:
        row: dict[str, object] = {
            "scene_node_id": node.scene_node_id,
            "shape": "container" if node.semantic_kind == "module_container" else "rect",
            "bounds": asdict(node.bounds),
        }
        if node.parent_routing_node_id is not None:
            row["parent_scene_node_id"] = scene_id_by_routing_id[
                node.parent_routing_node_id
            ]
        nodes.append(row)
    source_side = ports_by_id[route.source_port_id].preferred_side
    target_side = ports_by_id[route.target_port_id].preferred_side
    assert source_side is not None and target_side is not None
    return {
        "schema_version": "1.0",
        "engine": ENGINE_NAME,
        "engine_version": ENGINE_VERSION,
        "nodes": nodes,
        "edge": {
            "routing_edge_id": route.routing_edge_id,
            "source_scene_node_id": source_node.scene_node_id,
            "target_scene_node_id": target_node.scene_node_id,
            "source_port_id": route.source_port_id,
            "target_port_id": route.target_port_id,
            "portal_ids": list(route.portal_ids),
            "points": [asdict(point) for point in route.points],
            "route_digest": receipt.route_digest,
        },
        "expected": {
            "source_side": source_side.value,
            "target_side": target_side.value,
            "contract_signature": routing_contract_signature(
                route.source_port_id,
                route.portal_ids,
                route.target_port_id,
            ),
        },
        "preview": {
            "source": {
                "x": source_node.bounds.x + 40,
                "y": source_node.bounds.y + 25,
            }
        },
    }


def routing_preview_fixture_text() -> str:
    return json.dumps(
        build_routing_preview_fixture(),
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ) + "\n"
