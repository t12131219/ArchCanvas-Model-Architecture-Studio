"""CST-backed Stage 8 splice for one source-proven ``nn.LayerNorm`` module."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from archcanvas_core.models.patch import InsertLayerNormPatch
from archcanvas_core.models.source_identity import SourceAnchor

from ..source_revision import file_revision
from .set_parameter import TransformRejected, dotted_name, same_range


def _digest(value: str) -> str:
    return "sha256:" + sha256(value.encode("utf-8")).hexdigest()


def _call_matches_anchor(
    transformer: cst.CSTTransformer, node: cst.Call, anchor: SourceAnchor, module: cst.Module
) -> bool:
    if not same_range(transformer.get_metadata(PositionProvider, node), anchor):
        return False
    if _digest(module.code_for_node(node)) == anchor.content_fingerprint:
        return True
    # Static adapter v1 constructor anchors fingerprinted their complete source line while retaining
    # a Call span. Keep this bounded compatibility path tied to the exact current span.
    source_line = "".join(module.code.splitlines(keepends=True)[anchor.span.start.line - 1 : anchor.span.end.line])
    return _digest(source_line) == anchor.content_fingerprint


@dataclass(frozen=True)
class InsertLayerNormResult:
    output_bytes: bytes
    constructor_insertions: int
    forward_insertions: int


class _InsertLayerNormTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self,
        module: cst.Module,
        patch: InsertLayerNormPatch,
        constructor_anchor: SourceAnchor,
        forward_anchor: SourceAnchor,
    ) -> None:
        self.module = module
        self.patch = patch
        self.constructor_anchor = constructor_anchor
        self.forward_anchor = forward_anchor
        self.constructor_insertions = 0
        self.forward_insertions = 0

    def leave_SimpleStatementLine(
        self, original_node: cst.SimpleStatementLine, updated_node: cst.SimpleStatementLine
    ) -> cst.BaseStatement | cst.FlattenSentinel[cst.BaseStatement]:
        if len(original_node.body) != 1 or not isinstance(original_node.body[0], cst.Assign):
            return updated_node
        original_assign = original_node.body[0]
        if not isinstance(original_assign.value, cst.Call):
            return updated_node
        call = original_assign.value
        if _call_matches_anchor(self, call, self.constructor_anchor, self.module):
            target_name = self.patch.target_node_id.rsplit(".", maxsplit=1)[-1]
            if (
                len(original_assign.targets) != 1
                or dotted_name(original_assign.targets[0].target) != f"self.{target_name}"
            ):
                raise TransformRejected("INSERT_CONSTRUCTOR_TARGET_MISMATCH", self.constructor_anchor.anchor_id)
            inserted = cst.parse_statement(
                f"self.{self.patch.attribute_name} = nn.LayerNorm({self.patch.normalized_shape})\n"
            )
            self.constructor_insertions += 1
            return cst.FlattenSentinel([inserted, updated_node])
        if not _call_matches_anchor(self, call, self.forward_anchor, self.module):
            return updated_node
        if len(original_assign.targets) != 1 or not isinstance(original_assign.targets[0].target, cst.Name):
            raise TransformRejected("INSERT_FORWARD_TARGET_UNSUPPORTED", self.forward_anchor.anchor_id)
        target = original_assign.targets[0].target.value
        if dotted_name(call.func) != f"self.{self.patch.target_node_id.rsplit('.', maxsplit=1)[-1]}":
            raise TransformRejected("INSERT_FORWARD_CALLEE_MISMATCH", self.forward_anchor.anchor_id)
        if len(call.args) != 1 or not isinstance(call.args[0].value, cst.Name) or call.args[0].value.value != target:
            raise TransformRejected("INSERT_FORWARD_ARGUMENT_UNSUPPORTED", self.forward_anchor.anchor_id)
        inserted = cst.parse_statement(f"{target} = self.{self.patch.attribute_name}({target})\n")
        self.forward_insertions += 1
        return cst.FlattenSentinel([inserted, updated_node])


def apply_insert_layer_norm(
    raw_source: bytes,
    patch: InsertLayerNormPatch,
    constructor_anchor: SourceAnchor,
    forward_anchor: SourceAnchor,
    base_source_revision: str,
) -> InsertLayerNormResult:
    if file_revision(raw_source) != base_source_revision:
        raise TransformRejected("STALE_TARGET_FILE_REVISION", constructor_anchor.relative_file)
    if constructor_anchor.file_revision != base_source_revision or forward_anchor.file_revision != base_source_revision:
        raise TransformRejected("STALE_ANCHOR_REVISION", constructor_anchor.relative_file)
    if constructor_anchor.relative_file != forward_anchor.relative_file:
        raise TransformRejected("INSERT_CROSS_FILE_UNSUPPORTED", forward_anchor.relative_file)
    if patch.constructor_anchor_content_fingerprint != constructor_anchor.content_fingerprint:
        raise TransformRejected("INSERT_CONSTRUCTOR_FINGERPRINT_MISMATCH", constructor_anchor.anchor_id)
    if patch.forward_anchor_content_fingerprint != forward_anchor.content_fingerprint:
        raise TransformRejected("INSERT_FORWARD_FINGERPRINT_MISMATCH", forward_anchor.anchor_id)
    try:
        module = cst.parse_module(raw_source.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise TransformRejected("SOURCE_NOT_UTF8", constructor_anchor.relative_file) from error
    transformer = _InsertLayerNormTransformer(module, patch, constructor_anchor, forward_anchor)
    updated = MetadataWrapper(module).visit(transformer)
    if transformer.constructor_insertions != 1 or transformer.forward_insertions != 1:
        raise TransformRejected(
            "INSERT_MATCH_CARDINALITY",
            f"constructor={transformer.constructor_insertions}, forward={transformer.forward_insertions}",
        )
    return InsertLayerNormResult(
        output_bytes=updated.code.encode("utf-8"),
        constructor_insertions=1,
        forward_insertions=1,
    )
