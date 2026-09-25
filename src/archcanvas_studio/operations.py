from __future__ import annotations

import hashlib
import heapq
import json
import math
from datetime import UTC, datetime
from itertools import pairwise
from typing import TYPE_CHECKING, Any

from archcanvas_core.models import (
    Diagnostic,
    JobState,
    PatchBatch,
    SearchSubject,
    ValidationGateResult,
    ValidationRun,
    VisualPatch,
    VisualScene,
)
from archcanvas_core.validation import validate_architecture
from archcanvas_publication import validate_geometry

if TYPE_CHECKING:
    from .bundle import StudioBundle


def _now() -> str:
    return datetime.now(UTC).isoformat()


def studio_fingerprint(bundle: StudioBundle) -> str:
    payload = {
        "architecture": bundle.architecture.model_dump(mode="json"),
        "source_digest": bundle.document.source_digest,
        "visual_patches": [
            patch.model_dump(mode="json") for patch in bundle.document.visual_patches
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_search_index(bundle: StudioBundle) -> list[SearchSubject]:
    bindings: dict[str, list[dict[str, str]]] = {}
    for projection_id, scene in bundle.materialized_scenes().items():
        for node in scene.nodes:
            for canonical_id in node.canonical_node_ids:
                bindings.setdefault(canonical_id, []).append(
                    {
                        "projection_id": projection_id,
                        "scene_id": scene.scene_id,
                        "scene_node_id": node.scene_node_id,
                    }
                )

    subjects: list[SearchSubject] = []
    for node in bundle.architecture.nodes:
        aliases = [str(node.attributes.get(key, "")) for key in ("module_path", "op_type")]
        subjects.append(
            SearchSubject(
                id=node.node_id,
                kind="node",
                canonical_ids=[node.node_id],
                title=node.semantic_name,
                aliases=[alias for alias in aliases if alias],
                tokens=[node.kind.value, *[parameter.name for parameter in node.parameters]],
                view_bindings=bindings.get(node.node_id, []),
                facets={"kind": "node", "node-kind": node.kind.value},
            )
        )
        for port in [*node.input_ports, *node.output_ports]:
            subjects.append(
                SearchSubject(
                    id=port.port_id,
                    kind="port",
                    canonical_ids=[node.node_id, port.port_id],
                    title=f"{node.semantic_name}.{port.name}",
                    aliases=[port.role, node.semantic_name],
                    tokens=[port.direction, port.role],
                    view_bindings=bindings.get(node.node_id, []),
                    facets={
                        "kind": "port",
                        "direction": port.direction,
                        "role": port.role,
                    },
                )
            )
    for tensor in bundle.architecture.tensors:
        data = tensor.model_dump(mode="json")
        dtype = str(data.get("dtype") or data.get("element_type") or "unknown")
        subjects.append(
            SearchSubject(
                id=tensor.tensor_id,
                kind="tensor",
                canonical_ids=[tensor.tensor_id, tensor.producer_id, *tensor.consumer_ids],
                title=f"{tensor.role} {tensor.tensor_id}",
                aliases=[tensor.symbolic_shape, tensor.role],
                tokens=[dtype, tensor.symbolic_shape, *tensor.semantic_axes],
                view_bindings=bindings.get(tensor.producer_id, []),
                facets={
                    "kind": "tensor",
                    "dtype": dtype,
                    "role": tensor.role,
                    "shape": tensor.symbolic_shape,
                },
            )
        )
    for edge in bundle.architecture.edges:
        subjects.append(
            SearchSubject(
                id=edge.edge_id,
                kind="edge",
                canonical_ids=[
                    edge.edge_id,
                    edge.tensor_id,
                    edge.producer_id,
                    edge.consumer_id,
                ],
                title=f"{edge.producer_id} -> {edge.consumer_id}",
                aliases=[edge.role, edge.edge_type.value],
                tokens=[edge.producer_port, edge.consumer_port, edge.execution_predicate],
                view_bindings=[
                    *bindings.get(edge.producer_id, []),
                    *bindings.get(edge.consumer_id, []),
                ],
                facets={"kind": "edge", "edge-type": edge.edge_type.value, "role": edge.role},
            )
        )
    for evidence in bundle.evidence:
        source_spans: list[dict[str, Any]] = []
        if evidence.path and evidence.span:
            source_spans.append(
                {
                    "path": evidence.path,
                    "start_line": evidence.span.start_line,
                    "end_line": evidence.span.end_line,
                }
            )
        subjects.append(
            SearchSubject(
                id=evidence.evidence_id,
                kind="evidence",
                title=evidence.claim,
                aliases=[item for item in (evidence.path, evidence.symbol) if item],
                tokens=[evidence.kind.value, evidence.confidence.value],
                source_spans=source_spans,
                runtime_bindings=evidence.runtime_observation_ids,
                facets={
                    "kind": "evidence",
                    "confidence": evidence.confidence.value,
                    "evidence-kind": evidence.kind.value,
                },
            )
        )
    for diagnostic in bundle.diagnostics():
        digest = hashlib.sha256(
            f"{diagnostic.code}:{diagnostic.message}".encode()
        ).hexdigest()[:16]
        subjects.append(
            SearchSubject(
                id=f"diagnostic:{digest}",
                kind="diagnostic",
                canonical_ids=diagnostic.target_ids,
                title=diagnostic.message,
                aliases=[diagnostic.code],
                tokens=[diagnostic.severity],
                facets={"kind": "diagnostic", "status": diagnostic.severity},
            )
        )
    return subjects


def search_subjects(
    subjects: list[SearchSubject], query: str, limit: int = 50
) -> list[SearchSubject]:
    terms: list[str] = []
    facets: dict[str, str] = {}
    for token in query.lower().split():
        if ":" in token:
            key, value = token.split(":", 1)
            facets[key] = value.strip('"')
        else:
            terms.append(token.strip('"'))

    def score(subject: SearchSubject) -> int | None:
        if any(subject.facets.get(key, "").lower() != value for key, value in facets.items()):
            return None
        identifier = subject.id.lower()
        title = subject.title.lower()
        haystack = " ".join(
            [identifier, title, *subject.aliases, *subject.tokens, *subject.canonical_ids]
        ).lower()
        if any(term not in haystack for term in terms):
            return None
        return sum(
            100 if term == identifier else 70 if term == title else 40 if title.startswith(term) else 10
            for term in terms
        )

    ranked = [(score(subject), subject) for subject in subjects]
    return [
        subject
        for rank, subject in sorted(
            ((rank, subject) for rank, subject in ranked if rank is not None),
            key=lambda item: (-item[0], item[1].kind, item[1].title.lower()),
        )[:limit]
    ]


def run_validation(
    bundle: StudioBundle,
    profile: str,
    generation: int,
    *,
    runtime_execution_authorized: bool = False,
) -> ValidationRun:
    if profile not in {"fast-static", "publication", "full", "runtime-replay"}:
        raise ValueError("unknown validation profile")
    if profile == "runtime-replay" and not runtime_execution_authorized:
        raise ValueError("runtime replay requires explicit execution authorization")
    started_at = _now()
    gates, diagnostics = validate_architecture(
        bundle.architecture, bundle.evidence, bundle.snapshot
    )
    results = [
        ValidationGateResult(gate=gate.gate, status=gate.status, message=gate.message)
        for gate in gates
    ]
    if profile in {"publication", "full", "runtime-replay"}:
        for projection_id, scene in bundle.materialized_scenes().items():
            gate, found = validate_geometry(scene)
            results.append(
                ValidationGateResult(
                    gate=f"geometry-{projection_id.removeprefix('projection:')}",
                    status=gate.status,
                    message=gate.message,
                )
            )
            diagnostics.extend(found)
    if profile in {"full", "runtime-replay"}:
        if bundle.active_transaction is None:
            results.append(
                ValidationGateResult(
                    gate="transaction-consistency",
                    status="skipped",
                    message="No active source transaction requires consistency validation.",
                )
            )
        else:
            ready = bundle.active_transaction.state.value in {"review-ready", "committed"}
            results.append(
                ValidationGateResult(
                    gate="transaction-consistency",
                    status="passed" if ready else "failed",
                    message=f"Active transaction is {bundle.active_transaction.state.value}.",
                )
            )
    if profile == "runtime-replay":
        results.append(
            ValidationGateResult(
                gate="runtime-evidence",
                status="passed" if bundle.runtime_trace is not None else "unsupported",
                message=(
                    "Loaded runtime receipt contains replay evidence."
                    if bundle.runtime_trace is not None
                    else "No authorized runtime trace is loaded; no project code was executed."
                ),
            )
        )
    failed = any(result.status == "failed" for result in results)
    coverage = {
        "canonical_nodes": 1.0,
        "runtime_nodes": (
            len(bundle.runtime_node_evidence) / max(1, len(bundle.architecture.nodes))
            if bundle.runtime_trace is not None
            else 0.0
        ),
    }
    return ValidationRun(
        validation_id=f"validation:{generation}",
        profile=profile,
        input_fingerprint=studio_fingerprint(bundle),
        generation=generation,
        state=JobState.FAILED if failed else JobState.SUCCEEDED,
        gate_results=results,
        diagnostics=diagnostics,
        coverage=coverage,
        runtime_execution_authorized=runtime_execution_authorized,
        started_at=started_at,
        finished_at=_now(),
    )


def alignment_batch(
    scene: VisualScene,
    selected_ids: list[str],
    command: str,
    *,
    pinned_ids: set[str],
    gap: float | None = None,
    batch_id: str,
) -> PatchBatch:
    nodes = [node for node in scene.nodes if node.scene_node_id in selected_ids]
    if len(nodes) < 2:
        raise ValueError("alignment and distribution require at least two nodes")
    if any(node.scene_node_id in pinned_ids for node in nodes):
        raise ValueError("pinned nodes cannot be moved by alignment commands")
    primary = nodes[-1]
    if command in {"same-width", "same-height", "same-size"}:
        patches = []
        for node in nodes[:-1]:
            width = primary.bounds.width if command != "same-height" else node.bounds.width
            height = primary.bounds.height if command != "same-width" else node.bounds.height
            if (width, height) == (node.bounds.width, node.bounds.height):
                continue
            patches.append(
                VisualPatch(
                    patch_id=(
                        f"patch:{batch_id.removeprefix('batch:')}.{len(patches)}"
                    ),
                    operation="set-size",
                    target_id=node.scene_node_id,
                    value={
                        "scene_id": scene.scene_id,
                        "width": width,
                        "height": height,
                    },
                )
            )
        if not patches:
            raise ValueError("alignment command would not change the document")
        return PatchBatch(batch_id=batch_id, description=command, patches=patches)

    positions = {node.scene_node_id: (node.bounds.x, node.bounds.y) for node in nodes}
    if command in {"left", "hcenter", "right", "top", "vcenter", "bottom"}:
        for node in nodes[:-1]:
            x, y = positions[node.scene_node_id]
            if command == "left":
                x = primary.bounds.x
            elif command == "hcenter":
                x = primary.bounds.x + (primary.bounds.width - node.bounds.width) / 2
            elif command == "right":
                x = primary.bounds.x + primary.bounds.width - node.bounds.width
            elif command == "top":
                y = primary.bounds.y
            elif command == "vcenter":
                y = primary.bounds.y + (primary.bounds.height - node.bounds.height) / 2
            else:
                y = primary.bounds.y + primary.bounds.height - node.bounds.height
            positions[node.scene_node_id] = (max(0, x), max(0, y))
    elif command in {"distribute-horizontal", "distribute-vertical"}:
        horizontal = command.endswith("horizontal")
        ordered = sorted(nodes, key=lambda node: node.bounds.x if horizontal else node.bounds.y)
        if gap is None:
            start = ordered[0].bounds.x if horizontal else ordered[0].bounds.y
            end = (
                ordered[-1].bounds.x + ordered[-1].bounds.width
                if horizontal
                else ordered[-1].bounds.y + ordered[-1].bounds.height
            )
            extent = sum(node.bounds.width if horizontal else node.bounds.height for node in ordered)
            gap = max(0.0, (end - start - extent) / (len(ordered) - 1))
        cursor = ordered[0].bounds.x if horizontal else ordered[0].bounds.y
        for node in ordered:
            x, y = positions[node.scene_node_id]
            positions[node.scene_node_id] = (cursor, y) if horizontal else (x, cursor)
            cursor += (node.bounds.width if horizontal else node.bounds.height) + gap
    else:
        raise ValueError("unknown alignment command")
    patches = [
        VisualPatch(
            patch_id=f"patch:{batch_id.removeprefix('batch:')}.{index}",
            operation="set-position",
            target_id=node.scene_node_id,
            value={"scene_id": scene.scene_id, "x": positions[node.scene_node_id][0], "y": positions[node.scene_node_id][1]},
        )
        for index, node in enumerate(nodes)
        if positions[node.scene_node_id] != (node.bounds.x, node.bounds.y)
    ]
    if not patches:
        raise ValueError("alignment command would not change the document")
    return PatchBatch(batch_id=batch_id, description=command, patches=patches)


def auto_layout_batch(
    scene: VisualScene,
    *,
    baseline_scene: VisualScene,
    pinned_ids: set[str],
    batch_id: str,
) -> PatchBatch:
    """Restore the selected compiler layout without splitting nested modules."""
    if scene.scene_id != baseline_scene.scene_id:
        raise ValueError("auto-layout baseline belongs to a different scene")
    current_by_id = {node.scene_node_id: node for node in scene.nodes}
    baseline_by_id = {node.scene_node_id: node for node in baseline_scene.nodes}
    if set(current_by_id) != set(baseline_by_id):
        raise ValueError("auto-layout baseline has a different node set")

    children: dict[str, list[str]] = {}
    parent_by_id: dict[str, str] = {}
    for node in scene.nodes:
        if node.parent_scene_node_id:
            children.setdefault(node.parent_scene_node_id, []).append(node.scene_node_id)
            parent_by_id[node.scene_node_id] = node.parent_scene_node_id

    roots = sorted(
        node.scene_node_id for node in scene.nodes if node.parent_scene_node_id is None
    )
    outer_root = roots[0] if len(roots) == 1 and children.get(roots[0]) else None
    unit_ids = sorted(children[outer_root]) if outer_root else roots

    subtree_by_unit: dict[str, list[str]] = {}
    for unit_id in unit_ids:
        members: list[str] = []
        pending = [unit_id]
        while pending:
            node_id = pending.pop()
            members.append(node_id)
            pending.extend(sorted(children.get(node_id, []), reverse=True))
        subtree_by_unit[unit_id] = members

    locked_units = {
        unit_id
        for unit_id, members in subtree_by_unit.items()
        if pinned_ids.intersection(members)
    }
    # A pin outside the normal unit frontier locks its nearest top-level
    # ancestor as well, so restoring the baseline cannot move a pinned child
    # indirectly through its container.
    for pinned_id in pinned_ids:
        cursor = pinned_id
        visited: set[str] = set()
        while cursor in parent_by_id and cursor not in visited:
            visited.add(cursor)
            cursor = parent_by_id[cursor]
        if cursor in subtree_by_unit:
            locked_units.add(cursor)

    patches: list[VisualPatch] = []
    for unit_id in unit_ids:
        if unit_id in locked_units:
            continue
        for node_id in subtree_by_unit[unit_id]:
            current = current_by_id[node_id]
            baseline = baseline_by_id[node_id]
            if (current.bounds.x, current.bounds.y) == (
                baseline.bounds.x,
                baseline.bounds.y,
            ):
                continue
            patches.append(
                VisualPatch(
                    patch_id=(
                        f"patch:{batch_id.removeprefix('batch:')}.{len(patches)}"
                    ),
                    operation="set-position",
                    target_id=node_id,
                    value={
                        "scene_id": scene.scene_id,
                        "x": baseline.bounds.x,
                        "y": baseline.bounds.y,
                    },
                )
            )
    if not patches:
        raise ValueError("the current scene is already at its deterministic layout")
    return PatchBatch(batch_id=batch_id, description="auto-layout", patches=patches)


def _route_length(points: list[tuple[float, float]]) -> float:
    return sum(
        abs(end[0] - start[0]) + abs(end[1] - start[1])
        for start, end in pairwise(points)
    )


def _segment_length_inside_rect(
    start: tuple[float, float], end: tuple[float, float], rect: Any
) -> float:
    """Return the length of an orthogonal segment inside a rectangle."""
    if abs(start[0] - end[0]) < 1e-6:
        if not rect.x < start[0] < rect.x + rect.width:
            return 0.0
        return max(
            0.0,
            min(max(start[1], end[1]), rect.y + rect.height)
            - max(min(start[1], end[1]), rect.y),
        )
    if abs(start[1] - end[1]) < 1e-6:
        if not rect.y < start[1] < rect.y + rect.height:
            return 0.0
        return max(
            0.0,
            min(max(start[0], end[0]), rect.x + rect.width)
            - max(min(start[0], end[0]), rect.x),
        )
    return math.dist(start, end)


def _compact_route(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    compact: list[tuple[float, float]] = []
    for point in points:
        if compact and point == compact[-1]:
            continue
        compact.append(point)
        while len(compact) >= 3:
            first, middle, last = compact[-3:]
            vertical_middle = (
                first[0] == middle[0] == last[0]
                and min(first[1], last[1]) <= middle[1] <= max(first[1], last[1])
            )
            horizontal_middle = (
                first[1] == middle[1] == last[1]
                and min(first[0], last[0]) <= middle[0] <= max(first[0], last[0])
            )
            if vertical_middle or horizontal_middle:
                compact.pop(-2)
            else:
                break
    return compact


def _route_directions_valid(
    points: list[tuple[float, float]], source_side: str, target_side: str
) -> bool:
    if len(points) < 2:
        return False
    first, second = points[0], points[1]
    penultimate, last = points[-2], points[-1]
    source_valid = {
        "left": second[1] == first[1] and second[0] <= first[0],
        "right": second[1] == first[1] and second[0] >= first[0],
        "top": second[0] == first[0] and second[1] <= first[1],
        "bottom": second[0] == first[0] and second[1] >= first[1],
    }[source_side]
    target_valid = {
        "left": penultimate[1] == last[1] and penultimate[0] <= last[0],
        "right": penultimate[1] == last[1] and penultimate[0] >= last[0],
        "top": penultimate[0] == last[0] and penultimate[1] <= last[1],
        "bottom": penultimate[0] == last[0] and penultimate[1] >= last[1],
    }[target_side]
    return source_valid and target_valid


def _route_port(bounds: Any, side: str) -> tuple[float, float]:
    if side == "left":
        return bounds.x, bounds.y + bounds.height / 2
    if side == "right":
        return bounds.x + bounds.width, bounds.y + bounds.height / 2
    if side == "top":
        return bounds.x + bounds.width / 2, bounds.y
    return bounds.x + bounds.width / 2, bounds.y + bounds.height


def _port_stub(
    point: tuple[float, float], side: str, distance: float = 24.0
) -> tuple[float, float]:
    if side == "left":
        return point[0] - distance, point[1]
    if side == "right":
        return point[0] + distance, point[1]
    if side == "top":
        return point[0], point[1] - distance
    return point[0], point[1] + distance


def _route_inside_unrelated(
    points: list[tuple[float, float]],
    scene: VisualScene,
    related_ids: set[str],
) -> tuple[int, float, int, float, float]:
    crossed_node_ids: set[str] = set()
    crossed_container_ids: set[str] = set()
    node_length = 0.0
    container_length = 0.0
    clearance_length = 0.0
    for start, end in pairwise(points):
        for node in scene.nodes:
            if node.scene_node_id in related_ids:
                continue
            length = _segment_length_inside_rect(start, end, node.bounds)
            if node.shape == "container":
                container_length += length
                if length > 1e-6:
                    crossed_container_ids.add(node.scene_node_id)
            else:
                node_length += length
                if length > 1e-6:
                    crossed_node_ids.add(node.scene_node_id)
                margin = 10.0
                expanded = node.bounds.model_copy(
                    update={
                        "x": node.bounds.x - margin,
                        "y": node.bounds.y - margin,
                        "width": node.bounds.width + margin * 2,
                        "height": node.bounds.height + margin * 2,
                    }
                )
                clearance_length += _segment_length_inside_rect(start, end, expanded)
    return (
        len(crossed_node_ids),
        node_length,
        len(crossed_container_ids),
        container_length,
        clearance_length,
    )


def _orthogonal_segment_interaction(
    first_start: tuple[float, float],
    first_end: tuple[float, float],
    second_start: tuple[float, float],
    second_end: tuple[float, float],
) -> tuple[int, float]:
    first_vertical = abs(first_start[0] - first_end[0]) < 1e-6
    second_vertical = abs(second_start[0] - second_end[0]) < 1e-6
    if first_vertical == second_vertical:
        first_axis = first_start[0] if first_vertical else first_start[1]
        second_axis = second_start[0] if second_vertical else second_start[1]
        if abs(first_axis - second_axis) >= 1e-6:
            return 0, 0.0
        first_interval = sorted(
            (first_start[1], first_end[1])
            if first_vertical
            else (first_start[0], first_end[0])
        )
        second_interval = sorted(
            (second_start[1], second_end[1])
            if second_vertical
            else (second_start[0], second_end[0])
        )
        overlap = max(
            0.0,
            min(first_interval[1], second_interval[1])
            - max(first_interval[0], second_interval[0]),
        )
        return 0, overlap

    vertical_start, vertical_end = (
        (first_start, first_end) if first_vertical else (second_start, second_end)
    )
    horizontal_start, horizontal_end = (
        (second_start, second_end) if first_vertical else (first_start, first_end)
    )
    crossing = (
        min(horizontal_start[0], horizontal_end[0])
        <= vertical_start[0]
        <= max(horizontal_start[0], horizontal_end[0])
        and min(vertical_start[1], vertical_end[1])
        <= horizontal_start[1]
        <= max(vertical_start[1], vertical_end[1])
    )
    if not crossing:
        return 0, 0.0
    point = (vertical_start[0], horizontal_start[1])
    first_endpoint = point in {first_start, first_end}
    second_endpoint = point in {second_start, second_end}
    return (0 if first_endpoint and second_endpoint else 1), 0.0


def _route_interactions(
    points: list[tuple[float, float]],
    routed: list[tuple[list[tuple[float, float]], str, str]],
    source_id: str,
    target_id: str,
) -> tuple[int, float]:
    crossings = 0
    overlap = 0.0
    candidate_segments = list(pairwise(points))
    for other_points, other_source_id, other_target_id in routed:
        other_segments = list(pairwise(other_points))
        for index, (start, end) in enumerate(candidate_segments):
            for other_index, (other_start, other_end) in enumerate(other_segments):
                short_stubs = (
                    _route_length([start, end]) <= 32.0
                    and _route_length([other_start, other_end]) <= 32.0
                )
                shared_source_stub = (
                    short_stubs
                    and source_id == other_source_id
                    and index == 0
                    and other_index == 0
                )
                shared_target_stub = (
                    short_stubs
                    and target_id == other_target_id
                    and index == len(candidate_segments) - 1
                    and other_index == len(other_segments) - 1
                )
                if shared_source_stub or shared_target_stub:
                    continue
                segment_crossings, segment_overlap = _orthogonal_segment_interaction(
                    start, end, other_start, other_end
                )
                crossings += segment_crossings
                overlap += segment_overlap
    return crossings, overlap


def _route_candidates(
    scene: VisualScene,
    source_node: Any,
    target_node: Any,
    *,
    corridor_xs: list[float],
    corridor_ys: list[float],
    port_pairs: list[tuple[str, str]],
) -> list[tuple[list[tuple[float, float]], str | None, str, str]]:
    candidates: list[tuple[list[tuple[float, float]], str | None, str, str]] = []
    for source_side, target_side in port_pairs:
        start = _route_port(source_node.bounds, source_side)
        source_stub = _port_stub(start, source_side)
        end = _route_port(target_node.bounds, target_side)
        target_stub = _port_stub(end, target_side)
        raw_routes = [
            [start, source_stub, (source_stub[0], target_stub[1]), target_stub, end],
            [start, source_stub, (target_stub[0], source_stub[1]), target_stub, end],
        ]
        middle_x = (source_stub[0] + target_stub[0]) / 2
        middle_y = (source_stub[1] + target_stub[1]) / 2
        raw_routes.extend(
            [
                [
                    start,
                    source_stub,
                    (middle_x, source_stub[1]),
                    (middle_x, target_stub[1]),
                    target_stub,
                    end,
                ],
                [
                    start,
                    source_stub,
                    (source_stub[0], middle_y),
                    (target_stub[0], middle_y),
                    target_stub,
                    end,
                ],
            ]
        )
        for route in raw_routes:
            candidates.append(
                (_compact_route(route), None, source_side, target_side)
            )
        for corridor_x in corridor_xs:
            candidates.append(
                (
                    _compact_route(
                        [
                            start,
                            source_stub,
                            (corridor_x, source_stub[1]),
                            (corridor_x, target_stub[1]),
                            target_stub,
                            end,
                        ]
                    ),
                    f"x:{corridor_x}",
                    source_side,
                    target_side,
                )
            )
        for corridor_y in corridor_ys:
            candidates.append(
                (
                    _compact_route(
                        [
                            start,
                            source_stub,
                            (source_stub[0], corridor_y),
                            (target_stub[0], corridor_y),
                            target_stub,
                            end,
                        ]
                    ),
                    f"y:{corridor_y}",
                    source_side,
                    target_side,
                )
            )
    return candidates


def _segment_hits_box(
    start: tuple[float, float],
    end: tuple[float, float],
    box: tuple[float, float, float, float],
) -> bool:
    """Return whether an orthogonal segment enters a box interior."""
    left, top, right, bottom = box
    if abs(start[0] - end[0]) < 1e-6:
        return (
            left < start[0] < right
            and max(min(start[1], end[1]), top)
            < min(max(start[1], end[1]), bottom)
        )
    if abs(start[1] - end[1]) < 1e-6:
        return (
            top < start[1] < bottom
            and max(min(start[0], end[0]), left)
            < min(max(start[0], end[0]), right)
        )
    return True


def _orthogonal_shortest_path(
    scene: VisualScene,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    related_ids: set[str],
    soft_obstacles: list[Any],
    routed: list[tuple[list[tuple[float, float]], str, str]],
    strategy: str,
) -> list[tuple[float, float]] | None:
    """Find a deterministic obstacle-aware path on an orthogonal visibility grid."""
    clearance = 10.0
    blockers: list[tuple[float, float, float, float]] = []
    xs = {8.0, scene.paper_width - 8.0, start[0], end[0]}
    ys = {8.0, scene.paper_height - 8.0, start[1], end[1]}
    by_id = {node.scene_node_id: node for node in scene.nodes}

    def hidden_by_blocked_ancestor(node: Any) -> bool:
        parent_id = node.parent_scene_node_id
        visited: set[str] = set()
        while parent_id in by_id and parent_id not in visited:
            if parent_id not in related_ids:
                return True
            visited.add(parent_id)
            parent_id = by_id[parent_id].parent_scene_node_id
        return False

    for node in scene.nodes:
        if node.scene_node_id in related_ids or hidden_by_blocked_ancestor(node):
            continue
        bounds = node.bounds
        left = max(8.0, bounds.x - clearance)
        top = max(8.0, bounds.y - clearance)
        right = min(scene.paper_width - 8.0, bounds.x + bounds.width + clearance)
        bottom = min(scene.paper_height - 8.0, bounds.y + bounds.height + clearance)
        if right <= left or bottom <= top:
            continue
        blockers.append((left, top, right, bottom))
        xs.update((left, right))
        ys.update((top, bottom))
    for bounds in soft_obstacles:
        xs.update(
            (
                max(8.0, bounds.x - clearance),
                min(scene.paper_width - 8.0, bounds.x + bounds.width + clearance),
            )
        )
        ys.update(
            (
                max(8.0, bounds.y - clearance),
                min(scene.paper_height - 8.0, bounds.y + bounds.height + clearance),
            )
        )

    # Existing routes contribute neighbouring lanes. This is what lets a
    # crowded corridor fan into parallel tracks instead of sharing a trunk.
    lane_offsets = (-16.0, -8.0, 8.0, 16.0)
    occupied_xs: set[float] = set()
    occupied_ys: set[float] = set()
    for points, _, _ in routed:
        for first, second in pairwise(points):
            if abs(first[0] - second[0]) < 1e-6:
                occupied_xs.add(first[0])
            elif abs(first[1] - second[1]) < 1e-6:
                occupied_ys.add(first[1])
    focus_x = (start[0] + end[0]) / 2.0
    focus_y = (start[1] + end[1]) / 2.0
    for coordinate in sorted(occupied_xs, key=lambda value: abs(value - focus_x))[:16]:
        xs.update(
            coordinate + offset
            for offset in lane_offsets
            if 8.0 <= coordinate + offset <= scene.paper_width - 8.0
        )
    for coordinate in sorted(occupied_ys, key=lambda value: abs(value - focus_y))[:16]:
        ys.update(
            coordinate + offset
            for offset in lane_offsets
            if 8.0 <= coordinate + offset <= scene.paper_height - 8.0
        )

    x_values = sorted(xs)
    y_values = sorted(ys)
    x_index = {value: index for index, value in enumerate(x_values)}
    y_index = {value: index for index, value in enumerate(y_values)}
    start_index = (x_index[start[0]], y_index[start[1]])
    end_index = (x_index[end[0]], y_index[end[1]])

    def point(index: tuple[int, int]) -> tuple[float, float]:
        return x_values[index[0]], y_values[index[1]]

    def point_blocked(candidate: tuple[float, float]) -> bool:
        if candidate in {start, end}:
            return False
        return any(
            left < candidate[0] < right and top < candidate[1] < bottom
            for left, top, right, bottom in blockers
        )

    bend_cost = {"avoid": 28.0, "balanced": 22.0, "compact": 14.0}[strategy]
    crossing_cost = {"avoid": 900.0, "balanced": 520.0, "compact": 280.0}[
        strategy
    ]
    overlap_cost = {"avoid": 90.0, "balanced": 55.0, "compact": 28.0}[
        strategy
    ]
    container_cost = {"avoid": 12.0, "balanced": 6.0, "compact": 2.5}[strategy]
    horizontal_routes: dict[float, list[tuple[float, float]]] = {}
    vertical_routes: dict[float, list[tuple[float, float]]] = {}
    for points, _, _ in routed:
        for first, second in pairwise(points):
            if abs(first[0] - second[0]) < 1e-6:
                vertical_routes.setdefault(first[0], []).append(
                    tuple(sorted((first[1], second[1])))
                )
            elif abs(first[1] - second[1]) < 1e-6:
                horizontal_routes.setdefault(first[1], []).append(
                    tuple(sorted((first[0], second[0])))
                )

    interaction_cache: dict[
        tuple[tuple[float, float], tuple[float, float]], tuple[int, float]
    ] = {}

    def interactions(
        first: tuple[float, float], second: tuple[float, float]
    ) -> tuple[int, float]:
        key = tuple(sorted((first, second)))
        cached = interaction_cache.get(key)
        if cached is not None:
            return cached
        crossings = 0
        overlap = 0.0
        if abs(first[1] - second[1]) < 1e-6:
            low, high = sorted((first[0], second[0]))
            for other_low, other_high in horizontal_routes.get(first[1], []):
                overlap += max(0.0, min(high, other_high) - max(low, other_low))
            crossings = sum(
                low <= x <= high
                for x, intervals in vertical_routes.items()
                for other_low, other_high in intervals
                if other_low <= first[1] <= other_high
            )
        else:
            low, high = sorted((first[1], second[1]))
            for other_low, other_high in vertical_routes.get(first[0], []):
                overlap += max(0.0, min(high, other_high) - max(low, other_low))
            crossings = sum(
                low <= y <= high
                for y, intervals in horizontal_routes.items()
                for other_low, other_high in intervals
                if other_low <= first[0] <= other_high
            )
        interaction_cache[key] = crossings, overlap
        return crossings, overlap

    # State includes the incoming direction so the search can price bends.
    initial_state = (*start_index, "")
    distances: dict[tuple[int, int, str], float] = {initial_state: 0.0}
    previous: dict[tuple[int, int, str], tuple[int, int, str]] = {}
    serial = 0
    queue: list[tuple[float, float, int, tuple[int, int, str]]] = [
        (
            abs(end[0] - start[0]) + abs(end[1] - start[1]),
            0.0,
            serial,
            initial_state,
        )
    ]
    final_state: tuple[int, int, str] | None = None
    while queue:
        _, cost, _, state = heapq.heappop(queue)
        if cost != distances.get(state):
            continue
        ix, iy, incoming = state
        if (ix, iy) == end_index:
            final_state = state
            break
        neighbours = []
        if ix > 0:
            neighbours.append((ix - 1, iy, "h"))
        if ix + 1 < len(x_values):
            neighbours.append((ix + 1, iy, "h"))
        if iy > 0:
            neighbours.append((ix, iy - 1, "v"))
        if iy + 1 < len(y_values):
            neighbours.append((ix, iy + 1, "v"))
        origin = point((ix, iy))
        for next_x, next_y, direction in neighbours:
            destination = point((next_x, next_y))
            if point_blocked(destination) or any(
                _segment_hits_box(origin, destination, blocker)
                for blocker in blockers
            ):
                continue
            length = abs(destination[0] - origin[0]) + abs(
                destination[1] - origin[1]
            )
            crossings, overlap = interactions(origin, destination)
            step_cost = (
                length
                + crossings * crossing_cost
                + overlap * overlap_cost
                + sum(
                    _segment_length_inside_rect(origin, destination, bounds)
                    for bounds in soft_obstacles
                )
                * container_cost
                + (bend_cost if incoming and incoming != direction else 0.0)
            )
            next_state = (next_x, next_y, direction)
            next_cost = cost + step_cost
            if next_cost >= distances.get(next_state, math.inf) - 1e-9:
                continue
            distances[next_state] = next_cost
            previous[next_state] = state
            serial += 1
            heuristic = abs(end[0] - destination[0]) + abs(
                end[1] - destination[1]
            )
            heapq.heappush(
                queue,
                (next_cost + heuristic, next_cost, serial, next_state),
            )
    if final_state is None:
        return None
    reversed_points: list[tuple[float, float]] = []
    cursor = final_state
    while True:
        reversed_points.append(point((cursor[0], cursor[1])))
        if cursor == initial_state:
            break
        cursor = previous[cursor]
    return _compact_route(list(reversed(reversed_points)))


def auto_route_batch(
    scene: VisualScene, *, batch_id: str, strategy: str = "avoid"
) -> PatchBatch:
    """Route edges with obstacle-aware orthogonal search and congestion costs."""
    if strategy not in {"avoid", "balanced", "compact"}:
        raise ValueError("route strategy must be avoid, balanced, or compact")
    by_id = {node.scene_node_id: node for node in scene.nodes}

    def ancestors(node_id: str) -> set[str]:
        result = {node_id}
        current = by_id[node_id]
        while current.parent_scene_node_id:
            result.add(current.parent_scene_node_id)
            current = by_id[current.parent_scene_node_id]
        return result

    def route_edge(
        edge: Any,
        routed: list[tuple[list[tuple[float, float]], str, str]],
    ) -> tuple[list[tuple[float, float]], set[str]] | None:
        source_node = by_id[edge.source_scene_node_id]
        target_node = by_id[edge.target_scene_node_id]
        source_ancestors = ancestors(edge.source_scene_node_id)
        target_ancestors = ancestors(edge.target_scene_node_id)
        # An edge must be able to leave its source compound and enter its
        # target compound. Every other module is a true routing obstacle.
        hard_related_ids = source_ancestors | target_ancestors
        metric_related_ids = {
            edge.source_scene_node_id,
            edge.target_scene_node_id,
            *(source_ancestors & target_ancestors),
        }
        soft_obstacles = [
            by_id[node_id].bounds
            for node_id in sorted(hard_related_ids - metric_related_ids)
            if by_id[node_id].shape == "container"
        ]
        source_center = (
            source_node.bounds.x + source_node.bounds.width / 2,
            source_node.bounds.y + source_node.bounds.height / 2,
        )
        target_center = (
            target_node.bounds.x + target_node.bounds.width / 2,
            target_node.bounds.y + target_node.bounds.height / 2,
        )
        vertical = abs(target_center[1] - source_center[1]) >= (
            abs(target_center[0] - source_center[0]) * 0.5
        )
        if vertical:
            source_side = "bottom" if target_center[1] > source_center[1] else "top"
            target_side = "top" if target_center[1] > source_center[1] else "bottom"
        else:
            source_side = "right" if target_center[0] > source_center[0] else "left"
            target_side = "left" if target_center[0] > source_center[0] else "right"
        start = _route_port(source_node.bounds, source_side)
        end = _route_port(target_node.bounds, target_side)
        source_stub = _port_stub(start, source_side)
        target_stub = _port_stub(end, target_side)
        if any(
            x < 0 or y < 0 or x > scene.paper_width or y > scene.paper_height
            for x, y in (source_stub, target_stub)
        ):
            return None
        middle = _orthogonal_shortest_path(
            scene,
            source_stub,
            target_stub,
            related_ids=hard_related_ids,
            soft_obstacles=soft_obstacles,
            routed=routed,
            strategy=strategy,
        )
        if middle is None:
            # A malformed or extremely tight legacy scene can leave a stub in
            # an obstacle clearance box. Preserve a deterministic escape path
            # while still applying the same global scoring policy.
            candidates = _route_candidates(
                scene,
                source_node,
                target_node,
                corridor_xs=[8.0, scene.paper_width - 8.0],
                corridor_ys=[8.0, scene.paper_height - 8.0],
                port_pairs=[(source_side, target_side)],
            )
            valid = [
                points
                for points, _, candidate_source, candidate_target in candidates
                if _route_directions_valid(
                    points, candidate_source, candidate_target
                )
                and not any(
                    x < 0
                    or y < 0
                    or x > scene.paper_width
                    or y > scene.paper_height
                    for x, y in points
                )
            ]
            if not valid:
                return None

            def fallback_score(
                points: list[tuple[float, float]],
            ) -> tuple[float, ...]:
                obstruction = _route_inside_unrelated(
                    points, scene, metric_related_ids
                )
                crossings, overlap = _route_interactions(
                    points,
                    routed,
                    edge.source_scene_node_id,
                    edge.target_scene_node_id,
                )
                return (
                    obstruction[0],
                    obstruction[1],
                    obstruction[2],
                    obstruction[3],
                    overlap,
                    crossings,
                    _route_length(points),
                    len(points),
                )

            return min(valid, key=fallback_score), metric_related_ids
        points = _compact_route([start, source_stub, *middle, target_stub, end])
        if not _route_directions_valid(points, source_side, target_side):
            return None
        return points, metric_related_ids

    routes: dict[str, tuple[list[tuple[float, float]], set[str]]] = {}
    routed: list[tuple[list[tuple[float, float]], str, str]] = []
    ordered_edges = sorted(
        scene.edges,
        key=lambda edge: (
            -(
                abs(
                    by_id[edge.source_scene_node_id].bounds.x
                    - by_id[edge.target_scene_node_id].bounds.x
                )
                + abs(
                    by_id[edge.source_scene_node_id].bounds.y
                    - by_id[edge.target_scene_node_id].bounds.y
                )
            ),
            edge.scene_edge_id,
        ),
    )
    for edge in ordered_edges:
        result = route_edge(edge, routed)
        if result is None:
            continue
        points, related_ids = result
        routes[edge.scene_edge_id] = (points, related_ids)
        routed.append(
            (points, edge.source_scene_node_id, edge.target_scene_node_id)
        )

    # One deterministic rip-up/reroute pass gives early paths a chance to use
    # the lanes opened by later paths. Accept only strict local improvements.
    edge_by_id = {edge.scene_edge_id: edge for edge in scene.edges}

    def route_quality(
        edge: Any,
        points: list[tuple[float, float]],
        related_ids: set[str],
        others: list[tuple[list[tuple[float, float]], str, str]],
    ) -> tuple[float, ...]:
        obstruction = _route_inside_unrelated(points, scene, related_ids)
        crossings, overlap = _route_interactions(
            points,
            others,
            edge.source_scene_node_id,
            edge.target_scene_node_id,
        )
        return (
            obstruction[0],
            obstruction[1],
            obstruction[2],
            obstruction[3],
            overlap,
            crossings,
            _route_length(points),
            max(0, len(points) - 2),
        )

    conflicted = []
    for edge_id, (points, related_ids) in routes.items():
        edge = edge_by_id[edge_id]
        others = [
            (other_points, edge_by_id[other_id].source_scene_node_id, edge_by_id[other_id].target_scene_node_id)
            for other_id, (other_points, _) in routes.items()
            if other_id != edge_id
        ]
        crossings, overlap = _route_interactions(
            points,
            others,
            edge.source_scene_node_id,
            edge.target_scene_node_id,
        )
        if crossings or overlap > 1e-6:
            conflicted.append((-(overlap + crossings * 1000.0), edge_id, related_ids))
    for _, edge_id, related_ids in sorted(conflicted)[:12]:
        edge = edge_by_id[edge_id]
        others = [
            (other_points, edge_by_id[other_id].source_scene_node_id, edge_by_id[other_id].target_scene_node_id)
            for other_id, (other_points, _) in routes.items()
            if other_id != edge_id
        ]
        replacement = route_edge(edge, others)
        if replacement is None:
            continue
        new_points, new_related_ids = replacement
        old_points = routes[edge_id][0]
        if route_quality(edge, new_points, new_related_ids, others) < route_quality(
            edge, old_points, related_ids, others
        ):
            routes[edge_id] = (new_points, new_related_ids)

    patches: list[VisualPatch] = []
    for edge in scene.edges:
        if edge.scene_edge_id not in routes:
            continue
        points = routes[edge.scene_edge_id][0]
        current = [(point.x, point.y) for point in edge.points]
        if points == current:
            continue
        patches.append(
            VisualPatch(
                patch_id=f"patch:{batch_id.removeprefix('batch:')}.{len(patches)}",
                operation="set-route-hint",
                target_id=edge.scene_edge_id,
                value={
                    "scene_id": scene.scene_id,
                    "points": [{"x": x, "y": y} for x, y in points],
                },
            )
        )
    if not patches:
        raise ValueError("the current scene has no obstructed routes")
    return PatchBatch(
        batch_id=batch_id,
        description=f"auto-route:{strategy}",
        patches=patches,
    )


def proof_severity(status: str) -> int:
    return {
        "invalid": 7,
        "stale": 6,
        "unproven": 5,
        "conditional": 4,
        "checking": 3,
        "proven": 2,
        "review-ready": 1,
    }.get(status, 0)


def diagnostics_for_validation(run: ValidationRun) -> list[Diagnostic]:
    return run.diagnostics
