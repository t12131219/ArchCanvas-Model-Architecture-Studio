from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from archcanvas_core.models.canvas import (
    CanvasDocument,
    CanvasLayoutMode,
    CanvasNodeState,
    CanvasViewport,
)
from archcanvas_core.models.engine import (
    EngineEnvironment,
    EngineOperation,
    EngineRequest,
    OpenProjectCommand,
    ProjectCommand,
    ResolveSourceAnchorCommand,
    SaveCanvasDocumentCommand,
    VisualPatch,
)
from archcanvas_engine import ArchCanvasEngine
from archcanvas_engine.service_errors import EngineRejected

ROOT = Path(__file__).resolve().parents[2]


def _open_command(project_root: Path) -> OpenProjectCommand:
    return OpenProjectCommand(
        project_id="project:engine-transformer",
        approved_root=str(project_root),
        entrypoint="model.py:EncoderModel",
        environment=EngineEnvironment(python_executable=sys.executable, environment_name="TFB_py311"),
    )


def _project_copy(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    shutil.copyfile(ROOT / "fixtures" / "transformer_static_v1" / "source" / "model.py", root / "model.py")
    return root


def _canvas_document(analysis) -> CanvasDocument:
    return CanvasDocument(
        canvas_document_id="canvas-document:engine-transformer-layout",
        project_id=analysis.manifest.project_id,
        publication_id=analysis.publication.publication_id,
        base_source_revision=analysis.manifest.source_revision,
        layout_mode=CanvasLayoutMode.MANUAL,
        viewport=CanvasViewport(x=-120.0, y=48.0, zoom=1.25),
        nodes=[
            CanvasNodeState(
                publication_node_id=node.node_id,
                x=float(index * 240),
                y=96.0,
                width=200.0,
                height=80.0,
                collapsed=node.collapsed,
                locked=node.kind.value == "input",
            )
            for index, node in enumerate(analysis.publication.nodes)
        ],
    )


def test_engine_open_analyze_cache_reload_and_visual_patch_are_source_read_only(tmp_path: Path) -> None:
    project_root = _project_copy(tmp_path)
    source_path = project_root / "model.py"
    source_before = source_path.read_bytes()
    cache_root = tmp_path / "cache"
    engine = ArchCanvasEngine(cache_root)

    opened = engine.open_project(_open_command(project_root))
    analysis = engine.analyze_project(opened.project_id)
    patch = VisualPatch(
        visual_patch_id="visual-patch:engine-transformer-layout",
        project_id=opened.project_id,
        publication_id=analysis.publication.publication_id,
        base_source_revision=analysis.manifest.source_revision,
        expanded_node_ids=["publication-node:transformer-encoder"],
    )
    saved = engine.save_visual_patch(patch)

    assert analysis.architecture.project_id == opened.project_id
    assert analysis.svg.relative_path == "analysis/scene.svg"
    assert saved.visual_patches == [patch]
    assert source_path.read_bytes() == source_before

    restarted = ArchCanvasEngine(cache_root)
    source, architecture, publication, scene = restarted.load_analysis(opened.project_id)
    replayed = restarted.replay_visual_patches(opened.project_id)
    assert source.source_revision == analysis.manifest.source_revision
    assert architecture.ir_id == analysis.architecture.ir_id
    assert publication.publication_id == analysis.publication.publication_id
    assert scene.publication_id == publication.publication_id
    assert replayed.visual_patches == [patch]
    assert replayed.orphaned_visual_patch_ids == []


def test_external_source_change_marks_visual_patch_orphaned_without_engine_source_write(tmp_path: Path) -> None:
    project_root = _project_copy(tmp_path)
    source_path = project_root / "model.py"
    engine = ArchCanvasEngine(tmp_path / "cache")
    opened = engine.open_project(_open_command(project_root))
    analysis = engine.analyze_project(opened.project_id)
    patch = VisualPatch(
        visual_patch_id="visual-patch:engine-stale-layout",
        project_id=opened.project_id,
        publication_id=analysis.publication.publication_id,
        base_source_revision=analysis.manifest.source_revision,
    )
    engine.save_visual_patch(patch)

    source_path.write_bytes(source_path.read_bytes() + b"\n# external edit\n")
    externally_changed = source_path.read_bytes()
    refresh = engine.refresh_project(opened.project_id)
    replayed = engine.replay_visual_patches(opened.project_id)

    assert refresh.manifest.source_status.value == "stale"
    assert refresh.observed_source_revision != analysis.manifest.source_revision
    assert refresh.stale_visual_patch_ids == [patch.visual_patch_id]
    assert replayed.visual_patches == []
    assert replayed.orphaned_visual_patch_ids == [patch.visual_patch_id]
    assert source_path.read_bytes() == externally_changed


def test_typed_rpc_returns_structured_success_and_project_not_open_error(tmp_path: Path) -> None:
    engine = ArchCanvasEngine(tmp_path / "cache")
    missing = engine.dispatch(
        EngineRequest(
            request_id="engine-request:missing-project",
            command=ProjectCommand(
                operation=EngineOperation.ANALYZE_PROJECT,
                project_id="project:not-open",
            ),
        )
    )
    assert missing.status == "rejected"
    assert missing.error is not None
    assert missing.error.code == "PROJECT_NOT_OPEN"

    project_root = _project_copy(tmp_path)
    opened = engine.dispatch(
        EngineRequest(request_id="engine-request:open", command=_open_command(project_root))
    )
    assert opened.status == "succeeded"
    analyzed = engine.dispatch(
        EngineRequest(
            request_id="engine-request:analyze",
            command=ProjectCommand(
                operation=EngineOperation.ANALYZE_PROJECT,
                project_id="project:engine-transformer",
            ),
        )
    )
    assert analyzed.status == "succeeded"
    assert analyzed.result is not None
    assert analyzed.result.kind == "analysis_completed"


def test_canvas_document_replays_after_restart_without_changing_source_bytes(tmp_path: Path) -> None:
    project_root = _project_copy(tmp_path)
    source_path = project_root / "model.py"
    source_before = source_path.read_bytes()
    cache_root = tmp_path / "cache"
    engine = ArchCanvasEngine(cache_root)
    opened = engine.open_project(_open_command(project_root))
    analysis = engine.analyze_project(opened.project_id)
    document = _canvas_document(analysis)

    saved = engine.save_canvas_document(document)
    restarted = ArchCanvasEngine(cache_root)
    replayed = restarted.replay_canvas_documents(opened.project_id)

    assert saved.canvas_documents == [document]
    assert replayed.canvas_documents == [document]
    assert replayed.orphaned_canvas_document_ids == []
    assert source_path.read_bytes() == source_before


def test_canvas_document_rejects_unknown_nodes_and_stale_source(tmp_path: Path) -> None:
    project_root = _project_copy(tmp_path)
    source_path = project_root / "model.py"
    engine = ArchCanvasEngine(tmp_path / "cache")
    opened = engine.open_project(_open_command(project_root))
    analysis = engine.analyze_project(opened.project_id)
    document = _canvas_document(analysis)
    invalid = document.model_copy(
        update={
            "nodes": [
                *document.nodes[:-1],
                document.nodes[-1].model_copy(update={"publication_node_id": "publication-node:unknown"}),
            ]
        }
    )

    with pytest.raises(EngineRejected) as mismatch:
        engine.save_canvas_document(invalid)
    assert mismatch.value.code == "CANVAS_DOCUMENT_NODE_SET_MISMATCH"

    source_path.write_bytes(source_path.read_bytes() + b"\n# external edit\n")
    with pytest.raises(EngineRejected) as stale:
        engine.save_canvas_document(document)
    assert stale.value.code == "CANVAS_DOCUMENT_STALE"


def test_canvas_document_is_available_through_typed_engine_rpc(tmp_path: Path) -> None:
    project_root = _project_copy(tmp_path)
    engine = ArchCanvasEngine(tmp_path / "cache")
    opened = engine.open_project(_open_command(project_root))
    analysis = engine.analyze_project(opened.project_id)

    response = engine.dispatch(
        EngineRequest(
            request_id="engine-request:save-canvas-document",
            command=SaveCanvasDocumentCommand(canvas_document=_canvas_document(analysis)),
        )
    )

    assert response.status == "succeeded"
    assert response.result is not None
    assert response.result.kind == "canvas_document_saved"


def test_engine_resolves_only_analysis_backed_source_locations(tmp_path: Path) -> None:
    project_root = _project_copy(tmp_path)
    engine = ArchCanvasEngine(tmp_path / "cache")
    opened = engine.open_project(_open_command(project_root))
    analysis = engine.analyze_project(opened.project_id)
    anchor_id = analysis.architecture.nodes[1].source_anchor_ids[0]

    response = engine.dispatch(
        EngineRequest(
            request_id="engine-request:resolve-source-anchor",
            command=ResolveSourceAnchorCommand(project_id=opened.project_id, anchor_id=anchor_id),
        )
    )

    assert response.status == "succeeded"
    assert response.result is not None
    assert response.result.kind == "source_location"
    assert response.result.relative_file == "model.py"

    missing = engine.dispatch(
        EngineRequest(
            request_id="engine-request:resolve-missing-anchor",
            command=ResolveSourceAnchorCommand(
                project_id=opened.project_id,
                anchor_id="anchor:not-present",
            ),
        )
    )
    assert missing.status == "rejected"
    assert missing.error is not None
    assert missing.error.code == "SOURCE_ANCHOR_NOT_FOUND"

    (project_root / "model.py").unlink()
    unavailable = engine.dispatch(
        EngineRequest(
            request_id="engine-request:resolve-removed-anchor",
            command=ResolveSourceAnchorCommand(project_id=opened.project_id, anchor_id=anchor_id),
        )
    )
    assert unavailable.status == "rejected"
    assert unavailable.error is not None
    assert unavailable.error.code == "SOURCE_ANCHOR_OUTSIDE_APPROVED_ROOT"


def test_engine_persists_the_approved_resolved_config_for_static_analysis(tmp_path: Path) -> None:
    project_root = tmp_path / "config-project"
    project_root.mkdir()
    source_path = project_root / "model.py"
    source_before = b'''import torch.nn as nn

class TaskModel(nn.Module):
    def __init__(self, configs):
        super().__init__()
        self.task_name = configs.task_name
        self.embedding = nn.Linear(2, 2)
        if self.task_name == "forecast":
            self.head = nn.Linear(2, 1)

    def forecast(self, x):
        return self.head(self.embedding(x))

    def forward(self, x):
        if self.task_name == "forecast":
            return self.forecast(x)
        return x
'''
    source_path.write_bytes(source_before)
    engine = ArchCanvasEngine(tmp_path / "cache")
    command = OpenProjectCommand(
        project_id="project:engine-config-task",
        approved_root=str(project_root),
        entrypoint="model.py:TaskModel",
        environment=EngineEnvironment(python_executable=sys.executable, environment_name="TFB_py311"),
        resolved_config={"task_name": "forecast"},
    )

    opened = engine.open_project(command)
    analysis = engine.analyze_project(opened.project_id)

    assert opened.resolved_config == {"task_name": "forecast"}
    assert analysis.architecture.metadata["resolved_config"] == {"task_name": "forecast"}
    assert [(edge.source_node_id, edge.target_node_id) for edge in analysis.architecture.edges] == [
        ("node:taskmodel.embedding", "node:taskmodel.head"),
        ("node:taskmodel.head", "node:output"),
        ("node:input", "node:taskmodel.embedding"),
    ]
    assert source_path.read_bytes() == source_before
