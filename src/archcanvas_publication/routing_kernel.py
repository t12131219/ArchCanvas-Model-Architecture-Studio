from __future__ import annotations

from collections import defaultdict
from itertools import pairwise
from time import perf_counter

from .routing_digest import routing_input_digest, routing_route_digest
from .routing_metrics import measure_routes, segment_inside_rect
from .routing_models import (
    EvidenceBackedRoutingGraph,
    PortSide,
    RouteGeometry,
    RoutingPoint,
    RoutingPort,
    RoutingReceipt,
    RoutingRect,
)

ENGINE_NAME = "atomic-v1"
ENGINE_VERSION = "1.0.0-alpha.1"
_CLEARANCE = 18.0


def _validate_graph(graph: EvidenceBackedRoutingGraph) -> None:
    nodes = {node.routing_node_id: node for node in graph.nodes}
    ports = {port.routing_port_id: port for port in graph.ports}
    edges = {edge.routing_edge_id: edge for edge in graph.edges}
    if len(nodes) != len(graph.nodes):
        raise ValueError("routing node identifiers must be unique")
    if len(ports) != len(graph.ports):
        raise ValueError("routing port identifiers must be unique")
    if len(edges) != len(graph.edges):
        raise ValueError("routing edge identifiers must be unique")

    for node in graph.nodes:
        if node.bounds.width <= 0.0 or node.bounds.height <= 0.0:
            raise ValueError(f"routing node {node.routing_node_id} has invalid bounds")
        if (
            node.parent_routing_node_id is not None
            and node.parent_routing_node_id not in nodes
        ):
            raise ValueError(f"routing node {node.routing_node_id} has a missing parent")
        visited = {node.routing_node_id}
        cursor = node.parent_routing_node_id
        while cursor is not None:
            if cursor in visited:
                raise ValueError("routing node containment contains a cycle")
            visited.add(cursor)
            cursor = nodes[cursor].parent_routing_node_id

    for port in graph.ports:
        if port.owner_routing_node_id not in nodes:
            raise ValueError(f"routing port {port.routing_port_id} has a missing owner")
        if port.direction not in {"input", "output"}:
            raise ValueError(f"routing port {port.routing_port_id} has an invalid direction")
        if not port.allowed_sides:
            raise ValueError(f"routing port {port.routing_port_id} has no allowed side")
        if port.preferred_side is not None and port.preferred_side not in port.allowed_sides:
            raise ValueError(
                f"routing port {port.routing_port_id} prefers a forbidden side"
            )

    for edge in graph.edges:
        source = ports.get(edge.source_port_id)
        target = ports.get(edge.target_port_id)
        if source is None or target is None:
            raise ValueError(f"routing edge {edge.routing_edge_id} references a missing port")
        if source.direction != "output" or target.direction != "input":
            raise ValueError(f"routing edge {edge.routing_edge_id} reverses port direction")
        if not edge.canonical_edge_ids:
            raise ValueError(f"routing edge {edge.routing_edge_id} lacks canonical provenance")

    portal_ids = {portal.portal_id for portal in graph.portals}
    if len(portal_ids) != len(graph.portals):
        raise ValueError("routing portal identifiers must be unique")
    for portal in graph.portals:
        if (
            portal.owner_routing_node_id not in nodes
            or portal.child_routing_node_id not in nodes
        ):
            raise ValueError(f"routing portal {portal.portal_id} references a missing node")
    for chain in graph.portal_chains:
        if chain.routing_edge_id not in edges:
            raise ValueError(f"portal chain references missing edge {chain.routing_edge_id}")
        if any(portal_id not in portal_ids for portal_id in chain.portal_ids):
            raise ValueError(f"portal chain {chain.routing_edge_id} references a missing portal")


def _simplify(points: list[RoutingPoint]) -> tuple[RoutingPoint, ...]:
    result: list[RoutingPoint] = []
    for point in points:
        if result and point == result[-1]:
            continue
        result.append(point)
        while len(result) >= 3:
            first, middle, last = result[-3:]
            if first.x == middle.x == last.x or first.y == middle.y == last.y:
                result.pop(-2)
            else:
                break
    return tuple(result)


