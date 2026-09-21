"""Stable, dependency-free SVG renderer for a publication scene."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from archcanvas_core.models.publication import (
    PublicationEdgeKind,
    PublicationIR,
    ScenePoint,
    VisualScene,
)

_COLORS = {
    "input": ("#dbeafe", "#1d4ed8"),
    "module": ("#ecfeff", "#0f766e"),
    "repeat_group": ("#fef3c7", "#b45309"),
    "residual_block": ("#ffe4e6", "#be123c"),
    "output": ("#dcfce7", "#15803d"),
}


def _path(points: Sequence[ScenePoint]) -> str:
    coordinates = list(points)
    start, *rest = coordinates
    return "M " + " L ".join([f"{start.x} {start.y}", *(f"{point.x} {point.y}" for point in rest)])


def _expanded_repeat_preview(x: int, y: int, width: int, stroke: str) -> list[str]:
    """Render a visual-only repeat preview inside an already mapped publication group."""

    preview_x = x + 16
    preview_width = width - 32
    parts: list[str] = []
    for index, preview_y in enumerate((y + 38, y + 66), start=1):
        parts.append(
            f'<rect data-repeat-preview="{index}" x="{preview_x}" y="{preview_y}" width="{preview_width}" height="20" rx="3" fill="#ffffff" stroke="{stroke}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x + width // 2}" y="{preview_y + 14}" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#0f172a">Encoder layer</text>'
        )
    parts.append(
        f'<text x="{x + width // 2}" y="{y + 110}" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#475569">...</text>'
    )
    return parts


def render_svg(publication: PublicationIR, scene: VisualScene) -> str:
    publication_nodes = {node.node_id: node for node in publication.nodes}
    publication_edges = {edge.edge_id: edge for edge in publication.edges}
    scene_nodes = {node.publication_node_id: node for node in scene.nodes}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{scene.width}" height="{scene.height}" viewBox="0 0 {scene.width} {scene.height}">',
        "<defs><marker id=\"arrow\" markerWidth=\"8\" markerHeight=\"8\" refX=\"7\" refY=\"4\" orient=\"auto\"><path d=\"M 0 0 L 8 4 L 0 8 z\" fill=\"#334155\"/></marker></defs>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for edge in scene.edges:
        publication_edge = publication_edges[edge.publication_edge_id]
        color = "#be123c" if publication_edge.kind is PublicationEdgeKind.RESIDUAL else "#334155"
        dash = ' stroke-dasharray="5 4"' if publication_edge.kind is PublicationEdgeKind.RESIDUAL else ""
        parts.append(
            f'<path d="{_path(edge.points)}" fill="none" stroke="{color}" stroke-width="2"{dash} marker-end="url(#arrow)"/>'
        )
    for scene_node in scene.nodes:
        publication_node = publication_nodes[scene_node.publication_node_id]
        fill, stroke = _COLORS[publication_node.kind.value]
        x, y = scene_node.x, scene_node.y
        parts.append(
            f'<rect data-node-id="{publication_node.node_id}" data-expanded="{str(scene_node.expanded).lower()}" x="{x}" y="{y}" width="{scene_node.width}" height="{scene_node.height}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        )
        if scene_node.expanded:
            parts.append(
                f'<text x="{x + scene_node.width // 2}" y="{y + 23}" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#0f172a">{escape(publication_node.label)}</text>'
            )
            parts.extend(_expanded_repeat_preview(x, y, scene_node.width, stroke))
        else:
            parts.append(
                f'<text x="{x + scene_node.width // 2}" y="{y + scene_node.height // 2 + 5}" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#0f172a">{escape(publication_node.label)}</text>'
            )
    for annotation in publication.annotations:
        node = scene_nodes[annotation.target_node_id]
        parts.append(
            f'<text x="{node.x + node.width // 2}" y="{node.y - 8}" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#475569">{escape(annotation.text)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"
