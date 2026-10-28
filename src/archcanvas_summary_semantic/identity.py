"""Source object selection, separate from invocation and parameter identity.

Only a modeled prefix without unknown effects certifies a constructor binding.
This deliberately does not infer parameter stability or independent allocation.
"""
VERSION = 'source-module-binding/1'


def certify(nodes, edges):
    writes = {e['target'] for e in edges if e['kind'] == 'state-write'}
    barrier = None
    for node in nodes:
        candidate = node.get('module_binding') or node.get('module_resource_binding')
        if candidate:
            candidate.update(rule_version=VERSION, **{'read' if node.get('module_resource') else 'invocation': node['id']},
                             status='unresolved' if barrier else 'proved',
                             scope='constructor binding selected in a modeled effect-free source prefix',
                             parameter_identity='unresolved', allocation_distinctness='not-asserted')
            if barrier:
                candidate['barrier'] = barrier
            else:
                node['module_identity'] = candidate['reference']
        if node['kind'] == 'opaque' or node.get('mutable') or node['id'] in writes or (
                node['kind'] == 'control' and node.get('operator') == 'loop'):
            barrier = barrier or node['id']


def validate(nodes, edges):
    errors, barrier = [], None
    writes = {e['target'] for e in edges if e['kind'] == 'state-write'}
    for n in nodes:
        if n.get('evidence_status') == 'runtime-only' or n['id'].startswith('runtime:'):
            continue
        c = n.get('module_binding') or n.get('module_resource_binding')
        if c:
            valid = (c.get('rule_version') == VERSION and c.get('read' if n.get('module_resource') else 'invocation') == n['id']
                     and c.get('reference') and c.get('construction_evidence')
                     and c.get('parameter_identity') == 'unresolved'
                     and c.get('allocation_distinctness') == 'not-asserted'
                     and c.get('status') == ('unresolved' if barrier else 'proved'))
            if c.get('status') == 'proved':
                valid = valid and n.get('module_identity') == c.get('reference') and not c.get('barrier')
            else:
                valid = valid and c.get('barrier') == barrier
            if not valid:
                errors.append('invalid source module binding: ' + n['id'])
        if n['kind'] == 'opaque' or n.get('mutable') or n['id'] in writes or (
                n['kind'] == 'control' and n.get('operator') == 'loop'):
            barrier = barrier or n['id']
    return errors
