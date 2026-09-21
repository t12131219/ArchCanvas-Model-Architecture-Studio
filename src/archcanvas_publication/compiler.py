"""Conservative pattern reduction from Exact Architecture IR to Publication IR."""

from __future__ import annotations

from collections import defaultdict

from archcanvas_core.models.architecture import (
    ArchitectureIR,
    ArchitectureNode,
    EdgeKind,
    NodeKind,
)
from archcanvas_core.models.publication import (
    PublicationAnnotation,
    PublicationEdge,
    PublicationEdgeKind,
    PublicationIR,
    PublicationNode,
    PublicationNodeKind,
)

_IMPLEMENTATION_DETAIL_OPS = {
    "torch.reshape",
    "torch.transpose",
    "torch.permute",
    "torch.flatten",
    "torch.squeeze",
    "torch.unsqueeze",
}


def _token(value: str) -> str:
    return value.replace("publication-node:", "").replace("node:", "").replace(".", "-")


def _is_hidden(node: ArchitectureNode) -> bool:
    return (
        node.kind in {NodeKind.FUNCTION, NodeKind.OPERATOR}
        and node.op_type in _IMPLEMENTATION_DETAIL_OPS
    )


def _label(node: ArchitectureNode) -> str:
    kind = node.kind
    if kind is NodeKind.INPUT:
        return "Input"
    if kind is NodeKind.OUTPUT:
        return "Output"
    op_type = node.op_type
    if op_type == "torch.nn.Embedding":
        return "Token embedding"
    if op_type == "torch.nn.LayerNorm":
        return "Layer normalization"
    if op_type == "torch.nn.Linear":
        return "Prediction head"
    return node.display_name.replace("_", " ").title()


class PublicationCompiler:
    """Compile declared, source-backed patterns without altering the Exact IR."""

    compiler_id = "publication-compiler-v1"

    def compile(self, exact: ArchitectureIR) -> PublicationIR:
        visible = [node for node in exact.nodes if not _is_hidden(node)]
        omitted = [node.node_id for node in exact.nodes if _is_hidden(node)]
        transformer_repeat = next(
            (
                repeat
                for repeat in exact.repeats
                if all(
                    exact.node(member).op_type == "torch.nn.TransformerEncoderLayer"
                    for member in repeat.member_node_ids
                )
            ),
            None,
        )
        residual_edges = [edge for edge in exact.edges if edge.kind is EdgeKind.RESIDUAL]
        internal = [node.node_id for node in visible if node.kind not in {NodeKind.INPUT, NodeKind.OUTPUT}]
        group_members: set[str] = set()
        group: PublicationNode | None = None
        annotations: list[PublicationAnnotation] = []
        if transformer_repeat is not None:
            group_members = set(transformer_repeat.member_node_ids)
            group = PublicationNode(
                node_id="publication-node:transformer-encoder",
                kind=PublicationNodeKind.REPEAT_GROUP,
                label="Transformer encoder",
                member_node_ids=transformer_repeat.member_node_ids,
                collapsed=True,
            )
            count = str(transformer_repeat.count) if transformer_repeat.count is not None else transformer_repeat.count_symbol
            annotations.append(
                PublicationAnnotation(
                    annotation_id="annotation:transformer-encoder-repeat",
                    target_node_id=group.node_id,
                    text=f"Repeated {count} times",
                    kind="repeat",
                )
            )
        elif residual_edges and internal:
            group_members = set(internal)
            group = PublicationNode(
                node_id="publication-node:residual-stage",
                kind=PublicationNodeKind.RESIDUAL_BLOCK,
                label="Residual stage",
                member_node_ids=internal,
                collapsed=True,
            )
            annotations.append(
                PublicationAnnotation(
                    annotation_id="annotation:residual-stage-skip",
                    target_node_id=group.node_id,
                    text="Residual connection",
                    kind="residual",
                )
            )

        publication_nodes: list[PublicationNode] = []
        exact_to_publication: dict[str, str] = {}
        inserted_group = False
        for node in visible:
            if node.node_id in group_members:
                if not inserted_group and group is not None:
                    publication_nodes.append(group)
                    inserted_group = True
                exact_to_publication[node.node_id] = group.node_id if group is not None else ""
                continue
            publication_node_id = f"publication-node:{_token(node.node_id)}"
            exact_to_publication[node.node_id] = publication_node_id
            publication_nodes.append(
                PublicationNode(
                    node_id=publication_node_id,
                    kind=(
                        PublicationNodeKind.INPUT
                        if node.kind is NodeKind.INPUT
                        else PublicationNodeKind.OUTPUT
                        if node.kind is NodeKind.OUTPUT
                        else PublicationNodeKind.MODULE
                    ),
                    label=_label(node),
                    member_node_ids=[node.node_id],
                    collapsed=False,
                )
            )

        grouped_edges: dict[tuple[str, str, PublicationEdgeKind], list[str]] = defaultdict(list)
        omitted_edges: list[str] = []
        for edge in exact.edges:
            source = exact_to_publication.get(edge.source_node_id)
            target = exact_to_publication.get(edge.target_node_id)
            if source is None or target is None:
                omitted_edges.append(edge.edge_id)
                continue
            kind = PublicationEdgeKind.RESIDUAL if edge.kind is EdgeKind.RESIDUAL else PublicationEdgeKind.DATA
            if source == target and kind is PublicationEdgeKind.DATA:
                omitted_edges.append(edge.edge_id)
                continue
            grouped_edges[(source, target, kind)].append(edge.edge_id)
        publication_edges = [
            PublicationEdge(
                edge_id=f"publication-edge:{_token(source)}--{_token(target)}--{kind.value}",
                source_node_id=source,
                target_node_id=target,
                kind=kind,
                member_edge_ids=sorted(member_edge_ids),
            )
            for (source, target, kind), member_edge_ids in sorted(grouped_edges.items())
        ]
        return PublicationIR(
            publication_id=f"publication:{exact.ir_id.removeprefix('ir:')}",
            exact_ir_id=exact.ir_id,
            project_id=exact.project_id,
            source_revision=exact.source_revision,
            nodes=publication_nodes,
            edges=publication_edges,
            annotations=annotations,
            omitted_exact_node_ids=omitted,
            omitted_exact_edge_ids=sorted(omitted_edges),
        )
