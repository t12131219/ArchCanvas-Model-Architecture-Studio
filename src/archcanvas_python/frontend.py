"""Bounded static analysis of an explicit PyTorch Module source subset.

User source is parsed as data. No import, decorator, initializer, model forward,
eval, or exec runs. Unknown Python remains an opaque source-backed boundary.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .source_structure import SourceStructure
from .discovery import ModelIndex, NN_BASES, read_directory_files, DiscoveryError

MAX_FILES = 80
MAX_BYTES = 2_000_000
MAX_NODES = 1200
MAX_REPEAT = 16
MAX_SYNTAX_NODES = 100_000


class AnalysisError(ValueError):
    """A source input or analysis budget error safe to show to a client."""


def digest(value: Any) -> str:
    data = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def literal(node: ast.AST | None, env: dict[str, Any]) -> Any:
    """A finite constant domain, deliberately not ast.literal_eval or eval."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool, type(None))):
        return node.value
    if isinstance(node, ast.Name) and node.id in env:
        return env[node.id]
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
        return env.get(f"self.{node.attr}", UNKNOWN)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        value = literal(node.operand, env)
        return not value if type(value) is bool else UNKNOWN
    if isinstance(node, (ast.Tuple, ast.List)):
        values = [literal(item, env) for item in node.elts]
        if all(value is not UNKNOWN for value in values):
            return values
    if isinstance(node, ast.UnaryOp):
        value = literal(node.operand, env)
        if type(value) in (int, float):
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.UAdd):
                return value
    if isinstance(node, ast.BinOp):
        left, right = literal(node.left, env), literal(node.right, env)
        if type(left) in (int, float) and type(right) in (int, float):
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult) and abs(left) < 1e6 and abs(right) < 1e6:
                return left * right
            if isinstance(node.op, ast.FloorDiv) and right:
                return left // right
        if isinstance(left, list) and type(right) is int and isinstance(node.op, ast.Mult) and 0 <= right <= MAX_REPEAT:
            return left * right
    return UNKNOWN


UNKNOWN = object()


def portable_literal(value):
    """Abstract module objects must never escape into JSON parameter facts."""
    return (value is None or type(value) in (str, bool, int)
            or type(value) is float and math.isfinite(value)
            or isinstance(value, (list, tuple)) and all(portable_literal(item) for item in value)
            or isinstance(value, dict) and all(type(key) is str and portable_literal(item) for key, item in value.items()))


@dataclass
class Unit:
    module: str
    path: str
    content: str
    tree: ast.Module
    imports: dict[str, str] = field(default_factory=dict)
    classes: dict[str, ast.ClassDef] = field(default_factory=dict)
    constants: dict[str, Any] = field(default_factory=dict)
    functions: dict[str, ast.FunctionDef] = field(default_factory=dict)
    raw_digest: str | None = None

    def expression(self, node: ast.AST) -> str:
        return ast.get_source_segment(self.content, node) or ast.unparse(node)

    def resolve(self, node: ast.AST, locals: dict[str, Any] | None = None) -> str:
        if isinstance(node, ast.Name):
            if locals and node.id in locals:
                return ""
            if node.id in self.imports:
                return self.imports[node.id]
            return f"{self.module}.{node.id}" if node.id in self.classes or node.id in self.functions else node.id
        if isinstance(node, ast.Attribute):
            base = self.resolve(node.value, locals)
            return f"{base}.{node.attr}" if base else ""
        return ""


class Corpus:
    def __init__(self, root: Path | None = None):
        self.root = root.resolve() if root else None
        self.units: dict[str, Unit] = {}
        self.total_bytes = 0
        self._method_index: ModelIndex | None = None
        self._method_index_signature: tuple[tuple[str, str | None], ...] = ()

    def add(self, module: str, path: str, content: str, raw: bytes | None = None) -> Unit:
        if len(self.units) >= MAX_FILES or self.total_bytes + len(content.encode()) > MAX_BYTES:
            raise AnalysisError("Source corpus budget exceeded (80 files / 2 MB); no complete architecture was produced.")
        try:
            tree = ast.parse(content, filename=path)
        except SyntaxError as exc:
            raise AnalysisError(f"{path}:{exc.lineno}: {exc.msg}") from exc
        except (RecursionError, MemoryError) as exc:
            raise AnalysisError(f"{path}: parser resource budget exceeded.") from exc
        if sum(1 for _ in ast.walk(tree)) > MAX_SYNTAX_NODES:
            raise AnalysisError(f"{path}: syntax node budget exceeded (100000).")
        unit = Unit(module, path, content, tree)
        unit.raw_digest = digest(raw if raw is not None else content.encode("utf-8"))
        self.units[module] = unit
        self.total_bytes += len(content.encode())
        for statement in tree.body:
            if isinstance(statement, ast.ClassDef):
                unit.classes[statement.name] = statement
                unit.imports.pop(statement.name, None)
            elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                unit.imports.pop(statement.name, None)
                if isinstance(statement, ast.FunctionDef) and not statement.decorator_list:
                    unit.functions[statement.name] = statement
            elif isinstance(statement, ast.Import):
                for alias in statement.names:
                    unit.imports[alias.asname or alias.name.split(".")[0]] = alias.name if alias.asname else alias.name.split(".")[0]
            elif isinstance(statement, ast.ImportFrom):
                package = module.split(".") if path.endswith("/__init__.py") or path == "__init__.py" else module.split(".")[:-1]
                if statement.level:
                    prefix = package[:len(package) - statement.level + 1]
                    imported = ".".join(prefix + ([statement.module] if statement.module else []))
                else:
                    imported = statement.module or ""
                for alias in statement.names:
                    if alias.name != "*":
                        unit.imports[alias.asname or alias.name] = f"{imported}.{alias.name}".strip(".")
            elif isinstance(statement, ast.Assign):
                alias = unit.resolve(statement.value) if isinstance(statement.value, (ast.Name, ast.Attribute)) else ""
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        unit.imports.pop(target.id, None)
                        unit.functions.pop(target.id, None)
                        if alias:
                            unit.imports[target.id] = alias
                value = literal(statement.value, unit.constants)
                if value is not UNKNOWN:
                    for target in statement.targets:
                        if isinstance(target, ast.Name):
                            unit.constants[target.id] = value
        return unit

    def load(self, module: str) -> Unit | None:
        if module in self.units:
            return self.units[module]
        if not self.root or not module or any(not part.isidentifier() for part in module.split(".")):
            return None
        base = self.root.joinpath(*module.split("."))
        for candidate in (base.with_suffix(".py"), base / "__init__.py"):
            actual = candidate.resolve()
            if not actual.is_relative_to(self.root):
                raise AnalysisError("Source import resolves outside the selected project root.")
            if actual.is_file():
                if actual.stat().st_size > MAX_BYTES:
                    raise AnalysisError("A source file exceeds the 2 MB corpus budget.")
                try:
                    raw = actual.read_bytes()
                    content = raw.decode("utf-8-sig")
                except (OSError, UnicodeError) as exc:
                    raise AnalysisError(f"Cannot read Python source {candidate.name}: {exc}") from exc
                unit = self.add(module, actual.relative_to(self.root).as_posix(), content, raw)
                # Discover local import dependencies without importing packages.
                for qualified in list(unit.imports.values()):
                    pieces = qualified.split(".")
                    for count in range(len(pieces), 0, -1):
                        if self.load(".".join(pieces[:count])):
                            break
                return unit
        return None

    def definition(self, qualified: str, seen: set[str] | None = None) -> tuple[Unit, ast.ClassDef] | None:
        seen = set() if seen is None else seen
        if qualified in seen:
            return None
        seen.add(qualified)
        module, _, name = qualified.rpartition(".")
        unit = self.load(module)
        if unit and name in unit.classes:
            return unit, unit.classes[name]
        if unit and name in unit.imports:
            return self.definition(unit.imports[name], seen)
        return None

    def factory(self, qualified: str, seen: set[str] | None = None) -> tuple[Unit, ast.FunctionDef] | None:
        seen = set() if seen is None else seen
        if qualified in seen:
            return None
        seen.add(qualified)
        module, _, name = qualified.rpartition(".")
        unit = self.load(module)
        if not unit:
            return None
        if name in unit.imports:
            return self.factory(unit.imports[name], seen)
        function = unit.functions.get(name)
        if not function or function.decorator_list:
            return None
        # The analyzer separately certifies the complete bounded body. Merely
        # finding a return never authorizes skipping earlier side effects.
        bindings = [item for item in unit.tree.body if
                    isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and item.name == name
                    or not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and
                    any(isinstance(part, ast.Name) and part.id == name and isinstance(part.ctx, (ast.Store, ast.Del)) for part in ast.walk(item))]
        return (unit, function) if bindings == [function] else None

    def framework_is_unshadowed(self) -> bool:
        """A local module named torch cannot prove an external PyTorch contract."""
        return not any(name == "torch" or name.startswith("torch.") for name in self.units)

    def entry_method(self, unit: Unit, definition: ast.ClassDef) -> tuple[Unit, ast.FunctionDef] | None:
        """Resolve Python's local C3 lookup and a custom __call__ before forward.

        Base definitions are loaded as source data before building the index;
        dynamic/decorated entry methods remain an opaque boundary.
        """
        def load_bases(own: Unit, cls: ast.ClassDef, seen: set[str]) -> None:
            key = f"{own.module}:{cls.name}"
            if key in seen: return
            seen.add(key)
            for base in cls.bases:
                inherited = self.definition(own.resolve(base))
                if inherited: load_bases(*inherited, seen)
        load_bases(unit, definition, set())
        signature = tuple(sorted((own.path, own.raw_digest) for own in self.units.values()))
        if self._method_index is None or self._method_index_signature != signature:
            self._method_index = ModelIndex({own.path: own.content for own in self.units.values()})
            self._method_index_signature = signature
        index = self._method_index
        key = f"{unit.module}:{definition.name}"
        if index.resolve(key) != key:
            return None
        method = index.effective_method(key)
        if not method or not isinstance(method[1], ast.FunctionDef) or method[1].decorator_list:
            return None
        path, function = method
        own = next((candidate for candidate in self.units.values() if candidate.path == path), None)
        return (own, function) if own else None


