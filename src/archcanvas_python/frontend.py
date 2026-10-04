"""Bounded static analysis of an explicit PyTorch Module source subset.

User source is parsed as data. No import, decorator, initializer, model forward,
eval, or exec runs. Unknown Python remains an opaque source-backed boundary.
"""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


@dataclass
class Unit:
    module: str
    path: str
    content: str
    tree: ast.Module
    imports: dict[str, str] = field(default_factory=dict)
    classes: dict[str, ast.ClassDef] = field(default_factory=dict)
    constants: dict[str, Any] = field(default_factory=dict)
    raw_digest: str | None = None

    def expression(self, node: ast.AST) -> str:
        return ast.get_source_segment(self.content, node) or ast.unparse(node)

    def resolve(self, node: ast.AST, locals: dict[str, Any] | None = None) -> str:
        if isinstance(node, ast.Name):
            if locals and node.id in locals:
                return ""
            if node.id in self.imports:
                return self.imports[node.id]
            return f"{self.module}.{node.id}" if node.id in self.classes else node.id
        if isinstance(node, ast.Attribute):
            base = self.resolve(node.value, locals)
            return f"{base}.{node.attr}" if base else ""
        return ""


class Corpus:
    def __init__(self, root: Path | None = None):
        self.root = root.resolve() if root else None
        self.units: dict[str, Unit] = {}
        self.total_bytes = 0

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
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        unit.imports.pop(target.id, None)
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

    def framework_is_unshadowed(self) -> bool:
        """A local module named torch cannot prove an external PyTorch contract."""
        return not any(name == "torch" or name.startswith("torch.") for name in self.units)


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


def refs(value: Any) -> list[Ref]:
    if isinstance(value, Ref):
        return [value]
    if isinstance(value, (tuple, list)):
        return [ref for item in value for ref in refs(item)]
    if isinstance(value, dict):
        return [ref for item in value.values() for ref in refs(item)]
    return []


