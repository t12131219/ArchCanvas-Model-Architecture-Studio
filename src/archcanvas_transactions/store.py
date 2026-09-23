from __future__ import annotations

import json
import tempfile
from pathlib import Path

from archcanvas_core.models import SourceTransaction


def transaction_file(path: Path) -> Path:
    resolved = path.resolve()
    return resolved / "transaction.json" if resolved.is_dir() else resolved


def load_transaction(path: Path) -> SourceTransaction:
    manifest = transaction_file(path)
    if not manifest.is_file():
        raise ValueError(f"transaction manifest not found: {manifest}")
    return SourceTransaction.model_validate_json(manifest.read_text(encoding="utf-8"))


def save_transaction(transaction: SourceTransaction) -> Path:
    directory = Path(transaction.workspace) / "transactions" / transaction.transaction_id
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / "transaction.json"
    payload = json.dumps(
        transaction.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=directory, delete=False
    ) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    temporary.replace(manifest)
    return manifest