# Only exact framework-qualified constructors receive these public contracts.
# This registry describes atomic external calls, never authored library internals.
CONTRACTS: dict[str, tuple[list[str], str]] = {
    "Linear": (["in_features", "out_features", "bias"], "linear"),
    "Embedding": (["num_embeddings", "embedding_dim"], "embedding"),
    "LayerNorm": (["normalized_shape", "eps", "elementwise_affine"], "norm"),
    "Dropout": (["p", "inplace"], "regularization"),
    "ReLU": (["inplace"], "activation"),
    "GELU": (["approximate"], "activation"),
    "SiLU": (["inplace"], "activation"),
    "Identity": ([], "operator"),
    "Conv2d": (["in_channels", "out_channels", "kernel_size", "stride", "padding"], "convolution"),
    "BatchNorm2d": (["num_features", "eps", "momentum"], "norm"),
    "AdaptiveAvgPool2d": (["output_size"], "pooling"),
    "MaxPool2d": (["kernel_size", "stride", "padding"], "pooling"),
    "Flatten": (["start_dim", "end_dim"], "operator"),
    "MultiheadAttention": (["embed_dim", "num_heads", "dropout", "bias", "add_bias_kv", "add_zero_attn", "kdim", "vdim", "batch_first"], "attention"),
    "LSTM": (["input_size", "hidden_size", "num_layers", "bias", "batch_first", "dropout", "bidirectional"], "recurrent"),
}


# Exact external framework contracts, researched against official PyTorch APIs.
# Positional parameter lists preserve imported source facts; no model is executed.
for _dim in (1, 2, 3):
    for _transpose in (False, True):
        _name = f'Conv{"Transpose" if _transpose else ""}{_dim}d'
        _args = ['in_channels', 'out_channels', 'kernel_size', 'stride', 'padding']
        if _transpose: _args += ['output_padding', 'groups', 'bias', 'dilation']
        else: _args += ['dilation', 'groups', 'bias', 'padding_mode']
        CONTRACTS[_name] = (_args, 'convolution')
    for _operation in ('Max', 'Avg'):
        _args = ['kernel_size', 'stride', 'padding'] + (['dilation', 'return_indices', 'ceil_mode'] if _operation == 'Max' else ['ceil_mode', 'count_include_pad'])
        CONTRACTS[f'{_operation}Pool{_dim}d'] = (_args, 'pooling')
        CONTRACTS[f'Adaptive{_operation}Pool{_dim}d'] = (['output_size'] + (['return_indices'] if _operation == 'Max' else []), 'pooling')
    for _norm in ('Batch', 'Instance'):
        CONTRACTS[f'{_norm}Norm{_dim}d'] = (['num_features', 'eps', 'momentum', 'affine', 'track_running_stats'], 'norm')
for _kind, _args in {
    'Sigmoid': [], 'Tanh': [], 'ReLU6': ['inplace'], 'LeakyReLU': ['negative_slope', 'inplace'],
    'ELU': ['alpha', 'inplace'], 'SELU': ['inplace'], 'Softplus': ['beta', 'threshold'], 'Softsign': [],
    'Hardsigmoid': ['inplace'], 'Hardswish': ['inplace'], 'PReLU': ['num_parameters', 'init'],
    'Softmax': ['dim'], 'LogSoftmax': ['dim'],
}.items(): CONTRACTS[_kind] = (_args, 'activation')
for _kind in ('Dropout1d', 'Dropout2d', 'Dropout3d', 'AlphaDropout', 'FeatureAlphaDropout'):
    CONTRACTS[_kind] = (['p', 'inplace'], 'regularization')
CONTRACTS.update({
    'Unflatten': (['dim', 'unflattened_size'], 'operator'),
    'Upsample': (['size', 'scale_factor', 'mode', 'align_corners', 'recompute_scale_factor'], 'operator'),
    'GroupNorm': (['num_groups', 'num_channels', 'eps', 'affine'], 'norm'),
    'RMSNorm': (['normalized_shape', 'eps', 'elementwise_affine'], 'norm'),
    'RNN': (['input_size', 'hidden_size', 'num_layers', 'nonlinearity', 'bias', 'batch_first', 'dropout', 'bidirectional'], 'recurrent'),
    'GRU': (['input_size', 'hidden_size', 'num_layers', 'bias', 'batch_first', 'dropout', 'bidirectional'], 'recurrent'),
})


@dataclass
class Spec:
    identity: str
    kind: str
    category: str
    parameters: dict[str, Any]
    unit: Unit
    source: ast.AST
    definition: ast.ClassDef | None = None
    env: dict[str, Any] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)
    items: list["Spec"] = field(default_factory=list)
    parameter_origins: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Ref:
    node: str
    port: str
    tensor: str
    # Inspection-only variable provenance. The canonical tensor/port stays
    # conservative, while distinct opaque assignments keep distinct exits.
    source_slot: str | None = None


def refs(value: Any) -> list[Ref]:
    if isinstance(value, Ref):
        return [value]
    if isinstance(value, (tuple, list)):
        return [ref for item in value for ref in refs(item)]
    if isinstance(value, dict):
        return [ref for item in value.values() for ref in refs(item)]
    return []


def output_bindings(value: Any, path: list[dict[str, Any]] | None = None) -> list[tuple[Ref, list[dict[str, Any]]]]:
    """Retain every tensor occurrence and its authored fixed-container slot.

    This intentionally preserves repeated references rather than deduplicating
    by producer/tensor identity. Opaque values have no fabricated inner slots.
    """
    path = [] if path is None else path
    if isinstance(value, Ref):
        return [(value, path)]
    if isinstance(value, (tuple, list)):
        return [binding for index, item in enumerate(value)
                for binding in output_bindings(item, [*path, {"kind": "index", "index": index}])]
    if isinstance(value, dict):
        return [binding for key, item in value.items()
                for binding in output_bindings(item, [*path, {"kind": "key", "key": key}])]
    return []


def validate_output_paths(nodes: list[dict[str, Any]]) -> None:
    """Validate optional v1 slot evidence in generated or imported nodes."""
    for node in nodes:
        if not isinstance(node, dict) or "outputPath" not in node:
            continue
        if node.get("kind") != "Output" or node.get("category") != "output" or not isinstance(node["outputPath"], list):
            raise AnalysisError("outputPath belongs only to graph Output nodes and must be an array.")
        for segment in node["outputPath"]:
            if not isinstance(segment, dict):
                raise AnalysisError("outputPath segments must be key/index objects.")
            if segment.get("kind") == "index":
                index = segment.get("index")
                if set(segment) != {"kind", "index"} or type(index) is not int or not 0 <= index <= 2**53 - 1:
                    raise AnalysisError("outputPath index must be a nonnegative safe integer.")
            elif segment.get("kind") == "key":
                key = segment.get("key")
                valid = (key is None or type(key) in (str, bool)
                         or type(key) is int and abs(key) <= 2**53 - 1
                         or type(key) is float and math.isfinite(key) and abs(key) <= 2**53 - 1)
                if set(segment) != {"kind", "key"} or not valid:
                    raise AnalysisError("outputPath key must be a portable finite JSON scalar.")
            else:
                raise AnalysisError("outputPath segments require a key/index kind.")


