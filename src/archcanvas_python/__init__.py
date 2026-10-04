"""Independent, non-executing ArchCanvas static frontend.

The first implementation intentionally uses Python's standard-library AST. It
does not implement source writeback. LibCST belongs to the later formatting-
preserving semantic transaction implementation, not this analysis-only slice.
"""

from .frontend import AnalysisError, analyze_project, analyze_source

__all__ = ["AnalysisError", "analyze_project", "analyze_source"]

