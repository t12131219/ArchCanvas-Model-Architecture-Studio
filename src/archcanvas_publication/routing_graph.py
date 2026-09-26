from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence

from archcanvas_core.models import ArchitectureIR, PublicationView, SceneNode

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


def _stable_suffix(*parts: str) -> str:
    payload = "\x1f".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _preferred_sides(source: RoutingRect, target: RoutingRect) -> tuple[PortSide, PortSide]:
    dx = target.center.x - source.center.x
    dy = target.center.y - source.center.y
    if abs(dx) >= abs(dy):
        return (
            (PortSide.RIGHT, PortSide.LEFT)
            if dx >= 0.0
            else (PortSide.LEFT, PortSide.RIGHT)
        )
    return (
        (PortSide.BOTTOM, PortSide.TOP)
        if dy >= 0.0
        else (PortSide.TOP, PortSide.BOTTOM)
    )


def _ancestors(
    node_id: str,
    nodes: dict[str, RoutingNode],
) -> list[str]:
    result = [node_id]
    seen = {node_id}
    cursor = nodes[node_id]
    while cursor.parent_routing_node_id is not None:
        parent_id = cursor.parent_routing_node_id
        if parent_id in seen or parent_id not in nodes:
            raise ValueError("routing scene containment is cyclic or references a missing parent")
        result.append(parent_id)
        seen.add(parent_id)
        cursor = nodes[parent_id]
    return result


def _portal_chain(
    edge: RoutingEdge,
    nodes: dict[str, RoutingNode],
    ports: dict[str, RoutingPort],
) -> tuple[list[BoundaryPortal], PortalChain]:
    source_id = ports[edge.source_port_id].owner_routing_node_id
    target_id = ports[edge.target_port_id].owner_routing_node_id
    source_path = _ancestors(source_id, nodes)
    target_path = _ancestors(target_id, nodes)
    target_ancestors = set(target_path)
    lca = next((node_id for node_id in source_path if node_id in target_ancestors), None)
    if lca is None:
        raise ValueError("routing endpoints do not share a scene root")

    portals: list[BoundaryPortal] = []
    portal_ids: list[str] = []

    source_lca_index = source_path.index(lca)
    for index in range(1, source_lca_index):
        owner_id = source_path[index]
        child_id = source_path[index - 1]
        portal_id = (
            f"routing-portal:{_stable_suffix(edge.routing_edge_id, owner_id, child_id, 'output')}"
        )
        portals.append(
            BoundaryPortal(
                portal_id=portal_id,
                owner_routing_node_id=owner_id,
                child_routing_node_id=child_id,
                direction="output",
                canonical_edge_ids=edge.canonical_edge_ids,
            )
        )
        portal_ids.append(portal_id)

    target_lca_index = target_path.index(lca)
    for owner_index in range(target_lca_index - 1, 0, -1):
        owner_id = target_path[owner_index]
        child_id = target_path[owner_index - 1]
        portal_id = (
            f"routing-portal:{_stable_suffix(edge.routing_edge_id, owner_id, child_id, 'input')}"
        )
        portals.append(
            BoundaryPortal(
                portal_id=portal_id,
                owner_routing_node_id=owner_id,
                child_routing_node_id=child_id,
                direction="input",
                canonical_edge_ids=edge.canonical_edge_ids,
            )
        )
        portal_ids.append(portal_id)

    return portals, PortalChain(
        routing_edge_id=edge.routing_edge_id,
        source_port_id=edge.source_port_id,
        portal_ids=tuple(portal_ids),
        target_port_id=edge.target_port_id,
    )


