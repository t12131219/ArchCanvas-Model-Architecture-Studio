from __future__ import annotations

import math
import re
import textwrap
from collections import defaultdict, deque
from itertools import pairwise

from archcanvas_core.models import (
    NodeKind,
    PublicationNode,
    PublicationView,
    SceneEdge,
    SceneNode,
    ScenePoint,
    SceneRect,
    VisualEdgeStyle,
    VisualNodeStyle,
    VisualRelation,
    VisualScene,
    VisualSpec,
)

from .glyphs import resolve_node_glyph

NODE_WIDTH = 210.0
NODE_HEIGHT = 106.0
ROW_GAP = 76.0
LAYOUT_MODES = (
    "auto",
    "dual-swimlane",
    "single-lane",
    "hierarchical",
    "branch-tree",
    "force-directed",
    "radial",
    "orthogonal",
)


def _node_style(node: PublicationNode, fully_expanded: bool) -> tuple[str, str, str]:
    style = resolve_node_glyph(node, fully_expanded)
    return style.glyph, style.fill, style.stroke


def _edge_style(relation: VisualRelation) -> tuple[str, str | None, float]:
    return {
        VisualRelation.SEQUENCE: ("#263238", None, 1.8),
        VisualRelation.PARALLEL_BRANCH: ("#356f9f", "8 3", 1.9),
        VisualRelation.MERGE: ("#a15c00", None, 2.1),
        VisualRelation.RESIDUAL: ("#c2410c", "11 4", 2.1),
        VisualRelation.SHAPE_TRANSFORM: ("#7048a8", "3 3", 1.9),
        VisualRelation.MEMORY_REFERENCE: ("#007c91", "9 3", 2.0),
        VisualRelation.CONDITION: ("#8f3f97", "6 4", 1.8),
        VisualRelation.ROUTING: ("#495057", "2 3", 1.8),
        VisualRelation.STATE_UPDATE: ("#087f5b", "4 2 1 2", 1.9),
        VisualRelation.PARAMETER_SHARE: ("#9c2f76", "8 3 2 3", 1.8),
        VisualRelation.TRAINING_ONLY: ("#868e96", "5 5", 1.6),
    }[relation]


def _relation_label(relation: VisualRelation) -> str:
    return {
        VisualRelation.SEQUENCE: "flow",
        VisualRelation.PARALLEL_BRANCH: "branch",
        VisualRelation.MERGE: "merge",
        VisualRelation.RESIDUAL: "residual",
        VisualRelation.SHAPE_TRANSFORM: "reshape",
        VisualRelation.MEMORY_REFERENCE: "memory",
        VisualRelation.CONDITION: "condition",
        VisualRelation.ROUTING: "route",
        VisualRelation.STATE_UPDATE: "state",
        VisualRelation.PARAMETER_SHARE: "shared",
        VisualRelation.TRAINING_ONLY: "training",
    }[relation]


def build_visual_spec(view: PublicationView) -> VisualSpec:
    node_styles: list[VisualNodeStyle] = []
    for node in view.nodes:
        glyph, fill, stroke = _node_style(node, view.fully_expanded)
        secondary: str | None = None
        if node.attributes.get("repeat_count") is not None:
            secondary = f"{node.attributes['repeat_count']}x repeated"
        elif node.collapsed:
            secondary = f"{len(node.canonical_node_ids)} canonical nodes"
        elif not node.canonical_node_ids:
            secondary = f"{node.attributes.get('canonical_count', 0)} contained nodes"
        elif view.fully_expanded:
            secondary = str(node.attributes.get("op_type") or node.canonical_node_ids[0])
        elif node.boundary_roles:
            secondary = ", ".join(node.boundary_roles[:3])
        node_styles.append(
            VisualNodeStyle(
                view_node_id=node.view_node_id,
                glyph=glyph,
                fill=fill,
                stroke=stroke,
                label=node.semantic_name,
                secondary_label=secondary,
            )
        )
    edge_styles: list[VisualEdgeStyle] = []
    for edge in view.edges:
        stroke, dash, width = _edge_style(edge.visual_relation)
        label = edge.role
        if view.visible_depth > 1 and edge.symbolic_shape != "[?]":
            label = f"{label} {edge.symbolic_shape}"
        if edge.visual_relation is not VisualRelation.SEQUENCE:
            label = f"{_relation_label(edge.visual_relation)} · {label}"
        edge_styles.append(
            VisualEdgeStyle(
                view_edge_id=edge.view_edge_id,
                visual_relation=edge.visual_relation,
                stroke=stroke,
                dash=dash,
                width=width,
                label=label,
            )
        )
    return VisualSpec(
        spec_id=f"spec:{view.view_id.removeprefix('view:')}",
        view_id=view.view_id,
        font_family="Arial, Helvetica, Noto Sans CJK SC, sans-serif",
        node_styles=node_styles,
        edge_styles=edge_styles,
    )


def _ranks(view: PublicationView, node_ids: list[str]) -> dict[str, int]:
    """Rank the graph after collapsing cycles into deterministic components."""
    order = {node_id: index for index, node_id in enumerate(node_ids)}
    successors: dict[str, set[str]] = defaultdict(set)
    for edge in view.edges:
        source, target = edge.source_view_node_id, edge.target_view_node_id
        if source not in order or target not in order or source == target:
            continue
        successors[source].add(target)

    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def connect(node_id: str) -> None:
        nonlocal index
        indices[node_id] = index
        lowlinks[node_id] = index
        index += 1
        stack.append(node_id)
        on_stack.add(node_id)
        for target in sorted(successors[node_id], key=order.get):
            if target not in indices:
                connect(target)
                lowlinks[node_id] = min(lowlinks[node_id], lowlinks[target])
            elif target in on_stack:
                lowlinks[node_id] = min(lowlinks[node_id], indices[target])
        if lowlinks[node_id] != indices[node_id]:
            return
        component: list[str] = []
        while stack:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == node_id:
                break
        components.append(sorted(component, key=order.get))

    for node_id in node_ids:
        if node_id not in indices:
            connect(node_id)

    component_by_node = {
        node_id: component_index
        for component_index, members in enumerate(components)
        for node_id in members
    }
    component_successors: dict[int, set[int]] = defaultdict(set)
    indegree = {component_index: 0 for component_index in range(len(components))}
    for source, targets in successors.items():
        source_component = component_by_node[source]
        for target in targets:
            target_component = component_by_node[target]
            if source_component == target_component:
                continue
            if target_component not in component_successors[source_component]:
                component_successors[source_component].add(target_component)
                indegree[target_component] += 1

    component_order = {
        component_index: min(order[node_id] for node_id in members)
        for component_index, members in enumerate(components)
    }
    queue = deque(
        sorted(
            (component for component, degree in indegree.items() if degree == 0),
            key=component_order.get,
        )
    )
    component_ranks = {component: 0 for component in queue}
    while queue:
        source_component = queue.popleft()
        for target in sorted(
            component_successors[source_component], key=component_order.get
        ):
            component_ranks[target] = max(
                component_ranks.get(target, 0),
                component_ranks[source_component] + 1,
            )
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    return {
        node_id: component_ranks[component_by_node[node_id]] for node_id in node_ids
    }


def _lane(node: PublicationNode, family: str, fallback: int) -> int:
    text = f"{node.view_node_id} {node.semantic_name}".lower()
    if family == "dual-lane":
        if "encoder" in text or "enc_" in text:
            return 0
        if "cross" in text or "memory" in text:
            return 1
        if "decoder" in text or "dec_" in text:
            return 2
        return 3
    if family == "dual-backbone":
        if "residual" in text:
            return 0
        if "trend" in text:
            return 1
        if "main" in text:
            return 2
        return 3
    if family == "multiscale-ladder":
        match = re.search(r"scale[. _/-]?(\d+)", text)
        return int(match.group(1)) if match else 4
    if family == "single-lane":
        return 0
    return fallback


def _wrap_label(label: str) -> list[str]:
    lines = textwrap.wrap(
        label,
        width=20,
        break_long_words=True,
        break_on_hyphens=True,
        max_lines=3,
        placeholder="...",
    )
    return lines or [label[:20] or "?"]


def _compact_label(label: str) -> list[str]:
    lines = textwrap.wrap(
        label,
        width=15,
        break_long_words=True,
        break_on_hyphens=True,
        max_lines=3,
        placeholder="...",
    )
    return lines or [label[:15] or "?"]


def _detail_label(label: str) -> list[str]:
    """Keep dense expanded diagrams readable without growing every rank."""
    lines = textwrap.wrap(
        label,
        width=17,
        break_long_words=True,
        break_on_hyphens=True,
        max_lines=2,
        placeholder="...",
    )
    return lines or [label[:17] or "?"]


def _scene_shape(glyph: str) -> str:
    return {
        "operator": "rect",
        "tensor": "tensor",
        "container": "container",
        "merge": "merge",
        "io": "io",
        "state": "state",
        "opaque": "opaque",
        "projection": "projection",
        "activation": "activation",
        "normalization": "normalization",
        "attention": "attention",
        "transform": "transform",
        "condition": "condition",
        "repeat": "repeat",
    }[glyph]


def _simplify_route(points: list[ScenePoint]) -> list[ScenePoint]:
    simplified: list[ScenePoint] = []
    for point in points:
        if simplified and simplified[-1].x == point.x and simplified[-1].y == point.y:
            continue
        simplified.append(point)
        while len(simplified) >= 3:
            first, middle, last = simplified[-3:]
            vertical_middle = (
                first.x == middle.x == last.x
                and min(first.y, last.y) <= middle.y <= max(first.y, last.y)
            )
            horizontal_middle = (
                first.y == middle.y == last.y
                and min(first.x, last.x) <= middle.x <= max(first.x, last.x)
            )
            if vertical_middle or horizontal_middle:
                simplified.pop(-2)
            else:
                break
    return simplified


def _segment_inside_rect(first: ScenePoint, second: ScenePoint, rect: SceneRect) -> float:
    if first.x == second.x and rect.x < first.x < rect.x + rect.width:
        return max(
            0.0,
            min(max(first.y, second.y), rect.y + rect.height)
            - max(min(first.y, second.y), rect.y),
        )
    if first.y == second.y and rect.y < first.y < rect.y + rect.height:
        return max(
            0.0,
            min(max(first.x, second.x), rect.x + rect.width)
            - max(min(first.x, second.x), rect.x),
        )
    return 0.0


