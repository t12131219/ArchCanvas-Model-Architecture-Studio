from __future__ import annotations

import hashlib
import json
import shutil
import threading
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

import pytest

from archcanvas_core.builtin_registry import BuiltinModuleRegistry
from archcanvas_core.models import (
    DefinitionRef,
    DraftEdge,
    DraftGraphDocument,
    DraftNode,
    DraftPort,
)
from archcanvas_python import analyze_project
from archcanvas_studio.bundle import draft_document_digest, prepare_studio_bundle
from archcanvas_studio.generated_projects import (
    GENERATOR_VERSION,
    GeneratedProjectManager,
    MaterializeGeneratedProjectRequest,
    PrepareGeneratedProjectRequest,
)
from archcanvas_studio.server import create_studio_server

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "tier_a" / "transformer"


@pytest.fixture
def analysis_dir(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    analyzed = analyze_project(
        project,
        "model:Transformer",
        "inference",
        "eval",
        (project / "config.json").read_bytes(),
        project / "config.json",
    )
    target = tmp_path / "analysis"
    target.mkdir()
    (target / "architecture.json").write_text(analyzed.architecture.model_dump_json())
    (target / "source-snapshot.json").write_text(analyzed.snapshot.model_dump_json())
    (target / "evidence-ledger.json").write_text(
        json.dumps([record.model_dump(mode="json") for record in analyzed.evidence])
    )
    return target


def _node(
    registry: BuiltinModuleRegistry,
    definition_id: str,
    node_id: str,
    parameters: dict[str, object],
) -> DraftNode:
    definition = next(
        item for item in registry.bundle.definitions if item.definition_id == definition_id
    )
    return DraftNode(
        node_id=node_id,
        semantic_name=node_id.rsplit(".", 1)[-1],
        framework="pytorch",
        node_type=definition.definition_id,
        definition_ref=DefinitionRef(
            definition_id=definition.definition_id,
            version=definition.version,
            digest=definition.digest,
        ),
        parameters=parameters,
        ports=[
            DraftPort(
                port_id=f"{node_id}.{port.port_id}",
                name=port.port_id,
                direction=port.direction,
                role=port.port_id,
                definition_port_id=port.port_id,
                required=port.required,
                min_connections=port.min_connections,
                max_connections=port.max_connections,
                ordering=port.ordering,
                accepted_relations=port.accepted_relations,
                tensor_ranks=port.tensor_ranks,
                tensor_layouts=port.tensor_layouts,
            )
            for port in definition.ports
        ],
    )


def _draft(registry: BuiltinModuleRegistry) -> DraftGraphDocument:
    input_node = _node(
        registry,
        "archcanvas.input.tensor",
        "draft:node.input",
        {"shape": ["B", 3, 224, 224]},
    )
    conv = _node(
        registry,
        "pytorch.nn.conv2d",
        "draft:node.conv",
        {
            "in_channels": 3,
            "out_channels": 16,
            "kernel_size": 3,
            "stride": 1,
            "padding": 0,
            "dilation": 1,
            "groups": 1,
            "bias": True,
        },
    )
    relu = _node(
        registry,
        "pytorch.nn.relu",
        "draft:node.relu",
        {"inplace": False},
    )
    return DraftGraphDocument(
        draft_id="draft:generated-project-test",
        base_architecture_id="architecture:generated-project-test",
        base_source_digest="0" * 64,
        base_registry_digest=registry.bundle.bundle_digest,
        revision=5,
        nodes=[input_node, conv, relu],
        edges=[
            DraftEdge(
                edge_id="draft:edge.input-conv",
                source_port_id=f"{input_node.node_id}.output",
                target_port_id=f"{conv.node_id}.input",
                policy="replace-input",
            ),
            DraftEdge(
                edge_id="draft:edge.conv-relu",
                source_port_id=f"{conv.node_id}.output",
                target_port_id=f"{relu.node_id}.input",
                policy="replace-input",
            ),
        ],
    )


def _prepare_request(
    draft: DraftGraphDocument,
    registry: BuiltinModuleRegistry,
) -> PrepareGeneratedProjectRequest:
    return PrepareGeneratedProjectRequest(
        graph_digest=draft_document_digest(draft),
        registry_digest=registry.bundle.bundle_digest,
        generator_version=GENERATOR_VERSION,
        target_framework="pytorch",
        input_spec={"shape": ["B", 3, 224, 224], "dtype": "float32", "layout": "NCHW"},
    )


def _file_bytes(record) -> dict[str, bytes]:  # type: ignore[no-untyped-def]
    root = Path(record.candidate_directory)
    return {item.path: (root / item.path).read_bytes() for item in record.files}


def test_prepare_is_idempotent_and_byte_deterministic(tmp_path: Path) -> None:
    registry = BuiltinModuleRegistry()
    draft = _draft(registry)
    manager = GeneratedProjectManager(tmp_path / "workspace", registry)

    first = manager.prepare(draft, _prepare_request(draft, registry))
    first_bytes = _file_bytes(first)
    second = manager.prepare(draft, _prepare_request(draft, registry))

    assert second == first
    assert _file_bytes(second) == first_bytes
    assert [item.path for item in first.files] == [
        "archcanvas-generation.json",
        "archcanvas-project.json",
        "model.py",
        "pyproject.toml",
    ]
    compile(first_bytes["model.py"].decode(), "model.py", "exec")


def test_validate_reanalyzes_and_emits_exact_conformance(tmp_path: Path) -> None:
    registry = BuiltinModuleRegistry()
    draft = _draft(registry)
    manager = GeneratedProjectManager(tmp_path / "workspace", registry)
    prepared = manager.prepare(draft, _prepare_request(draft, registry))

    validated = manager.validate(
        prepared.project_id,
        draft,
        graph_digest=prepared.graph_digest,
        registry_digest=prepared.registry_digest,
        generator_version=prepared.generator_version,
    )

    assert validated.state == "review-ready"
    assert validated.receipt.status == "review-ready"
    assert validated.conformance_report is not None
    assert validated.conformance_report.semantic_isomorphism == "exact"
    assert validated.conformance_report.expected_delta_digest == (
        validated.conformance_report.observed_delta_digest
    )
    assert validated.conformance_report.source_writes == []
    assert manager.conformance_reports() == [validated.conformance_report]


def test_stale_and_unsupported_prepare_perform_no_candidate_write(tmp_path: Path) -> None:
    registry = BuiltinModuleRegistry()
    draft = _draft(registry)
    manager = GeneratedProjectManager(tmp_path / "workspace", registry)
    request = _prepare_request(draft, registry)

    with pytest.raises(ValueError, match="graph digest is stale"):
        manager.prepare(draft, request.model_copy(update={"graph_digest": "1" * 64}))
    assert not list(manager.candidates_dir.iterdir())

    linear = _node(
        registry,
        "pytorch.nn.linear",
        "draft:node.linear",
        {"in_features": 3, "out_features": 16, "bias": True},
    )
    unsupported = draft.model_copy(
        update={
            "nodes": [draft.nodes[0], linear, draft.nodes[2]],
            "edges": [
                DraftEdge(
                    edge_id="draft:edge.input-linear",
                    source_port_id="draft:node.input.output",
                    target_port_id="draft:node.linear.input",
                    policy="replace-input",
                ),
                DraftEdge(
                    edge_id="draft:edge.linear-relu",
                    source_port_id="draft:node.linear.output",
                    target_port_id="draft:node.relu.input",
                    policy="replace-input",
                ),
            ],
        }
    )
    with pytest.raises(ValueError, match="no implemented fixed generator rule"):
        manager.prepare(unsupported, _prepare_request(unsupported, registry))
    assert not list(manager.candidates_dir.iterdir())


def test_materialize_inventory_matches_files_and_conflict_writes_nothing(
    tmp_path: Path,
) -> None:
    registry = BuiltinModuleRegistry()
    draft = _draft(registry)
    manager = GeneratedProjectManager(tmp_path / "workspace", registry)
    prepared = manager.prepare(draft, _prepare_request(draft, registry))
    validated = manager.validate(
        prepared.project_id,
        draft,
        graph_digest=prepared.graph_digest,
        registry_digest=prepared.registry_digest,
        generator_version=prepared.generator_version,
    )
    conflict = tmp_path / "conflict"
    conflict.mkdir()
    marker = conflict / "marker.txt"
    marker.write_text("preserve", encoding="utf-8")
    conflict_request = MaterializeGeneratedProjectRequest(
        target_directory=str(conflict),
        graph_digest=validated.graph_digest,
        registry_digest=validated.registry_digest,
        generator_version=validated.generator_version,
        inventory_digest=validated.receipt.inventory_digest,
    )
    with pytest.raises(ValueError, match="must not already exist"):
        manager.materialize(validated.project_id, draft, conflict_request)
    assert marker.read_text(encoding="utf-8") == "preserve"

    target = tmp_path / "generated-model"
    result = manager.materialize(
        validated.project_id,
        draft,
        conflict_request.model_copy(update={"target_directory": str(target)}),
    )

    receipt = result.record.materialization_receipt
    assert result.record.state == "opened-and-reanalyzed"
    assert receipt is not None
    assert receipt.status == "opened-and-reanalyzed"
    actual = {
        path.relative_to(target).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in target.rglob("*")
        if path.is_file()
    }
    assert actual == {item.path: item.sha256 for item in receipt.files}
    assert result.artifact_path.is_file()


def test_generated_project_http_lifecycle_replaces_active_source_project(
    analysis_dir: Path,
    tmp_path: Path,
) -> None:
    registry = BuiltinModuleRegistry()
    draft = _draft(registry)
    bundle = prepare_studio_bundle(
        analysis_dir / "architecture.json",
        tmp_path / "studio-workspace",
        write_static=False,
    )
    bundle.draft = draft
    try:
        server = create_studio_server(bundle, "127.0.0.1", 0)
    except PermissionError:
        pytest.skip("local sockets are disabled by the test sandbox")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"

    def post(path: str, payload: dict[str, object]) -> dict[str, object]:
        request = Request(
            f"{base_url}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return json.loads(urlopen(request).read())

    try:
        request = _prepare_request(draft, registry)
        prepared_state = post(
            "/api/generated-projects/prepare",
            request.model_dump(mode="json"),
        )
        prepared = prepared_state["generated_projects"]["active"]  # type: ignore[index]
        assert prepared["state"] == "generated-source-draft"  # type: ignore[index]
        project_id = str(prepared["project_id"])  # type: ignore[index]
        validated_state = post(
            f"/api/generated-projects/{quote(project_id, safe='')}/validate",
            {
                "graph_digest": prepared["graph_digest"],  # type: ignore[index]
                "registry_digest": prepared["registry_digest"],  # type: ignore[index]
                "generator_version": prepared["generator_version"],  # type: ignore[index]
            },
        )
        validated = validated_state["generated_projects"]["active"]  # type: ignore[index]
        assert validated["state"] == "review-ready"  # type: ignore[index]
        assert any(
            report["path"] == "draft-source"  # type: ignore[index]
            for report in validated_state["round_trip_reports"]  # type: ignore[index]
        )
        target = tmp_path / "http-generated-model"
        opened = post(
            f"/api/generated-projects/{quote(project_id, safe='')}/materialize",
            {
                "target_directory": str(target),
                "graph_digest": validated["graph_digest"],  # type: ignore[index]
                "registry_digest": validated["registry_digest"],  # type: ignore[index]
                "generator_version": validated["generator_version"],  # type: ignore[index]
                "inventory_digest": validated["receipt"]["inventory_digest"],  # type: ignore[index]
            },
        )
        assert opened["project"]["root"] == str(target)  # type: ignore[index]
        assert opened["architecture"]["entrypoint"] == "model:GeneratedModel"  # type: ignore[index]
        assert opened["generated_projects"]["active"]["state"] == "opened-and-reanalyzed"  # type: ignore[index]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
