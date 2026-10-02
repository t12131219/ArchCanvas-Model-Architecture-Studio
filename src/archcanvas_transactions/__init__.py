"""Safe registered source transactions and no-permission structural proposals."""

from .registry import (
    TRANSFORM_REGISTRY,
    plan_connection,
    unsupported_intent_proposal,
    validate_structural_oracle,
)
from .service import (
    commit_transaction,
    discard_transaction,
    prepare_freeform_transaction,
    prepare_transaction,
    recover_incomplete_transactions,
    resolve_parameter_edit_context,
    resolve_parameter_edit_contexts,
    verify_transaction,
)
from .state_migration import build_state_migration_plan, state_inventory_digest
from .store import load_transaction

__all__ = [
    "TRANSFORM_REGISTRY",
    "build_state_migration_plan",
    "commit_transaction",
    "discard_transaction",
    "load_transaction",
    "plan_connection",
    "prepare_freeform_transaction",
    "prepare_transaction",
    "recover_incomplete_transactions",
    "resolve_parameter_edit_context",
    "resolve_parameter_edit_contexts",
    "state_inventory_digest",
    "unsupported_intent_proposal",
    "validate_structural_oracle",
    "verify_transaction",
]
