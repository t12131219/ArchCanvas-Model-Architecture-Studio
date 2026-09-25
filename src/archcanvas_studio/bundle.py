from __future__ import annotations

import difflib
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter

from archcanvas_core.models import (
    AgentProposal,
    ArchitectureIR,
    CanvasDocument,
    Diagnostic,
    DraftEdge,
    DraftGraphDocument,
    DraftNode,
    EditIntent,
    EditProofState,
    EditProofStatus,
    EvidenceRecord,
    FreeformSourceBufferPatch,
    FreeformSourcePatch,
    GraphDelta,
    PatchBatch,
    ProjectSession,
    ProposedConnection,
    PublicationHierarchy,
    PublicationView,
    RuntimeTrace,
    SearchSubject,
    SemanticAnnotationOverlay,
    SemanticParameterPatch,
    SemanticStructuralPatch,
    SourceFile,
    SourceSnapshot,
    SourceTransaction,
    SourceWorkspaceDocument,
    StagedSourceBuffer,
    TransactionState,
    ValidationRun,
    VisualPatch,
    VisualScene,
    VisualSpec,
    WritebackSummary,
)
from archcanvas_patterns import exact_ir_digest
from archcanvas_publication import (
    LAYOUT_MODES,
    build_scene,
    build_visual_spec,
    compile_hierarchy,
    expandable_node_ids,
    project_hierarchy,
    relayout_scene,
    render_svg,
    validate_geometry,
)
from archcanvas_transactions import (
    commit_transaction,
    discard_transaction,
    plan_connection,
    prepare_freeform_transaction,
    prepare_transaction,
    verify_transaction,
)

from .document import (
    apply_patch_batch,
    create_canvas_document,
    derive_view_state,
    load_canvas_document,
    materialize_scene,
    persist_canvas_document,
    source_binding_digest,
)
from .navigation import PROJECTIONS, build_navigation_projections
from .operations import (
    auto_layout_batch,
    build_search_index,
    run_validation,
    studio_fingerprint,
)
from .project import create_project_session, discover_project

STATIC_ROOT = Path(__file__).resolve().parent / "static"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _reachable_expansions(
    navigation: dict[str, object], projection: str, expanded_ids: set[str]
) -> set[str]:
    projections = navigation.get("projections", {})
    projection_data = projections.get(projection, {}) if isinstance(projections, dict) else {}
    rows = projection_data.get("nodes", []) if isinstance(projection_data, dict) else []
    parent_by_id = {
        str(row["id"]): (
            str(row["parent_id"]) if row.get("parent_id") is not None else None
        )
        for row in rows
        if isinstance(row, dict) and "id" in row
    }
    reachable: set[str] = set()
    pending = set(expanded_ids) & set(parent_by_id)
    changed = True
    while changed:
        changed = False
        for row_id in sorted(pending - reachable):
            parent_id = parent_by_id[row_id]
            if parent_id is None or parent_id in reachable:
                reachable.add(row_id)
                changed = True
    return reachable


