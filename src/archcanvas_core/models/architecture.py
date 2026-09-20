from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, TypeAlias, Union

from pydantic import Field, model_validator
from typing_extensions import TypeAliasType

from .common import StrictModel
from .source_identity import AnchorId, Framework, IdentityId, Sha256


JsonValue: TypeAlias = TypeAliasType(
    "JsonValue",
    Union[None, bool, int, float, str, list["JsonValue"], dict[str, "JsonValue"]],
)
NodeId = Annotated[str, Field(pattern=r"^node:[A-Za-z0-9._:-]+$")]
EdgeId = Annotated[str, Field(pattern=r"^edge:[A-Za-z0-9._:>-]+$")]
PortId = Annotated[str, Field(pattern=r"^port:[A-Za-z0-9._:>-]+$")]
RepeatId = Annotated[str, Field(pattern=r"^repeat:[A-Za-z0-9._:-]+$")]


class NodeKind(str, Enum):
    MODULE = "module"
    FUNCTION = "function"
    OPERATOR = "operator"
    INPUT = "input"
    OUTPUT = "output"
    MERGE = "merge"
    CONSTANT = "constant"
    CONTROL = "control"


class EdgeKind(str, Enum):
    DATA = "data"
    RESIDUAL = "residual"
    CONTROL = "control"
    PARAMETER = "parameter"


class EvidenceSource(str, Enum):
    STATIC_AST = "static_ast"
    STATIC_CST = "static_cst"
    FX = "torch_fx"
    TORCH_EXPORT = "torch_export"
    TORCHVIEW = "torchview"
    USER = "user"
    AGENT = "agent"


class Confidence(str, Enum):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    PROPOSED = "proposed"
    UNRESOLVED = "unresolved"


class ModelDescriptor(StrictModel):
    framework: Framework
    entrypoint: str = Field(min_length=1)
    model_class: str | None


class SymbolicDim(StrictModel):
    symbol: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    lower_bound: int | None = Field(default=None, ge=0)
    upper_bound: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def bounds_are_ordered(self) -> "SymbolicDim":
        if self.lower_bound is not None and self.upper_bound is not None and self.lower_bound > self.upper_bound:
            raise ValueError("lower_bound must not exceed upper_bound")
        return self


ShapeDim: TypeAlias = int | SymbolicDim | None


class TensorSpec(StrictModel):
    shape: list[ShapeDim]
    dtype: str | None
    device: str | None
    requires_grad: bool | None
    semantic_axes: list[str | None]

    @model_validator(mode="after")
    def axes_match_rank(self) -> "TensorSpec":
        if self.semantic_axes and len(self.semantic_axes) != len(self.shape):
            raise ValueError("semantic_axes must be empty or match tensor rank")
        return self


class Evidence(StrictModel):
    source: EvidenceSource
    confidence: Confidence
    description: str | None
    anchor_id: AnchorId | None
    trace_id: str | None


class ParameterOriginKind(str, Enum):
    LITERAL = "literal"
    CONSTANT = "constant"
    ARGUMENT = "argument"
    CONFIG_ATTRIBUTE = "config_attribute"
    COMPUTED = "computed"
    UNKNOWN = "unknown"


class ParameterOrigin(StrictModel):
    kind: ParameterOriginKind
    anchor_ids: list[AnchorId]


class ArchitectureParameter(StrictModel):
    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_.-]*$")
    source_name: str | None = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    value: JsonValue
    expression: str | None
    origin: ParameterOrigin
    evidence: list[Evidence] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_origin_form(self) -> "ArchitectureParameter":
        if self.origin.kind is ParameterOriginKind.LITERAL:
            if self.expression is not None or self.source_name is None:
                raise ValueError("literal parameter requires source_name and no expression")
        elif self.expression is None:
            raise ValueError("non-literal parameter requires source expression")
        return self


class ArchitecturePort(StrictModel):
    port_id: PortId
    direction: Literal["input", "output"]
    name: str | None
    tensor: TensorSpec | None


class ArchitectureNode(StrictModel):
    node_id: NodeId
    identity_id: IdentityId
    kind: NodeKind
    op_type: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    parent_id: NodeId | None
    parameters: list[ArchitectureParameter]
    input_ports: list[ArchitecturePort]
    output_ports: list[ArchitecturePort]
    semantic_role: str | None
    source_anchor_ids: list[AnchorId]
    metadata: dict[str, JsonValue]

    @model_validator(mode="after")
    def validate_local_uniqueness(self) -> "ArchitectureNode":
        names = [parameter.name for parameter in self.parameters]
        ports = self.input_ports + self.output_ports
        if len(names) != len(set(names)) or len(ports) != len({port.port_id for port in ports}):
            raise ValueError("node contains duplicate parameter or port")
        if any(port.direction != "input" for port in self.input_ports):
            raise ValueError("input_ports contains non-input port")
        if any(port.direction != "output" for port in self.output_ports):
            raise ValueError("output_ports contains non-output port")
        return self


class ArchitectureEdge(StrictModel):
    edge_id: EdgeId
    source_node_id: NodeId
    source_port_id: PortId | None
    target_node_id: NodeId
    target_port_id: PortId | None
    kind: EdgeKind
    tensor: TensorSpec | None
    semantic_role: str | None
    evidence: list[Evidence]
    metadata: dict[str, JsonValue]


class RepeatSpec(StrictModel):
    repeat_id: RepeatId
    member_node_ids: list[NodeId] = Field(min_length=1)
    count: int | None = Field(ge=1)
    count_symbol: str | None
    source_anchor_ids: list[AnchorId]

    @model_validator(mode="after")
    def exactly_one_count_form(self) -> "RepeatSpec":
        if (self.count is None) == (self.count_symbol is None):
            raise ValueError("exactly one of count and count_symbol is required")
        return self


class UnresolvedFact(StrictModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    message: str = Field(min_length=1)
    anchor_ids: list[AnchorId]
    blocking: bool


class ArchitectureIR(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    ir_id: str = Field(pattern=r"^ir:[A-Za-z0-9._-]+$")
    project_id: str = Field(min_length=1)
    source_revision: Sha256
    model: ModelDescriptor
    nodes: list[ArchitectureNode] = Field(min_length=1)
    edges: list[ArchitectureEdge]
    repeats: list[RepeatSpec]
    unresolved: list[UnresolvedFact]
    metadata: dict[str, JsonValue]

    def node(self, node_id: str) -> ArchitectureNode:
        return next(node for node in self.nodes if node.node_id == node_id)

    def parameter(self, node_id: str, name: str) -> ArchitectureParameter:
        return next(parameter for parameter in self.node(node_id).parameters if parameter.name == name)
