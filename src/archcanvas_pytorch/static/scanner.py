"""Conservative AST discovery for the supported PyTorch static subset.

This module reports observations and unresolved facts. It does not yet claim to produce a
complete Architecture IR; Stage 2's adapter will convert only proven discoveries into IR.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Literal


@dataclass(frozen=True)
class ModuleDiscovery:
    attribute_path: str
    op_type: str
    line: int
    column: int
    end_line: int
    end_column: int
    container: str | None = None
    parameters: list[ParameterDiscovery] = field(default_factory=list)
    repeat_count: int | None = None
    repeat_symbol: str | None = None


@dataclass(frozen=True)
class ParameterDiscovery:
    """A constructor argument with an intentionally conservative provenance classification."""

    name: str
    source_name: str
    value: object | None
    expression: str | None
    origin: Literal["literal", "constant", "argument", "config_attribute", "computed", "unknown"]
    line: int
    column: int
    end_line: int
    end_column: int
    origin_line: int | None = None
    origin_column: int | None = None
    origin_end_line: int | None = None
    origin_end_column: int | None = None


@dataclass(frozen=True)
class EdgeDiscovery:
    source: str
    target: str
    kind: str = "data"


@dataclass(frozen=True)
class MergeDiscovery:
    name: str
    operation: str
    inputs: list[str]
    line: int


@dataclass(frozen=True)
class FunctionDiscovery:
    """A statically resolved functional tensor operation in ``forward``."""

    name: str
    operation: str
    input: str
    line: int
    column: int
    end_line: int
    end_column: int


@dataclass(frozen=True)
class UnresolvedDiscovery:
    code: str
    line: int
    message: str


@dataclass(frozen=True)
class StaticRecoveryResult:
    model_classes: list[str]
    modules: list[ModuleDiscovery]
    edges: list[EdgeDiscovery]
    merges: list[MergeDiscovery] = field(default_factory=list)
    functions: list[FunctionDiscovery] = field(default_factory=list)
    unresolved: list[UnresolvedDiscovery] = field(default_factory=list)


def _dotted(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _dotted(node.value)
        return f"{left}.{node.attr}" if left else None
    return None


_NOT_LITERAL = object()


def _json_literal(node: ast.expr) -> object:
    """Return a JSON-compatible literal or a sentinel without evaluating user code."""

    if isinstance(node, ast.Constant) and (
        node.value is None or isinstance(node.value, (bool, int, float, str))
    ):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        values = [_json_literal(item) for item in node.elts]
        return _NOT_LITERAL if any(item is _NOT_LITERAL for item in values) else values
    if isinstance(node, ast.Dict):
        values: dict[str, object] = {}
        for key, value in zip(node.keys, node.values):
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                return _NOT_LITERAL
            item = _json_literal(value)
            if item is _NOT_LITERAL:
                return _NOT_LITERAL
            values[key.value] = item
        return values
    return _NOT_LITERAL


def _is_config_attribute(node: ast.expr) -> bool:
    dotted = _dotted(node)
    return dotted is not None and dotted.startswith(("self.config.", "config."))


def _inner_module_call(call: ast.Call, imports: _ImportIndex, op_type: str) -> ast.Call | None:
    resolved = imports.resolve(call.func)
    if resolved == op_type:
        return call
    return next(
        (
            candidate
            for candidate in ast.walk(call)
            if isinstance(candidate, ast.Call) and imports.resolve(candidate.func) == op_type
        ),
        None,
    )


_POSITIONAL_PARAMETER_NAMES: dict[str, tuple[str, ...]] = {
    "torch.nn.Conv2d": (
        "in_channels",
        "out_channels",
        "kernel_size",
        "stride",
        "padding",
        "dilation",
        "groups",
        "bias",
        "padding_mode",
    ),
    "torch.nn.Embedding": ("num_embeddings", "embedding_dim", "padding_idx", "max_norm"),
    "torch.nn.LayerNorm": ("normalized_shape", "eps", "elementwise_affine", "bias"),
    "torch.nn.Linear": ("in_features", "out_features", "bias"),
    "torch.nn.TransformerEncoderLayer": (
        "d_model",
        "nhead",
        "dim_feedforward",
        "dropout",
        "activation",
        "layer_norm_eps",
        "batch_first",
        "norm_first",
        "bias",
    ),
}


def _parameter_names(op_type: str, call: ast.Call) -> tuple[str, ...]:
    return _POSITIONAL_PARAMETER_NAMES.get(op_type, tuple(f"arg{index}" for index in range(len(call.args))))


def _canonical_parameter_name(op_type: str, source_name: str) -> str:
    if op_type == "torch.nn.TransformerEncoderLayer" and source_name == "nhead":
        return "num_heads"
    return source_name


def _is_supported_module_type(value: str) -> bool:
    return value.startswith(("torch.nn.", "local:"))


_SUPPORTED_FUNCTIONS = {
    "torch.relu",
    "torch.sigmoid",
    "torch.tanh",
    "torch.nn.functional.relu",
    "torch.nn.functional.gelu",
    "torch.nn.functional.silu",
    "torch.nn.functional.dropout",
    "torch.nn.functional.layer_norm",
}


def _is_functional_namespace(value: str | None) -> bool:
    return value is not None and (
        value.startswith("torch.nn.functional.")
        or value in {"torch.relu", "torch.sigmoid", "torch.tanh"}
    )


class _ImportIndex(ast.NodeVisitor):
    def __init__(self, local_module_aliases: Mapping[str, str] | None = None) -> None:
        self.aliases = dict(local_module_aliases or {})

    def visit_Import(self, node: ast.Import) -> None:
        for item in node.names:
            if item.name == "torch":
                self.aliases[item.asname or "torch"] = item.name
            if item.name == "torch.nn":
                self.aliases[item.asname or "torch"] = item.name
            if item.name == "torch.nn.functional":
                # ``import torch.nn.functional`` binds ``torch``; an alias binds the alias.
                self.aliases[item.asname or "torch"] = item.name if item.asname else "torch"
            if item.name == "collections":
                self.aliases[item.asname or "collections"] = item.name

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "torch":
            for item in node.names:
                if item.name == "nn":
                    self.aliases[item.asname or "nn"] = "torch.nn"
        if node.module == "torch.nn":
            for item in node.names:
                if item.name != "*":
                    self.aliases[item.asname or item.name] = f"torch.nn.{item.name}"
        if node.module == "torch.nn.functional":
            for item in node.names:
                if item.name != "*":
                    self.aliases[item.asname or item.name] = f"torch.nn.functional.{item.name}"
        if node.module == "collections":
            for item in node.names:
                if item.name == "OrderedDict":
                    self.aliases[item.asname or item.name] = "collections.OrderedDict"

    def resolve(self, expression: ast.expr) -> str | None:
        dotted = _dotted(expression)
        if dotted is None:
            return None
        head, _, tail = dotted.partition(".")
        if head not in self.aliases:
            return None
        return self.aliases[head] + (f".{tail}" if tail else "")


class _ModuleClassScanner(ast.NodeVisitor):
    def __init__(
        self,
        imports: _ImportIndex,
        constants: dict[str, ast.expr],
        selected_model_class: str | None = None,
    ) -> None:
        self.imports = imports
        self.constants = constants
        self.selected_model_class = selected_model_class
        self.model_classes: list[str] = []
        self.modules: list[ModuleDiscovery] = []
        self.edges: list[EdgeDiscovery] = []
        self.merges: list[MergeDiscovery] = []
        self.functions: list[FunctionDiscovery] = []
        self.unresolved: list[UnresolvedDiscovery] = []
        self.container_members: dict[str, list[str]] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if self.selected_model_class is not None and node.name != self.selected_model_class:
            return
        if not any(self.imports.resolve(base) == "torch.nn.Module" for base in node.bases):
            return
        self.model_classes.append(node.name)
        methods = {item.name: item for item in node.body if isinstance(item, ast.FunctionDef)}
        init = methods.get("__init__")
        if init:
            self._scan_constructor(init)
        forward = methods.get("forward")
        if forward:
            self._scan_forward(forward)

    def _scan_constructor(self, method: ast.FunctionDef) -> None:
        constructor_arguments = {
            argument.arg
            for argument in (
                [*method.args.posonlyargs, *method.args.args, *method.args.kwonlyargs]
            )
            if argument.arg != "self"
        }
        def scan_statements(statements: list[ast.stmt]) -> None:
            for node in statements:
                if isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.Match)):
                    self.unresolved.append(
                        UnresolvedDiscovery(
                            "DYNAMIC_CONSTRUCTOR_CONTROL_FLOW",
                            node.lineno,
                            f"{type(node).__name__.lower()} in __init__",
                        )
                    )
                    continue
                if isinstance(node, ast.Assign):
                    self._scan_constructor_assignment(node, constructor_arguments)

        scan_statements(method.body)

    def _scan_constructor_assignment(
        self, node: ast.Assign, constructor_arguments: set[str]
    ) -> None:
        if len(node.targets) != 1:
            return
        target = node.targets[0]
        if not (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
            and isinstance(node.value, ast.Call)
        ):
            return
        resolved = self.imports.resolve(node.value.func)
        if resolved is None or not _is_supported_module_type(resolved):
            self.unresolved.append(
                UnresolvedDiscovery("UNRESOLVED_MODULE_CONSTRUCTOR", node.lineno, target.attr)
            )
            return
        if resolved == "torch.nn.Sequential":
            self._scan_sequential(target.attr, node.value, constructor_arguments)
            return
        container = None
        op_type = resolved
        repeat_count = None
        repeat_symbol = None
        if resolved == "torch.nn.ModuleList":
            members = self._module_list_literal_members(node.value)
            if members is not None:
                self._scan_explicit_container(
                    target.attr, members, "ModuleList", constructor_arguments
                )
                return
            repeated_member = self._module_list_repeated_member(node.value)
            repeat_count, repeat_symbol = self._module_list_repeat(node.value)
            if repeated_member is None or (repeat_count is None and repeat_symbol is None):
                self.unresolved.append(
                    UnresolvedDiscovery("UNRESOLVED_CONTAINER_MEMBER", node.lineno, target.attr)
                )
                return
            container, op_type = "ModuleList", repeated_member
        self._append_module_discovery(
            target.attr,
            node.value,
            op_type,
            container,
            repeat_count,
            repeat_symbol,
            constructor_arguments,
        )

    def _scan_sequential(
        self, attribute: str, call: ast.Call, constructor_arguments: set[str]
    ) -> None:
        members = self._sequential_members(call)
        if members is None:
            self.unresolved.append(
                UnresolvedDiscovery("UNRESOLVED_CONTAINER_MEMBER", call.lineno, attribute)
            )
            return
        self._scan_explicit_container(attribute, members, "Sequential", constructor_arguments)

    def _scan_explicit_container(
        self,
        attribute: str,
        members: list[tuple[str, ast.Call]],
        container: str,
        constructor_arguments: set[str],
    ) -> None:
        member_names: list[str] = []
        resolved_members: list[tuple[ast.Call, str]] = []
        for member_key, item in members:
            op_type = self.imports.resolve(item.func)
            if op_type is None or not _is_supported_module_type(op_type):
                self.unresolved.append(
                    UnresolvedDiscovery("UNRESOLVED_CONTAINER_MEMBER", item.lineno, attribute)
                )
                return
            member_names.append(f"{attribute}.{member_key}")
            resolved_members.append((item, op_type))
        self.container_members[attribute] = member_names
        self.edges.extend(
            EdgeDiscovery(source, target)
            for source, target in pairwise(member_names)
        )
        for member_name, (member_call, op_type) in zip(member_names, resolved_members):
            self._append_module_discovery(
                member_name,
                member_call,
                op_type,
                container,
                None,
                None,
                constructor_arguments,
            )

    def _sequential_members(self, call: ast.Call) -> list[tuple[str, ast.Call]] | None:
        if call.keywords or not call.args:
            return None
        if all(
            isinstance(item, ast.Call)
            and _is_supported_module_type(self.imports.resolve(item.func) or "")
            for item in call.args
        ):
            return [(str(index), item) for index, item in enumerate(call.args) if isinstance(item, ast.Call)]
        if (
            len(call.args) != 1
            or not isinstance(call.args[0], ast.Call)
            or self.imports.resolve(call.args[0].func) != "collections.OrderedDict"
        ):
            return None
        ordered_dict = call.args[0]
        if ordered_dict.keywords or len(ordered_dict.args) != 1:
            return None
        pairs = ordered_dict.args[0]
        if not isinstance(pairs, (ast.List, ast.Tuple)):
            return None
        members: list[tuple[str, ast.Call]] = []
        names: set[str] = set()
        for pair in pairs.elts:
            if not (
                isinstance(pair, ast.Tuple)
                and len(pair.elts) == 2
                and isinstance(pair.elts[0], ast.Constant)
                and isinstance(pair.elts[0].value, str)
                and isinstance(pair.elts[1], ast.Call)
            ):
                return None
            name = pair.elts[0].value
            if not name or name in names or not all(
                character.isascii() and (character.isalnum() or character in {"_", "-"})
                for character in name
            ):
                return None
            names.add(name)
            members.append((name, pair.elts[1]))
        return members or None

    def _module_list_literal_members(self, call: ast.Call) -> list[tuple[str, ast.Call]] | None:
        if call.keywords or len(call.args) != 1 or not isinstance(call.args[0], (ast.List, ast.Tuple)):
            return None
        elements = call.args[0].elts
        if not elements or not all(isinstance(item, ast.Call) for item in elements):
            return None
        return [(str(index), item) for index, item in enumerate(elements) if isinstance(item, ast.Call)]

    def _module_list_repeated_member(self, call: ast.Call) -> str | None:
        if call.keywords or len(call.args) != 1 or not isinstance(call.args[0], ast.ListComp):
            return None
        list_comp = call.args[0]
        if len(list_comp.generators) != 1 or list_comp.generators[0].ifs:
            return None
        if not isinstance(list_comp.elt, ast.Call):
            return None
        op_type = self.imports.resolve(list_comp.elt.func)
        return op_type if op_type is not None and _is_supported_module_type(op_type) else None

    def _append_module_discovery(
        self,
        attribute: str,
        call: ast.Call,
        op_type: str,
        container: str | None,
        repeat_count: int | None,
        repeat_symbol: str | None,
        constructor_arguments: set[str],
    ) -> None:
        self.modules.append(
            ModuleDiscovery(
                attribute,
                op_type,
                call.lineno,
                call.col_offset,
                call.end_lineno,
                call.end_col_offset,
                container,
                self._parameters_for_call(
                    call,
                    op_type=op_type,
                    constructor_arguments=constructor_arguments,
                ),
                repeat_count,
                repeat_symbol,
            )
        )

    def _module_list_repeat(self, call: ast.Call) -> tuple[int | None, str | None]:
        if not call.args or not isinstance(call.args[0], ast.ListComp):
            return None, None
        generators = call.args[0].generators
        if len(generators) != 1 or not isinstance(generators[0].iter, ast.Call):
            return None, None
        range_call = generators[0].iter
        if _dotted(range_call.func) != "range" or len(range_call.args) != 1:
            return None, None
        count = range_call.args[0]
        literal = _json_literal(count)
        if isinstance(literal, int) and not isinstance(literal, bool) and literal >= 1:
            return literal, None
        if isinstance(count, ast.Name):
            return None, count.id
        self.unresolved.append(
            UnresolvedDiscovery("UNRESOLVED_REPEAT_COUNT", count.lineno, "ModuleList range"))
        return None, None

    def _parameters_for_call(
        self,
        call: ast.Call,
        *,
        op_type: str,
        constructor_arguments: set[str],
    ) -> list[ParameterDiscovery]:
        target_call = _inner_module_call(call, self.imports, op_type)
        if target_call is None:
            return []
        names = _parameter_names(op_type, target_call)
        discoveries: list[ParameterDiscovery] = []
        for position, argument in enumerate(target_call.args):
            name = names[position] if position < len(names) else f"arg{position}"
            discoveries.append(
                self._parameter_from_expression(
                    name=name,
                    source_name=name,
                    expression=argument,
                    constructor_arguments=constructor_arguments,
                )
            )
        for keyword in target_call.keywords:
            if keyword.arg is None:
                self.unresolved.append(
                    UnresolvedDiscovery("UNRESOLVED_KEYWORD_EXPANSION", keyword.value.lineno, op_type)
                )
                continue
            discoveries.append(
                self._parameter_from_expression(
                    name=_canonical_parameter_name(op_type, keyword.arg),
                    source_name=keyword.arg,
                    expression=keyword.value,
                    constructor_arguments=constructor_arguments,
                )
            )
        return discoveries

    def _parameter_from_expression(
        self,
        *,
        name: str,
        source_name: str,
        expression: ast.expr,
        constructor_arguments: set[str],
    ) -> ParameterDiscovery:
        literal = _json_literal(expression)
        if literal is not _NOT_LITERAL:
            origin = "literal"
            value: object | None = literal
            source_expression = None
            origin_node = expression
        elif isinstance(expression, ast.Name) and expression.id in constructor_arguments:
            origin = "argument"
            value = None
            source_expression = expression.id
            origin_node = expression
        elif isinstance(expression, ast.Name) and expression.id in self.constants:
            origin = "constant"
            value = _json_literal(self.constants[expression.id])
            source_expression = expression.id
            origin_node = self.constants[expression.id]
        elif _is_config_attribute(expression):
            origin = "config_attribute"
            value = None
            source_expression = ast.unparse(expression)
            origin_node = expression
        else:
            origin = "computed"
            value = None
            source_expression = ast.unparse(expression)
            origin_node = expression
            self.unresolved.append(
                UnresolvedDiscovery("UNRESOLVED_PARAMETER_PROVENANCE", expression.lineno, source_expression)
            )
        return ParameterDiscovery(
            name=name,
            source_name=source_name,
            value=value,
            expression=source_expression,
            origin=origin,
            line=expression.lineno,
            column=expression.col_offset,
            end_line=expression.end_lineno,
            end_column=expression.end_col_offset,
            origin_line=origin_node.lineno,
            origin_column=origin_node.col_offset,
            origin_end_line=origin_node.end_lineno,
            origin_end_column=origin_node.end_col_offset,
        )

    def _scan_forward(self, method: ast.FunctionDef) -> None:
        value_origin: dict[str, str] = {}
        loop_modules: dict[str, str] = {}
        arguments = [argument.arg for argument in method.args.args if argument.arg != "self"]
        if arguments:
            value_origin[arguments[0]] = "input"

        def record_module_call(source: str, module: str) -> str:
            members = self.container_members.get(module)
            if members:
                self.edges.append(EdgeDiscovery(source, members[0]))
                return members[-1]
            self.edges.append(EdgeDiscovery(source, module))
            return module

        def record_function_call(
            source: str, operation: str, call: ast.Call, name: str
        ) -> str:
            function_name = f"function:{name}.{call.lineno}"
            self.functions.append(
                FunctionDiscovery(
                    function_name,
                    operation,
                    source,
                    call.lineno,
                    call.col_offset,
                    call.end_lineno,
                    call.end_col_offset,
                )
            )
            self.edges.append(EdgeDiscovery(source, function_name))
            return function_name

        def scan_statements(statements: list[ast.stmt]) -> None:
            for node in statements:
                if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
                    iterable = _dotted(node.iter)
                    if iterable and iterable.startswith("self."):
                        loop_modules[node.target.id] = iterable.removeprefix("self.")
                    scan_statements(node.body)
                    continue
                if isinstance(node, ast.If):
                    self.unresolved.append(
                        UnresolvedDiscovery("DYNAMIC_CONTROL_FLOW", node.lineno, "if in forward")
                    )
                    continue
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    called = _dotted(node.value.func)
                    if called in {"eval", "exec"}:
                        self.unresolved.append(UnresolvedDiscovery("DYNAMIC_EXECUTION", node.lineno, called))
                    continue
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    target = node.targets[0].id
                    alias_source = value_origin.get(_dotted(node.value) or "")
                    if alias_source is not None:
                        value_origin[target] = alias_source
                        continue
                    if isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Add):
                        left_name = _dotted(node.value.left)
                        right_name = _dotted(node.value.right)
                        left = value_origin.get(left_name or "")
                        right = value_origin.get(right_name or "")
                        if left is not None and right is not None:
                            self.edges.append(EdgeDiscovery(right, left, "residual"))
                            value_origin[target] = left
                        else:
                            self.unresolved.append(
                                UnresolvedDiscovery("UNRESOLVED_RESIDUAL", node.lineno, "add operands")
                            )
                        continue
                    if isinstance(node.value, ast.Call):
                        operation = self.imports.resolve(node.value.func)
                        if operation in {"torch.cat", "torch.stack"}:
                            values = node.value.args[0] if node.value.args else None
                            elements = values.elts if isinstance(values, (ast.List, ast.Tuple)) else []
                            inputs = [value_origin.get(_dotted(value) or "") for value in elements]
                            if not inputs or any(value is None for value in inputs):
                                self.unresolved.append(
                                    UnresolvedDiscovery("UNRESOLVED_MERGE_INPUT", node.lineno, operation)
                                )
                                continue
                            merge_name = f"merge:{target}"
                            concrete_inputs = [value for value in inputs if value is not None]
                            self.merges.append(MergeDiscovery(merge_name, operation, concrete_inputs, node.lineno))
                            self.edges.extend(EdgeDiscovery(source, merge_name) for source in concrete_inputs)
                            value_origin[target] = merge_name
                            continue
                        if operation in _SUPPORTED_FUNCTIONS:
                            source_name = _dotted(node.value.args[0]) if node.value.args else None
                            source = value_origin.get(source_name or "")
                            if source is None:
                                self.unresolved.append(
                                    UnresolvedDiscovery(
                                        "UNRESOLVED_FUNCTION_INPUT", node.lineno, operation
                                    )
                                )
                                continue
                            value_origin[target] = record_function_call(
                                source, operation, node.value, target
                            )
                            continue
                        if _is_functional_namespace(operation):
                            self.unresolved.append(
                                UnresolvedDiscovery(
                                    "UNSUPPORTED_FUNCTIONAL_OP", node.lineno, operation
                                )
                            )
                            continue
                        called = _dotted(node.value.func)
                        if called and called.startswith("self."):
                            module = called.removeprefix("self.")
                        elif called in loop_modules:
                            module = loop_modules[called]
                        else:
                            continue
                        source_name = _dotted(node.value.args[0]) if node.value.args else None
                        value_origin[target] = record_module_call(
                            value_origin.get(source_name or "", "input"), module
                        )
                    continue
                if isinstance(node, ast.Return):
                    if isinstance(node.value, ast.Call):
                        operation = self.imports.resolve(node.value.func)
                        if operation in _SUPPORTED_FUNCTIONS:
                            source_name = _dotted(node.value.args[0]) if node.value.args else None
                            source = value_origin.get(source_name or "")
                            if source is None:
                                self.unresolved.append(
                                    UnresolvedDiscovery(
                                        "UNRESOLVED_FUNCTION_INPUT", node.lineno, operation
                                    )
                                )
                                continue
                            output_function = record_function_call(
                                source, operation, node.value, "return"
                            )
                            self.edges.append(EdgeDiscovery(output_function, "output"))
                            continue
                        if _is_functional_namespace(operation):
                            self.unresolved.append(
                                UnresolvedDiscovery(
                                    "UNSUPPORTED_FUNCTIONAL_OP", node.lineno, operation
                                )
                            )
                            continue
                        called = _dotted(node.value.func)
                        if called and called.startswith("self."):
                            module = called.removeprefix("self.")
                            source_name = _dotted(node.value.args[0]) if node.value.args else None
                            output_module = record_module_call(
                                value_origin.get(source_name or "", "input"), module
                            )
                            self.edges.append(EdgeDiscovery(output_module, "output"))
                            continue
                    returned_value = value_origin.get(_dotted(node.value) or "")
                    if returned_value is not None:
                        self.edges.append(EdgeDiscovery(returned_value, "output"))

        scan_statements(method.body)


class PyTorchStaticScanner:
    def scan(
        self,
        raw_source: bytes,
        *,
        local_module_aliases: Mapping[str, str] | None = None,
        selected_model_class: str | None = None,
    ) -> StaticRecoveryResult:
        try:
            module = ast.parse(raw_source.decode("utf-8"))
        except UnicodeDecodeError as error:
            raise ValueError("PyTorch source must be UTF-8") from error
        imports = _ImportIndex(local_module_aliases)
        imports.visit(module)
        constants = {
            target.id: node.value
            for node in module.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(target := node.targets[0], ast.Name)
            and _json_literal(node.value) is not _NOT_LITERAL
        }
        scanner = _ModuleClassScanner(imports, constants, selected_model_class)
        scanner.visit(module)
        return StaticRecoveryResult(
            model_classes=scanner.model_classes,
            modules=sorted(scanner.modules, key=lambda item: (item.line, item.attribute_path)),
            edges=sorted(set(scanner.edges), key=lambda item: (item.source, item.target, item.kind)),
            merges=sorted(scanner.merges, key=lambda item: (item.line, item.name)),
            functions=sorted(scanner.functions, key=lambda item: (item.line, item.name)),
            unresolved=sorted(scanner.unresolved, key=lambda item: (item.line, item.code)),
        )