@dataclass
class StudioBundle:
    artifact_path: Path
    workspace: Path
    static_dir: Path
    document_path: Path
    architecture: ArchitectureIR
    snapshot: SourceSnapshot
    evidence: list[EvidenceRecord]
    runtime_trace: RuntimeTrace | None
    runtime_node_evidence: dict[str, list[str]]
    semantic_overlay: SemanticAnnotationOverlay | None
    hierarchy: PublicationHierarchy
    views: dict[str, PublicationView]
    specs: dict[str, VisualSpec]
    base_scenes: dict[str, VisualScene]
    document: CanvasDocument
    project_session: ProjectSession
    project_discovery: dict[str, object]
    draft_path: Path
    draft: DraftGraphDocument
    source_workspace_path: Path
    source_workspace: SourceWorkspaceDocument
    search_index: list[SearchSubject]
    validation_runs: list[ValidationRun]
    navigation: dict[str, object]
    validation_generation: int = 0
    active_transaction: SourceTransaction | None = None
    active_proposal: AgentProposal | None = None

    def materialized_scenes(self) -> dict[str, VisualScene]:
        return {
            projection_id: materialize_scene(scene, self.document)
            for projection_id, scene in self.base_scenes.items()
        }

    def _expanded_hierarchy_ids(self) -> set[str]:
        state = derive_view_state(self.document)
        projection = str(state.get("navigation_view", "module"))
        expandable = expandable_node_ids(self.hierarchy)
        persisted = set(state.get(f"{projection}_expansion", []))
        reachable = _reachable_expansions(self.navigation, projection, persisted)
        if projection == "module":
            return reachable & expandable
        projections = self.navigation.get("projections", {})
        source = projections.get("source", {}) if isinstance(projections, dict) else {}
        rows = source.get("nodes", []) if isinstance(source, dict) else []
        expanded = reachable
        source_expandable = {
            str(row["id"])
            for row in rows
            if isinstance(row, dict) and int(row.get("child_count", 0)) > 0
        }
        if source_expandable and source_expandable <= expanded:
            return expandable
        visible_depth = max(
            (
                int(row.get("depth", 0))
                for row in rows
                if isinstance(row, dict) and row.get("id") in expanded
            ),
            default=0,
        )
        return {
            node.hierarchy_node_id
            for node in self.hierarchy.nodes
            if node.hierarchy_node_id in expandable and node.depth <= visible_depth
        }

    def recompile_projection(self) -> None:
        view = project_hierarchy(
            self.architecture, self.hierarchy, self._expanded_hierarchy_ids()
        )
        spec = build_visual_spec(view)
        layout_mode = str(derive_view_state(self.document).get("layout_mode", "auto"))
        scene = build_scene(view, spec, layout_mode)
        self.views = {view.projection_id: view}
        self.specs = {view.projection_id: spec}
        self.base_scenes = {view.projection_id: scene}

    def write_static(self) -> None:
        _write_static_bundle(self)

    def diagnostics(self) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        for scene in self.materialized_scenes().values():
            _, scene_diagnostics = validate_geometry(scene)
            diagnostics.extend(scene_diagnostics)
        return diagnostics

    def source_excerpt(
        self,
        path: str,
        start_line: int,
        end_line: int,
        *,
        context: int = 4,
    ) -> dict[str, object]:
        source_file = next((item for item in self.snapshot.source_files if item.path == path), None)
        if source_file is None:
            raise ValueError("source path is not part of the frozen snapshot")
        if start_line < 1 or end_line < start_line:
            raise ValueError("source excerpt line range is invalid")
        if not 0 <= context <= 12:
            raise ValueError("source excerpt context must be between 0 and 12")

        root = Path(self.snapshot.project_root).resolve()
        target = (root / source_file.path).resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise ValueError("source path escapes the frozen project root") from error
        if not target.is_file():
            raise ValueError("source file from the frozen snapshot is unavailable")
        payload = target.read_bytes()
        if hashlib.sha256(payload).hexdigest() != source_file.sha256:
            raise ValueError("source file no longer matches the frozen snapshot")

        lines = payload.decode("utf-8").splitlines()
        excerpt_start = max(1, start_line - context)
        excerpt_end = min(len(lines), min(end_line, start_line + 79) + context)
        highlight_end = min(end_line, start_line + 79, len(lines))
        return {
            "path": source_file.path,
            "sha256": source_file.sha256,
            "revision": self.snapshot.revision,
            "start_line": excerpt_start,
            "end_line": excerpt_end,
            "highlight_start_line": start_line,
            "highlight_end_line": highlight_end,
            "lines": [
                {"number": number, "text": lines[number - 1]}
                for number in range(excerpt_start, excerpt_end + 1)
            ],
        }

    def _source_workspace_target(self, path: str) -> tuple[Path, SourceFile]:
        source_file = next(
            (item for item in self.snapshot.source_files if item.path == path), None
        )
        if source_file is None:
            raise ValueError("source path is not part of the frozen snapshot")
        if Path(path).suffix not in {".py", ".json"}:
            raise ValueError("source workspace only edits snapshot Python and JSON files")
        root = Path(self.snapshot.project_root).resolve()
        unresolved = root / path
        if unresolved.is_symlink():
            raise ValueError("source workspace cannot edit symbolic links")
        target = unresolved.resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError("source workspace path is unavailable")
        if target.stat().st_size > 1_000_000:
            raise ValueError("source workspace file exceeds the 1 MB editing limit")
        return target, source_file

    def _working_source(self, path: str) -> tuple[bytes, str]:
        target, _ = self._source_workspace_target(path)
        content = target.read_bytes()
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("source workspace file is not UTF-8 text") from error
        return content, hashlib.sha256(content).hexdigest()

    def source_workspace_summary(self) -> dict[str, object]:
        buffers = {buffer.path: buffer for buffer in self.source_workspace.buffers}
        files: list[dict[str, object]] = []
        any_stale = False
        any_modified = False
        for source_file in sorted(self.snapshot.source_files, key=lambda item: item.path):
            if Path(source_file.path).suffix not in {".py", ".json"}:
                continue
            buffer = buffers.get(source_file.path)
            try:
                working, working_sha256 = self._working_source(source_file.path)
                readonly_reason = None
                size = len(working)
            except ValueError as error:
                working_sha256 = None
                readonly_reason = str(error)
                size = 0
            staged_sha256 = (
                hashlib.sha256(buffer.staged_content.encode("utf-8")).hexdigest()
                if buffer is not None
                else None
            )
            stale = working_sha256 != source_file.sha256
            modified = buffer is not None and staged_sha256 != buffer.base_sha256
            any_stale = any_stale or stale
            any_modified = any_modified or modified
            files.append(
                {
                    "path": source_file.path,
                    "base_sha256": source_file.sha256,
                    "staged_sha256": staged_sha256,
                    "working_sha256": working_sha256,
                    "state": (
                        "readonly"
                        if readonly_reason
                        else "stale"
                        if stale
                        else "modified"
                        if modified
                        else "clean"
                    ),
                    "opened": buffer is not None,
                    "size": size,
                    "readonly_reason": readonly_reason,
                }
            )
        return {
            "workspace_id": self.source_workspace.workspace_id,
            "revision": self.source_workspace.revision,
            "base_revision": self.source_workspace.base_revision,
            "state": "stale" if any_stale else "modified" if any_modified else "clean",
            "files": files,
        }

    def open_source_buffer(self, path: str) -> dict[str, object]:
        existing = next(
            (buffer for buffer in self.source_workspace.buffers if buffer.path == path), None
        )
        if existing is None:
            working, working_sha256 = self._working_source(path)
            _, source_file = self._source_workspace_target(path)
            if working_sha256 != source_file.sha256:
                raise ValueError("working source changed since the frozen snapshot")
            base_content = working.decode("utf-8")
            existing = StagedSourceBuffer(
                path=path,
                base_sha256=source_file.sha256,
                base_content=base_content,
                staged_content=base_content,
            )
            self.source_workspace = self.source_workspace.model_copy(
                update={
                    "revision": self.source_workspace.revision + 1,
                    "buffers": [*self.source_workspace.buffers, existing],
                }
            )
            _write_json(self.source_workspace_path, self.source_workspace)
        return self.source_buffer(path)

    def source_buffer(self, path: str) -> dict[str, object]:
        buffer = next(
            (item for item in self.source_workspace.buffers if item.path == path), None
        )
        if buffer is None:
            raise ValueError("source buffer is not open")
        working, working_sha256 = self._working_source(path)
        staged_bytes = buffer.staged_content.encode("utf-8")
        staged_sha256 = hashlib.sha256(staged_bytes).hexdigest()
        diff = "".join(
            difflib.unified_diff(
                buffer.base_content.splitlines(keepends=True),
                buffer.staged_content.splitlines(keepends=True),
                fromfile=f"a/{buffer.path}",
                tofile=f"b/{buffer.path}",
            )
        )
        return {
            "path": buffer.path,
            "revision": self.source_workspace.revision,
            "base_sha256": buffer.base_sha256,
            "staged_sha256": staged_sha256,
            "working_sha256": working_sha256,
            "state": (
                "stale"
                if working_sha256 != buffer.base_sha256
                else "modified"
                if staged_sha256 != buffer.base_sha256
                else "clean"
            ),
            "base_content": buffer.base_content,
            "staged_content": buffer.staged_content,
            "working_content": working.decode("utf-8"),
            "diff": diff,
        }

    def save_source_buffer(
        self, path: str, content: str, base_sha256: str, expected_revision: int
    ) -> dict[str, object]:
        if expected_revision != self.source_workspace.revision:
            raise ValueError("source workspace revision is stale")
        if self.active_transaction is not None and self.active_transaction.state not in {
            TransactionState.COMMITTED,
            TransactionState.DISCARDED,
            TransactionState.FAILED,
        }:
            raise ValueError("source buffers are locked while a transaction is active")
        if "\x00" in content or len(content.encode("utf-8")) > 1_000_000:
            raise ValueError("staged source buffer is not valid bounded UTF-8 text")
        buffer = next(
            (item for item in self.source_workspace.buffers if item.path == path), None
        )
        if buffer is None:
            raise ValueError("source buffer is not open")
        if buffer.base_sha256 != base_sha256:
            raise ValueError("source buffer base binding is stale")
        updated = buffer.model_copy(update={"staged_content": content})
        self.source_workspace = self.source_workspace.model_copy(
            update={
                "revision": self.source_workspace.revision + 1,
                "buffers": [
                    updated if item.path == path else item
                    for item in self.source_workspace.buffers
                ],
            }
        )
        _write_json(self.source_workspace_path, self.source_workspace)
        return self.source_buffer(path)

    def discard_source_buffer(self, path: str, expected_revision: int) -> None:
        if expected_revision != self.source_workspace.revision:
            raise ValueError("source workspace revision is stale")
        if not any(item.path == path for item in self.source_workspace.buffers):
            raise ValueError("source buffer is not open")
        self.source_workspace = self.source_workspace.model_copy(
            update={
                "revision": self.source_workspace.revision + 1,
                "buffers": [
                    item for item in self.source_workspace.buffers if item.path != path
                ],
            }
        )
        _write_json(self.source_workspace_path, self.source_workspace)

    def prepare_source_workspace(self) -> None:
        modified = [
            buffer
            for buffer in self.source_workspace.buffers
            if hashlib.sha256(buffer.staged_content.encode("utf-8")).hexdigest()
            != buffer.base_sha256
        ]
        if not modified:
            raise ValueError("source workspace has no staged changes")
        request = FreeformSourcePatch(
            patch_id=f"patch:source-workspace.{self.source_workspace.revision}",
            artifact_path=str(self.artifact_path),
            buffers=[
                FreeformSourceBufferPatch(
                    path=buffer.path,
                    base_sha256=buffer.base_sha256,
                    content=buffer.staged_content,
                )
                for buffer in modified
            ],
        )
        transaction, _ = prepare_freeform_transaction(request, self.workspace)
        transaction, _ = verify_transaction(
            self.workspace / "transactions" / transaction.transaction_id
        )
        self.active_transaction = transaction
        self.active_proposal = None

    def discard_source_workspace(self) -> None:
        if self.active_transaction is not None and self.active_transaction.state not in {
            TransactionState.COMMITTED,
            TransactionState.DISCARDED,
            TransactionState.FAILED,
        }:
            transaction, _ = discard_transaction(
                self.workspace / "transactions" / self.active_transaction.transaction_id
            )
            self.active_transaction = transaction
        self.source_workspace = self.source_workspace.model_copy(
            update={"revision": self.source_workspace.revision + 1, "buffers": []}
        )
        _write_json(self.source_workspace_path, self.source_workspace)

    def state(self) -> dict[str, object]:
        scenes = self.materialized_scenes()
        view_state = derive_view_state(self.document)
        navigation = dict(self.navigation)
        navigation["active_projection"] = view_state.get("navigation_view", "module")
        return {
            "schema_version": "1.0",
            "project": self.project_session.model_dump(mode="json"),
            "discovery": self.project_discovery,
            "architecture": self.architecture.model_dump(mode="json"),
            "snapshot": self.snapshot.model_dump(mode="json"),
            "evidence": [record.model_dump(mode="json") for record in self.evidence],
            "runtime": (
                {
                    "trace": self.runtime_trace.model_dump(mode="json"),
                    "node_evidence": self.runtime_node_evidence,
                }
                if self.runtime_trace is not None
                else None
            ),
            "semantic_overlay": (
                self.semantic_overlay.model_dump(mode="json")
                if self.semantic_overlay is not None
                else None
            ),
            "hierarchy": self.hierarchy.model_dump(mode="json"),
            "active_projection_id": next(iter(self.views)),
            "views": {
                projection_id: view.model_dump(mode="json")
                for projection_id, view in self.views.items()
            },
            "specs": {
                projection_id: spec.model_dump(mode="json")
                for projection_id, spec in self.specs.items()
            },
            "scenes": {
                projection_id: scene.model_dump(mode="json")
                for projection_id, scene in scenes.items()
            },
            "document": self.document.model_dump(mode="json"),
            "draft": self.draft.model_dump(mode="json"),
            "source_workspace": self.source_workspace_summary(),
            "view_state": view_state,
            "navigation": navigation,
            "diagnostics": [item.model_dump(mode="json") for item in self.diagnostics()],
            "search_subject_count": len(self.search_index),
            "validation_runs": [
                run.model_dump(mode="json") for run in self.validation_runs[-20:]
            ],
            "transaction": (
                self.active_transaction.model_dump(mode="json")
                if self.active_transaction is not None
                else None
            ),
            "proposal": (
                self.active_proposal.model_dump(mode="json")
                if self.active_proposal is not None
                else None
            ),
            "capabilities": {
                "visual_editing": True,
                "source_editing": True,
                "semantic_transforms": [
                    "set_parameter",
                    "replace_activation",
                    "insert_layer_norm",
                ],
                "proposed_connection": True,
                "runtime_evidence": self.runtime_trace is not None,
                "project_analysis": True,
                "patch_batches": True,
                "search_index": True,
                "draft_node_authoring": {
                    "status": "available",
                    "writeback": "proposal-unless-adapter-lowering-is-proven",
                },
                "arbitrary_draft_node_lowering": {
                    "status": "unavailable",
                    "reason": "Unknown node types require a framework adapter lowering and proof.",
                },
                "staged_multi_file_source_editor": {
                    "status": "available",
                    "scope": "frozen-snapshot-python-and-json",
                    "writeback": "validate-review-explicit-commit",
                },
                "navigation_projections": list(PROJECTIONS),
                "layout_modes": list(LAYOUT_MODES),
                "validation_profiles": [
                    "fast-static",
                    "publication",
                    "full",
                    "runtime-replay",
                ],
            },
        }

    def set_navigation_view(
        self,
        projection: str,
        expanded_ids: list[str] | None = None,
        expansions: dict[str, list[str]] | None = None,
    ) -> None:
        if projection not in PROJECTIONS:
            raise ValueError(f"unknown navigation projection: {projection}")
        state = dict(self.document.view_state)
        state["navigation_view"] = projection
        state.pop("active_level", None)

        def validate_expansion(kind: str, values: list[str]) -> list[str]:
            projections = self.navigation.get("projections")
            if not isinstance(projections, dict):
                raise TypeError("navigation projections are unavailable")
            projection_data = projections.get(kind)
            if not isinstance(projection_data, dict):
                raise TypeError("navigation projection is unavailable")
            rows = projection_data.get("nodes")
            if not isinstance(rows, list):
                raise TypeError("navigation rows are unavailable")
            known_ids = {
                str(row["id"])
                for row in rows
                if isinstance(row, dict) and "id" in row
            }
            if any(item not in known_ids for item in values):
                raise ValueError("navigation expansion references an unknown row")
            return sorted(set(values))

        if expansions is not None:
            if set(expansions) != set(PROJECTIONS):
                raise ValueError("navigation expansions must include every projection")
            for kind in PROJECTIONS:
                state[f"{kind}_expansion"] = validate_expansion(kind, expansions[kind])
        elif expanded_ids is not None:
            state[f"{projection}_expansion"] = validate_expansion(
                projection, expanded_ids
            )
        self.save_document(self.document.model_copy(update={"view_state": state}))
        self.recompile_projection()

    def set_layout_mode(self, layout_mode: str) -> None:
        if layout_mode not in LAYOUT_MODES:
            raise ValueError(f"unknown layout mode: {layout_mode}")
        state = dict(self.document.view_state)
        state["layout_mode"] = layout_mode
        self.save_document(self.document.model_copy(update={"view_state": state}))
        self.recompile_projection()

    def layout_candidates(self, limit: int = 3) -> list[tuple[dict[str, object], PatchBatch]]:
        """Build deterministic, geometry-valid layout previews without mutating the document."""
        if limit < 1:
            raise ValueError("layout candidate limit must be positive")
        projection_id = next(iter(self.views))
        current = self.materialized_scenes()[projection_id]
        base = self.base_scenes[projection_id]
        pinned_ids = set(derive_view_state(self.document).get("pinned_node_ids", []))
        fingerprint = studio_fingerprint(self)
        current_by_id = {node.scene_node_id: node for node in current.nodes}
        seen_geometry: set[str] = set()
        candidates: list[tuple[dict[str, object], PatchBatch]] = []
        targets = [
            ("compiler", base),
            *(
                (layout_mode, relayout_scene(current, layout_mode))
                for layout_mode in ("force-directed", "radial", "orthogonal")
            ),
        ]
        for layout_mode, target in targets:
            try:
                batch = auto_layout_batch(
                    current,
                    baseline_scene=target,
                    pinned_ids=pinned_ids,
                    batch_id=f"batch:layout.{fingerprint[:12]}.{layout_mode}",
                )
            except ValueError as error:
                if str(error) == "the current scene is already at its deterministic layout":
                    continue
                raise
            target_by_id = {node.scene_node_id: node for node in target.nodes}
            size_patches = [
                VisualPatch(
                    patch_id=(
                        f"patch:{batch.batch_id.removeprefix('batch:')}.size.{index}"
                    ),
                    operation="set-size",
                    target_id=node_id,
                    value={
                        "scene_id": current.scene_id,
                        "width": max(
                            current_by_id[node_id].bounds.width,
                            target_by_id[node_id].bounds.width,
                        ),
                        "height": max(
                            current_by_id[node_id].bounds.height,
                            target_by_id[node_id].bounds.height,
                        ),
                    },
                )
                for index, node_id in enumerate(sorted(current_by_id))
                if node_id not in pinned_ids
                if (
                    current_by_id[node_id].bounds.width,
                    current_by_id[node_id].bounds.height,
                )
                != (
                    max(
                        current_by_id[node_id].bounds.width,
                        target_by_id[node_id].bounds.width,
                    ),
                    max(
                        current_by_id[node_id].bounds.height,
                        target_by_id[node_id].bounds.height,
                    ),
                )
            ]
            manual_route_ids = {
                patch.target_id
                for patch in self.document.visual_patches
                if patch.operation == "set-route-hint" and patch.target_id is not None
            }
            route_patches = [
                VisualPatch(
                    patch_id=(
                        f"patch:{batch.batch_id.removeprefix('batch:')}.route.{index}"
                    ),
                    operation="set-route-hint",
                    target_id=edge.scene_edge_id,
                    value={
                        "scene_id": current.scene_id,
                        "points": [point.model_dump(mode="json") for point in edge.points],
                    },
                )
                for index, edge in enumerate(target.edges)
                if edge.scene_edge_id not in manual_route_ids
            ]
            batch = batch.model_copy(
                update={"patches": [*batch.patches, *size_patches, *route_patches]}
            )
            preview_document = apply_patch_batch(
                self.document, batch, {base.scene_id: base}
            )
            preview = materialize_scene(base, preview_document)
            preview_by_id = {node.scene_node_id: node for node in preview.nodes}
            if any(
                preview_by_id[node_id].bounds != current_by_id[node_id].bounds
                for node_id in pinned_ids
                if node_id in current_by_id and node_id in preview_by_id
            ):
                continue
            gate, diagnostics = validate_geometry(preview)
            if gate.status != "passed":
                continue
            geometry_payload = [
                (
                    node.scene_node_id,
                    node.bounds.x,
                    node.bounds.y,
                    node.bounds.width,
                    node.bounds.height,
                )
                for node in preview.nodes
            ]
            geometry_digest = hashlib.sha256(
                json.dumps(geometry_payload, separators=(",", ":")).encode()
            ).hexdigest()
            if geometry_digest in seen_geometry:
                continue
            seen_geometry.add(geometry_digest)
            movement = sum(
                abs(node.bounds.x - current_by_id[node.scene_node_id].bounds.x)
                + abs(node.bounds.y - current_by_id[node.scene_node_id].bounds.y)
                for node in preview.nodes
            )
            route_length = sum(
                abs(end.x - start.x) + abs(end.y - start.y)
                for edge in preview.edges
                for start, end in zip(edge.points, edge.points[1:])
            )
            area = preview.paper_width * preview.paper_height
            score = round(area / 1000.0 + route_length + movement * 0.2, 3)
            candidate_digest = hashlib.sha256(
                f"{fingerprint}:{layout_mode}:{geometry_digest}".encode()
            ).hexdigest()
            payload: dict[str, object] = {
                "candidate_id": f"layoutcandidate:{candidate_digest[:20]}",
                "input_fingerprint": fingerprint,
                "strategy": layout_mode,
                "score": score,
                "metrics": {
                    "paper_area": round(area, 3),
                    "route_length": round(route_length, 3),
                    "movement": round(movement, 3),
                    "changed_nodes": len(
                        {
                            patch.target_id
                            for patch in batch.patches
                            if patch.operation in {"set-position", "set-size"}
                        }
                    ),
                    "route_changes": len(route_patches),
                },
                "supported_fixes": [],
                "diagnostics": [
                    diagnostic.model_dump(mode="json") for diagnostic in diagnostics
                ],
                "scene": preview.model_dump(mode="json"),
            }
            candidates.append((payload, batch))
        candidates.sort(
            key=lambda item: (float(item[0]["score"]), str(item[0]["strategy"]))
        )
        return candidates[:limit]

    def search(self, query: str, limit: int = 50) -> list[dict[str, object]]:
        from .operations import search_subjects

        return [
            subject.model_dump(mode="json")
            for subject in search_subjects(self.search_index, query, limit)
        ]

    def validate(
        self, profile: str, *, runtime_execution_authorized: bool = False
    ) -> ValidationRun:
        self.validation_generation += 1
        validation = run_validation(
            self,
            profile,
            self.validation_generation,
            runtime_execution_authorized=runtime_execution_authorized,
        )
        self.validation_runs.append(validation)
        _write_json(
            self.workspace / "validations" / f"{validation.validation_id.removeprefix('validation:')}.json",
            validation,
        )
        return validation

    def save_draft(self, draft: DraftGraphDocument, expected_revision: int) -> None:
        if expected_revision != self.draft.revision:
            raise ValueError("draft revision is stale")
        if draft.base_architecture_id != self.architecture.architecture_id:
            raise ValueError("draft belongs to another architecture")
        if draft.base_source_digest != self.document.source_digest:
            raise ValueError("draft source binding is stale")
        if draft.revision != expected_revision + 1:
            raise ValueError("draft revision must advance exactly once")
        current_proofs = {proof.intent_id: proof for proof in self.draft.proofs}
        for proof in draft.proofs:
            if (
                proof.status in {EditProofState.PROVEN, EditProofState.REVIEW_READY}
                and current_proofs.get(proof.intent_id) != proof
            ):
                raise ValueError("client-authored drafts cannot grant proven writeback status")
        _write_json(self.draft_path, draft)
        self.draft = draft

    def propose_draft_node(self, payload: dict[str, object]) -> None:
        node = DraftNode.model_validate(payload["node"])
        if node.framework != self.architecture.framework:
            raise ValueError("draft node framework does not match the active architecture")
        if any(item.node_id == node.node_id for item in self.draft.nodes):
            raise ValueError("draft node identifier already exists")
        intent_id = str(payload.get("intent_id", node.node_id.replace("draft:", "intent:", 1)))
        intent = EditIntent(
            intent_id=intent_id,
            kind="create-node",
            target_ids=[node.node_id],
            preconditions=["registered framework lowering", "exact source anchor", "bounded Graph Delta"],
            user_input=node.model_dump(mode="json"),
            capability_requirement=f"semantic.create-node.{node.framework}.{node.node_type}",
        )
        proof = EditProofStatus(
            intent_id=intent_id,
            status=EditProofState.UNPROVEN,
            writeback_eligibility="blocked",
            reason_codes=["UNREGISTERED_NODE_LOWERING"],
            message=(
                f"No registered {node.framework} lowering proves how to create {node.node_type}."
            ),
            affected_subject_ids=[node.node_id],
            required_facts=["constructor anchor", "input/output compatibility", "delta oracle"],
            supported_fixes=["Register and test a framework-specific create-node lowering."],
            checked_generation=self.project_session.generation,
            input_fingerprint=studio_fingerprint(self),
        )
        self.active_proposal = AgentProposal(
            proposal_id=f"proposal:{intent_id.removeprefix('intent:')}",
            reason_code="UNSUPPORTED_STRUCTURAL_INTENT",
            summary=proof.message,
            requested_intent=intent.model_dump(mode="json"),
            source_context={
                "architecture_id": self.architecture.architecture_id,
                "source_digest": self.document.source_digest,
            },
        )
        draft = self.draft.model_copy(
            update={
                "revision": self.draft.revision + 1,
                "nodes": [*self.draft.nodes, node],
                "intents": [*self.draft.intents, intent],
                "proofs": [*self.draft.proofs, proof],
                "lowering_status": "blocked",
                "writeback_summary": WritebackSummary(
                    eligibility="blocked",
                    blocking_intent_ids=[
                        *self.draft.writeback_summary.blocking_intent_ids,
                        intent_id,
                    ],
                ),
            }
        )
        self.draft = DraftGraphDocument.model_validate(draft.model_dump(mode="json"))
        _write_json(self.draft_path, self.draft)

    def delete_draft_node(self, node_id: str) -> None:
        node = next((item for item in self.draft.nodes if item.node_id == node_id), None)
        if node is None:
            raise ValueError("draft node does not exist")
        port_ids = {port.port_id for port in node.ports}
        removed_edges = {
            edge.edge_id
            for edge in self.draft.edges
            if edge.source_port_id in port_ids or edge.target_port_id in port_ids
        }
        removed_subjects = {node_id, *port_ids, *removed_edges}
        removed_intents = {
            intent.intent_id
            for intent in self.draft.intents
            if removed_subjects.intersection(intent.target_ids)
        }
        intents = [
            intent
            for intent in self.draft.intents
            if intent.intent_id not in removed_intents
        ]
        proofs = [
            proof for proof in self.draft.proofs if proof.intent_id not in removed_intents
        ]
        blocking = [
            intent_id
            for intent_id in self.draft.writeback_summary.blocking_intent_ids
            if intent_id not in removed_intents
        ]
        draft = self.draft.model_copy(
            update={
                "revision": self.draft.revision + 1,
                "nodes": [item for item in self.draft.nodes if item.node_id != node_id],
                "edges": [
                    edge for edge in self.draft.edges if edge.edge_id not in removed_edges
                ],
                "intents": intents,
                "proofs": proofs,
                "lowering_status": "blocked" if proofs else "not-planned",
                "writeback_summary": WritebackSummary(
                    eligibility="blocked",
                    blocking_intent_ids=blocking,
                ),
            }
        )
        self.draft = DraftGraphDocument.model_validate(draft.model_dump(mode="json"))
        self.active_proposal = None
        _write_json(self.draft_path, self.draft)

    def _draft_port_owner(self, port_id: str) -> tuple[str, str, str, bool]:
        matches: list[tuple[str, str, str, bool]] = []
        for node in self.architecture.nodes:
            matches.extend(
                (node.node_id, port.direction, port.role, False)
                for port in [*node.input_ports, *node.output_ports]
                if port.port_id == port_id
            )
        for node in self.draft.nodes:
            matches.extend(
                (node.node_id, port.direction, port.role, True)
                for port in node.ports
                if port.port_id == port_id
            )
        if not matches:
            raise ValueError(f"draft edge references an unknown port: {port_id}")
        if len(matches) > 1:
            raise ValueError(f"draft edge references an ambiguous port: {port_id}")
        return matches[0]

    def propose_draft_edge(self, payload: dict[str, object]) -> None:
        edge = DraftEdge.model_validate(payload["edge"])
        if any(item.edge_id == edge.edge_id for item in self.draft.edges):
            raise ValueError("draft edge identifier already exists")
        source_node_id, source_direction, source_role, source_is_draft = (
            self._draft_port_owner(edge.source_port_id)
        )
        target_node_id, target_direction, _, target_is_draft = self._draft_port_owner(
            edge.target_port_id
        )
        if source_direction != "output":
            raise ValueError("draft edge source must reference an output port")
        if target_direction != "input":
            raise ValueError("draft edge target must reference an input port")

        intent_id = str(payload.get("intent_id", edge.edge_id.replace("draft:", "intent:", 1)))
        intent = EditIntent(
            intent_id=intent_id,
            kind="connect-ports",
            target_ids=[
                edge.edge_id,
                source_node_id,
                edge.source_port_id,
                target_node_id,
                edge.target_port_id,
            ],
            preconditions=[
                "authored output port",
                "authored input port",
                "proven tensor compatibility",
                "registered connection lowering",
            ],
            user_input={
                **edge.model_dump(mode="json"),
                "source_node_id": source_node_id,
                "target_node_id": target_node_id,
            },
            capability_requirement=f"semantic.connect-ports.{edge.policy}",
        )
        if source_is_draft or target_is_draft:
            reason_code = "UNSUPPORTED_STRUCTURAL_INTENT"
            summary = (
                "The draft connection is recorded for review, but an endpoint has no "
                "canonical source lowering."
            )
            proof_state = EditProofState.UNPROVEN
            source_context = {
                "architecture_id": self.architecture.architecture_id,
                "source_node_id": source_node_id,
                "source_port_id": edge.source_port_id,
                "target_node_id": target_node_id,
                "target_port_id": edge.target_port_id,
                "compatibility": "unresolved",
                "registry_match": None,
            }
            proposal = AgentProposal(
                proposal_id=f"proposal:{edge.edge_id.removeprefix('draft:')}",
                reason_code=reason_code,
                summary=summary,
                requested_intent=intent.model_dump(mode="json"),
                source_context=source_context,
            )
        else:
            request = ProposedConnection(
                proposal_id=f"proposal:{edge.edge_id.removeprefix('draft:')}",
                artifact_path=str(self.artifact_path),
                source_node_id=source_node_id,
                source_port_id=edge.source_port_id,
                target_node_id=target_node_id,
                target_port_id=edge.target_port_id,
                role=source_role,
            )
            proposal = plan_connection(request, self.architecture)
            reason_code = proposal.reason_code
            summary = proposal.summary
            proof_state = (
                EditProofState.INVALID
                if reason_code == "INCOMPATIBLE_PORTS"
                else EditProofState.UNPROVEN
            )

        proof = EditProofStatus(
            intent_id=intent_id,
            status=proof_state,
            writeback_eligibility="blocked",
            reason_codes=[reason_code],
            message=summary,
            affected_subject_ids=intent.target_ids,
            required_facts=["tensor shape compatibility", "exact source anchors"],
            supported_fixes=["Register and test a framework-specific connection lowering."],
            checked_generation=self.project_session.generation,
            input_fingerprint=studio_fingerprint(self),
        )
        draft = self.draft.model_copy(
            update={
                "revision": self.draft.revision + 1,
                "edges": [*self.draft.edges, edge],
                "intents": [*self.draft.intents, intent],
                "proofs": [*self.draft.proofs, proof],
                "lowering_status": "blocked",
                "writeback_summary": WritebackSummary(
                    eligibility="blocked",
                    blocking_intent_ids=[
                        *self.draft.writeback_summary.blocking_intent_ids,
                        intent_id,
                    ],
                ),
            }
        )
        self.draft = DraftGraphDocument.model_validate(draft.model_dump(mode="json"))
        self.active_proposal = proposal
        _write_json(self.draft_path, self.draft)

    def delete_draft_edge(self, edge_id: str) -> None:
        edge = next((item for item in self.draft.edges if item.edge_id == edge_id), None)
        if edge is None:
            raise ValueError("draft edge does not exist")
        removed_intents = {
            intent.intent_id
            for intent in self.draft.intents
            if edge_id in intent.target_ids
        }
        intents = [
            intent for intent in self.draft.intents if intent.intent_id not in removed_intents
        ]
        proofs = [
            proof for proof in self.draft.proofs if proof.intent_id not in removed_intents
        ]
        blocking = [
            intent_id
            for intent_id in self.draft.writeback_summary.blocking_intent_ids
            if intent_id not in removed_intents
        ]
        draft = self.draft.model_copy(
            update={
                "revision": self.draft.revision + 1,
                "edges": [item for item in self.draft.edges if item.edge_id != edge_id],
                "intents": intents,
                "proofs": proofs,
                "lowering_status": "blocked" if proofs else "not-planned",
                "writeback_summary": WritebackSummary(
                    eligibility="blocked",
                    blocking_intent_ids=blocking,
                ),
            }
        )
        self.draft = DraftGraphDocument.model_validate(draft.model_dump(mode="json"))
        self.active_proposal = None
        _write_json(self.draft_path, self.draft)

    def canonical_delete_impact(self, node_id: str) -> dict[str, object]:
        node = next((item for item in self.architecture.nodes if item.node_id == node_id), None)
        if node is None:
            raise ValueError("canonical delete references an unknown node")
        incoming_edges = [
            edge for edge in self.architecture.edges if edge.consumer_id == node_id
        ]
        outgoing_edges = [
            edge for edge in self.architecture.edges if edge.producer_id == node_id
        ]
        affected_edges = sorted(
            {edge.edge_id for edge in [*incoming_edges, *outgoing_edges]}
        )
        produced_tensors = sorted(
            tensor.tensor_id
            for tensor in self.architecture.tensors
            if tensor.producer_id == node_id
        )
        affected_fanouts = sorted(
            relation.relation_id
            for relation in self.architecture.fanouts
            if relation.producer_id == node_id
            or node_id in relation.consumer_ids
        )
        parameter_identity = node.parameter_identity.lower()
        explicitly_shared = any(
            marker in parameter_identity for marker in ("shared", "tied", "reused")
        )
        shared_parameter_nodes = sorted(
            item.node_id
            for item in self.architecture.nodes
            if explicitly_shared
            and item.node_id != node_id
            and item.parameter_identity == node.parameter_identity
        )
        child_ids = sorted(node.children)
        downstream_nodes = sorted({edge.consumer_id for edge in outgoing_edges})
        source_evidence_ids = sorted(
            evidence_id
            for evidence_id in node.evidence_ids
            if any(
                record.evidence_id == evidence_id and record.kind.value == "source"
                for record in self.evidence
            )
        )
        runtime_evidence_ids = sorted(self.runtime_node_evidence.get(node_id, []))
        unresolved: list[str] = []
        if incoming_edges and outgoing_edges:
            unresolved.append("deletion requires an explicit bypass or replacement connection")
        if child_ids:
            unresolved.append("child nodes require an explicit reparent or cascade decision")
        if shared_parameter_nodes:
            unresolved.append("shared parameter ownership must be preserved")
        if affected_fanouts:
            unresolved.append("fanout consumers require an explicit routing decision")
        if node.repeat_id:
            unresolved.append("repeat membership requires an explicit structural update")
        if node.execution_predicate != "always":
            unresolved.append("conditional execution semantics require proof")
        expected_delta = GraphDelta(
            removed_nodes=[node_id],
            removed_edges=affected_edges,
            removed_tensors=produced_tensors,
            removed_fanouts=affected_fanouts,
            unresolved_changes=unresolved,
        )
        return {
            "node_id": node.node_id,
            "semantic_name": node.semantic_name,
            "input_fingerprint": studio_fingerprint(self),
            "incoming_edge_ids": sorted(edge.edge_id for edge in incoming_edges),
            "outgoing_edge_ids": sorted(edge.edge_id for edge in outgoing_edges),
            "produced_tensor_ids": produced_tensors,
            "downstream_node_ids": downstream_nodes,
            "fanout_ids": affected_fanouts,
            "shared_parameter_node_ids": shared_parameter_nodes,
            "child_node_ids": child_ids,
            "repeat_id": node.repeat_id,
            "execution_predicate": node.execution_predicate,
            "source_evidence_ids": source_evidence_ids,
            "runtime_evidence_ids": runtime_evidence_ids,
            "expected_delta": expected_delta.model_dump(mode="json"),
            "required_action": (
                "Choose an explicit bypass or replacement before lowering."
                if incoming_edges and outgoing_edges
                else "Confirm the adapter-specific removal plan before lowering."
            ),
            "blocking_reasons": unresolved,
        }

    def propose_canonical_delete(self, payload: dict[str, object]) -> None:
        node_id = str(payload["node_id"])
        impact = self.canonical_delete_impact(node_id)
        if payload.get("input_fingerprint") != impact["input_fingerprint"]:
            raise ValueError("canonical delete impact preview is stale")
        if any(
            intent.kind == "delete-node" and node_id in intent.target_ids
            for intent in self.draft.intents
        ):
            raise ValueError("canonical node already has a delete intent")
        intent_id = str(payload.get("intent_id", f"intent:delete.{node_id.removeprefix('node:')}"))
        expected_delta = GraphDelta.model_validate(impact["expected_delta"])
        affected_ids = [
            node_id,
            *expected_delta.removed_edges,
            *expected_delta.removed_tensors,
            *expected_delta.removed_fanouts,
        ]
        intent = EditIntent(
            intent_id=intent_id,
            kind="delete-node",
            target_ids=affected_ids,
            preconditions=[
                "impact preview accepted",
                "no unresolved consumers",
                "explicit bypass or replacement",
                "registered adapter lowering",
            ],
            expected_delta=expected_delta,
            user_input={"node_id": node_id, "impact": impact},
            capability_requirement=(
                f"semantic.delete-node.{self.architecture.framework}.{node_id}"
            ),
        )
        summary = (
            f"Deleting {impact['semantic_name']} would remove "
            f"{len(expected_delta.removed_edges)} edge(s) and "
            f"{len(expected_delta.removed_tensors)} produced tensor(s). "
            "No registered adapter lowering proves this deletion safe."
        )
        proof = EditProofStatus(
            intent_id=intent_id,
            status=EditProofState.UNPROVEN,
            writeback_eligibility="blocked",
            reason_codes=["UNSUPPORTED_STRUCTURAL_INTENT"],
            message=summary,
            affected_subject_ids=affected_ids,
            required_facts=[
                "consumer preservation",
                "parameter ownership",
                "source deletion anchor",
                "observed Graph Delta oracle",
            ],
            supported_fixes=[
                "Choose an explicit bypass or replacement connection.",
                "Register and test an adapter-specific delete-node lowering.",
            ],
            checked_generation=self.project_session.generation,
            input_fingerprint=studio_fingerprint(self),
        )
        proposal = AgentProposal(
            proposal_id=f"proposal:{intent_id.removeprefix('intent:')}",
            reason_code="UNSUPPORTED_STRUCTURAL_INTENT",
            summary=summary,
            requested_intent=intent.model_dump(mode="json"),
            source_context={
                "architecture_id": self.architecture.architecture_id,
                "source_digest": self.document.source_digest,
                "impact": impact,
            },
        )
        draft = self.draft.model_copy(
            update={
                "revision": self.draft.revision + 1,
                "intents": [*self.draft.intents, intent],
                "proofs": [*self.draft.proofs, proof],
                "lowering_status": "blocked",
                "writeback_summary": WritebackSummary(
                    eligibility="blocked",
                    blocking_intent_ids=[
                        *self.draft.writeback_summary.blocking_intent_ids,
                        intent_id,
                    ],
                ),
            }
        )
        self.draft = DraftGraphDocument.model_validate(draft.model_dump(mode="json"))
        self.active_proposal = proposal
        _write_json(self.draft_path, self.draft)

    def discard_canonical_delete(self, intent_id: str) -> None:
        intent = next(
            (item for item in self.draft.intents if item.intent_id == intent_id), None
        )
        if intent is None or intent.kind != "delete-node":
            raise ValueError("canonical delete intent does not exist")
        intents = [item for item in self.draft.intents if item.intent_id != intent_id]
        proofs = [item for item in self.draft.proofs if item.intent_id != intent_id]
        blocking = [
            item
            for item in self.draft.writeback_summary.blocking_intent_ids
            if item != intent_id
        ]
        draft = self.draft.model_copy(
            update={
                "revision": self.draft.revision + 1,
                "intents": intents,
                "proofs": proofs,
                "lowering_status": "blocked" if proofs else "not-planned",
                "writeback_summary": WritebackSummary(
                    eligibility="blocked",
                    blocking_intent_ids=blocking,
                ),
            }
        )
        self.draft = DraftGraphDocument.model_validate(draft.model_dump(mode="json"))
        self.active_proposal = None
        _write_json(self.draft_path, self.draft)

    def prepare_parameter(self, payload: dict[str, object]) -> None:
        request = SemanticParameterPatch(
            patch_id=str(payload["patch_id"]),
            artifact_path=str(self.artifact_path),
            target_node_id=str(payload["target_node_id"]),
            parameter_name=str(payload["parameter_name"]),
            new_value=payload.get("new_value"),
            targeted_tests=payload.get("targeted_tests", []),
            runtime_input_spec=payload.get("runtime_input_spec"),
        )
        transaction, _ = prepare_transaction(request, self.workspace)
        transaction, _ = verify_transaction(
            self.workspace / "transactions" / transaction.transaction_id
        )
        self.active_transaction = transaction

    def prepare_structural(self, payload: dict[str, object]) -> None:
        request = SemanticStructuralPatch(
            patch_id=str(payload["patch_id"]),
            operation=str(payload["operation"]),
            artifact_path=str(self.artifact_path),
            target_node_id=str(payload["target_node_id"]),
            parameters=payload.get("parameters", {}),
            targeted_tests=payload.get("targeted_tests", []),
            runtime_input_spec=payload.get("runtime_input_spec"),
        )
        transaction, _ = prepare_transaction(request, self.workspace)
        transaction, _ = verify_transaction(
            self.workspace / "transactions" / transaction.transaction_id
        )
        self.active_transaction = transaction
        self.active_proposal = None

    def propose_connection(self, payload: dict[str, object]) -> None:
        request = ProposedConnection(
            proposal_id=str(payload["proposal_id"]),
            artifact_path=str(self.artifact_path),
            source_node_id=str(payload["source_node_id"]),
            source_port_id=str(payload["source_port_id"]),
            target_node_id=str(payload["target_node_id"]),
            target_port_id=str(payload["target_port_id"]),
            role=str(payload.get("role", "main")),
        )
        self.active_proposal = plan_connection(request, self.architecture)
        intent_id = request.proposal_id.replace("proposal:", "intent:", 1)
        intent = EditIntent(
            intent_id=intent_id,
            kind="connect-ports",
            target_ids=[
                request.source_node_id,
                request.source_port_id,
                request.target_node_id,
                request.target_port_id,
            ],
            capability_requirement=f"semantic.connect-ports.{request.role}",
            user_input={
                "source_node_id": request.source_node_id,
                "source_port_id": request.source_port_id,
                "target_node_id": request.target_node_id,
                "target_port_id": request.target_port_id,
                "policy": payload.get("policy", "fanout"),
            },
        )
        proof_state = (
            EditProofState.INVALID
            if self.active_proposal.reason_code == "INCOMPATIBLE_PORTS"
            else EditProofState.UNPROVEN
        )
        proof = EditProofStatus(
            intent_id=intent_id,
            status=proof_state,
            writeback_eligibility="blocked",
            reason_codes=[self.active_proposal.reason_code],
            message=self.active_proposal.summary,
            affected_subject_ids=intent.target_ids,
            checked_generation=self.project_session.generation,
            input_fingerprint=studio_fingerprint(self),
        )
        intents = [item for item in self.draft.intents if item.intent_id != intent_id]
        proofs = [item for item in self.draft.proofs if item.intent_id != intent_id]
        draft = self.draft.model_copy(
            update={
                "revision": self.draft.revision + 1,
                "intents": [*intents, intent],
                "proofs": [*proofs, proof],
                "lowering_status": "blocked",
                "writeback_summary": WritebackSummary(
                    eligibility="blocked",
                    blocking_intent_ids=[
                        *[item.intent_id for item in proofs],
                        intent_id,
                    ],
                ),
            }
        )
        draft = DraftGraphDocument.model_validate(draft.model_dump(mode="json"))
        _write_json(self.draft_path, draft)
        self.draft = draft

    def commit_parameter(self) -> None:
        if self.active_transaction is None:
            raise ValueError("there is no active source transaction")
        transaction, _ = commit_transaction(
            self.workspace / "transactions" / self.active_transaction.transaction_id
        )
        self.active_transaction = transaction
        if (
            transaction.state is TransactionState.COMMITTED
            and isinstance(transaction.request, FreeformSourcePatch)
        ):
            self.source_workspace = self.source_workspace.model_copy(
                update={"revision": self.source_workspace.revision + 1, "buffers": []}
            )
            _write_json(self.source_workspace_path, self.source_workspace)

    def discard_parameter(self) -> None:
        if self.active_transaction is None:
            raise ValueError("there is no active source transaction")
        transaction, _ = discard_transaction(
            self.workspace / "transactions" / self.active_transaction.transaction_id
        )
        self.active_transaction = transaction

    def save_document(self, document: CanvasDocument) -> None:
        if document.source_digest != self.document.source_digest:
            raise ValueError("CanvasDocument source digest cannot change")
        persist_canvas_document(self.document_path, document)
        self.document = document

    def export_svg(self) -> str:
        scene = next(iter(self.base_scenes.values()))
        return render_svg(materialize_scene(scene, self.document))


