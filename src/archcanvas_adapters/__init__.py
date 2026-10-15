"""Source-bound, data-only adapters; submitted Python is never executed."""
from .registry import (
    AdapterError, AdapterRegistry, scaffold_adapter, scaffold_adapter_files,
    validate_adapter, validate_adapter_files, apply_preview_adapters,
    automatic_preview_adapters, enrich_preview,
)
from .source_rules import validate_rule, compile_rule_adapter_files, validate_rule_adapter_files

__all__ = [
    'AdapterError', 'AdapterRegistry', 'scaffold_adapter', 'scaffold_adapter_files',
    'validate_adapter', 'validate_adapter_files', 'apply_preview_adapters',
    'automatic_preview_adapters', 'enrich_preview',
    'validate_rule', 'compile_rule_adapter_files', 'validate_rule_adapter_files',
]