def _port_point(rect: RoutingRect, side: PortSide, index: int, count: int) -> RoutingPoint:
    if side in {PortSide.LEFT, PortSide.RIGHT}:
        margin = min(14.0, rect.height / 4.0)
        span = max(0.0, rect.height - 2.0 * margin)
        offset = span / (count + 1) * (index + 1) if count else rect.height / 2.0
        return RoutingPoint(
            rect.x if side is PortSide.LEFT else rect.right,
            rect.y + margin + offset,
        )
    margin = min(14.0, rect.width / 4.0)
    span = max(0.0, rect.width - 2.0 * margin)
    offset = span / (count + 1) * (index + 1) if count else rect.width / 2.0
    return RoutingPoint(
        rect.x + margin + offset,
        rect.y if side is PortSide.TOP else rect.bottom,
    )


def _stub(point: RoutingPoint, side: PortSide) -> RoutingPoint:
    if side is PortSide.LEFT:
        return RoutingPoint(max(0.0, point.x - _CLEARANCE), point.y)
    if side is PortSide.RIGHT:
        return RoutingPoint(point.x + _CLEARANCE, point.y)
    if side is PortSide.TOP:
        return RoutingPoint(point.x, max(0.0, point.y - _CLEARANCE))
    return RoutingPoint(point.x, point.y + _CLEARANCE)


def _candidate_routes(
    start: RoutingPoint,
    start_stub: RoutingPoint,
    end_stub: RoutingPoint,
    end: RoutingPoint,
    obstacles: tuple[RoutingRect, ...],
) -> list[tuple[RoutingPoint, ...]]:
    candidates: list[tuple[RoutingPoint, ...]] = []

    def add(middle: list[RoutingPoint]) -> None:
        candidate = _simplify([start, start_stub, *middle, end_stub, end])
        if candidate not in candidates:
            candidates.append(candidate)

    if start_stub.x == end_stub.x or start_stub.y == end_stub.y:
        add([])
    add([RoutingPoint(end_stub.x, start_stub.y)])
    add([RoutingPoint(start_stub.x, end_stub.y)])
    middle_x = (start_stub.x + end_stub.x) / 2.0
    middle_y = (start_stub.y + end_stub.y) / 2.0
    add(
        [
            RoutingPoint(middle_x, start_stub.y),
            RoutingPoint(middle_x, end_stub.y),
        ]
    )
    add(
        [
            RoutingPoint(start_stub.x, middle_y),
            RoutingPoint(end_stub.x, middle_y),
        ]
    )
    x_corridors = {0.0}
    y_corridors = {0.0}
    for obstacle in obstacles:
        x_corridors.update(
            {
                max(0.0, obstacle.x - _CLEARANCE),
                obstacle.right + _CLEARANCE,
            }
        )
        y_corridors.update(
            {
                max(0.0, obstacle.y - _CLEARANCE),
                obstacle.bottom + _CLEARANCE,
            }
        )
    for x in sorted(x_corridors):
        add([RoutingPoint(x, start_stub.y), RoutingPoint(x, end_stub.y)])
    for y in sorted(y_corridors):
        add([RoutingPoint(start_stub.x, y), RoutingPoint(end_stub.x, y)])
    return candidates


def _score(
    points: tuple[RoutingPoint, ...],
    obstacles: tuple[RoutingRect, ...],
) -> tuple[int, float, int, float, tuple[tuple[float, float], ...]]:
    intersections = 0
    overlap = 0.0
    length = 0.0
    for first, second in pairwise(points):
        length += abs(second.x - first.x) + abs(second.y - first.y)
        for obstacle in obstacles:
            inside = segment_inside_rect(first, second, obstacle)
            if inside > 0.01:
                intersections += 1
                overlap += inside
    return (
        intersections,
        round(overlap, 4),
        max(0, len(points) - 2),
        round(length, 4),
        tuple((round(point.x, 4), round(point.y, 4)) for point in points),
    )


