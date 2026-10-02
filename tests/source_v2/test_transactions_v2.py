from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from archcanvas_core.builtin_registry import BuiltinModuleRegistry
from archcanvas_core.models import (
    EditProofState,
    SemanticParameterPatch,
    SemanticStructuralPatch,
    TransactionState,
)
from archcanvas_python import analyze_project_v2
from archcanvas_studio import prepare_studio_bundle
from archcanvas_studio.bundle import draft_document_digest
from archcanvas_transactions import (
    commit_transaction,
    prepare_transaction,
    resolve_parameter_edit_context,
    verify_transaction,
)
from archcanvas_transactions import service as transaction_service

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "frontend_v2" / "conv_relu"


def _write_json(path: Path, value: object) -> None:
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")
    elif isinstance(value, list):
        payload = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in value
        ]
    else:
        payload = value
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _setup(tmp_path: Path) -> tuple[Path, Path, Path, object]:
    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    analysis = tmp_path / "analysis"
    frontend = analyze_project_v2(
        project,
        "app.model:Model",
        "inference",
        "eval",
        analysis / ".frontend-v2",
    )
    analysis.mkdir(exist_ok=True)
    artifact = analysis / "architecture.json"
    _write_json(artifact, frontend.compatibility.architecture)
    _write_json(analysis / "source-snapshot.json", frontend.compatibility.snapshot)
    _write_json(analysis / "evidence-ledger.json", frontend.compatibility.evidence)
    _write_json(analysis / "project-manifest-v2.json", frontend.manifest)
    _write_json(analysis / "source-corpus-v2.json", frontend.corpus)
    _write_json(
        analysis / "analysis-environment-manifest-v1.json",
        frontend.environment_manifest,
    )
    _write_json(analysis / "analysis-input-v2.json", frontend.analysis_input)
    _write_json(analysis / "architecture-v2.json", frontend.exact_ir)
    return project, artifact, tmp_path / "workspace", frontend


def _write_frontend_bundle(analysis: Path, frontend: object) -> None:
    _write_json(analysis / "architecture.json", frontend.compatibility.architecture)
    _write_json(analysis / "source-snapshot.json", frontend.compatibility.snapshot)
    _write_json(analysis / "evidence-ledger.json", frontend.compatibility.evidence)
    _write_json(analysis / "project-manifest-v2.json", frontend.manifest)
    _write_json(analysis / "source-corpus-v2.json", frontend.corpus)
    _write_json(
        analysis / "analysis-environment-manifest-v1.json",
        frontend.environment_manifest,
    )
    _write_json(analysis / "analysis-input-v2.json", frontend.analysis_input)
    _write_json(analysis / "architecture-v2.json", frontend.exact_ir)


def _request(artifact: Path, frontend: object) -> SemanticParameterPatch:
    node = next(
        item
        for item in frontend.compatibility.architecture.nodes
        if item.attributes.get("definition_id") == "pytorch.nn.conv2d"
    )
    return SemanticParameterPatch(
        patch_id="patch:v2-conv-out-channels",
        artifact_path=str(artifact),
        target_node_id=node.node_id,
        parameter_name="out_channels",
        new_value=24,
    )


def _registered_insert_request(
    artifact: Path, frontend: object
) -> SemanticStructuralPatch:
    target = next(
        item
        for item in frontend.compatibility.architecture.nodes
        if item.attributes.get("definition_id") == "pytorch.nn.conv2d"
    )
    definition = BuiltinModuleRegistry().resolve_qualified_name("torch.nn.GELU")
    assert definition is not None
    return SemanticStructuralPatch(
        patch_id="patch:v2-insert-registered-gelu",
        operation="insert_registered_module",
        artifact_path=str(artifact),
        target_node_id=target.node_id,
        parameters={
            "module_name": "after_conv",
            "definition_ref": definition.ref.model_dump(mode="json"),
            "constructor_parameters": {"approximate": "none"},
            "correlation_id": "correlation:draft.after-conv",
        },
    )


