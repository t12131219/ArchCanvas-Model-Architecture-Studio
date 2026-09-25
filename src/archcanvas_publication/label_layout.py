from __future__ import annotations

from dataclasses import dataclass

from archcanvas_core.models import SceneEdge, SceneRect, VisualScene


@dataclass(frozen=True)
class LabelPlacement:
    x: float
    y: float
    bounds: SceneRect


def label_required(scene: VisualScene, edge: SceneEdge) -> bool:
    if scene.layout_family.endswith("-vertical") and edge.visual_relation.value in {
        "sequence",
        "parallel-branch",
    }:
        return False
    if not scene.view_id.endswith((".l1", ".l2")):
        return True
    return edge.edge_type.value in {"memory", "state", "condition", "parameter-share"}


def _overlap(first: SceneRect, second: SceneRect) -> bool:
    return (
        first.x < second.x + second.width
        and first.x + first.width > second.x
        and first.y < second.y + second.height
        and first.y + first.height > second.y
    )


def edge_label_placements(scene: VisualScene) -> dict[str, LabelPlacement]:
    nodes = [
        node.bounds
        for node in scene.nodes
        if node.parent_scene_node_id is not None and node.shape != "container"
    ]
    used: list[SceneRect] = []
    placements: dict[str, LabelPlacement] = {}
    first_node_y = min((bounds.y for bounds in nodes), default=scene.paper_height)

    for edge in scene.edges:
        if not label_required(scene, edge):
            continue
        width = min(len(edge.label), 28) * 7.75
        height = 15.0
        start, end = edge.points[0], edge.points[-1]
        candidates: list[tuple[float, float]] = []
        segments = sorted(
            zip(edge.points, edge.points[1:]),
            key=lambda pair: abs(pair[1].x - pair[0].x) + abs(pair[1].y - pair[0].y),
            reverse=True,
        )
        for first, second in segments:
            if first.y == second.y:
                for fraction in (0.5, 0.35, 0.65):
                    candidates.append(
                        (first.x + (second.x - first.x) * fraction, first.y - 6.0)
                    )
                    candidates.append(
                        (first.x + (second.x - first.x) * fraction, first.y + 18.0)
                    )
            elif first.x == second.x:
                for fraction in (0.5, 0.35, 0.65):
                    candidates.append(
                        (first.x + width / 2 + 8.0, first.y + (second.y - first.y) * fraction)
                    )
                    candidates.append(
                        (first.x - width / 2 - 8.0, first.y + (second.y - first.y) * fraction)
                    )
        x = (start.x + end.x) / 2
        middle_y = (start.y + end.y) / 2
        if scene.layout_family.endswith("-vertical"):
            for rail_x in (
                scene.paper_width * 0.5,
                scene.paper_width * 0.44,
                scene.paper_width * 0.56,
            ):
                candidates.extend(
                    (rail_x, rail_y)
                    for rail_y in (middle_y, middle_y - 18.0, middle_y + 18.0)
                )
        candidates.extend(
            (x, y)
            for y in (
                start.y - 6.0,
                end.y - 6.0,
                start.y - 24.0,
                end.y - 24.0,
                start.y + 24.0,
                end.y + 24.0,
                start.y - 64.0,
                end.y - 64.0,
                start.y + 64.0,
                end.y + 64.0,
                start.y - 82.0,
                end.y - 82.0,
            )
        )
        top_row = 42.0
        while top_row < first_node_y - 8.0:
            candidates.append((scene.paper_width / 2, top_row))
            top_row += 18.0

        for x, y in candidates:
            bounds = SceneRect(x=max(1.0, x - width / 2), y=max(1.0, y - 12.0), width=width, height=height)
            if bounds.x + bounds.width > scene.paper_width - 1.0:
                continue
            if bounds.y + bounds.height > scene.paper_height - 1.0:
                continue
            if any(_overlap(bounds, node) for node in nodes):
                continue
            if any(_overlap(bounds, other) for other in used):
                continue
            placement = LabelPlacement(x=x, y=y, bounds=bounds)
            placements[edge.scene_edge_id] = placement
            used.append(bounds)
            break
    return placements
