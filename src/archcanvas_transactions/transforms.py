from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import libcst as cst
from libcst.metadata import (
    ExpressionContext,
    ExpressionContextProvider,
    MetadataWrapper,
    PositionProvider,
)


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


class _ReplaceModuleConstructor(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self,
        module_name: str,
        original_operator: str,
        replacement_operator: str,
        expected_line: int,
    ) -> None:
        self.module_name = module_name
        self.original_operator = original_operator
        self.replacement = cst.parse_expression(replacement_operator)
        self.expected_line = expected_line
        self.matches = 0

    def leave_Assign(self, original_node: cst.Assign, updated_node: cst.Assign) -> cst.Assign:
        if len(original_node.targets) != 1:
            return updated_node
        target = original_node.targets[0].target
        if _SetModuleParameter._target_name(target) != self.module_name:
            return updated_node
        if not isinstance(original_node.value, cst.Call) or not isinstance(updated_node.value, cst.Call):
            return updated_node
        position = self.get_metadata(PositionProvider, original_node)
        operator = cst.Module([]).code_for_node(original_node.value.func)
        if position.start.line != self.expected_line or operator != self.original_operator:
            return updated_node
        if original_node.value.args:
            raise ValueError("activation replacement requires a zero-argument constructor")
        self.matches += 1
        return updated_node.with_changes(value=updated_node.value.with_changes(func=self.replacement))


def replace_module_constructor(
    source: bytes,
    *,
    module_name: str,
    original_operator: str,
    replacement_operator: str,
    expected_line: int,
) -> TransformResult:
    module = cst.parse_module(source.decode("utf-8"))
    transformer = _ReplaceModuleConstructor(
        module_name,
        original_operator,
        replacement_operator,
        expected_line,
    )
    changed = MetadataWrapper(module).visit(transformer)
    if transformer.matches != 1:
        raise ValueError(f"expected one exact module constructor anchor, found {transformer.matches}")
    return TransformResult(content=changed.code.encode(), anchor_line=expected_line)


class _RenameLoads(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (ExpressionContextProvider,)

    def __init__(self, old: str, new: str) -> None:
        self.old = old
        self.new = new

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.Name:
        if (
            original_node.value == self.old
            and self.get_metadata(ExpressionContextProvider, original_node, None)
            is ExpressionContext.LOAD
        ):
            return updated_node.with_changes(value=self.new)
        return updated_node


def _renamed_statement(statement: cst.BaseStatement, old: str, new: str) -> cst.BaseStatement:
    wrapped = cst.Module(body=[statement])
    changed = MetadataWrapper(wrapped).visit(_RenameLoads(old, new))
    return changed.body[0]


def _simple_assignment(statement: cst.BaseStatement) -> cst.Assign | None:
    if not isinstance(statement, cst.SimpleStatementLine) or len(statement.body) != 1:
        return None
    item = statement.body[0]
    return item if isinstance(item, cst.Assign) else None


def _self_call_module(call: cst.BaseExpression) -> str | None:
    if not isinstance(call, cst.Call) or not isinstance(call.func, cst.Attribute):
        return None
    if isinstance(call.func.value, cst.Name) and call.func.value.value == "self":
        return call.func.attr.value
    return None


class _InsertLayerNorm(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self,
        target_module: str,
        new_module: str,
        normalized_shape: str,
        init_line: int,
        forward_line: int,
    ) -> None:
        self.target_module = target_module
        self.new_module = new_module
        self.normalized_shape = normalized_shape
        self.init_line = init_line
        self.forward_line = forward_line
        self.init_matches = 0
        self.forward_matches = 0

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        if not isinstance(original_node.body, cst.IndentedBlock) or not isinstance(
            updated_node.body, cst.IndentedBlock
        ):
            return updated_node
        original_body = list(original_node.body.body)
        updated_body = list(updated_node.body.body)
        if original_node.name.value == "__init__":
            result: list[cst.BaseStatement] = []
            for original, updated in zip(original_body, updated_body, strict=True):
                result.append(updated)
                assignment = _simple_assignment(original)
                if assignment is None or len(assignment.targets) != 1:
                    continue
                target = assignment.targets[0].target
                position = self.get_metadata(PositionProvider, original)
                if (
                    _SetModuleParameter._target_name(target) == self.target_module
                    and position.start.line == self.init_line
                ):
                    result.append(
                        cst.parse_statement(
                            f"self.{self.new_module} = nn.LayerNorm({self.normalized_shape})\n"
                        )
                    )
                    self.init_matches += 1
            return updated_node.with_changes(body=updated_node.body.with_changes(body=result))
        if original_node.name.value != "forward":
            return updated_node
        match_index: int | None = None
        assigned_name = ""
        for index, statement in enumerate(original_body):
            assignment = _simple_assignment(statement)
            if assignment is None or len(assignment.targets) != 1:
                continue
            target = assignment.targets[0].target
            position = self.get_metadata(PositionProvider, statement)
            if (
                isinstance(target, cst.Name)
                and _self_call_module(assignment.value) == self.target_module
                and position.start.line == self.forward_line
            ):
                match_index = index
                assigned_name = target.value
                break
        if match_index is None:
            return updated_node
        new_variable = f"{assigned_name}_{self.new_module}"
        rewritten = updated_body[: match_index + 1]
        rewritten.append(
            cst.parse_statement(
                f"{new_variable} = self.{self.new_module}({assigned_name})\n"
            )
        )
        rewritten.extend(
            _renamed_statement(statement, assigned_name, new_variable)
            for statement in updated_body[match_index + 1 :]
        )
        self.forward_matches += 1
        return updated_node.with_changes(body=updated_node.body.with_changes(body=rewritten))


def insert_layer_norm(
    source: bytes,
    *,
    target_module: str,
    new_module: str,
    normalized_shape: str,
    init_line: int,
    forward_line: int,
) -> TransformResult:
    module = cst.parse_module(source.decode("utf-8"))
    if f"self.{new_module}" in module.code:
        raise ValueError(f"module name already exists: {new_module}")
    cst.parse_expression(normalized_shape)
    transformer = _InsertLayerNorm(
        target_module,
        new_module,
        normalized_shape,
        init_line,
        forward_line,
    )
    changed = MetadataWrapper(module).visit(transformer)
    if transformer.init_matches != 1 or transformer.forward_matches != 1:
        raise ValueError(
            "insert_layer_norm requires one exact constructor anchor and one exact forward call"
        )
    return TransformResult(content=changed.code.encode(), anchor_line=forward_line)


def write_prepared(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
