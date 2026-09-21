"""Explicit analyzer registration for source transactions.

The registry prevents a fixture analyzer from silently becoming the default for arbitrary
projects. Framework adapters register only the project shapes they can prove.
"""

from __future__ import annotations

from collections.abc import Callable

from archcanvas_core.models.architecture import ArchitectureIR
from archcanvas_core.models.source_identity import SourceIdentityDocument

from .fixture_analyzer import PROJECT_ID, analyze_transformer_fixture

Analyzer = Callable[[bytes], tuple[SourceIdentityDocument, ArchitectureIR]]


class AnalyzerUnavailable(LookupError):
    pass


class AnalyzerRegistry:
    def __init__(self) -> None:
        self._analyzers: dict[str, Analyzer] = {}

    def register(self, project_id: str, analyzer: Analyzer) -> None:
        if not project_id or project_id in self._analyzers:
            raise ValueError(f"analyzer already registered or invalid project id: {project_id!r}")
        self._analyzers[project_id] = analyzer

    def resolve(self, project_id: str) -> Analyzer:
        try:
            return self._analyzers[project_id]
        except KeyError as error:
            raise AnalyzerUnavailable(f"no analyzer registered for {project_id}") from error


def fixture_analyzer_registry() -> AnalyzerRegistry:
    registry = AnalyzerRegistry()
    registry.register(PROJECT_ID, analyze_transformer_fixture)
    return registry
