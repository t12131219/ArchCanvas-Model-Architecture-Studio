"""Source-only model inventory and possible containment, never a runtime graph.

This scanner interprets a finite abstract domain (symbols, module references and
collections). It never imports, evaluates or executes supplied Python. Factory
bodies and both dynamic branches describe *possible source containment*; they do
not establish an execution path, tensor edges or permission to rewrite source.
"""
from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

MAX_FILES, MAX_BYTES, MAX_STEPS, MAX_DEPTH = 512, 16_000_000, 100_000, 16
EXCLUDED = {'.git', '.venv', 'venv', '__pycache__', 'node_modules', 'dist', 'build'}
# Public nn inheritance contracts, not guesses based on a class's spelling.
NN_BASES = {'Module', 'Sequential', 'ModuleList', 'ModuleDict', 'ParameterList', 'ParameterDict',
            'Linear', 'Embedding', 'LayerNorm', 'Dropout', 'ReLU', 'GELU', 'SiLU', 'Identity',
            'Conv1d', 'Conv2d', 'Conv3d', 'BatchNorm1d', 'BatchNorm2d', 'BatchNorm3d',
            'AdaptiveAvgPool2d', 'MaxPool2d', 'Flatten', 'MultiheadAttention', 'LSTM', 'GRU'}


class DiscoveryError(ValueError):
    pass


@dataclass
class SourceUnit:
    path: str
    module: str
    text: str
    tree: ast.Module
    bindings: dict[str, str] = field(default_factory=dict)


