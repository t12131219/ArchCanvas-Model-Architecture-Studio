"""Bounded, nonexecuting source def/use, including call and region interfaces.

Source arrows remain separate from tensor bindings. Structured values preserve
argument/return slots; aliases, branches and calls never imply statement-order
edges. Boundary evidence refers back to the unchanged conservative graph.
"""
from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass, replace

MAX_SOURCE_RELATIONS = 1440
MAX_FLOW_STEPS = 100_000


@dataclass(frozen=True)
class Trace:
    node: str
    boundaries: frozenset[str] = frozenset()
    edges: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Value:
    producers: frozenset[Trace] = frozenset()
    slots: tuple | None = None
    complete: bool = True


def joined(values):
    values = list(values)
    slots = None
    if values and all(value.slots is not None for value in values):
        keys = tuple(key for key, _ in values[0].slots)
        if all(tuple(key for key, _ in value.slots) == keys for value in values):
            slots = tuple((key, joined(dict(value.slots)[key] for value in values)) for key in keys)
    return Value(frozenset(p for value in values for p in value.producers), slots,
                 all(value.complete for value in values))


def structured(items):
    items = tuple(items)
    return replace(joined(value for _, value in items), slots=items)


EMPTY = Value()
UNKNOWN = Value(complete=False)


