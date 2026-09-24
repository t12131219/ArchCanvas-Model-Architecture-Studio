from __future__ import annotations

import json
import math
import numbers
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from archcanvas_core.models import (
    ArchitectureIR,
    GraphDelta,
    SemanticParameterPatch,
    SemanticStructuralPatch,
    SourceSnapshot,
)

from .onnx_external import build_artifact_set, external_location


@dataclass(frozen=True)
class ModelTransformedFile:
    relative_path: Path
    content: bytes
    kind: str


@dataclass(frozen=True)
class ModelTransformResult:
    relative_path: Path
    content: bytes
    semantic_manifest: str
    anchor_line: int = 1
    additional_files: tuple[ModelTransformedFile, ...] = ()


def validate_artifact(path: Path) -> None:
    import onnx

    model = onnx.load(path, load_external_data=True)
    onnx.checker.check_model(model, full_check=False)
    onnx.shape_inference.infer_shapes(model)


def apply_transaction(
    request: SemanticParameterPatch | SemanticStructuralPatch,
    architecture: ArchitectureIR,
    snapshot: SourceSnapshot,
) -> ModelTransformResult:
    import numpy as np
    import onnx

    project = Path(snapshot.project_root).resolve()
    relative = Path(snapshot.source_files[0].path)
    model_path = (project / relative).resolve()
    stored_model = onnx.load(model_path, load_external_data=False)
    artifact_set = build_artifact_set(stored_model, model_path, project)
    model = onnx.load(model_path, load_external_data=True)
    external_contents = {
        Path(entry.logical_path): bytearray((project / entry.logical_path).read_bytes())
        for entry in artifact_set.entries
        if entry.role == "external-data"
    }
    target = next(
        (item for item in architecture.nodes if item.node_id == request.target_node_id), None
    )
    if target is None:
        raise ValueError(f"ONNX transaction target is absent: {request.target_node_id}")
    manifest: dict[str, Any] = {
        "framework": "onnx",
        "target_node_id": request.target_node_id,
        "operation": request.operation,
        "artifact_set_id": artifact_set.artifact_set_id,
        "artifact_set_digest_before": artifact_set.set_digest,
        "artifact_members": [entry.logical_path for entry in artifact_set.entries],
        "atomicity": "service-contract-with-rollback",
    }
    if isinstance(request, SemanticParameterPatch):
        if target.attributes.get("onnx_initializer"):
            if request.parameter_name != "value":
                raise ValueError("ONNX initializer transactions support only the value parameter")
            name = str(target.attributes.get("onnx_value", target.semantic_name))
            initializer = next((item for item in model.graph.initializer if item.name == name), None)
            stored_initializer = next(
                (item for item in stored_model.graph.initializer if item.name == name), None
            )
            if initializer is None or stored_initializer is None:
                raise ValueError(f"ONNX initializer not found: {name}")
            before = onnx.numpy_helper.to_array(initializer)
            after = np.asarray(request.new_value, dtype=before.dtype)
            if after.shape != before.shape:
                raise ValueError(
                    f"ONNX initializer shape is immutable in set_parameter: {before.shape} != {after.shape}"
                )
            replacement = onnx.numpy_helper.from_array(after, name=name)
            initializer.CopyFrom(replacement)
            if stored_initializer.data_location == onnx.TensorProto.EXTERNAL:
                location = external_location(stored_initializer)
                if location is None:
                    raise ValueError(f"ONNX external initializer has no location: {name}")
                fields = {item.key: item.value for item in stored_initializer.external_data}
                offset = int(fields.get("offset", "0"))
                payload = replacement.raw_data
                length = int(fields.get("length", str(len(payload))))
                relative_external = (model_path.parent / location).resolve().relative_to(project)
                target_content = external_contents[relative_external]
                if len(payload) != before.nbytes or length != len(payload):
                    raise ValueError(
                        "ONNX external initializer transaction must preserve the byte extent"
                    )
                if offset < 0 or offset + length > len(target_content):
                    raise ValueError("ONNX external initializer extent is outside its data file")
                target_content[offset : offset + length] = payload
                manifest["external_data_path"] = relative_external.as_posix()
            else:
                stored_initializer.CopyFrom(replacement)
            manifest.update(
                {
                    "kind": "initializer",
                    "name": name,
                    "dtype": str(before.dtype),
                    "shape": list(before.shape),
                }
            )
        else:
            index = target.attributes.get("node_index")
            if not isinstance(index, int) or index >= len(model.graph.node):
                raise ValueError("ONNX node has no stable ModelProto index")
            node = model.graph.node[index]
            stored_node = stored_model.graph.node[index]
            attribute_index = next(
                (
                    position
                    for position, item in enumerate(node.attribute)
                    if item.name == request.parameter_name
                ),
                None,
            )
            if attribute_index is None:
                raise ValueError(
                    f"ONNX attribute is not present on the target node: {request.parameter_name}"
                )
            original_type = node.attribute[attribute_index].type
            replacement = onnx.helper.make_attribute(request.parameter_name, request.new_value)
            if replacement.type != original_type:
                raise ValueError("ONNX attribute replacement must preserve the AttributeProto type")
            node.attribute[attribute_index].CopyFrom(replacement)
            stored_attribute_index = next(
                position
                for position, item in enumerate(stored_node.attribute)
                if item.name == request.parameter_name
            )
            stored_node.attribute[stored_attribute_index].CopyFrom(replacement)
            manifest.update(
                {
                    "kind": "attribute",
                    "node_index": index,
                    "name": request.parameter_name,
                    "attribute_type": int(original_type),
                }
            )
    else:
        if request.operation != "replace_activation":
            raise ValueError(f"{request.operation} has no registered ONNX node lowering")
        index = target.attributes.get("node_index")
        if not isinstance(index, int) or index >= len(model.graph.node):
            raise ValueError("ONNX node has no stable ModelProto index")
        node = model.graph.node[index]
        stored_node = stored_model.graph.node[index]
        allowed = {"Relu", "Gelu", "Silu"}
        replacement = {"ReLU": "Relu", "GELU": "Gelu", "SiLU": "Silu"}[
            str(request.parameters["replacement"])
        ]
        if node.op_type not in allowed or node.domain not in {"", "ai.onnx"}:
            raise ValueError("ONNX activation replacement requires a standard activation node")
        if node.op_type == replacement:
            raise ValueError("ONNX replacement activation is identical to the current node")
        manifest.update(
            {
                "kind": "node-op",
                "node_index": index,
                "before": node.op_type,
                "after": replacement,
            }
        )
        node.op_type = replacement
        stored_node.op_type = replacement
    onnx.checker.check_model(model, full_check=False)
    onnx.shape_inference.infer_shapes(model)
    return ModelTransformResult(
        relative_path=relative,
        content=stored_model.SerializeToString(),
        semantic_manifest=json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        additional_files=tuple(
            ModelTransformedFile(
                relative_path=path,
                content=bytes(content),
                kind="binary",
            )
            for path, content in sorted(
                external_contents.items(), key=lambda item: item[0].as_posix()
            )
        ),
    )


