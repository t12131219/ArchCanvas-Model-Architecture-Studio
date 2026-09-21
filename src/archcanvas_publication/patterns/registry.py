"""Pattern selection over Exact IR metadata, never over project files."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

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

    def match(self, exact: ArchitectureIR) -> list[PatternMatch]:
        raw_evidence = exact.metadata.get("publication_pattern_evidence", [])
        if not isinstance(raw_evidence, list):
            return []
        matches: list[PatternMatch] = []
        known_node_ids = {node.node_id for node in exact.nodes}
        for item in raw_evidence:
            if not isinstance(item, dict) or item.get("pattern_id") not in {
                "timesnet_v1", "transformer_encoder_layer_v1"
            }:
                continue
            pattern_id = item["pattern_id"]
            root_ids = item.get("root_node_ids")
            anchors = item.get("source_anchor_ids")
            markers = item.get("markers")
            parameters = item.get("resolved_parameters", {})
            if not (
                isinstance(root_ids, list)
                and root_ids
                and all(isinstance(node_id, str) and node_id in known_node_ids for node_id in root_ids)
                and isinstance(anchors, list)
                and len(anchors) == (8 if pattern_id == "timesnet_v1" else 4)
                and all(isinstance(anchor, str) for anchor in anchors)
                and isinstance(markers, dict)
                and (
                    {
                        "fft", "top_k", "period_loop", "reshape_1d_to_2d", "inception",
                        "reshape_2d_to_1d", "adaptive_aggregation", "residual",
                    }
                    if pattern_id == "timesnet_v1"
                    else {"layer_construction", "repeat_loop", "layer_norm", "forecast_head"}
                ) <= set(markers)
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
                        if pattern_id == "timesnet_v1"
                        else {
                            "attention_internal": "delegated to the confirmed TransformerEncoderLayer member",
                            "residual_norm_internal": "not reified as guessed child nodes",
                        }
                    ),
                    overview_template=(
                        "timesnet_overview_v1"
                        if pattern_id == "timesnet_v1"
                        else "transformer_encoder_overview_v1"
                    ),
                    detail_template=(
                        "timesblock_detail_v1"
                        if pattern_id == "timesnet_v1"
                        else "transformer_encoder_layer_detail_v1"
                    ),
                )
            )
        return matches
