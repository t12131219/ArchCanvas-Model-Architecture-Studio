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
    MiniatureDisclosure,
    MiniatureEvidenceKind,
    PublicationAnnotation,
    PublicationEdge,
    PublicationEdgeKind,
    PublicationIR,
    PublicationMiniature,
    PublicationMiniatureKind,
    PublicationNode,
    PublicationNodeKind,
)
from archcanvas_publication.patterns import (
    PatternConfidence,
    PatternMatch,
    PublicationPatternRegistry,
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


def _single_member(match: PatternMatch | None) -> str | None:
    if match is None or len(match.member_node_ids) != 1:
        return None
    return match.member_node_ids[0]


def _semantic_pattern_nodes(
    matches: list[PatternMatch],
) -> tuple[
    dict[str, PublicationNode],
    list[PublicationAnnotation],
    list[PublicationMiniature],
]:
    """Map only complete cross-file signatures to presentation nodes.

    The resulting nodes retain the root Exact member.  They deliberately do not invent
    cross-file child topology or edges that Exact recovery has not established.
    """

    by_id = {match.pattern_id: match for match in matches if match.confidence is PatternConfidence.CONFIRMED}
    nodes: dict[str, PublicationNode] = {}
    annotations: list[PublicationAnnotation] = []
    miniatures: list[PublicationMiniature] = []

    encoder = _single_member(by_id.get("encoder_attention_stack_v1"))
    decoder = _single_member(by_id.get("decoder_cross_attention_stack_v1"))
    if encoder is not None and decoder is not None and encoder != decoder:
        encoder_count = by_id["encoder_attention_stack_v1"].resolved_parameters.get("e_layers", "N")
        decoder_count = by_id["decoder_cross_attention_stack_v1"].resolved_parameters.get("d_layers", "N")
        nodes[encoder] = PublicationNode(
            node_id="publication-node:transformer-encoder",
            kind=PublicationNodeKind.REPEAT_GROUP,
            label="Transformer Encoder",
            member_node_ids=[encoder],
            collapsed=True,
        )
        nodes[decoder] = PublicationNode(
            node_id="publication-node:transformer-decoder",
            kind=PublicationNodeKind.REPEAT_GROUP,
            label="Transformer Decoder",
            member_node_ids=[decoder],
            collapsed=True,
        )
        annotations.extend(
            [
                PublicationAnnotation(
                    annotation_id="annotation:transformer-encoder-repeat",
                    target_node_id=nodes[encoder].node_id,
                    text=f"Repeated {encoder_count} times",
                    kind="repeat",
                ),
                PublicationAnnotation(
                    annotation_id="annotation:transformer-decoder-repeat",
                    target_node_id=nodes[decoder].node_id,
                    text=f"Repeated {decoder_count} times",
                    kind="repeat",
                ),
            ]
        )
        miniatures.extend(
            [
                PublicationMiniature(
                    miniature_id="miniature:transformer-encoder-inset",
                    target_node_id=nodes[encoder].node_id,
                    kind=PublicationMiniatureKind.INSET_CALLOUT,
                    evidence_kind=MiniatureEvidenceKind.PUBLICATION_ANNOTATION,
                    disclosure=MiniatureDisclosure.EVIDENCE,
                    label="Self-attention, residual, normalization, and feed-forward are source-backed",
                    member_node_ids=[encoder],
                ),
                PublicationMiniature(
                    miniature_id="miniature:transformer-decoder-inset",
                    target_node_id=nodes[decoder].node_id,
                    kind=PublicationMiniatureKind.INSET_CALLOUT,
                    evidence_kind=MiniatureEvidenceKind.PUBLICATION_ANNOTATION,
                    disclosure=MiniatureDisclosure.EVIDENCE,
                    label="Masked self-attention, cross-attention, and feed-forward are source-backed",
                    member_node_ids=[decoder],
                ),
            ]
        )

    router = _single_member(by_id.get("topk_expert_router_v1"))
    mask = _single_member(by_id.get("frequency_gumbel_mask_v1"))
    extractor = _single_member(by_id.get("decomposition_linear_fusion_v1"))
    channel_encoder = _single_member(by_id.get("masked_attention_stack_v1"))
    if router is not None and mask is not None and extractor == router and channel_encoder is not None:
        parameters = by_id["topk_expert_router_v1"].resolved_parameters
        expert_count = parameters.get("num_experts", "N")
        top_k = parameters.get("k", "K")
        layer_count = by_id["masked_attention_stack_v1"].resolved_parameters.get("e_layers", "N")
        nodes[router] = PublicationNode(
            node_id="publication-node:expert-temporal-pattern-module",
            kind=PublicationNodeKind.REPEAT_GROUP,
            label="Temporal Pattern Module",
            member_node_ids=[router],
            collapsed=True,
        )
        nodes[mask] = PublicationNode(
            node_id="publication-node:frequency-channel-mask",
            kind=PublicationNodeKind.MODULE,
            label="Channel Mask Generator",
            member_node_ids=[mask],
            collapsed=False,
        )
        nodes[channel_encoder] = PublicationNode(
            node_id="publication-node:masked-temporal-channel-fusion",
            kind=PublicationNodeKind.REPEAT_GROUP,
            label="Temporal-Channel Fusion",
            member_node_ids=[channel_encoder],
            collapsed=True,
        )
        annotations.extend(
            [
                PublicationAnnotation(
                    annotation_id="annotation:expert-router-repeat",
                    target_node_id=nodes[router].node_id,
                    text=f"{expert_count} experts; Top-{top_k} routing",
                    kind="repeat",
                ),
                PublicationAnnotation(
                    annotation_id="annotation:masked-attention-stack-repeat",
                    target_node_id=nodes[channel_encoder].node_id,
                    text=f"Repeated {layer_count} times",
                    kind="repeat",
                ),
            ]
        )
        miniatures.extend(
            [
                PublicationMiniature(
                    miniature_id="miniature:expert-router-schematic",
                    target_node_id=nodes[router].node_id,
                    kind=PublicationMiniatureKind.SIGNAL_PREVIEW,
                    evidence_kind=MiniatureEvidenceKind.DETERMINISTIC_SCHEMATIC,
                    disclosure=MiniatureDisclosure.ILLUSTRATIVE,
                    label="Illustrative routing flow (not runtime gates)",
                    member_node_ids=[router],
                ),
                PublicationMiniature(
                    miniature_id="miniature:decomposition-linear-fusion-inset",
                    target_node_id=nodes[router].node_id,
                    kind=PublicationMiniatureKind.INSET_CALLOUT,
                    evidence_kind=MiniatureEvidenceKind.PUBLICATION_ANNOTATION,
                    disclosure=MiniatureDisclosure.EVIDENCE,
                    label="Series decomposition and seasonal/trend linear fusion are source-backed",
                    member_node_ids=[router],
                ),
                PublicationMiniature(
                    miniature_id="miniature:frequency-mask-schematic",
                    target_node_id=nodes[mask].node_id,
                    kind=PublicationMiniatureKind.SIGNAL_PREVIEW,
                    evidence_kind=MiniatureEvidenceKind.DETERMINISTIC_SCHEMATIC,
                    disclosure=MiniatureDisclosure.ILLUSTRATIVE,
                    label="Illustrative frequency mask flow (not runtime channel values)",
                    member_node_ids=[mask],
                ),
                PublicationMiniature(
                    miniature_id="miniature:masked-attention-stack-inset",
                    target_node_id=nodes[channel_encoder].node_id,
                    kind=PublicationMiniatureKind.INSET_CALLOUT,
                    evidence_kind=MiniatureEvidenceKind.PUBLICATION_ANNOTATION,
                    disclosure=MiniatureDisclosure.EVIDENCE,
                    label="Masked attention, residual, normalization, and feed-forward are source-backed",
                    member_node_ids=[channel_encoder],
                ),
            ]
        )
    return nodes, annotations, miniatures


class PublicationCompiler:
    """Compile declared, source-backed patterns without altering the Exact IR."""

    compiler_id = "publication-compiler-v1"

    def compile(self, exact: ArchitectureIR) -> PublicationIR:
        visible = [node for node in exact.nodes if not _is_hidden(node)]
        omitted = [node.node_id for node in exact.nodes if _is_hidden(node)]
        pattern_matches = PublicationPatternRegistry().match(exact)
        semantic_nodes, semantic_annotations, semantic_miniatures = _semantic_pattern_nodes(
            pattern_matches
        )
        spectral_period_match = next(
            (
                match
                for match in pattern_matches
                if match.pattern_id == "spectral_period_inception_block_v1"
                and match.confidence is PatternConfidence.CONFIRMED
            ),
            None,
        )
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
        annotations = list(semantic_annotations)
        if not semantic_nodes and transformer_repeat is not None:
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
        elif not semantic_nodes and spectral_period_match is not None:
            group_members = set(spectral_period_match.member_node_ids)
            group = PublicationNode(
                node_id="publication-node:spectral-period-blocks",
                kind=PublicationNodeKind.REPEAT_GROUP,
                label="Spectral Period Block",
                member_node_ids=spectral_period_match.member_node_ids,
                collapsed=True,
            )
            repeat = next(
                (
                    candidate
                    for candidate in exact.repeats
                    if set(spectral_period_match.member_node_ids) <= set(candidate.member_node_ids)
                ),
                None,
            )
            count = (
                str(repeat.count) if repeat is not None and repeat.count is not None
                else repeat.count_symbol if repeat is not None else "N"
            )
            annotations.append(
                PublicationAnnotation(
                    annotation_id="annotation:spectral-period-block-repeat",
                    target_node_id=group.node_id,
                    text=f"Spectral period block repeated {count} times",
                    kind="repeat",
                )
            )
        elif not semantic_nodes and residual_edges and internal:
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
            semantic_node = semantic_nodes.get(node.node_id)
            if semantic_node is not None:
                publication_nodes.append(semantic_node)
                exact_to_publication[node.node_id] = semantic_node.node_id
                continue
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
        miniatures = list(semantic_miniatures)
        input_node = next(
            (node for node in publication_nodes if node.kind is PublicationNodeKind.INPUT),
            None,
        )
        if input_node is not None:
            miniatures.append(
                PublicationMiniature(
                    miniature_id="miniature:input-flow-schematic",
                    target_node_id=input_node.node_id,
                    kind=PublicationMiniatureKind.SIGNAL_PREVIEW,
                    evidence_kind=MiniatureEvidenceKind.DETERMINISTIC_SCHEMATIC,
                    disclosure=MiniatureDisclosure.ILLUSTRATIVE,
                    label="Illustrative input flow (not runtime data)",
                    member_node_ids=input_node.member_node_ids,
                )
            )
        if (
            group is not None
            and group.kind is PublicationNodeKind.REPEAT_GROUP
            and spectral_period_match is None
        ):
            miniatures.extend(
                [
                    PublicationMiniature(
                        miniature_id="miniature:transformer-repeat-equation",
                        target_node_id=group.node_id,
                        kind=PublicationMiniatureKind.EQUATION_NOTE,
                        evidence_kind=MiniatureEvidenceKind.PUBLICATION_ANNOTATION,
                        disclosure=MiniatureDisclosure.EVIDENCE,
                        label="N x repeated encoder block",
                        member_node_ids=group.member_node_ids,
                    ),
                    PublicationMiniature(
                        miniature_id="miniature:transformer-repeat-inset",
                        target_node_id=group.node_id,
                        kind=PublicationMiniatureKind.INSET_CALLOUT,
                        evidence_kind=MiniatureEvidenceKind.PUBLICATION_ANNOTATION,
                        disclosure=MiniatureDisclosure.EVIDENCE,
                        label="Open repeated-block detail",
                        member_node_ids=group.member_node_ids,
                    ),
                ]
            )
        if spectral_period_match is not None and group is not None:
            miniatures.extend(
                [
                    PublicationMiniature(
                        miniature_id="miniature:spectral-period-schematic",
                        target_node_id=group.node_id,
                        kind=PublicationMiniatureKind.SIGNAL_PREVIEW,
                        evidence_kind=MiniatureEvidenceKind.DETERMINISTIC_SCHEMATIC,
                        disclosure=MiniatureDisclosure.ILLUSTRATIVE,
                        label="Schematic period discovery (not runtime periods)",
                        member_node_ids=group.member_node_ids,
                    ),
                    PublicationMiniature(
                        miniature_id="miniature:spectral-period-detail-inset",
                        target_node_id=group.node_id,
                        kind=PublicationMiniatureKind.INSET_CALLOUT,
                        evidence_kind=MiniatureEvidenceKind.PUBLICATION_ANNOTATION,
                        disclosure=MiniatureDisclosure.EVIDENCE,
                        label="FFT, period paths, aggregation, and residual are source-backed",
                        member_node_ids=group.member_node_ids,
                    ),
                ]
            )
        return PublicationIR(
            publication_id=f"publication:{exact.ir_id.removeprefix('ir:')}",
            exact_ir_id=exact.ir_id,
            project_id=exact.project_id,
            source_revision=exact.source_revision,
            nodes=publication_nodes,
            edges=publication_edges,
            annotations=annotations,
            miniatures=miniatures,
            omitted_exact_node_ids=omitted,
            omitted_exact_edge_ids=sorted(omitted_edges),
        )
