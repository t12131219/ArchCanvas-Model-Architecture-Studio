from __future__ import annotations

from archcanvas_core.models.common import sha256_digest


def file_revision(raw_source: bytes) -> str:
    """Hash unnormalized source bytes, including the original line endings."""

    return sha256_digest(raw_source)
