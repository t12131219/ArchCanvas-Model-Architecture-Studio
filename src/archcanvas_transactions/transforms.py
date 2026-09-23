from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider


@dataclass(frozen=True)
class TransformResult:
    content: bytes
    anchor_line: int


def set_json_value(source: bytes, key: str, value: Any) -> TransformResult:
    document = json.loads(source)
    if not isinstance(document, dict) or key not in document:
        raise ValueError(f"config key is not available for an exact edit: {key}")
    document[key] = value
    return TransformResult(
        content=(json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode(),
        anchor_line=1,
    )


class _SetModuleParameter(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self,
        module_name: str,
        parameter_name: str,
        source_expression: str,
        value: Any,
        expected_line: int,
    ) -> None:
        self.module_name = module_name
        self.parameter_name = parameter_name
        self.source_expression = source_expression
        self.replacement = cst.parse_expression(repr(value))
        self.expected_line = expected_line
        self.matches = 0
        self.anchor_line = 0

    @staticmethod
    def _target_name(target: cst.BaseAssignTargetExpression) -> str | None:
        if (
            isinstance(target, cst.Attribute)
            and isinstance(target.value, cst.Name)
            and target.value.value == "self"
        ):
            return target.attr.value
        return None

    def leave_Assign(self, original_node: cst.Assign, updated_node: cst.Assign) -> cst.Assign:
        if len(original_node.targets) != 1:
            return updated_node
        target = original_node.targets[0].target
        if self._target_name(target) != self.module_name or not isinstance(original_node.value, cst.Call):
            return updated_node
        position = self.get_metadata(PositionProvider, original_node)
        if position.start.line != self.expected_line:
            return updated_node
        call = updated_node.value
        original_call = original_node.value
        positional_index = {
            "in_features": 0,
            "out_features": 1,
            "normalized_shape": 0,
        }.get(self.parameter_name)
        args = list(call.args)
        match_index: int | None = None
        for index, argument in enumerate(original_call.args):
            if argument.keyword and argument.keyword.value == self.parameter_name:
                match_index = index
                break
        if match_index is None and positional_index is not None:
            positional = [index for index, argument in enumerate(original_call.args) if argument.keyword is None]
            if positional_index < len(positional):
                match_index = positional[positional_index]
        if match_index is None:
            raise ValueError(f"parameter is not explicitly present at the source anchor: {self.parameter_name}")
        expression = cst.Module([]).code_for_node(original_call.args[match_index].value)
        if expression != self.source_expression:
            raise ValueError("parameter source expression no longer matches the analysis anchor")
        args[match_index] = args[match_index].with_changes(value=self.replacement)
        self.matches += 1
        self.anchor_line = position.start.line
        return updated_node.with_changes(value=call.with_changes(args=args))


def set_python_parameter(
    source: bytes,
    *,
    module_name: str,
    parameter_name: str,
    source_expression: str,
    value: Any,
    expected_line: int,
) -> TransformResult:
    module = cst.parse_module(source.decode("utf-8"))
    transformer = _SetModuleParameter(
        module_name,
        parameter_name,
        source_expression,
        value,
        expected_line,
    )
    changed = MetadataWrapper(module).visit(transformer)
    if transformer.matches != 1:
        raise ValueError(f"expected one exact Python parameter anchor, found {transformer.matches}")
    return TransformResult(content=changed.code.encode(), anchor_line=transformer.anchor_line)


def write_prepared(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
