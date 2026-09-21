"""Strict, source-free CanvasDocument contracts for the Stage 6 desktop client."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import StrictModel
from .publication import PublicationNodeId
from .source_identity import Sha256

CanvasDocumentId = Annotated[str, Field(pattern=r"^canvas-document:[A-Za-z0-9._-]+$")]
CanvasAnnotationId = Annotated[str, Field(pattern=r"^canvas-annotation:[A-Za-z0-9._-]+$")]


class CanvasLayoutMode(str, Enum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"


class CanvasViewport(StrictModel):
    """The client viewport, intentionally independent from publication geometry."""

    x: float = Field(ge=-100_000, le=100_000)
    y: float = Field(ge=-100_000, le=100_000)
    zoom: float = Field(ge=0.1, le=4.0)


class CanvasNodeStyle(StrictModel):
    """A deliberately small, visual-only style palette."""

    fill_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    stroke_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class CanvasNodeState(StrictModel):
    """Per-publication-node visual state; it cannot encode a graph or source patch."""

    publication_node_id: PublicationNodeId
    x: float = Field(ge=-100_000, le=100_000)
    y: float = Field(ge=-100_000, le=100_000)
    width: float = Field(ge=80, le=1_200)
    height: float = Field(ge=40, le=640)
    style: CanvasNodeStyle = Field(default_factory=CanvasNodeStyle)
    collapsed: bool = False
    locked: bool = False


class CanvasAnnotation(StrictModel):
    annotation_id: CanvasAnnotationId
    target_node_id: PublicationNodeId
    text: str = Field(min_length=1, max_length=500)


class CanvasDocument(StrictModel):
    """Persisted visual state keyed to one immutable Publication IR revision.

    This model intentionally contains no architecture parameters, source anchors, ports,
    edges, or source-write payload. Those facts belong to other, independently validated
    protocols.
    """

    schema_version: Literal["1.0"] = "1.0"
    canvas_document_id: CanvasDocumentId
    project_id: str = Field(pattern=r"^project:[A-Za-z0-9._-]+$")
    publication_id: str = Field(pattern=r"^publication:[A-Za-z0-9._-]+$")
    base_source_revision: Sha256
    layout_mode: CanvasLayoutMode = CanvasLayoutMode.AUTOMATIC
    viewport: CanvasViewport
    nodes: list[CanvasNodeState] = Field(min_length=1)
    annotations: list[CanvasAnnotation] = Field(default_factory=list)

    @model_validator(mode="after")
    def visual_identifiers_are_unique(self) -> CanvasDocument:
        node_ids = [node.publication_node_id for node in self.nodes]
        annotation_ids = [annotation.annotation_id for annotation in self.annotations]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("duplicate canvas publication node")
        if len(annotation_ids) != len(set(annotation_ids)):
            raise ValueError("duplicate canvas annotation")
        if any(annotation.target_node_id not in set(node_ids) for annotation in self.annotations):
            raise ValueError("canvas annotation refers to a node without visual state")
        return self
