from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

from archcanvas_core.models import SemanticParameterPatch, TransactionState
from archcanvas_engine.cli import main
from archcanvas_python import analyze_project
from archcanvas_transactions import (
    commit_transaction,
    prepare_transaction,
    verify_transaction,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "tier_a" / "transformer"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _analysis(project: Path, target: Path) -> Path:
    bundle = analyze_project(
        project,
        "model:Transformer",
        "inference",
        "eval",
        (project / "config.json").read_bytes(),
        project / "config.json",
    )
    target.mkdir(parents=True)
    (target / "architecture.json").write_text(bundle.architecture.model_dump_json())
    (target / "source-snapshot.json").write_text(bundle.snapshot.model_dump_json())
    (target / "evidence-ledger.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in bundle.evidence])
    )
    return target / "architecture.json"


def _setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    artifact = _analysis(project, tmp_path / "analysis")
    return project, artifact, tmp_path / "workspace"


def _request(
    artifact: Path,
    *,
    node: str = "node:generator",
    parameter: str = "out_features",
    value: int = 16000,
    tests: list[list[str]] | None = None,
) -> SemanticParameterPatch:
    return SemanticParameterPatch(
        patch_id="patch:test-parameter",
        artifact_path=str(artifact),
        target_node_id=node,
        parameter_name=parameter,
        new_value=value,
        targeted_tests=tests or [],
    )


def test_parameter_transaction_prepares_verifies_commits_and_reanalyzes(tmp_path: Path) -> None:
    project, artifact, workspace = _setup(tmp_path)
    original_hash = _sha256(project / "config.json")
    transaction, prepare_receipt = prepare_transaction(_request(artifact), workspace)
    transaction_path = workspace / "transactions" / transaction.transaction_id

    assert prepare_receipt.source_writes is False
    assert transaction.state is TransactionState.PREPARED
    assert _sha256(project / "config.json") == original_hash
    assert '"vocab_size": 32000' in transaction.source_diff
    assert '"vocab_size": 16000' in transaction.source_diff
    assert transaction.expected_delta.added_nodes == []
    assert transaction.expected_delta.removed_edges == []
    assert transaction.expected_delta.changed_parameters[0].node_id == "node:generator"

    verified, verify_receipt = verify_transaction(transaction_path)
    assert verify_receipt.source_writes is False
    assert verified.state is TransactionState.REVIEW_READY
    assert verified.state_history == [
        TransactionState.DRAFT,
        TransactionState.PLANNED,
        TransactionState.PREPARED,
        TransactionState.SOURCE_VALIDATED,
        TransactionState.REANALYZED,
        TransactionState.GRAPH_DELTA_VALIDATED,
        TransactionState.TESTS_PASSED,
        TransactionState.REVIEW_READY,
    ]
    assert verified.observed_delta == verified.expected_delta
    assert _sha256(project / "config.json") == original_hash

    committed, commit_receipt = commit_transaction(transaction_path)
    assert commit_receipt.source_writes is True
    assert committed.state is TransactionState.COMMITTED
    assert json.loads((project / "config.json").read_text())["vocab_size"] == 16000
    reanalyzed = analyze_project(
        project,
        "model:Transformer",
        "inference",
        "eval",
        (project / "config.json").read_bytes(),
        project / "config.json",
    )
    generator = next(item for item in reanalyzed.architecture.nodes if item.node_id == "node:generator")
    assert next(item for item in generator.parameters if item.name == "out_features").value == 16000


def test_syntax_failure_does_not_change_original(tmp_path: Path) -> None:
    project, artifact, workspace = _setup(tmp_path)
    original = (project / "config.json").read_bytes()
    transaction, _ = prepare_transaction(_request(artifact), workspace)
    prepared = Path(transaction.temporary_project_root) / "config.json"
    prepared.write_text("{ invalid json", encoding="utf-8")

    failed, receipt = verify_transaction(workspace / "transactions" / transaction.transaction_id)

    assert failed.state is TransactionState.FAILED
    assert receipt.source_writes is False
    assert failed.diagnostics[-1].code == "TRANSACTION_SOURCE_INVALID"
    assert (project / "config.json").read_bytes() == original


def test_shape_failure_does_not_change_original(tmp_path: Path) -> None:
    project, artifact, workspace = _setup(tmp_path)
    original = (project / "config.json").read_bytes()
    transaction, _ = prepare_transaction(
        _request(
            artifact,
            node="node:encoder_q_proj",
            parameter="in_features",
            value=63,
        ),
        workspace,
    )

    failed, _ = verify_transaction(workspace / "transactions" / transaction.transaction_id)

    assert failed.state is TransactionState.FAILED
    assert failed.diagnostics[-1].code == "SHAPE_INVARIANT_FAILED"
    assert (project / "config.json").read_bytes() == original


def test_targeted_test_failure_does_not_change_original(tmp_path: Path) -> None:
    project, artifact, workspace = _setup(tmp_path)
    original = (project / "config.json").read_bytes()
    transaction, _ = prepare_transaction(
        _request(artifact, tests=[[sys.executable, "-c", "raise SystemExit(7)"]]),
        workspace,
    )

    failed, _ = verify_transaction(workspace / "transactions" / transaction.transaction_id)

    assert failed.state is TransactionState.FAILED
    assert failed.diagnostics[-1].code == "TARGETED_TEST_FAILED"
    assert (project / "config.json").read_bytes() == original


def test_concurrent_modification_rejects_commit_without_overwrite(tmp_path: Path) -> None:
    project, artifact, workspace = _setup(tmp_path)
    transaction, _ = prepare_transaction(_request(artifact), workspace)
    transaction_path = workspace / "transactions" / transaction.transaction_id
    verified, _ = verify_transaction(transaction_path)
    assert verified.state is TransactionState.REVIEW_READY
    concurrent = json.loads((project / "config.json").read_text())
    concurrent["task"] = "concurrently-edited"
    concurrent_bytes = (json.dumps(concurrent, indent=2) + "\n").encode()
    (project / "config.json").write_bytes(concurrent_bytes)

    failed, receipt = commit_transaction(transaction_path)

    assert failed.state is TransactionState.FAILED
    assert receipt.source_writes is False
    assert failed.diagnostics[-1].code == "CONCURRENT_MODIFICATION"
    assert (project / "config.json").read_bytes() == concurrent_bytes


def test_cli_patch_emits_one_json_receipt(tmp_path: Path, capsys) -> None:
    _, artifact, workspace = _setup(tmp_path)
    request_path = tmp_path / "request.json"
    request_path.write_text(_request(artifact).model_dump_json())

    exit_code = main(
        ["patch", "prepare", str(request_path), "--workspace", str(workspace), "--json"]
    )
    captured = capsys.readouterr()
    receipt = json.loads(captured.out)

    assert exit_code == 0
    assert captured.out.count("\n") == 1
    assert receipt["details"]["transaction_state"] == "prepared"
    assert receipt["details"]["source_writes"] is False


def test_python_literal_parameter_uses_exact_libcst_anchor(tmp_path: Path) -> None:
    project = tmp_path / "literal-project"
    project.mkdir()
    source = (
        "from torch import nn\n\n"
        "class Toy(nn.Module):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self.proj = nn.Linear(4, 8)\n\n"
        "    def forward(self, x):\n"
        "        y = self.proj(x)\n"
        "        return y\n"
    )
    (project / "model.py").write_text(source)
    (project / "config.json").write_text("{}\n")
    bundle = analyze_project(
        project,
        "model:Toy",
        "inference",
        "eval",
        b"{}\n",
        project / "config.json",
    )
    analysis = tmp_path / "literal-analysis"
    analysis.mkdir()
    artifact = analysis / "architecture.json"
    artifact.write_text(bundle.architecture.model_dump_json())
    (analysis / "source-snapshot.json").write_text(bundle.snapshot.model_dump_json())
    (analysis / "evidence-ledger.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in bundle.evidence])
    )
    request = SemanticParameterPatch(
        patch_id="patch:literal",
        artifact_path=str(artifact),
        target_node_id="node:proj",
        parameter_name="out_features",
        new_value=12,
    )

    transaction, _ = prepare_transaction(request, tmp_path / "literal-workspace")

    prepared_source = (Path(transaction.temporary_project_root) / "model.py").read_text()
    assert "self.proj = nn.Linear(4, 12)" in prepared_source
    assert (project / "model.py").read_text() == source
