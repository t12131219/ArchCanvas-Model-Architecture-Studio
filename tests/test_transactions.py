from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

from archcanvas_core.models import (
    EditTargetScope,
    SemanticParameterPatch,
    StateAssetBinding,
    StateInventoryEntry,
    StateTensorSpec,
    TransactionJournalState,
    TransactionState,
    ValueOriginKind,
)
from archcanvas_engine.cli import main
from archcanvas_python import analyze_project
from archcanvas_release import create_bundle, verify_bundle
from archcanvas_studio.bundle import prepare_studio_bundle
from archcanvas_transactions import (
    commit_transaction,
    prepare_transaction,
    recover_incomplete_transactions,
    resolve_parameter_edit_context,
    state_inventory_digest,
    verify_transaction,
)
from archcanvas_transactions.store import load_journal, load_transaction, save_journal

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
    assert json.loads(
        (transaction_path / "transaction-receipt.json").read_text(encoding="utf-8")
    ) == prepare_receipt.model_dump(mode="json")
    assert transaction.state is TransactionState.PREPARED
    assert _sha256(project / "config.json") == original_hash
    assert '"vocab_size": 32000' in transaction.source_diff
    assert '"vocab_size": 16000' in transaction.source_diff
    assert transaction.expected_delta.added_nodes == []
    assert transaction.expected_delta.removed_edges == []
    assert transaction.expected_delta.changed_parameters[0].node_id == "node:generator"
    assert transaction.parameter_edit_context is not None
    assert transaction.parameter_edit_context.value_origin.kind is ValueOriginKind.CONFIG_KEY
    assert transaction.parameter_edit_context.default_scope is EditTargetScope.CONFIG_VALUE
    assert transaction.parameter_edit_context.affected_canonical_ids == ["node:generator"]

    additive_path = transaction_path / "transaction-additive-minor.json"
    additive_payload = transaction.model_dump(mode="json")
    additive_payload["schema_version"] = "1.1"
    additive_path.write_text(json.dumps(additive_payload), encoding="utf-8")
    assert load_transaction(additive_path) == transaction
    additive_payload["schema_version"] = "2.0"
    additive_path.write_text(json.dumps(additive_payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported source-transaction schema major"):
        load_transaction(additive_path)

    verified, verify_receipt = verify_transaction(transaction_path)
    assert verify_receipt.source_writes is False
    assert json.loads(
        (transaction_path / "transaction-receipt.json").read_text(encoding="utf-8")
    ) == verify_receipt.model_dump(mode="json")
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
    assert json.loads(
        (transaction_path / "transaction-receipt.json").read_text(encoding="utf-8")
    ) == commit_receipt.model_dump(mode="json")
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

    offline = tmp_path / "transaction-receipts.archcanvas"
    manifest, _ = create_bundle(artifact, offline, workspace=workspace)
    transaction_prefix = f"receipts/transactions/{transaction.transaction_id}/"
    bundled = {item.path for item in manifest.files}
    assert transaction_prefix + "transaction.json" in bundled
    assert transaction_prefix + "transaction-receipt.json" in bundled
    assert transaction_prefix + "transaction-journal.json" in bundled
    assert verify_bundle(offline) == manifest


def test_transaction_journal_reaches_committed_with_verified_backup(tmp_path: Path) -> None:
    _, artifact, workspace = _setup(tmp_path)
    transaction, _ = prepare_transaction(_request(artifact), workspace)
    transaction_path = workspace / "transactions" / transaction.transaction_id
    prepared_journal = load_journal(transaction_path)

    assert prepared_journal.state is TransactionJournalState.PREPARED
    assert prepared_journal.files[0].backup_verified is False

    verify_transaction(transaction_path)
    assert load_journal(transaction_path).state is TransactionJournalState.VERIFIED

    commit_transaction(transaction_path)
    committed_journal = load_journal(transaction_path)
    entry = committed_journal.files[0]
    assert committed_journal.state is TransactionJournalState.COMMITTED
    assert entry.backup_verified is True
    assert entry.rename_completed is True
    assert entry.directory_fsync_completed is True
    assert (transaction_path / entry.backup_relative_path).is_file()
    assert committed_journal.post_commit_gates[-1].status == "passed"


def test_bound_checkpoint_has_separate_blocked_state_compatibility(tmp_path: Path) -> None:
    project, artifact, workspace = _setup(tmp_path)
    inventory_entry = StateInventoryEntry(
        state_key="generator.weight",
        role="parameter",
        tensor=StateTensorSpec(dimensions=[32000, 64], dtype="float32", device="cpu"),
        parameter_group_id="parameter-group:generator-weight",
        optimizer_slot_keys=["exp_avg", "exp_avg_sq"],
        evidence_ids=["evidence:config.vocab_size"],
    )
    binding = StateAssetBinding(
        binding_id="state-asset:test-checkpoint",
        framework="pytorch",
        source_state_digest=hashlib.sha256(b"checkpoint").hexdigest(),
        inventory_digest="0" * 64,
        inventory=[inventory_entry],
        optimizer_state_bound=True,
    )
    binding = binding.model_copy(update={"inventory_digest": state_inventory_digest(binding)})
    request = _request(artifact).model_copy(update={"state_asset_binding": binding})

    transaction, prepared = prepare_transaction(request, workspace)
    transaction_path = workspace / "transactions" / transaction.transaction_id

    assert transaction.state_migration_plan is not None
    assert transaction.state_migration_plan.status == "blocked"
    assert transaction.state_migration_plan.entries[0].action.value == "block"
    assert prepared.source_status == "prepared"
    assert prepared.state_compatibility == "blocked"
    assert prepared.training_resume_compatibility == "blocked"
    assert prepared.inference_compatibility == "blocked"

    _, verified = verify_transaction(transaction_path)
    assert verified.source_status == "verified"
    assert verified.state_compatibility == "blocked"

    committed, receipt = commit_transaction(transaction_path)
    assert committed.state is TransactionState.COMMITTED
    assert receipt.source_status == "committed"
    assert receipt.state_compatibility == "blocked"
    assert json.loads((project / "config.json").read_text())["vocab_size"] == 16000


def test_startup_recovery_completes_all_after_commit_state(tmp_path: Path) -> None:
    project, artifact, workspace = _setup(tmp_path)
    transaction, _ = prepare_transaction(_request(artifact), workspace)
    transaction_path = workspace / "transactions" / transaction.transaction_id
    transaction, _ = verify_transaction(transaction_path)
    journal = load_journal(transaction_path)
    entry = journal.files[0]
    original = project / entry.working_path
    prepared = Path(transaction.temporary_project_root) / entry.working_path
    backup = transaction_path / entry.backup_relative_path
    backup.parent.mkdir(parents=True)
    backup.write_bytes(original.read_bytes())
    backup.chmod(entry.original_metadata.mode)
    original.write_bytes(prepared.read_bytes())
    original.chmod(entry.original_metadata.mode)
    replaced_entry = entry.model_copy(
        update={
            "backup_verified": True,
            "replacement_status": "replaced",
            "rename_completed": True,
            "directory_fsync_completed": True,
        }
    )
    save_journal(
        journal.model_copy(
            update={
                "state": TransactionJournalState.REPLACING_FILES,
                "files": [replaced_entry],
            }
        ),
        transaction_path,
    )

    receipts = recover_incomplete_transactions(workspace)

    assert len(receipts) == 1
    assert receipts[0].outcome == "committed"
    assert receipts[0].after_state_proven is True
    assert load_journal(transaction_path).state is TransactionJournalState.COMMITTED
    assert load_transaction(transaction_path).state is TransactionState.COMMITTED
    assert json.loads(original.read_text())["vocab_size"] == 16000


def test_startup_recovery_rolls_back_mixed_multifile_state(tmp_path: Path) -> None:
    project, artifact, workspace = _setup(tmp_path)
    model = project / "model.py"
    config = project / "config.json"
    model_before = model.read_bytes()
    config_before = config.read_bytes()
    transaction, _ = prepare_transaction(_request(artifact), workspace)
    transaction_path = workspace / "transactions" / transaction.transaction_id
    transaction, _ = verify_transaction(transaction_path)
    journal = load_journal(transaction_path)
    config_entry = journal.files[0]
    model_after = model_before + b"\n# recovery probe\n"
    model_entry = config_entry.model_copy(
        update={
            "logical_path": "model.py",
            "working_path": "model.py",
            "before_sha256": hashlib.sha256(model_before).hexdigest(),
            "after_sha256": hashlib.sha256(model_after).hexdigest(),
            "backup_relative_path": "journal-backups/0001-model.py",
        }
    )
    journal = journal.model_copy(update={"files": [config_entry, model_entry]})
    changed_entries = []
    for entry in journal.files:
        original = project / entry.working_path
        backup = transaction_path / entry.backup_relative_path
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(original.read_bytes())
        backup.chmod(entry.original_metadata.mode)
        changed_entries.append(entry.model_copy(update={"backup_verified": True}))
    first = changed_entries[0]
    first_original = project / first.working_path
    first_prepared = Path(transaction.temporary_project_root) / first.working_path
    first_original.write_bytes(first_prepared.read_bytes())
    first_original.chmod(first.original_metadata.mode)
    changed_entries[0] = first.model_copy(
        update={
            "replacement_status": "replaced",
            "rename_completed": True,
            "directory_fsync_completed": True,
        }
    )
    save_journal(
        journal.model_copy(
            update={
                "state": TransactionJournalState.REPLACING_FILES,
                "files": changed_entries,
            }
        ),
        transaction_path,
    )

    receipts = recover_incomplete_transactions(workspace)

    assert receipts[0].outcome == "rolled-back"
    assert receipts[0].before_state_proven is True
    assert receipts[0].recovered_files == [first.logical_path]
    assert model.read_bytes() == model_before
    assert config.read_bytes() == config_before
    assert load_journal(transaction_path).state is TransactionJournalState.ROLLED_BACK
    studio = prepare_studio_bundle(artifact, workspace, write_static=False)
    assert studio.state()["recovery_receipts"][0]["outcome"] == "rolled-back"


def test_commit_preserves_utf8_bom_crlf_trailing_newline_and_mode(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    config = project / "config.json"
    normalized = config.read_text(encoding="utf-8").replace("\n", "\r\n")
    config.write_bytes(b"\xef\xbb\xbf" + normalized.encode("utf-8"))
    config.chmod(0o640)
    artifact = _analysis(project, tmp_path / "analysis")
    workspace = tmp_path / "workspace"
    transaction, _ = prepare_transaction(_request(artifact), workspace)
    transaction_path = workspace / "transactions" / transaction.transaction_id

    verify_transaction(transaction_path)
    committed, _ = commit_transaction(transaction_path)
    content = config.read_bytes()

    assert committed.state is TransactionState.COMMITTED
    assert content.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in content
    assert b"\n" not in content.replace(b"\r\n", b"")
    assert content.endswith(b"\r\n")
    assert config.stat().st_mode & 0o777 == 0o640


def test_prepare_retry_reuses_intent_and_base_source_transaction(tmp_path: Path) -> None:
    _, artifact, workspace = _setup(tmp_path)
    request = _request(artifact)

    first, first_receipt = prepare_transaction(request, workspace)
    second, second_receipt = prepare_transaction(request, workspace)

    assert first.base_source_corpus_digest is not None
    assert second == first
    assert second_receipt == first_receipt
    assert [path.name for path in (workspace / "transactions").iterdir()] == [
        first.transaction_id
    ]


def test_committed_intent_retry_returns_original_without_second_write(tmp_path: Path) -> None:
    project, artifact, workspace = _setup(tmp_path)
    request = _request(artifact)
    transaction, _ = prepare_transaction(request, workspace)
    transaction_path = workspace / "transactions" / transaction.transaction_id
    verify_transaction(transaction_path)
    committed, committed_receipt = commit_transaction(transaction_path)
    committed_bytes = (project / "config.json").read_bytes()

    retried, retry_receipt = prepare_transaction(request, workspace)

    assert retried == committed
    assert retry_receipt == committed_receipt
    assert (project / "config.json").read_bytes() == committed_bytes
    assert len(list((workspace / "transactions").iterdir())) == 1


def test_reused_intent_id_rejects_different_payload_on_same_base(tmp_path: Path) -> None:
    _, artifact, workspace = _setup(tmp_path)
    request = _request(artifact)
    prepare_transaction(request, workspace)

    with pytest.raises(ValueError, match="intent id is already bound"):
        prepare_transaction(request.model_copy(update={"new_value": 12000}), workspace)

    assert len(list((workspace / "transactions").iterdir())) == 1


def test_parameter_noop_creates_no_transaction_workspace(tmp_path: Path) -> None:
    _, artifact, workspace = _setup(tmp_path)

    with pytest.raises(ValueError, match="identical to the current value"):
        prepare_transaction(_request(artifact, value=32000), workspace)

    assert not workspace.exists()


def test_parameter_scope_contract_is_recomputed_and_rejects_stale_impact(
    tmp_path: Path,
) -> None:
    _, artifact, workspace = _setup(tmp_path)
    context = resolve_parameter_edit_context(
        artifact, "node:generator", "out_features"
    )
    request = _request(artifact).model_copy(
        update={
            "value_origin_id": context.value_origin.origin_id,
            "edit_target_scope": context.default_scope,
            "confirmed_affected_ids": context.affected_canonical_ids,
            "confirmed_source_anchor_ids": context.value_origin.source_anchor_ids,
        }
    )

    transaction, _ = prepare_transaction(request, workspace)

    assert transaction.parameter_edit_context == context
    assert transaction.request.edit_target_scope is EditTargetScope.CONFIG_VALUE

    stale_workspace = tmp_path / "stale-workspace"
    with pytest.raises(ValueError, match="affected canonical objects are stale"):
        prepare_transaction(
            request.model_copy(update={"confirmed_affected_ids": ["node:activation"]}),
            stale_workspace,
        )
    assert not stale_workspace.exists()


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
