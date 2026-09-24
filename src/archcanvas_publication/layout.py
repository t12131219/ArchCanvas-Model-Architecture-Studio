from __future__ import annotations

import re
import textwrap
from collections import defaultdict, deque

from archcanvas_core.models import (
    EdgeType,
    NodeKind,
    PublicationNode,
    PublicationView,
    SceneEdge,
    SceneNode,
    ScenePoint,
    SceneRect,
    VisualEdgeStyle,
    VisualNodeStyle,
    VisualScene,
    VisualSpec,
)

NODE_WIDTH = 210.0
NODE_HEIGHT = 106.0
ROW_GAP = 76.0


def _node_style(node: PublicationNode, fully_expanded: bool) -> tuple[str, str, str]:
    source_kind = str(node.attributes.get("source_kind", node.kind.value))
    lowered = f"{node.semantic_name} {source_kind}".lower()
    if node.parent_view_node_id is None and node.kind is NodeKind.MODULE_CONTAINER:
        return "container", "#f7f9fc", "#52606d"
    if node.kind is NodeKind.OPAQUE_COMPOSITE or "opaque" in lowered:
        return "opaque", "#f1f3f5", "#59636e"
    if node.kind is NodeKind.MERGE_EVENT:
        return "merge", "#fff3bf", "#8d6b00"
    if node.kind is NodeKind.TENSOR_VALUE:
        return "tensor", "#e7f5ff", "#1971c2"
    if node.kind is NodeKind.STATE:
        return "state", "#e6fcf5", "#087f5b"
    if node.kind is NodeKind.INPUT_OUTPUT or node.attributes.get("io"):
        return "io", "#f3f0ff", "#7048a8"
    if node.kind is NodeKind.MODULE_CONTAINER or node.collapsed:
        return "container", "#edf6ff", "#3b6f98"
    if any(word in lowered for word in ("decomp", "head", "forecast", "output")):
        return "operator", "#ebfbee", "#2b8a3e"
    if any(word in lowered for word in ("norm", "residual", "add", "merge", "concat")):
        return "operator", "#fff9db", "#9c6f00"
    if any(word in lowered for word in ("attention", "correlation", "mix", "fft")):
        return "operator", "#fff0f0", "#c92a2a"
    if any(word in lowered for word in ("embed", "projection", "linear", "conv")):
        return "operator", "#fff4e6", "#d9480f"
    if fully_expanded:
        return "operator", "#e7f5ff", "#1864ab"
    return "operator", "#eef2f7", "#4b6075"


def _edge_style(edge_type: EdgeType) -> tuple[str, str | None, float]:
    return {
        EdgeType.MAIN: ("#263238", None, 1.8),
        EdgeType.RESIDUAL: ("#c77d00", None, 1.8),
        EdgeType.SKIP: ("#2b8a3e", "7 4", 1.8),
        EdgeType.MEMORY: ("#1971c2", None, 1.9),
        EdgeType.STATE: ("#087f5b", "3 3", 1.8),
        EdgeType.CONDITION: ("#7048a8", "6 4", 1.7),
        EdgeType.ROUTING: ("#495057", "2 3", 1.6),
        EdgeType.PARAMETER_SHARE: ("#862e9c", "8 3 2 3", 1.6),
        EdgeType.TRAINING_ONLY: ("#868e96", "5 5", 1.5),
    }[edge_type]


