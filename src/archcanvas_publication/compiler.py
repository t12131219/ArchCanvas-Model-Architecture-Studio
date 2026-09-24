from __future__ import annotations

from collections import defaultdict

from archcanvas_core.models import (
    ArchitectureIR,
    ArchitectureNode,
    EdgeType,
    NodeKind,
    PublicationEdge,
    PublicationNode,
    PublicationView,
    SemanticAnnotationOverlay,
)
from archcanvas_patterns import exact_ir_digest

LEVEL_NAMES = {
    "L1": "Paper overview",
    "L2": "Module view",
    "L3": "Semantic view",
    "L4": "Operator and tensor view",
}


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


def _region(node: ArchitectureNode, profile: str, level: str) -> str:
    raw = node.node_id.removeprefix("node:")
    if node.kind is NodeKind.MODULE_CONTAINER and node.parent_id is None:
        return "model"
    io = node.attributes.get("io")
    if io:
        return f"io-{io}-{node.node_id}"
    lowered = f"{raw} {node.semantic_name}".lower()
    if level in {"L3", "L4"}:
        return raw
    if profile == "transformer-l3":
        symbol = str(node.attributes.get("assigned_symbol", raw)).lower()
        if symbol.startswith("enc_") or symbol == "memory":
            return "encoder-attention" if level == "L1" else "encoder"
        if symbol.startswith("dec_") or symbol == "decoder_hidden":
            return "decoder-self" if level == "L1" else "decoder"
        if symbol.startswith("cross_"):
            return "cross-attention" if level == "L1" else "cross"
        if symbol in {"expanded", "activated", "transformed", "output_residual", "output_hidden"}:
            return "feed-forward" if level == "L1" else "output-block"
        return "projection-output"
    if profile == "autoformer":
        if raw.startswith(("encoder", "enc_")):
            return "encoder" if level == "L1" else raw.split(".", 1)[0]
        if raw.startswith(("decoder", "dec_")):
            return "decoder" if level == "L1" else ".".join(raw.split(".")[:2])
        if any(word in lowered for word in ("trend", "season", "decomp", "mean", "zero")):
            return "decomposition-flow"
        return "embedding-output"
    if profile == "itransformer":
        for key in ("normalize", "embedding", "covariate", "encoder", "forecast", "denormalize"):
            if key in lowered:
                return key
    if profile == "patchtst":
        for key in ("residual", "trend", "main"):
            if raw.startswith(key):
                return key if level == "L1" else ".".join(raw.split(".")[:2])
        if "decomposition" in lowered:
            return "decomposition"
        return "forecast-output"
    if profile == "timemixer":
        if raw.startswith("scale."):
            parts = raw.split(".")
            return f"scale-{parts[1]}" if level == "L1" else ".".join(parts[:3])
        if "season" in lowered:
            return "seasonal-mixing"
        if "trend" in lowered:
            return "trend-mixing"
        if "forecast" in lowered or "denormalize" in lowered:
            return "forecast-merge"
        return "input-scales"
    if level == "L1":
        if raw.startswith("opaque"):
            return raw
        return raw.split(".", 1)[0].split("_", 1)[0]
    return ".".join(raw.split(".")[:2])


def _group_label(nodes: list[ArchitectureNode], key: str) -> str:
    if len(nodes) == 1:
        return nodes[0].semantic_name
    friendly = key.replace("-", " ").replace("_", " ").replace(".", " / ")
    return friendly.title()