def source_dependencies(structure):
    analyzer = structure.analyzer
    facts = {node['id']: node for node in analyzer.nodes}
    roots = {parent: (statements, unit) for statements, unit, parent in structure.flow_roots}
    sequences = {owner: (children, unit, constructor) for owner, children, unit, constructor in structure.sequences}
    regions = {region['id']: (statement, spec, inputs) for region, statement, spec, inputs in structure.regions}
    relations, summaries, active = {}, {}, set()
    incomplete = set()
    steps = 0

    def marked(value, boundaries, edges):
        def mark(item):
            return Value(frozenset(Trace(p.node, p.boundaries | frozenset(boundaries), p.edges | frozenset(edges)) for p in item.producers),
                         tuple((key, mark(child)) for key, child in item.slots) if item.slots is not None else None, item.complete)
        return mark(value)

    def link(value, targets, unit, expression):
        for producer in sorted(value.producers, key=lambda p: (p.node, sorted(p.boundaries), sorted(p.edges))):
            for target in sorted(targets):
                if producer.node == target:
                    continue
                key = (producer.node, target, tuple(sorted(producer.boundaries)), tuple(sorted(producer.edges)))
                if key in relations or len(relations) >= MAX_SOURCE_RELATIONS:
                    continue
                boundary = ({'boundary': {'nodeIds': sorted(producer.boundaries), 'edgeIds': sorted(producer.edges), 'complete': value.complete}}
                            if producer.boundaries and producer.edges else {})
                identity = hashlib.sha256(repr(key).encode()).hexdigest()[:24]
                relations[key] = {'id': 'source-relation:' + identity, 'sourceId': producer.node,
                                  'targetId': target, 'kind': 'boundary-dependency' if boundary else 'value-dependency',
                                  'source': analyzer.source(unit, expression), **boundary}

    def invoke(target, args, keywords, unit, expression, stack):
        if target in stack or len(stack) >= 12:
            return Value(frozenset({Trace(target)}), complete=False)
        if target in sequences:
            children, seq_unit, constructor = sequences[target]
            if len(args) != 1 or keywords or any(child is None for child in children):
                return Value(frozenset({Trace(target)}), complete=False)
            result = args[0]
            for child in children:
                result = invoke(child, [result], {}, seq_unit, constructor, (*stack, target))
            return result
        function = structure.flow_functions.get(target)
        if function:
            # bind_static handles positional/keyword/default names without
            # importing source. Defaults with no supplied value carry no
            # caller dependency; unsupported signatures keep the boundary.
            bound = analyzer.bind_static(function, args, keywords, {}, method=True)
            if bound is None:
                return Value(frozenset({Trace(target)}), complete=False)
            env = {name: value if isinstance(value, Value) else EMPTY for name, value in bound.items()}
            body, own_unit = roots[target]
            _, falls, returned = block(body, own_unit, target, env, (*stack, target))
            if falls or not returned.complete:
                return replace(joined([returned, Value(frozenset({Trace(target)}), complete=False)]), complete=False)
            return returned
        inputs = joined([*args, *keywords.values()])
        link(inputs, {target}, unit, expression)
        return Value(frozenset({Trace(target)}), complete=inputs.complete)

    def expression(value, env, unit, parent, stack):
        nonlocal steps
        steps += 1
        if steps > MAX_FLOW_STEPS:
            return UNKNOWN
        if value is None:
            return EMPTY
        if isinstance(value, ast.Name):
            return env.get(value.id, EMPTY)
        if isinstance(value, (ast.Tuple, ast.List)):
            return structured((i, expression(item, env, unit, parent, stack)) for i, item in enumerate(value.elts))
        if isinstance(value, ast.Dict) and all(isinstance(key, ast.Constant) for key in value.keys):
            return structured((key.value, expression(item, env, unit, parent, stack)) for key, item in zip(value.keys, value.values))
        if isinstance(value, ast.Subscript):
            owner = expression(value.value, env, unit, parent, stack)
            if owner.slots is not None and isinstance(value.slice, ast.Constant):
                slots = dict(owner.slots)
                key = value.slice.value
                if isinstance(key, (str, int, float, bool, type(None))):
                    return slots.get(key, UNKNOWN)
            return joined([owner, expression(value.slice, env, unit, parent, stack)])
        if isinstance(value, ast.Call):
            args = [expression(arg, env, unit, parent, stack) for arg in value.args]
            keywords = {kw.arg: expression(kw.value, env, unit, parent, stack) for kw in value.keywords}
            receiver = expression(value.func, env, unit, parent, stack)
            targets = structure.call_nodes.get((parent, id(value)), ())
            if targets:
                if any(isinstance(arg, ast.Starred) for arg in value.args) or None in keywords:
                    return Value(frozenset(Trace(target) for target in targets), complete=False)
                return joined(invoke(target, args, keywords, unit, value, stack) if target in structure.flow_functions or target in sequences
                              else invoke(target, [receiver, *args], keywords, unit, value, stack) for target in targets)
            # Missing/truncated call cards must not turn into a fabricated
            # direct pass-through relation around the omitted operation.
            return UNKNOWN
        if isinstance(value, ast.NamedExpr):
            result = expression(value.value, env, unit, parent, stack)
            assign(value.target, result, env)
            return result
        return joined(expression(child, env, unit, parent, stack) for child in ast.iter_child_nodes(value))

    def assign(target, value, env):
        if isinstance(target, ast.Name):
            env[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            slots = dict(value.slots) if value.slots is not None else {}
            for i, item in enumerate(target.elts):
                assign(item, slots.get(i, UNKNOWN), env)

    def merge(environments):
        names = set().union(*(env.keys() for env in environments))
        return {name: joined(env.get(name, UNKNOWN) for env in environments) for name in names}

    def block(statements, unit, parent, env, stack=()):
        env, returns = dict(env), []
        for statement in statements:
            if steps > MAX_FLOW_STEPS:
                return {name: UNKNOWN for name in env}, True, UNKNOWN
            if isinstance(statement, ast.If):
                condition = structure.condition_scopes.get((parent, id(statement)), parent)
                scopes = structure.branch_scopes.get((condition, id(statement)), (None, None))
                paths = []
                for scope, body in zip(scopes, (statement.body, statement.orelse)):
                    if scope:
                        branch_env, falls, returned = block(body, unit, scope, env, stack)
                        if not falls or returned.producers or returned.slots is not None or not returned.complete:
                            returns.append(returned)
                        if falls:
                            paths.append(branch_env)
                    else:
                        forgotten = dict(env)
                        for node in ast.walk(statement):
                            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                                forgotten[node.id] = UNKNOWN
                        paths.append(forgotten)
                        returns.append(UNKNOWN)
                if not paths:
                    return env, False, joined(returns)
                env = merge(paths)
            elif isinstance(statement, (ast.For, ast.While)):
                scope = structure.loop_scopes.get((parent, id(statement)))
                if scope:
                    loop_env = dict(env)
                    if isinstance(statement, ast.For):
                        assign(statement.target, EMPTY, loop_env)
                    loop_env, _, returned = block(statement.body, unit, scope, loop_env, stack)
                    returns.append(returned)
                    env = merge([env, loop_env])
                else:
                    for node in ast.walk(statement):
                        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                            env[node.id] = UNKNOWN
            elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                value = expression(statement.value, env, unit, parent, stack)
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                for target in targets:
                    assign(target, value, env)
            elif isinstance(statement, ast.AugAssign):
                assign(statement.target, joined([expression(statement.target, env, unit, parent, stack), expression(statement.value, env, unit, parent, stack)]), env)
            elif isinstance(statement, ast.Return):
                returns.append(expression(statement.value, env, unit, parent, stack))
                return env, False, joined(returns)
            elif isinstance(statement, ast.Expr):
                expression(statement.value, env, unit, parent, stack)
        return env, True, joined(returns)

    def ref_value(value):
        if hasattr(value, 'node') and hasattr(value, 'source_slot'):
            if value.source_slot is not None and value.node in regions:
                env, falls, returned = region_summary(value.node)
                result = returned if value.source_slot == '$return' else env.get(value.source_slot, UNKNOWN)
                if value.source_slot == '$return' and falls:
                    result = replace(result, complete=False)
                return marked(result, [value.node], [])
            return Value(frozenset({Trace(value.node)}))
        if isinstance(value, (tuple, list)):
            return structured((i, ref_value(item)) for i, item in enumerate(value))
        if isinstance(value, dict):
            return structured((key, ref_value(item)) for key, item in value.items())
        return EMPTY

    def region_summary(identity):
        if identity in summaries:
            return summaries[identity]
        if identity in active:
            return {}, True, UNKNOWN
        active.add(identity)
        statement, spec, inputs = regions[identity]
        env = {}
        for name, value in inputs.items():
            # bind() flattens structured input refs into named port ordinals.
            # Retain that exact correspondence, rather than attributing every
            # tuple input edge to whichever tuple slot happens to be consumed.
            ordinal = 0
            def input_value(item):
                nonlocal ordinal
                if hasattr(item, 'node'):
                    port_name = name if ordinal == 0 else f'{name}.{ordinal}'
                    ordinal += 1
                    edge_ids = [edge['id'] for edge in analyzer.edges if edge['target']['nodeId'] == identity
                                and edge['source'] == {'nodeId': item.node, 'portId': item.port}
                                and any(port['id'] == edge['target']['portId'] and port['name'] == port_name for port in facts[identity]['ports'])]
                    return marked(ref_value(item), [identity], edge_ids)
                if isinstance(item, (tuple, list)):
                    return structured((i, input_value(child)) for i, child in enumerate(item))
                if isinstance(item, dict):
                    return structured((key, input_value(child)) for key, child in item.items())
                return EMPTY
            env[name] = input_value(value)
        summaries[identity] = block([statement], spec.unit, identity, env)
        active.remove(identity)
        if any(not value.complete for value in summaries[identity][0].values()) or not summaries[identity][2].complete:
            incomplete.add(identity)
        return summaries[identity]

    # First recover all called source definitions, including internal relations
    # in definitions not reached by a resolved data input.
    for statements, unit, parent in structure.flow_roots:
        if parent not in regions:
            block(statements, unit, parent, {})
    for owner, (children, unit, constructor) in sequences.items():
        invoke(owner, [EMPTY], {}, unit, constructor, ())
    for identity in regions:
        region_summary(identity)
    for value, edge in analyzer.source_uses:
        # Container plumbing isn't an atomic consumer. A following inspected
        # region composes its own named input with this exact named exit.
        target = facts[edge['target']['nodeId']]
        if target['id'] in regions or (target['category'] == 'container' and target['children']):
            continue
        statement, spec, _ = regions[value.node]
        result = marked(ref_value(value), [value.node], [edge['id']])
        link(result, {target['id']}, spec.unit, statement)
    for relation in relations.values():
        if 'boundary' in relation and (incomplete.intersection(relation['boundary']['nodeIds']) or steps > MAX_FLOW_STEPS):
            relation['boundary']['complete'] = False
    if len(relations) >= MAX_SOURCE_RELATIONS or steps > MAX_FLOW_STEPS:
        analyzer.warn('Source dependency inspection reached its bounded relation/work budget; retained arrows describe source def/use only, not verified tensor bindings.')
        for relation in relations.values():
            if 'boundary' in relation:
                relation['boundary']['complete'] = False
    return list(relations.values())
