from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal

from pydantic import Field, model_validator

from .digest_protocol import domain_digest
from .models import EntryInvocationConfig, Identifier, Sha256, SourceAnchor, StrictModel

SOURCE_CORPUS_DIGEST_DOMAIN = "archcanvas:source-corpus:v2"
ANALYSIS_INPUT_DIGEST_DOMAIN = "archcanvas:analysis-input:v2"
ANALYSIS_ENVIRONMENT_DIGEST_DOMAIN = "archcanvas:analysis-environment:v1"


def _validate_relative_path(value: str, *, allow_dot: bool = False) -> str:
    if "\\" in value:
        raise ValueError("paths must use POSIX separators")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("paths must be confined relative POSIX paths")
    if value != path.as_posix() or (value == "." and not allow_dot):
        raise ValueError("paths must be normalized relative POSIX paths")
    if not allow_dot and value in {"", "."}:
        raise ValueError("path cannot be empty")
    return value


class DiscoveryBudget(StrictModel):
    max_files: int = Field(default=10_000, ge=1, le=1_000_000)
    max_total_bytes: int = Field(default=512 * 1024 * 1024, ge=1)
    max_file_bytes: int = Field(default=2 * 1024 * 1024, ge=1)


class AnalysisBudget(StrictModel):
    max_call_depth: int = Field(default=64, ge=0, le=10_000)
    max_resolver_queries: int = Field(default=5_000, ge=0, le=1_000_000)


class SourceRootSpec(StrictModel):
    logical_prefix: str = ""
    relative_path: str = "."
    precedence: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def paths_are_normalized(self) -> SourceRootSpec:
        if self.logical_prefix:
            _validate_relative_path(self.logical_prefix)
        _validate_relative_path(self.relative_path, allow_dot=True)
        return self


class ProjectManifest(StrictModel):
    schema_version: Literal["2.0"] = "2.0"
    project_id: Identifier
    project_root_hint: str = Field(min_length=1)
    source_roots: list[SourceRootSpec] = Field(min_length=1)
    include_globs: list[str] = Field(min_length=1)
    exclude_globs: list[str] = Field(default_factory=list)
    config_paths: list[str] = Field(default_factory=list)
    python_target: str = Field(default="3.11", min_length=1)
    platform_target: str = Field(default="all", min_length=1)
    namespace_package_policy: Literal["enabled", "disabled"] = "enabled"
    discovery_budget: DiscoveryBudget = Field(default_factory=DiscoveryBudget)

    @model_validator(mode="after")
    def manifest_paths_are_safe(self) -> ProjectManifest:
        roots = [(item.logical_prefix, item.relative_path) for item in self.source_roots]
        if len(roots) != len(set(roots)):
            raise ValueError("source roots must be unique")
        for path in self.config_paths:
            _validate_relative_path(path)
        for pattern in [*self.include_globs, *self.exclude_globs]:
            if not pattern or pattern.startswith("/") or "\\" in pattern:
                raise ValueError("glob patterns must be relative POSIX patterns")
            if ".." in PurePosixPath(pattern).parts:
                raise ValueError("glob patterns cannot escape the project")
        return self


class ExcludedSource(StrictModel):
    logical_path: str
    reason: Literal[
        "excluded-pattern",
        "unsupported-kind",
        "symlink",
        "path-escape",
        "file-too-large",
        "budget-exhausted",
        "decode-error",
        "shadowed",
    ]
    detail: str | None = None

    @model_validator(mode="after")
    def path_is_safe(self) -> ExcludedSource:
        _validate_relative_path(self.logical_path)
        return self


class SourceBlobRef(StrictModel):
    logical_path: str
    sha256: Sha256
    blob_ref: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    size: int = Field(ge=0)
    encoding: str = Field(min_length=1)
    file_kind: Literal["python", "stub", "config", "project-metadata"]

    @model_validator(mode="after")
    def binding_is_valid(self) -> SourceBlobRef:
        _validate_relative_path(self.logical_path)
        if self.blob_ref != f"sha256:{self.sha256}":
            raise ValueError("blob_ref must bind the declared sha256")
        return self


def source_corpus_digest_payload(
    *,
    files: list[SourceBlobRef],
    source_roots: list[SourceRootSpec],
    excluded: list[ExcludedSource],
) -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "source_roots": [
            item.model_dump(mode="json")
            for item in sorted(
                source_roots,
                key=lambda root: (root.precedence, root.logical_prefix, root.relative_path),
            )
        ],
        "files": [
            {
                "logical_path": item.logical_path,
                "sha256": item.sha256,
                "size": item.size,
                "encoding": item.encoding,
                "file_kind": item.file_kind,
            }
            for item in sorted(files, key=lambda source: source.logical_path)
        ],
        "excluded": [
            item.model_dump(mode="json")
            for item in sorted(excluded, key=lambda source: (source.logical_path, source.reason))
        ],
    }


