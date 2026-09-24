from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Iterable

from archcanvas_core.models import (
    ArchitectureIR,
    ArchitectureNode,
    EdgeType,
    NodeKind,
    PublicationEdge,
    PublicationHierarchy,
    PublicationHierarchyNode,
    PublicationNode,
    PublicationView,
    SemanticAnnotationOverlay,
)
from archcanvas_patterns import exact_ir_digest


def _profile(ir: ArchitectureIR) -> str:
    return next(
        (
            str(node.attributes["architecture_profile"])
            for node in ir.nodes
            if node.attributes.get("architecture_profile")
        ),
        "generic",
    )


def _layout_family(profile: str) -> str:
    return {
        "transformer-l3": "dual-lane",
        "autoformer": "dual-lane",
        "itransformer": "single-lane",
        "patchtst": "dual-backbone",
        "timemixer": "multiscale-ladder",
    }.get(profile, "generic-dag")


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _identifier_part(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._:-]+", ".", value.lower()).strip(".")
    return normalized or "unnamed"


def _module_parts(node: ArchitectureNode) -> list[str]:
    raw = str(node.attributes.get("module_path") or "").strip()
    if not raw:
        raw = node.node_id.removeprefix("node:")
    parts = [part for part in re.split(r"[./:_]+", raw) if part]
    while parts and parts[0].lower() in {"self", "model", "module"}:
        parts.pop(0)
    if not parts:
        return []

    lowered = [part.lower() for part in parts]
    if lowered[0] in {"enc", "encoder"}:
        parts[0] = "encoder"
    elif lowered[0] in {"dec", "decoder"}:
        parts[0] = "decoder"
    elif lowered[0] == "cross":
        parts = ["decoder", "cross", *parts[1:]]
    elif lowered[0] in {"mask", "masked"}:
        parts = ["decoder", "mask", *parts[1:]]
    elif lowered[0] in {"ffn", "feedforward", "feed", "mlp"}:
        parts[0] = "ffn"
    elif lowered[0] in {"input", "inputs"}:
        parts[0] = "inputs"
    elif lowered[0] == "output":
        parts[0] = "output"
    elif lowered[0] in {"generator", "head"}:
        parts = ["output", *parts]
    elif lowered[0] in {"activation", "activated", "transformed"}:
        parts = ["ffn", *parts]

    # The final token identifies the operation itself. The preceding tokens are
    # stable semantic containers (encoder/q, decoder/cross/k, ffn, ...).
    return parts[:-1]


def _overlay_check(ir: ArchitectureIR, overlay: SemanticAnnotationOverlay | None) -> None:
    if overlay is not None and (
        overlay.architecture_id != ir.architecture_id
        or overlay.exact_ir_digest != exact_ir_digest(ir)
    ):
        raise ValueError("semantic annotation overlay binding is stale")