class Analyzer:
    def __init__(self, corpus: Corpus):
        self.corpus = corpus
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self.diagnostics: list[dict[str, str]] = []
        self.counters: dict[str, int] = {}
        self.depth = 0
        self.source_regions = []
        self.source_uses = []

    def warn(self, message: str):
        if not any(item["message"] == message for item in self.diagnostics):
            self.diagnostics.append({"level": "warning", "message": message})

    def source(self, unit: Unit, node: ast.AST) -> dict[str, Any]:
        return {"path": unit.path, "line": getattr(node, "lineno", 1), "endLine": getattr(node, "end_lineno", 1), "expression": unit.expression(node)}

    def parameter_origin(self, unit: Unit, expression: ast.AST, env: dict[str, Any]) -> dict[str, Any]:
        """Expose exact argument evidence; values resolved from names are not editable literals."""
        if isinstance(expression, ast.Constant) and type(expression.value) in (int, float, str, bool):
            kind = "literal"
        elif isinstance(expression, ast.Name):
            kind = "constructor_argument" if expression.id in env and expression.id not in unit.constants else "unknown"
        elif isinstance(expression, (ast.BinOp, ast.UnaryOp)):
            kind = "derived"
        else:
            kind = "unknown"
        return {"kind": kind, **self.source(unit, expression), "column": getattr(expression, "col_offset", 0), "endColumn": getattr(expression, "end_col_offset", 0)}

    def node(self, key: str, label: str, kind: str, category: str, parent: str | None, unit: Unit, source: ast.AST, *, evidence: str = "source", parameters: dict[str, Any] | None = None, instance: str | None = None) -> dict[str, Any]:
        if len(self.nodes) >= MAX_NODES:
            raise AnalysisError("Architecture node budget exceeded (1200); simplify the entry or layer count.")
        count = self.counters.get(key, 0)
        self.counters[key] = count + 1
        identity = key if count == 0 else f"{key}@{count + 1}"
        item: dict[str, Any] = {"id": identity, "label": label, "kind": kind, "category": category, "children": [], "ports": [], "parameters": parameters or {}, "source": self.source(unit, source), "evidence": evidence}
        if parent:
            item["parentId"] = parent
            next(node for node in self.nodes if node["id"] == parent)["children"].append(identity)
        if instance:
            item["instanceId"] = instance
            item["callId"] = identity
        self.nodes.append(item)
        return item

    def port(self, node: dict[str, Any], name: str, direction: str, role: str = "data") -> str:
        identity = f"{node['id']}:{direction}:{name}"
        if not any(port["id"] == identity for port in node["ports"]):
            node["ports"].append({"id": identity, "name": name, "direction": direction, "role": role, "ordinal": sum(port["direction"] == direction for port in node["ports"])})
        return identity

    def out(self, node: dict[str, Any], name: str = "output") -> Ref:
        return Ref(node["id"], self.port(node, name, "out"), f"tensor:{node['id']}:{name}")

    def bind(self, value: Any, node: dict[str, Any], name: str, role: str = "data"):
        for index, value_ref in enumerate(refs(value)):
            port = self.port(node, name if index == 0 else f"{name}.{index}", "in", role)
            self.edges.append({"id": f"edge:{len(self.edges)}", "source": {"nodeId": value_ref.node, "portId": value_ref.port}, "target": {"nodeId": node["id"], "portId": port}, "tensorId": value_ref.tensor, "role": role})
            if value_ref.source_slot is not None:
                self.source_uses.append((value_ref, self.edges[-1]))

    def is_module(self, unit: Unit, definition: ast.ClassDef, seen: set[str] | None = None) -> bool:
        seen = seen or set()
        key = f"{unit.module}.{definition.name}"
        if key in seen:
            return False
        seen.add(key)
        for base in definition.bases:
            qualified = unit.resolve(base)
            if qualified.startswith("torch.nn.") and qualified[9:] in NN_BASES and self.corpus.framework_is_unshadowed():
                return True
            inherited = self.corpus.definition(qualified)
            if inherited and self.is_module(*inherited, seen):
                return True
        return False

    @staticmethod
    def bind_static(function: ast.FunctionDef, args: list[Any], keywords: dict[str, Any], env: dict[str, Any], *, method: bool = False) -> dict[str, Any] | None:
        positional = [*function.args.posonlyargs, *function.args.args][int(method):]
        if function.args.vararg or function.args.kwarg or len(args) > len(positional):
            return None
        names = [item.arg for item in positional]
        defaults = dict(zip(names[-len(function.args.defaults):], function.args.defaults)) if function.args.defaults else {}
        defaults.update({item.arg: value for item, value in zip(function.args.kwonlyargs, function.args.kw_defaults) if value is not None})
        allowed = set(names + [item.arg for item in function.args.kwonlyargs])
        bound = dict(zip(names, args))
        if set(keywords) - allowed or set(bound) & set(keywords) or set(keywords) & {item.arg for item in function.args.posonlyargs[int(method):]}:
            return None
        bound.update(keywords)
        for name in allowed - bound.keys():
            bound[name] = literal(defaults[name], env) if name in defaults else UNKNOWN
        return bound

    def factory_expression(self, unit: Unit, function: ast.FunctionDef, stack=()) -> ast.AST | None:
        key = unit.module, function.name
        if key in stack or len(stack) >= 12:
            return None
        body = [item for item in function.body if not (isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str))]
        if not 1 <= len(body) <= 80 or not isinstance(body[-1], ast.Return) or body[-1].value is None:
            return None
        local = {item.arg: UNKNOWN for item in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]}
        expressions = []
        for statement in body[:-1]:
            if not isinstance(statement, (ast.Assign, ast.AnnAssign)) or statement.value is None:
                return None
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            if not all(isinstance(target, ast.Name) for target in targets):
                return None
            # Local rebinding must not change a constructor/import symbol used
            # earlier in this same factory; resolve against the complete scope.
            local.update({target.id: UNKNOWN for target in targets})
            expressions.append(statement.value)
        expressions.append(body[-1].value)
        for part in (part for expression in expressions for part in ast.walk(expression)):
            if isinstance(part, ast.Call):
                qualified = unit.resolve(part.func, local)
                short = qualified.rsplit(".", 1)[-1]
                if qualified == "copy.deepcopy" and "copy" not in self.corpus.units:
                    continue
                if qualified == "range" and self.constant_range(part, {**unit.constants, **{key: 1 for key in local}}, unit) is not None:
                    continue
                if self.corpus.framework_is_unshadowed() and qualified == f"torch.nn.{short}" and short in (*CONTRACTS, "ModuleList", "Sequential"):
                    continue
                definition = self.corpus.definition(qualified)
                if definition and self.is_module(*definition):
                    continue
                factory = self.corpus.factory(qualified)
                if factory and self.factory_expression(*factory, (*stack, key)) is not None:
                    continue
                return None
            if isinstance(part, (ast.NamedExpr, ast.Await, ast.Yield, ast.Lambda)):
                return None
        return body[-1].value

    def factory_value(self, unit, function, bound, identity, depth):
        """Interpret only certified assignment/return syntax as source data."""
        env = {**unit.constants, **bound}
        for statement in function.body:
            if isinstance(statement, ast.Expr):
                continue  # factory_expression admitted only a docstring here.
            expression = statement.value
            local_identity = identity if isinstance(statement, ast.Return) else f"{identity}.{(statement.targets[0] if isinstance(statement, ast.Assign) else statement.target).id}@factory:{statement.lineno}"
            value = self.construct(expression, unit, env, {}, local_identity, depth + 1)
            if value is None:
                value = literal(expression, env)
            if isinstance(statement, ast.Return):
                return value if value is not UNKNOWN else None
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            for target in targets:
                env[target.id] = value
        return None

    @staticmethod
    def method_environment(spec, unit):
        """Methods use their defining module globals, never __init__ locals."""
        return {**unit.constants, **{key: value for key, value in spec.env.items() if key.startswith("self.")}}

    def construct(self, expression: ast.AST, unit: Unit, env: dict[str, Any], attributes: dict[str, Any], identity: str, depth: int = 0) -> Any:
        if depth > 12:
            return None
        if isinstance(expression, ast.Name) and isinstance(env.get(expression.id), (Spec, list, tuple)):
            return env[expression.id]
        if isinstance(expression, ast.Attribute) and isinstance(expression.value, ast.Name) and expression.value.id == "self":
            return attributes.get(expression.attr)
        if isinstance(expression, (ast.List, ast.Tuple)):
            values = [self.construct(item, unit, env, attributes, f"{identity}.{index}", depth + 1) for index, item in enumerate(expression.elts)]
            return tuple(values) if isinstance(expression, ast.Tuple) else values
        if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Mult):
            values = self.construct(expression.left, unit, env, attributes, identity, depth + 1)
            count = literal(expression.right, env)
            if isinstance(values, list) and type(count) is int and 0 <= count <= MAX_REPEAT:
                return values * count
        if isinstance(expression, ast.ListComp) and len(expression.generators) == 1:
            generator = expression.generators[0]
            if isinstance(generator.target, ast.Name) and not generator.ifs:
                values = self.constant_range(generator.iter, env, unit)
                if values is not None:
                    return [self.construct(expression.elt, unit, {**env, generator.target.id: index}, attributes, f"{identity}.{index}", depth + 1) for index in values]
        if not isinstance(expression, ast.Call):
            return None
        qualified = unit.resolve(expression.func, env)
        short = qualified.rsplit(".", 1)[-1]
        if qualified == "copy.deepcopy" and "copy" not in self.corpus.units and len(expression.args) == 1 and not expression.keywords:
            value = self.construct(expression.args[0], unit, env, attributes, identity, depth + 1)
            if isinstance(value, Spec):
                copied = copy.deepcopy(value, {id(item): item for item in self.corpus.units.values()})
                seen: set[int] = set()
                def identify(item):
                    if isinstance(item, Spec) and id(item) not in seen:
                        seen.add(id(item)); item.identity = f"{identity}@copy:{len(seen)}"
                        for child in [*item.attributes.values(), *item.items, *item.env.values()]: identify(child)
                    elif isinstance(item, list):
                        for child in item: identify(child)
                identify(copied)
                return copied
            return None
        factory = self.corpus.factory(qualified)
        if factory:
            factory_unit, function = factory
            body = self.factory_expression(factory_unit, function)
            if body is not None and not any(keyword.arg is None for keyword in expression.keywords):
                argument = lambda value, suffix: self.construct(value, unit, env, attributes, f"{identity}.{suffix}", depth + 1) or literal(value, env)
                bound = self.bind_static(function, [argument(value, f"arg{index}") for index, value in enumerate(expression.args)], {item.arg: argument(item.value, item.arg) for item in expression.keywords}, factory_unit.constants)
                if bound is not None:
                    return self.factory_value(factory_unit, function, bound, identity, depth + 1)
        if qualified in ("torch.nn.ModuleList", "torch.nn.Sequential") and self.corpus.framework_is_unshadowed():
            if short == "ModuleList":
                items = self.construct(expression.args[0], unit, env, attributes, identity, depth + 1) if expression.args else []
            else:
                items = [self.construct(arg, unit, env, attributes, f"{identity}.{index}", depth + 1) for index, arg in enumerate(expression.args)]
            if not isinstance(items, list) or not all(isinstance(item, Spec) for item in items):
                self.warn(f"Unsupported {short} construction at {unit.path}:{expression.lineno}; retained opaque.")
                return Spec(identity, short, "opaque", {}, unit, expression)
            return Spec(identity, short, "container", {}, unit, expression, items=items)
        definition = self.corpus.definition(qualified)
        if definition and self.is_module(*definition):
            own_unit, cls = definition
            initialized = self.local_initializer(own_unit, cls)
            init_unit, init_cls, initializer = initialized if initialized else (own_unit, cls, None)
            local = dict(init_unit.constants)
            if not initializer and any(own_unit.resolve(base) != "torch.nn.Module" for base in cls.bases):
                self.warn(f"Inherited initializer for {cls.name} is outside the initial subset; unresolved attributes remain opaque.")
            if initializer:
                params = [*initializer.args.posonlyargs, *initializer.args.args][1:] + list(initializer.args.kwonlyargs)
                argument = lambda value, suffix: self.construct(value, unit, env, attributes, f"{identity}.{suffix}", depth + 1) or literal(value, env)
                bound = None if any(isinstance(item, ast.Starred) for item in expression.args) or any(item.arg is None for item in expression.keywords) else self.bind_static(initializer, [argument(value, params[index].arg if index < len(params) else f"arg{index}") for index, value in enumerate(expression.args)], {item.arg: argument(item.value, item.arg) for item in expression.keywords}, local, method=True)
                if bound is None:
                    self.warn(f"Constructor binding for {cls.name} is outside the supported signature subset; retained opaque.")
                    return Spec(identity, cls.name, "opaque", {}, own_unit, expression)
                local.update(bound)
                unresolved = [param.arg for param in params if local.get(param.arg) is UNKNOWN]
                if unresolved:
                    self.warn(f"Constructor arguments for {cls.name} remain symbolic ({', '.join(unresolved)}); this is not a claim of valid executable instantiation.")
            spec = Spec(identity, cls.name, "container", {key: value for key, value in local.items() if portable_literal(value)}, own_unit, expression, cls, local)
            # Lexical super lookup follows the initializer's defining class,
            # while overridden self methods still dispatch on the receiver.
            spec.receiver_definition = (own_unit, cls)
            if initializer:
                initial_spec = copy.copy(spec)
                initial_spec.unit, initial_spec.definition = init_unit, init_cls
                self.initializer_statements(initializer.body, initial_spec, depth)
            return spec
        params: dict[str, Any] = {}
        origins: dict[str, Any] = {}
        contract = CONTRACTS.get(short) if qualified == f"torch.nn.{short}" and self.corpus.framework_is_unshadowed() else None
        positional = contract[0] if contract else []
        for index, arg in enumerate(expression.args):
            value = literal(arg, env)
            name = positional[index] if index < len(positional) else f"arg{index}"
            params[name] = value if portable_literal(value) else {"expression": unit.expression(arg), "origin": "unknown"}
            origins[name] = self.parameter_origin(unit, arg, env)
        for keyword in expression.keywords:
            if keyword.arg:
                value = literal(keyword.value, env)
                params[keyword.arg] = value if portable_literal(value) else {"expression": unit.expression(keyword.value), "origin": "unknown"}
                origins[keyword.arg] = self.parameter_origin(unit, keyword.value, env)
        if not contract:
            self.warn(f"Unknown constructor {qualified or unit.expression(expression.func)} at {unit.path}:{expression.lineno}; no type semantics inferred from its name.")
        return Spec(identity, short or "Unknown", contract[1] if contract else "opaque", params, unit, expression, parameter_origins=origins)

    def local_initializer(self, unit, cls):
        """Locate an ordinary inherited initializer through local C3 lookup."""
        self.corpus.entry_method(unit, cls)  # Load local base source definitions.
        index = ModelIndex({own.path: own.content for own in self.corpus.units.values()})
        method = index.method(f"{unit.module}:{cls.name}", "__init__")
        if not method or not isinstance(method[1], ast.FunctionDef) or method[1].decorator_list:
            return None
        path, function = method
        own = next((candidate for candidate in self.corpus.units.values() if candidate.path == path), None)
        definition = next((candidate for candidate in own.classes.values()
                           if candidate.lineno <= function.lineno <= candidate.end_lineno), None) if own else None
        return (own, definition, function) if own and definition else None

    def super_initializer(self, expression, spec, depth):
        """Bind a single local base initializer; uncertain MRO stays opaque."""
        if (not spec.definition or depth >= 12 or not isinstance(expression, ast.Call)
                or not isinstance(expression.func, ast.Attribute) or expression.func.attr != "__init__"
                or not isinstance(expression.func.value, ast.Call)):
            return False
        call = expression.func.value
        if not isinstance(call.func, ast.Name) or call.func.id != "super" or "super" in spec.env or call.keywords:
            return False
        if call.args and not (len(call.args) == 2 and isinstance(call.args[0], ast.Name)
                              and call.args[0].id == spec.definition.name and isinstance(call.args[1], ast.Name)
                              and call.args[1].id == "self"):
            return False
        if len(spec.definition.bases) != 1 or any(isinstance(item, ast.Starred) for item in expression.args) or any(item.arg is None for item in expression.keywords):
            return False
        base = spec.unit.resolve(spec.definition.bases[0])
        argument = lambda value, suffix: self.construct(value, spec.unit, spec.env, spec.attributes, f"{spec.identity}.super.{suffix}", depth + 1) or literal(value, spec.env)
        args = [argument(value, f"arg{index}") for index, value in enumerate(expression.args)]
        keywords = {item.arg: argument(item.value, item.arg) for item in expression.keywords}
        if base == "torch.nn.Module" and self.corpus.framework_is_unshadowed():
            return not args and not keywords
        if base == "torch.nn.Sequential" and self.corpus.framework_is_unshadowed():
            if keywords or not all(isinstance(value, Spec) for value in args):
                return False
            spec.items.extend(args)
            return True
        definition = self.corpus.definition(base)
        initialized = self.local_initializer(*definition) if definition else None
        if not initialized:
            return False
        unit, cls, function = initialized
        bound = self.bind_static(function, args, keywords, unit.constants, method=True)
        if bound is None:
            return False
        inherited = copy.copy(spec)
        inherited.unit, inherited.definition = unit, cls
        inherited.env = {**unit.constants, **bound, **{key: value for key, value in spec.env.items() if key.startswith("self.")}}
        self.initializer_statements(function.body, inherited, depth + 1)
        spec.env.update({key: value for key, value in inherited.env.items() if key.startswith("self.")})
        return True

    def initializer_unknown(self, statements: list[ast.stmt], spec: Spec):
        """Invalidate facts that an unsupported initializer region can replace.

        Reassignment affects an attribute name. Mutation can affect all aliases
        of the existing object. Neither operation may leave an earlier contract
        behind merely because its replacement cannot be constructed statically.
        """
        replaced: set[str] = set()
        mutated: set[str] = set()
        local_names: set[str] = set()
        unknown_self_call = False
        local_mutations: set[str] = set()

        def self_attribute(node: ast.AST) -> str | None:
            while isinstance(node, (ast.Attribute, ast.Subscript)):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
                    return node.attr
                node = node.value
            return None

        for statement in statements:
            for item in ast.walk(statement):
                if isinstance(item, (ast.Attribute, ast.Subscript)) and isinstance(item.ctx, (ast.Store, ast.Del)):
                    base = item.value
                    while isinstance(base, (ast.Attribute, ast.Subscript)): base = base.value
                    if isinstance(base, ast.Name) and isinstance(spec.env.get(base.id), (Spec, list)):
                        local_mutations.add(base.id)
                if isinstance(item, ast.Name) and isinstance(item.ctx, (ast.Store, ast.Del)):
                    local_names.add(item.id)
                if isinstance(item, (ast.Attribute, ast.Subscript)) and isinstance(item.ctx, (ast.Store, ast.Del)):
                    attribute = self_attribute(item)
                    if attribute:
                        direct = isinstance(item, ast.Attribute) and isinstance(item.value, ast.Name) and item.value.id == "self"
                        (replaced if direct else mutated).add(attribute)
                if isinstance(item, ast.Call):
                    dependencies = [*item.args, *(keyword.value for keyword in item.keywords)]
                    if isinstance(item.func, ast.Attribute): dependencies.append(item.func.value)
                    for argument in dependencies:
                        for part in ast.walk(argument):
                            if isinstance(part, ast.Name) and isinstance(spec.env.get(part.id), (Spec, list)):
                                local_mutations.add(part.id)
                    if isinstance(item.func, ast.Attribute):
                        attribute = self_attribute(item.func.value)
                        if attribute:
                            mutated.add(attribute)
                        elif isinstance(item.func.value, ast.Name) and item.func.value.id == "self":
                            unknown_self_call = True
                    if any(isinstance(argument, ast.Name) and argument.id == "self"
                           for argument in item.args + [keyword.value for keyword in item.keywords]):
                        unknown_self_call = True
                    for argument in item.args + [keyword.value for keyword in item.keywords]:
                        for dependency in ast.walk(argument):
                            attribute = self_attribute(dependency)
                            if attribute:
                                mutated.add(attribute)
        visited: set[int] = set()
        def invalidate_local(value):
            if isinstance(value, Spec) and id(value) not in visited:
                visited.add(id(value))
                for child in [*value.attributes.values(), *value.items]: invalidate_local(child)
                value.kind, value.category = "OpaqueModule", "opaque"
                value.parameters.clear(); value.parameter_origins.clear(); value.definition = None
                value.env.clear(); value.attributes.clear(); value.items.clear()
            elif isinstance(value, list):
                for child in value: invalidate_local(child)
        for name in local_mutations: invalidate_local(spec.env.get(name))
        if unknown_self_call:
            mutated.update(spec.attributes)
        mutated_identities = {spec.attributes[name].identity for name in mutated
                              if isinstance(spec.attributes.get(name), Spec)}
        affected = replaced | mutated | {name for name, value in spec.attributes.items()
                                         if isinstance(value, Spec) and value.identity in mutated_identities}
        # Mutate the abstract object in place: ModuleList/Sequential and aliases
        # can have captured this same instance before the uncertain mutation.
        # Replacing only the attribute would leave those references proven.
        for name in mutated:
            value = spec.attributes.get(name)
            if isinstance(value, Spec):
                value.kind, value.category = "OpaqueModule", "opaque"
                value.parameters.clear()
                value.parameter_origins.clear()
                value.definition = None
                value.env.clear()
                value.attributes.clear()
                value.items.clear()
        for name in replaced:
            self.retire_captured_binding(spec, name)
            spec.attributes[name] = Spec(f"{spec.identity}.{name}", name, "opaque", {}, spec.unit, statements[0])
        for name in affected:
            spec.env.pop(f"self.{name}", None)
        for name in local_names:
            spec.env[name] = UNKNOWN
        first = statements[0]
        self.warn(f"Unsupported initializer region at {spec.unit.path}:{first.lineno}; affected attributes ({', '.join(sorted(affected)) or 'unresolved'}) remain opaque.")

    def retire_captured_binding(self, owner: Spec, name: str):
        """Keep captured old objects distinct from a new attribute binding.

        Ordinary instance IDs remain the attribute path. When that path is
        rebound, an old object surviving through another alias or container
        receives a deterministic constructor-occurrence suffix, without
        changing instances merely referenced through an alias of another owner.
        """
        previous = owner.attributes.get(name)
        canonical = f"{owner.identity}.{name}"
        if not isinstance(previous, Spec) or previous.identity != canonical:
            return
        owned: set[int] = set()

        def owned_objects(value: Any):
            if isinstance(value, Spec):
                if id(value) in owned or not (value.identity == canonical or value.identity.startswith(canonical + ".")):
                    return
                owned.add(id(value))
                for item in [*value.attributes.values(), *value.items]:
                    owned_objects(item)
            elif isinstance(value, (tuple, list)):
                for item in value:
                    owned_objects(item)

        owned_objects(previous)
        visited: set[int] = set()

        def captured(value: Any) -> bool:
            if id(value) in owned:
                return True
            if isinstance(value, Spec):
                if id(value) in visited:
                    return False
                visited.add(id(value))
                return any(captured(item) for key, item in value.attributes.items()
                           if value is not owner or key != name) or any(captured(item) for item in value.items)
            if isinstance(value, (tuple, list)):
                return any(captured(item) for item in value)
            return False

        if not any(captured(value) for key, value in owner.attributes.items() if key != name):
            return
        expression = ast.dump(previous.source, include_attributes=False)
        occurrence = 0
        for item in ast.walk(previous.unit.tree):
            if item is previous.source:
                break
            if type(item) is type(previous.source) and ast.dump(item, include_attributes=False) == expression:
                occurrence += 1
        construction = digest({"path": previous.unit.path, "expression": expression, "occurrence": occurrence})
        retired = f"{canonical}@construction:{construction}"
        renamed: set[int] = set()

        def rename(value: Any):
            if isinstance(value, Spec):
                if id(value) in renamed:
                    return
                renamed.add(id(value))
                if value.identity == canonical or value.identity.startswith(canonical + "."):
                    value.identity = retired + value.identity[len(canonical):]
                for item in [*value.attributes.values(), *value.items]:
                    rename(item)
            elif isinstance(value, (tuple, list)):
                for item in value:
                    rename(item)

        rename(previous)

    def initializer_expression_mutations(self, expression: ast.AST, spec: Spec):
        """An unknown RHS helper can mutate a module passed to it as an argument."""
        for item in ast.walk(expression):
            if not isinstance(item, ast.Call):
                continue
            qualified = spec.unit.resolve(item.func, spec.env)
            short = qualified.rsplit(".", 1)[-1]
            trusted_constructor = (self.corpus.framework_is_unshadowed()
                                   and qualified == f"torch.nn.{short}"
                                   and (short in CONTRACTS or short in ("ModuleList", "Sequential")))
            factory = self.corpus.factory(qualified)
            trusted_factory = factory and self.factory_expression(*factory) is not None
            trusted_copy = qualified == "copy.deepcopy" and "copy" not in self.corpus.units and len(item.args) == 1 and not item.keywords
            definition = self.corpus.definition(qualified)
            analyzed_constructor = definition and self.is_module(*definition) and any(isinstance(member, ast.FunctionDef) and member.name == "__init__" for member in definition[1].body)
            if trusted_constructor or trusted_factory or trusted_copy or analyzed_constructor:
                continue
            dependencies = [*item.args, *(keyword.value for keyword in item.keywords)]
            if isinstance(item.func, ast.Attribute):
                dependencies.append(item.func.value)
            if any(isinstance(dependency, ast.Name) and (dependency.id == "self" or isinstance(spec.env.get(dependency.id), (Spec, list)))
                   for argument in dependencies for dependency in ast.walk(argument)):
                # Use an expression wrapper so this only invalidates mutations,
                # not the separate attribute receiving the helper's return.
                statement = ast.copy_location(ast.Expr(value=item), item)
                self.initializer_unknown([statement], spec)

    def parameter_only_initializer(self, expression: ast.AST, spec: Spec) -> bool:
        """A narrow standard Module contract: initialize tensors, not topology.

        Certify the AST shape and every call. Similar names and arbitrary
        initializer helpers never inherit this contract.
        """
        if not spec.definition or not self.corpus.framework_is_unshadowed():
            return False
        if getattr(spec, "receiver_definition", (spec.unit, spec.definition)) != (spec.unit, spec.definition):
            return False
        if any(spec.unit.resolve(base) != "torch.nn.Module" for base in spec.definition.bases):
            return False
        if not (isinstance(expression, ast.Call) and isinstance(expression.func, ast.Attribute)
                and isinstance(expression.func.value, ast.Name) and expression.func.value.id == "self"
                and not expression.args and not expression.keywords):
            return False
        name = expression.func.attr
        if name in spec.attributes or f"self.{name}" in spec.env:
            return False
        members = [item for item in spec.definition.body if getattr(item, "name", None) == name]
        if len(members) != 1 or not isinstance(members[0], ast.FunctionDef) or members[0].decorator_list:
            return False
        method = members[0]
        body = [item for item in method.body if not (isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str))]
        if len(body) != 1 or not isinstance(body[0], ast.For):
            return False
        loop = body[0]
        if not isinstance(loop.target, ast.Name) or loop.orelse:
            return False
        iterator = loop.iter
        if not (isinstance(iterator, ast.Call) and isinstance(iterator.func, ast.Attribute) and iterator.func.attr == "parameters"
                and isinstance(iterator.func.value, ast.Name) and iterator.func.value.id == "self"
                and not iterator.args and not iterator.keywords):
            return False
        if any(getattr(item, "name", None) == "parameters" for item in spec.definition.body) or "parameters" in spec.attributes:
            return False
        parameter = loop.target.id
        initializers = {"zeros_", "ones_", "constant_", "uniform_", "normal_", "xavier_uniform_", "xavier_normal_", "kaiming_uniform_", "kaiming_normal_", "trunc_normal_", "orthogonal_", "sparse_"}
        allowed_nodes = (ast.Expr, ast.Call, ast.Attribute, ast.Name, ast.Load, ast.If, ast.Compare, ast.Constant,
                         ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.Eq, ast.NotEq, ast.keyword, ast.UnaryOp, ast.USub, ast.UAdd)
        for statement in loop.body:
            for item in ast.walk(statement):
                if not isinstance(item, allowed_nodes): return False
                if isinstance(item, ast.Name) and item.id != parameter and item.id not in spec.unit.imports: return False
                if isinstance(item, ast.Call):
                    dim = (isinstance(item.func, ast.Attribute) and isinstance(item.func.value, ast.Name)
                           and item.func.value.id == parameter and item.func.attr == "dim" and not item.args and not item.keywords)
                    qualified = spec.unit.resolve(item.func)
                    init = (qualified.removeprefix("torch.nn.init.") in initializers and qualified.startswith("torch.nn.init.")
                            and item.args and isinstance(item.args[0], ast.Name) and item.args[0].id == parameter
                            and all(literal(arg, spec.env) is not UNKNOWN for arg in item.args[1:])
                            and all(keyword.arg and literal(keyword.value, spec.env) is not UNKNOWN for keyword in item.keywords))
                    if not dim and not init: return False
        return bool(loop.body)

    def registered_state_initializer(self, expression: ast.AST, spec: Spec) -> bool:
        """Exact Module state registration does not replace unrelated children.

        This is a topology contract, not permission to run a buffer-producing
        helper. User overrides and module-valued arguments remain uncertain.
        """
        if (not spec.definition or not self.corpus.framework_is_unshadowed()
                or not isinstance(expression, ast.Call) or not isinstance(expression.func, ast.Attribute)
                or not isinstance(expression.func.value, ast.Name) or expression.func.value.id != "self"
                or expression.func.attr not in ("register_buffer", "register_parameter")
                or expression.func.attr in spec.attributes):
            return False
        method_name = expression.func.attr
        visited = set()
        def unshadowed(unit, cls):
            key = unit.module, cls.name
            if key in visited:
                return False
            visited.add(key)
            if len(cls.bases) != 1 or any(getattr(item, "name", None) == method_name for item in cls.body):
                return False
            for base in cls.bases:
                qualified = unit.resolve(base)
                if qualified == "torch.nn.Module":
                    return True
                definition = self.corpus.definition(qualified)
                if definition and unshadowed(*definition):
                    return True
            return False
        receiver_unit, receiver_cls = getattr(spec, "receiver_definition", (spec.unit, spec.definition))
        if not unshadowed(receiver_unit, receiver_cls) or any(item.arg is None for item in expression.keywords):
            return False
        allowed = {"name", "tensor", "persistent"} if method_name == "register_buffer" else {"name", "param"}
        if len(expression.args) > (3 if method_name == "register_buffer" else 2) or any(item.arg not in allowed for item in expression.keywords):
            return False
        values = dict(zip(["name", "tensor" if method_name == "register_buffer" else "param", "persistent"], expression.args))
        if any(item.arg in values for item in expression.keywords):
            return False
        values.update({item.arg: item.value for item in expression.keywords})
        name = literal(values.get("name"), spec.env)
        if type(name) is not str or not name or "." in name or name in spec.attributes:
            return False
        value = values.get("tensor" if method_name == "register_buffer" else "param")
        if value is None:
            return False
        # An arbitrary helper may mutate a child passed into it, even when its
        # return is registered as state. Do not grant it this narrow contract.
        for part in ast.walk(value):
            if isinstance(part, ast.Name) and part.id == "self":
                return False
            if isinstance(part, ast.Name) and isinstance(spec.env.get(part.id), (Spec, list)):
                return False
            if isinstance(part, ast.Attribute) and isinstance(part.value, ast.Name) and part.value.id == "self" and isinstance(spec.attributes.get(part.attr), (Spec, list)):
                return False
        spec.env.pop(f"self.{name}", None)
        return True

    def initializer_statements(self, statements: list[ast.stmt], spec: Spec, depth: int) -> bool:
        """Recover direct construction and constant branches, never unknown paths."""
        for index, statement in enumerate(statements):
            if isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None:
                self.initializer_expression_mutations(statement.value, spec)
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                constructed = False
                constructed_value = None
                for target in targets:
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                        if not constructed:
                            constructed_value = self.construct(statement.value, spec.unit, spec.env, spec.attributes,
                                                               f"{spec.identity}.{target.attr}", depth + 1)
                            constructed = True
                        built = constructed_value
                        # A new assignment always replaces the previous fact.
                        if built is not spec.attributes.get(target.attr):
                            self.retire_captured_binding(spec, target.attr)
                        spec.attributes.pop(target.attr, None)
                        spec.env.pop(f"self.{target.attr}", None)
                        if built is not None:
                            spec.attributes[target.attr] = built
                        else:
                            value = literal(statement.value, spec.env)
                            if value is UNKNOWN:
                                spec.attributes[target.attr] = Spec(f"{spec.identity}.{target.attr}", target.attr,
                                                                    "opaque", {}, spec.unit, statement.value)
                                spec.env.pop(f"self.{target.attr}", None)
                            else:
                                spec.env[f"self.{target.attr}"] = value
                            if value is UNKNOWN:
                                self.warn(f"Unresolved initializer assignment at {spec.unit.path}:{statement.lineno}; attribute {target.attr} remains opaque.")
                    elif isinstance(target, ast.Name):
                        built = self.construct(statement.value, spec.unit, spec.env, spec.attributes,
                                               f"{spec.identity}.{target.id}@construction:{statement.lineno}", depth + 1)
                        spec.env[target.id] = built if built is not None else literal(statement.value, spec.env)
                    else:
                        self.initializer_unknown([statement], spec)
            elif isinstance(statement, ast.If):
                predicate = literal(statement.test, spec.env)
                if type(predicate) is bool:
                    if self.initializer_statements(statement.body if predicate else statement.orelse, spec, depth):
                        return True
                else:
                    # An uncertain early return can also skip every later write.
                    may_return = any(isinstance(item, ast.Return) for item in ast.walk(statement))
                    self.initializer_unknown(statements[index:] if may_return else [statement], spec)
                    if may_return:
                        return True
            elif isinstance(statement, ast.Return):
                return True
            elif isinstance(statement, ast.Pass) or isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
                continue
            elif isinstance(statement, ast.Expr) and self.super_initializer(statement.value, spec, depth):
                continue
            elif isinstance(statement, ast.Expr) and (self.registered_state_initializer(statement.value, spec)
                                                      or self.parameter_only_initializer(statement.value, spec)):
                continue
            else:
                self.initializer_unknown([statement], spec)
        return False

    @staticmethod
    def constant_range(expression: ast.AST, env: dict[str, Any], unit: Unit) -> list[int] | None:
        global_shadow = any(
            isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and statement.name == "range"
            or not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and any((isinstance(item, ast.Name) and item.id == "range" and isinstance(item.ctx, (ast.Store, ast.Del)))
                    or (isinstance(item, ast.arg) and item.arg == "range")
                    for item in ast.walk(statement))
            for statement in unit.tree.body)
        if (isinstance(expression, ast.Call) and isinstance(expression.func, ast.Name)
                and expression.func.id == "range" and "range" not in env
                and unit.resolve(expression.func, env) == "range" and not global_shadow and not expression.keywords):
            arguments = [literal(arg, env) for arg in expression.args]
            if 1 <= len(arguments) <= 3 and all(type(arg) is int and abs(arg) <= 1000 for arg in arguments):
                try:
                    result = list(range(*arguments))
                    return result if len(result) <= MAX_REPEAT else None
                except ValueError:
                    pass
        return None

    def invoke(self, spec: Spec, args: list[Any], keywords: dict[str, Any], parent: str | None, call_unit: Unit, call_source: ast.AST, label: str | None = None) -> Any:
        source_name = spec.identity.rsplit(".", 1)[-1].split("@construction:", 1)[0]
        display_name = f"{spec.kind} {int(source_name) + 1}" if source_name.isdigit() else source_name.replace("_", " ")
        own = self.node(f"call:{spec.identity}", label or display_name, spec.kind if spec.category != "container" else "Module", spec.category, parent, call_unit, call_source, evidence="opaque" if spec.category == "opaque" else "source" if spec.definition or spec.items else "contract", parameters=spec.parameters, instance=spec.identity)
        if spec.parameter_origins:
            own["parameterOrigins"] = spec.parameter_origins
        if spec.category == "opaque":
            for index, arg in enumerate(args):
                self.bind(arg, own, f"arg{index}")
            for name, value in keywords.items():
                self.bind(value, own, name)
            return self.out(own)
        if spec.kind == "ModuleList":
            own["category"], own["evidence"] = "opaque", "opaque"
            self.warn(f"ModuleList has no forward contract at {call_unit.path}:{getattr(call_source, 'lineno', 1)}; direct invocation remains opaque, not Sequential.")
            for index, arg in enumerate(args):
                self.bind(arg, own, f"arg{index}")
            for name, value in keywords.items():
                self.bind(value, own, name)
            return self.out(own)
        if spec.kind == "Sequential":
            if not spec.items:
                value = args[0] if args else None
                self.bind(value, own, "input")
                return value
            own["repeat"] = {"count": len(spec.items), "sharing": "shared" if len({item.identity for item in spec.items}) < len(spec.items) else "independent"}
            value = args[0] if args else None
            self.bind(value, own, "input")
            for item in spec.items:
                value = self.invoke(item, [value], {}, own["id"], call_unit, call_source)
            self.bind(value, own, "result")
            return value
        if spec.definition:
            if self.depth >= 12:
                own["category"], own["evidence"] = "opaque", "opaque"
                self.warn("Custom forward recursion budget reached; retained opaque.")
                for index, value in enumerate(args):
                    self.bind(value, own, f"arg{index}")
                for name, value in keywords.items():
                    self.bind(value, own, name)
                return self.out(own)
            method = self.corpus.entry_method(spec.unit, spec.definition)
            if not method:
                own["category"], own["evidence"] = "opaque", "opaque"
                self.warn(f"No safe local forward/__call__ method found for {spec.kind}; invocation remains opaque.")
                for index, value in enumerate(args):
                    self.bind(value, own, f"arg{index}")
                for name, value in keywords.items():
                    self.bind(value, own, name)
                return self.out(own)
            method_unit, forward = method
            names = [item.arg for item in [*forward.args.posonlyargs, *forward.args.args][1:]] + [item.arg for item in forward.args.kwonlyargs]
            method_env = self.method_environment(spec, method_unit)
            bound = self.bind_static(forward, args, keywords, method_env, method=True)
            if bound is None:
                own["category"], own["evidence"] = "opaque", "opaque"
                self.warn(f"Call signature for {spec.kind}.{forward.name} cannot be bound statically; invocation remains opaque.")
                for index, value in enumerate(args): self.bind(value, own, f"arg{index}")
                for name, value in keywords.items(): self.bind(value, own, name)
                return self.out(own)
            values: dict[str, Any] = {}
            for name in names:
                value = bound.get(name)
                self.bind(value, own, name, "mask" if "mask" in name else "memory" if name == "memory" else "data")
                values[name] = value
            self.depth += 1
            method_spec = copy.copy(spec)
            method_spec.unit = method_unit
            method_spec.env = method_env
            result, returned = self.statements(forward.body, method_spec, values, own["id"])
            self.depth -= 1
            if not returned:
                own["category"], own["evidence"] = "opaque", "opaque"
                self.warn(f"Forward {spec.kind} contains no recoverable return; output remains opaque.")
                return self.out(own)
            return result
        if spec.kind == "MultiheadAttention":
            names = ["query", "key", "value", "key_padding_mask", "need_weights", "attn_mask", "average_attn_weights", "is_causal"]
            bindings = dict(zip(names, args)) | keywords
            query_tensors = {ref.tensor for ref in refs(bindings.get("query"))}
            for name, value in bindings.items():
                same_as_query = bool(query_tensors and query_tensors.intersection({ref.tensor for ref in refs(value)}))
                role = "mask" if name in ("attn_mask", "key_padding_mask") else "memory" if name in ("key", "value") and not same_as_query else "data"
                self.bind(value, own, name, role)
            output, weights = self.out(own, "output"), self.out(own, "weights")
            # The API still has a second output slot, but need_weights=False
            # makes it None; do not fabricate a tensor flowing from that slot.
            return output, None if bindings.get("need_weights") is False else weights
        for index, arg in enumerate(args):
            self.bind(arg, own, "input" if index == 0 else f"arg{index}")
        for name, value in keywords.items():
            self.bind(value, own, name)
        if spec.kind == "LSTM":
            return self.out(own, "output"), (self.out(own, "h_n"), self.out(own, "c_n"))
        if spec.kind in ('RNN', 'GRU'):
            return self.out(own, 'output'), self.out(own, 'h_n')
        return self.out(own)

    def residual_operand(self, inputs: list[tuple[str, Any]]) -> str | None:
        """Prove a bypass from recovered tensor dependencies, never operand order.

        An opaque endpoint or intermediate cannot establish this role. Tensor
        identity matters: separate outputs of one producer are not ancestors of
        one another merely because their node identity is the same.
        """
        operands = dict(inputs)
        left, right = operands.get("left"), operands.get("right")
        if (len(inputs) != 2 or set(operands) != {"left", "right"}
                or not isinstance(left, Ref) or not isinstance(right, Ref)
                or left.tensor == right.tensor or left.node == right.node):
            return None
        nodes = {node["id"]: node for node in self.nodes}
        known = {identity for identity, node in nodes.items()
                 if node["category"] != "opaque" and node["evidence"] in ("source", "contract")}
        if left.node not in known or right.node not in known:
            return None
        incoming: dict[str, list[dict[str, Any]]] = {}
        for edge in self.edges:
            incoming.setdefault(edge["target"]["nodeId"], []).append(edge)

        def depends_on(descendant: Ref, ancestor: Ref) -> bool:
            pending, seen = [descendant.node], set()
            while pending:
                identity = pending.pop()
                if identity in seen or identity not in known:
                    continue
                seen.add(identity)
                for edge in incoming.get(identity, []):
                    producer = edge["source"]["nodeId"]
                    if producer not in known:
                        continue
                    if (producer == ancestor.node and edge["source"]["portId"] == ancestor.port
                            and edge["tensorId"] == ancestor.tensor):
                        return True
                    pending.append(producer)
            return False

        left_is_bypass, right_is_bypass = depends_on(right, left), depends_on(left, right)
        if left_is_bypass != right_is_bypass:
            return "left" if left_is_bypass else "right"
        return None

    def operator(self, source: ast.AST, spec: Spec, parent: str, kind: str, inputs: list[tuple[str, Any]], category: str = "operator", evidence: str = "source", outputs: list[str] | None = None, parameters: dict | None = None) -> Any:
        # The source structure and operation occurrence, rather than line number,
        # identify a call. Inserting comments therefore preserves diagram IDs.
        fingerprint = digest(ast.dump(source, include_attributes=False))[:10]
        residual_operand = self.residual_operand(inputs) if kind == "Add" else None
        if kind == "Add":
            category = "residual" if residual_operand else "operator"
        node = self.node(f"op:{parent}:{kind}:{fingerprint}", kind, kind, category, parent, spec.unit, source, evidence=evidence)
        if parameters is not None:
            node["parameters"] = parameters
        for name, value in inputs:
            self.bind(value, node, name, "residual" if name == residual_operand else "data")
        if outputs:
            return tuple(self.out(node, name) for name in outputs)
        return self.out(node)

    def expression(self, expression: ast.AST, spec: Spec, values: dict[str, Any], parent: str) -> Any:
        if isinstance(expression, ast.Name):
            if expression.id == "self":
                return spec
            return values.get(expression.id, spec.env.get(expression.id))
        if isinstance(expression, ast.Constant):
            return expression.value
        if isinstance(expression, (ast.Tuple, ast.List)):
            return tuple(self.expression(item, spec, values, parent) for item in expression.elts)
        if isinstance(expression, ast.Dict):
            entries = [(literal(key, spec.env | values) if key is not None else UNKNOWN,
                        self.expression(value, spec, values, parent))
                       for key, value in zip(expression.keys, expression.values)]
            def portable_key(key):
                return (key is None or type(key) in (str, bool)
                        or type(key) is int and abs(key) <= 2**53 - 1
                        or type(key) is float and math.isfinite(key) and abs(key) <= 2**53 - 1)
            if any(not portable_key(key) for key, _ in entries):
                self.warn(f"Unknown or nonportable dictionary key/unpack at {spec.unit.path}:{expression.lineno}; complete dictionary retained opaque with no claimed key slots.")
                dependencies = [(f"value{index}", value) for index, (_, value) in enumerate(entries)]
                for index, key in enumerate(expression.keys):
                    if key is not None:
                        involved = sorted({item.id for item in ast.walk(key) if isinstance(item, ast.Name) and item.id in values})
                        dependencies.extend((f"key{index}.{name}", values[name]) for name in involved)
                return self.operator(expression, spec, parent, "OpaqueDictionary", dependencies, "opaque", evidence="opaque")
            return dict(entries)
        if isinstance(expression, ast.Attribute):
            if isinstance(expression.value, ast.Name) and expression.value.id == "self":
                return spec.attributes.get(expression.attr, spec.env.get(f"self.{expression.attr}"))
            return None
        if isinstance(expression, ast.Subscript):
            value = self.expression(expression.value, spec, values, parent)
            index = literal(expression.slice, spec.env)
            if isinstance(value, Spec) and value.items:
                value = value.items
            if isinstance(value, (tuple, list, dict)) and index is not UNKNOWN:
                try:
                    return value[index]
                except (IndexError, KeyError, TypeError):
                    pass
            return self.operator(expression, spec, parent, "Select", [("input", value)])
        if isinstance(expression, ast.BinOp):
            left = self.expression(expression.left, spec, values, parent)
            right = self.expression(expression.right, spec, values, parent)
            kind = {ast.Add: "Add", ast.Sub: "Subtract", ast.Mult: "Multiply", ast.MatMult: "MatMul", ast.Div: "Divide"}.get(type(expression.op), "OpaqueExpression")
            return self.operator(expression, spec, parent, kind, [("left", left), ("right", right)], "residual" if kind == "Add" else "operator", evidence="opaque" if kind == "OpaqueExpression" else "source")
        if isinstance(expression, ast.Call):
            target = self.expression(expression.func, spec, values, parent)
            args = [self.expression(arg, spec, values, parent) for arg in expression.args]
            keywords = {keyword.arg: self.expression(keyword.value, spec, values, parent) for keyword in expression.keywords if keyword.arg}
            if isinstance(target, Spec):
                return self.invoke(target, args, keywords, parent, spec.unit, expression)
            if (spec.definition and isinstance(expression.func, ast.Attribute) and isinstance(expression.func.value, ast.Name)
                    and expression.func.value.id == "self" and expression.func.attr not in spec.attributes and f"self.{expression.func.attr}" not in spec.env):
                members = [item for item in spec.definition.body if getattr(item, "name", None) == expression.func.attr
                           or isinstance(item, (ast.Assign, ast.AnnAssign)) and any(isinstance(part, ast.Name) and part.id == expression.func.attr and isinstance(part.ctx, ast.Store) for part in ast.walk(item))]
                method = members[0] if len(members) == 1 else None
                if (isinstance(method, ast.FunctionDef) and not method.decorator_list and self.depth < 12
                        and not any(isinstance(item, ast.Starred) for item in expression.args)
                        and not any(item.arg is None for item in expression.keywords)
                        and not any(isinstance(item, ast.Attribute) and isinstance(item.ctx, (ast.Store, ast.Del)) for item in ast.walk(method))):
                    helper_unit = next((unit for unit in self.corpus.units.values()
                                        if any(method is part for part in ast.walk(unit.tree))), spec.unit)
                    helper_spec = copy.copy(spec)
                    helper_spec.unit = helper_unit
                    helper_spec.env = self.method_environment(spec, helper_unit)
                    bound = self.bind_static(method, args, keywords, helper_spec.env, method=True)
                    if bound is not None:
                        self.depth += 1
                        try:
                            result, returned = self.statements(method.body, helper_spec, bound, parent)
                        finally:
                            self.depth -= 1
                        if returned:
                            return result

            qualified = spec.unit.resolve(expression.func, spec.env | values)
            functional = {
                "torch.nn.functional.relu": "ReLU", "torch.nn.functional.gelu": "GELU", "torch.nn.functional.dropout": "Dropout",
                "torch.flatten": "Flatten", "torch.cat": "Concat", "torch.matmul": "MatMul", "torch.softmax": "Softmax",
            }
            if qualified in functional and self.corpus.framework_is_unshadowed():
                return self.operator(expression, spec, parent, functional[qualified], [(f"arg{index}", value) for index, value in enumerate(args)] + list(keywords.items()), "activation" if functional[qualified] in ("ReLU", "GELU", "Softmax") else "operator", evidence="contract")
            if isinstance(expression.func, ast.Attribute):
                receiver = self.expression(expression.func.value, spec, values, parent)
                method = expression.func.attr
                if refs(receiver) and method in ("transpose", "permute", "reshape", "view", "flatten", "mean", "sum", "contiguous", "chunk", "split", "unsqueeze", "squeeze"):
                    if method in ("chunk", "split"):
                        self.warn(f"{method.capitalize()} output arity depends on tensor shape at {spec.unit.path}:{expression.lineno}; no shape contract proves its output slots, so the result remains opaque.")
                        return self.operator(expression, spec, parent, method.capitalize(),
                                             [("input", receiver)] + [(f"arg{index}", value) for index, value in enumerate(args)] + list(keywords.items()),
                                             "opaque", evidence="opaque")
                    # Tensor method arguments are model facts, not palette
                    # defaults. Retain their static literal axes/shapes so an
                    # expanded editor can recreate the authored calculation.
                    positional = [literal(arg, spec.env | values) for arg in expression.args]
                    named = {keyword.arg: literal(keyword.value, spec.env | values) for keyword in expression.keywords if keyword.arg}
                    parameters = {}
                    signatures = {"flatten": (["start_dim", "end_dim"], {"start_dim": 0, "end_dim": -1}),
                                  "transpose": (["dim0", "dim1"], {}),
                                  "mean": (["dim", "keepdim"], {"keepdim": False}),
                                  "sum": (["dim", "keepdim"], {"keepdim": False}),
                                  "unsqueeze": (["dim"], {}), "squeeze": (["dim"], {})}
                    if method in signatures:
                        fields, defaults = signatures[method]
                        parameters = {**defaults, **dict(zip(fields, positional)), **named}
                    elif method in ("reshape", "view", "permute"):
                        shape = positional[0] if len(positional) == 1 and isinstance(positional[0], (list, tuple)) else positional
                        parameters = {"dims" if method == "permute" else "shape": list(shape)}
                    def literal_parameter(value):
                        return type(value) in (int, float, bool, str) or isinstance(value, (list, tuple)) and all(literal_parameter(item) for item in value)
                    parameters = {key: list(value) if isinstance(value, tuple) else value for key, value in parameters.items() if literal_parameter(value)}
                    return self.operator(expression, spec, parent, "Reshape" if method == "view" else method.capitalize(), [("input", receiver)], evidence="contract", parameters=parameters)
                if refs(receiver):
                    args.insert(0, receiver)
            self.warn(f"Unsupported call {spec.unit.expression(expression.func)} at {spec.unit.path}:{expression.lineno}; retained opaque.")
            return self.operator(expression, spec, parent, spec.unit.expression(expression.func), [(f"arg{index}", value) for index, value in enumerate(args)] + list(keywords.items()), "opaque", evidence="opaque")
        if isinstance(expression, ast.UnaryOp):
            return self.operator(expression, spec, parent, "Unary", [("input", self.expression(expression.operand, spec, values, parent))])
        self.warn(f"Unsupported expression {type(expression).__name__} at {spec.unit.path}:{getattr(expression, 'lineno', 1)}; retained opaque.")
        dependencies = [(name, values[name]) for name in sorted({item.id for item in ast.walk(expression) if isinstance(item, ast.Name) and item.id in values})]
        return self.operator(expression, spec, parent, "OpaqueExpression", dependencies, "opaque", evidence="opaque")

    def assign(self, target: ast.AST, value: Any, values: dict[str, Any], spec: Spec, parent: str):
        if isinstance(target, ast.Name):
            values[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            if not isinstance(value, (tuple, list)):
                self.warn(f"Unknown tuple arity at {spec.unit.path}:{target.lineno}; selections retained opaque.")
                value = [self.operator(target, spec, parent, f"OpaqueSlot{index}", [("input", value)], "opaque", evidence="opaque") for index in range(len(target.elts))]
            for child, item in zip(target.elts, value):
                self.assign(child, item, values, spec, parent)
        else:
            self.warn(f"State or subscript assignment at {spec.unit.path}:{target.lineno} is not supported; no writeback is available.")

    def statements(self, statements: list[ast.stmt], spec: Spec, values: dict[str, Any], parent: str) -> tuple[Any, bool]:
        for statement in statements:
            if isinstance(statement, ast.Assign):
                value = self.expression(statement.value, spec, values, parent)
                for target in statement.targets:
                    self.assign(target, value, values, spec, parent)
            elif isinstance(statement, ast.AnnAssign) and statement.value:
                self.assign(statement.target, self.expression(statement.value, spec, values, parent), values, spec, parent)
            elif isinstance(statement, ast.AugAssign) and isinstance(statement.target, ast.Name):
                value = self.operator(statement, spec, parent, "Add" if isinstance(statement.op, ast.Add) else "OpaqueUpdate", [("left", values.get(statement.target.id)), ("right", self.expression(statement.value, spec, values, parent))], "residual" if isinstance(statement.op, ast.Add) else "opaque")
                values[statement.target.id] = value
            elif isinstance(statement, ast.Return):
                return self.expression(statement.value, spec, values, parent) if statement.value else None, True
            elif isinstance(statement, ast.For) and isinstance(statement.target, ast.Name):
                iterable = self.expression(statement.iter, spec, values, parent) if not isinstance(statement.iter, ast.Call) else self.constant_range(statement.iter, spec.env | values, spec.unit)
                if any(isinstance(item, (ast.Break, ast.Continue)) for item in ast.walk(statement)):
                    iterable = None
                if isinstance(iterable, Spec) and iterable.items:
                    items = iterable.items
                    region = self.node(f"repeat:{iterable.identity}", iterable.identity.rsplit(".", 1)[-1], "Repeat", "container", parent, spec.unit, statement)
                    region["repeat"] = {"count": len(items), "sharing": "shared" if len({item.identity for item in items}) < len(items) else "independent"}
                    loop_parent = region["id"]
                elif isinstance(iterable, (tuple, list)) and len(iterable) <= MAX_REPEAT:
                    items, loop_parent = iterable, parent
                else:
                    output = self.opaque_statement(statement, spec, values, parent, "DynamicLoop")
                    if any(isinstance(item, ast.Return) for item in ast.walk(statement)):
                        return output, True
                    continue
                for item in items:
                    values[statement.target.id] = item
                    result, returned = self.statements(statement.body, spec, values, loop_parent)
                    if returned:
                        return result, True
                result, returned = self.statements(statement.orelse, spec, values, parent)
                if returned:
                    return result, True
            elif isinstance(statement, ast.If):
                predicate = literal(statement.test, spec.env | values)
                if isinstance(predicate, bool):
                    result, returned = self.statements(statement.body if predicate else statement.orelse, spec, values, parent)
                    if returned:
                        return result, True
                else:
                    self.opaque_statement(statement, spec, values, parent, "ConditionalRegion")
                    # A conditional return must not disappear into a later graph.
                    if any(isinstance(item, ast.Return) for item in ast.walk(statement)):
                        boundary = next(node for node in reversed(self.nodes) if node["parentId"] == parent)
                        output = self.out(boundary)
                        return Ref(output.node, output.port, output.tensor, '$return'), True
            elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
                continue  # A docstring is data, not a model operation.
            elif isinstance(statement, ast.Expr):
                self.expression(statement.value, spec, values, parent)
            else:
                self.opaque_statement(statement, spec, values, parent, type(statement).__name__)
        return None, False

    def opaque_statement(self, statement: ast.stmt, spec: Spec, values: dict[str, Any], parent: str, kind: str):
        self.warn(f"Unsupported control/state region {kind} at {spec.unit.path}:{statement.lineno}; affected values are opaque.")
        involved = sorted({item.id for item in ast.walk(statement) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load) and item.id in values})
        output = self.operator(statement, spec, parent, kind, [(name, values[name]) for name in involved], "opaque", evidence="opaque")
        if isinstance(statement, ast.If):
            region = next(node for node in self.nodes if node["id"] == output.node)
            self.source_regions.append((region, statement, spec, {name: values[name] for name in involved}))
        assigned = {item.id for item in ast.walk(statement) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)}
        for name in assigned:
            values[name] = Ref(output.node, output.port, output.tensor, name) if isinstance(statement, ast.If) else output
        return output

    def analyze(self, module: str, name: str) -> dict[str, Any]:
        unit = self.corpus.load(module)
        definition = self.corpus.definition(f"{module}.{name}")
        if not unit or not definition:
            raise AnalysisError(f"Entry {module}:{name} is not a local class in the selected source corpus.")
        if not self.is_module(*definition):
            raise AnalysisError(f"Entry {module}:{name} is not statically proven to derive from torch.nn.Module.")
        own_unit, cls = definition
        entry_expression = ast.Call(func=ast.Name(id=name), args=[], keywords=[])
        ast.copy_location(entry_expression, cls)
        spec = self.construct(entry_expression, own_unit, {}, {}, f"instance:{module}.{name}")
        if not isinstance(spec, Spec):
            raise AnalysisError("Entry construction is outside the supported static subset.")
        method = self.corpus.entry_method(own_unit, cls)
        if not method:
            raise AnalysisError("Entry needs a safe local forward or __call__ method (possibly inherited).")
        method_unit, forward = method
        # Root node is inserted by invoke; inputs are its children and can feed
        # deeply expanded calls while keeping one canonical tensor identity.
        root_id = f"call:{spec.identity}"
        positional_names = [item.arg for item in [*forward.args.posonlyargs, *forward.args.args][1:]]
        names = positional_names + [item.arg for item in forward.args.kwonlyargs]
        input_nodes = []
        args = []
        keywords = {}
        for arg in names:
            node = self.node(f"input:{module}.{name}:{arg}", arg, "Input", "input", None, method_unit, forward)
            input_nodes.append(node)
            if arg in positional_names: args.append(self.out(node, arg))
            else: keywords[arg] = self.out(node, arg)
        outputs = self.invoke(spec, args, keywords, None, own_unit, cls, name)
        root = next(node for node in self.nodes if node["id"] == root_id)
        for node in input_nodes:
            node["parentId"] = root_id
            root["children"].insert(0, node["id"])
        bindings = output_bindings(outputs)
        for index, (value, path) in enumerate(bindings):
            node = self.node(f"output:{module}.{name}:{index}", "output" if len(bindings) == 1 else f"output {index + 1}", "Output", "output", root_id, method_unit, forward)
            node["outputPath"] = path
            self.bind(value, node, "value")
        # Expose available branch syntax and local definitions independently
        # of the conservative tensor graph. No branch/config is selected.
        source_relations = SourceStructure(self, MAX_NODES).populate(self.source_regions)
        validate_output_paths(self.nodes)
        source_files = [{"path": unit.path, "content": unit.content, "digest": unit.raw_digest} for unit in sorted(self.corpus.units.values(), key=lambda value: value.path)]
        source_digest = digest([{key: value for key, value in source.items() if key != "content"} for source in source_files])
        semantic_nodes = []
        for node in self.nodes:
            item = {key: value for key, value in node.items() if key not in ("source", "parameterOrigins")}
            if "parameterOrigins" in node:
                item["parameterOrigins"] = {name: {"kind": origin["kind"], "expression": origin["expression"], "path": origin["path"]} for name, origin in node["parameterOrigins"].items()}
            semantic_nodes.append(item)
        semantic = {"entry": f"{module}:{name}", "nodes": semantic_nodes, "edges": self.edges}
        if source_relations:
            semantic['sourceRelations'] = [{k:v for k,v in relation.items() if k != 'source'} for relation in source_relations]
        self.diagnostics.insert(0, {"level": "info", "message": "Static AST subset only. User code was not imported or executed; no inferred shapes or runtime verification. Source editing uses separately reviewed registered transactions."})
        return {"schemaVersion": 1, "id": f"architecture:{module}.{name}", "label": name, "sourceDigest": source_digest, "irDigest": digest(semantic), "entry": f"{module}:{name}", "nodes": self.nodes, "edges": self.edges, "diagnostics": self.diagnostics, "sources": source_files,
                **({'sourceRelations':source_relations} if source_relations else {})}


