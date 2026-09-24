from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from archcanvas_core.models import (
    AgentProposal,
    ArchitectureIR,
    EvidenceKind,
    EvidenceRecord,
    GraphDelta,
    ProposedConnection,
    SemanticStructuralPatch,
    SourceSnapshot,
)

from .transforms import (
    TransformResult,
    insert_keras_layer_norm,
    insert_layer_norm,
    replace_function_call,
    replace_module_constructor,
    set_functional_parameter,
    set_python_parameter,
)

ACTIVATION_OPERATORS = {"nn.GELU", "nn.ReLU", "nn.SiLU"}
TRANSFORM_REGISTRY: dict[str, dict[str, Any]] = {
    "replace_activation": {
        "version": "1.0",
        "target": "zero-argument nn.GELU/nn.ReLU/nn.SiLU module",
        "topology_change": False,
    },
    "insert_layer_norm": {
        "version": "1.0",
        "target": "single-consumer sequential module output",
        "topology_change": True,
    },
}


@dataclass(frozen=True)
class StructuralTransformResult:
    relative_path: Path
    transformed: TransformResult


def _source_records(node: Any, evidence: list[EvidenceRecord]) -> list[EvidenceRecord]:
    return [
        item
        for item in evidence
        if item.evidence_id in node.evidence_ids
        and item.kind is EvidenceKind.SOURCE
        and item.path is not None
        and item.span is not None
    ]


def _anchors(node: Any, evidence: list[EvidenceRecord]) -> tuple[EvidenceRecord, EvidenceRecord]:
    records = _source_records(node, evidence)
    definition = next((item for item in records if ".init." in item.evidence_id), None)
    flow = next(
        (
            item
            for item in records
            if ".forward." in item.evidence_id or ".call." in item.evidence_id
        ),
        None,
    )
    if definition is None or flow is None or definition.path != flow.path:
        raise ValueError("structural transform requires exact constructor and forward anchors")
    return definition, flow


def _validated_shape_expression(value: Any, snapshot: SourceSnapshot) -> str:
    if isinstance(value, int) and value > 0:
        return str(value)
    if (
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value)
        and isinstance(snapshot.resolved_config.get(value), int)
        and snapshot.resolved_config[value] > 0
    ):
        return value
    raise ValueError("normalized_shape must be a positive integer or a positive config symbol")


def _single_value_flow(
    source: bytes, class_name: str, variable: str, method_name: str = "forward"
) -> None:
    tree = ast.parse(source)
    class_node = next(
        (item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == class_name),
        None,
    )
    forward = next(
        (
            item
            for item in (class_node.body if class_node else [])
            if isinstance(item, ast.FunctionDef) and item.name == method_name
        ),
        None,
    )
    if forward is None:
        raise ValueError(f"{method_name} source anchor is unavailable")
    stores = [
        item
        for item in ast.walk(forward)
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store) and item.id == variable
    ]
    if len(stores) != 1:
        raise ValueError("insert_layer_norm requires a target value assigned exactly once")
    loads = [
        item
        for item in ast.walk(forward)
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load) and item.id == variable
    ]
    if len(loads) != 1:
        raise ValueError("insert_layer_norm requires a target value consumed exactly once")


