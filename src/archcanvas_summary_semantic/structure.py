"""Compare modeled local graphs, never source class/constructor signatures.

This is a structural correspondence, not execution or numerical equivalence.
Unknown effects, incomplete values and unsupported cycles prevent comparison.
"""
from __future__ import annotations
import ast
from .schema import digest

VERSION = 'local-structure/1'
FLOW = {'data', 'alias', 'interface-binding'}


def syntax(node):
    """Keep literal/operator syntax that has no value edge in source lowering.

Dynamic subexpressions have their own nodes/ports. Their spelling is not a
structural identity. Call targets are separately resolved in framework facts.
"""
    def form(value, path, root=False):
        if isinstance(value, ast.Constant):
            return {'literal_type': type(value.value).__name__, 'literal': repr(value.value)}
        if isinstance(value, ast.UnaryOp) and isinstance(value.operand, ast.Constant):
            return {'literal_expression': ast.dump(value, include_attributes=False)}
        if isinstance(value, ast.expr) and not root and not isinstance(value, ast.Slice):
            return {'operand': path}
        if isinstance(value, ast.AST):
            return {'type': type(value).__name__, 'fields': {
                field: form(child, path + '.' + field)
                for field, child in ast.iter_fields(value)
                if field != 'ctx' and not (isinstance(value, ast.Call) and field == 'func')}}
        if isinstance(value, list):
            return [form(child, path + ':' + str(i)) for i, child in enumerate(value)]
        return value
    return form(node, '', root=True)


