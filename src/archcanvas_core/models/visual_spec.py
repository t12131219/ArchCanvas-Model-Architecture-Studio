"""Renderer-independent composition of source-mapped publication facts."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field, model_validator

from .architecture import PortId
from .common import StrictModel
from .publication import PublicationEdgeId, PublicationId, PublicationNodeId, PublicationNodeKind
from .source_identity import Sha256


class ReadingDirection(str, Enum):
    LEFT_TO_RIGHT = "left_to_right"
    BOTTOM_TO_TOP = "bottom_to_top"
    MIXED = "mixed"


class VisualCanvas(StrictModel):
    composition_mode: Literal["integrated"] = "integrated"
    reading_direction: ReadingDirection = ReadingDirection.LEFT_TO_RIGHT
    default_detail_level: Literal["L1"] = "L1"
    opening_policy: Literal["overview"] = "overview"


class VisualPort(StrictModel):
    port_id: PortId
    direction: Literal["input", "output"]


class VisualNode(StrictModel):
    canonical_id: PublicationNodeId
    label: str = Field(min_length=1, max_length=120)
    visual_class: PublicationNodeKind
    parent_id: PublicationNodeId | None = None
    detail_level: Literal["L1"] = "L1"
    children: list[PublicationNodeId] = Field(default_factory=list)
    ports: list[VisualPort] = Field(default_factory=list)
    inline_expand: bool = False


class VisualEdge(StrictModel):
    canonical_id: PublicationEdgeId
    source_node_id: PublicationNodeId
    target_node_id: PublicationNodeId
    source_port_id: PortId | None = None
    target_port_id: PortId | None = None
    edge_type: Literal["main", "residual"]
    route_preference: Literal["orthogonal"] = "orthogonal"


class VisualConstraint(StrictModel):
    kind: Literal["before"]
    source_node_id: PublicationNodeId
    target_node_id: PublicationNodeId


class VisualViewPolicy(StrictModel):
    # This becomes true only after source-mapped children and their edges are available.
    direct_full_detail_supported: bool = False


class VisualSpec(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    spec_id: str = Field(pattern=r"^visual-spec:[A-Za-z0-9._-]+$")
    publication_id: PublicationId
    source_revision: Sha256
    canvas: VisualCanvas = Field(default_factory=VisualCanvas)
    nodes: list[VisualNode] = Field(min_length=2)
    edges: list[VisualEdge]
    constraints: list[VisualConstraint] = Field(default_factory=list)
    view_policy: VisualViewPolicy = Field(default_factory=VisualViewPolicy)

    @model_validator(mode="after")
    def references_are_unique_and_closed(self) -> VisualSpec:
        node_ids = [node.canonical_id for node in self.nodes]
        edge_ids = [edge.canonical_id for edge in self.edges]
        if len(node_ids) != len(set(node_ids)) or len(edge_ids) != len(set(edge_ids)):
            raise ValueError("duplicate visual canonical id")
        by_id = {node.canonical_id: node for node in self.nodes}
        for node in self.nodes:
            if node.parent_id is not None or node.children or node.inline_expand:
                raise ValueError("inline expansion requires a source-mapped hierarchy")
            ports = [port.port_id for port in node.ports]
            if len(ports) != len(set(ports)):
                raise ValueError("duplicate visual port")
        for edge in self.edges:
            source = by_id.get(edge.source_node_id)
            target = by_id.get(edge.target_node_id)
            if source is None or target is None:
                raise ValueError("visual edge refers to an unknown node")
            if edge.source_port_id is not None and not any(
                port.port_id == edge.source_port_id and port.direction == "output"
                for port in source.ports
            ):
                raise ValueError("visual edge source port is not an output of its node")
            if edge.target_port_id is not None and not any(
                port.port_id == edge.target_port_id and port.direction == "input"
                for port in target.ports
            ):
                raise ValueError("visual edge target port is not an input of its node")
        for constraint in self.constraints:
            if (
                constraint.source_node_id not in by_id
                or constraint.target_node_id not in by_id
                or constraint.source_node_id == constraint.target_node_id
            ):
                raise ValueError("visual constraint refers to invalid nodes")
        if self.view_policy.direct_full_detail_supported:
            raise ValueError("full detail requires a source-mapped hierarchy")
        return self
