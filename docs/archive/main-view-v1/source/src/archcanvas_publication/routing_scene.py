from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Literal

from archcanvas_core.models import ArchitectureIR, PublicationView, ScenePoint, VisualScene

from .routing_digest import routing_input_digest, routing_route_digest
from .routing_graph import build_routing_graph
from .routing_kernel import route_graph
from .routing_metrics import measure_routes
from .routing_models import RoutingPoint, RoutingReceipt


@dataclass(frozen=True)
class AtomicRoutingReport:
    mode: Literal["atomic-v1"]
    requested_engine: Literal["atomic-v1"]
    visible_engine: Literal["atomic-v1", "legacy"]
    status: Literal["routed", "fallback"]
    scene_id: str
    view_id: str
    receipt: RoutingReceipt | None = None
    routed_edge_count: int = 0
    fixed_route_count: int = 0
    error_code: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def failed_atomic_routing(
    scene: VisualScene,
    view: PublicationView,
    error: Exception,
) -> AtomicRoutingReport:
    return AtomicRoutingReport(
        mode="atomic-v1",
        requested_engine="atomic-v1",
        visible_engine="legacy",
        status="fallback",
        scene_id=scene.scene_id,
        view_id=view.view_id,
        error_code="atomic-routing-failed",
        error_message=str(error),
    )


def route_atomic_scene(
    architecture: ArchitectureIR,
    view: PublicationView,
    scene: VisualScene,
    *,
    fixed_scene_edge_ids: frozenset[str] = frozenset(),
) -> tuple[VisualScene, AtomicRoutingReport]:
    """Materialize atomic-v1 geometry without changing scene or canonical identity."""
    graph = build_routing_graph(architecture, view, scene.nodes)
    routes, receipt = route_graph(graph)
    graph_edges = {edge.routing_edge_id: edge for edge in graph.edges}
    scene_edges = {edge.view_edge_id: edge for edge in scene.edges}
    expected_view_edges = {edge.view_edge_id for edge in graph.edges}
    if set(scene_edges) != expected_view_edges:
        raise ValueError("scene and routing graph edge identities differ")

    fixed_routes: dict[str, tuple[RoutingPoint, ...]] = {}
    route_by_id = {route.routing_edge_id: route for route in routes}
    for routing_edge_id, routing_edge in graph_edges.items():
        scene_edge = scene_edges[routing_edge.view_edge_id]
        if scene_edge.scene_edge_id not in fixed_scene_edge_ids:
            continue
        fixed_points = tuple(RoutingPoint(point.x, point.y) for point in scene_edge.points)
        fixed_routes[routing_edge_id] = fixed_points
        automatic = route_by_id[routing_edge_id]
        route_by_id[routing_edge_id] = replace(
            automatic,
            points=fixed_points,
            fallback_reason=None,
        )

    visible_routes = tuple(route_by_id[edge.routing_edge_id] for edge in graph.edges)
    metrics = measure_routes(graph, visible_routes)
    route_digest = routing_route_digest(visible_routes)
    receipt = replace(
        receipt,
        input_digest=routing_input_digest(graph, route_hints=fixed_routes),
        route_digest=route_digest,
        metrics=metrics,
        fallback_reasons=tuple(
            (route.routing_edge_id, route.fallback_reason)
            for route in visible_routes
            if route.fallback_reason is not None
        ),
        diagnostics=("hard-routing-errors",) if metrics.has_hard_errors else (),
    )
    if metrics.has_hard_errors or receipt.fallback_reasons:
        return scene, AtomicRoutingReport(
            mode="atomic-v1",
            requested_engine="atomic-v1",
            visible_engine="legacy",
            status="fallback",
            scene_id=scene.scene_id,
            view_id=view.view_id,
            receipt=receipt,
            routed_edge_count=len(visible_routes),
            fixed_route_count=len(fixed_routes),
            error_code="atomic-hard-routing-errors",
            error_message="atomic-v1 did not satisfy the hard routing metrics",
        )

    routes_by_view_edge = {
        graph_edges[route.routing_edge_id].view_edge_id: route
        for route in visible_routes
    }
    graph_edges_by_view = {edge.view_edge_id: edge for edge in graph.edges}
    routed_edges = []
    for edge in scene.edges:
        route = routes_by_view_edge[edge.view_edge_id]
        routing_edge = graph_edges_by_view[edge.view_edge_id]
        routed_edges.append(
            edge.model_copy(
                update={
                    "points": [ScenePoint(x=point.x, y=point.y) for point in route.points],
                    "source_port_id": route.source_port_id,
                    "target_port_id": route.target_port_id,
                    "evidence_ids": list(routing_edge.evidence_ids),
                    "portal_ids": list(route.portal_ids),
                    "route_digest": route_digest,
                }
            )
        )
    routed_scene = scene.model_copy(update={"edges": routed_edges})
    return routed_scene, AtomicRoutingReport(
        mode="atomic-v1",
        requested_engine="atomic-v1",
        visible_engine="atomic-v1",
        status="routed",
        scene_id=scene.scene_id,
        view_id=view.view_id,
        receipt=receipt,
        routed_edge_count=len(visible_routes),
        fixed_route_count=len(fixed_routes),
    )
