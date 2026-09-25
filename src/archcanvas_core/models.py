from __future__ import annotations

from enum import Enum
from pathlib import PurePosixPath
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

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
        "uint32",
        "uint64",
        "bool",
    ] = "float32"
    generator: Literal["zeros", "ones", "normal", "uniform", "randint"] = "normal"
    low: float | int | None = None
    high: float | int | None = None

    @model_validator(mode="after")
    def generator_parameters_are_valid(self) -> RuntimeInput:
        if self.generator == "randint":
            if self.dtype not in {"int32", "int64", "uint32", "uint64"}:
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
    selected_target: str | None = None
    provider_options: dict[str, dict[str, str]] = Field(default_factory=dict)
    constructor_kwargs: dict[str, Any] = Field(default_factory=dict)
    forward_kwargs: dict[str, Any] = Field(default_factory=dict)
    static_args: dict[str, Any] = Field(default_factory=dict)
    runtime_state: dict[str, Any] = Field(default_factory=dict)
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
    requires_grad: bool | None = None
    trainable: bool | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def omit_legacy_optional_defaults(self, handler: Any) -> dict[str, Any]:
        data = handler(self)
        if self.trainable is None or self.trainable == self.requires_grad:
            data.pop("trainable", None)
        if not self.attributes:
            data.pop("attributes", None)
        return data


class RuntimeObservation(StrictModel):
    observation_id: Identifier
    sequence: int = Field(ge=0)
    module_path: str = Field(min_length=1)
    module_type: str = Field(min_length=1)
    input_tensors: list[RuntimeTensorObservation] = Field(default_factory=list)
    output_tensors: list[RuntimeTensorObservation] = Field(default_factory=list)
    matched_node_ids: list[Identifier] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


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
    adapter_id: Identifier = "runtime:pytorch-hooks-v1"
    framework: Literal["pytorch", "keras", "jax", "onnx"] = "pytorch"
    framework_version: str = Field(default="unknown", min_length=1)
    backend: str | None = None
    backend_version: str | None = None
    selected_target: str = Field(default="cpu", min_length=1)
    available_targets: list[dict[str, Any]] = Field(default_factory=list)
    observation_mechanism: str = Field(default="pytorch-hooks-v1", min_length=1)
    determinism_requested: bool = True
    determinism_achieved: bool = True
    determinism_limitations: list[str] = Field(default_factory=list)
    runtime_context: dict[str, Any] = Field(default_factory=dict)
    torch_version: str | None = None
    cuda_build: str | None = None
    cuda_available: bool = False
    selected_device: str | None = None
    deterministic_algorithms: bool | None = None


