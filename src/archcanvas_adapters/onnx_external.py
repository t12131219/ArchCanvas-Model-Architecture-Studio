from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path, PureWindowsPath
from typing import Any

from archcanvas_core.models import ArtifactEntry, ArtifactSet


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _tensors_in_graph(graph: Any) -> Iterable[Any]:
    yield from graph.initializer
    for sparse in graph.sparse_initializer:
        yield sparse.values
        yield sparse.indices
    for node in graph.node:
        for attribute in node.attribute:
            if attribute.HasField("t"):
                yield attribute.t
            yield from attribute.tensors
            if attribute.HasField("g"):
                yield from _tensors_in_graph(attribute.g)
            for nested in attribute.graphs:
                yield from _tensors_in_graph(nested)


def external_location(tensor: Any) -> str | None:
    values = {item.key: item.value for item in tensor.external_data}
    return values.get("location")


def external_data_paths(model: Any, model_path: Path, root: Path) -> list[Path]:
    import onnx

    model_path = model_path.resolve()
    root = root.resolve()
    paths: set[Path] = set()
    for tensor in _tensors_in_graph(model.graph):
        if tensor.data_location != onnx.TensorProto.EXTERNAL:
            continue
        location = external_location(tensor)
        if not location:
            raise ValueError(f"ONNX external tensor has no location: {tensor.name or '<unnamed>'}")
        normalized = location.replace("\\", "/")
        logical = Path(normalized)
        if (
            logical.is_absolute()
            or PureWindowsPath(location).is_absolute()
            or ".." in logical.parts
            or "\x00" in location
        ):
            raise ValueError(f"ONNX external-data location is not confined: {location}")
        resolved = (model_path.parent / logical).resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise ValueError(f"ONNX external-data file is unavailable or outside the project: {location}")
        paths.add(resolved.relative_to(root))
    return sorted(paths, key=lambda item: item.as_posix())


def build_artifact_set(model: Any, model_path: Path, root: Path) -> ArtifactSet:
    model_path = model_path.resolve()
    root = root.resolve()
    model_relative = model_path.relative_to(root)
    entries = [
        ArtifactEntry(
            logical_path=model_relative.as_posix(),
            size=model_path.stat().st_size,
            sha256=_sha256(model_path.read_bytes()),
            role="model",
        )
    ]
    entries.extend(
        ArtifactEntry(
            logical_path=relative.as_posix(),
            size=(root / relative).stat().st_size,
            sha256=_sha256((root / relative).read_bytes()),
            role="external-data",
        )
        for relative in external_data_paths(model, model_path, root)
    )
    payload = [entry.model_dump(mode="json") for entry in entries]
    set_digest = _sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    return ArtifactSet(
        artifact_set_id=f"artifact-set:{set_digest[:16]}",
        root=str(root),
        set_digest=set_digest,
        entries=entries,
    )
