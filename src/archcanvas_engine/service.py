"""The only Stage 5 business entrypoint for project analysis and visual history."""

from __future__ import annotations

from pathlib import Path

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
from archcanvas_publication import PublicationCompiler, StageLayout
from archcanvas_python.source_revision import file_revision
from archcanvas_pytorch.static import PyTorchProjectScanner, PyTorchProjectStaticAdapter
from archcanvas_renderer import publication_preflight, render_svg

from .environment import EnvironmentResolver
from .repository import EngineRepository
from .service_errors import EngineRejected
from .watcher import ProjectSourceWatcher


class ArchCanvasEngine:
    """Orchestrate approved projects without granting implicit source-write authority."""

    def __init__(self, cache_root: Path) -> None:
        self._repository = EngineRepository(cache_root)
        self._environment_resolver = EnvironmentResolver()
        self._watcher = ProjectSourceWatcher()
        self._scanner = PyTorchProjectScanner()
        self._adapter = PyTorchProjectStaticAdapter(project_scanner=self._scanner)
        self._compiler = PublicationCompiler()
        self._layout = StageLayout()

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

    def dispatch(self, request: EngineRequest) -> EngineResponse:
        command = request.command
        try:
            if isinstance(command, HealthCommand):
                result = HealthResult(
                    capabilities=["open_project", "analyze_project", "publication_svg", "canvas_document"]
                )
            elif isinstance(command, OpenProjectCommand):
                result = ProjectOpenedResult(manifest=self.open_project(command))
            elif isinstance(command, SaveVisualPatchCommand):
                result = self.save_visual_patch(command.visual_patch)
            elif isinstance(command, SaveCanvasDocumentCommand):
                result = self.save_canvas_document(command.canvas_document)
            elif isinstance(command, ResolveSourceAnchorCommand):
                result = self.resolve_source_anchor(command)
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
            return EngineResponse(
                request_id=request.request_id,
                status="rejected",
                error=EngineError(code=error.code, message=str(error)),
            )
