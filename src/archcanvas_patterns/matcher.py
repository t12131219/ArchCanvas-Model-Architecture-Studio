from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from archcanvas_core.models import (
    ArchitectureIR,
    PatternCandidateReview,
    PatternDistribution,
    PatternMatch,
    PatternPackManifest,
    PatternPackReceipt,
    PatternPredicate,
    PatternStage,
    SemanticAnnotation,
    SemanticAnnotationOverlay,
)

from .registry import PatternRegistry


def exact_ir_digest(architecture: ArchitectureIR) -> str:
    payload = json.dumps(
        architecture.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _matches(value: Any, predicate: PatternPredicate) -> bool:
    if predicate.operator == "exists":
        return value is not None
    if predicate.operator == "contains":
        if isinstance(value, (list, tuple, set)):
            return predicate.value in value
        return str(predicate.value).lower() in str(value).lower()
    return value == predicate.value or str(value) == str(predicate.value)


def _evaluate(
    architecture: ArchitectureIR, predicate: PatternPredicate
) -> tuple[bool, list[str]]:
    hits: list[str] = []
    if predicate.fact == "node-kind":
        hits = [node.node_id for node in architecture.nodes if _matches(node.kind.value, predicate)]
    elif predicate.fact == "node-attribute":
        hits = [
            node.node_id
            for node in architecture.nodes
            if _matches(node.attributes.get(predicate.field or ""), predicate)
        ]
    elif predicate.fact == "edge-type":
        hits = [edge.edge_id for edge in architecture.edges if _matches(edge.edge_type.value, predicate)]
    elif predicate.fact == "edge-route":
        hits = [
            edge.edge_id
            for edge in architecture.edges
            if _matches(
                f"{edge.producer_id}:{edge.producer_port}->{edge.consumer_id}:{edge.consumer_port}",
                predicate,
            )
        ]
    elif predicate.fact == "shape-axis":
        for edge in architecture.edges:
            if _matches(edge.symbolic_shape, predicate) or any(
                _matches(axis, predicate) for axis in edge.semantic_axes
            ):
                hits.append(edge.edge_id)
    elif predicate.fact == "repeat-kind":
        hits = [
            repeat.repeat_id for repeat in architecture.repeats if _matches(repeat.kind.value, predicate)
        ]
    elif predicate.fact == "execution-predicate":
        hits = [
            node.node_id
            for node in architecture.nodes
            if _matches(node.execution_predicate, predicate)
        ]
    elif predicate.fact == "name-hint":
        hits = [
            node.node_id
            for node in architecture.nodes
            if _matches(
                " ".join(filter(None, (node.node_id, node.semantic_name, node.source_symbol))),
                predicate,
            )
        ]
    return len(hits) >= predicate.min_count, hits


@dataclass(frozen=True)
class _Evaluated:
    manifest: PatternPackManifest
    match: PatternMatch
    annotations: list[SemanticAnnotation]


_STAGE_ORDER = {
    PatternStage.STRUCTURE: 0,
    PatternStage.DATAFLOW: 1,
    PatternStage.SHAPE: 2,
    PatternStage.SHARING_CONTROL: 3,
    PatternStage.WEAK_NAME: 4,
}


def _annotations(
    architecture: ArchitectureIR,
    manifest: PatternPackManifest,
) -> list[SemanticAnnotation]:
    result: list[SemanticAnnotation] = []
    for rule in manifest.annotations:
        passed, ids = _evaluate(architecture, rule.selector)
        if not passed:
            continue
        result.append(
            SemanticAnnotation(
                annotation_id=f"annotation:{manifest.pack_id}:{rule.rule_id}",
                pack_id=manifest.pack_id,
                canonical_node_ids=ids,
                semantic_role=rule.semantic_role,
                group_id=rule.group_id,
                recommended_level=rule.recommended_level,
                glyph=rule.glyph,
                layout_family=rule.layout_family,
                label=rule.label,
                predicate_ids=[rule.selector.predicate_id],
            )
        )
    return result


def _evaluate_pack(architecture: ArchitectureIR, manifest: PatternPackManifest) -> _Evaluated:
    matched_ids: list[str] = []
    matched_predicates: list[str] = []
    reasons: list[str] = []
    for predicate in sorted(manifest.required, key=lambda item: _STAGE_ORDER[item.stage]):
        passed, ids = _evaluate(architecture, predicate)
        if not passed:
            reasons.append(f"required_failed:{predicate.stage.value}:{predicate.predicate_id}")
        else:
            matched_predicates.append(predicate.predicate_id)
            matched_ids.extend(ids)
    for predicate in sorted(manifest.forbidden, key=lambda item: _STAGE_ORDER[item.stage]):
        passed, ids = _evaluate(architecture, predicate)
        if passed:
            reasons.append(f"forbidden_matched:{predicate.stage.value}:{predicate.predicate_id}")
            matched_ids.extend(ids)
    hard_failed = bool(reasons)
    optional_non_name = [item for item in manifest.optional if item.stage is not PatternStage.WEAK_NAME]
    name_hints = [item for item in manifest.optional if item.stage is PatternStage.WEAK_NAME]
    optional_hits = 0
    name_hits = 0
    for predicate in sorted(
        [*optional_non_name, *name_hints], key=lambda item: _STAGE_ORDER[item.stage]
    ):
        passed, ids = _evaluate(architecture, predicate)
        if passed:
            matched_predicates.append(predicate.predicate_id)
            matched_ids.extend(ids)
            if predicate.stage is PatternStage.WEAK_NAME:
                name_hits += 1
            else:
                optional_hits += 1
    score = 0.0
    if not hard_failed:
        score += manifest.score.required_weight
        if optional_non_name:
            score += manifest.score.optional_weight * optional_hits / len(optional_non_name)
        if name_hints:
            score += manifest.score.weak_name_weight * name_hits / len(name_hints)
    score = min(1.0, round(score, 6))
    accepted = not hard_failed and score >= manifest.score.minimum
    if not accepted and not reasons:
        reasons.append(f"score_below_minimum:{score:.6f}<{manifest.score.minimum:.6f}")
    status = "matched" if accepted else "rejected"
    if accepted and manifest.distribution is PatternDistribution.SESSION_CANDIDATE:
        status = "candidate-match"
    return _Evaluated(
        manifest=manifest,
        match=PatternMatch(
            pack_id=manifest.pack_id,
            distribution=manifest.distribution,
            status=status,
            score=score,
            matched_predicate_ids=sorted(set(matched_predicates)),
            matched_canonical_ids=sorted(set(matched_ids)),
            reasons=reasons,
        ),
        annotations=_annotations(architecture, manifest) if accepted else [],
    )


def _annotations_conflict(left: _Evaluated, right: _Evaluated) -> bool:
    for left_annotation in left.annotations:
        for right_annotation in right.annotations:
            if set(left_annotation.canonical_node_ids) & set(right_annotation.canonical_node_ids) and (
                left_annotation.semantic_role != right_annotation.semantic_role
                or left_annotation.group_id != right_annotation.group_id
            ):
                return True
    return False


def apply_pattern_packs(
    architecture: ArchitectureIR,
    registry: PatternRegistry,
    *,
    enabled: bool = True,
) -> tuple[SemanticAnnotationOverlay, PatternPackReceipt]:
    if not isinstance(registry, PatternRegistry):
        raise TypeError("registry must be a PatternRegistry")
    before = exact_ir_digest(architecture)
    if not enabled:
        overlay = SemanticAnnotationOverlay(
            architecture_id=architecture.architecture_id,
            exact_ir_digest=before,
            status="disabled",
            reasons=["pattern_packs_disabled"],
        )
        return overlay, PatternPackReceipt(
            architecture_id=architecture.architecture_id,
            status="disabled",
            loaded_packs=[],
            matches=[],
            exact_ir_digest_before=before,
            exact_ir_digest_after=exact_ir_digest(architecture),
        )

    evaluated = [_evaluate_pack(architecture, item) for item in registry.manifests]
    eligible = [
        item
        for item in evaluated
        if item.match.status == "matched"
        and item.manifest.distribution is not PatternDistribution.SESSION_CANDIDATE
    ]
    builtin_matches = [
        item for item in eligible if item.manifest.distribution is PatternDistribution.BUILTIN
    ]
    if builtin_matches:
        maximum_builtin_specificity = max(len(item.manifest.required) for item in builtin_matches)
        insufficient_workspace_ids = {
            item.manifest.pack_id
            for item in eligible
            if item.manifest.distribution is PatternDistribution.WORKSPACE
            and len(item.manifest.required) <= maximum_builtin_specificity
        }
        if insufficient_workspace_ids:
            evaluated = [
                _Evaluated(
                    manifest=item.manifest,
                    match=item.match.model_copy(
                        update={
                            "status": "rejected",
                            "reasons": [*item.match.reasons, "workspace_not_more_specific"],
                        }
                    ),
                    annotations=[],
                )
                if item.manifest.pack_id in insufficient_workspace_ids
                else item
                for item in evaluated
            ]
            eligible = [
                item for item in evaluated if item.match.status == "matched"
            ]
    ambiguous: list[_Evaluated] = []
    selected: list[_Evaluated] = []
    if eligible:
        top_rank = max((item.match.score, len(item.manifest.required)) for item in eligible)
        top = [
            item
            for item in eligible
            if (item.match.score, len(item.manifest.required)) == top_rank
        ]
        cross_distribution_conflict = any(
            _annotations_conflict(left, right)
            for index, left in enumerate(eligible)
            for right in eligible[index + 1 :]
            if {left.manifest.distribution, right.manifest.distribution}
            == {PatternDistribution.BUILTIN, PatternDistribution.WORKSPACE}
        )
        if len(top) > 1 or cross_distribution_conflict:
            ambiguous = top if len(top) > 1 else eligible
        else:
            selected = top

    matches = [item.match for item in evaluated]
    if ambiguous:
        ambiguous_ids = {item.manifest.pack_id for item in ambiguous}
        matches = [
            match.model_copy(
                update={"status": "ambiguous", "reasons": [*match.reasons, "ambiguous_pattern"]}
            )
            if match.pack_id in ambiguous_ids
            else match
            for match in matches
        ]
    status = "ambiguous" if ambiguous else "matched" if selected else "generic"
    annotations = [annotation for item in selected for annotation in item.annotations]
    reasons = ["ambiguous_pattern"] if ambiguous else ([] if selected else ["no_pattern_matched"])
    after = exact_ir_digest(architecture)
    overlay = SemanticAnnotationOverlay(
        architecture_id=architecture.architecture_id,
        exact_ir_digest=before,
        status=status,
        applied_pack_ids=[item.manifest.pack_id for item in selected],
        annotations=annotations,
        reasons=reasons,
    )
    receipt = PatternPackReceipt(
        architecture_id=architecture.architecture_id,
        status=status,
        loaded_packs=registry.loads,
        matches=matches,
        selected_pack_ids=overlay.applied_pack_ids,
        exact_ir_digest_before=before,
        exact_ir_digest_after=after,
    )
    return overlay, receipt


def build_candidate_reviews(
    architecture: ArchitectureIR,
    registry: PatternRegistry,
) -> list[PatternCandidateReview]:
    before = exact_ir_digest(architecture)
    reviews: list[PatternCandidateReview] = []
    for manifest in registry.manifests:
        if manifest.distribution is not PatternDistribution.SESSION_CANDIDATE:
            continue
        evaluated = _evaluate_pack(architecture, manifest)
        proven = set(evaluated.match.matched_predicate_ids)
        declared = {item.predicate_id for item in [*manifest.required, *manifest.optional]}
        reviews.append(
            PatternCandidateReview(
                pack_id=manifest.pack_id,
                match_status=evaluated.match.status,
                match_basis=evaluated.match.matched_predicate_ids,
                unproven_predicates=sorted(declared - proven),
                counterexample_risks=[
                    *manifest.known_limitations,
                    *[f"inventory:{item}" for item in manifest.tests.negative],
                ],
                preview_annotations=evaluated.annotations,
                exact_ir_digest_before=before,
                exact_ir_digest_after=exact_ir_digest(architecture),
            )
        )
    return reviews
