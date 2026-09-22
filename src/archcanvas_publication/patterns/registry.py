"""Pattern selection over Exact IR metadata, never over project files."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from archcanvas_core.models.architecture import ArchitectureIR


class PatternConfidence(str, Enum):
    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class PatternMatch:
    pattern_id: str
    confidence: PatternConfidence
    root_node_ids: list[str]
    member_node_ids: list[str]
    source_anchor_ids: list[str]
    resolved_parameters: dict[str, object]
    omitted_node_reasons: dict[str, str]
    overview_template: str | None
    detail_template: str | None


class PublicationPatternRegistry:
    """Select only complete source signatures emitted by static recovery."""

    _REQUIRED_MARKERS: ClassVar[dict[str, set[str]]] = {
        "spectral_period_inception_block_v1": {
            "fft", "top_k", "period_loop", "reshape_1d_to_2d", "inception",
            "reshape_2d_to_1d", "adaptive_aggregation", "residual",
        },
        "encoder_attention_stack_v1": {
            "layer_construction", "repeat_loop", "layer_norm", "forecast_head",
        },
        "decoder_cross_attention_stack_v1": {
            "root_decoder_root_construction",
            "root_decoder_root_layer_repeat",
            "root_decoder_root_norm",
            "root_decoder_output_head",
            "root_decoder_task_call",
            "root_decoder_task_dispatch",
            "decoder_module_list",
            "decoder_repeat_loop",
            "decoder_norm_call",
            "decoder_projection_call",
            "decoder_layer_self_attention",
            "decoder_layer_norm1",
            "decoder_layer_cross_attention",
            "decoder_layer_norm2",
            "decoder_layer_feed_forward_residual",
            "decoder_layer_norm3",
        },
        "topk_expert_router_v1": {
            "router_root_construction",
            "router_root_call",
            "router_experts",
            "router_softmax",
            "router_top_k",
            "router_gating_call",
            "router_dispatcher",
            "router_dispatch",
            "router_expert_loop",
            "router_combine",
            "router_expert_constructor",
        },
        "decomposition_linear_fusion_v1": {
            "series_root_root_construction",
            "series_root_root_call",
            "series_cluster_experts",
            "series_cluster_expert_loop",
            "series_extractor_decomposition",
            "series_extractor_seasonal_linear",
            "series_extractor_trend_linear",
            "series_extractor_decomposition_call",
            "series_extractor_seasonal_call",
            "series_extractor_trend_call",
            "series_extractor_fuse",
            "series_decomposition_moving_average",
            "series_decomposition_moving_average_call",
            "series_decomposition_seasonal_residual",
        },
        "frequency_gumbel_mask_v1": {
            "mask_root_construction",
            "mask_root_call",
            "mask_rfft",
            "mask_pairwise_difference",
            "mask_learned_metric",
            "mask_probability",
            "mask_gumbel_sample",
            "mask_forward_sample",
        },
        "masked_attention_stack_v1": {
            "channel_root_construction",
            "channel_root_layer_repeat",
            "channel_root_norm",
            "channel_root_masked_call",
            "channel_root_head",
            "channel_root_head_call",
            "channel_encoder_module_list",
            "channel_encoder_repeat_loop",
            "channel_encoder_norm_call",
            "channel_layer_attention",
            "channel_layer_attention_residual",
            "channel_layer_norm1",
            "channel_layer_feed_forward_residual",
            "channel_layer_norm2",
        },
    }

    _CROSS_FILE_ENCODER_MARKERS: ClassVar[set[str]] = {
        "root_encoder_root_construction",
        "root_encoder_root_layer_repeat",
        "root_encoder_root_norm",
        "root_encoder_task_call",
        "root_encoder_task_dispatch",
        "encoder_module_list",
        "encoder_repeat_loop",
        "encoder_norm_call",
        "encoder_layer_attention",
        "encoder_layer_attention_residual",
        "encoder_layer_norm1",
        "encoder_layer_feed_forward_residual",
        "encoder_layer_norm2",
    }

    def match(self, exact: ArchitectureIR) -> list[PatternMatch]:
        raw_evidence = exact.metadata.get("publication_pattern_evidence", [])
        if not isinstance(raw_evidence, list):
            return []
        matches: list[PatternMatch] = []
        known_node_ids = {node.node_id for node in exact.nodes}
        for item in raw_evidence:
            if not isinstance(item, dict) or item.get("pattern_id") not in self._REQUIRED_MARKERS:
                continue
            pattern_id = item["pattern_id"]
            root_ids = item.get("root_node_ids")
            anchors = item.get("source_anchor_ids")
            markers = item.get("markers")
            parameters = item.get("resolved_parameters", {})
            required_markers = (
                self._CROSS_FILE_ENCODER_MARKERS
                if pattern_id == "encoder_attention_stack_v1"
                and set(markers) == self._CROSS_FILE_ENCODER_MARKERS
                else self._REQUIRED_MARKERS[pattern_id]
            )
            node_anchor_ids = (
                {
                    anchor_id
                    for node_id in root_ids
                    if node_id in known_node_ids
                    for anchor_id in exact.node(node_id).source_anchor_ids
                }
                if isinstance(root_ids, list)
                else set()
            )
            if not (
                isinstance(root_ids, list)
                and root_ids
                and all(isinstance(node_id, str) and node_id in known_node_ids for node_id in root_ids)
                and isinstance(anchors, list)
                and all(isinstance(anchor, str) for anchor in anchors)
                and isinstance(markers, dict)
                and set(markers) == required_markers
                and set(markers.values()) == set(anchors)
                and set(anchors) <= node_anchor_ids
                and isinstance(parameters, dict)
            ):
                continue
            matches.append(
                PatternMatch(
                    pattern_id=pattern_id,
                    confidence=PatternConfidence.CONFIRMED,
                    root_node_ids=sorted(root_ids),
                    member_node_ids=sorted(root_ids),
                    source_anchor_ids=sorted(anchors),
                    resolved_parameters=dict(sorted(parameters.items())),
                    omitted_node_reasons=(
                        {
                            "reshape/permutation/padding": "represented by the source-backed 1D-to-2D semantic stage",
                            "unsqueeze/repeat": "represented by adaptive aggregation without inventing runtime weights",
                        }
                        if pattern_id == "spectral_period_inception_block_v1"
                        else {
                            "attention_internal": "proven in a source-backed imported layer without flattening it",
                            "residual_norm_internal": "preserved as anchored cross-file evidence, not guessed child nodes",
                        }
                    ),
                    overview_template={
                        "spectral_period_inception_block_v1": "spectral_period_inception_overview_v1",
                        "encoder_attention_stack_v1": "encoder_attention_stack_overview_v1",
                        "decoder_cross_attention_stack_v1": "decoder_cross_attention_stack_overview_v1",
                        "topk_expert_router_v1": "topk_expert_router_overview_v1",
                        "decomposition_linear_fusion_v1": "decomposition_linear_fusion_overview_v1",
                        "frequency_gumbel_mask_v1": "frequency_gumbel_mask_overview_v1",
                        "masked_attention_stack_v1": "masked_attention_stack_overview_v1",
                    }[pattern_id],
                    detail_template={
                        "spectral_period_inception_block_v1": "spectral_period_inception_detail_v1",
                        "encoder_attention_stack_v1": "encoder_attention_stack_detail_v1",
                        "decoder_cross_attention_stack_v1": "decoder_cross_attention_stack_detail_v1",
                        "topk_expert_router_v1": "topk_expert_router_detail_v1",
                        "decomposition_linear_fusion_v1": "decomposition_linear_fusion_detail_v1",
                        "frequency_gumbel_mask_v1": "frequency_gumbel_mask_detail_v1",
                        "masked_attention_stack_v1": "masked_attention_stack_detail_v1",
                    }[pattern_id],
                )
            )
        return matches
