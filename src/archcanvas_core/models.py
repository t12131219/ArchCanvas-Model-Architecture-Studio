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
    runtime_trace_id: Identifier | None = None
    runtime_observation_ids: list[Identifier] = Field(default_factory=list)

    @model_validator(mode="after")
    def source_has_location(self) -> EvidenceRecord:
        if self.kind is EvidenceKind.SOURCE and not (
            self.path and self.symbol and self.span and self.file_sha256
        ):
            raise ValueError("source evidence requires path, symbol, span, and file_sha256")
        if self.confidence is Confidence.REFERENCE_ONLY and self.kind is not EvidenceKind.REFERENCE:
            raise ValueError("reference-only confidence requires reference evidence")
        if self.kind is EvidenceKind.RUNTIME and not self.runtime_trace_id:
            raise ValueError("runtime evidence requires a runtime trace identifier")
        if self.kind is not EvidenceKind.RUNTIME and (
            self.runtime_trace_id or self.runtime_observation_ids
        ):
            raise ValueError("only runtime evidence may reference runtime observations")
        return self


RuntimeDimension = Annotated[int, Field(ge=1)]


class RuntimeInput(StrictModel):
    name: Identifier
    shape: list[RuntimeDimension] = Field(min_length=1)
    dtype: Literal[
        "float16",
        "float32",
        "float64",
        "bfloat16",
        "int32",
        "int64",
        "bool",
    ] = "float32"
    generator: Literal["zeros", "ones", "normal", "uniform", "randint"] = "normal"
    low: float | int | None = None
    high: float | int | None = None

    @model_validator(mode="after")
    def generator_parameters_are_valid(self) -> RuntimeInput:
        if self.generator == "randint":
            if self.dtype not in {"int32", "int64"}:
                raise ValueError("randint inputs require an integer dtype")
            if self.low is None or self.high is None or self.low >= self.high:
                raise ValueError("randint inputs require low < high")
        if self.dtype == "bool" and self.generator not in {"zeros", "ones"}:
            raise ValueError("boolean inputs support only zeros or ones")
        return self


