from __future__ import annotations

import hashlib
import json
from typing import Any

from archcanvas_core.models import (
    ArchitectureIR,
    EvidenceRecord,
    FactDelta,
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


def _digest(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _fact_changes(kind: str, before: dict[str, Any], after: dict[str, Any]) -> list[FactDelta]:
    changes: list[FactDelta] = []
    for subject_id in sorted(before.keys() | after.keys()):
        old = before.get(subject_id)
        new = after.get(subject_id)
        old_digest = _digest(old) if old is not None else None
        new_digest = _digest(new) if new is not None else None
        if old_digest != new_digest:
            changes.append(
                FactDelta(
                    subject_id=subject_id,
                    kind=kind,
                    before_sha256=old_digest,
                    after_sha256=new_digest,
                )
            )
    return changes


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
    before_fanouts = _by_id(before.fanouts, "relation_id")
    after_fanouts = _by_id(after.fanouts, "relation_id")
    before_predicates = _by_id(before.config_predicates, "predicate_id")
    after_predicates = _by_id(after.config_predicates, "predicate_id")
    before_ports = {
        port.port_id: port for node in before.nodes for port in [*node.input_ports, *node.output_ports]
    }
    after_ports = {
        port.port_id: port for node in after.nodes for port in [*node.input_ports, *node.output_ports]
    }

    parameter_changes: list[ParameterDelta] = []
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
    before_unresolved = {
        f"unresolved:{index}.{item.code.lower()}": item
        for index, item in enumerate(before.unresolved)
    }
    after_unresolved = {
        f"unresolved:{index}.{item.code.lower()}": item
        for index, item in enumerate(after.unresolved)
    }
    fact_changes = [
        *_fact_changes("node", before_nodes, after_nodes),
        *_fact_changes("edge", before_edges, after_edges),
        *_fact_changes("tensor", before_tensors, after_tensors),
        *_fact_changes("port", before_ports, after_ports),
        *_fact_changes("fanout", before_fanouts, after_fanouts),
        *_fact_changes("repeat", before_repeats, after_repeats),
        *_fact_changes("config-predicate", before_predicates, after_predicates),
        *_fact_changes("evidence", old_evidence, new_evidence),
        *_fact_changes("unresolved", before_unresolved, after_unresolved),
    ]

    return GraphDelta(
        added_nodes=sorted(after_nodes.keys() - before_nodes.keys()),
        removed_nodes=sorted(before_nodes.keys() - after_nodes.keys()),
        changed_nodes=_changed_ids(before_nodes, after_nodes),
        added_edges=sorted(after_edges.keys() - before_edges.keys()),
        removed_edges=sorted(before_edges.keys() - after_edges.keys()),
        changed_edges=_changed_ids(before_edges, after_edges),
        changed_parameters=parameter_changes,
        added_ports=sorted(after_ports.keys() - before_ports.keys()),
        removed_ports=sorted(before_ports.keys() - after_ports.keys()),
        changed_ports=_changed_ids(before_ports, after_ports),
        added_tensors=sorted(after_tensors.keys() - before_tensors.keys()),
        removed_tensors=sorted(before_tensors.keys() - after_tensors.keys()),
        changed_tensors=_changed_ids(before_tensors, after_tensors),
        changed_shapes=shape_changes,
        added_fanouts=sorted(after_fanouts.keys() - before_fanouts.keys()),
        removed_fanouts=sorted(before_fanouts.keys() - after_fanouts.keys()),
        changed_fanouts=_changed_ids(before_fanouts, after_fanouts),
        changed_repeats=sorted(
            (before_repeats.keys() ^ after_repeats.keys())
            | set(_changed_ids(before_repeats, after_repeats))
        ),
        added_config_predicates=sorted(
            after_predicates.keys() - before_predicates.keys()
        ),
        removed_config_predicates=sorted(
            before_predicates.keys() - after_predicates.keys()
        ),
        changed_config_predicates=_changed_ids(before_predicates, after_predicates),
        changed_sharing=sorted(changed_sharing),
        evidence_anchor_changes=sorted(set(evidence_changes)),
        unresolved_changes=(
            []
            if before.unresolved == after.unresolved
            else ["architecture.unresolved"]
        ),
        fact_changes=fact_changes,
    )
