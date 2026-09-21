from __future__ import annotations

from .models.architecture import ArchitectureIR
from .models.source_identity import SourceIdentityDocument


def validate_architecture_semantics(
    ir: ArchitectureIR, source_index: SourceIdentityDocument
) -> list[str]:
    """Return deterministic protocol errors that JSON Schema cannot express."""

    errors: list[str] = []
    if ir.project_id != source_index.project_id:
        errors.append("PROJECT_ID_MISMATCH")
    if ir.source_revision != source_index.source_revision:
        errors.append("SOURCE_REVISION_MISMATCH")
    nodes = {node.node_id: node for node in ir.nodes}
    anchors = {anchor.anchor_id for anchor in source_index.anchors}
    identities = {identity.identity_id for identity in source_index.identities}
    if len(nodes) != len(ir.nodes):
        errors.append("DUPLICATE_NODE_ID")
    if len({edge.edge_id for edge in ir.edges}) != len(ir.edges):
        errors.append("DUPLICATE_EDGE_ID")
    if len({repeat.repeat_id for repeat in ir.repeats}) != len(ir.repeats):
        errors.append("DUPLICATE_REPEAT_ID")

    for node in ir.nodes:
        if node.identity_id not in identities:
            errors.append(f"UNKNOWN_IDENTITY:{node.node_id}:{node.identity_id}")
        if node.parent_id is not None and node.parent_id not in nodes:
            errors.append(f"UNKNOWN_PARENT:{node.node_id}:{node.parent_id}")
        for anchor_id in node.source_anchor_ids:
            if anchor_id not in anchors:
                errors.append(f"UNKNOWN_ANCHOR:{node.node_id}:{anchor_id}")
        for parameter in node.parameters:
            for anchor_id in parameter.origin.anchor_ids:
                if anchor_id not in anchors:
                    errors.append(f"UNKNOWN_PARAMETER_ANCHOR:{node.node_id}:{parameter.name}:{anchor_id}")

    for edge in ir.edges:
        source, target = nodes.get(edge.source_node_id), nodes.get(edge.target_node_id)
        if source is None:
            errors.append(f"UNKNOWN_EDGE_SOURCE:{edge.edge_id}")
        if target is None:
            errors.append(f"UNKNOWN_EDGE_TARGET:{edge.edge_id}")
        if (
            source is not None
            and edge.source_port_id is not None
            and edge.source_port_id not in {port.port_id for port in source.output_ports}
        ):
            errors.append(f"UNKNOWN_SOURCE_PORT:{edge.edge_id}")
        if (
            target is not None
            and edge.target_port_id is not None
            and edge.target_port_id not in {port.port_id for port in target.input_ports}
        ):
            errors.append(f"UNKNOWN_TARGET_PORT:{edge.edge_id}")

    for repeat in ir.repeats:
        for node_id in repeat.member_node_ids:
            if node_id not in nodes:
                errors.append(f"UNKNOWN_REPEAT_MEMBER:{repeat.repeat_id}:{node_id}")
        for anchor_id in repeat.source_anchor_ids:
            if anchor_id not in anchors:
                errors.append(f"UNKNOWN_REPEAT_ANCHOR:{repeat.repeat_id}:{anchor_id}")

    for node in ir.nodes:
        seen: set[str] = set()
        cursor = node
        while cursor.parent_id is not None:
            if cursor.node_id in seen:
                errors.append(f"PARENT_CYCLE:{node.node_id}")
                break
            seen.add(cursor.node_id)
            parent = nodes.get(cursor.parent_id)
            if parent is None:
                break
            cursor = parent
    return sorted(set(errors))
