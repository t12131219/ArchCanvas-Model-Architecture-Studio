from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from archcanvas_core.models import (
    AgentProposal,
    ProposedConnection,
    SemanticStructuralPatch,
    TransactionState,
)
from archcanvas_engine.cli import main
from archcanvas_python import analyze_project
from archcanvas_transactions import commit_transaction, prepare_transaction, verify_transaction
from archcanvas_transactions.registry import plan_connection, unsupported_intent_proposal

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "tier_a" / "transformer"


def _setup(tmp_path: Path) -> tuple[Path, Path, Path, object]:
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
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    artifact = analysis / "architecture.json"
    artifact.write_text(bundle.architecture.model_dump_json())
    (analysis / "source-snapshot.json").write_text(bundle.snapshot.model_dump_json())
    (analysis / "evidence-ledger.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in bundle.evidence])
    )
    return project, artifact, tmp_path / "workspace", bundle


def _request(artifact: Path, operation: str, parameters: dict[str, object]):
    return SemanticStructuralPatch(
        patch_id=f"patch:test-{operation.replace('_', '-')}",
        operation=operation,
        artifact_path=str(artifact),
        target_node_id="node:activation",
        parameters=parameters,
    )


def test_replace_activation_round_trip_and_mutation_oracle(tmp_path: Path) -> None:
    project, artifact, workspace, _ = _setup(tmp_path)
    original = (project / "model.py").read_bytes()
    transaction, receipt = prepare_transaction(
        _request(artifact, "replace_activation", {"replacement": "ReLU"}), workspace
    )
    transaction_path = workspace / "transactions" / transaction.transaction_id

    assert receipt.source_writes is False
    assert transaction.expected_delta.changed_nodes == ["node:activation"]
    prepared = Path(transaction.temporary_project_root) / "model.py"
    assert "self.activation = nn.ReLU()" in prepared.read_text()
    assert (project / "model.py").read_bytes() == original

    verified, _ = verify_transaction(transaction_path)
    assert verified.state is TransactionState.REVIEW_READY
    assert verified.expected_delta == verified.observed_delta
    committed, receipt = commit_transaction(transaction_path)
    assert committed.state is TransactionState.COMMITTED
    assert receipt.source_writes is True
    assert "self.activation = nn.ReLU()" in (project / "model.py").read_text()
    reanalyzed = analyze_project(
        project,
        "model:Transformer",
        "inference",
        "eval",
        (project / "config.json").read_bytes(),
        project / "config.json",
    )
    activation = next(
        item for item in reanalyzed.architecture.nodes if item.node_id == "node:activation"
    )
    assert activation.attributes["op_type"] == "nn.ReLU"

    second, _, second_workspace, _ = _setup(tmp_path / "mutation")
    mutated, _ = prepare_transaction(
        _request(
            tmp_path / "mutation" / "analysis" / "architecture.json",
            "replace_activation",
            {"replacement": "ReLU"},
        ),
        second_workspace,
    )
    mutated_path = Path(mutated.temporary_project_root) / "model.py"
    mutated_path.write_text(mutated_path.read_text().replace("nn.ReLU()", "nn.SiLU()"))
    failed, _ = verify_transaction(
        second_workspace / "transactions" / mutated.transaction_id
    )
    assert failed.state is TransactionState.FAILED
    assert failed.diagnostics[-1].code == "GRAPH_DELTA_MISMATCH"
    assert (second / "model.py").read_bytes() == original