def build_visual_spec(view: PublicationView) -> VisualSpec:
    node_styles: list[VisualNodeStyle] = []
    for node in view.nodes:
        glyph, fill, stroke = _node_style(node, view.fully_expanded)
        secondary: str | None = None
        if node.collapsed:
            secondary = f"{len(node.canonical_node_ids)} canonical nodes"
        elif not node.canonical_node_ids:
            secondary = f"{node.attributes.get('canonical_count', 0)} contained nodes"
        elif view.fully_expanded:
            secondary = node.canonical_node_ids[0]
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
        stroke, dash, width = _edge_style(edge.edge_type)
        label = edge.role
        if view.visible_depth > 1 and edge.symbolic_shape != "[?]":
            label = f"{label} {edge.symbolic_shape}"
        edge_styles.append(
            VisualEdgeStyle(
                view_edge_id=edge.view_edge_id,
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
    order = {node_id: index for index, node_id in enumerate(node_ids)}
    successors: dict[str, set[str]] = defaultdict(set)
    indegree = {node_id: 0 for node_id in node_ids}
    for edge in view.edges:
        source, target = edge.source_view_node_id, edge.target_view_node_id
        if source not in indegree or target not in indegree or source == target:
            continue
        if target not in successors[source]:
            successors[source].add(target)
            indegree[target] += 1
    queue = deque(sorted((node for node, degree in indegree.items() if degree == 0), key=order.get))
    ranks = {node_id: 0 for node_id in queue}
    visited: set[str] = set()
    while queue:
        source = queue.popleft()
        visited.add(source)
        for target in sorted(successors[source], key=order.get):
            ranks[target] = max(ranks.get(target, 0), ranks[source] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    next_rank = max(ranks.values(), default=-1) + 1
    for node_id in node_ids:
        if node_id not in visited:
            ranks[node_id] = next_rank
            next_rank += 1
    return ranks


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


def build_scene(view: PublicationView, spec: VisualSpec) -> VisualScene:
    if spec.view_id != view.view_id:
        raise ValueError("VisualSpec does not belong to the PublicationView")
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
    column_gap = 240.0 if view.visible_depth > 1 else 112.0
    rankable_ids = [
        node.view_node_id
        for node in view.nodes
        if node is not root and node.canonical_node_ids
    ]
    ranks = _ranks(view, rankable_ids)

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
                _lane(node, view.layout_family, placed.index(node)),
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
    paper_height = max(360.0, top_margin + content_height + 86.0)

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
                    shape={
                        "operator": "rect",
                        "tensor": "rect",
                        "container": "container",
                        "merge": "merge",
                        "io": "io",
                        "state": "state",
                        "opaque": "opaque",
                    }[style.glyph],
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
    corridor_index = {edge.view_edge_id: index for index, edge in enumerate(long_edges)}
    scene_edges: list[SceneEdge] = []
    for index, edge in enumerate(view.edges):
        if edge.source_view_node_id not in by_scene_view or edge.target_view_node_id not in by_scene_view:
            continue
        source = by_scene_view[edge.source_view_node_id].bounds
        target = by_scene_view[edge.target_view_node_id].bounds
        start = ScenePoint(x=source.x + source.width, y=source.y + source.height / 2)
        end = ScenePoint(x=target.x, y=target.y + target.height / 2)
        rank_delta = ranks[edge.target_view_node_id] - ranks[edge.source_view_node_id]
        if rank_delta == 1:
            offset = ((index % 5) - 2) * 5.0
            corridor_x = (start.x + end.x) / 2 + offset
            points = [
                start,
                ScenePoint(x=corridor_x, y=start.y),
                ScenePoint(x=corridor_x, y=end.y),
                end,
            ]
        else:
            corridor_y = 60.0 + corridor_index[edge.view_edge_id] * 18.0
            source_out = start.x + 24.0
            target_out = max(36.0, end.x - 24.0)
            points = [
                start,
                ScenePoint(x=source_out, y=start.y),
                ScenePoint(x=source_out, y=corridor_y),
                ScenePoint(x=target_out, y=corridor_y),
                ScenePoint(x=target_out, y=end.y),
                end,
            ]
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
                stroke=style.stroke,
                dash=style.dash,
                width=style.width,
                label=style.label,
            )
        )
    return VisualScene(
        scene_id=f"scene:{view.view_id.removeprefix('view:')}",
        view_id=view.view_id,
        spec_id=spec.spec_id,
        layout_family=view.layout_family,
        paper_width=paper_width,
        paper_height=paper_height,
        nodes=scene_nodes,
        edges=scene_edges,
    )