def validate_delta(
    request: SemanticParameterPatch | SemanticStructuralPatch,
    before: ArchitectureIR,
    after: ArchitectureIR,
    delta: GraphDelta,
) -> None:
    node = next(item for item in after.nodes if item.node_id == request.target_node_id)
    allowed_changed_nodes = {request.target_node_id}
    if node.parent_id:
        allowed_changed_nodes.add(node.parent_id)
    topology_changed = any(
        (
            delta.added_nodes,
            delta.removed_nodes,
            delta.added_edges,
            delta.removed_edges,
            delta.changed_edges,
            delta.added_ports,
            delta.removed_ports,
            delta.changed_ports,
            delta.added_tensors,
            delta.removed_tensors,
            delta.changed_tensors,
            delta.changed_shapes,
            delta.added_fanouts,
            delta.removed_fanouts,
            delta.changed_fanouts,
            delta.changed_repeats,
            delta.added_config_predicates,
            delta.removed_config_predicates,
            delta.changed_config_predicates,
            delta.changed_sharing,
            delta.unresolved_changes,
            set(delta.changed_nodes) - allowed_changed_nodes,
        )
    )
    if topology_changed:
        raise ValueError("ONNX transaction changed facts outside the selected ModelProto field")
    if isinstance(request, SemanticParameterPatch):
        def same_value(actual: Any, expected: Any) -> bool:
            if isinstance(actual, numbers.Real) and isinstance(expected, numbers.Real):
                return math.isclose(float(actual), float(expected), rel_tol=1e-6, abs_tol=1e-7)
            if isinstance(actual, list) and isinstance(expected, list):
                return len(actual) == len(expected) and all(
                    same_value(left, right) for left, right in zip(actual, expected, strict=True)
                )
            return actual == expected

        changes = [
            item
            for item in delta.changed_parameters
            if item.node_id == request.target_node_id
            and item.parameter_name == request.parameter_name
            and same_value(item.after, request.new_value)
        ]
        if len(changes) != 1 or len(delta.changed_parameters) != 1:
            raise ValueError("ONNX parameter transaction must change exactly one parameter fact")
        return
    replacement = {"ReLU": "Relu", "GELU": "Gelu", "SiLU": "Silu"}[
        str(request.parameters["replacement"])
    ]
    if node.attributes.get("op_type") != replacement or delta.changed_parameters:
        raise ValueError("ONNX node replacement did not produce the declared semantic delta")