def compile_publication(
    ir: ArchitectureIR,
    level: str,
    overlay: SemanticAnnotationOverlay | None = None,
) -> PublicationView:
    if level not in LEVEL_NAMES:
        raise ValueError(f"unsupported publication level: {level}")
    if overlay is not None and (
        overlay.architecture_id != ir.architecture_id
        or overlay.exact_ir_digest != exact_ir_digest(ir)
    ):
        raise ValueError("semantic annotation overlay binding is stale")
    profile = _profile(ir)
    executable_nodes = [node for node in ir.nodes if node.kind is not NodeKind.REFERENCE_ONLY]
    executable_ids = {node.node_id for node in executable_nodes}
    executable_edges = [
        edge
        for edge in ir.edges
        if edge.producer_id in executable_ids and edge.consumer_id in executable_ids
    ]
    root = next((node for node in executable_nodes if node.parent_id is None), None)
    groups: dict[str, list[ArchitectureNode]] = defaultdict(list)
    for node in executable_nodes:
        key = _region(node, profile, level)
        groups[key].append(node)

    canonical_to_view: dict[str, str] = {}
    publication_nodes: list[PublicationNode] = []
    root_view_id: str | None = None
    for index, (key, members) in enumerate(groups.items()):
        if len(members) == 1 and level in {"L3", "L4"}:
            view_node_id = f"viewnode:{members[0].node_id.removeprefix('node:')}"
        elif key == "model":
            view_node_id = "viewnode:model"
        else:
            view_node_id = f"viewnode:group.{index}"
        for member in members:
            canonical_to_view[member.node_id] = view_node_id
        representative = members[0]
        is_root = root is not None and root in members
        if is_root:
            root_view_id = view_node_id
        roles = sorted(
            {
                port.role
                for member in members
                for port in [*member.input_ports, *member.output_ports]
            }
        )
        semantic_annotations = [
            annotation
            for annotation in (overlay.annotations if overlay is not None else [])
            if set(annotation.canonical_node_ids) & {member.node_id for member in members}
        ]
        publication_nodes.append(
            PublicationNode(
                view_node_id=view_node_id,
                canonical_node_ids=[member.node_id for member in members],
                semantic_name=_group_label(members, key),
                kind=(
                    NodeKind.MODULE_CONTAINER
                    if is_root
                    else representative.kind
                    if len(members) == 1
                    else NodeKind.MODULE_CONTAINER
                ),
                parent_view_node_id=None if is_root else root_view_id,
                collapsed=len(members) > 1,
                boundary_roles=roles,
                evidence_ids=list(
                    dict.fromkeys(
                        evidence_id for member in members for evidence_id in member.evidence_ids
                    )
                ),
                attributes={
                    "profile": profile,
                    "canonical_count": len(members),
                    "source_kind": representative.kind.value,
                    "io": representative.attributes.get("io"),
                    "semantic_annotations": [
                        {
                            "annotation_id": annotation.annotation_id,
                            "pack_id": annotation.pack_id,
                            "semantic_role": annotation.semantic_role,
                            "group_id": annotation.group_id,
                            "recommended_level": annotation.recommended_level,
                            "glyph": annotation.glyph,
                            "layout_family": annotation.layout_family,
                            "label": annotation.label,
                        }
                        for annotation in semantic_annotations
                    ],
                    "resolution": {
                        key: representative.attributes[key]
                        for key in (
                            "implementation_status",
                            "semantic_status",
                            "execution_status",
                            "unresolved_reason",
                        )
                        if key in representative.attributes
                    },
                },
            )
        )

    if root_view_id:
        publication_nodes = [
            node.model_copy(
                update={
                    "parent_view_node_id": (
                        None if node.view_node_id == root_view_id else root_view_id
                    )
                }
            )
            for node in publication_nodes
        ]

    edge_groups: dict[tuple[str, str, EdgeType, str], list] = defaultdict(list)
    collapsed_edge_ids: list[str] = []
    for edge in executable_edges:
        source = canonical_to_view[edge.producer_id]
        target = canonical_to_view[edge.consumer_id]
        if source == target:
            collapsed_edge_ids.append(edge.edge_id)
            continue
        role_key = edge.role if level in {"L3", "L4"} else edge.edge_type.value
        edge_groups[(source, target, edge.edge_type, role_key)].append(edge)

    publication_edges: list[PublicationEdge] = []
    for index, ((source, target, edge_type, _), members) in enumerate(edge_groups.items()):
        role = members[0].role if len(members) == 1 else f"{edge_type.value} x{len(members)}"
        shapes = {member.symbolic_shape for member in members}
        publication_edges.append(
            PublicationEdge(
                view_edge_id=f"viewedge:{index}",
                canonical_edge_ids=[member.edge_id for member in members],
                source_view_node_id=source,
                target_view_node_id=target,
                role=role,
                edge_type=edge_type,
                symbolic_shape=next(iter(shapes)) if len(shapes) == 1 else "[multiple]",
                evidence_ids=list(
                    dict.fromkeys(
                        evidence_id for member in members for evidence_id in member.evidence_ids
                    )
                ),
            )
        )

    tensors = [tensor for tensor in ir.tensors if tensor.producer_id in executable_ids]
    ports = [
        port.port_id
        for node in executable_nodes
        for port in [*node.input_ports, *node.output_ports]
    ]
    return PublicationView(
        view_id=f"view:{ir.architecture_id.removeprefix('architecture:')}.{level.lower()}",
        architecture_id=ir.architecture_id,
        level=level,
        name=LEVEL_NAMES[level],
        layout_family=_layout_family(profile),
        nodes=publication_nodes,
        edges=publication_edges,
        canonical_node_ids=[node.node_id for node in executable_nodes],
        canonical_edge_ids=[edge.edge_id for edge in executable_edges],
        collapsed_edge_ids=collapsed_edge_ids,
        canonical_tensor_ids=[tensor.tensor_id for tensor in tensors],
        canonical_port_ids=ports,
    )


def compile_views(
    ir: ArchitectureIR,
    overlay: SemanticAnnotationOverlay | None = None,
) -> list[PublicationView]:
    return [
        compile_publication(ir, level, overlay) for level in ("L1", "L2", "L3", "L4")
    ]
