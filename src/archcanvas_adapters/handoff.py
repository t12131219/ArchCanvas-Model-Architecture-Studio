"""A bounded, data-only work request for the calling Agent; no agent execution."""
from __future__ import annotations

import copy


def starter_rules():
    """Portable examples. Matching is not proof of tensor semantics."""
    return {
        'attribute-call': {
            'schema': 'archcanvas-source-rule/1', 'name': 'Attribute callable source view',
            'match': {'type': 'Call', 'fields': {'func': {'type': 'Attribute'}}},
            'nodes': [
                {'key': 'call', 'at': [], 'parent': None, 'kind': 'SourceCall'},
                {'key': 'callable', 'at': ['func'], 'parent': 'call', 'kind': 'SourceExpression'},
                {'key': 'receiver', 'at': ['func', 'value'], 'parent': 'callable', 'kind': 'SourceExpression'},
            ],
            'relations': [
                {'source': 'receiver', 'target': 'callable', 'proof': 'expression-input'},
                {'source': 'callable', 'target': 'call', 'proof': 'expression-input'},
            ],
        },
        'list-comprehension': {
            'schema': 'archcanvas-source-rule/1', 'name': 'Single generator source view',
            'match': {'type': 'ListComp', 'fields': {
                'generators': [{'type': 'comprehension', 'fields': {'is_async': 0}}]}},
            'nodes': [
                {'key': 'loop', 'at': [], 'parent': None, 'kind': 'SourceLoop'},
                {'key': 'iterable', 'at': ['generators', 0, 'iter'], 'parent': 'loop', 'kind': 'SourceExpression'},
                {'key': 'body', 'at': ['elt'], 'parent': 'loop', 'kind': 'SourceExpression'},
            ],
            'relations': [{'source': 'iterable', 'target': 'body', 'proof': 'comprehension-iteration'}],
        },
    }


def build_handoff(files, entry, config=None, registry=None, probe_result=None):
    from archcanvas_preview import analyze
    from .registry import AdapterRegistry, _adaptation_coverage

    bundle = analyze(files, entry, config, semantic_mode='summary')
    if registry is not None:
        bundle = AdapterRegistry(registry).preview(bundle, files)
    else:
        bundle = _adaptation_coverage(bundle, files)
    nodes = {n['id']: n for n in bundle['ir']['nodes']}
    requests = []
    for item in bundle['adaptationRequests']:
        node = nodes[item['nodeId']]
        request = copy.deepcopy(item)
        request.update(label=node['label'], reason=node.get('semantic', {}).get('reason', 'unverified source boundary'),
                       source=[copy.deepcopy(bundle['evidence'][key]) for key in item['sourceEvidence']],
                       authority='source-structure-only', generationContract=None)
        requests.append(request)
    probe = {'policy': 'optional-explicit-separate-step', 'runByHandoff': False,
             'note': 'A failed, unavailable or incomplete CPU probe does not block source-only views. Observations never prove all inputs.'}
    if probe_result is not None:
        from archcanvas_summary_semantic.schema import digest
        from .registry import AdapterError
        receipt = probe_result['receipt']
        binding = receipt.get('binding', {})
        # This is diagnostic provenance, never a grant of semantic authority.
        # Reject results for another source/config rather than mislabelling them.
        expected_generation = {name: digest(value.encode('utf-8')) for name, value in sorted(files.items())}
        if (receipt.get('profile') != 'summary-aten-observed/1'
                or binding.get('entry') != bundle['entry']
                or binding.get('source_generation') != expected_generation
                or binding.get('source_manifest_sha256') != bundle['sourceSha256']
                or receipt.get('input_spec', {}).get('constructor', {}) != bundle['config']
                or receipt.get('status') not in {'passed', 'failed', 'unavailable'}):
            raise AdapterError('CPU probe diagnostic does not match this source, entry and constructor.')
        probe.update(runByHandoff=True, status=receipt['status'],
                     modelExecuted=receipt.get('model_executed'),
                     runtimeVerified=bool(receipt.get('runtimeVerified')),
                     reason=receipt.get('reason'), receiptDigest=digest(receipt),
                     runs=[{k: row[k] for k in ('case', 'mode', 'status', 'reason', 'truncated', 'replay') if k in row}
                           for row in receipt.get('runs', [])],
                     next='inspect-unresolved-source-and-author-view',
                     authority='diagnostic-only')
    return {
        'schema': 'archcanvas-agent-view-handoff/1', 'entry': bundle['entry'],
        'sourceSha256': bundle['sourceSha256'], 'semanticIrDigest': bundle['ir']['semantic_ir']['ir_digest'],
        'sourceFiles': [{k: row[k] for k in ('path', 'sha256')} for row in bundle['files']],
        'config': copy.deepcopy(bundle['config']), 'modelExecuted': probe.get('modelExecuted', False), 'sourceWrites': False,
        'probe': probe,
        'requests': requests, 'coverage': bundle['coverage'],
        'starterRules': starter_rules(), 'ruleDiagnostics': bundle.get('ruleDiagnostics', []),
        'workflow': ['inspect-request-source', 'author-rule', 'adapter rule-validate',
                     'adapter scaffold --rules', 'adapter validate', 'adapter register',
                     'adapter preview --semantic-mode summary', 'open-fresh-native-preview'],
        'limits': {'nodes': 480, 'edges': 3600, 'hierarchyDepth': 12, 'files': 80, 'sourceBytes': 2_000_000},
        'unavailableImplementation': 'Keep an opaque source-backed call card; labels/notes may explain the limitation. Never invent internal topology, tensor ports or an execution contract.',
        'agentDispatch': 'The active Codex or Claude Code Agent follows this request. No model API, background Agent, or Python plugin is started.',
    }
