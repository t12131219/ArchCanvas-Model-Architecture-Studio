"""CST-backed inverse of the restricted Stage 8 LayerNorm splice."""

from __future__ import annotations

from hashlib import sha256

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from archcanvas_core.models.patch import RemoveLayerNormPatch
from archcanvas_core.models.source_identity import SourceAnchor

from ..source_revision import file_revision
from .set_parameter import TransformRejected, dotted_name, same_range


def _digest(value: str) -> str:
    return "sha256:" + sha256(value.encode("utf-8")).hexdigest()


class _RemoveLayerNormTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, module: cst.Module, patch: RemoveLayerNormPatch, constructor: SourceAnchor, forward: SourceAnchor) -> None:
        self.module, self.patch, self.constructor, self.forward = module, patch, constructor, forward
        self.constructor_removals = 0
        self.forward_removals = 0

    def _matches(self, node: cst.Call, anchor: SourceAnchor) -> bool:
        if not same_range(self.get_metadata(PositionProvider, node), anchor):
            return False
        if _digest(self.module.code_for_node(node)) == anchor.content_fingerprint:
            return True
        line = "".join(self.module.code.splitlines(keepends=True)[anchor.span.start.line - 1 : anchor.span.end.line])
        return _digest(line) == anchor.content_fingerprint

    def leave_SimpleStatementLine(self, original_node: cst.SimpleStatementLine, updated_node: cst.SimpleStatementLine):
        if len(original_node.body) != 1 or not isinstance(original_node.body[0], cst.Assign):
            return updated_node
        assignment = original_node.body[0]
        if not isinstance(assignment.value, cst.Call):
            return updated_node
        call = assignment.value
        if self._matches(call, self.constructor):
            if dotted_name(call.func) != "nn.LayerNorm":
                raise TransformRejected("REMOVE_CONSTRUCTOR_CALLEE_MISMATCH", self.constructor.anchor_id)
            if (
                len(assignment.targets) != 1
                or dotted_name(assignment.targets[0].target) != f"self.{self.patch.attribute_name}"
            ):
                raise TransformRejected("REMOVE_CONSTRUCTOR_TARGET_MISMATCH", self.constructor.anchor_id)
            self.constructor_removals += 1
            return cst.RemovalSentinel.REMOVE
        if not self._matches(call, self.forward):
            return updated_node
        if dotted_name(call.func) != f"self.{self.patch.attribute_name}":
            raise TransformRejected("REMOVE_FORWARD_CALLEE_MISMATCH", self.forward.anchor_id)
        if (
            len(assignment.targets) != 1
            or not isinstance(assignment.targets[0].target, cst.Name)
            or len(call.args) != 1
            or not isinstance(call.args[0].value, cst.Name)
            or assignment.targets[0].target.value != call.args[0].value.value
        ):
            raise TransformRejected("REMOVE_FORWARD_ARGUMENT_UNSUPPORTED", self.forward.anchor_id)
        self.forward_removals += 1
        return cst.RemovalSentinel.REMOVE


def apply_remove_layer_norm(
    raw_source: bytes,
    patch: RemoveLayerNormPatch,
    constructor: SourceAnchor,
    forward: SourceAnchor,
    base_revision: str,
) -> bytes:
    if file_revision(raw_source) != base_revision:
        raise TransformRejected("STALE_TARGET_FILE_REVISION", constructor.relative_file)
    if constructor.file_revision != base_revision or forward.file_revision != base_revision:
        raise TransformRejected("STALE_ANCHOR_REVISION", constructor.relative_file)
    if constructor.relative_file != forward.relative_file:
        raise TransformRejected("REMOVE_CROSS_FILE_UNSUPPORTED", forward.relative_file)
    if (
        patch.constructor_anchor_content_fingerprint != constructor.content_fingerprint
        or patch.forward_anchor_content_fingerprint != forward.content_fingerprint
    ):
        raise TransformRejected("REMOVE_ANCHOR_FINGERPRINT_MISMATCH", patch.patch_id)
    module = cst.parse_module(raw_source.decode("utf-8"))
    transformer = _RemoveLayerNormTransformer(module, patch, constructor, forward)
    updated = MetadataWrapper(module).visit(transformer)
    if transformer.constructor_removals != 1 or transformer.forward_removals != 1:
        raise TransformRejected(
            "REMOVE_MATCH_CARDINALITY",
            f"constructor={transformer.constructor_removals}, forward={transformer.forward_removals}",
        )
    return updated.code.encode("utf-8")