def _render_index(template: str, state: dict[str, object]) -> str:
    payload = json.dumps(state, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    script = f'<script id="archcanvas-studio-data" type="application/json">{payload}</script>'
    if "<!--ARCHCANVAS_DATA-->" not in template:
        raise ValueError("Studio index is missing its data injection marker")
    return template.replace("<!--ARCHCANVAS_DATA-->", script)


def _write_static_bundle(bundle: StudioBundle) -> None:
    if not (STATIC_ROOT / "index.html").is_file():
        raise ValueError("Studio frontend has not been built")
    bundle.static_dir.mkdir(parents=True, exist_ok=True)
    for source in STATIC_ROOT.iterdir():
        target = bundle.static_dir / source.name
        if source.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
        elif source.name != "index.html":
            shutil.copy2(source, target)
    template = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    (bundle.static_dir / "index.html").write_text(
        _render_index(template, bundle.state()), encoding="utf-8"
    )
    _write_json(bundle.static_dir / "studio-state.json", bundle.state())


def _archive_stale_binding(path: Path) -> Path:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    archive = path.with_name(f"{path.stem}.stale-{digest}{path.suffix}")
    index = 1
    while archive.exists():
        archive = path.with_name(f"{path.stem}.stale-{digest}-{index}{path.suffix}")
        index += 1
    path.rename(archive)
    return archive


def prepare_studio_bundle(
    artifact: Path,
    workspace: Path,
    *,
    write_static: bool = True,
    replace_stale_bindings: bool = False,
) -> StudioBundle:
    artifact = artifact.resolve()
    workspace = workspace.resolve()
    architecture = ArchitectureIR.model_validate_json(artifact.read_text(encoding="utf-8"))
    snapshot_path = artifact.parent / "source-snapshot.json"
    if not snapshot_path.is_file():
        raise ValueError("Studio requires source-snapshot.json beside architecture.json")
    snapshot = SourceSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
    evidence_path = artifact.parent / "evidence-ledger.json"
    evidence = (
        TypeAdapter(list[EvidenceRecord]).validate_json(evidence_path.read_text(encoding="utf-8"))
        if evidence_path.is_file()
        else []
    )
    semantic_overlay_path = artifact.parent / "semantic-annotation-overlay.json"
    semantic_overlay = (
        SemanticAnnotationOverlay.model_validate_json(
            semantic_overlay_path.read_text(encoding="utf-8")
        )
        if semantic_overlay_path.is_file()
        else None
    )
    if semantic_overlay is not None and (
        semantic_overlay.architecture_id != architecture.architecture_id
        or semantic_overlay.exact_ir_digest != exact_ir_digest(architecture)
    ):
        raise ValueError("semantic annotation overlay binding is stale")
    runtime_trace_path = artifact.parent / "runtime-trace.json"
    runtime_evidence_path = artifact.parent / "runtime-evidence-ledger.json"
    runtime_overlay_path = artifact.parent / "runtime-evidence-overlay.json"
    runtime_receipt_path = artifact.parent / "runtime-receipt.json"
    runtime_trace: RuntimeTrace | None = None
    runtime_node_evidence: dict[str, list[str]] = {}
    runtime_paths = (runtime_trace_path, runtime_evidence_path, runtime_overlay_path)
    runtime_receipt = (
        json.loads(runtime_receipt_path.read_text(encoding="utf-8"))
        if runtime_receipt_path.is_file()
        else None
    )
    if any(path.is_file() for path in runtime_paths) and runtime_receipt is None:
        raise ValueError("Studio found runtime evidence without a runtime receipt")
    if runtime_receipt is not None and runtime_receipt.get("status") == "ok":
        if not all(
            path.is_file() for path in runtime_paths
        ):
            raise ValueError("Studio found an incomplete runtime evidence bundle")
        runtime_trace = RuntimeTrace.model_validate_json(
            runtime_trace_path.read_text(encoding="utf-8")
        )
        if (
            runtime_trace.architecture_id != architecture.architecture_id
            or runtime_trace.source_snapshot_id != snapshot.snapshot_id
            or runtime_trace.source_revision != snapshot.revision
        ):
            raise ValueError("runtime evidence belongs to a stale architecture or source snapshot")
        runtime_evidence = TypeAdapter(list[EvidenceRecord]).validate_json(
            runtime_evidence_path.read_text(encoding="utf-8")
        )
        overlay = json.loads(runtime_overlay_path.read_text(encoding="utf-8"))
        if (
            overlay.get("architecture_id") != architecture.architecture_id
            or overlay.get("trace_id") != runtime_trace.trace_id
            or runtime_receipt.get("details", {}).get("trace_id") != runtime_trace.trace_id
        ):
            raise ValueError("runtime evidence overlay binding is stale")
        runtime_node_evidence = TypeAdapter(dict[str, list[str]]).validate_python(
            overlay.get("node_evidence", {})
        )
        runtime_ids = {item.evidence_id for item in runtime_evidence}
        if any(
            evidence_id not in runtime_ids
            for ids in runtime_node_evidence.values()
            for evidence_id in ids
        ):
            raise ValueError("runtime evidence overlay references an unknown record")
        evidence.extend(runtime_evidence)
    hierarchy = compile_hierarchy(architecture, semantic_overlay)
    navigation = build_navigation_projections(architecture, snapshot, evidence, hierarchy)
    suffix = architecture.architecture_id.removeprefix("architecture:")
    document_path = workspace / "documents" / f"{suffix}.canvas.json"
    document: CanvasDocument | None = None
    if document_path.is_file():
        saved_document = load_canvas_document(document_path)
        expected_digest = source_binding_digest(snapshot)
        stale_reason = next(
            (
                message
                for invalid, message in (
                    (
                        saved_document.architecture_id != architecture.architecture_id,
                        "saved CanvasDocument belongs to a different architecture",
                    ),
                    (
                        saved_document.source_snapshot_id != snapshot.snapshot_id,
                        "saved CanvasDocument belongs to a stale source snapshot",
                    ),
                    (
                        saved_document.source_digest != expected_digest,
                        "saved CanvasDocument source digest is stale",
                    ),
                    (
                        saved_document.base_hierarchy_id not in {None, hierarchy.hierarchy_id},
                        "saved CanvasDocument hierarchy does not match this compilation",
                    ),
                )
                if invalid
            ),
            None,
        )
        if stale_reason is not None:
            if not replace_stale_bindings:
                raise ValueError(stale_reason)
            _archive_stale_binding(document_path)
        else:
            document = saved_document
        if document is not None and document.base_hierarchy_id is None:
            document = document.model_copy(update={"base_hierarchy_id": hierarchy.hierarchy_id})
            persist_canvas_document(document_path, document)
    if document is None:
        document = create_canvas_document(
            architecture, snapshot, hierarchy_id=hierarchy.hierarchy_id
        )
        persist_canvas_document(document_path, document)

    state = derive_view_state(document)
    projection = str(state.get("navigation_view", "module"))
    expandable = expandable_node_ids(hierarchy)
    if projection == "module":
        expanded_ids = (
            _reachable_expansions(
                navigation, "module", set(state.get("module_expansion", []))
            )
            & expandable
        )
    else:
        source_rows = navigation["projections"]["source"]["nodes"]
        source_expanded = _reachable_expansions(
            navigation, "source", set(state.get("source_expansion", []))
        )
        source_expandable = {
            row["id"] for row in source_rows if row["child_count"] > 0
        }
        if source_expandable and source_expandable <= source_expanded:
            expanded_ids = expandable
        else:
            visible_depth = max(
                (row["depth"] for row in source_rows if row["id"] in source_expanded),
                default=0,
            )
            expanded_ids = {
                node.hierarchy_node_id
                for node in hierarchy.nodes
                if node.hierarchy_node_id in expandable and node.depth <= visible_depth
            }
    view = project_hierarchy(architecture, hierarchy, expanded_ids)
    spec = build_visual_spec(view)
    scene = build_scene(view, spec, str(state.get("layout_mode", "auto")))
    views = {view.projection_id: view}
    specs = {view.projection_id: spec}
    base_scenes = {view.projection_id: scene}

    project_root = Path(snapshot.project_root).resolve()
    project_session = create_project_session(
        project_root,
        workspace,
        generation=1,
        snapshot=snapshot,
    )
    project_discovery = discover_project(project_root)
    draft_path = workspace / "drafts" / f"{suffix}.draft.json"
    if draft_path.is_file():
        saved_draft = DraftGraphDocument.model_validate_json(
            draft_path.read_text(encoding="utf-8")
        )
        if (
            saved_draft.base_architecture_id != architecture.architecture_id
            or saved_draft.base_source_digest != document.source_digest
        ):
            if not replace_stale_bindings:
                raise ValueError("saved DraftGraphDocument binding is stale")
            _archive_stale_binding(draft_path)
            draft = None
        else:
            draft = saved_draft
    else:
        draft = None
    if draft is None:
        draft = DraftGraphDocument(
            draft_id=f"draft:{suffix}",
            base_architecture_id=architecture.architecture_id,
            base_source_digest=document.source_digest,
            revision=0,
        )
        _write_json(draft_path, draft)

    source_workspace_path = workspace / "source-workspace" / f"{suffix}.source-workspace.json"
    if source_workspace_path.is_file():
        saved_source_workspace = SourceWorkspaceDocument.model_validate_json(
            source_workspace_path.read_text(encoding="utf-8")
        )
        if (
            saved_source_workspace.source_snapshot_id != snapshot.snapshot_id
            or saved_source_workspace.base_revision != snapshot.revision
        ):
            if not replace_stale_bindings:
                raise ValueError("saved source workspace binding is stale")
            _archive_stale_binding(source_workspace_path)
            source_workspace = None
        else:
            source_workspace = saved_source_workspace
    else:
        source_workspace = None
    if source_workspace is None:
        source_workspace = SourceWorkspaceDocument(
            workspace_id=f"source-workspace:{suffix}",
            source_snapshot_id=snapshot.snapshot_id,
            base_revision=snapshot.revision,
            revision=0,
        )
        _write_json(source_workspace_path, source_workspace)

    bundle = StudioBundle(
        artifact_path=artifact,
        workspace=workspace,
        static_dir=workspace / "studio",
        document_path=document_path,
        architecture=architecture,
        snapshot=snapshot,
        evidence=evidence,
        runtime_trace=runtime_trace,
        runtime_node_evidence=runtime_node_evidence,
        semantic_overlay=semantic_overlay,
        hierarchy=hierarchy,
        views=views,
        specs=specs,
        base_scenes=base_scenes,
        document=document,
        project_session=project_session,
        project_discovery=project_discovery,
        draft_path=draft_path,
        draft=draft,
        source_workspace_path=source_workspace_path,
        source_workspace=source_workspace,
        search_index=[],
        validation_runs=[],
        navigation=navigation,
    )
    bundle.search_index = build_search_index(bundle)
    _write_json(workspace / "publication" / "hierarchy.json", hierarchy)
    _write_json(workspace / "publication" / "current" / "publication-view.json", view)
    _write_json(workspace / "publication" / "current" / "visual-spec.json", spec)
    _write_json(workspace / "publication" / "current" / "visual-scene.json", scene)
    if write_static:
        _write_static_bundle(bundle)
    return bundle
