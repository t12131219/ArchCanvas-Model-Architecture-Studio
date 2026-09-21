from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, TypeAlias

from pydantic import Field, model_validator

from .architecture import NodeId
from .common import StrictModel
from .source_identity import AnchorId, Sha256

Scalar: TypeAlias = None | bool | int | float | str
PatchId = Annotated[str, Field(pattern=r"^patch:[A-Za-z0-9._-]+$")]
PatchSetId = Annotated[str, Field(pattern=r"^patchset:[A-Za-z0-9._-]+$")]


def _same_scalar(left: Scalar, right: Scalar) -> bool:
    return type(left) is type(right) and left == right


class ParameterChange(StrictModel):
    node_id: NodeId
    parameter: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_.-]*$")
    before: Scalar
    after: Scalar

    @model_validator(mode="after")
    def value_changes(self) -> ParameterChange:
        if _same_scalar(self.before, self.after):
            raise ValueError("parameter change must change value and type")
        return self


class ExpectedGraphDelta(StrictModel):
    required_parameter_changes: list[ParameterChange] = Field(min_length=1)
    allowed_node_additions: list[str]
    allowed_node_removals: list[str]
    allowed_node_modifications: list[str]
    allowed_edge_additions: list[str]
    allowed_edge_removals: list[str]
    allowed_edge_modifications: list[str]
    require_identity_retention: bool


class PatchTarget(StrictModel):
    node_id: NodeId
    parameter: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_.-]*$")
    anchor_id: AnchorId


class SetParameterPatch(StrictModel):
    patch_id: PatchId
    scope: Literal["architecture"] = "architecture"
    operation: Literal["set_parameter"] = "set_parameter"
    target: PatchTarget
    before: Scalar
    after: Scalar
    anchor_content_fingerprint: Sha256
    expected_delta: ExpectedGraphDelta

    @model_validator(mode="after")
    def expected_delta_matches_payload(self) -> SetParameterPatch:
        expected = ParameterChange(
            node_id=self.target.node_id,
            parameter=self.target.parameter,
            before=self.before,
            after=self.after,
        )
        if self.expected_delta.required_parameter_changes != [expected]:
            raise ValueError("set_parameter must declare exactly its own parameter delta")
        return self


class PatchSet(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    patch_set_id: PatchSetId
    project_id: str = Field(min_length=1)
    base_source_revision: Sha256
    created_at: datetime
    created_by: Literal["user", "agent", "system"]
    patches: list[SetParameterPatch] = Field(min_length=1, max_length=1)

    @model_validator(mode="after")
    def unique_patch_ids(self) -> PatchSet:
        if len({patch.patch_id for patch in self.patches}) != len(self.patches):
            raise ValueError("patch_id values must be unique")
        return self
