from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any

from pydantic import BaseModel

MAX_SAFE_INTEGER = 2**53 - 1


class CanonicalizationError(ValueError):
    """Raised when a value cannot be represented identically across runtimes."""


def _utf16_sort_key(value: str) -> bytes:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise CanonicalizationError("canonical strings cannot contain lone surrogates") from error
    return value.encode("utf-16be")


def _canonical_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _canonical_value(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return _canonical_value(value.value)
    if value is None or isinstance(value, (str, bool)):
        if isinstance(value, str):
            _utf16_sort_key(value)
        return value
    if isinstance(value, int):
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise CanonicalizationError("integers must fit the cross-runtime safe range")
        return value
    if isinstance(value, float):
        raise CanonicalizationError(
            "floating-point values require an explicit string representation"
        )
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise CanonicalizationError("canonical object keys must be strings")
        return {
            key: _canonical_value(value[key])
            for key in sorted(value, key=_utf16_sort_key)
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_canonical_value(item) for item in value]
    raise CanonicalizationError(f"unsupported canonical value: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize the I-JSON subset used by v2 protocols with JCS key ordering."""
    normalized = _canonical_value(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def domain_digest(domain: str, value: Any) -> str:
    if not domain or "\x00" in domain:
        raise ValueError("digest domain must be non-empty and cannot contain NUL")
    payload = domain.encode("ascii") + b"\x00" + canonical_json_bytes(value)
    return hashlib.sha256(payload).hexdigest()
