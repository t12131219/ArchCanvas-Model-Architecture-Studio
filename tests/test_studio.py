from __future__ import annotations

import hashlib
import json
import shutil
import sys
import threading
import time
from collections import defaultdict
from itertools import pairwise
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from archcanvas_core.models import (
    AnalysisJob,
    AnalysisRequest,
    DraftGraphDocument,
    EditProofState,
    JobState,
    PatchBatch,
    SceneEdge,
    SceneNode,
    ScenePoint,
    SceneRect,
    TransactionState,
    VisualPatch,
    VisualScene,
)
from archcanvas_engine.cli import main
from archcanvas_publication import render_svg, validate_geometry
from archcanvas_python import analyze_project
from archcanvas_studio import (
    apply_patch,
    apply_patch_batch,
    auto_route_batch,
    derive_view_state,
    load_canvas_document,
    materialize_scene,
    persist_canvas_document,
    prepare_studio_bundle,
    redo_patch,
    source_binding_digest,
    undo_patch,
)
from archcanvas_studio.document import _reroute_edges
from archcanvas_studio.operations import (
    _orthogonal_segment_interaction,
    _route_inside_unrelated,
    _route_interactions,
    alignment_batch,
    auto_layout_batch,
    build_search_index,
)
from archcanvas_studio.project import (
    browse_directories,
    create_project_session,
    discover_conda_environments,
    discover_project,
)
from archcanvas_studio.routing import routing_runtime_config
from archcanvas_studio.server import (
    StudioHTTPServer,
    StudioRequestHandler,
    create_studio_server,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "tier_a" / "transformer"


def _server_without_socket(bundle) -> StudioHTTPServer:  # type: ignore[no-untyped-def]
    server = StudioHTTPServer.__new__(StudioHTTPServer)
    server.bundle = bundle
    server.lock = threading.RLock()
    server.session_nonce = "test-nonce"
    server.jobs = {}
    server.pending_projects = {}
    server.job_processes = {}
    server.job_cancellations = {}
    server.project_generation = bundle.project_session.generation
    server.validation_generation = bundle.validation_generation
    server.layout_candidates = {}
    server.active_project_key = (
        bundle.project_session.project_id,
        bundle.project_session.generation,
    )
    return server


def _wait_for_job(server: StudioHTTPServer, job_id: str) -> AnalysisJob:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with server.lock:
            job = server.jobs[job_id]
            if job.state in {
                JobState.SUCCEEDED,
                JobState.FAILED,
                JobState.CANCELLED,
                JobState.STALE,
            }:
                return job
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not reach a terminal state")


def _handler_without_request(server: StudioHTTPServer) -> StudioRequestHandler:
    handler = StudioRequestHandler.__new__(StudioRequestHandler)
    handler.server = server
    return handler


class _BlockingAnalysisProcess:
    def __init__(self) -> None:
        self.pid = 999_999
        self.returncode: int | None = None
        self.started = threading.Event()
        self.release = threading.Event()
        self.terminated = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15
        self.release.set()

    def communicate(self) -> tuple[str, str]:
        self.started.set()
        if not self.release.wait(5):
            raise TimeoutError("test analysis process was not released")
        return "", ""


def _analysis_request(session, request_id: str) -> AnalysisRequest:  # type: ignore[no-untyped-def]
    return AnalysisRequest(
        project_id=session.project_id,
        project_generation=session.generation,
        entrypoint="model:Transformer",
        framework="pytorch",
        task="inference",
        request_id=request_id,
    )


@pytest.fixture
def analysis_dir(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    bundle = analyze_project(
        project,
        "model:Transformer",
        "inference",
        "eval",
        (project / "config.json").read_bytes(),
        project / "config.json",
    )
    target = tmp_path / "analysis"
    target.mkdir()
    (target / "architecture.json").write_text(bundle.architecture.model_dump_json())
    (target / "source-snapshot.json").write_text(bundle.snapshot.model_dump_json())
    (target / "evidence-ledger.json").write_text(
        json.dumps([record.model_dump(mode="json") for record in bundle.evidence])
    )
    return target


def _source_hashes() -> dict[str, str]:
    return {
        str(path.relative_to(FIXTURE)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(FIXTURE.rglob("*.py"))
    }


def test_route_interactions_distinguish_crossings_and_shared_segments() -> None:
    assert _orthogonal_segment_interaction(
        (10.0, 0.0), (10.0, 20.0), (0.0, 10.0), (20.0, 10.0)
    ) == (1, 0.0)
    assert _orthogonal_segment_interaction(
        (10.0, 0.0), (10.0, 20.0), (10.0, 5.0), (10.0, 25.0)
    ) == (0, 15.0)
    assert _orthogonal_segment_interaction(
        (10.0, 0.0), (10.0, 20.0), (10.0, 20.0), (30.0, 20.0)
    ) == (0, 0.0)


def test_route_interactions_allow_shared_endpoint_stubs() -> None:
    candidate = [(10.0, 10.0), (10.0, 30.0), (40.0, 30.0)]
    routed = [
        ([(10.0, 10.0), (10.0, 30.0), (10.0, 50.0)], "source", "other"),
        ([(70.0, 30.0), (40.0, 30.0)], "other", "target"),
    ]
    assert _route_interactions(candidate, routed, "source", "target") == (0, 0.0)


def test_route_obstacle_metric_prioritizes_unique_module_count() -> None:
    scene = VisualScene(
        scene_id="scene:route-metric",
        view_id="view:route-metric",
        spec_id="spec:route-metric",
        layout_family="orthogonal",
        paper_width=500,
        paper_height=300,
        nodes=[
            SceneNode(
                scene_node_id="scene-node:large",
                view_node_id="view-node:large",
                bounds=SceneRect(x=100, y=80, width=180, height=80),
                shape="rect",
                label_lines=["large"],
                fill="#fff",
                stroke="#111",
            ),
            SceneNode(
                scene_node_id="scene-node:small-a",
                view_node_id="view-node:small-a",
                bounds=SceneRect(x=320, y=50, width=12, height=30),
                shape="rect",
                label_lines=["a"],
                fill="#fff",
                stroke="#111",
            ),
            SceneNode(
                scene_node_id="scene-node:small-b",
                view_node_id="view-node:small-b",
                bounds=SceneRect(x=360, y=50, width=12, height=30),
                shape="rect",
                label_lines=["b"],
                fill="#fff",
                stroke="#111",
            ),
        ],
    )

    one_long_crossing = _route_inside_unrelated(
        [(80.0, 120.0), (300.0, 120.0)], scene, set()
    )
    two_short_crossings = _route_inside_unrelated(
        [(300.0, 65.0), (390.0, 65.0)], scene, set()
    )

    assert one_long_crossing[0] == 1
    assert two_short_crossings[0] == 2
    assert one_long_crossing[1] > two_short_crossings[1]


def test_auto_route_separates_unavoidable_shared_corridors() -> None:
    source = SceneNode(
        scene_node_id="scene-node:source",
        view_node_id="view-node:source",
        bounds=SceneRect(x=40, y=120, width=60, height=40),
        shape="rect",
        label_lines=["s"],
        fill="#fff",
        stroke="#111",
    )
    target = SceneNode(
        scene_node_id="scene-node:target",
        view_node_id="view-node:target",
        bounds=SceneRect(x=400, y=120, width=60, height=40),
        shape="rect",
        label_lines=["t"],
        fill="#fff",
        stroke="#111",
    )
    direct = [ScenePoint(x=100, y=140), ScenePoint(x=400, y=140)]
    scene = VisualScene(
        scene_id="scene:parallel-routes",
        view_id="view:parallel-routes",
        spec_id="spec:parallel-routes",
        layout_family="orthogonal",
        paper_width=500,
        paper_height=300,
        nodes=[source, target],
        edges=[
            SceneEdge(
                scene_edge_id=f"scene-edge:{suffix}",
                view_edge_id=f"view-edge:{suffix}",
                canonical_edge_ids=[f"edge:{suffix}"],
                source_scene_node_id=source.scene_node_id,
                target_scene_node_id=target.scene_node_id,
                points=direct,
                role="main",
                edge_type="main",
                stroke="#111",
                width=1.5,
                label="Flow",
            )
            for suffix in ("a", "b")
        ],
    )

    batch = auto_route_batch(scene, batch_id="batch:test.parallel-routes")
    second = next(
        patch for patch in batch.patches if patch.target_id == "scene-edge:b"
    )
    horizontal_lanes = {
        point["y"]
        for point, following in pairwise(second.value["points"])
        if point["y"] == following["y"]
        and abs(following["x"] - point["x"]) > 100
    }

    assert horizontal_lanes
    assert 140.0 not in horizontal_lanes
    assert min(abs(lane - 140.0) for lane in horizontal_lanes) == 8.0


def test_auto_route_finds_short_multi_corridor_path_between_staggered_obstacles() -> None:
    source = SceneNode(
        scene_node_id="scene-node:source",
        view_node_id="view-node:source",
        bounds=SceneRect(x=30, y=176, width=60, height=48),
        shape="rect",
        label_lines=["s"],
        fill="#fff",
        stroke="#111",
    )
    target = SceneNode(
        scene_node_id="scene-node:target",
        view_node_id="view-node:target",
        bounds=SceneRect(x=610, y=176, width=60, height=48),
        shape="rect",
        label_lines=["t"],
        fill="#fff",
        stroke="#111",
    )
    blockers = [
        SceneNode(
            scene_node_id="scene-node:blocker-a",
            view_node_id="view-node:blocker-a",
            bounds=SceneRect(x=190, y=20, width=100, height=250),
            shape="opaque",
            label_lines=["a"],
            fill="#fff",
            stroke="#111",
        ),
        SceneNode(
            scene_node_id="scene-node:blocker-b",
            view_node_id="view-node:blocker-b",
            bounds=SceneRect(x=390, y=130, width=100, height=250),
            shape="opaque",
            label_lines=["b"],
            fill="#fff",
            stroke="#111",
        ),
    ]
    edge = SceneEdge(
        scene_edge_id="scene-edge:staggered",
        view_edge_id="view-edge:staggered",
        canonical_edge_ids=["edge:staggered"],
        source_scene_node_id=source.scene_node_id,
        target_scene_node_id=target.scene_node_id,
        points=[ScenePoint(x=90, y=200), ScenePoint(x=610, y=200)],
        role="main",
        edge_type="main",
        stroke="#111",
        width=1.5,
        label="Flow",
    )
    scene = VisualScene(
        scene_id="scene:staggered",
        view_id="view:staggered",
        spec_id="spec:staggered",
        layout_family="orthogonal",
        paper_width=700,
        paper_height=400,
        nodes=[source, target, *blockers],
        edges=[edge],
    )

    batch = auto_route_batch(scene, batch_id="batch:test.staggered")
    patch = next(item for item in batch.patches if item.target_id == edge.scene_edge_id)
    points = [ScenePoint.model_validate(point) for point in patch.value["points"]]
    route_length = sum(
        abs(end.x - start.x) + abs(end.y - start.y)
        for start, end in pairwise(points)
    )
    routed = scene.model_copy(
        update={"edges": [edge.model_copy(update={"points": points})]}
    )
    gate, diagnostics = validate_geometry(routed)

    assert gate.status == "passed", diagnostics
    assert min(point.y for point in points) <= 120.0
    assert max(point.y for point in points) >= 280.0
    assert route_length < 900.0


def test_route_hint_reconnects_after_endpoint_moves() -> None:
    source = SceneNode(
        scene_node_id="scene-node:source",
        view_node_id="view-node:source",
        bounds=SceneRect(x=40, y=120, width=60, height=40),
        shape="rect",
        label_lines=["s"],
        fill="#fff",
        stroke="#111",
    )
    target = SceneNode(
        scene_node_id="scene-node:target",
        view_node_id="view-node:target",
        bounds=SceneRect(x=400, y=120, width=60, height=40),
        shape="rect",
        label_lines=["t"],
        fill="#fff",
        stroke="#111",
    )
    edge = SceneEdge(
        scene_edge_id="scene-edge:hinted",
        view_edge_id="view-edge:hinted",
        canonical_edge_ids=["edge:hinted"],
        source_scene_node_id=source.scene_node_id,
        target_scene_node_id=target.scene_node_id,
        points=[ScenePoint(x=100, y=140), ScenePoint(x=400, y=140)],
        role="main",
        edge_type="main",
        stroke="#111",
        width=1.5,
        label="Flow",
    )
    hint = [
        ScenePoint(x=100, y=140),
        ScenePoint(x=124, y=140),
        ScenePoint(x=124, y=80),
        ScenePoint(x=376, y=80),
        ScenePoint(x=376, y=140),
        ScenePoint(x=400, y=140),
    ]
    moved_source = source.model_copy(
        update={"bounds": source.bounds.model_copy(update={"y": 180})}
    )
    scene = VisualScene(
        scene_id="scene:hinted-route",
        view_id="view:hinted-route",
        spec_id="spec:hinted-route",
        layout_family="orthogonal",
        paper_width=500,
        paper_height=300,
        nodes=[moved_source, target],
        edges=[edge],
    )

    [rerouted] = _reroute_edges(
        scene,
        scene.nodes,
        {edge.scene_edge_id: hint},
        {source.scene_node_id},
    )

    assert (rerouted.points[0].x, rerouted.points[0].y) == (100, 200)
    assert (rerouted.points[-1].x, rerouted.points[-1].y) == (400, 140)
    _, diagnostics = validate_geometry(scene.model_copy(update={"edges": [rerouted]}))
    assert not any(
        diagnostic.code == "GEOMETRY_PORT_DIRECTION_INVALID"
        for diagnostic in diagnostics
    )


def _move_patch(bundle, *, suffix: str = "move") -> tuple[VisualPatch, str, float]:
    scene = next(iter(bundle.base_scenes.values()))
    node = next(node for node in scene.nodes if node.parent_scene_node_id)
    patch = VisualPatch(
        patch_id=f"patch:test.{suffix}",
        operation="set-position",
        target_id=node.scene_node_id,
        value={
            "scene_id": scene.scene_id,
            "x": node.bounds.x + 12,
            "y": node.bounds.y,
        },
    )
    return patch, node.scene_node_id, node.bounds.x


def test_visual_patch_history_preserves_source_and_reopens_layout(
    analysis_dir: Path, tmp_path: Path
) -> None:
    before = _source_hashes()
    workspace = tmp_path / ".archcanvas"
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", workspace)
    digest = bundle.document.source_digest
    patch, node_id, original_x = _move_patch(bundle)
    scenes = {scene.scene_id: scene for scene in bundle.base_scenes.values()}
    changed = apply_patch(bundle.document, patch, scenes)
    assert changed.source_digest == digest
    base_scene = next(iter(bundle.base_scenes.values()))
    moved = materialize_scene(base_scene, changed)
    assert next(node for node in moved.nodes if node.scene_node_id == node_id).bounds.x == original_x + 12

    undone = undo_patch(changed)
    assert materialize_scene(base_scene, undone) == base_scene
    redone = redo_patch(undone)
    assert redone == changed
    persist_canvas_document(bundle.document_path, redone)

    reopened = prepare_studio_bundle(analysis_dir / "architecture.json", workspace)
    reopened_scene = next(iter(reopened.materialized_scenes().values()))
    assert next(node for node in reopened_scene.nodes if node.scene_node_id == node_id).bounds.x == original_x + 12
    assert reopened.document.source_digest == digest
    assert load_canvas_document(reopened.document_path) == reopened.document
    assert _source_hashes() == before


def test_shadow_routing_compares_without_replacing_visible_scene(
    analysis_dir: Path, tmp_path: Path
) -> None:
    workspace = tmp_path / ".archcanvas-shadow"
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json",
        workspace,
        routing_mode="shadow",
    )
    state = bundle.state()
    projection_id = state["active_projection_id"]
    report = state["routing"]["reports"][projection_id]

    assert state["routing"]["mode"] == "shadow"
    assert state["routing"]["visible_engine"] == "legacy"
    assert state["routing"]["shadow_engine"] == "atomic-v1"
    assert report["status"] == "compared"
    assert report["compared_edge_count"] == len(state["scenes"][projection_id]["edges"])
    assert report["legacy_metrics"] is not None
    assert report["shadow_receipt"]["engine"] == "atomic-v1"
    assert report["shadow_receipt"]["metrics"] is not None
    assert report["delta"] is not None
    assert len(report["legacy_route_digest"]) == 64
    assert report["route_digest_matches"] == (
        report["legacy_route_digest"] == report["shadow_receipt"]["route_digest"]
    )
    assert state["scenes"][projection_id] == next(
        iter(bundle.materialized_scenes().values())
    ).model_dump(mode="json")
    assert (workspace / "publication" / "current" / "routing-shadow.json").is_file()

    before_digest = report["shadow_receipt"]["input_digest"]
    patch, _, _ = _move_patch(bundle, suffix="shadow-move")
    changed = apply_patch(
        bundle.document,
        patch,
        {scene.scene_id: scene for scene in bundle.base_scenes.values()},
    )
    bundle.save_document(changed)
    updated = bundle.state()["routing"]["reports"][projection_id]
    assert updated["status"] == "compared"
    assert updated["shadow_receipt"]["input_digest"] != before_digest


def test_shadow_routing_sampling_and_visible_switch_guard(
    analysis_dir: Path, tmp_path: Path
) -> None:
    workspace = tmp_path / ".archcanvas-shadow-skip"
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json",
        workspace,
        routing_mode="shadow",
        routing_shadow_sample_rate=0.0,
    )
    state = bundle.state()
    report = state["routing"]["reports"][state["active_projection_id"]]
    assert report["status"] == "not-sampled"
    assert state["capabilities"]["routing_engines"]["atomic_v1_visible"] is False

    legacy = prepare_studio_bundle(
        analysis_dir / "architecture.json",
        workspace,
        routing_mode="legacy",
    )
    persisted = json.loads(
        (workspace / "publication" / "current" / "routing-shadow.json").read_text(
            encoding="utf-8"
        )
    )
    assert legacy.routing_shadow_reports == {}
    assert persisted["mode"] == "legacy"
    assert persisted["shadow_engine"] is None
    assert persisted["reports"] == {}

    atomic = prepare_studio_bundle(
        analysis_dir / "architecture.json",
        tmp_path / ".archcanvas-atomic",
        routing_mode="atomic-v1",
    )
    atomic_state = atomic.state()
    atomic_projection = atomic_state["active_projection_id"]
    atomic_report = atomic_state["routing"]["reports"][atomic_projection]
    atomic_scene = atomic_state["scenes"][atomic_projection]

    assert atomic_state["routing"]["visible_engine"] == "atomic-v1"
    assert atomic_state["capabilities"]["routing_engines"] == {
        "available": ["legacy", "shadow", "atomic-v1"],
        "selected": "atomic-v1",
        "visible": "atomic-v1",
        "atomic_v1_visible": True,
    }
    assert atomic_report["status"] == "routed"
    assert atomic_report["visible_engine"] == "atomic-v1"
    assert atomic_report["receipt"]["metrics"]["invalid_endpoint_count"] == 0
    assert atomic_report["receipt"]["metrics"]["obstacle_intersection_count"] == 0
    assert atomic_scene["edges"]
    assert all(edge["source_port_id"] for edge in atomic_scene["edges"])
    assert all(edge["target_port_id"] for edge in atomic_scene["edges"])
    assert all(
        edge["route_digest"] == atomic_report["receipt"]["route_digest"]
        for edge in atomic_scene["edges"]
    )


def test_routing_runtime_config_reads_and_validates_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARCHCANVAS_ROUTING_ENGINE", "shadow")
    monkeypatch.setenv("ARCHCANVAS_ROUTING_SHADOW_SAMPLE_RATE", "0.25")
    assert routing_runtime_config().mode == "shadow"
    assert routing_runtime_config().shadow_sample_rate == 0.25

    monkeypatch.setenv("ARCHCANVAS_ROUTING_SHADOW_SAMPLE_RATE", "invalid")
    with pytest.raises(ValueError, match="must be a number"):
        routing_runtime_config()

    monkeypatch.setenv("ARCHCANVAS_ROUTING_SHADOW_SAMPLE_RATE", "1.1")
    with pytest.raises(ValueError, match="between 0 and 1"):
        routing_runtime_config()

    monkeypatch.setenv("ARCHCANVAS_ROUTING_ENGINE", "atomic-v1")
    monkeypatch.setenv("ARCHCANVAS_ROUTING_SHADOW_SAMPLE_RATE", "1.0")
    assert routing_runtime_config().mode == "atomic-v1"


def test_atomic_routing_rebuilds_after_visual_patch_and_exports_same_geometry(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json",
        tmp_path / ".archcanvas-atomic-patch",
        routing_mode="atomic-v1",
    )
    state = bundle.state()
    projection_id = state["active_projection_id"]
    first_report = state["routing"]["reports"][projection_id]
    first_digest = first_report["receipt"]["route_digest"]

    patch, _, _ = _move_patch(bundle, suffix="atomic-move")
    changed = apply_patch(
        bundle.document,
        patch,
        {scene.scene_id: scene for scene in bundle.base_scenes.values()},
    )
    bundle.save_document(changed)
    updated = bundle.state()
    report = updated["routing"]["reports"][projection_id]
    scene = updated["scenes"][projection_id]

    assert report["status"] == "routed"
    assert report["receipt"]["route_digest"] != first_digest
    assert all(
        edge["route_digest"] == report["receipt"]["route_digest"]
        for edge in scene["edges"]
    )
    svg = bundle.export_svg()
    for edge in scene["edges"]:
        points = " ".join(
            f'{point["x"]:.1f},{point["y"]:.1f}' for point in edge["points"]
        )
        assert f'points="{points}"' in svg
        assert f'data-route-digest="{edge["route_digest"]}"' in svg


def test_atomic_routing_failure_falls_back_to_legacy_scene(
    analysis_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json",
        tmp_path / ".archcanvas-atomic-fallback",
        routing_mode="atomic-v1",
    )
    legacy = {
        projection_id: materialize_scene(scene, bundle.document)
        for projection_id, scene in bundle.base_scenes.items()
    }

    def fail_atomic(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("atomic exploded")

    monkeypatch.setattr("archcanvas_studio.bundle.route_atomic_scene", fail_atomic)
    state = bundle.state()
    projection_id = state["active_projection_id"]
    report = state["routing"]["reports"][projection_id]

    assert state["routing"]["visible_engine"] == "legacy"
    assert report["status"] == "fallback"
    assert report["error_code"] == "atomic-routing-failed"
    assert report["error_message"] == "atomic exploded"
    assert state["scenes"][projection_id] == legacy[projection_id].model_dump(mode="json")


def test_shadow_routing_failure_does_not_change_visible_scene(
    analysis_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json",
        tmp_path / ".archcanvas-shadow-failure",
        routing_mode="shadow",
    )
    visible_before = {
        projection_id: scene.model_dump(mode="json")
        for projection_id, scene in bundle.materialized_scenes().items()
    }

    def fail_shadow(*_args: object) -> None:
        raise RuntimeError("shadow exploded")

    monkeypatch.setattr(
        "archcanvas_studio.bundle.compare_shadow_routing",
        fail_shadow,
    )
    bundle.refresh_routing_shadow()

    state = bundle.state()
    projection_id = state["active_projection_id"]
    report = state["routing"]["reports"][projection_id]
    assert report["status"] == "failed"
    assert report["error_code"] == "shadow-routing-failed"
    assert report["error_message"] == "shadow exploded"
    assert state["scenes"] == visible_before
    assert {
        item: scene.model_dump(mode="json")
        for item, scene in bundle.materialized_scenes().items()
    } == visible_before


def test_visual_patch_rejects_unknown_target(analysis_dir: Path, tmp_path: Path) -> None:
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", tmp_path / ".archcanvas")
    scene = next(iter(bundle.base_scenes.values()))
    patch = VisualPatch(
        patch_id="patch:test.invalid",
        operation="set-position",
        target_id="scenenode:missing",
        value={"scene_id": scene.scene_id, "x": 1, "y": 1},
    )
    with pytest.raises(ValueError, match="valid scene and target"):
        apply_patch(
            bundle.document,
            patch,
            {item.scene_id: item for item in bundle.base_scenes.values()},
        )


@pytest.mark.parametrize("operation", ["set-alignment", "set-gap"])
def test_aggregate_visual_operations_require_patch_batch(
    analysis_dir: Path, tmp_path: Path, operation: str
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    scene = next(iter(bundle.base_scenes.values()))
    node = next(item for item in scene.nodes if item.parent_scene_node_id)
    patch = VisualPatch(
        patch_id=f"patch:test.{operation}",
        operation=operation,
        target_id=node.scene_node_id,
        value={"scene_id": scene.scene_id, "gap": 16},
    )
    with pytest.raises(ValueError, match="must be lowered.*PatchBatch"):
        apply_patch(bundle.document, patch, {scene.scene_id: scene})


def test_visual_metadata_and_palette_materialize_and_export(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    scene = next(iter(bundle.base_scenes.values()))
    node = next(item for item in scene.nodes if item.parent_scene_node_id)
    edge = scene.edges[0]
    digest = bundle.document.source_digest
    patches = [
        VisualPatch(
            patch_id="patch:test.caption",
            operation="set-caption",
            value={"scene_id": scene.scene_id, "caption": "Verified architecture"},
        ),
        VisualPatch(
            patch_id="patch:test.legend",
            operation="set-legend-placement",
            value={"scene_id": scene.scene_id, "placement": "bottom-right"},
        ),
        VisualPatch(
            patch_id="patch:test.annotation",
            operation="add-annotation",
            target_id="annotation:test.note",
            value={
                "scene_id": scene.scene_id,
                "text": "Review this boundary",
                "x": node.bounds.x,
                "y": node.bounds.y + node.bounds.height + 8,
                "width": 180,
                "height": 52,
            },
        ),
        VisualPatch(
            patch_id="patch:test.palette",
            operation="set-palette",
            value={
                "scene_id": scene.scene_id,
                "overrides": {
                    node.scene_node_id: "#abcdef",
                    f"{node.scene_node_id}:stroke": "#123456",
                    edge.scene_edge_id: "#654321",
                    "annotation:test.note": "#fff4aa",
                },
            },
        ),
    ]
    changed = bundle.document
    for patch in patches:
        changed = apply_patch(changed, patch, {scene.scene_id: scene})

    materialized = materialize_scene(scene, changed)
    changed_node = next(
        item for item in materialized.nodes if item.scene_node_id == node.scene_node_id
    )
    changed_edge = next(
        item for item in materialized.edges if item.scene_edge_id == edge.scene_edge_id
    )
    assert materialized.caption == "Verified architecture"
    assert materialized.legend_placement == "bottom-right"
    assert materialized.annotations[0].text == "Review this boundary"
    assert materialized.annotations[0].fill == "#fff4aa"
    assert changed_node.fill == "#abcdef"
    assert changed_node.stroke == "#123456"
    assert changed_edge.stroke == "#654321"
    assert changed.source_digest == digest
    state = derive_view_state(changed)
    assert state["legend_placement"] == "bottom-right"
    assert state["annotations"][0]["annotation_id"] == "annotation:test.note"
    svg = render_svg(materialized)
    assert "Verified architecture" in svg
    assert "Review this boundary" in svg
    assert 'class="scene-legend"' in svg


def test_palette_rejects_unknown_visual_target(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    scene = next(iter(bundle.base_scenes.values()))
    patch = VisualPatch(
        patch_id="patch:test.unknown-palette-target",
        operation="set-palette",
        value={"scene_id": scene.scene_id, "overrides": {"scene-node:missing": "#fff"}},
    )
    with pytest.raises(ValueError, match="unknown visual target"):
        apply_patch(bundle.document, patch, {scene.scene_id: scene})


def test_theme_and_camera_persist_across_reopen(
    analysis_dir: Path, tmp_path: Path
) -> None:
    workspace = tmp_path / ".archcanvas"
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", workspace)
    scene = next(iter(bundle.base_scenes.values()))
    scenes = {item.scene_id: item for item in bundle.base_scenes.values()}
    document = apply_patch(
        bundle.document,
        VisualPatch(
            patch_id="patch:test.theme",
            operation="set-theme",
            value={"theme": "studio-dark", "scene_id": scene.scene_id},
        ),
        scenes,
    )
    document = apply_patch(
        document,
        VisualPatch(
            patch_id="patch:test.camera",
            operation="set-camera",
            value={"scene_id": scene.scene_id, "x": -24, "y": -12, "zoom": 1.25},
        ),
        scenes,
    )
    persist_canvas_document(bundle.document_path, document)

    reopened = prepare_studio_bundle(analysis_dir / "architecture.json", workspace)
    state = derive_view_state(reopened.document)
    assert state["theme"] == "studio-dark"
    assert state["cameras"][scene.scene_id] == {
        "x": -24,
        "y": -12,
        "zoom": 1.25,
    }


def test_layout_mode_recompiles_and_persists_across_reopen(
    analysis_dir: Path, tmp_path: Path
) -> None:
    workspace = tmp_path / ".archcanvas"
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", workspace)
    assert bundle.state()["view_state"]["layout_mode"] == "auto"
    assert bundle.state()["capabilities"]["layout_modes"] == [
        "auto",
        "dual-swimlane",
        "single-lane",
        "hierarchical",
        "branch-tree",
        "force-directed",
        "radial",
        "orthogonal",
    ]

    canonical_nodes = set(next(iter(bundle.views.values())).canonical_node_ids)
    bundle.set_layout_mode("branch-tree")
    state = bundle.state()
    assert state["view_state"]["layout_mode"] == "branch-tree"
    assert next(iter(state["scenes"].values()))["layout_family"] == "branch-tree"
    assert {
        canonical_id
        for node in next(iter(state["scenes"].values()))["nodes"]
        for canonical_id in node["canonical_node_ids"]
    } == canonical_nodes

    reopened = prepare_studio_bundle(analysis_dir / "architecture.json", workspace)
    assert reopened.state()["view_state"]["layout_mode"] == "branch-tree"
    assert next(iter(reopened.base_scenes.values())).layout_family == "branch-tree"
    with pytest.raises(ValueError, match="unknown layout mode"):
        reopened.set_layout_mode("spiral")


def test_module_and_source_navigation_share_canonical_objects_and_preference(
    analysis_dir: Path, tmp_path: Path
) -> None:
    workspace = tmp_path / ".archcanvas"
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", workspace)
    state = bundle.state()
    navigation = state["navigation"]
    assert navigation["active_projection"] == "module"
    assert set(navigation["projections"]) == {"module", "source"}
    module_rows = navigation["projections"]["module"]["nodes"]
    source_rows = navigation["projections"]["source"]["nodes"]
    assert len({row["id"] for row in module_rows}) == len(module_rows)
    assert len({row["id"] for row in source_rows}) == len(source_rows)
    module_ids = {canonical for row in module_rows for canonical in row["canonical_ids"]}
    source_ids = {canonical for row in source_rows for canonical in row["canonical_ids"]}
    assert {node.node_id for node in bundle.architecture.nodes} <= module_ids
    assert {node.node_id for node in bundle.architecture.nodes} <= source_ids
    assert any(row["kind"] == "file" for row in source_rows)
    assert any(row["kind"] == "class" for row in source_rows)
    assert any(row["kind"] == "binding" for row in source_rows)
    assert any(row["kind"] == "return" for row in source_rows)
    assert any(row["kind"] == "callsite" for row in source_rows)
    assert max(row["depth"] for row in source_rows) >= 7
    assert all("min_level" not in row for row in source_rows)
    assert any(row["child_count"] > 0 for row in source_rows)
    assert any(row["relation"] == "producer-output" for row in source_rows)
    assert any(row["relation"] == "consumer-reference" for row in source_rows)
    assert all(
        row["relation"]
        in {
            "source-containment",
            "invocation",
            "assignment",
            "return",
            "producer-output",
            "consumer-reference",
            "module-containment",
        }
        for row in [*module_rows, *source_rows]
    )
    assert navigation["projections"]["source"]["description"] == (
        "文件 / 作用域 / 语句 / 表达式逐级包含；引用关系来自 Exact IR"
    )

    calls_by_line: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for row in source_rows:
        if row["kind"] == "callsite":
            calls_by_line[(row["path"], row["span"]["start_line"])].append(row)
    same_line_calls = next(
        calls
        for calls in calls_by_line.values()
        if len(calls) > 1 and any(call["canonical_ids"] for call in calls)
    )
    assert len({call["id"] for call in same_line_calls}) == len(same_line_calls)
    assert len(
        {
            (
                call["span"]["start_line"],
                call["span"]["start_column"],
                call["span"]["end_line"],
                call["span"]["end_column"],
            )
            for call in same_line_calls
        }
    ) == len(same_line_calls)
    source_by_id = {row["id"]: row for row in source_rows}
    same_line_ids = {call["id"] for call in same_line_calls}
    assert any(call["parent_id"] in same_line_ids for call in same_line_calls)
    exact_call = next(
        call for call in same_line_calls if call["binding_status"] == "exact"
    )
    assert source_by_id[exact_call["parent_id"]]["kind"] == "binding"
    calls_by_parent: dict[str, list[dict[str, object]]] = defaultdict(list)
    for call in same_line_calls:
        calls_by_parent[call["parent_id"]].append(call)
    sibling_calls = next(calls for calls in calls_by_parent.values() if len(calls) > 1)
    assert all(call["sibling_count"] > 1 for call in sibling_calls)
    assert len({call["sibling_index"] for call in sibling_calls}) == len(sibling_calls)
    assert sum(call["binding_status"] == "exact" for call in same_line_calls) == 1
    assert all(
        call["secondary_label"].endswith(
            f":{call['span']['start_line']}:{call['span']['start_column'] + 1}"
        )
        for call in same_line_calls
    )

    bundle.set_navigation_view(
        "source",
        expansions={
            "module": [next(row["id"] for row in module_rows if row["parent_id"] is None)],
            "source": ["source:root"],
        },
    )
    assert bundle.state()["view_state"]["navigation_view"] == "source"
    assert bundle.state()["view_state"]["source_expansion"] == ["source:root"]
    module_root = next(row["id"] for row in module_rows if row["parent_id"] is None)
    assert bundle.state()["view_state"]["module_expansion"] == [module_root]
    assert "active_level" not in bundle.state()["view_state"]
    reopened = prepare_studio_bundle(analysis_dir / "architecture.json", workspace)
    assert reopened.state()["navigation"]["active_projection"] == "source"
    assert reopened.state()["view_state"]["source_expansion"] == ["source:root"]
    assert reopened.state()["view_state"]["module_expansion"] == [module_root]

    legacy_state = dict(reopened.document.view_state)
    legacy_state["active_level"] = "L3"
    reopened.save_document(reopened.document.model_copy(update={"view_state": legacy_state}))
    reopened.set_navigation_view(
        "source",
        expansions={"module": [module_root], "source": []},
    )
    collapsed = prepare_studio_bundle(analysis_dir / "architecture.json", workspace)
    assert collapsed.state()["view_state"]["source_expansion"] == []
    assert "active_level" not in collapsed.state()["view_state"]


def test_module_expansion_compiles_stable_arbitrary_frontiers(
    analysis_dir: Path, tmp_path: Path
) -> None:
    workspace = tmp_path / ".archcanvas"
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", workspace)
    rows = bundle.state()["navigation"]["projections"]["module"]["nodes"]
    root_id = next(row["id"] for row in rows if row["parent_id"] is None)
    expandable = [
        row["id"]
        for row in rows
        if row["child_count"] > 0 and row["id"] != root_id
    ]
    assert expandable
    collapsed_id = bundle.state()["active_projection_id"]

    bundle.set_navigation_view(
        "module",
        expansions={"module": [root_id, expandable[0]], "source": []},
    )
    partial = bundle.state()
    assert partial["active_projection_id"] != collapsed_id
    assert expandable[0] in partial["views"][partial["active_projection_id"]][
        "expanded_node_ids"
    ]

    bundle.set_navigation_view(
        "module",
        expansions={"module": [expandable[0]], "source": []},
    )
    hidden_descendant = bundle.state()
    assert hidden_descendant["active_projection_id"] == collapsed_id

    bundle.set_navigation_view(
        "module",
        expansions={"module": [root_id, expandable[0]], "source": []},
    )
    partial = bundle.state()

    reopened = prepare_studio_bundle(analysis_dir / "architecture.json", workspace)
    assert reopened.state()["active_projection_id"] == partial["active_projection_id"]

    all_expandable = [row["id"] for row in rows if row["child_count"] > 0]
    reopened.set_navigation_view(
        "module",
        expansions={"module": all_expandable, "source": []},
    )
    full = reopened.state()
    assert full["views"][full["active_projection_id"]]["fully_expanded"] is True


def test_autoformer_module_navigation_is_semantic_preorder(tmp_path: Path) -> None:
    fixture = ROOT / "fixtures" / "tier_a" / "autoformer"
    analyzed = analyze_project(
        fixture,
        "models.Autoformer:Model",
        "long_term_forecast",
        "eval",
        (fixture / "config.json").read_bytes(),
        fixture / "config.json",
    )
    analysis_dir = tmp_path / "autoformer-analysis"
    analysis_dir.mkdir()
    (analysis_dir / "architecture.json").write_text(
        analyzed.architecture.model_dump_json()
    )
    (analysis_dir / "source-snapshot.json").write_text(
        analyzed.snapshot.model_dump_json()
    )
    (analysis_dir / "evidence-ledger.json").write_text(
        json.dumps([record.model_dump(mode="json") for record in analyzed.evidence])
    )
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".autoformer-archcanvas"
    )
    rows = bundle.state()["navigation"]["projections"]["module"]["nodes"]
    root = next(row for row in rows if row["parent_id"] is None)
    root_children = [row for row in rows if row["parent_id"] == root["id"]]
    assert [row["label"].lower() for row in root_children] == [
        "inputs",
        "decomposition",
        "encoder",
        "decoder",
        "output",
    ]

    positions = {row["id"]: index for index, row in enumerate(rows)}
    assert all(
        row["parent_id"] is None or positions[row["parent_id"]] < positions[row["id"]]
        for row in rows
    )
    seasonal = next(row for row in rows if row["label"] == "Seasonal zero seed")
    decomposition = next(row for row in rows if row["label"] == "decomposition")
    assert seasonal["parent_id"] == decomposition["id"]


@pytest.mark.parametrize(
    ("fixture_name", "entrypoint", "task"),
    [
        ("transformer", "model:Transformer", "inference"),
        ("autoformer", "models.Autoformer:Model", "long_term_forecast"),
        ("itransformer", "model.iTransformer:Model", "long_term_forecast"),
        ("patchtst", "models.PatchTST:Model", "long_term_forecast"),
        ("timemixer", "models.TimeMixer:Model", "long_term_forecast"),
    ],
)
def test_fresh_tier_a_analysis_retains_expandable_studio_hierarchy(
    fixture_name: str,
    entrypoint: str,
    task: str,
    tmp_path: Path,
) -> None:
    fixture = ROOT / "fixtures" / "tier_a" / fixture_name
    analyzed = analyze_project(
        fixture,
        entrypoint,
        task,
        "eval",
        (fixture / "config.json").read_bytes(),
        fixture / "config.json",
    )
    analysis_dir = tmp_path / f"{fixture_name}-analysis"
    analysis_dir.mkdir()
    (analysis_dir / "architecture.json").write_text(
        analyzed.architecture.model_dump_json()
    )
    (analysis_dir / "source-snapshot.json").write_text(
        analyzed.snapshot.model_dump_json()
    )
    (analysis_dir / "evidence-ledger.json").write_text(
        json.dumps([record.model_dump(mode="json") for record in analyzed.evidence])
    )
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json",
        tmp_path / f".{fixture_name}-archcanvas",
    )
    state = bundle.state()
    projection_id = state["active_projection_id"]
    rows = state["navigation"]["projections"]["module"]["nodes"]
    expandable_ids = [row["id"] for row in rows if row["child_count"] > 0]
    collapsed_node_count = len(state["scenes"][projection_id]["nodes"])

    assert max(row["depth"] for row in rows) >= 2
    assert len(expandable_ids) >= 2

    bundle.set_navigation_view(
        "module",
        expansions={"module": expandable_ids, "source": []},
    )
    expanded = bundle.state()
    expanded_view = expanded["views"][expanded["active_projection_id"]]
    expanded_scene = expanded["scenes"][expanded["active_projection_id"]]

    assert expanded_view["fully_expanded"] is True
    assert len(expanded_scene["nodes"]) > collapsed_node_count


def test_encoder_expansion_preserves_container_and_reveals_immediate_structure(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    module_rows = bundle.state()["navigation"]["projections"]["module"]["nodes"]
    root_id = next(row["id"] for row in module_rows if row["parent_id"] is None)
    encoder = next(row for row in module_rows if row["label"] == "encoder")

    collapsed_state = bundle.state()
    collapsed_view = collapsed_state["views"][collapsed_state["active_projection_id"]]
    collapsed_encoder = next(
        node
        for node in collapsed_view["nodes"]
        if node["attributes"].get("hierarchy_node_id") == encoder["id"]
    )
    assert collapsed_encoder["collapsed"] is True
    assert len(collapsed_encoder["canonical_node_ids"]) > 1

    bundle.set_navigation_view(
        "module",
        expansions={"module": [root_id, encoder["id"]], "source": []},
    )
    expanded_state = bundle.state()
    expanded_view = expanded_state["views"][expanded_state["active_projection_id"]]
    expanded_encoder = next(
        node
        for node in expanded_view["nodes"]
        if node["attributes"].get("hierarchy_node_id") == encoder["id"]
    )
    assert expanded_encoder["collapsed"] is False
    assert expanded_encoder["canonical_node_ids"] == []
    children = [
        node
        for node in expanded_view["nodes"]
        if node["parent_view_node_id"] == expanded_encoder["view_node_id"]
    ]
    assert {node["semantic_name"] for node in children} >= {
        "q",
        "k",
        "v",
        "encoder_norm",
    }
    scene = expanded_state["scenes"][expanded_state["active_projection_id"]]
    scene_encoder = next(
        node for node in scene["nodes"] if node["view_node_id"] == expanded_encoder["view_node_id"]
    )
    assert scene_encoder["shape"] == "container"
    assert any(
        node["parent_scene_node_id"] == scene_encoder["scene_node_id"]
        for node in scene["nodes"]
    )


def test_repeated_camera_updates_are_compacted(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", tmp_path / ".archcanvas")
    scene = next(iter(bundle.base_scenes.values()))
    scenes = {item.scene_id: item for item in bundle.base_scenes.values()}
    document = bundle.document
    for index in range(5):
        document = apply_patch(
            document,
            VisualPatch(
                patch_id=f"patch:test.camera-{index}",
                operation="set-camera",
                value={"scene_id": scene.scene_id, "x": -index, "y": index, "zoom": 1.1},
            ),
            scenes,
        )
    camera_patches = [
        item for item in document.visual_patches if item.operation == "set-camera"
    ]
    assert len(camera_patches) == 1
    assert derive_view_state(document)["cameras"][scene.scene_id]["x"] == -4


def test_patch_batch_is_atomic_and_undoes_as_one_action(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", tmp_path / ".archcanvas")
    scene = next(iter(bundle.base_scenes.values()))
    nodes = [item for item in scene.nodes if item.parent_scene_node_id][:2]
    batch = PatchBatch(
        batch_id="batch:test.align",
        description="Align two nodes",
        patches=[
            VisualPatch(
                patch_id=f"patch:test.align-{index}",
                operation="set-position",
                target_id=node.scene_node_id,
                value={"scene_id": scene.scene_id, "x": node.bounds.x + 10, "y": node.bounds.y},
            )
            for index, node in enumerate(nodes)
        ],
    )
    scenes = {item.scene_id: item for item in bundle.base_scenes.values()}
    changed = apply_patch_batch(bundle.document, batch, scenes)
    assert len(changed.visual_patches) == 2
    undone = undo_patch(changed)
    assert not undone.visual_patches
    assert [item.patch_id for item in undone.redo_patches] == [
        "patch:test.align-0",
        "patch:test.align-1",
    ]
    assert redo_patch(undone).visual_patches == changed.visual_patches


def test_equal_size_alignment_uses_primary_node_and_undoes_as_one_action(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    baseline = next(iter(bundle.base_scenes.values()))
    candidates = [node for node in baseline.nodes if node.parent_scene_node_id]
    first, primary = candidates[:2]
    first = first.model_copy(
        update={
            "bounds": first.bounds.model_copy(
                update={
                    "width": primary.bounds.width + 17,
                    "height": primary.bounds.height + 11,
                }
            )
        }
    )
    scene = baseline.model_copy(
        update={
            "nodes": [
                first if node.scene_node_id == first.scene_node_id else node
                for node in baseline.nodes
            ]
        }
    )
    batch = alignment_batch(
        scene,
        [first.scene_node_id, primary.scene_node_id],
        "same-size",
        pinned_ids=set(),
        batch_id="batch:test.same-size",
    )

    assert len(batch.patches) == 1
    assert batch.patches[0].operation == "set-size"
    assert batch.patches[0].value == {
        "scene_id": scene.scene_id,
        "width": primary.bounds.width,
        "height": primary.bounds.height,
    }
    changed = apply_patch_batch(
        bundle.document,
        batch,
        {scene.scene_id: scene},
    )
    resized = next(
        node
        for node in materialize_scene(scene, changed).nodes
        if node.scene_node_id == first.scene_node_id
    )
    assert (resized.bounds.width, resized.bounds.height) == (
        primary.bounds.width,
        primary.bounds.height,
    )
    assert not undo_patch(changed).visual_patches


def test_container_move_translates_descendants_and_internal_edges_atomically(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    rows = bundle.state()["navigation"]["projections"]["module"]["nodes"]
    bundle.set_navigation_view(
        "module",
        expansions={
            "module": [row["id"] for row in rows if row["child_count"] > 0],
            "source": [],
        },
    )
    scene = next(iter(bundle.base_scenes.values()))
    view = next(iter(bundle.views.values()))
    encoder_row = next(row for row in rows if row["label"] == "encoder")
    encoder_view = next(
        node
        for node in view.nodes
        if node.attributes.get("hierarchy_node_id") == encoder_row["id"]
    )
    container = next(
        node for node in scene.nodes if node.view_node_id == encoder_view.view_node_id
    )
    children: dict[str, list[str]] = defaultdict(list)
    for node in scene.nodes:
        if node.parent_scene_node_id:
            children[node.parent_scene_node_id].append(node.scene_node_id)
    moving_ids: set[str] = set()

    def collect(node_id: str) -> None:
        if node_id in moving_ids:
            return
        moving_ids.add(node_id)
        for child_id in children[node_id]:
            collect(child_id)

    collect(container.scene_node_id)
    assert len(moving_ids) > 1
    internal_edge = next(
        edge
        for edge in scene.edges
        if {edge.source_scene_node_id, edge.target_scene_node_id} <= moving_ids
    )
    delta_x, delta_y = 37.0, 23.0
    batch = PatchBatch(
        batch_id="batch:test.move-container",
        description="Move encoder with descendants",
        patches=[
            VisualPatch(
                patch_id=f"patch:test.move-container-{index}",
                operation="set-position",
                target_id=node.scene_node_id,
                value={
                    "scene_id": scene.scene_id,
                    "x": node.bounds.x + delta_x,
                    "y": node.bounds.y + delta_y,
                },
            )
            for index, node in enumerate(scene.nodes)
            if node.scene_node_id in moving_ids
        ],
    )
    original = materialize_scene(scene, bundle.document)
    changed = apply_patch_batch(
        bundle.document,
        batch,
        {item.scene_id: item for item in bundle.base_scenes.values()},
        enforce_containment=True,
    )
    moved = materialize_scene(scene, changed)
    original_nodes = {node.scene_node_id: node for node in original.nodes}
    moved_nodes = {node.scene_node_id: node for node in moved.nodes}
    for node_id in moving_ids:
        assert moved_nodes[node_id].bounds.x == original_nodes[node_id].bounds.x + delta_x
        assert moved_nodes[node_id].bounds.y == original_nodes[node_id].bounds.y + delta_y
    moved_edge = next(
        edge for edge in moved.edges if edge.scene_edge_id == internal_edge.scene_edge_id
    )
    assert [
        (point.x, point.y) for point in moved_edge.points
    ] == [
        (point.x + delta_x, point.y + delta_y) for point in internal_edge.points
    ]
    undone = undo_patch(changed)
    assert materialize_scene(scene, undone) == original
    redone = redo_patch(undone)
    assert materialize_scene(scene, redone) == moved


def test_containment_enforcement_rejects_detached_child(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    rows = bundle.state()["navigation"]["projections"]["module"]["nodes"]
    bundle.set_navigation_view(
        "module",
        expansions={
            "module": [row["id"] for row in rows if row["child_count"] > 0],
            "source": [],
        },
    )
    scene = next(iter(bundle.base_scenes.values()))
    by_id = {node.scene_node_id: node for node in scene.nodes}
    child = next(
        node
        for node in scene.nodes
        if node.parent_scene_node_id
        and by_id[node.parent_scene_node_id].parent_scene_node_id is not None
    )
    parent = by_id[child.parent_scene_node_id]
    patch = VisualPatch(
        patch_id="patch:test.detach-child",
        operation="set-position",
        target_id=child.scene_node_id,
        value={
            "scene_id": scene.scene_id,
            "x": parent.bounds.x + parent.bounds.width + 1,
            "y": child.bounds.y,
        },
    )

    with pytest.raises(ValueError, match="would detach"):
        apply_patch(
            bundle.document,
            patch,
            {scene.scene_id: scene},
            enforce_containment=True,
        )


def test_auto_layout_restores_compound_baseline_without_breaking_containment(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    rows = bundle.state()["navigation"]["projections"]["module"]["nodes"]
    bundle.set_navigation_view(
        "module",
        expansions={
            "module": [row["id"] for row in rows if row["child_count"] > 0],
            "source": [],
        },
    )
    baseline = next(iter(bundle.base_scenes.values()))
    parent_ids = {
        node.parent_scene_node_id
        for node in baseline.nodes
        if node.parent_scene_node_id is not None
    }
    parent = next(
        node
        for node in baseline.nodes
        if node.scene_node_id in parent_ids and node.parent_scene_node_id is not None
    )
    child = next(
        node
        for node in baseline.nodes
        if node.parent_scene_node_id == parent.scene_node_id
    )
    moved_patch = VisualPatch(
        patch_id="patch:test.damage-containment",
        operation="set-position",
        target_id=child.scene_node_id,
        value={
            "scene_id": baseline.scene_id,
            "x": parent.bounds.x + parent.bounds.width + 40.0,
            "y": child.bounds.y,
        },
    )
    scenes = {baseline.scene_id: baseline}
    damaged_document = apply_patch(bundle.document, moved_patch, scenes)
    damaged = materialize_scene(baseline, damaged_document)
    damaged_gate, _ = validate_geometry(damaged)
    assert damaged_gate.status == "failed"

    batch = auto_layout_batch(
        damaged,
        baseline_scene=baseline,
        pinned_ids=set(),
        batch_id="batch:test.restore-layout",
    )
    restored_document = apply_patch_batch(damaged_document, batch, scenes)
    restored = materialize_scene(baseline, restored_document)
    restored_gate, diagnostics = validate_geometry(restored)
    assert restored_gate.status == "passed", diagnostics
    assert restored == baseline


def test_layout_candidates_are_deterministic_preview_only_and_stale_guarded(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    original_document = bundle.document
    first = bundle.layout_candidates()
    second = bundle.layout_candidates()
    assert first
    assert [item[0]["candidate_id"] for item in first] == [
        item[0]["candidate_id"] for item in second
    ]
    assert [item[0]["score"] for item in first] == [item[0]["score"] for item in second]
    assert bundle.document == original_document
    assert all(
        validate_geometry(VisualScene.model_validate(item[0]["scene"]))[0].status
        == "passed"
        for item in first
    )

    server = _server_without_socket(bundle)
    payloads = server.create_layout_candidates()
    stale_id = str(payloads[0]["candidate_id"])
    patch, _, _ = _move_patch(bundle, suffix="stale-layout-candidate")
    scenes = {scene.scene_id: scene for scene in bundle.base_scenes.values()}
    bundle.save_document(apply_patch(bundle.document, patch, scenes))
    with pytest.raises(ValueError, match="fingerprint is stale"):
        server.apply_layout_candidate(stale_id)
    assert not server.layout_candidates

    payloads = server.create_layout_candidates()
    before_count = len(bundle.document.visual_patches)
    source_digest = bundle.document.source_digest
    state = server.apply_layout_candidate(str(payloads[0]["candidate_id"]))
    assert len(bundle.document.visual_patches) > before_count
    assert bundle.document.source_digest == source_digest
    assert not server.layout_candidates
    assert state["document"]["source_digest"] == source_digest


def test_layout_candidates_keep_pinned_node_bounds(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    scene = next(iter(bundle.materialized_scenes().values()))
    pinned_node = next(node for node in scene.nodes if node.parent_scene_node_id)
    movable_node = next(
        node
        for node in scene.nodes
        if node.parent_scene_node_id == pinned_node.parent_scene_node_id
        and node.scene_node_id != pinned_node.scene_node_id
    )
    scenes = {scene.scene_id: next(iter(bundle.base_scenes.values()))}
    document = apply_patch(
        bundle.document,
        VisualPatch(
            patch_id="patch:test.pin-layout-candidate",
            operation="set-pin",
            target_id=pinned_node.scene_node_id,
            value={"scene_id": scene.scene_id, "enabled": True},
        ),
        scenes,
    )
    document = apply_patch(
        document,
        VisualPatch(
            patch_id="patch:test.move-for-layout-candidate",
            operation="set-position",
            target_id=movable_node.scene_node_id,
            value={
                "scene_id": scene.scene_id,
                "x": movable_node.bounds.x + 12,
                "y": movable_node.bounds.y,
            },
        ),
        scenes,
    )
    bundle.save_document(document)
    candidates = bundle.layout_candidates()
    assert candidates
    for payload, _ in candidates:
        preview = VisualScene.model_validate(payload["scene"])
        preview_node = next(
            node
            for node in preview.nodes
            if node.scene_node_id == pinned_node.scene_node_id
        )
        assert preview_node.bounds == pinned_node.bounds


def test_auto_route_uses_distributed_exterior_corridors_for_long_edges(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    rows = bundle.state()["navigation"]["projections"]["module"]["nodes"]
    bundle.set_navigation_view(
        "module",
        expansions={
            "module": [row["id"] for row in rows if row["child_count"] > 0],
            "source": [],
        },
    )
    scene = next(iter(bundle.materialized_scenes().values()))
    canonical = next(
        edge
        for edge in bundle.architecture.edges
        if edge.producer_id == "node:input.src"
        and edge.consumer_id == "node:enc_residual"
    )
    scene_edge = next(
        edge for edge in scene.edges if canonical.edge_id in edge.canonical_edge_ids
    )
    batch = auto_route_batch(scene, batch_id="batch:test.auto-route")
    route_patch = next(
        patch for patch in batch.patches if patch.target_id == scene_edge.scene_edge_id
    )
    encoder = next(
        node
        for node in scene.nodes
        if node.shape == "container" and " ".join(node.label_lines).lower() == "encoder"
    )
    points = route_patch.value["points"]
    exterior_verticals = [
        (start, end)
        for start, end in pairwise(points)
        if start["x"] == end["x"]
        and (
            start["x"] < encoder.bounds.x
            or start["x"] > encoder.bounds.x + encoder.bounds.width
        )
    ]
    assert exterior_verticals
    assert max(
        abs(end["y"] - start["y"]) for start, end in exterior_verticals
    ) > encoder.bounds.height * 0.75

    source = next(
        node
        for node in scene.nodes
        if node.scene_node_id == scene_edge.source_scene_node_id
    )
    for consumer_id in (
        "node:encoder_q_proj",
        "node:encoder_k_proj",
        "node:encoder_v_proj",
    ):
        canonical_qkv = next(
            edge
            for edge in bundle.architecture.edges
            if edge.producer_id == "node:input.src"
            and edge.consumer_id == consumer_id
        )
        qkv_edge = next(
            edge
            for edge in scene.edges
            if canonical_qkv.edge_id in edge.canonical_edge_ids
        )
        qkv_patch = next(
            patch for patch in batch.patches if patch.target_id == qkv_edge.scene_edge_id
        )
        qkv_target = next(
            node
            for node in scene.nodes
            if node.scene_node_id == qkv_edge.target_scene_node_id
        )
        qkv_points = qkv_patch.value["points"]
        assert qkv_points[0]["y"] == source.bounds.y
        assert qkv_points[-1]["y"] == qkv_target.bounds.y + qkv_target.bounds.height

    for strategy in ("avoid", "balanced", "compact"):
        strategy_batch = auto_route_batch(
            scene,
            batch_id=f"batch:test.auto-route.{strategy}",
            strategy=strategy,
        )
        strategy_document = apply_patch_batch(
            bundle.document,
            strategy_batch,
            {item.scene_id: item for item in bundle.base_scenes.values()},
        )
        strategy_scene = materialize_scene(
            next(iter(bundle.base_scenes.values())), strategy_document
        )
        strategy_gate, strategy_diagnostics = validate_geometry(strategy_scene)
        assert strategy_gate.status == "passed", strategy_diagnostics

    base_scene = next(iter(bundle.base_scenes.values()))
    original = materialize_scene(base_scene, bundle.document)
    changed = apply_patch_batch(
        bundle.document,
        batch,
        {item.scene_id: item for item in bundle.base_scenes.values()},
    )
    routed = materialize_scene(base_scene, changed)
    changed_edge = next(
        edge for edge in routed.edges if edge.scene_edge_id == scene_edge.scene_edge_id
    )
    assert [(point.x, point.y) for point in changed_edge.points] == [
        (point["x"], point["y"]) for point in points
    ]
    gate, diagnostics = validate_geometry(routed)
    assert gate.status == "passed", diagnostics
    assert not diagnostics

    target = next(
        node for node in routed.nodes if node.scene_node_id == changed_edge.target_scene_node_id
    )
    trunk = changed_edge.points[-2]
    top_x = target.bounds.x + target.bounds.width / 2
    top_y = target.bounds.y
    moved_points = [
        *changed_edge.points[:-2],
        trunk,
        ScenePoint(x=trunk.x, y=top_y - 24.0),
        ScenePoint(x=top_x, y=top_y - 24.0),
        ScenePoint(x=top_x, y=top_y),
    ]
    moved_edge = changed_edge.model_copy(update={"points": moved_points})
    moved_scene = routed.model_copy(
        update={
            "edges": [
                moved_edge if edge.scene_edge_id == moved_edge.scene_edge_id else edge
                for edge in routed.edges
            ]
        }
    )
    gate, diagnostics = validate_geometry(moved_scene)
    assert gate.status == "passed", diagnostics
    assert not diagnostics
    undone = undo_patch(changed)
    assert materialize_scene(base_scene, undone) == original
    redone = redo_patch(undone)
    assert materialize_scene(base_scene, redone) == routed


def test_patch_batch_failure_keeps_original_document(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", tmp_path / ".archcanvas")
    scene = next(iter(bundle.base_scenes.values()))
    node = next(item for item in scene.nodes if item.parent_scene_node_id)
    batch = PatchBatch(
        batch_id="batch:test.invalid",
        description="Invalid batch",
        patches=[
            VisualPatch(
                patch_id="patch:test.valid-first",
                operation="set-position",
                target_id=node.scene_node_id,
                value={"scene_id": scene.scene_id, "x": node.bounds.x + 10, "y": node.bounds.y},
            ),
            VisualPatch(
                patch_id="patch:test.invalid-second",
                operation="set-position",
                target_id="scenenode:missing",
                value={"scene_id": scene.scene_id, "x": 1, "y": 1},
            ),
        ],
    )
    with pytest.raises(ValueError, match="valid scene and target"):
        apply_patch_batch(
            bundle.document,
            batch,
            {item.scene_id: item for item in bundle.base_scenes.values()},
        )
    assert not bundle.document.visual_patches


def test_static_project_discovery_does_not_execute_source(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "model.py").write_text(
        "raise RuntimeError('must not execute')\n"
        "from torch import nn\n"
        "class Model(nn.Module):\n"
        "    def forward(self, x):\n"
        "        return x\n"
    )
    discovered = discover_project(project)
    assert discovered["source_execution"] is False
    assert discovered["entrypoints"][0]["entrypoint"] == "model:Model"
    assert discovered["entrypoints"][0]["path"] == "model.py"


def test_project_discovery_builds_model_component_hierarchy(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "components.py").write_text(
        "from torch import nn\n"
        "class EncoderLayer(nn.Module):\n"
        "    def forward(self, x): return x\n"
        "class Encoder(nn.Module):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self.layers = nn.ModuleList([EncoderLayer() for _ in range(2)])\n"
        "    def forward(self, x): return x\n"
    )
    (project / "model.py").write_text(
        "raise RuntimeError('must not execute')\n"
        "from torch import nn\n"
        "from .components import Encoder\n"
        "class Transformer(nn.Module):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self.encoder = Encoder()\n"
        "    def forward(self, x): return self.encoder(x)\n"
    )

    discovered = discover_project(project)
    by_id = {item["entrypoint"]: item for item in discovered["entrypoints"]}

    assert discovered["source_execution"] is False
    assert by_id["model:Transformer"]["depth"] == 0
    assert by_id["model:Transformer"]["top_level"] is True
    assert by_id["model:Transformer"]["category"] == "model"
    assert by_id["model:Transformer"]["contains"] == ["components:Encoder"]
    assert by_id["components:Encoder"]["parent_entrypoint"] == "model:Transformer"
    assert by_id["components:Encoder"]["depth"] == 1
    assert by_id["components:Encoder"]["top_level"] is False
    assert by_id["components:Encoder"]["category"] == "encoder"
    assert by_id["components:EncoderLayer"]["parent_entrypoint"] == "components:Encoder"
    assert by_id["components:EncoderLayer"]["depth"] == 2
    assert by_id["components:EncoderLayer"]["category"] == "layer"
    assert [item["entrypoint"] for item in discovered["entrypoints"] if item["depth"] == 0] == [
        "model:Transformer"
    ]
    assert by_id["model:Transformer"]["analysis_root"] == "."
    assert by_id["model:Transformer"]["analysis_entrypoint"] == "model:Transformer"


def test_project_discovery_scopes_fixture_model_profiles_and_browses_directories() -> None:
    root = ROOT / "fixtures" / "tier_a"
    discovered = discover_project(root)
    by_id = {item["entrypoint"]: item for item in discovered["entrypoints"]}
    assert by_id["autoformer.models.Autoformer:Model"]["analysis_root"] == "autoformer"
    assert by_id["autoformer.models.Autoformer:Model"]["analysis_entrypoint"] == "models.Autoformer:Model"
    assert "autoformer/config.json" in by_id["autoformer.models.Autoformer:Model"]["config_paths"]
    browser = browse_directories(root)
    assert browser["path"] == str(root.resolve())
    assert any(item["name"] == "autoformer" for item in browser["directories"])


def test_conda_environment_discovery_is_static_and_marks_active(tmp_path: Path) -> None:
    root = tmp_path / "miniconda3"
    environment = root / "envs" / "ArchCanvas"
    (root / "conda-meta").mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin" / "python").touch()
    (environment / "conda-meta").mkdir(parents=True)
    (environment / "bin").mkdir()
    (environment / "bin" / "python").touch()
    registry = tmp_path / ".conda" / "environments.txt"
    registry.parent.mkdir()
    registry.write_text(f"{environment}\n")

    discovered = discover_conda_environments(
        home=tmp_path,
        environ={
            "CONDA_PREFIX": str(environment),
            "CONDA_EXE": str(root / "bin" / "conda"),
        },
    )

    assert discovered["source_execution"] is False
    assert discovered["selected"] == str(environment)
    assert [item["name"] for item in discovered["environments"]] == [
        "ArchCanvas",
        "base",
    ]
    assert discovered["environments"][0]["active"] is True


def test_project_session_preserves_an_explicit_environment_and_allows_none(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / ".archcanvas"
    default_session = create_project_session(FIXTURE, workspace, generation=2)
    selected_session = create_project_session(
        FIXTURE,
        workspace,
        generation=3,
        environment={
            "path": "/opt/conda/envs/model",
            "python": "/opt/conda/envs/model/bin/python",
        },
    )

    assert default_session.environment_path is None
    assert default_session.python_executable is None
    assert selected_session.environment_path == "/opt/conda/envs/model"
    assert selected_session.python_executable == "/opt/conda/envs/model/bin/python"


def test_analysis_cancel_terminates_the_host_static_analysis_process(
    analysis_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    selected_python = "/opt/conda/envs/model/bin/python"
    bundle.project_session = bundle.project_session.model_copy(
        update={
            "environment_path": "/opt/conda/envs/model",
            "python_executable": selected_python,
        }
    )
    server = _server_without_socket(bundle)
    process = _BlockingAnalysisProcess()
    invocation: dict[str, object] = {}

    def popen(command, **options):  # type: ignore[no-untyped-def]
        invocation["command"] = command
        invocation["options"] = options
        return process

    monkeypatch.setattr("archcanvas_studio.server.subprocess.Popen", popen)
    monkeypatch.setattr(
        server,
        "_terminate_process_locked",
        lambda running: running.terminate(),
    )
    job = server.start_analysis(
        _analysis_request(bundle.project_session, "request:test-cancel")
    )
    assert process.started.wait(3)

    cancelling = server.cancel_job(job.job_id)
    finished = _wait_for_job(server, job.job_id)

    assert cancelling.state is JobState.CANCELLING
    assert finished.state is JobState.CANCELLED
    assert finished.finished_at is not None
    assert process.terminated is True
    assert invocation["command"][0] == sys.executable  # type: ignore[index]
    assert server.bundle is bundle


def test_static_analysis_uses_host_python_when_target_environment_is_incompatible(
    analysis_dir: Path,
    tmp_path: Path,
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    bundle.project_session = bundle.project_session.model_copy(
        update={
            "environment_path": "/opt/conda/envs/incompatible",
            "python_executable": "/opt/conda/envs/incompatible/bin/python",
        }
    )
    server = _server_without_socket(bundle)

    job = server.start_analysis(
        _analysis_request(bundle.project_session, "request:test-host-analysis-python")
    )
    finished = _wait_for_job(server, job.job_id)

    assert finished.state is JobState.SUCCEEDED
    assert finished.receipt is not None
    assert finished.receipt["details"]["analysis_python"] == sys.executable
    assert (
        finished.receipt["details"]["target_environment_python"]
        == "/opt/conda/envs/incompatible/bin/python"
    )
    assert finished.receipt["details"]["target_environment_usage"] == "runtime-only"


def test_project_switch_marks_late_analysis_stale_without_replacing_bundle(
    analysis_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    server = _server_without_socket(bundle)
    process = _BlockingAnalysisProcess()
    monkeypatch.setattr(
        "archcanvas_studio.server.subprocess.Popen",
        lambda *args, **kwargs: process,
    )
    monkeypatch.setattr(
        server,
        "_terminate_process_locked",
        lambda running: running.terminate(),
    )
    job = server.start_analysis(
        _analysis_request(bundle.project_session, "request:test-project-a")
    )
    assert process.started.wait(3)

    project_b = tmp_path / "project-b"
    project_b.mkdir()
    session_b = create_project_session(
        project_b,
        bundle.workspace,
        generation=server.next_project_generation(),
    )
    server.activate_project(session_b, {"entrypoints": [], "source_execution": False})
    finished = _wait_for_job(server, job.job_id)

    assert finished.state is JobState.STALE
    assert finished.finished_at is not None
    assert process.terminated is True
    assert server.bundle is bundle
    assert server.active_project_key == (session_b.project_id, session_b.generation)


def test_cancelled_before_analysis_thread_start_reaches_terminal_state(
    analysis_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    server = _server_without_socket(bundle)
    request = _analysis_request(bundle.project_session, "request:test-prestart-cancel")
    job = AnalysisJob(
        job_id="job:test-prestart-cancel",
        project_id=request.project_id,
        generation=request.project_generation,
        input_fingerprint="0" * 64,
        profile="static-analysis",
        state=JobState.QUEUED,
        progress=0,
    )
    server.jobs[job.job_id] = job
    server.job_cancellations[job.job_id] = threading.Event()
    server.job_cancellations[job.job_id].set()
    monkeypatch.setattr(
        "archcanvas_studio.server.subprocess.Popen",
        lambda *args, **kwargs: pytest.fail("cancelled analysis started a process"),
    )

    server._run_analysis(
        request,
        bundle.project_session,
        {},
        bundle.workspace,
        job.job_id,
    )

    assert server.jobs[job.job_id].state is JobState.CANCELLED
    assert server.jobs[job.job_id].finished_at is not None


def test_validation_job_publishes_only_after_background_completion(
    analysis_dir: Path,
    tmp_path: Path,
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    server = _server_without_socket(bundle)

    job = server.start_validation("publication")
    finished = _wait_for_job(server, job.job_id)

    assert finished.state is JobState.SUCCEEDED
    assert len(bundle.validation_runs) == 1
    validation = bundle.validation_runs[0]
    assert validation.input_fingerprint == job.input_fingerprint
    assert finished.receipt == {
        "status": validation.state.value,
        "validation_id": validation.validation_id,
    }
    assert (
        bundle.workspace
        / "validations"
        / f"{validation.validation_id.removeprefix('validation:')}.json"
    ).is_file()


def test_search_index_and_publication_validation_are_fingerprint_bound(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", tmp_path / ".archcanvas")
    subjects = build_search_index(bundle)
    assert any(item.kind == "tensor" for item in subjects)
    run = bundle.validate("publication")
    assert run.state.value == "succeeded"
    assert run.input_fingerprint
    assert all(item.status in {"passed", "failed", "skipped", "unsupported", "cancelled"} for item in run.gate_results)


def test_unknown_draft_node_becomes_blocked_zero_permission_proposal(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", tmp_path / ".archcanvas")
    before = _source_hashes()
    bundle.propose_draft_node(
        {
            "node": {
                "node_id": "draft:research-block",
                "semantic_name": "Research block",
                "framework": "pytorch",
                "node_type": "labs.ResearchBlock",
                "parameters": {"width": 32},
                "ports": [
                    {
                        "port_id": "draft:research-block.input",
                        "name": "input",
                        "direction": "input",
                        "role": "main",
                    },
                    {
                        "port_id": "draft:research-block.output",
                        "name": "output",
                        "direction": "output",
                        "role": "main",
                    },
                ],
            }
        }
    )
    assert bundle.draft.lowering_status == "blocked"
    assert bundle.draft.proofs[-1].status.value == "unproven"
    assert bundle.draft.writeback_summary.eligibility == "blocked"
    assert bundle.active_proposal is not None
    assert not any(bundle.active_proposal.permissions.values())
    assert _source_hashes() == before

    forged = bundle.draft.model_copy(
        update={
            "revision": bundle.draft.revision + 1,
            "proofs": [
                bundle.draft.proofs[-1].model_copy(
                    update={
                        "status": EditProofState.PROVEN,
                        "writeback_eligibility": "prepare",
                    }
                )
            ],
        }
    )
    forged = DraftGraphDocument.model_validate(forged.model_dump(mode="json"))
    with pytest.raises(ValueError, match="cannot grant proven"):
        bundle.save_draft(forged, bundle.draft.revision)


def test_deleting_draft_node_removes_its_intent_and_preserves_source(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    before = _source_hashes()
    bundle.propose_draft_node(
        {
            "node": {
                "node_id": "draft:temporary-block",
                "semantic_name": "Temporary block",
                "framework": "pytorch",
                "node_type": "custom.TemporaryBlock",
                "ports": [
                    {
                        "port_id": "draft:temporary-block.input",
                        "name": "input",
                        "direction": "input",
                        "role": "main",
                    },
                    {
                        "port_id": "draft:temporary-block.output",
                        "name": "output",
                        "direction": "output",
                        "role": "main",
                    },
                ],
            }
        }
    )
    revision = bundle.draft.revision

    bundle.delete_draft_node("draft:temporary-block")

    assert bundle.draft.revision == revision + 1
    assert not bundle.draft.nodes
    assert not bundle.draft.intents
    assert not bundle.draft.proofs
    assert bundle.draft.lowering_status == "not-planned"
    assert not bundle.draft.writeback_summary.blocking_intent_ids
    assert bundle.active_proposal is None
    assert _source_hashes() == before


def test_draft_edge_validates_ports_and_preserves_exact_ir_and_source(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    before_source = _source_hashes()
    before_architecture = bundle.architecture.model_dump_json()
    source = next(node for node in bundle.architecture.nodes if node.output_ports)
    target = next(node for node in bundle.architecture.nodes if node.input_ports)
    edge_payload = {
        "edge": {
            "edge_id": "draft:test-connection",
            "source_port_id": source.output_ports[0].port_id,
            "target_port_id": target.input_ports[0].port_id,
            "policy": "fanout",
        }
    }

    bundle.propose_draft_edge(edge_payload)

    assert bundle.draft.edges[-1].edge_id == "draft:test-connection"
    assert bundle.draft.intents[-1].kind == "connect-ports"
    assert bundle.draft.proofs[-1].status in {
        EditProofState.UNPROVEN,
        EditProofState.INVALID,
    }
    assert bundle.draft.writeback_summary.blocking_intent_ids == [
        bundle.draft.intents[-1].intent_id
    ]
    assert bundle.active_proposal is not None
    assert not any(bundle.active_proposal.permissions.values())
    assert bundle.architecture.model_dump_json() == before_architecture
    assert _source_hashes() == before_source

    revision = bundle.draft.revision
    bundle.delete_draft_edge("draft:test-connection")
    assert bundle.draft.revision == revision + 1
    assert not bundle.draft.edges
    assert not bundle.draft.intents
    assert not bundle.draft.proofs
    assert bundle.draft.lowering_status == "not-planned"
    assert _source_hashes() == before_source


def test_draft_edge_accepts_draft_ports_and_node_delete_cascades(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    source = next(node for node in bundle.architecture.nodes if node.output_ports)
    bundle.propose_draft_node(
        {
            "node": {
                "node_id": "draft:edge-target",
                "semantic_name": "Edge target",
                "framework": bundle.architecture.framework,
                "node_type": "custom.EdgeTarget",
                "ports": [
                    {
                        "port_id": "draft:edge-target.input",
                        "name": "input",
                        "direction": "input",
                        "role": "main",
                    },
                    {
                        "port_id": "draft:edge-target.output",
                        "name": "output",
                        "direction": "output",
                        "role": "main",
                    },
                ],
            }
        }
    )
    bundle.propose_draft_edge(
        {
            "edge": {
                "edge_id": "draft:edge-to-node",
                "source_port_id": source.output_ports[0].port_id,
                "target_port_id": "draft:edge-target.input",
                "policy": "replace-input",
            }
        }
    )

    assert bundle.draft.edges[-1].edge_id == "draft:edge-to-node"
    assert bundle.draft.proofs[-1].status is EditProofState.UNPROVEN
    assert bundle.draft.proofs[-1].reason_codes == ["UNSUPPORTED_STRUCTURAL_INTENT"]

    bundle.delete_draft_node("draft:edge-target")
    assert not bundle.draft.edges
    assert not bundle.draft.intents
    assert not bundle.draft.proofs
    assert not bundle.draft.writeback_summary.blocking_intent_ids


def test_draft_edge_rejects_unknown_and_reversed_ports(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    source = next(node for node in bundle.architecture.nodes if node.output_ports)
    target = next(node for node in bundle.architecture.nodes if node.input_ports)

    with pytest.raises(ValueError, match="unknown port"):
        bundle.propose_draft_edge(
            {
                "edge": {
                    "edge_id": "draft:unknown-port",
                    "source_port_id": "port:missing",
                    "target_port_id": target.input_ports[0].port_id,
                    "policy": "fanout",
                }
            }
        )
    with pytest.raises(ValueError, match="source must reference an output"):
        bundle.propose_draft_edge(
            {
                "edge": {
                    "edge_id": "draft:reversed",
                    "source_port_id": target.input_ports[0].port_id,
                    "target_port_id": source.output_ports[0].port_id,
                    "policy": "fanout",
                }
            }
        )


def test_canonical_delete_requires_impact_preview_and_never_mutates_source(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    before_source = _source_hashes()
    before_architecture = bundle.architecture.model_dump_json()
    node = next(
        item
        for item in bundle.architecture.nodes
        if item.input_ports and item.output_ports
    )
    impact = bundle.canonical_delete_impact(node.node_id)
    expected_edges = sorted(
        edge.edge_id
        for edge in bundle.architecture.edges
        if edge.producer_id == node.node_id or edge.consumer_id == node.node_id
    )

    assert impact["node_id"] == node.node_id
    assert sorted(
        [*impact["incoming_edge_ids"], *impact["outgoing_edge_ids"]]
    ) == expected_edges
    with pytest.raises(ValueError, match="preview is stale"):
        bundle.propose_canonical_delete(
            {"node_id": node.node_id, "input_fingerprint": "0" * 64}
        )

    bundle.propose_canonical_delete(
        {
            "node_id": node.node_id,
            "input_fingerprint": impact["input_fingerprint"],
        }
    )

    intent = bundle.draft.intents[-1]
    assert intent.kind == "delete-node"
    assert intent.expected_delta is not None
    assert intent.expected_delta.removed_nodes == [node.node_id]
    assert intent.expected_delta.removed_edges == expected_edges
    assert bundle.draft.proofs[-1].status is EditProofState.UNPROVEN
    assert bundle.active_proposal is not None
    assert not any(bundle.active_proposal.permissions.values())
    assert bundle.architecture.model_dump_json() == before_architecture
    assert _source_hashes() == before_source

    revision = bundle.draft.revision
    bundle.discard_canonical_delete(intent.intent_id)
    assert bundle.draft.revision == revision + 1
    assert not bundle.draft.intents
    assert not bundle.draft.proofs
    assert bundle.architecture.model_dump_json() == before_architecture
    assert _source_hashes() == before_source


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_camera_rejects_non_finite_values(
    analysis_dir: Path, tmp_path: Path, value: float
) -> None:
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", tmp_path / ".archcanvas")
    scene = next(iter(bundle.base_scenes.values()))
    patch = VisualPatch(
        patch_id="patch:test.non-finite",
        operation="set-camera",
        value={"scene_id": scene.scene_id, "x": value, "y": 0, "zoom": 1},
    )
    with pytest.raises(ValueError, match="camera x must be finite"):
        apply_patch(
            bundle.document,
            patch,
            {item.scene_id: item for item in bundle.base_scenes.values()},
        )


def test_source_excerpt_is_snapshot_bound(analysis_dir: Path, tmp_path: Path) -> None:
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", tmp_path / ".archcanvas")

    excerpt = bundle.source_excerpt("model.py", 36, 36, context=2)

    assert excerpt["start_line"] == 34
    assert excerpt["highlight_start_line"] == 36
    assert excerpt["highlight_end_line"] == 36
    assert excerpt["lines"][2] == {
        "number": 36,
        "text": "        enc_k = self.encoder_k_proj(src)",
    }
    with pytest.raises(ValueError, match="frozen snapshot"):
        bundle.source_excerpt("../model.py", 1, 1)


def test_source_workspace_stages_persists_and_discards_without_source_write(
    analysis_dir: Path, tmp_path: Path
) -> None:
    workspace = tmp_path / ".archcanvas"
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", workspace)
    source_file = bundle.snapshot.source_files[0]
    source_path = Path(bundle.snapshot.project_root) / source_file.path
    before = source_path.read_bytes()

    opened = bundle.open_source_buffer(source_file.path)
    assert opened["state"] == "clean"
    staged = f"{opened['staged_content']}\n# staged source workspace\n"
    saved = bundle.save_source_buffer(
        source_file.path,
        staged,
        source_file.sha256,
        int(opened["revision"]),
    )

    assert saved["state"] == "modified"
    assert "# staged source workspace" in saved["diff"]
    assert source_path.read_bytes() == before
    reopened = prepare_studio_bundle(analysis_dir / "architecture.json", workspace)
    assert reopened.source_buffer(source_file.path)["staged_content"] == staged
    reopened.discard_source_buffer(
        source_file.path, reopened.source_workspace.revision
    )
    assert not reopened.source_workspace.buffers
    assert source_path.read_bytes() == before


def test_nested_source_workspace_state_keeps_session_nonce(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    server = _server_without_socket(bundle)

    state = _handler_without_request(server)._studio_state()

    assert state["session_nonce"] == "test-nonce"
    assert state["jobs"] == []


def test_source_workspace_detects_stale_working_file(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    source_file = bundle.snapshot.source_files[0]
    source_path = Path(bundle.snapshot.project_root) / source_file.path
    before = source_path.read_bytes()
    opened = bundle.open_source_buffer(source_file.path)
    bundle.save_source_buffer(
        source_file.path,
        f"{opened['staged_content']}\n# candidate\n",
        source_file.sha256,
        int(opened["revision"]),
    )
    try:
        source_path.write_bytes(before + b"\n# external edit\n")
        summary = bundle.source_workspace_summary()
        assert summary["state"] == "stale"
        assert summary["files"][0]["state"] == "stale"
        with pytest.raises(ValueError, match="revision changed"):
            bundle.prepare_source_workspace()
    finally:
        source_path.write_bytes(before)


def test_source_workspace_validates_and_commits_only_after_review_ready(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json", tmp_path / ".archcanvas"
    )
    source_file = bundle.snapshot.source_files[0]
    source_path = Path(bundle.snapshot.project_root) / source_file.path
    before = source_path.read_bytes()
    opened = bundle.open_source_buffer(source_file.path)
    staged = f"{opened['staged_content']}\n# reviewed freeform change\n"
    bundle.save_source_buffer(
        source_file.path,
        staged,
        source_file.sha256,
        int(opened["revision"]),
    )

    bundle.prepare_source_workspace()

    assert bundle.active_transaction is not None
    assert bundle.active_transaction.request.operation == "edit_source_buffers"
    assert bundle.active_transaction.state is TransactionState.REVIEW_READY
    assert bundle.active_transaction.observed_delta == bundle.active_transaction.expected_delta
    assert not bundle.active_transaction.expected_delta.added_nodes
    assert not bundle.active_transaction.expected_delta.removed_nodes
    assert not bundle.active_transaction.expected_delta.added_edges
    assert not bundle.active_transaction.expected_delta.removed_edges
    assert bundle.active_transaction.expected_delta.fact_changes
    assert source_path.read_bytes() == before

    bundle.commit_parameter()

    assert bundle.active_transaction.state is TransactionState.COMMITTED
    assert source_path.read_text(encoding="utf-8") == staged
    assert not bundle.source_workspace.buffers


def test_reanalysis_archives_stale_studio_bindings(
    analysis_dir: Path, tmp_path: Path
) -> None:
    workspace = tmp_path / ".archcanvas"
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", workspace)

    document_payload = json.loads(bundle.document_path.read_text(encoding="utf-8"))
    document_payload["source_digest"] = "0" * 64
    bundle.document_path.write_text(json.dumps(document_payload), encoding="utf-8")
    draft_payload = json.loads(bundle.draft_path.read_text(encoding="utf-8"))
    draft_payload["base_source_digest"] = "0" * 64
    bundle.draft_path.write_text(json.dumps(draft_payload), encoding="utf-8")
    source_workspace_payload = json.loads(
        bundle.source_workspace_path.read_text(encoding="utf-8")
    )
    source_workspace_payload["base_revision"] = f"content:{'0' * 64}"
    bundle.source_workspace_path.write_text(
        json.dumps(source_workspace_payload), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="source digest is stale"):
        prepare_studio_bundle(analysis_dir / "architecture.json", workspace)

    refreshed = prepare_studio_bundle(
        analysis_dir / "architecture.json",
        workspace,
        replace_stale_bindings=True,
    )

    assert refreshed.document.source_digest == source_binding_digest(refreshed.snapshot)
    assert refreshed.draft.base_source_digest == refreshed.document.source_digest
    assert refreshed.source_workspace.base_revision == refreshed.snapshot.revision
    assert list(bundle.document_path.parent.glob("*.stale-*.json"))
    assert list(bundle.draft_path.parent.glob("*.stale-*.json"))
    assert list(bundle.source_workspace_path.parent.glob("*.stale-*.json"))


def test_geometry_rejects_non_finite_values(analysis_dir: Path, tmp_path: Path) -> None:
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", tmp_path / ".archcanvas")
    scene = next(iter(bundle.base_scenes.values()))
    node = next(item for item in scene.nodes if item.parent_scene_node_id)
    patch = VisualPatch(
        patch_id="patch:test.non-finite-position",
        operation="set-position",
        target_id=node.scene_node_id,
        value={"scene_id": scene.scene_id, "x": 0, "y": float("inf")},
    )
    with pytest.raises(ValueError, match="y must be finite"):
        apply_patch(
            bundle.document,
            patch,
            {item.scene_id: item for item in bundle.base_scenes.values()},
        )


def test_studio_server_persists_patch_undo_redo_and_exports_svg(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", tmp_path / ".archcanvas")
    try:
        server = create_studio_server(bundle, "127.0.0.1", 0)
    except PermissionError:
        pytest.skip("local sockets are disabled by the test sandbox")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        state = json.loads(urlopen(f"{base_url}/api/state").read())
        assert state["document"]["source_digest"] == bundle.document.source_digest
        layout_request = Request(
            f"{base_url}/api/layout-mode",
            data=json.dumps({"layout_mode": "hierarchical"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        state = json.loads(urlopen(layout_request).read())
        assert state["view_state"]["layout_mode"] == "hierarchical"
        assert next(iter(state["scenes"].values()))["layout_family"] == "hierarchical"
        layout_noop_request = Request(
            f"{base_url}/api/layout",
            data=json.dumps({"batch_id": "batch:test.layout-noop"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        unchanged = json.loads(urlopen(layout_noop_request).read())
        assert unchanged["view_state"]["layout_mode"] == "hierarchical"
        assert not unchanged["document"]["visual_patches"]
        patch, _, _ = _move_patch(bundle, suffix="server")
        request = Request(
            f"{base_url}/api/patch",
            data=patch.model_dump_json().encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        changed = json.loads(urlopen(request).read())
        assert len(changed["document"]["visual_patches"]) == 1

        undo = Request(f"{base_url}/api/undo", data=b"{}", method="POST")
        undone = json.loads(urlopen(undo).read())
        assert not undone["document"]["visual_patches"]
        assert len(undone["document"]["redo_patches"]) == 1

        redo = Request(f"{base_url}/api/redo", data=b"{}", method="POST")
        redone = json.loads(urlopen(redo).read())
        assert len(redone["document"]["visual_patches"]) == 1
        svg = urlopen(f"{base_url}/api/export").read().decode()
        assert svg.startswith('<?xml version="1.0"')
        assert next(iter(bundle.base_scenes.values())).scene_id in svg
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_cli_studio_prepares_one_receipt_and_built_frontend(
    analysis_dir: Path, tmp_path: Path, capsys
) -> None:
    workspace = tmp_path / ".archcanvas"
    exit_code = main(
        [
            "studio",
            str(analysis_dir / "architecture.json"),
            "--workspace",
            str(workspace),
            "--json",
        ]
    )
    receipt = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert receipt["status"] == "ok"
    assert receipt["details"]["source_writes"] is False
    assert next(
        gate for gate in receipt["gates"] if gate["gate"] == "F-visual-source-invariance"
    )["status"] == "passed"
    index = (workspace / "studio" / "index.html").read_text()
    assert "archcanvas-studio-data" in index
    assert "https://" not in index
    assert (workspace / "documents").is_dir()


def test_studio_server_prepares_review_ready_parameter_transaction(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    analysis = tmp_path / "analysis"
    bundle = analyze_project(
        project,
        "model:Transformer",
        "inference",
        "eval",
        (project / "config.json").read_bytes(),
        project / "config.json",
    )
    analysis.mkdir()
    (analysis / "architecture.json").write_text(bundle.architecture.model_dump_json())
    (analysis / "source-snapshot.json").write_text(bundle.snapshot.model_dump_json())
    (analysis / "evidence-ledger.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in bundle.evidence])
    )
    studio = prepare_studio_bundle(analysis / "architecture.json", tmp_path / ".archcanvas")
    before = (project / "config.json").read_bytes()
    try:
        server = create_studio_server(studio, "127.0.0.1", 0)
    except PermissionError:
        pytest.skip("local sockets are disabled by the test sandbox")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        request = Request(
            f"{base_url}/api/transaction/prepare",
            data=json.dumps(
                {
                    "patch_id": "patch:studio-parameter",
                    "target_node_id": "node:generator",
                    "parameter_name": "out_features",
                    "new_value": 16000,
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        state = json.loads(urlopen(request).read())
        assert state["capabilities"]["source_editing"] is True
        assert state["transaction"]["state"] == "review-ready"
        assert state["transaction"]["expected_delta"] == state["transaction"]["observed_delta"]
        assert "vocab_size" in state["transaction"]["source_diff"]
        assert (project / "config.json").read_bytes() == before

        discard = Request(
            f"{base_url}/api/transaction/discard", data=b"{}", method="POST"
        )
        discarded = json.loads(urlopen(discard).read())
        assert discarded["transaction"]["state"] == "discarded"
        assert (project / "config.json").read_bytes() == before
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_studio_server_prepares_structural_transaction_and_connection_proposal(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    analysis = tmp_path / "analysis"
    analyzed = analyze_project(
        project,
        "model:Transformer",
        "inference",
        "eval",
        (project / "config.json").read_bytes(),
        project / "config.json",
    )
    analysis.mkdir()
    (analysis / "architecture.json").write_text(analyzed.architecture.model_dump_json())
    (analysis / "source-snapshot.json").write_text(analyzed.snapshot.model_dump_json())
    (analysis / "evidence-ledger.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in analyzed.evidence])
    )
    studio = prepare_studio_bundle(analysis / "architecture.json", tmp_path / ".archcanvas")
    before = (project / "model.py").read_bytes()
    try:
        server = create_studio_server(studio, "127.0.0.1", 0)
    except PermissionError:
        pytest.skip("local sockets are disabled by the test sandbox")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        request = Request(
            f"{base_url}/api/transaction/prepare-structural",
            data=json.dumps(
                {
                    "patch_id": "patch:studio-activation",
                    "operation": "replace_activation",
                    "target_node_id": "node:activation",
                    "parameters": {"replacement": "ReLU"},
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        state = json.loads(urlopen(request).read())
        assert state["transaction"]["state"] == "review-ready"
        assert state["transaction"]["request"]["operation"] == "replace_activation"
        assert (project / "model.py").read_bytes() == before

        edge = analyzed.architecture.edges[0]
        request = Request(
            f"{base_url}/api/proposal/connection",
            data=json.dumps(
                {
                    "proposal_id": "proposal:studio-connection",
                    "source_node_id": edge.producer_id,
                    "source_port_id": edge.producer_port,
                    "target_node_id": edge.consumer_id,
                    "target_port_id": edge.consumer_port,
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        state = json.loads(urlopen(request).read())
        assert state["proposal"]["status"] == "handoff-required"
        assert not any(state["proposal"]["permissions"].values())
        assert (project / "model.py").read_bytes() == before
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