class RuntimeTrace(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    trace_id: Identifier
    architecture_id: Identifier
    source_snapshot_id: Identifier
    source_revision: str = Field(min_length=1)
    entrypoint: str = Field(min_length=3)
    adapter_id: Identifier = "runtime:pytorch-hooks-v1"
    framework: Literal["pytorch", "keras", "jax", "onnx"] = "pytorch"
    input_spec: RuntimeInputSpec
    input_spec_digest: Sha256
    replay_digest: Sha256
    params_digest: Sha256 | None = None
    state_digest: Sha256 | None = None
    checkpoint_digest: Sha256 | None = None
    observation_mechanism: str = Field(default="pytorch-hooks-v1", min_length=1)
    limitations: list[str] = Field(default_factory=list)
    observations: list[RuntimeObservation] = Field(min_length=1)
    output_tensors: list[RuntimeTensorObservation] = Field(default_factory=list)
    environment: RuntimeEnvironment
    isolation: RuntimeIsolation


class RuntimeCapabilityReport(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    adapter: str = Field(default="pytorch-hooks-v1", min_length=1)
    adapter_id: Identifier = "runtime:pytorch-hooks-v1"
    framework: Literal["pytorch", "keras", "jax", "onnx"] = "pytorch"
    framework_version: str | None = None
    backend: str | None = None
    backend_version: str | None = None
    runtime_available: bool
    torch_version: str | None = None
    cuda_build: str | None = None
    cuda_available: bool = False
    supported_devices: list[Literal["cpu", "cuda"]] = Field(default_factory=lambda: ["cpu"])
    available_targets: list[dict[str, Any]] = Field(default_factory=list)
    observation_mechanism: str = Field(default="pytorch-hooks-v1", min_length=1)
    shape_trace: bool = True
    dtype_trace: bool = True
    replay_check: bool = True
    isolation: RuntimeIsolation
    limitations: list[str] = Field(default_factory=list)


class FrameworkFormCapability(StrictModel):
    form_id: Identifier
    form_name: str = Field(min_length=1)
    static: Literal["verified", "experimental", "partial", "unavailable"]
    runtime: Literal["verified", "experimental", "partial", "unavailable"]
    parameter_transaction: Literal["verified", "experimental", "partial", "unavailable"]
    structural_transaction: Literal["verified", "experimental", "partial", "unavailable"]
    artifact_commit: Literal["verified", "experimental", "partial", "unavailable"]
    supported_targets: list[str] = Field(default_factory=list)
    verified_fixtures: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class FrameworkAdapterCapability(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    adapter_id: Identifier
    framework: Literal["pytorch", "keras", "jax", "onnx", "python"]
    adapter_version: str = Field(min_length=1)
    status: Literal["verified", "experimental", "partial", "unavailable", "supported"]
    static_analysis: bool
    runtime_evidence: bool
    source_transactions: bool
    parameter_transactions: bool = False
    structural_transactions: bool = False
    artifact_commit: bool = False
    capability_status: dict[str, Literal["verified", "experimental", "partial", "unavailable"]] = Field(
        default_factory=dict
    )
    supported_targets: list[str] = Field(default_factory=list)
    supported_forms: list[str] = Field(default_factory=list)
    verified_fixtures: list[str] = Field(default_factory=list)
    forms: list[FrameworkFormCapability] = Field(default_factory=list)
    required_packages: dict[str, str | None] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def form_ids_are_unique(self) -> FrameworkAdapterCapability:
        identifiers = [form.form_id for form in self.forms]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("framework form capability identifiers must be unique")
        return self


class HostSupport(StrictModel):
    host: Literal["codex-local", "claude-code-local", "claude-api", "claude.ai"]
    status: Literal["verified", "installer-tested", "unverified", "unsupported"]
    install_target: str | None = None
    limitations: list[str] = Field(default_factory=list)


class PlatformSupport(StrictModel):
    platform: Literal["linux", "macos", "windows"]
    status: Literal["verified", "ci-configured", "unverified"]
    limitations: list[str] = Field(default_factory=list)


class ReleaseSupportMatrix(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    release: str = Field(min_length=1)
    adapters: list[FrameworkAdapterCapability] = Field(min_length=1)
    hosts: list[HostSupport] = Field(min_length=1)
    platforms: list[PlatformSupport] = Field(min_length=1)
    offline_runtime_network_required: Literal[False] = False
    notes: list[str] = Field(default_factory=list)


class OfflineBundleFile(StrictModel):
    path: str = Field(min_length=1)
    sha256: Sha256
    size: int = Field(ge=0)


class OfflineBundleManifest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    bundle_id: Identifier
    architecture_id: Identifier
    source_snapshot_id: Identifier
    exact_ir_digest: Sha256
    source_execution: Literal[False] = False
    network_required: Literal[False] = False
    absolute_paths_redacted: bool
    files: list[OfflineBundleFile] = Field(min_length=1)


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


class VisualRelation(str, Enum):
    """Evidence-derived diagram grammar layered over canonical edge semantics."""

    SEQUENCE = "sequence"
    PARALLEL_BRANCH = "parallel-branch"
    MERGE = "merge"
    RESIDUAL = "residual"
    SHAPE_TRANSFORM = "shape-transform"
    MEMORY_REFERENCE = "memory-reference"
    CONDITION = "condition"
    ROUTING = "routing"
    STATE_UPDATE = "state-update"
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


class PatternDistribution(str, Enum):
    BUILTIN = "builtin"
    WORKSPACE = "workspace"
    SESSION_CANDIDATE = "session-candidate"


class PatternStage(str, Enum):
    STRUCTURE = "structure"
    DATAFLOW = "dataflow"
    SHAPE = "shape"
    SHARING_CONTROL = "sharing-control"
    WEAK_NAME = "weak-name"


class PatternPredicate(StrictModel):
    predicate_id: Identifier
    stage: PatternStage
    fact: Literal[
        "node-kind",
        "node-attribute",
        "edge-type",
        "edge-route",
        "shape-axis",
        "repeat-kind",
        "execution-predicate",
        "name-hint",
    ]
    operator: Literal["equals", "contains", "exists"] = "equals"
    field: str | None = None
    value: Any = None
    min_count: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def stage_matches_fact(self) -> PatternPredicate:
        allowed = {
            PatternStage.STRUCTURE: {"node-kind", "node-attribute"},
            PatternStage.DATAFLOW: {"edge-type", "edge-route"},
            PatternStage.SHAPE: {"shape-axis"},
            PatternStage.SHARING_CONTROL: {"repeat-kind", "execution-predicate"},
            PatternStage.WEAK_NAME: {"name-hint"},
        }
        if self.fact not in allowed[self.stage]:
            raise ValueError(f"{self.fact} is not valid in the {self.stage.value} stage")
        if self.fact == "node-attribute" and not self.field:
            raise ValueError("node-attribute predicates require a field")
        if self.operator != "exists" and self.value is None:
            raise ValueError("non-existence predicates require a value")
        return self


class PatternScore(StrictModel):
    required_weight: float = Field(default=0.7, ge=0, le=1)
    optional_weight: float = Field(default=0.25, ge=0, le=1)
    weak_name_weight: float = Field(default=0.05, ge=0, le=1)
    minimum: float = Field(default=0.7, ge=0, le=1)

    @model_validator(mode="after")
    def weights_fit(self) -> PatternScore:
        if self.required_weight + self.optional_weight + self.weak_name_weight > 1.000001:
            raise ValueError("pattern score weights cannot exceed 1")
        return self


class PatternAnnotationRule(StrictModel):
    rule_id: Identifier
    selector: PatternPredicate
    semantic_role: str = Field(min_length=1)
    group_id: Identifier | None = None
    recommended_depth: int | None = Field(default=None, ge=0)
    glyph: str | None = None
    layout_family: str | None = None
    label: str | None = None

    @model_validator(mode="after")
    def selector_is_not_a_name_hint(self) -> PatternAnnotationRule:
        if self.selector.stage is PatternStage.WEAK_NAME:
            raise ValueError("annotation selectors cannot rely on weak names")
        return self


class PatternTestInventory(StrictModel):
    positive: list[str] = Field(min_length=1)
    negative: list[str] = Field(min_length=1)
    mutation: list[str] = Field(min_length=1)
    digest_invariance: list[str] = Field(min_length=1)


class PatternPackManifest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    pack_id: Identifier
    version: str = Field(min_length=1)
    authors: list[str] = Field(min_length=1)
    license: str = Field(min_length=1)
    pack_digest: Sha256
    distribution: PatternDistribution
    supported_ir_versions: list[str] = Field(min_length=1)
    supported_adapter_versions: list[str] = Field(min_length=1)
    required: list[PatternPredicate] = Field(min_length=1)
    optional: list[PatternPredicate] = Field(default_factory=list)
    forbidden: list[PatternPredicate] = Field(default_factory=list)
    score: PatternScore = Field(default_factory=PatternScore)
    ambiguity_policy: Literal["generic"] = "generic"
    fallback_policy: Literal["generic"] = "generic"
    known_limitations: list[str] = Field(default_factory=list)
    annotations: list[PatternAnnotationRule] = Field(default_factory=list)
    tests: PatternTestInventory

    @model_validator(mode="after")
    def weak_hints_are_optional(self) -> PatternPackManifest:
        if any(item.stage is PatternStage.WEAK_NAME for item in self.required):
            raise ValueError("weak name hints cannot be required predicates")
        return self


class SemanticAnnotation(StrictModel):
    annotation_id: Identifier
    pack_id: Identifier
    canonical_node_ids: list[Identifier] = Field(min_length=1)
    semantic_role: str = Field(min_length=1)
    group_id: Identifier | None = None
    recommended_depth: int | None = Field(default=None, ge=0)
    glyph: str | None = None
    layout_family: str | None = None
    label: str | None = None
    predicate_ids: list[Identifier] = Field(min_length=1)


class SemanticAnnotationOverlay(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    architecture_id: Identifier
    exact_ir_digest: Sha256
    status: Literal["disabled", "generic", "matched", "ambiguous"]
    applied_pack_ids: list[Identifier] = Field(default_factory=list)
    annotations: list[SemanticAnnotation] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class PatternPackLoad(StrictModel):
    pack_id: Identifier
    version: str = Field(min_length=1)
    digest: Sha256
    distribution: PatternDistribution
    source: str = Field(min_length=1)
    locked: bool


class PatternMatch(StrictModel):
    pack_id: Identifier
    distribution: PatternDistribution
    status: Literal["matched", "rejected", "ambiguous", "candidate-match"]
    score: float = Field(ge=0, le=1)
    matched_predicate_ids: list[Identifier] = Field(default_factory=list)
    matched_canonical_ids: list[Identifier] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class PatternPackReceipt(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    architecture_id: Identifier
    status: Literal["disabled", "generic", "matched", "ambiguous"]
    source_execution: Literal[False] = False
    loaded_packs: list[PatternPackLoad] = Field(default_factory=list)
    matches: list[PatternMatch] = Field(default_factory=list)
    selected_pack_ids: list[Identifier] = Field(default_factory=list)
    exact_ir_digest_before: Sha256
    exact_ir_digest_after: Sha256

    @model_validator(mode="after")
    def exact_ir_is_invariant(self) -> PatternPackReceipt:
        if self.exact_ir_digest_before != self.exact_ir_digest_after:
            raise ValueError("Pattern Pack application changed the Exact IR digest")
        return self


class PatternCandidateReview(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    pack_id: Identifier
    status: Literal["preview-only"] = "preview-only"
    match_status: Literal["candidate-match", "rejected"]
    match_basis: list[Identifier] = Field(default_factory=list)
    unproven_predicates: list[Identifier] = Field(default_factory=list)
    counterexample_risks: list[str] = Field(default_factory=list)
    preview_annotations: list[SemanticAnnotation] = Field(default_factory=list)
    exact_ir_digest_before: Sha256
    exact_ir_digest_after: Sha256
    activated: Literal[False] = False
    permissions: dict[Literal["shell", "network", "source_write"], bool] = Field(
        default_factory=lambda: {"shell": False, "network": False, "source_write": False}
    )

    @model_validator(mode="after")
    def remains_a_preview(self) -> PatternCandidateReview:
        if self.exact_ir_digest_before != self.exact_ir_digest_after:
            raise ValueError("candidate preview changed the Exact IR digest")
        if set(self.permissions) != {"shell", "network", "source_write"} or any(
            self.permissions.values()
        ):
            raise ValueError("candidate review cannot grant permissions")
        return self


class PublicationNode(StrictModel):
    view_node_id: Identifier
    canonical_node_ids: list[Identifier] = Field(default_factory=list)
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
    visual_relation: VisualRelation = VisualRelation.SEQUENCE
    symbolic_shape: str = Field(min_length=1)
    evidence_ids: list[Identifier] = Field(default_factory=list)


class PublicationHierarchyNode(StrictModel):
    hierarchy_node_id: Identifier
    parent_hierarchy_node_id: Identifier | None = None
    semantic_name: str = Field(min_length=1)
    kind: NodeKind
    depth: int = Field(ge=0)
    canonical_node_ids: list[Identifier] = Field(default_factory=list)
    evidence_ids: list[Identifier] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class PublicationHierarchy(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    hierarchy_id: Identifier
    architecture_id: Identifier
    root_node_id: Identifier
    nodes: list[PublicationHierarchyNode] = Field(min_length=1)
    max_depth: int = Field(ge=0)
    canonical_node_ids: list[Identifier] = Field(min_length=1)
    canonical_edge_ids: list[Identifier] = Field(default_factory=list)
    canonical_tensor_ids: list[Identifier] = Field(default_factory=list)
    canonical_port_ids: list[Identifier] = Field(default_factory=list)

    @model_validator(mode="after")
    def containment_is_well_formed(self) -> PublicationHierarchy:
        by_id = {node.hierarchy_node_id: node for node in self.nodes}
        if len(by_id) != len(self.nodes):
            raise ValueError("publication hierarchy node identifiers must be unique")
        root = by_id.get(self.root_node_id)
        if root is None or root.parent_hierarchy_node_id is not None or root.depth != 0:
            raise ValueError("publication hierarchy root is missing or invalid")
        canonical_ids = [
            canonical_id for node in self.nodes for canonical_id in node.canonical_node_ids
        ]
        if len(canonical_ids) != len(set(canonical_ids)) or set(canonical_ids) != set(
            self.canonical_node_ids
        ):
            raise ValueError("publication hierarchy must own every canonical node exactly once")
        for node in self.nodes:
            if node.hierarchy_node_id == self.root_node_id:
                continue
            parent = by_id.get(node.parent_hierarchy_node_id or "")
            if parent is None:
                raise ValueError("publication hierarchy references a missing parent")
            if node.depth != parent.depth + 1:
                raise ValueError("publication hierarchy depth does not match containment")
            visited = {node.hierarchy_node_id}
            cursor = parent
            while cursor.parent_hierarchy_node_id is not None:
                if cursor.hierarchy_node_id in visited:
                    raise ValueError("publication hierarchy contains a cycle")
                visited.add(cursor.hierarchy_node_id)
                cursor = by_id.get(cursor.parent_hierarchy_node_id)
                if cursor is None:
                    raise ValueError("publication hierarchy references a missing ancestor")
        if self.max_depth != max(node.depth for node in self.nodes):
            raise ValueError("publication hierarchy max_depth is stale")
        return self


class PublicationView(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    view_id: Identifier
    architecture_id: Identifier
    hierarchy_id: Identifier
    projection_id: Identifier
    frontier_digest: Sha256
    expanded_node_ids: list[Identifier] = Field(default_factory=list)
    visible_depth: int = Field(ge=0)
    max_depth: int = Field(ge=0)
    fully_expanded: bool = False
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
    glyph: Literal[
        "container",
        "operator",
        "tensor",
        "merge",
        "io",
        "state",
        "opaque",
        "projection",
        "activation",
        "normalization",
        "attention",
        "transform",
        "condition",
        "repeat",
    ]
    fill: str = Field(min_length=1)
    stroke: str = Field(min_length=1)
    label: str = Field(min_length=1)
    secondary_label: str | None = None


class VisualEdgeStyle(StrictModel):
    view_edge_id: Identifier
    visual_relation: VisualRelation = VisualRelation.SEQUENCE
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
    canonical_node_ids: list[Identifier] = Field(default_factory=list)
    bounds: SceneRect
    shape: Literal[
        "container",
        "rect",
        "tensor",
        "merge",
        "io",
        "state",
        "opaque",
        "projection",
        "activation",
        "normalization",
        "attention",
        "transform",
        "condition",
        "repeat",
    ]
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
    visual_relation: VisualRelation = VisualRelation.SEQUENCE
    stroke: str = Field(min_length=1)
    dash: str | None = None
    width: float = Field(gt=0)
    label: str = Field(min_length=1)


class SceneAnnotation(StrictModel):
    annotation_id: Identifier
    text: str = Field(min_length=1, max_length=500)
    bounds: SceneRect
    fill: str = Field(default="#fff8c5", min_length=1)
    stroke: str = Field(default="#8a6d1d", min_length=1)


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
    caption: str | None = None
    legend_placement: Literal[
        "top-left",
        "top-right",
        "bottom-left",
        "bottom-right",
        "hidden",
    ] | None = None
    annotations: list[SceneAnnotation] = Field(default_factory=list)


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


class PatchBatch(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    batch_id: Identifier
    description: str = Field(min_length=1)
    patches: list[VisualPatch] = Field(min_length=1)

    @model_validator(mode="after")
    def patch_ids_are_unique(self) -> PatchBatch:
        patch_ids = [patch.patch_id for patch in self.patches]
        if len(patch_ids) != len(set(patch_ids)):
            raise ValueError("patch identifiers must be unique within a batch")
        return self


class CanvasDocument(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    document_id: Identifier
    source_snapshot_id: Identifier
    architecture_id: Identifier
    source_digest: Sha256
    base_hierarchy_id: Identifier | None = None
    visual_patches: list[VisualPatch] = Field(default_factory=list)
    redo_patches: list[VisualPatch] = Field(default_factory=list)
    view_state: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def migrate_fixed_scene_binding(cls, value: Any) -> Any:
        if isinstance(value, dict) and "base_scene_ids" in value:
            migrated = dict(value)
            migrated.pop("base_scene_ids", None)
            migrated.setdefault("base_hierarchy_id", None)
            return migrated
        return value

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


class SemanticStructuralPatch(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    patch_id: Identifier
    operation: Literal["replace_activation", "insert_layer_norm"]
    artifact_path: str = Field(min_length=1)
    target_node_id: Identifier
    parameters: dict[str, Any] = Field(default_factory=dict)
    targeted_tests: list[list[str]] = Field(default_factory=list)
    runtime_input_spec: str | None = None

    @model_validator(mode="after")
    def commands_are_nonempty(self) -> SemanticStructuralPatch:
        if any(not command or any(not argument for argument in command) for command in self.targeted_tests):
            raise ValueError("targeted test commands must contain non-empty arguments")
        if self.operation == "replace_activation":
            if set(self.parameters) != {"replacement"} or self.parameters["replacement"] not in {
                "GELU",
                "ReLU",
                "SiLU",
            }:
                raise ValueError("replace_activation requires exactly one GELU/ReLU/SiLU replacement")
        elif set(self.parameters) != {"module_name", "normalized_shape"}:
            raise ValueError(
                "insert_layer_norm requires exactly module_name and normalized_shape parameters"
            )
        return self


class FreeformSourceBufferPatch(StrictModel):
    path: str = Field(min_length=1)
    base_sha256: Sha256
    content: str

    @model_validator(mode="after")
    def path_is_snapshot_relative(self) -> FreeformSourceBufferPatch:
        path = PurePosixPath(self.path)
        if path.is_absolute() or ".." in path.parts or "." in path.parts:
            raise ValueError("source buffer path must be normalized and project-relative")
        return self


class FreeformSourcePatch(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    patch_id: Identifier
    operation: Literal["edit_source_buffers"] = "edit_source_buffers"
    artifact_path: str = Field(min_length=1)
    buffers: list[FreeformSourceBufferPatch] = Field(min_length=1)
    targeted_tests: list[list[str]] = Field(default_factory=list)
    runtime_input_spec: str | None = None

    @model_validator(mode="after")
    def buffers_and_commands_are_well_formed(self) -> FreeformSourcePatch:
        paths = [buffer.path for buffer in self.buffers]
        if len(paths) != len(set(paths)):
            raise ValueError("freeform source buffer paths must be unique")
        if any(
            not command or any(not argument for argument in command)
            for command in self.targeted_tests
        ):
            raise ValueError("targeted test commands must contain non-empty arguments")
        return self


class StagedSourceBuffer(StrictModel):
    path: str = Field(min_length=1)
    base_sha256: Sha256
    base_content: str
    staged_content: str

    @model_validator(mode="after")
    def path_is_snapshot_relative(self) -> StagedSourceBuffer:
        path = PurePosixPath(self.path)
        if path.is_absolute() or ".." in path.parts or "." in path.parts:
            raise ValueError("staged source path must be normalized and project-relative")
        return self


class SourceWorkspaceDocument(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    workspace_id: Identifier
    source_snapshot_id: Identifier
    base_revision: str = Field(min_length=1)
    revision: int = Field(ge=0)
    buffers: list[StagedSourceBuffer] = Field(default_factory=list)

    @model_validator(mode="after")
    def identity_and_paths_are_well_formed(self) -> SourceWorkspaceDocument:
        if not self.workspace_id.startswith("source-workspace:"):
            raise ValueError("source workspace identifiers must use the source-workspace: prefix")
        paths = [buffer.path for buffer in self.buffers]
        if len(paths) != len(set(paths)):
            raise ValueError("staged source buffer paths must be unique")
        return self


class ProposedConnection(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    proposal_id: Identifier
    kind: Literal["proposed_connection"] = "proposed_connection"
    artifact_path: str = Field(min_length=1)
    source_node_id: Identifier
    source_port_id: Identifier
    target_node_id: Identifier
    target_port_id: Identifier
    role: str = Field(default="main", min_length=1)


class AgentProposal(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    proposal_id: Identifier
    kind: Literal["agent_proposal"] = "agent_proposal"
    status: Literal["handoff-required"] = "handoff-required"
    reason_code: Literal[
        "UNSUPPORTED_CONNECTION_TRANSFORM",
        "INCOMPATIBLE_PORTS",
        "UNRESOLVED_TENSOR_COMPATIBILITY",
        "UNSUPPORTED_STRUCTURAL_INTENT",
    ]
    summary: str = Field(min_length=1)
    requested_intent: dict[str, Any]
    source_context: dict[str, Any] = Field(default_factory=dict)
    permissions: dict[Literal["shell", "network", "source_write"], bool] = Field(
        default_factory=lambda: {"shell": False, "network": False, "source_write": False}
    )

    @model_validator(mode="after")
    def grants_no_permissions(self) -> AgentProposal:
        if set(self.permissions) != {"shell", "network", "source_write"} or any(
            self.permissions.values()
        ):
            raise ValueError("AgentProposal cannot grant shell, network, or source-write permission")
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


class FactDelta(StrictModel):
    subject_id: Identifier
    kind: Literal[
        "node",
        "edge",
        "tensor",
        "port",
        "fanout",
        "repeat",
        "config-predicate",
        "evidence",
        "unresolved",
    ]
    before_sha256: Sha256 | None = None
    after_sha256: Sha256 | None = None

    @model_validator(mode="after")
    def contains_a_change(self) -> FactDelta:
        if self.before_sha256 == self.after_sha256:
            raise ValueError("fact delta must change, add, or remove content")
        return self


class GraphDelta(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    added_nodes: list[Identifier] = Field(default_factory=list)
    removed_nodes: list[Identifier] = Field(default_factory=list)
    changed_nodes: list[Identifier] = Field(default_factory=list)
    added_edges: list[Identifier] = Field(default_factory=list)
    removed_edges: list[Identifier] = Field(default_factory=list)
    changed_edges: list[Identifier] = Field(default_factory=list)
    changed_parameters: list[ParameterDelta] = Field(default_factory=list)
    added_ports: list[Identifier] = Field(default_factory=list)
    removed_ports: list[Identifier] = Field(default_factory=list)
    changed_ports: list[Identifier] = Field(default_factory=list)
    added_tensors: list[Identifier] = Field(default_factory=list)
    removed_tensors: list[Identifier] = Field(default_factory=list)
    changed_tensors: list[Identifier] = Field(default_factory=list)
    changed_shapes: list[ShapeDelta] = Field(default_factory=list)
    added_fanouts: list[Identifier] = Field(default_factory=list)
    removed_fanouts: list[Identifier] = Field(default_factory=list)
    changed_fanouts: list[Identifier] = Field(default_factory=list)
    changed_repeats: list[Identifier] = Field(default_factory=list)
    added_config_predicates: list[Identifier] = Field(default_factory=list)
    removed_config_predicates: list[Identifier] = Field(default_factory=list)
    changed_config_predicates: list[Identifier] = Field(default_factory=list)
    changed_sharing: list[Identifier] = Field(default_factory=list)
    evidence_anchor_changes: list[Identifier] = Field(default_factory=list)
    unresolved_changes: list[str] = Field(default_factory=list)
    fact_changes: list[FactDelta] = Field(default_factory=list)


class FileChange(StrictModel):
    path: str = Field(min_length=1)
    kind: Literal["python", "json", "onnx", "binary"]
    before_sha256: Sha256
    after_sha256: Sha256


class SourceTransaction(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    transaction_id: Identifier
    framework: Literal["pytorch", "keras", "jax", "onnx"] = "pytorch"
    transaction_adapter_id: Identifier = "transaction:pytorch-source-v1"
    adapter_version: str = "0.1.0"
    artifact_kind: Literal["source-artifact", "model-artifact"] = "source-artifact"
    validators: list[str] = Field(default_factory=list)
    reanalysis_route: str = "analyze_with_adapter"
    state: TransactionState
    state_history: list[TransactionState] = Field(default_factory=list)
    request: SemanticParameterPatch | SemanticStructuralPatch | FreeformSourcePatch
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
    framework: Literal["pytorch", "keras", "jax", "onnx"] = "pytorch"
    transaction_adapter_id: Identifier = "transaction:pytorch-source-v1"
    artifact_kind: Literal["source-artifact", "model-artifact"] = "source-artifact"
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


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STALE = "stale"


class ProjectSession(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    project_id: Identifier
    root: str = Field(min_length=1)
    generation: int = Field(ge=1)
    entrypoint: str | None = None
    framework: str = "auto"
    task: str = "inference"
    config_path: str | None = None
    config_digest: Sha256
    execution_policy: Literal["static-only", "runtime-opt-in"] = "static-only"
    environment_path: str | None = None
    python_executable: str | None = None
    workspace: str = Field(min_length=1)
    opened_at: str = Field(min_length=1)


class AnalysisRequest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    project_id: Identifier
    project_generation: int = Field(ge=1)
    entrypoint: str = Field(min_length=1)
    framework: str = "auto"
    task: str = "inference"
    config_path: str | None = None
    execution_mode: Literal["static", "runtime"] = "static"
    pattern_packs_enabled: bool = True
    request_id: Identifier


class AnalysisJob(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    job_id: Identifier
    project_id: Identifier
    generation: int = Field(ge=1)
    input_fingerprint: Sha256
    profile: str = Field(min_length=1)
    state: JobState
    progress: float = Field(ge=0, le=1)
    started_at: str | None = None
    finished_at: str | None = None
    receipt: dict[str, Any] | None = None
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class DraftPort(StrictModel):
    port_id: Identifier
    name: str = Field(min_length=1)
    direction: Literal["input", "output"]
    role: str = Field(min_length=1)
    shape_constraint: str | None = None
    dtype: str | None = None

    @model_validator(mode="after")
    def uses_draft_identity(self) -> DraftPort:
        if not self.port_id.startswith("draft:"):
            raise ValueError("draft port identifiers must use the draft: prefix")
        return self


class DraftNode(StrictModel):
    node_id: Identifier
    semantic_name: str = Field(min_length=1)
    framework: str = Field(min_length=1)
    node_type: str = Field(min_length=1)
    parent_id: Identifier | None = None
    source_anchor: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    ports: list[DraftPort] = Field(default_factory=list)

    @model_validator(mode="after")
    def uses_draft_identity(self) -> DraftNode:
        if not self.node_id.startswith("draft:"):
            raise ValueError("draft node identifiers must use the draft: prefix")
        return self


class DraftEdge(StrictModel):
    edge_id: Identifier
    source_port_id: Identifier
    target_port_id: Identifier
    policy: Literal["replace-input", "add-residual", "concat", "fanout", "disconnect"]
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def uses_draft_identity(self) -> DraftEdge:
        if not self.edge_id.startswith("draft:"):
            raise ValueError("draft edge identifiers must use the draft: prefix")
        return self


EditIntentKind = Literal[
    "create-node",
    "delete-node",
    "connect-ports",
    "disconnect-edge",
    "replace-node",
    "set-parameter",
    "edit-source-buffer",
    "edit-onnx-initializer",
    "edit-onnx-attribute",
]


class EditIntent(StrictModel):
    intent_id: Identifier
    kind: EditIntentKind
    target_ids: list[Identifier] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    expected_delta: GraphDelta | None = None
    user_input: dict[str, Any] = Field(default_factory=dict)
    capability_requirement: str = Field(min_length=1)

    @model_validator(mode="after")
    def uses_intent_identity(self) -> EditIntent:
        if not self.intent_id.startswith("intent:"):
            raise ValueError("edit intent identifiers must use the intent: prefix")
        return self


class EditProofState(str, Enum):
    CHECKING = "checking"
    CONDITIONAL = "conditional"
    UNPROVEN = "unproven"
    INVALID = "invalid"
    STALE = "stale"
    PROVEN = "proven"
    REVIEW_READY = "review-ready"


class EditProofStatus(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    intent_id: Identifier
    status: EditProofState
    writeback_eligibility: Literal["blocked", "prepare", "commit"]
    reason_codes: list[str] = Field(default_factory=list)
    message: str = Field(min_length=1)
    affected_subject_ids: list[Identifier] = Field(default_factory=list)
    required_facts: list[str] = Field(default_factory=list)
    supported_fixes: list[str] = Field(default_factory=list)
    checked_generation: int = Field(ge=1)
    input_fingerprint: Sha256

    @model_validator(mode="after")
    def eligibility_matches_status(self) -> EditProofStatus:
        expected = {
            EditProofState.PROVEN: "prepare",
            EditProofState.REVIEW_READY: "commit",
        }.get(self.status, "blocked")
        if self.writeback_eligibility != expected:
            raise ValueError("proof status and writeback eligibility disagree")
        return self


class WritebackSummary(StrictModel):
    eligibility: Literal["blocked", "prepare", "commit"] = "blocked"
    blocking_intent_ids: list[Identifier] = Field(default_factory=list)


class DraftGraphDocument(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    draft_id: Identifier
    base_architecture_id: Identifier
    base_source_digest: Sha256
    revision: int = Field(ge=0)
    nodes: list[DraftNode] = Field(default_factory=list)
    edges: list[DraftEdge] = Field(default_factory=list)
    intents: list[EditIntent] = Field(default_factory=list)
    proofs: list[EditProofStatus] = Field(default_factory=list)
    lowering_status: Literal["not-planned", "checking", "planned", "blocked"] = "not-planned"
    writeback_summary: WritebackSummary = Field(default_factory=WritebackSummary)

    @model_validator(mode="after")
    def identities_and_summary_are_consistent(self) -> DraftGraphDocument:
        if not self.draft_id.startswith("draft:"):
            raise ValueError("draft document identifiers must use the draft: prefix")
        groups = (self.nodes, self.edges, self.intents)
        identifiers = [
            item.node_id if isinstance(item, DraftNode)
            else item.edge_id if isinstance(item, DraftEdge)
            else item.intent_id
            for group in groups
            for item in group
        ]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("draft document identifiers must be unique")
        intent_ids = {intent.intent_id for intent in self.intents}
        if any(proof.intent_id not in intent_ids for proof in self.proofs):
            raise ValueError("proof status references an unknown edit intent")
        if any(item not in intent_ids for item in self.writeback_summary.blocking_intent_ids):
            raise ValueError("writeback summary references an unknown edit intent")
        return self


class EditableCapability(StrictModel):
    id: str = Field(min_length=1)
    plane: Literal["visual", "draft", "source"]
    control: str | None = None
    status: Literal["available", "conditional", "unavailable"]
    preconditions: list[str] = Field(default_factory=list)


class EditableCapabilityManifest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    subject_id: Identifier
    capabilities: list[EditableCapability] = Field(default_factory=list)


class SearchSubject(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    id: Identifier
    kind: Literal[
        "node", "tensor", "edge", "port", "evidence", "source", "diagnostic", "transaction"
    ]
    canonical_ids: list[Identifier] = Field(default_factory=list)
    title: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    tokens: list[str] = Field(default_factory=list)
    source_spans: list[dict[str, Any]] = Field(default_factory=list)
    view_bindings: list[dict[str, str]] = Field(default_factory=list)
    runtime_bindings: list[Identifier] = Field(default_factory=list)
    facets: dict[str, str] = Field(default_factory=dict)


class ValidationGateResult(StrictModel):
    gate: str = Field(min_length=1)
    status: Literal["passed", "failed", "skipped", "unsupported", "cancelled"]
    message: str = Field(min_length=1)
    target_ids: list[Identifier] = Field(default_factory=list)


class ValidationRun(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    validation_id: Identifier
    profile: Literal["fast-static", "publication", "full", "runtime-replay"]
    input_fingerprint: Sha256
    generation: int = Field(ge=1)
    state: JobState
    gate_results: list[ValidationGateResult] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    supported_fixes: list[str] = Field(default_factory=list)
    coverage: dict[str, float] = Field(default_factory=dict)
    runtime_execution_authorized: bool = False
    started_at: str | None = None
    finished_at: str | None = None

    @model_validator(mode="after")
    def runtime_requires_authorization(self) -> ValidationRun:
        if self.profile == "runtime-replay" and not self.runtime_execution_authorized:
            raise ValueError("runtime replay requires explicit execution authorization")
        return self


class ArtifactEntry(StrictModel):
    logical_path: str = Field(min_length=1)
    size: int = Field(ge=0)
    sha256: Sha256
    role: Literal["model", "external-data", "manifest"]

    @model_validator(mode="after")
    def path_is_relative_and_confined(self) -> ArtifactEntry:
        normalized = self.logical_path.replace("\\", "/")
        if normalized.startswith("/") or ".." in normalized.split("/") or "\x00" in normalized:
            raise ValueError("artifact paths must be safe relative paths")
        return self


class ArtifactSet(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    artifact_set_id: Identifier
    root: str = Field(min_length=1)
    set_digest: Sha256
    entries: list[ArtifactEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def logical_paths_are_unique(self) -> ArtifactSet:
        paths = [entry.logical_path for entry in self.entries]
        if len(paths) != len(set(paths)):
            raise ValueError("artifact logical paths must be unique")
        if not any(entry.role == "model" for entry in self.entries):
            raise ValueError("artifact set requires a model entry")
        return self


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
    "framework-adapter-capability-v1.schema.json": FrameworkAdapterCapability,
    "release-support-matrix-v1.schema.json": ReleaseSupportMatrix,
    "offline-bundle-manifest-v1.schema.json": OfflineBundleManifest,
    "discrepancy-record-v1.schema.json": DiscrepancyRecord,
    "architecture-ir-v1.schema.json": ArchitectureIR,
    "pattern-pack-manifest-v1.schema.json": PatternPackManifest,
    "semantic-annotation-overlay-v1.schema.json": SemanticAnnotationOverlay,
    "pattern-pack-receipt-v1.schema.json": PatternPackReceipt,
    "pattern-candidate-review-v1.schema.json": PatternCandidateReview,
    "publication-hierarchy-v1.schema.json": PublicationHierarchy,
    "publication-view-v1.schema.json": PublicationView,
    "visual-spec-v1.schema.json": VisualSpec,
    "visual-scene-v1.schema.json": VisualScene,
    "canvas-document-v1.schema.json": CanvasDocument,
    "patch-batch-v1.schema.json": PatchBatch,
    "semantic-parameter-patch-v1.schema.json": SemanticParameterPatch,
    "semantic-structural-patch-v1.schema.json": SemanticStructuralPatch,
    "proposed-connection-v1.schema.json": ProposedConnection,
    "agent-proposal-v1.schema.json": AgentProposal,
    "graph-delta-v1.schema.json": GraphDelta,
    "source-transaction-v1.schema.json": SourceTransaction,
    "transaction-receipt-v1.schema.json": TransactionReceipt,
    "command-receipt-v1.schema.json": CommandReceipt,
    "project-session-v1.schema.json": ProjectSession,
    "analysis-job-v1.schema.json": AnalysisJob,
    "draft-graph-document-v1.schema.json": DraftGraphDocument,
    "edit-proof-status-v1.schema.json": EditProofStatus,
    "search-subject-v1.schema.json": SearchSubject,
    "validation-run-v1.schema.json": ValidationRun,
    "artifact-set-v1.schema.json": ArtifactSet,
}
