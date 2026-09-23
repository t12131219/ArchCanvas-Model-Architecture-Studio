from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9._:-]*$")]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Confidence(str, Enum):
    EXACT = "exact"
    RUNTIME_CONFIRMED = "runtime-confirmed"
    EQUIVALENT = "equivalent"
    INFERRED = "inferred"
    UNRESOLVED = "unresolved"
    REFERENCE_ONLY = "reference-only"
    CONTRADICTED = "contradicted"


class EvidenceKind(str, Enum):
    SOURCE = "source"
    CONFIG = "config"
    RUNTIME = "runtime"
    CHECKPOINT = "checkpoint"
    REFERENCE = "reference"


class SourceSpan(StrictModel):
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    start_column: int = Field(default=0, ge=0)
    end_column: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def ordered(self) -> SourceSpan:
        if self.end_line < self.start_line:
            raise ValueError("source span end_line precedes start_line")
        return self


class SourceFile(StrictModel):
    path: str = Field(min_length=1)
    sha256: Sha256


class SourceSnapshot(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    snapshot_id: Identifier
    project_root: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    entrypoint: str = Field(min_length=3)
    task: str = Field(min_length=1)
    execution_mode: Literal["eval", "train"]
    framework: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    config_digest: Sha256
    config_path: str | None = None
    resolved_config: dict[str, Any] = Field(default_factory=dict)
    source_files: list[SourceFile] = Field(min_length=1)


class EvidenceRecord(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    evidence_id: Identifier
    kind: EvidenceKind
    path: str | None = None
    symbol: str | None = None
    span: SourceSpan | None = None
    file_sha256: Sha256 | None = None
    revision: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    confidence: Confidence
    execution_predicate: str = Field(min_length=1)

    @model_validator(mode="after")
    def source_has_location(self) -> EvidenceRecord:
        if self.kind is EvidenceKind.SOURCE and not (
            self.path and self.symbol and self.span and self.file_sha256
        ):
            raise ValueError("source evidence requires path, symbol, span, and file_sha256")
        if self.confidence is Confidence.REFERENCE_ONLY and self.kind is not EvidenceKind.REFERENCE:
            raise ValueError("reference-only confidence requires reference evidence")
        return self


class NodeKind(str, Enum):
    MODULE_CONTAINER = "module_container"
    OPERATOR = "operator"
    TENSOR_VALUE = "tensor_value"
    MERGE_EVENT = "merge_event"
    FANOUT_RELATION = "fanout_relation"
    CONDITION_CONTROL = "condition_control"
    STATE = "state"
    REPEAT = "repeat"
    PARAMETER_SHARE = "parameter_share"
    INPUT_OUTPUT = "input_output"
    REFERENCE_ONLY = "reference_only"


class EdgeType(str, Enum):
    MAIN = "main"
    RESIDUAL = "residual"
    SKIP = "skip"
    MEMORY = "memory"
    STATE = "state"
    CONDITION = "condition"
    ROUTING = "routing"
    PARAMETER_SHARE = "parameter-share"
    TRAINING_ONLY = "training-only"


class RepeatKind(str, Enum):
    STACK = "stack"
    TIME = "time"
    SCALE = "scale"
    OUTER_ITERATION = "outer-iteration"
    DYNAMIC_ROUTE = "dynamic-route"


class Port(StrictModel):
    port_id: Identifier
    name: str = Field(min_length=1)
    direction: Literal["input", "output"]
    role: str = Field(min_length=1)


class ParameterOrigin(str, Enum):
    LITERAL = "literal"
    CONSTRUCTOR_DEFAULT = "constructor-default"
    CONFIG = "config"
    COMPUTED = "computed"
    UNRESOLVED = "unresolved"


class ArchitectureParameter(StrictModel):
    name: str = Field(min_length=1)
    source_expression: str = Field(min_length=1)
    value: Any = None
    origin: ParameterOrigin
    evidence_ids: list[Identifier] = Field(min_length=1)


class ArchitectureNode(StrictModel):
    node_id: Identifier
    kind: NodeKind
    semantic_name: str = Field(min_length=1)
    source_symbol: str | None = None
    parent_id: Identifier | None = None
    children: list[Identifier] = Field(default_factory=list)
    input_ports: list[Port] = Field(default_factory=list)
    output_ports: list[Port] = Field(default_factory=list)
    parameters: list[ArchitectureParameter] = Field(default_factory=list)
    repeat_id: Identifier | None = None
    parameter_identity: str = Field(default="not-applicable", min_length=1)
    execution_predicate: str = Field(min_length=1)
    evidence_ids: list[Identifier] = Field(default_factory=list)
    confidence: Confidence
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def ports_are_well_formed(self) -> ArchitectureNode:
        ports = self.input_ports + self.output_ports
        if len({port.port_id for port in ports}) != len(ports):
            raise ValueError("node port identifiers must be unique")
        if any(port.direction != "input" for port in self.input_ports):
            raise ValueError("input_ports contains a non-input port")
        if any(port.direction != "output" for port in self.output_ports):
            raise ValueError("output_ports contains a non-output port")
        return self


class TensorValue(StrictModel):
    tensor_id: Identifier
    role: str = Field(min_length=1)
    producer_id: Identifier
    producer_port: Identifier
    consumer_ids: list[Identifier] = Field(min_length=1)
    symbolic_shape: str = Field(default="[?]", min_length=1)
    semantic_axes: list[str] = Field(default_factory=list)
    dtype: str = "unknown"
    provenance: str = Field(min_length=1)
    confidence: Confidence
    evidence_ids: list[Identifier] = Field(default_factory=list)


class ArchitectureEdge(StrictModel):
    edge_id: Identifier
    tensor_id: Identifier
    producer_id: Identifier
    producer_port: Identifier
    consumer_id: Identifier
    consumer_port: Identifier
    role: str = Field(min_length=1)
    edge_type: EdgeType
    symbolic_shape: str = Field(default="[?]", min_length=1)
    semantic_axes: list[str] = Field(default_factory=list)
    evidence_ids: list[Identifier] = Field(default_factory=list)
    confidence: Confidence
    execution_predicate: str = Field(min_length=1)


class FanoutRelation(StrictModel):
    relation_id: Identifier
    tensor_id: Identifier
    producer_id: Identifier
    consumer_ids: list[Identifier] = Field(min_length=2)
    evidence_ids: list[Identifier] = Field(min_length=1)


class Repeat(StrictModel):
    repeat_id: Identifier
    kind: RepeatKind
    member_node_ids: list[Identifier] = Field(min_length=1)
    count: int | None = Field(default=None, ge=1)
    count_symbol: str | None = None
    parameter_identity: str = Field(min_length=1)
    evidence_ids: list[Identifier] = Field(default_factory=list)

    @model_validator(mode="after")
    def one_count_form(self) -> Repeat:
        if (self.count is None) == (self.count_symbol is None):
            raise ValueError("repeat requires exactly one of count or count_symbol")
        return self


class UnresolvedFact(StrictModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    message: str = Field(min_length=1)
    blocking: bool
    evidence_ids: list[Identifier] = Field(default_factory=list)


class ArchitectureIR(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    architecture_id: Identifier
    source_snapshot_id: Identifier
    framework: str = Field(min_length=1)
    entrypoint: str = Field(min_length=3)
    nodes: list[ArchitectureNode] = Field(min_length=1)
    tensors: list[TensorValue] = Field(default_factory=list)
    edges: list[ArchitectureEdge] = Field(default_factory=list)
    fanouts: list[FanoutRelation] = Field(default_factory=list)
    repeats: list[Repeat] = Field(default_factory=list)
    unresolved: list[UnresolvedFact] = Field(default_factory=list)


class VisualPatch(StrictModel):
    patch_id: Identifier
    operation: Literal[
        "set-position",
        "set-size",
        "set-pin",
        "set-route-hint",
        "set-label-wrap",
        "set-theme",
        "set-collapse",
        "set-camera",
        "add-annotation",
    ]
    target_id: Identifier | None = None
    value: dict[str, Any]


class CanvasDocument(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    document_id: Identifier
    source_snapshot_id: Identifier
    architecture_id: Identifier
    source_digest: Sha256
    visual_patches: list[VisualPatch] = Field(default_factory=list)
    view_state: dict[str, Any] = Field(default_factory=dict)


class Diagnostic(StrictModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    severity: Literal["blocking", "warning", "unresolved", "suggestion"]
    message: str = Field(min_length=1)
    target_ids: list[Identifier] = Field(default_factory=list)


class GateResult(StrictModel):
    gate: str = Field(pattern=r"^[A-Z][A-Za-z0-9_-]+$")
    status: Literal["passed", "failed", "skipped"]
    message: str = Field(min_length=1)


class CommandReceipt(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    command: str = Field(min_length=1)
    status: Literal["ok", "invalid", "unavailable", "failed"]
    exit_code: Literal[0, 1, 2, 3]
    artifacts: dict[str, str] = Field(default_factory=dict)
    gates: list[GateResult] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def status_matches_exit_code(self) -> CommandReceipt:
        expected = {"ok": 0, "failed": 1, "invalid": 2, "unavailable": 3}
        if self.exit_code != expected[self.status]:
            raise ValueError("receipt status and exit code disagree")
        return self


SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "source-snapshot-v1.schema.json": SourceSnapshot,
    "evidence-record-v1.schema.json": EvidenceRecord,
    "architecture-ir-v1.schema.json": ArchitectureIR,
    "canvas-document-v1.schema.json": CanvasDocument,
    "command-receipt-v1.schema.json": CommandReceipt,
}
