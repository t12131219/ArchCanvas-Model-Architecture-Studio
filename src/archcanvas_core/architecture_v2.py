from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from .digest_protocol import domain_digest
from .models import Confidence, Diagnostic, Identifier, RepeatKind, Sha256, StrictModel
from .module_contract import DefinitionRef
from .source_v2 import SourceAnchor

SEMANTIC_GRAPH_DIGEST_DOMAIN = "archcanvas:python-semantic-graph:v2"
EXACT_IR_DIGEST_DOMAIN = "archcanvas:exact-architecture-ir:v2"


class SemanticDefinition(StrictModel):
    definition_id: Identifier
    qualified_name: str = Field(min_length=1)
    kind: Literal["class", "function", "method", "registry"]
    anchor: SourceAnchor | None = None


class ConstructorArgument(StrictModel):
    parameter_name: str = Field(min_length=1)
    source_expression: str = Field(min_length=1)
    value: Any = None
    anchor: SourceAnchor


class ModuleInstance(StrictModel):
    instance_id: Identifier
    instance_path: str = Field(min_length=1)
    parent_instance_id: Identifier | None = None
    local_definition_id: Identifier | None = None
    definition_ref: DefinitionRef | None = None
    constructor_arguments: list[ConstructorArgument] = Field(default_factory=list)
    anchor: SourceAnchor

    @model_validator(mode="after")
    def exactly_one_definition(self) -> ModuleInstance:
        if (self.local_definition_id is None) == (self.definition_ref is None):
            raise ValueError("module instance requires exactly one definition binding")
        return self


class SemanticValue(StrictModel):
    value_id: Identifier
    semantic_name: str = Field(min_length=1)
    producer_call_id: Identifier | None = None
    producer_port_id: Identifier | None = None
    consumer_call_ids: list[Identifier] = Field(default_factory=list)
    anchor: SourceAnchor


class CallArgumentBinding(StrictModel):
    port_id: Identifier
    value_id: Identifier
    argument_name: str = Field(min_length=1)
    argument_kind: Literal["positional", "keyword", "implicit"]
    ordinal: int = Field(ge=0)
    anchor: SourceAnchor


class CallOutputBinding(StrictModel):
    port_id: Identifier
    value_id: Identifier
    ordinal: int = Field(ge=0)


class ArchitectureCall(StrictModel):
    call_id: Identifier
    instance_id: Identifier | None = None
    local_definition_id: Identifier | None = None
    definition_ref: DefinitionRef | None = None
    parent_module_id: Identifier
    input_bindings: list[CallArgumentBinding] = Field(default_factory=list)
    output_bindings: list[CallOutputBinding] = Field(default_factory=list)
    control_region_id: Identifier
    anchor: SourceAnchor
    confidence: Confidence

    @model_validator(mode="after")
    def has_a_definition(self) -> ArchitectureCall:
        if self.local_definition_id is None and self.definition_ref is None:
            raise ValueError("architecture call requires a local or registry definition")
        return self


class ControlRegion(StrictModel):
    control_region_id: Identifier
    kind: Literal["function", "conditional", "loop", "opaque"]
    owner_definition_id: Identifier
    parent_region_id: Identifier | None = None
    anchor: SourceAnchor


class ParameterGroup(StrictModel):
    parameter_group_id: Identifier
    owner_instance_id: Identifier
    member_instance_ids: list[Identifier] = Field(default_factory=list)
    call_ids: list[Identifier] = Field(default_factory=list)
    binding_kind: Literal["instance", "tied"] = "instance"
    shared_attribute: str | None = None
    anchor: SourceAnchor

    @model_validator(mode="before")
    @classmethod
    def populate_members(cls, value: Any) -> Any:
        if isinstance(value, dict) and not value.get("member_instance_ids") and value.get("owner_instance_id"):
            return {**value, "member_instance_ids": [value["owner_instance_id"]]}
        return value

    @model_validator(mode="after")
    def members_are_valid(self) -> ParameterGroup:
        members = self.member_instance_ids
        if self.owner_instance_id not in members:
            raise ValueError("parameter group owner must be one of its members")
        if len(members) != len(set(members)) or len(self.call_ids) != len(set(self.call_ids)):
            raise ValueError("parameter group members and calls must be unique")
        if self.binding_kind == "tied" and len(members) < 2:
            raise ValueError("tied parameter groups require at least two member instances")
        return self


class SemanticRepeat(StrictModel):
    repeat_id: Identifier
    kind: RepeatKind = RepeatKind.STACK
    owner_instance_id: Identifier
    container_instance_id: Identifier
    body_call_ids: list[Identifier] = Field(default_factory=list)
    count: int | None = Field(default=None, ge=1)
    count_symbol: str | None = None
    parameter_identity: str = Field(min_length=1)
    anchor: SourceAnchor

    @model_validator(mode="after")
    def one_count_form(self) -> SemanticRepeat:
        if (self.count is None) == (self.count_symbol is None):
            raise ValueError("semantic repeat requires exactly one of count or count_symbol")
        if len(self.body_call_ids) != len(set(self.body_call_ids)):
            raise ValueError("semantic repeat body calls must be unique")
        return self