def compare_instances(nodes, edges, sequence):
    """Return exact, ordered local DAG correspondences and explicit unknowns.

Transparent interfaces/wrappers do not select the comparison. Every compute
operation (including disconnected work), operand slot, configuration, literal,
condition, parameter-read and external boundary is accounted for.
"""
    by = {n['id']: n for n in nodes}
    from .symbolic_values import derive, value_for, exception_for
    symbolic = derive(nodes, edges)
    symbolic = {i: c for i, c in symbolic.items() if by[i].get('symbolic_value') == c}
    children, incoming, outgoing = {}, {}, {}
    for n in nodes:
        children.setdefault(n.get('parent'), []).append(n['id'])
    for e in edges:
        incoming.setdefault(e['target'], []).append(e)
        outgoing.setdefault(e['source'], []).append(e)

    def closure(root):
        result, todo = set(), [root]
        while todo:
            at = todo.pop()
            if at in result: continue
            result.add(at); todo.extend(children.get(at, []))
        return result

    def clean_literal(value):
        if isinstance(value, dict):
            if 'unresolved' in value: raise ValueError('unresolved configuration')
            return {k: clean_literal(v) for k, v in value.items()}
        if isinstance(value, list): return [clean_literal(v) for v in value]
        return value

    def instance(root):
        members = closure(root)
        atoms = [n for n in nodes if n['id'] in members and (n['kind'] not in {'composite', 'interface', 'value-alias'}
                 or n.get('return_selection') or n.get('source_constant_input'))]
        for n in nodes:
            if n['id'] not in members: continue
            if n['kind'] == 'opaque' or n.get('mutable'):
                raise ValueError('unknown or mutable computation')
            if n['kind'] == 'control' and n.get('operator') not in {'if', 'if-expression'} and exception_for(n) is None:
                raise ValueError('unsupported control or nested iteration')
            if exception_for(n):
                dynamic = {str(i) for i, a in enumerate(n['exception_signature']['syntax']['fields']['args']) if 'operand' in a}
                actual = {e.get('target_port') for e in incoming.get(n['id'], []) if e['kind'] == 'control'}
                if not dynamic <= actual: raise ValueError('incomplete exceptional operand binding')
            if n['kind'] == 'value-alias' and n.get('operator') not in {None, 'phi'}:
                raise ValueError('unresolved value binding')
            if n['kind'] in {'state', 'buffer'}:
                clean_literal(value_for(n, symbolic) if n['id'] in symbolic else n.get('value', {'unresolved': True}))
        if any(e['kind'] == 'state-write' and (e['source'] in members or e['target'] in members) for e in edges):
            raise ValueError('state write')
        # Conditional merges are operations; plain aliases/interfaces are not.
        atoms += [n for n in nodes if n['id'] in members and n['kind'] == 'value-alias' and n.get('operator') == 'phi']
        atom_ids = {n['id'] for n in atoms}
        local, external, objects, records, mapping, active = {}, {}, {}, [], {}, set()

        def resolve(at, port='out', seen=None):
            seen = set() if seen is None else seen
            if (at, port) in seen: raise ValueError('cyclic transparent binding')
            seen.add((at, port))
            if at not in members:
                key = (at, port)
                if key not in external: external[key] = len(external)
                return ['external', external[key]]
            n = by[at]
            es = [e for e in incoming.get(at, []) if e['kind'] in FLOW]
            if n['kind'] in {'interface', 'value-alias'} and not n.get('operator') and len(es) == 1 and not es[0].get('condition'):
                e = es[0]
                if n['kind'] == 'value-alias' and n.get('slot') is not None and str(n['slot']) != str(e.get('source_port')):
                    raise ValueError('unresolved extraction slot')
                outer = e.get('source_port', 'out')
                slot = port if outer == 'out' else outer if port == 'out' else outer + '.' + port
                return resolve(e['source'], slot, seen)
            if at not in atom_ids: raise ValueError('incomplete interface binding')
            return ['local', visit(at), port]

        def condition(c):
            return None if not c else {'branch': resolve(c['branch']), 'outcome': c['outcome']}

        def arguments(n):
            result = {}
            ports = {e.get('target_port') for e in incoming.get(n['id'], []) if e['kind'] in FLOW}
            for kind, values in n.get('arguments', {}).items():
                pairs = enumerate(values) if isinstance(values, list) else values.items()
                result[kind] = {str(k): {'binding': ('arg:' if kind == 'args' else 'kw:') + str(k)}
                               if ('arg:' if kind == 'args' else 'kw:') + str(k) in ports else clean_literal(v)
                               for k, v in pairs}
            return result

        def visit(at):
            if at in local: return local[at]
            if at in active: raise ValueError('cyclic local graph')
            active.add(at); n = by[at]
            # Preserve framework identity. Tensor method receiver spelling may
            # change, but the operation and explicit receiver edge remain.
            target = n.get('function_target')
            if target and not target.startswith(('torch.', 'math.')):
                scalar = n.get('operator') == 'scalar-cast' and n.get('source_scalar_cast') == target and target in {'float', 'int', 'bool'}
                if not scalar and not any(e.get('target_port') == 'receiver' for e in incoming.get(at, [])):
                    raise ValueError('unresolved function identity')
                if not scalar: target = 'receiver.' + target.rsplit('.', 1)[-1]
            if n['kind'] == 'compute' and not n.get('syntax'):
                raise ValueError('missing literal/operator syntax')
            descriptor = {'kind': n['kind'], 'operator': n.get('operator'),
                          'framework_type': n.get('framework_type'), 'function': target,
                          'constructor': clean_literal(n.get('constructor')),
                          'arguments': arguments(n), 'syntax': n.get('syntax'),
                          'value': clean_literal(value_for(n, symbolic)), 'structure_kind': n.get('structure_kind')}
            if n.get('operator') == 'exception-exit':
                descriptor['exception_exit'] = exception_for(n)
            if n.get('source_constant_input'):
                if n.get('role') != 'input' or incoming.get(at): raise ValueError('invalid invocation constant')
                descriptor['invocation_constant'] = clean_literal(n['source_constant_input'])
            if n.get('return_selection'):
                c = n['return_selection']
                choices = [e for e in incoming.get(at, []) if e['source'] == c['selected'] and e['kind'] == 'interface-binding']
                if len(choices) != 1: raise ValueError('invalid normal return selection')
                inputs = [v for v in nodes if v.get('parent') == n['parent'] and v['kind'] == 'interface' and v.get('role') == 'input']
                constants = {str(i): c['call_constants'][v['slot']] for i, v in enumerate(inputs) if v.get('slot') in c['call_constants']}
                descriptor['normal_returns'] = {'constants': clean_literal(constants),
                    'selected_input': choices[0].get('target_port', 'in'), 'scope': c['scope']}
            if n.get('module_resource'):
                descriptor['resource_type'] = n['resource_framework_type']
                descriptor['resource_constructor'] = clean_literal(n['resource_constructor'])
            if (n.get('framework_type') and n['kind'] == 'compute') or n.get('module_resource'):
                binding = n.get('module_binding') or n.get('module_resource_binding', {})
                if binding.get('status') != 'proved' or binding.get('reference') != n.get('module_identity'):
                    raise ValueError('module selection correspondence unresolved')
                reference = binding['reference']
                if reference not in objects: objects[reference] = len(objects)
                descriptor['object_selection'] = objects[reference]
            scopes, parent = [], n.get('parent')
            while parent in members:
                c = by[parent].get('condition')
                if c: scopes.append(condition(c))
                parent = by[parent].get('parent')
            bindings = [{'kind': 'value' if e['kind'] in FLOW else e['kind'], 'port': e.get('target_port', 'in'),
                         'source': resolve(e['source'], e.get('source_port', 'out')),
                         'condition': condition(e.get('condition'))}
                        for e in sorted(incoming.get(at, []), key=lambda e: (e['kind'], e.get('target_port', 'in')))]
            record = {'operation': descriptor, 'bindings': bindings, 'conditions': scopes}
            local[at] = len(records); records.append(record); mapping[at] = local[at]
            active.remove(at); return local[at]

        # Source order is intentionally retained for otherwise disconnected
        # work. We do not prove reordered effects or arbitrary DAG equivalence.
        for n in atoms: visit(n['id'])
        boundary = []
        for e in edges:
            if e['source'] in members and e['target'] not in members:
                boundary.append({'source': resolve(e['source'], e.get('source_port', 'out')),
                                 'kind': 'value' if e['kind'] in FLOW else e['kind'], 'condition': condition(e.get('condition'))})
        if not records: raise ValueError('no modeled operations')
        structure = {'operations': records, 'outputs': boundary, 'inputs': len(external)}
        return {'status': 'proved', 'fingerprint': digest(structure), 'structure': structure,
                'node_mapping': mapping, 'boundary_edges': [e['id'] for e in edges
                    if (e['source'] in members) != (e['target'] in members)],
                'members': [n['id'] for n in nodes if n['id'] in members]}

    instances = [by[i] for i in children.get(sequence['id'], []) if by[i].get('semantic_type') == 'repeat-instance']
    rows, groups = [], []
    for n in instances:
        try: row = instance(n['id'])
        except ValueError as error: row = {'status': 'unresolved', 'reason': str(error)}
        row.update(instance=n['id'], index=n['repeat_index']); rows.append(row)
        # Unresolved elements always retain their own representative.
        group = next((g for g in groups if row['status'] == 'proved' and g.get('fingerprint') == row['fingerprint']), None)
        if group is None:
            group = {'representative': n['id'], 'indices': [], 'instances': [],
                     'status': row['status'], 'fingerprint': row.get('fingerprint')}; groups.append(group)
        group['indices'].append(n['repeat_index']); group['instances'].append(n['id'])
    return {'rule_version': VERSION, 'scope': 'modeled source graph and exact boundary slots; ordered operations',
            'instances': rows, 'groups': groups,
            'homogeneous': bool(rows) and all(r['status'] == 'proved' for r in rows) and len(groups) == 1,
            'not_asserted': ['numerical equivalence', 'parameter equality or stability', 'purity',
                             'runtime count', 'time axis', 'arbitrary graph isomorphism']}


def certify(nodes, edges):
    for n in nodes:
        if not n.get('repeat_contract'): continue
        comparison = compare_instances(nodes, edges, n)
        n['repeat_contract']['structure'] = comparison
        n['repeat_contract']['homogeneous'] = comparison['homogeneous']
        n['label'] = ('Repeated block × ' if comparison['homogeneous'] else 'Serial sequence · ') + str(n['repeat_contract']['count'])


def validate(nodes, edges):
    errors = []
    for n in nodes:
        c = n.get('repeat_contract', {})
        if 'structure' not in c: continue  # legacy IR has no structural proof
        instances = [a for a in nodes if a.get('parent') == n['id'] and a.get('semantic_type') == 'repeat-instance']
        cardinality = (c.get('count') == len(instances) == len(c.get('instances', []))
                       and [a.get('repeat_index') for a in instances] == list(range(len(instances)))
                       and [a.get('module_identity') for a in instances] == c.get('instances'))
        if not cardinality or c['structure'] != compare_instances(nodes, edges, n) or c['homogeneous'] != c['structure']['homogeneous']:
            errors.append('invalid local structure correspondence: ' + n['id'])
    return errors
