from __future__ import annotations

import ast
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from typing import Any

import libcst as cst
from libcst.metadata import CodeRange, MetadataWrapper, PositionProvider

from archcanvas_core.models.architecture import ArchitectureParameter, ParameterOriginKind
from archcanvas_core.models.patch import SetParameterPatch
from archcanvas_core.models.source_identity import SourceAnchor

from ..fingerprints import content_fingerprint, structural_fingerprint
from ..source_revision import file_revision


class TransformRejected(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def dotted_name(node: cst.BaseExpression) -> str | None:
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        left = dotted_name(node.value)
        return f"{left}.{node.attr.value}" if left is not None else None
    return None


def same_value(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


def literal_expression(value: Any) -> cst.BaseExpression:
    if value is None:
        return cst.Name("None")
    if type(value) is bool:
        return cst.Name("True" if value else "False")
    if type(value) is int:
        return cst.Integer(str(value))
    if type(value) is float:
        if not isfinite(value):
            raise TransformRejected("NON_JSON_FLOAT", "NaN and infinity are not JSON scalars")
        return cst.Float(repr(value))
    if type(value) is str:
        return cst.SimpleString(repr(value))
    raise TransformRejected("UNSUPPORTED_VALUE", type(value).__name__)


def parse_literal(module: cst.Module, node: cst.BaseExpression) -> Any:
    text = module.code_for_node(node)
    try:
        value = ast.literal_eval(text)
    except (SyntaxError, ValueError) as error:
        raise TransformRejected("NON_LITERAL_SOURCE", text) from error
    if type(value) not in {type(None), bool, int, float, str}:
        raise TransformRejected("NON_SCALAR_SOURCE", text)
    return value


def same_range(position: CodeRange, anchor: SourceAnchor) -> bool:
    return (
        position.start.line == anchor.span.start.line
        and position.start.column == anchor.span.start.column
        and position.end.line == anchor.span.end.line
        and position.end.column == anchor.span.end.column
    )


def _structural_fingerprint_matches(node: cst.Call, anchor: SourceAnchor) -> bool:
    actual = structural_fingerprint(node)
    if actual == anchor.structural_fingerprint:
        return True
    # Static adapter v1 recorded the qualified operation type as its structural fingerprint.
    # Keep this explicit compatibility path bounded by span, qualified callee and content checks.
    qualified_callee = anchor.locator.qualified_callee
    legacy = None if qualified_callee is None else "sha256:" + sha256(qualified_callee.encode("utf-8")).hexdigest()
    return anchor.locator.callee_text is None and legacy == anchor.structural_fingerprint


def _content_fingerprint_matches(module: cst.Module, node: cst.Call, anchor: SourceAnchor) -> bool:
    if content_fingerprint(node) == anchor.content_fingerprint:
        return True
    # Static adapter v1 hashed the complete source lines covered by the constructor span.
    lines = module.code.splitlines(keepends=True)
    segment = "".join(lines[anchor.span.start.line - 1 : anchor.span.end.line])
    legacy = "sha256:" + sha256(segment.encode("utf-8")).hexdigest()
    return anchor.locator.callee_text is None and legacy == anchor.content_fingerprint


@dataclass(frozen=True)
class TransformResult:
    output_bytes: bytes
    changed_calls: int
    changed_arguments: int


class _SetParameterTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self,
        module: cst.Module,
        patch: SetParameterPatch,
        anchor: SourceAnchor,
        parameter: ArchitectureParameter,
    ) -> None:
        self.module = module
        self.patch = patch
        self.anchor = anchor
        self.parameter = parameter
        self.matched_calls = 0
        self.changed_arguments = 0

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        position = self.get_metadata(PositionProvider, original_node)
        if not same_range(position, self.anchor):
            return updated_node
        self.matched_calls += 1
        if not _structural_fingerprint_matches(original_node, self.anchor):
            raise TransformRejected("ANCHOR_STRUCTURE_MISMATCH", self.anchor.anchor_id)
        if not _content_fingerprint_matches(self.module, original_node, self.anchor):
            raise TransformRejected("ANCHOR_CONTENT_MISMATCH", self.anchor.anchor_id)
        if self.patch.anchor_content_fingerprint != self.anchor.content_fingerprint:
            raise TransformRejected("ANCHOR_CONTENT_MISMATCH", self.anchor.anchor_id)
        if self.anchor.locator.callee_text is not None:
            actual_callee = dotted_name(original_node.func)
            if actual_callee != self.anchor.locator.callee_text:
                raise TransformRejected("CALLEE_MISMATCH", repr(actual_callee))
        source_name = self.parameter.source_name
        if source_name is None:
            raise TransformRejected("MISSING_SOURCE_NAME", self.parameter.name)

        class _NestedArgumentTransformer(cst.CSTTransformer):
            def __init__(self, outer: _SetParameterTransformer) -> None:
                self.outer = outer
                self.matches = 0

            def leave_Call(self, nested_original: cst.Call, nested_updated: cst.Call) -> cst.Call:
                indexes = [
                    index
                    for index, argument in enumerate(nested_original.args)
                    if argument.keyword is not None and argument.keyword.value == source_name
                ]
                if not indexes:
                    return nested_updated
                if len(indexes) != 1:
                    raise TransformRejected("ARGUMENT_CARDINALITY", f"{source_name}: {len(indexes)}")
                self.matches += 1
                index = indexes[0]
                current = parse_literal(self.outer.module, nested_original.args[index].value)
                if not same_value(current, self.outer.patch.before):
                    raise TransformRejected("BEFORE_VALUE_MISMATCH", repr(current))
                arguments = list(nested_updated.args)
                arguments[index] = arguments[index].with_changes(
                    value=literal_expression(self.outer.patch.after)
                )
                return nested_updated.with_changes(args=tuple(arguments))

        nested = _NestedArgumentTransformer(self)
        updated = updated_node.visit(nested)
        if nested.matches != 1:
            raise TransformRejected("ARGUMENT_CARDINALITY", f"{source_name}: {nested.matches}")
        self.changed_arguments += 1
        return updated


def apply_set_parameter(
    raw_source: bytes,
    patch: SetParameterPatch,
    anchor: SourceAnchor,
    parameter: ArchitectureParameter,
    base_source_revision: str,
) -> TransformResult:
    actual_revision = file_revision(raw_source)
    if actual_revision != base_source_revision:
        raise TransformRejected("STALE_TARGET_FILE_REVISION", actual_revision)
    if anchor.file_revision != base_source_revision:
        raise TransformRejected("STALE_ANCHOR_REVISION", anchor.file_revision)
    if patch.target.anchor_id != anchor.anchor_id:
        raise TransformRejected("ANCHOR_ID_MISMATCH", patch.target.anchor_id)
    if parameter.name != patch.target.parameter:
        raise TransformRejected("PARAMETER_NAME_MISMATCH", parameter.name)
    if parameter.origin.kind is not ParameterOriginKind.LITERAL:
        raise TransformRejected("NON_LITERAL_ORIGIN", parameter.origin.kind.value)
    if not same_value(parameter.value, patch.before):
        raise TransformRejected("IR_BEFORE_VALUE_MISMATCH", repr(parameter.value))
    if anchor.content_fingerprint != patch.anchor_content_fingerprint:
        raise TransformRejected("PATCH_ANCHOR_FINGERPRINT_MISMATCH", anchor.anchor_id)
    try:
        module = cst.parse_module(raw_source.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise TransformRejected("SOURCE_NOT_UTF8", anchor.relative_file) from error
    transformer = _SetParameterTransformer(module, patch, anchor, parameter)
    updated = MetadataWrapper(module).visit(transformer)
    if transformer.matched_calls != 1:
        raise TransformRejected("ANCHOR_CARDINALITY", str(transformer.matched_calls))
    if transformer.changed_arguments != 1:
        raise TransformRejected("CHANGE_CARDINALITY", str(transformer.changed_arguments))
    output = updated.code.encode("utf-8")
    if b"\r\n" in raw_source and b"\r\n" not in output:
        raise TransformRejected("LINE_ENDING_CHANGED", "LibCST changed CRLF source")
    return TransformResult(output_bytes=output, changed_calls=1, changed_arguments=1)
