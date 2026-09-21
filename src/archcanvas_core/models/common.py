from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Base for protocol objects: no coercion and no undeclared fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_digest(value: bytes) -> str:
    return "sha256:" + sha256(value).hexdigest()


def source_snapshot_revision(file_revisions: dict[str, str]) -> str:
    return sha256_digest(canonical_json(dict(sorted(file_revisions.items()))))