def test_insert_layer_norm_round_trip_and_topology_mutation(tmp_path: Path) -> None:
    project, artifact, workspace, _ = _setup(tmp_path)
    original = (project / "model.py").read_bytes()
    transaction, _ = prepare_transaction(
        _request(
            artifact,
            "insert_layer_norm",
            {"module_name": "activation_norm", "normalized_shape": "d_model"},
        ),
        workspace,
    )
    transaction_path = workspace / "transactions" / transaction.transaction_id
    prepared = Path(transaction.temporary_project_root) / "model.py"
    content = prepared.read_text()

    assert "self.activation_norm = nn.LayerNorm(d_model)" in content
    assert "activated_activation_norm = self.activation_norm(activated)" in content
    assert "self.ffn_out(activated_activation_norm)" in content
    assert transaction.expected_delta.added_nodes == ["node:activation_norm"]
    assert len(transaction.expected_delta.added_edges) == 2
    assert len(transaction.expected_delta.removed_edges) == 1
    verified, _ = verify_transaction(transaction_path)
    assert verified.state is TransactionState.REVIEW_READY
    assert (project / "model.py").read_bytes() == original
    committed, _ = commit_transaction(transaction_path)
    assert committed.state is TransactionState.COMMITTED
    reanalyzed = analyze_project(
        project,
        "model:Transformer",
        "inference",
        "eval",
        (project / "config.json").read_bytes(),
        project / "config.json",
    )
    assert any(
        item.node_id == "node:activation_norm" for item in reanalyzed.architecture.nodes
    )

    mutated_project, mutated_artifact, mutated_workspace, _ = _setup(tmp_path / "mutation")
    mutated, _ = prepare_transaction(
        _request(
            mutated_artifact,
            "insert_layer_norm",
            {"module_name": "activation_norm", "normalized_shape": "d_model"},
        ),
        mutated_workspace,
    )
    mutated_source = Path(mutated.temporary_project_root) / "model.py"
    mutated_source.write_text(
        mutated_source.read_text().replace(
            "self.ffn_out(activated_activation_norm)", "self.ffn_out(activated)"
        )
    )
    failed, _ = verify_transaction(
        mutated_workspace / "transactions" / mutated.transaction_id
    )
    assert failed.state is TransactionState.FAILED
    assert failed.diagnostics[-1].code == "GRAPH_DELTA_MISMATCH"
    assert (mutated_project / "model.py").read_bytes() == original


def test_proposed_connection_handoff_never_grants_permissions(tmp_path: Path) -> None:
    _, artifact, _, bundle = _setup(tmp_path)
    edge = bundle.architecture.edges[0]
    proposal = plan_connection(
        ProposedConnection(
            proposal_id="proposal:test-connection",
            artifact_path=str(artifact),
            source_node_id=edge.producer_id,
            source_port_id=edge.producer_port,
            target_node_id=edge.consumer_id,
            target_port_id=edge.consumer_port,
        ),
        bundle.architecture,
    )

    assert proposal.status == "handoff-required"
    assert proposal.permissions == {"shell": False, "network": False, "source_write": False}
    assert proposal.source_context["registry_match"] is None

    unsupported = unsupported_intent_proposal(
        {"proposal_id": "proposal:cross-attention", "description": "Add cross-attention"}
    )
    assert unsupported.reason_code == "UNSUPPORTED_STRUCTURAL_INTENT"
    assert not any(unsupported.permissions.values())


def test_structural_protocol_rejects_unregistered_operation_and_proposal_permissions() -> None:
    with pytest.raises(ValidationError):
        SemanticStructuralPatch(
            patch_id="patch:skip",
            operation="add_skip_connection",
            artifact_path="architecture.json",
            target_node_id="node:activation",
        )
    with pytest.raises(ValidationError):
        AgentProposal(
            proposal_id="proposal:unsafe",
            reason_code="UNSUPPORTED_STRUCTURAL_INTENT",
            summary="Unsafe proposal",
            requested_intent={"description": "Run arbitrary edit"},
            permissions={"shell": False, "network": False, "source_write": True},
        )


def test_cli_routes_structural_transactions_and_proposals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, artifact, workspace, bundle = _setup(tmp_path)
    structural_path = tmp_path / "structural.json"
    structural_path.write_text(
        _request(artifact, "replace_activation", {"replacement": "SiLU"}).model_dump_json()
    )

    exit_code = main(
        ["patch", "prepare", str(structural_path), "--workspace", str(workspace), "--json"]
    )
    receipt = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert receipt["details"]["source_writes"] is False
    assert receipt["details"]["expected_delta"]["changed_nodes"] == ["node:activation"]

    edge = bundle.architecture.edges[0]
    proposal_request = tmp_path / "connection.json"
    proposal_request.write_text(
        ProposedConnection(
            proposal_id="proposal:cli-connection",
            artifact_path=str(artifact),
            source_node_id=edge.producer_id,
            source_port_id=edge.producer_port,
            target_node_id=edge.consumer_id,
            target_port_id=edge.consumer_port,
        ).model_dump_json()
    )
    output = tmp_path / "agent-proposal.json"
    exit_code = main(
        ["propose", str(proposal_request), "--out", str(output), "--json"]
    )
    captured = capsys.readouterr()
    receipt = json.loads(captured.out)
    proposal = json.loads(output.read_text())
    assert exit_code == 0
    assert captured.out.count("\n") == 1
    assert receipt["details"]["source_writes"] is False
    assert proposal["permissions"] == {
        "shell": False,
        "network": False,
        "source_write": False,
    }
