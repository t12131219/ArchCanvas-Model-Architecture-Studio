from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from archcanvas_core.models import (
    RecoveryReceipt,
    SourceTransaction,
    TransactionJournal,
    TransactionReceipt,
)
from archcanvas_core.protocols import read_source_transaction_protocol


def _write_model(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_value = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    payload = json.dumps(
        payload_value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.replace(path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return path


def transaction_file(path: Path) -> Path:
    resolved = path.resolve()
    return resolved / "transaction.json" if resolved.is_dir() else resolved


def load_transaction(path: Path) -> SourceTransaction:
    manifest = transaction_file(path)
    if not manifest.is_file():
        raise ValueError(f"transaction manifest not found: {manifest}")
    transaction, _ = read_source_transaction_protocol(
        json.loads(manifest.read_text(encoding="utf-8"))
    )
    return transaction


def save_transaction(transaction: SourceTransaction) -> Path:
    directory = Path(transaction.workspace) / "transactions" / transaction.transaction_id
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / "transaction.json"
    _write_model(manifest, transaction)
    if transaction.state_migration_plan is not None:
        _write_model(directory / "state-migration-plan.json", transaction.state_migration_plan)
    return manifest


def save_transaction_receipt(
    receipt: TransactionReceipt, transaction_directory: Path
) -> Path:
    return _write_model(
        transaction_directory.resolve() / "transaction-receipt.json",
        receipt,
    )


def journal_file(path: Path) -> Path:
    resolved = path.resolve()
    return resolved / "transaction-journal.json" if resolved.is_dir() else resolved


def load_journal(path: Path) -> TransactionJournal:
    manifest = journal_file(path)
    if not manifest.is_file():
        raise ValueError(f"transaction journal not found: {manifest}")
    return TransactionJournal.model_validate_json(manifest.read_text(encoding="utf-8"))


def save_journal(journal: TransactionJournal, transaction_directory: Path) -> Path:
    return _write_model(
        transaction_directory.resolve() / "transaction-journal.json",
        journal,
    )


def save_recovery_receipt(
    receipt: RecoveryReceipt, transaction_directory: Path
) -> Path:
    return _write_model(
        transaction_directory.resolve() / "recovery-receipt.json",
        receipt,
    )
