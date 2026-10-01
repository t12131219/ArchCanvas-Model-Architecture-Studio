from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from .digest_protocol import domain_digest
from .models import DefinitionRef, Identifier, Sha256, StrictModel

MODULE_DEFINITION_DIGEST_DOMAIN = "archcanvas:module-definition:v1"
MODULE_REGISTRY_DIGEST_DOMAIN = "archcanvas:module-registry:v1"

DerivedArtifact = Literal["ports", "shape", "cost", "code", "visual"]
ParameterEditability = Literal["editable", "source-readonly", "derived-readonly"]


class ParameterContract(StrictModel):
    parameter_id: Identifier
    required: bool = False
    default: Any = None
    value_type: Literal["integer", "number", "boolean", "string", "shape", "any"] = "any"
    positional_index: int | None = Field(default=None, ge=0)
    affects: list[DerivedArtifact] = Field(default_factory=list)
    editability: ParameterEditability = "editable"

    @model_validator(mode="after")
    def impact_is_valid(self) -> ParameterContract:
        if len(self.affects) != len(set(self.affects)):
            raise ValueError("parameter affects entries must be unique")
        return self


class PortContract(StrictModel):
    port_id: Identifier
    direction: Literal["input", "output"]
    required: bool = True
    min_connections: int = Field(default=1, ge=0)
    max_connections: int | Literal["many"] = 1
    ordering: Literal["ordered", "unordered"] = "ordered"
    accepted_relations: list[str] = Field(default_factory=lambda: ["main"])
    tensor_ranks: list[int] = Field(default_factory=list)
    tensor_layouts: list[Literal["NCHW", "NHWC", "sequence", "scalar", "any"]] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def cardinality_is_valid(self) -> PortContract:
        if isinstance(self.max_connections, int) and self.max_connections < self.min_connections:
            raise ValueError("max_connections cannot be smaller than min_connections")
        if not self.required and self.min_connections > 0:
            raise ValueError("optional ports must allow zero connections")
        if len(self.accepted_relations) != len(set(self.accepted_relations)):
            raise ValueError("accepted_relations entries must be unique")
        if any(rank < 0 for rank in self.tensor_ranks) or len(self.tensor_ranks) != len(
            set(self.tensor_ranks)
        ):
            raise ValueError("tensor ranks must be unique non-negative integers")
        if len(self.tensor_layouts) != len(set(self.tensor_layouts)):
            raise ValueError("tensor layouts must be unique")
        return self


def module_definition_payload(definition: ModuleDefinition) -> dict[str, object]:
    return {
        "definition_id": definition.definition_id,
        "version": definition.version,
        "semantic_kind": definition.semantic_kind,
        "qualified_names": sorted(definition.qualified_names),
        "parameter_schema_version": definition.parameter_schema_version,
        "parameters": [item.model_dump(mode="json") for item in definition.parameters],
        "ports": [item.model_dump(mode="json") for item in definition.ports],
        "glyph_id": definition.glyph_id,
        "detail_template_id": definition.detail_template_id,
        "shape_rule_id": definition.shape_rule_id,
        "cost_rule_id": definition.cost_rule_id,
        "codegen_rule_id": definition.codegen_rule_id,
    }


class ModuleDefinition(StrictModel):
    definition_id: Identifier
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    digest: Sha256
    semantic_kind: str = Field(min_length=1)
    qualified_names: list[str] = Field(min_length=1)
    parameter_schema_version: Literal["1.0"] = "1.0"
    parameters: list[ParameterContract] = Field(default_factory=list)
    ports: list[PortContract] = Field(min_length=1)
    glyph_id: Identifier
    detail_template_id: Identifier | None = None
    shape_rule_id: Identifier | None = None
    cost_rule_id: Identifier | None = None
    codegen_rule_id: Identifier | None = None

    @model_validator(mode="after")
    def definition_is_valid(self) -> ModuleDefinition:
        port_ids = [item.port_id for item in self.ports]
        parameter_ids = [item.parameter_id for item in self.parameters]
        if len(port_ids) != len(set(port_ids)):
            raise ValueError("module definition port identifiers must be unique")
        if len(parameter_ids) != len(set(parameter_ids)):
            raise ValueError("module definition parameter identifiers must be unique")
        expected = domain_digest(MODULE_DEFINITION_DIGEST_DOMAIN, module_definition_payload(self))
        if self.digest != expected:
            raise ValueError("module definition digest does not match its contract")
        return self

    @property
    def ref(self) -> DefinitionRef:
        return DefinitionRef(
            definition_id=self.definition_id,
            version=self.version,
            digest=self.digest,
        )