class Analyzer:
    def __init__(self, corpus: Corpus):
        self.corpus = corpus
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self.diagnostics: list[dict[str, str]] = []
        self.counters: dict[str, int] = {}
        self.depth = 0

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

    def is_module(self, unit: Unit, definition: ast.ClassDef, seen: set[str] | None = None) -> bool:
        seen = seen or set()
        key = f"{unit.module}.{definition.name}"
        if key in seen:
            return False
        seen.add(key)
        for base in definition.bases:
            qualified = unit.resolve(base)
            if qualified == "torch.nn.Module" and self.corpus.framework_is_unshadowed():
                return True
            inherited = self.corpus.definition(qualified)
            if inherited and self.is_module(*inherited, seen):
                return True
        return False

    def construct(self, expression: ast.AST, unit: Unit, env: dict[str, Any], attributes: dict[str, Any], identity: str, depth: int = 0) -> Any:
        if depth > 12:
            return None
        if isinstance(expression, ast.Attribute) and isinstance(expression.value, ast.Name) and expression.value.id == "self":
            return attributes.get(expression.attr)
        if isinstance(expression, ast.List):
            return [self.construct(item, unit, env, attributes, f"{identity}.{index}", depth + 1) for index, item in enumerate(expression.elts)]
        if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Mult):
            values = self.construct(expression.left, unit, env, attributes, identity, depth + 1)
            count = literal(expression.right, env)
            if isinstance(values, list) and type(count) is int and 0 <= count <= MAX_REPEAT:
                return values * count
        if isinstance(expression, ast.ListComp) and len(expression.generators) == 1:
            generator = expression.generators[0]
            if isinstance(generator.target, ast.Name) and not generator.ifs:
                values = self.constant_range(generator.iter, env)
                if values is not None:
                    return [self.construct(expression.elt, unit, {**env, generator.target.id: index}, attributes, f"{identity}.{index}", depth + 1) for index in values]
        if not isinstance(expression, ast.Call):
            return None
        qualified = unit.resolve(expression.func, env)
        short = qualified.rsplit(".", 1)[-1]
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
            initializer = next((item for item in cls.body if isinstance(item, ast.FunctionDef) and item.name == "__init__"), None)
            local = dict(own_unit.constants)
            if not initializer and any(own_unit.resolve(base) != "torch.nn.Module" for base in cls.bases):
                self.warn(f"Inherited initializer for {cls.name} is outside the initial subset; unresolved attributes remain opaque.")
            if initializer:
                params = initializer.args.args[1:]
                defaults = dict(zip([param.arg for param in params[-len(initializer.args.defaults):]], initializer.args.defaults)) if initializer.args.defaults else {}
                for param in params:
                    local[param.arg] = literal(defaults.get(param.arg), local) if param.arg in defaults else UNKNOWN
                for param, arg in zip(params, expression.args):
                    local[param.arg] = literal(arg, env)
                for keyword in expression.keywords:
                    if keyword.arg:
                        local[keyword.arg] = literal(keyword.value, env)
                unresolved = [param.arg for param in params if local.get(param.arg) is UNKNOWN]
                if unresolved:
                    self.warn(f"Constructor arguments for {cls.name} remain symbolic ({', '.join(unresolved)}); this is not a claim of valid executable instantiation.")
            spec = Spec(identity, cls.name, "container", {key: value for key, value in local.items() if value is not UNKNOWN}, own_unit, expression, cls, local)
            if initializer:
                for statement in initializer.body:
                    if isinstance(statement, ast.Assign):
                        for target in statement.targets:
                            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                                built = self.construct(statement.value, own_unit, local, spec.attributes, f"{identity}.{target.attr}", depth + 1)
                                if built is not None:
                                    spec.attributes[target.attr] = built
                                else:
                                    local[f"self.{target.attr}"] = literal(statement.value, local)
                            elif isinstance(target, ast.Name):
                                local[target.id] = literal(statement.value, local)
            return spec
        params: dict[str, Any] = {}
        origins: dict[str, Any] = {}
        contract = CONTRACTS.get(short) if qualified == f"torch.nn.{short}" and self.corpus.framework_is_unshadowed() else None
        positional = contract[0] if contract else []
        for index, arg in enumerate(expression.args):
            value = literal(arg, env)
            name = positional[index] if index < len(positional) else f"arg{index}"
            params[name] = value if value is not UNKNOWN else {"expression": unit.expression(arg), "origin": "unknown"}
            origins[name] = self.parameter_origin(unit, arg, env)
        for keyword in expression.keywords:
            if keyword.arg:
                value = literal(keyword.value, env)
                params[keyword.arg] = value if value is not UNKNOWN else {"expression": unit.expression(keyword.value), "origin": "unknown"}
                origins[keyword.arg] = self.parameter_origin(unit, keyword.value, env)
        if not contract:
            self.warn(f"Unknown constructor {qualified or unit.expression(expression.func)} at {unit.path}:{expression.lineno}; no type semantics inferred from its name.")
        return Spec(identity, short or "Unknown", contract[1] if contract else "opaque", params, unit, expression, parameter_origins=origins)

    @staticmethod
    def constant_range(expression: ast.AST, env: dict[str, Any]) -> list[int] | None:
        if isinstance(expression, ast.Call) and isinstance(expression.func, ast.Name) and expression.func.id == "range":
            arguments = [literal(arg, env) for arg in expression.args]
            if 1 <= len(arguments) <= 3 and all(type(arg) is int and abs(arg) <= 1000 for arg in arguments):
                try:
                    result = list(range(*arguments))
                    return result if len(result) <= MAX_REPEAT else None
                except ValueError:
                    pass
        return None

    def invoke(self, spec: Spec, args: list[Any], keywords: dict[str, Any], parent: str | None, call_unit: Unit, call_source: ast.AST, label: str | None = None) -> Any:
        source_name = spec.identity.rsplit(".", 1)[-1]
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
        if spec.kind in ("Sequential", "ModuleList") and spec.items:
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
            forward = next((item for item in spec.definition.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "forward"), None)
            if not forward:
                own["category"], own["evidence"] = "opaque", "opaque"
                self.warn(f"No directly authored forward found for {spec.kind}; inherited forward analysis is not yet supported.")
                for index, value in enumerate(args):
                    self.bind(value, own, f"arg{index}")
                for name, value in keywords.items():
                    self.bind(value, own, name)
                return self.out(own)
            names = [item.arg for item in forward.args.args[1:]] + [item.arg for item in forward.args.kwonlyargs]
            bound = dict(zip(names, args)) | keywords
            defaults = dict(zip([item.arg for item in forward.args.args[-len(forward.args.defaults):]], forward.args.defaults)) if forward.args.defaults else {}
            values: dict[str, Any] = {}
            for name in names:
                value = bound.get(name)
                if value is None and name in defaults:
                    value = literal(defaults[name], spec.env)
                self.bind(value, own, name, "mask" if "mask" in name else "memory" if name == "memory" else "data")
                values[name] = value
            self.depth += 1
            result, returned = self.statements(forward.body, spec, values, own["id"])
            self.depth -= 1
            if not returned:
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
        return self.out(own)

    def operator(self, source: ast.AST, spec: Spec, parent: str, kind: str, inputs: list[tuple[str, Any]], category: str = "operator", evidence: str = "source", outputs: list[str] | None = None) -> Any:
        # The source structure and operation occurrence, rather than line number,
        # identify a call. Inserting comments therefore preserves diagram IDs.
        fingerprint = digest(ast.dump(source, include_attributes=False))[:10]
        node = self.node(f"op:{parent}:{kind}:{fingerprint}", kind, kind, category, parent, spec.unit, source, evidence=evidence)
        for name, value in inputs:
            self.bind(value, node, name, "residual" if kind == "Add" and name == "left" else "data")
        if outputs:
            return tuple(self.out(node, name) for name in outputs)
        return self.out(node)

    def expression(self, expression: ast.AST, spec: Spec, values: dict[str, Any], parent: str) -> Any:
        if isinstance(expression, ast.Name):
            return values.get(expression.id, spec.env.get(expression.id))
        if isinstance(expression, ast.Constant):
            return expression.value
        if isinstance(expression, (ast.Tuple, ast.List)):
            return tuple(self.expression(item, spec, values, parent) for item in expression.elts)
        if isinstance(expression, ast.Dict):
            return {key.value: self.expression(value, spec, values, parent) for key, value in zip(expression.keys, expression.values) if isinstance(key, ast.Constant)}
        if isinstance(expression, ast.Attribute):
            if isinstance(expression.value, ast.Name) and expression.value.id == "self":
                return spec.attributes.get(expression.attr, spec.env.get(f"self.{expression.attr}"))
            return None
        if isinstance(expression, ast.Subscript):
            value = self.expression(expression.value, spec, values, parent)
            index = literal(expression.slice, spec.env)
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
                    outputs = None
                    if method == "chunk" and expression.args:
                        count = literal(expression.args[0], spec.env)
                        if type(count) is int and 0 < count <= MAX_REPEAT:
                            outputs = [f"output{index}" for index in range(count)]
                        else:
                            self.warn(f"Unknown chunk count at {spec.unit.path}:{expression.lineno}; output remains opaque.")
                    return self.operator(expression, spec, parent, method.capitalize(), [("input", receiver)], evidence="contract", outputs=outputs)
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
                iterable = self.expression(statement.iter, spec, values, parent) if not isinstance(statement.iter, ast.Call) else self.constant_range(statement.iter, spec.env)
                if isinstance(iterable, Spec) and iterable.items:
                    items = iterable.items
                    region = self.node(f"repeat:{iterable.identity}", iterable.identity.rsplit(".", 1)[-1], "Repeat", "container", parent, spec.unit, statement)
                    region["repeat"] = {"count": len(items), "sharing": "shared" if len({item.identity for item in items}) < len(items) else "independent"}
                    loop_parent = region["id"]
                elif isinstance(iterable, (tuple, list)) and len(iterable) <= MAX_REPEAT:
                    items, loop_parent = iterable, parent
                else:
                    self.opaque_statement(statement, spec, values, parent, "DynamicLoop")
                    continue
                for item in items:
                    values[statement.target.id] = item
                    result, returned = self.statements(statement.body, spec, values, loop_parent)
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
                        return self.out(boundary), True
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
        assigned = {item.id for item in ast.walk(statement) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)}
        for name in assigned:
            values[name] = output

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
        forward = next((statement for statement in cls.body if isinstance(statement, ast.FunctionDef) and statement.name == "forward"), None)
        if not forward:
            raise AnalysisError("Entry needs a directly authored forward method in this initial static subset.")
        # Root node is inserted by invoke; inputs are its children and can feed
        # deeply expanded calls while keeping one canonical tensor identity.
        root_id = f"call:{spec.identity}"
        names = [item.arg for item in forward.args.args[1:]] + [item.arg for item in forward.args.kwonlyargs]
        input_nodes = []
        args = []
        for arg in names:
            node = self.node(f"input:{module}.{name}:{arg}", arg, "Input", "input", None, own_unit, forward)
            input_nodes.append(node)
            args.append(self.out(node, arg))
        outputs = self.invoke(spec, args, {}, None, own_unit, cls, name)
        root = next(node for node in self.nodes if node["id"] == root_id)
        for node in input_nodes:
            node["parentId"] = root_id
            root["children"].insert(0, node["id"])
        for index, value in enumerate(refs(outputs)):
            node = self.node(f"output:{module}.{name}:{index}", "output" if len(refs(outputs)) == 1 else f"output {index + 1}", "Output", "output", root_id, own_unit, forward)
            self.bind(value, node, "value")
        source_files = [{"path": unit.path, "content": unit.content, "digest": unit.raw_digest} for unit in sorted(self.corpus.units.values(), key=lambda value: value.path)]
        source_digest = digest([{key: value for key, value in source.items() if key != "content"} for source in source_files])
        semantic_nodes = []
        for node in self.nodes:
            item = {key: value for key, value in node.items() if key not in ("source", "parameterOrigins")}
            if "parameterOrigins" in node:
                item["parameterOrigins"] = {name: {"kind": origin["kind"], "expression": origin["expression"], "path": origin["path"]} for name, origin in node["parameterOrigins"].items()}
            semantic_nodes.append(item)
        semantic = {"entry": f"{module}:{name}", "nodes": semantic_nodes, "edges": self.edges}
        self.diagnostics.insert(0, {"level": "info", "message": "Static AST subset only. User code was not imported or executed; no inferred shapes or runtime verification. Source editing uses separately reviewed registered transactions."})
        return {"schemaVersion": 1, "id": f"architecture:{module}.{name}", "label": name, "sourceDigest": source_digest, "irDigest": digest(semantic), "entry": f"{module}:{name}", "nodes": self.nodes, "edges": self.edges, "diagnostics": self.diagnostics, "sources": source_files}


def analyze_project(root: str | Path, entry: str) -> dict[str, Any]:
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise AnalysisError("Project root is not a directory.")
    module, separator, name = entry.partition(":")
    if not separator or not name.isidentifier() or any(not part.isidentifier() for part in module.split(".")):
        raise AnalysisError("Entry must have the form module:ModelClass.")
    return Analyzer(Corpus(root_path)).analyze(module, name)


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
