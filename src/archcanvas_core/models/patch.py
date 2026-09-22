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
    required_parameter_changes: list[ParameterChange] = Field(default_factory=list)
    allowed_node_additions: list[str] = Field(default_factory=list)
    allowed_node_removals: list[str] = Field(default_factory=list)
    allowed_node_modifications: list[str] = Field(default_factory=list)
    allowed_edge_additions: list[str] = Field(default_factory=list)
    allowed_edge_removals: list[str] = Field(default_factory=list)
    allowed_edge_modifications: list[str] = Field(default_factory=list)
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


class InsertLayerNormPatch(StrictModel):
    """Stage 8's first structural operation: splice one LayerNorm into a proven data edge."""

    patch_id: PatchId
    scope: Literal["architecture"] = "architecture"
    operation: Literal["insert_layer_norm"] = "insert_layer_norm"
    source_node_id: NodeId
    target_node_id: NodeId
    constructor_anchor_id: AnchorId
    forward_anchor_id: AnchorId
    attribute_name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    normalized_shape: int = Field(ge=1)
    constructor_anchor_content_fingerprint: Sha256
    forward_anchor_content_fingerprint: Sha256
    expected_delta: ExpectedGraphDelta

    @model_validator(mode="after")
    def splice_is_non_degenerate(self) -> InsertLayerNormPatch:
        if self.source_node_id == self.target_node_id:
            raise ValueError("insert_layer_norm source and target must differ")
        if self.constructor_anchor_id == self.forward_anchor_id:
            raise ValueError("insert_layer_norm requires distinct constructor and forward anchors")
        if self.expected_delta.required_parameter_changes:
            raise ValueError("insert_layer_norm cannot declare parameter changes")
        if not self.expected_delta.allowed_node_additions:
            raise ValueError("insert_layer_norm must declare its added node")
        return self


# Keep v1 payloads valid: ``set_parameter`` historically relied on its default operation field.
# The two strict shapes have disjoint required fields, so Pydantic can safely select their union.
Patch = SetParameterPatch | InsertLayerNormPatch


class PatchSet(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    patch_set_id: PatchSetId
    project_id: str = Field(min_length=1)
    base_source_revision: Sha256
    created_at: datetime
    created_by: Literal["user", "agent", "system"]
    patches: list[Patch] = Field(min_length=1, max_length=1)

    @model_validator(mode="after")
    def unique_patch_ids(self) -> PatchSet:
        if len({patch.patch_id for patch in self.patches}) != len(self.patches):
            raise ValueError("patch_id values must be unique")
        return self