def registry_bundle_payload(definitions: list[ModuleDefinition]) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "definitions": [
            item.model_dump(mode="json")
            for item in sorted(definitions, key=lambda value: (value.definition_id, value.version))
        ],
    }


class ModuleRegistryBundle(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    bundle_id: Identifier
    bundle_digest: Sha256
    definitions: list[ModuleDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def registry_is_valid(self) -> ModuleRegistryBundle:
        identities = [(item.definition_id, item.version) for item in self.definitions]
        if len(identities) != len(set(identities)):
            raise ValueError("module registry definitions must be unique by id and version")
        qualified_names = [name for item in self.definitions for name in item.qualified_names]
        if len(qualified_names) != len(set(qualified_names)):
            raise ValueError("module registry qualified names must resolve unambiguously")
        expected = domain_digest(
            MODULE_REGISTRY_DIGEST_DOMAIN,
            registry_bundle_payload(self.definitions),
        )
        if self.bundle_digest != expected:
            raise ValueError("module registry digest does not match its definitions")
        return self


def define_module(
    *,
    definition_id: str,
    version: str,
    semantic_kind: str,
    qualified_names: list[str],
    ports: list[PortContract],
    parameters: list[ParameterContract] | None = None,
    glyph_id: str,
    detail_template_id: str | None = None,
    shape_rule_id: str | None = None,
    cost_rule_id: str | None = None,
    codegen_rule_id: str | None = None,
    parameter_schema_version: Literal["1.0"] = "1.0",
) -> ModuleDefinition:
    values = {
        "definition_id": definition_id,
        "version": version,
        "semantic_kind": semantic_kind,
        "qualified_names": qualified_names,
        "parameter_schema_version": parameter_schema_version,
        "parameters": parameters or [],
        "ports": ports,
        "glyph_id": glyph_id,
        "detail_template_id": detail_template_id,
        "shape_rule_id": shape_rule_id,
        "cost_rule_id": cost_rule_id,
        "codegen_rule_id": codegen_rule_id,
    }
    prototype = ModuleDefinition.model_construct(digest="0" * 64, **values)
    digest = domain_digest(MODULE_DEFINITION_DIGEST_DOMAIN, module_definition_payload(prototype))
    return ModuleDefinition(digest=digest, **values)


def migrate_parameter_values(
    definition: ModuleDefinition,
    source_schema_version: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Normalize a persisted parameter object against its pinned definition schema.

    Version 1.0 is the first published ABI. Keeping migration explicit, even for the
    identity migration, prevents callers from silently applying a newer definition.
    """

    if source_schema_version != definition.parameter_schema_version:
        raise ValueError(
            "no registered parameter migration from "
            f"{source_schema_version} to {definition.parameter_schema_version}"
        )
    contracts = {item.parameter_id: item for item in definition.parameters}
    unknown = sorted(set(values) - set(contracts))
    if unknown:
        raise ValueError("unknown module parameters: " + ", ".join(unknown))
    migrated = {item.parameter_id: item.default for item in definition.parameters}
    migrated.update(values)
    return migrated


MODULE_CONTRACT_SCHEMA_MODELS = {
    "module-registry-bundle-v1.schema.json": ModuleRegistryBundle,
}
