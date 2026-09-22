"""Strict project, visual-history and Engine RPC contracts for Stage 5."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .architecture import ArchitectureIR, JsonValue
from .canvas import CanvasDocument, CanvasDocumentId
from .common import StrictModel
from .patch import PatchSet
from .publication import PublicationIR, PublicationNodeId, VisualScene
from .runtime import NetworkPolicy, RuntimeProviderId, RuntimeTensorInput, RuntimeTraceResult
from .source_identity import AnchorId, Sha256, SourceIdentityDocument
from .validation import ObservedGraphDelta, ValidationReport

ProjectId = Annotated[str, Field(pattern=r"^project:[A-Za-z0-9._-]+$")]
VisualPatchId = Annotated[str, Field(pattern=r"^visual-patch:[A-Za-z0-9._-]+$")]
EngineRequestId = Annotated[str, Field(pattern=r"^engine-request:[A-Za-z0-9._-]+$")]
EngineEventId = Annotated[str, Field(pattern=r"^engine-event:[A-Za-z0-9._-]+$")]
ResolvedConfigValue = str | int | float | bool | None


class ProjectSourceStatus(str, Enum):
    READY = "ready"
    STALE = "stale"


class EngineEnvironment(StrictModel):
    python_executable: str = Field(min_length=1)
    environment_name: str | None = None
    dependency_lockfile: str | None = None


class ProjectManifest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    project_id: ProjectId
    approved_root: str = Field(min_length=1)
    framework: Literal["pytorch"]
    entrypoint: str = Field(pattern=r"^[A-Za-z0-9_./-]+\.py:[A-Za-z_][A-Za-z0-9_]*$")
    environment: EngineEnvironment
    resolved_config: dict[str, ResolvedConfigValue] = Field(default_factory=dict)
    patch_parameter_names: list[str] = Field(default_factory=list)
    source_revision: Sha256
    file_revisions: dict[str, Sha256] = Field(min_length=1)
    source_status: ProjectSourceStatus = ProjectSourceStatus.READY
    analysis_generation: int = Field(default=0, ge=0)


class VisualAnnotation(StrictModel):
    annotation_id: str = Field(pattern=r"^visual-annotation:[A-Za-z0-9._-]+$")
    target_node_id: PublicationNodeId
    text: str = Field(min_length=1, max_length=160)


class VisualPatch(StrictModel):
    """Persisted presentation state; it contains no source or architecture edit payload."""

    schema_version: Literal["1.0"] = "1.0"
    visual_patch_id: VisualPatchId
    project_id: ProjectId
    publication_id: str = Field(pattern=r"^publication:[A-Za-z0-9._-]+$")
    base_source_revision: Sha256
    expanded_node_ids: list[PublicationNodeId] = Field(default_factory=list)
    annotations: list[VisualAnnotation] = Field(default_factory=list)

    @model_validator(mode="after")
    def visual_identifiers_are_unique(self) -> VisualPatch:
        if len(self.expanded_node_ids) != len(set(self.expanded_node_ids)):
            raise ValueError("duplicate expanded publication node")
        identifiers = [annotation.annotation_id for annotation in self.annotations]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("duplicate visual annotation")
        return self


class EngineOperation(str, Enum):
    HEALTH = "health"
    OPEN_PROJECT = "open_project"
    ANALYZE_PROJECT = "analyze_project"
    REFRESH_PROJECT = "refresh_project"
    SAVE_VISUAL_PATCH = "save_visual_patch"
    REPLAY_VISUAL_PATCHES = "replay_visual_patches"
    SAVE_CANVAS_DOCUMENT = "save_canvas_document"
    REPLAY_CANVAS_DOCUMENTS = "replay_canvas_documents"
    LOAD_ANALYSIS = "load_analysis"
    RESOLVE_SOURCE_ANCHOR = "resolve_source_anchor"
    PLAN_PATCH = "plan_patch"
    VALIDATE_PATCH = "validate_patch"
    COMMIT_PATCH = "commit_patch"


class HealthCommand(StrictModel):
    operation: Literal[EngineOperation.HEALTH] = EngineOperation.HEALTH


class OpenProjectCommand(StrictModel):
    operation: Literal[EngineOperation.OPEN_PROJECT] = EngineOperation.OPEN_PROJECT
    project_id: ProjectId
    approved_root: str = Field(min_length=1)
    entrypoint: str = Field(pattern=r"^[A-Za-z0-9_./-]+\.py:[A-Za-z_][A-Za-z0-9_]*$")
    environment: EngineEnvironment
    resolved_config: dict[str, ResolvedConfigValue] = Field(default_factory=dict)


class ProjectCommand(StrictModel):
    operation: Literal[
        EngineOperation.ANALYZE_PROJECT,
        EngineOperation.REFRESH_PROJECT,
        EngineOperation.REPLAY_VISUAL_PATCHES,
        EngineOperation.REPLAY_CANVAS_DOCUMENTS,
        EngineOperation.LOAD_ANALYSIS,
    ]
    project_id: ProjectId


class SaveVisualPatchCommand(StrictModel):
    operation: Literal[EngineOperation.SAVE_VISUAL_PATCH] = EngineOperation.SAVE_VISUAL_PATCH
    visual_patch: VisualPatch


class SaveCanvasDocumentCommand(StrictModel):
    operation: Literal[EngineOperation.SAVE_CANVAS_DOCUMENT] = EngineOperation.SAVE_CANVAS_DOCUMENT
    canvas_document: CanvasDocument


class ResolveSourceAnchorCommand(StrictModel):
    operation: Literal[EngineOperation.RESOLVE_SOURCE_ANCHOR] = EngineOperation.RESOLVE_SOURCE_ANCHOR
    project_id: ProjectId
    anchor_id: AnchorId


class PatchCommand(StrictModel):
    operation: Literal[
        EngineOperation.PLAN_PATCH,
        EngineOperation.VALIDATE_PATCH,
        EngineOperation.COMMIT_PATCH,
    ]
    project_id: ProjectId
    patch_set: PatchSet
    # Issued only after Engine validation.  The Engine treats it as a one-time
    # confirmation capability rather than trusting a client-side "validated" flag.
    confirmation_id: str | None = Field(default=None, pattern=r"^confirmation:[A-Za-z0-9_-]+$")


class PatchRuntimeProfile(StrictModel):
    """Engine-registered, bounded runtime validation for a candidate patch."""

    constructor_kwargs: dict[str, JsonValue] = Field(default_factory=dict)
    inputs: list[RuntimeTensorInput] = Field(min_length=1, max_length=8)
    provider: RuntimeProviderId
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    memory_limit_mb: int = Field(default=2_048, ge=128, le=16_384)
    network_policy: NetworkPolicy = NetworkPolicy.DENY


EngineCommand = Annotated[
    HealthCommand
    | OpenProjectCommand
    | ProjectCommand
    | SaveVisualPatchCommand
    | SaveCanvasDocumentCommand
    | ResolveSourceAnchorCommand
    | PatchCommand,
    Field(discriminator="operation"),
]


class EngineRequest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    request_id: EngineRequestId
    command: EngineCommand


class ArtifactReference(StrictModel):
    relative_path: str = Field(pattern=r"^[A-Za-z0-9._/-]+$")
    sha256: Sha256


class ProjectOpenedResult(StrictModel):
    kind: Literal["project_opened"] = "project_opened"
    manifest: ProjectManifest


class AnalysisResult(StrictModel):
    kind: Literal["analysis_completed"] = "analysis_completed"
    manifest: ProjectManifest
    source: SourceIdentityDocument
    architecture: ArchitectureIR
    publication: PublicationIR
    scene: VisualScene
    svg: ArtifactReference


class LoadedAnalysisResult(StrictModel):
    """A cache-backed analysis bundle for a restarting Engine client."""

    kind: Literal["analysis_loaded"] = "analysis_loaded"
    manifest: ProjectManifest
    source: SourceIdentityDocument
    architecture: ArchitectureIR
    publication: PublicationIR
    scene: VisualScene
    svg: ArtifactReference


class SourceLocationResult(StrictModel):
    """An Engine-approved source jump target, intentionally without source bytes."""

    kind: Literal["source_location"] = "source_location"
    project_id: ProjectId
    anchor_id: AnchorId
    relative_file: str = Field(min_length=1)
    line: int = Field(ge=1)
    column: int = Field(ge=0)


class RefreshResult(StrictModel):
    kind: Literal["project_refreshed"] = "project_refreshed"
    manifest: ProjectManifest
    observed_source_revision: Sha256
    stale_visual_patch_ids: list[VisualPatchId]


class VisualPatchResult(StrictModel):
    kind: Literal["visual_patch_saved", "visual_patches_replayed"]
    visual_patches: list[VisualPatch]
    orphaned_visual_patch_ids: list[VisualPatchId]


class CanvasDocumentResult(StrictModel):
    kind: Literal["canvas_document_saved", "canvas_documents_replayed"]
    canvas_documents: list[CanvasDocument]
    orphaned_canvas_document_ids: list[CanvasDocumentId]


class PatchProvenance(StrictModel):
    analyzer: str = Field(min_length=1)
    transform_id: str = Field(min_length=1)
    relative_file: str = Field(min_length=1)
    anchor_id: AnchorId
    node_id: str = Field(min_length=1)
    parameter: str = Field(min_length=1)
    origin: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)


class PatchRisk(StrictModel):
    level: Literal["low", "medium", "high"]
    reasons: list[str] = Field(min_length=1)


class PatchResult(StrictModel):
    kind: Literal["patch_planned", "patch_validated", "patch_committed"]
    project_id: ProjectId
    patch_set_id: str = Field(min_length=1)
    patch_id: str = Field(min_length=1)
    candidate_diff: str = ""
    before_source_revision: Sha256
    after_source_revision: Sha256
    observed_delta: ObservedGraphDelta
    validation: ValidationReport
    provenance: PatchProvenance
    risk: PatchRisk
    blocking: bool
    confirmation_id: str | None = None
    runtime_validation: RuntimeTraceResult | None = None
    analysis: AnalysisResult | None = None


class HealthResult(StrictModel):
    kind: Literal["health"] = "health"
    capabilities: list[str]


EngineResult = Annotated[
    HealthResult
    | ProjectOpenedResult
    | AnalysisResult
    | LoadedAnalysisResult
    | SourceLocationResult
    | RefreshResult
    | VisualPatchResult
    | CanvasDocumentResult
    | PatchResult,
    Field(discriminator="kind"),
]


class EngineError(StrictModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    message: str = Field(min_length=1)


class EngineResponse(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    request_id: EngineRequestId
    status: Literal["succeeded", "rejected", "failed"]
    result: EngineResult | None = None
    error: EngineError | None = None

    @model_validator(mode="after")
    def outcome_is_consistent(self) -> EngineResponse:
        if (self.result is None) == (self.error is None):
            raise ValueError("response must contain exactly one result or error")
        if self.status == "succeeded" and self.error is not None:
            raise ValueError("successful response cannot contain an error")
        if self.status != "succeeded" and self.error is None:
            raise ValueError("unsuccessful response requires an error")
        return self


class EngineEvent(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    event_id: EngineEventId
    kind: Literal[
        "project_opened",
        "analysis_completed",
        "source_stale",
        "visual_patch_saved",
        "canvas_document_saved",
        "patch_planned",
        "patch_validated",
        "patch_committed",
        "patch_rolled_back",
        "patch_rejected",
    ]
    project_id: ProjectId
    source_revision: Sha256
    message: str = Field(min_length=1)
