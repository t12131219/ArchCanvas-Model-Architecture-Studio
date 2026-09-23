"""Cross-document validation for the Exact IR to Publication IR mapping."""

from __future__ import annotations

from .models.architecture import ArchitectureIR
from .models.publication import PublicationIR, VisualScene
from .models.visual_spec import VisualSpec


def validate_publication_semantics(publication: PublicationIR, exact: ArchitectureIR) -> list[str]:
    errors: list[str] = []
    if publication.exact_ir_id != exact.ir_id:
        errors.append("EXACT_IR_ID_MISMATCH")
    if publication.project_id != exact.project_id:
        errors.append("PROJECT_ID_MISMATCH")
    if publication.source_revision != exact.source_revision:
        errors.append("SOURCE_REVISION_MISMATCH")
    exact_nodes = {node.node_id for node in exact.nodes}
    exact_edges = {edge.edge_id for edge in exact.edges}
    members = [member for node in publication.nodes for member in node.member_node_ids]
    if len(members) != len(set(members)):
        errors.append("EXACT_NODE_MAPPED_MORE_THAN_ONCE")
    mapped = set(members)
    omitted = set(publication.omitted_exact_node_ids)
    if mapped & omitted:
        errors.append("EXACT_NODE_BOTH_MAPPED_AND_OMITTED")
    if mapped | omitted != exact_nodes:
        errors.append("EXACT_NODE_MAPPING_INCOMPLETE")
    if not mapped <= exact_nodes or not omitted <= exact_nodes:
        errors.append("UNKNOWN_EXACT_NODE")
    for edge in publication.edges:
        if not set(edge.member_edge_ids) <= exact_edges:
            errors.append(f"UNKNOWN_EXACT_EDGE:{edge.edge_id}")
    edge_members = [member for edge in publication.edges for member in edge.member_edge_ids]
    if len(edge_members) != len(set(edge_members)):
        errors.append("EXACT_EDGE_MAPPED_MORE_THAN_ONCE")
    mapped_edges = set(edge_members)
    omitted_edges = set(publication.omitted_exact_edge_ids)
    if mapped_edges & omitted_edges:
        errors.append("EXACT_EDGE_BOTH_MAPPED_AND_OMITTED")
    if mapped_edges | omitted_edges != exact_edges:
        errors.append("EXACT_EDGE_MAPPING_INCOMPLETE")
    if not omitted_edges <= exact_edges:
        errors.append("UNKNOWN_EXACT_EDGE")
    return sorted(set(errors))


def validate_scene_semantics(scene: VisualScene, publication: PublicationIR) -> list[str]:
    errors: list[str] = []
    if scene.publication_id != publication.publication_id:
        errors.append("PUBLICATION_ID_MISMATCH")
    scene_node_ids = {node.publication_node_id for node in scene.nodes}
    publication_nodes = {node.node_id: node for node in publication.nodes}
    if scene_node_ids != set(publication_nodes):
        errors.append("SCENE_NODE_MAPPING_INCOMPLETE")
    for scene_node in scene.nodes:
        publication_node = publication_nodes.get(scene_node.publication_node_id)
        if scene_node.expanded and (
            publication_node is None
            or publication_node.kind.value != "repeat_group"
        ):
            errors.append("EXPANDED_NODE_NOT_REPEAT_GROUP")
    scene_edges = {edge.publication_edge_id for edge in scene.edges}
    publication_edges = {edge.edge_id for edge in publication.edges}
    if scene_edges != publication_edges:
        errors.append("SCENE_EDGE_MAPPING_INCOMPLETE")
    return sorted(set(errors))


def validate_visual_spec_semantics(spec: VisualSpec, publication: PublicationIR) -> list[str]:
    errors: list[str] = []
    if spec.publication_id != publication.publication_id:
        errors.append("VISUAL_SPEC_PUBLICATION_ID_MISMATCH")
    if spec.source_revision != publication.source_revision:
        errors.append("VISUAL_SPEC_SOURCE_REVISION_MISMATCH")
    nodes = {node.node_id: node for node in publication.nodes}
    edges = {edge.edge_id: edge for edge in publication.edges}
    if {node.canonical_id for node in spec.nodes} != set(nodes):
        errors.append("VISUAL_SPEC_NODE_MAPPING_INCOMPLETE")
    for node in spec.nodes:
        original = nodes.get(node.canonical_id)
        if original is not None and (node.label != original.label or node.visual_class != original.kind):
            errors.append("VISUAL_SPEC_NODE_FACT_MISMATCH")
    if {edge.canonical_id for edge in spec.edges} != set(edges):
        errors.append("VISUAL_SPEC_EDGE_MAPPING_INCOMPLETE")
    for edge in spec.edges:
        original = edges.get(edge.canonical_id)
        if original is not None and (
            edge.source_node_id != original.source_node_id
            or edge.target_node_id != original.target_node_id
            or edge.edge_type != (
                "residual" if original.kind.value == "residual" else "main"
            )
        ):
            errors.append("VISUAL_SPEC_EDGE_FACT_MISMATCH")
    return sorted(set(errors))