def test_shared_instance_parameter_scope_includes_every_call_site(tmp_path: Path) -> None:
    project = tmp_path / "shared-project"
    shutil.copytree(ROOT / "tests" / "fixtures" / "frontend_v2" / "shared_module", project)
    analysis = tmp_path / "shared-analysis"
    frontend = analyze_project_v2(
        project,
        "model:Model",
        "inference",
        "eval",
        analysis / ".frontend-v2",
    )
    analysis.mkdir(exist_ok=True)
    _write_frontend_bundle(analysis, frontend)
    calls = [
        node
        for node in frontend.compatibility.architecture.nodes
        if node.attributes.get("v2_instance_id") == "instance:model.projection"
    ]
    assert len(calls) == 2

    context = resolve_parameter_edit_context(
        analysis / "architecture.json", calls[0].node_id, "out_features"
    )

    assert context.default_scope is not None
    assert context.default_scope.value == "module-instance"
    assert context.affected_canonical_ids == sorted(node.node_id for node in calls)


def test_v2_parameter_transaction_preserves_exact_anchor_and_commits(tmp_path: Path) -> None:
    project, artifact, workspace, frontend = _setup(tmp_path)
    first_blob = frontend.corpus.files[0]
    assert frontend.corpus.source_corpus_digest != first_blob.sha256

    request = _request(artifact, frontend)
    transaction, prepared_receipt = prepare_transaction(request, workspace)

    expected_anchor = next(
        argument.anchor
        for instance in frontend.exact_ir.instances
        if instance.instance_path == "model.block.conv"
        for argument in instance.constructor_arguments
        if argument.parameter_name == "out_channels"
    )
    assert prepared_receipt.source_writes is False
    assert transaction.source_anchor == expected_anchor
    assert transaction.base_source_corpus_digest == frontend.corpus.source_corpus_digest
    assert transaction.base_analysis_input_digest == frontend.analysis_input.analysis_input_digest
    assert transaction.base_registry_digest == frontend.analysis_input.registry_digest
    assert transaction.base_exact_ir_digest == frontend.exact_ir.exact_ir_digest
    assert transaction.parameter_edit_context is not None
    assert transaction.parameter_edit_context.value_origin.kind.value == "constructor-literal"
    assert transaction.parameter_edit_context.default_scope.value == "module-instance"
    assert transaction.parameter_edit_context.value_origin.source_anchor_ids
    assert len(transaction.base_source_blobs) == len(frontend.corpus.files)
    assert transaction.file_changes[0].path == "src/app/blocks.py"
    assert transaction.expected_delta.changed_nodes == [request.target_node_id]
    assert transaction.expected_delta.changed_edges == []
    assert transaction.expected_delta.changed_tensors == []
    assert {
        change.subject_id
        for change in transaction.expected_delta.fact_changes
        if change.kind != "evidence"
    } == {request.target_node_id}
    assert "nn.Conv2d(3, 24, 3)" in (
        Path(transaction.temporary_project_root) / "src/app/blocks.py"
    ).read_text()
    assert "nn.Conv2d(3, 16, 3)" in (project / "src/app/blocks.py").read_text()

    transaction_path = workspace / "transactions" / transaction.transaction_id
    verified, _ = verify_transaction(transaction_path)
    assert verified.state is TransactionState.REVIEW_READY
    assert verified.result_source_corpus_digest is not None
    assert verified.result_source_corpus_digest != verified.base_source_corpus_digest
    assert verified.result_exact_ir_digest is not None
    assert verified.result_exact_ir_digest != verified.base_exact_ir_digest
    committed, receipt = commit_transaction(transaction_path)
    assert committed.state is TransactionState.COMMITTED
    assert receipt.source_writes is True
    assert "nn.Conv2d(3, 24, 3)" in (project / "src/app/blocks.py").read_text()


def test_v2_prepare_rejects_change_to_any_base_blob(tmp_path: Path) -> None:
    project, artifact, workspace, frontend = _setup(tmp_path)
    model = project / "src/app/model.py"
    model.write_text(model.read_text() + "\n# concurrent change\n", encoding="utf-8")

    with pytest.raises(ValueError, match="corpus changed"):
        prepare_transaction(_request(artifact, frontend), workspace)


