"""Attach independently checked rule views to precise opaque source regions.

These are source inspection cards in the existing preview engine. Original
opaque ports, nodes and edges remain authoritative and are never replaced.
"""
from __future__ import annotations

import ast
import copy


def apply_rule_adapters(bundle, files, definitions):
    from .registry import (AdapterError, _corpus, _source, _entry, _preview_evidence,
                           _local_call_entries, _local_owner_entries, _canonical, _sha)
    corpus = _corpus(files)
    result = copy.deepcopy(bundle)
    ir = result['ir']
    # Native Summary already owns the known computation. Restrict new syntax
    # cards to its actual unknowns instead of duplicating every known call
    # below a source-module composite. Legacy inspection trees retain their
    # existing anchoring contract.
    native = bool(ir.get('semantic_ir'))
    originals = [node for node in ir['nodes'] if node.get('kind') == 'opaque'
                 or not native and node.get('sourceStructure')]
    by_id = {node['id']: node for node in ir['nodes']}
    original_ids = {node['id'] for node in originals if not node.get('sourceRuleId')}
    span_counts = {}
    def span_key(source):
        return (source.get('file', source.get('path')), source['line'], source['column'], source['endLine'], source['endColumn'])
    for unit in corpus.units.values():
        for item in ast.walk(unit.tree):
            if hasattr(item, 'lineno') and getattr(item, 'end_lineno', None) is not None:
                key = (unit.path, item.lineno, item.col_offset, item.end_lineno, item.end_col_offset)
                span_counts[key] = span_counts.get(key, 0) + 1

    def evidence(node):
        return [result['evidence'][key] for key in node.get('source_evidence', []) if key in result['evidence']]

    def contains(outer, inner):
        return (outer.get('file', outer.get('path')) == inner.get('file', inner.get('path'))
                and (outer['line'], outer['column']) <= (inner['line'], inner['column'])
                and (outer['endLine'], outer['endColumn']) >= (inner['endLine'], inner['endColumn']))

    def equal(left, right):
        return contains(left, right) and contains(right, left)

    def below(node, ancestor):
        cursor, seen = node, set()
        while cursor and cursor['id'] not in seen:
            if cursor['id'] == ancestor['id']:
                return True
            seen.add(cursor['id']); cursor = by_id.get(cursor.get('parent'))
        return False

    def in_branch_scope(node, source):
        """Branch cards share their If span; their actual bodies do not.

        Check every enclosing branch against the authored AST before choosing
        an anchor. Source definitions reached through a resolved local call
        may live outside that If and retain their invocation's branch.
        """
        cursor = node
        while cursor:
            if cursor.get('sourceKind') == 'SourceBranch':
                for span in evidence(cursor):
                    if not contains(span, source):
                        continue
                    unit = next((unit for unit in corpus.units.values() if unit.path == span.get('file')), None)
                    condition = cursor.get('sourceParameters', {}).get('condition')
                    owners = [] if unit is None else [item for item in ast.walk(unit.tree)
                        if isinstance(item, ast.If) and equal(_source(unit, item), span)]
                    if len(owners) != 1:
                        return False
                    owner = owners[0]; predicate = ast.unparse(owner.test)
                    statements = owner.body if condition == predicate else owner.orelse if condition == f'not ({predicate})' else []
                    if not any(contains(_source(unit, item), source) for item in statements):
                        return False
            cursor = by_id.get(cursor.get('parent'))
        return True

    def add_evidence(source):
        projection = _preview_evidence(source)
        identity = 'e-' + _sha(_canonical(projection))[:16]
        result['evidence'][identity] = projection
        return identity

    added, applications = 0, result.setdefault('sourceRuleApplications', [])
    existing = {(item['ruleId'], item['matchKey'], item['boundary']): item for item in applications}
    for adapter in definitions:
        if adapter['config'] != result.get('config', {}):
            continue
        # Whole-callee expansion is allowed only for the resolved callable,
        # never an unrelated custom method on the same class.
        try:
            _, _, function, _, unit, _ = _entry(corpus, adapter['binding']['entry'], None)
            is_callable = equal(_source(unit, function), adapter['binding']['methodSpan'])
        except AdapterError:
            # Explicit constructor/helper methods need no default forward.
            is_callable = False
        relevant = adapter['binding']['entry'] == result['entry'] or any(
            adapter['binding']['entry'] in (_local_call_entries(node, result, corpus) | _local_owner_entries(node, result, corpus))
            for node in originals)
        facts = {node['id']: node for node in adapter['children']}
        for application in adapter['applications']:
            match_source = application['source']
            candidates = []
            for boundary in originals:
                whole = is_callable and adapter['binding']['entry'] in _local_call_entries(boundary, result, corpus)
                if boundary['id'] in original_ids and (whole or any(contains(span, match_source) for span in evidence(boundary))) and in_branch_scope(boundary, match_source):
                    candidates.append(boundary)
            # Nested opaque regions own their own views. Separate invocation
            # branches may share a definition, and each retains its instance.
            candidates = [node for node in candidates if not any(
                other['id'] != node['id'] and below(other, node) for other in candidates)]
            if not candidates and relevant:
                result.setdefault('ruleDiagnostics', []).append({'ruleId': application['ruleId'],
                    'matchKey': application['matchKey'], 'message': 'Verified source match has no matching opaque region in this preview; original graph retained.'})
            for boundary in candidates:
                receipt_key = (application['ruleId'], application['matchKey'], boundary['id'])
                if receipt_key in existing:
                    receipt = existing[receipt_key]
                    if receipt.get('adapter') == adapter['id']:
                        receipt['labels'] = {identity: adapter['presentation']['labels'].get(fact_id, facts[fact_id]['label'])
                            for fact_id, identity in receipt.get('nodeMap', {}).items()}
                    continue
                descendants = [node for node in ir['nodes'] if below(node, boundary)]
                anchors = [node for node in descendants if node['id'] in original_ids and in_branch_scope(node, match_source)
                    and any(contains(span, match_source) for span in evidence(node))]
                def rank(node):
                    spans = [span for span in evidence(node) if contains(span, match_source)]
                    return min((span['endLine'] - span['line'], span['endColumn'] - span['column']) for span in spans)
                anchor = min(anchors, key=rank) if anchors else boundary
                mapping, pending = {}, [facts[identity] for identity in application['nodeIds']]
                root_id = application['rootId']
                reused, omitted = [], 0
                while pending:
                    progressed = False
                    for fact in list(pending):
                        parent = fact.get('parentId')
                        if parent is not None and parent not in mapping:
                            continue
                        pending.remove(fact); progressed = True
                        target_parent = mapping.get(parent, anchor['id'])
                        # Reuse an exact source card under this same parent.
                        # Never move an unrelated manual or canonical object.
                        same = [node for node in descendants if span_counts.get(span_key(fact['source'])) == 1 and
                                (fact['id'] == root_id and node['id'] == anchor['id'] or node.get('parent') == target_parent)
                                and (fact['id'] == root_id or node.get('sourceStructure'))
                                and any(equal(span, fact['source']) for span in evidence(node))]
                        same.sort(key=lambda node: node['id'])
                        if len(same) == 1:
                            node = same[0]; mapping[fact['id']] = node['id']; reused.append(node['id'])
                            continue
                        depth, cursor = 1, by_id.get(target_parent)
                        while cursor:
                            depth += 1; cursor = by_id.get(cursor.get('parent'))
                        if len(ir['nodes']) >= 480 or depth > 12:
                            omitted += 1
                            continue
                        identity = boundary['id'] + '/rule-' + _sha(adapter['id'] + fact['id'])[:16]
                        parameters = copy.deepcopy(fact.get('parameters', {}))
                        parameters.update({'sourceRuleId': application['ruleId'], 'sourceMatch': application['matchKey']})
                        node = {'id': identity, 'parent': target_parent, 'kind': 'source_structure',
                                'label': adapter['presentation']['labels'].get(fact['id'], fact['label']),
                                'sourceParameters': parameters, 'source_evidence': [add_evidence(fact['source'])],
                                'expression': fact['source']['expression'], 'certainty': 'syntax',
                                'sourceStructure': True, 'sourceKind': fact['kind'],
                                'sourceAdapterId': adapter['id'], 'sourceRuleId': application['ruleId'],
                                'generationContract': None}
                        ir['nodes'].append(node); by_id[identity] = node; descendants.append(node)
                        mapping[fact['id']] = identity; added += 1
                    if not progressed:
                        omitted += len(pending)
                        break
                edge_ids = []
                for relation in adapter['dependencies']:
                    if relation['sourceId'] not in mapping or relation['targetId'] not in mapping:
                        continue
                    producer, consumer = mapping[relation['sourceId']], mapping[relation['targetId']]
                    if producer == consumer:
                        continue
                    # Overlapping saved templates can prove the same read.
                    # Preserve the existing arrow rather than drawing it twice.
                    same = next((edge for edge in ir['edges'] if edge.get('syntaxOnly')
                        and edge.get('role') == 'source_dependency' and edge.get('source') == producer
                        and edge.get('target') == consumer and edge.get('sourcePort') == 'out'
                        and edge.get('targetPort') == 'source-dependency'), None)
                    if same:
                        edge_ids.append(same['id'])
                        continue
                    if len(ir['edges']) >= 3600:
                        omitted += 1
                        continue
                    identity = 'rule-edge-' + _sha(boundary['id'] + adapter['id'] + relation['id'])[:20]
                    if any(edge['id'] == identity for edge in ir['edges']):
                        continue
                    ir['edges'].append({'id': identity, 'source': producer, 'target': consumer,
                        'sourcePort': 'out', 'targetPort': 'source-dependency', 'wire': producer + ':out',
                        'role': 'source_dependency', 'source_evidence': [add_evidence(relation['source'])],
                        'syntaxOnly': True, 'sourceAdapterId': adapter['id'], 'sourceRuleId': application['ruleId']})
                    edge_ids.append(identity)
                receipt = {'adapter': adapter['id'], 'ruleId': application['ruleId'],
                    'matchKey': application['matchKey'], 'boundary': boundary['id'], 'anchor': anchor['id'],
                    'nodes': list(mapping.values()), 'reusedNodes': reused, 'edges': edge_ids,
                    'nodeMap': mapping, 'labels': {identity: adapter['presentation']['labels'].get(fact_id, facts[fact_id]['label'])
                        for fact_id, identity in mapping.items()},
                    'truncated': bool(omitted), 'authority': 'source-structure-only'}
                applications.append(receipt); existing[receipt_key] = receipt
    if added or applications != bundle.get('sourceRuleApplications', []):
        result['canonicalIR'] = _canonical(ir); result['irSha256'] = _sha(result['canonicalIR'])
        result['id'] = 'source-' + _sha(result['entry'] + result['sourceSha256'] + result['canonicalIR'])[:16]
    return result
