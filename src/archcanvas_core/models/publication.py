"""Publication and scene protocols derived from, but separate from, Exact Architecture IR."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .architecture import EdgeId, NodeId
from .common import StrictModel
from .source_identity import Sha256

PublicationId = Annotated[str, Field(pattern=r"^publication:[A-Za-z0-9._-]+$")]
PublicationNodeId = Annotated[str, Field(pattern=r"^publication-node:[A-Za-z0-9._-]+$")]
PublicationEdgeId = Annotated[str, Field(pattern=r"^publication-edge:[A-Za-z0-9._-]+$")]
SceneId = Annotated[str, Field(pattern=r"^scene:[A-Za-z0-9._-]+$")]
SceneNodeId = Annotated[str, Field(pattern=r"^scene-node:[A-Za-z0-9._-]+$")]
SceneEdgeId = Annotated[str, Field(pattern=r"^scene-edge:[A-Za-z0-9._-]+$")]
AnnotationId = Annotated[str, Field(pattern=r"^annotation:[A-Za-z0-9._-]+$")]


class PublicationNodeKind(str, Enum):
    INPUT = "input"
    MODULE = "module"
    REPEAT_GROUP = "repeat_group"
    RESIDUAL_BLOCK = "residual_block"
    OUTPUT = "output"


class PublicationEdgeKind(str, Enum):
    DATA = "data"
    RESIDUAL = "residual"


class PublicationNode(StrictModel):
    node_id: PublicationNodeId
    kind: PublicationNodeKind
    label: str = Field(min_length=1, max_length=120)
    member_node_ids: list[NodeId] = Field(min_length=1)
    collapsed: bool


class PublicationEdge(StrictModel):
    edge_id: PublicationEdgeId
    source_node_id: PublicationNodeId
    target_node_id: PublicationNodeId
    kind: PublicationEdgeKind
    member_edge_ids: list[EdgeId] = Field(min_length=1)


class PublicationAnnotation(StrictModel):
    annotation_id: AnnotationId
    target_node_id: PublicationNodeId
    text: str = Field(min_length=1, max_length=160)
    kind: Literal["repeat", "residual"]


class PublicationIR(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    publication_id: PublicationId
    exact_ir_id: str = Field(pattern=r"^ir:[A-Za-z0-9._-]+$")
    project_id: str = Field(min_length=1)
    source_revision: Sha256
    nodes: list[PublicationNode] = Field(min_length=2)
    edges: list[PublicationEdge]
    annotations: list[PublicationAnnotation]
    omitted_exact_node_ids: list[NodeId]
    omitted_exact_edge_ids: list[EdgeId]

    @model_validator(mode="after")
    def publication_identifiers_are_unique(self) -> PublicationIR:
        identifiers = [node.node_id for node in self.nodes]
        edge_ids = [edge.edge_id for edge in self.edges]
        annotation_ids = [annotation.annotation_id for annotation in self.annotations]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("duplicate publication node_id")
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("duplicate publication edge_id")
        if len(annotation_ids) != len(set(annotation_ids)):
            raise ValueError("duplicate publication annotation_id")
        if len(self.omitted_exact_node_ids) != len(set(self.omitted_exact_node_ids)):
            raise ValueError("duplicate omitted exact node_id")
        if len(self.omitted_exact_edge_ids) != len(set(self.omitted_exact_edge_ids)):
            raise ValueError("duplicate omitted exact edge_id")
        node_ids = set(identifiers)
        if any(edge.source_node_id not in node_ids or edge.target_node_id not in node_ids for edge in self.edges):
            raise ValueError("publication edge refers to an unknown node")
        if any(annotation.target_node_id not in node_ids for annotation in self.annotations):
            raise ValueError("publication annotation refers to an unknown node")
        return self


class ScenePoint(StrictModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class SceneNode(StrictModel):
    scene_node_id: SceneNodeId
    publication_node_id: PublicationNodeId
    expanded: bool = False
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=40, le=640)
    height: int = Field(ge=32, le=320)


class SceneEdge(StrictModel):
    scene_edge_id: SceneEdgeId
    publication_edge_id: PublicationEdgeId
    points: list[ScenePoint] = Field(min_length=2)


class VisualScene(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    scene_id: SceneId
    publication_id: PublicationId
    width: int = Field(ge=200, le=20_000)
    height: int = Field(ge=120, le=20_000)
    nodes: list[SceneNode] = Field(min_length=2)
    edges: list[SceneEdge]

    @model_validator(mode="after")
    def scene_node_identifiers_are_unique(self) -> VisualScene:
        scene_ids = [node.scene_node_id for node in self.nodes]
        publication_ids = [node.publication_node_id for node in self.nodes]
        if len(scene_ids) != len(set(scene_ids)):
            raise ValueError("duplicate scene_node_id")
        if len(publication_ids) != len(set(publication_ids)):
            raise ValueError("scene must contain each publication node once")
        if any(node.x + node.width > self.width or node.y + node.height > self.height for node in self.nodes):
            raise ValueError("scene node is outside scene bounds")
        return self
