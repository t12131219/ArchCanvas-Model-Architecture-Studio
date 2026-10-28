"""Group observed trace structure, and associate unambiguous module roles.

Neither association proves operator equivalence nor grouping proves equal tensor
values. Original run/call/event IDs and differing execution variants survive.
"""
from collections import defaultdict
from .schema import digest


def index_observations(ir, receipt):
    static = defaultdict(list)
    aliases = defaultdict(list)
    for n in ir['nodes']:
        if n['id'].startswith('runtime:') or n['id'] == 'runtime-observations':
            continue
        cls = n.get('source_class') or n.get('framework_type', '').split('.')[-1]
        if cls and 'module_path' in n:
            static[n['module_path'], cls].append(n['id'])
            if n.get('module_identity'):
                aliases[n['module_identity'], cls].append(n['id'])
    # A shared object can be registered under several paths, whereas hooks
    # report one canonical path. That path alone cannot identify the invocation.
    by = {n['id']: n for n in ir['nodes']}
    for key, ids in static.items():
        static[key] = list(dict.fromkeys(member for identity in ids for member in
            (aliases.get((by[identity].get('module_identity'), key[1])) or [identity])))
    associations, unresolved, variants = {}, [], {}
    for index, run in enumerate(receipt.get('runs', [])):
        prefix = f'runtime:{index}:'
        nodes = [n for n in ir['nodes'] if n['id'].startswith(prefix)]
        normal = lambda identity: identity.removeprefix(prefix)
        node_ids = {n['id'] for n in nodes}
        tensors = lambda values: [{k: t.get(k) for k in ('producer', 'slot', 'dtype')} for t in values]
        shape = {'mode': run['mode'], 'status': run['status'], 'truncated': bool(run.get('truncated')),
                 'branches': run.get('branches', []),
                 'nodes': [{'id': normal(n['id']), 'kind': n['kind'], 'parent': normal(n.get('parent') or ''),
                            'operator': n.get('operator'), 'module_path': n.get('module_path'), 'type': n.get('framework_type'),
                            'mutable': n.get('mutable'), 'source': n.get('source'),
                            'aliases': n.get('aliases'), 'role': n.get('role'),
                            'inputs': tensors(n.get('inputs', [])), 'outputs': tensors(n.get('outputs', []))}
                           for n in nodes if n['id'] != prefix + 'run'],
                 'edges': [{**{k: v for k, v in e.items() if k != 'id'}, 'source': normal(e['source']), 'target': normal(e['target'])}
                           for e in ir['edges'] if e['source'] in node_ids and e['target'] in node_ids]}
        signature = digest(shape)
        group = variants.setdefault(signature, {'id': 'observed-variant:' + signature[:16], 'normal_form_digest': signature,
                    'representative': prefix + 'run', 'runs': [], 'node_correspondences': [],
                    'scope': 'same recorded hierarchy, operators, source locations, tensor dtypes, slots, branches and mode',
                    'not_asserted': ['equal tensor values or shapes', 'unrecorded scalar argument equivalence', 'unobserved behavior'],
                    'complete_trace': run['status'] == 'passed' and not run.get('truncated')})
        group['runs'].append({'node': prefix + 'run', 'run': index, 'case': run['case'], 'mode': run['mode']})
        group['node_correspondences'].append({'run': index, 'mapping': {n['id']: group['representative'].removesuffix('run') + normal(n['id']) for n in nodes}})
        stack = []
        for event in run.get('module_events', []):
            if event['event'] == 'enter':
                key = event['path'], event.get('module_type', '').split('.')[-1]
                candidates = static.get(key, [])
                observation = {'run': index, 'case': run['case'], 'mode': run['mode'], 'call': prefix + event['id'],
                               'path': event['path'], 'module_type': event.get('module_type'),
                               'inputs': [{k: t.get(k) for k in ('shape', 'dtype', 'producer', 'slot')} for t in event.get('inputs', [])]}
                if len(candidates) == 1:
                    identity = candidates[0]
                    entry = associations.setdefault(identity, {'node': identity, 'path': event['path'], 'observations': [],
                        'basis': 'unique static module path and class in the same source generation and constructor configuration',
                        'not_asserted': ['operator equivalence', 'equal values across runs', 'unobserved branch coverage']})
                    entry['observations'].append(observation)
                else:
                    unresolved.append({**observation, 'reason': 'ambiguous-static-invocation' if candidates else 'static-module-role-unresolved', 'candidates': candidates})
                stack.append(observation)
            elif stack and event['event'] == 'exit':
                current = stack.pop()
                if current['path'] == event['path']:
                    current['outputs'] = [{k: t.get(k) for k in ('shape', 'dtype', 'producer', 'slot')} for t in event.get('outputs', [])]
    ir['observation_index'] = {'schema': 'archcanvas-observation-index/1', 'receipt_digest': receipt.get('trace_digest'),
        'module_associations': list(associations.values()), 'unmatched_calls': unresolved, 'trace_groups': list(variants.values()),
        'source_binding': receipt.get('binding'), 'constructor': receipt.get('input_spec', {}).get('constructor', {})}
    return ir
