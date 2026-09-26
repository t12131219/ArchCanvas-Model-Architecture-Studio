from __future__ import annotations

from dataclasses import asdict, dataclass

from archcanvas_core.models import ArchitectureIR, PublicationView, VisualScene

from .routing_digest import routing_route_digest
from .routing_graph import build_routing_graph
from .routing_kernel import route_graph
from .routing_metrics import measure_routes
from .routing_models import RouteGeometry, RoutingMetrics, RoutingPoint, RoutingReceipt


@dataclass(frozen=True)
class RoutingMetricDelta:
    invalid_endpoint_count: int
    obstacle_intersection_count: int
    obstacle_intersection_length: float
    crossing_count: int
    shared_segment_length: float
    bend_count: int
    reverse_departure_count: int
    total_length: float


@dataclass(frozen=True)
class RoutingShadowComparison:
    mode: str
    visible_engine: str
    shadow_engine: str
    status: str
    scene_id: str
    view_id: str
    legacy_metrics: RoutingMetrics | None = None
    shadow_receipt: RoutingReceipt | None = None
    delta: RoutingMetricDelta | None = None
    legacy_route_digest: str | None = None
    route_digest_matches: bool | None = None
    compared_edge_count: int = 0
    endpoint_displacement_total: float = 0.0
    endpoint_displacement_max: float = 0.0
    error_code: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _legacy_routes(
    scene: VisualScene,
    routing_edge_ids: dict[str, str],
    source_port_ids: dict[str, str],
    target_port_ids: dict[str, str],
) -> tuple[RouteGeometry, ...]:
    by_view_edge = {edge.view_edge_id: edge for edge in scene.edges}
    if len(by_view_edge) != len(scene.edges):
        raise ValueError("legacy scene edge view identifiers must be unique")
    missing = set(routing_edge_ids) - set(by_view_edge)
    extra = set(by_view_edge) - set(routing_edge_ids)
    if missing or extra:
        raise ValueError(
            "legacy scene and routing graph edge identities differ: "
            f"missing={sorted(missing)}, extra={sorted(extra)}"
        )
    return tuple(
        RouteGeometry(
            routing_edge_id=routing_edge_ids[view_edge_id],
            points=tuple(RoutingPoint(point.x, point.y) for point in by_view_edge[view_edge_id].points),
            source_port_id=source_port_ids[view_edge_id],
            target_port_id=target_port_ids[view_edge_id],
        )
        for view_edge_id in sorted(routing_edge_ids)
    )


def _metric_delta(
    legacy: RoutingMetrics,
    shadow: RoutingMetrics,
) -> RoutingMetricDelta:
    return RoutingMetricDelta(
        invalid_endpoint_count=(
            shadow.invalid_endpoint_count - legacy.invalid_endpoint_count
        ),
        obstacle_intersection_count=(
            shadow.obstacle_intersection_count - legacy.obstacle_intersection_count
        ),
        obstacle_intersection_length=round(
            shadow.obstacle_intersection_length - legacy.obstacle_intersection_length,
            4,
        ),
        crossing_count=shadow.crossing_count - legacy.crossing_count,
        shared_segment_length=round(
            shadow.shared_segment_length - legacy.shared_segment_length,
            4,
        ),
        bend_count=shadow.bend_count - legacy.bend_count,
        reverse_departure_count=(
            shadow.reverse_departure_count - legacy.reverse_departure_count
        ),
        total_length=round(shadow.total_length - legacy.total_length, 4),
    )


def _distance(left: RoutingPoint, right: RoutingPoint) -> float:
    return abs(left.x - right.x) + abs(left.y - right.y)


def compare_shadow_routing(
    architecture: ArchitectureIR,
    view: PublicationView,
    visible_scene: VisualScene,
) -> RoutingShadowComparison:
    """Compare atomic-v1 against a visible legacy scene without mutating it."""
    graph = build_routing_graph(architecture, view, visible_scene.nodes)
    routing_edge_ids = {
        edge.view_edge_id: edge.routing_edge_id for edge in graph.edges
    }
    source_port_ids = {edge.view_edge_id: edge.source_port_id for edge in graph.edges}
    target_port_ids = {edge.view_edge_id: edge.target_port_id for edge in graph.edges}
    legacy_routes = _legacy_routes(
        visible_scene,
        routing_edge_ids,
        source_port_ids,
        target_port_ids,
    )
    shadow_routes, shadow_receipt = route_graph(graph)
    legacy_metrics = measure_routes(graph, legacy_routes)
    legacy_route_digest = routing_route_digest(legacy_routes)
    legacy_by_id = {route.routing_edge_id: route for route in legacy_routes}
    displacement = []
    for route in shadow_routes:
        legacy = legacy_by_id[route.routing_edge_id]
        displacement.append(
            _distance(legacy.points[0], route.points[0])
            + _distance(legacy.points[-1], route.points[-1])
        )
    return RoutingShadowComparison(
        mode="shadow",
        visible_engine="legacy",
        shadow_engine=shadow_receipt.engine,
        status="compared",
        scene_id=visible_scene.scene_id,
        view_id=view.view_id,
        legacy_metrics=legacy_metrics,
        shadow_receipt=shadow_receipt,
        delta=_metric_delta(legacy_metrics, shadow_receipt.metrics),
        legacy_route_digest=legacy_route_digest,
        route_digest_matches=legacy_route_digest == shadow_receipt.route_digest,
        compared_edge_count=len(shadow_routes),
        endpoint_displacement_total=round(sum(displacement), 4),
        endpoint_displacement_max=round(max(displacement, default=0.0), 4),
    )


def failed_shadow_comparison(
    scene: VisualScene,
    view: PublicationView,
    error: Exception,
) -> RoutingShadowComparison:
    return RoutingShadowComparison(
        mode="shadow",
        visible_engine="legacy",
        shadow_engine="atomic-v1",
        status="failed",
        scene_id=scene.scene_id,
        view_id=view.view_id,
        error_code="shadow-routing-failed",
        error_message=str(error),
    )


def skipped_shadow_comparison(
    scene: VisualScene,
    view: PublicationView,
) -> RoutingShadowComparison:
    return RoutingShadowComparison(
        mode="shadow",
        visible_engine="legacy",
        shadow_engine="atomic-v1",
        status="not-sampled",
        scene_id=scene.scene_id,
        view_id=view.view_id,
    )
