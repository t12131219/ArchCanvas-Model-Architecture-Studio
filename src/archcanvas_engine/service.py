"""The only Stage 5 business entrypoint for project analysis and visual history."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from secrets import token_urlsafe
from shutil import copytree, ignore_patterns
from tempfile import TemporaryDirectory

from archcanvas_core.models.canvas import CanvasDocument
from archcanvas_core.models.common import sha256_digest, source_snapshot_revision
from archcanvas_core.models.engine import (
    AnalysisResult,
    ArtifactReference,
    CanvasDocumentResult,
    EngineError,
    EngineEvent,
    EngineOperation,
    EngineRequest,
    EngineResponse,
    HealthCommand,
    HealthResult,
    LoadedAnalysisResult,
    OpenProjectCommand,
    PatchCommand,
    PatchProvenance,
    PatchResult,
    PatchRisk,
    PatchRuntimeProfile,
    ProjectCommand,
    ProjectManifest,
    ProjectOpenedResult,
    ProjectSourceStatus,
    RefreshResult,
    ResolveSourceAnchorCommand,
    SaveCanvasDocumentCommand,
    SaveVisualPatchCommand,
    SourceLocationResult,
    VisualPatch,
    VisualPatchResult,
)
from archcanvas_core.models.patch import InsertLayerNormPatch, PatchSet, SetParameterPatch
from archcanvas_core.models.runtime import RuntimeTraceResult, TraceRequest, TraceStatus
from archcanvas_publication import PublicationCompiler, StageLayout
from archcanvas_python.analyzers import Analyzer
from archcanvas_python.source_revision import file_revision
from archcanvas_python.transactions.insert_layer_norm import plan_insert_layer_norm
from archcanvas_python.transactions.set_parameter import (
    CandidateTransaction,
    TransactionRejected,
    commit_candidate,
    plan_set_parameter,
    rollback_candidate,
)
from archcanvas_python.transforms.registry import (
    available_parameter_names,
    resolve_parameter_transform,
)
from archcanvas_pytorch.runtime.resolver import RuntimeShapeValidator
from archcanvas_pytorch.runtime.worker_client import IsolatedTraceWorker
from archcanvas_pytorch.static import PyTorchProjectScanner, PyTorchProjectStaticAdapter
from archcanvas_renderer import publication_preflight, render_svg

from .environment import EnvironmentResolver
from .repository import EngineRepository
from .service_errors import EngineRejected
from .watcher import ProjectSourceWatcher


@dataclass(frozen=True)
class _PlannedPatch:
    patch_set_id: str
    patch_id: str
    project_id: str
    patch_set: PatchSet
    relative_file: str
    path: Path
    candidate: CandidateTransaction
    provenance: PatchProvenance
    risk: PatchRisk
    validated: bool = False
    confirmation_id: str | None = None
    runtime_validation: RuntimeTraceResult | None = None


class ArchCanvasEngine:
    """Orchestrate approved projects without granting implicit source-write authority."""

    def __init__(
        self,
        cache_root: Path,
        patch_analyzers: Mapping[str, Analyzer] | None = None,
        patch_runtime_profiles: Mapping[str, PatchRuntimeProfile] | None = None,
        runtime_worker: Callable[[TraceRequest], RuntimeTraceResult] | None = None,
    ) -> None:
        self._repository = EngineRepository(cache_root)
        self._environment_resolver = EnvironmentResolver()
        self._watcher = ProjectSourceWatcher()
        self._scanner = PyTorchProjectScanner()
        self._adapter = PyTorchProjectStaticAdapter(project_scanner=self._scanner)
        self._compiler = PublicationCompiler()
        self._layout = StageLayout()
        # Only explicitly registered analyzers may participate in source transactions.
        self._patch_analyzers = dict(patch_analyzers or {})
        self._patch_runtime_profiles = dict(patch_runtime_profiles or {})
        self._runtime_worker = runtime_worker or IsolatedTraceWorker().run
        self._planned_patches: dict[tuple[str, str], _PlannedPatch] = {}

    def register_patch_analyzer(self, project_id: str, analyzer: Analyzer) -> None:
        """Register a project-scoped transaction analyzer before planning a patch."""

        if not project_id or project_id in self._patch_analyzers:
            raise ValueError(f"patch analyzer already registered or invalid project id: {project_id!r}")
        self._patch_analyzers[project_id] = analyzer
        self._refresh_patch_capabilities(project_id)

    def register_patch_runtime_profile(self, project_id: str, profile: PatchRuntimeProfile) -> None:
        """Register an approved, bounded candidate-runtime profile for one project."""

        if not project_id or project_id in self._patch_runtime_profiles:
            raise ValueError(f"patch runtime profile already registered or invalid project id: {project_id!r}")
        self._patch_runtime_profiles[project_id] = profile
        self._refresh_patch_capabilities(project_id)

    def _patch_parameter_names(self, project_id: str) -> list[str]:
        if project_id not in self._patch_analyzers:
            return []
        return sorted(
            available_parameter_names(runtime_validation_available=project_id in self._patch_runtime_profiles)
        )

    def _refresh_patch_capabilities(self, project_id: str) -> None:
        """Persist newly registered transaction capabilities for an already open project."""

        try:
            manifest = self._repository.load_manifest(project_id)
        except FileNotFoundError:
            return
        self._repository.save_manifest(
            manifest.model_copy(update={"patch_parameter_names": self._patch_parameter_names(project_id)})
        )

    def _record_patch_event(
        self,
        *,
        kind: str,
        project_id: str,
        source_revision: str,
        patch_id: str,
        message: str,
    ) -> None:
        self._repository.append_event(
            EngineEvent(
                event_id=(
                    f"engine-event:{patch_id.removeprefix('patch:')}-{kind}-{token_urlsafe(6)}"
                ),
                kind=kind,  # type: ignore[arg-type]
                project_id=project_id,
                source_revision=source_revision,
                message=message,
            )
        )

    @staticmethod
    def _entrypoint_path(root: Path, entrypoint: str) -> Path:
        relative_file, _ = entrypoint.split(":", maxsplit=1)
        path = (root / relative_file).resolve(strict=False)
        if not path.is_file() or not path.is_relative_to(root):
            raise EngineRejected("ENTRYPOINT_OUTSIDE_APPROVED_ROOT", relative_file)
        return path

    def open_project(self, command: OpenProjectCommand) -> ProjectManifest:
        try:
            root = Path(command.approved_root).resolve(strict=True)
        except FileNotFoundError as error:
            raise EngineRejected("PROJECT_ROOT_NOT_FOUND", command.approved_root) from error
        if not root.is_dir():
            raise EngineRejected("PROJECT_ROOT_NOT_DIRECTORY", str(root))
        environment = self._environment_resolver.resolve(command.environment, root)
        source_path = self._entrypoint_path(root, command.entrypoint)
        try:
            self._scanner.build_symbol_table(root).resolve_entrypoint(command.entrypoint)
        except (KeyError, ValueError) as error:
            raise EngineRejected("ENTRYPOINT_NOT_DISCOVERED", command.entrypoint) from error
        revision = file_revision(source_path.read_bytes())
        manifest = ProjectManifest(
            project_id=command.project_id,
            approved_root=str(root),
            framework="pytorch",
            entrypoint=command.entrypoint,
            environment=environment,
            resolved_config=command.resolved_config,
            patch_parameter_names=self._patch_parameter_names(command.project_id),
            source_revision=source_snapshot_revision({source_path.relative_to(root).as_posix(): revision}),
            file_revisions={source_path.relative_to(root).as_posix(): revision},
        )
        self._repository.save_manifest(manifest)
        self._repository.append_event(
            EngineEvent(
                event_id=f"engine-event:{command.project_id.removeprefix('project:')}-opened-{manifest.analysis_generation}",
                kind="project_opened",
                project_id=manifest.project_id,
                source_revision=manifest.source_revision,
                message="approved project opened",
            )
        )
        return manifest

    def _manifest(self, project_id: str) -> ProjectManifest:
        try:
            return self._repository.load_manifest(project_id)
        except FileNotFoundError as error:
            raise EngineRejected("PROJECT_NOT_OPEN", project_id) from error

    def _observe_revision(self, manifest: ProjectManifest) -> tuple[str, dict[str, str]]:
        observation = self._watcher.observe(manifest)
        return observation.source_revision, observation.file_revisions

    def refresh_project(self, project_id: str) -> RefreshResult:
        manifest = self._manifest(project_id)
        observed_revision, _ = self._observe_revision(manifest)
        stale = observed_revision != manifest.source_revision
        refreshed = manifest.model_copy(
            update={"source_status": ProjectSourceStatus.STALE if stale else ProjectSourceStatus.READY}
        )
        self._repository.save_manifest(refreshed)
        patches = self._repository.load_visual_patches(project_id)
        orphaned = sorted(
            patch.visual_patch_id for patch in patches if patch.base_source_revision != observed_revision
        )
        if stale:
            self._repository.append_event(
                EngineEvent(
                    event_id=f"engine-event:{project_id.removeprefix('project:')}-stale-{refreshed.analysis_generation}",
                    kind="source_stale",
                    project_id=refreshed.project_id,
                    source_revision=observed_revision,
                    message="source changed outside the engine",
                )
            )
        return RefreshResult(
            manifest=refreshed,
            observed_source_revision=observed_revision,
            stale_visual_patch_ids=orphaned,
        )

    def analyze_project(self, project_id: str) -> AnalysisResult:
        manifest = self._manifest(project_id)
        root = Path(manifest.approved_root).resolve(strict=True)
        source, architecture = self._adapter.analyze(
            root,
            project_id=manifest.project_id,
            entrypoint=manifest.entrypoint,
            resolved_config=manifest.resolved_config,
        )
        publication = self._compiler.compile(architecture)
        scene = self._layout.layout(publication)
        svg = render_svg(publication, scene)
        report = publication_preflight(publication, scene, svg)
        if report.blocking:
            raise EngineRejected("PUBLICATION_PREFLIGHT_FAILED", ",".join(issue.code for issue in report.issues))
        refreshed = manifest.model_copy(
            update={
                "source_revision": source.source_revision,
                "file_revisions": source.file_revisions,
                "source_status": ProjectSourceStatus.READY,
                "analysis_generation": manifest.analysis_generation + 1,
            }
        )
        self._repository.save_manifest(refreshed)
        relative_svg = self._repository.save_analysis(
            refreshed, source, architecture, publication, scene, svg
        )
        self._repository.append_event(
            EngineEvent(
                event_id=f"engine-event:{project_id.removeprefix('project:')}-analysis-{refreshed.analysis_generation}",
                kind="analysis_completed",
                project_id=refreshed.project_id,
                source_revision=refreshed.source_revision,
                message="static and publication analysis completed",
            )
        )
        return AnalysisResult(
            manifest=refreshed,
            source=source,
            architecture=architecture,
            publication=publication,
            scene=scene,
            svg=ArtifactReference(relative_path=relative_svg, sha256=sha256_digest(svg.encode("utf-8"))),
        )

    def load_analysis(self, project_id: str):
        """Load the last persisted read-only analysis bundle after an engine restart."""

        try:
            return self._repository.load_analysis(project_id)
        except FileNotFoundError as error:
            raise EngineRejected("ANALYSIS_NOT_AVAILABLE", project_id) from error

    def load_analysis_result(self, project_id: str) -> LoadedAnalysisResult:
        """Return persisted analysis through the same typed client boundary as live analysis."""

        manifest = self._manifest(project_id)
        source, architecture, publication, scene = self.load_analysis(project_id)
        try:
            svg = self._repository.artifact_bytes(project_id, "analysis/scene.svg")
        except FileNotFoundError as error:
            raise EngineRejected("ANALYSIS_ARTIFACT_NOT_AVAILABLE", project_id) from error
        return LoadedAnalysisResult(
            manifest=manifest,
            source=source,
            architecture=architecture,
            publication=publication,
            scene=scene,
            svg=ArtifactReference(relative_path="analysis/scene.svg", sha256=sha256_digest(svg)),
        )

    def resolve_source_anchor(self, command: ResolveSourceAnchorCommand) -> SourceLocationResult:
        """Return a cache-evidenced source location without granting source-byte access."""

        manifest = self._manifest(command.project_id)
        source, _, _, _ = self.load_analysis(command.project_id)
        try:
            anchor = next(anchor for anchor in source.anchors if anchor.anchor_id == command.anchor_id)
        except StopIteration as error:
            raise EngineRejected("SOURCE_ANCHOR_NOT_FOUND", command.anchor_id) from error
        root = Path(manifest.approved_root).resolve(strict=True)
        candidate = (root / anchor.relative_file).resolve(strict=False)
        if (
            not candidate.is_relative_to(root)
            or not candidate.is_file()
            or anchor.relative_file not in source.file_revisions
        ):
            raise EngineRejected("SOURCE_ANCHOR_OUTSIDE_APPROVED_ROOT", command.anchor_id)
        return SourceLocationResult(
            project_id=manifest.project_id,
            anchor_id=anchor.anchor_id,
            relative_file=anchor.relative_file,
            line=anchor.span.start.line,
            column=anchor.span.start.column,
        )

    def save_visual_patch(self, patch: VisualPatch) -> VisualPatchResult:
        manifest = self._manifest(patch.project_id)
        observed_revision, _ = self._observe_revision(manifest)
        if patch.base_source_revision != observed_revision:
            raise EngineRejected("VISUAL_PATCH_STALE", patch.visual_patch_id)
        try:
            _, _, publication, _ = self._repository.load_analysis(patch.project_id)
        except FileNotFoundError as error:
            raise EngineRejected("ANALYSIS_NOT_AVAILABLE", patch.project_id) from error
        if patch.publication_id != publication.publication_id:
            raise EngineRejected("VISUAL_PATCH_PUBLICATION_MISMATCH", patch.visual_patch_id)
        repeat_groups = {
            node.node_id for node in publication.nodes if node.kind.value == "repeat_group"
        }
        if not set(patch.expanded_node_ids) <= repeat_groups:
            raise EngineRejected("VISUAL_PATCH_EXPANSION_INVALID", patch.visual_patch_id)
        publication_node_ids = {node.node_id for node in publication.nodes}
        if any(annotation.target_node_id not in publication_node_ids for annotation in patch.annotations):
            raise EngineRejected("VISUAL_PATCH_ANNOTATION_INVALID", patch.visual_patch_id)
        self._repository.save_visual_patch(patch)
        self._repository.append_event(
            EngineEvent(
                event_id=f"engine-event:{patch.visual_patch_id.removeprefix('visual-patch:')}-saved",
                kind="visual_patch_saved",
                project_id=patch.project_id,
                source_revision=patch.base_source_revision,
                message="visual patch persisted",
            )
        )
        return VisualPatchResult(
            kind="visual_patch_saved", visual_patches=[patch], orphaned_visual_patch_ids=[]
        )

    def replay_visual_patches(self, project_id: str) -> VisualPatchResult:
        manifest = self._manifest(project_id)
        observed_revision, _ = self._observe_revision(manifest)
        patches = self._repository.load_visual_patches(project_id)
        orphaned = [
            patch.visual_patch_id
            for patch in patches
            if patch.base_source_revision != observed_revision
        ]
        return VisualPatchResult(
            kind="visual_patches_replayed",
            visual_patches=[patch for patch in patches if patch.visual_patch_id not in orphaned],
            orphaned_visual_patch_ids=sorted(orphaned),
        )

    def save_canvas_document(self, document: CanvasDocument) -> CanvasDocumentResult:
        """Persist a source-revision-bound visual document without touching source bytes."""

        manifest = self._manifest(document.project_id)
        observed_revision, _ = self._observe_revision(manifest)
        if document.base_source_revision != observed_revision:
            raise EngineRejected("CANVAS_DOCUMENT_STALE", document.canvas_document_id)
        try:
            _, _, publication, _ = self._repository.load_analysis(document.project_id)
        except FileNotFoundError as error:
            raise EngineRejected("ANALYSIS_NOT_AVAILABLE", document.project_id) from error
        if document.publication_id != publication.publication_id:
            raise EngineRejected("CANVAS_DOCUMENT_PUBLICATION_MISMATCH", document.canvas_document_id)
        publication_node_ids = {node.node_id for node in publication.nodes}
        document_node_ids = {node.publication_node_id for node in document.nodes}
        if document_node_ids != publication_node_ids:
            raise EngineRejected("CANVAS_DOCUMENT_NODE_SET_MISMATCH", document.canvas_document_id)
        self._repository.save_canvas_document(document)
        self._repository.append_event(
            EngineEvent(
                event_id=f"engine-event:{document.canvas_document_id.removeprefix('canvas-document:')}-saved",
                kind="canvas_document_saved",
                project_id=document.project_id,
                source_revision=document.base_source_revision,
                message="canvas document persisted without source modification",
            )
        )
        return CanvasDocumentResult(
            kind="canvas_document_saved",
            canvas_documents=[document],
            orphaned_canvas_document_ids=[],
        )

    def replay_canvas_documents(self, project_id: str) -> CanvasDocumentResult:
        manifest = self._manifest(project_id)
        observed_revision, _ = self._observe_revision(manifest)
        documents = self._repository.load_canvas_documents(project_id)
        orphaned = [
            document.canvas_document_id
            for document in documents
            if document.base_source_revision != observed_revision
        ]
        return CanvasDocumentResult(
            kind="canvas_documents_replayed",
            canvas_documents=[document for document in documents if document.canvas_document_id not in orphaned],
            orphaned_canvas_document_ids=sorted(orphaned),
        )

    def _patch_context(self, command: PatchCommand) -> tuple[ProjectManifest, object, object, Path, str]:
        if command.patch_set.project_id != command.project_id:
            raise EngineRejected("PATCH_PROJECT_ID_MISMATCH", command.patch_set.project_id)
        manifest = self._manifest(command.project_id)
        observed_revision, file_revisions = self._observe_revision(manifest)
        if observed_revision != manifest.source_revision:
            raise EngineRejected("PATCH_SOURCE_STALE", observed_revision)
        try:
            source, architecture, _, _ = self._repository.load_analysis(command.project_id)
        except FileNotFoundError as error:
            raise EngineRejected("ANALYSIS_NOT_AVAILABLE", command.project_id) from error
        if command.project_id not in self._patch_analyzers:
            raise EngineRejected("PATCH_ANALYZER_UNAVAILABLE", command.project_id)
        patch = command.patch_set.patches[0]
        anchor_id = (
            patch.target.anchor_id
            if isinstance(patch, SetParameterPatch)
            else patch.constructor_anchor_id
        )
        try:
            anchor = next(item for item in source.anchors if item.anchor_id == anchor_id)
        except StopIteration as error:
            raise EngineRejected("PATCH_TARGET_NOT_FOUND", anchor_id) from error
        relative_file = anchor.relative_file
        if relative_file not in file_revisions:
            raise EngineRejected("PATCH_FILE_NOT_IN_MANIFEST", relative_file)
        root = Path(manifest.approved_root).resolve(strict=True)
        path = (root / relative_file).resolve(strict=False)
        if not path.is_file() or not path.is_relative_to(root):
            raise EngineRejected("PATCH_FILE_OUTSIDE_APPROVED_ROOT", relative_file)
        return manifest, source, architecture, path, relative_file

    @staticmethod
    def _patch_result(
        kind: str,
        project_id: str,
        planned: _PlannedPatch,
        analysis: AnalysisResult | None = None,
    ) -> PatchResult:
        candidate = planned.candidate
        return PatchResult(
            kind=kind,  # type: ignore[arg-type]
            project_id=project_id,
            patch_set_id=planned.patch_set_id,
            patch_id=planned.patch_id,
            candidate_diff=candidate.diff,
            before_source_revision=candidate.before_source.source_revision,
            after_source_revision=candidate.after_source.source_revision,
            observed_delta=candidate.observed_delta,
            validation=candidate.validation,
            provenance=planned.provenance,
            risk=planned.risk,
            blocking=candidate.blocking,
            confirmation_id=planned.confirmation_id,
            runtime_validation=planned.runtime_validation,
            analysis=analysis,
        )

    def _validate_candidate_runtime(
        self,
        manifest: ProjectManifest,
        planned: _PlannedPatch,
        *,
        structural_change: bool,
    ) -> RuntimeTraceResult | None:
        profile = self._patch_runtime_profiles.get(manifest.project_id)
        if profile is None:
            if structural_change:
                raise EngineRejected("PATCH_RUNTIME_VALIDATION_REQUIRED", "structural patch requires a runtime profile")
            return None
        root = Path(manifest.approved_root).resolve(strict=True)
        with TemporaryDirectory(prefix="archcanvas-patch-runtime-") as temporary_directory:
            candidate_root = Path(temporary_directory) / "project"
            copytree(
                root,
                candidate_root,
                symlinks=True,
                ignore=ignore_patterns(".git", "__pycache__", ".venv", "venv", "build", "dist"),
            )
            symlink = next((path for path in candidate_root.rglob("*") if path.is_symlink()), None)
            if symlink is not None:
                raise EngineRejected(
                    "PATCH_RUNTIME_SYMLINK_UNSUPPORTED",
                    symlink.relative_to(candidate_root).as_posix(),
                )
            candidate_path = (candidate_root / planned.relative_file).resolve(strict=False)
            if not candidate_path.is_file() or not candidate_path.is_relative_to(candidate_root):
                raise EngineRejected("PATCH_RUNTIME_ENTRYPOINT_UNAVAILABLE", planned.relative_file)
            candidate_path.write_bytes(planned.candidate.candidate_bytes)
            entrypoint_file, _ = manifest.entrypoint.split(":", maxsplit=1)
            entrypoint_revision = planned.candidate.after_source.file_revisions.get(entrypoint_file)
            if entrypoint_revision is None:
                raise EngineRejected("PATCH_RUNTIME_ENTRYPOINT_UNAVAILABLE", entrypoint_file)
            request = TraceRequest(
                request_id=f"trace-request:patch-{token_urlsafe(12)}",
                project_root=str(candidate_root),
                python_executable=manifest.environment.python_executable,
                entrypoint=manifest.entrypoint,
                entrypoint_file_revision=entrypoint_revision,
                source_revision=planned.candidate.after_source.source_revision,
                environment_name=manifest.environment.environment_name,
                dependency_lockfile=manifest.environment.dependency_lockfile,
                constructor_kwargs=profile.constructor_kwargs,
                inputs=profile.inputs,
                provider=profile.provider,
                timeout_seconds=profile.timeout_seconds,
                memory_limit_mb=profile.memory_limit_mb,
                network_policy=profile.network_policy,
            )
            result = self._runtime_worker(request)
        if result.status is not TraceStatus.SUCCEEDED:
            detail = result.failure_code.value if result.failure_code is not None else result.status.value
            raise EngineRejected("PATCH_RUNTIME_VALIDATION_FAILED", f"{detail}: {result.message or ''}".strip())
        if structural_change:
            shape_validation = RuntimeShapeValidator().validate(
                planned.candidate.after_ir, result, structural_change=True
            )
            if shape_validation.blocking:
                raise EngineRejected(
                    "PATCH_RUNTIME_SHAPE_VALIDATION_FAILED", shape_validation.model_dump_json()
                )
        return result

    def plan_patch(self, command: PatchCommand) -> PatchResult:
        manifest, source, architecture, path, relative_file = self._patch_context(command)
        analyzer = self._patch_analyzers[command.project_id]
        try:
            if isinstance(command.patch_set.patches[0], SetParameterPatch):
                candidate = plan_set_parameter(
                    path.read_bytes(),
                    command.patch_set,
                    source,
                    architecture,
                    analyzer=analyzer,
                    runtime_validation_available=command.project_id in self._patch_runtime_profiles,
                )
            else:
                candidate = plan_insert_layer_norm(
                    path.read_bytes(), command.patch_set, source, architecture, analyzer=analyzer
                )
        except TransactionRejected as error:
            raise EngineRejected(error.code, error.message) from error
        patch = command.patch_set.patches[0]
        if isinstance(patch, SetParameterPatch):
            parameter = architecture.parameter(patch.target.node_id, patch.target.parameter)
            provenance = PatchProvenance(
                analyzer=getattr(analyzer, "__name__", analyzer.__class__.__name__),
                transform_id=resolve_parameter_transform(patch.target.parameter).transform_id,
                relative_file=relative_file,
                anchor_id=patch.target.anchor_id,
                node_id=patch.target.node_id,
                parameter=patch.target.parameter,
                origin=parameter.origin.kind.value,
                evidence=[item.description or item.source.value for item in parameter.evidence],
            )
            risk = PatchRisk(level="low", reasons=["literal source-backed parameter"])
        else:
            provenance = PatchProvenance(
                analyzer=getattr(analyzer, "__name__", analyzer.__class__.__name__),
                transform_id="insert_layer_norm_v1",
                relative_file=relative_file,
                anchor_id=patch.forward_anchor_id,
                node_id=patch.source_node_id,
                parameter=patch.operation,
                origin="source_proven_edge",
                evidence=["constructor and forward anchors", "declared node and edge graph delta"],
            )
            risk = PatchRisk(
                level="high",
                reasons=["structural splice requires isolated runtime shape validation"],
            )
        planned = _PlannedPatch(
            patch_set_id=command.patch_set.patch_set_id,
            patch_id=patch.patch_id,
            project_id=command.project_id,
            patch_set=command.patch_set,
            relative_file=relative_file,
            path=path,
            candidate=candidate,
            provenance=provenance,
            risk=risk,
        )
        self._planned_patches[(command.project_id, command.patch_set.patch_set_id)] = planned
        self._record_patch_event(
            kind="patch_planned",
            project_id=command.project_id,
            source_revision=candidate.before_source.source_revision,
            patch_id=patch.patch_id,
            message="candidate patch planned without source write",
        )
        return self._patch_result("patch_planned", manifest.project_id, planned)

    def validate_patch(self, command: PatchCommand) -> PatchResult:
        self._patch_context(command)
        key = (command.project_id, command.patch_set.patch_set_id)
        planned = self._planned_patches.get(key)
        if planned is None:
            raise EngineRejected("PATCH_PLAN_NOT_FOUND", command.patch_set.patch_set_id)
        if planned.patch_set != command.patch_set:
            raise EngineRejected("PATCH_PLAN_MISMATCH", command.patch_set.patch_set_id)
        runtime_validation = self._validate_candidate_runtime(
            self._manifest(command.project_id),
            planned,
            structural_change=isinstance(command.patch_set.patches[0], InsertLayerNormPatch),
        )
        planned = replace(
            planned,
            validated=True,
            confirmation_id=f"confirmation:{token_urlsafe(24)}",
            runtime_validation=runtime_validation,
        )
        self._planned_patches[key] = planned
        self._record_patch_event(
            kind="patch_validated",
            project_id=command.project_id,
            source_revision=planned.candidate.before_source.source_revision,
            patch_id=planned.patch_id,
            message=(
                "candidate patch validated with runtime evidence"
                if runtime_validation is not None
                else "candidate patch validated by static evidence"
            ),
        )
        return self._patch_result("patch_validated", command.project_id, planned)

    def commit_patch(self, command: PatchCommand) -> PatchResult:
        key = (command.project_id, command.patch_set.patch_set_id)
        planned = self._planned_patches.get(key)
        if planned is None:
            raise EngineRejected("PATCH_PLAN_NOT_FOUND", command.patch_set.patch_set_id)
        if planned.patch_set != command.patch_set:
            raise EngineRejected("PATCH_PLAN_MISMATCH", command.patch_set.patch_set_id)
        if not planned.validated or planned.confirmation_id is None:
            raise EngineRejected("PATCH_NOT_VALIDATED", command.patch_set.patch_set_id)
        if command.confirmation_id is None:
            raise EngineRejected("PATCH_CONFIRMATION_REQUIRED", command.patch_set.patch_set_id)
        if command.confirmation_id != planned.confirmation_id:
            raise EngineRejected("PATCH_CONFIRMATION_INVALID", command.patch_set.patch_set_id)
        manifest = self._manifest(command.project_id)
        try:
            previous_source, previous_architecture, previous_publication, previous_scene = self.load_analysis(
                command.project_id
            )
            previous_svg = self._repository.artifact_bytes(command.project_id, "analysis/scene.svg").decode("utf-8")
        except (FileNotFoundError, UnicodeDecodeError) as error:
            raise EngineRejected("ANALYSIS_ARTIFACT_NOT_AVAILABLE", command.project_id) from error
        observed_revision, _ = self._observe_revision(manifest)
        if observed_revision != manifest.source_revision:
            raise EngineRejected("PATCH_SOURCE_STALE", observed_revision)
        try:
            commit_candidate(planned.path, planned.candidate)
        except TransactionRejected as error:
            raise EngineRejected(error.code, error.message) from error
        # The confirmation capability is single-use even if post-commit analysis fails.
        self._planned_patches.pop(key, None)
        try:
            analysis = self.analyze_project(command.project_id)
        except Exception as error:
            try:
                restored = rollback_candidate(planned.path, planned.candidate)
            except OSError:
                restored = False
            if restored:
                try:
                    self._repository.save_manifest(manifest)
                    self._repository.save_analysis(
                        manifest,
                        previous_source,
                        previous_architecture,
                        previous_publication,
                        previous_scene,
                        previous_svg,
                    )
                except OSError as cache_error:
                    raise EngineRejected(
                        "POST_COMMIT_ANALYSIS_FAILED_ROLLED_BACK_CACHE_RESTORE_FAILED",
                        f"{error}; cache restore: {cache_error}",
                    ) from error
                self._record_patch_event(
                    kind="patch_rolled_back",
                    project_id=command.project_id,
                    source_revision=manifest.source_revision,
                    patch_id=planned.patch_id,
                    message="post-commit analysis failed; source and analysis cache restored",
                )
                raise EngineRejected("POST_COMMIT_ANALYSIS_FAILED_ROLLED_BACK", str(error)) from error
            raise EngineRejected("POST_COMMIT_ANALYSIS_FAILED_ROLLBACK_CONFLICT", str(error)) from error
        self._record_patch_event(
            kind="patch_committed",
            project_id=command.project_id,
            source_revision=analysis.manifest.source_revision,
            patch_id=planned.patch_id,
            message="candidate patch committed and re-analysis completed",
        )
        return self._patch_result("patch_committed", command.project_id, planned, analysis=analysis)

    def dispatch(self, request: EngineRequest) -> EngineResponse:
        command = request.command
        try:
            if isinstance(command, HealthCommand):
                result = HealthResult(
                    capabilities=[
                        "open_project", "analyze_project", "publication_svg", "canvas_document",
                        "plan_patch", "validate_patch", "commit_patch",
                    ]
                )
            elif isinstance(command, OpenProjectCommand):
                result = ProjectOpenedResult(manifest=self.open_project(command))
            elif isinstance(command, SaveVisualPatchCommand):
                result = self.save_visual_patch(command.visual_patch)
            elif isinstance(command, SaveCanvasDocumentCommand):
                result = self.save_canvas_document(command.canvas_document)
            elif isinstance(command, ResolveSourceAnchorCommand):
                result = self.resolve_source_anchor(command)
            elif isinstance(command, PatchCommand) and command.operation is EngineOperation.PLAN_PATCH:
                result = self.plan_patch(command)
            elif isinstance(command, PatchCommand) and command.operation is EngineOperation.VALIDATE_PATCH:
                result = self.validate_patch(command)
            elif isinstance(command, PatchCommand) and command.operation is EngineOperation.COMMIT_PATCH:
                result = self.commit_patch(command)
            elif isinstance(command, ProjectCommand) and command.operation is EngineOperation.ANALYZE_PROJECT:
                result = self.analyze_project(command.project_id)
            elif isinstance(command, ProjectCommand) and command.operation is EngineOperation.REFRESH_PROJECT:
                result = self.refresh_project(command.project_id)
            elif isinstance(command, ProjectCommand) and command.operation is EngineOperation.REPLAY_CANVAS_DOCUMENTS:
                result = self.replay_canvas_documents(command.project_id)
            elif isinstance(command, ProjectCommand) and command.operation is EngineOperation.LOAD_ANALYSIS:
                result = self.load_analysis_result(command.project_id)
            elif isinstance(command, ProjectCommand):
                result = self.replay_visual_patches(command.project_id)
            else:
                raise EngineRejected("UNSUPPORTED_OPERATION", str(command.operation))
            return EngineResponse(request_id=request.request_id, status="succeeded", result=result)
        except EngineRejected as error:
            if isinstance(command, PatchCommand):
                try:
                    manifest = self._manifest(command.project_id)
                    self._record_patch_event(
                        kind="patch_rejected",
                        project_id=command.project_id,
                        source_revision=manifest.source_revision,
                        patch_id=command.patch_set.patches[0].patch_id,
                        message=f"{error.code}: {error}",
                    )
                except (EngineRejected, IndexError):
                    pass
            return EngineResponse(
                request_id=request.request_id,
                status="rejected",
                error=EngineError(code=error.code, message=str(error)),
            )
        except TransactionRejected as error:
            return EngineResponse(
                request_id=request.request_id,
                status="rejected",
                error=EngineError(code=error.code, message=error.message),
            )