def build_routing_graph(
    architecture: ArchitectureIR,
    view: PublicationView,
    scene_nodes: Sequence[SceneNode],
) -> EvidenceBackedRoutingGraph:
    """Adapt authoritative IR, view projection, and scene bounds into routing input."""
    if architecture.architecture_id != view.architecture_id:
        raise ValueError("PublicationView does not belong to the ArchitectureIR")

    architecture_nodes = {node.node_id: node for node in architecture.nodes}
    architecture_edges = {edge.edge_id: edge for edge in architecture.edges}
    scene_by_view = {node.view_node_id: node for node in scene_nodes}
    if len(scene_by_view) != len(scene_nodes):
        raise ValueError("scene view node identifiers must be unique")

    view_by_canonical: dict[str, str] = {}
    for node in view.nodes:
        if node.view_node_id not in scene_by_view:
            raise ValueError(f"scene is missing view node {node.view_node_id}")
        for canonical_id in node.canonical_node_ids:
            if canonical_id in view_by_canonical:
                raise ValueError(f"canonical node {canonical_id} appears in multiple view nodes")
            if canonical_id not in architecture_nodes:
                raise ValueError(f"view references missing canonical node {canonical_id}")
            view_by_canonical[canonical_id] = node.view_node_id

    routing_id_by_scene = {
        node.scene_node_id: f"routing-node:{node.scene_node_id}"
        for node in scene_nodes
    }
    for node in scene_nodes:
        if (
            node.parent_scene_node_id is not None
            and node.parent_scene_node_id not in routing_id_by_scene
        ):
            raise ValueError(
                f"scene node {node.scene_node_id} references a missing parent"
            )
    view_nodes = {node.view_node_id: node for node in view.nodes}
    unexpected_scene_views = set(scene_by_view) - set(view_nodes)
    if unexpected_scene_views:
        unexpected = min(unexpected_scene_views)
        raise ValueError(f"scene references unknown view node {unexpected}")
    routing_nodes = tuple(
        sorted(
            (
                RoutingNode(
                    routing_node_id=routing_id_by_scene[node.scene_node_id],
                    scene_node_id=node.scene_node_id,
                    view_node_id=node.view_node_id,
                    canonical_node_ids=tuple(sorted(node.canonical_node_ids)),
                    parent_routing_node_id=(
                        routing_id_by_scene[node.parent_scene_node_id]
                        if node.parent_scene_node_id is not None
                        else None
                    ),
                    bounds=RoutingRect(
                        x=node.bounds.x,
                        y=node.bounds.y,
                        width=node.bounds.width,
                        height=node.bounds.height,
                    ),
                    semantic_kind=view_nodes[node.view_node_id].kind.value,
                    collapsed=view_nodes[node.view_node_id].collapsed,
                    evidence_ids=tuple(sorted(node.evidence_ids)),
                )
                for node in scene_nodes
            ),
            key=lambda node: node.routing_node_id,
        )
    )
    routing_nodes_by_id = {node.routing_node_id: node for node in routing_nodes}

    ports_by_id: dict[str, RoutingPort] = {}
    routing_edges: list[RoutingEdge] = []
    for view_edge in sorted(view.edges, key=lambda edge: edge.view_edge_id):
        canonical_edges = []
        for edge_id in view_edge.canonical_edge_ids:
            edge = architecture_edges.get(edge_id)
            if edge is None:
                raise ValueError(f"view edge references missing canonical edge {edge_id}")
            canonical_edges.append(edge)
        if not canonical_edges:
            raise ValueError(f"view edge {view_edge.view_edge_id} has no canonical edges")

        for edge in canonical_edges:
            if view_by_canonical.get(edge.producer_id) != view_edge.source_view_node_id:
                raise ValueError(f"view edge {view_edge.view_edge_id} has an invalid source projection")
            if view_by_canonical.get(edge.consumer_id) != view_edge.target_view_node_id:
                raise ValueError(f"view edge {view_edge.view_edge_id} has an invalid target projection")

        source_scene = scene_by_view[view_edge.source_view_node_id]
        target_scene = scene_by_view[view_edge.target_view_node_id]
        source_node = routing_nodes_by_id[routing_id_by_scene[source_scene.scene_node_id]]
        target_node = routing_nodes_by_id[routing_id_by_scene[target_scene.scene_node_id]]
        source_side, target_side = _preferred_sides(source_node.bounds, target_node.bounds)
        source_port_ids = tuple(sorted({edge.producer_port for edge in canonical_edges}))
        target_port_ids = tuple(sorted({edge.consumer_port for edge in canonical_edges}))
        evidence_ids = _unique(
            [
                *view_edge.evidence_ids,
                *(evidence_id for edge in canonical_edges for evidence_id in edge.evidence_ids),
            ]
        )
        channel = view_edge.role

        source_routing_port_id = (
            "routing-port:"
            + _stable_suffix(
                source_node.view_node_id,
                "output",
                channel,
                *source_port_ids,
            )
        )
        target_routing_port_id = (
            "routing-port:"
            + _stable_suffix(
                target_node.view_node_id,
                "input",
                channel,
                *target_port_ids,
            )
        )
        ports_by_id.setdefault(
            source_routing_port_id,
            RoutingPort(
                routing_port_id=source_routing_port_id,
                owner_routing_node_id=source_node.routing_node_id,
                canonical_port_ids=source_port_ids,
                direction="output",
                semantic_role=channel,
                semantic_channel=channel,
                allowed_sides=tuple(PortSide),
                preferred_side=source_side,
                evidence_ids=evidence_ids,
            ),
        )
        ports_by_id.setdefault(
            target_routing_port_id,
            RoutingPort(
                routing_port_id=target_routing_port_id,
                owner_routing_node_id=target_node.routing_node_id,
                canonical_port_ids=target_port_ids,
                direction="input",
                semantic_role=channel,
                semantic_channel=channel,
                allowed_sides=tuple(PortSide),
                preferred_side=target_side,
                evidence_ids=evidence_ids,
            ),
        )
        routing_edges.append(
            RoutingEdge(
                routing_edge_id=f"routing-edge:{view_edge.view_edge_id}",
                view_edge_id=view_edge.view_edge_id,
                canonical_edge_ids=tuple(sorted(view_edge.canonical_edge_ids)),
                source_port_id=source_routing_port_id,
                target_port_id=target_routing_port_id,
                tensor_ids=tuple(sorted({edge.tensor_id for edge in canonical_edges})),
                semantic_channel=channel,
                visual_relation=view_edge.visual_relation.value,
                evidence_ids=evidence_ids,
            )
        )

    portals_by_id: dict[str, BoundaryPortal] = {}
    portal_chains: list[PortalChain] = []
    for edge in routing_edges:
        portals, chain = _portal_chain(edge, routing_nodes_by_id, ports_by_id)
        for portal in portals:
            portals_by_id.setdefault(portal.portal_id, portal)
        portal_chains.append(chain)

    return EvidenceBackedRoutingGraph(
        architecture_id=architecture.architecture_id,
        view_id=view.view_id,
        nodes=routing_nodes,
        ports=tuple(sorted(ports_by_id.values(), key=lambda port: port.routing_port_id)),
        edges=tuple(routing_edges),
        portals=tuple(sorted(portals_by_id.values(), key=lambda portal: portal.portal_id)),
        portal_chains=tuple(
            sorted(portal_chains, key=lambda chain: chain.routing_edge_id)
        ),
    )