def _avoid_opaque_nodes(
    points: list[ScenePoint],
    nodes: list[SceneNode],
    source_id: str,
    target_id: str,
    paper_width: float,
    paper_height: float,
) -> list[ScenePoint]:
    """Select a short orthogonal corridor that avoids unrelated opaque nodes."""
    blockers = [
        node
        for node in nodes
        if node.shape == "opaque" and node.scene_node_id not in {source_id, target_id}
    ]
    if not blockers or len(points) < 4:
        return points
    start, first_lead = points[0], points[1]
    penultimate, end = points[-2], points[-1]

    def short_stub(
        anchor: ScenePoint, direction: ScenePoint, distance: float = 24.0
    ) -> ScenePoint:
        dx = direction.x - anchor.x
        dy = direction.y - anchor.y
        if abs(dx) >= abs(dy):
            sign = 1.0 if dx >= 0.0 else -1.0
            return ScenePoint(
                x=min(paper_width, max(0.0, anchor.x + sign * distance)),
                y=anchor.y,
            )
        sign = 1.0 if dy >= 0.0 else -1.0
        return ScenePoint(
            x=anchor.x,
            y=min(paper_height, max(0.0, anchor.y + sign * distance)),
        )

    lead_start = short_stub(start, first_lead)
    lead_end = short_stub(end, penultimate)
    candidates = [points]
    x_corridors = {18.0, paper_width - 18.0}
    y_corridors = {18.0, paper_height - 18.0}
    for blocker in blockers:
        x_corridors.update(
            {
                max(18.0, blocker.bounds.x - 18.0),
                min(paper_width - 18.0, blocker.bounds.x + blocker.bounds.width + 18.0),
            }
        )
        y_corridors.update(
            {
                max(18.0, blocker.bounds.y - 18.0),
                min(paper_height - 18.0, blocker.bounds.y + blocker.bounds.height + 18.0),
            }
        )
    for corridor_x in x_corridors:
        candidates.append(
            _simplify_route(
                [
                    points[0],
                    lead_start,
                    ScenePoint(x=corridor_x, y=lead_start.y),
                    ScenePoint(x=corridor_x, y=lead_end.y),
                    lead_end,
                    points[-1],
                ]
            )
        )
    for corridor_y in y_corridors:
        candidates.append(
            _simplify_route(
                [
                    points[0],
                    lead_start,
                    ScenePoint(x=lead_start.x, y=corridor_y),
                    ScenePoint(x=lead_end.x, y=corridor_y),
                    lead_end,
                    points[-1],
                ]
            )
        )

    def score(candidate: list[ScenePoint]) -> tuple[float, float, int]:
        obstruction = sum(
            _segment_inside_rect(first, second, blocker.bounds)
            for first, second in pairwise(candidate)
            for blocker in blockers
        )
        length = sum(
            abs(second.x - first.x) + abs(second.y - first.y)
            for first, second in pairwise(candidate)
        )
        return obstruction, length, len(candidate)

    return min(candidates, key=score)


def _overview_label_lines(node: PublicationNode) -> list[str]:
    label = node.semantic_name.strip()
    lowered = label.lower()
    names = " ".join(str(name).lower() for name in node.attributes.get("operation_names", []))
    if "encoder" in lowered and all(token in names for token in ("q", "k", "v")):
        return ["Encoder", "Q / K / V attention", "Residual + norm"]
    if "decoder" in lowered and "mask" in names and "cross" in names:
        return ["Decoder", "Masked + cross attention", "Residual + norm"]
    if "ffn" in lowered and "activation" in names:
        return ["Feed forward", "Linear + activation", "Linear projection"]
    if "output" in lowered:
        return ["Output head", "Add + norm + linear", "Model output"]
    if "input" in lowered:
        return ["Inputs", "src + tgt", "target mask"]
    operations = [str(name) for name in node.attributes.get("operation_names", [])]
    return [label, *operations[:2]][:3]


def _overview_role(node: PublicationNode) -> str:
    """Return a stable semantic role for a collapsed dual-lane stage.

    The role is intentionally derived from the node's authored name and
    operation summary rather than from a model profile.  This keeps the
    Transformer layout reusable for time-series variants and future model
    families that expose different spelling or casing for the same stage.
    """
    name = node.semantic_name.lower()
    text = " ".join(
        str(value)
        for value in (
            node.semantic_name,
            node.attributes.get("source_expression", ""),
            *node.attributes.get("operation_names", []),
            *node.attributes.get("path", []),
        )
    ).lower()
    if any(token in name for token in ("input", "source", "covariate")):
        return "inputs"
    if any(token in text for token in ("x_enc", "x_dec", "src", "tgt")):
        return "inputs"
    if "encoder" in name or "backbone" in name:
        return "encoder"
    if "decoder" in name:
        return "decoder"
    if any(token in name for token in ("ffn", "feed forward", "feedforward", "mlp", "projection head")):
        return "ffn"
    if any(token in name for token in ("output", "forecast", "prediction", "head", "generator")):
        return "output"
    if any(
        token in name
        for token in (
            "decomp",
            "seasonal",
            "trend",
            "state",
            "memory",
            "normalization",
            "denormal",
        )
    ):
        return "decomposition"
    if any(token in text for token in ("output", "forecast", "prediction", "head", "generator")):
        return "output"
    if any(token in text for token in ("decomp", "seasonal", "trend", "state", "memory", "normal")):
        return "decomposition"
    return "auxiliary"


def _overview_summary_lines(role: str, members: list[PublicationNode]) -> list[str]:
    """Use concise, role-aware copy while keeping source symbols untouched."""
    labels = {
        "inputs": ["Inputs", "source + target", "masks / covariates"],
        "encoder": ["Encoder", "feature extraction", "attention / residual"],
        "decoder": ["Decoder", "self + cross attention", "residual / output"],
        "ffn": ["Feed forward", "linear + activation", "projection"],
        "decomposition": ["Decomposition", "seasonal + trend", "state / normalization"],
        "output": ["Output head", "forecast / prediction", "model output"],
    }
    if role in labels:
        return labels[role]
    return _overview_label_lines(members[0])


