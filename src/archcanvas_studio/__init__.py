"""Persistent visual editing and local Studio delivery."""

from .bundle import StudioBundle, prepare_studio_bundle
from .document import (
    apply_patch,
    apply_patch_batch,
    create_canvas_document,
    derive_view_state,
    load_canvas_document,
    materialize_scene,
    persist_canvas_document,
    redo_patch,
    source_binding_digest,
    undo_patch,
)
from .operations import auto_route_batch

__all__ = [
    "StudioBundle",
    "apply_patch",
    "apply_patch_batch",
    "auto_route_batch",
    "create_canvas_document",
    "derive_view_state",
    "load_canvas_document",
    "materialize_scene",
    "persist_canvas_document",
    "prepare_studio_bundle",
    "redo_patch",
    "source_binding_digest",
    "undo_patch",
]