class SourceEvidenceV2(StrictModel):
    evidence_id: Identifier
    source_corpus_digest: Sha256
    anchor: SourceAnchor
    claim: str = Field(min_length=1)
    confidence: Confidence


class PatternBindingV2(StrictModel):
    binding_id: Identifier
    pack_id: Identifier
    pack_digest: Sha256
    pattern_id: Identifier
    fidelity: Literal["exact", "schematic", "opaque"]
    subject_ids: list[Identifier] = Field(default_factory=list)
    template_id: Identifier | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    slot_bindings: dict[str, list[Identifier]] = Field(default_factory=dict)
    evidence_ids: list[Identifier] = Field(default_factory=list)

    @model_validator(mode="after")
    def references_are_unique(self) -> PatternBindingV2:
        if len(self.subject_ids) != len(set(self.subject_ids)):
            raise ValueError("pattern binding subjects must be unique")
        if any(len(values) != len(set(values)) for values in self.slot_bindings.values()):
            raise ValueError("pattern slot bindings must be unique")
        return self


def semantic_graph_payload(graph: PythonSemanticGraph) -> dict[str, object]:
    data = graph.model_dump(mode="json", exclude={"semantic_graph_digest"})
    for key in (
        "definitions",
        "instances",
        "calls",
        "values",
        "control_regions",
        "parameter_groups",
        "repeats",
        "evidence",
        "diagnostics",
        "pattern_bindings",
    ):
        data[key] = sorted(data[key], key=lambda item: tuple(str(value) for value in item.values()))
    return data


def _validate_semantic_relationships(
    *,
    definitions: list[SemanticDefinition],
    instances: list[ModuleInstance],
    calls: list[ArchitectureCall],
    values: list[SemanticValue],
    control_regions: list[ControlRegion],
    parameter_groups: list[ParameterGroup],
    repeats: list[SemanticRepeat],
    pattern_bindings: list[PatternBindingV2],
    evidence: list[SourceEvidenceV2],
    graph_input_value_ids: list[Identifier],
    graph_output_value_ids: list[Identifier],
) -> None:
    definition_ids = {item.definition_id for item in definitions}
    instance_ids = {item.instance_id for item in instances}
    call_ids = {item.call_id for item in calls}
    value_ids = {item.value_id for item in values}
    control_region_ids = {item.control_region_id for item in control_regions}
    parameter_group_ids = {item.parameter_group_id for item in parameter_groups}
    repeat_ids = {item.repeat_id for item in repeats}
    evidence_ids = {item.evidence_id for item in evidence}

    def require_subset(references: set[str], known: set[str], label: str) -> None:
        missing = sorted(references - known)
        if missing:
            raise ValueError(f"{label} reference unknown IDs: {', '.join(missing)}")

    require_subset(
        {item.local_definition_id for item in instances if item.local_definition_id},
        definition_ids,
        "module instance definition",
    )
    require_subset(
        {item.parent_instance_id for item in instances if item.parent_instance_id},
        instance_ids,
        "module instance parent",
    )
    require_subset(
        {item.parent_module_id for item in calls},
        instance_ids,
        "call parent module",
    )
    require_subset(
        {item.instance_id for item in calls if item.instance_id},
        instance_ids,
        "call instance",
    )
    require_subset(
        {item.local_definition_id for item in calls if item.local_definition_id},
        definition_ids,
        "call definition",
    )
    require_subset(
        {item.control_region_id for item in calls},
        control_region_ids,
        "call control region",
    )
    require_subset(
        {
            binding.value_id
            for item in calls
            for binding in [*item.input_bindings, *item.output_bindings]
        },
        value_ids,
        "call value binding",
    )
    require_subset(
        {item.owner_definition_id for item in control_regions},
        definition_ids,
        "control region owner",
    )
    require_subset(
        {item.parent_region_id for item in control_regions if item.parent_region_id},
        control_region_ids,
        "control region parent",
    )
    require_subset(
        {
            identifier
            for item in parameter_groups
            for identifier in [item.owner_instance_id, *item.member_instance_ids]
        },
        instance_ids,
        "parameter group instance",
    )
    require_subset(
        {call_id for item in parameter_groups for call_id in item.call_ids},
        call_ids,
        "parameter group call",
    )
    require_subset(
        {
            identifier
            for item in repeats
            for identifier in (item.owner_instance_id, item.container_instance_id)
        },
        instance_ids,
        "repeat instance",
    )
    require_subset(
        {call_id for item in repeats for call_id in item.body_call_ids},
        call_ids,
        "repeat body call",
    )
    semantic_ids = (
        definition_ids
        | instance_ids
        | call_ids
        | value_ids
        | control_region_ids
        | parameter_group_ids
        | repeat_ids
    )
    require_subset(
        {subject for item in pattern_bindings for subject in item.subject_ids},
        semantic_ids,
        "pattern subject",
    )
    require_subset(
        {
            subject
            for item in pattern_bindings
            for subjects in item.slot_bindings.values()
            for subject in subjects
        },
        semantic_ids,
        "pattern slot",
    )
    require_subset(
        {evidence_id for item in pattern_bindings for evidence_id in item.evidence_ids},
        evidence_ids,
        "pattern evidence",
    )
    require_subset(set(graph_input_value_ids), value_ids, "graph input value")
    require_subset(set(graph_output_value_ids), value_ids, "graph output value")
    if len(graph_input_value_ids) != len(set(graph_input_value_ids)):
        raise ValueError("graph input value IDs must be unique")
    if len(graph_output_value_ids) != len(set(graph_output_value_ids)):
        raise ValueError("graph output value IDs must be unique")


