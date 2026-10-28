"""Bind complete observed module-call regions to source call expressions.

This proves where a recorded invocation belongs and how its tensor arguments
and return connect in that run. It does not certify the implementation for
unobserved inputs, or identify an arbitrary ATen event by a source line alone.
"""
import ast
from pathlib import Path
from .schema import digest, seal, source_graph_digest, validate_ir


VERSION = 'source-runtime-integration/1'


def build_index(ir):
    receipt = ir.get('runtime', {})
    binding = receipt.get('binding', {})
    root = Path(binding.get('source_root', '/'))
    static = [n for n in ir['nodes'] if not n['id'].startswith('runtime:') and n['id'] != 'runtime-observations']
    by = {n['id']: n for n in ir['nodes']}
    source_files = {s['file'] for n in static for s in n.get('source', [])}
    generations = {str(root / p): sha for p, sha in binding.get('source_generation', {}).items()}
    source_ok = (bool(receipt.get('runs')) and receipt.get('source_unchanged') is True
                 and receipt.get('isolation', {}).get('status') == 'passed'
                 and binding.get('spec_digest') == digest(receipt.get('input_spec', {}))
                 and receipt.get('input_spec', {}).get('constructor', {}) == ir['entry'].get('constructor', {})
                 and all(generations.get(s['physical']) == s['sha256'] for s in ir['sources'] if s['path'] in source_files))
    index = {'schema': VERSION, 'receipt_digest': receipt.get('trace_digest'),
             'source_graph_digest': source_graph_digest(ir), 'regions': [], 'unplaced': [],
             'scope': 'one selected recorded invocation; source topology and unobserved branches retained',
             'not_asserted': ['operator equivalence for arbitrary inputs', 'complete unknown-module resolution']}
    if not source_ok:
        index['unplaced'].append({'reason': 'runtime/source generation or execution integrity unavailable'})
        return index
    operations = [n for n in static if n['kind'] in {'compute', 'opaque'}]
    incoming = {}
    for edge in ir['edges']:
        incoming.setdefault(edge['target'], []).append(edge)

    def is_call(node):
        for location in node.get('source', []):
            try:
                if isinstance(ast.parse(location.get('expression', ''), mode='eval').body, ast.Call):
                    return True
            except (ValueError, SyntaxError):
                pass
        return False

    def candidates(site, exact=True):
        if not site:
            return []
        file = str(root / site['file'])
        rows = []
        for node in operations:
            for s in node.get('source', []):
                if s['file'] != file or s.get('symbol') != site.get('symbol'):
                    continue
                if exact:
                    matched = all(s.get(k) == site.get(k) for k in ('line', 'end_line', 'column', 'end_column'))
                else:
                    matched = s['line'] <= site['line'] <= s['end_line']
                if matched:
                    rows.append(node);break
        return rows

    for ri, run in enumerate(receipt.get('runs', [])):
        prefix = f'runtime:{ri}:'
        if run.get('status') != 'passed' or run.get('truncated') or not run.get('replay', {}).get('matched'):
            index['unplaced'].append({'run': ri, 'reason': 'incomplete or failed run'})
            continue
        calls, exits, stack = {}, {}, []
        for e in run.get('module_events', []):
            if e['event'] == 'enter':
                calls[e['id']] = e;stack.append(e['id'])
            elif stack:
                identity = stack.pop()
                if calls[identity]['path'] == e['path']:
                    exits[identity] = e
        for identity, call in calls.items():
            if not call.get('parent_call') or identity not in exits:
                continue
            descendants = {identity}
            for _ in range(len(calls)):
                added = {c for c, v in calls.items() if v.get('parent_call') in descendants}
                if added <= descendants:break
                descendants.update(added)
            events = [e for e in run.get('events', []) if e.get('module_call') in descendants]
            if not events or any(e.get('mutable') for e in events):
                continue
            matches, basis = [], None
            # Python 3.11+ frame positions distinguish two calls on one line.
            for site in call.get('source_stack', []):
                rows = candidates(site)
                if len(rows) == 1 and is_call(rows[0]):
                    matches=rows;basis='unique source call span from module invocation stack';break
                if rows:break
            # Legacy receipts: accept a complete module invocation only when
            # every event belongs to the sole source operation on its line.
            # Never use the previous many-to-many line associations as a proof.
            if not matches and not call.get('source_stack'):
                rows = [candidates(e.get('source'), exact=False) for e in events]
                if rows and all(len(row) == 1 and row[0]['id'] == rows[0][0]['id'] for row in rows):
                    matches = rows[0]
                    if is_call(matches[0]):basis='complete module invocation at the sole recorded source operation on its line'
                    else:matches=[]
            if len(matches) != 1:
                index['unplaced'].append({'run': ri, 'call': prefix+identity, 'reason': 'ambiguous or missing source call location'})
                continue
            source = matches[0]
            if source['kind'] != 'opaque':
                # Known static operations stay in place, without duplicate
                # runtime implementations in the normal source architecture.
                continue
            if any(e['source_port'] != 'out' or e['kind'] not in {'data', 'alias', 'interface-binding'} for e in ir['edges'] if e['source'] == source['id']):
                continue
            output = exits[identity].get('outputs', [])
            event_ids = {e['id'] for e in events}
            if len(output) != 1 or output[0].get('producer') not in event_ids or (
                    exits[identity].get('output_is_tensor') is not True):
                index['unplaced'].append({'run': ri, 'call': prefix+identity, 'reason': 'structured, aliased or unresolved return requires an explicit boundary'})
                continue
            producer = next(e for e in events if e['id'] == output[0]['producer'])
            if not any(t['id'] == output[0]['id'] and str(t.get('slot')) == str(output[0].get('slot')) for t in producer.get('outputs', [])):
                continue
            tensors = call.get('input_bindings')
            if tensors is None:
                # Original hooks only observed positional tensor args. A single
                # positional source argument and one tensor are unambiguous.
                actuals = source.get('arguments', {})
                tensors = [{'port': 'arg:0', **call['inputs'][0]}] if len(actuals.get('args', [])) == 1 and not actuals.get('kwargs') and len(call.get('inputs', [])) == 1 else []
            ports = {e['target_port']: e for e in incoming.get(source['id'], []) if e['kind'] == 'data'}
            bridges, resources, failures = [], set(), []
            runtime_edges = [e for e in ir['edges'] if e['id'].startswith('rt-edge:') and e['target'] in {prefix+v for v in event_ids}]
            for edge in runtime_edges:
                if edge['source'] in {prefix+v for v in event_ids}:
                    continue
                raw = by[edge['source']]
                if raw['kind'] in {'parameter', 'buffer'}:
                    resources.add(raw['id']);continue
                ev = next(e for e in events if prefix+e['id'] == edge['target'])
                t = ev['inputs'][int(edge['target_port'])]
                bound = [v for v in tensors if v.get('id') == t['id'] and v.get('port') in ports and not v.get('component')]
                if len(bound) != 1 or ports[bound[0]['port']].get('condition'):
                    failures.append(edge['id']);continue
                bridges.append({'source_edge': ports[bound[0]['port']]['id'], 'runtime_edge': edge['id'],
                                'tensor': t['id'], 'argument_port': bound[0]['port'],
                                'target': edge['target'], 'target_port': edge['target_port']})
            # One static operand cannot be replaced with several observed uses
            # without a dedicated input junction. Keep that boundary for now.
            if failures or len({v['source_edge'] for v in bridges}) != len(bridges):
                index['unplaced'].append({'run': ri, 'call': prefix+identity, 'reason': 'input operand or tensor-use binding is ambiguous'})
                continue
            index['regions'].append({'source': source['id'], 'run': ri, 'case': run['case'], 'mode': run['mode'],
                'call': prefix+identity, 'module_type': call.get('module_type'), 'module_path': call['path'],
                'events': [prefix+e['id'] for e in events], 'calls': sorted(prefix+c for c in descendants if c != identity),
                'resources': sorted(resources), 'inputs': bridges,
                'output': {'source': prefix+output[0]['producer'], 'source_port': str(output[0].get('slot', 'out')), 'tensor': output[0]['id']},
                'basis': basis, 'static_unknown_preserved': True})
    return index


def attach_index(ir):
    """Upgrade an existing receipt without executing or rereading the model."""
    if not validate_ir(ir)['ok']:
        raise ValueError('需要有效的源码与运行凭据 IR')
    ir['source_runtime_index'] = build_index(ir)
    return seal(ir)
