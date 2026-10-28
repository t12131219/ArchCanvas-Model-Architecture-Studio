"""Independent facts, evidence states and presentation contracts (no torch import)."""
import hashlib
import json

SCHEMA = 'archcanvas-source-semantic/2'
COVERAGE_CONTRACT = (
    '在明确限定的模型、输入范围和运行模式内，完整覆盖并验证所有分支。'
    '任何任意 PyTorch 模型均无 opaque 无法保证：未知自定义算子、外部依赖或动态 Python 行为可能无法从现有证据中还原。'
)
KINDS = {'composite', 'compute', 'parameter', 'buffer', 'state', 'value-alias', 'control', 'interface', 'opaque'}
EVIDENCE = {'static-only', 'runtime-only', 'source-runtime-associated', 'static-runtime-consistent', 'unobserved-branch', 'conflict', 'opaque'}
GLYPHS = {
    'composite': {'shape': 'frame', 'fill': '#edf2ff'},
    'compute': {'shape': 'rounded-rect', 'fill': '#dceffc'},
    'parameter': {'shape': 'resource', 'fill': '#f3dff1'},
    'buffer': {'shape': 'resource', 'fill': '#f5e6d6'},
    'state': {'shape': 'resource', 'fill': '#fbe8d3'},
    'value-alias': {'shape': 'value', 'fill': '#e8f6ef'},
    'control': {'shape': 'diamond', 'fill': '#fff0c1'},
    'interface': {'shape': 'port', 'fill': '#e7edf4'},
    'opaque': {'shape': 'dashed-rect', 'fill': '#fbe4e4'},
}

def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def seal(ir):
    ir.pop('ir_digest', None)
    ir['ir_digest'] = digest(ir)
    return ir


def source_graph_digest(ir):
    """Bind certificates to source facts; appending observations cannot change it."""
    nodes = [{k: v for k, v in n.items() if k not in {'runtime_evidence', 'evidence_status', 'runtime_branch_outcomes'}}
             for n in ir['nodes'] if n['id'] != 'runtime-observations' and not n['id'].startswith('runtime:')]
    ids = {n['id'] for n in nodes}
    edges = [e for e in ir['edges'] if e['source'] in ids and e['target'] in ids]
    files = {s['file'] for n in nodes for s in n.get('source', [])}
    generation = {s['path']: s['sha256'] for s in ir.get('sources', []) if s['path'] in files}
    return digest({'nodes': nodes, 'edges': edges, 'entry': ir['entry'], 'source_generation': generation})


