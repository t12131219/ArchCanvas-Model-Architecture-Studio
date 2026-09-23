from __future__ import annotations

import hashlib
import json
import math
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from archcanvas_core.models import (
    ArchitectureIR,
    CanvasDocument,
    SceneNode,
    ScenePoint,
    SceneRect,
    SourceSnapshot,
    VisualPatch,
    VisualScene,
)
from archcanvas_core.validation import (
    apply_visual_patch,
    redo_visual_patch,
    undo_visual_patch,
)

NODE_OPERATIONS = {
    "set-position",
    "set-size",
    "set-pin",
    "set-alignment",
    "set-gap",
    "set-label-wrap",
    "set-collapse",
}
EDGE_OPERATIONS = {"set-route-hint"}
GLOBAL_OPERATIONS = {
    "set-caption",
    "set-legend-placement",
    "set-theme",
    "set-palette",
    "set-line-weight",
    "set-font-scale",
    "set-camera",
    "add-annotation",
}


def _compact(value: Any) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def source_binding_digest(snapshot: SourceSnapshot) -> str:
    binding = {
        "revision": snapshot.revision,
        "entrypoint": snapshot.entrypoint,
        "task": snapshot.task,
        "execution_mode": snapshot.execution_mode,
        "config_digest": snapshot.config_digest,
        "source_files": [
            {"path": source.path, "sha256": source.sha256}
            for source in sorted(snapshot.source_files, key=lambda item: item.path)
        ],
    }
    return hashlib.sha256(_compact(binding)).hexdigest()


def create_canvas_document(
    ir: ArchitectureIR,
    snapshot: SourceSnapshot,
    scenes: Iterable[VisualScene],
) -> CanvasDocument:
    suffix = ir.architecture_id.removeprefix("architecture:")
    return CanvasDocument(
        document_id=f"document:{suffix}",
        source_snapshot_id=snapshot.snapshot_id,
        architecture_id=ir.architecture_id,
        source_digest=source_binding_digest(snapshot),
        base_scene_ids=[scene.scene_id for scene in scenes],
        view_state={"active_level": "L1", "mode": "explore", "theme": "paper-light"},
    )


