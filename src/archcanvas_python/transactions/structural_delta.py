"""Exact graph-delta declaration gate for the restricted structural splice."""

from __future__ import annotations

from archcanvas_core.models.patch import ExpectedGraphDelta
from archcanvas_core.models.validation import ObservedGraphDelta

from .set_parameter import TransactionRejected


def require_exact_structural_delta(
    expected: ExpectedGraphDelta,
    observed: ObservedGraphDelta,
    *,
    added_node_id: str | None = None,
    removed_node_id: str | None = None,
    edge_additions: int,
    edge_removals: int,
) -> None:
    node_additions = [added_node_id] if added_node_id is not None else []
    node_removals = [removed_node_id] if removed_node_id is not None else []
    changes = (
        (expected.allowed_node_additions, observed.added_node_ids, node_additions),
        (expected.allowed_node_removals, observed.removed_node_ids, node_removals),
        (expected.allowed_node_modifications, observed.modified_node_ids, []),
        (expected.allowed_edge_additions, observed.added_edge_ids, None),
        (expected.allowed_edge_removals, observed.removed_edge_ids, None),
        (expected.allowed_edge_modifications, observed.modified_edge_ids, []),
    )
    if (
        any(set(declared) != set(actual) or (required is not None and set(actual) != set(required))
            for declared, actual, required in changes)
        or len(observed.added_edge_ids) != edge_additions
        or len(observed.removed_edge_ids) != edge_removals
        or expected.required_parameter_changes
        or observed.parameter_changes
        or observed.modified_repeat_ids
        or observed.identity_changes
        or not expected.require_identity_retention
    ):
        raise TransactionRejected(
            "STRUCTURAL_DELTA_DECLARATION_MISMATCH",
            "structural splice requires an exact node/edge delta with retained identities",
        )
