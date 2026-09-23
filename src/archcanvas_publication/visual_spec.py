"""Compile a visual contract from Publication and Exact IR, without inventing topology."""

from __future__ import annotations

from archcanvas_core.models.architecture import ArchitectureIR
from archcanvas_core.models.publication import PublicationEdgeKind, PublicationIR
from archcanvas_core.models.visual_spec import (
    VisualConstraint,
    VisualEdge,
    VisualNode,
    VisualPort,
    VisualSpec,
)
from archcanvas_core.publication_validation import validate_publication_semantics


class VisualSpecCompiler:
    def compile(self, publication: PublicationIR, exact: ArchitectureIR) -> VisualSpec:
        errors = validate_publication_semantics(publication, exact)
        if errors:
            raise ValueError(f"invalid publication mapping: {errors}")

        exact_nodes = {node.node_id: node for node in exact.nodes}
        exact_edges = {edge.edge_id: edge for edge in exact.edges}
        nodes = []
        for node in publication.nodes:
            ports = {
                port.port_id: VisualPort(port_id=port.port_id, direction=port.direction)
                for member_id in node.member_node_ids
                for port in (
                    exact_nodes[member_id].input_ports + exact_nodes[member_id].output_ports
                )
            }
            nodes.append(
                VisualNode(
                    canonical_id=node.node_id,
                    label=node.label,
                    visual_class=node.kind,
                    ports=[ports[port_id] for port_id in sorted(ports)],
                )
            )

        edges = []
        constraints = []
        for edge in publication.edges:
            members = [exact_edges[member_id] for member_id in edge.member_edge_ids]
            sources = {member.source_port_id for member in members}
            targets = {member.target_port_id for member in members}
            edges.append(
                VisualEdge(
                    canonical_id=edge.edge_id,
                    source_node_id=edge.source_node_id,
                    target_node_id=edge.target_node_id,
                    source_port_id=next(iter(sources)) if len(sources) == 1 else None,
                    target_port_id=next(iter(targets)) if len(targets) == 1 else None,
                    edge_type=(
                        "residual" if edge.kind is PublicationEdgeKind.RESIDUAL else "main"
                    ),
                )
            )
            if edge.kind is PublicationEdgeKind.DATA and edge.source_node_id != edge.target_node_id:
                constraints.append(
                    VisualConstraint(
                        kind="before",
                        source_node_id=edge.source_node_id,
                        target_node_id=edge.target_node_id,
                    )
                )
        return VisualSpec(
            spec_id=f"visual-spec:{publication.publication_id.removeprefix('publication:')}",
            publication_id=publication.publication_id,
            source_revision=publication.source_revision,
            nodes=nodes,
            edges=edges,
            constraints=constraints,
        )