def _ancestors(node_id: str, parent_by_id: dict[str, str | None]) -> set[str]:
    result = {node_id}
    cursor = parent_by_id.get(node_id)
    while cursor is not None and cursor not in result:
        result.add(cursor)
        cursor = parent_by_id.get(cursor)
    return result


def route_graph(
    graph: EvidenceBackedRoutingGraph,
) -> tuple[tuple[RouteGeometry, ...], RoutingReceipt]:
    started = perf_counter()
    _validate_graph(graph)
    nodes = {node.routing_node_id: node for node in graph.nodes}
    ports = {port.routing_port_id: port for port in graph.ports}
    parent_by_id = {
        node.routing_node_id: node.parent_routing_node_id for node in graph.nodes
    }
    chain_by_edge = {chain.routing_edge_id: chain for chain in graph.portal_chains}

    selected_sides: dict[str, PortSide] = {}
    for port in graph.ports:
        side = port.preferred_side
        if side not in port.allowed_sides:
            side = port.allowed_sides[0]
        selected_sides[port.routing_port_id] = side

    grouped_ports: dict[tuple[str, PortSide], list[RoutingPort]] = defaultdict(list)
    for port in graph.ports:
        grouped_ports[(port.owner_routing_node_id, selected_sides[port.routing_port_id])].append(
            port
        )
    positions: dict[str, RoutingPoint] = {}
    for (node_id, side), members in grouped_ports.items():
        ordered = sorted(
            members,
            key=lambda port: (port.semantic_channel or "", port.routing_port_id),
        )
        for index, port in enumerate(ordered):
            positions[port.routing_port_id] = _port_point(
                nodes[node_id].bounds,
                side,
                index,
                len(ordered),
            )

    routes: list[RouteGeometry] = []
    fallbacks: list[tuple[str, str]] = []
    for edge in sorted(graph.edges, key=lambda item: item.routing_edge_id):
        source_port = ports[edge.source_port_id]
        target_port = ports[edge.target_port_id]
        source_id = source_port.owner_routing_node_id
        target_id = target_port.owner_routing_node_id
        ignored = _ancestors(source_id, parent_by_id) | _ancestors(target_id, parent_by_id)
        obstacles = tuple(
            node.bounds for node in graph.nodes if node.routing_node_id not in ignored
        )
        start = positions[source_port.routing_port_id]
        end = positions[target_port.routing_port_id]
        candidates = _candidate_routes(
            start,
            _stub(start, selected_sides[source_port.routing_port_id]),
            _stub(end, selected_sides[target_port.routing_port_id]),
            end,
            obstacles,
        )
        points = min(candidates, key=lambda candidate: _score(candidate, obstacles))
        score = _score(points, obstacles)
        fallback_reason = "no-obstacle-free-route" if score[0] else None
        if fallback_reason is not None:
            fallbacks.append((edge.routing_edge_id, fallback_reason))
        chain = chain_by_edge.get(edge.routing_edge_id)
        routes.append(
            RouteGeometry(
                routing_edge_id=edge.routing_edge_id,
                points=points,
                source_port_id=edge.source_port_id,
                target_port_id=edge.target_port_id,
                portal_ids=chain.portal_ids if chain is not None else (),
                fallback_reason=fallback_reason,
            )
        )

    result = tuple(routes)
    metrics = measure_routes(graph, result)
    elapsed_ms = (perf_counter() - started) * 1000.0
    receipt = RoutingReceipt(
        engine=ENGINE_NAME,
        engine_version=ENGINE_VERSION,
        input_digest=routing_input_digest(graph),
        route_digest=routing_route_digest(result),
        metrics=metrics,
        fallback_reasons=tuple(fallbacks),
        diagnostics=("hard-routing-errors",) if metrics.has_hard_errors else (),
        duration_ms=(("total", round(elapsed_ms, 4)),),
    )
    return result, receipt