class ModelIndex:
    """Reusable source class resolver, including aliases and Python C3 lookup."""
    def __init__(self, files: dict[str, str]):
        if not isinstance(files, dict) or not files or len(files) > MAX_FILES:
            raise DiscoveryError('Model discovery accepts 1–512 Python source files.')
        if any(not isinstance(path, str) or not isinstance(text, str) for path, text in files.items()):
            raise DiscoveryError('Source paths and contents must be text.')
        if sum(len(text.encode('utf-8')) for text in files.values() if isinstance(text, str)) > MAX_BYTES:
            raise DiscoveryError('Model discovery source budget exceeded (16 MB).')
        self.units: dict[str, SourceUnit] = {}
        self.classes: dict[str, tuple[str, ast.ClassDef]] = {}
        self.functions: dict[str, tuple[str, ast.FunctionDef]] = {}
        self.syntax_errors: list[dict[str, Any]] = []
        self.unindexed_classes: list[dict[str, Any]] = []
        for path, text in sorted(files.items()):
            if not isinstance(path, str) or not isinstance(text, str):
                raise DiscoveryError('Source paths and contents must be text.')
            logical = PurePosixPath(path.replace('\\', '/'))
            if logical.is_absolute() or '..' in logical.parts or logical.suffix != '.py':
                raise DiscoveryError('Source paths must be relative .py paths without traversal.')
            path = str(logical)
            module = path[:-3].replace('/', '.')
            if module == '__init__': module = ''
            elif module.endswith('.__init__'): module = module[:-9]
            try:
                tree = ast.parse(text, filename=path)
            except (SyntaxError, RecursionError) as exc:
                self.syntax_errors.append({'file': path, 'line': getattr(exc, 'lineno', None), 'message': str(exc)})
                continue
            if sum(1 for _ in ast.walk(tree)) > MAX_STEPS:
                self.syntax_errors.append({'file': path, 'line': None, 'message': 'Syntax node budget exceeded (100000 per file).'})
                continue
            unit = SourceUnit(path, module, text, tree)
            self.units[path] = unit
            top_classes = {id(stmt) for stmt in tree.body if isinstance(stmt, ast.ClassDef)}
            for nested in ast.walk(tree):
                if isinstance(nested, ast.ClassDef) and id(nested) not in top_classes:
                    self.unindexed_classes.append({'file': path, 'name': nested.name,
                        'line': nested.lineno, 'endLine': nested.end_lineno,
                        'bases': [ast.unparse(base) for base in nested.bases],
                        'reason': 'Nested or conditional class declaration requires a lexical-scope adapter; no entry path is invented.'})
            for stmt in tree.body:
                if isinstance(stmt, ast.ClassDef):
                    key = self.key(module, stmt.name)
                    self.classes[key] = (path, stmt)
                elif isinstance(stmt, ast.FunctionDef):
                    self.functions[self.key(module, stmt.name)] = (path, stmt)
            self._bindings(unit)
        self._mro_cache: dict[str, list[str] | None] = {}
        self._module_cache: dict[str, bool] = {}
        self.method_mutations: dict[str, set[str]] = {}
        self._collect_method_mutations()

    def _collect_method_mutations(self) -> None:
        """A module-level write can replace a class without running its body.

        Inspect every possible module branch, while skipping function/class
        bodies. We never assume an import-time condition is false. This is a
        conservative shadow invalidation, not a simulation of Python effects.
        """
        index = self
        class Mutations(ast.NodeVisitor):
            def __init__(self, path): self.path = path
            def visit_ClassDef(self, node): pass
            def visit_FunctionDef(self, node): pass
            def visit_AsyncFunctionDef(self, node): pass
            def visit_Lambda(self, node): pass
            def record(self, receiver, name):
                key = index.resolve(index.symbol(self.path, receiver))
                if key in index.classes:
                    index.method_mutations.setdefault(key, set()).add(name)
            def visit_Attribute(self, node):
                if isinstance(node.ctx, (ast.Store, ast.Del)):
                    self.record(node.value, node.attr)
                self.generic_visit(node)
            def visit_Call(self, node):
                symbol = index.symbol(self.path, node.func)
                if symbol in ('setattr', 'delattr') and len(node.args) >= 2:
                    name = node.args[1].value if isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str) else '*'
                    self.record(node.args[0], name)
                self.generic_visit(node)
            def visit_Subscript(self, node):
                if isinstance(node.ctx, (ast.Store, ast.Del)) and isinstance(node.value, ast.Attribute) and node.value.attr == '__dict__':
                    name = node.slice.value if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str) else '*'
                    self.record(node.value.value, name)
                self.generic_visit(node)
        for path, unit in self.units.items():
            Mutations(path).visit(unit.tree)

    @staticmethod
    def key(module: str, name: str) -> str:
        return f'{module}:{name}'

    def _bindings(self, unit: SourceUnit) -> None:
        for stmt in unit.tree.body:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    unit.bindings[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
            elif isinstance(stmt, ast.ImportFrom):
                package = unit.module.split('.') if unit.path == '__init__.py' or unit.path.endswith('/__init__.py') else unit.module.split('.')[:-1]
                prefix = package[:max(0, len(package)-stmt.level+1)] if stmt.level else []
                module = '.'.join(prefix + ([stmt.module] if stmt.module else []))
                for alias in stmt.names:
                    if alias.name != '*':
                        unit.bindings[alias.asname or alias.name] = '.'.join(filter(None, (module, alias.name)))
            elif isinstance(stmt, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                unit.bindings[stmt.name] = '.'.join(filter(None, (unit.module, stmt.name)))
            elif isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                value = self.symbol(unit.path, stmt.value) if stmt.value is not None else ''
                for target in targets:
                    if isinstance(target, ast.Name):
                        if value: unit.bindings[target.id] = value
                        else: unit.bindings.pop(target.id, None)
        # Branch-local imports and names are not unconditional contracts.
        # Invalidate any import/alias they may replace, without guessing which
        # import-time condition a user environment will select.
        class ConditionalNames(ast.NodeVisitor):
            def visit_ClassDef(self, node): pass
            def visit_FunctionDef(self, node): pass
            def visit_AsyncFunctionDef(self, node): pass
            def visit_Name(self, node):
                if isinstance(node.ctx, (ast.Store, ast.Del)):
                    unit.bindings[node.id] = 'unresolved-conditional:' + node.id
            def visit_Import(self, node):
                for alias in node.names:
                    unit.bindings[alias.asname or alias.name.split('.')[0]] = 'unresolved-conditional:' + (alias.asname or alias.name.split('.')[0])
            def visit_ImportFrom(self, node):
                for alias in node.names:
                    if alias.name != '*': unit.bindings[alias.asname or alias.name] = 'unresolved-conditional:' + (alias.asname or alias.name)
        for stmt in unit.tree.body:
            if isinstance(stmt, (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.Match)):
                ConditionalNames().visit(stmt)

    def symbol(self, path: str, node: ast.AST | None) -> str:
        unit = self.units[path]
        if isinstance(node, ast.Name):
            return unit.bindings.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            prefix = self.symbol(path, node.value)
            return prefix + '.' + node.attr if prefix else ''
        return ''

    def resolve(self, symbol: str, seen: set[str] | None = None) -> str:
        """Resolve imported/re-exported aliases without loading external modules."""
        seen = set() if seen is None else seen
        if symbol in seen: return symbol
        seen.add(symbol)
        if ':' in symbol:
            module, _, name = symbol.rpartition(':')
        else:
            module, _, name = symbol.rpartition('.')
        key = self.key(module, name)
        for unit in self.units.values():
            if unit.module != module: continue
            if name in unit.bindings:
                alias = unit.bindings[name]
                canonical = '.'.join(filter(None, (module, name)))
                if alias not in (symbol, canonical, key): return self.resolve(alias, seen)
                if key in self.classes or key in self.functions: return key
            elif key in self.classes or key in self.functions:
                return 'unresolved-rebinding:' + symbol
        return symbol

    def framework_base(self, symbol: str) -> bool:
        return (not any(u.module == 'torch' or u.module.startswith('torch.') for u in self.units.values())
                and symbol.startswith('torch.nn.') and symbol[9:] in NN_BASES)

    def bases(self, key: str) -> list[str]:
        path, cls = self.classes[key]
        return [self.resolve(self.symbol(path, base)) for base in cls.bases]

    def is_module(self, key: str, seen: set[str] | None = None) -> bool:
        if key in self._module_cache: return self._module_cache[key]
        seen = set() if seen is None else set(seen)
        if key in seen or key not in self.classes: return False
        seen.add(key)
        result = any(self.framework_base(base) or (base in self.classes and self.is_module(base, seen)) for base in self.bases(key))
        self._module_cache[key] = result
        return result

    def mro(self, key: str, seen: set[str] | None = None) -> list[str] | None:
        if key in self._mro_cache: return self._mro_cache[key]
        seen = set() if seen is None else set(seen)
        if key in seen: return None
        if key not in self.classes: return [key]
        seen.add(key)
        bases = self.bases(key)
        inherited = [self.mro(base, seen) for base in bases]
        if any(value is None for value in inherited): return None
        sequences = [list(value) for value in inherited if value] + [list(bases)]
        result = [key]
        while any(sequences):
            sequences = [value for value in sequences if value]
            candidate = next((value[0] for value in sequences if not any(value[0] in other[1:] for other in sequences)), None)
            if candidate is None:
                self._mro_cache[key] = None
                return None
            result.append(candidate)
            for value in sequences:
                if value and value[0] == candidate: value.pop(0)
        self._mro_cache[key] = result
        return result

    def method(self, key: str, name: str) -> tuple[str, ast.FunctionDef | ast.AsyncFunctionDef] | None:
        return self._method_lookup(key, name)[1]

    def _method_lookup(self, key: str, name: str) -> tuple[str, tuple[str, ast.FunctionDef | ast.AsyncFunctionDef] | None]:
        order = self.mro(key)
        if order is None: return 'blocked', None
        for owner in order:
            if owner not in self.classes:
                if self.framework_base(owner) or owner == 'object': continue
                return 'blocked', None  # An external mixin may override the hook.
            path, cls = self.classes[owner]
            if cls.decorator_list or self.resolve(owner) != owner: return 'blocked', None
            if name in self.method_mutations.get(owner, set()) or '*' in self.method_mutations.get(owner, set()):
                return 'blocked', None
            for stmt in reversed(cls.body):
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == name:
                    return 'found', (path, stmt)
                # A class assignment shadows inherited methods too.
                if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                    if any(isinstance(target, ast.Name) and target.id == name for target in targets): return 'blocked', None
        return 'missing', None

    def method_blocked(self, key: str, name: str) -> bool:
        """True when a lookup was shadowed/replaced rather than merely absent."""
        return self._method_lookup(key, name)[0] == 'blocked'

    def effective_method(self, key: str) -> tuple[str, ast.FunctionDef | ast.AsyncFunctionDef] | None:
        # A custom __call__ overrides nn.Module.__call__, including an inherited
        # custom __call__; analysing only forward would describe another program.
        state, method = self._method_lookup(key, '__call__')
        return method if state == 'found' else None if state == 'blocked' else self.method(key, 'forward')

    def evidence(self, path: str, node: ast.AST) -> dict[str, Any]:
        return {'file': path, 'line': getattr(node, 'lineno', 1), 'endLine': getattr(node, 'end_lineno', 1),
                'expression': ast.get_source_segment(self.units[path].text, node) or ast.unparse(node)}


@dataclass
class Unknown:
    reason: str = 'runtime value'


@dataclass
class Object:
    cls: str
    identity: str
    attrs: dict[str, Any] = field(default_factory=dict)
    origin: dict[str, Any] | None = None
    ownership: str = 'source-instance'
    copy_evidence: dict[str, Any] | None = None


@dataclass
class Collection:
    items: list[Any]
    count: int | None
    kind: str = 'list'


@dataclass
class Alternatives:
    items: list[Any]


class Inventory:
    def __init__(self, index: ModelIndex):
        self.index = index
        self.relationships: dict[str, dict[str, Any]] = {}
        self.unknowns: dict[str, dict[str, Any]] = {}
        self.steps = 0
        self.active: list[str] = []
        self.context: list[dict[str, Any]] = []
        self._visited_factories: set[str] = set()
        self.budget_exhausted = False
        self.invalid_bindings: list[dict[str, Any]] = []
        self.assignment_overrides: list[dict[str, Any]] = []
        self.instance_serial = 0

    def tick(self) -> bool:
        self.steps += 1
        if self.steps > MAX_STEPS or len(self.active) > MAX_DEPTH:
            self.budget_exhausted = True
            return False
        return True

    def unknown(self, owner: str, slot: str, path: str, node: ast.AST, reason: str) -> None:
        record = {'owner': owner, 'slot': slot, 'reason': reason, 'evidence': self.index.evidence(path, node)}
        self.unknowns[json.dumps(record, sort_keys=True)] = record

    def relation(self, owner: Object, slot: str, value: Any, path: str, node: ast.AST,
                 count: int | None = 1, conditional: bool = False) -> None:
        if isinstance(value, Object):
            record = {'kind': 'contains', 'owner': owner.cls, 'target': value.cls, 'slot': slot,
                      'count': count, 'certainty': 'possible' if conditional or self.context else 'source',
                      'instanceId': value.identity, 'evidence': self.index.evidence(path, node),
                      'ownerInstanceId': owner.identity,
                      'via': list(self.context), 'targetLocal': value.cls in self.index.classes,
                      'targetEvidence': value.origin, 'ownership': value.ownership,
                      'copyEvidence': value.copy_evidence}
            # Context affects provenance, not a newly invented model edge.
            key = json.dumps({k: v for k, v in record.items() if k not in ('via', 'instanceId', 'certainty')}, sort_keys=True)
            previous = self.relationships.get(key)
            if previous is None or (previous['certainty'] == 'possible' and record['certainty'] == 'source'):
                self.relationships[key] = record
            if value.cls in ('torch.nn.ModuleList', 'torch.nn.Sequential', 'torch.nn.ModuleDict') and 'items' in value.attrs:
                self.relation(owner, slot, value.attrs['items'], path, node, count, conditional)
        elif isinstance(value, Collection):
            for i, item in enumerate(value.items):
                multiplicity = None if value.count is None else value.count if len(value.items) == 1 else count
                self.relation(owner, f'{slot}[{i if value.count is not None else "*"}]', item, path, node,
                              multiplicity, conditional or value.count is None)
            if not value.items and value.count is None:
                self.unknown(owner.cls, slot, path, node, 'Collection elements or runtime count are unresolved.')
        elif isinstance(value, Alternatives):
            for item in value.items: self.relation(owner, slot, item, path, node, count, True)
        elif isinstance(value, Unknown):
            self.unknown(owner.cls, slot, path, node, value.reason)

    @staticmethod
    def flatten(value: Any) -> list[Any]:
        return value.items if isinstance(value, (Collection, Alternatives)) else [value]

    def bind(self, function: ast.FunctionDef, args: list[Any], kwargs: dict[str, Any], path: str,
             method: bool = False) -> dict[str, Any]:
        positional = [*function.args.posonlyargs, *function.args.args][int(method):]
        names = [item.arg for item in positional]
        defaults = dict(zip(names[-len(function.args.defaults):], function.args.defaults)) if function.args.defaults else {}
        defaults.update({item.arg: value for item, value in zip(function.args.kwonlyargs, function.args.kw_defaults) if value is not None})
        allowed = set(names + [item.arg for item in function.args.kwonlyargs])
        invalid = (len(args) > len(positional) or bool(set(kwargs) - allowed)
                   or bool(set(names[:len(args)]) & set(kwargs))
                   or bool(set(kwargs) & {item.arg for item in function.args.posonlyargs[int(method):]})
                   or function.args.vararg is not None or function.args.kwarg is not None)
        if invalid:
            self.invalid_bindings.append({'file': path, 'function': function.name,
                'line': function.lineno, 'reason': 'Call signature cannot be bound (duplicate, positional-only, unknown, variadic, or excessive arguments).'} )
            return {name: Unknown('Invalid or dynamic call signature; argument binding is unproven.') for name in allowed}
        env = dict(zip(names, args))
        env.update(kwargs)
        for name in names + [item.arg for item in function.args.kwonlyargs]:
            if name not in env:
                env[name] = self.expr(defaults[name], path, env) if name in defaults else Unknown(f'Constructor/factory parameter {name} is not selected.')
        return env

    def construct(self, key: str, args: list[Any], kwargs: dict[str, Any], path: str, node: ast.AST) -> Any:
        self.instance_serial += 1
        obj = Object(key, f'{path}:{getattr(node, "lineno", 1)}:{getattr(node, "col_offset", 0)}:{key}:context-{self.instance_serial}', origin=self.index.evidence(path, node))
        if key in self.active or not self.tick(): return obj
        self.active.append(key)
        init = self.index.method(key, '__init__')
        if init and isinstance(init[1], ast.FunctionDef):
            own_path, method = init
            env = self.bind(method, args, kwargs, own_path, True)
            env['self'] = obj
            self.block(method.body, own_path, env)
        self.active.pop()
        return obj

    def expr(self, node: ast.AST | None, path: str, env: dict[str, Any]) -> Any:
        if node is None: return None
        if not self.tick(): return Unknown('Discovery budget exhausted; subtree not claimed complete.')
        if isinstance(node, ast.Name): return env.get(node.id, Unknown('Unbound source symbol ' + node.id))
        if isinstance(node, ast.Constant): return node.value
        if isinstance(node, ast.Attribute):
            base = self.expr(node.value, path, env)
            if isinstance(base, Object): return base.attrs.get(node.attr, Unknown('Object attribute ' + node.attr + ' is unresolved.'))
            return Unknown('Attribute ' + ast.unparse(node) + ' is runtime dependent.')
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return Collection([self.expr(item, path, env) for item in node.elts], len(node.elts), type(node).__name__.lower())
        if isinstance(node, ast.Dict):
            return {self.expr(k, path, env): self.expr(v, path, env) for k, v in zip(node.keys, node.values) if isinstance(k, ast.Constant)}
        if isinstance(node, ast.Subscript):
            value, slot = self.expr(node.value, path, env), self.expr(node.slice, path, env)
            if isinstance(value, Collection):
                if isinstance(slot, int) and -len(value.items) <= slot < len(value.items): return value.items[slot]
                return Alternatives(value.items) if value.items else Unknown('Collection slot unresolved.')
            if isinstance(value, dict) and isinstance(slot, (str, int)): return value.get(slot, Unknown('Dictionary slot unresolved.'))
            return Unknown('Dynamic source slot ' + ast.unparse(node))
        if isinstance(node, ast.IfExp):
            test = self.expr(node.test, path, env)
            if isinstance(test, bool): return self.expr(node.body if test else node.orelse, path, env)
            return Alternatives([self.expr(node.body, path, env), self.expr(node.orelse, path, env)])
        if isinstance(node, ast.ListComp):
            local = dict(env)
            count = 1
            for generator in node.generators:
                collection = self.expr(generator.iter, path, local)
                known = collection.count if isinstance(collection, Collection) else None
                count = count * known if count is not None and known is not None else None
                sample = Alternatives(collection.items) if isinstance(collection, Collection) else Unknown('Dynamic comprehension element')
                self.assign(generator.target, sample, path, local)
                if generator.ifs: count = None
            return Collection([self.expr(node.elt, path, local)], count)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'append':
                collection = self.expr(node.func.value, path, env)
                value = self.expr(node.args[0], path, env) if node.args else Unknown()
                if isinstance(collection, Collection):
                    collection.items.append(value)
                    if collection.count is not None: collection.count += 1
                return None
            args = [self.expr(item, path, env) for item in node.args]
            kwargs = {item.arg: self.expr(item.value, path, env) for item in node.keywords if item.arg is not None}
            dynamic_arguments = any(isinstance(item, ast.Starred) for item in node.args) or any(item.arg is None for item in node.keywords)
            if dynamic_arguments:
                self.invalid_bindings.append({'file': path, 'function': ast.unparse(node.func), 'line': node.lineno,
                                              'reason': 'Expanded *args/**kwargs are not a proven static signature.'})
                return Unknown('Expanded call arguments are unresolved; no constructor/factory binding is established.')
            symbol = self.index.resolve(self.index.symbol(path, node.func))
            if isinstance(node.func, ast.Name) and node.func.id in env:
                # Local names can shadow a framework import or factory.
                return Unknown('Locally rebound callable ' + node.func.id)
            if symbol in self.index.classes:
                return self.construct(symbol, args, kwargs, path, node)
            if symbol in self.index.functions:
                own_path, function = self.index.functions[symbol]
                if symbol in self.active or function.decorator_list or not self.tick(): return Unknown('Recursive/decorated factory ' + symbol)
                self.active.append(symbol)
                self.context.append(self.index.evidence(path, node))
                result = self.block(function.body, own_path, self.bind(function, args, kwargs, own_path))
                self.context.pop()
                self.active.pop()
                return result if result is not _NO_RETURN else Unknown('Factory has no recoverable return: ' + symbol)
            if symbol in ('copy.copy', 'copy.deepcopy') and args:
                original = args[0]
                if isinstance(original, Object) and not (original.cls in self.index.classes and
                        self.index.method(original.cls, '__deepcopy__' if symbol == 'copy.deepcopy' else '__copy__')):
                    # A copy contract establishes a distinct source instance;
                    # no user __copy__/__deepcopy__ body is invoked or certified.
                    return Object(original.cls, original.identity + f'.copy@{path}:{node.lineno}:{node.col_offset}',
                                  dict(original.attrs), original.origin, 'copy-candidate', self.index.evidence(path, node))
                return Unknown('Copy source is not a locally identified module.')
            if symbol in ('list', 'tuple') and args:
                return args[0] if isinstance(args[0], Collection) else Collection([args[0]], None)
            if symbol == 'range':
                if args and all(isinstance(arg, int) and not isinstance(arg, bool) for arg in args):
                    try:
                        selected = list(range(*args)) if len(args) <= 3 and all(abs(arg) < 1024 for arg in args) else None
                    except ValueError: selected = None
                    if selected is not None: return Collection(selected, len(selected))
                return Collection([Unknown('Runtime range item')], None)
            if symbol.startswith('torch.nn.') and not symbol.startswith('torch.nn.functional.') and self.index.framework_base(symbol):
                obj = Object(symbol, f'{path}:{node.lineno}:{node.col_offset}:{symbol}', origin=self.index.evidence(path, node))
                if symbol in ('torch.nn.ModuleList', 'torch.nn.Sequential', 'torch.nn.ModuleDict'):
                    collection = args[0] if symbol == 'torch.nn.ModuleList' and args else Collection(args, len(args))
                    self.relation(obj, 'items', collection, path, node)
                    obj.attrs['items'] = collection
                return obj
            # super().__init__ can establish inherited containment. No initializer
            # body is imported or run; only its AST is visited with these values.
            if (isinstance(node.func, ast.Attribute) and node.func.attr == '__init__'
                    and isinstance(node.func.value, ast.Call) and isinstance(node.func.value.func, ast.Name)
                    and node.func.value.func.id == 'super' and isinstance(env.get('self'), Object)):
                obj = env['self']
                current = next((key for key in reversed(self.active) if key in self.index.classes), obj.cls)
                order = self.index.mro(obj.cls) or []
                rest = order[order.index(current)+1:] if current in order else []
                parent = next((key for key in rest if key in self.index.classes and self.index.method(key, '__init__')), None)
                if parent and parent not in self.active:
                    own_path, method = self.index.method(parent, '__init__')
                    if isinstance(method, ast.FunctionDef):
                        self.active.append(parent)
                        local = self.bind(method, args, kwargs, own_path, True)
                        local['self'] = obj
                        self.block(method.body, own_path, local)
                        self.active.pop()
                elif any(base == 'torch.nn.Sequential' for base in rest):
                    self.relation(obj, 'items', Collection(args, len(args)), path, node)
                return None
            return Unknown('External/dynamic callable ' + (symbol or ast.unparse(node.func)) + ' has no local body.')
        return Unknown('Expression ' + type(node).__name__ + ' is not a selected static value.')

    def assign(self, target: ast.AST, value: Any, path: str, env: dict[str, Any], conditional: bool = False) -> None:
        if isinstance(target, ast.Name): env[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            for i, item in enumerate(target.elts):
                selected = value.items[i] if isinstance(value, Collection) and i < len(value.items) else Unknown('Tuple return slot unresolved.')
                self.assign(item, selected, path, env, conditional)
        elif isinstance(target, ast.Attribute):
            owner = self.expr(target.value, path, env)
            if isinstance(owner, Object):
                if conditional:
                    for row in self.relationships.values():
                        if row['ownerInstanceId'] == owner.identity and (row['slot'] == target.attr or row['slot'].startswith(target.attr + '[')):
                            row['certainty'] = 'possible'
                    self.assignment_overrides.append({'owner': owner.cls, 'slot': target.attr,
                        'evidence': self.index.evidence(path, target), 'conditional': True,
                        'retiredTargets': []})
                if not conditional:
                    removed = [key for key, row in self.relationships.items()
                               if row['ownerInstanceId'] == owner.identity
                               and (row['slot'] == target.attr or row['slot'].startswith(target.attr + '['))]
                    if removed:
                        self.assignment_overrides.append({'owner': owner.cls, 'slot': target.attr,
                            'evidence': self.index.evidence(path, target),
                            'retiredTargets': sorted({self.relationships[key]['target'] for key in removed})})
                        for key in removed: del self.relationships[key]
                owner.attrs[target.attr] = value
                self.relation(owner, target.attr, value, path, target, conditional=conditional)

    def block(self, body: list[ast.stmt], path: str, env: dict[str, Any], conditional: bool = False) -> Any:
        returns = []
        for stmt in body:
            if not self.tick(): break
            if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                value = self.expr(stmt.value, path, env)
                for target in stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]:
                    self.assign(target, value, path, env, conditional)
            elif isinstance(stmt, ast.Return):
                value = self.expr(stmt.value, path, env)
                return Alternatives([*returns, value]) if returns else value
            elif isinstance(stmt, ast.Expr): self.expr(stmt.value, path, env)
            elif isinstance(stmt, ast.If):
                test = self.expr(stmt.test, path, env)
                branches = [stmt.body if test else stmt.orelse] if isinstance(test, bool) else [stmt.body, stmt.orelse]
                snapshots = []
                branch_returns = []
                for branch in branches:
                    local = dict(env)
                    result = self.block(branch, path, local, conditional or not isinstance(test, bool))
                    if result is not _NO_RETURN: branch_returns.append(result)
                    else: snapshots.append(local)
                returns.extend(branch_returns)
                if len(branch_returns) == len(branches):
                    return returns[0] if len(returns) == 1 else Alternatives(returns)
                for name in set().union(*(set(local) for local in snapshots)):
                    values = [local.get(name, Unknown('Name only assigned in another branch.')) for local in snapshots]
                    env[name] = values[0] if len(values) == 1 or all(value is values[0] for value in values) else Alternatives(values)
            elif isinstance(stmt, (ast.For, ast.AsyncFor)):
                collection = self.expr(stmt.iter, path, env)
                items = collection.items if isinstance(collection, Collection) else [Unknown('Dynamic loop element')]
                known = isinstance(collection, Collection) and collection.count is not None and collection.count <= 16
                collections = {id(value): value.count for value in env.values() if isinstance(value, Collection)}
                for value in items[:16] if known else [Alternatives(items)]:
                    self.assign(stmt.target, value, path, env, not known)
                    self.block(stmt.body, path, env, conditional or not known)
                if not known:
                    for value in env.values():
                        if isinstance(value, Collection) and collections.get(id(value)) != value.count: value.count = None
            elif isinstance(stmt, (ast.With, ast.Try, ast.While)):
                # Possible structural statements only; an unknown region never
                # establishes a definite execution path or exact multiplicity.
                for branch in [stmt.body, getattr(stmt, 'orelse', []), getattr(stmt, 'finalbody', [])]:
                    result = self.block(branch, path, dict(env), True)
                    if result is not _NO_RETURN: returns.append(result)
        return Alternatives(returns) if returns else _NO_RETURN

    def run(self) -> dict[str, Any]:
        model_keys = [key for key in sorted(self.index.classes) if self.index.is_module(key)]
        for key in model_keys:
            path, cls = self.index.classes[key]
            self.construct(key, [], {}, path, cls)
        # Analyze all local functions which can transitively construct a local
        # module. This closes constructor-argument/factory contexts, including
        # a factory returning (model, optimizer). Unrelated training functions
        # remain outside the inventory traversal.
        productive = set(model_keys)
        changed = True
        while changed:
            changed = False
            for key, (path, function) in self.index.functions.items():
                if key in productive: continue
                if any(isinstance(node, ast.Call) and self.index.resolve(self.index.symbol(path, node.func)) in productive for node in ast.walk(function)):
                    productive.add(key); changed = True
        for key in sorted(productive - set(model_keys)):
            path, function = self.index.functions[key]
            if not function.decorator_list:
                self.active.append(key)
                self.block(function.body, path, self.bind(function, [], {}, path))
                self.active.pop()
        # Distinct abstract factory contexts are tracked until their final
        # assignments have settled, then duplicate source facts are compacted.
        compact = {}
        for relation in self.relationships.values():
            identity = json.dumps({key: value for key, value in relation.items()
                                   if key not in ('ownerInstanceId', 'instanceId', 'via', 'certainty')}, sort_keys=True)
            old = compact.get(identity)
            if old is None or old['certainty'] == 'possible' and relation['certainty'] == 'source': compact[identity] = relation
        self.relationships = compact
        contained = {relation['target'] for relation in self.relationships.values() if relation['targetLocal'] and relation['owner'] != relation['target']}
        inheritance = [{'kind': 'inherits', 'owner': key, 'target': base,
                        'targetLocal': base in self.index.classes,
                        'evidence': self.index.evidence(path, expression)}
                       for key, (path, cls) in sorted(self.index.classes.items())
                       for base, expression in zip(self.index.bases(key), cls.bases)]
        models = []
        for key in model_keys:
            path, cls = self.index.classes[key]
            method = self.index.effective_method(key)
            reasons = []
            if self.index.mro(key) is None: reasons.append('Invalid or unresolved C3 method resolution order.')
            if self.index.resolve(key) != key: reasons.append('The class name is rebound after its declaration.')
            if self.index.method_blocked(key, '__init__'): reasons.append('Constructor is replaced or its local method resolution is uncertain.')
            if cls.decorator_list: reasons.append('Class decorators may replace the model class.')
            if not method: reasons.append('No local forward or __call__ implementation is available.')
            elif not isinstance(method[1], ast.FunctionDef) or method[1].decorator_list: reasons.append('Async/decorated entry method needs an explicit adapter.')
            models.append({'id': key, 'entry': key, 'name': cls.name, 'file': path,
                           'bases': self.index.bases(key), 'root': key not in contained,
                           'entryMethod': method[1].name if method else None,
                           'methodOwner': next((owner for owner in self.index.mro(key) or [] if owner in self.index.classes and method and method[1] in self.index.classes[owner][1].body), None),
                           'openable': not reasons, 'limitations': reasons,
                           'evidence': self.index.evidence(path, cls),
                           'methodEvidence': self.index.evidence(*method) if method else None})
        relations = sorted(self.relationships.values(), key=lambda row: (row['owner'], row['slot'], row['target'], row['evidence']['line']))
        resolved_slots = {(row['owner'], row['slot']) for row in relations}
        unknowns = sorted(self.unknowns.values(), key=lambda row: (row['owner'], row['slot'], row['evidence']['file'], row['evidence']['line']))
        for row in unknowns: row['resolvedInSomeContexts'] = (row['owner'], row['slot']) in resolved_slots
        inventory_complete = not self.index.syntax_errors and not self.index.unindexed_classes and not self.budget_exhausted
        return {'schema': 'archcanvas-model-discovery/1', 'analysis': 'static-source-inventory',
                'modelExecuted': False, 'complete': inventory_complete,
                'inventoryComplete': inventory_complete,
                'hierarchyComplete': inventory_complete and not self.invalid_bindings
                    and not any(row.get('conditional') for row in self.assignment_overrides)
                    and not any(not row['resolvedInSomeContexts'] for row in unknowns)
                    and not any(row['count'] is None or row['certainty'] == 'possible' for row in relations),
                'completenessScope': 'Local classes proven to inherit a registered torch.nn base; possible source containment only. External/dynamic classes and runtime paths remain explicit unknowns.',
                'models': models, 'candidates': [row['entry'] for row in models if row['openable']],
                'classes': [{'id': key, 'model': key in model_keys,
                             'modelStatus': 'module' if key in model_keys else 'not-proven-module',
                             'bases': self.index.bases(key),
                             'evidence': self.index.evidence(path, cls)} for key, (path, cls) in sorted(self.index.classes.items())],
                'roots': [row['id'] for row in models if row['root']], 'relationships': relations,
                'inheritance': inheritance,
                'unknowns': unknowns, 'syntaxErrors': self.index.syntax_errors,
                'unindexedClasses': self.index.unindexed_classes,
                'invalidBindings': self.invalid_bindings,
                'assignmentOverrides': self.assignment_overrides,
                'budget': {'files': len(self.index.units), 'steps': self.steps, 'exhausted': self.budget_exhausted,
                           'maxFiles': MAX_FILES, 'maxBytes': MAX_BYTES, 'maxSteps': MAX_STEPS, 'maxDepth': MAX_DEPTH},
                'files': [{'path': path, 'sha256': hashlib.sha256(unit.text.encode('utf-8')).hexdigest()} for path, unit in sorted(self.index.units.items())]}


_NO_RETURN = object()


def discover_files(files: dict[str, str]) -> dict[str, Any]:
    return Inventory(ModelIndex(files)).run()


def read_directory_files(root: str | Path, *, max_files: int = 80, max_bytes: int = 2_000_000) -> dict[str, str]:
    root = Path(root).resolve()
    if not root.is_dir(): raise DiscoveryError('Discovery root is not a directory.')
    files = {}
    total_bytes = 0
    for path in sorted(root.rglob('*.py')):
        relative = path.relative_to(root)
        if any(part in EXCLUDED for part in relative.parts): continue
        if path.is_symlink() or any(part.is_symlink() for part in path.parents if part != root and part.is_relative_to(root)):
            raise DiscoveryError(f'Source symlinks are not accepted: {relative}.')
        actual = path.resolve()
        if not actual.is_relative_to(root): continue
        if len(files) >= max_files: raise DiscoveryError(f'Model source file budget exceeded ({max_files} files).')
        total_bytes += path.stat().st_size
        if total_bytes > max_bytes: raise DiscoveryError(f'Model source byte budget exceeded ({max_bytes} bytes).')
        try: files[relative.as_posix()] = path.read_text(encoding='utf-8-sig')
        except (OSError, UnicodeError) as exc: raise DiscoveryError(f'Cannot read {relative}: {exc}') from exc
    return files


def discover_directory(root: str | Path) -> dict[str, Any]:
    return discover_files(read_directory_files(root, max_files=MAX_FILES, max_bytes=MAX_BYTES))
