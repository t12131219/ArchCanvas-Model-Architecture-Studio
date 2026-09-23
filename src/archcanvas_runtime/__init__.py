"""Opt-in isolated runtime evidence collection."""

from .orchestrator import RuntimeTraceError, trace_runtime

__all__ = ["RuntimeTraceError", "trace_runtime"]