class RuntimeInputSpec(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    seed: int = Field(default=0, ge=0, le=2**63 - 1)
    device: Literal["cpu", "cuda", "auto"] = "cpu"
    constructor_kwargs: dict[str, Any] = Field(default_factory=dict)
    forward_kwargs: dict[str, Any] = Field(default_factory=dict)
    inputs: list[RuntimeInput] = Field(min_length=1)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    cpu_limit_seconds: int = Field(default=20, ge=1, le=300)
    memory_limit_mb: int = Field(default=8192, ge=512, le=65536)

    @model_validator(mode="after")
    def input_names_are_unique(self) -> RuntimeInputSpec:
        names = [item.name for item in self.inputs]
        if len(names) != len(set(names)):
            raise ValueError("runtime input names must be unique")
        return self


class RuntimeTensorObservation(StrictModel):
    shape: list[int]
    dtype: str = Field(min_length=1)
    device: str = Field(min_length=1)
    requires_grad: bool


class RuntimeObservation(StrictModel):
    observation_id: Identifier
    sequence: int = Field(ge=0)
    module_path: str = Field(min_length=1)
    module_type: str = Field(min_length=1)
    input_tensors: list[RuntimeTensorObservation] = Field(default_factory=list)
    output_tensors: list[RuntimeTensorObservation] = Field(default_factory=list)
    matched_node_ids: list[Identifier] = Field(default_factory=list)


class RuntimeBoundaryViolation(StrictModel):
    operation: Literal["network", "process", "write"]
    target: str = Field(min_length=1)


class RuntimeIsolation(StrictModel):
    process: Literal["isolated-subprocess"] = "isolated-subprocess"
    working_directory: Literal["temporary-sandbox"] = "temporary-sandbox"
    network: Literal["python-socket-deny"] = "python-socket-deny"
    child_processes: Literal["python-process-deny"] = "python-process-deny"
    writes: Literal["sandbox-only"] = "sandbox-only"
    environment: Literal["allowlisted"] = "allowlisted"
    timeout_seconds: int = Field(ge=1)
    cpu_limit_seconds: int = Field(ge=1)
    memory_limit_mb: int = Field(ge=512)
    violations: list[RuntimeBoundaryViolation] = Field(default_factory=list)


class RuntimeEnvironment(StrictModel):
    python_version: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    torch_version: str = Field(min_length=1)
    cuda_build: str | None = None
    cuda_available: bool
    selected_device: str = Field(min_length=1)
    deterministic_algorithms: bool


class RuntimeTrace(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    trace_id: Identifier
    architecture_id: Identifier
    source_snapshot_id: Identifier
    source_revision: str = Field(min_length=1)
    entrypoint: str = Field(min_length=3)
    input_spec: RuntimeInputSpec
    input_spec_digest: Sha256
    replay_digest: Sha256
    observations: list[RuntimeObservation] = Field(min_length=1)
    output_tensors: list[RuntimeTensorObservation] = Field(default_factory=list)
    environment: RuntimeEnvironment
    isolation: RuntimeIsolation


class RuntimeCapabilityReport(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    adapter: Literal["pytorch-hooks-v1"] = "pytorch-hooks-v1"
    runtime_available: bool
    torch_version: str | None = None
    cuda_build: str | None = None
    cuda_available: bool
    supported_devices: list[Literal["cpu", "cuda"]] = Field(min_length=1)
    shape_trace: bool = True
    dtype_trace: bool = True
    replay_check: bool = True
    isolation: RuntimeIsolation
    limitations: list[str] = Field(default_factory=list)


class NodeKind(str, Enum):
    MODULE_CONTAINER = "module_container"
    OPERATOR = "operator"
    OPAQUE_COMPOSITE = "opaque_composite"
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


class ConfigPredicate(StrictModel):
    predicate_id: Identifier
    expression: str = Field(min_length=1)
    resolved_value: Any
    affected_ids: list[Identifier] = Field(default_factory=list)
    evidence_ids: list[Identifier] = Field(min_length=1)


class DiscrepancyRecord(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    discrepancy_id: Identifier
    subject: str = Field(min_length=1)
    reference_claim: str = Field(min_length=1)
    source_finding: str = Field(min_length=1)
    resolution: Literal[
        "exclude-from-executable-graph",
        "include-source-behavior",
        "mark-conditional",
        "mark-unresolved",
    ]
    evidence_ids: list[Identifier] = Field(min_length=1)


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
    config_predicates: list[ConfigPredicate] = Field(default_factory=list)
    unresolved: list[UnresolvedFact] = Field(default_factory=list)


class PublicationNode(StrictModel):
    view_node_id: Identifier
    canonical_node_ids: list[Identifier] = Field(min_length=1)
    semantic_name: str = Field(min_length=1)
    kind: NodeKind
    parent_view_node_id: Identifier | None = None
    collapsed: bool
    boundary_roles: list[str] = Field(default_factory=list)
    evidence_ids: list[Identifier] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class PublicationEdge(StrictModel):
    view_edge_id: Identifier
    canonical_edge_ids: list[Identifier] = Field(min_length=1)
    source_view_node_id: Identifier
    target_view_node_id: Identifier
    role: str = Field(min_length=1)
    edge_type: EdgeType
    symbolic_shape: str = Field(min_length=1)
    evidence_ids: list[Identifier] = Field(default_factory=list)


class PublicationView(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    view_id: Identifier
    architecture_id: Identifier
    level: Literal["L1", "L2", "L3", "L4"]
    name: str = Field(min_length=1)
    layout_family: Literal[
        "dual-lane",
        "single-lane",
        "dual-backbone",
        "multiscale-ladder",
        "generic-dag",
    ]
    nodes: list[PublicationNode] = Field(min_length=1)
    edges: list[PublicationEdge] = Field(default_factory=list)
    canonical_node_ids: list[Identifier] = Field(min_length=1)
    canonical_edge_ids: list[Identifier] = Field(default_factory=list)
    collapsed_edge_ids: list[Identifier] = Field(default_factory=list)
    canonical_tensor_ids: list[Identifier] = Field(default_factory=list)
    canonical_port_ids: list[Identifier] = Field(default_factory=list)
    non_executable_duplicates: bool = False


class VisualNodeStyle(StrictModel):
    view_node_id: Identifier
    glyph: Literal["container", "operator", "tensor", "merge", "io", "state", "opaque"]
    fill: str = Field(min_length=1)
    stroke: str = Field(min_length=1)
    label: str = Field(min_length=1)
    secondary_label: str | None = None


class VisualEdgeStyle(StrictModel):
    view_edge_id: Identifier
    stroke: str = Field(min_length=1)
    dash: str | None = None
    width: float = Field(default=1.5, gt=0)
    label: str = Field(min_length=1)


class VisualSpec(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    spec_id: Identifier
    view_id: Identifier
    theme: Literal["paper-light"] = "paper-light"
    font_family: str = Field(min_length=1)
    node_styles: list[VisualNodeStyle] = Field(min_length=1)
    edge_styles: list[VisualEdgeStyle] = Field(default_factory=list)


class ScenePoint(StrictModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)


class SceneRect(StrictModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class SceneNode(StrictModel):
    scene_node_id: Identifier
    view_node_id: Identifier
    canonical_node_ids: list[Identifier] = Field(min_length=1)
    bounds: SceneRect
    shape: Literal["container", "rect", "merge", "io", "state", "opaque"]
    label_lines: list[str] = Field(min_length=1, max_length=3)
    secondary_label: str | None = None
    fill: str = Field(min_length=1)
    stroke: str = Field(min_length=1)
    parent_scene_node_id: Identifier | None = None
    evidence_ids: list[Identifier] = Field(default_factory=list)


class SceneEdge(StrictModel):
    scene_edge_id: Identifier
    view_edge_id: Identifier
    canonical_edge_ids: list[Identifier] = Field(min_length=1)
    source_scene_node_id: Identifier
    target_scene_node_id: Identifier
    points: list[ScenePoint] = Field(min_length=2)
    role: str = Field(min_length=1)
    edge_type: EdgeType
    stroke: str = Field(min_length=1)
    dash: str | None = None
    width: float = Field(gt=0)
    label: str = Field(min_length=1)


class VisualScene(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    scene_id: Identifier
    view_id: Identifier
    spec_id: Identifier
    layout_family: str = Field(min_length=1)
    paper_width: float = Field(gt=0)
    paper_height: float = Field(gt=0)
    nodes: list[SceneNode] = Field(min_length=1)
    edges: list[SceneEdge] = Field(default_factory=list)


class VisualPatch(StrictModel):
    patch_id: Identifier
    operation: Literal[
        "set-position",
        "set-size",
        "set-pin",
        "set-alignment",
        "set-gap",
        "set-route-hint",
        "set-label-wrap",
        "set-caption",
        "set-legend-placement",
        "set-theme",
        "set-palette",
        "set-line-weight",
        "set-font-scale",
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
    base_scene_ids: list[Identifier] = Field(default_factory=list)
    visual_patches: list[VisualPatch] = Field(default_factory=list)
    redo_patches: list[VisualPatch] = Field(default_factory=list)
    view_state: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def history_is_well_formed(self) -> CanvasDocument:
        patch_ids = [
            patch.patch_id for patch in [*self.visual_patches, *self.redo_patches]
        ]
        if len(patch_ids) != len(set(patch_ids)):
            raise ValueError("visual patch identifiers must be unique across history")
        return self


class TransactionState(str, Enum):
    DRAFT = "draft"
    PLANNED = "planned"
    PREPARED = "prepared"
    SOURCE_VALIDATED = "source-validated"
    REANALYZED = "reanalyzed"
    GRAPH_DELTA_VALIDATED = "graph-delta-validated"
    TESTS_PASSED = "tests-passed"
    REVIEW_READY = "review-ready"
    COMMITTED = "committed"
    DISCARDED = "discarded"
    FAILED = "failed"


class SemanticParameterPatch(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    patch_id: Identifier
    operation: Literal["set_parameter"] = "set_parameter"
    artifact_path: str = Field(min_length=1)
    target_node_id: Identifier
    parameter_name: str = Field(min_length=1)
    new_value: Any
    targeted_tests: list[list[str]] = Field(default_factory=list)
    runtime_input_spec: str | None = None

    @model_validator(mode="after")
    def commands_are_nonempty(self) -> SemanticParameterPatch:
        if any(not command or any(not argument for argument in command) for command in self.targeted_tests):
            raise ValueError("targeted test commands must contain non-empty arguments")
        return self


class ParameterDelta(StrictModel):
    node_id: Identifier
    parameter_name: str = Field(min_length=1)
    before: Any
    after: Any
    source_expression: str = Field(min_length=1)


class ShapeDelta(StrictModel):
    subject_id: Identifier
    before: str = Field(min_length=1)
    after: str = Field(min_length=1)


class GraphDelta(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    added_nodes: list[Identifier] = Field(default_factory=list)
    removed_nodes: list[Identifier] = Field(default_factory=list)
    changed_nodes: list[Identifier] = Field(default_factory=list)
    added_edges: list[Identifier] = Field(default_factory=list)
    removed_edges: list[Identifier] = Field(default_factory=list)
    changed_edges: list[Identifier] = Field(default_factory=list)
    changed_parameters: list[ParameterDelta] = Field(default_factory=list)
    changed_ports: list[Identifier] = Field(default_factory=list)
    changed_tensors: list[Identifier] = Field(default_factory=list)
    changed_shapes: list[ShapeDelta] = Field(default_factory=list)
    changed_repeats: list[Identifier] = Field(default_factory=list)
    changed_sharing: list[Identifier] = Field(default_factory=list)
    evidence_anchor_changes: list[Identifier] = Field(default_factory=list)
    unresolved_changes: list[str] = Field(default_factory=list)


class FileChange(StrictModel):
    path: str = Field(min_length=1)
    kind: Literal["python", "json"]
    before_sha256: Sha256
    after_sha256: Sha256


class SourceTransaction(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    transaction_id: Identifier
    state: TransactionState
    state_history: list[TransactionState] = Field(default_factory=list)
    request: SemanticParameterPatch
    created_at: str = Field(min_length=1)
    workspace: str = Field(min_length=1)
    original_project_root: str = Field(min_length=1)
    temporary_project_root: str = Field(min_length=1)
    artifact_path: str = Field(min_length=1)
    source_snapshot_id: Identifier
    base_revision: str = Field(min_length=1)
    anchor_fingerprint: Sha256
    file_changes: list[FileChange] = Field(min_length=1)
    source_diff: str
    expected_delta: GraphDelta
    observed_delta: GraphDelta | None = None
    gates: list[GateResult] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    test_results: list[dict[str, Any]] = Field(default_factory=list)


class TransactionReceipt(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    transaction_id: Identifier
    state: TransactionState
    status: Literal["ok", "invalid", "failed"]
    gates: list[GateResult] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    source_writes: bool


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
    "runtime-input-spec-v1.schema.json": RuntimeInputSpec,
    "runtime-trace-v1.schema.json": RuntimeTrace,
    "runtime-capability-report-v1.schema.json": RuntimeCapabilityReport,
    "discrepancy-record-v1.schema.json": DiscrepancyRecord,
    "architecture-ir-v1.schema.json": ArchitectureIR,
    "publication-view-v1.schema.json": PublicationView,
    "visual-spec-v1.schema.json": VisualSpec,
    "visual-scene-v1.schema.json": VisualScene,
    "canvas-document-v1.schema.json": CanvasDocument,
    "semantic-parameter-patch-v1.schema.json": SemanticParameterPatch,
    "graph-delta-v1.schema.json": GraphDelta,
    "source-transaction-v1.schema.json": SourceTransaction,
    "transaction-receipt-v1.schema.json": TransactionReceipt,
    "command-receipt-v1.schema.json": CommandReceipt,
}
