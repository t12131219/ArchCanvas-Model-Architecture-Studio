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
    prepare_transaction,
    verify_transaction,
)
from .store import load_transaction

__all__ = [
    "TRANSFORM_REGISTRY",
    "commit_transaction",
    "discard_transaction",
    "load_transaction",
    "plan_connection",
    "prepare_transaction",
    "unsupported_intent_proposal",
    "validate_structural_oracle",
    "verify_transaction",
]
