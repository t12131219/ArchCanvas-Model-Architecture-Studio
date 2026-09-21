from __future__ import annotations

from enum import Enum
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import StrictModel

Sha256 = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
AnchorId = Annotated[str, Field(pattern=r"^anchor:[A-Za-z0-9._-]+$")]
IdentityId = Annotated[str, Field(pattern=r"^identity:[A-Za-z0-9._-]+$")]


class Framework(str, Enum):
    PYTORCH = "pytorch"
    KERAS = "keras"
    ONNX = "onnx"
    UNKNOWN = "unknown"


class AnchorKind(str, Enum):
    CLASS = "class"
    FUNCTION = "function"
    ASSIGNMENT = "assignment"
    CALL = "call"
    ARGUMENT = "argument"
    EXPRESSION = "expression"


class SourcePosition(StrictModel):
    line: int = Field(ge=1)
    column: int = Field(ge=0)


class SourceSpan(StrictModel):
    start: SourcePosition
    end: SourcePosition

    @model_validator(mode="after")
    def end_is_after_start(self) -> SourceSpan:
        if (self.end.line, self.end.column) <= (self.start.line, self.start.column):
            raise ValueError("source span must be non-empty and half-open")
        return self


class AnchorLocator(StrictModel):
    class_name: str | None
    function_name: str | None
    assignment_target: str | None
    callee_text: str | None
    qualified_callee: str | None
    argument_name: str | None
    occurrence: int = Field(ge=0)


class SourceAnchor(StrictModel):
    anchor_id: AnchorId
    relative_file: str
    symbol_path: str | None
    semantic_path: str | None
    kind: AnchorKind
    cst_node_type: str = Field(min_length=1)
    span: SourceSpan
    locator: AnchorLocator
    structural_fingerprint: Sha256
    content_fingerprint: Sha256
    file_revision: Sha256

    @model_validator(mode="after")
    def validate_relative_path(self) -> SourceAnchor:
        path = PurePosixPath(self.relative_file)
        if (
            not self.relative_file
            or path.is_absolute()
            or "\\" in self.relative_file
            or "//" in self.relative_file
            or self.relative_file.endswith("/")
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError("relative_file must be a normalized POSIX relative path")
        return self


class NodeIdentity(StrictModel):
    identity_id: IdentityId
    framework: Framework
    module_path: str | None
    relative_file: str | None
    qualified_symbol: str | None
    attribute_path: str | None
    semantic_role: str | None
    structural_fingerprint: Sha256
    anchor_ids: list[AnchorId]
    created_revision: Sha256

    @model_validator(mode="after")
    def source_backed_identity_has_anchor(self) -> NodeIdentity:
        if self.relative_file is not None and not self.anchor_ids:
            raise ValueError("source-backed identity requires at least one anchor")
        return self


class ReconciliationDecision(str, Enum):
    EXACT = "exact"
    RECONCILED = "reconciled"
    NEW = "new"
    AMBIGUOUS = "ambiguous"


class IdentityReconciliation(StrictModel):
    old_identity_id: IdentityId | None
    new_discovery_id: str = Field(min_length=1)
    resolved_identity_id: IdentityId | None
    score: float = Field(ge=0, le=1)
    decision: ReconciliationDecision
    reasons: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def decision_has_consistent_identifiers(self) -> IdentityReconciliation:
        resolved = self.resolved_identity_id is not None
        old = self.old_identity_id is not None
        if self.decision in {ReconciliationDecision.EXACT, ReconciliationDecision.RECONCILED}:
            valid = old and resolved
        elif self.decision is ReconciliationDecision.NEW:
            valid = not old and resolved
        else:
            valid = not old and not resolved
        if not valid:
            raise ValueError("reconciliation identifiers do not match decision")
        return self


class SourceIdentityDocument(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    project_id: str = Field(min_length=1)
    source_revision: Sha256
    file_revisions: dict[str, Sha256] = Field(min_length=1)
    anchors: list[SourceAnchor]
    identities: list[NodeIdentity]
    reconciliations: list[IdentityReconciliation]

    @model_validator(mode="after")
    def source_document_is_consistent(self) -> SourceIdentityDocument:
        anchor_ids = [anchor.anchor_id for anchor in self.anchors]
        identity_ids = [identity.identity_id for identity in self.identities]
        if len(anchor_ids) != len(set(anchor_ids)):
            raise ValueError("duplicate anchor_id")
        if len(identity_ids) != len(set(identity_ids)):
            raise ValueError("duplicate identity_id")
        if any("\\" in path or path.startswith("/") for path in self.file_revisions):
            raise ValueError("file_revisions contains an invalid relative path")
        return self
