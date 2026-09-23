from __future__ import annotations

import hashlib
import json
import shutil
import threading
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from archcanvas_core.models import VisualPatch
from archcanvas_engine.cli import main
from archcanvas_python import analyze_project
from archcanvas_studio import (
    apply_patch,
    derive_view_state,
    load_canvas_document,
    materialize_scene,
    persist_canvas_document,
    prepare_studio_bundle,
    redo_patch,
    undo_patch,
)
from archcanvas_studio.server import create_studio_server

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "tier_a" / "transformer"


@pytest.fixture
def analysis_dir(tmp_path: Path) -> Path:
    bundle = analyze_project(
        FIXTURE,
        "model:Transformer",
        "inference",
        "eval",
        (FIXTURE / "config.json").read_bytes(),
        FIXTURE / "config.json",
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


def _move_patch(bundle, *, suffix: str = "move") -> tuple[VisualPatch, str, float]:
    scene = bundle.base_scenes["L1"]
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
    moved = materialize_scene(bundle.base_scenes["L1"], changed)
    assert next(node for node in moved.nodes if node.scene_node_id == node_id).bounds.x == original_x + 12

    undone = undo_patch(changed)
    assert materialize_scene(bundle.base_scenes["L1"], undone) == bundle.base_scenes["L1"]
    redone = redo_patch(undone)
    assert redone == changed
    persist_canvas_document(bundle.document_path, redone)

    reopened = prepare_studio_bundle(analysis_dir / "architecture.json", workspace)
    reopened_scene = reopened.materialized_scenes()["L1"]
    assert next(node for node in reopened_scene.nodes if node.scene_node_id == node_id).bounds.x == original_x + 12
    assert reopened.document.source_digest == digest
    assert load_canvas_document(reopened.document_path) == reopened.document
    assert _source_hashes() == before


def test_visual_patch_rejects_unknown_target(analysis_dir: Path, tmp_path: Path) -> None:
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", tmp_path / ".archcanvas")
    scene = bundle.base_scenes["L1"]
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


def test_theme_and_camera_persist_across_reopen(
    analysis_dir: Path, tmp_path: Path
) -> None:
    workspace = tmp_path / ".archcanvas"
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", workspace)
    scene = bundle.base_scenes["L1"]
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


def test_repeated_camera_updates_are_compacted(
    analysis_dir: Path, tmp_path: Path
) -> None:
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", tmp_path / ".archcanvas")
    scene = bundle.base_scenes["L1"]
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


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_camera_rejects_non_finite_values(
    analysis_dir: Path, tmp_path: Path, value: float
) -> None:
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", tmp_path / ".archcanvas")
    scene = bundle.base_scenes["L1"]
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


def test_geometry_rejects_non_finite_values(analysis_dir: Path, tmp_path: Path) -> None:
    bundle = prepare_studio_bundle(analysis_dir / "architecture.json", tmp_path / ".archcanvas")
    scene = bundle.base_scenes["L1"]
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
        svg = urlopen(f"{base_url}/api/export?level=L1").read().decode()
        assert svg.startswith('<?xml version="1.0"')
        assert bundle.base_scenes["L1"].scene_id in svg
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