def persist_canvas_document(path: Path, document: CanvasDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        document.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def load_canvas_document(path: Path) -> CanvasDocument:
    return CanvasDocument.model_validate_json(path.read_text(encoding="utf-8"))


def _number(
    value: Any,
    name: str,
    *,
    positive: bool = False,
    allow_negative: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    if (not allow_negative and result < 0) or (positive and result <= 0):
        raise ValueError(f"{name} is outside its allowed range")
    return result


def _scene_for_patch(patch: VisualPatch, scenes: dict[str, VisualScene]) -> VisualScene | None:
    scene_id = patch.value.get("scene_id")
    if scene_id is None:
        return None
    if not isinstance(scene_id, str) or scene_id not in scenes:
        raise ValueError("visual patch references an unknown scene")
    return scenes[scene_id]


def validate_patch(
    document: CanvasDocument,
    patch: VisualPatch,
    scenes: dict[str, VisualScene],
) -> None:
    if patch.patch_id in {
        item.patch_id for item in [*document.visual_patches, *document.redo_patches]
    }:
        raise ValueError("visual patch identifier already exists")
    scene = _scene_for_patch(patch, scenes)
    if patch.operation in NODE_OPERATIONS:
        if scene is None or patch.target_id not in {node.scene_node_id for node in scene.nodes}:
            raise ValueError("node visual patch requires a valid scene and target node")
    elif patch.operation in EDGE_OPERATIONS:
        if scene is None or patch.target_id not in {edge.scene_edge_id for edge in scene.edges}:
            raise ValueError("edge visual patch requires a valid scene and target edge")
    elif patch.operation not in GLOBAL_OPERATIONS:
        raise ValueError("unsupported visual patch operation")

    if patch.operation == "set-position":
        _number(patch.value.get("x"), "x")
        _number(patch.value.get("y"), "y")
    elif patch.operation == "set-size":
        _number(patch.value.get("width"), "width", positive=True)
        _number(patch.value.get("height"), "height", positive=True)
    elif patch.operation in {"set-pin", "set-collapse"}:
        if not isinstance(patch.value.get("enabled"), bool):
            raise ValueError(f"{patch.operation} requires an enabled boolean")
    elif patch.operation == "set-label-wrap":
        lines = patch.value.get("lines")
        if (
            not isinstance(lines, list)
            or not 1 <= len(lines) <= 3
            or any(not isinstance(line, str) or not line for line in lines)
        ):
            raise ValueError("set-label-wrap requires one to three non-empty lines")
    elif patch.operation == "set-route-hint":
        points = patch.value.get("points")
        if not isinstance(points, list) or len(points) < 2:
            raise ValueError("set-route-hint requires at least two points")
        for point in points:
            if not isinstance(point, dict):
                raise TypeError("route points must be objects")
            _number(point.get("x"), "route x")
            _number(point.get("y"), "route y")
    elif patch.operation == "set-camera":
        _number(patch.value.get("x", 0), "camera x", allow_negative=True)
        _number(patch.value.get("y", 0), "camera y", allow_negative=True)
        _number(patch.value.get("zoom"), "camera zoom", positive=True)
    elif patch.operation == "set-font-scale":
        scale = _number(patch.value.get("scale"), "font scale", positive=True)
        if not 0.75 <= scale <= 1.5:
            raise ValueError("font scale must be between 0.75 and 1.5")


def apply_patch(
    document: CanvasDocument,
    patch: VisualPatch,
    scenes: dict[str, VisualScene],
) -> CanvasDocument:
    validate_patch(document, patch, scenes)
    if patch.operation == "set-camera":
        scene_id = patch.value["scene_id"]
        document = document.model_copy(
            update={
                "visual_patches": [
                    item
                    for item in document.visual_patches
                    if not (
                        item.operation == "set-camera"
                        and item.value.get("scene_id") == scene_id
                    )
                ],
                "redo_patches": [],
            }
        )
    changed = apply_visual_patch(document, patch)
    if changed.source_digest != document.source_digest:
        raise AssertionError("visual patch changed the source binding")
    return changed


def undo_patch(document: CanvasDocument) -> CanvasDocument:
    changed = undo_visual_patch(document)
    if changed.source_digest != document.source_digest:
        raise AssertionError("undo changed the source binding")
    return changed


def redo_patch(document: CanvasDocument) -> CanvasDocument:
    changed = redo_visual_patch(document)
    if changed.source_digest != document.source_digest:
        raise AssertionError("redo changed the source binding")
    return changed


def _patch_applies(patch: VisualPatch, scene: VisualScene) -> bool:
    return patch.value.get("scene_id") in {None, scene.scene_id}


def _reroute_edges(
    scene: VisualScene,
    nodes: list[SceneNode],
    route_hints: dict[str, list],
    changed_node_ids: set[str],
) -> list:
    by_id = {node.scene_node_id: node for node in nodes}
    edges = []
    for index, edge in enumerate(scene.edges):
        if edge.scene_edge_id in route_hints:
            points = [ScenePoint.model_validate(point) for point in route_hints[edge.scene_edge_id]]
            edges.append(edge.model_copy(update={"points": points}))
            continue
        if not changed_node_ids.intersection(
            {edge.source_scene_node_id, edge.target_scene_node_id}
        ):
            edges.append(edge)
            continue
        source = by_id[edge.source_scene_node_id].bounds
        target = by_id[edge.target_scene_node_id].bounds
        start = ScenePoint(x=source.x + source.width, y=source.y + source.height / 2)
        end = ScenePoint(x=target.x, y=target.y + target.height / 2)
        if len(edge.points) >= 6 or end.x <= start.x + 30:
            corridor_y = min(point.y for point in edge.points)
            points = [
                start,
                ScenePoint(x=start.x + 24.0, y=start.y),
                ScenePoint(x=start.x + 24.0, y=corridor_y),
                ScenePoint(x=max(24.0, end.x - 24.0), y=corridor_y),
                ScenePoint(x=max(24.0, end.x - 24.0), y=end.y),
                end,
            ]
        else:
            corridor_x = (start.x + end.x) / 2 + ((index % 5) - 2) * 5.0
            points = [
                start,
                ScenePoint(x=corridor_x, y=start.y),
                ScenePoint(x=corridor_x, y=end.y),
                end,
            ]
        edges.append(edge.model_copy(update={"points": points}))
    return edges


def materialize_scene(base: VisualScene, document: CanvasDocument) -> VisualScene:
    node_updates: dict[str, dict[str, Any]] = {}
    route_hints: dict[str, list] = {}
    for patch in document.visual_patches:
        if not _patch_applies(patch, base):
            continue
        if patch.operation == "set-position" and patch.target_id:
            node_updates.setdefault(patch.target_id, {}).update(
                {"x": float(patch.value["x"]), "y": float(patch.value["y"])}
            )
        elif patch.operation == "set-size" and patch.target_id:
            node_updates.setdefault(patch.target_id, {}).update(
                {
                    "width": float(patch.value["width"]),
                    "height": float(patch.value["height"]),
                }
            )
        elif patch.operation == "set-label-wrap" and patch.target_id:
            node_updates.setdefault(patch.target_id, {})["label_lines"] = patch.value["lines"]
        elif patch.operation == "set-route-hint" and patch.target_id:
            route_hints[patch.target_id] = patch.value["points"]

    nodes: list[SceneNode] = []
    for node in base.nodes:
        update = node_updates.get(node.scene_node_id, {})
        lines = update.pop("label_lines", None)
        bounds = node.bounds.model_copy(update=update) if update else node.bounds
        nodes.append(
            node.model_copy(
                update={
                    "bounds": bounds,
                    **({"label_lines": lines} if lines is not None else {}),
                }
            )
        )
    children = [node for node in nodes if node.parent_scene_node_id is not None]
    paper_width = max(
        base.paper_width,
        max((node.bounds.x + node.bounds.width + 48.0 for node in children), default=0),
    )
    paper_height = max(
        base.paper_height,
        max((node.bounds.y + node.bounds.height + 48.0 for node in children), default=0),
    )
    roots = {node.scene_node_id for node in nodes if node.parent_scene_node_id is None}
    nodes = [
        node.model_copy(
            update={
                "bounds": SceneRect(
                    x=node.bounds.x,
                    y=node.bounds.y,
                    width=paper_width - node.bounds.x * 2,
                    height=paper_height - node.bounds.y * 2,
                )
            }
        )
        if node.scene_node_id in roots
        else node
        for node in nodes
    ]
    changed_node_ids = {
        target_id
        for target_id, update in node_updates.items()
        if any(key in update for key in ("x", "y", "width", "height"))
    }
    edges = _reroute_edges(base, nodes, route_hints, changed_node_ids)
    return base.model_copy(
        update={
            "paper_width": paper_width,
            "paper_height": paper_height,
            "nodes": nodes,
            "edges": edges,
        }
    )


def derive_view_state(document: CanvasDocument) -> dict[str, Any]:
    state = dict(document.view_state)
    pinned: set[str] = set()
    collapsed: set[str] = set()
    cameras: dict[str, dict[str, Any]] = {}
    for patch in document.visual_patches:
        if patch.operation == "set-pin" and patch.target_id:
            (pinned.add if patch.value["enabled"] else pinned.discard)(patch.target_id)
        elif patch.operation == "set-collapse" and patch.target_id:
            (collapsed.add if patch.value["enabled"] else collapsed.discard)(patch.target_id)
        elif patch.operation == "set-camera":
            scene_id = patch.value.get("scene_id")
            if not isinstance(scene_id, str):
                continue
            cameras[scene_id] = {
                key: patch.value[key] for key in ("x", "y", "zoom")
            }
        elif patch.operation == "set-theme":
            state["theme"] = patch.value.get("theme", "paper-light")
        elif patch.operation == "set-caption":
            state["caption"] = patch.value.get("caption", "")
    state["pinned_node_ids"] = sorted(pinned)
    state["collapsed_node_ids"] = sorted(collapsed)
    state["cameras"] = cameras
    return state