def compute_source_corpus_digest(
    *,
    files: list[SourceBlobRef],
    source_roots: list[SourceRootSpec],
    excluded: list[ExcludedSource],
) -> str:
    return domain_digest(
        SOURCE_CORPUS_DIGEST_DOMAIN,
        source_corpus_digest_payload(
            files=files,
            source_roots=source_roots,
            excluded=excluded,
        ),
    )


class SourceCorpus(StrictModel):
    schema_version: Literal["2.0"] = "2.0"
    corpus_id: Identifier
    source_corpus_digest: Sha256
    vcs_revision: str | None = None
    files: list[SourceBlobRef] = Field(min_length=1)
    source_roots: list[SourceRootSpec] = Field(min_length=1)
    excluded: list[ExcludedSource] = Field(default_factory=list)

    @model_validator(mode="after")
    def corpus_is_canonical(self) -> SourceCorpus:
        paths = [item.logical_path for item in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("source corpus logical paths must be unique")
        expected = compute_source_corpus_digest(
            files=self.files,
            source_roots=self.source_roots,
            excluded=self.excluded,
        )
        if self.source_corpus_digest != expected:
            raise ValueError("source_corpus_digest does not match the corpus manifest")
        return self


class ResolverManifest(StrictModel):
    resolver_id: Identifier
    resolver_version: str = Field(min_length=1)
    resolver_digest: Sha256
    kind: Literal["pyright-typeserver", "libcst-only"] = "libcst-only"
    capability_status: Literal["active", "degraded"] = "active"
    diagnostic_code: str | None = None
    executable_digest: Sha256 | None = None
    config_digest: Sha256 | None = None
    typeshed_digest: Sha256 | None = None
    stub_corpus_digest: Sha256 | None = None
    python_target: str | None = None
    platform_target: str | None = None
    snapshot_id: str | None = None
    extra_paths: list[str] = Field(default_factory=list)
    query_count: int = Field(default=0, ge=0)
    query_digest: Sha256 | None = None
    result_digest: Sha256 | None = None

    @model_validator(mode="after")
    def paths_are_safe(self) -> ResolverManifest:
        for path in self.extra_paths:
            _validate_relative_path(path, allow_dot=True)
        if self.capability_status == "degraded" and not self.diagnostic_code:
            raise ValueError("degraded resolver manifests require a diagnostic code")
        if self.kind == "pyright-typeserver" and self.executable_digest is None:
            raise ValueError("Pyright resolver manifests require an executable digest")
        return self


def analysis_environment_manifest_payload(
    *,
    python_implementation: str,
    python_version: str,
    platform: str,
    framework_versions: dict[str, str | None],
    adapter_digests: dict[str, str],
    analyzer_digest: str,
    schema_bundle_digest: str,
    registry_digest: str,
    pattern_pack_digests: list[str],
    pyright_version: str | None,
    lockfile_digests: dict[str, str],
    environment_variables_allowlist_digest: str,
    reproducibility_level: str,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "python_implementation": python_implementation,
        "python_version": python_version,
        "platform": platform,
        "framework_versions": dict(sorted(framework_versions.items())),
        "adapter_digests": dict(sorted(adapter_digests.items())),
        "analyzer_digest": analyzer_digest,
        "schema_bundle_digest": schema_bundle_digest,
        "registry_digest": registry_digest,
        "pattern_pack_digests": sorted(pattern_pack_digests),
        "pyright_version": pyright_version,
        "lockfile_digests": dict(sorted(lockfile_digests.items())),
        "environment_variables_allowlist_digest": environment_variables_allowlist_digest,
        "reproducibility_level": reproducibility_level,
    }


class AnalysisEnvironmentManifest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    environment_manifest_digest: Sha256
    python_implementation: str = Field(min_length=1)
    python_version: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    framework_versions: dict[str, str | None]
    adapter_digests: dict[str, Sha256] = Field(min_length=1)
    analyzer_digest: Sha256
    schema_bundle_digest: Sha256
    registry_digest: Sha256
    pattern_pack_digests: list[Sha256] = Field(default_factory=list)
    pyright_version: str | None = None
    lockfile_digests: dict[str, Sha256] = Field(default_factory=dict)
    environment_variables_allowlist_digest: Sha256
    reproducibility_level: Literal["locked", "partially-locked", "unlocked"]

    @model_validator(mode="after")
    def digest_is_valid(self) -> AnalysisEnvironmentManifest:
        expected = domain_digest(
            ANALYSIS_ENVIRONMENT_DIGEST_DOMAIN,
            analysis_environment_manifest_payload(
                python_implementation=self.python_implementation,
                python_version=self.python_version,
                platform=self.platform,
                framework_versions=self.framework_versions,
                adapter_digests=self.adapter_digests,
                analyzer_digest=self.analyzer_digest,
                schema_bundle_digest=self.schema_bundle_digest,
                registry_digest=self.registry_digest,
                pattern_pack_digests=self.pattern_pack_digests,
                pyright_version=self.pyright_version,
                lockfile_digests=self.lockfile_digests,
                environment_variables_allowlist_digest=(
                    self.environment_variables_allowlist_digest
                ),
                reproducibility_level=self.reproducibility_level,
            ),
        )
        if self.environment_manifest_digest != expected:
            raise ValueError(
                "environment_manifest_digest does not match the environment manifest"
            )
        if len(self.pattern_pack_digests) != len(set(self.pattern_pack_digests)):
            raise ValueError("pattern pack digests must be unique")
        return self


def analysis_input_digest_payload(
    *,
    source_corpus_digest: str,
    registry_digest: str,
    analyzer_build_digest: str,
    pattern_pack_digests: list[str],
    resolver: ResolverManifest,
    task: str,
    execution_mode: str,
    entrypoint: str,
    config_digest: str,
    environment_manifest_digest: str = "0" * 64,
    entry_invocation: EntryInvocationConfig | None = None,
    analysis_budget: AnalysisBudget | None = None,
) -> dict[str, object]:
    analysis_budget = analysis_budget or AnalysisBudget()
    entry_invocation = entry_invocation or EntryInvocationConfig(mode=execution_mode)
    return {
        "schema_version": "2.0",
        "source_corpus_digest": source_corpus_digest,
        "registry_digest": registry_digest,
        "analyzer_build_digest": analyzer_build_digest,
        "pattern_pack_digests": sorted(pattern_pack_digests),
        "resolver": resolver.model_dump(mode="json"),
        "task": task,
        "execution_mode": execution_mode,
        "entrypoint": entrypoint,
        "config_digest": config_digest,
        "environment_manifest_digest": environment_manifest_digest,
        "entry_invocation": entry_invocation.model_dump(mode="json"),
        "analysis_budget": analysis_budget.model_dump(mode="json"),
    }


class AnalysisInputManifest(StrictModel):
    schema_version: Literal["2.0"] = "2.0"
    source_corpus_digest: Sha256
    registry_digest: Sha256
    analyzer_build_digest: Sha256
    pattern_pack_digests: list[Sha256] = Field(default_factory=list)
    resolver: ResolverManifest
    task: str = Field(min_length=1)
    execution_mode: Literal["eval", "train"]
    entrypoint: str = Field(min_length=3)
    config_digest: Sha256
    environment_manifest_digest: Sha256 = "0" * 64
    entry_invocation: EntryInvocationConfig = Field(default_factory=EntryInvocationConfig)
    analysis_budget: AnalysisBudget = Field(default_factory=AnalysisBudget)
    analysis_input_digest: Sha256

    @model_validator(mode="after")
    def digest_is_valid(self) -> AnalysisInputManifest:
        expected = domain_digest(
            ANALYSIS_INPUT_DIGEST_DOMAIN,
            analysis_input_digest_payload(
                source_corpus_digest=self.source_corpus_digest,
                registry_digest=self.registry_digest,
                analyzer_build_digest=self.analyzer_build_digest,
                pattern_pack_digests=self.pattern_pack_digests,
                resolver=self.resolver,
                task=self.task,
                execution_mode=self.execution_mode,
                entrypoint=self.entrypoint,
                config_digest=self.config_digest,
                environment_manifest_digest=self.environment_manifest_digest,
                entry_invocation=self.entry_invocation,
                analysis_budget=self.analysis_budget,
            ),
        )
        if self.entry_invocation.mode != self.execution_mode:
            raise ValueError("entry invocation mode must match analysis execution_mode")
        if self.analysis_input_digest != expected:
            raise ValueError("analysis_input_digest does not match the analysis inputs")
        return self


SOURCE_V2_SCHEMA_MODELS = {
    "project-manifest-v2.schema.json": ProjectManifest,
    "source-corpus-v2.schema.json": SourceCorpus,
    "analysis-input-manifest-v2.schema.json": AnalysisInputManifest,
    "analysis-environment-manifest-v1.schema.json": AnalysisEnvironmentManifest,
    "source-anchor-v2.schema.json": SourceAnchor,
}
