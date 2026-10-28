"""Attach runtime evidence without erasing source facts or claiming all-input proof."""
from pathlib import Path
from .schema import GLYPHS, seal, digest


def merge(ir, receipt):
    ir['runtime'] = receipt
    if receipt.get('binding') and (receipt['binding'].get('source_sha256') != next(s['sha256'] for s in ir['sources'] if s['physical'] == ir['entry']['file']) or receipt.get('input_spec', {}).get('constructor', {}) != ir['entry']['constructor']):
        raise ValueError('runtime/source generation or constructor mismatch')
    if not receipt.get('runs'):
        ir['coverage'] = {'status': 'runtime-failed' if receipt.get('status') == 'failed' else 'runtime-unavailable', 'complete': False, 'reason': receipt.get('reason', 'no runs')}
        return seal(ir)
    source_root = Path(receipt['binding']['source_root'])
    # Cross-file runtime locations retain their own recorded generation even
    # when the conservative static extractor cannot expand that definition.
    known_sources = {s['physical'] for s in ir['sources']}
    for relative, sha in receipt['binding'].get('source_generation', {}).items():
        file = str(source_root / relative)
        if file not in known_sources:
            ir['sources'].append({'path': file, 'physical': file, 'cell': None, 'sha256': sha, 'unit_sha256': sha})
    static = list(ir['nodes'])
    root = next(n['id'] for n in static if not n.get('parent'))
    graph_nodes, graph_edges = [], []
    branch_hits = {}
    def add(identity, kind, label, parent, evidence, source=None, **extra):
        n = {'id': identity, 'kind': kind, 'label': label, 'parent': parent,
             'source': source or [], 'runtime_evidence': evidence, 'glyph': GLYPHS[kind],
             'granularity': 'composite' if kind == 'composite' else 'atomic', 'evidence_status': 'runtime-only', **extra}
        graph_nodes.append(n)
        return identity
    def edge(a, b, kind='data', slot='in', source_slot='out'):
        if a == b: return
        graph_edges.append({'id': f'rt-edge:{len(graph_edges)}', 'source': a, 'target': b, 'source_port': str(source_slot),
                            'target_port': str(slot), 'kind': kind, 'evidence': 'runtime-state' if kind == 'state-write' else 'runtime-tensor'})
    observed_root = add('runtime-observations', 'composite', 'CPU observed execution', root, [{'receipt': receipt.get('trace_digest')}])
    for index, run in enumerate(receipt['runs']):
        prefix = f'runtime:{index}:'
        proof = [{'case': run['case'], 'mode': run['mode'], 'status': run['status']}]
        group = add(prefix + 'run', 'composite', run['case'] + ' · ' + run['mode'], observed_root, proof)
        for hit in run.get('branches', []):
            key = (str(source_root / hit['file']), hit['line'], hit.get('column', 0))
            branch_hits.setdefault(key, set()).add(hit['outcome'])
        calls = {v['id']: v for v in run.get('module_events', []) if v['event'] == 'enter'}
        for call in calls.values():
            add(prefix + call['id'], 'composite', call['path'] or ir['title'], prefix + call['parent_call'] if call.get('parent_call') else group,
                proof, semantic_type='observed-module-call', module_path=call['path'], framework_type=call.get('module_type'))
        producers = {}
        for parameter in run.get('parameters', []):
            canonical = parameter['aliases'][0]
            key = 'parameter:' + canonical
            if key not in producers:
                producers[key] = add(prefix + key, 'parameter', canonical, group, proof, parameter_identity=canonical,
                                     aliases=parameter['aliases'], tensor=parameter)
        for buffer in run.get('buffers', []):
            key = 'buffer:' + buffer['name']
            producers[key] = add(prefix + key, 'buffer', buffer['name'], group, proof, tensor=buffer)
        for event in run['events']: producers[event['id']] = prefix + event['id']
        for event in run['events']:
            source = event.get('source')
            evidence = [{'file': str(source_root / source['file']), 'line': source['line'], 'end_line': source['line'],
                         'column': 0, 'end_column': 0, 'symbol': source['symbol'], 'expression': event['operator']}] if source else []
            known = event['operator'].startswith('aten.')
            node = add(prefix + event['id'], 'compute' if known else 'opaque', event['operator'],
                       prefix + event['module_call'] if event.get('module_call') in calls else group,
                       [*proof, {'event': event['id']}], evidence,
                       operator=event['operator'], inputs=event['inputs'], outputs=event['outputs'], mutable=event['mutable'])
            if not known: graph_nodes[-1]['evidence_status'] = 'opaque'
            for i, tensor in enumerate(event['inputs']):
                producer = tensor['producer']
                key = producer or ('unresolved:' + tensor['id'])
                if key not in producers:
                    producers[key] = add(prefix + key, 'interface' if producer and producer.startswith('input:') else 'opaque', key, group, proof,
                                         tensor=tensor, reason=None if producer else 'tensor producer not observed')
                edge(producers[key], node, 'state-write' if event['mutable'] else 'data', i, tensor.get('slot', 'out'))
            if evidence:
                for original in static:
                    if original['kind'] not in {'compute', 'opaque'}: continue
                    matches = any(s['file'] == evidence[0]['file'] and s['line'] <= source['line'] <= s['end_line'] for s in original['source'])
                    if matches:
                        original['runtime_evidence'].append({'run': index, 'event': event['id'], 'node': node, 'match': 'source-line-associated; not operator-equivalence proof'})
                        if original['kind'] != 'opaque': original['evidence_status'] = 'source-runtime-associated'
        output = add(prefix + 'outputs', 'interface', 'model outputs', group, proof, role='output')
        for i, tensor in enumerate(run.get('outputs', [])):
            key = tensor['producer'] or ('unresolved:' + tensor['id'])
            if key not in producers:
                producers[key] = add(prefix + key, 'opaque', key, group, proof, reason='output producer unresolved')
            edge(producers[key], output, slot=i, source_slot=tensor.get('slot', 'out'))
    ir['nodes'].extend(graph_nodes)
    ir['edges'].extend(graph_edges)
    coverage = []
    for branch in ir['branches']:
        seen = branch_hits.get((branch['file'], branch['line'], branch.get('column', 0)), set())
        missing = sorted(set(branch['outcomes']) - seen)
        coverage.append({**branch, 'observed': sorted(seen), 'missing': missing})
        node = next(n for n in ir['nodes'] if n['id'] == branch['id'])
        node['runtime_branch_outcomes'] = sorted(seen)
        node['evidence_status'] = 'unobserved-branch' if missing else 'static-runtime-consistent'
    bounded_exhaustive = receipt.get('finite_domain', {}).get('exhaustive', False)
    expected = {(c['id'], mode) for c in receipt['input_spec']['cases'] for mode in receipt['input_spec']['modes']}
    actual = [(r['case'], r['mode']) for r in receipt['runs']]
    success = (receipt['status'] == 'passed' and receipt.get('source_unchanged') is True
               and receipt.get('isolation', {}).get('status') == 'passed'
               and receipt['binding'].get('spec_digest') == digest(receipt['input_spec'])
               and set(actual) == expected and len(actual) == len(expected)
               and all(run['status'] == 'passed' and not run.get('truncated') and run.get('replay', {}).get('matched') for run in receipt['runs']))
    unsupported = [n['id'] for n in ir['nodes'] if n['kind'] == 'opaque']
    complete = bool(bounded_exhaustive and success and not unsupported and not ir.get('coverage_blockers') and all(not c['missing'] and c['kind'] != 'loop' for c in coverage))
    ir['coverage'] = {'status': 'bounded-branch-verified' if complete else 'partial', 'complete': complete,
                      'scope': 'declared concrete input set × declared modes; selected forward and expanded local helper source',
                      'finite_domain': receipt.get('finite_domain'), 'branches': coverage,
                      'opaque_nodes': len(unsupported), 'coverage_blockers': ir.get('coverage_blockers', []), 'all_runs_passed': success,
                      'claimed_for_arbitrary_inputs': False,
                      'reason': 'if/if-expression outcomes and finite outputs verified for declared cases' if complete else 'unobserved/unsupported source, failed run, or input domain not exhaustively declared'}
    from .motifs import recognize_runtime
    recognize_runtime(ir)
    from .observations import index_observations
    index_observations(ir, receipt)
    from .source_runtime import build_index
    ir['source_runtime_index'] = build_index(ir)
    return seal(ir)
