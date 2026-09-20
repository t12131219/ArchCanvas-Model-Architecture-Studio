"""Conservative AST discovery for the supported PyTorch static subset.

This module reports observations and unresolved facts. It does not yet claim to produce a
complete Architecture IR; Stage 2's adapter will convert only proven discoveries into IR.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
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
    parameters: list["ParameterDiscovery"] = field(default_factory=list)
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
    return dotted is not None and (dotted.startswith("self.config.") or dotted.startswith("config."))


def _inner_module_call(call: ast.Call, imports: "_ImportIndex", op_type: str) -> ast.Call | None:
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


class _ImportIndex(ast.NodeVisitor):
    def __init__(self) -> None:
        self.aliases: dict[str, str] = {}

    def visit_Import(self, node: ast.Import) -> None:
        for item in node.names:
            if item.name == "torch":
                self.aliases[item.asname or "torch"] = item.name
            if item.name == "torch.nn":
                self.aliases[item.asname or "torch"] = item.name

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "torch":
            for item in node.names:
                if item.name == "nn":
                    self.aliases[item.asname or "nn"] = "torch.nn"
        if node.module == "torch.nn":
            for item in node.names:
                if item.name != "*":
                    self.aliases[item.asname or item.name] = f"torch.nn.{item.name}"

    def resolve(self, expression: ast.expr) -> str | None:
        dotted = _dotted(expression)
        if dotted is None:
            return None
        head, _, tail = dotted.partition(".")
        if head not in self.aliases:
            return None
        return self.aliases[head] + (f".{tail}" if tail else "")


class _ModuleClassScanner(ast.NodeVisitor):
    def __init__(self, imports: _ImportIndex, constants: dict[str, ast.expr]) -> None:
        self.imports = imports
        self.constants = constants
        self.model_classes: list[str] = []
        self.modules: list[ModuleDiscovery] = []
        self.edges: list[EdgeDiscovery] = []
        self.merges: list[MergeDiscovery] = []
        self.unresolved: list[UnresolvedDiscovery] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
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
        for node in ast.walk(method):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and isinstance(node.value, ast.Call)
            ):
                continue
            resolved = self.imports.resolve(node.value.func)
            if resolved is None or not resolved.startswith("torch.nn."):
                continue
            container = None
            op_type = resolved
            repeat_count = None
            repeat_symbol = None
            if resolved in {"torch.nn.ModuleList", "torch.nn.Sequential"}:
                inner = next(
                    (
                        self.imports.resolve(call.func)
                        for call in ast.walk(node.value)
                        if isinstance(call, ast.Call)
                        and self.imports.resolve(call.func) not in {resolved, None}
                        and (self.imports.resolve(call.func) or "").startswith("torch.nn.")
                    ),
                    None,
                )
                if inner is None:
                    self.unresolved.append(
                        UnresolvedDiscovery("UNRESOLVED_CONTAINER_MEMBER", node.lineno, target.attr)
                    )
                    continue
                container, op_type = resolved.removeprefix("torch.nn."), inner
                if resolved == "torch.nn.ModuleList":
                    repeat_count, repeat_symbol = self._module_list_repeat(node.value)
            parameters = self._parameters_for_call(
                node.value,
                op_type=op_type,
                constructor_arguments=constructor_arguments,
            )
            self.modules.append(
                ModuleDiscovery(
                    target.attr,
                    op_type,
                    node.value.lineno,
                    node.value.col_offset,
                    node.value.end_lineno,
                    node.value.end_col_offset,
                    container,
                    parameters,
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
                        called = _dotted(node.value.func)
                        if called and called.startswith("self."):
                            module = called.removeprefix("self.")
                        elif called in loop_modules:
                            module = loop_modules[called]
                        else:
                            continue
                        source_name = _dotted(node.value.args[0]) if node.value.args else None
                        self.edges.append(EdgeDiscovery(value_origin.get(source_name or "", "input"), module))
                        value_origin[target] = module
                    continue
                if isinstance(node, ast.Return) and isinstance(node.value, ast.Call):
                    called = _dotted(node.value.func)
                    if called and called.startswith("self."):
                        module = called.removeprefix("self.")
                        source_name = _dotted(node.value.args[0]) if node.value.args else None
                        self.edges.append(EdgeDiscovery(value_origin.get(source_name or "", "input"), module))
                        self.edges.append(EdgeDiscovery(module, "output"))

        scan_statements(method.body)


class PyTorchStaticScanner:
    def scan(self, raw_source: bytes) -> StaticRecoveryResult:
        try:
            module = ast.parse(raw_source.decode("utf-8"))
        except UnicodeDecodeError as error:
            raise ValueError("PyTorch source must be UTF-8") from error
        imports = _ImportIndex()
        imports.visit(module)
        constants = {
            target.id: node.value
            for node in module.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(target := node.targets[0], ast.Name)
            and _json_literal(node.value) is not _NOT_LITERAL
        }
        scanner = _ModuleClassScanner(imports, constants)
        scanner.visit(module)
        return StaticRecoveryResult(
            model_classes=scanner.model_classes,
            modules=sorted(scanner.modules, key=lambda item: (item.line, item.attribute_path)),
            edges=sorted(set(scanner.edges), key=lambda item: (item.source, item.target, item.kind)),
            merges=sorted(scanner.merges, key=lambda item: (item.line, item.name)),
            unresolved=sorted(scanner.unresolved, key=lambda item: (item.line, item.code)),
        )
