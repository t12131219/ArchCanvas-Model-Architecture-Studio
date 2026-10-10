"""Syntactic def/use arrows inside source inspection, separate from tensors.

No sequential edge is inferred merely because two statements are adjacent.
Branches use separate environments; missing expression cards carry their
dependencies through to the next visible consumer. Calls are never executed.
"""
from __future__ import annotations

import ast
import hashlib

MAX_SOURCE_RELATIONS = 1440


def source_dependencies(structure):
    relations = {}

    def link(producers, consumers, unit, expression):
        for producer in sorted(producers):
            for consumer in sorted(consumers):
                if producer == consumer:
                    continue
                key = (producer, consumer)
                if key in relations or len(relations) >= MAX_SOURCE_RELATIONS:
                    continue
                identity = hashlib.sha256(repr(key).encode()).hexdigest()[:24]
                relations[key] = {'id': 'source-relation:' + identity, 'sourceId': producer,
                                  'targetId': consumer, 'kind': 'value-dependency',
                                  'source': structure.analyzer.source(unit, expression)}

    def expression(value, env, unit, parent):
        if value is None:
            return set()
        if isinstance(value, ast.Name):
            return set(env.get(value.id, ()))
        if isinstance(value, ast.Call):
            # Include a method receiver (x.permute), nested calls and named
            # arguments. A self attribute has no variable producer here.
            inputs = expression(value.func, env, unit, parent)
            for arg in [*value.args, *(kw.value for kw in value.keywords)]:
                inputs |= expression(arg, env, unit, parent)
            targets = set(structure.call_nodes.get((parent, id(value)), ()))
            if targets:
                link(inputs, targets, unit, value)
                return targets
            return inputs
        if isinstance(value, ast.NamedExpr):
            result = expression(value.value, env, unit, parent)
            assign(value.target, result, env)
            return result
        result = set()
        for child in ast.iter_child_nodes(value):
            result |= expression(child, env, unit, parent)
        return result

    def assign(target, producers, env):
        if isinstance(target, ast.Name):
            env[target.id] = set(producers)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                assign(item, producers, env)
        # In-place/attribute writes are not resolved as pure variable aliases.

    def merge(environments):
        result = {}
        for env in environments:
            for name, values in env.items():
                result.setdefault(name, set()).update(values)
        return result

    def block(statements, unit, parent, env):
        env = {name: set(values) for name, values in env.items()}
        for statement in statements:
            if isinstance(statement, ast.If):
                condition = structure.condition_scopes.get((parent, id(statement)), parent)
                scopes = structure.branch_scopes.get((condition, id(statement)), ())
                paths = []
                for scope, body in zip(scopes, (statement.body, statement.orelse)):
                    if scope:
                        branch_env, returned = block(body, unit, scope, env)
                        if not returned:
                            paths.append(branch_env)
                if not scopes or any(scope is None for scope in scopes):
                    # Truncated branches can assign unknown values. Forget
                    # their affected bindings instead of drawing stale arrows.
                    for node in ast.walk(statement):
                        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                            env.pop(node.id, None)
                    paths.append(env)
                if not paths:
                    return env, True
                env = merge(paths)
            elif isinstance(statement, (ast.For, ast.While)):
                scope = structure.loop_scopes.get((parent, id(statement)))
                if scope:
                    loop_env = dict(env)
                    if isinstance(statement, ast.For):
                        assign(statement.target, set(), loop_env)
                    loop_env, _ = block(statement.body, unit, scope, loop_env)
                    env = merge([env, loop_env])  # symbolic zero-or-more loop
                for node in ast.walk(statement):
                    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and not scope:
                        env.pop(node.id, None)
            elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                value = statement.value
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                producers = expression(value, env, unit, parent)
                # Evaluate every RHS before binding any LHS (a,b = b,a).
                slots = [expression(rhs, env, unit, parent) for rhs in value.elts] if isinstance(value, (ast.Tuple, ast.List)) else None
                for target in targets:
                    if isinstance(target, (ast.Tuple, ast.List)) and slots is not None and len(target.elts) == len(slots):
                        for item, rhs in zip(target.elts, slots):
                            assign(item, rhs, env)
                    else:
                        assign(target, producers, env)
            elif isinstance(statement, ast.AugAssign):
                # A local update depends on its old value and RHS source.
                producers = expression(statement.target, env, unit, parent) | expression(statement.value, env, unit, parent)
                assign(statement.target, producers, env)
            elif isinstance(statement, ast.Return):
                expression(statement.value, env, unit, parent)
                return env, True
            elif isinstance(statement, ast.Expr):
                expression(statement.value, env, unit, parent)
        return env, False

    for statements, unit, parent in structure.flow_roots:
        block(statements, unit, parent, {})
    # Only the registered Sequential contract declares constructor order as
    # data passing. ModuleList is storage, so it never acquires these arrows.
    for sequence, unit, constructor in structure.sequences:
        for first, second in zip(sequence, sequence[1:]):
            if first and second:
                link({first}, {second}, unit, constructor)
    if len(relations) >= MAX_SOURCE_RELATIONS:
        structure.analyzer.warn('Source dependency inspection reached its relation budget; retained arrows describe source def/use only, not verified tensor bindings.')
    return list(relations.values())