def apply_structural_transform(
    request: SemanticStructuralPatch,
    architecture: ArchitectureIR,
    snapshot: SourceSnapshot,
    evidence: list[EvidenceRecord],
) -> StructuralTransformResult:
    project = Path(snapshot.project_root).resolve()
    node = next((item for item in architecture.nodes if item.node_id == request.target_node_id), None)
    if node is None:
        raise ValueError(f"structural target is not present in Exact IR: {request.target_node_id}")
    if architecture.framework == "jax":
        records = _source_records(node, evidence)
        flow = next(
            (
                item
                for item in records
                if ".call." in item.evidence_id
                or ".id-__call__." in item.evidence_id
                or (item.symbol or "").endswith(".__call__")
            ),
            None,
        )
        if flow is None:
            raise ValueError("JAX structural transform requires one exact call anchor")
        definition = flow
    else:
        definition, flow = _anchors(node, evidence)
    relative = Path(definition.path or "")
    source_path = (project / relative).resolve()
    if not source_path.is_relative_to(project) or not source_path.is_file():
        raise ValueError("structural source anchor escapes or is missing from the project")
    module_path = str(node.attributes.get("module_path", ""))
    module_name = module_path.removeprefix("self.") if module_path.startswith("self.") else ""
    source = source_path.read_bytes()
    if architecture.framework == "jax":
        if request.operation != "replace_activation":
            raise ValueError(f"{request.operation} has no registered JAX structural lowering")
        original = str(node.attributes.get("op_type", ""))
        if original not in {"nn.gelu", "nn.relu", "nn.silu"}:
            raise ValueError("JAX activation replacement requires an explicit Flax nn activation")
        replacement = f"nn.{str(request.parameters['replacement']).lower()}"
        target_name = str(node.attributes.get("assigned_symbol", ""))
        if not target_name:
            raise ValueError("JAX activation output has no exact assignment anchor")
        transformed = replace_function_call(
            source,
            target_name=target_name,
            original_operator=original,
            replacement_operator=replacement,
            expected_line=flow.span.start_line,  # type: ignore[union-attr]
        )
        return StructuralTransformResult(relative_path=relative, transformed=transformed)
    if architecture.framework == "keras":
        if request.operation == "insert_layer_norm":
            if not module_name or node.attributes.get("functional_anchor"):
                raise ValueError(
                    "Keras normalization insertion currently requires an exact subclass layer anchor"
                )
            outgoing = [edge for edge in architecture.edges if edge.producer_id == node.node_id]
            if len(outgoing) != 1:
                raise ValueError("Keras normalization insertion requires one downstream consumer")
            normalized_shape = request.parameters.get("normalized_shape")
            if not isinstance(normalized_shape, int) or normalized_shape <= 0:
                raise ValueError("Keras normalized_shape proof requires a positive integer")
            last_dimension = outgoing[0].symbolic_shape.removesuffix("]").split(",")[-1]
            if last_dimension.isdigit() and int(last_dimension) != normalized_shape:
                raise ValueError("Keras normalized_shape does not match the target tensor")
            new_module = request.parameters.get("module_name")
            if not isinstance(new_module, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", new_module):
                raise ValueError("Keras normalization module_name must be a lowercase identifier")
            assigned_symbol = str(node.attributes.get("assigned_symbol", ""))
            if not assigned_symbol:
                raise ValueError("Keras target output has no exact assigned symbol")
            _single_value_flow(
                source,
                snapshot.entrypoint.split(":", 1)[1],
                assigned_symbol,
                "call",
            )
            transformed = insert_keras_layer_norm(
                source,
                target_module=module_name,
                new_module=new_module,
                init_line=definition.span.start_line,  # type: ignore[union-attr]
                call_line=flow.span.start_line,  # type: ignore[union-attr]
            )
            return StructuralTransformResult(relative_path=relative, transformed=transformed)
        if node.attributes.get("op_type") != "layers.Activation":
            raise ValueError("Keras activation replacement requires layers.Activation")
        activation = next((item for item in node.parameters if item.name == "arg0"), None)
        if activation is None or activation.value not in {"gelu", "relu", "silu"}:
            raise ValueError("Keras activation must be an explicit gelu/relu/silu constructor value")
        replacement = str(request.parameters["replacement"]).lower()
        functional_anchor = node.attributes.get("functional_anchor")
        if isinstance(functional_anchor, str):
            transformed = set_functional_parameter(
                source,
                target_name=functional_anchor,
                parameter_name="arg0",
                source_expression=activation.source_expression,
                value=replacement,
                expected_line=definition.span.start_line,  # type: ignore[union-attr]
            )
        else:
            if not module_name:
                raise ValueError("Keras activation has no exact Functional or subclass anchor")
            transformed = set_python_parameter(
                source,
                module_name=module_name,
                parameter_name="arg0",
                source_expression=activation.source_expression,
                value=replacement,
                expected_line=definition.span.start_line,  # type: ignore[union-attr]
            )
        return StructuralTransformResult(relative_path=relative, transformed=transformed)
    if architecture.framework != "pytorch":
        raise ValueError(
            f"{request.operation} has no registered {architecture.framework} structural lowering"
        )
    if not module_name:
        raise ValueError("structural target is not a directly registered module")
    if request.operation == "replace_activation":
        original = str(node.attributes.get("op_type", ""))
        replacement_name = request.parameters.get("replacement")
        replacement = f"nn.{replacement_name}" if isinstance(replacement_name, str) else ""
        if original not in ACTIVATION_OPERATORS or replacement not in ACTIVATION_OPERATORS:
            raise ValueError("replace_activation supports GELU, ReLU, and SiLU module constructors")
        if original == replacement:
            raise ValueError("replacement activation is identical to the current activation")
        transformed = replace_module_constructor(
            source,
            module_name=module_name,
            original_operator=original,
            replacement_operator=replacement,
            expected_line=definition.span.start_line,  # type: ignore[union-attr]
        )
    elif request.operation == "insert_layer_norm":
        outgoing = [edge for edge in architecture.edges if edge.producer_id == node.node_id]
        if len(outgoing) != 1:
            raise ValueError("insert_layer_norm requires exactly one authored downstream consumer")
        new_module = request.parameters.get("module_name")
        if not isinstance(new_module, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", new_module):
            raise ValueError("LayerNorm module_name must be a lowercase Python identifier")
        if any(item.node_id == f"node:{new_module}" for item in architecture.nodes):
            raise ValueError("LayerNorm module_name already exists in Exact IR")
        normalized_shape = _validated_shape_expression(
            request.parameters.get("normalized_shape"), snapshot
        )
        assigned_symbol = str(node.attributes.get("assigned_symbol", ""))
        if not assigned_symbol:
            raise ValueError("target module output has no exact assigned symbol")
        class_name = snapshot.entrypoint.split(":", 1)[1]
        _single_value_flow(source, class_name, assigned_symbol)
        transformed = insert_layer_norm(
            source,
            target_module=module_name,
            new_module=new_module,
            normalized_shape=normalized_shape,
            init_line=definition.span.start_line,  # type: ignore[union-attr]
            forward_line=flow.span.start_line,  # type: ignore[union-attr]
        )
    else:  # pragma: no cover - model validation constrains the registry key
        raise ValueError(f"unsupported structural transform: {request.operation}")
    return StructuralTransformResult(relative_path=relative, transformed=transformed)


def validate_structural_oracle(
    request: SemanticStructuralPatch,
    before: ArchitectureIR,
    after: ArchitectureIR,
    delta: GraphDelta,
) -> None:
    if before.framework == "jax" and request.operation == "replace_activation":
        replacement = f"nn.{str(request.parameters['replacement']).lower()}"
        node = next(item for item in after.nodes if item.node_id == request.target_node_id)
        if node.attributes.get("op_type") != replacement:
            raise ValueError("JAX activation replacement is not reflected in Exact IR")
        allowed_changed_nodes = {request.target_node_id}
        if node.parent_id:
            allowed_changed_nodes.add(node.parent_id)
        forbidden = any(
            (
                delta.added_nodes,
                delta.removed_nodes,
                set(delta.changed_nodes) - allowed_changed_nodes,
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
                delta.changed_parameters,
                delta.added_fanouts,
                delta.removed_fanouts,
                delta.changed_fanouts,
                delta.changed_repeats,
                delta.added_config_predicates,
                delta.removed_config_predicates,
                delta.changed_config_predicates,
                delta.changed_sharing,
                delta.unresolved_changes,
            )
        )
        if forbidden:
            raise ValueError("JAX activation replacement changed facts outside its exact anchor")
        return
    if before.framework == "keras" and request.operation == "insert_layer_norm":
        new_node_id = f"node:{request.parameters['module_name']}"
        added_node = next((item for item in after.nodes if item.node_id == new_node_id), None)
        if added_node is None or added_node.attributes.get("op_type") != "layers.LayerNormalization":
            raise ValueError("Keras normalization node is missing from reanalyzed Exact IR")
        if added_node.attributes.get("module_path") != f"self.{request.parameters['module_name']}":
            raise ValueError("Keras normalization node has the wrong module binding")
        outgoing = [edge for edge in before.edges if edge.producer_id == request.target_node_id]
        if len(outgoing) != 1:
            raise ValueError("Keras normalization oracle requires one original outgoing edge")
        original = outgoing[0]
        added_edges = [edge for edge in after.edges if edge.edge_id in delta.added_edges]
        if (
            delta.added_nodes != [new_node_id]
            or delta.removed_nodes
            or delta.removed_edges != [original.edge_id]
            or {(edge.producer_id, edge.consumer_id) for edge in added_edges}
            != {
                (request.target_node_id, new_node_id),
                (new_node_id, original.consumer_id),
            }
            or delta.removed_tensors
            or delta.changed_shapes
            or delta.changed_parameters
        ):
            raise ValueError("Keras normalization insertion produced an unexpected Graph Delta")
        produced = [tensor for tensor in after.tensors if tensor.producer_id == new_node_id]
        if len(produced) != 1 or delta.added_tensors != [produced[0].tensor_id]:
            raise ValueError("Keras normalization insertion must add one normalized tensor")
        return
    if before.framework == "keras" and request.operation == "replace_activation":
        replacement = str(request.parameters["replacement"]).lower()
        node = next(item for item in after.nodes if item.node_id == request.target_node_id)
        activation = next((item for item in node.parameters if item.name == "arg0"), None)
        if activation is None or activation.value != replacement:
            raise ValueError("Keras activation replacement is not reflected in Exact IR")
        allowed_changed_nodes = {request.target_node_id}
        if node.parent_id:
            allowed_changed_nodes.add(node.parent_id)
        forbidden = any(
            (
                delta.added_nodes,
                delta.removed_nodes,
                set(delta.changed_nodes) - allowed_changed_nodes,
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
            )
        )
        changes = [
            item
            for item in delta.changed_parameters
            if item.node_id == request.target_node_id and item.parameter_name == "arg0"
        ]
        if forbidden or len(delta.changed_parameters) != 1 or len(changes) != 1:
            raise ValueError("Keras activation replacement must change exactly one parameter fact")
        return
    forbidden_common = any(
        (
            delta.changed_parameters,
            delta.added_fanouts,
            delta.removed_fanouts,
            delta.changed_repeats,
            delta.added_config_predicates,
            delta.removed_config_predicates,
            delta.changed_sharing,
            delta.unresolved_changes,
        )
    )
    if forbidden_common:
        raise ValueError(
            "structural transform changed parameters, fanouts, predicates, repeats, sharing, "
            "or unresolved facts"
        )
    for field, identifier, changed_ids in (
        ("fanouts", "relation_id", delta.changed_fanouts),
        ("config_predicates", "predicate_id", delta.changed_config_predicates),
    ):
        old_items = {getattr(item, identifier): item for item in getattr(before, field)}
        new_items = {getattr(item, identifier): item for item in getattr(after, field)}
        if any(
            _without_evidence(old_items[item_id]) != _without_evidence(new_items[item_id])
            for item_id in changed_ids
        ):
            raise ValueError(f"structural transform changed existing {field} semantics")
    if request.operation == "replace_activation":
        replacement = f"nn.{request.parameters['replacement']}"
        changed = next(item for item in after.nodes if item.node_id == request.target_node_id)
        if changed.attributes.get("op_type") != replacement:
            raise ValueError("replacement activation is not reflected in Exact IR")
        if any(
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
            )
        ) or delta.changed_nodes != [request.target_node_id]:
            raise ValueError("replace_activation must change exactly one node fact and no topology")
        return

    new_node_id = f"node:{request.parameters['module_name']}"
    if delta.added_nodes != [new_node_id] or delta.removed_nodes:
        raise ValueError("insert_layer_norm must add exactly its declared canonical node")
    added_node = next(item for item in after.nodes if item.node_id == new_node_id)
    if added_node.attributes.get("op_type") != "nn.LayerNorm":
        raise ValueError("inserted canonical node is not the declared LayerNorm")
    expected_shape = request.parameters["normalized_shape"]
    shape_parameter = next(
        (item for item in added_node.parameters if item.name == "normalized_shape"), None
    )
    if (
        added_node.attributes.get("module_path")
        != f"self.{request.parameters['module_name']}"
        or shape_parameter is None
        or shape_parameter.source_expression != str(expected_shape)
    ):
        raise ValueError("inserted LayerNorm constructor does not match the declared parameters")
    outgoing = [edge for edge in before.edges if edge.producer_id == request.target_node_id]
    if len(outgoing) != 1:
        raise ValueError("insert_layer_norm oracle requires one original outgoing edge")
    original_edge = outgoing[0]
    expected_added_endpoints = {
        (request.target_node_id, new_node_id),
        (new_node_id, original_edge.consumer_id),
    }
    actual_added = [edge for edge in after.edges if edge.edge_id in delta.added_edges]
    if (
        delta.removed_edges != [original_edge.edge_id]
        or {(edge.producer_id, edge.consumer_id) for edge in actual_added}
        != expected_added_endpoints
    ):
        raise ValueError("insert_layer_norm edge delta does not match the sequential insertion oracle")
    for edge_id in delta.changed_edges:
        old_edge = next(item for item in before.edges if item.edge_id == edge_id)
        new_edge = next(item for item in after.edges if item.edge_id == edge_id)
        if _without_evidence(old_edge) != _without_evidence(new_edge):
            raise ValueError("insert_layer_norm changed an unrelated authored edge")
    produced = [tensor for tensor in after.tensors if tensor.producer_id == new_node_id]
    if len(produced) != 1 or delta.added_tensors != [produced[0].tensor_id]:
        raise ValueError("insert_layer_norm must add exactly one tensor produced by the new node")
    if delta.removed_tensors or delta.changed_shapes:
        raise ValueError("insert_layer_norm cannot remove tensors or change known shapes")
    new_port_ids = sorted(
        port.port_id for port in [*added_node.input_ports, *added_node.output_ports]
    )
    if delta.added_ports != new_port_ids or delta.removed_ports:
        raise ValueError("insert_layer_norm port delta does not match the inserted node")
    if delta.changed_ports != [original_edge.consumer_port]:
        raise ValueError("insert_layer_norm must retarget exactly the original consumer port")

    produced_tensor = produced[0]
    if (
        produced_tensor.symbolic_shape != original_edge.symbolic_shape
        or produced_tensor.semantic_axes != original_edge.semantic_axes
    ):
        raise ValueError("insert_layer_norm must preserve the original tensor shape and axes")
    added_by_endpoints = {
        (edge.producer_id, edge.consumer_id): edge for edge in actual_added
    }
    first = added_by_endpoints[(request.target_node_id, new_node_id)]
    second = added_by_endpoints[(new_node_id, original_edge.consumer_id)]
    if (
        first.tensor_id != original_edge.tensor_id
        or first.producer_port != original_edge.producer_port
        or first.consumer_port not in new_port_ids
        or second.tensor_id != produced_tensor.tensor_id
        or second.producer_port not in new_port_ids
        or second.consumer_port != original_edge.consumer_port
        or first.symbolic_shape != original_edge.symbolic_shape
        or second.symbolic_shape != original_edge.symbolic_shape
    ):
        raise ValueError("insert_layer_norm did not preserve the exact sequential tensor route")

    before_nodes = {item.node_id: item for item in before.nodes}
    after_nodes = {item.node_id: item for item in after.nodes}
    consumer_id = original_edge.consumer_id
    parent_id = added_node.parent_id
    for node_id in before_nodes.keys() & after_nodes.keys():
        old_node = _without_evidence(before_nodes[node_id])
        new_node = _without_evidence(after_nodes[node_id])
        if node_id == parent_id:
            old_children = list(old_node["children"])
            target_index = old_children.index(request.target_node_id)
            old_children.insert(target_index + 1, new_node_id)
            old_node["children"] = old_children
        elif node_id == consumer_id:
            old_port = next(
                item for item in old_node["input_ports"] if item["port_id"] == original_edge.consumer_port
            )
            new_port = next(
                item for item in new_node["input_ports"] if item["port_id"] == original_edge.consumer_port
            )
            old_port["name"] = new_port["name"]
            old_port["role"] = new_port["role"]
            old_node["attributes"]["source_expression"] = new_node["attributes"][
                "source_expression"
            ]
        if old_node != new_node:
            raise ValueError(f"insert_layer_norm changed unrelated node semantics: {node_id}")

    before_tensors = {item.tensor_id: item for item in before.tensors}
    after_tensors = {item.tensor_id: item for item in after.tensors}
    for tensor_id in before_tensors.keys() & after_tensors.keys():
        old_tensor = _without_evidence(before_tensors[tensor_id])
        new_tensor = _without_evidence(after_tensors[tensor_id])
        if tensor_id == original_edge.tensor_id:
            old_tensor["consumer_ids"] = [
                new_node_id if item == consumer_id else item
                for item in old_tensor["consumer_ids"]
            ]
        if old_tensor != new_tensor:
            raise ValueError(f"insert_layer_norm changed an existing tensor: {tensor_id}")


def _without_evidence(value: Any) -> Any:
    data = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    if isinstance(data, dict):
        return {
            key: _without_evidence(item)
            for key, item in data.items()
            if key != "evidence_ids"
        }
    if isinstance(data, list):
        return [_without_evidence(item) for item in data]
    return data


def plan_connection(request: ProposedConnection, architecture: ArchitectureIR) -> AgentProposal:
    source = next((item for item in architecture.nodes if item.node_id == request.source_node_id), None)
    target = next((item for item in architecture.nodes if item.node_id == request.target_node_id), None)
    if source is None or target is None:
        raise ValueError("proposed connection references an unknown canonical node")
    source_port = next(
        (item for item in source.output_ports if item.port_id == request.source_port_id), None
    )
    target_port = next(
        (item for item in target.input_ports if item.port_id == request.target_port_id), None
    )
    if source_port is None or target_port is None:
        reason = "INCOMPATIBLE_PORTS"
        summary = "The proposal does not connect an authored output port to an authored input port."
        compatibility = "incompatible"
    else:
        source_shapes = {
            item.symbolic_shape
            for item in architecture.tensors
            if item.producer_id == source.node_id and item.producer_port == source_port.port_id
        }
        target_shapes = {
            item.symbolic_shape
            for item in architecture.edges
            if item.consumer_id == target.node_id and item.consumer_port == target_port.port_id
        }
        if not source_shapes or not target_shapes or "[?]" in source_shapes | target_shapes:
            reason = "UNRESOLVED_TENSOR_COMPATIBILITY"
            compatibility = "unresolved"
            summary = "Tensor compatibility cannot be proven from the current Exact IR."
        elif source_shapes.isdisjoint(target_shapes):
            reason = "INCOMPATIBLE_PORTS"
            compatibility = "incompatible"
            summary = "The authored source and target tensor shapes are incompatible."
        else:
            reason = "UNSUPPORTED_CONNECTION_TRANSFORM"
            compatibility = "compatible"
            summary = (
                "Port compatibility is plausible, but arbitrary connection rewrites are outside the "
                "trusted transform registry."
            )
    return AgentProposal(
        proposal_id=request.proposal_id,
        reason_code=reason,
        summary=summary,
        requested_intent=request.model_dump(mode="json"),
        source_context={
            "architecture_id": architecture.architecture_id,
            "source_node_id": request.source_node_id,
            "source_port_id": request.source_port_id,
            "target_node_id": request.target_node_id,
            "target_port_id": request.target_port_id,
            "compatibility": compatibility,
            "registry_match": None,
        },
    )


def unsupported_intent_proposal(payload: dict[str, Any]) -> AgentProposal:
    proposal_id = payload.get("proposal_id")
    description = payload.get("description")
    if not isinstance(proposal_id, str) or not isinstance(description, str) or not description:
        raise ValueError("unsupported intent requires proposal_id and description")
    return AgentProposal(
        proposal_id=proposal_id,
        reason_code="UNSUPPORTED_STRUCTURAL_INTENT",
        summary="The requested structural intent has no trusted transform and requires Agent review.",
        requested_intent=payload,
        source_context={"registry_match": None},
    )