def load_project_corpus(root: str | Path) -> Corpus:
    """Parse and retain the complete bounded selected project as source data."""
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise AnalysisError("Project root is not a directory.")
    corpus = Corpus(root_path)
    try:
        files = read_directory_files(root_path, max_files=MAX_FILES, max_bytes=MAX_BYTES)
    except DiscoveryError as exc:
        raise AnalysisError(str(exc)) from exc
    # A source-preserving copy includes the complete selected Python corpus,
    # including helpers imported inside methods or branches. Preloading parses
    # source as data; it does not execute imports or enlarge the tensor subset.
    for logical in sorted(files):
        parts = Path(logical).with_suffix("").parts
        own_module = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        if not own_module:
            own_module = "__init__"
        if own_module in corpus.units:
            raise AnalysisError(f"Selected source files have an ambiguous Python module identity: {own_module}.")
        raw = (root_path / logical).read_bytes()
        corpus.add(own_module, logical, raw.decode("utf-8-sig"), raw)
    return corpus


def analyze_project(root: str | Path, entry: str) -> dict[str, Any]:
    module, separator, name = entry.partition(":")
    if not separator or not name.isidentifier() or any(not part.isidentifier() for part in module.split(".")):
        raise AnalysisError("Entry must have the form module:ModelClass.")
    return Analyzer(load_project_corpus(root)).analyze(module, name)


