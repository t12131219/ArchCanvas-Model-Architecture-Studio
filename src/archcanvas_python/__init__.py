"""Independent, non-executing ArchCanvas static frontend.

Analysis uses Python's standard-library AST and never executes user code.
The separate archcanvas_transactions package registers a bounded, formatting-
preserving explicit float-token parameter transform; this module only analyzes.
"""

from .frontend import AnalysisError, analyze_project, analyze_source

__all__ = ["AnalysisError", "analyze_project", "analyze_source"]