def _build_vertical_dual_lane_scene(
    view: PublicationView,
    spec: VisualSpec,
    *,
    scene_layout_family: str | None = None,
) -> VisualScene:
    by_view = {node.view_node_id: node for node in view.nodes}
    root = next(
        (
            node
            for node in view.nodes
            if node.parent_view_node_id is None and node.kind is NodeKind.MODULE_CONTAINER
        ),
        None,
    )
    visible_children: dict[str, list[PublicationNode]] = defaultdict(list)
    for node in view.nodes:
        if node.parent_view_node_id is not None:
            visible_children[node.parent_view_node_id].append(node)
    container_ids = {parent for parent, members in visible_children.items() if members}
    placed = [
        node
        for node in view.nodes
        if node is not root and node.view_node_id not in container_ids
    ]
    if not placed:
        placed = list(view.nodes)
        root = None
    rankable_ids = [node.view_node_id for node in placed if node.canonical_node_ids]
    ranks = _ranks(view, rankable_ids)
    styles = {style.view_node_id: style for style in spec.node_styles}

    def top_owner(node: PublicationNode) -> PublicationNode:
        cursor = node
        while cursor.parent_view_node_id not in {None, "viewnode:model"}:
            parent = by_view.get(cursor.parent_view_node_id)
            if parent is None:
                break
            cursor = parent
        return cursor

    owner_nodes: list[PublicationNode] = []
    for node in placed:
        owner = top_owner(node)
        if all(item.view_node_id != owner.view_node_id for item in owner_nodes):
            owner_nodes.append(owner)
    owner_order = {node.view_node_id: index for index, node in enumerate(owner_nodes)}
    owner_successors: dict[str, set[str]] = defaultdict(set)
    owner_predecessors: dict[str, set[str]] = defaultdict(set)
    for edge in view.edges:
        source_node = by_view.get(edge.source_view_node_id)
        target_node = by_view.get(edge.target_view_node_id)
        if source_node is None or target_node is None:
            continue
        source = top_owner(source_node).view_node_id
        target = top_owner(target_node).view_node_id
        if source == target:
            continue
        owner_successors[source].add(target)
        owner_predecessors[target].add(source)

    owner_lanes: dict[str, int] = {}
    role_lanes = {
        "inputs": 2,
        "encoder": 0,
        "decoder": 1,
        "ffn": 1,
        "decomposition": 2,
        "output": 1,
    }
    for owner in owner_nodes:
        role = _overview_role(owner)
        if role in role_lanes:
            owner_lanes[owner.view_node_id] = role_lanes[role]
            continue
        text = f"{owner.semantic_name} {owner.view_node_id}".lower()
        if any(token in text for token in ("residual", "season", "backbone", "scale")):
            owner_lanes[owner.view_node_id] = 0
        elif any(token in text for token in ("trend", "forecast", "projection", "head")):
            owner_lanes[owner.view_node_id] = 1

    # Parallel successors and merge predecessors occupy opposite lanes when
    # semantic evidence did not already determine their placement.
    branch_sets = [
        members
        for members in [*owner_successors.values(), *owner_predecessors.values()]
        if len(members) > 1
    ]
    for members in branch_sets:
        for index, owner_id in enumerate(sorted(members, key=owner_order.get)):
            owner_lanes.setdefault(owner_id, index % 2)
    fallback_lane = 0
    for owner in owner_nodes:
        if owner.view_node_id not in owner_lanes:
            owner_lanes[owner.view_node_id] = fallback_lane
            fallback_lane = 1 - fallback_lane

    def lane(node: PublicationNode) -> int:
        owner = top_owner(node)
        text = f"{owner.semantic_name} {node.semantic_name} {node.view_node_id}".lower()
        if _overview_role(owner) == "inputs":
            if "src" in text and "tgt" not in text and "target" not in text:
                return 0
            if any(token in text for token in ("tgt", "target", "mask")):
                return 1
            return 2
        return owner_lanes[owner.view_node_id]

    def ancestor_names(node: PublicationNode) -> set[str]:
        names: set[str] = set()
        cursor = node
        while cursor.parent_view_node_id is not None:
            parent = by_view.get(cursor.parent_view_node_id)
            if parent is None:
                break
            names.add(parent.semantic_name.lower())
            cursor = parent
        return names

    decoder_norm_ranks = [
        ranks[node.view_node_id]
        for node in placed
        if node.view_node_id in ranks and "decoder_norm" in node.semantic_name.lower()
    ]
    cross_nodes = [
        node
        for node in placed
        if node.view_node_id in ranks and "cross" in ancestor_names(node)
    ]
    if decoder_norm_ranks and cross_nodes:
        minimum_cross_rank = min(ranks[node.view_node_id] for node in cross_nodes)
        shift = max(decoder_norm_ranks) + 1 - minimum_cross_rank
        if shift > 0:
            for node in cross_nodes:
                ranks[node.view_node_id] += shift
            changed = True
            while changed:
                changed = False
                for edge in view.edges:
                    source_rank = ranks.get(edge.source_view_node_id)
                    target_rank = ranks.get(edge.target_view_node_id)
                    if source_rank is None or target_rank is None:
                        continue
                    required = source_rank + 1
                    if target_rank < required:
                        ranks[edge.target_view_node_id] = required
                        changed = True

    # A collapsed publication is always a semantic overview.  Do not require
    # the exact Transformer vocabulary here: Autoformer and future families
    # may call the same swimlanes ``decomposition``, ``backbone`` or
    # ``forecast`` while still benefiting from the same visual grammar.
    overview = view.visible_depth <= 1 and not view.fully_expanded
    leaf_scene_nodes: list[SceneNode] = []
    view_to_scene: dict[str, str] = {}
    overview_aliases: dict[str, SceneNode] = {}
    root_scene_id = (
        f"scenenode:{root.view_node_id.removeprefix('viewnode:')}" if root is not None else None
    )
    dense_layout = False

    if overview:
        paper_width = 1120.0
        stage_ranks = _ranks(view, [node.view_node_id for node in placed])
        rank_members: dict[tuple[int, int], list[PublicationNode]] = defaultdict(list)
        for index, node in enumerate(placed):
            rank_members[(stage_ranks.get(node.view_node_id, index), lane(node))].append(node)
        for members in rank_members.values():
            members.sort(key=lambda item: owner_order.get(item.view_node_id, 0))
        rank_values = sorted({rank for rank, _ in rank_members}, reverse=True)
        rank_heights = {
            rank: max(
                (
                    len(members) * 150.0 + max(0, len(members) - 1) * 22.0
                    for (member_rank, _), members in rank_members.items()
                    if member_rank == rank
                ),
                default=150.0,
            )
            for rank in rank_values
        }
        rank_top: dict[int, float] = {}
        cursor_y = 72.0
        for rank in rank_values:
            rank_top[rank] = cursor_y
            cursor_y += rank_heights[rank] + 72.0
        paper_height = max(760.0, cursor_y + 54.0)
        lane_left = {0: 70.0, 1: 740.0, 2: 410.0}
        lane_width = {0: 320.0, 1: 320.0, 2: 300.0}

        for (rank, lane_id), members in sorted(
            rank_members.items(), key=lambda item: (-item[0][0], item[0][1])
        ):
            for row, node in enumerate(members):
                style = styles[node.view_node_id]
                role = _overview_role(node)
                scene_id = f"scenenode:{node.view_node_id.removeprefix('viewnode:')}"
                scene_node = SceneNode(
                    scene_node_id=scene_id,
                    view_node_id=node.view_node_id,
                    canonical_node_ids=node.canonical_node_ids,
                    bounds=SceneRect(
                        x=lane_left[lane_id],
                        y=rank_top[rank] + row * 172.0,
                        width=lane_width[lane_id],
                        height=150.0,
                    ),
                    shape="container",
                    label_lines=_overview_summary_lines(role, [node]),
                    secondary_label=style.secondary_label,
                    fill=style.fill,
                    stroke=style.stroke,
                    parent_scene_node_id=root_scene_id,
                    evidence_ids=node.evidence_ids,
                )
                leaf_scene_nodes.append(scene_node)
                view_to_scene[node.view_node_id] = scene_id
                overview_aliases[node.view_node_id] = scene_node
    else:
        # The fully expanded Transformer has roughly thirty topological ranks.
        # Compact rank geometry keeps both lanes visible as one publication-style
        # diagram while preserving every Exact IR operation and containment box.
        dense_layout = any(len(node.semantic_name) > 18 for node in placed)
        node_width = 190.0 if dense_layout else 182.0
        node_height = 68.0 if dense_layout else 64.0
        column_gap = 42.0 if dense_layout else 54.0
        lane_left = {0: 50.0, 1: 970.0, 2: 759.0}
        lane_width = {0: 680.0, 1: 680.0, 2: node_width}
        columns = {0: 3, 1: 3, 2: 1}
        members: dict[tuple[int, int], list[PublicationNode]] = defaultdict(list)
        for index, node in enumerate(placed):
            members[(ranks.get(node.view_node_id, index), lane(node))].append(node)

        branch_order = {"q": 0, "k": 1, "v": 2}

        def member_order(node: PublicationNode) -> tuple[int, str]:
            owner = node.parent_view_node_id
            parent_name = by_view[owner].semantic_name.lower() if owner in by_view else ""
            return branch_order.get(parent_name, 3), node.view_node_id

        for group in members.values():
            group.sort(key=member_order)

        def track_node(node: PublicationNode) -> PublicationNode | None:
            owner = top_owner(node)
            cursor = node
            while cursor.parent_view_node_id not in {None, owner.view_node_id}:
                parent = by_view.get(cursor.parent_view_node_id)
                if parent is None:
                    break
                cursor = parent
            return cursor if cursor is not node or not node.canonical_node_ids else None

        track_slots: dict[str, int] = {}
        tracks_by_lane: dict[int, list[PublicationNode]] = defaultdict(list)
        for node in placed:
            track = track_node(node)
            if track is not None and all(
                item.view_node_id != track.view_node_id for item in tracks_by_lane[lane(node)]
            ):
                tracks_by_lane[lane(node)].append(track)
        for lane_id, tracks in tracks_by_lane.items():
            if lane_id == 2:
                continue
            fallback_slot = 0
            for track in sorted(tracks, key=lambda item: item.view_node_id):
                name = track.semantic_name.lower()
                if name in branch_order:
                    slot = branch_order[name]
                elif any(token in name for token in ("residual", "seasonal")):
                    slot = 0
                elif "trend" in name:
                    slot = 2
                elif any(token in name for token in ("context", "score", "out", "mask", "cross")):
                    slot = 1
                else:
                    slot = fallback_slot % 3
                    fallback_slot += 1
                track_slots[track.view_node_id] = slot

        slot_by_node: dict[str, tuple[int, int]] = {}
        rows_by_rank: dict[int, int] = defaultdict(lambda: 1)
        for (rank, lane_id), group in members.items():
            occupied: list[set[int]] = []
            for node in group:
                parent = by_view.get(node.parent_view_node_id or "")
                parent_name = parent.semantic_name.lower() if parent is not None else ""
                track = track_node(node)
                preferred = (
                    branch_order[parent_name]
                    if parent_name in branch_order
                    else track_slots.get(track.view_node_id) if track is not None else None
                )
                row = 0
                while True:
                    if row == len(occupied):
                        occupied.append(set())
                    available = [
                        column
                        for column in range(columns[lane_id])
                        if column not in occupied[row]
                    ]
                    if preferred is not None and preferred in available:
                        column = preferred
                        break
                    if preferred is None and available:
                        column = available[len(available) // 2]
                        break
                    row += 1
                occupied[row].add(column)
                slot_by_node[node.view_node_id] = (row, column)
            rows_by_rank[rank] = max(rows_by_rank[rank], len(occupied))

        rank_values = sorted({rank for rank, _ in members}, reverse=True)
        rank_top: dict[int, float] = {}
        cursor_y = 92.0
        for rank in rank_values:
            rank_top[rank] = cursor_y
            if dense_layout:
                rank_span = (
                    (rows_by_rank[rank] - 1) * (node_height + 28.0) + node_height
                )
                cursor_y += rank_span + 28.0
            else:
                cursor_y += rows_by_rank[rank] * (node_height + 18.0) + 26.0
        paper_width = 1740.0 if dense_layout else 1700.0
        paper_height = max(720.0, cursor_y + 70.0)

        for (rank, lane_id), group in sorted(
            members.items(), key=lambda item: (-item[0][0], item[0][1])
        ):
            total_width = (
                columns[lane_id] * node_width
                + max(0, columns[lane_id] - 1) * column_gap
            )
            start_x = lane_left[lane_id] + (lane_width[lane_id] - total_width) / 2
            for node in group:
                row, column = slot_by_node[node.view_node_id]
                style = styles[node.view_node_id]
                owner_y_offset = 32.0 if top_owner(node).semantic_name.lower() == "inputs" else 0.0
                scene_id = f"scenenode:{node.view_node_id.removeprefix('viewnode:')}"
                view_to_scene[node.view_node_id] = scene_id
                label_lines = _detail_label(style.label)
                parent_scene_id = (
                    f"scenenode:{node.parent_view_node_id.removeprefix('viewnode:')}"
                    if node.parent_view_node_id
                    else None
                )
                leaf_scene_nodes.append(
                    SceneNode(
                        scene_node_id=scene_id,
                        view_node_id=node.view_node_id,
                        canonical_node_ids=node.canonical_node_ids,
                        bounds=SceneRect(
                            x=start_x + column * (node_width + column_gap),
                            y=rank_top[rank]
                            + row * (node_height + (28.0 if dense_layout else 44.0))
                            + owner_y_offset,
                            width=node_width,
                            height=node_height,
                        ),
                        shape=_scene_shape(style.glyph),
                        label_lines=label_lines,
                        secondary_label=(
                            None
                            if dense_layout or len(label_lines) > 1
                            else style.secondary_label
                        ),
                        fill=style.fill,
                        stroke=style.stroke,
                        parent_scene_node_id=parent_scene_id,
                        evidence_ids=node.evidence_ids,
                    )
                )

    scene_by_view = {node.view_node_id: node for node in leaf_scene_nodes}
    container_scene_nodes: list[SceneNode] = []
    if not overview:
        containers = sorted(
            (
                node
                for node in view.nodes
                if node is not root and node.view_node_id in container_ids
            ),
            key=lambda node: int(node.attributes.get("depth", 0)),
            reverse=True,
        )
        for node in containers:
            children = [
                scene_by_view[child.view_node_id]
                for child in visible_children[node.view_node_id]
                if child.view_node_id in scene_by_view
            ]
            if not children:
                continue
            left = max(30.0, min(child.bounds.x for child in children) - 18.0)
            top = max(30.0, min(child.bounds.y for child in children) - 30.0)
            right = max(child.bounds.x + child.bounds.width for child in children) + 18.0
            bottom = max(child.bounds.y + child.bounds.height for child in children) + 18.0
            style = styles[node.view_node_id]
            scene_id = f"scenenode:{node.view_node_id.removeprefix('viewnode:')}"
            parent_scene_id = (
                f"scenenode:{node.parent_view_node_id.removeprefix('viewnode:')}"
                if node.parent_view_node_id
                else None
            )
            scene_node = SceneNode(
                scene_node_id=scene_id,
                view_node_id=node.view_node_id,
                canonical_node_ids=node.canonical_node_ids,
                bounds=SceneRect(x=left, y=top, width=right - left, height=bottom - top),
                shape="container",
                label_lines=_compact_label(style.label),
                secondary_label=style.secondary_label,
                fill=style.fill,
                stroke=style.stroke,
                parent_scene_node_id=parent_scene_id,
                evidence_ids=node.evidence_ids,
            )
            scene_by_view[node.view_node_id] = scene_node
            view_to_scene[node.view_node_id] = scene_id
            container_scene_nodes.append(scene_node)
        paper_width = max(
            paper_width,
            max((node.bounds.x + node.bounds.width + 38.0 for node in scene_by_view.values()), default=0),
        )
        paper_height = max(
            paper_height,
            max((node.bounds.y + node.bounds.height + 56.0 for node in scene_by_view.values()), default=0),
        )

        # Structural containers are tightened from the leaves upward. This
        # avoids retaining stale empty space after a nested sibling is shifted.
        scene_by_id = {node.scene_node_id: node for node in scene_by_view.values()}

        def descendants(scene_id: str) -> list[str]:
            result: list[str] = []
            pending = [scene_id]
            while pending:
                parent_id = pending.pop()
                children = [
                    node.scene_node_id
                    for node in scene_by_id.values()
                    if node.parent_scene_node_id == parent_id
                ]
                result.extend(children)
                pending.extend(children)
            return result

        def shift_subtree(scene_id: str, dx: float, dy: float) -> None:
            for item_id in [scene_id, *descendants(scene_id)]:
                item = scene_by_id[item_id]
                scene_by_id[item_id] = item.model_copy(
                    update={
                        "bounds": item.bounds.model_copy(
                            update={"x": item.bounds.x + dx, "y": item.bounds.y + dy}
                        )
                    }
                )

        def depth(scene_id: str) -> int:
            value = 0
            cursor = scene_by_id[scene_id]
            visited: set[str] = set()
            while cursor.parent_scene_node_id in scene_by_id:
                parent_id = cursor.parent_scene_node_id
                if parent_id is None or parent_id in visited:
                    break
                visited.add(parent_id)
                value += 1
                cursor = scene_by_id[parent_id]
            return value

        def tighten_containers() -> bool:
            tightened = False
            containers = sorted(
                (item for item in scene_by_id.values() if item.shape == "container"),
                key=lambda item: (-depth(item.scene_node_id), item.scene_node_id),
            )
            for container in containers:
                children = [
                    item
                    for item in scene_by_id.values()
                    if item.parent_scene_node_id == container.scene_node_id
                ]
                if not children:
                    continue
                horizontal_padding = 18.0
                title_padding = 30.0
                bottom_padding = 18.0
                left = max(
                    18.0,
                    min(item.bounds.x for item in children) - horizontal_padding,
                )
                top = max(
                    18.0,
                    min(item.bounds.y for item in children) - title_padding,
                )
                right = (
                    max(item.bounds.x + item.bounds.width for item in children)
                    + horizontal_padding
                )
                bottom = (
                    max(item.bounds.y + item.bounds.height for item in children)
                    + bottom_padding
                )
                minimum_width = (
                    max(len(line) for line in container.label_lines) * 7.2 * 1.25
                    + 28.0
                )
                width = max(minimum_width, right - left)
                bounds = container.bounds.model_copy(
                    update={
                        "x": left,
                        "y": top,
                        "width": width,
                        "height": bottom - top,
                    }
                )
                current = scene_by_id[container.scene_node_id]
                if bounds != current.bounds:
                    scene_by_id[container.scene_node_id] = current.model_copy(
                        update={"bounds": bounds}
                    )
                    tightened = True
            return tightened

        for _ in range(12):
            changed = tighten_containers()
            siblings: dict[str | None, list[SceneNode]] = defaultdict(list)
            for node in scene_by_id.values():
                siblings[node.parent_scene_node_id].append(node)
            for members in siblings.values():
                members.sort(key=lambda item: (item.bounds.y, item.bounds.x, item.scene_node_id))
                accepted: list[SceneNode] = []
                for member in members:
                    current = scene_by_id[member.scene_node_id]
                    for prior in accepted:
                        if not (
                            prior.bounds.x < current.bounds.x + current.bounds.width
                            and prior.bounds.x + prior.bounds.width > current.bounds.x
                            and prior.bounds.y < current.bounds.y + current.bounds.height
                            and prior.bounds.y + prior.bounds.height > current.bounds.y
                        ):
                            continue
                        horizontal_shift = (
                            prior.bounds.x + prior.bounds.width - current.bounds.x + 24.0
                        )
                        vertical_shift = (
                            prior.bounds.y + prior.bounds.height - current.bounds.y + 24.0
                        )
                        if horizontal_shift <= vertical_shift:
                            shift_subtree(current.scene_node_id, horizontal_shift, 0.0)
                        else:
                            shift_subtree(current.scene_node_id, 0.0, vertical_shift)
                        current = scene_by_id[current.scene_node_id]
                        changed = True
                    accepted.append(current)
            if not changed:
                break

        tighten_containers()

        leaf_scene_nodes = [scene_by_id[node.scene_node_id] for node in leaf_scene_nodes]
        container_scene_nodes = [
            scene_by_id[node.scene_node_id] for node in container_scene_nodes
        ]
        scene_by_view = {node.view_node_id: node for node in scene_by_id.values()}
        paper_width = max(
            paper_width,
            max((node.bounds.x + node.bounds.width + 72.0 for node in scene_by_id.values()), default=paper_width),
        )
        paper_height = max(
            paper_height,
            max((node.bounds.y + node.bounds.height + 72.0 for node in scene_by_id.values()), default=paper_height),
        )

    scene_nodes = [
        *sorted(
            container_scene_nodes,
            key=lambda node: int(by_view[node.view_node_id].attributes.get("depth", 0)),
        ),
        *leaf_scene_nodes,
    ]
    scene_nodes = _compact_compound_nodes(scene_nodes, preserve_flow=True)
    paper_width = max(
        720.0,
        max(node.bounds.x + node.bounds.width for node in scene_nodes) + 72.0,
    )
    paper_height = max(
        420.0,
        max(node.bounds.y + node.bounds.height for node in scene_nodes) + 72.0,
    )
    if root is not None:
        style = styles[root.view_node_id]
        view_to_scene[root.view_node_id] = root_scene_id or "scenenode:model"
        scene_nodes.insert(
            0,
            SceneNode(
                scene_node_id=root_scene_id or "scenenode:model",
                view_node_id=root.view_node_id,
                canonical_node_ids=root.canonical_node_ids,
                bounds=SceneRect(
                    x=18.0,
                    y=18.0,
                    width=paper_width - 36.0,
                    height=paper_height - 36.0,
                ),
                shape="container",
                label_lines=_compact_label(style.label),
                secondary_label=style.secondary_label,
                fill=style.fill,
                stroke=style.stroke,
                evidence_ids=root.evidence_ids,
            ),
        )

    by_scene_id = {node.scene_node_id: node for node in scene_nodes}
    overview_aliases = {
        view_id: by_scene_id[node.scene_node_id]
        for view_id, node in overview_aliases.items()
    }
    by_scene_view = {node.view_node_id: node for node in scene_nodes}
    # Overview role groups intentionally alias several PublicationNodes to a
    # single summary box.  Resolve those aliases for routing while retaining
    # the original view-node IDs in the publication data.
    by_scene_view.update(overview_aliases)
    edge_styles = {style.view_edge_id: style for style in spec.edge_styles}
    outgoing_edges: dict[str, list[str]] = defaultdict(list)
    incoming_edges: dict[str, list[str]] = defaultdict(list)
    for edge in view.edges:
        if edge.source_view_node_id in by_scene_view and edge.target_view_node_id in by_scene_view:
            outgoing_edges[edge.source_view_node_id].append(edge.view_edge_id)
            incoming_edges[edge.target_view_node_id].append(edge.view_edge_id)

    def port_offset(edge_id: str, edge_ids: list[str], spacing: float, limit: float) -> float:
        if len(edge_ids) <= 1:
            return 0.0
        step = min(spacing, (limit * 2.0) / (len(edge_ids) - 1))
        return (edge_ids.index(edge_id) - (len(edge_ids) - 1) / 2.0) * step

    residual_index = 0
    scene_edges: list[SceneEdge] = []
    for index, edge in enumerate(view.edges):
        source_node = by_scene_view.get(edge.source_view_node_id)
        target_node = by_scene_view.get(edge.target_view_node_id)
        if source_node is None or target_node is None:
            continue
        if source_node.scene_node_id == target_node.scene_node_id:
            # The edge is internal to a collapsed semantic role.  Its exact
            # identity remains in the PublicationView's canonical mapping;
            # drawing a zero-length self-loop would obscure the overview.
            continue
        source, target = source_node.bounds, target_node.bounds
        source_lane = lane(by_view[edge.source_view_node_id])
        target_lane = lane(by_view[edge.target_view_node_id])
        if (
            edge.visual_relation is VisualRelation.MEMORY_REFERENCE
            and source.x + source.width <= target.x
        ):
            source_offset = port_offset(
                edge.view_edge_id,
                outgoing_edges[edge.source_view_node_id],
                11.0,
                source.height / 2.0 - 10.0,
            )
            target_offset = port_offset(
                edge.view_edge_id,
                incoming_edges[edge.target_view_node_id],
                11.0,
                target.height / 2.0 - 10.0,
            )
            start = ScenePoint(
                x=source.x + source.width,
                y=source.y + source.height / 2 + source_offset,
            )
            end = ScenePoint(
                x=target.x,
                y=target.y + target.height / 2 + target_offset,
            )
            corridor_x = (start.x + end.x) / 2
            points = [
                start,
                ScenePoint(x=corridor_x, y=start.y),
                ScenePoint(x=corridor_x, y=end.y),
                end,
            ]
        else:
            source_offset = port_offset(
                edge.view_edge_id,
                outgoing_edges[edge.source_view_node_id],
                16.0,
                source.width / 2.0 - 18.0,
            )
            target_offset = port_offset(
                edge.view_edge_id,
                incoming_edges[edge.target_view_node_id],
                16.0,
                target.width / 2.0 - 18.0,
            )
            vertical_overlap = not (
                source.y + source.height <= target.y
                or target.y + target.height <= source.y
            )
            horizontal_overlap = not (
                source.x + source.width < target.x
                or target.x + target.width < source.x
            )
            if edge.visual_relation is VisualRelation.RESIDUAL:
                # Residuals use an outside corridor so they never cut through
                # the lane they skip over, while retaining distinct target
                # ports for a shared residual destination.
                start = ScenePoint(
                    x=source.x + source.width / 2 + source_offset,
                    y=source.y,
                )
                end = ScenePoint(
                    x=target.x + target.width / 2 + target_offset,
                    y=target.y + target.height,
                )
                if dense_layout and vertical_overlap and horizontal_overlap:
                    corridor_x = max(source.x + source.width, target.x + target.width) + 28.0
                    source_side_offset = port_offset(
                        edge.view_edge_id,
                        outgoing_edges[edge.source_view_node_id],
                        16.0,
                        source.height / 2.0 - 10.0,
                    )
                    target_side_offset = port_offset(
                        edge.view_edge_id,
                        incoming_edges[edge.target_view_node_id],
                        16.0,
                        target.height / 2.0 - 10.0,
                    )
                    start = ScenePoint(
                        x=source.x + source.width,
                        y=source.y + source.height / 2 + source_side_offset,
                    )
                    end = ScenePoint(
                        x=target.x + target.width,
                        y=target.y + target.height / 2 + target_side_offset,
                    )
                    points = [
                        start,
                        ScenePoint(x=corridor_x, y=start.y),
                        ScenePoint(x=corridor_x, y=end.y),
                        end,
                    ]
                else:
                    lane_left_edge = min(source.x, target.x)
                    lane_right_edge = max(source.x + source.width, target.x + target.width)
                    if source_lane == 0 and target_lane == 0:
                        corridor_x = max(32.0, lane_left_edge - 42.0 - residual_index * 9.0)
                    else:
                        corridor_x = min(
                            paper_width - 32.0,
                            lane_right_edge + 42.0 + residual_index * 9.0,
                        )
                    residual_index += 1
                    points = [
                        start,
                        ScenePoint(x=start.x, y=start.y - 24.0),
                        ScenePoint(x=corridor_x, y=start.y - 24.0),
                        ScenePoint(x=corridor_x, y=end.y + 24.0),
                        ScenePoint(x=end.x, y=end.y + 24.0),
                        end,
                    ]
            elif vertical_overlap and not horizontal_overlap:
                source_side_offset = port_offset(
                    edge.view_edge_id,
                    outgoing_edges[edge.source_view_node_id],
                    16.0,
                    source.height / 2.0 - 10.0,
                )
                target_side_offset = port_offset(
                    edge.view_edge_id,
                    incoming_edges[edge.target_view_node_id],
                    16.0,
                    target.height / 2.0 - 10.0,
                )
                if source.x < target.x:
                    start = ScenePoint(
                        x=source.x + source.width,
                        y=source.y + source.height / 2 + source_side_offset,
                    )
                    end = ScenePoint(
                        x=target.x,
                        y=target.y + target.height / 2 + target_side_offset,
                    )
                else:
                    start = ScenePoint(
                        x=source.x + source.width,
                        y=source.y + source.height / 2 + source_side_offset,
                    )
                    end = ScenePoint(
                        x=target.x,
                        y=target.y + target.height / 2 + target_side_offset,
                    )
                if source.x < target.x:
                    corridor_x = (start.x + end.x) / 2 + ((index % 5) - 2) * 5.0
                    points = [
                        start,
                        ScenePoint(x=corridor_x, y=start.y),
                        ScenePoint(x=corridor_x, y=end.y),
                        end,
                    ]
                else:
                    corridor_y = (
                        max(
                            source.y + source.height,
                            target.y + target.height,
                        )
                        + 28.0
                        + (index % 3) * 7.0
                    )
                    points = [
                        start,
                        ScenePoint(x=start.x + 24.0, y=start.y),
                        ScenePoint(x=start.x + 24.0, y=corridor_y),
                        ScenePoint(x=end.x - 24.0, y=corridor_y),
                        ScenePoint(x=end.x - 24.0, y=end.y),
                        end,
                    ]
            elif vertical_overlap and horizontal_overlap:
                # Shared embedding branches can occupy overlapping rank bands.
                # Route around the right edge and use right-side ports instead
                # of producing a visually backwards top/bottom edge.
                corridor_x = max(source.x + source.width, target.x + target.width) + 28.0
                source_side_offset = port_offset(
                    edge.view_edge_id,
                    outgoing_edges[edge.source_view_node_id],
                    16.0,
                    source.height / 2.0 - 10.0,
                )
                target_side_offset = port_offset(
                    edge.view_edge_id,
                    incoming_edges[edge.target_view_node_id],
                    16.0,
                    target.height / 2.0 - 10.0,
                )
                start = ScenePoint(
                    x=source.x + source.width,
                    y=source.y + source.height / 2 + source_side_offset,
                )
                end = ScenePoint(
                    x=target.x + target.width,
                    y=target.y + target.height / 2 + target_side_offset,
                )
                points = [
                    start,
                    ScenePoint(x=corridor_x, y=start.y),
                    ScenePoint(x=corridor_x, y=end.y),
                    end,
                ]
            elif target.y < source.y:
                # The publication reads bottom-to-top for the encoder/decoder
                # swimlanes, so targets above the source use top/bottom ports.
                start = ScenePoint(
                    x=source.x + source.width / 2 + source_offset,
                    y=source.y,
                )
                end = ScenePoint(
                    x=target.x + target.width / 2 + target_offset,
                    y=target.y + target.height,
                )
                corridor_y = (start.y + end.y) / 2 + ((index % 5) - 2) * 5.0
                corridor_y = min(start.y, max(end.y, corridor_y))
                points = [
                    start,
                    ScenePoint(x=start.x, y=corridor_y),
                    ScenePoint(x=end.x, y=corridor_y),
                    end,
                ]
            else:
                # Auxiliary or reverse branches read top-to-bottom.
                start = ScenePoint(
                    x=source.x + source.width / 2 + source_offset,
                    y=source.y + source.height,
                )
                end = ScenePoint(
                    x=target.x + target.width / 2 + target_offset,
                    y=target.y,
                )
                corridor_y = (start.y + end.y) / 2 + ((index % 5) - 2) * 5.0
                corridor_y = max(start.y, min(end.y, corridor_y))
                points = [
                    start,
                    ScenePoint(x=start.x, y=corridor_y),
                    ScenePoint(x=end.x, y=corridor_y),
                    end,
                ]
        source_scene_id = view_to_scene[edge.source_view_node_id]
        target_scene_id = view_to_scene[edge.target_view_node_id]
        points = _avoid_opaque_nodes(
            points,
            scene_nodes,
            source_scene_id,
            target_scene_id,
            paper_width,
            paper_height,
        )
        style = edge_styles[edge.view_edge_id]
        scene_edges.append(
            SceneEdge(
                scene_edge_id=f"sceneedge:{edge.view_edge_id.removeprefix('viewedge:')}",
                view_edge_id=edge.view_edge_id,
                canonical_edge_ids=edge.canonical_edge_ids,
                source_scene_node_id=source_scene_id,
                target_scene_node_id=target_scene_id,
                points=points,
                role=edge.role,
                edge_type=edge.edge_type,
                visual_relation=edge.visual_relation,
                stroke=style.stroke,
                dash=style.dash,
                width=style.width,
                label=style.label,
                evidence_ids=edge.evidence_ids,
            )
        )
    return VisualScene(
        scene_id=f"scene:{view.view_id.removeprefix('view:')}",
        view_id=view.view_id,
        spec_id=spec.spec_id,
        layout_family=scene_layout_family or f"{view.layout_family}-vertical",
        paper_width=paper_width,
        paper_height=paper_height,
        nodes=scene_nodes,
        edges=scene_edges,
    )


def _quotient_ranks(
    node_ids: list[str], edge_pairs: set[tuple[str, str]]
) -> dict[str, int]:
    """Return stable ranks for a small graph of top-level layout units."""
    order = {node_id: index for index, node_id in enumerate(node_ids)}
    successors: dict[str, set[str]] = defaultdict(set)
    predecessors: dict[str, set[str]] = defaultdict(set)
    for source, target in edge_pairs:
        if source == target or source not in order or target not in order:
            continue
        successors[source].add(target)
        predecessors[target].add(source)
    indegree = {node_id: len(predecessors[node_id]) for node_id in node_ids}
    queue = deque(
        sorted(
            (node_id for node_id in node_ids if indegree[node_id] == 0),
            key=order.get,
        )
    )
    ranks = {node_id: 0 for node_id in queue}
    while queue:
        source = queue.popleft()
        for target in sorted(successors[source], key=order.get):
            ranks[target] = max(ranks.get(target, 0), ranks[source] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    # Cyclic components remain readable as a shared layer instead of relying
    # on an unstable cycle-breaking traversal.
    for node_id in node_ids:
        if node_id not in ranks:
            ranked_predecessors = [
                ranks[item] for item in predecessors[node_id] if item in ranks
            ]
            ranks[node_id] = max(ranked_predecessors, default=-1) + 1
    return ranks


def _resolve_box_collisions(
    centers: dict[str, list[float]],
    sizes: dict[str, tuple[float, float]],
    node_ids: list[str],
    *,
    gap: float,
) -> None:
    """Separate boxes deterministically after force or radial placement."""
    for _ in range(96):
        changed = False
        for left_index, left_id in enumerate(node_ids):
            for right_id in node_ids[left_index + 1 :]:
                left_x, left_y = centers[left_id]
                right_x, right_y = centers[right_id]
                left_width, left_height = sizes[left_id]
                right_width, right_height = sizes[right_id]
                overlap_x = (left_width + right_width) / 2.0 + gap - abs(right_x - left_x)
                overlap_y = (left_height + right_height) / 2.0 + gap - abs(right_y - left_y)
                if overlap_x <= 0.0 or overlap_y <= 0.0:
                    continue
                if overlap_x <= overlap_y:
                    direction = 1.0 if right_x >= left_x else -1.0
                    if right_x == left_x:
                        direction = 1.0
                    shift = overlap_x / 2.0 + 0.5
                    centers[left_id][0] -= direction * shift
                    centers[right_id][0] += direction * shift
                else:
                    direction = 1.0 if right_y >= left_y else -1.0
                    if right_y == left_y:
                        direction = 1.0
                    shift = overlap_y / 2.0 + 0.5
                    centers[left_id][1] -= direction * shift
                    centers[right_id][1] += direction * shift
                changed = True
        if not changed:
            break


def _compact_compound_nodes(
    nodes: list[SceneNode], *, preserve_flow: bool = False
) -> list[SceneNode]:
    """Pack each compound bottom-up and retain space for titles and routes."""
    by_id = {node.scene_node_id: node for node in nodes}

    def children(parent_id: str) -> list[SceneNode]:
        return [
            node for node in by_id.values() if node.parent_scene_node_id == parent_id
        ]

    def descendants(parent_id: str) -> list[str]:
        result: list[str] = []
        pending = [parent_id]
        while pending:
            current = pending.pop()
            child_ids = [item.scene_node_id for item in children(current)]
            result.extend(child_ids)
            pending.extend(child_ids)
        return result

    def depth(node_id: str) -> int:
        value = 0
        cursor = by_id[node_id]
        visited: set[str] = set()
        while cursor.parent_scene_node_id in by_id:
            parent_id = cursor.parent_scene_node_id
            if parent_id is None or parent_id in visited:
                break
            visited.add(parent_id)
            value += 1
            cursor = by_id[parent_id]
        return value

    def shift_subtree(node_id: str, dx: float, dy: float) -> None:
        for item_id in [node_id, *descendants(node_id)]:
            item = by_id[item_id]
            by_id[item_id] = item.model_copy(
                update={
                    "bounds": item.bounds.model_copy(
                        update={"x": item.bounds.x + dx, "y": item.bounds.y + dy}
                    )
                }
            )

    def tighten(container_id: str) -> None:
        members = children(container_id)
        if not members:
            return
        container = by_id[container_id]
        left = max(18.0, min(item.bounds.x for item in members) - 18.0)
        top = max(18.0, min(item.bounds.y for item in members) - 30.0)
        right = max(item.bounds.x + item.bounds.width for item in members) + 18.0
        bottom = max(item.bounds.y + item.bounds.height for item in members) + 18.0
        label_width = (
            max(len(line) for line in container.label_lines) * 7.2 * 1.25 + 28.0
        )
        by_id[container_id] = container.model_copy(
            update={
                "bounds": container.bounds.model_copy(
                    update={
                        "x": left,
                        "y": top,
                        "width": max(label_width, right - left),
                        "height": bottom - top,
                    }
                )
            }
        )

    containers = sorted(
        (
            node
            for node in nodes
            if node.shape == "container" and children(node.scene_node_id)
        ),
        key=lambda node: (-depth(node.scene_node_id), node.scene_node_id),
    )
    horizontal_gap = 24.0
    vertical_gap = 24.0

    def pack_members(raw_members: list[SceneNode]) -> None:
        members = list(raw_members)
        if len(members) < 2:
            return
        origin_x = min(item.bounds.x for item in members)
        origin_y = min(item.bounds.y for item in members)
        current_width = (
            max(item.bounds.x + item.bounds.width for item in members) - origin_x
        )
        current_height = (
            max(item.bounds.y + item.bounds.height for item in members) - origin_y
        )
        placements: list[tuple[str, float, float]] = []

        def place_layers(
            layers: list[
                tuple[float, float, list[tuple[str, float, float]]]
            ],
        ) -> list[tuple[str, float, float]]:
            if preserve_flow:
                result: list[tuple[str, float, float]] = []
                if current_height >= current_width:
                    y = 0.0
                    for _, layer_height, layer_members in layers:
                        result.extend(
                            (member_id, member_x, y + member_y)
                            for member_id, member_x, member_y in layer_members
                        )
                        y += layer_height + vertical_gap
                else:
                    x = 0.0
                    for layer_width, _, layer_members in layers:
                        result.extend(
                            (member_id, x + member_x, member_y)
                            for member_id, member_x, member_y in layer_members
                        )
                        x += layer_width + horizontal_gap
                return result
            preferred = min(2.0, max(0.75, current_width / current_height))
            layer_area = sum(width * height for width, height, _ in layers)
            base_width = math.sqrt(layer_area * preferred)
            target_widths = {
                max(width for width, _, _ in layers),
                *(base_width * scale for scale in (0.8, 1.0, 1.25, 1.5)),
            }
            arrangements = []
            for target_width in sorted(target_widths):
                x = 0.0
                y = 0.0
                row_height = 0.0
                width = 0.0
                result: list[tuple[str, float, float]] = []
                for layer_width, layer_height, layer_members in layers:
                    if x and x + layer_width > target_width + 1e-6:
                        x = 0.0
                        y += row_height + vertical_gap
                        row_height = 0.0
                    result.extend(
                        (member_id, x + member_x, y + member_y)
                        for member_id, member_x, member_y in layer_members
                    )
                    width = max(width, x + layer_width)
                    row_height = max(row_height, layer_height)
                    x += layer_width + horizontal_gap
                height = y + row_height
                aspect_penalty = abs(
                    math.log(max(width / max(height, 1.0), 1e-6) / preferred)
                )
                score = width * height * (1.0 + aspect_penalty * 0.35)
                arrangements.append((score, width * height, width, result))
            return min(arrangements, key=lambda item: item[:3])[3]

        if current_height >= current_width:
            rows: list[list[SceneNode]] = []
            row_bottoms: list[float] = []
            for member in sorted(
                members,
                key=lambda item: (item.bounds.y, item.bounds.x, item.scene_node_id),
            ):
                if not rows or member.bounds.y >= row_bottoms[-1]:
                    rows.append([member])
                    row_bottoms.append(member.bounds.y + member.bounds.height)
                else:
                    rows[-1].append(member)
                    row_bottoms[-1] = max(
                        row_bottoms[-1], member.bounds.y + member.bounds.height
                    )
            layers = []
            for row in rows:
                x = 0.0
                row_height = max(item.bounds.height for item in row)
                layer_members = []
                for member in sorted(
                    row,
                    key=lambda item: (item.bounds.x, item.bounds.y, item.scene_node_id),
                ):
                    layer_members.append((member.scene_node_id, x, 0.0))
                    x += member.bounds.width + horizontal_gap
                layers.append((x - horizontal_gap, row_height, layer_members))
            placements = place_layers(layers)
        else:
            columns: list[list[SceneNode]] = []
            column_rights: list[float] = []
            for member in sorted(
                members,
                key=lambda item: (item.bounds.x, item.bounds.y, item.scene_node_id),
            ):
                if not columns or member.bounds.x >= column_rights[-1]:
                    columns.append([member])
                    column_rights.append(member.bounds.x + member.bounds.width)
                else:
                    columns[-1].append(member)
                    column_rights[-1] = max(
                        column_rights[-1], member.bounds.x + member.bounds.width
                    )
            layers = []
            for column in columns:
                y = 0.0
                column_width = max(item.bounds.width for item in column)
                layer_members = []
                for member in sorted(
                    column,
                    key=lambda item: (item.bounds.y, item.bounds.x, item.scene_node_id),
                ):
                    layer_members.append((member.scene_node_id, 0.0, y))
                    y += member.bounds.height + vertical_gap
                layers.append((column_width, y - vertical_gap, layer_members))
            placements = place_layers(layers)
        for child_id, x, y in placements:
            child = by_id[child_id]
            shift_subtree(
                child_id,
                origin_x + x - child.bounds.x,
                origin_y + y - child.bounds.y,
            )

    for container in containers:
        tighten(container.scene_node_id)
        pack_members(children(container.scene_node_id))
        tighten(container.scene_node_id)

    # The visual root is added after this pass, so its direct children appear
    # as a sibling group whose parent is not present yet. Pack that group too
    # instead of repeatedly pushing colliding top-level compounds outward.
    if containers:
        external_groups: dict[str | None, list[SceneNode]] = defaultdict(list)
        for node in by_id.values():
            if node.parent_scene_node_id not in by_id:
                external_groups[node.parent_scene_node_id].append(node)
        for members in external_groups.values():
            pack_members(members)

    return [by_id[node.scene_node_id] for node in nodes]


def _unit_centers(
    mode: str,
    unit_ids: list[str],
    sizes: dict[str, tuple[float, float]],
    edge_pairs: set[tuple[str, str]],
) -> dict[str, list[float]]:
    """Place compound layout units without changing their internal geometry."""
    ranks = _quotient_ranks(unit_ids, edge_pairs)
    rank_members: dict[int, list[str]] = defaultdict(list)
    for node_id in unit_ids:
        rank_members[ranks[node_id]].append(node_id)
    for members in rank_members.values():
        members.sort(key=unit_ids.index)

    if mode == "orthogonal":
        centers: dict[str, list[float]] = {}
        rank_heights = {
            rank: max(sizes[node_id][1] for node_id in members)
            for rank, members in rank_members.items()
        }
        cursor_y = 0.0
        for rank in sorted(rank_members):
            members = rank_members[rank]
            cursor_x = 0.0
            for node_id in members:
                width, _height = sizes[node_id]
                centers[node_id] = [
                    cursor_x + width / 2.0,
                    cursor_y + rank_heights[rank] / 2.0,
                ]
                cursor_x += width + 132.0
            cursor_y += rank_heights[rank] + 156.0
        return centers

    if mode == "radial":
        centers = {}
        previous_radius = 0.0
        previous_extent = 0.0
        for rank in sorted(rank_members):
            members = rank_members[rank]
            extent = max(math.hypot(*sizes[node_id]) / 2.0 for node_id in members)
            if rank == 0 and len(members) == 1:
                radius = 0.0
            else:
                angular_clearance = max(
                    max(sizes[node_id]) + 150.0 for node_id in members
                )
                if len(members) == 1:
                    circumference_radius = angular_clearance
                else:
                    circumference_radius = angular_clearance / (
                        2.0 * math.sin(math.pi / len(members))
                    )
                radius = max(
                    circumference_radius,
                    previous_radius + previous_extent + extent + 170.0,
                )
            for index, node_id in enumerate(members):
                angle = -math.pi / 2.0 + (2.0 * math.pi * index / len(members))
                if rank % 2:
                    angle += math.pi / max(2, len(members))
                centers[node_id] = [
                    math.cos(angle) * radius,
                    math.sin(angle) * radius,
                ]
            previous_radius = radius
            previous_extent = extent
        _resolve_box_collisions(centers, sizes, unit_ids, gap=96.0)
        return centers

    # Deterministic Fruchterman-Reingold-style placement.  A stable circular
    # seed avoids output drift while edge attraction and rectangle-aware
    # repulsion reveal clusters in non-layered graphs.
    count = len(unit_ids)
    largest = max((max(sizes[node_id]) for node_id in unit_ids), default=240.0)
    radius = max(260.0, (largest + 170.0) * count / (2.0 * math.pi))
    centers = {
        node_id: [
            math.cos(-math.pi / 2.0 + 2.0 * math.pi * index / max(1, count)) * radius,
            math.sin(-math.pi / 2.0 + 2.0 * math.pi * index / max(1, count)) * radius,
        ]
        for index, node_id in enumerate(unit_ids)
    }
    neighbors = {node_id: set() for node_id in unit_ids}
    for source, target in edge_pairs:
        if source in neighbors and target in neighbors and source != target:
            neighbors[source].add(target)
            neighbors[target].add(source)
    for iteration in range(180):
        displacement = {node_id: [0.0, 0.0] for node_id in unit_ids}
        for left_index, left_id in enumerate(unit_ids):
            for right_id in unit_ids[left_index + 1 :]:
                dx = centers[left_id][0] - centers[right_id][0]
                dy = centers[left_id][1] - centers[right_id][1]
                if dx == 0.0 and dy == 0.0:
                    dx = 1.0 if left_index % 2 == 0 else -1.0
                distance = max(1.0, math.hypot(dx, dy))
                desired = (
                    math.hypot(*sizes[left_id]) + math.hypot(*sizes[right_id])
                ) / 2.0 + 120.0
                strength = max(0.0, desired - distance) * 0.42 + desired * desired / distance * 0.035
                force_x = dx / distance * strength
                force_y = dy / distance * strength
                displacement[left_id][0] += force_x
                displacement[left_id][1] += force_y
                displacement[right_id][0] -= force_x
                displacement[right_id][1] -= force_y
        for source in unit_ids:
            for target in sorted(neighbors[source]):
                if unit_ids.index(source) >= unit_ids.index(target):
                    continue
                dx = centers[target][0] - centers[source][0]
                dy = centers[target][1] - centers[source][1]
                distance = max(1.0, math.hypot(dx, dy))
                desired = (
                    math.hypot(*sizes[source]) + math.hypot(*sizes[target])
                ) / 2.0 + 150.0
                strength = (distance - desired) * 0.085
                force_x = dx / distance * strength
                force_y = dy / distance * strength
                displacement[source][0] += force_x
                displacement[source][1] += force_y
                displacement[target][0] -= force_x
                displacement[target][1] -= force_y
        temperature = max(6.0, largest * 0.22 * (1.0 - iteration / 180.0))
        for node_id in unit_ids:
            displacement[node_id][0] -= centers[node_id][0] * 0.012
            displacement[node_id][1] -= centers[node_id][1] * 0.012
            distance = math.hypot(*displacement[node_id])
            if distance > temperature:
                displacement[node_id][0] *= temperature / distance
                displacement[node_id][1] *= temperature / distance
            centers[node_id][0] += displacement[node_id][0]
            centers[node_id][1] += displacement[node_id][1]
    _resolve_box_collisions(centers, sizes, unit_ids, gap=112.0)
    return centers


def _route_between_rects(
    source: SceneRect,
    target: SceneRect,
    index: int,
    source_offset: float,
    target_offset: float,
) -> list[ScenePoint]:
    source_center = (source.x + source.width / 2.0, source.y + source.height / 2.0)
    target_center = (target.x + target.width / 2.0, target.y + target.height / 2.0)
    dx = target_center[0] - source_center[0]
    dy = target_center[1] - source_center[1]
    stagger = ((index % 7) - 3) * 7.0
    horizontal_separation = (
        source.x + source.width <= target.x
        or target.x + target.width <= source.x
    )
    vertical_separation = (
        source.y + source.height <= target.y
        or target.y + target.height <= source.y
    )
    route_horizontally = horizontal_separation and (
        not vertical_separation or abs(dx) >= abs(dy)
    )
    if route_horizontally:
        if dx >= 0.0:
            gap = target.x - (source.x + source.width)
            lead_distance = min(26.0, max(4.0, gap / 3.0))
            start = ScenePoint(
                x=source.x + source.width,
                y=source_center[1] + source_offset,
            )
            end = ScenePoint(x=target.x, y=target_center[1] + target_offset)
            lead_start = ScenePoint(x=start.x + lead_distance, y=start.y)
            lead_end = ScenePoint(x=end.x - lead_distance, y=end.y)
        else:
            gap = source.x - (target.x + target.width)
            lead_distance = min(26.0, max(4.0, gap / 3.0))
            start = ScenePoint(x=source.x, y=source_center[1] + source_offset)
            end = ScenePoint(
                x=target.x + target.width,
                y=target_center[1] + target_offset,
            )
            lead_start = ScenePoint(x=start.x - lead_distance, y=start.y)
            lead_end = ScenePoint(x=end.x + lead_distance, y=end.y)
        corridor_x = (lead_start.x + lead_end.x) / 2.0 + stagger
        corridor_x = min(
            max(lead_start.x, lead_end.x),
            max(min(lead_start.x, lead_end.x), corridor_x),
        )
        return _simplify_route(
            [
                start,
                lead_start,
                ScenePoint(x=corridor_x, y=lead_start.y),
                ScenePoint(x=corridor_x, y=lead_end.y),
                lead_end,
                end,
            ]
        )
    if vertical_separation:
        if dy >= 0.0:
            gap = target.y - (source.y + source.height)
            lead_distance = min(26.0, max(4.0, gap / 3.0))
            start = ScenePoint(
                x=source_center[0] + source_offset,
                y=source.y + source.height,
            )
            end = ScenePoint(x=target_center[0] + target_offset, y=target.y)
            lead_start = ScenePoint(x=start.x, y=start.y + lead_distance)
            lead_end = ScenePoint(x=end.x, y=end.y - lead_distance)
        else:
            gap = source.y - (target.y + target.height)
            lead_distance = min(26.0, max(4.0, gap / 3.0))
            start = ScenePoint(x=source_center[0] + source_offset, y=source.y)
            end = ScenePoint(
                x=target_center[0] + target_offset,
                y=target.y + target.height,
            )
            lead_start = ScenePoint(x=start.x, y=start.y - lead_distance)
            lead_end = ScenePoint(x=end.x, y=end.y + lead_distance)
        corridor_y = (lead_start.y + lead_end.y) / 2.0 + stagger
        corridor_y = min(
            max(lead_start.y, lead_end.y),
            max(min(lead_start.y, lead_end.y), corridor_y),
        )
        return _simplify_route(
            [
                start,
                lead_start,
                ScenePoint(x=lead_start.x, y=corridor_y),
                ScenePoint(x=lead_end.x, y=corridor_y),
                lead_end,
                end,
            ]
        )

    # Endpoint rectangles should not overlap, but a legacy compound scene may
    # contain such a pair. Route around their right edge with outward ports.
    corridor_x = max(
        source.x + source.width,
        target.x + target.width,
    ) + 26.0 + abs(stagger)
    start = ScenePoint(x=source.x + source.width, y=source_center[1] + source_offset)
    end = ScenePoint(x=target.x + target.width, y=target_center[1] + target_offset)
    return _simplify_route(
        [
            start,
            ScenePoint(x=corridor_x, y=start.y),
            ScenePoint(x=corridor_x, y=end.y),
            end,
        ]
    )


def _relayout_compound_scene(scene: VisualScene, mode: str) -> VisualScene:
    """Move top-level compounds as rigid units, preserving nested layouts."""
    children: dict[str, list[str]] = defaultdict(list)
    roots: list[str] = []
    for node in scene.nodes:
        if node.parent_scene_node_id is None:
            roots.append(node.scene_node_id)
        else:
            children[node.parent_scene_node_id].append(node.scene_node_id)
    outer_root = roots[0] if len(roots) == 1 and children.get(roots[0]) else None
    unit_ids = sorted(children[outer_root]) if outer_root else sorted(roots)
    if not unit_ids:
        return scene.model_copy(update={"layout_family": mode})

    unit_by_node: dict[str, str] = {}

    def assign(node_id: str, unit_id: str) -> None:
        unit_by_node[node_id] = unit_id
        for child_id in children.get(node_id, []):
            assign(child_id, unit_id)

    for unit_id in unit_ids:
        assign(unit_id, unit_id)

    edge_pairs = {
        (unit_by_node[edge.source_scene_node_id], unit_by_node[edge.target_scene_node_id])
        for edge in scene.edges
        if edge.source_scene_node_id in unit_by_node
        and edge.target_scene_node_id in unit_by_node
        and unit_by_node[edge.source_scene_node_id]
        != unit_by_node[edge.target_scene_node_id]
    }
    unit_frames: dict[str, SceneRect] = {}
    for unit_id in unit_ids:
        member_bounds = [
            node.bounds
            for node in scene.nodes
            if unit_by_node.get(node.scene_node_id) == unit_id
        ]
        internal_points = [
            point
            for edge in scene.edges
            if unit_by_node.get(edge.source_scene_node_id) == unit_id
            and unit_by_node.get(edge.target_scene_node_id) == unit_id
            for point in edge.points
        ]
        left = min(
            [bounds.x for bounds in member_bounds]
            + [point.x for point in internal_points]
        )
        top = min(
            [bounds.y for bounds in member_bounds]
            + [point.y for point in internal_points]
        )
        right = max(
            [bounds.x + bounds.width for bounds in member_bounds]
            + [point.x for point in internal_points]
        )
        bottom = max(
            [bounds.y + bounds.height for bounds in member_bounds]
            + [point.y for point in internal_points]
        )
        unit_frames[unit_id] = SceneRect(
            x=left,
            y=top,
            width=max(1.0, right - left),
            height=max(1.0, bottom - top),
        )
    sizes = {
        unit_id: (unit_frames[unit_id].width, unit_frames[unit_id].height)
        for unit_id in unit_ids
    }
    centers = _unit_centers(mode, unit_ids, sizes, edge_pairs)
    minimum_x = min(
        centers[unit_id][0] - sizes[unit_id][0] / 2.0 for unit_id in unit_ids
    )
    minimum_y = min(
        centers[unit_id][1] - sizes[unit_id][1] / 2.0 for unit_id in unit_ids
    )
    margin_x = 104.0
    margin_y = 116.0 if outer_root else 104.0
    shifts = {
        unit_id: (
            centers[unit_id][0]
            - sizes[unit_id][0] / 2.0
            - minimum_x
            + margin_x
            - unit_frames[unit_id].x,
            centers[unit_id][1]
            - sizes[unit_id][1] / 2.0
            - minimum_y
            + margin_y
            - unit_frames[unit_id].y,
        )
        for unit_id in unit_ids
    }
    moved_nodes: list[SceneNode] = []
    for node in scene.nodes:
        unit_id = unit_by_node.get(node.scene_node_id)
        if unit_id is None:
            moved_nodes.append(node)
            continue
        dx, dy = shifts[unit_id]
        moved_nodes.append(
            node.model_copy(
                update={
                    "bounds": node.bounds.model_copy(
                        update={"x": node.bounds.x + dx, "y": node.bounds.y + dy}
                    )
                }
            )
        )
    moved_by_id = {node.scene_node_id: node for node in moved_nodes}
    if outer_root:
        right = max(
            moved_by_id[unit_id].bounds.x + moved_by_id[unit_id].bounds.width
            for unit_id in unit_ids
        )
        bottom = max(
            moved_by_id[unit_id].bounds.y + moved_by_id[unit_id].bounds.height
            for unit_id in unit_ids
        )
        root = moved_by_id[outer_root]
        resized_root = root.model_copy(
            update={
                "bounds": root.bounds.model_copy(
                    update={
                        "x": 24.0,
                        "y": 24.0,
                        "width": right + 80.0,
                        "height": bottom + 80.0,
                    }
                )
            }
        )
        moved_by_id[outer_root] = resized_root
        moved_nodes = [
            resized_root if node.scene_node_id == outer_root else node
            for node in moved_nodes
        ]

    outgoing: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in scene.edges:
        outgoing[edge.source_scene_node_id].append(edge.scene_edge_id)
        incoming[edge.target_scene_node_id].append(edge.scene_edge_id)

    def port_offset(edge_id: str, edge_ids: list[str], limit: float) -> float:
        if len(edge_ids) <= 1:
            return 0.0
        step = min(15.0, (limit * 2.0) / (len(edge_ids) - 1))
        return (edge_ids.index(edge_id) - (len(edge_ids) - 1) / 2.0) * step

    moved_edges: list[SceneEdge] = []
    for index, edge in enumerate(scene.edges):
        source_unit = unit_by_node.get(edge.source_scene_node_id)
        target_unit = unit_by_node.get(edge.target_scene_node_id)
        if source_unit is not None and source_unit == target_unit:
            dx, dy = shifts[source_unit]
            points = [
                ScenePoint(x=point.x + dx, y=point.y + dy) for point in edge.points
            ]
        else:
            source = moved_by_id[edge.source_scene_node_id].bounds
            target = moved_by_id[edge.target_scene_node_id].bounds
            source_limit = max(0.0, min(source.width, source.height) / 2.0 - 12.0)
            target_limit = max(0.0, min(target.width, target.height) / 2.0 - 12.0)
            points = _route_between_rects(
                source,
                target,
                index,
                port_offset(
                    edge.scene_edge_id,
                    outgoing[edge.source_scene_node_id],
                    source_limit,
                ),
                port_offset(
                    edge.scene_edge_id,
                    incoming[edge.target_scene_node_id],
                    target_limit,
                ),
            )
        moved_edges.append(edge.model_copy(update={"points": points}))

    maximum_x = max(
        [node.bounds.x + node.bounds.width for node in moved_nodes]
        + [point.x for edge in moved_edges for point in edge.points]
    )
    maximum_y = max(
        [node.bounds.y + node.bounds.height for node in moved_nodes]
        + [point.y for edge in moved_edges for point in edge.points]
    )
    return scene.model_copy(
        update={
            "layout_family": mode,
            "paper_width": max(720.0, maximum_x + 72.0),
            "paper_height": max(420.0, maximum_y + 72.0),
            "nodes": moved_nodes,
            "edges": moved_edges,
        }
    )


def relayout_scene(scene: VisualScene, layout_mode: str) -> VisualScene:
    """Relayout an existing scene while preserving its labels, sizes, and hierarchy."""
    if layout_mode not in {"force-directed", "radial", "orthogonal"}:
        raise ValueError("scene relayout requires a compound layout mode")
    return _relayout_compound_scene(scene, layout_mode)


def build_scene(
    view: PublicationView, spec: VisualSpec, layout_mode: str = "auto"
) -> VisualScene:
    if spec.view_id != view.view_id:
        raise ValueError("VisualSpec does not belong to the PublicationView")
    if layout_mode not in LAYOUT_MODES:
        raise ValueError(f"unknown layout mode: {layout_mode}")
    if layout_mode in {"force-directed", "radial", "orthogonal"}:
        baseline = build_scene(view, spec, "hierarchical")
        return _relayout_compound_scene(baseline, layout_mode)
    if layout_mode == "dual-swimlane":
        return _build_vertical_dual_lane_scene(
            view,
            spec,
            scene_layout_family="dual-swimlane-vertical",
        )
    if layout_mode == "auto" and view.layout_family == "dual-lane":
        return _build_vertical_dual_lane_scene(view, spec)
    root = next(
        (
            node
            for node in view.nodes
            if node.parent_view_node_id is None and node.kind is NodeKind.MODULE_CONTAINER
        ),
        None,
    )
    by_view = {node.view_node_id: node for node in view.nodes}
    visible_children: dict[str, list[PublicationNode]] = defaultdict(list)
    for node in view.nodes:
        if node.parent_view_node_id is not None:
            visible_children[node.parent_view_node_id].append(node)
    container_ids = {
        parent_id for parent_id, members in visible_children.items() if members
    }
    placed = [
        node
        for node in view.nodes
        if node is not root and node.view_node_id not in container_ids
    ]
    if not placed:
        placed = list(view.nodes)
        root = None
    column_gap = (
        72.0
        if layout_mode == "single-lane"
        else 240.0 if view.visible_depth > 1 else 112.0
    )
    rankable_ids = [
        node.view_node_id
        for node in view.nodes
        if node is not root and node.canonical_node_ids
    ]
    ranks = _ranks(view, rankable_ids)
    if layout_mode == "single-lane":
        original_order = {
            node.view_node_id: index for index, node in enumerate(placed)
        }
        ordered_ids = sorted(
            ranks,
            key=lambda node_id: (ranks[node_id], original_order[node_id]),
        )
        ranks = {node_id: rank for rank, node_id in enumerate(ordered_ids)}
    elif layout_mode == "branch-tree":
        depth_values = {
            node.view_node_id: int(node.attributes.get("depth", 0))
            for node in placed
            if node.view_node_id in ranks
        }
        minimum_depth = min(depth_values.values(), default=0)
        ranks = {
            node_id: depth - minimum_depth
            for node_id, depth in depth_values.items()
        }

    def containment_track(node: PublicationNode) -> tuple[str, str]:
        nearest_container = (
            node.parent_view_node_id
            if node.parent_view_node_id in container_ids
            else "__direct__"
        )
        cursor = node
        while cursor.parent_view_node_id not in {None, "viewnode:model"}:
            cursor = by_view[cursor.parent_view_node_id]
        if cursor.view_node_id not in container_ids:
            return "__ungrouped__", "__direct__"
        return cursor.view_node_id, nearest_container

    track_rank_members: dict[tuple[str, str, int], list[PublicationNode]] = defaultdict(list)
    for index, node in enumerate(placed):
        rank = ranks.get(node.view_node_id, index)
        group, track = containment_track(node)
        track_rank_members[(group, track, rank)].append(node)
    for members in track_rank_members.values():
        members.sort(
            key=lambda node: (
                _lane(
                    node,
                    (
                        "single-lane"
                        if layout_mode == "single-lane"
                        else "generic-dag"
                        if layout_mode in {"hierarchical", "branch-tree"}
                        else view.layout_family
                    ),
                    placed.index(node),
                ),
                node.view_node_id,
            )
        )

    groups = sorted(
        {group for group, _, _ in track_rank_members},
        key=lambda group: (
            min(rank for candidate, _, rank in track_rank_members if candidate == group),
            group,
        ),
    )

    def track_path(track: str) -> tuple[str, ...]:
        if track not in by_view:
            return (track,)
        path: list[str] = []
        cursor = by_view[track]
        while cursor.parent_view_node_id is not None:
            path.append(cursor.view_node_id)
            parent = by_view.get(cursor.parent_view_node_id)
            if parent is None:
                break
            cursor = parent
        return tuple(reversed(path))

    tracks_by_group = {
        group: sorted(
            {track for candidate, track, _ in track_rank_members if candidate == group},
            key=lambda track: (track_path(track), track),
        )
        for group in groups
    }
    track_rows = {
        (group, track): max(
            len(members)
            for (candidate, candidate_track, _), members in track_rank_members.items()
            if candidate == group and candidate_track == track
        )
        for group in groups
        for track in tracks_by_group[group]
    }

    long_edges = [
        edge
        for edge in view.edges
        if edge.source_view_node_id in ranks
        and edge.target_view_node_id in ranks
        and ranks[edge.target_view_node_id] - ranks[edge.source_view_node_id] != 1
    ]
    residual_edges = [
        edge for edge in view.edges if edge.visual_relation is VisualRelation.RESIDUAL
    ]
    top_margin = 92.0 + len(long_edges) * 18.0
    group_gap = 112.0
    track_gap = 72.0
    track_offsets: dict[tuple[str, str], float] = {}
    cursor_y = top_margin
    for group in groups:
        for track in tracks_by_group[group]:
            track_offsets[(group, track)] = cursor_y
            cursor_y += track_rows[(group, track)] * (NODE_HEIGHT + ROW_GAP) + track_gap
        cursor_y += group_gap - track_gap
    max_rank = max((ranks.get(node.view_node_id, 0) for node in placed), default=0)
    content_width = (max_rank + 1) * NODE_WIDTH + max_rank * column_gap
    content_height = max(NODE_HEIGHT, cursor_y - top_margin - group_gap)
    paper_width = max(720.0, content_width + 144.0)
    paper_height = max(
        360.0,
        top_margin + content_height + 86.0 + (44.0 + len(residual_edges) * 18.0 if residual_edges else 0.0),
    )

    styles = {style.view_node_id: style for style in spec.node_styles}
    leaf_scene_nodes: list[SceneNode] = []
    view_to_scene: dict[str, str] = {}
    root_scene_id = (
        f"scenenode:{root.view_node_id.removeprefix('viewnode:')}" if root is not None else None
    )
    for (group, track, rank), members in sorted(
        track_rank_members.items(), key=lambda item: (item[0][2], item[0][0], item[0][1])
    ):
        for row, node in enumerate(members):
            style = styles[node.view_node_id]
            scene_id = f"scenenode:{node.view_node_id.removeprefix('viewnode:')}"
            view_to_scene[node.view_node_id] = scene_id
            parent_scene_id = (
                f"scenenode:{node.parent_view_node_id.removeprefix('viewnode:')}"
                if node.parent_view_node_id
                else None
            )
            leaf_scene_nodes.append(
                SceneNode(
                    scene_node_id=scene_id,
                    view_node_id=node.view_node_id,
                    canonical_node_ids=node.canonical_node_ids,
                    bounds=SceneRect(
                        x=96.0 + rank * (NODE_WIDTH + column_gap),
                        y=track_offsets[(group, track)] + row * (NODE_HEIGHT + ROW_GAP),
                        width=NODE_WIDTH,
                        height=NODE_HEIGHT,
                    ),
                    shape=_scene_shape(style.glyph),
                    label_lines=_wrap_label(style.label),
                    secondary_label=style.secondary_label,
                    fill=style.fill,
                    stroke=style.stroke,
                    parent_scene_node_id=parent_scene_id,
                    evidence_ids=node.evidence_ids,
                )
            )

    scene_by_view = {node.view_node_id: node for node in leaf_scene_nodes}
    container_scene_nodes: list[SceneNode] = []
    containers = sorted(
        (
            node
            for node in view.nodes
            if node is not root and node.view_node_id in container_ids
        ),
        key=lambda node: int(node.attributes.get("depth", 0)),
        reverse=True,
    )
    for node in containers:
        members = [
            scene_by_view[child.view_node_id]
            for child in visible_children[node.view_node_id]
            if child.view_node_id in scene_by_view
        ]
        if not members:
            continue
        left = min(member.bounds.x for member in members) - 30.0
        top = min(member.bounds.y for member in members) - 44.0
        right = max(member.bounds.x + member.bounds.width for member in members) + 30.0
        bottom = max(member.bounds.y + member.bounds.height for member in members) + 24.0
        style = styles[node.view_node_id]
        scene_id = f"scenenode:{node.view_node_id.removeprefix('viewnode:')}"
        parent_scene_id = (
            f"scenenode:{node.parent_view_node_id.removeprefix('viewnode:')}"
            if node.parent_view_node_id
            else None
        )
        scene_node = SceneNode(
            scene_node_id=scene_id,
            view_node_id=node.view_node_id,
            canonical_node_ids=node.canonical_node_ids,
            bounds=SceneRect(
                x=max(30.0, left),
                y=max(30.0, top),
                width=right - max(30.0, left),
                height=bottom - max(30.0, top),
            ),
            shape="container",
            label_lines=_wrap_label(style.label),
            secondary_label=style.secondary_label,
            fill=style.fill,
            stroke=style.stroke,
            parent_scene_node_id=parent_scene_id,
            evidence_ids=node.evidence_ids,
        )
        scene_by_view[node.view_node_id] = scene_node
        view_to_scene[node.view_node_id] = scene_id
        container_scene_nodes.append(scene_node)

    paper_width = max(
        paper_width,
        max(
            (node.bounds.x + node.bounds.width + 72.0 for node in scene_by_view.values()),
            default=paper_width,
        ),
    )
    paper_height = max(
        paper_height,
        max(
            (node.bounds.y + node.bounds.height + 72.0 for node in scene_by_view.values()),
            default=paper_height,
        ),
    )
    scene_nodes = [
        *sorted(
            container_scene_nodes,
            key=lambda node: int(by_view[node.view_node_id].attributes.get("depth", 0)),
        ),
        *leaf_scene_nodes,
    ]
    scene_nodes = _compact_compound_nodes(scene_nodes)
    paper_width = max(
        720.0,
        max(node.bounds.x + node.bounds.width for node in scene_nodes) + 72.0,
    )
    paper_height = max(
        420.0,
        max(node.bounds.y + node.bounds.height for node in scene_nodes) + 72.0,
    )
    if root is not None:
        style = styles[root.view_node_id]
        view_to_scene[root.view_node_id] = root_scene_id or "scenenode:model"
        scene_nodes.insert(
            0,
            SceneNode(
                scene_node_id=root_scene_id or "scenenode:model",
                view_node_id=root.view_node_id,
                canonical_node_ids=root.canonical_node_ids,
                bounds=SceneRect(x=24.0, y=24.0, width=paper_width - 48.0, height=paper_height - 48.0),
                shape="container",
                label_lines=_wrap_label(style.label),
                secondary_label=style.secondary_label,
                fill=style.fill,
                stroke=style.stroke,
                evidence_ids=root.evidence_ids,
            ),
        )

    by_scene_view = {node.view_node_id: node for node in scene_nodes}
    edge_styles = {style.view_edge_id: style for style in spec.edge_styles}
    outgoing_edges: dict[str, list[str]] = defaultdict(list)
    incoming_edges: dict[str, list[str]] = defaultdict(list)
    for edge in view.edges:
        outgoing_edges[edge.source_view_node_id].append(edge.view_edge_id)
        incoming_edges[edge.target_view_node_id].append(edge.view_edge_id)

    def port_offset(edge_id: str, edge_ids: list[str], limit: float) -> float:
        if len(edge_ids) <= 1:
            return 0.0
        step = min(15.0, (limit * 2.0) / (len(edge_ids) - 1))
        return (edge_ids.index(edge_id) - (len(edge_ids) - 1) / 2.0) * step

    scene_edges: list[SceneEdge] = []
    for index, edge in enumerate(view.edges):
        if edge.source_view_node_id not in by_scene_view or edge.target_view_node_id not in by_scene_view:
            continue
        source = by_scene_view[edge.source_view_node_id].bounds
        target = by_scene_view[edge.target_view_node_id].bounds
        source_limit = max(0.0, min(source.width, source.height) / 2.0 - 12.0)
        target_limit = max(0.0, min(target.width, target.height) / 2.0 - 12.0)
        points = _route_between_rects(
            source,
            target,
            index,
            port_offset(
                edge.view_edge_id,
                outgoing_edges[edge.source_view_node_id],
                source_limit,
            ),
            port_offset(
                edge.view_edge_id,
                incoming_edges[edge.target_view_node_id],
                target_limit,
            ),
        )
        points = _avoid_opaque_nodes(
            points,
            scene_nodes,
            view_to_scene[edge.source_view_node_id],
            view_to_scene[edge.target_view_node_id],
            paper_width,
            paper_height,
        )
        style = edge_styles[edge.view_edge_id]
        scene_edges.append(
            SceneEdge(
                scene_edge_id=f"sceneedge:{edge.view_edge_id.removeprefix('viewedge:')}",
                view_edge_id=edge.view_edge_id,
                canonical_edge_ids=edge.canonical_edge_ids,
                source_scene_node_id=view_to_scene[edge.source_view_node_id],
                target_scene_node_id=view_to_scene[edge.target_view_node_id],
                points=points,
                role=edge.role,
                edge_type=edge.edge_type,
                visual_relation=edge.visual_relation,
                stroke=style.stroke,
                dash=style.dash,
                width=style.width,
                label=style.label,
                evidence_ids=edge.evidence_ids,
            )
        )
    return VisualScene(
        scene_id=f"scene:{view.view_id.removeprefix('view:')}",
        view_id=view.view_id,
        spec_id=spec.spec_id,
        layout_family=(
            view.layout_family if layout_mode == "auto" else layout_mode
        ),
        paper_width=paper_width,
        paper_height=paper_height,
        nodes=scene_nodes,
        edges=scene_edges,
    )
