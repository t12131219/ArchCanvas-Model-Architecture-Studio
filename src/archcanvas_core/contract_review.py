from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .digest_protocol import domain_digest
from .models import DefinitionRef, Diagnostic, Identifier, Sha256, StrictModel
from .module_contract import ModuleDefinition, module_definition_payload

CONTRACT_CANDIDATE_DIGEST_DOMAIN = "archcanvas:module-definition-candidate:v1"
CONTRACT_VALIDATION_DIGEST_DOMAIN = "archcanvas:contract-validation:v1"

ContractCompatibility = Literal[
    "breaking", "backward-compatible", "visual-only", "unchanged"
]
VersionBump = Literal["major", "minor", "patch", "none"]


def contract_candidate_digest(candidate: ModuleDefinition) -> str:
    return domain_digest(CONTRACT_CANDIDATE_DIGEST_DOMAIN, module_definition_payload(candidate))


class ContractChange(StrictModel):
    subject: str = Field(min_length=1)
    kind: Literal["parameter", "port", "rule", "matcher", "semantic", "visual"]
    compatibility: Literal["breaking", "backward-compatible", "visual-only"]
    message: str = Field(min_length=1)


class ContractDiff(StrictModel):
    changes: list[ContractChange] = Field(default_factory=list)
    compatibility: ContractCompatibility
    required_version_bump: VersionBump


class MigrationFixtureResult(StrictModel):
    fixture_id: Identifier
    status: Literal["passed", "failed"]
    message: str = Field(min_length=1)


class DefinitionMigration(StrictModel):
    migration_id: Identifier
    from_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    to_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    parameter_map: dict[Identifier, Identifier | None] = Field(default_factory=dict)
    port_map: dict[Identifier, Identifier | None] = Field(default_factory=dict)
    fixture_results: list[MigrationFixtureResult] = Field(default_factory=list)


class ContractDefinitionDraft(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    draft_id: Identifier
    base: DefinitionRef
    candidate: ModuleDefinition
    candidate_digest: Sha256
    author: str = Field(min_length=1)
    created_at: str = Field(min_length=1)
    revision: int = Field(default=0, ge=0)
    state: Literal["draft", "validating", "review-ready", "approved", "rejected"] = "draft"
    migration: DefinitionMigration | None = None

    @model_validator(mode="after")
    def candidate_is_bound(self) -> ContractDefinitionDraft:
        if self.candidate_digest != contract_candidate_digest(self.candidate):
            raise ValueError("contract draft candidate digest is stale")
        return self


class ContractValidation(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    validation_id: Identifier
    draft_id: Identifier
    candidate_digest: Sha256
    validation_digest: Sha256
    status: Literal["passed", "failed"]
    diff: ContractDiff
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    validated_at: str = Field(min_length=1)


class ContractReviewReceipt(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    receipt_id: Identifier
    draft_id: Identifier
    candidate_digest: Sha256
    validation_digest: Sha256
    reviewer: str = Field(min_length=1)
    decision: Literal["approved", "rejected"]
    decided_at: str = Field(min_length=1)


class ContractMaintenanceCapability(StrictModel):
    capability_id: Identifier
    subject: str = Field(min_length=1)
    draft_id: Identifier
    base: DefinitionRef
    allowed_commands: list[
        Literal["UpdateCandidate", "Validate", "Review", "Publish", "Discard"]
    ] = Field(min_length=1)
    issued_at: str = Field(min_length=1)
    expires_at: str = Field(min_length=1)


class ContractMaintenanceSession(StrictModel):
    mode: Literal["contract-maintenance"] = "contract-maintenance"
    capability: ContractMaintenanceCapability
    candidate_digest: Sha256


def contract_validation_digest(
    *,
    draft_id: str,
    candidate_digest: str,
    status: str,
    diff: ContractDiff,
    diagnostics: list[Diagnostic],
) -> str:
    return domain_digest(
        CONTRACT_VALIDATION_DIGEST_DOMAIN,
        {
            "draft_id": draft_id,
            "candidate_digest": candidate_digest,
            "status": status,
            "diff": diff,
            "diagnostics": diagnostics,
        },
    )