def compile_hierarchy(
    ir: ArchitectureIR,
    overlay: SemanticAnnotationOverlay | None = None,
) -> PublicationHierarchy:
    """Compile the Exact IR into one stable, arbitrarily deep containment tree."""
    _overlay_check(ir, overlay)
    executable = [node for node in ir.nodes if node.kind is not NodeKind.REFERENCE_ONLY]
    if not executable:
        raise ValueError("publication hierarchy requires an executable node")
    executable_ids = {node.node_id for node in executable}
    roots = [node for node in executable if node.parent_id not in executable_ids]
    root = next((node for node in roots if node.kind is NodeKind.MODULE_CONTAINER), roots[0])
    suffix = ir.architecture_id.removeprefix("architecture:")
    root_id = f"hierarchy:{_identifier_part(suffix)}.root"
    hierarchy_nodes: list[PublicationHierarchyNode] = [
        PublicationHierarchyNode(
            hierarchy_node_id=root_id,
            semantic_name=root.semantic_name,
            kind=NodeKind.MODULE_CONTAINER,
            depth=0,
            canonical_node_ids=[root.node_id],
            evidence_ids=root.evidence_ids,
            attributes={"synthetic": False, "source_node_id": root.node_id},
        )
    ]
    node_to_hierarchy = {root.node_id: root_id}
    group_ids: dict[tuple[str, ...], str] = {}

    architecture_nodes = {node.node_id: node for node in executable}

    def architecture_depth(node: ArchitectureNode, trail: set[str] | None = None) -> int:
        if node.node_id == root.node_id or node.parent_id not in architecture_nodes:
            return 0
        trail = set() if trail is None else trail
        if node.node_id in trail:
            raise ValueError("Exact IR containment contains a cycle")
        return 1 + architecture_depth(
            architecture_nodes[node.parent_id], {*trail, node.node_id}
        )

    ordered_nodes = sorted(
        (item for item in executable if item.node_id != root.node_id),
        key=lambda item: (architecture_depth(item), item.node_id),
    )
    for node in ordered_nodes:
        explicit_parent = node_to_hierarchy.get(node.parent_id or "")
        parent_id = explicit_parent or root_id
        parent_depth = next(
            item.depth for item in hierarchy_nodes if item.hierarchy_node_id == parent_id
        )
        path: tuple[str, ...] = ()
        if explicit_parent is None or explicit_parent == root_id:
            for segment in _module_parts(node):
                path = (*path, segment)
                group_id = group_ids.get(path)
                if group_id is None:
                    group_id = f"hierarchy:group.{_digest(path)[:16]}"
                    group_ids[path] = group_id
                    hierarchy_nodes.append(
                        PublicationHierarchyNode(
                            hierarchy_node_id=group_id,
                            parent_hierarchy_node_id=parent_id,
                            semantic_name=segment.replace("_", " "),
                            kind=NodeKind.MODULE_CONTAINER,
                            depth=parent_depth + 1,
                            attributes={"synthetic": True, "path": list(path)},
                        )
                    )
                parent_id = group_id
                parent_depth += 1
        hierarchy_id = f"hierarchy:node.{_digest(node.node_id)[:16]}"
        node_to_hierarchy[node.node_id] = hierarchy_id
        annotations = [
            annotation
            for annotation in (overlay.annotations if overlay is not None else [])
            if node.node_id in annotation.canonical_node_ids
        ]
        hierarchy_nodes.append(
            PublicationHierarchyNode(
                hierarchy_node_id=hierarchy_id,
                parent_hierarchy_node_id=parent_id,
                semantic_name=node.semantic_name,
                kind=node.kind,
                depth=parent_depth + 1,
                canonical_node_ids=[node.node_id],
                evidence_ids=node.evidence_ids,
                attributes={
                    "synthetic": False,
                    "source_node_id": node.node_id,
                    "source_kind": node.kind.value,
                    "io": node.attributes.get("io"),
                    "semantic_annotations": [
                        {
                            "annotation_id": annotation.annotation_id,
                            "pack_id": annotation.pack_id,
                            "semantic_role": annotation.semantic_role,
                            "group_id": annotation.group_id,
                            "recommended_depth": annotation.recommended_depth,
                            "glyph": annotation.glyph,
                            "layout_family": annotation.layout_family,
                            "label": annotation.label,
                        }
                        for annotation in annotations
                    ],
                    "resolution": {
                        key: node.attributes[key]
                        for key in (
                            "implementation_status",
                            "semantic_status",
                            "execution_status",
                            "unresolved_reason",
                        )
                        if key in node.attributes
                    },
                },
            )
        )

    edges = [
        edge
        for edge in ir.edges
        if edge.producer_id in executable_ids and edge.consumer_id in executable_ids
    ]
    tensors = [tensor for tensor in ir.tensors if tensor.producer_id in executable_ids]
    ports = [
        port.port_id
        for node in executable
        for port in [*node.input_ports, *node.output_ports]
    ]
    return PublicationHierarchy(
        hierarchy_id=f"hierarchy:{_identifier_part(suffix)}",
        architecture_id=ir.architecture_id,
        root_node_id=root_id,
        nodes=hierarchy_nodes,
        max_depth=max(node.depth for node in hierarchy_nodes),
        canonical_node_ids=[node.node_id for node in executable],
        canonical_edge_ids=[edge.edge_id for edge in edges],
        canonical_tensor_ids=[tensor.tensor_id for tensor in tensors],
        canonical_port_ids=ports,
    )


def expandable_node_ids(hierarchy: PublicationHierarchy) -> set[str]:
    parents = {
        node.parent_hierarchy_node_id
        for node in hierarchy.nodes
        if node.parent_hierarchy_node_id is not None
    }
    return {item for item in parents if item != hierarchy.root_node_id}


