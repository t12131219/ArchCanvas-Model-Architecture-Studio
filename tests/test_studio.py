from __future__ import annotations

import hashlib
import json
import shutil
import threading
from collections import defaultdict
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from archcanvas_core.models import DraftGraphDocument, EditProofState, PatchBatch, VisualPatch
from archcanvas_engine.cli import main
from archcanvas_python import analyze_project
from archcanvas_studio import (
    apply_patch,
    apply_patch_batch,
    derive_view_state,
    load_canvas_document,
    materialize_scene,
    persist_canvas_document,
    prepare_studio_bundle,
    redo_patch,
    undo_patch,
)
from archcanvas_studio.operations import build_search_index
from archcanvas_studio.project import discover_project
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
