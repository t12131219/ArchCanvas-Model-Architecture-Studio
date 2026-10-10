"""Isolated authored model drafts; never a mutable source-bound CanvasDocument."""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from pathlib import Path

from archcanvas_authoring import validate_draft


MAX_DRAFT_BYTES = 16_000_000


class DraftConflict(ValueError):
    def __init__(self, revision: int):
        self.revision = revision
        super().__init__(f"Draft storage changed to revision {revision}; current edits were retained.")


class DraftStore:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def path(self, identity: str) -> Path:
        if not isinstance(identity, str) or not re.fullmatch(r"draft-[a-f0-9-]{1,80}", identity):
            raise ValueError("Unknown authored draft identity.")
        path = self.directory / f"{identity}.json"
        if path.is_symlink() or not path.resolve().is_relative_to(self.directory):
            raise ValueError("Draft path escapes its isolated directory.")
        return path

    def get(self, identity: str) -> dict | None:
        with self.lock:
            path = self.path(identity)
            if not path.exists():
                return None
            if path.stat().st_size > MAX_DRAFT_BYTES:
                raise ValueError("Saved draft exceeds its persistence budget.")
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError("Saved draft is unreadable; it was not overwritten.") from exc
            if not isinstance(value, dict) or set(value) != {"draft", "revision"} or type(value["revision"]) is not int or value["revision"] < 1:
                raise ValueError("Invalid saved draft envelope.")
            validate_draft(value["draft"])
            if value["draft"]["id"] != identity:
                raise ValueError("Saved draft identity mismatch.")
            return value

    def put(self, identity: str, draft: dict, expected_revision: int) -> dict:
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expectedRevision must be a non-negative storage revision.")
        validate_draft(draft)
        if draft["id"] != identity:
            raise ValueError("Draft identity mismatch.")
        with self.lock:
            current = self.get(identity)
            revision = current["revision"] if current else 0
            if revision != expected_revision:
                raise DraftConflict(revision)
            result = {"draft": draft, "revision": revision + 1}
            encoded = json.dumps(result, ensure_ascii=False, allow_nan=False).encode()
            if len(encoded) > MAX_DRAFT_BYTES:
                raise ValueError("Draft exceeds its persistence budget.")
            descriptor, temporary = tempfile.mkstemp(prefix=".draft-", dir=self.directory)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path(identity))
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            return result
