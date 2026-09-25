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
    PatchBatch,
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
    scenes: Iterable[VisualScene] = (),
    *,
    hierarchy_id: str | None = None,
) -> CanvasDocument:
    suffix = ir.architecture_id.removeprefix("architecture:")
    return CanvasDocument(
        document_id=f"document:{suffix}",
        source_snapshot_id=snapshot.snapshot_id,
        architecture_id=ir.architecture_id,
        source_digest=source_binding_digest(snapshot),
        base_hierarchy_id=hierarchy_id,
        view_state={
            "mode": "explore",
            "theme": "paper-light",
            "navigation_view": "module",
            "layout_mode": "auto",
        },
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
    elif patch.operation == "set-line-weight":
        width = _number(patch.value.get("width"), "line weight", positive=True)
        if width > 8:
            raise ValueError("line weight must not exceed 8")
    elif patch.operation == "set-palette":
        overrides = patch.value.get("overrides")
        if not isinstance(overrides, dict):
            raise ValueError("set-palette requires an overrides object")
        if any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or not value.startswith("#")
            or len(value) not in {4, 7, 9}
            for key, value in overrides.items()
        ):
            raise ValueError("palette overrides must map identifiers to hex colors")


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
    state = dict(changed.view_state)
    state["_redo_batches"] = []
    changed = changed.model_copy(update={"view_state": state})
    if changed.source_digest != document.source_digest:
        raise AssertionError("visual patch changed the source binding")
    return changed


def apply_patch_batch(
    document: CanvasDocument,
    batch: PatchBatch,
    scenes: dict[str, VisualScene],
) -> CanvasDocument:
    """Apply a validated group of visual changes as one history action."""
    state = dict(document.view_state)
    known_batch_ids = {
        item.get("batch_id")
        for key in ("_history_batches", "_redo_batches")
        for item in state.get(key, [])
        if isinstance(item, dict)
    }
    if batch.batch_id in known_batch_ids:
        raise ValueError("visual patch batch identifier already exists")
    camera_keys = [
        patch.value.get("scene_id")
        for patch in batch.patches
        if patch.operation == "set-camera"
    ]
    if len(camera_keys) != len(set(camera_keys)):
        raise ValueError("a patch batch cannot contain repeated camera updates")
    changed = document
    for patch in batch.patches:
        changed = apply_patch(changed, patch, scenes)
    state = dict(changed.view_state)
    history = list(state.get("_history_batches", []))
    history.append(
        {
            "batch_id": batch.batch_id,
            "description": batch.description,
            "patch_ids": [patch.patch_id for patch in batch.patches],
        }
    )
    state["_history_batches"] = history
    state["_redo_batches"] = []
    changed = changed.model_copy(update={"view_state": state})
    if changed.source_digest != document.source_digest:
        raise AssertionError("visual patch batch changed the source binding")
    return changed


def undo_patch(document: CanvasDocument) -> CanvasDocument:
    state = dict(document.view_state)
    history = list(state.get("_history_batches", []))
    record = history[-1] if history else None
    patch_ids = record.get("patch_ids", []) if isinstance(record, dict) else []
    is_batch = bool(patch_ids) and [
        patch.patch_id for patch in document.visual_patches[-len(patch_ids) :]
    ] == patch_ids
    changed = document
    if is_batch:
        for _ in patch_ids:
            changed = undo_visual_patch(changed)
        history.pop()
        redo = list(state.get("_redo_batches", []))
        state["_history_batches"] = history
        state["_redo_batches"] = [record, *redo]
        changed = changed.model_copy(update={"view_state": state})
    else:
        changed = undo_visual_patch(document)
    if changed.source_digest != document.source_digest:
        raise AssertionError("undo changed the source binding")
    return changed


def redo_patch(document: CanvasDocument) -> CanvasDocument:
    state = dict(document.view_state)
    redo = list(state.get("_redo_batches", []))
    record = redo[0] if redo else None
    patch_ids = record.get("patch_ids", []) if isinstance(record, dict) else []
    is_batch = bool(patch_ids) and [
        patch.patch_id for patch in document.redo_patches[: len(patch_ids)]
    ] == patch_ids
    changed = document
    if is_batch:
        for _ in patch_ids:
            changed = redo_visual_patch(changed)
        history = list(state.get("_history_batches", []))
        state["_history_batches"] = [*history, record]
        state["_redo_batches"] = redo[1:]
        changed = changed.model_copy(update={"view_state": state})
    else:
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
    original_by_id = {node.scene_node_id: node for node in scene.nodes}
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
        original_source = original_by_id[edge.source_scene_node_id].bounds
        original_target = original_by_id[edge.target_scene_node_id].bounds
        source = by_id[edge.source_scene_node_id].bounds
        target = by_id[edge.target_scene_node_id].bounds
        source_delta = (source.x - original_source.x, source.y - original_source.y)
        target_delta = (target.x - original_target.x, target.y - original_target.y)
        both_translated = (
            {edge.source_scene_node_id, edge.target_scene_node_id}.issubset(changed_node_ids)
            and source.width == original_source.width
            and source.height == original_source.height
            and target.width == original_target.width
            and target.height == original_target.height
            and abs(source_delta[0] - target_delta[0]) < 1e-6
            and abs(source_delta[1] - target_delta[1]) < 1e-6
        )
        if both_translated:
            edges.append(
                edge.model_copy(
                    update={
                        "points": [
                            point.model_copy(
                                update={
                                    "x": point.x + source_delta[0],
                                    "y": point.y + source_delta[1],
                                }
                            )
                            for point in edge.points
                        ]
                    }
                )
            )
            continue
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
    node_style_updates: dict[str, dict[str, Any]] = {}
    route_hints: dict[str, list] = {}
    line_width: float | None = None
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
        elif patch.operation == "set-palette":
            for target_id, color in patch.value.get("overrides", {}).items():
                node_style_updates.setdefault(target_id, {})["fill"] = color
        elif patch.operation == "set-line-weight":
            line_width = float(patch.value["width"])

    nodes: list[SceneNode] = []
    for node in base.nodes:
        update = node_updates.get(node.scene_node_id, {})
        lines = update.pop("label_lines", None)
        bounds = node.bounds.model_copy(update=update) if update else node.bounds
        nodes.append(
            node.model_copy(
                update={
                    "bounds": bounds,
                    **node_style_updates.get(node.scene_node_id, {}),
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
    if line_width is not None:
        edges = [edge.model_copy(update={"width": line_width}) for edge in edges]
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
    state.setdefault("navigation_view", "module")
    state.setdefault("layout_mode", "auto")
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
        elif patch.operation == "set-font-scale":
            state["font_scale"] = patch.value["scale"]
        elif patch.operation == "set-line-weight":
            state["line_weight"] = patch.value["width"]
        elif patch.operation == "set-palette":
            overrides = dict(state.get("palette_overrides", {}))
            overrides.update(patch.value.get("overrides", {}))
            state["palette_overrides"] = overrides
    state["pinned_node_ids"] = sorted(pinned)
    state["collapsed_node_ids"] = sorted(collapsed)
    state["cameras"] = cameras
    return state
