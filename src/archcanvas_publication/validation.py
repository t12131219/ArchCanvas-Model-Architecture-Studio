from __future__ import annotations

from collections import Counter, defaultdict, deque

from archcanvas_core.models import (
    ArchitectureIR,
    Diagnostic,
    GateResult,
    NodeKind,
    PublicationView,
    SceneRect,
    VisualScene,
)

from .label_layout import edge_label_placements, label_required


def _diagnostic(code: str, message: str, *target_ids: str) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity="blocking",
        message=message,
        target_ids=list(target_ids),
    )


def _duplicates(values: list[str]) -> set[str]:
    return {value for value, count in Counter(values).items() if count > 1}


def _finger_trace(view: PublicationView, inputs: set[str], outputs: set[str]) -> bool:
    canonical_to_view = {
        canonical_id: node.view_node_id
        for node in view.nodes
        for canonical_id in node.canonical_node_ids
    }
    starts = {canonical_to_view[node_id] for node_id in inputs if node_id in canonical_to_view}
    targets = {canonical_to_view[node_id] for node_id in outputs if node_id in canonical_to_view}
    if not starts or not targets:
        return False
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in view.edges:
        adjacency[edge.source_view_node_id].add(edge.target_view_node_id)
    reachable = set(starts)
    queue = deque(starts)
    while queue:
        current = queue.popleft()
        for target in adjacency[current] - reachable:
            reachable.add(target)
            queue.append(target)
    return targets <= reachable


