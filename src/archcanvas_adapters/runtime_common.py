from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any


def resolve_entrypoint(project: Path, entrypoint: str) -> Any:
    module_name, symbol_path = entrypoint.split(":", 1)
    sys.path.insert(0, str(project))
    value: Any = importlib.import_module(module_name)
    for segment in symbol_path.split("."):
        value = getattr(value, segment)
    return value


def constructor_kwargs(target: Any, request: dict[str, Any]) -> dict[str, Any]:
    signature = inspect.signature(target)
    configured = request.get("resolved_config", {})
    explicit = request["input_spec"].get("constructor_kwargs", {})
    candidates = {**configured, **explicit}
    return {
        name: value
        for name, value in candidates.items()
        if name in signature.parameters and name != "self"
    }


def digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(payload).hexdigest()


def matched_nodes(request: dict[str, Any], *subjects: str) -> list[str]:
    bindings = request.get("match_paths", {})
    result: list[str] = []
    for subject in subjects:
        result.extend(bindings.get(subject, []))
    return sorted(set(result))


def numpy_input(item: dict[str, Any], numpy: Any, seed: int) -> Any:
    dtype = numpy.dtype(item["dtype"])
    shape = tuple(item["shape"])
    generator = item["generator"]
    rng = numpy.random.default_rng(seed)
    if generator == "zeros":
        return numpy.zeros(shape, dtype=dtype)
    if generator == "ones":
        return numpy.ones(shape, dtype=dtype)
    if generator == "normal":
        return rng.normal(size=shape).astype(dtype)
    if generator == "uniform":
        return rng.uniform(size=shape).astype(dtype)
    return rng.integers(int(item["low"]), int(item["high"]), size=shape, dtype=dtype)


def flatten(value: Any, is_tensor: Any) -> list[Any]:
    if is_tensor(value):
        return [value]
    if isinstance(value, dict):
        return [tensor for item in value.values() for tensor in flatten(item, is_tensor)]
    if isinstance(value, (list, tuple)):
        return [tensor for item in value for tensor in flatten(item, is_tensor)]
    return []

