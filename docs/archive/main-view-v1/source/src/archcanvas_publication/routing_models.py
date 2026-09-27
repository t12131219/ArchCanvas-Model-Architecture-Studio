from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PortSide(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


@dataclass(frozen=True, order=True)
class RoutingPoint:
    x: float
    y: float


@dataclass(frozen=True)
class RoutingRect:
    x: float
    y: float
    width: float
    height: float

    @property
    def left(self) -> float:
        return self.x

    @property
    def top(self) -> float:
        return self.y

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def center(self) -> RoutingPoint:
        return RoutingPoint(self.x + self.width / 2.0, self.y + self.height / 2.0)


@dataclass(frozen=True)
class RoutingNode:
    routing_node_id: str
    scene_node_id: str
    view_node_id: str
    canonical_node_ids: tuple[str, ...]
    parent_routing_node_id: str | None
    bounds: RoutingRect
    semantic_kind: str
    collapsed: bool
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class RoutingPort:
    routing_port_id: str
    owner_routing_node_id: str
    canonical_port_ids: tuple[str, ...]
    direction: str
    semantic_role: str
    semantic_channel: str | None
    allowed_sides: tuple[PortSide, ...]
    preferred_side: PortSide | None
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class RoutingEdge:
    routing_edge_id: str
    view_edge_id: str
    canonical_edge_ids: tuple[str, ...]
    source_port_id: str
    target_port_id: str
    tensor_ids: tuple[str, ...]
    semantic_channel: str | None
    visual_relation: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class BoundaryPortal:
    portal_id: str
    owner_routing_node_id: str
    child_routing_node_id: str
    direction: str
    canonical_edge_ids: tuple[str, ...]


@dataclass(frozen=True)
class PortalChain:
    routing_edge_id: str
    source_port_id: str
    portal_ids: tuple[str, ...]
    target_port_id: str


@dataclass(frozen=True)
class EvidenceBackedRoutingGraph:
    architecture_id: str
    view_id: str
    nodes: tuple[RoutingNode, ...]
    ports: tuple[RoutingPort, ...]
    edges: tuple[RoutingEdge, ...]
    portals: tuple[BoundaryPortal, ...] = ()
    portal_chains: tuple[PortalChain, ...] = ()


@dataclass(frozen=True)
class RouteGeometry:
    routing_edge_id: str
    points: tuple[RoutingPoint, ...]
    source_port_id: str
    target_port_id: str
    portal_ids: tuple[str, ...] = ()
    fallback_reason: str | None = None


@dataclass(frozen=True)
class RoutingMetrics:
    invalid_endpoint_count: int = 0
    obstacle_intersection_count: int = 0
    obstacle_intersection_length: float = 0.0
    crossing_count: int = 0
    shared_segment_length: float = 0.0
    bend_count: int = 0
    reverse_departure_count: int = 0
    total_length: float = 0.0

    @property
    def has_hard_errors(self) -> bool:
        return self.invalid_endpoint_count > 0 or self.obstacle_intersection_count > 0


@dataclass(frozen=True)
class RoutingReceipt:
    engine: str
    engine_version: str
    input_digest: str
    route_digest: str
    metrics: RoutingMetrics
    fallback_reasons: tuple[tuple[str, str], ...] = ()
    diagnostics: tuple[str, ...] = ()
    duration_ms: tuple[tuple[str, float], ...] = ()
