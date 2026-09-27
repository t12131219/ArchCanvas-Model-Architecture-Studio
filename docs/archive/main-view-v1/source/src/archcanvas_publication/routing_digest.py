from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from .routing_models import EvidenceBackedRoutingGraph, RouteGeometry


def _normalized(value: Any) -> Any:
    if is_dataclass(value):
        return _normalized(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _normalized(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_normalized(item) for item in value]
    if isinstance(value, float):
        return round(value, 4)
    return value


def _digest(value: Any) -> str:
    payload = json.dumps(
        _normalized(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def routing_input_digest(
    graph: EvidenceBackedRoutingGraph,
    *,
    route_hints: dict[str, tuple[object, ...]] | None = None,
) -> str:
    return _digest(
        {
            "architecture_id": graph.architecture_id,
            "view_id": graph.view_id,
            "nodes": sorted(graph.nodes, key=lambda item: item.routing_node_id),
            "ports": sorted(graph.ports, key=lambda item: item.routing_port_id),
            "edges": sorted(graph.edges, key=lambda item: item.routing_edge_id),
            "portals": sorted(graph.portals, key=lambda item: item.portal_id),
            "portal_chains": sorted(
                graph.portal_chains,
                key=lambda item: item.routing_edge_id,
            ),
            "route_hints": route_hints or {},
        }
    )


def routing_route_digest(routes: tuple[RouteGeometry, ...]) -> str:
    return _digest(tuple(sorted(routes, key=lambda route: route.routing_edge_id)))