def analyze_source(source: str, entry: str, filename: str = "model.py", *, raw_bytes: bytes | None = None) -> dict[str, Any]:
    if not isinstance(source, str) or len(source.encode()) > MAX_BYTES:
        raise AnalysisError("Source must be UTF-8 text within the 2 MB analysis budget.")
    if raw_bytes is not None and (not isinstance(raw_bytes, bytes) or raw_bytes.decode("utf-8-sig") != source):
        raise AnalysisError("Explicit raw source bytes must decode to the supplied UTF-8 source text.")
    filename_path = Path(filename)
    if filename_path.is_absolute() or ".." in filename_path.parts or filename_path.suffix != ".py":
        raise AnalysisError("Filename must be a relative Python logical path without traversal.")
    module = filename_path.with_suffix("").as_posix().replace("/", ".")
    if any(not part.isidentifier() for part in module.split(".")):
        raise AnalysisError("Filename must correspond to a valid Python module.")
    if ":" in entry:
        entry_module, name = entry.split(":", 1)
        if entry_module != module:
            raise AnalysisError("Source entry module must match its logical filename.")
    else:
        name = entry
    if not name.isidentifier():
        raise AnalysisError("Source entry must name a ModelClass.")
    corpus = Corpus()
    corpus.add(module, filename_path.as_posix(), source, raw_bytes)
    return Analyzer(corpus).analyze(module, name)
