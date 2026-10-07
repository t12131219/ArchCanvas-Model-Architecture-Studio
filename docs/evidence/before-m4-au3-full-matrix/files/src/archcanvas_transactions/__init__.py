"""Bounded static semantic transactions with explicit review and guarded writeback."""

from .service import TransactionError, TransactionManager

__all__ = ["TransactionError", "TransactionManager"]
