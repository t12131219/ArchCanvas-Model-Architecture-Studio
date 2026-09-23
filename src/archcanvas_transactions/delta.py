from __future__ import annotations

from typing import Any

from archcanvas_core.models import (
    ArchitectureIR,
    EvidenceRecord,
    GraphDelta,
    ParameterDelta,
    ShapeDelta,
)


def _by_id(items: list[Any], field: str) -> dict[str, Any]:
    return {getattr(item, field): item for item in items}


def _changed_ids(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    return sorted(
        key
        for key in before.keys() & after.keys()
        if before[key].model_dump(mode="json") != after[key].model_dump(mode="json")
    )


def graph_delta(
    before: ArchitectureIR,
    after: ArchitectureIR,
    before_evidence: list[EvidenceRecord] | None = None,
    after_evidence: list[EvidenceRecord] | None = None,
) -> GraphDelta:
    before_nodes = _by_id(before.nodes, "node_id")
    after_nodes = _by_id(after.nodes, "node_id")
    before_edges = _by_id(before.edges, "edge_id")
    after_edges = _by_id(after.edges, "edge_id")
    before_tensors = _by_id(before.tensors, "tensor_id")
    after_tensors = _by_id(after.tensors, "tensor_id")
    before_repeats = _by_id(before.repeats, "repeat_id")
    after_repeats = _by_id(after.repeats, "repeat_id")

    parameter_changes: list[ParameterDelta] = []
    changed_ports: set[str] = set()
    changed_sharing: set[str] = set()
    for node_id in sorted(before_nodes.keys() & after_nodes.keys()):
        old_node, new_node = before_nodes[node_id], after_nodes[node_id]
        old_parameters = {item.name: item for item in old_node.parameters}
        new_parameters = {item.name: item for item in new_node.parameters}
        for name in sorted(old_parameters.keys() & new_parameters.keys()):
            old_parameter, new_parameter = old_parameters[name], new_parameters[name]
            if old_parameter.value != new_parameter.value:
                parameter_changes.append(
                    ParameterDelta(
                        node_id=node_id,
                        parameter_name=name,
                        before=old_parameter.value,
                        after=new_parameter.value,
                        source_expression=new_parameter.source_expression,
                    )
                )
        old_ports = {
            item.port_id: item for item in [*old_node.input_ports, *old_node.output_ports]
        }
        new_ports = {
            item.port_id: item for item in [*new_node.input_ports, *new_node.output_ports]
        }
        changed_ports.update(old_ports.keys() ^ new_ports.keys())
        changed_ports.update(_changed_ids(old_ports, new_ports))
        if old_node.parameter_identity != new_node.parameter_identity:
            changed_sharing.add(node_id)

    shape_changes: list[ShapeDelta] = []
    for old_items, new_items in ((before_tensors, after_tensors), (before_edges, after_edges)):
        for subject_id in sorted(old_items.keys() & new_items.keys()):
            old_shape = old_items[subject_id].symbolic_shape
            new_shape = new_items[subject_id].symbolic_shape
            if old_shape != new_shape:
                shape_changes.append(
                    ShapeDelta(subject_id=subject_id, before=old_shape, after=new_shape)
                )

    old_evidence = _by_id(before_evidence or [], "evidence_id")
    new_evidence = _by_id(after_evidence or [], "evidence_id")
    evidence_changes = sorted(old_evidence.keys() ^ new_evidence.keys())
    evidence_changes.extend(_changed_ids(old_evidence, new_evidence))

    return GraphDelta(
        added_nodes=sorted(after_nodes.keys() - before_nodes.keys()),
        removed_nodes=sorted(before_nodes.keys() - after_nodes.keys()),
        changed_nodes=_changed_ids(before_nodes, after_nodes),
        added_edges=sorted(after_edges.keys() - before_edges.keys()),
        removed_edges=sorted(before_edges.keys() - after_edges.keys()),
        changed_edges=_changed_ids(before_edges, after_edges),
        changed_parameters=parameter_changes,
        changed_ports=sorted(changed_ports),
        changed_tensors=_changed_ids(before_tensors, after_tensors),
        changed_shapes=shape_changes,
        changed_repeats=sorted(
            (before_repeats.keys() ^ after_repeats.keys())
            | set(_changed_ids(before_repeats, after_repeats))
        ),
        changed_sharing=sorted(changed_sharing),
        evidence_anchor_changes=sorted(set(evidence_changes)),
        unresolved_changes=(
            []
            if before.unresolved == after.unresolved
            else ["architecture.unresolved"]
        ),
    )