def validate_ir(ir):
    errors = []
    if ir.get('schema') != SCHEMA:
        errors.append('unsupported schema')
    nodes = ir.get('nodes', [])
    by = {n['id']: n for n in nodes}
    if len(by) != len(nodes):
        errors.append('duplicate node IDs')
    for n in nodes:
        if n.get('kind') not in KINDS or n.get('evidence_status') not in EVIDENCE:
            errors.append('invalid kind/evidence: ' + n['id'])
        if n.get('parent') and n['parent'] not in by:
            errors.append('missing parent: ' + n['id'])
        seen, current = set(), n
        while current and current.get('parent'):
            if current['id'] in seen:
                errors.append('cyclic hierarchy: ' + n['id'])
                break
            seen.add(current['id'])
            current = by.get(current['parent'])
        if not n.get('source') and not n.get('runtime_evidence'):
            errors.append('node without evidence: ' + n['id'])
        for source in n.get('source', []):
            if source['file'] not in {s['path'] for s in ir['sources']} or source['line'] < 1:
                errors.append('invalid source: ' + n['id'])
    edge_ids = set()
    for e in ir.get('edges', []):
        if e['id'] in edge_ids or e['source'] not in by or e['target'] not in by:
            errors.append('invalid edge: ' + e['id'])
        edge_ids.add(e['id'])
        if e.get('evidence') not in {'source-dependency', 'runtime-tensor', 'framework-contract', 'runtime-state'}:
            errors.append('invalid edge evidence: ' + e['id'])
    for motif in ir.get('motifs', []):
        if not set(motif['members']) <= by.keys() or not motif.get('evidence'):
            errors.append('invalid motif: ' + motif['id'])
    from .iteration import validate_contracts
    errors.extend(validate_contracts(nodes, ir.get('edges', [])))
    from .identity import validate as validate_identities
    errors.extend(validate_identities(nodes, ir.get('edges', [])))
    from .symbolic_values import validate as validate_values
    errors.extend(validate_values(nodes, ir.get('edges', [])))
    from .structure import validate as validate_structure
    errors.extend(validate_structure(nodes, ir.get('edges', [])))
    certificates = {c['id']: c for c in ir.get('semantic_contracts', [])}
    if certificates and ir.get('semantic_contract_basis') != source_graph_digest(ir):
        errors.append('semantic certificates refer to a different source graph')
    if len(certificates) != len(ir.get('semantic_contracts', [])):
        errors.append('duplicate semantic certificate IDs')
    for c in certificates.values():
        if c.get('rule_version') != 'source-contracts/1' or c.get('node') not in by or not set(c.get('members', [])) <= by.keys() or not set(c.get('edges', [])) <= edge_ids:
            errors.append('invalid semantic certificate: ' + c['id'])
        if not set(c.get('dependencies', [])) <= certificates.keys() or not c.get('proof') or not c.get('scope'):
            errors.append('missing semantic certificate evidence: ' + c['id'])
    from .contracts import validate_source_chains
    errors.extend(validate_source_chains(ir))
    for n in nodes:
        if n.get('return_selection'):
            selected = n['return_selection']['selected']
            if selected not in by or not any(e['source'] == selected and e['target'] == n['id'] and e['kind'] == 'interface-binding' for e in ir.get('edges', [])):
                errors.append('invalid invocation return selection: ' + n['id'])
    index = ir.get('observation_index')
    if index:
        receipt = ir.get('runtime', {})
        runs = receipt.get('runs', [])
        if index.get('schema') != 'archcanvas-observation-index/1' or index.get('receipt_digest') != receipt.get('trace_digest') or index.get('source_binding') != receipt.get('binding'):
            errors.append('invalid observation evidence binding')
        for a in index.get('module_associations', []):
            static = by.get(a.get('node'), {})
            if not static or static.get('module_path') != a.get('path') or static['id'].startswith('runtime:'):
                errors.append('invalid observation module association')
            for o in a.get('observations', []):
                ri = o.get('run', -1)
                call = by.get(o.get('call'), {})
                if not 0 <= ri < len(runs) or o.get('case') != runs[ri]['case'] or o.get('mode') != runs[ri]['mode'] or call.get('module_path') != a.get('path') or not o.get('call', '').startswith(f'runtime:{ri}:'):
                    errors.append('invalid observed invocation')
        for g in index.get('trace_groups', []):
            representative = g.get('representative')
            if representative not in by or not any(r.get('node') == representative for r in g.get('runs', [])):
                errors.append('missing observed trace representative')
            for row in g.get('node_correspondences', []):
                ri = row.get('run', -1)
                mapping = row.get('mapping', {})
                expected = {n['id'] for n in nodes if n['id'].startswith(f'runtime:{ri}:')}
                if set(mapping) != expected or len(set(mapping.values())) != len(mapping) or not set(mapping.values()) <= by.keys():
                    errors.append('invalid observed trace correspondence')
    if 'source_runtime_index' in ir:
        from .source_runtime import build_index
        try:
            if ir['source_runtime_index'] != build_index(ir):
                errors.append('invalid source-runtime integration evidence')
        except (KeyError, TypeError, ValueError, IndexError):
            errors.append('invalid source-runtime integration evidence')
    if ir.get('ir_digest') != digest({k: v for k, v in ir.items() if k != 'ir_digest'}):
        errors.append('IR digest mismatch')
    return {'ok': not errors, 'errors': errors}
