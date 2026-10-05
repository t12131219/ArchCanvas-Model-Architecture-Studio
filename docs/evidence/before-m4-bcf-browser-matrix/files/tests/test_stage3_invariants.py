"""Independent handwritten RebindInput holdouts; successful writes stay in /tmp.

Source byte expectations and edge relationships are authored here, not derived
from the implementation's staged output, expected-delta builder or candidates.
"""

from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from archcanvas_python import analyze_project
from archcanvas_transactions import TransactionError, TransactionManager


SOURCE = '''from torch import nn

class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.first = nn.Identity()
        self.branch = nn.Dropout(p=0.1)
        self.other = nn.GELU()
        self.sink = nn.ReLU(inplace=False)
        self.tail = nn.Identity()

    def forward(self, x, memory):
        original = self.first(x)
        candidate = self.branch(x)
        separate = self.other(memory)
        result = self.sink(original)  # exactly this Name, not every original
        return self.tail(result)
'''


def handwritten_expected(raw: bytes = SOURCE.encode()) -> bytes:
    before, after = b'self.sink(original)', b'self.sink(candidate)'
    assert raw.count(before) == 1
    return raw.replace(before, after, 1)


class Stage3InvariantTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='archcanvas-m3-oracle-', dir='/tmp')
        self.base = Path(self.directory.name)
        self.project = self.base / 'project'
        self.project.mkdir()
        self.model = self.project / 'model.py'
        self.model.write_bytes(SOURCE.encode())
        self.store = self.base / 'transactions'
        self.manager = TransactionManager(self.store)
        self.architecture = analyze_project(self.project, 'model:Model')
        self.initial_architecture = copy.deepcopy(self.architecture)

    def tearDown(self):
        self.directory.cleanup()

    def node(self, member: str, graph=None):
        nodes = [node for node in (graph or self.architecture)['nodes']
                 if node.get('instanceId', '').endswith('.' + member)]
        self.assertEqual(len(nodes), 1, 'The independent fixture has one call per module member')
        return nodes[0]

    def prepare(self, producer='branch', *, target_port=None, producer_port=None):
        # Invalid-source holdouts may remove a known call. Sending its original
        # identity with the current digest must reject, rather than guessing a
        # replacement node by its display name.
        target, source = self.node('sink', self.initial_architecture), self.node(producer, self.initial_architecture)
        return self.manager.prepare_rebind(
            root=self.project, entry='model:Model', nodeId=target['id'],
            portId=target_port or next(port['id'] for port in target['ports'] if port['name'] == 'input'),
            producerNodeId=source['id'],
            producerPortId=producer_port or next(port['id'] for port in source['ports'] if port['direction'] == 'out'),
            baseSourceDigest=self.architecture['sourceDigest'],
        )

    def assert_rejected(self, action):
        try:
            receipt = action()
        except TransactionError:
            return None
        self.assertIn(receipt['status'], {'Failed', 'Stale', 'RolledBack', 'ManualRecovery'})
        self.assertTrue(receipt.get('blockers') or receipt.get('recovery'))
        return receipt

    def approve_commit(self, receipt):
        self.assertEqual(receipt['status'], 'ReviewReady', receipt.get('blockers'))
        approved = self.manager.approve(receipt['id'], receipt['reviewDigest'])
        committed = self.manager.commit(receipt['id'], approved['approvalId'])
        self.assertEqual(committed['status'], 'Committed', committed.get('blockers'))
        return committed

    def relationships(self, graph):
        names = {}
        for node in graph['nodes']:
            if node.get('instanceId', '').count('.') >= 2:
                names[node['id']] = node['instanceId'].rsplit('.', 1)[-1]
            else:
                names[node['id']] = node['label']
        ports = {port['id']: port['name'] for node in graph['nodes'] for port in node['ports']}
        return {(names[edge['source']['nodeId']], ports[edge['source']['portId']],
                 names[edge['target']['nodeId']], ports[edge['target']['portId']], edge['role'])
                for edge in graph['edges']}

    def full_facts(self, graph):
        # Ignore source evidence offsets/digests, not any declared graph fact.
        nodes = copy.deepcopy(graph['nodes'])
        for node in nodes:
            node.pop('source', None)
            for origin in node.get('parameterOrigins', {}).values():
                for key in ('line', 'column', 'endLine', 'endColumn'):
                    origin.pop(key, None)
        return {'nodes': nodes, 'edges': copy.deepcopy(graph['edges'])}

    def test_review_and_commit_change_one_exact_name_and_one_binding(self):
        before_bytes = self.model.read_bytes()
        record = self.prepare()
        self.assertEqual(record['status'], 'ReviewReady', record.get('blockers'))
        self.assertEqual(self.model.read_bytes(), before_bytes)
        self.assertEqual(record['intent']['kind'], 'RebindInput')
        self.assertEqual(record['intent']['before']['variable'], 'original')
        self.assertEqual(record['intent']['after']['variable'], 'candidate')
        self.assertIn('-        result = self.sink(original)', record['diff'])
        self.assertIn('+        result = self.sink(candidate)', record['diff'])
        self.assertEqual(next(g['status'] for g in record['gates'] if g['id'] == 'G6'), 'not_run')
        committed = self.approve_commit(record)
        self.assertEqual(self.model.read_bytes(), handwritten_expected())
        observed = analyze_project(self.project, 'model:Model')
        self.assertEqual(observed, committed['committedArchitecture'])
        before_relations = self.relationships(self.architecture)
        after_relations = self.relationships(observed)
        self.assertEqual(before_relations, {
            ('x', 'x', 'Model', 'x', 'data'), ('memory', 'memory', 'Model', 'memory', 'memory'),
            ('x', 'x', 'first', 'input', 'data'), ('x', 'x', 'branch', 'input', 'data'),
            ('memory', 'memory', 'other', 'input', 'data'),
            ('first', 'output', 'sink', 'input', 'data'),
            ('sink', 'output', 'tail', 'input', 'data'), ('tail', 'output', 'output', 'value', 'data'),
        })
        self.assertEqual(after_relations - before_relations, {('branch', 'output', 'sink', 'input', 'data')})
        self.assertEqual(before_relations - after_relations, {('first', 'output', 'sink', 'input', 'data')})
        expected = self.full_facts(self.architecture)
        target_id, source_id = self.node('sink')['id'], self.node('branch')['id']
        source_edge = next(edge for edge in observed['edges'] if edge['target']['nodeId'] == target_id)
        changed = next(edge for edge in expected['edges'] if edge['target']['nodeId'] == target_id)
        # The manually declared intent changes the source and tensor on this
        # exact target edge; all other fields and stable output identities stay.
        self.assertEqual(source_edge['source']['nodeId'], source_id)
        source_port = next(p['id'] for p in self.node('branch')['ports'] if p['direction'] == 'out')
        changed['source'] = {'nodeId': source_id, 'portId': source_port}
        changed['tensorId'] = 'tensor:' + source_id + ':output'
        self.assertEqual(self.full_facts(observed), expected)

    def test_different_base_later_producer_and_invalid_ports_rejected(self):
        for action in (
            lambda: self.prepare('other'), lambda: self.prepare('tail'),
            lambda: self.prepare(target_port='invented-target-port'),
            lambda: self.prepare(producer_port='invented-producer-port'),
        ):
            with self.subTest(action=action):
                self.assert_rejected(action)
                self.assertEqual(self.model.read_bytes(), SOURCE.encode())

    def test_direct_base_input_is_a_compatible_dominating_producer(self):
        target = self.node('sink')
        producer = next(n for n in self.architecture['nodes'] if n['kind'] == 'Input' and n['label'] == 'x')
        record = self.manager.prepare_rebind(
            root=self.project, entry='model:Model', nodeId=target['id'],
            portId=next(p['id'] for p in target['ports'] if p['name'] == 'input'),
            producerNodeId=producer['id'], producerPortId=producer['ports'][0]['id'],
            baseSourceDigest=self.architecture['sourceDigest'],
        )
        self.approve_commit(record)
        self.assertEqual(self.model.read_bytes(), SOURCE.encode().replace(b'self.sink(original)', b'self.sink(x)', 1))
        observed = analyze_project(self.project, 'model:Model')
        target_edge = next(e for e in observed['edges'] if e['target']['nodeId'] == target['id'])
        self.assertEqual(target_edge['source'], {'nodeId': producer['id'], 'portId': producer['ports'][0]['id']})
        self.assertEqual(target_edge['tensorId'], 'tensor:input:model.Model:x:x')

    def test_candidate_sidecar_has_exact_names_and_conditional_signature(self):
        from archcanvas_python.rebind import inspect_rebind
        evidence = inspect_rebind(self.project, 'model:Model', self.node('sink')['id'])
        self.assertEqual(evidence['status'], 'supported')
        self.assertEqual(evidence['sourceDigest'], self.architecture['sourceDigest'])
        self.assertEqual(evidence['irDigest'], self.architecture['irDigest'])
        self.assertEqual(evidence['target']['slot']['expression'], 'original')
        self.assertEqual(evidence['target']['slot']['variable'], 'original')
        self.assertEqual({c['variable'] for c in evidence['candidates']}, {'x', 'original', 'candidate'})
        self.assertEqual({c['variable'] for c in evidence['excludedCandidates']}, {'memory', 'separate'})
        for candidate in evidence['candidates']:
            contract = candidate['contract']
            self.assertTrue(contract['conditional'])
            self.assertIs(contract['runtimeVerified'], False)
            self.assertEqual(contract['baseTensorId'], 'tensor:input:model.Model:x:x')
            self.assertEqual(contract['shape'], {'kind': 'symbol', 'identity': 'shape:tensor:input:model.Model:x:x'})
            self.assertEqual(contract['dtype'], {'kind': 'symbol', 'identity': 'dtype:tensor:input:model.Model:x:x'})
        self.assertEqual(self.model.read_bytes(), SOURCE.encode())

    def test_framework_mutations_cannot_prove_an_external_constructor(self):
        variants = {
            'direct-monkeypatch': 'nn.ReLU = nn.Identity\n',
            'setattr-monkeypatch': 'setattr(nn, "ReLU", nn.Identity)\n',
            'unknown-import-time-side-effect': 'patch_framework(nn)\n',
            'class-creation-hook': (
                'class Hook:\n'
                '    def __init_subclass__(cls):\n'
                '        nn.ReLU = nn.Identity\n'
                'class Trigger(Hook):\n'
                '    pass\n'
            ),
        }
        for reason, mutation in variants.items():
            with self.subTest(reason=reason):
                source = SOURCE.replace('from torch import nn\n', 'from torch import nn\n' + mutation)
                self.model.write_text(source, encoding='utf-8')
                self.architecture = analyze_project(self.project, 'model:Model')
                self.assert_rejected(self.prepare)
                self.assertEqual(self.model.read_text(encoding='utf-8'), source)

    def test_unsupported_source_regions_do_not_offer_writeback(self):
        variants = {
            'target-expression': SOURCE.replace('self.sink(original)', 'self.sink(original + candidate)'),
            'target-subscript': SOURCE.replace('self.sink(original)', 'self.sink(original[0])'),
            'keyword-slot': SOURCE.replace('self.sink(original)', 'self.sink(input=original)'),
            'unknown-producer': SOURCE.replace('self.branch = nn.Dropout(p=0.1)', 'self.branch = nn.Linear(4, 4)'),
            'inplace-producer': SOURCE.replace('self.branch = nn.Dropout(p=0.1)', 'self.branch = nn.Dropout(p=0.1, inplace=True)'),
            'inplace-consumer': SOURCE.replace('nn.ReLU(inplace=False)', 'nn.ReLU(inplace=True)'),
            'reassigned-candidate': SOURCE.replace('        result = self.sink(original)', '        candidate = self.first(x)\n        result = self.sink(original)'),
            'reassigned-original': SOURCE.replace('        result = self.sink(original)', '        original = self.branch(x)\n        result = self.sink(original)'),
            'unknown-mutation': SOURCE.replace('        result = self.sink(original)', '        original.zero_()\n        result = self.sink(original)'),
            'dynamic-branch': SOURCE.replace('        candidate = self.branch(x)', '        if x is not None:\n            candidate = self.branch(x)'),
            'nested-scope': SOURCE.replace('        candidate = self.branch(x)', '        def make_candidate():\n            return self.branch(x)\n        candidate = make_candidate()'),
            'constructor-shadow': SOURCE.replace('        super().__init__()', '        nn = object()\n        super().__init__()'),
        }
        for reason, source in variants.items():
            with self.subTest(reason=reason):
                self.model.write_text(source, encoding='utf-8')
                self.architecture = analyze_project(self.project, 'model:Model')
                self.assert_rejected(self.prepare)
                self.assertEqual(self.model.read_text(encoding='utf-8'), source)

    def test_staged_second_connection_tamper_cannot_enter_commit(self):
        record = self.prepare()
        self.assertEqual(record['status'], 'ReviewReady', record.get('blockers'))
        approved = self.manager.approve(record['id'], record['reviewDigest'])
        staged = self.store / record['id'] / 'staged' / 'model.py'
        staged.write_bytes(staged.read_bytes().replace(b'self.tail(result)', b'self.tail(candidate)', 1))
        self.assert_rejected(lambda: self.manager.commit(record['id'], approved['approvalId']))
        self.assertEqual(self.model.read_bytes(), SOURCE.encode())

    def test_parameter_approval_never_authorizes_connection_intent(self):
        branch = self.node('branch')
        parameter = self.manager.prepare(root=self.project, entry='model:Model', nodeId=branch['id'],
                                         parameter='p', value=0.2, baseSourceDigest=self.architecture['sourceDigest'])
        self.assertEqual(parameter['status'], 'ReviewReady')
        approval = self.manager.approve(parameter['id'], parameter['reviewDigest'])
        connection = self.prepare()
        self.assertEqual(connection['status'], 'ReviewReady', connection.get('blockers'))
        self.assert_rejected(lambda: self.manager.commit(connection['id'], approval['approvalId']))
        self.assertEqual(self.model.read_bytes(), SOURCE.encode())

    def test_rebind_after_approval_freshness_preserves_external_bytes(self):
        record = self.prepare()
        self.assertEqual(record['status'], 'ReviewReady', record.get('blockers'))
        approved = self.manager.approve(record['id'], record['reviewDigest'])
        later = SOURCE.encode() + b'\n# independent external edit after concrete connection approval\n'
        self.model.write_bytes(later)
        self.assert_rejected(lambda: self.manager.commit(record['id'], approved['approvalId']))
        self.assertEqual(self.model.read_bytes(), later)

    def test_rebind_write_failure_recovers_original_connection_bytes(self):
        record = self.prepare()
        self.assertEqual(record['status'], 'ReviewReady', record.get('blockers'))
        approved = self.manager.approve(record['id'], record['reviewDigest'])
        def fail_after_write(_record):
            self.assertEqual(self.model.read_bytes(), handwritten_expected())
            raise TransactionError('independent M3 write-after-verification failure')
        self.manager._verify_committed = fail_after_write
        result = self.assert_rejected(lambda: self.manager.commit(record['id'], approved['approvalId']))
        self.assertEqual(result['status'], 'RolledBack')
        self.assertEqual(self.model.read_bytes(), SOURCE.encode())

    def test_crlf_bom_and_comment_bytes_survive_name_splice(self):
        raw = b'\xef\xbb\xbf' + SOURCE.replace('\n', '\r\n').encode()
        self.model.write_bytes(raw)
        self.architecture = analyze_project(self.project, 'model:Model')
        self.approve_commit(self.prepare())
        self.assertEqual(self.model.read_bytes(), handwritten_expected(raw))


if __name__ == '__main__':
    unittest.main()
