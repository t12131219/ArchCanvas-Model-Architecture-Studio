"""Project independently verified syntax cards into the native Summary view.

The source computation remains unchanged. Added objects are opaque inspection
cards, not tensor operations, and carry no generation or runtime authority.
"""
from __future__ import annotations

import copy


def native_inspection_views(bundle, files):
    from archcanvas_preview.semantic_bridge import _to_bundle
    from archcanvas_summary_semantic.schema import digest, seal, source_graph_digest, validate_ir
    from .registry import AdapterError

    native = bundle['ir'].get('semantic_ir')
    if not native:
        return bundle
    prior = native.get('source_inspection_views', {})
    previous_nodes = set(prior.get('nodes', []))
    previous_edges = set(prior.get('edges', []))
    base_nodes = [n for n in native['nodes'] if n['id'] not in previous_nodes]
    base_edges = [e for e in native['edges'] if e['id'] not in previous_edges]
    base_ids = {n['id'] for n in base_nodes}
    cards = [n for n in bundle['ir']['nodes'] if n['id'] not in base_ids]
    if not cards and not previous_nodes:
        return bundle
    if any(not (n.get('sourceStructure') and n.get('sourceAdapterId')
                and n.get('generationContract') is None) for n in cards):
        raise AdapterError('Native inspection cards require independently verified source adapters.')

    derived = copy.deepcopy(native)
    derived['nodes'] = copy.deepcopy(base_nodes)
    derived['edges'] = copy.deepcopy(base_edges)
    for card in cards:
        locations = []
        for key in card['source_evidence']:
            source = bundle['evidence'][key]
            locations.append({'file': source['file'], 'line': source['line'],
                              'column': source['column'], 'end_line': source['endLine'],
                              'end_column': source['endColumn'], 'expression': source['expression']})
        derived['nodes'].append({
            'id': card['id'], 'parent': card['parent'], 'source_parent': card['parent'],
            'kind': 'opaque', 'label': card['label'], 'source': locations,
            'evidence_status': 'opaque', 'granularity': 'atomic', 'runtime_evidence': [],
            'glyph': {'shape': 'dashed-rect', 'fill': '#f0f0ed'},
            'semantic_type': 'source-inspection', 'inspection_only': True,
            'reason': 'Source inspection only; tensor semantics and runtime path remain unverified.',
            'sourceAdapterId': card['sourceAdapterId'],
            'sourceKind': card['sourceKind'],
            'sourceParameters': copy.deepcopy(card.get('sourceParameters', {})),
            'generationContract': None,
        })
    base_edge_ids = {e['id'] for e in base_edges}
    arrows = [e for e in bundle['ir']['edges'] if e['id'] not in base_edge_ids]
    if any(not (e.get('syntaxOnly') and e.get('sourceAdapterId')) for e in arrows):
        raise AdapterError('Native inspection arrows require syntax-only source proofs.')
    for arrow in arrows:
        derived['edges'].append({
            'id': arrow['id'], 'source': arrow['source'], 'target': arrow['target'],
            'source_port': arrow['sourcePort'], 'target_port': arrow['targetPort'],
            'kind': 'source-inspection', 'evidence': 'source-dependency',
            'syntaxOnly': True, 'sourceAdapterId': arrow['sourceAdapterId'],
        })
    derived['source_inspection_views'] = {
        'schema': 'archcanvas-source-inspection-views/1',
        'base_ir_digest': prior.get('base_ir_digest', native['ir_digest']),
        'base_graph_digest': digest({'nodes': base_nodes, 'edges': base_edges}),
        'nodes': [n['id'] for n in cards], 'edges': [e['id'] for e in arrows],
        'authority': 'source-structure-only', 'tensorGeneration': False,
    }
    # Existing certificates still describe exactly the original computation;
    # bind them to this graph without certifying any inspection object.
    if 'semantic_contract_basis' in derived:
        derived['semantic_contract_basis'] = source_graph_digest(derived)
    seal(derived)
    validation = validate_ir(derived)
    if not validation['ok']:
        raise AdapterError('Native inspection view validation failed: ' + '; '.join(validation['errors'][:3]))
    projected = _to_bundle(derived, files, bundle['entry'], bundle.get('config', {}))
    result = copy.deepcopy(bundle)
    for key in ('id', 'ir', 'canonicalIR', 'irSha256', 'evidence', 'semantic'):
        result[key] = projected[key]
    projected_nodes = {n['id']: n for n in result['ir']['nodes']}
    for original in bundle['ir']['nodes']:
        target = projected_nodes[original['id']]
        if original['id'] in base_ids:
            if 'sourceInspection' in original:
                target['sourceInspection'] = copy.deepcopy(original['sourceInspection'])
        else:
            # Preserve the portable syntax identity for re-registration and
            # rule reuse; the native semantic body remains the sealed copy.
            target.update({key: copy.deepcopy(value) for key, value in original.items()
                           if key not in {'semantic', 'semantic_kind', 'evidence_status', 'source_evidence'}})
    projected_edges = {e['id']: e for e in result['ir']['edges']}
    for arrow in arrows:
        projected_edges[arrow['id']].update(syntaxOnly=True, sourceAdapterId=arrow['sourceAdapterId'])
    # Projected node decorations are part of the portable transport digest.
    from .registry import _canonical, _sha
    result['canonicalIR'] = _canonical(result['ir'])
    result['irSha256'] = _sha(result['canonicalIR'])
    result['id'] = 'source-' + _sha(result['entry'] + result['sourceSha256'] + result['canonicalIR'])[:16]
    return result