def project_hierarchy(
    ir: ArchitectureIR,
    hierarchy: PublicationHierarchy,
    expanded_node_ids: Iterable[str] = (),
) -> PublicationView:
    """Project a hierarchy frontier selected by stable expanded container IDs."""
    if hierarchy.architecture_id != ir.architecture_id:
        raise ValueError("publication hierarchy belongs to a different architecture")
    by_id = {node.hierarchy_node_id: node for node in hierarchy.nodes}
    children: dict[str, list[PublicationHierarchyNode]] = defaultdict(list)
    for node in hierarchy.nodes:
        if node.parent_hierarchy_node_id is not None:
            children[node.parent_hierarchy_node_id].append(node)
    for members in children.values():
        members.sort(key=lambda item: item.hierarchy_node_id)
    expandable = expandable_node_ids(hierarchy)
    expanded = set(expanded_node_ids)
    unknown = expanded - expandable - {hierarchy.root_node_id}
    if unknown:
        raise ValueError(f"publication expansion references unknown containers: {sorted(unknown)}")
    expanded &= expandable

    descendants: dict[str, list[str]] = {}

    def canonical_descendants(node_id: str) -> list[str]:
        if node_id in descendants:
            return descendants[node_id]
        node = by_id[node_id]
        result = list(node.canonical_node_ids)
        for child in children.get(node_id, []):
            result.extend(canonical_descendants(child.hierarchy_node_id))
        descendants[node_id] = list(dict.fromkeys(result))
        return descendants[node_id]

    root = by_id[hierarchy.root_node_id]
    frontier: list[PublicationHierarchyNode] = []

    def visit(node: PublicationHierarchyNode) -> None:
        members = children.get(node.hierarchy_node_id, [])
        if members and node.hierarchy_node_id in expanded:
            if node.canonical_node_ids:
                frontier.append(node)
            for child in members:
                visit(child)
        else:
            frontier.append(node)

    for child in children.get(root.hierarchy_node_id, []):
        visit(child)

    canonical_to_view: dict[str, str] = {
        canonical_id: "viewnode:model" for canonical_id in root.canonical_node_ids
    }
    publication_nodes = [
        PublicationNode(
            view_node_id="viewnode:model",
            canonical_node_ids=root.canonical_node_ids,
            semantic_name=root.semantic_name,
            kind=NodeKind.MODULE_CONTAINER,
            collapsed=False,
            evidence_ids=root.evidence_ids,
            attributes={
                **root.attributes,
                "hierarchy_node_id": root.hierarchy_node_id,
                "semantic_annotations": root.attributes.get("semantic_annotations", []),
            },
        )
    ]
    architecture_nodes = {node.node_id: node for node in ir.nodes}

    def emit(item: PublicationHierarchyNode, parent_view_node_id: str) -> None:
        item_children = children.get(item.hierarchy_node_id, [])
        is_expanded_container = bool(item_children) and item.hierarchy_node_id in expanded
        canonical_ids = (
            list(item.canonical_node_ids)
            if is_expanded_container
            else canonical_descendants(item.hierarchy_node_id)
        )
        if not canonical_ids and not is_expanded_container:
            return
        view_node_id = f"viewnode:{item.hierarchy_node_id.removeprefix('hierarchy:')}"
        for canonical_id in canonical_ids:
            canonical_to_view[canonical_id] = view_node_id
        source_nodes = [architecture_nodes[node_id] for node_id in canonical_ids]
        roles = sorted(
            {
                port.role
                for node in source_nodes
                for port in [*node.input_ports, *node.output_ports]
            }
        )
        descendant_ids = canonical_descendants(item.hierarchy_node_id)
        publication_nodes.append(
            PublicationNode(
                view_node_id=view_node_id,
                canonical_node_ids=canonical_ids,
                semantic_name=item.semantic_name,
                kind=(
                    NodeKind.MODULE_CONTAINER
                    if item_children
                    else item.kind if len(canonical_ids) == 1 else NodeKind.MODULE_CONTAINER
                ),
                parent_view_node_id=parent_view_node_id,
                collapsed=bool(item_children) and not is_expanded_container,
                boundary_roles=roles,
                evidence_ids=list(
                    dict.fromkeys(
                        evidence_id for node in source_nodes for evidence_id in node.evidence_ids
                    )
                ),
                attributes={
                    **item.attributes,
                    "hierarchy_node_id": item.hierarchy_node_id,
                    "canonical_count": len(descendant_ids),
                    "structural_container": is_expanded_container and not canonical_ids,
                    "depth": item.depth,
                    "semantic_annotations": [
                        annotation
                        for hierarchy_item in hierarchy.nodes
                        if set(hierarchy_item.canonical_node_ids).intersection(descendant_ids)
                        for annotation in hierarchy_item.attributes.get(
                            "semantic_annotations", []
                        )
                    ],
                },
            )
        )
        if is_expanded_container:
            for child in item_children:
                emit(child, view_node_id)

    for child in children.get(root.hierarchy_node_id, []):
        emit(child, "viewnode:model")

    executable_ids = set(hierarchy.canonical_node_ids)
    executable_edges = [
        edge
        for edge in ir.edges
        if edge.producer_id in executable_ids and edge.consumer_id in executable_ids
    ]
    edge_groups: dict[tuple[str, str, EdgeType, str], list] = defaultdict(list)
    collapsed_edge_ids: list[str] = []
    exact_frontier = all(
        len(node.canonical_node_ids) == 1
        for node in publication_nodes
        if node.canonical_node_ids
    )
    for edge in executable_edges:
        source = canonical_to_view[edge.producer_id]
        target = canonical_to_view[edge.consumer_id]
        if source == target:
            collapsed_edge_ids.append(edge.edge_id)
            continue
        role_key = edge.role if exact_frontier else edge.edge_type.value
        edge_groups[(source, target, edge.edge_type, role_key)].append(edge)
    publication_edges: list[PublicationEdge] = []
    for key, members in sorted(edge_groups.items(), key=lambda item: str(item[0])):
        source, target, edge_type, _ = key
        shapes = {member.symbolic_shape for member in members}
        edge_digest = _digest([member.edge_id for member in members])[:16]
        publication_edges.append(
            PublicationEdge(
                view_edge_id=f"viewedge:{edge_digest}",
                canonical_edge_ids=[member.edge_id for member in members],
                source_view_node_id=source,
                target_view_node_id=target,
                role=(
                    members[0].role
                    if len(members) == 1
                    else f"{edge_type.value} x{len(members)}"
                ),
                edge_type=edge_type,
                symbolic_shape=next(iter(shapes)) if len(shapes) == 1 else "[multiple]",
                evidence_ids=list(
                    dict.fromkeys(
                        evidence_id for member in members for evidence_id in member.evidence_ids
                    )
                ),
            )
        )

    frontier_digest = _digest(sorted(expanded))
    fully_expanded = expanded == expandable
    return PublicationView(
        view_id=f"view:{ir.architecture_id.removeprefix('architecture:')}.{frontier_digest[:16]}",
        architecture_id=ir.architecture_id,
        hierarchy_id=hierarchy.hierarchy_id,
        projection_id=f"projection:{frontier_digest[:16]}",
        frontier_digest=frontier_digest,
        expanded_node_ids=sorted(expanded),
        visible_depth=max((node.depth for node in frontier), default=0),
        max_depth=hierarchy.max_depth,
        fully_expanded=fully_expanded,
        name="Fully expanded" if fully_expanded else "Containment projection",
        layout_family=_layout_family(_profile(ir)),
        nodes=publication_nodes,
        edges=publication_edges,
        canonical_node_ids=hierarchy.canonical_node_ids,
        canonical_edge_ids=hierarchy.canonical_edge_ids,
        collapsed_edge_ids=collapsed_edge_ids,
        canonical_tensor_ids=hierarchy.canonical_tensor_ids,
        canonical_port_ids=hierarchy.canonical_port_ids,
    )


def compile_publication(
    ir: ArchitectureIR,
    expanded_node_ids: Iterable[str] = (),
    overlay: SemanticAnnotationOverlay | None = None,
) -> PublicationView:
    hierarchy = compile_hierarchy(ir, overlay)
    return project_hierarchy(ir, hierarchy, expanded_node_ids)


def compile_views(
    ir: ArchitectureIR,
    overlay: SemanticAnnotationOverlay | None = None,
) -> list[PublicationView]:
    """Return deterministic collapsed and exact projections for batch publication."""
    hierarchy = compile_hierarchy(ir, overlay)
    collapsed = project_hierarchy(ir, hierarchy)
    expanded = project_hierarchy(ir, hierarchy, expandable_node_ids(hierarchy))
    return [collapsed] if collapsed.view_id == expanded.view_id else [collapsed, expanded]
