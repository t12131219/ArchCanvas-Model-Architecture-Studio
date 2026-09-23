"""Stable, dependency-free SVG renderer for a publication scene."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from archcanvas_core.models.publication import (
    PublicationEdgeKind,
    PublicationIR,
    PublicationMiniature,
    PublicationMiniatureKind,
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
    parts: list[str] = [
        '<g data-non-executable-duplicate="true"><title>Illustrative repetition; not additional computation nodes</title>'
    ]
    for index, preview_y in enumerate((y + 38, y + 66), start=1):
        parts.append(
            f'<rect data-repeat-preview="{index}" x="{preview_x}" y="{preview_y}" width="{preview_width}" height="20" rx="3" fill="#ffffff" stroke="{stroke}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x + width // 2}" y="{preview_y + 14}" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#0f172a">Repeated unit</text>'
        )
    parts.append(
        f'<text x="{x + width // 2}" y="{y + 110}" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#475569">...</text>'
    )
    parts.append("</g>")
    return parts


def _miniature_preview(
    miniature: PublicationMiniature,
    *,
    x: int,
    y: int,
    width: int,
    height: int,
) -> list[str]:
    """Render a disclosed visual grammar without creating an architecture fact."""

    preview_x = x + 12
    preview_y = y + height - 20
    preview_width = max(26, width - 24)
    disclosure = miniature.disclosure.value
    attrs = (
        f'data-miniature-id="{miniature.miniature_id}" '
        f'data-miniature-kind="{miniature.kind.value}" '
        f'data-disclosure="{disclosure}"'
    )
    title = f"<title>{escape(miniature.label)} [{disclosure}]</title>"
    if miniature.kind is PublicationMiniatureKind.TENSOR_STRIP:
        cells = "".join(
            f'<rect x="{preview_x + index * 12}" y="{preview_y}" width="9" height="12" fill="#dbeafe" stroke="#1d4ed8" stroke-width="1"/>'
            for index in range(min(8, max(2, preview_width // 12)))
        )
        body = cells
    elif miniature.kind is PublicationMiniatureKind.SIGNAL_PREVIEW:
        body = (
            f'<path d="M {preview_x} {preview_y + 8} C {preview_x + 8} {preview_y - 2}, '
            f'{preview_x + 16} {preview_y + 18}, {preview_x + 24} {preview_y + 8} S '
            f'{preview_x + 40} {preview_y - 2}, {preview_x + 52} {preview_y + 8} S '
            f'{preview_x + 68} {preview_y + 18}, {preview_x + preview_width} {preview_y + 7}" '
            'fill="none" stroke="#0f766e" stroke-width="1.5"/>'
        )
    elif miniature.kind is PublicationMiniatureKind.DISTRIBUTION_PREVIEW:
        body = (
            f'<path d="M {preview_x} {preview_y + 13} C {preview_x + preview_width // 4} {preview_y + 13}, '
            f'{preview_x + preview_width // 3} {preview_y}, {preview_x + preview_width // 2} {preview_y} S '
            f'{preview_x + preview_width * 3 // 4} {preview_y + 13}, {preview_x + preview_width} {preview_y + 13}" '
            'fill="none" stroke="#b45309" stroke-width="1.5"/>'
        )
    elif miniature.kind is PublicationMiniatureKind.EQUATION_NOTE:
        body = (
            f'<text x="{x + width - 18}" y="{y + 18}" text-anchor="end" font-family="serif" '
            'font-size="12" fill="#475569">N x</text>'
        )
    else:
        body = (
            f'<rect x="{preview_x}" y="{preview_y - 2}" width="{preview_width}" height="15" rx="2" '
            'fill="none" stroke="#475569" stroke-width="1" stroke-dasharray="3 2"/>'
        )
    marker = "schematic" if disclosure == "illustrative" else "evidence"
    return [
        f"<g {attrs}>{title}{body}</g>",
        f'<text x="{preview_x}" y="{preview_y + 25}" font-family="sans-serif" font-size="7" fill="#475569">{marker}</text>',
    ]


def render_svg(publication: PublicationIR, scene: VisualScene) -> str:
    publication_nodes = {node.node_id: node for node in publication.nodes}
    publication_edges = {edge.edge_id: edge for edge in publication.edges}
    scene_nodes = {node.publication_node_id: node for node in scene.nodes}
    miniatures_by_target: dict[str, list[PublicationMiniature]] = {}
    for miniature in publication.miniatures:
        miniatures_by_target.setdefault(miniature.target_node_id, []).append(miniature)
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
        for miniature in miniatures_by_target.get(publication_node.node_id, []):
            parts.extend(
                _miniature_preview(
                    miniature,
                    x=x,
                    y=y,
                    width=scene_node.width,
                    height=scene_node.height,
                )
            )
    for annotation in publication.annotations:
        node = scene_nodes[annotation.target_node_id]
        parts.append(
            f'<text x="{node.x + node.width // 2}" y="{node.y - 8}" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#475569">{escape(annotation.text)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"
