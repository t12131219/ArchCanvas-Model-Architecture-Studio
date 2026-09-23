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
ROW_GAP = 42.0


def _node_style(node: PublicationNode, level: str) -> tuple[str, str, str]:
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
    if level == "L4":
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
        glyph, fill, stroke = _node_style(node, view.level)
        secondary: str | None = None
        if node.collapsed:
            secondary = f"{len(node.canonical_node_ids)} canonical nodes"
        elif view.level == "L4":
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
        if view.level in {"L3", "L4"} and edge.symbolic_shape != "[?]":
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
    placed = [node for node in view.nodes if node is not root]
    if not placed:
        placed = list(view.nodes)
        root = None
    column_gap = 240.0 if view.level in {"L3", "L4"} else 92.0
    node_ids = [node.view_node_id for node in placed]
    ranks = _ranks(view, node_ids)
    rank_members: dict[int, list[PublicationNode]] = defaultdict(list)
    for index, node in enumerate(placed):
        rank_members[ranks[node.view_node_id]].append(node)
    for rank, members in rank_members.items():
        members.sort(key=lambda node: (_lane(node, view.layout_family, placed.index(node)), node.view_node_id))

    long_edges = [
        edge
        for edge in view.edges
        if edge.source_view_node_id in ranks
        and edge.target_view_node_id in ranks
        and ranks[edge.target_view_node_id] - ranks[edge.source_view_node_id] != 1
    ]
    top_margin = 92.0 + len(long_edges) * 18.0
    max_rows = max((len(members) for members in rank_members.values()), default=1)
    max_rank = max(ranks.values(), default=0)
    content_width = (max_rank + 1) * NODE_WIDTH + max_rank * column_gap
    content_height = max_rows * NODE_HEIGHT + max(0, max_rows - 1) * ROW_GAP
    paper_width = max(720.0, content_width + 144.0)
    paper_height = max(360.0, top_margin + content_height + 86.0)

    styles = {style.view_node_id: style for style in spec.node_styles}
    scene_nodes: list[SceneNode] = []
    view_to_scene: dict[str, str] = {}
    root_scene_id = (
        f"scenenode:{root.view_node_id.removeprefix('viewnode:')}" if root is not None else None
    )
    for rank in sorted(rank_members):
        for row, node in enumerate(rank_members[rank]):
            style = styles[node.view_node_id]
            scene_id = f"scenenode:{node.view_node_id.removeprefix('viewnode:')}"
            view_to_scene[node.view_node_id] = scene_id
            scene_nodes.append(
                SceneNode(
                    scene_node_id=scene_id,
                    view_node_id=node.view_node_id,
                    canonical_node_ids=node.canonical_node_ids,
                    bounds=SceneRect(
                        x=72.0 + rank * (NODE_WIDTH + column_gap),
                        y=top_margin + row * (NODE_HEIGHT + ROW_GAP),
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
                    parent_scene_node_id=root_scene_id,
                    evidence_ids=node.evidence_ids,
                )
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

    by_view = {node.view_node_id: node for node in scene_nodes}
    edge_styles = {style.view_edge_id: style for style in spec.edge_styles}
    corridor_index = {edge.view_edge_id: index for index, edge in enumerate(long_edges)}
    scene_edges: list[SceneEdge] = []
    for index, edge in enumerate(view.edges):
        if edge.source_view_node_id not in by_view or edge.target_view_node_id not in by_view:
            continue
        source = by_view[edge.source_view_node_id].bounds
        target = by_view[edge.target_view_node_id].bounds
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
