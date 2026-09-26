from __future__ import annotations

from itertools import combinations, pairwise

from .routing_models import (
    EvidenceBackedRoutingGraph,
    RouteGeometry,
    RoutingMetrics,
    RoutingPoint,
    RoutingRect,
)

_EPSILON = 0.01


def segment_inside_rect(
    first: RoutingPoint,
    second: RoutingPoint,
    rect: RoutingRect,
) -> float:
    if abs(first.x - second.x) <= _EPSILON and rect.x < first.x < rect.right:
        return max(
            0.0,
            min(max(first.y, second.y), rect.bottom)
            - max(min(first.y, second.y), rect.y),
        )
    if abs(first.y - second.y) <= _EPSILON and rect.y < first.y < rect.bottom:
        return max(
            0.0,
            min(max(first.x, second.x), rect.right)
            - max(min(first.x, second.x), rect.x),
        )
    return 0.0


def point_on_boundary(point: RoutingPoint, rect: RoutingRect) -> bool:
    horizontal = (
        abs(point.y - rect.y) <= _EPSILON or abs(point.y - rect.bottom) <= _EPSILON
    ) and rect.x - _EPSILON <= point.x <= rect.right + _EPSILON
    vertical = (
        abs(point.x - rect.x) <= _EPSILON or abs(point.x - rect.right) <= _EPSILON
    ) and rect.y - _EPSILON <= point.y <= rect.bottom + _EPSILON
    return horizontal or vertical


def _segment_interaction(
    first_start: RoutingPoint,
    first_end: RoutingPoint,
    second_start: RoutingPoint,
    second_end: RoutingPoint,
) -> tuple[int, float]:
    first_vertical = abs(first_start.x - first_end.x) <= _EPSILON
    second_vertical = abs(second_start.x - second_end.x) <= _EPSILON
    if first_vertical != second_vertical:
        vertical_start, vertical_end = (
            (first_start, first_end) if first_vertical else (second_start, second_end)
        )
        horizontal_start, horizontal_end = (
            (second_start, second_end) if first_vertical else (first_start, first_end)
        )
        x = vertical_start.x
        y = horizontal_start.y
        inside_vertical = (
            min(vertical_start.y, vertical_end.y) + _EPSILON
            < y
            < max(vertical_start.y, vertical_end.y) - _EPSILON
        )
        inside_horizontal = (
            min(horizontal_start.x, horizontal_end.x) + _EPSILON
            < x
            < max(horizontal_start.x, horizontal_end.x) - _EPSILON
        )
        return (1, 0.0) if inside_vertical and inside_horizontal else (0, 0.0)
    if first_vertical:
        if abs(first_start.x - second_start.x) > _EPSILON:
            return 0, 0.0
        overlap = max(
            0.0,
            min(max(first_start.y, first_end.y), max(second_start.y, second_end.y))
            - max(min(first_start.y, first_end.y), min(second_start.y, second_end.y)),
        )
        return 0, overlap
    if abs(first_start.y - second_start.y) > _EPSILON:
        return 0, 0.0
    overlap = max(
        0.0,
        min(max(first_start.x, first_end.x), max(second_start.x, second_end.x))
        - max(min(first_start.x, first_end.x), min(second_start.x, second_end.x)),
    )
    return 0, overlap


def _ancestor_ids(node_id: str, parent_by_id: dict[str, str | None]) -> set[str]:
    result = {node_id}
    cursor = parent_by_id.get(node_id)
    while cursor is not None and cursor not in result:
        result.add(cursor)
        cursor = parent_by_id.get(cursor)
    return result


def measure_routes(
    graph: EvidenceBackedRoutingGraph,
    routes: tuple[RouteGeometry, ...],
) -> RoutingMetrics:
    nodes = {node.routing_node_id: node for node in graph.nodes}
    ports = {port.routing_port_id: port for port in graph.ports}
    edges = {edge.routing_edge_id: edge for edge in graph.edges}
    parent_by_id = {
        node.routing_node_id: node.parent_routing_node_id for node in graph.nodes
    }
    invalid_endpoints = 0
    obstacle_count = 0
    obstacle_length = 0.0
    bend_count = 0
    reverse_departures = 0
    total_length = 0.0

    for route in routes:
        edge = edges[route.routing_edge_id]
        source = nodes[ports[edge.source_port_id].owner_routing_node_id]
        target = nodes[ports[edge.target_port_id].owner_routing_node_id]
        if not point_on_boundary(route.points[0], source.bounds):
            invalid_endpoints += 1
        if not point_on_boundary(route.points[-1], target.bounds):
            invalid_endpoints += 1
        ignored = _ancestor_ids(source.routing_node_id, parent_by_id) | _ancestor_ids(
            target.routing_node_id, parent_by_id
        )
        for first, second in pairwise(route.points):
            if abs(first.x - second.x) > _EPSILON and abs(first.y - second.y) > _EPSILON:
                invalid_endpoints += 1
            total_length += abs(second.x - first.x) + abs(second.y - first.y)
            for node in graph.nodes:
                if node.routing_node_id in ignored:
                    continue
                overlap = segment_inside_rect(first, second, node.bounds)
                if overlap > _EPSILON:
                    obstacle_count += 1
                    obstacle_length += overlap
        bend_count += max(0, len(route.points) - 2)
        if len(route.points) >= 2:
            first, second = route.points[0], route.points[1]
            if abs(first.x - source.bounds.left) <= _EPSILON and second.x > first.x:
                reverse_departures += 1
            if abs(first.x - source.bounds.right) <= _EPSILON and second.x < first.x:
                reverse_departures += 1
            if abs(first.y - source.bounds.y) <= _EPSILON and second.y > first.y:
                reverse_departures += 1
            if abs(first.y - source.bounds.bottom) <= _EPSILON and second.y < first.y:
                reverse_departures += 1

    crossings = 0
    shared_length = 0.0
    for left, right in combinations(routes, 2):
        for left_start, left_end in pairwise(left.points):
            for right_start, right_end in pairwise(right.points):
                crossing, shared = _segment_interaction(
                    left_start,
                    left_end,
                    right_start,
                    right_end,
                )
                crossings += crossing
                shared_length += shared

    return RoutingMetrics(
        invalid_endpoint_count=invalid_endpoints,
        obstacle_intersection_count=obstacle_count,
        obstacle_intersection_length=round(obstacle_length, 4),
        crossing_count=crossings,
        shared_segment_length=round(shared_length, 4),
        bend_count=bend_count,
        reverse_departure_count=reverse_departures,
        total_length=round(total_length, 4),
    )
