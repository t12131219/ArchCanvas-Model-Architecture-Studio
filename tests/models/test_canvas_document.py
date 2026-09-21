from __future__ import annotations

import pytest
from pydantic import ValidationError

from archcanvas_core.models.canvas import CanvasDocument, CanvasNodeState, CanvasViewport


def _document(**updates: object) -> CanvasDocument:
    values: dict[str, object] = {
        "canvas_document_id": "canvas-document:fixture-layout",
        "project_id": "project:fixture",
        "publication_id": "publication:fixture",
        "base_source_revision": "sha256:" + "a" * 64,
        "viewport": CanvasViewport(x=0.0, y=0.0, zoom=1.0),
        "nodes": [
            CanvasNodeState(
                publication_node_id="publication-node:input",
                x=0.0,
                y=0.0,
                width=180.0,
                height=72.0,
            )
        ],
    }
    values.update(updates)
    return CanvasDocument(**values)


def test_canvas_document_rejects_source_or_architecture_payloads() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _document(architecture_patch={"operation": "set_parameter"})

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _document(source_anchor="model.py:12")


def test_canvas_document_annotation_must_target_a_visual_node() -> None:
    with pytest.raises(ValidationError, match="canvas annotation refers to a node without visual state"):
        _document(
            annotations=[
                {
                    "annotation_id": "canvas-annotation:missing-target",
                    "target_node_id": "publication-node:missing",
                    "text": "Not backed by a CanvasNodeState.",
                }
            ]
        )