class PythonSemanticGraph(StrictModel):
    schema_version: Literal["2.0"] = "2.0"
    graph_id: Identifier
    source_corpus_digest: Sha256
    entrypoint: str = Field(min_length=3)
    definitions: list[SemanticDefinition] = Field(default_factory=list)
    instances: list[ModuleInstance] = Field(default_factory=list)
    calls: list[ArchitectureCall] = Field(default_factory=list)
    values: list[SemanticValue] = Field(default_factory=list)
    graph_input_value_ids: list[Identifier] = Field(default_factory=list)
    graph_output_value_ids: list[Identifier] = Field(default_factory=list)
    control_regions: list[ControlRegion] = Field(default_factory=list)
    parameter_groups: list[ParameterGroup] = Field(default_factory=list)
    repeats: list[SemanticRepeat] = Field(default_factory=list)
    pattern_bindings: list[PatternBindingV2] = Field(default_factory=list)
    evidence: list[SourceEvidenceV2] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    semantic_graph_digest: Sha256

    @model_validator(mode="after")
    def relationships_are_valid(self) -> PythonSemanticGraph:
        _validate_semantic_relationships(
            definitions=self.definitions,
            instances=self.instances,
            calls=self.calls,
            values=self.values,
            control_regions=self.control_regions,
            parameter_groups=self.parameter_groups,
            repeats=self.repeats,
            pattern_bindings=self.pattern_bindings,
            evidence=self.evidence,
            graph_input_value_ids=self.graph_input_value_ids,
            graph_output_value_ids=self.graph_output_value_ids,
        )
        return self

    @model_validator(mode="after")
    def digest_is_valid(self) -> PythonSemanticGraph:
        expected = domain_digest(SEMANTIC_GRAPH_DIGEST_DOMAIN, semantic_graph_payload(self))
        if self.semantic_graph_digest != expected:
            raise ValueError("semantic graph digest does not match graph content")
        return self


def exact_ir_payload(ir: ExactArchitectureIRV2) -> dict[str, object]:
    return ir.model_dump(mode="json", exclude={"exact_ir_digest"})


class ExactArchitectureIRV2(StrictModel):
    schema_version: Literal["2.0"] = "2.0"
    architecture_id: Identifier
    source_corpus_digest: Sha256
    analysis_input_digest: Sha256
    registry_digest: Sha256
    semantic_graph_digest: Sha256
    framework: str = Field(min_length=1)
    entrypoint: str = Field(min_length=3)
    definitions: list[SemanticDefinition] = Field(default_factory=list)
    instances: list[ModuleInstance] = Field(default_factory=list)
    calls: list[ArchitectureCall] = Field(default_factory=list)
    values: list[SemanticValue] = Field(default_factory=list)
    graph_input_value_ids: list[Identifier] = Field(default_factory=list)
    graph_output_value_ids: list[Identifier] = Field(default_factory=list)
    control_regions: list[ControlRegion] = Field(default_factory=list)
    parameter_groups: list[ParameterGroup] = Field(default_factory=list)
    repeats: list[SemanticRepeat] = Field(default_factory=list)
    pattern_bindings: list[PatternBindingV2] = Field(default_factory=list)
    evidence: list[SourceEvidenceV2] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    exact_ir_digest: Sha256

    @model_validator(mode="after")
    def relationships_are_valid(self) -> ExactArchitectureIRV2:
        _validate_semantic_relationships(
            definitions=self.definitions,
            instances=self.instances,
            calls=self.calls,
            values=self.values,
            control_regions=self.control_regions,
            parameter_groups=self.parameter_groups,
            repeats=self.repeats,
            pattern_bindings=self.pattern_bindings,
            evidence=self.evidence,
            graph_input_value_ids=self.graph_input_value_ids,
            graph_output_value_ids=self.graph_output_value_ids,
        )
        return self

    @model_validator(mode="after")
    def digest_is_valid(self) -> ExactArchitectureIRV2:
        expected = domain_digest(EXACT_IR_DIGEST_DOMAIN, exact_ir_payload(self))
        if self.exact_ir_digest != expected:
            raise ValueError("exact IR v2 digest does not match architecture content")
        return self


ARCHITECTURE_V2_SCHEMA_MODELS = {
    "python-semantic-graph-v2.schema.json": PythonSemanticGraph,
    "architecture-ir-v2.schema.json": ExactArchitectureIRV2,
}
