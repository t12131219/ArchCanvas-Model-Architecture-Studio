from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from .common import StrictModel


class ObservedParameterChange(StrictModel):
    node_id: str
    parameter: str
    before: Any
    after: Any


class IdentityChange(StrictModel):
    node_id: str
    before_identity_id: str
    after_identity_id: str


class ObservedGraphDelta(StrictModel):
    added_node_ids: list[str] = Field(default_factory=list)
    removed_node_ids: list[str] = Field(default_factory=list)
    modified_node_ids: list[str] = Field(default_factory=list)
    added_edge_ids: list[str] = Field(default_factory=list)
    removed_edge_ids: list[str] = Field(default_factory=list)
    modified_edge_ids: list[str] = Field(default_factory=list)
    modified_repeat_ids: list[str] = Field(default_factory=list)
    parameter_changes: list[ObservedParameterChange] = Field(default_factory=list)
    identity_changes: list[IdentityChange] = Field(default_factory=list)


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ValidationIssue(StrictModel):
    severity: Severity
    code: str
    message: str
    node_ids: list[str] = Field(default_factory=list)
    edge_ids: list[str] = Field(default_factory=list)
    blocking: bool


class ValidationReport(StrictModel):
    validator: str = "graph_delta_v1"
    blocking: bool
    issues: list[ValidationIssue]