def test_v2_commit_rejects_unrelated_base_blob_change(tmp_path: Path) -> None:
    project, artifact, workspace, frontend = _setup(tmp_path)
    transaction, _ = prepare_transaction(_request(artifact, frontend), workspace)
    transaction_path = workspace / "transactions" / transaction.transaction_id
    verified, _ = verify_transaction(transaction_path)
    assert verified.state is TransactionState.REVIEW_READY
    model = project / "src/app/model.py"
    concurrent = model.read_text() + "\n# concurrent change\n"
    model.write_text(concurrent, encoding="utf-8")

    failed, receipt = commit_transaction(transaction_path)

    assert failed.state is TransactionState.FAILED
    assert receipt.source_writes is False
    assert failed.diagnostics[-1].code == "CONCURRENT_MODIFICATION"
    assert model.read_text() == concurrent
    assert "nn.Conv2d(3, 16, 3)" in (project / "src/app/blocks.py").read_text()


def test_v2_transform_uses_frozen_bytes_after_freshness_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, artifact, workspace, frontend = _setup(tmp_path)
    original_copy = transaction_service._copy_project

    def copy_then_mutate(*args: object, **kwargs: object) -> None:
        original_copy(*args, **kwargs)
        source = project / "src/app/blocks.py"
        source.write_text(
            source.read_text().replace(
                "self.conv = nn.Conv2d(3, 16, 3)",
                "self.conv = nn.Conv2d(3, 99, 3)  # raced working tree",
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(transaction_service, "_copy_project", copy_then_mutate)

    transaction, _ = prepare_transaction(_request(artifact, frontend), workspace)
    prepared = (
        Path(transaction.temporary_project_root) / "src/app/blocks.py"
    ).read_text()

    assert "nn.Conv2d(3, 24, 3)" in prepared
    assert "raced working tree" not in prepared
    assert transaction.file_changes[0].before_sha256 == next(
        item.sha256
        for item in frontend.corpus.files
        if item.logical_path == "app/blocks.py"
    )


def test_v2_registered_module_insertion_round_trips_through_exact_ir(
    tmp_path: Path,
) -> None:
    project, artifact, workspace, frontend = _setup(tmp_path)
    request = _registered_insert_request(artifact, frontend)

    transaction, prepared = prepare_transaction(request, workspace)

    assert prepared.source_writes is False
    assert transaction.source_anchor is not None
    assert transaction.source_anchor.semantic_role == "module-call"
    assert transaction.proposal_correlation_id == "correlation:draft.after-conv"
    assert len(transaction.expected_delta.added_nodes) == 1
    inserted_node_id = transaction.expected_delta.added_nodes[0]
    assert inserted_node_id in transaction.realized_subject_ids
    assert any(item.startswith("port:") for item in transaction.realized_subject_ids)
    assert any(item.startswith("evidence:") for item in transaction.realized_subject_ids)
    assert prepared.proposal_correlation_id == transaction.proposal_correlation_id
    assert prepared.realized_subject_ids == transaction.realized_subject_ids
    prepared_source = (
        Path(transaction.temporary_project_root) / "src/app/blocks.py"
    ).read_text(encoding="utf-8")
    assert "self.after_conv = nn.GELU()" in prepared_source
    assert "x_after_conv = self.after_conv(x)" in prepared_source
    assert "return self.relu(x_after_conv)" in prepared_source

    verified, verify_receipt = verify_transaction(
        workspace / "transactions" / transaction.transaction_id
    )
    assert verified.state is TransactionState.REVIEW_READY
    assert verify_receipt.source_writes is False

    committed, commit_receipt = commit_transaction(
        workspace / "transactions" / transaction.transaction_id
    )
    assert committed.state is TransactionState.COMMITTED
    assert commit_receipt.source_writes is True
    assert commit_receipt.realized_subject_ids == transaction.realized_subject_ids

    reanalyzed = analyze_project_v2(
        project,
        "app.model:Model",
        "inference",
        "eval",
        tmp_path / "reanalysis",
    )
    inserted = next(
        item
        for item in reanalyzed.compatibility.architecture.nodes
        if item.node_id == inserted_node_id
    )
    assert inserted.semantic_name == "after_conv"
    assert inserted.attributes["definition_id"] == "pytorch.nn.gelu"


def test_studio_topology_draft_prepares_registered_insertion_transaction(
    tmp_path: Path,
) -> None:
    _, artifact, workspace, frontend = _setup(tmp_path)
    bundle = prepare_studio_bundle(artifact, workspace / "studio", write_static=False)
    definition = BuiltinModuleRegistry().resolve_qualified_name("torch.nn.GELU")
    assert definition is not None
    conv = next(
        item
        for item in frontend.compatibility.architecture.nodes
        if item.attributes.get("definition_id") == "pytorch.nn.conv2d"
    )
    relu = next(
        item
        for item in frontend.compatibility.architecture.nodes
        if item.attributes.get("definition_id") == "pytorch.nn.relu"
    )
    original = next(
        item
        for item in frontend.compatibility.architecture.edges
        if item.producer_id == conv.node_id and item.consumer_id == relu.node_id
    )
    session = bundle.begin_topology_draft(
        draft_document_digest(bundle.draft), "session:v2-insertion"
    )

    def dispatch(command: str, payload: dict[str, object]) -> None:
        assert bundle.topology_session is not None
        bundle.dispatch_topology_command(
            command,
            {
                **payload,
                "capability_id": session.capability.capability_id,
                "expected_document_digest": bundle.topology_session.current_document_digest,
            },
            "session:v2-insertion",
        )

    dispatch(
        "CreateNode",
        {
            "node": {
                "node_id": "draft:after-conv",
                "semantic_name": "after_conv",
                "framework": "pytorch",
                "node_type": definition.definition_id,
                "definition_ref": definition.ref.model_dump(mode="json"),
                "parameters": {"approximate": "none"},
            }
        },
    )
    dispatch(
        "ConnectPorts",
        {
            "edge": {
                "edge_id": "draft:edge-conv-after",
                "source_port_id": original.producer_port,
                "target_port_id": "draft:after-conv.input",
                "policy": "fanout",
                "relation": "main",
            }
        },
    )
    dispatch(
        "ConnectPorts",
        {
            "edge": {
                "edge_id": "draft:edge-after-relu",
                "source_port_id": "draft:after-conv.output",
                "target_port_id": original.consumer_port,
                "policy": "replace-input",
                "relation": "main",
            }
        },
    )

    receipt = bundle.submit_topology_draft(
        session.capability.capability_id,
        draft_document_digest(bundle.draft),
        "session:v2-insertion",
    )

    assert receipt.status == "review-ready"
    assert bundle.active_transaction is not None
    assert bundle.active_transaction.state is TransactionState.REVIEW_READY
    assert bundle.active_transaction.proposal_correlation_id == "correlation:after-conv"
    assert bundle.draft.lowering_status == "planned"
    assert bundle.draft.writeback_summary.eligibility == "commit"
    assert {item.status for item in bundle.draft.proofs} == {
        EditProofState.REVIEW_READY
    }


def _commit_studio_insertion(tmp_path: Path):  # type: ignore[no-untyped-def]
    project, artifact, workspace, frontend = _setup(tmp_path)
    bundle = prepare_studio_bundle(artifact, workspace / "studio", write_static=False)
    definition = BuiltinModuleRegistry().resolve_qualified_name("torch.nn.GELU")
    assert definition is not None
    conv = next(
        item
        for item in frontend.compatibility.architecture.nodes
        if item.attributes.get("definition_id") == "pytorch.nn.conv2d"
    )
    relu = next(
        item
        for item in frontend.compatibility.architecture.nodes
        if item.attributes.get("definition_id") == "pytorch.nn.relu"
    )
    original = next(
        item
        for item in frontend.compatibility.architecture.edges
        if item.producer_id == conv.node_id and item.consumer_id == relu.node_id
    )
    session = bundle.begin_topology_draft(
        draft_document_digest(bundle.draft), "session:reconcile"
    )

    def dispatch(command: str, payload: dict[str, object]) -> None:
        assert bundle.topology_session is not None
        bundle.dispatch_topology_command(
            command,
            {
                **payload,
                "capability_id": session.capability.capability_id,
                "expected_document_digest": bundle.topology_session.current_document_digest,
            },
            "session:reconcile",
        )

    dispatch(
        "CreateNode",
        {
            "node": {
                "node_id": "draft:after-conv",
                "semantic_name": "after_conv",
                "framework": "pytorch",
                "node_type": definition.definition_id,
                "definition_ref": definition.ref.model_dump(mode="json"),
                "parameters": {"approximate": "none"},
            }
        },
    )
    dispatch(
        "ConnectPorts",
        {
            "edge": {
                "edge_id": "draft:edge-conv-after",
                "source_port_id": original.producer_port,
                "target_port_id": "draft:after-conv.input",
                "policy": "fanout",
                "relation": "main",
            }
        },
    )
    dispatch(
        "ConnectPorts",
        {
            "edge": {
                "edge_id": "draft:edge-after-relu",
                "source_port_id": "draft:after-conv.output",
                "target_port_id": original.consumer_port,
                "policy": "replace-input",
                "relation": "main",
            }
        },
    )
    bundle.submit_topology_draft(
        session.capability.capability_id,
        draft_document_digest(bundle.draft),
        "session:reconcile",
    )
    bundle.commit_parameter()
    assert bundle.active_transaction is not None
    return project, artifact, workspace, bundle, set(
        bundle.active_transaction.realized_subject_ids
    )


def test_studio_reanalysis_retires_realized_synthetic_insertion(tmp_path: Path) -> None:
    project, artifact, workspace, _bundle, realized = _commit_studio_insertion(tmp_path)

    refreshed_frontend = analyze_project_v2(
        project,
        "app.model:Model",
        "inference",
        "eval",
        tmp_path / "reanalysis",
    )
    _write_frontend_bundle(artifact.parent, refreshed_frontend)
    refreshed = prepare_studio_bundle(
        artifact,
        workspace / "studio",
        write_static=False,
        replace_stale_bindings=True,
    )

    assert not refreshed.draft.nodes
    assert not refreshed.draft.edges
    assert not refreshed.draft.intents
    assert not refreshed.draft.proofs
    assert refreshed.draft.lowering_status == "not-planned"
    receipt = refreshed.draft.reconciliation_receipts[-1]
    assert receipt.status == "realized"
    assert set(receipt.canonical_subject_ids) == realized
    available = {
        *[node.node_id for node in refreshed.architecture.nodes],
        *[
            port.port_id
            for node in refreshed.architecture.nodes
            for port in [*node.input_ports, *node.output_ports]
        ],
        *[item.evidence_id for item in refreshed.evidence],
    }
    assert realized <= available


def test_studio_reanalysis_keeps_synthetic_when_realization_is_incomplete(
    tmp_path: Path,
) -> None:
    project, artifact, workspace, bundle, _realized = _commit_studio_insertion(tmp_path)
    assert bundle.active_transaction is not None
    transaction_path = (
        Path(bundle.active_transaction.workspace)
        / "transactions"
        / bundle.active_transaction.transaction_id
        / "transaction.json"
    )
    payload = json.loads(transaction_path.read_text(encoding="utf-8"))
    payload["realized_subject_ids"].append("node:canonical-result-missing")
    _write_json(transaction_path, payload)

    refreshed_frontend = analyze_project_v2(
        project,
        "app.model:Model",
        "inference",
        "eval",
        tmp_path / "reanalysis",
    )
    _write_frontend_bundle(artifact.parent, refreshed_frontend)
    refreshed = prepare_studio_bundle(
        artifact,
        workspace / "studio",
        write_static=False,
        replace_stale_bindings=True,
    )

    assert {item.node_id for item in refreshed.draft.nodes} == {"draft:after-conv"}
    assert refreshed.draft.edges
    assert refreshed.draft.intents
    assert refreshed.draft.lowering_status == "blocked"
    assert refreshed.draft.writeback_summary.eligibility == "blocked"
    assert {
        reason
        for proof in refreshed.draft.proofs
        for reason in proof.reason_codes
    } == {"SYNTHETIC_REALIZATION_MISMATCH"}
    receipt = refreshed.draft.reconciliation_receipts[-1]
    assert receipt.status == "blocked"
    assert receipt.missing_subject_ids == ["node:canonical-result-missing"]
