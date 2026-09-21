"""Versioned newline-delimited JSON transport for local Engine sidecars.

The transport only decodes typed Engine request envelopes and delegates to ``ArchCanvasEngine``.
It never receives a desktop filesystem capability or performs source writes itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from pydantic import ValidationError

from archcanvas_core.models.engine import EngineError, EngineRequest, EngineResponse

from .service import ArchCanvasEngine

_MAX_REQUEST_BYTES = 1_000_000


def _rejection(request_id: str, code: str, message: str) -> EngineResponse:
    return EngineResponse(
        request_id=request_id,
        status="rejected",
        error=EngineError(code=code, message=message),
    )


def _request_id(payload: Any) -> str:
    if isinstance(payload, dict) and isinstance(payload.get("request_id"), str):
        candidate = payload["request_id"]
        if candidate.startswith("engine-request:"):
            return candidate
    return "engine-request:invalid"


def dispatch_line(engine: ArchCanvasEngine, line: str) -> EngineResponse:
    """Decode one bounded JSON request and return a typed response for the same line."""

    if len(line.encode("utf-8")) > _MAX_REQUEST_BYTES:
        return _rejection("engine-request:invalid", "REQUEST_TOO_LARGE", "request exceeds byte limit")
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return _rejection("engine-request:invalid", "INVALID_ENGINE_REQUEST", "request is not valid JSON")
    request_id = _request_id(payload)
    try:
        # JSON validation preserves protocol wire semantics for strict enum fields.
        request = EngineRequest.model_validate_json(line)
    except ValidationError:
        return _rejection(request_id, "INVALID_ENGINE_REQUEST", "request does not match EngineRequest v1")
    return engine.dispatch(request)


def serve(engine: ArchCanvasEngine, input_stream: TextIO, output_stream: TextIO) -> None:
    """Serve independent JSONL requests without emitting diagnostic bytes to stdout."""

    for line in input_stream:
        response = dispatch_line(engine, line.rstrip("\n"))
        output_stream.write(response.model_dump_json() + "\n")
        output_stream.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="ArchCanvas Engine JSONL sidecar")
    parser.add_argument("--cache-root", required=True, type=Path)
    arguments = parser.parse_args()
    serve(ArchCanvasEngine(arguments.cache_root), sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
