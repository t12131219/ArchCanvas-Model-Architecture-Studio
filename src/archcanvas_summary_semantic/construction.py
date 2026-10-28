"""Bounded module construction evidence. This never imports or executes a model.

Only straight assignments and single-return collection factories are interpreted.
Object bindings are separate from JSON constructor constants and from tensor SSA.
"""
import ast
import copy
from dataclasses import dataclass, replace


@dataclass
class Module:
    call: ast.Call
    constants: dict
    objects: dict
    identity: str
    evidence: list
    allocation: str = 'constructor-object; parameter-sharing-unresolved'
    reference: str = ''


@dataclass
class Collection:
    elements: list
    evidence: list
    expression: str


@dataclass
class ModuleMap:
    elements: dict
    evidence: list
    expression: str


class Construction:
    LIMIT = 16

    def __init__(self, analyzer, unit, owner, constants, objects, path, reference_prefix='entry'):
        self.a, self.u, self.path, self.owner = analyzer, unit, path, owner
        self.reference_prefix = reference_prefix
        self.constants, self.objects = dict(constants), dict(objects or {})
        self.blocked = set()
        if owner is None:
            return
        from .analyzer import text
        if any(self.a.resolve(text(base)) not in {'torch.nn.Module', 'object'} for base in owner.bases):
            self.objects.clear()
            return
        hooks = {'__getattribute__', '__getattr__', '__setattr__', '__new__'}
        if any(isinstance(n, ast.FunctionDef) and (n.name in hooks or n.decorator_list)
               for n in owner.body):
            self.objects.clear()
            return
        init = next((n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == '__init__'), None)
        if init is None:
            return
        if init.decorator_list:
            return
        init = copy.copy(init)
        init.body = self.selected_body(init.body)
        from .analyzer import literal, text
        # Any non-straight assignment to an attribute invalidates that binding.
        direct = {id(n) for n in init.body if isinstance(n, (ast.Assign, ast.AnnAssign))}
        for n in self.walk_helpers(init):
            if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)) and id(n) not in direct:
                for t in n.targets if isinstance(n, ast.Assign) else [n.target]:
                    if isinstance(t, ast.Attribute):
                        self.blocked.add(text(t))
        for n in init.body:
            if not isinstance(n, (ast.Assign, ast.AnnAssign)) or n.value is None:
                continue
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            if len(targets) != 1 or not isinstance(targets[0], (ast.Name, ast.Attribute)):
                continue
            key = text(targets[0])
            if key in self.blocked:
                self.objects.pop(key, None)
                continue
            obj = self.read(n.value, self.constants, self.objects, self.identity(key))
            self.objects.pop(key, None)
            if obj is not None:
                self.objects[key] = obj
            value = literal(n.value, self.constants)
            if not isinstance(value, dict):
                self.constants[key] = value
        # Mutating methods or indexed writes can change a collection after creation.
        invalid = set()
        for n in self.walk_helpers(init):
            target = None
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in {'append', 'extend', 'insert', 'pop', 'clear', 'remove', '__setitem__', '__delitem__'}:
                target = text(n.func.value)
            if isinstance(n, ast.Subscript) and isinstance(n.ctx, (ast.Store, ast.Del)):
                target = text(n.value)
            if target:
                obj = self.objects.get(target)
                if obj is not None:
                    invalid.add(id(obj))
            if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Del):
                obj = self.objects.get(text(n))
                if obj is not None:
                    invalid.add(id(obj))
            if isinstance(n, ast.Call):
                methods = {m.name for m in owner.body if isinstance(m, ast.FunctionDef)}
                target = text(n.func)
                queries = {'parameters', 'named_parameters', 'buffers', 'named_buffers',
                           'modules', 'named_modules', 'children', 'named_children'} if any(
                               self.a.resolve(text(base)) == 'torch.nn.Module' for base in owner.bases) else set()
                registration = target in {'self.register_buffer', 'self.register_parameter'} and target[5:] not in methods and bool(queries) and n.args and isinstance(n.args[0], ast.Constant) and type(n.args[0].value) is str
                if registration:
                    replaced = self.objects.get('self.' + n.args[0].value)
                    if replaced is not None:
                        invalid.add(id(replaced))
                if target.startswith('self.') and target[5:] not in methods | queries and not registration:
                    invalid.update(id(o) for o in self.objects.values() if isinstance(o, (Module, Collection, ModuleMap)))
                for arg in [*n.args, *(k.value for k in n.keywords)]:
                    obj = self.objects.get(text(arg))
                    if isinstance(obj, (Collection, ModuleMap)):
                        invalid.add(id(obj))
                    # An escaping owner can replace module bindings as well as
                    # collections. No later selection certificate survives it.
                    if text(arg) == 'self':
                        invalid.update(id(o) for o in self.objects.values() if isinstance(o, (Module, Collection, ModuleMap)))
        self.objects = {key: obj for key, obj in self.objects.items() if id(obj) not in invalid}

    def selected_body(self, body, constants=None, objects=None):
        from .static_values import value, UNKNOWN
        from .analyzer import text
        constants = dict(self.constants if constants is None else constants)
        objects = dict(self.objects if objects is None else objects)
        result = []
        for statement in body:
            if isinstance(statement, ast.If):
                condition = value(statement.test, constants, objects)
                if type(condition) is bool:
                    selected = self.selected_body(statement.body if condition else statement.orelse, constants, objects)
                    result.extend(selected)
                else:
                    result.append(statement)
            else:
                selected = [statement]
                result.append(statement)
            # A prior write invalidates a condition input, including writes in
            # unresolved control. Never select using the original argument value.
            for item in ([statement] if isinstance(statement, ast.If) else selected):
                for node in ast.walk(item):
                    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                        scalar = value(node.value, constants, objects) if isinstance(node, (ast.Assign, ast.AnnAssign)) else UNKNOWN
                        for target in targets:
                            key = text(target)
                            constants.pop(key, None); objects.pop(key, None)
                            if scalar is not UNKNOWN and not isinstance(statement, ast.If):
                                constants[key] = scalar
        return result

    def walk_helpers(self, fn):
        """Include reachable local owner helpers when checking writes/escapes."""
        methods = {n.name: n for n in self.owner.body if isinstance(n, ast.FunctionDef)} if self.owner else {}
        pending, seen = [fn], set()
        for function in pending:
            if id(function) in seen:
                continue
            seen.add(id(function))
            for node in ast.walk(function):
                yield node
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == 'self' and node.func.attr in methods:
                    pending.append(methods[node.func.attr])

    def identity(self, name):
        return '.'.join(filter(None, [self.path, name.removeprefix('self.')]))

    def reference(self, identity, allocation):
        # A binding name can be assigned two different allocations. Include
        # owner generation and allocation position, while aliases reuse Module.
        return f'{self.reference_prefix}|{identity}@{self.u["path"]}:{allocation.lineno}:{allocation.col_offset}'

    def get(self, name):
        return self.objects.get(name)

    def bind(self, fn, call, constants, objects):
        """Exact Python argument binding for our restricted factory subset."""
        from .analyzer import literal
        if fn.args.vararg or fn.args.kwarg or fn.decorator_list:
            return None
        params = [p.arg for p in [*fn.args.posonlyargs, *fn.args.args] if p.arg != 'self']
        posonly = {p.arg for p in fn.args.posonlyargs}
        keyword_only = {p.arg: default for p, default in zip(fn.args.kwonlyargs, fn.args.kw_defaults)}
        if len(call.args) > len(params) or any(isinstance(n, ast.Starred) for n in call.args):
            return None
        args = dict(zip(params[-len(fn.args.defaults):], fn.args.defaults)) if fn.args.defaults else {}
        args.update({p: default for p, default in keyword_only.items() if default is not None})
        args.update(zip(params, call.args))
        for kw in call.keywords:
            if kw.arg not in [*params, *keyword_only] or kw.arg in posonly or kw.arg in params[:len(call.args)] or sum(k.arg == kw.arg for k in call.keywords) != 1:
                return None
            args[kw.arg] = kw.value
        if any(p not in args for p in [*params, *keyword_only]):
            return None
        scalar, refs = {}, {}
        defaults = {id(n) for n in [*fn.args.defaults, *(d for d in fn.args.kw_defaults if d is not None)]}
        for key, expr in args.items():
            if id(expr) in defaults:
                # Defaults belong to the definition's namespace and are created
                # once by Python, not freshly allocated by each factory call.
                unit = self.a.expression_unit(expr, self.u)
                with self.a.scope(unit):
                    scalar[key] = literal(expr, self.a.globals)
                obj = None
            else:
                scalar[key] = literal(expr, constants)
                obj = self.read(expr, constants, objects, self.identity('argument:' + key))
            if obj is not None:
                refs[key] = obj
        return scalar, refs

    def arguments(self, module, cls):
        init = next((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '__init__'), None)
        unit = self.a.expression_unit(module.call, self.u)
        with self.a.scope(unit):
            return self.bind(init, module.call, module.constants, module.objects) if init else ({}, {})

    def read(self, n, constants, objects, identity, depth=0):
        unit = self.a.expression_unit(n, self.u)
        previous = self.u
        self.u = unit
        try:
            with self.a.scope(unit):
                return self._read(n, constants, objects, identity, depth)
        finally:
            self.u = previous

    def _read(self, n, constants, objects, identity, depth=0):
        from .analyzer import literal, text, MODULES
        if depth > 8:
            return None
        if isinstance(n, (ast.Name, ast.Attribute)):
            return objects.get(text(n))
        if isinstance(n, (ast.List, ast.Tuple)):
            elements = [self.read(e, constants, objects, identity + '.' + str(i), depth + 1) for i, e in enumerate(n.elts)]
            if len(elements) <= self.LIMIT and all(isinstance(e, Module) for e in elements):
                return Collection(elements, [v for e in elements for v in e.evidence], text(n))
            return None
        if isinstance(n, ast.Subscript):
            collection = self.read(n.value, constants, objects, identity, depth + 1)
            index = literal(n.slice, constants)
            if isinstance(collection, ModuleMap) and type(index) is str:
                return collection.elements.get(index)
            if isinstance(collection, Collection) and type(index) is int and -len(collection.elements) <= index < len(collection.elements):
                return collection.elements[index]
            return None
        if not isinstance(n, ast.Call):
            return None
        target = self.a.resolve(text(n.func))
        evidence = self.a.evidence(self.u, n, 'constructor')
        if target == 'copy.deepcopy' and len(n.args) == 1 and not n.keywords:
            obj = self.read(n.args[0], constants, objects, identity, depth + 1)
            if isinstance(obj, Module):
                # Internal argument references require a graph copy, beyond this subset.
                if obj.objects:
                    return None
                pair = self.a.definition(text(obj.call.func), self.u['cell']) or self.a.definition(text(obj.call.func))
                if pair:
                    cls = pair[1]
                    if not isinstance(cls, ast.ClassDef) or [self.a.resolve(text(b)) for b in cls.bases] != ['torch.nn.Module']:
                        return None
                    hooks = {'__deepcopy__', '__copy__', '__reduce__', '__reduce_ex__', '__getstate__', '__setstate__'}
                    if any(isinstance(m, ast.FunctionDef) and m.name in hooks for entries in self.a.definitions.values() for _, c in entries if isinstance(c, ast.ClassDef) for m in c.body):
                        return None
                return replace(obj, identity=identity, reference=self.reference(identity, n), evidence=obj.evidence + evidence, allocation='default-deepcopy')
            return None
        if target == 'torch.nn.ModuleDict' and len(n.args) == 1 and not n.keywords and isinstance(n.args[0], ast.Dict):
            expr = n.args[0]
            keys = [literal(k, constants) for k in expr.keys]
            items = [self.read(e, constants, objects, identity + '.' + str(i), depth + 1) for i,e in enumerate(expr.values)]
            if len(items) <= self.LIMIT and all(type(k) is str for k in keys) and len(set(keys)) == len(keys) and all(isinstance(e, Module) for e in items):
                return ModuleMap(dict(zip(keys, items)), evidence + [s for e in items for s in e.evidence], text(n))
            return None
        if target == 'torch.nn.ModuleList' and len(n.args) == 1 and not n.keywords:
            expr = n.args[0]
            items = []
            if isinstance(expr, (ast.List, ast.Tuple)):
                items = [self.read(e, constants, objects, identity + '.' + str(i), depth + 1) for i, e in enumerate(expr.elts)]
            elif isinstance(expr, ast.ListComp) and len(expr.generators) == 1:
                gen = expr.generators[0]
                if gen.ifs or gen.is_async or not isinstance(gen.target, ast.Name) or not isinstance(gen.iter, ast.Call) or text(gen.iter.func) != 'range' or self.a.definition('range') or 'range' in objects or len(gen.iter.args) != 1 or gen.iter.keywords:
                    return None
                count = literal(gen.iter.args[0], constants)
                if type(count) is not int or not 0 <= count <= self.LIMIT:
                    return None
                items = [self.read(expr.elt, dict(constants, **{gen.target.id: i}), objects, identity + '.' + str(i), depth + 1) for i in range(count)]
            else:
                bound = self.read(expr, constants, objects, identity, depth + 1)
                if not isinstance(bound, Collection):
                    return None
                items = bound.elements
            if len(items) > self.LIMIT or any(not isinstance(e, Module) for e in items):
                return None
            return Collection(items, evidence + [s for e in items for s in e.evidence], text(n))
        pair = self.a.definition(text(n.func), self.u['cell']) or self.a.definition(text(n.func))
        if pair and isinstance(pair[1], ast.FunctionDef):
            unit, fn = pair
            body = [s for s in fn.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))]
            bound = self.bind(fn, n, constants, objects)
            if bound is None:
                return None
            with self.a.scope(unit):
                obj = self.factory_body(body, *bound, identity, depth + 1)
            if isinstance(obj, (Module, Collection, ModuleMap)):
                obj.evidence = evidence + obj.evidence
            return obj
        known = target == 'torch.nn.' + target.split('.')[-1] and target.split('.')[-1] in MODULES and self.a.value_namespace(n.func, self.u)
        if known or pair and isinstance(pair[1], ast.ClassDef):
            # Retain only module references actually used as constructor arguments.
            refs = {key: obj for key, obj in objects.items() if isinstance(obj, (Module, Collection, ModuleMap)) and any(text(part) == key for arg in [*n.args, *(k.value for k in n.keywords)] for part in ast.walk(arg))}
            return Module(n, dict(constants), refs, identity, evidence,
                          'fresh-framework-construction' if known else 'constructor-object; parameter-sharing-unresolved',
                          self.reference(identity, n))
        return None

    def factory_body(self, body, constants, objects, identity, depth):
        """Interpret a deliberately small effect-free factory language, never eval.

        Unknown effects, owner escapes, loops and dynamic branch choices abort.
        Unlike source-call expansion, this produces construction identity proof.
        """
        from .analyzer import literal, text
        if depth > 8 or len(body) > 64:
            return None
        constants, objects = dict(constants), dict(objects)
        evidence = []
        for statement in body:
            if isinstance(statement, ast.Return):
                obj = self.read(statement.value, constants, objects, identity, depth + 1)
                if isinstance(obj, (Module, Collection, ModuleMap)):
                    unit = self.a.expression_unit(statement, self.u)
                    obj = replace(obj, evidence=evidence + self.a.evidence(unit, statement, 'factory-return') + obj.evidence)
                return obj
            if isinstance(statement, ast.Pass):
                continue
            if isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None:
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                if len(targets) != 1 or not isinstance(targets[0], ast.Name):
                    return None
                key = targets[0].id
                obj = self.read(statement.value, constants, objects, identity + '.' + key, depth + 1)
                value = literal(statement.value, constants)
                if obj is None and (isinstance(value, dict) and 'unresolved' in value or any(isinstance(n, ast.Call) for n in ast.walk(statement.value))):
                    return None
                objects.pop(key, None); constants.pop(key, None)
                if obj is not None:
                    objects[key] = obj
                else:
                    constants[key] = value
                unit = self.a.expression_unit(statement, self.u)
                evidence += self.a.evidence(unit, statement, 'factory-assignment')
                continue
            # Conditions must be statically decidable; no guessing a branch.
            if isinstance(statement, ast.If):
                from .static_values import value as static_value
                value = static_value(statement.test, constants, objects)
                if type(value) is not bool:
                    return None
                selected = statement.body if value else statement.orelse
                index = body.index(statement)
                obj = self.factory_body([*selected, *body[index+1:]], constants, objects, identity, depth + 1)
                if isinstance(obj, (Module, Collection, ModuleMap)):
                    unit = self.a.expression_unit(statement, self.u)
                    obj = replace(obj, evidence=evidence + self.a.evidence(unit, statement.test, 'factory-condition') + obj.evidence)
                return obj
            return None
        return None

    def serial_loop(self, statement, fn):
        """Certify only `for m in collection: x = m(x, invariant_inputs...)`."""
        from .analyzer import text
        if not isinstance(statement, ast.For) or statement.orelse or not isinstance(statement.target, ast.Name) or len(statement.body) != 1:
            return None
        body = statement.body[0]
        if not isinstance(body, ast.Assign) or len(body.targets) != 1 or not isinstance(body.targets[0], ast.Name) or not isinstance(body.value, ast.Call):
            return None
        state, iterator, call = body.targets[0].id, statement.target.id, body.value
        if state == iterator or text(call.func) != iterator:
            return None
        args = [*call.args, *(k.value for k in call.keywords)]
        if any(not isinstance(a, (ast.Name, ast.Constant)) for a in args) or any(k.arg is None for k in call.keywords):
            return None
        if sum(isinstance(a, ast.Name) and a.id == state for a in args) != 1 or any(isinstance(a, ast.Name) and a.id == iterator for a in args):
            return None
        name = text(statement.iter)
        obj = self.get(name)
        if not isinstance(obj, Collection):
            return None
        aliases = {key for key, value in self.objects.items() if value is obj}
        tree = list(self.walk_helpers(fn))
        changed = True
        while changed:
            changed = False
            for n in tree:
                if isinstance(n, ast.Assign) and text(n.value) in aliases:
                    for target in n.targets:
                        if isinstance(target, (ast.Name, ast.Attribute)) and text(target) not in aliases:
                            aliases.add(text(target)); changed = True
        for n in tree:
            if isinstance(n, (ast.Attribute, ast.Subscript)) and isinstance(n.ctx, (ast.Store, ast.Del)) and any(text(n) == alias or text(n).startswith(alias + '.') or text(n).startswith(alias + '[') for alias in aliases):
                return None
            if isinstance(n, ast.Call):
                target = text(n.func)
                if any(target.startswith(alias + '.') for alias in aliases) or any(text(a) in aliases or text(a) == 'self' for a in [*n.args, *(k.value for k in n.keywords)]):
                    return None
        return obj, state, iterator