def validate_publication(
    ir: ArchitectureIR, views: list[PublicationView]
) -> tuple[list[GateResult], list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []
    executable_nodes = [node for node in ir.nodes if node.kind is not NodeKind.REFERENCE_ONLY]
    executable_ids = {node.node_id for node in executable_nodes}
    expected_nodes = set(executable_ids)
    expected_edges = {
        edge.edge_id
        for edge in ir.edges
        if edge.producer_id in executable_ids and edge.consumer_id in executable_ids
    }
    expected_tensors = {
        tensor.tensor_id for tensor in ir.tensors if tensor.producer_id in executable_ids
    }
    expected_ports = {
        port.port_id
        for node in executable_nodes
        for port in [*node.input_ports, *node.output_ports]
    }
    inputs = {
        node.node_id
        for node in executable_nodes
        if node.kind is NodeKind.INPUT_OUTPUT and node.attributes.get("io") == "input"
    }
    outputs = {
        node.node_id
        for node in executable_nodes
        if node.kind is NodeKind.INPUT_OUTPUT and node.attributes.get("io") == "output"
    }
    levels = [view.level for view in views]
    if set(levels) != {"L1", "L2", "L3", "L4"} or len(levels) != 4:
        diagnostics.append(
            _diagnostic(
                "PUBLICATION_LEVEL_SET_INVALID",
                "Publication compilation must contain exactly one L1, L2, L3, and L4 view.",
            )
        )

    for view in views:
        target = view.view_id
        if view.architecture_id != ir.architecture_id:
            diagnostics.append(
                _diagnostic(
                    "PUBLICATION_ARCHITECTURE_MISMATCH",
                    f"{view.view_id} belongs to a different architecture.",
                    target,
                )
            )
        for label, actual, expected in (
            ("NODE", set(view.canonical_node_ids), expected_nodes),
            ("EDGE", set(view.canonical_edge_ids), expected_edges),
            ("TENSOR", set(view.canonical_tensor_ids), expected_tensors),
            ("PORT", set(view.canonical_port_ids), expected_ports),
        ):
            if actual != expected:
                diagnostics.append(
                    _diagnostic(
                        f"PUBLICATION_{label}_SET_MISMATCH",
                        f"{view.view_id} does not preserve the canonical {label.lower()} set.",
                        target,
                    )
                )
        visible_nodes = [
            canonical_id for node in view.nodes for canonical_id in node.canonical_node_ids
        ]
        if set(visible_nodes) != expected_nodes or _duplicates(visible_nodes):
            diagnostics.append(
                _diagnostic(
                    "PUBLICATION_NODE_MAPPING_INVALID",
                    f"{view.view_id} must map every executable node exactly once.",
                    target,
                )
            )
        visible_edges = [
            canonical_id for edge in view.edges for canonical_id in edge.canonical_edge_ids
        ]
        covered_edges = [*visible_edges, *view.collapsed_edge_ids]
        if set(covered_edges) != expected_edges or _duplicates(covered_edges):
            diagnostics.append(
                _diagnostic(
                    "PUBLICATION_EDGE_MAPPING_INVALID",
                    f"{view.view_id} must expose or collapse every executable edge exactly once.",
                    target,
                )
            )
        view_node_ids = {node.view_node_id for node in view.nodes}
        if len(view_node_ids) != len(view.nodes):
            diagnostics.append(
                _diagnostic(
                    "PUBLICATION_VIEW_NODE_DUPLICATE",
                    f"{view.view_id} contains duplicate view node identifiers.",
                    target,
                )
            )
        for node in view.nodes:
            if node.parent_view_node_id and node.parent_view_node_id not in view_node_ids:
                diagnostics.append(
                    _diagnostic(
                        "PUBLICATION_PARENT_MISSING",
                        f"{node.view_node_id} references a missing publication parent.",
                        node.view_node_id,
                    )
                )
        for edge in view.edges:
            if (
                edge.source_view_node_id not in view_node_ids
                or edge.target_view_node_id not in view_node_ids
            ):
                diagnostics.append(
                    _diagnostic(
                        "PUBLICATION_EDGE_ENDPOINT_MISSING",
                        f"{edge.view_edge_id} references a missing publication node.",
                        edge.view_edge_id,
                    )
                )
        if not _finger_trace(view, inputs, outputs):
            diagnostics.append(
                _diagnostic(
                    "PUBLICATION_FINGER_TRACE_FAILED",
                    f"Input-to-output reachability is not preserved in {view.view_id}.",
                    target,
                )
            )
        if view.non_executable_duplicates:
            diagnostics.append(
                _diagnostic(
                    "PUBLICATION_EXECUTABLE_DUPLICATE",
                    f"{view.view_id} contains a detached executable duplicate.",
                    target,
                )
            )
        if view.level == "L4":
            if any(len(node.canonical_node_ids) != 1 or node.collapsed for node in view.nodes):
                diagnostics.append(
                    _diagnostic(
                        "PUBLICATION_L4_NODE_NOT_EXACT",
                        "L4 requires one visible view node per canonical node.",
                        target,
                    )
                )
            if any(len(edge.canonical_edge_ids) != 1 for edge in view.edges) or view.collapsed_edge_ids:
                diagnostics.append(
                    _diagnostic(
                        "PUBLICATION_L4_EDGE_NOT_EXACT",
                        "L4 requires one visible view edge per canonical edge.",
                        target,
                    )
                )

    gate = GateResult(
        gate="C-publication",
        status="failed" if diagnostics else "passed",
        message=(
            "Publication views failed canonical identity or reachability checks."
            if diagnostics
            else "L1-L4 preserve canonical identity, provenance, and input-to-output reachability."
        ),
    )
    return [gate], diagnostics


def _overlap(first: SceneRect, second: SceneRect) -> bool:
    return (
        first.x < second.x + second.width
        and first.x + first.width > second.x
        and first.y < second.y + second.height
        and first.y + first.height > second.y
    )


def _contains(outer: SceneRect, inner: SceneRect) -> bool:
    return (
        inner.x >= outer.x
        and inner.y >= outer.y
        and inner.x + inner.width <= outer.x + outer.width
        and inner.y + inner.height <= outer.y + outer.height
    )


def _segment_crosses_rect(
    x1: float, y1: float, x2: float, y2: float, rect: SceneRect
) -> bool:
    left, right = rect.x, rect.x + rect.width
    top, bottom = rect.y, rect.y + rect.height
    if x1 == x2:
        return left < x1 < right and max(min(y1, y2), top) < min(max(y1, y2), bottom)
    if y1 == y2:
        return top < y1 < bottom and max(min(x1, x2), left) < min(max(x1, x2), right)
    return False


def validate_geometry(scene: VisualScene) -> tuple[GateResult, list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []
    by_id = {node.scene_node_id: node for node in scene.nodes}
    if len(by_id) != len(scene.nodes):
        diagnostics.append(
            _diagnostic("GEOMETRY_NODE_ID_DUPLICATE", "VisualScene node identifiers are not unique.")
        )
    for node in scene.nodes:
        bounds = node.bounds
        if bounds.x + bounds.width > scene.paper_width or bounds.y + bounds.height > scene.paper_height:
            diagnostics.append(
                _diagnostic(
                    "GEOMETRY_NODE_OFF_CANVAS",
                    f"{node.scene_node_id} extends beyond the paper bounds.",
                    node.scene_node_id,
                )
            )
        if node.parent_scene_node_id:
            parent = by_id.get(node.parent_scene_node_id)
            if parent is None or not _contains(parent.bounds, bounds):
                diagnostics.append(
                    _diagnostic(
                        "GEOMETRY_CONTAINMENT_INVALID",
                        f"{node.scene_node_id} is not contained by its declared parent.",
                        node.scene_node_id,
                    )
                )
        longest = max(len(line) for line in node.label_lines)
        estimated_width = longest * 7.2 * 1.25 + 24.0
        required_height = len(node.label_lines) * 16.0 * 1.25 + 24.0
        if node.secondary_label:
            required_height += 13.0 * 1.25
        if estimated_width > bounds.width or required_height > bounds.height:
            diagnostics.append(
                _diagnostic(
                    "GEOMETRY_TEXT_OVERFLOW",
                    f"{node.scene_node_id} label does not fit at 125% text scale.",
                    node.scene_node_id,
                )
            )
    for index, first in enumerate(scene.nodes):
        for second in scene.nodes[index + 1 :]:
            if first.parent_scene_node_id == second.scene_node_id:
                continue
            if second.parent_scene_node_id == first.scene_node_id:
                continue
            if _overlap(first.bounds, second.bounds):
                diagnostics.append(
                    _diagnostic(
                        "GEOMETRY_NODE_OVERLAP",
                        f"{first.scene_node_id} overlaps {second.scene_node_id}.",
                        first.scene_node_id,
                        second.scene_node_id,
                    )
                )

    route_signatures: dict[tuple[tuple[float, float], ...], str] = {}
    for edge in scene.edges:
        source = by_id.get(edge.source_scene_node_id)
        target = by_id.get(edge.target_scene_node_id)
        if source is None or target is None:
            diagnostics.append(
                _diagnostic(
                    "GEOMETRY_EDGE_ENDPOINT_MISSING",
                    f"{edge.scene_edge_id} references a missing scene node.",
                    edge.scene_edge_id,
                )
            )
            continue
        if any(point.x > scene.paper_width or point.y > scene.paper_height for point in edge.points):
            diagnostics.append(
                _diagnostic(
                    "GEOMETRY_EDGE_OFF_CANVAS",
                    f"{edge.scene_edge_id} route extends beyond the paper.",
                    edge.scene_edge_id,
                )
            )
        first, second = edge.points[0], edge.points[1]
        penultimate, last = edge.points[-2], edge.points[-1]
        source_right = source.bounds.x + source.bounds.width
        target_left = target.bounds.x
        if not (
            first.x == source_right
            and first.y == second.y
            and second.x >= first.x
            and last.x == target_left
            and penultimate.y == last.y
            and penultimate.x <= last.x
        ):
            diagnostics.append(
                _diagnostic(
                    "GEOMETRY_PORT_DIRECTION_INVALID",
                    f"{edge.scene_edge_id} does not leave right and enter left orthogonally.",
                    edge.scene_edge_id,
                )
            )
        for opaque in scene.nodes:
            if opaque.shape != "opaque" or opaque.scene_node_id in {
                edge.source_scene_node_id,
                edge.target_scene_node_id,
            }:
                continue
            if any(
                _segment_crosses_rect(a.x, a.y, b.x, b.y, opaque.bounds)
                for a, b in zip(edge.points, edge.points[1:])
            ):
                diagnostics.append(
                    _diagnostic(
                        "GEOMETRY_EDGE_THROUGH_OPAQUE",
                        f"{edge.scene_edge_id} crosses unrelated {opaque.scene_node_id}.",
                        edge.scene_edge_id,
                        opaque.scene_node_id,
                    )
                )
        signature = tuple((point.x, point.y) for point in edge.points)
        if signature in route_signatures:
            diagnostics.append(
                _diagnostic(
                    "GEOMETRY_AMBIGUOUS_CORRIDOR",
                    f"{edge.scene_edge_id} exactly overlaps another complete route.",
                    edge.scene_edge_id,
                )
            )
        route_signatures[signature] = edge.scene_edge_id

    styles_by_type: dict[str, set[tuple[str, str | None]]] = defaultdict(set)
    for edge in scene.edges:
        styles_by_type[edge.edge_type.value].add((edge.stroke, edge.dash))
    representatives = {
        edge_type: next(iter(styles)) for edge_type, styles in styles_by_type.items() if styles
    }
    if len(set(representatives.values())) != len(representatives):
        diagnostics.append(
            _diagnostic(
                "GEOMETRY_EDGE_STYLE_AMBIGUOUS",
                "Distinct edge semantics must remain distinguishable by color or dash pattern.",
            )
        )

    label_placements = edge_label_placements(scene)
    required_labels = {
        edge.scene_edge_id for edge in scene.edges if label_required(scene, edge)
    }
    for missing in sorted(required_labels - label_placements.keys()):
        diagnostics.append(
            _diagnostic(
                "GEOMETRY_EDGE_LABEL_UNPLACED",
                f"{missing} has no collision-free label position.",
                missing,
            )
        )
    placements = list(label_placements.items())
    child_nodes = [node for node in scene.nodes if node.parent_scene_node_id is not None]
    for edge_id, placement in placements:
        for node in child_nodes:
            if _overlap(placement.bounds, node.bounds):
                diagnostics.append(
                    _diagnostic(
                        "GEOMETRY_EDGE_LABEL_NODE_OVERLAP",
                        f"{edge_id} label overlaps {node.scene_node_id}.",
                        edge_id,
                        node.scene_node_id,
                    )
                )
    for index, (first_id, first) in enumerate(placements):
        for second_id, second in placements[index + 1 :]:
            if _overlap(first.bounds, second.bounds):
                diagnostics.append(
                    _diagnostic(
                        "GEOMETRY_EDGE_LABEL_OVERLAP",
                        f"{first_id} label overlaps {second_id} label.",
                        first_id,
                        second_id,
                    )
                )

    gate = GateResult(
        gate="D-geometry",
        status="failed" if diagnostics else "passed",
        message=(
            "VisualScene failed deterministic geometry checks."
            if diagnostics
            else "VisualScene has bounded, non-overlapping nodes, readable labels, and valid routes."
        ),
    )
    return gate, diagnostics
