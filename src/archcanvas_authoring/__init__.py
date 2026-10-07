"""New authored graphs, separate from imported source-bound CanvasDocuments.

The contract consumes JSON data and generates fresh Python text. It never
imports a model, executes it, mutates a source project, or invents IR bindings.
"""

from .draft import DraftError, generate_model, module_catalog, validate_draft, verify_generated
from .source_import import import_source_draft, rebase_source_frontier
from .source_generation_groups import generate_grouped_source

__all__ = ["DraftError", "module_catalog", "validate_draft", "generate_model", "verify_generated", "import_source_draft", "rebase_source_frontier", "generate_grouped_source"]
